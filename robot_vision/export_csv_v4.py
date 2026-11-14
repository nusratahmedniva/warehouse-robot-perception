"""v4 CSV export for experiments A and B (AUDIT.md section 16). EVALUATION CODE ONLY: it reads goal B, the truth rows and the true
gesture of every worker; inference code never imports it (a test checks that).

From session folders (the pair UNITY + BRIDGE of hri_eval_dev_v4.py: Unity's trial folder with session.json, truth_run###.json and
run_###/truth.jsonl, and the bridge run folder with v4_log.jsonl, python_trial_###.json and config_used/) it writes

  runs.csv     one row per run: experiment, set, seed, looks, route, goal, outcome, time, trail against optimal, stops, collisions,
               lies given / detected / corrected / fooled, and which lie-detection switches were on;
  dialogs.csv  one row per ask (every time "Which direction?" was shown): junction, worker, look, the command shown and whether it was
               truthful, the command read, correct, time to read, distance, and the controller's decision with its reason.

Which columns, in which order and under which header is in configs/v4/experiments/export_csv.json (so they can be matched to the faculty's list
later without touching code); a field name that is not known is refused with the list of known fields. Development data only
(hri_eval_dev_v4.load_sessions runs data_splits_v4.guard_run before anything is read), except in the FINAL mode below.

FINAL mode (2026-11-14, AUDIT.md 16.15; the finals of experiments A and B, evaluation code):
  --final --setting S --session UNITY BRIDGE [...]   one setting's runs.csv and dialogs.csv. Refused unless configs/v4/frozen.json is frozen with
        every hash matching, the leak test passed, every run lies wholly in the TEST split (guard_run with final_evaluation) and is what setting S
        says (final_guard_v4.check_setting), and S was not exported before (its own marker FINAL_EXPORT_DONE.json, written last). Writes
        <output_root>/export_csv_v4_final_<S>_<time>/ with runs.csv, dialogs.csv, summary.json (the counts of the setting: SUCCESS with a Wilson
        95 % interval, failure kinds, medians, lies, stops), export.json, config_used/, run.json. No threshold is changed here.
  --final-combine FOLDER [...]   ONE combined table over the per-setting export folders (each with its marker, no setting twice): every setting,
        then A vs B per scenario, B detection on vs off, A2 right vs left, every rate with its count and a Wilson 95 % interval, the difference
        in percentage points with a Newcombe (Wilson-based) 95 % interval, only as a description. Derived from the exports (no test data is read again): rerunnable into a new folder.

Definitions (AUDIT.md 16.3), per run:
  lies given     lying gestures in truth.jsonl (gesture_truthful false): one per clip;
  lies detected  lying asks whose answer the robot rejected (impossible direction), outvoted (second opinion) or withdrew (backtrack);
  lies corrected detected lying asks after which the visit ended with the true branch (the branch toward B; BACK when B cannot be
                 reached from the node);
  lies fooled    lying asks whose answer the robot acted on and that was not the true branch.
A lie that is neither detected nor fooled (no reading, or read as the right branch by the mirror ambiguity of the pointing arm) is only
"given". Per ask: `correct` = the command read is the command shown (the reader was right); `correct_direction` = the branch read is
the branch shown; `correct_branch` = the branch read is the true branch toward B. Anything that cannot be evaluated is empty, never a guess.

Usage (from robot_vision/):
  python export_csv_v4.py --session outputs/trials_X outputs/bridge_Y [--session ... ...] [--config configs/v4/experiments/export_csv.json]
Writes a new folder <output_root>/export_csv_v4_<time>/ with runs.csv, dialogs.csv, export.json, config_used/ and run.json (git commit).
"""

from __future__ import annotations

import argparse
import csv
import json
import math
from collections import Counter, defaultdict
from pathlib import Path

import data_splits_v4 as ds
import gesture_data as gd
import gt_path
import hri_control as hc
import hri_control_v4 as hv
import hri_eval_dev_v4 as ev

HERE = Path(__file__).resolve().parent
DEFAULT_CONFIG = "configs/v4/experiments/export_csv.json"
COMPASS = {"FORWARD": 0.0, "RIGHT": 90.0, "BACK": 180.0, "LEFT": -90.0}

