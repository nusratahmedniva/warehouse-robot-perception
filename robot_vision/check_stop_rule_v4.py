"""The candidate false-STOP rule and its declared fallbacks against the criteria (a) to (c) of AUDIT.md 16.16, on Nusrat's STOP sessions (AUDIT.md 16.18,
decided 2026-11-16 and recorded BEFORE the data was analysed). EVALUATION CODE ONLY: it reads the workers' true commands (truth.jsonl); inference code
never imports it. It changes nothing in the reader: the rules are applied in this script only, by the wrapper of analyse_false_stop_v4 (16.14).

Input: the zip of Nusrat's STOP sessions (read in place with zipfile, never extracted or copied; layout as analyse_false_stop_v4.Logs). DEVELOPMENT DATA
ONLY: every run's looks and clips go through data_splits_v4.guard_run before anything is computed.

Rules (configs/v4/experiments/stop_rule_check.json): the current reader; the candidate (open hand AND fingertip spread >= 1.3 AND static AND raised arm);
fallback (i) (the static cue as the short 0.3 s window); fallback (ii) (the static cue dropped). The candidate is evaluated first; a fallback is tried only
when the previous rule fails (a); if (a) is met and (b) or (c) is not, no fallback is declared and none is tried. Nothing else is tuned.

Criteria, as declared:
  (a) every true STOP, held and while driving, read within 1.0 s of its first shown truth row: n of n (a STOP is one contiguous run of shown truth rows of
      one worker with true_command STOP; read = the reader says STOP on a person-frame matched to that worker);
  (b) fewer accepted false STOPs than the current rule on the PROCEED, POINT and WAIT frames of the 36 negative items, as person-frames and as stop episodes,
      total strictly smaller in both counts and no category with more;
  (c) no accepted STOP on any idle frame (NONE, idle and start-delay frames of every worker), including the idle passes.
An accepted STOP is a STOP reading of the reader on a person-frame; a stop episode is the readings of one run closer than episode_gap_s (0.5 s).

Usage (from robot_vision/):
  python check_stop_rule_v4.py --zip ~/Downloads/stop_session_logs_20261115_192423.zip [--config configs/v4/experiments/stop_rule_check.json]
Writes a new folder <output_root>/stop_rule_check_v4_<time>/ with report.json, report.md, config_used/ and run.json (git commit, zip SHA-256).
"""

from __future__ import annotations

import argparse
import bisect
import contextlib
import json
import statistics as st
from collections import Counter, defaultdict
from pathlib import Path

import analyse_false_stop_v4 as fs
import commander_v4 as cm
import data_splits_v4 as ds
import gesture_motion as gm

HERE = Path(__file__).resolve().parent
DEFAULT_CONFIG = "configs/v4/experiments/stop_rule_check.json"
NEGATIVES = ("PROCEED", "POINT", "WAIT")
KINDS = ("held_stop", "driving_stop", "negative_POINT", "negative_PROCEED", "negative_WAIT", "idle_pass", "other")


def load_config(path: str | Path = DEFAULT_CONFIG) -> dict:
    """The settings of this check merged over the 16.14 analysis settings it names (matching, shown phases, episode gap)."""
    p = Path(path)
    own = json.loads((p if p.is_absolute() else HERE / p).read_text(encoding="utf-8"))
    base = fs.load_config(own["base_config"])
    return {**base, **{k: v for k, v in own.items() if k != "base_config"}, "sessions": own["sessions"]}


# ---------------------------------------------------------------- what each run is, and its true STOPs

