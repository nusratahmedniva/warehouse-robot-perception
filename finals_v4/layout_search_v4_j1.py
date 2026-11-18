"""Why no beside layout has three workers at J1 with the 0.8 m re-ask shift, and the closest alternatives
(Avatar/Config/experiments_ab.md section 15 addendum 3, amendment of 2026-11-17, declared before this ran).

Uses the model of finals_v4/layout_search_v4.py (same config file, same rules: clearance 1.0 m, the NavMesh requirement, shift from
configs/v4/control.json). Computes:
  binding: over every slot triple whose slots 1 and 2 are a pair valid on corridor, turn and turn_left and whose three J1 positions are
           3.0 m apart, the rules the triple breaks at J1 of roadmap (A's workers placed), and the triples valid when one rule is dropped;
  (i)   2 workers at J1 in A3 / B3 too: the first pair by the declared choice rule on every map;
  (ii)  the ask zone dropped: the smallest largest own-ask distance of a set valid on every map otherwise, and the zone radius it needs;
  (iii) a smaller clearance for slot 3 only: the largest value (0.05 m steps) with every other worker 1.0 m from every drive and road.
Geometry only. Writes <outputs>/layout_search_v4_j1_<time>/ (report.md, result.json, run_info.json).
Usage, from the repository root with the project venv:
  Windows: robot_vision\\.venv\\Scripts\\python.exe finals_v4\\layout_search_v4_j1.py
  macOS:   robot_vision/.venv/bin/python finals_v4/layout_search_v4_j1.py
"""
from __future__ import annotations

import json
import math
import sys
import time
from collections import Counter
from dataclasses import replace
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import layout_search_v4 as L  # noqa: E402

CLEAR_RULES = ("clearance from a road", "clearance from J1's own drive", "A's workers within J1's drive", "clearance from A's drive")


def j1_breaks(m, phys, pos, placed_a, R, world):
    """Every rule the J1 workers (slot order) break, Unity's checks at J1 with A placed; and each J1 worker's smallest distance to any
    road or drive (own, A's)."""
    out = set()
    turning = [m.pos(n) for n in m.ask_nodes()] + [phys.pos(n) for n in phys.ask_nodes()]
    roads = m.roads() + phys.roads()
    for i, p in enumerate(pos):
        if any(math.dist(p, q) < R.sep for _, _, q in placed_a) or any(math.dist(p, pos[j]) < R.sep for j in range(i)):
            out.add("separation")
        if any(math.dist(p, t) < R.turn for t in turning):
            out.add("turning point")
        if not world.free(p):
            out.add("blocked cell")
        if i > 0 and L.nearer_margin(m, "J1", p, pos[0], R.approach) < R.nearer:
            out.add("bystander margin")
    segs, asks = L.drivable(m, "J1", pos, R.standoff, R.shift)
    c = m.pos("J1")
    if any(math.dist(a, c) > R.zone + 1e-4 for a in asks):
        out.add("ask zone")
    if R.navmesh and not all(world.on_nav(a) for a in asks):
        out.add("NavMesh (ask points)")
    a_pos = [q for _, _, q in sorted(placed_a, key=lambda x: x[1])]
    a_segs, _ = L.drivable(m, "A", a_pos, R.standoff, R.shift)
    clr = R.clearance - 1e-4
    per = []
    for p in pos:
        dr = min(L.segd(p, a, b) for a, b in roads)
        do = min(L.segd(p, a, b) for a, b in segs)
        da = min(L.segd(p, a, b) for a, b in a_segs)
        per.append(min(dr, do, da))
        if dr < clr:
            out.add("clearance from a road")
        if do < clr:
            out.add("clearance from J1's own drive")
        if da < clr:
            out.add("clearance from A's drive")
    if any(L.segd(q, a, b) < clr for q in a_pos for a, b in segs):
        out.add("A's workers within J1's drive")
    return out, per