RUN_FIELDS = {
    "experiment": "A1 to A4 / B1 to B4 (session.json 'experiment'; empty when the session does not say)",
    "set": "A (all truthful) or B (workers lie), from session.json",
    "lie_probability": "P(a gesture is a lie) of the session (session.json); empty when not recorded",
    "session": "name of Unity's session folder", "run": "session/run_###", "trial": "trial number",
    "seed": "run seed (truth_run###.json)", "looks": "avatar looks seen in the run, joined",
    "route": "the nodes the robot arrived at, A>J1>...", "goal": "goal B (truth_run###.json b_name)",
    "outcome": "SUCCESS / FAILURE", "failure_reason": "none / collision / timeout / aborted / wrong_goal",
    "time_s": "run time (truth_run###.json total_s)", "trail_m": "length of the trail",
    "optimal_m": "length of the optimal path", "trail_over_optimal": "trail_m / optimal_m",
    "trail_source": "where trail and optimal come from: gt_path (grid, optimal_path.json, trail.csv) or road_route (simulator: travelled and the road length)",
    "stops": "safety stops that began (the controller's person-in-path / stale-perception stops)",
    "stop_s": "seconds spent in safety stops", "collisions": "collisions (truth_run###.json)",
    "closest_person_m": "closest approach to any person", "final_distance_m": "final distance from B",
    "asks": "number of asks (questions shown)", "dialogs": "number of dialogs (people asked, node visits counted separately)",
    "second_opinions": "dialogs started with a further person (ask_next)", "rejections": "answers rejected as impossible",
    "backtracks": "backtracks started", "lies_given": "see Definitions", "lies_detected": "see Definitions",
    "lies_corrected": "see Definitions", "lies_fooled": "see Definitions",
    "setting": "lie-detection setting label of the session (session.json 'lie_detection': off, on, a, b, bc, abc, mirror), empty when not recorded",
    "final_setting": "the final setting (A1 ... B4_off) when exported in final mode (session.json 'final_setting'), empty otherwise",
    "max_distance_from_optimal_m": "largest distance of the trail from the optimal path (gt_path); empty without gt_path files",
    "share_within_corridor": "share of trail points within gt_path's near distance of the optimal path (the corridor); empty without gt_path files",
    "watchdog_stops": "Unity watchdog stops while this run was running (bridge messages.jsonl); empty when the bridge log has no telemetry of the run (B11(a): a result)",
    "second_opinion_on": "the switch of the control config used", "reject_impossible_on": "the switch", "backtrack_on": "the switch",
}
DIALOG_FIELDS = {
    "experiment": "as in runs.csv", "set": "as in runs.csv", "session": "", "run": "", "trial": "", "seed": "",
    "junction": "node of the ask", "visit": "n-th arrival at that node (a backtrack return is a new visit)",
    "dialog": "n-th person asked at this visit (1 = the first)", "worker": "truth worker id of the commander in the ask window",
    "look": "that worker's avatar look", "ask": "ask number within the dialog (1 or 2)", "serial": "ask number within the run",
    "t_s": "time of the ask from the start of the run", "command_shown": "true command in the ask window (POINT / PROCEED / WAIT / STOP / NONE)",
    "direction_shown": "LEFT / FORWARD / RIGHT / BACK relative to the arrival direction (POINT from the true angle, PROCEED = FORWARD)",
    "branch_shown": "direction_shown if the node has a branch there, else 'none' (a wall, the arrival road)",
    "truthful": "gesture_truthful of the commander in the window (false = a lie); empty when not recorded",
    "command_read": "the reader's last command for the chosen commander in the window", "branch_read": "the branch the robot read (accepted answer, else the last label)",
    "true_branch": "branch toward B from the node (BACK when B cannot be reached from it)", "correct": "command_read == command_shown",
    "correct_direction": "branch_read == branch_shown", "correct_branch": "branch_read == true_branch",
    "time_to_read_s": "from the ask to the accepted (or rejected) answer; empty when none", "distance_m": "true robot-to-worker distance at the ask",
    "distance_est_m": "the robot's 360-camera estimate at the ask", "decision": "accepted / rejected:<reason> / unclear",
    "decision_reason": "the controller's logged reasons for this ask", "outvoted": "the answer was outvoted by the others (second opinion)",
    "withdrawn": "the answer was withdrawn by a backtrack", "final_branch": "the branch the robot took at this visit",
    "arrival_candidate": "true when one of the two depth readings (the pointed direction and its mirror image) of the frames that gave branch_read, or of the "
                         "ask's frames when nothing was accepted, was the arrival road; empty when no frame carried a resolution",
}


def load_config(path: str | Path = DEFAULT_CONFIG) -> dict:
    p = Path(path)
    return json.loads((p if p.is_absolute() else HERE / p).read_text(encoding="utf-8"))


def check_columns(cfg: dict) -> None:
    for table, known in (("runs", RUN_FIELDS), ("dialogs", DIALOG_FIELDS)):
        names = [c["field"] for c in cfg[table]]
        bad = [n for n in names if n not in known]
        if bad:
            raise SystemExit(f"export_csv config: unknown field(s) {bad} in '{table}'; known fields: {sorted(known)}")
        if len(set(names)) != len(names):
            raise SystemExit(f"export_csv config: a field is listed twice in '{table}'")


# ---------------------------------------------------------------- helpers

def _wrap(a: float) -> float:
    return hc.wrap(a)


def _json(path: Path):
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else None


def compass_of(world_yaw: float, heading: float) -> str:
    d = _wrap(world_yaw - heading)
    return min(COMPASS, key=lambda k: abs(_wrap(d - COMPASS[k])))


def _mean_angle(a: list[float]) -> float:
    return math.degrees(math.atan2(sum(math.sin(math.radians(x)) for x in a), sum(math.cos(math.radians(x)) for x in a)))


def lying_clips(truth: list) -> tuple[int, int]:
    """(lying gestures, gestures) in truth.jsonl; gestures without the field count as neither (None)."""
    by_line = {r.line: r for r in truth}
    lies = total = 0
    for c in gd.build_clips(truth):
        flags = {by_line[ln].gesture_truthful for ln in c.row_lines}
        if None in flags:
            continue
        total += 1
        lies += flags == {False}
    return lies, total


def _fmt(v, empty: str = ""):
    if v is None:
        return empty
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, float):
        return f"{v:.6g}" if abs(v) < 1e6 else f"{v:.1f}"
    return str(v)


# ---------------------------------------------------------------- one run

def _road_for(run: ev.Run, cache: dict) -> hc.Roadmap:
    key = str(run.bridge_dir)
    if key not in cache:
        mp = _json(Path(run.bridge_dir) / "config_used" / "map_used.json")
        if mp is not None:
            cache[key] = hc.Roadmap(mp)
        else:
            control = _json(Path(run.bridge_dir) / "config_used" / "control.json")
            cache[key] = hv.load_roadmap(hv.roadmap_path(control))
    return cache[key]


