"""The C2s reader switch of AUDIT.md 16.19.7 (2026-11-17, chosen after the replay of 16.19.6, disclosed there): while the robot is stopped (|v| < 0.05 m/s in the states read
and approach) a STOP needs the hand still over the 0.3 s stop window; while it moves the STOP rule is exactly as before. The reader reads every window twice (reading and
reading_stopped) when hand.stop_still_when_robot_stopped is true and the controller (control.json stop_rule) chooses. Pinned here: the values, the switch-off = the current reader,
the readings while moving, the controller's choice, and (opt-in, it needs the three zips and about 10 minutes) the 16.19.6 C2s numbers reproduced by the REAL switch."""

import json
import os
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))

import analyse_false_stop_v4 as fs  # noqa: E402
import analyse_proceed_stop_v4 as ap  # noqa: E402
import commander_v4 as cm  # noqa: E402
import gesture_motion as gm  # noqa: E402
import hri_control_v4 as hv  # noqa: E402
import test_hri_control_v4 as thc  # noqa: E402
import test_stop_rule_v4 as tsr  # noqa: E402

CC = cm.load_config()
ON = gm.load_config()
OFF = {**ON, "hand": {**ON["hand"], "stop_still_when_robot_stopped": False}}
CONTROL = [ROOT / "configs/v4/control.json", ROOT / "configs/v4/control_zoom_on.json", ROOT / "configs/v4/control_zoom_off.json"] + \
    sorted((ROOT / "configs/v4/experiments").glob("control_lie_*.json"))


def scene(raised: bool, swing: bool, n: int = 25) -> list:
    return [tsr.frame(i * 0.1, i, raised, swing) for i in range(n)]


class ConfigTests(unittest.TestCase):
    def test_the_values_are_the_declared_ones_and_both_switches_are_on(self):
        self.assertIs(ON["hand"]["stop_still_when_robot_stopped"], True)
        self.assertEqual((ON["window"]["stop_window_s"], ON["motion"]["still_speed_max"]), (0.3, 0.4))        # the reader's own values: no new number
        self.assertEqual(len(CONTROL), 11)
        for f in CONTROL:
            sr = json.loads(f.read_text(encoding="utf-8"))["stop_rule"]
            self.assertEqual({k: sr[k] for k in ("still_when_robot_stopped", "robot_stopped_speed_mps", "states")},
                             {"still_when_robot_stopped": True, "robot_stopped_speed_mps": 0.05, "states": ["read", "approach"]}, f.name)
            self.assertIn("DECIDED 2026-11-17", sr["why"])

    def test_the_v3_path_and_the_default_reading_are_untouched(self):
        self.assertNotIn("robot_stopped", (ROOT / "hri_perception.py").read_text(encoding="utf-8"))        # the v3 classifier knows nothing of it
        import inspect
        self.assertIs(inspect.signature(gm.read_window).parameters["robot_stopped"].default, False)
        self.assertIs(inspect.signature(gm._arm_window).parameters["robot_stopped"].default, False)

    def test_b1_floor_10_was_adopted_after_16_19_7(self):                                                      # AUDIT.md 16.21 (it waited for the rerun in 16.19.7)
        self.assertEqual(ON["proceed"].get("min_valid_floor"), 10)
        self.assertNotIn("min_valid_relative", ON["proceed"])

    def test_the_analysis_declares_the_difference_with_the_disclosure(self):
        d = json.loads((ROOT / "configs/v4/analysis.json").read_text(encoding="utf-8"))["declared_differences"]
        text = " ".join(d)
        for word in ("C2s", "16.19.7", "32 are read within 1.0 s instead of 34", "+0.90 s", "AFTER seeing"):
            self.assertIn(word, text)


