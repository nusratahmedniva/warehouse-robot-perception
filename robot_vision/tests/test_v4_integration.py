"""v4 live path without models or Unity: the pan-tilt pipeline on synthetic skeletons, the landmark extraction of the v4
hand adapter, the v4 perception worker and guide with fakes, and the server wiring for protocol 3 only."""

import asyncio
import json
import sys
import tempfile
import time
import unittest
from pathlib import Path
from types import SimpleNamespace

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))

import commander_v4 as cm  # noqa: E402
import gesture_adapter_v4 as gav4  # noqa: E402
import gesture_motion as gm  # noqa: E402
import hri_control as hc  # noqa: E402
import hri_control_v4 as hv  # noqa: E402
import hri_perception_v4 as hp4  # noqa: E402
import run_paths as rp  # noqa: E402
import test_hri_control_v4 as tc  # noqa: E402
import v4_synth as vs  # noqa: E402
from bridge import protocol as P  # noqa: E402
from bridge import server as S  # noqa: E402
from bridge.guide_v4 import GuideControllerV4  # noqa: E402
from bridge.perception_v4 import PerceptionWorkerV4  # noqa: E402
from test_bridge import JPEG, hello, telemetry  # noqa: E402
from test_protocol_v3 import V3_CFG, check, frame_pan_tilt  # noqa: E402

RC, CC = gm.load_config(), cm.load_config()
META = {"fx": vs.FX, "fy": vs.FY, "cx": vs.CX, "cy": vs.CY, "width": vs.WIDTH, "height": vs.HEIGHT, "pan_deg": 0.0,
        "robot_yaw_deg": 0.0}


def det(tid, kp, conf):
    xs, ys = kp[:, 0], kp[:, 1]
    return {"track_id": tid, "box": (float(xs.min()), float(ys.min()), float(xs.max()), float(ys.max())), "kp": kp, "conf": conf}


class PipelineTests(unittest.TestCase):
    def test_two_people_one_points(self):
        pipe = hp4.PersonsPipeline(RC, CC)
        out = []
        for i in range(14):
            kp1, c1 = vs.body(left=vs.direction(90.0))                 # the commander, straight ahead
            kp2, c2 = vs.body(x0=-1.2)                                  # a bystander standing with arms down
            hands = {1: [vs.hand(kp1[gm.L_WRIST], axis=(1.0, 0.0), category="Pointing_Up")]}
            out = pipe.update([det(1, kp1, c1), det(2, kp2, c2)], hands, {**META, "t": 0.1 * i})
        by = {p.track_id: p for p in out}
        self.assertEqual(by[1].reading.command, "POINT")
        self.assertEqual(by[2].reading.command, "NONE")
        self.assertTrue(by[1].facing and by[2].facing)
        self.assertLess(abs(by[1].bearing_deg), 5.0)
        self.assertLess(by[2].bearing_deg, -20.0)
        choice = cm.pick_commander(out, CC)
        self.assertEqual(choice.commander, 1)

    def test_untracked_detections_are_skipped_and_old_tracks_purged(self):
        pipe = hp4.PersonsPipeline(RC, CC)
        kp, c = vs.body()
        self.assertEqual(pipe.update([det(-1, kp, c)], {}, {**META, "t": 0.0}), [])
        pipe.update([det(5, kp, c)], {}, {**META, "t": 0.1})
        self.assertIn(5, pipe.buffers)
        pipe.update([], {}, {**META, "t": 5.0})
        self.assertNotIn(5, pipe.buffers)

    def test_hands_are_linked_to_the_right_person(self):
        pipe = hp4.PersonsPipeline(RC, CC)
        kp1, c1 = vs.body(left=vs.direction(90.0, 10.0))
        hand = vs.hand(kp1[gm.L_WRIST], axis=(1.0, 0.0), category="Open_Palm")
        out = []
        for i in range(6):
            out = pipe.update([det(1, kp1, c1)], {1: [hand]}, {**META, "t": 0.1 * i})
        self.assertEqual(out[0].reading.command, "STOP")
        self.assertIsNotNone(out[0].reading.hand_box)


