"""Synthetic people for the v4 reader tests (not a test module): a skeleton in the camera frame projected through the
real pan-tilt intrinsics (730 x 530, fx = fy = 458.99), and a MediaPipe-like hand. Body model (metres): shoulder width
0.40, torso 0.50, upper arm 0.30, forearm 0.26, so the arm is 1.4 shoulder widths long, the value in
configs/v4/gesture_reader.json. Camera frame: x right, y down, z forward (away from the camera)."""

import math
from types import SimpleNamespace

import numpy as np

import gesture_motion as gm

FX = FY = 458.99
CX, CY = 365.0, 265.0
WIDTH, HEIGHT = 730, 530
UPPER, FORE, SW, TORSO = 0.30, 0.26, 0.40, 0.50
DOWN = (0.0, 1.0, 0.0)


def unit(v):
    v = np.asarray(v, float)
    return v / np.linalg.norm(v)


def project(p):
    return np.array([FX * p[0] / p[2] + CX, FY * p[1] / p[2] + CY])


def direction(az_deg, elev_deg=0.0):
    """Unit arm direction in the camera frame from a camera azimuth (atan2(x, z)) and an elevation above horizontal."""
    a, e = math.radians(az_deg), math.radians(elev_deg)
    return np.array([math.cos(e) * math.sin(a), -math.sin(e), math.cos(e) * math.cos(a)])


def body(x0=0.0, z0=2.0, y0=-0.2, left=DOWN, right=DOWN, left_fore=None, right_fore=None):
    """(kp (17, 2) px, conf (17,)) of a person facing the camera at (x0, y0, z0) (shoulder-midpoint). left / right are the
    person's own arms (the person's left arm is on the image right); a second direction bends the elbow."""
    pts = np.tile([x0, y0 + TORSO, z0], (17, 1)).astype(float)      # unused keypoints sit at the hips' height
    pts[gm.NOSE] = (x0, y0 - 0.25, z0)
    pts[gm.L_EYE] = (x0 + 0.03, y0 - 0.28, z0)
    pts[gm.R_EYE] = (x0 - 0.03, y0 - 0.28, z0)
    pts[3] = (x0 + 0.08, y0 - 0.25, z0)
    pts[4] = (x0 - 0.08, y0 - 0.25, z0)
    pts[gm.L_SHOULDER] = (x0 + SW / 2, y0, z0)
    pts[gm.R_SHOULDER] = (x0 - SW / 2, y0, z0)
    pts[gm.L_HIP] = (x0 + 0.1, y0 + TORSO, z0)
    pts[gm.R_HIP] = (x0 - 0.1, y0 + TORSO, z0)
    for side, d1, d2 in (("left", left, left_fore), ("right", right, right_fore)):
        sh, el, wr = gm.ARMS[side]
        u1 = unit(d1)
        u2 = unit(d2 if d2 is not None else d1)
        pts[el] = pts[sh] + UPPER * u1
        pts[wr] = pts[el] + FORE * u2
    kp = np.array([project(p) for p in pts])
    return kp, np.ones(17)


def hand(wrist_px, axis=(0.0, -1.0), z=2.0, extended=("index", "middle", "ring", "pinky"), fan_deg=18.0,
         category="Open_Palm", score=0.9, world_dir=None):
    """A MediaPipe-like hand: landmarks_px (21, 2), box, optional world landmarks whose index MCP -> tip is world_dir."""
    scale = FX / z
    ax = unit((axis[0], axis[1], 0.0))[:2]
    perp = np.array([-ax[1], ax[0]])
    wr = np.asarray(wrist_px, float)
    lat = {"index": -0.02, "middle": -0.007, "ring": 0.007, "pinky": 0.02}
    fan = {"index": -fan_deg, "middle": -fan_deg / 3, "ring": fan_deg / 3, "pinky": fan_deg}
    lm = np.zeros((21, 2))
    lm[0] = wr
    for i in (1, 2, 3, 4):
        lm[i] = wr + (ax * 0.03 * i + perp * -0.03) * scale
    for name, (mcp, tip) in gm.FINGERS.items():
        mcp_p = wr + (ax * 0.095 + perp * lat[name]) * scale
        ext = 0.08 if name in extended else 0.01
        a = math.radians(fan[name])
        d = np.array([math.cos(a) * ax[0] - math.sin(a) * ax[1], math.sin(a) * ax[0] + math.cos(a) * ax[1]])
        lm[mcp] = mcp_p
        lm[mcp + 1], lm[mcp + 2] = mcp_p + d * ext * 0.4 * scale, mcp_p + d * ext * 0.7 * scale
        lm[tip] = wr + d * (0.095 + ext) * scale
    world = None
    if world_dir is not None:
        world = np.zeros((21, 3))
        world[0] = -0.09 * unit(world_dir)
        world[gm.INDEX_TIP] = 0.08 * unit(world_dir)
        world[gm.MIDDLE_MCP] = 0.0
    box = (float(lm[:, 0].min()), float(lm[:, 1].min()), float(lm[:, 0].max()), float(lm[:, 1].max()))
    return SimpleNamespace(category=category, score=score, handedness=None, landmarks_px=lm, world_xyz=world, box=box,
                           wrist=tuple(wr))


def sample(t, kp, conf, hands=None, pan_deg=0.0, robot_yaw_deg=0.0, noise_px=0.0, rng=None):
    if noise_px:
        kp = kp + rng.normal(0.0, noise_px, kp.shape)
    return gm.Sample(t, kp, conf, hands or {}, FX, FY, CX, CY, WIDTH, HEIGHT, pan_deg, robot_yaw_deg)


def arm_sequence(builder, n, dt=0.1, t0=0.0, **kw):
    """n samples; builder(i) -> (kp, conf, hands)."""
    out = []
    for i in range(n):
        kp, conf, hands = builder(i)
        out.append(sample(t0 + i * dt, kp, conf, hands, **kw))
    return out
