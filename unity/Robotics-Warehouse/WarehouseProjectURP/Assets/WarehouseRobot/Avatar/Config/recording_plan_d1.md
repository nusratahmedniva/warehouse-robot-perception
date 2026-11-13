# v4 development recordings (Stage D1): the plan, declared before any D2 recording

Written **2026-11-12** by Nusrat (with Claude Code), committed **before any Stage D2 session is recorded**. It follows
`Avatar/Config/upgrade_design.md` (sections 10 and 11), Anisha's `hri_eval_dev_v4.py` (what it scores: frame-level accuracy
per command in the phases gesturing and holding, commander accuracy with and without bystanders, the junction-level dialogs
and the standoff) and AUDIT.md 14.11 (thresholds set on development data only, B12). Nothing here is a threshold.

## Rules for every session

- Development seed 1, development looks `sunbox_m1` and `sunbox_f1` (alternating per run, the trial runner's rotation) and
  development clips only; `sunbox_f2` and every test clip are never rendered (the runner and Python refuse them).
- `WarehouseRobot_v4.unity`, `TrialRunnerV4`, `TrialPlayV4` (not batch, so the HUD is drawn and screenshots are taken),
  Python `bridge.server --mode guide --task Task2 --perception vision --config configs/v4/bridge.json --resource-log`,
  threads mode, the committed configs. Run protocol reported before each session (free memory, programs running).
- Every session is checked with `python gt_path.py session <unity folder>` (both leak checks) and every run's
  `truth.jsonl` with `gesture_data.py` (Python refuses any bad line).
- A session that stops early is kept and reported; it is not re-run silently.

## Conditions and counts

| id | condition | how it is selected | runs | why this many |
|---|---|---|---|---|
| R1 | zoom on, no bystanders, PROCEED / POINT | the Stage C session itself (`trials_development_Task2_20261112_163710` + `bridge_guide_20261112_163011`, 20 runs, recorded with these settings) | 20 | the bulk of PROCEED and POINT frames; not re-recorded |
| R2 | zoom OFF, no bystanders, PROCEED / POINT | `--control-config configs/v4/control_zoom_off.json` | 10 | the zoom on / off comparison of the evaluation on the same goals (seed 1: the first 10 goals of R1) |
| R3 | zoom on, 3 bystanders (never gesturing) | `TrialPlayV4 -workersConfig Assets/WarehouseRobot/Avatar/Config/sessions/dev_bystanders.json` | 10 | commander accuracy with bystanders (the evaluation's with / without split) |
| R4 | zoom on, WAIT then the direction at every ask | `-workersConfig .../sessions/dev_wait_then_direction.json` | 6 | WAIT frames for the WAIT thresholds (about 2.5 asks per run: about 15 WAIT gestures, both looks) |
| R5 | zoom on, STOP while driving once per run | `-workersConfig .../sessions/dev_stop.json` | 6 | STOP frames for the STOP thresholds and the stop-and-resume check (6 STOP gestures, both looks) |

Trial count per session through `launch_prep.py --task Task2 --trials N` (development only). Total new runs: 32.

## What the calibration (D3) uses

All five sessions (R1 to R5), both development looks, frames of the commander in the phases gesturing and holding, exactly as
declared in `upgrade_design.md` section 10 and its section 13 entries. Reported per threshold: committed value, chosen value,
the rule's reason, and accuracy and coverage per grid value.

## After the calibration (D4)

A 3-trial session per condition R1 to R5 (15 runs) with the calibrated configs. **STOP and report if more than one trial in any
condition aborts, or if any wrong-branch decision occurs** (`upgrade_design.md` section 11).
