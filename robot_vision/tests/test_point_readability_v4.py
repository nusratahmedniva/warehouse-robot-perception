"""The simulator's readability of a pointing by its angle to the line of sight (AUDIT.md 16.26.5 item 4): the bin lookup, the fit rule (20 frames per bin, else Nusrat's band), the
simulated reading (NONE with point_fail "length" when not read, unchanged when the model is off or the bin reads 1.0), the angle recomputed from the robot's viewpoint, and the runner
switches (readability model for every variant, side view in T4 only)."""

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import fit_point_readability_v4 as fit  # noqa: E402
import gesture_motion as gm  # noqa: E402
import hri_sim_v4 as sv  # noqa: E402
import run_t3_v4 as r3  # noqa: E402
from hri_sim import SimConfig  # noqa: E402

BAND = {"bins": [{"lo": lo, "hi": lo + 15, "p": 1.0 if 45 <= lo and lo + 15 <= 135 else 0.0} for lo in range(0, 180, 15)]}


def commander(angle, x=0.0, z=2.0):
    ep = sv.Episode("POINT", 10.0, 0.5, 0.5, 1.0, 0.5, arm="right", clip="clipA", world_angle_deg=angle)
    return sv.Scene([sv.Person(1, x, z, "look_a", "commander", ep)])


def read(model, angle, robot=(0.0, 0.0, 0.0), person=(0.0, 2.0), seed=1, t=11.5):
    v = sv.ReaderLevelVision(commander(angle, *person), SimConfig(), sv.GestureSimConfig(point_readability=model), gm.load_config(), seed)
    out = v.person_readings(t, robot[0], robot[1], robot[2], 0.0, 60.0)
    return out[0].reading


class Lookup(unittest.TestCase):
    def test_bins_and_edges(self):
        self.assertEqual(sv.readability_p(BAND, 0.0), 0.0)
        self.assertEqual(sv.readability_p(BAND, 44.9), 0.0)
        self.assertEqual(sv.readability_p(BAND, 45.0), 1.0)
        self.assertEqual(sv.readability_p(BAND, 134.9), 1.0)
        self.assertEqual(sv.readability_p(BAND, 135.0), 0.0)
        self.assertEqual(sv.readability_p(BAND, 180.0), 0.0)                    # the last bin includes 180
        self.assertEqual(sv.readability_p(BAND, -90.0), 1.0)                    # the angle is an absolute one


class Fit(unittest.TestCase):
    def frames(self, angle, n, read):
        return [{"cat": "POINT", "phase": "holding", "cmd": "POINT" if i < read else "NONE", "sight_angle": angle} for i in range(n)]

    def test_a_bin_with_20_frames_is_fitted_and_fewer_take_the_band(self):
        fr = self.frames(100.0, 20, 5) + self.frames(70.0, 19, 19) + self.frames(10.0, 25, 0) + self.frames(170.0, 3, 3)
        bins = {b["lo"]: b for b in fit.fit_bins(fr)}
        self.assertEqual((bins[90]["source"], bins[90]["p"]), ("fitted", 0.25))                 # 20 frames: its own read rate
        self.assertEqual((bins[60]["source"], bins[60]["p"]), ("band", 1.0))                    # 19 frames, inside 45 to 135: the band's step, not the 100 % read
        self.assertEqual((bins[0]["source"], bins[0]["p"]), ("fitted", 0.0))                    # 25 frames, none read
        self.assertEqual((bins[165]["source"], bins[165]["p"]), ("band", 0.0))                  # 3 frames at 170 degrees: the band says unreadable
        self.assertEqual((bins[30]["source"], bins[30]["p"], bins[30]["held"]), ("band", 0.0, 0))
        self.assertEqual(len(bins), 12)

    def test_only_held_frames_of_a_true_pointing_count(self):
        fr = [{"cat": "nothing", "phase": "idle", "cmd": "POINT", "sight_angle": 100.0}] * 30 + [{"cat": "POINT", "phase": "gesturing", "cmd": "POINT", "sight_angle": 100.0}] * 30
        self.assertTrue(all(b["held"] == 0 for b in fit.fit_bins(fr)))

    def test_the_last_bin_includes_180_degrees(self):
        bins = fit.fit_bins(self.frames(180.0, 20, 20))
        self.assertEqual((bins[-1]["held"], bins[-1]["p"]), (20, 1.0))


