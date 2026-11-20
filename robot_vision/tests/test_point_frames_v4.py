"""The POINT-frames analysis (AUDIT.md 16.26 item 3): the two variants applied to the reader for a replay, the measures and the declared criteria, on synthetic windows and records.
The variants change nothing in the reader outside the replay: gesture_motion is restored afterwards."""

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))

import analyse_point_frames_v4 as pf  # noqa: E402
import gesture_motion as gm  # noqa: E402
import test_gesture_motion as T  # noqa: E402
import v4_synth as vs  # noqa: E402

CFG = gm.load_config()


def setUpModule():
    T.setUpModule()


def tearDownModule():
    T.tearDownModule()


def slow_window(dt, n, az=90.0, n_swing=2):
    """A held POINT seen at a slow frame rate: n frames dt apart (the swing over in the first frames)."""
    return vs.arm_sequence(T.point_builder(n_swing, az=az), n, dt=dt)


class Variants(unittest.TestCase):
    def read(self, samples, variant):
        with pf.variant_ctx(variant):
            return gm.read_window(samples, CFG, samples[-1].t)

    def test_the_reference_needs_6_valid_frames_in_the_1_s_window(self):
        s = slow_window(0.25, 12)                                                # 4 frames per second: 5 in the last 1.0 s (the ends count)
        r = gm.read_window(s, CFG, s[-1].t)
        self.assertEqual(r.command, "insufficient_history")
        dense = slow_window(0.1, 14)
        self.assertEqual(gm.read_window(dense, CFG, dense[-1].t).command, "POINT")

    def test_a_floor_tied_to_the_frames_received_reads_the_slow_window(self):
        s = slow_window(0.25, 12)
        for floor in (3, 4, 5):
            r = self.read(s, {"floor": floor})
            self.assertEqual(r.command, "POINT", floor)
        self.assertEqual(self.read(s, {"floor": 6}).command, "insufficient_history")             # a floor of 6 is the reference's own need: 5 frames are not enough
        sparse = slow_window(0.4, 8)                                                             # 2.5 frames per second: 3 in the window
        self.assertEqual(self.read(sparse, {"floor": 4}).command, "insufficient_history")
        self.assertEqual(self.read(sparse, {"floor": 3}).command, "POINT")

    def test_the_stretch_keeps_the_6_frame_minimum_and_grows_the_window(self):
        s = slow_window(0.25, 12)
        r = self.read(s, {"stretch": 2.0})
        self.assertEqual(r.command, "POINT")
        self.assertGreaterEqual(r.valid_frames, 6)                                               # 6 frames, from a window of 1.3 s
        sparse = slow_window(0.4, 8)                                                             # 6 frames need 2.0 s here: 6 frames at 0.4 s spacing = 2.0 s
        self.assertEqual(self.read(sparse, {"stretch": 2.0}).command, "POINT")
        too_sparse = slow_window(0.6, 6)                                                         # 2.0 s holds 4 frames: not enough
        self.assertEqual(self.read(too_sparse, {"stretch": 2.0}).command, "insufficient_history")
        self.assertEqual(self.read(slow_window(0.1, 14), {"stretch": 2.0}).command, "POINT")     # a dense window is unchanged

    def test_the_reader_is_restored_afterwards(self):
        a, b = gm._arm_window, gm.read_window
        with pf.variant_ctx({"floor": 3, "stretch": 2.0}):
            self.assertIsNot(gm._arm_window, a)
        self.assertIs(gm._arm_window, a)
        self.assertIs(gm.read_window, b)
        s = slow_window(0.25, 12)
        self.assertEqual(gm.read_window(s, CFG, s[-1].t).command, "insufficient_history")


class Measures(unittest.TestCase):
    def rec(self, key, cat="POINT", cmd="POINT", phase="holding", cls="RIGHT", err=5.0, sight=90.0, people=1, valid=6):
        r = {"key": ("s", 1, key, 0), "cat": cat, "cmd": cmd, "why": "", "valid": valid, "n_frames": 8, "people": people, "phase": phase, "stopped": False}
        if cat == "POINT":
            r.update({"truth_rel": 90.0, "class": cls, "sight_angle": sight})
            if cmd == "POINT":
                r["err"] = err
        return r

    def test_classes_and_wrap(self):
        self.assertEqual([pf.class_of(x) for x in (0, 44, 46, 134, 136, -46, -134, -136, 180)], ["FORWARD", "FORWARD", "RIGHT", "RIGHT", "BACK", "LEFT", "LEFT", "BACK", "BACK"])
        self.assertEqual(pf.people_bucket(1), "1 person")
        self.assertEqual(pf.people_bucket(2), "2 people")
        self.assertEqual(pf.people_bucket(5), "3+ people")

    def test_score_read_rate_accuracy_and_false_point(self):
        recs = [self.rec(1), self.rec(2, err=40.0), self.rec(3, cmd="insufficient_history"), self.rec(4, cmd="NONE", phase="gesturing"),
                self.rec(5, cat="nothing", cmd="POINT"), self.rec(6, cat="nothing", cmd="NONE"), self.rec(7, cat="STOP", cmd="STOP")]
        sc = pf.score(recs, 30.0)
        self.assertEqual((sc["held_frames"], sc["read_point"], sc["insufficient"]), (3, 2, 1))
        self.assertEqual(sc["read_rate"], 66.7)
        self.assertEqual(sc["classes"]["RIGHT"], {"held": 3, "read": 2, "accurate": 1, "wrong": 1, "accurate_share": 50.0, "read_rate": 66.7})
        self.assertEqual(sc["false_point"]["rate"], 33.3)                                         # 1 of 3 frames without a POINT shown
        self.assertEqual(sc["valid_frames_used"], {"min": 6, "median": 6})

    def test_diff_and_the_declared_criteria(self):
        ref = [self.rec(1, cmd="insufficient_history"), self.rec(2, cat="STOP", cmd="STOP"), self.rec(3)]
        var = [self.rec(1), self.rec(2, cat="STOP", cmd="STOP"), self.rec(3)]
        d = pf.diff_vs_ref(var, ref)
        self.assertEqual((d["POINT"], d["STOP"]), ({"gained": 1, "lost": 0}, {"gained": 0, "lost": 0}))
        res = {"ref": {"ALL": pf.combine([pf.score(ref, 30.0)]), "name": "ref"}, "v": {"ALL": pf.combine([pf.score(var, 30.0)]), "name": "v"}}
        for ds in ("S5", "STOP", "D4*"):
            res["v"][ds] = {"diff": {**d, "STOP": {"gained": 0, "lost": 0}}}
        c = pf.criteria(res, "v")
        self.assertTrue(c["all_met"])
        res["v"]["STOP"] = {"diff": {**d, "STOP": {"gained": 0, "lost": 1}}}
        self.assertFalse(pf.criteria(res, "v")["2_no_STOP_changed"]["ok"])
        worse = [self.rec(1, err=50.0), self.rec(2, cat="STOP", cmd="STOP"), self.rec(3)]             # a new wrong reading in class RIGHT: criterion 1 fails
        res["v"]["ALL"] = pf.combine([pf.score(worse, 30.0)])
        self.assertFalse(pf.criteria(res, "v")["1_accuracy_LEFT_FORWARD_RIGHT"]["ok"])


if __name__ == "__main__":
    unittest.main()
