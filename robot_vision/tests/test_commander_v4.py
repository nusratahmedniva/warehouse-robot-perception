"""v4 commander rule (commander_v4.py) on synthetic readings and synthetic skeletons: facing, moving hand, bystanders,
no candidate, ties, stickiness, hand-to-body linking and the link to 360-camera ids."""

import json
import sys
import unittest
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))

import commander_v4 as cm  # noqa: E402
import gesture_motion as gm  # noqa: E402
import v4_synth as vs  # noqa: E402

CC = cm.load_config()
GC = gm.load_config()


def reading(command="NONE", raised=False, moving=False, path=0.0, score=0.0):
    r = gm.Reading(command, score, "", 0.0, raised=raised, moving=moving)
    r.arms = {"left": {"raised": raised, "path": path, "moving": moving}}
    return r


def person(tid, facing=True, **kw):
    return cm.PersonReading(tid, kw.pop("bearing", 0.0), facing, "facing" if facing else "turned away", reading(**kw))


class FacingTests(unittest.TestCase):
    def test_facing_person(self):
        kp, conf = vs.body()
        self.assertEqual(cm.facing_check(vs.sample(0, kp, conf), CC, 0.5), (True, "facing"))

    def test_back_to_the_camera_or_sideways(self):
        kp, conf = vs.body()
        conf2 = conf.copy()
        conf2[gm.L_EYE] = 0.1                                        # one eye hidden: head turned
        ok, why = cm.facing_check(vs.sample(0, kp, conf2), CC, 0.5)
        self.assertFalse(ok)
        self.assertIn("face keypoints", why)
        kp3 = kp.copy()
        mid = (kp3[gm.L_SHOULDER] + kp3[gm.R_SHOULDER]) / 2
        kp3[gm.L_SHOULDER] = mid + (kp3[gm.L_SHOULDER] - mid) * 0.4          # shoulders squeezed: body turned
        kp3[gm.R_SHOULDER] = mid + (kp3[gm.R_SHOULDER] - mid) * 0.4
        ok, why = cm.facing_check(vs.sample(0, kp3, conf), CC, 0.5)
        self.assertFalse(ok)
        self.assertIn("turned sideways", why)

    def test_missing_torso(self):
        kp, conf = vs.body()
        conf = conf.copy()
        conf[gm.L_HIP] = 0.0
        self.assertEqual(cm.facing_check(vs.sample(0, kp, conf), CC, 0.5)[1], "torso keypoints missing")

    def test_bearing_from_box(self):
        s = vs.sample(0, *vs.body(), pan_deg=10.0)
        self.assertAlmostEqual(cm.box_bearing_deg((s.cx - 10, 0, s.cx + 10, 100), s), -10.0, delta=1e-6)    # centred: minus the pan
        self.assertAlmostEqual(cm.box_bearing_deg((s.cx + s.fx - 5, 0, s.cx + s.fx + 5, 1), s), 45.0 - 10.0, delta=1e-6)


class BodyBearingTests(unittest.TestCase):
    def test_outstretched_arm_does_not_shift_the_bearing(self):
        kp, conf = vs.body(left=vs.direction(90.0))
        s = vs.sample(0, kp, conf)
        s.box = (float(kp[:, 0].min()), float(kp[:, 1].min()), float(kp[:, 0].max()), float(kp[:, 1].max()))
        self.assertLess(abs(cm.body_bearing_deg(s, 0.5)), 1.0)
        self.assertGreater(abs(cm.box_bearing_deg(s.box, s)), 5.0)             # the box centre is pulled toward the arm

    def test_falls_back_to_the_box(self):
        kp, conf = vs.body()
        conf = conf.copy()
        conf[gm.L_SHOULDER] = 0.0
        s = vs.sample(0, kp, conf, pan_deg=4.0)
        s.box = (s.cx - 20, 0, s.cx + 20, 100)
        self.assertAlmostEqual(cm.body_bearing_deg(s, 0.5), -4.0, delta=1e-6)


