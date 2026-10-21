"""Development evaluation of vision mode (dev seed only; refuses final sessions and the final seed).

Inputs (a Unity session folder and the bridge run folder that served it):
    --sweep  outputs/gestures_sweep_development_X  outputs/bridge_guide_Y     gestures (pan-tilt camera)
    --trials outputs/trials_development_Task2_X    outputs/bridge_guide_Y     people (360 deg camera), trials
    --forward-hands outputs/forward_hand_sweep_development_X outputs/bridge_guide_Y   FORWARD fist vs index finger
Optional --simulate N: hri_sim.py trials with the measured rates (label "simulation", not Unity).

Gestures, per pan-tilt frame inside each sweep sample: confusion matrix shown x read, per command coverage (frames
with a command / frames) and accuracy (correct / frames with a command); per sample, whether the 1.0 s hold rule
accepts the shown command (strict: any NONE restarts; tolerant: NONE gaps up to max_none_gap_s), with
hri_control.GestureDialog itself. People, per 360 frame of the trials: the true worker position at the frame's time
(truth_run###.csv), recall within the bearing match by distance bin, the panorama detection rate, distance error by
source. Inference times per model. This is evaluation code (it reads truth); inference never imports it.
Criteria: configs/hri_perception.json -> evaluation (declared before any evaluation).
"""

from __future__ import annotations

import argparse
import bisect
import csv
import json
import math
import statistics as st
from collections import Counter, defaultdict
from pathlib import Path

import hri_control as hc

HERE = Path(__file__).resolve().parent
COMMANDS = ["NONE", "LEFT", "FORWARD_LEFT", "FORWARD", "FORWARD_RIGHT", "RIGHT", "STOP"]
DIRECTIONS = list(hc.DIRECTIONS)


def read_csv(p: Path) -> list[dict]:
    if not p.exists():
        return []
    with p.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def num(x, d=None):
    try:
        v = float(x)
        return v if math.isfinite(v) else d
    except (TypeError, ValueError):
        return d


def r3(x):
    return round(x, 3) if isinstance(x, float) else x


def pct(v, q):
    v = sorted(v)
    if not v:
        return None
    k = (len(v) - 1) * q
    lo, hi = math.floor(k), math.ceil(k)
    return v[lo] + (v[hi] - v[lo]) * (k - lo)


def guard_development(session: Path) -> dict:
    info = json.loads((session / "session.json").read_text(encoding="utf-8"))
    cfgs = list((session / "config_used").glob("trials*.json"))
    cfg = json.loads(cfgs[0].read_text(encoding="utf-8")) if cfgs else {}
    if info.get("mode") != "development" or cfg.get("mode", "development") != "development":
        raise SystemExit(f"{session.name}: not a development session; this script never evaluates final runs")
    if "dev_seed" in cfg and (info.get("seed") != cfg["dev_seed"] or info.get("seed") == cfg.get("final_seed")):
        raise SystemExit(f"{session.name}: seed {info.get('seed')} is not the dev seed {cfg['dev_seed']}")
    return info


# ---------------------------------------------------------------- gestures

def hold_result(frames: list[dict], hold_s: float, gap_s: float) -> str | None:
    """Command accepted by the dialog's hold rule within the frames of one sample (None = nothing accepted)."""
    d = hc.GestureDialog(hold_s, 1e9, 1, max_none_gap_s=gap_s)
    if not frames:
        return None
    d.begin_ask(frames[0]["t"])
    for f in frames:
        if d.update(f["read"], f["t"], f["t"]) == "accepted":
            return d.accepted
    return None


