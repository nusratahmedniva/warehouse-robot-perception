"""Gesture adapter: the teammate's MediaPipe gesture recognizer -> GestureEvent for Step 9.

The module itself (git submodule external/media_pipe_gesture, configs/gesture.json -> source) is not modified or
imported; the adapter uses the same model file and the same category mapping as her gesture_heuristics.py, in
IMAGE running mode on unmirrored frames.

Two modes (configs/gesture.json -> modes):
- full_frame:  her approach (baseline). The whole frame goes to the recognizer.
- person_crop: one call per tracked person on the upper part of the box plus a margin, resized so the longer side
               is resize_long_side_px.

Hands, in full-image pixels, then go through the same steps in both modes (configs/gesture.json -> assignment):
1. Duplicates: hands whose boxes overlap with IoU >= duplicate_hand_iou_threshold are one hand (overlapping crops
   see the same hand); the highest-scoring copy is kept and the others are recorded with it.
2. Owner, one per hand, among the candidates (persons whose crop region contains the wrist, plus the persons whose
   crop found the hand):
   a. depth: the candidate whose depth_m best matches the depth at the wrist, if the gap is <= depth_match_max_m
      and the next candidate's gap is larger by >= depth_margin_m (needs a depth image and person depths);
   b. otherwise the person whose box contains the wrist, if exactly one box does;
   c. otherwise track_id None (ambiguous / no_containing_box).

Every hand becomes a GestureDetection with its raw category, raw score, hand box and wrist in full-image pixels.
No confidence threshold is applied here: the decision threshold lives only in decision.json and is applied by
the decision's gesture filter. A frame without a hand (full_frame), or a person without an owned hand
(person_crop), gives one NONE detection.

MediaPipe is imported only inside GestureRecognizerAdapter, so every other module (and the geometry, mapping and
assignment functions here) runs without it. No reference data is read: depth and person depths come from the
caller.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np

from decision import GESTURES, GestureEvent

HERE = Path(__file__).resolve().parent
DEFAULT_CONFIG = HERE / "configs" / "gesture.json"
MODES = ("full_frame", "person_crop")
WRIST = 0  # MediaPipe hand landmark index


@dataclass(frozen=True)
class PersonBox:
    """A tracked person's detection box in full-image pixels (x1, y1) top-left, (x2, y2) bottom-right. depth_m: the
    person's depth on the same scale as the depth image (THUD: Step 4 planar depth), or None if unknown."""
    track_id: int | str
    x1: float
    y1: float
    x2: float
    y2: float
    depth_m: float | None = None


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
    assignment: str                   # depth | wrist_in_single_box | ambiguous | no_containing_box
                                      # | no_hand | no_owned_hand
    crop_box_xyxy: tuple[int, int, int, int] | None = None
    wrist_depth_m: float | None = None
    candidates: tuple = ()
    duplicates: tuple = ()            # (source track, raw category, raw score) of each merged copy

    def as_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class ImageHand:
    """A hand in full-image pixels. source_track / crop: the person crop it was found in (None in full_frame)."""
    category: str
    score: float
    handedness: str | None
    box: tuple[float, float, float, float]
    wrist: tuple[float, float]
    source_track: int | str | None = None
    crop: tuple[int, int, int, int] | None = None


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


def to_image_hand(hand: RawHand, region: tuple[int, int, int, int], img_w: int, img_h: int,
                  source_track=None, crop=None) -> ImageHand:
    """RawHand -> ImageHand: hand box clipped to the image, wrist in full-image pixels."""
    pts = [to_image_xy(x, y, region) for x, y in hand.landmarks_xy]
    xs = [min(max(p[0], 0.0), float(img_w)) for p in pts]
    ys = [min(max(p[1], 0.0), float(img_h)) for p in pts]
    return ImageHand(hand.category, float(hand.score), hand.handedness, (min(xs), min(ys), max(xs), max(ys)),
                     pts[WRIST], source_track, crop)


def box_iou(a, b) -> float:
    iw = max(0.0, min(a[2], b[2]) - max(a[0], b[0]))
    ih = max(0.0, min(a[3], b[3]) - max(a[1], b[1]))
    inter = iw * ih
    union = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - inter
    return inter / union if union > 0 else 0.0


def contains(box, xy) -> bool:
    """Edges included."""
    return box[0] <= xy[0] <= box[2] and box[1] <= xy[1] <= box[3]


