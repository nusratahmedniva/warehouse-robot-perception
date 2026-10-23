"""v4 development evaluation: the gesture reader, the commander rule and the dialog scored against Unity's truth.
EVALUATION CODE ONLY (reads truth.jsonl through gesture_data.py); inference code never imports it.

Input, per session (repeatable --session UNITY BRIDGE; give the zoom-on and zoom-off sessions to compare them):
  UNITY  = Unity's trial folder: session.json, run_###/truth.jsonl (docs/protocol_v3.md)
  BRIDGE = the bridge guide run folder of the same session: v4_log.jsonl (one row per pan-tilt frame read in the READ
           state: the people with their readings, the commander choice with reasons, the label, the resolution, the zoom),
           python_trial_###.json (junction records), config_used/control.json (zoom on or off).

DEVELOPMENT DATA ONLY: before anything is computed, the avatar looks and animation clips of every run go through
data_splits_v4.guard_run; a run with test looks or clips, a mix, an unlisted name or a gesture without a logged clip name
is refused (SystemExit), with or without anything else.

Matching: a person in the pan-tilt view (bearing from the log) is matched to the truth worker whose true bearing from the
robot is nearest, within match_bearing_deg and not equally near to another (configs/v4/eval_dev.json). Truth rows are
joined to frames within truth_join_max_s (configs/v4/gesture_data.json).

Reported, always with coverage (anything that cannot be evaluated says not_evaluated, never a guess):
- gesture reading: confusion matrix shown (truth) vs read, per command accuracy among the frames the reader answered
  (coverage = share answered), false reads on frames where nothing was shown; per look, per distance bin, per zoom;
- POINT angle error: of the better of the two depth readings, and of the reading the roadmap resolved; share of ambiguous;
- correct branch: the branch the dialog accepted against the branch nearest the true pointed direction; answered / asked;
- commander accuracy, with and without bystanders (correct, wrong, no commander);
- time from the first "Which direction?" to the accepted gesture (and without the WAIT time).

Usage (from robot_vision/):
  python hri_eval_dev_v4.py --session outputs/trials_X outputs/bridge_guide_Y [--session ... ...] [--config configs/v4/eval_dev.json]
Writes a new folder <output_root>/hri_eval_dev_v4_<time>/ with eval.json, eval.md, config_used/ and run.json (git commit).
"""

from __future__ import annotations

import argparse
import json
import math
import statistics as st
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path

import data_splits_v4 as ds
import gesture_data as gd
import gesture_motion as gm
import hri_control as hc
import hri_control_v4 as hv

HERE = Path(__file__).resolve().parent
DEFAULT_CONFIG = "configs/v4/eval_dev.json"
GESTURES = ("POINT", "WAIT", "STOP")
READS = ("POINT", "WAIT", "STOP", "NONE", "insufficient_history")
NOT_EVALUATED = "not_evaluated"


def load_config(path: str | Path = DEFAULT_CONFIG) -> dict:
    p = Path(path)
    return json.loads((p if p.is_absolute() else HERE / p).read_text(encoding="utf-8"))


# ---------------------------------------------------------------- loading

@dataclass
class Run:
    session: str
    trial: int
    rows: list
    junctions: list
    truth: list
    zoom_on: bool
    looks: set = field(default_factory=set)
    clips: set = field(default_factory=set)

    @property
    def bystanders(self) -> bool:
        return len({r.worker_id for r in self.truth}) > 1

    @property
    def name(self) -> str:
        return f"{self.session}/run_{self.trial:03d}"