class ReaderTests(unittest.TestCase):
    def readings(self, frames, cfg):
        return [prs[0] for _, prs, _ in fs.replay(frames, cfg, CC) if prs]

    def test_switch_off_is_the_current_reader_and_carries_no_second_reading(self):
        for raised, swing in ((True, False), (True, True), (False, False)):
            on, off = self.readings(scene(raised, swing), ON), self.readings(scene(raised, swing), OFF)
            self.assertEqual([p.reading.to_dict() for p in on], [p.reading.to_dict() for p in off])           # the reading never depends on the switch
            self.assertTrue(all(p.reading_stopped is None for p in off))
            self.assertTrue(all(p.reading_stopped is not None for p in on))

    def test_a_swinging_raised_hand_is_a_stop_but_not_while_the_robot_is_stopped(self):
        ps = self.readings(scene(True, True), ON)
        self.assertIn("STOP", [p.reading.command for p in ps])
        self.assertNotIn("STOP", [p.reading_stopped.command for p in ps])

    def test_a_still_raised_hand_is_a_stop_in_both_readings_within_a_few_frames(self):
        ps = self.readings(scene(True, False), ON)
        first = lambda key: next(k for k, p in enumerate(ps) if getattr(p, key).command == "STOP")
        self.assertEqual(first("reading"), first("reading_stopped"))
        self.assertLessEqual(first("reading_stopped"), 4)

    def test_a_hanging_hand_is_no_stop_in_either_reading(self):
        ps = self.readings(scene(False, False), ON)
        self.assertNotIn("STOP", [p.reading.command for p in ps] + [p.reading_stopped.command for p in ps])

    def test_wrist_speed_is_the_one_implementation(self):
        frames = scene(True, True)
        _, prs, smp = fs.replay(frames, ON, CC, keep_samples=True)[-1]
        s = smp[prs[0].track_id]
        buf = [x[2][prs[0].track_id] for x in fs.replay(frames, ON, CC, keep_samples=True)]
        self.assertEqual(fs.wrist_speed(buf, "right", ON, s.t, 0.3), gm.wrist_speed(buf, "right", ON, s.t, 0.3))
        self.assertGreater(gm.wrist_speed(buf, "right", ON, s.t, 0.3), ON["motion"]["still_speed_max"])      # a swing is far above the limit
        self.assertIsNone(gm.wrist_speed(buf[:1], "right", ON, buf[0].t, 0.3))


class ControllerChoiceTests(unittest.TestCase):
    """The controller uses reading_stopped while |v| < 0.05 m/s in the states read / approach, the reader's own reading otherwise."""

    def stop_person(self, with_second=True):
        p = thc.person(7, "STOP")
        if with_second:
            p.reading_stopped = thc.reading("NONE")                        # the short-window rule says: not a STOP
        return p

    def step(self, v, state="read", with_second=True, switch=True):
        r = thc.Rig()
        r.c.state = state
        r.c.approach_point, r.c.target_node = (8.75, 2.5), "J1"                 # what the approach and navigate ticks need
        r.c.v4["stop_rule"] = {**json.loads(CONTROL[0].read_text(encoding="utf-8"))["stop_rule"], "still_when_robot_stopped": switch}
        inp = hv.TickInputV4(time_s=0.1, x=8.75, z=0.5, yaw_deg=0.0, v=v, people=[], people_time_s=0.1, persons=[self.stop_person(with_second)],
                             persons_time_s=0.1, fov_deg=60.0)
        cmd = r.c.step(inp)
        return "stopped: STOP gesture" in cmd.state

    def test_stopped_robot_uses_the_short_window_reading(self):
        self.assertFalse(self.step(0.0))
        self.assertFalse(self.step(0.04, "approach"))

    def test_a_moving_robot_uses_the_readers_own_reading_so_the_fast_stop_is_unchanged(self):
        self.assertTrue(self.step(0.06))                                    # just above 0.05 m/s: the STOP stops it
        self.assertTrue(self.step(0.5))
        self.assertTrue(self.step(-0.5))                                    # backing up is moving too

    def test_other_states_use_the_readers_own_reading(self):
        self.assertTrue(self.step(0.0, "navigate"))                         # the robot stands still behind a person while navigating: not covered by the rule

    def test_switch_off_or_no_second_reading_is_the_current_behaviour(self):
        self.assertTrue(self.step(0.0, switch=False))
        self.assertTrue(self.step(0.0, with_second=False))                  # a person without reading_stopped (the simulator, the switch off in the reader)


# ---------------------------------------------------------------- the 16.19.6 numbers by the REAL switch (opt-in)

