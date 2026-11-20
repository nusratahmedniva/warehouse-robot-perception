"""Do the checkpoint positions Nusrat sent meet the placement rules? (AUDIT.md 16.26 item 1, 2026-11-19). CHECK CODE: nothing in the controller or the simulator imports it.

For every checkpoint of a layout file (default configs/v4/experiments/checkpoints_unity.json) and for the junction workers of A3 (the beside layout) and of A4 (random: drawn around
the fixed checkpoint workers, seeds 1 to 20), measured and reported, never tuned:
  - the worker's distance from the robot's spot (the point of the road abeam) and the 2.0 m across point the robot asks from (its distance from the road centre line);
  - the distance to every other worker (rule: at least 3.0 m) and to every turning point (3.0 m);
  - the distance to every junction and the start node (rule: outside the 6.5 m second-opinion zone);
  - the clearance from every road and every segment the robot can drive: the junction workers' ask / re-ask / return segments and the segments of every checkpoint (rule: 1.0 m),
    and the junction workers' clearance from the checkpoint segments;
  - Part 1's rule (AUDIT.md 16.25): the checkpoint worker qualifies at its spot and nobody else (a junction worker, another checkpoint worker) does.
Not checkable here: whether the 2.0 m across point is inside the drivable area of Unity (the ground-truth grid is in no data I hold).

Usage (from robot_vision/): python check_checkpoints_v4.py [--layout configs/v4/experiments/checkpoints_unity.json] [--seeds 20] [--label x]
Writes outputs/check_checkpoints_v4_<time>[_label]/ (report.json, report.md, run.json); never overwrites."""

from __future__ import annotations

import argparse
import json
import math
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import hri_sim_v4 as sv  # noqa: E402
import run_t3_v4 as rn  # noqa: E402


def measure(name: str, seed: int, cp_cfg: dict) -> list[dict]:
    sc = sv.scenario_ab(name, seed, rn.detection_for("T4", "on", cp_cfg), checkpoints=cp_cfg)
    sim, road = sc["sim"], sc["road"]
    sim._plan, sim._cp_plan = {}, {}
    sim._cp_plan = sim.plan_checkpoints()
    sim._plan = sim.plan_workers()
    rule = sv.load_scenarios()["placement_rule"]
    standoff, shift = float(rule["ask_standoff_m"]), float(rule["reask_shift_m"])
    workers = [(node, i + 1, q) for node, pts in sim._plan.items() for i, q in enumerate(pts)]
    cps = {k: (v["x"], v["z"]) for k, v in sim._cp_plan.items()}
    asking = {n: road.pos(n) for n, v in road.nodes.items() if v["kind"] in ("junction", "start")}
    turns = sv.turning_points(road, sc["spec"].physical_map)
    roads = sv._road_segments(road, sc["spec"].physical_map)
    drive = [sg[:4] for node, pts in sim._plan.items() for sg in sv.drivable_segments(road, node, pts, standoff, shift)[0]]
    cp_segs = {k: sv.checkpoint_segments(road, k[0], v["next"], v["point"], cps[k], standoff, shift) for k, v in sim._cp_plan.items()}
    all_cp_segs = [sg for segs in cp_segs.values() for sg in segs]
    rows = []
    for k, v in sim._cp_plan.items():
        w = cps[k]
        sim.c.cp = {"junction": k[0], "branch": k[1], "next": v["next"], "point": v["point"], "stage": "dialog"}
        across = sv.ask_position(w, v["point"], standoff)
        people = [{"x": q[0], "z": q[1]} for _, _, q in workers] + [{"x": c[0], "z": c[1]} for kk, c in cps.items() if kk != k]
        qualifies = sim.c._cp_qualifies({"x": w[0], "z": w[1]})
        others_qualify = [p for p in people if sim.c._cp_qualifies(p)]
        rows.append({"experiment": name, "seed": seed, "checkpoint": f"{k[0]}>{k[1]}", "worker": [round(w[0], 3), round(w[1], 3)], "spot": [round(c, 3) for c in v["point"]],
                     "worker_to_spot_m": round(math.dist(w, v["point"]), 3), "across_point": [round(c, 3) for c in across], "across_from_road_m": round(abs(v["lateral_m"] - standoff), 3),
                     "nearest_other_worker_m": round(min(math.dist(w, q) for _, _, q in workers), 3) if workers else None,
                     "nearest_other_checkpoint_worker_m": round(min(math.dist(w, c) for kk, c in cps.items() if kk != k), 3) if len(cps) > 1 else None,
                     "nearest_turning_point_m": round(min(math.dist(w, t) for t in turns), 3), "nearest_asking_node_m": round(min(math.dist(w, p) for p in asking.values()), 3),
                     "clearance_from_roads_and_driven_segments_m": round(min(sv._seg_dist(w[0], w[1], sg) for sg in roads + drive + [s for kk, ss in cp_segs.items() if kk != k for s in ss]), 3),
                     "junction_workers_nearest_to_this_checkpoints_segments_m": round(min(sv._seg_dist(q[0], q[1], sg) for _, _, q in workers for sg in cp_segs[k]), 3) if workers else None,
                     "qualifies_at_its_spot": bool(qualifies), "others_who_qualify": len(others_qualify)})
    return rows


