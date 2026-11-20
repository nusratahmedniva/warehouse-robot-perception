"""Timing rerun report: the strict-protocol rerun of A2_left, A3 and B2_right (development, rehearsal mode, 3 runs each).

Avatar/Config/experiments_ab.md section 15 addendum 5, item 2 (measures declared there before any session ran). EVALUATION ONLY, read-only
on the session folders: it reads truth (truth.jsonl, for the run spans and the true/false STOP split, as step5_report.py) and the export of
Anisha's export_csv_v4.py (development mode). Never imported by inference code. Nothing is tuned on it.

Input: a JSON manifest {"sessions": [{"setting": "A2_left", "unity": "<trials_development_...>", "bridge": "<bridge_guide_...>",
"export": "<export_csv_v4_...>", "protocol": "<run_protocol_...txt>"}]}, paths relative to robot_vision/ (or absolute); or
robot_vision/outputs/step5_sessions.json itself, whose entries named timing_<setting> (step5_session_checks.ps1 -Setting timing_<setting>)
are used, with the protocol note read from each launcher transcript. Since addendum 8 (2026-11-20): --prefix P uses the entries named
P<final setting> instead (e.g. the step-5 sessions t0_A1 ... t0_B4_off); the output names carry P.
Output (never overwritten): robot_vision/outputs/timing_rerun_report_<time>.md, timing_rerun_<time>.json and the zip for Anisha
timing_rerun_logs_<time>.zip (its SHA-256 is printed). With an output folder given (a tool check) only the report is written, there.
Usage (from the repository root): robot_vision\\.venv\\Scripts\\python.exe finals_v4\\timing_rerun_report.py <manifest> [<output folder>] [--prefix P]
"""
from __future__ import annotations

import bisect
import csv
import json
import math
import statistics as st
import sys
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import step5_report as s5  # noqa: E402  (stop_episodes, truth_by_worker, rows, jload, num)

REPO = s5.REPO
RV, OUT = s5.RV, s5.OUT
GESTURE_STATES = ("ask", "read", "wait")
FLOOR, NOMINAL = 10, 12


def pct(v, q):
    if not v:
        return None
    s = sorted(v)
    k = (len(s) - 1) * q / 100.0
    lo, hi = math.floor(k), math.ceil(k)
    return s[lo] + (s[hi] - s[lo]) * (k - lo)


def dist(v):
    return {"n": len(v), "median": st.median(v) if v else None, "p10": pct(v, 10), "p95": pct(v, 95), "max": max(v) if v else None}


def lines(path: Path):
    with path.open(encoding="utf-8") as f:
        for ln in f:
            if ln.strip():
                yield json.loads(ln)


def run_spans(unity: Path) -> dict[int, tuple[float, float]]:
    spans = {}
    for d in sorted(unity.glob("run_*")):
        ts = [r["time_s"] for rs in s5.truth_by_worker(d).values() for r in rs]
        if ts:
            spans[int(d.name.split("_")[1])] = (min(ts), max(ts))
    return spans


def state_index(bridge: Path):
    """Per trial, the decisions.csv times and states (first word)."""
    idx = defaultdict(lambda: ([], []))
    for r in s5.rows(bridge / "decisions.csv"):
        t = int(r["trial"])
        if t > 0:
            idx[t][0].append(float(r["time_s"]))
            idx[t][1].append((r["state"].split(" ")[0], r.get("safety", "")))
    return idx


def state_at(idx, trial, t):
    ts, vs = idx.get(trial, ([], []))
    i = bisect.bisect_right(ts, t) - 1
    return vs[i] if i >= 0 else ("", "")


