"""Sim / Unity agreement on the B settings of step 5 (AUDIT.md 16.28 item 3b). EVALUATION CODE; analysis only: it changes no value, rule or config.

Unity's step-5 sessions (the zip of finals_v4/step5_zip_v4.py, read in place, never extracted) record for every run the placement of every worker and who lies and what the liar
shows (`session.json` `workers_plan`: "run 2 worker 5: J2 slot 1, <look>, (x, z), LIAR shows RIGHT (true FORWARD)"), the goals (`goals_override` E5,E6,E5) and the result (`truth_run###.json`,
`runs.csv`, `dialogs.csv`). This script replays each run in the simulator (hri_sim_v4) with THE SAME placement, THE SAME liars (a liar shows the same wrong direction at every ask, as in
Unity), THE SAME goal and the same lie-detection switches, and compares run by run: the outcome, the route, the junction decisions (a wrong-branch decision is where a failure happened), and the
asks of liars. Two simulator variants: "sim" (as it is: every pointing is read, nothing is noisy: one deterministic run) and "sim + readability" (the model of AUDIT.md 16.26.6: a pointing
close to the line of sight is not read; stochastic: N seeds). The simulator code is not touched: the fixed layout and the liars are given through the simulator's own `layout`
{"kind": "fixed"} and its per-worker lie table.

Usage (from robot_vision/): python compare_sim_unity_v4.py --zip ~/Downloads/step5_t0_logs_<...>.zip [--seeds 40] [--label x]
Writes outputs/compare_sim_unity_v4_<time>[_label]/ (report.json, report.md, run.json); never overwrites."""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import re
import subprocess
import time
import types
import zipfile
from collections import Counter
from pathlib import Path

import hri_sim as hs
import hri_sim_v4 as sv

HERE = Path(__file__).resolve().parent
SETTINGS = ("B3", "B3_off", "B4", "B4_off")
READABILITY = "configs/v4/experiments/point_readability.json"
PLAN_LINE = re.compile(r"run (\d+) worker (\d+): (\w+) slot (\d+), (\S+), \(([-\d.]+), ([-\d.]+)\), (?:truthful (\w+)|LIAR shows (\w+)(?: \(no such branch\))? \(true (\w+)\))")


def parse_workers_plan(lines: list[str]) -> dict:
    """{run: {node: [ {slot, look, x, z, lie, true}, ... ]}} from session.json `workers_plan`; `lie` is the direction a liar shows (None = honest), `true` the honest direction.
    The workers of a node are in slot order (slot 1 is the first person of the node in the simulator's layout). A line that does not fit is an error, never skipped."""
    plan: dict = {}
    for line in lines:
        m = PLAN_LINE.match(line)
        if m is None:
            raise ValueError(f"workers_plan line not understood: {line!r}")
        run, _w, node, slot, look, x, z, truthful, lie, true = m.groups()
        plan.setdefault(int(run), {}).setdefault(node, []).append({"slot": int(slot), "look": look, "x": float(x), "z": float(z), "lie": lie, "true": truthful or true})
    for nodes in plan.values():
        for ws in nodes.values():
            ws.sort(key=lambda w: w["slot"])
    return plan


def fixed_layout(nodes: dict) -> dict:
    """The simulator's explicit layout of one run: the workers of every node at Unity's positions, in slot order."""
    return {"kind": "fixed", "points": {n: [[w["x"], w["z"]] for w in ws] for n, ws in nodes.items()}}


def lie_table(nodes: dict) -> dict:
    """{(node, person id): the direction a liar shows | None}: person ids of the simulator's layout are 1, 2, ... in slot order."""
    return {(n, i + 1): w["lie"] for n, ws in nodes.items() for i, w in enumerate(ws)}


def wrong_decisions(decisions: list[dict], correct_of) -> list[dict]:
    """The junction decisions that took another branch than the one toward the goal: [{'node', 'drove', 'true'}]. decisions: events 'go' with node and branch; correct_of(node) = the true branch."""
    out = []
    for d in decisions:
        if d.get("event") == "go":
            true = correct_of(d["node"])
            if d.get("branch") != true:
                out.append({"node": d["node"], "drove": d.get("branch"), "true": true})
    return out


# ---------------------------------------------------------------- Unity

def _rows(z: zipfile.ZipFile, name: str) -> list[dict]:
    return list(csv.DictReader(io.StringIO(z.read(name).decode("utf-8-sig"))))


