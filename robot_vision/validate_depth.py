"""Validate the THUD synthetic depth encoding and camera intrinsics against the dataset's own 3D boxes.

Evidence used (no depth assumption is made in advance):
- One sensor has instance masks + 2D boxes, the other has 3D boxes in metres (same pose and
  timestamps). For each object visible in both, its masked depth pixels are back-projected to 3D
  and tested against its 3D box.
- Depth scale (far_m), planar-vs-ray interpretation and vertical field of view are fitted on one
  capture and then tested, unchanged, on other captures.
- Independent of depth: 3D boxes are projected with the candidate intrinsics and compared with the
  2D boxes.

Usage:
    python validate_depth.py --fit-capture Synthetic_Scenes/Office/dynamic/Capture_1 ^
        --test-captures Synthetic_Scenes/Office/dynamic/Capture_2 Synthetic_Scenes/Office/static/Capture_1
    (The recorded Stage 3 run also tested Synthetic_Scenes/Gym/dynamic/Capture_1; that capture is now excluded
    and the split guard refuses it.)
"""

from __future__ import annotations

import argparse
import json
import math
from collections import Counter
from datetime import datetime
from pathlib import Path

import numpy as np
from PIL import Image

import data_splits as ds
import run_paths as rp
import thud_data as td
import thud_depth as tdd
from check_camera_streams import box_iou, quat_rotate

SIGNS = np.array([[a, b, c] for a in (-1, 1) for b in (-1, 1) for c in (-1, 1)], dtype=float)
POSE_FIELDS = ("sequence_id", "timestamp")
MARGIN_SWEEP = (0.0, 0.005, 0.01, 0.02, 0.03)


def quat_matrix(q: dict) -> np.ndarray:
    return quat_rotate(q, np.eye(3)).T  # columns = rotated basis vectors


# ---------------------------------------------------------------- sample collection

def sensor_roles(records: dict) -> tuple[str, str]:
    ann = {}
    for (sid, _), cap in records.items():
        ann.setdefault(sid, set()).update(a["id"] for a in cap["annotations"])
    label = [s for s, a in ann.items() if "instance segmentation" in a and "bounding box" in a]
    box3d = [s for s, a in ann.items() if "bounding box 3D" in a]
    if len(label) != 1 or len(box3d) != 1:
        raise RuntimeError(f"Cannot identify label / 3D-box sensors from annotations: {ann}")
    return label[0], box3d[0]


def load_records(capture_dir: Path) -> dict:
    out = {}
    for f in sorted((capture_dir / "Label").glob("captures_*.json")):
        for cap in json.loads(f.read_text(encoding="utf-8"))["captures"]:
            key = (cap["sensor"]["sensor_id"], int(cap["step"]))
            if key in out:
                raise RuntimeError(f"Duplicate record {key} in {capture_dir}")
            out[key] = cap
    return out


def collect(capture_dir: Path, stride: int, min_pixels: int, max_pixels: int, rng) -> dict:
    records = load_records(capture_dir)
    label_s, box_s = sensor_roles(records)
    steps = sorted(s for (sid, s) in records if sid == label_s)[::stride]
    samples = {"u": [], "v": [], "raw": [], "inst": []}
    objects = []  # per object observation: box + 2D box + stats
    skipped = Counter()
    for step in steps:
        cl, cb = records.get((label_s, step)), records.get((box_s, step))
        if cb is None:
            skipped["no_3d_record"] += 1
            continue
        if any(cl[k] != cb[k] for k in POSE_FIELDS) or cl["sensor"]["translation"] != cb["sensor"]["translation"] \
                or cl["sensor"]["rotation"] != cb["sensor"]["rotation"]:
            skipped["pose_or_time_mismatch"] += 1
            continue
        ann = {a["id"]: a for a in cl["annotations"]}
        inst = np.array(Image.open(capture_dir / "Label" / "Instance" /
                                   Path(ann["instance segmentation"]["filename"]).name).convert("RGBA"))
        depth_name = Path(cl["filename"]).name.replace("rgb_", "depth_")
        raw = tdd.load_raw_depth(capture_dir / "Depth" / depth_name)
        if raw.shape != inst.shape[:2]:
            raise RuntimeError(f"{capture_dir} step {step}: depth {raw.shape} vs instance {inst.shape[:2]}")
        packed = inst[..., 0].astype(np.int64) << 16 | inst[..., 1].astype(np.int64) << 8 | inst[..., 2]
        colours = {v["instance_id"]: (v["color"]["r"] << 16 | v["color"]["g"] << 8 | v["color"]["b"])
                   for v in ann["instance segmentation"]["values"]}
        boxes2d = {v["instance_id"]: v for v in ann["bounding box"]["values"]}
        for a in cb["annotations"]:
            if a["id"] != "bounding box 3D":
                continue
            for b in a["values"]:
                iid = b["instance_id"]
                if iid not in colours:
                    skipped["no_instance_colour"] += 1
                    continue
                ys, xs = np.nonzero(packed == colours[iid])
                if len(ys) < min_pixels:
                    skipped["too_few_pixels"] += 1
                    continue
                r = raw[ys, xs]
                keep = r < tdd.RAW_MAX
                if keep.mean() < 0.99:
                    skipped["saturated_depth"] += 1
                    continue
                ys, xs, r = ys[keep], xs[keep], r[keep]
                if len(ys) > max_pixels:
                    idx = rng.choice(len(ys), max_pixels, replace=False)
                    ys, xs, r = ys[idx], xs[idx], r[idx]
                n = len(objects)
                samples["u"].append(xs)
                samples["v"].append(ys)
                samples["raw"].append(r)
                samples["inst"].append(np.full(len(xs), n))
                objects.append({
                    "step": step, "instance_id": iid, "label": b["label_name"], "pixels": int(keep.sum()),
                    "t": np.array([b["translation"][k] for k in "xyz"]),
                    "half": np.array([b["size"][k] for k in "xyz"]) / 2,
                    "R": quat_matrix(b["rotation"]),
                    "box2d": boxes2d.get(iid),
                    "truncated_2d": bool(xs.min() == 0 or ys.min() == 0 or xs.max() == raw.shape[1] - 1
                                         or ys.max() == raw.shape[0] - 1),
                })
    if not objects:
        raise RuntimeError(f"No usable objects in {capture_dir}")
    h, w = raw.shape
    data = {k: np.concatenate(v) for k, v in samples.items()}
    data.update({"objects": objects, "size_wh": (w, h), "label_sensor": label_s, "box_sensor": box_s,
                 "steps_used": len(steps), "skipped": dict(skipped),
                 "recorded_intrinsic": records[(label_s, steps[0])]["sensor"]["camera_intrinsic"]})
    return data


