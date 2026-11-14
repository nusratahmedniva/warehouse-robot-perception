"""Experiments A and B (AUDIT.md section 16): the lie model of the simulator, the three lie-detection rules of the v4 controller
(second opinion, reject impossible, backtrack), the scenarios A1-A4 / B1-B4, the placements, the obstacle detour and the claim
that with every switch off the behaviour is that of the commit this work started from (a golden record made on 808f028).

Simulator tests: the simulator's perception is the reader's OUTPUT (two depth readings of a pointing arm, mirror images about the
image plane), so a lie is read as a valid branch whenever its mirror image lands on one. The rule tests therefore place the people
('fixed' layout) so that the mirror lands where the test needs it: a person due north of a node (camera yaw 0) reads LEFT / RIGHT
unambiguously (the mirror of a direction d is 2 * camera_yaw + 180 - d)."""

import json
import math
import random
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))

import commander_v4 as cm  # noqa: E402
import gesture_data as gd  # noqa: E402
import hri_trials as ht  # noqa: E402
import golden_sim_v4 as golden  # noqa: E402
import hri_control as hc  # noqa: E402
import hri_control_v4 as hv  # noqa: E402
import hri_sim_v4 as sv  # noqa: E402
from bridge import protocol as P  # noqa: E402
from hri_sim import SimConfig  # noqa: E402

OFF, ON = sv.DETECTION_OFF, sv.DETECTION_ON
REJECT = {"second_opinion": False, "reject_impossible": True, "backtrack": False}
BACKTRACK = {"second_opinion": False, "reject_impossible": True, "backtrack": True}
SECOND = {"second_opinion": True, "reject_impossible": False, "backtrack": False}

# One person due north of every node of the v4 map (camera yaw 0 at the ask, so LEFT and RIGHT read unambiguously); at J3 one to the
# north-east (the mirror of LEFT lands on the arrival road and is dropped).
NORTH = {"kind": "fixed", "points": {"A": [[6.25, -17.5]], "J1": [[6.25, 2.5]], "J2": [[-6.25, 2.5]], "J3": [[20.55, 1.8]],
                                      "J4": [[-18.75, 2.5]]}}
# J1 person north-west of the node (camera yaw -45): the mirror of LEFT (-90) is 2 * (-45) + 270 = 180 = the arrival road, the other reading is LEFT itself
MIRROR_AT_J1 = {"kind": "fixed", "points": {**NORTH["points"], "J1": [[6.25 - 2.5 * math.sin(math.radians(45)), 2.5 * math.cos(math.radians(45))]]}}
# J1 person due east of the node (camera yaw 90): the mirror of BACK is BACK, both candidates are the arrival road.
EAST_AT_J1 = {"kind": "fixed", "points": {**NORTH["points"], "J1": [[8.75, 0.0]]}}


# J3 person due north (camera yaw 0): FORWARD (east) and its mirror both fall on the wall side, so a FORWARD lie is read as no_branch
WALL_AT_J3 = {"kind": "fixed", "points": {**NORTH["points"], "J3": [[18.75, 2.5], [17.0, 3.5]]}}


def run(name, goal, script=None, detection=None, layout=None, seed=1, people=None, p=None, xcheck=False):
    """One scenario run; xcheck = the simulator's perfect MediaPipe hand cross-check as the tie-break (an ambiguous honest gesture
    then reads as shown whatever the viewpoint; the rule tests are about the rules, not about the mirror ambiguity)."""
    sc = sv.scenario_ab(name, seed, detection)
    if xcheck:
        sc["sim"].g.crosscheck_accuracy = 1.0
        sc["sim"].c.v4["dialog"]["use_hand_crosscheck_as_tiebreak"] = True
    if script is not None:
        sc["spec"].lie_script = script
    if layout is not None:
        sc["spec"].layout = layout
    if people is not None:                                   # an explicit head count replaces the per-node counts of the config (J1 has 3, 16.12)
        sc["spec"].layout["people"] = people
        sc["spec"].layout.pop("people_by_node", None)
    if p is not None:
        sc["spec"].lie_probability = p
    return sc["sim"].run(goal or sc["goal"])


def events(r, *names):
    return [d for d in r["v4"]["decisions"] if not names or d["event"] in names]


class SwitchesOffUnchanged(unittest.TestCase):
    """Every switch false = the behaviour of commit 808f028, on 14 whole simulated trials (golden_sim_v4.py, run there)."""

    def test_golden_cases_are_identical(self):
        base = json.loads((ROOT / "tests/golden_sim_v4_baseline.json").read_text(encoding="utf-8"))
        self.assertEqual(base["commit"], "808f028")
        now = golden.all_cases()
        self.assertEqual(sorted(now), sorted(base["cases"]))
        for name, expected in base["cases"].items():
            for key, value in expected.items():
                self.assertEqual(now[name][key], value, f"{name}: {key}")

    def test_the_three_control_files_ship_with_every_switch_off(self):
        for f in ("control.json", "control_zoom_on.json", "control_zoom_off.json"):
            ld = json.loads((ROOT / "configs/v4" / f).read_text(encoding="utf-8"))["lie_detection"]
            self.assertEqual([ld[k] for k in ("second_opinion", "reject_impossible", "backtrack")], [False] * 3, f)
            self.assertEqual(ld["max_opinions"], 3)

    def test_missing_block_means_all_off(self):
        base, v4 = hv.load_control()
        v4.pop("lie_detection")
        c = hv.ControllerV4(base, v4, cm.load_config(), hv.load_roadmap())
        self.assertEqual([c.ld[k] for k in ("second_opinion", "reject_impossible", "backtrack")], [False] * 3)

    def test_backtrack_needs_reject_impossible(self):
        base, v4 = hv.load_control()
        v4["lie_detection"] = {"backtrack": True, "reject_impossible": False}
        with self.assertRaisesRegex(ValueError, "reject_impossible"):
            hv.ControllerV4(base, v4, cm.load_config(), hv.load_roadmap())

    def test_decisions_are_logged_with_the_switches_off_too(self):
        r = run("A3", "E2", detection=OFF)
        ev = events(r)
        self.assertTrue(ev)
        for d in ev:
            self.assertEqual({"t", "node", "event", "reason", "serial"} <= set(d), True)
            self.assertTrue(d["reason"])
        self.assertEqual({d["event"] for d in ev} <= {"answer_accepted", "go", "second_view"}, True)
        json.dumps(r["v4"])                                              # serialisable


class TruthField(unittest.TestCase):
    ROW = {"time_s": 1.0, "worker_id": 1, "look": "l", "x": 0.0, "z": 0.0, "true_command": "POINT", "point_angle_deg": 10.0,
           "arm": "right", "phase": "holding", "is_commander": True}

    def parse(self, **extra):
        return gd.parse_truth([json.dumps({**self.ROW, **extra})])[0]

    def test_optional_and_typed(self):
        self.assertIsNone(self.parse().gesture_truthful)
        self.assertIs(self.parse(gesture_truthful=False).gesture_truthful, False)
        self.assertIs(self.parse(gesture_truthful=True).gesture_truthful, True)
        for bad in ("false", 0, 1, None.__class__):
            if bad is None.__class__:
                continue
            with self.assertRaises(gd.TruthError):
                self.parse(gesture_truthful=bad)

    def test_unity_may_not_send_it(self):
        self.assertIn("gesture_truthful", P.TRUTH_KEYS)
        self.assertIn("gesture_truthful", P.FORBIDDEN_KEYS_V3)
        self.assertNotIn("gesture_truthful", P.FORBIDDEN_KEYS)            # version 2 unchanged

    def test_simulator_rows_carry_it_and_parse(self):
        r = run("A3", "E2", p=1.0, detection=OFF)
        rows = gd.parse_truth([json.dumps(x) for x in r["truth_rows"]])
        self.assertTrue(rows and all(x.gesture_truthful is not None for x in rows))
        self.assertTrue(any(x.gesture_truthful is False for x in rows))
        self.assertTrue(all(x.gesture_truthful for x in rows if x.true_command == "NONE"))


