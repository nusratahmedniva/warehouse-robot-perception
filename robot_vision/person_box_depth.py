"""Lower-bound distance of tracked people, for Step 9 people without a usable position.

For every person observation of a Step 8 motion run (detector class or voted class "person"), the configured
percentile (decision.json -> unlocated_distance.box_depth_percentile, 5) of the valid planar depths inside the
person's detection box. Background and other objects in the box can only add depths, so low percentiles stay at
or below the person's own depth: errors go in the safe (near) direction. With camera pitch 0 (checked here from the
recorded poses) the ground-plane distance from the camera is at least the planar depth.

REFERENCE-DEPTH BASELINE: depth is THUD reference depth decoded with configs/depth_thud_synthetic.json, the same
input as Step 4. Only predicted boxes (Step 4 object_states.csv) and depth images are read; no annotation,
reference mask or reference loader. Saturated pixels are invalid; a box without valid depth gets no value.

Usage (from robot_vision/):
    python person_box_depth.py --motion-run outputs/motion_1388f_20261013_223619
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import os
from pathlib import Path

import numpy as np

import data_splits as ds
import decision_io as dio
import run_paths as rp
import thud_depth as tdd

def dataset_root(office_path: Path) -> Path:
    """THUD_DATASET_ROOT, else dataset_root in the office config (same priority as the other scripts)."""
    return Path(os.environ.get("THUD_DATASET_ROOT") or json.loads(office_path.read_text(encoding="utf-8"))["dataset_root"])


FIELDS = ["step", "timestamp", "track_id", "class_name", "position_valid", "x1", "y1", "x2", "y2", "box_pixels",
          "valid_depth_pixels", "depth_percentile_m", "depth_median_box_m", "step4_selected_depth_median_m"]


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--config", default=dio.DEFAULT_CONFIG)
    p.add_argument("--motion-run", required=True)
    a = p.parse_args()

    cfg_path = dio.resolve(a.config)
    cfg = dio.read_json(cfg_path)
    pct = cfg["unlocated_distance"]["box_depth_percentile"]
    motion = dio.resolve(a.motion_run)
    if not (motion / "COMPLETE").exists():
        raise SystemExit(f"Motion run is not complete: {motion}")
    minfo = dio.read_json(motion / "run_info.json")
    office_path = dio.resolve(minfo["config"]["office_config"])
    depth_cfg_path = dio.resolve(minfo["config"]["depth_config"])
    rts = rp.make_roots(dataset_root(office_path), dio.resolve(cfg["paths"]["output_root"]))
    split = ds.guard("Synthetic_Scenes/" + minfo["capture"], False, ds.load())
    capture_dir = rts["dataset_root"] / "Synthetic_Scenes" / minfo["capture"]
    fusion, tracking = rp.resolve(minfo["fusion_run"], rts), rp.resolve(minfo["tracking_run"], rts)
    depth_cfg = tdd.load_depth_config(depth_cfg_path)

    with (motion / "motion_states.csv").open(encoding="utf-8") as f:
        persons = {(int(r["step"]), int(r["track_id"])): r for r in csv.DictReader(f)
                   if "person" in (r["class_name"], r["motion_class"])}
    with (fusion / "object_states.csv").open(encoding="utf-8") as f:
        boxes = {(int(r["step"]), int(r["track_id"])): r for r in csv.DictReader(f)
                 if (int(r["step"]), int(r["track_id"])) in persons}
    rgb = {}
    for line in (tracking / "frames.jsonl").read_text(encoding="utf-8").splitlines():
        if line:
            fr = json.loads(line)
            rgb[fr["step"]] = Path(str(rp.resolve(fr["rgb_path"], rts))).name
    frames = [json.loads(l) for l in (fusion / "frames.jsonl").read_text(encoding="utf-8").splitlines() if l]
    q = np.array([f["pose_rotation_xyzw"] for f in frames])
    pitch_roll = {"max_abs_qx": float(np.abs(q[:, 0]).max()), "max_abs_qz": float(np.abs(q[:, 2]).max())}

    rows, missing_box = [], 0
    for step in sorted({s for s, _ in persons}):
        dpath = capture_dir / "Depth" / rgb[step].replace("rgb_", "depth_")
        depth, valid = tdd.decode_depth(tdd.load_raw_depth(dpath), depth_cfg["far_m"])
        h, w = depth.shape
        for (s, tid), m in sorted(persons.items()):
            if s != step:
                continue
            b = boxes.get((s, tid))
            if b is None:
                missing_box += 1
                continue
            x1, y1, x2, y2 = (float(b[c]) for c in ("x1", "y1", "x2", "y2"))
            c0, c1 = max(0, math.floor(x1)), min(w, math.ceil(x2))
            r0, r1 = max(0, math.floor(y1)), min(h, math.ceil(y2))
            z = depth[r0:r1, c0:c1][valid[r0:r1, c0:c1]]
            rows.append({"step": s, "timestamp": m["timestamp"], "track_id": tid, "class_name": m["class_name"],
                         "position_valid": m["position_valid"], "x1": round(x1, 2), "y1": round(y1, 2),
                         "x2": round(x2, 2), "y2": round(y2, 2), "box_pixels": (r1 - r0) * (c1 - c0),
                         "valid_depth_pixels": int(z.size),
                         "depth_percentile_m": round(float(np.percentile(z, pct)), 5) if z.size else "",
                         "depth_median_box_m": round(float(np.median(z)), 5) if z.size else "",
                         "step4_selected_depth_median_m": b["depth_median_m"]})

    out = dio.new_run_dir(cfg, f"person_box_depth_{len(rows)}obs")
    rp.set_active_roots(rts)
    with (out / "person_box_depth.csv").open("w", newline="", encoding="utf-8") as f:
        wr = csv.DictWriter(f, fieldnames=FIELDS)
        wr.writeheader()
        wr.writerows(rows)
    hashes = dio.copy_configs(out, [cfg_path, depth_cfg_path])
    # office.json holds the machine's dataset root: store it with portable paths, never as a raw copy
    dio.write_json(out / "config_used" / office_path.name, dio.read_json(office_path))
    hashes[office_path.name] = dio.sha256(office_path)
    sel = [(float(r["depth_percentile_m"]), float(r["step4_selected_depth_median_m"])) for r in rows
           if r["depth_percentile_m"] != "" and r["step4_selected_depth_median_m"]]
    info = dio.run_info(cfg_path, {
        "label": "reference-depth baseline", "config_sha256": hashes, "box_depth_percentile": pct,
        "motion_run": str(motion), "fusion_run": str(fusion), "tracking_run": str(tracking),
        "capture": minfo["capture"], "split_of_this_capture": split, "camera_pitch_roll_check": pitch_roll,
        "person_observations": len(persons), "rows": len(rows), "missing_box": missing_box,
        "rows_without_valid_depth": sum(r["depth_percentile_m"] == "" for r in rows),
        "check_percentile_not_above_step4_selected_median": {
            "rows": len(sel), "violations": sum(p_ > m_ + 1e-6 for p_, m_ in sel)}})
    dio.write_json(out / "run_info.json", info)
    dio.mark_complete(out)
    print(f"{len(rows)} person observations, {info['rows_without_valid_depth']} without valid depth, "
          f"percentile above Step 4 median in {info['check_percentile_not_above_step4_selected_median']['violations']}"
          f" of {len(sel)}; pitch/roll {pitch_roll}")
    print(f"Wrote {out}")


if __name__ == "__main__":
    main()
