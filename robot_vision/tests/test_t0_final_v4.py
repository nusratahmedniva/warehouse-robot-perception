"""The control files of the finals are T0 exactly, and the T0 numbers of AUDIT.md 16.26.8.1 are reproduced from them (AUDIT.md 16.26.9: checkpoints dropped, T0 kept).

The numbers are those of the final check of 16.26.8: simulator, fresh seeds 101 to 140, cap 900 s, all 16 rows, the readability model of 16.26.6 (configs/v4/experiments/point_readability.json), the
checkpoint workers of checkpoints_unity.json present in the scene and ignored (T0 with workers). Here every run is driven by the control file of its row (no detection override). The
per-seed outcomes of seeds 101 to 105 of all 16 rows and the 40-seed counts of B3 on and B4 on are pinned; the 40-seed success counts of all 16 rows are listed for the record."""

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import hri_control_v4 as hv  # noqa: E402
import hri_sim as hs  # noqa: E402
import hri_sim_v4 as sv  # noqa: E402

EXP = ROOT / "configs/v4/experiments"
CP = json.loads((EXP / "checkpoints_unity.json").read_text(encoding="utf-8"))
MODEL = json.loads((EXP / "point_readability.json").read_text(encoding="utf-8"))
FILES = {"on": {"A1": "control_lie_on_a1", "B1": "control_lie_on_a1", "A2": "control_lie_on_a2_right", "B2": "control_lie_on_a2_right",
                "A3": "control_lie_on", "A4": "control_lie_on", "B3": "control_lie_on", "B4": "control_lie_on"},
         "off": {"A1": "control_lie_off_a1", "B1": "control_lie_off_a1", "A2": "control_lie_off_a2_right", "B2": "control_lie_off_a2_right",
                 "A3": "control_lie_off", "A4": "control_lie_off", "B3": "control_lie_off", "B4": "control_lie_off"}}

# (seed, outcome, failure_reason, time_s) of seeds 101 to 105, from outputs/t3_v4_final_check_s101_140_20261120_011844/runs.json (variant T0)
FIRST5 = {
    "A1_off": [[101, "SUCCESS", "none", 70.05], [102, "SUCCESS", "none", 70.05], [103, "SUCCESS", "none", 70.05], [104, "SUCCESS", "none", 70.05], [105, "SUCCESS", "none", 70.05]],
    "A1_on": [[101, "SUCCESS", "none", 85.6], [102, "SUCCESS", "none", 85.6], [103, "SUCCESS", "none", 85.6], [104, "SUCCESS", "none", 85.6], [105, "SUCCESS", "none", 85.6]],
    "A2_off": [[101, "SUCCESS", "none", 91.8], [102, "SUCCESS", "none", 91.9], [103, "SUCCESS", "none", 91.8], [104, "SUCCESS", "none", 92.5], [105, "SUCCESS", "none", 92.1]],
    "A2_on": [[101, "SUCCESS", "none", 155.4], [102, "SUCCESS", "none", 155.6], [103, "SUCCESS", "none", 155.2], [104, "SUCCESS", "none", 155.8], [105, "SUCCESS", "none", 156.0]],
    "A3_off": [[101, "SUCCESS", "none", 92.75], [102, "SUCCESS", "none", 141.6], [103, "SUCCESS", "none", 129.35], [104, "SUCCESS", "none", 189.6], [105, "SUCCESS", "none", 92.75]],
    "A3_on": [[101, "SUCCESS", "none", 127.9], [102, "SUCCESS", "none", 221.1], [103, "SUCCESS", "none", 242.15], [104, "SUCCESS", "none", 265.0], [105, "SUCCESS", "none", 127.9]],
    "A4_off": [[101, "SUCCESS", "none", 91.5], [102, "SUCCESS", "none", 136.05], [103, "SUCCESS", "none", 126.7], [104, "FAILURE", "aborted", 141.55], [105, "SUCCESS", "none", 89.3]],
    "A4_on": [[101, "SUCCESS", "none", 123.25], [102, "SUCCESS", "none", 202.75], [103, "SUCCESS", "none", 179.15], [104, "SUCCESS", "none", 266.0], [105, "SUCCESS", "none", 114.3]],
    "B1_off": [[101, "SUCCESS", "none", 70.05], [102, "SUCCESS", "none", 70.05], [103, "SUCCESS", "none", 70.05], [104, "SUCCESS", "none", 70.05], [105, "SUCCESS", "none", 70.05]],
    "B1_on": [[101, "SUCCESS", "none", 98.45], [102, "SUCCESS", "none", 85.6], [103, "SUCCESS", "none", 85.6], [104, "SUCCESS", "none", 98.45], [105, "SUCCESS", "none", 85.6]],
    "B2_off": [[101, "SUCCESS", "none", 91.8], [102, "SUCCESS", "none", 91.9], [103, "SUCCESS", "none", 91.8], [104, "FAILURE", "aborted", 72.05], [105, "SUCCESS", "none", 92.1]],
    "B2_on": [[101, "SUCCESS", "none", 158.95], [102, "SUCCESS", "none", 147.95], [103, "SUCCESS", "none", 155.2], [104, "SUCCESS", "none", 171.15], [105, "SUCCESS", "none", 156.0]],
    "B3_off": [[101, "SUCCESS", "none", 92.75], [102, "FAILURE", "wrong_goal", 129.45], [103, "SUCCESS", "none", 129.35], [104, "FAILURE", "aborted", 110.15], [105, "SUCCESS", "none", 92.75]],
    "B3_on": [[101, "SUCCESS", "none", 140.8], [102, "FAILURE", "wrong_goal", 241.05], [103, "SUCCESS", "none", 241.05], [104, "FAILURE", "aborted", 234.15], [105, "SUCCESS", "none", 127.9]],
    "B4_off": [[101, "SUCCESS", "none", 91.5], [102, "FAILURE", "wrong_goal", 123.15], [103, "SUCCESS", "none", 126.7], [104, "FAILURE", "aborted", 77.7], [105, "SUCCESS", "none", 89.3]],
    "B4_on": [[101, "SUCCESS", "none", 135.4], [102, "FAILURE", "wrong_goal", 219.65], [103, "SUCCESS", "none", 187.65], [104, "FAILURE", "aborted", 142.55], [105, "SUCCESS", "none", 114.3]],
}
# successes of the 40 seeds of every row (the table of 16.26.8.1)
SUCCESSES_40 = {"A1_off": 40, "A1_on": 40, "A2_off": 40, "A2_on": 40, "A3_off": 40, "A3_on": 40, "A4_off": 30, "A4_on": 37, "B1_off": 32, "B1_on": 37, "B2_off": 27, "B2_on": 36, "B3_off": 21, "B3_on": 24, "B4_off": 17, "B4_on": 23}


