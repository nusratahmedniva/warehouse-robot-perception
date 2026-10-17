"""Step 9: movement decisions (MOVE / STOP / WAIT) from people, passage and gesture inputs.

Standard library only; no file access, no dataset, no reference data. The same code runs on THUD replays and,
later, on Unity frames: a caller builds one DecisionFrame per timestamp from its own sources (motion output or
the Unity scene, the Step 6 passage result, the gesture adapter) and passes it to DecisionEngine.step().

Ground plane: (x, z) in metres, in the frame of the route corridor (THUD: world x-z, y up).

Rules, checked top-down; the first match wins (configs/decision.json holds every threshold):
 1. Person inside the stop zone (latest valid position; no motion needed)          -> STOP
 2. Person predicted to enter the stop zone within entry_horizon_s (trusted motion) -> STOP
 3. Valid STOP gesture from anyone                                                  -> STOP
 4. Person in the caution zone without trusted motion                               -> STOP
 5. Passage blocked / unknown / not_evaluated                                       -> WAIT
 6. MOVE requested but passage too narrow                                           -> STOP
 7. Valid MOVE held for move_hold_s and passage clear                               -> MOVE
 8. Otherwise                                                                       -> WAIT
Switching to STOP is immediate; switching to MOVE needs the rule-7 conditions to hold for resume_hold_s.

Stop zone: the corridor from the robot's projected position to look_ahead_m ahead (flat far end), where
look_ahead_m = v * reaction_s + v^2 / (2 * decel) + buffer_m (footprint.look_ahead). Caution zone: outside the
stop zone, within caution_lateral_m of the corridor edge, up to caution_ahead_m ahead (flat far end).
"""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass, field

DECISIONS = ("MOVE", "STOP", "WAIT")
PASSAGE_STATUSES = ("clear", "too_narrow", "blocked", "unknown", "not_evaluated")
PASSAGE_NOT_CONFIRMED = ("blocked", "unknown", "not_evaluated")
GESTURES = ("STOP", "MOVE", "NONE")
NO_MOTION_LABELS = ("unknown", "insufficient_history", "not_evaluated", "")
EPS = 1e-9

RULE_NAMES = {
    1: "person in route",
    2: "person entering stop zone",
    3: "STOP gesture",
    4: "cannot confirm person's movement",
    5: "cannot confirm passage is clear",
    6: "load too wide",
    7: "passage clear",
    8: "waiting for instruction",
}


# ---------------------------------------------------------------- input contract

@dataclass(frozen=True)
class PersonState:
    """One tracked person at one timestamp. position_xz / velocity_xz are ground-plane (x, z) or None.
    distance_m: ground distance from the robot (used for motion_range_m). distance_lower_bound_m: a distance the
    person is known to be at least as far as (errors must be on the near side); used only for a person without a
    position. None -> no lower bound, so an unlocated person counts as in the caution zone."""
    track_id: int | str
    timestamp: float
    position_xz: tuple[float, float] | None
    distance_m: float | None
    motion_label: str
    velocity_xz: tuple[float, float] | None
    motion_trusted: bool
    distance_lower_bound_m: float | None = None


@dataclass(frozen=True)
class PassageState:
    """Step 6 result for the route ahead. required_width_m is the width the passage was evaluated against."""
    status: str
    available_width_m: float | None
    required_width_m: float | None

    def __post_init__(self):
        if self.status not in PASSAGE_STATUSES:
            raise ValueError(f"passage status {self.status!r} not in {PASSAGE_STATUSES}")


@dataclass(frozen=True)
class GestureEvent:
    """One gesture-module output, through the adapter. track_id may be None (gesturer not associated)."""
    timestamp: float
    track_id: int | str | None
    gesture: str
    confidence: float

    def __post_init__(self):
        if self.gesture not in GESTURES:
            raise ValueError(f"gesture {self.gesture!r} not in {GESTURES}")


