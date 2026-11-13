"""v4 perception worker for protocol 3 (bridge/perception.py unchanged): the 360 camera runs as in v3; the pan-tilt camera
runs hri_perception_v4.HriPerceptionV4.persons() and keeps the readings of everybody in view (snapshot_v4()).
Same threading model: one thread per camera, latest frame only, never inference on the asyncio loop.

Per-frame model-output log (P12, 2026-11-12): model_outputs.jsonl in the run folder, one compact JSON line per processed
camera frame (camera, time, frame index, pose; for the 360 every person's box, 17 keypoints with scores, track id, bearing,
distance and its source; for the pan-tilt also pan, tilt, field of view and intrinsics, every tracked body with its
keypoints and every hand with its 21 landmarks, world landmarks, label and score). It is what the calibration replays
(calibrate_v4.py). Written by this threaded worker only (perception_workers.mode 'threads'; the worker processes write none)."""

from __future__ import annotations

import json
import threading
import time
from pathlib import Path

from bridge.perception import PerceptionWorker

MODEL_OUTPUTS = "model_outputs.jsonl"


class PerceptionWorkerV4(PerceptionWorker):
    def __init__(self, perception, out_dir=None, verbose: bool = True):
        super().__init__(perception, out_dir, verbose)
        self._v4 = {"persons": [], "persons_time_s": None, "fov_deg": None, "pan_deg": 0.0, "tilt_deg": 0.0}
        self._mo_lock = threading.Lock()
        self._mo_file = (Path(out_dir) / MODEL_OUTPUTS).open("x", encoding="utf-8", buffering=1) if out_dir is not None else None

    def snapshot_v4(self) -> dict:
        with self._lock:
            return dict(self._v4)

    def close(self) -> None:
        super().close()
        if self._mo_file is not None:
            with self._mo_lock:
                self._mo_file.close()

    def _model_output(self, row: dict) -> None:
        if self._mo_file is None:
            return
        with self._mo_lock:
            if not self._mo_file.closed:
                self._mo_file.write(json.dumps(row, separators=(",", ":")) + "\n")

    @staticmethod
    def _frame_fields(cam: str, h: dict) -> dict:
        pose = h.get("pose", {})
        return {"cam": cam, "time_s": h.get("time_s"), "frame_index": h.get("frame_index"),
                "pose": {k: pose.get(k) for k in ("x", "z", "yaw_deg")}}

    def _process(self, kind: str, msg, skipped: int) -> float:
        if kind != "frame_pan_tilt":
            total = super()._process(kind, msg, skipped)
            h = msg.header
            self._model_output({**self._frame_fields("360", h), "camera_height_m": h.get("camera_height_m"),
                                "people": list(getattr(self.p, "last_people_raw", None) or [])})
            return total
        h = msg.header
        pose = h.get("pose", {})
        t_start = time.perf_counter()
        img = self.p.decode_jpeg(msg.attachments["image"])
        decode_ms = (time.perf_counter() - t_start) * 1000.0
        meta = {"t": float(h["time_s"]), "fx": h["fx"], "fy": h["fy"], "cx": h["cx"], "cy": h["cy"], "width": h["width"],
                "height": h["height"], "pan_deg": float(h["pan_deg"]), "tilt_deg": float(h.get("tilt_deg", 0.0)),
                "robot_yaw_deg": float(pose.get("yaw_deg", 0.0))}
        readings, times = self.p.persons(img, meta)
        with self._lock:
            self._v4 = {"persons": readings, "persons_time_s": meta["t"], "fov_deg": float(h["vertical_fov_deg"]),
                        "pan_deg": meta["pan_deg"], "tilt_deg": meta["tilt_deg"]}
            self._latest["inference_ms"].update({k: round(v, 3) for k, v in times.items()})
        raw = getattr(self.p, "last_persons_raw", None) or {}
        self._model_output({**self._frame_fields("pan_tilt", h), "pan_deg": meta["pan_deg"], "tilt_deg": meta["tilt_deg"],
                            "vertical_fov_deg": float(h["vertical_fov_deg"]),
                            **{k: h[k] for k in ("fx", "fy", "cx", "cy", "width", "height")},
                            "people": raw.get("people", []), "hands": raw.get("hands", [])})
        total = (time.perf_counter() - t_start) * 1000.0
        row = {"t_wall_s": round(time.monotonic() - self._t0, 4), "type": kind, "frame_index": h.get("frame_index"),
               "time_s": h.get("time_s"), "pose_x": pose.get("x"), "pose_z": pose.get("z"), "yaw_deg": pose.get("yaw_deg"),
               "skipped_before": skipped, "decode_ms": round(decode_ms, 3), "n_people": len(readings),
               "gesture_read": ";".join(f"{p.track_id}:{p.reading.command}" for p in readings),
               "model_ms": ";".join(f"{k}:{v:.2f}" for k, v in times.items()), "total_ms": round(total, 3)}
        if self._csv_file is not None:
            with self._lock:
                if not self._csv_file.closed:
                    self._csv.writerow(row)
        return total
