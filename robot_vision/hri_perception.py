"""Step 4: vision perception for the Unity guided robot (replaces the bridge's stub; label "vision").

People: YOLO11s-pose + ByteTrack on the world-aligned 360 deg panorama; bearing from the column
(hri_protocol.pano_bearing), distance from where the feet meet the floor (level camera, flat floor).
Gesture: YOLO11s-pose on the gesture camera; the arm direction (shoulder -> wrist, elbow straightness, arm length)
is classified into LEFT, FORWARD_LEFT, FORWARD, FORWARD_RIGHT, RIGHT or NONE. Directions are from the ROBOT's
point of view: the worker faces the robot, so the worker's right arm appears on the image left and sends the robot
left. STOP: MediaPipe gesture recognizer through gesture_adapter (Anisha's module, adapter only), STOP-only mapping
(configs/gesture_hri.json); STOP overrides any arm direction.

All thresholds: configs/hri_perception.json. This module never reads ground truth: true positions and scripted
gestures stay in Unity's truth files and are read only by hri_eval_dev.py. The pure functions below need no
models (unit-tested with synthetic keypoints); HriPerception loads the models.
"""

from __future__ import annotations

import json
import math
import time
from dataclasses import dataclass
from pathlib import Path

import numpy as np

import hri_protocol as hp

HERE = Path(__file__).resolve().parent
DEFAULT_CONFIG = HERE / "configs" / "hri_perception.json"
LABEL = "vision (YOLO11s-pose arm direction + MediaPipe STOP)"

# COCO-17 keypoints used here (the person's own left/right).
L_SHOULDER, R_SHOULDER, L_ELBOW, R_ELBOW, L_WRIST, R_WRIST, L_ANKLE, R_ANKLE = 5, 6, 7, 8, 9, 10, 15, 16
DIRECTIONS = ("LEFT", "FORWARD_LEFT", "FORWARD", "FORWARD_RIGHT", "RIGHT")


def load_config(path: str | Path = DEFAULT_CONFIG) -> dict:
    cfg = json.loads(Path(path).read_text(encoding="utf-8"))
    centres = cfg["gesture"]["direction_centres_deg"]
    if set(centres) != set(DIRECTIONS):
        raise ValueError(f"direction_centres_deg must name exactly {DIRECTIONS}")
    if 2 * cfg["gesture"]["direction_tolerance_deg"] >= min(
            abs(a - b) for a in centres.values() for b in centres.values() if a != b):
        raise ValueError("direction_tolerance_deg leaves no NONE band between neighbouring directions")
    return cfg


def resolve(p: str | Path) -> Path:
    p = Path(p)
    return p if p.is_absolute() else HERE / p


# ---------------------------------------------------------------- gesture geometry (pure)

def arm_angle_deg(shoulder, wrist) -> float:
    """Image angle of shoulder -> wrist measured from straight up; + = toward the image right (x right, y down)."""
    dx, dy = wrist[0] - shoulder[0], wrist[1] - shoulder[1]
    return math.degrees(math.atan2(dx, -dy))


def angle_diff_deg(a: float, b: float) -> float:
    """a - b wrapped to [-180, 180)."""
    return (a - b + 180.0) % 360.0 - 180.0


def circular_mean_deg(a: float, b: float) -> float:
    """Mean direction of two angles (deg), robust to the +-180 wrap."""
    x = math.cos(math.radians(a)) + math.cos(math.radians(b))
    y = math.sin(math.radians(a)) + math.sin(math.radians(b))
    return math.degrees(math.atan2(y, x))


def joint_angle_deg(a, b, c) -> float:
    """Angle at b between b->a and b->c (180 = straight)."""
    v1 = np.subtract(a, b, dtype=float)
    v2 = np.subtract(c, b, dtype=float)
    n = np.linalg.norm(v1) * np.linalg.norm(v2)
    if n < 1e-9:
        return 0.0
    return math.degrees(math.acos(float(np.clip(np.dot(v1, v2) / n, -1.0, 1.0))))


@dataclass(frozen=True)
class ArmReading:
    state: str                 # unknown | down | raised
    angle_deg: float | None    # arm direction, from straight up, + = image right
    command: str | None        # a direction, or None (raised but no clear direction / not raised / unknown)
    reason: str