def run_tables(run: ev.Run, ecfg: dict, road: hc.Roadmap, watchdog: dict | None = None) -> tuple[dict, list[dict]]:
    """(the runs.csv row as a dict of every known field, the dialogs.csv rows) of one run. watchdog = the counts of the run's bridge
    folder (hri_eval_final_v4.bridge_watchdog_counts), None when it has no messages.jsonl."""
    unity, bridge = Path(run.unity_dir), Path(run.bridge_dir)
    session = _json(unity / "session.json") or {}
    truth_run = _json(unity / f"truth_run{run.trial:03d}.json") or {}
    py = _json(bridge / f"python_trial_{run.trial:03d}.json") or {}
    control = _json(bridge / "config_used" / "control.json") or {}
    ld = control.get("lie_detection", {})
    v4 = py.get("v4", {})
    decisions = v4.get("decisions", [])
    goal = truth_run.get("b_name") or None
    t0_run = float((_json(unity / f"run_{run.trial:03d}" / "run.json") or {}).get("run_start_s", truth_run.get("t_start", 0.0)))
    phases = ecfg["accuracy_phases"]

    by_serial: dict[int, list] = defaultdict(list)
    for d in decisions:
        by_serial[d["serial"]].append(d)
    gos = [d for d in decisions if d["event"] == "go"]
    outvoted = {v["serial"] for g in gos for v in g.get("votes", []) if v["branch"] != g["branch"]}
    withdrawn = {d["withdrawn_serial"] for d in decisions if d["event"] == "backtrack"}

    def final_branch(node: str, t_from: float) -> str | None:
        nxt = [g for g in gos if g["node"] == node and g["t"] >= t_from - 1e-6]
        return nxt[0]["branch"] if nxt else None

    def final_after_withdrawal(serial: int) -> str | None:
        bt = next((d for d in decisions if d["event"] == "backtrack" and d["withdrawn_serial"] == serial), None)
        if bt is None:
            return None
        return final_branch(bt["to"], bt["t"])

    rows: list[dict] = []
    seen_nodes: Counter = Counter()
    prev = None
    serial_lie: dict[int, bool] = {}
    for rec in run.junctions:
        node = rec["junction"]
        opinion = rec.get("opinion", 1)
        if not (prev is not None and prev["junction"] == node and opinion > 1):
            seen_nodes[node] += 1
        prev = rec
        t_start, t_end = rec.get("t_start", 0.0), rec.get("t_end", math.inf)
        true_branch = None
        if goal:
            true_branch = road.command_toward(node, goal)
            true_branch = "BACK" if true_branch == "NONE" else true_branch
        heading = hv.heading_in(road, node)
        dirs, _ = hv.branch_directions(road, node)
        crow_all = ev._commander_rows(run, t_start, t_end)
        log = rec.get("asks_log", [])
        for k, a in enumerate(log):
            t0 = a["t"]
            t1 = log[k + 1]["t"] if k + 1 < len(log) else t_end
            last = k + 1 == len(log)
            arow = ev._commander_rows(run, t0, t1)
            worker = Counter(r.worker_id for r in arow).most_common(1)[0][0] if arow else None
            arow = [r for r in arow if r.worker_id == worker]            # the tick the question is shown may still carry the previous commander
            shown = ev._shown(arow, phases)
            hold = [r.point_angle_deg for r in arow if r.phase in phases and r.true_command == "POINT"]
            direction = ""
            if shown == "PROCEED":
                direction = "FORWARD"
            elif shown == "POINT" and hold and heading is not None:
                direction = compass_of(_wrap(a["robot"]["yaw_deg"] + _mean_angle(hold)), heading)
            branch_shown = (direction if road.next(node, direction) is not None else "none") if direction else ""
            flags = {r.gesture_truthful for r in arow if r.true_command != "NONE" and r.phase in phases}
            truthful = None if (not flags or None in flags) else (False not in flags)
            serial_lie[a["serial"]] = truthful is False
            evs = by_serial.get(a["serial"], [])
            rejected = next((e for e in evs if e["event"] == "answer_rejected"), None)
            accepted = rec.get("result") == "accepted" and last
            decision = f"rejected:{rejected['reason']}" if rejected else ("accepted" if accepted else "unclear")
            read_cmd = ev._read_in(run, t0, t1)
            window = [r for r in run.rows if t0 - 1e-9 <= r["t"] <= t1 + 1e-9 and r.get("resolution")]
            if accepted:
                branch_read = rec.get("read")
            else:
                labels = [r["label"] for r in run.rows if t0 - 1e-9 <= r["t"] <= t1 + 1e-9 and r.get("label") in hc.DIRECTIONS]
                branch_read = labels[-1] if labels else "NONE"
            if rejected:
                branch_read = "NONE"
            used = [r for r in window if r.get("label") == branch_read] if branch_read in hc.DIRECTIONS else window
            arrival_candidate = (any(c["target"] == "ARRIVAL" for r in used for c in r["resolution"]["candidates"])
                                 if any(r["resolution"]["candidates"] for r in used) else None)
            t_read = rec.get("t_accept") if accepted else (rejected["t"] if rejected else None)
            true_d, look = ev._true_distance(run, t0, a["robot"])
            est = a.get("distance_est_m", -1.0)
            rows.append({
                "junction": node, "visit": seen_nodes[node], "dialog": opinion, "worker": worker,
                "look": arow[0].look if arow else (crow_all[0].look if crow_all else look), "ask": a.get("ask"),
                "serial": a["serial"], "t_s": round(t0 - t0_run, 3), "command_shown": shown, "direction_shown": direction,
                "branch_shown": branch_shown, "truthful": truthful, "command_read": read_cmd, "branch_read": branch_read,
                "true_branch": true_branch,
                "correct": (read_cmd == shown) if shown != "NONE" or read_cmd != "NONE" else None,
                "correct_direction": (branch_read == branch_shown) if branch_shown in hc.DIRECTIONS and branch_read else None,
                "correct_branch": (branch_read == true_branch) if (branch_read in hc.DIRECTIONS and true_branch) else None,
                "time_to_read_s": round(t_read - t0, 3) if t_read is not None else None,
                "distance_m": round(true_d, 3) if true_d is not None else None,
                "distance_est_m": est if est is not None and est >= 0 else None, "decision": decision,
                "decision_reason": "; ".join(f"{e['event']}: {e['reason']}" for e in evs if e["event"] != "answer_accepted") or
                                   ("accepted" if accepted else ""),
                "outvoted": a["serial"] in outvoted, "withdrawn": a["serial"] in withdrawn,
                "final_branch": final_branch(node, t0), "arrival_candidate": arrival_candidate, "_true": true_branch,
            })
    # lies per ask
    detected = corrected = fooled = 0
    for r in rows:
        if r["truthful"] is not False:
            continue
        det = r["decision"].startswith("rejected") or r["outvoted"] or r["withdrawn"]
        detected += det
        if det:
            end = final_after_withdrawal(r["serial"]) if r["withdrawn"] else r["final_branch"]
            corrected += bool(end is not None and end == r["_true"])
        elif r["decision"] == "accepted" and r["final_branch"] == r["branch_read"] and r["branch_read"] != r["_true"]:
            fooled += 1
    n_lies, n_gestures = lying_clips(run.truth)
    route = v4.get("route") or [j["junction"] for j in run.junctions]
    trail_m = optimal_m = max_dist = share = None
    source = ""
    run_dir = unity / f"run_{run.trial:03d}"
    if gt_path.has_v4_files(run_dir):
        meas = gt_path.evaluate_run(run_dir)["measures"]
        trail_m, optimal_m, source = meas.get("trail_length_m"), meas.get("optimal_length_m"), "gt_path"
        max_dist, share = meas.get("max_distance_from_optimal_m"), meas.get("share_within_near_distance")
    elif truth_run.get("optimal_m") is not None:
        trail_m, optimal_m, source = truth_run.get("travelled_m"), truth_run["optimal_m"], "road_route"
    run_row = {
        "experiment": session.get("experiment", truth_run.get("experiment")), "set": session.get("set", truth_run.get("set")),
        "lie_probability": session.get("lie_probability"), "setting": session.get("lie_detection"),
        "final_setting": session.get("final_setting"), "session": run.session, "run": run.name, "trial": run.trial,
        "seed": truth_run.get("seed"), "looks": "+".join(sorted(run.looks)), "route": ">".join(route), "goal": goal,
        "outcome": truth_run.get("outcome"), "failure_reason": truth_run.get("failure_reason"), "time_s": truth_run.get("total_s"),
        "trail_m": trail_m, "optimal_m": optimal_m, "max_distance_from_optimal_m": max_dist, "share_within_corridor": share,
        "watchdog_stops": (watchdog["per_trial"].get(run.trial, 0) if watchdog is not None and run.trial in watchdog["trials_seen"] else None),
        "trail_over_optimal": round(trail_m / optimal_m, 4) if trail_m is not None and optimal_m else None, "trail_source": source,
        "stops": v4.get("safety_stops"), "stop_s": py.get("safety_stop_s"), "collisions": truth_run.get("collisions"),
        "closest_person_m": truth_run.get("closest_human_m"), "final_distance_m": truth_run.get("final_distance_to_b_m"),
        "asks": len(rows), "dialogs": len(run.junctions),
        "second_opinions": sum(d["event"] == "ask_next" for d in decisions),
        "rejections": sum(d["event"] == "answer_rejected" for d in decisions),
        "backtracks": sum(d["event"] == "backtrack" for d in decisions),
        "lies_given": n_lies if n_gestures else None, "lies_detected": detected if n_gestures else None,
        "lies_corrected": corrected if n_gestures else None, "lies_fooled": fooled if n_gestures else None,
        "second_opinion_on": ld.get("second_opinion"), "reject_impossible_on": ld.get("reject_impossible"),
        "backtrack_on": ld.get("backtrack"),
    }
    context = {k: run_row[k] for k in ("experiment", "set", "session", "run", "trial", "seed")}
    for r in rows:
        r.pop("_true", None)
        r.update(context)
    return run_row, rows


