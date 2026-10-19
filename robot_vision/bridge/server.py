"""Step 2 TCP bridge server (docs/protocol.md): Unity connects, sends telemetry and camera frames, Python answers
every telemetry message with a command.

Run (from robot_vision/):
    python -m bridge.server --mode hello [--config configs/bridge.json] [--duration-s 60]

Mode hello: answers v = hello_test.v_mps (0.2), omega = 0, so the robot creeps forward while connected; it also
requests a NavMesh path to a point target_ahead_m in front of the robot's first reported pose. Every server start
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
import socket
import statistics
import sys
import time
from datetime import datetime
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import decision_io as dio  # noqa: E402  (run-folder helpers: new_run_dir, git_info, sha256, write_json)
from bridge import protocol as P  # noqa: E402

DEFAULT_CONFIG = "configs/bridge.json"


def load_config(path: str | Path = DEFAULT_CONFIG) -> tuple[dict, Path]:
    p = dio.resolve(path)
    cfg = dio.read_json(p)
    if cfg.get("protocol_version") != P.PROTOCOL_VERSION:
        raise ValueError(f"{p}: protocol_version {cfg.get('protocol_version')} but bridge/protocol.py speaks "
                         f"{P.PROTOCOL_VERSION}")
    for key in ("host", "port", "telemetry_hz", "frame_360_hz", "frame_pan_tilt_hz", "watchdog_timeout_s",
                "max_header_bytes", "max_attachment_bytes"):
        if key not in cfg:
            raise ValueError(f"{p}: missing {key}")
    return cfg, p


class HelloController:
    """Hello test: constant creep command, plus one NavMesh target ahead of the first pose."""

    def __init__(self, hello_cfg: dict):
        self.cfg = hello_cfg
        self.target: tuple[float, float] | None = None

    def on_connect(self) -> None:
        self.target = None

    def on_message(self, msg: P.Message) -> dict | None:
        if msg.type != "telemetry":
            return None
        if self.target is None:
            pose, d = msg.header["pose"], float(self.cfg["target_ahead_m"])
            yaw = math.radians(pose["yaw_deg"])  # Unity yaw: 0 = +Z, 90 = +X, so forward = (sin, cos)
            self.target = (pose["x"] + d * math.sin(yaw), pose["z"] + d * math.cos(yaw))
        return {"v": float(self.cfg["v_mps"]), "omega": float(self.cfg["omega_radps"]),
                "pan_deg": float(self.cfg["pan_deg"]), "has_target": True, "target_x": self.target[0],
                "target_z": self.target[1], "state": self.cfg["state"], "screen_text": self.cfg["screen_text"]}


class RunLog:
    """messages.jsonl (one line per message), sampled frames and summary.json in one run folder."""

    def __init__(self, out: Path, save_every_n_frames: int):
        self.out = out
        self.save_every = int(save_every_n_frames)
        self.t0 = time.monotonic()
        self.lines = (out / "messages.jsonl").open("w", encoding="utf-8")
        (out / "frames").mkdir()
        self.counts: dict[str, int] = {}
        self.rtts: list[float] = []
        self.rtt_seen: set[int] = set()
        self.n_telemetry = 0
        self.errors: list[str] = []
        self.watchdog_count = 0
        self.connections = 0

    def now(self) -> float:
        return round(time.monotonic() - self.t0, 6)

    def event(self, kind: str, **fields) -> None:
        self._write({"t_wall_s": self.now(), "dir": "event", "type": kind, **fields})
        if kind == "connect":
            self.connections += 1
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
        if direction == "in" and t in ("frame_360", "frame_pan_tilt") and self.save_every > 0 \
                and h["frame_index"] % self.save_every == 0:
            name = f"{t}_{h['frame_index']:06d}.jpg"
            (self.out / "frames" / name).write_bytes(attachments["image"])
            line["saved_as"] = f"frames/{name}"
        self._write(line)

    def _write(self, obj: dict) -> None:
        self.lines.write(json.dumps(obj, separators=(",", ":")) + "\n")

    def summary(self) -> dict:
        r = sorted(self.rtts)
        rtt = {"n": len(r), "coverage": f"{len(r)} of {self.n_telemetry} telemetry messages",
               "note": "Unity-measured: telemetry queued -> answering command received"}
        if r:
            rtt.update(mean_ms=round(statistics.fmean(r), 3), median_ms=round(statistics.median(r), 3),
                       p95_ms=round(r[min(len(r) - 1, math.ceil(0.95 * len(r)) - 1)], 3), max_ms=round(r[-1], 3))
        return {"duration_s": self.now(), "connections": self.connections, "message_counts": dict(sorted(self.counts.items())),
                "round_trip": rtt, "watchdog_count_reported_by_unity": self.watchdog_count, "errors": self.errors}

    def close(self) -> None:
        self.lines.close()
        dio.write_json(self.out / "summary.json", self.summary())
        dio.mark_complete(self.out)


class BridgeServer:
    """asyncio TCP server for one Unity client at a time."""

    def __init__(self, cfg: dict, controller, log: RunLog | None = None, port: int | None = None, verbose: bool = True):
        self.cfg = cfg
        self.verbose = verbose
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
        P.validate(P.Message({**h, "version": self.limits.version, "attachments": []}), P.TO_UNITY)
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
                    P.validate(msg, P.FROM_UNITY)
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


async def run(cfg: dict, cfg_path: Path, mode: str, duration_s: float | None) -> Path:
    out = dio.new_run_dir(cfg, f"bridge_{mode}")
    hashes = dio.copy_configs(out, [cfg_path])
    dio.write_json(out / "run_info.json", {
        "created": datetime.now().isoformat(timespec="seconds"), "mode": mode,
        "command": " ".join([Path(sys.executable).name] + sys.argv), "git": dio.git_info(),
        "python": platform.python_version(), "platform": platform.platform(),
        "bridge_config": str(cfg_path), "config_sha256": hashes, "protocol_version": P.PROTOCOL_VERSION})
    log = RunLog(out, cfg["logging"]["save_every_n_frames"])
    controller = HelloController(cfg["hello_test"])
    server = BridgeServer(cfg, controller, log)
    port = await server.start()
    print(f"[bridge] mode {mode}: listening on {cfg['host']}:{port}; run folder {out}", flush=True)
    print("[bridge] press Ctrl+C to stop" + (f" (or wait {duration_s:g} s)" if duration_s else ""), flush=True)
    try:
        if duration_s:
            await asyncio.sleep(duration_s)
        else:
            await asyncio.Event().wait()
    finally:
        await server.close()
        log.close()
        print(f"[bridge] stopped; summary in {out / 'summary.json'}", flush=True)
    return out


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--config", default=DEFAULT_CONFIG)
    ap.add_argument("--mode", choices=["hello"], default="hello")
    ap.add_argument("--duration-s", type=float, default=None, help="stop after this many seconds")
    args = ap.parse_args(argv)
    cfg, cfg_path = load_config(args.config)
    try:
        asyncio.run(run(cfg, cfg_path, args.mode, args.duration_s))
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