def summarise(rows: list[dict]) -> list[dict]:
    out = []
    for key in sorted({r["checkpoint"] for r in rows}):
        rs = [r for r in rows if r["checkpoint"] == key]
        f = lambda k, fn: fn(r[k] for r in rs if r[k] is not None)
        out.append({"checkpoint": key, "worker": rs[0]["worker"], "spot": rs[0]["spot"], "worker_to_spot_m": rs[0]["worker_to_spot_m"], "across_point": rs[0]["across_point"],
                    "across_from_road_m": rs[0]["across_from_road_m"], "min_other_worker_m": f("nearest_other_worker_m", min), "min_other_checkpoint_worker_m": f("nearest_other_checkpoint_worker_m", min),
                    "min_turning_point_m": f("nearest_turning_point_m", min), "min_asking_node_m": f("nearest_asking_node_m", min),
                    "min_clearance_m": f("clearance_from_roads_and_driven_segments_m", min), "min_junction_workers_to_segments_m": f("junction_workers_nearest_to_this_checkpoints_segments_m", min),
                    "qualifies_always": all(r["qualifies_at_its_spot"] for r in rs), "others_who_qualify_max": max(r["others_who_qualify"] for r in rs)})
    return out


def verdicts(summary: list[dict]) -> dict:
    return {"worker_to_spot_at_most_4_7": all(s["worker_to_spot_m"] <= 4.7 + 1e-9 for s in summary),
            "separation_3_0": all((s["min_other_worker_m"] is None or s["min_other_worker_m"] >= 3.0 - 1e-6) and (s["min_other_checkpoint_worker_m"] is None or s["min_other_checkpoint_worker_m"] >= 3.0 - 1e-6) for s in summary),
            "turning_points_3_0": all(s["min_turning_point_m"] >= 3.0 - 1e-6 for s in summary),
            "outside_junction_zone_6_5": all(s["min_asking_node_m"] > 6.5 for s in summary),
            "clearance_1_0": all(s["min_clearance_m"] >= 1.0 - 1e-4 and (s["min_junction_workers_to_segments_m"] is None or s["min_junction_workers_to_segments_m"] >= 1.0 - 1e-4) for s in summary),
            "part_1_rule": all(s["qualifies_always"] and s["others_who_qualify_max"] == 0 for s in summary)}


def markdown(label: str, summary: dict, verdict: dict) -> str:
    L = [f"## Checkpoint positions against the placement rules: {label}", ""]
    for exp, rows in summary.items():
        L += [f"### {exp}", "", "| checkpoint | worker | spot | worker to spot m | across point | across from road m | nearest other worker m | nearest other checkpoint worker m | nearest turning point m | nearest junction / start m | min clearance m | junction workers to its segments m | qualifies | others who qualify |",
              "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
        for s in rows:
            L.append(f"| {s['checkpoint']} | {s['worker']} | {s['spot']} | {s['worker_to_spot_m']} | {s['across_point']} | {s['across_from_road_m']} | {s['min_other_worker_m']} | {s['min_other_checkpoint_worker_m']} | "
                     f"{s['min_turning_point_m']} | {s['min_asking_node_m']} | {s['min_clearance_m']} | {s['min_junction_workers_to_segments_m']} | {'always' if s['qualifies_always'] else 'NOT always'} | {s['others_who_qualify_max']} |")
        L += ["", "Rules: " + ", ".join(f"{k} **{'met' if v else 'NOT met'}**" for k, v in verdict[exp].items()), ""]
    return "\n".join(L)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--layout", default="configs/v4/experiments/checkpoints_unity.json")
    ap.add_argument("--seeds", type=int, default=20)
    ap.add_argument("--label", default="")
    a = ap.parse_args(argv)
    cp_cfg = json.loads((HERE / a.layout).read_text(encoding="utf-8"))
    rows = {"A3 (beside layout)": measure("A3", 1, cp_cfg), "A4 (random layout, seeds 1 to %d)" % a.seeds: [r for seed in range(1, a.seeds + 1) for r in measure("A4", seed, cp_cfg)]}
    summary = {k: summarise(v) for k, v in rows.items()}
    verdict = {k: verdicts(v) for k, v in summary.items()}
    md = markdown(a.layout, summary, verdict)
    out = HERE / "outputs" / f"check_checkpoints_v4_{time.strftime('%Y%m%d_%H%M%S')}{'_' + a.label if a.label else ''}"
    out.mkdir(parents=True, exist_ok=False)
    (out / "report.json").write_text(json.dumps({"summary": summary, "verdict": verdict}, indent=1), encoding="utf-8")
    (out / "report.md").write_text(md + "\n", encoding="utf-8")
    commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=HERE, capture_output=True, text=True).stdout.strip()
    (out / "run.json").write_text(json.dumps({"git_commit": commit, "layout": a.layout, "source": cp_cfg.get("source")}, indent=1), encoding="utf-8")
    print(md)
    print(f"Folder: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
