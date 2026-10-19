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
   The Game view shows the **view camera** (`FollowCamera`, chase by default). **C** cycles chase (behind and
   above the robot) -> top-down (orthographic, +z up, roof clipped) -> gesture camera (exactly what the robot's
   pan-tilt camera sees). **H** toggles the camera previews. The overlay (top left) shows the robot state, the
   current junction, the gesture shown (scripted) vs read (by the robot), goal B (name, position, distance; an
   orange "B" label and an orange marker whose ring is the 0.3 m success radius) and the running success ratio.
   The goal marker is on the `ViewerOnly` layer, which the robot's cameras do not render, so it can never leak
   into vision; the overlay is Game-view only for the same reason. The old fly camera ("Main Camera") is disabled.
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
| Python link | TCP bridge (Step 3) in **shadow mode**: observations and images go to Python, replies are logged, decisions still use the scripted sources | Step 4 switches decisions to the replies |
| Python perception | `StubPerception`: no people, gesture NONE, labelled "stub (no perception until Step 4)" | Step 4 |
| Unity-Python round trip | measured per reply (observation written -> reply read) | stays |
| Inference time | Python-side time per observation (now: JPEG check of the stub only) | Step 4 adds per-model times |

RobotBrain sees people and gestures only through the two interfaces and never sees B. Every run log names
both sources, so results from these baselines measure navigation, timing and the dialog logic, not perception.

### Python bridge (Step 3)

Message format: [docs/protocol.md](docs/protocol.md) (length-prefixed JSON + JPEG images, protocol v1).
Start the server first (it waits for Unity and accepts it again after every Play):

```
# Windows PowerShell, from robot_vision\
.\.venv\Scripts\python.exe hri_bridge_server.py
# macOS Terminal, from robot_vision/
.venv/bin/python hri_bridge_server.py
```

(Use the venv you run the tests with; in this checkout it is the repository-root `.venv`.) Then press Play.
The HUD shows `Python link: connected` and the round trip. `hri_config.json -> link`: `enabled` (connect at
all), `link_required` (false = shadow mode, the robot drives without Python; true = trials wait for Python and
the robot stops by itself after 0.3 s of silence). Server output: `robot_vision/outputs/bridge_<time>/` with
the config, `run.json` (git commit), and per connection `hello.json`, `frames.csv`, `summary.json` and every
50th observation's images. Unity's per-run log adds `link_status`, round-trip mean/max and inference mean/max;
telemetry adds `link`, `inference_ms` and `round_trip_ms` per 0.1 s row. After updating, run
**Build Guided Scene** again so the robot gets its `HriBridgeClient`.

### Vision perception (Step 4)

`hri_config.json -> perception.mode`: `scripted` (default; baselines) or `vision`. In vision mode RobotBrain gets
people from `VisionPersonSource` and gestures from `VisionGestureSource` (the Python replies); the Python link
becomes required. Python (`robot_vision/hri_perception.py`, thresholds frozen in `configs/hri_perception.json`,
record `configs/hri_perception_frozen.json`):
- People: YOLO11s-pose + ByteTrack on the 360 deg horizon band (+30..-60 deg, 2048 x 512, JPEG 90); bearing from
  the column, distance from the ankles on the floor (level camera, flat floor); nearest person = target.
- Gesture: YOLO11s-pose on the gesture camera; arm direction = mean of shoulder->wrist and elbow->wrist; bins
  LEFT -90, FORWARD_LEFT -45, FORWARD 0, FORWARD_RIGHT 45, RIGHT 90 deg (+-15), NONE between or when unclear.
- STOP: MediaPipe gesture recognizer through `gesture_adapter.py` (Anisha's module unchanged) with
  `configs/gesture_hri.json`: STOP = Open_Palm only (her baseline also maps Closed_Fist; the worker points with
  fists, so that mapping would stop the robot at every direction).
- Weights: `robot_vision/models/yolo11s-pose.pt` (git-ignored; sha256 in the config). Download once from
  robot_vision/models: `python -c "from ultralytics import YOLO; YOLO('yolo11s-pose.pt')"`.
- The Mixamo worker's textures are extracted by Build Guided Scene into the git-ignored
  `Characters/worker_textures/` (untextured it rendered pale and was hard to detect).

Development evaluation (**vision**, dev seed 1 only, macOS M-series laptop, MPS; `hri_eval_dev.py`,
report `outputs/hri_dev_eval_20261020_031217`). Accuracy = correct / frames with a command; coverage = frames
with a command / all frames of that command. Unity synthetic scene, one avatar, 1.7-2.5 m, view +-25 deg:

| shown | coverage | accuracy | 1.0 s hold: correct / wrong / none (of 20) |
|---|---|---|---|
| NONE | false command rate 0.0 | - | 20 without a false accept |
| LEFT | 0.953 | 1.0 | 18 / 0 / 2 |
| FORWARD_LEFT | 0.982 | 0.927 (8 frames read LEFT) | 17 / 0 / 3 |
| FORWARD | 0.795 | 1.0 | 15 / 0 / 5 |
| FORWARD_RIGHT | 0.914 | 1.0 | 16 / 0 / 4 |
| RIGHT | 1.0 | 1.0 | 18 / 0 / 2 |
| STOP | 1.0 | 1.0 | 20 / 0 / 0 |

Diagonals meet the declared criterion (accuracy >= 0.9, coverage >= 0.8): no recommendation to drop them.
People recall (true worker within the bearing match of 10 deg): 0.91 at 0-3 m, 1.0 at 3-6 m, 0.55 at 6-9 m,
0.0 at 9-12 m (all 0.763 of 2159 frames); distance known for all matched frames, error median 0.25 m,
p90 0.59 m, mean +0.28 m (too far). Trials: 10/10 SUCCESS, 15/15 junction readings correct.
Python time per observation: total median 235 ms, p95 319 ms (YOLO on the panorama band median 139 ms); it
rose from 154 to 252 ms over the 8.5 min session (likely thermal throttling; not measured). Replies above
0.3 s let the watchdog stop the robot briefly: 14 telemetry rows, at most 0.42 s per trial.

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