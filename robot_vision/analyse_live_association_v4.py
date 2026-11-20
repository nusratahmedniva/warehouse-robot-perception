"""The track-consistent recount of AUDIT.md 16.26.4: the dialog replayed with the LIVE association (the controller's own commander rule and 360 link, per logged frame) instead of the
replay's own (commander = most POINT frames, every track as a stream, a worker matched by bearing at every frame). EVALUATION CODE ONLY: it reads the workers' truth; inference code never
imports it. It changes nothing in the reader (a variant is applied to the replay only, analyse_point_frames_v4.variant_ctx). Everything it does is declared in AUDIT.md 16.26.4 before it ran.

Per frame that has a row in the session's v4_log.jsonl: persons of PersonsPipeline -> commander_v4.pick_commander (previous commander, `early` rule) -> commander_v4.link_to_360 ->
label (S5: hri_control_v4.resolve_point; STOP sessions and D4*: the robot-relative class of the commander's POINT) -> hri_control.GestureDialog. The replay is verified against the live log
(V1 persons, V2 commander, V3 360 track: 100 % required). The worker a commander is = the truth worker nearest to its 360 track in the ground plane (unresolved, not guessed, when none is
within 1.0 m or two are within 0.3 m of each other).

Usage (from robot_vision/): python analyse_live_association_v4.py --step5 Z --stop Z --d4 Z [--label x]
Writes outputs/live_association_v4_<time>[_label]/ (report.json, report.md, run.json); never overwrites."""

from __future__ import annotations

import argparse
import bisect
import json
import math
import subprocess
import time
from collections import Counter, defaultdict
from dataclasses import replace
from pathlib import Path

import analyse_false_stop_v4 as fs
import analyse_point_dialog_v4 as pd
import analyse_point_frames_v4 as pf
import analyse_proceed_stop_v4 as ps
import commander_v4 as cm
import gesture_motion as gm
import hri_control as hc
import hri_control_v4 as hv

HERE = Path(__file__).resolve().parent

# Declared in AUDIT.md 16.26.4 before anything was computed.
IDENT_RADIUS_M = 1.0          # the nearest worker must be within this of the commander's 360 track
IDENT_MARGIN_M = 0.3          # and the second nearest at least this much farther
CHAIN_GAP_S = 1.0             # a break between logged frames: the chain restarts from the logged commander (if at most this old)
GROUP_GAP_S = 30.0            # asks less than this apart (same junction, same run) are one dialog: the question time is the first one's
ROW_TOL_S = 0.0015            # a logged row belongs to the replayed frame whose time is this near
BEARING_TOL_DEG = 0.0051      # logged bearings are rounded to 0.01 degrees
WINDOW_MARGIN_S = 1.0         # rows this long after the last ask's window still belong to its dialog


# ---------------------------------------------------------------- the live inputs of a session

def load_session(ds: ps.Dataset, sname: str) -> dict:
    """The logged controller rows by trial and the 360 frames (time, pose, people with bearing and distance) of one session."""
    bridge = ds.cfg["sessions"][sname]["bridge"]
    rows: dict = defaultdict(list)
    for r in ds.logs.lines(f"{bridge}/v4_log.jsonl"):
        rows[int(r["trial"])].append(r)
    for rs in rows.values():
        rs.sort(key=lambda r: r["t"])
    p360 = []
    for f in ds.logs.lines(f"{bridge}/model_outputs.jsonl"):
        if f["cam"] == "360":
            p360.append((f["time_s"], f["pose"], [{"track_id": p["track_id"], "bearing_deg": p["bearing_deg"], "distance_m": p.get("distance_m")} for p in f["people"]]))
    p360.sort(key=lambda x: x[0])
    return {"rows": rows, "p360": p360, "p360_t": [x[0] for x in p360]}


def newest_360(sess: dict, ctrl_t: float, stale_s: float):
    """The newest 360 frame at or before the controller time, None when older than people_stale_s (as the controller's _fresh_people)."""
    i = bisect.bisect_right(sess["p360_t"], ctrl_t) - 1
    if i < 0 or ctrl_t - sess["p360_t"][i] > stale_s:
        return None
    return sess["p360"][i]


