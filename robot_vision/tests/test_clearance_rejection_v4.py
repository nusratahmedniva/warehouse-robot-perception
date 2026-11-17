"""The random layout adopts Unity's clearance rejection (AUDIT.md 16.20.2, 2026-11-17).

Unity's ExperimentPlanAB.ClearanceProblem (read from origin/nusrat/v4-step5-dev) redraws the workers of a node unless every ask position is within 5.5 m of the
node and no worker is within 1.0 m of a road or of a segment the robot can drive (node to ask positions in every order incl. the tie return, ask positions and re-ask
points to the next node of every branch). hri_sim_v4.clearance_problem / place_random(clearance=...) do the same in the simulator; the values (1.0, 5.5, 2.0, 0.4) are
hers and live in scenarios_ab.json placement_rule."""

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import hri_control as hc  # noqa: E402
import hri_sim_v4 as sv  # noqa: E402
import layout_check_v4 as lc  # noqa: E402

RULE = {"path_clearance_m": 1.0, "ask_zone_m": 5.5, "ask_standoff_m": 2.0, "reask_shift_m": 0.4}
UNITY_CFG = ROOT.parent / "unity/Robotics-Warehouse/WarehouseProjectURP/Assets/WarehouseRobot/Scenario/Config/experiments_ab_unity.json"


def road():
    return hc.Roadmap(hc.load_json("configs/v4/roadmap.json"))


class Config(unittest.TestCase):
    def test_the_values_are_hers_and_in_the_placement_rule(self):
        pr = sv.load_scenarios()["placement_rule"]
        self.assertEqual({k: pr[k] for k in RULE}, RULE)
        self.assertEqual(pr["min_worker_separation_m"], 3.0)                 # the earlier rule is unchanged
        self.assertIn("placement_rule.clearance", sv.load_scenarios()["why"])
        self.assertIn("DECIDED 2026-11-17", sv.load_scenarios()["why"]["placement_rule.clearance"])

    def test_they_equal_unitys_whenever_the_file_carries_them(self):
        u = json.loads(UNITY_CFG.read_text(encoding="utf-8"))
        if "path_clearance_m" not in u:
            self.skipTest("main's unity/ does not carry the clearance values yet (PR #40); the values were read from origin/nusrat/v4-step5-dev")
        self.assertEqual((u["path_clearance_m"], u["answer_zone_radius_m"] - u["answer_zone_margin_m"], u["ask_standoff_m"], u["reask_shift_m"]),
                         (RULE["path_clearance_m"], RULE["ask_zone_m"], RULE["ask_standoff_m"], RULE["reask_shift_m"]))

    def test_scenario_ab_passes_the_values_to_the_spec(self):
        self.assertEqual({k: sv.scenario_ab("A4", 1)["spec"].placement_rule[k] for k in RULE}, RULE)

    def test_the_geometry_lives_in_one_place(self):
        self.assertIs(lc.drivable_segments, sv.drivable_segments)
        self.assertIs(lc.ask_position, sv.ask_position)
        self.assertIs(lc.reask_position, sv.reask_position)


class Problem(unittest.TestCase):
    """clearance_problem on constructed cases (J1 at (6.25, 0); the road to E1 runs north, J2 to the west, J3 to the east)."""

    def test_her_clearance_slots_at_j1_are_clean(self):
        pts = sv.place_slots(road(), "J1", 3, [{"before_m": 3.5, "right_m": -2.5}, {"before_m": -4.5, "right_m": 3.5}, {"before_m": -5.0, "right_m": -4.0}])
        self.assertIsNone(sv.clearance_problem(road(), "J1", pts, {}, None, RULE))

    def test_a_worker_on_the_drive_to_another_worker_is_rejected(self):
        r = road()
        first = (3.75, -3.5)
        ask1 = sv.ask_position(first, r.pos("J1"))
        mid = ((r.pos("J1")[0] + ask1[0]) / 2, (r.pos("J1")[1] + ask1[1]) / 2)          # standing on the line from the node to the first worker's ask position
        msg = sv.clearance_problem(r, "J1", [first, mid], {}, None, RULE)
        self.assertIsNotNone(msg)
        self.assertIn("(< 1.0)", msg)                                                    # some rule names the clearance; the first one found is reported
        self.assertIsNone(sv.clearance_problem(r, "J1", [first], {}, None, RULE))        # the first worker alone is clean: the second one breaks it

    def test_a_worker_beside_a_road_is_rejected(self):
        msg = sv.clearance_problem(road(), "J1", [(6.75, 3.0)], {}, None, RULE)          # 0.5 m beside the road J1 to E1, its ask position inside the zone
        self.assertIn("from a road", msg)

    def test_an_ask_position_beyond_the_zone_is_rejected(self):
        msg = sv.clearance_problem(road(), "J1", [(1.0, -6.0)], {}, None, RULE)         # 8.1 m from J1: its ask position is 6.2 m away
        self.assertIn("ask position", msg)
        self.assertIn("5.50", msg)

    def test_a_worker_of_an_earlier_node_next_to_this_nodes_drive_is_rejected(self):
        r = road()
        ours = [(3.75, -3.5)]                                                # J1: the drive from J1 to the ask position of this worker
        e = sv.ask_position(ours[0], r.pos("J1"))
        near = (e[0] + 0.3, e[1] + 0.3)                                      # a worker of J2 standing right next to it
        self.assertIn("a worker of J2", sv.clearance_problem(r, "J1", ours, {"J2": [near]}, None, RULE))

    def test_this_nodes_worker_next_to_an_earlier_nodes_drive_is_rejected(self):
        r = road()
        theirs = [(-9.0, 3.0)]                                               # a worker of J2
        e = sv.ask_position(theirs[0], r.pos("J2"))
        mine = (e[0] + 0.3, e[1] - 0.3)
        self.assertIsNotNone(sv.clearance_problem(r, "J1", [mine], {"J2": theirs}, None, RULE))

    def test_the_physical_map_roads_count(self):
        run = hc.Roadmap({"start": "A", "nodes": {"A": {"x": 0.0, "z": 0.0, "kind": "start"}, "B": {"x": 0.0, "z": 20.0, "kind": "endpoint"}}, "branches": {"A": {"FORWARD": "B"}}})
        phys = hc.Roadmap({"start": "P", "nodes": {"P": {"x": 3.5, "z": -5.0, "kind": "start"}, "Q": {"x": 3.5, "z": 5.0, "kind": "endpoint"}}, "branches": {"P": {"FORWARD": "Q"}}})
        worker = (3.0, 0.0)                                                              # 3.0 m from the run map's road, 0.5 m from the physical road
        self.assertIsNone(sv.clearance_problem(run, "A", [worker], {}, None, RULE))
        self.assertIn("from a road", sv.clearance_problem(run, "A", [worker], {}, phys, RULE))

    def test_a_zero_rule_never_rejects(self):
        zero = {"path_clearance_m": 0.0, "ask_zone_m": 0.0, "ask_standoff_m": 2.0, "reask_shift_m": 0.4}
        self.assertIsNone(sv.clearance_problem(road(), "J1", [(6.75, 9.0), (6.8, 9.2)], {}, None, zero))


