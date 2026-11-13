"""Run experiments A1-A4 and B1-B4 in the SIMULATOR (hri_sim_v4.py) and report the table (AUDIT.md section 16). Simulator only: the numbers
are properties of its geometry and noise model (neutral gesture reader, perfect tracker, routes with a detour around people), not
measurements, and are labelled "simulator" everywhere.

For each experiment (A1-A4 truthful workers, B1-B4 each gesture a lie with probability 0.2) and each lie-detection setting (off: every
switch false; on: second opinion + reject impossible + backtrack) it runs `runs` seeded runs (run k uses seed first_seed + k - 1;
configs/v4/experiments/scenarios_ab.json), writes them as session folders exactly as a real session leaves them (hri_sim_v4.export_session),
exports runs.csv and dialogs.csv (export_csv_v4.py, columns from configs/v4/experiments/export_csv.json) and the summary table (table.md,
table.json). Set A with detection on is an extra beyond the plan (it shows what detection costs when nobody lies).

Usage (from robot_vision/):
  python run_experiments_ab_v4.py [--runs 20] [--timeout-s 270] [--experiments A1 B3 ...] [--settings off on a b bc ab] [--label x]
Writes a new folder <output_root>/experiments_ab_v4_<time>[_label]/ (never overwrites) with sessions/, runs.csv, dialogs.csv, table.md,
table.json, config_used/ and run.json (git commit, runs, timeout)."""

from __future__ import annotations

import argparse
import json
import statistics as st
from collections import Counter, defaultdict
from pathlib import Path

import export_csv_v4 as ex
import gesture_data as gd
import hri_analysis as ha
import hri_eval_dev_v4 as ev
import hri_sim as hs
import hri_sim_v4 as sv

EXPERIMENTS = ("A1", "A2", "A3", "A4", "B1", "B2", "B3", "B4")
# the lie-detection settings: off / on are the plan's; the others show one rule or a pair alone (an extra beyond the plan)
SETTINGS = {
    "off": sv.DETECTION_OFF,
    "on": sv.DETECTION_ON,
    "a": {"second_opinion": True, "reject_impossible": False, "backtrack": False},
    "b": {"second_opinion": False, "reject_impossible": True, "backtrack": False},
    "bc": {"second_opinion": False, "reject_impossible": True, "backtrack": True},
    "ab": {"second_opinion": True, "reject_impossible": True, "backtrack": False},
}
ORDER = list(SETTINGS)
NAMES = {"off": "off", "on": "on (a+b+c)", "a": "a: second opinion only", "b": "b: reject only", "bc": "b+c: reject + backtrack",
         "ab": "a+b: second opinion + reject"}


def detection_label(row: dict) -> str:
    flags = {"second_opinion": bool(row.get("second_opinion_on")), "reject_impossible": bool(row.get("reject_impossible_on")),
             "backtrack": bool(row.get("backtrack_on"))}
    return next((k for k, v in SETTINGS.items() if v == flags), "partial")


def run_all(out_root: Path, runs: int, timeout_s: float, experiments=EXPERIMENTS, scen: dict | None = None,
            settings=("off", "on")) -> list[tuple[Path, Path]]:
    """Simulate and write the session folders; returns the (UNITY, BRIDGE) pairs in order."""
    scen = scen if scen is not None else sv.load_scenarios()
    first = int(scen["first_seed"])
    cfg = hs.SimConfig(timeout_s=timeout_s)
    pairs = []
    for name in experiments:
        for label in settings:
            det = SETTINGS[label]
            results = [sv.run_scenario(name, first + k, det, scen=scen, sim_cfg=cfg) for k in range(runs)]
            pairs.append(sv.export_session(results, out_root, True, seed=first, name=f"{name}_{label}",
                                           road_cfg=results[0]["road_cfg"], v4_override=results[0]["v4_config"],
                                           session_extra={"experiment": name, "set": name[0],
                                                          "lie_probability": results[0]["lie_probability"],
                                                          "lie_detection": label, "source": "simulator"}))
    return pairs


def summarise(run_rows: list[dict]) -> list[dict]:
    """One row per (experiment, detection): successes with a Wilson interval, failure reasons, times and the lie counts."""
    groups: dict = defaultdict(list)
    for r in run_rows:
        groups[(r["experiment"], detection_label(r))].append(r)
    out = []
    for (exp, det), rows in sorted(groups.items(), key=lambda kv: (kv[0][0], ORDER.index(kv[0][1]) if kv[0][1] in ORDER else 99)):
        n = len(rows)
        ok = sum(r["outcome"] == "SUCCESS" for r in rows)
        lo, hi = ha.wilson(ok, n)
        times = [r["time_s"] for r in rows if r["time_s"] is not None]
        ratio = [r["trail_over_optimal"] for r in rows if r["outcome"] == "SUCCESS" and r["trail_over_optimal"] is not None]
        s = lambda k: sum(r[k] or 0 for r in rows)  # noqa: E731
        out.append({
            "experiment": exp, "detection": det, "runs": n, "success": ok, "success_rate": round(ok / n, 3) if n else None,
            "success_ci95": [round(lo, 3), round(hi, 3)] if lo is not None else None,
            "failures": dict(Counter(r["failure_reason"] for r in rows if r["outcome"] != "SUCCESS")),
            "median_time_s": round(st.median(times), 1) if times else None,
            "median_trail_over_optimal_success": round(st.median(ratio), 3) if ratio else None,
            "lies_given": s("lies_given"), "lies_detected": s("lies_detected"), "lies_corrected": s("lies_corrected"),
            "lies_fooled": s("lies_fooled"), "runs_with_lies": sum((r["lies_given"] or 0) > 0 for r in rows),
            "collisions": s("collisions"), "safety_stops": s("stops"), "rejections": s("rejections"),
            "second_opinions": s("second_opinions"), "backtracks": s("backtracks"),
        })
    return out


