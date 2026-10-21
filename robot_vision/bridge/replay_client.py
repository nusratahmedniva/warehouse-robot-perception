"""Stand-in for Unity that replays saved camera frames to a running bridge server and measures its reply times
(diagnostics only, 2026-10-21; AUDIT.md section 9). No robot, no trial: telemetry says trial_running false, so a guide
server answers idle commands while its perception processes every frame as in a live session. This separates
Python's own stalls from Unity's: the client's clock and the server's are on the same machine.

Run (from robot_vision/, with a server listening, e.g. run_trials.ps1 / run_trials.sh or bridge.server):
    python -m bridge.replay_client --frames outputs/<bridge run>/frames --duration-s 120

Sends hello, telemetry at telemetry_hz, frame_360 at frame_360_hz and frame_pan_tilt at frame_pan_tilt_hz
(bridge.json), cycling through the saved JPEGs of each camera. Writes outputs/replay_<time>/replies.csv (per
telemetry: send time, reply time, round trip) and summary.json (max, mean, p95, count over 300 ms = would-be watchdog
stops, frames sent).
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import math
import statistics
import sys
import time
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import decision_io as dio  # noqa: E402
from bridge import protocol as P  # noqa: E402
from bridge import server as S  # noqa: E402

POSE = {"x": 6.25, "z": -6.0, "yaw_deg": 0.0}


def telemetry(seq: int, t: float) -> dict:
    return {"type": "telemetry", "seq": seq, "time_s": t, "pose": dict(POSE), "v": 0.0, "omega": 0.0, "v_cmd": 0.0,
            "omega_cmd": 0.0, "pan_deg": 0.0, "collision_count": 0, "reached_end_point": False, "trial_index": -1,
            "trial_running": False, "nav_has_target": False, "nav_target_x": 0.0, "nav_target_z": 0.0,
            "nav_status": "none", "nav_start_snap_m": -1.0, "nav_target_snap_m": -1.0, "nav_corners": [],
            "last_command_seq": -1, "rtt_telemetry_seq": -1, "rtt_ms": -1.0, "watchdog_stopped": False,
            "watchdog_count": 0, "keyboard_override": False, "estop": False, "frames_360_sent": 0,
            "frames_360_dropped": 0, "frames_pan_tilt_sent": 0, "frames_pan_tilt_dropped": 0, "realtime_s": t}


def frame_header(kind: str, seq: int, index: int, t: float, w: int, h: int) -> dict:
    head = {"type": kind, "seq": seq, "time_s": t, "frame_index": index, "width": w, "height": h,
            "camera_height_m": 1.6, "pose": dict(POSE), "encoding": "jpeg"}
    if kind == "frame_360":
        head["centre_world_yaw_deg"] = 0.0
    else:
        head.update(fx=458.99, fy=458.99, cx=365.0, cy=265.0, vertical_fov_deg=60.0, pan_deg=0.0, tilt_deg=0.0)
    return head


async def replay(host: str, port: int, cfg: dict, frames: Path, duration_s: float, out: Path) -> dict:
    pano = sorted(frames.glob("frame_360_*.jpg"))
    pan = sorted(frames.glob("frame_pan_tilt_*.jpg"))
    if not pano or not pan:
        raise SystemExit(f"{frames}: need frame_360_*.jpg and frame_pan_tilt_*.jpg")
    pano_b = [p.read_bytes() for p in pano]
    pan_b = [p.read_bytes() for p in pan]
    limits = P.Limits.from_config(cfg)
    for _ in range(600):                       # the server listens only after its models are warmed up
        try:
            reader, writer = await asyncio.open_connection(host, port)
            break
        except OSError:
            await asyncio.sleep(0.5)
    else:
        raise SystemExit(f"no server on {host}:{port}")
    sent: dict[int, float] = {}
    rows: list[tuple[int, float, float, float]] = []
    t0 = time.perf_counter()
    seq = 0

    async def receive():
        while True:
            msg = await P.read_message(reader, limits)
            if msg is None:
                return
            if msg.type == "command" and msg.header["reply_to"] in sent:
                ts = sent.pop(msg.header["reply_to"])
                now = time.perf_counter() - t0
                rows.append((msg.header["reply_to"], round(ts, 4), round(now, 4), round((now - ts) * 1000.0, 3)))

    rx = asyncio.create_task(receive())
    writer.write(P.encode({"type": "hello", "seq": seq, "time_s": 0.0, "client": "replay", "unity_version": "replay",
                           "telemetry_hz": cfg["telemetry_hz"], "frame_360_hz": cfg["frame_360_hz"],
                           "frame_pan_tilt_hz": cfg["frame_pan_tilt_hz"], "watchdog_timeout_s": cfg["watchdog_timeout_s"]}))
    periods = {"telemetry": 1.0 / cfg["telemetry_hz"], "frame_360": 1.0 / cfg["frame_360_hz"],
               "frame_pan_tilt": 1.0 / cfg["frame_pan_tilt_hz"]}
    due = dict.fromkeys(periods, 0.0)
    count = dict.fromkeys(periods, 0)
    while True:
        now = time.perf_counter() - t0
        if now >= duration_s:
            break
        for kind, per in periods.items():
            if now < due[kind]:
                continue
            due[kind] += per
            seq += 1
            if kind == "telemetry":
                sent[seq] = now
                writer.write(P.encode(telemetry(seq, now)))
            else:
                data = (pano_b if kind == "frame_360" else pan_b)[count[kind] % len(pano_b if kind == "frame_360" else pan_b)]
                w, h = (2048, 1024) if kind == "frame_360" else (730, 530)
                writer.write(P.encode(frame_header(kind, seq, count[kind], now, w, h), {"image": data}))
            count[kind] += 1
        await writer.drain()
        await asyncio.sleep(max(0.0, min(due.values()) - (time.perf_counter() - t0)))
    await asyncio.sleep(1.0)
    writer.close()
    rx.cancel()
    with (out / "replies.csv").open("x", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["telemetry_seq", "sent_s", "reply_s", "round_trip_ms"])
        w.writerows(rows)
    rtt = sorted(r[3] for r in rows)
    unanswered = len(sent)
    summary = {"duration_s": duration_s, "frames_dir": str(frames), "sent": count, "answered": len(rows),
               "unanswered": unanswered,
               "round_trip_ms": {"mean": round(statistics.fmean(rtt), 3), "p95": rtt[max(0, math.ceil(0.95 * len(rtt)) - 1)],
                                 "max": rtt[-1]} if rtt else None,
               "over_300ms": sum(1 for x in rtt if x > 300.0), "over_100ms": sum(1 for x in rtt if x > 100.0),
               "note": "round trip measured by this client: telemetry written -> its command read (same machine clock)"}
    dio.write_json(out / "summary.json", summary)
    return summary


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--frames", required=True, help="folder with frame_360_*.jpg and frame_pan_tilt_*.jpg")
    ap.add_argument("--duration-s", type=float, default=120.0)
    ap.add_argument("--config", default=S.DEFAULT_CONFIG)
    ap.add_argument("--port", type=int, default=None)
    args = ap.parse_args(argv)
    cfg, _ = S.load_config(args.config)
    out = dio.new_run_dir(cfg, "replay")
    s = asyncio.run(replay(cfg["host"], args.port or int(cfg["port"]), cfg, dio.resolve(args.frames), args.duration_s, out))
    print(f"[replay] {s['answered']} replies, round trip {s['round_trip_ms']}, over 300 ms: {s['over_300ms']}; {out}")


if __name__ == "__main__":
    main()
