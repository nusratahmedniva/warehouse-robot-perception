"""Worker layout search for experiments A and B (Avatar/Config/experiments_ab.md section 15 addendum 3, declared before it ran).

A Python port of Unity's placement model (HRI/Scripts/V4/ExperimentPlanAB.cs: NodeProblem, ClearanceProblem, DrivableSegments, ReaskPosition,
NearerMargin, MaxActive), used to search:
  item 1: the beside junction slots (scenarios 1 to 3) under the path clearance with the controller's re-ask shift
          (configs/v4/control.json dialog.reask_shift_m), the declared choice rule, and the same search at the report-only clearance;
  item 2: three random workers at J1 of the v4 map (scenario 4, A4 / B4): existence on a lattice, the rules that bind, and the declared
          alternatives (a fixed third worker, a smaller clearance for one worker, a larger square);
  item 3: the slot table for Anisha's scenarios_ab.json.
Geometry only: config and map files, the saved ground-truth grid of one development run and the cell classification of the v4 NavMesh
verification. No trial result is read. Unity's Edit Mode tests (HRI/Tests/ExperimentClearanceTests.cs) re-check the chosen layout on every
planned run with Unity's own code; this tool is not the authority.

Usage, from the repository root with the project venv:
  Windows: robot_vision\\.venv\\Scripts\\python.exe finals_v4\\layout_search_v4.py
  macOS:   robot_vision/.venv/bin/python finals_v4/layout_search_v4.py
Writes a new folder <outputs>/layout_search_v4_<time>/ (report.md, slot_table.csv, result.json, run_info.json).
"""
from __future__ import annotations

import csv
import itertools
import json
import math
import subprocess
import sys
import time
from dataclasses import dataclass, replace
from datetime import datetime
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parent.parent
CONFIG = Path(__file__).with_suffix(".json")


def load(rel: str):
    return json.loads((REPO / rel).read_text(encoding="utf-8"))


# ---------------------------------------------------------------- maps and geometry (RoadmapV4 / ExperimentPlanAB)

class Map:
    def __init__(self, name: str, d: dict):
        self.name, self.start = name, d["start"]
        self.nodes = dict(d["nodes"])
        self.branches = {k: dict(v) for k, v in d["branches"].items()}

    def pos(self, n):
        nd = self.nodes[n]
        return (float(nd["x"]), float(nd["z"]))

    def arrival(self, n):
        nd = self.nodes[n]
        if nd.get("arrive_from"):
            a, b = self.pos(nd["arrive_from"]), self.pos(n)
            d = math.dist(a, b)
            return ((b[0] - a[0]) / d, (b[1] - a[1]) / d)
        y = math.radians(float(nd.get("start_yaw_deg", 0.0)))
        return (math.sin(y), math.cos(y))

    def ask_nodes(self):
        return [n for n in self.nodes if n == self.start] + [n for n, v in self.nodes.items() if v["kind"] == "junction"]

    def roads(self):
        return [(self.pos(n), self.pos(x)) for n, bs in self.branches.items() for x in bs.values()]

    def slot(self, n, s):
        """SlotPosition: s = (before_m, right_m) in the node's arrival frame; right = Cross(up, f) = (f.z, -f.x)."""
        f, c = self.arrival(n), self.pos(n)
        r = (f[1], -f[0])
        return (c[0] - f[0] * s[0] + r[0] * s[1], c[1] - f[1] * s[0] + r[1] * s[1])


def segd(p, a, b):
    abx, abz = b[0] - a[0], b[1] - a[1]
    L = abx * abx + abz * abz
    t = 0.0 if L <= 1e-12 else max(0.0, min(1.0, ((p[0] - a[0]) * abx + (p[1] - a[1]) * abz) / L))
    return math.hypot(p[0] - a[0] - t * abx, p[1] - a[1] - t * abz)


def ask_pos(w, frm, standoff):
    dx, dz = frm[0] - w[0], frm[1] - w[1]
    if dx * dx + dz * dz < 1e-12:
        dx, dz = 1.0, 0.0
    n = math.hypot(dx, dz)
    return (w[0] + dx / n * standoff, w[1] + dz / n * standoff)


