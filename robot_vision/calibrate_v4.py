"""v4 threshold calibration (P4, Nusrat during Anisha's absence, 2026-11-12; AUDIT.md section 15; the design and grids are declared in
unity/.../Avatar/Config/upgrade_design.md section 10). EVALUATION CODE ONLY (reads truth.jsonl); inference code never imports it.

Implements Anisha's B12 rule exactly (AUDIT.md 14.11 item 3, configs/v4/final_plan.json threshold_rule): for each initial threshold, the
value with the highest DEVELOPMENT accuracy among those with coverage >= 0.8; ties go to the v3 value, else to the more conservative value
(the one that answers less often). One threshold at a time, all others at their committed values.

Data: development sessions of the development looks sunbox_m1 and sunbox_f1 only (refused otherwise, before anything is computed): the
Unity session folder (run_###/truth.jsonl, truth_run###.json) and the bridge run folder (model_outputs.jsonl, v4_log.jsonl). The reader
(gesture_motion) and the commander rule are re-run offline on the logged model outputs (body keypoints, hand landmarks), frame by frame,
and scored against the commander's truth rows in the accuracy phases (gesturing, holding): accuracy = correct among answered frames,
coverage = answered among those frames. branch_match_max_deg is scored on held POINT frames resolved with the roadmap. Measured, not swept:
the arm ratio (median YOLO shoulder-to-wrist over shoulder width on held POINT frames whose true direction lies within 30 deg of the
camera's image plane, upgrade_design.md section 13) and nothing else.

Usage (from robot_vision/):
  python calibrate_v4.py --session outputs/trials_X outputs/bridge_guide_Y [--session ...] [--write]
Without --write it only reports (outputs/calibrate_v4_<time>/report.json, report.md). With --write it also writes the chosen values into
configs/v4/gesture_reader.json, commander.json and the three control*.json, each with the date, the rule and the evidence folder.
"""

from __future__ import annotations

import argparse
import copy
import json
import math
import re
import statistics as st
from collections import defaultdict
from datetime import date
from pathlib import Path
from types import SimpleNamespace

import numpy as np

import commander_v4 as cm
import data_splits_v4 as ds
import gesture_data as gd
import gesture_motion as gm
import hri_control as hc
import hri_control_v4 as hv
import hri_eval_dev_v4 as ev
import hri_perception_v4 as hp4

HERE = Path(__file__).resolve().parent
CALIBRATION_LOOKS = ("sunbox_m1", "sunbox_f1")            # AUDIT.md 14.16 item 3: never sunbox_f2
COVERAGE_MIN = 0.8

# upgrade_design.md section 10 (declared 2026-11-12, before any calibration data): (config, path, grid, v3 value or None)
GRIDS = [
    ("reader", ("window", "window_s"), [1.0, 1.5, 2.0], None),
    ("reader", ("window", "min_valid_fraction"), [0.5, 0.6, 0.7, 0.8], None),
    ("reader", ("window", "hold_min_s"), [0.3, 0.4, 0.5, 0.6], None),
    ("reader", ("window", "stop_window_s"), [0.2, 0.3, 0.4, 0.5], None),
    ("reader", ("keypoints", "arm_raised_margin"), [0.10, 0.15, 0.20, 0.25, 0.30, 0.35], None),
    ("reader", ("motion", "still_speed_max"), [0.2, 0.3, 0.4, 0.5, 0.6], None),
    ("reader", ("motion", "motion_path_min"), [0.2, 0.3, 0.4, 0.5, 0.6], None),
    ("reader", ("point", "point_arm_extension_min_deg"), [120, 130, 140, 150, 160], None),
    ("reader", ("point", "segment_disagreement_max_deg"), [30, 45, 60], 45),
    ("reader", ("point", "point_elevation_max_deg"), [45, 60, 75], None),
    ("reader", ("hand", "finger_extended_ratio"), [1.4, 1.5, 1.6, 1.7, 1.8], None),
    ("reader", ("hand", "finger_curled_ratio"), [1.0, 1.1, 1.2, 1.3], None),
    ("reader", ("hand", "palm_spread_min_deg"), [10, 15, 20, 25, 30], None),
    ("reader", ("hand", "index_up_tol_deg"), [20, 30, 40, 50], None),
    ("reader", ("hand", "wait_forearm_vertical_tol_deg"), [30, 40, 50, 60], None),
    ("reader", ("hand", "wait_arm_extension_max_deg"), [110, 120, 130, 140], None),
    ("reader", ("decision", "class_share_min"), [0.5, 0.6, 0.7, 0.8, 0.9], None),
    ("reader", ("decision", "class_margin_min"), [0.1, 0.2, 0.3], None),
    ("reader", ("proceed", "window_s"), [1.5, 2.0, 2.5], None),
    ("reader", ("proceed", "cycles_min"), [1.5, 2.0, 2.5, 3.0], None),
    ("reader", ("proceed", "swing_min"), [0.20, 0.25, 0.30, 0.35, 0.40], None),
    ("reader", ("proceed", "vertical_share_min"), [0.5, 0.6, 0.7, 0.8], None),
    ("commander", ("facing_shoulder_ratio_min",), [0.3, 0.4, 0.5, 0.6], None),
    ("control", ("dialog", "branch_match_max_deg"), [20, 25, 30, 35, 40], None),
]
FILES = {"reader": "configs/v4/gesture_reader.json", "commander": "configs/v4/commander.json",
         "control": ("configs/v4/control.json", "configs/v4/control_zoom_on.json", "configs/v4/control_zoom_off.json")}


