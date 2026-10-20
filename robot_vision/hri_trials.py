"""Step 7: per-run log of the guided-robot trials (one JSON per run + results.csv), from the two sides of a session.

Unity's trial runner folder (trials_<mode>_<task>_<time>/) holds the ground truth: goal B, where the robot stopped,
travelled distance, speeds, collisions, closest distance to the worker, what the worker showed at each junction.
The bridge's guide run folder (bridge_guide_<time>/) holds what Python did: per-trial state machine summary
(python_trial_###.json: per-step times, junction readings, abort reason), decisions.csv (0.1 s; round trip,
watchdog, safety reason) and perception.csv (per-model inference time per frame). This is evaluation code: it may
read truth; inference code never imports it.

Times (each log row counts until the next row of the trial; rows every 0.1 s):
- total_s: Unity's trial time.
- stale_stop_s: time Python held the robot because perception was stale (decisions.csv safety "perception stale").
- time_excl_stale_stops_s = total_s - stale_stop_s; still includes scanning, asking and reading at junctions.
- in_motion_s: time whose speed |v_mps| in Unity's truth_run###.csv is above in_motion_speed_threshold_mps
  (configs/hri_trials_metrics.json).
Stale stops depend on the machine's inference speed, so total_s and stale_stop_s are not comparable across machines;
time_excl_stale_stops_s and in_motion_s are. Older logs without a safety or v_mps column give None.

Output: a new folder <output_root>/hri_trials_<time>/ with run_###.json (all metrics of one run), results.csv (one
row per run, running success ratio), summary.json, the configs of both sides and run.json (git commit).

Usage (from robot_vision/):  python hri_trials.py --unity outputs/trials_development_Task2_X --bridge outputs/bridge_guide_Y
                             [--metrics-config configs/hri_trials_metrics.json]
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import statistics as st
from pathlib import Path

HERE = Path(__file__).resolve().parent
DEFAULT_METRICS_CONFIG = "configs/hri_trials_metrics.json"
STEPS = ("navigate", "scan", "approach", "ask", "gesture", "execute")
STALE = "perception stale"
MODELS = ("jpeg_decode", "yolo11s-pose/cam360", "yolo11s-pose/gesture", "mediapipe/stop")
COLUMNS = ["trial", "task", "mode", "seed", "perception", "outcome", "failure_reason", "detail", "success_ratio",
           "a_x", "a_z", "b_name", "b_x", "b_z", "straight_line_m", "travelled_m", "total_s",
           "stale_stop_s", "time_excl_stale_stops_s", "in_motion_s",
           *[f"{s}_s" for s in STEPS], "safety_stop_s", "avg_speed_mps", "max_speed_mps", "avg_turn_dps", "max_turn_dps",
           "final_distance_to_b_m", "junctions_shown_vs_read", "collisions", "human_collisions", "closest_human_m",
           "inference_total_ms_mean", "inference_total_ms_p95", *[f"{m}_ms_mean" for m in MODELS],
           "round_trip_ms_mean", "round_trip_ms_max", "watchdog_stops", "python_final_state"]


# ---------------------------------------------------------------- the seeded goal order (same as Unity GoalSequence)

M64 = (1 << 64) - 1


class GoalSequence:
    """SplitMix64, identical to Unity's WarehouseHRI.GoalSequence (pinned in both test suites)."""

    def __init__(self, seed: int):
        self.state = ((seed & 0xFFFFFFFF) * 0x9E3779B97F4A7C15 + 0x632BE59BD9B4E019) & M64
        self.prev = -1

    def next_u64(self) -> int:
        self.state = (self.state + 0x9E3779B97F4A7C15) & M64
        z = self.state
        z = ((z ^ (z >> 30)) * 0xBF58476D1CE4E5B9) & M64
        z = ((z ^ (z >> 27)) * 0x94D049BB133111EB) & M64
        return z ^ (z >> 31)

    def next_goal_index(self, count: int) -> int:
        if count <= 1 or self.prev < 0:
            i = self.next_u64() % max(count, 1)
        else:
            i = self.next_u64() % (count - 1)
            if i >= self.prev:
                i += 1
        self.prev = i
        return i


def goal_order(seed: int, endpoints: list[str], n: int) -> list[str]:
    g = GoalSequence(seed)
    return [endpoints[g.next_goal_index(len(endpoints))] for _ in range(n)]


# ---------------------------------------------------------------- helpers

def read_csv(p: Path) -> list[dict]:
    if not p.exists():
        return []
    with p.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def num(x, default=None):
    try:
        v = float(x)
        return v if math.isfinite(v) else default
    except (TypeError, ValueError):
        return default


def pct(v: list[float], q: float):
    v = sorted(v)
    if not v:
        return None
    k = (len(v) - 1) * q
    lo, hi = math.floor(k), math.ceil(k)
    return v[lo] + (v[hi] - v[lo]) * (k - lo)


def r3(x):
    return round(x, 3) if isinstance(x, float) else x


