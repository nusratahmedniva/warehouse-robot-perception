"""hri_perception pure functions with synthetic COCO keypoints (no models, no images, no Unity)."""

import ast
import math
import unittest
from pathlib import Path

import numpy as np

import hri_perception as hpm

CFG = hpm.load_config()
G = CFG["gesture"]
P = CFG["people"]
HERE = Path(__file__).resolve().parents[1]


def person(right_arm_deg=None, left_arm_deg=None, conf=0.9, bend_deg=0.0, length=60.0):
    """A frontal person in a 730 x 530 image. Arm angles are image angles from straight up, + = image right.
    The worker faces the camera, so their right arm (COCO 6, 8, 10) is on the image left, their left on the right.
    A missing angle = arm hanging down. bend_deg rotates the forearm relative to the upper arm."""
    kp = np.zeros((17, 2))
    kc = np.full(17, conf)
    kp[hpm.R_SHOULDER] = (340, 200)
    kp[hpm.L_SHOULDER] = (390, 200)
    for sh, el, wr, ang in ((hpm.R_SHOULDER, hpm.R_ELBOW, hpm.R_WRIST, right_arm_deg),
                            (hpm.L_SHOULDER, hpm.L_ELBOW, hpm.L_WRIST, left_arm_deg)):
        a = 180.0 if ang is None else ang
        upper = np.array([math.sin(math.radians(a)), -math.cos(math.radians(a))]) * length / 2
        b = a + bend_deg if ang is not None else a
        fore = np.array([math.sin(math.radians(b)), -math.cos(math.radians(b))]) * length / 2
        kp[el] = kp[sh] + upper
        kp[wr] = kp[el] + fore
    kp[hpm.L_ANKLE] = (395, 500)
    kp[hpm.R_ANKLE] = (335, 500)
    return kp, kc


def read(**kw):
    return hpm.classify_gesture(*person(**kw), G)[0]


class GestureTests(unittest.TestCase):
    def test_every_command_from_the_robots_point_of_view(self):
        # The worker's RIGHT arm, on the image left, sends the robot LEFT.
        self.assertEqual(read(right_arm_deg=-90), "LEFT")
        self.assertEqual(read(right_arm_deg=-45), "FORWARD_LEFT")
        self.assertEqual(read(right_arm_deg=0), "FORWARD")
        self.assertEqual(read(left_arm_deg=0), "FORWARD")
        self.assertEqual(read(left_arm_deg=45), "FORWARD_RIGHT")
        self.assertEqual(read(left_arm_deg=90), "RIGHT")

    def test_tolerance_band_and_none_between_directions(self):
        tol = G["direction_tolerance_deg"]
        self.assertEqual(read(right_arm_deg=-90 + tol - 0.5), "LEFT")
        self.assertEqual(read(right_arm_deg=-45 - tol + 0.5), "FORWARD_LEFT")
        for between in (-67.5, -22.5, 22.5, 67.5, -90 + tol + 1, 45 - tol - 1):
            self.assertEqual(read(right_arm_deg=between), "NONE", between)

    def test_arms_down_or_missing_give_none(self):
        self.assertEqual(read(), "NONE")
        cmd, detail = hpm.classify_gesture(*person(right_arm_deg=-90, conf=0.2), G)
        self.assertEqual(cmd, "NONE")
        self.assertEqual(detail["why"], "arms not visible")

    def test_one_low_confidence_keypoint_makes_that_arm_unknown(self):
        kp, kc = person(right_arm_deg=-90)
        kc[hpm.R_WRIST] = G["keypoint_confidence"] - 0.01
        self.assertEqual(hpm.classify_gesture(kp, kc, G)[0], "NONE")
        kc[hpm.R_WRIST] = G["keypoint_confidence"]
        self.assertEqual(hpm.classify_gesture(kp, kc, G)[0], "LEFT")

    def test_conflicting_arms_give_none_and_agreeing_arms_count(self):
        self.assertEqual(read(right_arm_deg=-90, left_arm_deg=90), "NONE")
        self.assertEqual(read(right_arm_deg=0, left_arm_deg=0), "FORWARD")

    def test_bent_arm_gives_none(self):
        self.assertEqual(read(right_arm_deg=-90, bend_deg=10), "LEFT")       # slightly bent: still LEFT
        self.assertEqual(read(right_arm_deg=-90, bend_deg=100), "NONE")      # elbow bent hard

    def test_foreshortened_arm_gives_none(self):
        self.assertEqual(read(right_arm_deg=-90, length=20), "NONE")         # arm pointing at the camera

    def test_angle_helpers(self):
        self.assertAlmostEqual(hpm.arm_angle_deg((0, 0), (0, -10)), 0.0)
        self.assertAlmostEqual(hpm.arm_angle_deg((0, 0), (-10, 0)), -90.0)
        self.assertAlmostEqual(hpm.circular_mean_deg(170, -170), 180.0, delta=1e-6)
        self.assertAlmostEqual(abs(hpm.angle_diff_deg(170, -170)), 20.0)

    def test_config_keeps_a_none_band(self):
        bad = dict(CFG, gesture=dict(G, direction_tolerance_deg=25))
        path = HERE / "outputs" / "_tmp_bad_cfg.json"
        path.parent.mkdir(exist_ok=True)
        try:
            path.write_text(__import__("json").dumps(bad))
            with self.assertRaises(ValueError):
                hpm.load_config(path)
        finally:
            path.unlink(missing_ok=True)


