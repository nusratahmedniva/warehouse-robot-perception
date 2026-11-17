"""Placement checks of the simulator's worker layouts (AUDIT.md 16.20, 2026-11-17). Evaluation and check code only: nothing in the controller or the
simulator imports it.

Three questions, asked of every worker of every scenario, seed and asking node of the simulator (hri_sim_v4.scenario_ab(...).sim.plan_workers()):

1. Does the worker belong to its node? Within `lie_detection.second_opinion_radius_m` (6.5 m, 16.19) of it AND that node is the nearest node of the roadmap
   (the rule of ControllerV4._belongs_here, used directly).
2. Is the worker clear of every segment the robot can drive? An independent model of Nusrat's clearance rule (experiments_ab.md section 15 addendum 1,
   item 3b, commit ed4e000): per asking node the segment from the node to the ask position of each worker in every order (second opinions), the return to
   the first worker of an order (the tie rule), and from every ask position and re-ask point to the next node of every branch; plus every road of the run's
   map and of the physical v4 map. Ask position = `standoff` from the worker toward where the robot comes from; re-ask point = `shift` to the robot's right,
   back on that circle (hri_control._reposition). No worker may be closer than `clearance` (1.0 m = corridor half width 0.6 m + 0.4 m).
3. How far is each ask position from its node? (Her answer-zone rule: at most 5.5 m = 6.0 m zone - 0.5 m margin.)

The re-ask shift is checked at her value 0.4 m (a copy of hri_control.json, the v3 value) AND at the value the v4 controller really uses (control.json
dialog.reask_shift_m, 0.8 m). Reported, never tuned.

Usage (from robot_vision/): python layout_check_v4.py [--seeds 20] [--label x]    writes outputs/layout_check_v4_<time>/ (never overwrites).
"""

from __future__ import annotations

import argparse
import itertools
import json
import math
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

import hri_control as hc  # noqa: E402
import hri_control_v4 as hv  # noqa: E402
import hri_sim_v4 as sv  # noqa: E402

CLEARANCE_M = 1.0                      # Nusrat's path_clearance_m
ASK_ZONE_M = 5.5                       # answer_zone_radius_m 6.0 - answer_zone_margin_m 0.5
UNITY_STANDOFF_M = 2.0                 # ask_standoff_m
UNITY_RESHIFT_M = 0.4                  # reask_shift_m of her model
EPS = 1e-4
EXPERIMENTS = ("A1", "A2", "A3", "A4")      # B has the same placements as A (same seed); the layout does not depend on the set


def ask_position(worker, frm, standoff: float = UNITY_STANDOFF_M):
    """`standoff` from the worker toward `frm` (the node, or the previous ask position)."""
    dx, dz = frm[0] - worker[0], frm[1] - worker[1]
    n = math.hypot(dx, dz)
    if n < 1e-6:
        dx, dz, n = 1.0, 0.0, 1.0
    return (worker[0] + dx / n * standoff, worker[1] + dz / n * standoff)


def reask_position(worker, ask, standoff: float = UNITY_STANDOFF_M, shift: float = UNITY_RESHIFT_M):
    """`shift` to the robot's right as it faces the worker (right of heading (hx, hz) = (hz, -hx)), back onto the standoff circle."""
    if shift <= 0:
        return ask
    hx, hz = worker[0] - ask[0], worker[1] - ask[1]
    n = math.hypot(hx, hz)
    if n < 1e-6:
        return ask
    hx, hz = hx / n, hz / n
    return ask_position(worker, (ask[0] + hz * shift, ask[1] - hx * shift), standoff)


def _add(points: list, p) -> None:
    if all(math.dist(p, q) >= 1e-3 for q in points):
        points.append(p)


def drivable_segments(road: hc.Roadmap, node: str, workers: list, standoff: float = UNITY_STANDOFF_M, shift: float = UNITY_RESHIFT_M):
    """(segments [(ax, az, bx, bz, label)], ask points) of one asking node with its workers in slot order."""
    c = road.pos(node)
    segs, asks = [], []
    idx = list(range(len(workers)))
    for perm in itertools.permutations(idx):
        prev, frm = c, node
        for k in range(len(perm) + 1):
            if k == len(perm) and len(perm) < 2:
                break
            i = perm[k] if k < len(perm) else perm[0]               # after the last: back to the first (tie)
            a = ask_position(workers[i], prev, standoff)
            segs.append((prev[0], prev[1], a[0], a[1], f"{frm} to the ask position of worker {i + 1}{' (again)' if k == len(perm) else ''}"))
            _add(asks, a)
            _add(asks, reask_position(workers[i], a, standoff, shift))
            prev, frm = a, f"the ask position of worker {i + 1}"
    for a in asks:
        for cmd, nxt in road.branches.get(node, {}).items():
            n = road.pos(nxt)
            segs.append((a[0], a[1], n[0], n[1], f"{node}: ask position ({a[0]:.2f}, {a[1]:.2f}) to {nxt} ({cmd})"))
    return segs, asks


