"""Variant T3 "checkpoint workers" (AUDIT.md 16.23, 2026-11-18). Simulator only; the controller key lie_detection.checkpoint defaults to false, so every earlier behaviour is unchanged.

Pinned: the defaults and the refusals; the provisional placement rule (midpoint, 3.0 m to the right, farther than 6.5 m from every node, 1.0 m clearance, 3.0 m separation) for
both layouts and all 20 seeds; the honest and lying checkpoint, the backtrack (two-way and three-way), the one backtrack per junction (no loop), detection off = the same run as
without the workers, the checkpoint workers' own noise stream, and the report's definitions."""

import json
import math
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import commander_v4 as cm  # noqa: E402
import hri_control as hc  # noqa: E402
import hri_control_v4 as hv  # noqa: E402
import hri_sim as hs  # noqa: E402
import hri_sim_v4 as sv  # noqa: E402
import report_t3_v4 as rt  # noqa: E402
import run_t3_v4 as rn  # noqa: E402
from tests.test_lie_detection_v4 import NORTH  # noqa: E402

CP = json.loads((ROOT / "configs/v4/experiments/checkpoints.json").read_text(encoding="utf-8"))
FIXED = {"J1>LEFT": [0, 3], "J1>RIGHT": [12.5, -3], "J1>FORWARD": [9.25, 10], "J2>FORWARD": [-12.5, 3], "J2>RIGHT": [-3.25, 10], "J3>LEFT": [21.75, 10],
         "J3>RIGHT": [15.75, -10], "J4>RIGHT": [-15.75, 10], "J4>LEFT": [-21.75, -10]}
CP_FIXED = {**CP, "fixed": FIXED}
ON = rn.detection_for("T3", "on", CP)
OFF = rn.detection_for("T3", "off", CP)


def go(goal, script=None, cp_lies=None, det=ON, cps=CP_FIXED, name="A3", seed=1):
    sc = sv.scenario_ab(name, seed, det, checkpoints=cps)
    sc["spec"].layout = NORTH
    sc["spec"].lie_script = script
    sc["spec"].cp_lies = cp_lies
    return sc["sim"].run(goal)


def log(r):
    return [(e["junction"], e["branch"], e["result"], e["action"]) for e in r["v4"]["checkpoint"]["log"]]


def controller(detection):
    base, v4 = hv.load_control()
    v4["lie_detection"] = {**v4["lie_detection"], **detection}
    return hv.ControllerV4(base, v4, cm.load_config(), hv.load_roadmap())


class Defaults(unittest.TestCase):
    def test_off_by_default_and_in_no_shipped_config(self):
        self.assertEqual((hv.LIE_DEFAULTS["checkpoint"], hv.LIE_DEFAULTS["checkpoint_fraction"]), (False, 0.5))
        for f in sorted((ROOT / "configs/v4").rglob("*.json")):
            ld = json.loads(f.read_text(encoding="utf-8")).get("lie_detection", {})
            self.assertNotIn("checkpoint", ld, f.name)
            self.assertNotIn("checkpoint_fraction", ld, f.name)
        self.assertFalse(controller({}).ld["checkpoint"])

    def test_refusals(self):
        with self.assertRaisesRegex(ValueError, "second_opinion_radius_m"):
            controller({"checkpoint": True, "second_opinion_radius_m": None})
        with self.assertRaisesRegex(ValueError, "checkpoint_fraction"):
            controller({"checkpoint": True, "checkpoint_fraction": 1.0})
        self.assertTrue(controller({"checkpoint": True}).ld["checkpoint"])

    def test_the_variants_of_the_runner(self):
        self.assertEqual(rn.detection_for("T0", "on", CP), sv.DETECTION_ON)
        self.assertEqual(rn.detection_for("T0", "off", CP), sv.DETECTION_OFF)
        self.assertEqual(rn.detection_for("T3", "off", CP), sv.DETECTION_OFF)                       # the robot ignores the workers
        self.assertEqual(rn.detection_for("T3", "on", CP), {**sv.DETECTION_ON, "checkpoint": True, "checkpoint_fraction": CP["fraction"]})
        self.assertEqual(CP["fraction"], hv.LIE_DEFAULTS["checkpoint_fraction"])                     # the worker's and the robot's rule are the same
        self.assertTrue(CP["provisional"])


