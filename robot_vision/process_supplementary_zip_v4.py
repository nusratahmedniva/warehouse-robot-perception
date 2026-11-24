"""Supplementary experiment S1 (AUDIT.md 16.37, replacing 16.36): navigation with all workers in ONE character per session; post-freeze and EXPLORATORY. REPORTING / EVALUATION CODE.

  python process_supplementary_zip_v4.py <zip> --sha256 <hash> [--finals-root <folder>] [--out-root <folder>]

The zip is made by final_zip_v4.py avatar (a manifest with `folders`): the Unity session folders and their bridge run folders of S1. It is read in place; the folders are copied
out (member by member, hash checked, no code) into a temporary folder outside the repository, used and removed.
Steps (it stops at the first failure with the reason): 1 verify; 2 sessions: pair each Unity session with its bridge folder (the bridge started last before the Unity session; each
used once; the runs must agree), check each (session.json 'supplementary' "S1", seed 2, a setting of A1 / A3 / B3, one look, timeout 480 s, 5 runs, plan_runs, leak test) and record its commit
and the hashes of its config_used files (S1 does NOT require frozen.json to match); 3 evaluate: the S1 guard (data_splits_v4.guard_run(supplementary="S1")), the run tables; 4 tables.
It writes NO final run-once marker, never writes into the finals' root (read only: the Sunbox finals A1, A3 and B3 for the paired comparison) and never edits frozen.json.
Output: a NEW folder <out_root>/process_supplementary_zip_v4_<time>/ with the tables as CSV and Markdown and report.json / report.md.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import sys
import tempfile
from collections import defaultdict
from datetime import datetime
from pathlib import Path

import data_splits_v4 as ds
import export_csv_v4 as ex
import final_guard_v4 as fg
import final_results_v4 as fr
import freeze_v4 as fz
import gesture_data as gd
import gt_path
import hri_eval_dev_v4 as ev
import process_final_zip_v4 as pf

HERE = Path(__file__).resolve().parent
NAME = "S1"
SETTINGS = ("A1", "A3", "B3")
LOOKS = ds.SUPPLEMENTARY[NAME]
# AUDIT.md 16.37: the plan runs of the final plans (seed 2) that S1 runs, in order, as run_001..run_005 of a session. B3: the 5 lowest plan runs with a liar at a junction ON the planned
# route, read from the final B3 session's workers_plan (see b3_plan_runs); A1 and A3: runs 1-5.
PLAN_RUNS = {"A1": [1, 2, 3, 4, 5], "A3": [1, 2, 3, 4, 5], "B3": [5, 7, 8, 10, 11]}
RUNS, SEED, TIMEOUT_S = 5, 2, 480.0
FINAL_MARKERS = ("FINAL_DONE.json", "FINAL_EXPORT_DONE.json", "FINAL_RUN_DONE.json", "FINAL_SETTING.json", "FINAL_INTERRUPTION.json", "FINAL_RESUME.json",
                 "FINAL_INVALID.json", "FINAL_EVAL_SUPERSEDED.json")
_STAMP = re.compile(r"(\d{8}_\d{6})$")


def b3_plan_runs(workers_plan: list, goal_order: list, road, n: int = RUNS) -> list[int]:
    """The B3 rule of AUDIT.md 16.37, from the PLAN only (a final B3 session's workers_plan and goal_order, the map): the n lowest run numbers in which at least one worker standing at
    a node of kind 'junction' on the planned route (A to the goal along command_toward) is a liar. A, the start node, is not a junction: nobody is asked there."""
    liars: dict[int, set] = defaultdict(set)
    for line in workers_plan:
        m = re.match(r"run (\d+) worker \d+: (\w+) slot \d+.*?(LIAR|truthful)", line)
        if m and m.group(3) == "LIAR":
            liars[int(m.group(1))].add(m.group(2))
    out = []
    for i, goal in enumerate(goal_order, 1):
        node, route = "A", {"A"}
        while node != goal and len(route) < 40:
            node = road.next(node, road.command_toward(node, goal))
            route.add(node)
        if any(road.kind(j) == "junction" for j in liars[i] & route):
            out.append(i)
    return out[:n]


def stamp_of(path: Path) -> str | None:
    m = _STAMP.search(path.name)
    return m.group(1) if m else None


def sha_lf(p: Path) -> str:
    return fz.sha256_lf(p)


# ---------------------------------------------------------------- sessions

def setting_of(session: dict, plan: dict) -> str | None:
    s = session.get("final_setting")
    if s in SETTINGS:
        return s
    cands = [n for n in SETTINGS if plan["settings"][n].get("experiment") == session.get("experiment") and plan["settings"][n].get("set") == session.get("set")]
    return cands[0] if len(cands) == 1 else None


def classify_folders(root: Path, folders: list[str]) -> tuple[list[Path], list[Path]]:
    """(Unity session folders, bridge run folders) among the copied folders: a Unity session has session.json, a bridge folder has python_trial_*.json."""
    unity, bridge = [], []
    for n in folders:
        d = root / n
        if (d / "session.json").is_file():
            unity.append(d)
        elif list(d.glob("python_trial_*.json")) or (d / "v4_log.jsonl").is_file():
            bridge.append(d)
        else:
            raise pf.StepFailed(f"{n}: neither a Unity session (no session.json) nor a bridge run folder (no python_trial files)")
    return sorted(unity, key=lambda d: stamp_of(d) or d.name), sorted(bridge, key=lambda d: stamp_of(d) or d.name)


def runs_of_unity(u: Path) -> list[int]:
    return sorted(int(f.name[9:12]) for f in u.glob("truth_run[0-9][0-9][0-9].json"))


def runs_of_bridge(b: Path) -> list[int]:
    return sorted(int(re.search(r"(\d{3})", f.name).group(1)) for f in b.glob("python_trial_[0-9][0-9][0-9].json"))


def pair_sessions(unity: list[Path], bridge: list[Path]) -> list[tuple[Path, Path]]:
    """Each Unity session gets the bridge folder that started last before it (bridge and Unity folder names end in their start time); each bridge is used once; the runs
    of the two must be the same. Anything else is refused: nothing is guessed."""
    if len(unity) != len(bridge):
        raise pf.StepFailed(f"{len(unity)} Unity sessions but {len(bridge)} bridge folders: cannot be paired")
    used, out = set(), []
    for u in unity:
        su = stamp_of(u)
        cands = [b for b in bridge if b not in used and stamp_of(b) and su and stamp_of(b) <= su]
        if not cands:
            raise pf.StepFailed(f"{u.name}: no bridge folder started before it")
        b = max(cands, key=lambda d: stamp_of(d))
        if runs_of_unity(u) != runs_of_bridge(b):
            raise pf.StepFailed(f"{u.name} (runs {runs_of_unity(u)}) and {b.name} (runs {runs_of_bridge(b)}) do not cover the same runs: not paired")
        used.add(b)
        out.append((u, b))
    return out


def provenance(u: Path, b: Path, setting: str, repo: Path) -> dict:
    """The session's commit and the hashes of its config_used files, compared (reported, not required) with the frozen record and the setting's final control file."""
    frozen = fz.read(repo)
    sj = json.loads((u / "session.json").read_text(encoding="utf-8"))
    files = {}
    for f in sorted((b / "config_used").glob("*")):
        if f.is_file():
            h = sha_lf(f)
            rel = [k for k in frozen.get("sha256", {}) if Path(k).name == f.name]
            files[f.name] = {"sha256": h, "equals_frozen_record": (frozen["sha256"][rel[0]] == h) if rel else None}
    return {"unity_session": u.name, "bridge": b.name, "git_commit": sj.get("git_commit"), "git_branch": sj.get("git_branch"), "config_used": files,
            "config_files_equal_to_the_frozen_record": sum(1 for v in files.values() if v["equals_frozen_record"] is True),
            "config_files_that_differ_from_the_frozen_record": sorted(k for k, v in files.items() if v["equals_frozen_record"] is False),
            "config_files_not_in_the_frozen_record": sorted(k for k, v in files.items() if v["equals_frozen_record"] is None)}


def check_session(u: Path, b: Path, repo: Path) -> tuple[str, str, list[str]]:
    """(setting, look, problems). The look is read from the truth files; the S1 guard (guard_run) is applied again when the runs are loaded."""
    plan = fg.plan(repo)
    sj = json.loads((u / "session.json").read_text(encoding="utf-8"))
    problems = []
    if sj.get("supplementary") != NAME:
        problems.append(f"session.json supplementary is {sj.get('supplementary')!r}, not {NAME!r}")
    if sj.get("seed") != SEED:
        problems.append(f"seed {sj.get('seed')} (S1 runs seed {SEED})")
    setting = setting_of(sj, plan)
    if setting is None:
        problems.append(f"the setting is not one of {list(SETTINGS)} (final_setting {sj.get('final_setting')!r}, experiment {sj.get('experiment')!r})")
    if sj.get("timeout_s") not in (None, TIMEOUT_S):
        problems.append(f"timeout {sj.get('timeout_s')} s (S1: {TIMEOUT_S:g} s)")
    if runs_of_unity(u) != list(range(1, RUNS + 1)):
        problems.append(f"runs {runs_of_unity(u)}, expected 1..{RUNS}")
    if setting in PLAN_RUNS and sj.get("plan_runs") != PLAN_RUNS[setting]:
        problems.append(f"session.json plan_runs {sj.get('plan_runs')!r}, declared for {setting}: {PLAN_RUNS[setting]} (AUDIT.md 16.37)")
    gcfg = gd.load_config(repo / "robot_vision/configs/v4/gesture_data.json")
    looks = set()
    for r in sorted(u.glob("run_[0-9][0-9][0-9]")):
        looks |= {t.look for t in gd.load_truth(r / "truth.jsonl", gcfg)}
    if len(looks) != 1 or not looks <= set(LOOKS):
        problems.append(f"looks {sorted(looks)}: S1 sessions have ONE look, one of {list(LOOKS)}")
    try:
        leak = gt_path.session_leak_check(u, gt_path.load_config(repo / "robot_vision/configs/v4/gt_eval.json"))
        if not leak["passed"]:
            problems.append("leak test did not pass: " + "; ".join(leak["reasons"]))
    except (SystemExit, ValueError, OSError) as e:
        problems.append(f"leak test: {e}")
    return setting or "?", (sorted(looks) or ["?"])[0], problems


# ---------------------------------------------------------------- evaluation and tables

def evaluate_session(u: Path, b: Path, setting: str, repo: Path) -> dict:
    gcfg, ecfg = gd.load_config(repo / "robot_vision/configs/v4/gesture_data.json"), ev.load_config(repo / "robot_vision/configs/v4/eval_dev.json")
    splits = ds.load(repo / "robot_vision/configs/v4/data_splits.json")
    runs = ev.load_sessions([(u, b)], gcfg, splits, settings=[setting], supplementary=NAME)      # the S1 guard; no frozen.json needed
    rows, dialogs = ex.build_tables(runs, ecfg, splits)
    plan_runs = json.loads((u / "session.json").read_text(encoding="utf-8")).get("plan_runs") or []
    for r in rows:
        r["plan_run"] = plan_runs[int(r["trial"]) - 1] if 0 < int(r["trial"]) <= len(plan_runs) else None
    return {"setting": setting, "runs": rows, "dialogs": [{k: ex._fmt(v) for k, v in d.items()} for d in dialogs]}


def cell_rows(sessions: dict, z: float) -> list[dict]:
    out = []
    for (setting, look), d in sorted(sessions.items(), key=lambda kv: (kv[0][1], kv[0][0])):
        r, dl = d["runs"], d["dialogs"]
        k = sum(x["outcome"] == "SUCCESS" for x in r)
        t_ok = fr.floats([x for x in r if x["outcome"] == "SUCCESS"], "time_s")
        asks = [x for x in dl if x.get("command_read") not in ("", None) or x.get("command_shown") not in ("", None)]
        ka = sum(x.get("command_read") == x.get("command_shown") for x in asks)
        ts, fs = [x.get("stop_gestures_true") for x in r], [x.get("stop_gestures_false") for x in r]
        have = [x for x in ts if x is not None]
        out.append({"character": look, "scene": setting, "n": len(r), "successes": k, **fr.wilson_cell(k, len(r), z),
                    **{f"failed_{f}": sum(x["failure_reason"] == f for x in r if x["outcome"] != "SUCCESS") for f in ("wrong_goal", "aborted", "timeout", "collision")},
                    "aborts": sum(x["failure_reason"] == "aborted" for x in r), "median_time_s_success": fr.pct(t_ok, 50),
                    "asks": len(asks), "asks_read_as_shown": ka, "asks_read_as_shown_rate": round(ka / len(asks), 4) if asks else fr.ND,
                    **{"asks_wilson_" + k_: v for k_, v in fr.wilson_cell(ka, len(asks), z).items() if k_ != "rate"},
                    "stop_episodes_true": int(sum(x for x in ts if x is not None)) if have else fr.ND,
                    "stop_episodes_false": int(sum(x for x in fs if x is not None)) if have else fr.ND})
    return out


def lie_rows(sessions: dict) -> list[dict]:
    """B3 only: lies given / detected / corrected / fooled per character, the first person asked at a visit and later ones apart (final_results_v4.lie_split)."""
    out = []
    for (setting, look), d in sorted(sessions.items(), key=lambda kv: (kv[0][1], kv[0][0])):
        if setting != "B3":
            continue
        sp = fr.lie_split(d["dialogs"])
        for g in ("first", "later"):
            out.append({"character": look, "scene": setting, "asked": g, **sp[g]})
        out.append({"character": look, "scene": setting, "asked": "all", **{k: sp["first"][k] + sp["later"][k] for k in sp["first"]}})
    return out


def baseline_outcomes(finals_root: Path, setting: str) -> dict[int, tuple[bool, str]]:
    """plan run -> (success, goal) of the Sunbox final of the setting (the export's runs.csv: its trial is the plan run). Read only."""
    m = fg.markers(finals_root, setting, "export")
    if len(m) != 1:
        raise pf.StepFailed(f"{setting}: {len(m)} final export folders in {finals_root}: the comparison needs exactly one")
    return {int(r["trial"]): (r["outcome"] == "SUCCESS", r.get("goal", "")) for r in fr.read_csv(m[0].parent / "runs.csv")}


def comparison_rows(sessions: dict, finals_root: Path, z: float) -> tuple[list[dict], list[dict]]:
    """Each S1 cell against the Sunbox final of the same scene on the SAME plan runs (same seed, same goals, same worker and lie schedule): paired by plan run; the rates with Newcombe
    95 % for the difference (S1 minus final), and the four combinations per cell. A run whose goal differs from the final's goal for its plan run is refused."""
    rates, pairs = [], []
    for (setting, look), d in sorted(sessions.items(), key=lambda kv: (kv[0][1], kv[0][0])):
        fin = baseline_outcomes(finals_root, setting)
        s1 = {}
        for x in d["runs"]:
            pr = x.get("plan_run")
            if pr not in fin:
                raise pf.StepFailed(f"{setting} {look} run {x['trial']}: plan run {pr} is not in the Sunbox final of {setting}")
            if fin[pr][1] and x.get("goal") and fin[pr][1] != x["goal"]:
                raise pf.StepFailed(f"{setting} {look} run {x['trial']}: goal {x['goal']} but the final plan's goal for plan run {pr} is {fin[pr][1]}")
            s1[pr] = x["outcome"] == "SUCCESS"
        idx = sorted(s1)
        ks, kf = sum(s1[i] for i in idx), sum(fin[i][0] for i in idx)
        nc = ex.newcombe(kf, len(idx), ks, len(idx), z)
        ws, wf = ex._wilson(ks, len(idx), z), ex._wilson(kf, len(idx), z)
        rates.append({"character": look, "scene": setting, "plan_runs": " ".join(map(str, idx)), "S1 successes": ks, "S1 rate": ws["ratio"], "S1 wilson95": ws["wilson95"],
                      "Sunbox final successes (same plan runs)": kf, "Sunbox rate": wf["ratio"], "Sunbox wilson95": wf["wilson95"],
                      "difference_pp (S1 - Sunbox)": nc["difference_pp"], "newcombe_lo_pp": nc["lo_pp"], "newcombe_hi_pp": nc["hi_pp"]})
        pairs.append({"character": look, "scene": setting, "both_succeed": sum(s1[i] and fin[i][0] for i in idx), "only_S1_succeeds": sum(s1[i] and not fin[i][0] for i in idx),
                      "only_Sunbox_succeeds": sum(fin[i][0] and not s1[i] for i in idx), "neither": sum(not s1[i] and not fin[i][0] for i in idx),
                      "plan_runs_failed_in_S1": ", ".join(str(i) for i in idx if not s1[i]) or "none"})
    return rates, pairs


def confusion_tables(sessions: dict, out: Path, cfg: dict) -> None:
    """Gesture (command shown vs read) and branch (true vs read) confusion per character x scene, and pooled per scene (a pooled matrix mixes characters)."""
    for stem, title, shown, read, labels in (("s1_e_gesture_confusion", "S1 gesture confusion: command shown vs read", "command_shown", "command_read", cfg["gesture_labels"]),
                                            ("s1_f_branch_confusion", "S1 branch confusion: true branch vs branch read", "true_branch", "branch_read", cfg["branch_labels"])):
        mats = {}
        for scene in sorted({s for s, _ in sessions}):
            mats[f"{scene}: all characters (pooled)"] = pf.confusion([x for (s, _), d in sessions.items() if s == scene for x in d["dialogs"]], shown, read, labels)
            for (s, look), d in sorted(sessions.items(), key=lambda kv: kv[0][1]):
                if s == scene:
                    mats[f"{scene}: {look}"] = pf.confusion(d["dialogs"], shown, read, labels)
        pf.write_matrix(out, stem, title, mats, shown, read)


# ---------------------------------------------------------------- the tool

def outside(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return False
    except ValueError:
        return path.resolve() != root.resolve()


def run(zip_path, sha256: str, repo: Path | None = None, finals_root: str | Path | None = None, out_root: str | Path | None = None, config: str | Path | None = None,
        work_root: str | Path | None = None) -> tuple[int, Path, pf.Report]:
    cfg = pf.load_config(config)
    repo = Path(repo) if repo else fz.REPO
    zpath = Path(zip_path)
    finals = pf._root(str(finals_root or cfg["final_root"]))
    root = pf._root(str(out_root or cfg["supplementary_root"]))
    report = pf.Report(zpath, False, "process_supplementary_zip_v4", "Sessions")
    failed, work = None, None
    if not outside(root, finals) or root == finals:
        raise SystemExit(f"--out-root {root} is the finals' root or inside it: S1 never writes into the finals' results")
    root.mkdir(parents=True, exist_ok=True)
    out = pf.new_report_dir(root, "process_supplementary_zip_v4")
    try:
        got, warnings, meta = pf.verify_zip_hash(zpath, sha256)
        folders = list(meta.get("folders") or [])
        if not folders:
            raise pf.StepFailed("MANIFEST.json has no 'folders': not a zip made by final_zip_v4.py avatar")
        report.settings = folders
        report.add(1, "verify", pf.OK, f"SHA-256 {got[:12]}... matches; testzip and MANIFEST.json agree; folders {', '.join(folders)}" + (f"; warning: {'; '.join(warnings)}" if warnings else ""), sha256=got)
        work = Path(tempfile.mkdtemp(prefix="s1_zip_", dir=str(work_root) if work_root else None))
        pf.copy_out(zpath, meta, [{"setting": NAME, "label": "avatar", "unity": folders, "bridge": [], "markers": []}], work)
        unity, bridge = classify_folders(work, folders)
        pairs = pair_sessions(unity, bridge)
        sessions, prov, z = {}, [], ex.wilson_z(repo)
        for u, b in pairs:
            setting, look, problems = check_session(u, b, repo)
            report.add(2, f"session {u.name}", pf.FAIL if problems else pf.OK, "; ".join(problems) or f"{setting}, look {look}, {RUNS} runs, seed {SEED}; bridge {b.name}")
            if problems:
                raise pf.StepFailed(f"{u.name}: " + "; ".join(problems))
            if (setting, look) in sessions:
                raise pf.StepFailed(f"two sessions of {setting} with the look {look}: S1 has one session per setting and look")
            sessions[(setting, look)] = {**evaluate_session(u, b, setting, repo)}
            prov.append({"setting": setting, "look": look, **provenance(u, b, setting, repo)})
        report.add(3, "evaluate", pf.OK, f"{len(sessions)} sessions evaluated with the S1 guard (frozen.json not required, no final marker written)")
        fr.write_table(out, "s1_a_per_character_and_scene", "S1 (supplementary, exploratory; NOT pooled with the finals): success, failure reasons, asks read as shown, aborts, STOP episodes",
                       cell_rows(sessions, z), "Success with Wilson 95 % (n = 5 runs per cell: very wide); asks read as shown = the command read equals the command shown (ask level: asks within a run are "
                       "not independent). Post-freeze and exploratory: reported in its own section, never pooled with the A/B finals. Cells present: " + ", ".join(f"{l}/{s}" for (s, l) in sorted(sessions, key=lambda k: (k[1], k[0]))) +
                       ("; missing: " + ", ".join(f"{l}/{s}" for l in LOOKS for s in SETTINGS if (s, l) not in sessions) if len(sessions) < len(LOOKS) * len(SETTINGS) else "."))
        fr.write_table(out, "s1_b_lies_B3", "S1 B3: lies given / detected / corrected / fooled per character", lie_rows(sessions),
                       "Definitions of export_csv_v4 (detected = rejected, outvoted or withdrawn; corrected = detected and the branch finally taken is the true one; fooled = accepted, taken, not true). "
                       "first = the first person asked at a visit; later = a later one.")
        confusion_tables(sessions, out, cfg)
        rates, pr = comparison_rows(sessions, finals, z)
        fr.write_table(out, "s1_c_vs_sunbox_finals", "S1 against the Sunbox finals of the same scene on the same plan runs: paired by plan run (same seed, goals, worker and lie schedule), Newcombe 95 %", rates,
                       "Difference = S1 minus the Sunbox final, percentage points. Description only: no test, no claim of significance.")
        fr.write_table(out, "s1_c2_paired_outcomes", "S1 against the Sunbox finals: the four combinations per plan run", pr)
        fr.write_table(out, "s1_d_provenance", "Session provenance (commit and config_used hashes; S1 does not require frozen.json to match)",
                       [{"scene": p["setting"], "character": p["look"], "unity_session": p["unity_session"], "bridge": p["bridge"], "git_commit": p["git_commit"], "git_branch": p["git_branch"],
                         "config_files": len(p["config_used"]), "equal_to_frozen_record": p["config_files_equal_to_the_frozen_record"],
                         "differ_from_frozen_record": ", ".join(p["config_files_that_differ_from_the_frozen_record"]) or "none",
                         "not_in_frozen_record": ", ".join(p["config_files_not_in_the_frozen_record"]) or "none"} for p in prov])
        (out / "provenance.json").write_text(json.dumps(prov, indent=2) + "\n", encoding="utf-8")
        report.add(4, "tables", pf.OK, "s1_a, s1_b (lies), s1_e / s1_f (confusion), s1_c / s1_c2 (paired Sunbox baseline), s1_d (provenance) as CSV and Markdown")
        bad = [str(p) for name in FINAL_MARKERS for p in out.rglob(name)]
        if bad:
            raise pf.StepFailed(f"a final marker exists in the S1 output: {bad}")
        report.add(0, "no final marker", pf.OK, "no FINAL_*.json in the S1 output; the finals' folders were only read")
    except pf.StepFailed as e:
        failed = str(e)
        report.add(99, "STOPPED", pf.FAIL, failed)
    except SystemExit as e:
        failed = str(e)
        report.add(99, "STOPPED", pf.FAIL, failed)
    finally:
        if work is not None:
            shutil.rmtree(work, ignore_errors=True)
    report.write(out, failed)
    return (1 if failed else 0), out, report


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("zip")
    ap.add_argument("--sha256", required=True)
    ap.add_argument("--finals-root", default=None, help="the finals' root (read only; default: final_root of configs/v4/experiments/phase_b.json)")
    ap.add_argument("--out-root", default=None, help="where the results folder is made (default: supplementary_root of the config; never the finals' root)")
    ap.add_argument("--config", default=None)
    a = ap.parse_args(argv)
    code, out, _ = run(a.zip, a.sha256, finals_root=a.finals_root, out_root=a.out_root, config=a.config)
    print(f"results: {out}")
    return code


if __name__ == "__main__":
    sys.exit(main())