def ask_groups(ds: ps.Dataset, sname: str, road: hc.Roadmap | None, frames_by_run: dict) -> dict:
    """{run: [{first, last, node}]}: consecutive asks at the same junction (S5; the gap alone elsewhere) less than GROUP_GAP_S apart; the first ask's time is the dialog's question time."""
    out: dict = defaultdict(list)
    for run, t0 in sorted(pd.ask_starts(ds, sname)):
        node = None
        if road is not None:
            fr = next((f for f in frames_by_run.get(run, []) if f["time_s"] >= t0), None)
            node = pd.asking_node(road, fr["pose"]["x"], fr["pose"]["z"]) if fr is not None else None
        g = out[run][-1] if out[run] else None
        if g is not None and g["node"] == node and t0 - g["last"] < GROUP_GAP_S:
            g["last"] = t0
        else:
            out[run].append({"first": t0, "last": t0, "node": node})
    return out


def t_ask_of(groups: list, t: float) -> float | None:
    for g in groups:
        if g["first"] - 1e-9 <= t <= g["last"] + 5.0 + WINDOW_MARGIN_S:
            return g["first"]
    return None


# ---------------------------------------------------------------- the replay of a run under one reader

def replay_run(ds: ps.Dataset, sname: str, run: int, sess: dict, v: dict, rc: dict, cfg: dict) -> list[dict]:
    """One entry per replayed frame that has a logged row: persons as the controller sees them, the persons' onset times and the logged row."""
    d = ds.runs[(sname, run)]
    idx = ds.dec[sname]
    rows = sess["rows"].get(run, [])
    row_t = [r["t"] for r in rows]
    cc = cm.load_config()
    raised: dict = {}
    out = []
    with pf.variant_ctx(v):
        for f, prs, _ in ps.replay_hooked(d["frames"], rc, cc, lambda f: None):
            stopped = ps.is_stopped(idx, run, f["time_s"], cfg["stopped_speed_mps"])
            persons = [replace(p, reading=p.reading_stopped) if (stopped and p.reading_stopped is not None) else p for p in prs]
            seen = {p.track_id for p in persons}
            for p in persons:
                if p.reading.raised or p.reading.command == "PROCEED":
                    raised.setdefault(p.track_id, f["time_s"])
                else:
                    raised.pop(p.track_id, None)
            for k in [k for k in raised if k not in seen]:
                del raised[k]
            i = bisect.bisect_left(row_t, f["time_s"])
            near = [j for j in (i - 1, i) if 0 <= j < len(rows) and abs(row_t[j] - f["time_s"]) <= ROW_TOL_S]
            if not near:
                continue
            j = min(near, key=lambda k: abs(row_t[k] - f["time_s"]))
            out.append({"t": f["time_s"], "yaw": f["pose"]["yaw_deg"], "pose": f["pose"], "persons": persons, "raised": dict(raised), "row": rows[j], "row_index": j})
    return out


def logged_previous(rows: list[dict], j: int, t: float) -> int | None:
    """The live state at a restart: the logged commander of the row before this one, if at most CHAIN_GAP_S earlier."""
    if j <= 0 or t - rows[j - 1]["t"] > CHAIN_GAP_S + 1e-9:
        return None
    return rows[j - 1]["commander"]["commander"]


