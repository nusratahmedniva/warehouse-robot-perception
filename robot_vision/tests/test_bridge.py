"""Step 2 TCP bridge: framing, attachments, version, broken messages, schema (goal B never accepted), and the
asyncio server end to end with a fake Unity client on localhost. No Unity needed."""

import asyncio
import json
import struct
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import run_paths as rp  # noqa: E402
from bridge import protocol as P  # noqa: E402
from bridge import server as S  # noqa: E402

LIM = P.Limits(max_header_bytes=4096, max_attachment_bytes=1 << 20)
JPEG = b"\xff\xd8" + bytes(64) + b"\xff\xd9"
UNITY_PROJECT = ROOT.parent / "unity" / "Robotics-Warehouse" / "WarehouseProjectURP"
POSE = {"x": 1.0, "z": 2.0, "yaw_deg": 90.0}


def telemetry(seq: int, **over) -> dict:
    h = {"type": "telemetry", "seq": seq, "time_s": 0.05 * seq, "pose": dict(POSE), "v": 0.0, "omega": 0.0,
         "v_cmd": 0.0, "omega_cmd": 0.0, "pan_deg": 0.0, "collision_count": 0, "reached_end_point": False,
         "nav_has_target": False, "nav_target_x": 0.0, "nav_target_z": 0.0, "nav_status": "none",
         "nav_start_snap_m": -1.0, "nav_target_snap_m": -1.0, "nav_corners": [], "last_command_seq": -1,
         "rtt_telemetry_seq": -1, "rtt_ms": -1.0, "watchdog_stopped": False, "watchdog_count": 0,
         "keyboard_override": False, "estop": False, "frames_360_sent": 0, "frames_360_dropped": 0,
         "frames_pan_tilt_sent": 0, "frames_pan_tilt_dropped": 0}
    h.update(over)
    return h


def hello(seq: int = 0) -> dict:
    return {"type": "hello", "seq": seq, "time_s": 0.0, "client": "unity", "unity_version": "2022.3.62f3",
            "telemetry_hz": 20.0, "frame_360_hz": 5.0, "frame_pan_tilt_hz": 10.0, "watchdog_timeout_s": 0.3}


def frame_pan(seq: int, index: int) -> dict:
    return {"type": "frame_pan_tilt", "seq": seq, "time_s": 1.0, "frame_index": index, "width": 730, "height": 530,
            "fx": 458.99, "fy": 458.99, "cx": 365.0, "cy": 265.0, "vertical_fov_deg": 60.0, "pan_deg": 0.0,
            "tilt_deg": 0.0, "camera_height_m": 1.2, "pose": dict(POSE), "encoding": "jpeg"}


V = b'{"version":%d,' % P.PROTOCOL_VERSION  # start of a raw header with the current version


def raw(header_bytes: bytes, tail: bytes = b"") -> bytes:
    return struct.pack(">I", len(header_bytes)) + header_bytes + tail