# ---------------------------------------------------------------- data

def guard_looks(runs: list) -> None:
    """Refuse anything but the two development looks (on top of the development split guard of load_sessions)."""
    bad = sorted({lk for r in runs for lk in r.looks} - set(CALIBRATION_LOOKS))
    if bad:
        raise SystemExit(f"calibration uses {', '.join(CALIBRATION_LOOKS)} only; refused: {', '.join(bad)}")


def load(pairs) -> tuple[list, dict]:
    """(runs of hri_eval_dev_v4, pan-tilt model-output frames per run name). Development data only (SystemExit otherwise)."""
    runs = ev.load_sessions(pairs, gd.load_config())
    guard_looks(runs)
    frames: dict[str, list] = defaultdict(list)
    for unity, bridge in pairs:
        mine = [r for r in runs if Path(r.unity_dir) == Path(unity)]
        spans = [(min(t.time_s for t in r.truth), max(t.time_s for t in r.truth), r) for r in mine if r.truth]
        p = Path(bridge) / "model_outputs.jsonl"
        if not p.exists():
            raise SystemExit(f"{p} is missing: calibration needs the per-frame model outputs (P12)")
        for line in p.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            row = json.loads(line)
            if row.get("cam") != "pan_tilt":
                continue
            for lo, hi, r in spans:
                if lo - 1e-6 <= row["time_s"] <= hi + 1e-6:
                    frames[r.name].append(row)
                    break
    return runs, frames


def _hands(raw: list) -> dict:
    out: dict[int, list] = defaultdict(list)
    for h in raw:
        out[h["track_id"]].append(SimpleNamespace(
            track_id=h["track_id"], category=h["category"], score=h["score"], handedness=h.get("handedness"),
            landmarks_px=np.asarray(h["lm"], float), world_xyz=np.asarray(h["world"], float) if h.get("world") else None,
            box=tuple(h["box"]), wrist=tuple(h.get("wrist", h["lm"][0]))))
    return out


def replay(frames: list, rcfg: dict, ccfg: dict) -> list:
    """[(frame, [PersonReading])] for one run, re-running the reader on the logged outputs."""
    pipe = hp4.PersonsPipeline(rcfg, ccfg)
    out = []
    for f in frames:
        dets = [{"track_id": p["track_id"], "box": tuple(p["box"]), "kp": np.asarray([k[:2] for k in p["kp"]], float),
                 "conf": np.asarray([k[2] if k[2] is not None else 0.0 for k in p["kp"]], float)} for p in f["people"] if p["kp"]]
        meta = {"t": f["time_s"], **{k: f[k] for k in ("fx", "fy", "cx", "cy", "width", "height")}, "pan_deg": f["pan_deg"],
                "tilt_deg": f.get("tilt_deg", 0.0), "robot_yaw_deg": f["pose"]["yaw_deg"]}
        out.append((f, pipe.update(dets, _hands(f["hands"]), meta)))
    return out


def _commander_row(run, t: float, tol: float):
    best = None
    for r in run.truth:
        if r.is_commander and abs(r.time_s - t) <= tol + 1e-9 and (best is None or abs(r.time_s - t) < abs(best.time_s - t)):
            best = r
    return best


