"""Slot tables of the candidate layouts and alternative (a) of item 2 (Avatar/Config/experiments_ab.md section 15 addendum 3).

Item 1 found no beside slot set with three workers at J1, so there is no chosen layout to tabulate. This writes, for Nusrat and Anisha to
decide between (nothing is chosen or switched on):
  - the slot table (per scenario, asking node and worker: slot, before_m / right_m, position, distance to its node, nearest node, the
    node's largest own-ask distance, the worker's smallest distance to any road or drive) of three candidate layouts:
      P   the pending block of addendum 1 with two workers at J1 (what Unity's tests now pin at 0.8 m);
      i   alternative (i): the first pair by the declared choice rule with two at J1 (layout_search_v4_j1.py);
      iii alternative (iii): three at J1 with slot 3 at the reduced clearance (layout_search_v4_j1.py);
  - item 2's alternative (a): two random workers in J1's square plus a third at a fixed slot on the other side of the road, for the slot 3
    of P and of iii (item 1 has no slot 3 of its own), as Unity's draw would accept them (estimated over the configured draws).
Usage, from the repository root with the project venv:
  Windows: robot_vision\\.venv\\Scripts\\python.exe finals_v4\\layout_alternatives_v4.py
  macOS:   robot_vision/.venv/bin/python finals_v4/layout_alternatives_v4.py
Writes <outputs>/layout_alternatives_v4_<time>/ (slot_table.csv, report.md, result.json, run_info.json).
"""
from __future__ import annotations

import csv
import json
import math
import sys
from dataclasses import replace
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import layout_search_v4 as L  # noqa: E402

CANDIDATES = {
    "P": {"slots": [(3.5, -2.5), (-4.5, 3.5), (-5.0, -4.0)], "three_at_j1": False,
          "what": "pending block of addendum 1, two workers at J1 in every setting"},
    "i": {"slots": [(3.0, -2.0), (-2.5, 4.0)], "three_at_j1": False,
          "what": "alternative (i): first pair by the declared choice rule, two workers at J1 in every setting"},
    "iii": {"slots": [(3.5, -2.5), (-4.0, 4.0), (-4.5, -3.0)], "three_at_j1": True,
            "what": "alternative (iii): three at J1 in A3 / B3, slot 3 at 0.60 m from a drive (the others 1.0 m)"},
}


