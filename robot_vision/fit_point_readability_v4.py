"""The simulator's readability of a pointing by its angle to the line of sight, fitted as declared in AUDIT.md 16.26.5 (item 4). EVALUATION CODE ONLY (it reads the workers' true pointed
angles); the simulator reads the model file it writes, never the truth.

Frames: analyse_point_frames_v4.run_variant for the REFERENCE reader on the three development zips (guard: development only): frames in the holding phase of a true POINT with a
measurable angle a = the angle between the pointed direction and the line of sight (0 = pointing away from the camera, 180 = at the camera). 15 degree bins [0, 15) ... [165, 180].
A bin with at least 20 such frames: probability = read as POINT / held. A bin with fewer: Nusrat's band as a step (1 inside 45 to 135 degrees, else 0).

Usage (from robot_vision/): python fit_point_readability_v4.py --step5 Z --stop Z --d4 Z [--label x] [--write-config configs/v4/experiments/point_readability.json]
Writes outputs/point_readability_v4_<time>[_label]/ (report.json, report.md, run.json, point_readability.json); never overwrites (--write-config refuses an existing file)."""

from __future__ import annotations

import argparse
import json
import subprocess
import time
from pathlib import Path

import analyse_point_frames_v4 as pf
import analyse_proceed_stop_v4 as ps
import commander_v4 as cm
import gesture_motion as gm
from hri_sim_v4 import readability_p as probability  # noqa: F401  (the one implementation: the simulator's)

HERE = Path(__file__).resolve().parent
BIN_DEG = 15
MIN_FRAMES = 20                    # declared in AUDIT.md 16.26.5
BAND = (45.0, 135.0)               # Nusrat's readable band (16.26)


def band_p(lo: float, hi: float) -> float:
    """The step of the reported band for a whole bin: 1 if it lies inside 45 to 135 degrees, else 0."""
    return 1.0 if lo >= BAND[0] - 1e-9 and hi <= BAND[1] + 1e-9 else 0.0


def fit_bins(frames: list[dict], bin_deg: int = BIN_DEG, min_frames: int = MIN_FRAMES) -> list[dict]:
    """The model of 16.26.5 from per-frame records (cat, phase, cmd, sight_angle)."""
    held = [r for r in frames if r["cat"] == "POINT" and r["phase"] == "holding" and r.get("sight_angle") is not None]
    out = []
    for lo in range(0, 180, bin_deg):
        hi = lo + bin_deg
        top = hi if hi < 180 else 180.0 + 1e-6                    # the last bin includes 180
        fr = [r for r in held if lo <= r["sight_angle"] < top]
        read = sum(r["cmd"] == "POINT" for r in fr)
        if len(fr) >= min_frames:
            out.append({"lo": lo, "hi": hi, "held": len(fr), "read": read, "rate": round(read / len(fr), 4), "source": "fitted", "p": round(read / len(fr), 4)})
        else:
            out.append({"lo": lo, "hi": hi, "held": len(fr), "read": read, "rate": round(read / len(fr), 4) if fr else None, "source": "band", "p": band_p(lo, hi)})
    return out


def markdown(rep: dict) -> str:
    L = [f"## Item 4 of AUDIT.md 16.26.5: the readability of a pointing by its angle to the line of sight (reference reader; guard: {'all development' if rep['guard_all_development'] else 'NOT ALL DEVELOPMENT'})", "",
         "Zips: " + "; ".join(f"{k} `{v['name']}` {v['sha256'][:12]}..." for k, v in rep["zips"].items()), "",
         f"Frames held (holding phase of a true POINT, angle measurable): {rep['held_frames']}; read as POINT {rep['read_frames']}. Bins of {BIN_DEG} degrees; at least {MIN_FRAMES} frames = fitted, else Nusrat's band as a step.", "",
         "| bin (degrees) | held | read as POINT | read rate | used | probability |", "|---|---|---|---|---|---|"]
    for b in rep["bins"]:
        L.append(f"| {b['lo']} to {b['hi']} | {b['held']} | {b['read']} | {'' if b['rate'] is None else format(100 * b['rate'], '.1f') + ' %'} | {b['source']} | {b['p']} |")
    L += ["", f"Bins fitted: {sum(b['source'] == 'fitted' for b in rep['bins'])} of {len(rep['bins'])}; taken from the band: {sum(b['source'] == 'band' for b in rep['bins'])}.",
          "Caveat (declared in 16.26.5): the read rate of the held frames also holds reasons that are not the angle (a window not yet full, slow windows with several people, `insufficient_history`); "
          "the simulator models the hold timing separately, so the fitted probability counts those a second time."]
    return "\n".join(L)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--step5", required=True)
    ap.add_argument("--stop", required=True)
    ap.add_argument("--d4", required=True)
    ap.add_argument("--label", default="")
    ap.add_argument("--write-config", default=None, help="also write the model file here (a new file; an existing one is refused)")
    a = ap.parse_args(argv)
    cfg = ps.load_config()
    rc, cc = gm.load_config(), cm.load_config()
    sets = {"S5": ps.Dataset("S5", a.step5, cfg["sessions"]["S5"], cfg), "STOP": ps.Dataset("STOP", a.stop, cfg["sessions"]["STOP"], cfg), "D4*": ps.Dataset("D4*", a.d4, cfg["sessions"]["D4*"], cfg)}
    ref = next(v for v in pf.VARIANTS if v["key"] == "ref")
    frames: list[dict] = []
    for k, d in sets.items():
        frames += pf.run_variant(d, ref, rc, cc, cfg)
        print("done:", k, flush=True)
    bins = fit_bins(frames)
    held = [r for r in frames if r["cat"] == "POINT" and r["phase"] == "holding" and r.get("sight_angle") is not None]
    commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=HERE, capture_output=True, text=True).stdout.strip()
    rep = {"guard_all_development": all(set(d.guard.values()) == {"development"} for d in sets.values()),
           "zips": {k: {"name": Path(p).name, "sha256": sets[k].logs.sha256()} for k, p in (("S5", a.step5), ("STOP", a.stop), ("D4*", a.d4))},
           "held_frames": len(held), "read_frames": sum(r["cmd"] == "POINT" for r in held), "bins": bins}
    model = {"label": "Readability of a pointing by its angle to the line of sight (AUDIT.md 16.26.5, item 4): P(read as POINT in a frame). Simulator input only.",
             "reader": "reference", "min_frames_per_bin": MIN_FRAMES, "bin_deg": BIN_DEG, "band_deg": list(BAND), "git_commit": commit,
             "zips": {k: v["sha256"] for k, v in rep["zips"].items()}, "bins": [{k: b[k] for k in ("lo", "hi", "p", "source", "held", "read")} for b in bins]}
    out = HERE / "outputs" / f"point_readability_v4_{time.strftime('%Y%m%d_%H%M%S')}{'_' + a.label if a.label else ''}"
    out.mkdir(parents=True, exist_ok=False)
    md = markdown(rep)
    (out / "report.json").write_text(json.dumps(rep, indent=1), encoding="utf-8")
    (out / "report.md").write_text(md + "\n", encoding="utf-8")
    (out / "point_readability.json").write_text(json.dumps(model, indent=1) + "\n", encoding="utf-8")
    (out / "run.json").write_text(json.dumps({"git_commit": commit, "zips": rep["zips"]}, indent=1), encoding="utf-8")
    if a.write_config:
        target = (HERE / a.write_config)
        if target.exists():
            raise SystemExit(f"{target} exists; not overwritten")
        target.write_text(json.dumps(model, indent=1) + "\n", encoding="utf-8")
    print(md)
    print(f"\nFolder: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
