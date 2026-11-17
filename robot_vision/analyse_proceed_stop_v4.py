"""PROCEED against STOP: the candidates B1, C1, C2 and C1 + C2 replayed on the step-5 logs, the STOP sessions and the old-pose stand-in for D4 (AUDIT.md 16.19.2,
2026-11-17; every candidate, value and pass criterion is declared there BEFORE this ran). EVALUATION CODE ONLY: it reads the workers' true commands; inference
code never imports it. It changes nothing in the reader: the candidates are applied in this script only, by wrapping gesture_motion functions for the
duration of one replay (as analyse_false_stop_v4.candidate does).

Input: three zips, read in place with zipfile (never extracted or copied): the step-5 logs, the STOP-session logs, and the 14 Nov gesture logs (R1 and V13, old
PROCEED pose: the stand-in for D4, whose raw sessions are not available). DEVELOPMENT DATA ONLY: every run goes through the split guard before anything is computed.

Variants: 'previous reader' (before the STOP rule of 16.18.2; reference), 'current' (gesture_reader.json as it is: open hand + fingertip spread >= 1.3 + raised arm),
B1 (PROCEED needs max(floor, 0.6 x the frames received) valid frames, floor 10, and 8 as a sensitivity line), C1 (STOP also needs the palm facing the camera, from the
3D landmarks, limit from the true STOPs), C2 (while the robot is stopped, v < 0.05 m/s in the states read / approach, a STOP needs the arm still; while moving the
fast STOP rule is unchanged), C1 + C2, and B1 + C1 + C2. Measured per dataset: the PROCEED read rate (frames, and holds accepted by the dialog: 0.5 s with a gap of at most
0.3 s), the false STOPs (frames and episodes, while moving / while stopped) on PROCEED, POINT, WAIT and nothing, and on the STOP sessions criterion (a) of 16.18.2.
Also: per look and arm, sunbox_m_shirt_white + proceed_ik_01 apart, the palm-to-camera angles of the true STOPs, the frames per 2 s window by the number of people (B2),
and what blocked the PROCEED of the aborted asks (the question of bug A).

Usage (from robot_vision/):
  python analyse_proceed_stop_v4.py --step5 ~/Downloads/step5_logs_X.zip --stop ~/Downloads/stop_session_logs_X.zip --d4 ~/Downloads/anisha_gesture_logs_X.zip
Writes a new folder <output_root>/proceed_stop_v4_<time>/ with report.json, report.md, config_used/ and run.json (git commit, zip SHA-256s).
"""

from __future__ import annotations

import argparse
import bisect
import contextlib
import csv
import io
import json
import math
import statistics as st
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

import analyse_false_stop_v4 as fs
import check_stop_rule_v4 as ck
import commander_v4 as cm
import gesture_motion as gm
import hri_control as hc
import hri_perception_v4 as hp4

HERE = Path(__file__).resolve().parent
DEFAULT_CONFIG = "configs/v4/experiments/proceed_stop_check.json"
CATS = ("PROCEED", "POINT", "WAIT", "nothing")


def load_config(path: str | Path = DEFAULT_CONFIG) -> dict:
    p = Path(path)
    return json.loads((p if p.is_absolute() else HERE / p).read_text(encoding="utf-8"))


# ---------------------------------------------------------------- the palm cue (C1): the palm normal from the 3D hand landmarks

def palm_normal(world) -> np.ndarray | None:
    """Unit normal of the palm plane in the hand's world frame: (index knuckle - wrist) x (pinky knuckle - wrist); None for a degenerate hand."""
    w = np.asarray(world, float)
    n = np.cross(w[gm.INDEX_MCP] - w[gm.WRIST_LM], w[gm.PINKY_MCP] - w[gm.WRIST_LM])
    m = float(np.linalg.norm(n))
    return n / m if m > 1e-12 else None


def palm_to_camera_deg(world, side: str, sign_right: float) -> float | None:
    """Angle between the palm normal and the direction from the hand to the camera. MediaPipe's world frame has x right, y down and z away from the camera
    (configs/v4/gesture_reader.json hand_world_z_away_positive), so the camera lies at -z. The sign of the normal flips between the hands (mirror): sign_right is
    the factor of the right hand, the left hand gets its negative; it is fixed from the TRUE STOPs only (fix_sign)."""
    n = palm_normal(world)
    if n is None:
        return None
    n = n * (sign_right if side == "right" else -sign_right)
    return float(math.degrees(math.acos(float(np.clip(np.dot(n, np.array([0.0, 0.0, -1.0])), -1.0, 1.0)))))


# ---------------------------------------------------------------- variants