def eval_gestures(sweep: Path, bridge: Path, hold_s: float, gap_s: float) -> dict:
    truth = read_csv(sweep / "truth_sweep.csv")
    frames = sorted(({"t": float(r["time_s"]), "read": r["gesture_read"] or "NONE"}
                     for r in read_csv(bridge / "perception.csv") if r["type"] == "frame_pan_tilt" and num(r["time_s"]) is not None),
                    key=lambda f: f["t"])
    ts = [f["t"] for f in frames]
    conf = {c: Counter() for c in COMMANDS}
    samples = {c: {"strict": Counter(), "tolerant": Counter(), "n": 0} for c in COMMANDS}
    by_dist = defaultdict(Counter)
    for t in truth:
        shown, t0, t1, d = t["gesture_shown"], float(t["t_start"]), float(t["t_end"]), float(t["distance_m"])
        win = frames[bisect.bisect_left(ts, t0):bisect.bisect_right(ts, t1)]
        b = "1.7-2.1 m" if d < 2.1 else "2.1-2.5 m"
        for f in win:
            conf[shown][f["read"]] += 1
            by_dist[(b, shown)]["frames"] += 1
            by_dist[(b, shown)]["covered"] += f["read"] != "NONE"
            by_dist[(b, shown)]["correct"] += f["read"] == shown
        samples[shown]["n"] += 1
        for name, gap in (("strict", 0.0), ("tolerant", gap_s)):
            acc = hold_result(win, hold_s, gap)
            key = ("correct" if acc is None else "false_accept") if shown in ("NONE", "STOP") else \
                ("correct" if acc == shown else "none" if acc is None else "wrong")
            samples[shown][name][key] += 1
    per = {}
    for c in COMMANDS:
        n = sum(conf[c].values())
        covered = n - conf[c]["NONE"]
        e = {"frames": n, "samples": samples[c]["n"],
             "hold_strict": dict(samples[c]["strict"]), "hold_tolerant": dict(samples[c]["tolerant"])}
        if c == "NONE":
            e["false_command_rate"] = r3(covered / n) if n else None
        else:
            e.update(coverage=r3(covered / n) if n else None, accuracy=r3(conf[c][c] / covered) if covered else None,
                     correct_rate=r3(conf[c][c] / n) if n else None)
        per[c] = e
    return {"confusion": {c: dict(conf[c]) for c in COMMANDS}, "per_command": per, "samples": len(truth),
            "frames": len(frames), "hold_s": hold_s, "tolerant_gap_s": gap_s,
            "by_distance": {f"{b} {s}": {"frames": c["frames"], "coverage": r3(c["covered"] / c["frames"]) if c["frames"] else None,
                                         "correct_rate": r3(c["correct"] / c["frames"]) if c["frames"] else None}
                            for (b, s), c in sorted(by_dist.items())}}


def eval_forward_hands(sweep: Path, bridge: Path, hold_s: float) -> dict:
    """FORWARD hand sweep (truth_sweep.csv with column hand; AUDIT.md section 9 item 15, declared before the run).

    Per hand: pan-tilt frames read as each command inside the sample windows, the FORWARD rate (FORWARD / all frames),
    STOP frames, and the strict 1.0 s hold result per sample. The rule: adopt the index finger if its FORWARD rate is
    at least the fist's and no index-finger frame is read STOP.
    """
    truth = read_csv(sweep / "truth_sweep.csv")
    if not truth or "hand" not in truth[0]:
        raise SystemExit(f"{sweep.name}: truth_sweep.csv has no hand column (not a ForwardHandSweep session)")
    frames = sorted(({"t": float(r["time_s"]), "read": r["gesture_read"] or "NONE"}
                     for r in read_csv(bridge / "perception.csv") if r["type"] == "frame_pan_tilt" and num(r["time_s"]) is not None),
                    key=lambda f: f["t"])
    ts = [f["t"] for f in frames]
    per = defaultdict(lambda: {"samples": 0, "reads": Counter(), "hold_strict": Counter(), "samples_with_stop": 0,
                               "samples_without_frames": 0})
    for t in truth:
        e = per[t["hand"]]
        win = frames[bisect.bisect_left(ts, float(t["t_start"])):bisect.bisect_right(ts, float(t["t_end"]))]
        e["samples"] += 1
        e["samples_without_frames"] += not win
        e["samples_with_stop"] += any(f["read"] == "STOP" for f in win)
        for f in win:
            e["reads"][f["read"]] += 1
        acc = hold_result(win, hold_s, 0.0)
        e["hold_strict"]["correct" if acc == "FORWARD" else "none" if acc is None else "wrong"] += 1
    out = {}
    for hand, e in sorted(per.items()):
        n = sum(e["reads"].values())
        out[hand] = {"samples": e["samples"], "frames": n, "reads": dict(e["reads"]),
                     "forward_rate": r3(e["reads"]["FORWARD"] / n) if n else None,
                     "coverage": r3((n - e["reads"]["NONE"]) / n) if n else None,
                     "stop_frames": e["reads"]["STOP"], "samples_with_stop": e["samples_with_stop"],
                     "samples_without_frames": e["samples_without_frames"], "hold_strict": dict(e["hold_strict"])}
    fi, fs = out.get("index_finger"), out.get("fist")
    if fi and fs and fi["forward_rate"] is not None and fs["forward_rate"] is not None:
        at_least = e_rate(fi) >= e_rate(fs)
        never_stop = fi["stop_frames"] == 0
        decision = "adopt index_finger" if at_least and never_stop else "keep fist"
    else:
        at_least = never_stop = None
        decision = "not_evaluated (a hand has no frames)"
    return {"per_hand": out, "hold_s": hold_s, "rule": {"finger_forward_rate_at_least_fist": at_least,
                                                         "finger_never_read_stop": never_stop, "decision": decision}}


