"""Run-once guards for the v4 final settings (since 2026-11-14 the 13 settings of the experiments A/B: A1, A2_right, A2_left, A3, A4,
B1, B2_right, B3, B4 and the detection-off B1_off, B2_right_off, B3_off, B4_off; configs/v4/final_plan.json, AUDIT.md 16.15), the Python
side of v3's FINAL_DONE.json. A final cannot be repeated silently.

Three markers, all written with mode 'x' (never overwritten), found by scanning every folder under the output root:
- FINAL_RUN_DONE.json in a bridge run folder: the server ran the setting in final mode (bridge.server --final-setting NAME)
  and finished at least one trial. A setting with this marker cannot be started again.
- FINAL_DONE.json in a final-evaluation folder (hri_eval_final_v4_<setting>_<time>/): the setting was evaluated. It cannot be
  evaluated again. (hri_analysis_v4.py only describes the data and may be re-run into a new folder.)
- FINAL_EXPORT_DONE.json in a final CSV export folder (export_csv_v4_final_<setting>_<time>/): the setting's runs.csv / dialogs.csv
  were written; its own marker, so that exporting does not block evaluating and the other way round.
A started run or evaluation that did not finish writes no marker and does not block (as in v3).

Interruptions (AUDIT.md 16.30.1): a final of a setting that was STARTED (FINAL_SETTING.json in its bridge folder, written before the first trial)
cannot be started again silently, whether or not FINAL_RUN_DONE.json exists. An infrastructure failure (server, Unity or machine dies before a
run finishes) is declared with `python final_guard_v4.py --declare-interruption SETTING --run K ...` (FINAL_INTERRUPTION.json); the session may
then be resumed ONCE from run K (the server's --resume-marker writes FINAL_RESUME.json); a second interruption makes the setting invalid
(FINAL_INVALID.json). `python final_guard_v4.py --status` lists every setting's state. The evaluation and the export score a resumed setting
as one session (resume_plan).

check_setting: a final session must be what its setting says (zoom flag, bystanders, number of runs, seed, task, Unity mode
final; for an experiment setting also its looks and clips, the control file the bridge ran with and the experiment and set Unity
recorded), from configs/v4/final_plan.json. timeout_from_development, development_timeout: the declared timeout rule (AUDIT.md 16.15 decision 2, corrected in 16.16 decision 4).
Reporting/evaluation code; inference code never imports it.

Command line (AUDIT.md 16.20.5.1): python final_guard_v4.py --timeout-from SOURCE [SOURCE ...] [--prefix t0_] [--runs-per-setting 3] [--out FILE]
pools the step-5 development runs of ALL 13 settings once, lists every run that is excluded from the rule with its outcome, and prints the timeout the
rule gives. SOURCE: the step-5 zip of finals_v4/step5_zip_v4.py (read in place), the step-5 manifest (outputs/step5_sessions.json), or NAME=<Unity session
folder> (e.g. t0_A3=outputs/trials_development_Task2_...). It computes the number only; final_plan.json is not edited.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import sys
import zipfile
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
PLAN = "robot_vision/configs/v4/final_plan.json"
MARKERS = {"run": "FINAL_RUN_DONE.json", "evaluation": "FINAL_DONE.json", "export": "FINAL_EXPORT_DONE.json",
           "started": "FINAL_SETTING.json", "interruption": "FINAL_INTERRUPTION.json", "resume": "FINAL_RESUME.json", "invalid": "FINAL_INVALID.json",
           "superseded": "FINAL_EVAL_SUPERSEDED.json"}
SUPERSEDED_PREFIX = "final_eval_superseded"
INTERRUPTION_PREFIX = "final_interruption"
INVALID_PREFIX = "final_invalid"
SCENARIOS = "robot_vision/configs/v4/experiments/scenarios_ab.json"
LIE_RULES = ("second_opinion", "reject_impossible", "backtrack")        # the a / b / c rules of the experiments (export_csv_v4.lie_detection_label letters)
# AUDIT.md 16.25.2 (T4: 16.24.3, 16.25, 16.25.1), replaced by 16.26.9: the checkpoint workers are NOT used in the finals. Every key listed in final_plan.json lie_detection_checkpoint must have the
# plan's value (OFF for every setting): a control file with any checkpoint key on is refused. checkpoint_s_m (the per-branch spot of 16.26 item 1) is a checkpoint key too.
CHECKPOINT_SWITCHES = ("checkpoint", "checkpoint_fraction", "checkpoint_scope", "checkpoint_person_radius_m", "checkpoint_branches", "checkpoint_s_m", "next_junction_back")
SWITCHES = LIE_RULES + CHECKPOINT_SWITCHES
EVAL_PREFIX = "hri_eval_final_v4"
EXPORT_PREFIX = "export_csv_v4_final"


def plan(repo: Path = REPO) -> dict:
    return json.loads((repo / PLAN).read_text(encoding="utf-8"))


def settings(repo: Path = REPO) -> list[str]:
    return list(plan(repo)["settings"])


def check_name(setting: str, repo: Path = REPO) -> None:
    if setting not in settings(repo):
        raise SystemExit(f"unknown final setting {setting!r}; the plan has {settings(repo)}")


def markers(output_root: str | Path, setting: str, kind: str) -> list[Path]:
    """Marker files of this kind and setting in any folder directly under the output root."""
    found = []
    root = Path(output_root)
    if not root.is_dir():
        return found
    for d in sorted(root.iterdir()):
        m = d / MARKERS[kind]
        if d.is_dir() and m.is_file():
            try:
                rec = json.loads(m.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            if rec.get("setting") == setting:
                found.append(m)
    if kind == "evaluation" and found:           # AUDIT.md 16.35.1: an evaluation that a declaration supersedes (wrong map, crashed) no longer blocks; nothing else is unlocked
        gone = set()
        for d in root.iterdir():
            m = d / MARKERS["superseded"]
            if d.is_dir() and m.is_file():
                try:
                    rec = json.loads(m.read_text(encoding="utf-8"))
                except (OSError, ValueError):
                    continue
                if rec.get("setting") == setting:
                    gone.add(rec.get("superseded_folder"))
        found = [m for m in found if m.parent.name not in gone]
    return found


def declare_evaluation_superseded(setting: str, folder_name: str, reason: str, output_root, repo: Path = REPO) -> Path:
    """AUDIT.md 16.35.1: declare that the evaluation in folder_name (a folder directly under the output root with a FINAL_DONE.json of this setting) is
    superseded (it used the wrong map, or crashed). It stays untouched; markers() no longer counts it, so the setting can be evaluated once more. Never
    for an export, never twice for one folder, never without a reason. Writes <root>/final_eval_superseded_<setting>_<time>/FINAL_EVAL_SUPERSEDED.json."""
    check_name(setting, repo)
    root = Path(output_root)
    if not (reason or "").strip():
        raise SystemExit("--reason is required")
    old = root / folder_name
    done = old / MARKERS["evaluation"]
    if not done.is_file() or json.loads(done.read_text(encoding="utf-8")).get("setting") != setting:
        raise SystemExit(f"{folder_name}: not an evaluation folder of {setting!r} (no {MARKERS['evaluation']} for it)")
    for m in root.glob(f"*/{MARKERS['superseded']}"):
        rec = json.loads(m.read_text(encoding="utf-8"))
        if rec.get("setting") == setting and rec.get("superseded_folder") == folder_name:
            raise SystemExit(f"{folder_name} is already superseded ({m.parent.name})")
    out = root / f"{SUPERSEDED_PREFIX}_{setting}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    out.mkdir()
    return write_done(out, setting, "superseded", {"superseded_folder": folder_name, "reason": reason.strip()})


def ensure_not_done(output_root: str | Path, setting: str, kind: str, repo: Path = REPO) -> None:
    """SystemExit if this setting was already run (kind 'run'), evaluated ('evaluation') or exported ('export') as a final."""
    check_name(setting, repo)
    done = markers(output_root, setting, kind)
    if done:
        what = {"run": "run", "evaluation": "evaluated", "export": "exported"}[kind]
        raise SystemExit(f"final setting {setting!r} was already {what} as a final: {done[0].parent.name}/{done[0].name}. "
                         "Finals are run once; the earlier result stands (disclose any repetition in AUDIT.md section 14 first).")


def write_done(folder: str | Path, setting: str, kind: str, info: dict | None = None) -> Path:
    """Write the marker (never overwrites)."""
    p = Path(folder) / MARKERS[kind]
    rec = {"setting": setting, "kind": kind, "written": datetime.now().isoformat(timespec="seconds"), **(info or {})}
    with p.open("x", encoding="utf-8") as f:
        f.write(json.dumps(rec, indent=2, default=str) + "\n")
    return p


# ---------------------------------------------------------------- interruptions and the one resume (AUDIT.md 16.30.1)

def frozen_sha256(repo: Path = REPO) -> str:
    import freeze_v4 as fz
    return fz.sha256_lf(repo / fz.FROZEN_REL)


def _read(path) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _all_markers(output_root, setting: str) -> dict:
    return {k: markers(output_root, setting, k) for k in MARKERS}


def _marker_file(path, kind: str) -> Path:
    """A marker given as the file or as the folder that holds it."""
    p = Path(path)
    if p.is_dir():
        p = p / MARKERS[kind]
    if not p.is_file():
        raise SystemExit(f"{path}: no {MARKERS[kind]} there")
    return p


def completed_runs(unity_folder) -> list[int]:
    """The runs of a Unity session folder that have an outcome: truth_run###.json exists (Unity writes it when a run ends)."""
    return sorted(int(f.name[9:12]) for f in Path(unity_folder).glob("truth_run[0-9][0-9][0-9].json"))


