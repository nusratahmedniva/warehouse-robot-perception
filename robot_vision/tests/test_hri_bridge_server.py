"""Bridge server end to end over localhost: hello, observations with real JPEGs, replies, heartbeat, logging.

A Python client stands in for Unity. The server binds an ephemeral port and writes into a temporary folder.
"""

import csv
import io
import json
import socket
import tempfile
import time
import unittest
from pathlib import Path

import hri_protocol as hp
from hri_bridge_server import BridgeServer, StubPerception

try:
    from PIL import Image
except ImportError:  # pragma: no cover
    Image = None


def jpeg(w, h):
    buf = io.BytesIO()
    Image.new("RGB", (w, h), (40, 90, 160)).save(buf, format="JPEG", quality=70)
    return buf.getvalue()


@unittest.skipIf(Image is None, "Pillow not installed")
class BridgeServerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.run_dir = Path(self.tmp.name)
        cfg = {"host": "127.0.0.1", "port": 0, "heartbeat_s": 0.1, "frame_read_timeout_s": 2.0,
               "save_images_every_n": 2}
        self.server = BridgeServer(cfg, run_dir=self.run_dir, log=lambda *_: None)
        self.port = self.server.start()
        self.client = socket.create_connection(("127.0.0.1", self.port), timeout=2.0)

    def tearDown(self):
        self.client.close()
        self.server.stop()
        self.tmp.cleanup()

    def read_until(self, kind, limit=20):
        for _ in range(limit):
            f = hp.read_frame(self.client)
            if f.header["type"] == kind:
                return f
        self.fail(f"no {kind} within {limit} frames")

    def observation(self, seq, images):
        entries = [{"name": n, "format": "jpeg", "width": w, "height": h, "bytes": len(b)}
                   for n, w, h, b in images]
        hp.send_frame(self.client, hp.message("observation", seq, time.monotonic(), t_sim=seq * 0.1,
                                              robot={"x": 1.0, "z": 2.0, "heading_deg": 0.0, "v": 0.5, "w_dps": 0.0},
                                              state="Navigate", pan_yaw_deg=0.0, images=entries),
                      [b for *_, b in images])

    def test_hello_observation_reply_and_logs(self):
        hp.send_frame(self.client, hp.message("hello", 1, 0.0, client="test"))
        ack = self.read_until("hello_ack")
        self.assertEqual(ack.header["perception"], StubPerception.label)

        g, c = jpeg(730, 530), jpeg(64, 32)
        for seq in (2, 3, 4):
            self.observation(seq, [("gesture", 730, 530, g), ("cam360", 64, 32, c)])
            reply = self.read_until("perception")
            self.assertEqual(reply.header["ack_seq"], seq)
            self.assertEqual(reply.header["gesture"]["command"], "NONE")
            self.assertEqual(reply.header["people"], [])
            self.assertGreaterEqual(reply.header["inference_total_ms"], 0.0)

        hp.send_frame(self.client, hp.message("bye", 5, 1.0, reason="test done"))
        time.sleep(0.3)
        conn = self.run_dir / "conn_001"
        rows = list(csv.DictReader((conn / "frames.csv").open(encoding="utf-8")))
        self.assertEqual([r["type"] for r in rows], ["hello", "observation", "observation", "observation", "bye"])
        self.assertTrue(all(r["images_ok"] == "1" for r in rows if r["type"] == "observation"))
        summary = json.loads((conn / "summary.json").read_text(encoding="utf-8"))
        self.assertEqual(summary["end_reason"], "bye")
        self.assertEqual(summary["observations_with_bad_images"], 0)
        saved = sorted(p.name for p in (conn / "images").iterdir())  # observations 1 and 3 (every 2nd)
        self.assertEqual(saved, ["obs000002_cam360.jpg", "obs000002_gesture.jpg",
                                 "obs000004_cam360.jpg", "obs000004_gesture.jpg"])

    def test_heartbeat_keeps_the_watchdog_quiet(self):
        hp.send_frame(self.client, hp.message("hello", 1, 0.0, client="test"))
        self.read_until("hello_ack")
        times = []
        t_end = time.monotonic() + 1.0
        while time.monotonic() < t_end:
            f = hp.read_frame(self.client)
            times.append(time.monotonic())
            self.assertEqual(f.header["type"], "heartbeat")
        gaps = [b - a for a, b in zip(times, times[1:])]
        self.assertGreaterEqual(len(times), 6)
        self.assertLess(max(gaps), 0.3, "Unity's 0.3 s watchdog would fire")

    def test_wrong_image_size_is_flagged(self):
        self.observation(1, [("gesture", 730, 530, jpeg(100, 100))])
        self.read_until("perception")
        hp.send_frame(self.client, hp.message("bye", 2, 0.0))
        time.sleep(0.3)
        rows = list(csv.DictReader((self.run_dir / "conn_001" / "frames.csv").open(encoding="utf-8")))
        self.assertEqual(rows[0]["images_ok"], "0")

    def test_protocol_error_closes_the_connection_and_server_accepts_again(self):
        self.client.sendall(hp.encode_raw(b"garbage"))
        with self.assertRaises((ConnectionError, OSError)):
            for _ in range(50):
                hp.read_frame(self.client)
        second = socket.create_connection(("127.0.0.1", self.port), timeout=2.0)
        try:
            hp.send_frame(second, hp.message("hello", 1, 0.0))
            for _ in range(20):
                if hp.read_frame(second).header["type"] == "hello_ack":
                    break
            else:
                self.fail("no hello_ack on the second connection")
        finally:
            second.close()
        summary = json.loads((self.run_dir / "conn_001" / "summary.json").read_text(encoding="utf-8"))
        self.assertTrue(summary["end_reason"].startswith("protocol error"))


