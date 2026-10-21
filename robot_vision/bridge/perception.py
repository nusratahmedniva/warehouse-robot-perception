"""Step 3 (team numbering) perception next to the Step 2 bridge: frame_360 -> people, frame_pan_tilt -> gesture.

The models (hri_perception.HriPerception, label "vision") run on one background thread, so the asyncio server keeps
answering every telemetry message within the watchdog time while YOLO works. Only the newest frame of each camera
is processed; older frames waiting behind it are counted as skipped. snapshot() gives the latest result to the
command side (the Step 5 state machine; for now the hello controller shows it on screen).

Every processed frame becomes one row of perception.csv in the server's run folder. Nothing here reads ground
truth: protocol v2 carries no goal and no scripted gesture.
"""

from __future__ import annotations

import csv
import json
import threading
import time
from pathlib import Path

import hri_perception as hpm

NO_TARGET = {"track_id": -1, "bearing_deg": 0.0, "distance_m": -1.0, "distance_source": "none", "confidence": 0.0}
FIELDS = ["t_wall_s", "type", "frame_index", "time_s", "pose_x", "pose_z", "yaw_deg", "skipped_before",
          "n_people", "target_id", "target_bearing_deg", "target_distance_m", "target_distance_source",
          "gesture_read", "gesture_source", "gesture_why", "right_arm_deg", "left_arm_deg", "stop_score",
          "decode_ms", "model_ms", "total_ms", "people_json"]


class PerceptionWorker:
    def __init__(self, perception, out_dir: Path | None = None, verbose: bool = True):
        self.p = perception
        self.verbose = verbose
        self._lock = threading.Lock()
        self._wake = threading.Event()
        self._stop = False
        self._pending: dict[str, object] = {"frame_360": None, "frame_pan_tilt": None}
        self._skipped = {"frame_360": 0, "frame_pan_tilt": 0}
        self.processed = {"frame_360": 0, "frame_pan_tilt": 0}
        self._latest = {"people": [], "target": dict(NO_TARGET), "people_time_s": None, "people_pose": None,
                        "gesture": "NONE", "gesture_confidence": 0.0, "gesture_source": "none", "gesture_time_s": None,
                        "inference_ms": {}}
        self._t0 = time.monotonic()
        self._csv_file = None
        if out_dir is not None:
            self._csv_file = (Path(out_dir) / "perception.csv").open("x", newline="", encoding="utf-8", buffering=1)
            self._csv = csv.DictWriter(self._csv_file, fieldnames=FIELDS)
            self._csv.writeheader()
        self._thread = threading.Thread(target=self._run, name="perception", daemon=True)
        self._thread.start()

    @property
    def label(self) -> str:
        return getattr(self.p, "label", "vision")

    @property
    def ready(self) -> bool:
        """Perception ready: the models are loaded and warmed up (HriPerception does that before this worker exists)
        and at least one live frame of each camera has been processed, so its first-call costs are paid. The guide
        sends it with every command (perception_ready); the Unity trial runner starts trial 1 only after it."""
        return self.processed["frame_360"] > 0 and self.processed["frame_pan_tilt"] > 0

    def submit(self, msg) -> None:
        """Queue a frame message (bridge.protocol.Message); a newer frame of the same camera replaces it."""
        if msg.type not in self._pending:
            return
        with self._lock:
            if self._pending[msg.type] is not None:
                self._skipped[msg.type] += 1
            self._pending[msg.type] = msg
        self._wake.set()

    def snapshot(self) -> dict:
        with self._lock:
            return json.loads(json.dumps(self._latest))

    def close(self) -> None:
        self._stop = True
        self._wake.set()
        self._thread.join(timeout=5)
        if self._csv_file is not None:
            self._csv_file.close()
        if hasattr(self.p, "close"):
            self.p.close()

    def _run(self) -> None:
        while not self._stop:
            self._wake.wait(0.2)
            self._wake.clear()
            for kind in ("frame_pan_tilt", "frame_360"):  # the gesture first: it decides the dialog
                with self._lock:
                    msg, self._pending[kind] = self._pending[kind], None
                    skipped, self._skipped[kind] = self._skipped[kind], 0
                if msg is None:
                    continue
                try:
                    self._process(kind, msg, skipped)
                except Exception as e:  # noqa: BLE001 - a bad frame must not stop perception
                    if self.verbose:
                        print(f"[perception] {kind} {msg.header.get('frame_index')}: {e!r}", flush=True)

    def _process(self, kind: str, msg, skipped: int) -> None:
        h = msg.header
        pose = h.get("pose", {})
        t_start = time.perf_counter()
        img = self.p.decode_jpeg(msg.attachments["image"])
        decode_ms = (time.perf_counter() - t_start) * 1000.0
        row = {"t_wall_s": round(time.monotonic() - self._t0, 4), "type": kind, "frame_index": h.get("frame_index"),
               "time_s": h.get("time_s"), "pose_x": pose.get("x"), "pose_z": pose.get("z"), "yaw_deg": pose.get("yaw_deg"),
               "skipped_before": skipped, "decode_ms": round(decode_ms, 3)}
        if kind == "frame_360":
            people, ms = self.p.people(img, float(pose.get("yaw_deg", 0.0)), 90.0, -90.0,
                                       camera_height_m=h.get("camera_height_m"),
                                       centre_world_yaw_deg=float(h.get("centre_world_yaw_deg", 0.0)))
            i = hpm.pick_nearest(people)
            target = dict(people[i]) if i is not None else dict(NO_TARGET)
            for q in people + [target]:
                q.pop("box_h", None)
            with self._lock:
                self._latest.update(people=people, target=target, people_time_s=h.get("time_s"), people_pose=dict(pose))
                self._latest["inference_ms"]["yolo11s-pose/cam360"] = round(ms, 3)
            row.update(n_people=len(people), target_id=target["track_id"], target_bearing_deg=target["bearing_deg"],
                       target_distance_m=target["distance_m"], target_distance_source=target["distance_source"],
                       model_ms=f"yolo11s-pose/cam360:{ms:.2f}", people_json=json.dumps(people, separators=(",", ":")))
        else:
            command, conf, detail, times = self.p.gesture(img, float(h.get("time_s", 0.0)))
            with self._lock:
                self._latest.update(gesture=command, gesture_confidence=conf, gesture_source=detail.get("source", "none"),
                                    gesture_time_s=h.get("time_s"))
                self._latest["inference_ms"].update({k: round(v, 3) for k, v in times.items()})
            row.update(gesture_read=command, gesture_source=detail.get("source", "none"), gesture_why=detail.get("why"),
                       right_arm_deg=_r(detail.get("right_arm_deg")), left_arm_deg=_r(detail.get("left_arm_deg")),
                       stop_score=detail.get("stop_score"),
                       model_ms=";".join(f"{k}:{v:.2f}" for k, v in times.items()))
        row["total_ms"] = round((time.perf_counter() - t_start) * 1000.0, 3)
        self.processed[kind] += 1
        if self._csv_file is not None:
            self._csv.writerow(row)


def _r(x):
    return round(float(x), 2) if x is not None else None
