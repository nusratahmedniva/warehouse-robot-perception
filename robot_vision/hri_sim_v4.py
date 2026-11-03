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

Phase 3: SimulatorV4 runs whole v4 trials end to end (hri_control_v4.ControllerV4 against a kinematic robot, a commander
and bystanders at each junction, synthetic POINT / WAIT / STOP readings in the reader's output format, zoom on or off),
logging the frame log and truth rows a real run would produce. The perception it simulates is at the level of the
reader's OUTPUT (gesture_motion.Reading per person), not pixels; the reader itself is tested on synthetic keypoints.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, field

import commander_v4 as cm
import gesture_motion as gm
import hri_control as hc
import hri_control_v4 as hv
from hri_sim import SimConfig, _ramp

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
    amplitude: float = 1.0                      # wrist path of the swing in torso lengths (the commander rule compares them)

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
    facing: bool = True                          # facing the robot (a bystander may look away)
    extra_episodes: list = field(default_factory=list)   # later gestures of the same person (e.g. WAIT, then POINT)

    def state(self, t: float) -> dict:
        """What the person shows at t: phase, true command, arm, clip, the world POINT angle (None if not POINT), the
        wrist path amplitude and the seconds since the gesturing phase began (None outside gesturing / holding).
        While gesturing the pointed angle ramps linearly from 0 (world +Z) to the final angle: a placeholder shape, not a
        model of real arms. The first episode that is not idle decides."""
        idle = {"phase": "idle", "command": "NONE", "arm": "none", "clip": "", "world_angle_deg": None,
                "amplitude": 0.0, "since_gesture_s": None, "hold_age_s": 0.0}
        eps = ([self.episode] if self.episode is not None else []) + list(self.extra_episodes)
        for e in eps:
            phase, f = e.phase(t)
            if phase == "idle":
                continue
            if phase not in GESTURING_PHASES:
                return {**idle, "phase": phase}
            angle = None
            if e.command == "POINT":
                angle = e.world_angle_deg * (f if phase == "gesturing" else 1.0)
            since = f * e.gesturing_s if phase == "gesturing" else e.gesturing_s + f * e.hold_s
            return {"phase": phase, "command": e.command, "arm": e.arm, "clip": e.clip, "world_angle_deg": angle,
                    "amplitude": e.amplitude, "since_gesture_s": since,
                    "hold_age_s": f * e.hold_s if phase == "holding" else 0.0}
        return idle


@dataclass
class GestureSimConfig:
    coverage: dict = field(default_factory=dict)        # command -> P(reading is not NONE); default 1
    accuracy: dict = field(default_factory=dict)        # command -> P(correct | not NONE); default 1
    point_angle_sigma_deg: float = 0.0
    crosscheck_accuracy: float | None = None    # None: no hand world landmarks; else P(the cross-check prefers the TRUE depth reading)
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


# ---------------------------------------------------------------- Phase 3: reader-level perception and whole trials

def _wrap(a: float) -> float:
    return hc.wrap(a)


@dataclass
class SceneSpec:
    """What stands at each junction and how it behaves. Times in seconds; none is a tuned value."""
    start_delay_s: float = 0.5
    gesturing_s: float = 0.5
    hold_s: float = 3.0
    returning_s: float = 0.5
    bystander_offsets_m: list = field(default_factory=list)      # (dx, dz) from the commander's stand
    bystander_looks: list = field(default_factory=list)
    bystander_facing: list = field(default_factory=list)         # per bystander; missing = facing
    commander_look: str = "placeholder_look_dev_1"
    clips: dict = field(default_factory=lambda: {"POINT": "placeholder_point_dev_1", "WAIT": "placeholder_wait_dev_1",
                                                  "STOP": "placeholder_stop_dev_1"})     # animation clip names (the placeholder development names of the v4 split config)
    arm: str = "right"
    wait_first_s: float = 0.0                                    # the commander shows WAIT this long, then the POINT
    distractors: list = field(default_factory=list)              # (bystander index, command, seconds after the ask, world angle | None)
    early_distractors: list = field(default_factory=list)        # (bystander index, command, seconds after the people appear, world angle | None, hold s)
    stop: dict | None = None                                     # {"who": "commander" | bystander index, "after_ask_s", "hold_s"}


class ReaderLevelVision(VisionSim):
    """VisionSim that returns what the v4 reader would output for every person in the pan-tilt view (gesture_motion.Reading
    inside commander_v4.PersonReading), with the reader's timing: POINT and WAIT only once the pose has been held for
    hold_min_s, STOP after stop_window_s. Boxes follow the pinhole geometry of the current field of view."""

    HAND_H_M, HAND_W_M, ARM_W_M, ARM_H_M = 0.19, 0.12, 0.8, 0.5
    FRAME_W, FRAME_H = 730, 530

    def __init__(self, scene, cfg, gcfg, reader_cfg: dict, seed: int = 1):
        super().__init__(scene, cfg, gcfg, seed)
        self.rc = reader_cfg

    def _degrade(self, shown: str) -> str:
        if self.rng.random() >= self.g.coverage.get(shown, 1.0):
            return "NONE"
        if self.rng.random() >= self.g.accuracy.get(shown, 1.0):
            return self.rng.choice(self.g.confusion[shown])
        return shown

    def _point(self, true_world, cam_yaw: float, robot_yaw: float, shown: str, command: str) -> gm.PointEstimate:
        if true_world is not None and command == shown:
            w = _wrap(true_world + self.rng.gauss(0, self.g.point_angle_sigma_deg))
        else:
            w = self.rng.uniform(-180.0, 180.0)             # a made-up angle: the reading is a wrong class
        alpha = _wrap(w - cam_yaw)
        w_other = _wrap(cam_yaw + _wrap(180.0 - alpha))     # the other depth reading (mirror about the image plane)
        world = {"away": w, "toward": w_other} if abs(alpha) < 90 else {"away": w_other, "toward": w}
        rel = {k: _wrap(v - robot_yaw) for k, v in world.items()}
        cc = {"available": False, "prefers": None, "diff_deg": {}, "why": "simulated, no hand world landmarks"}
        if self.g.crosscheck_accuracy is not None and true_world is not None and command == shown:
            true_family = "away" if abs(alpha) < 90 else "toward"
            other = "toward" if true_family == "away" else "away"
            cc = {"available": True, "diff_deg": {}, "why": "simulated",
                  "prefers": true_family if self.rng.random() < self.g.crosscheck_accuracy else other}
        return gm.PointEstimate(0.0, 0.0, world, rel, True, 10, cc)

    def person_readings(self, t: float, x: float, z: float, yaw: float, pan_deg: float, fov_deg: float) -> list:
        half_fov = math.degrees(math.atan(math.tan(math.radians(fov_deg / 2.0)) * self.FRAME_W / self.FRAME_H))
        reach = self.cfg.gesture_range_m
        cam = yaw - pan_deg
        fx = (self.FRAME_H / 2.0) / math.tan(math.radians(fov_deg / 2.0))
        out = []
        for p in self.scene.people:
            dist = math.hypot(p.x - x, p.z - z)
            off = _wrap(hc.yaw_to(x, z, p.x, p.z) - cam)
            if dist > reach or abs(off) > half_fov:
                continue
            s = p.state(t)
            shown = s["command"]
            raised = shown != "NONE"
            moving = raised and s["phase"] == "gesturing"
            ready = (shown in ("POINT", "WAIT") and s["phase"] == "holding" and s["hold_age_s"] >= self.rc["window"]["hold_min_s"]) or \
                    (shown == "STOP" and s["since_gesture_s"] is not None and s["since_gesture_s"] >= self.rc["window"]["stop_window_s"])
            command = self._degrade(shown) if ready else "NONE"
            r = gm.Reading(command, 0.9 if command != "NONE" else 0.0, "simulated", t, arm=s["arm"] if raised else None,
                           frame_class=shown, moving=moving, raised=raised, hold_s=s["hold_age_s"], valid_frames=10, n_frames=10)
            r.arms = {s["arm"] if raised else "right": {"raised": raised, "path": s["amplitude"] if moving else 0.0, "moving": moving}}
            if command == "POINT":
                r.point = self._point(s["world_angle_deg"], cam, yaw, shown, command)
            if raised:
                u = self.FRAME_W / 2.0 + fx * math.tan(math.radians(off))
                scale = fx / max(dist, 0.1)
                hw, hh, aw, ah = (self.HAND_W_M * scale, self.HAND_H_M * scale, self.ARM_W_M * scale, self.ARM_H_M * scale)
                cy = self.FRAME_H / 2.0
                r.hand_box = (u - hw / 2, cy - hh / 2, u + hw / 2, cy + hh / 2)
                r.arm_box = (u - aw / 2, cy - ah / 2, u + aw / 2, cy + ah / 2)
                r.frame_wh, r.fov_deg = (self.FRAME_W, self.FRAME_H), fov_deg
            out.append(cm.PersonReading(p.id, _wrap(hc.yaw_to(x, z, p.x, p.z) - yaw), p.facing,
                                        "facing" if p.facing else "turned away (simulated)", r, None, dist))
        return out


class SimulatorV4:
    """Whole v4 trials: ControllerV4 against a kinematic robot with the hri_sim.py limits, a commander and bystanders at
    every junction (SceneSpec), and ReaderLevelVision. The commander starts gesturing when the robot asks (start delay,
    swing, hold, return) and points along the branch that leads to goal B; the controller never sees B. The field of view
    the controller commands is the one rendered (no lag)."""

    def __init__(self, controller: hv.ControllerV4, cfg: SimConfig, gcfg: GestureSimConfig, spec: SceneSpec,
                 seed: int = 1, truth_dt_s: float = 0.1, reader_cfg: dict | None = None):
        self.c, self.cfg, self.g, self.spec = controller, cfg, gcfg, spec
        self.road = controller.road
        self.seed, self.truth_dt = seed, truth_dt_s
        self.reader_cfg = reader_cfg or gm.load_config()

    def _scene_at(self, junction: str) -> Scene:
        sp = self.spec
        cmdr = Person(1, 0.0, 0.0, sp.commander_look, "commander")
        scene = junction_scene(self.road, junction, cmdr, [tuple(o) for o in sp.bystander_offsets_m], list(sp.bystander_looks))
        for i, q in enumerate(scene.people[1:]):
            q.facing = sp.bystander_facing[i] if i < len(sp.bystander_facing) else True
        return scene

    def _stage_ask(self, scene: Scene, t: float, junction: str, goal: str) -> None:
        sp = self.spec
        road = self.road
        jx, jz = road.pos(junction)
        correct = road.command_toward(junction, goal)
        if correct == "NONE":                                   # B is not reachable from here (a wrong branch was taken)
            return
        w = hc.yaw_to(jx, jz, *road.pos(road.next(junction, correct)))
        cm_ = scene.commander
        eps = []
        t0 = t
        if sp.wait_first_s > 0:
            e = Episode("WAIT", t0, sp.start_delay_s, sp.gesturing_s, sp.wait_first_s, sp.returning_s, arm=sp.arm,
                        clip=sp.clips["WAIT"])
            eps.append(e)
            t0 = e.end() + 0.2
        eps.append(Episode("POINT", t0, sp.start_delay_s, sp.gesturing_s, sp.hold_s, sp.returning_s, arm=sp.arm,
                           clip=sp.clips["POINT"], world_angle_deg=w))
        cm_.episode, cm_.extra_episodes = eps[0], eps[1:]
        for bi, command, dt, angle in sp.distractors:
            q = scene.people[1 + bi]
            q.episode = Episode(command, t + dt, sp.start_delay_s, sp.gesturing_s, sp.hold_s, sp.returning_s, arm="left",
                                clip=sp.clips[command], world_angle_deg=angle if command == "POINT" else None)
        if sp.stop:
            who = scene.commander if sp.stop["who"] == "commander" else scene.people[1 + sp.stop["who"]]
            stop = Episode("STOP", t + sp.stop["after_ask_s"], 0.0, 0.3, sp.stop["hold_s"], 0.3, arm="left", clip=sp.clips["STOP"])
            if who.episode is not None:
                who.extra_episodes = [who.episode] + who.extra_episodes
            who.episode = stop

    def run(self, goal: str) -> dict:
        cfg, road, c = self.cfg, self.road, self.c
        rng_seed = self.seed
        x, z = road.pos(road.start)
        first = road.only_next(road.start)
        yaw = hc.yaw_to(x, z, *road.pos(first))
        v = w = 0.0
        t = travelled = 0.0
        scenes: dict[str, Scene] = {}
        scene: Scene | None = None
        vision: ReaderLevelVision | None = None
        shown_at: dict[str, str] = {}
        staged_asks: set = set()
        latest_people, latest_people_t = [], None
        latest_persons, latest_persons_t, latest_fov, latest_pan = [], None, 60.0, 0.0
        pend_people, pend_persons = [], []
        next_360 = next_pan = 0.0
        cmd = hv.CommandV4()
        fov_now = 60.0
        truth, frames, hud_log = [], [], []
        next_truth = 0.0
        c.begin(t)
        closest, collided = math.inf, False
        while t < cfg.timeout_s:
            if scene is not None:
                if t >= next_360:
                    next_360 += 1.0 / cfg.frame_360_hz
                    det = [{**{k: q[k] for k in ("x", "z", "distance_m", "bearing_deg")}, "track_id": q["id"]}
                           for q in vision.detect(x, z, yaw)]
                    pend_people.append((t + cfg.people_latency_s, t, det))
                if t >= next_pan:
                    next_pan += 1.0 / cfg.frame_pan_hz
                    frames.append({"frame_index": len(frames), "time_s": round(t, 4), "pose": {"x": x, "z": z, "yaw_deg": yaw}})
                    pend_persons.append((t + cfg.gesture_latency_s, t, vision.person_readings(t, x, z, yaw, cmd.pan_deg, fov_now),
                                         fov_now, cmd.pan_deg))
                if t >= next_truth:
                    next_truth += self.truth_dt
                    truth += scene.truth_rows(t, yaw)
            while pend_people and pend_people[0][0] <= t:
                _, latest_people_t, latest_people = pend_people.pop(0)
            while pend_persons and pend_persons[0][0] <= t:
                _, latest_persons_t, latest_persons, latest_fov, latest_pan = pend_persons.pop(0)
            target = (cmd.target_x, cmd.target_z) if cmd.has_target else None
            inp = hv.TickInputV4(time_s=t, x=x, z=z, yaw_deg=yaw, v=v, omega=w,
                                 nav_corners=[(x, z), target] if target else [], nav_target=target, people=latest_people,
                                 people_time_s=latest_people_t, persons=latest_persons, persons_time_s=latest_persons_t,
                                 fov_deg=latest_fov, pan_deg=latest_pan)
            cmd = c.step(inp)
            fov_now = cmd.vertical_fov_deg if cmd.vertical_fov_deg > 0 else 60.0
            hud_log.append({"t": round(t, 3), "state": cmd.state, "fov_cmd": cmd.vertical_fov_deg, **cmd.hud})
            if cmd.has_target:                                   # stage the people at the junction being approached
                for j in road.nodes:
                    if road.kind(j) == "junction" and j not in scenes and math.hypot(
                            cmd.target_x - road.pos(j)[0], cmd.target_z - road.pos(j)[1]) < 0.5:
                        scenes[j] = self._scene_at(j)
                        scene = scenes[j]
                        shown_at[j] = road.command_toward(j, goal)
                        vision = ReaderLevelVision(scene, cfg, self.g, self.reader_cfg, rng_seed * 1000 + len(scenes))
                        for bi, command, dt, angle, hold in self.spec.early_distractors:      # they gesture before any question
                            scene.people[1 + bi].episode = Episode(
                                command, t + dt, 0.2, 0.3, hold, 0.3, arm="left", clip=self.spec.clips[command],
                                world_angle_deg=angle if command == "POINT" else None)
                        pend_people, pend_persons, latest_people, latest_persons = [], [], [], []
                        latest_people_t = latest_persons_t = None
                        next_360 = next_pan = next_truth = t
            if c.state == "ask" and scene is not None and (c.node, c.ask_serial) not in staged_asks:
                staged_asks.add((c.node, c.ask_serial))
                self._stage_ask(scene, t, c.node, goal)
            v = _ramp(v, max(-cfg.max_speed_mps, min(cfg.max_speed_mps, cmd.v)), cfg.max_accel_mps2, cfg.decel_mps2, cfg.dt)
            w = _ramp(w, max(-cfg.max_angular_speed_radps, min(cfg.max_angular_speed_radps, cmd.omega)),
                      cfg.max_angular_accel_radps2, cfg.max_angular_accel_radps2, cfg.dt)
            yaw = hc.wrap(yaw - math.degrees(w * cfg.dt))
            nx, nz = x + math.sin(math.radians(yaw)) * v * cfg.dt, z + math.cos(math.radians(yaw)) * v * cfg.dt
            travelled += math.hypot(nx - x, nz - z)
            x, z = nx, nz
            t += cfg.dt
            if scene is not None:
                for q in scene.people:
                    d = math.hypot(q.x - x, q.z - z)
                    closest = min(closest, d)
                    collided |= d < cfg.collision_radius_m
            if collided or (c.finished and abs(v) < 0.01):
                break
        gx, gz = road.pos(goal)
        final = math.hypot(gx - x, gz - z)
        if collided:
            outcome, reason = "FAILURE", "collision"
        elif not c.finished:
            outcome, reason = "FAILURE", "timeout"
        elif c.state == "aborted":
            outcome, reason = "FAILURE", "aborted"
        elif final <= cfg.success_radius_m:
            outcome, reason = "SUCCESS", "none"
        else:
            outcome, reason = "FAILURE", "wrong_goal"
        summ = c.summary()
        for j in summ["junctions"]:
            j["shown"] = shown_at.get(j["junction"], "unknown")
        return {"goal": goal, "outcome": outcome, "failure_reason": reason, "final_distance_m": round(final, 3),
                "time_s": round(t, 2), "travelled_m": round(travelled, 2), "closest_person_m": round(closest, 2),
                "frame_log": list(c.frame_log), "hud_log": hud_log, "truth_rows": truth, "frames": frames, **summ}


def export_session(results: list[dict], out_root, zoom_enabled: bool, seed: int = 1, name: str = "sim",
                   trial_gap_s: float = 1000.0, mode: str = "development", task: str = "Task2") -> tuple:
    """Write simulated trials as the two run folders a real session leaves, so hri_eval_dev_v4.py and hri_analysis_v4.py can
    be tried (and tested) on them. Unity's trials_<name>/: session.json, truth_run###.json (outcome, collisions, closest
    person, times), run_###/truth.jsonl and run.json. The bridge's bridge_<name>/: v4_log.jsonl, python_trial_###.json,
    decisions.csv and perception.csv (fixed illustrative round-trip and inference times), config_used/control.json. Trial k's
    clock starts at (k - 1) * trial_gap_s, as one Unity session's Time.time keeps running. Returns (unity, bridge)."""
    import csv
    import json
    from pathlib import Path
    root = Path(out_root)
    u, b = root / f"trials_{name}", root / f"bridge_{name}"
    u.mkdir(parents=True)
    (b / "config_used").mkdir(parents=True)
    base, v4 = hv.load_control()
    v4["zoom"]["enabled"] = zoom_enabled
    (b / "config_used" / "control.json").write_text(json.dumps(v4, indent=2) + "\n", encoding="utf-8")
    (u / "session.json").write_text(json.dumps({"task": task, "mode": mode, "seed": seed,
                                                "endpoints": ["E1", "E2", "E3", "E4"]}), encoding="utf-8")
    road = hc.Roadmap(hc.load_json("configs/roadmap.json"))
    perc_rows, dec_rows = [], []
    with (b / "v4_log.jsonl").open("w", encoding="utf-8") as log:
        for i, r in enumerate(results, 1):
            off = (i - 1) * trial_gap_s
            ax, az = road.pos(road.start)
            gx, gz = road.pos(r["goal"])
            col = r["failure_reason"] == "collision"
            (u / f"truth_run{i:03d}.json").write_text(json.dumps({
                "trial": i, "task": "Task2", "mode": "development", "seed": seed, "a_name": road.start, "b_name": r["goal"],
                "a_x": ax, "a_z": az, "b_x": gx, "b_z": gz, "outcome": r["outcome"], "failure_reason": r["failure_reason"],
                "final_distance_to_b_m": r["final_distance_m"], "straight_line_m": round(math.hypot(gx - ax, gz - az), 3),
                "travelled_m": r["travelled_m"], "total_s": r["time_s"], "t_start": off, "t_end": off + r["time_s"],
                "collisions": int(col), "human_collisions": int(col), "closest_human_m": r["closest_person_m"]}), encoding="utf-8")
            run = u / f"run_{i:03d}"
            run.mkdir()
            rows = [{**x, "time_s": round(x["time_s"] + off, 6)} for x in r["truth_rows"]]
            (run / "truth.jsonl").write_text("".join(json.dumps(x) + "\n" for x in rows), encoding="utf-8")
            (run / "run.json").write_text(json.dumps({"run_start_s": off}), encoding="utf-8")
            for row in r["frame_log"]:
                log.write(json.dumps({"trial": i, **row, "t": round(row["t"] + off, 4), "ctrl_t": round(row["ctrl_t"] + off, 4)}) + "\n")
            summary = {k: r[k] for k in ("state", "abort_reason", "junctions", "step_s", "trace")}
            (b / f"python_trial_{i:03d}.json").write_text(json.dumps({**summary, "trial": i}), encoding="utf-8")
            for k in range(5):
                dec_rows.append({"trial": i, "time_s": round(off + k * 0.1, 3), "rtt_ms": 0.8 + 0.1 * k, "watchdog_count": 0})
            perc_rows += [{"type": "frame_360", "time_s": off + 1.0, "decode_ms": 5.0, "model_ms": "yolo11s-pose/cam360:200.0",
                           "total_ms": 210.0},
                          {"type": "frame_pan_tilt", "time_s": off + 1.1, "decode_ms": 3.0,
                           "model_ms": "yolo11s-pose/gesture:60.0;mediapipe/hands:20.0;reader/window:0.5", "total_ms": 85.0}]
    for name_, rows_ in (("decisions.csv", dec_rows), ("perception.csv", perc_rows)):
        with (b / name_).open("w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(rows_[0]))
            w.writeheader()
            w.writerows(rows_)
    return u, b


def two_view_study(goals=("E1", "E2", "E3"), sigmas=(0.0,), shifts=(0.4,), seeds=range(1, 11), tolerance_deg=None,
                   two_view: bool = True) -> list[dict]:
    """Simulated trials at J1 (E1 = FORWARD, E2 = RIGHT, E3 = LEFT, no bystanders) for each angle noise (deg) and re-ask shift
    (m): how many asks were ambiguous (the second view started), how many of those the second view resolved to the
    right branch, to a wrong branch, or left unresolved (ask again, abort). A property of the simulator's geometry and
    noise model, not a measurement."""
    import commander_v4
    rows = []
    for sigma in sigmas:
        for shift in shifts:
            for goal in goals:
                c = {"trials": 0, "ambiguous": 0, "resolved_right": 0, "resolved_wrong": 0, "unresolved": 0, "no_ambiguity_right": 0,
                     "no_ambiguity_wrong": 0}
                for seed in seeds:
                    base, v4 = hv.load_control()
                    base["dialog"]["reask_shift_m"] = shift
                    v4["dialog"]["two_view_enabled"] = two_view
                    if tolerance_deg is not None:
                        v4["dialog"]["view_consistency_deg"] = tolerance_deg
                    ctrl = hv.ControllerV4(base, v4, commander_v4.load_config(), hc.Roadmap(hc.load_json("configs/roadmap.json")))
                    r = SimulatorV4(ctrl, SimConfig(), GestureSimConfig(point_angle_sigma_deg=sigma), SceneSpec(), seed).run(goal)
                    j = r["junctions"][0] if r["junctions"] else {}
                    ok = j.get("result") == "accepted" and j.get("read") == j.get("shown")
                    wrong = j.get("result") == "accepted" and not ok
                    c["trials"] += 1
                    if any("second_view" in x for x in r["trace"]):
                        c["ambiguous"] += 1
                        c["resolved_right" if ok else "resolved_wrong" if wrong else "unresolved"] += 1
                    else:
                        c["no_ambiguity_right" if ok else "no_ambiguity_wrong"] += bool(ok or wrong)
                rows.append({"goal": goal, "branch": {"E1": "FORWARD", "E2": "RIGHT", "E3": "LEFT"}.get(goal, goal),
                             "sigma_deg": sigma, "shift_m": shift, **c})
    return rows