def reask_pos(w, a, standoff, shift):
    if not shift > 0:
        return a
    hx, hz = w[0] - a[0], w[1] - a[1]
    if hx * hx + hz * hz < 1e-12:
        return a
    n = math.hypot(hx, hz)
    hx, hz = hx / n, hz / n
    return ask_pos(w, (a[0] + hz * shift, a[1] - hx * shift), standoff)


def drivable(m: Map, node, workers, standoff, shift):
    """DrivableSegments: node to each worker's ask position in every order, the return to the first (tie), every ask position and re-ask
    point to the next node of every branch. Returns (segments, asks)."""
    c, segs, asks = m.pos(node), [], []

    def add(p):
        if all(math.dist(p, q) >= 1e-3 for q in asks):
            asks.append(p)

    for perm in itertools.permutations(range(len(workers))):
        prev = c
        for k in range(len(perm) + 1):
            if k == len(perm) and len(perm) < 2:
                break
            i = perm[k] if k < len(perm) else perm[0]
            a = ask_pos(workers[i], prev, standoff)
            segs.append((prev, a))
            add(a)
            add(reask_pos(workers[i], a, standoff, shift))
            prev = a
    for a in asks:
        for x in m.branches.get(node, {}).values():
            segs.append((a, m.pos(x)))
    return segs, asks


@dataclass(frozen=True)
class Rules:
    sep: float
    turn: float
    min_road: float
    approach: float
    nearer: float
    clearance: float
    zone: float
    standoff: float
    shift: float
    navmesh: bool
    max_active: int
    act_radius: float
    act_step: float


class World:
    """The ground-truth grid (free cells for the workers) and the v4 NavMesh by V2's cell classification (for the robot's ask points)."""

    def __init__(self, grid: dict, disagreements_csv: Path):
        self.g = grid
        self.nav_off, self.nav_on = set(), set()
        with open(disagreements_csv, encoding="utf-8", newline="") as f:
            for r in csv.DictReader(f):
                (self.nav_off if r["class"] == "grid_free_navmesh_off" else self.nav_on).add((int(r["ix"]), int(r["iz"])))

    def cell(self, p):
        g = self.g
        ix, iz = math.floor((p[0] - g["origin_x"]) / g["cell_size_m"]), math.floor((p[1] - g["origin_z"]) / g["cell_size_m"])
        return (ix, iz) if 0 <= ix < g["cells_x"] and 0 <= iz < g["cells_z"] else None

    def free(self, p):
        c = self.cell(p)
        return c is not None and self.g["blocked_rows"][c[1]][c[0]] == "0"

    def on_nav(self, p):
        c = self.cell(p)
        if c is None or c in self.nav_off:
            return False
        return c in self.nav_on or self.g["blocked_rows"][c[1]][c[0]] == "0"


def nearer_margin(m: Map, node, other, first, approach):
    n, nd = m.pos(node), m.nodes[node]
    length, back = 0.0, (0.0, 0.0)
    if nd.get("arrive_from"):
        b = m.pos(nd["arrive_from"])
        bx, bz = b[0] - n[0], b[1] - n[1]
        L = math.hypot(bx, bz)
        length, back = min(approach, L), (bx / L, bz / L)
    steps = max(0, round(length / 0.05))
    best = math.inf
    for i in range(steps + 1):
        f = 0.0 if steps == 0 else length * i / steps
        q = (n[0] + back[0] * f, n[1] + back[1] * f)
        best = min(best, math.dist(q, other) - math.dist(q, first))
    return best


def node_problem(m: Map, phys: Map, node, pos, placed, R: Rules, world: World):
    """NodeProblem (+ ClearanceProblem): the first rule broken, or None. placed: [(node, slot, position)] of the nodes placed before."""
    turning = [m.pos(n) for n in m.ask_nodes()] + [phys.pos(n) for n in phys.ask_nodes()]
    roads = m.roads() + phys.roads()
    for i, p in enumerate(pos):
        for _, _, q in placed:
            if math.dist(p, q) < R.sep:
                return "separation from another node's worker"
        for j in range(i):
            if math.dist(p, pos[j]) < R.sep:
                return "separation"
        for t in turning:
            if math.dist(p, t) < R.turn:
                return "turning point"
        if R.min_road > 0 and any(segd(p, a, b) < R.min_road for a, b in roads):
            return "min_road_m"
        if world is not None and not world.free(p):
            return "blocked cell"
        if i > 0 and nearer_margin(m, node, p, pos[0], R.approach) < R.nearer:
            return "bystander margin"
    if R.clearance > 0 or R.zone > 0:
        return clearance_problem(m, node, pos, placed, roads, R, world)
    return None


