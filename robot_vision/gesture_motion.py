"""v4 moving-gesture reader (docs/gesture_reader_v4.md): POINT / WAIT / STOP / NONE from a time window of one person's
body keypoints (YOLO11s-pose, COCO 17) and hand landmarks (MediaPipe, through gesture_adapter_v4.py).

Pure functions and small classes, no models and no I/O (unit-tested on synthetic keypoint sequences). All thresholds
come from configs/v4/gesture_reader.json (initial values, to be set on development data).

Pipeline per person (one PersonBuffer per tracked person):
  Sample (one frame: keypoints, linked hands, camera intrinsics, pan, robot pose)
    -> arm_frame per arm: raised? angle, length, elbow, wrist in torso units
    -> frame_flags per arm: point_ok / wait_ok / stop_ok (all cues of the class pass in this frame)
    -> read_window over the last window_s: moving or still (wrist path), the held pose (trailing still stretch of at
       least hold_min_s) for POINT and WAIT, the last stop_window_s for STOP -> Reading.

Moving vs still: a wrist path over the window of at least motion_path_min torso lengths is a moving gesture; speeds are
in torso lengths per second so distance and zoom do not matter. POINT and WAIT are read only from a held pose (the
swing is not read); a moving arm with no hold yet reads NONE ("moving, no hold yet"). STOP is read on a short window and
overrides the other classes.

POINT direction (point_estimate): the arm direction is rebuilt as a 3D vector in the camera frame from the pixel rays of
the shoulder and the wrist (frame fx, fy, cx, cy) and the arm's full length in shoulder widths: the unknown depth of the
wrist along its ray is the root of |Zw * ray_wrist - ray_shoulder| = arm length (units of the shoulder depth). Two roots
(arm pointing away from or toward the camera) unless the arm is nearly in the image plane (inplane_ratio_min), then one.
The camera azimuth is turned into a world yaw with the camera yaw (robot yaw - pan_deg; pan > 0 = left) and the
candidates are returned as world yaws; the controller chooses between them with the roadmap (the branch the robot arrived
from is never an answer). The camera is assumed level (tilt_deg is not used). MediaPipe hand WORLD landmarks give an
independent finger direction used as a cross-check (never changes the candidates).

Conventions: pixels x right, y down; camera frame x right, y down, z forward (away from the camera); Unity yaw 0 = +Z,
+ = clockwise from above (hri_control.py); angles in degrees; "up" angles are measured from straight up in the image,
+ = toward the image right.
"""

from __future__ import annotations

import json
import math
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
DEFAULT_CONFIG = "configs/v4/gesture_reader.json"

NOSE, L_EYE, R_EYE = 0, 1, 2
L_SHOULDER, R_SHOULDER, L_ELBOW, R_ELBOW, L_WRIST, R_WRIST, L_HIP, R_HIP = 5, 6, 7, 8, 9, 10, 11, 12
# the person's own side -> (shoulder, elbow, wrist) keypoints
ARMS = {"right": (R_SHOULDER, R_ELBOW, R_WRIST), "left": (L_SHOULDER, L_ELBOW, L_WRIST)}
FINGERS = {"index": (5, 8), "middle": (9, 12), "ring": (13, 16), "pinky": (17, 20)}   # (MCP, tip) of MediaPipe's 21 landmarks
WRIST_LM, INDEX_MCP, INDEX_TIP, MIDDLE_MCP, PINKY_TIP = 0, 5, 8, 9, 20
COMMANDS = ("POINT", "WAIT", "STOP")


def load_config(path: str | Path = DEFAULT_CONFIG) -> dict:
    p = Path(path)
    return json.loads((p if p.is_absolute() else HERE / p).read_text(encoding="utf-8"))


# ---------------------------------------------------------------- small geometry

def wrap(a: float) -> float:
    return (a + 180.0) % 360.0 - 180.0


