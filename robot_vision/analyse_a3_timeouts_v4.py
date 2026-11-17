"""Why A3 with detection on times out when the return to the junction point is on (AUDIT.md 16.20.3, 2026-11-17). ANALYSIS ONLY: nothing is changed.

For every seed of A3 (detection on = second opinion + reject impossible, backtrack off, valid-branch liar) it runs the simulator four ways: return_to_junction
on (the live setting) and off, each with the 270 s budget; the runs that time out are repeated with the return on and a 600 s budget to see when they would have
finished (the simulator is deterministic: the same run, only the clock limit differs). It then shows, for every timeout, the timeline of the node visits
(arrival, dialog, ask / second opinion / second view counts, the return to the junction point with its distance and speed, the drive on) and the time spent per
controller state, on against off.

Usage (from robot_vision/): python analyse_a3_timeouts_v4.py [--layout old|clearance] [--label x]
  old       = the live slots before 16.20 (the baseline of 16.20.1: 14/20 with 6 timeouts)
  clearance = scenarios_ab.json as it is now (Nusrat's clearance layout)
Writes outputs/a3_timeouts_v4_<time>[_label]/ (report.md, report.json, config_used.json, run.json with the git commit); never overwrites.
"""

from __future__ import annotations

import argparse
import copy
import json
import math
import subprocess
import sys
import time
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

import hri_sim_v4 as sv  # noqa: E402

OLD_SLOTS = [{"before_m": 3.0, "right_m": -2.0}, {"before_m": 5.5, "right_m": 2.0}, {"before_m": 6.0, "right_m": -2.0}]   # live slots before AUDIT.md 16.20


def scenarios(layout: str) -> dict:
    scen = copy.deepcopy(sv.load_scenarios())
    if layout == "old":
        for k in ("1", "2", "3"):
            scen["scenarios"][k]["layout"]["junction_slots"] = copy.deepcopy(OLD_SLOTS)
        scen["scenarios"]["4"]["layout"]["people_by_node"] = {"J1": 3}
    return scen


def run_one(seed: int, scen: dict, return_to_junction: bool, timeout_s: float, cruise_return: bool = False) -> dict:
    stops: list = []

    def hook(c):
        if not return_to_junction:
            c.v4["dialog"]["return_to_junction"] = False
        orig, state = c.step, {"on": False}

        def step(inp):                                          # observation only: logs when a safety stop begins
            out = orig(inp)
            now = bool(c.safety_reason)
            if now and not state["on"]:
                stops.append({"t": round(inp.time_s, 2), "x": round(inp.x, 2), "z": round(inp.z, 2), "state": c.state, "node": c.node, "reason": str(c.safety_reason)})
            state["on"] = now
            return out
        c.step = step
        if cruise_return:                                       # COUNTERFACTUAL (a hook on this one run; no code or config is changed): the return drives at cruise_speed_mps
            tick = c._tick

            def _tick(inp, cmd):
                if c.state == "execute" and c._return_pending():
                    saved = c.d["approach_speed_mps"]
                    c.d["approach_speed_mps"] = c.d["cruise_speed_mps"]
                    try:
                        return tick(inp, cmd)
                    finally:
                        c.d["approach_speed_mps"] = saved
                return tick(inp, cmd)
            c._tick = _tick
    sc = sv.scenario_ab("A3", seed, sv.DETECTION_ON, scen=scen, hook=hook, sim_cfg=sv.SimConfig(timeout_s=timeout_s))
    r = sc["sim"].run(sc["goal"])
    r["_safety"] = stops
    r["_road"] = sc["road"]
    r["_goal"] = sc["goal"]
    return r


def pose_at(r: dict, t: float) -> tuple[float, float]:
    f = min(r["frames"], key=lambda fr: abs(fr["time_s"] - t))
    return f["pose"]["x"], f["pose"]["z"]


