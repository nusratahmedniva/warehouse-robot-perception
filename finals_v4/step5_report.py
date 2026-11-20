"""Step 5 report: development runs of the final matrix (experiments A/B, rehearsal mode, 3 runs per setting).

EVALUATION ONLY, read-only on the session folders: it reads truth (truth.jsonl, truth_run###.json) and goal B through
Anisha's CSV export (export_csv_v4.py, development mode) and is never imported by inference code. Nothing is tuned on it.

Input: a JSON manifest (robot_vision/outputs/step5_sessions.json, git-ignored) listing per setting
  {"setting": "A1", "unity": "<trials_development_...>", "bridge": "<bridge_guide_...>", "export": "<export_csv_v4_...>",
   "timeout_s": 420}
with paths relative to robot_vision/ (or absolute).

Output (never overwritten, new names every time):
  robot_vision/outputs/step5_report_<time>.md       per-setting tables (outcomes, durations, dialogs, safety stops, timing, lies)
  robot_vision/outputs/step5_durations_<time>.csv   one row per run (for Anisha's timeout rule)
  robot_vision/outputs/step5_stops_<time>.csv       one row per accepted STOP (true / false, what was shown)

Definitions (declared here, before any step 5 session was read):
  accepted STOP   an episode of consecutive decisions.csv rows of one trial with safety "STOP gesture" (the controller
                  stopped for a STOP reading); it starts at the first such row.
  true STOP       at the episode start some worker's latest truth row (time_s <= start) has true_command STOP in phase
                  gesturing or holding; otherwise false. For a false STOP every worker's latest command and phase is listed,
                  and the worker nearest to the robot (decisions.csv x, z) is named.
  dialog          one (trial, junction, visit, dialog) group of dialogs.csv. correct = accepted and correct_branch;
                  wrong branch = accepted and not correct_branch; asked again = more than one ask; abort = no accepted
                  answer and no rejection (python_trial junction result not "accepted"); rejected = a lie-detection rejection.
  wrong-branch decision  the branch the robot drove from that node (dialogs.csv final_branch) is not the true branch toward B.
  setting prefix  (2026-11-20, experiments_ab.md section 15 addendum 8) --prefix P keeps only the entries named P + one of the 13 final
                  settings (SETTINGS) and drops P to pair a B setting with its A partner; the output names carry P. Without it every
                  entry is read, as before.
Usage (from the repository root): robot_vision\\.venv\\Scripts\\python.exe finals_v4\\step5_report.py [manifest] [--prefix P]
"""
from __future__ import annotations

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
SHOWN_PHASES = ("gesturing", "holding")
B_OF_A = {"B1": "A1", "B2_right": "A2_right", "B3": "A3", "B4": "A4"}
SETTINGS = ("A1", "A2_right", "A2_left", "A3", "A4", "B1", "B2_right", "B3", "B4", "B1_off", "B2_right_off", "B3_off", "B4_off")


def select(entries: list[dict], prefix: str) -> list[dict]:
    """The manifest entries named prefix + a final setting (all entries for an empty prefix)."""
    if not prefix:
        return list(entries)
    return [e for e in entries if e["setting"].startswith(prefix) and e["setting"][len(prefix):] in SETTINGS]


def p(path: str) -> Path:
    q = Path(path)
    return q if q.is_absolute() else RV / q


def jload(path: Path):
    return json.loads(path.read_text(encoding="utf-8-sig")) if path.exists() else None


def rows(path: Path) -> list[dict]:
    with path.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def num(x):
    try:
        v = float(x)
        return v if math.isfinite(v) else None
    except (TypeError, ValueError):
        return None


def truth_by_worker(run_dir: Path) -> dict[int, list[dict]]:
    out: dict[int, list[dict]] = defaultdict(list)
    path = run_dir / "truth.jsonl"
    if not path.exists():
        return out
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            r = json.loads(line)
            out[r["worker_id"]].append(r)
    return out


def latest(rows_w: list[dict], t: float) -> dict | None:
    best = None
    for r in rows_w:
        if r["time_s"] <= t + 1e-6:
            best = r
        else:
            break
    return best