def unity_session(z: zipfile.ZipFile, setting: str) -> dict:
    """What Unity recorded for one step-5 session t0_<setting>: per run the goal, outcome, route, the lies, the wrong-branch decisions, the dialog results and the placement."""
    man = json.loads(z.read("MANIFEST.json").decode("utf-8-sig"))
    s = next(x for x in man["sessions"] if x["setting"] == f"t0_{setting}")
    st, unity, exp = s["setting"], s["unity"], s["export"]
    sess = json.loads(z.read(f"{st}/{unity}/session.json").decode("utf-8-sig"))
    plan = parse_workers_plan(sess["workers_plan"])
    runs = {int(r["trial"]): r for r in _rows(z, f"{st}/{exp}/runs.csv")}
    dl = _rows(z, f"{st}/{exp}/dialogs.csv")
    out = {}
    for trial, r in sorted(runs.items()):
        ds = [x for x in dl if int(x["trial"]) == trial]
        groups: dict = {}
        for x in ds:
            groups.setdefault((x["junction"], x["visit"], x["dialog"]), []).append(x)
        wrong, aborts, asks_liar = [], [], 0
        visits: dict = {}
        for (node, visit, dialog), g in groups.items():                    # the branch driven is decided once per junction visit: by its last dialog
            if (node, visit) not in visits or int(dialog) > visits[(node, visit)][0]:
                visits[(node, visit)] = (int(dialog), g)
            if g[-1]["decision"] != "accepted" and not g[-1]["decision"].startswith("rejected"):
                aborts.append({"node": node, "reasons": [x["decision_reason"][:60] for x in g if x["decision_reason"]]})
            asks_liar += sum(1 for x in g if x["truthful"].lower() == "false")
        for (node, _visit), (_d, g) in visits.items():
            last = g[-1]
            if last["final_branch"] and last["true_branch"] and last["final_branch"] != last["true_branch"]:
                wrong.append({"node": node, "drove": last["final_branch"], "true": last["true_branch"]})
        out[trial] = {"goal": r["goal"], "outcome": r["outcome"], "failure_reason": r["failure_reason"], "route": r["route"], "time_s": float(r["time_s"]),
                      "lies": [int(float(r[k] or 0)) for k in ("lies_given", "lies_detected", "lies_corrected", "lies_fooled")],
                      "wrong_decisions": wrong, "unclear_dialogs": aborts, "asks_of_liars": asks_liar, "dialogs": len(groups), "nodes": plan[trial]}
    return {"setting": setting, "goals": sess.get("goals_override"), "seed": sess["seed"], "runs": out, "lie_rule": sess["lie_rule"]}


# ---------------------------------------------------------------- the simulator

def run_sim(setting: str, nodes: dict, goal: str, seed: int = 1, readability: dict | None = None, timeout_s: float = 900.0) -> dict:
    """One simulated run of a B setting with Unity's placement and liars and Unity's goal. Returns a summary comparable with unity_session()['runs'][i]."""
    name, on = setting.split("_")[0], not setting.endswith("_off")
    sc = sv.scenario_ab(name, seed, dict(sv.DETECTION_ON if on else sv.DETECTION_OFF), sim_cfg=hs.SimConfig(timeout_s=timeout_s),
                        gcfg=sv.GestureSimConfig(point_readability=readability) if readability is not None else None)
    spec, sim, road = sc["spec"], sc["sim"], sc["road"]
    spec.layout = fixed_layout(nodes)
    spec.lie_probability, spec.lie_mode, spec.lie_script = 0.2, "per_worker", None
    lies = lie_table(nodes)
    orig = sim._stage_ask

    def staged(self, scene, t, junction, goal_, serial=0):
        w = self._asked_worker(scene)                                          # the worker the controller is asking; its lie is Unity's, not a draw
        self._worker_lies[f"{self.seed}|{junction}|{w.id}"] = lies.get((junction, w.id))
        return orig(scene, t, junction, goal_, serial)
    sim._stage_ask = types.MethodType(staged, sim)
    r = sim.run(goal)
    dec = r["v4"]["decisions"]
    asked = [g for g in r["gestures"] if g.get("kind") != "checkpoint"]
    aborts = [{"node": d.get("node"), "reasons": [d.get("reason", "")[:60]]} for d in dec if d.get("event") == "abort"]
    honest_ok = [(g["node"], g["worker"]) for g in asked if g["truthful"] and g["shown"] != road.command_toward(g["node"], goal) and road.command_toward(g["node"], goal) != "NONE"]
    return {"outcome": r["outcome"], "failure_reason": r["failure_reason"], "route": ">".join(r["v4"]["route"]), "time_s": r["time_s"], "asks": len(asked),
            "asks_of_liars": sum(1 for g in asked if not g["truthful"]), "wrong_decisions": wrong_decisions(dec, lambda n: road.command_toward(n, goal)),
            "unclear_dialogs": aborts, "honest_mismatch": honest_ok,
            "rejections": [d.get("detail") or d.get("reason") for d in dec if d.get("event") == "answer_rejected"]}