def state_times(r: dict) -> dict:
    """Seconds spent in each controller state (the trace is 't:state' at every change; the last state runs to the end of the run)."""
    ev = [(float(x.split(":")[0]), x.split(":")[1]) for x in r["trace"]]
    out = defaultdict(float)
    for (t0, s), (t1, _) in zip(ev, ev[1:] + [(r["time_s"], "")]):
        out[s] += t1 - t0
    return {k: round(v, 1) for k, v in out.items()}


def visits(r: dict) -> list[dict]:
    """One row per node visit: arrival, dialog, the return to the junction point, the drive on."""
    road = r["_road"]
    dec = r["v4"]["decisions"]
    tr = [(float(x.split(":")[0]), x.split(":")[1]) for x in r["trace"]]
    rows = []
    recs = []
    for rec in r["junctions"]:                                  # one record per opinion: merge the consecutive records of one node into one visit
        if recs and recs[-1]["junction"] == rec["junction"]:
            continue
        recs.append(rec)
    for i, rec in enumerate(recs):
        node, t0 = rec["junction"], rec["t_start"]
        mine = [d for d in dec if d["node"] == node and d["t"] >= t0 - 1e-9 and (i + 1 >= len(recs) or d["t"] < recs[i + 1]["t_start"] - 1e-9)]
        go = next((d for d in mine if d["event"] == "go"), None)
        back = next((d for d in mine if d["event"] == "returned_to_junction"), None)
        row = {"node": node, "arrive_s": round(t0, 1), "arrive_at": tuple(round(c, 1) for c in pose_at(r, t0)), "go_at": None, "returned_at": None, "go_s": go["t"] if go else None, "dialog_s": round(go["t"] - t0, 1) if go else None,
               "people_asked": sum(1 for d in mine if d["event"] == "ask_next") + 1, "second_views": sum(1 for d in mine if d["event"] == "second_view"),
               "rejections": sum(1 for d in mine if d["event"] == "answer_rejected"), "branch": go.get("branch") if go else None,
               "returned_s": back["t"] if back else None}
        if go and back:
            nx, nz = road.pos(node)
            p0 = pose_at(r, go["t"])
            row["go_at"] = tuple(round(c, 1) for c in p0)
            row["returned_at"] = tuple(round(c, 1) for c in pose_at(r, back["t"]))
            row["return_s"] = round(back["t"] - go["t"], 1)
            row["return_from_m"] = round(math.dist(p0, (nx, nz)), 2)
            row["return_speed_mps"] = round(row["return_from_m"] / row["return_s"], 2) if row["return_s"] > 0 else None
            nav = next((t for t, s in tr if s == "navigate" and t >= back["t"] - 1e-9), None)
            row["navigate_from_s"] = nav
            if nav is not None and i + 1 < len(recs):
                row["drive_to_next_s"] = round(recs[i + 1]["t_start"] - nav, 1)
        rows.append(row)
    return rows


def analyse(layout: str, seeds=range(1, 21)) -> dict:
    scen = scenarios(layout)
    per_seed = []
    for seed in seeds:
        on = run_one(seed, scen, True, 270.0)
        off = run_one(seed, scen, False, 270.0)
        entry = {"seed": seed, "goal": on["_goal"], "route": on["v4"]["route"], "on": {"outcome": on["outcome"], "failure": on["failure_reason"], "time_s": on["time_s"],
                                                                                   "safety_stop_s": on["safety_stop_s"], "safety_stops": on["_safety"]},
                 "off": {"outcome": off["outcome"], "time_s": off["time_s"], "safety_stop_s": off["safety_stop_s"], "safety_stops": off["_safety"]},
                 "visits_on": visits(on), "states_on": state_times(on), "states_off": state_times(off), "visits_off": visits(off)}
        entry["return_total_s"] = round(sum(v.get("return_s") or 0.0 for v in entry["visits_on"]), 1)
        entry["returns"] = sum(1 for v in entry["visits_on"] if v.get("return_s") is not None)
        if on["outcome"] != "SUCCESS":
            long = run_one(seed, scen, True, 600.0)
            entry["needs_s"] = long["time_s"] if long["outcome"] == "SUCCESS" else None
            entry["needs_outcome"] = long["outcome"]
            last = on["frames"][-1]
            entry["at_timeout"] = {"x": last["pose"]["x"], "z": last["pose"]["z"], "state": on["state"], "final_node": on["final_node"], "route_so_far": on["v4"]["route"],
                                   "distance_to_goal_m": on["final_distance_m"]}
            long_states = state_times(long)
            entry["states_needs"] = long_states
        cf = run_one(seed, scen, True, 270.0, cruise_return=True)
        entry["counterfactual_cruise_return"] = {"outcome": cf["outcome"], "failure": cf["failure_reason"], "time_s": cf["time_s"], "closest_person_m": cf["closest_person_m"],
                                                 "safety_stops": cf["_safety"], "returns": [v.get("return_s") for v in visits(cf) if v.get("return_s") is not None]}
        entry["closest_person_on_m"] = on["closest_person_m"]
        per_seed.append(entry)
    return {"layout": layout, "seeds": per_seed}