def window_counts(frames, spans, idx):
    """Anisha's B2: per frame within a run, the frames of the same camera in the 2.0 s ending at it, by the people in that frame."""
    per_run = defaultdict(list)
    for f in frames:
        for run, (lo, hi) in spans.items():
            if lo - 1e-6 <= f["time_s"] <= hi + 1e-6:
                per_run[run].append(f)
                break
    allw, gest = defaultdict(list), defaultdict(list)
    for run, fr in per_run.items():
        fr.sort(key=lambda f: f["time_s"])
        ts = [f["time_s"] for f in fr]
        for i, f in enumerate(fr):
            j = bisect.bisect_left(ts, f["time_s"] - 2.0)
            k = min(len(f["people"]), 3)
            allw[k].append(i + 1 - j)
            if state_at(idx, run, f["time_s"])[0] in GESTURE_STATES:
                gest[k].append(i + 1 - j)
    return allw, gest, {r: len(v) for r, v in per_run.items()}


def perception_times(bridge: Path):
    out = defaultdict(lambda: {"total": [], "decode": [], "model": [], "skipped": 0, "frames": 0, "by_people": defaultdict(list)})
    for r in s5.rows(bridge / "perception.csv"):
        o = out[r["type"]]
        o["frames"] += 1
        o["skipped"] += int(r["skipped_before"] or 0)
        tot = s5.num(r["total_ms"])
        if tot is None:
            continue
        o["total"].append(tot)
        o["decode"].append(s5.num(r["decode_ms"]) or 0.0)
        o["model"].append(sum(float(x.rsplit(":", 1)[1]) for x in r["model_ms"].split(";") if ":" in x))
        o["by_people"][min(int(r["n_people"] or 0), 3)].append(tot)
    return out


def proceed_floor(bridge: Path):
    """v4_log.jsonl: the PROCEED windows the reader passed, and those passed with fewer than 12 valid frames (only through the floor)."""
    passed, floor_only, valid_when_passed = 0, 0, []
    for r in lines(bridge / "v4_log.jsonl"):
        for p in r.get("persons", []):
            arms = ((p.get("reading") or {}).get("arms") or {})
            for a in arms.values():
                pr = (a or {}).get("proceed") or {}
                if pr.get("ok"):
                    passed += 1
                    valid_when_passed.append(pr.get("valid", 0))
                    floor_only += pr.get("valid", 0) < NOMINAL
    return {"passed_windows": passed, "passed_with_fewer_than_12": floor_only, "valid_when_passed": dist(valid_when_passed)}


def dialogs_proceed(export: Path):
    d = s5.rows(export / "dialogs.csv")
    pro = [r for r in d if r["command_shown"] == "PROCEED"]
    return {"asks": len(d), "proceed_asks": len(pro), "read": dict(Counter(r["command_read"] or "-" for r in pro)),
            "decision": dict(Counter(r["decision"] or "-" for r in pro)),
            "accepted": sum(1 for r in pro if r["decision"] == "accepted"),
            "accepted_as_proceed": sum(1 for r in pro if r["decision"] == "accepted" and r["command_read"] == "PROCEED")}


def person_in_path(bridge: Path):
    """Episodes of consecutive decisions.csv rows of one trial with a person-in-path safety stop."""
    eps, prev, prev_t = 0, False, None
    for r in s5.rows(bridge / "decisions.csv"):
        on = "person in path" in r.get("safety", "")
        t = int(r["trial"])
        if on and (not prev or t != prev_t):
            eps += 1
        prev, prev_t = on, t
    return eps


def recoveries(bridge: Path):
    ev = Counter()
    per = []
    for f in sorted(bridge.glob("python_trial_*.json")):
        t = s5.jload(f) or {}
        v4 = t.get("v4") or {}
        for d in v4.get("decisions", []):
            if str(d.get("event", "")).startswith("recovery"):
                ev[d["event"]] += 1
                per.append(f"trial {t.get('trial')}: t {d.get('t')} {d['event']}: {d.get('reason')}")
    return dict(ev), per


