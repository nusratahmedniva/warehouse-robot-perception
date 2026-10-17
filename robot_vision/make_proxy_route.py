"""Write an explicit route-corridor config ("proxy_route") from the recorded camera trajectory of a fusion run.

The corridor centreline is the recorded reference camera path on the ground plane (world x, z), resampled
every --spacing metres. Its width is the one required passage width, footprint.load_footprint (robot.json and
the load file it names). Step 9 decisions read only the centreline, never this width.
This is a test fixture for THUD, not a planned robot route; using reference poses makes it a controlled
experimental baseline.

Usage (from robot_vision/):
    python make_proxy_route.py --fusion-run outputs/fuse_300f_20261011_042733 \
        --out configs/proxy_route_office_capture1.json
"""

from __future__ import annotations

import argparse
import json

import numpy as np

import footprint as fp
from fuse_objects import resolve


def resample(path: np.ndarray, spacing: float) -> np.ndarray:
    seg = np.linalg.norm(np.diff(path, axis=0), axis=1)
    s = np.concatenate([[0], np.cumsum(seg)])
    keep = np.concatenate([[True], seg > 1e-9])
    s, path = s[keep], path[keep]
    q = np.append(np.arange(0, s[-1], spacing), s[-1])
    return np.stack([np.interp(q, s, path[:, 0]), np.interp(q, s, path[:, 1])], axis=1)


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--fusion-run", required=True)
    p.add_argument("--robot-config", default="configs/robot.json")
    p.add_argument("--spacing", type=float, default=0.25)
    p.add_argument("--out", required=True)
    a = p.parse_args()
    run = resolve(a.fusion_run)
    frames = [json.loads(l) for l in (run / "frames.jsonl").read_text(encoding="utf-8").splitlines() if l]
    info = json.loads((run / "run_info.json").read_text(encoding="utf-8"))
    cam = np.array([[f["pose_translation"][0], f["pose_translation"][2]] for f in frames])
    line = resample(cam, a.spacing)
    foot = fp.load_footprint(resolve(a.robot_config))
    width = foot["required_width_m"]
    note = f"robot and load footprint (load: {foot['load_label']})" if foot["load"] else "robot only (no load configured)"
    out = {
        "label": "proxy_route",
        "description": "Corridor around the recorded reference camera path; a THUD test fixture, not a planned robot route.",
        "source": {"fusion_run": run.name, "capture": info["capture_dir"].replace("\\", "/").split("Synthetic_Scenes/")[-1],
                   "steps": [frames[0]["step"], frames[-1]["step"]], "poses": "reference camera poses (controlled baseline)"},
        "plane_axes": ["world_x", "world_z"],
        "centreline_xz_m": [[round(x, 4), round(z, 4)] for x, z in line],
        "centreline_length_m": round(float(np.linalg.norm(np.diff(line, axis=0), axis=1).sum()), 4),
        "width_m": round(width, 4),
        "width_rule": "footprint.required_width: (furthest right - furthest left extent of robot and load) + 2 * safety_margin_per_side_m",
        "width_note": note,
        "resample_spacing_m": a.spacing,
    }
    resolve(a.out).write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {resolve(a.out)}: {len(line)} points, {out['centreline_length_m']} m, width {out['width_m']} m")


if __name__ == "__main__":
    main()