def model_times(rows: list[dict]) -> dict:
    per = {m: [] for m in MODELS}
    totals = []
    for r in rows:
        if num(r.get("decode_ms")) is not None:
            per["jpeg_decode"].append(float(r["decode_ms"]))
        for part in (r.get("model_ms") or "").split(";"):
            if ":" in part:
                name, ms = part.rsplit(":", 1)
                per.setdefault(name, []).append(float(ms))
        if num(r.get("total_ms")) is not None:
            totals.append(float(r["total_ms"]))
    out = {m: {"n": len(v), "mean": r3(st.fmean(v)) if v else None, "p95": r3(pct(v, 0.95)), "max": r3(max(v)) if v else None}
           for m, v in per.items()}
    out["total_per_frame"] = {"n": len(totals), "mean": r3(st.fmean(totals)) if totals else None,
                              "p95": r3(pct(totals, 0.95)), "max": r3(max(totals)) if totals else None}
    return out


def _timed(rows: list[dict], column: str) -> list[tuple[float, dict]]:
    return sorted(((num(r.get("time_s")), r) for r in rows if column in r and num(r.get("time_s")) is not None),
                  key=lambda x: x[0])


def stale_stop_s(rows: list[dict]):
    """Seconds with safety == "perception stale" in one trial's decisions.csv rows; None if not logged."""
    timed = _timed(rows, "safety")
    if not timed:
        return None
    return sum(t1 - t0 for (t0, r), (t1, _) in zip(timed, timed[1:]) if r["safety"] == STALE)


def in_motion_s(rows: list[dict], threshold_mps: float):
    """Seconds with |v_mps| > threshold_mps in one trial's Unity truth rows; None if speed is not logged."""
    timed = _timed(rows, "v_mps")
    if not timed:
        return None
    return sum(t1 - t0 for (t0, r), (t1, _) in zip(timed, timed[1:]) if abs(num(r["v_mps"], 0.0)) > threshold_mps)


def load_metrics_config(path: str | Path = DEFAULT_METRICS_CONFIG) -> dict:
    p = Path(path)
    return json.loads((p if p.is_absolute() else HERE / p).read_text(encoding="utf-8"))


# ---------------------------------------------------------------- merge

def merge(unity: Path, bridge: Path, metrics: dict | None = None) -> tuple[list[dict], dict]:
    metrics = metrics if metrics is not None else load_metrics_config()
    threshold = float(metrics["in_motion_speed_threshold_mps"])
    session = json.loads((unity / "session.json").read_text(encoding="utf-8"))
    decisions = read_csv(bridge / "decisions.csv")
    perception = read_csv(bridge / "perception.csv")
    runs, successes = [], 0
    for truth_json in sorted(unity.glob("truth_run*.json")):
        t = json.loads(truth_json.read_text(encoding="utf-8"))
        i = t["trial"]
        py_path = bridge / f"python_trial_{i:03d}.json"
        py = json.loads(py_path.read_text(encoding="utf-8")) if py_path.exists() else {}
        dec = [r for r in decisions if r.get("trial") == str(i)]
        per = [r for r in perception if t["t_start"] <= (num(r.get("time_s"), -1) or -1) <= t["t_end"]]
        rtt = [num(r["rtt_ms"]) for r in dec if num(r.get("rtt_ms"), -1) >= 0]
        wd = [int(r["watchdog_count"]) for r in dec if r.get("watchdog_count", "").isdigit()]
        shown = {s["junction"]: s["shown"] for s in t.get("shown", [])}
        junctions = [{"junction": j["junction"], "shown": shown.get(j["junction"], "unknown"), "read": j["read"],
                      "asks": j["asks"], "result": j["result"]} for j in py.get("junctions", [])]
        for s in t.get("shown", []):          # a junction the worker stood at but Python never answered (aborted before)
            if not any(j["junction"] == s["junction"] for j in junctions) and py.get("state") == "aborted" and s["junction"] in py.get("abort_reason", ""):
                junctions.append({"junction": s["junction"], "shown": s["shown"], "read": "NONE", "asks": None, "result": "aborted"})
        if t["outcome"] == "SUCCESS":
            successes += 1
        times = model_times(per)
        stale = stale_stop_s(dec)
        motion = in_motion_s(read_csv(unity / f"truth_run{i:03d}.csv"), threshold)
        run = {
            "trial": i, "task": t["task"], "mode": t["mode"], "seed": t["seed"],
            "perception": py.get("perception", "unknown"), "outcome": t["outcome"], "failure_reason": t["failure_reason"],
            "detail": t["detail"], "successes_so_far": successes, "success_ratio": round(successes / (len(runs) + 1), 4),
            "a": {"name": t["a_name"], "x": t["a_x"], "z": t["a_z"]}, "b": {"name": t["b_name"], "x": t["b_x"], "z": t["b_z"]},
            "straight_line_m": r3(t["straight_line_m"]), "travelled_m": r3(t["travelled_m"]), "total_s": r3(t["total_s"]),
            "stale_stop_s": r3(stale), "time_excl_stale_stops_s": r3(t["total_s"] - stale) if stale is not None else None,
            "in_motion_s": r3(motion), "in_motion_speed_threshold_mps": threshold,
            "step_s": py.get("step_s", {}), "safety_stop_s": py.get("safety_stop_s"),
            "avg_speed_mps": r3(t["avg_speed_mps"]), "max_speed_mps": r3(t["max_speed_mps"]),
            "avg_turn_dps": r3(t["avg_turn_dps"]), "max_turn_dps": r3(t["max_turn_dps"]),
            "final_distance_to_b_m": r3(t["final_distance_to_b_m"]), "junctions": junctions,
            "inference_ms": times,
            "round_trip_ms": {"n": len(rtt), "mean": r3(st.fmean(rtt)) if rtt else None, "p95": r3(pct(rtt, 0.95)),
                              "max": r3(max(rtt)) if rtt else None,
                              "note": "Unity-measured telemetry -> command delay, sampled every 0.1 s"},
            "watchdog_stops": (max(wd) - min(wd)) if wd else None,
            "collisions": t["collisions"], "human_collisions": t["human_collisions"], "collided_with": t["collided_with"],
            "closest_human_m": r3(t["closest_human_m"]), "closest_human_note": t["closest_human_note"],
            "python_final_state": t["python_final_state"], "abort_reason": py.get("abort_reason", ""),
            "python_trace": py.get("trace", []), "truth_file": t["truth_file"],
        }
        runs.append(run)
    endpoints = session.get("endpoints", [])
    check = {"goal_order_in_session": session.get("goal_order", []),
             "goal_order_recomputed": goal_order(session["seed"], endpoints, len(session.get("goal_order", [])))
             if session.get("task") == "Task2" and endpoints else None}
    check["goal_order_matches"] = check["goal_order_recomputed"] in (None, check["goal_order_in_session"])
    return runs, {"session": session, "check": check}