def load_sessions(pairs, gcfg: dict, splits: dict | None = None) -> list[Run]:
    """Read every run of every session and apply the development-only split guard BEFORE any metric is computed."""
    runs: list[Run] = []
    for unity, bridge in pairs:
        unity, bridge = Path(unity), Path(bridge)
        control = json.loads((bridge / "config_used" / "control.json").read_text(encoding="utf-8"))
        zoom_on = bool(control["zoom"]["enabled"])
        log: dict[int, list] = defaultdict(list)
        for line in (bridge / "v4_log.jsonl").read_text(encoding="utf-8").splitlines():
            if line.strip():
                row = json.loads(line)
                log[row["trial"]].append(row)
        for run_dir in sorted(unity.glob("run_[0-9][0-9][0-9]")):
            trial = int(run_dir.name[4:])
            truth = gd.load_truth(run_dir / "truth.jsonl", gcfg)
            py = bridge / f"python_trial_{trial:03d}.json"
            junctions = json.loads(py.read_text(encoding="utf-8")).get("junctions", []) if py.exists() else []
            run = Run(unity.name, trial, log.get(trial, []), junctions, truth, zoom_on)
            run.looks = {r.look for r in truth}
            run.clips = {c.clip for c in gd.build_clips(truth)}
            try:
                ds.guard_run(run.looks, run.clips, final_evaluation=False, splits=splits)
            except SystemExit as e:
                raise SystemExit(f"{run.name}: {e}") from None
            runs.append(run)
    return runs


# ---------------------------------------------------------------- frame table

def _bearing_to(robot: dict, x: float, z: float) -> float:
    return hc.wrap(hc.yaw_to(robot["x"], robot["z"], x, z) - robot["yaw_deg"])


def match_worker(bearing_deg: float, truth_bearings: dict, tol_deg: float) -> int | None:
    """The worker whose true bearing is nearest, within tol_deg and strictly nearer than the next; else None."""
    near = sorted((abs(hc.wrap(b - bearing_deg)), w) for w, b in truth_bearings.items())
    if not near or near[0][0] > tol_deg:
        return None
    if len(near) > 1 and near[1][0] - near[0][0] < 1e-9:
        return None
    return near[0][1]


def frame_table(run: Run, ecfg: dict, gcfg: dict) -> tuple[list, list]:
    """(entries, rows): one entry per person per frame with the truth of the matched worker; one record per frame with
    the commander outcome. Both carry the run, frame and what is needed to group them."""
    frames = [{"frame_index": i, "time_s": r["t"], "pose": r["robot"]} for i, r in enumerate(run.rows)]
    joined = gd.join(frames, run.truth, gcfg)
    by_frame: dict[int, list] = defaultdict(list)
    for lab in joined.labels:
        by_frame[lab["frame_index"]].append(lab)
    entries, rows = [], []
    for i, row in enumerate(run.rows):
        labs = by_frame.get(i, [])
        tb = {lab["worker_id"]: _bearing_to(row["robot"], lab["row"].x, lab["row"].z) for lab in labs}
        lab_of = {lab["worker_id"]: lab for lab in labs}
        matched = {}
        for p in row["persons"]:
            w = match_worker(p["bearing_deg"], tb, ecfg["match_bearing_deg"])
            matched[p["id"]] = w
            rd = p["reading"]
            e = {"run": run.name, "trial": run.trial, "frame": i, "t": row["t"], "person": p["id"], "worker": w,
                 "read": rd["command"], "zoom_on": run.zoom_on, "bystanders": run.bystanders, "point": rd.get("point"),
                 "truth": None, "phase": None, "look": None, "distance_m": None, "angle": None}
            if w is not None:
                t = lab_of[w]["row"]
                e.update(truth=t.true_command, phase=t.phase, look=t.look, distance_m=lab_of[w]["distance_m"],
                         angle=t.point_angle_deg, truth_commander=t.is_commander)
            entries.append(e)
        commander = [lab for lab in labs if lab["row"].is_commander and lab["row"].true_command != "NONE"]
        rec = {"run": run.name, "trial": run.trial, "frame": i, "bystanders": run.bystanders, "zoom_on": run.zoom_on,
               "junction": row["junction"], "truth_commander": commander[0]["worker_id"] if commander else None,
               "chosen_person": (row["commander"] or {}).get("commander"), "resolution": row.get("resolution"),
               "robot": row["robot"], "reason": (row["commander"] or {}).get("reason", ""),
               "truth_angle": commander[0]["row"].point_angle_deg if commander and commander[0]["row"].true_command == "POINT"
               and commander[0]["row"].phase == "holding" else None}
        rec["chosen_worker"] = matched.get(rec["chosen_person"]) if rec["chosen_person"] is not None else None
        rows.append(rec)
    return entries, rows


