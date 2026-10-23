# configs/v4: v4 study configs

v3 configs in `configs/` are frozen (`configs/hri_frozen.json`) and are not touched. Everything v4 declares lives here
and is frozen separately (`configs/v4/frozen.json`, written before the final runs; not yet created).

| file | for |
|---|---|
| `bridge.json` | Bridge config for protocol version 3 (`docs/protocol_v3.md`). Pass it with `python -m bridge.server --config configs/v4/bridge.json`; without it the server speaks version 2 as before. Also holds the HUD log length and the intrinsics consistency tolerance. |
| `gt_eval.json` | Settings of `gt_path.py` (ground-truth evaluation): A* length tolerance, "near the optimal path" distance, leak-test pixel tolerance. Evaluation only. |

More v4 configs (decision rules, zoom, gesture reader, commander rule) are added in later phases.
