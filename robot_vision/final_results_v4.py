"""The results of the A/B finals over all 13 settings, as tables (AUDIT.md 16.35). REPORTING CODE; it reads the final root (the sittings' folders, the evaluation and
export folders written by process_final_zip_v4.py) and writes ONE new folder <final_root>/final_results_<time>/ with every table as CSV and Markdown. It evaluates
nothing and writes no run-once marker; it changes no file that exists. Numbers are reported as they are, with their counts.

  python final_results_v4.py --final-root <folder> [--zip <sitting zip> ...]

a  per setting: n, successes, rate with Wilson 95 %, failure reasons, median / p95 time, closest approach
b  B detection ON vs OFF (B1, B2_right, B3, B4): difference with the Newcombe 95 % interval (from the combined table)
c  Set A vs Set B: per scenario (combined table) and pooled over the four matched scenarios
d  lies per B setting: given / detected / corrected / fooled, split by the person asked first and the persons asked later (dialogs.csv)
e  STOP gesture episodes true / false per setting, and from stop_reading.jsonl how often C2s applied
f  gesture confusion (shown vs read) and branch confusion (true vs read), overall and per setting
g  timing per sitting against the limits declared in configs/v4/bridge.json; interruptions / resumes; superseded evaluations
"""

from __future__ import annotations

import argparse
import csv
import json
import statistics
import sys
import zipfile
from datetime import datetime
from pathlib import Path

import export_csv_v4 as ex
import final_guard_v4 as fg
import freeze_v4 as fz
import process_final_zip_v4 as pf

HERE = Path(__file__).resolve().parent
ND = "not evaluated"


