"""Per-row report of experiment folders of run_experiments_ab_v4.py (AUDIT.md 16.21.2, 2026-11-17). EVALUATION CODE: it reads runs.csv and dialogs.csv of finished folders
(truth-based columns included); nothing in the controller or the simulator imports it.

Per row (experiment x lie detection): successes, failures, collisions, the longest successful duration, the E5 / E6 runs (n, successes, longest) and whether the row is one of
the 13 final settings of configs/v4/final_plan.json. For the B rows the lying asks split by WHO lied (the first-asked worker of the visit, or a later-asked one; the re-ask of the
first worker on a tie counts as the first) and by what happened to the lie:
  caught_by_reject_impossible  the answer was rejected as impossible (decision "rejected:*"; lie_detection rule b)
  outvoted / withdrawn         the second opinion (rule a) outvoted it / a backtrack withdrew it
  fooled                       accepted, acted on and not the true branch (as export_csv_v4)
  neither                      no reading, or read as the true branch (the mirror ambiguity), or unclear
These are the definitions of export_csv_v4 (det = rejected or outvoted or withdrawn; fooled = accepted and followed and wrong); the totals are checked against runs.csv.

Usage (from robot_vision/): python report_rows_ab_v4.py --folder outputs/experiments_ab_v4_<a> [--previous outputs/experiments_ab_v4_<b>] [--label x]
Writes outputs/report_rows_ab_v4_<time>[_label]/ (report.md, report.json, run.json with the git commit); never overwrites.
"""

from __future__ import annotations

import argparse
import csv
import json
import subprocess
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

OUTCOMES = ("caught_by_reject_impossible", "outvoted", "withdrawn", "fooled", "neither")


def read_csv(path) -> list[dict]:
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def final_rows(plan_path: Path | None = None) -> set[tuple[str, str]]:
    """The (experiment, detection setting) rows that are among the 13 final settings of final_plan.json (the left-turn A2 is not a row of the 16-row table)."""
    plan = json.loads((plan_path or ROOT / "configs/v4/final_plan.json").read_text(encoding="utf-8"))["settings"]
    return {(v["experiment"], v["lie_detection"]) for v in plan.values() if v.get("map") != "turn_left"}


def _is(value, want: bool) -> bool:
    """The CSV booleans are written lower case ("true" / "false"); an empty cell is neither."""
    return str(value).strip().lower() == ("true" if want else "false")


def classify(row: dict) -> str:
    if row["decision"].startswith("rejected"):
        return "caught_by_reject_impossible"
    if _is(row["outvoted"], True):
        return "outvoted"
    if _is(row["withdrawn"], True):
        return "withdrawn"
    if row["decision"] == "accepted" and row["branch_read"] and row["final_branch"] == row["branch_read"] and row["branch_read"] != row["true_branch"]:
        return "fooled"
    return "neither"


def lie_split(dialogs: list[dict]) -> dict:
    """{"first": Counter, "later": Counter, "asks": n} over the lying asks (truthful False) of these dialogue rows (one experiment and setting)."""
    visits: dict = defaultdict(list)
    for r in dialogs:
        visits[(r["session"], r["run"], r["junction"], r["visit"])].append(r)
    out = {"first": Counter(), "later": Counter()}
    for rows in visits.values():
        first = min(rows, key=lambda r: (int(r["dialog"]), int(r["serial"])))["worker"]
        for r in rows:
            if _is(r["truthful"], False):
                out["first" if r["worker"] == first else "later"][classify(r)] += 1
    out["lying_asks"] = sum(sum(out[k].values()) for k in ("first", "later"))
    return out


def row_summary(runs: list[dict], dialogs: list[dict], exp: str, setting: str) -> dict:
    rr = [r for r in runs if r["experiment"] == exp and r["setting"] == setting]
    ok = [float(r["time_s"]) for r in rr if r["outcome"] == "SUCCESS"]
    fails = Counter(r["failure_reason"] for r in rr if r["outcome"] != "SUCCESS")

    def goal(g):
        x = [r for r in rr if r["goal"] == g]
        s = [float(r["time_s"]) for r in x if r["outcome"] == "SUCCESS"]
        return {"runs": len(x), "success": len(s), "longest_s": max(s) if s else None}
    out = {"experiment": exp, "setting": setting, "runs": len(rr), "success": len(ok), "failures": dict(fails),
           "collisions": sum(int(float(r["collisions"] or 0)) for r in rr), "longest_successful_s": max(ok) if ok else None, "E5": goal("E5"), "E6": goal("E6")}
    if exp.startswith("B"):
        dd = [d for d in dialogs if d["experiment"] == exp and d["session"] in {r["session"] for r in rr}]
        sp = lie_split(dd)
        out["lies"] = {"lying_asks": sp["lying_asks"], "first": dict(sp["first"]), "later": dict(sp["later"]),
                       "runs_csv": {"given": sum(int(float(r["lies_given"] or 0)) for r in rr), "detected": sum(int(float(r["lies_detected"] or 0)) for r in rr),
                                    "fooled": sum(int(float(r["lies_fooled"] or 0)) for r in rr)}}
        det = sum(sp[k][o] for k in ("first", "later") for o in ("caught_by_reject_impossible", "outvoted", "withdrawn"))
        fooled = sum(sp[k]["fooled"] for k in ("first", "later"))
        out["lies"]["consistent_with_runs_csv"] = (det == out["lies"]["runs_csv"]["detected"] and fooled == out["lies"]["runs_csv"]["fooled"])
    return out


