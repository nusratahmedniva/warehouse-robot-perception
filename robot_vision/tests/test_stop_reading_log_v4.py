"""The per-control-step log of which STOP reading the controller used (AUDIT.md 16.29 item 3): instrument only, no behaviour change. C2s (16.19.7: while the robot stands still in the states
read / approach a STOP is read with the short stillness window, PersonReading.reading_stopped) is provable from the rows: used = 'reading_stopped' or 'reading', per person the command of both
readings and the one used, and the ids whose used / other reading is STOP."""

import dataclasses
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))

import hri_control_v4 as hv  # noqa: E402
import test_hri_control_v4 as tc  # noqa: E402
from bridge.guide_v4 import GuideControllerV4  # noqa: E402
from test_protocol_v3 import V3_CFG  # noqa: E402
from test_v4_integration import FakeWorkerV4, tel_msg  # noqa: E402

SR = {"still_when_robot_stopped": True, "robot_stopped_speed_mps": 0.05, "states": ["read", "approach"]}


def person(tid, current="NONE", stopped="STOP", bearing=0.0):
    p = tc.person(tid, current, bearing=bearing)
    return dataclasses.replace(p, reading_stopped=tc.reading(stopped) if stopped is not None else None)


def rig(sr=SR, log=True):
    r = tc.Rig()
    r.c.v4["stop_rule"] = dict(sr) if sr is not None else {}
    r.c.stop_log_enabled = log
    return r


def tick(r, persons, v=0.0, dt=0.1, persons_age=0.0):
    r.t = round(r.t + dt, 6)
    inp = hv.TickInputV4(time_s=r.t, x=8.75, z=0.5, yaw_deg=0.0, v=v, people=[], people_time_s=r.t, persons=persons, persons_time_s=round(r.t - persons_age, 6), fov_deg=60.0)
    return r.c.step(inp)


class TheRows(unittest.TestCase):
    def test_the_stopped_reading_is_used_when_the_robot_stands_still_in_the_read_state(self):
        r = rig()
        tick(r, [person(7, "NONE", "STOP")])
        row = r.c.pop_stop_log()[0]
        self.assertEqual((row["state"], row["v"], row["switch"], row["applies"], row["used"]), ("read", 0.0, True, True, "reading_stopped"))
        self.assertEqual(row["people"], [{"id": 7, "reading": "NONE", "stopped": "STOP", "used": "STOP", "src": "reading_stopped"}])
        self.assertEqual((row["stop_used"], row["stop_other"]), ([7], []))
        self.assertTrue(r.c.safety_reason)                                                   # and the controller really stopped for that STOP

    def test_the_readers_own_reading_is_used_while_the_robot_moves(self):
        r = rig()
        tick(r, [person(7, "NONE", "STOP")], v=0.5)
        row = r.c.pop_stop_log()[0]
        self.assertEqual((row["applies"], row["used"], row["people"][0]["used"], row["people"][0]["src"]), (False, "reading", "NONE", "reading"))
        self.assertEqual((row["stop_used"], row["stop_other"]), ([], [7]))                  # the other reading (what C2s would have said) is STOP
        self.assertFalse(r.c.safety_reason)

    def test_the_speed_limit_is_the_configured_one(self):
        r = rig()
        for v, applies in ((0.049, True), (0.05, False), (-0.049, True), (-0.2, False)):
            tick(r, [person(7)], v=v)
            self.assertEqual(r.c.pop_stop_log()[0]["applies"], applies, v)

    def test_the_state_must_be_one_of_the_declared_states(self):
        r = rig({**SR, "states": ["approach"]})                                              # the controller is in `read`, which this config does not list
        tick(r, [person(7)])
        row = r.c.pop_stop_log()[0]
        self.assertEqual((row["state"], row["switch"], row["applies"], row["used"]), ("read", True, False, "reading"))

    def test_the_switch_off_or_absent_means_the_readers_own_reading(self):
        for sr in ({"still_when_robot_stopped": False, "robot_stopped_speed_mps": 0.05, "states": ["read"]}, None):
            r = rig(sr)
            tick(r, [person(7)])
            row = r.c.pop_stop_log()[0]
            self.assertEqual((row["switch"], row["applies"], row["used"]), (False, False, "reading"))

    def test_a_person_without_a_stopped_reading_is_read_with_its_own(self):
        r = rig()
        tick(r, [person(7, "WAIT", None), person(8, "NONE", "STOP")])
        row = r.c.pop_stop_log()[0]
        self.assertTrue(row["applies"])
        self.assertEqual([(q["id"], q["used"], q["src"]) for q in row["people"]], [(7, "WAIT", "reading"), (8, "STOP", "reading_stopped")])
        self.assertEqual(row["stop_used"], [8])

    def test_a_stale_persons_frame_has_no_persons(self):
        r = rig()
        tick(r, [person(7)], persons_age=5.0)                                                # older than gesture_stale_s: the controller sees nobody
        row = r.c.pop_stop_log()[0]
        self.assertEqual((row["people"], row["stop_used"], row["stop_other"]), ([], [], []))

    def test_one_row_per_control_step_and_pop_clears_it(self):
        r = rig()
        for _ in range(7):
            tick(r, [person(7)])
        rows = r.c.pop_stop_log()
        self.assertEqual(len(rows), 7)
        self.assertEqual([x["t"] for x in rows], [round(0.1 * k, 3) for k in range(1, 8)])
        self.assertEqual(r.c.pop_stop_log(), [])

    def test_nothing_is_collected_unless_enabled(self):
        r = rig(log=False)
        self.assertFalse(tc.Rig().c.stop_log_enabled)                                         # off by default
        for _ in range(5):
            tick(r, [person(7)])
        self.assertEqual(r.c.pop_stop_log(), [])