def clearance_problem(m: Map, node, pos, placed, roads, R: Rules, world: World):
    segs, asks = drivable(m, node, pos, R.standoff, R.shift)
    c = m.pos(node)
    if R.zone > 0 and any(math.dist(a, c) > R.zone + 1e-4 for a in asks):
        return "ask zone"
    if R.navmesh and world is not None and not all(world.on_nav(a) for a in asks):
        return "ask point off the NavMesh"
    if not R.clearance > 0:
        return None
    clr = R.clearance - 1e-4
    for p in pos:
        if any(segd(p, a, b) < clr for a, b in roads):
            return "clearance from a road"
        if any(segd(p, a, b) < clr for a, b in segs):
            return "clearance from its own node's drive"
    for _, _, q in placed:
        if any(segd(q, a, b) < clr for a, b in segs):
            return "another node's worker within the clearance of this node's drive"
    before = []
    for n, _, _ in placed:
        if n not in before:
            before.append(n)
    for n in before:
        theirs = [q for nn, _, q in sorted((x for x in placed if x[0] == n), key=lambda x: x[1])]
        s2, _ = drivable(m, n, theirs, R.standoff, R.shift)
        if any(segd(p, a, b) < clr for p in pos for a, b in s2):
            return "clearance from an earlier node's drive"
    return None


def max_active(m: Map, workers, R: Rules):
    best = 0
    for a, b in m.roads():
        n = max(1, math.ceil(math.dist(a, b) / R.act_step))
        for i in range(n + 1):
            q = (a[0] + (b[0] - a[0]) * i / n, a[1] + (b[1] - a[1]) * i / n)
            best = max(best, sum(1 for w in workers if math.dist(q, w) <= R.act_radius))
    return best


def plan_beside(m: Map, phys: Map, sslots, jslots, three, R: Rules, world: World):
    """Plan a beside map (PlanRun's fixed slots): (problem, None) or (None, (largest own-ask distance, [(node, slot, position)]))."""
    placed, own = [], 0.0
    for node in m.ask_nodes():
        k = 2 + (1 if node in three else 0)
        slots = sslots if node == m.start else jslots
        if k > len(slots):
            return f"{node}: {k} workers but {len(slots)} slots", None
        pos = [m.slot(node, s) for s in slots[:k]]
        why = node_problem(m, phys, node, pos, placed, R, world)
        if why:
            return f"{m.name} {node}: {why}", None
        _, asks = drivable(m, node, pos, R.standoff, R.shift)
        own = max(own, max(math.dist(m.pos(node), a) for a in asks))
        placed += [(node, s, p) for s, p in enumerate(pos)]
    if max_active(m, [p for _, _, p in placed], R) > R.max_active:
        return f"{m.name}: active avatars", None
    return None, (own, placed)


# ---------------------------------------------------------------- item 1: beside slots

def frange(lo, hi, step):
    n = int(round((hi - lo) / step))
    return [round(lo + i * step, 6) for i in range(n + 1)]


def beside_pairs(maps, phys, sslots, R: Rules, world: World, S: dict, log):
    """The single slots passing the point rules at every junction of turn, turn_left and roadmap, and the slot pairs (slots 1, 2) valid on
    corridor, turn and turn_left."""
    cands = [(b, r) for b in frange(*S["slot_before_m"], S["slot_step_m"]) for r in frange(*S["slot_right_m"], S["slot_step_m"])
             if math.hypot(b, r) >= R.turn]
    jnodes = [(maps[n], j) for n in ("turn", "turn_left", "roadmap") for j in maps[n].ask_nodes() if j != maps[n].start]
    singles = []
    for s in cands:
        ok = True
        for m, j in jnodes:
            p = m.slot(j, s)
            turning = [m.pos(n) for n in m.ask_nodes()] + [phys.pos(n) for n in phys.ask_nodes()]
            if (any(math.dist(p, t) < R.turn for t in turning) or not world.free(p)
                    or any(segd(p, a, b) < R.clearance - 1e-4 for a, b in m.roads() + phys.roads())):
                ok = False
                break
        if ok:
            singles.append(s)
    log(f"  candidates {len(cands)}, single slots passing roads / turning points / free cells {len(singles)}")
    pairs = []
    for s0, s1 in itertools.permutations(singles, 2):
        if all(plan_beside(maps[n], phys, sslots, [s0, s1], (), R, world)[0] is None for n in ("corridor", "turn", "turn_left")):
            pairs.append((s0, s1))
    log(f"  pairs valid on corridor, turn, turn_left: {len(pairs)}")
    return singles, pairs