def variant_wrap(v: dict, rc: dict, ctx: dict):
    """Context manager applying one variant to gesture_motion for a replay. v: {'b1': {'frac', 'floor'} | None, 'palm_limit_deg': float | None, 'sign_right': float,
    'static_when_stopped': bool}. ctx['stopped'] is set by the replay before every frame."""
    orig_flags, orig_window, orig_pf = gm.frame_flags, gm._arm_window, gm.proceed_features

    def flags(s, side, af, cfg):
        out = orig_flags(s, side, af, cfg)
        if out["stop_ok"] and v.get("palm_limit_deg") is not None:
            hand = s.hands.get(side)
            w = getattr(hand, "world_xyz", None) if hand is not None else None
            if w is not None:
                ang = palm_to_camera_deg(w, side, v["sign_right"])
                if ang is not None and ang > v["palm_limit_deg"]:
                    out["stop_ok"] = False
        return out

    def window(samples, side, cfg, t_now):
        info = orig_window(samples, side, cfg, t_now)
        mode = v.get("static_when_stopped")
        if mode and ctx.get("stopped"):
            if mode == "speed":            # C2s (AUDIT.md 16.19.5): the mean wrist speed over the short stop window, while the robot is stopped
                sp = fs.wrist_speed(samples, side, cfg, t_now, cfg["window"]["stop_window_s"])
                if sp is None or sp > cfg["motion"]["still_speed_max"]:
                    info["stop_share"] = 0.0
            elif info["moving"]:           # C2 (16.19.2): the reader's own `moving` flag (wrist path over the last 1.0 s)
                info["stop_share"] = 0.0
        return info

    def proceed(samples, side, cfg, t_now):
        out = orig_pf(samples, side, cfg, t_now)
        b = v.get("b1")
        if b:
            pc = cfg["proceed"]
            n = sum(1 for s in samples if s.t >= t_now - pc["window_s"] - 1e-9)
            need = max(b["floor"], math.ceil(b["frac"] * n - 1e-9))
            out["enough"] = out["valid"] >= need
            if out["valid"] >= 2:
                out["ok"] = bool(out["enough"] and out["cycles"] >= pc["cycles_min"] - 1e-9 and out["vertical_share"] >= pc["vertical_share_min"] - 1e-9)
        return out

    @contextlib.contextmanager
    def cm_():
        gm.frame_flags, gm._arm_window, gm.proceed_features = flags, window, proceed
        try:
            yield
        finally:
            gm.frame_flags, gm._arm_window, gm.proceed_features = orig_flags, orig_window, orig_pf
    return cm_()


# ---------------------------------------------------------------- the datasets

def decision_index(logs: fs.Logs, bridge: str) -> dict:
    """{trial: ([time_s], [(v, state)])} from decisions.csv."""
    by: dict = defaultdict(lambda: ([], []))
    for r in logs.decisions(bridge):
        ts, vs = by[int(r["trial"])]
        ts.append(float(r["time_s"]))
        vs.append((abs(float(r["v"])), r["state"]))
    return dict(by)


def is_stopped(idx: dict, trial: int, t: float, v_max: float) -> bool:
    ts, vs = idx.get(trial, ([], []))
    i = bisect.bisect_right(ts, t) - 1
    if i < 0:
        return False
    v, state = vs[i]
    return bool(v < v_max and (state.startswith("read") or state.startswith("approach") or state.startswith("wait")))


class Dataset:
    def __init__(self, name: str, zip_path: str | Path, sessions: dict, cfg: dict):
        self.name, self.logs = name, fs.Logs(zip_path)
        self.cfg = {**cfg["base"], "sessions": sessions}
        self.runs, self.guard, self.sessions = fs.load_runs(self.logs, self.cfg)
        self.dec = {s: decision_index(self.logs, sc["bridge"]) for s, sc in sessions.items()}


def replay_hooked(frames: list, rc: dict, cc: dict, hook, keep_samples: bool = False) -> list:
    """fs.replay with a hook(frame) called before every frame is fed to the pipeline (it sets what a variant needs to know about the robot)."""
    pipe = hp4.PersonsPipeline(rc, cc)
    out = []
    for f in frames:
        hook(f)
        dets = [{"track_id": p["track_id"], "box": tuple(p["box"]), "kp": np.asarray([k[:2] for k in p["kp"]], float),
                 "conf": np.asarray([k[2] if k[2] is not None else 0.0 for k in p["kp"]], float)} for p in f["people"] if p["kp"]]
        meta = {"t": f["time_s"], **{k: f[k] for k in ("fx", "fy", "cx", "cy", "width", "height")}, "pan_deg": f["pan_deg"],
                "tilt_deg": f.get("tilt_deg", 0.0), "robot_yaw_deg": f["pose"]["yaw_deg"]}
        prs = pipe.update(dets, fs.hands_of(f["hands"]), meta)
        smp = {p.track_id: pipe.buffers[p.track_id].window(f["time_s"], 0.0)[-1] for p in prs} if keep_samples else {}
        out.append((f, prs, smp))
    return out


def truth_row(truth: dict, w: int, t: float) -> dict | None:
    rs = truth.get(w)
    if not rs:
        return None
    ts = [r["time_s"] for r in rs]
    i = bisect.bisect_left(ts, t)
    near = [j for j in (i - 1, i) if 0 <= j < len(rs)]
    return rs[min(near, key=lambda k: abs(ts[k] - t))] if near else None


def run_variant(ds: Dataset, variant: dict, rc: dict, cc: dict, cfg: dict) -> list[tuple]:
    """Every person-frame of every run of the dataset under one variant:
    (session, run, t, category, worker, reading command, stopped, look, arm, clip, n_people_in_frame, valid_frames)."""
    ctx = {"stopped": False}
    recs = []
    with variant_wrap(variant, rc, ctx):
        for (sname, run), d in ds.runs.items():
            idx = ds.dec[sname]

            def hook(f, idx=idx, run=run):
                ctx["stopped"] = is_stopped(idx, run, f["time_s"], cfg["stopped_speed_mps"])
            for f, prs, _ in replay_hooked(d["frames"], rc, cc, hook):
                for p in prs:
                    w, cat = fs.category_of(f, p, d["truth"], ds.cfg)
                    if cat is None:
                        continue
                    row = truth_row(d["truth"], w, f["time_s"]) if w is not None else None
                    recs.append((sname, run, f["time_s"], cat, w, p.reading.command, is_stopped(idx, run, f["time_s"], cfg["stopped_speed_mps"]),
                                 row["look"] if row else None, row.get("arm") if row else None, row.get("clip") if row else None, len(prs),
                                 p.reading.valid_frames))
    return recs


