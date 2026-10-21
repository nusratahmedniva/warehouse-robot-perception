"""Task 1 map (declared design change 2026-10-21): checkpoints on the roadmap's straight line, the same rule as the
Unity trial runner (Task1Route.cs, pinned to the same positions in Task1RouteTests.cs). Pure Python, no Unity."""

import copy
import math
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import hri_control as hc  # noqa: E402
import hri_sim as hs  # noqa: E402
import task_route as tr  # noqa: E402

ROAD = hc.load_json("configs/roadmap.json")
ROUTE = hc.load_json("configs/task1_route.json")
UNITY_TESTS = (ROOT.parent / "unity" / "Robotics-Warehouse" / "WarehouseProjectURP" / "Assets" / "WarehouseRobot" / "HRI"
               / "Tests" / "Task1RouteTests.cs")

# Default (3 checkpoints): the stops in driving order; C2 falls on J1 and is J1. The same values are in
# Task1RouteTests.cs.
EXPECTED_STOPS = [("C1", 6.25, -5.0, False), ("J1", 6.25, 0.0, True), ("C3", 6.25, 5.0, False)]
# One standing worker per stop (2026-10-21): 1.0 m ahead, 2.5 m right of the arrival direction, facing back (yaw 180).
EXPECTED_WORKERS = [("C1", 8.75, -4.0, 180.0), ("J1", 8.75, 1.0, 180.0), ("C3", 8.75, 6.0, 180.0)]


class StraightLineTests(unittest.TestCase):
    def test_line_from_the_map_ends_at_task1_goal(self):
        line = tr.straight_line(ROAD)
        self.assertEqual(line, ["A", "J1", "E1"])
        self.assertEqual(line[-1], ROAD["task1_goal"])   # evaluation's B: found from the map, not read by the robot

    def test_dead_end_is_an_error(self):
        road = copy.deepcopy(ROAD)
        del road["branches"]["J1"]["FORWARD"]
        with self.assertRaises(ValueError):
            tr.straight_line(road)


class CheckpointTests(unittest.TestCase):
    def test_default_positions(self):
        self.assertEqual(ROUTE["checkpoints"], 3)
        got = tr.checkpoints(ROAD, ROUTE["checkpoints"], ROUTE["merge_with_junction_m"])
        self.assertEqual([s[0] for s in got], [s[0] for s in EXPECTED_STOPS])
        for (n, x, z, e), (n2, x2, z2, e2) in zip(got, EXPECTED_STOPS):
            self.assertAlmostEqual(x, x2, places=6, msg=n)
            self.assertAlmostEqual(z, z2, places=6, msg=n)
            self.assertEqual(e, e2, n)

    def test_zero_or_one_checkpoint_is_the_former_task1(self):
        for n in (0, 1):
            self.assertEqual([s[0] for s in tr.checkpoints(ROAD, n, 0.5)], ["J1"])

    def test_other_counts_are_deterministic(self):
        self.assertEqual([s[0] for s in tr.checkpoints(ROAD, 2, 0.5)], ["C1", "J1", "C2"])
        self.assertEqual([s[0] for s in tr.checkpoints(ROAD, 4, 0.5)], ["C1", "C2", "J1", "C3", "C4"])
        self.assertEqual(tr.checkpoints(ROAD, 4, 0.5), tr.checkpoints(ROAD, 4, 0.5))

    def test_negative_count_refused(self):
        with self.assertRaises(ValueError):
            tr.checkpoints(ROAD, -1, 0.5)


