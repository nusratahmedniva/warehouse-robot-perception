"""v4 timing check (AUDIT.md section 14.14): does the v4 server answer Unity's telemetry fast enough while the real models run?

Starts the v4 guide server (real models, protocol 3) and replays saved camera frames to it at the real rates (20 Hz
telemetry, 5 Hz panorama, 10 Hz pan-tilt, bridge/replay_client.py, a stand-in for Unity with no robot and no trial), then
reads what the server and the client measured:

  loop lag        how late the server's 10 ms asyncio sleep wakes up (max, p99): the loop could not run
  round trip      telemetry written -> its command read, as the client sees it (p99, max)
  reply gap       time between two consecutive commands: the silence Unity's watchdog (0.3 s) sees
  stall stacks    the Python stacks of all threads when the loop stalled (stall_tracebacks.txt)
  perception      frames processed / dropped per camera, worker events (died, behind) when workers are processes

and compares them with the limits declared in configs/v4/bridge.json -> timing_limits. Exit status 0 = every limit met (or no
limits declared yet: numbers only), 1 = a limit missed, 2 = the run itself failed.

Run from robot_vision/ with the project venv (real models: YOLO11s-pose weights in models/, the MediaPipe submodule):
    python timing_check_v4.py --frames outputs/<bridge run with saved frames>/frames --duration-s 60
The replay shows saved frames: it measures the Python side only. Unity's own load (Editor rendering on the same machine) is not
in it, so run it on the machine the final runs use, with the run protocol of AUDIT.md section 9 (other apps closed, Best
performance, mains power). Nothing is tuned on it; the limits are in the config.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import platform
import re
import socket
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import decision_io as dio  # noqa: E402
from bridge import machine_state  # noqa: E402
from bridge import replay_client as R  # noqa: E402
from bridge import timing_v4 as T  # noqa: E402

DEFAULT_CONFIG = "configs/v4/bridge.json"
LISTEN_RE = re.compile(r"listening on \S+; run folder (.+)$", re.M)


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def read_text(p: Path) -> str:
    return p.read_text(encoding="utf-8", errors="replace") if p.exists() else ""


def wait_for_listening(proc: subprocess.Popen, log: Path, timeout_s: float) -> Path:
    """The server loads and warms the models first, then prints its run folder. Returns that folder."""
    t0 = time.monotonic()
    while time.monotonic() - t0 < timeout_s:
        m = LISTEN_RE.search(read_text(log))
        if m:
            return Path(m.group(1).strip())
        if proc.poll() is not None:
            raise SystemExit(f"the server stopped before it listened (exit {proc.returncode}); see {log.name}:\n" + read_text(log)[-1500:])
        time.sleep(0.5)
    proc.terminate()
    raise SystemExit(f"the server did not listen within {timeout_s:g} s; see {log.name}")


def measure(server_dir: Path, replay_dir: Path, replay_summary: dict, limits: dict | None) -> dict:
    summary = json.loads((server_dir / "summary.json").read_text(encoding="utf-8"))
    loop = summary["event_loop_lag"]
    allv = loop.get("all_samples") or {}
    replies = T.read_replies(replay_dir / "replies.csv")
    rs = T.reply_stats(replies, replay_summary["unanswered"])
    perc = summary.get("perception") or {}
    events = perc.get("worker_events") or []
    measured = {
        "loop_lag_p99_ms": allv.get("p99_ms"), "loop_lag_max_ms": allv.get("max_ms", loop.get("max_lag_ms")),
        "reply_gap_max_ms": (rs.get("reply_gap_ms") or {}).get("max"),
        "round_trip_p99_ms": (rs.get("round_trip_ms") or {}).get("p99"),
        "round_trip_max_ms": (rs.get("round_trip_ms") or {}).get("max"),
        "unanswered_telemetry": rs["unanswered"], "perception_worker_events": len(events)}
    tb = read_text(server_dir / "stall_tracebacks.txt")
    return {"measured": measured, "loop_lag": loop, "replies": rs, "server_handle": T.handle_stats(server_dir / "messages.jsonl"),
            "perception": perc, "python_receive_lag": summary.get("python_receive_lag"), "gc_pauses": summary.get("gc_pauses"),
            "watchdog_would_stop_over_300ms": rs.get("round_trip_ms", {}).get("over_300ms"),
            "stall_dumps": tb.count("--- the stall dumped above"), "stall_traceback_bytes": len(tb),
            "evaluation": T.evaluate(limits, measured)}


def markdown(rep: dict) -> str:
    m, ev, L = rep["result"]["measured"], rep["result"]["evaluation"], []
    L += [f"# v4 timing check: {rep['label'] or 'unlabelled'}", "",
          f"Perception workers: **{rep['perception_mode']}**. Replay {rep['duration_s']:g} s at 20 Hz telemetry, 5 Hz panorama, 10 Hz "
          f"pan-tilt, protocol 3, real models. Git `{(rep['git'].get('commit') or '?')[:10]}`"
          + (" (uncommitted changes)" if rep["git"].get("uncommitted_changes") else "") + f". Machine: {rep['platform']}.", ""]
    if ev["declared"]:
        L += ["## Limits (configs/v4/bridge.json -> timing_limits)", "", "| metric | measured | limit | |", "|---|---|---|---|"]
        L += [f"| {c['metric']} | {c['value']} | <= {c['limit']} | {'ok' if c['ok'] else '**MISSED**'} |" for c in ev["checks"]]
        L += ["", f"**{'All limits met' if ev['passed'] else 'A limit was missed'}.**", ""]
    else:
        L += ["No limits declared: numbers only.", "", "| metric | measured |", "|---|---|"] + [f"| {k} | {v} |" for k, v in m.items()] + [""]
    lag, rs = rep["result"]["loop_lag"].get("all_samples") or {}, rep["result"]["replies"]
    L += ["## Event-loop lag (server, 10 ms sleeps)", "", json.dumps(lag), "",
          f"Worst wake-ups: {rep['result']['loop_lag'].get('worst')}", "",
          "## Telemetry -> command (client side)", "", f"round trip: {json.dumps(rs.get('round_trip_ms'))}", "",
          f"gap between consecutive commands: {json.dumps(rs.get('reply_gap_ms'))}", "",
          f"unanswered telemetry: {rs['unanswered']}; round trips over 300 ms (would-be watchdog stops): "
          f"{rep['result']['watchdog_would_stop_over_300ms']}", "",
          f"Server-side handling per telemetry (event loop): {json.dumps(rep['result']['server_handle'])}", "",
          f"Python receive lag (server read later than the earliest message): {json.dumps(rep['result']['python_receive_lag'])}", "",
          f"Garbage collection: {json.dumps(rep['result']['gc_pauses'])}", "", "## Perception", "",
          "```json", json.dumps(rep["result"]["perception"], indent=2), "```", "",
          f"## Stall stacks: {rep['result']['stall_dumps']} dump(s) in stall_tracebacks.txt", ""]
    if rep["stall_traceback_excerpt"]:
        L += ["```", rep["stall_traceback_excerpt"], "```", ""]
    L += [f"Server run folder: `{rep['server_run_folder']}`. Replay client: `replay/` here.", ""]
    return "\n".join(L)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--frames", required=True, help="folder with frame_360_*.jpg and frame_pan_tilt_*.jpg (a bridge run's frames/)")
    ap.add_argument("--duration-s", type=float, default=60.0)
    ap.add_argument("--config", default=DEFAULT_CONFIG)
    ap.add_argument("--label", default="")
    ap.add_argument("--task", choices=["Task1", "Task2"], default="Task2")
    ap.add_argument("--workers", choices=["config", "threads", "processes"], default="config",
                    help="where the models run: threads in the server process or worker processes (default: the config's "
                         "perception_workers.mode); written to a copy of the config, the repository file is not changed")
    ap.add_argument("--device", choices=["auto", "cpu", "cuda", "mps"], default="auto",
                    help="inference device (default: the perception config's, CUDA then MPS then CPU); written to a copy of the "
                         "perception config, the repository file is not changed")
    ap.add_argument("--ready-timeout-s", type=float, default=600.0, help="how long to wait for the models to load")
    a = ap.parse_args(argv)
    cfg_path = dio.resolve(a.config)
    cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
    if cfg.get("protocol_version") != 3:
        raise SystemExit("the timing check is for the v4 server: --config configs/v4/bridge.json (protocol 3)")
    frames = dio.resolve(a.frames)
    out = dio.new_run_dir(cfg, "timing_check_v4")
    port = free_port()
    cfg_run = {**cfg, "port": port}                   # a free port so a running Unity or server is never touched
    if a.workers != "config":
        cfg_run["perception_workers"] = {**(cfg.get("perception_workers") or {}), "mode": a.workers}
    run_cfg = out / "bridge_config_run.json"
    dio.write_json(run_cfg, cfg_run)
    log = out / "server.log"
    cmd = [sys.executable, "-m", "bridge.server", "--config", str(run_cfg), "--mode", "guide", "--task", a.task,
           "--perception", "vision", "--exit-on-disconnect", "--duration-s", str(a.duration_s + a.ready_timeout_s)]
    if a.device != "auto":
        pcfg = json.loads(dio.resolve("configs/hri_perception.json").read_text(encoding="utf-8"))
        pcfg["device"] = a.device
        dio.write_json(out / "hri_perception_run.json", pcfg)
        cmd += ["--perception-config", str(out / "hri_perception_run.json")]
    print(f"[timing] starting the v4 server (models load first, up to {a.ready_timeout_s:g} s) ...", flush=True)
    with log.open("w", encoding="utf-8") as lf:
        proc = subprocess.Popen(cmd, cwd=HERE, stdout=lf, stderr=subprocess.STDOUT)
        try:
            server_dir = wait_for_listening(proc, log, a.ready_timeout_s)
            print(f"[timing] server listening on port {port}; replaying {a.duration_s:g} s ...", flush=True)
            (out / "replay").mkdir()
            try:
                rsum = asyncio.run(R.replay(cfg["host"], port, cfg_run, frames, a.duration_s, out / "replay"))
            except (ConnectionError, OSError) as e:
                proc.poll()
                print(f"[timing] the server closed the connection ({type(e).__name__}); server exit status {proc.returncode}. "
                      f"End of {log.name}:\n{read_text(log)[-1200:]}", flush=True)
                return 2
            try:
                proc.wait(timeout=180)
            except subprocess.TimeoutExpired:
                proc.terminate()
                proc.wait(timeout=30)
        finally:
            if proc.poll() is None:
                proc.terminate()
    if not (server_dir / "summary.json").exists():
        print(f"[timing] the server wrote no summary.json; see {log}", flush=True)
        return 2
    result = measure(server_dir, out / "replay", rsum, cfg.get("timing_limits"))
    tb = read_text(server_dir / "stall_tracebacks.txt")
    rep = {"label": a.label, "perception_mode": (cfg_run.get("perception_workers") or {}).get("mode", "threads"),
           "duration_s": a.duration_s, "git": dio.git_info(), "platform": platform.platform(), "python": platform.python_version(),
           "machine_state": machine_state.read(), "config": a.config, "config_sha256": dio.sha256(cfg_path), "device": a.device,
           "server_run_folder": "{output_root}/" + server_dir.name, "replay_summary": rsum, "result": result,
           "stall_traceback_excerpt": tb[:6000], "command": "timing_check_v4.py " + " ".join(argv if argv is not None else sys.argv[1:])}
    dio.write_json(out / "report.json", rep)
    (out / "report.md").write_text(markdown(rep), encoding="utf-8")
    print((out / "report.md").read_text(encoding="utf-8"))
    print(f"[timing] folder: {out}", flush=True)
    ev = result["evaluation"]
    return 1 if ev["declared"] and not ev["passed"] else 0


if __name__ == "__main__":
    sys.exit(main())
