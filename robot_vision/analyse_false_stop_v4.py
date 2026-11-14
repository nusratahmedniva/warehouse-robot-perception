"""The false STOP of the live reader (AUDIT.md 16.14, item 1 of the decisions of 2026-11-14). EVALUATION CODE ONLY: it reads the workers' true
commands (truth.jsonl); inference code never imports it. It changes nothing in the reader: the candidate cues are applied in this script only,
by wrapping two functions of gesture_motion for the duration of one replay.

Input: the zip of Nusrat's gesture logs (read in place with zipfile, never extracted or copied): per session a bridge run folder
(decisions.csv, model_outputs.jsonl, v4_log.jsonl) and the Unity session folder (run_###/truth.jsonl). The session folder names are in
configs/v4/experiments/false_stop_analysis.json. DEVELOPMENT DATA ONLY: every run's looks and clips go through data_splits_v4.guard_run before
anything is computed (SystemExit on a test look or clip, an unlisted name or a mix).

What it does
- replays the live reader on the logged pan-tilt frames (hri_perception_v4.PersonsPipeline, the current gesture_reader.json) and checks the replay against
  the STOP rows of decisions.csv;
- (a) the stops while driving with nothing shown: which person, which hand, which cues (finger ratios, spread, MediaPipe label, arm raised or not);
- (c) STOP readings on PROCEED, on POINT, on nothing shown and on a true STOP (none is in the data), before and after, for each candidate cue alone
  (a grid of values) and combined: the palm normal facing the camera, the STOP hand static over the window, the spread between the fingertips.

Per person and frame a worker is matched by bearing (as hri_eval_dev_v4: within match_bearing_deg, strictly nearer than the next) and the
category is what that worker shows at that time: PROCEED, POINT (phases gesturing / holding), "nothing" (NONE, idle, start_delay), or "unmatched" (no
worker within the tolerance). Frames of the phase "returning" are left out.

Usage (from robot_vision/):
  python analyse_false_stop_v4.py --zip ~/Downloads/anisha_gesture_logs_20261114_143539.zip [--config configs/v4/experiments/false_stop_analysis.json]
Writes a new folder <output_root>/false_stop_analysis_v4_<time>/ with report.json, report.md, config_used/ and run.json (git commit, zip SHA-256).
"""

from __future__ import annotations

import argparse
import bisect
import contextlib
import csv
import hashlib
import io
import json
import math
import statistics as st
import zipfile
from collections import Counter, defaultdict
from pathlib import Path
from types import SimpleNamespace

import numpy as np

import commander_v4 as cm
import data_splits_v4 as ds
import gesture_motion as gm
import hri_eval_dev_v4 as ev
import hri_perception_v4 as hp4

HERE = Path(__file__).resolve().parent
DEFAULT_CONFIG = "configs/v4/experiments/false_stop_analysis.json"
CATEGORIES = ("PROCEED", "POINT", "nothing", "unmatched")


def load_config(path: str | Path = DEFAULT_CONFIG) -> dict:
    p = Path(path)
    return json.loads((p if p.is_absolute() else HERE / p).read_text(encoding="utf-8"))


# ---------------------------------------------------------------- the candidate cues (pure functions of the 21 pixel landmarks)

def palm_facing(lm, side: str) -> float:
    """Signed sine of the angle between wrist -> index knuckle and wrist -> pinky knuckle; POSITIVE when the PALM faces the camera. For a person
    facing the camera the thumb side (index knuckle) of a right hand with the palm toward the camera is at the image right: the image cross
    product is then negative, so the right hand (-) and the left hand (+) are signed opposite. `side` is the person's own side."""
    lm = np.asarray(lm, float)
    v1, v2 = lm[gm.INDEX_MCP] - lm[gm.WRIST_LM], lm[17] - lm[gm.WRIST_LM]
    n = float(np.linalg.norm(v1) * np.linalg.norm(v2))
    if n < 1e-9:
        return 0.0
    cross = float(v1[0] * v2[1] - v1[1] * v2[0])
    return (-cross if side == "right" else cross) / n


def fingertip_spread(lm) -> float:
    """Distance index tip to pinky tip over distance index knuckle to pinky knuckle: about 1 for fingers together, larger for a fan."""
    lm = np.asarray(lm, float)
    knuckles = float(np.linalg.norm(lm[gm.INDEX_MCP] - lm[17]))
    return float(np.linalg.norm(lm[gm.INDEX_TIP] - lm[gm.PINKY_TIP]) / knuckles) if knuckles > 1e-9 else 0.0