class FramingTests(unittest.TestCase):
    def test_roundtrip_with_attachments_in_order(self):
        data = P.encode({"type": "frame_pan_tilt", "seq": 3}, {"image": JPEG, "extra": b"abc"})
        msg, used = P.decode(data, LIM)
        self.assertEqual(used, len(data))
        self.assertEqual(msg.header["version"], P.PROTOCOL_VERSION)
        self.assertEqual(msg.header["attachments"], [{"name": "image", "size": len(JPEG)}, {"name": "extra", "size": 3}])
        self.assertEqual(msg.attachments, {"image": JPEG, "extra": b"abc"})
        self.assertEqual(struct.unpack(">I", data[:4])[0], len(data) - 4 - len(JPEG) - 3)  # big-endian header length

    def test_back_to_back_messages(self):
        data = P.encode(telemetry(1)) + P.encode({"type": "x", "seq": 2}, {"a": b""})
        m1, n1 = P.decode(data, LIM)
        m2, n2 = P.decode(data[n1:], LIM)
        self.assertEqual((m1.seq, m2.seq, n1 + n2), (1, 2, len(data)))
        self.assertEqual(m2.attachments, {"a": b""})

    def test_utf8_header(self):
        msg, _ = P.decode(P.encode({"type": "command", "seq": 0, "screen_text": "Which direction? → ✋"}), LIM)
        self.assertEqual(msg.header["screen_text"], "Which direction? → ✋")

    def test_version(self):
        with self.assertRaises(P.VersionError):
            P.decode(P.encode({"type": "hello", "seq": 0}, version=99), LIM)
        with self.assertRaises(P.FramingError):  # missing version
            P.decode(raw(b'{"type":"hello","seq":0,"attachments":[]}'), LIM)
        with self.assertRaises(P.FramingError):  # version not an integer
            P.decode(raw(b'{"version":"1","type":"hello","seq":0,"attachments":[]}'), LIM)

    def test_broken_headers(self):
        cases = {
            "not json": b"{oops",
            "not an object": b"[1,2]",
            "not utf-8": V + b'"type":"\xff","attachments":[]}',
            "no attachments list": V + b'"type":"hello","seq":0}',
            "attachment without size": V + b'"type":"t","seq":0,"attachments":[{"name":"a"}]}',
            "negative size": V + b'"type":"t","seq":0,"attachments":[{"name":"a","size":-1}]}',
            "duplicate name": V + b'"type":"t","seq":0,"attachments":[{"name":"a","size":0},{"name":"a","size":0}]}',
            "too large": V + b'"type":"t","seq":0,"attachments":[{"name":"a","size":2000000}]}',
            "NaN": V + b'"type":"t","seq":0,"attachments":[],"v":NaN}',
        }
        for name, header in cases.items():
            with self.subTest(name), self.assertRaises(P.FramingError):
                P.decode(raw(header), LIM)

    def test_bad_lengths_and_truncation(self):
        with self.assertRaises(P.FramingError):
            P.decode(struct.pack(">I", 0), LIM)
        with self.assertRaises(P.FramingError):
            P.decode(struct.pack(">I", LIM.max_header_bytes + 1) + b"{}", LIM)
        data = P.encode({"type": "t", "seq": 0}, {"image": JPEG})
        for cut in (2, 10, len(data) - 1):
            with self.subTest(cut=cut), self.assertRaises(P.FramingError):
                P.decode(data[:cut], LIM)

    def test_encode_refuses_nan(self):
        with self.assertRaises(ValueError):
            P.encode({"type": "command", "seq": 0, "v": float("nan")})


class ReadMessageTests(unittest.IsolatedAsyncioTestCase):
    async def test_stream_split_across_reads_then_clean_eof(self):
        data = P.encode(telemetry(1)) + P.encode(frame_pan(2, 0), {"image": JPEG})
        reader = asyncio.StreamReader()
        for i in range(0, len(data), 7):
            reader.feed_data(data[i:i + 7])
        reader.feed_eof()
        m1 = await P.read_message(reader, LIM)
        m2 = await P.read_message(reader, LIM)
        self.assertEqual((m1.type, m2.type, m2.attachments["image"]), ("telemetry", "frame_pan_tilt", JPEG))
        self.assertIsNone(await P.read_message(reader, LIM))

    async def test_truncated_stream(self):
        data = P.encode(frame_pan(0, 0), {"image": JPEG})
        for cut in (2, 20, len(data) - 1):
            reader = asyncio.StreamReader()
            reader.feed_data(data[:cut])
            reader.feed_eof()
            with self.subTest(cut=cut), self.assertRaises(P.FramingError):
                await P.read_message(reader, LIM)