class LieModel(unittest.TestCase):
    def test_no_lies_at_probability_zero(self):
        for seed in (1, 2):
            r = run("A3", None, seed=seed, detection=OFF)
            self.assertTrue(r["gestures"] and all(g["truthful"] and g["shown"] == g["correct"] for g in r["gestures"]))
            self.assertTrue(all(x["gesture_truthful"] for x in r["truth_rows"]))

    def test_every_gesture_lies_at_probability_one_and_never_shows_the_truth(self):
        r = run("A3", "E2", p=1.0, detection=OFF)
        self.assertTrue(r["gestures"])
        for g in r["gestures"]:
            self.assertFalse(g["truthful"])
            self.assertNotEqual(g["shown"], g["correct"])
            self.assertIn(g["shown"], ("LEFT", "FORWARD", "RIGHT", "BACK"))
        lying_rows = {x["worker_id"] for x in r["truth_rows"] if not x["gesture_truthful"]}
        self.assertTrue(lying_rows)

    def test_shown_direction_is_uniform_over_the_other_three(self):
        seen = set()
        for seed in range(1, 40):                                         # the compass model of 16.2 (a Set A scenario has no lie_directions key)
            for g in run("A3", "E2", p=1.0, seed=seed, detection=OFF, layout=NORTH)["gestures"]:
                if g["correct"] == "FORWARD" and g["node"] == "A":       # A has one branch: the other three directions, all impossible
                    seen.add(g["shown"])
        self.assertEqual(seen, {"LEFT", "RIGHT", "BACK"})

    def test_a_lie_is_a_lie_in_the_truth_rows_and_the_gesture_log_alike(self):
        r = run("B3" if False else "A3", "E2", p=0.5, seed=4, detection=OFF)
        lies = [g for g in r["gestures"] if not g["truthful"]]
        clips = gd.build_clips(gd.parse_truth([json.dumps(x) for x in r["truth_rows"]]))
        lying_clips = []
        rows = {x.line: x for x in gd.parse_truth([json.dumps(x) for x in r["truth_rows"]])}
        for c in clips:
            flags = {rows[line].gesture_truthful for line in c.row_lines}
            self.assertEqual(len(flags), 1)                              # one gesture, one flag
            if flags == {False}:
                lying_clips.append(c)
        self.assertEqual(len(lying_clips), len(lies))

    def test_the_generator_of_a_worker_is_seeded_by_run_node_and_worker(self):
        sc = sv.scenario_ab("B3", 7, OFF)
        sim = sc["sim"]
        a = [sim._worker_rng("J1", 2).random() for _ in range(3)]
        again = random.Random("7|J1|2")
        self.assertEqual(a, [again.random() for _ in range(3)])
        self.assertNotEqual(sim._worker_rng("J1", 1).random(), sim._worker_rng("J1", 2).random())

    def test_same_seed_same_lies_and_different_seed_not(self):
        a = run("B3", None, seed=5, detection=OFF)
        b = run("B3", None, seed=5, detection=OFF)
        c = run("B3", None, seed=6, detection=OFF)
        self.assertEqual((a["gestures"], a["trace"], a["time_s"]), (b["gestures"], b["trace"], b["time_s"]))
        self.assertNotEqual(a["gestures"], c["gestures"])

    def test_about_a_fifth_of_the_gestures_lie_in_set_b(self):
        n = lies = 0
        for seed in range(1, 21):
            g = run("B3", None, seed=seed, detection=OFF)["gestures"]
            n, lies = n + len(g), lies + sum(not x["truthful"] for x in g)
        self.assertGreater(n, 40)
        self.assertTrue(0.08 < lies / n < 0.35, lies / n)

    def test_a_worker_who_knows_b_but_cannot_lead_there_points_back(self):
        r = run("A3", "E3", [None, "LEFT"], OFF, NORTH)                   # J1 lie LEFT -> J2, no way to E3 from there
        g = [x for x in r["gestures"] if x["node"] == "J2"]
        self.assertTrue(g and all(x["correct"] == "BACK" for x in g))


class Placement(unittest.TestCase):
    def setUp(self):
        self.road = hc.Roadmap(hc.load_json("configs/v4/roadmap.json"))

    def test_beside_the_road_one_on_each_side_before_the_node(self):
        pts = sv.place_beside(self.road, "J1", 2, 2.0, 3.0)
        self.assertEqual([tuple(round(v, 6) for v in p) for p in pts], [(8.25, -3.0), (4.25, -3.0)])
        a = sv.place_beside(self.road, "A", 2, 2.0, 3.0)                  # at the start node: behind A, along the start heading
        self.assertEqual([tuple(round(v, 6) for v in p) for p in a], [(8.25, -23.0), (4.25, -23.0)])
        j2 = sv.place_beside(self.road, "J2", 2, 2.0, 3.0)                # arrival heading west: 3 m east of J2, right = north
        self.assertEqual([tuple(round(v, 6) for v in p) for p in j2], [(-3.25, 2.0), (-3.25, -2.0)])

    def test_random_placement_keeps_its_rules_and_is_seeded(self):
        segs = sv._road_segments(self.road)
        for node in ("J1", "J2", "J3", "J4", "A"):
            for seed in range(1, 15):
                pts = sv.place_random(self.road, node, 2, 3.0, 1.0, 1.0, seed)
                nx, nz = self.road.pos(node)
                for x, z in pts:
                    self.assertTrue(abs(x - nx) <= 3.0 and abs(z - nz) <= 3.0)
                    self.assertTrue(all(sv._seg_dist(x, z, sg) >= 1.0 for sg in segs))
                self.assertGreaterEqual(math.dist(*pts), 1.0)
                self.assertEqual(pts, sv.place_random(self.road, node, 2, 3.0, 1.0, 1.0, seed))
        self.assertNotEqual(sv.place_random(self.road, "J1", 2, 3.0, 1.0, 1.0, 1), sv.place_random(self.road, "J1", 2, 3.0, 1.0, 1.0, 2))

    def test_an_impossible_placement_is_refused(self):
        with self.assertRaises(ValueError):
            sv.place_random(self.road, "J1", 5, 1.0, 1.0, 1.0, 1)


