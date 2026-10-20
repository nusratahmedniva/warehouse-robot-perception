# Audit: guided warehouse robot (protocol v2, branch anisha/step5-7)

Status on 20 October 2026. Every figure names its folder under `robot_vision/outputs/` (git-ignored) and the number
of runs or frames it covers. Accuracy is always given with its coverage. "vision" means YOLO11s-pose people and arm
direction plus MediaPipe STOP, with decisions from the Python state machine. Unity provides only the simulation
and the scoring truth.

## 1. Step table

| Step | What | Status | Evidence |
|---|---|---|---|
| 0 | Message format | done | protocol v2, `docs/protocol.md` (adds trial_index / trial_running) |
| 1 | Robot and cameras | done (Nusrat, PR #6) | RobotRig, DiffDriveController, PanTiltCamera, Camera360 |
| 2 | TCP bridge | done (Nusrat) | final run: 0 watchdog stops, Unity-measured round trip 0.78 ms mean |
| 3 | Perception | done, frozen | `hri_perception.py`; gesture sweep `hri_dev_eval_20261020_141423`; people `hri_dev_eval_20261020_165909` |
| 4 | Worker and roadmap | done | Mixamo worker (not in git), roadmap A, J1, J2, E1-E4; `roadmap.json` equals the Unity builder (test) |
| 5 | State machine and steering | done, frozen | `hri_control.py`, simulator `hri_sim.py`, 23 controller tests |
| 6 | Scenarios | done | `TrialRunner`, `GoalSequence` (seeded goal B, pinned in both test suites), `TrialBatchPlay` |
| 7 | Logging and analysis | done | `hri_trials.py`, `hri_analysis.py`, `hri_eval_dev.py` |
| Final | Final trials, seed 2, once | **done: 10/10** | `trials_final_Task2_20261020_172445` (FINAL_DONE.json) |

## 2. Final result (final seed 2, run once, commit ce37a56)

Commit ce37a56 is the frozen commit 1a574cb plus `trials.json -> mode: final`, and nothing else. Frozen-config hashes
are in `configs/hri_frozen.json`. The branch was pushed with the frozen commit before the final run.

**10/10 SUCCESS** (Wilson 95 %: 0.72-1.0). The goal order E1 E2 E4 E2 E1 E3 E4 E1 E4 E1 was recomputed from the seed
and matches.

| run | goal B | outcome | distance to B (m) | time (s) | junctions shown > read | closest to worker (m) |
|---|---|---|---|---|---|---|
| 1 | E1 | SUCCESS | 0.031 | 40.64 | J1: FORWARD > FORWARD | 1.127 |
| 2 | E2 | SUCCESS | 0.033 | 42.56 | J1: RIGHT > RIGHT | 1.132 |
| 3 | E4 | SUCCESS | 0.052 | 72.88 | J1: LEFT > LEFT; J2: RIGHT > RIGHT | 1.264 |
| 4 | E2 | SUCCESS | 0.050 | 42.78 | J1: RIGHT > RIGHT | 1.275 |
| 5 | E1 | SUCCESS | 0.050 | 40.06 | J1: FORWARD > FORWARD | 1.140 |
| 6 | E3 | SUCCESS | 0.048 | 76.62 | J1: LEFT > LEFT; J2: FORWARD > FORWARD | 1.033 |
| 7 | E4 | SUCCESS | 0.055 | 73.66 | J1: LEFT > LEFT; J2: RIGHT > RIGHT | 1.260 |
| 8 | E1 | SUCCESS | 0.048 | 40.22 | J1: FORWARD > FORWARD | 1.141 |
| 9 | E4 | SUCCESS | 0.058 | 74.60 | J1: LEFT > LEFT; J2: RIGHT > RIGHT | 1.262 |
| 10 | E1 | SUCCESS | 0.049 | 42.64 | J1: FORWARD > FORWARD | 1.075 |

- Junctions: 14/14 read as shown, all at the first ask.
- Safety: 0 collisions, 0 with a person; the closest approach was 1.03 m from the robot body to the worker axis.
- Time per step (mean over 10 runs):
  - navigate 39.8 s, scan 0.95 s, approach 9.2 s, ask 0.73 s, gesture 1.73 s, execute 2.16 s;
  - stale-perception stops 1.35 s (max 5.8 s);
  - total 54.7 s (max 76.6 s, of the 240 s limit).
- Motion: average speed 0.51 m/s, max 0.80 m/s; turn rate max 51.6 deg/s; travelled / straight line 1.30.
- Inference, mean per run over runs:
  - panorama YOLO 256 ms, gesture YOLO 62 ms, MediaPipe 21 ms, JPEG decode 5.9 ms;
  - total per frame 177 ms.
- Folders: `trials_final_Task2_20261020_172445`, `bridge_guide_20261020_172422`, `hri_trials_20261020_173421`,
  `hri_analysis_20261020_173421` (analysis.md, running_success.png, step_times.png).
- Perception against truth (recall, distance error) is **not_evaluated** on the final session, because
  `hri_eval_dev.py` refuses final sessions by design.

## 3. Development evaluation (dev seed 1 only)

### Gestures: sweep of 140 samples, 955 pan-tilt frames, five-direction classifier

Source: `gestures_sweep_development_20261020_112717` + `bridge_guide_20261020_112702`.

| shown | frames | coverage | accuracy | 1.0 s hold accepted (of 20) |
|---|---|---|---|---|
| LEFT | 98 | 1.0 | 1.0 | 18 correct, 2 none |
| FORWARD_LEFT | 106 | 1.0 | 1.0 | 20 |
| FORWARD | 120 | 1.0 | 1.0 | 20 |
| FORWARD_RIGHT | 108 | 0.963 | 1.0 | 19 correct, 1 none |
| RIGHT | 105 | 0.99 | 1.0 | 20 |
| NONE | 97 | false-command rate 0.0 | - | 0 false accepts |
| STOP | 100 | 1.0 | 0.97 | 1 false accept (as FORWARD_LEFT) |

| shown \ read | NONE | LEFT | FORWARD_LEFT | FORWARD | FORWARD_RIGHT | RIGHT | STOP |
|---|---|---|---|---|---|---|---|
| NONE | 97 | 0 | 0 | 0 | 0 | 0 | 0 |
| LEFT | 0 | 98 | 0 | 0 | 0 | 0 | 0 |
| FORWARD_LEFT | 0 | 0 | 106 | 0 | 0 | 0 | 0 |
| FORWARD | 0 | 0 | 0 | 120 | 0 | 0 | 0 |
| FORWARD_RIGHT | 4 | 0 | 0 | 0 | 104 | 0 | 0 |
| RIGHT | 1 | 0 | 0 | 0 | 0 | 104 | 0 |
| STOP | 0 | 0 | 3 | 0 | 0 | 0 | 97 |

Strict hold vs tolerant hold (NONE gaps up to 0.3 s): identical in the sweep, and 200/200 each in the simulator with
the measured rates.

### People on the 360 deg camera (development trials)

| distance | `_140241` recall (n) | `_163348` recall (n) | `_164719` recall (n) |
|---|---|---|---|
| 0-3 m | 0.885 (381) | 0.91 (424) | 0.86 (363) |
| 3-6 m | 1.0 (515) | 1.0 (573) | 1.0 (522) |
| 6-9 m | 0.533 (244) | 0.584 (274) | 0.523 (214) |
| 9-12 m | 0.0 (170) | 0.0 (193) | 0.0 (157) |
| all frames within 12 m | 0.75 | 0.764 | 0.753 |

- Distance error (ankles, all matched frames):
  - mean signed: +0.255 m, +0.258 m and +0.251 m in the three sessions;
  - median absolute: about 0.22 m; 90th percentile: about 0.47 m.
- False-positive people: 0.024-0.028 per frame.

**Effect of the about 84 % panorama detection rate.** Misses are almost all beyond 6 m. Scan and approach happen
within 6 m, where recall is 0.86-1.0, so a scan took 0.70-0.93 s on average. The 1.0 s hold reads the pan-tilt
camera, not the panorama, so panorama misses do not reach it.

### Development trial sessions (vision, dev seed 1, 10 trials each)

| session | result | junctions | note |
|---|---|---|---|
| `trials_development_Task2_20261020_113942` | 2/3 (interrupted) | - | trial 3 timed out: panorama YOLO slowed to about 900 ms with uncapped Unity rendering; kept, not used |
| `trials_development_Task2_20261020_140241` | 10/10 | 15/15 | after capping batch rendering at 60 fps |
| `trials_development_Task2_20261020_163348` | 9/10 | 14/15 | diagonals dropped; trial 8 aborted at J2 (see 4.2) |
| `trials_development_Task2_20261020_164719` | 10/10 | 15/15 | with reask_shift_m; the re-ask did not trigger |

## 4. Changes made after seeing results (disclosed)

1. **Diagonals dropped.** FORWARD_LEFT and FORWARD_RIGHT now read NONE; they are kept under `dropped_directions` in
   `hri_perception.json`. This goes against the pre-declared `diagonals_reliable_if` criterion, which they passed.
   The reasons:
   - the only safety-relevant error was STOP read as FORWARD_LEFT (3/100 frames, 1/20 holds);
   - no junction has a diagonal branch (0/15 readings needed one).

   It was the owner's decision.
2. **New viewpoint before the second ask** (`reask_shift_m` 0.4 in `hri_control.json`). In dev trial 8 at J2,
   YOLO collapsed both shoulders to one point and placed the wrist about 100 px off on a clearly shown RIGHT
   (`bridge_guide_20261020_163322/frames/frame_pan_tilt_004500.jpg`). The repeat ask, from the same standstill,
   saw the same image.
   - The simulator test with a view-specific blind spot aborts without the shift and succeeds with it.
   - In Unity it never triggered (every junction was read at the first ask).
3. **Batch rendering capped at 60 fps** (`TrialBatchPlay`). This is a runner setting, not a threshold. Uncapped
   rendering shared the GPU with YOLO on MPS.
4. **Changes from simulator runs only, before any Unity trial** (in `hri_control.json`):
   - the speed-dependent person-in-path stop distance;
   - `max_none_gap_s` 0.3.

## 5. Checks

- Python: 214 tests pass (1 skipped), including `test_hri_frozen.py` (config hashes and fixed trial settings).
- Unity EditMode: 10/10 pass (GoalSequence pinned values and others).
- Goal order recomputed from the seed: matches in every session.
- `RobotWheel_Dark.mat` (changed by Unity reimports) is restored before each commit.

## 6. Remaining limitations

- **Inference slowdown with Unity running.** On the 8 GB Mac, panorama YOLO takes 157 ms alone (6-minute soak) but
  190-450 ms with Unity running, up to 790 ms.
  - Stale-perception stops reached 52 s in one dev trial; in the final they stayed at most 6 s.
  - The cause is not identified.
- **Re-ask viewpoint shift:** validated in the simulator only.
- **Small samples:** 10 final trials (Wilson lower bound 0.72), with E3 (two junctions) once.
- **Final-session perception metrics:** not_evaluated (by design).
- **Scenario simplifications:**
  - people and gestures are scripted poses of one Mixamo worker;
  - one worker per junction, no other moving people during the trials.
- **"Person steps into the path" stop:** tested only in the simulator (`hri_sim.py` intruder test), not in Unity.
  No Unity trial has a person entering the robot's path, so this stop has no Unity evidence.
- **Mixamo files:** not in git (licence); each user must add them.

## 7. Reproduce

From `robot_vision/`, start the bridge first, then Unity.

- **macOS Terminal:**
  1. `.venv/bin/python -m bridge.server --mode guide --perception vision`
  2. `/Applications/Unity/Hub/Editor/2022.3.62f3/Unity.app/Contents/MacOS/Unity -batchmode -projectPath ../unity/Robotics-Warehouse/WarehouseProjectURP -executeMethod WarehouseRobot.ScenarioEditor.TrialBatchPlay.Run -trialTimeout 2700 -logFile trials.log`
- **Windows PowerShell:**
  1. `.\.venv\Scripts\python.exe -m bridge.server --mode guide --perception vision`
  2. `& "C:\Program Files\Unity\Hub\Editor\2022.3.62f3\Editor\Unity.exe" -batchmode -projectPath ..\unity\Robotics-Warehouse\WarehouseProjectURP -executeMethod WarehouseRobot.ScenarioEditor.TrialBatchPlay.Run -trialTimeout 2700 -logFile trials.log`
- **Then, on both systems:**
  1. `python hri_trials.py --unity outputs/<trials folder> --bridge outputs/<bridge folder>`
  2. `python hri_analysis.py outputs/<hri_trials folder>`
  3. Development sessions only: `python hri_eval_dev.py --sweep ... --trials ... --simulate 200`

The final mode runs once per task: it refuses if a `trials_final_<same task>_*` folder holds FINAL_DONE.json
(see section 8).

## 8. Changes before the Task 1 final (21 October 2026)

Task 1 is the straight A to B run: B is the roadmap's `task1_goal` (E1) in every trial, and the worker shows FORWARD
at J1. It runs with exactly the settings frozen for Task 2. All changes below were made before any Task 1 trial.

1. **Run-once guard per task.** `TrialRunner` refused a final if *any* `trials_final_*` folder held
   FINAL_DONE.json, so the Task 2 final would have blocked the Task 1 final. It now refuses only if a
   `trials_final_<same task>_*` folder holds FINAL_DONE.json (`FinalRunGuard.EarlierFinal` in the WarehouseHRI
   assembly).
   - EditMode tests (`FinalRunGuardTests`): Task 2 final present -> Task 1 final allowed; Task 1 final present ->
     Task 1 final refused; an unfinished final folder (no FINAL_DONE.json) does not block.
   - Goal choice, worker placement and scoring in `TrialRunner` are unchanged.
2. **Per-task frozen settings** (`configs/hri_frozen.json`).
   - The shared hashes (`sha256`: hri_control, hri_perception, gesture_hri, roadmap, bridge, robot_unity,
     bridge_unity) are unchanged. `test_hri_frozen.py` pins them to the values recorded for the Task 2 final
     (ce37a56).
   - Per task: `tasks.<task>.route` and `tasks.<task>.trials_fixed`, checked for the task named in `trials.json`.
     Task 1 uses the Task 2 seeds, trial count, timeout and success criteria (tested).
   - `trials.json`: task Task1, mode development.
3. **robot.json added to the frozen set** (`sha256_added_2026_10_21`, ff8a6673...8880).
   - Last changed in 0c2771d, an ancestor of ce37a56.
   - `git log ce37a56..HEAD -- robot_vision/configs/robot.json` is empty, and its hash at ce37a56 equals the
     current one.
4. **Pose weights hash recorded** (`pose_weights`): `robot_vision/models/yolo11s-pose.pt`, sha256
   1060bda4...c2ba. **Status: to be confirmed against the Task 2 machine's file.**
   - Downloaded on 21 October 2026 on the Task 1 machine from the official Ultralytics assets release v8.4.0
     (git-ignored, not committed).
   - The hash equals `pose_model.sha256` in the frozen `hri_perception.json`. `HriPerception` checks that hash at
     load and refuses to run otherwise, and the Task 2 final ran in vision mode. This is strong evidence that the
     Task 2 machine used the same file, but the file itself has not been compared.
   - The Unity runner now also refuses a final if the local file's hash differs (`FinalRunGuard.WeightsProblem`).

**No perception, gesture or state-machine setting changed.** `git diff ce37a56 -- robot_vision/configs` lists only
`trials.json` (task, mode, mode note) and `hri_frozen.json`. hri_control.json, hri_perception.json, gesture_hri.json,
roadmap.json, bridge.json, robot.json and the two Unity configs are byte-identical to the Task 2 final.

**Task 1 development runs only check that the pipeline works** (bridge, perception, trial runner and logging on the
Task 1 route, dev seed 1). They must not be used to adjust any setting. If one shows a problem that needs a change,
the change is disclosed here and the frozen hashes are re-recorded before the Task 1 final.

Notes:
- Machine for the Task 1 final: to be recorded.
  - If it differs from the Task 2 machine, timing figures (inference times, stale-perception stops) are not
    comparable between the tasks. Success, accuracy, distances and travel times remain comparable.
  - Development runs on Nusrat's PC are pipeline checks only.
- The Unity EditMode tests are run locally; CI runs only the Python tests.
- Checks on 21 October 2026 (Windows): Python 222 tests pass, including 11 in `test_hri_frozen.py`; Unity
  EditMode 15/15 pass (10 earlier + 5 `FinalRunGuardTests`).
