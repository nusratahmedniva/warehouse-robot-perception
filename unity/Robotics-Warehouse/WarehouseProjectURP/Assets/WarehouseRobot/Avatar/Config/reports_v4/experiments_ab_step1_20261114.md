# Experiments A/B, step 1 (open items): report only, nothing changed

Written 2026-11-14 by Claude for Nusrat and Anisha. Branch nusrat/v4-experiments-ab at a6839ae (= main). Scripts used (report-only,
read the session folders, never write into them): `false_stop2.py`, `proceed_hand.py`, `timing.py` in Claude's session scratchpad (not copied
under robot_vision/: the import-isolation tests parse every .py file there).

## (a) Play session under the run protocol, threads mode

Session: `finals_v4/run_session_v4.ps1 -Setting zoom_on -Rehearsal -Trials 3` (development looks sunbox_m1 / sunbox_f1, development clips,
`control_zoom_on.json`, threads, Unity Editor window). Unity `trials_development_Task2_20261114_015118`, bridge `bridge_guide_20261114_014758`,
protocol note `run_protocol_rehearsal_zoom_on_20261114_014757.txt`.

Run protocol: power mode Best performance on mains (scheme "AMD Ryzen Balanced"); free memory before 3,048 of 14,226 MB. Still running (not
closed): Claude (9 processes, 986 MB; VS Code with the Claude Code session that ran this), NVIDIA container x5 and overlay x5, warp-svc;
VS Code ("Code") is the most frequent other CPU user in the resource log.

| measure | value | declared limit (configs/v4/bridge.json timing_limits) | |
|---|---|---|---|
| loop lag max | 68.0 ms | 100 ms | met |
| loop lag p99 | 21.0 ms | 25 ms | met |
| round trip max (all replies, network thread) | 42.5 ms | 150 ms | met |
| round trip p95 / median | 2.6 / 1.9 ms | p99 50 ms | met |
| watchdog stops | 0 | (B11(a): a result) | |
| Unity frame stalls (no stop) | 2, longest gap 3,409.7 ms | | reported |
| perception worker events | none (threads) | 0 | met |
| free memory min / at end | 328 MB / 1,887 MB | recorded (14.16) | heavy paging: hard paging up to 37,010/s |
| outcome | 2/3 SUCCESS; run 3 aborted at A (PROCEED unclear after 2 asks, sunbox_m1) | | |

