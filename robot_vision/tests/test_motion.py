"""Tests for motion.py. Run from robot_vision/:  python -m unittest discover -s tests -v"""

import math
import sys
import unittest
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import motion as mo  # noqa: E402

MCFG = {"window_s": 0.5, "min_observations": 10, "min_window_span_s": 0.3, "max_gap_s": 0.2,
        "jump_base_m": 0.5, "max_plausible_speed_mps": 3.0, "reset_on_class_change": True}
LAB = {"moving_enter_speed_mps": 0.35, "moving_exit_speed_mps": 0.20, "radial_min_speed_mps": 0.20,
       "range_rate_deadband_mps": 0.20, "persistence_s": 0.2}
QRULES = {"class_mask_max_depth_iqr_m": 0.5, "fallback_allowed": True, "fallback_max_depth_iqr_m": 0.25}
DT = 1 / 60.24


class QualityTests(unittest.TestCase):
    def obs(self, method, iqr, valid=True):
        return {"position_valid": valid, "selection_method": method, "depth_iqr_m": iqr}

    def test_rules(self):
        self.assertEqual(mo.quality(self.obs("seg_class_person", 0.4), QRULES), (True, ""))
        self.assertFalse(mo.quality(self.obs("seg_class_person", 0.6), QRULES)[0])
        self.assertFalse(mo.quality(self.obs("box_minus_background", 0.3), QRULES)[0])  # stricter fallback limit
        self.assertEqual(mo.quality(self.obs("seg_class_person", 0.1, False), QRULES), (False, "position_invalid"))
        self.assertEqual(mo.pixel_source("box_all"), "none")


class EstimatorTests(unittest.TestCase):
    def test_constant_velocity_recovered_with_real_timestamps(self):
        t = np.arange(40) * DT
        xz = np.stack([1.0 + 0.8 * t, 2.0 - 0.6 * t], axis=1)
        seg = np.zeros(40, int)
        e = mo.window_estimate(t, xz, 39, seg, MCFG)
        self.assertAlmostEqual(e["vx"], 0.8, places=9)
        self.assertAlmostEqual(e["vz"], -0.6, places=9)
        self.assertAlmostEqual(e["speed"], 1.0, places=9)
        self.assertAlmostEqual(e["x"], xz[39, 0], places=9)  # filtered position at the current time
        self.assertAlmostEqual(e["lag_s"], 0.25, delta=DT)  # half the window

    def test_insufficient_history(self):
        t = np.arange(5) * DT
        self.assertIsNone(mo.window_estimate(t, np.zeros((5, 2)), 4, np.zeros(5, int), MCFG))

    def test_resets_gap_jump_class(self):
        t = np.array([0, DT, 2 * DT, 0.5, 0.5 + DT, 0.5 + 2 * DT])
        xz = np.array([[0, 0], [0, 0], [0, 0], [0, 0], [2.0, 0], [2.0, 0]], float)
        cls = ["person"] * 5 + ["chair"]
        seg, reasons = mo.segment_track(t, xz, cls, MCFG)
        self.assertEqual(reasons, ["gap", "jump", "class_change"])
        self.assertEqual(list(seg), [0, 0, 0, 1, 2, 3])

    def test_window_stays_inside_segment(self):
        t = np.arange(30) * DT
        xz = np.zeros((30, 2))
        seg = np.array([0] * 25 + [1] * 5)
        self.assertIsNone(mo.window_estimate(t, xz, 29, seg, MCFG))


