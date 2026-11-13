"""v4 FINAL evaluation of one setting (zoom_on, zoom_off, bystanders, zoom_on_repeat). EVALUATION CODE ONLY.

Allowed only when ALL of this holds, otherwise refused (SystemExit) before any test data is read:
  1. configs/v4/frozen.json is frozen and every hash matches (v4 configs, v3 files v4 reads, pose weights, MediaPipe model);
  2. the setting has not been evaluated before (FINAL_DONE.json, final_guard_v4.py);
  3. the leak test of every Unity session passed: Unity's own result in session.json AND Python's independent check of leak_test/
     (gt_path.session_leak_check; it writes leak_test.json when absent, never overwrites). Missing images, a missing Unity result or any
     disagreement refuses, with the reason;
  4. every run lies wholly in the TEST split (data_splits_v4.guard_run with final evaluation: test looks and clips only, no
     development data, no mix, no placeholders) and is what the setting says (zoom, bystanders, runs, seed, task, Unity mode).
It runs the same evaluation as hri_eval_dev_v4.py (the numbers are computed by the same code), writes a new folder
<output_root>/hri_eval_final_v4_<setting>_<time>/ with eval.json, eval.md, the frozen record and every v4 config used, and
run.json (git commit), and only then FINAL_DONE.json (also a crash leaves no marker). No threshold is changed here.
It also counts Unity's watchdog stops PER RUN from each bridge run's messages.jsonl (watchdog_block; eval.json watchdog_stops,
a table in eval.md): per B11(a) (2026-11-13) a watchdog stop is a result, never a reason to refuse or invalidate.

Usage (from robot_vision/):
  python hri_eval_final_v4.py --setting zoom_on --session outputs/trials_final_X outputs/bridge_guide_Y [--session ... ...]
"""

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

import data_splits_v4 as ds
import final_guard_v4 as fg
import freeze_v4 as fz
import gesture_data as gd
import gt_path
import hri_eval_dev_v4 as ev

HERE = Path(__file__).resolve().parent


def gate(setting: str, pairs, output_root, gcfg: dict, repo: Path = fz.REPO) -> list:
    """All the checks, in order, before and while the test data is loaded. Returns the loaded runs."""
    fz.require_frozen(repo)                                           # 1. frozen and every hash matches (models must be present)
    fg.ensure_not_done(output_root, setting, "evaluation", repo)       # 2. not evaluated before
    gt_cfg = gt_path.load_config(repo / "robot_vision/configs/v4/gt_eval.json")
    for unity in sorted({Path(u) for u, _ in pairs}, key=str):         # 3. the leak test passed (before any test data is read)
        leak = gt_path.session_leak_check(unity, gt_cfg)
        if not leak["passed"]:
            raise SystemExit(f"{unity.name}: the leak test has not passed, so no result is reported: " + "; ".join(leak["reasons"]))
    splits = ds.load(repo / "robot_vision/configs/v4/data_splits.json")
    runs = ev.load_sessions(pairs, gcfg, splits, final_evaluation=True, settings=[setting] * len(pairs))   # 4. test split only
    problems = fg.check_setting(setting, runs, repo)
    if problems:
        raise SystemExit(f"setting {setting!r} refused: " + "; ".join(problems))
    return runs


def bridge_watchdog_counts(bridge: Path) -> dict | None:
    """Unity's watchdog stops per trial from a bridge run's messages.jsonl (every telemetry header carries Unity's cumulative
    watchdog_count, trial_index and trial_running). Each increase of the count is given to the trial running in the message
    that reports it, else to 'outside' (start-up, between runs). None when the bridge folder has no messages.jsonl."""
    path = Path(bridge) / "messages.jsonl"
    if not path.is_file():
        return None
    per_trial, seen, outside, prev, last = {}, set(), 0, 0, 0
    with path.open(encoding="utf-8") as f:
        for line in f:
            if '"telemetry"' not in line:
                continue
            msg = json.loads(line)
            if msg.get("dir") != "in" or msg.get("type") != "telemetry":
                continue
            h = msg.get("header", {})
            count = int(h.get("watchdog_count", prev))
            inc = count - prev if count >= prev else count            # a lower count: Unity's counter restarted from 0
            trial = int(h.get("trial_index", -1))
            running = bool(h.get("trial_running", False)) and trial >= 1
            if running:
                seen.add(trial)
                per_trial[trial] = per_trial.get(trial, 0) + inc
            else:
                outside += inc
            prev = last = count
    return {"per_trial": per_trial, "trials_seen": seen, "outside": outside, "last_count": last}


def _run_outcome(run) -> str | None:
    p = Path(run.unity_dir) / f"truth_run{run.trial:03d}.json" if run.unity_dir is not None else None
    try:
        return json.loads(p.read_text(encoding="utf-8")).get("outcome") if p is not None else None
    except (OSError, ValueError):
        return None


