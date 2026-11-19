"""POINT frames: how many valid frames the 1.0 s POINT window needs (AUDIT.md 16.26 item 3, 2026-11-19; every variant, measure and criterion is declared there BEFORE this ran).
EVALUATION CODE ONLY: it reads the workers' true commands and angles; inference code never imports it. It changes nothing in the reader: the variants are applied in this
script only, by wrapping gesture_motion functions for the duration of one replay (as analyse_proceed_stop_v4.variant_wrap does). NO VALUE IS CHANGED and nothing is chosen:
the table is shown to Anisha first.

Reference: the reader as it is now (configs/v4/gesture_reader.json: B1 floor 10 for PROCEED, the C2s STOP switch, the reading the controller uses while the robot stands
still). A POINT or WAIT needs 6 valid arm frames in the 1.0 s window (window.min_valid_fraction 0.6 x 10 frames).
  (i)  floor tied to the frames received: need = max(floor, ceil(0.6 x the frames received in the window)), floor 3, 4 and 5 (a sweep: Nusrat's floor is not known).
  (ii) stretch: the 6-frame minimum is kept and the window grows in steps of 0.1 s from 1.0 s up to 2.0 s until 6 valid frames are in it (the reader already receives 2.0 s).

Per dataset and variant: the POINT read rate over the frames in the holding phase (read as POINT, as another command, insufficient_history, NONE), by the number of people in
view and by the angle between the pointed direction and the line of sight; the minimum / median valid frames of the frames read as POINT; the accuracy of the read POINT frames
against the true pointed angle by class (LEFT, FORWARD, RIGHT, BACK by the angle to the robot's forward axis; tolerance dialog.branch_match_max_deg, either depth reading
within it); the false POINT readings; and the STOP, WAIT and PROCEED readings against the reference, frame by frame.
Criteria (declared): (1) per class LEFT, FORWARD, RIGHT: the accurate share of read POINT frames is not below the reference's and the wrong POINT readings are not more;
(2) no STOP reading changed (same STOP / not-STOP on every frame of every dataset); (3) the false POINT rate is not above the reference's.

Input: three zips, read in place with zipfile (never extracted or copied): the step-5 logs, the STOP-session logs, the 14 Nov gesture logs (the stand-in for D4). DEVELOPMENT
DATA ONLY: every run goes through the split guard before anything is computed.

Usage (from robot_vision/):
  python analyse_point_frames_v4.py --step5 ~/Downloads/step5_logs_X.zip --stop ~/Downloads/stop_session_logs_X.zip --d4 ~/Downloads/anisha_gesture_logs_X.zip [--label x]
Writes a new folder <output_root>/point_frames_v4_<time>[_label]/ (never overwrites): report.json, report.md, run.json (git commit, zip SHA-256s), config_used/."""

from __future__ import annotations

import argparse
import contextlib
import json
import math
import statistics as st
import subprocess
import time
from collections import Counter, defaultdict
from pathlib import Path

import analyse_false_stop_v4 as fs
import analyse_proceed_stop_v4 as ps
import commander_v4 as cm
import gesture_motion as gm

HERE = Path(__file__).resolve().parent
FRAC = 0.6
STEP_S = 0.1
VARIANTS = (
    {"key": "ref", "name": "reference (6 valid frames in the 1.0 s window)"},
    {"key": "i3", "name": "(i) max(3, 0.6 x received)", "floor": 3},
    {"key": "i4", "name": "(i) max(4, 0.6 x received)", "floor": 4},
    {"key": "i5", "name": "(i) max(5, 0.6 x received)", "floor": 5},
    {"key": "ii", "name": "(ii) 6 frames, window stretched up to 2.0 s", "stretch": 2.0},
)
CLASSES = ("LEFT", "FORWARD", "RIGHT", "BACK")
ANGLE_BINS = ((0, 45, "0-45 (away)"), (45, 135, "45-135 (readable band)"), (135, 145, "135-145"), (145, 163, "145-163"), (163, 181, "163-180 (toward)"))
PEOPLE = ((1, "1 person"), (2, "2 people"), (3, "3+ people"))