def build_tables(runs: list, ecfg: dict | None = None) -> tuple[list[dict], list[dict]]:
    import hri_eval_final_v4 as ef            # lazy: hri_eval_final_v4 imports this module
    ecfg = ecfg if ecfg is not None else ev.load_config()
    roads: dict = {}
    wd: dict = {}
    run_rows, dialog_rows = [], []
    for run in runs:
        key = str(run.bridge_dir)
        if key not in wd:                      # one read of each bridge log, not one per run
            wd[key] = ef.bridge_watchdog_counts(Path(run.bridge_dir)) if run.bridge_dir is not None else None
        rr, dr = run_tables(run, ecfg, _road_for(run, roads), wd[key])
        run_rows.append(rr)
        dialog_rows += dr
    return run_rows, dialog_rows


# ---------------------------------------------------------------- writing

def write_csv(path: Path, rows: list[dict], columns: list[dict], empty: str = "") -> None:
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow([c.get("header", c["field"]) for c in columns])
        for r in rows:
            w.writerow([_fmt(r.get(c["field"]), empty) for c in columns])


# ---------------------------------------------------------------- the numbers of one setting (final mode, and the final evaluation)

FAILURE_KINDS = ("collision", "timeout", "aborted", "wrong_goal")


def _wilson(k: int, n: int, z: float) -> dict:
    import hri_analysis as ha
    if n == 0:
        return {"k": k, "n": n, "ratio": ev.NOT_EVALUATED, "wilson95": ev.NOT_EVALUATED}
    lo, hi = ha.wilson(k, n, z)
    return {"k": k, "n": n, "ratio": round(k / n, 4), "wilson95": [lo, hi]}


def _wilson_exact(k: int, n: int, z: float) -> tuple[float, float, float]:
    """(p, lower, upper) of the Wilson score interval, unrounded (the rounded one of hri_analysis.wilson would bias a combination)."""
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return p, max(0.0, c - h), min(1.0, c + h)