def harness_check(setting: str, nodes: dict, goal: str) -> list[dict]:
    """Does the simulator's map agree with Unity's on what an honest worker shows? For every worker of the plan the direction toward the goal from its node (the simulator: command_toward,
    BACK where the goal is not reachable, as the simulated worker does) is compared with the honest direction Unity recorded. [] = every worker agrees."""
    sc = sv.scenario_ab(setting.split("_")[0], 1, dict(sv.DETECTION_ON))
    road = sc["road"]
    bad = []
    for node, ws in nodes.items():
        want = road.command_toward(node, goal)
        want = "BACK" if want == "NONE" else want
        for w in ws:
            if w["true"] != want:
                bad.append({"node": node, "slot": w["slot"], "unity_true": w["true"], "sim_true": want})
    return bad


def readability_model(path: str = READABILITY) -> dict:
    return json.loads((HERE / path).read_text(encoding="utf-8"))


def compare(unity: dict, sim: dict) -> dict:
    """Run by run: do the two agree on the outcome, on the route, on the wrong-branch decisions (node and branch driven)?"""
    key = lambda w: [(d["node"], d["drove"]) for d in w]
    return {"outcome": (unity["outcome"], sim["outcome"]), "same_outcome": unity["outcome"] == sim["outcome"] or (unity["outcome"] == "FAILURE" and sim["outcome"] == "FAILURE"),
            "same_failure_reason": unity["failure_reason"] == sim["failure_reason"], "same_route": unity["route"] == sim["route"], "same_wrong_decisions": key(unity["wrong_decisions"]) == key(sim["wrong_decisions"])}


def analyse(zip_path: str, seeds: int) -> dict:
    z = zipfile.ZipFile(zip_path)
    model = readability_model()
    rep: dict = {"zip": {"name": Path(zip_path).name, "sha256": hashlib.sha256(Path(zip_path).read_bytes()).hexdigest()}, "readability_model_file": READABILITY, "seeds": seeds, "settings": {}}
    for setting in SETTINGS:
        u = unity_session(z, setting)
        goals = [u["runs"][t]["goal"] for t in sorted(u["runs"])]
        rows = []
        for trial in sorted(u["runs"]):
            ur = u["runs"][trial]
            check = harness_check(setting, ur["nodes"], ur["goal"])
            plain = run_sim(setting, ur["nodes"], ur["goal"])
            noisy = [run_sim(setting, ur["nodes"], ur["goal"], seed=s, readability=model) for s in range(1, seeds + 1)]
            rows.append({"trial": trial, "harness_check": check, "unity": {k: v for k, v in ur.items() if k != "nodes"}, "liars": {n: [(w["slot"], w["lie"]) for w in ws if w["lie"]] for n, ws in ur["nodes"].items()},
                         "sim": plain, "agree_sim": compare(ur, plain),
                         "readability": {"success": sum(r["outcome"] == "SUCCESS" for r in noisy), "n": len(noisy), "outcomes": dict(Counter(r["failure_reason"] for r in noisy)),
                                         "routes": dict(Counter(r["route"] for r in noisy).most_common(4)),
                                         "same_route_as_unity": sum(r["route"] == ur["route"] for r in noisy), "same_wrong_decisions_as_unity": sum(compare(ur, r)["same_wrong_decisions"] for r in noisy),
                                         "first": noisy[0]}})
        rep["settings"][setting] = {"goals": goals, "runs": rows}
    return rep