class ValidateTests(unittest.TestCase):
    def check(self, header: dict, attachments: dict | None = None, allowed=P.FROM_UNITY):
        P.validate(P.Message({**header, "version": P.PROTOCOL_VERSION, "attachments": []}, attachments or {}), allowed)

    def test_valid_messages(self):
        self.check(hello())
        self.check(telemetry(1, nav_status="complete", nav_corners=[{"x": 1, "z": 2.5}], rtt_ms=3))
        self.check(frame_pan(2, 0), {"image": JPEG})
        self.check({"type": "command", "seq": 0, "reply_to": -1, "v": 0.2, "omega": 0, "pan_deg": 0, "has_target": False,
                    "target_x": 0, "target_z": 0, "state": "s", "screen_text": ""}, allowed=P.TO_UNITY)

    def test_invalid_messages(self):
        cases = {
            "missing pose": ({k: v for k, v in telemetry(1).items() if k != "pose"}, None),
            "pose missing yaw": (telemetry(1, pose={"x": 0, "z": 0}), None),
            "bool as int": (telemetry(1, collision_count=True), None),
            "string as number": (telemetry(1, v="0.2"), None),
            "bad corner": (telemetry(1, nav_corners=[{"x": 1}]), None),
            "unknown nav status": (telemetry(1, nav_status="maybe"), None),
            "negative seq": (telemetry(-1), None),
            "unknown type": ({"type": "teleport", "seq": 0}, None),
            "command from unity": ({"type": "command", "seq": 0}, None),
            "frame without image": (frame_pan(1, 0), None),
            "frame not jpeg": (frame_pan(1, 0), {"image": b"\x89PNG...."}),
        }
        for name, (header, att) in cases.items():
            with self.subTest(name), self.assertRaises(P.MessageError):
                self.check(header, att)

    def test_goal_b_never_accepted(self):
        for extra in ({"goal": {"x": 1, "z": 2}}, {"pose": {**POSE, "goal_x": 3.0}},
                      {"nav_corners": [{"x": 0, "z": 0, "end_point": 1}]}, {"B": [1, 2]}):
            with self.subTest(extra), self.assertRaises(P.MessageError):
                self.check(telemetry(1, **extra))
        self.check(telemetry(1, reached_end_point=True))  # the flag is allowed; coordinates are not

        def keys(obj):
            if isinstance(obj, dict):
                for k, v in obj.items():
                    yield k
                    yield from keys(v)
            elif isinstance(obj, list):
                for v in obj:
                    yield from keys(v)
        for t in P.FROM_UNITY:
            self.assertFalse(set(keys(P.SCHEMAS[t])) & P.FORBIDDEN_KEYS, t)


class ServerTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.cfg, _ = S.load_config()
        self.cfg = {**self.cfg, "host": "127.0.0.1", "logging": {"save_every_n_frames": 20}}
        out = Path(self.tmp.name) / "run"
        out.mkdir()
        self.log = S.RunLog(out, 20)
        self.server = S.BridgeServer(self.cfg, S.HelloController(self.cfg["hello_test"]), self.log, port=0, verbose=False)
        self.port = await self.server.start()
        self.limits = P.Limits.from_config(self.cfg)
        self.clients = []

    async def asyncTearDown(self):
        for w in self.clients:
            w.close()
        await self.server.close()
        self.log.close()
        self.tmp.cleanup()

    async def connect(self):
        r, w = await asyncio.open_connection("127.0.0.1", self.port)
        self.clients.append(w)
        return r, w

    async def send(self, w, header, attachments=None, version=P.PROTOCOL_VERSION):
        w.write(P.encode(header, attachments, version=version))
        await w.drain()

    async def recv(self, r):
        return await asyncio.wait_for(P.read_message(r, self.limits), 5)

    async def test_hello_test_command(self):
        r, w = await self.connect()
        await self.send(w, hello(0))
        await self.send(w, telemetry(1))
        cmd = await self.recv(r)
        h = cmd.header
        self.assertEqual((h["type"], h["reply_to"], h["v"], h["omega"], h["has_target"]), ("command", 1, 0.2, 0.0, True))
        # yaw 90 = facing +X: 5 m ahead of (1, 2) is (6, 2)
        self.assertAlmostEqual(h["target_x"], 6.0)
        self.assertAlmostEqual(h["target_z"], 2.0)
        await self.send(w, telemetry(2, pose={"x": 3.0, "z": 2.0, "yaw_deg": 90.0}))
        h2 = (await self.recv(r)).header
        self.assertEqual((h2["reply_to"], h2["target_x"]), (2, h["target_x"]))  # target fixed after the first pose
        self.assertGreater(h2["seq"], h["seq"])

    async def test_mute_stops_answering_but_keeps_connection(self):
        self.server.controller = S.HelloController(self.cfg["hello_test"], mute_after_s=0.2)
        r, w = await self.connect()
        await self.send(w, telemetry(1))
        self.assertEqual((await self.recv(r)).header["reply_to"], 1)
        await asyncio.sleep(0.3)
        await self.send(w, telemetry(2))
        with self.assertRaises(asyncio.TimeoutError):  # silent, connection still open
            await asyncio.wait_for(P.read_message(r, self.limits), 0.5)
        self.assertIsNotNone(self.server.active)

    async def test_frames_logged_sampled_and_not_answered(self):
        r, w = await self.connect()
        for i, idx in enumerate((19, 20, 21)):
            await self.send(w, frame_pan(i, idx), {"image": JPEG})
        await self.send(w, telemetry(5))
        cmd = await self.recv(r)
        self.assertEqual(cmd.header["reply_to"], 5)  # first reply is the telemetry answer, frames get none
        saved = sorted(p.name for p in (self.log.out / "frames").iterdir())
        self.assertEqual(saved, ["frame_pan_tilt_000020.jpg"])
        self.assertEqual((self.log.out / "frames" / saved[0]).read_bytes(), JPEG)

    async def test_message_error_keeps_connection(self):
        r, w = await self.connect()
        await self.send(w, {k: v for k, v in telemetry(1).items() if k != "pose"})
        err = await self.recv(r)
        self.assertEqual((err.header["type"], err.header["fatal"]), ("error", False))
        self.assertIn("pose", err.header["error"])
        await self.send(w, telemetry(2, goal={"x": 9, "z": 9}))
        err2 = await self.recv(r)
        self.assertIn("never receives B", err2.header["error"])
        await self.send(w, telemetry(3))
        self.assertEqual((await self.recv(r)).header["reply_to"], 3)

    async def assert_closed_with_fatal_error(self, r):
        err = await self.recv(r)
        self.assertEqual((err.header["type"], err.header["fatal"]), ("error", True))
        self.assertIsNone(await self.recv(r))  # server closed the connection
        return err.header["error"]

    async def test_version_mismatch_closes(self):
        r, w = await self.connect()
        await self.send(w, telemetry(1), version=99)
        self.assertIn("version 99", await self.assert_closed_with_fatal_error(r))

    async def test_broken_json_closes(self):
        r, w = await self.connect()
        w.write(raw(b"{not json"))
        await w.drain()
        await self.assert_closed_with_fatal_error(r)

    async def test_oversize_header_closes(self):
        r, w = await self.connect()
        w.write(struct.pack(">I", self.cfg["max_header_bytes"] + 1))
        await w.drain()
        await self.assert_closed_with_fatal_error(r)

    async def test_truncated_message_then_reconnect(self):
        r, w = await self.connect()
        w.write(P.encode(frame_pan(0, 0), {"image": JPEG})[:-5])
        await w.drain()
        w.close()
        await asyncio.sleep(0.1)
        r2, w2 = await self.connect()
        await self.send(w2, telemetry(7))
        self.assertEqual((await self.recv(r2)).header["reply_to"], 7)
        self.log.lines.flush()
        lines = [json.loads(x) for x in (self.log.out / "messages.jsonl").read_text().splitlines()]
        self.assertEqual([x["type"] for x in lines if x["dir"] == "event"][:3], ["connect", "framing_error", "disconnect"])

    async def test_second_client_rejected(self):
        r, w = await self.connect()
        await self.send(w, telemetry(1))
        await self.recv(r)
        r2, w2 = await self.connect()
        self.assertIn("already connected", await self.assert_closed_with_fatal_error(r2))
        await self.send(w, telemetry(2))
        self.assertEqual((await self.recv(r)).header["reply_to"], 2)  # first client unaffected

    async def test_round_trip_logged_per_message(self):
        r, w = await self.connect()
        await self.send(w, telemetry(1))
        await self.recv(r)
        await self.send(w, telemetry(2, rtt_telemetry_seq=1, rtt_ms=12.5, last_command_seq=0))
        await self.recv(r)
        await self.send(w, telemetry(3, rtt_telemetry_seq=1, rtt_ms=12.5))  # same round trip reported again
        await self.recv(r)
        self.log.lines.flush()
        lines = [json.loads(x) for x in (self.log.out / "messages.jsonl").read_text().splitlines()]
        tel = [x for x in lines if x["dir"] == "in" and x["type"] == "telemetry"]
        self.assertEqual([x["rtt_ms"] for x in tel], [None, 12.5, 12.5])
        s = self.log.summary()["round_trip"]
        self.assertEqual((s["n"], s["mean_ms"], s["coverage"]), (1, 12.5, "1 of 3 telemetry messages"))

    async def test_frame_drop_rate_per_camera_in_summary(self):
        r, w = await self.connect()
        await self.send(w, frame_pan(0, 0), {"image": JPEG})
        await self.send(w, telemetry(1, frames_pan_tilt_sent=38, frames_pan_tilt_dropped=2, frames_360_sent=20, estop=True))
        await self.recv(r)
        w.close()
        await asyncio.sleep(0.1)
        r2, w2 = await self.connect()  # second connection: Unity's counters restart
        await self.send(w2, telemetry(2, frames_pan_tilt_sent=10, frames_360_sent=5, frames_360_dropped=5))
        await self.recv(r2)
        f = self.log.summary()["frames"]
        self.assertEqual(f["pan_tilt"], {"sent_by_unity": 48, "dropped_by_unity": 2, "drop_rate": 0.04, "received_by_python": 1})
        self.assertEqual(f["360"], {"sent_by_unity": 25, "dropped_by_unity": 5, "drop_rate": round(5 / 30, 4),
                                    "received_by_python": 0})
        self.assertTrue(self.log.summary()["estop_seen"])

    async def test_server_close_disconnects_client(self):
        r, w = await self.connect()
        await self.send(w, telemetry(1))
        await self.recv(r)
        await self.server.close()
        self.assertIsNone(await self.recv(r))