class FakeVision:
    """Stands in for HriPerception (no models): fixed people, target, gesture and per-model times."""
    label = "fake vision"

    def process(self, frame):
        people = [{"track_id": 3, "bearing_deg": 12.5, "distance_m": 4.2, "distance_source": "ankles", "confidence": 0.9}]
        return {"people": people, "target": dict(people[0]), "command": "FORWARD_LEFT", "confidence": 0.8,
                "gesture_detail": {"source": "arm", "why": "ok", "right_arm_deg": -44.0, "left_arm_deg": -999.0},
                "inference": [{"model": "yolo11s-pose/cam360", "ms": 20.0}, {"model": "yolo11s-pose/gesture", "ms": 15.0},
                              {"model": "mediapipe/stop", "ms": 5.0}],
                "log": {"n_people": 1, "target_id": 3, "gesture_read": "FORWARD_LEFT", "gesture_source": "arm",
                        "model_ms": "yolo11s-pose/cam360:20.00"}}


@unittest.skipIf(Image is None, "Pillow not installed")
class VisionReplyTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.run_dir = Path(self.tmp.name)
        cfg = {"host": "127.0.0.1", "port": 0, "heartbeat_s": 0.1, "frame_read_timeout_s": 2.0, "save_images_every_n": 0}
        self.server = BridgeServer(cfg, perception=FakeVision(), run_dir=self.run_dir, log=lambda *_: None)
        self.port = self.server.start()
        self.client = socket.create_connection(("127.0.0.1", self.port), timeout=2.0)

    def tearDown(self):
        self.client.close()
        self.server.stop()
        self.tmp.cleanup()

    def obs(self, seq):
        return hp.encode(hp.message("observation", seq, 0.0, t_sim=seq * 0.1, robot={"x": 0, "z": 0, "heading_deg": 0},
                                    state="Read", images=[]))

    def replies(self, n):
        out = []
        while len(out) < n:
            f = hp.read_frame(self.client)
            if f.header["type"] == "perception":
                out.append(f.header)
        return out

    def test_reply_has_people_target_gesture_and_per_model_times(self):
        self.client.sendall(self.obs(1))
        r = self.replies(1)[0]
        self.assertEqual(r["ack_seq"], 1)
        self.assertEqual(r["target"]["track_id"], 3)
        self.assertEqual(r["target"]["distance_source"], "ankles")
        self.assertEqual(r["people"][0]["bearing_deg"], 12.5)
        self.assertEqual((r["gesture"]["command"], r["gesture"]["source"]), ("FORWARD_LEFT", "arm"))
        self.assertEqual([m["model"] for m in r["inference"]],
                         ["yolo11s-pose/cam360", "yolo11s-pose/gesture", "mediapipe/stop"])
        self.assertEqual(r["label"], "fake vision")

    def test_stub_reply_has_no_target(self):
        r = hp.perception_reply(1, 0.0, ack_seq=1, label="stub")
        self.assertEqual(r["target"]["track_id"], -1)
        self.assertEqual(r["target"]["distance_m"], -1.0)

    def test_backlog_is_answered_with_the_newest_observation_only(self):
        self.client.sendall(self.obs(1) + self.obs(2) + self.obs(3))
        r = self.replies(1)[0]
        self.assertEqual(r["ack_seq"], 3)
        hp.send_frame(self.client, hp.message("bye", 4, 0.0))
        time.sleep(0.3)
        rows = list(csv.DictReader((self.run_dir / "conn_001" / "frames.csv").open(encoding="utf-8")))
        kinds = [(row["type"], row["seq"]) for row in rows]
        self.assertIn(("observation_skipped", "1"), kinds)
        self.assertIn(("observation_skipped", "2"), kinds)
        answered = [row for row in rows if row["type"] == "observation"]
        self.assertEqual((answered[0]["seq"], answered[0]["skipped_before"], answered[0]["gesture_read"]), ("3", "2", "FORWARD_LEFT"))


if __name__ == "__main__":
    unittest.main()
