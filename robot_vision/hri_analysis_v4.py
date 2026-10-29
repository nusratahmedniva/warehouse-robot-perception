"""v4 analysis: the numbers of the study, per setting, with intervals, and the comparison with the archived v3 results (research
question 1). REPORTING / EVALUATION CODE ONLY (reads truth through hri_eval_dev_v4 and gt_path).

Input: sessions, each labelled with its setting (repeatable --session SETTING UNITY BRIDGE): Unity's trial folder (session.json,
truth_run###.json, run_###/truth.jsonl, grid / optimal path / trail) and the bridge guide run folder (v4_log.jsonl,
python_trial_###.json, decisions.csv, perception.csv, config_used/control.json). Sessions with the same label are one setting.

Development data only by default (data_splits_v4.guard_run refuses test data). --final analyses TEST data of the final settings and
is allowed only when configs/v4/frozen.json is frozen with every hash matching and each setting is what final_guard_v4.check_setting
says; the analysis only describes (no run-once), and writes into a new folder.

Per setting, always with its coverage and the number of runs behind it:
- success rate with a Wilson 95 % interval (over runs); failure reasons;
- gesture accuracy and coverage per command, with Wilson intervals (frame level, labelled) and cluster-bootstrap intervals over
  runs (frames within a run are not independent); false reads; the confusion matrix;
- POINT angle error: median and 95th percentile with bootstrap intervals, of the better depth reading and of the resolved reading;
- the correct-branch rate (Wilson), second looks, re-approaches; commander accuracy with and without bystanders;
- time from the first "Which direction?" to the accepted gesture (median, 95th percentile, bootstrap);
- trail length / optimal path, largest distance from the optimal line, share within one cell, final distance from B (gt_path);
- collisions, closest approach, final distance; inference time per model and Unity-Python round trip (machine-dependent);
- per look, per look style, per distance, zoom on vs zoom off.
One table compares v4 with the archived v3 results (results/summary/), with every declared difference listed under it.

Output: <output_root>/hri_analysis_v4_<time>/ (hri_analysis_v4_final_<time> with --final): analysis.json, analysis.md,
rq1_comparison.csv, config_used/, run.json (git commit).

Usage (from robot_vision/):
  python hri_analysis_v4.py --session zoom_on outputs/trials_X outputs/bridge_guide_Y [--session ...] [--final]
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import random
import re
import shutil
import statistics as st
from collections import Counter, defaultdict
from pathlib import Path

import data_splits_v4 as ds
import final_guard_v4 as fg
import freeze_v4 as fz
import gesture_data as gd
import gt_path
import hri_analysis as ha
import hri_control as hc
import hri_eval_dev_v4 as ev
import hri_trials as ht

HERE = Path(__file__).resolve().parent
DEFAULT_CONFIG = "configs/v4/analysis.json"
NE = ev.NOT_EVALUATED


def load_config(path: str | Path = DEFAULT_CONFIG) -> dict:
    p = Path(path)
    return json.loads((p if p.is_absolute() else HERE / p).read_text(encoding="utf-8"))


# ---------------------------------------------------------------- intervals

def wilson(k: int, n: int, cfg: dict) -> dict:
    """k of n with its Wilson interval (over the units counted: runs, junctions or frames, as labelled by the caller)."""
    if n == 0:
        return {"k": k, "n": n, "ratio": NE, "wilson95": NE}
    lo, hi = ha.wilson(k, n, cfg["wilson_z"])
    return {"k": k, "n": n, "ratio": round(k / n, 4), "wilson95": [lo, hi]}


def _quantile(sorted_vals: list, q: float):
    """Linear interpolation, q in 0..1 (hri_trials.pct)."""
    return ht.pct(sorted_vals, q)


def bootstrap(items: list, stat, cfg: dict) -> dict:
    """Cluster bootstrap over RUNS: resample the per-run items with replacement; stat(list of items) -> float or None."""
    if not items:
        return {"status": NE, "n_runs": 0}
    est = stat(items)
    b = cfg["bootstrap"]
    rng = random.Random(b["seed"])
    vals = []
    for _ in range(b["n_resamples"]):
        v = stat([items[rng.randrange(len(items))] for _ in items])
        if v is not None:
            vals.append(v)
    vals.sort()
    lo, hi = (_quantile(vals, b["percentiles"][0] / 100), _quantile(vals, b["percentiles"][1] / 100)) if vals else (None, None)
    r = lambda x: None if x is None else round(x, 4)
    return {"estimate": r(est), "lo": r(lo), "hi": r(hi), "n_runs": len(items), "resamples": len(vals),
            "unit": "run (cluster bootstrap)"}


def _pool(items: list) -> list:
    return [x for run in items for x in run]


def _ratio_stat(num: int, den: int):
    def f(items):
        d = sum(i[den] for i in items)
        return sum(i[num] for i in items) / d if d else None
    return f


def _median_stat(items):
    v = _pool(items)
    return st.median(v) if v else None


def _pct_stat(p):
    return lambda items: (_quantile(sorted(_pool(items)), p / 100) if _pool(items) else None)


def spread(values: list, cfg: dict, per_run: list | None = None) -> dict:
    """n, median, 95th percentile (config), mean, max; bootstrap intervals over runs when the per-run lists are given."""
    if not values:
        return {"n": 0, "status": NE}
    p = cfg["angle_percentile"]
    out = {"n": len(values), "median": round(st.median(values), 3), f"p{p}": round(_quantile(sorted(values), p / 100), 3),
           "mean": round(st.fmean(values), 3), "max": round(max(values), 3)}
    if per_run is not None:
        runs = [r for r in per_run if r]
        out["median_ci"] = bootstrap(runs, _median_stat, cfg)
        out[f"p{p}_ci"] = bootstrap(runs, _pct_stat(p), cfg)
    return out


# ---------------------------------------------------------------- per-run data

def run_data(runs: list, ecfg: dict, gcfg: dict) -> list[dict]:
    out = []
    for run in runs:
        entries, rows = ev.frame_table(run, ecfg, gcfg)
        f = run.unity_dir / f"truth_run{run.trial:03d}.json"
        outcome = json.loads(f.read_text(encoding="utf-8")) if f.exists() else None
        out.append({"run": run, "entries": entries, "rows": rows, "outcome": outcome})
    return out


# ---------------------------------------------------------------- blocks

def success_block(rd: list, cfg: dict) -> dict:
    have = [r for r in rd if r["outcome"]]
    k = sum(r["outcome"]["outcome"] == "SUCCESS" for r in have)
    return {**wilson(k, len(have), cfg), "unit": "runs", "runs": len(rd), "runs_with_an_outcome": len(have),
            "failure_reasons": dict(Counter(r["outcome"].get("failure_reason", "?") for r in have if r["outcome"]["outcome"] != "SUCCESS"))}


def gesture_block(rd: list, cfg: dict) -> dict:
    all_entries = [e for r in rd for e in r["entries"]]
    base = ev.accuracy_block(all_entries)
    per = {}
    for s in ev.GESTURES:
        items = []                                   # per run: (frames, answered, correct)
        for r in rd:
            es = [e for e in r["entries"] if e["truth"] == s]
            items.append((len(es), sum(e["read"] in ev.GESTURES for e in es), sum(e["read"] == s for e in es)))
        n, ans, cor = (sum(i[x] for i in items) for x in range(3))
        per[s] = {"frames": n, "answered": ans, "correct": cor,
                  "coverage": {**wilson(ans, n, cfg), "unit": "frames (not independent: see the run-level interval)",
                               "bootstrap": bootstrap([i for i in items if i[0]], _ratio_stat(1, 0), cfg)},
                  "accuracy_of_answered": {**wilson(cor, ans, cfg), "unit": "frames (not independent: see the run-level interval)",
                                           "bootstrap": bootstrap([i for i in items if i[1]], _ratio_stat(2, 1), cfg)}}
    return {"confusion": base["confusion"], "false_reads": base["false_reads"], "frames_matched": base["frames_matched"],
            "frames_unmatched": base["frames_unmatched"], "per_command": per}


def angle_block(rd: list, cfg: dict) -> dict:
    errs = [ev.angle_errors(r["entries"], r["rows"]) for r in rd]
    held, read = sum(e["held"] for e in errs), sum(e["read"] for e in errs)
    frames, amb = sum(e["resolution_frames"] for e in errs), sum(e["ambiguous"] for e in errs)
    return {"held_point_frames": held, "read_as_point": read, "coverage": wilson(read, held, cfg),
            "better_depth_reading_deg": spread(_pool([e["better"] for e in errs]), cfg, [e["better"] for e in errs]),
            "resolved_reading_deg": spread(_pool([e["resolved"] for e in errs]), cfg, [e["resolved"] for e in errs]),
            "resolved_frames": sum(len(e["resolved"]) for e in errs), "frames_with_a_resolution": frames,
            "ambiguous_share": wilson(amb, frames, cfg),
            "note": "Error against the true pointed angle on frames where the truth is a POINT being held; 'better' picks the closer of "
                    "the two depth readings (what an oracle could do), 'resolved' is what the roadmap resolution produced."}


def branch_block(rd: list, road: hc.Roadmap, cfg: dict) -> dict:
    runs = [r["run"] for r in rd]
    b = ev.branch_block(runs, {r["run"].name: r["rows"] for r in rd}, road)
    scored = [d for d in b["detail"] if d.get("correct") in (True, False)]
    first = [d for d in scored if d.get("asks") == 1]
    return {"junction_asks": b["junction_asks"], "accepted": wilson(b["accepted"], b["junction_asks"], cfg),
            "correct_of_scored": wilson(b["correct"], b["scored"], cfg),
            "correct_at_the_first_ask_of_all_asks": wilson(sum(d["correct"] for d in first), b["junction_asks"], cfg),
            "not_evaluated": b["not_evaluated"], "second_view": b["second_view"], "reapproached": b["reapproached"]}


def commander_block(rd: list, cfg: dict) -> dict:
    out = {}
    for label, flag in (("with_bystanders", True), ("without_bystanders", False)):
        items = []                                   # per run: (frames, decided, correct)
        for r in rd:
            rs = [x for x in r["rows"] if x["bystanders"] == flag and x["truth_commander"] is not None]
            cor = sum(x["chosen_person"] is not None and x["chosen_worker"] == x["truth_commander"] for x in rs)
            wrong = sum(x["chosen_person"] is not None and x["chosen_worker"] != x["truth_commander"] for x in rs)
            items.append((len(rs), cor + wrong, cor))
        n, dec, cor = (sum(i[x] for i in items) for x in range(3))
        out[label] = {"frames": n, "decided": dec, "correct": cor, "coverage": wilson(dec, n, cfg),
                      "accuracy_of_decided": {**wilson(cor, dec, cfg), "bootstrap": bootstrap([i for i in items if i[1]], _ratio_stat(2, 1), cfg)}}
    return out


def timing_block(rd: list, cfg: dict) -> dict:
    per_run, net, asks = [], [], 0
    for r in rd:
        recs = r["run"].junctions
        asks += len(recs)
        done = [j for j in recs if j.get("result") == "accepted" and "t_ask_first" in j and "t_accept" in j]
        per_run.append([j["t_accept"] - j["t_ask_first"] for j in done])
        net.append([j["t_accept"] - j["t_ask_first"] - j.get("waited_s", 0.0) for j in done])
    return {"junction_asks": asks, "accepted": len(_pool(per_run)), "coverage": wilson(len(_pool(per_run)), asks, cfg),
            "ask_to_accepted_s": spread(_pool(per_run), cfg, per_run),
            "ask_to_accepted_without_wait_s": spread(_pool(net), cfg, net)}


def path_block(rd: list, gt_cfg: dict) -> dict:
    ratio, far, share, final, match, n = [], [], [], [], 0, 0
    cor_cells, cor_share, several, in_cor = [], [], 0, 0
    for r in rd:
        d = r["run"].unity_dir / f"run_{r['run'].trial:03d}"
        if not gt_path.has_v4_files(d):
            continue
        res = gt_path.evaluate_run(d, gt_cfg)
        n += 1
        match += bool(res["optimal_path_check"]["match"])
        c = res["corridor"]
        if "cells" in c:
            cor_cells.append(c["cells"])
            cor_share.append(c["corridor_share_on_unity_path"])
            several += bool(c["several_shortest_paths"])
            in_cor += c["unity_path_cells_in_corridor"] == c["unity_path_cells"]
        m = res["measures"]
        for lst, key in ((ratio, "trail_over_optimal"), (far, "max_distance_from_optimal_m"),
                         (share, "share_within_near_distance"), (final, "final_distance_from_b_m")):
            if m[key] is not None:
                lst.append(m[key])
    if not n:
        return {"status": NE, "coverage": f"0 of {len(rd)} runs have the v4 path files"}
    return {"coverage": f"{n} of {len(rd)} runs have the v4 path files", "optimal_path_matches_astar": f"{match} of {n}",
            "reference": "optimal corridor: every cell on some shortest path (gt_path.optimal_corridor)",
            "corridor_cells": ha.stats(cor_cells), "runs_with_several_shortest_paths": f"{several} of {n}",
            "unity_path_inside_the_corridor": f"{in_cor} of {n}", "corridor_share_covered_by_unity_path": ha.stats(cor_share),
            "trail_over_optimal": ha.stats(ratio), "max_distance_from_optimal_m": ha.stats(far),
            "share_within_one_cell": ha.stats(share), "final_distance_from_b_m": ha.stats(final)}


def safety_block(rd: list) -> dict:
    have = [r["outcome"] for r in rd if r["outcome"]]
    clos = [o["closest_human_m"] for o in have if o.get("closest_human_m", -1) is not None and o.get("closest_human_m", -1) >= 0]
    succ = [o["final_distance_to_b_m"] for o in have if o["outcome"] == "SUCCESS" and "final_distance_to_b_m" in o]
    return {"runs": len(rd), "runs_with_an_outcome": len(have), "collisions": sum(o.get("collisions", 0) for o in have),
            "collisions_with_a_person": sum(o.get("human_collisions", 0) for o in have),
            "runs_with_a_collision": sum(o.get("collisions", 0) > 0 for o in have),
            "closest_person_m": ha.stats(clos), "final_distance_to_b_m_successes": ha.stats(succ)}


_CSV_CACHE: dict = {}


def _csv(p: Path) -> list:
    if p not in _CSV_CACHE:
        _CSV_CACHE[p] = ht.read_csv(p)
    return _CSV_CACHE[p]


def system_block(rd: list) -> dict:
    """Inference time per model and the Unity-measured round trip. Machine-dependent: not comparable across machines."""
    per_rows, rtt = [], []
    for r in rd:
        run, o = r["run"], r["outcome"]
        rows = _csv(run.bridge_dir / "perception.csv")
        if o and "t_start" in o and "t_end" in o:
            rows = [x for x in rows if o["t_start"] <= (ht.num(x.get("time_s"), -1) or -1) <= o["t_end"]]
        per_rows += rows
        rtt += [ht.num(x["rtt_ms"]) for x in _csv(run.bridge_dir / "decisions.csv")
                if x.get("trial") == str(run.trial) and ht.num(x.get("rtt_ms"), -1) is not None and ht.num(x.get("rtt_ms"), -1) >= 0]
    out = {"inference_ms": ht.model_times(per_rows) if per_rows else NE}
    rtt = [x for x in rtt if x is not None]
    out["round_trip_ms"] = ({"n": len(rtt), "mean": ht.r3(st.fmean(rtt)), "p95": ht.r3(ht.pct(rtt, 0.95)), "max": ht.r3(max(rtt))}
                            if rtt else NE)
    out["note"] = "Machine-dependent (not comparable across machines); the round trip is Unity-measured, sampled in decisions.csv."
    return out


def time_block(rd: list) -> dict:
    """Times that the v3 tables also give (hri_trials definitions), where the logs have them."""
    tot, excl, motion = [], [], []
    for r in rd:
        o, run = r["outcome"], r["run"]
        if o and "total_s" in o:
            tot.append(o["total_s"])
        dec = [x for x in _csv(run.bridge_dir / "decisions.csv") if x.get("trial") == str(run.trial)]
        stale = ht.stale_stop_s(dec)
        if stale is not None and o and "total_s" in o:
            excl.append(o["total_s"] - stale)
        tr = run.unity_dir / f"truth_run{run.trial:03d}.csv"
        if tr.exists():
            m = ht.in_motion_s(ht.read_csv(tr), 0.05)
            if m is not None:
                motion.append(m)
    ratio = [r["outcome"]["travelled_m"] / r["outcome"]["straight_line_m"] for r in rd
             if r["outcome"] and r["outcome"].get("straight_line_m") and "travelled_m" in r["outcome"]]
    return {"total_s": ha.stats(tot), "time_excl_stale_stops_s": ha.stats(excl), "in_motion_s": ha.stats(motion),
            "travelled_over_straight_line": ha.stats(ratio)}


def setting_block(rd: list, ecfg: dict, gcfg: dict, gt_cfg: dict, road: hc.Roadmap, cfg: dict, splits: dict, nested: bool = True) -> dict:
    entries = [e for r in rd for e in r["entries"]]
    styles = splits.get("styles", {})
    blk = {"runs": len(rd), "sessions": sorted({r["run"].session for r in rd}), "success": success_block(rd, cfg),
           "gesture": gesture_block(rd, cfg), "angle": angle_block(rd, cfg), "branch": branch_block(rd, road, cfg),
           "commander": commander_block(rd, cfg), "timing": timing_block(rd, cfg), "path": path_block(rd, gt_cfg),
           "safety": safety_block(rd), "times": time_block(rd), "system": system_block(rd),
           "per_look": _with_wilson(ev.group(entries, lambda e: e["look"]), cfg),
           "per_style": _with_wilson(ev.group(entries, lambda e: styles.get(e["look"], "unknown style") if e["look"] else None), cfg),
           "per_distance": _with_wilson(ev.group(entries, lambda e: ev.distance_bin(e, ecfg["distance_bins_m"]),
                                                 [f"{lo:g}-{hi:g} m" for lo, hi in zip(ecfg["distance_bins_m"], ecfg["distance_bins_m"][1:])]
                                                 + [f">= {ecfg['distance_bins_m'][-1]:g} m"]), cfg)}
    if nested:
        blk["per_zoom"] = {label: (setting_block([r for r in rd if r["run"].zoom_on == flag], ecfg, gcfg, gt_cfg, road, cfg, splits, False)
                                   if any(r["run"].zoom_on == flag for r in rd) else NE)
                           for label, flag in (("zoom_on", True), ("zoom_off", False))}
    return blk


def _with_wilson(table: dict, cfg: dict) -> dict:
    return {k: {**v, "accuracy_interval": wilson(v["correct"], v["answered"], cfg), "coverage_interval": wilson(v["answered"], v["frames"], cfg)}
            for k, v in table.items()}


# ---------------------------------------------------------------- v3 archive and the RQ1 table

JUNCTION = re.compile(r"(\w+):(\w+)>(\w+)(?:\(asks (\d+)\))?")


def _num(x):
    return ht.num(x)


def v3_column(path: Path, cfg: dict, original: bool = False) -> dict:
    rows = ht.read_csv(path)
    if not rows:
        return {"status": NE, "source": str(path.name)}
    k = sum(r["outcome"] == "SUCCESS" for r in rows)
    reads = [m for r in rows for m in JUNCTION.findall(r.get("junctions_shown_vs_read", "") or "")]
    same = sum(shown == read for _, shown, read, _ in reads)
    asks = [a for *_, a in reads if a]
    first = sum(shown == read and a == "1" for _, shown, read, a in reads) if len(asks) == len(reads) else None
    col = ({"collisions": cfg["v3_task2_original_collisions"], "human": cfg["v3_task2_original_collisions"]} if original else
           {"collisions": int(sum(_num(r.get("collisions")) or 0 for r in rows)), "human": int(sum(_num(r.get("human_collisions")) or 0 for r in rows))})
    clos = [_num(r["closest_human_m"]) for r in rows if _num(r.get("closest_human_m")) is not None and _num(r["closest_human_m"]) >= 0]
    fin = [_num(r["final_distance_to_b_m"]) for r in rows if r["outcome"] == "SUCCESS" and _num(r.get("final_distance_to_b_m")) is not None]
    ratio = [_num(r["travelled_m"]) / _num(r["straight_line_m"]) for r in rows if _num(r.get("travelled_m")) and _num(r.get("straight_line_m"))]

    def col_mean(name):
        v = [_num(r.get(name)) for r in rows if _num(r.get(name)) is not None]
        return round(st.fmean(v), 2) if v else NE
    return {"source": path.name, "runs": len(rows), "success": wilson(k, len(rows), cfg), "junction_reads": len(reads),
            "read_as_shown": same, "read_as_shown_at_first_ask": f"{first} of {len(reads)}" if first is not None else
            ("14 of 14 (stated in AUDIT.md section 2; not recorded per junction)" if original else NE),
            "collisions": col["collisions"], "collisions_with_a_person": col["human"],
            "closest_person_min_m": round(min(clos), 3) if clos else NE, "final_distance_mean_m": round(st.fmean(fin), 3) if fin else NE,
            "travelled_over_straight_line": round(st.fmean(ratio), 2) if ratio else NE,
            "time_excl_stale_stops_s": col_mean("time_excl_stale_stops_s"), "in_motion_s": col_mean("in_motion_s"), "total_s": col_mean("total_s")}


def v3_columns(cfg: dict) -> dict:
    out = {}
    for key, label, original in (("task2_final", "v3 Task 2 final (original)", True), ("task2_replication", "v3 Task 2 replication", False),
                                 ("task1_final", "v3 Task 1 final", False)):
        p = HERE / cfg["v3_results"][key]
        out[label] = v3_column(p, cfg, original) if p.exists() else {"status": NE, "source": f"{p.name} not found"}
    return out


def v4_column(blk: dict) -> dict:
    s, br, sf, t = blk["success"], blk["branch"], blk["safety"], blk["times"]
    g = blk["gesture"]["per_command"]
    return {"source": "v4 session(s) " + ", ".join(blk["sessions"]), "runs": blk["runs"], "success": s,
            "junction_reads": br["junction_asks"], "read_as_shown": br["correct_of_scored"]["k"],
            "read_as_shown_at_first_ask": f"{br['correct_at_the_first_ask_of_all_asks']['k']} of {br['junction_asks']}",
            "collisions": sf["collisions"], "collisions_with_a_person": sf["collisions_with_a_person"],
            "closest_person_min_m": sf["closest_person_m"].get("min", NE), "final_distance_mean_m": sf["final_distance_to_b_m_successes"].get("mean", NE),
            "travelled_over_straight_line": t["travelled_over_straight_line"].get("mean", NE),
            "time_excl_stale_stops_s": t["time_excl_stale_stops_s"].get("mean", NE), "in_motion_s": t["in_motion_s"].get("mean", NE),
            "total_s": t["total_s"].get("mean", NE), "gesture_coverage_POINT": g["POINT"]["coverage"]["ratio"]}


def _ci(w) -> str:
    return f"{w['k']}/{w['n']} ({w['ratio']}; Wilson 95 % {w['wilson95'][0]}-{w['wilson95'][1]})" if isinstance(w["wilson95"], list) else f"{w['k']}/{w['n']}"


ROWS = [("Runs", lambda c: c["runs"]), ("Success", lambda c: _ci(c["success"])),
        ("Junction asks answered correctly at the first ask", lambda c: c["read_as_shown_at_first_ask"]),
        ("Junction asks answered correctly (any ask) / asks", lambda c: f"{c['read_as_shown']} of {c['junction_reads']}"),
        ("Collisions (with a person)", lambda c: f"{c['collisions']} ({c['collisions_with_a_person']})"),
        ("Closest approach to a person, min (m)", lambda c: c["closest_person_min_m"]),
        ("Final distance from B, successes, mean (m)", lambda c: c["final_distance_mean_m"]),
        ("Travelled / straight line, mean", lambda c: c["travelled_over_straight_line"]),
        ("Time excluding stale-perception stops, mean (s)", lambda c: c["time_excl_stale_stops_s"]),
        ("Time in motion, mean (s)", lambda c: c["in_motion_s"]),
        ("Total time, mean (s) [machine-dependent]", lambda c: c["total_s"])]


def rq1_table(setting_blocks: dict, cfg: dict) -> dict:
    cols = {**v3_columns(cfg), **{f"v4 {name}": v4_column(b) for name, b in setting_blocks.items()}}
    rows = []
    for label, f in ROWS:
        row = {"measure": label}
        for name, c in cols.items():
            try:
                row[name] = NE if c.get("status") == NE else f(c)
            except (KeyError, TypeError):
                row[name] = NE
        rows.append(row)
    return {"columns": list(cols), "rows": rows, "declared_differences": cfg["declared_differences"],
            "comparability": cfg["comparability"], "note": cfg["rq1_note"],
            "reading": "Intervals are over runs (success) and are wide with so few runs; a difference smaller than the intervals is not a "
                       "difference. v3 and v4 differ in the ways listed under the table."}


# ---------------------------------------------------------------- report

def _cell(v) -> str:
    return str(v).replace("|", "/")


def markdown(res: dict) -> str:
    L = [f"# v4 analysis ({'FINAL settings, test data' if res['final'] else 'development data'})", "",
         f"Settings: {', '.join(res['settings'])}. Intervals: Wilson 95 % on counts (labelled with their unit), bootstrap over runs "
         f"({res['config']['bootstrap']['n_resamples']} resamples, seed {res['config']['bootstrap']['seed']}). Every figure is given with "
         "its coverage; not_evaluated means it cannot be computed from the files given.", ""]
    for name, b in res["settings"].items():
        s = b["success"]
        L += [f"## Setting {name}", "", f"{b['runs']} runs ({', '.join(b['sessions'])}). Success {_ci(s)}; failures {s['failure_reasons'] or 'none'}.", ""]
        L += ["| command | frames | answered (coverage) | coverage, Wilson (frames) | coverage, bootstrap (runs) | accuracy of answered | accuracy, Wilson (frames) | accuracy, bootstrap (runs) |",
              "|---|---|---|---|---|---|---|---|"]
        for c, v in b["gesture"]["per_command"].items():
            cb, ab = v["coverage"]["bootstrap"], v["accuracy_of_answered"]["bootstrap"]
            L.append(f"| {c} | {v['frames']} | {v['answered']} ({v['coverage']['ratio']}) | {v['coverage']['wilson95']} | "
                     f"{_b(cb)} | {v['accuracy_of_answered']['ratio']} | {v['accuracy_of_answered']['wilson95']} | {_b(ab)} |")
        f = b["gesture"]["false_reads"]
        a = b["angle"]
        L += ["", f"False reads: {f['read_as_a_command']} of {f['frames_nothing_shown']} frames where nothing was shown.", "",
              f"POINT angle (deg), held frames {a['held_point_frames']}, read as POINT {a['read_as_point']} (coverage {a['coverage']['ratio']}):",
              f"- better depth reading: {_sp(a['better_depth_reading_deg'], res['config'])}",
              f"- roadmap-resolved reading: {_sp(a['resolved_reading_deg'], res['config'])}",
              f"- ambiguous share of resolved frames: {_ci(a['ambiguous_share'])}", ""]
        br, tm, sf = b["branch"], b["timing"], b["safety"]
        L += [f"Branch: accepted {_ci(br['accepted'])}; correct of scored {_ci(br['correct_of_scored'])}; second looks {br['second_view']['asks_with_a_second_view']}, "
              f"re-approaches {br['reapproached']['asks']}.", ""]
        for k, v in b["commander"].items():
            L.append(f"- Commander {k}: {v['frames']} frames, decided {v['decided']} (coverage {v['coverage']['ratio']}), accuracy of decided {_ci({x: v['accuracy_of_decided'][x] for x in ('k', 'n', 'ratio', 'wilson95')})}, "
                     f"run-level bootstrap {_b(v['accuracy_of_decided']['bootstrap'])}.")
        L += ["", f"Time from the question to the accepted gesture (s): accepted {tm['accepted']} of {tm['junction_asks']} asks; "
              f"{_sp(tm['ask_to_accepted_s'], res['config'])}.", "",
              f"Path (against the optimal corridor of all shortest paths; corridor cells {b['path'].get('corridor_cells', NE)}, runs with several shortest "
              f"paths {b['path'].get('runs_with_several_shortest_paths', NE)}): {b['path'].get('coverage')}; trail/optimal {b['path'].get('trail_over_optimal', NE)}; largest distance from the corridor "
              f"{b['path'].get('max_distance_from_optimal_m', NE)}; share within one cell {b['path'].get('share_within_one_cell', NE)}; final distance from B "
              f"{b['path'].get('final_distance_from_b_m', NE)}.",
              f"Safety: collisions {sf['collisions']} (with a person {sf['collisions_with_a_person']}), closest approach {sf['closest_person_m']}.",
              f"System (machine-dependent): inference {b['system']['inference_ms'] if b['system']['inference_ms'] == NE else {k: v['mean'] for k, v in b['system']['inference_ms'].items() if v['mean'] is not None}}; "
              f"round trip {b['system']['round_trip_ms']}.", ""]
        for title, table in (("Per look", b["per_look"]), ("Per look style", b["per_style"]), ("Per distance", b["per_distance"])):
            L += [f"**{title}** (gesturing frames)", "", "| group | frames | answered | coverage | correct | accuracy of answered | accuracy, Wilson |", "|---|---|---|---|---|---|---|"]
            for k, v in table.items():
                L.append(f"| {k} | {v['frames']} | {v['answered']} | {v['coverage']} | {v['correct']} | {v['accuracy_of_answered']} | {v['accuracy_interval']['wilson95']} |")
            L.append("")
        L += ["**Zoom on vs off** (runs of this setting):", ""]
        for z, zb in b["per_zoom"].items():
            if zb == NE:
                L.append(f"- {z}: {NE}")
                continue
            pc = zb["gesture"]["per_command"]
            L.append(f"- {z}: {zb['runs']} runs; success {_ci(zb['success'])}; " + "; ".join(
                f"{c} coverage {v['coverage']['ratio']} accuracy {v['accuracy_of_answered']['ratio']}" for c, v in pc.items())
                + f"; ask to accepted median {zb['timing']['ask_to_accepted_s'].get('median', NE)} s")
        L.append("")
    r = res["rq1"]
    L += ["## Research question 1: v4 against the archived v3 results", "", r["note"], "",
          "| measure | " + " | ".join(r["columns"]) + " |", "|---|" + "---|" * len(r["columns"])]
    for row in r["rows"]:
        L.append(f"| {row['measure']} | " + " | ".join(_cell(row[c]) for c in r["columns"]) + " |")
    L += ["", r["reading"], "", "**Declared differences between v3 and v4** (each can affect the comparison):", ""]
    L += [f"{i}. {d}" for i, d in enumerate(r["declared_differences"], 1)]
    L += ["", "Comparable across machines: " + ", ".join(r["comparability"]["comparable"]) + ". Not comparable across machines: "
          + ", ".join(r["comparability"]["not_comparable_across_machines"]) + "."]
    return "\n".join(L) + "\n"


def _b(d: dict) -> str:
    return NE if d.get("status") == NE else f"{d['estimate']} [{d['lo']}, {d['hi']}] ({d['n_runs']} runs)"


def _sp(d: dict, cfg: dict) -> str:
    if d.get("status") == NE:
        return NE
    p = cfg["angle_percentile"]
    return (f"n {d['n']}, median {d['median']} {_b(d['median_ci'])}, p{p} {d[f'p{p}']} {_b(d[f'p{p}_ci'])}, max {d['max']}"
            if "median_ci" in d else f"n {d['n']}, median {d['median']}, p{p} {d[f'p{p}']}, max {d['max']}")


# ---------------------------------------------------------------- driver

def analyse(sessions: list, cfg: dict | None = None, final: bool = False, repo: Path = fz.REPO) -> dict:
    """sessions: [(setting label, unity folder, bridge folder)]. Applies the split guard (development data only, or test data
    with --final after the freeze check), groups the runs by setting and computes every block."""
    cfg = cfg if cfg is not None else load_config()
    gcfg, ecfg = gd.load_config(), ev.load_config()
    gt_cfg = gt_path.load_config()
    splits = ds.load()
    road = hc.Roadmap(hc.load_json("configs/roadmap.json"))
    if final:
        fz.require_frozen(repo)
        splits = ds.load(repo / "robot_vision/configs/v4/data_splits.json")
    runs = ev.load_sessions([(u, b) for _, u, b in sessions], gcfg, splits, final_evaluation=final, settings=[s for s, _, _ in sessions])
    by: dict[str, list] = defaultdict(list)
    for r in runs:
        by[r.setting].append(r)
    if final:
        for name, rs in by.items():
            problems = fg.check_setting(name, rs, repo)
            if problems:
                raise SystemExit(f"setting {name!r} refused: " + "; ".join(problems))
    blocks = {name: setting_block(run_data(rs, ecfg, gcfg), ecfg, gcfg, gt_cfg, road, cfg, splits) for name, rs in sorted(by.items())}
    return {"final": final, "config": cfg, "settings": blocks, "rq1": rq1_table(blocks, cfg),
            "splits": "TEST looks and clips only, frozen configs verified" if final else "development looks and clips only (data_splits_v4.guard_run)"}


def main(argv=None) -> None:
    import decision_io as dio

    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--session", nargs=3, action="append", required=True, metavar=("SETTING", "UNITY", "BRIDGE"))
    ap.add_argument("--final", action="store_true", help="analyse the TEST data of the final settings (needs the frozen v4 configs)")
    ap.add_argument("--config", default=DEFAULT_CONFIG)
    a = ap.parse_args(argv)
    cfg_path = dio.resolve(a.config)
    sessions = [(s, dio.resolve(u), dio.resolve(b)) for s, u, b in a.session]
    res = analyse(sessions, load_config(cfg_path), a.final)
    out = dio.new_run_dir({"paths": {"output_root": "outputs"}}, "hri_analysis_v4_final" if a.final else "hri_analysis_v4")
    (out / "config_used").mkdir()
    for p in [cfg_path, *(dio.resolve(x) for x in ("configs/v4/eval_dev.json", "configs/v4/gesture_data.json", "configs/v4/data_splits.json",
                                                   "configs/v4/gt_eval.json"))]:
        shutil.copy2(p, out / "config_used" / p.name)
    if a.final:
        shutil.copy2(fz.REPO / fz.FROZEN_REL, out / "config_used" / "frozen.json")
    dio.write_json(out / "analysis.json", {k: v for k, v in res.items() if k != "config"} | {"config_file": cfg_path.name})
    dio.write_json(out / "run.json", {"git": dio.git_info(), "final": a.final, "sessions": [[s, u.name, b.name] for s, u, b in sessions]})
    (out / "analysis.md").write_text(markdown(res), encoding="utf-8")
    with (out / "rq1_comparison.csv").open("x", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["measure", *res["rq1"]["columns"]])
        w.writeheader()
        w.writerows(res["rq1"]["rows"])
    print(markdown(res))
    print(f"Folder: {out}")


if __name__ == "__main__":
    main()
