"""Gesture adapter: the teammate's MediaPipe gesture recognizer -> GestureEvent for Step 9.

The module itself (git submodule external/media_pipe_gesture, configs/gesture.json -> source) is not modified or
imported; the adapter uses the same model file and the same category mapping as her gesture_heuristics.py, in
IMAGE running mode on unmirrored frames.

Two modes (configs/gesture.json -> modes):
- full_frame:  her approach (baseline). The whole frame goes to the recognizer; a hand is assigned to the person
               box containing its wrist landmark (none or several -> track_id None).
- person_crop: one call per tracked person on the upper part of the box plus a margin, resized so the longer side
               is resize_long_side_px. The hand gets that person's track_id.

Every hand becomes a GestureDetection with its raw category, raw score, hand box and wrist in full-image pixels.
No confidence threshold is applied here: the decision threshold lives only in decision.json and is applied by
the decision's gesture filter. A frame (full_frame) or a person (person_crop) without a hand gives one NONE detection.

The geometry and mapping functions need neither MediaPipe nor the model; GestureRecognizerAdapter imports
MediaPipe when it is created. No reference data is read.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path

from decision import GESTURES, GestureEvent

HERE = Path(__file__).resolve().parent
DEFAULT_CONFIG = HERE / "configs" / "gesture.json"
MODES = ("full_frame", "person_crop")
WRIST = 0  # MediaPipe hand landmark index


@dataclass(frozen=True)
class PersonBox:
    """A tracked person's detection box in full-image pixels (x1, y1) top-left, (x2, y2) bottom-right."""
    track_id: int | str
    x1: float
    y1: float
    x2: float
    y2: float


@dataclass(frozen=True)
class RawHand:
    """One hand from the recognizer, in the coordinates of the image it was given: landmarks normalised to [0, 1]
    of that image's width and height (MediaPipe convention; values may fall slightly outside)."""
    category: str
    score: float
    handedness: str | None
    landmarks_xy: tuple[tuple[float, float], ...]


@dataclass(frozen=True)
class GestureDetection:
    timestamp: float
    frame_id: str | None
    mode: str
    track_id: int | str | None
    gesture: str
    raw_category: str | None
    confidence: float | None          # raw category score; None when no hand
    hand_box_xyxy: tuple[float, float, float, float] | None
    wrist_xy: tuple[float, float] | None
    handedness: str | None
    assignment: str                   # wrist_in_person_box | no_containing_box | ambiguous | person_crop | no_hand
    crop_box_xyxy: tuple[int, int, int, int] | None = None

    def as_dict(self) -> dict:
        return asdict(self)


# ---------------------------------------------------------------- config and mapping

def load_gesture_config(path: str | Path = DEFAULT_CONFIG) -> dict:
    cfg = json.loads(Path(path).read_text(encoding="utf-8"))
    seen: dict[str, str] = {}
    for g in ("STOP", "MOVE"):
        for c in cfg["mapping"][g]:
            if c in seen:
                raise ValueError(f"category {c!r} mapped to both {seen[c]} and {g}")
            seen[c] = g
    if cfg["recognizer"]["running_mode"] != "IMAGE" or cfg["recognizer"]["mirror_frames"]:
        raise ValueError("the adapter runs in IMAGE mode on unmirrored frames")
    if set(cfg["modes"]) != set(MODES):
        raise ValueError(f"modes must be {MODES}")
    return cfg


def model_path(cfg: dict) -> Path:
    p = Path(cfg["model"]["path"])
    return p if p.is_absolute() else HERE / p


def map_category(category: str | None, mapping: dict) -> str:
    """Her mapping: a STOP or MOVE category -> that command; any other category or no hand (None) -> NONE."""
    if category is None:
        return "NONE"
    for g in ("STOP", "MOVE"):
        if category in mapping[g]:
            return g
    return "NONE"


# ---------------------------------------------------------------- geometry

