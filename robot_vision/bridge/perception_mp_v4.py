"""v4 perception in worker processes (protocol 3 only; AUDIT.md section 14.14). bridge/perception.py and
bridge/perception_v4.py (threads in the server process) are unchanged and stay the v3 / fallback path.

Why: Unity stops the robot when Python is silent for 0.3 s. Model inference on threads shares one GIL with the asyncio loop
that answers telemetry, so a heavy call (MediaPipe, the tracker, a garbage collection) can stall the loop. Here the models run
in two worker processes started with the "spawn" method (works on Windows and macOS), one per camera:

  people   frame_360 -> YOLO11s-pose + ByteTrack, people and the nearest person (hri_perception.HriPerception.people)
  gesture  frame_pan_tilt -> tracked people, hands, moving-gesture buffers and reader (HriPerceptionV4.persons)

Inside each worker the unchanged PerceptionWorkerV4 runs its lane (latest frame only, same processing and the same
perception.csv row as the threaded worker); the worker only adds a way out for the results. In the server process:

  - submit(msg) puts the frame into a one-slot mailbox (newer frame replaces the old one, counted as dropped) and returns;
    a sender thread per worker writes the JPEG bytes into the pipe. The asyncio loop never touches a pipe, so a slow or
    stuck worker can only block its own sender thread.
  - a receiver thread per worker reads the results (small pickled dicts and PersonReading objects) and swaps them in as the
    latest ones. snapshot() / snapshot_v4() only read them: the loop never waits for a model.
  - a worker that died or has not answered a frame for behind_after_s is logged (print,
    perception_events.jsonl, summary) and the last results stay in place with their capture times, so the controller sees
    them as stale (people_stale_s, gesture_stale_s: unknown, never a guess). Nothing blocks and nothing restarts.

Nothing here reads ground truth: the workers get the same frames and headers the threaded worker gets.
"""

from __future__ import annotations

import csv
import gc
import importlib
import json
import multiprocessing as mp
import threading
import time
import traceback
from pathlib import Path

import hri_perception as hpm
from bridge import protocol as P
from bridge.perception import FIELDS, NO_TARGET
from bridge.perception_v4 import PerceptionWorkerV4

LANES = {"frame_360": "people", "frame_pan_tilt": "gesture"}
MAX_SUBMIT_TIMES = 64              # frames whose submit time is remembered (end-to-end latency); older ones were dropped
MAX_LATENCIES = 200_000            # per worker: 10 h at 5 Hz, 20 h at 10 Hz
DEFAULTS = {"mode": "processes", "start_method": "spawn", "ready_timeout_s": 300.0, "behind_after_s": 0.5,
            "health_poll_s": 0.1, "stop_timeout_s": 15.0}


def is_behind(waiting_since: float | None, now: float, behind_after_s: float) -> bool:
    """A worker is behind when a frame handed to it has waited for its result longer than behind_after_s. Nothing waiting
    (no frame arrived since its last result, e.g. before the first frame or while Unity is idle) is never behind."""
    return waiting_since is not None and now - waiting_since > behind_after_s


# ---------------------------------------------------------------- the worker process

class _OpenSink:
    closed = False

    def close(self):
        self.closed = True


class _RowCapture:
    """Stands in for the csv writer of PerceptionWorker: keeps the row of the frame this thread just processed."""

    def __init__(self):
        self._local = threading.local()

    def writerow(self, row: dict) -> None:
        self._local.row = row

    def take(self) -> dict | None:
        row, self._local.row = getattr(self._local, "row", None), None
        return row


