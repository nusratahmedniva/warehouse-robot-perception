"""v4 state machine (hri_control_v4.py): resolving a pointed direction with the roadmap (the arrival branch is never an
answer), the READ dialog with POINT / WAIT / STOP, the zoom rule and the HUD fields, on scripted readings (no Unity)."""

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import commander_v4 as cm  # noqa: E402
import gesture_motion as gm  # noqa: E402
import hri_control as hc  # noqa: E402
import hri_control_v4 as hv  # noqa: E402

ROAD = hc.Roadmap(hc.load_json("configs/roadmap.json"))
BASE, V4 = hv.load_control()
Z = V4["zoom"]
MAXGAP = V4["dialog"]["branch_match_max_deg"]


def pt(away=None, toward=None, prefers=None):
    return gm.PointEstimate(0.0, 0.0, {"away": away, "toward": toward}, {"away": None, "toward": None}, True, 5,
                            {"available": prefers is not None, "prefers": prefers, "diff_deg": {}, "why": ""})


class BranchTests(unittest.TestCase):
    def test_directions_and_arrival(self):
        dirs, arrival = hv.branch_directions(ROAD, "J1")
        self.assertEqual({k: round(v) for k, v in dirs.items()}, {"FORWARD": 0, "RIGHT": 90, "LEFT": -90})
        self.assertEqual(round(abs(arrival)), 180)                 # back toward A
        dirs, arrival = hv.branch_directions(ROAD, "J2")
        self.assertEqual({k: round(v) for k, v in dirs.items()}, {"FORWARD": -90, "RIGHT": 0})   # arriving from J1 heading -x
        self.assertEqual(round(arrival), 90)                       # back toward J1 (+x)

    def test_load_control_applies_the_v4_hold_and_leaves_v3_alone(self):
        self.assertEqual(BASE["dialog"]["gesture_hold_s"], 0.5)
        self.assertEqual(hc.load_json("configs/hri_control.json")["dialog"]["gesture_hold_s"], 1.0)
        self.assertEqual(BASE["drive"], hc.load_json("configs/hri_control.json")["drive"])


class ResolveTests(unittest.TestCase):
    DIRS, ARR = hv.branch_directions(ROAD, "J1")

    def res(self, away=None, toward=None, yaw=0.0, prefers=None, use=False):
        return hv.resolve_point(pt(away, toward, prefers), self.DIRS, self.ARR, yaw, MAXGAP, use)

    def test_one_candidate_to_its_branch(self):
        r = self.res(away=90.0)
        self.assertEqual((r.command, r.gap_deg, r.ambiguous), ("RIGHT", 0.0, False))
        self.assertEqual(self.res(away=-80.0).command, "LEFT")
        self.assertEqual(self.res(away=10.0).command, "FORWARD")

    def test_the_arrival_branch_is_never_an_answer(self):
        r = self.res(away=180.0)
        self.assertIsNone(r.command)
        self.assertIn("came from", r.candidates[0]["verdict"])
        self.assertIsNone(self.res(away=-170.0).command)

    def test_the_candidate_pointing_back_is_dropped_and_the_other_decides(self):
        self.assertEqual(self.res(away=5.0, toward=175.0).command, "FORWARD")        # toward = the arrival side
        self.assertEqual(self.res(away=150.0, toward=95.0).command, "RIGHT")         # 150 is nearer 180 than 90: dropped
        r = self.res(away=150.0, toward=95.0)
        self.assertEqual([c["target"] for c in r.candidates], ["ARRIVAL", "RIGHT"])

    def test_within_the_gap_only(self):
        self.assertEqual(self.res(away=60.0).command, "RIGHT")                        # 30 from RIGHT: at the limit
        r = self.res(away=45.0)                                                       # 45 from both
        self.assertIsNone(r.command)
        self.assertIn("within reach", r.why)
        self.assertIn("more than", r.candidates[0]["verdict"])

    def test_two_branches_are_ambiguous_unless_the_crosscheck_decides(self):
        r = self.res(away=90.0, toward=-90.0)
        self.assertEqual((r.command, r.ambiguous), (None, True))
        r = self.res(away=90.0, toward=-90.0, prefers="toward")
        self.assertIsNone(r.command)                                                  # cross-check not allowed to decide
        r = self.res(away=90.0, toward=-90.0, prefers="toward", use=True)
        self.assertEqual((r.command, r.used_crosscheck), ("LEFT", True))
        self.assertIsNone(self.res(away=90.0, toward=-90.0, use=True).command)        # no preference: still ambiguous

    def test_both_candidates_on_one_branch_agree(self):
        r = self.res(away=80.0, toward=100.0)
        self.assertEqual((r.command, r.ambiguous), ("RIGHT", False))
        self.assertEqual(r.gap_deg, 10.0)

    def test_nothing_to_resolve(self):
        self.assertIsNone(self.res().command)

    def test_relative_to_the_robot(self):
        self.assertEqual(self.res(away=90.0, yaw=30.0).rel_deg, 60.0)
        self.assertEqual(self.res(away=-170.0, toward=-5.0, yaw=-20.0).rel_deg, 15.0)    # FORWARD via the toward candidate

    def test_json(self):
        json.dumps(self.res(away=90.0, toward=150.0).to_dict())