def run_chain(L: list[dict], rows: list[dict], lo: int, hi: int, groups: list, sess: dict, ccfg: dict, safety: dict) -> list[dict]:
    """The commander and its 360 track on the logged frames L[lo:hi], free-running from the logged state at lo. Returns one dict per frame."""
    out = []
    prev = None
    last_t = None
    for k in range(lo, hi):
        fr = L[k]
        if last_t is None or fr["t"] - last_t > CHAIN_GAP_S + 1e-9:
            prev = logged_previous(rows, fr["row_index"], fr["t"])
        last_t = fr["t"]
        ctrl_t = fr["row"]["ctrl_t"]
        persons = fr["persons"] if ctrl_t - fr["t"] <= safety["gesture_stale_s"] else []
        t_ask = t_ask_of(groups, fr["t"])
        early = {p.track_id: "early" for p in persons if (p.reading.raised or p.reading.command == "PROCEED") and t_ask is not None and fr["raised"].get(p.track_id, math.inf) < t_ask - 1e-9}
        choice = cm.pick_commander(persons, ccfg, prev, early)
        prev = choice.commander
        p = next((q for q in persons if q.track_id == choice.commander), None)
        f360 = None
        link = None
        if p is not None:
            f360 = newest_360(sess, ctrl_t, safety["people_stale_s"])
            link = cm.link_to_360(p.bearing_deg, [{"track_id": q["track_id"], "bearing_deg": q["bearing_deg"]} for q in (f360[2] if f360 else [])], ccfg["link_bearing_tol_deg"])
        out.append({"k": k, "t": fr["t"], "commander": choice.commander, "person": p, "link": link, "f360": f360, "persons": persons})
    return out


# ---------------------------------------------------------------- verification against the live log (V1, V2, V3)

def verify(L: list[dict], chain: list[dict], rows: list[dict]) -> dict:
    """The replay against the logged rows of one run: rows that have no replayed frame, and V1/V2/V3 disagreements."""
    out = {"rows": len(rows), "replayed": len(L), "no_frame": len(rows) - len(L), "v1_bad": [], "v2_bad": [], "v3_bad": []}
    for fr, c in zip(L, chain):
        row = fr["row"]
        logged = {p["id"]: (p["bearing_deg"], p["reading"]["command"], p["reading"]["valid_frames"]) for p in row["persons"]}
        mine = {p.track_id: (p.bearing_deg, p.reading.command, p.reading.valid_frames) for p in c["persons"]}
        ok = set(logged) == set(mine) and all(abs(logged[i][0] - mine[i][0]) <= BEARING_TOL_DEG and logged[i][1:] == mine[i][1:] for i in logged if i in mine)
        if not ok:
            out["v1_bad"].append({"t": fr["t"], "logged": {str(k): v for k, v in logged.items()}, "replayed": {str(k): [round(v[0], 2), v[1], v[2]] for k, v in mine.items()}})
        if c["commander"] != row["commander"]["commander"]:
            out["v2_bad"].append({"t": fr["t"], "logged": row["commander"]["commander"], "replayed": c["commander"]})
        if c["link"] != row["commander_360"]:
            out["v3_bad"].append({"t": fr["t"], "logged": row["commander_360"], "replayed": c["link"]})
    return out


# ---------------------------------------------------------------- the worker a commander is (evaluation only)

def worker_row(truth: dict, w: int, t: float, tol: float) -> dict | None:
    r = ps.truth_row(truth, w, t)
    return r if r is not None and abs(r["time_s"] - t) <= tol + 1e-9 else None


def identity(c: dict, truth: dict, cfg: dict) -> tuple[int | None, str]:
    """The truth worker nearest, in the ground plane, to the commander's 360 track; (None, why) when not resolved."""
    if c["person"] is None:
        return None, "no commander"
    if c["link"] is None or c["f360"] is None:
        return None, "no 360 track"
    t360, pose, people = c["f360"]
    q = next((q for q in people if q["track_id"] == c["link"]), None)
    if q is None or q["distance_m"] is None:
        return None, "no distance"
    pos = hc.world_point(pose["x"], pose["z"], pose["yaw_deg"], q["bearing_deg"], q["distance_m"])
    ds_ = []
    for w in truth:
        r = worker_row(truth, w, t360, cfg["truth_join_max_s"])
        if r is not None:
            ds_.append((math.hypot(r["x"] - pos[0], r["z"] - pos[1]), w))
    ds_.sort()
    if not ds_ or ds_[0][0] > IDENT_RADIUS_M:
        return None, f"no worker within {IDENT_RADIUS_M} m"
    if len(ds_) > 1 and ds_[1][0] - ds_[0][0] < IDENT_MARGIN_M:
        return None, f"two workers within {IDENT_MARGIN_M} m of each other"
    return ds_[0][1], ""


