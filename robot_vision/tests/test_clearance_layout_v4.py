"""Nusrat's clearance layout in the simulator (AUDIT.md 16.20, 2026-11-17).

What is pinned: the slots of scenarios 1 to 3 are her clearance layout and A4/B4 have two workers at J1; every worker of every scenario, seed and node is
within 6.5 m of its node and has it as the nearest node (largest distance reported: 6.40 m, A3 J1 worker 3); no worker is within 1.0 m of any segment the
robot can drive (an independent model, layout_check_v4.py) and every ask position is within 5.5 m of its node, at her model's re-ask shift of 0.4 m.
Known findings that are pinned as facts and NOT fixed (AUDIT.md 16.20.1): with the shift the v4 controller really uses (0.8 m) A3's third worker at J1 is
0.74 m from a drivable segment and the re-ask point is 5.53 m from J1; the random layout (A4, B4) has no clearance rule in the simulator."""

import copy
import json
import math
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import hri_control as hc  # noqa: E402
import hri_control_v4 as hv  # noqa: E402
import hri_sim_v4 as sv  # noqa: E402
import layout_check_v4 as lc  # noqa: E402

CLEARANCE_SLOTS = [{"before_m": 3.5, "right_m": -2.5}, {"before_m": -4.5, "right_m": 3.5}, {"before_m": -5.0, "right_m": -4.0}]   # ed4e000
OLD_SLOTS = [{"before_m": 3.0, "right_m": -2.0}, {"before_m": 5.5, "right_m": 2.0}, {"before_m": 6.0, "right_m": -2.0}]
UNITY_CFG = ROOT.parent / "unity/Robotics-Warehouse/WarehouseProjectURP/Assets/WarehouseRobot/Scenario/Config/experiments_ab_unity.json"


class Model(unittest.TestCase):
    def test_ask_position_is_two_metres_from_the_worker_toward_where_the_robot_comes_from(self):
        a = lc.ask_position((0.0, 5.0), (0.0, 0.0))
        self.assertAlmostEqual(a[0], 0.0)
        self.assertAlmostEqual(a[1], 3.0)

    def test_reask_point_is_to_the_robots_right_and_back_on_the_circle(self):
        w, a = (0.0, 5.0), (0.0, 3.0)                                          # the robot faces north (+z): its right is +x
        r = lc.reask_position(w, a, shift=0.4)
        self.assertGreater(r[0], 0.0)
        self.assertAlmostEqual(math.dist(r, w), 2.0)
        self.assertEqual(lc.reask_position(w, a, shift=0.0), a)

    def test_the_python_controller_moves_the_same_way(self):
        """The model's re-ask point equals the approach point of hri_control._reposition for a robot standing at the ask position (the geometry in two places)."""
        for worker, robot in (((3.0, 7.0), (3.0, 5.0)), ((-5.0, 2.0), (-3.0, 2.0)), ((9.75, 4.5), (8.0, 3.5))):
            for shift in (0.4, 0.8):
                c = hv.make_controller_v4()
                c.g = {**c.g, "reask_shift_m": shift}
                c.person = worker
                ask = lc.ask_position(worker, robot)                              # the robot stands on the 2.0 m circle toward where it came from
                c._reposition(hc.TickInput(time_s=0.0, x=ask[0], z=ask[1], yaw_deg=0.0), 0.0, hc.Command())
                want = lc.reask_position(worker, ask, shift=shift)
                self.assertAlmostEqual(c.approach_point[0], want[0], places=6)
                self.assertAlmostEqual(c.approach_point[1], want[1], places=6)

    def test_segments_of_two_workers_include_every_order_the_tie_return_and_the_branches(self):
        road = hc.Roadmap(hc.load_json("configs/v4/roadmap.json"))
        workers = [(3.75, -3.5), (9.75, 4.5)]
        segs, asks = lc.drivable_segments(road, "J1", workers)
        labels = [s[4] for s in segs]
        self.assertEqual(sum("(again)" in x for x in labels), 2)                 # the return to the first worker of each of the two orders
        self.assertTrue(any(x.startswith("J1 to the ask position of worker 1") for x in labels))
        self.assertTrue(any(x.startswith("J1 to the ask position of worker 2") for x in labels))
        self.assertTrue(any("to J2 (LEFT)" in x for x in labels) and any("to J3 (RIGHT)" in x for x in labels))
        self.assertEqual(len(segs), 2 * 3 + len(asks) * len(road.branches["J1"]))