class ZoomMathTests(unittest.TestCase):
    WH = (730, 530)

    def test_hand_fills_the_share(self):
        hand = (300.0, 200.0, 340.0, 240.0)          # 40 px tall = 7.5 % of 530
        arm = (290.0, 190.0, 350.0, 250.0)           # small: the hand decides
        fov = hv.zoom_target(hand, arm, self.WH, 60.0, Z)
        self.assertAlmostEqual(fov, 19.8, delta=0.3)

    def test_the_arm_limits_the_zoom(self):
        hand = (300.0, 200.0, 340.0, 240.0)
        arm = (150.0, 150.0, 450.0, 260.0)           # 300 px wide = 0.41 of the width
        fov = hv.zoom_target(hand, arm, self.WH, 60.0, Z)
        self.assertGreater(fov, 30.0)
        self.assertLess(fov, 36.0)

    def test_clamped(self):
        big = (100.0, 50.0, 600.0, 500.0)
        self.assertEqual(hv.zoom_target(big, big, self.WH, 60.0, Z), Z["fov_max_deg"])
        tiny = (300.0, 200.0, 302.0, 202.0)
        self.assertEqual(hv.zoom_target(tiny, tiny, self.WH, 60.0, Z), Z["fov_min_deg"])

    def test_consistent_with_a_narrower_current_view(self):
        hand = (300.0, 200.0, 340.0, 240.0)
        a = hv.zoom_target(hand, (290.0, 190.0, 350.0, 250.0), self.WH, 60.0, Z)
        # the same scene seen at 30 deg would show the hand about twice as tall
        hand2 = (280.0, 160.0, 360.0, 240.0)
        b = hv.zoom_target(hand2, (270.0, 150.0, 370.0, 250.0), self.WH, 30.0, Z)
        self.assertAlmostEqual(a, b, delta=2.0)

    def test_hand_centred(self):
        self.assertTrue(hv.hand_centred((330.0, 240.0, 400.0, 290.0), self.WH, 0.1))
        self.assertFalse(hv.hand_centred((10.0, 240.0, 60.0, 290.0), self.WH, 0.1))


def reading(command="NONE", hand=(340.0, 230.0, 390.0, 290.0), arm=(300.0, 200.0, 400.0, 300.0), fov=60.0, **kw):
    r = gm.Reading(command, kw.pop("score", 0.9), "", 0.0, raised=True, moving=kw.pop("moving", False),
                   hand_box=hand, arm_box=arm, frame_wh=(730, 530), fov_deg=fov, frame_class=command)
    r.arms = {"left": {"raised": True, "path": kw.pop("path", 0.0), "moving": r.moving}}
    r.point = kw.pop("point", None)
    return r


def person(tid, command="NONE", bearing=0.0, facing=True, **kw):
    return cm.PersonReading(tid, bearing, facing, "facing" if facing else "turned away", reading(command, **kw))


class Rig:
    """A controller placed in the READ state at J1: robot at (8.75, 0.5) facing +Z, the worker 2 m ahead."""

    def __init__(self, zoom=True, wait_timeout=None):
        base, v4 = hv.load_control()
        v4["zoom"]["enabled"] = zoom
        if wait_timeout is not None:
            v4["dialog"]["wait_timeout_s"] = wait_timeout
        self.c = hv.ControllerV4(base, v4, cm.load_config(), ROAD)
        c = self.c
        c.reset(0.0)
        c.last_t = 0.0
        c.node = "J1"
        c.person = (8.75, 2.5)
        c.record = {"junction": "J1", "t_ask_first": 0.0}
        c.dialog.reset()
        c.dialog.begin_ask(0.0)
        c.state, c.state_start = "read", 0.0
        self.t = 0.0
        self.states = []

    def tick(self, persons, dt=0.1, fov=60.0, people360=None):
        self.t = round(self.t + dt, 6)
        inp = hv.TickInputV4(time_s=self.t, x=8.75, z=0.5, yaw_deg=0.0, people=people360 or [], people_time_s=self.t,
                             persons=persons, persons_time_s=self.t, fov_deg=fov)
        cmd = self.c.step(inp)
        self.states.append(cmd.state)
        return cmd

    def run(self, persons, seconds, **kw):
        out = None
        for _ in range(int(round(seconds / 0.1))):
            out = self.tick(persons, **kw)
        return out