# ---------------------------------------------------------------- duplicates and ownership

def deduplicate(hands, iou_min: float) -> list[tuple[ImageHand, list[ImageHand]]]:
    """Greedy, highest score first: a hand whose box overlaps a kept hand with IoU >= iou_min is a copy of it.
    Returns (kept hand, its copies)."""
    groups: list[tuple[ImageHand, list[ImageHand]]] = []
    for h in sorted(hands, key=lambda h: -h.score):
        for kept, copies in groups:
            if box_iou(kept.box, h.box) >= iou_min:
                copies.append(h)
                break
        else:
            groups.append((h, []))
    return groups


def depth_at(depth, xy, half_window: int) -> float | None:
    """Median of the valid (finite, > 0) depths in a (2 * half_window + 1)^2 window at xy; None if none."""
    if depth is None:
        return None
    h, w = depth.shape[:2]
    c, r = int(round(xy[0])), int(round(xy[1]))
    if not (0 <= c < w and 0 <= r < h):
        return None
    win = depth[max(0, r - half_window):r + half_window + 1, max(0, c - half_window):c + half_window + 1]
    v = win[np.isfinite(win) & (win > 0)]
    return float(np.median(v)) if v.size else None


def assign_owner(wrist, wrist_depth: float | None, persons, candidate_ids, acfg: dict):
    """(track_id or None, assignment) for one hand; see the module docstring, step 2."""
    by_id = {p.track_id: p for p in persons}
    if wrist_depth is not None:
        gaps = sorted((abs(by_id[t].depth_m - wrist_depth), str(t), t) for t in candidate_ids
                      if t in by_id and by_id[t].depth_m is not None)
        if gaps and gaps[0][0] <= acfg["depth_match_max_m"] and (
                len(gaps) == 1 or gaps[1][0] - gaps[0][0] >= acfg["depth_margin_m"]):
            return gaps[0][2], "depth"
    hits = [p.track_id for p in persons if contains((p.x1, p.y1, p.x2, p.y2), wrist)]
    if len(hits) == 1:
        return hits[0], "wrist_in_single_box"
    return None, ("ambiguous" if hits else "no_containing_box")


def assign_track(wrist_xy, persons) -> tuple[int | str | None, str]:
    """Fallback only (no depth): the person whose box contains the wrist, if exactly one does."""
    return assign_owner(wrist_xy, None, persons, (), {})


def owned_detections(hands, img_w: int, img_h: int, persons, timestamp: float, cfg: dict, mode: str,
                     depth=None, frame_id=None) -> list[GestureDetection]:
    """Deduplicate, assign one owner per hand, and build the detections (hands only, no NONE records)."""
    acfg = cfg["assignment"]
    crops = {p.track_id: crop_box(p, img_w, img_h, cfg["modes"]["person_crop"]) for p in persons}
    out = []
    for kept, copies in deduplicate(hands, acfg["duplicate_hand_iou_threshold"]):
        cands = [p.track_id for p in persons if crops[p.track_id] and contains(crops[p.track_id], kept.wrist)]
        cands += [h.source_track for h in [kept] + copies if h.source_track is not None
                  and h.source_track not in cands]
        wd = depth_at(depth, kept.wrist, acfg["wrist_depth_half_window_px"])
        tid, how = assign_owner(kept.wrist, wd, persons, cands, acfg)
        out.append(GestureDetection(
            timestamp, frame_id, mode, tid, map_category(kept.category, cfg["mapping"]), kept.category, kept.score,
            kept.box, kept.wrist, kept.handedness, how, kept.crop, wd, tuple(cands),
            tuple((h.source_track, h.category, h.score) for h in copies)))
    return out


def full_frame_detections(hands, img_w: int, img_h: int, persons, timestamp: float, cfg: dict, depth=None,
                          frame_id: str | None = None) -> list[GestureDetection]:
    if not hands:
        return [GestureDetection(timestamp, frame_id, "full_frame", None, "NONE", None, None, None, None, None,
                                 "no_hand")]
    ih = [to_image_hand(h, (0, 0, img_w, img_h), img_w, img_h) for h in hands]
    return owned_detections(ih, img_w, img_h, persons, timestamp, cfg, "full_frame", depth, frame_id)