ZIPS = {"step5": Path("~/Downloads/step5_logs_20261117_011303.zip").expanduser(), "stop": Path("~/Downloads/stop_session_logs_20261115_192423.zip").expanduser(),
        "d4": Path("~/Downloads/anisha_gesture_logs_20261114_143539.zip").expanduser()}


@unittest.skipUnless(os.environ.get("C2S_REPORT") or (os.environ.get("C2S_REPLAY") == "1" and all(p.is_file() for p in ZIPS.values())),
                     "opt-in: set C2S_REPORT=<report.json of analyse_proceed_stop_v4.py --switch> or C2S_REPLAY=1 with the three zips in ~/Downloads (about 10 minutes)")
class ReplayNumbersTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if os.environ.get("C2S_REPORT"):
            cls.rep = json.loads(Path(os.environ["C2S_REPORT"]).read_text(encoding="utf-8"))
        else:
            cls.rep = ap.analyse(str(ZIPS["step5"]), str(ZIPS["stop"]), str(ZIPS["d4"]), ap.load_config(), round2="switch")

    def fs_(self, key, ds):
        t = self.rep["variants"][key][ds]["false_stop_total"]
        return (t["stop_frames"], t["episodes"], t["stop_frames_moving"], t["episodes_moving"], t["stop_frames_stopped"], t["episodes_stopped"])

    def test_the_current_reader_is_the_one_of_16_19_6(self):
        self.assertEqual(self.fs_("current", "S5"), (216, 150, 20, 14, 196, 136))
        self.assertEqual(self.fs_("current", "STOP"), (67, 29, 21, 12, 46, 17))
        self.assertEqual(self.fs_("current", "D4*"), (80, 44, 16, 8, 64, 36))
        a = self.rep["variants"]["current"]["STOP"]["a"]
        self.assertEqual((a["within_1s"], a["by_robot_state"]["moving"]["within_1s"], a["by_robot_state"]["stopped"]["within_1s"]), (34, 16, 18))

    def test_the_real_switch_reproduces_the_c2s_false_stops_and_proceed_holds(self):
        self.assertEqual(self.fs_("switch", "S5"), (73, 65, 20, 15, 53, 50))
        self.assertEqual(self.fs_("switch", "STOP"), (21, 13, 21, 13, 0, 0))
        self.assertEqual(self.fs_("switch", "D4*"), (28, 19, 16, 8, 12, 11))
        s5, stp, d4 = (self.rep["variants"]["switch"][k] for k in ("S5", "STOP", "D4*"))
        self.assertEqual((s5["holds_accepted"], s5["holds"], s5["proceed_frames_read"]), (37, 62, 377))
        self.assertEqual((stp["holds_accepted"], stp["holds"], stp["proceed_frames_read"]), (26, 26, 587))
        self.assertEqual((d4["holds_accepted"], d4["holds"], d4["proceed_frames_read"]), (38, 38, 519))

    def test_the_real_switch_reproduces_criterion_a_of_16_19_6(self):
        a = self.rep["variants"]["switch"]["STOP"]["a"]
        m, s = a["by_robot_state"]["moving"], a["by_robot_state"]["stopped"]
        self.assertEqual((m["stops"], m["within_1s"], m["lost_from_the_1s_set"], m["read_later_than_current"], m["later_median_s"], m["lost_altogether"]), (22, 15, 1, 10, 0.25, 1))
        self.assertEqual((s["stops"], s["within_1s"], s["lost_from_the_1s_set"], s["read_later_than_current"], s["later_median_s"], s["lost_altogether"]), (18, 17, 1, 15, 0.21, 0))
        self.assertEqual((a["within_1s"], a["lost_vs_current"]), (32, 0))                                 # 32 of 40 within 1.0 s, no STOP lost that the current reader reads

    def test_the_readings_while_the_robot_moves_are_the_current_readers(self):
        mv = {k: self.rep["variants"]["switch"][k]["moving_identical_to_current"]["different_readings"] for k in ("S5", "STOP", "D4*")}
        self.assertEqual(mv, {"S5": 0, "STOP": 0, "D4*": 3})                                                # the 3 of the D4 stand-in were disclosed in 16.19.6, not traced


if __name__ == "__main__":
    unittest.main()
