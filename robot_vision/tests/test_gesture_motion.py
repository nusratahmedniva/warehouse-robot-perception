"""v4 moving-gesture reader (gesture_motion.py) on synthetic keypoint sequences: POINT geometry (in-plane, toward, away,
off-axis, pan and robot yaw, noise), WAIT / STOP hand cues, moving vs still, both arms, missing hand and keypoints."""

import json
import sys
import unittest
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))

import gesture_motion as gm  # noqa: E402
import v4_synth as vs  # noqa: E402

CFG = gm.load_config()
RNG = np.random.default_rng(7)


def sample_for(left=vs.DOWN, right=vs.DOWN, hands=None, **kw):
    kp, conf = vs.body(left=left, right=right, **kw.pop("body", {}))
    return vs.sample(0.0, kp, conf, hands or {}, **kw)


class GeometryTests(unittest.TestCase):
    def sol(self, az, elev=0.0, z=2.0, x0=0.0, side="left"):
        kw = {side: vs.direction(az, elev)}
        s = sample_for(body={"z0": z, "x0": x0}, **kw)
        return gm.arm_solutions(s, side, CFG)

    def test_in_plane_arm_has_its_true_azimuth_among_the_solutions(self):
        for az in (90.0, -90.0):
            side = "left" if az > 0 else "right"
            sol = self.sol(az, side=side)
            self.assertAlmostEqual(sol["away"][0], az, delta=2.0)          # the wrist at the depth of the shoulder
            self.assertAlmostEqual(sol["phi_deg"], 0.0, delta=2.0)
            self.assertTrue(sol["two"])                                    # and a second, out-of-plane reading of the same pixels

    def assert_same_wrist_ray(self, s, side, sol, name):
        """A solution is a valid arm: its length is the arm length and shoulder + arm lies on the wrist's pixel ray."""
        sh, _, wr = gm.ARMS[side]
        ray = lambda xy: np.array([(xy[0] - s.cx) / s.fx, (xy[1] - s.cy) / s.fy, 1.0])
        rs, rw = ray(s.kp[sh]), ray(s.kp[wr])
        k = CFG["point"]["arm_length_in_shoulder_widths"] * np.linalg.norm((ray(s.kp[gm.L_SHOULDER]) - ray(s.kp[gm.R_SHOULDER]))[:2])
        az, el = (np.radians(sol[name][0]), np.radians(sol[name][1]))
        d = k * np.array([np.cos(el) * np.sin(az), -np.sin(el), np.cos(el) * np.cos(az)])
        tip = rs + d
        self.assertLess(np.linalg.norm(np.cross(tip / np.linalg.norm(tip), rw / np.linalg.norm(rw))), 1e-3, name)

    def test_out_of_plane_arm_has_two_solutions_one_is_true(self):
        for az in (40.0, 140.0, -50.0):
            side = "right" if az < 0 else "left"
            s = sample_for(**{side: vs.direction(az)})
            sol = gm.arm_solutions(s, side, CFG)
            self.assertTrue(sol["two"], az)
            family = "away" if abs(az) < 90 else "toward"
            self.assertAlmostEqual(sol[family][0], az, delta=3.0, msg=az)          # the true arm is one of the two
            for name in ("away", "toward"):
                self.assert_same_wrist_ray(s, side, sol, name)                       # both are consistent with the image
            self.assertGreater(abs(gm.wrap(sol["away"][0] - sol["toward"][0])), 40.0)
        self.assertAlmostEqual(self.sol(40.0)["phi_deg"], 50.0, delta=3.0)

    def test_negative_side_and_elevation(self):
        sol = self.sol(-30.0, elev=25.0, side="right")
        self.assertAlmostEqual(sol["away"][0], -30.0, delta=3.0)
        self.assertAlmostEqual(sol["away"][1], 25.0, delta=3.0)
        self.assertLess(sol["toward"][0], -90.0)

    def test_off_axis_person(self):
        for x0 in (-1.0, 1.2):
            sol = self.sol(90.0, x0=x0)                   # the true arm is one of the two roots (which one depends on the side)
            self.assertLess(min(abs(sol[n][0] - 90.0) for n in ("away", "toward")), 2.0, x0)
        sol = self.sol(140.0, x0=1.2)
        self.assertLess(min(abs(sol[n][0] - 140.0) for n in ("away", "toward")), 3.0)

    def test_distance_does_not_matter(self):
        for z in (1.5, 3.0, 5.0):
            self.assertAlmostEqual(self.sol(40.0, z=z)["away"][0], 40.0, delta=3.0)

    def test_vertical_arm_has_no_ground_direction(self):
        # the true arm is rejected when too steep; at most the other depth reading survives (the roadmap then decides)
        self.assertIsNone(self.sol(0.0, elev=90.0)["away"])
        self.assertIsNone(self.sol(0.0, elev=70.0)["away"])
        self.assertIsNotNone(self.sol(0.0, elev=45.0)["away"])
        self.assertIsNone(self.sol(0.0, elev=-75.0)["away"])

    def test_missing_keypoints(self):
        kp, conf = vs.body(left=vs.direction(90))
        conf[gm.L_WRIST] = 0.1
        self.assertIsNone(gm.arm_solutions(vs.sample(0, kp, conf), "left", CFG))

    def test_world_yaw_uses_pan_and_robot_yaw(self):
        # camera azimuth 90, robot yaw 90, pan 20 (camera turned left: camera yaw 70): world yaw 160, relative to the robot 70
        hold = [vs.sample(0.1 * i, *vs.body(left=vs.direction(90.0)), robot_yaw_deg=90.0, pan_deg=20.0) for i in range(6)]
        est = gm.point_estimate(hold, "left", CFG)
        self.assertAlmostEqual(est.world_deg["away"], 160.0, delta=2.0)
        self.assertAlmostEqual(est.rel_deg["away"], 70.0, delta=2.0)

    def test_both_candidates_in_world_for_an_out_of_plane_arm(self):
        hold = [vs.sample(0.1 * i, *vs.body(right=vs.direction(-40.0)), robot_yaw_deg=10.0) for i in range(6)]
        est = gm.point_estimate(hold, "right", CFG)
        self.assertTrue(est.two_solutions)
        self.assertAlmostEqual(est.world_deg["away"], 10.0 - 40.0, delta=3.0)
        self.assertGreater(abs(gm.wrap(est.world_deg["toward"] - est.world_deg["away"])), 40.0)
        self.assertGreater(est.phi_deg, 35.0)

    def test_noisy_keypoints(self):
        hold = [vs.sample(0.1 * i, *vs.body(left=vs.direction(90.0)), noise_px=1.5, rng=RNG) for i in range(8)]
        est = gm.point_estimate(hold, "left", CFG)
        self.assertAlmostEqual(est.world_deg["away"], 90.0, delta=8.0)

    def test_no_estimate_when_nothing_has_a_direction(self):
        est = gm.point_estimate([sample_for(left=vs.direction(0, 85))], "left", CFG)
        self.assertIsNone(est.world_deg["away"])                 # only the other depth reading is left


