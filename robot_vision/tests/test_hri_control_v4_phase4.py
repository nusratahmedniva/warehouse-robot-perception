"""Phase 4 decisions in the v4 controller: two-view POINT disambiguation, re-approaching the commander, and the commander
timing rule (only a gesture that starts after 'Which direction?' counts). Scripted readings, no Unity."""

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))

import commander_v4 as cm  # noqa: E402
import gesture_motion as gm  # noqa: E402
import hri_control as hc  # noqa: E402
import hri_control_v4 as hv  # noqa: E402
from test_hri_control_v4 import ROAD, Rig, person, point_person, pt  # noqa: E402

BASE, V4 = hv.load_control()
DIRS, ARR = hv.branch_directions(ROAD, "J1")          # FORWARD 0, RIGHT 90, LEFT -90, arrival 180
GAP, TOL = V4["dialog"]["branch_match_max_deg"], V4["dialog"]["view_consistency_deg"]


class TwoViewResolution(unittest.TestCase):
    def two(self, v1, v2, tol=TOL):
        return hv.resolve_two_views(v1, v2, DIRS, ARR, 0.0, GAP, tol)

    def test_the_true_direction_stays_put_the_mirror_moves(self):
        r = self.two({"away": 90.0, "toward": -90.0}, {"away": 92.0, "toward": 20.0})
        self.assertEqual((r.command, r.views), ("RIGHT", 2))
        self.assertAlmostEqual(r.rel_deg, 91.0, delta=0.1)

    def test_other_family_may_be_the_true_one(self):
        self.assertEqual(self.two({"away": 5.0, "toward": -85.0}, {"away": 60.0, "toward": -88.0}).command, "LEFT")

    def test_identical_views_leave_it_ambiguous(self):
        r = self.two({"away": 90.0, "toward": -90.0}, {"away": 90.0, "toward": -90.0})
        self.assertEqual((r.command, r.ambiguous), (None, True))
        self.assertIn("still fit two branches", r.why)

    def test_no_agreement_is_unclear(self):
        r = self.two({"away": 90.0, "toward": -90.0}, {"away": 30.0, "toward": 0.0})
        self.assertEqual((r.command, r.ambiguous), (None, False))
        self.assertIn("do not agree", r.why)

    def test_tolerance_is_inclusive_and_configurable(self):
        v1, v2 = {"away": 90.0, "toward": None}, {"away": 100.0, "toward": None}
        self.assertEqual(self.two(v1, v2, 10.0).command, "RIGHT")
        self.assertIsNone(self.two(v1, v2, 9.9).command)

    def test_the_arrival_direction_is_still_never_an_answer(self):
        self.assertIsNone(self.two({"away": 175.0, "toward": None}, {"away": 178.0, "toward": None}).command)

    def test_wraps_around_180(self):
        self.assertIsNone(self.two({"away": 179.0, "toward": None}, {"away": -179.0, "toward": None}).command)

    def test_single_candidate_views(self):
        self.assertEqual(self.two({"away": 4.0, "toward": 4.0}, {"away": 2.0, "toward": 2.0}).command, "FORWARD")


def ambiguous_person(tid=7, away=90.0, toward=-90.0, **kw):
    return point_person(tid, away, toward, **kw)


