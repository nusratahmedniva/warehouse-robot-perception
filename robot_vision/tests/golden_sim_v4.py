"""Golden simulator runs for the 'switches off = behaviour unchanged' test of AUDIT.md section 16 (not a test module).

CASES builds whole v4 simulator trials with the API that existed BEFORE the lie-detection work (hri_control_v4.ControllerV4,
hri_sim_v4.SimulatorV4, SceneSpec, GestureSimConfig; nothing of experiments A and B). tests/golden_sim_v4_baseline.json holds
their results, recorded with this same file on the untouched commit 808f028 (main, 2026-11-13) in a separate worktree:

    python tests/golden_sim_v4.py > tests/golden_sim_v4_baseline.json        (from robot_vision/, on that commit)

test_lie_detection_v4.py runs the cases on the current code and compares every field. They are simulator runs, not data."""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import commander_v4 as cm  # noqa: E402
import hri_control as hc  # noqa: E402
import hri_control_v4 as hv  # noqa: E402
import hri_sim_v4 as sv  # noqa: E402
from hri_sim import SimConfig  # noqa: E402

BYST = dict(bystander_offsets_m=[(1.2, 0.3), (2.0, -0.5)], bystander_looks=["look_b", "look_c"])
NEARER = dict(bystander_offsets_m=[(1.2, 0.3), (-1.95, -0.7)], bystander_looks=["look_b", "look_c"])


def run(goal, road="configs/roadmap.json", spec=None, gcfg=None, cfg=None, seed=1, tiebreak=False, two_view=True, shift=None):
    base, v4 = hv.load_control()
    v4["dialog"]["use_hand_crosscheck_as_tiebreak"] = tiebreak
    v4["dialog"]["two_view_enabled"] = two_view
    if shift is not None:
        base["dialog"]["reask_shift_m"] = shift
    ctrl = hv.ControllerV4(base, v4, cm.load_config(), hc.Roadmap(hc.load_json(road)))
    return sv.SimulatorV4(ctrl, cfg or SimConfig(), gcfg or sv.GestureSimConfig(), spec or sv.SceneSpec(), seed).run(goal)


CASES = {
    "v3map_E1_crosscheck": lambda: run("E1", gcfg=sv.GestureSimConfig(crosscheck_accuracy=1.0), tiebreak=True),
    "v3map_E2": lambda: run("E2"),
    "v3map_E3_second_view": lambda: run("E3"),
    "v3map_E4_second_view": lambda: run("E4"),
    "v3map_E1_abort_no_second_view": lambda: run("E1", two_view=False, shift=0.4),
    "v3map_E3_wrong_crosscheck": lambda: run("E3", gcfg=sv.GestureSimConfig(crosscheck_accuracy=0.0), tiebreak=True),
    "v3map_E4_noise_seed3": lambda: run("E4", gcfg=sv.GestureSimConfig(crosscheck_accuracy=1.0, coverage={"POINT": 0.8},
                                                                       point_angle_sigma_deg=8.0), seed=3, tiebreak=True),
    "v3map_E2_bystanders": lambda: run("E2", spec=sv.SceneSpec(**BYST)),
    "v3map_E2_reapproach": lambda: run("E2", spec=sv.SceneSpec(**NEARER)),
    "v3map_E2_wait_first": lambda: run("E2", spec=sv.SceneSpec(wait_first_s=3.0)),
    "v3map_E2_stop": lambda: run("E2", spec=sv.SceneSpec(stop={"who": "commander", "after_ask_s": 1.0, "hold_s": 1.0})),
    "v4map_E1_proceed": lambda: run("E1", road="configs/v4/roadmap.json", spec=sv.SceneSpec(proceed_forward=True)),
    "v4map_E3_proceed_point": lambda: run("E3", road="configs/v4/roadmap.json", spec=sv.SceneSpec(proceed_forward=True)),
    "v4map_E5_point_seed2": lambda: run("E5", road="configs/v4/roadmap.json", seed=2),
}


def compact(r: dict) -> dict:
    return {"outcome": r["outcome"], "failure_reason": r["failure_reason"], "final_distance_m": r["final_distance_m"],
            "time_s": r["time_s"], "travelled_m": r["travelled_m"], "closest_person_m": r["closest_person_m"],
            "abort_reason": r["abort_reason"], "trace": r["trace"], "step_s": r["step_s"], "safety_stop_s": r["safety_stop_s"],
            "junctions": r["junctions"], "frame_log_rows": len(r["frame_log"]), "truth_rows": len(r["truth_rows"]),
            "hud_rows": len(r["hud_log"])}


def all_cases() -> dict:
    return {name: compact(make()) for name, make in CASES.items()}


if __name__ == "__main__":
    json.dump({"commit": "808f028", "cases": all_cases()}, sys.stdout, indent=1, sort_keys=True)
    sys.stdout.write("\n")
