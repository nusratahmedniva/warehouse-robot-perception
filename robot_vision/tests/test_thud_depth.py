"""Tests for thud_depth.py. Run from robot_vision/:  python -m unittest discover -s tests -v"""

import json
import math
import sys
import unittest
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import thud_data as td  # noqa: E402
import thud_depth as tdd  # noqa: E402

# dataset location from configs/office.json (or THUD_DATASET_ROOT); no drive letter in code
CAPTURE = Path(td.load_config(ROOT / "configs" / "office.json")["capture_dir"])


class DecodeTests(unittest.TestCase):
    def setUp(self):
        self.cfg = tdd.load_depth_config()

    def test_config_values(self):
        self.assertEqual(self.cfg["encoding"], "linear_planar_z")
        self.assertEqual(self.cfg["far_m"], 10.0)
        self.assertEqual(self.cfg["intrinsics"]["vertical_fov_deg"], 60.0)

    def test_linear_scale_and_saturation(self):
        raw = np.array([[0, 6553, 32767, 65534, 65535]], dtype=np.uint16)
        depth, valid = tdd.decode_depth(raw, self.cfg["far_m"])
        np.testing.assert_allclose(depth[0, :4], raw[0, :4] * 10.0 / 65535)
        self.assertAlmostEqual(depth[0, 1], 1.0, places=3)
        self.assertTrue(valid[0, :4].all())
        self.assertFalse(valid[0, 4])
        self.assertTrue(math.isnan(depth[0, 4]))

    def test_intrinsics_from_fov(self):
        k = tdd.pixel_intrinsics(730, 530, 60.0)
        self.assertAlmostEqual(k["fx"], 265 / math.tan(math.radians(30)), places=9)
        self.assertEqual(k["fx"], k["fy"])
        self.assertEqual((k["cx"], k["cy"]), (365.0, 265.0))

    def test_backproject_round_trip(self):
        k = tdd.pixel_intrinsics(730, 530, 60.0)
        p = np.array([1.2, -0.7, 4.0])  # x right, y up, z forward
        u = k["fx"] * p[0] / p[2] + k["cx"] - 0.5
        v = k["cy"] - k["fy"] * p[1] / p[2] - 0.5
        np.testing.assert_allclose(tdd.backproject(np.array(u), np.array(v), np.array(p[2]), k), p, atol=1e-12)


@unittest.skipUnless(CAPTURE.is_dir(), "THUD dataset not available")
class DatasetTests(unittest.TestCase):
    def test_chair_inside_its_3d_box(self):
        """Office/dynamic/Capture_1 step 0, chair instance 52: decoded pixels lie inside its 3D box."""
        from PIL import Image
        from validate_depth import load_records, quat_matrix

        cfg = tdd.load_depth_config()
        recs = load_records(CAPTURE)
        c0, c1 = recs[("camera_0", 0)], recs[("camera", 0)]
        ann = {a["id"]: a for a in c0["annotations"]}
        colour = next(v["color"] for v in ann["instance segmentation"]["values"] if v["instance_id"] == 52)
        box = next(v for a in c1["annotations"] if a["id"] == "bounding box 3D" for v in a["values"]
                   if v["instance_id"] == 52)
        inst = np.array(Image.open(CAPTURE / "Label" / "Instance" /
                                   Path(ann["instance segmentation"]["filename"]).name).convert("RGBA"))
        ys, xs = np.nonzero((inst[..., 0] == colour["r"]) & (inst[..., 1] == colour["g"]) & (inst[..., 2] == colour["b"]))
        raw = tdd.load_raw_depth(CAPTURE / "Depth" / "depth_2.png")
        depth, valid = tdd.decode_depth(raw, cfg["far_m"])
        k = tdd.pixel_intrinsics(raw.shape[1], raw.shape[0], cfg["intrinsics"]["vertical_fov_deg"])
        keep = valid[ys, xs]
        pts = tdd.backproject(xs[keep], ys[keep], depth[ys[keep], xs[keep]], k)
        t = np.array([box["translation"][a] for a in "xyz"])
        half = np.array([box["size"][a] for a in "xyz"]) / 2
        local = (pts - t) @ quat_matrix(box["rotation"])
        inside = (np.abs(local) <= half + 0.01).all(axis=1)
        self.assertGreater(len(pts), 1000)
        self.assertGreaterEqual(inside.mean(), 0.99)


if __name__ == "__main__":
    unittest.main()