def check_start(output_root, setting: str, resume_marker=None, frozen_sha: str | None = None, repo: Path = REPO) -> dict | None:
    """Called by the server before a final starts (bridge.server.preflight_final). SystemExit unless this start is allowed. Returns None for a
    fresh start, or the declaration (FINAL_INTERRUPTION.json content) when this start is the declared resume."""
    check_name(setting, repo)
    m = _all_markers(output_root, setting)
    if m["invalid"]:
        raise SystemExit(f"final setting {setting!r} was declared invalid ({m['invalid'][0].parent.name}): it is reported as invalid and never rerun.")
    for kind, what in (("evaluation", "evaluated"), ("export", "exported")):
        if m[kind]:
            raise SystemExit(f"final setting {setting!r} was already {what} as a final ({m[kind][0].parent.name}): no start and no resume after that.")
    if not (m["started"] or m["run"]):                                 # nothing started yet
        if resume_marker is not None:
            raise SystemExit(f"--resume-marker: no final of {setting!r} was started, so there is nothing to resume.")
        return None
    where = (m["started"] or m["run"])[0].parent.name
    if not m["interruption"]:
        raise SystemExit(
            f"final setting {setting!r} was already run as a final (started: {where}). Finals are run once: the earlier run stands. If an infrastructure failure "
            f"(server, Unity or machine) ended it before a run finished, declare it first: python final_guard_v4.py --declare-interruption {setting} "
            "--run K --reason TEXT --evidence PATH ... --unity-folder U --bridge-folder B (AUDIT.md 16.30.1).")
    if len(m["interruption"]) > 1:
        raise SystemExit(f"final setting {setting!r} has more than one declared interruption: the setting is not started again; report it.")
    if m["resume"]:
        raise SystemExit(
            f"final setting {setting!r} was already resumed once ({m['resume'][0].parent.name}). A second resume is never made. If the resumed part was "
            "interrupted too, declare it with --declare-interruption: the setting becomes invalid and is reported as such (B11).")
    if resume_marker is None:
        raise SystemExit(f"an interruption of {setting!r} is declared ({m['interruption'][0].parent.name}): start the resume with "
                         f"--resume-marker {m['interruption'][0].parent.name} (once, from run {_read(m['interruption'][0])['resume_from_run']}).")
    given = _marker_file(resume_marker, "interruption")
    if given.resolve() != m["interruption"][0].resolve():
        raise SystemExit(f"--resume-marker {resume_marker} is not the declaration of {setting!r} ({m['interruption'][0].parent.name}).")
    rec = _read(given)
    if frozen_sha is not None and rec.get("frozen_sha256") != frozen_sha:
        raise SystemExit(f"configs/v4/frozen.json changed since the interruption of {setting!r} was declared: the resume is refused.")
    return rec


def resume_info(output_root, setting: str, repo: Path = REPO) -> dict:
    """What the launcher needs to resume a declared interruption (AUDIT.md 16.31.2 item 3): the run to resume from (Unity's -StartRun k), the
    declaration folder (the server's --resume-marker), and the seed and goal order the declaration recorded (Unity compares its own with
    them). SystemExit with the reason when no resume is allowed: nothing started, no declaration, already resumed, invalid, evaluated or exported."""
    check_name(setting, repo)
    m = _all_markers(output_root, setting)
    if m["invalid"]:
        raise SystemExit(f"{setting}: declared invalid ({m['invalid'][0].parent.name}): no resume.")
    for kind, what in (("evaluation", "evaluated"), ("export", "exported")):
        if m[kind]:
            raise SystemExit(f"{setting}: already {what} ({m[kind][0].parent.name}): no resume.")
    if not (m["started"] or m["run"]):
        raise SystemExit(f"{setting}: no final was started: there is nothing to resume (start it normally).")
    if not m["interruption"]:
        raise SystemExit(f"{setting}: no interruption is declared: declare it first (final_guard_v4.py --declare-interruption), then ask again.")
    if len(m["interruption"]) > 1:
        raise SystemExit(f"{setting}: more than one declared interruption: no resume.")
    if m["resume"]:
        raise SystemExit(f"{setting}: already resumed once ({m['resume'][0].parent.name}): a second resume is never made; declare the second "
                         "interruption (the setting becomes invalid).")
    d = _read(m["interruption"][0])
    return {"setting": setting, "resume_from_run": d["resume_from_run"], "resume_marker": m["interruption"][0].parent.name,
            "seed": d.get("seed"), "goal_order": d.get("goal_order"), "part_1": {"unity": d["unity_folder"], "bridge": d["bridge_folder"]},
            "frozen_sha256": d.get("frozen_sha256")}


