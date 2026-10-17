"""Device selection (CUDA -> MPS -> CPU) with mocked availability, and the data-split guard.
Run from robot_vision/:  python -m unittest discover -s tests -v"""

import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import data_splits as ds  # noqa: E402

try:
    import torch  # noqa: F401

    import check_environment as ce
except ImportError:  # torch not installed
    ce = None


@unittest.skipIf(ce is None, "PyTorch not installed")
class DeviceSelectionTests(unittest.TestCase):
    """check_environment.select_device is used by run_segmentation.py and track_objects.py (default --device auto)."""

    def pick(self, cuda: bool, mps: bool, mode: str = "auto") -> str:
        with mock.patch.object(ce.torch.cuda, "is_available", return_value=cuda), \
                mock.patch.object(ce.torch.backends.mps, "is_available", return_value=mps):
            return ce.select_device(mode).type

    def test_auto_prefers_cuda_then_mps_then_cpu(self):
        self.assertEqual(self.pick(cuda=True, mps=True), "cuda")
        self.assertEqual(self.pick(cuda=False, mps=True), "mps")
        self.assertEqual(self.pick(cuda=False, mps=False), "cpu")

    def test_explicit_modes_never_fall_back(self):
        with self.assertRaises(RuntimeError):
            self.pick(cuda=False, mps=True, mode="cuda")
        with self.assertRaises(RuntimeError):
            self.pick(cuda=True, mps=False, mode="mps")
        self.assertEqual(self.pick(cuda=True, mps=True, mode="cpu"), "cpu")

    def test_inference_scripts_default_to_auto(self):
        root = Path(__file__).resolve().parents[1]
        for script in ("run_segmentation.py", "track_objects.py"):
            text = (root / script).read_text(encoding="utf-8")
            self.assertIn('"--device", default="auto"', text, script)


class SplitGuardTests(unittest.TestCase):
    def setUp(self):
        self.splits = ds.load()

    def test_split_lookup(self):
        self.assertEqual(ds.split_of("Synthetic_Scenes/Office/dynamic/Capture_1", self.splits), "development")
        self.assertEqual(ds.split_of("Synthetic_Scenes/Office/dynamic/Capture_2", self.splits), "adjustment")
        self.assertEqual(ds.split_of("Synthetic_Scenes/Office/dynamic/Capture_4", self.splits), "final_evaluation")
        self.assertEqual(ds.split_of("Synthetic_Scenes/Gym/dynamic/Capture_5", self.splits), "cross_scene_final_evaluation")
        self.assertEqual(ds.split_of("Synthetic_Scenes/Gym/dynamic/Capture_1", self.splits), "excluded")
        self.assertIsNone(ds.split_of("Synthetic_Scenes/Gym/static/Capture_1", self.splits))

    def test_guard(self):
        for key in ("Synthetic_Scenes/Office/dynamic/Capture_3", "Synthetic_Scenes/Gym/dynamic/Capture_2"):
            with self.assertRaises(SystemExit):
                ds.guard(key, False, self.splits)
            self.assertIn(ds.guard(key, True, self.splits), self.splits["final_evaluation_splits"])
        self.assertEqual(ds.guard("Synthetic_Scenes/Office/dynamic/Capture_2", False, self.splits), "adjustment")
        with self.assertRaises(SystemExit):  # the flag is only for final-evaluation captures
            ds.guard("Synthetic_Scenes/Office/dynamic/Capture_2", True, self.splits)

    def test_exclusion_wins_in_either_entry_order(self):
        gym1, wild = "Synthetic_Scenes/Gym/dynamic/Capture_1", "Synthetic_Scenes/Gym/dynamic/*"
        orders = {"exclusion before wildcard": [(gym1, "excluded"), (wild, "cross_scene_final_evaluation")],
                  "exclusion after wildcard": [(wild, "cross_scene_final_evaluation"), (gym1, "excluded")],
                  "excluded by pattern": [(wild, "cross_scene_final_evaluation"), ("*/Gym/dynamic/Capture_1", "excluded")]}
        for name, entries in orders.items():
            splits = {**self.splits, "captures": dict(entries)}
            with self.subTest(name):
                self.assertEqual(ds.split_of(gym1, splits), "excluded")
                for flag in (False, True):  # refused with and without --final-evaluation
                    with self.assertRaises(SystemExit):
                        ds.guard(gym1, flag, splits)
                self.assertEqual(ds.guard("Synthetic_Scenes/Gym/dynamic/Capture_2", True, splits),
                                 "cross_scene_final_evaluation")

    def test_repo_config_refuses_gym_capture_1(self):
        for flag in (False, True):
            with self.assertRaises(SystemExit):
                ds.guard("Synthetic_Scenes/Gym/dynamic/Capture_1", flag, self.splits)

    def test_capture_key(self):
        self.assertEqual(ds.capture_key(Path("/data/RGB-D/Synthetic_Scenes/Gym/dynamic/Capture_2"), Path("/data/RGB-D")),
                         "Synthetic_Scenes/Gym/dynamic/Capture_2")


if __name__ == "__main__":
    unittest.main()
