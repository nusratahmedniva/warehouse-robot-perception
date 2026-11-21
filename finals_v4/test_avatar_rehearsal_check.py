"""Tests of avatar_rehearsal_check.py (Avatar/Config/experiments_ab.md section 15 addendum 10): the timing rule (every frame within 0.100 s
of its 0.1 s mark, steps at most 0.2 s, strictly increasing), the play-only call and the verdict. No frame is read and no model runs.
Run from the repository root (CI runs robot_vision/tests only, so this suite is run by hand):
    Windows: robot_vision\\.venv\\Scripts\\python.exe -m unittest discover -s finals_v4 -p "test_*.py"
    macOS:   robot_vision/.venv/bin/python -m unittest discover -s finals_v4 -p "test_*.py"
"""
from __future__ import annotations

import contextlib
import io
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import avatar_rehearsal_check as arc  # noqa: E402


def from_steps(steps, start=1000.0):
    t = [start]
    for s in steps:
        t.append(t[-1] + s)
    return t


def grid(n, start=1000.0):
    return [start + 0.1 * i for i in range(n)]


# Two sequences flagged by the old rule on 2026-11-20 (avatar_rehearsal_check_20261121_001920/report.json, steps rounded to 3 decimals)
WORST_NONE = [0.102, 0.112, 0.177, 0.049, 0.074, 0.092, 0.101, 0.111, 0.09, 0.096]          # sunbox_f2__NONE__2.0__s1_j1
WORST_PROCEED = [0.108, 0.098, 0.096, 0.117, 0.098, 0.096, 0.09, 0.172, 0.036, 0.097, 0.097,
                 0.096, 0.117, 0.09, 0.098, 0.099, 0.096, 0.107, 0.097, 0.101]                # sunbox_m_tshirt_black__PROCEED__2.0__left_s2_j2_proceed_ik_02


class TimingRule(unittest.TestCase):
    def test_exact_grid_passes(self):
        self.assertIsNone(arc.timing_problem(grid(11), "POINT"))
        self.assertAlmostEqual(float(max(abs(arc.timing_offsets(grid(11), "POINT")))), 0.0, places=9)

    def test_late_frame_then_short_step_passes(self):
        # frame 3 rendered 64 ms late, frame 4 back on the grid: a step of 0.036 s, which the old 0.09 s lower bound refused
        t = from_steps([0.1, 0.1, 0.164, 0.036, 0.1, 0.1, 0.1, 0.1, 0.1, 0.1])
        self.assertIsNone(arc.timing_problem(t, "WAIT"))

    def test_the_flagged_sequences_of_2026_11_20_pass(self):
        self.assertIsNone(arc.timing_problem(from_steps(WORST_NONE), "NONE"))
        self.assertIsNone(arc.timing_problem(from_steps(WORST_PROCEED), "PROCEED"))
        self.assertLess(float(max(abs(arc.timing_offsets(from_steps(WORST_NONE), "NONE")))), 0.092)

    def test_a_frame_0_100_s_from_its_mark_fails(self):
        # two long steps (each under 0.2 s) put frames 4.. 0.10005 s behind their marks
        why = arc.timing_problem(from_steps([0.1, 0.1, 0.15, 0.15005, 0.1, 0.1, 0.1, 0.1, 0.1, 0.1]), "STOP")
        self.assertIsNotNone(why)
        self.assertIn("from its mark", why)
        self.assertNotIn("step over", why)

    def test_just_inside_the_tolerance_passes(self):
        self.assertIsNone(arc.timing_problem(from_steps([0.1, 0.1, 0.15, 0.1498, 0.1, 0.1, 0.1, 0.1, 0.1, 0.1]), "STOP"))   # 0.0998 s behind

    def test_slow_drift_fails_although_every_step_is_between_0_09_and_0_2(self):
        t = from_steps([0.111] * 10)                         # 11 ms behind per frame: 0.110 s behind at frame 10
        why = arc.timing_problem(t, "POINT")
        self.assertIsNotNone(why)
        self.assertIn("from its mark", why)

    def test_equal_or_decreasing_times_fail(self):
        t = grid(11)
        t[6] = t[5]
        self.assertIn("not strictly increasing", arc.timing_problem(t, "POINT"))
        t = grid(11)
        t[6] = t[5] - 0.01
        self.assertIn("not strictly increasing", arc.timing_problem(t, "POINT"))

    def test_a_step_over_0_2_fails(self):
        t = grid(11)
        t = t[:5] + [x + 0.15 for x in t[5:]]
        self.assertIn("step over 0.2", arc.timing_problem(t, "POINT"))

    def test_proceed_marks_carry_the_1_ms(self):
        t = [1000.0] + [1000.0 + 0.1 * i + 0.001 for i in range(1, 21)]
        self.assertAlmostEqual(float(max(abs(arc.timing_offsets(t, "PROCEED")))), 0.0, places=9)
        self.assertAlmostEqual(float(max(abs(arc.timing_offsets(t, "POINT")))), 0.001, places=9)

    def test_a_single_frame_has_no_timing(self):
        self.assertIsNone(arc.timing_problem([1000.0], "POINT"))


class PlayOnlyAndVerdict(unittest.TestCase):
    def test_edit_is_optional(self):
        a = arc.parser().parse_args(["--play", "look_check_play_ab_20261121_000000", "--delete-frames"])
        self.assertEqual(a.edit, "")
        self.assertTrue(a.delete_frames)
        with self.assertRaises(SystemExit), contextlib.redirect_stderr(io.StringIO()):
            arc.parser().parse_args(["--edit", "look_check_ab_20261121_000000"])        # --play stays required

    @staticmethod
    def clean_part(name):
        return {"part": name, "missing_groups": [], "problem_count": 0, "sequence_count_problems": [], "timing_problems": [],
                "error_shader_frame_count": 0}

    def test_play_only_verdict_leaves_the_edit_part_out(self):
        report = {"edit": {"part": "edit", "not_checked": "no --edit given"}, "play": self.clean_part("play"), "truth_play": {"refused": []}}
        self.assertTrue(arc.verdict(report))
        report["play"]["timing_problems"] = ["x: a frame 0.120 s from its mark"]
        self.assertFalse(arc.verdict(report))

    def test_missing_groups_still_fail(self):
        report = {"edit": self.clean_part("edit"), "play": self.clean_part("play"), "truth_play": {"refused": []}}
        report["play"]["missing_groups"] = ["anime_f_01 POINT 2.0 left"]
        self.assertFalse(arc.verdict(report))

    def test_a_part_without_its_recording_folder_fails(self):
        with tempfile.TemporaryDirectory() as d:
            part = arc.check_folder("play", Path(d), [], {}, {})                       # returns before any config is read
        self.assertEqual(part["problem_count"], 1)
        report = {"edit": {"part": "edit", "not_checked": "play-only"}, "play": part, "truth_play": {"refused": []}}
        self.assertFalse(arc.verdict(report))


if __name__ == "__main__":
    unittest.main()