def main():
    C = json.loads(L.CONFIG.read_text(encoding="utf-8"))
    S = C["search"]
    sc, U, ctl = L.load(C["scenarios_ab"]), L.load(C["experiments_unity"]), L.load(C["control_v4"])
    maps = {k: L.Map(k, v) for k, v in sc["maps"].items()}
    maps["roadmap"] = phys = L.Map("roadmap", L.load(C["roadmap_v4"]))
    world = L.World(L.load(C["grid"]), L.REPO / C["navmesh_cells"])
    pr = sc["placement_rule"]
    R = L.Rules(sep=pr["min_worker_separation_m"], turn=pr["min_turning_point_m"], min_road=0.0, approach=U["approach_m"],
                nearer=U["nearer_margin_m"], clearance=U["path_clearance_m"], zone=U["answer_zone_radius_m"] - U["answer_zone_margin_m"],
                standoff=U["ask_standoff_m"], shift=float(ctl["dialog"]["reask_shift_m"]), navmesh=True, max_active=U["max_active_avatars"],
                act_radius=U["activation_radius_m"], act_step=U["activation_sample_step_m"])
    sslots = [(s["before_m"], s["right_m"]) for s in U["start_slots"]]
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out = L.REPO / C["outputs"] / f"layout_alternatives_v4_{stamp}"
    out.mkdir(parents=True, exist_ok=False)
    rows, result, lines = [], {"rules": R.__dict__, "candidates": {}}, [f"# Candidate layouts and item 2 (a) ({stamp})", ""]
    for key, cand in CANDIDATES.items():
        jslots = cand["slots"]
        info = {"what": cand["what"], "slots": jslots, "maps": {}}
        for name, scen in (("corridor", "1"), ("turn", "2"), ("turn_left", "2 (left)"), ("roadmap", "3")):
            m = maps[name]
            three = ("J1",) if (cand["three_at_j1"] and name == "roadmap") else ()
            # every rule but the clearance through the planner; the clearance per worker below (iii relaxes slot 3 only)
            why, res = L.plan_beside(m, phys, sslots, jslots, three, replace(R, clearance=0.0), world)
            if why:
                info["maps"][name] = why
                continue
            placed = res[1]
            segs = m.roads() + phys.roads()
            own = {}
            for node in m.ask_nodes():
                ws = [p for n, _, p in placed if n == node]
                s, asks = L.drivable(m, node, ws, R.standoff, R.shift)
                segs += s
                own[node] = max(math.dist(m.pos(node), a) for a in asks)
            worst = 1e9
            for node, s, p in placed:
                sl = (sslots if node == m.start else jslots)[s]
                clear = min(L.segd(p, a, b) for a, b in segs)
                relaxed = cand["three_at_j1"] and name == "roadmap" and node == "J1" and s == 2
                if not relaxed:
                    worst = min(worst, clear)
                rows.append({"layout": key, "scenario": scen, "map": name, "node": node, "slot": s + 1, "before_m": sl[0], "right_m": sl[1],
                             "x": round(p[0], 3), "z": round(p[1], 3), "distance_to_node_m": round(math.dist(p, m.pos(node)), 3),
                             "nearest_node": min(m.nodes, key=lambda n: math.dist(p, m.pos(n))), "own_ask_max_m": round(own[node], 3),
                             "clearance_m": round(clear, 3), "relaxed": relaxed})
            info["maps"][name] = "pass" if worst >= R.clearance - 1e-4 else f"clearance {worst:.3f} m"
        mine = [r for r in rows if r["layout"] == key]
        info["largest_worker_to_node_m"] = max(r["distance_to_node_m"] for r in mine)
        info["largest_own_ask_m"] = max(r["own_ask_max_m"] for r in mine)
        info["nearest_node_is_own"] = all(r["nearest_node"] == r["node"] for r in mine)
        result["candidates"][key] = info
        lines.append(f"- {key} ({cand['what']}): {info['maps']}; largest worker-to-node {info['largest_worker_to_node_m']} m, largest own-ask "
                     f"{info['largest_own_ask_m']} m, every worker nearest its own node: {info['nearest_node_is_own']}")
    with open(out / "slot_table.csv", "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    # item 2 (a): a fixed third worker on the other side of the road, two random in the square
    rnd = replace(R, min_road=float(sc["scenarios"]["4"]["layout"]["min_road_m"]), nearer=U["random_nearer_margin_m"])
    half = float(sc["scenarios"]["4"]["layout"]["half_size_m"])
    lines += ["", "## Item 2 (a): a third worker at a fixed slot, two random in J1's square", ""]
    result["item2_a"] = {}
    for key in ("P", "iii"):
        slot = CANDIDATES[key]["slots"][2]
        fixed = phys.slot("J1", slot)
        a, n = L.mc_rate(phys, phys, rnd, world, half, S["mc_draws"], S["mc_seed"], fixed=fixed, k=2)
        fc = L.fail_chance(a / n, U["random_max_draws"])
        result["item2_a"][key] = {"slot": slot, "position": [round(fixed[0], 3), round(fixed[1], 3)], "accepted": a, "draws": n,
                                  "rate": a / n, "fail_chance_100k": fc}
        lines.append(f"- slot 3 of {key} {slot} = ({fixed[0]:.2f}, {fixed[1]:.2f}): {a} of {n} draws accepted (rate {a / n:.3g}); chance "
                     f"that {U['random_max_draws']} draws all fail {fc:.3g}")
    (out / "result.json").write_text(json.dumps(result, indent=1, default=str), encoding="utf-8")
    (out / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    (out / "run_info.json").write_text(json.dumps({"created": stamp, "git_commit": L.git_head(), "python": sys.version.split()[0],
                                                   "config": C, "tool": "finals_v4/layout_alternatives_v4.py"}, indent=1), encoding="utf-8")
    print("\n".join(lines))
    print(f"\nwritten: {out.relative_to(L.REPO).as_posix()}")


if __name__ == "__main__":
    main()
