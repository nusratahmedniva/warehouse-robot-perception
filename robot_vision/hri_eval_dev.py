"""Step 4 DEVELOPMENT evaluation of the vision perception (dev seed only; never the final seed).

The only module that reads ground truth: Unity's truth_sweep.csv / truth_run###.csv (true worker position, scripted
gesture). Inference (hri_perception.py, hri_bridge_server.py) never imports this module (tests check it).

Inputs (pairs: a Unity session folder and the bridge connection folder that served it):
    --sweep  <gestures_sweep_development_...>  <bridge_.../conn_###>   gesture accuracy, confusion, hold acceptance
    --trials <trials_development_Task2_...>     <bridge_.../conn_###>   people recall, distance error, trial outcomes
Inference times come from every bridge folder given. Criteria: configs/hri_perception.json -> evaluation.

Output: a new folder <output_root>/hri_dev_eval_<date>_<time>/ with report.json, report.md, gesture_confusion.csv,
gesture_per_command.csv, people_by_distance.csv, the configs used and run.json (git commit).

Usage (from robot_vision/):
    .venv python hri_eval_dev.py --sweep outputs/gestures_sweep_development_X outputs/bridge_Y/conn_001 \
                                 --trials outputs/trials_development_Task2_Z outputs/bridge_W/conn_001
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import statistics as st
from collections import Counter, defaultdict
from pathlib import Path

import hri_perception as hpm

HERE = Path(__file__).resolve().parent
COMMANDS = ["NONE", "LEFT", "FORWARD_LEFT", "FORWARD", "FORWARD_RIGHT", "RIGHT", "STOP"]
DIRECTIONS = ["LEFT", "FORWARD_LEFT", "FORWARD", "FORWARD_RIGHT", "RIGHT"]


def read_csv(p: Path) -> list[dict]:
    with p.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def fnum(x, default=None):
    try:
        return float(x)
    except (TypeError, ValueError):
        return default


def unity_config(session: Path) -> dict:
    cfg = json.loads((session / "hri_config.json").read_text(encoding="utf-8"))
    local = session / "hri_config.local.json"
    if local.exists():
        _merge(cfg, json.loads(local.read_text(encoding="utf-8")))
    return cfg


def _merge(base: dict, over: dict) -> None:
    for k, v in over.items():
        if isinstance(v, dict) and isinstance(base.get(k), dict):
            _merge(base[k], v)
        else:
            base[k] = v


def guard_development(session: Path) -> dict:
    """Refuse anything but a development session on the dev seed."""
    info = json.loads((session / "session.json").read_text(encoding="utf-8"))
    cfg = unity_config(session)
    if info.get("mode") != "development" or cfg["trials"].get("mode", "development") != "development":
        raise SystemExit(f"{session.name}: not a development session; this script never evaluates final runs")
    if info.get("seed") != cfg["trials"]["dev_seed"] or info.get("seed") == cfg["trials"]["final_seed"]:
        raise SystemExit(f"{session.name}: seed {info.get('seed')} is not the dev seed {cfg['trials']['dev_seed']}")
    return info


def frames(conn: Path) -> tuple[list[dict], int]:
    rows = read_csv(conn / "frames.csv")
    obs = [r for r in rows if r["type"] == "observation" and fnum(r["t_sim"]) is not None]
    for r in obs:
        r["t_sim_f"] = float(r["t_sim"])
    obs.sort(key=lambda r: r["t_sim_f"])
    return obs, sum(1 for r in rows if r["type"] == "observation_skipped")


def pct(values, q):
    v = sorted(values)
    if not v:
        return None
    k = (len(v) - 1) * q
    lo, hi = math.floor(k), math.ceil(k)
    return v[lo] + (v[hi] - v[lo]) * (k - lo)


def r3(x):
    return round(x, 3) if isinstance(x, (int, float)) and x is not None else x


# ---------------------------------------------------------------- gestures (sweep)

def hold_accept(window: list[dict], hold_s: float) -> str | None:
    """The first command (not NONE) read continuously for hold_s within the window, like RobotBrain's dialog."""
    start = None
    for i, r in enumerate(window):
        cmd = r["gesture_read"]
        if start is None or cmd != window[start]["gesture_read"]:
            start = i
        if cmd != "NONE" and r["t_sim_f"] - window[start]["t_sim_f"] >= hold_s - 1e-6:
            return cmd
    return None