def timing(bridge: Path):
    s = s5.jload(bridge / "summary.json") or {}
    rt = s.get("round_trip", {})
    lag = s.get("event_loop_lag", {})
    res = s.get("resources", {})
    fr = s.get("frames", {})
    pc = s.get("perception", {})
    return {
        "watchdog_stops": s.get("watchdog", {}).get("stops_reported_by_unity"),
        "frame_stalls": s.get("watchdog", {}).get("unity_frame_stalls_reported_by_unity"),
        "round_trip_p95_ms": rt.get("p95_ms"), "round_trip_max_ms": rt.get("all_messages", {}).get("max_ms", rt.get("max_ms")),
        "loop_lag_p99_ms": lag.get("all_samples", {}).get("p99_ms"), "loop_lag_max_ms": lag.get("max_lag_ms"),
        "free_mem_min_mb": res.get("mem_available_mb", {}).get("min"), "hard_paging_max": res.get("hard_paging_per_s", {}).get("max"),
        "unity_drop": {k: fr.get(k, {}).get("drop_rate") for k in ("360", "pan_tilt")},
        "unity_sent": {k: fr.get(k, {}).get("sent_by_unity") for k in ("360", "pan_tilt")},
        "python_dropped": {k: (pc.get(k, {}).get("dropped"), pc.get(k, {}).get("processed")) for k in ("frame_360", "frame_pan_tilt")},
        "unity_frame_ms_p99": s.get("unity_frames", {}).get("frame_ms_p99"), "unity_frames_over_100ms": s.get("unity_frames", {}).get("frames_over_100ms"),
        "errors": len(s.get("errors", [])),
    }


def f(x, n=1):
    return "-" if x is None else (f"{x:.{n}f}" if isinstance(x, float) else str(x))


def wtable(title, w):
    L = [f"| {title} | n | median | p10 | share < 10 | share < 12 |", "|---|---|---|---|---|---|"]
    for k in sorted(w):
        v = w[k]
        L.append(f"| {'3+' if k == 3 else k} | {len(v)} | {f(st.median(v) if v else None)} | {f(pct(v, 10))} | "
                 f"{f(sum(x < FLOOR for x in v) / len(v), 3) if v else '-'} | {f(sum(x < NOMINAL for x in v) / len(v), 3) if v else '-'} |")
    return L


def from_step5(entries, prefix="timing_"):
    """step5_sessions.json as written by step5_session_checks.ps1: the entries named <prefix><setting> (timing_ by default; since addendum 8
    any prefix, e.g. t0_, with a final setting name after it), with the protocol note named in the launcher transcript ("protocol note: <path>")."""
    out = []
    for e in entries:
        if not e["setting"].startswith(prefix) or (prefix != "timing_" and e["setting"][len(prefix):] not in s5.SETTINGS):
            continue
        e = {**e, "setting": e["setting"][len(prefix):]}
        log = REPO / e.get("launcher_log", "") if e.get("launcher_log") else None
        if log is not None and not log.exists():
            log = s5.p(e["launcher_log"])
        if log is not None and log.exists() and "protocol" not in e:
            for ln in log.read_text(encoding="utf-8-sig").splitlines():
                if ln.strip().startswith("protocol note:"):
                    q = ln.split("protocol note:", 1)[1].strip().replace("\\", "/")
                    e["protocol"] = q if Path(q).is_absolute() else str(REPO / q)
        out.append(e)
    return out