def wrap(a: float) -> float:
    return (a + 180.0) % 360.0 - 180.0


@contextlib.contextmanager
def variant_ctx(v: dict):
    """Apply one variant to gesture_motion for a replay and restore it afterwards."""
    orig_arm, orig_read = gm._arm_window, gm.read_window

    def arm(samples, side, cfg, t_now, **kw):
        info = orig_arm(samples, side, cfg, t_now, **kw)
        if v.get("floor") is not None:
            need = max(int(v["floor"]), math.ceil(FRAC * len(samples) - 1e-9))
            info["enough"] = info["valid"] >= need
        return info

    def read(samples, cfg, t_now=None, robot_stopped=False):
        if v.get("stretch") and samples:
            t = t_now if t_now is not None else samples[-1].t
            w0 = cfg["window"]["window_s"]
            n_min = math.ceil(cfg["window"]["min_valid_fraction"] * max(1, round(w0 * cfg["frame_hz"])) - 1e-9)
            span = w0
            while span < v["stretch"] - 1e-9:
                win = [s for s in samples if s.t >= t - span - 1e-9]
                if max(sum(1 for s in win if gm.arm_frame(s, side, cfg).valid) for side in gm.ARMS) >= n_min:
                    break
                span = round(span + STEP_S, 6)
            if span > w0 + 1e-9:
                cfg2 = {**cfg, "window": {**cfg["window"], "window_s": span, "min_valid_fraction": n_min / max(1, round(span * cfg["frame_hz"]))}}
                return orig_read(samples, cfg2, t_now, robot_stopped=robot_stopped)
        return orig_read(samples, cfg, t_now, robot_stopped=robot_stopped)

    gm._arm_window, gm.read_window = arm, read
    try:
        yield
    finally:
        gm._arm_window, gm.read_window = orig_arm, orig_read


def people_bucket(n: int) -> str:
    return "3+ people" if n >= 3 else f"{n} person" if n == 1 else f"{n} people"


def class_of(rel: float) -> str:
    a = wrap(rel)
    return "BACK" if abs(a) > 135 else "FORWARD" if abs(a) <= 45 else "RIGHT" if a > 0 else "LEFT"


def run_variant(ds: ps.Dataset, v: dict, rc: dict, cc: dict, cfg: dict) -> list[dict]:
    """One record per person-frame with a truth category."""
    ctx = {"stopped": False}
    recs: list[dict] = []
    with variant_ctx(v):
        for (sname, run), d in ds.runs.items():
            idx = ds.dec[sname]

            def hook(f, idx=idx, run=run):
                ctx["stopped"] = ps.is_stopped(idx, run, f["time_s"], cfg["stopped_speed_mps"])
            for f, prs, _ in ps.replay_hooked(d["frames"], rc, cc, hook):
                for p in prs:
                    w, cat = fs.category_of(f, p, d["truth"], ds.cfg)
                    if cat is None or cat == "unmatched":
                        continue
                    row = ps.truth_row(d["truth"], w, f["time_s"]) if w is not None else None
                    stopped = ps.is_stopped(idx, run, f["time_s"], cfg["stopped_speed_mps"])
                    r = p.reading_stopped if (stopped and p.reading_stopped is not None) else p.reading
                    rec = {"key": (sname, run, round(f["time_s"], 4), p.track_id), "t": f["time_s"], "tid": p.track_id, "yaw": f["pose"]["yaw_deg"], "point": r.point if r.command == "POINT" else None,
                           "cat": cat, "cmd": r.command, "why": r.why, "valid": r.valid_frames, "n_frames": r.n_frames,
                           "people": len(prs), "phase": row["phase"] if row else None, "stopped": stopped,
                           "look": row.get("look") if row else None, "clip": row.get("clip") if row else None, "arm": row.get("arm") if row else None}
                    if row is not None and row["true_command"] == "POINT":
                        rel = float(row["point_angle_deg"])
                        rec["truth_rel"] = rel
                        rec["class"] = class_of(rel)
                        rec["sight_angle"] = abs(wrap(rel - float(p.bearing_deg)))
                        if r.command == "POINT" and r.point is not None:
                            cands = [x for x in (r.point.rel_deg or {}).values() if x is not None]
                            rec["err"] = min(abs(wrap(x - rel)) for x in cands) if cands else None
                    recs.append(rec)
    return recs


