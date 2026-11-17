"""Nusrat's layout in the simulator (AUDIT.md 16.20, 16.21.2).

Since 16.21.2 the junction slots are layout (i) of her slot_table.csv (SHA-256 a180e358...ed39f; the re-search with the controller's 0.8 m re-ask shift): slot 1 3.0 m before and
2.0 m left, slot 2 2.5 m AHEAD and 4.0 m right, two workers at every node. Pinned: every worker of every scenario, seed and node is within 6.5 m of its node and has it as the
nearest node (largest distance 5.00 m, the start node's second slot); no worker is within 1.0 m of any segment the robot can drive and every ask position is within 5.5 m of its
node, at her earlier model's re-ask shift of 0.4 m AND at the 0.8 m the controller really uses (layout_check_v4.py, an independent distance check). The 16.20 layout (three slots,
three workers at J1 in A3) and the live slots before it are kept in analyse_a3_timeouts_v4 for the reproducible analyses; the 16.20 layout fails at 0.8 m (A3 J1: 0.74 m)."""

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
import analyse_a3_timeouts_v4 as a3  # noqa: E402
import layout_check_v4 as lc  # noqa: E402

CLEARANCE_SLOTS = [{"before_m": 3.0, "right_m": -2.0}, {"before_m": -2.5, "right_m": 4.0}]   # layout (i) of slot_table.csv, AUDIT.md 16.21.2
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
        workers = [(4.25, -3.0), (10.25, 2.5)]
        segs, asks = lc.drivable_segments(road, "J1", workers)
        labels = [s[4] for s in segs]
        self.assertEqual(sum("(again)" in x for x in labels), 2)                 # the return to the first worker of each of the two orders
        self.assertTrue(any(x.startswith("J1 to the ask position of worker 1") for x in labels))
        self.assertTrue(any(x.startswith("J1 to the ask position of worker 2") for x in labels))
        self.assertTrue(any("to J2 (LEFT)" in x for x in labels) and any("to J3 (RIGHT)" in x for x in labels))
        self.assertEqual(len(segs), 2 * 3 + len(asks) * len(road.branches["J1"]))


class TheLayout(unittest.TestCase):
    def test_slots_and_people_are_layout_i(self):
        scen = sv.load_scenarios()["scenarios"]
        for k in ("1", "2", "3"):
            self.assertEqual(scen[k]["layout"]["junction_slots"], CLEARANCE_SLOTS, k)
        for k in ("1", "2", "3", "4"):
            self.assertNotIn("people_by_node", scen[k]["layout"], k)              # two workers at every node, A3, B3, A4, B4 included
        self.assertEqual(scen["4"]["layout"]["kind"], "random")
        self.assertEqual(sv.load_scenarios()["placement_rule"]["reask_shift_m"], 0.8)

    def test_the_start_slots_are_unchanged(self):
        scen = sv.load_scenarios()["scenarios"]
        for k in ("1", "2", "3"):
            self.assertEqual(scen[k]["layout"]["start_slots"], [{"before_m": 3.0, "right_m": -2.0}, {"before_m": 3.0, "right_m": 4.0}, {"before_m": 6.0, "right_m": -2.0}])

    def test_unitys_values_agree_whenever_the_file_carries_them(self):
        u = json.loads(UNITY_CFG.read_text(encoding="utf-8"))
        if "clearance_layout" not in u:
            self.skipTest("main's unity/ does not carry clearance_layout yet (PR #40); the pins in test_lie_detection_v4.MatchesUnity use the values of slot_table.csv")
        self.assertEqual(u["clearance_layout"]["junction_slots"][:2], CLEARANCE_SLOTS)
        pr = sv.load_scenarios()["placement_rule"]
        self.assertEqual((u["path_clearance_m"], u["ask_standoff_m"], u["reask_shift_m"]), (pr["path_clearance_m"], pr["ask_standoff_m"], pr["reask_shift_m"]))
        self.assertAlmostEqual(u["answer_zone_radius_m"] - u["answer_zone_margin_m"], pr["ask_zone_m"])

    def test_the_simulator_places_the_workers_at_the_table_positions(self):
        for name in ("A3", "A4"):
            plan = sv.scenario_ab(name, 1)["sim"].plan_workers()
            self.assertTrue(all(len(pts) == 2 for pts in plan.values()), name)
        j1 = [tuple(round(c, 6) for c in q) for q in sv.scenario_ab("A3", 1)["sim"].plan_workers()["J1"]]
        self.assertEqual(j1, [(4.25, -3.0), (10.25, 2.5)])
        self.assertEqual([tuple(round(c, 6) for c in q) for q in sv.scenario_ab("A3", 1)["sim"].plan_workers()["J4"]], [(-15.75, -2.0), (-21.25, 4.0)])