def e_rate(e: dict) -> float:
    """Unrounded FORWARD rate, so the comparison is not decided by rounding."""
    return e["reads"].get("FORWARD", 0) / e["frames"]


# ---------------------------------------------------------------- people

def eval_people(trials: Path, bridge: Path, ev: dict) -> dict:
    truth = []
    for p in sorted(trials.glob("truth_run*.csv")):
        truth += read_csv(p)
    truth.sort(key=lambda r: float(r["time_s"]))
    tt = [float(r["time_s"]) for r in truth]
    edges = ev["distance_bins_m"]
    bins = {f"{a}-{b} m": Counter() for a, b in zip(edges, edges[1:])}
    errors = defaultdict(list)
    elig = det = fp = known = frames = 0
    for r in read_csv(bridge / "perception.csv"):
        if r["type"] != "frame_360" or num(r["time_s"]) is None or not truth:
            continue
        t = float(r["time_s"])
        i = bisect.bisect_left(tt, t)
        j = min((k for k in (i - 1, i) if 0 <= k < len(tt)), key=lambda k: abs(tt[k] - t))
        if abs(tt[j] - t) > ev["truth_join_max_s"]:
            continue
        frames += 1
        g = truth[j]
        rx, rz, yaw = float(r["pose_x"]), float(r["pose_z"]), float(r["yaw_deg"])
        wx, wz = float(g["worker_x"]), float(g["worker_z"])
        d_true = math.hypot(wx - rx, wz - rz)
        b_true = hc.wrap(hc.yaw_to(rx, rz, wx, wz) - yaw)
        people = json.loads(r["people_json"]) if r.get("people_json") else []
        best = None
        for q in people:
            diff = abs(hc.wrap(q["bearing_deg"] - b_true))
            if diff <= ev["match_bearing_deg"] and (best is None or diff < best[0]):
                best = (diff, q)
        fp += len(people) - (1 if best else 0)
        if d_true > ev["detection_range_m"]:
            continue
        elig += 1
        key = next((k for k, (a, b) in zip(bins, zip(edges, edges[1:])) if a <= d_true < b), None)
        if key:
            bins[key]["eligible"] += 1
        if best:
            det += 1
            if key:
                bins[key]["detected"] += 1
            q = best[1]
            if q.get("distance_m", -1) >= 0:
                known += 1
                errors[q["distance_source"]].append(q["distance_m"] - d_true)
                errors["all"].append(q["distance_m"] - d_true)
    dist = {}
    for src, e in errors.items():
        a = [abs(x) for x in e]
        dist[src] = {"n": len(e), "mean_signed_m": r3(st.fmean(e)), "median_abs_m": r3(st.median(a)),
                     "p90_abs_m": r3(pct(a, 0.9)), "max_abs_m": r3(max(a))}
    return {"frames_joined": frames, "frames_eligible": elig, "frames_detected": det,
            "detection_rate": r3(det / elig) if elig else None,
            "by_distance": {k: {"eligible": c["eligible"], "recall": r3(c["detected"] / c["eligible"]) if c["eligible"] else None}
                            for k, c in bins.items()},
            "distance_error": dist, "distance_coverage": r3(known / det) if det else None,
            "false_positive_people_per_frame": r3(fp / frames) if frames else None}


