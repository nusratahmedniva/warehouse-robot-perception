"""Depth decoding and pixel back-projection for THUD synthetic (Unity) captures.

The encoding parameters are NOT assumed here: they come from configs/depth_thud_synthetic.json,
which records the values established by validate_depth.py and the evidence for them.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
from PIL import Image

RAW_MAX = 65535


def load_depth_config(path: Path | None = None) -> dict:
    path = path or Path(__file__).parent / "configs" / "depth_thud_synthetic.json"
    return json.loads(Path(path).read_text(encoding="utf-8"))


def load_raw_depth(path: str | Path) -> np.ndarray:
    with Image.open(path) as im:
        if im.mode not in ("I;16", "I;16B", "I"):
            raise ValueError(f"Expected a 16-bit depth PNG, got mode {im.mode}: {path}")
        raw = np.array(im)
    if raw.dtype != np.uint16:
        raw = raw.astype(np.uint16)
    return raw


def decode_depth(raw: np.ndarray, far_m: float) -> tuple[np.ndarray, np.ndarray]:
    """Linear encoding: depth_m = raw / 65535 * far_m (planar Z, along the optical axis).

    Returns (depth_m, valid). Saturated pixels (raw == 65535) mean "at or beyond far_m" and are
    marked invalid with depth NaN, since their true distance is unknown.
    """
    depth = raw.astype(np.float64) * (far_m / RAW_MAX)
    valid = raw < RAW_MAX
    depth[~valid] = np.nan
    return depth, valid


def pixel_intrinsics(width: int, height: int, vertical_fov_deg: float) -> dict:
    """Square-pixel pinhole intrinsics from a vertical field of view, principal point at the image centre."""
    f = (height / 2) / math.tan(math.radians(vertical_fov_deg) / 2)
    return {"fx": f, "fy": f, "cx": width / 2, "cy": height / 2}


def backproject(u: np.ndarray, v: np.ndarray, z: np.ndarray, k: dict) -> np.ndarray:
    """Pixel indices (column u, row v) + planar depth Z -> camera-frame points.

    Unity camera convention: x right, y up, z forward. Pixel centres are at index + 0.5.
    """
    x = (u + 0.5 - k["cx"]) * z / k["fx"]
    y = -(v + 0.5 - k["cy"]) * z / k["fy"]
    return np.stack([x, y, z], axis=-1)
