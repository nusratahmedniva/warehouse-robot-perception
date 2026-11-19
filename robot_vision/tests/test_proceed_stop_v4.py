"""analyse_proceed_stop_v4.py (AUDIT.md 16.19.2): the palm cue from 3D landmarks, B1 (relative minimum of valid frames with an absolute floor), C2 (a still arm for STOP while
the robot is stopped, nothing changed while moving), the dialog simulation, the robot-state lookup, and that the candidates are applied inside one replay only."""

import ast
import math
import sys
import unittest
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))

import analyse_false_stop_v4 as fs  # noqa: E402
import analyse_proceed_stop_v4 as ap  # noqa: E402
import commander_v4 as cm  # noqa: E402
import gesture_motion as gm  # noqa: E402
import test_stop_rule_v4 as tsr  # noqa: E402
import test_v4_upgrades as tu  # noqa: E402

CFG = ap.load_config()
RC, CC = gm.load_config(), cm.load_config()
RC["proceed"] = {k: v for k, v in RC["proceed"].items() if k != "min_valid_floor"}      # the nominal rule: the replay baseline, B1 (AUDIT.md 16.21) is the variant under test


def world(mirror=False, flip_z=False):
    """A hand in MediaPipe's world frame (x right, y down, z away): wrist at the origin, the index knuckle to the right and the pinky knuckle to the left, both above."""
    w = np.zeros((21, 3))
    w[gm.WRIST_LM] = (0.0, 0.0, 0.0)
    w[gm.INDEX_MCP] = (0.03, -0.09, 0.0)
    w[gm.PINKY_MCP] = (-0.03, -0.08, 0.0)
    w[gm.INDEX_TIP] = (0.04, -0.17, 0.0)
    if mirror:
        w[:, 0] = -w[:, 0]
    if flip_z:
        w[:, 2] = -w[:, 2]
    return w


class PalmCueTests(unittest.TestCase):
    def test_the_normal_is_a_unit_vector_in_the_palm_plane_normal_and_degenerate_hands_give_none(self):
        n = ap.palm_normal(world())
        self.assertAlmostEqual(float(np.linalg.norm(n)), 1.0)
        self.assertAlmostEqual(abs(float(n[2])), 1.0)                                  # a flat hand in the x-y plane: the normal is along z
        self.assertIsNone(ap.palm_normal(np.zeros((21, 3))))

    def test_the_sign_flips_the_angle_to_its_supplement_and_the_two_hands_are_mirrors(self):
        a_plus = ap.palm_to_camera_deg(world(), "right", 1.0)
        a_minus = ap.palm_to_camera_deg(world(), "right", -1.0)
        self.assertAlmostEqual(a_plus + a_minus, 180.0, places=6)
        self.assertIn(round(a_plus), (0, 180))
        # the mirror image of a right hand is a left hand showing the same face: with the opposite factor of the left hand its angle is the same
        self.assertAlmostEqual(ap.palm_to_camera_deg(world(), "right", 1.0), ap.palm_to_camera_deg(world(mirror=True), "left", 1.0), places=6)
        # the same right hand mirrored in the image plane is the back of the hand: the angle is the supplement
        self.assertAlmostEqual(ap.palm_to_camera_deg(world(mirror=True), "right", 1.0), 180.0 - a_plus, places=6)
        self.assertIsNone(ap.palm_to_camera_deg(np.zeros((21, 3)), "right", 1.0))


class RobotStateTests(unittest.TestCase):
    IDX = {1: ([0.0, 1.0, 2.0, 3.0], [(0.0, "read"), (0.03, "read (stopped: STOP gesture)"), (0.5, "navigate"), (0.04, "approach")])}

    def test_stopped_means_slow_and_in_read_approach_or_wait(self):
        self.assertTrue(ap.is_stopped(self.IDX, 1, 0.5, 0.05))
        self.assertTrue(ap.is_stopped(self.IDX, 1, 1.4, 0.05))                          # the row at or before the time: v 0.03, a read state
        self.assertFalse(ap.is_stopped(self.IDX, 1, 2.2, 0.05))                         # v 0.5, navigate
        self.assertTrue(ap.is_stopped(self.IDX, 1, 3.5, 0.05))                          # approach at 0.04 m/s
        self.assertFalse(ap.is_stopped(self.IDX, 1, -1.0, 0.05))                        # before the first row
        self.assertFalse(ap.is_stopped(self.IDX, 2, 1.0, 0.05))                         # unknown trial

    def test_the_declared_threshold(self):
        self.assertEqual(CFG["stopped_speed_mps"], 0.05)


