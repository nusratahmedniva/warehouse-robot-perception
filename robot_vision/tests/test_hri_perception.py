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


# The classifier takes any set of centres; the five-direction set tests the bins, the shipped config has three.
G5 = dict(G, direction_centres_deg={**G["direction_centres_deg"], **G["dropped_directions"]})


def read5(**kw):
    return hpm.classify_gesture(*person(**kw), G5)[0]


class GestureTests(unittest.TestCase):
    def test_every_command_from_the_robots_point_of_view(self):
        # The worker's RIGHT arm, on the image left, sends the robot LEFT.
        self.assertEqual(read(right_arm_deg=-90), "LEFT")
        self.assertEqual(read(right_arm_deg=0), "FORWARD")
        self.assertEqual(read(left_arm_deg=0), "FORWARD")
        self.assertEqual(read(left_arm_deg=90), "RIGHT")
        self.assertEqual(read5(right_arm_deg=-45), "FORWARD_LEFT")
        self.assertEqual(read5(left_arm_deg=45), "FORWARD_RIGHT")

    def test_diagonals_dropped_in_the_shipped_config(self):
        self.assertEqual(set(G["direction_centres_deg"]), {"LEFT", "FORWARD", "RIGHT"})
        for a in (-45, 45, -45 + G["direction_tolerance_deg"] - 0.5):
            self.assertEqual(read(right_arm_deg=a), "NONE", a)
            self.assertEqual(read(left_arm_deg=a), "NONE", a)

    def test_tolerance_band_and_none_between_directions(self):
        tol = G["direction_tolerance_deg"]
        self.assertEqual(read(right_arm_deg=-90 + tol - 0.5), "LEFT")
        self.assertEqual(read5(right_arm_deg=-45 - tol + 0.5), "FORWARD_LEFT")
        for between in (-67.5, -22.5, 22.5, 67.5, -90 + tol + 1, 45 - tol - 1):
            self.assertEqual(read5(right_arm_deg=between), "NONE", between)

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
        bad = dict(CFG, gesture=dict(G, direction_tolerance_deg=45))   # half the 90 deg spacing: no NONE band left
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
        for name in ("hri_perception.py", "bridge/perception.py"):
            tree = ast.parse((HERE / name).read_text(encoding="utf-8"))
            imported = set()
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    imported |= {a.name.split(".")[0] for a in node.names}
                elif isinstance(node, ast.ImportFrom) and node.module:
                    imported.add(node.module.split(".")[0])
            self.assertFalse(imported & {"hri_eval_dev", "thud_data", "validate_depth"}, (name, imported))


class PanoramaBearingTests(unittest.TestCase):
    def test_measured_axis(self):
        # Measured in Unity (both pipelines): world +x right of the centre column, world +z at the centre.
        self.assertAlmostEqual(hpm.pano_world_yaw(1535, 2048), 90.0, delta=0.2)
        self.assertAlmostEqual(hpm.pano_world_yaw(1023.5, 2048), 0.0, delta=1e-9)

    def test_bearing_relative_to_heading(self):
        self.assertAlmostEqual(hpm.pano_bearing(1535, 2048, 90.0), 0.0, delta=0.2)
        self.assertAlmostEqual(hpm.pano_bearing(1535, 2048, 0.0), 90.0, delta=0.2)
        self.assertAlmostEqual(hpm.pano_bearing(511, 2048, 0.0), -90.0, delta=0.2)
        self.assertTrue(-180.0 <= hpm.pano_bearing(0, 2048, 0.0) < 180.0)

    def test_header_camera_height_overrides_the_config(self):
        kp, kc = np.zeros((17, 2)), np.zeros(17)
        e = -math.degrees(math.atan(1.6 / 4.0))
        v = (90 - e) / 180 * 1024 - 0.5
        kp[hpm.L_ANKLE] = kp[hpm.R_ANKLE] = (500, v)
        kc[hpm.L_ANKLE] = kc[hpm.R_ANKLE] = 0.9
        d, _ = hpm.person_distance((490, v - 90, 510, v + 2), kp, kc, 1024, P, camera_height_m=1.6)
        self.assertAlmostEqual(d, 4.0, delta=1e-6)


