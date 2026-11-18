"""Checkpoint workers on every branch: feasibility, proposed positions, people in view, active avatars (report only).

Avatar/Config/experiments_ab.md section 15 addendum 5, item 3c (rules, choice rule and visibility model declared there before this ran).
Geometry only, on top of finals_v4/layout_search_v4.py's port of Unity's placement model: config and map files, the saved ground-truth
grid and the NavMesh cell classification of layout_search_v4.json, and the plans and obstacle footprints that item 1's temporary Editor
script exported from Unity's own planner (worker_path_check_<time>/plans.json, footprints.json). No trial result is read; nothing is
built or changed.

Usage, from the repository root with the project venv:
  Windows: robot_vision\\.venv\\Scripts\\python.exe finals_v4\\checkpoint_feasibility_v4.py robot_vision\\outputs\\worker_path_check_<time>
  macOS:   robot_vision/.venv/bin/python finals_v4/checkpoint_feasibility_v4.py robot_vision/outputs/worker_path_check_<time>
Writes a new folder <outputs>/checkpoint_feasibility_v4_<time>/ (report.md, branches.csv, proposals.csv, asks.csv, driving.csv,
result.json, run_info.json).
"""
from __future__ import annotations

import csv
import itertools
import json
import math
import sys
import time
from collections import Counter, defaultdict
from dataclasses import replace
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import layout_search_v4 as ls  # noqa: E402  (the port: Map, World, Rules, drivable, segd, ask_pos, reask_pos, nearer_margin, max_active, plan_beside)

REPO = ls.REPO
LATERAL = [1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0, 4.5]
S_STEP = 0.5
RENDER_M = None            # activation_radius_m, read from Unity's config
RANGE_M = None             # hri_perception.json evaluation detection_range_m
OCCLUDERS = ("Shelves", "Walls")
PANTILT_W, PANTILT_H = 730, 530
P_RULES = ["P1 separation", "P2 turning points", "P3 free cell", "P4 road clearance", "P5 node drives", "P6 own drive",
           "P7 NavMesh", "P8 ask zone", "P9 bystander margin", "P10 active avatars"]
Q_RULES = ["Q1 second opinion", "Q2 answerer 3.5 m", "Q3 zones 12.0 m"]


# ---------------------------------------------------------------- line of sight against the footprints

class Occlusion:
    def __init__(self, footprints: list[dict]):
        self.hulls = []
        for f in footprints:
            if f["group"] in OCCLUDERS:
                h = [tuple(p) for p in f["hull"]]
                xs, zs = [p[0] for p in h], [p[1] for p in h]
                self.hulls.append((h, min(xs), max(xs), min(zs), max(zs)))
        self.cache: dict = {}

    @staticmethod
    def _inside(h, p):
        sign = 0
        for i in range(len(h)):
            a, b = h[i], h[(i + 1) % len(h)]
            c = (b[0] - a[0]) * (p[1] - a[1]) - (b[1] - a[1]) * (p[0] - a[0])
            if abs(c) < 1e-12:
                continue
            s = 1 if c > 0 else -1
            if sign == 0:
                sign = s
            elif s != sign:
                return False
        return True

    @staticmethod
    def _cross(p, q, a, b):
        def o(u, v, w):
            return (v[0] - u[0]) * (w[1] - u[1]) - (v[1] - u[1]) * (w[0] - u[0])
        d1, d2, d3, d4 = o(a, b, p), o(a, b, q), o(p, q, a), o(p, q, b)
        return (d1 > 0) != (d2 > 0) and (d3 > 0) != (d4 > 0)

    def blocked(self, p, q) -> bool:
        key = (round(p[0], 2), round(p[1], 2), round(q[0], 2), round(q[1], 2))
        if key in self.cache:
            return self.cache[key]
        lox, hix, loz, hiz = min(p[0], q[0]), max(p[0], q[0]), min(p[1], q[1]), max(p[1], q[1])
        res = False
        for h, x0, x1, z0, z1 in self.hulls:
            if x1 < lox or x0 > hix or z1 < loz or z0 > hiz:
                continue
            if self._inside(h, p) or self._inside(h, q) or any(self._cross(p, q, h[i], h[(i + 1) % len(h)]) for i in range(len(h))):
                res = True
                break
        self.cache[key] = res
        return res