class CrosscheckTests(unittest.TestCase):
    def est(self, true_az, world_dir, cfg=CFG, extended=("index",)):
        kp, conf = vs.body(left=vs.direction(true_az))
        wrist = kp[gm.L_WRIST]
        h = vs.hand(wrist, extended=extended, category="Pointing_Up", world_dir=world_dir)
        hold = [vs.sample(0.1 * i, kp, conf, {"left": h}) for i in range(6)]
        return gm.point_estimate(hold, "left", cfg)

    def test_hand_world_finger_picks_the_matching_solution(self):
        e = self.est(140.0, vs.direction(140.0))                # pointing toward the camera, finger toward the camera
        self.assertEqual(e.crosscheck["prefers"], "toward")
        e = self.est(40.0, vs.direction(40.0))
        self.assertEqual(e.crosscheck["prefers"], "away")

    def test_z_sign_assumption_is_a_config_switch(self):
        cfg = json.loads(json.dumps(CFG))
        cfg["point"]["hand_world_z_away_positive"] = False
        e = self.est(40.0, vs.direction(140.0), cfg)            # z flipped: the finger now reads as pointing away
        self.assertEqual(e.crosscheck["prefers"], "away")

    def test_no_preference_when_the_finger_matches_neither(self):
        e = self.est(40.0, vs.direction(-90.0))
        self.assertIsNone(e.crosscheck["prefers"])
        self.assertTrue(e.crosscheck["available"])

    def test_no_world_landmarks_and_no_hand(self):
        self.assertFalse(self.est(40.0, None).crosscheck["available"])
        hold = [vs.sample(0.1 * i, *vs.body(left=vs.direction(40.0))) for i in range(6)]
        e = gm.point_estimate(hold, "left", CFG)
        self.assertEqual((e.crosscheck["available"], e.crosscheck["why"]), (False, "no hand linked"))

    def test_in_plane_arm_finger_picks_the_in_plane_solution(self):
        self.assertEqual(self.est(90.0, vs.direction(90.0)).crosscheck["prefers"], "away")


