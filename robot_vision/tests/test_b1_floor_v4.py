"""B1 floor 10 (AUDIT.md 16.21, 2026-11-17; the candidate B1 of 16.19.2, replayed in 16.19.6): PROCEED needs valid arm frames >= max(proceed.min_valid_floor 10,
0.6 x the frames received in the 2.0 s window) instead of 0.6 x the nominal 20. v4 reader only; absent = the nominal rule."""

import json
import os
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))

import analyse_proceed_stop_v4 as ap  # noqa: E402
import gesture_motion as gm  # noqa: E402
import test_v4_upgrades as tu  # noqa: E402

ON = gm.load_config()
OFF = {**ON, "proceed": {k: v for k, v in ON["proceed"].items() if k != "min_valid_floor"}}


def feat(cfg, samples):
    return gm.proceed_features(samples, "right", cfg, samples[-1].t)


class Config(unittest.TestCase):
    def test_the_floor_and_its_reason(self):
        self.assertEqual(ON["proceed"]["min_valid_floor"], 10)
        self.assertEqual(ON["window"]["min_valid_fraction"], 0.6)                      # the fraction is the existing value
        why = ON["proceed"]["why"]["min_valid_floor"]
        for w in ("DECIDED 2026-11-17", "16.21", "35/62 -> 58/62", "v4 only"):
            self.assertIn(w, why)

    def test_v3_is_untouched(self):
        self.assertNotIn("min_valid_floor", (ROOT / "hri_perception.py").read_text(encoding="utf-8"))
        self.assertNotIn("min_valid_floor", (ROOT / "configs/hri_perception.json").read_text(encoding="utf-8"))

    def test_the_difference_is_declared(self):
        d = " ".join(json.loads((ROOT / "configs/v4/analysis.json").read_text(encoding="utf-8"))["declared_differences"])
        for w in ("PROCEED valid frames", "16.21", "max(10, 0.6 x the frames it received", "35/62 to 58/62"):
            self.assertIn(w, d)


class Reader(unittest.TestCase):
    def test_a_5_hz_stream_is_read_with_the_floor_and_not_without(self):
        full = tu.swing_samples(n=25, hz=1.5)
        sparse = full[::2]                                                             # 11 frames in the last 2 s
        self.assertEqual(feat(OFF, sparse)["valid"], 11)
        self.assertFalse(feat(OFF, sparse)["enough"])                                  # 11 < 12: the nominal rule
        self.assertTrue(feat(ON, sparse)["enough"])                                    # 11 >= max(10, 0.6 x 11)
        self.assertNotEqual(gm.read_window(sparse, OFF, sparse[-1].t).command, "PROCEED")
        r = gm.read_window(sparse, ON, sparse[-1].t)
        self.assertEqual(r.command, "PROCEED", r.why)

    def test_below_the_floor_never(self):
        sparse = tu.swing_samples(n=25, hz=1.5)[::2]
        tiny = sparse[:7]
        self.assertFalse(feat(ON, tiny)["enough"])
        self.assertNotEqual(gm.read_window(tiny, ON, tiny[-1].t).command, "PROCEED")

    def test_the_nominal_rate_is_unchanged(self):
        full = tu.swing_samples(n=25, hz=1.5)
        for k in (0, 3, 6):                                                            # a few windows of the 10 Hz stream
            s = full[k:]
            a, b = feat(OFF, s), feat(ON, s)
            self.assertEqual(a, b)
            ra, rb = gm.read_window(s, OFF, s[-1].t), gm.read_window(s, ON, s[-1].t)
            self.assertEqual((ra.command, ra.score, ra.why), (rb.command, rb.score, rb.why))

    def test_it_does_not_read_a_wave_or_one_swing_as_proceed(self):
        for s in (tu.swing_samples(plane="sideways", amp_deg=50.0)[::2], tu.swing_samples(n=25, hz=0.3)[::2]):
            self.assertNotEqual(gm.read_window(s, ON, s[-1].t).command, "PROCEED")

    def test_the_real_key_equals_the_analysis_model(self):
        """analyse_proceed_stop_v4's B1 variant (what 16.19.6 replayed) and the key do the same on the same frames."""
        sparse = tu.swing_samples(n=25, hz=1.5)[::2]
        for s in (sparse, sparse[:9], sparse[:11], tu.swing_samples(n=25, hz=1.5)):
            with ap.variant_wrap({"b1": {"frac": 0.6, "floor": 10}}, OFF, {"stopped": False}):
                model = feat(OFF, s)
            self.assertEqual(feat(ON, s), model)

    def test_the_stop_readings_do_not_depend_on_it(self):
        """Through the whole pipeline (frames -> reader), the STOP, hanging-arm and swinging-hand scenes read the same with and without the floor."""
        import analyse_false_stop_v4 as fs
        import commander_v4 as cm
        import test_c2s_switch_v4 as tc
        cc = cm.load_config()
        for raised, swing in ((True, False), (True, True), (False, False)):
            fr = tc.scene(raised, swing)
            key = lambda r: (r.command, r.score, r.arm, r.frame_class, r.raised, r.moving)      # the proceed features inside the reading do carry the floor's `enough`
            a = [key(prs[0].reading) for _, prs, _ in fs.replay(fr, OFF, cc) if prs]
            b = [key(prs[0].reading) for _, prs, _ in fs.replay(fr, ON, cc) if prs]
            self.assertEqual(a, b, (raised, swing))
            self.assertTrue(a)