class LabelTests(unittest.TestCase):
    def test_hysteresis(self):
        self.assertEqual(mo.moving_state(0.4, None, LAB), "moving")
        self.assertEqual(mo.moving_state(0.3, "moving", LAB), "moving")
        self.assertEqual(mo.moving_state(0.3, "stationary", LAB), "stationary")
        self.assertEqual(mo.moving_state(0.3, None, LAB), "unknown")
        self.assertEqual(mo.moving_state(0.1, "moving", LAB), "stationary")

    def test_own_motion_not_camera_motion(self):
        # object velocity component along camera->object: negative = toward the camera
        self.assertEqual(mo.motion_candidate("moving", -0.5, LAB), "approaching")
        self.assertEqual(mo.motion_candidate("moving", 0.5, LAB), "moving_away")
        self.assertEqual(mo.motion_candidate("moving", 0.05, LAB), "moving_lateral")
        self.assertEqual(mo.motion_candidate("stationary", -0.5, LAB), "stationary")

    def test_persistence(self):
        p = mo.Persistent(0.2)
        self.assertEqual(p.update("stationary", 0.0), "unknown")
        self.assertEqual(p.update("stationary", 0.2), "stationary")
        self.assertEqual(p.update("approaching", 0.25), "stationary")  # flicker is held back
        self.assertEqual(p.update("stationary", 0.3), "stationary")
        self.assertEqual(p.update("approaching", 0.4), "stationary")
        self.assertEqual(p.update("approaching", 0.6), "approaching")


class Step8v2Tests(unittest.TestCase):
    def test_class_vote_smooths_flicker(self):
        t = np.arange(8) * 0.1
        cls = ["chair", "chair", "couch", "chair", "chair", "couch", "couch", "couch"]
        v = mo.vote_classes(t, cls, 0.35)  # 4-observation trailing window
        self.assertEqual(v[:5], ["chair"] * 5)  # single flicker ignored
        self.assertEqual(v[5], "chair")  # tie 2-2 keeps the previous vote
        self.assertEqual(v[7], "couch")  # a lasting change is adopted

    def test_no_reset_on_class_change_when_disabled(self):
        t = np.arange(4) * DT
        _, reasons = mo.segment_track(t, np.zeros((4, 2)), ["chair", "couch", "chair", "couch"],
                                      {**MCFG, "reset_on_class_change": False})
        self.assertEqual(reasons, [])

    def test_coverage_flags(self):
        t = np.array([0.0, 0.1, 0.2, 0.3, 0.6, 0.7])
        n = np.array([100, 110, 400, 420, 430, 1000], float)
        f = mo.coverage_flags(t, n, 0.25, 2.0)
        # 400 vs 100/110 within 0.25 s; 420 vs 110 (0.2 s back); 430 has no step inside its window; 1000 vs 430
        self.assertEqual(f.tolist(), [False, False, True, True, False, True])

    def test_uncertainty_scaled_threshold(self):
        lab = {**LAB, "uncertainty_k": 2.0}
        self.assertEqual(mo.moving_state(0.5, None, lab, speed_se=0.05), "moving")  # 0.5 - 0.1 >= 0.35
        self.assertEqual(mo.moving_state(0.5, None, lab, speed_se=0.1), "unknown")  # 0.3 < 0.35, 0.7 > 0.2
        self.assertEqual(mo.moving_state(0.1, None, lab, speed_se=0.2), "unknown")  # upper bound 0.5 > 0.2
        self.assertEqual(mo.moving_state(0.1, None, lab, speed_se=0.02), "stationary")
        self.assertEqual(mo.moving_state(0.5, None, LAB, speed_se=0.1), "moving")  # k = 0: unchanged behaviour


class RouteTests(unittest.TestCase):
    line = np.array([[0.0, 0.0], [0.0, 10.0]])

    def test_distance(self):
        d = mo.polyline_distance(np.array([[3.0, 5.0], [0.0, -2.0]]), self.line)
        np.testing.assert_allclose(d, [3.0, 2.0])

    def test_time_to_route_constant_velocity(self):
        # 2 m from the centreline, corridor half width 0.4 -> edge at 1.6 m; 1 m/s toward it -> 1.6 s
        ttr = mo.time_to_route(np.array([2.0, 5.0]), np.array([[-1.0, 0.0], [1.0, 0.0]]), self.line, 0.4, 5.0, 0.02)
        self.assertAlmostEqual(ttr[0], 1.6, places=6)
        self.assertTrue(math.isnan(ttr[1]))


if __name__ == "__main__":
    unittest.main()
