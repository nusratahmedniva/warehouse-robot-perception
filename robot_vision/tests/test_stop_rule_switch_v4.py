"""The STOP rule adopted on 2026-11-16 (AUDIT.md 16.18.2) is what the reader uses: open hand AND fingertip spread >= 1.3 AND raised arm, no static cue, switched
by two keys of the `hand` block of configs/v4/gesture_reader.json. The reader reads exactly what the analysis wrapper 'fallback (ii)' read in 16.18.1 (frame by
frame), absent or null keys are the reader as it was, and the earlier STOP behaviour is still there with the keys off."""

import json
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))

import analyse_false_stop_v4 as fs  # noqa: E402
import check_stop_rule_v4 as ck  # noqa: E402
import commander_v4 as cm  # noqa: E402
import gesture_motion as gm  # noqa: E402
import test_stop_rule_v4 as tsr  # noqa: E402

NEW = gm.load_config()                                   # gesture_reader.json as it is now
OLD = fs.live_reader_config()                            # the same with the two keys of 2026-11-16 off
CC = cm.load_config()


def hand_of(tip_x: float) -> SimpleNamespace:
    """A hand with four extended fingers whose knuckles are 36 px apart and whose tips are tip_x px either side of the middle: tip_x 18 = fingers
    parallel (fingertip spread 1.0), 30 = a fan (1.67). The reader's own open-hand geometry passes for both."""
    lm = np.zeros((21, 2))
    xs = np.array([-1.0, -1 / 3, 1 / 3, 1.0])
    for k, (mcp, tip) in enumerate(gm.FINGERS.values()):
        lm[mcp] = (18.0 * xs[k], -40.0)
        lm[tip] = (tip_x * xs[k], -70.0)
    return SimpleNamespace(landmarks_px=lm, category="Open_Palm", score=0.9)


def af(valid=True, raised=True) -> SimpleNamespace:
    return SimpleNamespace(valid=valid, raised=raised)


class ConfigTests(unittest.TestCase):
    def test_the_two_keys_are_on_with_the_declared_values_and_there_is_no_static_key(self):
        h = json.loads((ROOT / "configs/v4/gesture_reader.json").read_text(encoding="utf-8"))["hand"]
        self.assertIs(h["stop_requires_raised"], True)
        self.assertEqual(h["stop_fingertip_spread_min"], 1.3)                       # fixed in AUDIT.md 16.18 before the data was read, never varied
        self.assertFalse([k for k in h if "static" in k or "still" in k or "palm_facing" in k])   # no static cue, no palm direction (16.18.2)
        self.assertIs(h["stop_requires_push"], False)                                  # unchanged
        for k in ("stop_requires_raised", "stop_fingertip_spread_min"):
            self.assertIn("DECIDED 2026-11-16", h["why"][k])
        self.assertEqual((NEW["keypoints"]["arm_raised_margin"], NEW["keypoints"]["raised_max_abs_deg"]), (0.25, 120))    # the raised flag's own values
        self.assertEqual((NEW["hand"]["finger_extended_ratio"], NEW["hand"]["palm_spread_min_deg"]), (1.6, 20))            # the open hand's own values

    def test_the_analysis_baseline_is_the_reader_as_it_was(self):
        self.assertEqual((OLD["hand"]["stop_requires_raised"], OLD["hand"]["stop_fingertip_spread_min"]), (False, None))
        self.assertEqual({k: v for k, v in OLD["hand"].items() if k not in ("stop_requires_raised", "stop_fingertip_spread_min")},
                         {k: v for k, v in NEW["hand"].items() if k not in ("stop_requires_raised", "stop_fingertip_spread_min")})
        self.assertTrue(NEW["hand"]["stop_requires_raised"])                           # live_reader_config returns a copy: the loaded config is not changed


class FingertipSpreadTests(unittest.TestCase):
    def test_parallel_fingers_one_and_a_fan_larger_and_the_analysis_function_agrees(self):
        tight, fan = hand_of(18.0), hand_of(30.0)
        self.assertAlmostEqual(gm.fingertip_spread(tight.landmarks_px), 1.0, places=6)
        self.assertAlmostEqual(gm.fingertip_spread(fan.landmarks_px), 60.0 / 36.0, places=6)
        for h in (tight, fan):
            self.assertEqual(gm.fingertip_spread(h.landmarks_px), fs.fingertip_spread(h.landmarks_px))
            self.assertTrue(gm.open_palm_geometry(gm.hand_cues(h, NEW), NEW))           # the reader's own open hand passes both: the new cue is what separates them
        self.assertEqual(gm.fingertip_spread(np.zeros((21, 2))), 0.0)                  # degenerate hand: no spread, not a crash

    def test_the_wrist_angle_spread_passes_the_tight_hand_which_is_why_the_cue_is_needed(self):
        cues = gm.hand_cues(hand_of(18.0), NEW)
        self.assertGreaterEqual(cues["spread_deg"], NEW["hand"]["palm_spread_min_deg"])


