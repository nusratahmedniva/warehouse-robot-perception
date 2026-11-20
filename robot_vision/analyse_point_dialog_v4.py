"""The safety condition of AUDIT.md 16.26.3: replay the dialog with variant (ii) (the POINT window stretched up to 2.0 s, 6 valid frames) on all development data and look for a WRONG
ANSWER ACCEPTED. EVALUATION CODE ONLY: it reads the workers' true commands and angles; inference code never imports it. It changes nothing in the reader (the variant is applied
for the replay only, analyse_point_frames_v4.variant_ctx). Everything it does is declared in AUDIT.md 16.26.3 before it ran.

(1) The step-5 asks (state `ask` of decisions.csv; window ask_window_s = 5.0 s): the commander is the person who shows a POINT in the window; each frame is labelled as the controller would
label it (hri_control_v4.resolve_point against the branches and the arrival road of the session's roadmap at the junction nearest the robot, branch_match_max_deg, the mirror-image
rule on for the detection-on sessions); the labels go to hri_control.GestureDialog with the controller's values (hold 0.5 s, none gap 0.3 s). The commander's true direction is the roadmap
target nearest to the true pointed world angle within the tolerance. Accepted and wrong = a wrong answer of kind (a).
(2) A POINT read from a person who does not show a POINT, kind (b): the stream of every person-track of every run of all three datasets (the step-5, the STOP sessions and the D4
stand-in) is fed to GestureDialog as a direction label (each depth reading its own stream); an acceptance whose hold contains a POINT reading of a frame whose true category is not POINT
is an answer accepted from a false POINT frame.
Limits (declared): single view (the second view and the re-approach are not replayed), the commander rule is not replayed, no safety stop is replayed.

Usage (from robot_vision/): python analyse_point_dialog_v4.py --step5 Z --stop Z --d4 Z [--label x]
Writes outputs/point_dialog_v4_<time>[_label]/ (report.json, report.md, run.json); never overwrites."""

from __future__ import annotations

import argparse
import json
import math
import subprocess
import time
from collections import Counter, defaultdict
from pathlib import Path

import analyse_point_frames_v4 as pf
import analyse_proceed_stop_v4 as ps
import commander_v4 as cm
import gesture_motion as gm
import hri_control as hc
import hri_control_v4 as hv

HERE = Path(__file__).resolve().parent
ROADMAPS = {"A1": "configs/v4/experiments/roadmap_a1.json", "B1": "configs/v4/experiments/roadmap_a1.json", "B1_off": "configs/v4/experiments/roadmap_a1.json",
            "A2_right": "configs/v4/experiments/roadmap_a2_right.json", "B2_right": "configs/v4/experiments/roadmap_a2_right.json",
            "B2_right_off": "configs/v4/experiments/roadmap_a2_right.json", "A2_left": "configs/v4/experiments/roadmap_a2_left.json", "A3": "configs/v4/roadmap.json"}
VARIANTS = tuple(v for v in pf.VARIANTS if v["key"] in ("ref", "ii"))


def wrap(a: float) -> float:
    return (a + 180.0) % 360.0 - 180.0


def dialog_values() -> dict:
    base, v4 = hv.load_control()
    g = base["dialog"]
    return {"hold": float(g["gesture_hold_s"]), "window": float(g["gesture_window_s"]), "max_asks": int(g["max_asks"]), "gap": float(g.get("max_none_gap_s", 0.0)),
            "tol": float(v4["dialog"]["branch_match_max_deg"]), "crosscheck": bool(v4["dialog"]["use_hand_crosscheck_as_tiebreak"])}


def asking_node(road: hc.Roadmap, x: float, z: float) -> str:
    return min((n for n, v in road.nodes.items() if v["kind"] in ("junction", hv.START)), key=lambda n: math.hypot(road.pos(n)[0] - x, road.pos(n)[1] - z))


def label_of(rec: dict, road: hc.Roadmap, node: str, dv: dict, mirror: bool) -> str:
    """The label the controller gives this frame: the branch a POINT reading resolves to, else NONE."""
    if rec["cmd"] != "POINT" or rec["point"] is None:
        return "NONE"
    dirs, arrival = hv.branch_directions(road, node)
    res = hv.resolve_point(rec["point"], dirs, arrival, rec["yaw"], dv["tol"], dv["crosscheck"], mirror)
    return res.command if res.command in hc.DIRECTIONS else "NONE"


