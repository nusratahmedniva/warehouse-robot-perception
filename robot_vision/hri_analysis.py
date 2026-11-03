"""Step 7 analysis: summary of one or more merged trial sessions (hri_trials.py output folders).

Writes a new folder <output_root>/hri_analysis_<time>/ with analysis.json, analysis.md, running_success.png and
step_times.png: success ratio with its Wilson 95 % interval, failure reasons, success per goal, time per step,
total time, stale-perception stops, time excluding stale stops and time in motion (see hri_trials.py) separately,
speed and turn rate, gesture shown vs read at the junctions, inference time per model, Unity-Python round trip,
watchdog stops, collisions and the closest distance to a person. Every figure says over how many runs it is.

v4 (docs/protocol_v3.md): when a run's folder <input folder>/run_###/ holds Unity's grid.json, optimal_path.json and
trail.csv, the path measures of gt_path.py (trail length / optimal length, largest distance from the optimal line, share
of the trail within one grid cell, final distance from B) are added to analysis.json ("path_measures") and analysis.md.
Without those files nothing is added: v3 output is byte-identical.

Usage (from robot_vision/):  python hri_analysis.py outputs/hri_trials_X [outputs/hri_trials_Y ...]
"""

from __future__ import annotations

import argparse
import json
import math
import statistics as st
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
STEPS = ("navigate", "scan", "approach", "ask", "gesture", "execute")
COMMANDS = ("NONE", "LEFT", "FORWARD_LEFT", "FORWARD", "FORWARD_RIGHT", "RIGHT", "STOP")


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float | None, float | None]:
    if n == 0:
        return None, None
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return round(max(0.0, c - h), 4), round(min(1.0, c + h), 4)


def stats(v: list[float]) -> dict:
    v = [x for x in v if x is not None]
    if not v:
        return {"n": 0}
    s = sorted(v)
    return {"n": len(v), "mean": round(st.fmean(v), 3), "median": round(st.median(v), 3), "min": round(s[0], 3),
            "max": round(s[-1], 3)}


def load_runs(folders: list[Path]) -> list[dict]:
    runs = []
    for f in folders:
        for p in sorted(f.glob("run_*.json")):
            r = json.loads(p.read_text(encoding="utf-8"))
            r["_folder"] = f.name
            runs.append(r)
    return runs


def analyse(runs: list[dict]) -> dict:
    n = len(runs)
    k = sum(r["outcome"] == "SUCCESS" for r in runs)
    per_goal = defaultdict(Counter)
    for r in runs:
        per_goal[r["b"]["name"]][r["outcome"]] += 1
    junction_conf = defaultdict(Counter)
    asks = Counter()
    for r in runs:
        for j in r["junctions"]:
            junction_conf[j["shown"]][j["read"]] += 1
            asks[j.get("asks")] += 1
    models = defaultdict(list)
    for r in runs:
        for m, s in r["inference_ms"].items():
            if s.get("mean") is not None:
                models[m].append(s["mean"])
    return {
        "runs": n, "sessions": sorted({r["_folder"] for r in runs}),
        "labels": {"perception": sorted({r["perception"] for r in runs}), "mode": sorted({r["mode"] for r in runs}),
                   "seed": sorted({r["seed"] for r in runs}), "task": sorted({r["task"] for r in runs})},
        "success": {"k": k, "n": n, "ratio": round(k / n, 4) if n else None, "wilson95": wilson(k, n)},
        "failure_reasons": dict(Counter(r["failure_reason"] for r in runs if r["outcome"] != "SUCCESS")),
        "per_goal": {g: dict(c) for g, c in sorted(per_goal.items())},
        "total_s": stats([r["total_s"] for r in runs]),
        "stale_stop_s": stats([r.get("stale_stop_s") for r in runs]),
        "time_excl_stale_stops_s": stats([r.get("time_excl_stale_stops_s") for r in runs]),
        "in_motion_s": stats([r.get("in_motion_s") for r in runs]),
        "in_motion_speed_threshold_mps": sorted({r["in_motion_speed_threshold_mps"] for r in runs
                                                 if r.get("in_motion_speed_threshold_mps") is not None}),
        "step_s": {s: stats([r["step_s"].get(s) for r in runs]) for s in STEPS},
        "safety_stop_s": stats([r.get("safety_stop_s") for r in runs]),
        "travel_ratio": stats([r["travelled_m"] / r["straight_line_m"] for r in runs if r["straight_line_m"]]),
        "final_distance_to_b_m": stats([r["final_distance_to_b_m"] for r in runs if r["outcome"] == "SUCCESS"]),
        "speed_mps": {"avg": stats([r["avg_speed_mps"] for r in runs]), "max": stats([r["max_speed_mps"] for r in runs])},
        "turn_dps": {"avg": stats([r["avg_turn_dps"] for r in runs]), "max": stats([r["max_turn_dps"] for r in runs])},
        "junctions": {"n": sum(sum(c.values()) for c in junction_conf.values()),
                      "shown_vs_read": {s: dict(c) for s, c in sorted(junction_conf.items())},
                      "correct": sum(c[s] for s, c in junction_conf.items()),
                      "asks": {str(a): c for a, c in asks.items()}},
        "inference_ms_mean_of_runs": {m: stats(v) for m, v in sorted(models.items())},
        "round_trip_ms": {"mean_of_runs": stats([r["round_trip_ms"]["mean"] for r in runs]),
                          "max": stats([r["round_trip_ms"]["max"] for r in runs])},
        "watchdog_stops": stats([r.get("watchdog_stops") for r in runs]),
        "collisions": {"total": sum(r["collisions"] for r in runs), "human": sum(r["human_collisions"] for r in runs)},
        "closest_human_m": stats([r["closest_human_m"] for r in runs if r["closest_human_m"] is not None and r["closest_human_m"] >= 0]),
    }