def hfov_deg(vfov_deg: float) -> float:
    return 2.0 * math.degrees(math.atan(math.tan(math.radians(vfov_deg / 2.0)) * PANTILT_W / PANTILT_H))


def bearing(frm, to):
    return math.degrees(math.atan2(to[0] - frm[0], to[1] - frm[1]))


def angdiff(a, b):
    return abs((a - b + 180.0) % 360.0 - 180.0)


def in_view(robot, people, occ: Occlusion, pan_dir_deg=None, half_fov=None):
    """People (list of (label, (x, z))) in view: rendered (<= RENDER_M), in range (<= RANGE_M), line of sight; pan-tilt also within
    half_fov of pan_dir_deg. Returns (360 count, pan-tilt count, labels in pan-tilt)."""
    n360, npt, labels = 0, 0, []
    for lab, p in people:
        d = math.dist(robot, p)
        if d > RENDER_M or d > RANGE_M or occ.blocked(robot, p):
            continue
        n360 += 1
        if pan_dir_deg is not None and (d < 1e-6 or angdiff(bearing(robot, p), pan_dir_deg) <= half_fov):
            npt += 1
            labels.append(lab)
    return n360, npt, labels


# ---------------------------------------------------------------- the checkpoint model

def branches(m: ls.Map):
    return [(n, cmd, x) for n, bs in m.branches.items() for cmd, x in bs.items()]


def node_workers(placed):
    by = defaultdict(list)
    for n, s, p in sorted(placed, key=lambda t: (t[0], t[1])):
        by[n].append(p)
    return by


def node_drives(m, placed, R):
    """Every asking node's drivable segments and ask points (with the asked worker) for these workers."""
    segs, asks = [], []
    for n, ws in node_workers(placed).items():
        s, a = ls.drivable(m, n, ws, R.standoff, R.shift)
        segs += s
        for q in a:
            who = next((w for w in ws if abs(math.dist(q, w) - R.standoff) < 1e-3), None)
            asks.append((n, q, who))
    return segs, asks


def checkpoint_geometry(m, start, end, w, R):
    """The checkpoint's ask points (both directions, re-ask included) and its own drive."""
    S, E = m.pos(start), m.pos(end)
    asks, segs = [], []
    for X in (S, E):
        a = ls.ask_pos(w, X, R.standoff)
        r = ls.reask_pos(w, a, R.standoff, R.shift)
        segs.append((X, a))
        for q in (a, r):
            asks.append(q)
            segs += [(q, S), (q, E)]
    return asks, segs


def candidate_rules(m, phys, start, end, s, l, placed, base_segs, base_asks, others, R, world, so_radius, ask_max, zone_gap):
    """Rule results (True = passes) of one candidate; others = the other checkpoints [(anchor, worker, own drive segments)]."""
    S, E = m.pos(start), m.pos(end)
    L = math.dist(S, E)
    f = ((E[0] - S[0]) / L, (E[1] - S[1]) / L)
    r = (f[1], -f[0])
    anchor = (S[0] + f[0] * s, S[1] + f[1] * s)
    w = (anchor[0] + r[0] * l, anchor[1] + r[1] * l)
    nodes_w = [p for _, _, p in placed]
    asking = [m.pos(n) for n in m.ask_nodes()] + [phys.pos(n) for n in phys.ask_nodes()]
    roads = m.roads() + phys.roads()
    asks, segs = checkpoint_geometry(m, start, end, w, R)
    clr = R.clearance - 1e-4
    all_w = nodes_w + [o[1] for o in others]
    res = {}
    res["P1 separation"] = all(math.dist(w, q) >= R.sep for q in all_w)
    res["P2 turning points"] = (all(math.dist(w, t) >= R.turn for t in asking + [o[0] for o in others])
                                and all(math.dist(q, anchor) >= R.turn for q in all_w))
    res["P3 free cell"] = world.free(w)
    res["P4 road clearance"] = all(ls.segd(w, a, b) >= clr for a, b in roads)
    res["P5 node drives"] = all(ls.segd(w, a, b) >= clr for a, b in base_segs + [sg for o in others for sg in o[2]])
    res["P6 own drive"] = all(ls.segd(q, a, b) >= clr for q in all_w + [w] for a, b in segs)
    res["P7 NavMesh"] = all(world.on_nav(q) for q in asks)
    res["P8 ask zone"] = all(math.dist(q, anchor) <= R.zone + 1e-4 for q in asks)
    nw = node_workers(placed)
    res["P9 bystander margin"] = all(ls.nearer_margin(m, n, w, nw[n][0], R.approach) >= R.nearer for n in m.ask_nodes() if nw.get(n))
    res["P10 active avatars"] = ls.max_active(m, all_w + [w], R) <= R.max_active
    nearest = min(m.nodes, key=lambda n: math.dist(w, m.pos(n)))
    res["Q1 second opinion"] = not (nearest in m.ask_nodes() and math.dist(w, m.pos(nearest)) <= so_radius)
    res["Q2 answerer 3.5 m"] = (all(math.dist(w, q) > ask_max for _, q, _ in base_asks)
                                and all(math.dist(p, q) > ask_max for p in all_w for q in asks))
    res["Q3 zones 12.0 m"] = all(math.dist(anchor, t) >= zone_gap for t in [m.pos(n) for n in m.ask_nodes()])
    return res, anchor, w, asks, segs


