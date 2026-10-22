# Avatar-Mediated Human-Robot Interaction in Virtual Worlds

A robot in a virtual warehouse has to reach a goal it doesn't know.
Workers standing along the way show it where to go with simple arm
signals. The robot finds the nearest worker, drives up to them, asks
"Which direction?", reads the signal, and follows it until it
reaches the goal.

Everything runs in a Unity simulation. Python does the "thinking":
it looks at the robot's camera images, recognises people and their
arm signals, and tells the robot how to drive.

## Results

| Task | What happens | Result |
|---|---|---|
| Task 1 | The robot drives straight from A to its goal, stopping at three workers who each signal "go straight" | 10 out of 10 runs reached the goal; at all 30 stops the signal was read correctly at the first ask; no collisions |
| Task 2 | A route with junctions; the goal changes every run, and the workers guide the robot to it | 10 out of 10 runs reached the goal; all 14 junction signals were read correctly at the first ask; no collisions |

Each final run happened once: 10 runs on a random seed that was not
used during development, with all settings fixed beforehand.

Task 2 was then repeated once on a second computer (the original ran
on a Mac, the repeat on a Windows PC), with the same seed and settings
and with the plan written down before it ran. It gave the same result:
10 out of 10. The repeat is reported next to the original and does
not replace it. Every detail, number and decision is recorded in
[AUDIT.md](AUDIT.md).

## How it works

1. **Drive:** the robot follows the warehouse map towards the next
   junction.
2. **Look:** near a junction it slows down and uses its 360° camera
   to find the nearest worker.
3. **Approach:** it stops about 2 m in front of the worker.
4. **Ask:** "Which direction?" appears on screen, and a second
   camera turns towards the worker.
5. **Read:** it reads the worker's arm signal. The same signal must
   be held for 1 second before the robot accepts it.
6. **Go:** it takes the direction it was shown and drives on.

**Safety, always on:** an open palm (STOP) stops the robot at once,
and if the Python side stops answering, the robot stops by itself.

### The arm signals

| Signal | What the worker does |
|---|---|
| LEFT | Arm straight out to the robot's left |
| RIGHT | Arm straight out to the robot's right |
| FORWARD | Arm straight up |
| STOP | Open palm towards the robot |

FORWARD is "arm up" on purpose: seen from a camera in front of the
worker, a pointing-ahead arm would look almost the same as LEFT or
RIGHT.

## What's in this repository

- `robot_vision/`: the Python code (seeing, deciding, steering,
  logging, analysis); technical details are in
  [robot_vision/README.md](robot_vision/README.md)
- `unity/Robotics-Warehouse/WarehouseProjectURP/`: the Unity project
- `external/media_pipe_gesture/`: Anisha's hand gesture module
- `AUDIT.md`: the full record of every experiment and decision
- `results/summary/`: result tables and plots

## Getting started

**You need:** Unity 2022.3.62f3 and Python 3.12, on Windows 11 or
macOS. The final runs used a Windows 11 PC with an NVIDIA RTX 3060
(Task 1 and the Task 2 repeat) and a Mac (the original Task 2 final).

1. Download the project, including the gesture module:
   `git clone --recurse-submodules https://github.com/nusratahmedniva/warehouse-robot-perception.git`
2. In `robot_vision/`, create a Python environment named `.venv`
   (`python -m venv .venv`) and install the packages into it:
   `pip install -r requirements.txt`. The launchers only use this
   environment.
3. Download `yolo11s-pose.pt` from Ultralytics into
   `robot_vision/models/`. The code checks that it's the exact file
   we used.
4. Open `unity/Robotics-Warehouse/WarehouseProjectURP` in Unity Hub
   with Unity 2022.3.62f3.
5. The worker character isn't included, because its licence doesn't
   allow sharing the files. Download it from Mixamo and place it in
   `Assets/WarehouseRobot/Characters/` as `worker.fbx`,
   `Walking.fbx`, `Idle.fbx` and `Stop.fbx`.
6. In Unity, run **Tools > Warehouse HRI > Restore Worker
   Appearance**. Without it the worker shows up magenta, and every
   test session refuses to start.

## Running a test session

From `robot_vision/` in PowerShell:

    .\run_trials.ps1 -Task Task1

Then open the `WarehouseRobot` scene in Unity and press Play. When
the last run has finished, press Ctrl+C once in the PowerShell window
so the summary is written.

Use `Task2` for the other task. Add `-Trials 5` for a shorter
development test, or add `-UnityBatch` to run without opening the
Unity window (Unity is looked for in the default Unity Hub folder;
otherwise set `UNITY_EDITOR` to its path). On macOS, use
`./run_trials.sh Task1` (with `--trials 5` or `--unity-batch`).

The official final runs are already done and protected, so they
can't be run a second time by accident.

## How we kept the results honest

- All thresholds and settings were fixed **before** the first final
  run. They are byte-identical in all three reported runs, and a test
  checks this.
- Each final run, and the Task 2 repeat, was allowed to happen **only
  once**.
- Some rules were changed after we saw **development** results (for
  example, the diagonal "forward-left" and "forward-right" signals
  were dropped, even though they had passed the test we had set for
  keeping them). These changes are listed in `AUDIT.md`. Nothing was
  changed after seeing **final** results.
- Code changes between runs (for example, a fix to when the safety
  stop triggers, made before Task 1 and the Task 2 repeat) were
  written down before those runs.
- Every change, problem and limitation is written in `AUDIT.md`.

## Limitations

- The "person walks into the robot's path" stop was only tested in a
  Python simulation, not in Unity.
- In one run, the robot mistook a hand for STOP for a split second
  (0.05 s), then carried on.
- Small samples: 10 runs per task, on one seed.
- One worker character in one warehouse; the arm signals are a fixed
  set of poses, not natural pointing.
- Workers stand still; they don't walk around.
- On the 8 GB Mac, person detection slowed down while Unity was
  running, so the robot sometimes paused to wait for fresh images
  (up to 6 s in the final). The cause wasn't found.
- Our run checklist (other apps closed, enough free memory) wasn't
  fully met in the Windows runs. Both runs record this.

## Ideas for the future

- Natural pointing gestures, read in 3D
- Workers who move around the warehouse
- Testing on a real robot

## Team

- **Nusrat Ahmed Niva** ([@nusratahmedniva](https://github.com/nusratahmedniva)):
  the robot and its cameras, the Unity–Python connection, the early
  perception work on the THUD++ dataset, Task 1, and the results
  archive.
- **Anisha** ([@anisha274](https://github.com/anisha274)): the hand
  gesture module, people and gesture recognition, the worker and the
  warehouse map, the robot's step-by-step behaviour, the trial runner
  and logging, and Task 2.

## Use of AI tools

We used Claude Code and GitHub Copilot to help write code. We
reviewed and tested all results ourselves.

## Credits and licences

- [Robotics-Warehouse](https://github.com/Unity-Technologies/Robotics-Warehouse)
  by Unity Technologies (Apache-2.0), modified; see its
  `MODIFICATIONS.md`
- [media_pipe_gesture](https://github.com/anisha274/media_pipe_gesture)
  by Anisha (MIT)
- [Ultralytics YOLO](https://github.com/ultralytics/ultralytics)
  (AGPL-3.0)
- [MediaPipe](https://github.com/google-ai-edge/mediapipe) by Google
  (Apache-2.0)
- THUD++ dataset: not included; see its project page for access and
  how to cite it

This project is licensed under AGPL-3.0.
