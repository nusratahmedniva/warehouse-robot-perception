"""Why was BACK not read? Diagnosis of the B3 smoke trial (experiments_ab.md section 15 addendum 6) and the BACK geometry (report only).

Evaluation only, read-only on every input; never imported by inference code; nothing is tuned on it. Three parts:
  Q1  the asks of one worker in one session, frame by frame: the pan-tilt frames (time, processing time, people in the frame and who they
      are), worker's track, hand landmarks linked, the reader's per-frame arm cues (valid, raised, image arm length in shoulder widths,
      elbow angle, segment disagreement, point_ok) by re-running Anisha's reader (hri_perception_v4.PersonsPipeline, gesture_motion, with
      the bridge run's own config_used) on the logged model outputs, checked against the logged readings (v4_log.jsonl).
  Q2  geometry on Unity's planner export (checkpoint_check_<time>/plans.json): at every modelled ask point, the horizontal angle between
      the direction a worker would point (BACK, and every branch it can point to) and the line from the worker to the robot (the
      pan-tilt camera, at the robot's centre), per ask spot: min / median / max, and the asks within 30 and 45 deg of the camera line
      (toward the camera, away from it, either).
  Q2b the same angle measured at every real POINT ask of the development sessions (step5_sessions.json): truth (worker position, shown
      point_angle_deg while holding) and the robot pose (trail.csv), against what the reader made of it (export dialogs.csv).
The POINT cue needs the image arm length >= point.arm_length_min shoulder widths (gesture_reader.json); with the arm at
point.arm_length_in_shoulder_widths, a level arm projects to that length only when sin(angle) >= arm_length_min / arm_length_in_shoulder_widths.

Usage (repository root):
  Windows: robot_vision\\.venv\\Scripts\\python.exe finals_v4\\back_read_diagnosis_v4.py --unity <trials_development_...> --bridge <bridge_guide_...>
           --worker 7 --compare-worker 3 --export <checkpoint_check_...> [--manifest robot_vision\\outputs\\step5_sessions.json]
  macOS:   robot_vision/.venv/bin/python finals_v4/back_read_diagnosis_v4.py (same arguments, forward slashes)
Writes robot_vision/outputs/back_read_diagnosis_<time>/ (report.md, frames.csv, geometry_asks.csv, geometry_spots.csv, dev_point_asks.csv,
result.json, run_info.json); never overwrites.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import statistics
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
RV = REPO / "robot_vision"
OUT = RV / "outputs"
sys.path.insert(0, str(RV))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import numpy as np  # noqa: E402

import calibrate_v4 as cal  # noqa: E402  (its _hands only: the logged hands as the pipeline takes them)
import gesture_motion as gm  # noqa: E402
import hri_perception_v4 as hp4  # noqa: E402
import layout_search_v4 as ls  # noqa: E402


def p(rel: str) -> Path:
    q = Path(rel)
    if q.is_absolute():
        return q
    for base in (Path.cwd(), RV, REPO, OUT):
        if (base / q).exists():
            return base / q
    return RV / q


def jl(path: Path) -> list[dict]:
    return [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines() if x.strip()]


def unit(yaw_deg: float) -> tuple[float, float]:
    return math.sin(math.radians(yaw_deg)), math.cos(math.radians(yaw_deg))


def ang(a: tuple[float, float], b: tuple[float, float]) -> float:
    na, nb = math.hypot(*a), math.hypot(*b)
    if na < 1e-9 or nb < 1e-9:
        return float("nan")
    c = max(-1.0, min(1.0, (a[0] * b[0] + a[1] * b[1]) / (na * nb)))
    return math.degrees(math.acos(c))


def wrap(d: float) -> float:
    return (d + 180.0) % 360.0 - 180.0


# ---------------------------------------------------------------- Q1: the asks of one worker, frame by frame

def asks_of(bridge: Path, unity: Path, worker: int, trial: int = 1) -> list[dict]:
    """The asks Unity gave to this worker (truth: commander rows) joined with Python's asks (python_trial asks_log, by time)."""
    pt = json.loads((bridge / f"python_trial_{trial:03d}.json").read_text(encoding="utf-8"))
    truth = jl(unity / f"run_{trial:03d}" / "truth.jsonl")
    mine = [r for r in truth if r["worker_id"] == worker]
    out = []
    for j in pt["junctions"]:
        for a in j.get("asks_log", []):
            near = [r for r in mine if a["t"] - 0.2 <= r["time_s"] <= a["t"] + 0.5]
            if any(r["is_commander"] for r in near):
                out.append({"junction": j["junction"], "t_ask": a["t"], "serial": a["serial"], "robot": a["robot"],
                            "track_360": a.get("track_360"), "result": j.get("result"), "read": j.get("read"), "t_end_dialog": j.get("t_end")})
    for i, a in enumerate(out):                          # an ask's window ends at the next ask or the dialog's end
        a["t_end"] = out[i + 1]["t_ask"] if i + 1 < len(out) and out[i + 1]["junction"] == a["junction"] else a["t_end_dialog"]
    return out