def run_kind(truth: dict, cfg: dict) -> str:
    """The item of a run, read from its truth rows (Nusrat's scenario, experiments_ab.md section 13): a STOP at the ask (held) or after a PROCEED that starts
    a drive (driving); one negative command at the ask; PROCEED with a second, idle worker (the idle pass)."""
    shown = defaultdict(set)
    for w, rows in truth.items():
        for r in rows:
            if r["true_command"] != "NONE" and r["phase"] in cfg["shown_phases"]:
                shown[w].add(r["true_command"])
    cmds = set().union(*shown.values()) if shown else set()
    if "STOP" in cmds:
        return "driving_stop" if "PROCEED" in cmds else "held_stop"
    if cmds in ({"POINT"}, {"WAIT"}):
        return f"negative_{next(iter(cmds))}"
    if cmds == {"PROCEED"}:
        return "idle_pass" if len(truth) > 1 else "negative_PROCEED"
    return "other"


def stop_segments(truth: dict, cfg: dict, session: str, run: int, kind: str) -> list[dict]:
    """The true STOPs of one run: per worker, contiguous shown rows with true_command STOP (a gap longer than stop_gap_s starts a new one)."""
    out = []
    for w, rows in truth.items():
        cur = None
        for r in sorted(rows, key=lambda r: r["time_s"]):
            if r["true_command"] == "STOP" and r["phase"] in cfg["shown_phases"]:
                if cur is None or r["time_s"] - cur["end"] > cfg["stop_gap_s"] + 1e-9:
                    cur = {"session": session, "run": run, "worker": w, "look": r["look"], "arm": r.get("arm"), "clip": r.get("clip"), "kind": kind,
                           "onset": r["time_s"], "end": r["time_s"], "x": r["x"], "z": r["z"]}
                    out.append(cur)
                cur["end"] = r["time_s"]
    return out


# ---------------------------------------------------------------- one rule on every run

def readings(runs_data: dict, kinds: dict, cues: dict, rc: dict, cc: dict, cfg: dict) -> list[tuple]:
    """Every person-frame of every run under one rule: (session, run, kind, t, category, worker, is_stop, has_hand). The frames of the phase
    "returning" get the category "returning": they are in no criterion (as in 16.14) but the replay check needs every STOP reading."""
    out = []
    ctx = fs.candidate(cues, rc) if cues else contextlib.nullcontext()
    with ctx:
        for (sname, run), d in runs_data.items():
            for f, prs, _ in fs.replay(d["frames"], rc, cc):
                for p in prs:
                    w, cat = fs.category_of(f, p, d["truth"], cfg)
                    has_hand = any(h["track_id"] == p.track_id for h in f["hands"])
                    out.append((sname, run, kinds[(sname, run)], f["time_s"], cat if cat is not None else "returning", w, p.reading.command == "STOP", has_hand))
    return out


def _tally(recs: list[tuple], gap_s: float) -> dict:
    """{frames, stop_frames, episodes} of a set of person-frames (episodes per run)."""
    by_run: dict = defaultdict(list)
    for r in recs:
        if r[6]:
            by_run[(r[0], r[1])].append((r[3], r[4]))
    return {"frames": len(recs), "stop_frames": sum(1 for r in recs if r[6]), "episodes": sum(len(fs.episodes(ev, gap_s)) for ev in by_run.values())}