def csv_row(r: dict) -> dict:
    row = {k: r.get(k) for k in COLUMNS if k in r}
    row.update(a_x=r["a"]["x"], a_z=r["a"]["z"], b_name=r["b"]["name"], b_x=r["b"]["x"], b_z=r["b"]["z"])
    for s in STEPS:
        row[f"{s}_s"] = r["step_s"].get(s)
    row["junctions_shown_vs_read"] = "; ".join(f"{j['junction']}:{j['shown']}>{j['read']}(asks {j['asks']})" for j in r["junctions"])
    tm = r["inference_ms"]
    row["inference_total_ms_mean"] = tm["total_per_frame"]["mean"]
    row["inference_total_ms_p95"] = tm["total_per_frame"]["p95"]
    for m in MODELS:
        row[f"{m}_ms_mean"] = tm.get(m, {}).get("mean")
    row["round_trip_ms_mean"] = r["round_trip_ms"]["mean"]
    row["round_trip_ms_max"] = r["round_trip_ms"]["max"]
    return row


def main(argv=None) -> None:
    import decision_io as dio

    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--unity", required=True, help="Unity trial runner folder (trials_...)")
    ap.add_argument("--bridge", required=True, help="bridge guide run folder (bridge_guide_...)")
    ap.add_argument("--metrics-config", default=DEFAULT_METRICS_CONFIG)
    a = ap.parse_args(argv)
    unity, bridge, metrics_path = dio.resolve(a.unity), dio.resolve(a.bridge), dio.resolve(a.metrics_config)
    runs, meta = merge(unity, bridge, load_metrics_config(metrics_path))
    if not runs:
        raise SystemExit(f"no truth_run*.json in {unity}")
    out = dio.new_run_dir({"paths": {"output_root": "outputs"}}, "hri_trials")
    (out / "config_used").mkdir()
    for d in (unity / "config_used", bridge / "config_used"):
        for f in d.glob("*.json"):
            (out / "config_used" / f.name).write_bytes(f.read_bytes())
    (out / "config_used" / metrics_path.name).write_bytes(metrics_path.read_bytes())
    for r in runs:
        (out / f"run_{r['trial']:03d}.json").write_text(json.dumps(r, indent=2) + "\n", encoding="utf-8")
    with (out / "results.csv").open("x", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNS)
        w.writeheader()
        for r in runs:
            w.writerow(csv_row(r))
    n, s = len(runs), sum(r["outcome"] == "SUCCESS" for r in runs)
    summary = {"trials": n, "successes": s, "success_ratio": round(s / n, 4), "task": runs[0]["task"], "mode": runs[0]["mode"],
               "seed": runs[0]["seed"], "perception": runs[0]["perception"], "unity_session": unity.name,
               "bridge_run": bridge.name, "unity_git_commit": meta["session"].get("git_commit"), **meta["check"]}
    dio.write_json(out / "summary.json", summary)
    dio.write_json(out / "run.json", {"git": dio.git_info(), "inputs": {"unity": unity.name, "bridge": bridge.name}})
    print(json.dumps(summary, indent=2))
    print(f"Folder: {out.relative_to(HERE) if out.is_relative_to(HERE) else out}")


if __name__ == "__main__":
    main()