class _ChildWorker(PerceptionWorkerV4):
    """PerceptionWorkerV4 in the worker process: processing unchanged; every finished frame is also sent to the server."""

    def __init__(self, perception, emit):
        self._emit = emit
        super().__init__(perception, None)
        self._capture = _RowCapture()
        self._csv_file, self._csv = _OpenSink(), self._capture      # _process "writes" its row here; we send it on

    def _process(self, kind: str, msg, skipped: int) -> float:
        total = super()._process(kind, msg, skipped)
        h = msg.header
        payload = {"frame_index": h.get("frame_index"), "total_ms": total, "row": self._capture.take(),
                   "processed": self.lanes[kind].processed + 1, "dropped": self.lanes[kind].dropped_total,
                   "max_total_ms": max(self.lanes[kind].max_total_ms, total)}
        s = self.snapshot()
        if kind == "frame_360":
            payload.update({k: s[k] for k in ("people", "target", "people_time_s", "people_pose")})
        else:
            payload["v4"] = self.snapshot_v4()
        payload["inference_ms"] = s["inference_ms"]
        self._emit("result", kind, payload)
        return total


def _resolve(dotted: str):
    mod, _, name = dotted.partition(":")
    return getattr(importlib.import_module(mod), name)


def child_main(spec: dict, rx, tx) -> None:
    """Entry point of a worker process (module level: spawn must be able to import it)."""
    import signal
    signal.signal(signal.SIGINT, signal.SIG_IGN)     # Ctrl+C reaches every process of the console: the server stops us
    send_lock = threading.Lock()

    def send(*msg) -> None:
        with send_lock:
            tx.send(msg)

    worker = perception = None
    try:
        perception = _resolve(spec["factory"])(spec)
        worker = _ChildWorker(perception, lambda *m: send(*m))
        from bridge import diagnostics as diag
        frozen = diag.freeze_heap()                  # as in the server process: a full collection no longer stalls the models
        devices = perception.inference_devices() if hasattr(perception, "inference_devices") else {}
        send("ready", {"label": getattr(perception, "label", spec["name"]), "devices": devices, "gc_freeze": frozen})
        while True:
            m = rx.recv()
            if m[0] == "stop":
                break
            if m[0] == "frame":
                worker.submit(P.Message(m[2], {"image": m[3]}))
    except (EOFError, OSError):
        pass                                          # the server went away
    except Exception:                                 # noqa: BLE001 - reported to the server, which refuses to start or logs it
        try:
            send("error", traceback.format_exc())
        except Exception:                             # noqa: BLE001
            pass
    finally:
        try:
            if worker is not None:
                worker.close()
        except Exception:                             # noqa: BLE001
            pass


# ---------------------------------------------------------------- real models, one camera each

def _check_weights(cfg: dict):
    import gesture_adapter as ga
    w = hpm.resolve(cfg["pose_model"]["weights"])
    if not w.exists():
        raise FileNotFoundError(f"{w} not found (download yolo11s-pose.pt into robot_vision/models, see README)")
    if ga.sha256_file(w) != cfg["pose_model"]["sha256"]:
        raise ValueError(f"{w} does not match the sha256 in the perception config")
    return w


class PeoplePerception:
    """The panorama lane of hri_perception.HriPerception: YOLO11s-pose + ByteTrack on frame_360. people() is that class's own
    function (same models, arguments and thresholds); only the models this lane needs are loaded."""

    label = "vision v4 people (YOLO11s-pose tracked on the 360 camera)"
    people = hpm.HriPerception.people
    decode_jpeg = staticmethod(hpm.HriPerception.decode_jpeg)

    def __init__(self, cfg: dict, device: str | None = None):
        from ultralytics import YOLO

        from check_environment import select_device
        self.cfg = cfg
        w = _check_weights(cfg)
        self.device = device or str(select_device(cfg.get("device", "auto")))
        self.pano_model = YOLO(str(w), task="pose")
        pano = hpm.warm_up_frame(*hpm.WARM_UP_SIZES["frame_360"])     # the same warm-up calls as a live frame, results discarded
        for _ in range(3):
            self.people(pano, 0.0, camera_height_m=cfg["people"]["camera_height_m"])
        for tracker in getattr(self.pano_model.predictor, "trackers", None) or []:
            tracker.reset()

    def inference_devices(self) -> dict:
        return {"requested_device": self.device, "models": {"yolo11s-pose/cam360": hpm.yolo_runtime(self.pano_model)},
                "versions": hpm.library_versions()}