@unittest.skipUnless(os.environ.get("B1_REPORT") or os.environ.get("B1_REPLAY"),
                     "opt-in: B1_REPORT=<report.json of analyse_proceed_stop_v4.py --switch> or B1_REPLAY=1 (replays the three zips of ~/Downloads, about 10 minutes)")
class ReplayNumbers(unittest.TestCase):
    """The REAL reader (both keys, as gesture_reader.json says) reproduces the 16.19.6 row 'C2s + B1 floor 10' on the development data."""

    @classmethod
    def setUpClass(cls):
        if os.environ.get("B1_REPORT"):
            cls.rep = json.loads(Path(os.environ["B1_REPORT"]).read_text(encoding="utf-8"))
        else:
            z = Path.home() / "Downloads"
            cls.rep = ap.analyse(str(z / "step5_logs_20261117_011303.zip"), str(z / "stop_session_logs_20261115_192423.zip"),
                                 str(z / "anisha_gesture_logs_20261114_143539.zip"), ap.load_config(), round2="switch")

    def v(self, key, ds):
        return self.rep["variants"][key][ds]

    def test_the_proceed_holds_of_16_19_6(self):
        self.assertEqual({k: (self.v("final", k)["holds_accepted"], self.v("final", k)["holds"], self.v("final", k)["proceed_frames_read"]) for k in ("S5", "STOP", "D4*")},
                         {"S5": (59, 62, 664), "STOP": (26, 26, 587), "D4*": (38, 38, 537)})
        self.assertEqual((self.v("current", "S5")["holds_accepted"], self.v("current", "S5")["holds"]), (35, 62))

    def test_no_stop_reading_changes_with_the_floor(self):
        for k in ("S5", "STOP", "D4*"):
            self.assertEqual(self.v("final", k)["false_stop_total"], self.v("switch", k)["false_stop_total"], k)
        self.assertEqual(self.v("final", "STOP")["a"]["within_1s"], self.v("switch", "STOP")["a"]["within_1s"])
        self.assertEqual(self.v("final", "STOP")["a"]["lost_vs_current"], 0)

    def test_the_moving_readings_differ_only_where_more_proceed_is_read(self):
        mv = {k: self.v("final", k)["moving_identical_to_current"]["different_readings"] for k in ("S5", "STOP", "D4*")}
        self.assertEqual(mv, {"S5": 8, "STOP": 0, "D4*": 8})                                    # 16.19.6 fact 2: up to 8 frames, B1 reads more PROCEED


if __name__ == "__main__":
    unittest.main()
