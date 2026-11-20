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

check_setting: a final session must be what its setting says (zoom flag, bystanders, number of runs, seed, task, Unity mode
final; for an experiment setting also its looks and clips, the control file the bridge ran with and the experiment and set Unity
recorded), from configs/v4/final_plan.json. timeout_from_development, development_timeout: the declared timeout rule (AUDIT.md 16.15 decision 2, corrected in 16.16 decision 4).
Reporting/evaluation code; inference code never imports it.
"""

from __future__ import annotations

import json
import math
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
PLAN = "robot_vision/configs/v4/final_plan.json"
MARKERS = {"run": "FINAL_RUN_DONE.json", "evaluation": "FINAL_DONE.json", "export": "FINAL_EXPORT_DONE.json"}
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
    return found


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