class AdapterV4Tests(unittest.TestCase):
    def fake_result(self, world=True):
        lm = [SimpleNamespace(x=0.1 * i % 1, y=0.05 * i, z=0.0) for i in range(21)]
        w = [SimpleNamespace(x=0.001 * i, y=0.0, z=-0.002 * i) for i in range(21)]
        return SimpleNamespace(gestures=[[SimpleNamespace(category_name="Pointing_Up", score=0.8)], []],
                               handedness=[[SimpleNamespace(category_name="Left")], []], hand_landmarks=[lm, lm],
                               hand_world_landmarks=[w, w] if world else [])

    def test_landmarks_and_world_landmarks_are_kept(self):
        hands = gav4.hands_from_result_v4(self.fake_result())
        self.assertEqual(len(hands), 1)                                # the hand without a category is skipped
        h = hands[0]
        self.assertEqual((h.category, h.score, h.handedness, len(h.landmarks_xy), len(h.world_xyz)), ("Pointing_Up", 0.8, "Left", 21, 21))
        self.assertEqual(gav4.hands_from_result_v4(self.fake_result(world=False))[0].world_xyz, None)

    def test_crop_to_image_coordinates_and_box(self):
        raw = gav4.hands_from_result_v4(self.fake_result())[0]
        h = gav4.to_hand_v4(raw, (100, 50, 300, 250), 730, 530, 7)
        self.assertEqual(h.track_id, 7)
        self.assertEqual(h.landmarks_px.shape, (21, 2))
        self.assertAlmostEqual(h.wrist[0], 100 + raw.landmarks_xy[0][0] * 200)
        self.assertAlmostEqual(h.wrist[1], 50 + raw.landmarks_xy[0][1] * 200)
        self.assertEqual(h.world_xyz.shape, (21, 3))
        self.assertTrue(0 <= h.box[0] <= h.box[2] <= 730 and 0 <= h.box[1] <= h.box[3] <= 530)

    def test_v3_adapter_is_unchanged(self):
        import gesture_adapter as ga
        self.assertNotIn("world", Path(ga.__file__).read_text(encoding="utf-8").lower().replace("world.", ""))   # still drops them


class FakeP:
    """A perception object for the worker: no models."""
    label = "fake"

    def __init__(self, readings):
        self.readings = readings

    def decode_jpeg(self, data):
        return np.zeros((530, 730, 3), np.uint8)

    def people(self, *a, **k):
        return [], 1.0

    def persons(self, img, meta):
        return self.readings, {"yolo11s-pose/gesture": 5.0, "mediapipe/hands": 3.0, "reader/window": 0.5}

    def close(self):
        pass


class WorkerTests(unittest.TestCase):
    def test_pan_tilt_frames_become_person_readings(self):
        with tempfile.TemporaryDirectory() as d:
            w = PerceptionWorkerV4(FakeP([tc.person(7, "WAIT")]), Path(d), verbose=False)
            try:
                h = frame_pan_tilt(seq=3, time_s=12.5, pan_deg=-8.0)
                w.submit(P.Message({**h, "version": 3, "attachments": []}, {"image": JPEG}))
                t0 = time.time()
                while w.snapshot_v4()["persons_time_s"] is None and time.time() - t0 < 5:
                    time.sleep(0.02)
                s = w.snapshot_v4()
                self.assertEqual((s["persons_time_s"], s["pan_deg"], [p.track_id for p in s["persons"]]), (12.5, -8.0, [7]))
                self.assertAlmostEqual(s["fov_deg"], 60.0)
                self.assertIn("yolo11s-pose/gesture", w.snapshot()["inference_ms"])
            finally:
                w.close()
            rows = (Path(d) / "perception.csv").read_text(encoding="utf-8").splitlines()
            self.assertEqual(len(rows), 2)
            self.assertIn("7:WAIT", rows[1])

    def test_360_frames_use_the_v3_path(self):
        with tempfile.TemporaryDirectory() as d:
            w = PerceptionWorkerV4(FakeP([]), Path(d), verbose=False)
            try:
                h = {"type": "frame_360", "seq": 1, "time_s": 1.0, "frame_index": 0, "width": 2048, "height": 1024,
                     "camera_height_m": 1.6, "centre_world_yaw_deg": 0.0, "pose": {"x": 0, "z": 0, "yaw_deg": 0}, "encoding": "jpeg"}
                w.submit(P.Message({**h, "version": 3, "attachments": []}, {"image": JPEG}))
                t0 = time.time()
                while w.snapshot()["people_time_s"] is None and time.time() - t0 < 5:
                    time.sleep(0.02)
                self.assertEqual(w.snapshot()["people_time_s"], 1.0)
            finally:
                w.close()


