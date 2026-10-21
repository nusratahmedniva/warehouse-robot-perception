"""Task 1 development-session acceptance check (AUDIT.md section 9, item 7; evaluation code, reads ground truth).

For one session (Unity trial runner folder + bridge guide folder) it reports, per trial: the checkpoints visited, the
interaction steps at each (slow down, scan, approach to 2.0 m, ask, FORWARD read and held 1.0 s, execute), asks,
gestures read vs shown, outcome, stale-perception stops, watchdog stops and round trip; per session: max and mean
round trip over all messages, watchdog stops after start-up, dropped frames. Then it checks the four acceptance
criteria, each as met / not met (no criterion is loosened; a missing measurement is "not met: not measured").

Measurement definitions (declared 2026-10-21 with the criteria, before any test of the changes):
- slow down: every speed command in the last 1.0 s of navigation before the stop's scan is at most the frozen
  junction_speed_mps (hri_control.json);
- approach to 2.0 m: the approach state ran, and at the start of the ask the true distance robot centre -> that stop's
  worker centre (Unity truth) is within 2.0 +- 0.3 m (frozen approach_tolerance_m 0.15 + 0.15 m vision distance error);
- read FORWARD held 1.0 s: Python accepted FORWARD at the stop (its dialog accepts only after the frozen 1.0 s hold),
  the worker showed FORWARD, and at least gesture_hold_s passed between the ask and the execute step;
- watchdog stops after start-up: increase of Unity's watchdog counter from the first telemetry of trial 1 to the
  last telemetry of the session;
- round trip (all messages): Unity's per-telemetry window of every reply (rtt_window_max_ms / _sum_ms / _n).

Measurement correction (2026-10-22, AUDIT.md section 9; the criteria are unchanged):
- watchdog stops: Unity's watchdog now stops only when Python does not answer telemetry Unity actually sent within
  0.3 s (watchdog_rule unanswered_sent_telemetry); silences that only the old wall-clock rule caught are counted as
  unity_frame_stall events. Reported side by side: stops (new rule, the criterion) and old-rule stops = stops + Unity
  frame stalls (each stop also meets the old rule);
- round trip: measured on Unity's network threads (telemetry write -> reply received; rtt_clock network_thread);
  the earlier definition (queued on Unity's main thread -> reply) is reported beside it;
- Unity main-thread frame times: every frame (frame_ms_list): count, max, p99, frames over 100 ms;
- resources: resources.csv (bridge/resource_monitor.py) max / mean, when the server ran with --resource-log.

Usage (from robot_vision/): python hri_session_check.py --unity outputs/trials_development_Task1_X --bridge outputs/bridge_guide_Y
Writes outputs/session_check_<time>/ (session_check.json, session_check.md); exit 0 only if every criterion is met.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import re
import sys
from pathlib import Path

import decision_io as dio

HERE = Path(__file__).resolve().parent
APPROACH_TOL_M = 0.3
SLOW_WINDOW_S = 1.0
RTT_LIMIT_MS = 100.0


def read_json(p: Path) -> dict:
    return json.loads(p.read_text(encoding="utf-8"))


def read_csv(p: Path) -> list[dict]:
    with p.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def fnum(x, default=None):
    try:
        return float(x)
    except (TypeError, ValueError):
        return default


def parse_trace(trace: list[str]) -> list[tuple[float, str]]:
    out = []
    for item in trace:
        t, _, state = item.partition(":")
        out.append((float(t), state))
    return out


def worker_positions(session: dict) -> dict[str, tuple[float, float]]:
    """session.json 'workers': ["Worker_C1 (8.75, -4.00)", ...] -> {"C1": (8.75, -4.0)}."""
    out = {}
    for w in session.get("workers", []):
        m = re.match(r"Worker_(\w+) \(([-\d.]+), ([-\d.]+)\)", w)
        if m:
            out[m.group(1)] = (float(m.group(2)), float(m.group(3)))
    return out


def stop_segments(trace: list[tuple[float, str]]) -> list[dict]:
    """Split the state trace at every scan: [{t_scan, states: [(t, state)...]}], states up to the next navigate."""
    segs = []
    for i, (t, s) in enumerate(trace):
        if s != "scan":
            continue
        states = [(t, s)]
        for t2, s2 in trace[i + 1:]:
            states.append((t2, s2))
            if s2 in ("navigate", "done", "aborted", "scan"):
                break
        segs.append({"t_scan": t, "states": states})
    return segs


def first(states, name):
    return next((t for t, s in states if s == name), None)


def frame_stats(ms: list[float]) -> dict | None:
    if not ms:
        return None
    v = sorted(ms)
    return {"frames": len(v), "max_ms": round(v[-1], 1), "p99_ms": round(v[min(len(v) - 1, math.ceil(0.99 * len(v)) - 1)], 1),
            "over_100ms": sum(1 for x in v if x > 100.0)}


def window_rtt(tel: list[dict], prefix: str) -> dict:
    n = sum(h.get(f"{prefix}_n", 0) for h in tel)
    mx = max((h.get(f"{prefix}_max_ms", -1.0) for h in tel if h.get(f"{prefix}_n", 0) > 0), default=None)
    sm = sum(h.get(f"{prefix}_sum_ms", 0.0) for h in tel)
    return {"n": n, "max": round(mx, 3) if mx is not None else None, "mean": round(sm / n, 3) if n else None}


def increase(tel: list[dict], key: str):
    v = [h[key] for h in tel if isinstance(h.get(key), int)]
    return (max(v) - min(v)) if v else None


def telemetry_measures(tel: list[dict]) -> dict:
    """Watchdog (new and old rule), round trip (network-thread and queued clock), frame times of these telemetry."""
    stops, stalls = increase(tel, "watchdog_count"), increase(tel, "unity_frame_stall_count")
    events = [e for h in tel for e in (h.get("watchdog_events") or [])]
    frames = [float(x) for h in tel for x in (h.get("frame_ms_list") or [])]
    clock = next((h["rtt_clock"] for h in tel if h.get("rtt_clock")), None)
    # Unity builds before 2026-10-22 had no rtt_clock: their rtt_window_* is the queued (main-thread) clock.
    none = {"n": 0, "max": None, "mean": None}
    network = window_rtt(tel, "rtt_window") if clock else none
    queued = window_rtt(tel, "rtt_queue_window") if clock else window_rtt(tel, "rtt_window")
    if not clock:                       # old build: its watchdog_count is the old wall-clock rule
        stops, stalls, old = None, None, stops
    else:
        old = stops + stalls if stops is not None and stalls is not None else None
    return {"watchdog_stops": stops, "unity_frame_stalls": stalls, "old_rule_stops": old,
            "watchdog_events": [{k: (round(v, 1) if isinstance(v, float) else v) for k, v in e.items()} for e in events],
            "round_trip_ms": network, "round_trip_queued_ms": queued, "rtt_clock": clock or "main_thread_queued (old build)",
            "unity_frames": frame_stats(frames)}


def check_trial(i: int, unity: Path, bridge: Path, stops: list[str], workers: dict, ctl: dict, telemetry: list[dict]) -> dict:
    truth = read_json(unity / f"truth_run{i:03d}.json")
    tcsv = read_csv(unity / f"truth_run{i:03d}.csv")
    pyf = bridge / f"python_trial_{i:03d}.json"
    py = read_json(pyf) if pyf.exists() else {"trace": [], "junctions": []}
    dec = [r for r in read_csv(bridge / "decisions.csv") if r["trial"] == str(i)]
    shown = {s["junction"]: s["shown"] for s in truth.get("shown", [])}
    segs = stop_segments(parse_trace(py.get("trace", [])))
    jrec = {j["junction"]: j for j in py.get("junctions", [])}
    hold = ctl["dialog"]["gesture_hold_s"]
    per_stop = []
    for k, stop in enumerate(stops):
        seg = segs[k] if k < len(segs) else None
        j = jrec.get(stop)
        st = seg["states"] if seg else []
        t_scan = seg["t_scan"] if seg else None
        t_app, t_ask, t_read, t_exec = first(st, "approach"), first(st, "ask"), first(st, "read"), first(st, "execute")
        nav = [fnum(r["v_cmd"], 0.0) for r in dec if t_scan is not None and r["state"].startswith("navigate")
               and t_scan - SLOW_WINDOW_S <= fnum(r["time_s"], -1e9) < t_scan]
        slow = bool(nav) and max(nav) <= ctl["drive"]["junction_speed_mps"] + 1e-6
        dist = None
        if t_ask is not None and stop in workers and tcsv:
            row = min(tcsv, key=lambda r: abs(fnum(r["time_s"], 1e9) - t_ask))
            wx, wz = workers[stop]
            dist = round(((fnum(row["robot_x"]) - wx) ** 2 + (fnum(row["robot_z"]) - wz) ** 2) ** 0.5, 3)
        approached = t_app is not None and dist is not None and abs(dist - ctl["dialog"]["approach_distance_m"]) <= APPROACH_TOL_M
        read_ok = (j is not None and j.get("result") == "accepted" and j.get("read") == "FORWARD"
                   and shown.get(stop) == "FORWARD" and t_ask is not None and t_exec is not None and t_exec - t_ask >= hold - 1e-6)
        steps = {"visited": j is not None, "slow_down": slow, "scan": t_scan is not None, "approach_2m": approached,
                 "ask": t_ask is not None, "read_forward_held_1s": read_ok, "execute": t_exec is not None}
        per_stop.append({"stop": stop, "junction_in_python_log": j["junction"] if j else None, **steps,
                         "all_steps": all(steps.values()), "asks": j.get("asks") if j else None,
                         "shown": shown.get(stop, "unknown"), "read": j.get("read") if j else "NONE",
                         "max_v_cmd_last_1s_before_scan": max(nav) if nav else None,
                         "robot_worker_distance_at_ask_m": dist,
                         "ask_to_execute_s": round(t_exec - t_ask, 3) if t_ask is not None and t_exec is not None else None})
    # stale-perception stops: transitions into safety == "perception stale" in this trial's 0.1 s rows
    stale_events, prev = 0, ""
    for r in sorted(dec, key=lambda r: fnum(r["time_s"], 0.0)):
        cur = r.get("safety", "")
        stale_events += int(cur == "perception stale" and prev != "perception stale")
        prev = cur
    tel = [h for h in telemetry if h.get("trial_index") == i]
    m = telemetry_measures(tel)
    return {"trial": i, "outcome": truth.get("outcome"), "failure_reason": truth.get("failure_reason"),
            "detail": truth.get("detail"), "stops": per_stop,
            "checkpoints_visited": sum(s["visited"] for s in per_stop), "checkpoints": len(stops),
            "full_interaction_at_every_stop": all(s["all_steps"] for s in per_stop),
            "asks": [s["asks"] for s in per_stop], "shown_vs_read": [f"{s['stop']}:{s['shown']}>{s['read']}" for s in per_stop],
            "stale_perception_stops": stale_events,
            "stale_perception_stop_s": round(sum(0.1 for r in dec if r.get("safety") == "perception stale"), 1),
            **m}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--unity", required=True)
    ap.add_argument("--bridge", required=True)
    args = ap.parse_args(argv)
    unity, bridge = dio.resolve(args.unity), dio.resolve(args.bridge)
    session = read_json(unity / "session.json")
    ctl = read_json(HERE / "configs" / "hri_control.json")
    stops = session.get("task1_stops") or []
    workers = worker_positions(session)
    telemetry = []
    for line in (bridge / "messages.jsonl").open(encoding="utf-8"):
        m = json.loads(line)
        if m.get("dir") == "in" and m.get("type") == "telemetry":
            telemetry.append(m["header"])
    n = int(session["trials"])
    trials = [check_trial(i, unity, bridge, stops, workers, ctl, telemetry) for i in range(1, n + 1)
              if (unity / f"truth_run{i:03d}.json").exists()]
    summary = read_json(bridge / "summary.json") if (bridge / "summary.json").exists() else {}
    running = [h for h in telemetry if h.get("trial_running")]
    after_start = None
    session_m = telemetry_measures(telemetry[telemetry.index(running[0]):]) if running else None
    if running:
        k0 = telemetry.index(running[0])
        after_start = telemetry[-1]["watchdog_count"] - telemetry[k0]["watchdog_count"]
    allm = summary.get("round_trip", {}).get("all_messages")
    queued = summary.get("round_trip", {}).get("all_messages_queued")
    looks = session.get("worker_appearance", "")
    appearance_ok = (len(workers) == len(stops) > 0 and all(f"Worker_{s}:" in looks for s in stops)
                     and looks.count("Universal Render Pipeline/Lit") == len(stops) and "missing" not in looks
                     and "InternalErrorShader" not in looks)
    pose_visible = bool(trials) and all(s["read"] == "FORWARD" for t in trials for s in t["stops"])
    criteria = {
        "1_full_interaction_every_trial_every_checkpoint": bool(trials) and len(trials) == n
            and all(t["full_interaction_at_every_stop"] and t["checkpoints_visited"] == len(stops) for t in trials),
        "2_workers_textured_and_arm_pose_read": appearance_ok and pose_visible,
        "3a_zero_watchdog_stops_after_start_up": after_start == 0,
        "3b_max_round_trip_all_messages_under_100ms": bool(allm) and allm["max_ms"] < RTT_LIMIT_MS,
        "4_every_trial_outcome_recorded": len(trials) == n and all(t["outcome"] in ("SUCCESS", "FAILURE") for t in trials),
    }
    result = {"unity_folder": unity.name, "bridge_folder": bridge.name, "task": session.get("task"),
              "mode": session.get("mode"), "seed": session.get("seed"), "trials_expected": n, "trials_recorded": len(trials),
              "stops": stops, "workers": workers, "worker_appearance": looks,
              "session": {"round_trip_all_messages": allm, "round_trip_all_messages_queued_clock": queued,
                          "after_start_up": session_m, "resources": summary.get("resources"),
                          "watchdog_rule": (summary.get("watchdog") or {}).get("rule"),
                          "round_trip_unity_latest_only": {
                              k: summary.get("round_trip", {}).get(k) for k in ("n", "mean_ms", "max_ms")},
                          "watchdog_stops_total": summary.get("watchdog_count_reported_by_unity"),
                          "watchdog_stops_after_start_up": after_start,
                          "python_receive_lag": summary.get("python_receive_lag"), "unity_frames": summary.get("unity_frames"),
                          "event_loop_lag": {k: (summary.get("event_loop_lag") or {}).get(k) for k in ("over_threshold", "max_lag_ms")},
                          "frames_dropped_by_unity": {k: (summary.get("frames") or {}).get(k, {}).get("dropped_by_unity") for k in ("360", "pan_tilt")},
                          "frames_dropped_by_python": {k: v.get("dropped") for k, v in (summary.get("perception") or {}).items() if isinstance(v, dict)}},
              "criteria": criteria, "all_met": all(criteria.values()), "trials": trials,
              "definitions": __doc__.split("Measurement definitions")[1].split("Usage")[0].strip()}
    out = dio.new_run_dir({"paths": {"output_root": "outputs"}}, "session_check")
    dio.write_json(out / "session_check.json", result)
    md = [f"# Session check {unity.name} + {bridge.name}", "",
          "| trial | outcome | checkpoints visited | full interaction | asks | shown>read | stale stops | watchdog (new rule) | "
          "old-rule stops | rtt max ms (network) | rtt max ms (queued) | frames max / p99 ms, over 100 ms |",
          "|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for t in trials:
        uf = t["unity_frames"] or {}
        md.append(f"| {t['trial']} | {t['outcome']} {'' if t['failure_reason'] == 'none' else t['failure_reason']} | "
                  f"{t['checkpoints_visited']}/{t['checkpoints']} | {'yes' if t['full_interaction_at_every_stop'] else 'NO'} | "
                  f"{t['asks']} | {', '.join(t['shown_vs_read'])} | {t['stale_perception_stops']} ({t['stale_perception_stop_s']} s) | "
                  f"{t['watchdog_stops']} | {t['old_rule_stops']} | {t['round_trip_ms']['max']} | {t['round_trip_queued_ms']['max']} | "
                  f"{uf.get('max_ms')} / {uf.get('p99_ms')}, {uf.get('over_100ms')} |")
    sm = session_m or {}
    md += ["", f"Session: round trip all messages {allm}; queued clock {queued}; watchdog stops after start-up {after_start} "
               f"(total {summary.get('watchdog_count_reported_by_unity')}); old-rule stops after start-up {sm.get('old_rule_stops')} "
               f"(Unity frame stalls {sm.get('unity_frame_stalls')}); Unity frames after start-up {sm.get('unity_frames')}; "
               f"dropped frames Unity {result['session']['frames_dropped_by_unity']}, Python "
               f"{result['session']['frames_dropped_by_python']}.", ""]
    for e in sm.get("watchdog_events") or []:
        md.append(f"- event {e.get('kind')} ({e.get('cause')}): gap {e.get('gap_ms')} ms, longest Unity frame "
                  f"{e.get('frame_ms_max')} ms, at Unity real time {e.get('start_realtime_s')} s")
    md.append("")
    md += [f"- {k}: {'MET' if v else 'NOT MET'}" for k, v in criteria.items()]
    (out / "session_check.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print("\n".join(md))
    print(f"Folder: {out}")
    return 0 if result["all_met"] else 1


if __name__ == "__main__":
    sys.exit(main())