def point_person(tid, away, toward=None, **kw):
    return person(tid, "POINT", point=pt(away, toward), **kw)


class DialogTests(unittest.TestCase):
    def test_point_right_held_is_accepted_and_the_robot_turns_to_the_branch(self):
        r = Rig()
        r.run([point_person(7, 90.0)], 1.0)
        c = r.c
        self.assertEqual(c.state, "execute")
        self.assertEqual((c.next_node, c.dialog.accepted), ("E2", "RIGHT"))
        rec = c.junctions[-1]
        self.assertEqual((rec["result"], rec["read"], rec["point"]["command"], rec["commander_pt"]), ("accepted", "RIGHT", "RIGHT", 7))
        self.assertIn("t_accept", rec)

    def test_hold_time_is_needed(self):
        r = Rig()
        r.run([point_person(7, 90.0)], 0.3)
        self.assertEqual(r.c.state, "read")
        self.assertEqual(r.c.junctions, [])

    def test_a_changing_answer_restarts_the_hold(self):
        r = Rig()
        r.run([point_person(7, 90.0)], 0.4)
        r.run([point_person(7, -90.0)], 0.4)
        self.assertEqual(r.c.state, "read")
        r.run([point_person(7, -90.0)], 0.5)
        self.assertEqual(r.c.next_node, "J2")                              # LEFT

    def test_pointing_back_at_the_arrival_never_works_and_asks_again(self):
        r = Rig()
        r.run([point_person(7, 180.0)], 5.2)
        self.assertEqual(r.c.state, "approach")                            # window over: ask again (reposition)
        self.assertEqual(r.c.dialog.asks, 1)
        self.assertEqual(r.c.junctions, [])

    def test_unclear_twice_aborts_as_in_v3(self):
        r = Rig()
        r.run([point_person(7, 180.0)], 5.2)
        self.assertEqual(r.c.state, "approach")
        r.c._ask(r.t, hc.Command())                                        # (the v3 reposition and ask, tested in v3)
        r.run([point_person(7, 180.0)], 5.2)
        self.assertEqual(r.c.state, "aborted")
        self.assertIn("gesture unclear after 2 asks", r.c.abort_reason)

    def test_bystander_is_not_the_commander(self):
        r = Rig()
        idle = cm.PersonReading(3, -20.0, True, "facing", gm.Reading("NONE", 0.0, "", 0.0))
        persons = [idle, point_person(7, 90.0, bearing=5.0)]
        r.run(persons, 1.0)
        self.assertEqual(r.c.commander_pt, 7)
        self.assertEqual(r.c.next_node, "E2")

    def test_no_commander_means_nothing_is_read(self):
        r = Rig()
        r.run([point_person(7, 90.0, facing=False)], 2.0)
        self.assertEqual((r.c.state, r.c.commander_pt, r.c.label), ("read", None, "NONE"))

    def test_two_people_gesturing_equally_is_a_tie_and_nothing_is_accepted(self):
        r = Rig()
        r.run([point_person(7, 90.0, bearing=-10.0), point_person(8, -90.0, bearing=10.0)], 2.0)
        self.assertEqual((r.c.state, r.c.commander_pt), ("read", None))
        self.assertIn("tie", r.c.choice.reason)

    def test_the_camera_is_aimed_at_the_commander(self):
        r = Rig()
        cmd = r.run([point_person(7, 90.0, bearing=20.0)], 0.3)
        self.assertAlmostEqual(cmd.pan_deg, -20.0, delta=1.0)