def load_folder(folder) -> dict:
    f = Path(folder)
    runs, dialogs = read_csv(f / "runs.csv"), read_csv(f / "dialogs.csv")
    rows = []
    seen = []
    for r in runs:
        k = (r["experiment"], r["setting"])
        if k not in seen:
            seen.append(k)
    for exp, st in seen:
        rows.append(row_summary(runs, dialogs, exp, st))
    return {"folder": f.name, "rows": rows}


def _fmt_goal(g: dict) -> str:
    return f"{g['runs']}, {g['success']}, {g['longest_s'] if g['longest_s'] is not None else '-'}" if g["runs"] else "0"


def markdown(cur: dict, finals: set, title: str, previous: dict | None = None) -> str:
    L = [f"## {title}: `{cur['folder']}`", "",
         "| experiment | detection | final setting | SUCCESS | failures | collisions | longest successful s | E5: runs, successes, longest s | E6: runs, successes, longest s |",
         "|---|---|---|---|---|---|---|---|---|"]
    for r in cur["rows"]:
        fin = "**final**" if (r["experiment"], r["setting"]) in finals else "-"
        L.append(f"| {r['experiment']} | {r['setting']} | {fin} | {r['success']}/{r['runs']} | {', '.join(f'{k} {v}' for k, v in r['failures'].items()) or '-'} | {r['collisions']} | "
                 f"{r['longest_successful_s'] if r['longest_successful_s'] is not None else '-'} | {_fmt_goal(r['E5'])} | {_fmt_goal(r['E6'])} |")
    b = [r for r in cur["rows"] if "lies" in r]
    if b:
        L += ["", "Lies by who lied and what became of the lie (lying asks of the dialogue table):", "",
              "| experiment | detection | lying asks | first-asked liar: asks / caught by reject_impossible / outvoted / withdrawn / fooled / neither | later-asked liar: asks / caught by reject_impossible / outvoted / withdrawn / fooled / neither | runs.csv: given / detected / fooled | totals agree |",
              "|---|---|---|---|---|---|---|"]
        for r in b:
            ls = r["lies"]
            cell = lambda c: f"{sum(c.values())} / " + " / ".join(str(c.get(o, 0)) for o in OUTCOMES)
            L.append(f"| {r['experiment']} | {r['setting']} | {ls['lying_asks']} | {cell(ls['first'])} | {cell(ls['later'])} | "
                     f"{ls['runs_csv']['given']} / {ls['runs_csv']['detected']} / {ls['runs_csv']['fooled']} | {'yes' if ls['consistent_with_runs_csv'] else 'NO'} |")
    if previous is not None:
        prev = {(r["experiment"], r["setting"]): r for r in previous["rows"]}
        L += ["", f"Against the previous layout (`{previous['folder']}`):", "",
              "| experiment | detection | previous: SUCCESS, collisions, longest s | now: SUCCESS, collisions, longest s | previous fooled (first / later) | now fooled (first / later) |", "|---|---|---|---|---|---|"]
        for r in cur["rows"]:
            p = prev.get((r["experiment"], r["setting"]))
            if p is None:
                continue
            f = lambda x: f"{x['success']}/{x['runs']}, {x['collisions']}, {x['longest_successful_s'] if x['longest_successful_s'] is not None else '-'}"
            fo = lambda x: (f"{x['lies']['first'].get('fooled', 0)} / {x['lies']['later'].get('fooled', 0)}" if "lies" in x else "-")
            L.append(f"| {r['experiment']} | {r['setting']} | {f(p)} | {f(r)} | {fo(p)} | {fo(r)} |")
    return "\n".join(L)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--folder", required=True, action="append", help="a run_experiments_ab_v4 folder; repeat for several (e.g. the 270 s and the 420 s one)")
    ap.add_argument("--previous", action="append", default=[], help="the previous-layout folder for each --folder, in the same order (optional)")
    ap.add_argument("--title", action="append", default=[])
    ap.add_argument("--label", default="")
    a = ap.parse_args(argv)
    finals = final_rows()
    parts, data = [], []
    for i, f in enumerate(a.folder):
        cur = load_folder(f)
        prev = load_folder(a.previous[i]) if i < len(a.previous) else None
        title = a.title[i] if i < len(a.title) else f"Folder {i + 1}"
        parts.append(markdown(cur, finals, title, prev))
        data.append({"title": title, "current": cur, "previous": prev})
    out = ROOT / "outputs" / f"report_rows_ab_v4_{time.strftime('%Y%m%d_%H%M%S')}{'_' + a.label if a.label else ''}"
    out.mkdir(parents=True, exist_ok=False)
    md = "\n\n".join(parts)
    (out / "report.md").write_text(md + "\n", encoding="utf-8")
    (out / "report.json").write_text(json.dumps(data, indent=1, default=str), encoding="utf-8")
    commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    (out / "run.json").write_text(json.dumps({"git_commit": commit, "folders": a.folder, "previous": a.previous, "final_rows": sorted(finals)}, indent=1), encoding="utf-8")
    print(md)
    print(f"\nFolder: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