def category_of_worker(truth: dict, w: int, t: float, cfg: dict) -> tuple[str | None, dict | None]:
    """What the worker shows at the frame time, as analyse_false_stop_v4.category_of (None = the phase 'returning' or no truth row)."""
    r = worker_row(truth, w, t, cfg["truth_join_max_s"])
    if r is None:
        return None, None
    if r["true_command"] != "NONE" and r["phase"] in cfg["shown_phases"]:
        return r["true_command"], r
    if r["true_command"] == "NONE" or r["phase"] in ("idle", "start_delay"):
        return "nothing", r
    return None, r


def frame_truth(c: dict, fr: dict, truth: dict, cfg: dict) -> dict:
    """Identity and truth of the commander at one replayed frame."""
    w, why = identity(c, truth, cfg)
    out = {"worker": w, "why": why, "cat": None, "phase": None}
    if w is not None:
        cat, r = category_of_worker(truth, w, fr["t"], cfg)
        out["cat"] = cat
        if r is not None:
            out["phase"] = r["phase"]
            if r["true_command"] == "POINT":
                out["truth_rel"] = float(r["point_angle_deg"])
    return out


# ---------------------------------------------------------------- the dialog on the commander's labels

def hold_check(L: list[dict], C: list[dict], T: list[dict], first: int, last: int) -> dict:
    """The POINT readings of the commander inside an accepted hold (frames first..last): false (the identified worker shows no POINT), unresolved (identity or category unknown)."""
    false_f, unres = [], []
    for k in range(first, last + 1):
        p = C[k]["person"]
        if p is None or p.reading.command != "POINT":
            continue
        t = T[k]
        if t["worker"] is None or t["cat"] is None:
            unres.append({"t": L[k]["t"], "why": t["why"] or f"category unknown (phase {t['phase']})"})
        elif t["cat"] != "POINT":
            false_f.append({"t": L[k]["t"], "worker": t["worker"], "shows": t["cat"], "tid": p.track_id})
    return {"false": false_f, "unresolved": unres}


def label_s5(p: cm.PersonReading | None, yaw: float, road: hc.Roadmap, node: str, dv: dict, mirror: bool) -> str:
    if p is None or p.reading.command != "POINT" or p.reading.point is None:
        return "NONE"
    return pd.label_of({"cmd": "POINT", "point": p.reading.point, "yaw": yaw}, road, node, dv, mirror)