def true_label(frames: list[dict], road: hc.Roadmap, node: str, tol: float) -> str:
    """The roadmap target (a branch command, or BACK for the arrival road) nearest to the true pointed world angle within tol; 'none' if no target is near."""
    dirs, arrival = hv.branch_directions(road, node)
    votes = Counter()
    for r in frames:
        if r["cat"] != "POINT" or r["phase"] != "holding" or "truth_rel" not in r:
            continue
        w = wrap(r["yaw"] + r["truth_rel"])
        targets = [(abs(wrap(w - y)), c) for c, y in dirs.items()] + ([(abs(wrap(w - arrival)), "BACK")] if arrival is not None else [])
        gap, c = min(targets)
        votes[c if gap <= tol else "none"] += 1
    return votes.most_common(1)[0][0] if votes else "none"


def feed(frames: list[dict], labels: list[str], dv: dict, t0: float):
    """GestureDialog over the frames of one person; returns (accepted label | None, index of the accepting frame, index of the first frame of the accepted hold)."""
    d = hc.GestureDialog(dv["hold"], dv["window"], dv["max_asks"], dv["gap"])
    d.begin_ask(t0)
    for i, (r, lab) in enumerate(zip(frames, labels)):
        ev = d.update(lab, r["t"], r["t"])
        if ev == "accepted":
            first = next((j for j, x in enumerate(frames) if x["t"] >= d.since - 1e-9), i)
            return d.accepted, i, first
        if ev in ("ask_again", "abort"):
            break
    return None, None, None


def ask_starts(ds: ps.Dataset, sname: str) -> list[tuple[int, float]]:
    out = []
    for run, (ts, vs) in ds.dec[sname].items():
        out += [(run, ts[i]) for i in range(1, len(ts)) if vs[i][1].startswith("ask") and not vs[i - 1][1].startswith("ask")]
    return out


def false_in_hold(frames: list[dict], first: int, last: int) -> bool:
    return any(frames[k]["cmd"] == "POINT" and frames[k]["cat"] != "POINT" for k in range(first, last + 1))


def replay_asks(ds: ps.Dataset, recs: list[dict], dv: dict) -> list[dict]:
    by_run: dict = defaultdict(lambda: defaultdict(list))
    for r in recs:
        by_run[(r["key"][0], r["key"][1])][r["tid"]].append(r)
    out = []
    for sname in ds.dec:
        road = hc.Roadmap(hc.load_json(ROADMAPS[sname]))
        mirror = not sname.endswith("_off")
        frames_by_run = {run: d["frames"] for (s, run), d in ds.runs.items() if s == sname}
        for run, t0 in ask_starts(ds, sname):
            fr = next((f for f in frames_by_run.get(run, []) if f["time_s"] >= t0), None)
            if fr is None:
                continue
            node = asking_node(road, fr["pose"]["x"], fr["pose"]["z"])
            persons = {tid: sorted((r for r in rs if t0 <= r["t"] <= t0 + dv["window"]), key=lambda r: r["t"]) for tid, rs in by_run[(sname, run)].items()}
            persons = {tid: rs for tid, rs in persons.items() if rs}
            shown = {tid: sum(r["cat"] == "POINT" for r in rs) for tid, rs in persons.items()}
            if not shown or max(shown.values()) == 0:
                continue
            cmd_tid = max(shown, key=shown.get)
            rs = persons[cmd_tid]
            acc, i_acc, i_first = feed(rs, [label_of(r, road, node, dv, mirror) for r in rs], dv, t0)
            truth = true_label(rs, road, node, dv["tol"])
            row = {"session": sname, "run": run, "t0": round(t0, 2), "node": node, "commander": cmd_tid, "frames": len(rs), "true": truth, "accepted": acc,
                   "right": (acc is not None and acc == truth), "wrong": (acc is not None and acc != truth),
                   "from_false_point": bool(acc is not None and false_in_hold(rs, i_first, i_acc)), "t_accept": None if acc is None else round(rs[i_acc]["t"] - t0, 2)}
            others = []
            for tid, ors in persons.items():
                if tid == cmd_tid or shown[tid] > 0:
                    continue
                a2, j_acc, j_first = feed(ors, [label_of(r, road, node, dv, mirror) for r in ors], dv, t0)
                if a2 is not None:
                    others.append({"tid": tid, "accepted": a2, "from_false_point": false_in_hold(ors, j_first, j_acc)})
            row["others_accepted"] = others
            out.append(row)
    return out


