"""Step 4 report supplement: documents the calibration actually used and adds the analyses missing from a
finished fusion run. Reads the run's files; never modifies them. Writes a new folder
outputs/step4_supplement_<date>_<time>/ (step4_supplement.json, step4_report.md, couch_unmatched.csv).

Reference 2D boxes are read here for evaluation only (classifying unmatched couch boxes).

Usage (from robot_vision/):
    python report_step4.py --fusion-run outputs/fuse_300f_20261011_042733 \
        --depth-validation-run outputs/depth_check_20261011_031941
"""

from __future__ import annotations

import argparse
import csv
import json
import math
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

import numpy as np

import thud_data as td
from check_camera_streams import box_iou
import run_paths as rp
from fuse_objects import ref_boxes_2d, resolve, stats, write_json
from validate_depth import load_records

STATIC_VERIFIED = ("Chair", "Desk", "Sofa")  # reference labels with 3D boxes whose world pose was shown fixed in Step 4


def read_csv(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as f:
        return list(csv.DictReader(f))


def fnum(v):
    return float(v) if v not in ("", None) else None


def is_true(v) -> bool:
    return str(v) == "True"


def calibration_section(run_info: dict, depth_cfg: dict, depth_val: dict | None) -> dict:
    k = run_info["intrinsics"]
    sec = {
        "intrinsics_used": {"fx": k["fx"], "fy": k["fy"], "cx": k["cx"], "cy": k["cy"],
                            "image_size_wh": [int(2 * k["cx"]), int(2 * k["cy"])]},
        "intrinsics_source": ("Square-pixel pinhole from a 60 deg vertical field of view with the principal point at "
                              "the image centre: fy = (H/2)/tan(vfov/2), fx = fy, cx = W/2, cy = H/2 "
                              "(configs/depth_thud_synthetic.json, thud_depth.pixel_intrinsics)."),
        "backprojection": ["x = (u + 0.5 - cx) * Z / fx", "y = -(v + 0.5 - cy) * Z / fy", "z = Z",
                           "u = column index, v = row index, pixel centre at index + 0.5; Z = planar depth (m)",
                           "camera axes: x right, y up, z forward (Unity, left-handed)"],
        "world_transform": ["p_world = R(q) @ p_cam + t", "q = sensor rotation stored as [x, y, z, w]",
                            "t = sensor translation (m); ego pose is identity in this capture"],
        "depth_conversion": {
            "rule": f"depth_m = raw / 65535 * {depth_cfg['far_m']}; raw == 65535 -> invalid (at or beyond far plane)",
            "quantity": "planar depth along the optical axis (camera z), not distance along the pixel ray",
            "evidence": depth_cfg["validation"]["summary"],
        },
        "recorded_camera_intrinsic_rejected": {
            "values": depth_cfg["intrinsics"]["recorded_camera_intrinsic_in_metadata"],
            "reason": ("The metadata camera_intrinsic is not in pixel units. Back-projecting with it puts only 6-16% "
                       "of reference instance points inside their 3D boxes, and projecting the 3D boxes with it gives "
                       "median IoU 0 with the reference 2D boxes; the 60 deg model gives 92-100% and IoU 0.72-0.82."),
        },
    }
    vfov = 2 * math.degrees(math.atan(k["cy"] / k["fy"]))
    sec["vertical_fov_check"] = {
        "fy": k["fy"], "cy": k["cy"], "vertical_fov_deg": round(vfov, 6),
        "note": "2 * atan(cy / fy) = 60.0 deg, Unity's default camera field of view (vertical).",
    }
    if depth_val:
        fitted = depth_val["report"]["fitted_parameters"]
        far = fitted["far_m"]
        sec["far_plane_check"] = {
            "fitted_far_m": far, "nearest_round_m": round(far), "relative_difference": abs(far - round(far)) / round(far),
            "fitted_vertical_fov_deg": fitted["vertical_fov_deg"],
            "note": (f"The fitted far plane {far:.3f} m is within {abs(far - round(far)) / round(far):.2%} of a round "
                     f"{round(far)} m, and the round value fits the held-out captures at least as well, so a 10 m "
                     "depth range is the likely capture setting. It is not Unity's default camera far clip plane "
                     "(1000 m) and is not stated in the capture metadata, so it remains an inference from the fit."),
        }
        sec["depth_validation_run"] = depth_val["path"]
        sec["mean_inside_fraction_by_model_and_capture"] = {
            c: {m: round(s["mean_inside_fraction"], 3) for m, s in v["models"].items()}
            for c, v in depth_val["report"]["captures"].items()}
        sec["recorded_intrinsics_projection_iou_fit_capture"] = depth_val["report"]["captures"].get(
            depth_val["report"]["fit_capture"], {}).get("projection_vs_2d_boxes")
    return sec


def fitted_parameters_section(depth_cfg: dict, depth_val: dict | None) -> dict:
    fitted = depth_val["report"]["fitted_parameters"] if depth_val else None
    return {
        "parameters_fitted_against_reference_boxes": [
            {"parameter": "depth far plane (far_m)", "fitted_value": fitted and fitted["far_m"], "used_value": depth_cfg["far_m"]},
            {"parameter": "vertical field of view (deg)", "fitted_value": fitted and fitted["vertical_fov_deg"],
             "used_value": depth_cfg["intrinsics"]["vertical_fov_deg"]},
        ],
        "calibration_data": depth_cfg["validation"]["fit_capture"] + " (every 10th step, reference 3D boxes of Chair/Desk/Sofa)",
        "independent_test_data": depth_cfg["validation"]["test_captures"],
        "overlap_with_step4_evaluation": (
            "Step 4 was evaluated on the same capture used for the depth/FOV fit. The rounded values (10 m, 60 deg) were "
            "then confirmed unchanged on the four held-out captures, which is the independent evidence for the "
            "calibration. Step 4's inside-3D-box rates on Capture_1 are therefore NOT independent of the calibration. "
            "The visible-point error uses the same depth and intrinsics on both sides, so it does not test them."),
        "not_fitted": ("Step 4 pixel-selection rules, thresholds and the association IoU were set before the full run "
                       "and were not tuned on reference boxes or on the evaluation results. Geometry-check thresholds "
                       "are pass/fail criteria, not fitted values."),
    }


def per_class_table(assoc: list[dict]) -> list[dict]:
    rows = []
    valid = [r for r in assoc if is_true(r["associated"]) and is_true(r["position_valid"])]
    for label in sorted({r["ref_label"] for r in valid}):
        sel = [r for r in valid if r["ref_label"] == label]
        err = [fnum(r["err_visible_point_m"]) for r in sel if fnum(r["err_visible_point_m"]) is not None]
        inside = [is_true(r["inside_ref_3d_box_with_margin"]) for r in sel if r["inside_ref_3d_box_with_margin"] != ""]
        s = stats(err)
        rows.append({"reference_label": label, "associated_valid": len(sel), "with_visible_point_error": s["n"],
                     "visible_point_error_median_m": s.get("median"), "visible_point_error_p90_m": s.get("p90"),
                     "with_3d_box": len(inside), "inside_3d_box_with_margin": float(np.mean(inside)) if inside else None,
                     "detector_classes": dict(Counter(r["class_name"] for r in sel)),
                     "selection_methods": dict(Counter(r["selection_method"] for r in sel))})
    return rows


def classify_unmatched(assoc: list[dict], states: list[dict], records: dict, label_sensor: str, cls: str,
                       compatible: list[str], min_iou: float) -> tuple[dict, list[dict]]:
    """Each unmatched box of detector class `cls`, by its best-overlapping reference 2D box (any label)."""
    boxes = {(int(s["step"]), s["track_id"]): tuple(float(s[c]) for c in ("x1", "y1", "x2", "y2")) for s in states}
    taken = defaultdict(set)
    for r in assoc:
        if is_true(r["associated"]):
            taken[int(r["step"])].add(int(r["ref_instance_id"]))
    out = []
    for r in assoc:
        if r["class_name"] != cls or is_true(r["associated"]):
            continue
        step = int(r["step"])
        box = boxes[(step, r["track_id"])]
        refs = ref_boxes_2d(records[(label_sensor, step)])
        ious = [(box_iou(box, ref["box"]), ref) for ref in refs]
        best_iou, best = max(ious, key=lambda x: x[0], default=(0.0, None))
        same = [(i, ref) for i, ref in ious if ref["label"] in compatible]
        best_same = max((i for i, _ in same), default=0.0)
        if best_iou <= 0:
            cat = "no_overlap_with_any_reference_box"
        elif best["label"] in compatible:
            cat = ("same_label_iou_ge_threshold_but_reference_taken_by_another_track" if best_iou >= min_iou
                   else "same_label_iou_below_threshold")
        else:
            cat = "best_overlap_is_another_label"
        out.append({"step": step, "track_id": r["track_id"], "category": cat,
                    "best_iou": round(best_iou, 4), "best_label": best["label"] if best else "",
                    "best_instance_id": best["instance_id"] if best else "",
                    "best_instance_already_matched": bool(best and best["instance_id"] in taken[step]),
                    "best_same_label_iou": round(best_same, 4),
                    "same_label_boxes_in_frame": len(same),
                    "x1": box[0], "y1": box[1], "x2": box[2], "y2": box[3]})
    summary = {
        "detector_class": cls, "compatible_reference_labels": compatible, "unmatched": len(out),
        "by_category": dict(Counter(o["category"] for o in out)),
        "other_label_breakdown": dict(Counter(o["best_label"] for o in out if o["category"] == "best_overlap_is_another_label")),
        "other_label_with_iou_ge_threshold": sum(1 for o in out if o["category"] == "best_overlap_is_another_label"
                                                 and o["best_iou"] >= min_iou),
        "same_label_iou_below_threshold_iou": stats(o["best_iou"] for o in out if o["category"] == "same_label_iou_below_threshold"),
        "frames_with_no_same_label_box": sum(1 for o in out if o["same_label_boxes_in_frame"] == 0),
        "distinct_tracks": len({o["track_id"] for o in out}),
        "rule": ("category from the reference 2D box (any label) with the highest IoU: none overlapping -> no overlap; "
                 "a compatible label -> same label (IoU below threshold, or above it but that reference was assigned to "
                 "another track by the one-to-one matching); otherwise another label."),
    }
    return summary, out


def timing_and_steps(states: list[dict], frames: list[dict], assoc: list[dict]) -> dict:
    ts = np.array(sorted({f["timestamp"] for f in frames}), dtype=float)
    dt = np.diff(ts)
    # reference label per track = most frequent associated reference label (evaluation-only grouping)
    labels = defaultdict(Counter)
    for r in assoc:
        if is_true(r["associated"]):
            labels[r["track_id"]][r["ref_label"]] += 1
    track_group = {}
    for tid, c in labels.items():
        lab = c.most_common(1)[0][0]
        track_group[tid] = "people" if lab == "people" else ("static_verified" if lab in STATIC_VERIFIED else "other_reference")
    by_track = defaultdict(list)
    for s in states:
        if is_true(s["position_valid"]):
            by_track[s["track_id"]].append(s)
    steps_3d, steps_ground = defaultdict(list), defaultdict(list)
    for tid, obs in by_track.items():
        obs.sort(key=lambda s: int(s["step"]))
        g = track_group.get(tid, "unassociated")
        for a, b in zip(obs, obs[1:]):
            if int(b["step"]) - int(a["step"]) != 1:
                continue
            d = np.array([fnum(b[c]) - fnum(a[c]) for c in ("world_x", "world_y", "world_z")])
            steps_3d[g].append(float(np.linalg.norm(d)))
            steps_ground[g].append(float(np.hypot(d[0], d[2])))
    return {
        "frames": len(ts), "median_dt_s": float(np.median(dt)), "dt_min_s": float(dt.min()), "dt_max_s": float(dt.max()),
        "median_frame_rate_hz": float(1 / np.median(dt)),
        "track_grouping": ("people / static_verified (Chair, Desk, Sofa) / other_reference by the track's most frequent "
                           "associated reference label (evaluation-only); unassociated = never associated"),
        "frame_to_frame_world_step_m": {g: {"ground_plane_xz": stats(steps_ground[g]), "3d": stats(steps_3d[g])}
                                        for g in sorted(steps_3d)},
        "note": ("Consecutive-step pairs of valid positions of the same track. For static objects the true step is 0, "
                 "so their step size is pixel-selection jitter of the visible-surface point."),
    }


def write_markdown(rep: dict, path: Path) -> None:
    c, f, t, u = rep["calibration"], rep["fitted_parameters"], rep["timing_and_steps"], rep["unmatched_couch"]
    k = c["intrinsics_used"]
    L = [f"# Step 4 report supplement — {rep['fusion_run']}", "",
         f"**Depth source:** {rep['depth_source']} — reference-depth fusion baseline; it does not measure an RGB-only "
         "depth model. Camera poses are the recorded reference poses.", "",
         "**Data split:** " + "; ".join(f"{k_}: {', '.join(v)}" for k_, v in rep["data_splits"]["splits"].items())
         + f" (scene {rep['data_splits']['scene']}). This run is on the development capture.", "",
         "## Calibration used", "",
         f"- fx = fy = {k['fx']:.4f}, cx = {k['cx']}, cy = {k['cy']} ({k['image_size_wh'][0]}x{k['image_size_wh'][1]} px).",
         f"- Source: {c['intrinsics_source']}",
         "- Back-projection: " + "; ".join(c["backprojection"]) + ".",
         "- World: " + "; ".join(c["world_transform"]) + ".",
         f"- Depth: {c['depth_conversion']['rule']}. {c['depth_conversion']['quantity']}.",
         f"- Evidence: {c['depth_conversion']['evidence']}",
         f"- Field of view check: fy = {c['vertical_fov_check']['fy']:.2f}, cy = {c['vertical_fov_check']['cy']} -> "
         f"vertical FOV {c['vertical_fov_check']['vertical_fov_deg']:.1f} deg. {c['vertical_fov_check']['note']}",
         *([f"- Far plane: {c['far_plane_check']['note']}"] if "far_plane_check" in c else []),
         f"- Recorded camera_intrinsic rejected ({c['recorded_camera_intrinsic_rejected']['values']}): "
         f"{c['recorded_camera_intrinsic_rejected']['reason']}", "",
         "## Parameters fitted on reference boxes", ""]
    for p in f["parameters_fitted_against_reference_boxes"]:
        L.append(f"- {p['parameter']}: fitted {p['fitted_value']}, used {p['used_value']}.")
    L += [f"- Calibration data: {f['calibration_data']}. Independent test data: {', '.join(f['independent_test_data'])}.",
          f"- {f['overlap_with_step4_evaluation']}", f"- {f['not_fitted']}", "",
          "## Statements", ""] + [f"- {s}" for s in rep["statements"]] + [
          "", "## Per-class results (all associated classes)", "",
          "| Reference label | Associated (valid) | Visible-point error n | median (m) | p90 (m) | With 3D box | Inside 3D box (+5 cm) |",
          "|---|---|---|---|---|---|---|"]
    fmt = lambda v, f=".3f": "—" if v is None else format(v, f)  # noqa: E731
    for r in rep["per_class"]:
        L.append(f"| {r['reference_label']} | {r['associated_valid']} | {r['with_visible_point_error']} | "
                 f"{fmt(r['visible_point_error_median_m'])} | {fmt(r['visible_point_error_p90_m'])} | {r['with_3d_box']} | "
                 f"{fmt(r['inside_3d_box_with_margin'], '.0%')} |")
    L.append(f"| **total** | {sum(r['associated_valid'] for r in rep['per_class'])} | | | | | |")
    L += ["", f"## Unmatched couch boxes ({u['unmatched']}, {u['distinct_tracks']} tracks)", "", u["rule"], ""]
    for cat, n in sorted(u["by_category"].items(), key=lambda x: -x[1]):
        L.append(f"- {cat}: {n}")
    if u["other_label_breakdown"]:
        L.append(f"- other-label breakdown: {u['other_label_breakdown']} "
                 f"({u['other_label_with_iou_ge_threshold']} of them with IoU >= threshold)")
    if u["same_label_iou_below_threshold_iou"].get("n"):
        s = u["same_label_iou_below_threshold_iou"]
        L.append(f"- same-label IoU: median {s['median']:.2f}, max {s['max']:.2f}")
    L += ["", "## Timing and frame-to-frame world step", "",
          f"- {t['frames']} frames, median dt {t['median_dt_s']:.4f} s ({t['median_frame_rate_hz']:.2f} Hz), "
          f"range {t['dt_min_s']:.4f}–{t['dt_max_s']:.4f} s.",
          f"- Grouping: {t['track_grouping']}.", "",
          "| Group | pairs | ground-plane step median (m) | p90 (m) | max (m) |", "|---|---|---|---|---|"]
    for g, v in t["frame_to_frame_world_step_m"].items():
        s = v["ground_plane_xz"]
        L.append(f"| {g} | {s['n']} | {s['median']:.4f} | {s['p90']:.4f} | {s['max']:.3f} |")
    L += ["", t["note"]]
    path.write_text(rp.portable_text("\n".join(L) + "\n", rp.active_roots())[0], encoding="utf-8")


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--fusion-run", required=True, help="finished fuse_objects.py output folder")
    p.add_argument("--depth-validation-run", help="validate_depth.py output folder (for the rejected-model scores)")
    p.add_argument("--splits", default="configs/data_splits.json")
    args = p.parse_args()
    run = resolve(args.fusion_run)
    if not (run / "COMPLETE").exists():
        raise SystemExit(f"Fusion run is not complete: {run}")
    run_info = json.loads((run / "run_info.json").read_text(encoding="utf-8"))
    cfg = run_info["config"]
    office = td.load_config(resolve(cfg["office_config"]))
    rp.set_active_roots(rp.roots_from_config(office))
    depth_cfg = run_info["depth_config"]
    depth_val = None
    if args.depth_validation_run:
        dv = resolve(args.depth_validation_run)
        depth_val = {"path": str(dv), "report": json.loads((dv / "depth_validation_report.json").read_text(encoding="utf-8"))}
    states = read_csv(run / "object_states.csv")
    assoc = read_csv(run / "association_evaluation.csv")
    frames = [json.loads(l) for l in (run / "frames.jsonl").read_text(encoding="utf-8").splitlines() if l]
    records = load_records(Path(office["capture_dir"]))
    checks = json.loads((run / "geometry_checks.json").read_text(encoding="utf-8"))
    ev = cfg["evaluation"]
    couch_summary, couch_rows = classify_unmatched(assoc, states, records, checks["label_sensor"], "couch",
                                                   ev["compatible_reference_labels"]["couch"], ev["association_min_iou"])
    rep = {
        "created": datetime.now().isoformat(timespec="seconds"),
        "fusion_run": str(run), "capture_dir": office["capture_dir"],
        "data_splits": json.loads(resolve(args.splits).read_text(encoding="utf-8")),
        "depth_source": cfg["depth_source"],
        "calibration": calibration_section(run_info, depth_cfg, depth_val),
        "fitted_parameters": fitted_parameters_section(depth_cfg, depth_val),
        "statements": [
            "The static-box check (Chair/Desk/Sofa 3D boxes fixed in the world to about 1 micrometre under "
            "world = R(q) p + t, metres apart under the transpose) verifies the pose convention and the reference "
            "poses' internal consistency. It does not establish micrometre-level perception accuracy.",
            "Stored positions: cam_x/cam_y/cam_z are camera-frame metres (x right, y up, z forward, Unity left-handed); "
            "world_x/world_y/world_z are Unity world metres with y up, so the ground plane is world x-z.",
            "With rendered (reference) depth, the visible-point error compares two medians computed from the same depth "
            "map, so it measures pixel-selection / segmentation error, not depth error.",
            "Each estimated position is a visible-surface point (per-axis median of selected pixels), not a 3D box centre.",
        ],
        "per_class": per_class_table(assoc),
        "unmatched_couch": couch_summary,
        "timing_and_steps": timing_and_steps(states, frames, assoc),
    }
    out = resolve(office["output_root"]) / f"step4_supplement_{datetime.now():%Y%m%d_%H%M%S}"
    out.mkdir(parents=True)
    write_json(out / "step4_supplement.json", rep)
    with (out / "couch_unmatched.csv").open("w", newline="", encoding="utf-8") as f:
        wr = csv.DictWriter(f, fieldnames=list(couch_rows[0]) if couch_rows else ["step"])
        wr.writeheader()
        wr.writerows(couch_rows)
    write_markdown(rep, out / "step4_report.md")
    print(f"Output: {out}")


if __name__ == "__main__":
    main()