def asks_s5(ds: ps.Dataset, sname: str, L_by_run: dict, ctx_by_run: dict, dv: dict, ccfg: dict, safety: dict, groups_by_run: dict, cfg: dict) -> list[dict]:
    """Every ask of a step-5 session: the window, the live commander chain, the dialog, the verdict."""
    road = hc.Roadmap(hc.load_json(pd.ROADMAPS[sname]))
    mirror = not sname.endswith("_off")
    out = []
    for run, t0 in sorted(pd.ask_starts(ds, sname)):
        L, sess = L_by_run.get(run, []), ctx_by_run[run]
        rows = sess["rows"].get(run, [])
        win = [k for k, fr in enumerate(L) if t0 - 1e-9 <= fr["t"] <= t0 + dv["window"] + 1e-9]
        if not win:
            out.append({"session": sname, "run": run, "t0": round(t0, 2), "frames": 0, "commanders": [], "accepted": None})
            continue
        lo, hi = win[0], win[-1] + 1
        node = next((g["node"] for g in groups_by_run.get(run, []) if g["first"] - 1e-9 <= t0 <= g["last"] + 1e-9), None) or pd.asking_node(road, L[lo]["pose"]["x"], L[lo]["pose"]["z"])
        C = run_chain(L, rows, lo, hi, groups_by_run.get(run, []), sess, ccfg, safety)
        truth = ds.runs[(sname, run)]["truth"]
        T = [frame_truth(c, L[lo + i], truth, ds.cfg) for i, c in enumerate(C)]
        labels = [label_s5(c["person"], L[lo + i]["yaw"], road, node, dv, mirror) for i, c in enumerate(C)]
        fr_dialog = [{"t": L[lo + i]["t"]} for i in range(len(C))]
        acc, i_acc, i_first = pd.feed(fr_dialog, labels, dv, t0)
        tl_frames = [{"cat": T[i]["cat"], "phase": T[i]["phase"], "yaw": L[lo + i]["yaw"], "truth_rel": T[i].get("truth_rel", 0.0)} for i in range(len(C)) if "truth_rel" in T[i]]
        truth_label = pd.true_label(tl_frames, road, node, dv["tol"])
        row = {"session": sname, "run": run, "t0": round(t0, 2), "node": node, "frames": len(C),
               "commanders": sorted({(c["commander"], c["link"]) for c in C if c["commander"] is not None}, key=str),
               "workers": sorted({t["worker"] for t in T if t["worker"] is not None}),
               "true": truth_label, "accepted": acc, "t_accept": None}
        row["right"] = bool(acc is not None and acc == truth_label)
        row["wrong"] = bool(acc is not None and acc != truth_label)
        row["false_point"], row["unresolved"] = [], []
        if acc is not None:
            h = hold_check(L, C, T, i_first, i_acc)
            row["false_point"], row["unresolved"] = h["false"], h["unresolved"]
            row["t_accept"] = round(C[i_acc]["t"] - t0, 2)
        out.append(row)
    return out


def streams_stop(ds: ps.Dataset, sname: str, L: list[dict], sess: dict, run: int, dv: dict, ccfg: dict, safety: dict, groups: list, cfg: dict) -> dict:
    """STOP sessions and D4*: the whole run as one commander chain, the commander's POINT as a robot-relative LEFT/FORWARD/RIGHT label (away and toward readings each), the dialog tiled over it."""
    rows = sess["rows"].get(run, [])
    C = run_chain(L, rows, 0, len(L), groups, sess, ccfg, safety)
    truth = ds.runs[(sname, run)]["truth"]
    T = [frame_truth(c, L[i], truth, ds.cfg) for i, c in enumerate(C)]
    acc_list = []
    n_windows = 0
    for fam in ("away", "toward"):
        labels = []
        for c in C:
            p = c["person"]
            rel = (p.reading.point.rel_deg or {}).get(fam) if (p is not None and p.reading.command == "POINT" and p.reading.point is not None) else None
            cl = pf.class_of(rel) if rel is not None else "NONE"
            labels.append(cl if cl in ("LEFT", "FORWARD", "RIGHT") else "NONE")
        frames = [{"t": fr["t"]} for fr in L]
        start = 0
        while start < len(frames):
            n_windows += 1
            acc, i_acc, i_first = pd.feed(frames[start:], labels[start:], dv, frames[start]["t"])
            if acc is not None:
                h = hold_check(L, C, T, start + i_first, start + i_acc)
                acc_list.append({"session": sname, "run": run, "family": fam, "t": round(L[start + i_acc]["t"], 2), "label": acc, "false_point": h["false"], "unresolved": h["unresolved"],
                                 "commander": C[start + i_acc]["commander"]})
                start += i_acc + 1
            else:
                end_t = frames[start]["t"] + dv["window"]
                nxt = next((k for k in range(start, len(frames)) if frames[k]["t"] > end_t), len(frames))
                start = max(nxt, start + 1)
    return {"frames": len(L), "windows": n_windows, "accepted": acc_list}


# ---------------------------------------------------------------- the analysis