def score(recs: list[tuple], segments: list[dict], kinds: dict, cfg: dict) -> dict:
    """The numbers of one rule: (a) per true STOP, (b) per category on the negative items, (c) on the idle frames, and the information lines."""
    gap, within = cfg["episode_gap_s"], cfg["within_s"]
    a = []
    for s in segments:
        mine = sorted((r for r in recs if r[0] == s["session"] and r[1] == s["run"] and r[5] == s["worker"] and r[3] >= s["onset"] - 1e-9), key=lambda r: r[3])
        first = next((r[3] - s["onset"] for r in mine if r[6] and r[4] == "STOP" and r[3] <= s["onset"] + within + 1e-9), None)
        later = next((r[3] - s["onset"] for r in mine if r[6] and r[3] <= s["end"] + 1e-9), None)
        a.append({**{k: s[k] for k in ("session", "run", "worker", "look", "arm", "clip", "kind", "onset")}, "latency_s": None if first is None else round(first, 3),
                  "read_within": first is not None, "first_reading_s_any_time_in_the_segment": None if later is None else round(later, 3),
                  "matched_frames_in_the_window": sum(1 for r in mine if r[3] <= s["onset"] + within + 1e-9),
                  "frames_with_a_hand_in_the_window": sum(1 for r in mine if r[3] <= s["onset"] + within + 1e-9 and r[7])})
    items = {c: _tally([r for r in recs if r[2] == f"negative_{c}" and r[4] == c], gap) for c in NEGATIVES}
    total = {k: sum(items[c][k] for c in NEGATIVES) for k in ("frames", "stop_frames", "episodes")}
    idle_all = _tally([r for r in recs if r[4] == "nothing"], gap)
    idle_stops = [{"session": r[0], "run": r[1], "kind": r[2], "t": round(r[3], 3), "worker": r[5]} for r in recs if r[4] == "nothing" and r[6]]
    idle_pass = _tally([r for r in recs if r[2] == "idle_pass" and r[4] == "nothing"], gap)
    by_cat = {c: _tally([r for r in recs if r[4] == c], gap) for c in ("PROCEED", "POINT", "WAIT", "STOP", "nothing", "unmatched")}
    runs_with_stop = {k: {"runs": sum(1 for v in kinds.values() if v == k), "with_a_STOP_reading": len({(r[0], r[1]) for r in recs if r[2] == k and r[6]})}
                      for k in KINDS}
    lat = [x["latency_s"] for x in a if x["latency_s"] is not None]
    return {"a": a, "a_summary": {"stops": len(a), "read_within": sum(x["read_within"] for x in a),
                                    "held": {"stops": sum(x["kind"] == "held_stop" for x in a), "read_within": sum(x["kind"] == "held_stop" and x["read_within"] for x in a)},
                                    "driving": {"stops": sum(x["kind"] == "driving_stop" for x in a), "read_within": sum(x["kind"] == "driving_stop" and x["read_within"] for x in a)},
                                    "latency_median_s": round(st.median(lat), 3) if lat else None, "latency_max_s": round(max(lat), 3) if lat else None},
            "b_items": items, "b_total": total, "c_idle_frames": idle_all, "c_idle_stop_frames_listed": idle_stops, "c_idle_pass_runs": idle_pass, "by_category_all_frames": by_cat, "runs_with_a_STOP_reading": runs_with_stop}


def verdict(rule: dict, current: dict) -> dict:
    """(a), (b), (c) of one rule against the current rule, as declared (AUDIT.md 16.16 decision 2, 16.16.2 item 1)."""
    s = rule["a_summary"]
    a = {"met": s["stops"] > 0 and s["read_within"] == s["stops"], "n": s["stops"], "read_within": s["read_within"]}
    cb, rb = current["b_total"], rule["b_total"]
    per_cat_ok = all(rule["b_items"][c][k] <= current["b_items"][c][k] for c in NEGATIVES for k in ("stop_frames", "episodes"))
    testable = cb["stop_frames"] > 0 and cb["episodes"] > 0
    b = {"met": bool(testable and rb["stop_frames"] < cb["stop_frames"] and rb["episodes"] < cb["episodes"] and per_cat_ok), "testable": testable,
         "frames": [rb["stop_frames"], cb["stop_frames"]], "episodes": [rb["episodes"], cb["episodes"]], "no_category_with_more": per_cat_ok}
    c = {"met": rule["c_idle_frames"]["stop_frames"] == 0, "stop_frames": rule["c_idle_frames"]["stop_frames"], "episodes": rule["c_idle_frames"]["episodes"],
         "idle_frames": rule["c_idle_frames"]["frames"]}
    return {"a": a, "b": b, "c": c, "all_met": a["met"] and b["met"] and c["met"]}