def write_resume(folder, setting: str, declaration: dict, declaration_folder: str, frozen_sha: str) -> Path:
    """The server writes this into the bridge folder of the resumed run, before the first trial (never overwrites)."""
    return write_done(folder, setting, "resume", {"resume_from_run": declaration["resume_from_run"], "interruption_folder": declaration_folder,
                                                  "frozen_sha256": frozen_sha})


def _evidence_record(evidence, output_root) -> list[dict]:
    out, root = [], Path(output_root).resolve()
    for e in evidence:
        p = Path(e)
        if not p.exists():
            raise SystemExit(f"evidence {e}: not found")
        files = [p] if p.is_file() else sorted(q for q in p.rglob("*") if q.is_file())
        for q in files:
            try:
                shown = q.resolve().relative_to(root).as_posix()
            except ValueError:
                shown = q.name + " (outside the output root: send it with the zip)"
            out.append({"path": shown, "bytes": q.stat().st_size, "sha256": hashlib.sha256(q.read_bytes()).hexdigest()})
    if not out:
        raise SystemExit("the evidence is empty: name the Event Viewer export, the crash log or the server and Unity logs")
    return out


def _check_part(setting: str, unity: Path, bridge: Path, first_run: int, run: int) -> dict:
    """Runs first_run to run-1 have an outcome and a python_trial file, run has no outcome, nothing is later; returns Unity's session.json."""
    if not unity.is_dir() or not (unity / "session.json").is_file():
        raise SystemExit(f"--unity-folder {unity}: not a Unity session folder (no session.json)")
    if not (bridge / MARKERS["started"]).is_file() or _read(bridge / MARKERS["started"]).get("setting") != setting:
        raise SystemExit(f"--bridge-folder {bridge}: not a bridge run folder of the final {setting!r} (no FINAL_SETTING.json for it)")
    session = _read(unity / "session.json")
    if session.get("final_setting") not in (None, "", setting):
        raise SystemExit(f"{unity.name}: Unity ran final setting {session['final_setting']!r}, not {setting!r}")
    done = completed_runs(unity)
    if done != list(range(first_run, run)):
        raise SystemExit(f"{unity.name}: runs with an outcome are {done}, but an interruption of run {run} needs exactly runs {first_run} to {run - 1} "
                         f"(a run that has an outcome is a result, not an interruption; run {run} must have none)")
    missing = [i for i in done if not (bridge / f"python_trial_{i:03d}.json").is_file()]
    if missing:
        raise SystemExit(f"{bridge.name}: runs {missing} have an outcome in Unity but no python_trial file: not declared; ask Anisha")
    for key in ("seed", "goal_order"):
        if session.get(key) in (None, []):
            raise SystemExit(f"{unity.name}: session.json has no {key}: the resume could not be checked")
    return session


def declare_interruption(setting: str, run: int, reason: str, evidence: list, unity_folder, bridge_folder, output_root, repo: Path = REPO) -> Path:
    """Declare an infrastructure interruption of the final of this setting before run `run` finished (AUDIT.md 16.30.1). Writes
    <output_root>/final_interruption_<setting>_<time>/FINAL_INTERRUPTION.json, or, when the setting was already resumed once, the second
    interruption: <output_root>/final_invalid_<setting>_<time>/FINAL_INVALID.json. Returns the marker. SystemExit when refused."""
    check_name(setting, repo)
    n = int(plan(repo)["runs_per_setting"])
    if not (reason or "").strip():
        raise SystemExit("--reason is required: what failed, in one line")
    if not 1 <= run <= n:
        raise SystemExit(f"--run {run}: the setting has runs 1 to {n}")
    root = Path(output_root)
    m = _all_markers(root, setting)
    if m["invalid"]:
        raise SystemExit(f"{setting!r} is already declared invalid ({m['invalid'][0].parent.name})")
    for kind, what in (("evaluation", "evaluated"), ("export", "exported")):
        if m[kind]:
            raise SystemExit(f"{setting!r} was already {what} ({m[kind][0].parent.name}): an interruption is not declared after that")
    if not (m["started"] or m["run"]):
        raise SystemExit(f"no final of {setting!r} was started (no FINAL_SETTING.json under {root}): nothing to declare")
    if len(m["interruption"]) > 1:
        raise SystemExit(f"{setting!r} has more than one declared interruption")
    unity, bridge = Path(unity_folder), Path(bridge_folder)
    ev_rec = _evidence_record(evidence, root)
    sha = frozen_sha256(repo)
    started_file = bridge / MARKERS["started"]
    if started_file.is_file() and _read(started_file).get("frozen_sha256") != sha:
        raise SystemExit("configs/v4/frozen.json changed since this run started: no declaration")
    base = {"resume_from_run": run, "interrupted_run": run, "reason": reason.strip(), "evidence": ev_rec, "frozen_sha256": sha,
            "unity_folder": unity.name, "bridge_folder": bridge.name, "outcome_of_interrupted_run": "interrupted (infrastructure)"}
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    if m["resume"]:                                                    # the resumed part was interrupted too: the setting is invalid
        resume = _read(m["resume"][0])
        if bridge.resolve() != m["resume"][0].parent.resolve():
            raise SystemExit(f"--bridge-folder must be the resumed run's folder {m['resume'][0].parent.name}")
        k1 = int(resume["resume_from_run"])
        if run < k1:
            raise SystemExit(f"--run {run} is before the resume point {k1}")
        session = _check_part(setting, unity, bridge, k1, run)
        out = root / f"{INVALID_PREFIX}_{setting}_{stamp}"
        out.mkdir()
        return write_done(out, setting, "invalid", {**base, "rule": "second interruption in the same setting (AUDIT.md 16.30.1 rule 5, B11)",
                                                    "first_interruption": m["interruption"][0].parent.name, "resume_folder": m["resume"][0].parent.name,
                                                    "seed": session["seed"]})
    if m["interruption"]:
        raise SystemExit(f"an interruption of {setting!r} is already declared ({m['interruption'][0].parent.name}): resume it once (--resume-marker) "
                         "instead of declaring another")
    starts = [p.parent.resolve() for p in m["started"]]
    if starts != [bridge.resolve()]:
        raise SystemExit(f"--bridge-folder must be the one bridge run folder of the started final ({[p.name for p in map(Path, starts)]})")
    session = _check_part(setting, unity, bridge, 1, run)
    out = root / f"{INTERRUPTION_PREFIX}_{setting}_{stamp}"
    out.mkdir()
    return write_done(out, setting, "interruption", {**base, "seed": session["seed"], "goal_order": session["goal_order"],
                                                     "completed_runs": list(range(1, run))})


