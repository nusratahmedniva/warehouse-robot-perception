"""v4 extension of the gesture adapter: the 21 hand landmarks (image and world) per person crop.

gesture_adapter.py (v3, unchanged) reduces each hand to its category, score, box and wrist and drops the landmarks.
The v4 reader (gesture_motion.py) needs the landmarks (finger extension, index direction, palm spread, hand box) and
the MediaPipe hand WORLD landmarks (metres, hand-centred, image axes) as a cross-check on the finger direction. They
are in the MediaPipe result (GestureRecognizerResult.hand_landmarks / hand_world_landmarks), so nothing has to change in
the MediaPipe gesture module or in gesture_adapter.py: this module subclasses the adapter, reuses its model check,
crop geometry and conventions, and only changes what is kept from the result.

Mode person_crop only: one recognizer call per tracked person on the upper part of the box plus a margin (the same
crop as v3). Hands come back in full-image pixels, per person, with no owner decision: the reader links each hand to
an arm by its wrist (gesture_motion.link_hands). No score threshold is applied here.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

import gesture_adapter as ga


@dataclass(frozen=True)
class RawHandV4:
    """A hand in the coordinates of the image it was found in: landmarks normalised to [0, 1], world landmarks in metres."""
    category: str
    score: float
    handedness: str | None
    landmarks_xy: tuple          # 21 x (x, y) normalised
    world_xyz: tuple | None      # 21 x (x, y, z) metres, or None when the result carries none


@dataclass(frozen=True)
class HandV4:
    """A hand of one person in full-image pixels."""
    track_id: int | str
    category: str
    score: float
    handedness: str | None
    landmarks_px: np.ndarray     # (21, 2)
    world_xyz: np.ndarray | None  # (21, 3)
    box: tuple                   # (x1, y1, x2, y2) of the landmarks, clipped to the image
    wrist: tuple


def hands_from_result_v4(result) -> list[RawHandV4]:
    """GestureRecognizerResult -> RawHandV4 list (top category per hand, as in the v3 adapter)."""
    out = []
    world = getattr(result, "hand_world_landmarks", None) or []
    for i, cats in enumerate(result.gestures):
        if not cats:
            continue
        hd = result.handedness[i][0].category_name if i < len(result.handedness) and result.handedness[i] else None
        lms = tuple((lm.x, lm.y) for lm in result.hand_landmarks[i])
        w = tuple((lm.x, lm.y, lm.z) for lm in world[i]) if i < len(world) and world[i] else None
        out.append(RawHandV4(cats[0].category_name, float(cats[0].score), hd, lms, w))
    return out


def to_hand_v4(raw: RawHandV4, region: tuple, img_w: int, img_h: int, track_id) -> HandV4:
    """Crop coordinates -> full-image pixels (ga.to_image_xy); the box is clipped to the image as in v3."""
    pts = np.array([ga.to_image_xy(x, y, region) for x, y in raw.landmarks_xy], dtype=float)
    box = (float(np.clip(pts[:, 0].min(), 0, img_w)), float(np.clip(pts[:, 1].min(), 0, img_h)),
           float(np.clip(pts[:, 0].max(), 0, img_w)), float(np.clip(pts[:, 1].max(), 0, img_h)))
    world = np.array(raw.world_xyz, dtype=float) if raw.world_xyz is not None else None
    return HandV4(track_id, raw.category, raw.score, raw.handedness, pts, world, box, (float(pts[0, 0]), float(pts[0, 1])))


class V4RecognizerAdapter(ga.GestureRecognizerAdapter):
    """The v3 recognizer wrapper (same model file, same options) that keeps the landmarks."""

    def __init__(self, cfg: dict):
        super().__init__(cfg, "person_crop")

    def _recognize_v4(self, rgb) -> list[RawHandV4]:
        img = self._mp.Image(image_format=self._mp.ImageFormat.SRGB, data=np.ascontiguousarray(rgb))
        return hands_from_result_v4(self._rec.recognize(img))

    def detect_hands(self, rgb, persons) -> dict:
        """track_id -> [HandV4] for every person with a valid crop (a person with no hand maps to [])."""
        import cv2
        h, w = rgb.shape[:2]
        ccfg = self.cfg["modes"]["person_crop"]
        out = {}
        for p in persons:
            crop = ga.crop_box(p, w, h, ccfg)
            if crop is None:
                continue
            x0, y0, x1, y1 = crop
            size = ga.resized_size(x1 - x0, y1 - y0, ccfg["resize_long_side_px"])
            interp = cv2.INTER_AREA if size[0] < x1 - x0 else cv2.INTER_LINEAR
            raws = self._recognize_v4(cv2.resize(rgb[y0:y1, x0:x1], size, interpolation=interp))
            out[p.track_id] = [to_hand_v4(r, crop, w, h, p.track_id) for r in raws]
        return out
