# Avatar-Mediated Human-Robot Interaction in Virtual Worlds: v4 flow

v4 is a new study built on top of v3, not a change to it. v3 is frozen as release `v1.0` and is the baseline: fixed arm
poses (v3) against natural, moving gestures (v4). v3 runs are never repeated or edited. v4 has its own spec (this
file), its own configs (`robot_vision/configs/v4/`), its own scene (`WarehouseRobot_v4.unity`), its own decision rules
declared in advance and its own final runs.

## The idea in steps

The robot never knows where B is; the workers' gestures lead it there. The robot works only from what its cameras
see; everything used to check it lives on a separate layer it cannot see.

1. Start: the robot stands at point A. Goal B is known only to the evaluation, not to the robot.
2. Navigate: it drives toward the next junction. Unity's NavMesh gives the path; Python steers with a speed (v) and a
   turn rate (ω).
3. Slow down and scan: near the junction it slows and uses its 360° camera to find every person around it.
4. Find the commander: among the people it sees, it picks the one who is facing it and whose hand is gesturing (hand
   linked to body by keypoints). Bystanders are ignored.
5. Approach: it drives to 2.0 m in front of the commander and turns to face them.
6. Ask: it shows "Which direction?" on screen and aims its pan-tilt camera at the commander.
7. Zoom: it narrows the pan-tilt camera's field of view onto the commander's hand, and widens it again if the hand is
   lost. Every frame carries the field of view and intrinsics at render time.
8. Read the gesture: it reads 1 to 2 s of wrist, elbow and hand movement and classifies it as POINT, WAIT or STOP
   (below).
9. Act: POINT → it takes the route or branch closest to the pointed direction and drives on. WAIT → it holds its
   position and keeps watching the same person. STOP → it stops at once. If the gesture stays unclear, it asks once
   more, then aborts.
10. Repeat: steps 3 to 9 happen at every junction until the robot reaches B.
11. End and log: SUCCESS when it stops within 0.3 m of B; FAILURE on timeout, collision, getting stuck, wrong goal or
    abort. Every run is added to the results log.

Always active: an open palm (STOP) or a person stepping into the path stops the robot at once. If Python stops
answering for 0.3 s, Unity stops the robot by itself.

## Commands

No fixed poses: every gesture is a natural movement that varies each time (speed, size, which arm, start delay), and
the worker starts gesturing when the robot arrives and asks.

| Command | What the avatar does | What the robot does |
|---|---|---|
| POINT | Points with a moving arm toward any direction; the angle is not fixed to left, right or forward | Reads the pointed direction as an angle and takes the route or branch closest to it |
| WAIT | Raises one hand with the index finger up ("one moment") | Holds its position and keeps watching the same person until a POINT follows or a timeout ends the dialog |
| STOP | Open palm pushed toward the robot | Stops at once; a safety command that works at any time, not only after "Which direction?" |

WAIT and STOP must look clearly different (finger up vs open palm); their confusion is reported.

## The world

- **Workers:** one complete humanoid template (look, Animator with a gesture layer, worker ID, head turning to the
  robot), copied with different looks. Looks come from VRoid Studio (via UniVRM) and free Unity Asset Store
  avatars; gesture clips from Mixamo, 2 to 3 per command. Development looks and at least one test look are fixed
  before development; the test look is never used in development.
- **Several people:** scenes include bystanders near the robot; only one person commands at a time.
- **Heads-up display (for us):** one on-screen panel shows the robot's state, the messages between Python and Unity,
  what it detects, its gesture guess and score, and who is commanding. Python fills it through the `hud` block of
  every command; Unity draws it. It never appears in the robot's camera images.
- **Ground-truth layer (for us only):** on its own Unity layer `GroundTruth`, which both robot cameras skip.
  - Grid: the floor is divided into 0.5 m cells; racks, boxes, stations and walls block cells, widened by the robot's
    half-width plus a safety margin.
  - Lights: a glowing marker at start A and at the true goal B, like the checkpoint markers in a racing game.
  - Optimal path: the shortest route from A to B on the grid (A*, straight and diagonal steps), drawn as highlighted
    points and a line. Saved per run; never sent to Python's inference code.
  - Trail: a line drawn behind the robot, plus its position every 0.1 s, saved per run.
  - Leak test: before every session Unity renders both robot cameras with the layer on and off; the images must be
    identical, or no run starts.

## Who owns what

- Python (`robot_vision/`, docs): Anisha. Protocol v3, HUD feed, zoom rule, gesture reader, commander rule, state
  machine, simulator and replay, evaluation, analysis, archive.
- Unity (`unity/.../WarehouseRobot/`): Nusrat. Protocol v3 client, HUD drawing, ground-truth layer, trail, zoom
  camera, avatars and gestures, truth logger, recording mode, scenes and final-run guard.
- Neither edits the other's files; shared files change only by agreement.

## Data that never reaches the robot

Goal B, the grid, the optimal path, the trail and the truth labels (true gesture, true commander, worker IDs) are
written by Unity to files in the run folder. Only evaluation code reads them. No bridge message carries them, and
`bridge/protocol.py` rejects any Unity message that contains such a key.

## Research questions

1. Moving vs fixed: can the robot understand natural, moving gestures as reliably as v3's fixed poses?
2. Who commands: can it tell which of several people is giving the command?
3. Zoom: does zooming onto the hand improve recognition at a distance? (Same runs with zoom on and off.)
4. New looks: does it still work on avatar looks it never saw in development?

## Metrics and data to record

- Outcome (SUCCESS or FAILURE) and failure reason; success rate with confidence intervals
- Gesture shown vs gesture read at every ask: accuracy with coverage and the confusion matrix (POINT, WAIT, STOP)
- POINT: angle error between pointed and true direction, and whether the right branch was taken
- Time from "Which direction?" to understanding
- Commander identified correctly, with and without bystanders
- Accuracy per avatar look and style, per distance, zoom on and off
- Trail length vs optimal path length, largest distance from the optimal line, share of the trail within one grid
  cell, final distance from B
- Collisions and closest distance to any person
- Camera inference time per frame, Unity-to-Python round-trip delay, Unity frame times

## Fair testing

- Thresholds and decision rules are declared in `configs/v4/` before any evaluation and frozen before the final runs
  (`configs/v4/frozen.json` with hashes); any later change is disclosed in AUDIT.md.
- Development and test data are split by avatar look and by animation clip; test looks and clips are never used in
  development.
- The v4 plan is written in AUDIT.md before the final runs; final runs use a different seed and are run once.
- Code, asset list with download steps (no redistributed Mixamo, Asset Store or VRoid Hub files) and the results
  archive are published.

## Open decisions

- Number of avatar looks and which one is the unseen test look
- WAIT timeout and what happens after it
- Whether a trained sequence model is added next to the rule-based gesture reader
- Target venue and deadline