def rate(n: int, d: int) -> float | None:
    return None if d == 0 else round(100.0 * n / d, 1)


def score(recs: list[dict], tol: float) -> dict:
    held = [r for r in recs if r["cat"] == "POINT" and r["phase"] == "holding"]
    out: dict = {"held_frames": len(held), "read_point": sum(r["cmd"] == "POINT" for r in held), "insufficient": sum(r["cmd"] == "insufficient_history" for r in held),
                 "read_other": sum(r["cmd"] in ("WAIT", "STOP", "PROCEED") for r in held), "none": sum(r["cmd"] == "NONE" for r in held)}
    out["read_rate"] = rate(out["read_point"], len(held))
    used = [r["valid"] for r in held if r["cmd"] == "POINT"]
    out["valid_frames_used"] = {"min": min(used) if used else None, "median": st.median(used) if used else None}
    out["by_people"] = {lab: {"held": sum(1 for r in held if people_bucket(r["people"]) == lab),
                              "read": sum(1 for r in held if people_bucket(r["people"]) == lab and r["cmd"] == "POINT"),
                              "insufficient": sum(1 for r in held if people_bucket(r["people"]) == lab and r["cmd"] == "insufficient_history")} for _, lab in PEOPLE}
    out["by_angle"] = {lab: {"held": sum(1 for r in held if lo <= r["sight_angle"] < hi), "read": sum(1 for r in held if lo <= r["sight_angle"] < hi and r["cmd"] == "POINT")}
                       for lo, hi, lab in ANGLE_BINS}
    cls = {}
    for c in CLASSES:
        h = [r for r in held if r["class"] == c]
        rd = [r for r in h if r["cmd"] == "POINT"]
        acc = [r for r in rd if r.get("err") is not None and r["err"] <= tol + 1e-9]
        cls[c] = {"held": len(h), "read": len(rd), "accurate": len(acc), "wrong": len(rd) - len(acc), "accurate_share": rate(len(acc), len(rd)), "read_rate": rate(len(rd), len(h))}
    out["classes"] = cls
    fp = {}
    for cat in ("nothing", "WAIT", "STOP", "PROCEED"):
        rs = [r for r in recs if r["cat"] == cat]
        fp[cat] = {"frames": len(rs), "read_as_point": sum(r["cmd"] == "POINT" for r in rs)}
    tot, rp = sum(v["frames"] for v in fp.values()), sum(v["read_as_point"] for v in fp.values())
    out["false_point"] = {**fp, "frames": tot, "read_as_point": rp, "rate": rate(rp, tot)}
    return out


def diff_vs_ref(recs: list[dict], ref: list[dict]) -> dict:
    """Frame by frame: how many frames read STOP / WAIT / PROCEED differently from the reference (same person-frame key)."""
    refmap = {r["key"]: r["cmd"] for r in ref}
    out = {"frames": 0}
    for name in ("STOP", "WAIT", "PROCEED", "POINT"):
        out[name] = {"gained": 0, "lost": 0}
    for r in recs:
        c0 = refmap.get(r["key"])
        if c0 is None:
            continue
        out["frames"] += 1
        for name in ("STOP", "WAIT", "PROCEED", "POINT"):
            a, b = c0 == name, r["cmd"] == name
            if b and not a:
                out[name]["gained"] += 1
            elif a and not b:
                out[name]["lost"] += 1
    return out