def eval_trials(trials: Path, bridge: Path) -> dict:
    runs = [json.loads(p.read_text(encoding="utf-8")) for p in sorted(trials.glob("truth_run*.json"))]
    out = {"trials": len(runs), "successes": sum(r["outcome"] == "SUCCESS" for r in runs),
           "failures": dict(Counter(r["failure_reason"] for r in runs if r["outcome"] != "SUCCESS"))}
    scans, asks, junction = [], Counter(), Counter()
    for r in runs:
        py = bridge / f"python_trial_{r['trial']:03d}.json"
        if not py.exists():
            continue
        s = json.loads(py.read_text(encoding="utf-8"))
        tr = [(float(x.split(":")[0]), x.split(":")[1]) for x in s.get("trace", [])]
        for (t0, a), (t1, b) in zip(tr, tr[1:]):
            if a == "scan":
                scans.append(t1 - t0)
        shown = {x["junction"]: x["shown"] for x in r.get("shown", [])}
        for j in s.get("junctions", []):
            asks[j["asks"]] += 1
            junction["correct" if j["read"] == shown.get(j["junction"]) else "NONE" if j["read"] == "NONE" else "wrong direction"] += 1
    out.update(scan_s={"n": len(scans), "mean": r3(st.fmean(scans)) if scans else None, "max": r3(max(scans)) if scans else None},
               asks_per_junction=dict(asks), junction_reads=dict(junction))
    return out


def eval_timing(bridges: list[Path]) -> dict:
    per = defaultdict(list)
    for b in bridges:
        for r in read_csv(b / "perception.csv"):
            if num(r.get("decode_ms")) is not None:
                per["jpeg_decode"].append(float(r["decode_ms"]))
            for part in (r.get("model_ms") or "").split(";"):
                if ":" in part:
                    k, v = part.rsplit(":", 1)
                    per[k].append(float(v))
            if num(r.get("total_ms")) is not None:
                per[f"total ({r['type']})"].append(float(r["total_ms"]))
    return {k: {"n": len(v), "mean": r3(st.fmean(v)), "p50": r3(pct(v, 0.5)), "p95": r3(pct(v, 0.95)), "max": r3(max(v))}
            for k, v in sorted(per.items()) if v}


# ---------------------------------------------------------------- simulation with the measured rates

def simulate(gest: dict | None, people: dict | None, n: int) -> dict:
    import hri_sim as hs
    road = hc.Roadmap(hc.load_json("configs/roadmap.json"))
    cov = {c: gest["per_command"][c]["coverage"] for c in DIRECTIONS} if gest else {}
    acc = {c: gest["per_command"][c]["accuracy"] or 0.0 for c in DIRECTIONS} if gest else {}
    p_det = people["detection_rate"] if people and people["detection_rate"] is not None else 1.0
    err = (people or {}).get("distance_error", {}).get("all", {})
    goals = [road.endpoints()[i % 4] for i in range(n)]
    out = {}
    for name, p, gap in (("perfect", 1.0, 0.3), ("measured, tolerant hold", p_det, 0.3), ("measured, strict hold", p_det, 0.0),
                         ("perfect people, measured gestures, strict hold", 1.0, 0.0)):
        ok = 0
        reasons = Counter()
        for i, g in enumerate(goals):
            c = hc.make_controller()
            c.dialog.max_none_gap_s = gap
            r = hs.Simulator(c, hs.SimConfig(p_detect=p, coverage=cov if p < 1.0 or "measured" in name else {},
                                             accuracy=acc if "measured" in name else {}, distance_bias_m=err.get("mean_signed_m") or 0.0,
                                             distance_sigma_m=0.2), seed=100 + i).run(g)
            ok += r["outcome"] == "SUCCESS"
            reasons[r["failure_reason"]] += 1
        out[name] = {"p_detect": p, "max_none_gap_s": gap, "success": f"{ok}/{n}", "ratio": round(ok / n, 3), "reasons": dict(reasons)}
    return out