class SecondView(unittest.TestCase):
    def test_ambiguous_reading_starts_a_second_view_not_an_abort(self):
        r = Rig()
        r.run([ambiguous_person()], 0.3)
        self.assertEqual(r.c.state, "read")                              # not held long enough yet
        r.run([ambiguous_person()], 0.4)
        c = r.c
        self.assertEqual((c.state, c.two_view_used, c.free_asks, c.dialog.asks), ("approach", True, 1, 1))
        self.assertIn("second_view", " ".join(c.trace))
        self.assertAlmostEqual(c.view1["away"], 90.0)
        self.assertAlmostEqual(c.view1["toward"], -90.0)
        self.assertIn("second_view_t", c.record)

    def test_the_second_view_does_not_use_up_an_ask(self):
        r = Rig()
        r.run([ambiguous_person()], 0.8)
        r.c._ask(r.t, hc.Command())                                       # the robot arrived at its new viewpoint
        self.assertEqual((r.c.dialog.asks, r.c.free_asks), (1, 0))
        self.assertEqual(r.c.ask_serial, 1)

    def test_the_candidate_both_views_agree_on_is_accepted(self):
        r = Rig()
        r.run([ambiguous_person()], 0.8)
        r.c._ask(r.t, hc.Command())
        r.c.state, r.c.state_start = "read", r.t
        r.run([point_person(7, 92.0, 20.0)], 1.0)
        self.assertEqual((r.c.state, r.c.next_node, r.c.dialog.asks), ("execute", "E2", 1))
        rec = r.c.junctions[-1]
        self.assertEqual((rec["views"], rec["read"], rec["point"]["views"]), (2, "RIGHT", 2))

    def test_views_that_do_not_agree_end_as_an_unclear_ask_then_abort(self):
        r = Rig()
        r.run([ambiguous_person()], 0.8)
        r.c._ask(r.t, hc.Command())
        r.c.state, r.c.state_start = "read", r.t
        r.run([point_person(7, 30.0, 0.0)], 5.2)                         # agrees with nothing
        self.assertEqual((r.c.state, r.c.dialog.asks), ("approach", 1))   # the normal ask-again path (reposition)
        r.c._ask(r.t, hc.Command())
        self.assertEqual(r.c.dialog.asks, 2)                               # now it counts
        r.c.state, r.c.state_start = "read", r.t
        r.run([ambiguous_person()], 5.2)                                   # a second two-view is not allowed
        self.assertEqual(r.c.state, "aborted")
        self.assertIn("gesture unclear after 2 asks", r.c.abort_reason)

    def test_at_most_one_second_view_per_junction(self):
        r = Rig()
        r.run([ambiguous_person()], 0.8)
        r.c._ask(r.t, hc.Command())
        r.c.state, r.c.state_start = "read", r.t
        r.run([point_person(7, 90.0, -90.0)], 0.8)                         # identical to view 1: still ambiguous
        self.assertEqual(r.c.state, "read")
        self.assertEqual(r.c.free_asks, 0)
        self.assertEqual(r.c.trace.count([x for x in r.c.trace if "second_view" in x][0]), 1)

    def test_switch_off_restores_the_old_behaviour(self):
        r = Rig()
        r.c.v4["dialog"]["two_view_enabled"] = False
        r.run([ambiguous_person()], 5.2)
        self.assertEqual((r.c.state, r.c.two_view_used, r.c.dialog.asks), ("approach", False, 1))

    def test_unambiguous_readings_never_start_one(self):
        r = Rig()
        r.run([point_person(7, 90.0, 150.0)], 1.0)                        # 150 is nearest the arrival direction: dropped
        self.assertEqual((r.c.state, r.c.two_view_used), ("execute", False))

    def test_a_crosscheck_decision_is_not_a_second_view(self):
        r = Rig()
        r.c.v4["dialog"]["use_hand_crosscheck_as_tiebreak"] = True
        r.run([person(7, "POINT", point=pt(90.0, -90.0, prefers="away"))], 1.0)
        self.assertEqual((r.c.state, r.c.next_node, r.c.two_view_used), ("execute", "E2", False))

    def test_a_new_junction_forgets_the_first_view(self):
        r = Rig()
        r.run([ambiguous_person()], 0.8)
        self.assertIsNotNone(r.c.view1)
        r.c._arrive("J2", r.t)
        self.assertEqual((r.c.view1, r.c.two_view_used, r.c.reapproached), (None, False, False))


def p360(tid, bearing, x=8.0, z=2.0, d=2.0):
    return {"track_id": tid, "bearing_deg": bearing, "x": x, "z": z, "distance_m": d}