def search_beside(maps, phys, sslots, live_j, R: Rules, world: World, S: dict, log):
    """Pairs (slots 1, 2) on corridor, turn, turn_left; then slot 3 with 3 at J1 on roadmap. Returns (start problem, sorted valid sets)."""
    start_problem = None
    for name in ("corridor",):
        why, _ = plan_beside(maps[name], phys, sslots, live_j, (), R, world)
        if why:
            start_problem = why
    singles, pairs = beside_pairs(maps, phys, sslots, R, world, S, log)
    valid = []
    for s0, s1 in pairs:
        p0, p1 = maps["roadmap"].slot("J1", s0), maps["roadmap"].slot("J1", s1)
        for s2 in singles:
            if s2 in (s0, s1):
                continue
            p2 = maps["roadmap"].slot("J1", s2)
            if math.dist(p2, p0) < R.sep or math.dist(p2, p1) < R.sep:
                continue
            why, res = plan_beside(maps["roadmap"], phys, sslots, [s0, s1, s2], ("J1",), R, world)
            if why:
                continue
            own = res[0]
            for n in ("corridor", "turn", "turn_left"):
                own = max(own, plan_beside(maps[n], phys, sslots, [s0, s1, s2], (), R, world)[1][0])
            move = sum(math.dist(a, b) for a, b in zip((s0, s1, s2), live_j))
            valid.append({"slots": [s0, s1, s2], "own_max_m": own, "move_m": move})
    valid.sort(key=lambda v: (round(v["own_max_m"], 6), round(v["move_m"], 6), v["slots"]))
    log(f"  slot sets valid on every map (3 at J1 of roadmap): {len(valid)}")
    return start_problem, valid, len(singles), len(pairs)


# ---------------------------------------------------------------- item 2: three random workers at J1

RULES_POINT = ("turning point", "min_road_m", "road clearance", "free cell")
RULES_TRIPLE = ("separation", "bystander margin", "ask zone", "NavMesh (ask points)", "segment clearance")


def point_margins(m, phys, p, R, world):
    turning = [m.pos(n) for n in m.ask_nodes()] + [phys.pos(n) for n in phys.ask_nodes()]
    droad = min(segd(p, a, b) for a, b in m.roads() + phys.roads())
    return {"turning point": min(math.dist(p, t) for t in turning) - R.turn, "min_road_m": droad - R.min_road,
            "road clearance": droad - (R.clearance - 1e-4), "free cell": 0.0 if world.free(p) else -math.inf}


def triple_margins(m, node, pos, R, world):
    """pos sorted by distance to the node. Margins >= 0 pass (Unity's comparisons); per-worker smallest distance to the node's drive."""
    segs, asks = drivable(m, node, pos, R.standoff, R.shift)
    c = m.pos(node)
    per = [min(segd(p, a, b) for a, b in segs) for p in pos]
    return {"separation": min(math.dist(a, b) for a, b in itertools.combinations(pos, 2)) - R.sep,
            "bystander margin": min(nearer_margin(m, node, p, pos[0], R.approach) for p in pos[1:]) - R.nearer,
            "ask zone": R.zone + 1e-4 - max(math.dist(a, c) for a in asks),
            "NavMesh (ask points)": 0.0 if (not R.navmesh or all(world.on_nav(a) for a in asks)) else -math.inf,
            "segment clearance": min(per) - (R.clearance - 1e-4)}, per


