"""Out-of-sample check of T4 (AUDIT.md 16.24.2, 2026-11-18). EVALUATION CODE: reads runs.json of run_t3_v4.py (fresh seeds, T0 and T4; the gestures staged with their
truth included); nothing in the controller or the simulator imports it.

Per row (experiment x setting x variant): successes with a 95% Wilson interval; for T4 the difference of the success rates to T0 with a 95% Newcombe (hybrid score, method 10)
interval, and the seeds that changed in each direction; wrong goals, aborts, timeouts, backtracks, FALSE backtracks, the most people in view; median / 95th percentile (linear
interpolation, numpy's default) / maximum duration of the successful runs; the timeout the declared rule would give from the longest successful run (information only).
The pass bar of 16.24.2: in B3 on AND B4 on the success rate of T4 exceeds T0's by at least 15 percentage points, and no A row loses a success or backtracks.
The estimate of the total time of the 260 final runs: 20 x the sum over the 13 final settings of the mean duration of ALL runs of the row (failures included).

Usage (from robot_vision/): python report_t4_oos_v4.py --folder outputs/t3_v4_<a> [--label x]
Writes outputs/report_t4_oos_v4_<time>[_label]/ (table.md, table.json, run.json with the git commit); never overwrites."""

from __future__ import annotations

import argparse
import json
import math
import statistics
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

import final_guard_v4 as fg  # noqa: E402
import report_rows_ab_v4 as rr  # noqa: E402
import report_t3_v4 as rt  # noqa: E402

Z = 1.959964
BAR_PP = 15.0
FINAL_PLAN = "configs/v4/final_plan.json"


def wilson(k: int, n: int, z: float = Z) -> tuple[float, float]:
    if n == 0:
        return 0.0, 1.0
    p = k / n
    d = 1.0 + z * z / n
    c = p + z * z / (2 * n)
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return max(0.0, (c - h) / d), min(1.0, (c + h) / d)


def newcombe(k1: int, n1: int, k2: int, n2: int, z: float = Z) -> tuple[float, float, float]:
    """(difference p1 - p2, lower, upper): Newcombe's hybrid score interval (method 10) for two independent proportions."""
    p1, p2 = k1 / n1, k2 / n2
    l1, u1 = wilson(k1, n1, z)
    l2, u2 = wilson(k2, n2, z)
    d = p1 - p2
    return d, d - math.sqrt((p1 - l1) ** 2 + (u2 - p2) ** 2), d + math.sqrt((u1 - p1) ** 2 + (p2 - l2) ** 2)


def percentile(values: list[float], q: float) -> float | None:
    """numpy's default (linear interpolation between order statistics)."""
    v = sorted(values)
    if not v:
        return None
    pos = q * (len(v) - 1)
    lo = int(math.floor(pos))
    hi = min(lo + 1, len(v) - 1)
    return v[lo] + (v[hi] - v[lo]) * (pos - lo)


def row_stats(rows: list[dict]) -> dict:
    """The statistics of one (experiment, setting, variant) group of run records."""
    ok = [r["time_s"] for r in rows if r["outcome"] == "SUCCESS"]
    reasons = [r["failure_reason"] for r in rows if r["outcome"] != "SUCCESS"]
    m = [rt.run_metrics(r) for r in rows]
    return {"runs": len(rows), "success": len(ok), "wrong_goal": reasons.count("wrong_goal"), "aborted": reasons.count("aborted"), "timeout": reasons.count("timeout"),
            "collision": reasons.count("collision"), "backtracks": sum(x["backtracks"] for x in m), "nj_backtracks": sum(x["nj_backtracks"] for x in m), "false_backtracks": sum(x["false_backtracks"] for x in m),
            "max_people_in_view": max(r["max_people_in_view"] for r in rows), "median_s": statistics.median(ok) if ok else None, "p95_s": percentile(ok, 0.95),
            "max_s": max(ok) if ok else None, "mean_all_s": statistics.fmean(r["time_s"] for r in rows),
            "rule_timeout_s": fg.timeout_from_development(max(ok)) if ok else None}