def classify_arm(kp, conf, shoulder: int, elbow: int, wrist: int, shoulder_width: float | None, g: dict) -> ArmReading:
    """One arm from COCO keypoints (kp: (17, 2) pixels, conf: (17,)) with the gesture section of the config."""
    if min(conf[shoulder], conf[elbow], conf[wrist]) < g["keypoint_confidence"]:
        return ArmReading("unknown", None, None, "keypoint below confidence")
    a_sw = arm_angle_deg(kp[shoulder], kp[wrist])
    if abs(a_sw) > g["raised_max_abs_deg"]:
        return ArmReading("down", a_sw, None, "arm down")
    a_ew = arm_angle_deg(kp[elbow], kp[wrist])
    if abs(angle_diff_deg(a_sw, a_ew)) > g["max_segment_disagreement_deg"]:
        return ArmReading("raised", a_sw, None, "segments disagree (bent arm)")
    a = circular_mean_deg(a_sw, a_ew)
    length = float(np.linalg.norm(np.subtract(kp[wrist], kp[shoulder], dtype=float)))
    if shoulder_width is not None and shoulder_width > 1e-6 and length < g["min_arm_to_shoulder_width"] * shoulder_width:
        return ArmReading("raised", a, None, "arm foreshortened")
    for name, centre in g["direction_centres_deg"].items():
        if abs(a - centre) <= g["direction_tolerance_deg"]:
            return ArmReading("raised", a, name, "ok")
    return ArmReading("raised", a, None, "between directions")


def classify_gesture(kp, conf, g: dict) -> tuple[str, dict]:
    """Arm-direction command for one person. Returns (command, detail); NONE when unclear or nothing raised."""
    kp = np.asarray(kp, dtype=float)
    conf = np.asarray(conf, dtype=float)
    sw = None
    if min(conf[L_SHOULDER], conf[R_SHOULDER]) >= g["keypoint_confidence"]:
        sw = float(np.linalg.norm(kp[L_SHOULDER] - kp[R_SHOULDER]))
    right = classify_arm(kp, conf, R_SHOULDER, R_ELBOW, R_WRIST, sw, g)   # worker's right = robot's left
    left = classify_arm(kp, conf, L_SHOULDER, L_ELBOW, L_WRIST, sw, g)
    detail = {"right_arm_deg": right.angle_deg, "left_arm_deg": left.angle_deg,
              "right_arm": right.reason, "left_arm": left.reason}
    raised = [r for r in (right, left) if r.state == "raised"]
    if not raised:
        detail["why"] = "no raised arm" if right.state != "unknown" or left.state != "unknown" else "arms not visible"
        return "NONE", detail
    commands = {r.command for r in raised}
    if None in commands or len(commands) != 1:
        detail["why"] = "unclear or conflicting arms"
        return "NONE", detail
    detail["why"] = "ok"
    return commands.pop(), detail


# ---------------------------------------------------------------- panorama geometry (pure)

def pano_elevation_deg(v: float, height: int) -> float:
    """Elevation of panorama row v (0 = top); 0 = horizon, negative = below."""
    return (0.5 - (v + 0.5) / height) * 180.0


def ground_distance(v: float, height: int, camera_height_m: float) -> float | None:
    """Horizontal distance to the floor point seen at row v (level camera, flat floor); None above the horizon."""
    e = pano_elevation_deg(v, height)
    if e >= -0.05:
        return None
    return camera_height_m / math.tan(math.radians(-e))


def person_distance(box, kp, kconf, pano_height: int, p: dict) -> tuple[float | None, str]:
    """(distance m, source) for one panorama person: 'ankles', 'box_bottom' or 'unknown' (see config)."""
    if kp is not None and kconf is not None:
        ys = [kp[i][1] for i in (L_ANKLE, R_ANKLE) if kconf[i] >= p["ankle_confidence"]]
        if ys:
            d = ground_distance(float(np.mean(ys)), pano_height, p["camera_height_m"])
            if d is not None:
                return d, "ankles"
    bottom = box[3]
    if bottom < pano_height - p["occlusion_margin_px"]:
        d = ground_distance(bottom, pano_height, p["camera_height_m"])
        if d is not None:
            return d, "box_bottom"
    return None, "unknown"