class DialogTests(unittest.TestCase):
    def recs(self, cmds, dt=0.1):
        return [("S", 1, round(0.1 * k, 4), "PROCEED", 7, c, False, None, None, None, 1, 12) for k, c in enumerate(cmds)]

    def seg(self, n):
        return {"start": 0.0, "end": 0.1 * (n - 1)}

    def test_half_a_second_of_proceed_is_accepted(self):
        r = self.recs(["PROCEED"] * 8)
        self.assertAlmostEqual(ap.dialog_accepts(r, self.seg(8), "live", CFG), 0.5)

    def test_a_stop_flicker_is_skipped_live_and_a_no_direction_reading_when_fed(self):
        r = self.recs(["PROCEED"] * 3 + ["STOP"] * 3 + ["PROCEED"] * 6)
        self.assertIsNotNone(ap.dialog_accepts(r, self.seg(12), "live", CFG))            # the stop frames are not fed: the hold goes on
        self.assertIsNotNone(ap.dialog_accepts(r, self.seg(12), "fed", CFG))
        long_stop = self.recs(["PROCEED"] * 3 + ["STOP"] * 5 + ["PROCEED"] * 3)
        live = ap.dialog_accepts(long_stop, self.seg(11), "live", CFG)
        fed = ap.dialog_accepts(long_stop, self.seg(11), "fed", CFG)
        self.assertIsNotNone(live)                                                       # live is the more lenient: feeding the STOP as NONE restarts the hold
        self.assertIsNone(fed)

    def test_too_little_proceed_is_never_accepted(self):
        self.assertIsNone(ap.dialog_accepts(self.recs(["PROCEED"] * 4 + ["NONE"] * 6), self.seg(10), "live", CFG))


class VariantTests(unittest.TestCase):
    def tearDown(self):
        self.assertIs(gm.frame_flags.__module__, "gesture_motion")                     # nothing is left patched

    def test_b1_accepts_a_slow_frame_rate_the_nominal_rule_refuses_and_keeps_the_floor(self):
        ctx = {"stopped": False}
        full = tu.swing_samples(n=25, hz=1.5)
        sparse = full[::2]                                                               # 5 fps: 11 frames in the last 2 s, fewer than the 12 the nominal rule needs
        feat = lambda samples: gm.proceed_features(samples, "right", RC, samples[-1].t)
        base = feat(sparse)
        self.assertFalse(base["enough"])
        with ap.variant_wrap({"b1": {"frac": 0.6, "floor": 10}}, RC, ctx):
            b1 = feat(sparse)
            self.assertEqual(b1["valid"], base["valid"])
            self.assertEqual(base["valid"], 11)
            self.assertTrue(b1["enough"])                                                # 11 >= max(10, 0.6 x 11)
            tiny = feat(sparse[:7])
            self.assertFalse(tiny["enough"])                                            # below the floor of 10: never
        with ap.variant_wrap({"b1": {"frac": 0.6, "floor": 8}}, RC, ctx):
            self.assertGreaterEqual(feat(sparse)["enough"], b1["enough"])               # a lower floor never reads less
        self.assertFalse(feat(sparse)["enough"])                                        # restored afterwards

    def test_b1_changes_nothing_at_the_nominal_frame_rate(self):
        ctx = {"stopped": False}
        full = tu.swing_samples(n=25, hz=1.5)
        base = gm.proceed_features(full, "right", RC, full[-1].t)
        with ap.variant_wrap({"b1": {"frac": 0.6, "floor": 10}}, RC, ctx):
            self.assertEqual(gm.proceed_features(full, "right", RC, full[-1].t), base)

    def test_c2_needs_a_still_arm_only_while_the_robot_is_stopped(self):
        frames = [tsr.frame(i * 0.1, i, True, True) for i in range(25)]                  # a raised, swinging, open hand
        ctx = {"stopped": False}

        def run(stopped):
            ctx["stopped"] = stopped
            with ap.variant_wrap({"static_when_stopped": True}, RC, ctx):
                res = ap.replay_hooked(frames, RC, CC, lambda f: None)
            return [prs[0].reading.command for _, prs, _ in res if prs]
        moving, stopped = run(False), run(True)
        base = [prs[0].reading.command for _, prs, _ in fs.replay(frames, RC, CC) if prs]
        self.assertEqual(moving, base)                                                    # moving: exactly the current reader
        self.assertIn("STOP", base)
        self.assertNotIn("STOP", stopped)                                                 # stopped and swinging: not a STOP

    def test_c2_keeps_a_still_raised_hand_a_stop_while_stopped(self):
        frames = [tsr.frame(i * 0.1, i, True, False) for i in range(25)]
        ctx = {"stopped": True}
        with ap.variant_wrap({"static_when_stopped": True}, RC, ctx):
            res = ap.replay_hooked(frames, RC, CC, lambda f: None)
        self.assertIn("STOP", [prs[0].reading.command for _, prs, _ in res if prs])

    def test_c1_vetoes_a_stop_whose_palm_points_away_and_without_world_landmarks_it_does_not_veto(self):
        frames = [tsr.frame(i * 0.1, i, True, False) for i in range(25)]
        ctx = {"stopped": False}
        with ap.variant_wrap({"palm_limit_deg": 60.0, "sign_right": 1.0}, RC, ctx):
            res = ap.replay_hooked(frames, RC, CC, lambda f: None)
        self.assertIn("STOP", [prs[0].reading.command for _, prs, _ in res if prs])      # the synthetic hands carry no world landmarks: the cue is not applied


