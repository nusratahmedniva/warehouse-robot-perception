"""v4 perception on the pan-tilt camera: every person in view with a tracked body (YOLO11s-pose + ByteTrack), the hands
of each person (MediaPipe, gesture_adapter_v4.py) linked to their arms by the wrist, a time buffer per person and the
moving-gesture reader (gesture_motion.py) -> commander_v4.PersonReading per person.

- PersonsPipeline: no models. Takes the detections of one frame and returns the readings; unit-tested on synthetic input.
- HriPerceptionV4: the v3 HriPerception (unchanged; the 360 camera people() path is inherited) plus a tracked pose model
  on the pan-tilt image and the MediaPipe hand adapter v4. v3's single-person gesture() is not used by v4.

Never reads ground truth. Thresholds: configs/v4/gesture_reader.json and configs/v4/commander.json.
"""

from __future__ import annotations

import time

import numpy as np

import commander_v4 as cm
import gesture_motion as gm
import hri_perception as hpm


class PersonsPipeline:
    """One buffer per tracked person. update() returns the readings of the people seen in this frame."""

    def __init__(self, reader_cfg: dict, commander_cfg: dict):
        self.rc, self.cc = reader_cfg, commander_cfg
        self.keep_s = 1.5 * reader_cfg["window"]["window_s"]
        self.buffers: dict[int, gm.PersonBuffer] = {}

    def reset(self) -> None:
        self.buffers.clear()

    def update(self, dets: list[dict], hands_by_track: dict, meta: dict) -> list[cm.PersonReading]:
        """dets: [{'track_id', 'box' (x1, y1, x2, y2), 'kp' (17, 2), 'conf' (17,)}]; hands_by_track: track_id -> HandV4 list;
        meta: t, fx, fy, cx, cy, width, height, pan_deg, robot_yaw_deg."""
        out = []
        thr = self.rc["keypoints"]["body_kp_conf_min"]
        for d in dets:
            tid = d["track_id"]
            if tid < 0:                                    # untracked: no history, no reading
                continue
            kp, conf = np.asarray(d["kp"], float), np.asarray(d["conf"], float)
            linked = gm.link_hands(kp, conf, hands_by_track.get(tid, []), self.rc)
            s = gm.Sample(meta["t"], kp, conf, linked, meta["fx"], meta["fy"], meta["cx"], meta["cy"], meta["width"],
                          meta["height"], meta["pan_deg"], meta["robot_yaw_deg"], tuple(d["box"]))
            buf = self.buffers.setdefault(tid, gm.PersonBuffer(self.keep_s))
            buf.add(s)
            reading = gm.read_window(buf.window(meta["t"], self.rc["window"]["window_s"]), self.rc, meta["t"])
            facing, why = cm.facing_check(s, self.cc, thr)
            out.append(cm.PersonReading(tid, cm.body_bearing_deg(s, thr), facing, why, reading, tuple(d["box"])))
        for tid in [k for k, b in self.buffers.items() if b.last_t is not None and meta["t"] - b.last_t > self.keep_s]:
            del self.buffers[tid]
        return out


class HriPerceptionV4(hpm.HriPerception):
    label = "vision v4 (YOLO11s-pose tracked + MediaPipe hands + moving-gesture reader)"

    def __init__(self, cfg: dict, reader_cfg: dict, commander_cfg: dict, device: str | None = None):
        from ultralytics import YOLO

        import gesture_adapter_v4 as gav4
        super().__init__(cfg, device)
        self.reader_cfg, self.commander_cfg = reader_cfg, commander_cfg
        self._ga4 = gav4
        self.track_model = YOLO(str(hpm.resolve(cfg["pose_model"]["weights"])), task="pose")
        self.hands = gav4.V4RecognizerAdapter(self.stop_cfg)
        self.pipeline = PersonsPipeline(reader_cfg, commander_cfg)
        frame = hpm.warm_up_frame(*hpm.WARM_UP_SIZES["frame_pan_tilt"])
        meta = {"fx": 458.99, "fy": 458.99, "cx": 365.0, "cy": 265.0, "width": frame.shape[1], "height": frame.shape[0],
                "pan_deg": 0.0, "robot_yaw_deg": 0.0}
        for i in range(3):
            self.persons(frame, {**meta, "t": 0.1 * i})
        for tracker in getattr(self.track_model.predictor, "trackers", None) or []:
            tracker.reset()
        self.pipeline.reset()

    def close(self):
        self.hands.close()
        super().close()

    def persons(self, bgr, meta: dict) -> tuple[list[cm.PersonReading], dict]:
        """Readings of every person in this pan-tilt frame and the per-model milliseconds."""
        g = self.cfg["gesture"]
        t0 = time.perf_counter()
        r = self.track_model.track(bgr, persist=True, tracker=self.cfg["people"]["tracker"], imgsz=g["imgsz"],
                                   conf=g["det_confidence"], device=self.device, verbose=False)[0]
        yolo_ms = (time.perf_counter() - t0) * 1000.0
        dets = []
        if r.boxes is not None and len(r.boxes) > 0 and r.keypoints is not None:
            boxes = r.boxes.xyxy.cpu().numpy()
            ids = r.boxes.id.cpu().numpy().astype(int) if r.boxes.id is not None else [-1] * len(boxes)
            kps, kcs = r.keypoints.xy.cpu().numpy(), r.keypoints.conf.cpu().numpy()
            dets = [{"track_id": int(i), "box": tuple(map(float, b)), "kp": kp, "conf": kc}
                    for b, i, kp, kc in zip(boxes, ids, kps, kcs)]
        t1 = time.perf_counter()
        persons = [self._ga.PersonBox(d["track_id"], *d["box"]) for d in dets if d["track_id"] >= 0]
        hands = self.hands.detect_hands(bgr[:, :, ::-1], persons) if persons else {}
        mp_ms = (time.perf_counter() - t1) * 1000.0
        t2 = time.perf_counter()
        readings = self.pipeline.update(dets, hands, meta)
        read_ms = (time.perf_counter() - t2) * 1000.0
        return readings, {"yolo11s-pose/gesture": yolo_ms, "mediapipe/hands": mp_ms, "reader/window": read_ms}
