"""Step 4: fuse verified depth, camera calibration, predicted segmentation and tracking into per-object 3D positions.

Prediction inputs (unchanged, re-used from earlier runs):
- tracking run: tracks.csv + frames.jsonl (YOLO11n + ByteTrack boxes, track IDs, steps, timestamps)
- segmentation run referenced by the tracking run (SegFormer grouped masks)
Geometry inputs:
- depth: THUD synthetic reference depth, decoded with configs/depth_thud_synthetic.json
  -> results are a REFERENCE-DEPTH FUSION BASELINE, not an RGB-only depth result
- intrinsics: 60 deg vertical FOV pinhole (the recorded camera_intrinsic is not in pixel units)
- camera pose: sensor translation + rotation of each capture, world = R(q_xyzw) p_cam + t

Reference annotations (instance masks, 2D/3D boxes) are used only in the geometry checks and in the
evaluation stage; they never feed the estimated positions.

Estimated quantity per tracked box: the per-axis median of the back-projected visible-surface points
of the selected pixels (a point on the visible object surface, NOT a 3D box centre).

Usage (from robot_vision/):
    python fuse_objects.py --check-only     # geometry checks + 3 frames
    python fuse_objects.py                  # checks, then the whole tracking run
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import sys
import traceback
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

import matplotlib
import numpy as np
from PIL import Image, ImageDraw
from scipy.optimize import linear_sum_assignment

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

import data_splits as ds  # noqa: E402
import run_paths as rp  # noqa: E402
import thud_data as td  # noqa: E402
import thud_depth as tdd  # noqa: E402
from check_camera_streams import box_iou, gradient_magnitude  # noqa: E402
from track_objects import box_region, track_colour  # noqa: E402
from validate_depth import load_records, quat_matrix, sensor_roles  # noqa: E402

HERE = Path(__file__).resolve().parent
STATE_FIELDS = [
    "sequence_id", "sensor_id", "step", "timestamp", "track_id", "class_name", "confidence",
    "x1", "y1", "x2", "y2", "box_touches_edge", "selection_method", "region_pixels", "selected_pixels",
    "valid_depth_pixels", "valid_depth_fraction", "depth_median_m", "depth_iqr_m",
    "cam_x", "cam_y", "cam_z", "range_m", "world_x", "world_y", "world_z",
    "floor_strip_fraction", "floor_context", "bottom_height_above_floor_m", "position_valid", "invalid_reason",
]


# ---------------------------------------------------------------- helpers

def resolve(p: str | Path) -> Path:
    p = Path(p)
    return p if p.is_absolute() else HERE / p


def write_json(path: Path, data) -> None:
    path.write_text(rp.dumps(data, indent=2, default=lambda o: o.tolist() if hasattr(o, "tolist") else str(o)),
                    encoding="utf-8")


def sensor_pose(meta: dict) -> tuple[np.ndarray, np.ndarray]:
    """Rotation matrix and translation of the camera in the world: world = R @ p_cam + t."""
    x, y, z, w = meta["sensor"]["rotation"]  # stored as [x, y, z, w]
    return quat_matrix({"x": x, "y": y, "z": z, "w": w}), np.array(meta["sensor"]["translation"], dtype=float)


def depth_path(capture_dir: Path, meta: dict) -> Path:
    return capture_dir / "Depth" / Path(meta["filename"]).name.replace("rgb_", "depth_")


def stats(values) -> dict:
    a = np.asarray([v for v in values if v is not None and np.isfinite(v)], dtype=float)
    if a.size == 0:
        return {"n": 0}
    return {"n": int(a.size), "median": float(np.median(a)), "mean": float(a.mean()),
            "p90": float(np.percentile(a, 90)), "max": float(a.max())}


def ref_boxes_2d(meta: dict) -> list[dict]:
    out = []
    for a in meta["annotations"]:
        if a["id"] == "bounding box":
            for b in a["values"]:
                out.append({"instance_id": b["instance_id"], "label": b["label_name"],
                            "box": (b["x"], b["y"], b["x"] + b["width"], b["y"] + b["height"])})
    return out


def ref_boxes_3d(meta: dict) -> dict[int, dict]:
    out = {}
    for a in meta["annotations"]:
        if a["id"] == "bounding box 3D":
            for b in a["values"]:
                out[b["instance_id"]] = {"label": b["label_name"],
                                         "t": np.array([b["translation"][k] for k in "xyz"]),
                                         "half": np.array([b["size"][k] for k in "xyz"]) / 2,
                                         "R": quat_matrix(b["rotation"])}
    return out


def instance_masks(capture_dir: Path, meta: dict) -> tuple[np.ndarray, dict[int, int]]:
    ann = {a["id"]: a for a in meta["annotations"]}
    inst = np.array(Image.open(capture_dir / "Label" / "Instance" /
                               Path(ann["instance segmentation"]["filename"]).name).convert("RGBA"))
    packed = inst[..., 0].astype(np.int64) << 16 | inst[..., 1].astype(np.int64) << 8 | inst[..., 2]
    colours = {v["instance_id"]: v["color"]["r"] << 16 | v["color"]["g"] << 8 | v["color"]["b"]
               for v in ann["instance segmentation"]["values"]}
    return packed, colours


def box_distance(p: np.ndarray, box: dict) -> float:
    """Distance from a point to an oriented 3D box (0 inside)."""
    local = (p - box["t"]) @ box["R"]
    return float(np.linalg.norm(np.maximum(np.abs(local) - box["half"], 0.0)))


# ---------------------------------------------------------------- geometry checks

def depth_edge_alignment(rgb: np.ndarray, depth: np.ndarray, max_shift: int = 3) -> dict:
    """Mean RGB gradient on depth discontinuities, for each shift of the depth edges."""
    d = np.where(np.isfinite(depth), depth, np.nanmax(depth))
    gy, gx = np.gradient(np.log(np.maximum(d, 1e-3)))
    edge = np.hypot(gx, gy) > 0.15
    grad = gradient_magnitude(rgb)
    h, w = edge.shape
    m = max_shift
    inner = edge[m:h - m, m:w - m]
    scores = {(dx, dy): float(grad[m + dy:h - m + dy, m + dx:w - m + dx][inner].mean())
              for dy in range(-m, m + 1) for dx in range(-m, m + 1)}
    best = max(scores, key=scores.get)
    return {"edge_pixels": int(inner.sum()), "best_shift_dxdy": list(best),
            "zero_shift_score": scores[(0, 0)], "median_other_shift_score": float(np.median(
                [v for k, v in scores.items() if k != (0, 0)]))}


def geometry_checks(ctx: dict, steps: list[int]) -> dict:
    capture_dir, records, frames = ctx["capture_dir"], ctx["records"], ctx["frames_by_step"]
    label_s, box_s, k, far = ctx["label_sensor"], ctx["box_sensor"], ctx["K"], ctx["far_m"]
    report = {"capture_dir": str(capture_dir), "label_sensor": label_s, "box_sensor": box_s,
              "tracked_sensor": ctx["tracked_sensor"], "intrinsics_used": k,
              "recorded_camera_intrinsic_not_used": records[(label_s, steps[0])]["sensor"]["camera_intrinsic"],
              "frames": [], "failures": []}
    fail = report["failures"]
    if ctx["tracked_sensor"] != label_s:
        fail.append(f"tracked sensor {ctx['tracked_sensor']} is not the labelled RGB sensor {label_s}")
    static_world = defaultdict(lambda: defaultdict(list))
    for step in steps:
        f, meta, mb = frames[step], records.get((label_s, step)), records.get((box_s, step))
        fr = {"step": step}
        if meta is None or mb is None:
            fail.append(f"step {step}: missing metadata record")
            continue
        for key, a, b in (("timestamp", f["timestamp"], meta["timestamp"]), ("sequence_id", f["sequence_id"],
                          meta["sequence_id"]), ("capture_id", f.get("capture_id"), meta["id"])):
            if a != b:
                fail.append(f"step {step}: {key} tracking={a} metadata={b}")
        fr["rgb_matches_metadata"] = Path(f["rgb_path"]).name == Path(meta["filename"]).name
        if not fr["rgb_matches_metadata"]:
            fail.append(f"step {step}: RGB file {f['rgb_path']} != metadata {meta['filename']}")
        fr["poses_equal_between_sensors"] = (meta["sensor"]["translation"] == mb["sensor"]["translation"]
                                            and meta["sensor"]["rotation"] == mb["sensor"]["rotation"])
        fr["ego_identity"] = (meta["ego"]["translation"] == [0.0, 0.0, 0.0]
                             and meta["ego"]["rotation"] == [0.0, 0.0, 0.0, 1.0])
        for key in ("poses_equal_between_sensors", "ego_identity"):
            if not fr[key]:
                fail.append(f"step {step}: {key} is false")
        dp = depth_path(capture_dir, meta)
        raw = tdd.load_raw_depth(dp)
        rgb = np.array(Image.open(f["rgb_path"]).convert("RGB"))
        seg = np.array(Image.open(f["segmentation_mask"]))
        fr.update({"depth_file": str(dp), "depth_shape": list(raw.shape), "rgb_shape": list(rgb.shape[:2]),
                   "seg_shape": list(seg.shape), "saturated_fraction": float((raw == tdd.RAW_MAX).mean())})
        if not (raw.shape == rgb.shape[:2] == seg.shape == (ctx["height"], ctx["width"])):
            fail.append(f"step {step}: image sizes differ {raw.shape} {rgb.shape[:2]} {seg.shape}")
            continue
        depth, valid = tdd.decode_depth(raw, far)
        fr["rgb_depth_alignment"] = al = depth_edge_alignment(rgb, depth)
        if al["best_shift_dxdy"] != [0, 0]:
            fail.append(f"step {step}: RGB/depth edges best aligned at shift {al['best_shift_dxdy']}")
        # depth encoding re-check on this frame: reference instance points inside reference 3D boxes
        packed, colours = instance_masks(capture_dir, meta)
        boxes = ref_boxes_3d(mb)
        R, t = sensor_pose(meta)
        planar, ray = [], []
        for iid, box in boxes.items():
            if box["label"] in ("Chair", "Desk", "Sofa"):
                static_world[iid]["R_p_plus_t"].append(R @ box["t"] + t)
                static_world[iid]["RT_p_plus_t"].append(R.T @ box["t"] + t)
            if box["label"] == "Sofa" or iid not in colours:  # sofa boxes are known to be partial
                continue
            ys, xs = np.nonzero(packed == colours[iid])
            if len(ys) < 200 or (~valid[ys, xs]).mean() > 0.01:
                continue
            ys, xs = ys[valid[ys, xs]], xs[valid[ys, xs]]
            z = depth[ys, xs]
            pts = tdd.backproject(xs, ys, z, k)
            rn = np.hypot(np.hypot(xs + 0.5 - k["cx"], ys + 0.5 - k["cy"]), k["fx"])
            pts_ray = tdd.backproject(xs, ys, z * k["fx"] / rn, k)  # if the value were distance along the ray
            for store, p in ((planar, pts), (ray, pts_ray)):
                local = (p - box["t"]) @ box["R"]
                store.append(float((np.abs(local) <= box["half"] + 0.02).all(axis=1).mean()))
        fr["depth_check_objects"] = len(planar)
        fr["median_inside_fraction_planar_z"] = float(np.median(planar)) if planar else None
        fr["median_inside_fraction_ray_distance"] = float(np.median(ray)) if ray else None
        if not planar or np.median(planar) < 0.9 or np.median(planar) <= np.median(ray):
            fail.append(f"step {step}: depth encoding not confirmed on this frame "
                        f"(planar {fr['median_inside_fraction_planar_z']}, ray {fr['median_inside_fraction_ray_distance']})")
        report["frames"].append(fr)
    spreads = {}
    for conv in ("R_p_plus_t", "RT_p_plus_t"):
        s = [float(np.linalg.norm(np.std(np.array(v[conv]), axis=0))) for v in static_world.values() if len(v[conv]) >= 2]
        spreads[conv] = stats(s)
    report["static_box_world_spread_m"] = spreads
    ok_conv = spreads["R_p_plus_t"].get("max", 1) < 0.01 and spreads["RT_p_plus_t"].get("median", 0) > 0.1
    if not ok_conv:
        fail.append(f"pose convention world = R(q_xyzw) p + t not confirmed: {spreads}")
    report["pose_convention"] = ("world = R(q) @ p_cam + t, q stored [x, y, z, w]; camera axes x right, y up, "
                                 "z forward (Unity, left-handed); 3D box translations are in the camera frame")
    report["passed"] = not fail
    return report


# ---------------------------------------------------------------- fusion (prediction only)

def select_pixels(row: dict, seg: np.ndarray, cfg: dict, cls_ids: dict) -> tuple[np.ndarray, np.ndarray, str, int]:
    h, w = seg.shape
    region = box_region(float(row["x1"]), float(row["y1"]), float(row["x2"]), float(row["y2"]), w, h)
    if region is None:
        return np.empty(0, int), np.empty(0, int), "empty_box", 0
    c0, r0, c1, r1 = region
    patch = seg[r0:r1, c0:c1]
    sel = cfg["pixel_selection"]
    target = sel["detector_to_seg_class"].get(row["class_name"])
    mask, method = None, None
    if target is not None:
        m = patch == cls_ids[target]
        if m.sum() >= sel["min_selected_pixels"]:
            mask, method = m, f"seg_class_{target}"
    if mask is None:
        m = ~np.isin(patch, [cls_ids[c] for c in sel["background_seg_classes"]])
        if m.sum() >= sel["min_selected_pixels"]:
            mask, method = m, "box_minus_background"
    if mask is None:
        mask, method = np.ones_like(patch, bool), "box_all"
    ys, xs = np.nonzero(mask)
    return ys + r0, xs + c0, method, int(patch.size)


def fuse_frame(frame: dict, rows: list[dict], meta: dict, ctx: dict) -> tuple[list[dict], dict]:
    cfg, k, cls_ids = ctx["cfg"], ctx["K"], ctx["class_ids"]
    seg = np.array(Image.open(frame["segmentation_mask"]))
    depth, valid = tdd.decode_depth(tdd.load_raw_depth(depth_path(ctx["capture_dir"], meta)), ctx["far_m"])
    R, t = sensor_pose(meta)
    h, w = seg.shape
    # floor height in the world from PREDICTED floor pixels with valid depth
    fy, fx = np.nonzero((seg == cls_ids["floor"]) & valid)
    floor = {"floor_pixels": int(len(fy)), "floor_world_y": None, "floor_world_y_iqr": None}
    if len(fy) >= 200:
        n = cfg["floor_context"]["floor_sample_pixels"]
        idx = ctx["rng"].choice(len(fy), min(n, len(fy)), replace=False)
        wy = (tdd.backproject(fx[idx], fy[idx], depth[fy[idx], fx[idx]], k) @ R.T + t)[:, 1]
        floor["floor_world_y"] = float(np.median(wy))
        floor["floor_world_y_iqr"] = float(np.subtract(*np.percentile(wy, [75, 25])))
    out = []
    sel_cfg, fc = cfg["pixel_selection"], cfg["floor_context"]
    for row in rows:
        ys, xs, method, region_px = select_pixels(row, seg, cfg, cls_ids)
        ok = valid[ys, xs] if len(ys) else np.empty(0, bool)
        rec = {k_: row[k_] for k_ in ("sequence_id", "sensor_id", "step", "timestamp", "track_id", "class_name",
                                      "confidence", "x1", "y1", "x2", "y2")}
        x1, y1, x2, y2 = (float(row[c]) for c in ("x1", "y1", "x2", "y2"))
        rec.update({"box_touches_edge": x1 <= 1 or y1 <= 1 or x2 >= w - 1 or y2 >= h - 1,
                    "selection_method": method, "region_pixels": region_px, "selected_pixels": int(len(ys)),
                    "valid_depth_pixels": int(ok.sum()),
                    "valid_depth_fraction": round(float(ok.mean()), 4) if len(ys) else 0.0})
        reason = None
        if method in ("empty_box", "box_all"):
            reason = f"pixel_selection_{method}"
        elif ok.sum() < sel_cfg["min_selected_pixels"]:
            reason = "too_few_valid_depth_pixels"
        elif ok.mean() < sel_cfg["min_valid_depth_fraction"]:
            reason = "mostly_saturated_depth"
        if ok.sum():
            ys, xs = ys[ok], xs[ok]
            z = depth[ys, xs]
            pts = tdd.backproject(xs, ys, z, k)
            p = np.median(pts, axis=0)
            pw = p @ R.T + t
            rec.update({"depth_median_m": float(np.median(z)), "depth_iqr_m": float(np.subtract(*np.percentile(z, [75, 25]))),
                        "cam_x": p[0], "cam_y": p[1], "cam_z": p[2], "range_m": float(np.linalg.norm(p)),
                        "world_x": pw[0], "world_y": pw[1], "world_z": pw[2]})
            if floor["floor_world_y"] is not None:
                low = np.percentile((pts @ R.T + t)[:, 1], 5)
                rec["bottom_height_above_floor_m"] = float(low - floor["floor_world_y"])
        # scene context: predicted floor around the bottom edge of the box
        s = fc["strip_half_height_px"]
        c0, c1 = max(0, math.floor(x1)), min(w, math.ceil(x2))
        r0, r1 = max(0, math.floor(y2) - s), min(h, math.ceil(y2) + s)
        if y2 >= h - 2:
            rec["floor_context"] = "bottom_out_of_frame"
        elif c1 > c0 and r1 > r0:
            frac = float((seg[r0:r1, c0:c1] == cls_ids["floor"]).mean())
            rec["floor_strip_fraction"] = round(frac, 4)
            rec["floor_context"] = "floor_contact_visible" if frac >= fc["min_floor_fraction"] else "floor_contact_not_visible"
        else:
            rec["floor_context"] = "unknown"
        rec["position_valid"] = reason is None
        rec["invalid_reason"] = reason or ""
        out.append(rec)
    return out, {"pose_translation": t.tolist(), "pose_rotation_xyzw": meta["sensor"]["rotation"], **floor}


# ---------------------------------------------------------------- evaluation (reference used here only)

def evaluate(states: list[dict], ctx: dict) -> tuple[dict, list[dict]]:
    ev, k = ctx["cfg"]["evaluation"], ctx["K"]
    by_step = defaultdict(list)
    for s in states:
        by_step[int(s["step"])].append(s)
    rows = []
    unmatched = Counter()
    for step, obs in sorted(by_step.items()):
        meta = ctx["records"][(ctx["label_sensor"], step)]
        refs = ref_boxes_2d(meta)
        boxes3d = ref_boxes_3d(ctx["records"][(ctx["box_sensor"], step)])
        R, t = sensor_pose(meta)
        cost = np.zeros((len(obs), len(refs)))
        for i, o in enumerate(obs):
            allowed = ev["compatible_reference_labels"].get(o["class_name"], [])
            bo = (float(o["x1"]), float(o["y1"]), float(o["x2"]), float(o["y2"]))
            for j, r in enumerate(refs):
                if r["label"] in allowed:
                    iou = box_iou(bo, r["box"])
                    cost[i, j] = iou if iou >= ev["association_min_iou"] else 0
        pairs = {}
        if refs and obs:
            ri, ci = linear_sum_assignment(-cost)
            pairs = {i: (j, cost[i, j]) for i, j in zip(ri, ci) if cost[i, j] > 0}
        packed = colours = depth = valid = None
        for i, o in enumerate(obs):
            row = {"step": step, "track_id": o["track_id"], "class_name": o["class_name"],
                   "position_valid": o["position_valid"], "selection_method": o["selection_method"]}
            if i not in pairs:
                unmatched[o["class_name"]] += 1
                row["associated"] = False
                rows.append(row)
                continue
            r = refs[pairs[i][0]]
            row.update({"associated": True, "ref_instance_id": r["instance_id"], "ref_label": r["label"],
                        "iou": round(float(pairs[i][1]), 4)})
            if o["position_valid"]:
                est = np.array([o["cam_x"], o["cam_y"], o["cam_z"]], dtype=float)
                if packed is None:
                    packed, colours = instance_masks(ctx["capture_dir"], meta)
                    depth, valid = tdd.decode_depth(tdd.load_raw_depth(depth_path(ctx["capture_dir"], meta)),
                                                    ctx["far_m"])
                if r["instance_id"] in colours:
                    ys, xs = np.nonzero((packed == colours[r["instance_id"]]) & valid)
                    if len(ys) >= 20:
                        ref_pt = np.median(tdd.backproject(xs, ys, depth[ys, xs], k), axis=0)
                        d = est - ref_pt
                        row.update({"ref_visible_pixels": int(len(ys)), "err_visible_point_m": float(np.linalg.norm(d)),
                                    "err_x_m": float(d[0]), "err_y_m": float(d[1]), "err_z_m": float(d[2]),
                                    "ref_visible_world": (ref_pt @ R.T + t).tolist()})
                box = boxes3d.get(r["instance_id"])
                if box is not None:
                    row.update({"dist_to_ref_3d_box_m": box_distance(est, box),
                                "inside_ref_3d_box_with_margin": box_distance(est, box) <= ev["box_margin_m"],
                                "dist_to_ref_box_centre_m_info_only": float(np.linalg.norm(est - box["t"])),
                                "est_world": (est @ R.T + t).tolist(), "ref_box_world_centre": (R @ box["t"] + t).tolist()})
            rows.append(row)

    def group(pred):
        sel = [r for r in rows if pred(r)]
        return {"observations": len(sel),
                "visible_point_error_m": stats(r.get("err_visible_point_m") for r in sel),
                "abs_depth_axis_error_m": stats(abs(r["err_z_m"]) if "err_z_m" in r else None for r in sel),
                "dist_to_ref_3d_box_m": stats(r.get("dist_to_ref_3d_box_m") for r in sel),
                "fraction_inside_ref_3d_box_with_margin": (
                    float(np.mean([r["inside_ref_3d_box_with_margin"] for r in sel if "inside_ref_3d_box_with_margin" in r]))
                    if any("inside_ref_3d_box_with_margin" in r for r in sel) else None)}

    assoc = [r for r in rows if r.get("associated") and r["position_valid"]]
    by_class = {c: group(lambda r, c=c: r.get("associated") and r["position_valid"] and r["ref_label"] == c)
                for c in sorted({r["ref_label"] for r in assoc})}
    by_method = {m: group(lambda r, m=m: r.get("associated") and r["position_valid"] and r["selection_method"] == m)
                 for m in sorted({r["selection_method"] for r in assoc})}
    # world-frame stability: tracks matched to static furniture (have reference 3D boxes)
    world, ref_world = defaultdict(list), defaultdict(list)
    for r in assoc:
        if "est_world" in r and "ref_visible_world" in r:
            world[(r["track_id"], r["ref_instance_id"])].append(r["est_world"])
            ref_world[(r["track_id"], r["ref_instance_id"])].append(r["ref_visible_world"])
    spread = lambda v: float(np.linalg.norm(np.std(np.array(v), axis=0)))  # noqa: E731
    keys = [key for key, v in world.items() if len(v) >= 10]
    stability = [spread(world[key]) for key in keys]
    ref_stability = [spread(ref_world[key]) for key in keys]
    report = {
        "depth_source": ctx["cfg"]["depth_source"], "note": ctx["cfg"]["depth_source_note"],
        "estimated_quantity": "per-axis median of back-projected visible-surface points of the selected pixels "
                              "(camera frame, metres). It is not a 3D box centre; it sits on the visible surface.",
        "association": f"per frame, Hungarian matching of tracked boxes to reference camera_0 2D boxes with a "
                       f"class-compatible label and IoU >= {ev['association_min_iou']} (table in config). "
                       f"Reference data is used only here.",
        "metrics": {
            "visible_point_error": "distance to the per-axis median of reference-instance-mask pixels back-projected "
                                   "with the SAME reference depth: isolates pixel-selection error (predicted mask + box "
                                   "vs true instance mask). Available for all associated classes including people.",
            "dist_to_ref_3d_box": "distance from the estimated point to the reference 3D box (0 inside). Only Chair, "
                                  "Desk and Sofa have 3D boxes in this capture; people have none. Sofa boxes are known "
                                  "to cover only part of the sectional sofa.",
            "static_track_world_spread": "std of world positions of one track matched to static furniture "
                                         "(>=10 frames): tests pose transform + pixel-selection jitter together.",
        },
        "counts": {"observations": len(rows), "associated": sum(1 for r in rows if r.get("associated")),
                   "associated_with_valid_position": len(assoc), "unassociated_by_detector_class": dict(unmatched)},
        "overall": group(lambda r: r.get("associated") and r["position_valid"]),
        "by_reference_label": by_class,
        "by_selection_method": by_method,
        "static_track_world_spread_m": stats(stability),
        "static_track_world_spread_of_reference_visible_point_m": stats(ref_stability),
        "static_track_spread_note": "A visible-surface point moves on a static object as the camera walks around it, "
                                    "so the reference visible point's spread (same tracks, same frames) is the baseline.",
    }
    return report, rows


# ---------------------------------------------------------------- drawing

def draw_overlay(frame: dict, states: list[dict], path: Path) -> None:
    img = Image.open(frame["rgb_path"]).convert("RGB")
    d = ImageDraw.Draw(img)
    for s in states:
        col = track_colour(int(s["track_id"]))
        box = [float(s[c]) for c in ("x1", "y1", "x2", "y2")]
        d.rectangle(box, outline=col, width=2)
        if s["position_valid"]:
            txt = f"#{s['track_id']} {s['class_name']} Z={float(s['cam_z']):.2f}m {s['floor_context']}"
        else:
            txt = f"#{s['track_id']} {s['class_name']} no 3D: {s['invalid_reason']}"
        tw = d.textlength(txt)
        y = max(0, box[1] - 12)
        d.rectangle([box[0], y, box[0] + tw + 4, y + 12], fill=(0, 0, 0))
        d.text((box[0] + 2, y), txt, fill=col)
    d.rectangle([0, 0, 470, 14], fill=(0, 0, 0))
    d.text((3, 1), f"step {frame['step']}  reference-depth fusion baseline (THUD reference depth)", fill=(255, 255, 0))
    img.save(path)


def draw_topdown(states: list[dict], frame_info: list[dict], eval_rows: list[dict] | None, path: Path) -> None:
    fig, ax = plt.subplots(figsize=(8, 7))
    cam = np.array([f["pose_translation"] for f in frame_info])
    ax.plot(cam[:, 0], cam[:, 2], "k-", lw=2, label="camera path (reference pose)")
    classes = sorted({s["class_name"] for s in states if s["position_valid"]})
    cmap = plt.get_cmap("tab10")
    for i, c in enumerate(classes):
        p = np.array([[s["world_x"], s["world_z"]] for s in states if s["position_valid"] and s["class_name"] == c],
                     dtype=float)
        ax.scatter(p[:, 0], p[:, 1], s=4, color=cmap(i % 10), label=f"{c} (estimated)")
    if eval_rows:
        seen = {}
        for r in eval_rows:
            if "ref_box_world_centre" in r:
                seen[r["ref_instance_id"]] = r["ref_box_world_centre"]
        if seen:
            c = np.array(list(seen.values()))
            ax.scatter(c[:, 0], c[:, 2], marker="x", s=60, color="k", label="reference 3D box centres (eval)")
    ax.set_xlabel("world x (m)")
    ax.set_ylabel("world z (m)")
    ax.set_aspect("equal")
    ax.set_title("Top-down: tracked-object visible-surface points (reference-depth baseline)")
    ax.legend(fontsize=7, loc="best")
    fig.tight_layout()
    fig.savefig(path, dpi=130)
    plt.close(fig)


# ---------------------------------------------------------------- main

def run(args: argparse.Namespace) -> Path:
    cfg = json.loads(resolve(args.config).read_text(encoding="utf-8"))
    office = td.load_config(resolve(cfg["office_config"]), capture=args.capture)
    rp.set_active_roots(rp.roots_from_config(office))
    split = ds.guard(ds.capture_key(office["capture_dir"], office["dataset_root"]), args.final_evaluation)
    depth_cfg = tdd.load_depth_config(resolve(cfg["depth_config"]))
    track_dir = resolve(args.tracking_run or cfg["tracking_run"])
    if not (track_dir / "COMPLETE").exists():
        raise RuntimeError(f"Tracking run is not complete: {track_dir}")
    frames = [json.loads(l) for l in (track_dir / "frames.jsonl").read_text(encoding="utf-8").splitlines() if l]
    with (track_dir / "tracks.csv").open(encoding="utf-8") as f:
        tracks = list(csv.DictReader(f))
    for f in frames:  # stored paths -> paths on this machine
        for key in ("rgb_path", "segmentation_mask"):
            f[key] = str(rp.resolve(f[key], rp.active_roots()))
    rows_by_step = defaultdict(list)
    for r in tracks:
        rows_by_step[int(r["step"])].append(r)
    capture_dir = Path(office["capture_dir"])
    if {f["sequence_id"] for f in frames}.__len__() != 1:
        raise RuntimeError("Tracking run spans several sequences; this script expects one.")
    for f in frames:
        if not Path(f["rgb_path"]).resolve().is_relative_to(capture_dir.resolve()):
            raise RuntimeError(f"Tracked frame {f['rgb_path']} is not in the configured capture {capture_dir}")
    records = load_records(capture_dir)
    label_s, box_s = sensor_roles(records)
    h, w = frames[0]["image_height"], frames[0]["image_width"]
    ctx = {"cfg": cfg, "capture_dir": capture_dir, "records": records, "label_sensor": label_s, "box_sensor": box_s,
           "tracked_sensor": frames[0]["sensor_id"], "frames_by_step": {f["step"]: f for f in frames},
           "far_m": depth_cfg["far_m"], "width": w, "height": h,
           "K": tdd.pixel_intrinsics(w, h, depth_cfg["intrinsics"]["vertical_fov_deg"]),
           "class_ids": {c: i for i, c in enumerate(office["project_classes"])},
           "rng": np.random.default_rng(0)}
    steps = cfg["check_steps"] if args.check_only else [f["step"] for f in frames]
    out = resolve(office["output_root"]) / f"fuse_{len(steps)}f_{datetime.now():%Y%m%d_%H%M%S}"
    (out / "overlays").mkdir(parents=True)
    write_json(out / "run_status.json", {"status": "running"})
    write_json(out / "run_info.json", {
        "command": " ".join(sys.argv), "config": cfg, "tracking_run": str(track_dir),
        "segmentation_run": json.loads((track_dir / "tracking_summary.json").read_text())["segmentation_run"],
        "capture_dir": str(capture_dir), "depth_config": depth_cfg, "intrinsics": ctx["K"],
        "check_only": args.check_only, "steps": len(steps), "split": split})
    try:
        checks = geometry_checks(ctx, cfg["check_steps"])
        write_json(out / "geometry_checks.json", checks)
        if not checks["passed"]:
            write_json(out / "run_status.json", {"status": "geometry_unverified", "failures": checks["failures"],
                                                 "note": "No positions or metric errors were produced."})
            print("Geometry checks FAILED; see geometry_checks.json")
            return out
        states, frame_info = [], []
        for step in steps:
            frame, meta = ctx["frames_by_step"][step], records[(label_s, step)]
            fs, fi = fuse_frame(frame, rows_by_step.get(step, []), meta, ctx)
            states += fs
            frame_info.append({"step": step, "timestamp": frame["timestamp"], **fi, "observations": len(fs),
                               "valid_positions": sum(s["position_valid"] for s in fs)})
            if step in cfg["overlay_steps"]:
                draw_overlay(frame, fs, out / "overlays" / f"step_{step:06d}.png")
        with (out / "object_states.csv").open("w", newline="", encoding="utf-8") as f:
            wr = csv.DictWriter(f, fieldnames=STATE_FIELDS, extrasaction="ignore")
            wr.writeheader()
            for s in states:
                wr.writerow({k_: (round(v, 5) if isinstance(v, float) else v) for k_, v in s.items()})
        (out / "frames.jsonl").write_text("".join(rp.dumps(fi) + "\n" for fi in frame_info), encoding="utf-8")
        report, eval_rows = evaluate(states, ctx)
        report["coverage"] = {
            "observations": len(states), "valid_positions": sum(s["position_valid"] for s in states),
            "invalid_reasons": dict(Counter(s["invalid_reason"] for s in states if not s["position_valid"])),
            "selection_methods": dict(Counter(s["selection_method"] for s in states)),
            "floor_context": dict(Counter(s["floor_context"] for s in states)),
            "floor_world_y_per_frame": stats(fi["floor_world_y"] for fi in frame_info)}
        write_json(out / "evaluation_report.json", report)
        with (out / "association_evaluation.csv").open("w", newline="", encoding="utf-8") as f:
            keys = sorted({k_ for r in eval_rows for k_ in r if k_ not in ("est_world", "ref_box_world_centre", "ref_visible_world")})
            wr = csv.DictWriter(f, fieldnames=keys, extrasaction="ignore")
            wr.writeheader()
            wr.writerows(eval_rows)
        draw_topdown(states, frame_info, eval_rows, out / "topdown_positions.png")
        write_json(out / "run_status.json", {"status": "complete", "frames": len(steps)})
        (out / "COMPLETE").write_text(datetime.now().isoformat(), encoding="utf-8")
    except Exception as e:
        write_json(out / "run_status.json", {"status": "failed", "error": repr(e), "traceback": traceback.format_exc()})
        raise
    print(f"Output: {out}")
    return out


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--config", default="configs/fusion_office.json")
    p.add_argument("--check-only", action="store_true", help="run geometry checks and fuse only the check steps")
    p.add_argument("--tracking-run", help="overrides tracking_run in the config")
    p.add_argument("--capture", help="capture relative to the dataset root (default: the office config's)")
    p.add_argument("--final-evaluation", action="store_true")
    run(p.parse_args())


if __name__ == "__main__":
    main()
