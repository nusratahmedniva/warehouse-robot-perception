"""Tests for fuse_objects.py helpers. Run from robot_vision/:  python -m unittest discover -s tests -v"""

import math
import sys
import unittest
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import fuse_objects as fo  # noqa: E402

CFG = {"pixel_selection": {"detector_to_seg_class": {"person": "person"}, "background_seg_classes": ["wall", "floor"],
                           "min_selected_pixels": 4, "min_valid_depth_fraction": 0.5}}
IDS = {"other": 0, "wall": 1, "floor": 2, "person": 4}


class PoseTests(unittest.TestCase):
    def test_yaw_quaternion_xyzw(self):
        a = math.radians(90)  # rotation about +y stored as [x, y, z, w]
        R, t = fo.sensor_pose({"sensor": {"rotation": [0, math.sin(a / 2), 0, math.cos(a / 2)],
                                          "translation": [1.0, 2.0, 3.0]}})
        world = R @ np.array([0.0, 0.0, 1.0]) + t  # camera forward axis
        np.testing.assert_allclose(world, [2.0, 2.0, 3.0], atol=1e-12)

    def test_box_distance(self):
        box = {"t": np.zeros(3), "half": np.array([1.0, 1.0, 1.0]), "R": np.eye(3)}
        self.assertEqual(fo.box_distance(np.array([0.5, 0, 0]), box), 0.0)
        self.assertAlmostEqual(fo.box_distance(np.array([3.0, 0, 0]), box), 2.0)


class SelectionTests(unittest.TestCase):
    def setUp(self):
        self.seg = np.full((10, 10), IDS["wall"], np.uint8)
        self.row = {"x1": 2, "y1": 2, "x2": 6, "y2": 6, "class_name": "person"}

    def test_prefers_matching_seg_class(self):
        self.seg[3:5, 3:5] = IDS["person"]
        ys, xs, method, region = fo.select_pixels(self.row, self.seg, CFG, IDS)
        self.assertEqual((method, len(ys), region), ("seg_class_person", 4, 16))

    def test_falls_back_to_non_background(self):
        self.seg[2:4, 2:4] = IDS["other"]
        _, _, method, _ = fo.select_pixels(self.row, self.seg, CFG, IDS)
        self.assertEqual(method, "box_minus_background")

    def test_all_background_is_flagged(self):
        _, _, method, _ = fo.select_pixels(self.row, self.seg, CFG, IDS)
        self.assertEqual(method, "box_all")


if __name__ == "__main__":
    unittest.main()