class WaitTests(unittest.TestCase):
    def test_wait_holds_position_and_watches_the_same_person(self):
        r = Rig()
        cmd = r.run([person(7, "WAIT", bearing=8.0)], 1.0)
        self.assertTrue(r.c.waiting)
        self.assertEqual(cmd.state, "wait")
        self.assertEqual((cmd.v, cmd.omega, cmd.screen_text), (0.0, 0.0, "One moment..."))
        self.assertEqual(r.c.commander_pt, 7)
        self.assertEqual(r.c.hud_fields(r.c._fresh_persons(hv.TickInputV4(r.t, 0, 0, 0, persons=[person(7, "WAIT")], persons_time_s=r.t)))["gesture_accepted"], "WAIT")

    def test_wait_then_point_is_accepted(self):
        r = Rig()
        r.run([person(7, "WAIT")], 3.0)
        self.assertTrue(r.c.waiting)
        r.run([point_person(7, 90.0)], 1.0)
        self.assertEqual((r.c.state, r.c.next_node, r.c.waiting), ("execute", "E2", False))
        self.assertGreater(r.c.junctions[-1]["waited_s"], 2.0)

    def test_wait_far_longer_than_the_ask_window_does_not_end_the_ask(self):
        r = Rig()
        r.run([person(7, "WAIT")], 12.0)                                   # the ask window is 5 s
        self.assertTrue(r.c.waiting)
        self.assertEqual(r.c.state, "read")

    def test_wait_times_out_after_20_s_and_the_ask_is_unclear(self):
        r = Rig()
        r.run([person(7, "WAIT")], 21.0)                                   # 0.5 s hold, then 20 s
        self.assertEqual(r.c.state, "approach")                            # ask again from a new viewpoint
        self.assertFalse(r.c.waiting)
        self.assertEqual(r.c.dialog.asks, 1)

    def test_wait_timeout_twice_aborts_with_a_clear_reason(self):
        r = Rig(wait_timeout=2.0)
        r.run([person(7, "WAIT")], 3.0)
        self.assertEqual(r.c.state, "approach")
        r.c._ask(r.t, hc.Command())
        r.run([person(7, "WAIT")], 4.0)
        self.assertEqual(r.c.state, "aborted")
        self.assertIn("wait timeout", r.c.abort_reason)

    def test_wait_needs_a_hold(self):
        r = Rig()
        r.run([person(7, "WAIT")], 0.3)
        self.assertFalse(r.c.waiting)


class StopTests(unittest.TestCase):
    def test_stop_of_a_bystander_stops_at_once_and_it_resumes(self):
        r = Rig()
        r.run([point_person(7, 90.0, bearing=0.0)], 0.2)
        cmd = r.tick([point_person(7, 90.0), person(9, "STOP", bearing=-30.0)])
        self.assertIn("stopped: STOP gesture", cmd.state)
        self.assertEqual((cmd.v, cmd.omega), (0.0, 0.0))
        self.assertEqual(r.c.hud_fields(r.c._fresh_persons(hv.TickInputV4(r.t, 0, 0, 0, persons=[person(9, "STOP")], persons_time_s=r.t)))["gesture"], "STOP")
        cmd = r.tick([point_person(7, 90.0)])
        self.assertNotIn("stopped", cmd.state)

    def test_stop_while_navigating(self):
        c = hv.make_controller_v4()
        c.begin(0.0)
        self.assertEqual(c.state, "navigate")
        inp = hv.TickInputV4(0.1, 6.25, -10.0, 0.0, people=[], people_time_s=0.1, persons=[person(9, "STOP")], persons_time_s=0.1)
        cmd = c.step(inp)
        self.assertIn("stopped: STOP gesture", cmd.state)

    def test_a_stale_stop_is_ignored(self):
        r = Rig()
        r.run([point_person(7, 90.0)], 0.1)
        inp = hv.TickInputV4(r.t + 5.0, 8.75, 0.5, 0.0, people_time_s=r.t + 5.0, persons=[person(9, "STOP")], persons_time_s=r.t)
        self.assertNotIn("stopped", r.c.step(inp).state)