def crop_box(person: PersonBox, img_w: int, img_h: int, crop_cfg: dict) -> tuple[int, int, int, int] | None:
    """Integer crop [x0, x1) x [y0, y1) in full-image pixels: the upper upper_fraction of the person box, grown by
    margin_fraction_of_box_height * box height on every side, clipped to the image. None if empty."""
    h = person.y2 - person.y1
    m = crop_cfg["margin_fraction_of_box_height"] * h
    x0 = max(0, int(round(person.x1 - m)))
    x1 = min(img_w, int(round(person.x2 + m)))
    y0 = max(0, int(round(person.y1 - m)))
    y1 = min(img_h, int(round(person.y1 + crop_cfg["upper_fraction"] * h + m)))
    return (x0, y0, x1, y1) if x1 > x0 and y1 > y0 else None


def resized_size(crop_w: int, crop_h: int, long_side: int) -> tuple[int, int]:
    """(width, height) after scaling the longer side to long_side, aspect ratio kept."""
    s = long_side / max(crop_w, crop_h)
    return max(1, int(round(crop_w * s))), max(1, int(round(crop_h * s)))


def to_image_xy(xn: float, yn: float, region: tuple[int, int, int, int]) -> tuple[float, float]:
    """Normalised coordinates in an image showing region (x0, y0, x1, y1) of the full image -> full-image pixels.
    Resizing the region does not matter: normalised coordinates are relative to the region either way."""
    x0, y0, x1, y1 = region
    return x0 + xn * (x1 - x0), y0 + yn * (y1 - y0)


def hand_geometry(hand: RawHand, region: tuple[int, int, int, int], img_w: int, img_h: int):
    """(hand box clipped to the image, wrist) in full-image pixels."""
    pts = [to_image_xy(x, y, region) for x, y in hand.landmarks_xy]
    xs = [min(max(p[0], 0.0), float(img_w)) for p in pts]
    ys = [min(max(p[1], 0.0), float(img_h)) for p in pts]
    box = (min(xs), min(ys), max(xs), max(ys))
    return box, pts[WRIST]


def assign_track(wrist_xy: tuple[float, float], persons) -> tuple[int | str | None, str]:
    """The track whose box contains the wrist (edges included). None if no box or several boxes contain it."""
    x, y = wrist_xy
    hits = [p.track_id for p in persons if p.x1 <= x <= p.x2 and p.y1 <= y <= p.y2]
    if len(hits) == 1:
        return hits[0], "wrist_in_person_box"
    return None, ("ambiguous" if hits else "no_containing_box")


# ---------------------------------------------------------------- detections from recognizer output

def full_frame_detections(hands, img_w: int, img_h: int, persons, timestamp: float, mapping: dict,
                          frame_id: str | None = None) -> list[GestureDetection]:
    if not hands:
        return [GestureDetection(timestamp, frame_id, "full_frame", None, "NONE", None, None, None, None, None,
                                 "no_hand")]
    out = []
    for h in hands:
        box, wrist = hand_geometry(h, (0, 0, img_w, img_h), img_w, img_h)
        tid, how = assign_track(wrist, persons)
        out.append(GestureDetection(timestamp, frame_id, "full_frame", tid, map_category(h.category, mapping),
                                    h.category, float(h.score), box, wrist, h.handedness, how))
    return out


def crop_detections(hands, crop: tuple[int, int, int, int], person: PersonBox, img_w: int, img_h: int,
                    timestamp: float, mapping: dict, frame_id: str | None = None) -> list[GestureDetection]:
    if not hands:
        return [GestureDetection(timestamp, frame_id, "person_crop", person.track_id, "NONE", None, None, None,
                                 None, None, "no_hand", crop)]
    out = []
    for h in hands:
        box, wrist = hand_geometry(h, crop, img_w, img_h)
        out.append(GestureDetection(timestamp, frame_id, "person_crop", person.track_id,
                                    map_category(h.category, mapping), h.category, float(h.score), box, wrist,
                                    h.handedness, "person_crop", crop))
    return out


_RANK = {"STOP": 2, "MOVE": 1, "NONE": 0}