def _part_pair(pairs, folder_name: str):
    for u, b in pairs:
        if Path(b).name == folder_name:
            return Path(u), Path(b)
    return None


def resume_plan(output_root, setting: str, pairs, repo: Path = REPO) -> dict:
    """What the evaluation and the export need for a setting that may have been interrupted: {"resumed": bool, "problems": [str], "include":
    callable(unity_dir, trial) -> bool or None, "declaration": dict or None, "interrupted": [{"unity", "run"}]}. No test data is read here (only
    markers and the session.json of each part). Without any interruption marker it returns resumed False and no filter."""
    m = _all_markers(output_root, setting)
    plan_ = {"resumed": False, "problems": [], "include": None, "declaration": None, "resume": None, "interrupted": []}
    pr = plan_["problems"]
    if m["invalid"]:
        pr.append(f"setting declared invalid ({m['invalid'][0].parent.name}: {_read(m['invalid'][0]).get('reason')}): reported as invalid, not evaluated")
    if not m["interruption"]:
        stray = [Path(b).name for _, b in pairs if (Path(b) / MARKERS["resume"]).is_file()]
        if stray or m["resume"]:
            pr.append("a resumed run (FINAL_RESUME.json) without a declared interruption")
        return plan_
    if len(m["interruption"]) > 1:
        pr.append("more than one declared interruption")
        return plan_
    if not m["resume"]:
        pr.append(f"an interruption is declared ({m['interruption'][0].parent.name}) but the session was never resumed: a partial session is not scored; "
                  "it is reported as interrupted")
        return plan_
    if len(m["resume"]) > 1:
        pr.append("more than one resume")
        return plan_
    plan_["resumed"] = True
    decl, resume = _read(m["interruption"][0]), _read(m["resume"][0])
    plan_["declaration"], plan_["resume"] = decl, resume
    k, sha = int(decl["resume_from_run"]), frozen_sha256(repo)
    if len(pairs) != 2:
        pr.append(f"a resumed setting is evaluated as TWO session parts (--session twice), got {len(pairs)}")
    p1, p2 = _part_pair(pairs, decl["bridge_folder"]), _part_pair(pairs, m["resume"][0].parent.name)
    if p1 is None or p2 is None:
        pr.append(f"the parts must be the declaration's bridge folder {decl['bridge_folder']} and the resumed run's {m['resume'][0].parent.name}")
        return plan_
    (u1, b1), (u2, b2) = p1, p2
    if u1.name != decl["unity_folder"]:
        pr.append(f"part 1 Unity folder {u1.name} is not the declaration's {decl['unity_folder']}")
    if u1.resolve() == u2.resolve():
        pr.append("the two parts have the same Unity session folder: the resumed session is a new Unity session")
    if int(resume.get("resume_from_run", -1)) != k or resume.get("interruption_folder") != m["interruption"][0].parent.name:
        pr.append("the resume marker does not answer this declaration (run number or declaration folder differ)")
    shas = {"declaration": decl.get("frozen_sha256"), "resume": resume.get("frozen_sha256"), "now": sha}
    for tag, b in (("part 1", b1), ("part 2", b2)):
        f = b / MARKERS["started"]
        shas[tag] = _read(f).get("frozen_sha256") if f.is_file() else None
    if len(set(shas.values())) != 1:
        pr.append(f"the frozen hashes differ between the parts, the declaration, the resume and now: {shas}")
    try:
        s1, s2 = _read(u1 / "session.json"), _read(u2 / "session.json")
    except (OSError, ValueError) as e:
        pr.append(f"session.json unreadable: {e}")
        return plan_
    if not (s1.get("seed") == s2.get("seed") == decl.get("seed")):
        pr.append(f"the seed differs: part 1 {s1.get('seed')}, part 2 {s2.get('seed')}, declaration {decl.get('seed')}")
    if not (s1.get("goal_order") == s2.get("goal_order") == decl.get("goal_order")):
        pr.append("the goal order differs between part 1, part 2 and the declaration")
    if s2.get("resume_from_run") != k:
        pr.append(f"part 2 session.json records resume_from_run {s2.get('resume_from_run')!r}, the declaration says {k}")
    start = s2.get("start_run")                  # AUDIT.md 16.31.4: Unity's own record of the run it started at must agree (both keys are required; no alias)
    if isinstance(start, bool) or not isinstance(start, int):
        pr.append(f"part 2 session.json records start_run {start!r}: a resumed final needs the whole number start_run equal to resume_from_run {k}")
    elif start != s2.get("resume_from_run"):
        pr.append(f"part 2 session.json records start_run {start} but resume_from_run {s2.get('resume_from_run')!r}: a resumed final must have "
                  f"start_run == resume_from_run (the declaration says {k})")
    if s2.get("resume_of") != u1.name:
        pr.append(f"part 2 session.json records resume_of {s2.get('resume_of')!r}, part 1 is {u1.name}")
    plan_["interrupted"] = [{"unity": u1.name, "run": int(d.name[4:])} for d in sorted(u1.glob("run_[0-9][0-9][0-9]")) if int(d.name[4:]) >= k]
    early = [int(d.name[4:]) for d in sorted(u2.glob("run_[0-9][0-9][0-9]")) if int(d.name[4:]) < k]
    if early:
        pr.append(f"part 2 has runs {early} before the resume point {k}: the resumed session starts at run {k}")
    r1, r2 = u1.resolve(), u2.resolve()
    plan_["include"] = lambda unity, trial: (Path(unity).resolve() == r1 and trial < k) or (Path(unity).resolve() == r2 and trial >= k)
    return plan_


def trial_problems(runs: list, n: int) -> list[str]:
    """After loading a resumed setting: the scored runs are 1 to n, each once."""
    got = sorted(r.trial for r in runs)
    return [] if got == list(range(1, n + 1)) else [f"the scored runs are {got}, a resumed setting needs runs 1 to {n} once each"]