# ---------------------------------------------------------------- metrics

def _ratio(k: int, n: int):
    return round(k / n, 4) if n else NOT_EVALUATED


def accuracy_block(entries: list) -> dict:
    """Per truth command: frames, frames the reader answered (coverage), correct among the answered. Truth NONE gives the
    false-read rate. Frames with no matched worker are counted apart."""
    matched = [e for e in entries if e["truth"] is not None]
    conf: dict = {s: Counter() for s in GESTURES + ("NONE",)}
    for e in matched:
        conf[e["truth"]][e["read"]] += 1
    per = {}
    for s in GESTURES:
        n = sum(conf[s].values())
        answered = sum(conf[s][r] for r in GESTURES)
        correct = conf[s][s]
        per[s] = {"frames": n, "answered": answered, "coverage": _ratio(answered, n), "correct": correct,
                  "accuracy_of_answered": _ratio(correct, answered)}
    n_none = sum(conf["NONE"].values())
    false = sum(conf["NONE"][r] for r in GESTURES)
    return {"frames_matched": len(matched), "frames_unmatched": len(entries) - len(matched),
            "confusion": {s: {r: conf[s][r] for r in READS} for s in conf}, "per_command": per,
            "false_reads": {"frames_nothing_shown": n_none, "read_as_a_command": false, "rate": _ratio(false, n_none)}}


def group(entries: list, key, label_order=None) -> dict:
    """accuracy_block of the gesturing frames per key value (a look, a distance bin, a zoom setting)."""
    g = defaultdict(list)
    for e in entries:
        k = key(e)
        if k is not None and e["truth"] in GESTURES:
            g[k].append(e)
    keys = label_order or sorted(g)
    out = {}
    for k in keys:
        es = g.get(k, [])
        n = len(es)
        ans = sum(e["read"] in GESTURES for e in es)
        cor = sum(e["read"] == e["truth"] for e in es)
        out[str(k)] = {"frames": n, "answered": ans, "coverage": _ratio(ans, n), "correct": cor,
                       "accuracy_of_answered": _ratio(cor, ans)}
    return out


def distance_bin(e: dict, bins: list):
    d = e["distance_m"]
    if d is None:
        return None
    for lo, hi in zip(bins, bins[1:]):
        if lo <= d < hi:
            return f"{lo:g}-{hi:g} m"
    return f">= {bins[-1]:g} m" if d >= bins[-1] else None


def _stats(v: list) -> dict:
    if not v:
        return {"n": 0, "status": NOT_EVALUATED}
    return {"n": len(v), "mean": round(st.fmean(v), 3), "median": round(st.median(v), 3), "min": round(min(v), 3),
            "max": round(max(v), 3)}


def angle_block(entries: list, rows: list) -> dict:
    """POINT angle error against the true angle, on the frames where the truth is a POINT being held."""
    held = [e for e in entries if e["truth"] == "POINT" and e["phase"] == "holding"]
    read = [e for e in held if e["read"] == "POINT" and e["point"]]
    best = []
    for e in read:
        cands = [v for v in e["point"]["rel_deg"].values() if v is not None]
        if cands:
            best.append(min(abs(hc.wrap(c - e["angle"])) for c in cands))
    resolved, point_rows, ambiguous = [], 0, 0
    for r in rows:
        res = r["resolution"]
        if res and r["truth_angle"] is not None:
            point_rows += 1
            ambiguous += bool(res["ambiguous"])
            if res.get("rel_deg") is not None:
                resolved.append(abs(hc.wrap(res["rel_deg"] - r["truth_angle"])))
    return {"truth_point_frames_held": len(held), "read_as_point": len(read), "coverage": _ratio(len(read), len(held)),
            "error_deg_better_depth_reading": _stats(best), "error_deg_resolved_reading": _stats(resolved),
            "frames_with_a_resolution": point_rows, "resolved": len(resolved), "ambiguous": ambiguous,
            "ambiguous_share": _ratio(ambiguous, point_rows),
            "note": "ambiguous = the two depth readings of the arm fit two different branches of the roadmap (the arrival "
                    "direction is never a candidate); the remaining ambiguity is a limitation of one RGB camera"}