# ---------------------------------------------------------------- scoring

def inside_fractions(data: dict, far_m: float, k: dict, ray: bool, margin: float) -> tuple[np.ndarray, np.ndarray]:
    """Per object: share of back-projected pixels inside its 3D box (+margin), and median outside distance."""
    d = data["raw"].astype(np.float64) * (far_m / tdd.RAW_MAX)
    if ray:  # interpret the value as distance along the pixel ray, convert to planar Z
        xn = (data["u"] + 0.5 - k["cx"]) / k["fx"]
        yn = (data["v"] + 0.5 - k["cy"]) / k["fy"]
        d = d / np.sqrt(1 + xn ** 2 + yn ** 2)
    pts = tdd.backproject(data["u"], data["v"], d, k)
    inst = data["inst"]
    t = np.array([o["t"] for o in data["objects"]])[inst]
    R = np.array([o["R"] for o in data["objects"]])[inst]
    half = np.array([o["half"] for o in data["objects"]])[inst]
    local = np.einsum("nji,nj->ni", R, pts - t)  # R^T (p - t)
    excess = np.clip(np.abs(local) - half, 0, None)
    outside_dist = np.linalg.norm(excess, axis=1)
    inside = outside_dist <= margin
    n = len(data["objects"])
    frac = np.bincount(inst, weights=inside, minlength=n) / np.bincount(inst, minlength=n)
    return frac, outside_dist