def path_section(runs: list[dict], folders: list[Path], cfg: dict | None = None) -> dict | None:
    """v4 path measures over the runs whose folder has the v4 files; None when no run has them (v3 sessions)."""
    import gt_path
    cfg = cfg if cfg is not None else gt_path.load_config()
    by_name = {f.name: f for f in folders}
    per_run = []
    for r in runs:
        run_dir = by_name[r["_folder"]] / f"run_{r['trial']:03d}"
        if not gt_path.has_v4_files(run_dir):
            continue
        res = gt_path.evaluate_run(run_dir, cfg)
        per_run.append({"session": r["_folder"], "trial": r["trial"], "outcome": r["outcome"], **res})
    if not per_run:
        return None
    m = [x["measures"] for x in per_run]
    return {"coverage": f"{len(per_run)} of {len(runs)} runs have the v4 files",
            "optimal_path_matches": f"{sum(x['optimal_path_check']['match'] for x in per_run)} of {len(per_run)}",
            "trail_over_optimal": stats([x["trail_over_optimal"] for x in m]),
            "max_distance_from_optimal_m": stats([x["max_distance_from_optimal_m"] for x in m]),
            "share_within_near_distance": stats([x["share_within_near_distance"] for x in m]),
            "near_distance_m": sorted({x["near_distance_m"] for x in m}),
            "final_distance_from_b_m": stats([x["final_distance_from_b_m"] for x in m]),
            "runs": per_run}


def path_markdown(sec: dict) -> str:
    L = ["", "## Path measures (v4 ground truth)", "",
         f"{sec['coverage']}; Unity's optimal path equals Python's A* in {sec['optimal_path_matches']}. "
         f"Near = within {', '.join(map(str, sec['near_distance_m']))} m (one grid cell) of the optimal line.", "",
         "| measure | n | mean | median | min | max |", "|---|---|---|---|---|---|"]
    for k, label in (("trail_over_optimal", "trail length / optimal length"),
                     ("max_distance_from_optimal_m", "largest distance from optimal line (m)"),
                     ("share_within_near_distance", "share of trail within one cell"),
                     ("final_distance_from_b_m", "final distance from B (m)")):
        v = sec[k]
        if v.get("n"):
            L.append(f"| {label} | {v['n']} | {v['mean']} | {v['median']} | {v['min']} | {v['max']} |")
    return "\n".join(L) + "\n"