def circular_mean(angles_deg) -> float:
    a = [math.radians(x) for x in angles_deg]
    return math.degrees(math.atan2(sum(math.sin(x) for x in a), sum(math.cos(x) for x in a)))


def angle_from_up(dx: float, dy: float) -> float:
    """Direction (dx, dy) in the image (y down) measured from straight up, + = toward the image right."""
    return math.degrees(math.atan2(dx, -dy))


def joint_angle(a, b, c) -> float:
    """Angle at b between b->a and b->c in degrees (180 = straight)."""
    v1, v2 = np.subtract(a, b, dtype=float), np.subtract(c, b, dtype=float)
    n = np.linalg.norm(v1) * np.linalg.norm(v2)
    return 0.0 if n < 1e-9 else math.degrees(math.acos(float(np.clip(np.dot(v1, v2) / n, -1.0, 1.0))))


# ---------------------------------------------------------------- samples, hands, buffer

@dataclass
class Sample:
    """One pan-tilt frame of one person. hands: the hand linked to each arm ('left'/'right', None if none), objects
    with category, score, landmarks_px (21, 2), world_xyz (21, 3) or None, box (x1, y1, x2, y2) in pixels."""
    t: float
    kp: np.ndarray                       # (17, 2) pixels
    conf: np.ndarray                     # (17,)
    hands: dict = field(default_factory=dict)
    fx: float = 458.99
    fy: float = 458.99
    cx: float = 365.0
    cy: float = 265.0
    width: int = 730
    height: int = 530
    pan_deg: float = 0.0
    robot_yaw_deg: float = 0.0
    box: tuple | None = None


def torso_frame(kp, conf, thr: float):
    """(torso length px, shoulder midpoint, hip midpoint, shoulder width px) or None when a shoulder or hip is missing."""
    if min(conf[L_SHOULDER], conf[R_SHOULDER], conf[L_HIP], conf[R_HIP]) < thr:
        return None
    sm = (np.asarray(kp[L_SHOULDER], float) + np.asarray(kp[R_SHOULDER], float)) / 2.0
    hm = (np.asarray(kp[L_HIP], float) + np.asarray(kp[R_HIP], float)) / 2.0
    torso = float(np.linalg.norm(hm - sm))
    width = float(np.linalg.norm(np.asarray(kp[L_SHOULDER], float) - np.asarray(kp[R_SHOULDER], float)))
    if torso < 1e-6 or width < 1e-6:
        return None
    return torso, sm, hm, width


def link_hands(kp, conf, hands, cfg: dict) -> dict:
    """Link each hand to an arm by its wrist: the hand whose wrist landmark is nearest the YOLO wrist keypoint of that
    arm, within hand_link_max_shoulder_widths shoulder widths. A hand is linked to one arm only (the nearer one); a
    hand equally near both arms, or beyond the limit, is not linked. Returns {'left': hand|None, 'right': hand|None}."""
    out = {"left": None, "right": None}
    k, thr = cfg["keypoints"], cfg["keypoints"]["body_kp_conf_min"]
    if min(conf[L_SHOULDER], conf[R_SHOULDER]) < thr:
        return out
    width = float(np.linalg.norm(np.asarray(kp[L_SHOULDER], float) - np.asarray(kp[R_SHOULDER], float)))
    limit = k["hand_link_max_shoulder_widths"] * width
    best = {}
    for side, (_, _, w) in ARMS.items():
        if conf[w] < thr:
            continue
        for i, h in enumerate(hands):
            d = float(np.linalg.norm(np.asarray(h.landmarks_px[WRIST_LM], float) - np.asarray(kp[w], float)))
            if d <= limit:
                best.setdefault(i, []).append((d, side))
    for i, cands in best.items():
        cands.sort()
        if len(cands) == 2 and abs(cands[0][0] - cands[1][0]) < 1e-9:
            continue
        side = cands[0][1]
        cur = out[side]
        if cur is None or cands[0][0] < cur[0]:
            out[side] = (cands[0][0], hands[i])
    return {s: (v[1] if v else None) for s, v in out.items()}