class PlacementRule(unittest.TestCase):
    """AUDIT.md 16.11: any two workers at least 3.0 m apart and every worker at least 3.0 m from every turning point of the path."""

    def test_the_rule_is_in_the_frozen_scenarios_config(self):
        r = sv.load_scenarios()["placement_rule"]
        self.assertEqual((r["min_worker_separation_m"], r["min_turning_point_m"]), (3.0, 3.0))
        self.assertIn("UNITY MUST USE THE SAME RULE", r["why"])
        self.assertNotIn("min_sep_m", sv.load_scenarios()["scenarios"]["4"]["layout"])

    def test_every_scene_of_every_scenario_seed_and_node_obeys_it(self):
        for name in ("A1", "A2", "A3", "A4"):
            for seed in range(1, 21):
                sc = sv.scenario_ab(name, seed)
                for node, v in sc["road"].nodes.items():
                    if v["kind"] not in ("start", "junction"):
                        continue
                    scene = sc["sim"]._scene_at(node)
                    pts = [(p.x, p.z) for p in scene.people]
                    sv.check_placement(sc["road"], node, pts, 3.0, 3.0)           # raises if not
                    for i, a in enumerate(pts):
                        for b in pts[i + 1:]:
                            self.assertGreaterEqual(math.dist(a, b), 3.0 - 1e-9)

    def test_a_violation_is_refused_with_its_reason(self):
        road = hc.Roadmap(hc.load_json("configs/v4/roadmap.json"))
        with self.assertRaisesRegex(ValueError, "2 are|workers 1 and 2 are 2.00 m apart"):
            sv.check_placement(road, "J1", [(8.0, -3.0), (10.0, -3.0)], 3.0, 3.0)
        with self.assertRaisesRegex(ValueError, "worker 1 is 2.00 m from a turning point"):
            sv.check_placement(road, "J1", [(8.25, 0.0)], 3.0, 3.0)
        sv.check_placement(road, "J1", sv.place_beside(road, "J1", 2, 2.0, 3.0), 3.0, 3.0)

    def test_the_simulator_refuses_a_layout_that_breaks_the_rule_but_not_a_fixed_test_layout(self):
        sc = sv.scenario_ab("A3", 1)
        sc["spec"].layout = {"kind": "beside", "people": 2, "lateral_m": 0.5, "before_m": 3.0}      # 1.0 m apart
        with self.assertRaisesRegex(ValueError, "apart"):
            sc["sim"].run("E1")
        r = run("A3", "E1", None, OFF, NORTH)                      # fixed layouts (tests) are exempt
        self.assertEqual(r["outcome"], "SUCCESS")

    def test_random_placement_with_the_rule_is_seeded_and_keeps_its_older_rules_too(self):
        road = hc.Roadmap(hc.load_json("configs/v4/roadmap.json"))
        segs = sv._road_segments(road)
        for node in ("A", "J1", "J2", "J3", "J4"):
            for seed in range(1, 30):
                pts = sv.place_random(road, node, 2, 3.0, 1.0, 3.0, seed, 3.0)
                self.assertEqual(pts, sv.place_random(road, node, 2, 3.0, 1.0, 3.0, seed, 3.0))
                self.assertGreaterEqual(math.dist(*pts), 3.0)
                for x, z in pts:
                    self.assertTrue(all(sv._seg_dist(x, z, sg) >= 1.0 for sg in segs))
                    self.assertTrue(all(math.hypot(x - tx, z - tz) >= 3.0 for tx, tz in sv.turning_points(road)))


class Detour(unittest.TestCase):
    def test_straight_when_nobody_is_near(self):
        self.assertEqual(sv.detour_corners(0, 0, (0, 10), [(5.0, 5.0)], 0.9), [(0, 0), (0, 10)])

    def test_goes_around_a_person_on_the_route_and_clears_them(self):
        pts = sv.detour_corners(0, 0, (0, 10), [(0.1, 5.0)], 0.9)
        self.assertGreater(len(pts), 2)
        self.assertEqual((pts[0], pts[-1]), ((0, 0), (0, 10)))
        for a, b in zip(pts, pts[1:]):
            self.assertGreaterEqual(sv._seg_dist(0.1, 5.0, (*a, *b)), 0.9 - 1e-9)

    def test_a_person_behind_the_start_or_beyond_the_end_is_not_an_obstacle(self):
        self.assertEqual(len(sv.detour_corners(0, 0, (0, 10), [(0.0, -1.0), (0.0, 11.0)], 0.9)), 2)

    def test_two_people_on_the_route(self):
        pts = sv.detour_corners(0, 0, (0, 20), [(0.0, 5.0), (0.2, 12.0)], 0.9)
        for a, b in zip(pts, pts[1:]):
            for o in ((0.0, 5.0), (0.2, 12.0)):
                self.assertGreaterEqual(sv._seg_dist(*o, (*a, *b)), 0.9 - 1e-9)

    def test_the_clearance_is_the_safety_corridor_plus_half_the_robot(self):
        sc = sv.scenario_ab("A3", 1)
        self.assertAlmostEqual(sc["spec"].avoid_people_m, 0.6 + 0.3)


class RuleB_RejectImpossible(unittest.TestCase):
    def test_a_direction_with_no_branch_is_rejected_and_asked_again(self):
        # a person due north of J3 (arrival from the west): FORWARD points at a wall; the second ask is truthful
        script = [None, None, "FORWARD"]
        on = run("A3", "E3", script, REJECT, WALL_AT_J3, xcheck=True)
        rej = events(on, "answer_rejected")
        self.assertEqual([d["reason"] for d in rej], ["no_branch"])
        self.assertEqual((on["outcome"], on["v4"]["route"]), ("SUCCESS", ["A", "J1", "J3", "E3"]))
        self.assertEqual([j["asks"] for j in on["junctions"]], [1, 1, 2])
        self.assertIn("reject:no_branch", " ".join(on["trace"]))

    def test_off_it_is_not_logged_and_the_ask_runs_to_its_window(self):
        off = run("A3", "E3", [None, None, "FORWARD"], OFF, WALL_AT_J3, xcheck=True)
        self.assertEqual(events(off, "answer_rejected"), [])
        on = run("A3", "E3", [None, None, "FORWARD"], REJECT, WALL_AT_J3, xcheck=True)
        self.assertEqual((off["outcome"], on["outcome"]), ("SUCCESS", "SUCCESS"))
        self.assertLess(on["time_s"], off["time_s"])                       # asking again at once beats waiting out the 5 s window

    def test_the_arrival_road_is_rejected_with_that_reason(self):
        r = run("A3", "E3", [None, "LEFT"], REJECT, NORTH)               # J1 lie LEFT -> J2; J2's worker points BACK
        self.assertEqual({d["reason"] for d in events(r, "answer_rejected")}, {"arrival"})
        self.assertEqual(len(events(r, "answer_rejected")), 2)             # one per ask, two asks

    def test_a_dead_end_branch_is_rejected(self):
        road = {"start": "A", "nodes": {"A": {"x": 0.0, "z": 0.0, "kind": "start", "start_yaw_deg": 0.0},
                                        "J": {"x": 0.0, "z": 12.0, "kind": "junction", "arrive_from": "A"},
                                        "D": {"x": 0.0, "z": 24.0, "kind": "dead_end"},
                                        "E": {"x": 12.0, "z": 12.0, "kind": "endpoint"}},
                "branches": {"A": {"FORWARD": "J"}, "J": {"FORWARD": "D", "RIGHT": "E"}},
                "worker_stand": {"corner_offset_m": 2.5}}
        layout = {"kind": "fixed", "points": {"A": [[0.0, 2.5]], "J": [[0.0, 14.5]]}}
        for det, reason in ((REJECT, "dead_end"), (OFF, None)):
            base, v4 = hv.load_control()
            v4["lie_detection"] = {**v4["lie_detection"], **det}
            ctrl = hv.ControllerV4(base, v4, cm.load_config(), hc.Roadmap(road))
            spec = sv.SceneSpec(proceed_forward=True, anyone_commands=True, point_back_when_lost=True, record_truthful=True,
                                layout=layout, lie_script=[None, "FORWARD"], avoid_people_m=0.9)
            r = sv.SimulatorV4(ctrl, SimConfig(timeout_s=270.0), sv.GestureSimConfig(), spec, 1).run("E")
            if reason:
                self.assertEqual([d["reason"] for d in events(r, "answer_rejected")][:1], [reason])
                self.assertEqual(r["outcome"], "SUCCESS")
            else:
                self.assertEqual((r["outcome"], r["failure_reason"]), ("FAILURE", "aborted"))
                self.assertIn("dead end at D", r["abort_reason"])

    def test_an_answer_already_tried_is_not_an_answer(self):
        base, v4 = hv.load_control()
        c = hv.ControllerV4(base, v4, cm.load_config(), hv.load_roadmap())
        c.node, c.excluded = "J1", {"LEFT"}
        self.assertEqual(c._rejection("LEFT", None, "")[0], "already_tried")
        self.assertIsNone(c._rejection("RIGHT", None, ""))
        c.excluded = set()
        self.assertIsNone(c._rejection("LEFT", None, ""))                    # no exclusion, switch off: nothing is rejected