def person_crop_detections(hands_by_track: dict, img_w: int, img_h: int, persons, timestamp: float, cfg: dict,
                           depth=None, frame_id: str | None = None) -> list[GestureDetection]:
    """hands_by_track: track_id -> (crop, RawHand list in crop coordinates) for each person that was cropped.
    Each cropped person without an owned hand gets one NONE detection (no_hand: the crop found nothing;
    no_owned_hand: the hands found went to someone else or to nobody)."""
    ih = [to_image_hand(h, crop, img_w, img_h, tid, crop)
          for tid, (crop, hs) in hands_by_track.items() for h in hs]
    out = owned_detections(ih, img_w, img_h, persons, timestamp, cfg, "person_crop", depth, frame_id)
    owners = {d.track_id for d in out}
    for tid, (crop, hs) in hands_by_track.items():
        if tid not in owners:
            out.append(GestureDetection(timestamp, frame_id, "person_crop", tid, "NONE", None, None, None, None,
                                        None, "no_owned_hand" if hs else "no_hand", crop))
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
    never mirrored; depth (optional) is an (H, W) float array in metres, invalid pixels NaN or <= 0. Use as a
    context manager or call close(). The only place MediaPipe is imported."""

    def __init__(self, cfg: dict, mode: str):
        if mode not in MODES:
            raise ValueError(f"mode {mode!r} not in {MODES}")
        try:
            import mediapipe as mp
            from mediapipe.tasks import python as mp_python
            from mediapipe.tasks.python import vision
        except ImportError as e:
            raise ImportError("the gesture adapter needs mediapipe (pip install -r requirements.txt; no wheel "
                              "exists for Intel macOS); the rest of the pipeline runs without it") from e

        path = model_path(cfg)
        if not path.exists():
            raise FileNotFoundError(f"{path} not found: run 'git submodule update --init' in the repository root")
        if sha256_file(path) != cfg["model"]["sha256"]:
            raise ValueError(f"{path} does not match the sha256 in the gesture config")
        self.cfg, self.mode, self._mp = cfg, mode, mp
        rec = cfg["recognizer"]
        options = vision.GestureRecognizerOptions(
            base_options=mp_python.BaseOptions(model_asset_path=str(path)),
            running_mode=vision.RunningMode.IMAGE,
            num_hands=cfg["modes"][mode]["num_hands"],
            min_hand_detection_confidence=rec["min_hand_detection_confidence"],
            min_hand_presence_confidence=rec["min_hand_presence_confidence"])
        self._rec = vision.GestureRecognizer.create_from_options(options)
        self.delegate = options.base_options.delegate

    def runtime(self) -> dict:
        """Device of the recognizer, from the delegate it was created with (logging only). MediaPipe Tasks does not
        report the precision it computes in, so that is 'unknown', not a guess."""
        d = self.delegate
        name = getattr(d, "name", None)
        return {"device": "CPU" if d is None or name == "CPU" else str(name or d),
                "delegate": "not set (MediaPipe default: CPU)" if d is None else str(name or d),
                "precision": "unknown", "precision_note": "not exposed by MediaPipe Tasks",
                "read_from": "BaseOptions.delegate of the created recognizer"}

    def _recognize(self, rgb) -> list[RawHand]:
        img = self._mp.Image(image_format=self._mp.ImageFormat.SRGB, data=np.ascontiguousarray(rgb))
        return hands_from_result(self._rec.recognize(img))

    def detect(self, rgb, timestamp: float, persons=(), frame_id: str | None = None,
               depth=None) -> list[GestureDetection]:
        h, w = rgb.shape[:2]
        if self.mode == "full_frame":
            return full_frame_detections(self._recognize(rgb), w, h, persons, timestamp, self.cfg, depth, frame_id)
        import cv2
        ccfg = self.cfg["modes"]["person_crop"]
        by_track = {}
        for p in persons:
            crop = crop_box(p, w, h, ccfg)
            if crop is None:
                continue
            x0, y0, x1, y1 = crop
            size = resized_size(x1 - x0, y1 - y0, ccfg["resize_long_side_px"])
            interp = cv2.INTER_AREA if size[0] < x1 - x0 else cv2.INTER_LINEAR
            by_track[p.track_id] = (crop, self._recognize(cv2.resize(rgb[y0:y1, x0:x1], size, interpolation=interp)))
        return person_crop_detections(by_track, w, h, persons, timestamp, self.cfg, depth, frame_id)

    def close(self) -> None:
        self._rec.close()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()


assert set(_RANK) == set(GESTURES)
