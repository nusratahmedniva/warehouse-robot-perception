"""Step 3 perception next to the Step 2 bridge: worker (newest frame only, perception.csv, snapshot) and the server
hook (commands unchanged, reading shown on screen). Fake models; no Unity, no weights."""

import csv
import sys
import tempfile
import threading
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


class BlockingPerception(FakePerception):
    """people() waits for release on its first call."""

    def __init__(self, release):
        super().__init__()
        self.release, self.started = release, threading.Event()

    def people(self, img, heading, top, bottom, camera_height_m=None, centre_world_yaw_deg=0.0):
        self.started.set()
        self.release.wait(3)
        return super().people(img, heading, top, bottom, camera_height_m, centre_world_yaw_deg)


class SlowPeoplePerception(FakePerception):
    """Every people() call takes delay_s (a simulated slow model call)."""

    def __init__(self, delay_s):
        super().__init__()
        self.delay_s, self.started = delay_s, threading.Event()

    def people(self, img, heading, top, bottom, camera_height_m=None, centre_world_yaw_deg=0.0):
        self.started.set()
        time.sleep(self.delay_s)
        return super().people(img, heading, top, bottom, camera_height_m, centre_world_yaw_deg)


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

    def test_ready_after_one_frame_of_each_camera(self):
        w = PerceptionWorker(self.fake, None, verbose=False)
        self.assertFalse(w.ready)
        w.submit(frame("frame_360", 1))
        self.assertTrue(wait_for(lambda: w.processed["frame_360"] == 1))
        self.assertFalse(w.ready)                 # the pan-tilt camera has not been processed yet
        w.submit(frame("frame_pan_tilt", 2))
        self.assertTrue(wait_for(lambda: w.ready))
        w.close()

    def test_newest_frame_first_with_counted_drops(self):
        """While the 360 thread is busy, frames 2, 3 and 4 arrive: 2 and 3 are dropped (counted), 4 is next."""
        release = threading.Event()
        fake = BlockingPerception(release)
        w = PerceptionWorker(fake, Path(self.tmp.name), verbose=False)
        w.submit(frame("frame_360", 1, b"one"))
        self.assertTrue(wait_for(lambda: fake.started.is_set()))       # frame 1 is being processed
        for i, img in ((2, b"two"), (3, b"three"), (4, b"four")):
            w.submit(frame("frame_360", i, img))
        release.set()
        self.assertTrue(wait_for(lambda: w.processed["frame_360"] == 2))
        time.sleep(0.1)
        self.assertEqual([c[1] for c in fake.calls if c[0] == "people"], [b"one", b"four"])
        self.assertEqual(w.summary()["frame_360"]["dropped"], 2)
        w.close()
        rows = [r for r in csv.DictReader((Path(self.tmp.name) / "perception.csv").open(encoding="utf-8"))]
        self.assertEqual([(r["frame_index"], r["skipped_before"]) for r in rows], [("1", "0"), ("4", "2")])

    def test_slow_panorama_call_does_not_hold_the_gesture_reader(self):
        """One thread per camera: a 1.5 s person-detection call leaves the gesture thread free."""
        fake = SlowPeoplePerception(1.5)
        w = PerceptionWorker(fake, None, verbose=False)
        w.submit(frame("frame_360", 1))
        self.assertTrue(wait_for(lambda: fake.started.is_set()))
        t0 = time.perf_counter()
        for i in range(2, 6):
            w.submit(frame("frame_pan_tilt", i))
            self.assertTrue(wait_for(lambda: w.processed["frame_pan_tilt"] == i - 1, 1.0))
        self.assertLess(time.perf_counter() - t0, 0.5)
        self.assertEqual(w.processed["frame_360"], 0)                  # still inside the slow call
        self.assertEqual(w.snapshot()["gesture_time_s"], 0.5)          # newest gesture frame (time 0.1 * 5)
        self.assertTrue(wait_for(lambda: w.processed["frame_360"] == 1, 3.0))
        w.close()

    def test_one_thread_per_camera(self):
        w = PerceptionWorker(self.fake, None, verbose=False)
        names = {t.name for t in threading.enumerate()}
        self.assertTrue({"perception-360", "perception-gesture"} <= names)
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


class SlowCallReplyTests(unittest.IsolatedAsyncioTestCase):
    """The asyncio server never runs inference: while a (simulated) 1.5 s perception call is in progress every
    telemetry message is still answered at once (Unity's watchdog is 0.3 s)."""

    async def test_slow_perception_call_does_not_delay_replies(self):
        import asyncio

        from bridge import server as S
        from test_bridge import JPEG, telemetry  # same message builders as the server tests (tests/ is on sys.path)

        cfg, _ = S.load_config()
        cfg = {**cfg, "host": "127.0.0.1"}
        fake = SlowPeoplePerception(1.5)
        worker = PerceptionWorker(fake, None, verbose=False)
        hello_cfg = cfg["hello_test"]
        server = S.BridgeServer(cfg, PerceptionController(HelloController(hello_cfg), worker), None, port=0, verbose=False)
        port = await server.start()
        r, w = await asyncio.open_connection("127.0.0.1", port)
        limits = P.Limits.from_config(cfg)
        try:
            pano = {**frame("frame_360", 1).header, "width": 2048, "height": 1024, "encoding": "jpeg"}
            w.write(P.encode({k: v for k, v in pano.items() if k not in ("version", "attachments")},
                             {"image": JPEG}))
            await w.drain()
            self.assertTrue(await asyncio.to_thread(wait_for, lambda: fake.started.is_set()))
            worst = 0.0
            for seq in range(10, 26):                          # 0.8 s of telemetry at 20 Hz during the 1.5 s call
                t0 = time.perf_counter()
                w.write(P.encode(telemetry(seq)))
                await w.drain()
                reply = await asyncio.wait_for(P.read_message(r, limits), 2)
                worst = max(worst, time.perf_counter() - t0)
                self.assertEqual(reply.header["reply_to"], seq)
                await asyncio.sleep(0.05)
            self.assertEqual(worker.processed["frame_360"], 0, "the slow call was still running")
            self.assertLess(worst, 0.1, worst)
        finally:
            w.close()
            await server.close()
            worker.close()


if __name__ == "__main__":
    unittest.main()
