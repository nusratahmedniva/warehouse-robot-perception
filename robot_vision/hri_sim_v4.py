"""v4 simulator groundwork (v4 mode only; hri_sim.py and the v3 simulation are untouched and only reused).

Several people stand at a junction: exactly one commander, the rest bystanders. Each person has a gesture timeline
(an Episode: POINT with a world angle, WAIT or STOP, with start delay, gesturing, holding and returning phases, as
in docs/protocol_v3.md truth.jsonl). Synthetic perception, seeded and reproducible:

- 360 camera: every person within range is detected with p_detect, bearing and distance noise (hri_sim.SimConfig),
  carrying a perfect tracker id;
- pan-tilt camera: the person nearest the optical axis within the field of view and range is read (a gesturing
  bystander nearer the axis than the commander is read instead of the commander). The shown command is read with
  probability coverage[command] (else NONE) and correctly with probability accuracy[command] (else a wrong class
  from `confusion`); POINT carries the pointed angle relative to the robot's forward axis (+ = right) plus Gaussian
  noise point_angle_sigma_deg.

Nothing here is tuned: every probability, noise and timing is an argument, and the defaults are the neutral ones
(coverage 1, accuracy 1, no noise). The default confusion is POINT -> WAIT, WAIT -> STOP, STOP -> WAIT; a wrong
reading of POINT-from-another-class draws its angle uniformly in [-180, 180). simulate_ask also writes the truth rows
of docs/protocol_v3.md, so gesture_data.py can be tested against the simulator.

No v4 controller exists yet (Phase 3+): this module produces perception and truth, it does not drive the robot.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, field

import hri_control as hc
from hri_sim import SimConfig

COMMANDS = ("POINT", "WAIT", "STOP")
DEFAULT_CONFUSION = {"POINT": ["WAIT"], "WAIT": ["STOP"], "STOP": ["WAIT"]}
GESTURING_PHASES = ("gesturing", "holding")


@dataclass
class Episode:
    """One gesture of one person. Times are Unity time (s). Before t0 and after the returning phase the person is
    idle (true command NONE); start_delay and returning also show NONE."""
    command: str
    t0: float
    start_delay_s: float
    gesturing_s: float
    hold_s: float
    returning_s: float
    arm: str = "right"
    clip: str = ""
    world_angle_deg: float | None = None        # POINT: pointed direction, Unity yaw convention (0 = +Z, + = clockwise)

    def __post_init__(self):
        if self.command not in COMMANDS:
            raise ValueError(f"episode command {self.command!r} not in {COMMANDS}")
        if (self.command == "POINT") != (self.world_angle_deg is not None):
            raise ValueError("world_angle_deg is required for POINT and only for POINT")

    def phase(self, t: float) -> tuple[str, float]:
        """(phase name, progress 0..1 within the phase) at time t."""
        edges = [("start_delay", self.start_delay_s), ("gesturing", self.gesturing_s), ("holding", self.hold_s),
                 ("returning", self.returning_s)]
        s = t - self.t0
        if s < 0:
            return "idle", 0.0
        for name, length in edges:
            if s < length:
                return name, s / length if length > 0 else 1.0
            s -= length
        return "idle", 0.0

    def end(self) -> float:
        return self.t0 + self.start_delay_s + self.gesturing_s + self.hold_s + self.returning_s


@dataclass
class Person:
    id: int
    x: float
    z: float
    look: str
    role: str = "bystander"                      # "commander" or "bystander"
    episode: Episode | None = None               # a bystander may gesture too (a distractor)

    def state(self, t: float) -> dict:
        """What the person shows at t: phase, true command, arm, clip and the world POINT angle (None if not POINT).
        While gesturing the pointed angle ramps linearly from 0 (world +Z) to the final angle: a placeholder shape,
        not a model of real arms."""
        if self.episode is None:
            return {"phase": "idle", "command": "NONE", "arm": "none", "clip": "", "world_angle_deg": None}
        e = self.episode
        phase, f = e.phase(t)
        if phase not in GESTURING_PHASES:
            return {"phase": phase, "command": "NONE", "arm": "none", "clip": "", "world_angle_deg": None}
        angle = None
        if e.command == "POINT":
            angle = e.world_angle_deg * (f if phase == "gesturing" else 1.0)
        return {"phase": phase, "command": e.command, "arm": e.arm, "clip": e.clip, "world_angle_deg": angle}


@dataclass
class GestureSimConfig:
    coverage: dict = field(default_factory=dict)        # command -> P(reading is not NONE); default 1
    accuracy: dict = field(default_factory=dict)        # command -> P(correct | not NONE); default 1
    point_angle_sigma_deg: float = 0.0
    confusion: dict = field(default_factory=lambda: {k: list(v) for k, v in DEFAULT_CONFUSION.items()})


class Scene:
    """The people at one junction: exactly one commander, unique ids."""

    def __init__(self, people: list[Person]):
        self.people = people
        if sum(p.role == "commander" for p in people) != 1:
            raise ValueError("a scene needs exactly one commander")
        if len({p.id for p in people}) != len(people):
            raise ValueError("person ids must be unique")
        if any(p.role not in ("commander", "bystander") for p in people):
            raise ValueError("role must be 'commander' or 'bystander'")

    @property
    def commander(self) -> Person:
        return next(p for p in self.people if p.role == "commander")

    def truth_rows(self, t: float, robot_yaw_deg: float) -> list[dict]:
        """One truth.jsonl row per person at time t (docs/protocol_v3.md); the POINT angle is relative to the robot's
        forward axis (+ = right), -1 when the command is not POINT."""
        rows = []
        for p in self.people:
            s = p.state(t)
            rel = hc.wrap(s["world_angle_deg"] - robot_yaw_deg) if s["world_angle_deg"] is not None else -1
            row = {"time_s": round(t, 6), "worker_id": p.id, "look": p.look, "x": p.x, "z": p.z,
                   "true_command": s["command"], "point_angle_deg": rel, "arm": s["arm"], "phase": s["phase"],
                   "is_commander": p.role == "commander"}
            if s["clip"]:
                row["clip"] = s["clip"]
            rows.append(row)
        return rows


def junction_scene(road: hc.Roadmap, junction: str, commander: Person, bystander_offsets_m: list[tuple[float, float]],
                   bystander_looks: list[str]) -> Scene:
    """The commander at the junction's worker stand (road.stand) and bystanders at the given (dx, dz) offsets from it.
    The offsets are the caller's choice: none is built in."""
    if len(bystander_offsets_m) != len(bystander_looks):
        raise ValueError("one look per bystander offset")
    sx, sz, _ = road.stand(junction)
    commander.x, commander.z, commander.role = sx, sz, "commander"
    others = [Person(commander.id + 1 + i, sx + dx, sz + dz, look)
              for i, ((dx, dz), look) in enumerate(zip(bystander_offsets_m, bystander_looks))]
    return Scene([commander] + others)


