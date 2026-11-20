"""Checkpoint workers (variant T4): positions, people in view per ask, active avatars, redraws (report only).

Avatar/Config/experiments_ab.md section 15 addendum 6, item 5 (declared there before this ran). Evaluation only, read-only: it reads the
export that the temporary Editor script of that item wrote from Unity's own planner (checkpoint_check_<time>/plans.json, footprints.json:
every planned run of seeds 1 and 2 of the 10 Unity settings, with its node workers, its checkpoint workers and Unity's modelled ask points)
and the map and config files. Nothing is built or changed.

The view model is addendum 5's (finals_v4/checkpoint_feasibility_v4.py, imported unchanged): a person is in view when rendered (within
activation_radius_m), within the detection range and not hidden by a Shelves or Walls footprint; the pan-tilt camera also within half its
horizontal field of view of the pan direction (toward the asked worker at an ask point, the heading while driving).
It also re-checks every checkpoint of every plan with addendum 5's port of the rules (P1-P7, P9, P10, Q1, Q2; P8 there is a 5.5 m ask
zone around the anchor, not the T4 answer rule, so it is reported, not required), as an independent check of Unity's planner.

Usage, from the repository root with the project venv:
  Windows: robot_vision\\.venv\\Scripts\\python.exe finals_v4\\checkpoint_layout_report_v4.py robot_vision\\outputs\\checkpoint_check_<time>
  macOS:   robot_vision/.venv/bin/python finals_v4/checkpoint_layout_report_v4.py robot_vision/outputs/checkpoint_check_<time>
Writes a new folder <outputs>/checkpoint_layout_report_v4_<time>/ (report.md, positions.csv, asks.csv, driving.csv, result.json,
run_info.json).
"""
from __future__ import annotations

import csv
import json
import math
import statistics
import sys
import time
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import checkpoint_feasibility_v4 as cf  # noqa: E402  (view model and the rule port, unchanged)
import layout_search_v4 as ls  # noqa: E402

REPO = ls.REPO
RULES_REQUIRED = ["P1 separation", "P2 turning points", "P3 free cell", "P4 road clearance", "P5 node drives", "P6 own drive",
                  "P7 NavMesh", "P9 bystander margin", "P10 active avatars", "Q1 second opinion", "Q2 answerer 3.5 m"]


def dist_summary(values):
    if not values:
        return "-"
    c = Counter(min(v, 3) for v in values)
    return f"0: {c[0]}, 1: {c[1]}, 2: {c[2]}, 3+: {c[3]} (max {max(values)})"


