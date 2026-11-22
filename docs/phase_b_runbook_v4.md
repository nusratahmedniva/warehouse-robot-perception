# Phase B runbooks: from a sitting zip to the results (AUDIT.md 16.33 to 16.33.2)

Anisha's side. Two commands, one for the A/B finals and one for the avatar experiment. Each one stops at the first failure with the reason, writes its report either way, and never re-evaluates a setting or reports a part twice. Run them from `robot_vision/` with the project venv (Windows `.\.venv\Scripts\python.exe`, macOS `.venv/bin/python`).

## A/B finals, per sitting zip

```
python process_final_zip_v4.py <final_sitting zip> --sha256 <the hash Nusrat sent>
```

| step | what it does |
|---|---|
| 1 | SHA-256 against the one given and the `.sha256` file, `testzip`, every member against `MANIFEST.json`; the zip is read in place |
| 2 | copies ONLY the settings' folders out of the zip (member by member, hash checked, no code, nothing run) into `final_root` (`outputs/`, git-ignored; `--final-root` to change); the seven acceptance criteria of `final_plan.json` and the interruption / resume rule, for ALL settings before anything is evaluated |
| 3 | `hri_eval_final_v4.evaluate_final` per setting, once (`FINAL_DONE.json`) |
| 4 | `export_csv_v4.export_final` per setting (`runs.csv`, `dialogs.csv`), then the combined table over every final export so far (Wilson per setting, Newcombe per pair) |
| 5 | `phase_b_tables`, `phase_b_pairs` (B ON vs OFF, Set A vs Set B, A2 right vs left), `phase_b_gesture_confusion`, `phase_b_branch_confusion`, each as CSV and Markdown, in the report folder `process_final_zip_v4_<time>/`; the figures (`paper_v4/figures_v4.py`) are NOT RUN in a final (it reads development data only) |
| 6 | the entries appended to `configs/v4/archive/results_manifest.json` (a tracked file: commit it; `--no-manifest-append` to skip) |

**Dry run on development data** (no final marker anywhere, steps 3 and 6 skipped, a NEW folder under `development_root`, outside the repository):

```
python process_final_zip_v4.py ~/Downloads/step5_t0_logs_20261121_002030.zip --sha256 <its hash> --development [--no-figures] [--only A1 B1]
```

`--no-figures` is needed on the step-5 sessions until `paper_v4/figures_v4.py` handles the dialog outcome `not_evaluated` (AUDIT 16.33.2).

## Avatar experiment

```
python process_avatar_zip_v4.py <avatar_experiment zip> --sha256 <hash>
```

Follows `docs/avatar_experiment_protocol_v4.md` exactly: the guard (`avatar_experiment_part`, STARTED / DONE, frozen hashes, names), the INVALID rules (frames and headers, the timing rule, the wrong record, a placeholder colour while `shaders_compiling`), the floor (Play: 2 sequences and 10 single takes per arm and distance), the per-take shares, the take as the unit (bootstrap over takes, 2000 resamples, seed 1; Wilson only for take-level yes/no), and the tables per look, per kind group, per look role and per clip role as CSV and Markdown. `play/` is the headline and `edit/` the control; they are never pooled. The results go to `avatar_root` of `configs/v4/experiments/phase_b.json` (outside the repository). The frames are copied to a temporary folder, used and removed; the zip stays the evidence. It runs the real detector (`look_check_v4.RealDetector`, pose weights and MediaPipe model needed) on the real recordings.

## Limits (also in AUDIT 16.33.2)

Repetitions of an INVALID group and the Python side of the avatar interruption rule are not built; the real warm-up record's format is assumed (`recordings.jsonl` `shaders_compiling`, `cyan_pixels`, `magenta_pixels`); a resumed final is recorded in the archive entry but only its first part is archived until the archive tool is extended.