class PersonBuffer:
    """Time buffer of one tracked person's samples; keeps the last keep_s seconds."""

    def __init__(self, keep_s: float):
        self.keep_s = float(keep_s)
        self._q: deque[Sample] = deque()

    def add(self, s: Sample) -> None:
        self._q.append(s)
        while self._q and self._q[0].t < s.t - self.keep_s - 1e-9:
            self._q.popleft()

    def window(self, t_now: float, window_s: float) -> list[Sample]:
        return [s for s in self._q if t_now - window_s - 1e-9 <= s.t <= t_now + 1e-9]

    def __len__(self) -> int:
        return len(self._q)

    @property
    def last_t(self) -> float | None:
        return self._q[-1].t if self._q else None


# ---------------------------------------------------------------- per-frame arm and hand features

@dataclass
class ArmFrame:
    side: str
    valid: bool
    raised: bool = False
    theta_deg: float | None = None          # arm direction in the image, from straight up (circular mean of S->W and E->W)
    disagreement_deg: float | None = None
    length_ratio: float | None = None       # |shoulder -> wrist| / shoulder width
    elbow_deg: float | None = None
    forearm_up_deg: float | None = None     # elbow -> wrist from straight up
    wrist_rel: tuple | None = None          # wrist relative to the shoulder midpoint, in torso lengths
    wrist_above_hip: float | None = None    # torso lengths
    wrist_above_shoulder: float | None = None
    torso_px: float | None = None
    reason: str = ""


def arm_frame(s: Sample, side: str, cfg: dict) -> ArmFrame:
    k = cfg["keypoints"]
    thr = k["body_kp_conf_min"]
    tf = torso_frame(s.kp, s.conf, thr)
    sh, el, wr = ARMS[side]
    if tf is None:
        return ArmFrame(side, False, reason="torso keypoints missing")
    if min(s.conf[sh], s.conf[el], s.conf[wr]) < thr:
        return ArmFrame(side, False, reason="arm keypoints below confidence")
    torso, sm, hm, width = tf
    S, E, W = (np.asarray(s.kp[i], float) for i in (sh, el, wr))
    a_sw = angle_from_up(*(W - S))
    a_ew = angle_from_up(*(W - E))
    dis = abs(wrap(a_sw - a_ew))
    above_hip = float((hm[1] - W[1]) / torso)
    above_sh = float((S[1] - W[1]) / torso)
    raised = abs(a_sw) <= k["raised_max_abs_deg"] and above_hip >= k["arm_raised_margin"]
    return ArmFrame(side, True, raised, circular_mean([a_sw, a_ew]), dis, float(np.linalg.norm(W - S) / width),
                    joint_angle(S, E, W), angle_from_up(*(W - E)), tuple(((W - sm) / torso).tolist()), above_hip,
                    above_sh, torso)


def hand_cues(hand, cfg: dict) -> dict:
    """Finger states and shape cues of one hand from its 21 pixel landmarks."""
    h = cfg["hand"]
    lm = np.asarray(hand.landmarks_px, float)
    wr = lm[WRIST_LM]
    ratios = {}
    for name, (mcp, tip) in FINGERS.items():
        base = float(np.linalg.norm(lm[mcp] - wr))
        ratios[name] = float(np.linalg.norm(lm[tip] - wr) / base) if base > 1e-9 else 0.0
    ext = {n: r >= h["finger_extended_ratio"] for n, r in ratios.items()}
    curled = {n: r <= h["finger_curled_ratio"] for n, r in ratios.items()}
    v1, v2 = lm[INDEX_TIP] - wr, lm[PINKY_TIP] - wr
    n = float(np.linalg.norm(v1) * np.linalg.norm(v2))
    spread = math.degrees(math.acos(float(np.clip(np.dot(v1, v2) / n, -1.0, 1.0)))) if n > 1e-9 else 0.0
    d = lm[INDEX_TIP] - lm[INDEX_MCP]
    return {"ratios": ratios, "extended": ext, "curled": curled, "spread_deg": spread,
            "index_up_deg": angle_from_up(d[0], d[1]), "category": hand.category, "score": float(hand.score)}