def combine(parts: list[dict]) -> dict:
    """The sum of the counts of several dataset scores (read rates recomputed)."""
    def add(key, sub=None):
        return sum((p[key] if sub is None else p[key][sub]) for p in parts)
    out = {"held_frames": add("held_frames"), "read_point": add("read_point"), "insufficient": add("insufficient"), "read_other": add("read_other"), "none": add("none")}
    out["read_rate"] = rate(out["read_point"], out["held_frames"])
    mins = [p["valid_frames_used"]["min"] for p in parts if p["valid_frames_used"]["min"] is not None]
    out["valid_frames_used"] = {"min": min(mins) if mins else None}
    out["by_people"] = {lab: {k: sum(p["by_people"][lab][k] for p in parts) for k in ("held", "read", "insufficient")} for _, lab in PEOPLE}
    out["by_angle"] = {lab: {k: sum(p["by_angle"][lab][k] for p in parts) for k in ("held", "read")} for _, _, lab in ANGLE_BINS}
    out["classes"] = {}
    for c in CLASSES:
        d = {k: sum(p["classes"][c][k] for p in parts) for k in ("held", "read", "accurate", "wrong")}
        out["classes"][c] = {**d, "accurate_share": rate(d["accurate"], d["read"]), "read_rate": rate(d["read"], d["held"])}
    fp = {cat: {k: sum(p["false_point"][cat][k] for p in parts) for k in ("frames", "read_as_point")} for cat in ("nothing", "WAIT", "STOP", "PROCEED")}
    tot, rp = sum(v["frames"] for v in fp.values()), sum(v["read_as_point"] for v in fp.values())
    out["false_point"] = {**fp, "frames": tot, "read_as_point": rp, "rate": rate(rp, tot)}
    return out


def criteria(res: dict, key: str) -> dict:
    """The three declared criteria of one variant against the reference, on all datasets together (and the STOP criterion on every dataset)."""
    ref, v = res["ref"]["ALL"], res[key]["ALL"]
    ok1, detail = True, {}
    for c in ("LEFT", "FORWARD", "RIGHT"):
        a0, a1 = ref["classes"][c], v["classes"][c]
        s0, s1 = a0["accurate_share"], a1["accurate_share"]
        share_ok = (s1 is None) or (s0 is None) or s1 >= s0 - 1e-9
        wrong_ok = a1["wrong"] <= a0["wrong"]
        detail[c] = {"ref_accurate_share": s0, "accurate_share": s1, "ref_wrong": a0["wrong"], "wrong": a1["wrong"], "ok": bool(share_ok and wrong_ok)}
        ok1 = ok1 and share_ok and wrong_ok
    stop_changed = {ds: res[key][ds]["diff"]["STOP"] for ds in ("S5", "STOP", "D4*")}
    ok2 = all(x["gained"] == 0 and x["lost"] == 0 for x in stop_changed.values())
    f0, f1 = ref["false_point"], v["false_point"]
    ok3 = f1["read_as_point"] * f0["frames"] <= f0["read_as_point"] * f1["frames"]          # exact, not the rounded rate: 6 frames of 28,099 are above 0 of 28,099
    return {"1_accuracy_LEFT_FORWARD_RIGHT": {"ok": bool(ok1), "detail": detail}, "2_no_STOP_changed": {"ok": bool(ok2), "per_dataset": stop_changed},
            "3_false_point_not_above": {"ok": bool(ok3), "ref": f"{f0['read_as_point']}/{f0['frames']}", "now": f"{f1['read_as_point']}/{f1['frames']}"}, "all_met": bool(ok1 and ok2 and ok3)}