class RuleB_ArrivalMirror(unittest.TestCase):
    """AUDIT.md 16.11 (decided 2026-11-13): under reject_impossible a reading whose OTHER depth reading is the arrival road is ambiguous
    (the second view decides), because the two readings are mirror images and a worker pointing back along the arrival road can be read
    as the branch his mirror image lands on."""

    def test_resolve_point_unit(self):
        from types import SimpleNamespace
        # at J2 (arrival from the east): RIGHT = north (0), FORWARD = west (-90), arrival = east (90)
        dirs, arrival = hv.branch_directions(hv.load_roadmap(), "J2")
        point = SimpleNamespace(world_deg={"away": 0.0, "toward": 90.0}, crosscheck={})
        plain = hv.resolve_point(point, dirs, arrival, 0.0, 30.0)
        self.assertEqual((plain.command, plain.ambiguous), ("RIGHT", False))                 # the old behaviour: the mirror is simply dropped
        fixed = hv.resolve_point(point, dirs, arrival, 0.0, 30.0, False, True)
        self.assertEqual((fixed.command, fixed.ambiguous), (None, True))
        self.assertIn("arrival road", fixed.why)
        self.assertEqual({c["target"] for c in fixed.candidates}, {"RIGHT", "ARRIVAL"})
        # a reading with no arrival-road candidate is not touched
        clean = SimpleNamespace(world_deg={"away": 0.0, "toward": None}, crosscheck={})
        self.assertEqual(hv.resolve_point(clean, dirs, arrival, 0.0, 30.0, False, True).command, "RIGHT")
        # a reading that is the arrival road itself stays what it was (dropped, no candidate left): not ambiguous
        back = SimpleNamespace(world_deg={"away": 90.0, "toward": 90.0}, crosscheck={})
        self.assertEqual((hv.resolve_point(back, dirs, arrival, 0.0, 30.0, False, True).command, ), (None,))

    def test_the_switch_off_changes_nothing_and_the_switch_on_catches_a_lie_whose_mirror_is_the_arrival_road(self):
        off = run("A3", "E3", [None, "LEFT"], OFF, MIRROR_AT_J1)        # J1 lie LEFT, read as LEFT: the robot follows it to J2, then E2
        self.assertEqual(off["v4"]["route"][:3], ["A", "J1", "J2"])         # the lie was followed to J2 (where B cannot be reached; the worker there points back)
        self.assertEqual(off["outcome"], "FAILURE")
        on = run("A3", "E3", [None, "LEFT"], REJECT, MIRROR_AT_J1)
        self.assertEqual(on["v4"]["route"], ["A", "J1"])                 # not followed
        self.assertEqual((on["outcome"], on["failure_reason"]), ("FAILURE", "aborted"))     # fail safe: unclear after two asks
        sv_events = events(on, "second_view")
        self.assertEqual(len(sv_events), 1)
        self.assertEqual(sv_events[0]["reason"], "ambiguous: one of the two readings is the arrival road")

    def test_an_honest_gesture_still_gets_through_via_the_second_view(self):
        for seed in (1, 2, 3):
            r = sv.run_scenario("A3", seed, REJECT)
            self.assertEqual((r["outcome"], r["failure_reason"]), ("SUCCESS", "none"), seed)

    def test_the_second_view_is_logged_with_its_reason_also_for_two_branches(self):
        r = run("A3", "E3", None, OFF, seed=1)
        for d in events(r, "second_view"):
            self.assertTrue(d["reason"].startswith("ambiguous"))


class RuleA_SecondOpinion(unittest.TestCase):
    def test_two_people_who_agree(self):
        r = run("A3", "E2", None, SECOND)
        self.assertEqual(r["outcome"], "SUCCESS")
        go = events(r, "go")
        self.assertTrue(go and all(d["reason"] == "2 of 2 answers agree" for d in go))
        self.assertEqual(len(events(r, "ask_next")), len(go))             # one more person per node
        self.assertEqual([j["opinion"] for j in r["junctions"] if j["junction"] == "J1"], [1, 2])
        self.assertEqual(len([j for j in r["junctions"] if j["junction"] == "J1"]), 2)        # two dialogs, two records

    def test_first_lies_second_truthful_nobody_else_so_the_first_is_asked_again(self):
        r = run("A3", "E2", [None, None, "RIGHT"], SECOND, xcheck=True, people=2)  # J1: p1 lies RIGHT (valid branch), goal is LEFT; two people (the tie rule)
        self.assertEqual((r["outcome"], r["v4"]["route"]), ("SUCCESS", ["A", "J1", "J2", "E2"]))
        why = [d["reason"] for d in events(r, "ask_next")]
        self.assertTrue(any("ask the first person again" in w for w in why), why)
        self.assertIn("2 of 3 answers agree", [d["reason"] for d in events(r, "go")])

    def test_the_first_person_counts_twice_so_a_persistent_first_liar_can_win(self):
        r = run("A3", "E2", [None, None, "RIGHT", None, "RIGHT"], SECOND, xcheck=True, people=2)
        self.assertEqual(r["outcome"], "FAILURE")
        j1 = [d for d in events(r, "go") if d["node"] == "J1"][0]
        self.assertEqual((j1["branch"], j1["reason"]), ("RIGHT", "2 of 3 answers agree"))
        self.assertEqual([v["branch"] for v in j1["votes"]], ["RIGHT", "LEFT", "RIGHT"])

    def test_three_different_answers_are_unclear_and_abort(self):
        r = run("A3", "E2", [None, None, "RIGHT", None, "FORWARD"], SECOND, xcheck=True, people=2)
        self.assertEqual((r["outcome"], r["failure_reason"]), ("FAILURE", "aborted"))
        self.assertIn("no majority among 3 answers", r["abort_reason"])

    def test_with_three_people_the_third_decides(self):
        r = run("A3", "E2", [None, None, None, "RIGHT"], SECOND, people=3, xcheck=True)   # J1: p1 truthful, p2 lies, p3 truthful
        self.assertEqual(r["outcome"], "SUCCESS")
        j1 = [d for d in events(r, "go") if d["node"] == "J1"][0]
        self.assertEqual((j1["branch"], j1["reason"]), ("LEFT", "2 of 3 answers agree"))
        self.assertEqual(len(j1["votes"]), 3)
        self.assertEqual(len({v["person_360"] for v in j1["votes"]}), 3)    # three different people, nobody asked twice

    def test_one_person_only_is_asked_once(self):
        r = run("A3", "E2", None, SECOND, people=1)
        self.assertEqual(r["outcome"], "SUCCESS")
        self.assertEqual({d["reason"] for d in events(r, "go")}, {"one person only"})
        self.assertEqual(events(r, "ask_next"), [])

    def test_rejected_answers_are_not_votes_and_the_next_person_is_asked(self):
        both = {"second_opinion": True, "reject_impossible": True, "backtrack": False}
        # J3, first person: FORWARD (a wall) at both asks -> rejected twice, no vote; the second person is asked and answers
        r = run("A3", "E3", [None, None, "FORWARD", "FORWARD"], both, WALL_AT_J3, xcheck=True)
        self.assertEqual([d["reason"] for d in events(r, "answer_rejected")], ["no_branch", "no_branch"])
        j3 = [d for d in events(r, "go") if d["node"] == "J3"][0]
        self.assertEqual(j3["reason"], "one usable answer, nobody else to ask")
        self.assertEqual(len(j3["votes"]), 1)
        self.assertEqual((r["outcome"], r["v4"]["route"][-1]), ("SUCCESS", "E3"))
        self.assertEqual([j["result"] for j in r["junctions"] if j["junction"] == "J3"], ["no_answer", "accepted"])

    def test_nobody_else_to_ask_after_two_rejections_is_an_abort_without_backtrack(self):
        both = {"second_opinion": True, "reject_impossible": True, "backtrack": False}
        one = {"kind": "fixed", "points": {**NORTH["points"], "J3": [[18.75, 2.5]]}}         # one person only at J3
        r = run("A3", "E3", [None, None, "FORWARD", "FORWARD"], both, one, xcheck=True)
        self.assertEqual(len(events(r, "answer_rejected")), 2)
        self.assertEqual((r["outcome"], r["failure_reason"]), ("FAILURE", "aborted"))

    def test_the_approach_point_stays_clear_of_the_other_people(self):
        base, v4 = hv.load_control()
        c = hv.ControllerV4(base, v4, cm.load_config(), hv.load_roadmap())
        inp = hv.TickInputV4(time_s=0.0, x=0.0, z=0.0, yaw_deg=0.0,
                             people=[{"x": 0.0, "z": 5.0, "distance_m": 5.0, "bearing_deg": 0.0, "track_id": 1},
                                     {"x": 0.0, "z": 3.0, "distance_m": 3.0, "bearing_deg": 0.0, "track_id": 2}], people_time_s=0.0)
        pt, turned = c._clear_approach_point(inp, inp.people[0])        # the straight spot (0, 3) is on top of person 2
        self.assertNotEqual(turned, 0.0)
        self.assertGreaterEqual(math.hypot(pt[0] - 0.0, pt[1] - 3.0), 2 * c.s["corridor_half_width_m"])
        self.assertAlmostEqual(math.hypot(pt[0] - 0.0, pt[1] - 5.0), c.g["approach_distance_m"])