def roadmap_worker_clearance(m, phys, sslots, jslots, R):
    """Every roadmap worker's (node, slot, position, smallest distance to any road or any node's drive), 3 at J1."""
    placed = []
    for node in m.ask_nodes():
        k = 3 if node == "J1" else 2
        sl = sslots if node == m.start else jslots
        placed += [(node, s, m.slot(node, sl[s])) for s in range(k)]
    segs = m.roads() + phys.roads()
    for node in m.ask_nodes():
        ws = [p for n, _, p in placed if n == node]
        segs += L.drivable(m, node, ws, R.standoff, R.shift)[0]
    return [(n, s, p, min(L.segd(p, a, b) for a, b in segs)) for n, s, p in placed]


def own_max_all(maps, phys, sslots, jslots, R, world, three_at_j1):
    own = 0.0
    for name in ("corridor", "turn", "turn_left", "roadmap"):
        why, res = L.plan_beside(maps[name], phys, sslots, jslots, ("J1",) if (three_at_j1 and name == "roadmap") else (), R, world)
        if why:
            return None, why
        own = max(own, res[0])
    return own, None


def main():
    t0 = time.time()
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
    live_j = [(s["before_m"], s["right_m"]) for s in U["junction_slots"]]
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out = L.REPO / C["outputs"] / f"layout_search_v4_j1_{stamp}"
    out.mkdir(parents=True, exist_ok=False)
    lines, result = [], {"rules": R.__dict__}

    def log(s):
        print(s, flush=True)
        lines.append(s)

    log(f"# Three workers at J1, beside layout ({stamp})\n\nexperiments_ab.md section 15 addendum 3, amendment. Shift {R.shift} m, clearance "
        f"{R.clearance} m, zone {R.zone} m, NavMesh requirement on.\n")
    singles, pairs = L.beside_pairs(maps, phys, sslots, R, world, S, log)
    _, pairs_nz = L.beside_pairs(maps, phys, sslots, replace(R, zone=0.0), world, S, log)
    pair_set = set(pairs)
    m = phys
    placed_a = [("A", i, m.slot("A", s)) for i, s in enumerate(sslots[:2])]
    trip = []
    for s0, s1 in pairs_nz:
        p0, p1 = m.slot("J1", s0), m.slot("J1", s1)
        if math.dist(p0, p1) < R.sep:
            continue
        for s2 in singles:
            if s2 in (s0, s1):
                continue
            p2 = m.slot("J1", s2)
            if math.dist(p2, p0) < R.sep or math.dist(p2, p1) < R.sep:
                continue
            br, per = j1_breaks(m, phys, [p0, p1, p2], placed_a, R, world)
            trip.append(((s0, s1, s2), br, per, (s0, s1) in pair_set))
    base = [t for t in trip if t[3]]
    log(f"\n## Binding rules at J1\n\nTriples (slots 1-2 a valid pair, J1 positions 3.0 m apart): {len(base)}; valid at J1: "
        f"{sum(1 for t in base if not t[1])}.")
    sets = Counter(" + ".join(sorted(t[1])) or "none" for t in base)
    log("Rules broken (count of triples):\n" + "\n".join(f"- {k}: {v}" for k, v in sets.most_common()))
    rules = sorted({r for t in base for r in t[1]})
    drop = {r: sum(1 for t in base if t[1] <= {r}) for r in rules}
    drop["the four clearance rules together"] = sum(1 for t in base if t[1] <= set(CLEAR_RULES))
    log("Triples valid at J1 when one rule is dropped: " + ", ".join(f"{k} {v}" for k, v in drop.items()))
    per_rule = Counter(r for t in base for r in t[1])
    log("Triples breaking each rule: " + ", ".join(f"{k} {v}" for k, v in per_rule.most_common()))
    result["binding"] = {"triples": len(base), "valid_at_j1": sum(1 for t in base if not t[1]), "break_sets": dict(sets),
                         "valid_if_dropped": drop, "breaking_each_rule": dict(per_rule)}

    # (i) two at J1
    two = []
    for s0, s1 in pairs:
        own, why = own_max_all(maps, phys, sslots, [s0, s1], R, world, False)
        if own is not None:
            two.append({"slots": [s0, s1], "own_max_m": own, "move_m": sum(math.dist(a, b) for a, b in zip((s0, s1), live_j))})
    two.sort(key=lambda v: (round(v["own_max_m"], 6), round(v["move_m"], 6), v["slots"]))
    result["i_two_at_j1"] = {"valid": len(two), "first": two[:10]}
    log(f"\n## (i) 2 workers at J1\n\nPairs valid on every map (2 per asking node): {len(two)}.")
    for v in two[:5]:
        log(f"- {v['slots']}: largest own-ask distance {v['own_max_m']:.3f} m, moved {v['move_m']:.2f} m")

    # (ii) the zone dropped
    Rz = replace(R, zone=0.0)
    zone_c = []
    for slots, br, per, _ in trip:
        if br <= {"ask zone"}:
            own, why = own_max_all(maps, phys, sslots, list(slots), Rz, world, True)
            if own is not None:
                zone_c.append({"slots": list(slots), "own_max_m": own, "move_m": sum(math.dist(a, b) for a, b in zip(slots, live_j))})
    zone_c.sort(key=lambda v: (round(v["own_max_m"], 6), round(v["move_m"], 6), v["slots"]))
    margin = U["answer_zone_margin_m"]
    limit = min(math.dist(m.pos(a), m.pos(b)) for a in m.ask_nodes() for b in m.ask_nodes() if a < b) / 2
    result["ii_zone"] = {"valid": len(zone_c), "first": zone_c[:10], "overlap_limit_m": limit,
                         "zone_needed_m": round(zone_c[0]["own_max_m"] + margin, 3) if zone_c else None}
    log(f"\n## (ii) ask zone dropped\n\nSets valid on every map otherwise: {len(zone_c)}." + (
        f" Smallest largest own-ask distance {zone_c[0]['own_max_m']:.3f} m ({zone_c[0]['slots']}), so the zone radius would be "
        f"{zone_c[0]['own_max_m'] + margin:.2f} m (zones overlap beyond {limit:.2f} m)." if zone_c else ""))
    for v in zone_c[1:5]:
        log(f"- {v['slots']}: {v['own_max_m']:.3f} m, moved {v['move_m']:.2f} m")

    # (iii) a smaller clearance for slot 3 only
    clr = R.clearance - 1e-4
    cand = sorted((t for t in trip if t[3] and t[1] <= set(CLEAR_RULES) and t[2][0] >= clr and t[2][1] >= clr
                   and "A's workers within J1's drive" not in t[1]), key=lambda t: -t[2][2])
    best = None
    R0 = replace(R, clearance=0.0)
    for slots, br, per, _ in cand:
        if L.plan_beside(m, phys, sslots, list(slots), ("J1",), R0, world)[0] is not None:
            continue
        ws = roadmap_worker_clearance(m, phys, sslots, list(slots), R)
        others = [d for n, s, p, d in ws if not (n == "J1" and s == 2)]
        if min(others) < clr:
            continue
        c3 = next(d for n, s, p, d in ws if n == "J1" and s == 2)
        best = {"slots": list(slots), "slot3_clearance_m": round(c3, 3),
                "in_steps_m": round(math.floor(c3 / S["relaxed_clearance_step_m"] + 1e-9) * S["relaxed_clearance_step_m"], 2),
                "own_max_m": round(own_max_all(maps, phys, sslots, list(slots), R0, world, True)[0] or -1, 3)}
        break
    result["iii_slot3_clearance"] = best
    log(f"\n## (iii) smaller clearance for slot 3 only\n\nCandidates {len(cand)}; best: {best}")
    result["seconds"] = round(time.time() - t0, 1)
    (out / "result.json").write_text(json.dumps(result, indent=1, default=str), encoding="utf-8")
    (out / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    (out / "run_info.json").write_text(json.dumps({"created": stamp, "git_commit": L.git_head(), "python": sys.version.split()[0],
                                                   "config": C, "tool": "finals_v4/layout_search_v4_j1.py"}, indent=1), encoding="utf-8")
    print(f"\nwritten: {out.relative_to(L.REPO).as_posix()} ({result['seconds']} s)")


if __name__ == "__main__":
    main()