def wrist_speed(samples, side: str, cfg: dict, t_now: float, window_s: float) -> float | None:
    """Mean speed of the wrist landmark over the last window_s (torso lengths per second); None when fewer than two samples with the
    hand linked or no torso."""
    pts = []
    for s in samples:
        h = s.hands.get(side)
        if h is None or s.t < t_now - window_s - 1e-9:
            continue
        tf = gm.torso_frame(s.kp, s.conf, cfg["keypoints"]["body_kp_conf_min"])
        if tf is None:
            return None
        pts.append((s.t, np.asarray(h.landmarks_px, float)[gm.WRIST_LM], tf[0]))
    if len(pts) < 2 or pts[-1][0] - pts[0][0] < 1e-6:
        return None
    path = sum(float(np.linalg.norm(b[1] - a[1])) / (0.5 * (a[2] + b[2])) for a, b in zip(pts, pts[1:]))
    return path / (pts[-1][0] - pts[0][0])


@contextlib.contextmanager
def candidate(variant: dict, rc: dict):
    """Apply a variant to the reader for the duration of the block: {'palm': min value | None, 'spread': min value | None, 'static': None |
    'arm_moving' | 'speed_stop_window', 'raised': True | None (the reader's own arm-raised flag; an extra, not one of the three)}.
    gesture_motion is restored afterwards; nothing is written anywhere."""
    orig_flags, orig_window = gm.frame_flags, gm._arm_window

    def flags(s, side, af, cfg):
        out = orig_flags(s, side, af, cfg)
        hand = s.hands.get(side)
        if out["stop_ok"] and variant.get("raised") and not (af.valid and af.raised):
            out["stop_ok"] = False
        if out["stop_ok"] and hand is not None:
            lm = np.asarray(hand.landmarks_px, float)
            if variant.get("palm") is not None and palm_facing(lm, side) < variant["palm"]:
                out["stop_ok"] = False
            if variant.get("spread") is not None and fingertip_spread(lm) < variant["spread"]:
                out["stop_ok"] = False
        return out

    def window(samples, side, cfg, t_now):
        info = orig_window(samples, side, cfg, t_now)
        mode = variant.get("static")
        if mode == "arm_moving" and info["moving"]:
            info["stop_share"] = 0.0
        elif mode == "speed_stop_window":
            v = wrist_speed(samples, side, cfg, t_now, cfg["window"]["stop_window_s"])
            if v is None or v > cfg["motion"]["still_speed_max"]:
                info["stop_share"] = 0.0
        return info

    gm.frame_flags, gm._arm_window = flags, window
    try:
        yield
    finally:
        gm.frame_flags, gm._arm_window = orig_flags, orig_window


# ---------------------------------------------------------------- the zip (read in place)

class Logs:
    def __init__(self, zip_path: str | Path):
        self.path = Path(zip_path)
        self.z = zipfile.ZipFile(self.path)
        self.root = self.z.namelist()[0].split("/")[0] + "/"

    def sha256(self) -> str:
        h = hashlib.sha256()
        with self.path.open("rb") as f:
            for block in iter(lambda: f.read(1 << 20), b""):
                h.update(block)
        return h.hexdigest()

    def lines(self, name: str):
        with self.z.open(self.root + name) as f:
            for line in f:
                if line.strip():
                    yield json.loads(line)

    def decisions(self, bridge: str) -> list[dict]:
        with self.z.open(f"{self.root}{bridge}/decisions.csv") as f:
            return list(csv.DictReader(io.TextIOWrapper(f, encoding="utf-8")))

    def runs(self, unity: str) -> list[int]:
        pre = f"{self.root}{unity}/run_"
        return sorted(int(n[len(pre):len(pre) + 3]) for n in self.z.namelist() if n.startswith(pre) and n.endswith("truth.jsonl"))

    def truth(self, unity: str, run: int) -> dict[int, list]:
        by: dict[int, list] = defaultdict(list)
        for r in self.lines(f"{unity}/run_{run:03d}/truth.jsonl"):
            by[r["worker_id"]].append(r)
        return by


def guard(truth: dict) -> str:
    """Development data only: the looks and clips of a run through the split guard of the v4 study."""
    rows = [r for rs in truth.values() for r in rs]
    return ds.guard_run({r["look"] for r in rows}, {r["clip"] for r in rows if r.get("clip")})