class RuleC_Backtrack(unittest.TestCase):
    def test_return_to_the_last_junction_and_ask_again_with_the_failed_branch_excluded(self):
        r = run("A3", "E3", [None, "LEFT"], BACKTRACK, NORTH)
        self.assertEqual((r["outcome"], r["v4"]["route"]), ("SUCCESS", ["A", "J1", "J2", "J1", "J3", "E3"]))
        bt = events(r, "backtrack")
        self.assertEqual(len(bt), 1)
        self.assertEqual((bt[0]["node"], bt[0]["to"], bt[0]["failed_branch"]), ("J2", "J1", "LEFT"))
        self.assertIn("arrival", bt[0]["reason"])
        again = events(r, "ask_again_after_backtrack")
        self.assertEqual(again[0]["excluded"], ["LEFT"])
        self.assertEqual([j["result"] for j in r["junctions"] if j["junction"] == "J2"], ["backtrack"])
        self.assertIn("backtrack", " ".join(r["trace"]))

    def test_with_one_untried_branch_it_is_taken_without_a_question(self):
        r = run("A3", "E2", [None, None, "FORWARD"], BACKTRACK, NORTH)   # J2 lie FORWARD -> J4; back at J2 only RIGHT is untried
        self.assertEqual((r["outcome"], r["v4"]["route"]), ("SUCCESS", ["A", "J1", "J2", "J4", "J2", "E2"]))
        self.assertEqual(len(events(r, "take_other_branch")), 1)
        self.assertEqual([j["junction"] for j in r["junctions"]].count("J2"), 2 - 1)    # J2 was asked once; the return asked nobody

    def test_off_the_robot_follows_the_lie_to_a_dead_road_and_aborts(self):
        r = run("A3", "E3", [None, "LEFT"], OFF, NORTH)
        self.assertEqual((r["outcome"], r["failure_reason"]), ("FAILURE", "aborted"))
        self.assertEqual(events(r, "backtrack"), [])

    def test_reject_alone_does_not_backtrack(self):
        r = run("A3", "E3", [None, "LEFT"], REJECT, NORTH)
        self.assertEqual((r["outcome"], r["failure_reason"]), ("FAILURE", "aborted"))
        self.assertEqual(events(r, "backtrack"), [])

    def test_no_other_branch_at_the_last_junction_aborts_with_the_reason(self):
        r = run("A3", "E3", [None, "BACK", "BACK"], BACKTRACK, EAST_AT_J1)   # J1 itself: every answer impossible, the last decision was A
        self.assertEqual((r["outcome"], r["failure_reason"]), ("FAILURE", "aborted"))
        blocked = events(r, "backtrack_blocked")
        self.assertEqual(len(blocked), 1)
        self.assertIn("A has no other branch", blocked[0]["reason"])

    def test_once_per_junction(self):
        base, v4 = hv.load_control()
        v4["lie_detection"] = {**v4["lie_detection"], **BACKTRACK}
        c = hv.ControllerV4(base, v4, cm.load_config(), hv.load_roadmap())
        c.begin(0.0)
        c.node, c.last_choice, c.rejections = "J2", {"node": "J1", "branch": "LEFT", "serial": 3}, ["arrival", "arrival"]
        c.tried = {"J1": {"LEFT"}}
        c.backtracked = {"J1"}
        inp = hv.TickInputV4(time_s=1.0, x=0.0, z=0.0, yaw_deg=0.0)
        self.assertFalse(c._start_backtrack(inp, 1.0))
        self.assertIn("used its one backtrack", c.decisions[-1]["reason"])
        c.backtracked = set()
        c.road.nodes["J2"]["arrive_from"] = "J3"                          # J2 would not follow the last decision junction
        self.assertFalse(c._start_backtrack(inp, 1.0))
        self.assertIn("does not follow", c.decisions[-1]["reason"])

    def test_the_withdrawn_answer_is_named_in_the_log(self):
        r = run("A3", "E3", [None, "LEFT"], BACKTRACK, NORTH)
        bt = events(r, "backtrack")[0]
        lied = [d for d in events(r, "go") if d["node"] == "J1"][0]
        self.assertEqual(bt["withdrawn_serial"], lied["serial"])


class ConsistentLies(unittest.TestCase):
    """AUDIT.md 16.12 item 2: a worker is a liar or not, and which wrong direction it shows, drawn ONCE per run (as in Unity)."""

    def shown_by_worker(self, r):
        out = {}
        for g in r["gestures"]:
            out.setdefault((g["node"], g["worker"]), []).append(g)
        return out

    def test_set_b_is_per_worker_and_set_a_has_no_lies(self):
        scen = sv.load_scenarios()
        self.assertEqual(scen["sets"]["B"]["lie_mode"], "per_worker")
        self.assertEqual(sv.scenario_ab("B3", 1)["spec"].lie_mode, "per_worker")
        self.assertEqual(sv.scenario_ab("A3", 1)["spec"].lie_probability, 0.0)

    def test_a_liar_shows_the_same_direction_every_time_it_is_asked(self):
        multi = 0
        for name in ("B1", "B2", "B3", "B4"):
            for seed in range(1, 21):
                for key, gs in self.shown_by_worker(sv.run_scenario(name, seed, sv.DETECTION_ON)).items():
                    self.assertEqual(len({(g["shown"], g["truthful"]) for g in gs}), 1, (name, seed, key))
                    multi += len(gs) > 1
        self.assertGreater(multi, 20)                                              # many workers were asked more than once

    def test_the_earlier_per_gesture_model_does_vary(self):
        varied = 0
        for seed in range(1, 21):
            sc = sv.scenario_ab("B3", seed, sv.DETECTION_ON)
            sc["spec"].lie_mode = "per_gesture"
            sc["spec"].lie_probability = 0.5
            for gs in self.shown_by_worker(sc["sim"].run(sc["goal"])).values():
                varied += len({(g["shown"], g["truthful"]) for g in gs}) > 1
        self.assertGreater(varied, 0)

    def test_the_share_of_liars_is_a_fifth(self):
        liars = workers = 0
        for seed in range(1, 41):
            for gs in self.shown_by_worker(sv.run_scenario("B3", seed, sv.DETECTION_OFF)).values():
                workers += 1
                liars += not gs[0]["truthful"]
        self.assertGreater(workers, 60)
        self.assertTrue(0.08 < liars / workers < 0.35, liars / workers)

    def test_the_draw_is_seeded_and_does_not_depend_on_what_the_robot_does(self):
        a = run("B3", None, seed=5, detection=OFF)
        b = run("B3", None, seed=5, detection=T_ON)
        la = {k: gs[0]["shown"] for k, gs in self.shown_by_worker(a).items()}
        lb = {k: gs[0]["shown"] for k, gs in self.shown_by_worker(b).items()}
        for k in set(la) & set(lb):                                                # the same worker, the same lie, whatever the robot did before
            self.assertEqual(la[k], lb[k], k)
        c = run("B3", None, seed=6, detection=OFF)
        self.assertNotEqual({k: gs[0]["shown"] for k, gs in self.shown_by_worker(c).items()}, la)

    def test_a_consistent_liar_asked_twice_counts_twice_in_the_vote(self):
        # J1, goal LEFT: the first person asked lies (the script) and, with the tie rule, is asked again: per_worker would repeat the lie.
        sc = sv.scenario_ab("B3", 1, SECOND)
        sc["spec"].lie_script = None
        self.assertEqual(sc["spec"].lie_mode, "per_worker")

    def test_scripted_lies_still_work(self):
        r = run("A3", "E2", [None, None, "RIGHT"], SECOND, xcheck=True)
        self.assertEqual([g["shown"] for g in r["gestures"] if not g["truthful"]][:1], ["RIGHT"])