def asdict(cmd):
    return dataclasses.asdict(cmd) if dataclasses.is_dataclass(cmd) else dict(vars(cmd))


class NoBehaviourChange(unittest.TestCase):
    def test_the_commands_are_identical_with_the_log_on_and_off(self):
        """The same scripted sequence (still and moving, a STOP only in the stopped reading, a STOP in both, an ordinary POINT) into two controllers."""
        on, off = rig(log=True), rig(log=False)
        script = [([person(7, "NONE", "STOP")], 0.0), ([person(7, "NONE", "STOP")], 0.4), ([person(7, "STOP", "STOP")], 0.0), ([person(7, "NONE", "NONE")], 0.0),
                  ([tc.point_person(9, 90.0)], 0.0), ([person(7, "WAIT", None)], 0.2), ([], 0.0), ([person(7, "NONE", "STOP")], 0.0)] * 4
        for persons, v in script:
            a, b = asdict(tick(on, persons, v=v)), asdict(tick(off, persons, v=v))
            self.assertEqual(a, b)
            self.assertEqual((on.c.state, on.c.safety_reason, on.c.safety_stops, on.c.commander_pt), (off.c.state, off.c.safety_reason, off.c.safety_stops, off.c.commander_pt))
        self.assertEqual(len(on.c.pop_stop_log()), len(script))
        self.assertEqual(off.c.pop_stop_log(), [])

    def test_the_input_is_changed_exactly_as_before(self):
        r = rig(log=True)
        inp = hv.TickInputV4(time_s=0.1, x=8.75, z=0.5, yaw_deg=0.0, v=0.0, people_time_s=0.1, persons=[person(7, "NONE", "STOP")], persons_time_s=0.1, fov_deg=60.0)
        r.c.step(inp)
        self.assertEqual(inp.persons[0].reading.command, "STOP")                              # C2s replaced the reading, as it always did


class TheGuideWritesTheFile(unittest.TestCase):
    def test_stop_reading_jsonl_has_a_row_per_control_step(self):
        with tempfile.TemporaryDirectory() as d:
            r = tc.Rig()
            worker = FakeWorkerV4()
            g = GuideControllerV4(r.c, worker, Path(d), log_every=1, hud_cfg=V3_CFG["hud"])
            g.trial = 1
            self.assertTrue(r.c.stop_log_enabled)                                             # the guide switches the instrument on
            for k in range(1, 6):
                worker.t = round(0.1 * k, 3)
                worker.persons = [person(7, "NONE", "STOP")]
                g.on_message(tel_msg(k, 0.1 * k))
            g.close()
            rows = [json.loads(x) for x in (Path(d) / "stop_reading.jsonl").read_text(encoding="utf-8").splitlines()]
            self.assertEqual(len(rows), 5)
            self.assertEqual({x["trial"] for x in rows}, {1})
            self.assertTrue(all(x["used"] in ("reading", "reading_stopped") and "people" in x and "applies" in x for x in rows))
            self.assertEqual(rows[0]["people"][0]["id"], 7)
            self.assertEqual(r.c.pop_stop_log(), [])                                          # the guide took them all

    def test_the_decisions_csv_and_the_v4_log_are_unchanged_files(self):
        with tempfile.TemporaryDirectory() as d:
            r = tc.Rig()
            g = GuideControllerV4(r.c, FakeWorkerV4(), Path(d), log_every=1, hud_cfg=V3_CFG["hud"])
            g.close()
            names = sorted(p.name for p in Path(d).iterdir())
            self.assertIn("decisions.csv", names)
            self.assertIn("v4_log.jsonl", names)
            self.assertIn("stop_reading.jsonl", names)
            header = (Path(d) / "decisions.csv").read_text(encoding="utf-8").splitlines()[0]
            self.assertNotIn("stop_reading", header)                                          # no column was added to the shared decisions.csv


class Isolation(unittest.TestCase):
    def test_the_v3_guide_and_controller_are_untouched(self):
        for name in ("bridge/guide.py", "hri_control.py"):
            self.assertNotIn("stop_log", (ROOT / name).read_text(encoding="utf-8"), name)


if __name__ == "__main__":
    unittest.main()
