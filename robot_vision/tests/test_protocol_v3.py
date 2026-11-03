"""Protocol version 3 (docs/protocol_v3.md): schemas, rejected truth keys, version separation, the HUD feed of the
guide controller on a fake telemetry stream, and the server end to end. Version 2 behaviour is covered by test_bridge.py
(unchanged); here only that it stays accepted on a v2 config and refused on a v3 one. No Unity needed."""

import asyncio
import copy
import json
import math
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))

import hri_control as hc  # noqa: E402
from bridge import protocol as P  # noqa: E402
from bridge import server as S  # noqa: E402
from bridge.guide import GuideController  # noqa: E402
from test_bridge import JPEG, POSE, hello, telemetry  # noqa: E402

V3_CFG, _ = S.load_config("configs/v4/bridge.json")
V2_CFG, _ = S.load_config("configs/bridge.json")
LIM3 = P.Limits(4096, 1 << 20, 3)
HUD_N = V3_CFG["hud"]["log_messages_per_direction"]


def hud(**over) -> dict:
    h = {"state": "navigate", "screen_text": "", "commander_id": -1, "gesture": "NONE", "gesture_score": 0.0,
         "gesture_raw": "NONE", "gesture_accepted": "NONE", "point_angle_deg": -1.0,
         "people": [{"id": 4, "bearing_deg": -12.5, "distance_m": 3.2, "is_commander": False}],
         "log": [{"dir": "in", "type": "telemetry", "seq": 3, "text": "pose"},
                 {"dir": "out", "type": "command", "seq": 3, "text": "navigate"}]}
    h.update(over)
    return h


def command(seq=0, **over) -> dict:
    h = {"type": "command", "seq": seq, "reply_to": 1, "v": 0.5, "omega": 0.0, "pan_deg": 0.0, "has_target": False,
         "target_x": 0.0, "target_z": 0.0, "state": "navigate", "screen_text": "", "vertical_fov_deg": -1.0,
         "hud": hud()}
    h.update(over)
    return h


def frame_pan_tilt(seq=1, fov=60.0, w=730, h=530, **over) -> dict:
    fy = (h / 2) / math.tan(math.radians(fov) / 2)
    f = {"type": "frame_pan_tilt", "seq": seq, "time_s": 1.0, "frame_index": 2, "width": w, "height": h, "fx": fy,
         "fy": fy, "cx": w / 2, "cy": h / 2, "vertical_fov_deg": fov, "pan_deg": 0.0, "tilt_deg": 0.0,
         "camera_height_m": 1.2, "pose": dict(POSE), "encoding": "jpeg"}
    f.update(over)
    return f


def msg(header: dict, version: int, attachments=None) -> P.Message:
    return P.Message({**header, "version": version, "attachments": []}, attachments or {})


def check(header, allowed, version, attachments=None):
    P.validate(msg(header, version, attachments), allowed, LIM3 if version == 3 else None)


class CommandSchemaTests(unittest.TestCase):
    def test_valid_v3_command(self):
        check(command(), P.TO_UNITY, 3)
        check(command(vertical_fov_deg=35.0, hud=hud(commander_id=4, gesture="POINT", gesture_score=0.8,
                                                      point_angle_deg=-40.0)), P.TO_UNITY, 3)
        check(command(hud=hud(people=[], log=[])), P.TO_UNITY, 3)

    def test_every_new_field_is_required(self):
        for key in ("vertical_fov_deg", "hud"):
            c = command()
            del c[key]
            with self.assertRaisesRegex(P.MessageError, key):
                check(c, P.TO_UNITY, 3)
        for key in hud():
            c = command()
            del c["hud"][key]
            with self.assertRaisesRegex(P.MessageError, key):
                check(c, P.TO_UNITY, 3)

    def test_wrong_types_rejected(self):
        bad = [("vertical_fov_deg", "wide"), ("hud", None), ("hud", [])]
        for key, value in bad:
            with self.assertRaises(P.MessageError, msg=key):
                check(command(**{key: value}), P.TO_UNITY, 3)
        for key, value in (("state", 1), ("screen_text", None), ("commander_id", 1.5), ("gesture", 3),
                           ("gesture_score", "high"), ("gesture_raw", None), ("gesture_accepted", 0),
                           ("point_angle_deg", None), ("people", {}), ("log", "x")):
            with self.assertRaises(P.MessageError, msg=key):
                check(command(hud=hud(**{key: value})), P.TO_UNITY, 3)

    def test_people_and_log_entries_are_checked(self):
        person = {"id": 1, "bearing_deg": 0.0, "distance_m": 1.0, "is_commander": False}
        for key in person:
            p = {k: v for k, v in person.items() if k != key}
            with self.assertRaisesRegex(P.MessageError, key):
                check(command(hud=hud(people=[p])), P.TO_UNITY, 3)
        with self.assertRaises(P.MessageError):
            check(command(hud=hud(people=[{**person, "is_commander": 1}])), P.TO_UNITY, 3)
        entry = {"dir": "in", "type": "telemetry", "seq": 1, "text": ""}
        for key in entry:
            e = {k: v for k, v in entry.items() if k != key}
            with self.assertRaisesRegex(P.MessageError, key):
                check(command(hud=hud(log=[e])), P.TO_UNITY, 3)
        with self.assertRaises(P.MessageError):
            check(command(hud=hud(log=["telemetry"])), P.TO_UNITY, 3)

    def test_gesture_classes_and_ranges(self):
        for g in ("POINT", "WAIT", "STOP", "NONE"):
            check(command(hud=hud(gesture=g)), P.TO_UNITY, 3)
        for g in ("LEFT", "point", ""):
            with self.assertRaisesRegex(P.MessageError, "gesture"):
                check(command(hud=hud(gesture=g)), P.TO_UNITY, 3)
        for fov in (0.0, -2.0, 180.0, 400.0):
            with self.assertRaisesRegex(P.MessageError, "vertical_fov_deg"):
                check(command(vertical_fov_deg=fov), P.TO_UNITY, 3)
        check(command(vertical_fov_deg=-1), P.TO_UNITY, 3)
        check(command(vertical_fov_deg=20.0), P.TO_UNITY, 3)
        with self.assertRaisesRegex(P.MessageError, "commander_id"):
            check(command(hud=hud(commander_id=-2)), P.TO_UNITY, 3)