def stop_episodes(bridge: Path, unity: Path, setting: str) -> list[dict]:
    dec = rows(bridge / "decisions.csv")
    eps, prev_on, prev_trial = [], False, None
    for r in dec:
        on = r.get("safety", "") == "STOP gesture"
        trial = int(r["trial"])
        if on and (not prev_on or trial != prev_trial):
            eps.append({"row": r, "trial": trial, "rows": 1, "t_end": float(r["time_s"])})
        elif on:
            eps[-1]["rows"] += 1
            eps[-1]["t_end"] = float(r["time_s"])
        prev_on, prev_trial = on, trial
    cache: dict[int, dict] = {}
    out = []
    for e in eps:
        r, trial = e["row"], e["trial"]
        t, x, z = float(r["time_s"]), float(r["x"]), float(r["z"])
        if trial not in cache:
            cache[trial] = truth_by_worker(unity / f"run_{trial:03d}") if trial > 0 else {}
        workers = []
        for wid, wr in sorted(cache[trial].items()):
            lr = latest(wr, t)
            if lr is None:
                continue
            workers.append({"worker_id": wid, "look": lr["look"], "command": lr["true_command"], "phase": lr["phase"],
                            "commander": lr["is_commander"], "truthful": lr.get("gesture_truthful"),
                            "dist_m": math.hypot(lr["x"] - x, lr["z"] - z)})
        true_stop = any(w["command"] == "STOP" and w["phase"] in SHOWN_PHASES for w in workers)
        nearest = min(workers, key=lambda w: w["dist_m"]) if workers else None
        shown = [w for w in workers if w["command"] != "NONE" and w["phase"] in SHOWN_PHASES]
        out.append({
            "setting": setting, "trial": trial, "t_start_s": round(t, 3), "duration_s": round(e["t_end"] - t, 3),
            "state": r["state"], "robot_v": num(r["v"]), "true_stop": true_stop,
            "shown": "; ".join(f"w{w['worker_id']} {w['command']} ({w['phase']}, {w['dist_m']:.2f} m"
                               f"{', commander' if w['commander'] else ''})" for w in shown) or "nothing (no worker gesturing or holding)",
            "nearest_worker": (f"w{nearest['worker_id']} {nearest['look']} {nearest['command']} {nearest['phase']} "
                               f"{nearest['dist_m']:.2f} m") if nearest else "",
            "all_workers": "; ".join(f"w{w['worker_id']} {w['command']}/{w['phase']}" for w in workers),
        })
    return out


def dialogs(export: Path, bridge: Path) -> tuple[dict, list[str]]:
    d = rows(export / "dialogs.csv")
    groups: dict[tuple, list[dict]] = defaultdict(list)
    for r in d:
        groups[(int(r["trial"]), r["junction"], r["visit"], r["dialog"])].append(r)
    results: dict[tuple, str] = {}
    counts = {"dialogs": 0, "correct": 0, "wrong_branch": 0, "asked_again": 0, "abort": 0, "rejected": 0}
    wrong_decisions = []
    for key, g in sorted(groups.items()):
        counts["dialogs"] += 1
        last = g[-1]
        if len(g) > 1:
            counts["asked_again"] += 1
        if any(x["decision"].startswith("rejected") for x in g):
            counts["rejected"] += 1
        if last["decision"] == "accepted":
            if last["correct_branch"].lower() == "true":
                counts["correct"] += 1
            elif last["correct_branch"].lower() == "false":
                counts["wrong_branch"] += 1
        elif not last["decision"].startswith("rejected"):
            counts["abort"] += 1
        fb, tb = last["final_branch"], last["true_branch"]
        if fb and tb and fb != tb:
            wrong_decisions.append(f"trial {key[0]} {key[1]} visit {key[2]} dialog {key[3]}: drove {fb}, true {tb}, "
                                   f"shown {last['command_shown']} {last['branch_shown']} truthful {last['truthful']}, read {last['branch_read']}")
    return counts, wrong_decisions


