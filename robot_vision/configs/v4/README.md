# configs/v4: v4 study configs

v3 configs in `configs/` are frozen (`configs/hri_frozen.json`) and are not touched. Everything v4 declares lives here
and is frozen separately (`configs/v4/frozen.json`, written before the final runs; not yet created).

| file | for |
|---|---|
| `bridge.json` | Bridge config for protocol version 3 (`docs/protocol_v3.md`). Pass it with `python -m bridge.server --config configs/v4/bridge.json`; without it the server speaks version 2 as before. Also holds the HUD log length and the intrinsics consistency tolerance. |
| `gt_eval.json` | Settings of `gt_path.py` (ground-truth evaluation): A* length tolerance, "near the optimal path" distance, leak-test pixel tolerance. Evaluation only. |
| `gesture_data.json` | Settings of `gesture_data.py` (truth.jsonl loader, truth-to-frame join, clips): the join tolerance (0.06 s) and the allowed commands, arms and phases of `docs/protocol_v3.md`. Evaluation only. |
| `data_splits.json` | v4 splits by avatar look and by animation clip (development vs test), read by `data_splits_v4.py`. **Placeholder names** until Nusrat sends the real ones; a final evaluation is refused while `placeholder` is true. |

| `gesture_reader.json` | Phase 3: the moving-gesture reader (`gesture_motion.py`): window, keypoint and motion thresholds, POINT geometry, hand cues, class decision. All values INITIAL, with reasoning, to be set on development data. |
| `commander.json` | Phase 3: the commander rule (`commander_v4.py`): facing, motion margin, bearing link to the 360 camera. Initial. |
| `control.json` | Phase 3: the v4 dialog (`hri_control_v4.py`): hold, branch gap, WAIT (20 s decided), cross-check tie-break switch, zoom rule and its on/off switch. Drive, safety and the other dialog timings are read from the frozen v3 `configs/hri_control.json` (read only). |
| `eval_dev.json` | Phase 3: how `hri_eval_dev_v4.py` matches readings to workers and bins distances. Evaluation only. |

More v4 configs (frozen.json with hashes) are added before the final runs.