def who_is(frame: dict, person: dict, truth_at: dict) -> tuple[int | None, float]:
    """The worker whose bearing (from the robot pose, pan, and the box centre) is nearest to the person's; (id, bearing error deg)."""
    u = 0.5 * (person["box"][0] + person["box"][2])
    # protocol.md: pan_deg > 0 turns the camera LEFT; yaw and image bearings are + = right
    world = frame["pose"]["yaw_deg"] - frame["pan_deg"] + math.degrees(math.atan((u - frame["cx"]) / frame["fx"]))
    rx, rz = frame["pose"]["x"], frame["pose"]["z"]
    best = (None, 999.0)
    for wid, (x, z) in truth_at.items():
        e = abs(wrap(math.degrees(math.atan2(x - rx, z - rz)) - world))
        if e < best[1]:
            best = (wid, e)
    return best


def replay_q1(bridge: Path, unity: Path, worker: int, label: str, trial: int = 1) -> tuple[list[dict], list[str], dict]:
    rcfg = json.loads((bridge / "config_used" / "gesture_reader.json").read_text(encoding="utf-8"))
    ccfg = json.loads((bridge / "config_used" / "commander.json").read_text(encoding="utf-8"))
    frames = [d for d in jl(bridge / "model_outputs.jsonl") if d.get("cam") == "pan_tilt"]
    perc = {round(float(r["time_s"]), 3): r for r in csv.DictReader(open(bridge / "perception.csv", encoding="utf-8")) if r["type"] == "frame_pan_tilt"}
    v4 = defaultdict(dict)                              # t (3 dp) -> track -> logged reading
    for d in jl(bridge / "v4_log.jsonl"):
        for q in d.get("persons", []):
            v4[round(d["t"], 2)][q["id"]] = q.get("reading") or {}
    truth = jl(unity / f"run_{trial:03d}" / "truth.jsonl")
    pos_by_t = defaultdict(dict)
    for r in truth:
        if r.get("active", True):                       # only rendered workers can be in a camera image
            pos_by_t[round(r["time_s"], 1)][r["worker_id"]] = (r["x"], r["z"])
    wrows = sorted((r for r in truth if r["worker_id"] == worker), key=lambda r: r["time_s"])
    asks = asks_of(bridge, unity, worker, trial)
    pipe = hp4.PersonsPipeline(rcfg, ccfg)
    pc = rcfg["point"]
    rows, lines = [], []
    agree = disagree = 0
    for f in frames:
        dets = [{"track_id": q["track_id"], "box": tuple(q["box"]), "kp": np.asarray([k[:2] for k in q["kp"]], float),
                 "conf": np.asarray([k[2] if k[2] is not None else 0.0 for k in q["kp"]], float)} for q in f["people"] if q["kp"]]
        hands = cal._hands(f["hands"])
        meta = {"t": f["time_s"], **{k: f[k] for k in ("fx", "fy", "cx", "cy", "width", "height")}, "pan_deg": f["pan_deg"],
                "tilt_deg": f.get("tilt_deg", 0.0), "robot_yaw_deg": f["pose"]["yaw_deg"]}
        readings = {pr.track_id: pr for pr in pipe.update(dets, hands, meta)}
        a = next((a for a in asks if a["t_ask"] - 0.3 <= f["time_s"] <= a["t_end"]), None)
        if a is None:
            continue
        tkey = round(f["time_s"], 1)
        truth_at = pos_by_t.get(tkey) or pos_by_t.get(round(tkey - 0.1, 1)) or {}
        ids = {q["track_id"]: who_is(f, q, truth_at) for q in f["people"]}
        tracks = [t for t, (wid, e) in ids.items() if wid == worker and e < 6.0]
        wr = max((r for r in wrows if r["time_s"] <= f["time_s"] + 1e-6), key=lambda r: r["time_s"], default=None)
        prc = perc.get(round(f["time_s"], 3), {})
        row = {"case": label, "ask_serial": a["serial"], "junction": a["junction"], "t": round(f["time_s"], 3),
               "t_since_ask": round(f["time_s"] - a["t_ask"], 2), "total_ms": prc.get("total_ms", ""), "pan_deg": round(f["pan_deg"], 2),
               "fov_deg": f["vertical_fov_deg"], "tilt_deg": f.get("tilt_deg", 0.0),
               "people_in_frame": " ".join(f"track {t} = worker {wid} ({e:.1f} deg)" for t, (wid, e) in ids.items()),
               "worker_phase": wr["phase"] if wr else "", "worker_true_command": wr["true_command"] if wr else "",
               "worker_point_angle_deg": wr["point_angle_deg"] if wr else "", "worker_clip": wr.get("clip", "") if wr else ""}
        if not tracks:
            row["track"] = "absent"
            rows.append(row)
            continue
        tid = tracks[0]
        pr = readings.get(tid)
        s = pipe.buffers[tid]._q[-1] if tid in pipe.buffers and pipe.buffers[tid]._q else None
        row["track"] = tid
        row["hands_linked"] = "" if s is None else ",".join(k for k, v in s.hands.items() if v is not None) or "none"
        for side in ("right", "left"):
            if s is None:
                continue
            af = gm.arm_frame(s, side, rcfg)
            fl = gm.frame_flags(s, side, af, rcfg)
            row[f"{side}_valid"] = af.valid
            row[f"{side}_raised"] = getattr(af, "raised", "")
            row[f"{side}_length_ratio"] = round(af.length_ratio, 3) if af.valid else ""
            row[f"{side}_elbow_deg"] = round(af.elbow_deg, 1) if af.valid else ""
            row[f"{side}_disagreement_deg"] = round(af.disagreement_deg, 1) if af.valid else ""
            row[f"{side}_point_ok"] = fl["point_ok"]
            why = []
            if af.valid and af.raised:
                if af.length_ratio < pc["arm_length_min"]:
                    why.append(f"length {af.length_ratio:.2f} < {pc['arm_length_min']}")
                if af.elbow_deg < pc["point_arm_extension_min_deg"]:
                    why.append(f"elbow {af.elbow_deg:.0f} < {pc['point_arm_extension_min_deg']}")
                if af.disagreement_deg > pc["segment_disagreement_max_deg"]:
                    why.append(f"disagreement {af.disagreement_deg:.0f} > {pc['segment_disagreement_max_deg']}")
            row[f"{side}_point_fails"] = "; ".join(why) if not fl["point_ok"] else ""
        if pr is not None:
            rd = pr.reading
            row.update({"reading": rd.command, "reading_why": rd.why, "valid_frames": rd.valid_frames, "n_frames": rd.n_frames})
            logged = v4[round(f["time_s"], 2)].get(tid) or {}
            if logged:
                if logged.get("command") == rd.command and logged.get("valid_frames") == rd.valid_frames:
                    agree += 1
                else:
                    disagree += 1
        rows.append(row)
    return rows, asks, {"replay_matches_log": agree, "replay_differs_from_log": disagree}