def newcombe(k1: int, n1: int, k2: int, n2: int, z: float = 1.96) -> dict:
    """The difference p2 - p1 of two rates with the Newcombe hybrid-score 95 % interval (Newcombe 1998, method 10: the Wilson intervals of the
    two rates combined), in percentage points. A description of two small samples, not a test. Either n is 0: not evaluated."""
    if n1 == 0 or n2 == 0:
        return {"difference_pp": ev.NOT_EVALUATED, "lo_pp": ev.NOT_EVALUATED, "hi_pp": ev.NOT_EVALUATED, "method": "Newcombe hybrid score"}
    p1, l1, u1 = _wilson_exact(k1, n1, z)
    p2, l2, u2 = _wilson_exact(k2, n2, z)
    d = p2 - p1
    lo = d - math.sqrt((p2 - l2) ** 2 + (u1 - p1) ** 2)
    hi = d + math.sqrt((u2 - p2) ** 2 + (p1 - l1) ** 2)
    return {"difference_pp": round(100 * d, 1), "lo_pp": round(100 * lo, 1), "hi_pp": round(100 * hi, 1), "method": "Newcombe hybrid score"}


def _median(v: list):
    import statistics
    return {"n": len(v), "median": round(statistics.median(v), 3)} if v else {"n": 0, "median": ev.NOT_EVALUATED}


def wilson_z(repo: Path | None = None) -> float:
    import freeze_v4 as fz
    return float(json.loads(((repo or fz.REPO) / "robot_vision/configs/v4/analysis.json").read_text(encoding="utf-8"))["wilson_z"])


def summarize(run_rows: list[dict], z: float) -> dict:
    """The numbers of one setting from its run rows (run_tables), every rate with its count and a Wilson interval (z from analysis.json).
    Nothing that cannot be evaluated is guessed: a rate without a denominator is 'not_evaluated'."""
    n_runs = len(run_rows)
    have = [r for r in run_rows if r.get("outcome")]
    ok = [r for r in have if r["outcome"] == "SUCCESS"]
    fails = [r for r in have if r["outcome"] != "SUCCESS"]
    kinds = {k: sum(r.get("failure_reason") == k for r in fails) for k in FAILURE_KINDS}
    kinds["other"] = len(fails) - sum(kinds.values())
    times = [float(r["time_s"]) for r in run_rows if r.get("time_s") is not None]
    ok_times = [float(r["time_s"]) for r in ok if r.get("time_s") is not None]
    ratios = [float(r["trail_over_optimal"]) for r in run_rows if r.get("trail_over_optimal") is not None]
    maxd = [float(r["max_distance_from_optimal_m"]) for r in run_rows if r.get("max_distance_from_optimal_m") is not None]
    shares = [float(r["share_within_corridor"]) for r in run_rows if r.get("share_within_corridor") is not None]
    lied = [r for r in run_rows if r.get("lies_given") is not None]
    given = sum(r["lies_given"] for r in lied)
    lies = {"runs_evaluated": len(lied), "given": given}
    for k in ("detected", "corrected", "fooled"):
        tot = sum(r[f"lies_{k}"] for r in lied if r.get(f"lies_{k}") is not None)
        lies[k] = {"total": tot, **(_wilson(tot, given, z) if given else {"rate": "no lies given"})}
    stops = [r for r in run_rows if r.get("stops") is not None]
    wd = [r for r in run_rows if r.get("watchdog_stops") is not None]
    cols = [r for r in run_rows if r.get("collisions") is not None]
    return {
        "runs": n_runs, "runs_with_an_outcome": len(have),
        "success": _wilson(len(ok), len(have), z), "failure_kinds": kinds,
        "time_s": {"all_runs": _median(times), "success_runs": _median(ok_times)},
        "trail_over_optimal": _median(ratios),
        "corridor": {"max_distance_from_optimal_m": _median(maxd), "share_within_corridor": _median(shares),
                     "note": "median over the runs with gt_path files; the corridor is gt_path's near distance around the optimal path"},
        "lies": lies,
        "safety_stops": {"runs_counted": len(stops), "runs_with_a_stop": _wilson(sum(1 for r in stops if r["stops"] > 0), len(stops), z),
                         "stops_total": sum(r["stops"] for r in stops), "seconds_in_stops": round(sum(float(r.get("stop_s") or 0.0) for r in stops), 3)},
        "watchdog_stops": {"runs_counted": len(wd), "runs_with_a_stop": _wilson(sum(1 for r in wd if r["watchdog_stops"] > 0), len(wd), z),
                           "stops_total": sum(r["watchdog_stops"] for r in wd),
                           "note": "B11(a): a result, never a reason for invalidity"},
        "collisions": {"runs_counted": len(cols), "runs_with_a_collision": sum(1 for r in cols if r["collisions"]),
                       "collisions_total": sum(int(r["collisions"]) for r in cols)},
    }


def summary_markdown(setting: str, sm: dict) -> str:
    sc = sm["success"]
    iv = f"{sc['wilson95'][0]}-{sc['wilson95'][1]}" if isinstance(sc["wilson95"], list) else sc["wilson95"]
    L = [f"### Experiment numbers, setting {setting} ({sm['runs']} runs, {sm['runs_with_an_outcome']} with an outcome)", "",
         f"- **SUCCESS {sc['k']}/{sc['n']} = {sc['ratio']}** (Wilson 95 %: {iv}); failures: " + ", ".join(f"{k} {v}" for k, v in sm["failure_kinds"].items()),
         f"- time (s): median {sm['time_s']['all_runs']['median']} over {sm['time_s']['all_runs']['n']} runs; of SUCCESS runs "
         f"{sm['time_s']['success_runs']['median']} over {sm['time_s']['success_runs']['n']}",
         f"- trail / optimal: median {sm['trail_over_optimal']['median']} over {sm['trail_over_optimal']['n']} runs; largest distance from the optimal path "
         f"(median) {sm['corridor']['max_distance_from_optimal_m']['median']} m; share of the trail within the corridor (median) "
         f"{sm['corridor']['share_within_corridor']['median']} ({sm['corridor']['share_within_corridor']['n']} runs with gt_path files)"]
    ls = sm["lies"]
    if ls["given"]:
        L.append(f"- lies given {ls['given']} in {ls['runs_evaluated']} runs; " + "; ".join(
            f"{k} {ls[k]['total']}/{ls['given']} = {ls[k]['ratio']} (Wilson 95 %: {ls[k]['wilson95'][0]}-{ls[k]['wilson95'][1]})" for k in ("detected", "corrected", "fooled")))
    else:
        L.append(f"- lies given 0 in {ls['runs_evaluated']} runs evaluated (no lies, so no detection rates)")
    ss, wd = sm["safety_stops"], sm["watchdog_stops"]
    L.append(f"- safety stops: {ss['stops_total']} in {ss['runs_counted']} runs ({ss['runs_with_a_stop']['k']} runs with a stop), {ss['seconds_in_stops']} s; "
             f"watchdog stops (a result): {wd['stops_total']} in {wd['runs_counted']} runs counted ({wd['runs_with_a_stop']['k']} runs with a stop); "
             f"collisions {sm['collisions']['collisions_total']} in {sm['collisions']['runs_counted']} runs counted")
    return "\n".join(L) + "\n"


