"""Step 2 TCP bridge server (docs/protocol.md): Unity connects, sends telemetry and camera frames, Python answers
every telemetry message with a command.

Run (from robot_vision/). Trials: run_trials.ps1 / run_trials.sh, which run
    python -m bridge.server --mode guide --perception vision --task Task1|Task2
Bridge test only: python -m bridge.server --mode hello --allow-hello [--config configs/bridge.json] [--duration-s 60]
    [--mute-after-s 5]   (hello mode is refused without --allow-hello so it cannot be used for trials by accident)

--perception vision (optional): frame_360 and frame_pan_tilt also go to the Step 3 perception (bridge/perception.py,
hri_perception.py; models on two background threads, one per camera, latest frame only), whose latest reading is
shown in screen_text and logged to perception.csv in the run folder. The asyncio loop never runs inference.

Diagnostics (2026-10-21, bridge/diagnostics.py): after the models are warmed up the heap is frozen (gc.freeze), so a
full garbage collection no longer stalls the reply loop for 0.2-0.3 s; every run logs event-loop lags
(loop_lag.csv, stall_tracebacks.txt), garbage-collection pauses (gc_pauses.csv), thread counts and Unity's optional
telemetry diagnostics (every round trip, Unity frame times) in summary.json. --exit-on-disconnect stops the server
when Unity disconnects (headless sessions).

Measurement correction (2026-10-22, AUDIT.md section 9): Unity's round trip now runs on its network threads (write of
the telemetry -> reply received; the earlier queued -> received figure is kept as all_messages_queued), Unity sends
every frame duration (unity_frames: max, p99, frames over 100 ms) and its watchdog events (watchdog: stops for
unanswered sent telemetry, unity_frame_stall silences that only the old wall-clock rule caught). --resource-log
starts bridge/resource_monitor.py in its own process (resources.csv, once per second: memory, paging, CPU per process,
GPU). run_info.json records the machine state (power mode, power source; bridge/machine_state.py).

Mode guide (Step 5): the hri_control state machine drives the robot (bridge/guide.py); trials are started by the Unity
trial runner (telemetry trial_index / trial_running); use with --perception vision. Logs decisions.csv and
python_trial_###.json in the run folder. --task Task1 gives the controller the Task 1 map (task_route.py: the
checkpoints of configs/task1_route.json on the straight line); default Task2 (roadmap.json). Every command carries
the map id (route) and perception_ready; the Unity trial runner waits for perception_ready before trial 1 and refuses
trials if the map is not that of its task.

Mode hello (needs --allow-hello): answers v = hello_test.v_mps (0.2), omega = 0, so the robot creeps forward while connected; it also
requests a NavMesh path to a point target_ahead_m in front of the robot's first reported pose. --mute-after-s N stops
answering N s after Unity connects while keeping the connection open, to test Unity's watchdog. Every server start
writes a new folder outputs/bridge_<mode>_<timestamp>/ with run_info.json (git commit, config hash),
config_used/, messages.jsonl (one line per message, with the round-trip delay Unity measured), every
save_every_n_frames-th JPEG of each stream, summary.json and COMPLETE.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import math
import platform
import queue
import socket
import statistics
import sys
import threading
import time
from datetime import datetime
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import decision_io as dio  # noqa: E402  (run-folder helpers: new_run_dir, git_info, sha256, write_json)
from bridge import protocol as P  # noqa: E402

DEFAULT_CONFIG = "configs/bridge.json"
V4_CONTROL, V4_COMMANDER, V4_READER = "configs/v4/control.json", "configs/v4/commander.json", "configs/v4/gesture_reader.json"
FRAME_COUNTERS = ("frames_360_sent", "frames_360_dropped", "frames_pan_tilt_sent", "frames_pan_tilt_dropped")


def load_config(path: str | Path = DEFAULT_CONFIG) -> tuple[dict, Path]:
    p = dio.resolve(path)
    cfg = dio.read_json(p)
    if cfg.get("protocol_version") not in P.SUPPORTED_VERSIONS:
        raise ValueError(f"{p}: protocol_version {cfg.get('protocol_version')} but bridge/protocol.py speaks "
                         f"{list(P.SUPPORTED_VERSIONS)}")
    if cfg["protocol_version"] >= 3 and "hud" not in cfg:
        raise ValueError(f"{p}: protocol version 3 needs a 'hud' block (log_messages_per_direction)")
    for key in ("host", "port", "telemetry_hz", "frame_360_hz", "frame_pan_tilt_hz", "watchdog_timeout_s",
                "max_header_bytes", "max_attachment_bytes"):
        if key not in cfg:
            raise ValueError(f"{p}: missing {key}")
    return cfg, p


class HelloController:
    """Hello test: constant creep command, plus one NavMesh target ahead of the first pose."""

    def __init__(self, hello_cfg: dict, mute_after_s: float | None = None):
        self.cfg = hello_cfg
        self.mute_after_s = mute_after_s
        self.target: tuple[float, float] | None = None
        self.connected_at = time.monotonic()
        self.muted_logged = False

    def on_connect(self) -> None:
        self.target = None
        self.connected_at = time.monotonic()
        self.muted_logged = False

    def on_message(self, msg: P.Message) -> dict | None:
        if msg.type != "telemetry":
            return None
        if self.mute_after_s is not None and time.monotonic() - self.connected_at >= self.mute_after_s:
            if not self.muted_logged:
                print(f"[bridge] muted after {self.mute_after_s:g} s: no more commands (Unity's watchdog should stop "
                      f"the robot)", flush=True)
                self.muted_logged = True
            return None
        if self.target is None:
            pose, d = msg.header["pose"], float(self.cfg["target_ahead_m"])
            yaw = math.radians(pose["yaw_deg"])  # Unity yaw: 0 = +Z, 90 = +X, so forward = (sin, cos)
            self.target = (pose["x"] + d * math.sin(yaw), pose["z"] + d * math.cos(yaw))
        return {"v": float(self.cfg["v_mps"]), "omega": float(self.cfg["omega_radps"]),
                "pan_deg": float(self.cfg["pan_deg"]), "has_target": True, "target_x": self.target[0],
                "target_z": self.target[1], "state": self.cfg["state"], "screen_text": self.cfg["screen_text"]}


class PerceptionController:
    """Wraps a controller: camera frames also go to the perception worker; its latest reading is shown on screen.
    v, omega, pan and the target come from the wrapped controller unchanged."""

    def __init__(self, inner, worker):
        self.inner = inner
        self.worker = worker

    def on_connect(self) -> None:
        self.inner.on_connect()

    def on_message(self, msg: P.Message) -> dict | None:
        if msg.type in ("frame_360", "frame_pan_tilt"):
            self.worker.submit(msg)
        reply = self.inner.on_message(msg)
        if reply is not None:
            s = self.worker.snapshot()
            t = s["target"]
            seen = (f"nearest person {t['bearing_deg']:+.0f} deg, {t['distance_m']:.1f} m" if t["track_id"] >= 0 and
                    t["distance_m"] >= 0 else "nearest person: distance unknown" if t["track_id"] >= 0 else "no person")
            reply = {**reply, "screen_text": f"{reply.get('screen_text', '')} | vision: {seen}; gesture {s['gesture']}"}
        return reply


FRAME_SAVE_QUEUE = 32  # sampled JPEGs waiting for the writer thread (infrastructure, not a bridge.json setting)


class FrameWriter:
    """Writes the sampled frame JPEGs on a background thread, so a slow file write (e.g. an antivirus scan of each new
    file on Windows) never holds the asyncio loop that answers telemetry within Unity's 0.3 s watchdog. The queue is
    bounded: when it is full the save is skipped and counted (summary.json -> frames_saved). Added 2026-10-21 after
    3 of 5 unexplained watchdog stops on the PC directly followed a JPEG write (AUDIT.md section 9)."""

    def __init__(self, folder: Path, max_queue: int = FRAME_SAVE_QUEUE, write=None):
        self.folder = Path(folder)
        self.max_queue = int(max_queue)
        self._q: queue.Queue = queue.Queue(self.max_queue)
        self._write = write or (lambda path, data: path.write_bytes(data))
        self.saved = 0
        self.skipped = 0
        self.errors: list[str] = []
        self._thread = threading.Thread(target=self._run, name="frame-writer", daemon=True)
        self._thread.start()

    def submit(self, name: str, data: bytes) -> bool:
        """Queue one file (never blocks). False = queue full, the save is skipped and counted."""
        try:
            self._q.put_nowait((name, data))
            return True
        except queue.Full:
            self.skipped += 1
            return False

    def _run(self) -> None:
        while True:
            item = self._q.get()
            try:
                if item is None:
                    return
                name, data = item
                try:
                    self._write(self.folder / name, data)
                    self.saved += 1
                except OSError as e:
                    self.errors.append(f"frames/{name}: {e}")
            finally:
                self._q.task_done()

    def wait(self) -> None:
        """Block until every queued file is written (tests, close)."""
        self._q.join()

    def close(self, timeout_s: float = 60.0) -> None:
        self._q.put(None)
        self._thread.join(timeout=timeout_s)

    def summary(self) -> dict:
        return {"saved": self.saved, "skipped_queue_full": self.skipped, "write_errors": len(self.errors),
                "queue_size": self.max_queue,
                "note": "sampled frame JPEGs are written by a background thread; a save is skipped (and counted) "
                        "only when queue_size files are already waiting"}


class RunLog:
    """messages.jsonl (one line per message), sampled frames (FrameWriter, off the event loop) and summary.json."""

    def __init__(self, out: Path, save_every_n_frames: int, frame_write=None, frame_queue: int = FRAME_SAVE_QUEUE):
        self.out = out
        self.save_every = int(save_every_n_frames)
        self.t0 = time.monotonic()
        self.extra: dict = {}                    # more summary.json blocks (diagnostics), filled by run()
        # Unity's optional diagnostics (protocol v2 extras, 2026-10-21): every round trip, Unity frame times, and the
        # receive lag of each telemetry message (how much later than the earliest one Python read it).
        self.rtt_window_max = -1.0
        self.rtt_window_n = 0
        self.rtt_window_sum = 0.0
        self.unity_frame_ms_max = 0.0
        self.unity_frames_over_250ms = 0
        # 2026-10-22: every Unity frame duration, the queued-clock round trip and the watchdog events.
        self.unity_frame_ms: list[float] = []
        self.rtt_clock: str | None = None
        self.rtt_queue_max = -1.0
        self.rtt_queue_n = 0
        self.rtt_queue_sum = 0.0
        self.watchdog_events: list[dict] = []
        self.watchdog_rule: str | None = None
        self.unity_frame_stall_count = 0
        self.recv_offset: float | None = None
        self.recv_lags: list[float] = []
        self.lines = (out / "messages.jsonl").open("w", encoding="utf-8")
        (out / "frames").mkdir()
        self.frames = FrameWriter(out / "frames", frame_queue, frame_write)
        self.counts: dict[str, int] = {}
        self.rtts: list[float] = []
        self.rtt_seen: set[int] = set()
        self.n_telemetry = 0
        self.errors: list[str] = []
        self.watchdog_count = 0
        self.connections = 0
        self.estop_seen = False
        self.frames_received = {"frame_360": 0, "frame_pan_tilt": 0}
        self.frame_counters: list[dict] = []  # Unity's per-connection frame counters, from its latest telemetry

    def now(self) -> float:
        return round(time.monotonic() - self.t0, 6)

    def event(self, kind: str, **fields) -> None:
        self._write({"t_wall_s": self.now(), "dir": "event", "type": kind, **fields})
        if kind == "connect":
            self.connections += 1
            self.frame_counters.append({})
            self.recv_offset = None
        if kind in ("framing_error", "message_error"):
            self.errors.append(f"{kind}: {fields.get('error')}")

    def message(self, direction: str, msg_header: dict, attachments: dict[str, bytes], handle_ms: float | None = None):
        h = {k: v for k, v in msg_header.items() if k != "attachments"}
        t = h.get("type", "?")
        self.counts[f"{direction}:{t}"] = self.counts.get(f"{direction}:{t}", 0) + 1
        line = {"t_wall_s": self.now(), "dir": direction, "type": t, "seq": h.get("seq"),
                "attachments": {n: len(b) for n, b in attachments.items()}, "header": h}
        if handle_ms is not None:
            line["handle_ms"] = round(handle_ms, 3)
        if direction == "in" and t == "telemetry":
            self.n_telemetry += 1
            line["rtt_ms"] = h["rtt_ms"] if h["rtt_ms"] >= 0 else None
            if h["rtt_telemetry_seq"] >= 0 and h["rtt_telemetry_seq"] not in self.rtt_seen:
                self.rtt_seen.add(h["rtt_telemetry_seq"])
                self.rtts.append(float(h["rtt_ms"]))
            self.watchdog_count = max(self.watchdog_count, h["watchdog_count"])
            self.estop_seen |= h["estop"]
            self._unity_diagnostics(h, line)
            if not self.frame_counters:
                self.frame_counters.append({})
            self.frame_counters[-1] = {k: h[k] for k in FRAME_COUNTERS}
        if direction == "in" and t in self.frames_received:
            self.frames_received[t] += 1
        if direction == "in" and t in ("frame_360", "frame_pan_tilt") and self.save_every > 0 \
                and h["frame_index"] % self.save_every == 0:
            name = f"{t}_{h['frame_index']:06d}.jpg"
            if self.frames.submit(name, attachments["image"]):
                line["saved_as"] = f"frames/{name}"
            else:
                line["save_skipped"] = "writer queue full"
        self._write(line)

    def _write(self, obj: dict) -> None:
        self.lines.write(json.dumps(obj, separators=(",", ":")) + "\n")

    def _unity_diagnostics(self, h: dict, line: dict) -> None:
        """Optional telemetry fields (absent from older Unity builds)."""
        if isinstance(h.get("rtt_window_n"), int) and h["rtt_window_n"] > 0:
            self.rtt_window_n += h["rtt_window_n"]
            self.rtt_window_sum += float(h.get("rtt_window_sum_ms", 0.0))
            self.rtt_window_max = max(self.rtt_window_max, float(h.get("rtt_window_max_ms", -1.0)))
        if isinstance(h.get("frame_ms_max"), (int, float)):
            self.unity_frame_ms_max = max(self.unity_frame_ms_max, float(h["frame_ms_max"]))
            self.unity_frames_over_250ms += int(h["frame_ms_max"] > 250.0)
        if isinstance(h.get("frame_ms_list"), list):
            self.unity_frame_ms += [float(x) for x in h["frame_ms_list"] if isinstance(x, (int, float))]
        if isinstance(h.get("rtt_clock"), str):
            self.rtt_clock = h["rtt_clock"]
        if isinstance(h.get("rtt_queue_window_n"), int) and h["rtt_queue_window_n"] > 0:
            self.rtt_queue_n += h["rtt_queue_window_n"]
            self.rtt_queue_sum += float(h.get("rtt_queue_window_sum_ms", 0.0))
            self.rtt_queue_max = max(self.rtt_queue_max, float(h.get("rtt_queue_window_max_ms", -1.0)))
        if isinstance(h.get("watchdog_rule"), str):
            self.watchdog_rule = h["watchdog_rule"]
            self.unity_frame_stall_count = max(self.unity_frame_stall_count, int(h.get("unity_frame_stall_count", 0)))
        for e in h.get("watchdog_events") or []:
            if isinstance(e, dict):
                self.watchdog_events.append({**e, "t_wall_s": line["t_wall_s"], "trial_index": h.get("trial_index"),
                                             "trial_running": h.get("trial_running")})
        if isinstance(h.get("realtime_s"), (int, float)):
            offset = line["t_wall_s"] - float(h["realtime_s"])
            self.recv_offset = offset if self.recv_offset is None else min(self.recv_offset, offset)
            lag_ms = (offset - self.recv_offset) * 1000.0
            self.recv_lags.append(lag_ms)
            line["recv_lag_ms"] = round(lag_ms, 2)

    def summary(self) -> dict:
        r = sorted(self.rtts)
        rtt = {"n": len(r), "coverage": f"{len(r)} of {self.n_telemetry} telemetry messages",
               "note": "Unity-measured: telemetry queued -> answering command received. Before 2026-10-21 Unity "
                       "reported only the latest reply of each frame, so late replies arriving together were missed; "
                       "all_messages (when present) covers every reply"}
        if r:
            rtt.update(mean_ms=round(statistics.fmean(r), 3), median_ms=round(statistics.median(r), 3),
                       p95_ms=round(r[min(len(r) - 1, math.ceil(0.95 * len(r)) - 1)], 3), max_ms=round(r[-1], 3))
        if self.rtt_window_n:
            rtt["all_messages"] = {"n": self.rtt_window_n, "coverage": f"{self.rtt_window_n} replies to "
                                   f"{self.n_telemetry} telemetry messages", "max_ms": round(self.rtt_window_max, 3),
                                   "mean_ms": round(self.rtt_window_sum / self.rtt_window_n, 3),
                                   "clock": self.rtt_clock or "main_thread_queued (Unity build before 2026-10-22)"}
        if self.rtt_queue_n:
            rtt["all_messages_queued"] = {
                "n": self.rtt_queue_n, "max_ms": round(self.rtt_queue_max, 3),
                "mean_ms": round(self.rtt_queue_sum / self.rtt_queue_n, 3),
                "clock": "main_thread_queued: telemetry queued on Unity's main thread -> reply received on its network "
                         "thread (the definition before 2026-10-22, kept for comparison)"}
        lags = sorted(self.recv_lags)
        unity = {"frame_ms_max": round(self.unity_frame_ms_max, 2),
                 "telemetry_windows_with_a_frame_over_250ms": self.unity_frames_over_250ms} if self.recv_lags else None
        if unity is not None and self.unity_frame_ms:
            unity.update(frame_stats(self.unity_frame_ms))
        watchdog = None
        if self.watchdog_rule:
            kinds: dict[str, list[float]] = {}
            for e in self.watchdog_events:
                kinds.setdefault(e.get("kind", "?"), []).append(float(e.get("gap_ms", 0.0)))
            watchdog = {"rule": self.watchdog_rule, "stops_reported_by_unity": self.watchdog_count,
                        "unity_frame_stalls_reported_by_unity": self.unity_frame_stall_count,
                        "events_by_kind": {k: {"n": len(v), "max_gap_ms": round(max(v), 1)} for k, v in sorted(kinds.items())},
                        "events": self.watchdog_events,
                        "note": "watchdog_stop: Python did not answer telemetry Unity actually sent within the timeout; "
                                "unity_frame_stall: no command for the timeout of wall-clock time but no sent telemetry "
                                "unanswered (Unity sent none: a long Unity frame); the old wall-clock rule stopped for both"}
        recv = {"n": len(lags), "max_ms": round(lags[-1], 2), "over_100ms": sum(1 for x in lags if x > 100.0),
                "over_250ms": sum(1 for x in lags if x > 250.0),
                "note": "how much later Python read each telemetry message than the earliest one (Unity real-time "
                        "clock vs. Python's): Python's receive loop stalling shows here, a Unity hitch does not"} if lags else None
        return {"duration_s": self.now(), "connections": self.connections, "message_counts": dict(sorted(self.counts.items())),
                "round_trip": rtt, "python_receive_lag": recv, "unity_frames": unity,
                "frames": self.frame_summary(), "frames_saved": self.frames.summary(),
                "watchdog_count_reported_by_unity": self.watchdog_count, "watchdog": watchdog,
                "estop_seen": self.estop_seen,
                **self.extra, "errors": self.errors + self.frames.errors}

    def frame_summary(self) -> dict:
        """Drop rate per camera from Unity's counters (summed over connections) and frames Python received."""
        out = {"note": "Unity counts per connection and reports in every telemetry message; the last report of each "
                       "connection is used, so frames sent after it are missing from sent_by_unity. drop_rate = "
                       "dropped / (sent + dropped); a frame slot is dropped when a whole period passes without a "
                       "frame or its readback/encoding fails."}
        for cam, prefix, msg_type in (("360", "frames_360", "frame_360"), ("pan_tilt", "frames_pan_tilt", "frame_pan_tilt")):
            sent = sum(c.get(f"{prefix}_sent", 0) for c in self.frame_counters)
            dropped = sum(c.get(f"{prefix}_dropped", 0) for c in self.frame_counters)
            out[cam] = {"sent_by_unity": sent, "dropped_by_unity": dropped,
                        "drop_rate": round(dropped / (sent + dropped), 4) if sent + dropped else None,
                        "received_by_python": self.frames_received[msg_type]}
        return out

    def close(self) -> None:
        self.lines.close()
        self.frames.close()   # writes what is still queued first
        dio.write_json(self.out / "summary.json", self.summary())
        dio.mark_complete(self.out)