def lattice(c, half, step):
    n = int(round(2 * half / step))
    return [(c[0] - half + i * step, c[1] - half + j * step) for i in range(n + 1) for j in range(n + 1)]


def j1_triples(m, phys, R, world, half, step, drop=None):
    """Every unordered lattice triple at J1 passing the point rules (all but `drop`), with its margins. Separation >= sep unless dropped."""
    c = m.pos("J1")
    pts = []
    for p in lattice(c, half, step):
        pm = point_margins(m, phys, p, R, world)
        if all(v >= 0 for k, v in pm.items() if k != drop):
            pts.append((p, pm))
    out = []
    for (a, ma), (b, mb), (d, md) in itertools.combinations(pts, 3):
        if drop != "separation" and (math.dist(a, b) < R.sep or math.dist(a, d) < R.sep or math.dist(b, d) < R.sep):
            continue
        pos = sorted([a, b, d], key=lambda p: math.dist(p, c))
        tm, per = triple_margins(m, "J1", pos, R, world)
        pm = {k: min(ma[k], mb[k], md[k]) for k in ma}
        out.append((pos, {**pm, **tm}, per))
    return len(pts), out


def is_valid(marg, drop=None):
    return all(v >= 0 for k, v in marg.items() if k != drop)


def mc_rate(m, phys, R, world, half, draws, seed, fixed=None, k=3):
    """Unity's random draw at J1 (k uniform points in the square, sorted by distance to the node), J1's own rules, estimated over `draws`.
    fixed: an extra worker at a fixed position (alternative (a)), drawn k = 2. Returns (accepted, draws)."""
    c = np.array(m.pos("J1"))
    rng = np.random.default_rng(seed)
    acc, done, chunk = 0, 0, 200000
    turning = np.array([m.pos(n) for n in m.ask_nodes()] + [phys.pos(n) for n in phys.ask_nodes()])
    roads = m.roads() + phys.roads()
    g = world.g
    blocked = np.array([[ch == "1" for ch in row] for row in g["blocked_rows"]])
    road_min = max(R.min_road, R.clearance - 1e-4)

    def point_ok(P):                                   # P (..., 2)
        ok = np.all(np.linalg.norm(P[..., None, :] - turning, axis=-1) >= R.turn, axis=-1)
        for a, b in roads:
            a, b = np.array(a), np.array(b)
            ab = b - a
            t = np.clip(((P - a) @ ab) / (ab @ ab), 0, 1)
            ok &= np.linalg.norm(P - (a + t[..., None] * ab), axis=-1) >= road_min
        ix = np.floor((P[..., 0] - g["origin_x"]) / g["cell_size_m"]).astype(int)
        iz = np.floor((P[..., 1] - g["origin_z"]) / g["cell_size_m"]).astype(int)
        inside = (ix >= 0) & (ix < g["cells_x"]) & (iz >= 0) & (iz < g["cells_z"])
        ok &= inside & ~blocked[np.clip(iz, 0, g["cells_z"] - 1), np.clip(ix, 0, g["cells_x"] - 1)]
        return ok

    while done < draws:
        n = min(chunk, draws - done)
        P = c + (rng.random((n, k, 2)) * 2 - 1) * half
        if fixed is not None:
            P = np.concatenate([P, np.broadcast_to(np.array(fixed), (n, 1, 2))], axis=1)
        ok = np.all(point_ok(P), axis=1)
        for i, j in itertools.combinations(range(P.shape[1]), 2):
            ok &= np.linalg.norm(P[:, i] - P[:, j], axis=-1) >= R.sep
        for idx in np.nonzero(ok)[0]:
            pos = sorted((tuple(map(float, q)) for q in P[idx]), key=lambda p: math.dist(p, tuple(c)))
            tm, _ = triple_margins(m, "J1", pos, R, world)
            acc += is_valid(tm)
        done += n
    return acc, draws


def fail_chance(p, draws):
    return 1.0 if p <= 0 else math.exp(draws * math.log1p(-p))


# ---------------------------------------------------------------- report

