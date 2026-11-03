"""v4 perception worker for protocol 3 (bridge/perception.py unchanged): the 360 camera runs as in v3; the pan-tilt camera
runs hri_perception_v4.HriPerceptionV4.persons() and keeps the readings of everybody in view (snapshot_v4()).
Same threading model: one thread per camera, latest frame only, never inference on the asyncio loop."""

from __future__ import annotations

import time

from bridge.perception import PerceptionWorker


class PerceptionWorkerV4(PerceptionWorker):
    def __init__(self, perception, out_dir=None, verbose: bool = True):
        super().__init__(perception, out_dir, verbose)
        self._v4 = {"persons": [], "persons_time_s": None, "fov_deg": None, "pan_deg": 0.0}

    def snapshot_v4(self) -> dict:
        with self._lock:
            return dict(self._v4)

    def _process(self, kind: str, msg, skipped: int) -> float:
        if kind != "frame_pan_tilt":
            return super()._process(kind, msg, skipped)
        h = msg.header
        pose = h.get("pose", {})
        t_start = time.perf_counter()
        img = self.p.decode_jpeg(msg.attachments["image"])
        decode_ms = (time.perf_counter() - t_start) * 1000.0
        meta = {"t": float(h["time_s"]), "fx": h["fx"], "fy": h["fy"], "cx": h["cx"], "cy": h["cy"], "width": h["width"],
                "height": h["height"], "pan_deg": float(h["pan_deg"]), "robot_yaw_deg": float(pose.get("yaw_deg", 0.0))}
        readings, times = self.p.persons(img, meta)
        with self._lock:
            self._v4 = {"persons": readings, "persons_time_s": meta["t"], "fov_deg": float(h["vertical_fov_deg"]),
                        "pan_deg": meta["pan_deg"]}
            self._latest["inference_ms"].update({k: round(v, 3) for k, v in times.items()})
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