# ---------------------------------------------------------------- final mode

def export_final(setting: str, pairs, repo: Path | None = None, output_root: Path | None = None, config_path: str | Path = DEFAULT_CONFIG):
    """One setting's final export. Returns (folder, run rows, summary). Raises SystemExit when refused; the marker is written last."""
    import decision_io as dio
    import final_guard_v4 as fg
    import freeze_v4 as fz
    import hri_eval_final_v4 as ef
    repo = repo or fz.REPO
    output_root = Path(output_root) if output_root is not None else dio.resolve("outputs")
    cfg_path = Path(config_path) if Path(config_path).is_absolute() else dio.resolve(config_path)
    cfg = load_config(cfg_path)
    check_columns(cfg)
    gcfg, ecfg = gd.load_config(repo / "robot_vision/configs/v4/gesture_data.json"), ev.load_config(repo / "robot_vision/configs/v4/eval_dev.json")
    runs = ef.gate(setting, pairs, output_root, gcfg, repo, kind="export")      # frozen, not exported, leak test, test split, the setting's checks
    run_rows, dialog_rows = build_tables(runs, ecfg)
    for r in run_rows:
        r["final_setting"] = r.get("final_setting") or setting
    sm = summarize(run_rows, wilson_z(repo))
    out = dio.new_run_dir({"paths": {"output_root": str(output_root)}}, f"{fg.EXPORT_PREFIX}_{setting}")
    (out / "config_used").mkdir()
    for f in fz.config_files(repo):
        (out / "config_used" / Path(f).name).write_bytes((repo / f).read_bytes())
    (out / "config_used" / "frozen.json").write_bytes((repo / fz.FROZEN_REL).read_bytes())
    (out / "config_used" / cfg_path.name).write_bytes(cfg_path.read_bytes())
    write_csv(out / "runs.csv", run_rows, cfg["runs"], cfg.get("empty", ""))
    write_csv(out / "dialogs.csv", dialog_rows, cfg["dialogs"], cfg.get("empty", ""))
    dio.write_json(out / "summary.json", {"setting": setting, "summary": sm,
                                          "plan_entry": fg.plan(repo)["settings"][setting]})
    dio.write_json(out / "export.json", {"final_setting": setting, "runs": len(run_rows), "asks": len(dialog_rows),
                                         "runs_columns": [c["field"] for c in cfg["runs"]], "dialogs_columns": [c["field"] for c in cfg["dialogs"]],
                                         "definitions": {"runs": RUN_FIELDS, "dialogs": DIALOG_FIELDS},
                                         "splits": "TEST looks and clips only (data_splits_v4.guard_run, final evaluation), frozen configs verified"})
    frozen_sha = fz.sha256_lf(repo / fz.FROZEN_REL)
    git = dio.git_info()
    dio.write_json(out / "run.json", {"git": git, "setting": setting, "sessions": [[u.name, b.name] for u, b in pairs], "frozen_sha256": frozen_sha})
    fg.write_done(out, setting, "export", {"git_commit": git["commit"], "export_folder": out.name, "runs": len(run_rows), "frozen_sha256": frozen_sha})
    return out, run_rows, sm


# ---------------------------------------------------------------- the combined table

def _side(setting: str) -> str:
    return next((p for p in setting.split("_") if p in ("right", "left")), "")


def comparisons(settings: list[str], plan: dict) -> list[dict]:
    """The pairs the combined table compares, derived from the plan: (name, x, y, what): A vs B per scenario (both detection on), B detection on vs
    off, A2 right vs left. 'x' is the reference (A, detection off, left), 'y' the other."""
    pairs = []
    entries = plan["settings"]
    for name, spec in entries.items():
        if spec.get("set") == "B" and spec.get("lie_detection") == "on":
            twin_a = next((n for n, e in entries.items() if e.get("experiment") == "A" + spec["experiment"][1:] and _side(n) == _side(name)
                           and e.get("lie_detection") == "on"), None)
            twin_off = next((n for n, e in entries.items() if e.get("experiment") == spec["experiment"] and _side(n) == _side(name)
                             and e.get("lie_detection") == "off"), None)
            if twin_a:
                pairs.append({"name": f"A vs B, scenario {spec['experiment'][1:]}" + (f" ({_side(name)})" if _side(name) else ""), "x": twin_a, "y": name,
                              "kind": "A vs B"})
            if twin_off:
                pairs.append({"name": f"B detection on vs off, scenario {spec['experiment'][1:]}" + (f" ({_side(name)})" if _side(name) else ""),
                              "x": twin_off, "y": name, "kind": "B on vs off"})
    if "A2_left" in entries and "A2_right" in entries:
        pairs.append({"name": "A2 right vs left (truthful workers, detection on)", "x": "A2_left", "y": "A2_right", "kind": "A2 right vs left"})
    for p in pairs:
        p["available"] = p["x"] in settings and p["y"] in settings
    return pairs