def slot_rows(maps, phys, sslots, jslots, R, world, label):
    rows = []
    for name, three, scen in (("corridor", (), "1"), ("turn", (), "2"), ("turn_left", (), "2 (left)"), ("roadmap", ("J1",), "3")):
        m = maps[name]
        why, res = plan_beside(m, phys, sslots, jslots, three, R, world)
        if why:
            rows.append({"layout": label, "scenario": scen, "map": name, "problem": why})
            continue
        own_by_node = {}
        for node in m.ask_nodes():
            ws = [p for n, _, p in res[1] if n == node]
            _, asks = drivable(m, node, ws, R.standoff, R.shift)
            own_by_node[node] = max(math.dist(m.pos(node), a) for a in asks)
        for node, s, p in res[1]:
            sl = (sslots if node == m.start else jslots)[s]
            nearest = min(m.nodes, key=lambda n: math.dist(p, m.pos(n)))
            rows.append({"layout": label, "scenario": scen, "map": name, "node": node, "slot": s + 1, "before_m": sl[0], "right_m": sl[1],
                         "x": round(p[0], 3), "z": round(p[1], 3), "distance_to_node_m": round(math.dist(p, m.pos(node)), 3),
                         "nearest_node": nearest, "own_ask_max_m": round(own_by_node[node], 3), "problem": ""})
    return rows


