"""analyse_a3_timeouts_v4.py (AUDIT.md 16.20.3): the analysis of the A3 detection-on timeouts. The tool only observes (hooks on `step`; the counterfactual sets the
return speed on one run); these tests pin that it changes nothing and the numbers the AUDIT quotes."""

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import analyse_a3_timeouts_v4 as a3  # noqa: E402
import hri_sim_v4 as sv  # noqa: E402


class Setup(unittest.TestCase):
    def test_the_old_layout_is_the_baseline_of_16_20_1(self):
        old = a3.scenarios("old")["scenarios"]
        for k in ("1", "2", "3"):
            self.assertEqual(old[k]["layout"]["junction_slots"], a3.OLD_SLOTS)
        self.assertEqual(old["4"]["layout"]["people_by_node"], {"J1": 3})
        self.assertEqual(a3.scenarios("clearance")["scenarios"], sv.load_scenarios()["scenarios"])

    def test_state_times_add_up_to_the_run(self):
        r = {"trace": ["0.00:scan", "1.50:approach", "4.00:ask", "5.00:done"], "time_s": 7.0}
        self.assertEqual(a3.state_times(r), {"scan": 1.5, "approach": 2.5, "ask": 1.0, "done": 2.0})


class OneRun(unittest.TestCase):
    """The E5 run of A3 (seed 4; seeds 6, 8, 12, 14, 17 are the same run), old slots."""

    @classmethod
    def setUpClass(cls):
        cls.scen = a3.scenarios("old")
        cls.on = a3.run_one(4, cls.scen, True, 270.0)
        cls.long = a3.run_one(4, cls.scen, True, 600.0)
        cls.off = a3.run_one(4, cls.scen, False, 270.0)

    def test_the_observing_hook_changes_nothing(self):
        def drop_key(c):                                                    # only what the tool does to the live config, without the observing wrapper
            c.v4["dialog"].pop("return_speed_mps", None)
        plain = sv.scenario_ab("A3", 4, sv.DETECTION_ON, scen=self.scen, hook=drop_key, sim_cfg=sv.SimConfig(timeout_s=270.0))
        r = plain["sim"].run(plain["goal"])
        self.assertEqual((r["outcome"], r["time_s"], r["safety_stop_s"]), (self.on["outcome"], self.on["time_s"], self.on["safety_stop_s"]))

    def test_the_live_config_now_is_the_counterfactual(self):                 # AUDIT.md 16.20.5: dialog.return_speed_mps 0.8 in the control files
        live = sv.scenario_ab("A3", 4, sv.DETECTION_ON, scen=self.scen, sim_cfg=sv.SimConfig(timeout_s=270.0))
        r = live["sim"].run(live["goal"])
        cf = a3.run_one(4, self.scen, True, 270.0, cruise_return=True)
        self.assertEqual((r["outcome"], r["time_s"]), ("SUCCESS", 254.7))
        self.assertEqual((r["outcome"], r["time_s"]), (cf["outcome"], cf["time_s"]))

    def test_the_timeout_is_a_budget_effect_of_the_returns(self):
        self.assertEqual((self.on["_goal"], self.on["outcome"], self.on["failure_reason"], self.on["time_s"]), ("E5", "FAILURE", "timeout", 270.0))
        self.assertEqual((self.long["outcome"], self.long["time_s"]), ("SUCCESS", 270.3))          # 0.3 s over the limit
        self.assertEqual((self.off["outcome"], self.off["time_s"]), ("SUCCESS", 230.3))
        v = a3.visits(self.on)
        self.assertEqual([x["node"] for x in v], ["A", "J1", "J2", "J4"])
        self.assertEqual([x["return_s"] for x in v], [10.1, 14.2, 12.2, 12.2])
        self.assertAlmostEqual(sum(x["return_s"] for x in v), 48.7, places=1)
        self.assertTrue(all(0.29 <= x["return_speed_mps"] <= 0.33 for x in v))
        self.assertEqual([x["people_asked"] for x in v], [2, 2, 2, 2])
        self.assertEqual(len(self.on["_safety"]), 1)
        self.assertEqual(self.on["_safety"][0]["reason"], "perception stale")
        self.assertEqual(self.off["_safety"], [])
        self.assertAlmostEqual(a3.state_times(self.on)["execute"] - a3.state_times(self.off)["execute"], 46.0, delta=0.5)

    def test_the_counterfactual_cruise_return_fits_the_old_layout_but_not_the_clearance_layout(self):
        cf = a3.run_one(4, self.scen, True, 270.0, cruise_return=True)
        self.assertEqual(cf["outcome"], "SUCCESS")
        self.assertLess(cf["time_s"], 260.0)
        self.assertLess(max(x["return_s"] for x in a3.visits(cf)), 10.0)
        self.assertEqual(cf["closest_person_m"], self.on["closest_person_m"])
        new = a3.run_one(4, a3.scenarios("clearance"), True, 600.0, cruise_return=True)
        self.assertEqual((new["outcome"], new["time_s"]), ("SUCCESS", 283.9))                   # still over 270 s


if __name__ == "__main__":
    unittest.main()
