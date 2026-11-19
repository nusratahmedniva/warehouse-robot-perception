"""Variant T3 "checkpoint workers" (AUDIT.md 16.23, 2026-11-18). Simulator only; the controller key lie_detection.checkpoint defaults to false, so every earlier behaviour is unchanged.

Added for T4 (AUDIT.md 16.24): lie_detection.checkpoint_scope "disputed" = a checkpoint pointing back counts only when the junction's answers disagreed.

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
import report_t4_oos_v4 as oos  # noqa: E402
import run_t3_v4 as rn  # noqa: E402
from tests.test_lie_detection_v4 import NORTH  # noqa: E402

CP_NEW = json.loads((ROOT / "configs/v4/experiments/checkpoints.json").read_text(encoding="utf-8"))          # the layout of AUDIT.md 16.25.1: 7 fixed checkpoints
CP = {k: v for k, v in CP_NEW.items() if k not in ("branches", "branches_note", "fixed_first", "fixed_first_note")}              # the layout of 16.23 to 16.25.0.1: 9 checkpoints planned after the workers
FIXED = {"J1>LEFT": [0, 3], "J1>RIGHT": [12.5, -3], "J1>FORWARD": [9.25, 10], "J2>FORWARD": [-12.5, 3], "J2>RIGHT": [-3.25, 10], "J3>LEFT": [21.75, 10],
         "J3>RIGHT": [15.75, -10], "J4>RIGHT": [-15.75, 10], "J4>LEFT": [-21.75, -10]}
CP_FIXED = {**CP, "fixed": FIXED}
ON = rn.detection_for("T3", "on", CP)
OFF = rn.detection_for("T3", "off", CP)
T4 = rn.detection_for("T4", "on", CP)
T4N = rn.detection_for("T4", "on", CP_NEW)
FIXED7 = {k: v for k, v in FIXED.items() if k not in ("J1>LEFT", "J2>FORWARD")}
CP_FIXED7 = {**CP_NEW, "fixed": FIXED7}
ON_FILES = ["control_lie_on.json", "control_lie_on_a1.json", "control_lie_on_a2_right.json", "control_lie_on_a2_left.json"]
TWO_AT_J3 = {"kind": "fixed", "points": {**NORTH["points"], "J3": [[18.75, 2.5], [17.0, 3.5]]}}     # J3: two workers, so its answers can disagree


def go(goal, script=None, cp_lies=None, det=ON, cps=CP_FIXED, name="A3", seed=1, layout=NORTH, xcheck=False):
    sc = sv.scenario_ab(name, seed, det, checkpoints=cps)
    if xcheck:                                                                   # the hand cross-check settles the mirror ambiguity: the tests are about the rules
        sc["sim"].g.crosscheck_accuracy = 1.0
        sc["sim"].c.v4["dialog"]["use_hand_crosscheck_as_tiebreak"] = True
    sc["spec"].layout = layout
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
    def test_off_by_default_and_only_the_four_detection_on_control_files_carry_it(self):
        self.assertEqual((hv.LIE_DEFAULTS["checkpoint"], hv.LIE_DEFAULTS["checkpoint_fraction"]), (False, 0.5))
        self.assertFalse(controller({}).ld["checkpoint"])
        self.assertEqual(hv.LIE_DEFAULTS["checkpoint_scope"], "any")
        carrying = set()
        for f in sorted((ROOT / "configs/v4").rglob("*.json")):
            ld = json.loads(f.read_text(encoding="utf-8")).get("lie_detection", {})
            if any(k in ld for k in ("checkpoint", "checkpoint_fraction", "checkpoint_scope")):
                carrying.add(f.name)
        self.assertEqual(carrying, set(ON_FILES))                         # AUDIT.md 16.24.3: control.json, the zoom files and the off files do not

    def test_refusals(self):
        with self.assertRaisesRegex(ValueError, "second_opinion_radius_m"):
            controller({"checkpoint": True, "second_opinion_radius_m": None})
        with self.assertRaisesRegex(ValueError, "checkpoint_fraction"):
            controller({"checkpoint": True, "checkpoint_fraction": 1.0})
        with self.assertRaisesRegex(ValueError, "checkpoint_scope"):
            controller({"checkpoint": True, "checkpoint_scope": "everywhere"})
        self.assertTrue(controller({"checkpoint": True}).ld["checkpoint"])

    def test_the_variants_of_the_runner(self):
        self.assertEqual(rn.detection_for("T0", "on", CP), sv.DETECTION_ON)
        self.assertEqual(rn.detection_for("T0", "off", CP), sv.DETECTION_OFF)
        self.assertEqual(rn.detection_for("T3", "off", CP), sv.DETECTION_OFF)                       # the robot ignores the workers
        self.assertEqual(rn.detection_for("T3", "on", CP), {**sv.DETECTION_ON, "checkpoint": True, "checkpoint_fraction": CP["fraction"]})
        self.assertEqual(rn.detection_for("T4", "on", CP), {**rn.detection_for("T3", "on", CP), "checkpoint_scope": "disputed", "checkpoint_person_radius_m": 5.0})          # T4 = T3 + the dispute test + R of 16.25
        self.assertEqual(rn.detection_for("T4", "off", CP), sv.DETECTION_OFF)
        self.assertEqual(rn.VARIANTS, ("T0", "T3", "T4"))
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


class VoteNotVeto(unittest.TestCase):
    """T4 (AUDIT.md 16.24)."""

    def test_a_pointing_back_is_ignored_when_the_junction_answers_agreed(self):
        a = go("E3", [None, None, None, "RIGHT"])                                  # T3: one worker lies RIGHT at J3, nobody disagrees: the honest checkpoint overrides, success
        b = go("E3", [None, None, None, "RIGHT"], det=T4)
        self.assertEqual((a["outcome"], log(a)[1]), ("SUCCESS", ("J3", "RIGHT", "back", "backtrack")))
        self.assertEqual(log(b)[1], ("J3", "RIGHT", "back", "ignore_undisputed"))
        self.assertEqual((b["outcome"], b["failure_reason"], b["v4"]["route"]), ("FAILURE", "wrong_goal", ["A", "J1", "J3", "E4"]))
        self.assertEqual(b["v4"]["checkpoint"]["backtracks"], 0)

    def test_a_pointing_back_counts_when_the_junction_answers_disagreed(self):
        script = [None, None, None, "RIGHT", None, "RIGHT"]                       # J3: the first worker lies RIGHT, the second says LEFT, the tie re-asks the first
        a = go("E3", script, layout=TWO_AT_J3, xcheck=True)
        b = go("E3", script, det=T4, layout=TWO_AT_J3, xcheck=True)
        votes = [[v["branch"] for v in d["votes"]] for d in b["v4"]["decisions"] if d["event"] == "go" and d["node"] == "J3"][0]
        self.assertEqual(votes, ["RIGHT", "LEFT", "RIGHT"])
        self.assertEqual(log(b), log(a))
        self.assertEqual((b["outcome"], b["v4"]["route"]), ("SUCCESS", ["A", "J1", "J3", "J3", "E3"]))
        self.assertEqual(log(b)[1], ("J3", "RIGHT", "back", "backtrack"))

    def test_a_lying_checkpoint_on_the_right_branch_is_ignored_when_the_junction_agreed(self):
        a = go("E3", None, ["J1>RIGHT"])                                            # T3: the false backtrack
        b = go("E3", None, ["J1>RIGHT"], det=T4)
        self.assertEqual((log(a)[0], a["outcome"]), (("J1", "RIGHT", "back", "backtrack"), "FAILURE"))
        self.assertEqual((log(b)[0], b["outcome"]), (("J1", "RIGHT", "back", "ignore_undisputed"), "SUCCESS"))

    def test_the_dispute_is_checked_before_the_one_backtrack_rule(self):
        b = go("E3", [None, None, None, "RIGHT"], ["J3>LEFT"], det=T4)             # undisputed: both pointings back are ignored, nothing is kept or backtracked
        self.assertEqual([e[3] for e in log(b)[1:]], ["ignore_undisputed"])

    def test_the_off_rows_and_the_a_rows_are_the_same_as_t3(self):
        for seed in range(1, 5):
            sc3 = sv.scenario_ab("A3", seed, ON, checkpoints=CP, sim_cfg=hs.SimConfig(timeout_s=420.0))
            sc4 = sv.scenario_ab("A3", seed, T4, checkpoints=CP, sim_cfg=hs.SimConfig(timeout_s=420.0))
            r3, r4 = sc3["sim"].run(sc3["goal"]), sc4["sim"].run(sc4["goal"])
            self.assertEqual((r3["outcome"], r3["time_s"], r3["v4"]["route"]), (r4["outcome"], r4["time_s"], r4["v4"]["route"]), seed)
            self.assertEqual(r4["v4"]["checkpoint"]["backtracks"], 0)


class AdoptedConfigs(unittest.TestCase):
    """AUDIT.md 16.24.3: T4 is switched on in the control files of the detection-on settings; the detection-off files ignore the checkpoints."""
    EXP = ROOT / "configs/v4/experiments"

    def test_the_on_files_carry_t4_exactly_and_build_a_controller_with_it(self):
        base = json.loads((ROOT / "configs/v4/control.json").read_text(encoding="utf-8"))["lie_detection"]
        for name in ON_FILES:
            f = json.loads((self.EXP / name).read_text(encoding="utf-8"))["lie_detection"]
            flags = {k: v for k, v in f.items() if k != "why"}
            self.assertEqual(flags, {**{k: v for k, v in base.items() if k != "why"}, **T4N}, name)         # the T4 detection of the runner (16.25.1 layout), every other key as control.json
            self.assertEqual((f["backtrack"], f["checkpoint"], f["checkpoint_scope"], f["checkpoint_fraction"]), (False, True, "disputed", 0.5), name)
            self.assertIn("16.24.3", f["why"]["checkpoint"])
            c = hv.make_controller_v4(str(self.EXP / name))
            self.assertEqual((c.ld["checkpoint"], c.ld["checkpoint_scope"], c.ld["checkpoint_fraction"], c.ld["backtrack"]), (True, "disputed", 0.5, False), name)
            self.assertEqual((f["checkpoint_branches"], f["next_junction_back"], f["checkpoint_person_radius_m"]), (CP_NEW["branches"], True, 5.0), name)       # AUDIT.md 16.25 / 16.25.1
            self.assertIn("16.25.1", f["why"]["checkpoint"])

    def test_the_off_files_and_the_base_files_ignore_the_checkpoints(self):
        for rel in ("configs/v4/control.json", "configs/v4/control_zoom_on.json", "configs/v4/control_zoom_off.json",
                    *[f"configs/v4/experiments/control_lie_off{m}.json" for m in ("", "_a1", "_a2_right", "_a2_left") if (self.EXP / f"control_lie_off{m}.json").exists()]):
            c = hv.make_controller_v4(str(ROOT / rel))
            self.assertFalse(c.ld["checkpoint"], rel)
            self.assertEqual(c.ld["checkpoint_scope"], "any", rel)

    def test_the_declared_text_changes(self):
        plan = json.loads((ROOT / "configs/v4/final_plan.json").read_text(encoding="utf-8"))
        note = plan["test_assignment_note"]
        self.assertNotIn("third worker at J1 (A3", note)
        self.assertIn("two workers", note)
        self.assertIn("16.24.3", note)
        diffs = json.loads((ROOT / "configs/v4/analysis.json").read_text(encoding="utf-8"))["declared_differences"]
        d = diffs[-1]
        self.assertTrue(d.startswith("Checkpoint workers (v4 only, T4;"))
        for text in ("designed after seeing", "+20.0 pp", "-0.5 to +38.4", "p = 0.039", "supplementary only", "38 of 40", "one result counted twice", "provisional"):
            self.assertIn(text, d)
        for text in ("CORRECTED 2026-11-19", "16.25.0.1", "NEXT junction", "+17.5 pp", "-3.2 to +36.2", "p = 0.065"):
            self.assertIn(text, d)
        self.assertEqual(sum("T4" in x for x in diffs), 1)

    def run_file(self, name, seed, control):
        """A run driven by the control file itself (no detection override) in the scene of the 16.25.1 layout."""
        sc = sv.scenario_ab(name, seed, None, control_path=str(self.EXP / control), checkpoints=CP_NEW, sim_cfg=hs.SimConfig(timeout_s=900.0))
        return sc["sim"].run(sc["goal"])

    def test_a_run_from_the_control_file_is_the_t4_run_of_the_runner(self):
        for name, control in (("A3", "control_lie_on.json"), ("A4", "control_lie_on.json"), ("B3", "control_lie_on.json"), ("B4", "control_lie_on.json")):
            for seed in (21, 26, 36, 40):
                a = self.run_file(name, seed, control)
                b = rn.one_run("T4", name, "on", seed, 900.0, CP_NEW, sv.load_scenarios())
                self.assertEqual((a["outcome"], a["failure_reason"], a["time_s"], a["v4"]["route"]), (b["outcome"], b["failure_reason"], b["time_s"], b["route"]), (name, seed))

    def test_the_a_rows_are_unchanged_by_the_files(self):
        for name in ("A3", "A4"):
            t0 = [sv.run_scenario(name, s, sv.DETECTION_ON, sim_cfg=hs.SimConfig(timeout_s=900.0)) for s in range(21, 31)]
            t4 = [self.run_file(name, s, "control_lie_on.json") for s in range(21, 31)]
            self.assertTrue(all(r["outcome"] == "SUCCESS" for r in t0 + t4), name)
            self.assertEqual(sum(r["v4"]["checkpoint"]["backtracks"] for r in t4), 0, name)
            self.assertTrue(all(e["result"] == "proceed" for r in t4 for e in r["v4"]["checkpoint"]["log"]), name)

    def test_the_numbers_of_16_25_1_1_are_reproduced_from_the_control_file(self):
        """Seeds 21 to 60, cap 900 s (AUDIT.md 16.25.1.1): B3 on and B4 on, T0 (the checkpoint workers present and ignored, the earlier 'on') against T4 (control_lie_on.json in the 16.25.1 layout)."""
        want = {"T0": (23, 8, 9), "T4": (30, 6, 4, 13, 4, 1)}                   # successes, wrong goals, aborts [, backtracks, of them at the next junction, false backtracks]
        for name in ("B3", "B4"):
            t0 = [sv.run_scenario(name, s, sv.DETECTION_ON, sim_cfg=hs.SimConfig(timeout_s=900.0), checkpoints=CP_NEW) for s in range(21, 61)]
            t4 = [self.run_file(name, s, "control_lie_on.json") for s in range(21, 61)]
            count = lambda rs, why: sum(1 for r in rs if r["failure_reason"] == why)
            self.assertEqual((sum(r["outcome"] == "SUCCESS" for r in t0), count(t0, "wrong_goal"), count(t0, "aborted")), want["T0"], name)
            self.assertEqual((sum(r["outcome"] == "SUCCESS" for r in t4), count(t4, "wrong_goal"), count(t4, "aborted")), want["T4"][:3], name)
            self.assertEqual(sum(r["v4"]["checkpoint"]["backtracks"] for r in t4), want["T4"][3], name)
            self.assertEqual(sum(len(r["v4"]["checkpoint"]["next_junction_back"]) for r in t4), want["T4"][4], name)
            rows = [{"gestures": r["gestures"], "go": [{"node": d["node"], "branch": d["branch"], "correct": sc_road_correct(name, r, d)} for d in r["v4"]["decisions"] if d["event"] == "go"],
                     "checkpoint": r["v4"]["checkpoint"]} for r in t4]
            self.assertEqual(sum(rt.run_metrics(x)["false_backtracks"] for x in rows), want["T4"][5], name)
            self.assertEqual(sum(r["failure_reason"] == "timeout" for r in t0 + t4), 0, name)                                       # the 900 s cap truncates nothing
            self.assertGreaterEqual(sum(r["outcome"] == "SUCCESS" for r in t4) - sum(r["outcome"] == "SUCCESS" for r in t0), 6)    # the 15 pp bar of 40 runs

    def test_the_numbers_of_16_25_0_1_are_still_reproduced_by_the_earlier_layout(self):
        """The model of 16.25.0.1 (9 checkpoints planned after the workers, no BACK vote): T4 = the old switches with CP (no `branches`): 30/40 in both rows, 14 backtracks, 2 false."""
        for name in ("B3", "B4"):
            t4 = []
            for s in range(21, 61):
                sc = sv.scenario_ab(name, s, T4, checkpoints=CP, sim_cfg=hs.SimConfig(timeout_s=900.0))
                t4.append(sc["sim"].run(sc["goal"]))
            count = lambda rs, why: sum(1 for r in rs if r["failure_reason"] == why)
            self.assertEqual((sum(r["outcome"] == "SUCCESS" for r in t4), count(t4, "wrong_goal"), count(t4, "aborted")), (30, 5, 5), name)
            self.assertEqual(sum(r["v4"]["checkpoint"]["backtracks"] for r in t4), 14, name)
            self.assertEqual(sum(len(r["v4"]["checkpoint"]["next_junction_back"]) for r in t4), 0, name)


def sc_road_correct(name: str, result: dict, decision: dict) -> str:
    """The true command toward the goal at the node of a 'go' decision (evaluation side: the test knows the goal)."""
    road = hc.Roadmap(hc.load_json("configs/v4/roadmap.json"))
    return road.command_toward(decision["node"], result["goal"])


class PersonRule(unittest.TestCase):
    """Who is asked at a checkpoint (AUDIT.md 16.25): within R of THIS spot, this spot the nearest, outside every junction zone."""

    def at_spot(self, j, cmd, detection=T4):
        c = controller(detection)
        c.cp = {"junction": j, "branch": cmd, "next": c.road.next(j, cmd), "point": c._cp_point(j, c.road.next(j, cmd)), "stage": "dialog"}
        return c

    def test_each_of_the_three_conditions_alone_rejects(self):
        c = self.at_spot("J1", "LEFT")                                                  # the spot (0, 0), R = 5.0 m
        self.assertEqual(c.ld["checkpoint_person_radius_m"], 5.0)
        self.assertTrue(c._cp_qualifies({"x": 0.0, "z": 3.0}))                          # the checkpoint worker: 3.0 m, nearest spot, 6.9 m from J1 and J2
        self.assertFalse(c._cp_qualifies({"x": 0.0, "z": 5.5}))                         # (a) farther than R (5.5 m), nothing else wrong
        self.assertFalse(c._cp_qualifies({"x": 2.0, "z": 0.0}))                         # (c) 4.25 m from J1: inside its zone
        wide = self.at_spot("J1", "LEFT", {**T4, "checkpoint_person_radius_m": 10.0})
        self.assertTrue(wide._cp_qualifies({"x": 0.0, "z": 3.0}))
        self.assertFalse(wide._cp_qualifies({"x": -4.0, "z": 8.0}))                     # (b) 8.9 m from this spot, 3.0 m from the spot of J2 RIGHT; (a) and (c) hold: outside every zone
        other = self.at_spot("J2", "RIGHT", {**T4, "checkpoint_person_radius_m": 10.0})
        self.assertTrue(other._cp_qualifies({"x": -4.0, "z": 8.0}))                      # the same person qualifies at the spot they are nearest to

    def test_a_worker_of_another_junction_never_qualifies_and_a_junction_worker_neither(self):
        c = self.at_spot("J1", "LEFT")
        self.assertFalse(c._cp_qualifies({"x": -3.25, "z": -2.0}))                      # a worker of J2: 3.8 m from the spot, the nearest person, 3.6 m from J2
        self.assertFalse(c._cp_qualifies({"x": -8.75, "z": 4.0}))
        self.assertFalse(c._cp_qualifies({"x": 4.25, "z": -3.0}))                       # a worker of J1: 5.2 m from the spot and inside the J1 zone

    def test_a_pan_tilt_person_is_read_only_when_linked_to_a_qualifying_track(self):
        c = self.at_spot("J1", "LEFT")
        inp = hv.TickInputV4(time_s=1.0, x=0.0, z=0.0, yaw_deg=0.0, people_time_s=1.0,
                             people=[{"x": 0.0, "z": 3.0, "track_id": 7, "distance_m": 3.0, "bearing_deg": 0.0}, {"x": -3.25, "z": -2.0, "track_id": 8, "distance_m": 3.8, "bearing_deg": 0.0}])
        for tid, ok in ((7, True), (8, False), (None, False), (99, False)):
            c._link_360 = lambda p, i, tid=tid: tid
            self.assertEqual(c._cp_pt_ok(None, inp), ok, tid)

    def test_the_spots_are_the_roadmaps_and_the_junction_worker_of_a_wrong_scene_is_not_asked_in_a_run(self):
        layout = {"kind": "fixed", "points": {**NORTH["points"], "J1": [[6.25, 2.5], [13.5, 1.5]]}}      # J1's second worker stands at J3's zone, 1.8 m from the spot of J1 RIGHT: the nearest person
        r = go("E3", det=T4, layout=layout)
        self.assertEqual((r["outcome"], r["v4"]["route"]), ("SUCCESS", ["A", "J1", "J3", "E3"]))
        asked = [e["person_360"] for e in r["v4"]["checkpoint"]["log"]]
        self.assertEqual(len(asked), 2)
        self.assertTrue(all(x >= 100 for x in asked), asked)                            # checkpoint workers only (ids 100 and up), never the junction worker (id 2)
        self.assertTrue(all(rec["person_360"] >= 100 for rec in r["junctions"] if rec.get("checkpoint")))

    def test_the_checkpoint_worker_is_the_only_person_who_qualifies_for_every_checkpoint_of_the_provisional_layout(self):
        for name in ("A3", "A4"):
            for seed in range(1, 21):
                sc = sv.scenario_ab(name, seed, T4, checkpoints=CP)
                sim = sc["sim"]
                sim._plan = sim.plan_workers()
                plan = sim.plan_checkpoints()
                everyone = [{"x": q[0], "z": q[1], "track_id": 1 + i} for i, q in enumerate(q for pts in sim._plan.values() for q in pts)]
                everyone += [{"x": v["x"], "z": v["z"], "track_id": 100 + i} for i, v in enumerate(plan.values())]
                for (j, cmd), v in plan.items():
                    sim.c.cp = {"junction": j, "branch": cmd, "next": v["next"], "point": v["point"], "stage": "dialog"}
                    ok = [q["track_id"] for q in everyone if sim.c._cp_qualifies(q)]
                    mine = [q["track_id"] for q in everyone if (q["x"], q["z"]) == (v["x"], v["z"])]
                    self.assertEqual(ok, mine, (name, seed, j, cmd))

    def test_in_the_runs_every_checkpoint_dialog_asks_its_own_worker_in_every_branch(self):
        for name, seeds in (("A3", range(1, 7)), ("A4", range(1, 5)), ("B3", range(1, 9))):
            for seed in seeds:
                sc = sv.scenario_ab(name, seed, T4, checkpoints=CP, sim_cfg=hs.SimConfig(timeout_s=900.0))
                r = sc["sim"].run(sc["goal"])
                for e in r["v4"]["checkpoint"]["log"]:
                    self.assertFalse(e["no_person"], (name, seed, e))
                    self.assertGreaterEqual(e["person_360"], 100, (name, seed, e))

    def test_nobody_qualifies_is_none_logged_and_never_a_backtrack(self):
        r = go("E3", det=T4, cps=None)                                                  # the robot looks for checkpoint workers, the scene has none
        self.assertEqual((r["outcome"], r["v4"]["route"]), ("SUCCESS", ["A", "J1", "J3", "E3"]))
        self.assertEqual([(e["result"], e["action"], e["no_person"]) for e in r["v4"]["checkpoint"]["log"]], [("none", "continue", True)] * 2)
        self.assertEqual(len([d for d in r["v4"]["decisions"] if d["event"] == "checkpoint_no_person"]), 2)
        self.assertEqual(r["v4"]["checkpoint"]["backtracks"], 0)
        lied = go("E3", [None, "LEFT"], det=T4, cps=None)                               # a followed junction lie: nobody to say BACK: carry on, no backtrack
        self.assertEqual(lied["v4"]["checkpoint"]["backtracks"], 0)
        self.assertTrue(all(e["result"] == "none" for e in lied["v4"]["checkpoint"]["log"]))
        self.assertNotEqual(lied["outcome"], "SUCCESS")


class NextJunctionBack(unittest.TestCase):
    """AUDIT.md 16.25.1: after a disputed junction a BACK answer at the next junction (reached by a branch without a checkpoint worker) is a vote to go back."""
    TWO_AT_J1 = {"kind": "fixed", "points": {**NORTH["points"], "J1": [[6.25, 2.5], [3.0, 5.0]]}}      # J1: two workers, so its answers can disagree

    def go7(self, goal, script, layout, det=T4N):
        return go(goal, script, det=det, cps=CP_FIXED7, layout=layout, xcheck=True)

    def test_the_layout_and_the_switches(self):
        self.assertEqual(CP_NEW["branches"], ["J1>FORWARD", "J1>RIGHT", "J2>RIGHT", "J3>LEFT", "J3>RIGHT", "J4>RIGHT", "J4>LEFT"])      # no J1 LEFT (to J2), no J2 FORWARD (to J4)
        self.assertTrue(CP_NEW["fixed_first"])
        self.assertEqual(T4N["checkpoint_branches"], CP_NEW["branches"])
        self.assertTrue(T4N["next_junction_back"])
        self.assertNotIn("next_junction_back", T4)                                      # without `branches` T4 is the T4 of 16.25.0.1
        self.assertEqual((hv.LIE_DEFAULTS["next_junction_back"], hv.LIE_DEFAULTS["checkpoint_branches"]), (False, None))
        c = controller(T4N)
        self.assertEqual((c.ld["next_junction_back"], c.ld["checkpoint_branches"]), (True, CP_NEW["branches"]))
        self.assertEqual(sorted(c._cp_spots()), sorted(tuple(b.split(">")) for b in CP_NEW["branches"]))     # the robot's spots are the branches with a worker
        with self.assertRaisesRegex(ValueError, "checkpoint_branches"):
            controller({**T4N, "checkpoint_branches": ["J1>LEFT", "J1>BACK"]})
        with self.assertRaisesRegex(ValueError, "checkpoint_branches"):
            controller({**T4N, "checkpoint_branches": ["J3>LEFT", "J3 LEFT"]})                # malformed
        self.assertTrue(controller({**T4N, "checkpoint_branches": ["J3>LEFT", "J9>LEFT"]}).ld["checkpoint"])        # a junction this map does not have: ignored (the list is the deployment's)
        small = hv.ControllerV4(*hv.load_control(), cm.load_config(), hc.Roadmap(sv.load_scenarios()["maps"]["corridor"]))
        self.assertIsNone(small.ld["checkpoint_branches"])
        base, v4 = hv.load_control()
        v4["lie_detection"] = {**v4["lie_detection"], **T4N}
        corridor = hv.ControllerV4(base, v4, cm.load_config(), hc.Roadmap(sv.load_scenarios()["maps"]["corridor"]))          # the 7 branches of the v4 map on the corridor map: no error, no spot
        self.assertEqual(corridor._cp_spots(), {})

    def test_arriving_on_a_wrong_branch_from_a_disputed_junction_backtracks_and_succeeds(self):
        r = self.go7("E3", [None, "LEFT", None, "LEFT"], self.TWO_AT_J1)               # J1: the first worker lies LEFT, the second says RIGHT, the tie follows the first: LEFT to J2
        self.assertEqual((r["outcome"], r["v4"]["route"]), ("SUCCESS", ["A", "J1", "J2", "J1", "J3", "E3"]))
        votes = [[v["branch"] for v in d["votes"]] for d in r["v4"]["decisions"] if d["event"] == "go" and d["node"] == "J1"][0]
        self.assertEqual(votes, ["LEFT", "RIGHT", "LEFT"])                                # disputed
        nj = r["v4"]["checkpoint"]["next_junction_back"]
        self.assertEqual([(e["junction"], e["branch"], e["at"], e["action"]) for e in nj], [("J1", "LEFT", "J2", "backtrack")])
        self.assertEqual(r["v4"]["checkpoint"]["backtracks"], 1)
        self.assertEqual([e[:2] for e in [(x["junction"], x["branch"]) for x in r["v4"]["checkpoint"]["log"]]], [("J1", "RIGHT"), ("J3", "LEFT")])     # no checkpoint on J1 LEFT
        ev = [d["event"] for d in r["v4"]["decisions"]]
        self.assertIn("ask_again_after_backtrack", ev)
        self.assertEqual(len([d for d in r["v4"]["decisions"] if d["event"] == "answer_rejected"]), 0)
        self.assertTrue(any(d["event"] == "answer_accepted" and d.get("back_vote") for d in r["v4"]["decisions"]))

    def test_from_an_undisputed_junction_back_is_still_rejected(self):
        r = self.go7("E3", [None, "LEFT"], NORTH)                                       # J1 has one worker: nobody disagrees
        self.assertEqual((r["outcome"], r["failure_reason"], r["v4"]["route"]), ("FAILURE", "aborted", ["A", "J1", "J2"]))
        self.assertEqual(r["v4"]["checkpoint"]["next_junction_back"], [])
        self.assertEqual(r["v4"]["checkpoint"]["backtracks"], 0)
        self.assertEqual({d["reason"] for d in r["v4"]["decisions"] if d["event"] == "answer_rejected"}, {"arrival"})
        off = self.go7("E3", [None, "LEFT", None, "LEFT"], self.TWO_AT_J1, det={**T4N, "next_junction_back": False})      # the switch off: rejected, abort, as T4 of 16.25.0.1
        self.assertEqual((off["failure_reason"], off["v4"]["checkpoint"]["backtracks"]), ("aborted", 0))

    def test_a_branch_with_a_checkpoint_worker_is_unchanged_and_the_other_conditions(self):
        c = controller(T4N)
        c.begin(0.0)
        c.node = "J3"
        c.last_choice = {"node": "J1", "branch": "RIGHT", "serial": 2, "disagreed": True}          # J1 RIGHT has a checkpoint worker: back stays rejected at J3
        self.assertIsNone(c._back_context("J3"))
        c.last_choice = {"node": "J1", "branch": "LEFT", "serial": 2, "disagreed": True}
        c.tried = {"J1": {"LEFT"}}
        self.assertEqual(c._back_context("J2"), {"junction": "J1", "branch": "LEFT", "serial": 2})                    # no checkpoint on J1 LEFT, disputed, an untried branch: counts
        self.assertIsNone(c._back_context("J3"))                                        # J3 is not the node J1 LEFT leads to
        self.assertIsNone(c._back_context("E1"))                                        # not a junction
        c.last_choice = {"node": "J1", "branch": "LEFT", "serial": 2, "disagreed": False}
        self.assertIsNone(c._back_context("J2"))                                        # undisputed
        c.last_choice = {"node": "J1", "branch": "LEFT", "serial": 2, "disagreed": True}
        c.backtracked = {"J1"}
        self.assertIsNone(c._back_context("J2"))                                        # at most once per J
        c.backtracked = set()
        c.tried = {"J1": {"LEFT", "RIGHT", "FORWARD"}}
        self.assertIsNone(c._back_context("J2"))                                        # nothing untried at J
        c.tried = {"J1": {"LEFT"}}
        c.ld["next_junction_back"] = False
        self.assertIsNone(c._back_context("J2"))                                        # the switch is off
        c.ld["next_junction_back"] = True
        c.last_choice = {"node": "J2", "branch": "FORWARD", "serial": 3, "disagreed": True}
        c.tried = {"J2": {"FORWARD"}}
        self.assertEqual(c._back_context("J4"), {"junction": "J2", "branch": "FORWARD", "serial": 3})                 # the other branch without a checkpoint worker

    def test_truthful_a_runs_never_backtrack_in_this_layout(self):
        for name in ("A3", "A4"):
            for seed in range(1, 9):
                sc = sv.scenario_ab(name, seed, T4N, checkpoints=CP_NEW, sim_cfg=hs.SimConfig(timeout_s=900.0))
                r = sc["sim"].run(sc["goal"])
                self.assertEqual(r["outcome"], "SUCCESS", (name, seed))
                self.assertEqual(r["v4"]["checkpoint"]["backtracks"], 0, (name, seed))
                self.assertTrue(all(e["result"] == "proceed" for e in r["v4"]["checkpoint"]["log"]), (name, seed))

    def test_the_checkpoints_are_fixed_and_the_random_workers_keep_the_rules_around_them(self):
        rule = sv.load_scenarios()["placement_rule"]
        first = None
        for name in ("A3", "A4"):
            for seed in range(1, 21):
                sc = sv.scenario_ab(name, seed, T4N, checkpoints=CP_NEW)
                sim, road = sc["sim"], sc["road"]
                sim._plan, sim._cp_plan = {}, {}
                sim._cp_plan = sim.plan_checkpoints()
                sim._plan = sim.plan_workers()
                pos = {k: (round(v["x"], 6), round(v["z"], 6)) for k, v in sim._cp_plan.items()}
                self.assertEqual(len(pos), 7, (name, seed))
                self.assertEqual(sorted(f"{j}>{c}" for j, c in pos), sorted(CP_NEW["branches"]))
                first = first or pos
                self.assertEqual(pos, first, (name, seed))                              # the same in every seed and in both scenarios
                workers = [q for pts in sim._plan.values() for q in pts]
                cps = [(v["x"], v["z"]) for v in sim._cp_plan.values()]
                cp_segs = [sg for (j, c), v in sim._cp_plan.items() for sg in sv.checkpoint_segments(road, j, v["next"], v["point"], (v["x"], v["z"]), rule["ask_standoff_m"], rule["reask_shift_m"])]
                drive = [sg[:4] for node, pts in sim._plan.items() for sg in sv.drivable_segments(road, node, pts, rule["ask_standoff_m"], rule["reask_shift_m"])[0]]
                roads = sv._road_segments(road, sc["spec"].physical_map)
                for q in workers:
                    self.assertTrue(all(math.dist(q, c) >= 3.0 - 1e-6 for c in cps), (name, seed, q))
                    self.assertTrue(all(sv._seg_dist(q[0], q[1], sg) >= 1.0 - 1e-4 for sg in cp_segs), (name, seed, q))
                for c in cps:
                    self.assertTrue(all(sv._seg_dist(c[0], c[1], sg) >= 1.0 - 1e-4 for sg in drive + roads), (name, seed, c))
                    self.assertTrue(all(math.dist(c, n) > 6.5 for n in (road.pos(k) for k in road.nodes)), (name, seed, c))

    def test_t0_with_the_workers_present_is_the_earlier_t0_in_the_beside_layouts(self):
        scen = sv.load_scenarios()
        for name in ("A3", "B3"):
            for seed in (21, 22, 23, 24, 25, 26):
                a = rn.one_run("T0", name, "on", seed, 900.0, CP_NEW, scen, t0_workers=True)
                b = rn.one_run("T0", name, "on", seed, 900.0, CP_NEW, scen, t0_workers=False)
                self.assertEqual((a["outcome"], a["failure_reason"], a["time_s"], a["route"]), (b["outcome"], b["failure_reason"], b["time_s"], b["route"]), (name, seed))
                self.assertGreater(a["max_people_in_view"], b["max_people_in_view"])


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

    def test_the_ignored_pointings_and_the_stopping_rule(self):
        log_ = [{"junction": "J1", "branch": "LEFT", "result": "back", "action": "ignore_undisputed"}, {"junction": "J3", "branch": "LEFT", "result": "back", "action": "keep"}]
        self.assertEqual(rt.run_metrics(self.rec(checkpoint={"log": log_, "backtracks": 0}))["ignored_undisputed"], 1)

        def row(variant, exp, setting, success, backtracks=0):
            return {"variant": variant, "experiment": exp, "setting": setting, "runs": 20, "success": success, "backtracks": backtracks}
        base = [row("T0", "B3", "on", 11), row("T0", "B4", "on", 11), row("T0", "A3", "on", 20)]
        good = {(r["experiment"], r["setting"], r["variant"]): r for r in base + [row("T4", "B3", "on", 14), row("T4", "B4", "on", 15), row("T4", "A3", "on", 20)]}
        self.assertTrue(rt.stopping_rule(good)["adopted"])
        short = {(r["experiment"], r["setting"], r["variant"]): r for r in base + [row("T4", "B3", "on", 14), row("T4", "B4", "on", 13), row("T4", "A3", "on", 20)]}
        self.assertFalse(rt.stopping_rule(short)["adopted"])                                   # B4 gains 2 < 3
        bt = {(r["experiment"], r["setting"], r["variant"]): r for r in base + [row("T4", "B3", "on", 14), row("T4", "B4", "on", 15), row("T4", "A3", "on", 20, 1)]}
        self.assertFalse(rt.stopping_rule(bt)["adopted"])                                      # an A row backtracked
        lost = {(r["experiment"], r["setting"], r["variant"]): r for r in base + [row("T4", "B3", "on", 14), row("T4", "B4", "on", 15), row("T4", "A3", "on", 19)]}
        self.assertFalse(rt.stopping_rule(lost)["adopted"])                                    # an A row lost a success

    def test_summary_and_checks(self):
        rows = [self.rec(variant="T0", seed=s, max_people_in_view=2, experiment="A3", outcome="SUCCESS") for s in (1, 2)] + \
               [self.rec(variant="T3", seed=1, experiment="A3"), self.rec(variant="T3", seed=2, experiment="A3", outcome="FAILURE", failure_reason="timeout", time_s=420.0,
                                                                          checkpoint={"log": [], "backtracks": 1})]
        s = rt.summarise(rows)
        self.assertEqual((s[("A3", "on", "T3")]["success"], s[("A3", "on", "T3")]["timeout"], s[("A3", "on", "T3")]["max_people_in_view"]), (1, 1, 5))
        c = rt.checks(s)
        self.assertEqual(c["A_success_lost_vs_T0"], {"A3 on": 1})
        self.assertEqual(c["A_backtracks"], {"A3 on": 1})


class OutOfSample(unittest.TestCase):
    """The statistics of the out-of-sample check (AUDIT.md 16.24.2)."""

    def test_wilson_and_newcombe_against_known_values(self):
        lo, hi = oos.wilson(40, 40)
        self.assertAlmostEqual(lo, 0.9122, places=3)
        self.assertAlmostEqual(hi, 1.0, places=6)
        self.assertEqual(oos.wilson(0, 0), (0.0, 1.0))
        d, lo, hi = oos.newcombe(56, 70, 48, 80)                      # Newcombe (1998), example 1, method 10: 0.2000 (0.0524, 0.3339)
        self.assertAlmostEqual(d, 0.2, places=6)
        self.assertAlmostEqual(lo, 0.0524, places=3)
        self.assertAlmostEqual(hi, 0.3339, places=3)

    def test_percentile_is_numpys_default(self):
        self.assertAlmostEqual(oos.percentile([1, 2, 3, 4, 5], 0.95), 4.8)
        self.assertAlmostEqual(oos.percentile([5, 1, 3], 0.5), 3.0)
        self.assertIsNone(oos.percentile([], 0.95))
        self.assertEqual(oos.percentile([7.0], 0.95), 7.0)

    def rows(self, exp, setting, variant, n_ok, n=40, t_ok=100.0, seed0=21, backtracks=0):
        out = []
        for k in range(n):
            ok = k < n_ok
            out.append({"variant": variant, "experiment": exp, "setting": setting, "seed": seed0 + k, "outcome": "SUCCESS" if ok else "FAILURE",
                        "failure_reason": "none" if ok else "wrong_goal", "time_s": t_ok if ok else 50.0, "max_people_in_view": 5 if variant == "T4" else 2, "go": [],
                        "gestures": [], "checkpoint": {"log": [], "backtracks": backtracks if k == 0 else 0}})
        return out

    def test_the_pass_bar_is_15_points_in_b3_on_and_b4_on_and_the_a_rows(self):
        base = self.rows("A3", "on", "T0", 40) + self.rows("B3", "on", "T0", 20) + self.rows("B4", "on", "T0", 20)
        ok = oos.evaluate(base + self.rows("A3", "on", "T4", 40) + self.rows("B3", "on", "T4", 26) + self.rows("B4", "on", "T4", 26))        # +15.0 pp: passes
        self.assertTrue(ok["bar"]["adopted"])
        self.assertAlmostEqual(ok["bar"]["B_on_gain_pp"]["B3"], 15.0)
        short = oos.evaluate(base + self.rows("A3", "on", "T4", 40) + self.rows("B3", "on", "T4", 26) + self.rows("B4", "on", "T4", 25))      # B4 +12.5 pp: fails
        self.assertFalse(short["bar"]["adopted"])
        lost = oos.evaluate(base + self.rows("A3", "on", "T4", 39) + self.rows("B3", "on", "T4", 30) + self.rows("B4", "on", "T4", 30))
        self.assertEqual(lost["bar"]["A_success_lost_vs_T0"], {"A3 on": 1})
        self.assertFalse(lost["bar"]["adopted"])
        bt = oos.evaluate(base + self.rows("A3", "on", "T4", 40, backtracks=1) + self.rows("B3", "on", "T4", 30) + self.rows("B4", "on", "T4", 30))
        self.assertEqual(bt["bar"]["A_backtracks"], {"A3 on": 1})
        self.assertFalse(bt["bar"]["adopted"])

    def test_paired_counts_and_the_row_statistics(self):
        t0, t4 = self.rows("B3", "on", "T0", 20), self.rows("B3", "on", "T4", 26)
        self.assertEqual(oos.paired(t0, t4), {"gained": 6, "lost": 0})
        s = oos.row_stats(t4)
        self.assertEqual((s["success"], s["runs"], s["wrong_goal"], s["median_s"], s["max_s"], s["rule_timeout_s"]), (26, 40, 14, 100.0, 100.0, 270.0))
        self.assertAlmostEqual(s["mean_all_s"], (26 * 100.0 + 14 * 50.0) / 40)

    def test_the_total_time_uses_the_13_final_settings_and_a2_left_takes_the_a2_row(self):
        stats = {(e, st, v): {"mean_all_s": 10.0} for e in ("A1", "A2", "A3", "A4", "B1", "B2", "B3", "B4") for st in ("off", "on") for v in ("T0", "T4")}
        stats[("A2", "on", "T4")] = {"mean_all_s": 30.0}
        t = oos.total_time(stats, "T4")
        self.assertEqual((t["settings"], t["runs"]), (13, 260))
        self.assertEqual(t["per_setting_mean_s"]["A2_left"], 30.0)
        self.assertEqual(t["per_setting_mean_s"]["A2_right"], 30.0)
        self.assertAlmostEqual(t["total_s"], 20 * (11 * 10.0 + 2 * 30.0))


if __name__ == "__main__":
    unittest.main()