class Reapproach(unittest.TestCase):
    def rig(self):
        r = Rig()
        r.c.approached_360 = 3                                            # the robot walked up to person 3 (a bystander)
        return r

    def test_commander_that_is_someone_else_is_approached_at_2_m(self):
        r = self.rig()
        crowd = [p360(3, -30.0, x=7.0, z=2.0), p360(1, 4.0, x=8.75, z=2.5)]
        r.run([point_person(7, 90.0, bearing=4.0)], 0.8, people360=crowd)
        c = r.c
        # (the rig's robot already stands 2 m from the commander, so the approach ends at once and the question is shown again)
        self.assertEqual((c.reapproached, c.approached_360, c.free_asks, c.dialog.asks), (True, 1, 0, 1))
        self.assertIn(c.state, ("approach", "ask"))
        self.assertEqual(c.person, (8.75, 2.5))
        d = ((c.approach_point[0] - 8.75) ** 2 + (c.approach_point[1] - 2.5) ** 2) ** 0.5
        self.assertAlmostEqual(d, 2.0, places=6)
        self.assertEqual(c.record["reapproach"]["from_360"], 3)
        self.assertEqual(c.record["reapproach"]["to_360"], 1)
        self.assertIn("reapproach", " ".join(c.trace))

    def test_it_does_not_use_up_an_ask_and_happens_once(self):
        r = self.rig()
        crowd = [p360(3, -30.0), p360(1, 4.0, x=8.75, z=2.5)]
        r.run([point_person(7, 90.0, bearing=4.0)], 0.8, people360=crowd)
        self.assertEqual((r.c.dialog.asks, r.c.free_asks, r.c.ask_serial), (1, 0, 1))      # shown again, not counted as an ask
        r.c.approached_360 = 3                                            # even if it were still a different person
        r.run([point_person(7, 90.0, bearing=4.0)], 1.6, people360=crowd)
        self.assertEqual(len([x for x in r.c.trace if "reapproach" in x]), 1)             # no second re-approach
        self.assertEqual(r.c.state, "execute")
        self.assertTrue(r.c.junctions[-1]["reapproached"])

    def test_nothing_happens_when_the_commander_is_the_person_approached(self):
        r = Rig()
        r.c.approached_360 = 1
        r.run([point_person(7, 90.0, bearing=4.0)], 1.0, people360=[p360(1, 4.0, x=8.75, z=2.5)])
        self.assertEqual((r.c.state, r.c.reapproached), ("execute", False))

    def test_nothing_happens_when_the_commander_cannot_be_linked_to_a_360_person(self):
        r = self.rig()
        r.run([point_person(7, 90.0, bearing=4.0)], 1.0, people360=[p360(3, -30.0)])
        self.assertEqual((r.c.state, r.c.reapproached), ("execute", False))

    def test_the_commander_must_be_stable_first(self):
        r = self.rig()
        crowd = [p360(3, -30.0), p360(1, 4.0, x=8.75, z=2.5)]
        r.run([point_person(7, 90.0, bearing=4.0)], 0.3, people360=crowd)
        self.assertEqual((r.c.state, r.c.reapproached), ("read", False))

    def test_switch_off(self):
        r = self.rig()
        r.c.v4["dialog"]["reapproach_commander"] = False
        r.run([point_person(7, 90.0, bearing=4.0)], 1.0, people360=[p360(3, -30.0), p360(1, 4.0)])
        self.assertFalse(r.c.reapproached)

    def test_whom_the_robot_approached_is_recorded_from_the_scan(self):
        c = hv.make_controller_v4()
        c.reset(0.0)
        c.node, c.state, c.state_start = "J1", "scan", 0.0
        c.dialog.reset()
        inp = hv.TickInputV4(1.0, 6.25, 0.0, 0.0, people=[p360(5, 10.0, x=7.0, z=2.0, d=3.0), p360(9, -5.0, x=5.0, z=2.0, d=2.2)],
                             people_time_s=1.0)
        c._tick(inp, hc.Command())
        self.assertEqual((c.state, c.approached_360), ("approach", 9))     # the nearest


class CommanderTiming(unittest.TestCase):
    def test_a_gesture_that_started_before_the_question_is_ignored(self):
        r = Rig()
        r.c.record["t_ask_first"] = 1.0
        r.c.dialog.ask_start = 1.0
        r.c.raised_since = {7: 0.2}                                       # person 7 has had the arm up since before the question
        r.run([point_person(7, 90.0, bearing=4.0)], 1.2)
        self.assertEqual((r.c.state, r.c.commander_pt), ("read", None))
        left = {p["id"]: p["left_out"] for p in r.c.choice.people}
        self.assertEqual(left[7], "gesture started before the question was shown")

    def test_lowering_and_raising_again_makes_a_person_eligible(self):
        r = Rig()
        r.c.record["t_ask_first"] = 0.3
        r.c.dialog.ask_start = 0.3
        r.c.raised_since = {7: 0.1}
        r.run([point_person(7, 90.0, bearing=4.0)], 0.5)
        self.assertIsNone(r.c.commander_pt)
        r.tick([cm.PersonReading(7, 4.0, True, "facing", gm.Reading("NONE", 0.0, "", 0.0))])
        self.assertNotIn(7, r.c.raised_since)                              # arm down: the onset is forgotten
        r.run([point_person(7, 90.0, bearing=4.0)], 1.0)
        self.assertEqual((r.c.state, r.c.next_node), ("execute", "E2"))

    def test_onsets_after_the_question_count_and_are_tracked_in_every_state(self):
        c = hv.make_controller_v4()
        c.reset(0.0)
        c.state = "navigate"
        for k in range(3):
            c._track_onsets(hv.TickInputV4(0.1 * k, 0, 0, 0, persons=[point_person(7, 90.0)], persons_time_s=0.1 * k))
        self.assertEqual(c.raised_since, {7: 0.0})
        c._track_onsets(hv.TickInputV4(0.5, 0, 0, 0, persons=[], persons_time_s=0.5))
        self.assertEqual(c.raised_since, {})                               # out of view: forgotten

    def test_a_re_ask_does_not_reset_the_reference_time(self):
        r = Rig()
        first = r.c.record["t_ask_first"]
        r.c._ask(5.0, hc.Command())
        self.assertEqual(r.c.record["t_ask_first"], first)

    def test_the_commander_rule_reports_the_reason(self):
        a = cm.PersonReading(1, 0.0, True, "facing", gm.Reading("POINT", 0.9, "", 0.0, raised=True))
        c = cm.pick_commander([a], cm.load_config(), None, {1: "gesture started before the question was shown"})
        self.assertIsNone(c.commander)
        self.assertEqual(c.people[0]["left_out"], "gesture started before the question was shown")
        self.assertEqual(cm.pick_commander([a], cm.load_config()).commander, 1)


if __name__ == "__main__":
    unittest.main()