class VisionSim:
    """Synthetic 360 and pan-tilt perception of a Scene, from one seeded generator."""

    def __init__(self, scene: Scene, cfg: SimConfig, gcfg: GestureSimConfig, seed: int = 1):
        self.scene, self.cfg, self.g = scene, cfg, gcfg
        self.rng = random.Random(seed)
        for cmd, wrong in gcfg.confusion.items():
            if cmd in wrong or any(w not in COMMANDS for w in wrong) or not wrong:
                raise ValueError(f"confusion[{cmd}] must list other commands from {COMMANDS}")

    def detect(self, x: float, z: float, yaw: float) -> list[dict]:
        out = []
        for p in self.scene.people:
            dist = math.hypot(p.x - x, p.z - z)
            if dist <= self.cfg.detection_range_m and self.rng.random() < self.cfg.p_detect:
                b = hc.wrap(hc.yaw_to(x, z, p.x, p.z) - yaw) + self.rng.gauss(0, self.cfg.bearing_sigma_deg)
                d = max(0.1, dist + self.cfg.distance_bias_m + self.rng.gauss(0, self.cfg.distance_sigma_m))
                wx, wz = hc.world_point(x, z, yaw, b, d)
                out.append({"id": p.id, "x": wx, "z": wz, "distance_m": d, "bearing_deg": b})
        return out

    def read(self, t: float, x: float, z: float, yaw: float, pan_deg: float) -> dict:
        """One pan-tilt reading: {"person_id", "command", "angle_deg"}; person_id -1 and command NONE when nobody is in
        view; angle_deg is None unless the reading is POINT. pan_deg > 0 = camera turned left of the robot's forward."""
        cam = yaw - pan_deg
        best, best_off = None, math.inf
        for p in self.scene.people:
            off = abs(hc.wrap(hc.yaw_to(x, z, p.x, p.z) - cam))
            if math.hypot(p.x - x, p.z - z) <= self.cfg.gesture_range_m and off <= self.cfg.gesture_half_fov_deg and off < best_off:
                best, best_off = p, off
        none = {"person_id": -1 if best is None else best.id, "command": "NONE", "angle_deg": None}
        if best is None:
            return none
        s = best.state(t)
        shown = s["command"]
        if shown == "NONE" or self.rng.random() >= self.g.coverage.get(shown, 1.0):
            return none
        command = shown
        if self.rng.random() >= self.g.accuracy.get(shown, 1.0):
            command = self.rng.choice(self.g.confusion[shown])
        angle = None
        if command == "POINT":
            if s["world_angle_deg"] is not None and command == shown:
                angle = hc.wrap(hc.wrap(s["world_angle_deg"] - yaw) + self.rng.gauss(0, self.g.point_angle_sigma_deg))
            else:
                angle = self.rng.uniform(-180.0, 180.0)
        return {"person_id": best.id, "command": command, "angle_deg": angle}