Against Stage C (loop lag max 193 ms, round trip max 196.8 ms) this session met every timing limit. The 14.16 condition ("threads must pass a Play
session within the limits, 0 watchdog stops, free memory recorded") is met in this session, with the free-memory minimum (328 MB) low and paging heavy.
The B11 checker (`check_session_v4.ps1`) stopped at its frozen-hash step when run through `powershell -File` (Python's `require_frozen` message on stderr
became a terminating NativeCommandError); criterion 1 (leak test) had passed. Script issue, not changed here.

## (b) False STOP during PROCEED

**Yes, the LIVE reader does it.** AUDIT.md 15 says only the replay did, because it compared with `v4_log.jsonl`. That file **cannot show a STOP that stops the robot**:
`hri_control.Controller.step` returns before `_tick` while a safety stop holds (`hri_control.py` lines 387-391), so `ControllerV4._read_tick` and
`_log_frame` never run on those frames. `decisions.csv` has the live evidence: its `gesture` column is `STOP` exactly when some fresh person's live window
reading is STOP (`hri_control_v4.ControllerV4.step`, line 871), and `safety` = `STOP gesture` when the controller acted on it.

Counted per pan-tilt frame (unique `gesture_time_s` in `decisions.csv`), joined to `truth.jsonl` at the frame time (0.06 s), commander rows in phases gesturing/holding:

| session | PROCEED frames | read STOP (live) | STOP safety stops (episodes) | total stopped | stops while driving | other |
|---|---|---|---|---|---|---|
| 13 Nov video session (`trials_development_Task2_20261113_194012` + `bridge_guide_20261113_193706`) | 117 | 73 (62 %) | 16 (15 during PROCEED, 1 during POINT) | 9.3 s | 0 (read 10, execute 5) | 1 POINT holding |
| R1 (`..._20261112_163710` + `bridge_guide_20261112_163011`) | 877 | 358 (41 %) | 196 | 51.6 s | **5** (0.2-0.8 m/s): 3 with **nothing shown** (truth NONE/idle, 0.1-0.2 s, at 0.8 m/s), 2 at the end of a PROCEED | 23 during POINT (read) |
| this session (`..._20261114_015118` + `bridge_guide_20261114_014758`) | 117 | 43 (37 %) | 17 | 5.8 s | 0 | |

Video session trial 3/3 (sunbox_m1): at A (`proceed_ik_02`) STOP frames 234.68-237.17 s, stops 234.90-235.09, 235.69-235.90, 236.59-236.89, 237.10-237.49 s; at J1
(`proceed_ik_01`, the clip of the video) 20 of 30 PROCEED frames read STOP (274.88-278.98 s), stops 275.11-275.20, 275.41-276.92 (1.51 s), 277.21-277.31, 277.60-277.81,
278.31, 278.61-279.41 s. The stops in `execute` hold the robot's turn toward the branch after the PROCEED was accepted (the commander is still holding).

Effects: a STOP during READ freezes the dialog (no READ tick, so no PROCEED evidence collects while it holds); a STOP in `execute` delays the turn. In these
sessions no STOP made a run fail by itself (the aborts at A were "unclear after 2 asks"); whether the frozen ticks contributed to them is not analysed.

**What in the PROCEED pose passes as STOP** (model outputs `model_outputs.jsonl`, MediaPipe pixel landmarks of the pan-tilt hands found while truth says PROCEED,
the reader's own rule `gesture_motion.open_palm_geometry`: four fingers extended (tip/wrist over mcp/wrist >= 1.6) and index-tip-to-pinky-tip spread from the wrist >= 20 deg):

| session | PROCEED hands | all four fingers extended | open-palm geometry passes | spread median (p10-p90) | MediaPipe label Open_Palm |
|---|---|---|---|---|---|
| video 13 Nov | 118 | 109 (92 %) | 81 (69 %) | 37.8 deg (4.4-64.7) | 1 |
| R1 | 738 | 677 (92 %) | 570 (77 %) | 40.3 deg (8.9-79.7) | 54 |
| (POINT, R1, for comparison) | 779 | 390 | 81 (10 %) | 20.6 deg | 0 |

1. **Raised flat hand.** Unity's PROCEED hand is flat: all fingers straight and together (`worker_v4.json` `hand_shapes.proceed`, 5 deg per joint, spread 0), on a
   forearm swung up toward vertical. In the image the four fingers are long against the palm: the extension test passes in 92 % of the hands.
2. **Spread is measured from the wrist, so it includes the palm's width.** Index tip and pinky tip sit at the two edges of the palm, so even with fingers together
   their angle at the wrist is about 2 x atan(half palm width / wrist-to-tip), 30 to 40 deg for these hands, above the 20 deg threshold. Unity's design note
   (`hand_shapes.proceed_why`: "together, the fingers stay far below the reader's open-palm spread") assumed the spread is between the fingers; it is not.
3. **Palm direction is not checked.** The reader uses 2D pixel landmarks only; the PROCEED hand shows the BACK of the hand (palm toward the body), which in 2D has the same
   landmark layout as a palm. MediaPipe's own label rejects most of these (Open_Palm on 1 of 118 and 54 of 738), but since 14.16 item 2 the label is logged, not required.
4. **No raised-arm or still-hand condition for STOP.** STOP is read from the linked hand alone over a 0.3 s window (look_check.json: `arm valid` not required for STOP), so
   the swing does not prevent it; the PROCEED hold swings at 1 to 2 Hz with the hand near the top of the swing for part of every cycle.

For Anisha's decision before the freeze (nothing changed here): e.g. require the MediaPipe Open_Palm label or a palm-facing test (world landmarks / handedness vs the hand's
normal), or measure the spread between finger directions instead of from the wrist; or on the Unity side a PROCEED hand with curled fingers (a hand-shape change in
`worker_v4.json`, a B9 file). Also: `v4_log.jsonl` should log the frames read during a safety stop, otherwise every live STOP stays invisible to the evaluation.