class Placement(unittest.TestCase):
    def test_nine_checkpoints_at_the_midpoints_3_m_to_the_right_for_seed_1(self):
        sc = sv.scenario_ab("A3", 1, ON, checkpoints=CP)
        sc["sim"]._plan = sc["sim"].plan_workers()
        plan = sc["sim"].plan_checkpoints()
        self.assertEqual(len(plan), 9)
        self.assertEqual({k: (round(v["x"], 2), round(v["z"], 2)) for k, v in plan.items()},
                         {("J1", "FORWARD"): (9.25, 10.0), ("J1", "RIGHT"): (12.5, -3.0), ("J1", "LEFT"): (0.0, 3.0), ("J2", "FORWARD"): (-12.5, 3.0),
                          ("J2", "RIGHT"): (-3.25, 10.0), ("J3", "LEFT"): (21.75, 10.0), ("J3", "RIGHT"): (15.75, -10.0), ("J4", "RIGHT"): (-15.75, 10.0),
                          ("J4", "LEFT"): (-21.75, -10.0)})
        for (j, cmd), v in plan.items():
            self.assertAlmostEqual(math.dist(v["point"], tuple((a + b) / 2 for a, b in zip(sc["road"].pos(j), sc["road"].pos(v["next"])))), 0.0, places=9)
            self.assertEqual((v["side"], v["lateral_m"]), ("right", 3.0))

    def test_the_rules_hold_in_both_layouts_for_all_seeds(self):
        rule = sv.load_scenarios()["placement_rule"]
        for name in ("A3", "A4"):
            for seed in range(1, 21):
                sc = sv.scenario_ab(name, seed, ON, checkpoints=CP)
                sim, road = sc["sim"], sc["road"]
                sim._plan = sim.plan_workers()
                plan = sim.plan_checkpoints()
                self.assertEqual(len(plan), 9, (name, seed))
                workers = [q for pts in sim._plan.values() for q in pts]
                cps = [(v["x"], v["z"]) for v in plan.values()]
                roads = sv._road_segments(road, sc["spec"].physical_map)
                drive = [sg[:4] for node, pts in sim._plan.items() for sg in sv.drivable_segments(road, node, pts, rule["ask_standoff_m"], rule["reask_shift_m"])[0]]
                for (j, cmd), v in plan.items():
                    q = (v["x"], v["z"])
                    own = sv.checkpoint_segments(road, j, v["next"], v["point"], q, rule["ask_standoff_m"], rule["reask_shift_m"])
                    self.assertTrue(all(math.dist(q, road.pos(n)) > 6.5 for n in road.nodes), (name, seed, j, cmd))
                    self.assertTrue(all(math.dist(q, w) >= 3.0 - 1e-6 for w in workers + [c for c in cps if c != q]), (name, seed, j, cmd))
                    self.assertTrue(all(math.dist(q, t) >= 3.0 - 1e-6 for t in sv.turning_points(road, sc["spec"].physical_map)), (name, seed, j, cmd))
                    self.assertTrue(all(sv._seg_dist(q[0], q[1], sg) >= 1.0 - 1e-4 for sg in roads + drive + own), (name, seed, j, cmd))
                    self.assertTrue(all(sv._seg_dist(w[0], w[1], sg) >= 1.0 - 1e-4 for w in workers for sg in own), (name, seed, j, cmd))

    def test_no_decision_junction_no_checkpoint(self):
        for name in ("A1", "A2", "B1", "B2"):
            sc = sv.scenario_ab(name, 1, ON, checkpoints=CP)
            sc["sim"]._plan = sc["sim"].plan_workers()
            self.assertEqual(sc["sim"].plan_checkpoints(), {}, name)

    def test_an_impossible_rule_is_an_error_not_a_silent_drop(self):
        sc = sv.scenario_ab("A3", 1, ON, checkpoints={**CP, "lateral_m": [0.5], "side_order": ["right"]})
        sc["sim"]._plan = sc["sim"].plan_workers()
        with self.assertRaisesRegex(ValueError, "cannot place the checkpoint worker"):
            sc["sim"].plan_checkpoints()