# ---------------------------------------------------------------- Q2: geometry on Unity's planner export

def q2(export: Path, rcfg: dict):
    sc = ls.load("robot_vision/configs/v4/experiments/scenarios_ab.json")
    maps = {k: ls.Map(k, v) for k, v in sc["maps"].items()}
    maps["roadmap"] = ls.Map("roadmap", ls.load("robot_vision/configs/v4/roadmap.json"))
    U = ls.load("unity/Robotics-Warehouse/WarehouseProjectURP/Assets/WarehouseRobot/Scenario/Config/experiments_ab_unity.json")
    for prop in U.get("proposals", []):
        maps[prop["name"]] = ls.Map(prop["name"], json.loads((REPO / "unity/Robotics-Warehouse/WarehouseProjectURP" / prop["file"]).read_text(encoding="utf-8")))
    plans = json.loads((export / "plans.json").read_text(encoding="utf-8"))["plans"]
    rows = []
    seen = set()
    for pl in plans:
        m = maps[pl["map"]]
        ws = {w["id"]: w for w in pl["workers"]}
        for a in pl["asks"]:
            w = ws[a["worker"]]
            wp, cam = (w["x"], w["z"]), (a["x"], a["z"])
            to_cam = (cam[0] - wp[0], cam[1] - wp[1])
            dirs = []
            if w["kind"] == "checkpoint":
                f, t = m.pos(w["from"]), m.pos(w["to"])
                back = (f[0] - t[0], f[1] - t[1])
                dirs.append(("BACK", back, "honest on a wrong branch; liar on the right branch"))
                dirs.append(("FORWARD (PROCEED)", (-back[0], -back[1]), "PROCEED: not a POINT"))
                spot = f"checkpoint {w['node']}"
            else:
                n = w["node"]
                nd = m.pos(n)
                arr = m.arrival(n)                                       # unit arrival heading (x, z)
                back = (-arr[0], -arr[1])
                branches = m.branches.get(n, {})
                if n in ("J2", "J3", "J4"):
                    how = "honest when the robot arrives on a wrong path"
                elif len(branches) <= 1:
                    how = "liar only (a node with one branch)"
                else:
                    how = "never (a liar shows a wrong valid branch)"
                dirs.append(("BACK", back, how))
                for cmd, nxt in branches.items():
                    q = m.pos(nxt)
                    dirs.append((f"POINT {cmd}" if cmd != "FORWARD" else "FORWARD (PROCEED)", (q[0] - nd[0], q[1] - nd[1]), "branch"))
                spot = f"{pl['map']} {n} slot {w['slot'] + 1}"
            for cmd, d, how in dirs:
                key = (pl["setting"], pl["seed"], pl["run"], round(a["x"], 3), round(a["z"], 3), a["worker"], cmd)
                if key in seen:
                    continue
                seen.add(key)
                g = ang(d, to_cam)
                rows.append({"setting": pl["setting"], "seed": pl["seed"], "run": pl["run"], "map": pl["map"], "spot": spot, "worker": a["worker"],
                             "command": cmd, "how": how, "ask_x": a["x"], "ask_z": a["z"], "angle_to_camera_line_deg": round(g, 1),
                             "from_line_deg": round(min(g, 180.0 - g), 1),
                             "predicted_length_ratio": round(rcfg["point"]["arm_length_in_shoulder_widths"] * math.sin(math.radians(g)), 3)})
    return rows


