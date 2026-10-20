"""Step 5: the guided robot's state machine and steering, in Python (decisions are made here, Unity executes).

Inputs per telemetry tick (TickInput): robot pose and speeds, the NavMesh path corners Unity computed for the target
this controller requested, and the latest perception (people from the 360 deg camera with the pose of their frame,
the latest gesture reading from the pan-tilt camera). Output (Command): v, omega, pan, NavMesh target, state name and
screen text, i.e. one protocol v2 'command'. The controller knows the roadmap (configs/roadmap.json), never goal B.

States: IDLE -> NAVIGATE -> (junction) SCAN -> APPROACH -> ASK -> READ -> EXECUTE -> NAVIGATE ... -> DONE, or ABORTED.
Always active (checked before the state logic): a STOP gesture, a person in the path corridor ahead, or perception
that has gone stale while driving stops the robot; the state resumes when the condition clears. Unity's own 0.3 s
watchdog covers a silent Python.

Conventions: Unity yaw in degrees (0 = +z, 90 = +x, grows clockwise from above); bearings + = right. Toward Unity
(protocol v2): omega in rad/s with omega > 0 = LEFT (REP-103), pan_deg > 0 = LEFT.

Pure Python, no I/O: tested in the simulator (hri_sim.py) without Unity.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from pathlib import Path

HERE = Path(__file__).resolve().parent
DIRECTIONS = ("LEFT", "FORWARD_LEFT", "FORWARD", "FORWARD_RIGHT", "RIGHT")
STEPS = ("navigate", "scan", "approach", "ask", "gesture", "execute")


def load_json(path) -> dict:
    p = Path(path)
    return json.loads((p if p.is_absolute() else HERE / p).read_text(encoding="utf-8"))


# ---------------------------------------------------------------- geometry

def wrap(a: float) -> float:
    return (a + 180.0) % 360.0 - 180.0


def yaw_to(x0: float, z0: float, x1: float, z1: float) -> float:
    """Unity yaw (deg) of the direction (x0, z0) -> (x1, z1)."""
    return math.degrees(math.atan2(x1 - x0, z1 - z0))


def world_point(x: float, z: float, yaw_deg: float, bearing_deg: float, dist: float) -> tuple[float, float]:
    a = math.radians(yaw_deg + bearing_deg)
    return x + math.sin(a) * dist, z + math.cos(a) * dist


def turn_command(turn_deg: float) -> str:
    """Direction command for a branch leaving at a signed turn (deg, + = right) from the arrival direction."""
    a = wrap(turn_deg)
    if a < -67.5:
        return "LEFT"
    if a < -22.5:
        return "FORWARD_LEFT"
    if a <= 22.5:
        return "FORWARD"
    if a <= 67.5:
        return "FORWARD_RIGHT"
    return "RIGHT"


def stop_distance(v: float, s: dict) -> float:
    """Distance ahead (robot centre to person centre) within which a person stops the robot at speed v:
    body + person radius + reaction distance (perception latency) + braking distance + margin."""
    v = abs(v)
    return s["body_and_person_m"] + v * s["reaction_s"] + v * v / (2.0 * s["decel_mps2"]) + s["margin_m"]


def in_path(rx: float, rz: float, yaw_deg: float, px: float, pz: float, ahead_m: float, half_width_m: float) -> bool:
    """Person ahead of the robot within ahead_m and within half_width_m of its centre line."""
    a = math.radians(yaw_deg)
    fx, fz = math.sin(a), math.cos(a)
    dx, dz = px - rx, pz - rz
    along = dx * fx + dz * fz
    across = abs(dx * fz - dz * fx)
    return 0.0 < along <= ahead_m and across <= half_width_m


# ---------------------------------------------------------------- roadmap

class Roadmap:
    def __init__(self, cfg: dict):
        self.cfg = cfg
        self.start = cfg["start"]
        self.nodes = {k: dict(v) for k, v in cfg["nodes"].items()}
        self.branches = {k: dict(v) for k, v in cfg.get("branches", {}).items()}

    def pos(self, name: str) -> tuple[float, float]:
        n = self.nodes[name]
        return n["x"], n["z"]

    def kind(self, name: str) -> str:
        return self.nodes[name]["kind"]

    def next(self, name: str, command: str) -> str | None:
        return self.branches.get(name, {}).get(command)

    def only_next(self, name: str) -> str | None:
        b = self.branches.get(name, {})
        return next(iter(b.values())) if len(b) == 1 else None

    def reaches(self, name: str, goal: str, seen=None) -> bool:
        seen = seen if seen is not None else set()
        if name == goal:
            return True
        if name in seen:
            return False
        seen.add(name)
        return any(self.reaches(n, goal, seen) for n in self.branches.get(name, {}).values())

    def command_toward(self, junction: str, goal: str) -> str:
        """SCENARIO / SCORING ONLY (simulator and evaluation): the command that leads toward goal."""
        for cmd, n in self.branches.get(junction, {}).items():
            if self.reaches(n, goal):
                return cmd
        return "NONE"

    def endpoints(self) -> list[str]:
        return [k for k, v in self.nodes.items() if v["kind"] == "endpoint"]

    def stand(self, junction: str) -> tuple[float, float, float]:
        """Worker stand (x, z, facing yaw) of a junction (scenario side)."""
        jx, jz = self.pos(junction)
        ax, az = self.pos(self.nodes[junction]["arrive_from"])
        a = math.radians(yaw_to(ax, az, jx, jz))
        off = self.cfg["worker_stand"]["corner_offset_m"]
        fx, fz = math.sin(a), math.cos(a)
        rx, rz = fz, -fx  # right of the arrival direction
        return jx + (fx + rx) * off, jz + (fz + rz) * off, wrap(math.degrees(a) + 180.0)

    def check_labels(self) -> list[str]:
        """Branch labels must match the geometry (same rule as the Unity builder)."""
        bad = []
        for j, br in self.branches.items():
            prev = self.nodes[j].get("arrive_from")
            if prev is None:
                continue
            jx, jz = self.pos(j)
            arrive = yaw_to(*self.pos(prev), jx, jz)
            for cmd, n in br.items():
                if turn_command(yaw_to(jx, jz, *self.pos(n)) - arrive) != cmd:
                    bad.append(f"{j} {cmd} -> {n}")
        return bad


# ---------------------------------------------------------------- dialog (1.0 s hold, ask once more, abort)

class GestureDialog:
    """Accept a direction read for hold_s (by frame time). A different direction restarts the hold; a NONE reading
    (no command seen) restarts it only when the gap since the candidate was last seen exceeds max_none_gap_s
    (0 = strict: any NONE restarts). Nothing accepted within window_s -> unclear: ask again (max_asks in total),
    then abort. STOP is never an answer."""

    def __init__(self, hold_s: float, window_s: float, max_asks: int, max_none_gap_s: float = 0.0):
        self.hold_s, self.window_s, self.max_asks, self.max_none_gap_s = hold_s, window_s, max_asks, max_none_gap_s
        self.reset()

    def reset(self):
        self.asks = 0
        self.accepted = "NONE"
        self.candidate, self.since, self.last_seen, self.ask_start = "NONE", 0.0, 0.0, 0.0

    def begin_ask(self, t: float):
        self.asks += 1
        self.ask_start = t
        self.candidate, self.since, self.last_seen = "NONE", t, t

    def update(self, command: str, t_frame: float, t_now: float) -> str:
        """Feed one reading (taken at t_frame). Returns 'pending', 'accepted', 'ask_again' or 'abort'."""
        if command not in DIRECTIONS:
            if self.candidate == "NONE" or t_frame - self.last_seen > self.max_none_gap_s + 1e-6:
                self.candidate, self.since = "NONE", t_frame
        elif command != self.candidate:
            self.candidate, self.since, self.last_seen = command, t_frame, t_frame
        else:
            self.last_seen = t_frame
            if t_frame - self.since >= self.hold_s - 1e-6:
                self.accepted = command
                return "accepted"
        return self.unclear() if t_now - self.ask_start >= self.window_s else "pending"

    def unclear(self) -> str:
        self.accepted = "NONE"
        return "ask_again" if self.asks < self.max_asks else "abort"


# ---------------------------------------------------------------- pure pursuit

def pure_pursuit(x: float, z: float, yaw: float, path: list[tuple[float, float]], d: dict, max_speed: float,
                 stop_m: float) -> tuple[float, float, bool]:
    """(v m/s, omega rad/s with > 0 = left, arrived) along the polyline path (first point ~ robot)."""
    gx, gz = path[-1]
    to_goal = math.hypot(gx - x, gz - z)
    if to_goal <= stop_m:
        return 0.0, 0.0, True
    # look-ahead point: the first path point at least lookahead away, interpolated
    target = (gx, gz)
    for (ax, az), (bx, bz) in zip(path, path[1:]):
        da, db = math.hypot(ax - x, az - z), math.hypot(bx - x, bz - z)
        if db >= d["lookahead_m"] and da < d["lookahead_m"]:
            f = (d["lookahead_m"] - da) / max(db - da, 1e-6)
            target = (ax + (bx - ax) * f, az + (bz - az) * f)
            break
        if da >= d["lookahead_m"]:
            target = (ax, az)
            break
    err = wrap(yaw_to(x, z, *target) - yaw)  # + = target to the right
    wmax = d["max_turn_rate_radps"]
    if abs(err) > d["rotate_in_place_deg"]:
        return 0.0, max(-wmax, min(wmax, -math.radians(d["turn_gain"] * err))), False
    ld = max(math.hypot(target[0] - x, target[1] - z), 1e-3)
    kappa = 2.0 * math.sin(math.radians(err)) / ld          # curvature, + = turning right
    v = max_speed * math.cos(math.radians(err))
    v = min(v, math.sqrt(2.0 * 0.5 * max(to_goal - stop_m, 0.0)) + 0.05)  # brake at 0.5 m/s^2 before the goal
    if abs(kappa) > 1e-4:
        v = min(v, wmax / abs(kappa))
    v = max(0.0, min(max_speed, v))
    return v, max(-wmax, min(wmax, -v * kappa)), False


def turn_toward(x: float, z: float, yaw: float, px: float, pz: float, d: dict, tol_deg: float) -> tuple[float, bool]:
    """(omega rad/s, aligned) to turn in place toward (px, pz)."""
    err = wrap(yaw_to(x, z, px, pz) - yaw)
    if abs(err) <= tol_deg:
        return 0.0, True
    w = d["max_turn_rate_radps"]
    return max(-w, min(w, -math.radians(d["turn_gain"] * err))), False


# ---------------------------------------------------------------- controller

@dataclass
class TickInput:
    time_s: float
    x: float
    z: float
    yaw_deg: float
    v: float = 0.0
    omega: float = 0.0
    nav_corners: list = field(default_factory=list)       # [(x, z)] from the robot to the requested target
    nav_target: tuple | None = None                        # the target those corners lead to
    people: list = field(default_factory=list)             # [{"x", "z", "distance_m", "bearing_deg"}] world, from one frame
    people_time_s: float | None = None                     # capture time of that 360 frame
    gesture: str = "NONE"
    gesture_time_s: float | None = None                    # capture time of the pan-tilt frame read


@dataclass
class Command:
    v: float = 0.0
    omega: float = 0.0
    pan_deg: float = 0.0
    has_target: bool = False
    target_x: float = 0.0
    target_z: float = 0.0
    state: str = "idle"
    screen_text: str = ""

    def to_message(self) -> dict:
        return {"v": float(self.v), "omega": float(self.omega), "pan_deg": float(self.pan_deg),
                "has_target": bool(self.has_target), "target_x": float(self.target_x), "target_z": float(self.target_z),
                "state": self.state, "screen_text": self.screen_text}


class Controller:
    def __init__(self, cfg: dict, roadmap: Roadmap):
        self.cfg, self.road = cfg, roadmap
        self.d, self.g, self.s = cfg["drive"], cfg["dialog"], cfg["safety"]
        self.dialog = GestureDialog(self.g["gesture_hold_s"], self.g["gesture_window_s"], self.g["max_asks"],
                                    self.g.get("max_none_gap_s", 0.0))
        self.state = "idle"
        self.reset(None)

    # -- run bookkeeping --
    def reset(self, t: float | None):
        """New trial at the start node (t None = idle until begin())."""
        self.state = "idle"
        self.node = self.road.start
        self.target_node = None
        self.step_s = {k: 0.0 for k in STEPS}
        self.safety_s = 0.0
        self.safety_reason = ""
        self.abort_reason = ""
        self.junctions: list[dict] = []
        self.record = None
        self.person = None
        self.approach_point = None
        self.turning = False
        self.next_node = None
        self.state_start = t or 0.0
        self.last_t = t
        self.last_gesture_frame = None
        self.last_read = "NONE"
        self.dialog.reset()
        self.trace: list[str] = []

    def begin(self, t: float):
        self.reset(t)
        self._arrive(self.road.start, t)

    @property
    def finished(self) -> bool:
        return self.state in ("done", "aborted")

    def _set(self, state: str, t: float):
        self.state, self.state_start = state, t
        self.trace.append(f"{t:.2f}:{state}")

    def _arrive(self, node: str, t: float):
        self.node = node
        kind = self.road.kind(node)
        if kind == "endpoint":
            self._set("done", t)
        elif kind == "junction":
            self.dialog.reset()
            self._set("scan", t)
        else:
            nxt = self.road.only_next(node)
            if nxt is None:
                self._abort(f"dead end at {node}", t)
            else:
                self._navigate(nxt, t)

    def _navigate(self, node: str, t: float):
        self.target_node = node
        self._set("navigate", t)

    def _abort(self, reason: str, t: float):
        self.abort_reason = reason
        if self.record is not None:
            self._finish_record("aborted", t)
        self._set("aborted", t)

    def _finish_record(self, result: str, t: float):
        self.record.update(result=result, asks=self.dialog.asks, read=self.dialog.accepted, t_end=round(t, 3))
        self.junctions.append(self.record)
        self.record = None

    # -- perception helpers --
    def _fresh_people(self, inp: TickInput) -> list:
        if inp.people_time_s is None or inp.time_s - inp.people_time_s > self.s["people_stale_s"]:
            return []
        return inp.people

    def _fresh_gesture(self, inp: TickInput) -> str:
        if inp.gesture_time_s is None or inp.time_s - inp.gesture_time_s > self.s["gesture_stale_s"]:
            return "NONE"
        return inp.gesture

    def _safety(self, inp: TickInput) -> str | None:
        if self._fresh_gesture(inp) == "STOP":
            return "STOP gesture"
        for p in self._fresh_people(inp):
            if in_path(inp.x, inp.z, inp.yaw_deg, p["x"], p["z"], stop_distance(inp.v, self.s), self.s["corridor_half_width_m"]):
                return "person in path"
        moving = self.state in ("navigate", "approach") and not self.turning
        if moving and (inp.people_time_s is None or inp.time_s - inp.people_time_s > self.s["people_stale_s"]):
            return "perception stale"
        return None

    def _path(self, inp: TickInput, tx: float, tz: float) -> list:
        """NavMesh corners for this target if Unity has them, else a straight line."""
        if inp.nav_target is not None and inp.nav_corners and math.hypot(inp.nav_target[0] - tx, inp.nav_target[1] - tz) < 0.05:
            return [(inp.x, inp.z)] + [tuple(c) for c in inp.nav_corners[1:]]
        return [(inp.x, inp.z), (tx, tz)]

    # -- one tick --
    def step(self, inp: TickInput) -> Command:
        t = inp.time_s
        dt = 0.0 if self.last_t is None else max(0.0, t - self.last_t)
        self.last_t = t
        cmd = Command(state=self.state)
        if self.state in ("idle", "done", "aborted"):
            return cmd
        self.step_s[_step_of(self.state)] += dt
        reason = self._safety(inp)
        target = self._target()
        if target is not None:
            cmd.has_target, cmd.target_x, cmd.target_z = True, target[0], target[1]
        if self.state in ("ask", "read") and self.person is not None:
            cmd.pan_deg = -wrap(yaw_to(inp.x, inp.z, *self.person) - inp.yaw_deg)   # pan > 0 = left
            cmd.screen_text = self.g["prompt"] + (" (asking again)" if self.dialog.asks > 1 else "")
        if reason is not None:
            self.safety_s += dt
            self.safety_reason = reason
            cmd.state = f"{self.state} (stopped: {reason})"
            return cmd
        self.safety_reason = ""
        self._tick(inp, cmd)
        cmd.state = self.state
        if self.state in ("done", "aborted"):
            cmd.v, cmd.omega, cmd.has_target, cmd.screen_text = 0.0, 0.0, False, ""
        return cmd

    def _target(self):
        if self.state == "navigate" and self.target_node:
            return self.road.pos(self.target_node)
        if self.state == "approach" and self.approach_point:
            return self.approach_point
        if self.state == "execute" and self.next_node:
            return self.road.pos(self.next_node)
        return None

    def _tick(self, inp: TickInput, cmd: Command):
        t, d = inp.time_s, self.d
        stopped = abs(inp.v) < d["stopped_speed_mps"]
        if self.state == "navigate":
            tx, tz = self.road.pos(self.target_node)
            junction = self.road.kind(self.target_node) == "junction"
            dist = math.hypot(tx - inp.x, tz - inp.z)
            speed = d["junction_speed_mps"] if junction and dist < d["junction_slow_radius_m"] else d["cruise_speed_mps"]
            stop_m = d["arrive_junction_m"] if junction else d["arrive_endpoint_m"]
            cmd.v, cmd.omega, arrived = pure_pursuit(inp.x, inp.z, inp.yaw_deg, self._path(inp, tx, tz), d, speed, stop_m)
            if arrived and stopped:
                self._arrive(self.target_node, t)
        elif self.state == "scan":
            people = self._fresh_people(inp)
            seen = people and inp.people_time_s is not None and inp.people_time_s >= self.state_start
            if t - self.state_start >= self.g["scan_min_s"] and seen:
                p = min(people, key=lambda q: q["distance_m"])
                self.person = (p["x"], p["z"])
                ax, az = inp.x - p["x"], inp.z - p["z"]
                n = math.hypot(ax, az) or 1.0
                r = self.g["approach_distance_m"]
                self.approach_point = (p["x"] + ax / n * r, p["z"] + az / n * r)
                self.turning = False
                self.record = {"junction": self.node, "t_start": round(t, 3), "person_x": round(p["x"], 3),
                               "person_z": round(p["z"], 3), "person_distance_m": round(p["distance_m"], 3)}
                self._set("approach", t)
            elif t - self.state_start >= self.g["scan_timeout_s"]:
                self._abort(f"no person found at {self.node}", t)
        elif self.state == "approach":
            if not self.turning:
                cmd.v, cmd.omega, arrived = pure_pursuit(inp.x, inp.z, inp.yaw_deg, self._path(inp, *self.approach_point),
                                                         d, d["approach_speed_mps"], d["approach_tolerance_m"])
                if arrived and stopped:
                    self.turning = True
            if self.turning:
                cmd.omega, aligned = turn_toward(inp.x, inp.z, inp.yaw_deg, *self.person, d, d["align_tolerance_deg"])
                cmd.v = 0.0
                if aligned and abs(inp.omega) < 0.05:
                    self.turning = False
                    self._ask(t, cmd)
        elif self.state == "ask":
            if t - self.state_start >= self.g["ask_settle_s"]:
                self._set("read", t)
        elif self.state == "read":
            if inp.gesture_time_s is not None and inp.gesture_time_s != self.last_gesture_frame \
                    and inp.gesture_time_s >= self.dialog.ask_start:
                self.last_gesture_frame = inp.gesture_time_s
                self.last_read = inp.gesture
                ev = self.dialog.update(inp.gesture, inp.gesture_time_s, t)
            else:  # no new reading this tick: only the window can end the ask
                ev = "pending" if t - self.dialog.ask_start < self.g["gesture_window_s"] else self.dialog.unclear()
            if ev == "accepted":
                nxt = self.road.next(self.node, self.dialog.accepted)
                if nxt is not None:
                    self._finish_record("accepted", t)
                    self.next_node = nxt
                    self._set("execute", t)
                    return
                ev = self.dialog.unclear()  # a direction with no branch here: same as unclear
            if ev == "ask_again":
                self._ask(t, cmd)
            elif ev == "abort":
                self._abort(f"gesture unclear after {self.dialog.asks} asks at {self.node}", t)
        elif self.state == "execute":
            nx, nz = self.road.pos(self.next_node)
            cmd.omega, aligned = turn_toward(inp.x, inp.z, inp.yaw_deg, nx, nz, d, d["execute_align_deg"])
            if aligned:
                self._navigate(self.next_node, t)

    def _ask(self, t: float, cmd: Command):
        self.dialog.begin_ask(t)
        self._set("ask", t)
        cmd.screen_text = self.g["prompt"] + (" (asking again)" if self.dialog.asks > 1 else "")

    def summary(self) -> dict:
        return {"state": self.state, "final_node": self.node, "abort_reason": self.abort_reason,
                "step_s": {k: round(v, 3) for k, v in self.step_s.items()}, "safety_stop_s": round(self.safety_s, 3),
                "junctions": list(self.junctions), "trace": list(self.trace)}


def _step_of(state: str) -> str:
    return {"scan": "scan", "approach": "approach", "ask": "ask", "read": "gesture", "execute": "execute"}.get(state, "navigate")


def make_controller(control_path="configs/hri_control.json", roadmap_path="configs/roadmap.json") -> Controller:
    return Controller(load_json(control_path), Roadmap(load_json(roadmap_path)))