def interruption_report(plan_: dict) -> dict | None:
    """What the evaluation and the export state about an interruption (None when there was none)."""
    d = plan_.get("declaration")
    if not d:
        return None
    return {"resumed": plan_["resumed"], "interrupted_run": d["interrupted_run"], "outcome_of_interrupted_run": d["outcome_of_interrupted_run"],
            "reason": d["reason"], "evidence": d["evidence"], "part_1": {"unity": d["unity_folder"], "bridge": d["bridge_folder"]},
            "interrupted_runs_listed_not_scored": plan_["interrupted"], "scored_as_one_session": plan_["resumed"],
            "resume": plan_.get("resume"), "frozen_sha256": d["frozen_sha256"], "seed": d.get("seed"),
            "rule": "AUDIT.md 16.30.1: completed runs stand; the interrupted run has no outcome and is not scored; one resume from that run"}


def interruption_markdown(rep: dict | None) -> str:
    if not rep:
        return ""
    L = ["## Interruption and resume (AUDIT.md 16.30.1; reported, not hidden)", "",
         f"- Run {rep['interrupted_run']} was interrupted by an infrastructure failure: **{rep['outcome_of_interrupted_run']}**, no outcome, not scored.",
         f"- Reason given: {rep['reason']}",
         f"- Evidence: {', '.join(e['path'] for e in rep['evidence'])}",
         f"- Part 1: {rep['part_1']['unity']} / {rep['part_1']['bridge']}; the session was resumed once from run {rep['interrupted_run']} "
         "(same seed, goal order, configs and frozen hashes, checked) and is scored as one session.",
         "- Interrupted run folders listed, not scored: " + (", ".join(f"{x['unity']}/run_{x['run']:03d}" for x in rep["interrupted_runs_listed_not_scored"]) or "none"), ""]
    return "\n".join(L) + "\n"


def status(output_root, repo: Path = REPO) -> list[dict]:
    """One record per setting: what exists, so that every interruption and resume can be reported."""
    out = []
    for s in settings(repo):
        m = _all_markers(output_root, s)
        rec = {"setting": s, "started_folders": [p.parent.name for p in m["started"]], "run_done": [p.parent.name for p in m["run"]],
               "interruption": None, "resume": [p.parent.name for p in m["resume"]], "invalid": None,
               "evaluated": [p.parent.name for p in m["evaluation"]], "exported": [p.parent.name for p in m["export"]]}
        if m["interruption"]:
            d = _read(m["interruption"][0])
            rec["interruption"] = {"folder": m["interruption"][0].parent.name, "run": d.get("interrupted_run"), "reason": d.get("reason")}
        if m["invalid"]:
            rec["invalid"] = {"folder": m["invalid"][0].parent.name, "reason": _read(m["invalid"][0]).get("reason")}
        rec["state"] = ("invalid" if rec["invalid"] else "resumed" if rec["resume"] else "interrupted (declared, not resumed)" if rec["interruption"]
                        else "started (no declaration)" if rec["started_folders"] or rec["run_done"] else "fresh")
        out.append(rec)
    return out


def status_text(rows: list[dict]) -> str:
    L = [f"{'setting':<16}{'state':<38}{'evaluated':<10}{'exported':<10}details"]
    for r in rows:
        det = []
        if r["interruption"]:
            det.append(f"interrupted run {r['interruption']['run']} ({r['interruption']['folder']}): {r['interruption']['reason']}")
        if r["resume"]:
            det.append("resumed in " + ", ".join(r["resume"]))
        if r["invalid"]:
            det.append(f"INVALID ({r['invalid']['folder']}): {r['invalid']['reason']}")
        L.append(f"{r['setting']:<16}{r['state']:<38}{'yes' if r['evaluated'] else 'no':<10}{'yes' if r['exported'] else 'no':<10}{'; '.join(det)}")
    return "\n".join(L)


def timeout_from_development(longest_s: float, floor_s: float = 270.0, factor: float = 1.5, step_s: float = 30.0) -> float:
    """The declared timeout rule (AUDIT.md 16.15 decision 2, corrected in 16.16 decision 4, final_plan.json timeout_s_rule): factor x the longest
    SUCCESSFUL development run, rounded UP to a multiple of step_s, never below floor_s. final_plan.json keeps 270 until the rule is applied
    by a declared edit. See development_timeout for the runs."""
    if longest_s is None or longest_s <= 0:
        raise ValueError("the longest successful development run must be a positive number of seconds")
    return max(float(floor_s), float(math.ceil(round(factor * longest_s / step_s, 9)) * step_s))


def development_timeout(runs: list[dict], floor_s: float = 270.0, factor: float = 1.5, step_s: float = 30.0) -> dict:
    """Apply the rule to development runs (the dicts of truth_run###.json: outcome, failure_reason, total_s). Only SUCCESSFUL runs give the
    longest duration; every run that failed by timeout is listed (its cause must be found before the freeze, 16.16 decision 4), so is every
    other failure (not a duration, not a timeout). Raises ValueError when no run succeeded: no value can be derived."""
    ok = [float(r["total_s"]) for r in runs if r.get("outcome") == "SUCCESS" and r.get("total_s") is not None]
    if not ok:
        raise ValueError("no successful development run: the timeout cannot be derived")
    timeouts = [r for r in runs if r.get("outcome") != "SUCCESS" and r.get("failure_reason") == "timeout"]
    return {"timeout_s": timeout_from_development(max(ok), floor_s, factor, step_s), "longest_successful_s": max(ok), "successful_runs": len(ok),
            "runs": len(runs), "timeouts": len(timeouts), "timeouts_to_explain": [dict(r) for r in timeouts],
            "other_failures": sum(1 for r in runs if r.get("outcome") != "SUCCESS" and r.get("failure_reason") != "timeout"),
            "cause_needed_before_the_freeze": bool(timeouts)}


def _norm(path) -> str:
    return str(path).replace("\\", "/").lstrip("./") if path is not None else ""


def detection_switches(label: str, repo: Path = REPO) -> dict:
    """The lie-detection switches 'on' or 'off' means (scenarios_ab.json detection; the simulator and the control files equal it)."""
    return json.loads((repo / SCENARIOS).read_text(encoding="utf-8"))["detection"][label]


def checkpoint_switches(label: str, repo: Path = REPO) -> dict:
    """The checkpoint switches a detection 'on' or 'off' setting must have (final_plan.json lie_detection_checkpoint; checkpoint OFF for both since AUDIT.md 16.26.9)."""
    return plan(repo)["lie_detection_checkpoint"][label]


def _same_switch(have, want) -> bool:
    """A switch has the declared value: booleans as booleans (absent = false), everything else equal (absent = None never equals a declared value)."""
    if isinstance(want, bool):
        return bool(have) == want
    return have == want