def decide(scored: dict, cfg: dict) -> dict:
    """The declared order: the candidate; a fallback only when the previous rule failed (a). Returns which rules were tried and the outcome."""
    tried, outcome = [], "none of the tried rules meets (a), (b) and (c)"
    prev_a_failed = True
    for name in cfg["order"]:
        if not prev_a_failed:
            break
        v = verdict(scored[name], scored["current"])
        tried.append(name)
        prev_a_failed = not v["a"]["met"]
        if v["all_met"]:
            outcome = f"{name} meets (a), (b) and (c)"
            break
    return {"tried": tried, "not_tried": [n for n in cfg["order"] if n not in tried], "outcome": outcome,
            "verdicts": {n: verdict(scored[n], scored["current"]) for n in cfg["order"]}}


# ---------------------------------------------------------------- the whole check

def check(logs: fs.Logs, cfg: dict, rc: dict, cc: dict, progress=None) -> dict:
    runs_data, guard_out, sessions = fs.load_runs(logs, cfg)
    kinds, segments = {}, []
    for (sname, run), d in runs_data.items():
        kinds[(sname, run)] = run_kind(d["truth"], cfg)
        segments += stop_segments(d["truth"], cfg, sname, run, kinds[(sname, run)])
    counts = {s: Counter(k for (sn, _), k in kinds.items() if sn == s) for s in cfg["sessions"]}
    plan_check = {s: {"found": dict(counts[s]), "plan": cfg["plan"].get(s, {}),
                      "as_planned": all(counts[s].get(k, 0) == v for k, v in cfg["plan"].get(s, {}).items()) and counts[s].get("other", 0) == 0}
                  for s in cfg["sessions"]}
    report: dict = {"zip": {"name": logs.path.name, "sha256": logs.sha256()}, "sessions": sessions, "guard_all_development": set(guard_out.values()) == {"development"},
                    "plan_check": plan_check, "stops_found": {"total": len(segments), "held": sum(s["kind"] == "held_stop" for s in segments),
                                                              "driving": sum(s["kind"] == "driving_stop" for s in segments)}}
    rules_all = {name: cues for name, cues in cfg["rules"].items()}
    scored = {}
    for name, cues in rules_all.items():
        recs = readings(runs_data, kinds, cues, rc, cc, cfg)
        scored[name] = score(recs, segments, kinds, cfg)
        if name == "current":
            report["replay_check"] = replay_check(logs, cfg, recs)
        if progress:
            progress(name)
    report["rules"] = {n: {"cues": rules_all[n], **scored[n]} for n in rules_all}
    report["decision"] = decide(scored, cfg)
    report["live_robot_stop_runs"] = live_robot(logs, cfg, kinds)
    report["reader_changed"] = False
    return report


def replay_check(logs: fs.Logs, cfg: dict, recs: list[tuple]) -> dict:
    """The replay of the current reader reproduces the STOP rows of decisions.csv (as in 16.14): rows without a replayed STOP in the 0.6 s before."""
    out = {}
    for sname, sc in cfg["sessions"].items():
        rows = [float(r["time_s"]) for r in logs.decisions(sc["bridge"]) if r["gesture"] == "STOP"]
        stops = sorted(r[3] for r in recs if r[0] == sname and r[6])
        miss = sum(1 for t in rows if not (bisect.bisect_right(stops, t) > 0 and t - stops[bisect.bisect_right(stops, t) - 1] <= 0.6))
        out[sname] = {"decisions_STOP_rows": len(rows), "replayed_STOP_person_frames_matched_or_not": len(stops), "decision_STOP_rows_without_a_replayed_STOP_in_the_0.6_s_before": miss}
    return out


def live_robot(logs: fs.Logs, cfg: dict, kinds: dict) -> dict:
    """Nusrat's descriptive figures, recomputed: runs of each kind in which the live robot stopped by a STOP gesture (decisions.csv)."""
    out: dict = defaultdict(lambda: {"runs": 0, "with_a_stop": 0})
    for sname, sc in cfg["sessions"].items():
        stopped = {e["trial"] for e in fs.live_stop_episodes(logs.decisions(sc["bridge"]))}
        for (sn, run), k in kinds.items():
            if sn == sname:
                out[k]["runs"] += 1
                out[k]["with_a_stop"] += run in stopped
    return dict(out)