def frame_flags(s: Sample, side: str, af: ArmFrame, cfg: dict) -> dict:
    """Does each class's full set of cues pass in this frame, for this arm? Keys point_ok, wait_ok, stop_ok (+ why)."""
    p, h = cfg["point"], cfg["hand"]
    out = {"point_ok": False, "wait_ok": False, "stop_ok": False, "why": ""}
    hand = s.hands.get(side)
    cues = hand_cues(hand, cfg) if hand is not None else None
    if cues is not None:
        fingers4 = all(cues["extended"].values())
        out["stop_ok"] = bool(cues["category"] == "Open_Palm" and cues["score"] >= h["stop_score_min"] and fingers4
                              and cues["spread_deg"] >= h["palm_spread_min_deg"])
    if not af.valid:
        out["why"] = af.reason
        return out
    if cues is not None:
        wait_hand = (cues["category"] == "Pointing_Up" and cues["score"] >= h["wait_score_min"]
                     and cues["extended"]["index"] and all(cues["curled"][n] for n in ("middle", "ring", "pinky"))
                     and abs(cues["index_up_deg"]) <= h["index_up_tol_deg"])
        out["wait_ok"] = bool(wait_hand and af.raised and af.wrist_above_shoulder >= h["wait_raise_margin"]
                              and abs(af.forearm_up_deg) <= h["wait_forearm_vertical_tol_deg"]
                              and af.elbow_deg <= h["wait_arm_extension_max_deg"])
    open_palm = cues is not None and cues["category"] == "Open_Palm" and cues["score"] >= h["stop_score_min"]
    out["point_ok"] = bool(af.raised and af.disagreement_deg <= p["segment_disagreement_max_deg"]
                           and af.length_ratio >= p["arm_length_min"] and af.elbow_deg >= p["point_arm_extension_min_deg"]
                           and not open_palm and arm_solutions(s, side, cfg) is not None)
    return out


# ---------------------------------------------------------------- POINT: out-of-plane geometry