def control_problems(setting: str, control: dict, repo: Path = REPO) -> list[str]:
    """What is wrong with this control config (the dict of a control file or of a bridge run's config_used/control.json) for the
    setting: its lie-detection switches must be those of the setting's lie_detection (on / off), its checkpoint switches those of the
    same label in final_plan.json lie_detection_checkpoint (checkpoint OFF for every setting; AUDIT.md 16.26.9, it was T4 for the detection-on settings in 16.25.2),
    its side view off (final_plan.json side_view; absent block = off) and its roadmap the setting's map. A setting without those keys (none today) is not constrained."""
    spec = plan(repo)["settings"][setting]
    out = []
    if spec.get("lie_detection") is not None:
        want, have = detection_switches(spec["lie_detection"], repo), control.get("lie_detection", {})
        for k in LIE_RULES:
            if bool(have.get(k)) != bool(want[k]):
                out.append(f"lie_detection.{k} is {bool(have.get(k))} but setting {setting} needs {bool(want[k])} (detection {spec['lie_detection']})")
        cp = checkpoint_switches(spec["lie_detection"], repo)
        for k in CHECKPOINT_SWITCHES:
            if k in cp and not _same_switch(have.get(k), cp[k]):
                out.append(f"lie_detection.{k} is {have.get(k)!r} but setting {setting} needs {cp[k]!r} (detection {spec['lie_detection']}, final_plan.json lie_detection_checkpoint)")
    want_sv = bool(plan(repo).get("side_view", {}).get("enabled", False))                  # AUDIT.md 16.26.9: the side view of 16.26 item 2 stays in the code, off
    if bool((control.get("side_view") or {}).get("enabled", False)) != want_sv:
        out.append(f"side_view.enabled is {bool((control.get('side_view') or {}).get('enabled', False))} but setting {setting} needs {want_sv} (final_plan.json side_view)")
    if spec.get("roadmap") is not None and _norm(control.get("roadmap")) != _norm(spec["roadmap"]):
        out.append(f"roadmap is {control.get('roadmap')!r} but setting {setting} needs {spec['roadmap']!r}")
    return out


def check_setting(setting: str, runs: list, repo: Path = REPO) -> list[str]:
    """What is wrong with these runs (hri_eval_dev_v4.Run objects) as the final of this setting. Empty = fine."""
    pl = plan(repo)
    if setting not in pl["settings"]:
        return [f"unknown setting {setting!r}"]
    spec, out = pl["settings"][setting], []
    for key in ("task", "final_seed", "runs_per_setting"):
        if pl.get(key) is None:
            out.append(f"final_plan.json: {key} is blank")
    if out:
        return out
    if not runs:
        return ["no runs"]
    if spec.get("zoom") is not None and any(r.zoom_on != spec["zoom"] for r in runs):
        out.append(f"setting {setting} needs zoom {'on' if spec['zoom'] else 'off'}")
    if spec.get("bystanders") is not None and any(r.bystanders != spec["bystanders"] for r in runs):
        out.append(f"setting {setting} needs {'bystanders' if spec['bystanders'] else 'no bystanders'} in every run")
    if len(runs) != pl["runs_per_setting"]:
        out.append(f"{len(runs)} runs, the plan has {pl['runs_per_setting']} per setting")
    for unity in sorted({r.unity_dir for r in runs}, key=str):
        s = json.loads((unity / "session.json").read_text(encoding="utf-8"))
        if s.get("seed") != pl["final_seed"]:
            out.append(f"{unity.name}: seed {s.get('seed')} but the plan's final seed is {pl['final_seed']}")
        if s.get("task") != pl["task"]:
            out.append(f"{unity.name}: task {s.get('task')} but the plan's task is {pl['task']}")
        if s.get("mode") != "final":
            out.append(f"{unity.name}: Unity session mode is {s.get('mode')!r}, not 'final'")
        out += _experiment_session_problems(setting, spec, pl, unity.name, s, repo)
    out += _experiment_run_problems(setting, spec, pl, runs, repo)
    return out


def _experiment_session_problems(setting: str, spec: dict, pl: dict, name: str, s: dict, repo: Path) -> list[str]:
    """Experiment and set (and lie probability when recorded) in Unity's session.json are the setting's."""
    out = []
    if spec.get("experiment") is not None and s.get("experiment") != spec["experiment"]:
        out.append(f"{name}: experiment {s.get('experiment')!r} but setting {setting} is experiment {spec['experiment']}")
    if spec.get("set") is not None and s.get("set") != spec["set"]:
        out.append(f"{name}: set {s.get('set')!r} but setting {setting} is set {spec['set']}")
    if spec.get("set") is not None and s.get("lie_probability") is not None:
        want = json.loads((repo / SCENARIOS).read_text(encoding="utf-8"))["sets"][spec["set"]]["lie_probability"]
        if abs(float(s["lie_probability"]) - float(want)) > 1e-6:        # Unity writes a float32 (0.2f)
            out.append(f"{name}: lie probability {s['lie_probability']} but set {spec['set']} has {want}")
    if s.get("final_setting") not in (None, "") and s["final_setting"] != setting:     # Unity's session.json records the setting it ran (16.16 decision 7)
        out.append(f"{name}: Unity ran final setting {s['final_setting']!r}, not {setting!r}")
    return out


def _experiment_run_problems(setting: str, spec: dict, pl: dict, runs: list, repo: Path) -> list[str]:
    """The looks and clips of every run lie within the setting's test_assignment, and the bridge ran the setting's control config."""
    out = []
    ta = pl.get("test_assignment")
    assigned = ta.get(setting) if isinstance(ta, dict) else None
    if assigned is not None:
        for r in runs:
            extra_l, extra_c = sorted(set(r.looks) - set(assigned["looks"])), sorted(set(r.clips) - set(assigned["clips"]))
            if extra_l or extra_c:
                out.append(f"{r.name}: looks {extra_l} / clips {extra_c} are not in the setting's test assignment")
    seen = set()
    for r in runs:
        b = getattr(r, "bridge_dir", None)
        if b is None or str(b) in seen:
            continue
        seen.add(str(b))
        f = Path(b) / "config_used" / "control.json"
        if f.is_file():
            out += [f"{Path(b).name}: {p}" for p in control_problems(setting, json.loads(f.read_text(encoding="utf-8")), repo)]
    return out


# ---------------------------------------------------------------- the timeout from the step-5 runs (AUDIT.md 16.20.5.1)

STEP5_PREFIX = "t0_"                  # the step-5 sessions are named <prefix><final setting> (finals_v4/step5_report.py --prefix); smoke_t0_*, dry_* are not step 5
STEP5_RUNS_PER_SETTING = 3            # step 5 = 13 settings x 3 development runs
MIN_DEVELOPMENT_TIMEOUT_S = 420.0     # 16.20.5 decision 2: development runs that feed the rule never use less (900 s is used, 16.20.5.1)
_TRUTH_RUN = re.compile(r"truth_run(\d+)\.json$")