class ZoomTests(unittest.TestCase):
    def test_zoom_narrows_once_a_commander_is_picked(self):
        r = Rig(zoom=True)
        fovs = []
        for _ in range(30):
            cmd = r.tick([point_person(7, 90.0, hand=(340.0, 245.0, 360.0, 285.0), arm=(320.0, 225.0, 380.0, 300.0))], fov=fovs[-1] if fovs else 60.0)
            fovs.append(cmd.vertical_fov_deg)
            if r.c.state != "read":
                break
        self.assertTrue(any(0 < f < 60.0 for f in fovs))
        self.assertTrue(all(abs(b - a) <= Z["max_change_deg_per_s"] * 0.1 + 1e-6 for a, b in zip(fovs, fovs[1:]) if a > 0 and b > 0))

    def test_zoom_off_always_minus_one(self):
        r = Rig(zoom=False)
        cmds = [r.tick([person(7, "WAIT", hand=(340.0, 245.0, 360.0, 285.0), arm=(320.0, 225.0, 380.0, 300.0))]) for _ in range(20)]
        self.assertEqual({c.vertical_fov_deg for c in cmds}, {-1.0})

    def test_zoom_returns_to_default_after_the_dialog(self):
        r = Rig(zoom=True)
        r.run([point_person(7, 90.0, hand=(340.0, 245.0, 360.0, 285.0), arm=(320.0, 225.0, 380.0, 300.0))], 1.0)
        self.assertEqual(r.c.state, "execute")
        cmd = r.tick([])
        self.assertEqual(cmd.vertical_fov_deg, -1.0)

    def test_widens_in_steps_when_the_hand_is_lost(self):
        z = hv.ZoomController(Z)
        r = reading("WAIT", hand=(340.0, 245.0, 360.0, 285.0), arm=(320.0, 225.0, 380.0, 300.0))
        fov = 60.0
        for i in range(30):
            fov = z.update(0.1 * i, r, fov, True)
        narrow = fov
        self.assertLess(narrow, 40.0)
        lost = reading("WAIT")
        lost.hand_box = None
        t0 = 3.0
        seen = []
        for i in range(1, 25):
            fov = z.update(t0 + 0.1 * i, lost, fov, True)
            seen.append(fov)
        self.assertEqual(seen[:3], [narrow] * 3)                            # not at once: hand_lost_s (0.5 s) first
        self.assertEqual(seen[-1], Z["fov_max_deg"])
        changes = [(b - a, b) for a, b in zip(seen, seen[1:]) if b != a]
        self.assertGreater(len(changes), 1)
        self.assertTrue(all(abs(d - Z["widen_step_deg"]) < 1e-6 or b == Z["fov_max_deg"] for d, b in changes))

    def test_off_centre_hand_counts_as_lost(self):
        z = hv.ZoomController(Z)
        edge = reading("WAIT", hand=(10.0, 245.0, 40.0, 285.0), arm=(5.0, 225.0, 60.0, 300.0))
        out = [z.update(0.1 * i, edge, 60.0, True) for i in range(10)]
        self.assertEqual(set(out), {-1.0})                                  # never seen, never engaged

    def test_clamped_to_the_configured_range(self):
        z = hv.ZoomController({**Z, "fov_min_deg": 40.0})
        tiny = reading("WAIT", hand=(340.0, 245.0, 345.0, 250.0), arm=(335.0, 240.0, 350.0, 255.0))
        fov = 60.0
        for i in range(40):
            fov = z.update(0.1 * i, tiny, fov, True)
        self.assertEqual(fov, 40.0)


class HudTests(unittest.TestCase):
    def test_fields(self):
        r = Rig()
        r.run([point_person(7, 90.0, bearing=4.0)], 0.3, people360=[{"track_id": 12, "bearing_deg": 3.0, "x": 0, "z": 0, "distance_m": 2.0}])
        persons = [point_person(7, 90.0, bearing=4.0)]
        h = r.c.hud_fields(persons)
        self.assertEqual(h["commander_id"], 12)                              # linked to the 360-camera track
        self.assertEqual((h["gesture"], h["gesture_raw"]), ("POINT", "POINT"))
        self.assertEqual(h["point_angle_deg"], 90.0)
        self.assertEqual(h["gesture_accepted"], "NONE")
        r.run(persons, 1.0, people360=[{"track_id": 12, "bearing_deg": 3.0, "x": 0, "z": 0, "distance_m": 2.0}])
        self.assertEqual(r.c.hud_fields(persons)["gesture_accepted"], "RIGHT")

    def test_unlinked_commander_is_minus_one(self):
        r = Rig()
        r.run([point_person(7, 90.0, bearing=4.0)], 0.2)
        self.assertEqual(r.c.hud_fields([point_person(7, 90.0)])["commander_id"], -1)

    def test_idle_hud(self):
        r = Rig()
        h = r.c.hud_fields([])
        self.assertEqual((h["commander_id"], h["gesture"], h["point_angle_deg"], h["gesture_score"]), (-1, "NONE", -1.0, 0.0))


class V3IsUntouchedTests(unittest.TestCase):
    def test_v3_controller_still_has_no_v4_attributes(self):
        c = hc.make_controller()
        self.assertFalse(hasattr(c, "commander_pt") or hasattr(c, "zoom"))
        self.assertNotIn("hri_control_v4", (ROOT / "hri_control.py").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