def hands_of(raw: list) -> dict:
    out: dict = defaultdict(list)
    for h in raw:
        out[h["track_id"]].append(SimpleNamespace(
            track_id=h["track_id"], category=h["category"], score=h["score"], handedness=h.get("handedness"),
            landmarks_px=np.asarray(h["lm"], float), world_xyz=np.asarray(h["world"], float) if h.get("world") else None,
            box=tuple(h["box"]), wrist=tuple(h.get("wrist", h["lm"][0]))))
    return out


def replay(frames: list, rc: dict, cc: dict, keep_samples: bool = False) -> list:
    """[(frame, [PersonReading], {track_id: Sample})] of one run, re-running the live reader on the logged pan-tilt frames."""
    pipe = hp4.PersonsPipeline(rc, cc)
    out = []
    for f in frames:
        dets = [{"track_id": p["track_id"], "box": tuple(p["box"]), "kp": np.asarray([k[:2] for k in p["kp"]], float),
                 "conf": np.asarray([k[2] if k[2] is not None else 0.0 for k in p["kp"]], float)} for p in f["people"] if p["kp"]]
        meta = {"t": f["time_s"], **{k: f[k] for k in ("fx", "fy", "cx", "cy", "width", "height")}, "pan_deg": f["pan_deg"],
                "tilt_deg": f.get("tilt_deg", 0.0), "robot_yaw_deg": f["pose"]["yaw_deg"]}
        prs = pipe.update(dets, hands_of(f["hands"]), meta)
        smp = {p.track_id: pipe.buffers[p.track_id].window(f["time_s"], 0.0)[-1] for p in prs} if keep_samples else {}
        out.append((f, prs, smp))
    return out


# ---------------------------------------------------------------- truth categories

def category_of(frame: dict, person, truth: dict, cfg: dict) -> tuple[int | None, str | None]:
    """(worker id | None, category): what the worker matched to this person shows at the frame time. None category = leave the frame out."""
    robot = frame["pose"]
    bearings, rows = {}, {}
    for w, rs in truth.items():
        ts = [r["time_s"] for r in rs]
        i = bisect.bisect_left(ts, frame["time_s"])
        near = [j for j in (i - 1, i) if 0 <= j < len(rs)]
        if not near:
            continue
        j = min(near, key=lambda k: abs(ts[k] - frame["time_s"]))
        if abs(ts[j] - frame["time_s"]) > cfg["truth_join_max_s"] + 1e-9:
            continue
        rows[w] = rs[j]
        bearings[w] = ev._bearing_to(robot, rs[j]["x"], rs[j]["z"])
    w = ev.match_worker(person.bearing_deg, bearings, cfg["match_bearing_deg"])
    if w is None:
        return None, "unmatched"
    r = rows[w]
    if r["true_command"] != "NONE" and r["phase"] in cfg["shown_phases"]:
        return w, r["true_command"]
    if r["true_command"] == "NONE" or r["phase"] in ("idle", "start_delay"):
        return w, "nothing"
    return w, None                                                                  # returning: left out


# ---------------------------------------------------------------- the analysis

def episodes(stop_events: list[tuple[float, str]], gap_s: float) -> list[dict]:
    """[(time, category)] of one run -> stop episodes (readings closer together than gap_s), each with the category of its first reading."""
    out: list[dict] = []
    for t, c in sorted(stop_events):
        if out and t - out[-1]["t1"] <= gap_s + 1e-9:
            out[-1]["t1"] = t
        else:
            out.append({"t0": t, "t1": t, "category": c})
    return out


def live_stop_episodes(rows: list[dict], gap_s: float = 0.35) -> list[dict]:
    """The stops of the live robot: runs of decisions.csv rows whose state says (stopped: STOP gesture)."""
    eps: list[dict] = []
    cur = None
    prev = None
    for r in rows:
        t, tr = float(r["time_s"]), int(r["trial"])
        if "stopped: STOP gesture" in r["state"]:
            if cur is None or cur["trial"] != tr or t - cur["t1"] > gap_s:
                cur = {"trial": tr, "t0": t, "t1": t, "state": r["state"].split(" ")[0],
                       "v_before": float(prev["v"]) if prev is not None and int(prev["trial"]) == tr else None, "rows": 0}
                eps.append(cur)
            cur["t1"] = t
            cur["rows"] += 1
        prev = r
    return eps