class FramePanTiltTests(unittest.TestCase):
    def test_intrinsics_follow_the_zoom(self):
        for fov in (60.0, 30.0, 12.5):
            check(frame_pan_tilt(fov=fov), P.FROM_UNITY, 3, {"image": JPEG})

    def test_mismatch_with_zoom_is_rejected(self):
        for over in ({"fy": 400.0}, {"fx": 300.0}, {"cx": 100.0}, {"cy": 10.0}, {"vertical_fov_deg": 30.0},
                     {"vertical_fov_deg": 0.0}, {"vertical_fov_deg": 180.0}):
            with self.assertRaises(P.MessageError, msg=str(over)):
                check(frame_pan_tilt(**over), P.FROM_UNITY, 3, {"image": JPEG})

    def test_v2_does_not_check_intrinsics(self):
        check(frame_pan_tilt(fy=400.0), P.FROM_UNITY, 2, {"image": JPEG})


class TruthKeyTests(unittest.TestCase):
    KEYS = ("true_gesture", "true_commander", "commander_truth", "gesture_truth", "worker_label", "truth")

    def test_each_truth_key_rejected_at_any_depth(self):
        for key in self.KEYS:
            top = telemetry(1, **{key: "x"})
            nested = telemetry(1, pose={**POSE, key: 1})
            in_list = telemetry(1, nav_corners=[{"x": 0.0, "z": 0.0, key: True}])
            deep = telemetry(1, extra={"a": [{"b": {key.upper(): 1}}]})   # case-insensitive
            for h in (top, nested, in_list, deep):
                with self.assertRaisesRegex(P.MessageError, "forbidden", msg=key):
                    check(h, P.FROM_UNITY, 3)

    def test_other_message_types_too(self):
        for key in self.KEYS:
            with self.assertRaisesRegex(P.MessageError, "forbidden"):
                check({**hello(), key: 1}, P.FROM_UNITY, 3)
            with self.assertRaisesRegex(P.MessageError, "forbidden"):
                check(frame_pan_tilt(**{key: 1}), P.FROM_UNITY, 3, {"image": JPEG})

    def test_goal_keys_still_rejected_in_v3(self):
        for key in sorted(P.FORBIDDEN_KEYS):
            with self.assertRaisesRegex(P.MessageError, "forbidden"):
                check(telemetry(1, **{key: 1.0}), P.FROM_UNITY, 3)

    def test_truth_keys_are_new_in_v3_only(self):
        self.assertEqual(P.FORBIDDEN_KEYS_V3 - P.FORBIDDEN_KEYS, frozenset(self.KEYS))
        for key in self.KEYS:
            check(telemetry(1, **{key: "x"}), P.FROM_UNITY, 2)    # version 2 is unchanged

    def test_hud_is_commander_is_not_a_truth_key(self):
        check(command(hud=hud(people=[{"id": 1, "bearing_deg": 0.0, "distance_m": 1.0, "is_commander": True}])),
              P.TO_UNITY, 3)