def _run_record(d: dict, setting: str, where: str) -> dict:
    """The fields development_timeout and the listing need from one truth_run###.json (Unity's TruthRun)."""
    return {"setting": setting, "trial": d.get("trial"), "mode": d.get("mode"), "outcome": d.get("outcome"), "failure_reason": d.get("failure_reason"),
            "total_s": d.get("total_s"), "where": where}


def _runs_of_folder(folder: Path, setting: str) -> list[dict]:
    if not folder.is_dir():
        raise SystemExit(f"{setting}: {folder} is not a folder")
    return [_run_record(json.loads(f.read_text(encoding="utf-8-sig")), setting, f"{folder.name}/{f.name}")
            for f in sorted(folder.iterdir()) if _TRUTH_RUN.fullmatch(f.name)]


def _runs_of_zip(z: zipfile.ZipFile, setting: str, unity: str) -> list[dict]:
    base = f"{setting}/{unity}/"
    return [_run_record(json.loads(z.read(n).decode("utf-8-sig")), setting, f"{unity}/{n[len(base):]}") for n in sorted(z.namelist())      # the place is <session folder>/<file>, as for a folder
            if n.startswith(base) and _TRUTH_RUN.fullmatch(n[len(base):])]


def load_step5_sources(sources: list[str], base: Path = HERE) -> tuple[list[dict], list[str]]:
    """(sessions, files read): every session named by the sources, whatever its name; a session is {'name', 'where', 'timeout_s', 'runs'}. A zip is read in place
    (its MANIFEST.json names the sessions), a manifest .json names Unity session folders (relative to robot_vision/ unless absolute), NAME=FOLDER names one."""
    sessions, read = [], []
    for src in sources:
        if "=" in src and not Path(src).exists():
            name, _, folder = src.partition("=")
            f = Path(folder) if Path(folder).is_absolute() else base / folder
            sessions.append({"name": name, "where": str(folder), "timeout_s": None, "runs": _runs_of_folder(f, name)})
            read.append(f"{name}={f.name}")
            continue
        path = Path(src) if Path(src).is_absolute() else Path.cwd() / src
        if not path.is_file():
            raise SystemExit(f"{src}: not a file (a step-5 zip, a step-5 manifest .json or NAME=<Unity session folder>)")
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        read.append(f"{path.name} sha256 {digest}")
        if path.suffix.lower() == ".zip":
            with zipfile.ZipFile(path) as z:
                if "MANIFEST.json" not in z.namelist():
                    raise SystemExit(f"{path.name}: no MANIFEST.json (not a zip of finals_v4/step5_zip_v4.py)")
                for m in json.loads(z.read("MANIFEST.json").decode("utf-8-sig")).get("sessions", []):
                    sessions.append({"name": m["setting"], "where": f"{path.name}:{m['setting']}/{m['unity']}", "timeout_s": m.get("timeout_s"),
                                     "runs": _runs_of_zip(z, m["setting"], m["unity"])})
        elif path.suffix.lower() == ".json":
            for m in json.loads(path.read_text(encoding="utf-8-sig")).get("sessions", []):
                u = Path(m["unity"])
                sessions.append({"name": m["setting"], "where": f"{path.name}:{m['setting']}", "timeout_s": m.get("timeout_s"),
                                 "runs": _runs_of_folder(u if u.is_absolute() else base / u, m["setting"])})
        else:
            raise SystemExit(f"{src}: not a .zip, a .json manifest or NAME=FOLDER")
    return sessions, read


def pool_step5(sessions: list[dict], settings: list[str], prefix: str = STEP5_PREFIX, runs_per_setting: int = STEP5_RUNS_PER_SETTING) -> dict:
    """The pooled runs of the 13 final settings. {'runs': [...], 'ignored': [session names that are not step 5], 'problems': [...]}. Any problem = no timeout is derived."""
    by: dict[str, list[dict]] = {st: [] for st in settings}
    ignored = []
    for se in sessions:
        name = se["name"]
        if name.startswith(prefix) and name[len(prefix):] in by:
            by[name[len(prefix):]].append(se)
        else:
            ignored.append(name)
    problems, runs = [], []
    for st in settings:
        ses = by[st]
        if not ses:
            problems.append(f"{prefix}{st}: no session (step 5 has all {len(settings)} settings)")
            continue
        if len(ses) > 1:
            problems.append(f"{prefix}{st}: {len(ses)} sessions ({'; '.join(x['where'] for x in ses)}): give one (an interrupted session is kept, not used)")
            continue
        se = ses[0]
        if se["timeout_s"] is not None and float(se["timeout_s"]) < MIN_DEVELOPMENT_TIMEOUT_S:
            problems.append(f"{prefix}{st}: development timeout {se['timeout_s']} s is below {MIN_DEVELOPMENT_TIMEOUT_S:g} s: its runs cannot feed the rule (16.20.5)")
        se = {**se, "runs": [{**r, "setting": st} for r in se["runs"]]}            # from here on a run carries its FINAL setting name (A3), not the session's (t0_A3)
        if len(se["runs"]) != runs_per_setting:
            problems.append(f"{prefix}{st}: {len(se['runs'])} runs, step 5 has {runs_per_setting} per setting")
        trials = [r["trial"] for r in se["runs"]]
        if len(set(trials)) != len(trials):
            problems.append(f"{prefix}{st}: a trial number appears twice {sorted(trials)}")
        for r in se["runs"]:
            if r["mode"] != "development":
                problems.append(f"{prefix}{st} trial {r['trial']}: mode {r['mode']!r}: only development runs feed the rule")
            if r["outcome"] is None or r["total_s"] is None:
                problems.append(f"{prefix}{st} trial {r['trial']}: outcome or total_s missing in {r['where']}")
        runs += se["runs"]
    return {"runs": runs, "ignored": ignored, "problems": problems}


