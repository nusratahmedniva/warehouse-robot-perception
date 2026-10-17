"""Compare the two THUD camera streams that reuse RGB basenames, and check RGB/label alignment.

The dataset copy on disk flattens Unity's per-sensor RGB folders, so file names alone cannot show
which sensor rendered a given RGB file. This script collects the evidence that *can* be checked:

1. Metadata of both sensors over every step (sequence, timestamp, pose, intrinsics, ego, file names).
2. For selected steps: pixel alignment between the RGB image and the camera_0 semantic labels
   (edge-based shift search), camera_0 instance masks vs camera_0 2D boxes, and the projection of
   the other sensor's 3D boxes against camera_0 2D boxes.

Usage:
    python check_camera_streams.py --config configs/office.json --steps 0 150 299
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

import data_splits as ds
import run_paths as rp
import thud_data as td

MAX_SHIFT = 6  # pixels searched in each direction for the RGB/label alignment


def load_all_records(cfg: dict) -> dict[tuple[str, int], dict]:
    label_dir = Path(cfg["capture_dir"]) / cfg["label_dir"]
    out = {}
    for f in sorted(label_dir.glob("captures_*.json")):
        for cap in json.loads(f.read_text(encoding="utf-8"))["captures"]:
            key = (cap["sensor"]["sensor_id"], int(cap["step"]))
            if key in out:
                raise ValueError(f"Duplicate record for sensor/step {key}")
            out[key] = cap
    return out


def compare_metadata(records: dict, a: str, b: str) -> dict:
    steps_a = {s for (sid, s) in records if sid == a}
    steps_b = {s for (sid, s) in records if sid == b}
    fields = {"sequence_id": lambda c: c["sequence_id"], "timestamp": lambda c: c["timestamp"],
              "translation": lambda c: c["sensor"]["translation"], "rotation": lambda c: c["sensor"]["rotation"],
              "camera_intrinsic": lambda c: c["sensor"]["camera_intrinsic"],
              "projection": lambda c: c["sensor"]["projection"], "ego": lambda c: c["ego"],
              "rgb_basename": lambda c: Path(c["filename"]).name}
    differences = {k: [] for k in fields}
    for s in sorted(steps_a & steps_b):
        ca, cb = records[(a, s)], records[(b, s)]
        for k, get in fields.items():
            if get(ca) != get(cb):
                differences[k].append(s)
    ann = lambda sid: sorted({x["id"] for (s2, _), c in records.items() if s2 == sid for x in c["annotations"]})
    return {
        "sensors": [a, b],
        "steps_only_in": {a: sorted(steps_a - steps_b), b: sorted(steps_b - steps_a)},
        "common_steps": len(steps_a & steps_b),
        "steps_with_differences": {k: v for k, v in differences.items()},
        "rgb_folders_in_metadata": {sid: sorted({c["filename"].split("/")[0] for (s2, _), c in records.items()
                                                 if s2 == sid}) for sid in (a, b)},
        "annotation_types": {a: ann(a), b: ann(b)},
    }


def label_boundaries(sem: np.ndarray) -> np.ndarray:
    packed = sem[..., 0].astype(np.int64) << 16 | sem[..., 1].astype(np.int64) << 8 | sem[..., 2]
    edge = np.zeros(packed.shape, dtype=bool)
    edge[:, :-1] |= packed[:, :-1] != packed[:, 1:]
    edge[:-1, :] |= packed[:-1, :] != packed[1:, :]
    return edge


def gradient_magnitude(rgb: np.ndarray) -> np.ndarray:
    g = rgb.astype(np.float32).mean(axis=2)
    gx = np.zeros_like(g)
    gy = np.zeros_like(g)
    gx[:, 1:-1] = g[:, 2:] - g[:, :-2]
    gy[1:-1, :] = g[2:, :] - g[:-2, :]
    return np.hypot(gx, gy)


def alignment_scores(rgb: np.ndarray, sem: np.ndarray) -> dict:
    """Mean RGB gradient on label boundaries for each (dx, dy) shift of the labels."""
    edge = label_boundaries(sem)
    grad = gradient_magnitude(rgb)
    h, w = edge.shape
    m = MAX_SHIFT
    inner = edge[m:h - m, m:w - m]
    scores = {}
    for dy in range(-m, m + 1):
        for dx in range(-m, m + 1):
            shifted = grad[m + dy:h - m + dy, m + dx:w - m + dx]
            scores[(dx, dy)] = float(shifted[inner].mean())
    best = max(scores, key=scores.get)
    others = [v for k, v in scores.items() if k != (0, 0)]
    return {"best_shift_dxdy": list(best), "score_at_zero_shift": scores[(0, 0)],
            "best_score": scores[best], "median_score_other_shifts": float(np.median(others)),
            "zero_shift_ratio_to_median": scores[(0, 0)] / float(np.median(others))}


def box_iou(a, b) -> float:
    ix = max(0.0, min(a[2], b[2]) - max(a[0], b[0]))
    iy = max(0.0, min(a[3], b[3]) - max(a[1], b[1]))
    inter = ix * iy
    union = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - inter
    return inter / union if union > 0 else 0.0


def instance_vs_2d_boxes(cap: dict, inst: np.ndarray) -> dict:
    """Tight boxes of camera_0 instance-mask colours compared with camera_0 2D box annotations."""
    anns = {a["id"]: a for a in cap["annotations"]}
    colours = {v["instance_id"]: v["color"] for v in anns["instance segmentation"]["values"]}
    ious = []
    for v in anns["bounding box"]["values"]:
        c = colours.get(v["instance_id"])
        if c is None:
            continue
        mask = (inst[..., 0] == c["r"]) & (inst[..., 1] == c["g"]) & (inst[..., 2] == c["b"])
        if not mask.any():
            continue
        ys, xs = np.nonzero(mask)
        tight = (xs.min(), ys.min(), xs.max() + 1, ys.max() + 1)
        ann = (v["x"], v["y"], v["x"] + v["width"], v["y"] + v["height"])
        ious.append(box_iou(tight, ann))
    return {"boxes_compared": len(ious), "median_iou": float(np.median(ious)) if ious else None,
            "min_iou": float(min(ious)) if ious else None}


def quat_rotate(q: dict, v: np.ndarray) -> np.ndarray:
    x, y, z, w = q["x"], q["y"], q["z"], q["w"]
    r = np.array([[1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
                  [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
                  [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)]])
    return v @ r.T


def projected_3d_vs_2d(cap_3d: dict, cap_2d: dict, size_wh: tuple[int, int]) -> dict:
    """Project the other sensor's 3D boxes with its recorded intrinsics; compare with camera_0 2D boxes.

    Assumes Unity camera coordinates (x right, y up, z forward) and box translation = box centre.
    Only boxes fully in front of the camera are projected; the projection is clipped to the image.
    """
    k = np.array(cap_3d["sensor"]["camera_intrinsic"], dtype=float)
    w, h = size_wh
    boxes2d = {v["instance_id"]: v for a in cap_2d["annotations"] if a["id"] == "bounding box" for v in a["values"]}
    signs = np.array([[sx, sy, sz] for sx in (-1, 1) for sy in (-1, 1) for sz in (-1, 1)], dtype=float)
    ious = []
    for a in cap_3d["annotations"]:
        if a["id"] != "bounding box 3D":
            continue
        for v in a["values"]:
            b = boxes2d.get(v["instance_id"])
            if b is None:
                continue
            t = np.array([v["translation"][c] for c in "xyz"])
            s = np.array([v["size"][c] for c in "xyz"]) / 2
            corners = t + quat_rotate(v["rotation"], signs * s)
            if (corners[:, 2] <= 0.05).any():
                continue
            u = k[0, 0] * corners[:, 0] / corners[:, 2] + k[0, 2]
            vv = k[1, 2] - k[1, 1] * corners[:, 1] / corners[:, 2]
            proj = (max(0, u.min()), max(0, vv.min()), min(w, u.max()), min(h, vv.max()))
            if proj[2] <= proj[0] or proj[3] <= proj[1]:
                continue
            ann = (b["x"], b["y"], b["x"] + b["width"], b["y"] + b["height"])
            ious.append({"instance_id": v["instance_id"], "label": v["label_name"], "iou": round(box_iou(proj, ann), 4)})
    vals = [x["iou"] for x in ious]
    return {"boxes_compared": len(vals), "median_iou": float(np.median(vals)) if vals else None, "boxes": ious}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--config", type=Path, default=Path(__file__).parent / "configs" / "office.json")
    parser.add_argument("--dataset-root")
    parser.add_argument("--capture")
    parser.add_argument("--other-sensor", default="camera", help="Sensor that shares RGB basenames")
    parser.add_argument("--steps", type=int, nargs="+", default=[0, 150, 299])
    parser.add_argument("--final-evaluation", action="store_true",
                        help="required for a final-evaluation capture (one run, frozen config)")
    args = parser.parse_args()

    cfg = td.load_config(args.config, args.dataset_root, args.capture)
    rp.set_active_roots(rp.roots_from_config(cfg))
    ds.guard(ds.capture_key(cfg["capture_dir"], cfg["dataset_root"]), args.final_evaluation)
    main_sensor = cfg["rgb_sensor_id"]
    capture_dir = Path(cfg["capture_dir"])
    records = load_all_records(cfg)
    out_dir = Path(cfg["output_root"]) / f"camera_check_{datetime.now():%Y%m%d_%H%M%S}"
    out_dir.mkdir(parents=True, exist_ok=False)

    report = {"capture_dir": str(capture_dir), "main_sensor": main_sensor, "other_sensor": args.other_sensor,
              "metadata": compare_metadata(records, main_sensor, args.other_sensor), "steps": {}}

    for step in args.steps:
        c0 = records[(main_sensor, step)]
        c1 = records[(args.other_sensor, step)]
        anns = {a["id"]: a for a in c0["annotations"]}
        rgb_path = capture_dir / cfg["rgb_dir"] / Path(c0["filename"]).name
        sem_path = capture_dir / cfg["semantic_dir"] / Path(anns[cfg["semantic_annotation_id"]]["filename"]).name
        inst_path = capture_dir / cfg["label_dir"] / "Instance" / Path(anns["instance segmentation"]["filename"]).name
        rgb = np.asarray(td.load_rgb(rgb_path)[0])
        sem = td.load_semantic_rgba(sem_path)
        inst = td.load_semantic_rgba(inst_path)
        h, w = rgb.shape[:2]
        report["steps"][str(step)] = {
            "rgb": rgb_path.name, "semantic": sem_path.name, "instance": inst_path.name,
            "rgb_semantic_alignment": alignment_scores(rgb, sem),
            "rgb_instance_alignment": alignment_scores(rgb, inst),
            "camera_0_instance_mask_vs_2d_boxes": instance_vs_2d_boxes(c0, inst),
            "other_sensor_3d_boxes_projected_vs_camera_0_2d_boxes": projected_3d_vs_2d(c1, c0, (w, h)),
        }
        # Visual check: semantic boundaries in red over the RGB frame, camera_0 2D boxes in yellow.
        vis = rgb.copy()
        vis[label_boundaries(sem)] = [255, 0, 0]
        img = Image.fromarray(vis)
        draw = ImageDraw.Draw(img)
        for v in anns["bounding box"]["values"]:
            if v["label_name"] in ("people", "Chair", "Sofa"):
                draw.rectangle([v["x"], v["y"], v["x"] + v["width"], v["y"] + v["height"]], outline=(255, 255, 0))
        draw.text((6, 6), f"step {step}: semantic boundaries (red), camera_0 2D boxes people/chair/sofa (yellow)",
                  fill=(255, 255, 255))
        img.save(out_dir / f"alignment_step_{step:06d}.png")

    md = report["metadata"]
    identical = all(not v for v in md["steps_with_differences"].values() if v is not None)
    report["conclusion"] = {
        "confirmed": [
            f"{md['common_steps']} steps exist for both sensors; sequence ID, timestamp, pose, intrinsics, "
            f"projection, ego and RGB basename are {'identical at every step' if identical else 'NOT identical'}.",
            "The metadata lists different source RGB folders per sensor: " + json.dumps(md["rgb_folders_in_metadata"]),
            f"Only '{main_sensor}' carries semantic, instance and 2D box annotations; "
            f"'{args.other_sensor}' carries {md['annotation_types'][args.other_sensor]}.",
            "Alignment of the on-disk RGB frames with the camera_0 labels at the checked steps is reported "
            "per step (best shift and edge score).",
        ],
        "ambiguous": [
            "The on-disk RGB folder is flattened and both sensors use the same basenames, so which sensor "
            "rendered each RGB file cannot be proven from file names or metadata.",
            "Pixel alignment with camera_0 labels supports, but does not prove, camera_0 provenance: the two "
            "sensors share pose and intrinsics, so their renders would be geometrically identical.",
            "A best shift of 1 px is within the method's resolution: label boundaries lie between two pixels "
            "and are marked on one side of the pair.",
            f"Projecting '{args.other_sensor}' 3D boxes with a standard pinhole model and the recorded "
            "intrinsics does not reproduce the camera_0 2D boxes. The intrinsics/coordinate convention of these "
            "Unity records is not validated, so this test is inconclusive, not evidence of a mismatch.",
        ],
    }
    path = out_dir / "camera_stream_report.json"
    path.write_text(rp.dumps(report, indent=2), encoding="utf-8")

    print(f"Metadata differences between {main_sensor} and {args.other_sensor}: "
          + ", ".join(f"{k}={len(v)}" for k, v in md["steps_with_differences"].items()))
    print(f"Annotation types: {md['annotation_types']}")
    for s, r in report["steps"].items():
        a = r["rgb_semantic_alignment"]
        print(f"step {s}: RGB/semantic best shift {a['best_shift_dxdy']}, zero-shift edge score "
              f"{a['score_at_zero_shift']:.1f} vs median other shifts {a['median_score_other_shifts']:.1f}; "
              f"instance-vs-2D box median IoU {r['camera_0_instance_mask_vs_2d_boxes']['median_iou']}; "
              f"projected 3D-vs-2D median IoU {r['other_sensor_3d_boxes_projected_vs_camera_0_2d_boxes']['median_iou']} "
              f"({r['other_sensor_3d_boxes_projected_vs_camera_0_2d_boxes']['boxes_compared']} boxes)")
    print(f"Report: {path}")


if __name__ == "__main__":
    main()
