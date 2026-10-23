"""v4 commander rule (docs/project_flow_v4.md steps 4 and 7): among the people the pan-tilt camera sees, who is giving
the command? Pure functions, no models, no I/O (tests on synthetic readings); thresholds in configs/v4/commander.json.

A person is a candidate only if they FACE the robot (both eyes and the nose visible, shoulder width at least
facing_shoulder_ratio_min of the torso length) and have a RAISED arm: the hand is the YOLO wrist of that arm (linked to
the body because it is the same pose), with the MediaPipe hand attached when gesture_motion linked one. Among the
candidates the commander is the one whose raised hand is MOVING (gesture_motion.Reading.moving); a person who is
holding a recognised command (POINT / WAIT / STOP) counts too, so the commander does not drop out when the swing ends.
A person whose gesture started BEFORE "Which direction?" was shown is not eligible (the caller passes `ineligible`);
only a gesture that starts after the question counts.
Rules, in order:
  1. nobody facing with a raised hand -> no commander (reason says why each person was left out);
  2. the previously chosen person, if still a candidate, is kept (the dialog watches the same person);
  3. exactly one moving candidate -> them; several -> the one whose wrist travelled at least motion_margin further than
     the next, else a tie -> no commander; no moving candidate -> the holders by the same rule on their scores;
  4. no candidate or a tie -> NONE (never a guess).
Every call returns a Choice with the reasons per person, so the evaluation can score it against truth.jsonl.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

import gesture_motion as gm

HERE = Path(__file__).resolve().parent
DEFAULT_CONFIG = "configs/v4/commander.json"


def load_config(path: str | Path = DEFAULT_CONFIG) -> dict:
    p = Path(path)
    return json.loads((p if p.is_absolute() else HERE / p).read_text(encoding="utf-8"))


def facing_check(s: gm.Sample, ccfg: dict, kp_conf_min: float) -> tuple[bool, str]:
    """Is this person facing the camera? Both eyes and the nose visible and the shoulders wide enough."""
    if min(s.conf[gm.NOSE], s.conf[gm.L_EYE], s.conf[gm.R_EYE]) < kp_conf_min:
        return False, "face keypoints not visible (turned away)"
    tf = gm.torso_frame(s.kp, s.conf, kp_conf_min)
    if tf is None:
        return False, "torso keypoints missing"
    torso, _, _, width = tf
    ratio = width / torso
    if ratio < ccfg["facing_shoulder_ratio_min"]:
        return False, f"shoulders narrow ({ratio:.2f} of the torso): turned sideways"
    return True, "facing"


def box_bearing_deg(box, s: gm.Sample) -> float:
    """Bearing of a box centre relative to the robot's forward axis (+ = right): camera azimuth minus the pan."""
    u = 0.5 * (box[0] + box[2])
    return math.degrees(math.atan((u - s.cx) / s.fx)) - s.pan_deg


def body_bearing_deg(s: gm.Sample, kp_conf_min: float) -> float:
    """Bearing of the person's body: the shoulder midpoint when both shoulders are seen (an outstretched arm widens the
    person's box and would pull its centre sideways), else the centre of the person box."""
    if min(s.conf[gm.L_SHOULDER], s.conf[gm.R_SHOULDER]) >= kp_conf_min:
        u = 0.5 * (float(s.kp[gm.L_SHOULDER][0]) + float(s.kp[gm.R_SHOULDER][0]))
        return math.degrees(math.atan((u - s.cx) / s.fx)) - s.pan_deg
    return box_bearing_deg(s.box, s)


@dataclass
class PersonReading:
    """What the pan-tilt camera knows about one tracked person at one moment."""
    track_id: int
    bearing_deg: float
    facing: bool
    facing_why: str
    reading: gm.Reading
    box: tuple | None = None
    distance_m: float | None = None

    def raised_path(self) -> float:
        """Wrist path (torso lengths) of the raised arm with the most motion."""
        return max((a.get("path", 0.0) for a in self.reading.arms.values() if a.get("raised")), default=0.0)


@dataclass
class Choice:
    commander: int | None                 # pan-tilt track id
    reason: str
    people: list = field(default_factory=list)      # per person: {id, facing, facing_why, raised, moving, command, score, path, left_out}

    def to_dict(self) -> dict:
        return {"commander": self.commander, "reason": self.reason, "people": self.people}


def _describe(p: PersonReading, why_out: str = "") -> dict:
    r = p.reading
    return {"id": p.track_id, "bearing_deg": round(p.bearing_deg, 2), "facing": p.facing, "facing_why": p.facing_why,
            "raised": r.raised, "moving": r.moving, "command": r.command, "score": round(r.score, 3),
            "path": round(p.raised_path(), 3), "left_out": why_out}


def pick_commander(persons: list[PersonReading], ccfg: dict, previous: int | None = None,
                   ineligible: dict | None = None) -> Choice:
    """The commander among the people in view; see the module docstring for the rules. ineligible: {track id: reason}."""
    ineligible = ineligible or {}
    desc: dict[int, dict] = {}
    movers, holders = [], []
    for p in persons:
        r = p.reading
        if not p.facing:
            out = p.facing_why
        elif not r.raised:
            out = "no raised arm"
        elif p.track_id in ineligible:
            out = ineligible[p.track_id]
        elif r.moving:
            out = ""
            movers.append(p)
        elif r.command in gm.COMMANDS:
            out = ""
            holders.append(p)
        else:
            out = "raised arm neither moving nor holding a command"
        desc[p.track_id] = _describe(p, out)
    people = list(desc.values())
    cands = movers + holders
    if not cands:
        return Choice(None, "no person is facing the robot with a moving or gesturing raised hand", people)
    if previous is not None and any(p.track_id == previous for p in cands):
        return Choice(previous, "kept the previous commander: still gesturing", people)
    pool, score = (movers, lambda p: p.raised_path()) if movers else (holders, lambda p: p.reading.score)
    kind = "moving hand" if movers else "held command"
    if len(pool) == 1:
        return Choice(pool[0].track_id, f"the only facing person with a {kind}", people)
    ranked = sorted(pool, key=score, reverse=True)
    margin = ccfg["motion_margin"] if movers else 0.0
    if score(ranked[0]) - score(ranked[1]) > margin + 1e-9:
        return Choice(ranked[0].track_id, f"most {kind} of {len(pool)} candidates", people)
    return Choice(None, f"tie between {len(pool)} people with a {kind} (within {margin} of each other)", people)


def link_to_360(bearing_deg: float, people_360: list[dict], tol_deg: float) -> int | None:
    """The 360-camera track id of the person at this bearing (relative to the robot), or None when none is within
    tol_deg or two are equally near (ambiguous). people_360: [{'track_id', 'bearing_deg'}]."""
    near = sorted((abs(gm.wrap(q["bearing_deg"] - bearing_deg)), q["track_id"]) for q in people_360)
    near = [(d, t) for d, t in near if d <= tol_deg]
    if not near or (len(near) > 1 and abs(near[0][0] - near[1][0]) < 1e-9):
        return None
    return near[0][1]
