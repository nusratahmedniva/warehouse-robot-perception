"""Step 5 simulator: runs hri_control.Controller against a kinematic robot and synthetic perception, without Unity.

World: robot.json drive limits (acceleration, braking, turn rate), the roadmap, a straight line as the NavMesh path
(the warehouse aisles are open), and the scenario side exactly like the Unity trial runner: the worker stands at the
junction the robot is heading to and shows the command toward goal B (Roadmap.command_toward). Goal B and the
worker's true position live only here; the controller sees them only through the synthetic perception:
- 360 deg camera at frame_360_hz: the worker (and any extra person) is detected with probability p_detect per frame
  within detection_range_m, with bearing and distance noise, after people_latency_s;
- pan-tilt camera at frame_pan_hz: if the worker is in the camera's field of view and within gesture_range_m, the
  shown command is read with probability coverage[cmd] (else NONE), correctly with probability accuracy[cmd] (else
  the neighbouring direction), after gesture_latency_s.

All randomness comes from one seeded generator, so a run is reproducible.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, field

import hri_control as hc

NEIGHBOUR = {"LEFT": "FORWARD_LEFT", "FORWARD_LEFT": "LEFT", "FORWARD": "FORWARD_LEFT",
             "FORWARD_RIGHT": "RIGHT", "RIGHT": "FORWARD_RIGHT"}


@dataclass
class SimConfig:
    dt: float = 0.05                    # telemetry period (20 Hz, as Unity sends it)
    frame_360_hz: float = 5.0
    frame_pan_hz: float = 10.0
    people_latency_s: float = 0.25      # capture -> result available (YOLO on the panorama)
    gesture_latency_s: float = 0.1
    p_detect: float = 1.0
    detection_range_m: float = 12.0
    distance_sigma_m: float = 0.0
    distance_bias_m: float = 0.0
    bearing_sigma_deg: float = 0.0
    gesture_range_m: float = 6.0
    gesture_half_fov_deg: float = 38.0  # 730 px wide, fx 458.99 -> 2 * atan(365 / 459) = 77 deg
    coverage: dict = field(default_factory=dict)   # shown -> P(reading is not NONE); default 1
    accuracy: dict = field(default_factory=dict)   # shown -> P(correct | not NONE); default 1
    timeout_s: float = 240.0
    success_radius_m: float = 0.3
    collision_radius_m: float = 0.65    # robot centre to person centre
    max_speed_mps: float = 1.0
    max_accel_mps2: float = 0.5
    decel_mps2: float = 0.5
    max_angular_speed_radps: float = 1.0
    max_angular_accel_radps2: float = 2.0
    stop_gesture: tuple | None = None   # (t_start, t_end): the worker shows STOP in this window
    intruder: dict | None = None        # {"t": s, "x", "z"}: a second person standing still from t on
    blind_spot: dict | None = None      # {"x", "z", "r"}: gestures read NONE while the robot is within r of (x, z)


def _ramp(cur: float, target: float, up: float, down: float, dt: float) -> float:
    rate = up if abs(target) > abs(cur) and target * cur >= 0 else down
    step = rate * dt
    return target if abs(target - cur) <= step else cur + math.copysign(step, target - cur)


class Simulator:
    def __init__(self, controller: hc.Controller, cfg: SimConfig, seed: int = 1):
        self.c, self.cfg = controller, cfg
        self.road = controller.road
        self.rng = random.Random(seed)

    def run(self, goal: str) -> dict:
        cfg, road, c = self.cfg, self.road, self.c
        x, z = road.pos(road.start)
        first = road.only_next(road.start)
        yaw = hc.yaw_to(x, z, *road.pos(first))
        v = w = 0.0
        t = 0.0
        travelled = 0.0
        shown_at: dict[str, str] = {}
        worker = self._place(first, goal, shown_at) if road.kind(first) == "junction" else None
        pending_people, pending_gesture = [], []
        latest_people, latest_people_t, latest_gesture, latest_gesture_t = [], None, "NONE", None
        next_360, next_pan = 0.0, 0.0
        cmd = hc.Command()
        c.begin(t)
        closest = math.inf
        collided = False
        while t < cfg.timeout_s:
            # perception: capture frames, deliver after their latency
            people_now = self._people(t, worker)
            if t >= next_360:
                next_360 += 1.0 / cfg.frame_360_hz
                det = []
                for (px, pz) in people_now:
                    dist = math.hypot(px - x, pz - z)
                    if dist <= cfg.detection_range_m and self.rng.random() < cfg.p_detect:
                        b = hc.wrap(hc.yaw_to(x, z, px, pz) - yaw) + self.rng.gauss(0, cfg.bearing_sigma_deg)
                        de = max(0.1, dist + cfg.distance_bias_m + self.rng.gauss(0, cfg.distance_sigma_m))
                        wx, wz = hc.world_point(x, z, yaw, b, de)
                        det.append({"x": wx, "z": wz, "distance_m": de, "bearing_deg": b})
                pending_people.append((t + cfg.people_latency_s, t, det))
            if t >= next_pan:
                next_pan += 1.0 / cfg.frame_pan_hz
                pending_gesture.append((t + cfg.gesture_latency_s, t, self._read(t, x, z, yaw, cmd.pan_deg, worker)))
            while pending_people and pending_people[0][0] <= t:
                _, latest_people_t, latest_people = pending_people.pop(0)
            while pending_gesture and pending_gesture[0][0] <= t:
                _, latest_gesture_t, latest_gesture = pending_gesture.pop(0)

            path_target = (cmd.target_x, cmd.target_z) if cmd.has_target else None
            inp = hc.TickInput(time_s=t, x=x, z=z, yaw_deg=yaw, v=v, omega=w,
                               nav_corners=[(x, z), path_target] if path_target else [], nav_target=path_target,
                               people=latest_people, people_time_s=latest_people_t,
                               gesture=latest_gesture, gesture_time_s=latest_gesture_t)
            cmd = c.step(inp)
            # scenario: the worker moves to the junction the robot is heading to
            if cmd.has_target:
                for j in road.nodes:
                    if road.kind(j) == "junction" and j not in shown_at and math.hypot(cmd.target_x - road.pos(j)[0], cmd.target_z - road.pos(j)[1]) < 0.5:
                        worker = self._place(j, goal, shown_at)
            # robot kinematics (robot.json limits); omega > 0 = left -> Unity yaw decreases
            v = _ramp(v, max(-cfg.max_speed_mps, min(cfg.max_speed_mps, cmd.v)), cfg.max_accel_mps2, cfg.decel_mps2, cfg.dt)
            w = _ramp(w, max(-cfg.max_angular_speed_radps, min(cfg.max_angular_speed_radps, cmd.omega)),
                      cfg.max_angular_accel_radps2, cfg.max_angular_accel_radps2, cfg.dt)
            yaw = hc.wrap(yaw - math.degrees(w * cfg.dt))
            nx, nz = x + math.sin(math.radians(yaw)) * v * cfg.dt, z + math.cos(math.radians(yaw)) * v * cfg.dt
            travelled += math.hypot(nx - x, nz - z)
            x, z = nx, nz
            t += cfg.dt
            for (px, pz) in people_now:
                d = math.hypot(px - x, pz - z)
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
        s = c.summary()
        for j in s["junctions"]:
            j["shown"] = shown_at.get(j["junction"], "unknown")
        return {"goal": goal, "outcome": outcome, "failure_reason": reason, "final_distance_m": round(final, 3),
                "time_s": round(t, 2), "travelled_m": round(travelled, 2), "closest_person_m": round(closest, 2),
                **s}

    def _place(self, junction: str, goal: str, shown_at: dict):
        sx, sz, _ = self.road.stand(junction)
        shown_at[junction] = self.road.command_toward(junction, goal)
        return {"x": sx, "z": sz, "shown": shown_at[junction], "junction": junction}

    def _people(self, t: float, worker) -> list:
        out = [(worker["x"], worker["z"])] if worker else []
        it = self.cfg.intruder
        if it and t >= it["t"]:
            out.append((it["x"], it["z"]))
        return out

    def _read(self, t: float, x: float, z: float, yaw: float, pan_deg: float, worker) -> str:
        cfg = self.cfg
        if worker is None:
            return "NONE"
        shown = worker["shown"]
        if cfg.stop_gesture and cfg.stop_gesture[0] <= t <= cfg.stop_gesture[1]:
            shown = "STOP"
        if cfg.blind_spot and math.hypot(x - cfg.blind_spot["x"], z - cfg.blind_spot["z"]) <= cfg.blind_spot["r"]:
            return "NONE"                           # a view where the pose model fails, as in dev trial 8
        dist = math.hypot(worker["x"] - x, worker["z"] - z)
        cam_yaw = yaw - pan_deg                     # pan > 0 = left
        if dist > cfg.gesture_range_m or abs(hc.wrap(hc.yaw_to(x, z, worker["x"], worker["z"]) - cam_yaw)) > cfg.gesture_half_fov_deg:
            return "NONE"
        if shown == "NONE" or self.rng.random() >= cfg.coverage.get(shown, 1.0):
            return "NONE"
        if shown in NEIGHBOUR and self.rng.random() >= cfg.accuracy.get(shown, 1.0):
            return NEIGHBOUR[shown]
        return shown


def run_trials(goals: list[str], cfg: SimConfig, seed: int = 1) -> list[dict]:
    out = []
    for i, g in enumerate(goals):
        sim = Simulator(hc.make_controller(), cfg, seed=seed * 1000 + i)
        out.append(sim.run(g))
    return out
