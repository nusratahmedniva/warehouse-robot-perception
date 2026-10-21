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
- **Brief false STOP readings (Task 1 development, added 22 October 2026).** In the 10-trial Task 1 development
  session (`bridge_guide_20261021_215746`, section 9 item 13) MediaPipe read STOP (Open_Palm) on 3 single pan-tilt
  frames while every worker showed FORWARD with a fist: frames 321 (trial 1, approach, score 0.573), 996 (trial 2,
  navigating, 0.579) and 4767 (trial 7, approach, 0.616). The two during approach stopped the robot for one or two
  0.1 s log rows; all 10 trials still succeeded. Likely source: the open hanging hand (**unverified**: those frames
  were not among the sampled JPEGs, and in the FORWARD hand sweep's saved frames the hanging hand looks curled). No
  STOP setting was changed.
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
`trials.json` (task, mode, mode note), `hri_frozen.json` and the new evaluation-only `hri_trials_metrics.json`. hri_control.json, hri_perception.json, gesture_hri.json,
roadmap.json, bridge.json, robot.json and the two Unity configs are byte-identical to the Task 2 final.

**Task 1 development runs only check that the pipeline works** (bridge, perception, trial runner and logging on the
Task 1 route, dev seed 1). They must not be used to adjust any setting. If one shows a problem that needs a change,
the change is disclosed here and the frozen hashes are re-recorded before the Task 1 final.

Notes:
- Machine for the Task 1 final: to be recorded.
  - If it differs from the Task 2 machine:
    - comparable between the tasks: success, gesture accuracy, distance travelled, `time_excl_stale_stops_s` and
      `in_motion_s` (defined below);
    - not comparable: inference times, stale-perception stops, and total trial time (it includes those stops).
  - Development runs on Nusrat's PC are pipeline checks only.
- **Time measures reported separately** (added 21 October 2026, before any Task 1 trial; reporting only, no
  perception, gesture or state-machine setting changed). `hri_trials.py` writes per run `total_s`,
  `stale_stop_s`, `time_excl_stale_stops_s` and `in_motion_s`, and `hri_analysis.py` reports each separately.
  Each 0.1 s log row counts until the next row of the trial.
  - `stale_stop_s`: time Python held the robot because perception was stale (decisions.csv `safety` =
    "perception stale").
  - `time_excl_stale_stops_s` = `total_s` - `stale_stop_s`. It still includes scanning, asking and reading at
    junctions.
  - `in_motion_s`: time when the robot's speed `|v_mps|` in Unity's 0.1 s truth log (`truth_run###.csv`) is above
    `in_motion_speed_threshold_mps` = 0.05 m/s (5 % of the 1.0 m/s maximum).
  - **The threshold was set on 21 October 2026, before any Task 1 trial**, in `configs/hri_trials_metrics.json`.
    That file is evaluation-only and its hash is in `hri_frozen.json` (`sha256_added_2026_10_21`).
  - Older logs without a `safety` or `v_mps` column give None, not a guess.
  - The Task 2 figures in section 2 give total time and stale-perception stops. Both new measures can be
    recomputed from the Task 2 session folders with the new `hri_trials.py`; its logs have both columns.
- The Unity EditMode tests are run locally; CI runs only the Python tests.
- Checks on 21 October 2026 (Windows): Python 224 tests pass, including 11 in `test_hri_frozen.py` and the two time-measure tests in
  `test_trials.py`; Unity EditMode 15/15 pass (10 earlier + 5 `FinalRunGuardTests`).

## 9. Task 1 blockers fixed (21 October 2026, before any Task 1 final run)

Every fix is labelled **environment fix**, **infrastructure fix** or **declared design change**. **No shared frozen
setting changed:** hri_control.json, hri_perception.json, gesture_hri.json, roadmap.json, bridge.json, robot.json and
the two Unity configs are byte-identical to the Task 2 final (`test_hri_frozen.py` pins the shared hashes to the
ce37a56 values and still passes). The pose code (`GestureWorker.cs`, `GestureCommand.cs`, `GesturePoseCycler.cs`) is
unchanged since ce37a56. The Task 2 final result (section 2) is unaffected; no Task 2 final is rerun.

1. **Worker rendered magenta on Nusrat's PC: environment fix.**
   - Cause (found in the files, not guessed): the committed scene overrides the worker renderer's material with
     `worker_textures/Worker_URP.mat`, GUID `fececb7a5daa044cfabce1101932b943`, created by Add Worker and Roadmap on
     Anisha's Mac. That folder is git-ignored, so on any other machine the reference is missing and Unity draws the
     renderer magenta. Shaders, the FBX import and the avatar were not the cause. `Check Worker` on the PC before the
     fix: `Ch32 material 0: missing` (`outputs/worker_check_20261021_033452`).
   - Fix: `Tools > Warehouse HRI > Restore Worker Appearance` (also run by Add Worker and Roadmap) extracts the FBX's
     embedded textures into the git-ignored folder and creates the URP Lit material (opaque, smoothness 0.25, base map
     `Ch32_1001_Diffuse`, the settings of the earlier code) **with that fixed GUID**, so the committed scene resolves
     on every machine without being changed. No Mixamo texture, model or material is committed.
   - After the fix (PC): `Ch32: Worker_URP [Universal Render Pipeline/Lit] Ch32_1001_Diffuse 4096x4096`, no problems
     (`outputs/worker_check_20261021_202822`); the gesture PNGs show the textured orange worker.
   - New check (infrastructure): `WorkerAppearance.Problems` refuses **every** trial session (development, final, any
     task or seed; a Task 2 replication runs through the same runner) when a worker renderer has a missing material,
     Unity's error shader, a shader with no pass for the active render pipeline, no base texture, or the worker is
     not Humanoid. The message names the renderer and the fix. 7 EditMode tests.
   - session.json now records `worker_model_sha256`, `worker_avatar_bone_map_sha256` and `worker_appearance`, so
     sessions from different machines can be compared.
2. **Gesture poses on the PC: checked, nothing changed.**
   - Pose code identical to ce37a56. No pose bug was found, so the poses were not touched.
   - Import settings equal the committed `worker.fbx.meta` (Humanoid, avatar created from this model, no stored bone
     mapping: Unity generates it at import); the generated avatar is valid and Humanoid with 52 bones. On the PC
     (Unity 2022.3.62f3): worker.fbx sha256 `d883783c...2c51`, avatar mapping sha256 `d9b9596d...f310`, scene bone
     map sha256 `1bee2c43...b5a2`. **To be compared with Anisha's Mac** (run Check Worker there): the mapping is
     generated from the FBX file, so equal hashes mean the same rig and the same poses.
   - PNGs from the pan-tilt camera at 2.0 m, worker at J1's stand (`Save Gesture PNGs`):
     `outputs/gesture_pngs_20261021_202856/` LEFT, FORWARD, RIGHT, STOP and capture.json (git-ignored).
3. **Task 1 checkpoints: declared design change** (Task 1 only, before any Task 1 final run).
   - Task 1 stays the straight run A to B (E1). The straight line A -> J1 -> E1 now has checkpoints from the new
     per-task config `robot_vision/configs/task1_route.json` (default 3): the line is cut into checkpoints + 1 equal
     parts, the cut points are stops, one that falls on a junction is that junction. Default stops: C1 (6.25, -5),
     J1 (6.25, 0), C3 (6.25, 5). At every stop the robot asks as at a junction and the worker shows FORWARD. 0 or 1
     checkpoint gives the previous Task 1 (one stop, J1).
   - The **one worker** (the same avatar as in Task 2) is moved to each stop as the robot heads there, exactly as in
     Task 2, and stands by the roadmap rule (2.5 m ahead and right, facing the robot). Workers standing at all stops
     at once were rejected: with 5 m spacing the worker just passed is as close to the next stop as the next worker
     (both 3.54 m), so the frozen nearest-person rule could pick the wrong one.
   - Python: `task_route.py` builds the Task 1 map from roadmap.json (unchanged) and task1_route.json; the line is
     found from the map (FORWARD branches), never from B. `bridge.server --task Task1` selects it (default Task2 =
     roadmap.json); the run folder's `config_used/map_used.json` records it. Unity: `Task1Route` (same rule, pinned
     to the same stops in both test suites) adds the checkpoints for the Play session only; the scene is not changed.
     The trial runner refuses trials if Python's map (`route`, sent with every command) is not its task's map,
     refuses a worker stand inside a collider, and refuses a Task 1 final if task1_route.json differs from its hash.
   - hri_frozen.json: `tasks.Task1.route` (checkpoints 3, stops C1, J1, C3, map `Task1:C1,J1,C3`) and
     `tasks.Task1.route_config` (task1_route.json sha256 `ceb59d70...4a5b`). The shared hashes are unchanged.
   - Simulator (`hri_sim.py`, frozen controller): Task 1 SUCCESS, FORWARD read at C1, J1 and C3 at the first ask (test).