# ---------------------------------------------------------------- report

def markdown(rep: dict) -> str:
    L = ["# Development evaluation, vision mode (dev seed only)", "",
         "Accuracy = correct / frames with a command; coverage = frames with a command / all frames of that command.", ""]
    g = rep.get("gestures")
    if g:
        L += [f"## Gestures ({g['samples']} sweep samples, {g['frames']} pan-tilt frames)", "",
              "| shown | frames | coverage | accuracy | 1.0 s hold strict: correct / wrong / none | tolerant (gap "
              f"{g['tolerant_gap_s']} s) |", "|---|---|---|---|---|---|"]
        for c, v in g["per_command"].items():
            hs_, ht = v["hold_strict"], v["hold_tolerant"]
            if c in ("NONE", "STOP"):
                cov = f"false command rate {v['false_command_rate']}" if c == "NONE" else v["coverage"]
                L.append(f"| {c} | {v['frames']} | {cov} | {v.get('accuracy', '-')} | false accepts {hs_.get('false_accept', 0)}/{v['samples']} "
                         f"| false accepts {ht.get('false_accept', 0)}/{v['samples']} |")
            else:
                L.append(f"| {c} | {v['frames']} | {v['coverage']} | {v['accuracy']} | {hs_.get('correct', 0)} / {hs_.get('wrong', 0)} / "
                         f"{hs_.get('none', 0)} of {v['samples']} | {ht.get('correct', 0)} / {ht.get('wrong', 0)} / {ht.get('none', 0)} |")
        L += ["", "| shown \\ read | " + " | ".join(COMMANDS) + " |", "|---|" + "---|" * len(COMMANDS)]
        for c in COMMANDS:
            L.append(f"| {c} | " + " | ".join(str(g["confusion"][c].get(x, 0)) for x in COMMANDS) + " |")
        L.append("")
    fh = rep.get("forward_hands")
    if fh:
        L += ["## FORWARD hand sweep (AUDIT.md section 9 item 15)", "",
              "| hand | samples | frames | FORWARD rate | coverage | STOP frames | samples with STOP | reads | 1.0 s hold strict |",
              "|---|---|---|---|---|---|---|---|---|"]
        for h, v in fh["per_hand"].items():
            L.append(f"| {h} | {v['samples']} | {v['frames']} | {v['forward_rate']} | {v['coverage']} | {v['stop_frames']} | "
                     f"{v['samples_with_stop']} | {v['reads']} | {v['hold_strict']} |")
        r = fh["rule"]
        L += ["", f"Rule: finger FORWARD rate >= fist: {r['finger_forward_rate_at_least_fist']}; finger never read STOP: "
              f"{r['finger_never_read_stop']}; decision: **{r['decision']}**.", ""]
    p = rep.get("people")
    if p:
        L += ["## People on the 360 deg camera (trials)", "",
              f"Detection rate {p['detection_rate']} ({p['frames_detected']}/{p['frames_eligible']} frames with the worker within "
              f"range); false-positive people per frame {p['false_positive_people_per_frame']}; distance known for "
              f"{p['distance_coverage']} of matched frames.", "", "| distance | eligible | recall |", "|---|---|---|"]
        L += [f"| {k} | {v['eligible']} | {v['recall']} |" for k, v in p["by_distance"].items()]
        L += ["", "| source | n | mean signed m | median abs m | p90 abs m |", "|---|---|---|---|---|"]
        L += [f"| {k} | {v['n']} | {v['mean_signed_m']} | {v['median_abs_m']} | {v['p90_abs_m']} |" for k, v in p["distance_error"].items()]
        L.append("")
    t = rep.get("trials")
    if t:
        L += ["## Trials (vision decisions)", "", f"{t['successes']}/{t['trials']} SUCCESS; failures {t['failures'] or 'none'}; "
              f"junction reads {t['junction_reads']}; asks per junction {t['asks_per_junction']}; scan duration {t['scan_s']}.", ""]
    if rep.get("timing"):
        L += ["## Inference time (ms)", "", "| model | n | mean | p50 | p95 | max |", "|---|---|---|---|---|---|"]
        L += [f"| {k} | {v['n']} | {v['mean']} | {v['p50']} | {v['p95']} | {v['max']} |" for k, v in rep["timing"].items()]
        L.append("")
    if rep.get("simulation"):
        L += ["## Simulation with the measured rates (hri_sim.py; simulation, not Unity)", "", "| setting | success | reasons |", "|---|---|---|"]
        L += [f"| {k} | {v['success']} | {v['reasons']} |" for k, v in rep["simulation"].items()]
        L.append("")
    return "\n".join(L) + "\n"


