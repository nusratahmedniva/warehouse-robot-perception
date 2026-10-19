"""Step 3: TCP bridge server for the Unity guided-robot scene (protocol v1, docs/protocol.md).

Unity connects as the client and sends a hello, then an observation (robot pose, state, JPEG images) every
0.1 s. The server answers every observation with a perception message (ack_seq = the observation's seq, so
Unity measures the round-trip delay) and sends a heartbeat whenever it has been silent for heartbeat_s, so
Unity's 0.3 s watchdog only fires when Python is really gone.

Perception is a STUB until Step 4: no people, gesture NONE, labelled as such. No reference data is read.

Each server process writes a new folder <output_root>/bridge_<date>_<time>/ with the exact config, run.json
(git commit, versions) and per connection conn_###/: hello.json, frames.csv (one row per received frame),
summary.json and every n-th observation's images.

Usage (from robot_vision/):
    .venv python hri_bridge_server.py                       # configs/bridge.json, runs until Ctrl+C
    .venv python hri_bridge_server.py --max-seconds 120     # stop after 2 minutes
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import select
import signal
import socket
import threading
import time
from pathlib import Path

import hri_protocol as hp

HERE = Path(__file__).resolve().parent
DEFAULT_CONFIG = HERE / "configs" / "bridge.json"

FRAME_FIELDS = ["recv_s", "seq", "type", "t_unity", "t_sim", "state", "robot_x", "robot_z", "heading_deg",
                "n_images", "image_bytes", "images_ok", "inference_total_ms", "reply_seq"]


class StubPerception:
    """Placeholder until Step 4: reports nothing. Its label goes into every reply and log."""

    label = "stub (no perception until Step 4)"

    def process(self, frame: hp.Frame) -> dict:
        return {"people": [], "command": "NONE", "confidence": 0.0, "inference": []}


def check_images(frame: hp.Frame) -> tuple[bool, list[str]]:
    """Every image must decode as JPEG with the size the header states. Returns (all ok, problems)."""
    from PIL import Image  # lazy: the protocol tests do not need Pillow

    problems = []
    for entry, data in zip(frame.header.get("images", []), frame.images):
        try:
            with Image.open(io.BytesIO(data)) as im:
                im.load()
                if im.format != "JPEG":
                    problems.append(f"{entry.get('name')}: format {im.format}")
                elif (im.width, im.height) != (entry.get("width"), entry.get("height")):
                    problems.append(f"{entry.get('name')}: {im.width}x{im.height}, header says "
                                    f"{entry.get('width')}x{entry.get('height')}")
        except Exception as e:  # noqa: BLE001 - any decoder error means a bad image
            problems.append(f"{entry.get('name')}: {e}")
    return not problems, problems


class BridgeServer:
    """One Unity client at a time. start() binds and serves in a background thread; stop() ends it."""

    def __init__(self, cfg: dict, perception=None, run_dir: Path | None = None, log=print):
        self.cfg = cfg
        self.perception = perception or StubPerception()
        self.run_dir = run_dir
        self.log = log
        self.heartbeat_s = float(cfg["heartbeat_s"])
        self.read_timeout_s = float(cfg.get("frame_read_timeout_s", 5.0))
        self.save_every = int(cfg.get("save_images_every_n", 0))
        self._stop = threading.Event()
        self._sock: socket.socket | None = None
        self._thread: threading.Thread | None = None
        self.connections = 0
        self.port: int | None = None

    def start(self) -> int:
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._sock.bind((self.cfg["host"], int(self.cfg["port"])))
        self._sock.listen(1)
        self._sock.settimeout(0.2)
        self.port = self._sock.getsockname()[1]
        self._thread = threading.Thread(target=self._serve, name="bridge-server", daemon=True)
        self._thread.start()
        self.log(f"Bridge listening on {self.cfg['host']}:{self.port} (perception: {self.perception.label})")
        return self.port

    def stop(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=5)
        if self._sock is not None:
            self._sock.close()

    def _serve(self) -> None:
        while not self._stop.is_set():
            try:
                conn, addr = self._sock.accept()
            except (socket.timeout, OSError):
                continue
            self.connections += 1
            self.log(f"Unity connected from {addr[0]}:{addr[1]} (connection {self.connections})")
            with conn:
                conn.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
                try:
                    Session(self, conn, self.connections).run()
                except Exception as e:  # noqa: BLE001 - one bad session must not stop the server
                    self.log(f"Session failed: {e!r}")
            self.log("Unity disconnected")


class Session:
    """One connection: answer frames, keep the heartbeat, log every frame."""

    def __init__(self, server: BridgeServer, conn: socket.socket, index: int):
        self.s = server
        self.conn = conn
        self.seq = 0
        self.t0 = time.monotonic()
        self.last_sent = 0.0
        self.counts: dict[str, int] = {}
        self.max_gap_s = 0.0
        self.last_obs_recv: float | None = None
        self.bad_images = 0
        self.inference_ms: list[float] = []
        self.end_reason = ""
        self.dir = None
        if server.run_dir is not None:
            self.dir = server.run_dir / f"conn_{index:03d}"
            self.dir.mkdir(parents=True, exist_ok=False)
            # Line-buffered, so the rows survive the process being killed.
            self._csv_file = (self.dir / "frames.csv").open("x", newline="", encoding="utf-8", buffering=1)
            self.csv = csv.DictWriter(self._csv_file, fieldnames=FRAME_FIELDS)
            self.csv.writeheader()

    def send(self, header: dict, images=()) -> None:
        hp.send_frame(self.conn, header, list(images))
        self.last_sent = time.monotonic()

    def next_seq(self) -> int:
        self.seq += 1
        return self.seq

    def run(self) -> None:
        try:
            while not self.s._stop.is_set():
                wait = max(0.0, self.s.heartbeat_s - (time.monotonic() - self.last_sent))
                readable, _, _ = select.select([self.conn], [], [], wait)
                if readable:
                    self.conn.settimeout(self.s.read_timeout_s)
                    frame = hp.read_frame(self.conn)
                    if not self.handle(frame):
                        self.end_reason = "bye"
                        break
                if time.monotonic() - self.last_sent >= self.s.heartbeat_s:
                    self.send(hp.message("heartbeat", self.next_seq(), time.monotonic()))
            else:
                self.end_reason = "server stopped"
        except (ConnectionError, OSError) as e:
            self.end_reason = f"connection: {e}"
        except hp.ProtocolError as e:
            self.end_reason = f"protocol error: {e}"
            self.s.log(f"Closing connection: {e}")
        except Exception as e:  # noqa: BLE001 - recorded in summary.json, then re-raised to the server log
            self.end_reason = f"error: {e!r}"
            raise
        finally:
            self.close()

    def handle(self, frame: hp.Frame) -> bool:
        h = frame.header
        now = time.monotonic()
        kind = h["type"]
        self.counts[kind] = self.counts.get(kind, 0) + 1
        row = {"recv_s": f"{now - self.t0:.4f}", "seq": h.get("seq"), "type": kind, "t_unity": h.get("t"),
               "n_images": len(frame.images),
               "image_bytes": ";".join(f"{e.get('name')}:{e.get('bytes')}" for e in h.get("images", []))}
        reply_seq = None
        if kind == "hello":
            if self.dir is not None:
                (self.dir / "hello.json").write_text(json.dumps(h, indent=2) + "\n", encoding="utf-8")
            reply_seq = self.next_seq()
            self.send(hp.message("hello_ack", reply_seq, time.monotonic(), server="robot_vision",
                                 perception=self.s.perception.label))
        elif kind == "observation":
            if self.last_obs_recv is not None:
                self.max_gap_s = max(self.max_gap_s, now - self.last_obs_recv)
            self.last_obs_recv = now
            t_start = time.perf_counter()
            ok, problems = check_images(frame)
            if not ok:
                self.bad_images += 1
                self.s.log("Image problem: " + "; ".join(problems))
            result = self.s.perception.process(frame)
            total_ms = (time.perf_counter() - t_start) * 1000.0
            self.inference_ms.append(total_ms)
            reply_seq = self.next_seq()
            self.send(hp.perception_reply(reply_seq, time.monotonic(), ack_seq=h.get("seq"),
                                          label=self.s.perception.label, people=result["people"],
                                          command=result["command"], confidence=result["confidence"],
                                          inference=result["inference"], total_ms=total_ms))
            robot = h.get("robot", {})
            row.update(t_sim=h.get("t_sim"), state=h.get("state"), robot_x=robot.get("x"), robot_z=robot.get("z"),
                       heading_deg=robot.get("heading_deg"), images_ok=int(ok),
                       inference_total_ms=f"{total_ms:.3f}")
            self.save_images(frame)
        elif kind == "bye":
            self.s.log(f"Unity said bye: {h.get('reason', '')}")
        else:
            self.s.log(f"Ignoring unknown message type {kind!r}")
        row["reply_seq"] = reply_seq
        if self.dir is not None:
            self.csv.writerow(row)
        return kind != "bye"

    def save_images(self, frame: hp.Frame) -> None:
        n = self.counts.get("observation", 0)
        if self.dir is None or self.s.save_every <= 0 or (n - 1) % self.s.save_every != 0:
            return  # saves observations 1, 1 + n, 1 + 2n, ...
        img_dir = self.dir / "images"
        img_dir.mkdir(exist_ok=True)
        for e, data in zip(frame.header.get("images", []), frame.images):
            (img_dir / f"obs{frame.header.get('seq'):06d}_{e.get('name')}.jpg").write_bytes(data)

    def close(self) -> None:
        if self.dir is None:
            return
        self._csv_file.close()
        inf = sorted(self.inference_ms)
        summary = {"end_reason": self.end_reason, "duration_s": round(time.monotonic() - self.t0, 3),
                   "frames_received": self.counts, "frames_sent": self.seq,
                   "observations_with_bad_images": self.bad_images,
                   "max_gap_between_observations_s": round(self.max_gap_s, 4),
                   "server_processing_ms": {"mean": round(sum(inf) / len(inf), 3) if inf else None,
                                            "max": round(inf[-1], 3) if inf else None},
                   "perception": self.s.perception.label}
        (self.dir / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")


def load_config(path: Path) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def main() -> None:
    import decision_io as dio  # run-folder helpers (timestamped folder, git info, config copy)

    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--config", default=str(DEFAULT_CONFIG))
    p.add_argument("--port", type=int, help="overrides the configured port")
    p.add_argument("--max-seconds", type=float, help="stop after this many seconds")
    a = p.parse_args()
    cfg_path = Path(a.config)
    cfg = load_config(cfg_path)
    if a.port is not None:
        cfg["port"] = a.port
    out = dio.new_run_dir(cfg, "bridge")
    hashes = dio.copy_configs(out, [cfg_path])
    dio.write_json(out / "run.json", {"git": dio.git_info(), "config_sha256": hashes, "port": cfg["port"],
                                      "protocol_version": hp.VERSION, "perception": StubPerception.label})
    server = BridgeServer(cfg, run_dir=out)
    server.start()

    def on_sigterm(*_):
        raise KeyboardInterrupt  # same clean shutdown as Ctrl+C (summary.json is written)
    signal.signal(signal.SIGTERM, on_sigterm)
    print(f"Run folder: {out.relative_to(HERE) if out.is_relative_to(HERE) else out.name}", flush=True)
    t_end = time.monotonic() + a.max_seconds if a.max_seconds else None
    try:
        while t_end is None or time.monotonic() < t_end:
            time.sleep(0.2)
    except KeyboardInterrupt:
        pass
    finally:
        server.stop()
        print("Bridge stopped.", flush=True)


if __name__ == "__main__":
    main()