def shown_by_anyone(truth: dict, t: float, margin: float) -> list[str]:
    out = set()
    for rs in truth.values():
        ts = [r["time_s"] for r in rs]
        for r in rs[bisect.bisect_left(ts, t - margin):bisect.bisect_right(ts, t + margin)]:
            if r["true_command"] != "NONE":
                out.add(r["true_command"])
    return sorted(out) or ["nothing"]


def hand_cue_row(s, side: str, rc: dict) -> dict | None:
    h = s.hands.get(side)
    if h is None:
        return None
    af = gm.arm_frame(s, side, rc)
    c = gm.hand_cues(h, rc)
    lm = np.asarray(h.landmarks_px, float)
    return {"side": side, "mediapipe_label": h.category, "mediapipe_score": round(float(h.score), 3), "finger_ratios": {k: round(v, 2) for k, v in c["ratios"].items()},
            "spread_deg_from_wrist": round(c["spread_deg"], 1), "open_hand_geometry": bool(gm.open_palm_geometry(c, rc)),
            "palm_facing": round(palm_facing(lm, side), 3), "fingertip_spread": round(fingertip_spread(lm), 3),
            "arm_valid": bool(af.valid), "arm_raised": bool(af.raised) if af.valid else None,
            "wrist_above_hip_torso": round(float(af.wrist_above_hip), 2) if af.valid else None}


def quantiles(v: list[float]) -> dict:
    if not v:
        return {"n": 0}
    a = np.asarray(v, float)
    return {"n": len(v), "p10": round(float(np.percentile(a, 10)), 3), "median": round(float(np.median(a)), 3), "p90": round(float(np.percentile(a, 90)), 3)}


def variants(cfg: dict) -> list[dict]:
    c, comb = cfg["candidates"], cfg["combined"]
    out = [{"name": "before (the live reader)", "cues": {}}]
    for v in c["palm"]["min_values"]:
        out.append({"name": f"palm facing >= {v:g}", "cues": {"palm": v}})
    for v in c["spread"]["min_values"]:
        out.append({"name": f"fingertip spread >= {v:g}", "cues": {"spread": v}})
    for m in c["static"]["modes"]:
        out.append({"name": f"static: {m}", "cues": {"static": m}})
    p, s, t = comb["palm"], comb["spread"], comb["static"]
    out += [{"name": f"palm >= {p:g} + static ({t})", "cues": {"palm": p, "static": t}},
            {"name": f"palm >= {p:g} + spread >= {s:g}", "cues": {"palm": p, "spread": s}},
            {"name": f"spread >= {s:g} + static ({t})", "cues": {"spread": s, "static": t}},
            {"name": f"all three (palm >= {p:g}, spread >= {s:g}, static {t})", "cues": {"palm": p, "spread": s, "static": t}}]
    if "raised" in c.get("extra", {}):
        out += [{"name": "EXTRA: arm raised (the reader's flag) alone", "cues": {"raised": True}},
                {"name": f"EXTRA: all three + arm raised", "cues": {"palm": p, "spread": s, "static": t, "raised": True}}]
    return out