def markdown(a: dict) -> str:
    s = a["success"]
    L = [f"# Trial analysis ({', '.join(a['labels']['perception'])})", "",
         f"Sessions: {', '.join(a['sessions'])}. Task {a['labels']['task']}, mode {a['labels']['mode']}, seed {a['labels']['seed']}.", "",
         f"**Success {s['k']}/{s['n']} = {s['ratio']}** (Wilson 95 %: {s['wilson95'][0]}-{s['wilson95'][1]}); "
         f"failures: {a['failure_reasons'] or 'none'}.", "",
         "| goal B | " + " | ".join(["SUCCESS", "FAILURE"]) + " |", "|---|---|---|"]
    L += [f"| {g} | {c.get('SUCCESS', 0)} | {c.get('FAILURE', 0)} |" for g, c in a["per_goal"].items()]
    L += ["", "Time per step (s, over runs):", "", "| step | n | mean | median | max |", "|---|---|---|---|---|"]
    for k, v in list(a["step_s"].items()) + [("safety stop (any reason)", a["safety_stop_s"]),
                                             ("stale-perception stops", a["stale_stop_s"]), ("total", a["total_s"]),
                                             ("time excl. stale stops", a["time_excl_stale_stops_s"]),
                                             ("in motion", a["in_motion_s"])]:
        if v.get("n"):
            L.append(f"| {k} | {v['n']} | {v['mean']} | {v['median']} | {v['max']} |")
    L += ["", "Time excl. stale stops = total minus stale-perception stops (still includes scanning, asking and reading "
          f"at junctions). In motion = Unity speed above {', '.join(map(str, a['in_motion_speed_threshold_mps']))} m/s. Across machines both are "
          "comparable; total time, stale-perception stops and inference times are not (they depend on inference speed)."]
    j = a["junctions"]
    L += ["", f"Junctions: {j['correct']}/{j['n']} read as shown; asks per junction {j['asks']}.", "",
          "| shown \\ read | " + " | ".join(COMMANDS) + " |", "|---|" + "---|" * len(COMMANDS)]
    for shown, c in j["shown_vs_read"].items():
        L.append(f"| {shown} | " + " | ".join(str(c.get(x, 0)) for x in COMMANDS) + " |")
    L += ["", f"Speed m/s: average {a['speed_mps']['avg'].get('mean')}, max {a['speed_mps']['max'].get('max')}; "
          f"turn rate deg/s: average {a['turn_dps']['avg'].get('mean')}, max {a['turn_dps']['max'].get('max')}; "
          f"travelled / straight line: {a['travel_ratio'].get('mean')}.",
          f"Final distance from B (successes): mean {a['final_distance_to_b_m'].get('mean')} m, max {a['final_distance_to_b_m'].get('max')} m.",
          "", "Inference time (ms, mean per run, then over runs):", "", "| model | runs | mean | max |", "|---|---|---|---|"]
    for m, v in a["inference_ms_mean_of_runs"].items():
        if v.get("n"):
            L.append(f"| {m} | {v['n']} | {v['mean']} | {v['max']} |")
    L += ["", f"Round trip (Unity-measured) ms: mean of runs {a['round_trip_ms']['mean_of_runs'].get('mean')}, "
          f"max {a['round_trip_ms']['max'].get('max')}. Watchdog stops per run: {a['watchdog_stops']}.",
          f"Collisions: {a['collisions']['total']} (with a person: {a['collisions']['human']}). Closest distance to a person "
          f"(robot body to worker axis): min {a['closest_human_m'].get('min')} m, mean {a['closest_human_m'].get('mean')} m.", ""]
    return "\n".join(L) + "\n"


def plots(runs: list[dict], out: Path) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    k = 0
    ratio = []
    for i, r in enumerate(runs, 1):
        k += r["outcome"] == "SUCCESS"
        ratio.append(k / i)
    fig, ax = plt.subplots(figsize=(6, 3))
    ax.plot(range(1, len(runs) + 1), ratio, marker="o")
    ax.set_ylim(0, 1.05)
    ax.set_xlabel("run")
    ax.set_ylabel("running success ratio")
    fig.tight_layout()
    fig.savefig(out / "running_success.png", dpi=120)
    plt.close(fig)
    fig, ax = plt.subplots(figsize=(6, 3))
    bottom = [0.0] * len(runs)
    for s in STEPS:
        v = [r["step_s"].get(s, 0.0) or 0.0 for r in runs]
        ax.bar(range(1, len(runs) + 1), v, bottom=bottom, label=s)
        bottom = [b + x for b, x in zip(bottom, v)]
    ax.set_xlabel("run")
    ax.set_ylabel("time (s)")
    ax.legend(fontsize=7, ncol=3)
    fig.tight_layout()
    fig.savefig(out / "step_times.png", dpi=120)
    plt.close(fig)


def main(argv=None) -> None:
    import decision_io as dio

    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("folders", nargs="+", help="hri_trials_* folders")
    a = ap.parse_args(argv)
    runs = load_runs([dio.resolve(f) for f in a.folders])
    if not runs:
        raise SystemExit("no run_*.json found")
    res = analyse(runs)
    folders = [dio.resolve(f) for f in a.folders]
    sec = path_section(runs, folders)
    if sec is not None:
        res["path_measures"] = sec
    out = dio.new_run_dir({"paths": {"output_root": "outputs"}}, "hri_analysis")
    dio.write_json(out / "analysis.json", res)
    dio.write_json(out / "run.json", {"git": dio.git_info(), "inputs": res["sessions"]})
    md = markdown(res) + (path_markdown(sec) if sec is not None else "")
    (out / "analysis.md").write_text(md, encoding="utf-8")
    plots(runs, out)
    print(md)
    print(f"Folder: {out.relative_to(HERE) if out.is_relative_to(HERE) else out}")


if __name__ == "__main__":
    main()