def main(argv=None) -> None:
    import decision_io as dio
    import hri_perception as hpm

    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--sweep", nargs=2, metavar=("UNITY_SWEEP", "BRIDGE_RUN"))
    ap.add_argument("--trials", nargs=2, metavar=("UNITY_TRIALS", "BRIDGE_RUN"))
    ap.add_argument("--forward-hands", nargs=2, metavar=("UNITY_HAND_SWEEP", "BRIDGE_RUN"),
                    help="FORWARD fist vs index finger sweep (forward_hand_sweep_development_*)")
    ap.add_argument("--simulate", type=int, default=0, help="simulated trials per setting with the measured rates")
    a = ap.parse_args(argv)
    if not a.sweep and not a.trials and not a.forward_hands:
        raise SystemExit("give --sweep, --trials and/or --forward-hands")
    ev = hpm.load_config()["evaluation"]
    ctl = hc.load_json("configs/hri_control.json")["dialog"]
    rep, inputs, bridges = {"label": "vision"}, {}, []
    if a.sweep:
        s, b = dio.resolve(a.sweep[0]), dio.resolve(a.sweep[1])
        inputs["sweep"] = {"unity": s.name, "bridge": b.name, "session": guard_development(s)}
        rep["gestures"] = eval_gestures(s, b, ctl["gesture_hold_s"], ctl.get("max_none_gap_s", 0.3))
        bridges.append(b)
    if a.forward_hands:
        s, b = dio.resolve(a.forward_hands[0]), dio.resolve(a.forward_hands[1])
        inputs["forward_hands"] = {"unity": s.name, "bridge": b.name, "session": guard_development(s)}
        rep["forward_hands"] = eval_forward_hands(s, b, ctl["gesture_hold_s"])
        if b not in bridges:
            bridges.append(b)
    if a.trials:
        s, b = dio.resolve(a.trials[0]), dio.resolve(a.trials[1])
        inputs["trials"] = {"unity": s.name, "bridge": b.name, "session": guard_development(s)}
        rep["people"] = eval_people(s, b, ev)
        rep["trials"] = eval_trials(s, b)
        if b not in bridges:
            bridges.append(b)
    rep["timing"] = eval_timing(bridges)
    if a.simulate:
        rep["simulation"] = simulate(rep.get("gestures"), rep.get("people"), a.simulate)
    rep["inputs"] = inputs
    out = dio.new_run_dir({"paths": {"output_root": "outputs"}}, "hri_dev_eval")
    (out / "config_used").mkdir()
    for f in ("configs/hri_perception.json", "configs/gesture_hri.json", "configs/hri_control.json", "configs/roadmap.json"):
        (out / "config_used" / Path(f).name).write_bytes(dio.resolve(f).read_bytes())
    dio.write_json(out / "report.json", rep)
    dio.write_json(out / "run.json", {"git": dio.git_info(), "inputs": inputs})
    (out / "report.md").write_text(markdown(rep), encoding="utf-8")
    print(markdown(rep))
    print(f"Folder: {out.relative_to(HERE) if out.is_relative_to(HERE) else out}")


if __name__ == "__main__":
    main()
