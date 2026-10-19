# Avatar-Mediated Human-Robot Interaction in Virtual Worlds

A wheeled warehouse robot in a Unity simulation is guided to an unknown
goal by human avatars: at each junction it finds the nearest worker, asks
for a direction, reads a pointing gesture and takes the indicated way.
Python handles perception and decisions; Unity runs the simulation.

## Repository layout

- `robot_vision/`: Python perception, decision rules, Unity bridge, evaluation
- `unity/Robotics-Warehouse/WarehouseProjectURP/`: Unity project (2022.3.62f3, URP)
- `external/media_pipe_gesture/`: gesture module by Anisha (git submodule)

## Getting started

1. `git clone --recurse-submodules <this repository's URL>`
2. Python 3.12: create a virtual environment in `robot_vision/`, then
   `pip install -r requirements.txt`
3. Unity Hub: install Unity 2022.3.62f3, then add the project folder above
4. Mixamo character files are not included (licence terms). Obtain them
   separately and place them in `Assets/WarehouseRobot/Characters/` as
   `worker.fbx`, `walking.fbx` and `idle.fbx`.

## Unity guided-robot scene (Steps 1, 2 and the Unity part of Step 6)

Code: `Assets/Scripts/WarehouseHRI/` (runtime, no UnityEditor APIs), `Assets/Editor/` (scene builder),
`Assets/Tests/EditMode/` (Unity Test Framework). All thresholds: `Assets/StreamingAssets/WarehouseHRI/hri_config.json`
(declared before any trial, not tuned; set `"frozen": true` after the development trials).

### Set-up in the Editor

1. Open `Assets/Scenes/WarehouseRobot.unity`.
2. Optional: put the Mixamo `worker.fbx` in `Assets/WarehouseRobot/Characters/` (git-ignored) with
   Rig > Animation Type = Humanoid. Without it the builder makes a capsule placeholder with two arm pivots.
3. **Tools > Warehouse HRI > Build Guided Scene.** Creates (or updates; running it again never duplicates) one
   root object `WarehouseHRI` with: the robot, the 360 deg camera and the pan-tilt gesture camera, the worker,
   a roadmap (A, junctions J1 and J2, endpoints E1-E4), a floor slab collider, a NavMeshSurface (baked and saved
   to `Assets/Scenes/WarehouseRobot/NavMesh-WarehouseHRI.asset`) and the TrialManager. The Console lists the
   roadmap, every NavMesh path length and any problem.
4. Save the scene, press Play. The TrialManager runs `trial_count` trials automatically.
5. **Tools > Warehouse HRI > Gesture Pose Test** (in Play mode): stops the trials, puts the view camera where the
   robot would stand and cycles the worker through LEFT, FORWARD_LEFT, FORWARD, FORWARD_RIGHT, RIGHT and STOP,
   so the arm poses can be checked by eye. LEFT must appear on the viewer's (robot's) left.

Roadmap (floor x, z in m): A (6.25, -10) -> J1 (6.25, 0); J1: FORWARD E1 (6.25, 10), RIGHT E2 (18.75, 0),
LEFT J2 (-6.25, 0); J2: FORWARD E3 (-18.75, 0), RIGHT E4 (-6.25, 10). Branch commands are computed from the
geometry, relative to the robot's heading on arrival. The worker stands 2.5 m ahead and 2.5 m right of the
junction centre, off every lane. Diagonal commands exist in code but this roadmap has no diagonal branch
(cut order item 2), and it has two junctions (cut order item 4).

### Scripted vs vision (read before quoting any result)

| Part | Now | Replaced in |
|---|---|---|
| People around the robot | `ScriptedPersonSource`: **true positions** of the worker ("scripted-perception baseline") | Step 3/4: YOLO on the 360 deg camera over TCP (`IPersonSource`) |
| Gesture read | `ScriptedGestureSource`: **the scripted pose** ("scripted-gesture baseline") | Step 4: YOLO pose + MediaPipe over TCP (`IGestureSource`) |
| What the worker shows | `RoadNode.CommandToward(B)`, called only by the TrialManager | stays (scenario side) |
| Scoring (outcome, distance to B, closest human) | true positions, after the run | stays |
| Obstacle avoidance | **NavMesh map** (AI Navigation; racks and walls via their colliders), not the cameras | stays |
| Python link | watchdog hook (`PythonLinkWatchdog`, 0.3 s) present, `link_required` = false | Step 3 |
| Inference time, Unity-Python delay | empty columns, `not_evaluated` | Steps 3-4 |

RobotBrain sees people and gestures only through the two interfaces and never sees B. Every run log names
both sources, so results from these baselines measure navigation, timing and the dialog logic, not perception.

### Outputs

`output_root` in `hri_config.json` (default `../../../robot_vision/outputs`, relative to the Unity project folder,
git-ignored). Each Play session writes a new folder `trials_<mode>_<task>_<yyyyMMdd_HHmmss>/` with the exact
config, `session.json` (git commit, seed, labels, goal order), `results.csv` (one row per run, running success
ratio), `run_###.json` and `telemetry_run###.csv` (0.1 s). Files are created new; nothing is overwritten.
Final mode (`"mode": "final"`) uses `final_seed`, requires `"frozen": true` and refuses to run if a
`trials_final_*` folder with `FINAL_DONE.json` already exists.

### Changes to the generated warehouse made by the builder (in the scene only)

- Floor tile colliders have zero thickness, so the builder adds one 0.1 m invisible floor slab collider.
- The upstream rack prefab has carving NavMeshObstacles with centimetre extents used as metres (about
  120 x 370 x 370 m each), which carve away the whole NavMesh. The builder disables carving obstacles larger
  than 10 m; the racks still block the NavMesh through their colliders. Vendored files are not edited.

## Status

Work in progress; final version due 22 October 2026.

## Team

Nusrat Ahmed Niva ([@nusratahmedniva](https://github.com/nusratahmedniva))
and Anisha ([@anisha274](https://github.com/anisha274))

## Credits and licences

- [Robotics-Warehouse](https://github.com/Unity-Technologies/Robotics-Warehouse),
  Unity Technologies, Apache-2.0 (modified; see its MODIFICATIONS.md)
- [media_pipe_gesture](https://github.com/anisha274/media_pipe_gesture), Anisha, MIT
- [Ultralytics YOLO](https://github.com/ultralytics/ultralytics), AGPL-3.0
- [MediaPipe](https://github.com/google-ai-edge/mediapipe), Apache-2.0
- THUD++ dataset: not included; see its project page for access and citation
- Unity AI Navigation (`com.unity.ai.navigation` 1.1.6, NavMeshSurface) and Unity Test Framework
  (`com.unity.test-framework` 1.1.33): Unity Technologies, Unity Companion License
- Mixamo characters and animations (Adobe): used under the Adobe/Mixamo terms, not redistributed
- MiR100 (Mobile Industrial Robots): only its nominal datasheet footprint (0.89 x 0.58 x 0.35 m) is used for the
  box stand-in; no MiR model or URDF is included yet

This project is licensed under AGPL-3.0.