# ---------------------------------------------------------------- Q2b: real POINT asks of the development sessions

def q2b(manifest: Path, extra: list[dict]):
    entries = json.loads(manifest.read_text(encoding="utf-8-sig"))["sessions"] + extra
    out = []
    for e in entries:
        U, B, X = p(e["unity"]), p(e["bridge"]), p(e["export"]) if e.get("export") else None
        if X is None or not (X / "dialogs.csv").exists():
            continue
        dl = list(csv.DictReader(open(X / "dialogs.csv", encoding="utf-8")))
        cache = {}
        for r in dl:
            if r["command_shown"] != "POINT":
                continue
            trial = int(r["trial"])
            if trial not in cache:
                ptj = B / f"python_trial_{trial:03d}.json"
                tj = U / f"run_{trial:03d}" / "truth.jsonl"
                tr = U / f"run_{trial:03d}" / "trail.csv"
                if not (ptj.exists() and tj.exists() and tr.exists()):
                    cache[trial] = None
                    continue
                ptd = json.loads(ptj.read_text(encoding="utf-8"))
                asks = {a["serial"]: a for j in ptd["junctions"] for a in j.get("asks_log", [])}
                trail = [(float(x["time_s"]), float(x["x"]), float(x["z"]), float(x["yaw_deg"])) for x in csv.DictReader(open(tr, encoding="utf-8"))]
                cache[trial] = (asks, jl(tj), trail)
            if cache[trial] is None:
                continue
            asks, truth, trail = cache[trial]
            a = asks.get(int(r["serial"])) if r["serial"] else None
            if a is None:
                continue
            wid = int(r["worker"])
            hold = [x for x in truth if x["worker_id"] == wid and a["t"] - 0.2 <= x["time_s"] <= a["t"] + 8.0
                    and x["phase"] == "holding" and x["true_command"] == "POINT"]
            if not hold:
                continue
            gs = []
            for h in hold:
                ti = min(range(len(trail)), key=lambda i: abs(trail[i][0] - h["time_s"]))
                _, rx, rz, ryaw = trail[ti]
                d = unit(ryaw + h["point_angle_deg"])
                gs.append(ang(d, (rx - h["x"], rz - h["z"])))
            g = statistics.median(gs)
            out.append({"session_setting": e["setting"], "trial": trial, "junction": r["junction"], "worker": wid, "look": r["look"],
                        "direction_shown": r["direction_shown"], "truthful": r["truthful"], "command_read": r["command_read"],
                        "correct": r["correct"], "correct_direction": r["correct_direction"], "angle_to_camera_line_deg": round(g, 1),
                        "from_line_deg": round(min(g, 180.0 - g), 1)})
    return out