def watchdog_block(runs: list) -> dict:
    """B11(a), 2026-11-13: a watchdog stop is a RESULT, counted per run (a stop of that run, or its failure when the run failed),
    never a reason for invalidity: this block only reports, it refuses nothing. Per run: the stops reported by Unity while the run
    was running, or not_evaluated when the bridge log has no telemetry of that run."""
    counts = {}
    for b in sorted({Path(r.bridge_dir) for r in runs if r.bridge_dir is not None}, key=str):
        counts[b] = bridge_watchdog_counts(b)
    per_run = []
    for r in runs:
        c = counts.get(Path(r.bridge_dir)) if r.bridge_dir is not None else None
        stops = c["per_trial"].get(r.trial, 0) if c is not None and r.trial in c["trials_seen"] else ev.NOT_EVALUATED
        per_run.append({"run": r.name, "trial": r.trial, "outcome": _run_outcome(r), "watchdog_stops": stops})
    counted = [p["watchdog_stops"] for p in per_run if p["watchdog_stops"] != ev.NOT_EVALUATED]
    return {"per_run": per_run,
            "summary": {"runs": len(per_run), "runs_counted": len(counted), "coverage": ev._ratio(len(counted), len(per_run)),
                        "stops_in_runs": sum(counted), "runs_with_a_stop": sum(1 for s in counted if s > 0),
                        "stops_outside_runs": sum(c["outside"] for c in counts.values() if c is not None),
                        "reported_by_unity_total": sum(c["last_count"] for c in counts.values() if c is not None)},
            "source": "bridge messages.jsonl: Unity's cumulative watchdog_count in each telemetry header, an increase given to the "
                      "run with trial_running true in that message (else outside the runs)",
            "note": "B11(a): a watchdog stop is a result (a stop of its run, or its failure when the run failed), never a reason "
                    "for invalidity. Reported, not checked."}


def watchdog_markdown(w: dict) -> str:
    s = w["summary"]
    L = ["## Watchdog stops (a result, B11(a); never an invalidity reason)", "",
         f"{s['stops_in_runs']} stops in {s['runs_counted']} of {s['runs']} runs counted (coverage {s['coverage']}); runs with a stop "
         f"{s['runs_with_a_stop']}; outside the runs {s['stops_outside_runs']}; Unity's total {s['reported_by_unity_total']}.", "",
         "| run | outcome | watchdog stops |", "|---|---|---|"]
    L += [f"| {p['run']} | {p['outcome']} | {p['watchdog_stops']} |" for p in w["per_run"]]
    return "\n".join(L + ["", w["note"], ""]) + "\n"


def evaluate_final(setting: str, pairs, repo: Path = fz.REPO, output_root: Path | None = None) -> tuple[Path, dict]:
    """The whole final evaluation of one setting; returns (new output folder, result). Raises SystemExit when refused."""
    import decision_io as dio

    output_root = Path(output_root) if output_root is not None else dio.resolve("outputs")
    gcfg, ecfg = gd.load_config(repo / "robot_vision/configs/v4/gesture_data.json"), ev.load_config(repo / "robot_vision/configs/v4/eval_dev.json")
    runs = gate(setting, pairs, output_root, gcfg, repo)
    res = ev.evaluate(runs, ecfg, gcfg)
    res["final_setting"] = setting
    res["splits"] = "TEST looks and clips only (data_splits_v4.guard_run, final evaluation), frozen configs verified"
    res["watchdog_stops"] = watchdog_block(runs)                     # B11(a): a result, never a refusal
    out = dio.new_run_dir({"paths": {"output_root": str(output_root)}}, f"{fg.EVAL_PREFIX}_{setting}")
    (out / "config_used").mkdir()
    for f in fz.config_files(repo):
        shutil.copy2(repo / f, out / "config_used" / Path(f).name)
    shutil.copy2(repo / fz.FROZEN_REL, out / "config_used" / "frozen.json")
    dio.write_json(out / "eval.json", res)
    git = dio.git_info()
    frozen_sha = fz.sha256_lf(repo / fz.FROZEN_REL)
    dio.write_json(out / "run.json", {"git": git, "setting": setting, "sessions": [[u.name, b.name] for u, b in pairs],
                                      "frozen_sha256": frozen_sha})
    (out / "eval.md").write_text(ev.markdown(res) + "\n" + watchdog_markdown(res["watchdog_stops"]), encoding="utf-8")
    fg.write_done(out, setting, "evaluation", {"git_commit": git["commit"], "evaluation_folder": out.name, "runs": len(runs),
                                               "frozen_sha256": frozen_sha})      # last: a crash above leaves no marker
    return out, res


def main(argv=None) -> None:
    import decision_io as dio

    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--setting", required=True, choices=fg.settings())
    ap.add_argument("--session", nargs=2, action="append", required=True, metavar=("UNITY", "BRIDGE"))
    a = ap.parse_args(argv)
    pairs = [(dio.resolve(u), dio.resolve(b)) for u, b in a.session]
    out, res = evaluate_final(a.setting, pairs)
    print(ev.markdown(res) + "\n" + watchdog_markdown(res["watchdog_stops"]))
    print(f"Folder: {out}\nFINAL_DONE.json written: setting {a.setting} cannot be evaluated again.")


if __name__ == "__main__":
    main()