def analyse(step5: str, stop: str, d4: str, cfg: dict, tol: float, progress=None) -> dict:
    cc = cm.load_config()
    rc = gm.load_config()                                  # the reader as it is now
    sets = {"S5": ps.Dataset("S5", step5, cfg["sessions"]["S5"], cfg), "STOP": ps.Dataset("STOP", stop, cfg["sessions"]["STOP"], cfg),
            "D4*": ps.Dataset("D4*", d4, cfg["sessions"]["D4*"], cfg)}
    rep: dict = {"zips": {k: {"name": Path(p).name, "sha256": sets[k].logs.sha256()} for k, p in (("S5", step5), ("STOP", stop), ("D4*", d4))},
                 "guard_all_development": all(set(d.guard.values()) == {"development"} for d in sets.values()), "tolerance_deg": tol,
                 "datasets": {k: {"runs": len(d.runs), "frames": sum(len(x["frames"]) for x in d.runs.values())} for k, d in sets.items()}}
    res: dict = {}
    ref_recs: dict = {}
    for v in VARIANTS:
        res[v["key"]] = {"name": v["name"]}
        parts = []
        for k, d in sets.items():
            recs = run_variant(d, v, rc, cc, cfg)
            if v["key"] == "ref":
                ref_recs[k] = recs
            sc = score(recs, tol)
            sc["diff"] = diff_vs_ref(recs, ref_recs[k])
            res[v["key"]][k] = sc
            parts.append(sc)
        res[v["key"]]["ALL"] = combine(parts)
        if progress:
            progress(v["name"])
    for v in VARIANTS[1:]:
        res[v["key"]]["criteria"] = criteria(res, v["key"])
    # frames received per window by people in view (the reference), for the frames of true POINT holds
    b2 = defaultdict(list)
    for k, recs in ref_recs.items():
        for r in recs:
            if r["cat"] == "POINT" and r["phase"] == "holding":
                b2[people_bucket(r["people"])].append(r["valid"])
    rep["valid_frames_by_people"] = {lab: {"frames": len(b2[lab]), "median": st.median(b2[lab]) if b2[lab] else None, "below_6": sum(1 for x in b2[lab] if x < 6)} for _, lab in PEOPLE}
    rep["variants"] = res
    return rep


def markdown(rep: dict) -> str:
    V, L = rep["variants"], []
    names = [v["key"] for v in VARIANTS]
    L += [f"## POINT frames (AUDIT.md 16.26 item 3): the reader as it is against the variants, development data only (guard: {'all development' if rep['guard_all_development'] else 'NOT ALL DEVELOPMENT'})", "",
          "Zips: " + "; ".join(f"{k} `{v['name']}` {v['sha256'][:12]}..." for k, v in rep["zips"].items()), "",
          "### 1. POINT read rate over the frames in the holding phase, and the minimum valid frames used", "",
          "| variant | " + " | ".join(f"{ds}: read / held (%), insufficient" for ds in ("S5", "STOP", "D4*")) + " | ALL: read / held (%) | insufficient (all) | min valid frames of a POINT read |", "|---|---|---|---|---|---|---|"]
    for k in names:
        row = [f"{V[k][ds]['read_point']}/{V[k][ds]['held_frames']} ({V[k][ds]['read_rate']} %), {V[k][ds]['insufficient']}" for ds in ("S5", "STOP", "D4*")]
        a = V[k]["ALL"]
        L.append(f"| {V[k]['name']} | " + " | ".join(row) + f" | {a['read_point']}/{a['held_frames']} ({a['read_rate']} %) | {a['insufficient']} | {a['valid_frames_used']['min']} |")
    L += ["", "### 2. Valid frames in the 1.0 s window by the number of people in view (reference; frames of true POINT holds)", "", "| people in view | frames | median valid frames | below 6 |", "|---|---|---|---|"]
    for lab, d in rep["valid_frames_by_people"].items():
        L.append(f"| {lab} | {d['frames']} | {d['median']} | {d['below_6']} |")
    L += ["", "### 3. Read rate by the number of people in view (all datasets): read / held", "", "| variant | " + " | ".join(lab for _, lab in PEOPLE) + " |", "|---|---|---|---|"]
    for k in names:
        L.append(f"| {V[k]['name']} | " + " | ".join(f"{V[k]['ALL']['by_people'][lab]['read']}/{V[k]['ALL']['by_people'][lab]['held']}" for _, lab in PEOPLE) + " |")
    L += ["", "### 4. Read rate by the angle between the pointed direction and the line of sight (all datasets): read / held", "", "| variant | " + " | ".join(lab for _, _, lab in ANGLE_BINS) + " |", "|---|---|---|---|---|---|"]
    for k in names:
        L.append(f"| {V[k]['name']} | " + " | ".join(f"{V[k]['ALL']['by_angle'][lab]['read']}/{V[k]['ALL']['by_angle'][lab]['held']}" for _, _, lab in ANGLE_BINS) + " |")
    L += ["", f"### 5. Accuracy of the read POINT frames by class of the true direction (tolerance {rep['tolerance_deg']:g} deg; all datasets): read, accurate share (%), wrong", "",
          "| variant | " + " | ".join(CLASSES) + " |", "|---|---|---|---|---|"]
    for k in names:
        L.append(f"| {V[k]['name']} | " + " | ".join(f"{V[k]['ALL']['classes'][c]['read']} read, {V[k]['ALL']['classes'][c]['accurate_share']} %, {V[k]['ALL']['classes'][c]['wrong']} wrong" for c in CLASSES) + " |")
    L += ["", "### 6. Side effects against the reference (frames whose reading changed: gained / lost), and false POINT readings", "",
          "| variant | STOP S5 | STOP STOP-sessions | STOP D4* | WAIT (all) | PROCEED (all) | false POINT: read / frames (%) |", "|---|---|---|---|---|---|---|"]
    for k in names:
        d = {ds: V[k][ds]["diff"] for ds in ("S5", "STOP", "D4*")}
        fp = V[k]["ALL"]["false_point"]
        wait = "{}/{}".format(sum(d[ds]["WAIT"]["gained"] for ds in d), sum(d[ds]["WAIT"]["lost"] for ds in d))
        pro = "{}/{}".format(sum(d[ds]["PROCEED"]["gained"] for ds in d), sum(d[ds]["PROCEED"]["lost"] for ds in d))
        L.append(f"| {V[k]['name']} | " + " | ".join(f"{d[ds]['STOP']['gained']}/{d[ds]['STOP']['lost']}" for ds in ("S5", "STOP", "D4*")) + f" | {wait} | {pro} | {fp['read_as_point']}/{fp['frames']} ({fp['rate']} %) |")
    L += ["", "### 7. The declared criteria", "", "| variant | (1) accuracy LEFT / FORWARD / RIGHT not below the reference | (2) no STOP reading changed | (3) false POINT not above | all three |", "|---|---|---|---|---|"]
    for k in names[1:]:
        c = V[k]["criteria"]
        L.append(f"| {V[k]['name']} | {'met' if c['1_accuracy_LEFT_FORWARD_RIGHT']['ok'] else 'NOT met'} | {'met' if c['2_no_STOP_changed']['ok'] else 'NOT met'} | "
                 f"{'met' if c['3_false_point_not_above']['ok'] else 'NOT met'} ({c['3_false_point_not_above']['ref']} -> {c['3_false_point_not_above']['now']} frames) | **{'met' if c['all_met'] else 'NOT met'}** |")
    return "\n".join(L)