def summary(vals):
    return (min(vals), statistics.median(vals), max(vals)) if vals else (float("nan"),) * 3


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--unity", required=True)
    ap.add_argument("--bridge", required=True)
    ap.add_argument("--worker", type=int, required=True)
    ap.add_argument("--compare-worker", type=int, default=None)
    ap.add_argument("--export", required=True)
    ap.add_argument("--manifest", default="outputs/step5_sessions.json")
    a = ap.parse_args(argv)
    unity, bridge, export = p(a.unity), p(a.bridge), p(a.export)
    rcfg = json.loads((bridge / "config_used" / "gesture_reader.json").read_text(encoding="utf-8"))
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out = OUT / f"back_read_diagnosis_{stamp}"
    out.mkdir(parents=True, exist_ok=False)
    L = [f"# Why BACK was not read ({stamp})", "",
         f"Session `{unity.name}` + `{bridge.name}`; worker {a.worker}" + (f", compared with worker {a.compare_worker}" if a.compare_worker else "") +
         f"; planner export `{export.name}`. Reader config: the bridge run's config_used/gesture_reader.json (window {rcfg['window']['window_s']} s at "
         f"{rcfg['frame_hz']} Hz, min_valid_fraction {rcfg['window']['min_valid_fraction']}, point.arm_length_min {rcfg['point']['arm_length_min']}, "
         f"arm_length_in_shoulder_widths {rcfg['point']['arm_length_in_shoulder_widths']}). Evaluation only.", ""]

    # Q1
    frames_rows, res = [], {}
    for w, lab in ((a.worker, "target"), (a.compare_worker, "compare")):
        if w is None:
            continue
        rows, asks, chk = replay_q1(bridge, unity, w, f"worker {w}")
        frames_rows += rows
        res[f"worker_{w}"] = {"asks": asks, **chk}
        L += [f"## Q1: worker {w} ({lab}), {len(asks)} asks; replay against the log: {chk['replay_matches_log']} readings equal, "
              f"{chk['replay_differs_from_log']} differ", ""]
        for ak in asks:
            fr = [r for r in rows if r["ask_serial"] == ak["serial"]]
            seen = [r for r in fr if r.get("track") not in (None, "absent")]
            hold = [r for r in seen if r["worker_phase"] in ("gesturing", "holding")]
            ms = [float(r["total_ms"]) for r in fr if r["total_ms"] not in ("", None)]
            dt = [fr[i + 1]["t"] - fr[i]["t"] for i in range(len(fr) - 1)]
            win = [r["n_frames"] for r in hold if r.get("n_frames") is not None]
            side = max(("right", "left"), key=lambda sd: sum(1 for r in hold if r.get(f"{sd}_raised")))
            ok = sum(1 for r in hold if r.get(f"{side}_point_ok"))
            lr = [r[f"{side}_length_ratio"] for r in hold if r.get(f"{side}_raised") and r.get(f"{side}_length_ratio") != ""]
            fails = defaultdict(int)
            for r in hold:
                for x in str(r.get(f"{side}_point_fails", "")).split("; "):
                    if x:
                        fails[x.split(" ")[0]] += 1
            reads = defaultdict(int)
            for r in hold:
                reads[f"{r.get('reading')}: {r.get('reading_why')}"] += 1
            people = sorted({r["people_in_frame"] for r in fr})
            L += [f"### ask serial {ak['serial']} at {ak['junction']}, t {ak['t_ask']:.2f} s, robot ({ak['robot']['x']:.2f}, {ak['robot']['z']:.2f}) yaw "
                  f"{ak['robot']['yaw_deg']:.1f}; dialog result {ak['result']}, read {ak['read']}", "",
                  f"- (a) pan-tilt frames {len(fr)} in {ak['t_end'] - ak['t_ask']:.1f} s ({len(fr) / max(ak['t_end'] - ak['t_ask'], 1e-6):.2f}/s); frame interval "
                  f"median {statistics.median(dt) if dt else float('nan'):.3f} s; processing (perception.csv total_ms) median {statistics.median(ms) if ms else float('nan'):.0f} ms, "
                  f"max {max(ms) if ms else float('nan'):.0f} ms; worker {w} in {len(seen)} of {len(fr)} frames; pan {fr[0]['pan_deg'] if fr else ''} deg, "
                  f"vertical field of view {sorted({r['fov_deg'] for r in fr})} deg (no zoom), tilt {sorted({r['tilt_deg'] for r in fr})}; people in the frame: {people[:4]}",
                  f"- (b) frames while the worker gestured or held: {len(hold)}; frames in the reader's {rcfg['window']['window_s']} s window at those ticks: "
                  f"{sorted(set(win))} (needs {math.ceil(rcfg['window']['min_valid_fraction'] * rcfg['window']['window_s'] * rcfg['frame_hz'] - 1e-9)}); hands linked to the "
                  f"worker in {sum(1 for r in hold if r.get('hands_linked') not in ('', 'none', None))} of {len(hold)}",
                  f"- (c) {side} arm while gesturing/holding: raised in {sum(1 for r in hold if r.get(f'{side}_raised'))}, point_ok in {ok}; image arm length "
                  f"(shoulder widths) min / median / max {summary(lr)[0]:.2f} / {summary(lr)[1]:.2f} / {summary(lr)[2]:.2f} against {rcfg['point']['arm_length_min']}; "
                  f"POINT cue failures: {dict(fails) or 'none'}",
                  f"- (d) readings at those frames: {dict(reads)}", ""]
    # Q2
    g = q2(export, rcfg)
    spots = defaultdict(list)
    for r in g:
        spots[(r["spot"], r["command"], r["how"])].append(r["angle_to_camera_line_deg"])
    thr = math.degrees(math.asin(rcfg["point"]["arm_length_min"] / rcfg["point"]["arm_length_in_shoulder_widths"]))
    srows = []
    for (spot, cmd, how), v in sorted(spots.items()):
        mn, md, mx = summary(v)
        srows.append({"spot": spot, "command": cmd, "how": how, "asks": len(v), "min_deg": round(mn, 1), "median_deg": round(md, 1), "max_deg": round(mx, 1),
                      "toward_30": sum(x <= 30 for x in v), "toward_45": sum(x <= 45 for x in v), "away_30": sum(x >= 150 for x in v),
                      "away_45": sum(x >= 135 for x in v), "line_30": sum(min(x, 180 - x) <= 30 for x in v), "line_45": sum(min(x, 180 - x) <= 45 for x in v),
                      f"below_length_min_({thr:.1f}deg)": sum(min(x, 180 - x) < thr for x in v)})
    L += ["## Q2: the angle between the pointed direction and the line from the worker to the camera, at every modelled ask (Unity's plans)", "",
          f"0 deg = the arm points straight at the camera, 180 = straight away. A level arm of {rcfg['point']['arm_length_in_shoulder_widths']} shoulder widths "
          f"projects to at least arm_length_min {rcfg['point']['arm_length_min']} only when the angle is between {thr:.1f} and {180 - thr:.1f} deg "
          "(shoulders square to the camera; the worker's stance and torso turn for a large angle narrow the shoulders and change this a little).", "",
          "| spot | command | how it can be shown | asks | min / median / max (deg) | within 30 deg of the line (toward / away / either) | within 45 deg (toward / away / either) | below arm_length_min |",
          "|---|---|---|---|---|---|---|---|"]
    for s in srows:
        if s["command"] == "FORWARD (PROCEED)":
            continue
        L.append(f"| {s['spot']} | {s['command']} | {s['how']} | {s['asks']} | {s['min_deg']} / {s['median_deg']} / {s['max_deg']} | {s['toward_30']} / {s['away_30']} / {s['line_30']} | "
                 f"{s['toward_45']} / {s['away_45']} / {s['line_45']} | {s[f'below_length_min_({thr:.1f}deg)']} |")
    tot = defaultdict(lambda: [0, 0, 0])
    for r in g:
        k = "BACK (honest J2-J4 / checkpoints)" if r["command"] == "BACK" and ("honest" in r["how"]) else ("BACK (liar only)" if r["command"] == "BACK" else r["command"])
        tot[k][0] += 1
        tot[k][1] += min(r["angle_to_camera_line_deg"], 180 - r["angle_to_camera_line_deg"]) <= 30
        tot[k][2] += min(r["angle_to_camera_line_deg"], 180 - r["angle_to_camera_line_deg"]) < thr
    L += ["", "Totals over every plan: " + "; ".join(f"{k}: {v[0]} asks, {v[1]} within 30 deg of the line, {v[2]} below arm_length_min" for k, v in sorted(tot.items())), ""]
    # Q2b
    man = p(a.manifest)
    d = q2b(man, []) if man.exists() else []
    bins = [(0, 30), (30, 45), (45, 90), (90, 135), (135, 150), (150, 181)]
    L += ["## Q2b: the same angle at the real POINT asks of the development sessions (truth + trail; read = export dialogs.csv)", "",
          f"Sessions of `{man.name}`: {sorted({r['session_setting'] for r in d})}. {len(d)} POINT asks with a holding phase.", "",
          "| angle to the camera line (deg) | asks | read as POINT | correct direction |", "|---|---|---|---|"]
    for lo, hi in bins:
        sel = [r for r in d if lo <= r["angle_to_camera_line_deg"] < hi]
        L.append(f"| {lo}-{min(hi, 180)} | {len(sel)} | {sum(r['command_read'] == 'POINT' for r in sel)} | {sum(r['correct_direction'] in ('True', 'true', '1') for r in sel)} |")
    L.append("")
    by_dir = defaultdict(list)
    for r in d:
        by_dir[r["direction_shown"]].append(r["angle_to_camera_line_deg"])
    L += ["By the direction shown: " + "; ".join(f"{k}: {len(v)} asks, angle min / median / max {summary(v)[0]:.0f} / {summary(v)[1]:.0f} / {summary(v)[2]:.0f}"
                                                  for k, v in sorted(by_dir.items())), ""]

    def wcsv(fn, rs):
        if not rs:
            return
        keys = []
        for r in rs:
            for k in r:
                if k not in keys:
                    keys.append(k)
        with open(out / fn, "w", encoding="utf-8", newline="") as fh:
            wr = csv.DictWriter(fh, fieldnames=keys)
            wr.writeheader()
            wr.writerows(rs)
    wcsv("frames.csv", frames_rows)
    wcsv("geometry_asks.csv", g)
    wcsv("geometry_spots.csv", srows)
    wcsv("dev_point_asks.csv", d)
    (out / "result.json").write_text(json.dumps({"q1": res, "q2_spots": srows, "q2b": d}, indent=1, default=str), encoding="utf-8")
    (out / "report.md").write_text("\n".join(L) + "\n", encoding="utf-8")
    (out / "run_info.json").write_text(json.dumps({"created": stamp, "git_commit": ls.git_head(), "tool": "finals_v4/back_read_diagnosis_v4.py",
                                                   "unity": unity.name, "bridge": bridge.name, "export": export.name, "manifest": man.name,
                                                   "worker": a.worker, "compare_worker": a.compare_worker}, indent=1), encoding="utf-8")
    print("\n".join(L))
    print(f"\nwritten: {out.relative_to(REPO).as_posix()}")


if __name__ == "__main__":
    main()