def git_head():
    try:
        return subprocess.run(["git", "rev-parse", "HEAD"], cwd=REPO, capture_output=True, text=True, check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def main():
    t0 = time.time()
    C = json.loads(CONFIG.read_text(encoding="utf-8"))
    S = C["search"]
    sc, U, ctl = load(C["scenarios_ab"]), load(C["experiments_unity"]), load(C["control_v4"])
    maps = {k: Map(k, v) for k, v in sc["maps"].items()}
    maps["roadmap"] = phys = Map("roadmap", load(C["roadmap_v4"]))
    world = World(load(C["grid"]), REPO / C["navmesh_cells"])
    pr = sc["placement_rule"]
    shift = float(ctl["dialog"]["reask_shift_m"])
    base = Rules(sep=pr["min_worker_separation_m"], turn=pr["min_turning_point_m"], min_road=0.0, approach=U["approach_m"],
                 nearer=U["nearer_margin_m"], clearance=U["path_clearance_m"], zone=U["answer_zone_radius_m"] - U["answer_zone_margin_m"],
                 standoff=U["ask_standoff_m"], shift=shift, navmesh=True, max_active=U["max_active_avatars"],
                 act_radius=U["activation_radius_m"], act_step=U["activation_sample_step_m"])
    sslots = [(s["before_m"], s["right_m"]) for s in U["start_slots"]]
    live_j = [(s["before_m"], s["right_m"]) for s in U["junction_slots"]]
    pend_j = [(s["before_m"], s["right_m"]) for s in U["clearance_layout"]["junction_slots"]]
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out = REPO / C["outputs"] / f"layout_search_v4_{stamp}"
    out.mkdir(parents=True, exist_ok=False)
    lines = []

    def log(s):
        print(s, flush=True)
        lines.append(s)

    result = {"reask_shift_m": shift, "clearance_m": base.clearance, "rules": base.__dict__}
    log(f"# Layout search v4 ({stamp})\n\nexperiments_ab.md section 15 addendum 3. Re-ask shift {shift} m (configs/v4/control.json), "
        f"clearance {base.clearance} m, zone {base.zone} m, standoff {base.standoff} m.\n")

    # the pending layout of addendum 1 under the 0.8 m shift
    why = [plan_beside(maps[n], phys, sslots, pend_j, ("J1",) if n == "roadmap" else (), base, world)[0] for n in ("corridor", "turn", "turn_left", "roadmap")]
    result["addendum1_pending_with_new_shift"] = [w for w in why if w]
    log("## Item 1\n\nAddendum 1's pending slots with the 0.8 m shift: " + ("pass" if not any(why) else "FAIL: " + "; ".join(w for w in why if w)))

    variants = {}
    for label, R in (("clearance 1.0 m, NavMesh requirement", base), ("clearance 1.0 m, without the NavMesh requirement", replace(base, navmesh=False)),
                     (f"clearance {S['report_clearance_m']} m (report only), NavMesh requirement", replace(base, clearance=S["report_clearance_m"]))):
        log(f"\n### {label}")
        sp, valid, ns, npairs = search_beside(maps, phys, sslots, live_j, R, world, S, log)
        log(f"  start slots unchanged: {'pass' if sp is None else 'FAIL: ' + sp}")
        zone_ok = len(valid)
        for v in valid[:8]:
            log(f"  {v['slots']}  own-ask max {v['own_max_m']:.3f} m, moved {v['move_m']:.2f} m")
        variants[label] = {"start_problem": sp, "valid": valid, "singles": ns, "pairs": npairs, "valid_count": zone_ok}
    result["item1"] = {k: {**v, "valid": v["valid"][:50]} for k, v in variants.items()}
    main_valid = variants["clearance 1.0 m, NavMesh requirement"]["valid"]
    chosen = main_valid[0]["slots"] if main_valid else None
    no_nav = variants["clearance 1.0 m, without the NavMesh requirement"]["valid"]
    result["chosen"] = chosen
    result["navmesh_changes_choice"] = bool(no_nav) and (not main_valid or no_nav[0]["slots"] != chosen)
    log(f"\nChosen (first by the choice rule): {chosen}; the NavMesh requirement changes the choice: {result['navmesh_changes_choice']}")
    rep14 = variants[f"clearance {S['report_clearance_m']} m (report only), NavMesh requirement"]["valid"]

    # ---- item 2
    log("\n## Item 2: three random workers at J1 (scenario 4)\n")
    rnd = replace(base, min_road=float(sc["scenarios"]["4"]["layout"]["min_road_m"]), nearer=U["random_nearer_margin_m"])
    half = float(sc["scenarios"]["4"]["layout"]["half_size_m"])
    m = phys
    n_lat = (int(round(2 * half / S["lattice_step_m"])) + 1) ** 2
    npts, trip = j1_triples(m, phys, rnd, world, half, S["lattice_step_m"])
    valid3 = [t for t in trip if is_valid(t[1])]
    rate_lat = 6 * len(valid3) / n_lat ** 3
    log(f"Lattice {S['lattice_step_m']} m over the {2 * half:g} m square: {n_lat} points, {npts} pass the point rules; "
        f"{len(trip)} triples keep the separation; **{len(valid3)} valid** (lattice acceptance estimate {rate_lat:.3g}).")
    item2 = {"lattice_points": n_lat, "point_rule_points": npts, "triples": len(trip), "valid": len(valid3), "rate_lattice": rate_lat}
    # which single rule binds
    drop_counts = {}
    for r in RULES_TRIPLE[1:]:
        drop_counts[r] = sum(1 for t in trip if is_valid(t[1], drop=r))
    for r in ("separation",) + RULES_POINT:
        _, tr = j1_triples(m, phys, rnd, world, half, S["lattice_step_m"], drop=r)
        drop_counts[r] = sum(1 for t in tr if is_valid(t[1], drop=r))
    log("Triples valid when ONE rule is dropped: " + ", ".join(f"{k} {v}" for k, v in drop_counts.items()))
    item2["drop_one"] = drop_counts
    fails = {}
    for t in trip:
        bad = tuple(k for k, v in t[1].items() if v < 0)
        fails[bad] = fails.get(bad, 0) + 1
    item2["fail_sets"] = {" + ".join(k) or "none": v for k, v in sorted(fails.items(), key=lambda kv: -kv[1])}
    log("Rules broken per triple (count): " + "; ".join(f"{k}: {v}" for k, v in list(item2["fail_sets"].items())[:8]))
    finite = [t for t in trip if all(math.isfinite(v) for v in t[1].values())]
    if finite:
        best = max(finite, key=lambda t: min(t[1].values()))
        worst_rule = min(best[1], key=best[1].get)
        item2["closest"] = {"workers": [[round(x, 3) for x in p] for p in best[0]], "margins": {k: round(v, 3) for k, v in best[1].items()},
                            "binding": worst_rule}
        log(f"Closest triple (largest smallest margin): {item2['closest']['workers']}, breaks {worst_rule} by {-best[1][worst_rule]:.3f} m; "
            f"margins {item2['closest']['margins']}")
    # (b) one worker with a smaller clearance
    best_c, best_t = -1.0, None
    for pos, marg, per in trip:
        if not is_valid(marg, drop="segment clearance"):
            continue
        for i in range(3):
            if all(per[j] >= rnd.clearance - 1e-4 for j in range(3) if j != i) and per[i] > best_c:
                best_c, best_t = per[i], (pos, i)
    step_c = S["relaxed_clearance_step_m"]
    item2["relaxed_one_worker"] = None if best_t is None else {
        "largest_m": round(best_c, 3), "in_steps_m": round(math.floor(best_c / step_c + 1e-9) * step_c, 2),
        "workers": [[round(x, 3) for x in p] for p in best_t[0]], "relaxed_worker": best_t[1] + 1}
    log(f"(b) one worker closer to J1's drive: {item2['relaxed_one_worker']}")
    # acceptance by Monte Carlo, the square sizes, (a) a fixed third worker
    draws = S["mc_draws"]
    sizes = {}
    for h in S["half_sizes_m"]:
        a, n = mc_rate(m, phys, rnd, world, h, draws, S["mc_seed"])
        p = a / n
        sizes[h] = {"accepted": a, "draws": n, "rate": p, "fail_chance_100k": fail_chance(p, U["random_max_draws"])}
        log(f"(c) half_size {h} m: {a} of {n} draws accepted (rate {p:.3g}); chance that {U['random_max_draws']} draws all fail "
            f"{sizes[h]['fail_chance_100k']:.3g}")
    item2["half_sizes"] = sizes
    ok_sizes = [h for h, v in sizes.items() if v["fail_chance_100k"] < S["fail_chance_max"]]
    item2["smallest_half_size_m"] = min(ok_sizes) if ok_sizes else None
    if chosen:
        fixed = m.slot("J1", chosen[2])
        a, n = mc_rate(m, phys, rnd, world, half, draws, S["mc_seed"], fixed=fixed, k=2)
        item2["fixed_third"] = {"slot": chosen[2], "position": [round(fixed[0], 3), round(fixed[1], 3)], "accepted": a, "draws": n,
                                "rate": a / n, "fail_chance_100k": fail_chance(a / n, U["random_max_draws"])}
        log(f"(a) third worker fixed at slot 3 {chosen[2]} = {item2['fixed_third']['position']}, two random: {a} of {n} accepted "
            f"(rate {a / n:.3g}); chance that {U['random_max_draws']} draws all fail {item2['fixed_third']['fail_chance_100k']:.3g}")
    result["item2"] = item2

    # ---- item 3
    rows = []
    if chosen:
        rows += slot_rows(maps, phys, sslots, chosen, base, world, "chosen (clearance 1.0 m)")
    if rep14:
        rows += slot_rows(maps, phys, sslots, rep14[0]["slots"], replace(base, clearance=S["report_clearance_m"]), world,
                          f"report only (clearance {S['report_clearance_m']} m)")
    fields = ["layout", "scenario", "map", "node", "slot", "before_m", "right_m", "x", "z", "distance_to_node_m", "nearest_node",
              "own_ask_max_m", "problem"]
    with open(out / "slot_table.csv", "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)
    result["slot_table_rows"] = len(rows)
    result["largest_worker_to_node_m"] = max((r["distance_to_node_m"] for r in rows if r.get("node") and r["layout"].startswith("chosen")), default=None)
    result["every_worker_nearest_its_node"] = all(r["nearest_node"] == r["node"] for r in rows if r.get("node") and r["layout"].startswith("chosen"))
    log(f"\n## Item 3\n\nSlot table: {len(rows)} rows (slot_table.csv). Largest worker-to-node distance {result['largest_worker_to_node_m']} m; "
        f"every worker's nearest node is its own: {result['every_worker_nearest_its_node']}.")
    result["seconds"] = round(time.time() - t0, 1)
    (out / "result.json").write_text(json.dumps(result, indent=1, default=str), encoding="utf-8")
    (out / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    (out / "run_info.json").write_text(json.dumps({"created": stamp, "git_commit": git_head(), "python": sys.version.split()[0],
                                                   "config": C, "tool": "finals_v4/layout_search_v4.py"}, indent=1), encoding="utf-8")
    print(f"\nwritten: {out.relative_to(REPO).as_posix()} ({result['seconds']} s)")


if __name__ == "__main__":
    main()