def main(argv):
    argv, prefix = list(argv), None
    if "--prefix" in argv:                                 # addendum 8: the step-5 sessions of one setting prefix, e.g. --prefix t0_
        i = argv.index("--prefix")
        if i + 1 >= len(argv):
            raise SystemExit("--prefix needs a value, e.g. --prefix t0_")
        prefix = argv[i + 1]
        del argv[i:i + 2]
    man = Path(argv[1])
    entries = json.loads(man.read_text(encoding="utf-8-sig"))["sessions"]
    if prefix is not None:
        entries = from_step5(entries, prefix)
        if not entries:
            raise SystemExit(f"{man}: no session with the prefix '{prefix}' and a final setting name")
    elif any(e["setting"].startswith("timing_") for e in entries):
        entries = from_step5(entries)
    limits = json.loads((RV / "configs/v4/bridge.json").read_text(encoding="utf-8"))
    lim = next(v for k, v in limits.items() if isinstance(v, dict) and "loop_lag_max_ms" in v)
    stamp = (prefix or "") + datetime.now().strftime("%Y%m%d_%H%M%S")
    out = Path(argv[2]) if len(argv) > 2 else OUT          # a tool check writes elsewhere
    md_path, js_path = out / f"timing_rerun_report_{stamp}.md", out / f"timing_rerun_{stamp}.json"
    timeouts = sorted({str(e.get("timeout_s", "?")) for e in entries})
    what = ("experiments_ab.md section 15 addendum 5, item 2. Development data (rehearsal: dev seed 1, development looks and clips, 420 s). Not a result."
            if prefix is None else
            f"experiments_ab.md section 15 addendum 8: the step-5 sessions with the prefix '{prefix}'. Development data (rehearsal: dev seed 1, "
            f"development looks and clips, development timeout {', '.join(timeouts)} s). Not a result.")
    L = [f"# {'Strict-protocol timing rerun' if prefix is None else 'Step 5 timing'} ({stamp})", "", what,
         f"Limits (configs/v4/bridge.json): loop lag p99 {lim['loop_lag_p99_ms']} ms / max {lim['loop_lag_max_ms']} ms; round trip p99 "
         f"{lim['round_trip_p99_ms']} ms / max {lim['round_trip_max_ms']} ms.", ""]
    allres = {}
    for e in entries:
        stt, U, B, X = e["setting"], s5.p(e["unity"]), s5.p(e["bridge"]), s5.p(e["export"])
        spans, idx = run_spans(U), state_index(B)
        frames = list(lines(B / "model_outputs.jsonl"))
        pt = [fr for fr in frames if fr["cam"] == "pan_tilt"]
        c360 = [fr for fr in frames if fr["cam"] == "360"]
        w_pt, g_pt, n_pt = window_counts(pt, spans, idx)
        w_360, g_360, _ = window_counts(c360, spans, idx)
        pc = perception_times(B)
        tm = timing(B)
        pf = proceed_floor(B)
        dp = dialogs_proceed(X)
        stops = s5.stop_episodes(B, U, stt)
        pip = person_in_path(B)
        rec, rec_lines = recoveries(B)
        runs = s5.rows(X / "runs.csv")
        over = [k for k, v in (("loop lag max", tm["loop_lag_max_ms"] is not None and tm["loop_lag_max_ms"] > lim["loop_lag_max_ms"]),
                               ("loop lag p99", tm["loop_lag_p99_ms"] is not None and tm["loop_lag_p99_ms"] > lim["loop_lag_p99_ms"]),
                               ("round trip max", tm["round_trip_max_ms"] is not None and tm["round_trip_max_ms"] > lim["round_trip_max_ms"])) if v]
        proto = (s5.p(e["protocol"]).read_text(encoding="utf-8") if e.get("protocol") and s5.p(e["protocol"]).exists() else "")
        L += [f"## {stt}", "", f"Unity `{U.name}`, bridge `{B.name}`, export `{X.name}`", "",
              "Run protocol note:", "", "```", proto.strip(), "```", "",
              "| trial | goal | route | outcome | failure | time (s) | asks | dialogs |", "|---|---|---|---|---|---|---|---|"]
        L += [f"| {r['trial']} | {r['goal']} | {r['route']} | {r['outcome']} | {r['failure_reason']} | {f(s5.num(r['time_s']))} | {r['asks']} | {r['dialogs']} |" for r in runs]
        L += ["", "**Frames per 2 s window by people in the frame** (Anisha's B2 definition), pan-tilt, all frames of the runs:", ""]
        L += wtable("people (pan-tilt)", w_pt)
        L += ["", "Pan-tilt, gesture windows only (decisions.csv state ask / read / wait):", ""] + wtable("people (pan-tilt)", g_pt)
        L += ["", "360, all frames of the runs:", ""] + wtable("people (360)", w_360)
        L += ["", "**Frame drops:** " + "; ".join(
            f"{k}: Unity {f(tm['unity_drop'][k], 3)} of {tm['unity_sent'][k]} sent" for k in ("360", "pan_tilt")) + "; Python (replaced by a newer frame "
              "before its thread got to it): " + "; ".join(f"{k} {v[0]} of {(v[0] or 0) + (v[1] or 0)} ({f((v[0] or 0) / ((v[0] or 0) + (v[1] or 1)), 3)})"
                                                          for k, v in tm["python_dropped"].items()), ""]
        L += ["**Processing time per frame (ms)** (perception.csv):", "", "| camera | frames | total median | p95 | max | model median | decode median | Python skipped before |",
              "|---|---|---|---|---|---|---|---|"]
        for k, o in sorted(pc.items()):
            L.append(f"| {k} | {o['frames']} | {f(st.median(o['total']))} | {f(pct(o['total'], 95))} | {f(max(o['total']))} | {f(st.median(o['model']))} | "
                     f"{f(st.median(o['decode']))} | {o['skipped']} |")
        if "frame_pan_tilt" in pc:
            L += ["", "Pan-tilt total ms by people in the frame: " + "; ".join(
                f"{'3+' if k == 3 else k}: n {len(v)}, median {f(st.median(v))}, p95 {f(pct(v, 95))}" for k, v in sorted(pc['frame_pan_tilt']['by_people'].items()))]
        n_true = sum(s["true_stop"] for s in stops)
        L += ["", f"**PROCEED** (floor {FLOOR}): {dp['proceed_asks']} asks with PROCEED shown; read {dp['read']}; decisions {dp['decision']}; accepted "
              f"{dp['accepted']} (as PROCEED {dp['accepted_as_proceed']}). Reader windows passed: {pf['passed_windows']}, of them with fewer than 12 valid "
              f"frames (passed only through the floor): {pf['passed_with_fewer_than_12']}; valid frames when passed: median "
              f"{f(pf['valid_when_passed']['median'])}, p10 {f(pf['valid_when_passed']['p10'])}.",
              f"**Safety stops:** STOP gesture {len(stops)} (true {n_true}, false {len(stops) - n_true}); person in path {pip} episodes; recoveries "
              f"{rec or 'none'}.",
              f"**Timing:** watchdog stops {tm['watchdog_stops']} (frame stalls {tm['frame_stalls']}); round trip p95 {f(tm['round_trip_p95_ms'])} ms, max "
              f"{f(tm['round_trip_max_ms'])} ms; loop lag p99 {f(tm['loop_lag_p99_ms'])} ms, max {f(tm['loop_lag_max_ms'])} ms; free memory min "
              f"{f(tm['free_mem_min_mb'], 0)} MB; hard paging max {f(tm['hard_paging_max'], 0)} /s; Unity frame p99 {f(tm['unity_frame_ms_p99'])} ms "
              f"({tm['unity_frames_over_100ms']} frames over 100 ms); bridge errors {tm['errors']}. **Over a limit: {', '.join(over) if over else 'none'}.**", ""]
        L += [f"- recovery: {x}" for x in rec_lines]
        L += [f"- STOP trial {s['trial']} t {s['t_start_s']} s, {s['duration_s']} s, state {s['state']}: {'TRUE' if s['true_stop'] else 'FALSE'}; {s['shown']}"
              for s in stops]
        L.append("")
        allres[stt] = {"windows_pan_tilt": {k: dist(v) for k, v in w_pt.items()}, "gesture_windows_pan_tilt": {k: dist(v) for k, v in g_pt.items()},
                       "windows_360": {k: dist(v) for k, v in w_360.items()}, "pan_tilt_frames_per_run": n_pt,
                       "processing_ms": {k: {"total": dist(o["total"]), "model": dist(o["model"]), "decode": dist(o["decode"]), "skipped": o["skipped"],
                                             "frames": o["frames"], "total_by_people": {kk: dist(vv) for kk, vv in o["by_people"].items()}} for k, o in pc.items()},
                       "timing": tm, "over_limits": over, "proceed": {**dp, **pf}, "stops": {"stop_gesture": len(stops), "true": n_true,
                       "person_in_path_episodes": pip, "recoveries": rec}, "runs": runs}
    rule = allres.get("B2_right", {}).get("over_limits")
    L += ["## Anisha's rule (AUDIT.md 16.19.2 item 1)", "",
          "If B2_right still exceeds the limits, the active-avatar limit goes from 6 to 5: " +
          ("B2_right was not in this rerun." if rule is None else ("**B2_right exceeds: " + ", ".join(rule) + " -> the rule triggers** (not applied here)."
                                                               if rule else "B2_right exceeds no limit: the rule does not trigger.")), ""]
    with md_path.open("x", encoding="utf-8") as fh:
        fh.write("\n".join(L))
    with js_path.open("x", encoding="utf-8") as fh:
        json.dump({"created": stamp, "manifest": man.name, "settings": allres}, fh, indent=1, default=str)
    print(md_path)
    print(js_path)
    if len(argv) <= 2:                                     # the real run (not a tool check): the zip for Anisha
        print(make_zip(entries, [man, md_path, js_path], stamp))
    return 0