class GesturePerception:
    """The pan-tilt lane of hri_perception_v4.HriPerceptionV4: tracked people, MediaPipe hands, moving-gesture reader.
    persons() is that class's own function; the 360 model and the v3 STOP adapter, which v4 does not use, are not loaded."""

    label = "vision v4 (YOLO11s-pose tracked + MediaPipe hands + moving-gesture reader)"
    decode_jpeg = staticmethod(hpm.HriPerception.decode_jpeg)

    def __init__(self, cfg: dict, reader_cfg: dict, commander_cfg: dict, device: str | None = None):
        from ultralytics import YOLO

        import gesture_adapter as ga
        import gesture_adapter_v4 as gav4
        import hri_perception_v4 as hv4
        from check_environment import select_device
        self.persons = lambda bgr, meta: hv4.HriPerceptionV4.persons(self, bgr, meta)
        self.cfg, self._ga = cfg, ga
        w = _check_weights(cfg)
        self.device = device or str(select_device(cfg.get("device", "auto")))
        self.stop_cfg = ga.load_gesture_config(hpm.resolve(cfg["stop"]["adapter_config"]))
        self.track_model = YOLO(str(w), task="pose")
        self.hands = gav4.V4RecognizerAdapter(self.stop_cfg)
        self.pipeline = hv4.PersonsPipeline(reader_cfg, commander_cfg)
        frame = hpm.warm_up_frame(*hpm.WARM_UP_SIZES["frame_pan_tilt"])
        meta = {"fx": 458.99, "fy": 458.99, "cx": 365.0, "cy": 265.0, "width": frame.shape[1], "height": frame.shape[0],
                "pan_deg": 0.0, "robot_yaw_deg": 0.0}
        for i in range(3):
            self.persons(frame, {**meta, "t": 0.1 * i})
        for tracker in getattr(self.track_model.predictor, "trackers", None) or []:
            tracker.reset()
        self.pipeline.reset()

    def inference_devices(self) -> dict:
        return {"requested_device": self.device, "models": {"yolo11s-pose/people-track": hpm.yolo_runtime(self.track_model),
                                                            "mediapipe/hands": self.hands.runtime()},
                "versions": hpm.library_versions()}

    def close(self) -> None:
        self.hands.close()


def real_people(spec: dict):
    return PeoplePerception(hpm.load_config(hpm.resolve(spec["args"]["perception_config"])))


def real_gesture(spec: dict):
    import commander_v4
    import gesture_motion
    a = spec["args"]
    return GesturePerception(hpm.load_config(hpm.resolve(a["perception_config"])),
                             gesture_motion.load_config(hpm.resolve(a["reader_config"])),
                             commander_v4.load_config(hpm.resolve(a["commander_config"])))


# ---------------------------------------------------------------- the server side