class Reading(unittest.TestCase):
    def test_off_reads_every_pointing_as_before(self):
        for a in (0.0, 90.0, 180.0):
            r = read(None, a)
            self.assertEqual((r.command, r.point_fail), ("POINT", ""))

    def test_a_pointing_along_the_line_of_sight_is_not_read_and_fails_on_length(self):
        # the robot looks north at a worker 2 m ahead; pointing north is AWAY from the camera (a = 0), pointing south is AT it (a = 180): neither is readable
        for a in (0.0, 180.0):
            r = read(BAND, a)
            self.assertEqual((r.command, r.point_fail, r.raised), ("NONE", "length", True))
            self.assertIsNone(r.point)
        r = read(BAND, 90.0)                                                      # pointing east: across the line of sight
        self.assertEqual((r.command, r.point_fail), ("POINT", ""))
        self.assertIsNotNone(r.point)

    def test_the_angle_is_recomputed_for_another_viewpoint(self):
        # the same pointing (north) from a viewpoint 2 m east of the worker looking west: the line of sight runs east to west, so north is across it (a = 90)
        self.assertEqual(read(BAND, 0.0, robot=(0.0, 0.0, 0.0)).command, "NONE")
        r = read(BAND, 0.0, robot=(2.0, 2.0, -90.0), person=(0.0, 2.0))
        self.assertEqual((r.command, r.point_fail), ("POINT", ""))

    def test_only_a_pointing_is_affected(self):
        ep = sv.Episode("WAIT", 10.0, 0.5, 0.5, 1.0, 0.5, arm="right", clip="c")
        v = sv.ReaderLevelVision(sv.Scene([sv.Person(1, 0.0, 2.0, "look", "commander", ep)]), SimConfig(), sv.GestureSimConfig(point_readability=BAND), gm.load_config(), 1)
        r = v.person_readings(11.5, 0.0, 0.0, 0.0, 0.0, 60.0)[0].reading
        self.assertEqual((r.command, r.point_fail), ("WAIT", ""))

    def test_a_probability_between_0_and_1_is_drawn_per_frame(self):
        half = {"bins": [{"lo": 0, "hi": 180, "p": 0.5}]}
        n = sum(read(half, 90.0, seed=s).command == "POINT" for s in range(400))
        self.assertTrue(140 <= n <= 260, n)

    def test_a_model_of_all_ones_draws_nothing_so_every_earlier_run_is_unchanged(self):
        ones = {"bins": [{"lo": 0, "hi": 180, "p": 1.0}]}
        v1 = sv.ReaderLevelVision(commander(40.0), SimConfig(), sv.GestureSimConfig(), gm.load_config(), 7)
        v2 = sv.ReaderLevelVision(commander(40.0), SimConfig(), sv.GestureSimConfig(point_readability=ones), gm.load_config(), 7)
        a = [v1.person_readings(11.0 + 0.05 * i, 0.0, 0.0, 0.0, 0.0, 60.0)[0].reading.command for i in range(15)]
        b = [v2.person_readings(11.0 + 0.05 * i, 0.0, 0.0, 0.0, 0.0, 60.0)[0].reading.command for i in range(15)]
        self.assertEqual(a, b)
        self.assertEqual(v1.rng.random(), v2.rng.random())                        # the two generators are in the same state


class Runner(unittest.TestCase):
    def test_the_defaults_are_off(self):
        import inspect
        sig = inspect.signature(r3.one_run)
        self.assertIsNone(sig.parameters["readability"].default)
        self.assertFalse(sig.parameters["side_view"].default)

    def test_the_side_view_switch_reaches_the_controller(self):
        scen = sv.load_scenarios()
        cp = {"fraction": 0.5}
        seen = {}
        r3.one_run("T4", "A1", "on", 1, 5.0, cp, scen, hook=lambda c: seen.update(sv=dict(c.sv)), side_view=True)
        self.assertTrue(seen["sv"]["enabled"])
        seen.clear()
        r3.one_run("T4", "A1", "on", 1, 5.0, cp, scen, hook=lambda c: seen.update(sv=dict(c.sv)))
        self.assertFalse(seen["sv"]["enabled"])


if __name__ == "__main__":
    unittest.main()