class WarmUpTests(unittest.TestCase):
    """The warm-up (infrastructure, 2026-10-21) runs the live calls on frames of the live sizes and leaves no tracker
    state behind. No models: a stand-in records the calls."""

    def test_sizes_are_the_unity_camera_sizes(self):
        import json
        unity = json.loads((HERE.parent / "unity" / "Robotics-Warehouse" / "WarehouseProjectURP" / "Assets" / "WarehouseRobot"
                            / "Robot" / "Config" / "robot_unity.json").read_text(encoding="utf-8"))
        c360, pt = unity["camera_360"], unity["pan_tilt_camera"]
        self.assertEqual(hpm.WARM_UP_SIZES["frame_360"], (c360["height_px"], c360["width_px"]))
        self.assertEqual(hpm.WARM_UP_SIZES["frame_pan_tilt"], (pt["height_px"], pt["width_px"]))

    def test_warm_up_frame_has_the_size_and_content(self):
        try:
            import cv2  # noqa: F401
            from ultralytics.utils import ASSETS  # noqa: F401
        except ImportError:
            self.skipTest("OpenCV / Ultralytics not installed")
        img = hpm.warm_up_frame(530, 730)
        self.assertEqual(img.shape, (530, 730, 3))
        self.assertGreater(float(img.std()), 10.0)   # the sample photos are pasted in, not a blank frame

    def test_warm_up_uses_the_live_calls_and_resets_the_tracker(self):
        try:
            import cv2  # noqa: F401
            from ultralytics.utils import ASSETS  # noqa: F401
        except ImportError:
            self.skipTest("OpenCV / Ultralytics not installed")

        class Tracker:
            resets = 0

            def reset(self):
                Tracker.resets += 1

        class Stand(hpm.HriPerception):
            def __init__(self):            # no models
                self.cfg = hpm.load_config(hpm.DEFAULT_CONFIG)
                self.calls = []
                self.pano_model = type("M", (), {"predictor": type("P", (), {"trackers": [Tracker()]})()})()

            def people(self, bgr, heading_deg, top_deg=90.0, bottom_deg=-90.0, camera_height_m=None, centre_world_yaw_deg=0.0):
                self.calls.append(("people", bgr.shape, Tracker.resets))
                return [], 0.0

            def gesture(self, bgr, timestamp):
                self.calls.append(("gesture", bgr.shape, Tracker.resets))
                return "NONE", 0.0, {}, {}

        s = Stand()
        s._warm_up()
        self.assertEqual([c[0] for c in s.calls], ["people", "gesture"] * 3)
        self.assertEqual({c[1] for c in s.calls if c[0] == "people"}, {(1024, 2048, 3)})
        self.assertEqual({c[1] for c in s.calls if c[0] == "gesture"}, {(530, 730, 3)})
        self.assertEqual({c[2] for c in s.calls}, {0})   # every call before the reset ...
        self.assertEqual(Tracker.resets, 1)               # ... and the tracker reset once at the end


class BandTests(unittest.TestCase):
    def test_band_rows_map_to_elevation_and_distance(self):
        # 2048 x 512 band from +30 to -60 deg: 90 deg over 512 rows, horizon at row 512 / 3.
        self.assertAlmostEqual(hpm.pano_elevation_deg(-0.5, 512, 30, -60), 30.0)
        self.assertAlmostEqual(hpm.pano_elevation_deg(511.5, 512, 30, -60), -60.0)
        e = -math.degrees(math.atan(1.5 / 4.0))
        v = (30 - e) / 90 * 512 - 0.5
        self.assertAlmostEqual(hpm.ground_distance(v, 512, 1.5, 30, -60), 4.0, delta=1e-6)


if __name__ == "__main__":
    unittest.main()