def pick_nearest(people: list[dict]) -> int | None:
    """Index of the person to approach: smallest known distance; if nobody has one, the largest box."""
    if not people:
        return None
    known = [i for i, q in enumerate(people) if q.get("distance_m") is not None and q["distance_m"] >= 0]
    if known:
        return min(known, key=lambda i: people[i]["distance_m"])
    return max(range(len(people)), key=lambda i: people[i].get("box_h", 0.0))


# ---------------------------------------------------------------- models

class HriPerception:
    """Loads YOLO11s-pose twice (tracked panorama, untracked gesture frame) and the MediaPipe STOP adapter."""

    label = LABEL

    def __init__(self, cfg: dict, device: str | None = None):
        import cv2  # noqa: F401 - fail early if OpenCV is missing
        from ultralytics import YOLO

        from check_environment import select_device
        import gesture_adapter as ga

        self.cfg = cfg
        w = resolve(cfg["pose_model"]["weights"])
        if not w.exists():
            raise FileNotFoundError(f"{w} not found (download yolo11s-pose.pt into robot_vision/models, see README)")
        if ga.sha256_file(w) != cfg["pose_model"]["sha256"]:
            raise ValueError(f"{w} does not match the sha256 in the perception config")
        self.device = device or str(select_device(cfg.get("device", "auto")))
        self.pano_model = YOLO(str(w), task="pose")
        self.gesture_model = YOLO(str(w), task="pose")
        s = cfg["stop"]
        self._ga = ga
        self.stop_cfg = ga.load_gesture_config(resolve(s["adapter_config"]))
        self.stop = ga.GestureRecognizerAdapter(self.stop_cfg, s["adapter_mode"])
        self._warm_up()

    def _warm_up(self):
        """First calls compile kernels and load weights; done at start so the 0.3 s watchdog is not hit later."""
        blank = np.zeros((self.cfg["people"]["imgsz"] // 2, self.cfg["people"]["imgsz"], 3), np.uint8)
        self.pano_model.predict(blank, imgsz=self.cfg["people"]["imgsz"], device=self.device, verbose=False)
        self.gesture_model.predict(blank[:530, :730], imgsz=self.cfg["gesture"]["imgsz"], device=self.device, verbose=False)
        self.stop.detect(np.zeros((530, 730, 3), np.uint8), 0.0)

    def close(self):
        self.stop.close()

    @staticmethod
    def _decode(data: bytes):
        import cv2
        img = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR)
        if img is None:
            raise ValueError("JPEG could not be decoded")
        return img  # BGR

    def people(self, bgr, heading_deg: float) -> tuple[list[dict], float]:
        p = self.cfg["people"]
        h, w = bgr.shape[:2]
        t0 = time.perf_counter()
        r = self.pano_model.track(bgr, persist=True, tracker=p["tracker"], imgsz=p["imgsz"], conf=p["det_confidence"],
                                  device=self.device, verbose=False)[0]
        ms = (time.perf_counter() - t0) * 1000.0
        out = []
        if r.boxes is None or len(r.boxes) == 0:
            return out, ms
        boxes = r.boxes.xyxy.cpu().numpy()
        confs = r.boxes.conf.cpu().numpy()
        ids = r.boxes.id.cpu().numpy().astype(int) if r.boxes.id is not None else [-1] * len(boxes)
        kps = r.keypoints.xy.cpu().numpy() if r.keypoints is not None else [None] * len(boxes)
        kcs = r.keypoints.conf.cpu().numpy() if r.keypoints is not None and r.keypoints.conf is not None else [None] * len(boxes)
        for box, c, tid, kp, kc in zip(boxes, confs, ids, kps, kcs):
            if box[3] - box[1] < p["min_box_height_px"]:
                continue
            u = float(0.5 * (box[0] + box[2]))
            d, src = person_distance(box, kp, kc, h, p)
            out.append({"track_id": int(tid), "bearing_deg": round(hp.pano_bearing(u, w, heading_deg), 2),
                        "distance_m": round(d, 3) if d is not None else -1.0, "distance_source": src,
                        "confidence": round(float(c), 3), "box_h": float(box[3] - box[1])})
        return out, ms

    def gesture(self, bgr, timestamp: float) -> tuple[str, float, dict, dict]:
        """(command, confidence, detail, per-model ms) on the gesture-camera frame."""
        g = self.cfg["gesture"]
        t0 = time.perf_counter()
        r = self.gesture_model.predict(bgr, imgsz=g["imgsz"], conf=g["det_confidence"], device=self.device, verbose=False)[0]
        yolo_ms = (time.perf_counter() - t0) * 1000.0
        command, conf, detail, box = "NONE", 0.0, {"why": "no person"}, None
        if r.boxes is not None and len(r.boxes) > 0 and r.keypoints is not None:
            b = r.boxes.xyxy.cpu().numpy()
            i = int(np.argmax((b[:, 2] - b[:, 0]) * (b[:, 3] - b[:, 1])))
            box = b[i]
            kp = r.keypoints.xy.cpu().numpy()[i]
            kc = r.keypoints.conf.cpu().numpy()[i]
            command, detail = classify_gesture(kp, kc, g)
            conf = float(r.boxes.conf.cpu().numpy()[i]) if command != "NONE" else 0.0
        # STOP via the gesture adapter (MediaPipe), on the chosen person's crop.
        t1 = time.perf_counter()
        rgb = bgr[:, :, ::-1]
        persons = [self._ga.PersonBox("target", *map(float, box))] if box is not None else []
        events = self._ga.to_gesture_events(self.stop.detect(rgb, timestamp, persons=persons)) if persons else ()
        mp_ms = (time.perf_counter() - t1) * 1000.0
        stop = float(max((e.confidence for e in events if e.gesture == "STOP"), default=0.0))
        detail["stop_score"] = round(stop, 3)
        if stop >= self.cfg["stop"]["min_confidence"]:
            command, conf, detail["why"] = "STOP", stop, "open palm (MediaPipe)"
            detail["source"] = "mediapipe"
        else:
            detail["source"] = "arm" if command != "NONE" else "none"
        return command, conf, detail, {"yolo11s-pose/gesture": yolo_ms, "mediapipe/stop": mp_ms}

    def process(self, frame: hp.Frame) -> dict:
        """Observation -> reply fields (people, target, gesture, inference) plus a 'log' dict for frames.csv."""
        t_start = time.perf_counter()
        h = frame.header
        heading = float(h.get("robot", {}).get("heading_deg", 0.0))
        imgs = {e.get("name"): data for e, data in zip(h.get("images", []), frame.images)}
        inference = []
        people, command, conf, detail = [], "NONE", 0.0, {"why": "no gesture image"}
        t_dec = time.perf_counter()
        decoded = {k: self._decode(v) for k, v in imgs.items()}
        inference.append({"model": "jpeg_decode", "ms": round((time.perf_counter() - t_dec) * 1000.0, 3)})
        if "cam360" in decoded:
            people, ms = self.people(decoded["cam360"], heading)
            inference.append({"model": "yolo11s-pose/cam360", "ms": round(ms, 3)})
        if "gesture" in decoded:
            command, conf, detail, times = self.gesture(decoded["gesture"], float(h.get("t_sim", 0.0)))
            inference += [{"model": k, "ms": round(v, 3)} for k, v in times.items()]
        i = pick_nearest(people)
        target = dict(people[i]) if i is not None else {"track_id": -1, "bearing_deg": 0.0, "distance_m": -1.0,
                                                          "distance_source": "none", "confidence": 0.0}
        for q in people + [target]:
            q.pop("box_h", None)
        total = (time.perf_counter() - t_start) * 1000.0
        log = {"n_people": len(people), "target_id": target["track_id"], "target_bearing_deg": target["bearing_deg"],
               "target_distance_m": target["distance_m"], "target_distance_source": target["distance_source"],
               "gesture_read": command, "gesture_source": detail.get("source", "none"), "gesture_why": detail.get("why"),
               "right_arm_deg": _r(detail.get("right_arm_deg")), "left_arm_deg": _r(detail.get("left_arm_deg")),
               "stop_score": detail.get("stop_score"), "people_json": json.dumps(people, separators=(",", ":")),
               "model_ms": ";".join(f"{x['model']}:{x['ms']:.2f}" for x in inference)}
        return {"people": people, "target": target, "command": command, "confidence": round(conf, 3),
                "gesture_detail": {"source": detail.get("source", "none"), "why": detail.get("why", ""),
                                   "right_arm_deg": _r(detail.get("right_arm_deg"), -999.0),
                                   "left_arm_deg": _r(detail.get("left_arm_deg"), -999.0)},
                "inference": inference, "total_ms": total, "log": log}


def _r(x, default=None):
    return round(float(x), 2) if x is not None else default