def markdown(rep: dict) -> str:
    L = ["## Sim / Unity agreement on B3, B3_off, B4, B4_off (AUDIT.md 16.28 item 3b); same placement, liars, goals, lie-detection switches; the simulator is not changed", "",
         f"Zip `{rep['zip']['name']}` SHA-256 `{rep['zip']['sha256']}` read in place. Readability model `{rep['readability_model_file']}`, {rep['seeds']} seeds per run.", "",
         "| setting | run | goal | liars (node: slot shows) | Unity | sim (as is) | sim + readability: successes / seeds, same route as Unity |", "|---|---|---|---|---|---|---|"]
    tot_u = tot_s = tot_r = 0
    for setting, d in rep["settings"].items():
        for r in d["runs"]:
            u, s, y = r["unity"], r["sim"], r["readability"]
            liars = "; ".join(f"{n}: " + ",".join(f"{sl} shows {lie}" for sl, lie in ls) for n, ls in r["liars"].items() if ls) or "none"
            uw = ", ".join(f"{w['node']} drove {w['drove']} (true {w['true']})" for w in u["wrong_decisions"]) or "-"
            sw = ", ".join(f"{w['node']} drove {w['drove']} (true {w['true']})" for w in s["wrong_decisions"]) or "-"
            L.append(f"| {setting} | {r['trial']} | {u['goal']} | {liars} | {u['outcome']} {u['failure_reason']}; {u['route']}; wrong: {uw}; unclear: {[a['node'] for a in u['unclear_dialogs']] or '-'}; "
                     f"asks of liars {u['asks_of_liars']} | {s['outcome']} {s['failure_reason']}; {s['route']}; wrong: {sw}; unclear: {[a['node'] for a in s['unclear_dialogs']] or '-'}; asks of liars {s['asks_of_liars']} "
                     f"| {y['success']}/{y['n']}, route {y['same_route_as_unity']}/{y['n']}, outcomes {y['outcomes']} |")
            tot_u += u["outcome"] == "SUCCESS"
            tot_s += s["outcome"] == "SUCCESS"
            tot_r += y["success"]
    n_runs = sum(len(d["runs"]) for d in rep["settings"].values())
    rows = [r for d in rep["settings"].values() for r in d["runs"]]
    L += ["", f"Successes: Unity {tot_u} of {n_runs}; simulator as is {tot_s} of {n_runs}; simulator with readability: mean {tot_r / max(1, rep['seeds']):.2f} of {n_runs} per seed.", "",
          f"Harness check (every worker's honest direction in the simulator equals Unity's): mismatches in {sum(bool(r['harness_check']) for r in rows)} of {n_runs} runs.",
          f"Simulator as is against Unity, run by run: same outcome class {sum(r['agree_sim']['outcome'][0] == r['agree_sim']['outcome'][1] or (r['agree_sim']['outcome'][0] != 'SUCCESS' and r['agree_sim']['outcome'][1] != 'SUCCESS') for r in rows)} of {n_runs}; "
          f"same failure reason {sum(r['agree_sim']['same_failure_reason'] for r in rows)}; same route {sum(r['agree_sim']['same_route'] for r in rows)}; same wrong-branch decisions {sum(r['agree_sim']['same_wrong_decisions'] for r in rows)}.",
          f"Simulator with readability ({rep['seeds']} seeds x {n_runs} runs): successes {sum(r['readability']['success'] for r in rows)} of {rep['seeds'] * n_runs}; outcomes {dict(sum((Counter(r['readability']['outcomes']) for r in rows), Counter()))}; "
          f"same route as Unity {sum(r['readability']['same_route_as_unity'] for r in rows)} of {rep['seeds'] * n_runs}."]
    return "\n".join(L)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--zip", required=True)
    ap.add_argument("--seeds", type=int, default=40)
    ap.add_argument("--label", default="")
    a = ap.parse_args(argv)
    rep = analyse(str(Path(a.zip).expanduser()), a.seeds)
    out = HERE / "outputs" / f"compare_sim_unity_v4_{time.strftime('%Y%m%d_%H%M%S')}{'_' + a.label if a.label else ''}"
    out.mkdir(parents=True, exist_ok=False)
    md = markdown(rep)
    (out / "report.json").write_text(json.dumps(rep, indent=1, default=str), encoding="utf-8")
    (out / "report.md").write_text(md + "\n", encoding="utf-8")
    commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=HERE, capture_output=True, text=True).stdout.strip()
    (out / "run.json").write_text(json.dumps({"git_commit": commit, "zip": rep["zip"], "seeds": rep["seeds"]}, indent=1), encoding="utf-8")
    print(md)
    print(f"\nFolder: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