class FakeWorkerV4:
    label = "fake v4"
    ready = True
    p = object()                                            # no inference_devices: record_inference_devices skips it

    def __init__(self):
        self.t = None
        self.persons = []
        self.people = [{"track_id": 12, "bearing_deg": 3.0, "distance_m": 2.0}]

    def submit(self, msg):
        pass

    def snapshot(self):
        return {"people": self.people, "people_pose": {"x": 8.75, "z": 0.5, "yaw_deg": 0.0}, "people_time_s": self.t,
                "gesture": "NONE", "gesture_confidence": 0.0, "gesture_time_s": None}

    def snapshot_v4(self):
        return {"persons": self.persons, "persons_time_s": self.t, "fov_deg": 60.0, "pan_deg": 0.0}

    def close(self):
        pass


def tel_msg(seq, t, trial=1, running=True, x=8.75, z=0.5):
    h = telemetry(seq, trial_index=trial, trial_running=running, time_s=t, pose={"x": x, "z": z, "yaw_deg": 0.0})
    return P.Message({**h, "version": 3, "attachments": []}, {})


class GuideV4Tests(unittest.TestCase):
    def make(self, d, zoom=True):
        rig = tc.Rig(zoom=zoom)
        worker = FakeWorkerV4()
        g = GuideControllerV4(rig.c, worker, Path(d), log_every=1, hud_cfg=V3_CFG["hud"])
        g.trial = 1                                         # the Rig put the controller into its READ state already
        return rig, worker, g

    def test_replies_are_valid_protocol_3_commands_with_the_v4_fields(self):
        with tempfile.TemporaryDirectory() as d:
            rig, worker, g = self.make(d)
            last = None
            for k in range(1, 14):
                t = 0.1 * k
                worker.t = round(t, 3)
                worker.persons = [tc.point_person(7, 90.0, bearing=3.0, hand=(340.0, 245.0, 360.0, 285.0), arm=(320.0, 225.0, 380.0, 300.0))]
                last = g.on_message(tel_msg(k, t))
                check({"type": "command", "seq": k, "reply_to": k, **last}, P.TO_UNITY, 3)
                if rig.c.state == "execute":
                    break
            g.close()
            self.assertEqual(rig.c.state, "execute")
            hud = last["hud"]
            self.assertEqual((hud["commander_id"], hud["gesture"], hud["gesture_accepted"]), (12, "POINT", "RIGHT"))
            self.assertEqual(hud["point_angle_deg"], 90.0)
            self.assertTrue([q for q in hud["people"] if q["id"] == 12][0]["is_commander"])
            rows = [json.loads(x) for x in (Path(d) / "v4_log.jsonl").read_text().splitlines()]
            self.assertGreater(len(rows), 3)
            self.assertEqual({r["trial"] for r in rows}, {1})
            self.assertEqual(rows[-1]["commander"]["commander"], 7)
            self.assertEqual(rows[-1]["resolution"]["command"], "RIGHT")

    def test_zoom_goes_out_in_the_command(self):
        with tempfile.TemporaryDirectory() as d:
            rig, worker, g = self.make(d)
            fovs = []
            for k in range(1, 9):
                worker.t = round(0.1 * k, 3)
                worker.persons = [tc.person(7, "WAIT", bearing=3.0, hand=(340.0, 245.0, 360.0, 285.0), arm=(320.0, 225.0, 380.0, 300.0))]
                fovs.append(g.on_message(tel_msg(k, 0.1 * k))["vertical_fov_deg"])
            g.close()
            self.assertTrue(any(0 < f < 60.0 for f in fovs), fovs)

    def test_zoom_off(self):
        with tempfile.TemporaryDirectory() as d:
            rig, worker, g = self.make(d, zoom=False)
            worker.t, worker.persons = 0.1, [tc.person(7, "WAIT", bearing=3.0)]
            self.assertEqual(g.on_message(tel_msg(1, 0.1))["vertical_fov_deg"], -1.0)
            g.close()

    def test_idle_reply_keeps_the_phase_1_hud(self):
        with tempfile.TemporaryDirectory() as d:
            rig, worker, g = self.make(d)
            worker.t = 0.1
            r = g.on_message(tel_msg(1, 0.1, trial=-1, running=False))
            g.close()
            self.assertEqual((r["state"], r["vertical_fov_deg"], r["hud"]["commander_id"], r["hud"]["point_angle_deg"]), ("idle", -1.0, -1, -1.0))
            check({"type": "command", "seq": 1, "reply_to": 1, **r}, P.TO_UNITY, 3)