def _circular_mean(a: list) -> float:
    return gm.circular_mean(a)


def branch_block(runs: list, rows_by_run: dict, road: hc.Roadmap) -> dict:
    """Accepted branch against the branch nearest the true pointed direction (world), per junction record."""
    asked = accepted = correct = wrong = unknown = 0
    detail = []
    for run in runs:
        rows = rows_by_run[run.name]
        for rec in run.junctions:
            asked += 1
            if rec.get("result") != "accepted":
                detail.append({"run": run.name, "junction": rec["junction"], "result": rec.get("result"), "correct": None})
                continue
            accepted += 1
            worlds = [hc.wrap(r["robot"]["yaw_deg"] + r["truth_angle"]) for r in rows
                      if r["junction"] == rec["junction"] and r["truth_angle"] is not None]
            if not worlds:
                unknown += 1
                detail.append({"run": run.name, "junction": rec["junction"], "result": "accepted", "correct": NOT_EVALUATED})
                continue
            w = _circular_mean(worlds)
            dirs, arrival = hv.branch_directions(road, rec["junction"])
            options = [(abs(hc.wrap(w - y)), c) for c, y in dirs.items()] + ([(abs(hc.wrap(w - arrival)), "ARRIVAL")] if arrival is not None else [])
            true_branch = min(options)[1]
            ok = rec.get("read") == true_branch
            correct += ok
            wrong += not ok
            detail.append({"run": run.name, "junction": rec["junction"], "result": "accepted", "read": rec.get("read"),
                           "true_branch": true_branch, "correct": ok})
    scored = correct + wrong
    recs = [rec for run in runs for rec in run.junctions]
    second = [rec for rec in recs if "second_view_t" in rec]
    return {"second_view": {"asks_with_a_second_view": len(second),
                            "accepted_after_it": sum(rec.get("result") == "accepted" for rec in second),
                            "unresolved_after_it": sum(rec.get("result") != "accepted" for rec in second),
                            "share_of_asks": _ratio(len(second), asked)},
            "reapproached": {"asks": sum(1 for rec in recs if "reapproach" in rec), "share_of_asks": _ratio(
                sum(1 for rec in recs if "reapproach" in rec), asked)},
            "junction_asks": asked, "accepted": accepted, "answered_share": _ratio(accepted, asked), "scored": scored,
            "not_evaluated": unknown, "correct": correct, "correct_rate_of_scored": _ratio(correct, scored), "detail": detail}


def commander_block(rows: list) -> dict:
    """Per frame with a gesturing truth commander: was the chosen person that worker? Split by bystanders present."""
    out = {}
    for label, flag in (("with_bystanders", True), ("without_bystanders", False)):
        rs = [r for r in rows if r["bystanders"] == flag and r["truth_commander"] is not None]
        none = sum(r["chosen_person"] is None for r in rs)
        cor = sum(r["chosen_person"] is not None and r["chosen_worker"] == r["truth_commander"] for r in rs)
        wrong = len(rs) - none - cor
        out[label] = {"frames": len(rs), "no_commander": none, "correct": cor, "wrong": wrong,
                      "coverage": _ratio(cor + wrong, len(rs)), "accuracy_of_decided": _ratio(cor, cor + wrong)}
    return out


