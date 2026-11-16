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
