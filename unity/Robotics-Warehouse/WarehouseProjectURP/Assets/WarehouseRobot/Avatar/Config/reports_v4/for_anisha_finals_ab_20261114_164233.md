# For Anisha: what the Python side needs for the experiments A/B finals (2026-11-14)

From Nusrat's Unity side, branch `nusrat/v4-finals-ab` (declared in `Avatar/Config/experiments_ab.md` sections 7 and 8). Nothing under
`robot_vision/`, `docs/` or `external/` was changed; nothing was frozen or run. Each item says what, why, and what Unity already does about it.
Items marked **decide** are choices for you (and Nusrat) before the freeze.

## 1. Decisions before the freeze

1. **Lie detection in the finals (decide).** Unity's final configs name lie detection ON (second opinion + reject impossible, backtrack off,
   `scenarios_ab.json` `detection.on`) for all nine settings, so A and B differ only in the lies. The detection-off comparison would stay in the
   simulator. Alternative: B1 to B4 also with detection off as four more settings (`B1_off` ...), about +80 runs / +2.5 h; Unity would add four
   final configs with `lie_detection` "off" (the checks already accept it).
2. **The 270 s timeout with detection on (decide).** `timeout_s` 270 was set from Task 2 runs without second opinions. Estimate from the four Task 2
   development sessions x the simulator's on/off time ratio (16.13.1): the E5 and E6 routes of A3, B3, B4 come to 243 to 279 s, 8 of 20 runs of each
   above 0.9 x 270 s. Timeouts are likely in A3, A4, B3, B4. Unity reads the value from `final_plan.json` and changed nothing. If it changes, it
   must change (with its rule) before the freeze.
3. **B2 with the right turn only (decide with Nusrat).** The matrix is A1, A2_right, A2_left, A3, A4, B1, B2_right, B3, B4 (A2_left has no B
   counterpart). Adding B2_left = one more setting (+20 runs).
4. **The third worker at J1 (A3, A4, B3, B4) wears the same test look as the first** (one test look per gender). Development rotates two looks
   per gender. Accept, or say what else you want.
5. **Run order and sittings (decide with Nusrat).** Estimated 9.2 h for 180 runs (6.8 h with detection off). Proposed two sittings:
   {A1, B1, B3, A3} about 4.2 h and {A2_right, B2_right, B4, A4, A2_left} about 5.1 h; or three sittings of 2.7 to 3.4 h keeping each A/B pair together.

## 2. `configs/v4/final_plan.json`

- `settings`: the nine names **A1, A2_right, A2_left, A3, A4, B1, B2_right, B3, B4** (exactly these spellings: Unity's guard looks them up and the
  run-once markers carry them). The four Task 2 settings are superseded on the Unity side (`final_v4.json` `superseded_settings`); Unity refuses
  them. Proposed entries: `{"zoom": null, "bystanders": null, "experiment": "<A1..B4>", "map": "<corridor|turn|turn_left|roadmap>",
  "lie_detection": "on", "note": ...}` (zoom null: the experiment control files keep control.json's zoom block; `preflight_final` compares
  `zoom` only when it is not null; `bystanders` null: every experiment run has several workers, so `Run.bystanders` would be true anyway).
