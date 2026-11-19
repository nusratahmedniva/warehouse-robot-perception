"""Variant T3 "checkpoint workers" against T0 (AUDIT.md 16.23, 2026-11-18). SIMULATOR ONLY; the numbers are properties of its geometry and noise model, not measurements.

For each experiment (A1-A4, B1-B4), each setting (off, on) and each variant it runs `runs` seeded runs (run k uses seed first_seed + k - 1, as run_experiments_ab_v4.py):
  T0  the current behaviour: no checkpoint workers; "on" = second opinion + reject_impossible
  T4  T3 with lie_detection.checkpoint_scope "disputed" (AUDIT.md 16.24): a checkpoint pointing back counts only when the junction's answers disagreed
  T3  checkpoint workers in the scene (configs/v4/experiments/checkpoints.json, provisional positions) in BOTH settings; "on" = T0's "on" + lie_detection.checkpoint
      (the robot stops at the midpoint of every branch leaving a decision junction and asks the checkpoint worker); "off" = every switch false (the robot ignores them)
It writes the raw record of every run (outcome, duration, the junction decisions, the gestures staged with their truth, the checkpoint log, the most people in view) to runs.json;
report_t3_v4.py (evaluation code) turns it into the table. No session folders are exported (the standard export is for the Unity-comparable pipeline).

Usage (from robot_vision/): python run_t3_v4.py [--runs 20] [--timeout-s 420] [--experiments A1 ...] [--variants T0 T3] [--label x]
Writes a new folder <output_root>/t3_v4_<time>[_label]/ (never overwrites): runs.json, run.json (git commit, runs, timeout), config_used/."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import decision_io as dio
import hri_sim as hs
import hri_sim_v4 as sv

EXPERIMENTS = ("A1", "A2", "A3", "A4", "B1", "B2", "B3", "B4")
VARIANTS = ("T0", "T3", "T4")
CP_CONFIG = "configs/v4/experiments/checkpoints.json"
KEEP_EVENTS = ("go", "backtrack", "take_other_branch", "checkpoint_answer", "abort", "answer_rejected", "backtrack_blocked")


def detection_for(variant: str, setting: str, cp_cfg: dict) -> dict:
    """The lie_detection switches of one (variant, setting)."""
    if setting == "off":
        return dict(sv.DETECTION_OFF)
    if variant == "T0":
        return dict(sv.DETECTION_ON)
    on = {**sv.DETECTION_ON, "checkpoint": True, "checkpoint_fraction": float(cp_cfg["fraction"])}
    return {**on, "checkpoint_scope": "disputed"} if variant == "T4" else on


def one_run(variant: str, name: str, setting: str, seed: int, timeout_s: float, cp_cfg: dict, scen: dict) -> dict:
    sc = sv.scenario_ab(name, seed, detection_for(variant, setting, cp_cfg), scen=scen, sim_cfg=hs.SimConfig(timeout_s=timeout_s),
                        checkpoints=cp_cfg if variant in ("T3", "T4") else None)
    road, goal = sc["road"], sc["goal"]
    r = sc["sim"].run(goal)
    v4 = r["v4"]
    return {"variant": variant, "experiment": name, "setting": setting, "seed": seed, "goal": goal, "outcome": r["outcome"], "failure_reason": r["failure_reason"],
            "time_s": r["time_s"], "max_people_in_view": r["max_people_in_view"], "closest_person_m": r["closest_person_m"], "route": v4["route"],
            "go": [{"node": d["node"], "branch": d["branch"], "correct": road.command_toward(d["node"], goal)} for d in v4["decisions"] if d["event"] == "go"],
            "decisions": [d for d in v4["decisions"] if d["event"] in KEEP_EVENTS], "gestures": r["gestures"], "checkpoint": v4["checkpoint"],
            "safety_stops": v4["safety_stops"]}


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    scen = sv.load_scenarios()
    ap.add_argument("--runs", type=int, default=int(scen["runs_per_scenario"]))
    ap.add_argument("--timeout-s", type=float, default=420.0)
    ap.add_argument("--experiments", nargs="+", default=list(EXPERIMENTS), choices=EXPERIMENTS)
    ap.add_argument("--variants", nargs="+", default=list(VARIANTS), choices=VARIANTS)   # all three by default
    ap.add_argument("--first-seed", type=int, default=None,
                    help="the seed of run 1 (default: first_seed of scenarios_ab.json); AUDIT.md 16.24.2 runs seeds 21 to 60 with --first-seed 21 --runs 40 (goals: the same GoalSequence, run k = seed k)")
    ap.add_argument("--label", default="")
    a = ap.parse_args(argv)
    cp_cfg = json.loads(dio.resolve(CP_CONFIG).read_text(encoding="utf-8"))
    out = dio.new_run_dir({"paths": {"output_root": "outputs"}}, "t3_v4" + (f"_{a.label}" if a.label else ""))
    (out / "config_used").mkdir()
    for p in (dio.resolve(sv.AB_CONFIG), dio.resolve(CP_CONFIG), dio.resolve("configs/v4/control.json"), dio.resolve("configs/v4/commander.json"),
              dio.resolve("configs/v4/roadmap.json"), dio.resolve("configs/hri_control.json")):
        (out / "config_used" / p.name).write_bytes(p.read_bytes())
    first = int(scen["first_seed"]) if a.first_seed is None else int(a.first_seed)
    rows = []
    for variant in a.variants:
        for name in a.experiments:
            for setting in ("off", "on"):
                for k in range(a.runs):
                    rows.append(one_run(variant, name, setting, first + k, a.timeout_s, cp_cfg, scen))
    dio.write_json(out / "runs.json", rows)
    meta = {"git": dio.git_info(), "runs": a.runs, "timeout_s": a.timeout_s, "first_seed": first, "experiments": a.experiments, "variants": a.variants,
            "checkpoints": cp_cfg, "source": "simulator"}
    dio.write_json(out / "run.json", meta)
    print(f"{len(rows)} runs")
    print(f"Folder: {out}")


if __name__ == "__main__":
    main()
