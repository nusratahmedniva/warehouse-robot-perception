# Avatar-Mediated Human-Robot Interaction in Virtual Worlds

## Project goal
A robot in a Unity warehouse starts at point A and must reach a goal B
that it never knows; workers (one reused avatar) guide it there with
arm-pointing gestures, one junction at a time. At each junction the
robot slows, finds the nearest person with its 360-degree camera,
approaches to 2.0 m, asks "Which direction?", reads a gesture that must
hold for 1.0 s, and takes the indicated branch. An open palm (STOP) or
a person stepping into the path stops it at once, and Unity stops it by
itself if Python is silent for 0.3 s. Two automated tasks (straight A
to B, and a guided route with 2-3 junctions and a changing B) give the
results; thresholds are frozen on development trials before the final
trials run once on a different seed.

Specification: docs/project_flow.md

## Standing rules (apply to every task)
- Code must run on Windows 11 and macOS. Use pathlib. Read all paths
  from config files. Never hard-code drive letters or C: paths. Run
  outputs store paths relative to configured roots.
- Never copy datasets into the repo. Datasets, model weights, outputs
  and CLAUDE.local.md stay git-ignored.
- Do not modify Anisha's (GitHub: anisha274) gesture module (git
  submodule at external/media_pipe_gesture). Connect to it only through an adapter.
- Do not rerun successful inference. Never overwrite existing output
  folders; each run writes a new timestamped folder under outputs/.
- Reference (ground-truth) data is read only by evaluation code.
  Inference code must never import reference loaders.
- All thresholds live in config and are fixed before evaluation.
  Never tune on evaluation results. Disclose any rule changed after
  seeing results.
- Report every accuracy figure together with its coverage.
- Prefer unknown / insufficient_history / not_evaluated over guesses.
- Label results honestly: "reference-depth baseline",
  "reference-camera-pose baseline", "camera_proxy", "proxy_route".
- Save the exact config and git commit hash in every output folder.
- Commit locally at checkpoints. Claude Code (the AI) must never run
  git push. Nusrat and Anisha review the work and push their own
  branches themselves.
- Each person works on their own branch and merges into main through
  pull requests.
- Always run Python from the project venv, never the system Python:
  Windows robot_vision\.venv\Scripts\python.exe,
  macOS robot_vision/.venv/bin/python.
- Commit only after the full test suite passes, and check the exit
  status before committing. Windows PowerShell 5.1 has no '&&' and
  continues after ';', so use e.g. (from robot_vision/)
  `.\.venv\Scripts\python.exe -m unittest discover -s tests; if ($LASTEXITCODE -eq 0) { git commit ... }`
  (macOS/bash: `.venv/bin/python -m unittest discover -s tests && git commit ...`;
  never pipe the test output through tail/grep before the check).
- Code must stay macOS-compatible (checked by CI on macos-latest).
  Manual macOS runs are not required; do not list them as a
  limitation.
- Finish every task with: exact commands for Windows PowerShell and
  macOS Terminal, output paths, checks completed, remaining
  limitations. Then stop and wait for review.

## Verified facts (see README for evidence)
- THUD++ synthetic images: 730x530, 60.24 Hz; documented camera
  height 1.2 m, pitch 0.
- Intrinsics: fx = fy = 458.99, cx = 365, cy = 265 (vertical FOV
  60.0 deg, Unity default). Recorded camera_intrinsic is not in pixel
  units and is not used.
- Depth: planar (forward-axis); fitted far plane 9.966 m (~10 m);
  saturated pixels are invalid. This 10 m far plane applies to the
  THUD++ data only. The Unity cameras use no rendered depth (v3 takes
  distance from flat-floor geometry); their far clip is 100 m
  (robot_unity.json), checked at Play against the scene diagonal.
- Pose: quaternion [x, y, z, w]; world = R * p_cam + t; y is up,
  x-z is the ground plane.
- Device selection: CUDA, then MPS, then CPU
  (check_environment.select_device).
- Lower-bound person distance assumes a level camera (pitch = roll = 0);
  the Unity robot camera must stay level.
- Unity 360 camera: equirectangular, world-aligned; the image centre
  column faces world +Z (yaw 0). Confirmed in Unity on 2026-10-20 with
  a cube placed along +Z. Bridge JPEGs are upright (same check).