def markdown(rows: list[dict], meta: dict) -> str:
    def frac(k, n):
        return f"{k}/{n}" if n else "0/0"
    lines = [f"# Experiments A and B (SIMULATOR; AUDIT.md section 16)", "",
             f"{meta['runs']} seeded runs per experiment and setting (seeds {meta['first_seed']} to {meta['first_seed'] + meta['runs'] - 1}), "
             f"trial timeout {meta['timeout_s']:g} s, neutral gesture reader (coverage 1, accuracy 1, no angle noise), perfect tracker, "
             "routes with a detour around people. Numbers are properties of the simulator, not measurements.", "",
             "| experiment | detection | runs | SUCCESS (95 % Wilson) | failures | median time s | lies given | detected | corrected | fooled | "
             "collisions | safety stops | rejections | 2nd opinions | backtracks |",
             "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for r in rows:
        ci = r["success_ci95"]
        fail = ", ".join(f"{k} {v}" for k, v in sorted(r["failures"].items())) or "-"
        gv = r["lies_given"]
        lines.append(f"| {r['experiment']} | {NAMES.get(r['detection'], r['detection'])} | {r['runs']} | {frac(r['success'], r['runs'])} = {r['success_rate']:.2f} "
                     f"({ci[0]:.2f} to {ci[1]:.2f}) | {fail} | {r['median_time_s']} | {gv} | {frac(r['lies_detected'], gv)} | "
                     f"{frac(r['lies_corrected'], r['lies_detected'])} | {frac(r['lies_fooled'], gv)} | {r['collisions']} | "
                     f"{r['safety_stops']} | {r['rejections']} | {r['second_opinions']} | {r['backtracks']} |")
    lines += ["", "Lies: given = lying gestures in truth.jsonl; detected = rejected, outvoted or withdrawn by a backtrack (of those given); "
              "corrected = detected and the visit ended with the true branch (of those detected); fooled = acted on and not the true branch "
              "(of those given). A lie that is neither detected nor fooled was ignored or read as the right branch. "
              "Detection 'on' = second opinion (a) + reject impossible (b) + backtrack (c). Set A with detection on, and the rule-by-rule "
              "settings, are extras beyond the plan."]
    return "\n".join(lines) + "\n"


def main(argv=None) -> None:
    import decision_io as dio

    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    scen = sv.load_scenarios()
    ap.add_argument("--runs", type=int, default=int(scen["runs_per_scenario"]))
    ap.add_argument("--timeout-s", type=float, default=float(scen["trial_timeout_s"]))
    ap.add_argument("--experiments", nargs="+", default=list(EXPERIMENTS), choices=EXPERIMENTS)
    ap.add_argument("--settings", nargs="+", default=["off", "on"], choices=ORDER,
                    help="lie-detection settings to run: off and on (the plan); a, b, bc, ab = one rule or a pair alone (extra)")
    ap.add_argument("--label", default="")
    ap.add_argument("--config", default=ex.DEFAULT_CONFIG)
    a = ap.parse_args(argv)
    cfg_path = dio.resolve(a.config)
    cfg = ex.load_config(cfg_path)
    ex.check_columns(cfg)
    out = dio.new_run_dir({"paths": {"output_root": "outputs"}}, "experiments_ab_v4" + (f"_{a.label}" if a.label else ""))
    (out / "config_used").mkdir()
    for p in (dio.resolve(sv.AB_CONFIG), cfg_path, dio.resolve("configs/v4/control.json"), dio.resolve("configs/v4/commander.json"),
              dio.resolve("configs/v4/roadmap.json"), dio.resolve("configs/hri_control.json")):
        (out / "config_used" / p.name).write_bytes(p.read_bytes())
    pairs = run_all(out / "sessions", a.runs, a.timeout_s, a.experiments, scen, a.settings)
    runs = ev.load_sessions(pairs, gd.load_config())
    run_rows, dialog_rows = ex.build_tables(runs)
    ex.write_csv(out / "runs.csv", run_rows, cfg["runs"], cfg.get("empty", ""))
    ex.write_csv(out / "dialogs.csv", dialog_rows, cfg["dialogs"], cfg.get("empty", ""))
    table = summarise(run_rows)
    meta = {"runs": a.runs, "timeout_s": a.timeout_s, "first_seed": int(scen["first_seed"]), "experiments": a.experiments,
            "settings": a.settings, "source": "simulator"}
    dio.write_json(out / "table.json", {"meta": meta, "rows": table})
    (out / "table.md").write_text(markdown(table, meta), encoding="utf-8")
    dio.write_json(out / "run.json", {"git": dio.git_info(), **meta})
    print(markdown(table, meta))
    print(f"Folder: {out}")


if __name__ == "__main__":
    main()
