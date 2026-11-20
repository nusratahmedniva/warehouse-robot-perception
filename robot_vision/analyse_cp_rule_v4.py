"""What the checkpoint-person rule (AUDIT.md 16.25) and the staging fix (16.25.0) changed, run by run (2026-11-19). ANALYSIS / EVALUATION CODE: it reads runs.json of run_t3_v4.py
(the gestures staged with their truth included) and runs the simulator itself for B; nothing in the controller or the simulator imports it.

  A  16.24 as adopted: the stored runs (the old rule: the nearest person who does not belong to the junction; the scene of the NEXT junction was staged before the checkpoint)
  B  the new rule with the OLD staging (a hook puts the old `_target` of the execute state back): the checkpoints of the branches into a junction find nobody
  C  the new rule with the fixed staging (the runs of --c-folder): every checkpoint asks its own worker

For T4 and the rows with a decision junction (A3, A4, B3, B4 on): successes, wrong goals, aborts, timeouts, backtracks, false backtracks, the checkpoint dialogs by who was asked
(a checkpoint worker, id 100 and up, or a junction worker, below 100) and those that found nobody; the runs whose outcome differs between A and C. Every other row and all of T0 must be
identical in A and C (checked).

Usage (from robot_vision/): python analyse_cp_rule_v4.py --a-folder outputs/t3_v4_<a> --c-folder outputs/t3_v4_<c> [--label x]
Writes outputs/analyse_cp_rule_v4_<time>[_label]/ (report.md, report.json, run.json with the git commit); never overwrites."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
import types
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

import hri_control as hc  # noqa: E402
import hri_control_v4 as hv  # noqa: E402
import hri_sim_v4 as sv  # noqa: E402
import report_t3_v4 as rt  # noqa: E402
import run_t3_v4 as rn  # noqa: E402

ROWS = (("A3", "on"), ("A4", "on"), ("B3", "on"), ("B4", "on"))


def old_target(self):
    """The `_target` before AUDIT.md 16.25.0: in the execute state the target is the next node, not the checkpoint spot."""
    if self.state == "navigate" and self.cp is not None and self.cp["stage"] == "drive":
        return self.cp["point"]
    if self.state == "execute" and self.next_node and self._return_pending():
        return self.road.pos(self.node)
    return hc.Controller._target(self)


def put_old_staging_back(ctrl) -> None:
    ctrl._target = types.MethodType(old_target, ctrl)


def stats(rows: list[dict]) -> dict:
    reasons = [r["failure_reason"] for r in rows if r["outcome"] != "SUCCESS"]
    m = [rt.run_metrics(r) for r in rows]
    asked = Counter()
    for r in rows:
        for e in r["checkpoint"]["log"]:
            if e.get("no_person"):
                asked["found nobody"] += 1
            elif e["person_360"] is None:
                asked["no track id"] += 1
            else:
                asked["a checkpoint worker" if e["person_360"] >= 100 else "a junction worker"] += 1
    return {"runs": len(rows), "success": sum(r["outcome"] == "SUCCESS" for r in rows), "wrong_goal": reasons.count("wrong_goal"), "aborted": reasons.count("aborted"),
            "timeout": reasons.count("timeout"), "backtracks": sum(x["backtracks"] for x in m), "false_backtracks": sum(x["false_backtracks"] for x in m),
            "ignored_undisputed": sum(x["ignored_undisputed"] for x in m), "asked": dict(asked), "dialogs": sum(asked.values())}


def select(rows: list[dict], variant: str, exp: str, setting: str) -> list[dict]:
    return sorted((r for r in rows if r["variant"] == variant and r["experiment"] == exp and r["setting"] == setting), key=lambda r: r["seed"])


def run_b(meta: dict, cp_cfg: dict, scen: dict) -> list[dict]:
    first, runs, cap = int(meta["first_seed"]), int(meta["runs"]), float(meta["timeout_s"])
    return [rn.one_run("T4", exp, setting, first + k, cap, cp_cfg, scen, hook=put_old_staging_back) for exp, setting in ROWS for k in range(runs)]


def compare(a_rows: list[dict], c_rows: list[dict], b_rows: list[dict]) -> dict:
    out = {"rows": {}, "identical_elsewhere": True, "differences": []}
    for exp, setting in ROWS:
        a, c = select(a_rows, "T4", exp, setting), select(c_rows, "T4", exp, setting)
        b = [r for r in b_rows if r["experiment"] == exp and r["setting"] == setting]
        out["rows"][f"{exp} {setting}"] = {"A": stats(a), "B": stats(sorted(b, key=lambda r: r["seed"])), "C": stats(c), "T0": stats(select(c_rows, "T0", exp, setting))}
        for x, y in zip(a, c):
            if (x["outcome"], x["failure_reason"], x["time_s"]) != (y["outcome"], y["failure_reason"], y["time_s"]):
                out["differences"].append({"row": f"{exp} {setting}", "seed": x["seed"], "A": [x["outcome"], x["failure_reason"], x["time_s"]], "C": [y["outcome"], y["failure_reason"], y["time_s"]],
                                           "A_checkpoints": [(e["junction"], e["branch"], e["result"], e["action"], e["person_360"]) for e in x["checkpoint"]["log"]],
                                           "C_checkpoints": [(e["junction"], e["branch"], e["result"], e["action"], e["person_360"]) for e in y["checkpoint"]["log"]]})
    keys = {(r["variant"], r["experiment"], r["setting"], r["seed"]): (r["outcome"], r["failure_reason"], r["time_s"]) for r in a_rows}
    for r in c_rows:
        k = (r["variant"], r["experiment"], r["setting"], r["seed"])
        if (r["variant"] == "T0" or (r["experiment"], r["setting"]) not in ROWS) and keys.get(k) != (r["outcome"], r["failure_reason"], r["time_s"]):
            out["identical_elsewhere"] = False
    return out


def markdown(res: dict, label: str) -> str:
    L = [f"## {label}", "",
         "| row | model | successes | wrong goal | aborted | timeout | backtracks | false backtracks | ignored undisputed | checkpoint dialogs | asked: checkpoint worker | asked: junction worker | found nobody |",
         "|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for row, v in res["rows"].items():
        for m in ("T0", "A", "B", "C"):
            s = v[m]
            a = s["asked"]
            L.append(f"| {row} | {m} | {s['success']}/{s['runs']} | {s['wrong_goal']} | {s['aborted']} | {s['timeout']} | {s['backtracks']} | {s['false_backtracks']} | {s['ignored_undisputed']} | {s['dialogs']} | "
                     f"{a.get('a checkpoint worker', 0)} | {a.get('a junction worker', 0)} | {a.get('found nobody', 0)} |")
    L += ["", f"Every other row and all of T0 identical between A and C: **{res['identical_elsewhere']}**.", "", f"Runs of T4 whose outcome differs between A and C: {len(res['differences'])}"]
    for d in res["differences"][:40]:
        L.append(f"- {d['row']} seed {d['seed']}: A {d['A']} -> C {d['C']}; checkpoints A {d['A_checkpoints']} / C {d['C_checkpoints']}")
    return "\n".join(L)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--a-folder", required=True, action="append")
    ap.add_argument("--c-folder", required=True, action="append")
    ap.add_argument("--label", default="")
    a = ap.parse_args(argv)
    if len(a.a_folder) != len(a.c_folder):
        raise SystemExit("one --a-folder per --c-folder")
    scen = sv.load_scenarios()
    cp_cfg = json.loads((ROOT / rn.CP_CONFIG).read_text(encoding="utf-8"))
    parts, data = [], []
    for fa, fc in zip(a.a_folder, a.c_folder):
        meta = json.loads((Path(fc) / "run.json").read_text(encoding="utf-8"))
        a_rows = json.loads((Path(fa) / "runs.json").read_text(encoding="utf-8"))
        c_rows = json.loads((Path(fc) / "runs.json").read_text(encoding="utf-8"))
        res = compare(a_rows, c_rows, run_b(meta, cp_cfg, scen))
        parts.append(markdown(res, f"seeds {meta['first_seed']} to {int(meta['first_seed']) + int(meta['runs']) - 1}, cap {meta['timeout_s']:g} s: A = `{Path(fa).name}`, C = `{Path(fc).name}`"))
        data.append({"a": fa, "c": fc, **res})
    out = ROOT / "outputs" / f"analyse_cp_rule_v4_{time.strftime('%Y%m%d_%H%M%S')}{'_' + a.label if a.label else ''}"
    out.mkdir(parents=True, exist_ok=False)
    md = "\n\n".join(parts)
    (out / "report.md").write_text(md + "\n", encoding="utf-8")
    (out / "report.json").write_text(json.dumps(data, indent=1, default=str), encoding="utf-8")
    commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    (out / "run.json").write_text(json.dumps({"git_commit": commit, "a": a.a_folder, "c": a.c_folder}, indent=1), encoding="utf-8")
    print(md)
    print(f"\nFolder: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