class ExtraRequirementTests(unittest.TestCase):
    def test_truth_table(self):
        fan, tight = hand_of(30.0), hand_of(18.0)
        self.assertTrue(gm.stop_extra_ok(fan, af(True, True), NEW))
        self.assertFalse(gm.stop_extra_ok(fan, af(True, False), NEW))                  # arm not raised
        self.assertFalse(gm.stop_extra_ok(fan, af(False, True), NEW))                  # arm not valid is not raised
        self.assertFalse(gm.stop_extra_ok(tight, af(True, True), NEW))                 # fingertips together
        self.assertFalse(gm.stop_extra_ok(tight, af(True, False), NEW))

    def test_each_key_switches_its_own_requirement_and_absent_or_null_is_off(self):
        fan, tight = hand_of(30.0), hand_of(18.0)
        only_raised = {"hand": {"stop_requires_raised": True}}                         # the spread key absent
        self.assertTrue(gm.stop_extra_ok(tight, af(True, True), only_raised))
        self.assertFalse(gm.stop_extra_ok(fan, af(True, False), only_raised))
        only_spread = {"hand": {"stop_requires_raised": False, "stop_fingertip_spread_min": 1.3}}
        self.assertTrue(gm.stop_extra_ok(fan, af(True, False), only_spread))
        self.assertFalse(gm.stop_extra_ok(tight, af(True, True), only_spread))
        for off in ({"hand": {}}, {"hand": {"stop_requires_raised": False, "stop_fingertip_spread_min": None}}):
            self.assertTrue(gm.stop_extra_ok(tight, af(False, False), off))            # the reader as it was: nothing extra is required


class FrameFlagTests(unittest.TestCase):
    def sample(self, raised: bool):
        return tsr.frame(0.0, 0, raised, False)

    def flags(self, raised: bool, cfg: dict) -> dict:
        res = fs.replay([self.sample(raised)] * 1, cfg, CC, keep_samples=True)
        f, prs, smp = res[0]
        s = smp[prs[0].track_id]
        return gm.frame_flags(s, "right", gm.arm_frame(s, "right", cfg), cfg)

    def test_a_raised_open_hand_is_a_stop_frame_a_hanging_one_is_not(self):
        self.assertTrue(self.flags(True, NEW)["stop_ok"])
        self.assertFalse(self.flags(False, NEW)["stop_ok"])
        self.assertTrue(self.flags(False, OLD)["stop_ok"])                              # the earlier reader: a hanging open hand was a STOP frame


class ReaderEqualsTheEvaluatedRuleTests(unittest.TestCase):
    """The reader with the keys on reads, frame by frame, what 'fallback (ii)' (open hand + spread >= 1.3 + raised, no static) read on the old reader."""

    def stops(self, frames, cfg, cues=None):
        import contextlib
        with fs.candidate(cues, cfg) if cues else contextlib.nullcontext():
            res = fs.replay(frames, cfg, CC)
        return [[p.reading.command for p in prs] for _, prs, _ in res]

    def test_identical_on_raised_still_raised_swinging_and_hanging_hands(self):
        fallback_ii = ck.load_config()["rules"]["fallback_ii"]                          # the rule evaluated in 16.18.1, from its own config
        self.assertEqual(fallback_ii, {"spread": 1.3, "raised": True})
        for raised, swing in ((True, False), (True, True), (False, False)):
            frames = [tsr.frame(i * 0.1, i, raised, swing) for i in range(25)]
            new = self.stops(frames, NEW)
            ref = self.stops(frames, OLD, fallback_ii)
            self.assertEqual(new, ref, (raised, swing))
        raised_still = self.stops([tsr.frame(i * 0.1, i, True, False) for i in range(25)], NEW)
        self.assertEqual(raised_still[5], ["STOP"])
        swinging = self.stops([tsr.frame(i * 0.1, i, True, True) for i in range(25)], NEW)
        self.assertEqual(swinging[5], ["STOP"])                                         # no static cue: a swinging raised open hand still reads STOP
        hanging = self.stops([tsr.frame(i * 0.1, i, False, False) for i in range(25)], NEW)
        self.assertNotIn("STOP", [c for frame in hanging for c in frame])               # the hanging open hand of 16.14 no longer stops the robot
        old_hanging = self.stops([tsr.frame(i * 0.1, i, False, False) for i in range(25)], OLD)
        self.assertIn("STOP", [c for frame in old_hanging for c in frame])


if __name__ == "__main__":
    unittest.main()