def eval_gestures(sweep: Path, conn: Path, ev: dict) -> dict:
    truth = read_csv(sweep / "truth_sweep.csv")
    obs, _ = frames(conn)
    conf = {s: Counter() for s in COMMANDS}
    by_bin = defaultdict(lambda: Counter())
    samples = {s: Counter() for s in COMMANDS}
    for t in truth:
        shown, t0, t1, d = t["gesture_shown"], float(t["t_start"]), float(t["t_end"]), float(t["distance_m"])
        win = [r for r in obs if t0 <= r["t_sim_f"] <= t1]
        b = "1.7-2.1 m" if d < 2.1 else "2.1-2.5 m"
        for r in win:
            conf[shown][r["gesture_read"]] += 1
            by_bin[(b, shown)]["frames"] += 1
            by_bin[(b, shown)]["covered"] += r["gesture_read"] != "NONE"
            by_bin[(b, shown)]["correct"] += r["gesture_read"] == shown
        acc = hold_accept(win, ev["hold_s"])
        samples[shown]["n"] += 1
        samples[shown]["frames"] += len(win)
        if shown == "NONE":
            samples[shown]["correct" if acc is None else "wrong"] += 1
        else:
            samples[shown]["correct" if acc == shown else "wrong" if acc is not None else "unaccepted"] += 1
    per_cmd = {}
    for s in COMMANDS:
        n = sum(conf[s].values())
        covered = n - conf[s]["NONE"]
        correct = conf[s][s]
        if s == "NONE":
            per_cmd[s] = {"frames": n, "false_command_rate": r3(covered / n) if n else None,
                          "samples": samples[s]["n"], "samples_without_false_accept": samples[s]["correct"]}
        else:
            per_cmd[s] = {"frames": n, "coverage": r3(covered / n) if n else None,
                          "accuracy": r3(correct / covered) if covered else None,
                          "correct_rate": r3(correct / n) if n else None,
                          "samples": samples[s]["n"], "samples_accepted_correct": samples[s]["correct"],
                          "samples_accepted_wrong": samples[s]["wrong"], "samples_not_accepted": samples[s]["unaccepted"]}
    rel = ev["diagonals_reliable_if"]
    diag = {d: per_cmd[d] for d in ("FORWARD_LEFT", "FORWARD_RIGHT")}
    ok = all(v["accuracy"] is not None and v["accuracy"] >= rel["accuracy_min"] and
             v["coverage"] is not None and v["coverage"] >= rel["coverage_min"] for v in diag.values())
    bins = {f"{b} {s}": {"frames": c["frames"], "coverage": r3((c["covered"] / c["frames"]) if c["frames"] else None),
                         "correct_rate": r3((c["correct"] / c["frames"]) if c["frames"] else None)}
            for (b, s), c in sorted(by_bin.items())}
    return {"confusion": {s: dict(conf[s]) for s in COMMANDS}, "per_command": per_cmd, "by_distance": bins,
            "diagonals_reliable": ok, "diagonals_criterion": rel, "samples_total": len(truth)}


# ---------------------------------------------------------------- people (trials and sweep)