class PickTests(unittest.TestCase):
    def test_commander_among_bystanders(self):
        ps = [person(1, raised=True, moving=True, path=1.2, command="NONE"), person(2), person(3, facing=False)]
        c = cm.pick_commander(ps, CC)
        self.assertEqual(c.commander, 1)
        self.assertIn("only facing person", c.reason)
        left = {p["id"]: p["left_out"] for p in c.people}
        self.assertEqual(left[1], "")
        self.assertEqual(left[2], "no raised arm")
        self.assertIn("turned away", left[3])

    def test_not_facing_but_waving_is_not_the_commander(self):
        c = cm.pick_commander([person(1, facing=False, raised=True, moving=True, path=2.0), person(2)], CC)
        self.assertIsNone(c.commander)
        self.assertIn("no person is facing", c.reason)

    def test_nobody_gesturing(self):
        c = cm.pick_commander([person(1), person(2, raised=True)], CC)          # raised but still, no command
        self.assertIsNone(c.commander)
        self.assertEqual({p["id"]: p["left_out"] for p in c.people}[2], "raised arm neither moving nor holding a command")

    def test_empty(self):
        self.assertIsNone(cm.pick_commander([], CC).commander)

    def test_two_movers_the_clearly_more_active_wins_else_tie(self):
        a = person(1, raised=True, moving=True, path=1.5)
        b = person(2, raised=True, moving=True, path=0.8)
        self.assertEqual(cm.pick_commander([a, b], CC).commander, 1)
        near = person(2, raised=True, moving=True, path=1.4)                     # within motion_margin 0.2
        c = cm.pick_commander([a, near], CC)
        self.assertIsNone(c.commander)
        self.assertIn("tie", c.reason)

    def test_holder_counts_when_nobody_moves(self):
        c = cm.pick_commander([person(1, raised=True, command="WAIT", score=0.9), person(2)], CC)
        self.assertEqual(c.commander, 1)
        self.assertIn("held command", c.reason)

    def test_a_mover_beats_a_holder(self):
        c = cm.pick_commander([person(1, raised=True, command="STOP", score=1.0), person(2, raised=True, moving=True, path=0.9)], CC)
        self.assertEqual(c.commander, 2)

    def test_two_holders_tie_unless_scores_differ(self):
        a, b = person(1, raised=True, command="POINT", score=0.9), person(2, raised=True, command="POINT", score=0.9)
        self.assertIsNone(cm.pick_commander([a, b], CC).commander)
        b = person(2, raised=True, command="POINT", score=0.8)
        self.assertEqual(cm.pick_commander([a, b], CC).commander, 1)

    def test_previous_commander_is_kept_while_still_gesturing(self):
        a = person(1, raised=True, moving=True, path=0.9)
        b = person(2, raised=True, moving=True, path=1.8)
        self.assertEqual(cm.pick_commander([a, b], CC).commander, 2)
        c = cm.pick_commander([a, b], CC, previous=1)
        self.assertEqual(c.commander, 1)
        self.assertIn("kept the previous", c.reason)
        gone = cm.pick_commander([person(1), b], CC, previous=1)                 # the previous one stopped: choose again
        self.assertEqual(gone.commander, 2)

    def test_choice_is_json(self):
        c = cm.pick_commander([person(1, raised=True, moving=True, path=1.0), person(2)], CC)
        json.dumps(c.to_dict())


class RealReadingsTests(unittest.TestCase):
    """The rule on readings computed by the reader from synthetic skeletons: the waving person and a still bystander."""

    def read(self, builder, n=12):
        seq = vs.arm_sequence(builder, n)
        return gm.read_window(seq[-10:], GC, seq[-1].t), seq[-1]

    def test_waving_person_beats_standing_bystander(self):
        def wave(i):
            d = vs.direction(60.0 + (35.0 if i % 2 else -35.0), 25.0)
            return (*vs.body(left=d), {})
        rw, sw = self.read(wave)
        rb, sb = self.read(lambda i: (*vs.body(x0=1.0), {}))
        ps = [cm.PersonReading(1, 0.0, *cm.facing_check(sw, CC, 0.5), rw), cm.PersonReading(2, 20.0, *cm.facing_check(sb, CC, 0.5), rb)]
        self.assertTrue(rw.moving)
        self.assertEqual(cm.pick_commander(ps, CC).commander, 1)

    def test_pointing_person_and_bystander_with_a_raised_still_hand(self):
        rp, sp = self.read(lambda i: (*vs.body(left=vs.direction(90.0)), {}))
        rb, sb = self.read(lambda i: (*vs.body(x0=1.0, right=vs.direction(-90.0)), {}))
        self.assertEqual(rp.command, "POINT")
        # both hold a raised arm and both read POINT: equal scores are a tie
        ps = [cm.PersonReading(1, 0.0, True, "facing", rp), cm.PersonReading(2, 20.0, True, "facing", rb)]
        self.assertIsNone(cm.pick_commander(ps, CC).commander)


class LinkTests(unittest.TestCase):
    P = [{"track_id": 4, "bearing_deg": -20.0}, {"track_id": 9, "bearing_deg": 12.0}]

    def test_nearest_within_tolerance(self):
        self.assertEqual(cm.link_to_360(10.0, self.P, 10.0), 9)
        self.assertEqual(cm.link_to_360(-25.0, self.P, 10.0), 4)

    def test_none_beyond_tolerance_or_when_empty(self):
        self.assertIsNone(cm.link_to_360(40.0, self.P, 10.0))
        self.assertIsNone(cm.link_to_360(0.0, [], 10.0))

    def test_equidistant_is_ambiguous(self):
        p = [{"track_id": 1, "bearing_deg": -5.0}, {"track_id": 2, "bearing_deg": 5.0}]
        self.assertIsNone(cm.link_to_360(0.0, p, 10.0))

    def test_wraps_around_180(self):
        self.assertEqual(cm.link_to_360(-178.0, [{"track_id": 3, "bearing_deg": 179.0}], 10.0), 3)


class IsolationTests(unittest.TestCase):
    def test_commander_rule_imports_no_evaluation_or_truth_code(self):
        import ast
        tree = ast.parse((ROOT / "commander_v4.py").read_text(encoding="utf-8"))
        mods = {a.name.split(".")[0] for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names}
        mods |= {n.module.split(".")[0] for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) and n.module}
        self.assertFalse(mods & {"gesture_data", "gt_path", "data_splits_v4", "hri_eval_dev_v4"}, mods)


if __name__ == "__main__":
    unittest.main()