def timing(bridge: Path) -> dict:
    s = jload(bridge / "summary.json") or {}
    rt = s.get("round_trip", {})
    res = s.get("resources", {})
    return {
        "watchdog_stops": s.get("watchdog", {}).get("stops_reported_by_unity"),
        "frame_stalls": s.get("watchdog", {}).get("unity_frame_stalls_reported_by_unity"),
        "round_trip_max_ms": rt.get("all_messages", {}).get("max_ms", rt.get("max_ms")),
        "loop_lag_max_ms": s.get("event_loop_lag", {}).get("max_lag_ms"),
        "free_mem_min_mb": res.get("mem_available_mb", {}).get("min"),
        "hard_paging_max": res.get("hard_paging_per_s", {}).get("max"),
        "errors": len(s.get("errors", [])) if s else None,
    }


def fmt(x, n=1):
    return "" if x is None else (f"{x:.{n}f}" if isinstance(x, float) else str(x))


def main(argv: list[str]) -> int:
    args, prefix = list(argv[1:]), ""
    if "--prefix" in args:
        i = args.index("--prefix")
        if i + 1 >= len(args):
            raise SystemExit("--prefix needs a value, e.g. --prefix t0_")
        prefix = args[i + 1]
        del args[i:i + 2]
    manifest = Path(args[0]) if args else OUT / "step5_sessions.json"
    entries = select(json.loads(manifest.read_text(encoding="utf-8"))["sessions"], prefix)
    if not entries:
        raise SystemExit(f"{manifest}: no session{' with the prefix ' + repr(prefix) if prefix else ''}")
    stamp = prefix + datetime.now().strftime("%Y%m%d_%H%M%S")
    md_path, dur_path, stop_path = (OUT / f"step5_report_{stamp}.md", OUT / f"step5_durations_{stamp}.csv",
                                    OUT / f"step5_stops_{stamp}.csv")
    for f in (md_path, dur_path, stop_path):
        if f.exists():
            raise SystemExit(f"{f} exists; not overwritten")
    md = [f"# Step 5 development runs of the final matrix ({stamp})", "",
          "Development data (rehearsal mode: dev seed, development looks and clips, development timeout). Not a result.", ""]
    dur_rows, stop_rows, per = [], [], {}
    for e in entries:
        st, U, B, X = e["setting"], p(e["unity"]), p(e["bridge"]), p(e["export"])
        runs = rows(X / "runs.csv")
        dlg, wrong = dialogs(X, B)
        stops = stop_episodes(B, U, st)
        tm = timing(B)
        per[st] = {"runs": runs}
        stop_rows += stops
        for r in runs:
            dur_rows.append({"setting": st, "unity_session": U.name, "bridge_run": B.name, "trial": r["trial"], "goal": r["goal"],
                             "route": r["route"], "outcome": r["outcome"], "failure_reason": r["failure_reason"],
                             "time_s": r["time_s"], "timeout_s": e.get("timeout_s", ""), "trail_m": r["trail_m"],
                             "optimal_m": r["optimal_m"], "asks": r["asks"], "dialogs": r["dialogs"],
                             "second_opinions": r["second_opinions"]})
        times = [num(r["time_s"]) for r in runs if num(r["time_s"]) is not None]
        md += [f"## {st}", "", f"Unity `{U.name}`, bridge `{B.name}`, export `{X.name}`", "",
               "| trial | goal | route | outcome | failure | final dist (m) | time (s) | trail / optimal (m) | stops | lies g/d/c/f |",
               "|---|---|---|---|---|---|---|---|---|---|"]
        for r in runs:
            lies = "/".join(r[k] or "-" for k in ("lies_given", "lies_detected", "lies_corrected", "lies_fooled"))
            md.append(f"| {r['trial']} | {r['goal']} | {r['route']} | {r['outcome']} | {r['failure_reason']} | "
                      f"{fmt(num(r['final_distance_m']), 2)} | {fmt(num(r['time_s']))} | {fmt(num(r['trail_m']))} / "
                      f"{fmt(num(r['optimal_m']))} | {r['stops']} | {lies} |")
        md += ["", f"- longest run: {fmt(max(times)) if times else '-'} s (timeout {e.get('timeout_s', '?')} s)",
               f"- dialogs: {dlg['dialogs']}: correct {dlg['correct']}, wrong branch {dlg['wrong_branch']}, asked again "
               f"{dlg['asked_again']}, abort {dlg['abort']}, rejected by lie detection {dlg['rejected']}",
               f"- wrong-branch decisions (drove a branch other than toward B): {len(wrong)}"]
        md += [f"  - {w}" for w in wrong]
        n_true = sum(s["true_stop"] for s in stops)
        md += [f"- SAFETY STOPS accepted: {len(stops)} (true {n_true}, false {len(stops) - n_true})"]
        md += [f"  - trial {s['trial']} t {s['t_start_s']} s, {s['duration_s']} s, state {s['state']}, v {fmt(s['robot_v'], 2)}: "
               f"{'TRUE' if s['true_stop'] else 'FALSE'}; shown: {s['shown']}; nearest {s['nearest_worker']}" for s in stops]
        md += [f"- watchdog stops {tm['watchdog_stops']} (frame stalls {tm['frame_stalls']}), round trip max "
               f"{fmt(tm['round_trip_max_ms'])} ms, loop lag max {fmt(tm['loop_lag_max_ms'])} ms, free memory min "
               f"{fmt(tm['free_mem_min_mb'], 0)} MB, hard paging max {fmt(tm['hard_paging_max'], 0)} /s, bridge errors {tm['errors']}", ""]
    # Set B against its A partner
    md += ["## Set B against the matching A setting (development; same seed, so same goals and placements)", "",
           "| B setting | A setting | lies given / detected / corrected / fooled | mean time B - A (s) | mean trail B - A (m) | per-run pairs (trial: dt s, dtrail m, outcomes) |",
           "|---|---|---|---|---|---|"]
    base = {st: st[len(prefix):] for st in per}                      # the final setting name without the prefix
    for b, a in [(b, prefix + B_OF_A[base[b].replace("_off", "")]) for b in per if base[b].replace("_off", "") in B_OF_A]:
        if a not in per:
            continue
        rb, ra = per[b]["runs"], per[a]["runs"]
        lies = "/".join(str(sum(int(r[k] or 0) for r in rb)) for k in ("lies_given", "lies_detected", "lies_corrected", "lies_fooled"))

        def mean(rs, k):
            v = [num(r[k]) for r in rs if num(r[k]) is not None]
            return statistics.mean(v) if v else None
        dt = None if mean(rb, "time_s") is None or mean(ra, "time_s") is None else mean(rb, "time_s") - mean(ra, "time_s")
        dl = None if mean(rb, "trail_m") is None or mean(ra, "trail_m") is None else mean(rb, "trail_m") - mean(ra, "trail_m")
        ia = {r["trial"]: r for r in ra}
        pairs = []
        for r in rb:
            q = ia.get(r["trial"])
            if q is None:
                continue
            same = "" if q["goal"] == r["goal"] else f" goals differ {r['goal']}/{q['goal']}"
            pairs.append(f"{r['trial']}: {fmt(num(r['time_s']) - num(q['time_s']) if num(r['time_s']) is not None and num(q['time_s']) is not None else None)}, "
                         f"{fmt(num(r['trail_m']) - num(q['trail_m']) if num(r['trail_m']) is not None and num(q['trail_m']) is not None else None)}, "
                         f"{r['outcome']}/{q['outcome']}{same}")
        md.append(f"| {b} | {a} | {lies} | {fmt(dt)} | {fmt(dl)} | {'; '.join(pairs)} |")
    md.append("")
    with dur_path.open("x", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(dur_rows[0].keys()))
        w.writeheader()
        w.writerows(dur_rows)
    with stop_path.open("x", encoding="utf-8", newline="") as f:
        fields = ["setting", "trial", "t_start_s", "duration_s", "state", "robot_v", "true_stop", "shown", "nearest_worker", "all_workers"]
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(stop_rows)
    with md_path.open("x", encoding="utf-8") as f:
        f.write("\n".join(md))
    print(md_path)
    print(dur_path)
    print(stop_path)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