class Behaviour(unittest.TestCase):
    def test_honest_checkpoints_say_proceed_and_the_robot_goes_on(self):
        r = go("E3")
        self.assertEqual((r["outcome"], r["v4"]["route"]), ("SUCCESS", ["A", "J1", "J3", "E3"]))
        self.assertEqual(log(r), [("J1", "RIGHT", "proceed", "continue"), ("J3", "LEFT", "proceed", "continue")])
        self.assertTrue(all(g["truthful"] and g["shown"] == "PROCEED" for g in r["gestures"] if g.get("kind") == "checkpoint"))

    def test_an_honest_checkpoint_on_a_wrong_branch_points_back_and_the_robot_returns_three_way(self):
        r = go("E3", [None, "LEFT"])                                      # J1's worker lies LEFT; J1 has three branches: ask again with LEFT excluded
        self.assertEqual((r["outcome"], r["v4"]["route"]), ("SUCCESS", ["A", "J1", "J1", "J3", "E3"]))
        self.assertEqual(log(r)[0], ("J1", "LEFT", "back", "backtrack"))
        back = [g for g in r["gestures"] if g.get("kind") == "checkpoint"][0]
        self.assertEqual((back["correct"], back["shown"], back["truthful"]), ("BACK", "BACK", True))
        self.assertEqual(r["v4"]["checkpoint"]["backtracks"], 1)
        self.assertEqual(len([d for d in r["v4"]["decisions"] if d["event"] == "ask_again_after_backtrack"]), 1)

    def test_two_way_the_other_branch_is_taken_without_a_question(self):
        r = go("E3", [None, None, None, "RIGHT"])                         # J3's worker lies RIGHT (E4); J3 has two branches
        self.assertEqual((r["outcome"], r["v4"]["route"]), ("SUCCESS", ["A", "J1", "J3", "J3", "E3"]))
        self.assertEqual(log(r), [("J1", "RIGHT", "proceed", "continue"), ("J3", "RIGHT", "back", "backtrack"), ("J3", "LEFT", "proceed", "continue")])
        self.assertEqual(len([d for d in r["v4"]["decisions"] if d["event"] == "take_other_branch"]), 1)

    def test_a_second_checkpoint_pointing_back_keeps_the_branch_no_loop(self):
        r = go("E3", [None, None, None, "RIGHT"], ["J3>LEFT"])           # the checkpoint of the right branch also lies: BACK
        self.assertEqual((r["outcome"], r["v4"]["route"]), ("SUCCESS", ["A", "J1", "J3", "J3", "E3"]))
        self.assertEqual(log(r)[1:], [("J3", "RIGHT", "back", "backtrack"), ("J3", "LEFT", "back", "keep")])
        self.assertEqual(r["v4"]["checkpoint"]["backtracks"], 1)

    def test_a_lying_checkpoint_on_the_right_branch_is_a_false_backtrack(self):
        r = go("E3", None, ["J1>RIGHT"])
        self.assertEqual(log(r)[0], ("J1", "RIGHT", "back", "backtrack"))
        self.assertEqual(r["outcome"], "FAILURE")
        m = rt.run_metrics({"gestures": r["gestures"], "go": [], "checkpoint": r["v4"]["checkpoint"]})
        self.assertEqual((m["false_backtracks"], m["caught"], m["cp_fooled"], m["backtracks"]), (1, 0, 1, 1))

    def test_a_lying_checkpoint_on_a_wrong_branch_lets_the_robot_through(self):
        r = go("E3", [None, "LEFT"], ["J1>LEFT"])                         # the junction lie is followed and the checkpoint shows PROCEED
        self.assertEqual(log(r)[0], ("J1", "LEFT", "proceed", "continue"))
        m = rt.run_metrics({"gestures": r["gestures"], "go": [{"node": "J1", "branch": "LEFT", "correct": "RIGHT"}], "checkpoint": r["v4"]["checkpoint"]})
        self.assertEqual((m["junction_fooled"], m["cp_fooled"], m["caught"], m["false_backtracks"]), (1, 1, 0, 0))

    def test_detection_off_ignores_the_workers_and_is_the_same_run_as_without_them(self):
        a, b = go("E3", det=OFF), go("E3", det=OFF, cps=None)
        self.assertEqual(log(a), [])
        self.assertEqual((a["outcome"], a["time_s"], a["v4"]["route"]), (b["outcome"], b["time_s"], b["v4"]["route"]))
        self.assertGreater(a["max_people_in_view"], b["max_people_in_view"])                # same scene logic differs: they are in view

    def test_t0_has_no_checkpoint_gestures_and_no_checkpoint_log(self):
        r = go("E3", det=sv.DETECTION_ON, cps=None)
        self.assertEqual(log(r), [])
        self.assertFalse(any(g.get("kind") == "checkpoint" for g in r["gestures"]))

    def test_truthful_runs_never_backtrack(self):
        for name in ("A3", "A4"):
            for seed in range(1, 7):
                sc = sv.scenario_ab(name, seed, ON, checkpoints=CP, sim_cfg=hs.SimConfig(timeout_s=420.0))
                r = sc["sim"].run(sc["goal"])
                self.assertEqual(r["outcome"], "SUCCESS", (name, seed))
                self.assertEqual(r["v4"]["checkpoint"]["backtracks"], 0, (name, seed))
                self.assertTrue(all(e["result"] == "proceed" for e in r["v4"]["checkpoint"]["log"]), (name, seed))