class TheLayout(unittest.TestCase):
    def test_slots_and_people_are_nusrats_clearance_layout(self):
        scen = sv.load_scenarios()["scenarios"]
        for k in ("1", "2", "3"):
            self.assertEqual(scen[k]["layout"]["junction_slots"], CLEARANCE_SLOTS, k)
        self.assertEqual(scen["3"]["layout"]["people_by_node"], {"J1": 3})
        self.assertNotIn("people_by_node", scen["4"]["layout"])                  # A4 and B4: two at J1
        self.assertEqual(scen["4"]["layout"]["kind"], "random")

    def test_the_start_slots_are_unchanged(self):
        scen = sv.load_scenarios()["scenarios"]
        for k in ("1", "2", "3"):
            self.assertEqual(scen[k]["layout"]["start_slots"], [{"before_m": 3.0, "right_m": -2.0}, {"before_m": 3.0, "right_m": 4.0}, {"before_m": 6.0, "right_m": -2.0}])

    def test_unitys_values_agree_whenever_the_file_carries_them(self):
        u = json.loads(UNITY_CFG.read_text(encoding="utf-8"))
        if "clearance_layout" not in u:
            self.skipTest("main's unity/ does not carry clearance_layout yet (PR #40); the pins in test_lie_detection_v4.MatchesUnity use her quoted values")
        self.assertEqual(u["clearance_layout"]["junction_slots"], CLEARANCE_SLOTS)
        self.assertEqual((u["path_clearance_m"], u["ask_standoff_m"], u["reask_shift_m"]), (lc.CLEARANCE_M, lc.UNITY_STANDOFF_M, lc.UNITY_RESHIFT_M))
        self.assertAlmostEqual(u["answer_zone_radius_m"] - u["answer_zone_margin_m"], lc.ASK_ZONE_M)

    def test_the_simulator_places_the_workers_at_her_positions(self):
        sc = sv.scenario_ab("A3", 1)
        plan = sc["sim"].plan_workers()
        j1 = [tuple(round(c, 6) for c in q) for q in plan["J1"]]
        self.assertEqual(j1, [(3.75, -3.5), (9.75, 4.5), (2.25, 5.0)])
        self.assertEqual(len(plan["J2"]), 2)
        self.assertEqual(len(sv.scenario_ab("A4", 1)["sim"].plan_workers()["J1"]), 2)