def analyse(logs: Logs, cfg: dict, rc: dict, cc: dict, progress=None) -> dict:
    report: dict = {"zip": {"name": logs.path.name, "sha256": logs.sha256()}, "sessions": {}, "guard": {}}
    runs_data: dict = {}                                                            # (session, run) -> {"frames", "truth"}
    for sname, sc in cfg["sessions"].items():
        spans = {}
        truths = {}
        for run in logs.runs(sc["unity"]):
            tr = logs.truth(sc["unity"], run)
            report["guard"][f"{sname}/run_{run:03d}"] = guard(tr)                      # refuses anything but development looks and clips
            truths[run] = tr
            ts = [r["time_s"] for rs in tr.values() for r in rs]
            spans[run] = (min(ts), max(ts))
        per_run: dict = defaultdict(list)
        for f in logs.lines(f"{sc['bridge']}/model_outputs.jsonl"):
            if f["cam"] != "pan_tilt":
                continue
            for run, (lo, hi) in spans.items():
                if lo - 1e-6 <= f["time_s"] <= hi + 1e-6:
                    per_run[run].append(f)
                    break
        for run in truths:
            runs_data[(sname, run)] = {"frames": per_run.get(run, []), "truth": truths[run]}
        report["sessions"][sname] = {"what": sc["what"], "runs": len(truths), "pan_tilt_frames": sum(len(v) for v in per_run.values())}

    # ---- the baseline replay: categories, the replay check, the cue values, the cause of the stops with nothing shown
    cats: dict = {}                                                                 # (session, run, frame index, track) -> category
    base = {}
    cue_values: dict = {c: defaultdict(list) for c in CATEGORIES}
    open_hand_frames = Counter()
    for key, d in runs_data.items():
        res = replay(d["frames"], rc, cc, keep_samples=True)
        base[key] = res
        for i, (f, prs, smp) in enumerate(res):
            for p in prs:
                w, cat = category_of(f, p, d["truth"], cfg)
                cats[(key, i, p.track_id)] = cat
                if cat is None or p.track_id not in smp:
                    continue
                for side in gm.ARMS:
                    row = hand_cue_row(smp[p.track_id], side, rc)
                    if row is not None and row["open_hand_geometry"]:
                        open_hand_frames[cat] += 1
                        cue_values[cat]["palm_facing"].append(row["palm_facing"])
                        cue_values[cat][f"palm_facing_{side}_hand"].append(row["palm_facing"])
                        cue_values[cat]["fingertip_spread"].append(row["fingertip_spread"])
                        cue_values[cat]["spread_deg_from_wrist"].append(row["spread_deg_from_wrist"])
                        cue_values[cat]["arm_raised"].append(1.0 if row["arm_raised"] else 0.0)
                        v = wrist_speed(list(_buffer_window(base, key, i, p.track_id, rc)), side, rc, f["time_s"], rc["window"]["stop_window_s"])
                        if v is not None:
                            cue_values[cat]["wrist_speed_stop_window"].append(round(v, 3))
    report["cue_values_on_open_hand_frames"] = {c: {k: quantiles(v) for k, v in vals.items()} | {"open_hand_frames": open_hand_frames[c]}
                                                for c, vals in cue_values.items()}

    # ---- the live robot: stop episodes of decisions.csv by what the workers showed
    live, cause = {}, []
    for sname, sc in cfg["sessions"].items():
        eps = live_stop_episodes(logs.decisions(sc["bridge"]))
        tally: Counter = Counter()
        for e in eps:
            tr = runs_data[(sname, e["trial"])]["truth"]
            kinds = shown_by_anyone(tr, (e["t0"] + e["t1"]) / 2, (e["t1"] - e["t0"]) / 2 + 0.6)
            tally[(e["state"], "+".join(kinds))] += 1
            if kinds == ["nothing"] and e["state"] == "navigate":
                cause.append({"session": sname, **e, "persons": stop_details(base[(sname, e["trial"])], tr, e, rc, cfg)})
        live[sname] = {"stop_episodes": len(eps), "by_state_and_shown": {f"{k[0]} / {k[1]}": v for k, v in sorted(tally.items(), key=lambda kv: -kv[1])}}
    report["live_stops"], report["stops_with_nothing_shown_while_navigating"] = live, cause

    # ---- the replay check
    chk = {}
    for sname, sc in cfg["sessions"].items():
        rows = logs.decisions(sc["bridge"])
        stop_rows = [float(r["time_s"]) for r in rows if r["gesture"] == "STOP"]
        stops = sorted(f["time_s"] for (s2, _), res in base.items() if s2 == sname for f, prs, _ in res if any(p.reading.command == "STOP" for p in prs))
        miss = sum(1 for t in stop_rows if not (bisect.bisect_right(stops, t) > 0 and t - stops[bisect.bisect_right(stops, t) - 1] <= 0.6))
        chk[sname] = {"decisions_STOP_rows": len(stop_rows), "replayed_STOP_frames": len(stops), "decision_STOP_rows_without_a_replayed_STOP_in_the_0.6_s_before": miss}
    report["replay_check"] = chk

    # ---- the variants
    results = []
    for var in variants(cfg):
        tally = {c: {"person_frames": 0, "stop_frames": 0} for c in CATEGORIES}
        eps_by_cat: Counter = Counter()
        with candidate(var["cues"], rc) if var["cues"] else contextlib.nullcontext():
            for key, d in runs_data.items():
                res = base[key] if not var["cues"] else replay(d["frames"], rc, cc)
                events = []
                for i, (f, prs, _) in enumerate(res):
                    for p in prs:
                        cat = cats.get((key, i, p.track_id))
                        if cat is None:
                            continue
                        tally[cat]["person_frames"] += 1
                        if p.reading.command == "STOP":
                            tally[cat]["stop_frames"] += 1
                            events.append((f["time_s"], cat))
                for e in episodes(events, cfg["episode_gap_s"]):
                    eps_by_cat[e["category"]] += 1
        for c in CATEGORIES:
            n, k = tally[c]["person_frames"], tally[c]["stop_frames"]
            tally[c]["stop_rate"] = round(k / n, 4) if n else None
            tally[c]["stop_episodes"] = eps_by_cat[c]
        results.append({"name": var["name"], "cues": var["cues"], "by_category": tally})
        if progress:
            progress(var["name"])
    report["variants"] = results
    report["true_stop"] = {"frames_with_a_true_STOP_in_the_zip": 0, "note": "the zip holds no STOP and no WAIT gesture (truth: NONE, POINT, PROCEED only): STOP readings on a true STOP "
                           "cannot be shown from this data. The cost of each cue on a true STOP needs STOP recordings of the development looks and clips."}
    return report