def stream_check(ds: ps.Dataset, recs: list[dict], dv: dict) -> dict:
    """(2): every person-track of every run, each depth reading as its own label stream (LEFT, FORWARD, RIGHT by the angle to the robot's forward axis; BACK is no answer)."""
    by: dict = defaultdict(list)
    for r in recs:
        by[(r["key"][0], r["key"][1], r["tid"])].append(r)
    n_tracks = acceptances = 0
    false_acc = []
    for (sname, run, tid), rs in by.items():
        rs = sorted(rs, key=lambda r: r["t"])
        n_tracks += 1
        for fam in ("away", "toward"):
            labels = []
            for r in rs:
                rel = (r["point"].rel_deg or {}).get(fam) if r["point"] is not None else None
                c = pf.class_of(rel) if rel is not None else "NONE"
                labels.append(c if c in ("LEFT", "FORWARD", "RIGHT") else "NONE")
            # restart the dialog after every acceptance so that several acceptances in a long run are all found
            start = 0
            while start < len(rs):
                acc, i_acc, i_first = feed(rs[start:], labels[start:], dv, rs[start]["t"])
                if acc is None:
                    break
                acceptances += 1
                if false_in_hold(rs, start + i_first, start + i_acc):
                    false_acc.append({"session": sname, "run": run, "tid": tid, "family": fam, "t": round(rs[start + i_acc]["t"], 2), "label": acc})
                start += i_acc + 1
    return {"person_tracks": n_tracks, "acceptances": acceptances, "from_false_point": false_acc}


def analyse(step5: str, stop: str, d4: str, cfg: dict) -> dict:
    cc = cm.load_config()
    rc = gm.load_config()
    dv = dialog_values()
    sets = {"S5": ps.Dataset("S5", step5, cfg["sessions"]["S5"], cfg), "STOP": ps.Dataset("STOP", stop, cfg["sessions"]["STOP"], cfg),
            "D4*": ps.Dataset("D4*", d4, cfg["sessions"]["D4*"], cfg)}
    rep: dict = {"dialog": dv, "guard_all_development": all(set(d.guard.values()) == {"development"} for d in sets.values()),
                 "zips": {k: {"name": Path(p).name, "sha256": sets[k].logs.sha256()} for k, p in (("S5", step5), ("STOP", stop), ("D4*", d4))}, "variants": {}}
    for v in VARIANTS:
        res: dict = {"name": v["name"], "asks": [], "streams": {}}
        for k, d in sets.items():
            recs = pf.run_variant(d, v, rc, cc, cfg)
            if k == "S5":
                res["asks"] = replay_asks(d, recs, dv)
            res["streams"][k] = stream_check(d, recs, dv)
            print("done:", v["key"], k, flush=True)
        rep["variants"][v["key"]] = res
    ref, ii = ({(a["session"], a["run"], a["t0"]): a for a in rep["variants"][key]["asks"]} for key in ("ref", "ii"))
    rec: dict = {"asks": len(ref), "recovered_right": [], "recovered_wrong": [], "lost": [], "changed_label": []}
    for k, a in ii.items():
        b = ref.get(k)
        if b is None:
            continue
        if a["accepted"] is not None and b["accepted"] is None:
            (rec["recovered_right"] if a["right"] else rec["recovered_wrong"]).append(a)
        elif a["accepted"] is None and b["accepted"] is not None:
            rec["lost"].append(b)
        elif a["accepted"] is not None and b["accepted"] is not None and a["accepted"] != b["accepted"]:
            rec["changed_label"].append({"ref": b, "ii": a})
    rep["recovered"] = rec
    wrong_ii = [a for a in rep["variants"]["ii"]["asks"] if a["wrong"]]
    false_ii = [a for a in rep["variants"]["ii"]["asks"] if a["from_false_point"]] + [o for a in rep["variants"]["ii"]["asks"] for o in a["others_accepted"] if o["from_false_point"]]
    streams_false = {k: v["from_false_point"] for k, v in rep["variants"]["ii"]["streams"].items()}
    rep["condition"] = {"wrong_direction_accepted": len(wrong_ii), "accepted_from_a_false_POINT_frame": len(false_ii) + sum(len(v) for v in streams_false.values()),
                        "wrong_direction_asks": wrong_ii, "false_point_streams": streams_false,
                        "holds": not wrong_ii and not false_ii and not any(streams_false.values())}
    return rep