def run(name, setting, seed):
    sc = sv.scenario_ab(name, seed, None, control_path=str(EXP / f"{FILES[setting][name]}.json"), checkpoints=CP, sim_cfg=hs.SimConfig(timeout_s=900.0),
                        gcfg=sv.GestureSimConfig(point_readability=MODEL))
    return sc["sim"].run(sc["goal"])


class T0Files(unittest.TestCase):
    def test_the_on_files_are_the_t0_detection_and_the_off_files_the_off_detection(self):
        for name in sorted({f for m in FILES.values() for f in m.values()}):
            ld = hv.make_controller_v4(str(EXP / f"{name}.json")).ld
            want = sv.DETECTION_ON if "_on" in name else sv.DETECTION_OFF
            self.assertEqual({k: ld[k] for k in want}, want, name)
            self.assertEqual((ld["checkpoint"], ld["next_junction_back"], ld["checkpoint_branches"], ld["checkpoint_s_m"]), (False, False, None, None), name)

    def test_the_t0_numbers_of_16_26_8_1_seeds_101_to_105_all_16_rows(self):
        self.assertEqual(len(FIRST5), 16)
        for key, rows in FIRST5.items():
            name, setting = key.split("_")
            for seed, outcome, reason, time_s in rows:
                r = run(name, setting, seed)
                self.assertEqual((r["outcome"], r["failure_reason"], r["time_s"]), (outcome, reason, time_s), (key, seed))
                self.assertEqual(r["v4"]["checkpoint"]["log"], [], (key, seed))                       # nobody is asked at a checkpoint

    def test_the_t0_counts_of_b3_on_and_b4_on_over_the_40_fresh_seeds(self):
        want = {"B3": (24, 9, 7), "B4": (23, 7, 10)}                                                  # successes, wrong goals, aborts; no timeouts
        for name, counts in want.items():
            rs = [run(name, "on", s) for s in range(101, 141)]
            self.assertEqual((sum(r["outcome"] == "SUCCESS" for r in rs), sum(r["failure_reason"] == "wrong_goal" for r in rs), sum(r["failure_reason"] == "aborted" for r in rs)), counts, name)
            self.assertEqual(sum(r["failure_reason"] == "timeout" for r in rs), 0, name)
            self.assertEqual(sum(r["outcome"] == "SUCCESS" for r in rs), SUCCESSES_40[f"{name}_on"], name)

    def test_the_table_of_the_record(self):
        self.assertEqual(len(SUCCESSES_40), 16)
        self.assertEqual((SUCCESSES_40["B3_on"], SUCCESSES_40["B4_on"]), (24, 23))
        self.assertEqual([SUCCESSES_40[f"{n}_on"] for n in ("A1", "A2", "A3", "A4")], [40, 40, 40, 37])


if __name__ == "__main__":
    unittest.main()
