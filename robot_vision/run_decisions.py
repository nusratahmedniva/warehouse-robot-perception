"""Step 9: run the decision rules on scenario files and write decisions.csv + decision_log.json per scenario.

No dataset, no inference, no reference data. Each invocation writes a new folder
<output_root>/decisions_scenarios_<date>_<time>/ with one subfolder per scenario, the exact configs used, the git
commit and summary.json (expectation checks per scenario).

Usage (from robot_vision/):
    python run_decisions.py --all-scenarios
    python run_decisions.py --scenario tests/scenarios/rule1_person_in_route.json
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import decision_io as dio

SCENARIO_DIR = "tests/scenarios"


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--config", default=dio.DEFAULT_CONFIG)
    p.add_argument("--scenario", action="append", default=[], help="scenario JSON (repeatable)")
    p.add_argument("--all-scenarios", action="store_true", help=f"every {SCENARIO_DIR}/*.json")
    a = p.parse_args()
    paths = [dio.resolve(s) for s in a.scenario]
    if a.all_scenarios:
        paths += sorted(dio.resolve(SCENARIO_DIR).glob("*.json"))
    if not paths:
        p.error("give --scenario or --all-scenarios")

    cfg_path = dio.resolve(a.config)
    cfg, robot, load, req = dio.load_decision_config(cfg_path)
    out = dio.new_run_dir(cfg, "decisions_scenarios")
    hashes = dio.copy_configs(out, [cfg_path] + dio.footprint_files(req))
    info = dio.run_info(cfg_path, {"config_sha256": hashes, "required_width": dio.footprint_record(req),
                                   "look_ahead": cfg["look_ahead"],
                                   "required_width_label": load["label"], "decision_config": cfg,
                                   "robot_config": robot, "load_config": load,
                                   "inputs": "scenario files (placeholder providers); no dataset"})
    dio.write_json(out / "run_info.json", info)

    summary = {}
    for sp in paths:
        sc = json.loads(sp.read_text(encoding="utf-8"))
        problems = dio.check_assumptions(sc, cfg, req)
        decisions = dio.run_scenario(sc, cfg, req)
        errors = dio.check_expectations(sc, decisions)
        sub = out / sc["name"]
        sub.mkdir()
        (sub / sp.name).write_bytes(sp.read_bytes())
        dio.write_decisions(sub, decisions, {"scenario": sc["name"], "description": sc.get("description", ""),
                                             "scenario_file": str(sp), "scenario_sha256": dio.sha256(sp),
                                             "git": info["git"], "required_width": dio.footprint_record(req)})
        summary[sc["name"]] = {"frames": len(decisions), "assumption_mismatches": problems,
                               "expectation_errors": errors[:20], "n_expectation_errors": len(errors),
                               "passed": not problems and not errors}
        print(f"{'PASS' if summary[sc['name']]['passed'] else 'FAIL'}  {sc['name']}  ({len(decisions)} frames)")
        for msg in problems + errors[:5]:
            print("      ", msg)
    dio.write_json(out / "summary.json", {"all_passed": all(s["passed"] for s in summary.values()),
                                          "scenarios": summary})
    dio.mark_complete(out)
    print(f"Wrote {out}")


if __name__ == "__main__":
    main()