class _Link:
    """One worker process as the server sees it: the process, a one-slot mailbox with its sender thread, a receiver thread."""

    def __init__(self, ctx, spec: dict, owner: "ProcessPerceptionV4"):
        self.spec, self.owner, self.name, self.kind = spec, owner, spec["name"], spec["kind"]
        rx_parent, tx_child = ctx.Pipe(duplex=False)         # worker -> server
        rx_child, tx_parent = ctx.Pipe(duplex=False)         # server -> worker
        self.proc = ctx.Process(target=child_main, args=(spec, rx_child, tx_child), name=f"perception-{self.name}", daemon=True)
        self.proc.start()
        tx_child.close()
        rx_child.close()
        self._tx, self._rx = tx_parent, rx_parent
        self._lock = threading.Lock()                        # mailbox and counters; held for assignments only
        self._send_lock = threading.Lock()
        self._wake = threading.Event()
        self._mail = None
        self.closing = False
        self.dead = False
        self.ready_info: dict | None = None
        self.error: str | None = None
        self.submitted = self.dropped = self.processed = self.child_dropped = 0
        self.child_max_total_ms = 0.0
        self.submit_t: dict = {}
        self.latencies: list[float] = []
        self.t_ready = self.last_submit_t = self.last_result_t = None
        self.behind = False
        self.waiting_since = None      # when the frame now waiting for a result was handed in (None: nothing is waiting)
        self.latest_index = None
        self._sender = threading.Thread(target=self._send_loop, name=f"perception-{self.name}-send", daemon=True)
        self._receiver = threading.Thread(target=self._recv_loop, name=f"perception-{self.name}-recv", daemon=True)
        self._sender.start()
        self._receiver.start()

    def submit(self, header: dict, data: bytes) -> None:
        """Never blocks: the newest frame replaces one still waiting."""
        now = time.monotonic()
        with self._lock:
            if self._mail is not None:
                self.dropped += 1
            self._mail = ("frame", self.kind, header, data)
            self.submitted += 1
            self.last_submit_t = now
            self.latest_index = header.get("frame_index")
            if self.waiting_since is None:
                self.waiting_since = now
            self.submit_t[header.get("frame_index")] = now
            while len(self.submit_t) > MAX_SUBMIT_TIMES:
                del self.submit_t[next(iter(self.submit_t))]
        self._wake.set()

    def _send_loop(self) -> None:
        while not self.closing:
            self._wake.wait(0.5)
            self._wake.clear()
            with self._lock:
                m, self._mail = self._mail, None
            if m is None:
                continue
            try:
                with self._send_lock:
                    self._tx.send(m)
            except (OSError, ValueError, EOFError):
                return                                       # the receiver thread reports the worker's death

    def _recv_loop(self) -> None:
        while True:
            try:
                m = self._rx.recv()
            except (EOFError, OSError):
                break
            try:
                self.owner._on_message(self, m)
            except Exception:                                # noqa: BLE001 - a bad result must not end the receiver
                self.owner._event("error", self, text=traceback.format_exc(limit=3))
        self.owner._on_eof(self)

    def stop(self, timeout_s: float) -> None:
        self.closing = True
        self._wake.set()
        if self._send_lock.acquire(timeout=1.0):
            try:
                self._tx.send(("stop",))
            except (OSError, ValueError, EOFError):
                pass
            finally:
                self._send_lock.release()
        self.proc.join(timeout_s)
        if self.proc.is_alive():
            self.proc.terminate()
            self.proc.join(5.0)
        for c in (self._tx, self._rx):
            try:
                c.close()
            except OSError:
                pass


class _DevicesProxy:
    """worker.p of the threaded worker: the server asks it for the devices after warm-up (run_info.json)."""

    def __init__(self, owner):
        self.owner = owner

    def inference_devices(self) -> dict:
        models, versions, req = {}, {}, None
        for link in self.owner.links.values():
            d = (link.ready_info or {}).get("devices") or {}
            models.update(d.get("models", {}))
            versions = versions or d.get("versions", {})
            req = req or d.get("requested_device")
        return {"requested_device": req, "models": models, "versions": versions, "worker_processes": True}


