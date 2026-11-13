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
(hri_eval_dev_v4.load_sessions runs data_splits_v4.guard_run before anything is read).

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


def run_tables(run: ev.Run, ecfg: dict, road: hc.Roadmap) -> tuple[dict, list[dict]]:
    """(the runs.csv row as a dict of every known field, the dialogs.csv rows) of one run."""
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
    trail_m = optimal_m = None
    source = ""
    run_dir = unity / f"run_{run.trial:03d}"
    if gt_path.has_v4_files(run_dir):
        meas = gt_path.evaluate_run(run_dir)["measures"]
        trail_m, optimal_m, source = meas.get("trail_length_m"), meas.get("optimal_length_m"), "gt_path"
    elif truth_run.get("optimal_m") is not None:
        trail_m, optimal_m, source = truth_run.get("travelled_m"), truth_run["optimal_m"], "road_route"
    run_row = {
        "experiment": session.get("experiment", truth_run.get("experiment")), "set": session.get("set", truth_run.get("set")),
        "lie_probability": session.get("lie_probability"), "setting": session.get("lie_detection"), "session": run.session, "run": run.name, "trial": run.trial,
        "seed": truth_run.get("seed"), "looks": "+".join(sorted(run.looks)), "route": ">".join(route), "goal": goal,
        "outcome": truth_run.get("outcome"), "failure_reason": truth_run.get("failure_reason"), "time_s": truth_run.get("total_s"),
        "trail_m": trail_m, "optimal_m": optimal_m,
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
    ecfg = ecfg if ecfg is not None else ev.load_config()
    roads: dict = {}
    run_rows, dialog_rows = [], []
    for run in runs:
        rr, dr = run_tables(run, ecfg, _road_for(run, roads))
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


def main(argv=None) -> None:
    import decision_io as dio

    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--session", nargs=2, action="append", required=True, metavar=("UNITY", "BRIDGE"))
    ap.add_argument("--config", default=DEFAULT_CONFIG)
    a = ap.parse_args(argv)
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