@dataclass(frozen=True)
class RouteCorridor:
    """Centre polyline on the ground plane, in travel order, plus full width."""
    centreline_xz: tuple[tuple[float, float], ...]
    width_m: float
    label: str = "route"

    def __post_init__(self):
        if len(self.centreline_xz) < 2:
            raise ValueError("corridor centreline needs at least 2 points")
        if not self.width_m > 0:
            raise ValueError("corridor width must be positive")


@dataclass(frozen=True)
class DecisionFrame:
    """Everything the decision needs at one timestamp. robot_xz None: the whole corridor counts as ahead."""
    timestamp: float
    persons: tuple[PersonState, ...]
    passage: PassageState
    gestures: tuple[GestureEvent, ...] = ()
    robot_xz: tuple[float, float] | None = None


@dataclass
class Decision:
    timestamp: float
    decision: str
    rule: int
    reason: str
    track_ids: list = field(default_factory=list)
    snapshot: dict = field(default_factory=dict)

    def as_dict(self) -> dict:
        return asdict(self)


# ---------------------------------------------------------------- corridor geometry

class Polyline:
    def __init__(self, points):
        self.pts = [(float(x), float(z)) for x, z in points]
        self.cum = [0.0]
        for (ax, az), (bx, bz) in zip(self.pts, self.pts[1:]):
            self.cum.append(self.cum[-1] + math.hypot(bx - ax, bz - az))
        self.length = self.cum[-1]

    def nearest(self, p, s0: float = 0.0, s1: float = math.inf) -> tuple[float, float]:
        """(distance, arc length of the nearest point) from p to the part of the line with s0 <= s <= s1."""
        best = (math.inf, math.nan)
        s0 = max(0.0, min(s0, self.length))
        s1 = max(s0, min(s1, self.length))
        for i in range(len(self.pts) - 1):
            ca, cb = self.cum[i], self.cum[i + 1]
            if cb < s0 - EPS or ca > s1 + EPS:
                continue
            seg = cb - ca
            (ax, az), (bx, bz) = self.pts[i], self.pts[i + 1]
            if seg <= EPS:
                u_lo = u_hi = 0.0
            else:
                u_lo, u_hi = max(0.0, (s0 - ca) / seg), min(1.0, (s1 - ca) / seg)
            dx, dz = bx - ax, bz - az
            u = ((p[0] - ax) * dx + (p[1] - az) * dz) / (seg * seg) if seg > EPS else 0.0
            u = min(max(u, u_lo), u_hi)
            d = math.hypot(p[0] - (ax + u * dx), p[1] - (az + u * dz))
            if d < best[0]:
                best = (d, ca + u * seg)
        return best

    def point_and_tangent(self, s: float) -> tuple[tuple[float, float], tuple[float, float]]:
        """Point at arc length s (clamped) and the unit direction of travel there."""
        s = max(0.0, min(s, self.length))
        for i in range(len(self.pts) - 1):
            ca, cb = self.cum[i], self.cum[i + 1]
            if cb - ca <= EPS or (s > cb + EPS and i < len(self.pts) - 2):
                continue
            (ax, az), (bx, bz) = self.pts[i], self.pts[i + 1]
            u = min(max((s - ca) / (cb - ca), 0.0), 1.0)
            return (ax + u * (bx - ax), az + u * (bz - az)), ((bx - ax) / (cb - ca), (bz - az) / (cb - ca))
        (ax, az), (bx, bz) = self.pts[-2], self.pts[-1]
        n = math.hypot(bx - ax, bz - az) or 1.0
        return self.pts[-1], ((bx - ax) / n, (bz - az) / n)

    def zone(self, p, s0: float, s1: float, half: float) -> tuple[bool, float, float]:
        """Band of half-width `half` around the line between arc lengths s0 and s1, with a flat far end at s1
        (round at s0, which covers the robot body). Returns (inside, distance to the centre-line portion,
        arc length of the nearest point); a point past the flat end is outside whatever its distance.
        Where the route itself ends before s1, the end stays round: the robot and its load reach past the last
        centre-line point, so nothing there is cut off."""
        d, s = self.nearest(p, s0, s1)
        if d > half + EPS:
            return False, d, s
        if s1 < self.length - EPS and s >= s1 - EPS:
            e, t = self.point_and_tangent(s1)
            if (p[0] - e[0]) * t[0] + (p[1] - e[1]) * t[1] > EPS:
                return False, d, s
        return True, d, s

    def gap_to_zone(self, p, s0: float, s1: float, half: float) -> float:
        """Ground distance from p to the zone (0 inside): to its side, or to its flat far end."""
        inside, d, s = self.zone(p, s0, s1, half)
        if inside:
            return 0.0
        e, t = self.point_and_tangent(s1)
        along = (p[0] - e[0]) * t[0] + (p[1] - e[1]) * t[1]
        if s1 < self.length - EPS and s >= s1 - EPS and along > EPS:
            across = abs(-(p[0] - e[0]) * t[1] + (p[1] - e[1]) * t[0])
            return math.hypot(along, max(0.0, across - half))
        return max(0.0, d - half)