class VersionSeparationTests(unittest.TestCase):
    def test_configs(self):
        self.assertEqual(V3_CFG["protocol_version"], 3)
        self.assertEqual(V2_CFG["protocol_version"], 2)
        self.assertEqual(P.Limits.from_config(V3_CFG).version, 3)
        self.assertEqual(P.Limits.from_config(V2_CFG).version, 2)

    def test_v2_accepted_on_v2_config_refused_on_v3_config(self):
        raw = P.encode(telemetry(1), version=2)
        P.decode(raw, P.Limits.from_config(V2_CFG))
        with self.assertRaises(P.VersionError):
            P.decode(raw, P.Limits.from_config(V3_CFG))

    def test_v3_accepted_on_v3_config_refused_on_v2_config(self):
        raw = P.encode(telemetry(1), version=3)
        m, _ = P.decode(raw, P.Limits.from_config(V3_CFG))
        self.assertEqual(m.header["version"], 3)
        with self.assertRaises(P.VersionError):
            P.decode(raw, P.Limits.from_config(V2_CFG))

    def test_v2_command_has_no_hud_requirement(self):
        c = command()
        del c["hud"], c["vertical_fov_deg"]
        check(c, P.TO_UNITY, 2)
        with self.assertRaises(P.MessageError):
            check(c, P.TO_UNITY, 3)

    def test_unknown_versions_refused(self):
        with self.assertRaises(P.MessageError):
            check(command(), P.TO_UNITY, 4)

    def test_v3_config_needs_hud_block(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            bad = {k: v for k, v in V3_CFG.items() if k != "hud"}
            p = Path(d) / "bridge.json"
            p.write_text(json.dumps(bad))
            with self.assertRaisesRegex(ValueError, "hud"):
                S.load_config(p)
            p.write_text(json.dumps({**V3_CFG, "protocol_version": 9}))
            with self.assertRaisesRegex(ValueError, "protocol_version"):
                S.load_config(p)


class FakeWorker:
    label = "fake vision"
    ready = True

    def __init__(self, gesture="NONE", people=None):
        self.gesture = gesture
        self.people = people if people is not None else [{"track_id": 7, "bearing_deg": 15.0, "distance_m": 3.5}]

    def submit(self, msg):
        pass

    def snapshot(self):
        return {"people": self.people, "people_pose": {"x": 6.25, "z": -10.0, "yaw_deg": 0.0}, "people_time_s": 0.0,
                "gesture": self.gesture, "gesture_confidence": 0.9 if self.gesture != "NONE" else 0.0,
                "gesture_time_s": 0.0}


def tel(seq, trial=-1, running=False):
    h = telemetry(seq, trial_index=trial, trial_running=running, time_s=0.05 * seq)
    return P.Message({**h, "version": 3, "attachments": []}, {})


def v3_guide(worker, n=HUD_N, **kw):
    return GuideController(hc.make_controller(), worker, None, protocol_version=3,
                           hud_cfg={"log_messages_per_direction": n}, **kw)


class HudFeedTests(unittest.TestCase):
    def test_every_reply_is_a_valid_v3_command(self):
        g = v3_guide(FakeWorker())
        for i in range(1, 6):
            r = g.on_message(tel(i, trial=1, running=i > 2))
            check({"type": "command", "seq": i, "reply_to": i, **r}, P.TO_UNITY, 3)
            self.assertEqual(r["vertical_fov_deg"], -1.0)

    def test_hud_content(self):
        g = v3_guide(FakeWorker())
        g.on_message(tel(1))
        r = g.on_message(tel(2, trial=1, running=True))
        h = r["hud"]
        self.assertEqual((h["state"], h["screen_text"]), (r["state"], r["screen_text"]))
        self.assertEqual(h["people"], [{"id": 7, "bearing_deg": 15.0, "distance_m": 3.5, "is_commander": False}])
        self.assertEqual((h["commander_id"], h["point_angle_deg"], h["gesture"]), (-1, -1.0, "NONE"))
        self.assertEqual((h["gesture_raw"], h["gesture_accepted"], h["gesture_score"]), ("NONE", "NONE", 0.0))

    def test_stop_reading_shows_raw_and_class(self):
        g = v3_guide(FakeWorker(gesture="STOP"))
        h = g.on_message(tel(1))["hud"]
        self.assertEqual((h["gesture"], h["gesture_raw"], h["gesture_score"]), ("STOP", "STOP", 0.9))

    def test_direction_reading_is_none_class_but_visible_raw(self):
        g = v3_guide(FakeWorker(gesture="LEFT"))
        h = g.on_message(tel(1))["hud"]
        self.assertEqual((h["gesture"], h["gesture_raw"]), ("NONE", "LEFT"))     # v3 reader has no POINT / WAIT

    def test_accepted_gesture_follows_the_dialog(self):
        g = v3_guide(FakeWorker())
        g.c.dialog.accepted = "FORWARD"
        self.assertEqual(g.on_message(tel(1))["hud"]["gesture_accepted"], "FORWARD")

    def test_unknown_distance_and_no_people(self):
        g = v3_guide(FakeWorker(people=[{"track_id": 2, "bearing_deg": -3.0, "distance_m": -1.0}]))
        self.assertEqual(g.on_message(tel(1))["hud"]["people"][0]["distance_m"], -1.0)
        g = v3_guide(FakeWorker(people=[]))
        self.assertEqual(g.on_message(tel(1))["hud"]["people"], [])

    def test_log_keeps_the_last_n_per_direction_oldest_first(self):
        g = v3_guide(FakeWorker(), n=4)
        for i in range(1, 11):
            r = g.on_message(tel(i))
        log = r["hud"]["log"]
        ins, outs = [e for e in log if e["dir"] == "in"], [e for e in log if e["dir"] == "out"]
        self.assertEqual([e["seq"] for e in ins], [7, 8, 9, 10])
        self.assertEqual([e["seq"] for e in outs], [6, 7, 8, 9])          # the answer to telemetry 10 is not sent yet
        self.assertEqual(log, ins + outs)
        self.assertTrue(all(e["type"] == "telemetry" for e in ins) and all(e["type"] == "command" for e in outs))

    def test_log_has_frames_too(self):
        g = v3_guide(FakeWorker())
        f = P.Message({**frame_pan_tilt(seq=5), "version": 3, "attachments": []}, {"image": JPEG})
        self.assertIsNone(g.on_message(f))
        self.assertEqual(g.on_message(tel(6))["hud"]["log"][0]["type"], "frame_pan_tilt")

    def test_v2_guide_unchanged(self):
        g = GuideController(hc.make_controller(), FakeWorker(), None)
        r = g.on_message(tel(1))
        self.assertNotIn("hud", r)
        self.assertNotIn("vertical_fov_deg", r)

    def test_v3_needs_hud_config(self):
        with self.assertRaises(ValueError):
            GuideController(hc.make_controller(), FakeWorker(), None, protocol_version=3)


class ServerV3Tests(unittest.TestCase):
    def test_end_to_end_command_carries_hud(self):
        async def go():
            ctrl = v3_guide(FakeWorker(gesture="STOP"))
            server = S.BridgeServer(V3_CFG, ctrl, None, port=0, verbose=False)
            port = await server.start()
            r, w = await asyncio.open_connection("127.0.0.1", port)
            lim = P.Limits.from_config(V3_CFG)
            w.write(P.encode(hello(), version=3))
            w.write(P.encode(telemetry(1, trial_index=-1, trial_running=False), version=3))
            await w.drain()
            m = await asyncio.wait_for(P.read_message(r, lim), 5)
            w.close()
            await server.close()
            return m
        m = asyncio.run(go())
        self.assertEqual((m.type, m.header["version"], m.header["reply_to"]), ("command", 3, 1))
        self.assertEqual(m.header["hud"]["gesture"], "STOP")
        self.assertEqual(m.header["vertical_fov_deg"], -1.0)

    def test_v2_client_is_refused_by_a_v3_server(self):
        async def go():
            server = S.BridgeServer(V3_CFG, v3_guide(FakeWorker()), None, port=0, verbose=False)
            port = await server.start()
            r, w = await asyncio.open_connection("127.0.0.1", port)
            w.write(P.encode(hello(), version=2))
            await w.drain()
            m = await asyncio.wait_for(P.read_message(r, P.Limits.from_config(V3_CFG)), 5)
            w.close()
            await server.close()
            return m
        m = asyncio.run(go())
        self.assertEqual((m.type, m.header["fatal"]), ("error", True))

    def test_truth_key_from_unity_gets_a_nonfatal_error(self):
        async def go():
            server = S.BridgeServer(V3_CFG, v3_guide(FakeWorker()), None, port=0, verbose=False)
            port = await server.start()
            r, w = await asyncio.open_connection("127.0.0.1", port)
            lim = P.Limits.from_config(V3_CFG)
            w.write(P.encode(telemetry(1, true_commander=3), version=3))
            await w.drain()
            m = await asyncio.wait_for(P.read_message(r, lim), 5)
            w.close()
            await server.close()
            return m
        m = asyncio.run(go())
        self.assertEqual((m.type, m.header["fatal"]), ("error", False))
        self.assertIn("true_commander", m.header["error"])


if __name__ == "__main__":
    unittest.main()