def proceed_segments(ds: Dataset) -> list[dict]:
    out = []
    for (sname, run), d in ds.runs.items():
        for w, rows in d["truth"].items():
            cur = None
            for r in sorted(rows, key=lambda r: r["time_s"]):
                if r["true_command"] == "PROCEED" and r["phase"] in ds.cfg["shown_phases"]:
                    if cur is None or r["time_s"] - cur["end"] > 0.5 + 1e-9:
                        cur = {"session": sname, "run": run, "worker": w, "look": r["look"], "arm": r.get("arm"), "clip": r.get("clip"), "start": r["time_s"], "end": r["time_s"]}
                        out.append(cur)
                    cur["end"] = r["time_s"]
    return out


def dialog_accepts(recs_of_person: list[tuple], seg: dict, mode: str, cfg: dict) -> float | None:
    """When the dialog (0.5 s hold, gap tolerance 0.3 s) would accept PROCEED in this segment, as seconds after its start, or None. mode: 'live' = frames read as STOP
    are not fed (the robot is stopped by them), 'fed' = they are fed as no-direction readings, 'paused' = as live, the clock of 'accepted within' is not used here."""
    d = hc.GestureDialog(cfg["dialog_hold_s"], 1e9, 2, cfg["dialog_max_none_gap_s"])
    d.begin_ask(seg["start"])
    for r in sorted(recs_of_person, key=lambda r: r[2]):
        if not (seg["start"] - 1e-9 <= r[2] <= seg["end"] + 1e-9):
            continue
        if r[5] == "STOP" and mode == "live":
            continue
        ev = d.update("FORWARD" if r[5] == "PROCEED" else "NONE", r[2], r[2])
        if ev == "accepted":
            return r[2] - seg["start"]
    return None


def score_variant(ds: Dataset, recs: list[tuple], segs: list[dict], cfg: dict, base_recs: list[tuple] | None = None) -> dict:
    gap = ds.cfg["episode_gap_s"]
    # PROCEED read rate
    pro_frames = [r for r in recs if r[3] == "PROCEED"]
    holds = []
    for s in segs:
        mine = [r for r in recs if r[0] == s["session"] and r[1] == s["run"] and r[4] == s["worker"] and r[3] == "PROCEED"]
        acc = dialog_accepts(mine, s, "live", cfg)
        holds.append({**{k: s[k] for k in ("session", "run", "look", "arm", "clip")}, "accepted": acc is not None, "latency_s": None if acc is None else round(acc, 2),
                      "frames": len(mine), "read": sum(1 for r in mine if r[5] == "PROCEED")})
    # false STOPs by category, moving / stopped, frames and episodes
    out = {"proceed_frames": len(pro_frames), "proceed_frames_read": sum(1 for r in pro_frames if r[5] == "PROCEED"),
           "proceed_frames_read_as_stop": sum(1 for r in pro_frames if r[5] == "STOP"),
           "holds": len(holds), "holds_accepted": sum(h["accepted"] for h in holds), "hold_detail": holds}
    fa: dict = {}
    for cat in CATS:
        cr = [r for r in recs if r[3] == cat]
        stops = [r for r in cr if r[5] == "STOP"]
        by_run: dict = defaultdict(list)
        for r in stops:
            by_run[(r[0], r[1])].append((r[2], r[6]))
        eps = [e for ev in by_run.values() for e in _episodes_with_state(ev, gap)]
        fa[cat] = {"frames": len(cr), "stop_frames": len(stops), "stop_frames_moving": sum(1 for r in stops if not r[6]), "stop_frames_stopped": sum(1 for r in stops if r[6]),
                   "episodes": len(eps), "episodes_moving": sum(1 for e in eps if not e), "episodes_stopped": sum(1 for e in eps if e)}
    out["false_stops"] = fa
    out["false_stop_total"] = {k: sum(fa[c][k] for c in CATS) for k in ("stop_frames", "stop_frames_moving", "stop_frames_stopped", "episodes", "episodes_moving", "episodes_stopped")}
    # per look and arm
    pl: dict = defaultdict(lambda: {"proceed_frames": 0, "read": 0, "stop": 0, "holds": 0, "accepted": 0})
    for r in pro_frames:
        k = f"{r[7]} / {r[8]}"
        pl[k]["proceed_frames"] += 1
        pl[k]["read"] += r[5] == "PROCEED"
        pl[k]["stop"] += r[5] == "STOP"
    for h in holds:
        k = f"{h['look']} / {h['arm']}"
        pl[k]["holds"] += 1
        pl[k]["accepted"] += h["accepted"]
    out["per_look_arm"] = {k: dict(v) for k, v in sorted(pl.items())}
    ms = [h for h in holds if h["look"] == "sunbox_m_shirt_white" and h["clip"] == "proceed_ik_01"]
    mf = [r for r in pro_frames if r[7] == "sunbox_m_shirt_white" and r[9] == "proceed_ik_01"]
    out["m_shirt_white_proceed_ik_01"] = {"holds": len(ms), "accepted": sum(h["accepted"] for h in ms), "frames": len(mf), "read": sum(1 for r in mf if r[5] == "PROCEED"),
                                          "read_as_stop": sum(1 for r in mf if r[5] == "STOP")}
    return out