def detail(step5: str, stop: str, d4: str, cfg: dict, tol: float, keys=("i3", "ii")) -> dict:
    """The frames behind the two numbers that decide the criteria: for each variant the POINT frames it reads that the reference does not and that are WRONG (class LEFT, FORWARD,
    RIGHT or BACK, both depth readings beyond the tolerance), and the false POINT frames (a POINT read where none is shown). One record each, with the people in view and the
    valid frames, the look, the clip, the angle to the line of sight."""
    cc = cm.load_config()
    rc = gm.load_config()
    sets = {"S5": ps.Dataset("S5", step5, cfg["sessions"]["S5"], cfg), "STOP": ps.Dataset("STOP", stop, cfg["sessions"]["STOP"], cfg),
            "D4*": ps.Dataset("D4*", d4, cfg["sessions"]["D4*"], cfg)}
    out: dict = {}
    refs = {k: run_variant(d, VARIANTS[0], rc, cc, cfg) for k, d in sets.items()}
    for key in keys:
        v = next(x for x in VARIANTS if x["key"] == key)
        out[key] = {"wrong_gained": [], "false_point": []}
        for k, d in sets.items():
            refmap = {r["key"]: r for r in refs[k]}
            for r in run_variant(d, v, rc, cc, cfg):
                base = refmap.get(r["key"])
                if r["cmd"] != "POINT" or base is None:
                    continue
                if r["cat"] == "POINT" and r["phase"] == "holding" and (r.get("err") is None or r["err"] > tol + 1e-9) and base["cmd"] != "POINT":
                    out[key]["wrong_gained"].append({"dataset": k, **{x: r.get(x) for x in ("key", "people", "valid", "n_frames", "class", "sight_angle", "truth_rel", "err", "look", "clip", "arm", "stopped")}, "ref_cmd": base["cmd"]})
                elif r["cat"] != "POINT":
                    out[key]["false_point"].append({"dataset": k, "cat": r["cat"], **{x: r.get(x) for x in ("key", "people", "valid", "n_frames", "look", "clip", "arm", "stopped")}})
    return out


