"""Run-once guards for the v4 final settings (zoom_on, zoom_off, bystanders, unseen_look; configs/v4/final_plan.json), the Python
side of v3's FINAL_DONE.json. A final cannot be repeated silently.

Two markers, both written with mode 'x' (never overwritten), found by scanning every folder under the output root:
- FINAL_RUN_DONE.json in a bridge run folder: the server ran the setting in final mode (bridge.server --final-setting NAME)
  and finished at least one trial. A setting with this marker cannot be started again.
- FINAL_DONE.json in a final-evaluation folder (hri_eval_final_v4_<setting>_<time>/): the setting was evaluated. It cannot be
  evaluated again. (hri_analysis_v4.py only describes the data and may be re-run into a new folder.)
A started run or evaluation that did not finish writes no marker and does not block (as in v3).

check_setting: a final session must be what its setting says (zoom flag, bystanders, number of runs, seed, task, Unity mode
final), from configs/v4/final_plan.json. Reporting/evaluation code; inference code never imports it.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
PLAN = "robot_vision/configs/v4/final_plan.json"
MARKERS = {"run": "FINAL_RUN_DONE.json", "evaluation": "FINAL_DONE.json"}
EVAL_PREFIX = "hri_eval_final_v4"


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
    """SystemExit if this setting was already run (kind 'run') or evaluated (kind 'evaluation') as a final."""
    check_name(setting, repo)
    done = markers(output_root, setting, kind)
    if done:
        what = "run" if kind == "run" else "evaluated"
        raise SystemExit(f"final setting {setting!r} was already {what} as a final: {done[0].parent.name}/{done[0].name}. "
                         "Finals are run once; the earlier result stands (disclose any repetition in AUDIT.md section 14 first).")


def write_done(folder: str | Path, setting: str, kind: str, info: dict | None = None) -> Path:
    """Write the marker (never overwrites)."""
    p = Path(folder) / MARKERS[kind]
    rec = {"setting": setting, "kind": kind, "written": datetime.now().isoformat(timespec="seconds"), **(info or {})}
    with p.open("x", encoding="utf-8") as f:
        f.write(json.dumps(rec, indent=2, default=str) + "\n")
    return p


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
    return out
