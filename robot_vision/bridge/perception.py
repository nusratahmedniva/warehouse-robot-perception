"""Step 3 (team numbering) perception next to the Step 2 bridge: frame_360 -> people, frame_pan_tilt -> gesture.

The models (hri_perception.HriPerception, label "vision") run on background threads, one per camera (since
2026-10-21; before, one thread served both): "perception-360" (person detection on the panorama) and
"perception-gesture" (the gesture reader on the pan-tilt image). Each has a "latest frame only" mailbox: a frame
arriving while the previous one waits replaces it, and the replaced frame is counted as dropped (skipped_before in
perception.csv, dropped in summary()). So a slow panorama call never delays the gesture reading or the reverse, and
the asyncio server never runs inference: it answers every telemetry message from snapshot(), the latest results
with the capture times of their frames; results older than the frozen people_stale_s / gesture_stale_s
(hri_control.json) trigger the controller's existing stale-perception handling.

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
KINDS = ("frame_360", "frame_pan_tilt")
THREAD_NAMES = {"frame_360": "perception-360", "frame_pan_tilt": "perception-gesture"}


class _Lane:
    """One camera: a latest-frame-only mailbox and the thread that empties it."""

    def __init__(self, kind: str, process, verbose: bool):
        self.kind = kind
        self._process = process
        self.verbose = verbose
        self._lock = threading.Lock()
        self._wake = threading.Event()
        self._stop = False
        self.pending = None
        self.skipped = 0            # dropped since the last processed frame (goes into that frame's row)
        self.dropped_total = 0
        self.processed = 0
        self.busy = False
        self.max_total_ms = 0.0
        self.thread = threading.Thread(target=self._run, name=THREAD_NAMES[kind], daemon=True)

    def submit(self, msg) -> None:
        with self._lock:
            if self.pending is not None:
                self.skipped += 1
                self.dropped_total += 1
            self.pending = msg
        self._wake.set()

    def _run(self) -> None:
        while not self._stop:
            self._wake.wait(0.2)
            self._wake.clear()
            with self._lock:
                msg, self.pending = self.pending, None
                skipped, self.skipped = self.skipped, 0
                self.busy = msg is not None
            if msg is None:
                continue
            try:
                ms = self._process(self.kind, msg, skipped)
                self.max_total_ms = max(self.max_total_ms, ms)
                self.processed += 1
            except Exception as e:  # noqa: BLE001 - a bad frame must not stop perception
                if self.verbose:
                    print(f"[perception] {self.kind} {msg.header.get('frame_index')}: {e!r}", flush=True)
            finally:
                self.busy = False

    def stop(self) -> None:
        self._stop = True
        self._wake.set()
        self.thread.join(timeout=5)


class PerceptionWorker:
    def __init__(self, perception, out_dir: Path | None = None, verbose: bool = True):
        self.p = perception
        self.verbose = verbose
        self._lock = threading.Lock()          # guards _latest and the CSV writer
        self._latest = {"people": [], "target": dict(NO_TARGET), "people_time_s": None, "people_pose": None,
                        "gesture": "NONE", "gesture_confidence": 0.0, "gesture_source": "none", "gesture_time_s": None,
                        "inference_ms": {}}
        self._t0 = time.monotonic()
        self._csv_file = None
        if out_dir is not None:
            self._csv_file = (Path(out_dir) / "perception.csv").open("x", newline="", encoding="utf-8", buffering=1)
            self._csv = csv.DictWriter(self._csv_file, fieldnames=FIELDS)
            self._csv.writeheader()
        self.lanes = {k: _Lane(k, self._process, verbose) for k in KINDS}
        for lane in self.lanes.values():
            lane.thread.start()

    @property
    def label(self) -> str:
        return getattr(self.p, "label", "vision")

    @property
    def processed(self) -> dict:
        return {k: lane.processed for k, lane in self.lanes.items()}

    @property
    def ready(self) -> bool:
        """Perception ready: the models are loaded and warmed up (HriPerception does that before this worker exists)
        and at least one live frame of each camera has been processed, so its first-call costs are paid. The guide
        sends it with every command (perception_ready); the Unity trial runner starts trial 1 only after it is true."""
        return all(lane.processed > 0 for lane in self.lanes.values())

    def submit(self, msg) -> None:
        """Queue a frame message (bridge.protocol.Message); a newer frame of the same camera replaces it (dropped,
        counted). Never blocks: called from the asyncio loop."""
        lane = self.lanes.get(msg.type)
        if lane is not None:
            lane.submit(msg)

    def snapshot(self) -> dict:
        with self._lock:
            return json.loads(json.dumps(self._latest))

    def summary(self) -> dict:
        return {k: {"thread": THREAD_NAMES[k], "processed": lane.processed, "dropped": lane.dropped_total,
                    "max_total_ms": round(lane.max_total_ms, 2)} for k, lane in self.lanes.items()} | {
            "note": "one thread per camera, latest frame only: dropped = frames replaced by a newer one before "
                    "their thread got to them"}

    def close(self) -> None:
        for lane in self.lanes.values():
            lane.stop()
        if self._csv_file is not None:
            with self._lock:
                self._csv_file.close()
        if hasattr(self.p, "close"):
            self.p.close()

    def _process(self, kind: str, msg, skipped: int) -> float:
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
        total = (time.perf_counter() - t_start) * 1000.0
        row["total_ms"] = round(total, 3)
        if self._csv_file is not None:
            with self._lock:
                if not self._csv_file.closed:
                    self._csv.writerow(row)
        return total


def _r(x):
    return round(float(x), 2) if x is not None else None