def recompute(folder: Path) -> Path:
    """Recompute the criteria and the tables of a finished report from its report.json (the counts), writing report_recomputed.md / .json NEXT to it (nothing is overwritten)."""
    rep = json.loads((folder / "report.json").read_text(encoding="utf-8"))
    for v in VARIANTS[1:]:
        rep["variants"][v["key"]]["criteria"] = criteria(rep["variants"], v["key"])
    (folder / "report_recomputed.json").write_text(json.dumps(rep, indent=1, default=str), encoding="utf-8")
    (folder / "report_recomputed.md").write_text(markdown(rep) + "\n", encoding="utf-8")
    return folder / "report_recomputed.md"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--step5")
    ap.add_argument("--stop")
    ap.add_argument("--d4")
    ap.add_argument("--detail", action="store_true", help="list the wrong-and-newly-read and the false POINT frames of (i) floor 3 and (ii) (writes point_frames_v4_<time>_detail/)")
    ap.add_argument("--recompute", default=None, help="a finished folder: recompute the criteria from its report.json (new files next to it)")
    ap.add_argument("--label", default="")
    a = ap.parse_args(argv)
    if a.recompute:
        print(recompute(Path(a.recompute)).read_text(encoding="utf-8"))
        return 0
    if not (a.step5 and a.stop and a.d4):
        ap.error("--step5, --stop and --d4 are required (or --recompute FOLDER)")
    cfg = ps.load_config()
    tol = float(json.loads((HERE / "configs/v4/control.json").read_text(encoding="utf-8"))["dialog"]["branch_match_max_deg"])
    if a.detail:
        d = detail(a.step5, a.stop, a.d4, cfg, tol)
        out = HERE / "outputs" / f"point_frames_v4_{time.strftime('%Y%m%d_%H%M%S')}{'_' + a.label if a.label else ''}_detail"
        out.mkdir(parents=True, exist_ok=False)
        (out / "detail.json").write_text(json.dumps(d, indent=1, default=str), encoding="utf-8")
        for key, v in d.items():
            print(f"== {key}: newly read and wrong {len(v['wrong_gained'])}; false POINT {len(v['false_point'])}")
            for x in v["wrong_gained"]:
                print("  wrong:", x)
            for x in v["false_point"]:
                print("  false:", x)
        print(f"Folder: {out}")
        return 0
    rep = analyse(a.step5, a.stop, a.d4, cfg, tol, progress=lambda m: print("done:", m, flush=True))
    out = HERE / "outputs" / f"point_frames_v4_{time.strftime('%Y%m%d_%H%M%S')}{'_' + a.label if a.label else ''}"
    out.mkdir(parents=True, exist_ok=False)
    (out / "config_used").mkdir()
    for name in ("configs/v4/gesture_reader.json", "configs/v4/control.json", "configs/v4/experiments/proceed_stop_check.json"):
        (out / "config_used" / Path(name).name).write_bytes((HERE / name).read_bytes())
    md = markdown(rep)
    (out / "report.json").write_text(json.dumps(rep, indent=1, default=str), encoding="utf-8")
    (out / "report.md").write_text(md + "\n", encoding="utf-8")
    commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=HERE, capture_output=True, text=True).stdout.strip()
    (out / "run.json").write_text(json.dumps({"git_commit": commit, "zips": rep["zips"], "variants": [v["key"] for v in VARIANTS], "tolerance_deg": tol}, indent=1), encoding="utf-8")
    print(md)
    print(f"\nFolder: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