def _bearing(pose: dict, x: float, z: float) -> float:
    return hc.wrap(hc.yaw_to(pose["x"], pose["z"], x, z) - pose["yaw_deg"])


# ---------------------------------------------------------------- scoring

def score(runs, frames, rcfg, ccfg, v4cfg, kind: str, road, ecfg, gcfg) -> dict:
    """{frames, answered, correct, coverage, accuracy} of one configuration ('reader', 'commander' or 'control')."""
    tol, phases = gcfg["truth_join_max_s"], ecfg["accuracy_phases"]
    n = answered = correct = 0
    for run in runs:
        goal = ev.run_goal(run)
        log = sorted(run.rows, key=lambda r: r["t"])
        log_t = [r["t"] for r in log]
        for f, persons in replay(frames.get(run.name, []), rcfg, ccfg):
            truth = _commander_row(run, f["time_s"], tol)
            if truth is None or truth.true_command == "NONE" or truth.phase not in phases:
                continue
            tb = _bearing(f["pose"], truth.x, truth.z)
            near = sorted((abs(hc.wrap(p.bearing_deg - tb)), p) for p in persons) if persons else []
            mine = near[0][1] if near and near[0][0] <= ecfg["match_bearing_deg"] else None
            if kind == "reader":
                n += 1
                if mine is not None and mine.reading.command in ev.GESTURES:
                    answered += 1
                    correct += mine.reading.command == truth.true_command
            elif kind == "commander":
                n += 1
                ch = cm.pick_commander(persons, ccfg)
                if ch.commander is not None:
                    answered += 1
                    correct += mine is not None and ch.commander == mine.track_id
            else:                                            # control: branch_match_max_deg on held POINT frames
                if truth.true_command != "POINT" or truth.phase != "holding" or goal is None:
                    continue
                import bisect
                i = bisect.bisect_left(log_t, f["time_s"])
                cand = [log[j] for j in (i - 1, i) if 0 <= j < len(log) and abs(log[j]["t"] - f["time_s"]) <= tol]
                if not cand:
                    continue
                node = cand[0]["junction"]
                true_branch = road.command_toward(node, goal)
                n += 1
                if mine is None or mine.reading.command != "POINT" or mine.reading.point is None:
                    continue
                dirs, arrival = hv.branch_directions(road, node)
                res = hv.resolve_point(mine.reading.point, dirs, arrival, f["pose"]["yaw_deg"], v4cfg["dialog"]["branch_match_max_deg"])
                if res.command is not None:
                    answered += 1
                    correct += res.command == true_branch
    return {"frames": n, "answered": answered, "correct": correct,
            "coverage": round(answered / n, 4) if n else None, "accuracy": round(correct / answered, 4) if answered else None}


def choose_b12(rows: list, committed, v3_value=None) -> tuple:
    """B12: the value with the highest accuracy among those with coverage >= 0.8; ties to the v3 value, else to the more
    conservative (lower coverage); no value qualifies -> the committed value stays (upgrade_design.md section 13). (value, why)."""
    ok = [r for r in rows if r["coverage"] is not None and r["accuracy"] is not None and r["coverage"] >= COVERAGE_MIN - 1e-12]
    if not ok:
        return committed, f"no value reaches coverage {COVERAGE_MIN}: committed value kept"
    best = max(r["accuracy"] for r in ok)
    tied = [r for r in ok if abs(r["accuracy"] - best) < 1e-12]
    if len(tied) == 1:
        return tied[0]["value"], "highest accuracy with coverage >= 0.8"
    if v3_value is not None and any(r["value"] == v3_value for r in tied):
        return v3_value, "tie: the v3 value"
    low = min(r["coverage"] for r in tied)
    cons = [r for r in tied if abs(r["coverage"] - low) < 1e-12]
    if len(cons) == 1:
        return cons[0]["value"], "tie: the more conservative value (answers less often)"
    if any(r["value"] == committed for r in cons):
        return committed, "tie in accuracy and coverage: committed value kept"
    return cons[0]["value"], "tie in accuracy and coverage: the first of the grid"