def eval_people(session: Path, conn: Path, ev: dict, truth_glob: str) -> dict:
    truth = []
    for p in sorted(session.glob(truth_glob)):
        truth += read_csv(p)
    for t in truth:
        t["t_sim_f"] = float(t["t_sim"])
    truth.sort(key=lambda t: t["t_sim_f"])
    ts = [t["t_sim_f"] for t in truth]
    obs, _ = frames(conn)
    import bisect
    edges = ev["distance_bins_m"]
    bins = {f"{a}-{b} m": Counter() for a, b in zip(edges, edges[1:])}
    errors = defaultdict(list)
    eligible = detected = fp = 0
    known = 0
    for r in obs:
        if not truth:
            break
        i = bisect.bisect_left(ts, r["t_sim_f"])
        cand = [j for j in (i - 1, i) if 0 <= j < len(ts)]
        j = min(cand, key=lambda j: abs(ts[j] - r["t_sim_f"]))
        if abs(ts[j] - r["t_sim_f"]) > ev["truth_join_max_s"]:
            continue
        t = truth[j]
        rx, rz, hd = fnum(r["robot_x"]), fnum(r["robot_z"]), fnum(r["heading_deg"])
        wx, wz = float(t["worker_x"]), float(t["worker_z"])
        d_true = math.hypot(wx - rx, wz - rz)
        b_true = (math.degrees(math.atan2(wx - rx, wz - rz)) - hd + 180.0) % 360.0 - 180.0
        people = json.loads(r["people_json"]) if r.get("people_json") else []
        best = None
        for q in people:
            diff = abs((q["bearing_deg"] - b_true + 180.0) % 360.0 - 180.0)
            if diff <= ev["match_bearing_deg"] and (best is None or diff < best[0]):
                best = (diff, q)
        fp += len(people) - (1 if best else 0)
        if d_true > ev["detection_range_m"]:
            continue
        eligible += 1
        key = next((k for k, (a, b) in zip(bins, zip(edges, edges[1:])) if a <= d_true < b), None)
        if key:
            bins[key]["eligible"] += 1
        if best:
            detected += 1
            if key:
                bins[key]["detected"] += 1
            q = best[1]
            if q["distance_m"] is not None and q["distance_m"] >= 0:
                known += 1
                errors[q["distance_source"]].append(q["distance_m"] - d_true)
                errors["all"].append(q["distance_m"] - d_true)
    dist = {}
    for src, e in errors.items():
        a = [abs(x) for x in e]
        dist[src] = {"n": len(e), "mean_signed_m": r3(st.mean(e)), "median_abs_m": r3(st.median(a)),
                     "p90_abs_m": r3(pct(a, 0.9)), "max_abs_m": r3(max(a))}
    return {"frames_eligible": eligible, "frames_detected": detected,
            "recall": r3(detected / eligible) if eligible else None,
            "by_distance": {k: {"eligible": c["eligible"], "recall": r3(c["detected"] / c["eligible"]) if c["eligible"] else None}
                            for k, c in bins.items()},
            "distance_error": dist,
            "distance_coverage": r3(known / detected) if detected else None,
            "false_positive_people_per_frame": r3(fp / len(obs)) if obs else None}


# ---------------------------------------------------------------- timing and outcomes

def eval_timing(conns: list[Path]) -> dict:
    per = defaultdict(list)
    totals, skipped, answered = [], 0, 0
    for c in conns:
        obs, sk = frames(c)
        skipped += sk
        answered += len(obs)
        for r in obs:
            if fnum(r["inference_total_ms"]) is not None:
                totals.append(float(r["inference_total_ms"]))
            for part in (r.get("model_ms") or "").split(";"):
                if ":" in part:
                    name, ms = part.rsplit(":", 1)
                    per[name].append(float(ms))

    def summ(v):
        return {"n": len(v), "mean": r3(st.mean(v)), "p50": r3(pct(v, 0.5)), "p95": r3(pct(v, 0.95)), "max": r3(max(v))} if v else None
    return {"per_model_ms": {k: summ(v) for k, v in sorted(per.items())}, "total_ms": summ(totals),
            "observations_answered": answered, "observations_skipped": skipped}