class MapTests(unittest.TestCase):
    def setUp(self):
        self.m, self.route, self.files = tr.map_for_task("Task1", hc.load_json)

    def test_route_ids(self):
        self.assertEqual(self.route, "Task1:C1,J1,C3")
        self.assertEqual(tr.map_for_task("Task2", hc.load_json)[1], "Task2")
        self.assertEqual(self.files, ["configs/roadmap.json", "configs/task1_route.json"])
        with self.assertRaises(ValueError):
            tr.map_for_task("Task3", hc.load_json)

    def test_task2_map_is_the_roadmap_unchanged(self):
        self.assertEqual(tr.map_for_task("Task2", hc.load_json)[0], ROAD)

    def test_chain_and_branches(self):
        b = self.m["branches"]
        self.assertEqual(b["A"], {"FORWARD": "C1"})
        self.assertEqual(b["C1"], {"FORWARD": "J1"})
        self.assertEqual(b["J1"], {"FORWARD": "C3", "RIGHT": "E2", "LEFT": "J2"})   # J1 keeps LEFT and RIGHT
        self.assertEqual(b["C3"], {"FORWARD": "E1"})
        self.assertEqual(b["J2"], ROAD["branches"]["J2"])
        self.assertEqual(self.m["nodes"]["J1"]["arrive_from"], "C1")
        self.assertEqual(self.m["nodes"]["C3"]["arrive_from"], "J1")

    def test_labels_match_geometry_and_roadmap_not_modified(self):
        self.assertEqual(hc.Roadmap(self.m).check_labels(), [])
        self.assertEqual(ROAD, hc.load_json("configs/roadmap.json"))
        self.assertNotIn("C1", ROAD["nodes"])

    def test_one_worker_per_stop_pinned(self):
        self.assertEqual(tr.task1_worker_stands(ROAD, ROUTE), EXPECTED_WORKERS)
        self.assertEqual([w[0] for w in EXPECTED_WORKERS], self.m["task1_stops"])
        self.assertNotIn("workers", self.m)                     # scenario data never enters the controller's map

    def test_own_worker_is_clearly_the_nearest_at_every_stop(self):
        """The frozen scan approaches the nearest person: at each stop its own worker must win by a wide margin."""
        stands = tr.task1_worker_stands(ROAD, ROUTE)
        for stop, sx, sz, _ in tr.checkpoints(ROAD, 3, 0.5):
            d = sorted((math.hypot(wx - sx, wz - sz), w) for w, wx, wz, _ in stands)
            self.assertEqual(d[0][1], stop)
            self.assertAlmostEqual(d[0][0], 2.693, places=3)
            self.assertGreater(d[1][0] - d[0][0], 2.0, stop)            # 4.72 m against 2.69 m

    def test_workers_clear_of_the_straight_path(self):
        corridor = hc.load_json("configs/hri_control.json")["safety"]["corridor_half_width_m"]
        for _, wx, _, _ in tr.task1_worker_stands(ROAD, ROUTE):
            self.assertGreaterEqual(abs(wx - 6.25), 2.5)
            self.assertGreater(abs(wx - 6.25), 3 * corridor)

    def test_task2_stand_rule_unchanged(self):
        self.assertEqual(hc.Roadmap(ROAD).stand("J1")[:2], (8.75, 2.5))

    def test_every_stop_leads_to_b_by_forward(self):
        r = hc.Roadmap(self.m)
        for s in self.m["task1_stops"]:
            self.assertEqual(r.command_toward(s, ROAD["task1_goal"]), "FORWARD", s)

    def test_simulated_task1_asks_at_every_stop(self):
        stands = tr.task1_worker_stands(ROAD, ROUTE)
        for seed, kw in ((1, {}), (2, {"p_detect": 0.84, "distance_sigma_m": 0.2, "bearing_sigma_deg": 2.0})):
            c = hc.Controller(hc.load_json("configs/hri_control.json"), hc.Roadmap(self.m))
            out = hs.Simulator(c, hs.SimConfig(**kw), seed=seed).run(ROAD["task1_goal"], workers=stands)
            self.assertEqual(out["outcome"], "SUCCESS", out)
            self.assertEqual([(j["junction"], j["shown"], j["read"], j["asks"]) for j in out["junctions"]],
                             [(s, "FORWARD", "FORWARD", 1) for s in ("C1", "J1", "C3")])
            for j, (stop, wx, wz, _) in zip(out["junctions"], stands):   # it approached that stop's own worker
                self.assertLess(math.hypot(j["person_x"] - wx, j["person_z"] - wz), 0.5, (seed, stop))
            self.assertGreater(out["closest_person_m"], 1.5)


class UnityPinnedTests(unittest.TestCase):
    def test_unity_tests_pin_the_same_stops(self):
        src = UNITY_TESTS.read_text(encoding="utf-8")
        found = re.findall(r'\("(\w+)", ([-\d.]+)f, ([-\d.]+)f, (true|false)\)', src)
        self.assertEqual([(n, float(x), float(z), e == "true") for n, x, z, e in found], EXPECTED_STOPS)

    def test_unity_tests_pin_the_same_workers(self):
        src = UNITY_TESTS.read_text(encoding="utf-8")
        found = re.findall(r'\("(\w+)", ([-\d.]+)f, ([-\d.]+)f, ([-\d.]+)f\)', src)
        self.assertEqual([(n, float(x), float(z), float(y)) for n, x, z, y in found], EXPECTED_WORKERS)


if __name__ == "__main__":
    unittest.main()