def arm_solutions(s: Sample, side: str, cfg: dict) -> dict | None:
    """The pointing arm as a 3D direction in the camera frame, from pixel rays and the arm's full length.

    Rays r = ((u - cx) / fx, (v - cy) / fy, 1) of the shoulder and the wrist; shoulder depth taken as 1 (only ratios
    matter); the arm's full length k = arm_length_in_shoulder_widths x (the shoulder width in the same units); the
    wrist depth Zw solves |Zw r_w - r_s| = k: Zc +- sqrt(k^2 - l_c^2)/|r_w| (Zc the closest approach, l_c its distance).
    Both roots are returned, 'away' (larger Zw, pointing away from the camera) and 'toward': they are two physically
    possible arms behind the same pixels, and the foreshortening is too ill-conditioned near the image plane to
    discard either on the image alone (the roadmap does that in the controller). If no root is real (the arm looks
    longer than the model) or only one is in front of the camera, the wrist is taken at the root that exists or, if
    none, at the shoulder's depth (Zw = 1): one solution. Returns None when no solution has a ground direction
    (elevation within point_elevation_max_deg) or keypoints are missing. Else
    {'away': (az, elev) | None, 'toward': (az, elev) | None, 'two': bool, 'phi_deg', 'theta_deg'}: az = camera azimuth
    (atan2(x, z), + = right), elev = angle above horizontal, both in degrees; phi_deg = the smaller out-of-plane angle
    asin(|Zw - 1| / k) of the roots."""
    p, thr = cfg["point"], cfg["keypoints"]["body_kp_conf_min"]
    sh, el, wr = ARMS[side]
    if min(s.conf[L_SHOULDER], s.conf[R_SHOULDER], s.conf[wr]) < thr:
        return None

    def ray(xy):
        return np.array([(xy[0] - s.cx) / s.fx, (xy[1] - s.cy) / s.fy, 1.0])

    rs, rw = ray(s.kp[sh]), ray(s.kp[wr])
    wl, wrr = ray(s.kp[L_SHOULDER]), ray(s.kp[R_SHOULDER])
    k = p["arm_length_in_shoulder_widths"] * float(np.linalg.norm((wl - wrr)[:2]))
    if k < 1e-9:
        return None
    zc = float(np.dot(rw, rs) / np.dot(rw, rw))
    lc = float(np.linalg.norm(zc * rw - rs))
    if lc >= k:
        roots = [1.0]
    else:
        delta = math.sqrt(k * k - lc * lc) / float(np.linalg.norm(rw))
        roots = [z for z in (zc + delta, zc - delta) if z > 0]
        if not roots:
            roots = [1.0]
    phis = [math.degrees(math.asin(min(1.0, abs(z - 1.0) / k))) for z in roots]
    chosen = {"away": max(roots), "toward": min(roots)}
    out: dict = {"two": False, "phi_deg": min(phis)}
    ok_any = False
    for name, z in chosen.items():
        d = z * rw - rs
        horiz = math.hypot(d[0], d[2])
        elev = math.degrees(math.atan2(-d[1], horiz))
        if horiz < 1e-9 or abs(elev) > p["point_elevation_max_deg"]:
            out[name] = None
            continue
        out[name] = (math.degrees(math.atan2(d[0], d[2])), elev)
        ok_any = True
    if not ok_any:
        return None
    out["two"] = bool(len(roots) == 2 and out["away"] is not None and out["toward"] is not None)
    out["theta_deg"] = angle_from_up(*(np.asarray(s.kp[wr], float) - np.asarray(s.kp[sh], float)))
    return out


@dataclass
class PointEstimate:
    theta_deg: float                      # in-plane arm angle (from up, + right), mean over the hold
    phi_deg: float                        # out-of-plane angle of the arm, mean over the hold
    world_deg: dict                       # {'away': yaw | None, 'toward': yaw | None}, Unity yaw, mean over the hold
    rel_deg: dict                         # the same relative to the robot's forward axis at the last frame (+ = right)
    two_solutions: bool                   # the arm is out of the image plane: away and toward differ
    n_frames: int
    crosscheck: dict                      # hand world landmarks: {'available', 'prefers', 'diff_deg': {family: deg}, 'why'}

    def to_dict(self) -> dict:
        return {"theta_deg": _r(self.theta_deg), "phi_deg": _r(self.phi_deg), "world_deg": {k: _r(v) for k, v in self.world_deg.items()},
                "rel_deg": {k: _r(v) for k, v in self.rel_deg.items()}, "two_solutions": self.two_solutions,
                "n_frames": self.n_frames, "crosscheck": self.crosscheck}


def hand_world_azimuth(hand, cfg: dict) -> tuple[float | None, str]:
    """Camera azimuth (deg, + right) of the finger direction from the MediaPipe WORLD landmarks: index MCP -> tip when
    the index is extended, else the hand axis wrist -> middle MCP. (azimuth | None, which axis / why not)."""
    w = getattr(hand, "world_xyz", None)
    if w is None:
        return None, "no world landmarks"
    w = np.asarray(w, float)
    cues = hand_cues(hand, cfg)
    if cues["extended"]["index"]:
        v, axis = w[INDEX_TIP] - w[INDEX_MCP], "index"
    else:
        v, axis = w[MIDDLE_MCP] - w[WRIST_LM], "hand axis"
    z = v[2] if cfg["point"]["hand_world_z_away_positive"] else -v[2]
    horiz = math.hypot(v[0], z)
    if horiz < 1e-9 or abs(math.degrees(math.atan2(-v[1], horiz))) > cfg["point"]["point_elevation_max_deg"]:
        return None, f"{axis} direction vertical"
    return math.degrees(math.atan2(v[0], z)), axis