def groups(rows: list[dict]) -> dict:
    g: dict = {}
    for r in rows:
        g.setdefault((r["experiment"], r["setting"], r["variant"]), []).append(r)
    return {k: sorted(v, key=lambda r: r["seed"]) for k, v in g.items()}


def paired(t0: list[dict], t4: list[dict]) -> dict:
    a = {r["seed"]: r["outcome"] == "SUCCESS" for r in t0}
    b = {r["seed"]: r["outcome"] == "SUCCESS" for r in t4}
    return {"gained": sum(1 for s in a if not a[s] and b.get(s)), "lost": sum(1 for s in a if a[s] and not b.get(s))}


def evaluate(rows: list[dict]) -> dict:
    g = groups(rows)
    stats = {k: row_stats(v) for k, v in g.items()}
    diffs, bar = {}, {}
    for (exp, setting, var), s in stats.items():
        if var != "T4":
            continue
        t0 = stats[(exp, setting, "T0")]
        d, lo, hi = newcombe(s["success"], s["runs"], t0["success"], t0["runs"])
        diffs[(exp, setting)] = {"diff_pp": 100 * d, "lo_pp": 100 * lo, "hi_pp": 100 * hi, **paired(g[(exp, setting, "T0")], g[(exp, setting, "T4")])}
    b_ok = {exp: diffs[(exp, "on")]["diff_pp"] >= BAR_PP - 1e-9 for exp in ("B3", "B4")}
    a_lost = {f"{e} {st}": stats[(e, st, "T0")]["success"] - stats[(e, st, "T4")]["success"]
              for (e, st, v) in stats if v == "T4" and e.startswith("A") and stats[(e, st, "T4")]["success"] < stats[(e, st, "T0")]["success"]}
    a_bt = {f"{e} {st}": stats[(e, st, "T4")]["backtracks"] for (e, st, v) in stats if v == "T4" and e.startswith("A") and stats[(e, st, "T4")]["backtracks"]}
    bar = {"B_on_gain_pp": {e: diffs[(e, "on")]["diff_pp"] for e in ("B3", "B4")}, "B_on_pass": b_ok, "needed_pp": BAR_PP, "A_success_lost_vs_T0": a_lost, "A_backtracks": a_bt,
           "adopted": all(b_ok.values()) and not a_lost and not a_bt}
    return {"stats": stats, "diffs": diffs, "bar": bar}


def total_time(stats: dict, variant: str, plan_path: Path | None = None, runs_per_setting: int = 20) -> dict:
    """20 x the sum, over the 13 final settings of final_plan.json, of the mean duration of all runs of the row (A2 on the left turn takes the A2 on row)."""
    plan = json.loads((plan_path or ROOT / FINAL_PLAN).read_text(encoding="utf-8"))["settings"]
    per = {k: stats[(v["experiment"], v["lie_detection"], variant)]["mean_all_s"] for k, v in plan.items()}
    total = runs_per_setting * sum(per.values())
    return {"settings": len(per), "runs": runs_per_setting * len(per), "per_setting_mean_s": per, "total_s": total, "total_h": total / 3600.0}


