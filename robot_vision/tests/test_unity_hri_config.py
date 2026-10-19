"""The Unity guided-robot config (hri_config.json) holds the spec values, a relative output root and two seeds.

Reads only the JSON file; no Unity needed. The C# defaults in HriConfig.cs are checked by the Unity edit-mode
tests (Assets/Tests/EditMode).
"""

import json
import unittest
from pathlib import Path, PurePosixPath, PureWindowsPath

REPO = Path(__file__).resolve().parents[2]
UNITY_PROJECT = REPO / "unity" / "Robotics-Warehouse" / "WarehouseProjectURP"
CONFIG = UNITY_PROJECT / "Assets" / "StreamingAssets" / "WarehouseHRI" / "hri_config.json"


class UnityHriConfigTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cfg = json.loads(CONFIG.read_text(encoding="utf-8"))

    def test_spec_values(self):
        c = self.cfg
        self.assertEqual(c["trials"]["success_radius_m"], 0.3)
        self.assertEqual(c["brain"]["approach_distance_m"], 2.0)
        self.assertEqual(c["brain"]["gesture_hold_s"], 1.0)
        self.assertEqual(c["brain"]["max_asks"], 2)  # ask, ask once more, then abort
        self.assertEqual(c["link"]["watchdog_s"], 0.3)
        self.assertEqual(c["telemetry"]["interval_s"], 0.1)
        self.assertEqual(c["cameras"]["cam360_interval_s"], 0.1)
        self.assertEqual((c["cameras"]["gesture_width_px"], c["cameras"]["gesture_height_px"]), (730, 530))
        self.assertEqual(c["cameras"]["gesture_vfov_deg"], 60)

    def test_safety_stop_is_inside_the_approach_distance(self):
        b = self.cfg["brain"]
        self.assertLess(b["safety_stop_distance_m"], b["approach_distance_m"])
        self.assertGreater(b["safety_corridor_half_width_m"], self.cfg["robot"]["width_m"] / 2)

    def test_seeds_and_modes(self):
        t = self.cfg["trials"]
        self.assertNotEqual(t["dev_seed"], t["final_seed"])
        self.assertIn(t["mode"], ("development", "final"))
        self.assertIn(t["task"], ("Task1", "Task2"))
        if t["mode"] == "final":
            self.assertTrue(self.cfg["frozen"], "final trials need frozen thresholds")

    def test_output_root_is_relative_and_git_ignored(self):
        root = self.cfg["output_root"]
        self.assertFalse(PurePosixPath(root).is_absolute() or PureWindowsPath(root).is_absolute()
                         or PureWindowsPath(root).drive, root)
        resolved = (UNITY_PROJECT / root).resolve()
        self.assertTrue(resolved.is_relative_to(REPO), resolved)
        self.assertIn("outputs", resolved.parts, "outputs/ is git-ignored")


if __name__ == "__main__":
    unittest.main()