def _cell(m: dict) -> str:
    if not isinstance(m.get("wilson95"), list):
        return f"{m.get('k')}/{m.get('n')} (not evaluated)"
    return f"{m['k']}/{m['n']} = {m['ratio']} [{m['wilson95'][0]}-{m['wilson95'][1]}]"


def combine(folders, repo: Path | None = None, output_root: Path | None = None):
    """The combined table over per-setting final exports. Each folder must carry its FINAL_EXPORT_DONE.json and a summary.json; no
    setting may appear twice; the configs must still be frozen and unchanged. Returns (new folder, result dict)."""
    import decision_io as dio
    import final_guard_v4 as fg
    import freeze_v4 as fz
    repo = repo or fz.REPO
    fz.require_frozen(repo)
    output_root = Path(output_root) if output_root is not None else dio.resolve("outputs")
    per: dict = {}
    for f in map(Path, folders):
        marker, summ = f / fg.MARKERS["export"], f / "summary.json"
        if not (marker.is_file() and summ.is_file()):
            raise SystemExit(f"{f.name}: not a final export folder (needs {fg.MARKERS['export']} and summary.json)")
        m, sj = json.loads(marker.read_text(encoding="utf-8")), json.loads(summ.read_text(encoding="utf-8"))
        if m["setting"] != sj["setting"]:
            raise SystemExit(f"{f.name}: marker says setting {m['setting']!r}, summary.json says {sj['setting']!r}")
        fg.check_name(m["setting"], repo)
        if m["setting"] in per:
            raise SystemExit(f"setting {m['setting']!r} given twice ({per[m['setting']]['folder']} and {f.name})")
        if m.get("frozen_sha256") != fz.sha256_lf(repo / fz.FROZEN_REL):
            raise SystemExit(f"{f.name}: exported under another frozen.json than the current one")
        per[m["setting"]] = {"folder": f.name, **sj}
    plan = fg.plan(repo)
    order = [s for s in plan["settings"] if s in per]
    pairs = comparisons(order, plan)
    z = wilson_z(repo)
    rows = []
    for s in order:
        sm, spec = per[s]["summary"], plan["settings"][s]
        ls = sm["lies"]
        rows.append({"row": "setting", "setting": s, "experiment": spec["experiment"], "set": spec["set"], "lie_detection": spec["lie_detection"],
                     "runs": sm["runs"], "success_k": sm["success"]["k"], "success_n": sm["success"]["n"], "success_ratio": sm["success"]["ratio"],
                     "success_wilson_lo": sm["success"]["wilson95"][0] if isinstance(sm["success"]["wilson95"], list) else "",
                     "success_wilson_hi": sm["success"]["wilson95"][1] if isinstance(sm["success"]["wilson95"], list) else "",
                     **{f"failed_{k}": v for k, v in sm["failure_kinds"].items()},
                     "median_time_s_success": sm["time_s"]["success_runs"]["median"], "median_trail_over_optimal": sm["trail_over_optimal"]["median"],
                     "lies_given": ls["given"], **{f"lies_{k}": ls[k]["total"] for k in ("detected", "corrected", "fooled")},
                     "runs_with_safety_stop": sm["safety_stops"]["runs_with_a_stop"]["k"], "runs_with_watchdog_stop": sm["watchdog_stops"]["runs_with_a_stop"]["k"],
                     "collisions": sm["collisions"]["collisions_total"]})
    comp_rows = []
    for c in pairs:
        if not c["available"]:
            comp_rows.append({**c, "metric": "success", "x_cell": "not available (setting not exported)", "y_cell": "", "difference_pp": "",
                              "difference_lo_pp": "", "difference_hi_pp": ""})
            continue
        sx, sy = per[c["x"]]["summary"], per[c["y"]]["summary"]
        dx, dy = sx["success"], sy["success"]
        nc = newcombe(dx["k"], dx["n"], dy["k"], dy["n"], z)
        comp_rows.append({**c, "metric": "success", "x_cell": _cell(dx), "y_cell": _cell(dy), "difference_pp": nc["difference_pp"],
                          "difference_lo_pp": nc["lo_pp"], "difference_hi_pp": nc["hi_pp"]})
        if sx["lies"]["given"] and sy["lies"]["given"]:
            fx, fy = sx["lies"]["fooled"], sy["lies"]["fooled"]
            nc = newcombe(fx["k"], fx["n"], fy["k"], fy["n"], z)
            comp_rows.append({**c, "metric": "lies fooled (of lies given)", "x_cell": _cell(fx), "y_cell": _cell(fy), "difference_pp": nc["difference_pp"],
                              "difference_lo_pp": nc["lo_pp"], "difference_hi_pp": nc["hi_pp"]})
    res = {"settings": order, "per_setting": {s: per[s] for s in order}, "comparisons": comp_rows, "wilson_z": z,
           "note": "Every rate with its count and a Wilson 95 % interval; the difference is in percentage points (y minus x) with a Newcombe hybrid-score 95 % interval "
                   "(Wilson-based, Newcombe 1998 method 10). It only describes the two rates: no test, no claim of significance. Derived from the per-setting exports; "
                   "no test data is read here. 20 runs per setting is small: read the intervals."}
    out = dio.new_run_dir({"paths": {"output_root": str(output_root)}}, f"{fg.EXPORT_PREFIX}_combined")
    (out / "config_used").mkdir()
    (out / "config_used" / "frozen.json").write_bytes((repo / fz.FROZEN_REL).read_bytes())
    for name, table in (("combined_settings.csv", rows), ("combined_comparisons.csv", comp_rows)):
        cols = list(dict.fromkeys(k for r in table for k in r))
        with (out / name).open("w", newline="", encoding="utf-8") as fh:
            w = csv.writer(fh)
            w.writerow(cols)
            for r in table:
                w.writerow([_fmt(r.get(k)) for k in cols])
    dio.write_json(out / "combined.json", res)
    L = ["# Experiments A and B, final: combined table", "", f"Settings: {', '.join(order)}. Per-setting exports: " + ", ".join(per[s]["folder"] for s in order), "",
         "## Per setting", "", "| setting | experiment | set | detection | SUCCESS (k/n, Wilson 95 %) | failures | median time of SUCCESS (s) | trail/optimal | lies given / detected / corrected / fooled | runs with safety stop | runs with watchdog stop |",
         "|---|---|---|---|---|---|---|---|---|---|---|"]
    for s in order:
        sm, spec = per[s]["summary"], plan["settings"][s]
        ls = sm["lies"]
        L.append(f"| {s} | {spec['experiment']} | {spec['set']} | {spec['lie_detection']} | {_cell(sm['success'])} | "
                 + ", ".join(f"{k} {v}" for k, v in sm["failure_kinds"].items() if v) + f" | {sm['time_s']['success_runs']['median']} | {sm['trail_over_optimal']['median']} | "
                 + f"{ls['given']} / {ls['detected']['total']} / {ls['corrected']['total']} / {ls['fooled']['total']} | "
                 + f"{sm['safety_stops']['runs_with_a_stop']['k']}/{sm['safety_stops']['runs_counted']} | {sm['watchdog_stops']['runs_with_a_stop']['k']}/{sm['watchdog_stops']['runs_counted']} |")
    L += ["", "## Comparisons (y minus x, percentage points, with the Newcombe 95 % interval)", "",
          "| comparison | metric | x | y | y - x (pp) | Newcombe 95 % (pp) |", "|---|---|---|---|---|---|"]
    for c in comp_rows:
        ci = f"[{c['difference_lo_pp']}, {c['difference_hi_pp']}]" if c["difference_lo_pp"] != "" else ""
        L.append(f"| {c['name']} | {c['metric']} | {c['x']}: {c['x_cell']} | {c['y']}: {c['y_cell']} | {c['difference_pp']} | {ci} |")
    L += ["", res["note"], ""]
    (out / "combined.md").write_text("\n".join(L), encoding="utf-8")
    dio.write_json(out / "run.json", {"git": dio.git_info(), "folders": [Path(f).name for f in folders],
                                      "frozen_sha256": fz.sha256_lf(repo / fz.FROZEN_REL)})
    return out, res