class Survey(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.res = lc.survey(shifts=(0.4, 0.8))

    def test_every_worker_belongs_to_its_node_and_the_largest_distance(self):
        for name, r in self.res.items():
            self.assertEqual(r["not_belonging"], [], name)
            self.assertLess(r["max_distance_to_node_m"], 6.5, name)
        self.assertEqual(self.res["A1"]["workers"], 40)
        self.assertEqual(self.res["A2"]["workers"], 80)
        self.assertEqual(self.res["A3"]["workers"], 220)                          # 20 seeds x (A + J1 to J4: 2 + 3 + 2 + 2 + 2 = 11)
        self.assertEqual(self.res["A4"]["workers"], 200)                          # J1 has two workers now: 20 x 10
        self.assertAlmostEqual(self.res["A1"]["max_distance_to_node_m"], 5.0, places=3)
        self.assertAlmostEqual(self.res["A2"]["max_distance_to_node_m"], math.hypot(4.5, 3.5), places=3)    # 5.70: slot 2 at B
        a3 = self.res["A3"]["max_distance_where"]
        self.assertAlmostEqual(a3["distance_m"], math.hypot(5.0, 4.0), places=3)                              # 6.40: slot 3 at J1
        self.assertEqual((a3["node"], a3["worker"]), ("J1", 3))
        self.assertLess(self.res["A4"]["max_distance_to_node_m"], math.hypot(3.0, 3.0) + 1e-9)               # the 6 m square

    def test_no_worker_within_1_m_of_a_drivable_segment_at_her_reask_shift(self):
        for name in ("A1", "A2", "A3"):
            b = self.res[name]["by_shift"]["0.4"]
            self.assertEqual(b["plans_violating"], 0, name)
            self.assertGreaterEqual(b["min_clearance_m"], lc.CLEARANCE_M - lc.EPS, name)
            self.assertLessEqual(b["max_ask_distance_m"], lc.ASK_ZONE_M + lc.EPS, name)
        a3 = self.res["A3"]["by_shift"]["0.4"]
        self.assertAlmostEqual(a3["max_ask_distance_m"], 5.19, places=2)                    # her figure: the largest own-ask distance 5.19 m
        self.assertAlmostEqual(a3["min_clearance_m"], 1.01, places=2)

    def test_the_old_slots_are_caught_by_the_same_check(self):
        scen = copy.deepcopy(sv.load_scenarios())
        for k in ("1", "2", "3"):
            scen["scenarios"][k]["layout"]["junction_slots"] = copy.deepcopy(OLD_SLOTS)
        old = lc.survey(("A3",), range(1, 21), (0.4,), scen=scen)["A3"]["by_shift"]["0.4"]
        self.assertEqual(old["plans_violating"], 20)
        self.assertLess(old["min_clearance_m"], 0.35)                                       # her A3 run 2: 0.31 m from the diagnosis trail
        self.assertAlmostEqual(old["max_ask_distance_m"], 5.40, places=2)                  # her figure for the live slots at J1

    # ---- known findings, pinned as facts (AUDIT.md 16.20.1): reported, not fixed
    def test_known_finding_the_v4_controller_re_asks_with_0_8_not_0_4(self):
        self.assertEqual(hv.make_controller_v4().g["reask_shift_m"], 0.8)
        self.assertEqual(hc.load_json("configs/hri_control.json")["dialog"]["reask_shift_m"], 0.4)       # the v3 value her model copies

    def test_known_finding_a3_j1_at_the_v4_shift(self):
        b = self.res["A3"]["by_shift"]["0.8"]
        self.assertEqual(b["plans_violating"], 20)
        self.assertAlmostEqual(b["min_clearance_m"], 0.74, places=2)                        # worker 3 of J1 to the segment from its re-ask point to J2 (LEFT)
        self.assertAlmostEqual(b["max_ask_distance_m"], 5.53, places=2)                     # above her 5.5 m rule, below the 6.0 m answer zone
        self.assertLess(b["max_ask_distance_m"], 6.0)
        for name in ("A1", "A2"):
            self.assertEqual(self.res[name]["by_shift"]["0.8"]["plans_violating"], 0, name)

    def test_known_finding_the_random_layout_has_no_clearance_rule(self):
        for s in ("0.4", "0.8"):
            self.assertEqual(self.res["A4"]["by_shift"][s]["plans_violating"], 20, s)
            self.assertLess(self.res["A4"]["by_shift"][s]["min_clearance_m"], 0.1, s)
        own = 0
        for seed in range(1, 21):
            sc = sv.scenario_ab("A4", seed)
            for node, pts in sc["sim"].plan_workers().items():
                own += lc.evaluate_plan(sc["road"], sc["spec"].physical_map, {node: pts})["min_clearance_m"] < lc.CLEARANCE_M - lc.EPS
        self.assertEqual(own, 62)                                                           # of 100 asking nodes


if __name__ == "__main__":
    unittest.main()
