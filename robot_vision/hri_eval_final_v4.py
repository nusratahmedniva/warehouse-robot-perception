"""v4 FINAL evaluation of one setting (zoom_on, zoom_off, bystanders, unseen_look). EVALUATION CODE ONLY.

Allowed only when ALL of this holds, otherwise refused (SystemExit) before any test data is read:
  1. configs/v4/frozen.json is frozen and every hash matches (v4 configs, v3 files v4 reads, pose weights, MediaPipe model);
  2. the setting has not been evaluated before (FINAL_DONE.json, final_guard_v4.py);
  3. every run lies wholly in the TEST split (data_splits_v4.guard_run with final evaluation: test looks and clips only, no
     development data, no mix, no placeholders) and is what the setting says (zoom, bystanders, runs, seed, task, Unity mode).
It runs the same evaluation as hri_eval_dev_v4.py (the numbers are computed by the same code), writes a new folder
<output_root>/hri_eval_final_v4_<setting>_<time>/ with eval.json, eval.md, the frozen record and every v4 config used, and
run.json (git commit), and only then FINAL_DONE.json (also a crash leaves no marker). No threshold is changed here.

Usage (from robot_vision/):
  python hri_eval_final_v4.py --setting zoom_on --session outputs/trials_final_X outputs/bridge_guide_Y [--session ... ...]
"""

from __future__ import annotations

import argparse
import shutil
from pathlib import Path

import data_splits_v4 as ds
import final_guard_v4 as fg
import freeze_v4 as fz
import gesture_data as gd
import hri_eval_dev_v4 as ev

HERE = Path(__file__).resolve().parent


def gate(setting: str, pairs, output_root, gcfg: dict, repo: Path = fz.REPO) -> list:
    """All the checks, in order, before and while the test data is loaded. Returns the loaded runs."""
    fz.require_frozen(repo)                                           # 1. frozen and every hash matches (models must be present)
    fg.ensure_not_done(output_root, setting, "evaluation", repo)       # 2. not evaluated before
    splits = ds.load(repo / "robot_vision/configs/v4/data_splits.json")
    runs = ev.load_sessions(pairs, gcfg, splits, final_evaluation=True, settings=[setting] * len(pairs))   # 3. test split only
    problems = fg.check_setting(setting, runs, repo)
    if problems:
        raise SystemExit(f"setting {setting!r} refused: " + "; ".join(problems))
    return runs


def evaluate_final(setting: str, pairs, repo: Path = fz.REPO, output_root: Path | None = None) -> tuple[Path, dict]:
    """The whole final evaluation of one setting; returns (new output folder, result). Raises SystemExit when refused."""
    import decision_io as dio

    output_root = Path(output_root) if output_root is not None else dio.resolve("outputs")
    gcfg, ecfg = gd.load_config(repo / "robot_vision/configs/v4/gesture_data.json"), ev.load_config(repo / "robot_vision/configs/v4/eval_dev.json")
    runs = gate(setting, pairs, output_root, gcfg, repo)
    res = ev.evaluate(runs, ecfg, gcfg)
    res["final_setting"] = setting
    res["splits"] = "TEST looks and clips only (data_splits_v4.guard_run, final evaluation), frozen configs verified"
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
    (out / "eval.md").write_text(ev.markdown(res), encoding="utf-8")
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
    print(ev.markdown(res))
    print(f"Folder: {out}\nFINAL_DONE.json written: setting {a.setting} cannot be evaluated again.")


if __name__ == "__main__":
    main()