# ---------------------------------------------------------------- gestures

class GestureFilter:
    """Per-track gesture state. A STOP is accepted once held for stop_hold_s, a MOVE once held for move_hold_s
    (both in seconds, independent of the frame rate); an event older than gesture_timeout_s counts as NONE, and
    an event below min_confidence counts as NONE. A gesture is held while its events keep arriving no more than
    gesture_timeout_s apart."""

    def __init__(self, cfg: dict):
        self.min_conf = cfg["gesture_min_confidence"]
        self.stop_hold = cfg["stop_hold_s"]
        self.move_hold = cfg["move_hold_s"]
        self.timeout = cfg["gesture_timeout_s"]
        self.tracks: dict = {}

    def update(self, events, t: float) -> None:
        for e in sorted(events, key=lambda e: e.timestamp):
            if e.timestamp > t + EPS:
                raise ValueError(f"gesture event at {e.timestamp} is later than the decision time {t}")
            st = self.tracks.setdefault(e.track_id, {"last_t": None, "gesture": "NONE", "confidence": 0.0,
                                                     "stop_since": None, "move_since": None})
            if st["last_t"] is not None and e.timestamp <= st["last_t"] + EPS:
                continue  # already seen
            g = e.gesture if e.confidence >= self.min_conf else "NONE"
            fresh = st["last_t"] is not None and e.timestamp - st["last_t"] <= self.timeout + EPS
            prev = st["gesture"] if fresh else "NONE"
            st["stop_since"] = (st["stop_since"] if prev == "STOP" else e.timestamp) if g == "STOP" else None
            st["move_since"] = (st["move_since"] if prev == "MOVE" else e.timestamp) if g == "MOVE" else None
            st.update(last_t=e.timestamp, gesture=g, confidence=e.confidence)

    def state(self, t: float) -> list[dict]:
        out = []
        for tid, st in self.tracks.items():
            age = t - st["last_t"]
            g = st["gesture"] if age <= self.timeout + EPS else "NONE"
            held = t - st["move_since"] if g == "MOVE" else 0.0
            stop_held = t - st["stop_since"] if g == "STOP" else 0.0
            out.append({"track_id": tid, "gesture": g, "last_event_gesture": st["gesture"],
                        "confidence": st["confidence"], "age_s": round(age, 4),
                        "stop_held_s": round(stop_held, 4),
                        "stop_accepted": g == "STOP" and stop_held >= self.stop_hold - EPS,
                        "move_held_s": round(held, 4), "move_accepted": g == "MOVE" and held >= self.move_hold - EPS})
        return out


# ---------------------------------------------------------------- engine

def _f2(v) -> str:
    return "unknown" if v is None else f"{v:.2f}"