def point_estimate(samples: list[Sample], side: str, cfg: dict) -> PointEstimate | None:
    """POINT direction over the frames of a held pose; None when no frame has a ground direction."""
    fam = {"away": [], "toward": []}
    phis, thetas, two = [], [], 0
    last = None
    for s in samples:
        sol = arm_solutions(s, side, cfg)
        if sol is None:
            continue
        for name in fam:
            if sol[name] is not None:
                fam[name].append(wrap(s.robot_yaw_deg + sol[name][0] - s.pan_deg))
        phis.append(sol["phi_deg"])
        thetas.append(sol["theta_deg"])
        two += bool(sol["two"])
        last = (s, sol)
    if not phis:
        return None
    world = {n: (circular_mean(v) if v else None) for n, v in fam.items()}
    yaw_last = last[0].robot_yaw_deg
    rel = {n: (wrap(v - yaw_last) if v is not None else None) for n, v in world.items()}
    cc = {"available": False, "prefers": None, "diff_deg": {}, "why": "no hand linked"}
    hand = last[0].hands.get(side)
    if hand is not None:
        az_h, why = hand_world_azimuth(hand, cfg)
        cc["why"] = why
        if az_h is not None:
            cc["available"] = True
            diffs = {n: abs(wrap(last[1][n][0] - az_h)) for n in fam if last[1][n] is not None}
            cc["diff_deg"] = {n: _r(d) for n, d in diffs.items()}
            if last[1]["two"]:                            # with one solution there is nothing to choose between
                best = min(diffs, key=diffs.get)
                if diffs[best] <= cfg["point"]["hand_crosscheck_tol_deg"] and (
                        len(diffs) == 1 or abs(diffs["away"] - diffs["toward"]) > 1e-9):
                    cc["prefers"] = best
    return PointEstimate(circular_mean(thetas), float(np.mean(phis)), world, rel, two >= len(phis) / 2.0, len(phis), cc)


# ---------------------------------------------------------------- window reading

@dataclass
class Reading:
    command: str                          # POINT | WAIT | STOP | NONE | insufficient_history
    score: float
    why: str
    t: float
    arm: str | None = None
    frame_class: str = "NONE"             # the latest frame alone (STOP > WAIT > POINT > NONE)
    moving: bool = False
    raised: bool = False
    hold_s: float = 0.0
    valid_frames: int = 0
    n_frames: int = 0
    scores: dict = field(default_factory=dict)
    arms: dict = field(default_factory=dict)
    point: PointEstimate | None = None
    hand_box: tuple | None = None         # px, of the hand linked to the active (else the raised) arm in the latest frame
    arm_box: tuple | None = None          # px, shoulder + elbow + wrist of that arm
    frame_wh: tuple | None = None
    fov_deg: float | None = None

    def to_dict(self) -> dict:
        d = {"command": self.command, "score": _r(self.score), "why": self.why, "t": _r(self.t), "arm": self.arm,
             "frame_class": self.frame_class, "moving": self.moving, "raised": self.raised, "hold_s": _r(self.hold_s),
             "valid_frames": self.valid_frames, "n_frames": self.n_frames, "scores": {k: _r(v) for k, v in self.scores.items()},
             "arms": self.arms, "hand_box": self.hand_box, "arm_box": self.arm_box, "fov_deg": _r(self.fov_deg)}
        d["point"] = self.point.to_dict() if self.point is not None else None
        return d


def _r(x, n=3):
    return None if x is None else round(float(x), n)


def _share(flags: list[bool]) -> float:
    return sum(flags) / len(flags) if flags else 0.0