def _episodes_with_state(events: list[tuple], gap: float) -> list[bool]:
    """[(t, stopped)] of one run -> one bool per episode: was the robot stopped at its first reading."""
    out, last = [], None
    for t, stopped in sorted(events):
        if last is None or t - last > gap + 1e-9:
            out.append(stopped)
        last = t
    return out


def criterion_a(ds: Dataset, recs: list[tuple], base: dict | None, cfg: dict) -> dict:
    """16.18.2 reading of (a) on the STOP sessions: each true STOP's latency; no STOP lost compared with the current reader, and every STOP the current reader reads
    within 1.0 s still read within 1.0 s."""
    kinds = {k: ck.run_kind(d["truth"], ds.cfg) for k, d in ds.runs.items()}
    segs = []
    for (sname, run), d in ds.runs.items():
        segs += ck.stop_segments(d["truth"], {**ds.cfg, "stop_gap_s": cfg["stop_gap_s"]}, sname, run, kinds[(sname, run)])
    res = []
    for s in segs:
        mine = sorted((r for r in recs if r[0] == s["session"] and r[1] == s["run"] and r[4] == s["worker"] and r[2] >= s["onset"] - 1e-9), key=lambda r: r[2])
        first = next((r[2] - s["onset"] for r in mine if r[5] == "STOP" and r[3] == "STOP" and r[2] <= s["onset"] + cfg["within_s"] + 1e-9), None)
        later = next((r[2] - s["onset"] for r in mine if r[5] == "STOP" and r[2] <= s["end"] + 1e-9), None)
        res.append({"session": s["session"], "run": s["run"], "kind": s["kind"], "look": s["look"], "arm": s["arm"], "within": first, "any": later,
                    "robot_stopped_at_onset": is_stopped(ds.dec[s["session"]], s["run"], s["onset"], cfg["stopped_speed_mps"])})
    n = len(res)
    out = {"stops": n, "within_1s": sum(1 for r in res if r["within"] is not None), "read_at_all": sum(1 for r in res if r["any"] is not None),
           "held": [sum(1 for r in res if r["kind"] == "held_stop" and r["within"] is not None), sum(1 for r in res if r["kind"] == "held_stop")],
           "driving": [sum(1 for r in res if r["kind"] == "driving_stop" and r["within"] is not None), sum(1 for r in res if r["kind"] == "driving_stop")],
           "detail": res}
    if base is not None:
        b = base["detail"]
        out["lost_vs_current"] = sum(1 for x, y in zip(res, b) if y["any"] is not None and x["any"] is None)
        out["lost_from_the_1s_set"] = sum(1 for x, y in zip(res, b) if y["within"] is not None and x["within"] is None)
        later = [(x["any"] - y["any"]) for x, y in zip(res, b) if x["any"] is not None and y["any"] is not None]
        out["read_later_than_current"] = sum(1 for d in later if d > 1e-9)
        out["later_median_s"] = round(st.median([d for d in later if d > 1e-9]), 2) if any(d > 1e-9 for d in later) else 0.0
        out["non_inferior"] = bool(out["lost_vs_current"] == 0 and out["lost_from_the_1s_set"] == 0)
    out["by_robot_state"] = {}
    for label, flag in (("moving", False), ("stopped", True)):
        idx = [i for i, r in enumerate(res) if r["robot_stopped_at_onset"] == flag]
        part = {"stops": len(idx), "within_1s": sum(1 for i in idx if res[i]["within"] is not None), "lost_altogether": sum(1 for i in idx if res[i]["any"] is None)}
        if base is not None:
            b = base["detail"]
            part["lost_vs_current"] = sum(1 for i in idx if b[i]["any"] is not None and res[i]["any"] is None)
            part["lost_from_the_1s_set"] = sum(1 for i in idx if b[i]["within"] is not None and res[i]["within"] is None)
            lat = [res[i]["any"] - b[i]["any"] for i in idx if res[i]["any"] is not None and b[i]["any"] is not None]
            part["read_later_than_current"] = sum(1 for d in lat if d > 1e-9)
            part["later_median_s"] = round(st.median([d for d in lat if d > 1e-9]), 2) if any(d > 1e-9 for d in lat) else 0.0
        out["by_robot_state"][label] = part
    return out


def moving_identical(recs: list[tuple], base: list[tuple]) -> dict:
    """C2: the readings while the robot is moving must equal the current reader's (the fast STOP rule is unchanged while moving)."""
    a = {(r[0], r[1], round(r[2], 4), r[4]): r[5] for r in base if not r[6]}
    diff = sum(1 for r in recs if not r[6] and a.get((r[0], r[1], round(r[2], 4), r[4])) not in (None, r[5]))
    return {"moving_frames": sum(1 for r in recs if not r[6]), "different_readings": diff}


# ---------------------------------------------------------------- the palm angles of the true STOPs (C1 limit and sign)

