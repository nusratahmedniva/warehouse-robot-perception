# configs/v4: v4 study configs

v3 configs in `configs/` are frozen (`configs/hri_frozen.json`) and are not touched. Everything v4 declares lives here
and is frozen separately (`configs/v4/frozen.json`, written before the final runs; not yet created).

| file | for |
|---|---|
| `bridge.json` | Bridge config for protocol version 3 (`docs/protocol_v3.md`). Pass it with `python -m bridge.server --config configs/v4/bridge.json`; without it the server speaks version 2 as before. Also holds the HUD log length and the intrinsics consistency tolerance. |
| `gt_eval.json` | Settings of `gt_path.py` (ground-truth evaluation): A* length tolerance, "near the optimal path" distance, leak-test pixel tolerance. Evaluation only. |
| `gesture_data.json` | Settings of `gesture_data.py` (truth.jsonl loader, truth-to-frame join, clips): the join tolerance (0.06 s) and the allowed commands, arms and phases of `docs/protocol_v3.md`. Evaluation only. |
| `data_splits.json` | v4 splits by avatar look and by animation clip (development vs test), read by `data_splits_v4.py`. **Placeholder names** until Nusrat sends the real ones; a final evaluation is refused while `placeholder` is true. |

More v4 configs (decision rules, zoom, gesture reader, commander rule) are added in later phases.