BRIDGE_FILES = ("decisions.csv", "model_outputs.jsonl", "v4_log.jsonl", "perception.csv", "summary.json", "resources.csv", "loop_lag.csv")


def make_zip(entries, extra, stamp):
    """robot_vision/outputs/timing_rerun_logs_<time>.zip (read-only on the outputs): per session the bridge files above, python_trial_###.json,
    every run_###/truth.jsonl, the export and the protocol note; the manifest, the report and this script; README.md with every file's size
    and SHA-256. Prints the zip's path, size and SHA-256."""
    import hashlib
    import zipfile
    zpath = OUT / f"timing_rerun_logs_{stamp}.zip"
    files = []                                             # (path on disk, name in the zip)
    for e in entries:
        B, U, X = s5.p(e["bridge"]), s5.p(e["unity"]), s5.p(e["export"])
        files += [(B / n, f"{B.name}/{n}") for n in BRIDGE_FILES if (B / n).exists()]
        files += [(q, f"{B.name}/{q.name}") for q in sorted(B.glob("python_trial_*.json"))]
        files += [(q, f"{U.name}/{q.parent.name}/truth.jsonl") for q in sorted(U.glob("run_*/truth.jsonl"))]
        files += [(U / "session.json", f"{U.name}/session.json")] if (U / "session.json").exists() else []
        files += [(q, f"{X.name}/{q.name}") for q in sorted(X.glob("*.csv"))]
        if e.get("protocol") and s5.p(e["protocol"]).exists():
            files.append((s5.p(e["protocol"]), s5.p(e["protocol"]).name))
    files += [(q, q.name) for q in extra] + [(Path(__file__), Path(__file__).name)]

    def sha(path):
        h = hashlib.sha256()
        with path.open("rb") as fh:
            for chunk in iter(lambda: fh.read(1 << 20), b""):
                h.update(chunk)
        return h.hexdigest()
    readme = ["# Strict-protocol timing rerun: logs for Anisha", "", "experiments_ab.md section 15 addendum 5, item 2. Development data. Sessions:", ""]
    readme += [f"- {e['setting']}: Unity `{s5.p(e['unity']).name}`, bridge `{s5.p(e['bridge']).name}`, export `{s5.p(e['export']).name}`" for e in entries]
    readme += ["", "| file | bytes | SHA-256 |", "|---|---|---|"] + [f"| {n} | {q.stat().st_size} | {sha(q)} |" for q, n in files]
    with zipfile.ZipFile(zpath, "x", compression=zipfile.ZIP_DEFLATED) as z:
        for q, n in files:
            z.write(q, n)
        z.writestr("README.md", "\n".join(readme) + "\n")
    with zipfile.ZipFile(zpath) as z:
        bad = z.testzip()
    return f"{zpath} ({zpath.stat().st_size} bytes, {len(files) + 1} entries, testzip {'clean' if bad is None else 'FAILED at ' + bad}); SHA-256 {sha(zpath)}"


if __name__ == "__main__":
    sys.exit(main(sys.argv))
