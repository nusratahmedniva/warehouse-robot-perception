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