4. **Watchdog stops and round-trip spikes on the PC: infrastructure fix.**
   - Before: `bridge_guide_20261021_024850` (10 Task 1 development trials, old route): 9 watchdog stops in the
     session, 8 during trials (trial 1: 5, trial 3: 2, trial 8: 1), maximum round trip 330.6 ms. (The figures 622.6 ms
     and 7 stops quoted in the task are not in this folder's logs.) At each stop Python's receive loop paused
     0.33-0.59 s while Unity's frame times stayed normal: Python stalled, not Unity.
   - The 5 stops in the first 21 s of trial 1 (with the 157-331 ms round trips) coincide with first-call work in
     perception: first pan-tilt frame 2.8 s, first panorama 9.2 s (8.9 s in YOLO), then 0.8 s and 1.3 s when the
     tracker first saw a person. Cause in the code: the old warm-up called `predict()`, but Ultralytics rebuilds the
     predictor when the `tracker` argument appears, so the live `track()` call set everything up again in trial 1;
     the pan-tilt warm-up frame was 512 rows high instead of 530; no warm-up frame showed a person, so the tracker and
     the MediaPipe crop path never ran. Part of that work holds the GIL, which stalls the server.
   - The other 4 stops (one between trials 2 and 3, two in trial 3, one in trial 8) were **not** warm-up: no slow
     perception frame around them; 2 of 4 directly follow a sampled JPEG write. Cause not identified; not changed.
   - Fix: `HriPerception._warm_up` runs the live calls (`people()` with track/persist, `gesture()` with the MediaPipe
     crop) three times on frames of the live sizes (2048 x 1024, 730 x 530) that show people (Ultralytics' bundled
     sample photos), then resets the tracker; the bridge listens only after it. Python sends `perception_ready`
     (true once one live frame of each camera has been processed) with every command, and the trial runner starts
     trial 1 only after it (`docs/protocol.md`: optional fields `route`, `perception_ready`; protocol stays v2).
   - Offline check on 80 + 80 saved PC frames (Unity closed): first frames 43 ms / 47 ms with no main-thread stall
     above 6 ms, against 12.6 s / 1.3 s and a 226 ms stall without warm-up. Perception outputs (track ids, bearings,
     distances, gestures) are identical with and without the warm-up on all 160 frames.
   - After (live, PC, one Task 1 development pipeline-check trial on the new route, `trials_development_Task1_20261021_203226`
     and `bridge_guide_20261021_203057`, 1/1 SUCCESS at C1, J1, C3; run on the working tree just before this commit, so its session.json names the parent
     commit 4aeeed2; nothing adjusted on it): the slow first frames
     (up to 0.53 s) and one watchdog stop fell before trial 1, which waited for perception_ready. During the trial:
     1 watchdog stop at 28 s while navigating (same kind as the 4 unexplained ones above; it too directly follows a
     sampled JPEG write, so 3 of these 5 stops do), maximum round trip 194.9 ms at 12.1 s (all 1547 answered
     telemetry messages, summary.json; mean 1.6 ms, p95 1.5 ms; the 0.1 s decisions.csv sample shows 31.4 ms). The
     before figure 330.6 ms is over all messages too. One trial is a small sample; the full development session will
     tell.
5. **Sample-image saving moved off the event loop: infrastructure fix** (no frozen setting changed: bridge.json,
   save_every_n_frames and the saved files are the same).
   - Why: 3 of the 5 unexplained watchdog stops above directly followed a sampled JPEG write, which ran
     synchronously on the asyncio loop that answers telemetry.
   - Fix: `bridge/server.py` `FrameWriter`, a background thread with a bounded queue (32 files). The same files are
     saved; if the queue is full the save is skipped and counted (`summary.json -> frames_saved`:
     saved, skipped_queue_full, write_errors). Write errors are counted instead of breaking the connection.
   - Test (`test_bridge.py`): with a simulated 0.5 s write, a frame followed by telemetry is answered within 0.2 s
     and five replies within 0.4 s. The same test run against the old in-loop write fails (first reply 0.508 s).
     Two more tests: queue full -> skipped and counted; a write error is counted, not raised.
   - Rerun of the 1-trial Task 1 development pipeline check (`trials_development_Task1_20261021_205126`,
     `bridge_guide_20261021_204609`; 1/1 SUCCESS at C1, J1, C3, 0.035 m from B; nothing adjusted on it), against
     the check before this fix (`bridge_guide_20261021_203057`), all telemetry messages:

     | | before | after |
     |---|---|---|
     | watchdog stops during the trial | 1 | 2 |
     | watchdog stops before trial 1 (start-up, trial waited) | 1 | 1 |
     | max round trip during the trial | 194.9 ms | 39.0 ms |
     | mean round trip (session) | 1.6 ms | 1.2 ms |
     | sampled JPEGs saved / skipped | (not counted) | 55 / 0 |

   - **The stops were not removed.** Neither stop in the rerun followed a JPEG write. One (Python silent 0.31 s, at
     15.9 s) has no write and no slow perception frame near it; the other (1.03 s, at 54.8 s) coincides with one
     YOLO gesture call that took 1.04 s (normally about 25 ms; warm-up already done, so not first-call work). The
     JPEG write was therefore at most one contributor; the remaining stalls come from Python holding the event
     loop or the GIL for 0.3-1 s at irregular times (sporadic slow model calls, cause not identified). One trial
     per side is too few to tell 1 from 2 stops apart. Not changed further; the full development session will show
     the rate.
6. **Checks on 21 October 2026 (Windows):** Python 248 tests pass (after item 5; 245 before it) (21 new: task route, warm-up, perception ready,
   route in every command, per-task frozen record); Unity EditMode 26/26 pass (15 earlier + 4 `Task1RouteTests` +
   7 `WorkerAppearanceTests`).
7. **Acceptance criteria for the 10-trial Task 1 development session** (written 21 October 2026 before any test of the
   changes in items 8 onward; set by Nusrat; not loosened afterwards). Over one 10-trial Task 1 development session on
   Nusrat's PC:
   - every trial visits every Task 1 checkpoint and performs the full interaction at each: slow down, scan, approach
     to 2.0 m, ask, read FORWARD held 1.0 s, execute;
   - every worker renders textured (no error shader), with the arm pose visible in the pan-tilt image;
   - 0 watchdog stops after start-up; maximum round trip (all messages) under 100 ms;
   - every trial outcome recorded.
   If a criterion is not met, the result is reported as not met and work stops there.
   Measurement definitions (`hri_session_check.py`, written with the criteria and before any test of the changes;
   they say how each criterion is measured, they do not relax it):
   - slow down: every speed command in the last 1.0 s of navigation before a stop's scan is at most the frozen
     junction speed (0.35 m/s);
   - approach to 2.0 m: the approach state ran and, at the start of the ask, the true distance robot centre -> that
     stop's worker centre (Unity truth) is 2.0 +- 0.3 m (frozen approach tolerance 0.15 m + 0.15 m for the vision
     distance estimate);
   - FORWARD held 1.0 s: Python accepted FORWARD at that stop (its dialog accepts only after the frozen 1.0 s hold),
     the worker showed FORWARD, and at least 1.0 s passed from the ask to the execute step;
   - textured, arm pose visible: the trial runner's appearance check passed for every Task 1 worker (it refuses the
     session otherwise; session.json lists each worker's material and texture) and FORWARD was read from the arm at
     every stop;
   - watchdog stops after start-up: increase of Unity's watchdog counter from the first telemetry of trial 1 to the
     end of the session;
   - round trip (all messages): every reply Unity measured (new telemetry fields rtt_window_*; before, Unity reported
     only the latest reply of a frame, which hid stalls).