T_ON = sv.DETECTION_ON


class ThirdWorkerAndMargin(unittest.TestCase):
    """AUDIT.md 16.12 items 3 and 4."""

    def test_the_config(self):
        scen = sv.load_scenarios()
        for k in ("3", "4"):
            self.assertEqual(scen["scenarios"][k]["layout"]["people_by_node"], {"J1": 3})
        for k in ("1", "2"):
            self.assertNotIn("people_by_node", scen["scenarios"][k]["layout"])
        lay = scen["scenarios"]["4"]["layout"]
        self.assertEqual((lay["nearer_margin_m"], lay["approach_m"], lay["max_draws"]), (0.25, 3.0, 100000))
        self.assertEqual(scen["placement_rule"]["min_worker_separation_m"], 3.0)             # the 3.0 m rule is unchanged
        self.assertEqual(lay["approach_m"], hc.load_json("configs/hri_control.json")["drive"]["junction_slow_radius_m"])

    def test_three_workers_at_j1_and_two_elsewhere_in_a3_a4_b3_b4(self):
        for name in ("A3", "A4", "B3", "B4"):
            for seed in (1, 2, 3):
                sc = sv.scenario_ab(name, seed)
                for node, v in sc["road"].nodes.items():
                    if v["kind"] in ("start", "junction"):
                        n = len(sc["sim"]._scene_at(node).people)
                        self.assertEqual(n, 3 if node == "J1" else 2, (name, seed, node))
        for name in ("A1", "A2", "B1", "B2"):
            sc = sv.scenario_ab(name, 1)
            self.assertTrue(all(len(sc["sim"]._scene_at(n).people) == 2 for n, v in sc["road"].nodes.items() if v["kind"] in ("start", "junction")))

    def test_the_spacing_rule_holds_for_three_workers_too(self):
        for name in ("A3", "A4"):
            for seed in range(1, 21):
                sc = sv.scenario_ab(name, seed)
                scene = sc["sim"]._scene_at("J1")
                sv.check_placement(sc["road"], "J1", [(p.x, p.z) for p in scene.people], 3.0, 3.0)

    def test_the_first_worker_is_nearer_by_the_margin_along_the_whole_approach(self):
        road = hc.Roadmap(hc.load_json("configs/v4/roadmap.json"))
        for node in ("A", "J1", "J2", "J3", "J4"):
            robot = sv.approach_points(road, node, 3.0)
            for seed in range(1, 21):
                n = 3 if node == "J1" else 2
                pts = sv.place_random(road, node, n, 3.0, 1.0, 3.0, seed, 3.0, 0.25, 3.0, 100000)
                for q in robot:
                    d0 = math.dist(q, pts[0])
                    for other in pts[1:]:
                        self.assertGreaterEqual(math.dist(q, other), d0 + 0.25 - 1e-9, (node, seed))

    def test_the_approach_points(self):
        road = hc.Roadmap(hc.load_json("configs/v4/roadmap.json"))
        self.assertEqual(sv.approach_points(road, "A", 3.0), [(6.25, -20.0)])               # the start node: the start position alone
        pts = sv.approach_points(road, "J1", 3.0)
        self.assertEqual((pts[0], round(pts[-1][1], 6)), ((6.25, 0.0), -3.0))                # from the node back 3.0 m along the arrival road
        self.assertEqual(len(pts), 31)

    def test_without_the_margin_nothing_changes_and_an_impossible_set_is_refused(self):
        road = hc.Roadmap(hc.load_json("configs/v4/roadmap.json"))
        self.assertEqual(sv.place_random(road, "J1", 2, 3.0, 1.0, 3.0, 7, 3.0), sv.place_random(road, "J1", 2, 3.0, 1.0, 3.0, 7, 3.0, 0.0))
        with self.assertRaisesRegex(ValueError, "cannot place 3 people at J1 in 50 draws"):
            sv.place_random(road, "J1", 3, 3.0, 1.0, 3.0, 1, 3.0, 0.25, 3.0, 50)

    def test_every_scenario_still_builds_for_20_seeds(self):
        for name in ("A3", "A4"):
            for seed in range(1, 21):
                sc = sv.scenario_ab(name, seed)
                for node, v in sc["road"].nodes.items():
                    if v["kind"] in ("start", "junction"):
                        sc["sim"]._scene_at(node)


class LeftTurn(unittest.TestCase):
    def test_the_left_map_is_nusrats_proposal_and_consistent(self):
        scen = sv.load_scenarios()
        prop = json.loads((ROOT.parent / "unity/Robotics-Warehouse/WarehouseProjectURP/Assets/WarehouseRobot/Scenario/Config/roadmap_proposals/turn_left.json").read_text(encoding="utf-8"))
        m = scen["maps"]["turn_left"]
        self.assertEqual((m["start"], m["nodes"], m["branches"]), (prop["start"], prop["nodes"], prop["branches"]))
        self.assertEqual(hv.check_labels_v4(hc.Roadmap(m)), [])
        self.assertAlmostEqual(sv.route_length_m(hc.Roadmap(m), "C"), 40.0)

    def test_a2_and_b2_run_with_the_left_turn(self):
        for name in ("A2", "B2"):
            for seed in (1, 2, 3):
                r = sv.run_scenario(name, seed, sv.DETECTION_ON, side="left")
                self.assertEqual(sv.scenario_ab(name, seed, side="left")["road"].next("B", "LEFT"), "C")
                if name == "A2":
                    self.assertEqual((r["outcome"], r["v4"]["route"][-1]), ("SUCCESS", "C"))

    def test_other_experiments_have_no_left_map_and_right_is_the_default(self):
        with self.assertRaisesRegex(ValueError, "no 'left' map"):
            sv.scenario_ab("A1", 1, side="left")
        self.assertEqual(sv.scenario_ab("A2", 1)["road"].next("B", "RIGHT"), "C")