def measure_arm_ratio(runs, frames, rcfg, ccfg, ecfg, gcfg) -> dict:
    """Median shoulder-to-wrist over shoulder width (YOLO keypoints) of the pointing arm on held POINT frames whose true direction
    lies within 30 deg of the camera's image plane (where the arm is not foreshortened)."""
    tol = gcfg["truth_join_max_s"]
    ratios = []
    for run in runs:
        for f in frames.get(run.name, []):
            truth = _commander_row(run, f["time_s"], tol)
            if truth is None or truth.true_command != "POINT" or truth.phase != "holding":
                continue
            cam_yaw = f["pose"]["yaw_deg"] - f["pan_deg"]
            world = f["pose"]["yaw_deg"] + truth.point_angle_deg
            if abs(abs(hc.wrap(world - cam_yaw)) - 90.0) > 30.0:
                continue
            tb = _bearing(f["pose"], truth.x, truth.z)
            best = None
            for p in f["people"]:
                if not p["kp"]:
                    continue
                kp = np.asarray([k[:2] for k in p["kp"]], float)
                conf = np.asarray([k[2] or 0.0 for k in p["kp"]], float)
                u = 0.5 * (kp[gm.L_SHOULDER][0] + kp[gm.R_SHOULDER][0])
                b = math.degrees(math.atan((u - f["cx"]) / f["fx"])) - f["pan_deg"]
                if abs(hc.wrap(b - tb)) <= ecfg["match_bearing_deg"] and (best is None or abs(hc.wrap(b - tb)) < best[0]):
                    best = (abs(hc.wrap(b - tb)), kp, conf)
            if best is None:
                continue
            _, kp, conf = best
            sh, _, wr = gm.ARMS[truth.arm] if truth.arm in gm.ARMS else (None, None, None)
            thr = rcfg["keypoints"]["body_kp_conf_min"]
            if sh is None or min(conf[gm.L_SHOULDER], conf[gm.R_SHOULDER], conf[sh], conf[wr]) < thr:
                continue
            width = float(np.linalg.norm(kp[gm.L_SHOULDER] - kp[gm.R_SHOULDER]))
            if width > 1e-6:
                ratios.append(float(np.linalg.norm(kp[wr] - kp[sh]) / width))
    return {"frames": len(ratios), "median": round(st.median(ratios), 3) if ratios else None,
            "p25": round(float(np.percentile(ratios, 25)), 3) if ratios else None,
            "p75": round(float(np.percentile(ratios, 75)), 3) if ratios else None}


# ---------------------------------------------------------------- the sweep and the configs

def _get(cfg: dict, path: tuple):
    for k in path[:-1]:
        cfg = cfg[k]
    return cfg[path[-1]]


def _with(cfg: dict, path: tuple, value) -> dict:
    c = copy.deepcopy(cfg)
    d = c
    for k in path[:-1]:
        d = d[k]
    d[path[-1]] = value
    return c


def sweep(runs, frames, road) -> dict:
    rcfg, ccfg, (_, v4) = gm.load_config(), cm.load_config(), hv.load_control()
    ecfg, gcfg = ev.load_config(), gd.load_config()
    out = []
    for kind, path, grid, v3 in GRIDS:
        base = {"reader": rcfg, "commander": ccfg, "control": v4}[kind]
        committed = _get(base, path)
        rows = []
        for value in grid:
            cfgs = {"reader": rcfg, "commander": ccfg, "control": v4}
            cfgs[kind] = _with(base, path, value)
            s = score(runs, frames, cfgs["reader"], cfgs["commander"], cfgs["control"],
                      "reader" if kind == "reader" else kind, road, ecfg, gcfg)
            rows.append({"value": value, **s})
        chosen, why = choose_b12(rows, committed, v3)
        out.append({"config": kind, "path": list(path), "committed": committed, "chosen": chosen, "why": why, "v3_value": v3,
                    "grid": rows})
    arm = measure_arm_ratio(runs, frames, rcfg, ccfg, ecfg, gcfg)
    return {"thresholds": out, "arm_length_in_shoulder_widths": {"committed": rcfg["point"]["arm_length_in_shoulder_widths"], **arm}}


def set_json_value(text: str, path: tuple, value) -> str:
    """Replace the number at path (nested object keys) in a JSON text, keeping every other byte."""
    start, end = 0, len(text)
    for key in path[:-1]:
        m = re.compile(r'"' + re.escape(key) + r'"\s*:\s*\{').search(text, start, end)
        if m is None:
            raise KeyError(key)
        depth, i = 0, m.end() - 1
        for j in range(i, end):
            depth += {"{": 1, "}": -1}.get(text[j], 0)
            if depth == 0:
                start, end = m.end(), j
                break
    m = re.compile(r'("' + re.escape(path[-1]) + r'"\s*:\s*)(-?[0-9.eE+]+)').search(text, start, end)
    if m is None:
        raise KeyError(path[-1])
    v = repr(float(value)) if isinstance(value, float) else str(value)
    return text[:m.start(2)] + v + text[m.end(2):]