class RunFolderTests(unittest.IsolatedAsyncioTestCase):
    async def test_run_writes_portable_run_folder(self):
        cfg, cfg_path = S.load_config()
        with tempfile.TemporaryDirectory() as tmp:
            cfg = {**cfg, "port": 0, "paths": {"output_root": tmp}}
            try:
                out = await S.run(cfg, cfg_path, "hello", duration_s=0.2)
            finally:
                rp.set_active_roots({})
            self.assertTrue(out.name.startswith("bridge_hello_"))
            for name in ("run_info.json", "summary.json", "messages.jsonl", "COMPLETE", "config_used/bridge.json"):
                self.assertTrue((out / name).exists(), name)
            info_text = (out / "run_info.json").read_text(encoding="utf-8")
            info = json.loads(info_text)
            self.assertIn("commit", info["git"])
            self.assertEqual(info["bridge_config"], "{project_root}/configs/bridge.json")
            self.assertIn("bridge.json", info["config_sha256"])
            self.assertNotIn(str(ROOT), info_text)
            self.assertEqual(json.loads((out / "summary.json").read_text())["round_trip"]["n"], 0)


class ConfigTests(unittest.TestCase):
    def test_bridge_config(self):
        cfg, _ = S.load_config()
        self.assertEqual(cfg["protocol_version"], P.PROTOCOL_VERSION)
        self.assertEqual(cfg["watchdog_timeout_s"], 0.3)  # docs/project_flow.md
        self.assertEqual(cfg["telemetry_hz"], 20.0)
        self.assertNotIn("goal", json.dumps(cfg).lower())

    def test_estop_decel_is_separate_from_look_ahead_decel(self):
        import footprint as fp
        robot = json.loads((ROOT / "configs" / "robot.json").read_text(encoding="utf-8"))
        decision = json.loads((ROOT / "configs" / "decision.json").read_text(encoding="utf-8"))
        self.assertEqual((robot["decel_mps2"], robot["estop_decel_mps2"]), (0.5, 1.5))
        self.assertGreaterEqual(robot["estop_decel_mps2"], robot["decel_mps2"])
        la = fp.look_ahead(robot, decision["look_ahead"])  # still built on decel_mps2 only
        self.assertEqual((la["decel_mps2"], la["look_ahead_m"]), (0.5, 3.0))

    def test_unity_nav_agent_is_amr(self):
        unity = json.loads((UNITY_PROJECT / "Assets/WarehouseRobot/Bridge/Config/bridge_unity.json").read_text(encoding="utf-8"))
        self.assertEqual(unity["nav"]["agent_type"], "AMR")
        settings = (UNITY_PROJECT / "ProjectSettings/NavMeshAreas.asset").read_text(encoding="utf-8")
        self.assertIn("- AMR", settings)  # the agent type exists in the project

    def test_unity_configs_point_at_shared_configs(self):
        for rel, key, target in (("Assets/WarehouseRobot/Bridge/Config/bridge_unity.json", "bridge_config", "bridge.json"),
                                 ("Assets/WarehouseRobot/Robot/Config/robot_unity.json", "robot_config", "robot.json")):
            with self.subTest(rel):
                paths = json.loads((UNITY_PROJECT / rel).read_text(encoding="utf-8"))["paths"]
                resolved = (UNITY_PROJECT / paths["repo_root_relative_to_unity_project"] / paths[key]).resolve()
                self.assertEqual(resolved, (ROOT / "configs" / target).resolve())


if __name__ == "__main__":
    unittest.main()