def markdown(res: dict) -> str:
    L = [f"# A3, detection on: return_to_junction on against off (layout: {res['layout']}; simulator, 20 seeds, 270 s)", ""]
    ps = res["seeds"]
    L += ["| seed | goal | route | on: outcome | on: s | off: outcome | off: s | returns | return s total | on - off s |", "|---|---|---|---|---|---|---|---|---|---|"]
    for e in ps:
        L.append(f"| {e['seed']} | {e['goal']} | {'>'.join(e['route'])} | {e['on']['outcome']}{' (' + e['on']['failure'] + ')' if e['on']['failure'] not in (None, 'none') else ''} | "
                 f"{e['on']['time_s']} | {e['off']['outcome']} | {e['off']['time_s']} | {e['returns']} | {e['return_total_s']} | {round(e['on']['time_s'] - e['off']['time_s'], 1)} |")
    to = [e for e in ps if e["on"]["outcome"] != "SUCCESS"]
    L += ["", f"Timeouts with the return on: {len(to)} of {len(ps)} (seeds {', '.join(str(e['seed']) for e in to)}); with the return off: "
          f"{sum(e['off']['outcome'] != 'SUCCESS' for e in ps)}.", ""]
    for e in to:
        L += [f"## Seed {e['seed']}: goal {e['goal']}, timeout at 270 s", "",
              f"- At the timeout: position ({e['at_timeout']['x']:.1f}, {e['at_timeout']['z']:.1f}), state `{e['at_timeout']['state']}`, nodes visited {'>'.join(e['at_timeout']['route_so_far'])}, "
              f"{e['at_timeout']['distance_to_goal_m']:.1f} m from the goal; safety stops: {e['on']['safety_stops'] or 'none'}.",
              f"- The same run with a 600 s budget ends **{e['needs_outcome']} at {e['needs_s']} s**; with the return off it ends {e['off']['outcome']} at {e['off']['time_s']} s "
              f"(the returns cost {e['return_total_s']} s in {e['returns']} visits).", "",
              "| node | arrive s (position) | people asked | second views | rejections | go s (position) | dialog s | return from m | return s | return m/s | returned s (position) | drive on to next node s |", "|---|---|---|---|---|---|---|---|---|---|---|---|"]
        for v in e["visits_on"]:
            L.append(f"| {v['node']} | {v['arrive_s']} {v['arrive_at']} | {v['people_asked']} | {v['second_views']} | {v['rejections']} | {v['go_s']} {v['go_at']} | {v['dialog_s']} | "
                     f"{v.get('return_from_m', '-')} | {v.get('return_s', '-')} | {v.get('return_speed_mps', '-')} | {v.get('returned_s', '-')} {v['returned_at']} | {v.get('drive_to_next_s', '-')} |")
        keys = sorted(set(e["states_on"]) | set(e["states_off"]) | set(e["states_needs"]))
        L += ["", "Seconds per controller state: " + "; ".join(f"{k}: on(270 s) {e['states_on'].get(k, 0)}, on(600 s budget, to the end) {e['states_needs'].get(k, 0)}, off {e['states_off'].get(k, 0)}" for k in keys), ""]
    cf = [e["counterfactual_cruise_return"] for e in ps]
    L += ["## Counterfactual (a hook for the analysis; no code or config changed): the return at cruise_speed_mps 0.8 instead of approach_speed_mps 0.4", "",
          f"- SUCCESS {sum(c['outcome'] == 'SUCCESS' for c in cf)}/{len(cf)} (live return {sum(e['on']['outcome'] == 'SUCCESS' for e in ps)}/{len(ps)}, return off {sum(e['off']['outcome'] == 'SUCCESS' for e in ps)}/{len(ps)}); "
          f"timeouts {sum(c['outcome'] != 'SUCCESS' for c in cf)}.",
          "- finishing times (s), median / longest: live return " + f"{sorted(e['on']['time_s'] for e in ps)[len(ps) // 2]} / {max(e['on']['time_s'] for e in ps)}; cruise return "
          f"{sorted(c['time_s'] for c in cf)[len(cf) // 2]} / {max(c['time_s'] for c in cf)}; return off {sorted(e['off']['time_s'] for e in ps)[len(ps) // 2]} / {max(e['off']['time_s'] for e in ps)}.",
          f"- return duration, median s: " + str(sorted(x for c in cf for x in c['returns'])[len([x for c in cf for x in c['returns']]) // 2]) + "; the live one 12.2 s (below).",
          f"- closest approach to any person, smallest over the 20 runs: live {min(e['closest_person_on_m'] for e in ps)} m, cruise return {min(c['closest_person_m'] for c in cf)} m.",
          f"- safety stops: live {sum(len(e['on']['safety_stops']) for e in ps)}, cruise return {sum(len(c['safety_stops']) for c in cf)}.", ""]
    allret = [v for e in ps for v in e["visits_on"] if v.get("return_s") is not None]
    if allret:
        L += ["## The return itself (every visit of the 20 runs with a return)", "",
              f"- visits with a return: {len(allret)}; return distance {min(v['return_from_m'] for v in allret)} to {max(v['return_from_m'] for v in allret)} m (median "
              f"{sorted(v['return_from_m'] for v in allret)[len(allret) // 2]} m); duration median {sorted(v['return_s'] for v in allret)[len(allret) // 2]} s, "
              f"total {round(sum(v['return_s'] for v in allret), 1)} s; speed median {sorted(v['return_speed_mps'] for v in allret if v['return_speed_mps'])[len(allret) // 2]} m/s."]
        by = defaultdict(list)
        for v in allret:
            by[v["node"]].append(v["return_s"])
        L += ["- per node (median s of the return, n): " + ", ".join(f"{k} {sorted(x)[len(x) // 2]} (n={len(x)})" for k, x in sorted(by.items())), ""]
    return "\n".join(L)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--layout", choices=("old", "clearance"), default="old")
    ap.add_argument("--label", default="")
    a = ap.parse_args(argv)
    res = analyse(a.layout)
    out = ROOT / "outputs" / f"a3_timeouts_v4_{time.strftime('%Y%m%d_%H%M%S')}{'_' + a.label if a.label else ''}"
    out.mkdir(parents=True, exist_ok=False)
    (out / "report.json").write_text(json.dumps(res, indent=1, default=str), encoding="utf-8")
    md = markdown(res)
    (out / "report.md").write_text(md + "\n", encoding="utf-8")
    commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    (out / "run.json").write_text(json.dumps({"git_commit": commit, "layout": a.layout}, indent=1), encoding="utf-8")
    (out / "config_used.json").write_text(json.dumps(scenarios(a.layout)["scenarios"]["3"], indent=1), encoding="utf-8")
    print(md)
    print(f"\nFolder: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