def write_configs(result: dict, evidence: str) -> list:
    """Write every changed value into its config file(s), with a dated record; returns the changes."""
    changes = []
    edits = defaultdict(list)
    for t in result["thresholds"]:
        if t["chosen"] != t["committed"]:
            files = FILES[t["config"]] if isinstance(FILES[t["config"]], tuple) else (FILES[t["config"]],)
            for f in files:
                edits[f].append((tuple(t["path"]), t["chosen"]))
            changes.append({"config": t["config"], "path": t["path"], "old": t["committed"], "new": t["chosen"], "why": t["why"]})
    arm = result["arm_length_in_shoulder_widths"]
    if arm["median"] is not None and arm["median"] != arm["committed"]:
        edits[FILES["reader"]].append((("point", "arm_length_in_shoulder_widths"), arm["median"]))
        changes.append({"config": "reader", "path": ["point", "arm_length_in_shoulder_widths"], "old": arm["committed"], "new": arm["median"],
                        "why": "measured: median YOLO ratio, development looks, held in-plane POINT frames (AUDIT.md 14.16 item 3)"})
    for f, items in edits.items():
        p = HERE / f
        raw = p.read_bytes().decode("utf-8")
        crlf = "\r\n" in raw
        text = raw.replace("\r\n", "\n")
        for path, value in items:
            text = set_json_value(text, path, value)
        rec = (f'  "calibrated": "{date.today().isoformat()}: set on development data (sunbox_m1, sunbox_f1) by calibrate_v4.py, B12 rule '
               f'(AUDIT.md 14.11 item 3); changed: {", ".join(".".join(k) + " " + str(v) for k, v in items)}; evidence {evidence}",\n')
        text = text.replace("{\n", "{\n" + rec, 1)
        json.loads(text)
        p.write_bytes((text.replace("\n", "\r\n") if crlf else text).encode("utf-8"))
    return changes


def markdown(result: dict, changes: list) -> str:
    L = ["# v4 calibration (B12)", "", f"Sessions: {', '.join(result['sessions'])}; looks {', '.join(CALIBRATION_LOOKS)} only.", "",
         "| threshold | committed | chosen | why | grid (value: accuracy / coverage) |", "|---|---|---|---|---|"]
    for t in result["thresholds"]:
        grid = "; ".join(f"{r['value']}: {r['accuracy']} / {r['coverage']}" for r in t["grid"])
        L.append(f"| {t['config']} {'.'.join(t['path'])} | {t['committed']} | {t['chosen']} | {t['why']} | {grid} |")
    a = result["arm_length_in_shoulder_widths"]
    L += ["", f"Arm ratio (measured): median {a['median']} (p25 {a['p25']}, p75 {a['p75']}) over {a['frames']} frames; committed {a['committed']}.",
          "", "Changes written:" if changes else "No change written.", ""]
    L += [f"- {c['config']} {'.'.join(c['path'])}: {c['old']} -> {c['new']} ({c['why']})" for c in changes]
    return "\n".join(L) + "\n"


def main(argv=None) -> None:
    import decision_io as dio
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--session", nargs=2, action="append", required=True, metavar=("UNITY", "BRIDGE"))
    ap.add_argument("--write", action="store_true", help="write the chosen values into the v4 configs")
    a = ap.parse_args(argv)
    pairs = [(dio.resolve(u), dio.resolve(b)) for u, b in a.session]
    runs, frames = load(pairs)
    road = hv.load_roadmap(hv.roadmap_path(hv.load_control()[1]))
    result = sweep(runs, frames, road)
    result["sessions"] = [f"{Path(u).name} + {Path(b).name}" for u, b in pairs]
    out = dio.new_run_dir({"paths": {"output_root": "outputs"}}, "calibrate_v4")
    changes = write_configs(result, f"outputs/{out.name}") if a.write else []
    result["changes_written"] = changes
    dio.write_json(out / "report.json", result)
    dio.write_json(out / "run.json", {"git": dio.git_info(), "write": a.write})
    (out / "report.md").write_text(markdown(result, changes), encoding="utf-8")
    print(markdown(result, changes))
    print(f"Folder: {out}")


if __name__ == "__main__":
    main()