def _arm_window(samples: list[Sample], side: str, cfg: dict, t_now: float) -> dict:
    """Features of one arm over the window."""
    m, w = cfg["motion"], cfg["window"]
    rows = []
    for s in samples:
        af = arm_frame(s, side, cfg)
        if af.valid:
            rows.append((s, af, frame_flags(s, side, af, cfg)))
    need = math.ceil(w["min_valid_fraction"] * max(1, round(w["window_s"] * cfg["frame_hz"])) - 1e-9)
    info: dict = {"valid": len(rows), "enough": len(rows) >= need, "raised": False, "path": 0.0, "moving": False, "hold_s": 0.0, "hold": [],
                  "point_share": 0.0, "wait_share": 0.0, "stop_share": 0.0, "stop_n": 0, "push": None}
    # STOP does not need the arm keypoints: use every sample with a linked hand in the last stop_window_s
    stop_rows = [(s, frame_flags(s, side, af, cfg)) for s in samples if t_now - w["stop_window_s"] - 1e-9 <= s.t
                 for af in [arm_frame(s, side, cfg)] if s.hands.get(side) is not None]
    info["stop_n"] = len(stop_rows)
    info["stop_share"] = _share([f["stop_ok"] for _, f in stop_rows])
    boxes = [s.hands[side].box for s in samples if s.hands.get(side) is not None]     # the whole window
    if cfg["hand"]["stop_requires_push"] and len(boxes) >= 2:
        h0, h1 = boxes[0][3] - boxes[0][1], boxes[-1][3] - boxes[-1][1]
        info["push"] = (h1 / h0) if h0 > 1e-9 else None
    if not rows:
        return info
    info["raised"] = bool(rows[-1][1].raised)
    pts = [np.array(af.wrist_rel) for _, af, _ in rows]
    ts = [s.t for s, _, _ in rows]
    speeds = [float(np.linalg.norm(pts[i + 1] - pts[i]) / max(ts[i + 1] - ts[i], 1e-6)) for i in range(len(rows) - 1)]
    info["path"] = float(sum(np.linalg.norm(pts[i + 1] - pts[i]) for i in range(len(rows) - 1)))
    info["moving"] = info["path"] >= m["motion_path_min"]
    j = len(rows) - 1                                   # trailing still stretch
    while j > 0 and speeds[j - 1] <= m["still_speed_max"]:
        j -= 1
    hold = rows[j:]
    info["hold_s"] = float(ts[-1] - ts[j])
    if info["hold_s"] >= w["hold_min_s"] - 1e-9 and len(hold) >= 2:
        info["hold"] = hold
        info["point_share"] = _share([f["point_ok"] for _, _, f in hold])
        info["wait_share"] = _share([f["wait_ok"] for _, _, f in hold])
    return info