def true_stop_palm_angles(ds: Dataset, rc: dict, cc: dict, cfg: dict) -> dict:
    """The angle between the palm normal and the direction to the camera on every frame of every true STOP with a hand linked, for both signs of the normal, by side and
    held / driving. The sign of the right hand is the one with the median angle of the held right-arm STOPs below 90 degrees; the left hand uses the opposite sign
    and its held STOPs must agree (below 90), else the cue is not usable. Derived from the true STOPs only."""
    kinds = {k: ck.run_kind(d["truth"], ds.cfg) for k, d in ds.runs.items()}
    raw: dict = defaultdict(list)                            # (side, kind) -> [angle with sign +1]
    for (sname, run), d in ds.runs.items():
        for f, prs, smp in replay_hooked(d["frames"], rc, cc, lambda f: None, keep_samples=True):
            for p in prs:
                w, cat = fs.category_of(f, p, d["truth"], ds.cfg)
                if cat != "STOP":
                    continue
                for side in gm.ARMS:
                    h = smp[p.track_id].hands.get(side) if p.track_id in smp else None
                    wl = getattr(h, "world_xyz", None) if h is not None else None
                    if wl is None:
                        continue
                    row = truth_row(d["truth"], w, f["time_s"])
                    if row is None or row.get("arm") != side:
                        continue
                    ang = palm_to_camera_deg(wl, side, 1.0)
                    if ang is not None:
                        raw[(side, kinds[(sname, run)])].append(ang)                                      # under sign +1 for the right hand (the left hand mirrored)
    def med(side, kind):
        v = raw.get((side, kind), [])
        return st.median(v) if v else None
    mr = med("right", "held_stop")
    ml_plus = med("left", "held_stop")
    # sign +1 for the right hand gives the right median mr; sign -1 gives 180 - mr. Left with +1 mirrored gives ml_plus (already mirrored above)
    sign = 1.0 if (mr is not None and mr < 90.0) else -1.0
    out = {"sign_right": sign, "median_right_held_deg_sign_plus": mr, "median_left_held_deg_sign_plus": ml_plus, "angles": {}}
    allv = []
    for (side, kind), v in sorted(raw.items()):
        a = v if sign > 0 else [180.0 - x for x in v]
        allv += a
        out["angles"][f"{side} / {kind}"] = {"n": len(a), "p01": round(float(np.percentile(a, 1)), 1), "p50": round(float(np.percentile(a, 50)), 1),
                                              "p95": round(float(np.percentile(a, 95)), 1), "p99": round(float(np.percentile(a, 99)), 1), "max": round(max(a), 1)}
    if allv:
        p99 = float(np.percentile(allv, 99))
        out["all_true_stop_frames"] = {"n": len(allv), "p50": round(float(np.percentile(allv, 50)), 1), "p99": round(p99, 1), "max": round(max(allv), 1)}
        out["limit_deg"] = float(min(cfg["palm_limit_cap_deg"], math.ceil(p99 / cfg["palm_limit_step_deg"]) * cfg["palm_limit_step_deg"]))
    both = [out["angles"].get(f"{s} / held_stop") for s in ("right", "left")]
    out["usable"] = bool(all(b is not None and b["p50"] < 90.0 for b in both))
    return out


# ---------------------------------------------------------------- B2 and the aborted asks

def b2_counts(ds: Dataset) -> dict:
    """Frames the reader received per 2 s window of one person by the number of people in view, and hands per frame (B2: a replay cannot time the hand model)."""
    per: dict = defaultdict(list)
    hands = Counter()
    nframes = 0
    for (sname, run), d in ds.runs.items():
        frames = d["frames"]
        ts = [f["time_s"] for f in frames]
        for i, f in enumerate(frames):
            nframes += 1
            hands[len(f["hands"])] += 1
            j = bisect.bisect_left(ts, f["time_s"] - 2.0)
            per[min(len(f["people"]), 3)].append(i + 1 - j)
    return {"frames": nframes, "hands_per_frame": dict(sorted(hands.items())),
            "frames_per_2s_window_by_people": {str(k): {"n": len(v), "median": st.median(v), "p10": float(np.percentile(v, 10))} for k, v in sorted(per.items())}}


def aborted_asks(ds: Dataset, recs: list[tuple], cfg: dict) -> list[dict]:
    """For every ask of the dataset (decisions.csv: the state 'ask' begins one) that ends without PROCEED being accepted, what the frames of the gesturing worker were in
    its 5 s window: read as PROCEED, as STOP, NONE, or no frame at all. The question of bug A: how many of these are lost to STOP frames?"""
    out = []
    for sname, idx in ds.dec.items():
        for run, (ts, vs) in idx.items():
            starts = [ts[i] for i in range(1, len(ts)) if vs[i][1].startswith("ask") and not vs[i - 1][1].startswith("ask")]
            for t0 in starts:
                win = [r for r in recs if r[0] == sname and r[1] == run and t0 <= r[2] <= t0 + cfg["ask_window_s"] and r[3] == "PROCEED"]
                if not win:
                    continue
                w = Counter(r[4] for r in win).most_common(1)[0][0]
                mine = sorted((r for r in win if r[4] == w), key=lambda r: r[2])
                seg = {"start": mine[0][2], "end": mine[-1][2]}
                acc = {m: dialog_accepts(mine, seg, m, cfg) for m in ("live", "fed")}
                out.append({"session": sname, "run": run, "t0": round(t0, 2), "frames": len(mine), "proceed": sum(r[5] == "PROCEED" for r in mine),
                            "stop": sum(r[5] == "STOP" for r in mine), "none": sum(r[5] not in ("PROCEED", "STOP") for r in mine),
                            "accepted_live": acc["live"] is not None, "accepted_if_stop_frames_were_fed": acc["fed"] is not None})
    return out


