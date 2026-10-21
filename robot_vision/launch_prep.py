"""Checks shared by the trial launchers (run_trials.ps1 / run_trials.sh) before the server starts (2026-10-22).

    python launch_prep.py --task Task1 [--trials 5]     check, print the machine state, write the trial-count override
    python launch_prep.py --cleanup                     remove the override written by --trials

- The task must be the one in configs/trials.local.json (if present; the Unity trial runner prefers it) or
  configs/trials.json, else the Unity runner would refuse the map.
- --trials N (development only): the development check runs N trials instead of trial_count. It writes a git-ignored
  configs/trials.local.json = trials.json with trial_count N and a generated_by marker; the launcher removes it after
  the session (--cleanup), and the Unity runner copies it into the session's config_used/. Refused unless the mode is
  "development" (so never for a final or a replication), and refused if a trials.local.json not written by this
  helper exists. A leftover one written by this helper (a launcher that was killed) is removed first.
- Prints the machine state (bridge/machine_state.py: power mode, power source) and its warnings (run protocol in
  AUDIT.md section 9); warnings do not refuse the run, the state is also recorded in the bridge run's run_info.json.
Exit 0 = go, 2 = refused (message on stderr).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
CONFIGS = HERE / "configs"
MARKER = "run_trials --trials"


def _read(p: Path) -> dict:
    return json.loads(p.read_text(encoding="utf-8"))


def ours(local: Path) -> bool:
    try:
        return local.exists() and _read(local).get("generated_by") == MARKER
    except (OSError, ValueError):
        return False


def cleanup(configs: Path = CONFIGS) -> bool:
    local = configs / "trials.local.json"
    if ours(local):
        local.unlink()
        return True
    return False


def prepare(task: str, trials: int | None, configs: Path = CONFIGS) -> tuple[str, str]:
    """Returns (config file the Unity runner will read, mode); raises SystemExit(message) when refused."""
    local, base = configs / "trials.local.json", configs / "trials.json"
    if cleanup(configs):
        print(f"[launch_prep] removed a leftover {local.name} from an earlier --trials launch")
    cfg_file = local if local.exists() else base
    cfg = _read(cfg_file)
    if cfg.get("task") != task:
        raise SystemExit(f"{cfg_file} says task '{cfg.get('task')}' but you asked for {task}. "
                         f"Set \"task\" there (and \"mode\") first.")
    mode = cfg.get("mode", "development")
    if trials is not None:
        if mode != "development":
            raise SystemExit(f"--trials is for development checks only; {cfg_file.name} has mode '{mode}' "
                             f"(finals and replications run trial_count = {cfg.get('trial_count')} trials)")
        if local.exists():
            raise SystemExit(f"{local} exists (not written by --trials); remove it or run without --trials")
        if trials < 1:
            raise SystemExit("--trials must be at least 1")
        new = {**cfg, "trial_count": int(trials), "generated_by": MARKER,
               "generated_note": f"Development check with {trials} trials instead of trial_count {cfg.get('trial_count')} "
                                 f"(configs/trials.json); written by the launcher and removed after the session."}
        local.write_text(json.dumps(new, indent=2) + "\n", encoding="utf-8")
        cfg_file = local
        print(f"[launch_prep] development check: {trials} trials (configs/{local.name}, removed after the session)")
    return cfg_file.name, mode


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--task", choices=["Task1", "Task2"])
    ap.add_argument("--trials", type=int, default=None)
    ap.add_argument("--cleanup", action="store_true")
    a = ap.parse_args(argv)
    if a.cleanup:
        print(f"[launch_prep] {'removed' if cleanup() else 'no'} launcher-written trials.local.json")
        return 0
    if not a.task:
        ap.error("--task is required")
    try:
        name, mode = prepare(a.task, a.trials)
    except SystemExit as e:
        print(f"[launch_prep] refused: {e}", file=sys.stderr)
        return 2
    sys.path.insert(0, str(HERE))
    from bridge import machine_state
    state = machine_state.read()
    print(f"[launch_prep] task {a.task}, mode {mode} ({name}); power mode: {state.get('power_mode')}; "
          f"power source: {state.get('power_source')}")
    for w in state["warnings"]:
        print(f"[launch_prep] WARNING (run protocol): {w}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
