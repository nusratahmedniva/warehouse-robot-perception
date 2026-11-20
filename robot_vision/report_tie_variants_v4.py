"""ONE table for the tie-rule variants T0 / T1 / T2 of AUDIT.md 16.22 (2026-11-18). EVALUATION CODE: reads runs.csv and dialogs.csv of finished
run_experiments_ab_v4.py folders (truth-based columns included); nothing in the controller or the simulator imports it.

Per row (experiment x detection) and variant: successes of runs, wrong goals, aborts, collisions, the longest successful duration, the backtracks the robot made
(sum of the `backtracks` column) and, for the B rows, the lies fooled split by first-asked / later-asked liar (the definitions of report_rows_ab_v4 / 16.21.3).
Also the pass checks declared in 16.22: A rows lose no success against T0 and make no backtrack; the "off" rows are identical in the three variants.

Usage (from robot_vision/): python report_tie_variants_v4.py --t0 <folder> --t1 <folder> --t2 <folder> [--label x]
Writes outputs/report_tie_variants_v4_<time>[_label]/ (table.md, table.json, run.json with the git commit); never overwrites."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

import report_rows_ab_v4 as rr  # noqa: E402

VARIANTS = ("T0", "T1", "T2")


def load(folder) -> dict:
    f = Path(folder)
    runs, dialogs = rr.read_csv(f / "runs.csv"), rr.read_csv(f / "dialogs.csv")
    out = {}
    for row in rr.load_folder(f)["rows"]:
        rs = [r for r in runs if r["experiment"] == row["experiment"] and r["setting"] == row["setting"]]
        row["wrong_goal"] = row["failures"].get("wrong_goal", 0)
        row["aborted"] = row["failures"].get("aborted", 0)
        row["backtracks"] = sum(int(float(r["backtracks"] or 0)) for r in rs)
        row["runs_with_backtrack"] = sum(1 for r in rs if int(float(r["backtracks"] or 0)) > 0)
        row["signature"] = [[r[c] for c in ("run", "outcome", "failure_reason", "time_s", "collisions", "lies_fooled")] if "run" in r else [r[c] for c in ("outcome", "failure_reason", "time_s")] for r in rs]
        out[(row["experiment"], row["setting"])] = row
    return out


def cell(r: dict) -> str:
    longest = f"{r['longest_successful_s']:.1f}" if r["longest_successful_s"] is not None else "-"
    s = f"{r['success']}/{r['runs']}, wrong goal {r['wrong_goal']}, aborted {r['aborted']}, collisions {r['collisions']}, longest {longest} s, backtracks {r['backtracks']} ({r['runs_with_backtrack']} runs)"
    if "lies" in r:
        s += f"; fooled {r['lies']['first'].get('fooled', 0)} first / {r['lies']['later'].get('fooled', 0)} later, caught by reject_impossible {r['lies']['first'].get('caught_by_reject_impossible', 0) + r['lies']['later'].get('caught_by_reject_impossible', 0)}"
    return s


def checks(data: dict) -> dict:
    t0 = data["T0"]
    out = {"off_rows_identical": all(data[v][k]["signature"] == t0[k]["signature"] for v in VARIANTS[1:] for k in t0 if k[1] == "off"),
           "A_success_lost_vs_T0": {}, "A_backtracks": {}}
    for v in VARIANTS[1:]:
        out["A_success_lost_vs_T0"][v] = {f"{k[0]} {k[1]}": t0[k]["success"] - data[v][k]["success"] for k in t0 if k[0].startswith("A") and data[v][k]["success"] < t0[k]["success"]}
        out["A_backtracks"][v] = {f"{k[0]} {k[1]}": data[v][k]["backtracks"] for k in t0 if k[0].startswith("A") and data[v][k]["backtracks"]}
    return out


def markdown(data: dict, finals: set, folders: dict, chk: dict) -> str:
    L = ["| experiment | detection | final | " + " | ".join(VARIANTS) + " |", "|---|---|---|---|---|---|"]
    for k in data["T0"]:
        L.append(f"| {k[0]} | {k[1]} | {'**final**' if k in finals else '-'} | " + " | ".join(cell(data[v][k]) for v in VARIANTS) + " |")
    L += ["", "Folders: " + "; ".join(f"{v} `{Path(folders[v]).name}`" for v in VARIANTS), "",
          f"Checks of 16.22: off rows identical in T0 / T1 / T2: {chk['off_rows_identical']}; A rows losing a success against T0: {chk['A_success_lost_vs_T0']}; A rows with a backtrack: {chk['A_backtracks']}."]
    return "\n".join(L)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    for v in VARIANTS:
        ap.add_argument(f"--{v.lower()}", required=True, help=f"run_experiments_ab_v4 folder of variant {v}")
    ap.add_argument("--label", default="")
    a = ap.parse_args(argv)
    folders = {v: getattr(a, v.lower()) for v in VARIANTS}
    data = {v: load(folders[v]) for v in VARIANTS}
    finals = rr.final_rows()
    chk = checks(data)
    md = markdown(data, finals, folders, chk)
    out = ROOT / "outputs" / f"report_tie_variants_v4_{time.strftime('%Y%m%d_%H%M%S')}{'_' + a.label if a.label else ''}"
    out.mkdir(parents=True, exist_ok=False)
    (out / "table.md").write_text(md + "\n", encoding="utf-8")
    slim = {v: {f"{k[0]} {k[1]}": {x: y for x, y in r.items() if x != "signature"} for k, r in data[v].items()} for v in VARIANTS}
    (out / "table.json").write_text(json.dumps({"rows": slim, "checks": chk}, indent=1, default=str), encoding="utf-8")
    commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    (out / "run.json").write_text(json.dumps({"git_commit": commit, "folders": folders, "final_rows": sorted(finals)}, indent=1), encoding="utf-8")
    print(md)
    print(f"\nFolder: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
