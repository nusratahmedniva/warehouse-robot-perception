# configs/v4: v4 study configs

v3 configs in `configs/` are frozen (`configs/hri_frozen.json`) and are not touched. Everything v4 declares lives here and is
frozen separately by `freeze_v4.py` into `frozen.json`: while its `frozen` is false the thresholds are still being set on
development data; after Nusrat freezes it by hand (agreed with Anisha 2026-11-13; CLAUDE.md, AUDIT.md section 15), `tests/test_v4_frozen.py` fails if any file below, any v3 file v4 reads, or a model
file changes.

| file | for |
|---|---|
| `bridge.json` | Bridge config for protocol version 3 (`docs/protocol_v3.md`). Pass it with `python -m bridge.server --config configs/v4/bridge.json`; without it the server speaks version 2 as before. Also holds the HUD log length and the intrinsics consistency tolerance. |
| `gt_eval.json` | Settings of `gt_path.py` (ground-truth evaluation): A* length tolerance, "near the optimal path" distance, leak-test pixel tolerance. Evaluation only. |
| `gesture_data.json` | Settings of `gesture_data.py` (truth.jsonl loader, truth-to-frame join, clips): the join tolerance (0.06 s) and the allowed commands, arms and phases of `docs/protocol_v3.md`. Evaluation only. |
| `data_splits.json` | v4 splits by avatar look and by animation clip (development vs test) and the look styles, read by `data_splits_v4.py`. **Placeholder names** until Nusrat sends the real ones; a final evaluation is refused while `placeholder` is true. |
| `gesture_reader.json` | The moving-gesture reader (`gesture_motion.py`): window, keypoint and motion thresholds, POINT geometry, hand cues, class decision. All values INITIAL, with reasoning, to be set on development data. |
| `commander.json` | The commander rule (`commander_v4.py`): facing, motion margin, bearing link to the 360 camera. Initial. |
| `control.json` | The v4 dialog (`hri_control_v4.py`): hold, branch gap, WAIT (20 s decided), second look and re-approach, cross-check tie-break switch, zoom rule and its on/off switch. Since 2026-11-13: `lie_detection` (second opinion, reject impossible, backtrack; all false by default, AUDIT.md section 16); `control_zoom_on.json` / `control_zoom_off.json` carry the same block. Drive, safety and the other dialog timings are read from the frozen v3 `configs/hri_control.json` (read only). |
| `experiments/scenarios_ab.json` | Experiments A1-A4 / B1-B4 of the SIMULATOR study (AUDIT.md section 16): the two small maps (corridor, turn), the four scenarios with their placements, set A (truthful) and set B (lie probability 0.2), runs per scenario, seeds, trial timeout, the obstacle detour. Read by `hri_sim_v4.scenario_ab` and `run_experiments_ab_v4.py`. Simulator only. **Frozen** (`freeze_v4.FROZEN_EXTRA`). |
| `experiments/export_csv.json` | Columns, order and headers of `runs.csv` and `dialogs.csv` written by `export_csv_v4.py` (evaluation code). Edit this file to match the faculty's column list; the definitions of every field are in `export.json` of each export. Not frozen (AUDIT.md 16.10.1). |
| `eval_dev.json` | How `hri_eval_dev_v4.py` and `hri_eval_final_v4.py` match readings to workers and bin distances. Evaluation only. |
| `analysis.json` | The intervals (Wilson, bootstrap over runs), the archived v3 results used for research question 1 and the declared differences between v3 and v4 (`hri_analysis_v4.py`). Reporting only. |
| `final_plan.json` | The final settings (zoom_on, zoom_off, bystanders, zoom_on_repeat) and the numbers still BLANK (task, seeds, runs per setting, timeout, success radius) that Anisha fills before freezing; `freeze_v4.py` refuses to freeze while one is blank. |
| `frozen.json` | The freeze record written by `freeze_v4.py`. |

`configs/v4/archive/` (the results archive config and the manifest of session folders) is not part of the freeze: it lists run
folders, which are added after the runs. `configs/v4/experiments/` (2026-11-13, AUDIT.md section 16) is not reached by the glob `configs/v4/*.json`: `experiments/scenarios_ab.json` is frozen through
`freeze_v4.FROZEN_EXTRA` (it defines the experiments); `experiments/export_csv.json` is not frozen (it only chooses CSV columns; 16.10.1).