class LinkHandsTests(unittest.TestCase):
    def test_hand_goes_to_the_nearest_wrist(self):
        kp, conf = vs.body(left=vs.direction(90.0), right=vs.direction(-90.0))
        h_left = vs.hand(kp[gm.L_WRIST] + 3.0)
        h_right = vs.hand(kp[gm.R_WRIST] - 2.0)
        linked = gm.link_hands(kp, conf, [h_right, h_left], CFG)
        self.assertIs(linked["left"], h_left)
        self.assertIs(linked["right"], h_right)

    def test_far_hand_is_not_linked(self):
        kp, conf = vs.body(left=vs.direction(90.0))
        far = vs.hand(kp[gm.L_WRIST] + np.array([0.0, 200.0]))
        self.assertEqual(gm.link_hands(kp, conf, [far], CFG), {"left": None, "right": None})

    def test_low_confidence_wrist_or_shoulders(self):
        kp, conf = vs.body(left=vs.direction(90.0))
        h = vs.hand(kp[gm.L_WRIST])
        conf2 = conf.copy()
        conf2[gm.L_WRIST] = 0.1
        self.assertIsNone(gm.link_hands(kp, conf2, [h], CFG)["left"])
        conf3 = conf.copy()
        conf3[gm.R_SHOULDER] = 0.1
        self.assertEqual(gm.link_hands(kp, conf3, [h], CFG), {"left": None, "right": None})

    def test_one_hand_between_two_wrists_goes_to_the_nearer_only(self):
        kp, conf = vs.body(left=vs.direction(90.0), right=vs.direction(-90.0))
        h = vs.hand(kp[gm.L_WRIST] + 2.0)
        linked = gm.link_hands(kp, conf, [h], CFG)
        self.assertIs(linked["left"], h)
        self.assertIsNone(linked["right"])


def sweep(frm, to, f):
    """Arm direction between two directions (unit vectors), f in 0..1."""
    return vs.unit((1 - f) * np.asarray(frm, float) + f * np.asarray(to, float))


def point_builder(n_swing, az=90.0, hand_cat=None):
    target = vs.direction(az)

    def b(i):
        f = min(1.0, (i + 1) / n_swing) if n_swing else 1.0
        d = sweep(vs.DOWN, target, f)
        kp, conf = vs.body(left=d)
        hands = {}
        if hand_cat:
            hands = {"left": vs.hand(kp[gm.L_WRIST], axis=(1.0, 0.0), category=hand_cat, extended=("index",), score=0.9)}
        return kp, conf, hands
    return b