class ProcessPerceptionV4:
    """Same interface as bridge.perception_v4.PerceptionWorkerV4 (submit, snapshot, snapshot_v4, ready, label, summary,
    close, p), with the models in worker processes. specs: one dict per worker: name, kind (frame_360 | frame_pan_tilt),
    factory ('module:function', run in the worker: spec -> perception object) and args (JSON-able)."""

    mode = "processes"

    def __init__(self, specs: list[dict], out_dir: Path | None = None, wcfg: dict | None = None, verbose: bool = True):
        self.cfg = {**DEFAULTS, **(wcfg or {})}
        self.verbose = verbose
        self._lock = threading.Lock()                        # guards _latest, _v4 and the event list: assignments only, no I/O
        self._io_lock = threading.Lock()                     # guards the csv and the events file (writes happen under this one)
        self._t0 = time.monotonic()
        self._latest = {"people": [], "target": dict(NO_TARGET), "people_time_s": None, "people_pose": None, "gesture": "NONE",
                        "gesture_confidence": 0.0, "gesture_source": "none", "gesture_time_s": None, "inference_ms": {}}
        self._v4 = {"persons": [], "persons_time_s": None, "fov_deg": None, "pan_deg": 0.0}
        self.events: list[dict] = []
        self._csv_file = self._events_file = None
        if out_dir is not None:
            self._csv_file = (Path(out_dir) / "perception.csv").open("x", newline="", encoding="utf-8", buffering=1)
            self._csv = csv.DictWriter(self._csv_file, fieldnames=FIELDS)
            self._csv.writeheader()
            self._events_file = (Path(out_dir) / "perception_events.jsonl").open("x", encoding="utf-8", buffering=1)
        self.p = _DevicesProxy(self)
        self._stop_health = threading.Event()
        ctx = mp.get_context(self.cfg["start_method"])
        self.links = {s["kind"]: _Link(ctx, s, self) for s in specs}
        self._health = threading.Thread(target=self._health_loop, name="perception-health", daemon=True)
        self._health.start()

    # ---- the interface the controller and the server use (all non-blocking)

    @property
    def label(self) -> str:
        info = (self.links.get("frame_pan_tilt") or next(iter(self.links.values()))).ready_info or {}
        return str(info.get("label", "vision v4 (worker processes)")) + " in worker processes"

    @property
    def processed(self) -> dict:
        return {k: link.processed for k, link in self.links.items()}

    @property
    def ready(self) -> bool:
        return all(link.ready_info is not None and link.processed > 0 for link in self.links.values())

    def submit(self, msg) -> None:
        link = self.links.get(msg.type)
        if link is not None and not link.dead:
            link.submit(msg.header, msg.attachments["image"])

    def snapshot(self) -> dict:
        with self._lock:
            return json.loads(json.dumps(self._latest))

    def snapshot_v4(self) -> dict:
        with self._lock:
            return dict(self._v4)

    # ---- start-up and shutdown

    def wait_started(self, timeout_s: float | None = None) -> None:
        """Block until every worker has loaded and warmed up its models (the server listens only after this). A worker
        that failed or died raises RuntimeError with its traceback."""
        t_end = time.monotonic() + (self.cfg["ready_timeout_s"] if timeout_s is None else timeout_s)
        while time.monotonic() < t_end:
            for link in self.links.values():
                if link.error or link.dead:
                    self.close()
                    raise RuntimeError(f"perception worker {link.name} failed to start:\n{link.error or 'the process exited'}")
            if all(link.ready_info is not None for link in self.links.values()):
                return
            time.sleep(0.1)
        self.close()
        raise RuntimeError(f"perception workers not ready within {self.cfg['ready_timeout_s']:g} s")

    def close(self) -> None:
        self._stop_health.set()
        for link in self.links.values():
            link.stop(float(self.cfg["stop_timeout_s"]))
        for link in self.links.values():
            link._receiver.join(2.0)
        with self._io_lock:
            for f in (self._csv_file, self._events_file):
                if f is not None and not f.closed:
                    f.close()

    # ---- messages from the workers (receiver threads)

    def _on_message(self, link: _Link, m: tuple) -> None:
        kind = m[0]
        now = time.monotonic()
        if kind == "ready":
            link.ready_info, link.t_ready, link.last_result_t = m[1], now, now
            if self.verbose:
                print(f"[perception] worker {link.name} ready ({m[1].get('label')})", flush=True)
        elif kind == "result":
            self._on_result(link, m[1], m[2], now)
        elif kind == "error":
            link.error = m[1]
            self._event("error", link, text=m[1][-1500:])

    def _on_result(self, link: _Link, kind: str, d: dict, now: float) -> None:
        with self._lock:                                     # the results first, then the counters that announce them
            self._latest["inference_ms"].update(d.get("inference_ms", {}))
            if kind == "frame_360":
                self._latest.update({k: d[k] for k in ("people", "target", "people_time_s", "people_pose")})
            else:
                self._v4 = d["v4"]
        row = d.get("row")
        if row is not None and self._csv_file is not None:
            with self._io_lock:
                if not self._csv_file.closed:
                    self._csv.writerow({**row, "t_wall_s": round(now - self._t0, 4)})
        with link._lock:
            t_sub = link.submit_t.pop(d.get("frame_index"), None)
            was_behind, behind_since, link.behind = link.behind, link.waiting_since, False
            link.waiting_since = link.last_submit_t if d.get("frame_index") != link.latest_index else None
            link.last_result_t = now
            link.processed, link.child_dropped = d["processed"], d["dropped"]
            link.child_max_total_ms = d["max_total_ms"]
            if t_sub is not None and len(link.latencies) < MAX_LATENCIES:
                link.latencies.append((now - t_sub) * 1000.0)
        if was_behind:
            self._event("recovered", link, behind_s=round(now - (behind_since or now), 3))

    def _on_eof(self, link: _Link) -> None:
        link.dead = True
        if link.closing:
            return
        link.proc.join(1.0)
        self._event("died", link, exitcode=link.proc.exitcode)

    # ---- health (own thread)

    def _health_loop(self) -> None:
        while not self._stop_health.wait(float(self.cfg["health_poll_s"])):
            now = time.monotonic()
            for link in self.links.values():
                if link.dead or link.closing or link.ready_info is None:
                    continue
                with link._lock:
                    stuck = is_behind(link.waiting_since, now, float(self.cfg["behind_after_s"]))
                    newly = stuck and not link.behind
                    if newly:
                        link.behind, waited = True, now - link.waiting_since
                if newly:
                    self._event("behind", link, waiting_for_a_result_s=round(waited, 3))

    def _event(self, kind: str, link: _Link, **fields) -> None:
        ev = {"t_wall_s": round(time.monotonic() - self._t0, 4), "worker": link.name, "event": kind, **fields}
        with self._lock:
            self.events.append(ev)
        if self._events_file is not None:
            with self._io_lock:
                if not self._events_file.closed:
                    self._events_file.write(json.dumps(ev, separators=(",", ":")) + "\n")
        if self.verbose:
            print(f"[perception] worker {link.name}: {kind} {fields if kind != 'error' else ''}", flush=True)

    # ---- summary.json

    def summary(self) -> dict:
        def lat(link):
            v = sorted(link.latencies)
            if not v:
                return None
            return {"n": len(v), "mean_ms": round(sum(v) / len(v), 2), "p99_ms": round(v[min(len(v) - 1, -(-99 * len(v) // 100) - 1)], 2),
                    "max_ms": round(v[-1], 2)}
        out = {"mode": "processes", "start_method": self.cfg["start_method"], "behind_after_s": self.cfg["behind_after_s"]}
        for kind, link in self.links.items():
            out[kind] = {"worker": link.name, "pid": link.proc.pid, "processed": link.processed, "submitted": link.submitted,
                         "dropped_in_server_mailbox": link.dropped, "dropped_in_worker_mailbox": link.child_dropped,
                         "max_total_ms": round(link.child_max_total_ms, 2), "end_to_end_latency_ms": lat(link),
                         "alive": link.proc.is_alive() and not link.dead}
        out["worker_events"] = [e for e in self.events if e["event"] != "recovered"]
        out["worker_events_all"] = list(self.events)
        out["note"] = ("one process per camera, latest frame only (a one-slot mailbox in the server and one in the worker); "
                       "end_to_end_latency = frame handed to the server's mailbox -> its result received; worker_events counts "
                       "deaths, errors and 'behind' episodes (a frame waited longer than behind_after_s for its result)")
        return out


def start_v4(out_dir: Path | None, perception_config: str, reader_config: str, commander_config: str,
             wcfg: dict | None = None, verbose: bool = True) -> ProcessPerceptionV4:
    """The two real worker processes; returns when both have loaded and warmed up their models."""
    args = {"perception_config": str(perception_config), "reader_config": str(reader_config),
            "commander_config": str(commander_config)}
    specs = [{"name": "people", "kind": "frame_360", "factory": "bridge.perception_mp_v4:real_people", "args": args},
             {"name": "gesture", "kind": "frame_pan_tilt", "factory": "bridge.perception_mp_v4:real_gesture", "args": args}]
    worker = ProcessPerceptionV4(specs, out_dir, wcfg, verbose)
    worker.wait_started()
    return worker