def analyse(step5: str, stop: str, d4: str, cfg: dict) -> dict:
    rc = gm.load_config()
    ccfg = cm.load_config()
    dv = pd.dialog_values()
    base, _v4 = hv.load_control()
    safety = base["safety"]
    sets = {"S5": ps.Dataset("S5", step5, cfg["sessions"]["S5"], cfg), "STOP": ps.Dataset("STOP", stop, cfg["sessions"]["STOP"], cfg), "D4*": ps.Dataset("D4*", d4, cfg["sessions"]["D4*"], cfg)}
    rep: dict = {"dialog": dv, "guard_all_development": all(set(d.guard.values()) == {"development"} for d in sets.values()),
                 "zips": {k: {"name": Path(p).name, "sha256": sets[k].logs.sha256()} for k, p in (("S5", step5), ("STOP", stop), ("D4*", d4))},
                 "constants": {"ident_radius_m": IDENT_RADIUS_M, "ident_margin_m": IDENT_MARGIN_M, "chain_gap_s": CHAIN_GAP_S, "group_gap_s": GROUP_GAP_S}, "verification": {}, "variants": {}}
    sessions = {k: {s: load_session(d, s) for s in d.dec} for k, d in sets.items()}
    for v in pd.VARIANTS:
        res: dict = {"name": v["name"], "S5": [], "STOP": [], "D4*": []}
        for k, d in sets.items():
            for sname in d.dec:
                sess = sessions[k][sname]
                road = hc.Roadmap(hc.load_json(pd.ROADMAPS[sname])) if k == "S5" else None
                frames_by_run = {run: dd["frames"] for (s, run), dd in d.runs.items() if s == sname}
                groups = ask_groups(d, sname, road, frames_by_run)
                L_by_run = {run: replay_run(d, sname, run, sess, v, rc, cfg) for (s, run) in d.runs if s == sname}
                ctx_by_run = {run: sess for run in L_by_run}
                if v["key"] == "ref":                                    # V1-V3 on the reference reader, the whole run as one chain
                    for run, L in L_by_run.items():
                        rows = sess["rows"].get(run, [])
                        C = run_chain(L, rows, 0, len(L), groups.get(run, []), sess, ccfg, safety)
                        ver = verify(L, C, rows)
                        rep["verification"].setdefault(k, {})[f"{sname}/run_{run:03d}"] = ver
                if k == "S5":
                    res["S5"] += asks_s5(d, sname, L_by_run, ctx_by_run, dv, ccfg, safety, groups, cfg)
                else:
                    for run, L in L_by_run.items():
                        res[k].append({"session": sname, "run": run, **streams_stop(d, sname, L, sess, run, dv, ccfg, safety, groups.get(run, []), cfg)})
            print("done:", v["key"], k, flush=True)
        rep["variants"][v["key"]] = res
    return rep


def verification_summary(ver: dict) -> dict:
    out = {}
    for k, runs in ver.items():
        out[k] = {"runs": len(runs), "rows": sum(x["rows"] for x in runs.values()), "no_frame": sum(x["no_frame"] for x in runs.values()),
                  "v1_bad": sum(len(x["v1_bad"]) for x in runs.values()), "v2_bad": sum(len(x["v2_bad"]) for x in runs.values()), "v3_bad": sum(len(x["v3_bad"]) for x in runs.values())}
    return out


def condition(rep: dict, old: dict | None) -> dict:
    """The declared pass / fail / inconclusive of AUDIT.md 16.26.4."""
    vs = verification_summary(rep["verification"])
    reproduced = all(v["no_frame"] == 0 and v["v1_bad"] == 0 and v["v2_bad"] == 0 and v["v3_bad"] == 0 for v in vs.values())
    ii = rep["variants"]["ii"]
    s5 = ii["S5"]
    wrong = [a for a in s5 if a.get("wrong")]
    false_asks = [a for a in s5 if a.get("false_point")]
    unres_asks = [a for a in s5 if a.get("unresolved")]
    st_false = [x for k in ("STOP", "D4*") for r in ii[k] for x in r["accepted"] if x["false_point"]]
    st_unres = [x for k in ("STOP", "D4*") for r in ii[k] for x in r["accepted"] if x["unresolved"]]
    flagged_asks = [a for a in s5 if a["session"] == "A3" and a["run"] == 1 and a["node"] == "J1"]
    remains = [a for a in flagged_asks if a.get("false_point")] + [x for r in ii["STOP"] + ii["D4*"] for x in r["accepted"] if x["false_point"]]
    if not reproduced:
        verdict = "FAIL (the live association is not reproduced)"
    elif wrong or false_asks or st_false:
        verdict = "FAIL (a wrong or false-POINT accept)"
    elif unres_asks or st_unres:
        verdict = "INCONCLUSIVE (identity unresolved in an accepted hold): treated as FAIL for the build decision"
    else:
        verdict = "PASS"
    return {"verification": vs, "reproduced": reproduced, "wrong": len(wrong), "false_point_asks": len(false_asks), "false_point_streams": len(st_false),
            "unresolved_asks": len(unres_asks), "unresolved_streams": len(st_unres), "flagged_still_false": len(remains), "verdict": verdict}