# ---------------------------------------------------------------- main

def route(m: ls.Map, goal):
    """Nodes from the start to the goal through the map's branches (a tree)."""
    def walk(n, acc):
        if n == goal:
            return acc + [n]
        for x in m.branches.get(n, {}).values():
            r = walk(x, acc + [n])
            if r:
                return r
        return None
    return walk(m.start, [])


def samples_along(pts, step):
    out = []
    for a, b in zip(pts, pts[1:]):
        L = math.dist(a, b)
        n = max(1, math.ceil(L / step))
        h = bearing(a, b)
        out += [((a[0] + (b[0] - a[0]) * i / n, a[1] + (b[1] - a[1]) * i / n), h) for i in range(n)]
    out.append((pts[-1], bearing(pts[-2], pts[-1])))
    return out


def main(argv):
    global RENDER_M, RANGE_M
    if len(argv) < 2:
        raise SystemExit(__doc__)
    t0 = time.time()
    export = Path(argv[1])
    export = export if export.is_absolute() else (Path.cwd() / export)
    C = json.loads(ls.CONFIG.read_text(encoding="utf-8"))
    sc, U, ctl = ls.load(C["scenarios_ab"]), ls.load(C["experiments_unity"]), ls.load(C["control_v4"])
    perc = ls.load("robot_vision/configs/hri_perception.json")
    unity_robot = ls.load("unity/Robotics-Warehouse/WarehouseProjectURP/Assets/WarehouseRobot/Robot/Config/robot_unity_v4.json")
    RENDER_M, RANGE_M = float(U["activation_radius_m"]), float(perc["evaluation"]["detection_range_m"])
    half_fov = hfov_deg(float(unity_robot["pan_tilt_camera"]["vertical_fov_deg"])) / 2.0
    so_radius = float(ctl["lie_detection"]["second_opinion_radius_m"])
    ask_max = float(U["ask_max_distance_m"])
    zone_gap = 2.0 * float(U["answer_zone_radius_m"])
    maps = {k: ls.Map(k, v) for k, v in sc["maps"].items()}
    maps["roadmap"] = phys = ls.Map("roadmap", ls.load(C["roadmap_v4"]))
    world = ls.World(ls.load(C["grid"]), REPO / C["navmesh_cells"])
    pr = sc["placement_rule"]
    R = ls.Rules(sep=pr["min_worker_separation_m"], turn=pr["min_turning_point_m"], min_road=0.0, approach=U["approach_m"],
                 nearer=U["nearer_margin_m"], clearance=U["path_clearance_m"], zone=U["answer_zone_radius_m"] - U["answer_zone_margin_m"],
                 standoff=U["ask_standoff_m"], shift=float(ctl["dialog"]["reask_shift_m"]), navmesh=True, max_active=U["max_active_avatars"],
                 act_radius=U["activation_radius_m"], act_step=U["activation_sample_step_m"])
    sslots = [(s["before_m"], s["right_m"]) for s in U["start_slots"]]
    jslots = [(s["before_m"], s["right_m"]) for s in U["junction_slots"]]
    plans = json.loads((export / "plans.json").read_text(encoding="utf-8"))["plans"]
    occ = Occlusion(json.loads((export / "footprints.json").read_text(encoding="utf-8"))["footprints"])
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out = REPO / C["outputs"] / f"checkpoint_feasibility_v4_{stamp}"
    out.mkdir(parents=True, exist_ok=False)
    L = [f"# Checkpoint workers on every branch ({stamp})", "",
         "experiments_ab.md section 15 addendum 5, item 3c (declared before this ran). Geometry only; report only. Layout (i) workers; "
         f"re-ask shift {R.shift} m, clearance {R.clearance} m, separation {R.sep} m, turning points {R.turn} m, ask zone {R.zone} m, "
         f"bystander margin {R.nearer} m over {R.approach} m, active avatars <= {R.max_active} within {R.act_radius} m; second-opinion radius "
         f"{so_radius} m; answerer {ask_max} m; zone gap {zone_gap} m. In view: rendered within {RENDER_M} m, range {RANGE_M} m, line of sight "
         f"past {', '.join(OCCLUDERS)} ({len(occ.hulls)} footprints); pan-tilt half field of view {half_fov:.2f} deg (vertical 60 deg).",
         f"Plans and footprints: `{export.relative_to(REPO).as_posix() if export.is_relative_to(REPO) else export.name}` ({len(plans)} plans).", ""]

    # ---- layout (i) per beside map, checked against Unity's plans
    beside = {}
    for name in ("corridor", "turn", "turn_left", "roadmap"):
        why, res = ls.plan_beside(maps[name], phys, sslots, jslots, (), R, world)
        if why:
            raise SystemExit(f"layout (i) refused by the port on {name}: {why}")
        beside[name] = res[1]
    mism = 0
    for p in plans:
        if p["experiment"][1] in "123":
            mine = sorted((n, s, round(x, 3), round(z, 3)) for n, s, (x, z) in beside[p["map"]])
            theirs = sorted((w["node"], w["slot"], round(w["x"], 3), round(w["z"], 3)) for w in p["workers"])
            mism += mine != theirs
    L.append(f"Port check: the port's layout (i) equals Unity's planned workers in {sum(1 for p in plans if p['experiment'][1] in '123') - mism} "
             f"of {sum(1 for p in plans if p['experiment'][1] in '123')} beside plans.")
    L.append("")

    # ---- feasibility per branch
    rows, props, result = [], {}, {"branches": {}}
    L += ["## Feasibility per branch (one checkpoint at a time, layout (i) placed)", "",
          "| map | branch | length (m) | candidates | P1-P10 | P1-P10 + Q1-Q2 | + Q3 | binding (P1-P10: valid when this rule alone is dropped) | most broken |",
          "|---|---|---|---|---|---|---|---|---|"]
    for name in ("corridor", "turn", "turn_left", "roadmap"):
        m = maps[name]
        placed = beside[name]
        base_segs, base_asks = node_drives(m, placed, R)
        for start, cmd, end in branches(m):
            Ln = math.dist(m.pos(start), m.pos(end))
            cands = []
            for k in range(1, int(Ln / S_STEP)):
                s = k * S_STEP
                for l in [x for v in LATERAL for x in (v, -v)]:
                    res, anchor, w, asks, segs = candidate_rules(m, phys, start, end, s, l, placed, base_segs, base_asks, [], R, world,
                                                                 so_radius, ask_max, zone_gap)
                    cands.append({"s": s, "l": l, "anchor": anchor, "w": w, "asks": asks, "segs": segs, "res": res})
            okP = [c for c in cands if all(c["res"][k] for k in P_RULES)]
            okPQ = [c for c in okP if c["res"]["Q1 second opinion"] and c["res"]["Q2 answerer 3.5 m"]]
            okPQ3 = [c for c in okPQ if c["res"]["Q3 zones 12.0 m"]]
            drop = {k: sum(1 for c in cands if all(c["res"][j] for j in P_RULES if j != k)) for k in P_RULES}
            broken = Counter(" + ".join(k.split(" ")[0] for k in P_RULES if not c["res"][k]) for c in cands if not all(c["res"][k] for k in P_RULES))
            binding = "" if okP else "; ".join(f"{k} {v}" for k, v in drop.items() if v > 0) or "no single rule"
            key = f"{name} {start}-{cmd}->{end}"
            L.append(f"| {name} | {start} {cmd} -> {end} | {Ln:.2f} | {len(cands)} | {len(okP)} | {len(okPQ)} | {len(okPQ3)} | {binding or '-'} | "
                     f"{'; '.join(f'{k} {v}' for k, v in broken.most_common(3))} |")
            sv = [c["s"] for c in okP]
            result["branches"][key] = {"length_m": Ln, "candidates": len(cands), "valid_P": len(okP), "valid_PQ12": len(okPQ),
                                       "valid_PQ123": len(okPQ3), "drop_one_P": drop, "broken": dict(broken.most_common(10)),
                                       "s_range_valid_P": [min(sv), max(sv)] if sv else None,
                                       "q_fail_among_valid_P": {q: sum(1 for c in okP if not c["res"][q]) for q in Q_RULES}}
            for c in cands:
                rows.append({"map": name, "branch": f"{start} {cmd} -> {end}", "s_m": c["s"], "lateral_m": c["l"],
                             "x": round(c["w"][0], 3), "z": round(c["w"][1], 3),
                             **{k.split(" ")[0]: int(c["res"][k]) for k in P_RULES + Q_RULES}})
            # the proposal (declared choice rule)
            pool, label = okPQ, "P1-P10 + Q1-Q2"
            if not pool:
                pool, label = okP, "FALLBACK P1-P10 only (no candidate meets Q1-Q2)"
            if pool:
                starts = [q for n2, q, _ in base_asks if n2 == start]

                def seen(c):
                    return any(math.dist(q, c["w"]) <= min(RENDER_M, RANGE_M) and not occ.blocked(q, c["w"]) for q in starts)
                best = min(pool, key=lambda c: (seen(c), abs(c["s"] - Ln / 2), abs(c["l"]), c["l"] < 0))
                props[(name, start, end)] = {**best, "rule": label, "seen_from_start_asks": seen(best), "cmd": cmd}
    L.append("")
    L += ["Rules: " + ", ".join(P_RULES) + "; answer rules " + ", ".join(Q_RULES) + ". Candidates: s every 0.5 m strictly inside the branch, "
          "lateral 1.0 to 4.5 m each side (16 per s). 'binding': where no candidate meets P1-P10, the candidates that would when one rule "
          "alone is dropped. 'most broken': the commonest sets of broken P rules.", ""]
    q_lines = []
    for key, b in result["branches"].items():
        if b["valid_P"]:
            q_lines.append(f"- {key}: of {b['valid_P']} candidates meeting P1-P10, Q fails: " +
                           ", ".join(f"{q} {n}" for q, n in b["q_fail_among_valid_P"].items()) +
                           f"; valid s range {b['s_range_valid_P'][0]:.1f} to {b['s_range_valid_P'][1]:.1f} m")
    L += ["Answer rules among the candidates that meet P1-P10:", ""] + q_lines + [""]

    # ---- joint check of the proposals per map
    L += ["## Proposed checkpoint per branch (declared choice rule)", "",
          "| map | branch | s (m) | lateral (m, + right) | worker x, z | rule met | seen from the start node's ask points | joint check with the map's other checkpoints |",
          "|---|---|---|---|---|---|---|---|"]
    prow = []
    for name in ("corridor", "turn", "turn_left", "roadmap"):
        m = maps[name]
        placed = beside[name]
        base_segs, base_asks = node_drives(m, placed, R)
        mine = {k: v for k, v in props.items() if k[0] == name}
        for (nm, start, end), c in mine.items():
            others = [(o["anchor"], o["w"], o["segs"]) for k, o in mine.items() if k != (nm, start, end)]
            res, *_ = candidate_rules(m, phys, start, end, c["s"], c["l"], placed, base_segs, base_asks, others, R, world, so_radius, ask_max, zone_gap)
            bad = [k for k in P_RULES + Q_RULES[:2] if not res[k]]
            c["joint_bad"] = bad
            L.append(f"| {name} | {start} {c['cmd']} -> {end} | {c['s']:.1f} | {c['l']:+.1f} | {c['w'][0]:.2f}, {c['w'][1]:.2f} | {c['rule']} | "
                     f"{'yes' if c['seen_from_start_asks'] else 'no'} | {'passes' if not bad else 'FAILS: ' + ', '.join(bad)} |")
            prow.append({"map": name, "branch": f"{start} {c['cmd']} -> {end}", "s_m": c["s"], "lateral_m": c["l"], "x": round(c["w"][0], 3),
                         "z": round(c["w"][1], 3), "rule": c["rule"], "seen_from_start_asks": c["seen_from_start_asks"],
                         "joint_problems": "; ".join(bad)})
        missing = [f"{s}-{c}->{e}" for s, c, e in branches(m) if (name, s, e) not in mine]
        if missing:
            L.append(f"| {name} | {', '.join(missing)} | - | - | - | **no candidate** | - | - |")
    L.append("")

    # ---- per plan: active avatars and people in view, without and with the checkpoints
    ask_rows, drive_rows = [], []
    act = defaultdict(lambda: {"plans": 0, "max_without": 0, "max_with": 0, "over_with": 0, "rule_fail_plans": Counter()})
    flags = defaultdict(lambda: {"asks": 0, "flag360": 0, "flagpt": 0, "flag360_wo": 0, "flagpt_wo": 0, "drive_max360": 0, "drive_maxpt": 0,
                                 "drive_max360_wo": 0, "drive_maxpt_wo": 0, "drive_3plus360": 0, "drive_3plus_pt": 0})
    for p in plans:
        m = maps[p["map"]]
        placed = [(w["node"], w["slot"], (w["x"], w["z"])) for w in p["workers"]]
        cps = [(k, c) for k, c in props.items() if k[0] == p["map"]]
        cw = [c["w"] for _, c in cps]
        nodes_w = [q for _, _, q in placed]
        st = p["setting"]
        a = act[st]
        a["plans"] += 1
        mw, mwo = ls.max_active(m, nodes_w + cw, R), ls.max_active(m, nodes_w, R)
        a["max_without"], a["max_with"] = max(a["max_without"], mwo), max(a["max_with"], mw)
        a["over_with"] += mw > R.max_active
        if p["experiment"][1] == "4":                       # random workers: the proposed checkpoints under every rule of this plan
            base_segs, base_asks = node_drives(m, placed, R)
            for (nm, start, end), c in cps:
                others = [(o["anchor"], o["w"], o["segs"]) for k, o in cps if k != (nm, start, end)]
                res, *_ = candidate_rules(m, phys, start, end, c["s"], c["l"], placed, base_segs, base_asks, others, R, world, so_radius,
                                          ask_max, zone_gap)
                for k in P_RULES + Q_RULES[:2]:
                    if not res[k]:
                        a["rule_fail_plans"][f"{start}->{end} {k}"] += 1
        people_wo = [(f"w{w['id']}", (w["x"], w["z"])) for w in p["workers"]]
        people = people_wo + [(f"cp {k[1]}->{k[2]}", c["w"]) for k, c in cps]
        _, base_asks = node_drives(m, placed, R)
        ask_pts = [(n, q, who) for n, q, who in base_asks]
        for k, c in cps:
            ask_pts += [(f"cp {k[1]}->{k[2]}", q, c["w"]) for q in c["asks"]]
        f = flags[st]
        for n, q, who in ask_pts:
            pan = bearing(q, who) if who is not None else None
            n360, npt, labs = in_view(q, people, occ, pan, half_fov)
            n360w, nptw, _ = in_view(q, people_wo, occ, pan, half_fov) if not n.startswith("cp") else (None, None, None)
            f["asks"] += 1
            f["flag360"] += n360 >= 3
            f["flagpt"] += npt >= 3
            if n360w is not None:
                f["flag360_wo"] += n360w >= 3
                f["flagpt_wo"] += nptw >= 3
            if n360 >= 3 or npt >= 3 or (n360w or 0) >= 3:
                ask_rows.append({"setting": st, "seed": p["seed"], "run": p["run"], "map": p["map"], "ask_of": n, "x": round(q[0], 2), "z": round(q[1], 2),
                                 "in_360": n360, "in_pan_tilt": npt, "in_360_without_checkpoints": "" if n360w is None else n360w,
                                 "in_pan_tilt_without_checkpoints": "" if nptw is None else nptw, "pan_tilt_people": " ".join(labs)})
        rt = route(m, p["goal"])
        best = (0, 0, None)
        for pos, h in samples_along([m.pos(n) for n in rt], 0.5):
            n360, npt, _ = in_view(pos, people, occ, h, half_fov)
            n360w, nptw, _ = in_view(pos, people_wo, occ, h, half_fov)
            f["drive_max360"], f["drive_maxpt"] = max(f["drive_max360"], n360), max(f["drive_maxpt"], npt)
            f["drive_max360_wo"], f["drive_maxpt_wo"] = max(f["drive_max360_wo"], n360w), max(f["drive_maxpt_wo"], nptw)
            f["drive_3plus360"] += n360 >= 3
            f["drive_3plus_pt"] += npt >= 3
            if (n360, npt) > best[:2]:
                best = (n360, npt, pos)
        drive_rows.append({"setting": st, "seed": p["seed"], "run": p["run"], "map": p["map"], "goal": p["goal"], "route": ">".join(rt),
                           "max_in_360": best[0], "max_in_pan_tilt": best[1], "at_x": round(best[2][0], 2) if best[2] else "",
                           "at_z": round(best[2][1], 2) if best[2] else ""})
    L += ["## Per plan: active avatars and people in view (seeds 1 and 2, 20 runs, 10 settings)", "",
          f"| setting | plans | active max without / with checkpoints (limit {R.max_active}) | plans over the limit with | ask points | asks with 3+ in 360 (with / without) | asks with 3+ in pan-tilt (with / without) | driving: most in 360 (with / without) | driving: most in pan-tilt (with / without) | driving samples with 3+ (360 / pan-tilt, with) |",
          "|---|---|---|---|---|---|---|---|---|---|"]
    for st in sorted(act):
        a, f = act[st], flags[st]
        L.append(f"| {st} | {a['plans']} | {a['max_without']} / {a['max_with']} | {a['over_with']} | {f['asks']} | {f['flag360']} / {f['flag360_wo']} | "
                 f"{f['flagpt']} / {f['flagpt_wo']} | {f['drive_max360']} / {f['drive_max360_wo']} | {f['drive_maxpt']} / {f['drive_maxpt_wo']} | "
                 f"{f['drive_3plus360']} / {f['drive_3plus_pt']} |")
    L.append("")
    L.append("'ask points' counts every modelled ask position and re-ask point of every plan (node workers and, with checkpoints, the checkpoints' "
             "own); 'without' counts only the node workers' ask points with the node workers. Every flagged ask: asks.csv; per plan the most in "
             "view while driving: driving.csv.")
    rf = {st: dict(a["rule_fail_plans"]) for st, a in act.items() if a["rule_fail_plans"]}
    L += ["", "Random layouts (A4, B4): the proposed checkpoints against each plan's drawn workers, plans where a rule fails: " +
          ("; ".join(f"{st}: " + ", ".join(f"{k} {v}" for k, v in sorted(d.items())) for st, d in sorted(rf.items())) or "none"), ""]
    # flagged asks summarised by where they are
    where = Counter((r["setting"].replace("_right", "").replace("_left", "")[:2], r["ask_of"], r["in_360"], r["in_pan_tilt"]) for r in ask_rows)
    L += ["Flagged asks by experiment, asking point and count (360, pan-tilt): " +
          "; ".join(f"{k[0]} {k[1]} ({k[2]}, {k[3]}) x{v}" for k, v in sorted(where.items())), ""]

    def wcsv(fn, rs):
        with open(out / fn, "w", encoding="utf-8", newline="") as fh:
            if rs:
                w = csv.DictWriter(fh, fieldnames=list(rs[0].keys()))
                w.writeheader()
                w.writerows(rs)
    wcsv("branches.csv", rows)
    wcsv("proposals.csv", prow)
    wcsv("asks.csv", ask_rows)
    wcsv("driving.csv", drive_rows)
    result.update({"proposals": prow, "active": {k: {**v, "rule_fail_plans": dict(v["rule_fail_plans"])} for k, v in act.items()},
                   "view": dict(flags), "seconds": round(time.time() - t0, 1)})
    (out / "result.json").write_text(json.dumps(result, indent=1, default=str), encoding="utf-8")
    (out / "report.md").write_text("\n".join(L) + "\n", encoding="utf-8")
    (out / "run_info.json").write_text(json.dumps({"created": stamp, "git_commit": ls.git_head(), "python": sys.version.split()[0],
                                                   "config": C, "export": export.name, "tool": "finals_v4/checkpoint_feasibility_v4.py"},
                                                  indent=1), encoding="utf-8")
    print("\n".join(L))
    print(f"\nwritten: {out.relative_to(REPO).as_posix()} ({result['seconds']} s)")


if __name__ == "__main__":
    main(sys.argv)