def group_median(values: np.ndarray, groups: np.ndarray, n: int) -> np.ndarray:
    order = np.lexsort((values, groups))
    counts = np.bincount(groups, minlength=n)
    starts = np.concatenate([[0], np.cumsum(counts)[:-1]])
    return values[order][starts + (counts - 1) // 2]


def score(data: dict, far_m: float, vfov: float | None, ray: bool, margin: float, k_override: dict | None = None,
          details: bool = True):
    w, h = data["size_wh"]
    k = k_override or tdd.pixel_intrinsics(w, h, vfov)
    frac, outside_dist = inside_fractions(data, far_m, k, ray, margin)
    if not details:
        return {"mean_inside_fraction": float(frac.mean())}, frac
    med_out = group_median(outside_dist, data["inst"], len(frac))
    return {"mean_inside_fraction": float(frac.mean()), "median_inside_fraction": float(np.median(frac)),
            "objects_with_90pct_inside": float((frac >= 0.9).mean()),
            "median_outside_distance_m": float(np.median(med_out)),
            "p90_outside_distance_m": float(np.percentile(med_out, 90))}, frac


def projection_ious(data: dict, k: dict) -> dict:
    """Project 3D box corners with intrinsics k; IoU with the 2D box. Untruncated, unclipped boxes only."""
    w, h = data["size_wh"]
    ious = []
    for o in data["objects"]:
        b = o["box2d"]
        if b is None or o["truncated_2d"]:
            continue
        c = o["t"] + (SIGNS * o["half"]) @ o["R"].T
        if (c[:, 2] <= 0.1).any():
            continue
        u = k["fx"] * c[:, 0] / c[:, 2] + k["cx"]
        v = k["cy"] - k["fy"] * c[:, 1] / c[:, 2]
        if u.min() < 0 or v.min() < 0 or u.max() > w or v.max() > h:
            continue
        ious.append(box_iou((u.min(), v.min(), u.max(), v.max()),
                            (b["x"], b["y"], b["x"] + b["width"], b["y"] + b["height"])))
    return {"boxes": len(ious), "median_iou": float(np.median(ious)) if ious else None,
            "share_iou_above_0.5": float(np.mean(np.array(ious) > 0.5)) if ious else None}


def fit(data: dict, margin: float) -> dict:
    """Alternating 1-D searches for far_m and vertical FOV (planar depth), maximising mean inside fraction."""
    far, vfov = 10.0, 60.0
    obj = lambda f, a: score(data, f, a, False, margin, details=False)[0]["mean_inside_fraction"]
    for _ in range(2):
        for lo, hi, stepv in ((3.0, 30.0, 0.1), (None, None, 0.002)):
            grid = np.arange(lo, hi, stepv) if lo else np.arange(far - 0.2, far + 0.2, stepv)
            far = float(max(grid, key=lambda f: obj(f, vfov)))
        for lo, hi, stepv in ((30.0, 90.0, 0.25), (None, None, 0.01)):
            grid = np.arange(lo, hi, stepv) if lo else np.arange(vfov - 0.5, vfov + 0.5, stepv)
            vfov = float(max(grid, key=lambda a: obj(far, a)))
    return {"far_m": far, "vertical_fov_deg": vfov}


# ---------------------------------------------------------------- report

def evaluate_capture(data: dict, models: dict, margin: float) -> dict:
    w, h = data["size_wh"]
    rec = data["recorded_intrinsic"]
    k_rec = {"fx": rec[0][0], "fy": rec[1][1], "cx": rec[0][2], "cy": rec[1][2]}
    out = {"label_sensor": data["label_sensor"], "box_sensor": data["box_sensor"],
           "steps_used": data["steps_used"], "objects": len(data["objects"]),
           "pixels_tested": int(len(data["raw"])), "objects_per_label": dict(Counter(o["label"] for o in data["objects"])),
           "skipped": data["skipped"], "models": {}}
    for name, m in models.items():
        k = k_rec if m.get("recorded_intrinsics") else None
        s, frac = score(data, m["far_m"], m.get("vertical_fov_deg"), m.get("ray", False), margin, k)
        out["models"][name] = s
        if name in ("selected", "fitted"):
            # Pixel share inside the box for increasing tolerances, per object class: how far
            # back-projected points sit outside the boxes (a direct error indication).
            per_label = {}
            for lbl in sorted({o["label"] for o in data["objects"]}):
                idx = np.array([i for i, o in enumerate(data["objects"]) if o["label"] == lbl])
                sweep = {}
                for mg in MARGIN_SWEEP:
                    _, f = score(data, m["far_m"], m.get("vertical_fov_deg"), False, mg, details=False)
                    sweep[f"{mg * 100:g}cm"] = round(float(f[idx].mean()), 4)
                per_label[lbl] = {"objects": int(len(idx)), "mean_inside_fraction_by_tolerance": sweep}
            out[f"{name}_per_label"] = per_label
    out["projection_vs_2d_boxes"] = {
        "selected_intrinsics": projection_ious(data, tdd.pixel_intrinsics(w, h, models["selected"]["vertical_fov_deg"])),
        "recorded_intrinsics": projection_ious(data, k_rec),
    }
    return out


def save_plot(data: dict, far_m: float, path: Path) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    med = np.array([np.median(data["raw"][data["inst"] == i]) for i in range(len(data["objects"]))]) * far_m / tdd.RAW_MAX
    zc = np.array([o["t"][2] for o in data["objects"]])
    zr = np.array([[np.min((o["t"] + (SIGNS * o["half"]) @ o["R"].T)[:, 2]),
                    np.max((o["t"] + (SIGNS * o["half"]) @ o["R"].T)[:, 2])] for o in data["objects"]])
    fig, ax = plt.subplots(figsize=(7, 6))
    ax.errorbar(zc, med, xerr=[zc - zr[:, 0], zr[:, 1] - zc], fmt="o", ms=2, alpha=0.4, elinewidth=0.5)
    lim = [0, max(zr.max(), med.max()) * 1.05]
    ax.plot(lim, lim, "k--", lw=1)
    ax.set_xlabel("3D box centre Z (m); bars = box near..far Z")
    ax.set_ylabel(f"Median decoded depth on instance mask (m), far = {far_m:.3f}")
    ax.set_title("Decoded depth vs dataset 3D boxes (fit capture)")
    fig.tight_layout()
    fig.savefig(path, dpi=120)
    plt.close(fig)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--config", type=Path, default=Path(__file__).parent / "configs" / "office.json",
                        help="Used for dataset_root and output_root")
    parser.add_argument("--dataset-root")
    parser.add_argument("--fit-capture", default="Synthetic_Scenes/Office/dynamic/Capture_1")
    # Gym/dynamic/Capture_1 was a test capture in the recorded Stage 3 run; it is now excluded from every
    # evaluation split (data_splits.json), so it is no longer a default and the guard refuses it.
    parser.add_argument("--test-captures", nargs="*", default=[
        "Synthetic_Scenes/Office/dynamic/Capture_2", "Synthetic_Scenes/Office/static/Capture_1",
        "Synthetic_Scenes/Gym/static/Capture_1"])
    parser.add_argument("--final-evaluation", action="store_true",
                        help="required for a final-evaluation capture (one run, frozen config)")
    parser.add_argument("--stride", type=int, default=10, help="Use every Nth step")
    parser.add_argument("--margin", type=float, default=0.03, help="Allowed distance outside a 3D box (m)")
    parser.add_argument("--min-pixels", type=int, default=200)
    parser.add_argument("--max-pixels", type=int, default=400, help="Random pixels sampled per object")
    args = parser.parse_args()

    cfg = td.load_config(args.config, args.dataset_root)
    rp.set_active_roots(rp.roots_from_config(cfg))
    root = Path(cfg["dataset_root"])
    rng = np.random.default_rng(0)
    out_dir = Path(cfg["output_root"]) / f"depth_check_{datetime.now():%Y%m%d_%H%M%S}"
    out_dir.mkdir(parents=True, exist_ok=False)

    for cap in [args.fit_capture, *args.test_captures]:
        ds.guard(cap, args.final_evaluation)
    print(f"Collecting fit capture {args.fit_capture} ...")
    fit_data = collect(root / args.fit_capture, args.stride, args.min_pixels, args.max_pixels, rng)
    fitted = fit(fit_data, args.margin)
    print(f"Fitted on {args.fit_capture}: far_m = {fitted['far_m']:.3f}, vertical FOV = {fitted['vertical_fov_deg']:.2f} deg")

    nominal = {"far_m": 10.0, "vertical_fov_deg": 60.0}
    models = {
        "selected": nominal,
        "fitted": fitted,
        "ray_distance_far10_fov60": {**nominal, "ray": True},
        "millimetres_fov60": {"far_m": tdd.RAW_MAX / 1000.0, "vertical_fov_deg": 60.0},
        "far10_recorded_intrinsics": {"far_m": 10.0, "recorded_intrinsics": True},
    }
    report = {
        "created": datetime.now().isoformat(timespec="seconds"),
        "dataset_root": str(root),
        "settings": {"stride": args.stride, "margin_m": args.margin, "min_pixels": args.min_pixels,
                     "max_pixels_per_object": args.max_pixels,
                     "pixel_centre_convention": "index + 0.5", "camera_axes": "x right, y up, z forward"},
        "fit_capture": args.fit_capture,
        "fitted_parameters": fitted,
        "candidate_models": models,
        "captures": {},
    }
    report["captures"][args.fit_capture] = {"role": "fit", **evaluate_capture(fit_data, models, args.margin)}
    save_plot(fit_data, nominal["far_m"], out_dir / "depth_vs_3d_boxes.png")
    for cap in args.test_captures:
        print(f"Collecting test capture {cap} ...")
        data = collect(root / cap, args.stride, args.min_pixels, args.max_pixels, rng)
        report["captures"][cap] = {"role": "test", **evaluate_capture(data, models, args.margin)}

    path = out_dir / "depth_validation_report.json"
    path.write_text(rp.dumps(report, indent=2), encoding="utf-8")
    print()
    print(f"{'capture':<44}{'role':<6}{'objects':>8}  " + "  ".join(f"{m[:22]:>22}" for m in models))
    for cap, r in report["captures"].items():
        cells = "  ".join(f"{r['models'][m]['mean_inside_fraction']:>22.3f}" for m in models)
        print(f"{cap:<44}{r['role']:<6}{r['objects']:>8}  {cells}")
    print("(values = mean share of object pixels that back-project inside the object's 3D box)")
    for cap, r in report["captures"].items():
        p = r["projection_vs_2d_boxes"]
        print(f"{cap}: 3D->2D box median IoU selected {p['selected_intrinsics']['median_iou']} "
              f"({p['selected_intrinsics']['boxes']} boxes), recorded {p['recorded_intrinsics']['median_iou']}")
    print(f"Report: {path}")


if __name__ == "__main__":
    main()