# ---------------------------------------------------------------- everything

def variants(cfg: dict, palm: dict | None) -> list[dict]:
    b1 = {"frac": cfg["b1"]["frac"], "floor": cfg["b1"]["floor"]}
    b1s = {"frac": cfg["b1"]["frac"], "floor": cfg["b1"]["floor_sensitivity"]}
    pl = palm["limit_deg"] if palm and palm.get("usable") and palm.get("limit_deg") else None
    sg = palm["sign_right"] if palm else 1.0
    c1 = {"palm_limit_deg": pl, "sign_right": sg}
    c2 = {"static_when_stopped": True}
    return [
        {"name": "current reader", "key": "current", "v": {}},
        {"name": "previous reader (before 16.18.2)", "key": "previous", "v": {}, "reader": "previous"},
        {"name": f"B1 floor {b1['floor']}", "key": "b1", "v": {"b1": b1}},
        {"name": f"B1 floor {b1s['floor']} (sensitivity)", "key": "b1s", "v": {"b1": b1s}},
        {"name": f"C1 palm <= {pl} deg" if pl else "C1 palm (not usable)", "key": "c1", "v": c1},
        {"name": "C2 stopped: STOP needs a still arm", "key": "c2", "v": c2},
        {"name": "C1 + C2", "key": "c1c2", "v": {**c1, **c2}},
        {"name": "B1 + C1 + C2", "key": "all", "v": {"b1": b1, **c1, **c2}},
    ]


def variants_round2(cfg: dict) -> list[dict]:
    """The second table (AUDIT.md 16.19.5, declared before it was computed): the current reader, C2 (the `moving` flag) and C2s (the 0.3 s window), each without and with B1
    floor 10. C1 is dropped."""
    b1 = {"frac": cfg["b1"]["frac"], "floor": cfg["b1"]["floor"]}
    c2, c2s = {"static_when_stopped": True}, {"static_when_stopped": "speed"}
    return [
        {"name": "current reader", "key": "current", "v": {}},
        {"name": "C2 (moving flag, 1.0 s), while stopped", "key": "c2", "v": c2},
        {"name": "C2s (0.3 s window), while stopped", "key": "c2s", "v": c2s},
        {"name": "current + B1 floor 10", "key": "current_b1", "v": {"b1": b1}},
        {"name": "C2 + B1 floor 10", "key": "c2_b1", "v": {"b1": b1, **c2}},
        {"name": "C2s + B1 floor 10", "key": "c2s_b1", "v": {"b1": b1, **c2s}},
    ]


def analyse(step5: str, stop: str, d4: str, cfg: dict, progress=None, round2: bool = False) -> dict:
    cc = cm.load_config()
    rc_now, rc_prev = gm.load_config(), fs.live_reader_config()
    sets = {"S5": Dataset("S5", step5, cfg["sessions"]["S5"], cfg), "STOP": Dataset("STOP", stop, cfg["sessions"]["STOP"], cfg),
            "D4*": Dataset("D4*", d4, cfg["sessions"]["D4*"], cfg)}
    rep: dict = {"zips": {k: {"name": Path(p).name, "sha256": sets[k].logs.sha256()} for k, p in (("S5", step5), ("STOP", stop), ("D4*", d4))},
                 "guard_all_development": all(set(d.guard.values()) == {"development"} for d in sets.values()),
                 "datasets": {k: {"runs": len(d.runs), "frames": sum(len(x["frames"]) for x in d.runs.values())} for k, d in sets.items()}}
    palm = None
    if not round2:
        palm = true_stop_palm_angles(sets["STOP"], rc_now, cc, cfg)
        rep["palm_true_stops"] = palm
        if progress:
            progress("palm angles")
    segs = {k: proceed_segments(d) for k, d in sets.items()}
    res: dict = {}
    base_recs: dict = {}
    for var in (variants_round2(cfg) if round2 else variants(cfg, palm)):
        rc = rc_prev if var.get("reader") == "previous" else rc_now
        res[var["key"]] = {"name": var["name"]}
        for k, d in sets.items():
            recs = run_variant(d, var["v"], rc, cc, cfg)
            if var["key"] == "current":
                base_recs[k] = recs
            sc = score_variant(d, recs, segs[k], cfg)
            base_a = res.get("current", {}).get("STOP", {}).get("a")
            sc["a"] = criterion_a(d, recs, base_a if k == "STOP" else None, cfg) if k == "STOP" else {"stops": 0, "note": "no true STOP in this dataset: criterion (a) not evaluable"}
            if var["key"] in ("c2", "c2s", "c1c2", "all", "c2_b1", "c2s_b1") and k in base_recs:
                sc["moving_identical_to_current"] = moving_identical(recs, base_recs[k])
            if var["key"] == "current" and k == "S5" and not round2:
                sc["aborted_asks"] = aborted_asks(d, recs, cfg)
            res[var["key"]][k] = sc
        if progress:
            progress(var["name"])
    rep["variants"] = res
    if not round2:
        rep["b2"] = {k: b2_counts(sets[k]) for k in ("S5", "D4*")}
    return rep