def _buffer_window(base: dict, key, i: int, track_id: int, rc: dict):
    """The samples of one person up to frame i of a run (for the wrist speed over the stop window)."""
    out = []
    t_now = base[key][i][0]["time_s"]
    for j in range(i, -1, -1):
        f, _, smp = base[key][j]
        if f["time_s"] < t_now - rc["window"]["stop_window_s"] - 1e-9:
            break
        if track_id in smp:
            out.append(smp[track_id])
    return reversed(out)


def stop_details(res: list, truth: dict, ep: dict, rc: dict, cfg: dict) -> list[dict]:
    """Everything about the people seen around one stop with nothing shown: per frame, per person and hand."""
    rows = []
    for f, prs, smp in res:
        if not ep["t0"] - 0.8 <= f["time_s"] <= ep["t1"] + 0.05:
            continue
        for p in prs:
            w, cat = category_of(f, p, truth, cfg)
            near = None
            for wid, rs in truth.items():
                ts = [r["time_s"] for r in rs]
                r = rs[min(bisect.bisect_left(ts, f["time_s"]), len(rs) - 1)]
                d = math.hypot(r["x"] - f["pose"]["x"], r["z"] - f["pose"]["z"])
                if near is None or d < near[0]:
                    near = (d, wid, r["look"], r["true_command"], r["phase"])
            hands = [h for side in gm.ARMS for h in [hand_cue_row(smp[p.track_id], side, rc)] if h is not None]
            rows.append({"t": round(f["time_s"], 3), "track_id": p.track_id, "matched_worker": w, "category": cat, "reader_command": p.reading.command,
                         "nearest_worker": {"distance_m": round(near[0], 1), "worker": near[1], "look": near[2], "true_command": near[3], "phase": near[4]},
                         "pan_deg": f["pan_deg"], "hands": hands})
    return rows