def markdown(res: dict, finals: set, folder: str, t_t0: dict, t_t4: dict) -> str:
    st, df = res["stats"], res["diffs"]
    f = lambda x: "-" if x is None else f"{x:.1f}"
    L = ["| experiment | detection | final | variant | SUCCESS (95% Wilson) | T4 - T0, pp (95% Newcombe); seeds gained / lost | wrong goal | aborted | timeout | backtracks | false backtracks | most people in view | median s | p95 s | max s | timeout by the rule s |",
         "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for (exp, setting, var), s in sorted(st.items(), key=lambda kv: (kv[0][0], kv[0][1] != "off", kv[0][2])):
        lo, hi = wilson(s["success"], s["runs"])
        d = df.get((exp, setting)) if var == "T4" else None
        dtxt = f"{d['diff_pp']:+.1f} ({d['lo_pp']:+.1f} to {d['hi_pp']:+.1f}); {d['gained']} / {d['lost']}" if d else "-"
        L.append(f"| {exp} | {setting} | {'**final**' if (exp, setting) in finals else '-'} | {var} | {s['success']}/{s['runs']} = {100 * s['success'] / s['runs']:.1f}% ({100 * lo:.1f} to {100 * hi:.1f}) | {dtxt} | "
                 f"{s['wrong_goal']} | {s['aborted']} | {s['timeout']} | {s['backtracks']}{' (' + str(s['nj_backtracks']) + ' at the next junction)' if s['nj_backtracks'] else ''} | {s['false_backtracks']} | {s['max_people_in_view']} | {f(s['median_s'])} | {f(s['p95_s'])} | "
                 f"{f(s['max_s'])} | {f(s['rule_timeout_s'])} |")
    b = res["bar"]
    L += ["", f"Folder: `{folder}`", "",
          f"**Pass bar of 16.24.2** (B3 on and B4 on each at least {b['needed_pp']:g} percentage points above T0; no A row loses a success or backtracks): "
          f"gains B3 on {b['B_on_gain_pp']['B3']:+.1f} pp, B4 on {b['B_on_gain_pp']['B4']:+.1f} pp; A rows losing a success: {b['A_success_lost_vs_T0'] or 'none'}; A rows with a backtrack: "
          f"{b['A_backtracks'] or 'none'}; **{'PASSED: T4 adopted' if b['adopted'] else 'FAILED: T4 not adopted, the stopping rule of 16.24 applies (checkpoints dropped, T0 stays)'}**.", "",
          "Estimate of the total time of the 260 final runs (20 runs x 13 settings; mean duration of all runs of the row, failures included, a timeout = the cap; simulated time only, "
          "A2 on the left turn = the A2 on row):", "",
          "| variant | total s | total h | per setting (mean s) |", "|---|---|---|---|"]
    for name, t in (("T0", t_t0), ("T4", t_t4)):
        L.append(f"| {name} | {t['total_s']:.0f} | {t['total_h']:.2f} | " + ", ".join(f"{k} {v:.0f}" for k, v in t["per_setting_mean_s"].items()) + " |")
    L.append(f"\nT4 - T0: {t_t4['total_s'] - t_t0['total_s']:+.0f} s ({t_t4['total_h'] - t_t0['total_h']:+.2f} h).")
    return "\n".join(L)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--folder", required=True)
    ap.add_argument("--label", default="")
    a = ap.parse_args(argv)
    folder = Path(a.folder)
    rows = json.loads((folder / "runs.json").read_text(encoding="utf-8"))
    meta = json.loads((folder / "run.json").read_text(encoding="utf-8"))
    res = evaluate(rows)
    t0, t4 = total_time(res["stats"], "T0"), total_time(res["stats"], "T4")
    finals = rr.final_rows()
    md = markdown(res, finals, folder.name, t0, t4)
    out = ROOT / "outputs" / f"report_t4_oos_v4_{time.strftime('%Y%m%d_%H%M%S')}{'_' + a.label if a.label else ''}"
    out.mkdir(parents=True, exist_ok=False)
    (out / "table.md").write_text(md + "\n", encoding="utf-8")
    js = {"stats": {" | ".join(k): v for k, v in res["stats"].items()}, "diffs": {" | ".join(k): v for k, v in res["diffs"].items()}, "bar": res["bar"], "total_time": {"T0": t0, "T4": t4},
          "first_seed": meta["first_seed"], "runs": meta["runs"], "timeout_s": meta["timeout_s"]}
    (out / "table.json").write_text(json.dumps(js, indent=1, default=str), encoding="utf-8")
    commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    (out / "run.json").write_text(json.dumps({"git_commit": commit, "folder": str(folder), "final_rows": sorted(finals)}, indent=1), encoding="utf-8")
    print(md)
    print(f"\nFolder: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