class Placement(unittest.TestCase):
    def setUp(self):
        self.road = road()

    def args(self, node="J1", n=2, seed=3, **kw):
        a = dict(road=self.road, node=node, n=n, half_size_m=3.0, min_road_m=1.0, min_sep_m=3.0, seed=seed, min_turning_m=3.0, nearer_margin_m=0.25,
                 approach_m=3.0, max_draws=100000)
        a.update(kw)
        return a

    def test_off_is_the_earlier_behaviour_and_a_rule_that_rejects_nothing_changes_nothing(self):
        zero = {"path_clearance_m": 0.0, "ask_zone_m": 0.0, "ask_standoff_m": 2.0, "reask_shift_m": 0.4}
        for seed in range(1, 8):
            base = sv.place_random(**self.args(seed=seed))
            self.assertEqual(sv.place_random(**self.args(seed=seed, clearance=None)), base)
            self.assertEqual(sv.place_random(**self.args(seed=seed, clearance=zero)), base)

    def test_the_rule_bites_and_every_accepted_set_is_clean(self):
        bitten = 0
        for seed in range(1, 21):
            for node in ("J1", "J2", "J3"):
                free = sv.place_random(**self.args(node=node, seed=seed))
                ruled = sv.place_random(**self.args(node=node, seed=seed, clearance=RULE))
                self.assertIsNone(sv.clearance_problem(self.road, node, ruled, {}, None, RULE), (node, seed))
                bitten += free != ruled
        self.assertGreater(bitten, 0)                                        # the rule changes some draws

    def test_an_unsatisfiable_rule_refuses_the_run_naming_the_rule(self):
        with self.assertRaisesRegex(ValueError, "clearance"):
            sv.place_random(**self.args(max_draws=50, clearance={**RULE, "ask_zone_m": 0.5}))

    def test_earlier_nodes_are_respected(self):
        sc = sv.scenario_ab("A4", 5)
        plan = sc["sim"].plan_workers()
        done: dict = {}
        for node, pts in plan.items():
            self.assertIsNone(sv.clearance_problem(sc["road"], node, pts, dict(done), sc["spec"].physical_map, RULE), node)
            done[node] = pts


class Survey(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.res = lc.survey(("A4",), range(1, 21), (0.4,))["A4"]

    def test_every_a4_plan_passes_the_independent_check_at_her_shift(self):
        b = self.res["by_shift"]["0.4"]
        self.assertEqual((b["plans"], b["plans_violating"]), (20, 0))
        self.assertGreaterEqual(b["min_clearance_m"], 1.0 - lc.EPS)
        self.assertLessEqual(b["max_ask_distance_m"], 5.5 + lc.EPS)
        self.assertEqual(self.res["not_belonging"], [])                      # 6.5 m and nearest node (16.20.1) still hold
        self.assertEqual(self.res["workers"], 200)

    def test_b4_has_the_same_placements_and_the_earlier_rules_hold(self):
        for seed in (1, 6, 13):
            a, b = sv.scenario_ab("A4", seed), sv.scenario_ab("B4", seed)
            plan = a["sim"].plan_workers()
            self.assertEqual(plan, b["sim"].plan_workers())
            allp = [q for pts in plan.values() for q in pts]
            for i, p in enumerate(allp):
                for q in allp[i + 1:]:
                    self.assertGreaterEqual(sv.math.dist(p, q), 3.0 - 1e-9)

    def test_the_beside_layouts_are_unchanged(self):
        j1 = sv.scenario_ab("A3", 1)["sim"].plan_workers()["J1"]
        self.assertEqual([tuple(round(c, 6) for c in q) for q in j1], [(3.75, -3.5), (9.75, 4.5), (2.25, 5.0)])

    def test_the_run_still_completes(self):
        sc = sv.scenario_ab("A4", 1, sv.DETECTION_ON)
        self.assertEqual(sc["sim"].run(sc["goal"])["outcome"], "SUCCESS")


if __name__ == "__main__":
    unittest.main()