- `test_assignment`: for each of the nine, `{"looks": ["sunbox_m_shirt_plaid", "sunbox_f_shirt_plaid"], "clips": ["point_mixamo_02", "proceed_ik_03"]}`
  (what Unity's final configs hold; `data_splits.json` already lists them as test).
- `task` Task2, `final_seed` 2, `runs_per_setting` 20, `timeout_s` (see 1.2), `success_radius_m` 0.3: Unity reads these and nothing else.
- `unity_files_and_guard`: unchanged form (`freeze_list` = `Avatar/Config/final_v4.json`, key `freeze_files`); the list itself is now the new
  study's B9 list (22 files, below). `freeze_v4.unity_files` picks it up with no code change.
- `acceptance_criteria`: the seven B11 criteria apply unchanged (`finals_v4/check_session_v4.ps1` runs them on experiment sessions as on Task 2
  ones). Your decision whether an experiment needs another one.
- `tests/test_v4_frozen.py` pins `settings` to the four Task 2 names (line 173); it changes with the plan.

## 3. `bridge/server.py` `FINAL_CONTROL` (the `--final-setting` names)

| `--final-setting` | `--control-config` (from Unity's `sessions/final_ab_<setting>.json` `python_control`) |
|---|---|
| A1, B1 | `configs/v4/experiments/control_lie_on_a1.json` |
| A2_right, B2_right | `configs/v4/experiments/control_lie_on_a2_right.json` |
| A2_left | `configs/v4/experiments/control_lie_on_a2_left.json` |
| A3, A4, B3, B4 | `configs/v4/experiments/control_lie_on.json` |

The launcher (`finals_v4/run_session_v4.ps1 -Experiment X [-Side right|left]`) passes this file and refuses a final when `FINAL_CONTROL[setting]`
is missing or names another file. The server's map comes from the control file's `roadmap` key; Unity uses the same map from `scenarios_ab.json`
(A2_left: Unity's `roadmap_proposals/turn_left.json`, equal to your `turn_left`).

## 4. Freeze (`freeze_v4.py`)

- The experiment control files and maps are **not** frozen today (16.12 item 5 kept them out): `configs/v4/experiments/control_lie_on*.json`
  (and `control_lie_off*.json` if 1.1 adds detection-off settings) and `roadmap_a1.json`, `roadmap_a2_right.json`, `roadmap_a2_left.json` must be
  in the freeze for a final that runs with them (`FROZEN_EXTRA` or a glob of `configs/v4/experiments/`). `scenarios_ab.json` already is.
  `tests/test_v4_frozen.py` `ScriptTests` pins `FROZEN_EXTRA` to `scenarios_ab.json` only.
- `export_csv.json` stays outside by your 16.10.1 reasoning, or joins if the CSV columns of the finals should be fixed.
- B9 (Unity): `final_v4.json` `freeze_files`, now 22 files: the v4 scene, `bridge_unity_v4.json`, `robot_unity_v4.json`, `worker_v4.json`,
  `WorkerV4.prefab`, `trial_workers_v4.json`, `final_v4.json`, `trial_plan_v4.json`, `looks_ab.json`, `experiments_ab_unity.json`,
  `roadmap_proposals/turn_left.json`, `look_check.json`, `look_check_play_ab.json` (the avatar experiment) and the nine
  `sessions/final_ab_<setting>.json`. The four superseded `sessions/final_zoom_*.json` / `final_bystanders.json` left the list.

## 5. Evaluation and CSV export per experiment

- `final_guard_v4.check_setting` / `hri_eval_final_v4.py --setting` choose from `fg.settings()` = the plan's settings: with item 2 the nine names
  become valid. `check_setting` checks seed 2, task, mode `final`, 20 runs; the Unity experiment sessions write `session.json` with
  `mode` "final", `seed` 2, `task` Task2, `final_setting` <setting>, plus the experiment fields (`experiment`, `set`, `lie_probability`, `map`,
  `layout`, `placement`, `workers_plan`).
- **`export_csv_v4.py` is development-only** ("hri_eval_dev_v4.load_sessions runs data_splits_v4.guard_run before anything is read"): the finals'
  `runs.csv` / `dialogs.csv` per experiment need a final mode (test split with `final_evaluation`, frozen configs, once per setting with its own
  run-once marker like `FINAL_DONE.json`), per setting and one combined table over the nine (A vs B per scenario, A2 right vs left).
- Per experiment the final evaluation should report: SUCCESS with Wilson 95 % intervals and failure kinds (aborted, wrong goal, timeout, collision),
  median time, trail against the optimal corridor (`gt_path.py`), lies given / detected / corrected / fooled (Set B), safety stops, watchdog stops
  (a result, B11 (a)), and every rate with its count. Unity's `results_unity.csv` and `truth_run###.json` are as in the development sessions.
- The launcher prints, after a valid B11 check, the commands it expects (not run): `hri_eval_final_v4.py --setting <setting> --session <U> <B>`
  and `export_csv_v4.py --session <U> <B>`; change them if your final tools differ.

## 6. Smaller items

- `truth.jsonl` of an experiment carries the extra field `active` (inactive workers logged idle, section 3); `gesture_truthful` as amendment 4.
- In a final the third J1 worker repeats the first worker's look; `guard_run` sees two looks per run, both test.
- The avatar experiment (section 8) uses `look_check_v4.py` unchanged; PROCEED is not recorded by Unity's look checks, so it stays not evaluated.
- Unity Edit Mode was red on main 15f70cf (216/221) after `data_splits.json` gained the experiment looks: the Task 2 worker plan now ignores looks
  that worker_v4.json does not have (fixed on Nusrat's branch, step 1). Nothing to do on your side.