def to_gesture_events(detections) -> tuple[GestureEvent, ...]:
    """One GestureEvent per track_id (None included): STOP if any detection is STOP, else MOVE if any, else NONE;
    confidence = highest raw score of the chosen gesture (0.0 without a hand). No threshold is applied."""
    best: dict = {}
    for d in detections:
        conf = d.confidence if d.confidence is not None else 0.0
        cur = best.get(d.track_id)
        if cur is None or _RANK[d.gesture] > _RANK[cur[0]] or (d.gesture == cur[0] and conf > cur[1]):
            best[d.track_id] = (d.gesture, conf, d.timestamp)
    return tuple(GestureEvent(t, tid, g, c) for tid, (g, c, t) in best.items())


# ---------------------------------------------------------------- MediaPipe wrapper

def sha256_file(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def hands_from_result(result) -> list[RawHand]:
    """MediaPipe GestureRecognizerResult -> RawHand list; only the top category of each hand, as in her code."""
    out = []
    for i, cats in enumerate(result.gestures):
        if not cats:
            continue
        hd = result.handedness[i][0].category_name if i < len(result.handedness) and result.handedness[i] else None
        lms = tuple((lm.x, lm.y) for lm in result.hand_landmarks[i])
        out.append(RawHand(cats[0].category_name, cats[0].score, hd, lms))
    return out


class GestureRecognizerAdapter:
    """MediaPipe GestureRecognizer in IMAGE mode for one adapter mode. Frames are RGB uint8 arrays (H, W, 3),
    never mirrored. Use as a context manager or call close()."""

    def __init__(self, cfg: dict, mode: str):
        if mode not in MODES:
            raise ValueError(f"mode {mode!r} not in {MODES}")
        import mediapipe as mp
        from mediapipe.tasks import python as mp_python
        from mediapipe.tasks.python import vision

        path = model_path(cfg)
        if not path.exists():
            raise FileNotFoundError(f"{path} not found: run 'git submodule update --init' in the repository root")
        if sha256_file(path) != cfg["model"]["sha256"]:
            raise ValueError(f"{path} does not match the sha256 in the gesture config")
        self.cfg, self.mode, self.mapping, self._mp = cfg, mode, cfg["mapping"], mp
        rec = cfg["recognizer"]
        options = vision.GestureRecognizerOptions(
            base_options=mp_python.BaseOptions(model_asset_path=str(path)),
            running_mode=vision.RunningMode.IMAGE,
            num_hands=cfg["modes"][mode]["num_hands"],
            min_hand_detection_confidence=rec["min_hand_detection_confidence"],
            min_hand_presence_confidence=rec["min_hand_presence_confidence"])
        self._rec = vision.GestureRecognizer.create_from_options(options)

    def _recognize(self, rgb) -> list[RawHand]:
        import numpy as np
        img = self._mp.Image(image_format=self._mp.ImageFormat.SRGB, data=np.ascontiguousarray(rgb))
        return hands_from_result(self._rec.recognize(img))

    def detect(self, rgb, timestamp: float, persons=(), frame_id: str | None = None) -> list[GestureDetection]:
        h, w = rgb.shape[:2]
        if self.mode == "full_frame":
            return full_frame_detections(self._recognize(rgb), w, h, persons, timestamp, self.mapping, frame_id)
        import cv2
        ccfg = self.cfg["modes"]["person_crop"]
        out = []
        for p in persons:
            crop = crop_box(p, w, h, ccfg)
            if crop is None:
                continue
            x0, y0, x1, y1 = crop
            size = resized_size(x1 - x0, y1 - y0, ccfg["resize_long_side_px"])
            interp = cv2.INTER_AREA if size[0] < x1 - x0 else cv2.INTER_LINEAR
            img = cv2.resize(rgb[y0:y1, x0:x1], size, interpolation=interp)
            out += crop_detections(self._recognize(img), crop, p, w, h, timestamp, self.mapping, frame_id)
        return out

    def close(self) -> None:
        self._rec.close()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()


assert set(_RANK) == set(GESTURES)