# ---------------------------------------------------------------- report

def _fe(t: dict) -> str:
    return f"{t['stop_frames']}/{t['frames']} fr, {t['episodes']} ep"


def markdown(rep: dict, cfg: dict) -> str:
    d = rep["decision"]
    L = ["# The candidate false-STOP rule against the declared criteria (AUDIT.md 16.18)", "",
         f"Zip `{rep['zip']['name']}` (SHA-256 `{rep['zip']['sha256']}`), read in place. Development looks and clips only (guard passed for every run: {rep['guard_all_development']}). "
         f"**No reader value was changed and no rule is switched on.**", "",
         "## Sessions and what was found", "", "| session | runs | pan-tilt frames | runs by kind found | as planned |", "|---|---|---|---|---|"]
    for s, v in rep["sessions"].items():
        pc = rep["plan_check"][s]
        L.append(f"| {s} | {v['runs']} | {v['pan_tilt_frames']} | {pc['found']} | {pc['as_planned']} |")
    L += ["", f"True STOPs found: {rep['stops_found']['total']} ({rep['stops_found']['held']} held, {rep['stops_found']['driving']} while driving).", "",
          "Replay of the current reader against the STOP rows of decisions.csv: " + "; ".join(
              f"{s}: {c['decisions_STOP_rows']} rows, {c['decision_STOP_rows_without_a_replayed_STOP_in_the_0.6_s_before']} without a replayed STOP just before" for s, c in rep["replay_check"].items()), ""]
    L += ["The live robot (decisions.csv), runs with a stop by a STOP gesture: " + "; ".join(
        f"{k} {v['with_a_stop']}/{v['runs']}" for k, v in rep["live_robot_stop_runs"].items() if v["runs"]), ""]
    L += ["## The table: current rule, candidate and each fallback tried", "",
          "(a) = true STOPs read within 1.0 s (n of n); (b) = accepted false STOPs on the 36 negative items, person-frames with a STOP reading / person-frames, and stop episodes "
          "(rule against current); (c) = accepted STOPs on every idle frame. 'not tried' = the previous rule met (a): shown for information, decides nothing.", "",
          "| rule | tried | (a) held | (a) driving | (a) all, latency median / max (s) | (b) PROCEED | (b) POINT | (b) WAIT | (b) total vs current | (c) idle frames | (c) idle passes only | verdict |",
          "|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for name in ["current"] + cfg["order"]:
        r = rep["rules"][name]
        s = r["a_summary"]
        tried = "-" if name == "current" else ("yes" if name in d["tried"] else "not tried")
        if name == "current":
            ver = "reference"
            b_total = f"{r['b_total']['stop_frames']} fr, {r['b_total']['episodes']} ep"
        else:
            v = d["verdicts"][name]
            ver = f"(a) {'met' if v['a']['met'] else 'FAILS'}; (b) {'met' if v['b']['met'] else 'FAILS'}; (c) {'met' if v['c']['met'] else 'FAILS'}"
            b_total = f"{r['b_total']['stop_frames']} fr, {r['b_total']['episodes']} ep (current {v['b']['frames'][1]} fr, {v['b']['episodes'][1]} ep)"
        L.append(f"| {name} | {tried} | {s['held']['read_within']}/{s['held']['stops']} | {s['driving']['read_within']}/{s['driving']['stops']} | "
                 f"{s['read_within']}/{s['stops']}, {s['latency_median_s']} / {s['latency_max_s']} | {_fe(r['b_items']['PROCEED'])} | {_fe(r['b_items']['POINT'])} | {_fe(r['b_items']['WAIT'])} | "
                 f"{b_total} | {_fe(r['c_idle_frames'])} | {_fe(r['c_idle_pass_runs'])} | {ver} |")
    L += ["", f"**Outcome (declared order, declared fallbacks only): {d['outcome']}.** Rules tried: {', '.join(d['tried'])}; not tried: {', '.join(d['not_tried']) or 'none'}.", "",
          "## Information lines (not criteria)", "", "| rule | PROCEED, all frames incl. the 8 PROCEEDs that start a drive | POINT, all | WAIT, all | true-STOP frames read as STOP | people not matched to a worker |", "|---|---|---|---|---|---|"]
    for name in ["current"] + cfg["order"]:
        b = rep["rules"][name]["by_category_all_frames"]
        L.append(f"| {name} | {_fe(b['PROCEED'])} | {_fe(b['POINT'])} | {_fe(b['WAIT'])} | {_fe(b['STOP'])} | {_fe(b['unmatched'])} |")
    L += ["", "## Every true STOP: latency of the first STOP reading (s) after its first shown truth row; 'late x' = first read x s after it (not within 1.0 s), 'never' = not read in the segment", "",
          "| session/run | kind | look | arm | clip | " + " | ".join(["current"] + cfg["order"]) + " |", "|---|---|---|---|---|" + "---|" * (1 + len(cfg["order"]))]
    base = rep["rules"]["current"]["a"]
    for i, x in enumerate(base):
        cells = []
        for name in ["current"] + cfg["order"]:
            y = rep["rules"][name]["a"][i]
            late = y["first_reading_s_any_time_in_the_segment"]
            cells.append(f"{y['latency_s']:.2f}" if y["latency_s"] is not None else (f"late {late:.2f}" if late is not None else "never"))
        L.append(f"| {x['session']}/run_{x['run']:03d} | {x['kind']} | {x['look']} | {x['arm']} | {x['clip']} | " + " | ".join(cells) + " |")
    L += ["", "## Frames with a hand detected in the 1.0 s window after the onset (the 12 driving STOPs; the reader needs a hand)", "",
          "| session/run | matched person-frames in the window | with a hand | current rule: first reading |", "|---|---|---|---|"]
    for x in base:
        if x["kind"] == "driving_stop":
            late = x["first_reading_s_any_time_in_the_segment"]
            L.append(f"| {x['session']}/run_{x['run']:03d} | {x['matched_frames_in_the_window']} | {x['frames_with_a_hand_in_the_window']} | "
                     + ("never" if late is None else f"{late:.2f} s after the onset") + " |")
    L += ["", "## Accepted STOPs on idle frames (c)", ""]
    for name in ["current"] + cfg["order"]:
        lst = rep["rules"][name]["c_idle_stop_frames_listed"]
        L.append(f"- {name}: {len(lst)} frames" + ("" if not lst else ": " + "; ".join(f"{x['session']}/run_{x['run']:03d} ({x['kind']}) t {x['t']} worker {x['worker']}" for x in lst)))
    return "\n".join(L) + "\n"


def main(argv=None) -> None:
    import decision_io as dio

    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--zip", required=True)
    ap.add_argument("--config", default=DEFAULT_CONFIG)
    a = ap.parse_args(argv)
    cfg_path = dio.resolve(a.config)
    cfg = load_config(cfg_path)
    rc, cc = gm.load_config(), cm.load_config()
    logs = fs.Logs(Path(a.zip).expanduser())
    rep = check(logs, cfg, rc, cc, progress=lambda n: print("  done:", n, flush=True))
    out = dio.new_run_dir({"paths": {"output_root": "outputs"}}, "stop_rule_check_v4")
    (out / "config_used").mkdir()
    for p in (cfg_path, dio.resolve(cfg_path.parent / "false_stop_analysis.json"), dio.resolve(gm.DEFAULT_CONFIG), dio.resolve(cm.DEFAULT_CONFIG), dio.resolve(ds.DEFAULT)):
        (out / "config_used" / p.name).write_bytes(p.read_bytes())
    dio.write_json(out / "report.json", rep)
    (out / "report.md").write_text(markdown(rep, cfg), encoding="utf-8")
    dio.write_json(out / "run.json", {"git": dio.git_info(), "zip": rep["zip"]})
    print(markdown(rep, cfg))
    print(f"Folder: {out}")


if __name__ == "__main__":
    main()
