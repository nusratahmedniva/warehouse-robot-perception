"""calibrate_v4.py (P4, 2026-11-12): the B12 choice, the look guard and the in-place config writing. No data, no models."""

import json
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import calibrate_v4 as cal  # noqa: E402


def row(value, acc, cov):
    return {"value": value, "accuracy": acc, "coverage": cov}


class B12Tests(unittest.TestCase):
    def test_highest_accuracy_among_coverage_at_least_08(self):
        rows = [row(1, 0.99, 0.5), row(2, 0.90, 0.85), row(3, 0.95, 0.80)]
        self.assertEqual(cal.choose_b12(rows, 2)[0], 3)                  # 0.99 has too little coverage

    def test_ties_go_to_the_v3_value_then_the_more_conservative(self):
        rows = [row(30, 0.9, 0.95), row(45, 0.9, 0.85), row(60, 0.9, 0.82)]
        self.assertEqual(cal.choose_b12(rows, 30, v3_value=45), (45, "tie: the v3 value"))
        value, why = cal.choose_b12(rows, 30)
        self.assertEqual(value, 60)
        self.assertIn("conservative", why)

    def test_nothing_qualifies_keeps_the_committed_value(self):
        rows = [row(1, 1.0, 0.5), row(2, None, 0.0)]
        value, why = cal.choose_b12(rows, 7)
        self.assertEqual(value, 7)
        self.assertIn("committed value kept", why)

    def test_full_tie_keeps_the_committed_value(self):
        rows = [row(0.2, 0.9, 0.9), row(0.3, 0.9, 0.9)]
        self.assertEqual(cal.choose_b12(rows, 0.3)[0], 0.3)


class GuardAndWriteTests(unittest.TestCase):
    def test_only_the_two_development_looks(self):
        cal.guard_looks([SimpleNamespace(looks={"sunbox_m1"}), SimpleNamespace(looks={"sunbox_f1"})])
        with self.assertRaises(SystemExit):
            cal.guard_looks([SimpleNamespace(looks={"sunbox_f2"})])

    def test_set_json_value_changes_one_number_in_its_block(self):
        text = json.dumps({"window": {"window_s": 1.0, "x": 2}, "proceed": {"window_s": 2.0}}, indent=2)
        out = cal.set_json_value(text, ("proceed", "window_s"), 2.5)
        d = json.loads(out)
        self.assertEqual((d["window"]["window_s"], d["proceed"]["window_s"]), (1.0, 2.5))
        self.assertEqual(len(out.splitlines()), len(text.splitlines()))
        self.assertEqual(json.loads(cal.set_json_value(text, ("window", "window_s"), 1.5))["window"]["window_s"], 1.5)

    def test_every_grid_path_exists_in_its_config(self):
        import commander_v4 as cm
        import gesture_motion as gm
        import hri_control_v4 as hv
        cfgs = {"reader": gm.load_config(), "commander": cm.load_config(), "control": hv.load_control()[1]}
        for kind, path, grid, v3 in cal.GRIDS:
            committed = cal._get(cfgs[kind], path)
            self.assertIsInstance(committed, (int, float), path)
            self.assertGreaterEqual(len(grid), 3, path)
            if v3 is not None:
                self.assertIn(v3, grid, path)


if __name__ == "__main__":
    unittest.main()