def summary_rows(a: list[dict]) -> dict:
    return {"asks": len(a), "accepted": sum(x["accepted"] is not None for x in a), "right": sum(x["right"] for x in a), "wrong": sum(x["wrong"] for x in a),
            "from_false_point": sum(x["from_false_point"] for x in a), "others_accepted": sum(len(x["others_accepted"]) for x in a)}


def markdown(rep: dict) -> str:
    V, c = rep["variants"], rep["condition"]
    L = [f"## Safety condition of AUDIT.md 16.26.3: the dialog replayed with (ii) on all development data (guard: {'all development' if rep['guard_all_development'] else 'NOT ALL DEVELOPMENT'})", "",
         "Zips: " + "; ".join(f"{k} `{v['name']}` {v['sha256'][:12]}..." for k, v in rep["zips"].items()), "",
         f"Dialog values: hold {rep['dialog']['hold']} s, none gap {rep['dialog']['gap']} s, window {rep['dialog']['window']} s, tolerance {rep['dialog']['tol']} deg.", "",
         "### 1. The step-5 asks with a POINT commander (single view): accepted answers", "", "| variant | asks | accepted | right | WRONG | accepted from a false POINT frame | other persons accepted |", "|---|---|---|---|---|---|---|"]
    for k in ("ref", "ii"):
        s = summary_rows(V[k]["asks"])
        L.append(f"| {V[k]['name']} | {s['asks']} | {s['accepted']} | {s['right']} | {s['wrong']} | {s['from_false_point']} | {s['others_accepted']} |")
    r = rep["recovered"]
    L += ["", f"### 2. Asks recovered against the reference: **{len(r['recovered_right'])} right**, {len(r['recovered_wrong'])} wrong; lost (accepted by the reference, not by (ii)): {len(r['lost'])}; accepted by both with a different direction: {len(r['changed_label'])}", ""]
    for a in r["recovered_right"] + r["recovered_wrong"]:
        L.append(f"- {a['session']} run {a['run']} t0 {a['t0']} node {a['node']}: (ii) accepted {a['accepted']} after {a['t_accept']} s, true {a['true']}, {'right' if a['right'] else 'WRONG'}")
    L += ["", "### 3. Streams of every person-track of all three datasets (each depth reading its own label stream): acceptances and those from a false POINT frame", "",
          "| variant | S5 tracks / acceptances / from a false POINT | STOP sessions | D4* |", "|---|---|---|---|"]
    for k in ("ref", "ii"):
        L.append(f"| {V[k]['name']} | " + " | ".join(f"{V[k]['streams'][ds]['person_tracks']} / {V[k]['streams'][ds]['acceptances']} / {len(V[k]['streams'][ds]['from_false_point'])}" for ds in ("S5", "STOP", "D4*")) + " |")
    L += ["", f"### 4. The condition (any wrong answer accepted with (ii)?): wrong direction accepted **{c['wrong_direction_accepted']}**, accepted from a false POINT frame **{c['accepted_from_a_false_POINT_frame']}** -> "
          f"**{'HOLDS: nothing wrong was accepted' if c['holds'] else 'DOES NOT HOLD: stop and report'}**"]
    for a in c["wrong_direction_asks"]:
        L.append(f"- wrong: {a['session']} run {a['run']} t0 {a['t0']} node {a['node']}: accepted {a['accepted']}, true {a['true']}")
    for ds, lst in c["false_point_streams"].items():
        for x in lst:
            L.append(f"- false POINT accepted ({ds}): {x}")
    return "\n".join(L)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--step5", required=True)
    ap.add_argument("--stop", required=True)
    ap.add_argument("--d4", required=True)
    ap.add_argument("--label", default="")
    a = ap.parse_args(argv)
    rep = analyse(a.step5, a.stop, a.d4, ps.load_config())
    out = HERE / "outputs" / f"point_dialog_v4_{time.strftime('%Y%m%d_%H%M%S')}{'_' + a.label if a.label else ''}"
    out.mkdir(parents=True, exist_ok=False)
    md = markdown(rep)
    (out / "report.json").write_text(json.dumps(rep, indent=1, default=str), encoding="utf-8")
    (out / "report.md").write_text(md + "\n", encoding="utf-8")
    commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=HERE, capture_output=True, text=True).stdout.strip()
    (out / "run.json").write_text(json.dumps({"git_commit": commit, "zips": rep["zips"], "dialog": rep["dialog"]}, indent=1), encoding="utf-8")
    print(md)
    print(f"\nFolder: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