class DecisionEngine:
    def __init__(self, cfg: dict, required: dict, corridor: RouteCorridor):
        self.cfg = cfg
        self.required_m = required["required_width_m"]
        self.required = required
        self.corridor = corridor
        self.line = Polyline(corridor.centreline_xz)
        # one required width everywhere: the corridor is the robot-and-load footprint plus margins
        if abs(corridor.width_m - self.required_m) > 1e-6:
            raise ValueError(f"corridor width {corridor.width_m} m differs from the required width "
                             f"{self.required_m} m; build the corridor from footprint.load_footprint()")
        self.corridor_width_m = self.required_m
        self.half = self.corridor_width_m / 2
        self.look_ahead_m = cfg["look_ahead"]["look_ahead_m"]
        if cfg["caution_ahead_m"] < self.look_ahead_m - EPS:
            raise ValueError(f"caution_ahead_m {cfg['caution_ahead_m']} < look_ahead_m {self.look_ahead_m}")
        self.gestures = GestureFilter(cfg)
        self.memory: dict = {}  # track_id -> (timestamp, position_xz) of the latest valid position
        self.last_t: float | None = None
        self.last_decision: str | None = None
        self.move_candidate_since: float | None = None

    # -- per person

    def _motion(self, p: PersonState | None, pos_source: str | None) -> tuple[bool, str]:
        """(trusted motion usable for prediction, status)."""
        if p is None:
            return False, "not_observed_this_frame"
        if not p.motion_trusted:
            return False, "untrusted"
        if p.motion_label in NO_MOTION_LABELS:
            return False, p.motion_label or "unknown"
        if p.velocity_xz is None:
            return False, "no_velocity"
        if pos_source != "current":
            return False, "no_current_position"
        if p.distance_m is None:
            return False, "distance_unknown"
        if p.distance_m > self.cfg["motion_range_m"] + EPS:
            return False, f"beyond_motion_range ({p.distance_m:.2f} m > {self.cfg['motion_range_m']:.1f} m)"
        return True, "trusted"

    def _in_stop_zone(self, p, s_robot: float) -> tuple[bool, float, float]:
        return self.line.zone(p, s_robot, s_robot + self.look_ahead_m, self.half)

    def _entry_time(self, pos, vel, s_robot: float) -> float | None:
        """First sampled time at which the constant-velocity prediction is inside the current stop zone. Robot
        motion is not added: it is what look_ahead_m (reaction + braking + buffer) already covers."""
        step, horizon = self.cfg["entry_time_step_s"], self.cfg["entry_horizon_s"]
        for k in range(1, int(round(horizon / step)) + 1):
            tau = k * step
            q = (pos[0] + vel[0] * tau, pos[1] + vel[1] * tau)
            if self._in_stop_zone(q, s_robot)[0]:
                return round(tau, 6)
        return None

    def _assess(self, tid, p: PersonState | None, t: float, s_robot: float) -> dict:
        pos, src = None, None
        if p is not None and p.position_xz is not None:
            pos, src = tuple(p.position_xz), "current"
        elif tid in self.memory and t - self.memory[tid][0] <= self.cfg["person_memory_s"] + EPS:
            pos, src = self.memory[tid][1], "remembered"
        a = {"track_id": tid, "observed": p is not None, "position_xz": pos, "position_source": src,
             "distance_m": p.distance_m if p else None, "motion_label": p.motion_label if p else None,
             "velocity_xz": p.velocity_xz if p else None, "motion_trusted": p.motion_trusted if p else None,
             "in_stop_zone": False, "entry_in_s": None, "in_caution_zone": False}
        ok, status = self._motion(p, src)
        a["motion_usable"], a["motion_status"] = ok, status
        if pos is not None:
            d, s = self.line.nearest(pos, s_robot)
            a["dist_to_centreline_m"], a["ahead_m"] = round(d, 4), round(s - s_robot, 4)
            a["in_stop_zone"] = self._in_stop_zone(pos, s_robot)[0]
            if not a["in_stop_zone"]:
                inside_c, dc, _ = self.line.zone(pos, s_robot, s_robot + self.cfg["caution_ahead_m"],
                                                 self.half + self.cfg["caution_lateral_m"])
                a["dist_to_corridor_edge_m"] = round(dc - self.half, 4)
                a["in_caution_zone"] = inside_c
                if ok:
                    a["entry_in_s"] = self._entry_time(pos, p.velocity_xz, s_robot)
                    if a["entry_in_s"] is not None:
                        gap = self.line.gap_to_zone(pos, s_robot, s_robot + self.look_ahead_m, self.half)
                        a["gap_to_stop_zone_m"] = round(gap, 4)
                        a["closing_speed_mps"] = round(gap / a["entry_in_s"], 4)
        elif p is not None and self.cfg["unlocated_person_in_caution_zone"]:
            # detected but not locatable: inside the caution zone unless a lower bound puts it farther away
            lb = p.distance_lower_bound_m
            a["distance_lower_bound_m"] = lb
            a["in_caution_zone"] = lb is None or lb <= self.cfg["caution_ahead_m"] + EPS
            a["unlocated"] = True
        return a

    # -- passage

    def _passage(self, ps: PassageState) -> tuple[str, str]:
        if ps.required_width_m is not None and abs(ps.required_width_m - self.required_m) > 1e-6:
            return "unknown", (f"passage evaluated for {ps.required_width_m:.2f} m, decision needs "
                               f"{self.required_m:.2f} m")
        if ps.status == "clear":
            if ps.available_width_m is None:
                return "unknown", "clear without a measured width"
            if ps.available_width_m < self.required_m - EPS:
                return "too_narrow", "clear but narrower than required"
        return ps.status, ""

    # -- one timestamp

    def step(self, f: DecisionFrame) -> Decision:
        t = f.timestamp
        if self.last_t is not None and t <= self.last_t + EPS:
            raise ValueError(f"timestamps must increase: {t} after {self.last_t}")
        self.last_t = t
        self.gestures.update(f.gestures, t)
        gs = self.gestures.state(t)
        s_robot = self.line.nearest(f.robot_xz)[1] if f.robot_xz is not None else 0.0

        current = {p.track_id: p for p in f.persons}
        tids = list(current) + [k for k in self.memory if k not in current]
        people = [self._assess(k, current.get(k), t, s_robot) for k in tids]
        people = [a for a in people if a["observed"] or a["position_source"] == "remembered"]
        for p in f.persons:
            if p.position_xz is not None:
                self.memory[p.track_id] = (t, tuple(p.position_xz))
        self.memory = {k: v for k, v in self.memory.items() if t - v[0] <= self.cfg["person_memory_s"] + EPS}

        passage_status, passage_note = self._passage(f.passage)
        snapshot = {
            "robot_xz": f.robot_xz, "robot_arc_length_m": round(s_robot, 4), "corridor_label": self.corridor.label,
            "corridor_width_m": self.corridor_width_m, "required_width_m": self.required_m,
            "look_ahead_m": self.look_ahead_m,
            "persons": people, "passage": asdict(f.passage), "passage_effective_status": passage_status,
            "passage_note": passage_note, "gestures": gs,
        }
        decision, rule, reason, ids = self._rules(t, people, gs, f.passage, passage_status, passage_note)
        self.last_decision = decision
        return Decision(t, decision, rule, reason, ids, snapshot)

    def _rules(self, t, people, gs, passage, status, note):
        req = self.required_m
        r1 = [a for a in people if a["in_stop_zone"]]
        r2 = [a for a in people if a["entry_in_s"] is not None]
        stops = [g for g in gs if g["stop_accepted"]]
        r4 = [a for a in people if a["in_caution_zone"] and not a["motion_usable"] and not a["in_stop_zone"]]
        any_stop = [g for g in gs if g["gesture"] == "STOP"]  # accepted or not: a STOP cancels every MOVE
        moves = [g for g in gs if g["gesture"] == "MOVE"] if not any_stop else []
        moves_held = [g for g in moves if g["move_accepted"]]
        candidate = False

        def ids(xs):
            return [x["track_id"] for x in xs]

        if r1:
            out = ("STOP", 1, "person in route: " + "; ".join(
                f"track {a['track_id']} {a['dist_to_centreline_m']:.2f} m from centre line, {a['ahead_m']:.2f} m ahead"
                + (" (remembered position)" if a["position_source"] == "remembered" else "") for a in r1)
                + f" (stop zone {self.look_ahead_m:.2f} m)", ids(r1))
        elif r2:
            out = ("STOP", 2, "person entering stop zone: " + "; ".join(
                f"track {a['track_id']} predicted to enter in {a['entry_in_s']:.2f} s "
                f"(within {self.cfg['entry_horizon_s']:.1f} s), {a['gap_to_stop_zone_m']:.2f} m away, "
                f"closing at {a['closing_speed_mps']:.2f} m/s" for a in r2), ids(r2))
        elif stops:
            out = ("STOP", 3, "STOP gesture: " + "; ".join(
                f"track {g['track_id']} (confidence {g['confidence']:.2f}, held {g['stop_held_s']:.2f} s)" for g in stops),
                ids(stops))
        elif r4:
            def where(a):
                if a.get("unlocated"):
                    return f"position unknown, at least {_f2(a['distance_lower_bound_m'])} m away"
                if a["dist_to_corridor_edge_m"] <= 0:
                    return f"inside the corridor beyond the stop zone, {a['ahead_m']:.2f} m ahead"
                return f"{a['dist_to_corridor_edge_m']:.2f} m from corridor edge, {a['ahead_m']:.2f} m ahead"
            out = ("STOP", 4, "cannot confirm person's movement: " + "; ".join(
                f"track {a['track_id']} in caution zone ({where(a)}), motion {a['motion_status']}" for a in r4), ids(r4))
        elif status in PASSAGE_NOT_CONFIRMED:
            out = ("WAIT", 5, f"cannot confirm passage is clear: status {status}" + (f" ({note})" if note else ""), [])
        elif moves and status == "too_narrow":
            out = ("STOP", 6, f"load too wide: {_f2(passage.available_width_m)} m available, {req:.2f} m needed",
                   ids(moves))
        elif moves_held and status == "clear":
            candidate = True
            if self.move_candidate_since is None:
                self.move_candidate_since = t
            held = t - self.move_candidate_since
            reason = f"passage clear: {passage.available_width_m:.2f} m available, {req:.2f} m needed"
            if self.last_decision == "MOVE" or held >= self.cfg["resume_hold_s"] - EPS:
                out = ("MOVE", 7, reason, ids(moves_held))
            else:
                out = ("WAIT", 8, f"waiting for instruction: MOVE conditions held {held:.2f} s of "
                                  f"{self.cfg['resume_hold_s']:.2f} s ({reason})", ids(moves_held))
        else:
            detail = ""
            if any_stop:
                detail = " (unconfirmed STOP gesture from track " + ", ".join(str(g["track_id"]) for g in any_stop) \
                         + " cancels any MOVE)"
            elif moves:
                g = max(moves, key=lambda g: g["move_held_s"])
                detail = f" (MOVE from track {g['track_id']} held {g['move_held_s']:.2f} s of {self.cfg['move_hold_s']:.2f} s)"
            elif status == "too_narrow":
                detail = f" (passage too narrow: {_f2(passage.available_width_m)} m available, {req:.2f} m needed)"
            out = ("WAIT", 8, "waiting for instruction" + detail, ids(any_stop or moves))
        if not candidate:
            self.move_candidate_since = None
        return out