class ServerWiringTests(unittest.IsolatedAsyncioTestCase):
    async def test_protocol_3_guide_run_uses_the_v4_classes_and_writes_their_files(self):
        cfg = {**V3_CFG, "port": 0}
        real = S.make_perception_worker_v4
        S.make_perception_worker_v4 = lambda *a, **k: FakeWorkerV4()
        try:
            with tempfile.TemporaryDirectory() as tmp:
                cfg["paths"] = {"output_root": tmp}
                cfg_path = ROOT / "configs" / "v4" / "bridge.json"
                try:
                    out = await S.run(cfg, cfg_path, "guide", duration_s=0.3, perception="vision", task="Task2")
                finally:
                    rp.set_active_roots({})
                for name in ("run_info.json", "summary.json", "v4_log.jsonl", "decisions.csv", "config_used/control.json",
                             "config_used/commander.json", "config_used/gesture_reader.json", "config_used/hri_control.json"):
                    self.assertTrue((out / name).exists(), name)
                info = json.loads((out / "run_info.json").read_text())
                self.assertEqual(info["protocol_version"], 3)
        finally:
            S.make_perception_worker_v4 = real

    async def test_protocol_2_guide_run_does_not_touch_v4(self):
        cfg, cfg_path = S.load_config()
        called = []
        real = S.make_perception_worker_v4
        S.make_perception_worker_v4 = lambda *a, **k: called.append(1)
        try:
            with tempfile.TemporaryDirectory() as tmp:
                cfg = {**cfg, "port": 0, "paths": {"output_root": tmp}}
                try:
                    out = await S.run(cfg, cfg_path, "guide", duration_s=0.2, perception="off", task="Task2")
                finally:
                    rp.set_active_roots({})
                self.assertFalse((out / "v4_log.jsonl").exists())
                self.assertFalse((out / "config_used" / "control.json").exists())
                self.assertEqual(json.loads((out / "run_info.json").read_text())["protocol_version"], 2)
        finally:
            S.make_perception_worker_v4 = real
        self.assertEqual(called, [])

    def test_reader_frame_rate_matches_the_bridge(self):
        self.assertEqual(S.gesture_motion_hz(), V3_CFG["frame_pan_tilt_hz"])


class ReplayClientTests(unittest.TestCase):
    def test_replay_speaks_the_configured_protocol_version(self):
        import bridge.replay_client as rc
        src = (ROOT / "bridge" / "replay_client.py").read_text(encoding="utf-8")
        self.assertEqual(src.count("version=ver"), 3)
        h = rc.frame_header("frame_pan_tilt", 3, 0, 1.0, 730, 530)
        msg = P.Message({**h, "version": 3, "attachments": []}, {"image": JPEG})
        check(h, P.FROM_UNITY, 3, {"image": JPEG})                  # its pan-tilt intrinsics satisfy protocol 3
        t = rc.telemetry(1, 0.5)
        P.validate(P.Message({**t, "version": 3, "attachments": []}, {}), P.FROM_UNITY, P.Limits.from_config(V3_CFG))
        self.assertEqual(P.decode(P.encode(t, version=3), P.Limits.from_config(V3_CFG))[0].header["version"], 3)


if __name__ == "__main__":
    unittest.main()