## Project status
- Done (THUD++ pipeline): segmentation baseline, YOLO + ByteTrack,
  Step 4 fusion, Step 8 motion (frozen: configs/motion_frozen.json,
  hash 15821ff9...1625), Step 9 decision rules (60f6e1d; revised after
  the replay demo in 2a9ed63 and cc89948; configs/decision.json).
  Step 9 decisions use only motion_trusted (dynamic_classes:
  person), motion range 0-6 m, and stop for untrusted motion near
  the route. Second review (2c4aad8, 5ffd04e): caution band,
  lower-bound distance for unlocated people, stop_hold_s; proxy
  routes regenerated at 1.00 m.
- passage.py (Step 6, from the earlier plan) is kept but not used in v3.
- Splits (enforced by data_splits.json and the guard): Office/dynamic
  Capture_1 development, Capture_2 adjustment (used), Captures 3-4
  final; Gym/dynamic Captures 2-6 cross-scene final; Gym Capture_1
  excluded (prior use in Stage 3).
- Decided:
  - Look-ahead (implemented): look_ahead_m = v * reaction_s +
    v^2 / (2 * decel) + buffer_m = 1.0*0.5 + 1.0 + 1.5 = 3.0 m
    (v, decel in robot.json; reaction_s, buffer_m in decision.json).
    Rule 1 applies only in the stop zone (corridor within
    look-ahead); rule 2 predicts entry into it.
  - Caution distance (implemented): caution_ahead_m = stopping
    distance + person_speed_mps * stopping time = 1.5 + 1.4 * 2.5 =
    5.0 m (>= look_ahead_m).
  - Unlocated person (implemented): released from the caution zone
    only by a lower-bound distance (THUD: 5th percentile of valid
    box depths); no valid depth -> caution zone.
  - Gestures: STOP held stop_hold_s = 0.2 s, MOVE held 0.5 s.
  - Load (implemented): Euro pallet 1.20 x 0.80 m, 0.80 m side across
    travel, centred, "configured, not measured" (configs/load.json).
    Required width 1.00 m, computed only by footprint.py.
  - Gesture module (implemented): git submodule at
    external/media_pipe_gesture, pinned 180e2796; adapter
    robot_vision/gesture_adapter.py (configs/gesture.json), modes
    full_frame (her baseline) and person_crop, raw scores, no threshold
    in the adapter; to_gesture_events -> decision.GestureEvent. Gesture
    evaluation: not_evaluated until Unity recordings with labels exist.
- Next, in order (Steps 1-7):
  1. Robot and cameras (done, PR #6)
  2. TCP bridge (done, protocol v2)
  3. Perception (in branch anisha/integrate-hri: robot_vision/hri_perception.py,
     bridge/perception.py, `python -m bridge.server --perception vision`;
     YOLO11s-pose people on frame_360 + arm direction on frame_pan_tilt,
     MediaPipe STOP via gesture_adapter with configs/gesture_hri.json
     (STOP = Open_Palm only). Thresholds in configs/hri_perception.json,
     frozen: false until a development evaluation on the v2 pipeline.)
  4. Worker poses (Anisha) (in the same branch: Assets/WarehouseRobot/HRI,
     Tools > Warehouse HRI > Add Worker and Roadmap / Gesture Pose Test;
     roadmap A, J1, J2, E1-E4 validated on the AMR NavMesh)
  5. State machine (done 2026-10-20, branch anisha/step5-7: hri_control.py,
     hri_sim.py, bridge/guide.py, configs/hri_control.json not frozen)
  6. Scenarios (done: TrialRunner, GoalSequence, TrialBatchPlay; roadmap.json
     must equal HriScenarioBuilder)
  7. Logging (done: hri_trials.py, hri_analysis.py, hri_eval_dev.py). Dev seed 1,
     vision: 10/10, 9/10, 10/10 (sessions _140241, _163348, _164719); see README.
     An interrupted session (_113942, 3 trials) is kept, not used.
  Frozen 2026-10-20 (configs/hri_frozen.json, tests/test_hri_frozen.py): diagonals
  dropped, reask_shift_m 0.4. Final run once 2026-10-20 (seed 2, ce37a56): 10/10 SUCCESS,
  14/14 junctions, 0 collisions (trials_final_Task2_20261020_172445,
  FINAL_DONE.json). No further final runs.