8. **Diagnosis of the reported Unity run (21:14-21:16; operator / environment, nothing wrong in the frozen system).**
   - `bridge_hello_20261021_211443`: the **hello** server ran (`run_info.json` mode hello, 1384 of 1395 commands
     v = 0.2 m/s). Unity session `trials_development_Task1_20261021_211450` connected to it. Hello mode never sends
     `perception_ready`, so trial 1 never started: no poses, no approach, no ask, robot creeping at 0.2 m/s. Only the
     scene's one worker was visible (by design then).
   - `bridge_guide_20261021_211625`: guide mode **without `--task Task1`** (map Task2). No connection was logged
     (0 messages, no summary); had Unity connected, the trial runner would have refused the map. `_211417`: no server.
   - Scene: not rebuilt after the first Task 1 change, which did not need it (checkpoints were added at Play). The
     multi-worker layout was **not** in place (one worker was moved); it is now (item 10).
   - Speed: guide mode cruises at the frozen `drive.cruise_speed_mps` 0.8 (hri_control.json, unchanged since
     ce37a56); logs: max commanded 0.80 m/s (`bridge_guide_20261021_204609`), max 0.80 m/s in Unity truth. The
     0.2 m/s was hello mode (`bridge.json hello_test.v_mps`). No speed was changed.
