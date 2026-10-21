"""Step 5 live: the hri_control state machine driving the Unity robot over the Step 2 bridge (mode 'guide').

Every telemetry message is answered with the controller's command (v, omega, pan, NavMesh target, state, screen
text). Trials come from the Unity trial runner (Step 7) through two telemetry fields: trial_index and trial_running.
A new index while running starts a new run at the roadmap start; trial_running false keeps the robot idle (v = 0,
pan 0). The controller never receives goal B: telemetry carries none (protocol.py rejects goal keys).

Logs in the server's run folder (Step 7 merges them with Unity's truth files):
- decisions.csv: one row per second telemetry message (0.1 s at 20 Hz) with the robot's state and commands,
  perception inputs, the Unity-measured round trip and the watchdog count;
- python_trial_###.json: per trial, the controller summary (states, per-step times, junction readings, abort reason).
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

import hri_control as hc

DECISION_FIELDS = ["trial", "time_s", "state", "x", "z", "yaw_deg", "v", "omega", "v_cmd", "omega_cmd", "pan_cmd_deg",
                   "has_target", "target_x", "target_z", "nav_status", "n_people", "people_time_s", "gesture",
                   "gesture_time_s", "safety", "screen_text", "rtt_ms", "watchdog_count", "collision_count"]


class GuideController:
    """route: the id of the controller's map (task_route.route_id), sent with every command so the Unity trial
    runner can refuse a session whose task needs another map. perception_ready (worker.ready) is sent with every
    command too; Unity starts trial 1 only after it is true."""

    def __init__(self, controller: hc.Controller, worker, out_dir: Path | None, log_every: int = 2,
                 route: str = "Task2"):
        self.c = controller
        self.worker = worker
        self.route = route
        self.ready_logged = False
        self.out = Path(out_dir) if out_dir is not None else None
        self.log_every = max(1, int(log_every))
        self.trial = -1
        self.running = False
        self.n = 0
        self.written: set[int] = set()
        self._csv_file = None
        if self.out is not None:
            self._csv_file = (self.out / "decisions.csv").open("x", newline="", encoding="utf-8", buffering=1)
            self._csv = csv.DictWriter(self._csv_file, fieldnames=DECISION_FIELDS)
            self._csv.writeheader()

    def on_connect(self) -> None:
        self.running = False
        self.trial = -1

    def close(self) -> None:
        if self._csv_file is not None:
            self._csv_file.close()

    def _tick_input(self, h: dict) -> hc.TickInput:
        pose = h["pose"]
        snap = self.worker.snapshot() if self.worker is not None else {}
        people = []
        fp = snap.get("people_pose")
        unknown = self.c.s.get("unknown_person_distance_m", 1.0)
        for q in snap.get("people", []) if fp else []:
            d = q["distance_m"] if q.get("distance_m", -1) >= 0 else unknown   # unknown distance: assume close
            x, z = hc.world_point(fp["x"], fp["z"], fp["yaw_deg"], q["bearing_deg"], d)
            people.append({"x": x, "z": z, "distance_m": d, "bearing_deg": q["bearing_deg"]})
        target = (h["nav_target_x"], h["nav_target_z"]) if h.get("nav_has_target") else None
        corners = [(c["x"], c["z"]) for c in h.get("nav_corners", [])] if h.get("nav_status") == "complete" else []
        return hc.TickInput(time_s=h["time_s"], x=pose["x"], z=pose["z"], yaw_deg=pose["yaw_deg"], v=h["v"],
                            omega=h["omega"], nav_corners=corners, nav_target=target, people=people,
                            people_time_s=snap.get("people_time_s"), gesture=snap.get("gesture", "NONE"),
                            gesture_time_s=snap.get("gesture_time_s"))

    def on_message(self, msg) -> dict | None:
        if msg.type in ("frame_360", "frame_pan_tilt"):
            if self.worker is not None:
                self.worker.submit(msg)
            return None
        if msg.type != "telemetry":
            return None
        h = msg.header
        trial, running = int(h.get("trial_index", -1)), bool(h.get("trial_running", False))
        if running and trial != self.trial:
            self._write_trial()                    # the previous trial, if it was cut short
            self.trial = trial
            self.c.begin(h["time_s"])
        if not running and self.running:
            self._write_trial()
        self.running = running
        inp = self._tick_input(h)
        cmd = self.c.step(inp) if running else hc.Command(state="idle")
        if running and self.c.finished:
            self._write_trial()
        self.n += 1
        if self._csv_file is not None and self.n % self.log_every == 0:
            self._csv.writerow({
                "trial": self.trial if running else -1, "time_s": round(inp.time_s, 3), "state": cmd.state,
                "x": round(inp.x, 3), "z": round(inp.z, 3), "yaw_deg": round(inp.yaw_deg, 2), "v": round(inp.v, 3),
                "omega": round(inp.omega, 3), "v_cmd": round(cmd.v, 3), "omega_cmd": round(cmd.omega, 3),
                "pan_cmd_deg": round(cmd.pan_deg, 2), "has_target": int(cmd.has_target),
                "target_x": round(cmd.target_x, 3), "target_z": round(cmd.target_z, 3),
                "nav_status": h.get("nav_status"), "n_people": len(inp.people), "people_time_s": inp.people_time_s,
                "gesture": inp.gesture, "gesture_time_s": inp.gesture_time_s, "safety": self.c.safety_reason if running else "",
                "screen_text": cmd.screen_text, "rtt_ms": h.get("rtt_ms"), "watchdog_count": h.get("watchdog_count"),
                "collision_count": h.get("collision_count")})
        ready = bool(getattr(self.worker, "ready", False))
        if ready and not self.ready_logged:
            self.ready_logged = True
            print(f"[bridge] perception ready (models warmed up, first frame of each camera processed); "
                  f"Unity may start trials. Map: {self.route}", flush=True)
        return {**cmd.to_message(), "route": self.route, "perception_ready": ready}

    def _write_trial(self) -> None:
        if self.trial < 0 or self.trial in self.written or self.out is None:
            return
        self.written.add(self.trial)
        s = self.c.summary()
        s.update(trial=self.trial, perception=getattr(self.worker, "label", "none"))
        (self.out / f"python_trial_{self.trial:03d}.json").write_text(json.dumps(s, indent=2) + "\n", encoding="utf-8")