def markdown(rep: dict) -> str:
    L = ["# The false STOP of the live reader (SIMULATION-FREE analysis of Nusrat's logs; AUDIT.md 16.14)", "",
         f"Zip `{rep['zip']['name']}` (SHA-256 `{rep['zip']['sha256']}`), read in place. Development looks and clips only (guard passed for every run). Nothing in the reader was changed.", ""]
    L += ["## Sessions and the replay check", "", "| session | runs | pan-tilt frames | decisions STOP rows | replayed STOP frames | STOP rows with no replayed STOP just before |", "|---|---|---|---|---|---|"]
    for s, v in rep["sessions"].items():
        c = rep["replay_check"][s]
        L.append(f"| {s} | {v['runs']} | {v['pan_tilt_frames']} | {c['decisions_STOP_rows']} | {c['replayed_STOP_frames']} | {c['decision_STOP_rows_without_a_replayed_STOP_in_the_0.6_s_before']} |")
    L += ["", "## What the live robot did: stop episodes by what the workers showed", ""]
    for s, v in rep["live_stops"].items():
        L += [f"**{s}**: {v['stop_episodes']} stop episodes", ""] + [f"- {k}: {n}" for k, n in v["by_state_and_shown"].items()] + [""]
    L += ["## (a) The stops while driving with nothing shown", ""]
    for e in rep["stops_with_nothing_shown_while_navigating"]:
        L += [f"### {e['session']} trial {e['trial']}, t {e['t0']:.2f} to {e['t1']:.2f} s ({e['state']}, speed before {e['v_before']})", ""]
        for r in e["persons"]:
            for h in r["hands"]:
                L.append(f"- t {r['t']}: track {r['track_id']} (nearest worker {r['nearest_worker']['worker']} {r['nearest_worker']['look']}, {r['nearest_worker']['distance_m']} m, truth "
                         f"{r['nearest_worker']['true_command']}/{r['nearest_worker']['phase']}), reader {r['reader_command']}; {h['side']} hand: MediaPipe {h['mediapipe_label']} {h['mediapipe_score']}, "
                         f"finger ratios {h['finger_ratios']}, spread at the wrist {h['spread_deg_from_wrist']} deg, open-hand geometry {h['open_hand_geometry']}, arm raised {h['arm_raised']}, "
                         f"wrist above hip {h['wrist_above_hip_torso']}, palm facing {h['palm_facing']}, fingertip spread {h['fingertip_spread']}")
        L.append("")
    L += ["## Cue values on the frames where the reader's open-hand geometry passes, by what the worker shows", "",
          "| shown | open-hand frames | palm facing (p10 / median / p90) | fingertip spread | spread at the wrist (deg) | wrist speed (torso/s) | arm raised |", "|---|---|---|---|---|---|---|"]
    for c, v in rep["cue_values_on_open_hand_frames"].items():
        def q(k, v=v):
            x = v.get(k, {"n": 0})
            return "-" if not x["n"] else f"{x['p10']} / {x['median']} / {x['p90']}"
        ar = v.get("arm_raised", {"n": 0})
        L.append(f"| {c} | {v['open_hand_frames']} | {q('palm_facing')} | {q('fingertip_spread')} | {q('spread_deg_from_wrist')} | {q('wrist_speed_stop_window')} | {'-' if not ar['n'] else ar['median']} |")
    L += ["", "Palm facing by the person's own hand (p10 / median / p90; positive = the PALM faces the camera by the sign convention of `palm_facing`):", "",
          "| shown | right hand | left hand |", "|---|---|---|"]
    for c, v in rep["cue_values_on_open_hand_frames"].items():
        def qs(k, v=v):
            x = v.get(k, {"n": 0})
            return "-" if not x["n"] else f"n={x['n']}: {x['p10']} / {x['median']} / {x['p90']}"
        L.append(f"| {c} | {qs('palm_facing_right_hand')} | {qs('palm_facing_left_hand')} |")
    L += ["", "## (c) STOP readings per person-frame (stop frames / frames; stop episodes), before and after each candidate cue", "",
          "| variant | on PROCEED | on POINT | on nothing shown | on unmatched people |", "|---|---|---|---|---|"]
    for r in rep["variants"]:
        def cell(c, r=r):
            t = r["by_category"][c]
            return f"{t['stop_frames']}/{t['person_frames']} = {t['stop_rate']:.3f}; {t['stop_episodes']} ep." if t["person_frames"] else "-"
        L.append(f"| {r['name']} | {cell('PROCEED')} | {cell('POINT')} | {cell('nothing')} | {cell('unmatched')} |")
    L += ["", f"**On a true STOP:** {rep['true_stop']['note']}", ""]
    return "\n".join(L) + "\n"


def main(argv=None) -> None:
    import decision_io as dio

    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--zip", required=True)
    ap.add_argument("--config", default=DEFAULT_CONFIG)
    a = ap.parse_args(argv)
    cfg_path = dio.resolve(a.config)
    cfg = load_config(cfg_path)
    rc, cc = gm.load_config(), cm.load_config()
    logs = Logs(Path(a.zip).expanduser())
    rep = analyse(logs, cfg, rc, cc, progress=lambda n: print("  done:", n, flush=True))
    out = dio.new_run_dir({"paths": {"output_root": "outputs"}}, "false_stop_analysis_v4")
    (out / "config_used").mkdir()
    for p in (cfg_path, dio.resolve(gm.DEFAULT_CONFIG), dio.resolve(cm.DEFAULT_CONFIG), dio.resolve(ds.DEFAULT)):
        (out / "config_used" / p.name).write_bytes(p.read_bytes())
    dio.write_json(out / "report.json", rep)
    (out / "report.md").write_text(markdown(rep), encoding="utf-8")
    dio.write_json(out / "run.json", {"git": dio.git_info(), "zip": rep["zip"]})
    print(markdown(rep))
    print(f"Folder: {out}")


if __name__ == "__main__":
    main()