class PanoramaPeopleTests(unittest.TestCase):
    H = 512

    def row_for_distance(self, d):
        e = -math.degrees(math.atan(P["camera_height_m"] / d))
        return (0.5 - e / 180.0) * self.H - 0.5

    def test_ground_distance_inverts_the_geometry(self):
        for d in (1.0, 2.0, 5.0, 12.0):
            self.assertAlmostEqual(hpm.ground_distance(self.row_for_distance(d), self.H, P["camera_height_m"]), d, delta=1e-6)
        self.assertIsNone(hpm.ground_distance(100, self.H, 1.5))  # above the horizon

    def test_distance_sources(self):
        v = self.row_for_distance(4.0)
        kp = np.zeros((17, 2))
        kc = np.zeros(17)
        kp[hpm.L_ANKLE] = kp[hpm.R_ANKLE] = (500, v)
        kc[hpm.L_ANKLE] = kc[hpm.R_ANKLE] = 0.9
        box = (490, v - 60, 510, v + 3)
        d, src = hpm.person_distance(box, kp, kc, self.H, P)
        self.assertEqual(src, "ankles")
        self.assertAlmostEqual(d, 4.0, delta=1e-6)
        kc[:] = 0.1                                   # ankles not confident -> box bottom
        d, src = hpm.person_distance(box, kp, kc, self.H, P)
        self.assertEqual(src, "box_bottom")
        self.assertLess(d, 4.0)                       # box bottom is 3 px lower -> a bit closer
        d, src = hpm.person_distance((490, 300, 510, self.H - 1), kp, kc, self.H, P)  # cut off at the bottom
        self.assertEqual((d, src), (None, "unknown"))

    def test_nearest_person_pick(self):
        people = [{"distance_m": 6.0, "box_h": 20}, {"distance_m": 2.5, "box_h": 30}, {"distance_m": -1.0, "box_h": 90}]
        self.assertEqual(hpm.pick_nearest(people), 1)
        self.assertEqual(hpm.pick_nearest([{"distance_m": -1.0, "box_h": 10}, {"distance_m": -1.0, "box_h": 40}]), 1)
        self.assertIsNone(hpm.pick_nearest([]))


class IsolationTests(unittest.TestCase):
    def test_inference_never_imports_ground_truth_or_evaluation(self):
        for name in ("hri_perception.py", "hri_bridge_server.py", "hri_protocol.py"):
            tree = ast.parse((HERE / name).read_text(encoding="utf-8"))
            imported = set()
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    imported |= {a.name.split(".")[0] for a in node.names}
                elif isinstance(node, ast.ImportFrom) and node.module:
                    imported.add(node.module.split(".")[0])
            self.assertFalse(imported & {"hri_eval_dev", "thud_data", "validate_depth"}, (name, imported))
            self.assertNotIn("truth_", (HERE / name).read_text(encoding="utf-8"), name)


if __name__ == "__main__":
    unittest.main()