class ShortWindowAndSplitTests(unittest.TestCase):
    """C2s (AUDIT.md 16.19.5) and the split of criterion (a) by the robot's state when the STOP was given."""

    def run_frames(self, swing, mode, stopped):
        frames = [tsr.frame(i * 0.1, i, True, swing) for i in range(25)]
        ctx = {"stopped": stopped}
        with ap.variant_wrap({"static_when_stopped": mode}, RC, ctx):
            res = ap.replay_hooked(frames, RC, CC, lambda f: None)
        return [prs[0].reading.command for _, prs, _ in res if prs]

    def test_c2s_uses_the_0_3_s_window_and_only_while_stopped(self):
        self.assertEqual((RC["window"]["stop_window_s"], RC["motion"]["still_speed_max"]), (0.3, 0.4))      # the reader's own values, no new number
        base = [prs[0].reading.command for _, prs, _ in fs.replay([tsr.frame(i * 0.1, i, True, True) for i in range(25)], RC, CC) if prs]
        self.assertEqual(self.run_frames(True, "speed", False), base)                      # moving: exactly the current reader (a swinging raised hand is a STOP)
        self.assertIn("STOP", base)
        self.assertNotIn("STOP", self.run_frames(True, "speed", True))                    # stopped and swinging: not a STOP
        still = self.run_frames(False, "speed", True)
        self.assertIn("STOP", still)                                                       # stopped and still: a STOP ...
        first_c2s = next(k for k, c in enumerate(still) if c == "STOP")
        first_c2 = next((k for k, c in enumerate(self.run_frames(False, True, True)) if c == "STOP"), None)
        self.assertLessEqual(first_c2s, 4)                                                 # ... within a few frames, with no wait for a second of stillness
        self.assertTrue(first_c2 is None or first_c2s <= first_c2)

    def test_the_second_round_has_the_declared_variants_and_no_palm_cue(self):
        vs_ = ap.variants_round2(CFG)
        self.assertEqual([v["key"] for v in vs_], ["current", "c2", "c2s", "current_b1", "c2_b1", "c2s_b1"])
        self.assertTrue(all(v["v"].get("palm_limit_deg") is None for v in vs_))
        self.assertEqual(vs_[2]["v"], {"static_when_stopped": "speed"})
        self.assertEqual(vs_[5]["v"]["b1"], {"frac": 0.6, "floor": 10})

    def test_criterion_a_is_split_by_the_robot_state_at_the_onset(self):
        from types import SimpleNamespace

        def rows(worker, t0):
            return [{"time_s": t0 + 0.05 * k, "worker_id": worker, "look": "sunbox_m1", "x": 0.0, "z": 5.0, "true_command": "STOP", "arm": "right", "phase": "holding",
                     "clip": "stop_ik_01"} for k in range(30)]
        truth = {1: rows(1, 10.0) + rows(1, 50.0)}                                           # one STOP while the robot stands (v 0), one while it drives (v 0.5)
        ds = SimpleNamespace(runs={("S", 1): {"truth": truth}}, cfg={**CFG["base"], "sessions": {}},
                             dec={"S": {1: ([0.0, 9.0, 40.0, 49.0], [(0.5, "navigate"), (0.0, "read"), (0.5, "navigate"), (0.5, "navigate")])}})
        # the reader says STOP 0.3 s after the first, and 1.2 s after the second STOP onset (the segment lasts 1.45 s)
        recs = [("S", 1, 10.3, "STOP", 1, "STOP", True, "sunbox_m1", "right", "stop_ik_01", 1, 12),
                ("S", 1, 51.2, "STOP", 1, "STOP", False, "sunbox_m1", "right", "stop_ik_01", 1, 12)]
        a = ap.criterion_a(ds, recs, None, CFG)
        self.assertEqual(a["stops"], 2)
        self.assertEqual(a["by_robot_state"]["stopped"], {"stops": 1, "within_1s": 1, "lost_altogether": 0})
        self.assertEqual(a["by_robot_state"]["moving"], {"stops": 1, "within_1s": 0, "lost_altogether": 0})      # read, but after 1.2 s
        base = a
        slower = [("S", 1, 11.3, "STOP", 1, "STOP", True, "sunbox_m1", "right", "stop_ik_01", 1, 12)]        # the first STOP read at 1.3 s (inside its 1.45 s segment), the second never
        b = ap.criterion_a(ds, slower, base, CFG)
        self.assertEqual(b["by_robot_state"]["stopped"], {"stops": 1, "within_1s": 0, "lost_altogether": 0, "lost_vs_current": 0, "lost_from_the_1s_set": 1,
                                                         "read_later_than_current": 1, "later_median_s": 1.0})
        self.assertEqual(b["by_robot_state"]["moving"]["lost_altogether"], 1)
        self.assertEqual(b["by_robot_state"]["moving"]["lost_vs_current"], 1)
        self.assertEqual(b["lost_vs_current"], 1)


