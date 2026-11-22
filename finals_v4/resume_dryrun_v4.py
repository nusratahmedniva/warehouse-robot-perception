"""Resume of a final, dry run (Avatar/Config/experiments_ab.md section 15 addendum 13; Anisha's AUDIT.md 16.30.1, 16.31.3, 16.31.4).

A demonstration of the whole flow WITHOUT Unity Play, without a server and without any real final: every folder is synthetic and lives in
a new folder robot_vision/outputs/resume_dryrun_<time>/outputs/ (two levels below the real output root, so no real guard ever sees its
markers). Anisha's Python is used as it is (final_guard_v4.py command line and resume_plan); the launcher and the B11 check run with
-DryRun / on the synthetic folders; Unity's own checks (FinalResumeV4, EarlierFinal, SessionResumeV4, DoneJson) are the Edit Mode tests
Avatar/Tests/FinalResumeTests.cs, and part 2's session.json below is written with the keys Unity writes.

Steps (setting B3, 20 runs, seed 2, the plan's goal order; interrupted at run 4):
  1. part 1: Unity folder with runs 1-3 finished (truth_run###.json) and run_004 interrupted; bridge folder with FINAL_SETTING.json and
     python_trial_001..003.json
  2. launcher dry run WITHOUT -Resume: refused as "already started"
  3. final_guard_v4.py --declare-interruption B3 --run 4 ...  -> FINAL_INTERRUPTION.json
  4. final_guard_v4.py --resume-info B3                        -> the run, the declaration, seed and goal order
  5. launcher dry run WITH -Resume: Unity -startRun 4 -resumeMarker <declaration> -bridgeFolder, server --resume-marker, check -StartRun 4
     -ResumeMarker, the evaluation with both parts
  6. the server's start of part 2 (final_guard_v4.check_start + write_resume, as bridge.server does) and its FINAL_SETTING.json
  7. part 2 as Unity writes it: session.json (start_run 4, resume_from_run 4, resume_of part 1, seed, full goal order), truth_run004..020,
     UNITY_FINAL_DONE.json (start_run 4, runs_driven 17); the server's FINAL_RUN_DONE.json
  8. check_session_v4.ps1 -Final -StartRun 4: refused without -ResumeMarker, refused with a wrong session.json, accepted with it (the
     criteria then run; on synthetic files most fail, which is not what is shown here)
  9. final_guard_v4.resume_plan on part 1 + part 2: no problem (the evaluation would score them as one session)
 10. a second interruption (a fresh root: part 2 interrupted at run 10): --declare-interruption writes FINAL_INVALID.json; --resume-info and
     the launcher's -Resume refuse; --status shows the setting invalid
Writes report.json and report.md into the run folder. Usage (repository root):
  robot_vision\\.venv\\Scripts\\python.exe finals_v4\\resume_dryrun_v4.py
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
RV = REPO / "robot_vision"
PY = Path(sys.executable)
LAUNCHER = REPO / "finals_v4" / "run_session_v4.ps1"
CHECK = REPO / "finals_v4" / "check_session_v4.ps1"
SETTING = "B3"
SEED = 2
K = 4
P1_UNITY, P1_BRIDGE = "trials_final_Task2_B3_20261201_100000", "bridge_guide_20261201_100000"
P2_UNITY, P2_BRIDGE = "trials_final_Task2_B3_20261201_140000", "bridge_guide_20261201_140000"


def guard():
    sys.path.insert(0, str(RV))
    import final_guard_v4 as fg
    return fg


def goal_order() -> list[str]:
    """A full order of 20 goals (the final seed's order on the v4 map, as test_v4_frozen pins it). Python compares the orders Unity recorded
    in the parts and the declaration; it never recomputes them, so any fixed order shows the flow."""
    return ["E5", "E1", "E5", "E2", "E5", "E3", "E5", "E3", "E4", "E3", "E5", "E3", "E5", "E6", "E2", "E5", "E3", "E1", "E4", "E2"]


def write(path: Path, data) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(data if isinstance(data, str) else json.dumps(data, indent=2) + "\n", encoding="utf-8")
    return path


def session_json(goals, start_run=1, resume_from_run=0, resume_of="") -> dict:
    """The keys of Unity's session.json that the resume rule reads (TrialRunnerV4.SessionV4; the other keys are omitted here)."""
    return {"study": "v4", "task": "Task2", "mode": "final", "seed": SEED, "trials": 20, "goal_order": goals, "final_setting": SETTING,
            "start_run": start_run, "shader_warm_up": [], "resume_from_run": resume_from_run, "resume_of": resume_of}


def part(root: Path, unity: str, bridge: str, goals, runs_done, interrupted=None, session=None, sha="", run_dirs=True) -> None:
    u, b = root / unity, root / bridge
    write(u / "session.json", session or session_json(goals))
    for i in runs_done:
        write(u / f"truth_run{i:03d}.json", {"trial": i, "outcome": "SUCCESS", "note": "synthetic (resume dry run)"})
        write(b / f"python_trial_{i:03d}.json", {"trial_index": i, "note": "synthetic (resume dry run)"})
        if run_dirs:
            (u / f"run_{i:03d}").mkdir(parents=True, exist_ok=True)
    if interrupted:
        (u / f"run_{interrupted:03d}").mkdir(parents=True, exist_ok=True)      # the interrupted run's folder stays (16.30.1 item 6)
    write(b / "FINAL_SETTING.json", {"setting": SETTING, "frozen_sha256": sha, "note": "synthetic (resume dry run)"})


def run(cmd, cwd=REPO) -> dict:
    p = subprocess.run([str(c) for c in cmd], cwd=cwd, capture_output=True, text=True, encoding="utf-8", errors="replace",
                       env={**os.environ, "PYTHONIOENCODING": "utf-8"})
    return {"cmd": " ".join(str(c) for c in cmd), "exit": p.returncode, "out": (p.stdout + p.stderr).strip()}


def ps(script: Path, *args) -> dict:
    return run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", script, *args])


def declare(root: Path, run_k: int, unity: str, bridge: str) -> dict:
    ev = write(root / "evidence" / f"crash_run{run_k:03d}.log", "synthetic crash log (resume dry run): python312.dll 0xc0000005\n")
    return run([PY, "final_guard_v4.py", "--declare-interruption", SETTING, "--run", run_k, "--reason", "synthetic: server crash (dry run)",
                "--evidence", ev, "--unity-folder", root / unity, "--bridge-folder", root / bridge, "--output-root", root], cwd=RV)


def demo(base: Path) -> dict:
    fg = guard()
    sha = fg.frozen_sha256()
    goals = goal_order()
    root = base / "outputs"
    root.mkdir(parents=True)
    steps = {}
    # 1. part 1, interrupted at run K
    part(root, P1_UNITY, P1_BRIDGE, goals, range(1, K), interrupted=K, sha=sha)
    steps["1_part1"] = {"unity": P1_UNITY, "bridge": P1_BRIDGE, "runs_done": list(range(1, K)), "interrupted": K}
    # 2. the launcher without -Resume
    steps["2_launcher_without_resume"] = ps(LAUNCHER, "-Experiment", SETTING, "-DryRun", "-OutputRoot", root)
    # 3. the declaration
    steps["3_declare"] = declare(root, K, P1_UNITY, P1_BRIDGE)
    decl = fg.markers(root, SETTING, "interruption")
    steps["3_declare"]["marker"] = decl[0].parent.name if decl else None
    # 4. what the launcher reads
    steps["4_resume_info"] = run([PY, "final_guard_v4.py", "--resume-info", SETTING, "--output-root", root], cwd=RV)
    # 5. the launcher with -Resume
    steps["5_launcher_resume"] = ps(LAUNCHER, "-Experiment", SETTING, "-DryRun", "-Resume", "-OutputRoot", root)
    # 6. the server's start of part 2 (bridge.server.run: check_start, FINAL_SETTING.json, write_resume)
    d = fg.check_start(root, SETTING, decl[0].parent, sha)
    b2 = root / P2_BRIDGE
    write(b2 / "FINAL_SETTING.json", {"setting": SETTING, "frozen_sha256": sha, "resume_from_run": K, "note": "synthetic (resume dry run)"})
    fg.write_resume(b2, SETTING, d, decl[0].parent.name, sha)
    steps["6_server_start"] = {"check_start": "accepted", "resume_marker": str((b2 / "FINAL_RESUME.json").relative_to(base))}
    # 7. part 2 as Unity writes it
    s2 = session_json(goals, start_run=K, resume_from_run=K, resume_of=P1_UNITY)
    part(root, P2_UNITY, P2_BRIDGE, goals, range(K, 21), session=s2, sha=sha, run_dirs=False)   # no run folders: the check's per-run tools are not the point
    write(root / P2_UNITY / "UNITY_FINAL_DONE.json", {"final_setting": SETTING, "runs": 20, "start_run": K, "runs_driven": 21 - K,
                                                      "resume_from_run": K, "resume_of": P1_UNITY, "successes": 21 - K})
    write(b2 / "FINAL_RUN_DONE.json", {"setting": SETTING, "kind": "run"})
    steps["7_part2_session_json"] = {k: s2[k] for k in ("start_run", "resume_from_run", "resume_of", "seed", "final_setting")}
    # 8. the B11 check of part 2
    marker_dir = root / decl[0].parent.name
    common = ["-U", root / P2_UNITY, "-B", b2, "-Final"]
    steps["8a_check_without_marker"] = ps(CHECK, *common, "-StartRun", K)
    wrong = root / "trials_final_Task2_B3_20261201_150000"
    write(wrong / "session.json", session_json(goals, start_run=K, resume_from_run=0, resume_of=""))
    steps["8b_check_wrong_session"] = ps(CHECK, "-U", wrong, "-B", b2, "-Final", "-StartRun", K, "-ResumeMarker", marker_dir)
    steps["8c_check_with_marker"] = ps(CHECK, *common, "-StartRun", K, "-ResumeMarker", marker_dir)
    # 9. the evaluation's view
    plan_ = fg.resume_plan(root, SETTING, [(root / P1_UNITY, root / P1_BRIDGE), (root / P2_UNITY, b2)])
    steps["9_resume_plan"] = {"resumed": plan_["resumed"], "problems": plan_["problems"], "interrupted": plan_["interrupted"]}
    # 10. a second interruption, in a fresh root: part 2 interrupted at run 10
    root2 = base / "outputs_second"
    root2.mkdir()
    part(root2, P1_UNITY, P1_BRIDGE, goals, range(1, K), interrupted=K, sha=sha)
    first = declare(root2, K, P1_UNITY, P1_BRIDGE)
    decl2 = fg.markers(root2, SETTING, "interruption")[0].parent
    d2 = fg.check_start(root2, SETTING, decl2, sha)
    part(root2, P2_UNITY, P2_BRIDGE, goals, range(K, 10), interrupted=10,
         session=session_json(goals, start_run=K, resume_from_run=K, resume_of=P1_UNITY), sha=sha)
    fg.write_resume(root2 / P2_BRIDGE, SETTING, d2, decl2.name, sha)
    second = declare(root2, 10, P2_UNITY, P2_BRIDGE)
    steps["10_second_interruption"] = {
        "first_declaration_exit": first["exit"], "second_declaration": second,
        "invalid_marker": [m.parent.name for m in fg.markers(root2, SETTING, "invalid")],
        "resume_info": run([PY, "final_guard_v4.py", "--resume-info", SETTING, "--output-root", root2], cwd=RV),
        "launcher_resume": ps(LAUNCHER, "-Experiment", SETTING, "-DryRun", "-Resume", "-OutputRoot", root2),
        "status": run([PY, "final_guard_v4.py", "--status", "--output-root", root2], cwd=RV),
    }
    return steps


def verdicts(steps: dict) -> dict:
    """What each step must show (also asserted by test_resume_dryrun_v4.py)."""
    s = steps
    out5 = s["5_launcher_resume"]["out"]
    return {
        "2 launcher without -Resume: 'already started' blocker": "already started as a final" in s["2_launcher_without_resume"]["out"],
        "3 declaration written": s["3_declare"]["exit"] == 0 and bool(s["3_declare"]["marker"]),
        "4 resume-info gives run 4": s["4_resume_info"]["exit"] == 0 and json.loads(s["4_resume_info"]["out"])["resume_from_run"] == K,
        "5 launcher -Resume: Unity -startRun 4 -resumeMarker": s["5_launcher_resume"]["exit"] == 0 and "-startRun 4 -resumeMarker" in out5,
        "5 launcher -Resume: server --resume-marker": "--resume-marker" in out5,
        "5 launcher -Resume: Unity -bridgeFolder": "-bridgeFolder" in out5,
        "5 launcher -Resume: check -StartRun 4 -ResumeMarker": "-StartRun 4 -ResumeMarker" in out5,
        "5 launcher -Resume: no 'already started' blocker for part 1": "already started as a final" not in out5,
        "5 launcher -Resume: evaluation with both parts": out5.count("--session") >= 2 and P1_UNITY in out5,
        "8a check -Final -StartRun without -ResumeMarker refused": s["8a_check_without_marker"]["exit"] == 2 and "REFUSED" in s["8a_check_without_marker"]["out"],
        "8b check with a session.json that does not match refused": s["8b_check_wrong_session"]["exit"] == 2 and "does not match" in s["8b_check_wrong_session"]["out"],
        "8c check with -ResumeMarker accepted (criteria run)": "declared resume of " + P1_UNITY in s["8c_check_with_marker"]["out"]
                                                               and "REFUSED" not in s["8c_check_with_marker"]["out"],
        "9 resume_plan: resumed, no problem": s["9_resume_plan"]["resumed"] and not s["9_resume_plan"]["problems"],
        "10 second interruption: FINAL_INVALID.json": s["10_second_interruption"]["second_declaration"]["exit"] == 0
                                                      and bool(s["10_second_interruption"]["invalid_marker"]),
        "10 resume-info refuses": s["10_second_interruption"]["resume_info"]["exit"] != 0,
        "10 launcher -Resume refuses": s["10_second_interruption"]["launcher_resume"]["exit"] == 2,
    }


def relative(obj, base: Path):
    """The report keeps no absolute path (robot_vision/tests/test_run_paths.py scans outputs/): the run folder and the repository are named, any
    other drive path loses its drive letter."""
    import re
    if isinstance(obj, dict):
        return {k: relative(v, base) for k, v in obj.items()}
    if isinstance(obj, list):
        return [relative(v, base) for v in obj]
    if not isinstance(obj, str):
        return obj
    for root, name in ((base, "<run folder>"), (REPO, "<repo>")):
        for form in (str(root), str(root).replace("\\", "/")):
            obj = obj.replace(form, name)
    return re.sub(r"(?<![A-Za-z0-9])([A-Za-z]):([\\/])", r"<\1>\2", obj)


def main() -> int:
    base = RV / "outputs" / f"resume_dryrun_{datetime.now():%Y%m%d_%H%M%S}"
    base.mkdir()
    steps = demo(base)
    v = verdicts(steps)
    (base / "report.json").write_text(json.dumps({"what": "resume of a final, dry run (synthetic folders; no Unity Play, no server, no real final)",
                                                  "verdicts": v, "steps": relative(steps, base)}, indent=1, default=str) + "\n", encoding="utf-8")
    lines = ["# Resume of a final, dry run", "", f"Folder: {base.relative_to(REPO)} (synthetic; two levels below the output root).", "",
             "| step | shown |", "|---|---|"] + [f"| {k} | {'yes' if ok else 'NO'} |" for k, ok in v.items()]
    (base / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))
    return 0 if all(v.values()) else 1


if __name__ == "__main__":
    sys.exit(main())