def _cell_prc(sc: dict) -> str:
    return f"{sc['holds_accepted']}/{sc['holds']} holds; {sc['proceed_frames_read']}/{sc['proceed_frames']} fr ({100 * sc['proceed_frames_read'] / max(1, sc['proceed_frames']):.0f} %)"


def _cell_fs(sc: dict) -> str:
    t = sc["false_stop_total"]
    return f"{t['stop_frames']} fr / {t['episodes']} ep (moving {t['stop_frames_moving']}/{t['episodes_moving']}, stopped {t['stop_frames_stopped']}/{t['episodes_stopped']})"


def _cell_a(a: dict) -> str:
    s = f"{a['within_1s']}/{a['stops']} within 1.0 s"
    if "lost_vs_current" in a:
        s += f"; lost {a['lost_vs_current']}, lost from the 1.0 s set {a['lost_from_the_1s_set']}, later {a['read_later_than_current']} (median +{a['later_median_s']} s)"
    return s


def _cell_state(a: dict, state: str) -> str:
    x = a["by_robot_state"][state]
    s = f"{x['within_1s']}/{x['stops']} within 1.0 s; lost altogether {x['lost_altogether']}"
    if "lost_from_the_1s_set" in x:
        s += f"; lost from the 1.0 s set {x['lost_from_the_1s_set']}, later {x['read_later_than_current']} (median +{x['later_median_s']} s)"
    return s


def markdown2(rep: dict, cfg: dict) -> str:
    V = rep["variants"]
    L = ["# C2 and C2s against the current reader, with and without B1 floor 10 (AUDIT.md 16.19.5)", "",
         "Zips (read in place): " + "; ".join(f"{k} `{v['name']}` (SHA-256 `{v['sha256'][:16]}...`)" for k, v in rep["zips"].items()) +
         f". Development looks and clips only (guard passed: {rep['guard_all_development']}). **No reader value was changed.** D4* = R1 and V13 of the 14 Nov zip (old pose).", "",
         "Criterion (a) is split by the robot's state at the first shown truth row of each STOP (stopped = v < 0.05 m/s in read, approach, wait). S5 and D4* hold no true STOP: (a) is not evaluable there. "
         "False STOPs = frames / episodes (while moving / stopped) on PROCEED, POINT, WAIT and nothing.", "",
         "| reader | (a) STOPs given while the robot MOVED | (a) STOPs given while it STOOD STILL | STOP sessions false STOPs | STOP sessions PROCEED | S5 false STOPs | S5 PROCEED | D4* false STOPs | D4* PROCEED |",
         "|---|---|---|---|---|---|---|---|---|"]
    for v in V.values():
        L.append(f"| {v['name']} | {_cell_state(v['STOP']['a'], 'moving')} | {_cell_state(v['STOP']['a'], 'stopped')} | {_cell_fs(v['STOP'])} | {_cell_prc(v['STOP'])} | "
                 f"{_cell_fs(v['S5'])} | {_cell_prc(v['S5'])} | {_cell_fs(v['D4*'])} | {_cell_prc(v['D4*'])} |")
    a = V["current"]["STOP"]["a"]
    L += ["", f"STOPs in the STOP sessions: {a['stops']} ({a['by_robot_state']['moving']['stops']} given while the robot moved, {a['by_robot_state']['stopped']['stops']} while it stood still).", "",
          "## C2 and C2s: the readings while the robot moves equal the current reader's", ""]
    for key in ("c2", "c2s", "c2_b1", "c2s_b1"):
        for k in ("S5", "STOP", "D4*"):
            x = V[key][k].get("moving_identical_to_current")
            if x:
                L.append(f"- {V[key]['name']}, {k}: {x['different_readings']} different readings in {x['moving_frames']} moving frames")
    return "\n".join(L) + "\n"


