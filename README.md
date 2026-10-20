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

## Perception and worker (branch anisha/integrate-hri)

- Python: `python -m bridge.server --mode hello --perception vision` (from robot_vision/, project venv) runs the
  Step 3 perception on the frames the bridge receives: YOLO11s-pose + ByteTrack people on `frame_360` (bearing from
  the column, distance from the ankles on the floor, camera height and pose from the frame header) and the arm
  direction (LEFT, FORWARD_LEFT, FORWARD, FORWARD_RIGHT, RIGHT, NONE) on `frame_pan_tilt`; STOP from the MediaPipe
  gesture adapter (Anisha's module unchanged; `configs/gesture_hri.json` maps only Open_Palm to STOP because the
  worker points with fists). The models run on a background thread; commands are unchanged (hello test), the
  latest reading is shown in `screen_text` and logged to `perception.csv` in the run folder. Weights:
  `robot_vision/models/yolo11s-pose.pt` (git-ignored; from robot_vision/models:
  `python -c "from ultralytics import YOLO; YOLO('yolo11s-pose.pt')"`). Thresholds: `configs/hri_perception.json`
  (not frozen; needs a development evaluation on this pipeline).
- Unity: **Tools > Warehouse HRI > Add Worker and Roadmap** adds the Mixamo worker (`GestureWorker`; textures
  extracted to the git-ignored `Characters/worker_textures/`), the roadmap A, J1, J2, E1-E4 (`RoadNode`, validated
  on the AMR NavMesh) and a chase camera (`FollowCamera`, C: chase / top-down / gesture camera). It also disables
  the 12 upstream rack NavMeshObstacles whose carving boxes (cm values read as m) erased the whole NavMesh.
  **Tools > Warehouse HRI > Gesture Pose Test** (Play mode) cycles the six commands.

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

This project is licensed under AGPL-3.0.