class ExperimentFiles(unittest.TestCase):
    """AUDIT.md 16.12 item 5: server map files and control files for Nusrat's development runs."""
    EXP = ROOT / "configs/v4/experiments"
    MAPS = {"a1": "corridor", "a2_right": "turn", "a2_left": "turn_left"}

    def test_each_map_file_is_its_map_in_scenarios_ab(self):
        scen = sv.load_scenarios()
        for tag, m in self.MAPS.items():
            f = json.loads((self.EXP / f"roadmap_{tag}.json").read_text(encoding="utf-8"))
            for k in ("start", "nodes", "branches", "worker_stand"):
                self.assertEqual(f[k], scen["maps"][m][k], (tag, k))
            self.assertEqual(hv.check_labels_v4(hc.Roadmap(f)), [])

    def test_control_files_differ_from_control_json_in_the_label_the_roadmap_and_the_switches_only(self):
        scen = sv.load_scenarios()
        base = json.loads((ROOT / "configs/v4/control.json").read_text(encoding="utf-8"))
        roads = {"": "configs/v4/roadmap.json", "_a1": "configs/v4/experiments/roadmap_a1.json",
                 "_a2_right": "configs/v4/experiments/roadmap_a2_right.json", "_a2_left": "configs/v4/experiments/roadmap_a2_left.json"}
        for suffix, road in roads.items():
            for mode in ("off", "on"):
                f = json.loads((self.EXP / f"control_lie_{mode}{suffix}.json").read_text(encoding="utf-8"))
                self.assertEqual(f["roadmap"], road)
                for k in ("second_opinion", "reject_impossible", "backtrack"):
                    self.assertEqual(f["lie_detection"][k], scen["detection"][mode][k], (suffix, mode, k))
                g, b = json.loads(json.dumps(f)), json.loads(json.dumps(base))
                for d in (g, b):
                    d.pop("label"), d.pop("roadmap")
                    for k in ("second_opinion", "reject_impossible", "backtrack"):
                        d["lie_detection"].pop(k)
                self.assertEqual(g, b, (suffix, mode))
        on = json.loads((self.EXP / "control_lie_on.json").read_text(encoding="utf-8"))["lie_detection"]
        self.assertEqual([on["second_opinion"], on["reject_impossible"], on["backtrack"]], [True, True, False])     # backtrack off (16.10.2)
        self.assertEqual([base["lie_detection"][k] for k in ("second_opinion", "reject_impossible", "backtrack")], [False] * 3)

    def test_the_controller_builds_from_every_control_file_with_its_map(self):
        for suffix, start_next in (("", {"FORWARD": "J1"}), ("_a1", {"FORWARD": "B"}), ("_a2_right", {"FORWARD": "B"}), ("_a2_left", {"FORWARD": "B"})):
            for mode in ("off", "on"):
                c = hv.make_controller_v4(str(self.EXP / f"control_lie_{mode}{suffix}.json"))
                self.assertEqual(c.road.branches["A"], start_next)
                self.assertEqual((c.ld["second_opinion"], c.ld["backtrack"]), (mode == "on", False))

    def test_the_files_are_outside_the_freeze_list_except_scenarios_ab(self):
        import freeze_v4 as fz
        listed = fz.config_files()
        self.assertEqual([f for f in listed if "/experiments/" in f], list(fz.FROZEN_EXTRA))


UNITY_CFG = ROOT.parent / "unity/Robotics-Warehouse/WarehouseProjectURP/Assets/WarehouseRobot/Scenario/Config/experiments_ab_unity.json"


class MatchesUnity(unittest.TestCase):
    """AUDIT.md 16.13: the simulator does what Unity's ExperimentPlanAB does (the beside slots, the goal generator, the valid-branch liar)."""

    def setUp(self):
        self.u = json.loads(UNITY_CFG.read_text(encoding="utf-8"))
        self.scen = sv.load_scenarios()
        self.road = hc.Roadmap(hc.load_json("configs/v4/roadmap.json"))

    # -- 1. the beside slots
    def test_the_slots_and_margins_are_unitys(self):
        for k in ("1", "2", "3"):
            lay = self.scen["scenarios"][k]["layout"]
            self.assertEqual(lay["junction_slots"], self.u["junction_slots"], k)
            self.assertEqual(lay["start_slots"], self.u["start_slots"], k)
            self.assertEqual((lay["nearer_margin_m"], lay["approach_m"]), (self.u["nearer_margin_m"], self.u["approach_m"]), k)
        self.assertEqual(self.scen["scenarios"]["4"]["layout"]["nearer_margin_m"], self.u["random_nearer_margin_m"])
        self.assertEqual(self.scen["scenarios"]["4"]["layout"]["max_draws"], self.u["random_max_draws"])
        for e in self.u["experiments"]:                                                  # the third worker at J1 in A3, A4, B3, B4 only
            lay = self.scen["scenarios"][e["scenario"]]["layout"]
            self.assertEqual(sorted(lay.get("people_by_node", {})), e["three_worker_nodes"], e["name"])
        self.assertEqual(self.scen["placement_rule"]["min_worker_separation_m"], 3.0)

    def test_slot_positions(self):
        js, ss = self.u["junction_slots"], self.u["start_slots"]
        pts = [tuple(round(c, 6) for c in q) for q in sv.place_slots(self.road, "J1", 3, js)]
        self.assertEqual(pts, [(4.25, -3.0), (8.25, -5.5), (4.25, -6.0)])                   # the first worker stands on the LEFT, 3.0 m back
        self.assertEqual([tuple(round(c, 6) for c in q) for q in sv.place_slots(self.road, "A", 2, ss)], [(4.25, -23.0), (10.25, -23.0)])
        j2 = [tuple(round(c, 6) for c in q) for q in sv.place_slots(self.road, "J2", 2, js)]
        self.assertEqual(j2, [(-3.25, -2.0), (-0.75, 2.0)])                                  # arrival heading west: back = east, right = north
        with self.assertRaisesRegex(ValueError, "4 workers but 3 slots"):
            sv.place_slots(self.road, "J1", 4, js)

    def test_every_scene_of_the_beside_experiments_obeys_the_rules_including_the_bystander_margin(self):
        for name in ("A1", "A2", "A3", "B3"):
            sc = sv.scenario_ab(name, 1)
            for node in sv.ask_nodes(sc["road"]):
                pts = [(p.x, p.z) for p in sc["sim"]._scene_at(node).people]
                sv.check_placement(sc["road"], node, pts, 3.0, 3.0, sc["spec"].physical_map, 1.0, 3.0)
                for o in pts[1:]:
                    self.assertGreaterEqual(sv.nearer_margin(sc["road"], node, o, pts[0], 3.0), 1.0 - 1e-9, (name, node))

    def test_the_old_symmetric_pair_breaks_the_bystander_rule(self):
        pair = sv.place_beside(self.road, "J1", 2, 2.0, 3.0)
        sv.check_placement(self.road, "J1", pair, 3.0, 3.0)                                   # without the margin it passed
        with self.assertRaisesRegex(ValueError, "farther than the first worker"):
            sv.check_placement(self.road, "J1", pair, 3.0, 3.0, None, 1.0, 3.0)

    def test_the_physical_map_counts_for_every_map_and_other_nodes_workers_too(self):
        corridor = hc.Roadmap(self.scen["maps"]["corridor"])
        phys = hc.Roadmap(hc.load_json("configs/v4/roadmap.json"))
        near_j1 = [(6.25, -1.0)]                                                              # 1 m from J1 of the physical map, not near any node of the corridor
        sv.check_placement(corridor, "A", near_j1, 3.0, 3.0)
        with self.assertRaisesRegex(ValueError, "turning point"):
            sv.check_placement(corridor, "A", near_j1, 3.0, 3.0, phys)
        self.assertEqual(len(sv.turning_points(corridor, phys)), len(sv.turning_points(corridor)) + len(sv.turning_points(phys)))
        with self.assertRaisesRegex(ValueError, "another node"):
            sv.check_placement(self.road, "J2", [(-8.0, 3.0)], 3.0, 3.0, None, 0.0, 3.0, [(-8.0, 5.0)])

    def test_random_workers_are_sorted_by_distance_to_the_node_and_keep_away_from_placed_ones(self):
        for node in ("J1", "J3"):
            nx, nz = self.road.pos(node)
            for seed in range(1, 15):
                pts = sv.place_random(self.road, node, 3 if node == "J1" else 2, 3.0, 1.0, 3.0, seed, 3.0, 0.25, 3.0, 100000)
                d = [math.hypot(x - nx, z - nz) for x, z in pts]
                self.assertEqual(d, sorted(d), (node, seed))
        far = sv.place_random(self.road, "J1", 2, 3.0, 1.0, 3.0, 5, 3.0, 0.25, 3.0, 100000, None, [(8.0, 2.0)])
        self.assertTrue(all(math.dist(p, (8.0, 2.0)) >= 3.0 for p in far))

    def test_the_planned_run_obeys_every_rule_across_nodes_in_unitys_order(self):
        self.assertEqual(sv.ask_nodes(self.road), ["A", "J1", "J2", "J3", "J4"])
        for name in ("A3", "A4"):
            for seed in range(1, 11):
                sc = sv.scenario_ab(name, seed)
                plan = sc["sim"].plan_workers()
                self.assertEqual(list(plan), sv.ask_nodes(sc["road"]))
                allp = [q for pts in plan.values() for q in pts]
                for i, a in enumerate(allp):
                    for b in allp[i + 1:]:
                        self.assertGreaterEqual(math.dist(a, b), 3.0 - 1e-9)

    # -- 2. the goals
    def test_goals_are_unitys_goal_sequence_of_the_session_seed(self):
        self.assertEqual(self.scen["session_seed"], 1)
        ends = sorted(self.road.endpoints())
        want = ht.goal_order(1, ends, 20)
        got = [sv.scenario_ab("A3", seed)["goal"] for seed in range(1, 21)]
        self.assertEqual(got, want)
        self.assertEqual([sv.scenario_ab(n, 7)["goal"] for n in ("A3", "A4", "B3", "B4")], [want[6]] * 4)
        self.assertTrue(all(a != b for a, b in zip(got, got[1:])))                         # "B changes every run": never the previous goal
        self.assertEqual(sv.scenario_ab("A1", 5)["goal"], "B")

    # -- 3. the liar shows a real wrong branch
    def test_the_wrong_directions_are_unitys(self):
        sim = sv.scenario_ab("B3", 1)["sim"]
        self.assertEqual(sim.spec.lie_directions, "valid_branch")
        self.assertEqual(set(sim._wrong_directions("J1", "RIGHT")), {"FORWARD", "LEFT"})        # the other branches of J1
        self.assertEqual(set(sim._wrong_directions("J2", "BACK")), {"FORWARD", "RIGHT"})        # B cannot be reached from J2: every branch is wrong
        self.assertEqual(set(sim._wrong_directions("J3", "LEFT")), {"RIGHT"})
        self.assertEqual(set(sim._wrong_directions("A", "FORWARD")), {"LEFT", "RIGHT", "BACK"})  # no other branch: the compass fallback (impossible)
        b2 = sv.scenario_ab("B2", 1)["sim"]
        self.assertEqual(set(b2._wrong_directions("B", "RIGHT")), {"LEFT", "FORWARD", "BACK"})
        sim.spec.lie_directions = "compass"
        self.assertEqual(set(sim._wrong_directions("J1", "RIGHT")), {"LEFT", "FORWARD", "BACK"})  # the earlier model
        self.assertEqual(sv.scenario_ab("A3", 1)["spec"].lie_directions, "compass")             # Set A never lies, the default applies

    def test_a_liar_at_a_junction_never_shows_back_or_a_wall_and_always_the_same_branch(self):
        liars = 0
        for name in ("B3", "B4"):
            for seed in range(1, 21):
                sc = sv.scenario_ab(name, seed, sv.DETECTION_ON)
                r = sc["sim"].run(sc["goal"])
                for g in r["gestures"]:
                    if not g["truthful"] and g["node"] != "A":
                        liars += 1
                        self.assertIsNotNone(sc["road"].next(g["node"], g["shown"]), (name, seed, g))
        self.assertGreater(liars, 10)

    def test_where_no_other_branch_exists_a_liar_shows_an_impossible_direction(self):
        seen = set()
        for seed in range(1, 41):
            for name, node in (("B1", "A"), ("B2", "B")):
                sc = sv.scenario_ab(name, seed)
                for g in sc["sim"].run(sc["goal"])["gestures"]:
                    if not g["truthful"] and g["node"] == node:
                        seen.add(sc["road"].next(node, g["shown"]))
        self.assertEqual(seen, {None})