def simulate_ask(scene: Scene, cfg: SimConfig, gcfg: GestureSimConfig, robot_xz: tuple[float, float], robot_yaw_deg: float,
                 t0: float, duration_s: float, truth_dt_s: float, seed: int = 1) -> dict:
    """A robot standing still at robot_xz, its pan-tilt camera aimed at the commander, for duration_s: pan-tilt readings
    (with frame_index and time_s, after gesture_latency_s), 360 detections, the frames' headers and the truth rows
    (every truth_dt_s, all people). Times are Unity time starting at t0. truth_dt_s is the caller's choice."""
    x, z = robot_xz
    sim = VisionSim(scene, cfg, gcfg, seed)
    c = scene.commander
    pan = -hc.wrap(hc.yaw_to(x, z, c.x, c.z) - robot_yaw_deg)
    pose = {"x": x, "z": z, "yaw_deg": robot_yaw_deg}
    frames, readings, detections, truth = [], [], [], []
    n_pan = int(duration_s * cfg.frame_pan_hz + 1e-9)
    for i in range(n_pan):
        t = round(t0 + i / cfg.frame_pan_hz, 6)
        frames.append({"frame_index": i, "time_s": t, "pose": dict(pose)})
        readings.append({"frame_index": i, "time_s": t, "available_s": round(t + cfg.gesture_latency_s, 6),
                         **sim.read(t, x, z, robot_yaw_deg, pan)})
    for i in range(int(duration_s * cfg.frame_360_hz + 1e-9)):
        t = round(t0 + i / cfg.frame_360_hz, 6)
        detections.append({"time_s": t, "available_s": round(t + cfg.people_latency_s, 6),
                           "people": sim.detect(x, z, robot_yaw_deg)})
    for i in range(int(duration_s / truth_dt_s + 1e-9)):
        truth += scene.truth_rows(round(t0 + i * truth_dt_s, 6), robot_yaw_deg)
    return {"pan_deg": pan, "frames": frames, "readings": readings, "detections": detections, "truth_rows": truth}
