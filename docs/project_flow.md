# Avatar-Mediated Human-Robot Interaction in Virtual Worlds: approved flow

## The idea in steps

The robot never knows where B is; the workers' gestures lead it there, one junction at a time.

1. Start: the robot stands at point A. Goal B is known only to the evaluation, not to the robot.
2. Navigate: it drives along the warehouse roadmap toward the next junction. Unity's NavMesh gives the path; Python steers with a speed (v) and a turn rate (ω).
3. Slow down and scan: near the junction it slows and uses its 360° camera to find every person around it, then picks the nearest one.
4. Approach: it drives to 2.0 m in front of that worker and turns to face them.
5. Ask: it shows "Which direction?" on screen and aims its pan-tilt camera at the worker.
6. Read the gesture: it reads the worker's arm direction from body keypoints. The same answer must hold for 1.0 s; if unclear, it asks once more, then aborts.
7. Execute the step: it takes the branch the worker pointed to and drives on to the next junction.
8. Repeat: steps 3 to 7 happen at every junction until the robot reaches B.
9. End and log: SUCCESS when it stops within 0.3 m of B; FAILURE on timeout, collision, getting stuck, wrong goal or abort. Every run is added to the results log with the running success ratio.

Always active: an open palm (STOP) or a person stepping into the path stops the robot at once. If Python stops answering for 0.3 s, Unity stops the robot by itself.

## Tasks and trials

Two tasks, each run many times automatically, give the results.

- Task 1, straight A to B: the robot drives straight from A to B and stops at checkpoints along the way; a worker stands at each one (the same avatar, one per checkpoint, 1.0 m ahead and 2.5 m to the right of the checkpoint, facing the arriving robot, clear of the robot's straight path) and signals FORWARD, so the robot reads it and drives on past. The number of checkpoints and the worker offsets are in `robot_vision/configs/task1_route.json` (default 3, evenly spaced on the straight line A -> J1 -> E1; the middle one falls on J1, so the stops are C1, J1, C3). This is the baseline for speed, timing and gesture reading. (Changed 21 October 2026 before any Task 1 final run, declared design changes, AUDIT.md section 9; before: one stop, J1, and then one worker moved from stop to stop.)
- Task 2, guided route: a roadmap with 2 to 3 junctions and several possible end points; B changes every trial, and the workers at the junctions guide the robot to it.
- One avatar: a single worker character is coded and used throughout and always faces the arriving robot; in Task 1 one copy of it stands at each checkpoint, in Task 2 one copy stands at each junction (the scene worker at J1, a copy made at Play at J2), each showing the command toward B for the whole trial. (Task 2 changed 22 October 2026, declared design change after the Task 2 final and its replication, for demonstrations only, AUDIT.md section 12; both reported Task 2 runs used the earlier layout: the one worker moved to each junction as the robot headed there.)
- Fair testing: thresholds are set on development trials (one random seed), then frozen; the final trials use a different seed and are run once.

## Metrics and data to record

- Outcome (SUCCESS or FAILURE) and failure reason (timeout, collision, stuck, wrong goal, aborted)
- Running success ratio over all runs so far
- Point A and point B
- Straight-line distance A to B, and distance actually travelled
- Total time A to B, plus time per step (navigate, scan, approach, ask, gesture, execute)
- Average and maximum speed
- Average and maximum turning speed
- Final distance from B
- Gesture shown vs gesture read, at every junction
- Camera inference time per frame (per model and total)
- Unity-to-Python round-trip delay
- Collisions and closest distance to any human