def eval_trials(session: Path) -> dict:
    rows = read_csv(session / "results.csv")
    runs = [json.loads(p.read_text(encoding="utf-8")) for p in sorted(session.glob("run_*.json"))]
    junctions = Counter()
    for r in runs:
        for j in r.get("junctions", []):
            junctions["correct" if j["read"] == j["shown"] else "wrong"] += 1
    rtt = [r["round_trip_mean_ms"] for r in runs if r.get("round_trip_mean_ms", -1) >= 0]
    return {"trials": len(rows), "successes": sum(r["outcome"] == "SUCCESS" for r in rows),
            "failure_reasons": dict(Counter(r["failure_reason"] for r in rows if r["outcome"] != "SUCCESS")),
            "perception_mode": sorted({r.get("perception_mode", "") for r in runs}),
            "junction_reads": dict(junctions), "round_trip_mean_ms_per_trial": [r3(x) for x in rtt]}


# ---------------------------------------------------------------- report

def write_outputs(out: Path, report: dict) -> None:
    (out / "report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    g = report.get("gestures")
    if g:
        with (out / "gesture_confusion.csv").open("w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["shown \\ read"] + COMMANDS)
            for s in COMMANDS:
                w.writerow([s] + [g["confusion"][s].get(c, 0) for c in COMMANDS])
        with (out / "gesture_per_command.csv").open("w", newline="", encoding="utf-8") as f:
            keys = sorted({k for v in g["per_command"].values() for k in v})
            w = csv.writer(f)
            w.writerow(["command"] + keys)
            for s, v in g["per_command"].items():
                w.writerow([s] + [v.get(k, "") for k in keys])
    p = report.get("people_trials")
    if p:
        with (out / "people_by_distance.csv").open("w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["distance_bin", "eligible_frames", "recall"])
            for k, v in p["by_distance"].items():
                w.writerow([k, v["eligible"], v["recall"]])
    (out / "report.md").write_text(markdown(report), encoding="utf-8")


def markdown(rep: dict) -> str:
    L = [f"# Step 4 development evaluation ({rep['label']})", "",
         "Dev seed only. Accuracy is always given with its coverage. Truth: Unity truth files (evaluation only).", ""]
    g = rep.get("gestures")
    if g:
        L += ["## Gestures (gesture sweep, per frame)", "",
              "| shown | frames | coverage | accuracy | samples: accepted correct / wrong / not accepted |", "|---|---|---|---|---|"]
        for s, v in g["per_command"].items():
            if s == "NONE":
                L.append(f"| NONE | {v['frames']} | false command rate {v['false_command_rate']} | - | "
                         f"{v['samples_without_false_accept']}/{v['samples']} without a false accept |")
            else:
                L.append(f"| {s} | {v['frames']} | {v['coverage']} | {v['accuracy']} | "
                         f"{v['samples_accepted_correct']} / {v['samples_accepted_wrong']} / {v['samples_not_accepted']} of {v['samples']} |")
        L += ["", "Confusion (rows shown, columns read):", "", "| | " + " | ".join(COMMANDS) + " |",
              "|---|" + "---|" * len(COMMANDS)]
        for s in COMMANDS:
            L.append(f"| {s} | " + " | ".join(str(g["confusion"][s].get(c, 0)) for c in COMMANDS) + " |")
        L += ["", f"Diagonals reliable (accuracy >= {g['diagonals_criterion']['accuracy_min']} and coverage >= "
                  f"{g['diagonals_criterion']['coverage_min']}): **{g['diagonals_reliable']}**", ""]
    for key, title in (("people_trials", "People on the 360 deg camera (trials)"),):
        p = rep.get(key)
        if p:
            L += [f"## {title}", "", f"Recall {p['recall']} ({p['frames_detected']}/{p['frames_eligible']} frames within range); "
                  f"distance known for {p['distance_coverage']} of matched; false-positive people per frame {p['false_positive_people_per_frame']}.", ""]
            L += ["| distance bin | eligible | recall |", "|---|---|---|"] + [f"| {k} | {v['eligible']} | {v['recall']} |" for k, v in p["by_distance"].items()]
            L += ["", "| distance source | n | mean signed error m | median abs m | p90 abs m |", "|---|---|---|---|---|"]
            L += [f"| {k} | {v['n']} | {v['mean_signed_m']} | {v['median_abs_m']} | {v['p90_abs_m']} |" for k, v in p["distance_error"].items()]
            L.append("")
    t = rep.get("timing")
    if t:
        L += ["## Inference time (Python side, ms)", "", "| model | n | mean | p50 | p95 | max |", "|---|---|---|---|---|---|"]
        for k, v in list(t["per_model_ms"].items()) + [("total", t["total_ms"])]:
            if v:
                L.append(f"| {k} | {v['n']} | {v['mean']} | {v['p50']} | {v['p95']} | {v['max']} |")
        L += ["", f"Observations answered {t['observations_answered']}, skipped as stale {t['observations_skipped']}.", ""]
    tr = rep.get("trials")
    if tr:
        L += ["## Trials (vision decisions)", "", f"{tr['successes']}/{tr['trials']} SUCCESS; failures {tr['failure_reasons']}; "
              f"junction reads {tr['junction_reads']}; mode {tr['perception_mode']}.", ""]
    return "\n".join(L) + "\n"


def main() -> None:
    import decision_io as dio

    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", default=str(hpm.DEFAULT_CONFIG))
    ap.add_argument("--sweep", nargs=2, metavar=("UNITY_SWEEP_DIR", "BRIDGE_CONN_DIR"))
    ap.add_argument("--trials", nargs=2, metavar=("UNITY_TRIALS_DIR", "BRIDGE_CONN_DIR"))
    a = ap.parse_args()
    if not a.sweep and not a.trials:
        raise SystemExit("give --sweep and/or --trials")
    cfg_path = Path(a.config)
    cfg = hpm.load_config(cfg_path)
    ev = cfg["evaluation"]
    report = {"label": "vision", "inputs": {}}
    conns = []
    if a.sweep:
        s, c = Path(a.sweep[0]), Path(a.sweep[1])
        report["inputs"]["sweep"] = {"session": s.name, "bridge": f"{c.parent.name}/{c.name}", "session_info": guard_development(s)}
        report["gestures"] = eval_gestures(s, c, ev)
        conns.append(c)
    if a.trials:
        s, c = Path(a.trials[0]), Path(a.trials[1])
        report["inputs"]["trials"] = {"session": s.name, "bridge": f"{c.parent.name}/{c.name}", "session_info": guard_development(s)}
        report["people_trials"] = eval_people(s, c, ev, "truth_run*.csv")
        report["trials"] = eval_trials(s)
        conns.append(c)
    report["timing"] = eval_timing(conns)
    out = dio.new_run_dir(cfg, "hri_dev_eval")
    used = [cfg_path, hpm.resolve(cfg["stop"]["adapter_config"]), HERE / "configs" / "bridge.json"]
    hashes = dio.copy_configs(out, used)
    for key in ("sweep", "trials"):
        sess = getattr(a, key)
        if sess:
            for name in ("hri_config.json", "hri_config.local.json"):
                src = Path(sess[0]) / name
                if src.exists():
                    (out / "config_used" / f"unity_{key}_{name}").write_bytes(src.read_bytes())
    dio.write_json(out / "run.json", {"git": dio.git_info(), "config_sha256": hashes, "inputs": report["inputs"],
                                      "perception_config_frozen": cfg.get("frozen")})
    write_outputs(out, report)
    print((out / "report.md").read_text(encoding="utf-8"))
    print(f"Report folder: {out.relative_to(HERE) if out.is_relative_to(HERE) else out}")


if __name__ == "__main__":
    main()