def markdown(rep: dict) -> str:
    c = rep["condition"]
    V = rep["variants"]
    L = [f"## The track-consistent recount of AUDIT.md 16.26.4 (guard: {'all development' if rep['guard_all_development'] else 'NOT ALL DEVELOPMENT'})", "",
         "Zips: " + "; ".join(f"{k} `{v['name']}` {v['sha256'][:12]}..." for k, v in rep["zips"].items()), "",
         f"Dialog: hold {rep['dialog']['hold']} s, none gap {rep['dialog']['gap']} s, window {rep['dialog']['window']} s, tolerance {rep['dialog']['tol']} deg. Identity: nearest worker within {IDENT_RADIUS_M} m of the 360 track, margin {IDENT_MARGIN_M} m.", "",
         "### 1. Verification of the replay against the live logs (reference reader; 100 % required)", "", "| dataset | runs | logged rows | rows without a replayed frame | V1 persons differ | V2 commander differs | V3 360 track differs |", "|---|---|---|---|---|---|---|"]
    for k, v in c["verification"].items():
        L.append(f"| {k} | {v['runs']} | {v['rows']} | {v['no_frame']} | {v['v1_bad']} | {v['v2_bad']} | {v['v3_bad']} |")
    L.append(f"\n**Reproduced: {c['reproduced']}.**")
    for k, runs in rep["verification"].items():
        for name, x in runs.items():
            for key in ("v1_bad", "v2_bad", "v3_bad"):
                for b in x[key][:5]:
                    L.append(f"- {k} {name} {key}: {b}")
    L += ["", "### 2. The step-5 asks (S5): the live commander chain, the dialog, the verdict", "", "| reader | asks | with a commander | accepted | right | WRONG | accepted with a false POINT frame | accepted with identity unresolved |", "|---|---|---|---|---|---|---|---|"]
    for key in ("ref", "ii"):
        s5 = V[key]["S5"]
        L.append(f"| {V[key]['name']} | {len(s5)} | {sum(bool(a['commanders']) for a in s5)} | {sum(a['accepted'] is not None for a in s5)} | {sum(bool(a.get('right')) for a in s5)} | {sum(bool(a.get('wrong')) for a in s5)} | "
                 f"{sum(bool(a.get('false_point')) for a in s5)} | {sum(bool(a.get('unresolved')) for a in s5)} |")
    L += ["", "### 3. STOP sessions and D4* (continuous commander chain, tiled 5.0 s windows)", "", "| reader | dataset | runs | frames | windows | accepted | with a false POINT frame | with identity unresolved |", "|---|---|---|---|---|---|---|---|"]
    for key in ("ref", "ii"):
        for k in ("STOP", "D4*"):
            rs = V[key][k]
            acc = [x for r in rs for x in r["accepted"]]
            L.append(f"| {V[key]['name']} | {k} | {len(rs)} | {sum(r['frames'] for r in rs)} | {sum(r['windows'] for r in rs)} | {len(acc)} | {sum(bool(x['false_point']) for x in acc)} | {sum(bool(x['unresolved']) for x in acc)} |")
    L += ["", "### 4. The asks of step-5 A3 run 1 at J1 (where the 10 answers of 16.26.3.1 were), both readers", ""]
    for key in ("ref", "ii"):
        for a in V[key]["S5"]:
            if a["session"] == "A3" and a["run"] == 1 and a.get("node") == "J1":
                L.append(f"- {key}: t0 {a['t0']}: commanders (pan-tilt, 360) {a['commanders']}, workers {a.get('workers')}, true {a.get('true')}, accepted {a['accepted']} after {a.get('t_accept')} s, "
                         f"false POINT frames {a.get('false_point')}, unresolved {a.get('unresolved')}")
    L += ["", "### 5. Accepts of (ii) that the reference does not make", ""]
    ref = {(a["session"], a["run"], a["t0"]): a for a in V["ref"]["S5"]}
    for a in V["ii"]["S5"]:
        b = ref.get((a["session"], a["run"], a["t0"]))
        if a["accepted"] is not None and (b is None or b["accepted"] is None):
            L.append(f"- S5 {a['session']} run {a['run']} t0 {a['t0']} {a.get('node')}: (ii) accepted {a['accepted']} after {a.get('t_accept')} s, true {a.get('true')}, {'right' if a.get('right') else 'WRONG'}, false POINT {len(a.get('false_point', []))}, unresolved {len(a.get('unresolved', []))}")
    for k in ("STOP", "D4*"):
        r_ref = {(x["session"], x["run"], x["family"], x["t"]) for r in V["ref"][k] for x in r["accepted"]}
        for r in V["ii"][k]:
            for x in r["accepted"]:
                if (x["session"], x["run"], x["family"], x["t"]) not in r_ref:
                    L.append(f"- {k} {x['session']} run {x['run']} {x['family']} t {x['t']}: (ii) accepted {x['label']}, false POINT {len(x['false_point'])}, unresolved {len(x['unresolved'])}")
    L += ["", f"### 6. The declared condition: wrong {c['wrong']}, false-POINT accepts (asks {c['false_point_asks']}, streams {c['false_point_streams']}), unresolved (asks {c['unresolved_asks']}, streams {c['unresolved_streams']}), "
          f"flagged asks still false {c['flagged_still_false']} -> **{c['verdict']}**"]
    for key in ("ref", "ii"):
        for a in V[key]["S5"]:
            if a.get("false_point") or a.get("wrong"):
                L.append(f"- {key} S5 {a['session']} run {a['run']} t0 {a['t0']}: accepted {a['accepted']} true {a.get('true')}, false POINT {a.get('false_point')}")
        for k in ("STOP", "D4*"):
            for r in V[key][k]:
                for x in r["accepted"]:
                    if x["false_point"]:
                        L.append(f"- {key} {k} {x['session']} run {x['run']} {x['family']} t {x['t']}: accepted {x['label']}, false POINT {x['false_point']}")
    return "\n".join(L)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--step5", required=True)
    ap.add_argument("--stop", required=True)
    ap.add_argument("--d4", required=True)
    ap.add_argument("--label", default="")
    a = ap.parse_args(argv)
    rep = analyse(a.step5, a.stop, a.d4, ps.load_config())
    rep["condition"] = condition(rep, None)
    out = HERE / "outputs" / f"live_association_v4_{time.strftime('%Y%m%d_%H%M%S')}{'_' + a.label if a.label else ''}"
    out.mkdir(parents=True, exist_ok=False)
    md = markdown(rep)
    (out / "report.json").write_text(json.dumps(rep, indent=1, default=str), encoding="utf-8")
    (out / "report.md").write_text(md + "\n", encoding="utf-8")
    commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=HERE, capture_output=True, text=True).stdout.strip()
    (out / "run.json").write_text(json.dumps({"git_commit": commit, "zips": rep["zips"], "dialog": rep["dialog"], "constants": rep["constants"], "verdict": rep["condition"]["verdict"]}, indent=1), encoding="utf-8")
    print(md)
    print(f"\nFolder: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