9. **Safe launch: infrastructure fix.** `robot_vision/run_trials.ps1 -Task Task1|Task2 [-UnityBatch]` and
   `run_trials.sh Task1|Task2 [--unity-batch]` always start `bridge.server --mode guide --perception vision --task
   <task>` from the project venv and refuse a task other than the one in trials.json (or trials.local.json). Batch
   mode also runs TrialBatchPlay, stops the server when Unity quits (`--exit-on-disconnect`) and runs
   hri_trials.py, hri_analysis.py and hri_session_check.py. The server now needs `--mode`; guide mode needs
   `--task`; hello mode is refused without `--allow-hello`. Tests: `test_bridge_diagnostics.py`,
   `test_launch_and_session_check.py`.
10. **Task 1 workers: declared design change** (Task 1 only, before any Task 1 final; owner's request).
    - One standing worker per stop (same Mixamo avatar, same material), `task1_route.json` `worker_ahead_m` 1.0,
      `worker_right_m` 2.5: C1 (8.75, -4), J1 (8.75, 1), C3 (8.75, 6), facing the arriving robot, showing FORWARD
      the whole trial. Before: one worker moved to each stop by the roadmap rule (2.5 m ahead and right).
    - Why not the roadmap rule: with 5 m between stops the worker just passed would be as far from the next stop as
      that stop's worker (3.54 m both) and the frozen scan takes the nearest person. Now 2.69 m (own) vs 4.72 m
      (previous); every worker at least 1.9 m from the robot's path after the read (corridor 0.6 m).
    - Built by Tools > Warehouse HRI > Add Worker and Roadmap (rebuilt in batch mode: scene +545 lines, 0 removed,
      no overlap warnings, NavMesh validation passed) into `WarehouseHRI/Task1Workers`, saved **inactive**: Task 2
      and the gesture tools never see it. The trial runner activates it only in Task 1, hides the moved worker,
      refuses Task 1 if the scene's workers differ from task1_route.json, and applies the appearance check to every
      worker. Closest distance and the truth log use all workers.
    - Same rule in `task_route.task1_worker_stands` and `Task1Route.WorkerStands`, pinned to the same list in both
      test suites. Simulator (`hri_sim.py`, standing workers): SUCCESS, FORWARD read at C1, J1, C3, each time
      approaching that stop's own worker, also with noisy perception (test).
    - hri_frozen.json: `tasks.Task1.route.workers`, `route_config.sha256` 0d8cfa60...ec13 (was ceb59d70...4a5b).
      Shared hashes unchanged.
11. **Worker appearance and poses: checked, no pose change.** The magenta fix (item 1) and the error-shader /
    missing-texture check are in place and now cover every Task 1 worker. Pose code is identical to ce37a56
    (`git diff ce37a56 -- GestureWorker.cs GestureCommand.cs GesturePoseCycler.cs Characters/` is empty); no pose
    bug. PNGs from the pan-tilt camera at 2.0 m: `outputs/gesture_pngs_20261021_215233/` (LEFT, FORWARD, RIGHT,
    STOP; git-ignored).
12. **Watchdog stops: measured, two infrastructure fixes.**
    - Measured with `bridge.replay_client` (saved frames sent at live rates, no Unity) and new server diagnostics
      (event-loop lag monitor with faulthandler stack dumps, GC pause timer, thread counts; Unity telemetry now
      reports every round trip, its frame times and real-time clock).
    - Earlier logs re-read: in the 1.0 s stall of `bridge_guide_20261021_204609` Unity kept sending (clock offset
      constant) and Python read 20 telemetry messages at once, so Python stalled. Unity's reported maximum round trip
      (39 ms) had missed it: Unity reported only the latest reply per frame (fixed: `rtt_window_*`).
    - Cause found: **full garbage collections**. With the models loaded about 410 000 objects are tracked; a full
      collection took 230-320 ms, holds the GIL and stops every thread. In the 180 s replay the only loop stall
      (224 ms) was a 232 ms generation-2 collection on the perception thread.
    - Thread counts: torch intra-op 1, inter-op 8, OpenCV 1, 75-76 process threads on 16 logical CPUs. No evidence
      of CPU starvation, so **no thread caps**.
    - Fix 1: `gc.freeze()` after warm-up (`diagnostics.freeze_heap`): full collection 280 ms -> 0.01 ms. No
      computation changes.
    - Fix 2: perception on two threads (360 people, gesture), latest frame only, drops counted. The asyncio loop
      never runs inference; old results trigger the existing frozen stale-perception stop. Outputs are identical:
      350/350 perception rows equal (old one-thread worker vs new) on 350 saved frames.
    - Replay, 180 s, before -> after: max round trip 194.7 -> 31.0 ms; event-loop lag max 224 -> 22 ms (over 50 ms:
      1 -> 0); frames dropped 13 -> 0.
    - Tests: a 1.5 s perception call does not delay replies (worst reply < 0.1 s) and does not hold the gesture
      thread; newest frame first with counted drops; stale stop exactly above the frozen 1.0 s; heap freeze; loop
      lag monitor.
13. **Verification: 10-trial Task 1 development session, NOT ACCEPTED** (`run_trials.ps1 -Task Task1 -UnityBatch`,
    commit c96f9b2, dev seed 1; `trials_development_Task1_20261021_215821`, `bridge_guide_20261021_215746`,
    `hri_trials_20261021_221120`, `hri_analysis_20261021_221121`, `session_check_20261021_221131`).
    Nothing was adjusted on it.

    | trial | outcome | stops visited | full interaction | asks C1/J1/C3 | shown > read | stale stops | watchdog | rtt max ms |
    |---|---|---|---|---|---|---|---|---|
    | 1 | SUCCESS 0.043 m | 3/3 | yes | 1/2/1 | FORWARD > FORWARD x3 | 0 | 1 | 119.2 |
    | 2 | SUCCESS 0.061 m | 3/3 | yes | 1/2/1 | FORWARD > FORWARD x3 | 0 | 0 | 147.8 |
    | 3 | SUCCESS 0.064 m | 3/3 | yes | 1/1/1 | FORWARD > FORWARD x3 | 0 | 0 | 222.9 |
    | 4 | SUCCESS 0.033 m | 3/3 | yes | 1/1/1 | FORWARD > FORWARD x3 | 0 | 1 | 16.3 |
    | 5 | SUCCESS 0.052 m | 3/3 | yes | 1/2/1 | FORWARD > FORWARD x3 | 0 | 0 | 121.4 |
    | 6 | SUCCESS 0.037 m | 3/3 | yes | 1/2/1 | FORWARD > FORWARD x3 | 0 | 0 | 173.7 |
    | 7 | SUCCESS 0.074 m | 3/3 | yes | 2/2/1 | FORWARD > FORWARD x3 | 0 | 0 | 150.4 |
    | 8 | SUCCESS 0.054 m | 3/3 | yes | 2/1/1 | FORWARD > FORWARD x3 | 0 | 1 | 99.0 |
    | 9 | SUCCESS 0.050 m | 3/3 | yes | 1/1/1 | FORWARD > FORWARD x3 | 0 | 1 | 257.1 |
    | 10 | SUCCESS 0.048 m | 3/3 | yes | 1/1/1 | FORWARD > FORWARD x3 | 0 | 0 | 74.4 |

    - Session: 10/10 SUCCESS; 30/30 stops read FORWARD as shown (coverage 30/30; 7 needed the second ask: 5 at J1,
      2 at C1); 0 collisions; closest approach 1.30 m; robot-worker distance at the ask 1.90-1.96 m; ask to execute
      at least 1.43 s. Round trip, all messages: 14 497 replies to 14 499 telemetry, mean 2.04 ms, **max 257.1 ms**.
      Watchdog stops: 6 in total, 2 at start-up, **4 after start-up**. Dropped frames: Unity 40 (360) / 339
      (pan-tilt); Python 0 (360) / 853 (gesture, newest-frame-only drops). Stale-perception stops: 0.
    - Criteria: (1) full interaction at every checkpoint: **met**. (2) textured workers, arm pose read: **met**.
      (3) 0 watchdog stops after start-up: **not met (4)**; max round trip under 100 ms: **not met (257.1 ms)**.
      (4) every outcome recorded: **met**.
    - Where the remaining stops come from (from this session's diagnostics):
      - 3 of the 4 in-trial stops (trials 1, 4, 8) are **Unity main-thread hitches** of 239-322 ms. Python read
        every message within 16 ms, but Unity sent no telemetry during the long frame, so no command came back.
        11 Unity frames over 250 ms in the session.
      - 1 stop (trial 9) is a **Python stall** of 256 ms. The stack dump shows both perception threads idle and no
        garbage collection (all collections over 10 ms happened at start-up, before the freeze).
      - 51 event-loop lags over 50 ms (max 256 ms) with Unity running, against 0 over 50 ms in the replay without
        Unity. This points to contention between the two processes on one machine (CPU, GPU or memory), not to
        Python code. Cause not identified; process memory, paging and GPU load were not logged.
    - Stopped here as instructed: no criterion loosened, nothing further changed.
14. **No shared frozen setting changed** in items 8-13: hri_control.json, hri_perception.json, gesture_hri.json,
    roadmap.json, bridge.json, robot.json, robot_unity.json, bridge_unity.json, the pose weights and model
    precision are unchanged (`test_hri_frozen.py` passes with the ce37a56 hashes). Changed: Task 1's own
    task1_route.json (declared, item 10), infrastructure (items 9 and 12) and measurement code. **A Task 2
    replication will run with this server** (two perception threads, frozen heap, diagnostics, launcher, extra
    telemetry fields). That is a declared infrastructure difference from the original Task 2 final (ce37a56), whose
    result stands as recorded.
15. **Declared before running: FORWARD pose decision rule** (22 October 2026, 01:48 BST; written before any
    FORWARD finger-versus-fist sweep was run and before any of its frames were classified). Owner's rule:

    > "FORWARD pose decision rule: adopt the index-finger pose (arm angle unchanged) for both tasks if, in the FORWARD
    > gesture sweep (20 repeats each, distance and angle jitter), the finger is read as FORWARD at least as often as
    > the fist and is never read as STOP. Otherwise keep the fist."

    How it is measured (fixed with the rule, not after the results):
    - Sweep: the development gesture sweep (dev seed 1, robot still, worker at J1's stand, frozen perception) showing
      only FORWARD, 20 repeats with the fist and 20 with the index finger. Each repeat draws one distance (1.7-2.5 m),
      view angle (+-25 deg) and worker yaw jitter (+-15 deg) from `trials.json -> gesture_sweep`, and both hands are
      shown at that same placement (paired; the hand order within a pair is seeded). Settle 0.6 s, hold 2.0 s.
    - "Read as FORWARD": FORWARD frames / all pan-tilt frames inside the 20 sample windows of that hand (frozen
      classifier, `hri_eval_dev.py`). The finger passes this part if its rate is >= the fist's rate.
    - "Never read as STOP": 0 pan-tilt frames read STOP in all 20 finger samples (a single STOP frame fails).
    - Reported as well, not part of the rule: frames read NONE, the 1.0 s hold result per sample (strict), coverage.
    - Only the FORWARD hand changes; the arm angle and every other command are unchanged. No threshold changes.
16. **FORWARD hand sweep: result, rule not met, the fist is kept** (22 October 2026; development, dev seed 1; nothing
    adjusted on it). `forward_hand_sweep_development_20261022_015457` (Unity) + `bridge_guide_20261022_015430`
    (Python, guide mode, vision, frozen perception) -> `hri_dev_eval_20261022_015719` (`hri_eval_dev.py
    --forward-hands`). 20 placements, each showing FORWARD with both hands (40 samples, 731 pan-tilt frames).

    | hand | samples | frames | read FORWARD | read NONE | read STOP | FORWARD rate (= coverage) | 1.0 s hold (strict) |
    |---|---|---|---|---|---|---|---|
    | fist | 20 | 363 | 310 | 53 | 0 | 0.854 | 17 correct, 3 none |
    | index finger | 20 | 368 | 312 | 56 | 0 | 0.848 | 17 correct, 3 none |

    - Rule (item 15): finger FORWARD rate >= fist: **no** (0.848 < 0.854); finger never read STOP: yes (0 of 368
      frames). Decision: **keep the fist**. The difference is small (about 2 frames in 365), but the rule was
      declared beforehand and is applied as written. No other command read in either hand (accuracy 1.0 on the
      frames with a command).
    - The poses rendered as intended: saved pan-tilt frames `frames/frame_pan_tilt_000020.jpg` (index finger up) and
      `frame_pan_tilt_000060.jpg` (fist) of the bridge folder.
    - Code added for the sweep (development only, defaults unchanged): `GestureWorker.forwardHand` (Fist /
      IndexFinger; default Fist, so every trial still shows the fist), trial runner task `ForwardHandSweep` (refused
      in final mode, run through a git-ignored `trials.local.json`, removed afterwards), seeded pair order
      `ForwardHandSweepOrder`, `hri_eval_dev.py --forward-hands`. The gesture sweep keeps its placements (same random
      draws in the same order).
    - Not adopted, so the item "implement the finger pose for both tasks" was not carried out; Task 1 and the Task 2
      replication keep the fist pose of the Task 2 final.
    - Checks: Python 271 tests pass (1 new: the rule on synthetic frames); Unity EditMode 30/30 pass (3 new
      `ForwardHandSweepTests`).