def main(argv=None) -> None:
    import decision_io as dio

    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--session", nargs=2, action="append", metavar=("UNITY", "BRIDGE"))
    ap.add_argument("--config", default=DEFAULT_CONFIG)
    ap.add_argument("--final", action="store_true", help="final mode: one setting's export (needs --setting); test data only, once per setting")
    ap.add_argument("--setting", default=None, help="the final setting (final_plan.json), with --final")
    ap.add_argument("--final-combine", nargs="+", metavar="FOLDER", default=None,
                    help="the combined table over per-setting final export folders")
    a = ap.parse_args(argv)
    if a.final_combine:
        if a.final or a.setting or a.session:
            raise SystemExit("--final-combine takes only export folders")
        out, res = combine([dio.resolve(f) for f in a.final_combine])
        print((out / "combined.md").read_text(encoding="utf-8") + f"Folder: {out}")
        return
    if a.final:
        import final_guard_v4 as fg
        if not a.setting or not a.session:
            raise SystemExit("--final needs --setting and --session UNITY BRIDGE")
        if a.setting not in fg.settings():
            raise SystemExit(f"unknown final setting {a.setting!r}; the plan has {fg.settings()}")
        pairs = [(dio.resolve(u), dio.resolve(b)) for u, b in a.session]
        out, run_rows, sm = export_final(a.setting, pairs, config_path=a.config)
        print(f"{len(run_rows)} runs\n" + summary_markdown(a.setting, sm) + f"Folder: {out}\n{fg.MARKERS['export']} written: setting {a.setting} cannot be exported again.")
        return
    if a.setting or not a.session:
        raise SystemExit("development export: --session UNITY BRIDGE (final mode: --final --setting S --session ...)")
    cfg_path = dio.resolve(a.config)
    cfg = load_config(cfg_path)
    check_columns(cfg)
    ecfg, gcfg = ev.load_config(), gd.load_config()
    pairs = [(dio.resolve(u), dio.resolve(b)) for u, b in a.session]
    runs = ev.load_sessions(pairs, gcfg)
    if not runs:
        raise SystemExit("no run_### folders with truth.jsonl found")
    run_rows, dialog_rows = build_tables(runs, ecfg)
    out = dio.new_run_dir({"paths": {"output_root": "outputs"}}, "export_csv_v4")
    (out / "config_used").mkdir()
    for p in (cfg_path, dio.resolve(ev.DEFAULT_CONFIG), dio.resolve(gd.DEFAULT_CONFIG), dio.resolve(ds.DEFAULT)):
        (out / "config_used" / p.name).write_bytes(p.read_bytes())
    write_csv(out / "runs.csv", run_rows, cfg["runs"], cfg.get("empty", ""))
    write_csv(out / "dialogs.csv", dialog_rows, cfg["dialogs"], cfg.get("empty", ""))
    dio.write_json(out / "export.json", {"runs": len(run_rows), "asks": len(dialog_rows), "runs_columns": [c["field"] for c in cfg["runs"]],
                                         "dialogs_columns": [c["field"] for c in cfg["dialogs"]],
                                         "definitions": {"runs": RUN_FIELDS, "dialogs": DIALOG_FIELDS}})
    dio.write_json(out / "run.json", {"git": dio.git_info(), "sessions": [[u.name, b.name] for u, b in pairs]})
    print(f"{len(run_rows)} runs, {len(dialog_rows)} asks\nFolder: {out}")


if __name__ == "__main__":
    main()
