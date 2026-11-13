"""v4 perception on the pan-tilt camera: every person in view with a tracked body (YOLO11s-pose + ByteTrack), the hands
of each person (MediaPipe, gesture_adapter_v4.py) linked to their arms by the wrist, a time buffer per person and the
moving-gesture reader (gesture_motion.py) -> commander_v4.PersonReading per person.

- PersonsPipeline: no models. Takes the detections of one frame and returns the readings; unit-tested on synthetic input.
- HriPerceptionV4: the v3 HriPerception (unchanged; the 360 camera people() path is inherited) plus a tracked pose model
  on the pan-tilt image and the MediaPipe hand adapter v4. v3's single-person gesture() is not used by v4.

Never reads ground truth. Thresholds: configs/v4/gesture_reader.json and configs/v4/commander.json; the 360 distance's ankle
height: configs/v4/perception.json (P1, 2026-11-12). Both models also leave their raw output of the last frame
(last_people_raw, last_persons_raw) for the per-frame model-output log (bridge/perception_v4.py, P12).
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import numpy as np

import commander_v4 as cm
import gesture_motion as gm
import hri_perception as hpm

HERE = Path(__file__).resolve().parent
V4_PERCEPTION = "configs/v4/perception.json"


def load_v4_perception(path: str | Path = V4_PERCEPTION) -> dict:
    p = Path(path)
    return json.loads((p if p.is_absolute() else HERE / p).read_text(encoding="utf-8"))


def _kp_rows(kp, kc) -> list:
    """[[x, y, score], ...] rounded (pixels 1 decimal, scores 3) for the model-output log."""
    if kp is None:
        return []
    return [[round(float(x), 1), round(float(y), 1), round(float(c), 3) if c is not None else None]
            for (x, y), c in zip(kp, kc if kc is not None else [None] * len(kp))]


def people_v4(self, bgr, heading_deg: float, top_deg: float = 90.0, bottom_deg: float = -90.0,
              camera_height_m: float | None = None, centre_world_yaw_deg: float = 0.0) -> tuple[list[dict], float]:
    """hri_perception.HriPerception.people with the v4 ankle height (self.ankle_height_m) in person_distance, and the raw
    detections of the frame in self.last_people_raw. Otherwise the same model, arguments, thresholds and output."""
    p = self.cfg["people"]
    h, w = bgr.shape[:2]
    t0 = time.perf_counter()
    r = self.pano_model.track(bgr, persist=True, tracker=p["tracker"], imgsz=p["imgsz"], conf=p["det_confidence"],
                              device=self.device, verbose=False)[0]
    ms = (time.perf_counter() - t0) * 1000.0
    out, raw = [], []
    self.last_people_raw = raw
    if r.boxes is None or len(r.boxes) == 0:
        return out, ms
    boxes = r.boxes.xyxy.cpu().numpy()
    confs = r.boxes.conf.cpu().numpy()
    ids = r.boxes.id.cpu().numpy().astype(int) if r.boxes.id is not None else [-1] * len(boxes)
    kps = r.keypoints.xy.cpu().numpy() if r.keypoints is not None else [None] * len(boxes)
    kcs = r.keypoints.conf.cpu().numpy() if r.keypoints is not None and r.keypoints.conf is not None else [None] * len(boxes)
    ankle = float(getattr(self, "ankle_height_m", 0.0))
    for box, c, tid, kp, kc in zip(boxes, confs, ids, kps, kcs):
        if box[3] - box[1] < p["min_box_height_px"]:
            continue
        u = float(0.5 * (box[0] + box[2]))
        d, src = hpm.person_distance(box, kp, kc, h, p, top_deg, bottom_deg, camera_height_m, ankle_height_m=ankle)
        q = {"track_id": int(tid), "bearing_deg": round(hpm.pano_bearing(u, w, heading_deg, centre_world_yaw_deg), 2),
             "distance_m": round(d, 3) if d is not None else -1.0, "distance_source": src,
             "confidence": round(float(c), 3), "box_h": float(box[3] - box[1])}
        out.append(q)
        raw.append({"track_id": q["track_id"], "box": [round(float(x), 1) for x in box], "conf": q["confidence"],
                    "kp": _kp_rows(kp, kc), "bearing_deg": q["bearing_deg"], "distance_m": q["distance_m"],
                    "distance_source": src})
    return out, ms


class PersonsPipeline:
    """One buffer per tracked person. update() returns the readings of the people seen in this frame."""

    def __init__(self, reader_cfg: dict, commander_cfg: dict):
        self.rc, self.cc = reader_cfg, commander_cfg
        self.span_s = gm.read_span_s(reader_cfg)              # the 1.0 s window, or PROCEED's longer one
        self.keep_s = 1.5 * self.span_s
        self.buffers: dict[int, gm.PersonBuffer] = {}

    def reset(self) -> None:
        self.buffers.clear()

    def update(self, dets: list[dict], hands_by_track: dict, meta: dict) -> list[cm.PersonReading]:
        """dets: [{'track_id', 'box' (x1, y1, x2, y2), 'kp' (17, 2), 'conf' (17,)}]; hands_by_track: track_id -> HandV4 list;
        meta: t, fx, fy, cx, cy, width, height, pan_deg, robot_yaw_deg and (protocol 3 amendment, P6) tilt_deg."""
        out = []
        thr = self.rc["keypoints"]["body_kp_conf_min"]
        for d in dets:
            tid = d["track_id"]
            if tid < 0:                                    # untracked: no history, no reading
                continue
            kp, conf = np.asarray(d["kp"], float), np.asarray(d["conf"], float)
            linked = gm.link_hands(kp, conf, hands_by_track.get(tid, []), self.rc)
            s = gm.Sample(meta["t"], kp, conf, linked, meta["fx"], meta["fy"], meta["cx"], meta["cy"], meta["width"],
                          meta["height"], meta["pan_deg"], meta["robot_yaw_deg"], tuple(d["box"]),
                          float(meta.get("tilt_deg", 0.0)))
            buf = self.buffers.setdefault(tid, gm.PersonBuffer(self.keep_s))
            buf.add(s)
            reading = gm.read_window(buf.window(meta["t"], self.span_s), self.rc, meta["t"])
            facing, why = cm.facing_check(s, self.cc, thr)
            out.append(cm.PersonReading(tid, cm.body_bearing_deg(s, thr), facing, why, reading, tuple(d["box"])))
        for tid in [k for k, b in self.buffers.items() if b.last_t is not None and meta["t"] - b.last_t > self.keep_s]:
            del self.buffers[tid]
        return out


def persons_raw(dets: list, hands: dict) -> dict:
    """The pan-tilt model outputs of one frame for the model-output log (P12): every tracked body with its 17 keypoints and
    every hand (21 landmarks, world landmarks, MediaPipe label and score, box), keyed by track id."""
    return {"people": [{"track_id": int(d["track_id"]), "box": [round(float(x), 1) for x in d["box"]],
                        "kp": _kp_rows(d["kp"], d["conf"])} for d in dets],
            "hands": [{"track_id": h.track_id, "category": h.category, "score": round(float(h.score), 3),
                       "handedness": h.handedness,
                       "lm": [[round(float(x), 1), round(float(y), 1)] for x, y in np.asarray(h.landmarks_px)],
                       "world": ([[round(float(v), 4) for v in xyz] for xyz in np.asarray(h.world_xyz)]
                                 if h.world_xyz is not None else None),
                       "box": [round(float(x), 1) for x in h.box], "wrist": [round(float(x), 1) for x in h.wrist]}
                      for hs in hands.values() for h in hs]}


class HriPerceptionV4(hpm.HriPerception):
    label = "vision v4 (YOLO11s-pose tracked + MediaPipe hands + moving-gesture reader)"
    people = people_v4                                         # the 360 camera with the v4 ankle height (P1)

    def __init__(self, cfg: dict, reader_cfg: dict, commander_cfg: dict, device: str | None = None,
                 v4_cfg: dict | None = None):
        from ultralytics import YOLO

        import gesture_adapter_v4 as gav4
        self.ankle_height_m = float((v4_cfg if v4_cfg is not None else load_v4_perception())["ankle_height_m"])
        self.last_people_raw: list = []
        self.last_persons_raw: dict = {}
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
        self.last_persons_raw = persons_raw(dets, hands)
        return readings, {"yolo11s-pose/gesture": yolo_ms, "mediapipe/hands": mp_ms, "reader/window": read_ms}