def step5_timeout_report(runs: list[dict], ignored: list[str]) -> tuple[list[str], dict]:
    """(the lines to print, the development_timeout result) for the pooled runs: ONE value from all of them (16.20.5.1)."""
    res = development_timeout(runs)
    best = max((r for r in runs if r["outcome"] == "SUCCESS"), key=lambda r: float(r["total_s"]))
    lines = [f"Pooled: {res['runs']} runs of {len({r['setting'] for r in runs})} settings; {res['successful_runs']} successful, {len(runs) - res['successful_runs']} excluded "
             f"({res['timeouts']} timed out, {res['other_failures']} other failures)", "",
             "| setting | trial | outcome | failure | total_s | in the rule |", "|---|---|---|---|---|---|"]
    for r in runs:
        ok = r["outcome"] == "SUCCESS"
        lines.append(f"| {r['setting']} | {r['trial']} | {r['outcome']} | {r['failure_reason']} | {float(r['total_s']):.1f} | "
                     f"{'yes' if ok else 'NO: gives no duration' + (' (timed out: its cause must be found before the freeze, 16.16 decision 4)' if r['failure_reason'] == 'timeout' else '')} |")
    excluded = [r for r in runs if r["outcome"] != "SUCCESS"]
    lines += ["", f"Excluded from the rule ({len(excluded)}):"] + [f"  {r['setting']} trial {r['trial']}: {r['outcome']} / {r['failure_reason']}, {float(r['total_s']):.1f} s  [{r['where']}]" for r in excluded]
    if not excluded:
        lines.append("  none")
    lines += ["", f"Longest SUCCESSFUL run: {res['longest_successful_s']:.1f} s ({best['setting']} trial {best['trial']})",
              f"timeout_s = 1.5 x {res['longest_successful_s']:.1f} = {1.5 * res['longest_successful_s']:.1f}, rounded up to a multiple of 30 s, never below 270 s = {res['timeout_s']:g} s",
              "One value for all settings, from the pooled runs. final_plan.json timeout_s is NOT edited (it stays until a declared edit before the freeze)."]
    if ignored:
        lines.append(f"Not step 5 (ignored): {', '.join(sorted(set(ignored)))}")
    if res["cause_needed_before_the_freeze"]:
        lines.append(f"CAUSE NEEDED BEFORE THE FREEZE: {res['timeouts']} development run(s) timed out (listed above).")
    return lines, res


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Final guards: the development timeout from the pooled step-5 runs of all 13 settings (AUDIT.md 16.20.5.1), "
                                             "the state of every final (--status) and the declaration of an infrastructure interruption (AUDIT.md 16.30.1).")
    ap.add_argument("--status", action="store_true", help="print the state of every final setting (fresh, started, interrupted, resumed, invalid, evaluated, exported)")
    ap.add_argument("--declare-interruption", metavar="SETTING", default=None,
                    help="declare that the final of SETTING was interrupted by an infrastructure failure before run --run finished (needs --run, --reason, "
                         "--evidence, --unity-folder, --bridge-folder); after a resume, the same command declares the second interruption: the setting becomes invalid")
    ap.add_argument("--resume-info", metavar="SETTING", default=None,
                    help="print, as JSON, what the launcher needs to resume the declared interruption of SETTING (run to resume from = Unity's -StartRun k, "
                         "the --resume-marker folder, seed and goal order of the declaration), or refuse with the reason (AUDIT.md 16.31.2)")
    ap.add_argument("--supersede-evaluation", metavar="SETTING", default=None,
                    help="declare the evaluation in --folder superseded (wrong map or crashed; AUDIT.md 16.35.1) so that SETTING can be evaluated once more; needs --reason")
    ap.add_argument("--folder", default=None, help="--supersede-evaluation: the evaluation folder (a name under the output root)")
    ap.add_argument("--run", type=int, default=None, help="the run that was interrupted (it has no outcome; runs before it have)")
    ap.add_argument("--reason", default=None, help="what failed, one line")
    ap.add_argument("--evidence", nargs="+", default=None, help="files or folders: the Event Viewer export, the crash log, the server and Unity logs")
    ap.add_argument("--unity-folder", default=None, help="the Unity session folder of the interrupted part")
    ap.add_argument("--bridge-folder", default=None, help="the bridge run folder of the interrupted part")
    ap.add_argument("--output-root", default=None, help="the outputs folder (default: configs' outputs)")
    ap.add_argument("--timeout-from", nargs="+", default=None, metavar="SOURCE",
                    help="the step-5 zip of finals_v4/step5_zip_v4.py (read in place), the step-5 manifest .json, or NAME=<Unity session folder> (e.g. t0_A3=outputs/trials_development_...)")
    ap.add_argument("--prefix", default=STEP5_PREFIX, help="the setting prefix of the step-5 sessions (default t0_)")
    ap.add_argument("--runs-per-setting", type=int, default=STEP5_RUNS_PER_SETTING)
    ap.add_argument("--out", default=None, help="also write the report to this new file (an existing file is refused)")
    a = ap.parse_args(argv)
    if sum(bool(x) for x in (a.status, a.declare_interruption, a.resume_info, a.supersede_evaluation, a.timeout_from)) != 1:
        ap.error("give exactly one of --status, --declare-interruption SETTING, --resume-info SETTING, --supersede-evaluation SETTING, --timeout-from SOURCE")
    if a.status or a.declare_interruption or a.resume_info or a.supersede_evaluation:
        import decision_io as dio
        root = dio.resolve(a.output_root or "outputs")
        if a.supersede_evaluation:
            if not (a.folder and a.reason):
                ap.error("--supersede-evaluation needs --folder and --reason")
            m = declare_evaluation_superseded(a.supersede_evaluation, a.folder, a.reason, root)
            print(f"{m.name} written: {m.parent}")
            return 0
        if a.status:
            print(status_text(status(root)))
            return 0
        if a.resume_info:
            print(json.dumps(resume_info(root, a.resume_info), indent=2))
            return 0
        missing = [n for n, v in (("--run", a.run), ("--reason", a.reason), ("--evidence", a.evidence), ("--unity-folder", a.unity_folder),
                                  ("--bridge-folder", a.bridge_folder)) if v in (None, [])]
        if missing:
            ap.error("--declare-interruption also needs " + ", ".join(missing))
        marker = declare_interruption(a.declare_interruption, a.run, a.reason, a.evidence, dio.resolve(a.unity_folder), dio.resolve(a.bridge_folder), root)
        print(f"{marker.name} written: {marker.parent}")
        print("invalid: the setting is never rerun and is reported as invalid." if marker.name == MARKERS["invalid"]
              else f"Resume once from run {a.run} with --resume-marker {marker.parent.name} (same seed, goal order, configs, frozen hashes).")
        return 0
    settings = list(plan()["settings"])
    sessions, read = load_step5_sources(a.timeout_from)
    pooled = pool_step5(sessions, settings, a.prefix, a.runs_per_setting)
    lines = ["Timeout from the step-5 development runs (AUDIT.md 16.20.5.1), read in place:"] + [f"  {x}" for x in read] + [""]
    if pooled["problems"]:
        lines += ["REFUSED: no timeout is derived."] + [f"  - {p}" for p in pooled["problems"]]
        code = 2
    else:
        try:
            body, _ = step5_timeout_report(pooled["runs"], pooled["ignored"])
            lines += body
            code = 0
        except ValueError as e:
            lines += [f"REFUSED: {e}"]
            code = 2
    text = "\n".join(lines)
    if a.out:
        with Path(a.out).open("x", encoding="utf-8") as f:
            f.write(text + "\n")
    print(text)
    return code


if __name__ == "__main__":
    sys.exit(main())