class Survey(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.res = lc.survey(shifts=(0.4, 0.8))

    def test_every_worker_belongs_to_its_node_and_the_largest_distance(self):
        for name, r in self.res.items():
            self.assertEqual(r["not_belonging"], [], name)
            self.assertLess(r["max_distance_to_node_m"], 6.5, name)
        self.assertEqual([self.res[n]["workers"] for n in ("A1", "A2", "A3", "A4")], [40, 80, 200, 200])       # 20 seeds x 2 workers x (1, 2, 5, 5) nodes
        for n in ("A1", "A2", "A3"):
            w = self.res[n]["max_distance_where"]
            self.assertAlmostEqual(w["distance_m"], 5.0, places=3)                                          # the start node's second slot (3.0 m back, 4.0 m right)
            self.assertEqual((w["node"], w["worker"]), ("A", 2))
        self.assertLess(self.res["A4"]["max_distance_to_node_m"], math.hypot(3.0, 3.0) + 1e-9)               # the 6 m square

    def test_no_worker_within_1_m_of_a_drivable_segment_at_either_reask_shift(self):
        for name in ("A1", "A2", "A3", "A4"):
            for shift in ("0.4", "0.8"):
                b = self.res[name]["by_shift"][shift]
                self.assertEqual(b["plans_violating"], 0, (name, shift))
                self.assertGreaterEqual(b["min_clearance_m"], lc.CLEARANCE_M - lc.EPS, (name, shift))
                self.assertLessEqual(b["max_ask_distance_m"], lc.ASK_ZONE_M + lc.EPS, (name, shift))
        a3 = self.res["A3"]["by_shift"]["0.8"]
        self.assertAlmostEqual(a3["min_clearance_m"], 1.173, places=3)                      # the table's smallest clearance (A3 J1 slot 2)
        self.assertAlmostEqual(a3["max_ask_distance_m"], 4.062, places=3)                   # the table's largest own ask distance (A)

    def test_the_16_20_layout_is_caught_at_the_v4_shift_and_the_old_slots_at_both(self):
        for layout, shift, violating, low in (("clearance16", "0.8", 20, 0.8), ("old", "0.4", 20, 0.35)):
            res = lc.survey(("A3",), range(1, 21), (0.4, 0.8), scen=a3.scenarios(layout))["A3"]["by_shift"][shift]
            self.assertEqual(res["plans_violating"], violating, layout)
            self.assertLess(res["min_clearance_m"], low, layout)
        c16 = lc.survey(("A3",), range(1, 21), (0.4, 0.8), scen=a3.scenarios("clearance16"))["A3"]["by_shift"]
        self.assertAlmostEqual(c16["0.8"]["min_clearance_m"], 0.74, places=2)               # 16.20.1
        self.assertAlmostEqual(c16["0.8"]["max_ask_distance_m"], 5.53, places=2)
        self.assertEqual(c16["0.4"]["plans_violating"], 0)                                  # her model's own shift: clean, as she wrote

    def test_known_finding_the_v4_controller_re_asks_with_0_8_not_0_4(self):
        self.assertEqual(hv.make_controller_v4().g["reask_shift_m"], 0.8)
        self.assertEqual(hc.load_json("configs/hri_control.json")["dialog"]["reask_shift_m"], 0.4)       # the v3 value her model copies

    def test_the_random_layout_keeps_the_clearance_at_both_shifts_node_by_node(self):
        own = 0
        for seed in range(1, 21):
            sc = sv.scenario_ab("A4", seed)
            for node, pts in sc["sim"].plan_workers().items():
                for shift in (0.4, 0.8):
                    own += lc.evaluate_plan(sc["road"], sc["spec"].physical_map, {node: pts}, shift=shift)["min_clearance_m"] < lc.CLEARANCE_M - lc.EPS
        self.assertEqual(own, 0)


if __name__ == "__main__":
    unittest.main()
