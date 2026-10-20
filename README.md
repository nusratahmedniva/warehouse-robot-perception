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

## State machine and trials (Steps 5 and 7, branch anisha/step5-7)

- Step 5: `robot_vision/hri_control.py` (states idle, navigate, scan, approach, ask, read, execute, done/aborted;
  pure pursuit on the NavMesh corners; 1.0 s gesture hold with NONE gaps up to 0.3 s, one repeat ask, then abort;
  stops for STOP, a person in the path within the speed-dependent stopping distance, and perception older than
  1.0 s). Simulator `robot_vision/hri_sim.py`; tests `tests/test_hri_control.py`. Live: `python -m bridge.server
  --mode guide --perception vision`. Thresholds `configs/hri_control.json` (not frozen; two changes made after
  simulator runs are listed in it).
- Step 7: Unity `TrialRunner` (the only place goal B exists; seeded goal order, truth files) and
  `TrialBatchPlay.Run` for batch mode; Python `hri_trials.py` (run_###.json, results.csv), `hri_analysis.py`
  (analysis.md, plots) and `hri_eval_dev.py` (development evaluation; refuses final sessions).
- Development results (dev seed 1, vision mode, 10 trials, 20 October 2026): 10/10 SUCCESS (Wilson 95 %
  0.72-1.0), 15/15 junctions read as shown at the first ask, 0 collisions, closest approach to the worker 1.03 m,
  final distance from B 0.049 m mean. Gesture sweep (140 samples): per-frame accuracy 1.0 for the five directions
  at coverage 0.96-1.0; STOP read as FORWARD_LEFT in 3/100 frames (one 1.0 s hold accepted it). People on the
  panorama: recall 0.885 at 0-3 m, 1.0 at 3-6 m, 0.533 at 6-9 m, 0.0 at 9-12 m; distance error +0.255 m mean.
  Folders: `outputs/hri_trials_20261020_141351`, `hri_analysis_20261020_141359`, `hri_dev_eval_20261020_141423`.
- Known issue: on the 8 GB Mac, panorama YOLO slows from about 190 ms to about 440 ms over a 10-minute session
  while Unity runs (flat at 157 ms over 6 minutes with Unity closed). The robot then stops for "perception stale"
  (1 s in trial 1, 34 s in trial 10). `TrialBatchPlay` caps batch rendering at 60 fps, which halved the slowdown;
  the remaining cause is not identified.

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