def timing_block(runs: list) -> dict:
    asked = [j for r in runs for j in r.junctions]
    done = [j for j in asked if j.get("result") == "accepted" and "t_ask_first" in j and "t_accept" in j]
    dt = [j["t_accept"] - j["t_ask_first"] for j in done]
    net = [j["t_accept"] - j["t_ask_first"] - j.get("waited_s", 0.0) for j in done]
    return {"junction_asks": len(asked), "accepted": len(done), "coverage": _ratio(len(done), len(asked)),
            "ask_to_accepted_s": _stats(dt), "ask_to_accepted_without_wait_s": _stats(net)}


def evaluate_block(runs: list, ecfg: dict, gcfg: dict, road: hc.Roadmap) -> dict:
    entries, rows, rows_by_run = [], [], {}
    for run in runs:
        e, r = frame_table(run, ecfg, gcfg)
        entries += e
        rows += r
        rows_by_run[run.name] = r
    bins = ecfg["distance_bins_m"]
    return {"runs": len(runs), "frames_read": len(rows), "gesture": accuracy_block(entries),
            "per_look": group(entries, lambda e: e["look"]),
            "per_distance": group(entries, lambda e: distance_bin(e, bins),
                                  [f"{lo:g}-{hi:g} m" for lo, hi in zip(bins, bins[1:])] + [f">= {bins[-1]:g} m"]),
            "angle": angle_block(entries, rows), "branch": branch_block(runs, rows_by_run, road),
            "commander": commander_block(rows), "timing": timing_block(runs)}


def evaluate(runs: list, ecfg: dict | None = None, gcfg: dict | None = None, road: hc.Roadmap | None = None) -> dict:
    ecfg = ecfg if ecfg is not None else load_config()
    gcfg = gcfg if gcfg is not None else gd.load_config()
    road = road if road is not None else hc.Roadmap(hc.load_json("configs/roadmap.json"))
    res = evaluate_block(runs, ecfg, gcfg, road)
    res["sessions"] = sorted({r.session for r in runs})
    res["per_zoom"] = {label: evaluate_block([r for r in runs if r.zoom_on == flag], ecfg, gcfg, road) if any(
        r.zoom_on == flag for r in runs) else NOT_EVALUATED for label, flag in (("zoom_on", True), ("zoom_off", False))}
    res["splits"] = "development looks and clips only (data_splits_v4.guard_run)"
    res["note"] = ("Every accuracy is reported with its coverage. NONE and insufficient_history readings are coverage, not "
                   "errors. Numbers from the simulator or from a handful of runs are a check of this script, not a result.")
    return res


# ---------------------------------------------------------------- report

def _acc_table(title: str, table: dict) -> list:
    L = [f"**{title}**", "", "| group | frames | answered | coverage | correct | accuracy of answered |", "|---|---|---|---|---|---|"]
    for k, v in table.items():
        L.append(f"| {k} | {v['frames']} | {v['answered']} | {v['coverage']} | {v['correct']} | {v['accuracy_of_answered']} |")
    return L + [""]