class ConfigAndIsolationTests(unittest.TestCase):
    def test_the_declared_values(self):
        self.assertEqual((CFG["b1"]["frac"], CFG["b1"]["floor"], CFG["b1"]["floor_sensitivity"]), (0.6, 10, 8))
        self.assertEqual((CFG["palm_limit_step_deg"], CFG["palm_limit_cap_deg"]), (5, 90))
        self.assertEqual((CFG["dialog_hold_s"], CFG["dialog_max_none_gap_s"], CFG["ask_window_s"]), (0.5, 0.3, 5.0))
        self.assertEqual(len(CFG["sessions"]["S5"]), 8)
        self.assertEqual(RC["hand"]["stop_fingertip_spread_min"], 1.3)                    # the spread is not raised

    def test_the_variants_are_the_declared_ones_in_the_declared_order(self):
        names = [v["key"] for v in ap.variants(CFG, {"usable": True, "limit_deg": 80.0, "sign_right": 1.0})]
        self.assertEqual(names, ["current", "previous", "b1", "b1s", "c1", "c2", "c1c2", "all"])
        self.assertIsNone(ap.variants(CFG, {"usable": False, "limit_deg": 80.0, "sign_right": 1.0})[4]["v"]["palm_limit_deg"])

    def test_the_reader_is_not_changed_and_inference_never_imports_the_analysis(self):
        offenders = []
        for p in ROOT.rglob("*.py"):
            rel = p.relative_to(ROOT)
            if ".venv" in rel.parts or rel.parts[0] == "tests" or rel.name in ("analyse_proceed_stop_v4.py", "analyse_point_frames_v4.py", "analyse_point_dialog_v4.py", "analyse_live_association_v4.py", "fit_point_readability_v4.py"):          # the latter: evaluation code of AUDIT.md 16.26 item 3 (2026-11-19) and 16.26.4 / 16.26.5 (2026-11-20)
                continue
            tree = ast.parse(p.read_text(encoding="utf-8"))
            mods = {a.name.split(".")[0] for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names}
            mods |= {n.module.split(".")[0] for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) and n.module}
            if "analyse_proceed_stop_v4" in mods:
                offenders.append(str(rel))
        self.assertEqual(offenders, [])


if __name__ == "__main__":
    unittest.main()