def markdown(rep: dict, cfg: dict) -> str:
    V = rep["variants"]
    L = ["# PROCEED against STOP: B1, C1, C2 on the step-5 logs, the STOP sessions and the D4 stand-in (AUDIT.md 16.19.2)", "",
         "Zips (read in place): " + "; ".join(f"{k} `{v['name']}` (SHA-256 `{v['sha256'][:16]}...`)" for k, v in rep["zips"].items()) +
         f". Development looks and clips only (guard passed: {rep['guard_all_development']}). **No reader value was changed.** D4* = R1 and V13 of the 14 Nov zip (old PROCEED pose): the raw D4 sessions are not available.", "",
         "Datasets: " + "; ".join(f"{k} {v['runs']} runs, {v['frames']} pan-tilt frames" for k, v in rep["datasets"].items()) + ".", "",
         "## The table", "",
         "PROCEED read rate = holds accepted by the dialog (0.5 s, gap <= 0.3 s) / holds, and PROCEED frames read as PROCEED. False STOPs = STOP readings on PROCEED, POINT, WAIT and nothing: frames / stop episodes "
         "(while the robot was moving / stopped, v < 0.05 m/s in read, approach, wait). (a) = criterion (a) of 16.18.2 on the STOP sessions against the current reader.", "",
         "| variant | S5 PROCEED read | S5 false STOPs | STOP sessions PROCEED read | STOP sessions false STOPs | STOP sessions (a) | D4* PROCEED read | D4* false STOPs |", "|---|---|---|---|---|---|---|---|"]
    for k, v in V.items():
        L.append(f"| {v['name']} | {_cell_prc(v['S5'])} | {_cell_fs(v['S5'])} | {_cell_prc(v['STOP'])} | {_cell_fs(v['STOP'])} | {_cell_a(v['STOP']['a'])} | {_cell_prc(v['D4*'])} | {_cell_fs(v['D4*'])} |")
    p = rep["palm_true_stops"]
    L += ["", "## C1: the palm-to-camera angle of the TRUE STOPs (STOP sessions; sign fixed from the held STOPs, limit from the true STOPs only)", "",
          f"Sign of the right hand {p['sign_right']:+.0f} (median right held STOP with sign +1: {p['median_right_held_deg_sign_plus']}, left {p['median_left_held_deg_sign_plus']}); usable: {p['usable']}; "
          f"limit = {p.get('limit_deg')} deg (smallest multiple of {cfg['palm_limit_step_deg']} at or above the 99th percentile, at most {cfg['palm_limit_cap_deg']}).", "",
          "| side / kind | frames | p01 | median | p95 | p99 | max |", "|---|---|---|---|---|---|---|"]
    for k, a in p["angles"].items():
        L.append(f"| {k} | {a['n']} | {a['p01']} | {a['p50']} | {a['p95']} | {a['p99']} | {a['max']} |")
    L += ["", "## Per look and arm, PROCEED frames read as PROCEED / read as STOP / total, and holds accepted (S5)", "",
          "| look / arm | " + " | ".join(v["name"] for v in V.values()) + " |", "|---|" + "---|" * len(V)]
    keys = sorted({k for v in V.values() for k in v["S5"]["per_look_arm"]})
    for k in keys:
        cells = []
        for v in V.values():
            x = v["S5"]["per_look_arm"].get(k)
            cells.append("-" if not x else f"{x['read']}/{x['stop']}/{x['proceed_frames']}; {x['accepted']}/{x['holds']}")
        L.append(f"| {k} | " + " | ".join(cells) + " |")
    L += ["", "## sunbox_m_shirt_white + proceed_ik_01 (S5), apart", "", "| variant | holds accepted | PROCEED frames read as PROCEED / as STOP / total |", "|---|---|---|"]
    for v in V.values():
        m = v["S5"]["m_shirt_white_proceed_ik_01"]
        L.append(f"| {v['name']} | {m['accepted']}/{m['holds']} | {m['read']} / {m['read_as_stop']} / {m['frames']} |")
    L += ["", "## C2: readings while moving equal the current reader's", ""]
    for key in ("c2", "c1c2", "all"):
        for k in ("S5", "STOP", "D4*"):
            x = V[key][k].get("moving_identical_to_current")
            if x:
                L.append(f"- {V[key]['name']}, {k}: {x['different_readings']} different readings in {x['moving_frames']} moving frames")
    L += ["", "## B2: frames per 2 s window by the number of people in view, hands per frame", ""]
    for k, b in rep["b2"].items():
        L.append(f"- {k}: hands per frame {b['hands_per_frame']}; frames per 2 s window by people in view (3 = three or more): " +
                 "; ".join(f"{n} people: median {x['median']}, p10 {x['p10']:.0f} (n {x['n']})" for n, x in b["frames_per_2s_window_by_people"].items()))
    aa = V["current"]["S5"]["aborted_asks"]
    unacc = [a for a in aa if not a["accepted_live"]]
    L += ["", "## What blocked PROCEED in the asks of S5 (bug A): the current reader's frames of the gesturing worker in each ask's 5 s window", "",
          f"{len(aa)} asks with PROCEED frames; {len(unacc)} not accepted by the live dialog; of those, accepted if the STOP frames were fed to the dialog as no-direction readings: "
          f"{sum(a['accepted_if_stop_frames_were_fed'] for a in unacc)}; frames in them read as PROCEED / STOP / other: {sum(a['proceed'] for a in unacc)} / {sum(a['stop'] for a in unacc)} / {sum(a['none'] for a in unacc)}."]
    return "\n".join(L) + "\n"


def main(argv=None) -> None:
    import decision_io as dio

    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--step5", required=True)
    ap.add_argument("--stop", required=True)
    ap.add_argument("--d4", required=True)
    ap.add_argument("--config", default=DEFAULT_CONFIG)
    ap.add_argument("--round2", action="store_true", help="the second table of AUDIT.md 16.19.5: C2 and C2s, with and without B1 floor 10 (no palm cue)")
    a = ap.parse_args(argv)
    cfg_path = dio.resolve(a.config)
    cfg = load_config(cfg_path)
    rep = analyse(*(str(Path(x).expanduser()) for x in (a.step5, a.stop, a.d4)), cfg, progress=lambda n: print("  done:", n, flush=True), round2=a.round2)
    md = markdown2 if a.round2 else markdown
    out = dio.new_run_dir({"paths": {"output_root": "outputs"}}, "proceed_stop_v4_round2" if a.round2 else "proceed_stop_v4")
    (out / "config_used").mkdir()
    for p in (cfg_path, dio.resolve(gm.DEFAULT_CONFIG), dio.resolve(cm.DEFAULT_CONFIG)):
        (out / "config_used" / p.name).write_bytes(p.read_bytes())
    dio.write_json(out / "report.json", rep)
    (out / "report.md").write_text(md(rep, cfg), encoding="utf-8")
    dio.write_json(out / "run.json", {"git": dio.git_info(), "zips": rep["zips"]})
    print(md(rep, cfg))
    print(f"Folder: {out}")


if __name__ == "__main__":
    main()