def read_csv(path: Path) -> list[dict]:
    with Path(path).open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def write_table(folder: Path, stem: str, title: str, rows: list[dict], note: str = "") -> None:
    cols = list(dict.fromkeys(k for r in rows for k in r)) or ["(no rows)"]
    with (folder / f"{stem}.csv").open("x", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(cols)
        for r in rows:
            w.writerow([ex._fmt(r.get(c)) for c in cols])
    L = [f"# {title}", ""] + ([note, ""] if note else []) + ["| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
    L += ["| " + " | ".join(str(ex._fmt(r.get(c))) for c in cols) + " |" for r in rows]
    (folder / f"{stem}.md").write_text("\n".join(L) + "\n", encoding="utf-8")


def pct(values: list[float], q: float):
    if not values:
        return ND
    import numpy as np
    return round(float(np.percentile(values, q)), 3)


def floats(rows: list[dict], key: str) -> list[float]:
    out = []
    for r in rows:
        try:
            if r.get(key, "") != "":
                out.append(float(r[key]))
        except ValueError:
            pass
    return out


def wilson_cell(k: int, n: int, z: float) -> dict:
    w = ex._wilson(k, n, z)
    lo, hi = w["wilson95"] if isinstance(w["wilson95"], list) else (None, None)
    return {"rate": w["ratio"], "wilson_lo": lo, "wilson_hi": hi}


# ---------------------------------------------------------------- where things are

def locate(root: Path, repo: Path) -> dict:
    """setting -> {export, evaluation, bridges, runs.csv rows, dialogs.csv rows}; every setting must have exactly one export and one evaluation (superseded ones ignored)."""
    out = {}
    for s in fg.settings(repo):
        ex_m, ev_m = fg.markers(root, s, "export"), fg.markers(root, s, "evaluation")
        if len(ex_m) != 1 or len(ev_m) != 1:
            raise SystemExit(f"{s}: {len(ex_m)} export and {len(ev_m)} evaluation folders: the results need exactly one of each (nothing is guessed)")
        bridges = sorted(m.parent for m in fg.markers(root, s, "started"))
        out[s] = {"export": ex_m[0].parent, "evaluation": ev_m[0].parent, "bridges": bridges,
                  "runs": read_csv(ex_m[0].parent / "runs.csv"), "dialogs": read_csv(ex_m[0].parent / "dialogs.csv")}
    return out


# ---------------------------------------------------------------- the tables

def table_a(data: dict, z: float) -> list[dict]:
    rows = []
    for s, d in data.items():
        r = d["runs"]
        k = sum(x["outcome"] == "SUCCESS" for x in r)
        reasons = {x["failure_reason"] for x in r if x["outcome"] != "SUCCESS"}
        times_all, times_ok = floats(r, "time_s"), floats([x for x in r if x["outcome"] == "SUCCESS"], "time_s")
        close = floats(r, "closest_person_m")
        rows.append({"setting": s, "n": len(r), "successes": k, **wilson_cell(k, len(r), z),
                     **{f"failed_{f}": sum(x["failure_reason"] == f for x in r if x["outcome"] != "SUCCESS") for f in ("wrong_goal", "aborted", "timeout", "collision")},
                     "other_failure_reasons": ", ".join(sorted(reasons - {"wrong_goal", "aborted", "timeout", "collision"})) or "none",
                     "median_time_s_all_runs": pct(times_all, 50), "p95_time_s_all_runs": pct(times_all, 95), "median_time_s_success": pct(times_ok, 50),
                     "p95_time_s_success": pct(times_ok, 95), "closest_person_min_m": round(min(close), 3) if close else ND,
                     "closest_person_median_m": pct(close, 50), "collisions": sum(int(x["collisions"] or 0) for x in r)})
    return rows


def table_b(combined: dict) -> list[dict]:
    return [{"comparison": c["name"], "metric": c["metric"], "x (OFF)": c["x"], "x_cell": c["x_cell"], "y (ON)": c["y"], "y_cell": c["y_cell"],
             "difference_pp (ON - OFF)": c["difference_pp"], "newcombe_lo_pp": c["difference_lo_pp"], "newcombe_hi_pp": c["difference_hi_pp"]}
            for c in combined["comparisons"] if c.get("kind") == "B on vs off"]


def table_c(data: dict, combined: dict, z: float) -> list[dict]:
    rows = [{"scope": c["name"], "metric": c["metric"], "A": f"{c['x']}: {c['x_cell']}", "B": f"{c['y']}: {c['y_cell']}", "difference_pp (B - A)": c["difference_pp"],
             "newcombe_lo_pp": c["difference_lo_pp"], "newcombe_hi_pp": c["difference_hi_pp"]} for c in combined["comparisons"] if c.get("kind") == "A vs B"]

    def pool(names):
        r = [x for s in names for x in data[s]["runs"]]
        return sum(x["outcome"] == "SUCCESS" for x in r), len(r)

    for label, a_set, b_set in (("pooled: A1 A2_right A3 A4 vs B1 B2_right B3 B4 (detection ON)", ("A1", "A2_right", "A3", "A4"), ("B1", "B2_right", "B3", "B4")),
                                ("pooled: B ON (B1 B2_right B3 B4) vs B OFF (their _off partners)", ("B1_off", "B2_right_off", "B3_off", "B4_off"), ("B1", "B2_right", "B3", "B4"))):
        (ka, na), (kb, nb) = pool(a_set), pool(b_set)
        nc = ex.newcombe(ka, na, kb, nb, z)
        wa, wb = ex._wilson(ka, na, z), ex._wilson(kb, nb, z)
        rows.append({"scope": label, "metric": "success", "A": f"{ka}/{na} = {wa['ratio']} {wa['wilson95']}", "B": f"{kb}/{nb} = {wb['ratio']} {wb['wilson95']}",
                     "difference_pp (B - A)": nc["difference_pp"], "newcombe_lo_pp": nc["lo_pp"], "newcombe_hi_pp": nc["hi_pp"]})
    return rows


def lie_split(dialogs: list[dict]) -> dict:
    """given / detected / corrected / fooled over the asks with truthful == false, by the dialog index (1 = the first person asked at the visit, 2 or more = later).
    The definitions of export_csv_v4.run_tables, per ask: detected = rejected or outvoted or withdrawn; corrected = detected and the branch finally taken is the true one
    (not derivable per ask when the answer was withdrawn by a backtrack: counted apart); fooled = accepted, taken, and not the true branch."""
    res = {g: {"given": 0, "detected": 0, "corrected": 0, "corrected_not_derivable_withdrawn": 0, "fooled": 0} for g in ("first", "later")}
    for r in dialogs:
        if r.get("truthful") != "false":
            continue
        g = "first" if str(r.get("dialog")) == "1" else "later"
        res[g]["given"] += 1
        det = (r["decision"] or "").startswith("rejected") or r["outvoted"] == "true" or r["withdrawn"] == "true"
        res[g]["detected"] += det
        if det:
            if r["withdrawn"] == "true":
                res[g]["corrected_not_derivable_withdrawn"] += 1
            else:
                res[g]["corrected"] += bool(r["final_branch"] and r["final_branch"] == r["true_branch"])
        elif r["decision"] == "accepted" and r["final_branch"] == r["branch_read"] and r["branch_read"] != r["true_branch"]:
            res[g]["fooled"] += 1
    return res


def table_d(data: dict) -> list[dict]:
    rows = []
    for s, d in data.items():
        if fg.plan()["settings"][s].get("set") != "B":
            continue
        sp = lie_split(d["dialogs"])
        tot = {k: sum(sp[g][k] for g in sp) for k in sp["first"]}
        exp = {k: sum(int(x[f"lies_{k}"] or 0) for x in d["runs"]) for k in ("given", "detected", "corrected", "fooled")}
        for g in ("first", "later", "both"):
            v = tot if g == "both" else sp[g]
            rows.append({"setting": s, "asked": {"first": "first person asked", "later": "later persons asked", "both": "all"}[g], **v,
                         **({"export_runs_csv_given": exp["given"], "export_detected": exp["detected"], "export_corrected": exp["corrected"], "export_fooled": exp["fooled"],
                             "agrees_with_runs_csv": tot["given"] == exp["given"] and tot["detected"] == exp["detected"] and tot["fooled"] == exp["fooled"]} if g == "both" else {})})
    return rows


def c2s_counts(bridges: list[Path]) -> dict:
    n = applies = changed = switch_rows = 0
    for b in bridges:
        p = b / "stop_reading.jsonl"
        if not p.is_file():
            return {"rows": ND}
        for line in p.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            r = json.loads(line)
            n += 1
            switch_rows += bool(r.get("switch"))
            if r.get("applies"):
                applies += 1
                changed += set(r.get("stop_used", [])) != set(r.get("stop_other", []))
    return {"rows": n, "switch_on_rows": switch_rows, "c2s_applied_rows": applies, "share_applied": round(applies / n, 4) if n else ND, "c2s_changed_the_stop_reading_rows": changed}


def table_e(data: dict) -> list[dict]:
    rows = []
    for s, d in data.items():
        t, f = floats(d["runs"], "stop_gestures_true"), floats(d["runs"], "stop_gestures_false")
        rows.append({"setting": s, "stop_episodes_true": int(sum(t)) if t else ND, "stop_episodes_false": int(sum(f)) if f else ND, "runs_counted": len(t), **c2s_counts(d["bridges"])})
    return rows


def table_g(data: dict, sittings: dict, limits: dict) -> tuple[list[dict], list[dict]]:
    per = []
    for s, d in data.items():
        rt, lag, p99, wd, over, unans = [], [], [], [], [], []
        for b in d["bridges"]:
            sm = json.loads((b / "summary.json").read_text(encoding="utf-8"))
            am = (sm.get("round_trip") or {}).get("all_messages") or {}
            rt.append(am.get("max_ms"))
            lag.append(((sm.get("event_loop_lag") or {}).get("all_samples") or {}).get("max_ms"))
            p99.append(((sm.get("event_loop_lag") or {}).get("all_samples") or {}).get("p99_ms"))
            wd.append((sm.get("watchdog") or {}).get("stops_reported_by_unity"))
            m = (sm.get("round_trip") or {}).get("all_messages", {}).get("coverage", "")
            parts = [x for x in m.replace("replies to", " ").replace("telemetry messages", " ").split() if x.isdigit()]
            unans.append(int(parts[1]) - int(parts[0]) if len(parts) == 2 else None)
        num = lambda xs: [x for x in xs if isinstance(x, (int, float))]  # noqa: E731
        per.append({"setting": s, "sitting": next((k for k, v in sittings.items() if s in v), "?"), "round_trip_max_ms": max(num(rt)) if num(rt) else ND,
                    "loop_lag_max_ms": max(num(lag)) if num(lag) else ND, "loop_lag_p99_ms": max(num(p99)) if num(p99) else ND,
                    "telemetry_without_reply": sum(num(unans)) if num(unans) else ND, "watchdog_stops_reported": sum(num(wd)) if num(wd) else ND})
    out = []
    for k, names in sorted(sittings.items()):
        mine = [r for r in per if r["setting"] in names]
        for metric, lim_key in (("round_trip_max_ms", "round_trip_max_ms"), ("loop_lag_max_ms", "loop_lag_max_ms"), ("loop_lag_p99_ms", "loop_lag_p99_ms"),
                                ("telemetry_without_reply", "unanswered_telemetry")):
            vals = [r[metric] for r in mine if isinstance(r[metric], (int, float))]
            v = max(vals) if vals else None
            lim = limits.get(lim_key)
            worst = max((r for r in mine if isinstance(r[metric], (int, float))), key=lambda r: r[metric], default=None)
            out.append({"sitting": k, "settings": ", ".join(names), "metric": metric, "worst_value": v if v is not None else ND, "declared_limit": lim,
                        "within_limit": (v <= lim) if (v is not None and lim is not None) else ND, "worst_setting": worst["setting"] if worst else ND})
        out.append({"sitting": k, "settings": ", ".join(names), "metric": "watchdog_stops_reported", "worst_value": sum(r["watchdog_stops_reported"] for r in mine if isinstance(r["watchdog_stops_reported"], int)),
                    "declared_limit": "none declared (a result, B11 a)", "within_limit": "n/a", "worst_setting": ""})
        for m in ("round_trip_p99_ms", "reply_gap_max_ms"):
            out.append({"sitting": k, "settings": ", ".join(names), "metric": m, "worst_value": ND, "declared_limit": limits.get(m), "within_limit": ND,
                        "worst_setting": "not in the bridge summary (the replay timing check measures it)"})
    return per, out


# ---------------------------------------------------------------- the report

def build(root: Path, zips: list[Path], repo: Path = fz.REPO) -> Path:
    data = locate(root, repo)
    z = ex.wilson_z(repo)
    combs = sorted(root.glob("export_csv_v4_final_combined_*/combined.json"))
    if not combs:
        raise SystemExit("no combined table in the final root: run process_final_zip_v4.py first")
    combined = json.loads(combs[-1].read_text(encoding="utf-8"))
    if len(combined["settings"]) != len(fg.settings(repo)):
        raise SystemExit(f"the newest combined table has {len(combined['settings'])} settings, not {len(fg.settings(repo))}: not all sittings are processed")
    sittings, hashes = {}, []
    for zp in zips:
        with zipfile.ZipFile(zp) as zf:
            meta = json.loads(zf.read("MANIFEST.json").decode("utf-8-sig"))
        sittings[meta["sitting"]] = [x["setting"] for x in meta["settings"]]
        side = zp.parent / (zp.name + ".sha256")
        hashes.append({"sitting": meta["sitting"], "zip": zp.name, "sha256": fzip_sha(zp), "sha256_file_agrees": side.is_file() and side.read_text(encoding="utf-8").split()[0].lower() == fzip_sha(zp)})
    out = pf.new_report_dir(root, "final_results")
    limits = json.loads((repo / "robot_vision/configs/v4/bridge.json").read_text(encoding="utf-8")).get("timing_limits", {})
    write_table(out, "a_per_setting", "A. Per setting: success with Wilson 95 % interval, failure reasons, time, closest approach", table_a(data, z),
                "n = runs; time in seconds (all runs: every run's total time; success: successful runs only); p95 by linear interpolation. Closest approach to any person, in metres.")
    write_table(out, "b_on_vs_off", "B. Lie detection ON vs OFF: difference with the Newcombe 95 % interval", table_b(combined),
                "Difference = ON minus OFF in percentage points (Newcombe hybrid-score interval, Wilson based). It describes the two rates; no test, no claim of significance.")
    write_table(out, "c_set_a_vs_b", "C. Set A (truthful workers) vs Set B (lying workers), detection ON", table_c(data, combined, z),
                "Difference = B minus A in percentage points with the Newcombe 95 % interval; the pooled rows add the runs of the matched scenarios.")
    write_table(out, "d_lies", "D. Lies per B setting: given / detected / corrected / fooled, by the person asked first and the persons asked later", table_d(data),
                "From dialogs.csv, per ask (definitions of export_csv_v4). 'corrected' is not derivable per ask when a backtrack withdrew the answer (counted apart). The 'all' row is checked against runs.csv: runs.csv counts lying GESTURES, this table counts ASKS whose gesture was a lie, so 'given' can differ by the asks that repeated the same lie (agrees_with_runs_csv says where).")
    write_table(out, "e_stop_and_c2s", "E. STOP gesture episodes (true / false) and how often C2s applied (stop_reading.jsonl)", table_e(data),
                "A STOP episode = consecutive decisions.csv rows with the safety 'STOP gesture'; true = a worker was showing STOP at its first row. C2s applied = rows where the short-window STOP reading replaced the reader's own (robot stopped in read/approach).")
    for stem, title, shown, read, labels, share in (("f_gesture_confusion", "F. Gesture confusion: shown vs read", "command_shown", "command_read", ["POINT", "WAIT", "STOP", "PROCEED", "NONE"], "share read as shown"),
                                                     ("f_branch_confusion", "F. Branch confusion: true vs read branch", "true_branch", "branch_read", ["FORWARD", "LEFT", "RIGHT", "BACK", "NONE"], "share read as true")):
        allrows = [r for d in data.values() for r in d["dialogs"]]
        mats = {"ALL 13 settings (pooled)": pf.confusion(allrows, shown, read, labels), **{s: pf.confusion(d["dialogs"], shown, read, labels) for s, d in data.items()}}
        pf.write_matrix(out, stem, title, mats, shown, read, share)
    per, lim = table_g(data, sittings, limits)
    write_table(out, "g_timing_per_setting", "G. Timing per setting (bridge summary.json)", per)
    write_table(out, "g_timing_per_sitting_vs_limits", "G. Timing per sitting against the limits declared in configs/v4/bridge.json", lim,
                "The limits were declared for the replay timing check (2026-11-06); they are applied here to the finals' sessions as the worst value of each sitting. Metrics the bridge summary does not carry are 'not evaluated'.")
    inter = [{"item": "interruption / resume (16.30.1)", "found": "none: no FINAL_INTERRUPTION.json or FINAL_RESUME.json in the final root" if not list(root.glob("final_interruption_*")) else "SEE the folders final_interruption_*"}]
    sup = sorted(root.glob("final_eval_superseded_*/FINAL_EVAL_SUPERSEDED.json"))
    for m in sup:
        r = json.loads(m.read_text(encoding="utf-8"))
        inter.append({"item": "evaluation superseded (16.35.1)", "found": f"{r['setting']}: {r['superseded_folder']} (the wrong-map evaluation) -> corrected evaluation {data[r['setting']]['evaluation'].name}"})
    write_table(out, "g_interruptions_and_supersessions", "G. Interruptions, resumes and superseded evaluations", inter)
    write_table(out, "zips", "The four sitting zips", hashes)
    prov = [{"setting": s, "export_folder": d["export"].name, "evaluation_folder": d["evaluation"].name, "bridge_folders": ", ".join(b.name for b in d["bridges"])} for s, d in data.items()]
    write_table(out, "provenance", "Where each setting's numbers come from", prov)
    (out / "h_figures.md").write_text("# H. Figures\n\nNOT PRODUCED: `paper_v4/figures_v4.py` reads development data only (its split guard refuses test data) and fails on the dialog outcome `not_evaluated`; "
                                      "it needs a final mode and a fix (Nusrat's file, AUDIT.md 16.33.2). No figure is made from the finals here.\n", encoding="utf-8")
    return out


def fzip_sha(p: Path) -> str:
    import hashlib
    h = hashlib.sha256()
    with p.open("rb") as f:
        for c in iter(lambda: f.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--final-root", required=True)
    ap.add_argument("--zip", nargs="+", default=[], help="the sitting zips (read in place: their manifests and hashes)")
    a = ap.parse_args(argv)
    out = build(Path(a.final_root).expanduser(), [Path(z).expanduser() for z in a.zip])
    print(f"results: {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