def main(argv):
    if len(argv) < 2:
        raise SystemExit(__doc__)
    t0 = time.time()
    export = Path(argv[1])
    export = export if export.is_absolute() else (Path.cwd() / export)
    C = json.loads(ls.CONFIG.read_text(encoding="utf-8"))
    sc, U, ctl = ls.load(C["scenarios_ab"]), ls.load(C["experiments_unity"]), ls.load(C["control_v4"])
    perc = ls.load("robot_vision/configs/hri_perception.json")
    unity_robot = ls.load("unity/Robotics-Warehouse/WarehouseProjectURP/Assets/WarehouseRobot/Robot/Config/robot_unity_v4.json")
    cf.RENDER_M, cf.RANGE_M = float(U["activation_radius_m"]), float(perc["evaluation"]["detection_range_m"])
    half_fov = cf.hfov_deg(float(unity_robot["pan_tilt_camera"]["vertical_fov_deg"])) / 2.0
    so_radius = float(ctl["lie_detection"]["second_opinion_radius_m"])
    ask_max = float(U["ask_max_distance_m"])
    zone_gap = 2.0 * float(U["answer_zone_radius_m"])
    maps = {k: ls.Map(k, v) for k, v in sc["maps"].items()}
    maps["roadmap"] = phys = ls.Map("roadmap", ls.load(C["roadmap_v4"]))
    for p in U.get("proposals", []):
        if p["name"] not in maps:
            maps[p["name"]] = ls.Map(p["name"], json.loads((REPO / "unity/Robotics-Warehouse/WarehouseProjectURP" / p["file"]).read_text(encoding="utf-8")))
    world = ls.World(ls.load(C["grid"]), REPO / C["navmesh_cells"])
    pr = sc["placement_rule"]
    base = dict(sep=pr["min_worker_separation_m"], turn=pr["min_turning_point_m"], min_road=0.0, approach=U["approach_m"],
                clearance=U["path_clearance_m"], zone=U["answer_zone_radius_m"] - U["answer_zone_margin_m"], standoff=U["ask_standoff_m"],
                shift=float(ctl["dialog"]["reask_shift_m"]), navmesh=True, max_active=U["max_active_avatars"],
                act_radius=U["activation_radius_m"], act_step=U["activation_sample_step_m"])
    R_beside = ls.Rules(nearer=U["nearer_margin_m"], **base)
    R_random = ls.Rules(nearer=U["random_nearer_margin_m"], **base)
    data = json.loads((export / "plans.json").read_text(encoding="utf-8"))
    plans = data["plans"]
    occ = cf.Occlusion(json.loads((export / "footprints.json").read_text(encoding="utf-8"))["footprints"])
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out = REPO / C["outputs"] / f"checkpoint_layout_report_v4_{stamp}"
    out.mkdir(parents=True, exist_ok=False)
    rel = export.relative_to(REPO).as_posix() if export.is_relative_to(REPO) else export.name
    L = [f"# Checkpoint workers (T4): positions, people in view, active avatars ({stamp})", "",
         "experiments_ab.md section 15 addendum 6, item 5 (declared before this ran). Geometry only, report only. Export of Unity's planner: "
         f"`{rel}` ({len(plans)} plans). In view: rendered within {cf.RENDER_M} m, range {cf.RANGE_M} m, line of sight past "
         f"{', '.join(cf.OCCLUDERS)} ({len(occ.hulls)} footprints); pan-tilt half field of view {half_fov:.2f} deg (vertical 60 deg), toward the "
         "asked worker at an ask point, along the heading while driving.", ""]

    # ---- positions (identical in every plan of a map: checked)
    pos_by_map: dict[str, dict] = {}
    pos_problems = []
    for p in plans:
        cps = {w["node"]: (round(w["x"], 4), round(w["z"], 4)) for w in p["workers"] if w["kind"] == "checkpoint"}
        if p["map"] in pos_by_map and pos_by_map[p["map"]] != cps:
            pos_problems.append(f"{p['setting']} seed {p['seed']} run {p['run']}")
        pos_by_map.setdefault(p["map"], cps)
    rows_pos = []
    L += ["## Checkpoint positions (Unity's planner)", "",
          "| map | branch | s (m) | right (m) | worker x, z | anchor x, z | distance to its junction / next node (m) | nearest node |", "|---|---|---|---|---|---|---|---|"]
    for c in data.get("checkpoints", []):
        m = maps[c["map"]]
        w = (c["x"], c["z"])
        dj, dn = math.dist(w, m.pos(c["from"])), math.dist(w, m.pos(c["to"]))
        nearest = min(m.nodes, key=lambda n: math.dist(w, m.pos(n)))
        L.append(f"| {c['map']} | {c['from']} {c['command']} -> {c['to']} | {c['s_m']:.1f} | {c['right_m']:+.1f} | {c['x']:.2f}, {c['z']:.2f} | "
                 f"{c['anchor_x']:.2f}, {c['anchor_z']:.2f} | {dj:.2f} / {dn:.2f} | {nearest} ({math.dist(w, m.pos(nearest)):.2f}) |")
        rows_pos.append({**c, "dist_junction_m": round(dj, 3), "dist_next_m": round(dn, 3), "nearest_node": nearest})
    L += ["", "Positions equal in every plan of their map: " + ("yes" if not pos_problems else "NO: " + "; ".join(pos_problems[:10])), ""]

    # ---- per plan: independent rule check, active avatars, redraws, view
    by_setting = defaultdict(lambda: {"plans": 0, "max_active": 0, "rule_fail": Counter(), "p8_zone_fail": 0, "redraws": [], "redraws_by_node": defaultdict(list),
                                      "asks": defaultdict(lambda: {"n": 0, "v360": [], "vpt": []}), "drive360": 0, "drivept": 0, "drive_where": None})
    ask_rows, drive_rows = [], []
    for p in plans:
        st = p["setting"]
        s = by_setting[st]
        s["plans"] += 1
        s["max_active"] = max(s["max_active"], p["max_active"])
        tot = sum(p.get("redraws", {}).values())
        s["redraws"].append(tot)
        for n, v in p.get("redraws", {}).items():
            s["redraws_by_node"][n].append(v)
        m = maps[p["map"]]
        R = R_random if p["experiment"][1] == "4" else R_beside
        node_w = [w for w in p["workers"] if w["kind"] == "node"]
        cp_w = [w for w in p["workers"] if w["kind"] == "checkpoint"]
        placed = [(w["node"], w["slot"], (w["x"], w["z"])) for w in node_w]
        if cp_w:
            base_segs, base_asks = cf.node_drives(m, placed, R)
            geo = {}
            for w in cp_w:
                frm, to = w["from"], w["to"]
                asks, segs = cf.checkpoint_geometry(m, frm, to, (w["x"], w["z"]), R)
                a, e = m.pos(frm), m.pos(to)
                L_ = math.dist(a, e)
                f = ((e[0] - a[0]) / L_, (e[1] - a[1]) / L_)
                geo[w["id"]] = ((a[0] + f[0] * w["s_m"], a[1] + f[1] * w["s_m"]), (w["x"], w["z"]), segs)
            for w in cp_w:
                others = [g for k, g in geo.items() if k != w["id"]]
                res, *_ = cf.candidate_rules(m, phys, w["from"], w["to"], w["s_m"], w["right_m"], placed, base_segs, base_asks, others, R, world,
                                             so_radius, ask_max, zone_gap)
                for k in RULES_REQUIRED:
                    if not res[k]:
                        s["rule_fail"][f"{w['node']}: {k}"] += 1
                if not res["P8 ask zone"]:
                    s["p8_zone_fail"] += 1
        people = [(f"{'cp' if w['kind'] == 'checkpoint' else 'w'}{w['id']}", (w["x"], w["z"])) for w in p["workers"]]
        wpos = {w["id"]: (w["x"], w["z"]) for w in p["workers"]}
        for a in p["asks"]:
            q, who = (a["x"], a["z"]), wpos[a["worker"]]
            n360, npt, labs = cf.in_view(q, people, occ, cf.bearing(q, who), half_fov)
            k = s["asks"][a["kind"]]
            k["n"] += 1
            k["v360"].append(n360)
            k["vpt"].append(npt)
            ask_rows.append({"setting": st, "seed": p["seed"], "run": p["run"], "map": p["map"], "ask_of": a["of"], "kind": a["kind"],
                             "worker": a["worker"], "x": round(q[0], 3), "z": round(q[1], 3), "in_360": n360, "in_pan_tilt": npt,
                             "pan_tilt_people": " ".join(labs)})
        rt = cf.route(m, p["goal"])
        best = (0, 0, None)
        for q, h in cf.samples_along([m.pos(n) for n in rt], 0.5):
            n360, npt, _ = cf.in_view(q, people, occ, h, half_fov)
            if (n360, npt) > best[:2]:
                best = (n360, npt, q)
        if (best[0], best[1]) > (s["drive360"], s["drivept"]):
            s["drive_where"] = f"seed {p['seed']} run {p['run']} at ({best[2][0]:.1f}, {best[2][1]:.1f})"
        s["drive360"], s["drivept"] = max(s["drive360"], best[0]), max(s["drivept"], best[1])
        drive_rows.append({"setting": st, "seed": p["seed"], "run": p["run"], "map": p["map"], "goal": p["goal"], "route": ">".join(rt),
                           "max_in_360": best[0], "max_in_pan_tilt": best[1], "at_x": round(best[2][0], 2) if best[2] else "",
                           "at_z": round(best[2][1], 2) if best[2] else ""})

    L += ["## Per setting (seeds 1 and 2, 20 runs each)", "",
          f"| setting | plans | active max (limit {U['max_active_avatars']}) | redraws per run (min / median / max) | checkpoint rule failures (independent port) | "
          "ask kind | asks | people in 360 at the ask | people in pan-tilt at the ask | driving: most in 360 / pan-tilt |", "|---|---|---|---|---|---|---|---|---|---|"]
    result = {"settings": {}}
    for st in sorted(by_setting):
        s = by_setting[st]
        rd = s["redraws"]
        rf = "; ".join(f"{k} {v}" for k, v in sorted(s["rule_fail"].items())) or "none"
        head = [st, str(s["plans"]), str(s["max_active"]), f"{min(rd)} / {statistics.median(rd):g} / {max(rd)}", rf]
        drive = f"{s['drive360']} / {s['drivept']}"
        for kind in ("node", "checkpoint"):
            k = s["asks"].get(kind)
            if k is None:
                continue
            L.append(f"| {' | '.join(head)} | {kind} | {k['n']} | {dist_summary(k['v360'])} | {dist_summary(k['vpt'])} | {drive} |")
            head, drive = [""] * 5, ""
        result["settings"][st] = {"plans": s["plans"], "max_active": s["max_active"], "redraws_total_per_run": rd,
                                  "redraws_by_node": {n: v for n, v in s["redraws_by_node"].items()}, "rule_fail": dict(s["rule_fail"]),
                                  "p8_zone_fail": s["p8_zone_fail"],
                                  "asks": {kind: {"n": k["n"], "in_360": Counter(min(v, 3) for v in k["v360"]), "in_pan_tilt": Counter(min(v, 3) for v in k["vpt"]),
                                                  "max_360": max(k["v360"]), "max_pan_tilt": max(k["vpt"])} for kind, k in s["asks"].items()},
                                  "driving_max_360": s["drive360"], "driving_max_pan_tilt": s["drivept"], "driving_where": s["drive_where"]}
    L += ["", "People counts per ask: '0: n, 1: n, 2: n, 3+: n' = how many asks had that many people in view (the asked worker included). "
          "Every ask: asks.csv; per plan the most in view while driving: driving.csv.",
          "Independent port: addendum 5's rule functions with each plan's own workers (beside: bystander margin "
          f"{R_beside.nearer} m; random: {R_random.nearer} m, as Unity). Its P8 (every ask point within {R_beside.zone} m of the anchor) is not a "
          "T4 rule; checkpoints where it fails: " + (", ".join(f"{st} {s['p8_zone_fail']}" for st, s in sorted(by_setting.items()) if s["p8_zone_fail"]) or "none"), ""]
    # redraws by node (random layouts)
    rnd = [(st, s) for st, s in sorted(by_setting.items()) if st[1] == "4"]
    if rnd:
        L += ["## Redraws of the random layouts (per node, over the 40 runs)", "", "| setting | node | min | median | max | total |", "|---|---|---|---|---|---|"]
        for st, s in rnd:
            for n, v in sorted(s["redraws_by_node"].items()):
                L.append(f"| {st} | {n} | {min(v)} | {statistics.median(v):g} | {max(v)} | {sum(v)} |")
        L.append("")
    flagged = [r for r in ask_rows if r["in_360"] >= 3 or r["in_pan_tilt"] >= 3]
    where = Counter((r["setting"], r["ask_of"], r["in_360"], r["in_pan_tilt"]) for r in flagged)
    L += [f"Asks with 3 or more people in a view: {len(flagged)} of {len(ask_rows)} (360 {sum(r['in_360'] >= 3 for r in ask_rows)}, pan-tilt "
          f"{sum(r['in_pan_tilt'] >= 3 for r in ask_rows)}). By setting, asking point and (360, pan-tilt): " +
          ("; ".join(f"{k[0]} {k[1]} ({k[2]}, {k[3]}) x{v}" for k, v in sorted(where.items())) or "none"), ""]

    def wcsv(fn, rs):
        with open(out / fn, "w", encoding="utf-8", newline="") as fh:
            if rs:
                w = csv.DictWriter(fh, fieldnames=list(rs[0].keys()))
                w.writeheader()
                w.writerows(rs)
    wcsv("positions.csv", rows_pos)
    wcsv("asks.csv", ask_rows)
    wcsv("driving.csv", drive_rows)
    result.update({"positions": rows_pos, "positions_equal": not pos_problems, "asks_flagged": len(flagged), "asks": len(ask_rows),
                   "seconds": round(time.time() - t0, 1)})
    (out / "result.json").write_text(json.dumps(result, indent=1, default=str), encoding="utf-8")
    (out / "report.md").write_text("\n".join(L) + "\n", encoding="utf-8")
    (out / "run_info.json").write_text(json.dumps({"created": stamp, "git_commit": ls.git_head(), "python": sys.version.split()[0],
                                                   "config": C, "export": export.name, "tool": "finals_v4/checkpoint_layout_report_v4.py"},
                                                  indent=1), encoding="utf-8")
    print("\n".join(L))
    print(f"\nwritten: {out.relative_to(REPO).as_posix()} ({result['seconds']} s)")


if __name__ == "__main__":
    main(sys.argv)
