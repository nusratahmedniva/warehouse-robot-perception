"""ONE table for variants T3 "checkpoint workers" and T4 "the checkpoint is a vote" against T0 (AUDIT.md 16.23 and 16.24, 2026-11-18). EVALUATION CODE: reads runs.json of run_t3_v4.py (the gestures staged with their
truth included); nothing in the controller or the simulator imports it.

Per row (experiment x setting x variant): successes of runs, wrong goals, aborts, timeouts, collisions; lies fooled split into the JUNCTION liar (a wrong branch taken at a
junction after a lying junction answer showing it) and the CHECKPOINT liar (a lying checkpoint answer acted on: a wrong branch let through, or a false backtrack); lies CAUGHT
by a checkpoint (a backtrack from a checkpoint on a wrong branch); FALSE backtracks (a backtrack from a checkpoint on the right branch: a lying checkpoint, or a misread);
the backtracks made; the checkpoint pointings back IGNORED because the junction's answers agreed (T4, 16.24); the longest successful duration; the most people in the robot's view in any run (360 detections of one tick).
Checks of 16.23: the A rows lose no success against T0 and make no backtrack; T0 of this runner equals a given earlier folder of run_experiments_ab_v4.py run for run.
The stopping rule of 16.24, applied mechanically: T4 is adopted only if B3 on AND B4 on each gain at least 3 of 20 successes over T0 and no A row loses a success or makes a backtrack.

Usage (from robot_vision/): python report_t3_v4.py --folder outputs/t3_v4_<a> [--t0-folder outputs/experiments_ab_v4_<b>] [--label x]
Writes outputs/report_t3_v4_<time>[_label]/ (table.md, table.json, run.json with the git commit); never overwrites."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

import report_rows_ab_v4 as rr  # noqa: E402


def run_metrics(rec: dict) -> dict:
    """The lie and backtrack counts of one run record (the definitions in the module docstring)."""
    gest = rec["gestures"]
    junction_g = [g for g in gest if g.get("kind") != "checkpoint"]
    cp_g = {(g["node"], g["branch"]): g for g in gest if g.get("kind") == "checkpoint"}
    fooled_j = other_wrong = 0
    for go in rec["go"]:
        if go["correct"] != "NONE" and go["branch"] != go["correct"]:
            lied = any((not g["truthful"]) and g["node"] == go["node"] and g["shown"] == go["branch"] for g in junction_g)
            fooled_j += lied
            other_wrong += not lied
    caught = false_bt = cp_fooled = missed_honest = 0
    ignored = sum(1 for e in rec["checkpoint"]["log"] if e["action"] == "ignore_undisputed")
    for e in rec["checkpoint"]["log"]:
        g = cp_g.get((e["junction"], e["branch"]))
        right = None if g is None else g["correct"] == "PROCEED"
        liar = g is not None and not g["truthful"]
        if e["action"] == "backtrack":
            if right:
                false_bt += 1
                cp_fooled += int(liar)
            else:
                caught += 1
        elif e["result"] == "proceed" and right is False and liar:
            cp_fooled += 1
        elif right is False and not liar and e["action"] != "backtrack":
            missed_honest += 1                                  # an honest checkpoint on a wrong branch that did not send the robot back
    nj_backtracks = nj_false = 0                                # AUDIT.md 16.25.1: backtracks on a BACK vote at the next junction; false = the branch taken at J was the right one
    for e in rec["checkpoint"].get("next_junction_back", []):
        g = next((x for x in rec["go"] if x["node"] == e["junction"] and x["branch"] == e["branch"]), None)
        nj_backtracks += 1
        if g is not None and g["correct"] == g["branch"]:
            nj_false += 1
            false_bt += 1
    return {"nj_backtracks": nj_backtracks, "nj_false": nj_false, "junction_fooled": fooled_j, "wrong_branch_without_a_lie": other_wrong, "cp_fooled": cp_fooled, "caught": caught, "false_backtracks": false_bt,
            "backtracks": rec["checkpoint"]["backtracks"], "cp_lying": sum(1 for g in cp_g.values() if not g["truthful"]), "cp_asked": len(rec["checkpoint"]["log"]),
            "missed_honest": missed_honest, "ignored_undisputed": ignored}


def summarise(rows: list[dict]) -> dict:
    groups: dict = defaultdict(list)
    for r in rows:
        groups[(r["experiment"], r["setting"], r["variant"])].append(r)
    out = {}
    for key, rs in groups.items():
        m = [run_metrics(r) for r in rs]
        ok = [r["time_s"] for r in rs if r["outcome"] == "SUCCESS"]
        reasons = [r["failure_reason"] for r in rs if r["outcome"] != "SUCCESS"]
        out[key] = {"runs": len(rs), "success": len(ok), "wrong_goal": reasons.count("wrong_goal"), "aborted": reasons.count("aborted"), "timeout": reasons.count("timeout"),
                    "collision": reasons.count("collision"), "longest_successful_s": max(ok) if ok else None,
                    "max_people_in_view": max(r["max_people_in_view"] for r in rs),
                    **{k: sum(x[k] for x in m) for k in m[0]}}
    return out


def t0_equality(rows: list[dict], folder: Path, first_seed: int) -> dict:
    """T0 of the runner against an earlier folder of run_experiments_ab_v4.py: outcome, failure reason and duration of every run."""
    ref = {}
    for r in rr.read_csv(folder / "runs.csv"):
        ref[(r["experiment"], r["setting"], int(r["run"].rsplit("_", 1)[1]))] = (r["outcome"], r["failure_reason"], round(float(r["time_s"]), 2))
    n = same = 0
    differing = []
    for r in rows:
        if r["variant"] != "T0":
            continue
        k = (r["experiment"], r["setting"], r["seed"] - first_seed + 1)
        n += 1
        if ref.get(k) == (r["outcome"], r["failure_reason"], round(r["time_s"], 2)):
            same += 1
        else:
            differing.append([k, ref.get(k), (r["outcome"], r["failure_reason"], r["time_s"])])
    return {"t0_runs": n, "equal": same, "differing": differing[:10]}


def checks(summary: dict, variant: str = "T3") -> dict:
    """The A-row criteria for one variant, and (16.24) the stopping rule for T4."""
    lost, bt = {}, {}
    for (exp, setting, var), s in summary.items():
        if var != variant or not exp.startswith("A"):
            continue
        t0 = summary.get((exp, setting, "T0"))
        if t0 and s["success"] < t0["success"]:
            lost[f"{exp} {setting}"] = t0["success"] - s["success"]
        if s["backtracks"]:
            bt[f"{exp} {setting}"] = s["backtracks"]
    return {"A_success_lost_vs_T0": lost, "A_backtracks": bt}


def stopping_rule(summary: dict, variant: str = "T4", need: int = 3) -> dict:
    """AUDIT.md 16.24: adopted only if B3 on AND B4 on each gain at least `need` successes over T0 and no A row loses a success or backtracks."""
    gains = {}
    for exp in ("B3", "B4"):
        a, b = summary.get((exp, "on", variant)), summary.get((exp, "on", "T0"))
        gains[exp] = None if a is None or b is None else a["success"] - b["success"]
    chk = checks(summary, variant)
    ok = all(g is not None and g >= need for g in gains.values()) and not chk["A_success_lost_vs_T0"] and not chk["A_backtracks"]
    return {"variant": variant, "gains_B_on": gains, "needed_each": need, "A_success_lost_vs_T0": chk["A_success_lost_vs_T0"], "A_backtracks": chk["A_backtracks"], "adopted": ok}


def markdown(summary: dict, finals: set, chk: dict, eq: dict | None, folder: str, rule: dict | None = None) -> str:
    L = ["| experiment | detection | final | variant | SUCCESS | wrong goal | aborted | timeout | collision | lies fooled: junction liar | lies fooled: checkpoint liar | caught by a checkpoint | FALSE backtracks | checkpoint back ignored (undisputed) | backtracks | longest successful s | most people in view |",
         "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for (exp, setting, variant), s in sorted(summary.items(), key=lambda kv: (kv[0][0], kv[0][1] != "off", kv[0][2])):
        longest = f"{s['longest_successful_s']:.1f}" if s["longest_successful_s"] is not None else "-"
        L.append(f"| {exp} | {setting} | {'**final**' if (exp, setting) in finals else '-'} | {variant} | {s['success']}/{s['runs']} | {s['wrong_goal']} | {s['aborted']} | {s['timeout']} | "
                 f"{s['collision']} | {s['junction_fooled']} | {s['cp_fooled']} | {s['caught']} | {s['false_backtracks']} | {s['ignored_undisputed']} | {s['backtracks']} | {longest} | {s['max_people_in_view']} |")
    L += ["", f"Folder: `{folder}`", "",
          f"Checks of 16.23: A rows losing a success against T0: {chk['A_success_lost_vs_T0'] or 'none'}; A rows with a backtrack: {chk['A_backtracks'] or 'none'}."]
    for var, c in chk.get("by_variant", {}).items():
        L.append(f"A rows of {var}: losing a success against T0: {c['A_success_lost_vs_T0'] or 'none'}; with a backtrack: {c['A_backtracks'] or 'none'}.")
    if rule is not None:
        L.append(f"Stopping rule of 16.24 for {rule['variant']}: gains over T0 in B3 on / B4 on: {rule['gains_B_on']} (each at least {rule['needed_each']} needed); A rows losing a success: "
                 f"{rule['A_success_lost_vs_T0'] or 'none'}; A rows with a backtrack: {rule['A_backtracks'] or 'none'}; **{'ADOPTED' if rule['adopted'] else 'NOT adopted'}**.")
    if eq is not None:
        L.append(f"T0 against the earlier folder: {eq['equal']} of {eq['t0_runs']} runs equal (outcome, reason, duration)." + (f" Differing: {eq['differing']}" if eq["differing"] else ""))
    return "\n".join(L)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--folder", required=True)
    ap.add_argument("--t0-folder", default=None, help="a run_experiments_ab_v4 folder whose runs.csv T0 must equal (e.g. the 16.22 T0 folder)")
    ap.add_argument("--label", default="")
    a = ap.parse_args(argv)
    folder = Path(a.folder)
    rows = json.loads((folder / "runs.json").read_text(encoding="utf-8"))
    meta = json.loads((folder / "run.json").read_text(encoding="utf-8"))
    summary = summarise(rows)
    finals = rr.final_rows()
    variants = sorted({k[2] for k in summary} - {"T0"})
    chk = {**checks(summary, variants[0] if variants else "T3"), "by_variant": {v: checks(summary, v) for v in variants}}
    rule = stopping_rule(summary) if "T4" in variants else None
    eq = t0_equality(rows, Path(a.t0_folder), int(meta["first_seed"])) if a.t0_folder else None
    md = markdown(summary, finals, chk, eq, folder.name, rule)
    out = ROOT / "outputs" / f"report_t3_v4_{time.strftime('%Y%m%d_%H%M%S')}{'_' + a.label if a.label else ''}"
    out.mkdir(parents=True, exist_ok=False)
    (out / "table.md").write_text(md + "\n", encoding="utf-8")
    (out / "table.json").write_text(json.dumps({"rows": {" | ".join(k): v for k, v in summary.items()}, "checks": chk, "stopping_rule": rule, "t0_equality": eq}, indent=1, default=str), encoding="utf-8")
    commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    (out / "run.json").write_text(json.dumps({"git_commit": commit, "folder": str(folder), "t0_folder": a.t0_folder, "final_rows": sorted(finals)}, indent=1), encoding="utf-8")
    print(md)
    print(f"\nFolder: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
