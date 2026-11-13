"""Tests of paper_v4/figures_v4.py (result-neutral figure code; not part of robot_vision/tests, which is Anisha's).
From the repository root: robot_vision/.venv/Scripts/python.exe -m unittest discover -s paper_v4 -p "test_*.py"
"""

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import figures_v4 as fv  # noqa: E402


class LightTests(unittest.TestCase):
    def test_states_map_to_the_light_ring_colours(self):
        for state, light in [("navigate", "driving"), ("execute", "driving"), ("scan", "searching"), ("approach", "searching"),
                             ("ask", "asking"), ("read", "asking"), ("wait", "asking"), ("aborted", "stopped"),
                             ("safety_stopped", "stopped"), ("done", "idle"), ("", "idle")]:
            self.assertEqual(fv.light(state), light, state)
        self.assertEqual(set(fv.STATE), {"driving", "searching", "asking", "stopped", "idle"})


class DistanceTests(unittest.TestCase):
    def test_without_and_with_come_from_the_same_pixels(self):
        h, ankle = 1.6, 0.0927
        true_cot = 2.0 / (h - ankle)                 # an ankle 2.0 m away seen at this angle
        est_with = (h - ankle) * true_cot            # what P1 computes
        without, with_c = fv.distance_without_and_with(est_with, h, ankle, ankle)
        self.assertAlmostEqual(with_c, 2.0, places=9)
        self.assertAlmostEqual(without, h * true_cot, places=9)          # the ankles taken as floor points: too long
        self.assertGreater(without, with_c)

    def test_a_session_run_before_p1_is_corrected_by_the_measured_value(self):
        h, measured = 1.6, 0.0927
        est_before = h * (2.0 / (h - measured))      # recorded with ankle 0 (before P1)
        without, with_c = fv.distance_without_and_with(est_before, h, 0.0, measured)
        self.assertAlmostEqual(without, est_before, places=9)
        self.assertAlmostEqual(with_c, 2.0, places=9)


class ConfigTests(unittest.TestCase):
    def test_camera_height_is_read_from_the_sessions_own_config(self):
        with tempfile.TemporaryDirectory() as d:
            u = Path(d) / "trials_development_Task2_x"
            (u / "config_used").mkdir(parents=True)
            (u / "config_used" / "robot_unity_v4.json").write_text(json.dumps({"camera_360": {"height_m": 1.45}}), encoding="utf-8")
            self.assertEqual(fv.camera_height_of(u), 1.45)

    def test_ankle_of_a_session_without_the_p1_config_is_zero(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertEqual(fv.ankle_of(Path(d)), 0.0)


if __name__ == "__main__":
    unittest.main()
