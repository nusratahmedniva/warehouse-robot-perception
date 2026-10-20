"""Step 3 perception next to the Step 2 bridge: worker (newest frame only, perception.csv, snapshot) and the server
hook (commands unchanged, reading shown on screen). Fake models; no Unity, no weights."""

import csv
import sys
import tempfile
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from bridge import protocol as P  # noqa: E402
from bridge.perception import PerceptionWorker  # noqa: E402
from bridge.server import HelloController, PerceptionController  # noqa: E402

POSE = {"x": 1.0, "z": 2.0, "yaw_deg": 90.0}


class FakePerception:
    label = "fake vision"

    def __init__(self):
        self.calls = []

    @staticmethod
    def decode_jpeg(data):
        return data

    def people(self, img, heading, top, bottom, camera_height_m=None, centre_world_yaw_deg=0.0):
        self.calls.append(("people", img, heading, camera_height_m))
        return [{"track_id": 4, "bearing_deg": 30.0, "distance_m": 3.2, "distance_source": "ankles",
                 "confidence": 0.9, "box_h": 80.0}], 12.0

    def gesture(self, img, t):
        self.calls.append(("gesture", img, t))
        return "LEFT", 0.8, {"source": "arm", "why": "ok", "right_arm_deg": -88.0, "left_arm_deg": None,
                             "stop_score": 0.0}, {"yolo11s-pose/gesture": 9.0, "mediapipe/stop": 4.0}


def frame(kind, index, image=b"img"):
    h = {"type": kind, "seq": index, "time_s": 0.1 * index, "frame_index": index, "pose": dict(POSE),
         "camera_height_m": 1.6, "centre_world_yaw_deg": 0.0}
    return P.Message({**h, "version": P.PROTOCOL_VERSION, "attachments": []}, {"image": image})


def wait_for(cond, timeout=3.0):
    t = time.monotonic() + timeout
    while time.monotonic() < t:
        if cond():
            return True
        time.sleep(0.01)
    return False


class WorkerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.fake = FakePerception()

    def tearDown(self):
        self.tmp.cleanup()

    def test_frames_are_processed_and_logged(self):
        w = PerceptionWorker(self.fake, Path(self.tmp.name), verbose=False)
        w.submit(frame("frame_360", 1))
        w.submit(frame("frame_pan_tilt", 2))
        self.assertTrue(wait_for(lambda: w.processed["frame_360"] == 1 and w.processed["frame_pan_tilt"] == 1))
        s = w.snapshot()
        self.assertEqual((s["target"]["track_id"], s["target"]["distance_m"]), (4, 3.2))
        self.assertNotIn("box_h", s["target"])
        self.assertEqual((s["gesture"], s["gesture_source"]), ("LEFT", "arm"))
        self.assertIn("people", [c[0] for c in self.fake.calls])
        self.assertEqual(self.fake.calls[[c[0] for c in self.fake.calls].index("people")][3], 1.6, "camera height from the header")
        w.close()
        rows = list(csv.DictReader((Path(self.tmp.name) / "perception.csv").open(encoding="utf-8")))
        self.assertEqual(sorted(r["type"] for r in rows), ["frame_360", "frame_pan_tilt"])
        g = next(r for r in rows if r["type"] == "frame_pan_tilt")
        self.assertEqual((g["gesture_read"], g["right_arm_deg"]), ("LEFT", "-88.0"))

    def test_only_the_newest_frame_is_processed(self):
        w = PerceptionWorker(self.fake, None, verbose=False)
        w._lock.acquire()          # hold the worker while three frames arrive
        try:
            w._pending["frame_360"] = frame("frame_360", 1)
        finally:
            w._lock.release()
        w.submit(frame("frame_360", 2, b"two"))
        w.submit(frame("frame_360", 3, b"three"))
        self.assertTrue(wait_for(lambda: w.processed["frame_360"] >= 1))
        time.sleep(0.1)
        imgs = [c[1] for c in self.fake.calls if c[0] == "people"]
        self.assertEqual(imgs[-1], b"three")
        self.assertNotIn(b"two", imgs)
        w.close()


class ControllerTests(unittest.TestCase):
    def test_commands_unchanged_and_reading_on_screen(self):
        hello = {"v_mps": 0.2, "omega_radps": 0.0, "pan_deg": 0.0, "target_ahead_m": 5.0, "state": "hello",
                 "screen_text": "Bridge hello test"}
        w = PerceptionWorker(FakePerception(), None, verbose=False)
        c = PerceptionController(HelloController(hello), w)
        c.on_connect()
        self.assertIsNone(c.on_message(frame("frame_360", 1)))
        self.assertTrue(wait_for(lambda: w.processed["frame_360"] == 1))
        tel = P.Message({"type": "telemetry", "seq": 5, "pose": dict(POSE), "version": P.PROTOCOL_VERSION,
                         "attachments": []}, {})
        r = c.on_message(tel)
        self.assertEqual((r["v"], r["omega"], r["state"]), (0.2, 0.0, "hello"))
        self.assertIn("vision: nearest person +30 deg, 3.2 m", r["screen_text"])
        self.assertTrue(r["screen_text"].startswith("Bridge hello test"))
        w.close()


if __name__ == "__main__":
    unittest.main()