def read_window(samples: list[Sample], cfg: dict, t_now: float | None = None) -> Reading:
    """Classify the last window_s of one person's samples (already restricted to the window by PersonBuffer.window)."""
    w, d = cfg["window"], cfg["decision"]
    t_now = t_now if t_now is not None else (samples[-1].t if samples else 0.0)
    n_exp = max(1, round(w["window_s"] * cfg["frame_hz"]))
    last = samples[-1] if samples else None
    r = Reading("NONE", 0.0, "", t_now, n_frames=len(samples))
    if last is None:
        r.command, r.why = "insufficient_history", "no samples"
        return r
    arms = {side: _arm_window(samples, side, cfg, t_now) for side in ARMS}
    valid_frames = sum(1 for s in samples if any(arm_frame(s, side, cfg).valid for side in ARMS))
    r.valid_frames, r.frame_wh = valid_frames, (last.width, last.height)
    r.fov_deg = math.degrees(2.0 * math.atan((last.height / 2.0) / last.fy))
    r.arms = {side: {k: (_r(v) if isinstance(v, float) else v) for k, v in a.items() if k not in ("hold",)} for side, a in arms.items()}
    r.moving = any(a["moving"] and a["raised"] for a in arms.values())
    r.raised = any(a["raised"] for a in arms.values())
    # latest-frame class
    flags = [frame_flags(last, side, arm_frame(last, side, cfg), cfg) for side in ARMS]
    r.frame_class = next((name for name, key in (("STOP", "stop_ok"), ("WAIT", "wait_ok"), ("POINT", "point_ok"))
                          if any(f[key] for f in flags)), "NONE")
    need = math.ceil(w["min_valid_fraction"] * n_exp - 1e-9)
    stop_possible = any(a["stop_n"] >= 2 for a in arms.values())
    if not any(a["enough"] for a in arms.values()) and not stop_possible:
        r.command, r.why = "insufficient_history", f"fewer than {need} valid frames of {n_exp} expected"
        return r
    share_min, margin_min = d["class_share_min"], d["class_margin_min"]
    # STOP first: it overrides the other classes
    stops = []
    for side, a in arms.items():
        push_ok = (not cfg["hand"]["stop_requires_push"]) or (a["push"] is not None and a["push"] >= cfg["hand"]["push_scale_ratio_min"])
        if a["stop_n"] >= 2 and a["stop_share"] >= share_min and push_ok:
            stops.append((a["stop_share"], side))
    if stops:
        score, side = max(stops)
        _fill_boxes(r, samples, side)
        r.command, r.score, r.arm, r.why = "STOP", score, side, "open palm"
        r.scores = {"STOP": score}
        return r
    cands = []
    for side, a in arms.items():
        if not a["hold"] or not a["enough"]:
            continue
        ps, ws = a["point_share"], a["wait_share"]
        best, other = (("POINT", ps), ("WAIT", ws)) if ps >= ws else (("WAIT", ws), ("POINT", ps))
        if best[1] >= share_min and best[1] - other[1] >= margin_min:
            cands.append((best[1], best[0], side))
    r.scores = {"POINT": max((a["point_share"] for a in arms.values()), default=0.0),
                "WAIT": max((a["wait_share"] for a in arms.values()), default=0.0),
                "STOP": max((a["stop_share"] for a in arms.values()), default=0.0)}
    if not cands:
        raised = [s for s, a in arms.items() if a["raised"]]
        short = [s for s in raised if not arms[s]["enough"]]
        if short:
            r.command, r.why = "insufficient_history", f"raised {short[0]} arm has fewer than {need} valid frames"
            return r
        if not raised:
            r.why = "no raised arm"
        elif any(a["moving"] and not a["hold"] for a in arms.values()):
            r.why = "moving, no hold yet"
            _fill_boxes(r, samples, raised[0])
        elif any(a["hold"] for a in arms.values()):
            r.why = "cues not met or classes ambiguous"
            _fill_boxes(r, samples, raised[0])
        else:
            r.why = "no hold"
        return r
    if len({c[1] for c in cands}) > 1:
        r.why = "conflicting arms"
        return r
    score, cmd, side = max(cands)
    if len(cands) == 2 and abs(cands[0][0] - cands[1][0]) < 1e-9 and cmd == "POINT":
        r.why = "both arms point equally"
        return r
    _fill_boxes(r, samples, side)
    r.command, r.score, r.arm, r.why, r.hold_s = cmd, score, side, "ok", arms[side]["hold_s"]
    if cmd == "POINT":
        hold_samples = [s for s, _, _ in arms[side]["hold"]]
        r.point = point_estimate(hold_samples, side, cfg)
        if r.point is None:
            r.command, r.score, r.why = "NONE", 0.0, "pointing arm has no ground direction"
    return r


def _fill_boxes(r: Reading, samples: list[Sample], side: str) -> None:
    last = samples[-1]
    h = last.hands.get(side)
    r.hand_box = tuple(round(float(x), 1) for x in h.box) if h is not None else None
    sh, el, wr = ARMS[side]
    pts = np.array([last.kp[i] for i in (sh, el, wr)], float)
    r.arm_box = (round(float(pts[:, 0].min()), 1), round(float(pts[:, 1].min()), 1), round(float(pts[:, 0].max()), 1),
                 round(float(pts[:, 1].max()), 1))
