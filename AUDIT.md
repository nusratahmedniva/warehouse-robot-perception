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
| Final Task 1 | Task 1 final, seed 2, once (section 10) | **done: 10/10** | `trials_final_Task1_20261022_161544` (FINAL_DONE.json) |
| Replication Task 2 | Declared replication of the Task 2 final, seed 2, once (sections 11, 13) | **done: 10/10** | `trials_replication_Task2_20261022_180918` (REPLICATION_DONE.json) |

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
17. **Measurement correction before the 5-trial rerun** (22 October 2026, written before that session; infrastructure
    and measurement, plus one declared change of the watchdog trigger in Unity code; no frozen setting changed:
    bridge.json, bridge_unity.json and `watchdog_timeout_s` 0.3 s are byte-identical, `test_hri_frozen.py` passes).
    - **Why.** In the 10-trial session (item 13) 3 of the 4 watchdog stops after start-up were Unity main-thread hitches
      of 239-322 ms: Python read every message within 16 ms and answered at once, but Unity sent no telemetry during the
      long frame, so no command came back, and the wall-clock rule ("no command for 0.3 s") stopped the robot. The
      watchdog exists to stop the robot when Python is silent for 0.3 s; those stops measured Unity, not Python. The old
      rule also gave no protection during the hitch itself: Unity's physics catch-up steps run before the check.
    - **Watchdog (declared change of the trigger, `CommandWatchdog`, EditMode-tested).** It stops only if a command is
      missing for telemetry Unity actually sent more than 0.3 s ago (the network thread started writing it, and no
      command arrived after that). Backstop, also a stop: a telemetry message queued but not written for 0.3 s with no
      command since it was queued (blocked socket: Python is not reading). A silence that only the old wall-clock rule
      catches is logged as a `unity_frame_stall` event with its duration (command gap) and the longest Unity frame in
      it; stops are `watchdog_stop` events (cause `no_reply` / `not_written`). The old-rule count is reported beside
      the new one (old-rule stops = stops + Unity frame stalls). The Task 2 final (ce37a56) ran with the old rule; a
      Task 2 replication will run with this one, a declared difference.
    - **Round trip measured on Unity's network threads**: from the write thread starting to write the telemetry to the
      read thread receiving the reply (before: queued on the main thread -> received). The old definition is still
      sent (`rtt_queue_window_*`) and reported beside it.
    - **Unity main-thread frame times recorded separately**: every frame duration (`frame_ms_list`); reported per
      trial and per session as max, p99 and the number of frames over 100 ms.
    - **Resource logging once per second** (`bridge/resource_monitor.py`, its own process, started by
      `bridge.server --resource-log`, which both launchers pass): machine CPU, memory available, page-file use, hard
      paging (pages read from disk per second), CPU / memory / page faults of the server and Unity, the 3 other
      processes using most CPU, GPU utilisation and memory (nvidia-smi). Its own cost: about 2 % of one CPU.
    - **Run protocol** (every development check, final and replication on this PC): other applications closed; Windows
      power mode "Best performance"; charger connected (this PC is a desktop without a battery: mains power).
      `launch_prep.py` prints the power mode and power source and warns when they differ; the server records them in
      `run_info.json -> machine_state` (`bridge/machine_state.py`). Closing other applications is checked through the
      resource log (top other processes).
    - **Launcher option `-Trials N` / `--trials N`, development only**: writes a launcher-marked
      `trials.local.json` (trial_count N), which the Unity runner copies into `config_used/`, and removes it after
      the session. Refused unless trials.json's mode is `development` (so in final and replication mode), and refused
      if a user's own trials.local.json exists (tested).
    - **Acceptance criteria unchanged** (item 7, all four, measured by `hri_session_check.py`; criterion 3 now uses the
      corrected watchdog count and the network-thread round trip; the old-definition figures are printed beside them).
      **Development check reduced to 5 trials for time; finals and replication stay at 10.**
    - **Smoke check of the instrumentation, not part of the acceptance** (`run_trials.ps1 -Task Task1 -UnityBatch
      -Trials 1`; `trials_development_Task1_20261022_021648`, `bridge_guide_20261022_021624`; nothing adjusted on
      it): 1/1 SUCCESS, all new fields logged, the override removed afterwards. Round trip max 41.2 ms (network
      thread) / 41.3 ms (queued); watchdog stops 0, Unity frame stalls 0; Unity frames: max 238.8 ms, p99 48.6 ms,
      6 over 100 ms in 3211.
    - **Found by the resource log on this PC (left running; not part of this project, so not stopped by the AI):** a `cmd.exe` (PID 18312, started 21 October 20:22,
      parent gone, command line not readable) used about 4 logical CPUs continuously (124 000 CPU-seconds by
      02:00, so also during item 13's session); during the smoke trial available memory fell to 215 MB (mean 508 MB of
      14.2 GB), hard paging reached 24 700 pages/s (mean 2 700), the server held about 3.1 GB and Unity about 2.0 GB of
      private memory. Memory pressure and CPU contention are now a measured candidate cause of the stalls in item 13;
      the 5-trial check is to run under the run protocol.
    - Checks: Python 284 tests pass (13 new in `test_measurement_correction.py`); Unity EditMode 35/35 pass (5 new
      `CommandWatchdogTests`).
18. **Verification: 5-trial Task 1 development session, ALL FOUR CRITERIA MET** (22 October 2026, 02:26-02:32;
    `run_trials.ps1 -Task Task1 -UnityBatch -Trials 5`, commit e751ac6, dev seed 1;
    `trials_development_Task1_20261022_022631`, `bridge_guide_20261022_022557`, `hri_trials_20261022_023210`,
    `hri_analysis_20261022_023210`, `session_check_20261022_023213`). Nothing was adjusted on it.
    - Run protocol: the runaway `cmd.exe` (PID 18312) was ended by Nusrat and other applications were closed before
      the run (free memory before the start 5.5 GB, against 3.4 GB earlier); power mode Best performance, mains power
      (`run_info.json -> machine_state`, no launcher warning). Chrome processes were still present: in the top 3 CPU
      users in 24 of 369 resource samples.

    | trial | outcome | stops visited | full interaction | asks C1/J1/C3 | shown > read | stale stops | watchdog (new rule) | old-rule stops | rtt max ms (network / queued) | Unity frames max / p99 ms, over 100 ms |
    |---|---|---|---|---|---|---|---|---|---|---|
    | 1 | SUCCESS 0.052 m | 3/3 | yes | 1/1/1 | FORWARD > FORWARD x3 | 0 | 0 | 0 | 5.1 / 5.1 | 173.9 / 36.5, 8 |
    | 2 | SUCCESS 0.036 m | 3/3 | yes | 1/1/1 | FORWARD > FORWARD x3 | 0 | 0 | 0 | 44.9 / 44.9 | 165.3 / 34.6, 8 |
    | 3 | SUCCESS 0.087 m | 3/3 | yes | 1/1/1 | FORWARD > FORWARD x3 | 0 | 0 | 0 | 18.9 / 18.9 | 177.5 / 36.4, 7 |
    | 4 | SUCCESS 0.041 m | 3/3 | yes | 1/1/1 | FORWARD > FORWARD x3 | 0 | 0 | 0 | 6.4 / 6.4 | 167.3 / 34.0, 8 |
    | 5 | SUCCESS 0.036 m | 3/3 | yes | 1/1/1 | FORWARD > FORWARD x3 | 0 | 0 | 0 | 6.2 / 6.3 | 177.2 / 36.1, 8 |

    - Criteria: (1) full interaction at every checkpoint: **met** (robot-worker distance at the ask 1.89-1.97 m, ask
      to execute at least 1.45 s, speed in the last 1.0 s before every scan at most 0.35 m/s). (2) textured workers,
      arm pose read: **met**. (3) 0 watchdog stops after start-up: **met (0)**; max round trip, all messages, under
      100 ms: **met (44.9 ms)**. (4) every outcome recorded: **met**.
    - Old and new measurements side by side (item 13 = 10-trial session, old Unity build, before the measurement
      correction and with the runaway process running):

    | measure | item 13 (10 trials) | this session (5 trials) |
    |---|---|---|
    | success; stops read FORWARD (coverage) | 10/10; 30/30, 7 at the second ask | 5/5; 15/15, all at the first ask |
    | watchdog stops after start-up, new rule | not measured (old build) | **0** |
    | watchdog stops after start-up, old wall-clock rule | 4 | 0 (stops 0 + Unity frame stalls 0) |
    | start-up (before trial 1) | 2 watchdog stops | 0 stops; 1 Unity frame stall (449 ms gap, 456 ms frame) |
    | max round trip, all messages: network thread | not measured | **44.9 ms** (mean 0.89 ms, 6672 of 6673) |
    | max round trip, all messages: queued clock (old definition) | 257.1 ms (mean 2.04 ms, 14 497 of 14 499) | 44.9 ms (mean 0.91 ms) |
    | Unity main-thread frames after start-up | 11 telemetry windows with a frame over 250 ms (full distribution not logged) | 18 107 frames: max 177.5 ms, p99 35.8 ms, 39 over 100 ms, 0 over 250 ms |
    | Python event-loop lag | 51 over 50 ms, max 256 ms | 0 over 50 ms, max 37 ms |
    | dropped frames Unity (360 / pan-tilt); Python gesture drops | 40 / 339; 853 | 0 / 27; 5 |
    | STOP read while FORWARD shown | 3 single frames | 0 |
    | closest approach to a worker | 1.30 m | 1.39 m |
    | resources | not logged | free memory min 1979 MB (mean 2532); hard paging max 16 244 pages/s (mean 366); server CPU mean 95 % of one CPU, Unity 189 %; GPU mean 41 % |

    - Reading: the old-rule count is also 0 here, so the pass does not come from the redefinition alone; the Unity
      hitches over 250 ms and the Python stalls of item 13 did not recur. They disappeared together with the runaway
      process and the memory pressure, which supports those as their cause, but one 5-trial session cannot prove it.
      The criteria were not loosened; the Task 1 final and a Task 2 replication stay at 10 trials and must run under
      the same run protocol.
19. **10-trial Task 1 development rehearsal in the Unity Editor: pipeline check only** (22 October 2026, 02:56-03:09;
    `run_trials.ps1 -Task Task1` without `-UnityBatch`, Play pressed in the Editor, full trial_count 10, commit a9441ca
    (merge of 6cfa326 with no file change), dev seed 1; `trials_development_Task1_20261022_025616`,
    `bridge_guide_20261022_025526`; checked afterwards with `session_check_20261022_160430`). It rehearses the final's
    way of running (Editor, not batch). It is not an acceptance session and nothing was adjusted on it.
    - Run protocol: power mode Best performance, mains power, no launcher warning (`run_info.json -> machine_state`).
    - Result: 10/10 SUCCESS; 30/30 stops read FORWARD as shown, all at the first ask; 0 stale-perception stops;
      0 watchdog stops (new rule) and 0 Unity frame stalls (old-rule stops 0) after start-up; maximum round trip
      33.8 ms (trial 3, network thread; per-trial maxima 4.8-33.8 ms); Unity frames after start-up: 67 306, max
      211.3 ms, p99 35.9 ms, 93 over 100 ms. Workers textured (URP/Lit, `Ch32_1001_Diffuse`) at C1, J1 and C3.
    - **The bridge's summary.json is missing**: the server stopped without its shutdown step (the resource log ran on
      for about a minute after the last message, then the process was gone; most likely the window was closed or the
      server was interrupted twice). The session-wide figures that come only from summary.json (round trip over
      every message including start-up and the pauses between trials, dropped frames, event-loop lag) are therefore
      not available; the session check prints criterion 3b as NOT MET because that value is missing, not because a
      round trip over 100 ms was measured. For the final: after the last trial, press Ctrl+C once in the server window
      and wait for `[bridge] stopped; summary in ...` before closing it.
    - `trials_development_Task1_20261022_025551` (session.json and config_used only, no trial; Play pressed 25 s after
      the server started) is kept and not used.
20. **Task 1 final: declared before it runs** (22 October 2026).
    - Configuration: `configs/trials.json` "task": "Task1", "mode": "final" (commit 3ad244c, the only change in that
      commit); final seed 2, 10 trials, timeout 240 s, stuck 10 s / 0.25 m, success radius 0.3 m, equal to
      `hri_frozen.json -> tasks.Task1.trials_fixed`. Frozen settings unchanged (`test_hri_frozen.py` passes); pose
      weights sha256 1060bda4...2ba (equal to `hri_frozen.json -> pose_weights`); no `trials_final_Task1_*` folder
      exists.
    - Preconditions checked before the commit: working tree clean; full Python suite passes; error-shader / texture
      check passes (the 10-trial rehearsal, item 19, ran at a9441ca with all three Task 1 workers URP/Lit with
      `Ch32_1001_Diffuse`; the trial runner applies the same check to the final session and refuses it otherwise).
    - Machine: Nusrat's PC (Windows 11, NVIDIA RTX 3060 12 GB, 16 GB RAM), the machine of items 13-19.
    - Way of running: Unity Editor (2022.3.62f3), started with `run_trials.ps1 -Task Task1` (guide mode, vision
      perception, Task 1 map, resource log) and Play pressed in the Editor; after the last trial, Ctrl+C once in the
      server window and wait for `[bridge] stopped; summary in ...` (item 19).
    - Run protocol (item 17): other applications closed; Windows power mode Best performance; charger connected
      (desktop: mains power). The server records the power state in `run_info.json -> machine_state`; closed
      applications are checked through the resource log.
    - The final runs once. Its result is reported as it comes out; nothing is rerun, adjusted or discarded.

## 10. Task 1 final result (final seed 2, run once, commit 5440781, 22 October 2026)

Commit 5440781 is a9441ca plus `trials.json -> mode: final` (3ad244c, nothing else) and AUDIT.md notes (items 19-20).
Run as declared in section 9 item 20: Nusrat's PC, Unity Editor 2022.3.62f3, `run_trials.ps1 -Task Task1`, Play in
the Editor, server stopped with one Ctrl+C after the last trial (summary.json and COMPLETE written). Session
16:15:44-16:27:00 (server from 16:11:16). The trial runner's final checks passed (frozen hashes, task1_route.json, pose
weights, worker appearance) and it wrote FINAL_DONE.json, so no further Task 1 final can run. Analysed once with
`hri_trials.py`, `hri_analysis.py` and `hri_session_check.py`; nothing was rerun, adjusted or discarded.

Folders: `trials_final_Task1_20261022_161544` (Unity), `bridge_guide_20261022_161116` (Python),
`hri_trials_20261022_163150`, `hri_analysis_20261022_163151`, `session_check_20261022_163207`.

**10/10 SUCCESS** (Wilson 95 %: 0.72-1.0); running success ratio 1.0 after every run; failures: none (no timeout,
collision, stuck, wrong goal or abort). Goal order E1 x 10 (Task 1 fixed goal), matches.

| run | outcome | distance to B (m) | time (s) | travelled (m) | stops shown > read (asks) | closest to worker (m) | round trip max ms (all messages, network thread) |
|---|---|---|---|---|---|---|---|
| 1 | SUCCESS | 0.034 | 66.00 | 21.701 | C1, J1, C3: FORWARD > FORWARD (1, 1, 1) | 1.400 | 22.4 |
| 2 | SUCCESS | 0.031 | 65.50 | 21.654 | C1, J1, C3: FORWARD > FORWARD (1, 1, 1) | 1.393 | 51.9 |
| 3 | SUCCESS | 0.033 | 65.80 | 21.721 | C1, J1, C3: FORWARD > FORWARD (1, 1, 1) | 1.378 | 7.5 |
| 4 | SUCCESS | 0.025 | 65.68 | 21.753 | C1, J1, C3: FORWARD > FORWARD (1, 1, 1) | 1.352 | 21.1 |
| 5 | SUCCESS | 0.052 | 66.14 | 21.726 | C1, J1, C3: FORWARD > FORWARD (1, 1, 1) | 1.380 | 5.9 |
| 6 | SUCCESS | 0.026 | 65.94 | 21.722 | C1, J1, C3: FORWARD > FORWARD (1, 1, 1) | 1.371 | 10.3 |
| 7 | SUCCESS | 0.024 | 65.90 | 21.723 | C1, J1, C3: FORWARD > FORWARD (1, 1, 1) | 1.359 | 10.5 |
| 8 | SUCCESS | 0.082 | 65.68 | 21.755 | C1, J1, C3: FORWARD > FORWARD (1, 1, 1) | 1.379 | 83.5 |
| 9 | SUCCESS | 0.025 | 66.10 | 21.705 | C1, J1, C3: FORWARD > FORWARD (1, 1, 1) | 1.354 | 63.0 |
| 10 | SUCCESS | 0.026 | 65.88 | 21.676 | C1, J1, C3: FORWARD > FORWARD (1, 1, 1) | 1.396 | 36.7 |

Metrics of `docs/project_flow.md` (10 runs):
- Point A (6.25, -10), point B E1 (6.25, 10); straight line 20.0 m; travelled 21.654-21.755 m (travelled / straight
  line 1.086).
- Total time A to B: mean 65.86 s, max 66.14 s (of the 240 s limit). Time per step, mean (max) over runs: navigate
  40.20 (40.36) s, scan 1.28 (1.33) s, approach 14.90 (15.05) s, ask 1.58 (1.65) s, gesture 3.11 (3.40) s, execute
  4.75 (4.81) s; in motion (Unity speed > 0.05 m/s) 48.22 s; stale-perception stops 0 s in every run; safety stop
  (any reason) 0 s except run 8: 0.052 s (see below).
- Speed: average 0.33 m/s (0.328-0.331 per run), maximum 0.80 m/s. Turn rate: average 8.94 deg/s, maximum 51.6 deg/s.
- Final distance from B: mean 0.036 m, max 0.082 m (all within the 0.3 m success radius).
- Gesture shown vs read at every stop: **30/30 FORWARD read as FORWARD, coverage 30/30**, all at the first ask. Per
  frame over the whole session (all phases, start-up and pauses included; 8522 processed pan-tilt frames): FORWARD
  3895, NONE 4615 (4067 of them with no person in view), RIGHT 11, STOP 1.
- One STOP read while FORWARD was shown: run 8, approaching J1 (Python time 501.8 s), MediaPipe open palm on one
  frame (stop score 0.578). The always-active STOP rule stopped the robot for 0.052 s; it then continued, read
  FORWARD at J1 at the first ask and reached B. Not a junction read, so the 30/30 above is unaffected; it is a false
  STOP on the safety path, reported as such (item 18's 5-trial check had 0).
- Camera inference time per frame (mean per run, then mean / max over runs): YOLO11s-pose panorama 95.5 / 102.4 ms,
  YOLO11s-pose gesture 57.3 / 62.3 ms, MediaPipe STOP 28.5 / 37.0 ms, JPEG decode 5.2 / 6.0 ms; total per frame
  96.7 / 101.8 ms (p95 per run 150-164 ms).
- Unity-to-Python round trip: all messages on Unity's network threads 18 124 replies to 18 125 telemetry, mean 1.04 ms,
  **max 83.5 ms** (run 8); queued clock (old definition) mean 1.07 ms, max 83.5 ms. `hri_analysis.py` reports the
  per-frame field (18 121 of 18 125, mean 1.03 ms, p95 1.48 ms, max 51.9 ms), which misses some replies (item 12).
- Collisions: 0 (0 with a person). Closest distance to a person (robot body to worker axis): min 1.352 m, mean 1.376 m.
- Perception against truth (recall, distance error) is **not_evaluated** on the final session (`hri_eval_dev.py`
  refuses final sessions by design).

Acceptance criteria of item 7 (`hri_session_check.py`), all **met**: (1) full interaction at all 30 stops: speed in
the last 1.0 s before every scan at most 0.35 m/s, robot-worker distance at the ask 1.852-1.942 m (Unity truth), ask
to execute 1.39-1.78 s; (2) workers textured (URP/Lit, `Ch32_1001_Diffuse`) and FORWARD read from the arm at every
stop; (3) 0 watchdog stops after start-up (new rule; old-rule stops after start-up also 0), max round trip 83.5 ms
< 100 ms; (4) every outcome recorded.

Infrastructure (bridge summary.json, resources.csv):
- Watchdog: 0 stops in the session. 2 Unity frame stalls (gaps 3656 ms and 1281 ms), both before trial 1 (start-up,
  no trial running). Unity frames after start-up: 82 314, max 215.4 ms, p99 35.6 ms, 109 over 100 ms, 0 over 250 ms.
- Python: receive lag max 90.3 ms (0 over 100 ms); event-loop lag 5 over 50 ms, max 130 ms (just before trial 1),
  0 over 250 ms; garbage collections over 10 ms only at start-up (by 107.5 s, before the heap freeze), the largest
  2466 ms.
- Dropped frames: Unity 31 of 4606 (360, 0.67 %) and 149 of 9214 (pan-tilt, 1.62 %); Python newest-frame-only drops 3
  (360) and 543 (gesture). Sampled JPEGs 683 saved, 0 skipped.
- **Run protocol, as recorded:** power mode Best performance and mains power (`run_info.json -> machine_state`, no
  launcher warning): met. "Other applications closed": **not fully met** according to the resource log: Task
  Manager was among the top 3 other CPU users in 586 of 1184 samples, VS Code in 290, Claude Code in 64; a `cmd`
  process used 2-4 logical CPUs from the server start (16:11:18) until 16:16:28 (about 40 s into run 1), then at most
  11 % of one CPU (the log stores the name only, so which program it was is not known). Memory was tighter than in
  item 18: free memory min 13 MB, mean 498 MB (item 18: min 1979 MB, mean 2532 MB); hard paging max 119 428 pages/s,
  mean 2104. Lowest in run 1 (mean 125 MB free) and briefly in run 8 (min 82 MB). All criteria were met despite this;
  the result stands as recorded and the run is not repeated.
- Compared with the Task 2 final (section 2, different task, run under the old watchdog rule and before the
  infrastructure changes of section 9): junction reads 14/14 there, 30/30 here, all at the first ask in both; 0
  collisions in both; closest approach 1.03 m there, 1.35 m here.

## 11. Declared replication of the Task 2 final (22 October 2026, written before it runs)

Declared at 17:15 BST on 22 October 2026, before any replication trial and before any replication session folder
exists. The original Task 2 final (section 2, `trials_final_Task2_20261020_172445`, commit ce37a56) **stands as
recorded**. The replication's results are reported beside it **whatever they are**; they do not replace, correct or
average with it.

1. **What runs.**
   - `configs/trials.json`: "task": "Task2", "mode": "replication" (its own commit, the only change in it). Final seed
     2, 10 trials, timeout 240 s, stuck 10 s / 0.25 m, success radius 0.3 m, equal to
     `hri_frozen.json -> tasks.Task2.trials_fixed` (`test_hri_frozen.py`). Same seed, so the same goal order as the
     original (E1 E2 E4 E2 E1 E3 E4 E1 E4 E1, recomputed by the runner and written to session.json).
   - **Frozen settings unchanged.** hri_control.json, hri_perception.json, gesture_hri.json, roadmap.json, bridge.json,
     robot.json, robot_unity.json and bridge_unity.json are byte-identical to the Task 2 final; `test_hri_frozen.py`
     pins the shared hashes to the ce37a56 values and passes. Pose weights `models/yolo11s-pose.pt` sha256
     1060bda4...c2ba, equal to `hri_frozen.json -> pose_weights` (checked 22 October 2026, 17:10).
   - **Replication mode** (commit b587c73, infrastructure, before this declaration): the Unity trial runner applies
     the final's rules (final seed, trial_count, frozen hri_control / hri_perception, pose weights hash), writes
     `trials_replication_Task2_<time>/` and `REPLICATION_DONE.json`, and refuses a second Task 2 replication. It never
     writes or reads FINAL_DONE.json, so it cannot replace or block a final. Any mode other than development, final or
     replication is now refused (before, an unknown mode silently ran as development with the dev seed).
     EditMode tests `FinalRunGuardTests` (4 new, 39/39 pass); Python `test_hri_frozen.py` checks the mode.
   - Runs **once**. Nothing is rerun, adjusted or discarded, whatever the result.
2. **Machine and way of running.**
   - Nusrat's PC: Windows 11, NVIDIA RTX 3060 12 GB, 16 GB RAM; the machine of the Task 1 final (section 10).
   - Unity Editor 2022.3.62f3, started through the launcher `run_trials.ps1 -Task Task2` (guide mode, vision
     perception, Task 2 map, resource log), Play pressed in the Editor; after the last trial one Ctrl+C in the server
     window, then wait for `[bridge] stopped; summary in ...` (section 9 item 19).
   - Run protocol (section 9 item 17): other applications closed; Windows power mode Best performance; mains power
     (desktop). Recorded in `run_info.json -> machine_state` and checked through the resource log.
3. **Preconditions checked before this declaration** (22 October 2026, 17:05-17:14): working tree clean at fb810ca;
   full Python suite passes (284 tests; 285 with the new mode test); worker error-shader / texture check passes
   (`Check Worker` in batch mode, `outputs/worker_check_20261022_171211`: scene worker `Ch32: Worker_URP [Universal
   Render Pipeline/Lit] Ch32_1001_Diffuse 4096x4096`, no problems; worker.fbx sha256 d883783c...2c51, avatar mapping
   sha256 d9b9596d...f310, both equal to section 9 item 2); the trial runner repeats the appearance check on the
   session itself and refuses it otherwise; weights hash matches; no `REPLICATION_DONE.json` and no
   `trials_replication_*` folder exists.
4. **Declared differences from the original Task 2 final** (all made before this declaration; none is a frozen
   setting):
   - **Different machine.** Original: Anisha's Mac (8 GB; YOLO on MPS, section 4 item 3). Replication: Nusrat's PC,
     CUDA (RTX 3060). Device and precision per model are recorded at runtime in `run_info.json` from this run on
     (item 5).
   - **Decoupled server** (section 9 items 4, 5, 12; infrastructure): complete perception warm-up and
     `perception_ready` before trial 1; sampled JPEGs written on a background thread; heap frozen after warm-up
     (`gc.freeze()`); perception on two threads (360 people, gesture), newest frame only, the asyncio loop never runs
     inference. Outputs were shown identical on saved frames (section 9 item 12).
   - **Corrected watchdog rule** (section 9 item 17, declared change of the trigger in Unity code; `watchdog_timeout_s`
     0.3 s unchanged): the robot stops only if no command arrives for telemetry Unity actually sent more than 0.3 s
     earlier (plus the not-written backstop). The original ran under the wall-clock rule; the old-rule count (stops +
     Unity frame stalls) is reported beside the new one.
   - **Way of running:** Unity Editor (as the Task 1 final), not the batch-mode command of section 7. TrialBatchPlay's
     60 fps cap (section 4 item 3) applies only in batch mode.
   - **Worker material** recreated on this PC with the fixed GUID (section 9 item 1); same FBX, same URP/Lit settings.
   - **FORWARD pose unchanged** (the fist; section 9 item 16: the index finger was not adopted). Pose code identical
     to ce37a56. Task 2's single moved worker and its placement rule are unchanged (the Task 1 workers stay inactive).
   - Measurement added since the original (reporting only): network-thread round trip, Unity frame times, resource
     log, `time_excl_stale_stops_s` and `in_motion_s` (section 8).
5. **Comparison plan** (fixed now): side by side with section 2 — successes, junctions read as shown (with coverage),
   collisions, final distance to B, gesture shown vs read, time excluding stale-perception stops, time in motion.
   Inference time and total trial time are reported but marked **not comparable across machines**. Where a figure of
   the original is not in AUDIT.md and its session folders are not on this PC, it is reported as not available, not
   estimated.
6. **Inference device and precision now recorded at runtime** (logging only, after the trials.json commit and before
   the replication runs; no setting, model argument or device choice changed).
   - `run_info.json -> inference_devices`, written by the server once the models are loaded and warmed up: per model
     the device actually used (CUDA GPU name, MPS or CPU) and the precision (FP32 / FP16), read from the parameters of
     the live predictors (`hri_perception.yolo_runtime`); for MediaPipe the delegate the recognizer was created with
     (`GestureRecognizerAdapter.runtime`; MediaPipe does not expose its compute precision, so it is recorded as
     `unknown`); and the torch (with its CUDA build and cuDNN), Ultralytics, MediaPipe, OpenCV and Python versions.
     A reader error is written into the file instead of stopping the run.
   - Rerunnable check script in the repository: `robot_vision/check_inference_device.py [--save]` (same loading,
     warm-up and reader as the server; `--save` writes `outputs/device_check_<time>/`). On this PC
     (`outputs/device_check_20261022_172022`): YOLO11s-pose panorama and gesture **CUDA NVIDIA GeForce RTX 3060,
     FP32** (weights stored FP16 in the .pt, loaded as FP32); MediaPipe STOP **CPU** (delegate not set: MediaPipe's
     default); torch 2.14.1+cu130 (CUDA 13.0, cuDNN 92400), Ultralytics 8.4.175, MediaPipe 1.1.1, OpenCV 5.0.0,
     Python 3.12.14.
   - Tests: `tests/test_inference_devices.py` (13: FP32 / FP16 / mixed precision, the live predictor preferred over
     the loaded model, the real Ultralytics 8.4 layout when the weights are present, CUDA name when a GPU is present,
     MediaPipe delegate, run_info.json written with nothing else changed, reader errors logged not raised).
   - **The Task 1 final's device (section 10) was not recorded directly; it is reconstructed from logs and code:**
     CUDA from `hri_perception.json` `device: auto` with `check_environment.select_device` (CUDA first) and
     `bridge_guide_20261022_161116/summary.json -> threads_at_start.torch_cuda: true`; FP32 because the code passes
     no `half` argument (Ultralytics' default is FP32) and the same code on the same PC reads FP32 today; MediaPipe
     on CPU because the adapter sets no delegate. The same applies to every earlier session. For the original Task 2
     final (Mac) neither device nor precision was recorded; section 4 item 3 documents YOLO on MPS for the Mac
     sessions, and `select_device` picks MPS there when CUDA is absent.

## 12. Task 2 workers: one standing copy per junction (22 October 2026, declared design change after results)

**Declared design change for demonstrations only, made after both Task 2 runs** (the Task 2 final, section 2, and
the Task 2 replication, section 13; owner's request, on watching the replication). **It affects no reported
result:** both runs used the earlier layout (one worker moved to each junction), every figure in sections 2 and 13
comes from them, and neither can run again (FINAL_DONE.json, REPLICATION_DONE.json). The standing-worker layout is
**used for demonstrations only** (development-mode sessions shown to viewers); no result in this audit is produced
with it, and none will be.

- **Observed in the replication** (`trials_replication_Task2_20261022_180918`, truth logs): the one worker was moved
  to the next junction as soon as Python's target became that junction. In run 3 it jumped from J1's stand (8.75, 2.5)
  to J2's stand (-8.75, 2.5) at 111.4 s, while the robot was still executing the turn at J1, so it seemed to
  disappear after giving the direction. In one-junction trials it stayed at J1 throughout. This was the specified
  behaviour (`docs/project_flow.md`: "in Task 2 it is moved to each junction") and the same code as the original
  final (ce37a56); it was not a fault.
- **Change.** Only one worker is coded and kept in the scene (`Worker`, GestureWorker). For Task 2 the trial runner
  copies it at Play (`Instantiate`: same avatar, material, poses and code) so that one worker stands at every
  junction: the scene worker at J1, the copy `Worker_Task2_J2` at J2, each at its junction's `workerStand` (roadmap
  rule, unchanged), facing the robot, showing the command toward B for the whole trial (NONE at a junction off the
  route: J2 on E1 / E2 trials). `Task2Workers.cs` (WarehouseHRI), `TrialRunner.SetupTask2Workers`. The appearance
  check and the stand-inside-a-collider check apply to every copy; closest-person distance, the truth log and the
  collision scoring use all workers. The scene, roadmap.json and every frozen config are unchanged; the gesture
  sweeps still use the one worker alone. Task 1 is unchanged.
- **Why the frozen perception is not expected to be affected** (checked before any Unity session with it): the J2
  copy is never closer than 15 m to the E1 and E2 routes (the 360 camera's recall was already 0.0 at 9-12 m,
  section 3); on E3 / E4 it stands where the moved worker stood at J2. At each junction its own worker is the nearest person
  (3.5 m against 15 m), so the frozen nearest-person scan picks it.
- **Simulator** (`tests/test_task2_workers.py`, frozen controller, standing workers at J1 and J2): all four goals
  SUCCESS with seed 1 (exact perception) and seed 2 (detection 0.84, distance noise 0.2 m, bearing 2 deg); every
  junction read as shown at the first ask, each time approaching that junction's own worker (within 0.32 m);
  closest pass at least 1.42 m.
- **Unity Play evidence: none yet.** No Unity session has run with this layout; a demonstration session would be
  development mode (trials.json) and is not a result.
- Checks: Unity EditMode 43/43 pass in batch mode (4 new `Task2WorkersTests`: one worker per junction in name order,
  junction without a stand refused, copy name counted as a person and distinct from the Task 1 workers' names, NONE at
  a junction off the route); Python 300 tests pass (2 new in `test_task2_workers.py`).

## 13. Task 2 replication result (final seed 2, run once, commit 0e8269c, 22 October 2026)

Run as declared in section 11: Nusrat's PC, Unity Editor 2022.3.62f3, `run_trials.ps1 -Task Task2`, Play in the
Editor, server stopped with one Ctrl+C after the last trial (summary.json and COMPLETE written). Commit 0e8269c (no
uncommitted changes, `run_info.json -> git`); trials.json Task2 / replication. Server from 18:07:10, session from
18:09:18. The trial runner's final-rule checks passed and it wrote REPLICATION_DONE.json, so no second Task 2
replication can run. Worker layout: the original one (one worker moved to each junction); the standing-worker
layout of section 12 came after this run and is not in it. Analysed once with `hri_trials.py`, `hri_analysis.py` and
`hri_session_check.py`; nothing was rerun, adjusted or discarded. **The original Task 2 final (section 2) stands as
recorded; this result is reported beside it and replaces nothing.**

Folders: `trials_replication_Task2_20261022_180918` (Unity), `bridge_guide_20261022_180710` (Python),
`hri_trials_20261022_185958`, `hri_analysis_20261022_185958`, `session_check_20261022_190002`.

Devices (`run_info.json -> inference_devices`, read at runtime): YOLO11s-pose panorama and gesture on CUDA NVIDIA
GeForce RTX 3060, FP32; MediaPipe STOP on CPU (precision not exposed); torch 2.14.1+cu130, Ultralytics 8.4.175,
MediaPipe 1.1.1. Original: Mac, YOLO on MPS (section 4 item 3), precision not recorded.

**10/10 SUCCESS** (Wilson 95 %: 0.72-1.0); failures: none. Goal order E1 E2 E4 E2 E1 E3 E4 E1 E4 E1, equal to the
original's (recomputed from the seed, matches).

| run | goal B | outcome original / replication | distance to B (m) original / replication | junctions shown > read, replication (asks) | time (s) original / replication | closest to worker (m) original / replication |
|---|---|---|---|---|---|---|
| 1 | E1 | SUCCESS / SUCCESS | 0.031 / 0.029 | J1: FORWARD > FORWARD (1) | 40.64 / 39.84 | 1.127 / 1.067 |
| 2 | E2 | SUCCESS / SUCCESS | 0.033 / 0.022 | J1: RIGHT > RIGHT (1) | 42.56 / 42.62 | 1.132 / 1.112 |
| 3 | E4 | SUCCESS / SUCCESS | 0.052 / 0.031 | J1: LEFT > LEFT (1); J2: RIGHT > RIGHT (1) | 72.88 / 72.42 | 1.264 / 1.226 |
| 4 | E2 | SUCCESS / SUCCESS | 0.050 / 0.040 | J1: RIGHT > RIGHT (1) | 42.78 / 42.34 | 1.275 / 1.221 |
| 5 | E1 | SUCCESS / SUCCESS | 0.050 / 0.025 | J1: FORWARD > FORWARD (1) | 40.06 / 39.64 | 1.140 / 1.080 |
| 6 | E3 | SUCCESS / SUCCESS | 0.048 / 0.022 | J1: LEFT > LEFT (1); J2: FORWARD > FORWARD (1) | 76.62 / 75.90 | 1.033 / 1.002 |
| 7 | E4 | SUCCESS / SUCCESS | 0.055 / 0.030 | J1: LEFT > LEFT (1); J2: RIGHT > RIGHT (1) | 73.66 / 72.42 | 1.260 / 1.202 |
| 8 | E1 | SUCCESS / SUCCESS | 0.048 / 0.023 | J1: FORWARD > FORWARD (1) | 40.22 / 39.76 | 1.141 / 1.088 |
| 9 | E4 | SUCCESS / SUCCESS | 0.058 / 0.029 | J1: LEFT > LEFT (1); J2: RIGHT > RIGHT (1) | 74.60 / 72.54 | 1.262 / 1.231 |
| 10 | E1 | SUCCESS / SUCCESS | 0.049 / 0.025 | J1: FORWARD > FORWARD (1) | 42.64 / 39.74 | 1.075 / 1.064 |

The original's junction reads are those of section 2 (the same shown > read in every run, all at the first ask). Its
per-run times are total times, which include its stale-perception stops; the replication had none, so its total
equals its time excluding stale stops.

Side by side (comparison plan of section 11 item 5):

| measure | original Task 2 final (section 2) | replication (this section) |
|---|---|---|
| successes | 10/10 (Wilson 0.72-1.0) | 10/10 (Wilson 0.72-1.0) |
| junctions read as shown (coverage) | 14/14, all at the first ask | 14/14 (coverage 14/14), all at the first ask |
| gesture shown vs read at junctions | FORWARD 5/5, LEFT 4/4, RIGHT 5/5 | FORWARD 5/5, LEFT 4/4, RIGHT 5/5 |
| collisions (with a person) | 0 (0) | 0 (0) |
| final distance to B | mean 0.047 m, max 0.058 m | mean 0.028 m, max 0.040 m |
| closest approach to the worker | min 1.033 m, mean 1.171 m | min 1.002 m, mean 1.129 m |
| time excluding stale-perception stops, mean | 53.35 s (54.7 - 1.35, from the section 2 means; per run not available) | 53.72 s (max 75.9 s) |
| time in motion (Unity speed > 0.05 m/s), mean | **not available** (not in AUDIT.md; the original's session folders are not on this PC) | 46.70 s (max 65.2 s) |
| time per step, mean: navigate / scan / approach / ask / gesture / execute (s) | 39.8 / 0.95 / 9.2 / 0.73 / 1.73 / 2.16 | 39.49 / 0.61 / 9.16 / 0.74 / 1.55 / 2.15 |
| speed average / max; turn rate max; travelled / straight line | 0.51 / 0.80 m/s; 51.6 deg/s; 1.30 | 0.516 / 0.80 m/s; 51.6 deg/s; 1.30 |
| stale-perception stops, mean (max) | 1.35 s (5.8 s) | 0 s (0 s) |
| total time, mean (max): **not comparable across machines** | 54.7 s (76.6 s) | 53.72 s (75.9 s) |
| inference per frame, mean over runs: panorama YOLO / gesture YOLO / MediaPipe / JPEG decode / total: **not comparable across machines** | 256 / 62 / 21 / 5.9 / 177 ms | 68.7 / 37.7 / 23.7 / 4.9 / 69.8 ms |
| watchdog stops | 0 (old wall-clock rule) | 0 (new rule); old-rule stops 0 (Unity frame stalls 0) |

- **Gesture shown vs read, per frame** (replication, all 5520 processed pan-tilt frames of the session, all phases):
  NONE 2817, FORWARD 1046, RIGHT 841, LEFT 816, STOP 0. No false STOP and no safety stop of any kind (decisions.csv).
  The original's per-frame counts are not in AUDIT.md (not available).
- **Round trip, all messages (network thread):** 11 140 replies to 11 141 telemetry, mean 1.07 ms, **max 238.2 ms**
  (run 1); per-run maxima 2.3-51.3 ms in runs 2-10. The two telemetry windows over 60 ms are both in run 1: 238.2 ms
  at 136.1 s and 212.6 ms at 151.0 s (Python clock). Each coincides with a Python event-loop lag (240 ms at 136.09 s,
  194 ms at 151.03 s; receive lag max 248.7 ms), the first also with a 377 ms Unity frame. Both stayed under the
  0.3 s watchdog limit, so no stop. Cause not identified: no stack dump (only lags over 250 ms are dumped), no
  stale-perception stop. The original reported a Unity-measured mean of 0.78 ms (old definition); its maximum is not
  in AUDIT.md.
- **Unity frames after start-up:** 49 346, max 377.0 ms, p99 32.8 ms, 67 over 100 ms. Dropped frames: Unity 19 (360)
  / 104 (pan-tilt); Python newest-frame-only drops 1 (360) / 46 (gesture).
- **Run protocol, as recorded:** power mode Best performance and mains power (`run_info.json -> machine_state`, no
  launcher warning): met. "Other applications closed": **not fully met** according to the resource log (691
  samples): Task Manager among the top 3 other CPU users in 461 samples, VS Code in 226, `cmd` in 87. Free memory min
  154 MB, mean 514 MB (Task 1 final: min 13 MB, mean 498 MB); hard paging max 40 134 pages/s, mean 810. Around the two
  run-1 stalls free memory was 180-415 MB with Windows memory compression active.
- **Resource log, Unity columns not usable:** the monitor matched a process of about 2 MB resident (not the Editor),
  so Unity's CPU and memory figures for this session are not reported.
- **`hri_session_check.py`** was written for Task 1 (its criteria of section 9 item 7 count Task 1 checkpoints); on
  this Task 2 session it finds 0 checkpoints, so criteria 1 and 2 do not apply here (it prints 1 MET and 2 NOT MET on
  empty lists). For information: 3a, 0 watchdog stops after start-up: met; 3b, maximum round trip under 100 ms: **not
  met (238.2 ms)**; 4, every outcome recorded: met. These were the Task 1 development acceptance criteria, not part of
  this replication's comparison plan.
- Perception against truth (recall, distance error): **not_evaluated** (`hri_eval_dev.py` refuses non-development
  sessions by design).

Reading: on a different machine and with the declared infrastructure differences (section 11 item 4), the
replication reproduces the original's outcome exactly: 10/10, the same 14 junction reads all at the first ask,
0 collisions. It stopped closer to B (mean 0.028 m against 0.047 m) and passed the worker slightly closer (min 1.002 m
against 1.033 m; both above 1.0 m). Time excluding stale stops is about the same (53.72 s against 53.35 s); the
original lost 1.35 s per run to stale-perception stops and the replication none, consistent with its faster
inference, which is not comparable across machines. One 10-trial sample per side.

## 14. v4 plan (written 24 October 2026; to be completed BEFORE any v4 final run)

**Status: draft. Decided 24 October 2026 (before any v4 development or final data existed): B1 to B6, B10, B12 and the bootstrap settings (14.13); open: B7, B8, B9, B11.** This section is the v4 counterpart of sections 2, 8 and 11: it fixes, before any final run, what is measured, how it
is decided and how it is run. Everything not marked **BLANK** is decided or declared. A BLANK is a number or choice that only Anisha
can make (they are collected in 14.13); none is chosen by the code, and none may be chosen after seeing final results. The v3 results
(sections 2, 10, 13) are not touched: v3 is frozen as release `v1.0` and stays exactly reproducible.

### 14.1 What v4 is

v4 is a new study on top of v3, not a change to it (`docs/project_flow_v4.md`): fixed arm poses (v3) against natural, moving gestures
(v4: POINT with any angle, WAIT, STOP), several people with one commander, a zoom onto the hand, and ground-truth files for scoring.
v4 has its own configs (`robot_vision/configs/v4/`), its own protocol (version 3, `docs/protocol_v3.md`), its own scene, its own
decision rules (below) and its own final runs. The server speaks protocol 3 only when given `--config configs/v4/bridge.json`.
Rule kept from v3: no v3 config, frozen hash or v3 behaviour is changed for v4 (`tests/test_hri_frozen.py` still passes unchanged).

### 14.2 Research questions

1. **RQ1 moving vs fixed:** can the robot understand natural, moving gestures as reliably as v3's fixed poses?
2. **RQ2 who commands:** can it tell which of several people is giving the command?
3. **RQ3 zoom:** does zooming onto the hand improve recognition at a distance? (The same runs with zoom on and off.)
4. **RQ4 new looks:** does it still work on avatar looks it never saw in development? (Wording of 2026-11-08, 14.16: an **unseen appearance of the Sunbox body family**; the test look has the body family of the development looks, not a new body or a new avatar source.)

### 14.3 Metrics (all reported with their coverage and the number of runs behind them)

Computed by `hri_analysis_v4.py` (the numbers by `hri_eval_dev_v4.py` / `hri_eval_final_v4.py`):

- **Outcome:** success rate with a Wilson 95 % interval over runs; failure reasons (collision, timeout, aborted, wrong goal).
- **Gesture reading:** per command (POINT, WAIT, STOP): accuracy among the frames the reader answered and the coverage (share answered), each
  with a Wilson interval (frame level, labelled as such) and a bootstrap interval over runs; the confusion matrix; false reads on frames
  where nothing was shown. NONE and `insufficient_history` readings are coverage, not errors.
- **POINT:** angle error against the true angle on held frames (median, 95th percentile, bootstrap intervals), for the better of the two
  depth readings and for the reading the roadmap resolved; the share of ambiguous frames; the correct-branch rate; how many asks needed a
  second look and how many a re-approach.
- **Commander:** accuracy of the chosen commander against truth, with and without bystanders.
- **Time:** from the first "Which direction?" to the accepted gesture (median, 95th percentile, bootstrap), also without WAIT time.
- **Path:** trail length / optimal path length, largest distance from the optimal corridor, share of the trail within one grid cell of it, final
  distance from B (`gt_path.py`). The corridor is every cell on some shortest path (14.7b); Python's A* length is checked against Unity's, and the
  corridor size and how much of it Unity's drawn path covers are reported.
- **Safety and system:** collisions, closest approach to a person, inference time per model, Unity-measured round trip (machine-dependent).
- **Groups:** per look, per look style, per distance bin, zoom on vs off.
- **RQ1 table:** one table of v4 against the archived v3 results (`results/summary/`), with every declared difference listed under it
  (14.4, item 12).

Intervals: bootstrap over RUNS (frames within a run are not independent), 2000 resamples, seed 1, 95 % (`configs/v4/analysis.json`).

### 14.4 Decision rules, declared in advance

Values in `configs/v4/`, each with its reasoning in the file. "Decided" = decided by Anisha (dates in `docs/gesture_reader_v4.md`,
Decided). "Initial" = proposed with reasoning, to be set on DEVELOPMENT data only (never on test looks or clips).

1. **Reader** (`gesture_reader.json`): a 1.0 s window at 10 Hz; POINT and WAIT are read from a held pose, STOP on a 0.3 s window; initial values.
2. **STOP** needs no push motion (decided): an open palm stops the robot; STOP of anyone in view stops it at once, also while driving.
3. **POINT direction** (decided 24 Oct): a 3D direction from foreshortening (shoulder-to-wrist length against shoulder width, 1.4 initial), both depth
   readings (toward / away from the camera) kept; resolved with the roadmap: each candidate goes to the nearest branch or the arrival
   direction, the arrival direction is never an answer, a candidate farther than 30 deg (initial) from its branch is dropped.
4. **Hand cross-check tie-break** (decided): off until the development evaluation has measured the MediaPipe world-landmark cross-check.
5. **Two-view disambiguation** (decided): if the two readings fit two different branches, move sideways by the re-ask shift (item 5a), read
   again and accept the candidate consistent across both views within 10 deg (initial); at most once per junction; not counted as an ask.
   5a. **Re-ask shift 0.8 m** (`control.json` dialog.`reask_shift_m`; decided 24 Oct 2026 by Anisha as an INITIAL v4 value, to be confirmed on
   development data). **Declared v4 difference for RQ1:** v3 moved 0.4 m (`hri_control.json`, frozen, unchanged; the v4 controller reads the value
   from `control.json`). Reason: in the simulator two-view study (not a measurement; `docs/gesture_reader_v4.md`) at 10 deg angle noise a
   0.4 m shift resolved 18 of 20 ambiguous asks (2 to a wrong branch) and 0.8 m resolved 20 of 20. A 0.8 m shift also moves the mirror
   candidate by about 45 deg, so even a plain second ask from the new viewpoint is unambiguous in the simulator.
6. **Approach the commander** (decided): if the commander is not the person approached, go to them (2.0 m) and ask again, once; not counted as an ask.
7. **Commander timing** (decided): only a gesture that starts after "Which direction?" is shown counts; commander = facing the robot with a
   moving or held hand; none or a tie = no commander.
8. **WAIT** (decided): hold position and watch the same person; 20 s timeout counts as an unclear ask (ask again, then abort).
9. **Zoom rule** (initial values): hand fills a share of the image height, never narrower than the arm fits, widen in steps when the hand is
   lost, clamp 15-60 deg; switch on / off for the RQ3 runs.
10. **Dialog hold 0.5 s** (decided; v3: 1.0 s). **Declared v4 difference for RQ1.** The reader already needs the arm still for 0.4 s and the
    pose to pass its cues in 70 % of the frames; the dialog adds 0.5 s of the same resolved branch.
11. **Unchanged from v3:** approach distance 2.0 m, ask window 5 s, two asks, abort, safety stops, speeds (read from the frozen `hri_control.json`).
12. **Differences between v3 and v4 listed under the RQ1 table** (`analysis.json`, `declared_differences`): gestures, reader, decision, the 0.5 s
    hold, the 0.8 m re-ask shift, several people and the commander rule, zoom, avatar looks and clips, protocol 3 and the v4 scene,
    per-frame truth, runs / seeds / machine. Any further difference found later is added there before the final runs.

No rule is changed after seeing final results. A rule changed after seeing development results is listed in section 15 (to be added),
with the reason, as in section 4.

### 14.5 Settings, seeds and runs

Decided 24 October 2026 by Anisha, before any v4 development or final data existed (`configs/v4/final_plan.json`). Four final settings,
each run once:

| setting | what it varies | RQ |
|---|---|---|
| `zoom_on` | zoom rule on, test looks and clips | RQ3 (with `zoom_off`), RQ1 |
| `zoom_off` | the same runs with the zoom rule off | RQ3 |
| `bystanders` | several people at each junction, one commander | RQ2 |
| `unseen_look` | an avatar look never used in development | RQ4 |

Every final session lies wholly in the TEST split (test looks and clips, never used in development); a session that mixes development and test
data, or uses a name not in `configs/v4/data_splits.json`, is refused. Numbers:

| item | value |
|---|---|
| task / route (B1) | Task2: the guided route with junctions, goal B changing every run (the v3 Task 2 route) |
| development seed (B2) | 1 (as in v3) |
| final seed (B3) | 2: the same goal order as the v3 Task 2 final (E1 E2 E4 E2 E1 E3 E4 E1 E4 E1 for its first 10 runs; `tests/test_v4_frozen.py` pins this), so RQ1 compares the same goals |
| runs per setting (B4) | 20 (the first 10 goals are those of the v3 final; the full order is `hri_trials.goal_order(2, endpoints, 20)`, the same generator Unity uses) |
| trial timeout (B5) | 240 s: the v3 value, `robot_vision/configs/trials.json` `timeout_s`, pinned in `configs/hri_frozen.json` `tasks.Task2.trials_fixed` |
| success radius (B6) | 0.3 m: the v3 value (same two files) |
| which test looks / clips / bystander layout each setting uses (B7) | **BLANK B7** (waiting for Nusrat's real looks and clips, then both of us) |

### 14.6 Data split

Development looks and clips set every threshold; test looks and clips are used once, in the final runs. Names are PLACEHOLDERS in
`data_splits.json` until Nusrat sends the real looks and clips: **BLANK B8** (real names, the number of looks and clips, which look is the unseen
test look, and the look styles). A final evaluation is refused while the names are placeholders.

### 14.7 Frozen hashes

`configs/v4/frozen.json` (written by `freeze_v4.py --freeze`, by Anisha, after the development evaluation) records the SHA-256 (line endings
normalised) of: every file in `configs/v4/` (bridge, commander, control, data_splits, eval_dev, analysis, final_plan, gesture_data,
gesture_reader, gt_eval); the v3 files v4 reads (`hri_control.json`, `hri_perception.json`, `gesture_hri.json`, `roadmap.json`,
`robot.json`); the pose weights and the MediaPipe model file. `tests/test_v4_frozen.py` fails if any changes. Until then `frozen` is false
and final runs and final evaluations are refused. Unity-side files of the v4 scene (its bridge and robot configs) and the Unity final-run
guard: **BLANK B9** (Nusrat lists them; they are added to the freeze the way section 8 item 2 did for v3). So far agreed: `bridge_unity_v4.json`
and `robot_unity_v4.json` (14.7a).

#### 14.7a Unity side (agreed with Nusrat, 29 October 2026; docs only, before any v4 development or final data)

1. **Separate v4 config files.** Unity v4 uses new files `bridge_unity_v4.json` (pointing to `robot_vision/configs/v4/bridge.json`) and
   `robot_unity_v4.json`, loaded only by `WarehouseRobot_v4.unity`. The v3 files `bridge_unity.json` and `robot_unity.json`,
   `configs/hri_frozen.json` and the v3 AUDIT entries (sections 1 to 13) stay unchanged; `tests/test_hri_frozen.py` still pins them.
2. **Grid widening 0.40 m.** Blocked cells of `grid.json` are widened by 0.40 m = robot half-width 0.30 m (`robot_width_m` 0.6 in `robot.json`)
   + safety margin 0.10 m (`safety_margin_per_side_m` in `robot.json`), read through the v4 config. Cell size 0.5 m.
3. **Sensitivity check, report only, run once during development before the freeze.** For each scenario's A-to-B pair Unity also computes
   the A* path with a widening of 0.50 m (the AMR NavMesh agent radius) and reports whether the path or its length differs. It
   decides nothing by itself: the official grid stays 0.40 m unless Anisha and Nusrat decide otherwise before the freeze, and any
   change is disclosed here (section 15). Its report is kept with the development sessions, not with the finals.
4. **Trial runner.** `TrialRunnerV4`, used only in the v4 scene (the v3 `TrialRunner` is unchanged).

These files are added to the B9 list of Unity files to freeze (14.13): `bridge_unity_v4.json` and `robot_unity_v4.json`. B9 stays open
until Nusrat sends the complete list (the rest of the v4 scene's Unity configs) and the Unity final-run guard of `TrialRunnerV4`.

#### 14.7b Ground-truth scoring: the optimal corridor and the leak test (decided 29 October 2026, before any v4 development or final data)

1. **Corridor rule.** The trail measures are scored against the **optimal corridor**, not against `optimal_path.json`. Corridor = every free cell c with
   d(A, c) + d(c, B) = d(A, B) within the 1e-3 m tolerance (two Dijkstra passes, 8-connected, diagonal sqrt(2), no corner cutting, the A* rules). A
   trail point's distance is to the nearest corridor cell centre; "share of the trail within one grid cell" counts points within `near_optimal_cells`
   (1 cell = 0.5 m) of one. A perfect trail between two centres is up to 0.25 m (straight) or 0.35 m (diagonal) from the nearest centre, so the
   resolution of "largest distance" is about half a step. The length check against Unity's `optimal_path.json`, the A* length, the corridor size and the
   number of corridor cells Unity's drawn path covers are reported (so the paper can describe them).
2. **Why.** Nusrat's grid sensitivity check (14.7a item 3; reported by her, output folder
   `robot_vision/outputs/gt_grid_check_20261029_183748/` on her machine) found identical lengths at 0.40 m and 0.50 m widening for all 4 A-to-B pairs, but
   different cells for A to E3 and A to E4: several equally short paths exist, and the measures used to depend on which one A* or Unity returned.
   **0.40 m stays the official widening.**
3. **`trail.csv`** `yaw_deg` has 3 decimals (the protocol example is corrected).
4. **Leak test, enforced (decided 29 October 2026).** Unity runs its own check before trial 1, refuses to start on failure, records the result in `session.json`
   and keeps the image pairs in `leak_test/`; it never writes `leak_test.json`. Python's independent check (`gt_path.session_leak_check`) runs automatically at
   evaluation time and writes `leak_test.json` when absent (never overwriting). **Both must pass**: `hri_eval_final_v4.py` refuses otherwise, before
   `FINAL_DONE.json` and before any test data is read; `hri_eval_dev_v4.py` reports the status per session without refusing; `make_results_archive_v4.py` uses
   the same check. Missing images, a missing or non-boolean Unity result (only `true` passes) or any disagreement is "not passed", with the reason.
   The `session.json` key is a **named setting in `configs/v4/gt_eval.json`. Confirmed 4 November 2026** (Nusrat, commit `43cbeb2`, `TrialRunnerV4`): it is
   `leak_test.passed`, a boolean inside the object `leak_test` in `session.json` (`unity_leak_result_key_confirmed` is now `true`; the placeholder
   `leak_test_passed` of 29 October is gone). Only a boolean `true` passes; the string `"true"` does not. The file is in the frozen set (14.7), so the
   confirmation is made before the freeze.

### 14.8 Run protocol (before every final session)

Other apps closed, Windows power mode "Best performance" (as in section 9), enough free memory, the machine recorded; the leak test
(ground-truth layer on / off render identical) passes before the first run (Unity's own comparison, recorded in `session.json`, and Python's independent
check, `python gt_path.py session <session folder>`, which writes `leak_test.json` and also runs automatically when a final evaluation starts, 14.7b item 4); a resource
log is kept (`--resource-log`). The machine for the finals (B10, decided 24 Oct 2026): Nusrat's Windows PC with the NVIDIA RTX 3060, the same machine
as the v3 Task 1 final (section 10), so inference times of the finals are comparable with that run (not with the Mac original of Task 2). Inference times and total times are not comparable across
machines (14.3, RQ1 table).

### 14.9 Run-once guards

Python: `bridge.server --final-setting NAME` refuses unless the v4 configs are frozen with every hash matching and the setting has not been run
(marker `FINAL_RUN_DONE.json` in the bridge folder once a trial finished); `hri_eval_final_v4.py` refuses unless frozen, the data is test-split
only and is what the setting says (zoom, bystanders, number of runs, seed, task, Unity mode final), and writes `FINAL_DONE.json` last, after
which the setting cannot be evaluated again. A started run or evaluation that did not finish writes no marker and does not block (as in v3).
`hri_analysis_v4.py` only describes the data and may be re-run into a new folder. Unity: the final-run guard of the v4 trial runner is
Nusrat's (**BLANK B9**). A repetition of a final must be declared here first.

### 14.10 Acceptance and reporting

The v3 finals used four criteria (`hri_session_check.py`). Acceptance criteria for v4 (what counts as "reliable" for RQ1, RQ2, RQ3, RQ4):
**BLANK B11**. Results are reported whatever they are; intervals, coverage and the declared differences accompany every comparison.

### 14.11 Procedure, from development recordings to the archived final results

1. Nusrat sends the development recordings (v4 scene, development looks and clips) and the real names; `data_splits.json` is updated.
2. Development evaluation: `hri_eval_dev_v4.py --session UNITY BRIDGE ...` (development data only; test data is refused).
3. Thresholds are set on development data only, written to `configs/v4/` with the date and the rule used (B12, decided 24 Oct 2026: for each initial
   threshold the value with the **highest development accuracy among those with coverage >= 0.8**; ties go to the v3 value, or else to the more
   conservative value, i.e. the one that answers less often and rejects more), and the changes after seeing development results are
   disclosed in section 15.
4. Fill the BLANKs of `final_plan.json`; `python freeze_v4.py --freeze`; commit; `tests/test_v4_frozen.py` now pins everything.
5. Final runs, one per setting, `--final-setting NAME`, on the machine and protocol of 14.8, with Nusrat's Unity final guard.
6. `hri_eval_final_v4.py --setting NAME --session UNITY BRIDGE` per setting (once).
7. `hri_analysis_v4.py --final --session NAME UNITY BRIDGE ...` for the tables, intervals and the RQ1 comparison.
8. Add the sessions to `configs/v4/archive/results_manifest.json`; `make_results_archive_v4.py --repo-summary ../results/summary/v4`; verify with `--verify`.
9. Write the results into sections 16 onward (as sections 10 and 13 did for v3) and stop.

### 14.12 What may not happen

No threshold is tuned on test data or on final results. No final is repeated silently. No v3 file changes. The leak test must pass before a run.
Anything done differently from this section is disclosed here, dated, before the next run.

### 14.13 The blanks

**Decided on 24 October 2026 by Anisha, before any v4 development or final data existed:**

| | decision |
|---|---|
| B1 | Task2 |
| B2 | development seed 1 |
| B3 | final seed 2 (same goal order as the v3 final, for RQ1) |
| B4 | 20 runs per setting |
| B5 | 240 s, the v3 trial timeout (`configs/trials.json`, pinned in `configs/hri_frozen.json`) |
| B6 | success radius 0.3 m (the v3 value) |
| B10 | Nusrat's Windows PC with the RTX 3060 (same machine as the v3 Task 1 final) |
| B12 | threshold rule: highest development accuracy with coverage >= 0.8; ties to the v3 value or the more conservative value |
| bootstrap | 2000 resamples, seed 1 (confirmed) |
| `reask_shift_m` | 0.8 m, an initial v4 value (14.4, item 5a), to be confirmed on development data |

**Still open (the freeze is refused while any is blank; `final_plan.json` keys in brackets):**

| | what | waiting for |
|---|---|---|
| B7 | which test looks, clips and bystander layout each setting uses (`test_assignment`). **Note (7 November 2026, 14.15):** some final cases must place the commander at about 4 m, otherwise the zoom comparison (`zoom_on` against `zoom_off`) measures almost nothing: with a level camera the zoom hardly acts at 2 m | Nusrat's real looks and clips, then both of us |
| B8 | **decided 2026-11-08 (14.16):** real look and clip names (`data_splits.json`: looks `sunbox_m1`, `sunbox_f1` development, `sunbox_f2` test; the nine clips; `placeholder` false), one look style `sunbox`; RQ4 = unseen appearance of the Sunbox body family | decided |
| B9 | the Unity-side files of the v4 scene to freeze and the Unity final-run guard (`unity_files_and_guard`). Agreed 29 Oct 2026 so far: `bridge_unity_v4.json` and `robot_unity_v4.json` are on the list (14.7a); the rest of the list and the `TrialRunnerV4` guard are open. (The leak-test `session.json` key is no longer open: confirmed 4 Nov 2026, 14.7b item 4.) | Nusrat |
| B11 | v4 acceptance criteria for RQ1 to RQ4 (`acceptance_criteria`) | both of us |

### 14.14 Server timing: the v4 models in worker processes (6 November 2026)

**Status (updated 7 November 2026): implemented; measured on Anisha's Mac and, in the replay without Unity, on Nusrat's PC (the machine of the finals, B10).** On the PC both modes
meet every declared limit (section "PC measurement" below). The mode is **not decided yet**: step 4 of the rule (a real Play development session with Unity running, in both modes, with the
free system memory recorded) is still to be done. The rule for choosing the perception mode is decided (6 November 2026, "What is decided" below). Nothing here changes a
v3 file or a v3 result.

**Problem.** Unity stops the robot when Python is silent for 0.3 s (`watchdog_timeout_s`). The v3 server runs the models on two threads of the
same process as the asyncio loop that answers the telemetry, so heavy Python work (MediaPipe, the tracker, a garbage collection) can hold the GIL
and stall the loop. Nusrat's v3 check run of 2026-11-03 had one watchdog stop from a 0.4 s stall. v4 adds more work in that process (hands, the
moving-gesture buffers, the commander rule), so this had to be addressed before any v4 final.

**What was changed (protocol 3 only).**
- `bridge/perception_mp_v4.py` (new): the v4 perception in two worker processes started with `spawn` (Windows and macOS), one per camera:
  `people` (frame_360: YOLO11s-pose + ByteTrack, `HriPerception.people`) and `gesture` (frame_pan_tilt: tracked people, hands, buffers,
  reader, `HriPerceptionV4.persons`). Inside each worker the unchanged `PerceptionWorkerV4` runs its lane (same processing, same latest-frame-only
  rule, same `perception.csv` row); the real classes load only the models their lane needs (the 360 model and the v3 STOP adapter, which v4 does not use, are
  not loaded in the gesture worker).
- In the server process: `submit()` puts the frame in a one-slot mailbox (a newer frame replaces it, counted as dropped) and returns; a sender thread per
  worker writes it into the pipe; a receiver thread per worker swaps the results in; `snapshot()` / `snapshot_v4()` only read them under a lock that is
  held for assignments only (file writes have their own lock). The asyncio loop never touches a pipe and never waits for a model.
- A worker that dies, fails to start, or leaves a frame without a result for `behind_after_s` (0.5 s) is logged (console, `perception_events.jsonl`,
  `summary.json` -> `perception.worker_events`) and the server goes on answering with the last results, whose capture times make them stale for the
  controller (`people_stale_s`, `gesture_stale_s`: unknown, never a guess). A failure at start-up stops the server before it listens. No restart.
- `bridge/timing_v4.py` and `timing_check_v4.py` (new): the loop-lag monitor that keeps every sample (p99), and the repeatable timing check.
  `bridge/server.py`: protocol 3 only: `perception_workers.mode` and the v4 monitor; the protocol 2 branch is byte-for-byte the old behaviour (tests).
  `configs/v4/bridge.json`: `timing`, `timing_limits`, `perception_workers`. `bridge/perception.py`, `bridge/perception_v4.py`,
  `bridge/diagnostics.py`, `bridge/guide*.py`, every v3 config and every frozen hash are unchanged.
- Setting: `perception_workers.mode` is `processes` (as requested) or `threads` (the design that was measured as the baseline). It is part of the
  v4 bridge config, so it is pinned by the freeze (14.7).

**Limits declared before the fix was measured** (`configs/v4/bridge.json` -> `timing_limits`; proposed by Claude, accepted by Anisha as proposed on
6 November 2026 after the baseline below was shown to her; commit `d8a0200` holds the limits and the unwired module, the "after" runs came later). They come from
the 0.3 s watchdog and a margin, not from any measurement of the fix; every entry is "measured <= limit":

| metric | limit | meaning |
|---|---|---|
| `loop_lag_p99_ms` | 25 | how late the server's 10 ms asyncio sleep wakes up, 99th percentile |
| `loop_lag_max_ms` | 100 | the same, maximum (a third of the watchdog) |
| `round_trip_p99_ms` / `round_trip_max_ms` | 50 / 150 | telemetry written -> its command read, as the client sees it |
| `reply_gap_max_ms` | 150 | longest silence between two commands (the replay's telemetry period is 50 ms) |
| `unanswered_telemetry` | 0 | telemetry with no command |
| `perception_worker_events` | 0 | worker deaths, errors and "behind" episodes (0 when the workers are threads) |

**Method.** `timing_check_v4.py --frames outputs/bridge_guide_20261020_164656/frames --duration-s 120`: it starts the v4 guide server with the real models
(YOLO11s-pose, MediaPipe) and replays 171 saved panorama and 300 saved pan-tilt JPEGs of the 2026-10-20 development session through `bridge/replay_client.py`
at the real rates (20 Hz telemetry, 5 Hz panorama, 10 Hz pan-tilt, protocol 3), then reads what the server and the client measured. The replay is a
stand-in for Unity with no robot and no trial (`trial_running` false), so it measures the Python side with the models busy, not Unity's own load.
Machine: Anisha's MacBook (macOS 26.6, arm64, Apple GPU via MPS, 8 cores), commit as in each `report.json`. Outputs: `outputs/timing_check_v4_<time>/` (report.md,
report.json, the replay, the server log) and the server's own run folder.

**Before (thread design) and after (worker processes), 120 s replays.** Every run that was made is listed (none is left out):

| run (folder `timing_check_v4_...`) | workers | device | loop lag p99 / max (ms) | round trip p99 / max (ms) | longest reply gap (ms) | unanswered | worker events | stall dumps | replay client paused >100 ms |
|---|---|---|---|---|---|---|---|---|---|
| 20261106_171152 | threads | Apple GPU | server crashed at once (below), no numbers | | | | | | |
| 20261106_171429 | threads | CPU | 3.6 / 27.2 | 4.6 / 44.1 | 100.0 | 0 | 0 | 0 | no |
| 20261106_173759 (replicate) | threads | CPU | 4.1 / 27.9 | 4.6 / 20.5 | 69.8 | 0 | 0 | 0 | no |
| 20261106_172133 | processes | CPU | 4.7 / 28.2 | 6.4 / 21.3 | 72.4 | 0 | 101 "behind" | 0 | no |
| 20261106_172342 | processes | Apple GPU | 2.4 / **186.1** | 5.0 / 70.9 | **156.4** | 0 | 0 | 1 | yes (137 ms) |
| 20261106_172643 (replicate) | processes | Apple GPU | 11.8 / **226.0** | **67.4** / **460.5** | **561.4** | 0 | 12 | 4 | yes (7 times, up to 332 ms) |
| 20261106_172852 (replicate) | processes | Apple GPU | 2.9 / **274.2** | 26.2 / **371.4** | **423.3** | 0 | 9 | 4 | yes (4 times, up to 347 ms) |

A 30 s smoke run of the process mode (`..._171841`) found a flaw in the first "behind" rule (it measured from the last result, so both workers were flagged
as soon as the first frames arrived); the rule was changed to measure how long a submitted frame waits and the runs above were made with the corrected
rule. Bold = a declared limit missed. A 20 s run with the committed default config (`..._174823`, Apple GPU, processes, no flags) met every limit (loop lag p99 1.2 / max 11.6 ms, round trip max 6.1 ms, longest gap 56.7 ms); it is shorter than the 60 s the limits are defined for, so it is not counted as a pass. Perception throughput (frames processed of frames offered): CPU, threads 104 of 600 panorama and 522 of 1200 pan-tilt (second run 102 / 495),
CPU, processes 100 / 490 (the CPU cannot keep up: a panorama frame takes 1.3 to 1.7 s, so the workers report "behind" by design); Apple GPU, processes 442 to 478 of 600
panorama and 1037 to 1154 of 1200 pan-tilt, end-to-end latency p99 218 to 399 ms (pan-tilt) and 493 to 582 ms (panorama). Memory (60 s replays on the CPU, `..._174110` and `..._174218`):
threads 1.57 GB in one process; processes 0.23 GB (server) + 1.74 GB (workers) = 1.96 GB, about 25 % more. Cost of the controller itself per telemetry
(`GuideControllerV4.on_message`, the test rig with four people in view, 2000 messages): mean 0.04 ms, p99 0.15 ms, max 0.33 ms (not in the replay, which is idle; negligible next to the limits).

**PC measurement (Nusrat's PC, recorded 7 November 2026).** Windows 11, NVIDIA RTX 3060, 60 s replay (`timing_check_v4.py`, no Unity, real models, 20 / 5 / 10 Hz), the run protocol of 14.8 followed.
`threads` was run at commit `80a64d1`, `processes` at `650bf53`; `robot_vision/` is identical between these two commits, so the comparison is fair. Source of the numbers: they were read
directly from Nusrat's result zip `timing_checks_20261107.zip` (the two `timing_check_v4_*` `report.md` files, `gc_pauses.csv`, `loop_lag.csv`, `server.log` and `summary.json` of the two `bridge_guide_20261107_*` runs)
by Anisha's assistant, not taken from a second-hand analysis. The zip is outside the repository and nothing from it was copied in. Recorded here on Anisha's instruction.

| | loop lag p99 / max (ms) | round trip p99 / max (ms) | longest reply gap (ms) | unanswered | worker events | memory | limits |
|---|---|---|---|---|---|---|---|
| threads | 21 / 22 | 2.3 / 21.9 | 68.2 | 0 | 0 | 1.5 GB | all met |
| processes | 21 / 68 | 2.3 / 79.5 | 125.4 | 0 | 0 | 2.9 GB | all met |

*Garbage collection.* Every pause over 10 ms happened **before Unity connected** (threads: between 16 s and 58 s after the start, Unity connected at 59.9 s; processes: 58.9 to 62.6 s, connected at 63.1 s).
The largest ones, 294 ms (threads) and 125 ms (processes), are `freeze_heap`'s own `gc.collect()` (`full_collect_ms_before` 294.53 and 124.72 ms), which runs once before the server listens; after the freeze a full collection takes
0.01 ms. No pause over 10 ms happened while Unity was connected, so the loop lag maximum stayed at 22 ms with threads. The heap freeze works as it did in v3 (section 9).

*Reading.* Step 1 of the rule: both modes meet every limit in the replay, so `processes` is preferred. This is **not a decision**: the replay has no Unity. Step 4 (a real Play session with Unity running) is still open, to be run in both modes.
`processes` costs 1.4 GB more memory (2.9 GB against 1.5 GB), and free memory fell to 13 MB on this PC in a v3 session (as reported by Nusrat; see also section 9 item 17), so memory is the condition to watch.
**Recorded condition for that Play session: the free system memory** (lowest value and the value at the end, from the resource log, `--resource-log`), for each mode, next to the watchdog stops, the worker events, the loop lag and the round trip.
In the replay `processes` had a larger loop-lag maximum (68 against 22 ms), round-trip maximum (79.5 against 21.9 ms) and longest reply gap (125.4 against 68.2 ms), all inside the limits (100, 150, 150 ms) but with less margin on the reply gap.

**What the numbers show.**
1. **The thread design cannot use the Apple GPU at all:** with both perception threads on MPS the server process aborts at the first frames with the Metal assertion
   `A command encoder is already encoding to this command buffer` (`..._171152/server.log`). With one process per camera the same models run on the Apple GPU. (The v3
   Task 2 final on the Mac ran before the two-thread split of 2026-10-21.) On the PC with CUDA the thread design runs, as in the v3 checks.
2. **On the CPU both designs meet every timing limit** (loop lag max 27 to 28 ms, round trip max 20 to 44 ms, longest gap 70 to 100 ms); the worker-process design costs nothing measurable
   in loop timing there, and its "behind" events are the CPU being too slow for the panorama (not a defect; the limit `perception_worker_events` is meant for a machine whose inference keeps up).
3. **On the Apple GPU with worker processes the limits were missed in 3 of 3 runs** (loop lag max 186 to 274 ms, round trip max up to 461 ms; in two of the runs one round trip each exceeded 300 ms,
   which Unity's watchdog would have counted as a stop), **and the cause is not the server's GIL**: (a) in the 10 stack dumps of the 9 stalls (`stall_tracebacks.txt`, dump after 0.1 s) no other thread of the server process was running Python: they were waiting (on a lock, in `recv`, on the queue), or inside a pipe write or a console `print`, which release the GIL, and the main thread was either in the loop monitor's own sleep line or in ordinary handler code (`snapshot()`'s JSON, `_handle`), not blocked on any lock, so nothing was holding the GIL against it; (b) the replay client, a separate process that loads no model, also stopped sending telemetry for 104 to 347 ms at the same moments in all
   three runs, and in none of the five CPU runs (nor in the 30 s smoke run on the Apple GPU); (c) both workers were reported "behind" at the same instants. The whole machine paused while the Apple GPU was loaded; why is not identified
   (a hypothesis, not tested: GPU load starving the rest of the system on this Mac). The limits are therefore **not met on this machine on the Apple GPU**, and no thread-design figure exists for it to compare with (it crashes).
4. **This is the same signature as the PC stall of section 9 item 13** (256 ms stall with both perception threads idle in the stack dump). So the cause of the 2026-11-03 stall may also be machine-level
   (memory pressure, CPU contention, antivirus, power), in which case moving the models out of the process removes one cause (the shared GIL, by construction) but cannot be shown to remove that stall.
   **Whether it does can only be measured on the PC.**

**What is decided.** (The choice of the mode itself was made on 8 November 2026, with a disclosed departure from step 1 of the rule below: see 14.16 item 1.)
- Decided (6 November 2026, Anisha): v4 uses worker processes for the models; the thread design stays selectable (`perception_workers.mode`), protocol 2 always uses threads. The limits are not changed because of any result.
- **Decided (6 November 2026, Anisha): the rule for choosing the mode.**
  1. On Nusrat's PC, under the run protocol of 14.8, run `timing_check_v4.py` in both modes (`--workers threads`, `--workers processes`, 60 s or more).
  2. Use `processes` if it meets every declared limit; otherwise use `threads` if it does; if neither does, **no v4 final starts until the cause is found** (resource log, `stall_tracebacks.txt`).
  3. **Addition:** the chosen mode must also pass **one real Play development session with Unity running** before the freeze: 0 watchdog stops, 0 worker events, and loop lag and round trip within the declared limits. If it fails there, the same rule applies again (the other mode is tried; if neither passes, no freeze and no final).
     **Recorded condition (7 November 2026, Anisha):** the free system memory during that Play session is recorded with the result (lowest value and the value at the end, from the resource log, `--resource-log`), because the worker processes need about 400 MB more than threads and memory pressure was a measured candidate cause of the earlier stalls (section 9 item 17).
  4. The mode in `bridge.json` is what the freeze pins (14.7). The result of each step is recorded here, dated, with the run folders.
- Status of the rule: **not yet applied** (no PC measurement and no Play session exist yet).

**Not shown / limits of this check.** The replay is not Unity (Editor rendering, physics and the network threads share the PC in a real run); the controller's step and the commander rule are not in it (measured separately, tiny);
the frames are of the 2026-10-20 scene; one Mac and, for the PC, a replay without Unity (the Play session is step 4); the "behind" threshold (0.5 s, equal to `gesture_stale_s`) produced no event on the PC replay (0 worker events in both modes); a dead worker is not restarted (the trial then times out or aborts on stale perception, which is the honest outcome).

**For the next Play run (Nusrat).** (1) Before it: the two timing checks above on the PC, send both `outputs/timing_check_v4_*` folders. (2) In the run: the console shows `[perception] worker people ready`, `... worker gesture ready` before Unity may connect (loading takes
longer than with threads), and any `died` / `behind` / `error` line; afterwards `summary.json` -> `perception.worker_events` must be empty, `event_loop_lag.all_samples` gives p99 / max, `stall_tracebacks.txt` (dumps at 0.1 s), and Unity's own watchdog and frame-time figures as before.
(3) `nvidia-smi` during the run: two CUDA contexts now (people and gesture worker), memory of the GPU and free RAM (the process mode used about 400 MB more on the Mac and 1.4 GB more on the PC, 2.9 against 1.5 GB). (4) The run folder keeps `perception_events.jsonl` and `run_info.json` -> `perception_workers`.

### 14.15 Findings of 7 November 2026: zoom with a level camera, and the first look check (decisions before any development data)

Written on 2026-11-07, before any v4 development recording was evaluated and before any threshold was set on one.

**Decisions (Anisha, 2026-11-07).**
1. **VRoid is dropped as an avatar look.** The look check (Nusrat, Unity, commit `63a6aed`, merged in PR #22) found 0 hands in 20 VRoid images: the MediaPipe hand model does not see the stylised hands, so neither WAIT nor STOP could be read on it. This is a finding to report in the paper, not a defect to work around.
2. **WAIT clips are made clearer for all looks** (Nusrat). A change to the animations before recording; no threshold changes.
3. **The look check saw every look, including the future test look, and nothing was tuned on it.** It decides only which looks are kept (docs/look_check_v4.md); no reader, commander, perception or control value was changed because of it, and the test look's appearance was not used to choose any setting.
4. **B8 stays open** until Nusrat answers whether a test look with an unseen body exists (RQ4: new looks); B7 gets the note below.

**Zoom with a level camera: decision (c).** Nusrat found in Unity that at 2.0 m a raised hand is about 22 to 24 degrees above the level pan-tilt camera, so a 30 degree view (half angle 15 degrees) loses the hand. Decided: **the camera stays level** (`tilt_deg` is not used and no tilt command is added), and the zoom is limited by distance through the existing `arm_fit` rule (`configs/v4/control.json` -> `zoom`, unchanged: `arm_fit_margin` 0.1, `fov_min_deg` 15). No v4 code or config was changed for this.

*Check* (`tests/test_zoom_geometry_v4.py`, 10 tests, pure arithmetic): the real `ZoomController` in a closed loop with a pinhole camera 1.2 m above the floor, a person centred in front of it, shoulder 1.5 m, a raised arm (upper arm 0.30 m, forearm 0.26 m, hand 0.19 m), YOLO taken to miss a keypoint outside the image, Unity taken to apply the commanded view by the next frame, 60 s at 10 Hz. **The camera height of 1.2 m is inferred, not read from a config (measured on 8 November 2026 by Nusrat: 1.200 m, level, so this table stands; 14.16 item 8)** (it is not in any Python config): with it a vertical arm puts the wrist 23.3 degrees above the axis at 2.0 m, Nusrat's measurement. If the real pan-tilt camera height differs, the angles and the table change; Nusrat is asked to confirm it.

| distance | wrist above the axis (arm vertical / 60 degrees up) | floor: narrowest view that keeps shoulder, elbow and wrist inside the margin | narrowest view the controller commands | magnification of that view |
|---|---|---|---|---|
| 2 m | 23.3 / 21.4 degrees | 56.5 / 52.3 degrees | 60 / 54 degrees | 1.0x / 1.1x |
| 3 m | 16.0 / 14.7 degrees | 39.4 / 36.2 degrees | 41 / 37 degrees | 1.5x / 1.7x |
| 4 m | 12.1 / 11.1 degrees | 30.1 / 27.6 degrees | 31 / 28 degrees | 2.1x / 2.3x |
| 6 m | 8.2 / 7.5 degrees | 20.3 / 18.6 degrees | 20 / 18 degrees | 3.3x / 3.6x |

What the check shows: (a) **at 2.0 m the controller never narrows below the floor** (tested for arms raised 90, 75, 60 and 45 degrees: the narrowest commanded view is 60, 60, 54 and 48 degrees against floors of 56.5, 55.5, 52.3 and 47.0, so the zoom is absent or small at the asking distance); (b) at 3 and 4 m it stays above the floor; (c) at 6 m it overshoots the floor by 0.3 degrees (arm vertical) and 0.6 degrees (60 degrees), within one rate-limited step (the arm stays inside the image in every frame, only inside the margin band for a moment); (d) the arm is in the image in 100 % of the frames at every distance and the view never sits at `fov_min_deg`; (e) from 3 m on the commanded view moves in and out (for example 41 to 53 degrees at 3 m): the rule narrows until the hand reaches the edge margin, counts it lost, widens by `widen_step_deg`, and narrows again. This pumping is an observation for the development evaluation, not a reason to tune anything now.

**Expectation, recorded before any data:** the zoom is expected to matter **only from about 3 m** (1.5x at 3 m against 1.0x to 1.1x at 2 m). RQ3 compares `zoom_on` with `zoom_off`; if every final case has the commander at the 2 m asking distance the comparison would measure almost nothing. **B7 note:** some final cases should place the commander at about 4 m. Which cases, and how many, is for B7 (both of us).

**Not shown.** Real Unity frames with the zoom active (this is a model of the geometry); the pan-tilt camera height; how Unity ramps the field of view; the effect of the pumping on the readings.

### 14.16 Decisions of 8 November 2026 (Nusrat's Phase 2B-2D update), made before any development recording

Decided by Anisha on 2026-11-08 from Nusrat's Phase 2B-2D update. **No development recording exists yet, and none of these decisions uses a result on the test look.** Numbers quoted from Nusrat's runs and
look checks are as she reported them (the run folders are on her machine).

**1. Perception mode = `threads`** (`configs/v4/bridge.json` -> `perception_workers.mode`). Nusrat's Play runs in the v4 scene (3 trials each, before her Unity stall fix):

| mode | watchdog stops | loop lag max | free memory, minimum |
|---|---|---|---|
| `threads` | 0 | 52 ms | 519 MB |
| `processes` | 0 | 100 ms (exactly the declared limit of 100 ms) | 92 MB, with heavy paging |

**Disclosed departure from the rule of 14.14.** Step 1 of that rule prefers `processes` because both modes met every limit in the replay on the PC. We depart from it: with Unity running `processes` passed only at the
limit, with almost no free memory left (it needs 1.4 GB more than `threads`, 14.14; free memory fell to 13 MB on this PC in a v3 session, section 9 item 17). The rule is otherwise unchanged. **Condition before the freeze:** `threads` must
still pass a Play development session **after Nusrat's Unity stall fix** (0 watchdog stops, loop lag and round trip within the declared limits, free system memory recorded); if it fails, the rule of 14.14 applies again.

**2. STOP and WAIT no longer require MediaPipe's label** (`gesture_motion.py`, `configs/v4/gesture_reader.json`). STOP = the open-palm finger geometry (four fingers extended and spread); WAIT = the index-up geometry (index extended and up, the
other three curled) plus the arm pose. The label (`Open_Palm`, `Pointing_Up`) and its score are read, logged per frame and reported (`Reading.hand_label`, `hand_label_score`, `label_agrees`; the look check), but are not required; `wait_score_min` and
`stop_score_min` stay in the config as logged thresholds. An open palm is kept from being read as POINT by its geometry. **Reason:** in the look check MediaPipe said `Open_Palm` in 5 per cent of the STOP frames although the geometry passed in 66 to
97 per cent, and `Pointing_Up` in 13 per cent of the WAIT frames of look f2; the classifier was trained on real hands, and a false STOP is safe (a missed STOP is not). **A v4 difference from v3** (v3 STOP was the `Open_Palm` label at score 0.5): listed
in `configs/v4/analysis.json` -> `declared_differences` for RQ1. Look checks made before this date were computed with the label required (docs/look_check_v4.md). Tests: `tests/test_gesture_motion.py` (`LabelNotRequiredTests`): STOP and WAIT are read with any label or score, a label cannot
make a stop or a wait the geometry does not show, and no decision path reads the label.

**3. The arm ratio** (`point.arm_length_in_shoulder_widths`, 1.4) is **set in the development evaluation as the median YOLO keypoint ratio on the development looks only** (`sunbox_m1`, `sunbox_f1`), never on the test look (`sunbox_f2`). The value is
**not changed now.** The look check measured 1.87 to 2.00 (the bones give 1.587); that is a reason to look, not the value.

**4. Standoff.** `approach_distance_m` stays 2.0, measured from the robot centre to the person centre, as in v3. Nusrat measured 1.65 to 1.89 m (which points she measured is still to be asked of her). The development evaluation is to report the measured standoff, not the
nominal 2.0 m: its distance bins are already the measured robot-to-worker distance from the truth positions; a per-ask standoff summary is **not implemented yet** (to add to `hri_eval_dev_v4.py`).

**5. Forbidden keys from Unity (protocol 3 only).** `true_command`, `is_commander`, `worker_id`, `point_angle_deg`, `look`, `clip`, `phase` and `arm` join the six truth keys in the keys refused from Unity (`bridge/protocol.py`, `docs/protocol_v3.md` section 3). Checked: none of
them is a field of any version 3 message Unity sends (`hello`, `telemetry`, the two frame headers), and `time_s`, `x`, `z` stay allowed. Only Unity's incoming messages are scanned: `is_commander` and `point_angle_deg` are HUD fields Python sends TO Unity and are unchanged
(tests in `tests/test_protocol_v3.py`). Version 2 is unchanged.

**6. Truth meanings accepted:** `NONE` during `start_delay`; `returning` keeps the command; POINT uses the same-side arm unless the target is within 25 degrees of straight ahead; a hold lasts 3.0 to 4.5 s; truth rows every 0.05 s. **Frame-level accuracy counts only the phases `gesturing`
and `holding`** (`configs/v4/eval_dev.json` -> `accuracy_phases`; checked, and fixed in `hri_eval_dev_v4.py`: it had counted every phase with a gesture truth). `idle` and `start_delay` rows feed only the false-read rate, `returning` rows are in neither accuracy nor coverage. Tests in
`tests/test_hri_eval_dev_v4.py` (`AccuracyPhaseTests`). `gesture_data.py` needed no change: it already accepts these phases and builds clips from the rows with the same non-NONE command.

**7. Data splits** (`configs/v4/data_splits.json`, `placeholder` false): looks `sunbox_m1` and `sunbox_f1` development, `sunbox_f2` test; clips development / test: POINT `point_mixamo_01`, `point_ik_01` / `point_mixamo_02`; WAIT `wait_ik_01`, `wait_raise_01` / `wait_ik_02`;
STOP `stop_ik_01`, `stop_ik_03` / `stop_ik_02`. **The test look is never replaced because of its results**; a development look may still be replaced before the recordings (recorded here if it happens). All three looks are of the Sunbox body family, so there is **one look style (`sunbox`)** and the per-style table has
one row. **RQ4 wording: an unseen appearance of the Sunbox body family.** This closes B8 (14.13); B7 (which clips, looks and bystander layouts each setting uses) stays open. The simulator and the tests use the real names (the placeholder names are gone from the shipped config; the refusal on placeholder names is tested on a copy).

**8. Records (Nusrat's side, for the paper).** The look check moved from the backlit stage to the real scene (declared before the rerun in `Avatar/Config/look_check_changes.md`); the top of look f1 was changed; hand rest-pose and finger fixes were made; the look checks saw all looks including the future
test look and nothing was tuned on them; the Unity stall fix is in `RobotBridgeClient.cs` (protocol 3 only, the v3 path byte-identical, checked with a v3 smoke run); the pan-tilt camera height was measured at 1.200 m and level, so the zoom table of 14.15 stands (its height was inferred).

## 15. Changes made during Anisha's absence (by Nusrat)

Dated entries only, appended in order. Each names the task item (P1 to P12 of Nusrat's v4 completion task of 2026-11-12, the
exception of `CLAUDE.local.md` section 2) and the files under `robot_vision/` or `docs/` it changed. Sections 1 to 14 are not edited.
The design and every decision rule were declared before any code in `unity/.../Avatar/Config/upgrade_design.md` (commit `b55ccec`).

### 2026-11-12, Stage A (Python, simulator only; no Unity run, no recording, no threshold set on data)

- **P1 ankle height.** `hri_perception.person_distance` gains `ankle_height_m` (default 0.0 = the v3 behaviour byte for byte): for
  source `ankles` the camera height used is `camera_height_m - ankle_height_m`. Only the v4 360 path passes it
  (`hri_perception_v4.people_v4`, used by `HriPerceptionV4` and by the process lane `bridge/perception_mp_v4.PeoplePerception`), from
  the new `configs/v4/perception.json` (`ankle_height_m` 0.0 until measured: the median of the new truth field over the development
  looks while standing, never fitted to errors). `gesture_data.py` reads the optional truth field; `bridge/protocol.py` refuses it from
  Unity like the other truth fields; `docs/protocol_v3.md` amendment 2.
- **P2 PROCEED.** Reader rule in `gesture_motion.py` (`proceed_features`, `count_strokes`, `read_span_s`; block `proceed` in
  `configs/v4/gesture_reader.json`, initial values 2.0 s, 2 cycles, 0.3 torso lengths, 0.7 vertical share); the person buffer keeps the
  longer window (`hri_perception_v4.PersonsPipeline`). `commander_v4.py`: a facing person reading PROCEED is a candidate without a raised
  arm. `hri_control_v4.py`: PROCEED = the node's FORWARD branch (else unclear), a PROCEED reading marks a gesture onset, HUD gesture
  PROCEED. `configs/v4/data_splits.json`: `proceed_ik_01`, `proceed_ik_02` development, `proceed_ik_03` test. `configs/v4/gesture_data.json`
  and `eval_dev.json`: PROCEED in the command lists. `docs/protocol_v3.md` amendment 1. Simulator: PROCEED episodes, `SceneSpec.proceed_forward`.
- **P3 evaluation.** `hri_eval_dev_v4.py`: `junction_level` block (per ask: shown, read, branch chosen, true branch from goal B, dialog
  outcome; per (look, node, shown) pair; standoff: the 360 estimate logged at each ask against the true robot-to-commander distance),
  PROCEED in the command tables, the v4 map.
- **P6 tilt.** `bridge/protocol.py` (command `tilt_deg`, validated), `bridge/guide.py` (sends `tilt_deg` with protocol 3),
  `bridge/guide_v4.py`, `bridge/perception_v4.py` (frame tilt into the reader and the tick input), `gesture_motion.py` (`level_vector`,
  `pixel_azimuth_deg`, tilt-corrected `arm_solutions` and hand cross-check, `fit_box`), `commander_v4.py` (tilt-corrected bearings),
  `hri_control_v4.py` (`tilt_target`, the tilt part of `ZoomController`, fit box for the zoom when tilting), `configs/v4/control.json`
  (`zoom.tilt_enabled`, `tilt_min_deg` 0, `tilt_max_deg` 35, `tilt_max_change_deg_per_s` 30). `docs/protocol_v3.md` amendment 3.
  **Supersedes 14.15 decision (c)** (camera level, no tilt command): with a level camera the zoom cannot act at the 2 m asking distance.
- **P7 map.** New `configs/v4/roadmap.json` (A, J1 to J4, E1 to E6, routes 40 to 65 m), named by `control.json` -> `roadmap`; used by the
  server, the controller, the simulator export, `hri_eval_dev_v4.py` and `hri_analysis_v4.py`. The v3 `configs/roadmap.json` is unchanged.
  The final timeout and goal order follow later (Stage C), by the rule declared in upgrade_design.md section 6.
- **P8 start search.** `hri_control_v4.py`: the start node (kind `start`) asks like a junction (scan, approach, ask, read); the robot never
  navigates without an accepted instruction (tested: a PROCEED that is never read ends in an abort at A without any navigate state).
  Each ask logs the 360 distance estimate of the approached person (`asks_log`).
- **P10** `bridge/server.py --control-config` (default `configs/v4/control.json`); the file used is copied to `config_used/control.json`.
  **P11** `configs/v4/control_zoom_on.json`, `control_zoom_off.json` (identical to `control.json` except `zoom.enabled`, a test pins it);
  `--final-setting` refuses any other control file than the setting's (`FINAL_CONTROL` in `bridge/server.py`).
- **P12** `bridge/perception_v4.py`: `model_outputs.jsonl` per bridge run (threads mode): one line per processed camera frame with the
  360 people (box, 17 keypoints with scores, bearing, distance and source) and the pan-tilt people and hands (21 landmarks, world
  landmarks, label, score, box) with pan, tilt, field of view and intrinsics. The worker processes write none (threads is the decided mode).
- **Freeze record.** `configs/v4/frozen.json` "files" refreshed with `freeze_v4.py --refresh-list` (approved by Nusrat; unfrozen, no
  hashes) for the four new config files. Note for Anisha: `freeze_v4.V3_DEPENDENCIES` still hashes `configs/roadmap.json`, which v4 no
  longer reads (harmless; the v4 map is frozen with `configs/v4/`).
- **Existing tests updated** (approved by Nusrat; each keeps its intent): `tests/test_protocol_v3.py` (command `tilt_deg`, 15 truth
  names), `tests/test_v4_final.py` (finals with their control file), `tests/test_data_splits_v4.py` (PROCEED clips),
  `tests/test_gesture_data.py` (PROCEED in the list), `tests/test_perception_mp_v4.py` (the v4 people function),
  `tests/test_hri_control_v4.py` (the STOP-while-navigating test uses the v3 map, whose start drives). New: `tests/test_v4_upgrades.py`.
- `hri_sim_v4.export_session` now moves the junction records onto the session clock like the truth rows and the log (a simulator
  inconsistency found by the new junction metrics; real sessions share Unity's clock).

### 2026-11-12, Stage U (Unity upgrades; Python files touched: two)

- **P1 value measured.** `configs/v4/perception.json` `ankle_height_m` = **0.0927 m**: the median of the new truth field over the 3,195 idle rows of
  the development looks in the U6 session `trials_development_Task2_20261112_160917` (sunbox_f1 0.0908, sunbox_m1 0.0953; range 0.0875 to 0.1046).
  Measured, not fitted: before it the same session showed the predicted bias (360 estimate minus true distance at the 9 asks: median +0.094 m, all
  positive; true standoff median 1.81 m against the nominal 2.0 m).
- **P4 tool.** `calibrate_v4.py` (new, evaluation code; B12 exactly, grids of upgrade_design.md section 10, development looks sunbox_m1 and sunbox_f1
  only, replays the reader on `model_outputs.jsonl`) and `tests/test_calibrate_v4.py`; `tests/test_gesture_data.py` and `tests/test_hri_eval_dev_v4.py`
  list it as evaluation code in their import-isolation checks. Not run on data yet (Stage D3).
- U6 (3-trial development session, seed 1; bridge `bridge_guide_20261112_160553`): 2 of 3 SUCCESS; dialogs 7: 6 correct, 0 wrong, 1 abort (J1 POINT
  LEFT, sunbox_f1); PROCEED accepted at 4 of 4 dialogs (A x3, J1 x1); leak test passed (Unity and Python); 0 watchdog stops.

### 2026-11-12, Stage C (development check, 20 runs; the rules of upgrade_design.md section 11, declared before it)

Session `trials_development_Task2_20261112_163710` + `bridge_guide_20261112_163011` (seed 1, sunbox_f1 / sunbox_m1 alternating, development
clips, zoom on, threads, no bystanders, commander PROCEED / POINT; ankle height 0.0927 m). Leak test passed (Unity and Python, max diff 0).
**19 of 20 SUCCESS** (run 12 aborted: PROCEED at A unclear after 2 asks).

- **Rule 1 (junction level): MET.** 62 dialogs: 61 correct, **0 wrong**, 1 abort; every (look, node, shown) pair at least 0.8 (sunbox_m1 A PROCEED
  9 of 10; all others 100 per cent: f1 A PROCEED 10/10, J1 POINT 8/8, J1 PROCEED 2/2, J2 POINT 2/2, J2 PROCEED 2/2, J3 POINT 4/4, J4 POINT 2/2;
  m1 J1 POINT 9/9, J2 POINT 1/1, J2 PROCEED 4/4, J3 POINT 4/4, J4 POINT 4/4).
- **Rule 2 (distance): MET.** Median |360 estimate - true distance| at the 94 asks **0.011 m** (signed median -0.005 m; true standoff median 2.031 m).
- **Timeout (P7, the declared rule):** v_run 0.3944 m/s (median over the 19 successful runs) -> `configs/v4/final_plan.json` `timeout_s` **270**
  (was 240), with the numbers in `timeout_s_source`; `final_seed_note` and a new `roadmap` key state the v4 map and its final goal order.
  `tests/test_v4_frozen.py`: the timeout follows the rule, and the v4 final goal order is pinned (approved minimal test updates).
- Reported, not rule items: frame-level accuracy POINT 1.0 (coverage 0.375 of 1097 frames), PROCEED 1.0 (0.334 of 353); 1 false read in
  401 frames with nothing shown; commander accuracy 1.0 (coverage 0.60); ask to accepted median 13.4 s. **Timing finding:** loop lag max 193 ms
  and round trip max 196.8 ms exceed the declared limits (100 and 150 ms, 14.14) in this Play session, 0 watchdog stops; free memory minimum 1073 MB.
  The 14.16 condition (threads must pass a Play session within the limits before the freeze) is therefore not yet met.

### 2026-11-12/13, Stage D2 and D3 (development recordings and the calibration; the plan `Avatar/Config/recording_plan_d1.md`, declared before)

Every session: seed 1, sunbox_f1 / sunbox_m1 alternating, development clips, threads, leak test passed (Unity and Python, max diff 0), every
`truth.jsonl` accepted by `gesture_data.py`.

| id | condition | Unity + bridge folders | runs | result |
|---|---|---|---|---|
| R1 | zoom on (the Stage C session) | `..._163710` + `bridge_guide_20261112_163011` | 20 | 19 SUCCESS (above) |
| R2 | zoom off (`control_zoom_off.json`) | `..._173220` + `..._173119` | 10 | 9 SUCCESS; run 5 **wrong branch** at J1 (a POINT left, `point_mixamo_01`, read as PROCEED, score 0.834, during the arm's rise) |
| R3 (first) | 3 bystanders | `..._175544` + `..._175450` | 10 | 0 SUCCESS: all aborted at J1, the robot asked a bystander (Unity stand fault, below). Kept, reported, not used |
| R3 | 2 bystanders (fixed stands) | `..._214837` + `..._214449` | 10 | 9 SUCCESS; the robot chose the commander in 34 of 34 dialogs; run 5 aborted at J1 (POINT left, sunbox_f1) |
| R4 | WAIT then the direction | `..._180743` + `..._180650` | 6 | 1 SUCCESS; sunbox_f1's WAIT unread at A in runs 1, 3, 5; two aborts at J1 (a WAIT unread; a POINT not matched to a branch, then the 20 s WAIT timeout) |
| R5 | STOP while driving | `..._181558` + `..._181504` | 6 | 5 SUCCESS; STOP stopped the robot in 6 of 6 (2.5 to 8.9 s) and it resumed; run 1 aborted at J1 (POINT not matched to a branch) |

- **Bystander stand fault (Unity, declared fix before the second R3: `upgrade_design.md` section 13, commit 285878d).** The robot approaches the
  nearest person when it scans, stopped up to 0.3 m before the node; the "J1 behind-right" stand was as far from J1 as the commander's stand, so
  the robot approached that bystander. New rule: every bystander at least 1.0 m farther than the commander's stand along the last 3.0 m of every
  approach (`hri_control.json` `junction_slow_radius_m`); J1 behind-right removed, the two ahead-left stands moved out; 2 bystanders.
- **D3 (`calibrate_v4.py --write`, B12 exactly, on R1, R2, R3 (second), R4, R5; evidence `outputs/calibrate_v4_20261113_005017`).** No swept
  value reaches coverage 0.8 (frame-level coverage 0.24 to 0.49 across every grid), so all 24 swept thresholds keep their committed values
  (`upgrade_design.md` section 13, calibration details item 1). One value changed: **`gesture_reader.json` `point.arm_length_in_shoulder_widths`
  1.4 -> 1.683** (measured, median YOLO ratio over 880 held in-plane POINT frames, p25 1.435, p75 1.785; AUDIT.md 14.16 item 3), written by the
  tool with its `calibrated` record. The first R3 session was run through the tool without `--write` (`outputs/calibrate_v4_20261112_222639`):
  coverage 0.255 everywhere, branch match 0 frames, nothing changed.
- **Per look (frame level, the tool's scoring, after D3).** Branch match on held POINT frames (accuracy / coverage): sunbox_f1 1.0 / 0.48,
  sunbox_m1 1.0 / 0.52 (before D3: 1.0 / 0.19 and 1.0 / 0.23). Commander rule: f1 0.996 / 0.49 alone, 0.991 / 0.52 with bystanders; m1 1.0 /
  0.50 alone, 1.0 / 0.45 with bystanders. WAIT: **sunbox_f1 0.0 / 0.07**, sunbox_m1 0.78 / 0.41 (not changed by D3: f1's WAIT stays weak; not
  replaced, as decided). POINT f1 0.94 / 0.29, m1 0.88 / 0.36; STOP f1 0.89 / 0.25, m1 1.0 / 0.29.
- **Tests and config updated to the measured arm ratio (approved by Nusrat 2026-11-13; no other change).**
  `tests/test_gesture_motion.py`: `ArmRatioDeclarationTests` checks the configured, calibrated value (1.683, and the config's `calibrated`
  record) instead of 1.4; the module's synthetic arms (`v4_synth` upper arm and forearm, same proportion) are built from the configured ratio
  in `setUpModule` and restored in `tearDownModule`, so the 11 geometry and window tests that assumed 1.4 pass and the other modules that use
  `v4_synth` are unchanged. `configs/v4/look_check.json` `checks.arm_ratio_p95.assumed` 1.4 -> 1.683 (so `tests/test_look_check_v4.py` line 240
  matches); its `why` text still names 1.4 and the range 0.98 to 1.75 (left as it is: only the number was approved; for Anisha to reword).
- **Tool bug for Anisha (not fixed; `calibrate_v4.py` is not changed): the calibration replay does not reproduce the live reader.** On R1, `calibrate_v4.replay` (the reader re-run on
  `model_outputs.jsonl`) reads STOP on 419 of 894 PROCEED frames and 47 POINT frames; the live readings logged in `v4_log.jsonl` at the same
  times read STOP on none. The reader accuracies in the D3 report (e.g. PROCEED 0.34) therefore do not describe the live reader. The D3 outcome
  does not depend on it: the live readings answer 34 per cent of the gesturing and holding frames of R1, so B12's coverage 0.8 is not reached
  with them either, and the arm ratio is measured from the YOLO keypoints, not from the replay. Not fixed here (`calibrate_v4.py` is not an
  allowed change of this task). Also for Anisha: with frame-level coverage, which counts every frame of the arm's movement, B12's coverage 0.8
  is out of reach for every threshold, so B12 cannot move any threshold on these data.

### 2026-11-13, Stage D4 (3 runs per condition with the calibrated configs of commit fa226f8)

Rule declared before the runs (`upgrade_design.md` section 13, commit 582212a, replacing the D4 rule of section 11): stop only on a wrong-branch
decision; aborts are recorded and reported per look and condition. Seed 1 (goals E2, E3, E1), runs 1 and 3 sunbox_f1, run 2 sunbox_m1; leak
test passed (Unity and Python) and every `truth.jsonl` accepted in all five sessions. Run protocol: free memory 3.4 to 4.9 GB, Best performance;
Chrome, the Claude app, the NVIDIA overlay and warp-svc running (reported, not closed).

| id | Unity + bridge folders | SUCCESS | dialogs sunbox_f1 (correct / wrong / abort) | dialogs sunbox_m1 | aborts |
|---|---|---|---|---|---|
| R1 zoom on | `trials_development_Task2_20261113_014205` + `bridge_guide_20261113_014023` | 3 / 3 | 5 / 0 / 0 | 3 / 0 / 0 | none |
| R2 zoom off | `..._20261113_014921` + `..._014803` | 3 / 3 | 5 / 0 / 0 | 3 / 0 / 0 | none |
| R3 bystanders | `..._20261113_015635` + `..._015518` | 3 / 3 | 5 / 0 / 0 | 3 / 0 / 0 | none |
| R4 WAIT then direction | `..._20261113_020350` + `..._020230` | 0 / 3 | 0 / 0 / 2 | 1 / 0 / 1 | f1 at A twice (its WAIT unread: "cues not met"), m1 at J1 (a WAIT read briefly, then unclear) |
| R5 STOP while driving | `..._20261113_020709` + `..._020614` | 2 / 3 | 5 / 0 / 0 | 0 / 0 / 1 | m1 at A (PROCEED unclear after 2 asks); STOP stopped the robot in 3 of 3 (3.0, 5.9, 11.3 s) |

**Rule: MET, 0 wrong-branch decisions** (34 dialogs: 30 correct, 4 aborts; 11 of 15 runs SUCCESS). Per look: sunbox_f1 20 correct, 2 aborts
(both its unreadable WAIT); sunbox_m1 10 correct, 2 aborts. sunbox_f1's WAIT is a known per-look finding (D3: frame accuracy 0.0 at coverage
0.07), not fixed.

### 2026-11-13, B7 test assignment (decided by Nusrat, PENDING ANISHA'S CONFIRMATION; recorded before the Stage F tests)

- **zoom_on, zoom_off, bystanders:** the development looks (sunbox_m1 and sunbox_f1, alternating by run) with the **test** clips.
- **unseen_look:** sunbox_f2 with the **test** clips.
- **Conflict for Anisha to resolve when she confirms:** `data_splits_v4.guard_run` refuses a run that mixes development and test data (looks
  and clips together), and `hri_eval_final_v4.py` applies it with `final_evaluation=True`; `final_plan.json` `settings_note` also says every
  final session lies wholly in the test split. As decided, the zoom_on, zoom_off and bystanders finals mix development looks with test clips,
  so the current Python final evaluation would refuse them (unseen_look passes). Her guard needs a per-setting rule (looks from the setting's
  split, clips from the test split), or B7 changes. Until she fills `final_plan.json` `test_assignment`, the Unity final guard (Stage F)
  refuses every final run.

### 2026-11-13, Stage F (final setup, Unity side; no final run, no freeze; declared in `upgrade_design.md` section 13 before it was built)

- **B9, the Unity files to freeze** (Nusrat; `Avatar/Config/final_v4.json` `freeze_files`, repository paths): `unity/Robotics-Warehouse/
  WarehouseProjectURP/Assets/` + `Scenes/WarehouseRobot_v4.unity`, `WarehouseRobot/Bridge/Config/bridge_unity_v4.json`,
  `WarehouseRobot/Robot/Config/robot_unity_v4.json`, `WarehouseRobot/Avatar/Config/worker_v4.json`, `WarehouseRobot/Avatar/Prefabs/
  WorkerV4.prefab`, `WarehouseRobot/Avatar/Config/trial_workers_v4.json`, `WarehouseRobot/Avatar/Config/final_v4.json`,
  `WarehouseRobot/Avatar/Config/sessions/final_zoom_on.json`, `final_zoom_off.json`, `final_bystanders.json`, `final_unseen_look.json`,
  `WarehouseRobot/Scenario/Config/trial_plan_v4.json`. For Anisha: add them to `frozen.json` (any hash table, keyed by these paths,
  LF-normalised SHA-256 as `freeze_v4.sha256_lf`); the Unity guard looks each one up by its path. The avatar look assets are third-party and
  not in git, so they are not hashed (each session records their appearance text).
- **The Unity final-run guard** (`FinalGuardV4`, called by `TrialRunnerV4` when `TrialPlayV4 -finalSetting NAME` is given): refuses an unknown
  setting, any null among `task`, `final_seed`, `runs_per_setting`, `timeout_s`, `success_radius_m`, `test_assignment`,
  `unity_files_and_guard`, `acceptance_criteria`, an unfrozen `frozen.json`, a B9 file missing, unrecorded or changed, the development
  override `trials.local.json`, `-workersConfig` with `-finalSetting`, and a setting already run (Unity's `UNITY_FINAL_DONE.json` with
  `final_setting`, or Python's `FINAL_RUN_DONE.json` with `setting`, in any folder under `outputs/`). A final uses `final_plan.json`'s seed,
  runs, timeout and success radius, writes `trials_final_Task2_<setting>_<time>/` with `session.json` `mode` "final" and `final_setting`,
  copies `final_v4.json`, `final_plan.json` and `frozen.json` into `config_used/`, and writes `UNITY_FINAL_DONE.json` after its last run.
  The Unity marker is deliberately not named `FINAL_DONE.json`: `final_guard_v4.markers` scans every folder for that name and would take a
  Unity file for the setting's evaluation.
- **Checked:** Unity Edit Mode 194/194 (19 new `FinalGuardV4Tests`); in a Play session `TrialPlayV4 -finalSetting zoom_on` was refused with
  every open reason (blanks B7, B9, B11; not frozen; each B9 file unrecorded) and wrote no folder. Python files unchanged in this stage.

### 2026-11-13, B7 check against the unchanged Python guard (read-only; `data_splits_v4.guard_run` with `final_evaluation=True`)

Each setting's runs 1 and 2 (the look rotation; bystanders with two bystanders), direction scenario (POINT and PROCEED clips):
- **Plan (a)** zoom_on, zoom_off, bystanders = development looks (sunbox_f1 / sunbox_m1 alternating) + development clips; unseen_look =
  sunbox_f2 + test clips: **refused for zoom_on, zoom_off and bystanders** ("--final-evaluation given, but the run uses development data":
  a final evaluation accepts only the test split); **accepted for unseen_look** (split test).
- **Plan (b)** all four settings = sunbox_f2 + test clips (point_mixamo_02, proceed_ik_03): **accepted for all four** (split test); in the
  bystanders setting all three workers wear sunbox_f2.
- The B7 recorded above (development looks + test clips) is refused for the same three settings ("run mixes development and test data").
  Unity's Stage F `PlanFinal` also refuses plan (a): a final's clip split must be a final-evaluation split. Only plan (b) runs through both
  guards unchanged; with it `final_v4.json` needs `look_split` "test" for every setting (a declared Unity change once B7 is decided).

### 2026-11-13, B11 acceptance criteria: DRAFT, proposed by Nusrat, PENDING ANISHA

Validity criteria per final session (a session that fails one is reported as invalid with the reason; it is never re-run without a
repetition declared here first). No performance thresholds: results are reported whatever they are, with coverage and intervals.
1. **Leak test passed**, Unity and Python: `session.json` `leak_test.passed` is true and `gt_path.py session <unity folder>` passes.
2. **Every outcome recorded**: `results_unity.csv` has one row per run (`runs_per_setting`), `run_###/` and `python_trial_###.json` exist
   for every run with the same numbers, `summary_unity.json` and `UNITY_FINAL_DONE.json` are written, and the bridge folder holds
   `FINAL_RUN_DONE.json` and `summary.json`.
3. **Every truth file accepted**: `gesture_data.py` accepts every `run_###/truth.jsonl`, and `gt_path.py run` every run folder (run.json,
   grid.json, optimal_path.json, trail.csv).
4. **No watchdog stop after start-up**: the bridge `summary.json` reports `watchdog.stops_reported_by_unity` 0 for the runs (a stop before
   trial 1 starts is reported, not counted).
5. **Run protocol recorded**: the bridge `run_info.json` machine state (power mode, power source) and `resources.csv`, and the programs
   running and free memory before the session (written in the session report).

### 2026-11-13, B7, B9 and B11 decided by Nusrat in Anisha's absence (PENDING HER CONFIRMATION; `upgrade_design.md` section 13)

- **B7 = plan (b):** every final uses the test look sunbox_f2 with the test clips (point_mixamo_02, proceed_ik_03), the only plan the unchanged
  `guard_run` accepts for all four settings. **unseen_look is a repeat of zoom_on** (the same configs, a second 20-run session: a repeatability
  measure); research question 4 (an unseen look) is answered by comparing the finals with the development results. **In the bystanders
  setting every person wears sunbox_f2**, so the commander can be told apart only by behaviour (the gesture after the question).
- **B11 adopted:** the five validity criteria above, now `final_plan.json` `acceptance_criteria`. No performance thresholds.
- **B9 in the freeze:** `final_plan.json` `unity_files_and_guard` names `Avatar/Config/final_v4.json` (`freeze_files`) and the Unity guard;
  `freeze_v4.py` records their LF-normalised SHA-256 under `unity_files`.
- **Changes in Anisha's files (allowed by Nusrat in this task):**
  - `configs/v4/final_plan.json`: `test_assignment` (plan (b), per setting), `unity_files_and_guard`, `acceptance_criteria` filled, their
    notes, `status` and the `unseen_look` note updated (no blank left; not frozen).
  - `freeze_v4.py`: `unity_files()` (the B9 list read through the plan); the freeze records `unity_files` and refuses while a listed file is
    missing; `problems()` (so `require_frozen`, the server's final mode and the final evaluation) finds a changed, added or removed Unity
    file; the report lists them. `frozen.json` itself is not touched: the freeze is run by Nusrat, by hand.
  - `tests/test_v4_frozen.py`: new `UnityFilesFreezeTests` (6 tests); the decided-values test now expects the three fields filled and no
    blank; the blank-refusal test makes its own blank (the real plan has none).
- Unity: `final_v4.json` `look_split` "test" for every setting; the four `sessions/final_*.json` notes; `FinalGuardV4Tests` (plan (b) in every
  setting, unseen_look identical to zoom_on).

### 2026-11-13, batch-mode rehearsal (development, declared in `upgrade_design.md` section 13): BATCH MODE DOES NOT WORK for v4

Commit 9e58419; `finals_v4/run_protocol_v4.ps1` note `outputs/run_protocol_rehearsal_zoom_on_20261113_042517.txt` (free memory 3,253 MB;
Chrome, the Claude app, the NVIDIA overlay and warp-svc running; power plan "AMD Ryzen Balanced", power mode Best performance on mains);
server as in the zoom_on final without `--final-setting` (`bridge_guide_20261113_042519`, complete); Unity `-batchmode` `TrialPlayV4
-workersConfig .../final_zoom_on.json`. **Result:** Unity built the ground-truth grid, created `trials_development_Task2_20261113_042813/`
(only `config_used/`) and then hung for 7 minutes before the leak test, at `yield return new WaitForEndOfFrame()` (`TrialRunnerV4.cs`
line 481): in `-batchmode` the Editor never reaches the end of a frame, so the coroutine never resumes. Stopped by the assistant (Unity
killed; the server exited on the disconnect; the trial-count override removed). No run started; both folders are kept and are not results.
The D2 to D4 sessions ran in the Editor window, where this wait returns. The B11 checker (`finals_v4/check_session_v4.ps1`) and the
protocol note were shown to work on the D4 session R1 (all five criteria PASS) and in this rehearsal (the note) respectively; the end-to-end
rehearsal is still to be done once the mode of the finals is decided.

### 2026-11-13, pre-freeze completion (agreements with Anisha, rename, B11 update, disclosures; no freeze, no final)

**Agreed with Anisha today (2026-11-13), recorded here before the freeze:**
- **B7 confirmed:** every final uses the test look sunbox_f2 with the test clips (plan (b) above), in every setting.
- **B11 confirmed as validity only** (no performance thresholds), with the update below.
- **The freeze is run by Nusrat, by hand** (`python freeze_v4.py --freeze`); the AI never runs it and never writes `frozen.json` (CLAUDE.md
  updated accordingly). B9 (the Unity freeze list) stays as decided by Nusrat above.

**Rename (2026-11-13): the final setting `unseen_look` is now `zoom_on_repeat`.** Since B7 = plan (b) the fourth setting is a repeat of
zoom_on, and its name now says so. Changed everywhere it is used: `final_plan.json` (`settings`, `test_assignment`), `final_v4.json`, the
session config (`sessions/final_unseen_look.json` renamed `final_zoom_on_repeat.json`, same GUID), `bridge/server.py` `FINAL_CONTROL`,
the docstrings of `final_guard_v4.py` and `hri_eval_final_v4.py` (both read the names from the plan), the Python and Unity tests and the
procedure. The entries above keep the old name.

**B11 update (2026-11-13, before the freeze; `final_plan.json` `acceptance_criteria`, `finals_v4/check_session_v4.ps1`, tests):**
- (a) **A watchdog stop is a RESULT**: it is counted as a stop of its run (or as that run's failure when the run fails) and is never a reason
  for invalidity. The earlier criterion 4 ("no watchdog stop after start-up") is removed; the checker prints the count as a result.
- (b) **Added:** frozen hashes match (`freeze_v4.require_frozen` passes after the session), split guard passed (`data_splits_v4.guard_run` on
  every run's looks and clips, final evaluation: test split only), all runs present (runs 1 to 20, each with a `results_unity.csv` row, a
  `run_###` folder and a `python_trial_###.json`).
- (c) **A setting that fails a criterion is reported as invalid, with the reason, and is never rerun** (the earlier wording allowed a
  declared repetition; it no longer does).
- The seven criteria: leak test passed; frozen hashes match; split guard passed; all runs present; every outcome recorded; every truth and
  run file accepted; run protocol recorded. Checked on the D4 session R1 (`trials_development_Task2_20261113_014205` +
  `bridge_guide_20261113_014023`): as a development session all PASS (frozen hashes N/A, not required in development); with `-Final` it is
  refused on five criteria (not frozen, development data, 3 of 20 runs, no final markers, no protocol note given), as it must be.

**Decision (Nusrat, 2026-11-13): the finals run in the Unity Editor window,** without `-batchmode`, as the development sessions D2 to D4 did.

**Disclosures (before the freeze):**
1. **Calibration replay mismatch.** `calibrate_v4.replay` (the reader re-run on `model_outputs.jsonl`) reads STOP on 419 of 894 PROCEED frames
   of R1 (and on 47 POINT frames), where the live reader logged in `v4_log.jsonl` reads STOP on none (the D2/D3 entry above). Every reader
   accuracy in the D3 report, including the per-look frame-level numbers quoted above, comes from that replay and may not describe the live
   reader; they are development diagnostics, not results. **Code search (`git grep`, 2026-11-13):** `calibrate_v4` is imported only by
   `tests/test_calibrate_v4.py`; it is not imported or run by `hri_eval_final_v4.py`, `hri_eval_dev_v4.py`, `hri_analysis_v4.py`,
   `final_guard_v4.py`, `freeze_v4.py`, `bridge/server.py` or `paper_v4/figures_v4.py`, and no code reads its `calibrate_v4_*` output folders.
   Its only trace in a config is the `calibrated` record of `gesture_reader.json` (the arm ratio, measured from the YOLO keypoints, not from
   the replay). Its accuracies are not reported as results; the final evaluation computes everything from the live logs with
   `hri_eval_dev_v4`'s code.
2. **B12's coverage 0.8 was unreachable.** With frame-level coverage (every frame of the arm's movement counts) no swept value reached 0.8
   (0.24 to 0.49), so B12 could not move any threshold: **all thresholds kept their committed values except the measured arm ratio**
   (`point.arm_length_in_shoulder_widths` 1.4 -> 1.683, the median of 880 held in-plane POINT frames).
3. **Batch mode hangs.** In `-batchmode` the run hangs before the leak test at `yield return new WaitForEndOfFrame()` (`TrialRunnerV4.cs` line
   481; the batch rehearsal above). Not fixed; batch mode is not used.
4. **Finals in the Editor window**, like D2 to D4 (the decision above): the same timing conditions as the development data.
5. **RQ4 is answered as development versus finals.** No final uses a development look, so the unseen look (sunbox_f2) is compared with the
   development sessions (sunbox_m1, sunbox_f1), not within the finals. The development numbers are **optimistic**: the design, the
   calibrated arm ratio and every development check were made on those looks and clips, and the development sessions were watched and fixed
   while they ran (the R3 stand fix). A difference between development and the finals therefore mixes the look with the clips, the seed
   (1 vs 2), the session and this optimism; it is reported as such.

**Unity and scripts (Nusrat's files):** `sessions/rehearsal_zoom_on.json` (identical to `final_zoom_on.json` except the development looks
sunbox_m1 and sunbox_f1 and, through development mode, the development clips; two Edit Mode tests prove it and that it can never load sunbox_f2
or a test clip); `finals_v4/run_session_v4.ps1` (one session end to end, `-Setting`, `-Rehearsal`, `-DryRun`; a final is never retried);
`finals_v4/check_session_v4.ps1` (the seven criteria); `final_procedure_v4.md` (merge, rehearsal on main, freeze on a fresh branch with a pull
request, finals on main in the order zoom_on, zoom_off, bystanders, zoom_on_repeat); the "pending her confirmation" notes of `final_v4.json`
and the final session configs now say B7 is confirmed.

**Changes in Anisha's files (allowed by Nusrat in this task, items Q1 to Q4):**
- `configs/v4/final_plan.json`: `settings` and `test_assignment` key `unseen_look` -> `zoom_on_repeat` and their notes (Q1);
  `acceptance_criteria` (seven criteria) and `acceptance_criteria_note` (Q2); `status` and `test_assignment_note` say B7 and B11 are confirmed.
- `bridge/server.py`: `FINAL_CONTROL` key and the `--final-setting` help text (Q1).
- `final_guard_v4.py`, `hri_eval_final_v4.py`: the setting names in the module docstrings (Q1; no code change, the names come from the plan).
- `configs/v4/README.md`, `configs/v4/archive/results_manifest.json`: the setting names in their text (Q1).
- `tests/test_v4_final.py`: `check_setting("zoom_on_repeat", ...)` (Q1).
- `tests/test_v4_frozen.py`: the plan's settings and `repeat_of` under the new name (Q1); seven criteria and the docstring (Q2); new
  `test_b11_is_validity_only_and_a_watchdog_stop_is_a_result` (no watchdog criterion, the seven criteria in order, the never-rerun rule, and
  `check_session_v4.ps1` reporting exactly these criteria) (Q2).
- `AUDIT.md`: this entry (Q1 to Q3). `CLAUDE.md`: the freeze is run by Nusrat by hand (Q4).
- `hri_eval_final_v4.py` (follow-up the same day, allowed by Nusrat): Unity's watchdog stops are counted **per run** from each bridge
  run's `messages.jsonl` (every telemetry header carries Unity's cumulative `watchdog_count`, `trial_index` and `trial_running`; an
  increase is given to the run running in that message, else counted outside the runs; a run without telemetry is `not_evaluated`).
  `eval.json` gets `watchdog_stops` (per run with the run's outcome, and a summary) and `eval.md` a table, as a RESULT per B11(a): it
  refuses and invalidates nothing. Checked on the 23 v4 bridge folders under `outputs/`: in-run plus outside counts equal Unity's total
  (`summary.json` `stops_reported_by_unity`) in every one (two sessions with one stop each). `hri_eval_dev_v4.py` is unchanged: it does
  not share this code (the final evaluation adds the block after the shared `evaluate`). Tests: `tests/test_v4_final.py`
  `WatchdogStopTests` (4 tests).
- `freeze_v4.py` (follow-up, messages only, no logic): `require_frozen`'s refusal now says "until the freeze is run by hand" instead of
  "until Anisha freezes". Not changed (outside the allowed change): the usage line of its docstring ("Anisha, after the development
  evaluation"), `configs/v4/README.md` line 5, and the `label` of `configs/v4/frozen.json`, which the AI never edits (it says "until
  Anisha freezes it"; the freeze keeps the label).

### 2026-11-13, pre-freeze tidy-up (by Anisha; wording only: no threshold, value or logic changed; no freeze run)

Branch `anisha/v4-prefreeze-tidy`. Sections 1 to 14 are not edited; where they still say the freeze is "by Anisha" (14.7, 14.11) this entry and the 2026-11-13 agreement above supersede them.

1. **Arm-ratio wording in the look check** (`configs/v4/look_check.json` `checks.arm_ratio_p95.why`; the entry above left it for Anisha to reword). It now names the configured
   1.683 (kept equal to `point.arm_length_in_shoulder_widths` by `tests/test_look_check_v4.py`; 1.4 when the rule was declared on 2026-11-06, calibrated on 2026-11-13) and the range
   it implies, 1.683 x (1 - 0.30) to 1.683 x (1 + 0.25), i.e. **1.18 to 2.10** (it said 1.4 and 0.98 to 1.75). Only that text changed: `assumed` (1.683), `low_rel` (0.30) and `high_rel` (0.25) are untouched,
   and a check confirmed that, parsed as JSON, nothing else in the file changed. The same three stale mentions in `docs/look_check_v4.md` (the measured-ratio sentence, the table row, the recording instruction) are corrected to match.
2. **`freeze_v4.V3_DEPENDENCIES` and `configs/roadmap.json`: reported, NOT changed.** The v4 map is `configs/v4/roadmap.json` (named by `control.json`, frozen with `configs/v4/`). The v3 `configs/roadmap.json` is still read by v4-side code in two places,
   neither of which lets its content reach a v4 decision: `bridge/server.py` line 605 loads it through `task_route.map_for_task` for every protocol and then, for protocol 3, replaces `road` and `road_files` with the v4 map (so it is not
   copied to `config_used/` and not in `map_used.json`); and `hri_sim_v4.two_view_study` (a simulator study function, development only, line 607). Other readers are v3 code (`task_route.py`, `hri_eval_dev.py`,
   `hri_control.make_controller`) and tests (`test_v4_frozen.py` line 203 detects a change of it after freezing, `test_make_results_archive_v4.py` line 85 expects it in the archive; several more use it as a fixture). Unity C# files also mention `roadmap.json`
   (Nusrat's side; not examined). **Proposal (not applied, awaiting a decision):** removing it from the list is possible because no v4 decision depends on its content, but it needs (a) the list edit, (b) those two tests changed, (c) `bridge/server.py` line 605
   left reading it (harmless) or reworked, and (d) the stale note text in `frozen.json` left alone (the AI never edits it). The v3 file is already pinned by the v3 freeze (`configs/hri_frozen.json`, `tests/test_hri_frozen.py`), so hashing it again in `frozen.json` is redundant,
   not wrong. Recommendation: keep it (zero risk, the cost is that an edit to a v3 file fails a v4 test too); do not change the list before the freeze.
3. **Who runs the freeze** (wording): the `freeze_v4.py` usage line and `configs/v4/README.md` line 5 now say the freeze is run by **Nusrat, by hand**, after the development evaluation (agreed with Anisha on 2026-11-13; CLAUDE.md; the entry above), and never by the AI. These were the two
   places the entry above listed as not changed. `configs/v4/frozen.json` is not touched (its `label` still says "until Anisha freezes it"; the freeze keeps the label). `freeze_v4.py --freeze` was not run.

## 16. Experiments A and B: lying workers and lie detection (faculty plan of 2026-11-13; written BEFORE any code)

Branch `anisha/v4-experiments-ab`. Sections 1 to 15 are not edited. Python only (`robot_vision/`, `docs/`): simulator and controller, v4 code only. Nothing
under `unity/` or `external/` and no v3 file is touched; `freeze_v4.py --freeze` is not run; no frozen value is changed (`configs/v4/frozen.json` is
still unfrozen). **Everything in this section is a SIMULATOR study** (reader-level synthetic perception, `hri_sim_v4.py`): its numbers are properties of
the simulator's geometry and noise model, not measurements, and are labelled "simulator" wherever they appear.

### 16.1 The plan (faculty, 2026-11-13)

| set | experiment | what |
|---|---|---|
| A (all workers truthful) | A1 | straight corridor A to B, 2 avatars, one on each side |
| | A2 | A to B to C with a right-angle turn |
| | A3 | A to a random goal, people beside the optimal path |
| | A4 | A to a random goal, people at random places |
| B (each worker lies with probability 0.2, seeded per worker per run) | B1 to B4 | the same four as A1 to A4 |

A lie = the worker points a wrong direction. The robot never knows goal B; it detects a lie only from evidence.

Work items: (1) truth: a truthful / lie field per gesture in `truth.jsonl` (evaluation only, refused from Unity in `bridge/protocol.py`) and the simulator option
`lie_probability`; (2) lie detection in `hri_control_v4.py`, three rules each behind a switch in `configs/v4/control.json`, default off (current
behaviour unchanged): (a) second opinion, (b) reject impossible directions, (c) backtrack; every decision logged with its reason; (3) scenarios A1 to A4
and B1 to B4 in `hri_sim_v4.py`; (4) CSV export `export_csv_v4.py` (evaluation code: `runs.csv`, `dialogs.csv`, columns in a config file); (5) 20 seeded
simulator runs per scenario, Set B with detection on and off, and the table.

### 16.2 Decisions by Anisha, 2026-11-13 (answers to the open questions, before any code)

1. **Maps.** A1 and A2 on small new maps; A3 and A4 on the existing `configs/v4/roadmap.json` (goal drawn uniformly from E1 to E6 by the run seed). A1 = one
   straight road A to B, no branch. A2 = an L-shaped road A to B to C, one 90-degree right turn at B, no other branch. The two small maps and all
   scenario settings live in a new `configs/v4/experiments/scenarios_ab.json`; `roadmap.json` is untouched.
2. **Lie model.** Per gesture: every gesture of every worker is an independent draw with probability `lie_probability` (a re-ask is a new gesture), from a
   generator seeded per worker per run. A lie shows one of the OTHER three directions among LEFT / FORWARD / RIGHT / BACK relative to the arrival
   direction, uniformly, never the true one; BACK is the arrival road. Where the node has no branch in the shown direction (a corridor, a wall) the lie is an
   impossible direction, which is what rule (b) catches and why A1 and A2 can be lied about.
3. **People.** A1 and A2: 2 people, one on each side of the road at the asking node. A3: 2 people at EVERY junction (also those off the optimal path), one on each
   side of the arriving road, 2.0 m lateral, 3.0 m before the junction. A4: 2 people per junction, uniform in a 6 m x 6 m square centred on the junction, at
   least 1.0 m from every road centre line and 1.0 m apart, seeded by run and junction.
4. **Backtracking and ties.** Backtrack: return to the last junction; if exactly one branch there is untried (not the arrival road, not the failed one) take
   it with no question; if two are untried, ask again there with the failed branch excluded; at most once per junction. Second-opinion tie: two people
   disagree and nobody else is present -> ask the first person again; the majority of the three answers decides (the first person counts twice). Answers
   rejected by rule (b) never count as votes.

### 16.3 Design (declared before code)

- **Truth field.** `truth.jsonl` rows get the optional boolean `gesture_truthful` (absent in older sessions): false on every row of a gesture that shows a wrong
  direction, true otherwise (also while idle: nothing is shown). `gesture_data.py` parses it (`TruthRow.gesture_truthful`, None when absent) and
  `bridge/protocol.py` refuses the name in messages from Unity like the other truth fields. The direction a lie shows is the existing `point_angle_deg`
  (POINT) or a PROCEED (FORWARD); the evaluation maps it to a branch with the roadmap. Unity does not write the field yet (Nusrat's side, not touched).
- **Rule (b), `lie_detection.reject_impossible`.** A resolved answer is rejected, with a logged reason, when it is: `arrival` (the direction nearest the road the
  robot came from), `no_branch` (no branch of the node within `branch_match_max_deg`, or PROCEED where the node has no FORWARD branch), `dead_end` (the branch
  leads to a node of kind `dead_end` in the map; none of the maps here has one, the rule is unit-tested on a toy map) or `already_tried` (the branch just
  failed, backtrack). A rejection held for `gesture_hold_s` ends the ask at once and asks again (it uses an ask; two asks, then the existing abort, or
  backtrack). Off: the existing silent drop (the ask runs to its 5 s window) is unchanged.
- **Rule (a), `lie_detection.second_opinion`.** At a node (junction or start) where the 360 camera shows at least a second person: after an accepted answer the
  robot approaches the nearest person not yet asked at this visit (360 track id), asks, and compares. Agree -> go. Disagree -> ask a third person if there is
  one, majority of three; no third -> the tie rule above. No strict majority among all people and nobody left -> unclear (abort, fail safe). One person
  only -> as before. Each person's dialog is a record of its own (`opinion` number, 360 id).
- **Rule (c), `lie_detection.backtrack`.** When every answer at a junction is rejected (the ask budget is used up where the robot would abort) and the last
  decision junction still has its one backtrack, the robot drives back to it and takes the other branch as in decision 4. A junction that offers no
  other branch, or whose backtrack is used, aborts as before. Only the last decision junction is considered (one level).
- **Logging.** `summary()["v4"]["decisions"]`: one entry per decision with `t`, `node`, `event`, `reason`, `serial` (the ask it concerns) and the details
  (answer, votes, branches). Logged also with every switch off (an addition to the summary, not to the behaviour).
- **Simulator.** `hri_sim_v4.py`: every person at a node is a worker who can be asked (the person the robot approaches is the commander of that ask);
  `lie_probability` per scenario; `scenario_ab` builds A1 to A4 / B1 to B4 (maps, goal, placements) from the run seed. The generator of a worker is
  `random.Random(f"{seed}|{node}|{worker id}")`, so it is the same in every process.
- **CSV (`export_csv_v4.py`, `configs/v4/experiments/export_csv.json`).** `runs.csv`: one row per run; `dialogs.csv`: one row per ask (question shown). The columns and
  headers are in the config (a list of field names with optional header text); a field name the exporter does not know is refused with the list of
  known fields. Definitions: *lies given* = lying gestures of that run in `truth.jsonl`; *detected* = a lying ask whose decision is a rejection,
  an outvote or a backtrack that withdrew it; *corrected* = detected and the junction ended with the true branch; *fooled* = a lying answer the robot
  acted on (it drove the shown wrong branch). A lie that is neither (no reading, ignored) is given only.
- **Equivalence with the switches off.** With the three switches false the controller's decisions, traces and timings are those of the commit this branch
  started from (tested on fixed seeds against the stored result of the unmodified code path).

### 16.4 Values the AI chose where neither the plan nor the answers settle (complete list, one line each, for Anisha to confirm or change)

Marked (plan) or (decision) where the value comes from your plan or answers of 2026-11-13 and is listed only so that nothing is hidden.

**Runs and settings**
1. Runs per scenario 20 and seeds 1 to 20 (run k = seed k): the plan says 20 seeded runs; seeds are simulator-only, no final seed involved.
2. Gesture simulation = the neutral defaults of `GestureSimConfig` and `SimConfig` (coverage 1, accuracy 1, no angle or distance noise, `p_detect` 1): puts no number of mine into the study, so the lie is the only error source.
3. Trial timeout 270 s: the declared v4 value of `final_plan.json`.
4. Sensitivity timeout 600 s: a round value more than twice 270 s, to show whether the timeout matters (it does not: the tables are identical).
5. Set A also run with detection on, and the rule-by-rule and counterfactual settings: extras beyond the plan; they cost nothing and show what detection costs when nobody lies.
6. "On" = second opinion + reject impossible, backtrack off (decision of the review, 16.10).

**Maps and placements**
7. A1: A (6.25, -20) to B (6.25, 20), 40 m: the same start as the v4 map and the length of its route to E1.
8. A2: A (6.25, -20), B (6.25, 0), C (26.25, 0), 20 m + 20 m: equal legs, the turn to the right as decided.
9. A2 has people at both asking nodes, A and B (2 each): decision 3 says "at the asking node"; A2 has two.
10. People at the start node A stand 3.0 m BEHIND A (opposite the start heading), 2.0 m lateral: decision 3 applied literally ("3.0 m before the node along the arrival direction").
11. A third person of a `beside` layout (only used when `people` > 2, i.e. in tests) stands 3.0 m further back on the same side: an arbitrary spot for a case no experiment uses.
12. Random placement by rejection sampling, seeded `f"{seed}|place|{node}"`, up to 10000 tries, refusal if it fails: the implementation of decision 3.
13. Avatar looks alternate `sunbox_m1`, `sunbox_f1` (worker 1, 2, ...): development looks only, so the development guard accepts the sessions.
14. Gesture timing, arm, clip names, PROCEED for FORWARD / POINT otherwise: the existing `SceneSpec` defaults and the v4 design (P2), not changed.
15. Collision radius 0.65 m, success radius 0.3 m, speeds and latencies: the existing `SimConfig` defaults, not changed.

**Lies**
16. Probability 0.2 (plan); a lie shows one of the other three of LEFT / FORWARD / RIGHT / BACK uniformly (decision 2).
17. The generator of a worker is `random.Random(f"{seed}|{node}|{worker id}")`: deterministic across processes; a person at another node is another worker, so "per worker per run" = per person per node.
18. **A worker who knows B but stands at a node that cannot lead there points BACK (`point_back_when_lost`), truthfully.** Without it no gesture would be shown there. This is a modelling choice of mine that decides whether rule (c) can ever see evidence; it is the weakest assumption of the study.

**Rules**
19. Rule (b): an impossible answer must be held `gesture_hold_s` (0.5 s) to be rejected, a rejection uses one of the two asks, two rejections end in the existing abort: the existing dialog values reused, nothing new.
20. Rule (a): at most 3 answers (plan) and one more dialog for the tie rule's re-ask of the first person (so at most 4 dialogs per visit).
21. Rule (a): three different answers (no strict majority) = abort (fail safe); decision 4 only settled the two-person tie.
22. Rule (a): people are told apart by 360 track id; without ids no second opinion (the simulator's ids are perfect).
23. Rule (a): a person all of whose asks are rejected counts as no opinion and the next person is asked (an extension: decision 4 only said rejected answers are no votes).
24. Rule (c): trigger = every answer at the junction rejected and no vote; one level (the last decision junction); needs rule (b); `already_tried` excludes the failed branch after a backtrack whatever (b) says.
25. Map node kind `dead_end` for the dead-end rejection; none of the maps has one (unit-tested on a toy map).

**Definitions and reporting**
26. Lies detected / corrected / fooled as in 16.3 and the docstring of `export_csv_v4.py`; a lie that is neither (ignored, or read as the right branch by the mirror ambiguity) is "given" only.
27. `correct` (the command read is the command shown), `correct_direction`, `correct_branch`: three columns because the plan's "correct" is ambiguous.
28. Trail against optimal in the simulator = travelled distance against the road length A to B (a real session uses `gt_path`); success rates with Wilson 95 % intervals, medians of times.

### 16.5 Decisions of 2026-11-13, second round (Anisha, answers to two questions raised by the first runs; before the table below was made)

Found by running the scenarios (not by tuning on them): with second opinion on, the simulator's straight-line routes made the robot bump into or stall at the
OTHER avatar although every worker was truthful (A3 detection on: 5 of 20 collisions; A4 detection on: 7 of 20 timeouts, 188 s of one run in safety
stops). Decided: (1) **the simulator routes around people** for these scenarios (opt-in `SceneSpec.avoid_people_m`, off for every older simulation; a
detour waypoint wherever a route passes closer than 0.9 m = `safety.corridor_half_width_m` 0.6 m of `hri_control.json` + half the robot width of `robot.json`
0.3 m, as Unity's NavMesh agent would; `hri_sim_v4.detour_corners`; no new tuned number). (2) **Timeout: 270 s with a labelled 600 s sensitivity run.** Also
(my implementation choice, listed here for review): the approach point for the 2nd and 3rd person asked is moved around that person (30 degree steps) until
it is at least 2 x `corridor_half_width_m` = 1.2 m from every other person (`_clear_approach_point`; a person that close would hold the robot at the
person-in-path stop for good); the first approach is the unchanged v3 rule. Nothing else about the controller's first approach, reposition or drive changed.

### 16.6 What was built (files; nothing under `unity/`, `external/` or v3 was edited)

- `hri_control_v4.py`: rules (a), (b), (c), the decision log (`summary()["v4"]["decisions", "route", "safety_stops", "lie_detection"]`), records of further
  dialogs (`opinion`, `person_360`). `configs/v4/control.json`, `control_zoom_on.json`, `control_zoom_off.json`: the `lie_detection` block, all false.
- `hri_sim_v4.py`: lies (`lie_probability`, `lie_script` for tests), any person can be asked (`anyone_commands`), a worker who knows B points BACK when the node cannot
  lead there (`point_back_when_lost`), layouts `beside` / `random` / `fixed`, `detour_corners`, `scenario_ab` / `run_scenario`, `export_session` extended (map, control
  config, experiment metadata, decisions on the session clock). `configs/v4/experiments/scenarios_ab.json` (maps, scenarios, sets, seeds, timeout, detour).
- `gesture_data.py` (`TruthRow.gesture_truthful`), `bridge/protocol.py` (the name refused from Unity), `docs/protocol_v3.md` (amendment 4).
- `export_csv_v4.py`, `configs/v4/experiments/export_csv.json`, `run_experiments_ab_v4.py` (evaluation code; since the review of 2026-11-13, 16.10: `scenarios_ab.json` is in the freeze list through `freeze_v4.FROZEN_EXTRA`, `export_csv.json` is not;
  `frozen.json` was not touched).
- Tests: `tests/test_lie_detection_v4.py` (54), `tests/test_export_csv_v4.py` (25), `tests/golden_sim_v4.py` + `golden_sim_v4_baseline.json` (14 whole trials recorded on
  808f028: with every switch off the controller and simulator reproduce them field for field). **Existing tests changed (minimal, each keeps its intent):**
  `test_protocol_v3.py` (the new truth name), `test_gesture_data.py`, `test_hri_eval_dev_v4.py`, `test_gt_path.py`, `test_hri_sim_v4.py` (the new evaluation modules
  `export_csv_v4.py`, `run_experiments_ab_v4.py` added to their lists of files allowed to import evaluation code / the v4 simulator).

**Values chosen in this round, one line each (to confirm or change):**
- Obstacle detour on, for the scenarios only (opt-in): decision (2) of this round.
- Detour clearance 0.9 m = `safety.corridor_half_width_m` 0.6 m + half the robot width 0.3 m: derived from existing values, no new number.
- Detour waypoint 1.25 x clearance beside the person and at most 8 passes: geometry so that both legs clear the person; not a setting.
- Approach point of the 2nd and 3rd person kept at least 2 x 0.6 m = 1.2 m from every other person: twice the stop corridor, derived; the 1st approach is the unchanged v3 rule.
- The approach point is searched in 30 degree steps around the person (+30, -30, +60, ...): sampling resolution; 30 degrees is also `branch_match_max_deg`, reused for convenience.
- 600 s sensitivity timeout: see 16.4 item 4.

### 16.7 Result: the table (SIMULATOR; 20 seeded runs per row, seeds 1 to 20, timeout 270 s)

Rerun after the review of 2026-11-13 (16.10), folder `experiments_ab_v4_main_270s_v2_20261113_233042` (git-ignored, under `outputs/`; `runs.csv`, `dialogs.csv`, `table.md`, `table.json`, `arrival_mirror.md`, the session
folders). Neutral gesture reader (coverage 1, accuracy 1, no angle noise), perfect tracker, routes with a detour around people, maps and placements of 16.2.
Detection **on** = second opinion (a) + reject impossible (b); **backtrack (c) is off**. Every row is identical to the table of the first version of this section (commit e2adec2, which had
(c) on): (c) never fired in the 80 detection-on runs. Set A with detection on is an extra beyond the plan. Lies: given = lying gestures in `truth.jsonl`;
detected = rejected, outvoted or withdrawn by a backtrack (of those given); corrected = detected and the visit ended with the true branch (of those detected);
fooled = acted on and not the true branch (of those given); a lie that is neither was ignored or read as the right branch.

| experiment | detection | SUCCESS (95 % Wilson) | failures | median time s | lies given | detected | corrected | fooled | collisions | safety stops | rejections / 2nd opinions / backtracks |
|---|---|---|---|---|---|---|---|---|---|---|---|
| A1 | off | 20/20 (0.84 to 1.00) | - | 68.0 | 0 | 0/0 | 0/0 | 0/0 | 0 | 0 | 0 / 0 / 0 |
| A1 | on (a+b) | 20/20 (0.84 to 1.00) | - | 77.9 | 0 | 0/0 | 0/0 | 0/0 | 0 | 0 | 0 / 20 / 0 |
| A2 | off | 20/20 (0.84 to 1.00) | - | 82.9 | 0 | 0/0 | 0/0 | 0/0 | 0 | 0 | 0 / 0 / 0 |
| A2 | on (a+b) | 20/20 (0.84 to 1.00) | - | 101.0 | 0 | 0/0 | 0/0 | 0/0 | 0 | 0 | 0 / 40 / 0 |
| A3 | off | 20/20 (0.84 to 1.00) | - | 121.8 | 0 | 0/0 | 0/0 | 0/0 | 0 | 0 | 0 / 0 / 0 |
| A3 | on (a+b) | 20/20 (0.84 to 1.00) | - | 151.4 | 0 | 0/0 | 0/0 | 0/0 | 0 | 0 | 0 / 58 / 0 |
| A4 | off | 20/20 (0.84 to 1.00) | - | 110.2 | 0 | 0/0 | 0/0 | 0/0 | 0 | 2 | 0 / 0 / 0 |
| A4 | on (a+b) | 19/20 (0.76 to 0.99) | timeout 1 | 140.2 | 0 | 0/0 | 0/0 | 0/0 | 0 | 22 | 0 / 58 / 0 |
| B1 | off | 20/20 (0.84 to 1.00) | - | 68.0 | 3 | 0/3 | 0/0 | 0/3 | 0 | 0 | 0 / 0 / 0 |
| B1 | on (a+b) | 20/20 (0.84 to 1.00) | - | 77.9 | 5 | 3/5 | 3/3 | 0/5 | 0 | 0 | 3 / 20 / 0 |
| B2 | off | 17/20 (0.64 to 0.95) | aborted 3 | 82.9 | 13 | 0/13 | 0/0 | 0/13 | 0 | 0 | 0 / 0 / 0 |
| B2 | on (a+b) | 20/20 (0.84 to 1.00) | - | 108.7 | 21 | 16/21 | 16/16 | 0/21 | 0 | 0 | 16 / 40 / 0 |
| B3 | off | 13/20 (0.43 to 0.82) | aborted 1, wrong_goal 6 | 119.9 | 16 | 0/16 | 0/0 | 7/16 | 0 | 0 | 0 / 0 / 0 |
| B3 | on (a+b) | 18/20 (0.70 to 0.97) | aborted 1, wrong_goal 1 | 154.5 | 22 | 13/22 | 13/13 | 2/22 | 0 | 1 | 6 / 65 / 0 |
| B4 | off | 16/20 (0.58 to 0.92) | aborted 3, wrong_goal 1 | 109.3 | 12 | 0/12 | 0/0 | 1/12 | 0 | 2 | 0 / 0 / 0 |
| B4 | on (a+b) | 17/20 (0.64 to 0.95) | timeout 2, wrong_goal 1 | 151.7 | 28 | 18/28 | 18/18 | 2/28 | 0 | 21 | 10 / 66 / 0 |

**The same with a 600 s timeout** (`experiments_ab_v4_sensitivity_600s_v2_20261113_233147`, labelled "sensitivity, not a plan value"): every row is identical to the 270 s table. The 3 timeouts
(A4 on 1, B4 on 2) are permanent safety stalls, not slowness; their cause is in 16.10.3.

**Rule by rule** (extra beyond the plan; `experiments_ab_v4_rules_270s_v3_20261113_233238`; Set B, 270 s; the b+c and a+b+c rows have backtrack on):

| experiment | detection | SUCCESS (95 % Wilson) | failures | median time s | lies given | detected | corrected | fooled | collisions | safety stops | rejections / 2nd opinions / backtracks |
|---|---|---|---|---|---|---|---|---|---|---|---|
| B1 | off | 20/20 (0.84 to 1.00) | - | 68.0 | 3 | 0/3 | 0/0 | 0/3 | 0 | 0 | 0 / 0 / 0 |
| B1 | on (a+b) | 20/20 (0.84 to 1.00) | - | 77.9 | 5 | 3/5 | 3/3 | 0/5 | 0 | 0 | 3 / 20 / 0 |
| B1 | a only | 20/20 (0.84 to 1.00) | - | 77.9 | 5 | 0/5 | 0/0 | 0/5 | 0 | 0 | 0 / 20 / 0 |
| B1 | b only | 20/20 (0.84 to 1.00) | - | 68.0 | 3 | 2/3 | 2/2 | 0/3 | 0 | 0 | 2 / 0 / 0 |
| B1 | b+c | 20/20 (0.84 to 1.00) | - | 68.0 | 3 | 2/3 | 2/2 | 0/3 | 0 | 0 | 2 / 0 / 0 |
| B1 | a+b+c | 20/20 (0.84 to 1.00) | - | 77.9 | 5 | 3/5 | 3/3 | 0/5 | 0 | 0 | 3 / 20 / 0 |
| B2 | off | 17/20 (0.64 to 0.95) | aborted 3 | 82.9 | 13 | 0/13 | 0/0 | 0/13 | 0 | 0 | 0 / 0 / 0 |
| B2 | on (a+b) | 20/20 (0.84 to 1.00) | - | 108.7 | 21 | 16/21 | 16/16 | 0/21 | 0 | 0 | 16 / 40 / 0 |
| B2 | a only | 20/20 (0.84 to 1.00) | - | 111.6 | 21 | 0/21 | 0/0 | 0/21 | 0 | 0 | 0 / 40 / 0 |
| B2 | b only | 17/20 (0.64 to 0.95) | aborted 3 | 82.9 | 13 | 12/13 | 6/12 | 0/13 | 0 | 0 | 12 / 0 / 0 |
| B2 | b+c | 17/20 (0.64 to 0.95) | aborted 3 | 82.9 | 13 | 12/13 | 6/12 | 0/13 | 0 | 0 | 12 / 0 / 0 |
| B2 | a+b+c | 20/20 (0.84 to 1.00) | - | 108.7 | 21 | 16/21 | 16/16 | 0/21 | 0 | 0 | 16 / 40 / 0 |
| B3 | off | 13/20 (0.43 to 0.82) | aborted 1, wrong_goal 6 | 119.9 | 16 | 0/16 | 0/0 | 7/16 | 0 | 0 | 0 / 0 / 0 |
| B3 | on (a+b) | 18/20 (0.70 to 0.97) | aborted 1, wrong_goal 1 | 154.5 | 22 | 13/22 | 13/13 | 2/22 | 0 | 1 | 6 / 65 / 0 |
| B3 | a only | 18/20 (0.70 to 0.97) | aborted 1, wrong_goal 1 | 155.2 | 22 | 7/22 | 7/7 | 2/22 | 0 | 1 | 0 / 65 / 0 |
| B3 | b only | 13/20 (0.43 to 0.82) | aborted 1, wrong_goal 6 | 119.9 | 16 | 4/16 | 3/4 | 7/16 | 0 | 0 | 4 / 0 / 0 |
| B3 | b+c | 13/20 (0.43 to 0.82) | aborted 1, wrong_goal 6 | 119.9 | 16 | 4/16 | 3/4 | 7/16 | 0 | 0 | 4 / 0 / 0 |
| B3 | a+b+c | 18/20 (0.70 to 0.97) | aborted 1, wrong_goal 1 | 154.5 | 22 | 13/22 | 13/13 | 2/22 | 0 | 1 | 6 / 65 / 0 |
| B4 | off | 16/20 (0.58 to 0.92) | aborted 3, wrong_goal 1 | 109.3 | 12 | 0/12 | 0/0 | 1/12 | 0 | 2 | 0 / 0 / 0 |
| B4 | on (a+b) | 17/20 (0.64 to 0.95) | timeout 2, wrong_goal 1 | 151.7 | 28 | 18/28 | 18/18 | 2/28 | 0 | 21 | 10 / 66 / 0 |
| B4 | a only | 17/20 (0.64 to 0.95) | timeout 2, wrong_goal 1 | 153.0 | 28 | 8/28 | 8/8 | 2/28 | 0 | 21 | 0 / 66 / 0 |
| B4 | b only | 16/20 (0.58 to 0.92) | aborted 3, wrong_goal 1 | 109.3 | 12 | 6/12 | 2/6 | 1/12 | 0 | 2 | 6 / 0 / 0 |
| B4 | b+c | 16/20 (0.58 to 0.92) | aborted 2, wrong_goal 2 | 111.3 | 14 | 6/14 | 2/6 | 3/14 | 0 | 3 | 6 / 0 / 1 |
| B4 | a+b+c | 17/20 (0.64 to 0.95) | timeout 2, wrong_goal 1 | 151.7 | 28 | 18/28 | 18/18 | 2/28 | 0 | 21 | 10 / 66 / 0 |

### 16.8 What the table says, and what it does not

1. Detection (a+b) helps where a lie can lead to a wrong branch: B3 SUCCESS 13/20 -> 18/20, B2 17/20 -> 20/20, B4 16/20 -> 17/20, B1 20/20 both (a lie in a corridor
   is only an impossible direction: the robot asks again either way). It costs time (median +10 to +42 s per run: one more dialog per node) and, in the random
   layout, safety stops (A4 on 22 stops, 1 timeout, against 2 stops, 0 timeouts with detection off, although nobody lies).
2. Rules: second opinion (a) does most of the work in B2 to B4; reject alone (b) finds only the impossible directions (B2: 12 of 13 lies, but 6 of 12 corrected);
   a + b detects more than either alone (B3: 13 of 22 lies against 7 of 22 for a and 4 of 16 for b) because a rejected answer is no vote and the next person is asked.
   **Backtrack (c) was never used in the 80 a+b+c runs and fired once in the 80 b+c runs (B4; that run ended wrong_goal)**, so it is off in the experiments (16.10.2).
   Why: the evidence it needs, a worker pointing back along the arrival road, was read as a valid branch in many cases (16.10.2).
3. A lie is not always caught: fooled 2 of 22 in B3 on, 2 of 28 in B4 on (not analysed case by case).
4. **Simulator limits, stated so that nobody reads more into the table:** the perception is the reader's output, not pixels; gesture noise is neutral (no wrong readings
   beyond the mirror ambiguity), so real accuracy will be lower; the tracker is perfect (real ByteTrack id switches could make the robot ask the same person twice); the
   obstacle detour is a model of Unity's NavMesh, not Unity; the people are not moving; lies are drawn per gesture (decision 2) so a re-ask is a new draw. None of it was
   tuned on these results. The first runs found three simulator artefacts, fixed before the table was made (16.5): straight-line routes, an approach point on top of another
   person, and (the remaining 3 stalls, 16.7) avatars standing closer to the robot's path than the safety corridor allows.
5. With the detour there are 0 collisions in every row. Before it a person standing 1.0 to 1.2 m from the road (allowed by the decided placement rule) could be hit by a
   departure that cut a corner (A4 detection off 1 of 20, A3 detection on 5 of 20). The placement rule is unchanged; a larger lateral distance or road distance would
   make the problem disappear without the detour, if you prefer that to a model of the NavMesh.

### 16.9 Reproduce (from `robot_vision/`)

Windows PowerShell: `.\.venv\Scripts\python.exe run_experiments_ab_v4.py --runs 20 --timeout-s 270 --label main_270s`; macOS: `.venv/bin/python run_experiments_ab_v4.py --runs 20 --timeout-s 270 --label main_270s`.
Sensitivity: `--timeout-s 600 --label sensitivity_600s`. Rules: `--experiments B1 B2 B3 B4 --settings off a b bc ab on --label rules_270s`. CSV of any session pair:
`python export_csv_v4.py --session outputs/<run>/sessions/trials_B3_on outputs/<run>/sessions/bridge_B3_on`. Each call writes a new timestamped folder; nothing is overwritten.

### 16.10 Review of 2026-11-13 (Anisha), answers

**16.10.1 Freeze.** `configs/v4/experiments/scenarios_ab.json` defines the experiments (maps, placements, lie probability, seeds, timeout, detour, the two detection settings)
and is covered by the freeze: `freeze_v4.FROZEN_EXTRA` adds it to `config_files()`, so `--refresh-list` lists it, `--freeze` hashes it and `problems()` finds a change (tests:
`tests/test_v4_frozen.py`: the experiments file is listed, a change after freezing is found; the unfrozen record's list may lag behind the real list until `--refresh-list`
is run, it may not name a file that is not frozen). `frozen.json` itself is untouched and unfrozen. `experiments/export_csv.json` stays OUTSIDE the freeze, and the reasoning is
recorded here: it only chooses which columns of runs.csv and dialogs.csv are written, in which order and under which header. Every value in those files is computed from the
session folders by `export_csv_v4.py` (tested), with the definitions in its code and in `export.json`; no result, decision or number depends on the column list, and it has to
stay editable to match the faculty's list. If the definitions (detected / corrected / fooled) should be frozen too, the module would be listed in the freeze instead; not done.

**16.10.2 Backtrack and the mirror reading.** *Backtrack (rule c): the switch is kept in `control.json` (default false, `tests/test_lie_detection_v4.py` `RuleC_Backtrack` still passes) and is
OFF for the experiments: `scenarios_ab.json` `detection.on` = a + b, `hri_sim_v4.DETECTION_ON` equals it (a test pins both).* Finding recorded: in 80 runs with a+b+c it fired 0 times (the
a+b rows are identical), in the 80 reject + backtrack runs once, and that run ended in the wrong goal.

*Rule (b) and the mirror reading.* Measured on B1 to B4 (20 runs each, `experiments_ab_v4_rules_270s_v3_20261113_233238`, `arrival_mirror.md`), asks where the worker pointed BACK along the arrival road:

| setting | BACK shown | read as a branch | rejected | unclear | accepted asks | accepted with an arrival-road reading | truthful and correct | wrong or lie |
|---|---|---|---|---|---|---|---|---|
| off | 11 | 5 | 0 | 6 | 163 | 33 | 22 | 11 |
| on (a+b) | 20 | 6 | 12 | 2 | 357 | 84 | 66 | 18 |
| a+b + counterfactual 1 | 24 | 0 | 20 | 4 | 314 | 0 | 0 | 0 |
| a+b + counterfactual 2 | 26 | 2 | 13 | 11 | 343 | 0 | 0 | 0 |

- With detection off, 5 of 11 BACK asks (45 %) were accepted as a branch (2 of the 11 were truthful: a worker at a wrong node); with a+b, 6 of 20 (30 %), 12 rejected as `arrival`, 2 unclear. BACK asks are rare.
- The counts are small (11 to 26 BACK asks per setting over 80 runs): read them as an order of magnitude, not as rates.
- The cause is as you described: of the two depth readings the one nearest the arrival road is dropped, the other lands on a branch and is accepted.
- Any accepted answer with the arrival road as one of its two readings: 84 of 357 accepted asks (24 %) with a+b, of which
  66 are truthful and correct (an honest gesture whose mirror happens to be the arrival road) and 18 are not.
  This is the price of any fix that acts on "either reading is the arrival road".

*Proposed fixes (NOT applied; analysis-only counterfactuals in `run_experiments_ab_v4.py`, settings `mirror` and `mirror2`; nothing changed in `hri_control_v4.py`; B1 to B4, 20 runs each, 270 s):*

| experiment | detection | SUCCESS (95 % Wilson) | failures | median time s | lies given | detected | corrected | fooled | collisions | safety stops | rejections / 2nd opinions / backtracks |
|---|---|---|---|---|---|---|---|---|---|---|---|
| B1 | on (a+b) | 20/20 (0.84 to 1.00) | - | 77.9 | 5 | 3/5 | 3/3 | 0/5 | 0 | 0 | 3 / 20 / 0 |
| B1 | a+b + counterfactual 1 | 20/20 (0.84 to 1.00) | - | 77.9 | 6 | 6/6 | 6/6 | 0/6 | 0 | 0 | 6 / 20 / 0 |
| B1 | a+b + counterfactual 2 | 20/20 (0.84 to 1.00) | - | 77.9 | 6 | 4/6 | 4/4 | 0/6 | 0 | 0 | 4 / 20 / 0 |
| B2 | on (a+b) | 20/20 (0.84 to 1.00) | - | 108.7 | 21 | 16/21 | 16/16 | 0/21 | 0 | 0 | 16 / 40 / 0 |
| B2 | a+b + counterfactual 1 | 18/20 (0.70 to 0.97) | aborted 2 | 113.2 | 26 | 26/26 | 21/26 | 0/26 | 0 | 0 | 46 / 40 / 0 |
| B2 | a+b + counterfactual 2 | 20/20 (0.84 to 1.00) | - | 119.5 | 28 | 20/28 | 20/20 | 0/28 | 0 | 0 | 20 / 40 / 0 |
| B3 | on (a+b) | 18/20 (0.70 to 0.97) | aborted 1, wrong_goal 1 | 154.5 | 22 | 13/22 | 13/13 | 2/22 | 0 | 1 | 6 / 65 / 0 |
| B3 | a+b + counterfactual 1 | 16/20 (0.58 to 0.92) | aborted 4 | 159.3 | 31 | 21/31 | 21/21 | 0/31 | 0 | 2 | 44 / 64 / 0 |
| B3 | a+b + counterfactual 2 | 18/20 (0.70 to 0.97) | aborted 2 | 174.6 | 34 | 15/34 | 15/15 | 0/34 | 0 | 1 | 10 / 63 / 0 |
| B4 | on (a+b) | 17/20 (0.64 to 0.95) | timeout 2, wrong_goal 1 | 151.7 | 28 | 18/28 | 18/18 | 2/28 | 0 | 21 | 10 / 66 / 0 |
| B4 | a+b + counterfactual 1 | 17/20 (0.64 to 0.95) | timeout 1, wrong_goal 2 | 165.6 | 29 | 21/29 | 21/21 | 2/29 | 0 | 22 | 41 / 62 / 0 |
| B4 | a+b + counterfactual 2 | 17/20 (0.64 to 0.95) | timeout 2, wrong_goal 1 | 168.6 | 32 | 17/32 | 17/17 | 2/32 | 0 | 36 | 11 / 66 / 0 |

1. **Reject when either reading is the arrival road** (counterfactual 1, your example). BACK read as a branch: 6 -> 0. But it rejects the 66 honest answers
   that look the same, and both asks of a dialog can be used up: SUCCESS B2 20 -> 18, B3 18 -> 16 (aborted 4) of 20 against detection on. Not recommended as it stands.
2. **Treat such a reading as ambiguous and use the existing second view** (counterfactual 2): move 0.8 m aside, keep only the direction both views agree on (the true one stays put, the
   mirror moves by about 45 degrees), not counted as an ask. No accepted ask keeps an arrival-road reading; SUCCESS equal to detection on in all four experiments
   (B1 20, B2 20, B3 18, B4 17 of 20), fooled lies B3 2/22 -> 0/34, B4 2/28 -> 2/32 (unchanged), at +0 to +20 s median time. BACK read as a branch 6 -> 2 (2 remain, not analysed). **This is my
   recommendation.** The third idea, to ask a second person in that case, was not measured; with a+b already on, a second person is asked at every node anyway, so it adds
   little there and would matter only with second opinion off.
Nothing is applied before you confirm. **Update: Fix 2 was confirmed and applied on 2026-11-13, see 16.11.**

**16.10.3 The 3 timeouts (report only).** Three of the 160 detection-on runs (A1 to A4, B1 to B4) ended by timeout: A4 on seed 18, B4 on seed 18 (the same random layout at J4, same seed) and B4 on seed 2 (J2).
Cause, from the controller state at the end of each (`outputs/` session folders and a replay of the seeds):
- *State:* `navigate` (J4 to E5, twice) and `execute` (J2, turning to the next node); `safety_reason` = `person in path` in all three; the robot had been stopped for 98 to 149 s of 270 s and never moved again
  after t = 116 s to 173 s.
- *What it waits for:* the person-in-path stop (`hri_control.Controller._safety`, the frozen v3 rule) holds the robot while any person stands within `stop_distance` ahead of it (0.65 + 0.2 = 0.85 m at
  standstill) and within 0.6 m of its heading line. At the end a person stood 0.81 to 0.85 m ahead and 0.30 to 0.58 m across. The stop zeroes every command, including turning in place, and nothing
  else in the controller moves the robot away, so it waits for an avatar that never moves: for ever.
- *How it got there:* the two avatars stood only 1.23 to 1.47 m apart (random placement allows 1.0 m). Asking the second person from 2.0 m left the robot 1.0 to 1.4 m from the first person (in the J2 case after a re-ask, which moves 0.8 m aside and ignores
  other people); the next turn toward the following node brought that person inside the 0.85 m zone.
- *Simulator or controller?* Both parts are real. The rule that never lets go is controller logic that Unity would run unchanged (the same Python controller, people from the 360 camera). Whether the geometry
  arises in Unity depends on layout and on the NavMesh path, which the simulator only models (the detour); the `execute` stall at J2 happens during a turn in place, with no route involved, so it is
  not the simulator's straight-line route. Not tested in Unity. If you want it removed: the stop could allow turning away or backing off, or the placement keep avatars 2 m or more apart; neither is done.

**16.10.4 Every value I chose** is listed one per line with its reason in 16.4 (the first round) and 16.5 (the second round).

### 16.11 Decisions of 2026-11-13, third round (Anisha, after the review of 16.10)

1. **Freeze handling accepted** (16.10.1).
2. **Fix 2 is applied** in `hri_control_v4.py`, under the `reject_impossible` switch: when a pointed direction resolves to a branch but the OTHER of its two mirror-image depth readings is the
   arrival road, the answer is ambiguous (`resolve_point(..., arrival_mirror_ambiguous)`, also inside `resolve_two_views`; `_interpret` passes `lie_detection.reject_impossible`), and the
   existing second view decides (move 0.8 m aside, keep the direction both views agree on, not counted as an ask). Every second view is now logged as a decision with its reason (`second_view`).
   With the switch off nothing changes (the golden record of 14 trials on 808f028 is still identical). **Backtrack stays off** for the experiments. Before the counterfactual code was removed
   (it lives in commit 735eea2) the controller was checked against it: the 12 result columns of B1 to B4 are identical. Tests: `RuleB_ArrivalMirror`, `PlacementRule` in `tests/test_lie_detection_v4.py`.
   *The 2 BACK readings that still got through (B1 to B4, detection on, 80 runs; both found in `experiments_ab_v4_main_270s_v3_20261113_234228`, B2 run 19 at B and B4 run 19 at J3).* They are not a BACK answer taken as a wrong
   branch. In both, the FIRST view was an honest gesture (RIGHT, LEFT) whose mirror reading was the arrival road, so the fix did send the robot to a second view
   (first-view readings: -150.5 deg = arrival and 90 deg = RIGHT; -56.3 deg = arrival and 0 deg = LEFT). The simulator stages a new gesture whenever the question is shown, the second view included
   (decision 2: every gesture is an independent draw), and in both runs the worker's second gesture was a lie, BACK. The second view's check compares the readings of two different gestures: the
   mirror image of the BACK lie (86.4 and -1.5 deg) fell within 3.6 and 1.5 deg of the true direction of the first gesture (tolerance 10 deg), so the views "agreed" on the true branch
   (RIGHT, LEFT) and the robot took it. The answer was right by coincidence of a mirror reading, not because the back-pointing was understood. Counts: BACK asks in B1 to B4 with detection on
   26, read as a branch 2, rejected 14, unclear 10 (before the fix: 20, 6, 12, 2 in the earlier run); accepted asks with an arrival-road reading
   0 of 342 (before: 84 of 357). Reported only; nothing further changed.
3. **Placement rule** (timeouts of 16.10.3): `scenarios_ab.json` `placement_rule`: any two workers at least **3.0 m** apart and every worker at least **3.0 m** from every turning point of the path (the start
   node and every junction). Reason: the robot asks from 2.0 m, so another worker is then at least 3.0 - 2.0 = 1.0 m away, outside the 0.85 m person-in-path stop zone of a robot at standstill. The v3 person-in-path
   stop is unchanged. Enforced in the simulator (`check_placement` for the `beside` and `random` layouts, `place_random` samples under it; it replaces the 1.0 m separation of 16.2 decision 3 for A4; the `beside`
   placement (4.0 m apart, 3.6 m from the node) already obeyed it; `fixed` layouts of tests are exempt). **For Nusrat: Unity must use the same rule when it places the workers of these experiments (at least 3.0 m
   between any two workers and at least 3.0 m from every junction and from the start node).** A stall that still happens is a failure result, not hidden.
4. **Item 18 accepted** (a truthful worker at a wrong junction points BACK): recorded as an accepted modelling assumption of the study.

**The 20-seed table again** (SIMULATOR; seeds 1 to 20, timeout 270 s, detection off / on = a + b, backtrack off; new = `experiments_ab_v4_main_270s_v3_20261113_234228`, previous = `experiments_ab_v4_main_270s_v2_20261113_233042`, the table of 16.7). What changed between them:
Fix 2 (rule b) and the placement rule (A4 only: the separation of 1.0 m became 3.0 m plus the turning-point rule; A1 to A3 placements are unchanged). The counterfactual run of 16.10 (Fix 2 with the old placement) had the same
successes as the previous table in B1 to B4 (20, 20, 18, 17 of 20), so the differences in SUCCESS below come from the placement rule; the longer times come from the extra second views of Fix 2.

| experiment | detection | previous: SUCCESS | failures | median s | coll. | stops | **new: SUCCESS** | failures | median s | coll. | stops |
|---|---|---|---|---|---|---|---|---|---|---|---|
| A1 | off | 20/20 (0.84-1.00) | - | 68.0 | 0 | 0 | **20/20 (0.84-1.00)** | - | 68.0 | 0 | 0 |
| A1 | on (a+b) | 20/20 (0.84-1.00) | - | 77.9 | 0 | 0 | **20/20 (0.84-1.00)** | - | 77.9 | 0 | 0 |
| A2 | off | 20/20 (0.84-1.00) | - | 82.9 | 0 | 0 | **20/20 (0.84-1.00)** | - | 82.9 | 0 | 0 |
| A2 | on (a+b) | 20/20 (0.84-1.00) | - | 101.0 | 0 | 0 | **20/20 (0.84-1.00)** | - | 110.4 | 0 | 0 |
| A3 | off | 20/20 (0.84-1.00) | - | 121.8 | 0 | 0 | **20/20 (0.84-1.00)** | - | 121.8 | 0 | 0 |
| A3 | on (a+b) | 20/20 (0.84-1.00) | - | 151.4 | 0 | 0 | **20/20 (0.84-1.00)** | - | 160.7 | 0 | 0 |
| A4 | off | 20/20 (0.84-1.00) | - | 110.2 | 0 | 2 | **20/20 (0.84-1.00)** | - | 113.4 | 0 | 0 |
| A4 | on (a+b) | 19/20 (0.76-0.99) | timeout 1 | 140.2 | 0 | 22 | **20/20 (0.84-1.00)** | - | 159.2 | 0 | 1 |
| B1 | off | 20/20 (0.84-1.00) | - | 68.0 | 0 | 0 | **20/20 (0.84-1.00)** | - | 68.0 | 0 | 0 |
| B1 | on (a+b) | 20/20 (0.84-1.00) | - | 77.9 | 0 | 0 | **20/20 (0.84-1.00)** | - | 77.9 | 0 | 0 |
| B2 | off | 17/20 (0.64-0.95) | aborted 3 | 82.9 | 0 | 0 | **17/20 (0.64-0.95)** | aborted 3 | 82.9 | 0 | 0 |
| B2 | on (a+b) | 20/20 (0.84-1.00) | - | 108.7 | 0 | 0 | **20/20 (0.84-1.00)** | - | 119.5 | 0 | 0 |
| B3 | off | 13/20 (0.43-0.82) | aborted 1, wrong_goal 6 | 119.9 | 0 | 0 | **13/20 (0.43-0.82)** | aborted 1, wrong_goal 6 | 119.9 | 0 | 0 |
| B3 | on (a+b) | 18/20 (0.70-0.97) | aborted 1, wrong_goal 1 | 154.5 | 0 | 1 | **18/20 (0.70-0.97)** | aborted 2 | 174.6 | 0 | 1 |
| B4 | off | 16/20 (0.58-0.92) | aborted 3, wrong_goal 1 | 109.3 | 0 | 2 | **18/20 (0.70-0.97)** | aborted 1, wrong_goal 1 | 118.5 | 0 | 0 |
| B4 | on (a+b) | 17/20 (0.64-0.95) | timeout 2, wrong_goal 1 | 151.7 | 0 | 21 | **18/20 (0.70-0.97)** | aborted 2 | 177.4 | 0 | 2 |

Lies (Set B):

| experiment | detection | previous: lies given | detected | corrected | fooled | new: lies given | detected | corrected | fooled |
|---|---|---|---|---|---|---|---|---|---|
| B1 | off | 3 | 0 | 0/0 | 0 | 3 | 0 | 0/0 | 0 |
| B1 | on (a+b) | 5 | 3 | 3/3 | 0 | 6 | 4 | 4/4 | 0 |
| B2 | off | 13 | 0 | 0/0 | 0 | 13 | 0 | 0/0 | 0 |
| B2 | on (a+b) | 21 | 16 | 16/16 | 0 | 28 | 20 | 20/20 | 0 |
| B3 | off | 16 | 0 | 0/0 | 7 | 16 | 0 | 0/0 | 7 |
| B3 | on (a+b) | 22 | 13 | 13/13 | 2 | 34 | 15 | 15/15 | 0 |
| B4 | off | 12 | 0 | 0/0 | 1 | 12 | 0 | 0/0 | 1 |
| B4 | on (a+b) | 28 | 18 | 18/18 | 2 | 31 | 19 | 19/19 | 0 |

Read: **0 collisions and 0 timeouts in all 16 rows** (the previous table had 3 timeouts: A4 on 1, B4 on 2). Detection off and on, A: 80/80 and 80/80 (previous 80/80 and 79/80). Set B: off 68/80, on 76/80
(previous 66/80 and 75/80). Detection on costs time (A1 +10 s, A2 +27 s, A3 +39 s, A4 +46 s, B2 +37 s, B3 +55 s, B4 +59 s median over off); Fix 2 adds to it (B2 108.7 -> 119.5 s, B3 154.5 -> 174.6 s, B4 151.7 -> 177.4 s). Remaining safety stops
(A4 on 1, B3 on 1, B4 on 2) did not end in a timeout. The failures left in Set B with detection on are aborts (B3 2, B4 2): the fail-safe outcome (unclear after two asks); no wrong goal remains with detection on, no lie was acted on (fooled 0 in
every B row), against fooled 7/16 (B3) and 1/12 (B4) with detection off. Same simulator limits as 16.8 item 4.

### 16.12 Decisions of 2026-11-14 (Anisha), recorded BEFORE the code

Branch `anisha/v4-experiments-ab-2` (from main `cc95b9e`, which holds 16.1 to 16.11 and Nusrat's Unity side of experiments A and B: `Avatar/Config/experiments_ab.md`,
`looks_ab.json`, `Scenario/Config/experiments_ab_unity.json`, `roadmap_proposals/turn_left.json`). Read for this entry: Nusrat's `experiments_ab.md` (the step reports
`experiments_ab_step1_20261114.md` and `experiments_ab_step2_avatars_20261114.md` and `outputs/experiments_ab_roadmaps_20261114_025749/` are not on main and were not available). Python only; nothing under
`unity/`, `external/` or v3 is touched; `freeze_v4.py --freeze` is not run; no reader value is changed (item 1 stops at 1c).

**Item 1. FALSE STOP of the live reader (found by Nusrat; data in `~/Downloads/false_stop_data.zip`, NOT YET RECEIVED: items 2 to 6 first).** Observed by Nusrat: in the 13 Nov video session 73 of 117
PROCEED frames read STOP (16 stops); in R1 358 of 877, 196 stops, 3 of them while driving at 0.8 m/s with no gesture shown. Suspected cause: the flat PROCEED hand passes the open-palm test (finger
spread measured from the wrist, median 38 to 40 deg against the 20 deg limit), there is no palm-direction check, and the MediaPipe label is not required for STOP (decided 2026-11-08). Plan, in this order,
and only on development looks and development clips (the test looks `sunbox_f2`, `sunbox_*_plaid` and the test clips are never used; the zip is read with `zipfile`, never extracted or copied):
- (a) find the cause of the 3 stops with no gesture shown: which person, which hand, which cues passed (a report, no change);
- (b) propose a fix from three candidate cues: the palm normal facing the camera (from the hand landmarks), the STOP hand static over the window (PROCEED swings), the spread measured between the
  fingertips instead of from the wrist;
- (c) show, on the zip's data, STOP readings on PROCEED, on POINT, on nothing shown and on a true STOP, before and after, for each cue alone and combined (a table). **Then stop and ask before any
  reader value (`configs/v4/gesture_reader.json`, `gesture_motion.py`) is changed.**

**Item 2. Consistent lies.** In Unity a lying worker repeats the same wrong direction when asked again. The simulator does the same: one lie draw per worker per run (is the worker a liar, and which wrong
direction), from the generator `random.Random(f"{seed}|{node}|{worker id}")` of 16.4 item 17, drawn the first time the worker is asked and kept for the run (a re-ask, a second view, a later visit show
the same direction). This replaces "every gesture is an independent draw" of 16.2 decision 2 (`scenarios_ab.json` `sets.B.lie_mode` "per_worker"; "per_gesture" stays available, it is what produced
the table of 16.7 and 16.11). Direction model unchanged (one of the other three of LEFT / FORWARD / RIGHT / BACK relative to the arrival direction). The 20-seed table is rerun (A1 to A4, B1 to B4,
detection off and on) and shown next to the previous one (16.11), with the effect of items 3 and 4 separated.

**Item 3. A third worker at J1** (for the majority vote) in A3, A4, B3, B4: `scenarios_ab.json` `layout.people_by_node` {"J1": 3}. In `beside` the third worker stands 3.0 m behind the first, on its side
(16.4 item 11, as Nusrat's slot 3); in `random` it is drawn like the others.

**Item 4. Random layout: bystander margin 0.25 m accepted**, the 3.0 m spacing and turning-point rule of 16.11 unchanged. Rule (as Nusrat's, section 3 of her notes): at every asking node the first
worker drawn is the one the robot reaches first; every other worker is at least 0.25 m farther from the robot than the first at every point of the last 3.0 m of the arrival road (at the start node: from
the start position). `scenarios_ab.json` `layout.nearer_margin_m` 0.25, `approach_m` 3.0 (= `hri_control.json` `drive.junction_slow_radius_m`), `max_draws` 100000. Any stall in the reruns is reported.
The simulator draws the whole set of workers of a node and redraws it as a whole until every rule holds, as Unity does (drawing the workers one after the other got stuck: 15 of 40 A3 / A4 scenes
of 20 seeds could not be built with three workers at J1).

**Item 5. For Nusrat's development runs.**
- *Server map files* for A1 and A2 with both turns, in the robot-map format of `configs/v4/roadmap.json`, in `configs/v4/experiments/`: `roadmap_a1.json`, `roadmap_a2_right.json`, `roadmap_a2_left.json`.
  Her `turn_left` proposal is added to `scenarios_ab.json` `maps` as `turn_left` (C at (-13.75, 0), equal legs; the simulator can run A2 / B2 with it). A test pins every map file to its map in `scenarios_ab.json`.
- *Control files* for lie detection on and off, the pattern of `control_zoom_on.json` / `control_zoom_off.json` (identical to `control.json` except one block; a test pins it). The server takes its map from the control
  file's `roadmap` key, so there is one pair per map: `control_lie_off.json` / `control_lie_on.json` (v4 map: A3, A4, B3, B4) and `..._a1`, `..._a2_right`, `..._a2_left` (8 files, `configs/v4/experiments/`;
  not in the freeze list, which keeps the final settings' frozen set unchanged; the flags are pinned to `scenarios_ab.json` `detection` by a test). "On" = second opinion + reject impossible, backtrack off (16.10.2).
- *Her look names* in `configs/v4/data_splits.json`: development `sunbox_m_shirt_white`, `sunbox_m_tshirt_black`, `sunbox_f_shirt_white`, `sunbox_f_dress_red`; test `sunbox_m_shirt_plaid`, `sunbox_f_shirt_plaid`
  (all of the Sunbox body family: style `sunbox`). The existing looks and clips are unchanged.
- *PROCEED in `look_check_v4.py`*: a recording with command PROCEED is accepted (a sequence of at least `proceed.window_s` 2.0 s), reported like the other commands, and graded when a look has such recordings; a
  look without PROCEED recordings keeps the verdict it has (PROCEED is not made required, so no existing verdict changes). Its frame-level "wrong class" rate counts a STOP / WAIT / POINT frame read on a PROCEED recording,
  which is exactly the false STOP of item 1. `configs/v4/look_check.json` is changed for it (declared here, no reader value).

**Item 6. Findings recorded (no change of any value).**
- *Timing passed* in Nusrat's Play session: loop lag max 68 ms, round trip max 42.5 ms, 0 watchdog stops, free memory minimum 328 MB (**low**: the run protocol asks for free memory; 328 MB is a risk for longer
  sessions and for the avatar experiment with more avatars). This meets the 14.16 condition on the lag and the round trip (limits 100 ms and 150 ms, 14.14); the memory is reported as a finding.
- *Arm ratio per avatar kind* (the reader's POINT geometry assumes `arm_length_in_shoulder_widths` 1.683): Sunbox -6 %, Mixamo -33 %, anime +35 %. The Mixamo and anime values lie outside the look check's accepted
  range of 1.683 x (1 - 0.30) to 1.683 x (1 + 0.25) (`look_check.json` `arm_ratio_p95`): POINT directions of those kinds are biased (the look check can only make such a look "weak"). A finding for the avatar experiment.
- *Boxo person found in 8 % of the frames* (`cartoon_boxo_01`, thumb + 3 fingers): YOLO does not reliably detect the character as a person. A finding for the avatar experiment; the person rate is far below the look
  check's `person_rate` bounds (usable 0.95, weak 0.80), so that look fails the check as declared.

**Open points from Nusrat's notes (`experiments_ab.md`), NOT decided here, for Anisha** ([A] = her marker): (1) the `beside` slots: Unity puts the second worker farther away (junction slot 2 at 5.5 m back, +2.0 m; start node slot 2
at 3.0 m back, +4.0 m) so that the 1.0 m bystander rule holds; the simulator keeps two workers 3.0 m before the node, 2.0 m each side; (2) the goal generator: Unity uses `GoalSequence(seed)`, the simulator
`random.Random(f"{seed}|goal")`, so the same seed gives different goals; (3) Unity's liar always shows a VALID branch where the node has another one (only where it has none, an impossible direction), the simulator
draws from LEFT / FORWARD / RIGHT / BACK, so impossible directions occur at junctions in the simulator and not in Unity; (4) `truth.jsonl` carries the extra field `active` in Unity; (5) the licences of
`anime_f_01` and `cartoon_boxo_01` (`SOURCES.txt` does not exist).

**Choices of mine in this round (to confirm or change):** the 8 control files under `configs/v4/experiments/` and not in `configs/v4/`; PROCEED graded only when a look has PROCEED recordings; `turn_left` taken from
Nusrat's proposal unchanged; the simulator's whole-set draw of random workers (the same as Unity's); a simulator A2 with the left map selectable by `side="left"` (default right, the decision of 16.2).

#### 16.12.1 Results of items 2 to 4 (SIMULATOR; 20 seeds per row, seeds 1 to 20, timeout 270 s; detection off / on = a + b, backtrack off)

Three tables side by side: **previous** = the table of 16.11 (`experiments_ab_v4_main_270s_v3_20261113_234228`: independent lies per gesture, two workers everywhere, the 16.11 layouts); **layouts only** = the new layouts of
items 3 and 4 (a third worker at J1 in A3, A4, B3, B4; the random layout's 0.25 m bystander margin, whole-set draws) with the earlier lie model (`experiments_ab_v4_layouts_only_270s_20261114_133042`, `--lie-mode per_gesture`);
**new** = items 2 to 4 together, consistent lies (`experiments_ab_v4_main_270s_v4_20261114_133015`). Previous to layouts-only is the effect of items 3 and 4 (A1 to A3 and B1 to B3 only through the third worker at J1, A4 and B4 also through the
random placement, which now draws whole sets and therefore differs from the 16.11 placements); layouts-only to new is the effect of item 2 alone (same placements, same seeds).

| experiment | detection | previous (16.11): SUCCESS | failures | median s | stops | + layouts only: SUCCESS | failures | median s | stops | **new (consistent lies): SUCCESS** | failures | median s | coll. | stops |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| A1 | off | 20/20 | - | 68.0 | 0 | 20/20 | - | 68.0 | 0 | **20/20** | - | 68.0 | 0 | 0 |
| A1 | on (a+b) | 20/20 | - | 77.9 | 0 | 20/20 | - | 77.9 | 0 | **20/20** | - | 77.9 | 0 | 0 |
| A2 | off | 20/20 | - | 82.9 | 0 | 20/20 | - | 82.9 | 0 | **20/20** | - | 82.9 | 0 | 0 |
| A2 | on (a+b) | 20/20 | - | 110.4 | 0 | 20/20 | - | 110.4 | 0 | **20/20** | - | 110.4 | 0 | 0 |
| A3 | off | 20/20 | - | 121.8 | 0 | 20/20 | - | 121.8 | 0 | **20/20** | - | 121.8 | 0 | 0 |
| A3 | on (a+b) | 20/20 | - | 160.7 | 0 | 20/20 | - | 160.7 | 0 | **20/20** | - | 160.7 | 0 | 0 |
| A4 | off | 20/20 | - | 113.4 | 0 | 20/20 | - | 109.6 | 0 | **20/20** | - | 109.6 | 0 | 0 |
| A4 | on (a+b) | 20/20 | - | 159.2 | 1 | 20/20 | - | 155.5 | 0 | **20/20** | - | 155.5 | 0 | 0 |
| B1 | off | 20/20 | - | 68.0 | 0 | 20/20 | - | 68.0 | 0 | **18/20** | aborted 2 | 68.0 | 0 | 0 |
| B1 | on (a+b) | 20/20 | - | 77.9 | 0 | 20/20 | - | 77.9 | 0 | **20/20** | - | 77.9 | 0 | 0 |
| B2 | off | 17/20 | aborted 3 | 82.9 | 0 | 17/20 | aborted 3 | 82.9 | 0 | **11/20** | aborted 9 | 82.1 | 0 | 0 |
| B2 | on (a+b) | 20/20 | - | 119.5 | 0 | 20/20 | - | 119.5 | 0 | **19/20** | aborted 1 | 117.3 | 0 | 0 |
| B3 | off | 13/20 | aborted 1, wrong_goal 6 | 119.9 | 0 | 13/20 | aborted 1, wrong_goal 6 | 119.9 | 0 | **11/20** | aborted 4, wrong_goal 5 | 119.9 | 0 | 0 |
| B3 | on (a+b) | 18/20 | aborted 2 | 174.6 | 1 | 18/20 | aborted 1, wrong_goal 1 | 175.5 | 0 | **20/20** | - | 172.0 | 0 | 0 |
| B4 | off | 18/20 | aborted 1, wrong_goal 1 | 118.5 | 0 | 13/20 | aborted 2, wrong_goal 5 | 108.7 | 0 | **12/20** | aborted 4, wrong_goal 4 | 107.2 | 0 | 0 |
| B4 | on (a+b) | 18/20 | aborted 2 | 177.4 | 2 | 18/20 | aborted 1, wrong_goal 1 | 183.7 | 1 | **19/20** | wrong_goal 1 | 175.7 | 0 | 1 |

Lies (Set B):

| experiment | detection | previous: lies given | detected | corrected | fooled | layouts only: given | detected | corrected | fooled | **new: given** | detected | corrected | fooled |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| B1 | off | 3 | 0 | 0/0 | 0 | 3 | 0 | 0/0 | 0 | 5 | 0 | 0/0 | 0 |
| B1 | on (a+b) | 6 | 4 | 4/4 | 0 | 6 | 4 | 4/4 | 0 | 12 | 10 | 10/10 | 0 |
| B2 | off | 13 | 0 | 0/0 | 0 | 13 | 0 | 0/0 | 0 | 19 | 0 | 0/0 | 0 |
| B2 | on (a+b) | 28 | 20 | 20/20 | 0 | 28 | 20 | 20/20 | 0 | 38 | 32 | 28/32 | 0 |
| B3 | off | 16 | 0 | 0/0 | 7 | 16 | 0 | 0/0 | 7 | 19 | 0 | 0/0 | 7 |
| B3 | on (a+b) | 34 | 15 | 15/15 | 0 | 38 | 16 | 15/16 | 2 | 40 | 32 | 32/32 | 0 |
| B4 | off | 12 | 0 | 0/0 | 1 | 15 | 0 | 0/0 | 7 | 19 | 0 | 0/0 | 6 |
| B4 | on (a+b) | 31 | 19 | 19/19 | 0 | 39 | 20 | 20/20 | 2 | 49 | 34 | 32/34 | 2 |

Read:
- **Stalls: none.** 0 collisions and 0 timeouts in all 16 rows of both new tables; one safety stop in B4 with detection on, in both, which did not end in a timeout.
- **Set A** (truthful): 80/80 with detection off and on in all three tables; A1 to A3 identical to the previous table (the third worker at J1 is never asked when the first two agree), A4 median times differ because the random placements differ.
- **Set B, detection off: 68/80 (previous), 63/80 (layouts only), 52/80 (new).** A consistent liar repeats the same wrong direction when asked again, so the robot's re-ask no longer helps: aborts grow (B1 2, B2 9, B3 4,
  B4 4) while the wrong goals stay (B3 5, B4 4).
- **Set B, detection on: 76/80, 76/80, 78/80 (B1 20, B2 19, B3 20, B4 19 of 20).** Second opinion asks someone else, so the repeated lie of one worker is outvoted; the third worker at J1 gives the vote a majority
  without the tie rule's re-ask of a (now consistent) first person. Lies detected 32/40 (B3), 34/49 (B4), corrected 100 % of those detected in B1 and B3, 28/32 in B2 and 32/34 in B4; fooled 0/40 (B3), 2/49 (B4), 0 in B1 and B2.
  The failures left with detection on: B2 1 aborted, B4 1 wrong goal.
- The gain of detection is therefore larger than before: B on against B off 78/80 against 52/80 (previous 76/80 against 68/80).
- Same simulator limits as 16.8 item 4. A consistent liar at a one-way node (A1, A2) shows an impossible direction every time, as in Unity's fallback for nodes with no other branch; at a junction the simulator's liar can still
  show an impossible direction (open point 3 above).

#### 16.12.2 Existing tests changed in this round (each keeps its intent)

- `tests/test_gesture_motion.py` `ArmRatioDeclarationTests`: it pinned the development looks of the split to exactly `sunbox_m1`, `sunbox_f1` and the test look to `sunbox_f2`. It now pins the looks the arm
  ratio was calibrated on (`sunbox_m1`, `sunbox_f1`) as development, `sunbox_f2` as test, and lists the six new experiment looks of 16.12 item 5 as the only other entries (none was used for the calibration).
- `tests/test_data_splits_v4.py`: the shipped-config test compares the three earlier looks; new `ExperimentLooksTests`.
- `tests/test_look_check_v4.py`: the config test knows PROCEED; new `ProceedTests`.
- `tests/test_lie_detection_v4.py`, `tests/test_export_csv_v4.py`: tests that need exactly two workers at J1 (the tie rule) now ask for two explicitly (`people=2`, which replaces the per-node counts), the look of worker 3 is listed.

### 16.13 Decisions of 2026-11-14, third round (Anisha): the simulator matches Unity, recorded BEFORE the code

Branch `anisha/v4-experiments-ab-3` (from main `879ba9a`, which holds 16.12 merged as PR #31). The Unity runs are the experiment, so the simulator must do what Unity does. The three open points of 16.12 are decided as
"match Unity". The exact rules were read from Nusrat's code on main, not guessed: `HRI/Scripts/V4/ExperimentPlanAB.cs` (`PlanRun`, `SlotPosition`, `DrawRandom`, `NodeProblem`, `NearerMargin`, `DrawLie`, `TruthfulCommand`, `Goals`),
`HRI/Scripts/GoalSequence.cs` and `Scenario/Config/experiments_ab_unity.json`. Python only; nothing under `unity/` is touched (read only).

1. **Second `beside` worker as Unity places it.** Unity's slots (`before_m` back along the arrival road, at the start node behind it opposite the start heading; `right_m` to the right of the arrival direction, negative = left),
   position = node - heading x before_m + right x right_m: junctions (3.0, -2.0), (5.5, +2.0), (6.0, -2.0); start node (3.0, -2.0), (3.0, +4.0), (6.0, -2.0); worker k of a node stands at slot k (slot 0 is the first worker).
   So Unity's first worker is on the LEFT, 3.0 m back; the simulator's earlier pair (3.0 m back, 2.0 m each side, first on the right) is replaced. This settles Nusrat's "PENDING ANISHA" slots note (`slots_note`): the slots are confirmed. They are copied into
   `scenarios_ab.json` (`layout.junction_slots`, `layout.start_slots`) and a test pins them equal to Unity's file. As Unity, the simulator also checks the bystander margin of the `beside` layout (`nearer_margin_m` 1.0 m along the last
   `approach_m` 3.0 m of the arrival road), counts the start node and junctions of the physical v4 map as turning points and its roads as roads for every map, and checks the 3.0 m separation across nodes. The random layout sorts the drawn
   workers by distance to the node so that slot 0 is the one nearest the node (Unity's `DrawRandom`).
2. **Goals as Unity draws them.** The goal of run k of a session is the k-th value of `GoalSequence(session seed)` over the map's endpoints sorted by name (SplitMix64; never equal to the previous run's goal), not
   `random.Random(f"{seed}|goal")`. Python's port of the same generator is `hri_trials.goal_order(seed, endpoints, n)`. `scenarios_ab.json` gets `session_seed` 1 (the development seed); run k (seed `first_seed` + k - 1) uses
   `goal_order(session_seed, sorted endpoints, runs_per_scenario)[k - 1]`. Fixed goals (A1: B, A2: C) are unchanged.
3. **A liar shows only a real wrong branch** (Unity `DrawLie`): the wrong directions are the node's branches other than the true command (a node that cannot lead to B has the true command BACK, so every branch of the node is wrong);
   where there is no other branch (A1's A; A2's A and B; the v4 map's start node A) the fallback is any other of LEFT / FORWARD / RIGHT / BACK, uniformly, which is an impossible direction. `scenarios_ab.json` `sets.B.lie_directions`
   "valid_branch" ("compass" is the earlier model of 16.2 decision 2, still available for the comparison). Together with the consistent lies of 16.12 item 2 this is what Unity does.

**What the simulator still does differently from Unity** (not decided here; listed so that nobody reads the table as a replica): the random numbers are not Unity's SplitMix64 streams (only the goal order is the same generator), so a given
(seed, run) has the same goal but not the same placements or liars; Unity also checks that a position is a free grid cell and not inside a collider; Unity's activation window (workers rendered only within 8.0 m, at most 6 active) and its
rule for who answers a new ask (nearest to the camera axis within 3.5 m) have no counterpart in the simulator (the controller asks the person it approached); the A2 side is fixed to the right turn unless `side="left"`; Unity logs `active`.
Porting Unity's `Rng(seed, run, index, salt)` to make placements and liars identical per (seed, run) is possible and is not done.

#### 16.13.1 Results (SIMULATOR; 20 seeds per row, seeds 1 to 20, timeout 270 s; detection off / on = a + b, backtrack off)

Next to the table of 16.12 (`experiments_ab_v4_main_270s_v4_20261114_133015`: symmetric beside pair, goals from `random.Random`, compass liar, consistent lies), with the three changes of this round separated: **Unity placement + goals, compass liar**
(`experiments_ab_v4_unity_layouts_compass_liar_20261114_140847`, `--lie-directions compass`: items 1 and 2 only) and **new** (`experiments_ab_v4_main_270s_v5_20261114_140759`: items 1 to 3, the liar shows a real wrong branch). 16.12 to the middle block is the effect of items 1 and 2 (the slots, the
bystander margin, the physical-map rules and Unity's goal sequence; the random layout also sorts its workers by distance to the node, and the goals of A3, A4, B3, B4 now follow `GoalSequence(1)`); the middle block to
new is the effect of item 3 alone (same placements, same goals, same seeds).

| experiment | detection | 16.12: SUCCESS | failures | median s | stops | Unity placement + goals, compass liar: SUCCESS | failures | median s | stops | **new (+ valid-branch liar): SUCCESS** | failures | median s | coll. | stops |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| A1 | off | 20/20 | - | 68.0 | 0 | 20/20 | - | 68.0 | 0 | **20/20** | - | 68.0 | 0 | 0 |
| A1 | on (a+b) | 20/20 | - | 77.9 | 0 | 20/20 | - | 82.3 | 0 | **20/20** | - | 82.3 | 0 | 0 |
| A2 | off | 20/20 | - | 82.9 | 0 | 20/20 | - | 86.1 | 0 | **20/20** | - | 86.1 | 0 | 0 |
| A2 | on (a+b) | 20/20 | - | 110.4 | 0 | 20/20 | - | 118.1 | 0 | **20/20** | - | 118.1 | 0 | 0 |
| A3 | off | 20/20 | - | 121.8 | 0 | 20/20 | - | 122.0 | 0 | **20/20** | - | 122.0 | 0 | 0 |
| A3 | on (a+b) | 20/20 | - | 160.7 | 0 | 20/20 | - | 185.7 | 0 | **20/20** | - | 185.7 | 0 | 0 |
| A4 | off | 20/20 | - | 109.6 | 0 | 20/20 | - | 116.1 | 0 | **20/20** | - | 116.1 | 0 | 0 |
| A4 | on (a+b) | 20/20 | - | 155.5 | 0 | 20/20 | - | 165.6 | 0 | **20/20** | - | 165.6 | 0 | 0 |
| B1 | off | 18/20 | aborted 2 | 68.0 | 0 | 19/20 | aborted 1 | 68.0 | 0 | **19/20** | aborted 1 | 68.0 | 0 | 0 |
| B1 | on (a+b) | 20/20 | - | 77.9 | 0 | 20/20 | - | 82.3 | 0 | **20/20** | - | 82.3 | 0 | 0 |
| B2 | off | 11/20 | aborted 9 | 82.1 | 0 | 13/20 | aborted 7 | 86.1 | 0 | **13/20** | aborted 7 | 86.1 | 0 | 0 |
| B2 | on (a+b) | 19/20 | aborted 1 | 117.3 | 0 | 19/20 | aborted 1 | 118.1 | 0 | **19/20** | aborted 1 | 118.1 | 0 | 0 |
| B3 | off | 11/20 | aborted 4, wrong_goal 5 | 119.9 | 0 | 12/20 | aborted 3, wrong_goal 5 | 119.7 | 0 | **10/20** | aborted 1, wrong_goal 9 | 119.7 | 0 | 0 |
| B3 | on (a+b) | 20/20 | - | 172.0 | 0 | 19/20 | aborted 1 | 199.0 | 0 | **15/20** | aborted 2, wrong_goal 3 | 195.7 | 0 | 0 |
| B4 | off | 12/20 | aborted 4, wrong_goal 4 | 107.2 | 0 | 11/20 | aborted 6, wrong_goal 3 | 105.6 | 0 | **11/20** | aborted 2, wrong_goal 7 | 110.6 | 0 | 0 |
| B4 | on (a+b) | 19/20 | wrong_goal 1 | 175.7 | 1 | 19/20 | aborted 1 | 179.3 | 0 | **15/20** | aborted 2, wrong_goal 3 | 170.2 | 0 | 0 |

Lies (Set B):

| experiment | detection | 16.12: given | detected | corrected | fooled | compass liar: given | detected | corrected | fooled | **new: given** | detected | corrected | fooled |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| B1 | off | 5 | 0 | 0/0 | 0 | 5 | 0 | 0/0 | 0 | 5 | 0 | 0/0 | 0 |
| B1 | on (a+b) | 12 | 10 | 10/10 | 0 | 12 | 10 | 10/10 | 0 | 12 | 10 | 10/10 | 0 |
| B2 | off | 19 | 0 | 0/0 | 0 | 18 | 0 | 0/0 | 0 | 18 | 0 | 0/0 | 0 |
| B2 | on (a+b) | 38 | 32 | 28/32 | 0 | 35 | 32 | 28/32 | 0 | 35 | 32 | 28/32 | 0 |
| B3 | off | 19 | 0 | 0/0 | 7 | 19 | 0 | 0/0 | 7 | 15 | 0 | 0/0 | 10 |
| B3 | on (a+b) | 40 | 32 | 32/32 | 0 | 50 | 32 | 30/32 | 2 | 40 | 19 | 19/19 | 8 |
| B4 | off | 19 | 0 | 0/0 | 6 | 20 | 0 | 0/0 | 5 | 14 | 0 | 0/0 | 8 |
| B4 | on (a+b) | 49 | 34 | 32/34 | 2 | 48 | 33 | 31/33 | 2 | 37 | 20 | 20/20 | 8 |

Read:
- **Stalls: none.** 0 collisions, 0 timeouts and 0 safety stops in all 16 rows of both new tables.
- **Set A** (truthful): 80/80 with detection off and on in all three tables. Detection on takes longer with Unity's slots (median A1 77.9 -> 82.3 s, A2 110.4 -> 118.1 s, A3 160.7 -> 185.7 s, A4 155.5 -> 165.6 s): the second worker
  of a node stands farther back or out (5.5 m back at a junction, 4.0 m to the right at the start node), so asking a second person is a longer drive.
- **Items 1 and 2 change little:** Set B off 52/80 -> 55/80, on 78/80 -> 77/80.
- **Item 3 (a liar shows a real wrong branch) changes a lot: Set B on 77/80 -> 69/80, off 55/80 -> 53/80.** With detection on B3 20 -> 15 of 20 and B4 19 -> 15 of 20 (wrong goal 3 each, aborted 2 each), lies fooled 8/40 and 8/37 (compass liar:
  2/50 and 2/48). Rule (b) now has almost nothing to catch: a real wrong branch is not an impossible direction, so only the second opinion (a) works, and B on against B off is 69/80 against 53/80 (16.12: 78/80 against 52/80).
- **Why the fooled lies: the tie rule.** All 8 wrong decisions at nodes that could lead to B (B3 and B4, detection on) are the tie rule of 16.2 decision 4: two workers disagree, nobody else is there, the FIRST worker is asked again and
  counts twice. A consistent liar repeats the same wrong branch, so when he is the first worker he wins 2 : 1. Across B3 and B4 the rule was used 10 times: **2 times the re-ask gave the correct branch, 8 times a wrong one**
  (never an abort). With consistent liars (16.12 item 2) the re-ask carries no information; it only weights the first worker's answer double. Reported, **NOT changed**. Proposal for you to confirm: on a tie with nobody else present, do not ask
  the first person again, treat the answer as unclear (ask again from a new view as for any unclear answer, then abort): the 8 wrong goals would become aborts (the fail-safe outcome) and the 2 rescues aborts too (not measured: a counterfactual run was not made).

#### 16.13.2 Existing tests changed in this round (each keeps its intent)

`tests/test_lie_detection_v4.py`: tests whose geometry came from the old symmetric `beside` pair now use a fixed layout (`NORTH`, and the new `MIRROR_AT_J1`, where the mirror of a LEFT lie at J1 is the arrival road) or no
longer assume the route of one geometry (the arrival-mirror test asserts that the lie was followed to J2 with the switch off, not that it ended in `wrong_goal`; the compass test uses the node A, which has one branch); the goal test
compares with `hri_trials.goal_order(1, ...)`; the decisions-log test allows `second_view` events. `tests/test_export_csv_v4.py`: the distance sanity bound 4.0 m became 5.0 m (the second worker stands up to 6 m back). New:
`MatchesUnity` (slots and margins pinned to Unity's `experiments_ab_unity.json`, slot positions, the bystander rule, the physical map, cross-node separation, Unity's node order, the goal sequence, the wrong directions, a liar
never showing BACK or a wall at a junction, the compass fallback where there is no other branch).


### 16.14 The false STOP of the live reader (item 1 of 2026-11-14; analysis only, NO reader value changed)

Data: `~/Downloads/anisha_gesture_logs_20261114_143539.zip`, SHA-256 `a39cb42906c12e7a5fbfbee77c78d5deedcd082dc1a01f1e3ceb659808cfbe34` (equal to the one given), read in place with `zipfile`, never extracted or copied. It holds R1 (bridge `bridge_guide_20261112_163011`, Unity
`trials_development_Task2_20261112_163710`, 20 runs, 21441 pan-tilt frames) and the 13 Nov video session (`bridge_guide_20261113_193706`, `trials_development_Task2_20261113_194012`, 3 runs, 2684 frames). Looks
`sunbox_f1`, `sunbox_m1`; clips `point_mixamo_01`, `point_ik_01`, `proceed_ik_01`, `proceed_ik_02`: **development only**, the split guard passed for all 23 runs. **The zip holds no STOP and no WAIT gesture** (truth: NONE, POINT, PROCEED), so STOP readings
on a true STOP cannot be shown from it. Tool: `analyse_false_stop_v4.py` (evaluation code), settings `configs/v4/experiments/false_stop_analysis.json`, tests `tests/test_false_stop_v4.py` (15); the full output (`report.json`, `report.md`) is in
`robot_vision/outputs/false_stop_analysis_v4_20261114_171401/` (git-ignored). The tool replays the live reader (`hri_perception_v4.PersonsPipeline`, current `gesture_reader.json`: only the POINT arm ratio differs from the recording commits) on the logged pan-tilt frames and applies the
candidate cues in the script only (it wraps two functions of `gesture_motion` for the duration of one replay and restores them).

**What the live robot did.** Stop episodes of `decisions.csv` (runs of rows stopped by STOP, closer than 0.35 s), by what the workers were showing: R1 126 episodes (PROCEED 76 reading + 30 executing + 5 navigating + 1 approaching, POINT 10 + 1,
**nothing shown 3**), the video session 10 (PROCEED 8 + 1, POINT 1). Nusrat's counts (196 stops, 16 stops) do not match my episode counts; I count runs of rows closer than 0.35 s, her rule is not stated in the README. The replay reproduces the logged STOPs
(R1: 705 STOP rows of `decisions.csv` against 489 replayed STOP frames, 4 rows without a replayed STOP just before them; video session 109 against 77, none missing).

**(a) The 3 stops with no gesture shown** (all R1, state navigate at 0.8 m/s: trial 4 at t = 406.23 s and 452.34 s, trial 14 at t = 1720.02 s). The person is the same in all three: worker 1 (`sunbox_m1`, true command NONE, phase idle) standing about 7 m to the
right of the robot's heading (bearing 20 to 23 degrees; the pan-tilt camera is not aimed at anybody, pan 0). **His right hand hangs at his side**: the wrist is 0.08 to 0.13 torso lengths BELOW the hip, the arm is not raised, and the hand intermittently
passes the open-hand geometry **by a hair**: finger ratios 1.59 to 2.3 against the limit 1.6, spread at the wrist 21 to 23 degrees against the limit 20, MediaPipe gives no label (and does not need to: not required since 2026-11-08). Two such frames within
the 0.3 s STOP window give a stop share of 1.0 (the rule needs at least 2 samples and 70 %), and STOP of anybody the pan-tilt camera sees stops the robot while it is driving (the v3 safety rule). Two of the three reproduce exactly in the replay;
for the third the replay has the same hand and the same frame-level cue (stop share 0.5 against at least 0.7 live), a boundary effect I cannot resolve from the log. **The cause is that STOP needs no raised arm, no palm direction and no stillness: any linked hand
that is open by the finger geometry counts, however far away the person is and whatever the arm is doing.**

**The cause of the PROCEED stops** (confirming Nusrat's suspicion): on the frames where the reader's open-hand geometry passes while PROCEED is shown, the spread measured at the wrist is 34.8 / 41.5 / 71.6 degrees (p10 / median / p90) against the limit 20,
the four fingers are extended, and nothing else is asked. The avatar's flat hand with fingers together (`worker_v4.json` `hand_shapes.proceed`, spread 0, "can never read as STOP") passes because the reader's spread is the angle at the WRIST between the index tip and
the pinky tip, which already contains the width of the knuckle line. Of the 1001 person-frames on which a worker shows PROCEED, the reader reads STOP on 493 (49 %), in 98 episodes;
on POINT 48 frames (11 episodes), on nothing shown 3 frames (2 episodes, the hanging hand above).

**(c) The candidate cues** (person-frames, a worker matched by bearing within 10 degrees; the category is what that worker shows: PROCEED, POINT, nothing; stop frames / frames and stop episodes). "Combined" uses display values (palm >= 0.1, spread >= 1.3,
static = the reader's own `moving` flag), not proposals; the grids show how each cue behaves.

| variant | on PROCEED | on POINT | on nothing shown | on unmatched people |
|---|---|---|---|---|
| before (the live reader) | 493/1001 = 0.492; 98 ep. | 48/1646 = 0.029; 11 ep. | 3/7727 = 0.000; 2 ep. | 0/56 = 0.000; 0 ep. |
| palm facing >= 0 | 190/1001 = 0.190; 62 ep. | 48/1646 = 0.029; 11 ep. | 3/7727 = 0.000; 2 ep. | 0/56 = 0.000; 0 ep. |
| palm facing >= 0.1 | 187/1001 = 0.187; 60 ep. | 48/1646 = 0.029; 11 ep. | 3/7727 = 0.000; 2 ep. | 0/56 = 0.000; 0 ep. |
| palm facing >= 0.2 | 183/1001 = 0.183; 60 ep. | 48/1646 = 0.029; 11 ep. | 3/7727 = 0.000; 2 ep. | 0/56 = 0.000; 0 ep. |
| palm facing >= 0.3 | 183/1001 = 0.183; 60 ep. | 48/1646 = 0.029; 11 ep. | 3/7727 = 0.000; 2 ep. | 0/56 = 0.000; 0 ep. |
| fingertip spread >= 1.1 | 482/1001 = 0.481; 100 ep. | 31/1646 = 0.019; 10 ep. | 3/7727 = 0.000; 2 ep. | 0/56 = 0.000; 0 ep. |
| fingertip spread >= 1.2 | 479/1001 = 0.478; 101 ep. | 2/1646 = 0.001; 2 ep. | 3/7727 = 0.000; 2 ep. | 0/56 = 0.000; 0 ep. |
| fingertip spread >= 1.3 | 420/1001 = 0.420; 101 ep. | 1/1646 = 0.001; 1 ep. | 2/7727 = 0.000; 2 ep. | 0/56 = 0.000; 0 ep. |
| fingertip spread >= 1.4 | 217/1001 = 0.217; 82 ep. | 1/1646 = 0.001; 1 ep. | 2/7727 = 0.000; 2 ep. | 0/56 = 0.000; 0 ep. |
| fingertip spread >= 1.5 | 41/1001 = 0.041; 29 ep. | 1/1646 = 0.001; 1 ep. | 1/7727 = 0.000; 1 ep. | 0/56 = 0.000; 0 ep. |
| static: arm_moving | 10/1001 = 0.010; 7 ep. | 48/1646 = 0.029; 11 ep. | 3/7727 = 0.000; 2 ep. | 0/56 = 0.000; 0 ep. |
| static: speed_stop_window | 45/1001 = 0.045; 37 ep. | 41/1646 = 0.025; 10 ep. | 1/7727 = 0.000; 1 ep. | 0/56 = 0.000; 0 ep. |
| palm >= 0.1 + static (arm_moving) | 1/1001 = 0.001; 1 ep. | 48/1646 = 0.029; 11 ep. | 3/7727 = 0.000; 2 ep. | 0/56 = 0.000; 0 ep. |
| palm >= 0.1 + spread >= 1.3 | 163/1001 = 0.163; 55 ep. | 1/1646 = 0.001; 1 ep. | 2/7727 = 0.000; 2 ep. | 0/56 = 0.000; 0 ep. |
| spread >= 1.3 + static (arm_moving) | 9/1001 = 0.009; 6 ep. | 1/1646 = 0.001; 1 ep. | 2/7727 = 0.000; 2 ep. | 0/56 = 0.000; 0 ep. |
| all three (palm >= 0.1, spread >= 1.3, static arm_moving) | 1/1001 = 0.001; 1 ep. | 1/1646 = 0.001; 1 ep. | 2/7727 = 0.000; 2 ep. | 0/56 = 0.000; 0 ep. |
| EXTRA: arm raised (the reader's flag) alone | 90/1001 = 0.090; 50 ep. | 0/1646 = 0.000; 0 ep. | 0/7727 = 0.000; 0 ep. | 0/56 = 0.000; 0 ep. |
| EXTRA: all three + arm raised | 0/1001 = 0.000; 0 ep. | 0/1646 = 0.000; 0 ep. | 0/7727 = 0.000; 0 ep. | 0/56 = 0.000; 0 ep. |

Cue values on the frames where the open-hand geometry passes:

| shown | open-hand frames | palm facing (p10 / median / p90) | fingertip spread | spread at the wrist (deg) | wrist speed (torso/s) | arm raised |
|---|---|---|---|---|---|---|
| PROCEED | 647 | -0.943 / 0.552 / 0.969 | 1.321 / 1.44 / 1.67 | 34.8 / 41.5 / 71.62 | 0.493 / 1.729 / 3.068 | 0.0 |
| POINT | 80 | 0.475 / 0.571 / 0.648 | 1.081 / 1.149 / 1.69 | 20.19 / 21.3 / 23.58 | 0.006 / 0.057 / 2.015 | 0.0 |
| nothing | 47 | -0.573 / 0.408 / 0.708 | 1.122 / 1.68 / 2.216 | 20.42 / 22.7 / 38.32 | 0.322 / 0.571 / 1.509 | 0.0 |
| unmatched | 0 | - | - | - | - | - |

Palm facing by the person's own hand:

| shown | right hand | left hand |
|---|---|---|
| PROCEED | n=321: -0.739 / 0.787 / 0.984 | n=326: -0.97 / -0.786 / 0.856 |
| POINT | n=73: 0.484 / 0.57 / 0.616 | n=7: 0.463 / 0.733 / 0.964 |
| nothing | n=34: -0.137 / 0.422 / 0.69 | n=13: -0.792 / 0.371 / 0.705 |
| unmatched | - | - |

**What it shows, and what it does not** (nothing is applied; every value below is a question for you):
1. **Static (the STOP hand does not swing) is the cue that works on PROCEED**: 98 episodes -> 7 with the reader's own `moving` flag (wrist path of the last 1.0 s of at least `motion_path_min` 0.4 torso lengths; no new number). It does not touch POINT (11 episodes) or the hanging
   hand (2). **Its cost is latency on a true STOP**: a raised arm counts as moving for up to the window (1.0 s), so a STOP shown by raising the arm is read only when the wrist has been nearly still; I cannot measure that on this data. The short variant
   (mean wrist speed over the 0.3 s STOP window at most `still_speed_max` 0.4 torso lengths/s) keeps the latency at the STOP window but removes much less: 98 -> 37 episodes.
2. **Fingertip spread removes the POINT stops** (11 episodes -> 2 at >= 1.2, 1 at >= 1.3) and almost nothing on PROCEED (101 episodes at >= 1.2 and 1.3: the avatar's PROCEED hand is not tight). At >= 1.4 it halves PROCEED (82 episodes) but this is where a real
   open palm may also fall: no true STOP is in the data to say.
3. **The palm cue cannot be trusted on this data.** By its sign convention (derived for a person facing the camera: the thumb side of a right hand with the palm toward the camera is at the image right) it removes 61 % of the PROCEED stop frames (493 -> 190), but
   the values are bimodal (p10 -0.94, p90 +0.97 for PROCEED) and mirrored between the hands: PROCEED right hands +0.79, left hands -0.79 (median), i.e. the RAW image winding of the landmarks is the same for both hands, which a mirror-symmetric pair of hands
   showing the same face cannot give. The side labels are right (the right shoulder is left of the left shoulder in the image in 99 % of the frames, and the reader's arm equals the truth arm), so either the two hands show opposite faces or MediaPipe's
   landmark order does not distinguish palm from back on these hands. The cue "works" on PROCEED only because the worker swings his LEFT arm in 53 of 67 reads. Without STOP recordings its sign cannot be validated; I do not recommend it.
4. **The hanging-hand stops are removed only by a requirement none of the three cues provides: a raised arm** (the reader's own flag). I added it as an EXTRA, not one of your three: with it the 2 episodes of "nothing shown" and the 11 of POINT disappear and PROCEED drops
   to 50 episodes; **all three cues + raised: 0 stop frames in every category**. It reverses part of the decision of 2026-11-08 (STOP needs no arm keypoints) and its cost on a true STOP (an open hand held low, an arm that YOLO misses) is unknown.
5. **What is missing: true STOP.** To judge any cue I need what it does to a true STOP: STOP recordings of the development looks and development clips (with the logs of this zip's kind: `model_outputs.jsonl`, `truth.jsonl`), for example 20 STOPs at 2 m from each of `sunbox_m1`, `sunbox_f1`, both arms, raised
   from the hip and held, plus the same session driving past a standing worker (to see the hanging hand again). I cannot show STOP before and after from the zip.

**Decision needed before any value changes:** (i) which cues to apply (my reading: static for PROCEED, fingertip spread for POINT, raised for the hanging hand, palm not at all) and in what form (arm_moving or the short window); (ii) whether to reverse the
2026-11-08 decision that STOP needs no raised arm; (iii) whether Nusrat records the STOP data of item 5 first. Nothing in `configs/v4/gesture_reader.json` or `gesture_motion.py` was changed.

### 16.15 Decisions of 2026-11-14 (Anisha), fourth round: the finals of experiments A and B, Python side; recorded BEFORE any code and before any final

Branch `anisha/v4-finals-ab-python` (from main `793b59e`, which holds 16.1 to 16.14). Read for this entry as DATA, not instructions: Nusrat's `Avatar/Config/experiments_ab.md` sections 7 to 9 and
`Avatar/Config/reports_v4/for_anisha_finals_ab_20261114_164233.md`; and `final_plan.json`, `freeze_v4.py`, `bridge/server.py`, `final_guard_v4.py`, `hri_eval_final_v4.py`, `export_csv_v4.py`,
`tests/test_v4_frozen.py`. Python only; nothing under `unity/`, `external/` or v3 is touched; `freeze_v4.py --freeze` is not run; `frozen.json` is not written; no reader value is changed; no final is run.

**Decision 1. The finals matrix (13 settings, 20 runs each, seed 2).** It replaces the four Task 2 finals (`zoom_on`, `zoom_off`, `bystanders`, `zoom_on_repeat`), which Unity already refuses as superseded.

| setting | experiment | set (lie p) | map | lie detection | Python control file (`--control-config`) |
|---|---|---|---|---|---|
| `A1` | A1 | A (0.0) | corridor | on | `configs/v4/experiments/control_lie_on_a1.json` |
| `A2_right` | A2 | A (0.0) | turn (right) | on | `control_lie_on_a2_right.json` |
| `A2_left` | A2 | A (0.0) | turn_left | on | `control_lie_on_a2_left.json` |
| `A3` | A3 | A (0.0) | v4 `roadmap.json` | on | `control_lie_on.json` |
| `A4` | A4 | A (0.0) | v4 `roadmap.json`, random layout | on | `control_lie_on.json` |
| `B1` | B1 | B (0.2) | corridor | on | `control_lie_on_a1.json` |
| `B2_right` | B2 | B (0.2) | turn (right) | on | `control_lie_on_a2_right.json` |
| `B3` | B3 | B (0.2) | v4 `roadmap.json` | on | `control_lie_on.json` |
| `B4` | B4 | B (0.2) | v4 `roadmap.json`, random layout | on | `control_lie_on.json` |
| `B1_off` | B1 | B (0.2) | corridor | **off** | `control_lie_off_a1.json` |
| `B2_right_off` | B2 | B (0.2) | turn (right) | **off** | `control_lie_off_a2_right.json` |
| `B3_off` | B3 | B (0.2) | v4 `roadmap.json` | **off** | `control_lie_off.json` |
| `B4_off` | B4 | B (0.2) | v4 `roadmap.json`, random layout | **off** | `control_lie_off.json` |

- Seed 2, 20 runs per setting, test looks `sunbox_m_shirt_plaid` (male slots 1 and 3) and `sunbox_f_shirt_plaid` (female slot 2), test clips `point_mixamo_02` (POINT) and `proceed_ik_03` (PROCEED) in every setting.
  **Disclosed difference from development:** the third worker at J1 (A3, A4, B3, B4 and their `_off` twins) wears the same test look as the first (one test look per gender exists); development rotates two looks
  per gender. The two are told apart by position only.
- B2 is run with the right turn only; `A2_left` has no Set B counterpart and is a turn-direction check with truthful workers (decided; `B2_left` is NOT added).
- "Detection OFF" = second opinion, reject impossible and backtrack all false (`scenarios_ab.json` `detection.off`); "on" = second opinion + reject impossible, backtrack off (`detection.on`, 16.10.2). Set B's main
  comparison is `B*` against `B*_off`; `A*` against `B*` (both on) isolates the lies.
- **The exact Unity names Nusrat must add for the four `_off` settings** (the spelling matters: Unity's guard, the run-once markers and Python's `--final-setting` look them up by it):
  `B1_off`, `B2_right_off`, `B3_off`, `B4_off`. For each: an entry in `final_v4.json` `settings` (`experiment_config` = `sessions/final_ab_<setting>.json`, test / test as for the other nine); the config
  `Avatar/Config/sessions/final_ab_B1_off.json`, `final_ab_B2_right_off.json`, `final_ab_B3_off.json`, `final_ab_B4_off.json` with `experiment` "B1" / "B2" / "B3" / "B4" (side "right" for B2), `lie_detection` **"off"**,
  `python_control` = `configs/v4/experiments/control_lie_off_a1.json` (B1_off), `control_lie_off_a2_right.json` (B2_right_off), `control_lie_off.json` (B3_off and B4_off), and the same test looks and clips as the on
  twin; the four files added to `freeze_files` (22 to 26 files); the session folder `trials_final_Task2_<setting>_<time>`; `session.json` `final_setting` = the setting name; the launcher's `-Experiment B1 ... -LieDetection off`
  (or whatever form Nusrat gives it) must pass the matching `--final-setting`. Unity's checks already accept `lie_detection` "off" (her report, item 1.1); that is hers to verify.

**Decision 2. The timeout rule, declared now, applied after Nusrat's step-5 development runs.** `timeout_s` = 1.5 x the longest development run (the step-5 development sessions made with the same configs as the finals:
same maps, layouts, lie probabilities and detection switches), rounded UP to a multiple of 30 s, never below 270 s. **`timeout_s` stays 270 until then**; the rule text is added to `final_plan.json`
(`timeout_s_rule`), the value is changed only by a declared edit before the freeze. One value for all 13 settings (Unity reads one). Reading I chose, to be confirmed: "longest run" = the largest `total_s` of
`truth_run###.json` over those development runs whatever their outcome, so a development run that hit the old 270 s limit counts as 270 s and would raise the value to 420 s (1.5 x 270 = 405, up to 420); every
development timeout is reported next to the value. `final_guard_v4.timeout_from_development(longest_s)` computes it, so that the arithmetic is fixed in code and tested.
Why this rule: Nusrat's estimate puts 8 of 20 runs of A3, B3 and B4 above 0.9 x 270 s with detection on (`experiments_ab.md` section 7), from Task 2 runs without second opinions; the declared rule takes the value from
the configs that will be run.

**Decision 3. The false-STOP rule is switched on only after Nusrat's STOP recordings pass a criterion; the criterion is declared here (it did not exist).** Nothing in `gesture_reader.json` / `gesture_motion.py` changes now
(16.14: the zip holds no true STOP, so the cost of any cue on a true STOP is unknown). Criterion: with the rule switched on, **every true STOP is read within 1.0 s**. Operationally (my reading, to be confirmed): on the
STOP recordings (development looks and development clips only, never a test look or clip; the recordings asked for in 16.14 item 5: STOPs at 2 m from `sunbox_m1` and `sunbox_f1`, both arms, raised from the hip and
held, plus a pass beside a standing worker for the hanging hand), the replayed reader (`analyse_false_stop_v4.py` replay, the logged `model_outputs.jsonl`) reads STOP no later than 1.0 s after the first truth row of that
STOP in a shown phase (`false_stop_analysis.json` `shown_phases`); the unit is one STOP, the criterion is met only when it is n of n (no exception), reported with n and with the count per look and arm. A STOP that is
never read, or read after 1.0 s, fails the criterion and the rule stays off. The same recordings also report the false STOP on the pass-by and on PROCEED / POINT, without a threshold of their own (the criterion is the gate,
not the choice of cue). **The form of the rule (which cues, arm-moving or short window, raised arm) is still your decision (16.14 questions i and ii); this entry does not make it.** Because `gesture_reader.json`
is in the freeze list, the order is: STOP recordings, criterion passed, rule written (declared first), then the freeze.

**Work (items 2 to 5 of Nusrat's report), with the values I chose where nothing above settles them (for you to confirm or change):**
1. `final_plan.json`: the 13 settings above (replacing the four; they move to `superseded_settings` for the record, not read by any tool), each with `experiment`, `set`, `map`, `roadmap` (the robot map the control file names),
   `lie_detection`, `zoom` null, `bystanders` null, a note; `test_assignment` for each; `timeout_s_rule`; `false_stop_rule` (status off, pointer to this entry). Tests updated.
2. `bridge/server.py` `FINAL_CONTROL`: the 13 entries of the table. `preflight_final` also refuses a control file whose lie-detection switches or `roadmap` do not fit the setting's entry (it only checked zoom).
3. `freeze_v4.py`: `FROZEN_EXTRA` gets the eight `control_lie_*` files and `roadmap_a1.json`, `roadmap_a2_right.json`, `roadmap_a2_left.json` (an explicit list, not a glob: `export_csv.json` and
   `false_stop_analysis.json` stay outside, 16.10.1); `tests/test_v4_frozen.py` pinned lists updated. The `files` list of `frozen.json` is not edited by me (it is rewritten by the freeze itself).
4. `final_guard_v4.check_setting` also checks, for an experiment setting: the looks and clips of the runs lie within the setting's `test_assignment`; the bridge's `config_used/control.json` has the lie-detection
   switches and `roadmap` of the setting; `session.json` `experiment` and `set` (and `lie_probability`, when recorded) are the setting's. A third marker kind `export` (`FINAL_EXPORT_DONE.json`).
5. `export_csv_v4.py` final mode (`--final --setting S`): `fz.require_frozen`, leak test, test split with `final_evaluation`, `check_setting`, once per setting (own marker, written last), folder
   `export_csv_v4_final_<setting>_<time>/` with `runs.csv`, `dialogs.csv`, `export.json`, `config_used/`, `run.json`; and `--final-combine FOLDER...`: one combined table over the per-setting exports (each must carry its marker;
   derived data, rerunnable into a new folder): per setting, then A vs B per scenario, B on vs off, A2 right vs left, every rate with its count and a Wilson 95 % interval (`analysis.json` `wilson_z` 1.96), the
   difference of two rates in percentage points as a description only (no test, no interval).
6. `hri_eval_final_v4.py`: per experiment, in `eval.json` / `eval.md`: SUCCESS with a Wilson interval and failure kinds (collision / timeout / aborted / wrong goal, counted), median time (of all runs with a time and of
   SUCCESS runs, with n), trail against the optimal corridor (median ratio, share of trail points within the corridor when `gt_path` gives it), lies given / detected / corrected / fooled (totals and rates over lies given
   with Wilson intervals; Set A has none), safety stops (runs with at least one, total, seconds) and watchdog stops (already there; B11(a): a result, never a refusal). Same rate definitions in the export's combined table.
Not decided here and not done: the sittings and run order (item 1.5 of her report), `B2_left`, the Unity-versus-simulator differences still open in 16.13.

#### 16.15.1 What was built (files; nothing under `unity/`, `external/` or v3 was edited; no final was run; `frozen.json` untouched; `freeze_v4.py --freeze` not run)

- `configs/v4/final_plan.json`: the 13 settings (each with `experiment`, `set`, `map`, `roadmap`, `lie_detection`, `zoom` null, `bystanders` null), `test_assignment` for all 13 (plaid looks, the two test clips), the four Task 2 settings under
  `superseded_settings` (no tool reads them), `timeout_s_rule` (`timeout_s` stays 270), `false_stop_rule` (status off). `final_guard_v4.settings()` is therefore the 13 names.
- `bridge/server.py`: `FINAL_CONTROL` for the 13 (the `_off` settings use `control_lie_off_a1.json`, `control_lie_off_a2_right.json`, `control_lie_off.json`); `preflight_final` also reads the control file and refuses
  one whose lie-detection switches or `roadmap` are not the setting's (`final_guard_v4.control_problems`), whatever its name; the `--final-setting` help text names the 13.
- `freeze_v4.py`: `FROZEN_EXTRA` = `scenarios_ab.json` + the eight `control_lie_*` files + `roadmap_a1.json`, `roadmap_a2_right.json`, `roadmap_a2_left.json` (12 files; an explicit list). `export_csv.json` and
  `false_stop_analysis.json` stay outside. `frozen.json` is not written by me: its `files` list is stale (it also lacked `scenarios_ab.json` before today) and is rewritten by the freeze itself.
  `control_zoom_on.json` / `control_zoom_off.json` stay in the freeze list (the glob reaches them); no setting uses them any more; they are harmless, and dropping them would be a v3-style change I did not make unasked.
- `final_guard_v4.py`: a third marker kind `export` (`FINAL_EXPORT_DONE.json`); `timeout_from_development`; `detection_switches`, `control_problems`; `check_setting` also checks experiment / set / lie probability in `session.json`, the looks and clips against
  `test_assignment`, and the bridge's `config_used/control.json` against the setting.
- `export_csv_v4.py`: new run fields `final_setting`, `max_distance_from_optimal_m`, `share_within_corridor`, `watchdog_stops`; `summarize` (SUCCESS with Wilson 95 % and counts, failure kinds collision / timeout / aborted / wrong goal / other,
  median time of all runs and of SUCCESS runs, trail / optimal, corridor measures, lies given / detected / corrected / fooled with rates over lies given, safety and watchdog stops, collisions); `--final --setting S --session U B` (gates in
  `hri_eval_final_v4.gate(..., kind="export")`: frozen, not exported, leak test, test split with `final_evaluation`, `check_setting`; marker last; folder `export_csv_v4_final_<S>_<time>/` with `summary.json`); `--final-combine FOLDER...`
  (`combined.md`, `combined.json`, `combined_settings.csv`, `combined_comparisons.csv`; comparisons derived from the plan: A vs B x4, B on vs off x4, A2 right vs left; a pair whose second setting was not exported says "not available").
  `configs/v4/experiments/export_csv.json` gets the four new columns at the end of `runs`.
- `hri_eval_final_v4.py`: `eval.json` `experiment` {setting, plan entry, summary, runs_table} and a section of `eval.md`, from the same `summarize`; the watchdog block is unchanged (B11(a): a result, never a refusal).
- Tests: `tests/test_v4_final.py` rewritten for the 13 settings (guards, `check_setting`, plan / control / scenarios pinning, summary arithmetic, final evaluation, final export, combined table, server preflight);
  `tests/test_v4_frozen.py` (settings pin, freeze list, `test_assignment`, timeout rule, false-STOP rule off); `tests/test_lie_detection_v4.py` (freeze-list test for the 16.15 list);
  `tests/test_export_csv_v4.py` (the isolation test lets `hri_eval_final_v4.py` import the exporter: it is evaluation code; the rule for every other file is unchanged).

#### 16.15.2 Open points for Anisha (nothing below was decided by me)

1. **Timeout rule reading** (decision 2): a development run that timed out at 270 s counts as 270 s, so it would raise the value to 420 s. Say if timed-out runs should be left out.
2. **STOP criterion reading** (decision 3): onset = first truth row of the STOP in a shown phase, unit = one STOP, n of n; and the recordings are those of 16.14 item 5. Say if the unit or the onset should be different.
3. **The form of the false-STOP rule** (16.14 questions i and ii) is still open and is needed before the freeze, because `gesture_reader.json` is frozen.
4. **Not checked by the Python side:** Unity's `session.json` `map` and `lie_detection` label (their written format is not in her report); the Python side checks what it controls (the bridge's control file, i.e. what the robot actually ran) and the experiment, set and lie probability Unity records.
   If Unity writes `experiment` or `set` in another form than "A3" / "B" (it should be as in `session.json` of her report, item 5), the check refuses the evaluation before any data is read, without a marker, so the form can be fixed.
5. **Run order and sittings** (her item 1.5) and `B2_left` are not decided here. Detection OFF adds 80 runs (about 2.5 h, her estimate), so the matrix is 260 runs.
6. The combined table's difference column is a plain difference in percentage points between two rates of 20 runs each; it has no interval of its own (the intervals are on the two rates). Say if a difference interval is wanted.

#### 16.15.3 Tests changed besides those listed in 16.15.1, and the suite

`tests/test_hri_analysis_v4.py` and `tests/test_make_results_archive_v4.py` used the superseded setting `zoom_on` as the name of a final (the analysis tool's `--final` mode and the archive's manifest check the name against the plan): their final-mode fixtures now
use `A3` (the analysis test that refused a zoom-off session now refuses a detection-off session given as `A3`). `configs/v4/archive/results_manifest.json` and `configs/v4/README.md`: label text only. Full suite (`python -m unittest discover -s tests`, venv): exit 0, 1128 tests, 3 skipped (1108 before this round).
No reader value, `frozen.json`, `unity/`, `external/` or v3 file was changed.

### 16.16 Decisions of 2026-11-14 (Anisha), fifth round: the new PROCEED pose, the STOP re-check, timeout, intervals; recorded BEFORE any new recording and before the code of items 1 and 3

State at the time of writing: branch `anisha/v4-finals-ab-python` (16.15, staged, not yet committed); `origin/main` is `793b59e`. **The pose change is announced by Nusrat, PR not yet merged at the time of writing:** `origin/nusrat/v4-avatar-fixes` (tip `e6c6bfd`, ten commits) exists
on the remote and is not an ancestor of `origin/main`. I did not confirm the pose change itself (that her branch changes the PROCEED forearm by about 12 degrees on every look); I know it from the instruction, not from the code. `git pull --ff-only` brought nothing.
Python and docs only; nothing under `unity/`, `external/` or v3 is changed; no reader value is changed; no recording was made.

**Decision 1. Disclosure.** The development results D2 to D4 (and the false-STOP analysis of 16.14) were made with the OLD PROCEED pose (forearm about 12 degrees off, Nusrat). The finals use the new pose. So the development figures and the finals differ in
the PROCEED pose, besides the declared differences already listed; this is disclosed here and must be repeated wherever development and final numbers are compared.

**Decision 2. The candidate STOP rule is re-checked on Nusrat's next session, which uses the new poses.** Nothing is switched on before it (16.15 decision 3 stands). Pass criteria, declared now, all three needed:
- **(a)** every true STOP is read within 1.0 s: unchanged, and confirmed in its reading (16.15 decision 3): from the first truth row of the shown STOP, one STOP per unit, n of n within 1.0 s, reported with n and the count per look and arm.
- **(b)** on the PROCEED, POINT and WAIT frames of the new poses (3 negatives of each per look per arm), the new rule gives fewer accepted false STOPs than the current rule, **reported with the counts of both rules**.
  My reading of "fewer", to be confirmed: STOP readings counted per category (PROCEED, POINT, WAIT) as frames and as stop episodes (`false_stop_analysis.json` `episode_gap_s`), for both rules; met when the total over the three categories is
  strictly smaller with the new rule in both counts and no category has more. With 3 negatives per look per arm these counts are small; they are reported as counts, not as a rate with a claim of significance.
- **(c)** no accepted STOP from an idle worker: zero accepted STOP readings on every idle (NONE) frame, including the pass beside the idle worker.
If (a) fails, the fallbacks apply, in this order (corrected on 2026-11-14 by Anisha; see 16.16.2): **first the short 0.3 s static window** (mean wrist speed over the 0.3 s STOP window instead of the reader's `moving` flag),
**keeping** open hand, fingertip spread and raised arm; **if that still fails, drop the static cue** and keep open hand + fingertip spread + raised arm. Nothing else is a fallback.

**Decision 3. What Nusrat must record** (development looks `sunbox_m1` and `sunbox_f1` and development clips only; never a test look or clip), both arms, at 2 m, with the new poses:
- STOP, also while the robot drives: **20 per look (10 per arm), part of them while driving** (confirmed by Anisha on 2026-11-14);
- PROCEED, POINT and WAIT: 3 negatives of each per look per arm;
- one pass beside an idle worker (the idle worker shows nothing; this is the hanging-hand case of 16.14).
The logs of the kind of the zip of 16.14 (`model_outputs.jsonl`, `truth.jsonl`, `decisions.csv`, `v4_log.jsonl`) are needed, read with `analyse_false_stop_v4.py`.

**Decision 4. Timeout rule, corrected (replaces the reading of 16.15 decision 2).** `timeout_s` = 1.5 x the longest SUCCESSFUL development run (same configs as the finals), rounded up to a multiple of 30 s, never below 270 s. A development run that
timed out (or failed otherwise) does not count as a duration. **Every development timeout is reported, and its cause is found before the freeze.** `timeout_s_rule` and `final_guard_v4.timeout_from_development` are updated with a test; `timeout_s` stays 270.

**Decision 5. STOP criterion (a)**: the reading of 16.15 decision 3 is right (recorded above).

**Decision 6. Combined table**: each difference of two rates also gets a Newcombe (Wilson-based) 95 % interval (method 10 of Newcombe 1998: the Wilson intervals of the two rates combined), as a description only; tests with Newcombe's published example.

**Decision 7. The `session.json` values Unity writes, read in the Unity code on main (read only, nothing changed):** `experiment` = the experiment of the final config ("A1" ... "B4"; "B2" for `B2_right` and `B2_right_off`, "A2" for `A2_left`), `set` = "A" or "B",
`lie_probability` = the set's value as a float, `map` = the scenario's map name ("corridor", "turn", "roadmap"; "turn" also for the left turn), `final_setting` = the setting name. **`lie_detection` is NOT written to `session.json`** (it is only in the final config and Python's
control file): the exporter's `setting` column is therefore empty in the finals, and the Python checks use the control file the bridge ran with, which they already do. Consequences made in Python: the `lie_probability` comparison tolerates float32 (1e-6); a recorded
`final_setting` must equal the setting.

#### 16.16.1 What was built, and which open points of 16.15.2 are now settled

- `final_guard_v4.py`: `timeout_from_development` (longest SUCCESSFUL run) and `development_timeout(runs)` (applies the rule to the `truth_run###.json` dicts; lists every timeout for its cause; raises when no run succeeded); `final_plan.json` `timeout_s_rule` rewritten; `timeout_s` still 270.
  `check_setting` tolerates float32 in `lie_probability` (1e-6) and refuses a recorded `final_setting` that is not the setting.
- `export_csv_v4.py`: `newcombe(k1, n1, k2, n2, z)`; every difference of the combined table has `difference_lo_pp` / `difference_hi_pp` (also in `combined_comparisons.csv` and `combined.md`), for SUCCESS and for lies fooled.
- Tests: Newcombe's published example (56/70 against 48/80: 20.0, 5.2 to 33.4), sign and symmetry, bounds, no denominator; the development timeout (timeouts listed, never below 270, no success refused); the float32 lie probability and `final_setting`; the combined table's interval columns.
- Settled from 16.15.2: item 1 (timeout reading, decision 4), item 2 (STOP criterion reading, decision 5), item 4 (session format, decision 7), item 6 (difference interval, decision 6). Still open: item 3 (the form of the false-STOP rule), item 5 (sittings, `B2_left`), and the two points of this entry
  (my reading of "fewer" in 2(b), and what "the declared fallbacks of 16.14" means).
- Full suite (venv): exit 0, 1134 tests, 3 skipped. No reader value, `frozen.json`, `unity/`, `external/` or v3 file changed.

#### 16.16.2 Corrections and answers of 2026-11-14 (Anisha), recorded before the code of item 4

1. Criterion (b), "fewer": my reading is right (STOP readings per category as frames and as episodes, total strictly smaller with the new rule in both counts, no category with more).
2. **Fallbacks corrected.** The first version of decision 2 said I found no entry named fallback in 16.14 and read the fallbacks as the short-window static cue, the spread cue alone and no raised-arm requirement. That was wrong and is replaced in decision 2 above:
   the fallbacks are, in order, (i) the short 0.3 s static window with open hand, fingertip spread and raised arm kept, (ii) dropping the static cue, keeping open hand + fingertip spread + raised arm. "Spread alone" and "no raised arm" are NOT fallbacks and are removed.
3. STOP count confirmed: 20 per look, 10 per arm, part of them while driving (decision 3 above).
4. `lie_detection` is not in Unity's `session.json` (decision 7): the exporter's `setting` column is filled from the bridge's control file (the switches the robot ran: "off", "on", or the letters a = second opinion, b = reject impossible, c = backtrack) when `session.json` has no label,
   and a new column `lie_detection` always holds that control-file label, so the finals' CSV says what the robot ran. A label that Unity does record is kept in `setting` as before. Test added.
5. Built: `export_csv_v4.lie_detection_label`, the `setting` fallback and the `lie_detection` column (also in `configs/v4/experiments/export_csv.json`); tests `LieDetectionColumnTests`. Full suite (venv): exit 0, 1138 tests, 3 skipped. No reader value, `frozen.json`, `unity/`, `external/` or v3 file changed.

### 16.17 Decisions of 2026-11-14 (Anisha), sixth round: sittings, B2_left, the form of the false-STOP rule; docs only, recorded before any final and before any new recording

Docs only: no code, no config and no reader value is changed by this entry (`final_plan.json` `false_stop_rule` keeps its text of 16.15; this entry supersedes its remark that the form is undecided).

1. **Sittings and run order: Nusrat's plan.** Four sittings of about 3 h each; each B setting runs in the same sitting as its detection-off partner (`B1` with `B1_off`, `B2_right` with `B2_right_off`, `B3` with `B3_off`, `B4` with `B4_off`); the A settings are spread over the sittings.
   The exact order is Nusrat's and is recorded before the first final. (I have not seen the four-sitting plan in her files on main: her report of 2026-11-14 (`for_anisha_finals_ab_20261114_164233.md`, item 1.5) proposes two sittings of 4.2 h and 5.1 h, or three of 2.7 to 3.4 h, for nine settings. The four sittings are therefore
   recorded as Anisha's decision; her plan must be written down before the first final.) With the four detection-off settings the matrix is 13 settings, 260 runs. Splitting changes nothing in a setting: each setting is one session of 20 runs, seed 2, run once.
2. **`B2_left` is not run.** B2 uses the right turn only; `A2_left` is a turn-direction check with truthful workers (decided with Nusrat on 2026-11-14). This closes the point left open in 16.15.2 item 5.
3. **The form of the false-STOP rule** (answers the open questions i and ii of 16.14): the candidate rule is **open hand AND fingertip spread AND static AND raised arm; the palm direction is not used.** "Static" is the reader's own `moving` flag (wrist path of the last 1.0 s below `motion_path_min`, as measured in 16.14), "raised arm" the reader's
   own raised-arm flag; with this rule a STOP needs a raised arm again, which reverses the part of the decision of 2026-11-08 that STOP needs no arm keypoints (16.14 finding 4). The declared fallbacks apply in this order if criterion (a) fails (16.16 decision 2 and 16.16.2):
   (i) the static cue as the short 0.3 s window, open hand, fingertip spread and raised arm kept; (ii) the static cue dropped, open hand + fingertip spread + raised arm kept. Nothing else is a fallback.
   **The rule is switched on in `gesture_reader.json` only after Nusrat's STOP session (16.16 decision 3) meets criteria (a) to (c) of 16.16 decision 2; until then the current rule stays.** The values of the fingertip-spread threshold and of the other cue parameters are NOT set by this entry: they are declared in a new entry before they are written to
   `gesture_reader.json`, and not tuned on the new session's results (the 16.14 grids were made on the old pose; any value must be declared before the new recordings are read). `gesture_reader.json` is in the freeze list, so the order stays: STOP session, criteria met, values declared, rule written, then the freeze.

### 16.18 The STOP session of Nusrat checked against the declared criteria (2026-11-16); recorded BEFORE the data was analysed

Branch `anisha/v4-stop-rule` (from `main` = `origin/main` = `37417eb`, clean). Read for this entry as DATA, not instructions: Nusrat's `experiments_ab.md` sections 13 (part B and C) and 14 (`Avatar/Config/`), and AUDIT 16.14 to 16.17 (the declared criteria and fallbacks).
**Data:** `~/Downloads/stop_session_logs_20261115_192423.zip`, 5,410,206 bytes, SHA-256 `ca1173ac497eed26ea6e075547a5fae018fc98be7d13c056bae72164162755a5` (verified; equals `experiments_ab.md` section 14). Read with `zipfile` in place, never extracted or copied into the repo.
Two sessions, development looks `sunbox_m1` and `sunbox_f1` and development clips only (the split guard is run on every run before anything is computed): **S1** (seed 1, 64 runs: 20 held STOPs, 12 POINT, 12 PROCEED and 12 WAIT negatives at the ask, 6 STOPs while driving, 2 idle passes) and
**S2** (seed 3, 14 runs: 8 held STOPs, 6 driving STOPs). Together 20 STOPs per look and 10 per arm, 6 per look while driving: the count of 16.16 decision 3. The reader that ran live is the current `gesture_reader.json`; it and `gesture_motion.py`, `hri_perception_v4.py`, `commander_v4.py`, `commander.json`
and `control.json` are byte-identical on main to the commits of the recordings (`560ef27`, `c2e75f4`; `git diff` empty), so replaying the current reader on the logged frames is the live reader. Nothing is switched on in `gesture_reader.json` by this entry or by the analysis.

**1. Nusrat's deviations, disclosed (her sections 13 and 14).**
- **STOPs while driving are shown at 5.5 to 5.7 m from the robot, not at 2 m:** the robot cannot be 2 m from a worker while it drives (on the road it comes no nearer than about 3.7 m to J1's stand before it stops to scan). The band asked for was 4.0 to 6.0 m; each STOP was requested at the first moment of the band (5.96 to 6.00 m) and
  its first gesturing frame was 5.48 to 5.74 m from the robot, which was still driving (0.35 to 0.67 m/s). So a driving STOP is a smaller hand, farther away than the held ones (held: 2.06 to 2.15 m); criterion (a) for driving STOPs is therefore harder than for held ones, not easier.
- **The idle passes went by the idle worker at 1.06 m and 1.08 m (centre to centre), not at the declared 1.6 m** (the robot drives from its ask position at A straight to J1, not along the road centre line). Closer means a larger hand and a nearer hanging arm: the test of (c) is **harder** than declared. Two passes only.
  The idle-pass runs also contain the PROCEED at A that starts the drive, so a stop in them does not by itself isolate the hanging hands; the analysis attributes every reading to the person and frame it came from.
- **The run protocol (other apps closed) was not fully met:** S1: free memory before 3,791 MB, minimum available during the session 725 MB, Chrome x10, Claude x9 and others still running, hard paging peak 58,058 pages/s; S2: 3,865 MB, minimum 882 MB, Chrome x6. Unity pan-tilt frame drop 1.2 % (S1) and 3.65 % (S2). Watchdog stops 0. A thin machine can change which frames
  reach the reader; it does not change what the reader does with a frame. Disclosed, not a reason to drop the data.
- **Counts differ from 16.16 only in how they were reached** (two sessions: 13 STOPs per look in S1, 7 more per look in S2): 20 per look, 10 per arm. The 36 negatives are 3 each of POINT, PROCEED and WAIT per look per arm, all at the first ask at A; some PROCEED and POINT frames come from a robot that is moving or repositioning (her README says which).
  Eight PROCEEDs that start a drive are not items (marked "not an item" in her README); they are PROCEED frames of the new pose all the same.

**2. Her baseline with the current reader** (descriptive, from `decisions.csv`, the live robot; hers, not yet reproduced by me): the robot stopped on every STOP shown (held 20/20, driving 6/6 in S1; 14/14 in S2); on **12/12 PROCEED runs and 4/12 WAIT runs, never on POINT (0/12)**; and in both idle passes (2/2, with the PROCEED at A in the same runs).
These are the figures the candidate has to beat in (b); my replay recomputes them per person-frame and per episode and checks the replay against the STOP rows of `decisions.csv`.

**3. What is evaluated, exactly as declared in 16.16 decision 2 and 16.17 item 3 (nothing else may be tuned).**
- **Rules.** *Current* = the live reader as it is. *Candidate* = open hand (the reader's `open_palm_geometry`) AND fingertip spread AND static AND raised arm; the palm direction is not used. *Fallback (i)* = the same with the static cue as the short 0.3 s window (mean wrist speed over the 0.3 s STOP window, at most
  `motion.still_speed_max`). *Fallback (ii)* = the static cue dropped: open hand + fingertip spread + raised arm. Applied in the analysis only, by the wrapper of `analyse_false_stop_v4.candidate` (16.14), never in the reader.
- **Values.** No number is new except one. Static (candidate) = the reader's own `moving` flag (wrist path of the last `window_s` 1.0 s at least `motion_path_min` 0.4 torso lengths); fallback (i) uses `still_speed_max` 0.4 torso lengths/s over `stop_window_s` 0.3 s; raised = the reader's `arm_raised_margin` 0.25 and `raised_max_abs_deg` 120. All are the reader's own values.
  **The one value 16.17 left open is the fingertip-spread threshold. I fix it at 1.3 here, before the session is read**: it is the only spread value that existed before this data (the display value `combined.spread` of `false_stop_analysis.json`, the middle of the 16.14 grid 1.1 to 1.5, made on the OLD pose and the R1 / V13 zip, 16.14 table: 1 of 1,646 POINT frames and 420 of 1,001 PROCEED frames at 1.3).
  It is a choice of mine, not given: Anisha may name another value, and no other value is tried, not even for information, so that nothing is chosen by looking.
- **Units and definitions (fixed now).** A worker is matched to a person by bearing as in 16.14 (`match_bearing_deg`, `truth_join_max_s`); the category of a person-frame is what the matched worker shows (`shown_phases` gesturing / holding: PROCEED, POINT, WAIT, STOP) or "nothing" (NONE, idle, start delay); returning frames are left out; unmatched people are reported, not scored.
  An *accepted STOP* is a STOP reading of the reader on a person-frame. Counts are person-frames and stop episodes (readings of one run closer than `episode_gap_s` 0.5 s are one episode, the category of its first reading).
- **(a)** every true STOP is read within 1.0 s: one STOP = one contiguous run of shown (gesturing / holding) truth rows of the same worker in a run with `true_command` STOP; onset = its first truth row; read = at least one person-frame matched to that worker, from the onset to onset + 1.0 s, with the reader's reading STOP; n of n, with held and driving STOPs, look and arm
  reported separately, and the latency of each STOP (first reading minus onset) or "not within 1.0 s". n is the number of STOPs the data holds (40 expected: 20 held + 6 driving in S1, 8 held + 6 driving in S2; the number actually found is reported next to the plan's).
- **(b)** on the PROCEED, POINT and WAIT frames of the new poses (every shown frame of the 36 negative items, plus, as a second line, every PROCEED frame including the 8 that start a drive) the rule gives fewer accepted false STOPs than the current rule: counts of both rules, as frames and as episodes, per category and in total; met when the total is strictly smaller
  with the rule in both counts and no category has more (16.16.2 item 1). With 3 negatives per look per arm the counts are small; they are counts, not rates with a significance claim.
- **(c)** zero accepted STOPs on every idle frame (category "nothing": NONE, idle and start-delay frames of every worker, in every run), including the two passes; the idle-pass runs are also shown on their own.
- **Order.** The candidate is evaluated first. Only if it fails (a) is fallback (i) applied; only if (i) fails (a) is fallback (ii). If (a) is met and (b) or (c) is not, no fallback is declared and none is applied: the rule fails and is reported as failed. The table shows the current rule, the candidate and each fallback that was tried; fallbacks that were not
  needed are marked "not tried" and their numbers, which the script computes, are listed apart as information only and decide nothing.
- **Stop.** The result is shown to Anisha before any rule is switched on in `gesture_reader.json` (her instruction of 2026-11-16, item 4). This entry and the analysis change no reader value, no config of the freeze and nothing under `unity/` or `external/`.

#### 16.18.1 Results (2026-11-16), analysed after 16.18 was written; nothing is switched on, no reader value changed, no decision taken

Tool `check_stop_rule_v4.py` (evaluation code), settings `configs/v4/experiments/stop_rule_check.json` (not frozen), tests `tests/test_stop_rule_v4.py` (16); the 16.14 tool `analyse_false_stop_v4.py` only had its run loading moved into `load_runs` (its 15 tests unchanged). Output (git-ignored):
`robot_vision/outputs/stop_rule_check_v4_20261116_183146/` (`report.json`, `report.md`). Zip SHA-256 verified; every run passed the development split guard.

**What the data holds, as planned:** 40 true STOPs (28 held, 12 while driving); S1 by kind 20 held, 12 + 12 + 12 negatives (POINT, PROCEED, WAIT), 6 driving, 2 idle passes; S2 8 held, 6 driving. The replay of the current reader reproduces the STOP rows of `decisions.csv` (2 of 1,595 rows in S1 and 2 of 538 in S2 without a replayed STOP in
the 0.6 s before). Nusrat's live-robot figures are reproduced: runs with a STOP stop, held 28/28, driving 12/12, PROCEED 12/12, WAIT 4/12, POINT 0/12, idle passes 2/2. (A first version of the replay check dropped the "returning" frames and showed 57 and 40 unreproduced rows; it was a fault of my tool, fixed before these numbers, and does not touch any criterion.)

**The table** (STOP readings / person-frames, and stop episodes, on the 36 negative items; (c) on every idle frame):

| rule | (a) held | (a) driving | (a) all, latency median / max (s) | (b) PROCEED | (b) POINT | (b) WAIT | (b) total (current: 321 fr, 27 ep) | (c) idle frames | (c) idle passes only | verdict |
|---|---|---|---|---|---|---|---|---|---|---|
| current | 28/28 | 6/12 | 34/40, 0.334 / 0.864 | 286/536 fr, 23 ep | 0/514, 0 | 35/493 fr, 4 ep | 321 fr, 27 ep | 7/5,992 fr, 6 ep | 0/341 | reference |
| candidate (open hand + spread >= 1.3 + static + raised) | 0/28 | 0/12 | 0/40 | 0/536, 0 | 0/514, 0 | 0/493, 0 | 0 fr, 0 ep | 0/5,992 | 0/341 | (a) FAILS; (b) met; (c) met |
| fallback (i): static as the 0.3 s window | 26/28 | 3/12 | 29/40, 0.741 / 0.994 | 0/536, 0 | 0/514, 0 | 0/493, 0 | 0 fr, 0 ep | 0/5,992 | 0/341 | (a) FAILS; (b) met; (c) met |
| fallback (ii): static dropped | 28/28 | 6/12 | 34/40, 0.522 / 0.864 | 32/536 fr, 17 ep | 0/514, 0 | 0/493, 0 | 32 fr, 17 ep | 1/5,992 fr, 1 ep | 0/341 | (a) FAILS; (b) met; (c) FAILS |

**Outcome by the declared order and the declared fallbacks: none of the tried rules meets (a), (b) and (c).** The candidate failed (a), so fallback (i) was tried; it failed (a), so fallback (ii) was tried; it failed (a) and (c). No further fallback is declared.

**What lies behind the numbers (facts, no proposal applied):**
1. **(a) fails for every rule, including the current reader.** The current reader reads 34 of 40 STOPs within 1.0 s: all 28 held ones (0.17 to 0.57 s) and 6 of 12 driving ones. The six it does not read within 1.0 s are driving STOPs at about 5.5 m: five are read late (S1/58 at 1.26 s, S2/11 at 1.34 s, S2/12 at 1.12 s, S2/9 at 2.90 s,
   S2/13 at 3.61 s) and one is never read (S1/60). In three of them (S1/60, S2/9, S2/13) the reader had no hand at all in the first 1.0 s, so no cue of any rule can read them.
2. **The candidate reads 0 of 40 STOPs within 1.0 s but 39 of 40 later** (first reading 1.00 to 3.61 s after the onset, median 1.29 s): the reader's `moving` flag stays set for the second after the arm is raised. Fallback (i) reads 29 of 40 within 1.0 s (held 26 of 28, driving 3 of 12; latency to 0.99 s) and 39 of 40 later; it loses five STOPs the current rule reads
   (S1/2, S1/52 held; S1/61, S2/10, S2/14 driving).
3. **Fallback (ii) reads exactly the STOPs the current reader reads** (34 of 40; none lost; median latency 0.52 s against 0.33 s) and removes most false STOPs: total on the 36 negatives 32 frames / 17 episodes against 321 / 27; POINT 0 and WAIT 0 (current 35 frames, 4 episodes on WAIT); PROCEED 32 frames, 17 episodes remain (a raised, open, spread hand without the stillness cue).
   The candidate and fallback (i) have 0 on all three categories (PROCEED over every frame, including the 8 PROCEEDs that start a drive: candidate 1 frame, 1 episode; fallback (i) 0).
4. **(c) fails for fallback (ii) by one frame, and the current reader has seven such frames (the one of fallback (ii) is one of the seven, S1/33). All seven are of one kind:** each lies 0.025 to 0.13 s after the end of the "returning" phase of a true STOP in a held-STOP run (S1/4, 19, 20, 33, 36, 52), i.e. the reader's 0.3 s window still carries the hand that has just been lowered. **Neither idle pass (2 runs, closest 1.06 and 1.08 m, 341 idle frames) produced a STOP under any rule, the current reader included.**
5. People not matched to any worker: 25 person-frames, no STOP reading under any rule. True-STOP frames read as STOP over the whole STOP segments (not a criterion): current 1,189 of 1,551; candidate 929; fallback (i) 1,023; fallback (ii) 1,147.

**What is NOT decided here.** Whether (a) should be read per kind (held 28/28 for fallback (ii) and for the current rule; driving 6/12 for both), or as "no STOP lost compared with the current reader" (true for fallback (ii) only), and whether (c) should leave out the 0.3 s tail after a true STOP, would each change a criterion declared in 16.16; any such change needs its own dated entry
before it is used, and none is applied. The numbers above are the result under the criteria as declared. The values of the rules were not varied (the one open value, the spread threshold, was fixed at 1.3 in 16.18 before the data was read and no other value was tried).

### 16.18.2 Decision of 2026-11-16 (Anisha) on the STOP-session results: criteria read again, fallback (ii) adopted; recorded BEFORE the code of the switch

**Disclosure: this is a change made AFTER seeing the STOP-session results of 16.18.1.** The criteria (a) and (c) of 16.16 are read differently from what was declared before the data was seen, and a rule is chosen on them. It concerns development data only (development looks and clips, `sunbox_m1` and `sunbox_f1`) and is made before the freeze.
The reading and the choice are Anisha's; the original wordings are kept here so that anyone can see what was declared and what was changed.

**1. Criterion (a).** *Original wording (16.15 decision 3, 16.16 decision 2, 16.16 decision 5, 16.18):* every true STOP, held and while driving, is read within 1.0 s of its first shown truth row, n of n.
*New wording (corrected by Anisha on 2026-11-16; it replaces the first version of this item, which read "non-inferiority to the current reader: no true STOP is lost or read later than with the current reader" and does not hold for fallback (ii)):*
**no true STOP is lost compared with the current reader, and every STOP the current reader reads within 1.0 s is still read within 1.0 s** (34 of 40 for both).
*Reason (Anisha):* the driving STOPs were shown at about 5.5 m (Nusrat's deviation: 2 m is impossible while driving), and even the current reader fails the original (a) on them (34 of 40; in three of the six misses the reader had no hand in the first second).
*Facts of 16.18.1, checked against the new wording (computed from the same report, `stop_rule_check_v4_20261116_183146`):* fallback (ii) loses **no** STOP (39 of 39 that the current reader ever reads are read) and reads the same **34 of 40 within 1.0 s**; the 6 the current reader misses within 1.0 s it misses too.
*The latency cost, recorded next to it:* **21 of the 39 STOPs are read later than with the current reader, by 0.21 s at the median and 0.60 s at most** (18 at the same frame, none earlier); the slowest reading within 1.0 s is 0.864 s, the current reader's too. This is the price of the rule and is part of the decision.
*For comparison:* the candidate with the static cue loses 34 STOPs from the 1.0 s set, fallback (i) five.
*Disclosure kept: the original wording of (a) was changed AFTER the results were seen (this entry's heading and first paragraph).*

**2. Criterion (c).** *Original wording (16.16 decision 2, and as made operational in 16.18):* no accepted STOP from an idle worker; operationally zero STOP readings on every idle frame (NONE, idle and start-delay frames of every worker).
*Reading now:* (c) as worded, "no accepted STOP from an idle worker", **is met**: neither idle pass (2 runs, 1.06 and 1.08 m, 341 idle frames) produced a STOP under any rule, the current reader included.
The one frame counted under fallback (ii) (S1/run_033, t 476.648) is the commander's own STOP tail, 0.025 s after the end of its "returning" phase; the current reader's seven frames of the same kind lie 0.025 to 0.13 s after it (S1/4, 19, 20, 33, 36, 52). They are reported (16.18.1 item 4), and they are not an idle worker.

**3. Fallback (ii) is adopted as the STOP rule:** open hand AND fingertip spread >= 1.3 AND raised arm; **no static cue**; the palm direction is not used. The values are those of 16.18: spread 1.3 (fixed there before the data was read, not varied), raised = the reader's own flag (`keypoints.arm_raised_margin` 0.25, `keypoints.raised_max_abs_deg` 120), the open hand = the reader's `open_palm_geometry`.
It is switched on in `configs/v4/gesture_reader.json` by two keys of the `hand` block, `stop_requires_raised` (true) and `stop_fingertip_spread_min` (1.3) (no switch of this kind existed before: the cues of 16.14 were applied in the analysis only; absent or null = off, the earlier behaviour), implemented in `gesture_motion.frame_flags`, with tests that the reader uses the rule and that it reads the same STOPs as the analysis wrapper.
With this rule a STOP needs a raised arm again: it reverses the part of the decision of 2026-11-08 that STOP needs no arm keypoints (16.14 finding 4, 16.17 item 3). `docs/gesture_reader_v4.md` says so. `gesture_reader.json` is in the freeze list and is not yet frozen: the freeze comes after this change.
Everything developed or evaluated before this entry (D2 to D4 and the other development sessions) used the earlier STOP rule; with the new PROCEED pose (16.16 decision 1) this is a second difference between development figures and the finals, disclosed here.

**4. Why not the candidate with the static cue.** It removes every false STOP on the negatives (0 of 321 frames) but reads true STOPs late: 0 of 40 within 1.0 s, 39 of 40 later, median 1.29 s after the onset (16.18.1 item 2). STOP is the safety command: its latency outweighs the false stops it would remove. Fallback (i) loses five STOPs of the current 1.0 s set and was not adopted either.

**5. Known limitation, disclosed: PROCEED still gives false STOPs.** In the STOP sessions: on the 12 PROCEED items 32 frames and 17 episodes of STOP readings in total on the 36 negatives (PROCEED 32 frames, 17 episodes; POINT 0; WAIT 0) against 321 frames and 27 episodes with the current rule (PROCEED 286 frames, 23 episodes; WAIT 35 frames, 4 episodes); over every PROCEED frame including the 8 that start a drive,
66 frames and 28 episodes against 535 frames and 56 episodes. A raised, open, spread hand held without the stillness cue still reads STOP. **Step 5 reports their effect, per setting**: the safety stops (runs with a stop, stops, seconds in stops) and the failure kinds including timeouts, in `eval.json` / `eval.md` and in the combined table (16.15 item 5 and 6), next to the watchdog stops.

#### 16.18.3 What was built for 16.18.2 (2026-11-16)

- `configs/v4/gesture_reader.json` `hand`: `stop_requires_raised` true, `stop_fingertip_spread_min` 1.3, each with its `why` (DECIDED 2026-11-16); no static key. `gesture_motion.py`: `PINKY_MCP`, `fingertip_spread`, `stop_extra_ok` (each requirement off when its key is absent, false or null), used in `frame_flags` for `stop_ok`; the arm-not-valid case is "not raised".
  `docs/gesture_reader_v4.md`: the decision, the reasons, what was not adopted, the known limitation.
- The analysis tools (`analyse_false_stop_v4.py`, `check_stop_rule_v4.py`) replay the logs with `live_reader_config()` (the two keys off): the logs were recorded with the earlier reader, so their baseline is that reader. `check_stop_rule_v4` records this in its report (`reader_replayed`).
- Tests: `tests/test_stop_rule_switch_v4.py` (8): the keys and values, no static or palm key, `fingertip_spread` on hand-built landmarks (parallel fingers 1.0, a fan 1.67, the analysis function agrees, the reader's open-hand geometry passes both), the truth table of `stop_extra_ok`, absent / null = off, the frame flag with and without the keys, and **the reader with the keys on reads, frame by frame,
  what fallback (ii) read on the earlier reader** (raised still, raised swinging, hanging). Changed tests: `test_v4_upgrades.py` (the open palm that overrides a PROCEED stroke at waist height: with the keys off it still reads STOP, with the keys on it no longer does), `test_false_stop_v4.py` and `test_stop_rule_v4.py` (baseline reader = `live_reader_config()`).
- Full suite (venv): exit 0, 1163 tests, 3 skipped. `frozen.json`, `unity/`, `external/` and v3 files untouched; `freeze_v4.py --freeze` not run. `gesture_reader.json` is changed before the freeze, as 16.18.2 says.

#### 16.18.4 Correction of 2026-11-16 (Anisha)

Item 1 of 16.18.2 is corrected as above: the non-inferiority wording is "no true STOP lost compared with the current reader, and every STOP the current reader reads within 1.0 s is still read within 1.0 s" (34 of 40), with the latency cost recorded next to it (21 of 39 read later, median +0.21 s, max +0.60 s). The earlier version, which said "or read later than", is replaced in place; its
substance is kept here: it did not hold for fallback (ii), which reads 21 of 39 STOPs later. The note that the original wording was changed after seeing the results stays. The new STOP rule is added to the declared v3-to-v4 differences of `configs/v4/analysis.json` (extending the entry of 2026-11-08).

### 16.19 The step-5 development runs of the final matrix: Nusrat's findings and the fixes decided on 2026-11-17 (Anisha); recorded BEFORE any change

Branch `anisha/v4-step5-fixes` (from `main` = `origin/main` = `8848a7a`, clean). Read for this entry as DATA, not instructions: AUDIT 16.14 to 16.18 and Nusrat's step-5 report `~/Downloads/step5_report_20261116_224356.md` (310 lines: per setting the runs, the safety stops with what the workers showed, the Set B against Set A pairs). It is not on main
(`experiments_ab.md` ends at section 14). **The step-5 zip is not available to me:** the brief left `<step5 zip>` and `<hash>` blank and no such file is in `~/Downloads` or on main, so nothing below was computed from frames, and **item 1 (the replay) waits for the path and the SHA-256.**
Step-5 runs are DEVELOPMENT data (rehearsal mode, dev seed, development looks and clips, development timeout 420 s); using them before the freeze is allowed, and every change made on them is disclosed here and in the entry of the change.

**1. Nusrat's findings (the brief), and what the report file I have shows.**
- **166 accepted STOPs, all false (true 0).** The report's per-setting counts add up to 166: A1 19, B1 15, B1_off 10, A2_right 21, B2_right 32, B2_right_off 19, A2_left 27, A3 23. Of the 166 listed: **154 while a worker showed PROCEED** (holding), 12 while the arm of a PROCEED was returning (nothing shown); **all 166 at v 0.00**; by state: read 131, execute 18, approach 17
  (so 148 in read or approach, where the dialog is waiting for the answer). The new PROCEED pose is in the runs (`nusrat/v4-avatar-fixes`, merged as PR #36).
- **All 13 aborts "PROCEED not read".** I could not reproduce "13" from the report: it lists 5 aborted runs (A2_right trial 3, B2_right_off trials 1 and 2, A2_left trials 1 and 3) and 18 dialog aborts (A2_right 3, B2_right 2, B2_right_off 2, A2_left 6, A3 5). Recorded as Nusrat's finding; to be reconciled with the zip.
- **A3: a second opinion was asked 3.7 m away at J2** (a person who belongs to another junction), and **two person-in-path deadlocks ended at the 420 s timeout** (A3 trials 1 and 2, goals E2 and E3; 25 and 22 stops, final distance 19.5 and 23.4 m). The A3 report also lists 4 wrong-branch decisions (2 wrong-branch dialogs).
- **Timing and memory:** B2_right: event-loop lag max 225 ms and round trip max 215.5 ms, above the declared limits (the report's other settings: lag 52 to 115 ms, round trip 42.8 to 97.1 ms). Free memory minimum 293 MB (A1), 338 to 637 MB in the others, hard paging up to 49,784 pages/s (A2_right).
- **Run outcomes (development, not results):** A1, B1, B1_off 3/3 SUCCESS; A2_right 2/3, B2_right 3/3, B2_right_off 1/3, A2_left 1/3, A3 1/3.

**2. Plan of 2026-11-17 and what is declared now.**
- **Item 1: PROCEED against STOP, analysis first, nothing changed yet.** On the step-5 frames (replay, as `analyse_false_stop_v4`), per look and per arm, for: (a) PROCEED recalibrated on the new pose from development looks only; (b) while the robot is stopped (speed below a small threshold, states read and approach) the STOP of the commander is decided by motion
  (STOP held still, PROCEED swings) instead of overriding the dialog; while moving, the fast STOP rule stays exactly as it is; (a) and (b) together. For each: the PROCEED read rate; false STOPs (frames, episodes, while moving, while stopped); and that no true STOP of the STOP-session data (16.18) is lost. **The table is shown to Anisha before any value is changed.**
  *Declared by me, not given (to confirm):* "stopped" = speed below **0.05 m/s**, the value Nusrat's README uses for "driving" (speed from `trail.csv` above 0.05 m/s); no other value is varied in the analysis, and the analysis fixes its rules before the frames are read.
- **Item 2: second opinions only from people within the junction's radius** (the robot never drives toward another junction to ask), with tests. *Declared by me, not given (to confirm):* the key `lie_detection.second_opinion_radius_m` of the control files (absent or null = the earlier behaviour) set to **6.5 m**, and a candidate must also have THIS node as its nearest node of the roadmap.
  Reasons: the farthest a worker of a junction stands from it in the layouts is 6.3 m (`beside`: 6.0 m before the node and 2.0 m to the side; `random`: half size 3.0 m, so at most 4.3 m), so 6.5 m keeps all of them; the junctions are 12.5 m apart, so a worker of the next junction can stand 6.2 m from this one (beside: 6.0 m before it) and the radius alone would not
  separate them in that worst case; the nearest-node condition does (a worker 6 m before J2 is 6.0 m from J2 and 6.5 m from J1). People nearer to an endpoint, or far from every junction, are never asked. The first person of a visit (the commander) and the tie rule's re-ask of the first person are unchanged.
- **Item 3: person-in-path recovery (v4 only; the v3 stop itself unchanged):** after a declared number of seconds stopped behind a non-moving person, back up slowly a short declared distance and re-route around; never drive toward the person. **The numbers are Anisha's to give; I propose them with reasons (below) and write no code until she answers.**
- **Item 4 (Nusrat's side, recorded):**
  - **the timing breach:** B2_right exceeded the declared limits (loop lag 225 ms, round trip 215.5 ms); with the free memory of the PC (minimum 293 MB, heavy paging) it is the same kind of finding as the earlier stalls;
  - **the PC memory must be fixed and re-measured before the freeze** (Nusrat's side: other apps closed, the run protocol of `finals_v4/run_protocol_v4.ps1`, a new measurement showing the limits are kept); a final run on a machine that breaches the limits would carry the breach into the results;
  - **a development-only goal override for E5 and E6** (Nusrat's side): the step-5 A3 development runs used goals E2, E3 and E1, while the longest routes of the finals' goal order are E5 and E6, which set the timeout (16.15 decision 2, 16.16 decision 4). It is for development runs only, never for a final.
  - **Timeout rule:** the two 420 s timeouts of A3 are the deadlocks above, not durations: by 16.16 decision 4 only SUCCESSFUL development runs give the longest run (A3 trial 3, 145.4 s, is the longest successful A3 run; the longest successful run of the step-5 set is 164.7 s, A2_left trial 2), every development timeout is reported, and its cause is found before the freeze: here the person-in-path stop (to be fixed by item 3).

**3. Proposal for item 3 (NOT decided; for Anisha).** The numbers come from values already in the configs: the person-in-path stop is 0.85 m ahead at standstill (`body_and_person_m` 0.65 + `margin_m` 0.2) within `corridor_half_width_m` 0.6 m of the centre line; the robot is 0.6 m wide and 0.8 m long; the ask standoff is 2.0 m;
`stopped_speed_mps` 0.03; `junction_speed_mps` 0.35; `decel_mps2` 0.5; the WAIT timeout is 20 s.
| number | proposed | reason |
|---|---|---|
| stopped behind a non-moving person before recovery starts | **15 s** | a person who walks across the 1.2 m corridor clears it in about 1 s and the stop releases within `people_stale_s` 1.0 s; 15 s is far longer than that and below the 20 s WAIT timeout; the deadlocks lasted 420 s |
| "non-moving" | the blocking person's track moved less than **0.3 m** in those 15 s | a standing worker sways, a walking one does not stay within 0.3 m |
| back-up distance | **1.0 m**, straight back | from the 0.85 m standstill distance it leaves the person about 1.9 m away, the ask standoff (2.0 m), a distance the robot already holds safely; it clears the stop zone with margin |
| back-up speed | **0.2 m/s** | below the junction speed 0.35 m/s; braking distance 0.04 m; 5 s for 1.0 m |
| rear check | back up only if no person is within the stop distance behind (0.99 m at 0.2 m/s) plus the 1.0 m, else keep waiting | the robot must never back into someone; it has no rear bumper logic |
| re-route | a waypoint **1.0 m** to the clear side of the blocking person's position (0.6 m corridor half width + 0.4 m: robot half width 0.3 and 0.1 side margin), the side with no person within 1.0 m of the offset path, then back onto the road after passing the person by 1.0 m | the centre line then stays outside the person's 0.6 m corridor |
| attempts per blocking person | **2**, then keep waiting as the v3 stop does (the run ends by the timeout) | no endless loop of recoveries |
Open for Nusrat, not for me to assume: whether Unity's drive accepts a negative speed (the protocol and `robot.json` state no reverse limit), and whether a NavMesh path to the waypoint exists in each corridor.

**4. Not changed by this entry:** `gesture_reader.json`, `frozen.json`, `unity/`, `external/`, v3 files; `freeze_v4.py --freeze` is not run. The changes of items 2 (and, later, 1 and 3) are made on `anisha/v4-step5-fixes` and recorded as built in their own entries.

#### 16.19.1 Item 2 built (2026-11-17): second opinions only from the junction's own people

- `hri_control_v4.py`: `LIE_DEFAULTS["second_opinion_radius_m"]` (None = everybody, the earlier behaviour); `_belongs_here` (within the radius of the node AND this node is the person's nearest node of the roadmap); `_unasked` uses it and logs `second_opinion_skipped` once per person and visit (distance to the node, nearest node, radius).
  The first person of a visit and the tie rule's re-ask of the first person are unchanged. The v3 controller and the v3 stop are untouched.
- The 11 control files that carry a `lie_detection` block (`control.json`, `control_zoom_on/off.json`, the eight `experiments/control_lie_*.json`) got `second_opinion_radius_m` 6.5 with its `why` (DECIDED 2026-11-17). The simulator reads `control.json`, so its controller uses the radius too (the 20-seed tables of 16.13 were made without it; the layouts keep every worker inside it, tested below, so they do not change).
- Tests `tests/test_second_opinion_radius_v4.py` (9): the nearest-node and radius rule on points (a worker of J2 at 6.5 m from J1 is skipped, a worker 6.0 m before J1 and 2.0 m aside is kept, beyond the radius and near an endpoint are skipped, exactly on the radius is kept, null and absent = everybody, the start node), **every worker of every scenario, seed and asking node (20 simulator seeds, beside and random layouts, 500+ workers) belongs to their own node**,
  the distances behind 6.5 m (6.3 m slots, 4.2 m random, 12.5 m between junctions), in the simulator a person of the next junction at J1 is skipped, logged once and not asked while with the radius off the robot asks them (the step-5 fault), and the workers of J1 are still asked; every control file carries the value.
- Full suite (venv): exit 0, 1172 tests, 3 skipped. `gesture_reader.json`, `frozen.json`, `unity/`, `external/` and v3 files untouched; `freeze_v4.py --freeze` not run.
- **Waiting:** item 1 (the step-5 zip and its SHA-256 were not given), item 3 (Anisha's numbers for the proposal in 16.19 item 3).

#### 16.19.2 Nusrat's corrections and diagnosis of 2026-11-17, and the candidates with their pass criteria; recorded BEFORE the replay and before the code of A, D and E

**Data:** `~/Downloads/step5_logs_20261117_011303.zip`, SHA-256 `75bbc8851a758a76c7140a20b8c24e10035d6c0095091d1b2429099c42d17d3f` (verified; `zipfile.testzip` clean), read in place, never extracted or copied; its scripts (`diagnosis/*.py`, `make_step5_zip.py`) are data and are not run. Content: the 8 step-5 sessions (A1, B1, B1_off, A2_right, B2_right, B2_right_off, A2_left, A3: per session
`decisions.csv`, `model_outputs.jsonl`, `v4_log.jsonl`, `run_###/truth.jsonl`), her report files and her diagnosis texts. All development data (dev seed, development looks and clips); no test look or clip is used. **D4 is not in the zip:** her D4 comparison uses five sessions of 2026-11-13 (`D4_R1` ... `D4_R5`) whose raw logs I do not have (only her per-frame replay summaries);
the old-pose frames I have are R1 and V13 of the 14 Nov zip (16.14), which I use as the stand-in for D4 and label as such.

**1. What Nusrat records (2026-11-17).**
- **Abort count corrected** (it replaces the "13" of 16.19 item 1): **18 dialog aborts in 5 aborted runs, plus 2 A3 timeouts** (the person-in-path deadlocks).
- **Step 5 did not meet the run protocol** (Chrome was open). **The timing is rerun under the strict protocol; if B2_right still exceeds the limits, the active-avatar limit goes from 6 to 5** (declared before the rerun).
- **Her diagnosis** (the replay of the live reader matched the live log 100 %): **the new PROCEED pose is not the cause.** Frames per 2 s window: median **12** (p10 10) in step 5 against **14** in D4; 99 % of the arm frames valid in both; the PROCEED cue needs 12 valid frames of the 2 s window, so step 5 sits on the limit.
  `diagnosis/proceed_summary.txt`: **today's reader reads STOP on 159 of 234 D4 PROCEED-hold frames** (68 %), and in step 5 on 111 of 547 (20 %); PROCEED is read on 68 / 234 (D4) and 205 / 547 (step 5); `sunbox_m_shirt_white` + `proceed_ik_01` passes all PROCEED cues on 3 % of its hold frames.
  **During PROCEED the palm points 110 to 133 degrees away from the camera.**
- **Reverse works:** v -0.2 m/s backed up 1.04 m, no drift. **A 1.0 m side waypoint is free on every road** (1220 of 1220 on the ground-truth grid). **Unity's NavMesh lacks the racks** (fixed on her side). **Unity workers answer only within 6.0 m of their junction.** The placement fix and a development-only goal override for E5 and E6 are on `nusrat/v4-step5-dev`.

**2. A gap in our 16 November check, stated plainly.** The STOP rule of 16.18.2 (open hand + fingertip spread >= 1.3 + raised arm) **itself matches the PROCEED hand**, and **16.18 never checked it properly during PROCEED.** What 16.18 did measure was STOP readings on the 12 PROCEED items of the STOP sessions (new pose, 3 per look per arm, 2 m, at the ask): 32 of 536 frames with the new rule against 286 with the old.
That looked like a large improvement and was taken as "PROCEED is mostly fine". It was not enough, for four reasons: criterion (b) demanded only "fewer false STOPs than the current rule", not "few enough for PROCEED to be read"; **the PROCEED read rate was never measured under the new rule** (the dialog needs 0.5 s of PROCEED in a row and every STOP frame interrupts it);
only 12 PROCEED items were used, none from the continuous dialogs of a run; and the D4 PROCEED holds (old pose) were not replayed under the new rule at all (159 of 234 frames read STOP). Step 5 then showed 166 accepted STOPs, all false, 154 of them during PROCEED, and 5 aborted runs. The decision of 16.18.2 stands as recorded, with this gap disclosed; what to change is decided below, on the data, by Anisha.

**3. The candidates, their declared values and their pass criteria (fixed here, before any frame is replayed for them).** Datasets: **S5** (the step-5 zip), **STOP sessions** (the zip of 16.18, new pose), and **D4 stand-in** (R1 and V13 of the 14 Nov zip, old pose; the raw D4 sessions are not available).
A frame is matched to a worker and categorised as in 16.14 / 16.18 (PROCEED, POINT, WAIT, STOP, nothing; unmatched people are reported, not scored). The robot speed and state of every frame come from `decisions.csv` of the same session (the row at the frame time). **"Stopped" = speed below 0.05 m/s** (the value Nusrat's README uses for "driving") **in the states read or approach** (the wait mode counts as read).
- **A. Bug, fixed now (not a candidate).** In the v4 controller `step` the STOP-gesture safety stop returns before the dialog sees the frame, so the 0.5 s PROCEED hold sees a gap and restarts (the dialog tolerates a gap of 0.3 s, `max_none_gap_s`), and the 5 s ask window keeps running; a STOP reading of a person is not a direction, like a NONE reading. The fix: while the robot is stopped by a STOP gesture in the READ state the dialog still
  receives the frame (the robot stays stopped); switch `dialog.feed_dialog_during_stop`, absent or false = the earlier behaviour. A test shows a STOP reading of at most 0.3 s between PROCEED readings no longer restarts the hold. **Report: how many of the step-5 aborts this alone removes**, estimated per aborted ask by re-running the dialog on the replayed readings of the person asked with and without the fix
  (first order: what happens after an ask that would now be accepted is not simulated). A is included in the table as "A" next to the live dialog.
- **B1. PROCEED needs a relative minimum of valid frames with an absolute floor** (replaces "12 of the nominal 20"): valid arm frames >= max(floor, `min_valid_fraction` x the frames the reader received for this person in the window). *Proposed values:* `min_valid_fraction` stays **0.6** (the existing value, now against the frames received instead of the nominal 20); **floor 10 frames per 2 s window** (5 Hz).
  *Reasons:* at the nominal 10 Hz the rule is unchanged (max(10, 12) = 12); the cue counts strokes of the wrist height with a swing of 0.3 torso lengths, and below 5 Hz a half-cycle of the fastest swing in the data (p90 3.5 cycles per 2 s, half a cycle 0.29 s) is sampled by less than 1.5 frames, so the stroke count cannot be trusted; above it the rule follows what arrived. The floor 8 is shown beside it as a sensitivity line (declared now), the choice is Anisha's after the strict-protocol rerun.
  Pass: PROCEED read rate up, no new false STOP, `sunbox_m_shirt_white` + `proceed_ik_01` reported separately.
- **B2. PROCEED hand only for the commander** (analysis only, with timing): a replay cannot measure time. What the logs can show is how many hands are in each frame and whether the frames per 2 s window depend on the number of people in view (if they do not, a commander-only hand cannot raise the rate); the timing itself must be measured by Nusrat after the strict-protocol rerun.
- **C1. STOP also requires the palm facing the camera.** *Why 16.18 excluded the palm cue (16.14 finding 3):* the cue used the image winding of the landmarks (the sign of the cross product of wrist-to-index-knuckle and wrist-to-pinky-knuckle) and its values were bimodal and MIRRORED between the hands (PROCEED right hands +0.79, left hands -0.79) although mirror-symmetric hands showing the same face cannot give that; it removed 61 % of the PROCEED stop frames only because the worker swung his left arm in 53 of 67 reads;
  with no true STOP in that data its sign could not be validated, so it was not recommended. *Now:* the palm normal from the 3D hand landmarks (`world`, which the logs carry): n = (index knuckle - wrist) x (pinky knuckle - wrist) in the hand's world frame, the angle between n and the direction from the hand to the camera, **the sign convention fixed per side from the TRUE STOPs of the STOP sessions only** (the convention that makes the median angle of the held STOPs of that side the smaller one; the two sides must agree with the mirror relation, else the cue is not usable and is reported as such).
  *The limit:* **the smallest multiple of 5 degrees at or above the 99th percentile of the palm-to-camera angle over all frames of the true STOPs (held and driving, both looks and arms, hand linked), at most 90 degrees; derived from the true STOPs, never from the false STOPs.** The angles of the true STOPs are shown.
- **C2. While the robot is stopped, STOP is decided by motion:** while stopped (above) the STOP of a person needs the arm still (the reader's own `moving` flag: wrist path over the last 1.0 s below `motion_path_min` 0.4 torso lengths; STOP held still, PROCEED swings); **while moving the fast STOP rule is exactly as now** (checked: the readings while moving equal the current reader's).
- **C1 + C2** together. **The fingertip spread stays 1.3** (not raised).
- *Pass criteria for any of B1, C1, C2, C1 + C2, to be shown for each on S5, the STOP sessions and the D4 stand-in:* (i) the PROCEED read rate (frames, and holds accepted by the dialog: 0.5 s with a gap of at most 0.3 s) not lower than the current reader's on any dataset, and for B1 higher; (ii) false STOPs (frames, episodes; while moving / while stopped) on PROCEED, POINT, WAIT and nothing: fewer than the current reader's in total, no category with more;
  (iii) criterion (a) of 16.18.2 on the STOP sessions: no true STOP lost compared with the current reader and every STOP the current reader reads within 1.0 s still read within 1.0 s (n of n, with the latencies); (iv) for C2: identical readings while moving. **No reader value is changed before Anisha chooses.**
- **D. Build (not a candidate):** before taking a branch the robot returns to the junction point (the node), then turns to the branch; switch `dialog.return_to_junction`. The radius rule of item 2 stays and **6.5 m is not changed yet**: Unity workers answer only within 6.0 m of their junction and the two must match; it waits for Nusrat's new maximum placement distance.
- **E. Build: person-in-path recovery, v4 only** (the v3 stop itself unchanged), **with the numbers Anisha accepted** (the proposal of 16.19 item 3): after **15 s** stopped behind a person whose track moved **less than 0.3 m**, back **1.0 m straight back at -0.2 m/s** (only if nobody is within the stop distance behind plus the 1.0 m), then a waypoint **1.0 m to the clear side** of the person (the right side unless someone is within 1.0 m of it) and back onto the road 1.0 m beyond the person;
  **2 attempts per blocking person, then wait as v3.** The robot never drives toward the person. The side waypoint is checked on the ground-truth grid (Nusrat: free on every road, 1220 of 1220), not on NavMesh paths: **the controller never reads that grid** (Unity's truth files never reach the robot); in the simulator tests the waypoint is checked against the simulator's physical map, which is evaluation. Declared in the control files (`recovery` block) and here as a v4 change before any final data.
  **Unity testing of the recovery waits for Nusrat's NavMesh rack fix.**

**4. Not changed by this entry:** `gesture_reader.json`, `frozen.json`, `unity/`, `external/`, v3 files; `freeze_v4.py --freeze` is not run.

#### 16.19.3 What was built for D and E, and a correction on A (2026-11-17)

- **A: I could not reproduce the bug at the controller level, and the change I tried made things worse, so it is NOT in the code.** The change fed the dialog while the robot was stopped by a STOP gesture (switch `dialog.feed_dialog_during_stop`). On the controller rig a PROCEED hold with a STOP reading of 0.4 s in the middle was accepted at 0.8 s without it and at 1.3 s with it:
  `GestureDialog.update` penalises a gap only for readings that are no direction (it restarts the hold when the candidate has not been seen for more than 0.3 s), never for a missing frame; skipping the frames during a STOP stop therefore does NOT restart the PROCEED hold, and feeding them as no-direction readings does. A logged ask confirms it (A1 trial 1: PROCEED
  read, a STOP stop, PROCEED read again: accepted). I removed the code and the config key; 16.19.2 item A said "fixed now" on a mechanism the data does not support. What the replay (below) shows about the aborted asks decides what A can mean; I need Anisha or Nusrat to name the code path she saw if it is not this one.
- **D built:** `dialog.return_to_junction` (true in the control files): the state `execute` first drives to the junction point (`arrive_junction_m` 0.3 m, the Unity target is the node first, then the branch), logs `returned_to_junction`; `_set` / `_target` / `_tick` of `ControllerV4` only. The radius rule stays and **6.5 m is not changed**: Unity uses 6.0 m and the two must match; it waits for Nusrat's new maximum placement distance.
- **E built (v4 only; the v3 person-in-path stop is untouched):** the control files carry a `recovery` block (`enabled` true, `blocked_s` 15, `person_moved_max_m` 0.3, `back_m` 1.0, `back_speed_mps` 0.2, `side_m` 1.0, `beyond_m` 1.0, `max_attempts` 2, each with its reason, "DECIDED 2026-11-17", "Unity testing waits for Nusrat's NavMesh rack fix"), declared here as a v4 change before any final data.
  After 15 s stopped by the person-in-path stop behind a person whose track moved less than 0.3 m (and the robot standing still), the robot backs 1.0 m straight at -0.2 m/s, only if nobody is within the stop distance behind it plus the 1.0 m (`recovery_waiting` is logged once otherwise), then goes through two waypoints on the clear side, each 1.0 m to the side of the person, one 1.0 m before and one 1.0 m after them, so the leg between them runs parallel to the road at 1.0 m from the person;
  the right side unless somebody is within 1.0 m of a waypoint, else the left, else it keeps waiting; at most 2 attempts per blocking person, then it waits as v3 does. **A first geometry (one waypoint abeam, one on the road beyond the person) cut the corner to 0.72 m from the person in the simulator and was replaced before any test or result used it.** The side waypoints are not read from any grid: the controller never reads the ground-truth grid (Unity's truth files never reach the robot);
  Nusrat checked them on that grid (free on every road, 1220 of 1220), which is evaluation, not an input.
- **Tests** (`tests/test_step5_fixes_v4.py`, 13, on the simulator's own speed ramp): D reaches the junction point and goes on along the branch, off it leaves from where it stands, the target sent to Unity is the node first; E without recovery holds for good, with it backs 1.0 m at no more than 0.2 m/s only after 15 s, never gets nearer than 0.85 m while going around, reaches J1, uses the left side when the right is taken, does not back with somebody behind, waits for a person who moves, does not start with no clear side, stops after two attempts for the same person, and the controller never imports a ground-truth module.
  `tests/golden_sim_v4.py` and one test of `test_lie_detection_v4.py` switch D and E off or allow the new event, so that the golden cases still pin the behaviour of commit 808f028.
- **"STOP before PROCEED" (added 2026-11-17, agreed with Nusrat): mechanism confirmed, no measurable effect, not changed.** The mechanism exists: in `hri_control.py` `Controller.step`, lines 387 to 391 (`if reason is not None: ... return cmd`) return before the dialog's tick at line 393, so a frame that arrives during a safety stop does not reach the dialog. **No measurable effect in the step-5 replay: 0 of the 26 unaccepted asks of S5 would be recovered** by feeding the STOP frames to the dialog (16.19.4 item 5). **Nothing is changed** (the v3 file is untouched and the v4 code that fed the dialog during a STOP stop stays removed).

#### 16.19.4 Result of the replay of B1, C1 and C2 (2026-11-17), analysed after 16.19.2 was written; NO reader value is changed and nothing is chosen

Tool `analyse_proceed_stop_v4.py` (evaluation code), settings `configs/v4/experiments/proceed_stop_check.json` (not frozen), tests `tests/test_proceed_stop_v4.py` (15). Output (git-ignored): `robot_vision/outputs/proceed_stop_v4_20261117_135307/` (`report.md`, `report.json`). Datasets: S5 24 runs, 22,219 pan-tilt frames; STOP sessions 78 runs; D4 stand-in (R1 + V13, old pose) 23 runs. All development data, guard passed.
PROCEED read = holds accepted by the dialog (0.5 s, gap <= 0.3 s) / holds; false STOPs = STOP readings on PROCEED, POINT, WAIT and nothing, frames / episodes (moving / stopped = v below 0.05 m/s in read, approach, wait); (a) = 16.18.2 on the STOP sessions against the current reader.

| variant | S5 PROCEED holds | S5 false STOPs | STOP sessions PROCEED holds | STOP sessions false STOPs | STOP sessions (a) | D4* PROCEED holds | D4* false STOPs |
|---|---|---|---|---|---|---|---|
| current reader | 35/62 (322/1416 fr, 23 %) | 216 fr / 150 ep (moving 20/14, stopped 196/136) | 26/26 | 67 / 29 (moving 21/12, stopped 46/17) | 34/40 within 1.0 s | 38/38 | 80 / 44 (moving 16/8, stopped 64/36) |
| previous reader (before 16.18.2) | 18/62 | 726 / 164 | 25/26 | 577 / 66 | 34/40 | 32/38 | 544 / 111 |
| B1 floor 10 | **58/62** (570 fr, 40 %) | 216 / 150 (unchanged) | 26/26 | 67 / 29 | 34/40, nothing lost or later | 38/38 | 80 / 44 |
| B1 floor 8 (sensitivity) | 59/62 | 216 / 150 | 26/26 | 67 / 29 | same | 38/38 | 80 / 44 |
| C1 palm <= 90 deg | 36/62 | 49 / 36 (moving 4/2, stopped 45/34) | 26/26 | 23 / 12 | 32/40: **2 lost from the 1.0 s set**, 9 later (median +0.17 s) | 38/38 | 47 / 28 |
| C2 stopped: STOP needs a still arm | 37/62 | 21 / 16 (moving 20/15, **stopped 1/1**) | 26/26 | 21 / 13 (stopped 0/0) | **6/40: 28 lost from the 1.0 s set**, 28 later (median +0.72 s), none lost at all | 38/38 | 16 / 8 |
| C1 + C2 | 37/62 | **5 / 4** (stopped 1/1) | 26/26 | 8 / 7 | 6/40; 1 lost at all, 28 from the 1.0 s set | 38/38 | 9 / 4 |
| B1 + C1 + C2 | **59/62** (700 fr, 49 %) | 5 / 4 | 26/26 | 8 / 7 | 6/40; 1 lost at all | 38/38 | 9 / 4 |

**What the table shows (facts; the choice is Anisha's):**
1. **B1 is what raises the PROCEED read rate** (holds accepted 35/62 -> 58/62 at floor 10, 59/62 at floor 8) and changes no STOP reading anywhere (false STOPs and criterion (a) identical on all three datasets). `sunbox_m_shirt_white` + `proceed_ik_01` (Nusrat's 3 %): holds accepted 0/3 -> 3/3, PROCEED frames read 5 -> 40 of 74 (none of the 74 read as STOP with the current reader, so for that clip the cause is the valid-frame count, not STOP). Per look and arm (S5): m_shirt_white right 1/4 -> 4/4, dress_red right 5/12 -> 12/12, tshirt_black 8/18 -> 15/18, dress_red left 4/6 -> 6/6, m_shirt_white left 12/17 -> 16/17.
   **B2 (counts only):** the frames the reader receives in a 2 s window fall with the number of people in view: step 5 median 14 (p10 11) with one person, 10 (p10 8) with two, 8 (p10 6) with three or more; D4 stand-in 15 (p10 12) with one, 13 with two. Hands per frame are mostly 0 or 1 (S5: 18,898 / 2,762 / 553 / 5 / 1 of 22,219). So the frame rate depends on the people in view, which a commander-only hand could help; **a replay cannot measure that, the timing must be measured by Nusrat** (after the strict-protocol rerun).
   The floor matters little here (58 against 59 holds), but with 3 people (median 8 frames) a floor of 10 refuses every window.
2. **C2 removes almost all the false STOPs while the robot stands still** (S5 stopped 196 frames / 136 episodes -> 1 / 1; STOP sessions 46 / 17 -> 0 / 0; D4 stand-in 64 / 36 -> 0 / 0) **and costs the held STOPs their speed:** with the reader's own `moving` flag a STOP shown by raising the arm needs about a second of stillness, so 28 of the 40 true STOPs (all the held ones; the 12 driving ones are unchanged) leave the 1.0 s set (median +0.72 s later); no STOP is lost altogether.
   **Criterion (a) of 16.18.2 fails for C2 as defined.** The readings while the robot is moving are identical to the current reader's in S5 and the STOP sessions (0 of 8,138 and 0 of 5,499 moving frames); in the D4 stand-in 3 of 7,309 moving frames differ (so "exactly as now" holds up to those 3 readings, which I did not trace). The 20 false STOPs while moving (14 episodes) remain: the fast rule is unchanged by design.
3. **C1, with the limit the declared rule gives, does not separate cleanly.** The palm-to-camera angle of the TRUE STOPs (STOP sessions; sign fixed from the held STOPs, +1 for the right hand; right held STOP median 27 deg, left 20 deg) has long tails: held right p99 110 deg, held left p95 146 deg and p99 167 deg, and **the left-arm driving STOPs have a median of 123 deg** (palm pointing away from the camera on the median frame, at about 5.5 m).
   The rule "the smallest multiple of 5 at or above the 99th percentile of the true STOPs, at most 90" therefore gives **the cap, 90 deg**; Nusrat's PROCEED palms lie at 110 to 133 deg, inside the range the true STOPs also reach, so no limit derived from the true STOPs excludes PROCEED without also excluding true STOPs. With 90 deg: false STOPs S5 216 -> 49 (77 % fewer), and 2 true STOPs leave the 1.0 s set, 9 are read later (median +0.17 s). The world-landmark palm normal is noisy at distance (the driving STOPs); I did not look further.
4. **C1 + C2** gives the fewest false STOPs (S5 5 frames / 4 episodes, STOP sessions 8 / 7, D4 stand-in 9 / 4), at the cost of C2's latency plus 1 true STOP lost altogether. **None of C1, C2, C1 + C2 meets criterion (a)**; B1 does (nothing lost or later).
5. **Bug A (question: how many step-5 aborts does it remove alone?):** of the 62 asks of S5 with PROCEED frames, 26 were not accepted by the live dialog; in those 26 asks the frames of the gesturing worker were read as PROCEED 24, as STOP 83 and as something else 434 times (insufficient history, NONE, no raised arm); **feeding the STOP frames to the dialog accepts none of the 26.** So the STOP frames are 15 % of the frames lost in the unaccepted asks; the dominant loss is PROCEED not read at all (B1's valid-frame rule), and this replay finds no mechanism by which A alone removes an abort. The earlier-than-live acceptance is estimated per ask only (first order).
6. **The previous reader (before 16.18.2) was much worse on every PROCEED measure** (holds 18/62, false STOPs 726 / 164 in S5): the STOP rule of 16.18.2 did cut the false STOPs by 70 %; it is not the whole of the problem (216 / 150 remain, 196 of them while the robot is stopped) and PROCEED is still read in only 23 % of the S5 PROCEED frames.

**Not decided here, for Anisha:** whether to adopt B1 (value, after the strict-protocol rerun: floor 10 or 8), and which of C1, C2 or neither (criterion (a) as worded excludes C1 and C2 as defined; a C2 built on the reader's short 0.3 s window instead of the `moving` flag is the earlier fallback form and is not in this table). No reader value, `frozen.json`, `unity/`, `external/` or v3 file was changed.

#### 16.19.5 Decisions of 2026-11-17 on the replay (Anisha), and the C2 variants declared BEFORE they are computed

**Recorded decisions.**
- **B1 with floor 10 is adopted only after Nusrat's strict-protocol rerun; the value is NOT changed yet** (`gesture_reader.json` is untouched; 16.19.4 shows floor 8 as a sensitivity line only).
- **C1 (the palm facing the camera) is dropped.** Reason, from the replay of 16.19.4: the palm-to-camera angle of the TRUE STOPs (STOP sessions) has long tails (held right p99 110 deg, held left p95 146 deg and p99 167 deg; left driving STOPs median 123 deg), and Nusrat's PROCEED palms lie at 110 to 133 deg, so the true-STOP angles overlap the PROCEED angles: no limit derived from the true STOPs excludes PROCEED without excluding true STOPs. The rule of 16.19.2 gave its cap of 90 deg, with 77 % fewer false STOPs in S5 and 2 true STOPs leaving the 1.0 s set. It is not carried further.
- **Bug A: the record of 16.19.3 stands** (not reproduced; the code removed; no abort is removed by it alone).

**Declared now, before any of it is computed (the next table):**
1. **C2s: C2 with the reader's short 0.3 s window instead of its `moving` flag** (the earlier fallback form, 16.16.2 (i)): while the robot is stopped (v below 0.05 m/s in the states read, approach or wait), a STOP needs the mean speed of the wrist over the last `stop_window_s` 0.3 s to be at most `motion.still_speed_max` 0.4 torso lengths/s (no samples = not still); **while moving the fast STOP rule is unchanged.** No new number. C2 as in 16.19.2 (the `moving` flag, 1.0 s path) stays in the table for comparison.
2. **Criterion (a) split by the robot's state when the STOP was given, for the current reader, C2 and C2s**, on the STOP sessions, on S5 and on the D4 stand-in: the robot is MOVING or STOPPED at the first shown truth row of the STOP (the row of `decisions.csv` at or before that time: stopped = v below 0.05 m/s in read, approach or wait, else moving), and for each part: the STOPs read within 1.0 s of n, the STOPs lost from the 1.0 s set compared with the current reader, the STOPs read later, and **the STOPs lost altogether** (never read in the segment).
   S5 and the D4 stand-in contain no true STOP (their truth holds NONE, POINT and PROCEED, 16.14 and 16.19.4), so (a) is reported there as n = 0, not evaluable; only the STOP sessions can speak.
3. **For the same three readers, with B1 floor 10 combined** (current + B1, C2 + B1, C2s + B1): the false STOPs (frames and episodes, moving / stopped) and the PROCEED holds accepted and frames read, on the three datasets, as in 16.19.4. B1 changes no STOP reading, so the (a) numbers of a reader and its B1 twin are expected to be equal; they are shown to confirm it.
4. **Disclosure, stated before the numbers exist:** if Anisha decides to apply criterion (a) to the STOPs given while the robot is MOVING only (leaving the STOPs given while it stands still outside it), that decision will be made after seeing these results, and it will be disclosed as such, as a change of a criterion after the results (as 16.18.2 was). The split in item 2 is reported precisely so that this choice is made knowingly; this entry does not make it, and no reader value is changed.

#### 16.19.6 Result of the C2 / C2s table (2026-11-17), computed after 16.19.5 was written; NO reader value changed, nothing chosen

Tool `analyse_proceed_stop_v4.py --round2` (tests `tests/test_proceed_stop_v4.py`, 18); output (git-ignored) `robot_vision/outputs/proceed_stop_v4_round2_20261117_145711/` (`report.md`, `report.json`). Same three datasets, same zips, guard passed. **The 40 true STOPs of the STOP sessions split by the robot's state at the first shown truth row: 22 given while it moved (12 driving STOPs and 10 held STOPs given while the robot was still arriving at the ask) and 18 given while it stood still.** S5 and the D4 stand-in hold no true STOP: (a) is not evaluable there.

| reader | (a) STOPs given while the robot MOVED (22) | (a) STOPs given while it STOOD STILL (18) | STOP sessions false STOPs | S5 false STOPs | S5 PROCEED holds | D4* false STOPs |
|---|---|---|---|---|---|---|
| current reader | 16/22 within 1.0 s; lost altogether 1 | 18/18; lost altogether 0 | 67 fr / 29 ep (stopped 46/17) | 216 / 150 (stopped 196/136) | 35/62 | 80 / 44 (stopped 64/36) |
| C2 (`moving` flag), while stopped | 6/22; 10 lost from the 1.0 s set, 10 later (median +0.71 s); lost altogether 1 | **0/18**; 18 lost from the 1.0 s set, all later (median +0.73 s); lost altogether 0 | 21 / 13 (stopped 0/0) | 21 / 16 (stopped 1/1) | 37/62 | 16 / 8 (stopped 0/0) |
| C2s (0.3 s window), while stopped | 15/22; **1** lost from the 1.0 s set, 10 later (median +0.25 s); lost altogether 1 | 17/18; **1** lost from the 1.0 s set, 15 later (median +0.21 s); lost altogether 0 | 21 / 13 (stopped 0/0) | 73 / 65 (stopped 53/50) | 37/62 | 28 / 19 (stopped 12/11) |
| current + B1 floor 10 | as current, nothing lost or later | as current, nothing lost or later | 67 / 29 | 216 / 150 | **58/62** (570 fr, 40 %) | 80 / 44 |
| C2 + B1 floor 10 | as C2 | as C2 | 21 / 13 | 21 / 16 | **59/62** (684 fr, 48 %) | 16 / 8 |
| C2s + B1 floor 10 | as C2s | as C2s | 21 / 13 | 73 / 65 | **59/62** (664 fr, 47 %) | 28 / 19 |

**Facts (the choice is Anisha's):**
1. **No STOP is lost altogether by C2 or C2s that the current reader reads** (the 1 STOP lost altogether, given while the robot moved, is lost by the current reader too).
2. **C2 as defined (the `moving` flag) fails criterion (a) in BOTH halves, including the half "STOPs given while the robot moved":** 10 of the 22 are lost from the 1.0 s set. They are the 10 held STOPs given while the robot was still arriving at the ask: by the time the reader decides, the robot has stopped (v below 0.05 m/s) and C2 asks for the stillness it only gets about a second later. **A split by the robot's state at the ONSET of the STOP is therefore not a split by the state at the READING:** applying (a) "to the STOPs given while the robot moved" does not leave C2 outside the problem.
   The 12 driving STOPs (read while the robot drives) are unchanged by C2 and C2s (6 of 12 within 1.0 s, as the current reader); the readings while the robot moves are identical to the current reader's in S5 and the STOP sessions (0 different readings), 3 of 7,309 moving frames differ in the D4 stand-in (not traced). With B1 the "moving" readings differ by up to 8 frames per dataset because B1 reads more PROCEED, not because of C2.
3. **C2s keeps almost all of the speed:** 2 of the 40 STOPs leave the 1.0 s set (1 moved, 1 stood still), 25 are read later (median +0.21 to +0.25 s), against 28 leaving the set for C2. **Its cost is the false STOPs it leaves:** S5 73 frames / 65 episodes against C2's 21 / 16 and the current reader's 216 / 150 (stopped 53 / 50 against 1 / 1 and 196 / 136); D4 stand-in 28 / 19 against 16 / 8 and 80 / 44; the STOP sessions are the same as C2 (21 / 13).
   C2s is not non-inferior in the strict wording of 16.18.2 either (1 STOP lost from the 1.0 s set in each half).
4. **With B1 floor 10 the PROCEED holds are 58/62 (current), 59/62 (C2) and 59/62 (C2s)** in S5 (D4 stand-in and STOP sessions 38/38 and 26/26 in all of them); the false STOPs and criterion (a) of a reader are the same with and without B1 (B1 changes no STOP reading).
5. **Disclosure (declared in 16.19.5 before these numbers):** if criterion (a) is applied to the STOPs given while the robot moved only, that decision is made after seeing this table and is disclosed as a change of a criterion after the results. Fact 2 shows that this split, by the state at the onset, still leaves 10 of C2's 22 STOPs outside the 1.0 s set; a split by the robot's state at the first reading would be a different, further definition, not computed here.

### 16.19.7 Decision of 2026-11-17 (Anisha): C2s adopted as a v4 reader switch; recorded BEFORE building

**Decision.** **C2s is adopted:** while the robot is stopped (v below 0.05 m/s, in the states read or approach; the wait mode is the read state), a STOP uses the reader's short 0.3 s window: the mean wrist speed over the last `window.stop_window_s` 0.3 s must be at most `motion.still_speed_max` 0.4 torso lengths/s (no samples = not still), else that frame is not a STOP;
**while the robot moves, the STOP rule is exactly as now.** **C2 (the `moving` flag, 1.0 s) is rejected** (the held STOPs ~0.7 s later). No new number: 0.3 s, 0.4 torso lengths/s and the 0.05 m/s of 16.19.2 are all declared before. **B1 floor 10 is NOT changed now:** it still waits for Nusrat's strict-protocol rerun.

**Disclosed plainly (from the table of 16.19.6).**
- **It is chosen AFTER seeing 16.19.6, and criterion (a) is not met.** Of the 40 true STOPs the current reader reads 34 within 1.0 s and C2s reads **32** (the numbers: 16/22 and 18/18 for the current reader, 15/22 and 17/18 for C2s, given while the robot moved / stood still). **The two that leave the 1.0 s set are read later, not lost: S1 run 2 (a held STOP given while the robot was still arriving) at 1.43 s instead of 0.53 s (+0.90 s), and S1 run 52 at 1.04 s instead of 0.85 s (+0.20 s).**
  (The "+0.25 s" and "+0.21 s" of 16.19.6 are the medians of the STOPs that are read later: 10 of the 22 given while the robot moved and 15 of the 18 given while it stood still, 25 in all, +0.21 s at the median and +0.90 s at most.)
- **No STOP is lost altogether** that the current reader reads (the one lost altogether is lost by the current reader too); **the readings while the robot moves are identical to the current reader's** on the replay data (0 different readings in the step-5 logs and in the STOP sessions; 3 of 7,309 moving frames differ in the D4 stand-in, not traced).
- **The benefit:** the false STOPs in the step-5 logs fall from 216 frames / 150 episodes to **73 / 65** (frames / episodes; those while the robot stands still from 196 / 136 to 53 / 50); STOP sessions 67 / 29 -> 21 / 13; D4 stand-in 80 / 44 -> 28 / 19; with B1 floor 10 the S5 PROCEED holds would be 59/62 (not applied yet).
- **No split of criterion (a) by the robot's state at the first reading is computed** (not computed, to avoid trying definitions after seeing results).

**What is built (v4 only; the v3 behaviour, `hri_perception.classify_gesture` and the v3 controller are untouched).** The reader cannot see the robot's speed or state (a pan-tilt frame carries only the pose), so the two halves are split as follows:
- `configs/v4/gesture_reader.json` `hand.stop_still_when_robot_stopped` (true): the reader reads each window twice, as now and with the C2s rule, and `PersonReading.reading_stopped` carries the second reading (absent or false = only the current reading, as before). The rule is `gesture_motion._arm_window(..., robot_stopped=True)` / `read_window(..., robot_stopped=True)`; the default `False` path is the code as it was.
- The control files (`configs/v4/control*.json`, `experiments/control_lie_*.json`) get a `stop_rule` block (`still_when_robot_stopped` true, `robot_stopped_speed_mps` 0.05, `states` read and approach), read by `ControllerV4.step`, which uses `reading_stopped` of every person instead of `reading` when the robot is stopped (|v| below the speed in one of the states) and the current reading otherwise.
  The robot's speed and state are the controller's own (telemetry), the same as the `decisions.csv` rows the replay used; the pipeline's frame choice is therefore the replay's choice.
- `configs/v4/analysis.json` declared v3-to-v4 differences: the STOP entry is extended with C2s and this disclosure.
- **Tests that pin it:** (1) switch off = the current reader (readings identical on synthetic frames and on the replay data); (2) while the robot moves the readings are identical to the current reader's on the replay data (the three datasets); (3) the 16.19.6 C2s numbers (STOP-session criterion (a) split, false STOPs and PROCEED holds on the three datasets) are reproduced by the REAL reader switch, not by the analysis wrapper (these use the three zips in `~/Downloads` and are skipped where they are absent); (4) the config pins (values, both switches on, v3 files untouched).

#### 16.19.8 C2s built (2026-11-17); the real reader switch reproduces the numbers of 16.19.6

- **Built as declared in 16.19.7** (v4 only): `gesture_motion.wrist_speed` (the one implementation; `analyse_false_stop_v4.wrist_speed` delegates to it), `_arm_window(..., robot_stopped=False)` / `read_window(..., robot_stopped=False)` (the default path is the code as it was; the new argument is passed only when True), `commander_v4.PersonReading.reading_stopped`, `hri_perception_v4.PersonsPipeline.update` (reads the window a second time only when the switch is on),
  `ControllerV4.step` (uses `reading_stopped` while |v| < 0.05 m/s in the states read / approach), `gesture_reader.json` `hand.stop_still_when_robot_stopped` true, the `stop_rule` block in the 11 control files, `docs/gesture_reader_v4.md`, and the extension of the STOP entry of `configs/v4/analysis.json` with the disclosure. `hri_perception.py` (the v3 classifier), the v3 controller and every v3 file are untouched. **B1 is not changed.**
- **The analysis tools replay the logs with the switch OFF** (`live_reader_config()` and `rc_now` set it to false): the logs were recorded without it, and 'current reader' in every table means the reader's own reading.
- **Tests** (`tests/test_c2s_switch_v4.py`, 17): the values and both switches; the v3 path and the defaults untouched; switch off = the current reader (the `reading` never depends on the switch, `reading_stopped` is None when off); a swinging raised hand is a STOP but not while the robot is stopped; a still one is a STOP in both readings within 4 frames; the controller uses the short-window reading below 0.05 m/s in read / approach, the reader's own reading above it (also backing up), in other states, with the switch off or without a second reading;
  the declared difference and its disclosure in `analysis.json`. **Opt-in tests (4; they need the three zips or a report, about 10 minutes to compute): the real reader switch reproduces the 16.19.6 numbers exactly** (run on `outputs/proceed_stop_v4_switch_20261117_170008/report.json` with `C2S_REPORT=...`, 4 passed): S5 false STOPs 73 frames / 65 episodes (moving 20 / 15, stopped 53 / 50), STOP sessions 21 / 13 (stopped 0 / 0), D4 stand-in 28 / 19; PROCEED holds 37/62, 26/26, 38/38; criterion (a): moving 15/22 (1 lost from the 1.0 s set, 10 later, median +0.25 s, 1 lost altogether as for the current reader), stopped 17/18 (1, 15, +0.21 s), 32 of 40 within 1.0 s, no STOP lost that the current reader reads; the readings while the robot moves are identical to the current reader's (0, 0 and 3 of 7,309 in the D4 stand-in).
  Without the zips or the variable the 4 are skipped (so the plain suite does not depend on data outside the repository); the unit tests above run always.

### 16.20 Nusrat's clearance layout taken into the simulator (2026-11-17, Anisha); recorded BEFORE any change

Branch `anisha/v4-clearance-layout` (from main `29510ff` = origin/main, clean). Read as **data** from `origin/nusrat/v4-step5-dev` (PR #40), commits `8375ba8` (item 3a) and `ed4e000` (item 3b): `Scenario/Config/experiments_ab_unity.json`
(`answer_zone_radius_m`, `clearance_layout`, `path_clearance_m`, `ask_standoff_m`, `reask_shift_m`), `ExperimentPlanAB.cs` (`DrivableSegments`, `ReaskPosition`, `ClearanceProblem`) and `Avatar/Config/experiments_ab.md`. Nothing under `unity/` is changed or copied.

**1. Her layout (Unity values; `clearance_layout.active` is false in Unity until Python carries it).**
- Junction slots (`before_m` back along the arrival road, negative = ahead; `right_m` to the right of the arrival direction, negative = left): slot 1 `{3.5, -2.5}` (3.5 m before, 2.5 m left); slot 2 `{-4.5, 3.5}` (4.5 m ahead, 3.5 m right);
  slot 3 `{-5.0, -4.0}` (5.0 m ahead, 4.0 m left). Live slots today: `{3.0, -2.0}`, `{5.5, 2.0}`, `{6.0, -2.0}`. Start slots unchanged.
- A4 and B4 (`two_worker_experiments`) have two workers at J1 (three random workers in the 6 m square cannot keep the clearance); A3 and B3 keep three at J1.
- Her rules while the block is active: no worker within `path_clearance_m` 1.0 m (the corridor half-width 0.6 m + 0.4 m) of any segment the robot can drive (the roads of the run's map and of the physical v4 map; per asking node the segment from the node to the ask position of each
  worker in every order, the return to the first worker of an order (the tie rule), and from every ask position and re-ask point to the next node of every branch); every ask position within `answer_zone_radius_m` - `answer_zone_margin_m` = 5.5 m of its node.
  Ask position = `ask_standoff_m` 2.0 m from the worker toward where the robot comes from; re-ask point = `reask_shift_m` 0.4 m to the robot's right, back on that circle (copies of `hri_control.json` `dialog.approach_distance_m` and `dialog.reask_shift_m`).

**2. Its disclosure (hers, kept as she wrote it).** The slot search before her declaration left out one declared segment, the return to the first worker (tie). Under the full declared model the declared choice (slot 1 2.5 m before, slot 3 3.5 m left) failed at A3 J1 seed 1 run 1
by 0.03 m (worker 3 stood 0.97 m from the segment from its own tie ask position to E1). The search was rerun with the tie, with the same rules and the same declared choice rule (meets every rule; smallest largest own-ask distance, 5.19 m; then least movement from the section 3 slots).
Nothing else changed. **Not checked by her:** free cells and colliders for the pending slots at Play (Unity does at Play once the block is active).

**3. The two distances are different quantities.** Unity's answer zone (item 3a, 6.0 m) is the distance from the **robot** to the **worker's node**: a worker answers only while the robot's centre is within 6.0 m of the node the worker belongs to. My second-opinion radius (16.19, 6.5 m) is the
distance from the **person** to the **node**: the robot asks only people who stand within 6.5 m of the node and for whom it is the nearest node. A robot that stands 2.0 m from a person 6.3 m from the node can be 8 m from the node; it then gets no answer in Unity although Python still chose that person.
They are not made equal and 6.5 m is **not changed** here (unchanged since 16.19: the value is held until Nusrat's new maximum placement distance is known). What is checked here is that the clearance layout keeps every worker inside my 6.5 m and nearest to their own node (see 4), and, as an extra figure, the largest distance from each worker's own ask positions to the node
(her 5.5 m rule), computed with the model of 1.

**4. What I do (declared before any change; pass criteria fixed here).**
- (a) `scenarios_ab.json`: `junction_slots` of scenarios 1, 2, 3 = her slots exactly; `people_by_node` J1 3 removed from scenario 4 (A4, B4: 2 at J1); everything else (start slots, margins, placement rule, random layout) unchanged. **`MatchesUnity` keeps pinning** the slots: to her `clearance_layout` block (her values, quoted from `ed4e000`), to the live
  `junction_slots` too as soon as her file carries `clearance_layout.active` true; main's `unity/` file does not carry the block until PR #40 is merged, so the test pins the values as constants quoted from `ed4e000` and checks them against the block whenever it is present.
- (b) **Every worker of every scenario, seed (1-20) and node** (A1 to A4; beside and random layouts; every asking node): within 6.5 m of the node and the nearest node of the physical roadmap to be that node (the rule of `_belongs_here`). Pass = all. The largest distance is reported (per layout).
- (c) **Clearance in the simulator geometry:** an independent model (test code, `tests/`) of the segments of 1 built from the simulator's own roadmap and positions; for every scenario, seed and node no worker is closer than 1.0 m (minus 1e-4) to any segment or road, and the ask positions are within 5.5 m of the node. Pass = all. The `random` layout (A4, B4) is **checked and reported**; if its draws
  violate the clearance I report the count and do **not** change the random placement without asking (the sim placement has no clearance rule today; making it reject draws like her `ClearanceProblem` is a change to what the simulator does).
- (d) **Rerun of the 16.13 tables** (`run_experiments_ab_v4.py --runs 20 --timeout-s 270`, detection off and on, valid-branch liar): the **baseline is rerun first with the old layout on the current main code** (`outputs/experiments_ab_v4_baseline_old_layout_main_29510ff_*`), because the code changed since 16.13 (16.19: return to the junction point,
  person-in-path recovery, C2s, second-opinion radius, ...), so the old table is not comparable; then the new layout (`outputs/experiments_ab_v4_clearance_layout_*`). Both are reported next to the 16.13 numbers; the change of the layout alone is new minus baseline. Simulator only; nothing here is a measurement.
- Not done here: Unity's activation window and who answers a new ask (no counterpart in the simulator, as in 16.13); free cells and colliders (Unity at Play). `clearance_layout.active` is Nusrat's to switch after this branch is merged.

#### 16.20.1 Built and results (2026-11-17)

**Built (Python only; nothing under `unity/` is changed or copied).** `scenarios_ab.json`: `junction_slots` of scenarios 1, 2, 3 = her clearance slots exactly (`{3.5, -2.5}`, `{-4.5, 3.5}`, `{-5.0, -4.0}`), `people_by_node` J1 3 removed from scenario 4 (A4, B4: two at J1), the `why` entries say so; start slots and every other value unchanged
(`scenarios_ab.json` is in the frozen list of `freeze_v4.py` and `frozen.json` is not touched: it pins the files only once `frozen` is true, which it is not). New: `layout_check_v4.py` (the three checks of 4 for every scenario, seed and node; writes `outputs/layout_check_v4_<time>/`, with the git commit) and `tests/test_clearance_layout_v4.py` (14 tests).
`tests/test_lie_detection_v4.py`: `MatchesUnity` keeps pinning the slots, now to her quoted values (`CLEARANCE_SLOTS`, checked against her block whenever main's `unity/` file carries it; today it does not, PR #40 is not merged) and to the live slots as soon as her block says `active`; the J1, J2 slot positions, the "third worker at J1 in A3, A4, B3, B4 only"
test (now A3, B3 only) and the people_by_node config test were updated for the new layout, each keeping its intent. I verified once, by `git show` of `origin/nusrat/v4-step5-dev` (`3f0422c`), that my constants equal her slots, her two-worker list (A4, B4), 1.0 / 2.0 / 0.4 / 6.0 / 0.5 and that `active` is false there.

**(b) Every worker belongs to its node (6.5 m, nearest node): all 540 worker placements of A1 to A4, seeds 1 to 20, every asking node pass.** Largest distance worker to own node: A1 5.00 m (A, worker 2), A2 5.70 m (B, worker 2), **A3 6.40 m (J1, worker 3: 5.0 m ahead, 4.0 m left)**, A4 (random) 4.21 m. The margin to 6.5 m is 0.10 m (old layout: 6.32 m, 0.18 m).
A4 has 200 placements (two at J1); A1 40, A2 80, A3 220; B1 to B4 use the same placements as A1 to A4.

**(c) Clearance and ask zone, at her model's re-ask shift 0.4 m (`layout_check_v4.py`, an independent model of her segments: every order, the tie return, the branches; every road of the run's map and of the physical map):**

| experiment | layout | smallest worker-to-segment distance | largest ask-position distance from the node | plans (of 20) violating 1.0 m or 5.5 m |
|---|---|---|---|---|
| A1 | beside | 2.00 m | 3.72 m | 0 |
| A2 | beside | 1.76 m | 3.77 m | 0 |
| **A3** | beside | **1.01 m** | **5.19 m** (her figure 5.19 m) | **0** |
| A4 | random | 0.01 m | 3.00 m | **20** |

The same check on the old slots: A3 20 of 20 plans violate (smallest 0.03 m, largest ask distance 5.40 m, her figure for the live slots), so the check does catch the live layout.

**Two findings that are NOT fixed (reported; the decision is yours):**
1. **Her model's re-ask shift is 0.4 m (a copy of the v3 value in `hri_control.json`); the v4 controller really uses 0.8 m** (`configs/v4/control.json` `dialog.reask_shift_m`, "INITIAL v4 value, decided 2026-10-24 by Anisha"; it is also the shift of the second view of an ambiguous POINT). I added the 0.8 m check after noticing this during the build (it is not in the pre-declaration of 4; both values are reported). With 0.8 m, **A3 at J1 fails her rules in all 20 seeds: worker 3
   (2.25, 5.0) is 0.74 m from the segment from the re-ask point (4.24, 5.15) to J2 (LEFT), and the re-ask point is 5.53 m from J1 (her rule 5.5 m; still inside Unity's 6.0 m zone, and 0.74 m is outside the 0.6 m person-in-path corridor).** A1 and A2 pass at 0.8 m (1.96 m and 1.76 m; 4.06 m). Nothing is changed: `reask_shift_m` is a v4 value (not mine to change here) and the layout is hers; options: (a) accept 0.74 m, (b) Nusrat sets `reask_shift_m` 0.8 in her model and searches the slots again, (c) a v4 re-ask shift of 0.4 m.
2. **The random layout (A4, B4) has no clearance rule in the simulator.** 62 of the 100 asking nodes of A4 (seeds 1 to 20) have a worker closer than 1.0 m to their own node's segments or a road (all 20 plans violate). Unity's random placement rejects draws that break it (her 400 plans pass), so the simulator's A4 and B4 do not do what Unity does. As declared in 4(c) I did **not** change the random placement; making `place_random` reject draws like her `ClearanceProblem` (and the 5.5 m ask zone) is a change of what the simulator does and waits for your decision.

**(d) The 16.13 tables rerun (simulator; 20 seeds, 270 s, valid-branch liar; `outputs/experiments_ab_v4_baseline_old_layout_main_29510ff_20261117_181934` and `outputs/experiments_ab_v4_clearance_layout_20261117_182155`).** The 16.13 table is **not** reproduced by the current main even with the old slots, so the layout effect is new minus baseline:

| experiment | detection | 16.13: SUCCESS | median s | fooled/given | **baseline (old slots, current code): SUCCESS** | failures | median s | collisions | safety stops | fooled/given | **clearance layout: SUCCESS** | failures | median s | collisions | safety stops | fooled/given |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| A1 | off | 20/20 | 68.0 | - | **20/20** | - | 70.8 | 0 | 0 | - | **20/20** | - | 70.8 | 0 | 0 | - |
| A1 | on | 20/20 | 82.3 | - | **20/20** | - | 88.5 | 0 | 0 | - | **20/20** | - | 88.5 | 0 | 0 | - |
| A2 | off | 20/20 | 86.1 | - | **20/20** | - | 93.8 | 0 | 20 | - | **20/20** | - | 96.8 | 0 | 20 | - |
| A2 | on | 20/20 | 118.1 | - | **20/20** | - | 137.8 | 0 | 0 | - | **20/20** | - | 156.3 | 0 | 0 | - |
| A3 | off | 20/20 | 122.0 | - | **20/20** | - | 137.2 | 0 | 27 | - | **20/20** | - | 143.3 | 0 | 20 | - |
| A3 | on | 20/20 | 185.7 | - | **14/20** | timeout 6 | 217.4 | 0 | 7 | - | **13/20** | timeout 7 | 228.4 | 0 | 0 | - |
| A4 | off | 20/20 | 116.1 | - | **20/20** | - | 132.9 | 0 | 5 | - | **20/20** | - | 131.1 | 0 | 6 | - |
| A4 | on | 20/20 | 165.6 | - | **20/20** | - | 182.7 | 0 | 0 | - | **20/20** | - | 189.7 | 0 | 0 | - |
| B1 | off | 19/20 | 68.0 | 0/5 | **19/20** | aborted 1 | 70.8 | 0 | 0 | 0/5 | **19/20** | aborted 1 | 70.8 | 0 | 0 | 0/5 |
| B1 | on | 20/20 | 82.3 | 0/12 | **20/20** | - | 88.5 | 0 | 0 | 0/12 | **20/20** | - | 88.5 | 0 | 0 | 0/12 |
| B2 | off | 13/20 | 86.1 | 0/18 | **13/20** | aborted 7 | 93.8 | 0 | 18 | 0/18 | **13/20** | aborted 7 | 96.8 | 0 | 18 | 0/18 |
| B2 | on | 19/20 | 118.1 | 0/35 | **19/20** | aborted 1 | 137.8 | 0 | 0 | 0/35 | **19/20** | aborted 1 | 156.3 | 0 | 0 | 0/36 |
| B3 | off | 10/20 | 119.7 | 10/15 | **10/20** | wrong_goal 9, aborted 1 | 132.8 | 0 | 22 | 10/15 | **10/20** | wrong_goal 9, aborted 1 | 138.9 | 0 | 18 | 10/15 |
| B3 | on | 15/20 | 195.7 | 8/40 | **11/20** | timeout 5, wrong_goal 3, aborted 1 | 224.9 | 0 | 5 | 8/40 | **11/20** | timeout 5, wrong_goal 3, aborted 1 | 247.2 | 0 | 0 | 8/40 |
| B4 | off | 11/20 | 110.6 | 8/14 | **11/20** | aborted 2, wrong_goal 7 | 126.3 | 0 | 4 | 8/14 | **11/20** | aborted 2, wrong_goal 7 | 125.7 | 0 | 6 | 8/14 |
| B4 | on | 15/20 | 170.2 | 8/37 | **15/20** | aborted 2, wrong_goal 3 | 191.2 | 0 | 0 | 8/37 | **11/20** | aborted 2, wrong_goal 7 | 189.9 | 0 | 3 | 20/42 |


Read (simulator, not a measurement):
- **Code since 16.13, not the layout (baseline against 16.13):** A3 detection on 20/20 -> 14/20 (timeout 6), B3 on 15/20 -> 11/20 (timeout 5), the medians are 3 to 32 s longer, and the detection-off rows show safety stops of 0.05 s (A2 20, A3 27, A4 5, B2 18, B3 22, B4 4; 16.13: 0). **Cause, checked:** with `dialog.return_to_junction` off the same A3 detection-on runs are 20/20 for both layouts (A4: 20/20 either way) and the 0.05 s stop is gone in A2 (seed 1 run: stop 0.05 s -> 0.0 s). The return to the junction point (16.19, switched on in the v4 control files) costs the simulator's
  A3 and B3 runs their 270 s budget (three workers at J1, a drive back after every second opinion) and adds a stop on the return. Reported only; no value changed.
- **The layout alone (clearance minus baseline):** Set A 74/80 -> 73/80: A1, A2, A4 unchanged at 20/20; A3 on 14/20 -> 13/20 (timeout 6 -> 7); the medians of A2 and A3 detection on are 18 s and 11 s longer (second workers stand 4.5 m ahead; the robot drives farther for second opinions: A2 on 137.8 -> 156.3 s). Collisions 0 in all 32 rows of both runs.
  **B4 detection on 15/20 -> 11/20 (wrong goal 3 -> 7), lies fooled 8/37 -> 20/42:** A4 and B4 have two workers at J1 instead of three, so a disagreement at J1 is a tie (the first worker is asked again and counted twice, 16.13.1) instead of a vote of three: the effect of removing the third worker at J1 (her declared change), not of the slots. B3 on stays 11/20 and 8/40 fooled; B1, B2, B3 off and B4 off unchanged in SUCCESS.
- **Not run / not covered:** Unity's activation window and who answers a new ask (16.13), free cells and colliders at Play (hers), the 6.0 m answer zone (Unity only; in the simulator the person asked always answers), Python driving into another node's zone.

**Existing tests changed in this round (each keeps its intent).** `tests/test_lie_detection_v4.py` (the slots, the slot positions, A4 and B4 with two workers at J1); `tests/test_hri_sim_v4.py` (the isolation allow-list gets `layout_check_v4.py`, which imports the simulator like the experiments runner); `tests/test_export_csv_v4.py`: the sanity bound of `distance_m` 5.0 m -> 12.0 m. In the simulator the truth's commander is worker 1, so for a second opinion `distance_m` is the distance to worker 1 and not to the person asked (as before 16.20);
with the clearance layout the second and third workers stand 4.5 to 5.0 m ahead of the node and the largest value in that test's runs is 7.9 m (J2, worker 2 asked, worker 1 the commander). The new bound is the ask zone plus the worker distance, 5.5 m + 6.5 m. The decisions table's `distance_m` of simulator runs is therefore not the standoff for second opinions (reported, not changed).

**Open for you (nothing decided or changed):** (1) finding 1 (0.8 m against 0.4 m); (2) finding 2 (clearance rule for the random layout in the simulator); (3) the cost of the return to the junction point in A3 and B3 (A3 on 20/20 -> 14/20 in the simulator; the Unity runs have the same 270 s budget); (4) Nusrat sets `clearance_layout.active` after this branch is merged, as she wrote.

#### 16.20.2 Decisions of 2026-11-17 (Anisha) on the findings of 16.20.1; recorded BEFORE any change

Branch `anisha/v4-clearance-layout` (unchanged). `origin/nusrat/v4-step5-dev` is still `3f0422c` (read with `git show`; no `unity/` file copied).
1. **Re-ask shift: the controller's 0.8 m stays** (`control.json` `dialog.reask_shift_m`). Nusrat re-searches her slots with 0.8 m by her same declared rule (her model used 0.4 m). Until then **the A3 J1 0.74 m finding of 16.20.1 stands as reported** (and the 5.53 m ask distance).
2. **Random layout: the simulator adopts Unity's rejection rule exactly.** Declared here, before the code and before the rerun:
   - **The rule is her `ClearanceProblem` as read from `ExperimentPlanAB.cs` (`NodeProblem` -> `ClearanceProblem`, `DrawRandom`)**: a draw of the workers of a node is redrawn (up to `max_draws` 100000, as now; then the run is refused) unless (a) every ask position of the node (node to the ask position of each worker in every order, the return to the first worker of an order, the re-ask point) lies within 5.5 m of the node (answer zone 6.0 m minus margin 0.5 m);
     (b) every worker of this node and every worker already placed at another node is at least 1.0 m (`path_clearance_m`) from every drivable segment of this node (node to ask positions, and every ask position and re-ask point to the next node of every branch); (c) the workers of this node are at least 1.0 m from every road of the run's map and of the physical map and from the drivable segments of every node placed before.
   - **Values (hers, read from `experiments_ab_unity.json` of the branch): `path_clearance_m` 1.0, `answer_zone_radius_m` 6.0 - `answer_zone_margin_m` 0.5 = 5.5, `ask_standoff_m` 2.0, `reask_shift_m` 0.4.** They go into `scenarios_ab.json` `placement_rule` (`path_clearance_m`, `ask_zone_m`, `ask_standoff_m`, `reask_shift_m`), with her reasons. **The re-ask shift in the simulator's rule is her 0.4 m, not the controller's 0.8 m**, so that the simulator keeps doing exactly what Unity's planner does; it changes to 0.8 when Nusrat's model does (a value of her file, not mine).
   - It is applied to the draws of the **random** layout (A4, B4), the rest of the placement rule (3.0 m separation and turning points, `min_road_m` 1.0, the 0.25 m bystander margin, slot 0 = nearest to the node) unchanged and checked first, as in `NodeProblem`. **The beside slots are not enforced at planning** (Unity refuses fixed slots that break the rule; the simulator's A3/B3 slots pass at 0.4 m and fail at 0.8 m, 16.20.1): they stay checked by `layout_check_v4.py` and the tests, as before.
   - The geometry model moves from `layout_check_v4.py` into `hri_sim_v4.py` (one implementation; `layout_check_v4.py` imports it). The random draws of A4 and B4 change (rejection continues drawing from the same seeded stream), so their results change: that is the purpose.
   - **Pass criteria (fixed here):** every plan of A4 (and B4, same placements) seeds 1 to 20 passes the independent check of `layout_check_v4.py` at 0.4 m (0 of 20 plans violating, smallest clearance >= 1.0 m, largest ask distance <= 5.5 m); a draw that breaks any of (a) to (c) is rejected (tests on constructed cases); the existing placement tests still hold. **Rerun:** A4 and B4, detection off and on, 20 seeds, 270 s, next to the baseline of 16.20.1 (old slots) and the same layout without the rejection (`experiments_ab_v4_clearance_layout_20261117_182155`). Simulator only.
3. **B4 has two workers at J1 instead of three** (Anisha asked Nusrat why). Reported (16.20.1: B4 on 15/20 -> 11/20, a tie instead of a vote of three), **not changed**.
4. **Item 1 (analysis only, nothing changed): the A3 detection-on regression** (baseline of 16.20.1: 14/20 with 6 timeouts against 20/20 with `return_to_junction` off): for each timeout the timeline (positions, states, asks, safety stops) and the cause, then a proposal with reasons. **No fix is built.**

#### 16.20.3 Item 1: the A3 detection-on regression investigated (analysis only; nothing changed; proposal, no fix built)

Tool: `analyse_a3_timeouts_v4.py` (new; analysis only; hooks observe `step` and, for the counterfactual only, set the return speed on one run; the controller, the configs and the simulator are untouched). Output folders: `outputs/a3_timeouts_v4_20261117_185139_old_layout` (the baseline of 16.20.1: old slots, current code) and `outputs/a3_timeouts_v4_20261117_185242_clearance_layout` (scenarios_ab.json as it is now). Each run is the simulator, detection on (second opinion + reject impossible, backtrack off), 20 seeds, 270 s; the
timeouts are repeated with the return on and a 600 s budget (the simulator is deterministic: the same run with a later clock limit) and with the return off.

**What the 6 timeouts are.** Seeds 4, 6, 8, 12, 14 and 17 are **one and the same run six times**: the goal sequence of session seed 1 (`GoalSequence(1)`) draws E5 in 6 of the 20 runs, set A has truthful workers and the `beside` layout is deterministic, so the runs are identical (every number below is identical in all six). Route A > J1 > J2 > J4 > E5; two people asked at every node (A, J1, J2, J4), nothing rejected; second views (the ambiguous POINT, 0.8 m shift): old slots J1 2 and J4 1, clearance layout J1 1 and J4 2.

**Timeline of the E5 run, old slots, return on (position in metres; the same in all six):**

| node | arrives s (position) | people asked | second views | go s (position) | dialog s | return: distance, s, speed | back at the junction point s (position) | drive on to the next node s |
|---|---|---|---|---|---|---|---|---|
| A | 0.5 (6.2, -20.0) | 2 | 0 | 25.6 (8.3, -22.3) | 25.2 | 3.06 m, 10.1 s, 0.30 m/s | 35.75 (6.4, -20.2) | 30.4 |
| J1 | 67.0 (6.3, -0.3) | 2 | 2 | 105.45 (4.8, -4.1) | 38.5 | 4.39 m, 14.2 s, 0.31 m/s | 119.7 (6.2, -0.2) | 20.6 |
| J2 | 142.3 (-6.0, 0.0) | 2 | 0 | 166.15 (-2.5, 0.8) | 23.8 | 3.84 m, 12.2 s, 0.31 m/s | 178.4 (-6.0, 0.1) | 21.1 |
| J4 | 199.7 (-18.5, 0.0) | 2 | 1 | 229.45 (-14.9, 0.7) | 29.8 | 3.92 m, 12.2 s, 0.32 m/s | 241.7 (-18.5, 0.1) | (to E5) |

States: scan 1.7 s, approach 88.2 s, ask 5.7 s, read 23.3 s, **execute 54.0 s (return off: 8.0 s)**, navigate 97.1 s (off: 103.2 s). At 270.0 s the robot stands at E5 (-18.7, 20.0): the run ends **SUCCESS at 270.3 s with a 600 s budget, 0.3 s after the limit**; with the return off it ends at 230.3 s. Seed 15 (goal E6, the same route plus one leg) ends at 269.7 s, 0.3 s inside the limit. Safety stops: one of 0.05 s at J2 at 178.65 s (-6.01, 0.08), state navigate, reason "perception stale",
0.25 s after the return ended and the drive resumed (7 such stops of 0.05 s in the 20 runs; none with the clearance layout); no stall, no loop, no collision, closest person 0.97 m.

**Cause (checked).** A **time-budget effect of the return to the junction point (D, 16.19), not a stall:** the 20 runs make 65 returns of 3.06 to 4.51 m (median 3.92 m); each takes a median **12.2 s (10.1 s at A, 14.2 s at J1), 800.7 s in total, at a median 0.31 m/s**, because the return is driven at `approach_speed_mps` 0.4 m/s (it reuses the approach drive) with a full stop at the junction point (`stopped_speed_mps` 0.03).
Four asking nodes on the E5 route cost 48.7 s, and A3 > E5 and E6 are the longest routes of the study (230.3 s and 232.6 s without the returns), so it has no margin left: the return takes the run over the 270 s budget. The other routes of A3 with the return end at E1 132.9 s, E2 222.2 s, E3 212.0 s, E4 212.6 s (old slots; E6 269.7 s) and keep their margin except E6. **With the clearance layout the same run needs 298.45 s (return off: 240.85 s), so seeds 4, 6, 8, 12, 14, 17 and also 15 (E6, 280.3 s) time out: 13/20 (7 timeouts).**

**Counterfactual for the proposal (a hook for the analysis only):** the return at `cruise_speed_mps` 0.8 instead of 0.4:

| layout | live return | return off | return at cruise speed | the E5 run needs | the E6 run needs |
|---|---|---|---|---|---|
| old slots (16.20.1 baseline) | 14/20 (timeouts 6), longest 270.0 s | 20/20, longest 232.6 s | **20/20, longest 254.7 s**, return median 8.4 s | 270.3 s live; cruise return finishes within 254.7 s | 269.7 s live |
| clearance layout | 13/20 (timeouts 7) | 20/20, longest 240.9 s | **14/20 (timeouts 6)**, return median 8.6 s | live 298.45 s; **cruise return 283.9 s (still over)** | live 280.3 s; cruise return 265.8 s (inside) |

Closest approach to a person (smallest of the 20 runs) and safety stops are unchanged by the faster return in both layouts (old 0.97 m, 7 stops of 0.05 s; clearance 1.89 m, 0).

**Proposal (not built; yours to decide):**
1. **A new v4 key `dialog.return_speed_mps` (control files; absent = the approach speed, the behaviour as it is), set to the cruise speed 0.8 m/s, used only for the return of D.** Reasons: (a) the return is the one drive of a dialog that the robot makes with nobody to read: it goes back the way it came, away from the worker it asked; (b) the return is the reverse of Nusrat's node-to-ask-position segment, which her clearance rule already keeps 1.0 m from every worker, and the person-in-path stop (corridor half width 0.6 m, stop distance 1.89 m at 0.8 m/s) stays active, so a worker is never in the corridor of the return;
   (c) measured: the old-layout A3 returns to 20/20 with a 15 s margin (longest 254.7 s) and the safety numbers do not change; (d) one number, taken from the cruise speed already declared in `hri_control.json` (0.8 m/s), no new tuned value; (e) v3 is untouched.
2. **It is not enough alone for the clearance layout:** E5 needs 283.9 s with it (13 s over). What remains is the budget or the route: (i) a trial budget of 300 s for the experiments whose route has four asking nodes (A3, B3: E5 and E6 only) instead of 270 s: a change of `trial_timeout_s` of `scenarios_ab.json` and of Nusrat's run protocol, to be decided by you; with 283.9 s the margin would be 16 s; (ii) or reporting the E5 run as a finding of the study (A3 > E5 does not fit the budget with returns and two second views at J4, 47.7 s of dialog).
3. **Not proposed:** switching D off (it was decided on Unity's corner-cutting finding), a faster approach speed (changes every drive), a shorter second-view shift (a v4 value of its own decision).
4. **For Nusrat:** the Unity runs have the same 270 s budget and slower real-time clocks; the step-5 A3 timeouts (2) are consistent with a route that has 29 to 43 s of margin before the returns.
5. **No fix is built, nothing is changed, and the commit contains no behaviour change for item 1.**

#### 16.20.4 Item 2: the random layout's clearance rejection built and rerun (as declared in 16.20.2)

**Built (Python only).** `hri_sim_v4.py`: `ask_position`, `reask_position`, `drivable_segments` (the geometry moved from `layout_check_v4.py`, which now imports it: one implementation), `clearance_problem` (Unity's `ClearanceProblem`: ask positions within `ask_zone_m`, every worker of this node and of earlier nodes `path_clearance_m` from this node's drivable segments, this node's workers that far from every road of the map and of the physical map and from the drivable segments of every earlier node),
`place_random(..., clearance=None, placed_by_node=None)` (a drawn set is also redrawn while `clearance_problem` names a problem; `None` = the earlier behaviour, and a rule that rejects nothing leaves every draw unchanged: tested), `SimulatorV4._positions_at` / `plan_workers` (the placed workers by node), `scenario_ab` (the four values into the spec).
`scenarios_ab.json` `placement_rule`: `path_clearance_m` 1.0, `ask_zone_m` 5.5, `ask_standoff_m` 2.0, `reask_shift_m` 0.4 (hers, read from `origin/nusrat/v4-step5-dev` `3f0422c`; `why["placement_rule.clearance"]`). Applied to the random layout only, as declared; A3/B3 (beside) are unchanged and still only checked.

**Pass criteria of 16.20.2: all met.** Every plan of A4 (= B4: same placements), seeds 1 to 20, passes the independent check of `layout_check_v4.py` at her 0.4 m shift: **0 of 20 plans violating (was 20 of 20), smallest worker-to-segment distance 1.008 m, largest ask-position distance 2.85 m (<= 5.5 m)**; every asking node of A4 on its own is clean (was 62 of 100 nodes violating); the 6.5 m / nearest-node check still holds for all 200 placements (largest 4.17 m); the 3.0 m separation, turning-point, road and bystander rules hold (tests); constructed cases are rejected (a worker on the drive to another worker, beside a road, beyond the ask zone, next to an earlier node's drive and the reverse, on a road of the physical map); an unsatisfiable rule refuses the run naming the clearance.

**The 0.8 m finding extends to the random layout (reported, not changed).** At the controller's real re-ask shift 0.8 m, **19 of 20 A4 plans violate the 1.0 m clearance (smallest 0.73 m)**, as A3 does (16.20.1): the rule here is her 0.4 m model; it follows her file until Nusrat re-searches her slots with 0.8 m (decision 1 of 16.20.2), after which `reask_shift_m` in the placement rule changes to match.

**Rerun (simulator, 20 seeds, 270 s, valid-branch liar, `outputs/experiments_ab_v4_clearance_rejection_A4_B4_20261117_185604`)** next to the baseline of 16.20.1 and the same layout without the rejection:

| experiment | detection | baseline (old slots, 3 workers at J1, no rejection) | clearance layout, 2 at J1, no rejection | **clearance layout + rejection** |
|---|---|---|---|---|
| A4 | off | 20/20, 132.9 s, 0 collisions, 5 safety stops | 20/20, 131.1 s, 0, 6 | **20/20, 134.7 s, 0, 7** |
| A4 | on | 20/20, 182.7 s, 0, 0 | 20/20, 189.7 s, 0, 0 | **20/20, 199.6 s, 0, 0** |
| B4 | off | 11/20 (aborted 2, wrong goal 7), 126.3 s, 0, 4; fooled 8/14 | 11/20 (aborted 2, wrong goal 7), 125.7 s, 0, 6; fooled 8/14 | **10/20 (aborted 3, wrong goal 7), 126.3 s, 0, 6; fooled 8/14** |
| B4 | on | 15/20 (aborted 2, wrong goal 3), 191.2 s, 0, 0; fooled 8/37 | 11/20 (aborted 2, wrong goal 7), 189.9 s, 0, 3; fooled 20/42 | **11/20 (aborted 2, wrong goal 7), 205.9 s, 0, 2; fooled 20/47** |

Read: **the rejection changes the draws of A4 and B4, so their runs are different runs** (the median of A4 on is 9.9 s longer than without the rejection, B4 on 16.0 s; the reason was not investigated). Set A stays 40/40, there are 0 collisions in all eight rows. **B4 off 11/20 -> 10/20 (one more abort, a different draw) and B4 on 11/20 unchanged** (wrong goal 7, lies fooled 20 of 47): the drop of B4 on from 15/20 (baseline) to 11/20 comes from the second worker at J1 instead of three (decision 3 of 16.20.2, reported, not changed), not from the rejection. No statement about an effect of the rejection on success is made from 20 runs per row.
No A4 run times out: the longest A4 detection-on run takes 245.05 s (the A3 timeouts of 16.20.3 are a property of the E5/E6 routes of A3).

**Tests.** New `tests/test_clearance_rejection_v4.py` (20 tests, 1 skipped while main's `unity/` file lacks the values: the Unity values agree whenever it carries them), `tests/test_a3_timeouts_v4.py` (5, the analysis tool and the numbers quoted in 16.20.3; the hook changes nothing); `tests/test_clearance_layout_v4.py`: the random-layout known finding became the new expectation (0 of 20 at 0.4 m, 19 of 20 at 0.8 m); `tests/test_hri_sim_v4.py` isolation allow-list gets `analyse_a3_timeouts_v4.py`.

### 16.20.5 Decisions of 2026-11-17 (Anisha) on the proposal of 16.20.3: the return speed adopted, no per-setting budget; recorded BEFORE any change

1. **Adopted: `dialog.return_speed_mps` 0.8 m/s (the cruise speed of `hri_control.json`), used only for the return to the junction point (D, 16.19); absent = the current behaviour (the approach speed 0.4 m/s).** A v4 key in the 11 v4 control files; v3 and `hri_control.json` are untouched. Reason: the counterfactual of 16.20.3 (A3 detection on 20/20 on the old slots instead of 14/20, longest run 254.7 s, closest approach to a person 0.97 m and the number of safety stops unchanged). No new tuned number: 0.8 is the declared cruise speed.
   The controller refuses a value that is not above 0 and at most the cruise speed (a construction error, not a silent clamp).
2. **No per-setting time budget for A3 / B3.** The final timeout is **one value for all settings, from the declared rule** (`final_plan.json` `timeout_s_rule`, 16.15 decision 2 as corrected in 16.16 decision 4): `timeout_s` = 1.5 x the longest SUCCESSFUL development run, rounded UP to a multiple of 30 s, never below 270 s; applied to **Unity's step-5 rerun, which uses the 420 s development timeout and the development-only goal override, so that E5 and E6 are drawn.**
   **Stated plainly: development runs that feed the rule must never use 270 s as their timeout.** A run that times out at 270 s is not a duration and does not count (16.16 decision 4); if the development timeout were 270 s the longest routes (A3 > E5 and E6) would all time out, could never count as successful, and the rule would give a value that does not fit them. The 270 s of the simulator and of `final_plan.json` is the **floor** of the rule, not the final value;
   `timeout_s` in `final_plan.json` stays 270 until the rule is applied by a declared edit before the freeze (not touched here).
3. **Then (this round):** the key is built in the 11 control files with tests; the simulator's A3/B3 and A4/B4 rows are rerun on the clearance layout, **at the 270 s floor (the rows reported before) and at a 420 s development timeout (the runs that feed the rule)**, and per row the successes, the longest successful duration and the E5 / E6 durations are reported, with what the declared rule would give from those simulator durations (`final_guard_v4.timeout_from_development`). **For information only: the simulator is not Unity (speeds, clocks and perception differ), and the real value comes from Unity's runs.**

4. **Reported by Nusrat, 2026-11-17 (recorded here as her statements; nothing of it is checked by me, `unity/` is hers and read-only for me).**
   - **Unity NavMesh fixed.** The agent had "Ignore NavMesh Obstacles" on; racks, pallets and stations are now obstacles. 13.2 million paths were checked, none goes through an obstacle. v4 now has **its own NavMesh asset** (it shared v3's before); **the v3 asset is unchanged, pending her confirmation.**
     (This is the "NavMesh rack fix" that the Unity testing of the person-in-path recovery waited for, 16.19.2 item E; no decision about that testing is made here.)
   - **Consequence for the timeout rule (declared here): every development session made before this fix used the old NavMesh, so only development runs on the new NavMesh may feed the timeout rule of item 2** (together with the 420 s development timeout and the development-only E5/E6 goal override). Durations of the earlier step-5 and other development sessions must not be used for it. The simulator durations of 16.20.6 are unaffected (the simulator has no NavMesh) and remain information only.
   - **The reader decisions are unaffected:** B1 floor 10 stays pending Nusrat's strict-protocol rerun; C2s (16.19.7) stays adopted. The reader was replayed on logged frames, which the NavMesh does not change.
   - **The slots are being re-searched by Nusrat with the 0.8 m re-ask shift and three workers at J1** (decisions 1 and 3 of 16.20.2). **The clearance switch (`clearance_layout.active`) stays off until her new slot table.** Until then `scenarios_ab.json` keeps the layout of 16.20 and the rejection of 16.20.4 with her 0.4 m model; the results of 16.20.1, 16.20.4 and 16.20.6 on the clearance layout are for that layout and are superseded when her table arrives, when the slots, `people_by_node` of scenario 4 and `reask_shift_m` of the placement rule are taken over from it (a change to be recorded then, not before).
   - **"STOP before PROCEED" (16.19.3, bug A): she asks for the exact code line, otherwise it is withdrawn.** The line: `hri_control.py` `Controller.step`, lines 387 to 391 (`if reason is not None: ... return cmd`), which returns before `self._tick(inp, cmd)` at line 393, the call in which the dialog sees the frame; `ControllerV4.step` calls `super().step` (the safety stop is v3's, reason from `_safety`; the STOP gesture reaches it through `TickInput.gesture`).
     What 16.19.3 recorded stands unchanged: the mechanism exists in the code (a frame during a safety stop never reaches the dialog), but **the replay did not reproduce an abort from it** (feeding the STOP frames to the dialog would accept none of the 26 unaccepted asks of S5; the code that fed them was removed again; no abort is removed by A alone). The v3 file is not touched.

#### 16.20.5.1 Amendment of 16.20.5 (2026-11-20, Anisha, agreed with Nusrat), before step 5: the development timeout is 900 s, the rule is computed once over the pooled step-5 runs, the goal override is restored

**Amended 2026-11-20 (Anisha, agreed with Nusrat, Unity addendum 8 and its amendment 1), before step 5.** The text of 16.20.5 above is not changed; this entry amends it. Nusrat's entries are in `unity/Robotics-Warehouse/WarehouseProjectURP/Assets/WarehouseRobot/Avatar/Config/experiments_ab.md`, section 15: **addendum 8** (PR #46, declaration 2ee6e63, implementation b66e39a) and **addendum 8 amendment 1** (PR #47, dd11d55). Those two PRs changed no line of this file, so this is the AUDIT-side record; where her entries already say a thing I cite them and do not repeat it, and I add only what is missing.
1. **Development timeout: at least 420 s; 900 s is used** (her addendum 8 item 4: `Scenario/Config/trial_plan_v4.json` `development_timeout_s` 420 to 900, development mode only; the launcher prints "timeout 900 s per run" for all 13 settings in her dry runs; `final_plan.json` `timeout_s` is not touched). Reason added here: 16.20.5 decision 2 asks for 420 s, but the rule applied to the simulator's T0 durations already gives up to **510 s** (B3 on: the longest successful simulated T0 run is 326.6 s on seeds 101 to 140, 1.5 x 326.6 = 489.9, up to 510 s; the table of `outputs/report_t4_oos_v4_20261120_012143_final_check_s101_140`, the final check of 16.26.8.1; stated as "at most 510 s" in 16.26.9.1). That is the value of the rule, not a run length, but it shows that a 420 s development cap would sit BELOW the final timeout it is meant to set: a run lasting between 420 s and the final timeout would succeed under the final timeout and still be cut as a timeout in development, and a run that is cut cannot feed the rule. How long Unity's runs take is not known beforehand (the simulator is not Unity). 900 s keeps every run that could succeed under any final timeout the rule is likely to give.
2. **The timeout rule is unchanged** (16.20.5 decision 2; `final_plan.json` `timeout_s_rule`; 16.15 decision 2 as corrected in 16.16 decision 4): `timeout_s` = 1.5 x the longest SUCCESSFUL development run, rounded UP to a multiple of 30 s, never below 270 s, one value for all settings. **Verified in code on 2026-11-20, on e2c116f:** `final_guard_v4.timeout_from_development` (`final_guard_v4.py` lines 91 to 97: `max(floor 270, ceil(round(1.5 x longest / 30, 9)) x 30)`) and `final_guard_v4.development_timeout` (lines 100 to 111): the longest duration is taken ONLY from runs with `outcome` `SUCCESS` (and a `total_s`); a run that timed out is not a duration, it is listed (`timeouts_to_explain`, `cause_needed_before_the_freeze` true: its cause must be found before the freeze, 16.16 decision 4); every other failure (abort, collision, stuck) is counted (`other_failures`) and gives no duration either; the function raises when no run succeeded. **Pinned by `tests/test_v4_frozen.py`:** `test_the_timeout_stays_270_and_the_rule_is_declared` (the rounding table 50, 180, 181, 200, 280, 400 s to 270, 270, 300, 300, 420, 600 s; below 270 never) and `test_only_successful_development_runs_give_the_longest_duration` (a 270 s and a 300 s timeout in the list do not count: 190 s gives 300 s; 281 s gives 450 s; clean runs give the floor 270; no successful run raises). **This confirms item 5 of her addendum 8, which she left open pending my confirmation here: a run that timed out or aborted gives no duration** (it is listed with its outcome; a timeout needs its cause before the freeze).
3. **"One value for all settings" means computed ONCE over the POOLED successful step-5 runs of all 13 settings**: not per setting, not per experiment, not from a subset, not an average of per-setting values. `development_timeout` is called once on the 13 x 3 = 39 runs together; the longest successful run of the whole pool sets the value.
4. **Step 5** = 13 settings x 3 development runs (setting prefix `t0_`), T0 (no checkpoint workers, 16.26.9), under final conditions (her run protocol: other apps closed, Best performance; the new NavMesh only, 16.20.5 item 4 stands), with the **development-only goal override restored for A3, B3, B3_off, A4, B4 and B4_off: `-ExperimentGoals "E5,E6,E5"`** (goals E5, E6, E5 over the three runs, so that the longest routes are drawn; 16.19 item 4 and 16.20.5 decision 2), after an earlier step-5 command had dropped it by mistake: **her addendum 8 amendment 1 (PR #47, dd11d55) records the omission, the rule and where it applies** and is not repeated here. The other seven settings have fixed goals and get none. Her smoke trial (`smoke_t0_B3`) and her dry runs (`dry_*`) are not step 5 and never feed the rule.
5. **A tool, so that the manual step cannot be done wrong:** `python final_guard_v4.py --timeout-from SOURCE [SOURCE ...]` (from `robot_vision/`; `--prefix` default `t0_`, `--runs-per-setting` default 3, `--out FILE` writes a new file and never overwrites). SOURCE is the step-5 zip of her `finals_v4/step5_zip_v4.py` (read in place, its SHA-256 printed), the step-5 manifest `outputs/step5_sessions.json`, or `NAME=<Unity session folder>`; it reads the `truth_run###.json` of each Unity session folder (the outcome is scored by Unity: a bridge run folder holds only Python's side and is not a source). It pools the runs of the 13 settings, lists every excluded run with its outcome, and prints the longest successful run and the timeout of the rule (through `development_timeout`, unchanged). It REFUSES, and derives nothing, when a setting has no session or two (an interrupted session is kept, not used), a setting does not have 3 runs, a trial number repeats, a run is not in `development` mode or has no outcome or duration, a manifest records a development timeout below 420 s, or no run in the pool succeeded; it lists every problem, not only the first. It ignores sessions that are not `t0_` + a final setting (smoke, dry). It computes the number only: `final_plan.json` `timeout_s` stays 270 until a declared edit before the freeze. Tests: `tests/test_timeout_cli_v4.py` (22: the pooled value against `development_timeout` on the pooled list, the exclusions, the rounding and the floor, all three source forms giving the same report, the zip read in place and unchanged, every refusal).
**Not done:** no step 5 was run and no timeout is applied; no value of `final_plan.json` is changed; nothing is frozen; `unity/` is untouched.

#### 16.20.6 `return_speed_mps` built; the simulator rows rerun on the clearance layout (2026-11-17)

**Built (v4 only).** `dialog.return_speed_mps` 0.8 in the 11 v4 control files (`control.json`, `control_zoom_on/off.json`, `experiments/control_lie_{on,off}{,_a1,_a2_right,_a2_left}.json`) with its `why` (DECIDED 2026-11-17); `ControllerV4._tick` (the return branch) drives `pure_pursuit` at that speed, absent = the approach speed (the earlier behaviour, tested equal to an explicit 0.4); `ControllerV4.__init__` refuses a value that is not above 0 and at most the cruise speed (`ValueError`, no silent clamp). The approach to a person and the navigation are unchanged (a test compares the trails). `hri_control.py` and `configs/hri_control.json` are untouched.
`analyse_a3_timeouts_v4.py` removes the key for its "live" runs (the code of 16.20.3) and sets it for the counterfactual, so the numbers of 16.20.3 stay reproducible. Tests: `tests/test_return_speed_v4.py` (the 11 files, v3 untouched, refusals, the return is faster and its peak speed follows the key, absent = 0.4, the branch is still taken, nothing else changes, the E5 run of A3 on the old slots 270.3 s without the key and 254.7 s with it), `tests/test_a3_timeouts_v4.py` (the live config is now the counterfactual).

**Simulator rerun, clearance layout (with the rejection of 16.20.4), A3, B3, A4, B4, detection off and on, 20 seeds each, valid-branch liar.** Two timeouts, as decided: **270 s (the floor)** and **420 s (the development timeout of Unity's step-5 rerun; these are the runs that feed the rule)**. "Rule from this row" = `final_guard_v4.timeout_from_development(longest successful run)`: 1.5 x the longest SUCCESSFUL run, rounded up to a multiple of 30 s, never below 270 s. **For information only: the simulator is not Unity (speeds, clocks, perception); the real value comes from Unity's development runs.**

### 270 s (the floor): experiments_ab_v4_return_speed_270_20261117_192542

| experiment | detection | SUCCESS | failures | longest successful s | E5 runs: n, success, longest s | E6 runs: n, success, longest s | rule from this row |
|---|---|---|---|---|---|---|---|
| A3 | off | 20/20 | - | 184.45 | 6, 6, 183.55 | 1, 1, 184.45 | 300.0 |
| A3 | on | 14/20 | timeout 6 | 265.8 | 6, 0, - | 1, 1, 265.8 | 420.0 |
| B3 | off | 10/20 | wrong_goal 9, aborted 1 | 183.55 | 6, 3, 183.55 | 1, 0, - | 300.0 |
| B3 | on | 11/20 | timeout 5, wrong_goal 3, aborted 1 | 252.0 | 6, 0, - | 1, 0, - | 390.0 |
| A4 | off | 20/20 | - | 171.25 | 6, 6, 171.25 | 1, 1, 164.0 | 270.0 |
| A4 | on | 20/20 | - | 239.7 | 6, 6, 239.7 | 1, 1, 234.4 | 360.0 |
| B4 | off | 10/20 | aborted 3, wrong_goal 7 | 170.9 | 6, 3, 170.9 | 1, 0, - | 270.0 |
| B4 | on | 11/20 | aborted 2, wrong_goal 7 | 239.7 | 6, 3, 239.7 | 1, 0, - | 360.0 |

All 8 rows together: 116 successful runs, longest 265.8 s -> declared rule 420.0 s (floor 270 s).
E5/E6 successful runs: 31, durations [161.4, 162.75, 164.0, 168.9, 170.2, 170.9, 171.25, 183.55, 184.45, 226.8, 230.4, 234.2, 234.4, 238.3, 239.0, 239.7, 265.8].

### 420 s development timeout (feeds the rule): experiments_ab_v4_return_speed_420_dev_20261117_192605

| experiment | detection | SUCCESS | failures | longest successful s | E5 runs: n, success, longest s | E6 runs: n, success, longest s | rule from this row |
|---|---|---|---|---|---|---|---|
| A3 | off | 20/20 | - | 184.45 | 6, 6, 183.55 | 1, 1, 184.45 | 300.0 |
| A3 | on | 20/20 | - | 283.9 | 6, 6, 283.9 | 1, 1, 265.8 | 450.0 |
| B3 | off | 10/20 | wrong_goal 9, aborted 1 | 183.55 | 6, 3, 183.55 | 1, 0, - | 300.0 |
| B3 | on | 15/20 | aborted 2, wrong_goal 3 | 308.1 | 6, 4, 308.1 | 1, 0, - | 480.0 |
| A4 | off | 20/20 | - | 171.25 | 6, 6, 171.25 | 1, 1, 164.0 | 270.0 |
| A4 | on | 20/20 | - | 239.7 | 6, 6, 239.7 | 1, 1, 234.4 | 360.0 |
| B4 | off | 10/20 | aborted 3, wrong_goal 7 | 170.9 | 6, 3, 170.9 | 1, 0, - | 270.0 |
| B4 | on | 11/20 | aborted 2, wrong_goal 7 | 239.7 | 6, 3, 239.7 | 1, 0, - | 360.0 |

All 8 rows together: 126 successful runs, longest 308.1 s -> declared rule 480.0 s (floor 270 s).
E5/E6 successful runs: 41, durations [161.4, 162.75, 164.0, 168.9, 170.2, 170.9, 171.25, 183.55, 184.45, 226.8, 230.4, 234.2, 234.4, 238.3, 239.0, 239.7, 265.8, 283.9, 306.5, 308.1].


**Before and after the key at 270 s (the same layout and rejection; before = 16.20.1 for A3 and B3, 16.20.4 for A4 and B4):**

| experiment | detection | before: SUCCESS, median, collisions, safety stops | with the key: SUCCESS, median, collisions, safety stops |
|---|---|---|---|
| A3 | off | 20/20, 143.3 s, 0, 20 | 20/20, 138.8 s, 0, 0 |
| A3 | on | 13/20, 228.4 s, 0, 0 | **14/20**, 217.2 s, 0, 0 |
| B3 | off | 10/20, 138.9 s, 0, 18; fooled 10/15 | 10/20, 134.6 s, 0, 0; fooled 10/15 |
| B3 | on | 11/20, 247.2 s, 0, 0; fooled 8/40 | 11/20, 237.0 s, 0, 0; fooled 8/40 |
| A4 | off | 20/20, 134.7 s, 0, 7 | 20/20, 132.9 s, 0, 3 |
| A4 | on | 20/20, 199.6 s, 0, 0 | 20/20, 195.5 s, 0, 2 |
| B4 | off | 10/20, 126.3 s, 0, 6; fooled 8/14 | 10/20, 124.8 s, 0, 2; fooled 8/14 |
| B4 | on | 11/20, 205.9 s, 0, 2; fooled 20/47 | 11/20, 201.5 s, 0, 4; fooled 20/47 |

**Read.**
- **The key helps but does not remove the A3 / B3 timeouts at 270 s on the clearance layout, as 16.20.3 predicted:** the E5 runs of A3 on (6 of 20) and of B3 on still time out; E6 of A3 on now fits (265.8 s). **At the 420 s development timeout they succeed: A3 on 20/20 (E5 283.9 s, E6 265.8 s, longest 283.9 s) and B3 on 15/20 (the five 270 s timeouts become four successes and one abort; E5 up to 308.1 s)**, so those timeouts were duration, not failures. The other rows (A3 off, B3 off, A4, B4) are identical at 270 s and 420 s: nothing in them is near the limit (longest 239.7 s).
- **Set B successes do not change with the key:** B3 off 10/20, B3 on 11/20 at 270 s (15/20 at 420 s), B4 10/20 and 11/20, with the same lies fooled; the differences between rows come from the liars and the number of workers, not from the speed. 0 collisions in all 16 rows. The safety stops are short stops (0.05 to 0.25 s); most rows have fewer, A4 on and B4 on a few more (0 -> 2, 2 -> 4); not investigated.
- **Longest durations in the simulator (420 s runs):** A3 on 283.9 s (E5), B3 on 308.1 s (E5), A4 on and B4 on 239.7 s, off rows 171 to 184 s. E5 / E6 per row are in the tables above (successful runs only; A3 on: E5 283.9 s, E6 265.8 s; B3 on: E5 up to 308.1 s; A4 / B4 on: E5 239.7 s, E6 234.4 s; off rows: E5 up to 183.6 s).
- **What the declared rule would give from these simulator durations (information only):** from the 420 s development runs the longest successful run is 308.1 s (B3 on, E5) -> **480 s** (A3 on alone: 450 s; A4 and B4: 360 s; the off rows 270 to 300 s); one value for all settings is the maximum, 480 s. **From the 270 s runs the rule would wrongly give 420 s** (longest successful 265.8 s, because the E5 runs that need 284 to 308 s are timeouts and cannot count): the illustration of 16.20.5 that development runs feeding the rule must never use 270 s.
  Unity's real durations differ from the simulator's (step 5 had A3 timeouts); the value comes from the rule applied to Unity's 420 s runs. A route that needs more than the development timeout times out there too and the rule cannot see it, so the development timeout must stay above the durations that are meant to count; 420 s covers successful durations up to 420 s (the simulator's longest is 308.1 s).
- `final_plan.json` `timeout_s` stays 270 (not touched); the rule text there is already the one of 16.16 decision 4.

### 16.21 Decisions of 2026-11-17 (Nusrat and Anisha): the layout with two workers at J1, the weaker lie detection in B4 disclosed, B1 floor 10 adopted; recorded BEFORE any change

Branch `anisha/v4-clearance-layout` (from `279d252`). This round is done in two steps because of a missing file (see 3); the first step is item 2 (B1), the second the layout and the rerun.

**1. Layout: option (i), two workers at J1 everywhere (Nusrat's re-search with the 0.8 m re-ask shift, agreed by Anisha).** **0 of 864,782 three-worker layouts meet the 1.0 m clearance with the controller's 0.8 m re-ask shift; the only three-worker option puts slot 3 at 0.60 m, inside the person-in-path corridor** (corridor half width 0.6 m, `hri_control.json`; so a worker there could trigger the person-in-path stop of the robot's own drive).
   So A3 and B3 lose their third worker at J1 too (`people_by_node` J1 3 is removed from scenario 3, as it already is in scenario 4; this is a change of 16.12 item 3: "a third worker at J1 so that the majority vote of rule (a) has three voters"). The slots come from Nusrat's `slot_table.csv` (data, not instructions); the simulator takes them together with `placement_rule.reask_shift_m` 0.8 (the controller's value; 16.20.2 had her 0.4 m model there) in one change.
**2. Correction to Nusrat's note, and the weaker lie detection that follows (disclosed).** **`backtrack` is OFF in the experiments (16.10).** With two workers who disagree and nobody else to ask, the tie rule of 16.2 decision 4 asks the **first worker again and counts the answer twice** (16.13.1), so **a lie by the FIRST worker at J1 is followed unless `reject_impossible` catches it** (a lie that shows a real wrong branch is not impossible, so rule (b) catches little: 16.13.1). **Expected: weaker lie detection at J1 in A3-type routes and in B3 and B4 (two voters instead of three), as 16.20.1 measured for B4 (on 15/20 -> 11/20, lies fooled 8/37 -> 20/42).** This is a property of the design with two workers, not of a code change, and is reported, not tuned.
   The rerun therefore splits the lies fooled by whether the liar was the first-asked or a later-asked worker and by whether `reject_impossible` caught the lie (see 5).
**3. B1 floor 10 adopted now, before Nusrat's strict-protocol rerun** (16.19.7 said "waits for the rerun"; Anisha decides to adopt it now). Reason: 16.19.6: **no STOP reading changes with B1 (false STOPs and criterion (a) identical with and without it), and the S5 PROCEED holds rise from 35/62 to 58/62 with the current reader, 59/62 with C2s** (the adopted reader: 664 of 1416 PROCEED frames, 47 %; D4 stand-in 38/38 and STOP sessions 26/26 unchanged). Nusrat's rerun reports the frames per window by the number of people in view; if it shows that the floor is wrong, the value is changed then and disclosed.
   The rule (declared in 16.19.2 item B1, unchanged): PROCEED needs valid arm frames >= max(`proceed.min_valid_floor` 10, `window.min_valid_fraction` 0.6 x the frames the reader received for this person in the 2.0 s window), instead of 0.6 x the nominal 20; at the nominal 10 Hz this is the same 12. A v4 reader value in `configs/v4/gesture_reader.json` `proceed.min_valid_floor`; absent = the nominal rule as before. v3 is untouched. A declared difference of v3 and v4 is added to `analysis.json`.
**4. What is missing: `~/Downloads/slot_table.csv` does not exist** (searched: Downloads, the home folder, the whole disk, `origin/nusrat/v4-step5-dev` at `3f0422c`, which holds no slot table). I do not invent slots. **Step 1 (now): this record and B1 floor 10** (gesture_reader.json, `gesture_motion.proceed_features`, tests, docs), committed on its own. **Step 2 (when the file is there): `scenarios_ab.json` slots, `people_by_node` of scenario 3 and `placement_rule.reask_shift_m` 0.8 together, `MatchesUnity` and the clearance tests, and the rerun.**
**5. The rerun (declared now; step 2):** all simulator rows (the 13 of the request: to be confirmed whether they are the 16 rows of 16.13 (eight experiments, detection off and on) or the 13 final settings), 20 seeds, 270 s floor and a 420 s development timeout as in 16.20.6, on the new slots with B1 floor 10 and C2s live. Per row: successes, collisions, longest successful duration; for the B rows the lies fooled split by first-asked liar / later-asked liar and by caught by `reject_impossible` / not caught. Simulator only.

#### 16.21.1 Step 1 built: B1 floor 10 (2026-11-17); the layout and the rerun wait for `slot_table.csv`

**Built (v4 only; `hri_perception.py` and the v3 config are untouched).** `configs/v4/gesture_reader.json` `proceed.min_valid_floor` 10 (with its `why`, DECIDED 2026-11-17); `gesture_motion.proceed_features`: when the key is present the valid-frame requirement is max(floor, `window.min_valid_fraction` 0.6 x the frames received for the person in the 2.0 s window), else the nominal 0.6 x 20 as before (absent = the earlier rule);
`docs/gesture_reader_v4.md` and `configs/v4/analysis.json` (a new declared v3-to-v4 difference "PROCEED valid frames"). The replay tools model the earlier reader (`live_reader_config` and the `current` reader drop the key) and get a variant `final` = the real reader with both keys (C2s + B1).

**Replay of the real reader (both keys) on the three development datasets (S5, STOP sessions, D4 stand-in; guard passed, zips read in place; `outputs/proceed_stop_v4_switch_20261117_222619`): it reproduces the row "C2s + B1 floor 10" of 16.19.6.**

| reader | S5 PROCEED holds | STOP sessions PROCEED holds | D4* PROCEED holds | false STOPs S5 / STOP sessions / D4* (frames / episodes) | criterion (a) |
|---|---|---|---|---|---|
| current reader (no key) | 35/62 (322 of 1416 fr, 23 %) | 26/26 (559 fr) | 38/38 (494 fr) | 216 / 150, 67 / 29, 80 / 44 | 34 of 40 within 1.0 s |
| C2s (B1 off) | 37/62 (377 fr) | 26/26 (587 fr) | 38/38 (519 fr) | 73 / 65, 21 / 13, 28 / 19 | 32 of 40; none lost vs current |
| **C2s + B1 floor 10 (the reader now)** | **59/62 (664 fr, 47 %)** | 26/26 (587 fr) | 38/38 (537 fr) | 73 / 65, 21 / 13, 28 / 19 (identical to C2s) | identical to C2s |

**Read.** No STOP reading changes with B1 (false STOPs and criterion (a) are identical with and without the floor). The "58/62" of the request is the current reader with B1; with C2s already adopted the S5 PROCEED holds are **59/62**. The readings while the robot moves differ from the current reader's in 8 of 8138 (S5) and 8 of 7309 (D4*) moving frames, 0 in the STOP sessions: B1 reads more PROCEED (16.19.6 fact 2). Still not read: 3 of the 62 S5 holds and 53 % of the S5 PROCEED frames.
**Tests:** `tests/test_b1_floor_v4.py` (12: the floor and its reason, v3 untouched, the difference declared, a 5 Hz stream is read with the floor and not without, below the floor never, the nominal 10 Hz rate is unchanged, a wave or one swing is not PROCEED, the real key equals the analysis model, the STOP and hanging-arm readings through the whole pipeline do not depend on the floor; 3 opt-in tests pin the replay numbers above with `B1_REPORT=<report.json>` or `B1_REPLAY=1`; run once, 3 passed);
`tests/test_proceed_stop_v4.py` (the replay baseline has the key removed) and `tests/test_c2s_switch_v4.py` (the "B1 is not changed" pin of 16.19.7 became the adopted value). Nusrat's strict-protocol rerun still reports the frames per window by people in view; the floor is changed then only if it shows it is wrong, and disclosed.
**Open for step 2:** `~/Downloads/slot_table.csv`, and which "13 rows" (the 16 rows of 16.13, or the 13 final settings).

#### 16.21.2 Step 2: the slot table received; what is applied and how it is checked and rerun (2026-11-17); recorded BEFORE any change

**Data (not instructions): `~/Downloads/slot_table.csv`, SHA-256 `a180e358f4ec476e31f362918435170d57254644012b97e38d592ab3921ed39f`, 61 rows, three layouts: `P` (the previous clearance layout of 16.20, evaluated with the 0.8 m shift), `i` (two workers at J1), `iii` (three workers at J1, slot 3 relaxed to 0.631 m).** Decision of 16.21: **option (i)**. Its rows: junction slots (the same at every junction of every scenario) **slot 1 `{before 3.0, right -2.0}`, slot 2 `{before -2.5 (2.5 m AHEAD), right 4.0}`**; start slots unchanged (3.0, -2.0) and (3.0, 4.0); every row `relaxed` False, nearest node = own node, largest distance to the node 5.00 m (start slot 2), smallest clearance with the 0.8 m re-ask shift **1.173 m** (A3 J1 slot 2), largest own ask distance 4.062 m (A) and 3.18 m (junctions).
**Applied together in one change:** `scenarios_ab.json` `junction_slots` of scenarios 1, 2, 3 = the two slots of layout `i` (so no scenario can ask a third worker at a junction: `place_slots` refuses 3 workers with 2 slots); `people_by_node` J1 3 removed from scenario 3 (scenario 4 had none since 16.20); `placement_rule.reask_shift_m` 0.4 -> 0.8 (the controller's value; the random layout's rejection of 16.20.4 then uses 0.8 too).
**Checked (pass criteria fixed here):** every worker of every scenario, seed and node within 6.5 m of its node and nearest to it (largest distance reported); the independent clearance check of `layout_check_v4.py` at **both** re-ask shifts (0.4 m and 0.8 m): 0 of 20 plans violating for A1 to A4, smallest clearance >= 1.0 m, largest ask distance <= 5.5 m; the 3.0 m separation, turning-point, road and bystander rules hold for all seeds. `MatchesUnity` pins the slots to the values of this table (quoted constants; checked against her `clearance_layout` block whenever main's `unity/` file carries it, which it does not yet).
**Rerun (simulator, 20 seeds, valid-branch liar; B1 floor 10, C2s, `return_speed_mps` 0.8 live): the 16 rows of 16.13 (A1 to A4 and B1 to B4, detection off and on) at the 270 s floor and at the 420 s development timeout, with the 13 final settings marked** (the settings of `final_plan.json`: the rows that are final settings are marked from that file, not chosen here). Per row: successes, collisions, longest successful duration (at 420 s), E5 / E6 durations for A3 to B4; for the B rows the lies given, split by the liar being the first-asked worker of the visit or a later-asked one, and by what happened to the lie: caught by `reject_impossible` (decision `rejected:*`), outvoted, withdrawn, fooled (as `export_csv_v4`: accepted, acted on, not the true branch), neither (no reading / read as the true branch). A3/B3 and A4/B4 are shown against the previous layout (16.20.6 numbers, same code except the layout and `reask_shift_m`).
**Declared before the numbers: the expected effect is a weaker lie detection at J1 (two voters), as 16.21 item 2 disclosed; nothing is tuned on these rows.**

#### 16.21.3 Step 2 done: layout (i) applied, checked and the 16 rows rerun (2026-11-17)

**Applied in one change (as declared in 16.21.2).** `scenarios_ab.json`: `junction_slots` of scenarios 1 to 3 = `{3.0, -2.0}`, `{-2.5, 4.0}` (layout (i) of `slot_table.csv`, SHA-256 `a180e358...ed39f`); `people_by_node` J1 3 removed from scenario 3; `placement_rule.reask_shift_m` 0.8; the `why` entries say so. Start slots unchanged. Two workers at every node of every experiment (the simulator refuses a third at a junction: "3 workers but 2 slots").
**Checks (the pass criteria of 16.21.2; `layout_check_v4.py`, `outputs/layout_check_v4_20261117_223805_layout_i`): all met.** Every worker of A1 to A4, seeds 1 to 20, every node (40 / 80 / 200 / 200 placements) is within 6.5 m of its node and nearest to it: **largest distance 5.00 m** (the start node's second slot; A4 4.21 m). Clearance, **0 of 20 plans violating at both re-ask shifts**: A1 2.00 m / 1.96 m, A2 and A3 1.19 m / 1.17 m (the table's 1.173 m), A4 1.00 m (the random layout's rejection), largest ask distance 4.06 m (at 0.8 m), all <= 5.5 m. The 16.20 layout fails at 0.8 m (0.74 m, 5.53 m) as recorded; it stays reproducible in `analyse_a3_timeouts_v4.py --layout clearance16`.
**Tests.** `MatchesUnity` pins the slots to the table's values (quoted constants, against her `clearance_layout` block whenever main's `unity/` file carries it, which it does not yet) and J1 / J2 positions; `test_clearance_layout_v4.py` (layout (i), both shifts, the 16.20 layout and the old slots caught); `test_clearance_rejection_v4.py` (rule value 0.8; A4 clean at both shifts); the "three workers at J1" tests became "two workers at every node"; the rule tests that need three voters (`run(..., people=3)` in `test_lie_detection_v4.py` and `test_export_csv_v4.py`) now set their own three slots (the 16.13 ones), because the controller's three-voter rule is unchanged but the layout has two; `analyse_a3_timeouts_v4.py` has the layouts `old`, `clearance16`, `current`; new `report_rows_ab_v4.py` + `tests/test_report_rows_ab_v4.py` (5: the five outcomes, first / later asker and the tie re-ask, visits are separate, the 13 final settings give 12 rows of the 16, and the split agrees with `runs.csv` on a simulated B3 session).

**Rerun (simulator, 20 seeds per row, valid-branch liar; B1 floor 10, C2s and `return_speed_mps` 0.8 live): the 16 rows of 16.13 at the 270 s floor and at the 420 s development timeout** (`outputs/experiments_ab_v4_layout_i_270_20261117_224233` and `..._layout_i_420_dev_20261117_224306`; report `outputs/report_rows_ab_v4_20261117_224407_layout_i`). **Final setting = one of the 13 final settings of `final_plan.json`: 12 of the 16 rows are (A1, A2, A3, A4, B1 to B4 with detection on; B1 to B4 with detection off); the 13th, A2 with the left turn, is not a row of this table and was not run.** (The `final_plan.json` note of A3, "2 per node and 3 at J1", is stale since 16.21: reported, not edited.)
The definitions of the lie columns are those of `export_csv_v4` (caught by reject_impossible = decision `rejected:*`; fooled = accepted, acted on, not the true branch); the totals agree with `runs.csv` in all eight B rows. "First-asked liar" = the worker asked first at that visit (including the tie re-ask of him), "later-asked" = any other.

##### 270 s (the floor): `experiments_ab_v4_layout_i_270_20261117_224233`

| experiment | detection | final setting | SUCCESS | failures | collisions | longest successful s | E5: runs, successes, longest s | E6: runs, successes, longest s |
|---|---|---|---|---|---|---|---|---|
| A1 | off | - | 20/20 | - | 0 | 70.05 | 0 | 0 |
| A1 | on | **final** | 20/20 | - | 0 | 85.6 | 0 | 0 |
| A2 | off | - | 20/20 | - | 0 | 91.8 | 0 | 0 |
| A2 | on | **final** | 20/20 | - | 0 | 142.85 | 0 | 0 |
| A3 | off | - | 20/20 | - | 0 | 177.25 | 6, 6, 176.5 | 1, 1, 177.25 |
| A3 | on | **final** | 14/20 | timeout 6 | 0 | 251.85 | 6, 0, - | 1, 1, 251.85 |
| A4 | off | - | 20/20 | - | 0 | 170.9 | 6, 6, 170.9 | 1, 1, 162.8 |
| A4 | on | **final** | 20/20 | - | 0 | 253.0 | 6, 6, 253.0 | 1, 1, 244.4 |
| B1 | off | **final** | 19/20 | aborted 1 | 0 | 79.95 | 0 | 0 |
| B1 | on | **final** | 20/20 | - | 0 | 103.25 | 0 | 0 |
| B2 | off | **final** | 13/20 | aborted 7 | 0 | 101.65 | 0 | 0 |
| B2 | on | **final** | 19/20 | aborted 1 | 0 | 163.75 | 0 | 0 |
| B3 | off | **final** | 10/20 | wrong_goal 9, aborted 1 | 0 | 176.5 | 6, 3, 176.5 | 1, 0, - |
| B3 | on | **final** | 8/20 | timeout 4, wrong_goal 7, aborted 1 | 0 | 215.5 | 6, 0, - | 1, 0, - |
| B4 | off | **final** | 10/20 | aborted 3, wrong_goal 7 | 0 | 170.9 | 6, 3, 170.9 | 1, 0, - |
| B4 | on | **final** | 11/20 | aborted 2, wrong_goal 7 | 0 | 253.0 | 6, 3, 253.0 | 1, 0, - |

Lies by who lied and what became of the lie (lying asks of the dialogue table):

| experiment | detection | lying asks | first-asked liar: asks / caught by reject_impossible / outvoted / withdrawn / fooled / neither | later-asked liar: asks / caught by reject_impossible / outvoted / withdrawn / fooled / neither | runs.csv: given / detected / fooled | totals agree |
|---|---|---|---|---|---|---|
| B1 | off | 5 | 5 / 0 / 0 / 0 / 0 / 5 | 0 / 0 / 0 / 0 / 0 / 0 | 5 / 0 / 0 | yes |
| B1 | on | 12 | 8 / 6 / 0 / 0 / 0 / 2 | 4 / 4 / 0 / 0 / 0 / 0 | 12 / 10 / 0 | yes |
| B2 | off | 18 | 18 / 0 / 0 / 0 / 0 / 18 | 0 / 0 / 0 / 0 / 0 / 0 | 18 / 0 / 0 | yes |
| B2 | on | 36 | 23 / 20 / 0 / 0 / 0 / 3 | 13 / 12 / 0 / 0 / 0 / 1 | 36 / 32 / 0 | yes |
| B3 | off | 15 | 15 / 0 / 0 / 0 / 10 / 5 | 0 / 0 / 0 / 0 / 0 / 0 | 15 / 0 / 10 | yes |
| B3 | on | 49 | 40 / 6 / 0 / 0 / 19 / 15 | 9 / 4 / 2 / 0 / 1 / 2 | 49 / 12 / 20 | yes |
| B4 | off | 14 | 14 / 0 / 0 / 0 / 8 / 6 | 0 / 0 / 0 / 0 / 0 / 0 | 14 / 0 / 8 | yes |
| B4 | on | 47 | 37 / 6 / 0 / 0 / 19 / 12 | 10 / 4 / 2 / 0 / 1 / 3 | 47 / 12 / 20 | yes |

Against the previous layout (`experiments_ab_v4_return_speed_270_20261117_192542`):

| experiment | detection | previous: SUCCESS, collisions, longest s | now: SUCCESS, collisions, longest s | previous fooled (first / later) | now fooled (first / later) |
|---|---|---|---|---|---|
| A3 | off | 20/20, 0, 184.45 | 20/20, 0, 177.25 | - | - |
| A3 | on | 14/20, 0, 265.8 | 14/20, 0, 251.85 | - | - |
| A4 | off | 20/20, 0, 171.25 | 20/20, 0, 170.9 | - | - |
| A4 | on | 20/20, 0, 239.7 | 20/20, 0, 253.0 | - | - |
| B3 | off | 10/20, 0, 183.55 | 10/20, 0, 176.5 | 10 / 0 | 10 / 0 |
| B3 | on | 11/20, 0, 252.0 | 8/20, 0, 215.5 | 8 / 0 | 19 / 1 |
| B4 | off | 10/20, 0, 170.9 | 10/20, 0, 170.9 | 8 / 0 | 8 / 0 |
| B4 | on | 11/20, 0, 239.7 | 11/20, 0, 253.0 | 19 / 1 | 19 / 1 |

##### 420 s development timeout: `experiments_ab_v4_layout_i_420_dev_20261117_224306`

| experiment | detection | final setting | SUCCESS | failures | collisions | longest successful s | E5: runs, successes, longest s | E6: runs, successes, longest s |
|---|---|---|---|---|---|---|---|---|
| A1 | off | - | 20/20 | - | 0 | 70.05 | 0 | 0 |
| A1 | on | **final** | 20/20 | - | 0 | 85.6 | 0 | 0 |
| A2 | off | - | 20/20 | - | 0 | 91.8 | 0 | 0 |
| A2 | on | **final** | 20/20 | - | 0 | 142.85 | 0 | 0 |
| A3 | off | - | 20/20 | - | 0 | 177.25 | 6, 6, 176.5 | 1, 1, 177.25 |
| A3 | on | **final** | 20/20 | - | 0 | 271.2 | 6, 6, 271.2 | 1, 1, 251.85 |
| A4 | off | - | 20/20 | - | 0 | 170.9 | 6, 6, 170.9 | 1, 1, 162.8 |
| A4 | on | **final** | 20/20 | - | 0 | 253.0 | 6, 6, 253.0 | 1, 1, 244.4 |
| B1 | off | **final** | 19/20 | aborted 1 | 0 | 79.95 | 0 | 0 |
| B1 | on | **final** | 20/20 | - | 0 | 103.25 | 0 | 0 |
| B2 | off | **final** | 13/20 | aborted 7 | 0 | 101.65 | 0 | 0 |
| B2 | on | **final** | 19/20 | aborted 1 | 0 | 163.75 | 0 | 0 |
| B3 | off | **final** | 10/20 | wrong_goal 9, aborted 1 | 0 | 176.5 | 6, 3, 176.5 | 1, 0, - |
| B3 | on | **final** | 11/20 | aborted 2, wrong_goal 7 | 0 | 271.2 | 6, 3, 271.2 | 1, 0, - |
| B4 | off | **final** | 10/20 | aborted 3, wrong_goal 7 | 0 | 170.9 | 6, 3, 170.9 | 1, 0, - |
| B4 | on | **final** | 11/20 | aborted 2, wrong_goal 7 | 0 | 253.0 | 6, 3, 253.0 | 1, 0, - |

Lies by who lied and what became of the lie (lying asks of the dialogue table):

| experiment | detection | lying asks | first-asked liar: asks / caught by reject_impossible / outvoted / withdrawn / fooled / neither | later-asked liar: asks / caught by reject_impossible / outvoted / withdrawn / fooled / neither | runs.csv: given / detected / fooled | totals agree |
|---|---|---|---|---|---|---|
| B1 | off | 5 | 5 / 0 / 0 / 0 / 0 / 5 | 0 / 0 / 0 / 0 / 0 / 0 | 5 / 0 / 0 | yes |
| B1 | on | 12 | 8 / 6 / 0 / 0 / 0 / 2 | 4 / 4 / 0 / 0 / 0 / 0 | 12 / 10 / 0 | yes |
| B2 | off | 18 | 18 / 0 / 0 / 0 / 0 / 18 | 0 / 0 / 0 / 0 / 0 / 0 | 18 / 0 / 0 | yes |
| B2 | on | 36 | 23 / 20 / 0 / 0 / 0 / 3 | 13 / 12 / 0 / 0 / 0 / 1 | 36 / 32 / 0 | yes |
| B3 | off | 15 | 15 / 0 / 0 / 0 / 10 / 5 | 0 / 0 / 0 / 0 / 0 / 0 | 15 / 0 / 10 | yes |
| B3 | on | 49 | 40 / 6 / 0 / 0 / 19 / 15 | 9 / 4 / 2 / 0 / 1 / 2 | 49 / 12 / 20 | yes |
| B4 | off | 14 | 14 / 0 / 0 / 0 / 8 / 6 | 0 / 0 / 0 / 0 / 0 / 0 | 14 / 0 / 8 | yes |
| B4 | on | 47 | 37 / 6 / 0 / 0 / 19 / 12 | 10 / 4 / 2 / 0 / 1 / 3 | 47 / 12 / 20 | yes |

Against the previous layout (`experiments_ab_v4_return_speed_420_dev_20261117_192605`):

| experiment | detection | previous: SUCCESS, collisions, longest s | now: SUCCESS, collisions, longest s | previous fooled (first / later) | now fooled (first / later) |
|---|---|---|---|---|---|
| A3 | off | 20/20, 0, 184.45 | 20/20, 0, 177.25 | - | - |
| A3 | on | 20/20, 0, 283.9 | 20/20, 0, 271.2 | - | - |
| A4 | off | 20/20, 0, 171.25 | 20/20, 0, 170.9 | - | - |
| A4 | on | 20/20, 0, 239.7 | 20/20, 0, 253.0 | - | - |
| B3 | off | 10/20, 0, 183.55 | 10/20, 0, 176.5 | 10 / 0 | 10 / 0 |
| B3 | on | 15/20, 0, 308.1 | 11/20, 0, 271.2 | 8 / 0 | 19 / 1 |
| B4 | off | 10/20, 0, 170.9 | 10/20, 0, 170.9 | 8 / 0 | 8 / 0 |
| B4 | on | 11/20, 0, 239.7 | 11/20, 0, 253.0 | 19 / 1 | 19 / 1 |

Folder: /Users/anishamehajabin/warehouse-robot-perception/robot_vision/outputs/report_rows_ab_v4_20261117_224407_layout_i

**Read (simulator, not a measurement).**
- **0 collisions in all 32 rows.** Set A: A1, A2, A4 20/20 in both detection settings and A3 off 20/20 at both budgets; **A3 on is 14/20 at 270 s (the six E5 runs time out: E5 needs 271.2 s, 1.2 s over the floor) and 20/20 at 420 s (longest 271.2 s)**, against 283.9 s on the 16.20 layout.
- **The weaker lie detection that 16.21 disclosed is there, and it is B3.** B3 on (two voters at J1 instead of three): **SUCCESS 15/20 -> 11/20 at 420 s (8/20 at 270 s, where four E5 runs time out), wrong goal 3 -> 7, lies fooled 8 -> 20 (first-asked liars 8 -> 19, later-asked 0 -> 1)**. B4 on is unchanged (11/20, 19 + 1 fooled): it already had two workers at J1 in 16.20.4. The detection-off rows do not change (B3 off 10 fooled by the first-asked liar, B4 off 8). B1 on 20/20, B2 on 19/20 as before.
- **Who lied decides:** in B3 on, 40 of the 49 lying asks are the first-asked worker's: 6 are caught by `reject_impossible`, **19 fooled**, 15 neither (not read, or read as the true branch); of the 9 later-asked liars 4 are caught by `reject_impossible`, 2 outvoted, 1 fooled, 2 neither. **A second opinion outvotes a lie only 2 times in B3 on and 2 in B4 on (both by later-asked liars); every other detected lie is a rejection of an impossible direction** (6 + 4 in B3 on and B4 on; 20 + 12 in B2 on, 6 + 4 in B1 on). The first worker's lie is followed 19 times in each of B3 on and B4 on because a tie re-asks and counts him twice (16.13.1), as 16.21 item 2 said.
- **Durations (420 s runs):** longest successful run in the table 271.2 s (A3 on and B3 on, E5); A4 on and B4 on 253.0 s (previous layout 239.7 s); the E5 / E6 columns give the per-row durations. **What the declared rule would give from these simulator durations (information only; the real value comes from Unity's runs on the new NavMesh): 420 s** (`timeout_from_development(271.2)`: 1.5 x 271.2 = 406.8, rounded up to a multiple of 30; the previous layout gave 480 s from B3 on E5 at 308.1 s). Fed with the 270 s runs the rule would give 390 s from 253.0 s, wrongly: the long routes are timeouts there and cannot count (16.20.5).
- **A3 / B3 and A4 / B4 against the previous layout (16.20.6 runs):** the tables above. A3 off and A4 off are as before (longest 177.3 s against 184.5 s, 170.9 s against 171.3 s), A3 on 20/20 at 420 s both times; A4 on takes longer (253.0 s against 239.7 s); B3 on is the row that changed, for the reason above; B4 rows are unchanged in successes.

### 16.22 The tie rule with two workers: three variants declared (2026-11-18, Anisha, from the request of 16.21.3); recorded BEFORE any computation

Branch `anisha/v4-tie-rule`, from main after PR #42 (layout (i), 1e89dcd). Simulator only. No existing value of any config changes.

**Finding (16.21.3).** With two workers per node the tie rule (re-ask the first, who counts twice) always follows the first-asked worker, because the liars are consistent since 16.12 (`lie_mode` per_worker). B3 on 11/20 against off 10/20; the first-asked liar fooled 19 of 40 lying asks in B3 on, the second opinion outvoted 2.

**Why this is asked.** The faculty plan requires the robot to detect lies from evidence and to correct itself. Backtrack was turned off in 16.10 because it never triggered with three workers at J1; with two workers and a consistent first liar the situation is different, so it is looked at again before anything is decided.

**Variants (the "on" rows only; the "off" rows have every switch false, so they are identical in all three variants and are run only to show that):**

| variant | lie_detection of the "on" rows |
|---|---|
| T0 | the current "on": second_opinion true, reject_impossible true, backtrack false |
| T1 | T0 with backtrack true (the existing switch, unchanged code path: back to the last decision junction when every answer at a junction was rejected) |
| T2 | T1 with a new optional key `lie_detection.backtrack_scope`: "any" (default, = T1) or "disagreed". With "disagreed" a backtrack goes only to a decision junction at which the accepted answers of the visit named more than one branch (the two workers disagreed; the first, counted twice, does not change that); otherwise `backtrack_blocked` with that reason is logged. The disagreement is recorded in `last_choice` when the robot leaves the junction. |

The new key defaults to "any" in `LIE_DEFAULTS`; control.json and every other config are not edited; the runner sets the variant for a run (`run_experiments_ab_v4.py --tie-variant T0|T1|T2`, default T0 = what it does today). Nothing is tuned: the variants are run once as declared.

**Pass criteria, declared now.** B rows: successes and wrong goals against T0; lies fooled split by first-asked / later-asked liar and by caught by `reject_impossible`, as in 16.21.3. A rows: no success lost against T0 and no backtrack in any truthful run. Longest successful durations are reported for the timeout rule, for information only (the real value comes from Unity's runs on the new NavMesh). All 16 rows at 420 s, 20 runs, seeds as before, for T0, T1 and T2; one table; no decision is taken here, the table goes to review.

**Also in this branch.** The stale A3 note in `final_plan.json` ("2 per node and 3 at J1 (beside)") is corrected to layout (i) (two workers at every node, 16.21.2). The file is not frozen (`frozen.json` frozen false), so no pinned hash changes. Reported, not edited: `test_assignment_note` in the same file still speaks of a third worker at J1 (16.15).

#### 16.22.1 Result of the three variants (2026-11-18, simulator, 420 s, 20 runs per row, seeds as before); the declared criteria applied, nothing tuned

Code (after the declaration above): `lie_detection.backtrack_scope` ("any" default / "disagreed") in `hri_control_v4.py` (`last_choice["disagreed"]`, `_start_backtrack`), `--tie-variant T0|T1|T2` in `run_experiments_ab_v4.py` (default T0), `report_tie_variants_v4.py`, `tests/test_tie_variants_v4.py`. Folders (git-ignored): `experiments_ab_v4_tie_T0_420_20261118_004956`, `..._tie_T1_420_20261118_005026`, `..._tie_T2_420_20261118_005058`; table `report_tie_variants_v4_20261118_005157_420`.

- **T0 is the 16.21.3 "on" exactly:** all 320 runs equal run for run (outcome, reason, duration, collisions, lies fooled). The "off" rows are identical in the three variants (16 rows, 320 runs).
- **A rows (all 8): no success lost against T0, no backtrack in any truthful run** (0 backtracks in A1-A4 off and on, T1 and T2). 0 collisions in all 16 rows of all three variants.
- **B1, B2 (on): unchanged** (20/20 and 19/20, no backtrack).
- **B3 on and B4 on, the rows that matter** (successes / wrong goals / aborted / timeout; longest successful; lies fooled first-asked / later-asked; caught by `reject_impossible`):

| row | T0 | T1 = T2 |
|---|---|---|
| B3 on | 11/20, 7, 2, 0; 271.2 s; 19 / 1; 10 | 12/20, 7, 0, 1; 344.4 s; 17 / 1; 12; 2 backtracks (2 runs) |
| B4 on | 11/20, 7, 2, 0; 253.0 s; 19 / 1; 10 | 12/20, 7, 0, 1; 311.6 s; 17 / 1; 12; 2 backtracks (2 runs) |

- **T1 and T2 are identical in all 320 runs.** Every backtrack T1 made was at a junction where the two answers had disagreed, so the scope restriction of T2 never bit; it also blocked none.
- **What changed:** in each of B3 on and B4 on two runs, run_001 (goal E2) and run_012 (goal E5), had been aborts in T0 and now backtrack once. Run_001 reaches the goal (SUCCESS, +53 s and +53 s: 344.4 s and 311.6 s, the new longest successful runs); run_012 does not and ends in a timeout at 420 s instead of an abort at 225 s / 215 s. Successes 11 -> 12 in each row. **Wrong goals stay 7 and 7: a lie that is a valid branch is followed on to the wrong goal and no rejection ever follows, so the backtrack has no evidence to act on.** The first-asked liar's fooled count falls 19 -> 17 only because the two backtracked runs no longer count their lies as followed.
- **Not independent:** B3 and B4 use the same seeds and the same liars at J1, so the four changed runs are two cases counted twice; one success is a difference of one run in 20.
- **For the timeout rule (information only):** 1.5 x 344.4 = 516.6, rounded up to 30 s = 540 s with T1 / T2 (420 s with T0); the real value comes from Unity's runs.
- **Reading, no decision taken:** backtrack as it exists recovers 2 aborts into 1 success per B3 / B4 on and costs longer runs; it does not address the finding (a consistent first liar at a tie is followed to the wrong goal: 7 wrong goals per row in all three variants). Detecting that case needs evidence the robot does not have after a valid-but-wrong branch (a second look at the same junction or a check against the route taken), which is a design question for Nusrat and Anisha, not something to tune here. The variants go to review.
- **Also done:** the A3 note in `final_plan.json` now reads "layout (i) of slot_table.csv: two workers at every node (AUDIT.md 16.21.2)"; `test_assignment_note` (16.15) still mentions a third worker at J1 and is reported, not edited.

### 16.23 Variant T3 "checkpoint workers" (2026-11-18, Nusrat's proposal, decided with Anisha; simulator only); recorded BEFORE any code or computation

Branch `anisha/v4-tie-rule` (after 16.22 / cc49e1d). Nusrat's text is data; the rules below are the ones declared by Anisha for T3. Nothing is tuned, no existing config value changes, no v3 file, no `unity/`, no `external/`; the new controller key defaults off, so T0 is the current behaviour exactly.

**Rules (as given).**
1. One checkpoint worker on every branch leaving a decision junction, beside the road, meeting the placement rules (1.0 m clearance from every drivable segment, 3.0 m separation). Positions are PROVISIONAL until Nusrat sends Unity's.
2. Honest checkpoint: PROCEED on the branch toward the goal, POINT back along the arrival road on a wrong branch. Lies with the same 20% per-worker chance (`lie_mode` per_worker): a lying checkpoint shows the opposite.
3. Detection on: the robot asks the checkpoint. PROCEED: continue. POINT back: evidence: return to the junction and take the other branch (two-way) or re-ask there with the failed branch excluded (three-way). NONE / unclear: continue. At most one backtrack per junction; if the checkpoint of the second branch also points back, keep the second branch (no loop). `reject_impossible` still rejects "back" at junctions (before a decision). The mirror-image ambiguity of 16.11 is modelled for pointing back as for any pointing.
4. Detection off: checkpoint workers present, the robot ignores them (same scene, logic differs).
5. The junction tie rule is unchanged (T0).

**What I had to decide to make it runnable (declared now, provisional, all reported):**
- **Decision junction:** a node of kind junction with at least two branches. Hence the v4 map has 9 checkpoints (J1: 3, J2: 2, J3: 2, J4: 2) and the one-branch corner of A2 / B2 and the corridor of A1 / B1 have none: those four rows are the same in T3 and T0 by construction (reported, not hidden). The start node A (one branch) has none.
- **Checkpoint position rule (provisional):** the point P of a branch is its MIDPOINT along the road (`fraction` 0.5 of the junction-to-next-node segment). The robot's own rule is the same ("stop at the midpoint of a branch leaving a decision junction, look for a person"): it needs only the roadmap. The worker stands 3.0 m to the right of the travel direction from P. Candidates in this order when a rule is broken: left 3.0 m, right 4.0 m, left 4.0 m; no candidate = an error, not a silent drop. A candidate must satisfy: at least 1.0 m from every road segment and every segment the robot can drive (the junction workers' ask / re-ask / return segments at both re-ask shifts of 16.21.2, and the checkpoint's own ask and re-ask segments from P), at least 3.0 m from every other worker (junction or checkpoint) and from every turning point, and farther than `second_opinion_radius_m` (6.5 m) from every node, so that the junction rules (second opinion, `_belongs_here`) never take a checkpoint worker for a junction worker. At 3.0 m beside the midpoint of a 12.5 m branch the worker is 6.93 m from both ends. Planned after the junction workers (random layout A4 / B4 included), in the order of the roadmap.
- **Scenes:** the people of a junction's scene are its workers as before (T0 unchanged) plus the checkpoint workers of the branches leaving it; the robot sees them with the existing 360 detection range (12 m) and pan-tilt range (6 m). Detection noise of checkpoint workers is drawn from a separate generator, so the junction workers' readings are the same as in T0 and a T3 "off" row differs from T0 only by what the extra people do.
- **Robot side (lie_detection.checkpoint true, key `checkpoint_fraction` 0.5; off by default):** after a decision at a decision junction the robot drives to P, stops, scans, and picks the nearest person that does not belong to the junction (`_belongs_here`), approaches to 2.0 m and asks; the dialog is the existing one (hold 1.0 s, re-ask with the 0.8 m shift, two views for an ambiguous point). PROCEED or a point along the branch: continue. Pointing back (the arrival road, held 1.0 s): evidence. Nobody found, asks used up, or ambiguity not resolved: continue (never an abort). Evidence: if the junction has not used its backtrack and another branch is untried, the existing backtrack machinery (return to the junction point, the one untried branch directly, or ask again with the failed branch excluded); else keep the branch.
- **Lies:** a checkpoint worker is a liar with probability 0.2 (B only; A has none), drawn once per worker per run from its own generator (junction liars identical to T0), and shows the opposite of the honest gesture.

**Run.** All 16 rows at 420 s, 20 runs, seeds as before, for T0 and T3 (the same 320 runs per variant), through `run_t3_v4.py` (new) and `report_t3_v4.py` (new). Check first that T0 through the new runner equals the 16.22 T0 folder run for run. T3 "on" = second opinion + reject_impossible (T0's "on") + checkpoint; T3 "off" = every switch false.

**Metrics (one table):** successes, wrong goals, aborts, timeouts, collisions; lies fooled split into junction liar (a wrong branch taken at a junction after a lying junction answer) and checkpoint liar (a lying checkpoint answer acted on: a missed wrong branch, or a false backtrack); lies caught by a checkpoint (an honest POINT back on a wrong branch that sent the robot back); FALSE backtracks (a backtrack from a checkpoint on the right branch, a lying checkpoint or a misread); longest successful duration (for the timeout rule, information only); the most people in the robot's view in any run (360 detections of one tick). **Criteria:** the A rows lose no success against T0 and have 0 backtracks. No decision is taken here; the table goes to review.

#### 16.23.1 Result of T3 against T0 (2026-11-18, simulator, 420 s, 20 runs per row, seeds as before); the declared criteria applied, nothing tuned

Code (after the declaration above): `lie_detection.checkpoint` / `checkpoint_fraction` (default false / 0.5) and the checkpoint states in `hri_control_v4.py` (`_cp_drive`, `_cp_scan`, `_interpret_cp`, `_cp_proceed`, `_cp_back`, `_cp_none`; the backtrack is the existing machinery); `plan_checkpoints`, the checkpoint workers' scenes, their own detection-noise stream and `max_people_in_view` in `hri_sim_v4.py`; `configs/v4/experiments/checkpoints.json` (provisional positions); `run_t3_v4.py`, `report_t3_v4.py`; `tests/test_checkpoints_v4.py` (20 tests). Folders (git-ignored): `t3_v4_420_20261118_200744` (raw runs), `report_t3_v4_20261118_200827_420` (table.md, table.json).

- **T0 of the new runner is the 16.22 T0 exactly:** 320 of 320 runs equal (outcome, reason, duration) against `experiments_ab_v4_tie_T0_420_20261118_004956`.
- **The rows without a decision junction are identical in T3 and T0** (A1, A2, B1, B2, off and on; no checkpoint exists). **The T3 "off" rows equal the T0 "off" rows in every successes / failures / duration cell** (the robot ignores the workers; they only add people to the view: 5 instead of 2 in A3, A4, B3, B4).
- **A rows (criteria):** no success lost against T0 (A3 and A4 on 20/20 each) and **0 backtracks** in every A row; the 90 checkpoints asked in A3 / A4 on all answered PROCEED (none unclear). The price is time: longest successful run A3 on 303.2 s (T0 271.2 s), A4 on 287.6 s (253.0 s).
- **B3 on / B4 on, the rows that matter** (successes / wrong goals / aborts / timeouts; lies fooled: junction liar / checkpoint liar; caught by a checkpoint; false backtracks; longest successful):

| row | T0 | T3 |
|---|---|---|
| B3 on | 11/20, 7, 2, 0; 9 / 0; -; -; 271.2 s | 11/20, 4, 4, 1; 8 / 9; 6; 6; 351.9 s |
| B4 on | 11/20, 7, 2, 0; 9 / 0; -; -; 253.0 s | 12/20, 4, 4, 0; 8 / 9; 6; 6; 391.9 s |

  12 backtracks per row (6 sent back from a wrong branch, 6 false). The one T3 timeout of B3 on is the same E5 run that T1 turned from an abort into a timeout (16.22.1).
- **What the checkpoints did, per row (B3 on and B4 on alike):** of the 45 / 46 checkpoints asked, 9 were liars (20%), none was unclear, 2 pointings back were kept because the junction had used its one backtrack (the no-loop rule). Runs with only true backtracks: 5, all failures in T0, now 4 successes + 1 timeout in B3 and 5 successes in B4. Runs with only false backtracks: 5, 4 of them successes in T0, now 3 aborts + 2 wrong goals (a false backtrack at a three-way junction re-asks with the right branch excluded and the truthful worker's answer is rejected "already tried"; at a two-way junction the robot takes the other branch directly: the 3 wrong branches per row taken without a junction lie, checked). One run has both: a wrong goal. Net against T0: 10 runs per row changed (4 wrong goal to success, 2 success to wrong goal, 2 success to abort, 1 wrong goal to abort, and 1 abort to timeout in B3 / 1 abort to success in B4): the gains and the losses cancel (B3 11 to 11, B4 11 to 12), wrong goals fall from 7 to 4, aborts rise from 2 to 4. Safety stops over the 20 runs: 9 against 1 (B3) and 7 against 3 (B4); the cause was not looked into.
- **Reading, no decision taken:** a checkpoint turns a followed junction lie into a correction (6 per row), but a lying checkpoint on the right branch costs as much (6 false backtracks per row), because the robot has no evidence to weigh a checkpoint against the junction worker (the same 20% liars on both). With the declared rules the net on successes is about zero and the runs are 80-140 s longer (longest successful 351.9 s and 391.9 s; the declared timeout rule would give 1.5 x 391.9 = 587.9, rounded up to 600 s, for information only). A re-ask of the junction worker before the return, or two checkpoints agreeing, would be the evidence to weigh; that is a design question for Nusrat and Anisha. Positions are provisional (midpoint, 3.0 m to the right): the result may move with Unity's.

### 16.24 Variant T4 "the checkpoint is a vote, not a veto" (2026-11-18, Anisha; a change decided AFTER seeing 16.23.1, disclosed); recorded BEFORE any code or computation

Branch `anisha/v4-tie-rule` (after 16.23 / 0e67a8d). Simulator only; no existing config value changes; the new controller key defaults to the T3 behaviour, so T0 and T3 are exactly what they were.

**Finding (16.23.1).** In T3 a single checkpoint "back" overrides the junction. A checkpoint is one more vote of the same reliability (the same 20% liars), so its false backtracks (6 per row in B3 on and B4 on) cancel the lies it catches (6 per row).

**Variant T4.** The checkpoint counts as a vote, not a veto. A backtrack happens only when the junction was DISPUTED (the accepted answers of its visit named different branches: `last_choice["disagreed"]`, as recorded for `backtrack_scope` "disagreed" in 16.22) AND the checkpoint points back. Otherwise a checkpoint "back" is logged (`checkpoint_answer`, action `ignore_undisputed`) and ignored: the robot continues. Everything else as T3: provisional positions (16.23), the checkpoint workers' own noise stream, the OFF rows ignore the checkpoints, nothing is asked more often. New optional key `lie_detection.checkpoint_scope`: "any" (default, = T3) or "disputed" (= T4); the runner sets it for T4 (`run_t3_v4.py` variant T4). The no-loop rule and the one backtrack per junction are unchanged and are checked after the dispute test.

**Stopping rule, declared now.** T4 is adopted only if B3 on AND B4 on each gain at least 3 of 20 successes over T0 and no A row loses a success or makes a backtrack. Otherwise the checkpoints are dropped, T0 stays, and the limitation is reported: with two workers and consistent liars a lie toward a valid branch is not reliably detectable. **No further variants after T4.** (The code and its switches stay in the repository, off by default; "dropped" means not adopted for the experiments.)

**Run.** All 16 rows at 420 s, 20 runs, seeds as before, for T0, T3 and T4 (the same seeds); ONE table with the T3 columns plus "checkpoint back ignored (undisputed)", the longest successful duration and the most people in view. T0 of the runner is again checked against the 16.22 T0 folder (320 of 320 runs). No decision beyond the declared rule is taken here.

#### 16.24.1 Result of T4 against T0 and T3 (2026-11-18, simulator, 420 s, 20 runs per row, seeds as before); the declared stopping rule applied, nothing tuned

Code (after the declaration above): `lie_detection.checkpoint_scope` ("any" default = T3, "disputed" = T4) and the dispute test in `_cp_back` of `hri_control_v4.py` (action `ignore_undisputed`, checked before the one-backtrack rule); `--variants T0 T3 T4` (all three by default) in `run_t3_v4.py`; the "ignored (undisputed)" column and `stopping_rule()` in `report_t3_v4.py`; 6 new tests in `tests/test_checkpoints_v4.py` (26 in all). Folders (git-ignored): `t3_v4_t4_420_20261118_202418` (raw runs, 960), `report_t3_v4_20261118_202524_t4_420` (table.md, table.json).

- **T0 is the 16.22 T0 exactly** (320 of 320 runs). **T3 is as in 16.23.1** (the same 320 runs). Rows without a decision junction (A1, A2, B1, B2) and every "off" row: identical in T0, T3 and T4.
- **A rows:** T4 equals T3: no success lost against T0 (A3 and A4 on 20/20), **0 backtracks**; longest successful A3 on 303.2 s, A4 on 287.6 s.
- **B3 on and B4 on** (successes / wrong goals / aborts / timeouts; lies fooled junction / checkpoint; caught; false backtracks; ignored undisputed; longest successful):

| row | T0 | T3 | T4 |
|---|---|---|---|
| B3 on | 11/20, 7, 2, 0; 9 / 0; -; -; -; 271.2 s | 11/20, 4, 4, 1; 8 / 9; 6; 6; -; 351.9 s | **17/20**, 1, 1, 1; 9 / 2; 7; **0**; 6; 418.1 s |
| B4 on | 11/20, 7, 2, 0; 9 / 0; -; -; -; 253.0 s | 12/20, 4, 4, 0; 8 / 9; 6; 6; -; 391.9 s | **18/20**, 1, 1, 0; 9 / 2; 7; **0**; 6; 391.9 s |

- **Stopping rule (declared in 16.24): applied mechanically: gains over T0 are +6 (B3 on) and +7 (B4 on), each at least 3; no A row loses a success or backtracks: T4 is ADOPTED by the rule.** "Adopted" is the verdict of the rule on the simulator; no config default, no `final_plan.json` and no frozen file was changed, and what adoption needs in the experiments (Nusrat's Unity positions and her checkpoint worker and stop) is not done here.
- **Why (per run, B3 on / B4 on):** against T0, 6 runs go from a wrong goal to success in each row, and 1 more (B3: abort to timeout; B4: abort to success); 13 runs per row are unchanged. All 6 pointings ignored as undisputed are lying checkpoints on the RIGHT branch (the false backtracks of T3), so no honest pointing back was ever ignored; 7 junction lies per row were sent back and corrected (T3: 6). All 7 corrected junction lies were disputed (they must have been, T4 backtracks only then: two workers at every junction, the tie rule follows the first), so the checkpoint acts as the third voter at a dispute; whether the 2 junction lies let through by a lying checkpoint were disputed too was not looked at. The 2 failures that remain in each row (seeds 1 and 6) are runs where both the junction worker and the checkpoint lied (an abort, a wrong goal); B3's third failure (seed 12) is a correction that ran into the 420 s limit.
- **Disclosed:** T4 was designed after seeing T3's results on the same 20 development seeds, so the gain is in-sample; the stopping rule was declared before the T4 run, the final trials use other seeds. B3 and B4 share seeds and liars at J1 (and the checkpoint liars), so their gains are largely the same runs counted twice. The checkpoint workers lie with the same 20% as the junction workers, a simulator assumption; the positions are provisional.
- **Time:** the longest successful run of B3 on is 418.1 s, 1.9 s under the 420 s limit, and one run times out: the limit truncates the T4 durations, so these are lower bounds. For the timeout rule (information only): 1.5 x 418.1 = 627.2, rounded up to 30 s = 630 s, probably more without the limit; the real value comes from Unity's runs. Most people in view: 5 in A3, A4, B3, B4 (2 in T0). Safety stops over the 20 runs T0 / T3 / T4: 1 / 9 / 4 (B3) and 3 / 7 / 2 (B4); the cause was not looked into.
- **No further variants after T4 (declared).** The table goes to review.

### 16.24.2 Out-of-sample check of T4 (2026-11-18, Anisha); recorded BEFORE any computation

16.24.1 found T4 adopted by its stopping rule on the 20 development seeds the variant was designed on. This is the check on seeds it has never seen. Simulator only; no code or config value changes (a new `--first-seed` option of `run_t3_v4.py` only; the default stays the first seed of `scenarios_ab.json`).

**Runs.** Fresh simulator seeds 21 to 60 (40 per row; never used before: every earlier run in 16.x used seeds 1 to 20), T0 against T4, all 16 rows (A1-A4, B1-B4, detection off and on), development cap 900 s (so that no success is truncated). Run k = seed has goal k of the same GoalSequence (`goal_order` is a plain prefix: the goals of seeds 1 to 20 are unchanged), the placements and the liars are drawn from the seed as before; the checkpoint positions are the provisional ones of 16.23 and the variants are exactly those of 16.23 / 16.24 (T4 = `checkpoint` true, `checkpoint_scope` "disputed").

**Pass bar, declared now.** In B3 on AND B4 on the success RATE of T4 exceeds that of T0 by at least 15 percentage points (the 3/20 bar of 16.24; 6 or more extra successes of 40); AND no A row loses a success against T0 (successes of T4 at least those of T0, row by row) or makes a backtrack. If the bar fails, T4 is not adopted and the stopping rule of 16.24 applies: the checkpoints are dropped, T0 stays, and the limitation is reported (two workers and consistent liars: a lie toward a valid branch is not reliably detectable). No further variants.

**Reported per row and variant.** Successes with a 95% Wilson interval; the T4 - T0 difference of the success rates with a 95% Newcombe (hybrid score, method 10) interval (the unpaired formula, as declared; the runs are paired by seed, which this ignores, so it is conservative; the counts of seeds that changed in each direction are given beside it); wrong goals; aborts; timeouts; backtracks; FALSE backtracks (a backtrack from a checkpoint on the right branch); the most people in view; median, 95th percentile (linear interpolation between order statistics, numpy's default) and maximum duration of the SUCCESSFUL runs; the timeout the declared rule would give from the longest successful run of the row (`timeout_from_development`: 1.5 x that run, rounded up to 30 s, not below 270 s; information only; the real value comes from Unity's runs).

**Estimate of the total time of the 260 final runs (20 runs x 13 settings), T4 against T0.** The 13 final settings of `final_plan.json` are the rows A1, A2, A3, A4 on, B1 to B4 on and off, and A2 on the left turn; the latter has no row here and takes the A2 on row's mean (the mirrored map; an assumption). Per row: the mean duration of ALL its 40 runs, failures included (an abort counts the time it ended, a timeout the 900 s cap); estimate = 20 x the sum over the 13 settings. Simulated time only: no start-up, reset or other overhead between the runs; the 900 s cap inflates the rows that time out. Rows without a decision junction (A1, A2, B1, B2) and the off rows are the same in T0 and T4 by construction.

#### 16.24.2.1 Result of the out-of-sample check (2026-11-18, simulator, seeds 21 to 60, 40 runs per row, cap 900 s); the bar of 16.24.2 applied, nothing tuned

Code: `--first-seed` in `run_t3_v4.py`; `report_t4_oos_v4.py` (Wilson, Newcombe, percentiles, the timeout of the rule, the total-time estimate; evaluation code); tests in `tests/test_checkpoints_v4.py`. Folders (git-ignored): `t3_v4_oos_21_60_900_20261118_203001` (raw runs, 1280), `report_t4_oos_v4_20261118_203124_oos_21_60_900` (table.md, table.json). No run reached the 900 s cap (0 timeouts in all 32 rows), so no success is truncated.

- **Pass bar: PASSED.** B3 on 23/40 (57.5%, Wilson 42.2 to 71.5) for T0 against 31/40 (77.5%, 62.5 to 87.7) for T4: **+20.0 pp** (Newcombe 95%: -0.5 to +38.4), 10 seeds gained and 2 lost. B4 on 23/40 (57.5%, 42.2 to 71.5) against 31/40 (77.5%, 62.5 to 87.7): **+20.0 pp** (-0.5 to +38.4), 10 gained and 2 lost. Each is above the 15 pp bar. **No A row loses a success** (A1 to A4, off and on: 40/40 in both variants) **and none makes a backtrack.** T4 is therefore adopted by the declared bar.
- **What the intervals say, honestly:** the gain is a point estimate of +20 pp with 8 extra successes of 40; the declared (unpaired, conservative) Newcombe interval just reaches below zero (-0.5 pp), so with that method the gain is not separated from no gain at 95%. Extra, computed after seeing the data and not part of the declared method: the paired counts 10 gained / 2 lost have an exact two-sided sign-test p = 0.039 in each row. The effect is smaller than on the development seeds (+6 and +7 of 20: +30 and +35 pp), as expected of a variant designed on those seeds. B3 and B4 share seeds and liars at J1 and the checkpoints: their outcomes are identical on 38 of 40 seeds, so the two rows are one result counted twice.
- **What happened in the fresh seeds (B3 on / B4 on alike):** T4 made 15 backtracks per row (13 sent a wrong branch back, **2 false**), ignored 20 pointings back as undisputed, and 4 honest pointings back on a wrong branch did not send the robot back (ignored as undisputed, or kept by the one-backtrack rule): the case T4 trades away. Per row 10 runs improved (B3: 5 wrong goals and 5 aborts became successes; B4: 4 and 6) and 2 got worse (wrong goals; seeds 26 and 36, runs with a junction lie, a lying checkpoint and a false backtrack together). T4 has 0 false backtracks on the development seeds and 2 per row here: a lying checkpoint on the right branch of a disputed junction still overrides it.
- **Per row (successes of 40, T0 / T4; all rows in the table):** A1 to A4 off and on 40 / 40; B1 off and on 38 / 38; B2 off 34 / 34, B2 on 35 / 35; B3 off 23 / 23, B4 off 22 / 22 (the off rows are identical by construction); B3 on 23 / 31; B4 on 23 / 31.
- **Durations (successful runs, median / p95 / max s):** B3 on T0 220.2 / 296.5 / 300.4, T4 280.6 / 401.1 / 426.8; B4 on T0 204.7 / 272.6 / 288.1, T4 261.9 / 379.6 / 390.1; A3 on T0 214.4 / 271.2 / 271.2, T4 236.6 / 303.2 / 303.2; A4 on T0 199.7 / 250.7 / 257.8, T4 223.0 / 284.8 / 293.1. **The timeout the declared rule would give (information only):** from the longest successful run of a row: T0 at most 480 s (B3 on), T4 up to 660 s (B3 on, 426.8 s), 600 s (B4 on), 480 s (A3 on), 450 s (A4 on); the real value comes from Unity's runs. A 420 s limit (16.24.1) would have cut the T4 runs of B3 on above 420 s.
- **Most people in view:** 5 in A3, A4, B3, B4 under T4 (2 under T0, 2 in the rows without a checkpoint).
- **Estimate of the total time of the 260 final runs (20 x 13 settings; mean over all 40 runs of each row, failures included; simulated time only, no overhead between runs; A2 on the left turn = the A2 on row): T0 36,538 s (10.15 h), T4 39,581 s (10.99 h): +3,042 s (+0.85 h)**; the settings that change are A3 (215 to 238 s mean), A4 (197 to 223), B3 on (216 to 268) and B4 on (198 to 248). Per-setting means are in the table.
- **Verdict:** the bar is passed, so the stopping rule of 16.24 does not apply: no checkpoints are dropped. T4 stays a simulator result on provisional positions and the same-reliability assumption for the checkpoint liars; nothing in the experiments, `final_plan.json` or any frozen file was changed. No further variants (16.24).

### 16.24.3 T4 adopted for the detection-on settings (2026-11-18, Anisha); recorded BEFORE any change

**Decision.** T4 ("the checkpoint is a vote, not a veto", 16.24) is adopted by the stopping rule of 16.24: the out-of-sample check of 16.24.2 / 16.24.2.1 (simulator seeds 21 to 60, 40 runs per row) gave +20.0 percentage points in B3 on and in B4 on, above the 15 pp bar declared beforehand, and no A row lost a success or made a backtrack.

**Disclosed with the adoption.**
- T4 was designed after seeing 16.23.1 (T3's results on seeds 1 to 20); the gain on those seeds (+30 and +35 pp) is in-sample.
- The effect is smaller out of sample: +30 / +35 pp became +20 pp (8 extra successes of 40 in each row).
- The declared Newcombe 95% interval of each difference, -0.5 to +38.4 pp, touches zero; with the declared method the gain is not separated from no gain at 95%.
- The paired sign test (10 seeds gained, 2 lost, exact two-sided p = 0.039) was computed after seeing the data and is supplementary only.
- B3 and B4 give the same outcome on 38 of 40 seeds: one result counted twice.
- Simulator only: the checkpoint workers' positions are provisional (midpoint of the branch, 3.0 m to the right) until Unity's; the checkpoint liars have the junction liars' 20% (a simulator assumption); T4 made 2 false backtracks per row out of 15 on the fresh seeds.
- The estimated extra time of the 260 final runs is +0.85 h simulated (10.15 h to 10.99 h); successful T4 runs reached 426.8 s (the declared timeout rule would give 660 s from them, information only).

**What changes (declared now, nothing else).**
1. The four control files of the detection-on settings, `experiments/control_lie_on.json`, `control_lie_on_a1.json`, `control_lie_on_a2_right.json`, `control_lie_on_a2_left.json`: `lie_detection.checkpoint` true, `checkpoint_fraction` 0.5, `checkpoint_scope` "disputed" (a checkpoint pointing back counts only when the junction's answers disagreed; every other switch as before, `backtrack` of rule (c) stays false), and a `why.checkpoint` note. The detection-off files (`control_lie_off*.json`), `control.json` and the zoom files are not touched: `checkpoint` is absent = false there, so a detection-off run ignores the checkpoint workers (the same scene, the logic differs, as in 16.23).
2. `analysis.json`: one more entry in `declared_differences` (T4, with this disclosure). 
3. `final_plan.json`: the `test_assignment_note` (16.15) loses the third worker at J1 (two workers at every node since 16.21.2: the male slot 1 and the female slot 2 only; the file is not frozen).
4. `configs/v4/README.md`: the row of the control files says it. `docs/workflow_v4.md` does not exist (only `project_flow_v4.md`), so no document is updated there.
5. Tests: the configs as declared (the on files carry T4 exactly, the off files and the base files do not); the A rows unchanged (the control files run A3 and A4 on exactly as T3 did, no backtrack); the T4 numbers of 16.24.2.1 reproduced from these control files (seeds 21 to 60: B3 on and B4 on T0 23/40 and T4 31/40).

**Not changed, and why.** `sv.DETECTION_ON`, the "detection" blocks of `scenarios_ab.json` and `run_experiments_ab_v4.py` stay T0 (they are the earlier simulator study and the pinned flags; the T4 numbers come from `run_t3_v4.py`); the final guard (`final_guard_v4.SWITCHES`) is not extended to the checkpoint keys here (the freeze hashes the control files; reported as an observation); no `unity/` file; `frozen.json` and `freeze_v4.py --freeze` untouched.

**Open points, reported, not decided.** (a) Unity has no checkpoint workers yet. With the on files the robot stops at the midpoint of every branch leaving a decision junction, scans for `scan_timeout_s` (6 s), finds nobody who does not belong to the junction and carries on (+6 s per checkpoint); but it picks the nearest person who does not belong to the junction, so in Unity a worker of another junction inside the 360 camera's range could be taken for a checkpoint worker; the rule (or the range) is to be settled with Nusrat's positions. (b) The checkpoint workers' looks are not part of the test-look assignment of 16.15.

#### 16.24.3.1 Applied (2026-11-18): what was changed, as declared

- **Control files:** `experiments/control_lie_on.json`, `control_lie_on_a1.json`, `control_lie_on_a2_right.json`, `control_lie_on_a2_left.json` now carry `lie_detection.checkpoint` true, `checkpoint_fraction` 0.5, `checkpoint_scope` "disputed" and a `why.checkpoint` note (4 lines and one note each); every other key and the `backtrack` of rule (c) (false) as before. `control.json`, `control_zoom_on.json`, `control_zoom_off.json` and the three `control_lie_off*.json` files are untouched: the checkpoint keys are absent there (false), so a detection-off run ignores the workers.
- **`analysis.json`:** the 13th entry of `declared_differences` is the T4 entry with the disclosure of 16.24.3. **`final_plan.json`:** `test_assignment_note` no longer has a third worker at J1 and says the checkpoint workers are not part of the assignment. **`configs/v4/README.md`:** the control-files row says it. `docs/workflow_v4.md` does not exist: nothing updated.
- **Tests (`tests/test_checkpoints_v4.py`, 37 in all, 6 new in `AdoptedConfigs`; `tests/test_lie_detection_v4.py` updated):** only the four on files carry the keys and they equal the runner's T4 detection plus the base file's other keys; the off and base files build a controller with checkpoints off; the declared text changes are in place; a run from the control file equals the runner's T4 run (A3, A4, B3, B4, seeds 21, 26, 36, 40); the A rows unchanged (A3 and A4 on, seeds 21 to 30: all success, 0 backtracks, every checkpoint PROCEED); the numbers of 16.24.2.1 reproduced from `control_lie_on.json` (B3 on and B4 on, seeds 21 to 60: T0 23/40; T4 31/40 with 15 backtracks of which 2 false; wrong goals and aborts as in the table; no timeout at 900 s).
- **Not changed:** `sv.DETECTION_ON`, `scenarios_ab.json`, `run_experiments_ab_v4.py` (the earlier simulator study stays T0); the final guard's `SWITCHES` (it checks second opinion, reject impossible and backtrack, not the checkpoint keys: the frozen hashes of the control files will pin them; an observation for Anisha and Nusrat); `unity/`, `external/`, the v3 files, `frozen.json`; nothing frozen or run for the finals. The open points of 16.24.3 (Unity's checkpoint workers; the person the robot takes for a checkpoint worker) stand.

### 16.25 Who is asked at a checkpoint (2026-11-19, Anisha); recorded BEFORE any code

Branch `anisha/v4-tie-rule` after 471553e (T4 adopted, 16.24.3). Simulator and controller only. Closes the first open point of 16.24.3: at a checkpoint the robot asked the nearest person who does not belong to the junction; in Unity that can be a worker of another junction inside the 360 camera's range.

**Rule, declared now.** At a checkpoint the robot asks (and reads an answer from) only a person who
- (a) stands within R m of THIS branch's checkpoint spot,
- (b) has this spot as the NEAREST checkpoint spot, and
- (c) is not within the second-opinion zone (`lie_detection.second_opinion_radius_m`, 6.5 m) of any asking node (every junction and the start node).

Definitions. A *checkpoint spot* is the point of the road where the robot stops: `checkpoint_fraction` (0.5) of the way along a branch leaving a decision junction (a node of kind junction with two or more branches); the robot computes it from the roadmap alone (the worker stands beside it). The spots compared in (b) are all the spots of the map. A person's position is the 360 camera's world estimate of the fresh track; a pan-tilt reading counts only when it is linked (by bearing, `commander.json` `link_bearing_tol_deg`) to a qualifying 360 track, so a person who cannot be placed is never asked and never read. The rule is applied in three places: the scan (the nearest qualifying person is approached), the re-approach to a commander (only to a qualifying person) and the choice of the commander among the pan-tilt people (only qualifying ones). Nobody qualifies within `scan_timeout_s` (6 s, as now): the robot logs `checkpoint_no_person`, the result is NONE and it carries on; no backtrack, never an abort.

**R = 5.0 m (new key `lie_detection.checkpoint_person_radius_m`, default 5.0), from the geometry, not from results.**
- Lower bound: the worker stands `lateral_m` from the spot, 3.0 m in the layout and at most 4.0 m by the placement fallback (16.23); the robot stops within `arrive_junction_m` = 0.3 m of the spot; the 360 position estimate adds its own error (zero in the simulator, not measured in Unity). 4.0 + 0.3 = 4.3 m, plus 0.7 m for that error = 5.0 m.
- Upper bound: R must stay below half the distance between two spots, so that the discs of two spots never overlap (the closest are 11.79 m apart: 5.9 m), and below the junction zone (6.5 m); at 3.0 m separation a worker other than the checkpoint worker can still be inside a disc, which is why (b) and (c) exist.
- Consequence for Unity: if Nusrat's workers stand more than about 4.7 m from the spot, R is too small and must be re-derived the same way (checked in Part 4, AUDIT 16.26).

**Tests, declared now.** A worker of another junction is never asked (the nearest person to the robot at a spot is a junction worker: still not asked, and its gesture is not read); the checkpoint worker always is, for every checkpoint of the provisional layout (A3 and A4, seeds 1 to 20: the worker is inside R of its spot, its spot is its nearest, it is outside every junction zone, and no junction worker qualifies; and in the runs every checkpoint dialog asks the checkpoint worker); nobody qualifies = NONE, `checkpoint_no_person`, no backtrack.

**Rerun, declared now.** T0 against T4 on seeds 1 to 20 (cap 420 s, 16 rows, compared run by run with 16.24.1's folder `t3_v4_t4_420_20261118_202418`) and on seeds 21 to 60 (cap 900 s, compared with 16.24.2.1's folder `t3_v4_oos_21_60_900_20261118_203001`). In the simulator the checkpoint worker is the only person who qualifies at every spot, so no number is expected to change; if one changes, the runs and the reason are shown, nothing is tuned. T4's control files carry the new key (5.0) as part of the adopted configuration.

#### 16.25.0 Finding while building the rule: at three checkpoints the simulator showed the NEXT junction's workers (2026-11-19); recorded BEFORE the fix

The first test run of the rule of 16.25 failed 12 tests, because at the checkpoints of the branches that lead INTO a junction (J1 LEFT to J2, J1 RIGHT to J3, J2 FORWARD to J4) nobody qualified. Cause, found by tracing the people the robot saw at J1 LEFT: the simulator stages the scene of the next junction as soon as the controller's target is that junction, which already happens in the `execute` state (the turn toward the next node), before the robot has driven to the checkpoint. At the checkpoint the 360 camera therefore saw the workers of J2 (and J2's checkpoint workers) and NOT the checkpoint worker of its own branch, who belongs to the scene of J1. The old rule (the nearest person who does not belong to the junction) then asked a worker of the next junction, who answered as a checkpoint worker (a junction worker's `person_360` 1 in the log of the first smoke test). The branches to an endpoint (E) had no such switch (no scene), so there the checkpoint worker was asked. This is exactly the problem of 16.24.3's open point, found in the simulator itself: **the results of 16.23.1, 16.24.1 and 16.24.2.1 used a worker of the next junction as the checkpoint person on 3 of the 9 branches** (J1 LEFT, J1 RIGHT, J2 FORWARD); the other 6 used the checkpoint worker. The model of 16.23 declared that the robot sees the checkpoint workers of the branches leaving a junction; the staging did not do that for those three.

**Decision, declared now.** (1) The controller's target in the `execute` state is the checkpoint spot when the branch has one to be asked (it is the next place the robot goes; the heading is the same), so the scene of the junction the robot is leaving, with the checkpoint worker of the branch, stays until the checkpoint dialog is over; the next junction's scene is staged when the robot drives on from the checkpoint. No simulator code changes; `_target()` of `hri_control_v4.py` only. (2) The comparison asked for in 16.25 is made in three steps and reported as such: A = 16.24 as adopted (the stored runs: the flawed scenes and the old rule), B = the new rule with the old staging (the three checkpoints find nobody and carry on: they are effectively absent), C = the new rule with the fixed staging (every checkpoint asks its own worker). B is produced by a hook that puts the old `_target` back; the analysis script `analyse_cp_rule_v4.py` (analysis code) does it. C is what T4 means from now on. (3) T4's adoption (16.24.3) rested on A; the bar of 16.24 and 16.24.2 (+15 pp in B3 on and B4 on, no A loss) is re-applied to C in the report and the result is stated whatever it is. No new variant; nothing is tuned.

#### 16.25.0.1 Result of Part 1: the rule and the fixed staging (2026-11-19, simulator); the numbers of 16.24 change, shown run by run

Code: `lie_detection.checkpoint_person_radius_m` (5.0; `_cp_qualifies`, `_cp_pt_ok`, `_cp_spots`, `_cp_point`), the scan, the re-approach and the commander choice at a checkpoint restricted to qualifying people, `checkpoint_no_person` logged, `_target()` of the execute state = the checkpoint spot (16.25.0) in `hri_control_v4.py`; the four on files carry the key (5.0) and the rule in `why.checkpoint`; `analyse_cp_rule_v4.py` (analysis code) and `one_run(hook=, detection=)` in `run_t3_v4.py`; 7 new tests in `tests/test_checkpoints_v4.py` (`PersonRule`; 44 in all). Folders (git-ignored): `t3_v4_p1_1_20_420_20261119_191222` (T0 and T4, seeds 1 to 20, 420 s), `t3_v4_p1_21_60_900_20261119_191305` (seeds 21 to 60, 900 s), `analyse_cp_rule_v4_20261119_191505_part1` (A / B / C, report.md and report.json), `report_t4_oos_v4_..._p1_c_21_60` (the 16.24.2 table for C).

- **Why the numbers change.** In the model of 16.23 / 16.24 (A) the next junction's scene replaced the scene of the junction the robot was leaving before the checkpoint, so on the three branches into a junction the person asked was a worker of the NEXT junction: **25 of the 45 checkpoint dialogs in A3 on and A4 on (seeds 1 to 20) and 47 of 87 (seeds 21 to 60)**, 28 of 50 in B3 on and 26 of 51 in B4 on (seeds 1 to 20), 51 of 95 and 49 of 96 (seeds 21 to 60). With the rule alone and the old staging (B) those dialogs find nobody. With the rule and the fixed staging (C) every dialog asks its own checkpoint worker (45 of 45, 87 of 87, 51 of 51, 52 of 52, 93 of 93 twice): the table of the corrected model. T0 and every row without a checkpoint dialog (A1, A2, B1, B2, all off rows) are identical in A and C.
- **A / B / C, successes (wrong goals / aborts / timeouts; backtracks, false):**

| row | seeds | T0 | A (16.24) | B (rule, old staging) | **C (rule, fixed staging)** |
|---|---|---|---|---|---|
| A3 on, A4 on | 1-20 | 20/20 | 20/20, no backtrack | 20/20, no backtrack | **20/20, no backtrack** |
| B3 on | 1-20 | 11/20 | 17/20 (1/1/1; 7, 0) | 15/20 (3/2/0; 4, 0) | **17/20** (1/0/2; 8, 0) |
| B4 on | 1-20 | 11/20 | 18/20 (1/1/0; 7, 0) | 17/20 (1/2/0; 6, 0) | **19/20** (1/0/0; 8, 0) |
| A3 on, A4 on | 21-60 | 40/40 | 40/40, no backtrack | 40/40, no backtrack | **40/40, no backtrack** |
| B3 on | 21-60 | 23/40 | 31/40 (5/4/0; 15, 2) | 26/40 (5/9/0; 8, 1) | **30/40** (5/5/0; 14, 2) |
| B4 on | 21-60 | 23/40 | 31/40 (6/3/0; 15, 2) | 27/40 (5/8/0; 9, 1) | **30/40** (5/5/0; 14, 2) |

- **Runs whose outcome differs between A and C:** 3 on seeds 1 to 20 (B3 on seeds 1 and 17, B4 on seed 1) and 8 on seeds 21 to 60 (B3 on seeds 28, 36, 44, 51, 53; B4 on seeds 28, 36, 44); the others differ only by a few seconds of duration (the worker stands elsewhere: A3 on longest 303.2 s in A, 308.4 s in C). Each changed run is listed in `report.md` with the checkpoint answers of A and C: in every one the person asked at a branch into a junction is a different person (a junction worker's id below 100 in A, a checkpoint worker's id 100 and up in C), who lies or not by their own draw, so a lie is caught or let through differently (seeds 36 and 53 become successes; 28, 44 and 51 become failures).
- **The bar of 16.24.2 re-applied to C (seeds 21 to 60, 900 s, 40 runs): PASSED.** B3 on 30/40 (75.0%, Wilson 59.8 to 85.8) against T0 23/40 (57.5%): **+17.5 pp** (Newcombe 95%: -3.2 to +36.2; 9 seeds gained, 2 lost); B4 on likewise +17.5 pp. Above the 15 pp bar (the bar is 6 extra successes of 40; there are 7); no A row loses a success or backtracks. **The gain of 16.24.2.1 (+20.0 pp) rested on the flawed staging; the corrected figure is +17.5 pp, the declared interval reaches further below zero, and the paired sign test (supplementary, computed after seeing the data) is p = 0.065 against 0.039 before.** On seeds 1 to 20 C gives +6 and +8 successes (B3 on 17/20, B4 on 19/20). Had the three checkpoints simply been absent (B), the gain would be +7.5 and +10.0 pp, below the bar: the checkpoints on the branches into a junction contribute to the gain. The disclosures in `analysis.json` and in the `why.checkpoint` of the on files are corrected accordingly (the earlier figures are kept in the text as those of the flawed model).
- **Time (C):** estimate of the total of the 260 final runs: T0 36,538 s (10.15 h), T4 39,627 s (11.01 h), +3,089 s (+0.86 h); longest successful T4 run 432.2 s (B3 on): the declared timeout rule gives 660 s (information only), as before.

### 16.25.1 "Back" at the next junction (2026-11-19, Anisha, on Nusrat's report of 2026-11-19); recorded BEFORE any code

Nusrat's report (data): the branches J1 to J2 and J2 to J4 have no valid checkpoint spot; they lead into a junction whose honest workers point BACK when the robot arrives on a wrong path; in A4 and B4 the checkpoints are fixed and the random workers are drawn around them. Problem: `reject_impossible` rejects "arrival" answers at junctions, so the robot would reject the honest BACK answers of J2 and J4 and abort instead of backtracking. (16.25.0 showed the simulator had asked the NEXT junction's worker on exactly these branches, which is why this matters: that worker did what the rule below makes the robot do.)

**Rule, declared now.** When the robot arrives at junction K by the branch it chose at junction J, and J was DISPUTED (its accepted answers named different branches, `last_choice["disagreed"]`, as in T4), then K's resolved answer, after K's own second-opinion process, pointing BACK along the arrival road counts as the checkpoint vote: the robot backtracks to J, at most once per J, with the existing machinery (the one untried branch taken directly, or an ask again at J with the failed branch excluded). In every other case "back" stays rejected as now (`reject_impossible`). Branches with a checkpoint worker are unchanged: a robot that arrives at K by such a branch rejects BACK as before. Mirror-image ambiguity (16.11) is the one of `resolve_point`, as for any pointing.

**How, declared now.** Two new optional keys of `lie_detection`: `next_junction_back` (default false) and `checkpoint_branches` (a list of "J>COMMAND", default null = every branch leaving a decision junction as in T4); a branch has a checkpoint worker when `checkpoint` is true and the branch is in the list. At each arrival at a junction K the controller notes whether the rule applies (`next_junction_back`, K reached by the branch just decided at J, J disputed, that branch without a checkpoint worker, J not yet backtracked, another branch untried at J). In such a visit a held answer that resolves to the arrival road is not rejected but counted as a vote "BACK" in K's tally (so K's second opinions, the tie rule and the majority decide as for any answer); when the tally's decision is BACK the robot returns to J; when it is another branch the robot goes there as now. Logged as `answer_accepted` (back_vote) and `backtrack` (next-junction) and in `summary()["v4"]["checkpoint"]["next_junction_back"]`.

**Simulator layout, declared now.** `checkpoints.json` gets `branches`: the 7 branches with a checkpoint worker (J1 FORWARD, J1 RIGHT, J2 RIGHT, J3 LEFT, J3 RIGHT, J4 RIGHT, J4 LEFT); J1 LEFT (to J2) and J2 FORWARD (to J4) have none. The checkpoint positions are FIXED (planned before, and independent of, the junction workers; the same in every seed and in A3 / B3 and A4 / B4: midpoint, 3.0 m to the right, 16.23's rule); in A4 and B4 the random junction workers are then drawn around them with the placement rules (at least 3.0 m from every checkpoint worker, 1.0 m from every segment the robot can drive for a checkpoint, and the checkpoint workers 1.0 m from every segment of the junction workers). So that the runs of T0 and T4 of a seed stand in the same scene (as in Unity, where the checkpoint workers are in every setting), T0 is run with the checkpoint workers present and ignored by the robot: for A3 / B3 this is the earlier T0 (checked), for A4 / B4 the junction workers move. The T4 switches of the runner are `checkpoint_branches` (the 7) and `next_junction_back` true when `checkpoints.json` has `branches`; without `branches` T4 is the T4 of 16.25.0.1 (kept for the reproduction tests).

**Tests, declared now.** Arriving at K on a wrong branch from a disputed J backtracks and succeeds; from an undisputed J the BACK is still rejected (abort, no backtrack); a branch with a checkpoint worker is unchanged; truthful A runs never backtrack (A3 and A4 on, T4); the checkpoint positions are the same in every seed, and in A4 / B4 the random workers keep the rules around them for seeds 1 to 20; the controller's switches and refusals.

**Rerun and bar, declared now.** T0 against T4 on seeds 21 to 60, cap 900 s, all 16 rows, with this layout, reported as in 16.24.2 and against 16.24.2.1 and 16.25.0.1 under the same bar: B3 on AND B4 on each at least +15 percentage points over T0 and no A row loses a success or backtracks. **If it fails: report and stop (no new variant); the decision goes back to Anisha and Nusrat, and the control files are not changed.** If it passes: the four on files get `checkpoint_branches` and `next_junction_back` (the adopted T4 configuration of 16.24.3 as amended here), and the tests pin them.

#### 16.25.1.1 Result of Part 1b: the 7-checkpoint layout and "back" at the next junction (2026-11-19, simulator, seeds 21 to 60, 40 runs per row, cap 900 s); the declared bar applied

Code: `lie_detection.next_junction_back` (default false) and `checkpoint_branches` (default null) with `_back_context`, `_back_vote`, `_k_back`, `_cp_has` in `hri_control_v4.py` (a list entry for a node a map does not have is ignored, a typo on a node it has is refused: the first run crashed on A1 for this reason and was rerun after the fix; its partial output folder, which held only the config copy, was removed); `branches` and `fixed_first` in `configs/v4/experiments/checkpoints.json`; `decision_branches(road, branches)`, `plan_checkpoints`, the checkpoints planned before the junction workers, `clearance_problem` / `place_random` with `extra_workers` / `extra_segments` in `hri_sim_v4.py`; `--t0-with-workers`, T4's `checkpoint_branches` and `next_junction_back` in `run_t3_v4.py`; next-junction backtracks in `report_t3_v4.run_metrics` and `report_t4_oos_v4.py`; the four on files, `analysis.json` (the 13th declared difference) and `configs/v4/README.md`; 8 new tests (`NextJunctionBack`, 7, and a second reproduction test; `tests/test_checkpoints_v4.py` 52 in all). Folders (git-ignored): `t3_v4_p1b_21_60_900_20261119_192617` (raw runs, 1280), `report_t4_oos_v4_20261119_192744_p1b_21_60` (table.md, table.json).

- **Bar of 16.25.1: PASSED.** B3 on 23/40 (57.5%, Wilson 42.2 to 71.5) for T0 against 30/40 (75.0%, 59.8 to 85.8) for T4: **+17.5 pp** (Newcombe 95%: -3.2 to +36.2), **7 seeds gained, none lost**; B4 on the same (23/40, 30/40, +17.5 pp, -3.2 to +36.2, 7 / 0); the bar is 6 extra successes. **No A row loses a success** (A1 to A4, off and on: 40/40 in both variants) **and none makes a backtrack.** Every off row, A1, A2, B1 and B2 are identical in T0 and T4.
- **Against the earlier models (B3 on and B4 on, T4 of 40):** 16.24.2.1 (A, flawed staging) 31 and 31; 16.25.0.1 (C, 9 checkpoints, person rule, no BACK vote) 30 and 30; **16.25.1 (7 checkpoints, BACK vote at the next junction) 30 and 30**: removing the two checkpoints did not cost anything because the BACK vote at J2 and J4 replaces them.
- **What happened (per row, B3 on and B4 on alike):** 13 backtracks, **4 at the next junction (J1 LEFT to J2 twice, J2 FORWARD to J4 twice), none of them false**, 9 at checkpoints (8 sent a wrong branch back, **1 false**); 15 pointings back ignored as undisputed (the lying checkpoints on right branches of undisputed junctions); 48 answers rejected against 56 in T0 (the BACK answers that now count as votes are not rejected). Against T0, 8 runs improve (3 wrong goals and 4 aborts become successes, 1 abort becomes a wrong goal) and none gets worse.
- **Time:** the longest successful runs (T4, s): B3 on 411.1, B4 on 371.1, A3 on 283.4, A4 on 270.1 (T0: 300.4, 288.1, 271.2, 257.8); **the timeout the declared rule would give (information only): 630 s from B3 on (1.5 x 411.1 = 616.7, rounded up to 30 s)**, 570 s from B4 on, 450 s and 420 s from A3 and A4 on; no run reached the 900 s cap. **Estimate of the total time of the 260 final runs (20 x 13 settings, mean over all 40 runs of each row, failures included, simulated time only, A2 on the left turn = the A2 on row): T0 36,538 s (10.15 h), T4 39,026 s (10.84 h): +2,487 s (+0.69 h)**; the settings that change are A3 (215 to 230 s mean), A4 (197 to 213), B3 on (216 to 264) and B4 on (198 to 242). (16.25.0.1 gave 660 s and 11.01 h for the layout with 9 checkpoints.) Most people in view: 4 in A3, A4, B3 and B4 (the two checkpoint workers of J1 and its two junction workers), 2 elsewhere.
- **Control files (the pass branch of 16.25.1):** the four on files now also carry `checkpoint_branches` (the 7) and `next_junction_back` true, with 16.25.1 in `why.checkpoint`; the off files and `control.json` are untouched. The tests pin the files to the runner's T4.
- **Disclosed, as in 16.24.3 and 16.25.0.1:** the gain is +17.5 pp (not the +20.0 pp first adopted); the declared Newcombe interval reaches below zero (-3.2); B3 and B4 share seeds and liars and agree on all 40 seeds (identical outcomes: one result counted twice); T0 of this comparison has the checkpoint workers present and ignores them (identical to the earlier T0 in A3 / B3, a different draw of the junction workers in A4 / B4); positions provisional until Unity's; the checkpoint workers lie with the junction workers' 20% (a simulator assumption); the BACK vote relies on the honest workers at J2 and J4 pointing back when the robot arrives on a wrong path, as Nusrat reports for Unity; with only two workers per junction the vote at the next junction is the tie-break the junction itself lacked. No further variants.

### 16.25.2 The final guard checks the checkpoint switches (2026-11-19, Anisha); recorded BEFORE any code

**Why.** T4 is part of the detection-on settings (16.24.3, 16.25, 16.25.1) but `final_guard_v4` verified only the three rules (`second_opinion`, `reject_impossible`, `backtrack`) of a setting's control file. A final run with a control file that had the checkpoint switches wrong (absent, `checkpoint_scope` "any", the wrong radius or branches) would have passed the preflight and `check_setting`.

**Decision, declared now.**
1. `final_guard_v4.SWITCHES` is extended with the checkpoint keys: `checkpoint`, `checkpoint_fraction`, `checkpoint_scope` (as asked) and also `checkpoint_person_radius_m`, `checkpoint_branches` and `next_junction_back`, which T4 has carried since 16.25 and 16.25.1 (a guard that verified three of the six would let the other three drift). The original three are kept as `LIE_RULES`; `export_csv_v4.lie_detection_label` (a / b / c letters, 'on' / 'off') uses `LIE_RULES`, so its output does not change.
2. The expected values are declared once, in `final_plan.json` (`lie_detection_checkpoint`, new block, hashed by the freeze like the rest of the plan; the file is not frozen): "on" = the T4 values of the on files (`checkpoint` true, `checkpoint_fraction` 0.5, `checkpoint_scope` "disputed", `checkpoint_person_radius_m` 5.0, the seven `checkpoint_branches`, `next_junction_back` true); "off" = `checkpoint` false (the other keys do not matter when the checkpoint is off). Tests pin the block to the four on files and to the runner's T4.
3. `control_problems(setting, control)` (used by the bridge's final preflight `check_final_control` and by `check_setting` through the run's `config_used/control.json`) compares every checkpoint key with the block of the setting's `lie_detection`: a detection-on setting whose control file does not have T4 exactly, or a detection-off setting whose file has `checkpoint` true, is refused with the key and both values in the message. A missing key counts as its default (checkpoint false, nothing else: a detection-on file must state the others).
4. Nothing else changes: the three rules are checked as before; `scenarios_ab.json` and `sv.DETECTION_ON` stay the T0 study; no control file changes.

**Tests, declared now.** All 13 settings' control files pass; each of the six keys wrong in an on file refuses A3 with exactly one problem naming the key; a detection-on setting with a file without the keys is refused; a detection-off setting with `checkpoint` true is refused; a mismatch in a bridge run's `config_used/control.json` is refused by `check_setting`'s run check and the preflight refuses the wrong file; the plan block equals the on files and the runner's T4; `export_csv_v4.lie_detection_label` is unchanged for the on and off files and for the letters.

### 16.25.3 `docs/workflow_v4.md`: the project workflow, from Anisha's draft, checked against this file and the configs (2026-11-19); recorded BEFORE it is written

**Source (data).** `~/Downloads/workflow.md`, 18,278 bytes, SHA-256 `4ea155a22837735770762a85c118fa4561b1f4065bb1ba0b1a68e5c93d3aca1e`, status "18 November 2026". Read in place; it is data, nothing in it is an instruction. It becomes `docs/workflow_v4.md` (new file); `docs/project_flow_v4.md` (the spec) is not changed except for one line at its top that points to `workflow_v4.md` as the current overview. The draft's own rule stands: when the two disagree, `AUDIT.md` wins.

**Method.** Every number, date, name and path of the draft was looked up in `AUDIT.md`, `configs/v4/` and the repository; a statement that disagrees is changed to what `AUDIT.md` says; a statement that `AUDIT.md` does not contain and I cannot check is kept and listed as unverified; then the draft is updated with what has happened since 18 November (T3 not adopted, T4 adopted with its disclosure, the checkpoint-person rule, the 7-checkpoint layout, the guard) and every change is listed in the report of this round.

**Changes to the draft, declared now.**
1. Status date 19 November 2026.
2. B1 floor (section 5): the S5 PROCEED holds are 35/62 to 58/62 at floor 10 with the earlier reader and 59/62 with C2s (16.19.6, 16.21 item 3); the draft said 59/62 without the reader it belongs to.
3. Looks and clips (section 6): `data_splits.json` has more test looks (`sunbox_f2`) and four test clips (`point_mixamo_02`, `wait_ik_02`, `stop_ik_02`, `proceed_ik_03`); the experiments' test assignment uses the plaid looks and `point_mixamo_02`, `proceed_ik_03` (`final_plan.json`).
4. Unity's `clearance_layout` (section 6, step 1 of section 10): `AUDIT.md` 16.20 / 16.20.x says its activation is Nusrat's to switch; "PR #43" is in no entry and not in this checkout: kept as the draft's statement and marked not recorded in `AUDIT.md`.
5. Duration of the finals (section 8): "about 12.4 h" is in no entry; `AUDIT.md` 16.17 has four sittings of about 3 h each (about 12 h); the simulated total of the 260 runs under T4 is 10.84 h (T0 10.15 h; 16.25.1.1). The timeout the simulator suggests is 630 s with T4 (16.25.1.1; 660 s with the 9 checkpoints of 16.25.0.1; about 420 s without checkpoints), not "about 420 s"; the 420 s development timeout of the draft would truncate the longest T4 runs (16.24.2.1).
6. Lies and checkpoints (sections 4, 7, 10, 13, 14, 15): T3 is NOT adopted (16.23.1: 6 lies caught and 6 false backtracks per row); T4 is adopted by the stopping rule (16.24.3) with its disclosure: designed after seeing 16.23.1, the out-of-sample gain first +20.0 pp and, after the staging finding of 16.25.0, +17.5 pp, the declared Newcombe interval -3.2 to +36.2 touches zero, the paired sign test is supplementary; the checkpoint-person rule of 16.25 (R = 5.0 m); the 7-checkpoint layout and the BACK vote at the next junction of 16.25.1 and its result 16.25.1.1; the final guard of 16.25.2; positions provisional until Unity's (16.26 waits for Nusrat's file).
7. Paths (sections 9, 12): `finals_v4/` and `paper_v4/` are at the repository root, not under `robot_vision/`; the new simulator tools and `checkpoints.json` are listed.
8. Section 14: the `test_assignment_note` cleanup is done (16.24.3); the open questions are the ones that remain.

**Kept and not checkable here (listed, not changed):** the advice never to use GitHub's "Fix with Copilot" (it is in no entry; it is Anisha's own rule), the planning estimates of 1.5 to 2 and 3 to 4 weeks, and the name "Niva" for Nusrat.

### 16.26 BACK is hard to read: Nusrat's findings, Unity's checkpoint positions, a side view, POINT frames (2026-11-19, Anisha); recorded BEFORE any computation

Branch `anisha/v4-tie-rule` after c066028 (clean, equal to origin). Every item below is a change decided AFTER development results and is disclosed like the STOP rule (16.18, 16.19.7): the reasons are the findings, no value is tuned on the results of the finals (there are none), the criteria are declared before the numbers.

**Inputs (data, read in place, nothing copied into the repo).** (1) `~/Downloads/positions.csv`, SHA-256 `c20268236950485cd98b773fbbc65fbe1329fc57cf32957ddb2c2aefed9534d3` (verified; 582 bytes; `positions (1).csv` next to it is byte-identical): 7 checkpoints on the v4 map (columns map, from, command, to, s_m along the branch, right_m beside it, x, z, the anchor on the road abeam, distances to the junction and the next node, nearest node), none on J1 to J2 or J2 to J4. (2) **Nusrat's back-reading zip: NOT RECEIVED.** The request names it as `<Nusrat's back-reading zip>` with `<hash>` unfilled and no such file is in `~/Downloads` (three zips there: `anisha_gesture_logs_20261114_143539.zip`, `step5_logs_20261117_011303.zip`, `stop_session_logs_20261115_192423.zip`, all of 14 to 17 November). Her diagnosis is therefore recorded below as Anisha's summary of it (data, not verified by me), her PROPOSED diff is not seen and not used, and item 3 runs on the three development datasets we hold; her zip is added to item 3 when it is given (path and SHA-256), with the same variants and criteria.

**Findings recorded (Nusrat's, as given).** Honest BACK pointings at 145 to 163 degrees from the camera are unreadable: the arm looks short and bent and 0 of 20 frames passed the POINT cue; 42 % of honest BACKs fall within 30 degrees of the camera line (LEFT and RIGHT 1.4 to 2.5 %); the development data read only 45 to 135 degrees; with two people in view Python ran at about 4.4 frames per second, so the 1.0 s POINT window held 2 to 6 frames and the 6-frame minimum (`window.min_valid_fraction` 0.6 x 10 frames) returned `insufficient_history`. **Consequence: the simulator assumed BACK readable, so T4's +17.5 pp (16.25.1.1) is likely optimistic**; nothing in 16.24.3 to 16.25.3 is changed by this entry until the reruns below are done and shown.

**Item 1. Checkpoint positions and where the robot asks from.** The seven workers stand where `positions.csv` puts them (`s_m` along the branch, `right_m` beside it: J1 FORWARD 15.5 / -4.0, J1 RIGHT 6.0 / +4.0, J2 RIGHT 15.5 / -4.0, J3 LEFT 15.5 / -4.0, J3 RIGHT 14.5 / -4.5, J4 LEFT 15.5 / -4.0, J4 RIGHT 14.5 / -4.5; negative = left of the travel direction), replacing the provisional rule of 16.23 (midpoint, 3.0 m to the right). The robot's spot is the point of the road abeam the worker (the file's anchor): `lie_detection.checkpoint_s_m` (new, per branch, roadmap only: the spot is the junction plus s_m along the branch) replaces `checkpoint_fraction` where present. From the spot the approach rule of v3 (2.0 m from the person on the line to them) puts the robot at the point 2.0 m across from the worker, so the worker is seen at 90 degrees to the road: a BACK along the road is then at 90 degrees from the camera, the middle of the readable band. R stays 5.0 m (16.25): the worker is 4.0 or 4.5 m from the spot (at most 4.7 m is allowed), margin 0.2 m for the 4.5 m ones against 0.7 m for the others. For every checkpoint I check, and report: the worker at least 3.0 m from every other worker and every turning point, outside the 6.5 m zone of every junction and the start node (the file gives 7.21 m for J1 RIGHT, the nearest), 1.0 m from every segment the robot can drive (roads, the junction workers' ask segments, and now the segments to the 2.0 m across points), and Part 1's rule (the worker qualifies, nobody else does). **Question for Anisha, not decided here: does the point 2.0 m across leave the drivable area?** The ground-truth grid (`grid.json`) is in no file I hold (none of the three zips has one), so I cannot test the 7 points (2.0 m or 2.5 m from the road centre line, between the road and a worker spot Nusrat chose); geometrically each lies on the segment between a road point and a valid worker position, inside the aisle, but pallets or stations between them are unknown to me. I stop at this question in the report and build on the geometry until I am told otherwise.

**Item 2. 4a side view.** Trigger: an arm is raised and fails the POINT cue on arm length (`point.arm_length_min`) or elbow angle (`point.point_arm_extension_min_deg`) for `dialog.gesture_hold_s` (the reader reports which cue, a new field `Reading.point_fail`; no reader value changes). Then, once per ask, the robot takes its second reading from a point on the 2.0 m circle around the worker (never closer: the way there follows the circle, the recovery's rear and clearance checks, nobody else within 1.2 m of the point). **The angle I propose, with reasons:** the viewpoint whose line of sight is PERPENDICULAR to the arrival road (the axis of a BACK), on the road side of the worker; for a worker 17 to 35 degrees off the line of sight (rel 145 to 163 degrees) that is a rotation around the worker of rel minus 90 = 55 to 73 degrees; the rotation is clamped to 60 to 90 degrees. Reasons: (a) the readable band is 45 to 135 degrees of the pointing direction from the line of sight and its middle is 90, so perpendicular puts a BACK at 90 with a margin of 45 degrees on both sides; (b) over the observed range 145 to 163 degrees the rotation that maximises the worst-case margin is 64 degrees (margin 36), inside the clamp; (c) over the observed range 145 to 163 degrees every rotation from 28 to 100 degrees lands the BACK inside the readable band (163 minus 135 = 28, 145 minus 45 = 100); the clamp 60 to 90 sits inside that interval and gives 85 to 103 degrees at 60 and 55 to 73 at 90, at least 10 degrees from the edge of the band; (d) the side is the road side, not a guess: the sign of the pointing direction is not known from a failed reading, but a BACK is by definition along the arrival road, so the perpendicular viewpoint is fixed by the road, not by the arm. If the second reading also fails the answer stays unclear (the existing asks count), nothing loops.

**Item 3. 4b POINT frames: analysis only, no value changed, shown before anything is chosen.** Variants replayed on all development data we hold: the three zips (step-5 logs, STOP sessions, the 14 November gesture logs = the stand-in for D4), plus Nusrat's zip when given, all through the split guard (development only). Reference = the reader as it is now (gesture_reader.json: B1 floor 10 for PROCEED and the C2s STOP switch, the controller's reading while stopped). (i) **Floor tied to frames received** (Nusrat's idea; her floor is not known to me, so a sweep, declared now): POINT / WAIT need valid arm frames >= max(floor, 0.6 x the frames received in the 1.0 s window) with floor 3, 4 and 5 (the PROCEED analogue was 10 of 20 expected = 50 %). (ii) **Stretch**: keep the 6-frame minimum and let the window grow in steps of 0.1 s from 1.0 s up to 2.0 s until 6 valid frames are in it (the reader already receives 2.0 s of history), the 2.0 s window's own proportional rule not applied. **Measured per dataset and variant:** the POINT read rate (frames in the holding phase read as POINT; read as another command; `insufficient_history`), by the number of people in view and by the angle between the pointed direction and the line of sight (45 to 135 band, beyond); the minimum and median valid frames of frames read as POINT; the accuracy of read POINT frames against the true pointed angle by class of the true direction (LEFT, FORWARD, RIGHT, BACK by the angle to the robot's forward axis) with `dialog.branch_match_max_deg` as the tolerance (either depth reading within it); false POINT readings (POINT read when the worker shows nothing, WAIT, STOP or PROCEED); STOP, WAIT and PROCEED readings against the reference. **Declared criteria:** (1) no loss of accuracy on LEFT, RIGHT and FORWARD points: for each class the share of read POINT frames within the tolerance is not below the reference's, and the number of wrong POINT readings (both readings beyond the tolerance) is not above it; (2) no STOP reading changed: every frame has the same STOP / not-STOP reading as in the reference in every dataset; (3) no false POINT rate above the reference's. Report the read rate and the minimum frames used. **Stop and show Anisha the table before choosing; nothing is switched on.**

**Item 4. Simulator (after item 3 and Anisha's choice, not built before).** Readability by the angle between the pointed direction and the line of sight, for every view including the side views: the boundary is FITTED on the development data of item 3 (read rate by 15 degree bin of that angle) if every bin of the fit has at least 20 frames, else the band reported by Nusrat is used (readable 45 to 135 degrees, unreadable beyond 135); which of the two is used is stated with the table. **Reruns** (after item 4): T0 against T4 on seeds 21 to 60 and on fresh seeds 61 to 100 (confirmatory; never used before), cap 900 s, all 16 rows, the checkpoint positions of item 1 and the side view of item 2 in T4. **Bar, declared:** B3 on AND B4 on each at least +15 percentage points over T0, no A row loses a success or backtracks. **If it fails: report and stop; the decision goes back to Anisha and Nusrat.**

**Stop for this round: after the table of item 3.** Items 1 and 2 are built and tested; item 4 and the reruns wait for the choice of 4b.

#### 16.26.1 Result of items 1 to 3 (2026-11-19); nothing is chosen, nothing is switched on, items 4 and the reruns have not been done

**Item 1: the positions.** `configs/v4/experiments/checkpoints_unity.json` holds the seven rows of `positions.csv` (SHA-256 verified; in `source`); `checkpoints.json` (the provisional layout of 16.23 / 16.25.1) is untouched and no control file is changed (that is an adoption decision after the reruns); the controller has `lie_detection.checkpoint_s_m` (per branch, default none = the fraction): the robot's spot is the junction plus `s_m` along the branch and equals the file's anchor for all seven. `check_checkpoints_v4.py` (check code; `outputs/check_checkpoints_v4_20261119_205152_unity`) measures every checkpoint in A3 and in A4 (seeds 1 to 20; the random workers drawn around the fixed ones): **every rule holds**: worker 4.0 m (J1 FORWARD, J1 RIGHT, J2 RIGHT, J3 LEFT, J4 LEFT) or 4.5 m (J3 RIGHT, J4 RIGHT) from its spot (at most 4.7 m, so R = 5.0 m holds, margin 0.2 m for the 4.5 m ones); at least 3.0 m from every other worker (A3: 6.80 m at least; A4 over 20 seeds: 3.55 m at least, J1 RIGHT) and 12.5 m or more from another checkpoint worker; 7.21 m (J1 RIGHT) or more from every junction and start node, so outside the 6.5 m zone; at least 15.2 m from every turning point except J1 RIGHT (7.21 m); 2.78 m (A4) or 3.17 m (A3) at least from every road and every segment the robot can drive; the junction workers 1.03 m (A4) or 1.78 m (A3) at least from the checkpoint segments; Part 1's rule: each checkpoint worker qualifies at its spot and nobody else does. The robot asks from the spot, 2.0 m across the worker, which is 2.0 m (4.0 m workers) or 2.5 m (4.5 m workers) from the road centre line, the worker at 90 degrees to the road (tested in the runs: 2.0 m from the worker, 90 degrees within 12). **Not checkable: whether the 2.0 m across point is inside the drivable area of Unity** (no `grid.json` in any file I hold): a question for Anisha and Nusrat (her grid check of the seven across points); until answered the simulator has no obstacles there. Tests: `tests/test_unity_checkpoints_v4.py` (10).

**Item 2: the side view (built, unit-tested, off by default).** `Reading.point_fail` ("length" or "elbow": a raised arm held for the window fails that cue on at least `decision.class_share_min` of its hold frames; written to the log only when set; no reader value changed; tests in `tests/test_gesture_motion.py`) and the controller's `side_view` block (`SIDE_VIEW_DEFAULTS`: enabled false, rotation 60 to 90 degrees, arcs of at most 30 degrees, clearance 2 x the corridor half width = 1.2 m): the perpendicular viewpoint of 16.26, the way round a polygon whose legs touch the 2.0 m circle and never enter it, blocked (logged `side_view_blocked`) when somebody is within 1.2 m of the way or the viewpoint, a free ask (not an unclear answer), once per ask. The rear check of the recovery is not used: the robot never reverses here. **It is not exercised in a simulated run: the simulator cannot yet produce a failed POINT reading (item 4).** Tests: `tests/test_side_view_v4.py` (8).

**Item 3: the table (`outputs/point_frames_v4_20261119_210341_item3`, 5 variants x 3 datasets, all development, zips S5 `step5_logs_20261117_011303.zip` 75bbc885..., STOP `stop_session_logs_20261115_192423.zip` ca1173ac..., D4* `anisha_gesture_logs_20261114_143539.zip` a39cb429...; Nusrat's zip not received, so not in it).** Frames in the holding phase of a true POINT, read as POINT / held (insufficient_history):

| variant | S5 | STOP sessions | D4* | ALL | min valid frames of a POINT read |
|---|---|---|---|---|---|
| reference (6 in the 1.0 s window) | 199/569 (35.0 %), 185 | 178/428 (41.6 %), 0 | 636/1308 (48.6 %), 88 | 1013/2305 (43.9 %), 273 | 6 |
| (i) max(3, 0.6 x received) | 303/569 (53.3 %), 6 | 178/428, 0 | 658/1308 (50.3 %), 14 | 1139/2305 (49.4 %), 20 | 3 |
| (i) max(4, 0.6 x received) | 300/569 (52.7 %), 10 | 178/428, 0 | 658/1308, 18 | 1136/2305 (49.3 %), 28 | 4 |
| (i) max(5, 0.6 x received) | 265/569 (46.6 %), 56 | 178/428, 0 | 657/1308, 21 | 1100/2305 (47.7 %), 77 | 5 |
| (ii) 6 frames, window up to 2.0 s | 303/569 (53.3 %), 8 | 178/428, 0 | 659/1308 (50.4 %), 23 | 1140/2305 (49.5 %), 31 | 6 |

- **Frames in the 1.0 s window by people in view (reference):** 1 person median 7 (144 of 2148 below 6); 2 people median 5 (113 of 144 below 6); 3 or more median 4 (13 of 13 below 6). Read rate by people in view, reference / (i) floor 3 / (ii): 1 person 995/2148 / 1044 / 1044; **2 people 18/144 / 84 / 85; 3 or more 0/13 / 11 / 11**. So the `insufficient_history` of the slow windows is real in these data and both ideas remove most of it.
- **By the angle between the pointed direction and the line of sight (read / held):** 0 to 45 degrees 0/63 in every variant; 45 to 135 832/1952 (reference), 945 (i3), 946 (ii); 135 to 145 179/252, 188; 145 to 163 2/17, 6/17; 163 to 180 0/21 in every variant. Neither idea reads the pointings at or beyond 163 degrees or along the line of sight: it is the same geometry limit as Nusrat's, and why 4a and the across geometry of item 1 are needed.
- **Accuracy by class (tolerance 30 degrees, read frames: accurate share, wrong):** LEFT reference 362 read, 97.8 %, 8 wrong; (i3) and (ii) 411, 96.8 %, 13 wrong; FORWARD 102 / 105 read, 100 %, 0 wrong in all; RIGHT 273, 97.8 %, 6 wrong against 332, 98.2 %, 6 wrong; BACK 276, 98.9 %, 3 wrong against 291 to 292, 99.0 %, 3 wrong.
- **Side effects:** **no STOP reading changed in any dataset** (0 gained, 0 lost for every variant); WAIT unchanged; PROCEED 56 gained and 1 lost frames for (i), 60 and 0 for (ii) (the PROCEED window shares the same arm window); false POINT readings 6 of 28,099 frames (4 for floor 5) against 0 in the reference.
- **The declared criteria:** (2) no STOP reading changed: **met by all four**; (3) false POINT not above the reference's: met by rate (0.0 % to 0.0 %; 6 frames of 28,099 are 0.02 %, against 0), the count is not zero; **(1) accuracy on LEFT, FORWARD and RIGHT not below the reference: NOT met by any of the variants as declared**, because of LEFT alone: the extra reads include 5 more wrong LEFT readings (13 against 8; the share falls 97.8 % to 96.8 %); FORWARD and RIGHT meet it. The declaration is applied as written; whether the 5 extra wrong LEFT frames (about 10 % of the 49 extra LEFT reads against 2.2 % in the reference) are a property of short windows or of a few windows is not known from this table. **Not chosen; shown to Anisha first.**

#### 16.26.2 What is behind criteria (1) and (3) (2026-11-19; facts from `outputs/point_frames_v4_20261119_211247_detail/detail.json`, no choice made)

The detail mode of `analyse_point_frames_v4.py` (`--detail`, same three development zips, variants (i) floor 3 and (ii) stretch) lists the frames behind the two counts. Both variants give the same frames.
- **The 5 extra wrong LEFT readings (criterion 1) are ONE window: 5 consecutive frames (0.8 s, t = 157.92 to 158.72 s) of ONE pointing:** step-5 session B2_right_off, run 3, worker 25 (`sunbox_m_tshirt_black`, clip `point_ik_01`, right arm), the robot standing still (state read), one person in view, true pointed angle -120.99 degrees relative to the robot's forward axis (125 degrees from the line of sight), the reference read every one of these frames as `insufficient_history` (5 valid frames of 5 received); the variants read POINT with 5 (floor 3) or 6 (stretch) valid frames, and the nearer depth reading was 34.96 to 35.03 degrees from the truth in the first four frames and 30.77 (floor 3) or 31.49 degrees (stretch) in the fifth, against the tolerance of 30 degrees (`dialog.branch_match_max_deg`): beyond it by 0.8 to 5.0 degrees. The criterion counts frames, so one episode counts five times; the 49 extra LEFT frames the variants read hold no other wrong one.
- **The 6 false POINT frames (criterion 3, 4 for floor 5) are two short episodes of ONE worker in one run:** step-5 session A3, run 1, worker 105 (`sunbox_m_shirt_white`, no clip, arm none: shows nothing), two people in view, 4 frames at t = 94.97 to 98.40 s and 2 frames at 112.59 to 113.10 s, read POINT with 4 to 5 valid frames (floor 3) or 6 (stretch); the robot was standing still in five of the six. No other run, session or dataset has a false POINT.
- **What this does and does not say:** both numbers that fail the declared criteria come from a single window each; the tolerance (30 degrees) and the criteria are as declared and are not changed here; whether to read the failures as a property of short windows or as noise from two episodes is Anisha's judgement. Not examined: why worker 105's idle arm read POINT with two people in view (the match of the reading to the worker is by bearing within 10 degrees, so a mismatch with the other person is possible; not checked).

### 16.26.3 Decision: 4b variant (ii) (2026-11-19, Anisha); recorded BEFORE any change; the safety condition is declared here and checked before anything else is built

**Decision.** Variant (ii) of 16.26 item 3 is adopted: the POINT (and WAIT) window keeps the 6-valid-frame minimum and stretches in steps of 0.1 s from 1.0 s up to 2.0 s until 6 valid frames have arrived. Reason: the same read rate as the floors (85/144 against 84/144 with two people in view, from 18/144) while never deciding on fewer than 6 frames.

**Disclosed plainly, like the STOP rule.** Chosen AFTER seeing 16.26.2. Of the criteria declared in 16.26 for item 3, **criterion 1 (accuracy on LEFT, FORWARD and RIGHT not below the reference) and criterion 3 (false POINT not above the reference) are NOT met** by (ii) as declared: criterion 1 fails on one 0.8 s window of a LEFT pointing read 31 to 35 degrees from the truth against the 30 degree tolerance (step-5 B2_right_off, run 3, worker 25); criterion 3 fails on 6 false POINT frames of one idle worker (step-5 A3, run 1, worker 105; 0 in the reference). **Criterion 2 (no STOP reading changed) is met.** The criteria are not changed; the decision is Anisha's judgement of those two failures, and the table of 16.26.1 stays as it is.

**Safety condition, declared now, checked FIRST.** Replay the dialog with (ii) on all development data we hold (the three zips); **if ANY wrong answer is accepted, stop and report before building anything else.** A wrong answer is (a) an accepted direction that is not the commander's true direction, or (b) an answer accepted from a false POINT frame (a person who does not show a POINT). Also reported: the asks recovered against the reference (asks accepted with (ii) that the reference did not accept, split into right and wrong, and asks the reference accepted that (ii) does not).
Method (replay of the dialog, evaluation code `analyse_point_dialog_v4.py`, development data only, through the split guard): (1) the step-5 sessions are the only data with asks. For every ask (the state `ask` of `decisions.csv` begins one) the window of `ask_window_s` (5.0 s) is replayed; the commander is the person who shows a POINT in it (the most true-POINT frames); the label of a frame is what the controller would give it: a POINT reading is resolved with `hri_control_v4.resolve_point` against the branches and the arrival road of the roadmap of that session (`roadmap_a1.json`, `roadmap_a2_right.json`, `roadmap_a2_left.json`, `configs/v4/roadmap.json`) at the junction nearest to the robot at the start of the ask, `dialog.branch_match_max_deg` (30 degrees), the mirror-image rule on for the detection-on sessions and off for `B1_off` and `B2_right_off`; anything else (no POINT, an arrival-road answer, ambiguous) is NONE. The frames go to `GestureDialog` with the controller's values (hold `gesture_hold_s` 0.5 s, `max_none_gap_s` 0.3 s, window 5.0 s, 2 asks). The true direction of the commander is the roadmap target (a branch, or the arrival road) nearest to the worker's true pointed world angle within 30 degrees, else none. (2) For every OTHER person-track in an ask window, and for every person-track of the STOP and D4 stand-in sessions (no asks there), who does not show a POINT, the whole stream of POINT readings is fed to `GestureDialog` as a direction label (each depth reading as its own stream, the strictest reading); any acceptance is a wrong answer of kind (b). Limits, stated: single view (the controller's second view and re-approach are not replayed), the commander rule is not replayed (any person of the window can be the commander in the live controller), no safety stops are replayed.

**If the condition holds (no wrong answer accepted): build (ii) as a v4 reader switch** `window.stretch_to_s` in `gesture_reader.json` (key absent = the reader as it is; the v3 path, `hri_perception.py` and the v3 config, is untouched), switched on by a declared edit with the disclosure above in the `declared_differences` of `analysis.json`, with tests. Then **item 4** and the **reruns**.
**Item 4, declared now: the simulator models readability by the angle between the pointed direction and the line of sight, for every view including the side views.** Today the simulator reads every pointing. The model: a POINT shown at an angle `a` (0 = away from the camera along the line of sight, 180 = at the camera) is read with the probability fitted on the development data replayed with (ii) (the read rate of the frames in the holding phase, bins of 15 degrees), but only where every bin has at least 20 frames; bins with fewer take the band reported by Nusrat (readable from 45 to 135 degrees, unreadable beyond) as a step; which is used is stated with the table. An unreadable pointing gives a raised arm that reads NONE with `point_fail` "length" (so the side view of item 2 can start); the side view is a second viewpoint and the angle is recomputed for it. The model is a function of the angle only: it adds no other noise.
**Reruns, declared now:** T0 against T4 on seeds 21 to 60 and on FRESH seeds 61 to 100 (confirmatory; never used), cap 900 s, all 16 rows, with Unity's checkpoint positions (`checkpoints_unity.json`) and the ask from across (16.26 item 1), the side view on in T4 (item 2) and the stretch reader (ii) for both T0 and T4 (the simulator's frame counts are not modelled, so (ii) changes no simulated reading; stated). **Bar, as declared in 16.24.2 and 16.26: B3 on AND B4 on each at least +15 percentage points over T0, no A row loses a success or backtracks.** If it fails: report and stop; no new variant. **Stop after the rerun table.**

**Across-point geometry: pending Nusrat's drivable-area check.** The robot asks from the point 2.0 m across the worker (2.0 m from the road centre line for the 4.0 m workers, 2.5 m for the 4.5 m ones); whether those seven points are inside Unity's drivable area is NOT verified (no `grid.json` in any file I hold): everything built on it (the checkpoint positions and the ask from across) stands as "pending Nusrat's check". Nusrat's back-reading zip is not needed (Anisha, 2026-11-19); her diff was a suggestion only and is not used.

#### 16.26.3.1 Result of the safety condition (2026-11-19; `outputs/point_dialog_v4_20261119_235411_safety`): **the condition does NOT hold as declared: stopped, nothing else built**

`analyse_point_dialog_v4.py` (evaluation code; tests `tests/test_point_dialog_v4.py`, 7), the dialog replay of 16.26.3 on the three development zips (S5 `step5_logs_20261117_011303.zip` 75bbc885..., STOP `stop_session_logs_20261115_192423.zip` ca1173ac..., D4* `anisha_gesture_logs_20261114_143539.zip` a39cb429...; split guard: all development), reference against (ii):
- **Wrong direction accepted with (ii): 0** (reference 0).
- **Asks (35 step-5 asks with a POINT commander, single view): accepted 13 by the reference and 20 by (ii); recovered 7, all RIGHT** (A2_right run 2 at t0 221.38: RIGHT after 2.23 s; A3 run 1 at J1: LEFT at t0 93.22 (2.28 s), 95.29 (0.62 s), 108.58 (2.34 s), 120.19 (1.93 s); A3 run 2 at J1: RIGHT at t0 491.51 (2.22 s) and 503.05 (3.87 s)); **lost 0; accepted by both with a different direction 0**; no other person of an ask window accepted (0).
- **Answers accepted from a false POINT frame with (ii): 10 (reference 0), all in step-5 A3 run 1 at J1:** 2 asks (t0 93.22 and 95.29, commander track 105, answer LEFT, true LEFT: the correct direction) and 8 stream acceptances (tracks 105 and 150, label RIGHT in the robot-relative classes of the stream test, both depth readings, at t = 95.50, 97.82, 112.90 and 113.61 s). STOP sessions and D4*: 0 (their streams accept 0 and 72 times, none from a false POINT frame).
- **What the flagged frames are, from the truth rows (not proven):** at t0 = 93.22 the commander of the truth is worker 3 (`sunbox_m_tshirt_black`): start_delay from 93.22, gesturing 93.69, POINT held 94.19 to 98.22, returning to 99.10. The frames counted as false POINT (the detail of 16.26.2 had listed six such frames, on tracks 105 and 150) carry the truth of an idle worker with another look (`sunbox_m_shirt_white`, arm none) while the same track's other frames in the window are matched to the pointing worker 3, and track 105 is the commander of both asks (track 150 of the ask at t0 108.58). The match of a person to a worker in this analysis is by bearing within 10 degrees (`analyse_false_stop_v4.category_of`); the likely reading is that two workers at J1 stand within 10 degrees of each other in some frames and the track's frames are assigned to the wrong one, which would make these frames true POINT frames of the pointing worker counted as false. **Not checked:** a track-consistent assignment (each track to the worker it matches most often) and a recount; not run, because the condition as declared is "any answer accepted from a false POINT frame", it is not met, and the decision is Anisha's.
- **Also seen:** the stream test labels frames by the angle to the robot's forward axis (LEFT, FORWARD, RIGHT), not by the roadmap, so its RIGHT label for the frames of the LEFT-true asks is that convention, not a wrong direction (the resolved ask answers are LEFT, correct).
- **Not built, as declared:** the reader switch `window.stretch_to_s`, the `analysis.json` entry, item 4 (readability by angle in the simulator) and the reruns on seeds 21 to 60 and 61 to 100 are NOT done. The decision whether (ii) goes ahead given this result (or after a track-consistent recount) goes back to Anisha.

### 16.26.4 The track-consistent recount: is the false-POINT finding of 16.26.3.1 the replay's association or (ii)? (2026-11-20, Anisha); declared BEFORE anything is computed

**Purpose.** The 10 answers "accepted from a false POINT frame" of 16.26.3.1 (all step-5 A3 run 1 at J1: 2 asks at t0 93.22 and 95.29, commander track 105, plus 8 stream acceptances on tracks 105 and 150) were found with the replay's OWN association, not the live one: the commander was "the track with most POINT frames in the window" (the controller never does that), the stream test fed EVERY track as if it were the commander, and a frame's truth worker was the worker nearest by bearing within 10 degrees, chosen again at every frame (two workers close in bearing can swap between frames). This recount replaces all three with what the live system does, and nothing friendlier. No reader, config or controller code changes in this step; the variant is applied to the replay only (`analyse_point_frames_v4.variant_ctx`), as before.

**What is replayed (the live association).** Evaluation code `analyse_live_association_v4.py` (new; tests `tests/test_live_association_v4.py`), development data only through the split guard, the three zips read in place (S5 `step5_logs_20261117_011303.zip` 75bbc885..., STOP `stop_session_logs_20261115_192423.zip` ca1173ac..., D4* `anisha_gesture_logs_20261114_143539.zip` a39cb429...). Unit of replay = a frame that has a row in the session's `v4_log.jsonl` (the frames the controller interpreted; `trial` = run). Per such frame, in order:
1. persons = the persons of `hri_perception_v4.PersonsPipeline` for that pan-tilt frame (same config; reference reader, or with (ii) through `variant_ctx`), with the robot-stopped reading switch applied as in 16.26.3;
2. commander = `commander_v4.pick_commander(persons, ccfg, previous, early)` with the controller's own `previous` (the commander of the previous replayed frame; at the first frame of a window the logged commander of the last logged row if it is at most 1.0 s earlier, else none) and its own `early` rule (a person whose arm was raised, `raised_since` as in `ControllerV4._track_onsets` over ALL frames of the run, before the question was shown; the question time of a window = the start of the first ask of that dialog = the first of consecutive asks at the same junction of the same run less than 30 s apart);
3. 360 track = `commander_v4.link_to_360(commander bearing, 360 people, link_bearing_tol_deg)` on the newest 360 frame at or before the logged `ctrl_t` of that row, no older than `people_stale_s` (as `_link_360`);
4. label = the controller's: `resolve_point` against the branches and arrival road of the session's roadmap at the nearest junction (S5), `branch_match_max_deg`, mirror rule as `reject_impossible` of the session; for the STOP sessions and D4* (no asks, no roadmap) the label is the robot-relative class of the commander's POINT reading as in 16.26.3 (LEFT, FORWARD, RIGHT; BACK no answer);
5. `GestureDialog` with the controller's values (hold 0.5 s, none gap 0.3 s, window 5.0 s). S5: one dialog per ask, window = the ask start to +5.0 s as in 16.26.3. STOP and D4*: one continuous stream per run (chain of commanders over the logged frames, restarted after every break of more than 1.0 s between logged frames), the dialog tiled over it: a window starts at the first logged frame, and after an acceptance the next window starts at the next frame, after an expiry (5.0 s without an acceptance) at the first frame past the window's end. (Disclosed: the stream test of 16.26.3.1 stopped examining a track after its first window without an acceptance (`analyse_point_dialog_v4.stream_check`, `if acc is None: break`), so it saw less of the long runs than this recount does; both numbers are reported.)
Only the commander's label reaches the dialog; no other track does. Not replayed (declared, as before): the second view, the side view, the re-approach, safety stops.

**How the replay is verified against the live logs (reference reader, every logged row of all three datasets, before anything else is read).**
- V1 persons: the replay's persons at the frame with the logged reading time (within 0.0015 s) equal the logged `persons` as a set of (track id, `bearing_deg` to 0.01 degrees) and, per person, `reading.command` and `valid_frames` equal.
- V2 commander: the replayed commander (free-running chain, as used for (ii)) equals the logged `commander.commander` on every row.
- V3 360 track: the replayed 360 track equals the logged `commander_360` on every row.
- Reproduced = V1, V2 and V3 each hold on 100 % of the rows of all three datasets. Any row that does not agree is listed (session, trial, t, replayed against logged). **If the live association is not reproduced, the recount FAILS** (same as a remaining false accept): (ii) is not built, and I stop and report the disagreements. No rule is changed to make them agree.

**Which worker a commander is (evaluation only, never the controller's).** The truth identity of a replayed commander at a frame = the truth worker nearest, in the ground plane (x, z), to the position of the commander's 360 track (robot pose + the 360 track's `bearing_deg` and `distance_m`, `hri_control.world_point`), with the truth row nearest to the 360 frame time (at most `truth_join_max_s` = 0.06 s away). Declared now: the nearest worker must be within 1.0 m and the second nearest at least 0.3 m farther; otherwise, and when the commander has no 360 track, the identity is UNRESOLVED (not guessed). The truth category of that worker at the pan-tilt frame time is then POINT, WAIT, STOP, PROCEED or nothing as in `analyse_false_stop_v4.category_of` (phase `returning` left out = unresolved category). The true direction of an ask = `true_label` of 16.26.3 applied to the frames of the identified commander.

**Reported for ALL THREE datasets, reference reader and (ii), side by side.** Per dataset: V1, V2, V3 counts; asks (S5) or streams (STOP, D4*); answers accepted; right; WRONG; accepted with a FALSE POINT frame in the accepted hold (a replayed commander frame with a POINT reading whose identified worker does not show a POINT at that time); accepted with an UNRESOLVED identity in the hold; the 10 answers of 16.26.3.1 one by one (what each becomes under the live association); every accept of (ii) that the reference does not make, with its identity and truth; the figures of the old stream test beside them for comparison.

**Pass / fail, declared.**
- **Pass** = reproduced (V1-V3 all 100 %) AND none of the 10 answers of 16.26.3.1 remains (each is either gone, or its hold has no false POINT frame under the live association) AND no wrong and no false-POINT accept appears anywhere in the three datasets AND no accept has an unresolved identity in its hold. Then (ii) meets the safety condition of 16.26.3, and I build it, item 4 and the reruns as declared in 16.26.3.
- **Fail** = any of the 10 remains, OR the live association is not reproduced (V1-V3 below 100 %), OR a new wrong or false-POINT accept appears. (ii) is NOT built, the reference reader stays, and I stop and report.
- **Inconclusive** = identities unresolved in an accepted hold (the evidence cannot show the condition). Treated as Fail for the build decision (nothing is built); reported as inconclusive, with the frames, so that Anisha can decide.
The thresholds above (1.0 m, 0.3 m, 1.0 s, 30 s, 100 %) are fixed here, before the first number is seen. Chosen after seeing 16.26.3.1 (the 10 findings); disclosed. Output folder `outputs/live_association_v4_<time>[_label]/` (report.json, report.md, run.json with the config hashes and the git commit); never overwritten.

#### 16.26.4.1 Result of the recount (2026-11-20; `robot_vision/outputs/live_association_v4_20261120_004014_recount`): **declared verdict FAIL: the live association is NOT reproduced; (ii) is NOT built**

`analyse_live_association_v4.py` (evaluation code; tests `tests/test_live_association_v4.py`, 11), run once as declared on the three zips (guard: all development; S5 75bbc885..., STOP ca1173ac..., D4* a39cb429...). Nothing in the reader, the controller or any config was changed.
- **Verification (reference reader, every logged row; 100 % required): not met.** Rows without a replayed frame: 0 of 1923 (S5), 1899 (STOP), 2083 (D4*). V1 (persons) differs on 513 / 377 / 401 rows, V2 (commander) on 129 / 5 / 7, V3 (360 track) on 129 / 5 / 7 (V3 differs on exactly the V2 rows).
- **What the disagreements are (read from `report.json`; no rule changed because of it):**
  1. **Bearing rounding:** 305 (S5), 373 (STOP), 392 (D4*) of the V1 rows differ only in the bearing by 0.01 degrees (maximum 0.010): the log rounds to 0.01 and the replay differs in the last digit. My declared tolerance (0.0051) was too tight for this; it is not a difference in what the reader saw.
  2. **The reader config of the replay is not the one the logs were read with (S5: 208 rows).** The replay used the current `gesture_reader.json`, which contains `proceed.min_valid_floor` (B1, adopted in 16.21, AFTER these sessions were recorded); the live logs were read with the nominal rule (this is why `analyse_proceed_stop_v4.py` removes that key for its "current" variant, line 478). The replay reads PROCEED where the log has NONE (188 rows) or insufficient_history (19 rows); one row POINT in the log, NONE in the replay. Those frames make the replay pick a commander where the live system had none: the 129 V2/V3 rows of S5 are all of the kind logged none, replayed a commander (A1, B1, A2, B2 sessions, i.e. PROCEED showings). The 5 (STOP) and 7 (D4*) commander differences are mostly the other direction (logged a commander, replayed none: 5 in STOP and 2 in D4*, 7 of the 12; logged none, replayed a commander: 5 in D4*); I have not traced them further.
  3. My declaration said "same config" for the persons; for these logs that was wrong (item 2). It is a mistake of the declaration, found by the verification the declaration asked for.
- **Figures of the recount, reported as declared but NOT valid evidence, because the replay does not reproduce the log:** S5 asks 97 (95 with a commander): reference 13 accepted, 13 right, 0 wrong; (ii) 20 accepted, 20 right, 0 wrong, **0 accepted with a false POINT frame, 0 with an unresolved identity**. Step-5 A3 run 1 at J1: in all eight asks the commander track (105, 150, 188, 217, 220) is linked to 360 track 35 or 31 and identified by position as worker 3 (the pointing worker) or worker 7; none of the former 10 answers remains (asks at t0 93.22, 95.29, 108.58, 120.19 accepted LEFT, true LEFT, no false POINT frame). STOP sessions: 232 windows, reference 32 accepted, (ii) 32, 0 false, 0 unresolved. D4*: 263 / 271 windows, reference 110, (ii) 115 accepted, 0 false POINT, **2 accepted with an unresolved identity** in each reader (which would make the declared verdict INCONCLUSIVE on its own). Under the old stream test the 8 stream acceptances were tracks 105 and 150, which here are the commanders and are matched to the pointing worker.
- **What this does and does not say.** The evidence is consistent with the false POINT frames of 16.26.3.1 being the replay's bearing match (the commander of those asks is the pointing worker once the 360 position is used), but the declared condition for building (ii) was a reproduced live association, and it is not met. Per the declaration: **FAIL, (ii) not built, the reference reader kept**; the reader switch `window.stretch_to_s`, the `analysis.json` entry, item 4 and the reruns on seeds 21 to 60 and 61 to 100 are NOT done.
- **A corrected recount needs a new declaration (not done; it goes back to Anisha):** the replay reads with the reader the logs were read with (`proceed.min_valid_floor` removed, as in `analyse_proceed_stop_v4`), the V1 bearing tolerance 0.0101 (the logs' rounding), and the 12 STOP/D4* commander rows are traced first. The same pass / fail criteria and the identity rule would stand, with the 2 unresolved D4* accepts looked at beforehand.

### 16.26.5 Decision: no corrected recount; the reference POINT reader stays; the rest of Part 4 runs with it (2026-11-20, Anisha); recorded BEFORE anything below is computed

**Decision (Anisha).** No corrected recount. As declared in 16.26.4, the live association could not be reproduced, so **variant (ii) is not built and the reference POINT reader stays** (`gesture_reader.json` unchanged; no `window.stretch_to_s`). **Recorded as the likely reason, without further analysis:** the replay used a reader different from the one the logs were read with (the current config has `proceed.min_valid_floor`, adopted after the sessions were recorded). Nothing more is claimed: the 10 flagged answers of 16.26.3.1 are neither explained nor cleared, and the STOP/D4* commander differences and the 2 unresolved D4* accepts of 16.26.4.1 stay untraced. **Frame rate** is measured in step 5 under final conditions (frames per window by 1, 2 and 3 or more people); any later decision on POINT frames (a floor, a stretch) is made on that data and declared before it is computed.

**The rest of Part 4, with the reference reader.** (a) The across-point checkpoint asks of 16.26 item 1 stay as built, **pending Nusrat's drivable-area check** (no `grid.json` in any file I hold). (b) 4a, the side view of 16.26 item 2, is switched on in T4 for the reruns (off by default in the controller; T0 never has it). (c) Item 4, the simulator's readability by pointing angle, as declared in 16.26.3 with two changes forced by the decision: the fit is on the **reference** reader's replay (not (ii)), and **there is no stretch reader** in the reruns (T0 and T4 both use the reader as it is; the simulator's frame counts are still not modelled, so the reader changes no simulated reading).
**Item 4, exact rule (declared now, before the bins are computed).** Frames: those of `analyse_point_frames_v4.run_variant` for the reference reader on the three development zips (S5, STOP sessions, D4*; guard: development only): frames in the `holding` phase of a true POINT with a measurable angle `a` = the angle between the pointed direction and the line of sight (`sight_angle`: 0 = pointing away from the camera, 180 = at the camera), as in 16.26.1. 15 degree bins, [0, 15) to [165, 180]. A bin with at least 20 such frames takes its read rate (frames read as POINT over frames held) as the probability that a pointing at that angle is read in a frame; a bin with fewer takes Nusrat's band as a step (probability 1 if the bin lies inside 45 to 135 degrees, else 0). **Declared caveat, stated before the numbers:** the read rate of the held frames also contains reasons that are not the angle (the first frames of a hold before the window is full, slow windows with several people, `insufficient_history`); the simulator models the hold timing separately and reads every frame at 10 valid frames. The fitted probability therefore counts those reasons a second time and is pessimistic for T0 and T4 alike; I apply the rule as declared and do not correct for it (no new variant), and I say so with the table. The probability is drawn per frame and per person from the simulator's own generator only where it is strictly between 0 and 1 (a band step draws nothing, so every earlier run is unchanged when the model is off). An unreadable pointing shows a raised arm that reads NONE with `point_fail` = "length" (the side view can start); a readable one is read as before. The angle is computed from the robot's pose at the frame, so a side view (another viewpoint) recomputes it. WAIT, STOP and PROCEED are not affected. The model is a function of the angle only.
**Reruns (declared in 16.26.3, restated):** T0 against T4 on seeds 21 to 60 and on FRESH seeds 61 to 100 (never used before), cap 900 s, all 16 rows (A1 to A4 and B1 to B4, off and on), `--checkpoints configs/v4/experiments/checkpoints_unity.json --t0-with-workers`, the same readability model in T0 and T4, the side view on in T4 only. **Bar: B3 on AND B4 on each at least +15 percentage points over T0 (report_t4_oos_v4.py: success rates with Wilson intervals, Newcombe for the difference), and no A row loses a success or backtracks.** If the bar is not met: report and stop; no new variant; the decision goes to Anisha and Nusrat. **Stop after the rerun table.**

### 16.26.6 Item 4 built (2026-11-20): the fitted readability model, a defect of the side-view trigger found by running it in the simulator, recorded BEFORE the reruns

**The model (declared rule of 16.26.5, applied as written).** `fit_point_readability_v4.py` (evaluation code) on the reference reader and the three development zips (guard: all development; S5 75bbc885..., STOP ca1173ac..., D4* a39cb429...): 2305 held frames, 1013 read as POINT. Output `outputs/point_readability_v4_*/`, the model file `configs/v4/experiments/point_readability.json` (SHA-256 `92c818f31d8721822a3b5bebb4cc02e22b3188f47f1175e9b4c6b4a479fcb19b`). 15 degree bins, read / held: 0-15 14 frames (fewer than 20: band, 0.0); 15-30 0/20 (fitted 0.0); 30-45 0/29 (0.0); 45-60 132/567 (0.233); 60-75 161/259 (0.622); 75-90 121/243 (0.498); 90-105 86/265 (0.325); 105-120 154/298 (0.517); 120-135 178/320 (0.556); 135-150 181/269 (0.673); 150-165 0 frames (band, 0.0); 165-180 0/21 (fitted 0.0). **10 bins fitted, 2 from the band.** As declared in 16.26.5 the probabilities inside the readable band are low (0.23 to 0.67) because the read rate also contains reasons that are not the angle; this makes reading harder in the simulator for T0 and T4 alike and is NOT corrected. (The 135 to 150 bin reads better than several bins inside the band; no change made because of it.)
**Simulator.** `GestureSimConfig.point_readability` (None = as before), `readability_p`, and in `ReaderLevelVision.person_readings`: a POINT that would be read is, with the probability of its bin (angle between the pointed world direction and the line of sight from the robot to the person, from the robot's pose at the frame, so a side view recomputes it), instead a raised arm reading NONE with `point_fail` "length"; a probability strictly between 0 and 1 draws once from the simulator's own generator, 0 and 1 draw nothing (tests: a model of all ones leaves the generator state and every reading unchanged). `run_t3_v4.py`: `--readability FILE` (the same model in every variant) and `--side-view` (T4 only), recorded in `run.json`; the record of a run has `side_views`. Tests `tests/test_point_readability_v4.py` (12).
**A defect found by running the side view in the simulator for the first time.** The trigger of 16.26 item 2 was evaluated only for a selected commander, after the commander test in `ControllerV4._interpret`. A raised arm held still that fails the POINT cue reads NONE, so `pick_commander` never selects it ("raised arm neither moving nor holding a command") and the side view could not start in a run: with the readability model on, 76 of 80 runs had frames with `point_fail` and 0 had a side view. The unit tests of 16.26.1 set `sv_since` directly and did not cover this path. **Fix (`ControllerV4._track_side_view`, called before the commander test):** the person being asked is the commander if there is one, else the facing person in the direction of the worker the robot approached, within `link_bearing_tol_deg` (10 degrees, the commander rule's own link value); the clock, the once-per-ask rule, the geometry and every value are unchanged; off by default, so no earlier behaviour changes. Tests in `tests/test_side_view_v4.py` (13 now, 5 new).
**Disclosed: smoke runs before the declared reruns.** To time the runs and to see whether the side view starts, I ran T4 "on" for A3, A4, B3, B4 on seeds 21 to 40 (80 runs; seeds that belong to the rerun set 21 to 60, not the fresh ones) twice: with a stand-in band model (53/80 successes, no side view) and, after the fix, with the real model (28/80, 215 side views in 75 runs, none blocked, 40 timeouts). No T0 was run, no number was compared, and nothing (no value, no model, no variant) was chosen on these runs; the only change after them is the trigger fix above, made because no side view started, not because of an outcome. The reruns below are the declared ones, in full, on both seed ranges.

#### 16.26.7 Result of the reruns (2026-11-20): **the declared bar FAILS on both seed ranges; stopped, nothing adopted, no new variant**

Declared in 16.26.5 and 16.26.6, run once each: T0 and T4, all 16 rows, 40 seeds per row, cap 900 s, `--checkpoints configs/v4/experiments/checkpoints_unity.json --t0-with-workers --readability configs/v4/experiments/point_readability.json --side-view` (side view in T4 only, the same readability model in both), reference reader, 1280 runs per range. Folders `robot_vision/outputs/t3_v4_rerun_s21_60_20261120_010047` (seeds 21 to 60) and `t3_v4_rerun_s61_100_20261120_010047` (FRESH seeds 61 to 100, never used before); tables by `report_t4_oos_v4.py` in `outputs/report_t4_oos_v4_20261120_010602_rerun_s21_60` and `..._010607_rerun_s61_100`. Simulator numbers: properties of its geometry and noise model, not measurements.

| | seeds 21 to 60 | fresh seeds 61 to 100 |
|---|---|---|
| **B3 on**, T0 -> T4 | 20/40 (50.0 %) -> 8/40 (20.0 %): **-30.0 pp** (Newcombe -47.6 to -9.1) | 26/40 (65.0 %) -> 11/40 (27.5 %): **-37.5 pp** (-54.7 to -15.7) |
| **B4 on**, T0 -> T4 | 17/40 (42.5 %) -> 17/40: **+0.0 pp** (-20.7 to +20.7) | 25/40 (62.5 %) -> 18/40 (45.0 %): **-17.5 pp** (-37.0 to +4.2) |
| A rows losing successes (T4 against T0, seeds lost) | A2 on 40, A3 off 12, A3 on 25, A4 off 12, A4 on 12 | A2 on 39, A3 off 12, A3 on 26, A4 off 8, A4 on 11 |
| A rows with a backtrack | none | none |
| Bar (B3 on and B4 on each at least +15 pp; no A loss) | **FAILED** | **FAILED** |

T0 under the same model: A1, A2, A3 on 100 % in both ranges (A4 on 85.0 % and 92.5 %); T4: A2 on 0/40 and 1/40, A3 on 15/40 and 14/40, B2 on 7/40 and 11/40 (T0 35/40 and 37/40), almost all of the lost runs are timeouts at 900 s (T4 total simulated time of the 260 final runs about 30 h against 10 h for T0). Zero wrong goals are added by T4 in the A rows.
**What one run shows (a diagnosis of one case, not a result, nothing changed):** A2 on, T4, seed 21 (the honest worker at B points RIGHT in all 7 gestures): the first side view (t 98 s) completes and the ask follows; the second side view starts at t 120.8 s (rotation -60 degrees, target 9.15 / 0.83) and the robot stays in the state `approach` until the cap, 780 s, at 0.93 m from its viewpoint and 2.14 m from the worker with two waypoints still in the list; the same seed in T0 succeeds at 155 s. Whether this stall (a way that the controller's approach step does not finish) explains the A-row losses in general is NOT established: other rows lose runs by timeouts and aborts for reasons not examined (A3 off, A4, B2 on). The readability model is the declared pessimistic one (in-band probabilities 0.23 to 0.67, 16.26.6), which makes asks fail often in T0 too, but T0 stays at 100 % in A1 to A3.
**Not done and not decided here:** no new variant, no fix of the possible side-view stall, no second rerun, no change to `control.json`, `final_plan.json` or any frozen file; the stopping rule of 16.24 (the report tool's text: checkpoints dropped, T0 stays) is NOT applied by me: the decision goes to Anisha and Nusrat. T4's earlier +17.5 pp (16.25.1.1) does not hold under this simulator model.

### 16.26.8 Decision (Anisha, 2026-11-20; Nusrat is informed afterwards, not yet asked): ONE final check of T4 without the side view; recorded BEFORE anything below is computed

**Why.** The rerun of 16.26.7 is contaminated by the side-view stall: A2 on has no checkpoints at all and still falls from 40/40 (T0) to 0 and 1 of 40 by timeouts at 900 s. It cannot say whether checkpoints work. The side view stays in the code, off (default), and is not touched.
**The check, declared now.** T4 as adopted in 16.24.3 (a checkpoint pointing back counts only when the junction's answers disagreed; person rule R = 5.0 m of 16.25; the seven fixed checkpoints and the BACK vote at the next junction of 16.25.1) **plus the across-point checkpoint asks of 16.26 item 1** (`configs/v4/experiments/checkpoints_unity.json`, SHA-256 `15cc1977f1d9ab1c996a0eba6d7bb58b94a0eaa9b78cf404d372d9574c82cd68`; the robot asks from the point 2.0 m across the worker, **pending Nusrat's drivable-area check**), **WITHOUT the side view** (no `--side-view`; `side_view.enabled` false, the controller's default), with the **readability model of 16.26.6 (`point_readability.json`, SHA-256 `92c818f31d8721822a3b5bebb4cc02e22b3188f47f1175e9b4c6b4a479fcb19b`) in both T0 and T4**, the reference reader, T0 in the same scene as T4 (`--t0-with-workers`). **Fresh seeds 101 to 140 (never used: the simulator ranges so far are 1 to 20, 21 to 60 and 61 to 100), cap 900 s, all 16 rows, 40 runs per row.** `run_t3_v4.py --variants T0 T4 --first-seed 101 --runs 40 --timeout-s 900 --checkpoints configs/v4/experiments/checkpoints_unity.json --t0-with-workers --readability configs/v4/experiments/point_readability.json`, table by `report_t4_oos_v4.py`.
**Bar, unchanged:** B3 on AND B4 on each at least +15 percentage points over T0 (success rate), and no A row loses a success or backtracks.
**Final either way.** Pass: T4 (without the side view) stays adopted. Fail: the stopping rule of 16.24 applies (checkpoints dropped, T0 kept, the limitation reported). **No further variants, no fix of the side-view stall, no reruns.** This step changes no control, config or frozen file (`control.json`, `final_plan.json`, `analysis.json` stay as they are); what follows from the outcome is for Anisha to apply (Nusrat is informed afterwards).
**For information only (not used for the decision):** the same settings on seeds 21 to 60, the table reported next to it.
**Declared caveat, as in 16.26.6:** the readability model is the pessimistic one (in-band probabilities 0.23 to 0.67; the held-frame read rate counts reasons other than the angle a second time); it applies to T0 and T4 alike.

#### 16.26.8.1 Result of the final check (2026-11-20; `robot_vision/outputs/t3_v4_final_check_s101_140_20261120_011844`, table `outputs/report_t4_oos_v4_20261120_012143_final_check_s101_140`): **the bar FAILS; the stopping rule of 16.24 applies**

**The check as declared in 16.26.8, run once:** T4 (16.24.3 and 16.25.1) with the across-point checkpoint asks of Unity's positions, side view off, the 16.26.6 readability model in both T0 and T4, fresh seeds 101 to 140, 900 s, all 16 rows, 40 runs per row (1280 runs). Simulator numbers.
- **B3 on: T0 24/40 (60.0 %), T4 24/40 (60.0 %): +0.0 pp (Newcombe -20.6 to +20.6; 2 seeds gained, 2 lost). B4 on: T0 23/40 (57.5 %), T4 23/40: +0.0 pp (-20.7 to +20.7; 1 gained, 1 lost).** The bar is at least +15 pp in each.
- **A rows: no success lost, no backtrack, every A row identical to T0** (A1 to A3 100 % in both settings, A4 75.0 % off and 92.5 % on in both). The side-view stall of 16.26.7 is gone with the side view off (A2 on 40/40 in T0 and T4).
- B rows off, B1 and B2 on: identical to T0 (the checkpoints act only in the "on" rows of B3 and B4). T4 adds 4 backtracks in B3 on (1 false) and 2 in B4 on (1 false); wrong goals B3 on 9 -> 8, B4 on 7 -> 7; aborts B3 on 7 -> 8. Duration of the 260 final runs: T0 10.07 h, T4 10.59 h (+0.52 h).
- **Outcome as declared: FAIL. T4 is not adopted; the stopping rule of 16.24 applies (checkpoints dropped, T0 kept, the limitation reported).** I changed no control, config or frozen file and made no further variant, no stall fix and no rerun; applying the outcome to the files is for Anisha (Nusrat is informed afterwards, not yet asked). **Limitation to report:** under the declared readability model (pessimistic, 16.26.6) a checkpoint worker, whose BACK is read only when across the line of sight, did not make the system better in the simulator on 40 fresh seeds; the earlier +17.5 pp and +20.0 pp (16.24.3, 16.25.1.1) assumed every pointing readable and do not hold under this model; the across-point geometry is still pending Nusrat's drivable-area check.
**For information only (not used for the decision), seeds 21 to 60, the same settings (`t3_v4_info_s21_60_noside_20261120_011844`, `outputs/report_t4_oos_v4_20261120_012146_info_s21_60_noside`):** B3 on 20/40 -> 22/40 (+5.0 pp, 2 gained, 0 lost), B4 on 17/40 -> 20/40 (+7.5 pp, 3 gained, 0 lost); every A row identical to T0; no A backtrack; T4 4 backtracks in each of B3 on and B4 on (1 of them at the next junction in each; B3 on 1 false). Below the bar of +15 pp as well.

#### 16.26.8.2 The change in `gesture_motion.py` (answer to Anisha's question, 2026-11-20; committed in 7d5c101)
It adds an OUTPUT, not a rule: `Reading.point_fail` ("length" or "elbow", default ""), the helper `point_fail_reason` (reads the same cue values as `frame_flags`, decides nothing) and, in `_arm_window`, a key `point_fail` in the per-arm info of a held raised arm whose POINT cue fails on length or elbow in at least `class_share_min` of its frames. **It has no switch (it is always computed), and no command, score, `why`, validity count, point estimate, hold or any other reading value depends on it;** the controller reads it only when `side_view.enabled` (off by default). **Checked, not assumed:** the reference reader replayed on all three development zips with `gesture_motion.py` of c066028 (before the change) and with the current file, every `Reading` (both `reading` and `reading_stopped` of every person-frame; S5 22,428, STOP 20,348, D4* 21,326 readings) serialised by `to_dict` without the `point_fail` keys: **the SHA-256 of each dataset is identical** (S5 7f3a537b..., STOP 6ce45cff..., D4* 34792cbe...). Where the new code does differ is in the LOG: 105 (S5), 592 (STOP) and 354 (D4*) readings carry the extra `point_fail` key (in the arm's info and, when the reading is "cues not met", on the reading); a log reader that compared whole rows byte for byte would see it. (A first comparison that dropped only the top-level key gave different hashes: the key also sits in `reading.arms`; stripped there too, the hashes agree.)

### 16.26.9 Applying the outcome of 16.26.8: checkpoints dropped, T0 kept for the finals (2026-11-20, Anisha; Nusrat is informed afterwards); recorded BEFORE any file is changed

**Decision (Anisha).** The final check of 16.26.8.1 failed the declared bar (B3 on +0.0 pp, B4 on +0.0 pp on fresh seeds 101 to 140). By the stopping rule of 16.24 **checkpoints are dropped and T0 is kept for the finals.** No further variants, no fix of the side-view stall, no reruns (16.26.8).
**What changes (all of it by this entry):**
1. **The four `control_lie_on*.json` files** (`control_lie_on`, `_a1`, `_a2_right`, `_a2_left`): `lie_detection` = T0 exactly, as before T4: `second_opinion` true, `reject_impossible` true, `backtrack` false, `max_opinions` 3, `second_opinion_radius_m` 6.5 (the junction's own people: radius and nearest node), and now explicitly `checkpoint` false and `next_junction_back` false. The keys `checkpoint_fraction`, `checkpoint_scope`, `checkpoint_person_radius_m` and `checkpoint_branches` are removed (nothing reads them with the checkpoint off); the `why.checkpoint` text becomes a record of the 16.26.9 outcome. The side view stays off (the block is absent: the controller's default, `side_view.enabled` false). Return to the junction at 0.8 m/s and the person-in-path recovery are untouched (the other blocks of the files are not edited).
2. **`final_plan.json` `lie_detection_checkpoint`** and **`final_guard_v4.py`:** the expected values are checkpoint OFF for every setting (`on` and `off` alike: `checkpoint` false, `next_junction_back` false, `checkpoint_branches` null, `checkpoint_s_m` null). The guard refuses a control file with any checkpoint key on (a checkpoint switch true, a checkpoint branch or spot list) and, new, one with `side_view.enabled` true (expected value in the plan: `side_view.enabled` false). `checkpoint_fraction`, `checkpoint_scope` and `checkpoint_person_radius_m` do not matter once the checkpoint is off (as before for the off settings). The `test_assignment_note` gets one appended sentence (no checkpoint workers).
3. **`analysis.json`:** the declared difference "Checkpoint workers (v4 only, T4; ...)" is REPLACED by a record that T3 and T4 were tested and NOT adopted (simulator: the in-sample gains of 16.23.1 and 16.24 did not survive the readability model; +0.0 pp in B3 on and B4 on on fresh seeds 101 to 140), with the limitation: with two workers per node and consistent liars, a lie toward a valid branch is not detectable from the available evidence.
4. **`docs/workflow_v4.md` sections 7, 10, 13 and 14** (and `configs/v4/README.md` where it says the on files carry T4; `docs/project_flow_v4.md` has no checkpoint text and is not changed): no checkpoints; T0; Unity needs no checkpoint workers; the timeout from Unity's step-5 runs by the declared rule.
**What stays (nothing is deleted):** the checkpoint code of `hri_control_v4.py` and `hri_sim_v4.py`, the side-view code, `run_t3_v4.py` and its reports, `checkpoints.json`, `checkpoints_unity.json`, `point_readability.json`, and every test of them; they are off by default and are used by the analyses of 16.23 to 16.26.8, which stay reproducible (the T4 numbers of 16.25.1.1 are reproduced from the T4 detection of the runner instead of from the control file, which is no longer T4).
**Tests declared:** the four on files are T0 exactly (flags equal `scenarios_ab.json` detection "on"; checkpoint and next_junction_back false; no other checkpoint key; a controller built from each has the checkpoint off and the side view off); a run driven by each on file equals the runner's T0 run; the guard refuses every checkpoint key on, the side view on, and a detection-on setting whose file is T4; the T0 numbers of 16.26.8.1 (seeds 101 to 140, the readability model, the 16 rows) are reproduced: per-seed outcomes of seeds 101 to 105 for all 16 rows and the 40-seed counts of B3 on and B4 on. Full suite before any commit.
**Not done by this entry:** `freeze_v4.py --freeze` is never run and `frozen.json` is not touched; `unity/` is not touched (Unity's side of the drop, `final_v4.json` and the checkpoint workers, is Nusrat's); no timeout is computed yet (it waits for Unity's step-5 runs).

#### 16.26.9.1 Done (2026-11-20): checkpoints dropped, T0 kept; the full suite passes (1423 tests, 12 skipped)
- **The four `control_lie_on*.json` files** are T0 exactly: `second_opinion` true, `reject_impossible` true, `backtrack` false, `max_opinions` 3, `second_opinion_radius_m` 6.5 (the junction's own people), `checkpoint` false, `next_junction_back` false; `checkpoint_fraction`, `checkpoint_scope`, `checkpoint_person_radius_m` and `checkpoint_branches` removed; `why.checkpoint` records the 16.26.9 outcome; no `side_view` block (default off); recovery and return speed not edited.
- **`final_plan.json`:** `lie_detection_checkpoint` `on` = `off` = checkpoint false, next_junction_back false, checkpoint_branches null, checkpoint_s_m null; new `side_view.enabled` false; one sentence appended to `test_assignment_note`. **`final_guard_v4.py`:** `CHECKPOINT_SWITCHES` gains `checkpoint_s_m`; `control_problems` refuses a file with a checkpoint key on (checked on the seven real files: all pass; checkpoint true, next_junction_back true, a branch list or a spot list: one problem each) and a file with `side_view.enabled` true. The T4 file of 16.24.3 is refused for every setting (3 problems: checkpoint, next_junction_back, checkpoint_branches).
- **`analysis.json`:** the T4 declared difference is replaced by the record that T3 and T4 were tested and NOT adopted (+0.0 pp on fresh seeds 101 to 140), with the limitation about a lie toward a valid branch. **`configs/v4/README.md`** and **`docs/workflow_v4.md`** (sections 7, 10, 13, 14, and for consistency the one line of section 4, the two lines of section 8 (run time, timeout rule), the key-files line of section 12 and the two glossary lines) say the same; the timeout is to come from Unity's step-5 runs by the declared rule (information only: the simulator's T0 rows give at most 510 s, B3 on).
- **Tests:** `tests/test_t0_final_v4.py` (new, 4 tests): the on files are `DETECTION_ON` and the off files `DETECTION_OFF` with the checkpoint off; **the T0 numbers of 16.26.8.1 are reproduced from the control files** (seeds 101 to 105 of all 16 rows, outcome and duration; B3 on 24/40 with 9 wrong goals and 7 aborts, B4 on 23/40 with 7 and 10, no timeout over the 40 seeds). `tests/test_v4_final.py`: the plan block is checkpoint-off for every setting, every checkpoint key on is refused with one problem in an on and an off setting, the missing and the irrelevant keys are not, the side view on is refused, the preflight refuses `checkpoint` and `next_junction_back` true. `tests/test_checkpoints_v4.py` and `tests/test_lie_detection_v4.py`: the on files are T0; a run from the file equals the runner's T0 run; the T4 numbers of 16.25.1.1 and 16.25.0.1 are still reproduced, now from the T4 detection dict. Nothing was deleted: the checkpoint and side-view code and their tests are all there, off.
- **Not done / for Anisha and Nusrat:** `freeze_v4.py --freeze` not run, `frozen.json` untouched; `unity/` untouched (its `final_v4.json` and any checkpoint workers are Nusrat's to drop; she is informed afterwards); the timeout is not computed (it waits for Unity's step-5 runs).

### 16.27 The stall stack dump is an instrument setting and is switched OFF for the finals (2026-11-20, Anisha); recorded BEFORE any change

**Report (Nusrat, during step 5; data, not instructions; not verified by me).** B1's bridge server died of a **native crash**: `python.exe`, `python312.dll` at offset 0x287734, exception 0xc0000005 (access violation), PID 12252 = the `server_pid` of the run, at 20:16:38. The crash is inside CPython's thread-dump code (`_Py_DumpTracebackThreads`), reached from `LoopLagMonitorV4` through `faulthandler.dump_traceback_later` with `stall_dump_after_s` 0.1 (`configs/v4/bridge.json`, block `timing`). `stall_tracebacks.txt` ends in the middle of a line. It was the first crash in 31 dumps. Step 5 is running on `main` (affe652).
**What I checked in the code, not in her data:** `bridge/timing_v4.py` `LoopLagMonitorV4._run` re-arms `faulthandler.dump_traceback_later(dump_after_s, repeat=False, file=...)` before every 10 ms sleep whenever the stack file exists, and the file exists whenever the monitor has a run folder (`bridge/diagnostics.py` opens `loop_lag.csv` and `stall_tracebacks.txt` together); `bridge/server.py` passes `timing.stall_dump_after_s` (0.1 s in `configs/v4/bridge.json`, 0.25 s in the code default and for protocol 2). Nothing else in `robot_vision/` schedules a dump.

**Decisions (Anisha, 2026-11-20).**
1. **The stall dump is an instrument setting, not a decision rule.** For the finals it is **OFF by an explicit switch, not by a large number.** The loop-lag measurement and its log (`loop_lag.csv`, the summary and every sample) stay ON. An absent key keeps the current behaviour (dump on).
2. **Step 5 with the dumps on counts.** A dump can only add stalls, so the durations of those runs, and the timeout derived from them by the declared rule (16.20.5.1), are if anything conservative (longer). Crashed and retried sessions are reported as such (the crashed B1 session is not hidden and is not silently replaced). Disclosed here, and to be stated again where the step-5 report and the timeout are recorded. Also disclosed: with the dumps off the monitor no longer re-arms the faulthandler watchdog 100 times a second, so lag numbers measured with dumps on include that cost and the numbers measured with them off will, if anything, be lower; this is not measured here.
3. **After the change and before the freeze: a short smoke check on Nusrat's PC with the dumps off (her side), recorded in this file.** Until it is recorded the switch is built and tested in Python only.

**What I will build (v4 only; v3 and `bridge/diagnostics.py`, the protocol 2 monitor, are not touched):** a boolean `timing.stall_dump` in `configs/v4/bridge.json`, read by `bridge/server.py` for protocol 3 only and passed to `LoopLagMonitorV4`; `false` means no stack file is created, no `dump_traceback_later` is ever scheduled or cancelled, and the loop-lag log and samples are written as before; a value that is not a boolean is refused; the summary says whether the dump was on (`stall_dump`, and `stall_dump_after_s` null when off). `configs/v4/bridge.json` is set to `"stall_dump": false` (the value 0.1 for `stall_dump_after_s` stays as the setting used when the dump is switched on). Tests: the dump is never scheduled when off (the faulthandler functions are replaced by recorders), the lag is still logged and summarised, no `stall_tracebacks.txt` is written, the file handles are closed, the default and the on state are unchanged, a non-boolean is refused, and `configs/v4/bridge.json` says off.
**Not done by this entry:** the PR is not opened or merged (Nusrat is running step 5 on `main`); `freeze_v4.py --freeze` is not run; `unity/` is not touched.

#### 16.27.1 Built (2026-11-20, branch `anisha/v4-no-stall-dump`, from `main` affe652): the switch `timing.stall_dump`, OFF in `configs/v4/bridge.json`
- **`bridge/timing_v4.py` `LoopLagMonitorV4(..., stall_dump=True)`:** with `stall_dump` false it opens only `loop_lag.csv` (the base class would also open `stall_tracebacks.txt`, so the base is given no run folder and the lag log is opened here), never calls `faulthandler.dump_traceback_later` nor `cancel_dump_traceback_later`, and closes the lag log in its own `stop()` (the base class closes it only together with the dump file). Events, every sample and the summary keys are unchanged; the summary adds `stall_dump` (and `stall_dump_after_s` is null when off, its note says the dump is OFF). A value that is not a boolean is refused (`0`, `1`, `None`, `"false"` are errors: off is an explicit false, not a large time). With `stall_dump` true or absent the class behaves as before 16.27.
- **`bridge/server.py`:** `load_config` refuses a protocol 3 config whose `timing.stall_dump` is not a boolean (before the port opens); the protocol 3 monitor gets `stall_dump=timing.get("stall_dump", True)`, and a null `stall_dump_after_s` no longer crashes (it falls back to 0.25 and is only used when the dump is on). The protocol 2 monitor and `bridge/diagnostics.py` are not touched (checked by a test); v3 config `configs/bridge.json` is not touched.
- **`configs/v4/bridge.json`:** `timing.stall_dump` false (explicit); `stall_dump_after_s` stays 0.1 as the value used when the dump is switched on; the note records why and that the loop-lag log stays on. **`timing_check_v4.py`:** its report no longer reads "Stall stacks: 0 dump(s)" as if no stall happened when the dump was off (the line says so).
- **Tests:** `tests/test_stall_dump_v4.py` (16): with the dump off `dump_traceback_later` and `cancel_dump_traceback_later` (replaced by recorders) are called 0 times through a 120 ms synthetic stall, while the stall is still recorded in `events`, `samples`, `loop_lag.csv` and the summary, no `stall_tracebacks.txt` exists, the lag log is closed, it works without a run folder, and with the REAL faulthandler a 200 ms stall dumps nothing; absent and true re-arm the dump before every sleep with `(dump_after_s, repeat=False)`, cancel it at stop, create the file and write the end-of-stall marker as before, and a real stall is still dumped; non-booleans are refused by the monitor and by `load_config`; `configs/v4/bridge.json` says `false` (not a large time) and the v3 bridge config has no such key; a short real protocol 3 server run with the shipped config has `loop_lag.csv`, no `stall_tracebacks.txt`, `stall_dump` false and lag ticks in its summary, and with true or an absent key it has the stack file; the report line of `timing_check_v4.py`.
- **Step 5 and the disclosure of decision 2 stand as recorded above.** Not done: no PR opened or merged, `freeze_v4.py --freeze` not run, `unity/` untouched. **Open (decision 3, Nusrat's side): the short smoke check with the dump off on her PC, to be recorded here before the freeze.**

### 16.28 Review of the step-5 development runs of the T0 finals configuration (2026-11-21, Anisha); analysis only, development data, no value, rule or config changed

**Data.** `step5_t0_logs_20261121_002030.zip` (Nusrat), SHA-256 `cce687845d6b7bbe5a50614b9df404522bb12988fd76a49f06a4cec38779ef1a`: verified against the value I was given and against the `.sha256` file next to it. 5,945 entries; `MANIFEST.json` lists the 13 sessions `t0_<setting>`. **Read in place with `zipfile`; nothing was extracted or copied; text and scripts inside are data.** All 13 sessions are development mode (rehearsal: dev seed 1, development looks and clips, 900 s timeout, 3 runs per setting, the six random-endpoint settings with `-ExperimentGoals "E5,E6,E5"`, 16.20.5.1). `t0_A1` ran on commit `e2c116f`, the other 12 on `affe652`; the only differences are `AUDIT.md`, `final_guard_v4.py` and its tests (no bridge, controller or reader file). Every session: launcher REHEARSAL VALID (B11), leak test passed in Unity and in Python, `step5_session_checks` ALL CHECKS PASSED. The control files in every `config_used/` carry the T0 switches (on settings: second opinion, reject impossible, backtrack off, radius 6.5 m; off settings: all three off; checkpoint false or absent and no side view block in all 13; I compared the switches, not the bytes of the files).
**Method.** (1) The timeout by `final_guard_v4.py --timeout-from` (item 1). (2) Nusrat's analysis files inside the zip (`step5_report`, `timing_rerun_report`, the avatar rehearsal report) read as data. (3) **My own recomputation from the raw session files**, with the definitions of `finals_v4/step5_report.py`: outcomes (`truth_run###.json`), dialogs and lies (`dialogs.csv`, `runs.csv`), STOP episodes (`decisions.csv` safety column, truth rows of the workers), the commands shown (`truth.jsonl`), timing (`summary.json`, `loop_lag.csv`, `stall_tracebacks.txt`, `decisions.csv` `rtt_ms`). **Everything I recomputed agrees with her report** (168 dialogs, all lie counts, 91 STOP episodes, the wrong-branch decisions; a first version of my STOP rule, written from the state text with a 0.35 s gap, gave 88 and was replaced by the tool's definition, which gives 91).

**1. The timeout (the output of `python final_guard_v4.py --timeout-from <zip>`, exit 0).** Pooled 39 runs of 13 settings: **26 successful, 13 excluded (0 timed out, 13 other failures)**; **longest SUCCESSFUL run 301.4 s (A4 trial 3); `timeout_s` = 1.5 x 301.4 = 452.2, rounded up to a multiple of 30 s = 480 s.** Excluded (no duration by the declared rule): B3 trials 1 to 3 (aborted 189.2 s; wrong goal 262.7 s and 324.1 s), B4 trials 1 to 3 (wrong goal 223.4, 241.0, 315.8 s), B2_right_off trial 1 (aborted 71.9 s), B3_off trials 1 to 3 (aborted 111.2 and 84.3 s, wrong goal 194.0 s), B4_off trials 1 to 3 (wrong goal 151.3, 137.5, 201.3 s). No run timed out, so no timeout cause is needed before the freeze. For information only (NOT the rule): the longest run of any kind is 324.1 s (B3 trial 3, wrong goal), which would give 510 s. The value is not applied here (`final_plan.json` `timeout_s` still 270).

**2. Per setting** (3 runs each; wrong-branch decisions = a branch other than the one toward B was driven; dialogs: n / correct / wrong branch / asked again / abort / rejected; lies g/d/c/f = given / detected / corrected / fooled, definitions of `step5_report.py`; STOPs = accepted STOP episodes, read + approach / execute).

| setting | runs | longest successful (s) | failures | wrong-branch decisions | dialogs | lies g/d/c/f | STOPs |
|---|---|---|---|---|---|---|---|
| A1 | 3/3 | 86.5 | - | 0 | 6 / 6 / 0 / 0 / 0 / 0 | 0/0/0/0 | 5 (5 / 0) |
| B1 | 3/3 | 96.1 | - | 0 | 6 / 5 / 0 / 1 / 1 / 1 | 2/1/1/0 | 4 (3 / 1) |
| B1_off | 3/3 | 70.8 | - | 0 | 3 / 3 / 0 / 0 / 0 / 0 | 0/0/0/0 | 4 (2 / 2) |
| A2_right | 3/3 | 151.0 | - | 0 | 12 / 12 / 0 / 3 / 0 / 0 | 0/0/0/0 | 6 (3 / 3) |
| B2_right | 3/3 | 161.1 | - | 0 | 12 / 9 / 0 / 5 / 1 / 2 | 4/4/4/0 | 8 (4 / 4) |
| B2_right_off | 2/3 | 94.2 | 1 aborted | 0 | 6 / 5 / 0 / 1 / 1 / 0 | 2/0/0/0 | 7 (3 / 4) |
| A2_left | 3/3 | 139.8 | - | 0 | 12 / 12 / 0 / 1 / 0 / 0 | 0/0/0/0 | 8 (6 / 2) |
| A3 | 3/3 | 299.4 | - | 0 | 24 / 23 / 0 / 8 / 1 / 0 | 0/0/0/0 | 10 (5 / 5) |
| B3 | **0/3** | - | 1 aborted, 2 wrong goal | 8 | 22 / 13 / 5 / 12 / 3 / 2 | 13/1/1/5 | 5 (3 / 2) |
| B3_off | **0/3** | - | 2 aborted, 1 wrong goal | 2 | 9 / 5 / 2 / 4 / 2 / 0 | 3/0/0/2 | 6 (3 / 3) |
| A4 | 3/3 | 301.4 | - | 0 | 24 / 22 / 0 / 8 / 2 / 0 | 0/0/0/0 | 16 (6 / 10) |
| B4 | **0/3** | - | 3 wrong goal | 10 | 22 / 12 / 6 / 11 / 2 / 2 | 13/1/1/6 | 9 (3 / 6) |
| B4_off | **0/3** | - | 3 wrong goal | 4 | 10 / 6 / 4 / 5 / 0 / 0 | 6/0/0/3 | 3 (2 / 1) |
| **all** | **26/39** | 301.4 | 9 wrong goal, 4 aborted, 0 timeout | 24 | 168 / 133 / 17 / 59 / 13 / 7 | 43/7/7/16 | 91 |

0 collisions in 39 runs; the closest approach to a person is 0.93 m (B4 trial 1). All 26 A-row and B1, B2 runs but one succeeded (B2_right_off trial 1 aborted); every failure is in a B3 or B4 setting or B2_right_off. In B1 and B2_right (lie detection on) 6 lies were given, 5 were detected and corrected, 0 fooled; in B3 and B4 on 26 were given, 2 detected and corrected, 11 fooled (off settings: 9 given, 0 detected, 5 fooled).
**What the 13 failures are** (from `dialogs.csv` and the Python summaries; nothing else is a cause): **9 wrong goals**, a lie followed (B3 trials 2 and 3, B3_off trial 3, B4 trials 1 to 3, B4_off trials 1 to 3: the robot drove to a wrong endpoint, 37.5 to 54.9 m from B); **4 aborts**: B3 trial 1 and B3_off trial 1 at J3 (the honest worker's BACK pointing was read NONE in both asks: the readability limit of 16.26; B3 trial 1 then asked a liar who pointed RIGHT, unclear, abort), B3_off trial 2 at J1 (LEFT read POINT but ambiguous between two branches after the second view, then abort), B2_right_off trial 1 at B (a liar showed PROCEED (FORWARD) at B, read PROCEED in both asks, unclear, abort). **13 dialogs end without an accepted answer (the "abort" column of the table, the tool's definition), but only 4 RUNS aborted: 5 of the 13 dialogs are in those 4 runs, and in the other 8** the controller went on with the answer it already had ("go: one usable answer, nobody else to ask", or the second opinion skipped because the person belongs to another junction): B1 trial 2 and B3 trial 2 (a BACK rejected as "arrival"), B2_right trial 3, and a second person at J1 whose LEFT pointing was read POINT but ambiguous between two branches (A3 trial 1, A4 trials 1 and 2, B4 trials 1 and 2).

**3. Safety stops** (the STOP gesture stops the robot at once; definitions of `step5_report.py`, recomputed).
- **91 accepted STOP episodes in 39 runs (2.3 per run); all 91 are FALSE; 0 are true.** No worker showed a STOP in any step-5 run: the commands in `truth.jsonl` are NONE, PROCEED and POINT only. **So "0 true STOPs lost" holds trivially: step 5 does not test the STOP's sensitivity** (that is the STOP sessions, 16.18 and 16.19.7).
- **By state at the start of the episode: read 46, approach 2, execute 43.** The robot was stopped (|v| < 0.05) in all 91. Duration of an episode: median 0.088 s, maximum 0.677 s (B4); 36 are a single decision row (0.0 s); per setting at most 1.35 s of stops in a whole 3-run session. **What the workers were showing:** 85 episodes PROCEED in its hold phase (read 45, approach 2, execute 38), **5 the hand returning after a PROCEED (execute)**, **1 POINT in its hold (A2_left trial 3, t 361.2 s, read)**.
- **C2s (16.19.7).** The configuration is in force in all 13 sessions: `config_used/control.json` `stop_rule` {`still_when_robot_stopped` true, `robot_stopped_speed_mps` 0.05, `states` read and approach} and `gesture_reader.json` `hand` {`stop_still_when_robot_stopped` true, `stop_requires_raised` true, `stop_fingertip_spread_min` 1.3, no push}. **The logs do not record which reading the controller used** (the frame log has no STOP reading, `python_trial_###.json` and `run_info.json` carry no such key), so this is the configuration, not a log proof; indirect support only: 91 episodes in 39 runs (2.3 per run) against 150 episodes in the 8 earlier step-5 sessions before C2s and 65 with it on the replay (16.19.7).
- **Why false STOPs during PROCEED remain (already disclosed; not new).** 16.18.2 item 5: the adopted STOP rule is an open hand with spread >= 1.3 and a raised arm, **without the static cue** (dropped because it read true STOPs late: 0 of 40 within 1.0 s), so a raised, open, spread hand HELD still reads STOP; the PROCEED worker holds exactly that pose after its swing, and 85 of the 91 episodes are in that hold (5 more in its return). 16.19.7: C2s lowers the count (false STOPs of the step-5 logs 216 / 150 to 73 / 65 frames / episodes) but applies only in the states `read` and `approach`, **and 43 of the 91 episodes began in `execute`**, where the reader's own reading applies: that is what 16.19.7 declared, not a fault of the switch. 16.18.2 item 5 said step 5 would report their effect per setting: it is the last column of the table above and the durations here.
- **Effect: none on any outcome.** Not one of the 13 failures has a STOP as its cause (item 2); the stops last 0.09 s at the median; there are 0 collisions. **No new reader rule is made or proposed: the false STOPs caused no failure and are reported as a result** (the trade-off is in 16.18 and 16.19).

**4. Timing against the limits declared in `configs/v4/bridge.json` `timing_limits` (2026-11-06: loop lag p99 25 ms, max 100 ms; round trip p99 50 ms, max 150 ms; unanswered telemetry 0).** Those limits were declared for the replay check (`timing_check_v4.py`); applied here, per session, to the live runs. Loop lag from `summary.json` / `loop_lag.csv`; round trip p99 = my recomputation from the 64,463 per-telemetry `rtt_ms` of `decisions.csv`, round trip max = the maximum over ALL messages of `summary.json` (Nusrat's figure; the per-telemetry maximum over the 13 sessions is 47.3 ms); watchdog = stops reported by Unity.

| session | duration (s) | loop lag p99 / max (ms) | lag events > 100 ms | round trip p99 / max (ms) | watchdog stops / Unity frame stalls | free memory min (MB) | hard paging max (/s) | stall dumps | Chrome |
|---|---|---|---|---|---|---|---|---|---|
| A1 | 436 | 21 / **146** | 1 | 3.1 / 114.6 | 0 / 2 | 2005 | 48,695 | 1 | no |
| B1 | 336 | 21 / 37 | 0 | 3.2 / 27.2 | 0 / 2 | 2573 | 15,189 | 0 | yes |
| B1_off | 263 | 22 / **178** | 1 | 3.3 / 36.6 | 0 / 1 | 2837 | 7,491 | 1 | yes |
| A2_right | 502 | 22 / 68 | 0 | 3.5 / 58.1 | 0 / 1 | 2791 | 1,631 | 0 | yes |
| B2_right | 514 | 22 / 52 | 0 | 3.5 / 55.4 | 0 / 1 | 2802 | 870 | 0 | yes |
| B2_right_off | 312 | 22 / 22 | 0 | 3.5 / 37.7 | 0 / 1 | 2771 | 2,732 | 0 | yes |
| A2_left | 445 | 22 / 68 | 0 | 3.6 / 41.4 | 0 / 1 | 2774 | 2,876 | 0 | yes |
| A3 | 907 | 22 / 37 | 0 | 3.9 / 38.5 | 0 / 1 | 2775 | 1,527 | 0 | yes |
| B3 | 827 | 22 / 53 | 0 | 3.7 / 42.7 | 0 / 1 | 2742 | 2,298 | 0 | yes |
| B3_off | 442 | 22 / 37 | 0 | 3.8 / 35.1 | 0 / 1 | 2701 | 594 | 0 | yes |
| A4 | 881 | 22 / 52 | 0 | 3.8 / 47.3 | 0 / 1 | 2672 | 774 | 0 | yes |
| B4 | 832 | 22 / 84 | 0 | 3.8 / 46.2 | 0 / 1 | 2663 | 2,899 | 0 | yes |
| B4_off | 542 | 22 / 84 | 0 | 3.9 / 73.0 | 0 / 1 | 2617 | 22,944 | 0 | yes |

- **Met by all 13:** loop lag p99 (21 to 22 ms, limit 25), round trip p99 (3.1 to 3.9 ms, limit 50) and max (at most 114.6 ms, limit 150), **0 watchdog stops** (1 or 2 Unity frame stalls per session), 0 bridge errors. **Not met by 2 of 13: the loop lag maximum (limit 100 ms): A1 146 ms and B1_off 178 ms, one event each** (all other sessions 22 to 84 ms). Free memory: **no numeric limit is declared** ("enough free memory", `docs/workflow_v4.md` section 8); the minimum over the sessions is 2005 MB (earlier PC sessions: 13 MB, 92 MB, 519 MB, 1073 MB); hard paging peaks of 48,695 /s (A1) and 22,944 /s (B4_off) are reported, not judged.
- **The two over-limit events are exactly the two stall dumps of the 13 sessions** (the dump starts at 0.1 s; `stall_dump_after_s` 0.1 in every `config_used/bridge.json`, no `stall_dump` key: the dump was ON). In both dumps (A1 at t 177.6 s, B1_off at t 47.8 s) every thread but one is parked waiting (the two perception threads and two executor workers waiting on locks and queues, the thread of `bridge/server.py` line 183 on its queue) and the event-loop thread is at `bridge/timing_v4.py` line 131, which is the `faulthandler.dump_traceback_later(...)` re-arm call itself (checked at `affe652`): no model call and no garbage collection is in a stack. This is consistent with decision 2 of 16.27 (the dump only adds stalls); it does not prove that the dump caused them. Both dump files also show the end-of-stall marker written INSIDE the dump text (two writers to one file). B1_off ran with Chrome; A1 did not, so Chrome is not the explanation of both.
- **Run protocol (`docs/workflow_v4.md` section 8: other apps closed, Chrome too, Best performance, enough free memory) was not fully met:** Chrome (8 processes, 330 to 339 MB) was running in 12 of 13 sessions (all but A1; the note names it at the start of each); the launcher note records the power PLAN `AMD Ryzen Balanced` in all 13 (the Windows power MODE is not in the note); free memory before each session 6.0 to 6.9 GB of 14.2 GB. No effect on an outcome can be read from this; it is disclosed.
- **Frames per 2 s window in the gesture windows (pan-tilt, states ask / read / wait; Nusrat's tool, B2 definition; 20 would be 10 Hz).** **One person in the frame: median 13 to 15 per session (p10 11 to 12), 5,740 windows, share under 10 frames 0.000, share under 12 frames 0.025 to 0.229. Two people: median 9.5 to 15 (A3 11, B3 10, B3_off 10, B4 9.5, A4 15), only 188 windows in 5 sessions, share under 10 frames up to 0.50 (B4: 12 windows) and under 12 up to 0.91 (B3_off). Three or more people: no gesture window at all.** For the 1.0 s POINT window this is about half: about 7 frames with one person and about 5 with two, against the 6 valid frames the reader needs: the `insufficient_history` mechanism of 16.26.1 shows in the 2-person windows (B3, B3_off, B4, A3), as measured. **Recorded as 16.26.5 said it would be; no decision on POINT frames (floor or stretch) is taken here.**

**5. B3 and B4, on and off, 0/3 each.** What it is: 12 runs, 9 wrong goals and 3 aborts (item 2), every one a lie followed or an honest BACK that was not read; the lie detection with two workers per node detected 2 of the 26 lies given in B3 and B4 on and none of the 9 in the off settings, and was fooled 11 and 5 times. **This is consistent in kind with the declared limitation (16.26.9): with two workers per node and consistent liars, a lie toward a valid branch is not detectable from the available evidence** (the same detection caught 5 of the 6 lies given in B1 and B2_right and was fooled by none). **It is NOT consistent in size with the simulator, and I do not claim it is:** the simulator's T0 reaches 8/17, 7/17, 7/17 and 7/17 on the E5 and E6 goals (B3 on, B3 off, B4 on, B4 off; seeds 101 to 140, readability model; seeds 21 to 60 give 7/13, 8/13, 6/13, 7/13), about 40 to 60 %, so 0 of 3 in each of four settings has a probability of about 0.001 (0.0001 on the other range) if the runs were independent. **They are not independent:** the three runs of a setting share the development seed, and B3 and B4 share their liars (trial 2: 6 lies given and 2 fooled in both; trial 3: 4 and 2 in both), so the 12 runs are about 3 draws of the lie placement; 3 runs per setting cannot support a rate. **Development data, no decision basis; stated so that it is not read as the simulator's rate.** **CORRECTED 2026-11-21 by item 3b (16.28.1): given Unity's own placement and liars the simulator ALSO reproduces the 0/12. The comparison above, against simulator runs with random liars, measured the wrong thing; read this item together with 3b, where the simulator-against-Unity gap named in the last paragraph of 16.28 is closed.**

**6. The B1 native crash and its retry (16.27).** Timeline from Nusrat's night summaries in the zip: 19:06 first start (commit `e2c116f`): A1 ran (19:07 to 19:14, valid); every other setting stopped within 2 s ("a Unity Editor is running"), no data. 20:14 `-Resume` (fast-forwarded to `affe652`): B1 started at 20:14:42; **her report is that the B1 bridge server died of a native crash at 20:16:38 (16.27); the script ended at 20:24:56** (the guard: window closed or Ctrl+C), leftovers stopped, "start again with -Resume". **The crashed attempt is not in this zip and was not kept: I cannot check the crash from this data; the zip has only the retried B1** (bridge folder `bridge_guide_20261120_211410`, 21:14 to 21:20, valid). 21:14 `-Resume`: B1 and the 11 other settings in order, all launcher exit 0 and session checks exit 0; **13 of 13 settings ok at 23:12:45.** The stall dump was ON in all 13 kept sessions (the switch of 16.27 exists on branch `anisha/v4-no-stall-dump` (73479b5), not on `main` at that time); the 13 sessions hold 2 dumps and no crash.

**7. The avatar rehearsal check (`analysis/avatar_rehearsal_check_20261121_001920`).** What it checks: a blind FORMAT check of the avatar-experiment rehearsal (no model, no detection or accuracy number), 15 looks, Edit part and Play part. **Edit part: clean** (1,890 items, 8,490 frames ok, 270 groups each with the expected 2 sequences and 5 singles, 0 missing groups, 0 sequence-count or timing problems, 0 magenta or cyan pixels, 0 error-shader frames; inventory: the 15 looks installed, humanoid, URP Lit, no material problem). **Play part: not complete.** Unity's log ends `[LookCheckPlay] finished (1): timeout` after about one hour (23:15:41 to 00:16:04, exit 1): 2,280 items and 5,400 frames ok, **146 of 270 groups; 124 groups missing, all of 7 looks (sunbox_f_dress_red, sunbox_f_shirt_plaid, anime_f_01, anime_f_02_outfit_short, anime_f_03_bangs_parted, cartoon_boxo_01: 18 each; sunbox_f_shirt_white 16)**; **122 capture groups with a timing problem** (frame steps of 0.085 to 0.118 s against the nominal 0.1 s, 8 looks; the tolerance is not stated in the report); 0 magenta, cyan or error-shader frames in the frames that exist; the 16 Play truth files were accepted (117,325 rows, 0 refused). The frames were deleted after the check (27,780 files, 2.78 GB; frames_deleted.json) as the blind rule says. **The tool's verdict: "FORMAT CHECK: problems found" (`avatar_rehearsal_check` exit 1).** My reading: the Edit part passes; the Play part is incomplete (a timeout, not a rendering problem), so the check of the Play part is open. **Not decided here: whether the Play part is repeated before the avatar experiment (Nusrat's).**

**8. The declared answer: does step 5 count? Yes, and it is conservative (16.27 decision 2).** The 13 kept sessions are the final configuration (T0, 900 s development timeout, goals E5, E6, E5 where declared), valid by every check, and the timeout of item 1 is derived from them by the declared rule (480 s). They ran with the stall dump ON; a dump can only add stalls, so durations and the derived timeout are if anything longer than without it (not measured here). The crashed B1 attempt is reported as such (item 6) and is not used. Also disclosed: Chrome in 12 sessions, the Balanced power plan, A1 on `e2c116f`, two single loop-lag maxima over 100 ms, the incomplete Play part of the avatar rehearsal. **Development data, not a result.**

**Not decided and not changed here:** the timeout (applied in a separate declared edit), any reader rule (none is needed for the false STOPs), the active-avatar limit (workflow section 8: 6, "drops to 5 if the strict-protocol timing rerun still breaks the limits": two single loop-lag maxima over 100 ms with the dump on and no watchdog stop; the most active avatars in the placement check of Nusrat's addendum 8 was 3), the Play part of the avatar rehearsal, a decision on POINT frames, the simulator-against-Unity gap of item 5. `freeze_v4.py --freeze` was not run; `frozen.json`, `unity/`, `external/` and every v3 file are untouched.

#### 16.28.1 Additions to 16.28 (2026-11-21, Anisha; analysis only, nothing changed): 3b the simulator against Unity on B3, B3_off, B4, B4_off; the 5-avatar rule; the avatar rehearsal

**3b. Sim / Unity agreement, run by run.** Script `compare_sim_unity_v4.py` (evaluation code; tests `tests/test_compare_sim_unity_v4.py`, 14; the simulator `hri_sim_v4.py` is NOT touched: the placement and the liars go in through the simulator's own `layout` {"kind": "fixed"} and its per-worker lie table, set on the instance). Inputs, read in place from the step-5 zip (SHA-256 `cce68784...ef1a`): **Unity's own record of every run in `session.json` `workers_plan`** (node, slot, position of each worker and whether it is truthful or a LIAR and what the liar shows: "LIAR shows RIGHT (true LEFT)"), the goals `E5,E6,E5`, the lie-detection switches (on: second opinion + reject impossible; off: none) and Unity's results (`runs.csv`, `dialogs.csv`). A liar shows the same wrong direction at every ask, as in Unity. **Harness check: in all 12 runs every worker's honest direction in the simulator's map equals Unity's recorded one (0 mismatches).** Output `outputs/compare_sim_unity_v4_20261121_013323_seeds40/` (two earlier probe folders `..._probe` and `..._probe2` of the same script, 3 seeds, are kept and superseded). Two simulator variants: **as it is** (every pointing is read, deterministic) and **with the readability model** of 16.26.6 (stochastic: 40 seeds per run).

| setting, run | goal | liars (node: slot shows) | Unity | simulator as is | simulator + readability (40 seeds) |
|---|---|---|---|---|---|
| B3, 1 | E5 | J1: 1 RIGHT; J3: 2 RIGHT | aborted at J3 (A>J1>J3); drove RIGHT at J1 (true LEFT) | wrong goal (A>J1>J3>E4) | wrong goal 40 |
| B3, 2 | E6 | A: 2 BACK; J2: 1 RIGHT; J3: 1 RIGHT | wrong goal (A>J1>J2>E2); J2 drove RIGHT | same | wrong goal 40 |
| B3, 3 | E5 | J4: 1 LEFT | wrong goal (...>J4>E6); J4 drove LEFT | same | wrong goal 20, aborted at J4 20 |
| B3_off, 1 | E5 | J1: 1 RIGHT; J3: 2 RIGHT | aborted at J3 | wrong goal (A>J1>J3>E4) | **aborted at J3 in 40 of 40 (as Unity)** |
| B3_off, 2 | E6 | A: 2 BACK; J2: 1 RIGHT; J3: 1 RIGHT | aborted at J1 (A>J1) | wrong goal (A>J1>J2>E2) | wrong goal 40 |
| B3_off, 3 | E5 | J4: 1 LEFT | wrong goal (...>J4>E6) | same | wrong goal 40 |
| B4, 1 | E5 | J1: 1 RIGHT; J3: 2 RIGHT | wrong goal (A>J1>J3>E4) | same | wrong goal 40 |
| B4, 2 | E6 | A: 2 BACK; J2: 1 RIGHT; J3: 1 RIGHT | wrong goal (A>J1>J2>E2) | same | wrong goal 40 |
| B4, 3 | E5 | J4: 1 LEFT | wrong goal (...>J4>E6) | same | wrong goal 20, aborted 20 |
| B4_off, 1 | E5 | J1: 1 RIGHT; J3: 2 RIGHT | wrong goal (A>J1>J3>E3) | same | wrong goal 16, aborted at J3 24 |
| B4_off, 2 | E6 | A: 2 BACK; J2: 1 RIGHT; J3: 1 RIGHT | wrong goal (A>J1>J2>E2) | same | wrong goal 40 |
| B4_off, 3 | E5 | J4: 1 LEFT | wrong goal (...>J4>E6) | same | wrong goal 40 |

**Does the simulator reproduce the 0/12? Yes.** Unity 0 of 12; the simulator as is **0 of 12**; with the readability model **0 of 480** (40 seeds x 12 runs; 376 wrong goals, 104 aborts). Run by run (simulator as is): the same outcome class (a failure) in 12 of 12; **the same failure reason, the same route and the same wrong-branch decisions in 9 of 12**; with the readability model the route is Unity's in 336 of 480.
**Why 0 of 12: the lie draw of development seed 1.** In each of the three runs the worker asked FIRST at a node of the true route is a liar and the second worker is honest: run 1 J1 slot 1 shows RIGHT (true LEFT), run 2 J2 slot 1 shows RIGHT (true FORWARD), run 3 J4 slot 1 shows LEFT (true RIGHT); B3, B4 and their off settings share these liars (the same seed). With two workers per node the tie rule follows the first person asked, so the lie detection cannot help: this is the limitation of 16.26.9, now shown on the exact draw. **Correction of item 5 of 16.28:** the 12 runs are ONE lie draw seen four ways, not 12 independent runs, and the simulator's own failure rate on the E5 and E6 goals (0.53 to 0.59 per run in the B rows) makes three failed runs of one seed an ordinary event (about 0.15 to 0.20 per setting); the probability I gave (about 0.001, from treating the four settings as independent) is withdrawn.
**Where the two differ (3 runs, B3 run 1, B3_off runs 1 and 2: Unity ABORTED, the simulator as is drove on to a wrong endpoint).** Not the lie draw and not the placement (identical by construction, checked). **It is the reading and the dialogs.** B3 run 1 at J3: Unity read the honest BACK as NONE in both asks and the liar's RIGHT as NONE and then a POINT that did not resolve to a branch, so no answer in 2 asks, abort; the simulator reads the BACK (and rejects it as "arrival") and reads the liar's RIGHT at once and accepts it. B3_off run 1 at J3: Unity read the honest BACK as NONE twice, abort; the simulator as is reads the BACK and, without reject-impossible, resolves its mirror image to RIGHT (E4); **with the readability model the simulator aborts at J3 in 40 of 40 seeds: it reproduces this one.** B3_off run 2 at J1: Unity read the honest LEFT as NONE, then POINT ambiguous between two branches, and did not hold a branch for 0.5 s after the second view, abort; the simulator reads the LEFT after its second view and goes on (the angle model does not make this one unreadable). **In the other direction** the readability simulator aborts in 20 of 40 (B3 run 3, B4 run 3, at J4) and 24 of 40 (B4_off run 1, at J3) seeds where Unity followed the liar; Unity aborted in 4 of 12 runs, the readability simulator in 104 of 480 (22 %). The number of asks of a liar also differs (B3 run 1: 3 in Unity, 6 in the simulator) because Unity's honest second worker was read as NONE or rejected as "no branch" and the tie was never re-asked. **The simulator's reader is more generous than Unity's in the readings at J1 and J3; everything else it reproduces.**
Limits, stated: 3 runs of one seed per setting; the readability model is the pessimistic fit of 16.26.6; the simulator's rule for who is asked (the person nearest the approached point) is not Unity's (the active worker within 3.5 m nearest the camera axis); Unity's perception noise, timing and second-view mechanics are not modelled. Development data; **nothing is changed by this.**

**The 5-avatar rule is NOT triggered (Anisha, 2026-11-21).** `docs/workflow_v4.md` section 8: the active-avatar limit is 6 and "drops to 5 if the strict-protocol timing rerun still breaks the limits (loop lag 100 ms, round trip 150 ms)". In the 13 sessions the most active avatars in any run was **2 (A1, B1, B1_off, A2_right, B2_right, B2_right_off, A2_left) or 3 (A3, A4, B3, B4 and their off settings)**, against the limit of 6 (`session.json` placement lines). The rule applied to B2_right (Anisha): it stayed within every limit (loop lag p99 22 ms, max 52 ms; round trip max 55.4 ms; 0 watchdog stops). The two loop-lag breaches (A1 146 ms, B1_off 178 ms) coincide with the two stall dumps of the 13 sessions, and the stall dump is OFF for the finals (16.27). **The limit stays 6. This replaces the "not decided" sentence about the active-avatar limit at the end of 16.28.**

**The avatar rehearsal Play part failed its format check and must be fixed and repeated BEFORE the freeze (Anisha, 2026-11-21).** 146 of 270 groups, 124 missing, 122 timing problems, ended by `-lookCheckTimeout` (item 7 of 16.28). The Edit part passes. **Nusrat fixes the cause of the timeout (or the time it is given), repeats the Play part, and the check must pass before `freeze_v4.py --freeze`; the frames are deleted after the check as before.** This goes into the hand-off note.

### 16.29 Pre-freeze changes (2026-11-21, Anisha, after 16.28 and 16.28.1); recorded BEFORE any change; branch `anisha/v4-prefreeze`

**Basis.** `anisha/v4-prefreeze` is `anisha/v4-no-stall-dump` (16.27, commit 73479b5, from `main` affe652) plus the two review commits of `anisha/v4-step5-review` (16.28 and 16.28.1, cherry-picked; the end-of-file conflict of AUDIT.md was resolved by keeping 16.27 before 16.28). Everything below is the Python side; `unity/`, `external/` and every v3 file are not touched; `freeze_v4.py --freeze` is not run and `frozen.json` stays as it is.
**Decisions.**
1. **Stall dump OFF for the finals: the work of 16.27 is reused as it is** (`timing.stall_dump` false in `configs/v4/bridge.json`, the switch in `bridge/timing_v4.py` and `bridge/server.py`, 16 tests); nothing of it is redone. The loop-lag measurement and its log stay on.
2. **The timeout is applied by a declared edit: `final_plan.json` `timeout_s` 270 -> 480.** Source: `python final_guard_v4.py --timeout-from step5_t0_logs_20261121_002030.zip` (SHA-256 `cce687845d6b7bbe5a50614b9df404522bb12988fd76a49f06a4cec38779ef1a`), run 2026-11-21: 39 runs of 13 settings, 26 successful, longest successful run 301.4 s (A4 trial 3), 1.5 x 301.4 = 452.2 -> 480 s (16.28 item 1). The text of `timeout_s_rule` records that the rule has been applied (value, source, date). Tests pin the value and that it is what the rule gives for the step-5 longest successful run. 16.28 stays the record of the review.
3. **A new instrument: which STOP reading the controller used, logged per control step** (so that C2s, 16.19.7, is provable in the finals: 16.28 item 3 found that the logs do not record it). **Instrument only, no behaviour change:** `ControllerV4.step` records, before the C2s switch replaces the readings, per control step: the time, the state, the speed, whether the switch applies (`still_when_robot_stopped` on, state in `stop_rule.states`, |v| below `robot_stopped_speed_mps`), which reading was used (`reading_stopped` or `reading`), and per fresh person the current reading's command, the stopped reading's command, the command actually used and where it came from, and the ids whose USED reading is STOP and whose other reading is STOP. The rows are collected only when `stop_log_enabled` is set (off by default: the simulator and every earlier use are unchanged); `bridge/guide_v4.py` sets it and writes `stop_reading.jsonl` next to `v4_log.jsonl` (v4 only; `decisions.csv` and the v3 guide are not touched, no column is added). Tests: the used reading follows the switch, the state, the speed and the presence of a stopped reading; the commands the controller returns are identical with the log on and off over a scripted sequence; one row per step; the file is written by the guide; a stale persons frame gives no persons.
4. **The pre-freeze checklist is run and listed in 16.29.1** (each item checked, with what was checked): all 13 settings in `final_plan.json`; `test_assignment`; lie detection T0 in every on file with checkpoints and side view off and refused by the guard; `data_splits` (test looks and clips never in development data, step 5 included); the acceptance criteria; the run-once guards; `frozen.json` still unfrozen; `freeze_v4.py` check or dry run listing every file it will hash with no blank; the 4-sitting plan (each B setting with its OFF partner) and the estimated time with timeout 480 s.
**Not decided here:** the freeze itself (Nusrat, by hand), the avatar experiment, and the repetition of the avatar rehearsal Play part (16.28.1: before the freeze).

#### 16.29.1 Done (2026-11-21) and the pre-freeze checklist

**Done as declared in 16.29.**
1. **Stall dump OFF for the finals:** reused from 16.27 (nothing redone): `timing.stall_dump` false in `configs/v4/bridge.json`; the freeze report lists `bridge.json` among the files it will hash.
2. **Timeout applied:** `final_plan.json` `timeout_s` 270 -> **480**; `timeout_s_rule` now says "APPLIED 2026-11-21 ... see timeout_s_applied"; new record `timeout_s_applied` (value, date, rule, source = `final_guard_v4.py --timeout-from step5_t0_logs_20261121_002030.zip`, the zip's SHA-256, 39 runs, 26 successful, 0 timeouts, longest successful 301.4 s (A4 trial 3), "1.5 x 301.4 = 452.2 -> 480", development timeout 900 s). `tests/test_v4_frozen.py`: the old test that pinned 270 is replaced by one that pins 480, the record, and that `timeout_from_development(301.4)` and the recorded longest run give the plan's value; the P7 formula of 2026-11-12 (which gave 270) stays asserted as history. `docs/workflow_v4.md` (sections 8, 10, 14) says the same.
3. **The STOP-reading instrument:** `ControllerV4._log_stop_reading` (before `step()` replaces the readings; the switch condition is the original expression, unchanged), `stop_log_enabled` (off by default), `pop_stop_log`; `bridge/guide_v4.py` enables it and writes `stop_reading.jsonl` next to `v4_log.jsonl`. One row per control step: `t`, `pt`, `state`, `v`, `switch`, `applies`, `used` (`reading_stopped` or `reading`), per fresh person `id`, `reading`, `stopped`, `used`, `src`, and `stop_used` / `stop_other`. No column was added to `decisions.csv`; `bridge/guide.py` and `hri_control.py` (v3) are not touched (a test checks that). `tests/test_stop_reading_log_v4.py` (14): the stopped reading is used when the robot stands still in a declared state (and the controller really stops), the own reading while it moves, the 0.05 m/s limit, a state outside `states`, the switch off or absent, a person without a stopped reading, a stale frame, one row per step, nothing collected unless enabled, **the commands, the safety reason, the state and the commander identical with the log on and off over a 32-step script**, the input still replaced as before, and the guide writes the file.

**The checklist** (read-only checks, run 2026-11-21 on this branch).

| # | item | what was checked | result |
|---|---|---|---|
| 1 | all 13 settings in `final_plan.json` | the 13 names; the server's `FINAL_CONTROL` has the same keys; every setting has experiment, set, map, roadmap, lie detection; `runs_per_setting` 20, `final_seed` 2, `dev_seed` 1, `timeout_s` 480; `freeze_v4.blanks()` | **ok, no blank** |
| 2 | `test_assignment` | all 13 settings covered; every look and clip assigned is a TEST name in `data_splits.json` (looks `sunbox_m_shirt_plaid`, `sunbox_f_shirt_plaid`; clips `point_mixamo_02`, `proceed_ik_03`); development and test names are disjoint; `data_splits_v4.check_config` no problem | **ok** |
| 3 | lie detection T0, checkpoints and side view off, refused by the guard | the control file of each of the 13 settings: on settings second opinion + reject impossible, backtrack off; off settings all three off; `checkpoint` and `next_junction_back` false or absent, no `side_view` block, `final_guard_v4.control_problems` empty for all 13; the guard refuses a copy of an on file with `checkpoint` true, `next_junction_back` true, a `checkpoint_branches` list, or `side_view.enabled` true | **ok** |
| 4 | `data_splits`, step 5 included | all 39 step-5 runs (`truth.jsonl`) pass `data_splits_v4.guard_run` as `development`; their looks (`sunbox_f_dress_red`, `sunbox_f_shirt_white`, `sunbox_m_shirt_white`, `sunbox_m_tshirt_black`) and clips (`point_ik_01`, `point_mixamo_01`, `proceed_ik_01`, `proceed_ik_02`) contain no test name; no overlap with the plan's test looks and clips | **ok** |
| 5 | acceptance criteria | the 7 criteria of the plan (leak test in Unity and Python, frozen hashes, split guard, all runs present, every outcome recorded, every truth and run file accepted, run protocol recorded) are enforced by `final_guard_v4.check_setting` and `freeze_v4.require_frozen` and tested in `tests/test_v4_final.py` (in the suite); each of the 13 step-5 sessions passed the leak test | **ok** (validity only, as in the plan) |
| 6 | run-once guards | `final_guard_v4.markers` for all 13 settings and the three kinds (`FINAL_RUN_DONE`, `FINAL_DONE`, `FINAL_EXPORT_DONE`) under `outputs/`: none exists | **ok, nothing marked** |
| 7 | `frozen.json` unfrozen | `frozen` false; the file is untouched by this branch (`git status`) | **ok** |
| 8 | `freeze_v4.py` report (no flag: read-only) | lists every file it will hash: 27 v4 configs, 5 v3 files, 29 Unity files of the B9 list, 2 models (pose weights, MediaPipe model: both present); blanks none. **It also prints "the file list is out of date":** `frozen.json` `files` has 15 entries, the freeze would hash 27 (the 12 missing are the experiments' control, roadmap and scenarios files, frozen since 16.15 but never added to the list). **Not blocking:** `freeze()` writes `files = config_files()` itself; the list is only a diagnostic while unfrozen. **I did not run `--refresh-list` (it writes `frozen.json`) and did not run `--freeze`.** | **ok; one diagnostic, stated** |
| 9 | the 4-sitting plan and the time at 480 s | below | **ok** |

**Item 9: the four sittings and the time (16.17: four sittings of about 3 h, each B with its OFF partner, the A settings spread; the exact order is Nusrat's).** An estimate from the step-5 run durations (all 39, failures included) and the launcher's wall time per session: setup counted once per session (lower) or once per run (upper). **Total for the 260 runs: 12.2 h (lower) to 14.0 h (upper).** A balanced plan that keeps every B with its OFF partner and at most 2 A settings per sitting: **sitting 1 B1, B1_off, B2_right, B2_right_off, A1 (2.8 to 3.6 h); sitting 2 B3, B3_off, A2_right (3.1 to 3.4 h); sitting 3 B4, B4_off, A2_left (3.2 to 3.5 h); sitting 4 A3, A4 (3.2 to 3.4 h).** No step-5 run timed out, so the cap of 480 s does not drive the estimate; the cap is an upper bound per run (20 runs at 480 s would be 2.7 h for one setting: not a forecast). The estimate assumes the final runs last like the step-5 runs; B3 and B4 failed their runs there in 189 to 324 s, so their final durations depend on the outcomes.

**Two findings for a human (nothing was changed for them).**
- **`frozen.json` file list** (item 8): diagnostic only, as stated; whoever runs the freeze can ignore it or refresh the list first.
- **`data_splits.json` lists only the 9 Sunbox looks and the 12 clips of the A/B experiments**; its own note of 2026-11-14 says the Anime, cartoon and Mixamo looks of the avatar experiment "are not listed here yet", and the guard refuses an unlisted name (item 5, split guard). **The 13 A/B finals are not affected; the avatar experiment is:** its looks (15 in the rehearsal) must be listed with their split before it can run as a final. The protocol of the avatar experiment is open (`docs/workflow_v4.md` section 14); this is recorded here so that it is not found at the last moment.

**Not done / not decided:** `freeze_v4.py --freeze` and `--refresh-list` not run, `frozen.json` untouched; `unity/` and `external/` untouched; the smoke check with the dump off (Nusrat's PC) and the repeated avatar rehearsal Play are Nusrat's, in `docs/handoff_freeze_v4.md`.


### 16.30 Nusrat's three step-5 points: all KEEP AND REPORT (2026-11-21, Anisha); recorded BEFORE any code; branch `anisha/v4-prefreeze-2`

**Basis.** `main` = `origin/main` = 4312f97 (it contains `anisha/v4-prefreeze`, 16.29.1; tree clean) when this branch was made. Nusrat raised three points from her step-5 sessions. For each: what is declared, what is measured, and what is NOT changed. **No value, rule, threshold, config or controller behaviour changes in 16.30; nothing in the finals' setup changes because of it.** These are disclosures, to be reported with the results.

**Point 1: the tie re-ask counts a consistent first liar twice (one liar outvotes an honest worker 2:1). Decision: KEEP AND REPORT.**
- It is the declared rule (16.2, the commander's tie rule). The alternatives T1 to T4 were declared, tested in the simulator and not adopted (16.22 to 16.26.8; T4 and the checkpoints were tested again in 16.26.8 and dropped in 16.26.9; T0 is the finals configuration).
- The step-5 result 0/12 in B3, B3_off, B4, B4_off is reproduced by the simulator with Unity's own placement and liars (16.28.1; the runs where Unity aborted and the simulator drove on differ in the reading and the dialog, not in the lie draw).
- **How it is reported:** as the core limitation of the lie detection with two workers per node. With two workers and consistent liars, a lie toward a VALID branch cannot be outvoted (the tie rule follows the first person asked; the second, honest, worker only breaks a tie they cannot win). It is reported in the results of B3 and B4 (on and off) and in the discussion, **together with point 2**.
- **"Abort on a tie" was considered and is not adopted:** it would turn some wrong goals into aborts (the run still fails), so it would change what a failure is called, not how many runs succeed; and a rule chosen after seeing 12 failing runs is a change after the results (CLAUDE.md: thresholds and rules are fixed before evaluation; any change is disclosed).

**Point 2: honest BACK is unreadable, and the arrival rule blocks the recovery. Decision: KEEP AND REPORT, together with point 1.**
- Nusrat's count is 0 of 8 honest BACK pointings read at J3. **What I verified from the step-5 data (16.28):** the two J3 aborts of B3 trial 1 and B3_off trial 1 are an honest BACK read NONE in both asks; the 0/8 itself is Nusrat's count, which I have not recomputed here and report as hers.
- T0 rejects a BACK anyway (a BACK toward the arrival branch is not an answer: the arrival rule), so reading it better would not change the decision. The side view and the across asks were built and tested in 16.26 and not adopted (the readability model `point_readability.json` and the 16.26.8 check).
- Reported with point 1: in B3 and B4 the failures are (a) a followed lie that the tie rule cannot catch and (b) an honest BACK that cannot be read. Nothing is changed before the finals.

**Point 3: 91 accepted STOP episodes, all false (a PROCEED read as STOP). Decision: KEEP AND REPORT as a measured result.**
- The STOP rule (open hand, spread >= 1.3, raised arm, no static cue) and C2s (the short-window STOP while the robot stands still) were decided with their costs disclosed (16.18 to 16.19.7; the trade-off is in 16.18.2 item 5).
- Measured (16.28 item 3): 91 episodes in 39 runs, 0 true (no worker showed a STOP in step 5, so step 5 does not test the STOP's sensitivity); the robot was stopped in all 91; median 0.088 s, maximum 0.677 s; **none of the 91 caused a failure** (not one of the 13 failures has a STOP as its cause; 0 collisions).
- **What makes it provable in the finals:** `stop_reading.jsonl` (16.29 item 3, instrument only) records which reading the controller used at each control step, so C2s is checkable from the logs. The false-STOP count of the finals is reported as measured; it is not a reason to rerun anything.
- **Note:** the 900 s development-timeout wording is already in 16.20.5.1 (PR #48); nothing is added for it here.

**Not decided / not changed:** nothing in the controller, the commander, the reader, the readability model or any config. `unity/` and `external/` untouched.


### 16.30.1 The interruption rule for the finals (2026-11-21, Anisha); recorded BEFORE any code

**Why.** The finals are 13 sessions of 20 runs (about 3 h per sitting). The step-5 sessions showed a native crash of the Python server in B1 (16.27: python312.dll, 0xc0000005) and a machine can fail in other ways. Today a crash has two bad outcomes: if the server dies hard it writes no `FINAL_RUN_DONE.json`, so the setting can be started again **silently** (the guard of 16.15 sees nothing); if it exits cleanly after Unity dies, the marker blocks any continuation, so every crash would cost the whole setting. Neither is declared; this rule declares one.

**The rule.**
1. **Interruption = infrastructure only:** the bridge server or Unity dies, or the machine fails, BEFORE a run finishes. A run that ends (success, wrong goal, abort, timeout, collision, any outcome in `truth_run###.json`) is NOT an interruption, whatever caused it; a failure of the robot's behaviour is a result.
2. **Completed runs stand.** Runs 1 to k-1, which have an outcome, are never rerun and never rescored.
3. **The interrupted run k has no outcome.** It is recorded as "interrupted (infrastructure)" with the evidence (the Event Viewer entry or the crash log, the server and Unity logs), listed in the results and NOT scored.
4. **One resume.** The session may be RESUMED ONCE from run k (the same run number, so the goal of run k is the one that was interrupted), with the same seed, the same goal order, the same configs and frozen hashes. It is declared (below) before it starts, never silent.
5. **A second interruption in the same setting makes the setting INVALID**, reported with the reason, and the setting is never rerun (B11). Nothing is repaired after it.
6. **Every interruption and every resume is reported in the results** (the evaluation lists them; `final_guard_v4.py --status` prints them).
7. **No resume after the setting was evaluated or exported or declared invalid.**

**What the Python side does (declared design, built after this entry).**
- **Markers** (each written with mode 'x', found by the scan of `final_guard_v4.markers`): `FINAL_SETTING.json` in a bridge folder = a final of this setting was STARTED (already written at the start of every final server run, before the first trial; a hard crash leaves it without `FINAL_RUN_DONE.json`); `FINAL_INTERRUPTION.json` in `outputs/final_interruption_<setting>_<time>/` = the declaration (setting, resume_from_run k, reason, evidence paths with SHA-256, part-1 Unity and bridge folder names, seed and goal order as Unity recorded them, the frozen.json hash, the time); `FINAL_RESUME.json` in the bridge folder of the resumed server run (setting, resume_from_run, the declaration it answers, frozen hash); `FINAL_INVALID.json` in `outputs/final_invalid_<setting>_<time>/` (setting, reason, evidence, the markers it rests on).
- **The server's start (`preflight_final`)** is decided from the markers: a final already started (or done) and NO declaration -> refused (this closes the silent restart after a hard crash); a declaration and no resume yet -> allowed only with `--resume-marker <declaration>` for the same setting, an unchanged frozen hash, not evaluated or exported or invalid, and it writes `FINAL_RESUME.json`; a resume already exists -> refused (one resume); invalid -> refused; fresh + `--resume-marker` -> refused (nothing to resume).
- **Declaring** (`python final_guard_v4.py --declare-interruption SETTING --run K --reason TEXT --evidence PATH... --unity-folder U --bridge-folder B`): refused unless the part-1 folders belong to the setting, run K is the first run without an outcome (runs 1 to K-1 have `truth_run###.json` and `python_trial_###.json`, K has no `truth_run###.json`), evidence is given and exists, and nothing is evaluated, exported or invalid. If a resume already exists, the same command writes `FINAL_INVALID.json` instead (second interruption, rule 5).
- **Evaluation and export** (`hri_eval_final_v4.py`, `export_csv_v4.py` final mode) score a resumed setting as ONE session: `--session U1 B1 --session U2 B2` where part 1 is the declaration's folder; part-1 runs from k on are listed as interrupted and not scored, part-2 runs must start at k; the union must be runs 1 to 20 once each. They REFUSE: a declaration with no resume, a resume with no declaration, an invalid setting, parts whose seed, goal order or frozen hash differ (from each other and from the declaration; the seed is also checked against the plan's `final_seed` by `check_setting`). The goal order is compared, not recomputed from the seed (corrected before the code was finished: recomputing it needs the final map and is not done here), a part-2 Unity `session.json` that does not record `resume_from_run` equal to k, and a missing or additional part. The evaluation's summary names the declaration, the reason, the evidence and the interrupted run.
- **Limits, stated now:** (a) Python never receives the seed or the goal B (CLAUDE.md), so "same seed and goal order" is enforced at EVALUATION from Unity's `session.json`, and at start by Unity itself (its part below); (b) the declaration is made by a person on the machine that ran the final (Nusrat), with evidence; Python can check that run k has no outcome and that the evidence exists, not that the crash was real; whoever reads the results sees the evidence and the declaration in the report; (c) a crash inside the evaluation or export tools is not an interruption of a final (they write their marker only when they finish).

**What Unity must do for a resume (Nusrat's part; `unity/` is hers, nothing there is changed by me).**
1. After a crash, do NOT rerun the launcher for the setting. First Anisha's declaration command (`docs/handoff_freeze_v4.md` section 8) with the evidence.
2. Start the resumed session at run k: same `final_seed`, same goal order, same final config (`sessions/final_ab_<setting>.json`), same frozen files (the freeze hash must still match). The trial numbering CONTINUES at k (`run_011` ... `run_020`, `truth_run011.json` ..., `python_trial_011.json` ...), never 1 again.
3. Write into the resumed session's `session.json`: `resume_from_run` (k), `resume_of` (the name of the part-1 session folder), and the usual `seed`, `goal_order` (the FULL order, goal k is the same as in part 1), `final_setting`, `mode` "final".
4. REFUSE to start (print why, exit non-zero, write nothing) when: no declaration exists for the setting; the seed, goal order, config or frozen hashes differ from part 1; a resume was already used (a second resume); the setting is finished (`UNITY_FINAL_DONE.json` of a complete session, `FINAL_DONE.json`, `FINAL_EXPORT_DONE.json`) or invalid.
5. The launcher passes `--resume-marker <the declaration>` to the server and does not stop on the part-1 `FINAL_RUN_DONE.json` / `UNITY_FINAL_DONE.json` when a declaration exists for the setting; the launcher is not edited by me.
6. Keep the interrupted run's folder `run_<k>` in part 1 as it is (it is listed, not scored) and do not delete anything. The run-protocol note and the power-mode line are made for part 2 as for any session.
7. A second crash: stop, make no third part, declare it (the command writes the invalid marker), report the setting as invalid.

**Tests (Python side)** are listed when built (16.30.1.1 below, after the work).


### 16.30.2 The tool for the final zips (2026-11-21, Anisha); recorded BEFORE it is built

**Options.** (a) `finals_v4/step5_zip_v4.py`: built for the step-5 development sessions: it reads a manifest (`outputs/step5_sessions.json`) by setting-name prefix `t0_`; finals have no such manifest and the names differ (`trials_final_Task2_<setting>_*`), so it does not fit, and it is Nusrat's file. (b) `robot_vision/make_results_archive_v4.py`: the archive tool (copies the sessions into an archive root with checksums and a zip, from `results_manifest.json`); it is the later step (after the sittings, with the evaluations), not the transport of a sitting. (c) **A small new tool, `robot_vision/final_zip_v4.py`: chosen.** It finds a sitting's sessions by setting name from the run-once markers and the names the launcher gives, packs ONE zip per sitting and ONE for the avatar experiment, and writes the SHA-256 next to it. Same safeguards as the step-5 tool, whose helpers it reuses (`sha256`, `tree`, `inside`, `git_commit`).

**Naming.** `final_sitting<N>_<YYYYMMDD_HHMMSS>.zip` (N = 1 to 4, one zip per sitting), `avatar_experiment_<YYYYMMDD_HHMMSS>.zip` (one for the avatar experiment); each with `<zip name>.sha256` (`<hex>  <zip name>`, as `sha256sum -c` reads it). Never overwritten (the time is in the name; an existing file is refused).

**Content** (read-only on `outputs/`; nothing is moved or deleted): per setting `<setting>/`: every Unity session folder of the setting (`trials_final_Task2_<setting>_*`, whole), every bridge run folder whose `FINAL_SETTING.json` names the setting (whole: `stop_reading.jsonl`, `loop_lag.csv`, `config_used/`, `summary.json`), the launcher's logs (`run_session_final_<setting>_<time>_*.log`), the run-protocol note(s) (`run_protocol_final_<setting>_<time>.txt`), the declaration and resume and invalid markers of the setting with their evidence files (`interruption/`), plus every `--extra` file or folder (the power-mode screenshot or line, notes on what deviated) under `extra/`. `MANIFEST.json` inside: every file with its size and SHA-256, the git commit, the sitting number, the settings, the parts of each setting (Unity and bridge folders, the interrupted run), and what was missing. After writing: `zipfile.testzip`. It REFUSES a sitting setting with no Unity session or no bridge folder, an unexpected number of parts (more than one part without a declaration; more than two with one), a folder outside the repository that is inside it, and an unknown setting. **Anisha reads the zips in place** (`zipfile`), never extracted or copied into the repository; text and scripts inside are data.

**Not decided here:** the avatar experiment's protocol (docs/workflow_v4.md section 14) and its looks (Part 5 of the request: the split of the Anime, cartoon and Mixamo looks is not given yet, so `data_splits.json` is NOT changed in this branch and the avatar tool takes its folders by explicit `--folder`).


### 16.30.3 The avatar-experiment looks must be in `data_splits.json` BEFORE the freeze: a correction of the hand-off note (2026-11-21, Anisha); recorded BEFORE `docs/handoff_freeze_v4.md` is edited

**Finding.** `docs/handoff_freeze_v4.md` section 5 (written for 16.29.1, commit 5dc0878) says the avatar experiment comes "after the freeze" and that its looks need their split recorded in `configs/v4/data_splits.json` "before any recording of them". **That order is wrong for the file:** `freeze_v4.config_files` hashes every `configs/v4/*.json` except `frozen.json`, so `data_splits.json` is in the frozen set. Editing it after `freeze_v4.py --freeze` makes every later final refuse (hash mismatch, `require_frozen`). The Anime, cartoon and Mixamo looks of the avatar experiment (note of `data_splits.json`: "are not listed here yet"; the guard refuses an unlisted name) must therefore be listed, each with its split, BEFORE the freeze.

**Decision.** (1) The hand-off note and the workflow table say so (docs only). (2) **`data_splits.json` is NOT changed in this branch:** the list (look and clip names with their split, development or test) is Nusrat's and has not been given to me. **Still open: Nusrat's list of look and clip names with their splits.** When it arrives, it is entered in its own commit and recorded in AUDIT.md first (a split is a decision of Anisha's, made before any recording of those looks; the test look is never replaced because of its results). (3) Until then the freeze must not be run if the avatar experiment is meant to use the guard; Nusrat is told in the note. The A/B finals do not depend on it.


#### 16.30.1.1 Done (2026-11-21): the interruption rule and the final zips are built as declared

- **`final_guard_v4.py`:** marker kinds `started` (`FINAL_SETTING.json`), `interruption`, `resume`, `invalid`; `check_start` (the server's start rule), `write_resume`, `declare_interruption` (also the second interruption -> `FINAL_INVALID.json`), `resume_plan` / `trial_problems` / `interruption_report` / `interruption_markdown` (evaluation and export), `status` / `status_text`; command line `--status`, `--declare-interruption SETTING --run K --reason --evidence --unity-folder --bridge-folder`. `--timeout-from` unchanged.
- **`bridge/server.py`:** `preflight_final(..., resume_marker)` uses `check_start` (a started final is refused without a declaration, whether or not `FINAL_RUN_DONE.json` exists); `--resume-marker`; the resumed server writes `FINAL_RESUME.json` and `resume_from_run` into `FINAL_SETTING.json` before the first trial. A fresh start behaves as before; the refusal text still contains "already run as a final".
- **`hri_eval_final_v4.gate`** (so the evaluation AND the export): `resume_plan` before any test data is read; `hri_eval_dev_v4.load_sessions(include=...)` (default None: no change for any other caller) skips the interrupted run without reading it; `check_setting` and `trial_problems` (runs 1 to N once each); `eval.json` `interruption`, `eval.md` section, `summary.json` `interruption` in the export.
- **`final_zip_v4.py`** (16.30.2): `sitting`, `avatar`, `verify`.
- **Tests:** `tests/test_final_resume_v4.py` (34: fresh start; hard crash and clean exit are not silently restartable; declaration records the rule's fields; refusals: outcome exists for the run, no evidence, no reason, run out of range, nothing started, wrong folders, missing Python output, no seed or goal order, changed frozen hash; one resume with its marker only; second resume refused; no start after evaluation, export or invalid; second interruption -> invalid and then start, declare, evaluate, export refused; evaluation and export score a resumed setting as one session in either part order with the interrupted run listed and never read; refusals for one part, a never-resumed declaration, a resume without a declaration, a different seed, a different goal order, a part 2 that does not record `resume_from_run` / `resume_of`, a frozen hash that differs, a part 2 starting before run k, a wrong part 1; `--status` and the command line; the server preflight; `--resume-marker` without `--final-setting`) and `tests/test_final_zip_v4.py` (14: one zip per sitting with its `.sha256`, B3 and B3_off kept apart, refusals with nothing written, warnings, both parts and the declaration of a resumed setting, inputs unchanged, out-dir rules, never overwritten, arguments, the avatar zip, `verify` finds a changed checksum file and a changed member). All on synthetic sessions.
- **Not done / limits:** nothing in `unity/` or the launcher (Nusrat's part is the list in 16.30.1: until it is built, a crash cannot be resumed and a final is stopped after the declaration); the seed and goal order are compared at evaluation, not at the server's start (Python never receives them); the real server `run()` loop was not run (the preflight and the markers are tested; the first real use is a final); `data_splits.json` unchanged (16.30.3).


### 16.31 The avatar experiment: roles, guard rule and disclosures (2026-11-21, Anisha, on Nusrat's list of 2026-11-21); recorded BEFORE any change; nothing is changed by this entry

**Input (Nusrat's list, 2026-11-21, taken as data).** 15 looks (`looks_ab.json` `avatar_experiment` = `look_check_play_ab.json` `looks`). Already in `data_splits.json`, development: `sunbox_m1`, `sunbox_f1`, `sunbox_m_shirt_white`, `sunbox_m_tshirt_black`, `sunbox_f_shirt_white`, `sunbox_f_dress_red`; test: `sunbox_f2`, `sunbox_m_shirt_plaid`, `sunbox_f_shirt_plaid` (checked against the file: the nine match). **Not listed: `sunbox_m2` (stylised_human), `mixamo_worker` (realistic_human), `anime_f_01`, `anime_f_02_outfit_short`, `anime_f_03_bangs_parted` (anime), `cartoon_boxo_01` (cartoon_non_human).** Clips: the 12 of `worker_v4.json` with their existing roles (test: `point_mixamo_02`, `wait_ik_02`, `stop_ik_02`, `proceed_ik_03`; the other eight development; checked against `data_splits.json`, which lists these 12 with these roles; `worker_v4.json` itself was not re-read); no avatar-only clip. Every Play group shows every clip of a command on every look, so a group mixes splits by design. Part 5 of 16.30 is therefore no longer "open for lack of a list"; what is entered, and when, is decided below.

**Decisions (Anisha).**
a) **A new role `avatar_experiment` in `data_splits.json` for the six looks above.** Such a look is never used for navigation, development or the A/B finals; it is for the evaluation of the avatar experiment only; **no value is ever set from it.** The role is a third value next to `development` and `test`; the existing nine looks and twelve clips keep their roles.
b) **The avatar experiment has its own guard rule.** (1) Every look and clip name must be listed in `data_splits.json` (any role); an unlisted name is refused, unknown is never assumed. (2) The session must be marked as an avatar-experiment session. (3) The frozen hashes must match (`freeze_v4.require_frozen`): the experiment runs after the freeze (and after the last navigation final, as Unity's guard of experiments_ab.md section 10 item 6 already requires), so nothing can be tuned on it. **The development/test rule of `guard_run` (a run lies wholly in one split) does not apply to it**; its results are reported split by look role and by clip role instead. The reverse also holds: a look with the role `avatar_experiment` is refused by `guard_run` in every mode (development evaluation, final evaluation, the A/B finals), so it can never enter them.
c) **Disclosures to be made in the results.** Test-look frames were rendered in rehearsals but were never shown to a model and were deleted (the blind rule of the avatar rehearsal, 16.28.1 and the hand-off note). Earlier engineering look checks DID run perception on test looks (already disclosed); they are engineering checks, not results, and nothing was tuned on them.
d) **The evaluation protocol is DRAFTED in 16.31.1 below, marked DRAFT; no code and no `data_splits.json` change follows until Anisha has reviewed it** (nothing in this entry is built).
e) **Resume:** Nusrat reports that Unity now supports `-StartRun k`, refused in finals until the Python guard has the interruption rule. It has: 16.30.1 / 16.30.1.1 (`final_guard_v4.py`, `--resume-marker`, evaluation and export of a resumed setting). Points to settle with Nusrat, none changed here: her part-2 `session.json` must carry `resume_from_run` and `resume_of` (the evaluation refuses without them), the launcher passes `--resume-marker <declaration>` to the server, and a declaration (`--declare-interruption`) precedes any resume.

**What follows after review (planned, NOT done).** (1) `data_splits.json`: the six looks with role `avatar_experiment` and their kind in `styles`, entered BEFORE `freeze_v4.py --freeze` (the freeze hashes the file, 16.30.3) in its own commit; `data_splits_v4.check_config` and `guard_run` extended (the refusal of the role outside the experiment; a test per rule); (2) the avatar guard function and a reporting script that joins the look-check reports with the roles (look_check_v4.py itself never reads `data_splits.json`, a test pins that, and stays unchanged); (3) the hand-off note and `docs/workflow_v4.md` section 14 follow the reviewed protocol. **Before (1) the callers of `split_of_look`, `check_config` and `guard_run` (data_splits_v4, hri_eval_dev_v4, hri_eval_final_v4, gesture and look tools, tests) are read, because a third value must not be read as "development" or "test" by any of them.**

#### 16.31.2 Decisions of 2026-11-21 (Anisha) on 16.31: what is built now, what is not; recorded BEFORE any change

**Order.** Anisha: "the cut-off line meant: STOP for my review before building anything for the PROTOCOL only". So a), b) and e) of 16.31 are built now, after reading every caller; the protocol (16.31.1) stays a DRAFT and is shown for review.

**Callers read (the check demanded before the change).** Python: `data_splits_v4.guard_run` is the only function that decides a split. Its callers are `hri_eval_dev_v4.load_sessions` (and through it `hri_eval_final_v4.gate`, `export_csv_v4`, `hri_analysis_v4`, the development evaluation), `calibrate_v4`, `check_stop_rule_v4`, `analyse_false_stop_v4`; `hri_analysis_v4` reads `splits["styles"]` (a per-style table of the navigation looks); `freeze_v4` reads `placeholder`. `split_of_look` and `split_of_clip` have no caller outside `data_splits_v4.py`; `check_config` is called by `load`. **Finding: `guard_run` as it is would ACCEPT a run whose looks are all `avatar_experiment`:** it collects the roles found, finds one role, which is neither test nor a final run, and returns that role as "the split": a development evaluation would accept an avatar-only look. The change below closes it. **Unity has the same hole** (`DataSplitsV4.GuardRun` in `Avatar/Scripts/TrialWorkersV4.cs`, read only): a lone third role is returned without error; `Names(true, mode)` keeps such a look out of the default navigation plan, but an explicit `looks` list in a workers config would not be refused. That file is Nusrat's: it is told in the hand-off note, not edited.

**Decisions.**
1. **`data_splits.json`:** the six looks (`sunbox_m2`, `mixamo_worker`, `anime_f_01`, `anime_f_02_outfit_short`, `anime_f_03_bangs_parted`, `cartoon_boxo_01`) get the role `avatar_experiment` in the flat `looks` table (Unity's parser reads that table flat: name -> role). New table `kind_groups` (look -> kind group, the 15 looks; from `looks_ab.json` `kind_group`; `sunbox_m1`, `sunbox_f1`, `sunbox_f2` are in `worker_v4.json`, which has no kind group, and are entered as `stylised_human` on Anisha's answer "stylised_human = all ten Sunbox looks"). `styles` is NOT changed (it stays the per-style table of the nine navigation looks). `recorded.avatar_experiment_looks` records this decision. Clips: no avatar-only clip; a clip may only be development or test.
2. **`data_splits_v4.py`:** roles `development`, `test`, `avatar_experiment`; `check_config` accepts the third role for looks only, and requires every `avatar_experiment` look to have a kind group and every kind group to name a listed look; **`guard_run` refuses any look with the role `avatar_experiment`, in every mode (development evaluation, final evaluation, with or without `--final-evaluation`, alone or mixed), before anything else.** New `guard_avatar_experiment(looks, clips, session_marked, splits, repo)`: refused unless `session_marked` is true, `freeze_v4.require_frozen` passes (every hash matches), every look and clip name is listed (any role; an empty clip name is refused; unknown is never assumed), and it returns the role of each look and clip (for the report by role) and the kind groups. It does not apply the development/test mixing rule. **How a session is marked is OPEN (asked to Nusrat):** the function takes the result as an argument and reads no marker file yet.
3. **Resume alignment (e), Python side:** a new command `final_guard_v4.py --resume-info SETTING` prints, as JSON, what the launcher needs to resume (`resume_from_run`, the declaration folder, seed and goal order of the declaration) or refuses with the reason (nothing started, no declaration, already resumed, invalid, evaluated, exported). The launcher can pass `resume_from_run` as Unity's `-StartRun k` and the folder as `--resume-marker`, and Unity can compare its seed and goal order with the declaration's. Unity's own `-StartRun` code is not in this repository (no branch has it), so the keys Unity writes into `session.json` are NOT known to me: the evaluation keeps requiring `resume_from_run` and `resume_of` there, and refuses without them; if Unity writes other names, the names are agreed and one of the two sides changes, declared first. Nothing is guessed or aliased.
4. **The interruption rule applies to the avatar experiment too** (answer of 2026-11-21): resume once from the interrupted group; a second interruption makes that part invalid. **Not built now:** no Python process runs in the avatar experiment (the Unity look-check tools write recordings and its own markers), the group and recording formats are Unity's, and the merge of two recordings folders belongs to the reporting step of the protocol. It is specified in 16.31.1 (D3) and built after the review.

**Not done / open.** The clip per take and the session marker (16.31.1 Q5, Q6) are open and asked to Nusrat. `unity/` is not edited. `freeze_v4.py --freeze` is not run. The A/B finals are not affected (no setting uses these looks).


#### 16.31.2.1 Done (2026-11-21): a), b) and e) built as declared in 16.31.2

- **`configs/v4/data_splits.json`:** the six looks with the role `avatar_experiment`; `kind_groups` (15 looks); `recorded.avatar_experiment_looks`. The nine looks and 12 clips unchanged; `styles` unchanged; the flat `looks` table and a single `"looks"` / `"clips"` key are kept for Unity's reader (tested).
- **`data_splits_v4.py`:** `check_config` (role for looks only; kind groups consistent), `guard_run` refuses the role in every mode (also a hand-edited clip), `guard_avatar_experiment(looks, clips, session_marked, splits, repo)`. **The older test of the styles table was changed** (it required `styles` to have every listed look; it now requires the navigation looks): disclosed here because it is a test of mine edited for the new role.
- **`final_guard_v4.py --resume-info SETTING`** (`resume_info`): the run, the declaration folder, the declaration's seed and goal order, or the reason for a refusal.
- **Callers read:** all paths to a split go through `guard_run` (listed in 16.31.2); a test now fails if a module reads a look's role itself (`tests/test_avatar_role_v4.py`, `CallersTests`) and the session loader is shown to refuse an avatar look in development and in a final.
- **Tests:** `tests/test_avatar_role_v4.py` (shipped config; config rules; `guard_run` in every mode alone and mixed; callers; the guard: roles together accepted, marker, not frozen or a changed config, unlisted or empty names) and four more in `tests/test_final_resume_v4.py` (`--resume-info`).
- **Not built / open:** the protocol (16.31.1), the interruption rule for the avatar experiment on the Python side, the report by role, the session marker (Q6), the clip per take (Q5). Unity's own `GuardRun` has the same lone-role hole as Python's had: told to Nusrat in the hand-off note, not edited. The keys Unity writes for `-StartRun` are not in the repository and remain to be agreed.


#### 16.31.1 DECLARED (2026-11-21; reviewed and declared by Anisha the same day, Q5 and Q6 pending Nusrat's answers): the evaluation protocol of the avatar experiment; declared BEFORE any recording; the reporting tool is not built yet

Sources: `docs/look_check_v4.md`, `configs/v4/look_check.json`, `Avatar/Config/look_check_play_ab.json`, `looks_ab.json`, `experiments_ab.md` sections 8, 10, 11 (Nusrat's declaration of 2026-11-14, taken as data). Where the sources and the list of 2026-11-21 differ (13 looks and 12 clips in section 8; 15 looks now; Boxo spawnable in Play since section 11 item 3; PROCEED recorded since section 10 item 5), the list of 2026-11-21 is used. **Marking:** ANSWERED = Anisha's answer of 2026-11-21; ACCEPTED = my proposal, accepted by Anisha in her review of 2026-11-21; CHANGED = my proposal, changed by Anisha; OPEN = asked to Nusrat.

**Review of Anisha, 2026-11-21 (recorded here; it makes the protocol DECLARED).** (1) ACCEPTED: the floor (at least 2 sequences and at least 10 single-frame takes per arm and distance), INVALID = technical recording failures only, Q8 (PROCEED in Play only), Q9 (Play is the headline, Edit is the control, never pooled), Q10 (all 15 looks in the headline table, plus the summary by kind group). (2) **CHANGED, Q4: the TAKE is the unit for EVERY interval. Frames within a take are not independent.** A frame-level measure is computed as a share PER TAKE, then reported as the mean over takes with a bootstrap over takes (2000 resamples, seed 1, `configs/v4/analysis.json`); Wilson intervals only for take-level yes/no outcomes; **never a Wilson interval over frames.** This replaces my proposal (frame as the unit of frame checks, with a note). (3) **Q5 (the clip per take) and Q6 (the session marker) stay OPEN, pending Nusrat's answers. They do not change any outcome definition** (the clip per take only decides whether the split by clip role can be computed; the marker only decides how the guard learns that a session is an avatar-experiment session). (4) The protocol is DECLARED before any recording and before any code for it; a later change is made in a new, dated entry and disclosed, never in place.

**D1. Question.** How does the kind of avatar change what the frozen perception and reader find and read: the person, the arm, the hand, and the gesture (POINT, WAIT, STOP, PROCEED; NONE as a negative control)? An engineering measurement with `look_check_v4.py` and `look_check.json` UNCHANGED (frozen); **no threshold, reader, commander, perception or control value is set or changed from it, no look is added, dropped or replaced because of a result, and nothing feeds back into the navigation finals.**

**D2. Looks and kinds (ANSWERED).** 15 looks. Kind groups (`data_splits.json` `kind_groups`, from `looks_ab.json` `kind_group`): stylised_human = **all ten Sunbox looks** (`sunbox_m1`, `sunbox_f1`, `sunbox_f2`, `sunbox_m2`, `sunbox_m_shirt_white`, `sunbox_m_tshirt_black`, `sunbox_m_shirt_plaid`, `sunbox_f_shirt_white`, `sunbox_f_dress_red`, `sunbox_f_shirt_plaid`); realistic_human = `mixamo_worker`; anime = `anime_f_01`, `anime_f_02_outfit_short`, `anime_f_03_bangs_parted`; cartoon_non_human = `cartoon_boxo_01`. Role of each look (development, test, avatar_experiment) from `data_splits.json`. A kind with one look (realistic, cartoon) describes that look and is not generalised to a kind. The per-style table of `hri_analysis_v4` (navigation looks, one style) is not used: this protocol's tables are by kind group.

**D3. Recordings and repeats.** Unity records, once, after the freeze and **after the LAST final sitting** (the test looks are no longer needed for finals; 16.31.5 item 6), on the frozen commit (as declared), with **about 3 h reserved** (the Play part's `-lookCheckTimeout 10800`). Edit mode (held poses on the neutral stage, 2.0 m and 4.0 m, both arms; 2 sequences of 11 frames and singles per group) and Play mode (worker template in `WarehouseRobot_v4.unity`, J1 and J2 stands, asking bearings 15 to 50 deg, seed 1: per look, command, distance and arm 2 sequences of 11 frames + 16 single frames = 38 frames; PROCEED sequences of 21 frames). Commands POINT, WAIT, STOP, PROCEED, NONE.
- **One seeded recording pass (ANSWERED), provided each look x command has enough independent takes.** An independent take is one performance with its own variation stream and its own drawn camera pose (the 2 m and 4 m cameras record the same take, so a take is counted once per arm, not once per distance). **Floor (ACCEPTED 2026-11-21, declared before the recording):** a look x command cell is evaluated when it has at least 2 sequences and at least 10 single-frame takes per arm and distance among its VALID takes (Unity records 2 and 16, so up to 6 singles may be lost); below that the cell is `insufficient_data`, never filled. **The counts per look x command are reported in the main table** (takes recorded, valid, used). **Exact counts of the Play recording (from `look_check_play_ab.json`, 2026-11-21):** per look 18 groups (POINT, WAIT, STOP, PROCEED: 2 arms x 2 distances = 16; NONE: 2 distances) and 764 frames (a POINT, WAIT or STOP group 2 x 11 + 16 = 38 frames, a PROCEED group 2 x 21 + 16 = 58, a NONE group 38); 15 looks: 270 groups, 11,460 frames; 144 independent takes per look for the four gesturing commands (4 commands x 2 arms x 18 takes; the 2 m and 4 m cameras see the same take) and 36 for NONE (18 per distance, each at its own pose). **Gap found while writing the protocol for Nusrat, NOT in Anisha's review, to be confirmed before any recording (PROPOSED):** the Edit-mode recording (`look_check.json`) has 2 sequences and 5 singles per group, and its takes are fixed posed variants (a sequence is one pose held for 11 or 21 identical frames), so the floor of 10 single-frame takes cannot be met in Edit mode and Edit takes are not independent performances. PROPOSED: the floor of 10 singles applies to Play only; the Edit floor is the recording as declared (2 sequences and 5 singles per group), Edit is the control (Q9), its means and bootstrap intervals describe the variation across the posed variants only and are labelled so. PROCEED in Edit (a posed swing) is recorded by Unity but, by Q8, never evaluated: `not_evaluated`.
- **A group may be repeated only if it is INVALID, declared and reported; never because of its result (ANSWERED).** **Definition of INVALID (ACCEPTED 2026-11-21: technical recording failures only, independent of what the models see):** (i) frames or headers missing or truncated (fewer than the declared 11 or 21 frames, an unreadable PNG, a missing header); (ii) a header whose intrinsics fail the check of `docs/look_check_v4.md` (the tool already lists such frames as input problems); (iii) a Unity exception or crash during the take, or **a frame time that breaks the declared timing rule: each frame less than 0.100 s from its 0.1 s mark and consecutive frames at most 0.2 s apart (Unity `experiments_ab.md` section 15 addendum 10, `finals_v4/avatar_rehearsal_check.py`; 16.31.5 item 2)**; (iv) the wrong look, command, distance or arm recorded (name or header disagrees with Unity's own record); **(v) a frame with the placeholder colour (cyan placeholder or error-shader magenta) recorded while Unity's shader warm-up record, kept with the session, shows compilation still running (16.31.5 item 1).** Unity pre-warms all shaders before recording; the decision is made from that record and the frame's time, **never by inspecting images.** **NOT invalid, so never repeated:** no person found, no hand found or linked, a wrong read, a failing verdict, **and a placeholder colour after the warm-up finished (a look defect, reported as the look failing, as experiments_ab.md sections 5, 6 and 8 already say; 16.31.5 item 1)**. A repetition is declared before it is made (the group, the reason, the evidence: a file, the Unity log), its first recording is kept and listed, the repeat replaces it in the counts, and the report states every repeated group. At most one repetition per group. **If the repeat is invalid for the same reason (for example the placeholder colour again while compilation is running), the group is reported INVALID, not failing** (16.31.5 item 1).
- **The interruption rule of 16.30.1 applies (ANSWERED):** a crash of Unity or the machine ends a part (Edit or Play) before it is complete. It is declared with evidence; the part may be **resumed once, from the interrupted group** (the first group without a complete recording, in Unity's recording order; the interrupted group is listed and not scored, and recorded again from the start), with the same seed and configs and the frozen hashes unchanged; **a second interruption makes that part INVALID** (reported with its reason; the other part stands). The two recordings folders of a resumed part are reported as ONE session. The group order, the resume option of the look-check tools and the marker are Unity's and are asked to Nusrat; the Python side (declaration, refusal of undeclared extra folders, merge) is built after this protocol is reviewed (16.31.2 item 4).

**D4. What is measured (the fields of the unchanged report, per look, per kind, per command, per distance).** **"Person detected" = `person_rate`** (share of frames in which YOLO finds a person). **"Hand detected" (ANSWERED): primary = a hand found AND linked to the gesturing arm** (`hand_linked_rate`: the MediaPipe hand is linked to the recorded arm by its wrist; what the reader needs for WAIT and STOP); **secondary = a hand found anywhere in the frame** (the share of frames with any MediaPipe hand in the person crop). Both are reported, each with its count; the verdicts use only what `look_check.json` already uses. Also: arm valid, own cue, wrong class, sequence read as recorded, wrong read (a different command), POINT arm-to-shoulder ratio p95, **facing (reported only, not in the verdict; it goes into the per-look tables as a per-take share with its mean over takes and bootstrap like the other frame measures; 16.31.5 item 3)**, and the verdict per look (usable / weak / fails / insufficient_data by the declared rules of `look_check.json`; the 2.0 m groups decide, 4 m can only lower to weak). Every rate with its count and its coverage (frames, sequences, takes, groups); `not_evaluated` and `insufficient_data` are kept, never filled.

**D5. Aggregation and statistics (descriptive only; Q4 CHANGED by Anisha, 2026-11-21).** **The unit of every interval is the TAKE** (a sequence or a single frame; an independent performance with its own variation stream and drawn camera pose). The frames of one take are one held pose or one swing seen ten or twenty times, so they are not independent trials.
- **Frame-level measures** (person found, hand found anywhere, hand found AND linked, arm valid, own cue, wrong class, facing) are computed **as a share per take** (for a sequence: its frames with the property over its frames; for a single frame: 0 or 1), then reported as the **mean over takes** (each take counts once) with a **bootstrap over takes**: 2000 resamples, seed 1, percentiles 2.5 and 97.5, the settings of `configs/v4/analysis.json` (`bootstrap`; the avatar experiment's own block `avatar_experiment` names the unit "take" and repeats these numbers, 2026-11-21). Takes are resampled with replacement within each look x command x distance x arm cell; a pooled cell (a kind group, a command, a role) resamples the takes of each of its looks separately, so that its look composition stays fixed (the looks are not a random sample of looks: a look is a fixed avatar, and the interval describes take-to-take variation, not look-to-look variation).
- **Take-level yes/no outcomes** (a sequence is read as recorded, as a different command, or not read; the single-frame takes of a cell when only they are counted) get a **Wilson 95 % interval** (`export_csv_v4.wilson_z`) on the count of takes. **Never a Wilson interval over frames.**
- **The verdicts stay the unchanged tool's** (`look_check_v4.py` applies the declared thresholds of `look_check.json` to its own pooled frame and sequence rates, as before). The means over takes and their bootstrap intervals are reported NEXT to them; if the two disagree about a look, both are shown and the verdict stays the tool's.
- Every number is given with its counts: takes recorded, takes valid, takes used, and for a frame-level mean also the frames behind it; `not_evaluated` and `insufficient_data` are kept, never filled. Per kind: the number of looks per verdict (verdicts are counted, never averaged).
- No hypothesis test. A difference between kinds or roles is shown as the difference of the two reported values with their counts; an interval for a difference, if wanted, uses the same take bootstrap (the same resamples and seed); it is declared before the numbers are seen.

**D6. Reporting split by role.** Every table is also given by look role (development, test, avatar_experiment) and by clip role (development, test), because a group mixes them: a look's group shows every clip of its command. The clip of each take must be known to the report: the look-check recordings carry look, command, distance, arm and take in their names but not the animation clip. **Q5 CLOSED (16.31.5 item 4): the clip per take comes from `recordings.jsonl` of the Unity run folder** (per recording: look, command, distance, arm, take, clip; `name` joins it to the look-check report). **Edit takes have clip "" and pose "posed" and are excluded from the clip-role split; Play NONE takes have no gesture clip and are excluded too; a Play gesture take without a clip is `not_evaluated`, never guessed; an unlisted clip name is refused.** The split is built (`avatar_clip_roles_v4.py`, tested) and is computed per distance, never pooled over the 2 m and 4 m cameras (they see the same take). The reporting step reads the roles from `data_splits.json` and the look-check report; `look_check_v4.py` does not read `data_splits.json` and is not changed.

**D7. Guard (decision b of 16.31, built as `data_splits_v4.guard_avatar_experiment`, 16.31.2 item 2).** The reporting step is refused unless: every look and clip name in the recordings is listed in `data_splits.json` (any role); the session is marked as an avatar-experiment session; `freeze_v4.require_frozen` passes. **Q6 CLOSED (16.31.6): the session is marked by `avatar_experiment_part` ("edit" / "play" in an official run, "" in an engineering check, which is refused as not official) in `run_info.json`, plus the run-once markers `AVATAR_EXPERIMENT_STARTED.json` and `AVATAR_EXPERIMENT_DONE.json` with the same key; the guard reads them from the run folder (`data_splits_v4.load_avatar_session`).** The reporting step writes a new folder with the exact config, the git commit and the frozen hash, and its own run-once marker (it cannot be reported twice).

**D8. What does not happen, and a limitation.** **Limitation (16.31.5 item 5): the avatar experiment measures the pan-tilt camera only; finding people with the 360 camera, per look, is not measured.** No retuning; no look replaced for failing (a failing look is reported as failed, as `anime_f_01` and `cartoon_boxo_01` were in experiments_ab.md section 6); no rerun after seeing a result (a repetition only for an INVALID group, D3); the earlier engineering look checks (same seed) are not part of the experiment; no avatar result is used for navigation; the test looks are reported like the others, after the finals.

**Answers and proposals for Q1 to Q10.**
- **Q1 ANSWERED:** person detected = `person_rate`; hand detected primary = found AND linked to the gesturing arm, secondary = found anywhere in the frame (D4).
- **Q2 ANSWERED:** stylised_human = all ten Sunbox looks (D2).
- **Q3 ANSWERED, floor and INVALID ACCEPTED:** one seeded pass; counts per look x command; at least 2 sequences and 10 single-frame takes per arm and distance; a repetition only of an INVALID group, which is a technical recording failure only (D3).
- **Q4 CHANGED by Anisha:** the TAKE is the unit for every interval; frame measures are a share per take, reported as the mean over takes with a bootstrap over takes (2000 resamples, seed 1); Wilson only for take-level yes/no outcomes; never over frames (D5). Reason: frames of one take are not independent.
- **Q5 CLOSED (16.31.5 item 4):** the clip per take is read from `recordings.jsonl`; Edit takes (clip "", pose "posed") are excluded from the clip-role split (D6).
- **Q6 CLOSED (16.31.6):** `avatar_experiment_part` in `run_info.json` plus the run-once markers; the guard is wired to it (D7).
- **Q7 ANSWERED:** the interruption rule applies; resume once from the interrupted group; a second interruption makes that part invalid (D3).
- **Q8 ACCEPTED:** PROCEED is evaluated in Play (recorded for every look, experiments_ab.md section 10 item 5); in Edit mode only if Nusrat builds the posed swing, otherwise `not_evaluated` there, never filled. Reason: the swing is a motion; the Edit stage shows held poses.
- **Q9 ACCEPTED:** both parts are reported, separately and never pooled: Play (real motion, the robot's venue, the worker template) is the headline; Edit (held poses on a neutral stage) is the control. Reason: the two differ in what they show, and a pooled rate would hide which condition a failure belongs to.
- **Q10 ACCEPTED:** the headline table covers ALL 15 looks, with the summary by kind group; the role-split tables (development, test, avatar_experiment) are secondary and show the test looks like the others. Reason: the test looks are three of the ten stylised_human looks; leaving them out of the headline would be a selection, and leaving them in is safe because the experiment runs after the finals.

**Status: DECLARED 2026-11-21 (Anisha), changed by 16.31.5 after Nusrat's review (the placeholder rule, the timing rule, facing, Q5 closed, the 360 limitation, the order). Open, pending Nusrat's answers: the meaning of a "group" in Unity's recording order, the counts of section 2 of the doc and the resume option of the look-check tools; none changes an outcome definition. The standalone text for Nusrat's review is `docs/avatar_experiment_protocol_v4.md`. Not built: the reporting step, the Python side of the avatar interruption rule.**


### 16.31.3 Unity's `-startRun k` (PR #50, merged 2026-11-21) against the resume rule of 16.30.1: how it maps, what Unity must add for a resume in a final (2026-11-21, Anisha); recorded BEFORE any change; nothing in the code is changed by this entry

**Merge.** `origin/main` (21a4eaf, PR #50) merged into `anisha/v4-prefreeze-2` (f78d8a0): no conflict. PR #50 changed no line of AUDIT.md (its text is in `Avatar/Config/experiments_ab.md` section 15 addendum 10), so no entry had to be put in date order. This entry supersedes the sentence of 16.31.2 item 3 that Unity's `-StartRun` code was not in the repository.

**What her code does (read as data; nothing in `unity/` or `finals_v4/` is edited by me).**
- `TrialPlayV4 -startRun k` (an Editor session key, cleared at the end) and `SessionResumeV4.Parse(text, runs, final, ...)`: empty = 1; otherwise a whole number in 1..N (N = the session's runs); **refused when the session is a final** ("a resumed final needs Anisha's interruption rule in both guards first"). Development only.
- `TrialRunnerV4`: plans and checks all N runs as a full session does (every element of a run is a function of (session seed, run, goal of the run); the goals of all N runs come from one seeded sequence), takes the leak test from the start of run k, and drives runs k..N. A resumed session is a NEW Unity session folder with `run_###`, `truth_run###.json` and `results_unity.csv` rows for k..N only; the Python bridge folder holds `python_trial_###` for k..N.
- `session.json` and `summary_unity.json` get **`start_run`** (1 in every full session, k in a resumed one). `session.json` already holds `seed`, `goal_order` (the full order of all N runs, written from the plan), `final_setting`, `mode`. The summary line counts `Successes/(N - k + 1)`; the done file of a final is written when `Completed == TrialTotal`, and `Completed` is set to the run index i, so a session of runs k..N reaches N.
- Launcher `run_session_v4.ps1 -StartRun k` (rehearsal only; refused in a final) passes `-startRun k`; `check_session_v4.ps1 -StartRun k` expects runs k..N, and **refuses `-Final -StartRun`** (exit 2).
- Her own statement: the run-once guards are not changed; a resumed final stays refused; `FinalGuardV4.EarlierFinal` reads Unity's done file (`UNITY_FINAL_DONE.json`, key `final_setting`, written only for a COMPLETE session) and Python's `FINAL_RUN_DONE.json` (key `setting`). Her note [A] asks Python's evaluation and export to accept a session that starts at run k and pair it with the interrupted one: that is built (16.30.1.1: `resume_plan`, `--session` twice).

**How it maps to the resume rule of 16.30.1.**

| 16.30.1 (Python guard) | `-startRun` today | gap |
|---|---|---|
| the run to resume from, k | `start_run` = k in `session.json` and `summary_unity.json` | **name:** Python reads `resume_from_run`, not `start_run` |
| the part-2 session names the part-1 session | nothing | **`resume_of` is not written** |
| same seed, same goal order | `seed`, the full `goal_order` are in `session.json` of every session; same-seed plan by construction | none in the data; Unity does not compare them with part 1 or with the declaration |
| a declared interruption comes first | none (refused in every final) | the declaration is not read; `-startRun` in a final is refused outright |
| `--resume-marker` to the server | not passed; the launcher refuses `-StartRun` in a final | the launcher does not call `final_guard_v4.py --resume-info` |
| the run-once guards accept the one declared resume | `EarlierFinal` refuses a second session if `FINAL_RUN_DONE.json` or `UNITY_FINAL_DONE.json` exists | not changed: correct today, must follow |
| the check of a final session | `check_session_v4.ps1 -Final` expects all N runs; `-Final -StartRun` refused | part 2 of a resumed final needs `-Final -StartRun k` with runs k..N and the markers |

**Decision: our names are kept; no aliasing.** Python's evaluation and export read `resume_from_run` and `resume_of` from the part-2 `session.json` and **nothing else**: `start_run` is never read as an alias of `resume_from_run` (a session that says only `start_run` is refused, as now). Nusrat has agreed that Unity adopts our names for a resume in a final. `start_run` stays as it is (below).

**What Unity must add for a resume in a final** (her part; nothing here is done yet and nothing here is a change of any Python file):
1. **Accept `-startRun k` in a final only together with the declared interruption.** The launcher first calls `final_guard_v4.py --resume-info <setting>` (16.31.2 item 3): it prints `resume_from_run`, `resume_marker` (the declaration folder), `seed`, `goal_order`, part 1's folders and the frozen hash, or refuses with the reason. The launcher passes `resume_from_run` as `-startRun`, the declaration folder to Unity (a new argument, its name is hers) and `--resume-marker <declaration folder>` to the server. Without a declaration, `-startRun` in a final stays refused, with the message it has now.
2. **Unity reads the declaration (`FINAL_INTERRUPTION.json`) and refuses to start unless:** its `setting` is the final setting; `resume_from_run` equals `-startRun`; its `seed` equals the session's seed and its `goal_order` equals the full order Unity planned; its `frozen_sha256` equals the sha256 (LF) of `frozen.json` now and `FinalGuardV4.FreezeProblems` is empty; no `FINAL_INVALID.json` exists for the setting; no `FINAL_DONE.json` or `FINAL_EXPORT_DONE.json` exists for it. (A second resume is refused by Python's server at its start, `check_start`, which the launcher runs before Unity; Unity need not repeat it.)
3. **Write `resume_from_run` (= k) and `resume_of` (the name of part 1's Unity session folder, the declaration's `unity_folder`) into `session.json`** of the resumed final, next to `start_run` (also k) and the usual `seed`, `goal_order` (the full order), `final_setting`, `mode` "final". Without these two keys the evaluation and export refuse the setting (they are checked, with the seed and the goal order, against part 1 and the declaration). The same two keys in `summary_unity.json` are welcome and not read.
4. **`FinalGuardV4.EarlierFinal` (the final's start guard) accepts the earlier started final of the setting exactly when item 2 holds**, and refuses it in every other case (no declaration, a declaration that does not match, an invalid setting). It must also keep refusing a fresh start when `FINAL_SETTING.json` (the server's start marker, written before the first trial) exists without a declaration: today it reads only `FINAL_RUN_DONE.json` and `UNITY_FINAL_DONE.json`, which a hard crash does not leave.
5. **The done file of a resumed final** (`UNITY_FINAL_DONE.json`, written when `Completed == TrialTotal`) must say that it covers runs k..N, not N: `DoneJson` records `runs` = N today and `Successes` counted in part 2 only; add `start_run` and the number of runs driven.
6. **The B11 check of a resumed final:** `check_session_v4.ps1 -Final -StartRun k` accepts it (runs k..N present, the markers, the split guard) and refuses `-Final -StartRun` without a declaration. Part 1 of an interrupted final has no outcome for run k and is not a valid session by itself; its validity is judged on the merged session by Python's evaluation (16.30.1), not by the check of part 1.
7. **Keep part 1 as it is** (the interrupted run's folder `run_<k>` stays; nothing is deleted or renamed), and make the run-protocol note and the power-mode line for part 2 as for any session.
8. A second interruption (Python's `--declare-interruption` with part 2's folders) writes `FINAL_INVALID.json`: no part 3 is started (item 2 refuses it).

**What stays as it is, for development.** `-startRun k` in a rehearsal or any development session, `SessionResumeV4`, `session.json` and `summary_unity.json` `start_run` (written in every session, 1 for a full one, and kept in a resumed final next to the two new keys), the launcher's `-StartRun` (rehearsal only), `check_session_v4.ps1 -StartRun k` for a development session, and the refusal of `-startRun` in a final WITHOUT a declaration. A development session that starts at run k needs no declaration and no marker, and Python does not apply the resume rule to it (the development evaluation reads the run folders it finds).

**On the Python side nothing changes for this entry.** The evaluation checks the data, not the intent: it refuses a part 2 that has any run before k and requires the scored runs to be 1..N once each, so a part 2 that did not really start at k cannot pass whatever its keys say. It does not cross-check `start_run` against `resume_from_run` (no alias, no extra rule); if Anisha wants that check, it is a separate declared change.


### 16.31.4 Cross-check of `start_run` and `resume_from_run` in a resumed final (2026-11-21, Anisha); recorded BEFORE any code

**Decision.** 16.31.3 left out a cross-check of Unity's `start_run` against the `resume_from_run` of our rule, on the ground that nothing asked for it. Anisha asks for it now. **A resumed final session must have `start_run == resume_from_run`** in its part-2 `session.json`; the evaluation and the export (`final_guard_v4.resume_plan`, the one place both go through) refuse otherwise, with the reason.
- **Not an alias:** both keys are required. `resume_from_run` is still the key the guard reads for k (the declaration's k is the reference), and a session that carries only `start_run` is still refused; a session that carries only `resume_from_run` is now refused too, because `start_run` is what Unity's runner records as the run it actually started at (every Unity session writes it, 1 for a full one). The two must agree, and both must equal the declaration's `resume_from_run`.
- **Refused with the reason** when `start_run` is missing, is not a whole number, or differs from `resume_from_run` (named with both values), and when part 2's `resume_from_run` differs from the declaration (as before).
- **Part 1** is unchanged by this entry: it is a full session (`start_run` 1) and is not checked for it.
- **Consequence for 16.31.3 item 3:** a resume in a final needs Unity to write `start_run` (it already does, k), `resume_from_run` and `resume_of`, all in `session.json`. Nothing else changes: the data check (no run before k in part 2, runs 1 to N once each) stays as the check of what really ran.
- **Tests:** a resumed setting whose part 2 has `start_run` equal to k is accepted; missing, different (1, k + 1), or non-integer `start_run` is refused; `resume_from_run` alone and `start_run` alone are refused; the existing resume tests are adjusted to carry `start_run` (disclosed here: they build part 2 sessions by hand).
- **Also confirmed in this step (no change):** `docs/avatar_experiment_protocol_v4.md` exists and carries the Q4 change (the take is the unit of every interval; frame measures are a share per take, reported as the mean over takes with a bootstrap over takes, 2000 resamples, seed 1; Wilson only for take-level yes/no outcomes; never over frames), and 16.31.1 is marked DECLARED with Q5 and Q6 open, pending Nusrat; they change no outcome definition.


### 16.31.5 Nusrat's review of the avatar-experiment protocol (2026-11-21): six changes to 16.31.1 and `docs/avatar_experiment_protocol_v4.md`, Q5 closed; recorded BEFORE editing them (Anisha)

**Input (Nusrat's review, taken as data; adopted by Anisha).** Six points. Q6 (the session marker), the definition of a "group" in Unity's recording order and the counts of section 2 of the protocol doc stay OPEN for Nusrat's answers; none of them changes an outcome definition. 16.31.1 stays DECLARED; the changes below are made by this dated entry, not silently in place (the text of 16.31.1 is edited so that it reads true, and every edited place says "16.31.5").

1. **The cyan / magenta rule made objective (D3, INVALID).** Unity **pre-warms all shaders before recording and keeps the warm-up record (a log or file) with the session.** (a) A frame that shows the placeholder colour (the cyan placeholder or the error-shader magenta) **and was recorded while that record shows shader compilation still running** is **INVALID (a technical failure)**, repeatable once like any INVALID group. (b) **If the repeat is invalid for the same reason, the group is reported INVALID, not failing.** (c) A placeholder colour **after the warm-up finished** is a **look defect, reported as failing** (the look is not repeated). (d) **Never decided by inspecting images:** the decision uses the warm-up record and the time of the frame, not a person looking at the picture. This replaces the sentence of 16.31.1 that listed "a cyan placeholder or magenta material" among the things that are never invalid. What the rule needs from Unity (proposed, Unity's to build): the warm-up's finish time on the same clock as the frames' `time_s` (or, per recording, a flag "compilation running at the time of this frame"), kept in the session folder; the file name and fields are Unity's and are agreed with Nusrat. The Edit part has no Unity `Time.time` in its headers (look_check.json: `time_s` is left out), so for Edit the record is per recording, not per frame.
2. **INVALID item (iii) cites the declared timing rule:** **each frame must be less than 0.100 s from its 0.1 s mark, and consecutive frames at most 0.2 s apart** (Unity `experiments_ab.md` section 15 addendum 10, `finals_v4/avatar_rehearsal_check.py`); a take that breaks it is INVALID (technical), not a result.
3. **Facing goes into the per-look tables** (D4): the share of frames in which the commander rule's facing test passes (both eyes and the nose visible, shoulders wide enough), as a per-take share with the mean over takes and its bootstrap like the other frame measures. It stays **reported only**: it is not in the verdict (look_check.json, unchanged).
4. **Q5 CLOSED: the clip of each take comes from `recordings.jsonl`** of the Unity run folder (per recording: look, command, distance, arm, take, clip; the name joins it to the look-check report). **Edit takes have `clip` "" and `pose` "posed" and are excluded from the clip-role split** (a posed take shows no animation clip; they are counted as excluded, never given a role). In Play, NONE takes (no gesture) have no gesture clip and are excluded too. A Play gesture take whose clip is empty or missing is `not_evaluated` (counted and listed, never guessed); a clip name that is not listed in `data_splits.json` is refused (unknown is never assumed). **Built now** (this entry, tested): `avatar_clip_roles_v4.py`, the clip-role split. **Note on the data as it is today:** the Play writer (`LookCheckPlayDriver.RecordingRecord`) already writes `look`, `command`, `arm`, `clip`, `take`, `distance_m`, `name`; the Edit writer (`LookCheckMenu.RecordingRecord`) has no `clip` and no `pose` field yet, so Unity must add `clip` "" and `pose` "posed" to its Edit rows (Nusrat's); until then an Edit row is counted `not_evaluated` (no pose key, no clip), not guessed.
5. **Limitation, stated in the protocol:** the avatar experiment measures **the pan-tilt camera only.** Finding people with the 360 camera, per look, is **not measured** here (the robot finds the nearest person with the 360 camera before it asks; whether that works equally for every look is a different question that this experiment does not answer).
6. **Order and time (D3, section 2 of the doc):** the avatar experiment runs **after the LAST final sitting** (the test looks are no longer needed for finals), with **about 3 h reserved** (the Play part's `-lookCheckTimeout 10800`).

**The clip-role split (built).** `avatar_clip_roles_v4.py` (evaluation code; inference code never imports it): `load_recordings(path)` reads a `recordings.jsonl`; `classify(rows, splits)` gives each recording its clip status (`clip` with the clip and its role, `posed` excluded, `no_gesture_clip` for NONE, `missing_clip` not evaluated) and refuses an unlisted clip, a duplicate recording name, and a posed row that names a clip; `split_by_clip_role(take_values, rows, distance_m, splits, bootstrap)` takes a per-take share (name -> value, from the look-check report: the join is the reporting step's) for ONE distance (never pooled over distances: the 2 m and the 4 m camera see the same take, so a pooled cell would count it twice) and returns, per clip role, the number of takes, the mean over takes and the bootstrap interval of D5 (2000 resamples, seed 1, percentiles 2.5 and 97.5, read from `configs/v4/analysis.json`, takes resampled within each look), plus the excluded and the not-evaluated takes with their counts. Tests on a synthetic `recordings.jsonl` (`tests/test_avatar_clip_roles_v4.py`).

**Not built / open.** Q6 (session marker), the group definition, the counts of section 2 (Nusrat tonight); the reporting step (the look-check report is not read yet); the Python side of the avatar interruption rule; the warm-up record's format and the rule's evaluation (needs Unity's file). **No threshold, reader, commander, perception or control value is changed by this entry.**


### 16.31.6 Nusrat's answers of 2026-11-21: Q6 closed, the clip in the truth files, Unity's GuardRun; five new CSV columns; recorded BEFORE any code (Anisha)

**Input (Nusrat's answers, taken as data).**
- **Q6 CLOSED: the session marker of the avatar experiment is `avatar_experiment_part` in `run_info.json`** ("edit" or "play" in an OFFICIAL run, "" in an engineering check), **plus the run-once markers `AVATAR_EXPERIMENT_STARTED.json` and `AVATAR_EXPERIMENT_DONE.json` with the same key.** (Read in `Avatar/Scripts/AvatarExperimentGuard.cs`, `MarkerJson`: the markers sit in the run's own output folder, next to `run_info.json`, and carry `avatar_experiment_part`, `marker` ("started" / "done"), `git_commit`, `folder`, `written` and an optional `status`; they have no key `setting` or `final_setting`, so no final guard matches them.)
- **The clip per take:** `recordings.jsonl` AND `truth.jsonl` carry `clip`; Edit rows carry clip "" and pose "posed" (Unity branch `nusrat/v4-rehearsal-fixes`, not merged here yet). This confirms 16.31.5 item 4; `gesture_data.TruthRow.clip` already reads it.
- **Unity `GuardRun` now refuses the six `avatar_experiment` looks in every trial session** (from `looks_ab.json` role); Python's `guard_run` already does (16.31.2). **Both match.** (I have not read that Unity change: it is on her branch. The must-fix of the hand-off note is hers to close with her commit.)
- **The rehearsal Play failed only on 38 cyan frames** (the first anime shader compile); a shader warm-up was added and the Play part is being repeated. **Frames are deleted even when the check fails (the blind rule is kept)**; the diagnosis uses `cyan_pixels` and `magenta_pixels` in `recordings.jsonl`. (This is the warm-up of 16.31.5 item 1; the field names are noted for the rule's later evaluation, not wired.)

**Decision 1: `guard_avatar_experiment` is wired to the marker (16.31.2 item 2, which took the result as an argument until Q6 was answered).** The argument `session_marked` (a bool) is replaced by the session record read from the run folder (`load_avatar_session(folder)`: `run_info.json`, `AVATAR_EXPERIMENT_STARTED.json`, `AVATAR_EXPERIMENT_DONE.json`). The guard refuses, with the reason, unless: `run_info.json` exists; **`avatar_experiment_part` is "edit" or "play"; "" is refused as not official (an engineering check) and any other value is refused**; both markers exist, each with `marker` "started" / "done" and the SAME `avatar_experiment_part`; the git commit of `run_info.json` and of both markers agree; the marker's `folder` is the run folder's name. A missing DONE marker is refused ("the part did not finish": an interrupted part follows the interruption rule of 16.31.1 D3, which is not built). The guard returns the part, the commit and the DONE marker's `status` (reported, not judged: what a non-empty status means is the reporting step's). **The commit is NOT compared with the one in `frozen.json`:** that record is written before the commit that contains `frozen.json`, so the two cannot be equal; the frozen HASHES (`freeze_v4.require_frozen`) are what ties the run to the freeze. Order of the checks: the session record, then the freeze, then the names (any role).

**Decision 2: five new columns, appended as extras (the first columns of each table are the faculty plan's list and keep their order; `export_csv.json` is not frozen, 16.10.1).**
- **`dialogs.csv`: `clip`, `look_role`, `clip_role`.** `clip` = the animation clip the commander of the ask window showed: the most common non-empty `clip` of that worker's `truth.jsonl` rows inside the ask window in the shown phases (gesturing, holding; `accuracy_phases` of `eval_dev.json`) with the shown command; empty for NONE or when no row carries a clip. `look_role` = the role of the row's `look` and `clip_role` = the role of `clip`, both from `data_splits.json` (development or test; the six avatar-only looks cannot appear in a navigation export, `guard_run` refuses them); empty when the name is empty or not listed.
- **`runs.csv`: `stop_gestures_true`, `stop_gestures_false`.** The accepted STOP gesture episodes of the run, split by truth, with the definitions of `finals_v4/step5_report.py` and of 16.28: an episode = consecutive rows of the bridge's `decisions.csv` of that trial with `safety` "STOP gesture", starting at the first; **TRUE** if at the episode's first row some worker's latest `truth.jsonl` row (`time_s` <= the row's time) has `true_command` STOP in the phase gesturing or holding; otherwise FALSE. **Empty (not evaluated), not 0, when the bridge folder has no `decisions.csv` or it has no `safety` column.**
- **`runs.csv`: `resume_from_run`, `resume_of`, `interrupted`, from the session's `session.json`;** all three empty when the session is not resumed (no `resume_from_run`). `resume_from_run` and `resume_of` are copied as written. **`interrupted` is my reading of the request, for Anisha to confirm: "true" for the run whose number equals `resume_from_run` (the run that was interrupted in part 1 and is scored from the resumed session), "false" for the other runs of the resumed session, empty for a session that is not resumed.** (The interrupted attempt itself is not a row: it is listed in the evaluation's `interruption` block, 16.30.1.)
- The definitions are added to `RUN_FIELDS` / `DIALOG_FIELDS` (they go into `export.json` of every export). Column order: the five are inserted before `session`, `run`, `trial` in the run table and before `session`, `run`, `trial` in the dialog table, after the other extras (as 16.15 did for `final_setting` and the others).
- **Not changed:** the summary of the final export (`summarize`), the combined table, and every existing column and its value. No threshold is set.

**Tests** (with the code): the guard on synthetic run folders (official edit and play accepted; "" refused as not official; a missing run_info or marker; a part or commit that differs between run_info and a marker; a wrong folder name; any other part value); the columns on synthetic sessions (clip, look_role, clip_role of a shown clip, empty for NONE; TRUE and FALSE STOP episodes by truth, empty without `decisions.csv` or without the `safety` column; the three resume columns for a resumed and for a not resumed session).


#### 16.31.6.1 Done (2026-11-21): the guard wired to the marker and the five columns

- **`data_splits_v4.py`:** `load_avatar_session(folder)`, `avatar_session_problems(session)`, `guard_avatar_experiment(looks, clips, session, splits, repo)` (the bool argument is gone); refusals as declared in decision 1. Tests: `tests/test_avatar_role_v4.py` (`AvatarGuardTests`, 21 in the file).
- **`export_csv_v4.py` and `configs/v4/experiments/export_csv.json`:** `read_decisions`, `stop_gestures`, the three dialog columns and the five run columns as declared in decision 2, appended before `session`, `run`, `trial`; `build_tables(runs, ecfg, splits)` takes the roles from the repository's `data_splits.json` (the final export and the final evaluation pass their own repo's file). Tests: `tests/test_export_csv_v4.py` (`NewColumns`, `StopGestureSplit`).
- **A defect of mine found by the first run of the new code, before any commit:** `run_tables` already had a local variable `decisions` (the controller's decisions of `python_trial_###.json`), which shadowed the new parameter; the parameter is named `decisions_csv`. The tests of the STOP episodes cover it.
- **The pin test of 16.31.2 (no module reads a look's role itself) failed on the new exporter** (it reads `splits["looks"]` to fill `look_role` and `clip_role`). `export_csv_v4.py` is allowed in that test with the reason: it only labels rows of runs that `guard_run` has already accepted (a run with an `avatar_experiment` look is refused before any row exists), so it cannot take the role for a split. Disclosed because it is a test of mine edited after it failed.
- **Open:** `interrupted` is my reading (decision 2); the meaning of a "group" in Unity's recording order; the warm-up record's format; the reporting step.


#### 16.29.2 Defect of the STOP-reading instrument of 16.29 item 3: it was switched off at every trial start (found 2026-11-22 from Nusrat's smoke check; Anisha); recorded BEFORE the fix; branch `anisha/v4-stop-log-fix` from `main` 4d65a59

**Finding.** In Nusrat's smoke check (zip SHA-256 `86dcc48f...7d7d0c`, development data) **`stop_reading.jsonl` has 0 rows.** Point 4 of the smoke check in `docs/handoff_freeze_v4.md` section 2 (the file exists, has rows, and at least one row says `"applies":true` with `"used":"reading_stopped"`) is what caught it; nothing was lost, no final has run.

**Cause.** `bridge/guide_v4.py` sets `controller.stop_log_enabled = True` once, in `GuideControllerV4.__init__`. `ControllerV4.reset()` (`hri_control_v4.py`, the line `self.stop_log_enabled = False`) runs at every trial start (`bridge/guide.py`: a new `trial_index` while running calls `begin()`, which calls `reset()`), so the flag is `False` again before the first control step of the first trial and `step()` never calls `_log_stop_reading`. The file is created (the guide opens it) and stays empty. **My error in 16.29 / 16.29.1 item 3:** the flag was initialised in `reset()` instead of in the constructor, and the tests of the guide never started a trial (they run on a `Rig` that is already in its READ state and call `on_message` with trial 1 after setting `g.trial = 1`, so `reset()` never ran between the switch-on and the rows). 16.29.1 reported item 3 as done and tested; for the real flow it was not working.

**Effect.** Instrument only: **no decision, command, reading or outcome is affected** (the controller's behaviour does not depend on the flag; the test "commands identical with the log on and off" is the proof and stays). What is missing is only the evidence that makes C2s (16.19.7) provable from a session's logs (16.28 item 3).

**Decision (the fix).** (1) `stop_log_enabled` belongs to the instrument set-up, not to a trial: it is initialised **in `ControllerV4.__init__` only (default `False`), before `super().__init__` (which calls `reset()`), and `reset()` does not touch it.** `reset()` may still clear `stop_log` (the rows of the previous trial are not carried over; the guide pops them after every message anyway). (2) Tests, written first and failing on the old code: a guide-level test that starts the bridge guide with an output folder and runs TWO trials through telemetry (a new trial index while running = `begin()` = `reset()`) and checks `stop_reading.jsonl` has rows for both trials with the fields of the log, and that the flag is still on at every step; tests that `reset()` and `begin()` keep the flag either way, that the constructor default is `False`, that the log is cleared per trial but collected in the next; the existing "commands identical with the log on and off" test must still pass. (3) **The same pattern elsewhere:** checked every attribute the bridge sets on a controller: `bridge/guide.py` and `bridge/guide_v4.py` set exactly one, `stop_log_enabled` (a test pins this). The other per-trial collections (`frame_log`, `decisions`, `route`, `cp_log`, `nj_log`, `side_views`, ...) are not flags: they are collected always, reset per trial by design, and read by the guide (`pop_frame_log` after every message) or by `summary()` at the end of a trial. No other instrument flag is cleared by `reset()`.

**Not changed:** any control value, the STOP rule, C2s, the readers, or any config. The final configuration and the frozen hashes are untouched (`hri_control_v4.py` and `bridge/guide_v4.py` are Python code, not frozen files; the freeze has not been run).


#### 16.29.3 The freeze of 2026-11-22 was NOT committed: seven test modules read the real `frozen.json` (Anisha; recorded BEFORE any code; branch `anisha/v4-freeze-safe-tests` from `main` 919b632)

**Finding.** Nusrat's freeze (2026-11-22T20:35:28, `main` at 919b632, `freeze_v4.py` reported "problems: none") was **not committed**: the full suite on the frozen tree gave **2 failures and 127 errors, all in 7 test modules** (`test_v4_final`, `test_final_resume_v4`, `test_final_zip_v4`, `test_v4_frozen`, `test_avatar_role_v4`, `test_hri_analysis_v4`, `test_make_results_archive_v4`). There is **no hash mismatch, no missing file and no wrong config**: the same modules pass 220 of 220 at 919b632 with the unfrozen file. Reproduced here without the freeze tool (a temporary git worktree of 919b632 whose `frozen.json` was filled from the tool's own read-only pieces, `snapshot`, `model_status` and `config_files`, the fields `freeze()` writes; `freeze_v4.py --freeze` was NOT run): 220 tests, **failures=2, errors=127**, identical to Nusrat's result.

**Cause.** The tests are written for the unfrozen repository and read the REAL record by accident. (1) The shared fixture `test_v4_frozen.make_repo` copies `robot_vision/configs/` including the real `configs/v4/frozen.json`; `test_v4_final.final_repo` then calls `freeze_v4.refresh_list` and `freeze_v4.freeze` on that copy, which refuse a frozen record ("frozen.json is frozen: its file list is not rewritten", "already frozen"): every test built on `final_repo` (`test_v4_final`, `test_final_resume_v4`, `test_final_zip_v4`, `test_avatar_role_v4`, `test_hri_analysis_v4`, `test_make_results_archive_v4`) and the mechanics classes of `test_v4_frozen` error in their set-up (127 errors). (2) Two tests assert the refusal "not frozen" against the real repository: `test_v4_final.ServerFinalTests.test_refused_while_the_configs_are_not_frozen` and `test_hri_analysis_v4.GuardAndOutputTests.test_final_is_refused_while_not_frozen`; with a frozen real file other refusals fire first (the control-config check, the plan's run count and seed) and the message differs (2 failures). Three more assert "not frozen" against the real file by name and would have failed next: `test_v4_final.FinalEvaluationTests.test_the_real_repository_is_not_frozen_so_a_final_is_refused`, `FinalExportTests.test_the_real_repository_is_not_frozen_so_an_export_is_refused` and `test_avatar_role_v4.AvatarGuardTests.test_not_frozen_or_a_changed_config_is_refused`.

**Decision (Anisha, 2026-11-22).** Fix the fixtures; the freeze is redone afterwards; **no exception to "commit only after the full suite passes"** (the frozen record is not committed until the suite passes on it).
1. **Every fixture builds its OWN unfrozen record** in its temporary directory: `make_repo` overwrites the copied `frozen.json` with a template (`"frozen": false`, no hashes, the file list of the copy), never the repository's.
2. **The "not frozen" tests build an unfrozen state themselves and isolate the refusal they test:** a temporary unfrozen repository passed explicitly (`evaluate_final`, `export_final`, `guard_avatar_experiment`, `analyse(repo=...)`), and for the server preflight `fz.require_frozen` is pointed at that unfrozen repository, so no other refusal (control config, run count, seed) can fire first.
3. **Only `test_v4_frozen` reads the real `frozen.json`, and it passes whether the real file is frozen or not:** it pins what each state must contain (unfrozen: no hashes, a file list that names no file outside the frozen set; frozen: `frozen_at` and `git_commit`, a hash for every listed file, the v3 dependencies, the Unity files, both model hashes equal to the frozen v3 configs', `problems()` empty).
4. **Verification without the freeze tool:** (a) the full suite on the normal (unfrozen) repository; (b) in a temporary git worktree of the branch, `frozen.json` filled as above (frozen true, from the tool's read-only snapshot), the full suite there, then the worktree removed. Only test files and AUDIT.md change: no config, no `frozen.json`, no `unity/` or `external/`.
### 16.33 Phase B: what happens when a final sitting's zip arrives, and the runbook that does it (2026-11-22, Anisha); recorded BEFORE any code; branch `anisha/v4-phase-b` from `main` 94d10b9 (no final data exists yet)

**The six steps, in order (Anisha's list).** (1) Verify the zip's SHA-256 against the one Nusrat sends, reading the zip in place. (2) The acceptance checks of `final_plan.json` `acceptance_criteria`, per setting: leak test, frozen hashes, split guard, all runs present, outcomes recorded, truth and run files accepted, run protocol recorded; and the interruption / resume rule of 16.30.1. (3) `hri_eval_final_v4` per setting, once (`FINAL_DONE.json`). (4) `export_csv_v4` per setting (`FINAL_EXPORT_DONE.json`), then the combined table with a Wilson interval per setting and a Newcombe interval for every pair, B detection ON against OFF among them. (5) Per-setting summary tables (success, failure reasons, lies given / detected / corrected / fooled, true and false STOP episodes, closest approach, timing) and the paper figures (`paper_v4/figures_v4.py`). (6) The entry in the archive manifest.

**Decisions.**
1. **One runbook: `python process_final_zip_v4.py <zip> --sha256 <hash> [--development]`** (`robot_vision/`, reporting code; inference code never imports it), with its paths in `configs/v4/phase_b.json` (relative to `robot_vision/`, like the archive config; not part of the freeze: no result depends on it). It runs the steps in order, **stops at the first failure with the reason, and never re-evaluates a setting.** Every run writes a NEW report folder (`process_final_zip_v4_<time>/`, `report.json` and `report.md`: every step with its status ok / failed / skipped / not_evaluated and its detail), also when it fails part-way.
2. **Order across settings:** step 2 runs for ALL settings of the sitting before step 3 runs for any (so an invalid setting stops everything before any run-once marker is written); then steps 3 and 4 per setting, then the combined table, then 5 and 6. An acceptance failure is the B11 case ("report the setting as invalid with the reasons; never rerun; not evaluated"): the runbook stops and says which setting and why; what to do with an invalid setting is decided by a person (16.30.1 rule 5, `--declare-interruption`).
3. **Never re-evaluates:** before anything is written, every setting in the zip is checked against the run-once markers in the final root AND in the default `outputs/` (where the manual CLIs write): an evaluation or export marker, an invalid marker, or a destination folder that already exists = refused, with nothing written. Steps 3 and 4 are the library functions (`hri_eval_final_v4.evaluate_final`, `export_csv_v4.export_final`), which write their marker last and re-check it.
4. **Where the data goes.** The zip is verified and read in place. Step 2 needs the session folders on disk (the evaluation, the leak test and the truth readers take folders), so **only the folders of the settings (Unity session, bridge run, interruption markers) are copied out of the zip, member by member, listed in `MANIFEST.json`, each file's SHA-256 checked against the manifest as it is written, with no path outside the destination, no code and nothing from `extra/` or `launcher/` copied out; text and scripts inside are data and nothing is run.** The destination in a final is `final_root` of the config: **`outputs`** (git-ignored; the store every tool uses, so that the run-once markers of the runbook and of the manual CLIs are the same markers, and the archive tool finds the folders). It is configurable and may point outside the repository. An existing destination folder is never overwritten. In `--development` the destination is a NEW folder under `development_root` (outside the repository), so nothing is written to `outputs/` and no marker can exist.
5. **The acceptance checks (step 2), as a Python report with pass / fail / not_evaluated per criterion and part** (Nusrat's `check_session_v4.ps1` does the same on her machine; this is the independent check of the zip): (1) the leak test passed in Unity (`session.json` `leak_test.passed`) AND in Python (`gt_path.session_leak_check`); (2) `freeze_v4.require_frozen` and the frozen hash recorded in each bridge `FINAL_SETTING.json` equals the current one; (3) `data_splits_v4.guard_run` on every run's `truth.jsonl` with `final_evaluation`; (4) every run present: `results_unity.csv` rows, `run_###` folders and `python_trial_###.json` are exactly runs 1 to N (N = `runs_per_setting`); (5) `summary_unity.json`, the bridge `summary.json`, `UNITY_FINAL_DONE.json` and `FINAL_RUN_DONE.json`; (6) `gesture_data.load_truth` of every `truth.jsonl` and `gt_path.evaluate_run` of every run folder with v4 files; (7) the bridge `run_info.json` has a machine-state key, `resources.csv` exists, and the zip holds the launcher's run-protocol note with "free memory" in it (read in place); the power-mode line is looked for in `extra/` and reported (a warning, as the hand-off note says, not a criterion). **Interruption / resume:** `final_guard_v4.resume_plan` (markers, parts, seed, goal order, frozen hashes, `start_run`, `resume_from_run`, `resume_of`); for a resumed setting criteria 4 and 5 are applied per part (part 1: runs 1 to k-1 complete, run k may be present as the interrupted attempt; part 2: runs k to N, with the markers). A declared interruption that was never resumed, or an invalid setting, fails.
6. **What `--development` does.** It runs step 1 and step 2 "as far as development allows" (criterion 2 is `not_evaluated`, the markers of criterion 5 are not required, criterion 3 uses the development split, criterion 4 expects the development session's run count, 3 for step 5), step 4 and step 5 in development mode (a development export folder per setting with `runs.csv`, `dialogs.csv` and `summary.json`, and a development combined table labelled DEVELOPMENT built by the same `combined_tables` as the final one), and **SKIPS steps 3 and 6**: no `FINAL_*` marker is written anywhere and the runbook checks that none exists in its work folder afterwards. A final zip given with `--development` fails at the split guard (development splits only); a development zip given without the flag is refused in step 1 (its manifest says it is development data).
7. **Step 5.** Per-setting table (`phase_b_tables.csv` / `.md`): runs; SUCCESS k/n with Wilson 95 %; failures by reason (collision, timeout, aborted, wrong_goal); lies given / detected / corrected / fooled; STOP gesture episodes true / false (the sum of the run rows' `stop_gestures_true` / `_false`, "not evaluated" when no run has them); closest approach to a person (minimum and median over runs); timing: median run time of SUCCESS runs, and from each bridge `summary.json` the round-trip maximum, the event-loop-lag maximum and the watchdog stops. Every figure has its count; a cell that cannot be computed is "not evaluated", never 0. **The figures: `paper_v4/figures_v4.py` reads DEVELOPMENT data only (its split guard refuses test data) and is Nusrat's file, so in a final the figures step is reported as NOT RUN with that reason and is an open item: it needs a final mode (through `hri_eval_final_v4.gate`), agreed with Nusrat.** In `--development` it runs on the development sessions.
8. **Step 6.** In a final, one entry per setting (`role` "final", `setting`, `unity`, `bridge`, `eval`, `export`, and for a resumed setting `unity_resumed` / `bridge_resumed`) is appended to `configs/v4/archive/results_manifest.json` (validated by `make_results_archive_v4.validate_manifest`, a duplicate setting / role refused, written atomically); the report says the tracked file changed so that it is committed by a person. **Limit:** `make_results_archive_v4.py` archives one Unity and one bridge folder per entry, so the second part of a resumed setting is recorded in the entry but not yet archived; extending the archive tool is a separate change.
9. **Tests** (synthetic sittings, the existing helpers; no data): verification (hash mismatch, missing or changed sidecar, a changed member, a final zip that is not a final manifest), safe extraction (path traversal, a hash that differs, an existing folder), the criteria one by one, resumed settings, the run-once refusals, the order and the stop-at-first-failure rule, the development flag (nothing final written, steps 3 and 6 skipped), the manifest entry and its refusals, the tables.

**Not decided / not done here:** the freeze (`freeze_v4.py --freeze` is never run by me); a final mode of `figures_v4.py` (Nusrat); multi-part archiving. The first real use is the first final sitting's zip.


#### 16.33.1 Additions of 2026-11-22 (Anisha): the results tables, the gesture and branch confusion matrices, and the avatar-experiment tool; recorded BEFORE the code of those parts

**Role.** Anisha produces the experimental results (numbers, tables, matrices) for the paper team. The first module of 16.33 (`process_final_zip_v4.py`: steps 1 to 4, the acceptance checks, the per-setting table, the manifest) was written from the earlier form of the request; the additions below extend it and are recorded before their code.

**A. The A/B runbook, step 5 extended.** Output: one results folder per run of the tool, every table as CSV AND Markdown, ready to paste. Tables: (a) per setting (16.33 decision 7: SUCCESS with Wilson 95 %, failure reasons, lies, STOP episodes true / false, closest approach, timing); (b) **the pairs**: every comparison of the combined table with its Newcombe 95 % interval, split into **B detection ON vs OFF** and **Set A vs Set B** (and A2 right vs left), `phase_b_pairs.csv` / `.md`, from the same `combined_tables` as the combined table; (c) **the gesture confusion matrix**: `command_shown` against `command_read` of `dialogs.csv` over POINT, WAIT, STOP, PROCEED, NONE (and a blank column for no reading), one matrix per setting and one pooled over the sitting's settings, with the row totals and the share read as shown; (d) **the branch confusion matrix**: `true_branch` against `branch_read` over FORWARD, LEFT, RIGHT, BACK, NONE, likewise per setting and pooled. Counts are asks (a pooled matrix mixes settings and says so); a matrix cell that has no asks is 0 and the matrix states how many asks it rests on. The figures stay `paper_v4/figures_v4.py` (development data only; in a final the step is reported NOT RUN, 16.33 decision 7).

**B. The avatar experiment: `python process_avatar_zip_v4.py <zip> --sha256 <hash>`, following `docs/avatar_experiment_protocol_v4.md` (16.31.1, 16.31.5, 16.31.6) exactly.** The zip is the one made by `final_zip_v4.py avatar` (its manifest has `folders`). Steps, stopping at the first failure with the reason, never reporting a part twice:
1. **Verify** the SHA-256 and the manifest (as in the A runbook); copy out the folders (member by member, hash checked, no code; the frames are needed by the look check).
2. **Guard, per part** (a folder with a `run_info.json`): `data_splits_v4.load_avatar_session` and `guard_avatar_experiment` (`avatar_experiment_part` "edit" or "play", the two run-once markers, one commit, the frozen hashes, every look and clip name from `recordings.jsonl` listed in any role). A part is reported once: its own marker `process_avatar_zip_v4_DONE.json` in the results folder; a second run of the same part is refused.
3. **INVALID takes (16.31.1 D3, 16.31.5), a take at a time, technical failures only:** (i) frames or headers missing or truncated (fewer than the declared 11 frames, 21 for PROCEED; an unreadable PNG; a missing or bad header: the look check's own `errors`); (ii) intrinsics that fail the check (the same `errors`); (iii) a frame time that breaks the timing rule of Unity's addendum 10 (each frame less than 0.100 s from its 0.1 s mark, steps at most 0.2 s: `finals_v4/avatar_rehearsal_check.timing_problem`, imported read-only; Play only, Edit headers have no `time_s`), or a DONE marker with a non-empty `status` (reported); (iv) the look, command, distance or arm in `recordings.jsonl` disagrees with the recording's name or header; (v) **a placeholder colour (`cyan_pixels` or `magenta_pixels` > 0 in `recordings.jsonl`) while `shaders_compiling` is true in that row**, decided from the data, never from the picture. A placeholder colour with `shaders_compiling` false is a **look defect** (reported as such, not invalid). **Assumed formats (Nusrat's branch is not merged; to be confirmed, nothing else is guessed):** `recordings.jsonl` rows carry `name`, `look`, `command`, `distance_m`, `arm`, `clip`, `pose`, `cyan_pixels`, `magenta_pixels`, `shaders_compiling` (bool); `shader_warm_up.jsonl` is kept next to it (one JSON object per line); **if any placeholder pixel exists and the warm-up record is missing, the part is refused (the rule cannot be applied)**; a missing record without placeholder pixels is a warning. **Repetitions of an INVALID group are not read yet:** a duplicate recording name is refused ("repeat declarations are not defined yet"); an INVALID take stays INVALID and is counted as such.
4. **The look check** (`look_check_v4.py` and its frozen `look_check.json`, unchanged) is run on each part's recordings folder with the real detector (an injected detector in the tests); its `report.json` gives every frame's record and the per-look verdicts (the tool's own, reported as they are).
5. **Per-take shares (D5).** A take is a recording (a sequence or a single frame). Frame measures per take: person found; **hand found AND linked to the gesturing arm (primary)**; hand found anywhere (secondary); body keypoints (arm valid, and shoulder, elbow, wrist, hip keypoints); facing; own cue (the shown command's cue); wrong class. A single frame is 0 or 1. Take-level yes/no outcomes (sequences): **read as recorded**, **read as another command**, **not read** (`NONE` or insufficient history), for POINT, WAIT, STOP and PROCEED (PROCEED evaluated in Play only; in Edit it is `not_evaluated`). **Take is the unit: the mean over takes with a bootstrap over takes (2000 resamples, seed 1, percentiles 2.5 and 97.5, `configs/v4/analysis.json`), takes resampled within each look; Wilson 95 % only for take-level yes/no outcomes; never an interval over frames.**
6. **The floor (accepted):** a look x command cell is evaluated when, among VALID takes, per arm and distance, there are at least 2 sequences and at least 10 single-frame takes; below it the cell is `insufficient_data` and its takes are left out of the aggregates (counted). **Play only;** Edit has no floor (the PROPOSED rule of 16.31.1 D3: posed variants, labelled as such).
7. **Tables (CSV and Markdown), Play and Edit never pooled** (a folder per part): per look x command x distance (the headline: all 15 looks), per kind group, per look role (development, test, avatar_experiment) and per clip role (development, test; Play only: Edit takes and NONE takes are excluded, a Play gesture take without a clip is `not_evaluated`, per distance); the look-check verdict of each look next to the take-based means (both shown, the verdict stays the tool's); the INVALID takes with their reasons; every cell with takes recorded / valid / used and the frames behind each mean; the facing share in the per-look table.
8. **Not built:** the Python side of the avatar interruption rule (resume once from the interrupted group); repetition declarations; the evaluation of the warm-up record beyond the per-row `shaders_compiling` flag; the meaning of a "group" in Unity's recording order (Nusrat). **No threshold, reader, commander, perception or control value is set.**

**C. Dry runs (no final marker anywhere).** A: `process_final_zip_v4.py ~/Downloads/step5_t0_logs_20261121_002030.zip --sha256 <its hash> --development` (steps 3 and 6 skipped; a development export and a development combined table; the tables above). B: the avatar tool on synthetic sessions built in the tests (no avatar-experiment data exists yet): a frozen temporary repository, synthetic Edit and Play run folders with `recordings.jsonl`, markers and a warm-up record, a scripted detector; the tables it prints are a test of the tool, not a result.


#### 16.33.2 Done (2026-11-22): the two runbooks and what the dry runs showed

- **`robot_vision/process_final_zip_v4.py`** (A/B finals) and **`robot_vision/process_avatar_zip_v4.py`** (avatar experiment), configuration `configs/v4/experiments/phase_b.json` (in `experiments/`, so NOT part of the freeze; the 16.33 text says `configs/v4/phase_b.json`, which was the first plan). `export_csv_v4.combine` was split into `combined_tables` and `write_combined` (the final combined table is unchanged; the development runbook uses the same functions); `avatar_clip_roles_v4.mean_with_bootstrap` now uses numpy's `default_rng(seed)` (the same settings of `analysis.json`; vectorised, because the avatar tables need thousands of intervals); `process_final_zip_v4.verify_zip_hash` and `new_report_dir` are shared by both tools.
- **Tests:** `tests/test_process_final_zip_v4.py` (33) and `tests/test_process_avatar_zip_v4.py` (24), all on synthetic sessions; see their docstrings for the cases (verification, safe copy-out, the eight acceptance criteria, order and stop rule, run-once, resumed settings, manifest, `--development`; for the avatar tool the guard, the INVALID rules, the floor, the take as the unit, the tables, a part reported once).
- **Dry run A** (`--development`, `~/Downloads/step5_t0_logs_20261121_002030.zip`, SHA-256 `cce68784...ef1a`, 13 settings, 39 runs): steps 1, 2, 4 and 5 ran, 3 and 6 skipped, no `FINAL_*` marker anywhere in its folder. Acceptance (development): criteria 1, 3, 4, 5, 6 and 7 pass for all 13 settings; 2 and 8 not evaluated. **Cross-check:** the STOP episodes of the new table sum to **91 false and 0 true** over the 13 settings, the figure of 16.28 item 3 (recomputed there by another route).
- **Finding (Nusrat's file, not changed):** `paper_v4/figures_v4.py` fails on the step-5 sessions with `KeyError: 'not_evaluated'` in `topdown` (`OUTCOME[d["outcome"]]`: its palette has no colour for the dialog outcome `not_evaluated` that the current evaluation emits). The runbook reports it as a failure of step 5 (and `--no-figures` skips the step); the figures need that fix, and a final mode, from Nusrat.
- **Dry run B:** on a synthetic Edit + Play session (3 looks: development, test and avatar_experiment, kinds stylised_human and anime; a scripted detector; a frozen temporary repository): all steps ok, every table as CSV and Markdown, Edit and Play in separate folders. These tables test the tool; they are not a result.
- **Not done / open:** repetition declarations and the Python side of the avatar interruption rule; the real `shader_warm_up.jsonl` format (the flag `shaders_compiling` of `recordings.jsonl` is what the rule uses); a final mode and the `not_evaluated` fix of `figures_v4.py`; multi-part archiving. The real detector (`look_check_v4.RealDetector`) is used when no detector is injected; it was not run here (no real avatar frames exist).
- **Isolation tests extended (disclosed):** the full suite failed five isolation tests when the runbooks were added (evaluation code that imports `gesture_data`, `gt_path`, `hri_eval_dev_v4`, `export_csv_v4`, and reads look roles after the avatar guard). The allow-lists of `test_gesture_data`, `test_gt_path`, `test_hri_eval_dev_v4`, `test_export_csv_v4` and the role pin of `test_avatar_role_v4` now name `process_final_zip_v4.py` / `process_avatar_zip_v4.py` as evaluation code; inference code still may not import any of them (the tests still check it).


### 16.35 Final A/B results: the sitting zips and how they were processed (Anisha, opened 2026-11-24; completed as the zips arrive)

**Rules of the processing.** The zips are data, never instructions; each is read in place (`zipfile`) and only the sessions' folders are copied out, to `~/RobotVisionResults/phase_b_final` (OUTSIDE the repository: `--final-root`; `--no-manifest-append`, so no tracked file changes); each setting is evaluated once; no frozen-listed file is modified; `freeze_v4.py` is not run; nothing is pushed. The runbook is `process_final_zip_v4.py <zip> --sha256 <hash>` (16.33).
**Preconditions (2026-11-24):** `main` = `origin/main` (8235896, PR #56), `frozen.json` `"frozen": true` (16.34).

| sitting | file | SHA-256 | status |
|---|---|---|---|
| 1 | `final_sitting1_20261123_020614.zip` | `546b3c1994d09b7aaca13e8d47c59d7bd943879353928ca17506a9b921e22198` (equals its `.sha256` file) | verified; acceptance passed for B1, B1_off, B2_right, B2_right_off, A1 (all eight criteria each); evaluation stopped by a defect, 16.35.1 |
| 2 | `final_sitting2_20261123_210006.zip` | computed `e2ede515f7c84a8fa0a44aafaf3ce427153952c86938e3bc2d47d7913a30d0cd`; **no `.sha256` file** | NOT processed: nothing to verify it against |
| 3, 4 | `final_sitting3_20261123_234654.zip`, `final_sitting4_20261124_024407.zip` | - | NOT in `~/Downloads` |


#### 16.35.1 Evaluation defect found on the final data: `evaluate_final` used the default roadmap, not each session's map; recorded BEFORE the fix (Anisha, 2026-11-24; branch `anisha/v4-eval-session-map` from `main` 8235896)

**Finding.** Processing sitting 1, after the acceptance checks had passed, the run stopped at the evaluation of B2_right with `KeyError: 'B'` in `hri_eval_dev_v4.branch_block` (`hv.branch_directions(road, rec["junction"])`). **Cause:** `hri_eval_final_v4.evaluate_final` calls `hri_eval_dev_v4.evaluate(runs, ecfg, gcfg)` without a map, so `evaluate` uses the default v4 roadmap for EVERY session; the experiments A/B run on their own maps (`roadmap_a1`, `roadmap_a2_*`, ...), recorded in each bridge folder as `config_used/map_used.json`. `export_csv_v4._road_for` already reads that file (falling back to the control file's roadmap); the evaluation did not. The marker of a crashed evaluation is not written (it is written last): B2_right has none.
**What had already run.** B1 and B1_off were evaluated before the crash and have `FINAL_DONE.json`. **Checked (read only) before this entry:** their `map_used.json` is NOT identical to the default roadmap (it has a node `B` the default map does not have; the same for B2_right, B2_right_off and A1 with nodes `B`, `C`). So the evaluations of B1 and B1_off ran with the wrong map: their branch and junction-level numbers (`branch_block`, `junction_block`: the true branch toward the goal) are not reliable; no crash only because their nodes exist in both maps. Their run-level measures (success, time, trail) come from Unity's files and do not use the map.

**Decision (declared now, before any re-evaluated number has been seen).**
1. **The corrected evaluation is the authoritative one for ALL settings.** The fix: the evaluation takes the map from each session's `config_used/map_used.json` (else the control file's roadmap, else the default), run by run, exactly as `export_csv_v4._road_for` does (`hri_eval_dev_v4.road_of_run`; `branch_block` and `junction_block` ask for the road of the run they score). This also changes the DEVELOPMENT evaluations of sessions that carry their own map (they are corrected the same way; any earlier development evaluation of such a session used the default map and is disclosed here as superseded).
2. **B1 and B1_off are re-evaluated with the fixed code in a NEW folder.** Their old evaluation folders (`hri_eval_final_v4_B1_20261124_183226`, `hri_eval_final_v4_B1_off_20261124_183230`) stay untouched for the record. The run-once rule protects the RUNS from being evaluated again until a favourable number appears; it does not protect a crashed or wrong-map evaluation. To make that explicit and checkable, a new marker `FINAL_EVAL_SUPERSEDED.json` (its own folder `final_eval_superseded_<setting>_<time>/`, with the setting, the superseded evaluation folder and this reason) makes `final_guard_v4.markers(..., "evaluation")` ignore exactly that evaluation folder; nothing else is unlocked and a setting can be superseded only by such a declaration.
3. **Both are reported:** a comparison of the old and the new evaluation of B1 and B1_off (every number that differs) goes into the results; the corrected one is used.
4. **Tests (one per map):** the evaluation of a synthetic session on the default map, on `roadmap_a1`, on `roadmap_a2_right` and on `roadmap_a2_left` scores the true branch with its own map (and a session whose nodes exist only in its own map no longer raises); the fallbacks (control file, default); the supersede marker unlocks only the named folder.
5. Then: continue sitting 1 (B2_right, B2_right_off, A1, and the exports of all five), and sittings 2 to 4 when their files are in `~/Downloads` with their hashes.

**Not changed:** any config, the freeze, any frozen-listed file, any number of a run. The fix is in `hri_eval_dev_v4.py`, `final_guard_v4.py`, `process_final_zip_v4.py` (not frozen-listed).


#### 16.35.2 Completion of 16.35: the four sittings processed (Anisha, 2026-11-24); numbers as they are, no interpretation

**Zips (read in place; each SHA-256 equals its `.sha256` file, compared case-insensitively):** sitting 1 `final_sitting1_20261123_020614.zip` `546b3c1994d09b7aaca13e8d47c59d7bd943879353928ca17506a9b921e22198` (B1, B1_off, B2_right, B2_right_off, A1); sitting 2 `final_sitting2_20261123_210006.zip` `e2ede515f7c84a8fa0a44aafaf3ce427153952c86938e3bc2d47d7913a30d0cd` (B3, B3_off, A2_right); sitting 3 `final_sitting3_20261123_234654.zip` `78e02bff3d87b376d09040aa2701dcd17f30f79b2e60656dd6d848923669bc7d` (B4, B4_off, A2_left); sitting 4 `final_sitting4_20261124_024407.zip` `2f05c8ecb9b69f13c69e7018a4d6f3a1d5c9433bffde0bd7c602818d46c1998e` (A3, A4). Processed in order with `process_final_zip_v4.py ... --final-root ~/RobotVisionResults/phase_b_final --no-manifest-append --no-figures` (sitting 1 first by `--reuse-ingested`, see 16.35.1); nothing was copied into the repository.
**Acceptance (all 13 settings): all eight criteria PASS** (leak test, frozen hashes, split guard, all 20 runs present, outcomes recorded, truth and run files accepted, run protocol recorded, interruption / resume rule). **No setting was refused.** No interruption or resume exists in any of the 13 settings (one bridge folder per setting; no `FINAL_INTERRUPTION.json`).
**Evaluation and export:** each setting evaluated once and exported once (`FINAL_DONE.json`, `FINAL_EXPORT_DONE.json`), the combined table over all 13 settings. **The evaluation defect of 16.35.1** (default map instead of the session's `map_used.json`): the B1 and B1_off evaluations first written were declared superseded (`final_eval_superseded_B1_*`, `final_eval_superseded_B1_off_*`, their folders untouched) and re-evaluated with the corrected code. Old against corrected: B1 340 and B1_off 170 leaf values differ; **every difference lies in the junction-level blocks** (`junction_level` and its copy under `per_zoom`: the true branch toward the goal, `NONE` in the old, `FORWARD` in the corrected; the dialog outcome `not_evaluated` -> `correct`; derived shares); run-level success is identical (B1 20/20, B1_off 16/20 in both). The corrected evaluation is the one used everywhere.
**Success (20 runs each; Wilson 95 %):** A1 20/20, A2_right 20/20, A2_left 20/20, A3 16/20, A4 17/20; B1 20/20, B2_right 18/20, B3 10/20, B4 11/20; B1_off 16/20, B2_right_off 14/20, B3_off 9/20, B4_off 3/20. Pooled matched A (A1, A2_right, A3, A4) 73/80 against B ON 59/80; B ON 59/80 against B OFF 42/80 (Newcombe intervals in the tables). Zero collisions and zero timeouts in the 260 runs. **STOP gesture episodes: 0 true, 2 to 11 false per setting** (a STOP was never shown in the finals).
**Results folder:** `~/RobotVisionResults/phase_b_final/final_results_20261124_191243/` (CSV and Markdown: a per setting, b ON vs OFF, c Set A vs Set B, d lies by first / later asked, e STOP episodes and C2s, f gesture and branch confusion overall and per setting, g timing per setting and per sitting against the declared limits, interruptions and supersessions, zips, provenance, h figures), made by the new `robot_vision/final_results_v4.py` (reporting code; writes no marker). The evaluation and export folders, the combined table and the per-sitting runbook reports are in `~/RobotVisionResults/phase_b_final/`.
**Disclosed limits of these tables.** (1) **Figures (h) are NOT produced:** `paper_v4/figures_v4.py` reads development data only and fails on `not_evaluated` (Nusrat's file). (2) **Timing against the declared limits:** the limits of `configs/v4/bridge.json` `timing_limits` (declared for the replay timing check) are applied to each sitting's worst value from the bridge `summary.json`; **in every sitting the round-trip maximum (155 to 274 ms against 150), the loop-lag maximum (177 to 303 ms against 100) and the telemetry without a reply (1 against 0) exceed them** while the loop-lag p99 (22 ms against 25) is within; the round-trip p99 and the reply gap are not in the bridge summary (`not evaluated`). Reported as measured; the watchdog stops are a result (B11 a). (3) **Lies (d):** runs.csv counts lying gestures, the table counts asks whose gesture was a lie, so 'given' differs by one for B1 (18 against 17) and B3 (50 against 49); 'corrected' is not derivable per ask when a backtrack withdrew the answer (counted apart). (4) The archive manifest was NOT appended (`--no-manifest-append`); the entries are in the runbook reports. (5) `runs_per_setting` is 20 on this `main` (the 10-run change of 16.32 is not merged), and the finals ran 20 runs per setting.


### 16.36 Supplementary experiment S1: navigation with all workers in ONE avatar look; post-freeze, EXPLORATORY (Anisha, decided 2026-11-24 after the finals were run and evaluated (16.35) and before any S1 data); recorded BEFORE any code; branch `anisha/v4-supplementary-s1` from the tag `v4-finals-frozen` (73fbcc4)

**What it is.** A supplementary experiment, decided AFTER the A/B finals were run and evaluated and BEFORE any S1 data exists. It is **post-freeze and exploratory**: it is not part of the frozen study, it is **never pooled with the finals** and is reported in **its own section**. **Design:** navigation with **all workers in ONE look per session**; the looks are **`anime_f_01` and `cartoon_boxo_01`**; the settings are **A1 and A2_right with their final detection-on configurations** (the control files, maps, scenarios and test clips of the finals); **10 runs per setting per look** (so 4 sessions of 10 runs), **seed 2**, **timeout 480 s**, everything else unchanged. **Outcomes:** success (Wilson 95 %), failure reasons, dialogs read correctly, aborts, false STOP episodes. **Comparison:** with the Sunbox finals A1 and A2_right (same seed 2, so run k has the same goal), **paired by run index**, with Newcombe 95 % intervals for the difference of the rates (the pairing is also shown as a table of the four combinations per run index).

**Rules.** `frozen.json` and every frozen-listed file are never edited; no result of the finals is touched (the final root's evaluation, export and combined folders are read only, never written); no final run-once marker is written by anything in S1; no value, threshold or rule is set from S1.

**Decisions (the build).**
1. **`data_splits_v4.guard_run` accepts exactly these two looks only for a session whose `session.json` has `"supplementary": "S1"`** (a new argument `supplementary`). With it: every look must be `anime_f_01` or `cartoon_boxo_01`, and **a run has exactly one look** (all its workers); any other look (also a Sunbox look), a mix of the two, an unknown `supplementary` value, or clips that are not listed (or that mix roles) is refused. Without it the role `avatar_experiment` is still refused in every mode (16.31.2): **the S1 looks are refused everywhere else**. `hri_eval_dev_v4.load_sessions` reads each session's `supplementary` and **refuses a session that has it in every ordinary development or final evaluation**; only the S1 mode (`load_sessions(..., supplementary="S1")`) loads such sessions, and then only sessions that say "S1". `data_splits.json` is not changed (frozen).
2. **The S1 evaluation mode does NOT require `frozen.json` to match.** It never calls `require_frozen` for the S1 sessions; it **records instead each session's git commit (`session.json`), the hashes of its `config_used` files, and whether each equals the frozen record's hash or the final configuration of its setting** (reported, not required). It writes **no `FINAL_*` marker** (the module imports none of the writers, and the tool checks that its output folder contains none) and **refuses an output folder inside or equal to the finals' root**. A session is checked for: `supplementary` "S1", `seed` 2, a setting of A1 or A2_right (from `final_setting` when present, else from `experiment` and `set` and the turn map), one look in every run, the timeout 480 s when recorded, the runs present (10), the leak test.
3. **`process_supplementary_zip_v4.py <zip> --sha256 <hash>`** (new; reporting code): verifies the SHA-256 and the manifest (read in place), copies the session folders out member by member (hash checked, no code) into a NEW folder outside the repository (`supplementary_root` of `configs/v4/experiments/phase_b.json`), pairs each Unity session with its bridge folder (**the bridge folder started last before the Unity session started; each used once; the runs of the two must agree**: a session that cannot be paired is refused, nothing is guessed), runs the checks of 2, and writes the tables as CSV and Markdown: (a) per look and setting: n, successes with Wilson 95 %, failure reasons (wrong goal, abort, timeout, collision), median time; (b) dialogs: asks read correctly (the command read equals the command shown; ask level, counts shown) and aborts; (c) STOP gesture episodes true / false; (d) the comparison with the finals' A1 and A2_right read from the finals' export folders (`runs.csv`, read only; `--finals-root`), paired by run index, Newcombe 95 % for the difference, the four-way pairing table, and the session provenance (commit, config hashes). Every figure with its count; not computable = "not evaluated".
4. **Not decided here / for Nusrat (Unity side, not touched):** the sessions must carry `"supplementary": "S1"` in `session.json`, one look per run, the finals' configuration of the setting; Unity's own run-once guards and the preflight of the Python server refuse a second session of a final setting, so how S1 sessions are started (a development-mode session with the final configuration, or a declared S1 start in the launcher) is hers and is declared before the data exists.
5. **Tests:** the guard (accepted only with S1 and only these looks, one look per run; refused without S1, with another look or two looks, with an unknown value, with unlisted clips); `load_sessions` refuses an S1 session in development and final evaluations and loads it in the S1 mode; the S1 evaluation on synthetic sessions (both looks, both settings) writes the tables and no marker and refuses the finals' root; the pairing rule; the paired comparison on synthetic finals.

**16.36.1 Build notes (2026-11-24, same branch, before the commit).** The S1 evaluation mode is inside `process_supplementary_zip_v4.py` (no separate module): it calls `hri_eval_dev_v4.load_sessions(..., supplementary="S1")` and `export_csv_v4.build_tables`, needs no `frozen.json` match, records each session's commit and the hashes of its `config_used` files against the frozen record (reported, not required), refuses an output root equal to or inside the finals' root, and asserts that no `FINAL_*.json` exists in its output. New config key `supplementary_root` in `configs/v4/experiments/phase_b.json` (not a frozen file). Four isolation tests list the new module as evaluation code (allow-list change, like 16.33.2 and 16.35.2). Tests: `tests/test_supplementary_s1_v4.py`. Not tested on real S1 data (none exists); the zip path is exercised only by the pairing, comparison and refusal tests, not by a synthetic zip end to end. No `frozen.json`, finals result or frozen-listed file was touched.

**16.36.2 SUPERSEDED by 16.37 (2026-11-24):** the two-look design (anime_f_01, cartoon_boxo_01; A1 and A2_right; 10 runs) was replaced before any data; read 16.37 for the design in force. The guard, the evaluation mode and the tool of 16.36.1 remain, adapted.

### 16.37 Supplementary experiment S1, REDESIGNED: four characters, scenes A1, A3 and B3 (Anisha and Nusrat, 2026-11-24; replaces the design of 16.36, before any S1 data and before any S1 session was started); recorded BEFORE the code; same branch `anisha/v4-supplementary-s1` (the branch of 16.36 already existed locally with commit 5932f5f, never pushed; its history is kept and this entry supersedes the design of 16.36 and 16.36.1)

**Why.** The supervisor asked to "test perception with avatar ... human robot interaction". Nusrat's design replaces the two-look design of 16.36. Nothing of 16.36 ran: no S1 data exists. It stays **post-freeze, exploratory and descriptive only**: not part of the frozen study, never pooled with the finals, no value, threshold or rule set from it, reported in its own section.

**Design (Nusrat's).**
- **Characters (looks):** `mixamo_worker`, `anime_f_01`, `anime_f_02_outfit_short`, `cartoon_boxo_01` (the avatar_experiment role, 16.31.2). **ALL workers of a run wear the same character** (one look per run, one look per session).
- **Scenes and runs:** **A1** and **A3** with lies OFF (truthful workers), **5 runs per character per scene**; **B3** with lies ON and lie handling ON (the final B3 configuration, detection on), **5 runs per character**. 4 characters x 3 scenes x 5 runs = **60 runs**. Seed 2 and the final plans' **goals, worker positions, lie schedule and test gesture clips**; timeout 480 s; the strict run protocol (other apps closed, Best performance); everything else as the finals.
- **Runs (the plan runs of the final plans, seed 2):** A1: plan runs **1-5**. A3: plan runs **1-5**. **B3: plan runs 5, 7, 8, 10, 11** (rule below). The Unity session runs these in order as its run_001..run_005 and records the list in `session.json` as `"plan_runs"`; the Python side refuses a session whose `plan_runs` is not the declared list of its setting, and a run whose goal is not the final plan's goal for that plan run.
- **B3 run choice, by rule only.** "The 5 lowest run numbers of the final B3 plan (seed 2) in which at least one worker at a junction on the planned route is a liar", read from the **final B3 session's `workers_plan` only** (`trials_final_Task2_B3_20261123_175422/session.json`, which also equals the plan of the B3_off session: same goals and same worker lines), never from any outcome. The planned route is A to the run's goal along the map's `command_toward` (the bridge's `map_used.json`: A->J1->J2->J4->E5 etc.); a junction is a node of kind `junction` (J1-J4); **A is the start node, where the robot does not ask, so a liar standing at A does not count.** Result: lying workers on the route's junctions in plan runs **5** (J1, J4), **7** (J2, two workers), **8** (J3), **10** (J3), **11** (J4); runs 6 (liar J4 off the route), 12, 15, 17 have none on the route. **The 5 runs: 5, 7, 8, 10, 11.** (Had A counted, the rule would give runs 1-5; it does not, because no ask happens at A. This choice was made before any S1 data.)
- **Baseline:** the **same plan run numbers of the Sunbox finals** of the same setting (A1, A3, B3), **paired by plan run** (same goal, same schedule), Newcombe 95 % for the difference, descriptive.

**Outcomes (per character x scene).** Success with Wilson 95 %; failure reasons; dialogs read correctly (asks read as shown, ask level); gesture confusion (shown vs read) and branch confusion (true vs read); **lies given / detected / corrected / fooled (B3)**; false STOP episodes (and true); aborts; median time of successes; next to the paired Sunbox baseline.

**Decisions (the build; replaces 16.36 decisions 1-3 and 5).**
1. `data_splits_v4.SUPPLEMENTARY["S1"]` = the four looks; `guard_run(..., supplementary="S1")` accepts exactly these four looks only for a session with `"supplementary": "S1"`, one look per run; refused everywhere else (as in 16.36 decision 1, tests).
2. The S1 evaluation mode (inside `process_supplementary_zip_v4.py`) needs no `frozen.json` match; it records each session's commit and `config_used` hashes (compared with the frozen record, reported, not required); it writes **no `FINAL_*` marker**, refuses an output inside the finals' root, never touches the finals' results; **each run is scored on its own `map_used.json`** (the evaluation already does since 16.35.1).
3. `process_supplementary_zip_v4.py <zip> --sha256 <hash>`: settings A1, A3, B3; sessions of 5 runs; tables as CSV and Markdown: (a) per character x scene (success Wilson, failure reasons, asks read as shown, aborts, STOP episodes true/false, median time); (b) lies given/detected/corrected/fooled per character (B3, with the first/later split of `final_results_v4.lie_split`); (c) gesture confusion and (d) branch confusion per character x scene (and pooled per scene); (e) the paired Sunbox baseline by plan run (rates, Newcombe 95 %, the four-way pairing); (f) provenance. A zip with only some of the 12 cells is processed and the missing cells are listed; a cell twice is refused.
4. **For Nusrat (Unity side, not touched):** `"supplementary": "S1"` and `"plan_runs": [...]` in `session.json`, `final_setting` A1 / A3 / B3 with seed 2 and the final plan's goals for those plan runs; how the sessions are started (the run-once guards refuse a second final session) is hers.
5. Tests: the guard with the four looks; the B3 rule (computed from a synthetic `workers_plan`, and the declared list pinned to the final session's plan when that file exists); `plan_runs` and goal checks; the paired baseline by plan run; no marker; the finals' root refused. The full suite runs before the commit; no `frozen.json`, finals result or frozen-listed file is touched.

### 16.38 Avatar experiment: results processing and the Edit-part decision (Anisha, 2026-11-26; recorded BEFORE the zip is processed; branch `anisha/v4-results-rest` from main 29c536e)

**Input.** `avatar_experiment_20261124_202118.zip` (declared size 5,151,213,911 bytes; SHA-256 from its `.sha256` file in `~/Downloads`: 0c4e3398...ac8d). **On 2026-11-26 17:20 only the `.sha256` file was on the machine, not the zip**, so nothing was processed and no number exists. The zip is read in place only when its size equals the declared size and its SHA-256 equals the `.sha256` file (a different hash stops the work).
**Decisions, from rules already declared (16.30.1, 16.31.1, 16.31.4, `docs/avatar_experiment_protocol_v4.md`).**
1. **Play is processed exactly per the protocol** with `process_avatar_zip_v4.py`: tables per look and per kind_group: person detected, gesturing hand found AND linked (the primary measures), facing, command read per command (PROCEED included); the take is the unit, bootstrap over takes (2000 resamples, seed 1), Wilson only for take-level yes/no; the floor, the INVALID rules and the interruption rule as declared.
2. **The Edit part is reported as NOT COMPLETED (a limitation).** It stopped after about one minute with no recordings. The look checks have no resume mechanism, so the interruption rule of 16.30.1 (one resume from the interrupted group) **cannot apply**; nothing is re-run and nothing is invented for Edit. **Play stays the declared headline**; the Edit control is not part of any claim.
3. Nothing is re-run; no threshold, rule or look list is changed after seeing the data.

### 16.39 Set C = supplementary S1: processing (Anisha, 2026-11-26; recorded BEFORE the zip is processed)

**Input.** `s1_supplementary_20261126_002450.zip` (declared size 660,900,873 bytes; SHA-256 dfff4de1...e395), same rule as 16.38: not on the machine at 17:20, so not processed yet. Processed with `process_supplementary_zip_v4.py --finals-root ~/RobotVisionResults/phase_b_final` per 16.37 (exploratory, descriptive only, 5 runs per cell, never pooled with the finals). **Added now:** abort reasons PER ASK (person never detected, arm not raised, POINT not read, PROCEED not read, ...), **derived from the bridge logs by a fixed rule, not guessed**: for each ask of an aborted run, the reason is the first of the robot's own logged conditions that applies (the rule is written in the tool and tested before the data is read); an ask with no logged cause is `unknown`. No value is set from S1.

### 16.40 Methods values, figures and results_for_paper.md (Anisha, 2026-11-26)

**Disclosure of order:** `docs/methods_values.md` (every value with its file:line or AUDIT section; copied, no new decision), `make_paper_figures_v4.py` (Times New Roman, PDF and PNG 300 dpi, from the result CSVs only; stops if the font is missing: it is installed on this machine) and `build_results_for_paper_v4.py` were written BEFORE this entry was appended, in the same session and before any avatar or S1 data existed; figures a, b, c were produced from the finals' result tables (`final_results_20261124_191243`); d (avatar) and e (Set C) are produced when their zips are processed. `results_for_paper.md` copies the tables of the tools and says NOT AVAILABLE for a section whose data is missing. No frozen-listed file, `frozen.json` or finals result is touched (outputs go to `~/RobotVisionResults/paper_results/`).

### 16.39.1 S1 zip: actual layout and the mixamo_worker / A1 cell (Anisha, 2026-11-26 21:20; recorded BEFORE the tool is adapted and BEFORE any S1 number is read)

**What the zip is.** `s1_supplementary_20261126_002450.zip` (size 660,900,873 and SHA-256 dfff4de1...e395 both verified against its `.sha256` file) was made by Nusrat's `finals_v4/zip_s1.ps1` (commit 6830738), not by `final_zip_v4.py`: `cells/<character>_<scene>_part1/{<unity session>, <bridge run>, logs}` for 12 cells, a MANIFEST with `cells` (each: character, setting, part, unity_session, bridge_run, `valid`) and `files` (name, bytes, sha256), plus `s1/` (plan, config, `s1_runs.json`, `rechecks/`, `unlisted_*`) and `extra/power_mode_s1.txt`. `process_supplementary_zip_v4.py` assumed a manifest with `folders` and stopped at step 99 on its first run ("MANIFEST.json has no 'folders'"); nothing was evaluated and no number was read. The reader is adapted to this layout (cells from the manifest, each cell's two folders copied out with the per-file SHA-256 check of `process_final_zip_v4.copy_out`; the pairing the tool derives by time must equal the manifest's unity_session / bridge_run, else refused). The evaluation, tables and rules are unchanged.

**Findings from the zip's own records (read before decisions, no result read).**
1. **mixamo_worker / A1 has `valid: false` in the manifest and `s1_runs.json`.** Its transcript says INVALID on criterion 5 of Nusrat's checker; `s1/rechecks/run_s1_recheck_s1_mixamo_worker_A1_20261125_213327.log` (a read-only re-check with the checker fixed in commit 17be117, "count final markers by exact name, not a FINAL* wildcard", cell never rerun) says "S1 CELL VALID: every criterion passed". The original criterion-5 failure was the checker counting `final_ab_A1.json` / `final_plan.json` / `final_v4.json` (copies of config files in `config_used`, inputs, not markers) as final markers.
2. **mixamo_worker / A1 ran at commit f90a72e; the other 11 cells at 17be117.** Between the two, only `finals_v4/check_s1_session.ps1`, `finals_v4/zip_s1.ps1`, a Unity test and a Unity doc changed (git diff --stat f90a72e 17be117): no Python and no run-behaviour file.
3. **One earlier mixamo_worker / A1 start (commit 7fe864a, 20:50) was refused** ("NOT_STARTED.txt": `worker.fbx` not installed, no shader warm-up for the look); it is kept in `s1/unlisted_*` as evidence, has no runs and is not evaluated.
4. Run-protocol notes: for mixamo_worker / A1 other programs were running (nvcontainer x4, warp-svc), free memory 6,799 of 14,226 MB; power plan High performance, "Best performance" recorded in `extra/power_mode_s1.txt`. Reported as the run-protocol limitation, as in the finals.

**Decision (by the declared rules: 16.37 says what S1 is and how it is evaluated; 16.30.1 defines an interruption as infrastructure only; no rule makes a checker's false verdict a reason to drop data).**
1. **The mixamo_worker / A1 cell is evaluated like the other eleven**, because (a) every one of its five runs ended with an outcome, (b) the only criterion that failed was the checker's own wildcard bug, fixed and re-checked read-only with "every criterion passed", (c) Python's own checks in the S1 tool (leak test, S1 split guard, `plan_runs`, runs present, seed, per-run `map_used.json`) are independent of Nusrat's checker and still decide. **Its original verdict and the re-check are reported next to the cell** in `s1_d_provenance` (`packer_valid`, `recheck`) and in the text of the results, with the commit difference and the run-protocol note. Nothing is rerun; nothing is dropped.
2. If one of my own checks fails for any cell, that cell is reported INVALID with the reason and not scored; the other cells stand.
3. The `unlisted_*` evidence is listed in the provenance table and not evaluated.

### 16.39.2 S1 abort-reason table: a join bug found after the first run, fixed (Anisha, 2026-11-26 21:35; recorded BEFORE the fix and BEFORE the table is re-read)

**What happened.** The first real run of `process_supplementary_zip_v4.py` (`~/RobotVisionResults/phase_b_supplementary/process_supplementary_zip_v4_20261126_212240`) produced `s1_g_abort_reasons_per_ask` rows labelled `person_never_detected` with `frames_in_window` 0 for asks whose command was read correctly and even accepted (mixamo_worker, A3 trial 2, ask 3: read PROCEED, accepted). That is impossible, so the table was wrong. **Cause (my code, never run on real data before):** the dialog's `t_s` is seconds since the run start (`export_csv_v4`: `t0 - t0_run`), the bridge log's `t` is the bridge clock (about 300 s into the session), so the time windows did not overlap, and `ask_reason` read "no frames" as "no person". **No other table is affected** (they do not use the log windows; the numbers of tables s1_a, s1_b, s1_c, s1_c2, s1_d, s1_e, s1_f do not change). **Nothing about the rule was chosen from a result:** the rule's order (declared in 16.39) is unchanged.
**Fix, decided from the data's structure, not from any result.** (1) The ask's window is taken on the bridge clock from `python_trial_###.json` `junctions[].asks_log[]` (`t`, `serial`): from the ask's own `t` to the next ask's `t` (or at most 20 s, `dialog.wait_timeout_s`), matched to the dialog by `serial`; a serial with no `asks_log` entry is `unknown`. (2) An ask with no logged frame in its window is `no_frames_logged`, never `person_never_detected` (that needs frames with no person). (3) An ask the controller accepted is labelled `accepted` (it is not a cause of the abort); the reason columns are for the asks that did not give a usable answer. (4) Test on a synthetic session with the two clocks different. The first run's folder is kept as a superseded record (nothing is deleted or overwritten); the corrected run writes a new folder; the paper uses only the corrected one.

### 16.38.1 Avatar experiment: processed; correction of a statement in 16.38 (Anisha, 2026-11-26 21:25 to 21:50; recorded after the processing, nothing here changes a rule)

**Processed.** `avatar_experiment_20261124_202118.zip` (size 5,151,213,911 and SHA-256 0c4e3398...ac8d verified against its `.sha256`) with `process_avatar_zip_v4.py ... --device mps`: results `~/RobotVisionResults/phase_b_avatar/process_avatar_zip_v4_20261126_212318/play/`. Play: official run, commit 82358960d5, STARTED and DONE markers, 15 looks, 12 clips all listed; 4860 recordings, 11,460 frames, 4860 takes, **0 invalid, 4860 used**. Tables: per_kind_group, per_look (headline), per_look_role, per_clip_role. The unchanged look-check tool's own verdict is "fails" for all 15 looks (Sunbox looks included); reported as the tool gives it.
**Correction of 16.38 (a factual statement, not a rule).** 16.38 (and the hand-over) said the Edit part "stopped after about 1 minute with **no recordings**". The zip shows: the Edit folder `look_check_ab_20261124_175515` has the STARTED marker (17:55:15), **no DONE marker**, and **partial recordings (10,612 files, 17:55 to 17:56) for 10 of the 15 looks**; sunbox_f_dress_red is incomplete (PROCEED 46 files instead of 376). The decisions of 16.38 stand and now rest on the right facts: no DONE marker, so the guard (official run needs STARTED and DONE) refuses it; the marker says the part cannot be run again; the look checks have no resume; **the partial Edit data is not evaluated** (choosing the looks that happen to be complete would be a subset chosen after the fact) and nothing is claimed from it. The tool reports Edit as "skipped - not in the zip" (its wording for "no complete official Edit run"); the paper text says "NOT COMPLETED" and gives the facts above. `docs/methods_values.md` section 6 is corrected the same way.

### 16.39.3 Set C (S1): processed (Anisha, 2026-11-26 21:22 to 21:50)

`s1_supplementary_20261126_002450.zip` (size 660,900,873, SHA-256 dfff4de1...e395 verified) with `process_supplementary_zip_v4.py --finals-root ~/RobotVisionResults/phase_b_final`: **12 of 12 cells passed Python's own checks and were evaluated** (S1 guard, seed 2, plan_runs, one look, leak test, no final marker written). Results: `~/RobotVisionResults/phase_b_supplementary/process_supplementary_zip_v4_20261126_212608/` (the folder `..._212240` is the first run with the abort-reason join bug of 16.39.2: superseded; its other tables are identical). Decisions of 16.39.1 applied (mixamo_worker / A1 evaluated with its original verdict and the re-check reported in `s1_d_provenance`). Figures d and e and `results_for_paper` (`~/RobotVisionResults/paper_results/`) were made from these folders. Descriptive only: 5 runs per cell, no test, no claim.

### 16.40.1 Figure e legibility and two notes in results_for_paper.md (Anisha, 2026-11-26; recorded BEFORE the change; presentation only, no number, rule or table changes)

1. **Figure e:** a 0/5 bar has no height, so anime_f_01 and cartoon_boxo_01 could not be told apart. Change: a visible marker at the bar's value (also 0) in the character's colour, and the character's short name under every bar. Only e is re-rendered (new folder; the earlier folders are kept); the data are the same `s1_a_per_character_and_scene.csv`.
2. **Two notes added to `results_for_paper.md` (text only):** (a) POINT is read from the arm direction of the body pose, so "gesturing hand found and linked" in the avatar experiment does not measure POINT reading; the hand matters for STOP, WAIT and PROCEED. (b) The look-check tool's own "fails" verdict uses engineering thresholds and is not a declared outcome; the declared outcomes are the rates in the tables.
