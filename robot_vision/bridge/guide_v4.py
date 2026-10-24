"""Protocol 3 guide with the v4 controller (hri_control_v4.ControllerV4): bridge/guide.py's GuideController with the v4
tick input (pan-tilt people readings, rendered field of view) and the v4 HUD fields. Writes v4_log.jsonl next to
decisions.csv: one row per new pan-tilt frame read in the READ state (people, readings, commander choice with reasons,
label, resolution, zoom), which hri_eval_dev_v4.py scores against truth.jsonl."""

from __future__ import annotations

import json

import hri_control as hc
import hri_control_v4 as hv
from bridge.guide import GuideController


class GuideControllerV4(GuideController):
    def __init__(self, controller: hv.ControllerV4, worker, out_dir, log_every: int = 2, route: str = "Task2",
                 hud_cfg: dict | None = None):
        super().__init__(controller, worker, out_dir, log_every, route, protocol_version=3, hud_cfg=hud_cfg)
        self._v4_file = None
        if self.out is not None:
            self._v4_file = (self.out / "v4_log.jsonl").open("x", encoding="utf-8", buffering=1)

    def close(self) -> None:
        super().close()
        if self._v4_file is not None:
            self._v4_file.close()

    def _tick_input(self, h: dict) -> hv.TickInputV4:
        pose = h["pose"]
        snap = self.worker.snapshot() if self.worker is not None else {}
        v4 = self.worker.snapshot_v4() if self.worker is not None and hasattr(self.worker, "snapshot_v4") else {}
        people = []
        fp = snap.get("people_pose")
        unknown = self.c.s.get("unknown_person_distance_m", 1.0)
        for q in snap.get("people", []) if fp else []:
            d = q["distance_m"] if q.get("distance_m", -1) >= 0 else unknown
            x, z = hc.world_point(fp["x"], fp["z"], fp["yaw_deg"], q["bearing_deg"], d)
            people.append({"x": x, "z": z, "distance_m": d, "bearing_deg": q["bearing_deg"], "track_id": q.get("track_id", -1)})
        target = (h["nav_target_x"], h["nav_target_z"]) if h.get("nav_has_target") else None
        corners = [(c["x"], c["z"]) for c in h.get("nav_corners", [])] if h.get("nav_status") == "complete" else []
        return hv.TickInputV4(time_s=h["time_s"], x=pose["x"], z=pose["z"], yaw_deg=pose["yaw_deg"], v=h["v"], omega=h["omega"],
                              nav_corners=corners, nav_target=target, people=people, people_time_s=snap.get("people_time_s"),
                              persons=v4.get("persons", []), persons_time_s=v4.get("persons_time_s"),
                              fov_deg=v4.get("fov_deg"), pan_deg=v4.get("pan_deg", 0.0))

    def _hud(self, cmd, inp, snap: dict) -> dict:
        """Phase 1 fields from the people of the 360 camera, then the v4 fields; the commander is marked in the people list."""
        hud = super()._hud(cmd, inp, snap)
        extra = getattr(cmd, "hud", None) or {}
        hud.update(extra)
        for q in hud["people"]:
            q["is_commander"] = bool(extra) and q["id"] == extra.get("commander_id", -1) and q["id"] >= 0
        return hud

    def on_message(self, msg):
        reply = super().on_message(msg)
        if self._v4_file is not None:
            for row in self.c.pop_frame_log():
                self._v4_file.write(json.dumps({"trial": self.trial, **row}, separators=(",", ":")) + "\n")
        return reply