class Noise(unittest.TestCase):
    def test_the_checkpoint_workers_do_not_move_the_junction_workers_draws(self):
        cfg, g = hs.SimConfig(), sv.GestureSimConfig()
        w1 = sv.Person(1, 3.0, 4.0, "sunbox_m1", "commander")
        cp = sv.Person(100, 8.0, 2.0, "sunbox_f1", "bystander", cp=True)
        a = sv.VisionSim(sv.Scene([w1]), cfg, g, 5)
        b = sv.VisionSim(sv.Scene([sv.Person(1, 3.0, 4.0, "sunbox_m1", "commander"), cp]), cfg, g, 5)
        for k in range(30):
            da = a.detect(0.1 * k, 0.0, 10.0)
            db = [d for d in b.detect(0.1 * k, 0.0, 10.0) if d["id"] == 1]
            self.assertEqual(da, db)


class Report(unittest.TestCase):
    def rec(self, **kw):
        base = {"variant": "T3", "experiment": "B3", "setting": "on", "seed": 1, "outcome": "SUCCESS", "failure_reason": "none", "time_s": 100.0, "max_people_in_view": 5,
                "go": [], "gestures": [], "checkpoint": {"log": [], "backtracks": 0}}
        base.update(kw)
        return base

    def test_definitions(self):
        gest = [{"node": "J1", "worker": 1, "truthful": False, "shown": "LEFT", "correct": "RIGHT"},
                {"node": "J1", "branch": "LEFT", "kind": "checkpoint", "truthful": True, "shown": "BACK", "correct": "BACK"},
                {"node": "J3", "branch": "LEFT", "kind": "checkpoint", "truthful": False, "shown": "BACK", "correct": "PROCEED"}]
        log_ = [{"junction": "J1", "branch": "LEFT", "result": "back", "action": "backtrack"}, {"junction": "J3", "branch": "LEFT", "result": "back", "action": "backtrack"}]
        m = rt.run_metrics(self.rec(gestures=gest, go=[{"node": "J1", "branch": "LEFT", "correct": "RIGHT"}], checkpoint={"log": log_, "backtracks": 2}))
        self.assertEqual((m["junction_fooled"], m["caught"], m["false_backtracks"], m["cp_fooled"], m["backtracks"], m["cp_lying"]), (1, 1, 1, 1, 2, 1))

    def test_a_wrong_branch_without_a_lie_is_not_a_fooled_lie(self):
        m = rt.run_metrics(self.rec(go=[{"node": "J3", "branch": "RIGHT", "correct": "LEFT"}]))
        self.assertEqual((m["junction_fooled"], m["wrong_branch_without_a_lie"]), (0, 1))

    def test_summary_and_checks(self):
        rows = [self.rec(variant="T0", seed=s, max_people_in_view=2, experiment="A3", outcome="SUCCESS") for s in (1, 2)] + \
               [self.rec(variant="T3", seed=1, experiment="A3"), self.rec(variant="T3", seed=2, experiment="A3", outcome="FAILURE", failure_reason="timeout", time_s=420.0,
                                                                          checkpoint={"log": [], "backtracks": 1})]
        s = rt.summarise(rows)
        self.assertEqual((s[("A3", "on", "T3")]["success"], s[("A3", "on", "T3")]["timeout"], s[("A3", "on", "T3")]["max_people_in_view"]), (1, 1, 5))
        c = rt.checks(s)
        self.assertEqual(c["A_success_lost_vs_T0"], {"A3 on": 1})
        self.assertEqual(c["A_backtracks"], {"A3 on": 1})


if __name__ == "__main__":
    unittest.main()