def frame_stats(ms: list[float]) -> dict:
    """Unity main-thread frame durations: count, max, p99 (nearest rank), frames over 100 ms and over 250 ms."""
    v = sorted(ms)
    return {"frames": len(v), "frame_ms_p99": round(v[min(len(v) - 1, math.ceil(0.99 * len(v)) - 1)], 2),
            "frame_ms_max_all": round(v[-1], 2), "frames_over_100ms": sum(1 for x in v if x > 100.0),
            "frames_over_250ms": sum(1 for x in v if x > 250.0)}


class BridgeServer:
    """asyncio TCP server for one Unity client at a time."""

    def __init__(self, cfg: dict, controller, log: RunLog | None = None, port: int | None = None, verbose: bool = True):
        self.cfg = cfg
        self.verbose = verbose
        self.disconnected = asyncio.Event()      # set when a client that had connected goes away (--exit-on-disconnect)
        self.limits = P.Limits.from_config(cfg)
        self.controller = controller
        self.log = log
        self.host = cfg["host"]
        self.port = int(cfg["port"]) if port is None else port
        self.server: asyncio.AbstractServer | None = None
        self.active: asyncio.StreamWriter | None = None
        self.seq = 0

    def _say(self, text: str) -> None:
        if self.verbose:
            print(f"[bridge] {text}", flush=True)

    async def start(self) -> int:
        """Listen; returns the bound port (port 0 picks a free one)."""
        self.server = await asyncio.start_server(self._handle, self.host, self.port)
        self.port = self.server.sockets[0].getsockname()[1]
        return self.port

    async def close(self) -> None:
        if self.server is not None:
            self.server.close()
        if self.active is not None:
            self.active.close()
            try:
                await self.active.wait_closed()
            except (ConnectionError, OSError):
                pass
        if self.server is not None:
            await self.server.wait_closed()

    async def send(self, writer: asyncio.StreamWriter, header: dict) -> None:
        """Validate and send one Python -> Unity message (header without version/seq/attachments)."""
        h = {**header, "seq": self.seq}
        self.seq += 1
        P.validate(P.Message({**h, "version": self.limits.version, "attachments": []}), P.TO_UNITY, self.limits)
        writer.write(P.encode(h, version=self.limits.version))
        await writer.drain()
        if self.log:
            self.log.message("out", h, {})

    async def _error(self, writer: asyncio.StreamWriter, text: str, fatal: bool) -> None:
        try:
            await self.send(writer, {"type": "error", "error": text, "fatal": fatal})
        except (ConnectionError, OSError):
            pass

    async def _handle(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        peer = writer.get_extra_info("peername")
        if self.active is not None:
            await self._error(writer, "another client is already connected", fatal=True)
            writer.close()
            return
        self.active = writer
        sock = writer.get_extra_info("socket")
        if sock is not None:
            sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        if self.log:
            self.log.event("connect", peer=str(peer))
        self._say(f"Unity connected from {peer}")
        self.controller.on_connect()
        reason = "closed by client"
        try:
            while True:
                try:
                    msg = await P.read_message(reader, self.limits)
                except P.FramingError as e:
                    reason = f"{type(e).__name__}: {e}"
                    if self.log:
                        self.log.event("framing_error", error=str(e))
                    self._say(f"{reason}; closing the connection")
                    await self._error(writer, str(e), fatal=True)
                    break
                if msg is None:
                    break
                t0 = time.perf_counter()
                try:
                    P.validate(msg, P.FROM_UNITY, self.limits)
                except P.MessageError as e:
                    if self.log:
                        self.log.message("in", msg.header, msg.attachments)
                        self.log.event("message_error", error=str(e), seq=msg.header.get("seq"))
                    self._say(f"rejected message: {e}")
                    await self._error(writer, str(e), fatal=False)
                    continue
                reply = self.controller.on_message(msg)
                if self.log:
                    self.log.message("in", msg.header, msg.attachments, handle_ms=(time.perf_counter() - t0) * 1e3)
                if reply is not None:
                    await self.send(writer, {"type": "command", "reply_to": msg.seq, **reply})
        except (ConnectionError, OSError) as e:
            reason = f"connection lost: {e}"
        finally:
            self.active = None
            if self.log:
                self.log.event("disconnect", reason=reason)
            self._say(f"Unity disconnected ({reason})")
            writer.close()
            self.disconnected.set()


def gesture_motion_hz() -> float:
    return float(dio.read_json(V4_READER)["frame_hz"])


def make_perception_worker(out: Path, perception_config: str | Path):
    """Load the vision models (before Unity connects) and start the worker writing to out/perception.csv."""
    import hri_perception as hpm
    from bridge.perception import PerceptionWorker
    cfg = hpm.load_config(dio.resolve(perception_config))
    return PerceptionWorker(hpm.HriPerception(cfg), out)


def preflight_final(cfg: dict, mode: str, setting: str) -> None:
    """Before a v4 final run starts (SystemExit otherwise): protocol 3 in guide mode, the v4 configs frozen with every hash
    matching, the setting known and not run before, and the zoom switch of control.json what the setting says."""
    import final_guard_v4 as fg
    import freeze_v4 as fz
    if cfg["protocol_version"] < 3 or mode != "guide":
        raise SystemExit("--final-setting is for the v4 study: --mode guide with configs/v4/bridge.json (protocol 3)")
    fz.require_frozen()
    fg.check_name(setting)
    fg.ensure_not_done(dio.resolve(cfg["paths"]["output_root"]), setting, "run")
    want = fg.plan()["settings"][setting].get("zoom")
    have = dio.read_json(V4_CONTROL)["zoom"]["enabled"]
    if want is not None and have != want:
        raise SystemExit(f"setting {setting!r} needs zoom {'on' if want else 'off'} but {V4_CONTROL} has zoom.enabled = {have}")


def make_perception_worker_v4(out: Path, perception_config: str | Path, reader_config: str | Path,
                              commander_config: str | Path):
    """Protocol 3: the v4 perception (tracked pan-tilt people, hands, moving-gesture reader) on the same worker layout."""
    import commander_v4
    import gesture_motion
    import hri_perception as hpm
    import hri_perception_v4 as hv4
    from bridge.perception_v4 import PerceptionWorkerV4
    cfg = hpm.load_config(dio.resolve(perception_config))
    reader, commander = gesture_motion.load_config(dio.resolve(reader_config)), commander_v4.load_config(dio.resolve(commander_config))
    return PerceptionWorkerV4(hv4.HriPerceptionV4(cfg, reader, commander), out)


def record_inference_devices(path: Path, info: dict, perception) -> dict | None:
    """Adds the device and precision each model actually uses, read at runtime after warm-up, and the library
    versions to run_info.json (logging only; nothing is selected or changed here)."""
    if not hasattr(perception, "inference_devices"):
        return None
    try:
        info["inference_devices"] = perception.inference_devices()
    except Exception as e:   # logging must never stop a run
        info["inference_devices"] = {"error": f"{type(e).__name__}: {e}"}
    dio.write_json(path, info)
    models = info["inference_devices"].get("models", {})
    print("[bridge] inference devices: " + "; ".join(f"{k} {v.get('device')} {v.get('precision')}"
                                                     for k, v in models.items()), flush=True)
    return info["inference_devices"]


async def run(cfg: dict, cfg_path: Path, mode: str, duration_s: float | None, mute_after_s: float | None = None,
              perception: str = "off", perception_config: str = "configs/hri_perception.json",
              task: str = "Task2", exit_on_disconnect: bool = False, resource_log: bool = False,
              final_setting: str | None = None) -> Path:
    from bridge import diagnostics as diag
    from bridge import machine_state
    if final_setting:                              # a v4 FINAL: frozen configs, once per setting (final_guard_v4.py)
        preflight_final(cfg, mode, final_setting)
    out = dio.new_run_dir(cfg, f"bridge_{mode}")
    if final_setting:
        import final_guard_v4 as fg
        import freeze_v4 as fz
        dio.write_json(out / "FINAL_SETTING.json", {"setting": final_setting, "frozen_sha256": fz.sha256_lf(fz.REPO / fz.FROZEN_REL),
                                                    "started": datetime.now().isoformat(timespec="seconds")})
    used = [cfg_path]
    if perception == "vision":
        import hri_perception as hpm
        pcfg = dio.resolve(perception_config)
        used += [pcfg, dio.resolve(hpm.load_config(pcfg)["stop"]["adapter_config"])]
    hashes = dio.copy_configs(out, used)
    road = route = None
    if mode == "guide":
        import hri_control as hc
        import task_route as tr
        road, route, road_files = tr.map_for_task(task, hc.load_json)
        v4_files = []
        if cfg["protocol_version"] >= 3:
            v4_files = [V4_CONTROL, V4_COMMANDER, V4_READER]
            if abs(gesture_motion_hz() - cfg["frame_pan_tilt_hz"]) > 1e-9:
                raise ValueError(f"configs/v4/gesture_reader.json frame_hz {gesture_motion_hz()} differs from the bridge "
                                 f"frame_pan_tilt_hz {cfg['frame_pan_tilt_hz']}")
        for extra in ["configs/hri_control.json"] + road_files + v4_files:  # the exact configs of this run
            (out / "config_used" / Path(extra).name).write_bytes(dio.resolve(extra).read_bytes())
        dio.write_json(out / "config_used" / "map_used.json", road)
        print(f"[bridge] task {task}: map {route}", flush=True)
    info = {
        "created": datetime.now().isoformat(timespec="seconds"), "mode": mode,
        "command": " ".join([Path(sys.executable).name] + sys.argv), "git": dio.git_info(),
        "python": platform.python_version(), "platform": platform.platform(),
        "bridge_config": str(cfg_path), "config_sha256": hashes, "protocol_version": cfg["protocol_version"],
        "mute_after_s": mute_after_s, "perception": perception, "task": task if mode == "guide" else None,
        "route": route, "machine_state": machine_state.read(), "resource_log": resource_log}
    dio.write_json(out / "run_info.json", info)
    log = RunLog(out, cfg["logging"]["save_every_n_frames"])
    log.extra["clock_t0_unix_s"] = round(time.time() - (time.monotonic() - log.t0), 6)   # t_wall_s 0 in Unix time
    monitor = None
    if resource_log:
        from bridge import resource_monitor
        monitor = resource_monitor.start(out / "resources.csv")
        print(f"[bridge] resource log: {out / 'resources.csv'} (own process, once per second)", flush=True)
    gc_monitor = diag.GcMonitor(out)
    worker = None
    if perception == "vision":
        worker = (make_perception_worker_v4(out, perception_config, V4_READER, V4_COMMANDER) if cfg["protocol_version"] >= 3
                  else make_perception_worker(out, perception_config))
        print(f"[bridge] perception: {worker.label}", flush=True)
        record_inference_devices(out / "run_info.json", info, worker.p)
    log.extra["threads_at_start"] = diag.thread_info()
    print(f"[bridge] threads: {log.extra['threads_at_start']['python_threads']} Python, "
          f"{log.extra['threads_at_start'].get('process_threads')} in the process", flush=True)
    guide = None
    if mode == "guide":
        if cfg["protocol_version"] >= 3:                       # v4: the v4 controller and guide (protocol 3 only)
            import commander_v4
            import hri_control_v4 as hv
            from bridge.guide_v4 import GuideControllerV4
            base, v4 = hv.load_control(V4_CONTROL)
            controller = guide = GuideControllerV4(hv.ControllerV4(base, v4, commander_v4.load_config(V4_COMMANDER),
                                                                   hc.Roadmap(road)), worker, out, route=route,
                                                   hud_cfg=cfg.get("hud"))
        else:
            from bridge.guide import GuideController
            controller = guide = GuideController(hc.Controller(hc.load_json("configs/hri_control.json"), hc.Roadmap(road)),
                                                 worker, out, route=route,
                                                 protocol_version=cfg["protocol_version"], hud_cfg=cfg.get("hud"))
        if worker is None:
            print("[bridge] WARNING: guide mode without --perception vision: no people, the robot will not move.", flush=True)
    else:
        controller = HelloController(cfg["hello_test"], mute_after_s)
        if worker is not None:
            controller = PerceptionController(controller, worker)
    server = BridgeServer(cfg, controller, log)
    log.extra["gc_freeze"] = diag.freeze_heap()      # infrastructure: full collections no longer stall the loop
    print(f"[bridge] heap frozen: {log.extra['gc_freeze']}", flush=True)
    port = await server.start()
    lag = diag.LoopLagMonitor(out, t0=log.t0)
    lag.start()
    print(f"[bridge] mode {mode}: listening on {cfg['host']}:{port}; run folder {out}", flush=True)
    print("[bridge] press Ctrl+C to stop" + (f" (or wait {duration_s:g} s)" if duration_s else "") +
          (" (or when Unity disconnects)" if exit_on_disconnect else ""), flush=True)
    try:
        waits = [asyncio.create_task(asyncio.sleep(duration_s) if duration_s else asyncio.Event().wait())]
        if exit_on_disconnect:
            waits.append(asyncio.create_task(server.disconnected.wait()))
        try:
            await asyncio.wait(waits, return_when=asyncio.FIRST_COMPLETED)
        finally:
            for w in waits:
                w.cancel()
    finally:
        await lag.stop()
        await server.close()
        if guide is not None:
            guide.close()
        if final_setting and any(out.glob("python_trial_*.json")):
            import final_guard_v4 as fg
            fg.write_done(out, final_setting, "run", {"trials_written": len(list(out.glob("python_trial_*.json")))})
        if worker is not None:
            log.extra["perception"] = worker.summary() if hasattr(worker, "summary") else None
            worker.close()
        gc_monitor.close()
        if monitor is not None:
            from bridge import resource_monitor
            resource_monitor.stop(monitor)
            log.extra["resources"] = resource_monitor.summarise(out / "resources.csv")
        log.extra["event_loop_lag"] = lag.summary()
        log.extra["gc_pauses"] = gc_monitor.summary()
        log.extra["threads_at_end"] = diag.thread_info()
        log.close()
        print(f"[bridge] stopped; summary in {out / 'summary.json'}", flush=True)
    return out


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--config", default=DEFAULT_CONFIG)
    ap.add_argument("--mode", choices=["hello", "guide"], required=True,
                    help="guide: trials (use run_trials.ps1 / run_trials.sh). hello: bridge test only, needs --allow-hello")
    ap.add_argument("--allow-hello", action="store_true",
                    help="hello mode creeps forward at 0.2 m/s and never starts a trial; refused without this flag so "
                         "it cannot be used for trials by accident")
    ap.add_argument("--exit-on-disconnect", action="store_true",
                    help="stop (writing summary.json) when Unity disconnects after a connection (batch-mode launcher)")
    ap.add_argument("--duration-s", type=float, default=None, help="stop after this many seconds")
    ap.add_argument("--mute-after-s", type=float, default=None,
                    help="stop answering this many seconds after Unity connects (watchdog test)")
    ap.add_argument("--perception", choices=["off", "vision"], default="off",
                    help="vision: run the Step 3 perception on the camera frames (needs the YOLO weights)")
    ap.add_argument("--perception-config", default="configs/hri_perception.json")
    ap.add_argument("--resource-log", action="store_true",
                    help="log memory, paging, CPU per process and GPU once per second (resources.csv, own process)")
    ap.add_argument("--final-setting", default=None,
                    help="v4 FINAL run of this setting (zoom_on, zoom_off, bystanders, unseen_look): needs configs/v4/frozen.json "
                         "frozen with every hash matching; refused if the setting was already run (final_guard_v4.py)")
    ap.add_argument("--task", choices=["Task1", "Task2"], default=None,
                    help="guide mode (required there): the map (Task2 = roadmap.json; Task1 = roadmap.json plus the "
                         "checkpoints of configs/task1_route.json). The Unity trial runner refuses trials if it differs "
                         "from its task.")
    args = ap.parse_args(argv)
    if args.mode == "hello" and not args.allow_hello:
        ap.error("hello mode is a bridge test (0.2 m/s creep, no trials); it is refused without --allow-hello. "
                 "For trials run run_trials.ps1 (Windows) or run_trials.sh (macOS) with the task.")
    if args.mode == "guide" and args.task is None:
        ap.error("guide mode needs --task Task1 or --task Task2 (the map must match the Unity trial runner's task)")
    cfg, cfg_path = load_config(args.config)
    if args.mode == "hello" and cfg["protocol_version"] >= 3:
        ap.error("hello mode speaks protocol version 2 only; use --mode guide with a version 3 config")
    try:
        asyncio.run(run(cfg, cfg_path, args.mode, args.duration_s, args.mute_after_s, args.perception,
                        args.perception_config, args.task or "Task2", args.exit_on_disconnect, args.resource_log,
                        args.final_setting))
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