def markdown(res: dict) -> str:
    g = res["gesture"]
    L = ["# v4 development evaluation", "", f"Sessions: {', '.join(res['sessions'])}. {res['runs']} runs, {res['frames_read']} frames read "
         f"in the READ state. {res['splits']}.", "", res["note"], "", "## Gesture reading", "",
         f"Frames matched to a truth worker: {g['frames_matched']} (unmatched: {g['frames_unmatched']}).", "",
         "| shown \\ read | " + " | ".join(READS) + " |", "|---|" + "---|" * len(READS)]
    for s, c in g["confusion"].items():
        L.append(f"| {s} | " + " | ".join(str(c[r]) for r in READS) + " |")
    L += [""] + _acc_table("Per command", {k: v for k, v in g["per_command"].items()})
    f = g["false_reads"]
    L += [f"False reads: {f['read_as_a_command']} of {f['frames_nothing_shown']} frames where nothing was shown (rate {f['rate']}).", ""]
    L += _acc_table("Per look", res["per_look"]) + _acc_table("Per distance", res["per_distance"])
    a = res["angle"]
    L += ["## POINT angle", "", f"Held POINT frames {a['truth_point_frames_held']}, read as POINT {a['read_as_point']} (coverage {a['coverage']}).",
          f"Error of the better depth reading (deg): {a['error_deg_better_depth_reading']}.",
          f"Error of the roadmap-resolved reading (deg): {a['error_deg_resolved_reading']}.",
          f"Frames with a resolution {a['frames_with_a_resolution']}: resolved {a['resolved']}, ambiguous {a['ambiguous']} (share {a['ambiguous_share']}).", "", a["note"], ""]
    b = res["branch"]
    sv, ra = b["second_view"], b["reapproached"]
    L += ["## Branch", "", f"Asks {b['junction_asks']}, accepted {b['accepted']} (answered share {b['answered_share']}); scored {b['scored']}, "
          f"correct {b['correct']} (rate {b['correct_rate_of_scored']}); not evaluated {b['not_evaluated']}.",
          f"Second view (two depth readings fitted two branches): {sv['asks_with_a_second_view']} asks (share {sv['share_of_asks']}), "
          f"accepted after it {sv['accepted_after_it']}, unresolved {sv['unresolved_after_it']}. Re-approached the commander: {ra['asks']} asks.",
          "", "## Commander", ""]
    for k, v in res["commander"].items():
        L.append(f"- {k}: {v['frames']} frames with a gesturing truth commander; correct {v['correct']}, wrong {v['wrong']}, "
                 f"none {v['no_commander']}; coverage {v['coverage']}, accuracy of decided {v['accuracy_of_decided']}.")
    t = res["timing"]
    L += ["", "## Time from the ask to the accepted gesture", "", f"Accepted {t['accepted']} of {t['junction_asks']} asks (coverage {t['coverage']}). "
          f"Seconds: {t['ask_to_accepted_s']}; without WAIT time: {t['ask_to_accepted_without_wait_s']}.", "", "## Zoom on vs off", ""]
    for label, blk in res["per_zoom"].items():
        if blk == NOT_EVALUATED:
            L.append(f"- {label}: {NOT_EVALUATED} (no session)")
            continue
        pc = blk["gesture"]["per_command"]
        L.append(f"- {label}: {blk['runs']} runs; " + "; ".join(
            f"{s} answered {v['answered']}/{v['frames']} (coverage {v['coverage']}) accuracy {v['accuracy_of_answered']}" for s, v in pc.items())
            + f"; ask to accepted median {blk['timing']['ask_to_accepted_s'].get('median', NOT_EVALUATED)} s")
    return "\n".join(L) + "\n"


def main(argv=None) -> None:
    import decision_io as dio

    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--session", nargs=2, action="append", required=True, metavar=("UNITY", "BRIDGE"))
    ap.add_argument("--config", default=DEFAULT_CONFIG)
    a = ap.parse_args(argv)
    cfg_path = dio.resolve(a.config)
    ecfg, gcfg = load_config(cfg_path), gd.load_config()
    pairs = [(dio.resolve(u), dio.resolve(b)) for u, b in a.session]
    runs = load_sessions(pairs, gcfg)
    if not runs:
        raise SystemExit("no run_### folders with truth.jsonl found")
    res = evaluate(runs, ecfg, gcfg)
    out = dio.new_run_dir({"paths": {"output_root": "outputs"}}, "hri_eval_dev_v4")
    (out / "config_used").mkdir()
    for p in (cfg_path, dio.resolve(gd.DEFAULT_CONFIG), dio.resolve(ds.DEFAULT)):
        (out / "config_used" / p.name).write_bytes(p.read_bytes())
    dio.write_json(out / "eval.json", res)
    dio.write_json(out / "run.json", {"git": dio.git_info(), "sessions": [[u.name, b.name] for u, b in pairs]})
    (out / "eval.md").write_text(markdown(res), encoding="utf-8")
    print(markdown(res))
    print(f"Folder: {out}")


if __name__ == "__main__":
    main()