class DetectionSettings(unittest.TestCase):
    def test_the_experiments_detection_blocks_are_the_declared_ones_and_backtrack_is_off(self):
        d = sv.load_scenarios()["detection"]
        self.assertEqual({k: d["off"][k] for k in OFF}, OFF)
        self.assertEqual({k: d["on"][k] for k in ON}, ON)
        self.assertEqual(ON, {"second_opinion": True, "reject_impossible": True, "backtrack": False})

    def test_backtrack_is_still_a_working_switch(self):
        r = run("A3", "E3", [None, "LEFT"], BACKTRACK, NORTH)
        self.assertEqual(len(events(r, "backtrack")), 1)


class Scenarios(unittest.TestCase):
    def test_the_two_small_maps_are_consistent(self):
        scen = sv.load_scenarios()
        for name in ("corridor", "turn"):
            road = hc.Roadmap(scen["maps"][name])
            self.assertEqual(hv.check_labels_v4(road), [], name)
        self.assertAlmostEqual(sv.route_length_m(hc.Roadmap(scen["maps"]["corridor"]), "B"), 40.0)
        self.assertAlmostEqual(sv.route_length_m(hc.Roadmap(scen["maps"]["turn"]), "C"), 40.0)

    def test_every_scenario_succeeds_with_truthful_workers(self):
        for name in ("A1", "A2", "A3", "A4"):
            for det in (OFF, ON):
                for seed in (1, 2):
                    r = sv.run_scenario(name, seed, det)
                    self.assertEqual((r["outcome"], r["failure_reason"]), ("SUCCESS", "none"), (name, seed, det))
                    self.assertTrue(all(g["truthful"] for g in r["gestures"]))
                    self.assertEqual(r["set"], "A")

    def test_two_people_at_every_asking_node(self):
        for name, nodes in (("A1", {"A"}), ("A2", {"A", "B"})):
            r = sv.run_scenario(name, 1, OFF)
            seen = {}
            for x in r["truth_rows"]:
                seen.setdefault(x["worker_id"], set())
            self.assertEqual(len(seen), 2, name)

    def test_goals_come_from_the_seed_only(self):
        for seed in range(1, 8):
            sc = sv.scenario_ab("A3", seed)
            ends = sorted(sc["road"].endpoints())
            self.assertEqual(sc["goal"], ht.goal_order(1, ends, 20)[seed - 1])                # Unity's GoalSequence(session seed 1), run k = seed k
            self.assertEqual(sc["goal"], sv.scenario_ab("B4", seed)["goal"])               # the same four in set B
        self.assertEqual(sv.scenario_ab("A1", 3)["goal"], "B")
        self.assertEqual(sv.scenario_ab("A2", 3)["goal"], "C")

    def test_set_b_lies_set_a_does_not(self):
        self.assertEqual(sv.scenario_ab("A3", 1)["lie_probability"], 0.0)
        self.assertEqual(sv.scenario_ab("B3", 1)["lie_probability"], 0.2)
        self.assertEqual(sv.scenario_ab("B3", 1)["spec"].layout, sv.scenario_ab("A3", 1)["spec"].layout)

    def test_unknown_experiment_names_are_refused(self):
        for bad in ("C1", "A5", "A", "A12", "a1"):
            with self.assertRaises(ValueError):
                sv.scenario_ab(bad, 1)

    def test_a_run_is_reproducible(self):
        for name in ("B2", "B4"):
            a, b = sv.run_scenario(name, 3, ON), sv.run_scenario(name, 3, ON)
            self.assertEqual((a["outcome"], a["time_s"], a["trace"], a["gestures"]), (b["outcome"], b["time_s"], b["trace"], b["gestures"]))

    def test_the_corridor_and_the_turn_have_no_wrong_branch_so_every_lie_is_impossible(self):
        for name, goal in (("A1", "B"), ("A2", "C")):
            r = run(name, goal, p=1.0, detection=OFF)
            road = sv.scenario_ab(name, 1)["road"]
            for g in r["gestures"]:
                self.assertIsNone(road.next(g["node"], g["shown"]), (name, g))

    def test_the_controller_has_no_goal(self):
        c = sv.scenario_ab("A3", 1)["sim"].c
        self.assertEqual([k for k in vars(c) if "goal" in k.lower()], [])


if __name__ == "__main__":
    unittest.main()