def evaluate_plan(road: hc.Roadmap, physical: hc.Roadmap | None, plan: dict, standoff: float = UNITY_STANDOFF_M, shift: float = UNITY_RESHIFT_M) -> dict:
    """Clearance of every worker of `plan` ({node: [(x, z), ...]}) from the roads and from the drivable segments of every node, and the largest distance of a
    node's ask points from the node. min_clearance_m: the smallest worker-to-segment distance; worst: what it was."""
    roads = sv._road_segments(road, physical)
    worst = {"clearance_m": math.inf, "what": None}
    max_ask = {"distance_m": 0.0, "node": None}
    per_node = {}
    nodes = list(plan)
    for node in nodes:
        segs, asks = drivable_segments(road, node, plan[node], standoff, shift)
        per_node[node] = (segs, asks)
        for a in asks:
            d = math.dist(a, road.pos(node))
            if d > max_ask["distance_m"]:
                max_ask = {"distance_m": d, "node": node}
    workers = [(node, i + 1, q) for node in nodes for i, q in enumerate(plan[node])]
    for node, i, q in workers:
        for r in roads:
            d = sv._seg_dist(q[0], q[1], r)
            if d < worst["clearance_m"]:
                worst = {"clearance_m": d, "what": f"worker {i} of {node} to a road"}
        for n2 in nodes:
            for s in per_node[n2][0]:
                d = sv._seg_dist(q[0], q[1], s[:4])
                if d < worst["clearance_m"]:
                    worst = {"clearance_m": d, "what": f"worker {i} of {node} to {s[4]} (segments of {n2})"}
    return {"min_clearance_m": worst["clearance_m"], "worst": worst["what"], "max_ask_distance_m": max_ask["distance_m"], "max_ask_node": max_ask["node"],
            "violations": worst["clearance_m"] < CLEARANCE_M - EPS or max_ask["distance_m"] > ASK_ZONE_M + EPS}


def belongs(controller, q) -> tuple[bool, float, str]:
    return controller._belongs_here({"x": q[0], "z": q[1]})


def survey(experiments=EXPERIMENTS, seeds=range(1, 21), shifts=(UNITY_RESHIFT_M,), scen: dict | None = None) -> dict:
    """The three checks for every scenario, seed and node. Returns {experiment: summary} with the maxima and the counts of failures."""
    out = {}
    for name in experiments:
        rows = []
        for seed in seeds:
            sc = sv.scenario_ab(name, seed, scen=scen)
            sim = sc["sim"]
            plan = sim.plan_workers()
            phys = sc["spec"].physical_map
            for node, pts in plan.items():
                sim.c.node = node                                    # the controller's current node, as at a visit
                for i, q in enumerate(pts):
                    ok, d, near = belongs(sim.c, q)
                    rows.append({"kind": "worker", "seed": seed, "node": node, "worker": i + 1, "distance_m": d, "nearest": near, "belongs": ok})
            for shift in shifts:
                ev = evaluate_plan(sc["road"], phys, plan, shift=shift)
                rows.append({"kind": "clearance", "seed": seed, "shift_m": shift, **ev})
        workers = [r for r in rows if r["kind"] == "worker"]
        out[name] = {
            "layout": sc["spec"].layout["kind"],
            "workers": len(workers),
            "max_distance_to_node_m": max(r["distance_m"] for r in workers),
            "max_distance_where": max(workers, key=lambda r: r["distance_m"]),
            "not_belonging": [r for r in workers if not r["belongs"]],
            "by_shift": {
                f"{shift:g}": {
                    "min_clearance_m": min(r["min_clearance_m"] for r in rows if r["kind"] == "clearance" and r["shift_m"] == shift),
                    "max_ask_distance_m": max(r["max_ask_distance_m"] for r in rows if r["kind"] == "clearance" and r["shift_m"] == shift),
                    "plans": sum(1 for r in rows if r["kind"] == "clearance" and r["shift_m"] == shift),
                    "plans_violating": sum(1 for r in rows if r["kind"] == "clearance" and r["shift_m"] == shift and r["violations"]),
                    "violating_seeds": sorted(r["seed"] for r in rows if r["kind"] == "clearance" and r["shift_m"] == shift and r["violations"]),
                } for shift in shifts},
        }
    return out


def markdown(res: dict, shifts) -> str:
    lines = ["| experiment | layout | workers | largest worker-to-node distance | all belong (<= 6.5 m, nearest node) | " +
             " | ".join(f"shift {s:g} m: smallest clearance / largest ask distance / plans violating" for s in shifts) + " |",
             "|---|---|---|---|---|" + "---|" * len(shifts)]
    for name, r in res.items():
        w = r["max_distance_where"]
        cells = []
        for s in shifts:
            b = r["by_shift"][f"{s:g}"]
            cells.append(f"{b['min_clearance_m']:.2f} m / {b['max_ask_distance_m']:.2f} m / {b['plans_violating']} of {b['plans']}")
        lines.append(f"| {name} | {r['layout']} | {r['workers']} | {r['max_distance_to_node_m']:.2f} m (seed {w['seed']}, {w['node']}, worker {w['worker']}) | "
                     f"{'yes' if not r['not_belonging'] else 'NO: ' + str(len(r['not_belonging']))} | " + " | ".join(cells) + " |")
    return "\n".join(lines)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--seeds", type=int, default=20)
    ap.add_argument("--label", default="")
    a = ap.parse_args(argv)
    v4_shift = float(hv.make_controller_v4().g["reask_shift_m"])
    shifts = tuple(sorted({UNITY_RESHIFT_M, v4_shift}))
    res = survey(seeds=range(1, a.seeds + 1), shifts=shifts)
    md = markdown(res, shifts)
    import subprocess
    commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    out = ROOT / "outputs" / f"layout_check_v4_{time.strftime('%Y%m%d_%H%M%S')}{'_' + a.label if a.label else ''}"
    out.mkdir(parents=True, exist_ok=False)
    (out / "report.json").write_text(json.dumps(res, indent=1, default=str), encoding="utf-8")
    (out / "report.md").write_text(md + "\n", encoding="utf-8")
    scen = sv.load_scenarios()
    (out / "config_used.json").write_text(json.dumps({"scenarios_ab": scen["scenarios"], "shifts_m": shifts, "clearance_m": CLEARANCE_M, "ask_zone_m": ASK_ZONE_M, "git_commit": commit}, indent=1),
                                          encoding="utf-8")
    print(md)
    print(f"\nFolder: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