class WindowTests(unittest.TestCase):
    def read(self, samples, n=None):
        n = n or len(samples)
        win = samples[-n:]
        return gm.read_window(win, CFG, win[-1].t)

    def test_idle_arms_read_none(self):
        s = vs.arm_sequence(lambda i: (*vs.body(), {}), 12)
        r = self.read(s, 10)
        self.assertEqual((r.command, r.why, r.raised, r.moving), ("NONE", "no raised arm", False, False))

    def test_point_after_the_swing(self):
        s = vs.arm_sequence(point_builder(4), 16)
        r = self.read(s, 10)                                    # last 1.0 s: the swing is over, the arm is held
        self.assertEqual(r.command, "POINT")
        self.assertGreaterEqual(r.score, 0.7)
        self.assertEqual(r.arm, "left")
        self.assertAlmostEqual(r.point.rel_deg["away"], 90.0, delta=4.0)
        self.assertGreaterEqual(r.hold_s, 0.4)
        self.assertIsNotNone(r.arm_box)

    def test_moving_arm_without_a_hold_reads_none_and_says_why(self):
        s = vs.arm_sequence(point_builder(12), 12)               # still swinging for the whole window
        r = self.read(s, 10)
        self.assertEqual((r.command, r.why, r.moving), ("NONE", "moving, no hold yet", True))

    def test_the_swing_itself_is_never_read(self):
        s = vs.arm_sequence(point_builder(10), 20)
        cmds = [gm.read_window(s[max(0, k - 9):k + 1], CFG, s[k].t).command for k in range(len(s))]
        first_point = cmds.index("POINT")
        self.assertGreaterEqual(first_point, 10)                 # not before the arm has stopped
        self.assertTrue(all(c in ("insufficient_history", "NONE") for c in cmds[:first_point]))

    def test_still_raised_arm_is_a_held_pose_not_a_moving_gesture(self):
        s = vs.arm_sequence(point_builder(0), 12)
        r = self.read(s, 10)
        self.assertEqual((r.command, r.moving), ("POINT", False))

    def test_insufficient_history_at_the_start(self):
        s = vs.arm_sequence(point_builder(0), 10)
        self.assertEqual(self.read(s, 3).command, "insufficient_history")
        self.assertEqual(self.read(s, 5).command, "insufficient_history")
        self.assertEqual(self.read(s, 6).command, "POINT")       # 6 valid frames = min_valid_fraction 0.6 of 10

    def test_waving_raised_hand_is_moving(self):
        def b(i):
            d = vs.direction(60.0 + (40.0 if i % 2 else -40.0), 20.0)
            return (*vs.body(left=d), {})
        r = self.read(vs.arm_sequence(b, 12), 10)
        self.assertTrue(r.moving)
        self.assertEqual(r.command, "NONE")

    def wait_builder(self, category="Pointing_Up", extended=("index",)):
        def b(i):
            kp, conf = vs.body(left=(0.0, -1.0, 0.0), left_fore=(0.0, -1.0, 0.0))
            # bent elbow: upper arm out to the side, forearm vertical
            kp, conf = vs.body(left=vs.direction(90.0), left_fore=(0.0, -1.0, 0.0))
            h = vs.hand(kp[gm.L_WRIST], axis=(0.0, -1.0), extended=extended, category=category, fan_deg=4.0)
            return kp, conf, {"left": h}
        return b

    def test_wait_index_finger_up(self):
        r = self.read(vs.arm_sequence(self.wait_builder(), 12), 10)
        self.assertEqual((r.command, r.arm), ("WAIT", "left"))
        self.assertGreaterEqual(r.score, 0.7)
        self.assertEqual(r.frame_class, "WAIT")

    def test_wait_needs_the_finger_shape_not_only_the_category(self):
        r = self.read(vs.arm_sequence(self.wait_builder(extended=("index", "middle", "ring", "pinky")), 12), 10)
        self.assertNotEqual(r.command, "WAIT")                   # four fingers up with a Pointing_Up label

    def test_open_palm_is_stop_not_wait(self):
        b = self.wait_builder(category="Open_Palm", extended=("index", "middle", "ring", "pinky"))

        def b2(i):
            kp, conf, hands = b(i)
            hands["left"] = vs.hand(kp[gm.L_WRIST], axis=(0.0, -1.0), category="Open_Palm", fan_deg=18.0)
            return kp, conf, hands
        r = self.read(vs.arm_sequence(b2, 12), 10)
        self.assertEqual(r.command, "STOP")
        self.assertEqual(r.frame_class, "STOP")

    def test_stop_is_read_on_the_short_window_while_the_arm_still_moves(self):
        def b(i):
            d = vs.direction(60.0 + 8.0 * i, 10.0)
            kp, conf = vs.body(left=d)
            return kp, conf, {"left": vs.hand(kp[gm.L_WRIST], axis=(1.0, 0.0), category="Open_Palm")}
        r = self.read(vs.arm_sequence(b, 12), 10)
        self.assertEqual((r.command, r.moving), ("STOP", True))

    def test_stop_needs_open_fingers_and_spread(self):
        def b(spread, ext):
            def f(i):
                kp, conf = vs.body(left=vs.direction(90.0, 10.0))
                return kp, conf, {"left": vs.hand(kp[gm.L_WRIST], axis=(1.0, 0.0), category="Open_Palm", fan_deg=spread, extended=ext)}
            return f
        self.assertEqual(self.read(vs.arm_sequence(b(18, ("index", "middle", "ring", "pinky")), 12), 10).command, "STOP")
        self.assertNotEqual(self.read(vs.arm_sequence(b(2, ("index", "middle", "ring", "pinky")), 12), 10).command, "STOP")
        self.assertNotEqual(self.read(vs.arm_sequence(b(18, ("index",)), 12), 10).command, "STOP")

    def test_stop_push_can_be_required(self):
        cfg = json.loads(json.dumps(CFG))
        cfg["hand"]["stop_requires_push"] = True

        def grow(k):
            def f(i):
                kp, conf = vs.body(left=vs.direction(90.0, 10.0))
                h = vs.hand(kp[gm.L_WRIST], axis=(1.0, 0.0), category="Open_Palm", z=2.0 / (1.0 + k * i))
                return kp, conf, {"left": h}
            return f
        s_static = vs.arm_sequence(grow(0.0), 12)
        s_push = vs.arm_sequence(grow(0.05), 12)
        self.assertEqual(gm.read_window(s_static[-10:], cfg, s_static[-1].t).command, "NONE")
        self.assertEqual(gm.read_window(s_push[-10:], cfg, s_push[-1].t).command, "STOP")

    def test_missing_hand_still_reads_point_but_not_wait_or_stop(self):
        self.assertEqual(self.read(vs.arm_sequence(point_builder(0), 12), 10).command, "POINT")
        wait_no_hand = vs.arm_sequence(lambda i: (*vs.body(left=vs.direction(90.0), left_fore=(0.0, -1.0, 0.0)), {}), 12)
        self.assertEqual(self.read(wait_no_hand, 10).command, "NONE")

    def test_open_palm_on_an_extended_arm_is_not_a_point(self):
        def b(i):
            kp, conf = vs.body(left=vs.direction(90.0, 10.0))
            return kp, conf, {"left": vs.hand(kp[gm.L_WRIST], axis=(1.0, 0.0), category="Open_Palm")}
        r = self.read(vs.arm_sequence(b, 12), 10)
        self.assertEqual(r.command, "STOP")                       # STOP overrides; it is certainly not POINT

    def test_both_arms_different_commands_is_none(self):
        def b(i):
            kp, conf = vs.body(left=vs.direction(90.0), right=vs.direction(-90.0), right_fore=None)
            return kp, conf, {}
        # right arm bent as for WAIT, left arm pointing
        def b2(i):
            kp, conf = vs.body(left=vs.direction(90.0), right=vs.direction(-90.0), right_fore=(0.0, -1.0, 0.0))
            h = vs.hand(kp[gm.R_WRIST], axis=(0.0, -1.0), extended=("index",), category="Pointing_Up", fan_deg=4.0)
            return kp, conf, {"right": h}
        r = self.read(vs.arm_sequence(b2, 12), 10)
        self.assertEqual((r.command, r.why), ("NONE", "conflicting arms"))

    def test_both_arms_pointing_equally_is_none(self):
        s = vs.arm_sequence(lambda i: (*vs.body(left=vs.direction(90.0), right=vs.direction(-90.0)), {}), 12)
        r = self.read(s, 10)
        self.assertEqual((r.command, r.why), ("NONE", "both arms point equally"))

    def test_noisy_keypoints_still_read(self):
        def b(i):
            kp, conf = vs.body(left=vs.direction(90.0))
            return kp, conf, {}
        s = vs.arm_sequence(b, 14, noise_px=1.5, rng=np.random.default_rng(3))
        r = self.read(s, 10)
        self.assertEqual(r.command, "POINT")
        self.assertAlmostEqual(r.point.rel_deg["away"], 90.0, delta=8.0)

    def test_dropped_keypoints(self):
        def b(drop):
            def f(i):
                kp, conf = vs.body(left=vs.direction(90.0))
                if i % 10 in drop:
                    conf = conf.copy()
                    conf[gm.L_WRIST] = 0.0
                return kp, conf, {}
            return f
        self.assertEqual(self.read(vs.arm_sequence(b({1, 4, 7}), 12), 10).command, "POINT")          # 7 of 10 valid
        r = self.read(vs.arm_sequence(b({0, 1, 2, 3, 5, 6, 8}), 12), 10)                              # too few valid
        self.assertEqual(r.command, "insufficient_history")

    def test_pointing_arm_straight_up_leaves_only_the_alternative_reading(self):
        s = vs.arm_sequence(lambda i: (*vs.body(left=(0.0, -1.0, 0.0)), {}), 12)
        r = self.read(s, 10)
        self.assertIsNone(r.point.world_deg["away"])             # no ground direction for the true arm
        self.assertGreater(abs(r.point.rel_deg["toward"]), 150.0)  # the one left points back at the robot

    def test_reading_is_json_serialisable_and_has_zoom_inputs(self):
        r = self.read(vs.arm_sequence(point_builder(0, hand_cat="Pointing_Up"), 12), 10)
        d = json.loads(json.dumps(r.to_dict()))
        self.assertEqual(d["command"], "POINT")
        self.assertIsNotNone(d["hand_box"])
        self.assertEqual(r.frame_wh, (730, 530))
        self.assertAlmostEqual(r.fov_deg, 60.0, delta=0.05)

    def test_buffer_keeps_only_the_window(self):
        b = gm.PersonBuffer(1.5)
        for i in range(30):
            b.add(vs.sample(0.1 * i, *vs.body()))
        self.assertLessEqual(len(b), 16)
        w = b.window(2.9, 1.0)
        self.assertEqual(len(w), 11)
        self.assertAlmostEqual(w[0].t, 1.9)

    def test_config_is_consistent_with_the_bridge(self):
        bridge = json.loads((ROOT / "configs" / "v4" / "bridge.json").read_text())
        self.assertEqual(CFG["frame_hz"], bridge["frame_pan_tilt_hz"])
        self.assertEqual(CFG["status"], "initial")
        self.assertEqual(CFG["keypoints"]["raised_max_abs_deg"], 120)          # v3 values kept
        self.assertEqual(CFG["point"]["arm_length_min"], 0.8)


if __name__ == "__main__":
    unittest.main()
