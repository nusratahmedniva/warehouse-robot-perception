# v4 completion: upgrades, fixes, calibration and final setup, declared before any of it is built or tested

Written **2026-11-12** by Nusrat (with Claude Code) on branch `nusrat/v4-phase3b-to-final-setup` at `46422b4`, **committed
alone, before any code, scene, config or recording of this task exists** (Stage D0). Everything below is a design or a
rule fixed now; nothing in it is tuned on a result except where a stage says so (D3, the B12 calibration, and the measured
values named in sections 3 and 6). Any change after this commit is added as a dated entry in section 13 before it is
tested.

Stages, in order: **D0** (this note) -> **A** Python (P1-P3, P6, P8, P10-P12, simulator only) -> **U** Unity upgrades
(U1-U6) -> **C** development check (20 trials) -> **D** recordings and calibration -> **E** paper features ->
**F** final setup (no final runs, no freeze). After each stage both test suites run and the stage is committed only if
both pass; a 3-line status is added to `CLAUDE.local.md` section 4.

## 1. Rules that hold for the whole task

1. **Development data only**: looks `sunbox_m1`, `sunbox_f1` and the development clips of `data_splits.json`. `sunbox_f2`
   and every test clip are never rendered, recorded or evaluated in this task, except in Stage F tests that prove they are
   refused outside final mode (those tests use names and configs, not renders).
2. **Allowed changes in Anisha's files** are exactly P1-P12 of the task (Nusrat's exception in `CLAUDE.local.md`
   section 2). Every one is listed in the stage report under "Changes in Anisha's files" and in **AUDIT.md section 15**
   ("Changes made during Anisha's absence (by Nusrat)", dated entries only, P5). Nothing else under `robot_vision/`,
   `docs/` or `external/` changes. Session options are config COPIES passed with `--config` / `--control-config`, never
   edits of her configs.
3. **v3 is not touched**: `configs/roadmap.json`, `configs/hri_control.json`, `configs/hri_perception.json`,
   `configs/trials.json`, `configs/hri_frozen.json`, the v3 scene and the v3 prefab stay as they are. The longer v4 route
   is a **new file `robot_vision/configs/v4/roadmap.json`** (P7), so no v3 test needs retiring for it. If a v3-only test
   still blocks a v4 change, it is retired with a one-line reason in the stage report.
4. **Run protocol before every Unity session** (U6, C, D): free memory and any of vmmem, Chrome, warp-svc, the Claude app
   or the NVIDIA overlay running are reported; programs are never closed by the assistant.
5. **Stop and report** when: a test fails and cannot be fixed within the stage; a decision rule below says stop; a change
   outside P1-P12 seems necessary; anything contradicts `docs/project_flow_v4.md` or `docs/protocol_v3.md` beyond the
   amendments declared here.

## 2. PROCEED (P2; Unity U3)

**Why.** The development sessions of 2026-11-08 and the option A check of 2026-11-09 (`pointing_design.md` section 5)
show that a POINT along the branch straight ahead of the arriving robot points away from the robot's camera and is not
read (J1 FORWARD 0 of 320 held frames, J2 FORWARD 6 of 259). A worker who wants the robot to carry on straight does not
point past their own back: they wave it on. v4 therefore gets a fourth command.

**Meaning.** `PROCEED` = take the branch straight ahead of the robot's arrival direction: the roadmap branch labelled
`FORWARD` at that node (`hri_control.turn_command` of the branch yaw minus the arrival yaw within +-22.5 deg, the rule
`Roadmap.check_labels` already enforces). At the start node A, which has no arrival node, the arrival direction is the
robot's start heading `start_yaw_deg` in `configs/v4/roadmap.json`, and A's only branch is `FORWARD` to J1. A PROCEED at a
node without a `FORWARD` branch is an unclear answer (ask again, then abort), never a guess.

**Avatar (Unity, `WorkerV4`, procedural IK).** The forearm swings forward and up 2 to 4 times within about 2.0 s (one
swing = up and back down), the elbow bent, the upper arm slightly forward, **palm toward the body, fingers together**
(spread well under the reader's open-palm spread, so the STOP geometry never passes on it). The worker keeps swinging for
its hold time (the existing 3.0 to 4.5 s), so a 2.0 s reading window and the dialog hold fit inside it. Truth phases:
`start_delay` (NONE) -> `gesturing` (arm rising to the start pose) -> `holding` (the swings) -> `returning`; `true_command`
`PROCEED`, `point_angle_deg` -1, `arm` the swinging arm. **Three variants** (procedural IK, no third-party clip), varied
per run and worker by the existing seeded variation (swing rate 1.0 to 2.0 Hz, i.e. 2 to 4 swings per 2.0 s; amplitude;
arm; start delay):

| clip name | split | shape |
|---|---|---|
| `proceed_ik_01` | development | elbow about 90 deg, forearm from about 20 deg below to 60 deg above horizontal |
| `proceed_ik_02` | development | larger upper-arm lift, forearm from horizontal to about 75 deg above |
| `proceed_ik_03` | test | smaller swing from the wrist and forearm, elbow about 70 deg |

`data_splits.json` gets these three clip names (2 development, 1 test) (P2).

**Commander script.** At every ask the commander shows **PROCEED when the branch toward goal B is the node's `FORWARD`
branch, POINT otherwise** (option A stance kept for POINT: `worker_v4.json` -> `pointing` unchanged). Development
scenarios also use **WAIT, then the direction** (PROCEED or POINT) within the 20 s WAIT timeout, and **STOP while the
robot drives** (section 6). Bystanders never gesture after the question.

**Reader rule (`gesture_motion.py`, new block `proceed` in `configs/v4/gesture_reader.json`, initial values, P2).** Per
arm, over the last `proceed.window_s` = **2.0 s** of samples with valid shoulders, hips and the arm's wrist:

- wrist height `y` = the wrist above the shoulder midpoint in torso lengths (the reader's existing `wrist_rel`, so
  distance and zoom do not matter);
- **swings**: the turning points of `y` after ignoring reversals smaller than `swing_min` (hysteresis); a cycle = one up
  and one down stretch each at least **`swing_min` = 0.3 torso lengths**; **`cycles_min` = 2**;
- **vertical share** = sum of |dy| over the sum of the wrist path lengths, at least **`vertical_share_min` = 0.7**;
- at least `window.min_valid_fraction` of the expected frames valid (as the other classes).

PROCEED does **not** need a raised arm (the swing starts at about hip height). Order: STOP (short window, overrides) >
PROCEED (moving) > WAIT / POINT (held poses); a moving arm that meets PROCEED is not "moving, no hold yet" any more.
Score = the vertical share. `frame_class` (one frame) never says PROCEED: it needs a window.

**Commander rule (`commander_v4.py`, P2).** A facing person whose reading is PROCEED is a candidate like a person holding
a command, although the arm is not raised (the only change). **Onset (`hri_control_v4._track_onsets`)**: a person's
gesture onset is the first frame in which the arm is raised **or** the reading is PROCEED, so "only a gesture that starts
after the question counts" also holds for PROCEED.

**State machine (`hri_control_v4.py`, P2).** Reader PROCEED -> dialog label `FORWARD` when the node has a `FORWARD`
branch, else NONE with the reason logged. It then goes through the same dialog hold (`gesture_hold_s`) as a resolved
POINT. HUD: `gesture` `PROCEED`, `point_angle_deg` -1.

**Protocol (`docs/protocol_v3.md`, P2 amendment).** `hud.gesture` may be `PROCEED`; `truth.jsonl` `true_command` may be
`PROCEED` (`point_angle_deg` -1); `hud.gesture_accepted` stays a branch command. Nothing else changes.

## 3. Distance bias: ankle height (P1)

`hri_perception.person_distance` (source `ankles`) treats the ankle keypoints as floor points, so every distance is too
long by about `d * h_ankle / (h_cam - h_ankle)` (at 2.0 m with an ankle 0.08 m high and the 360 camera at 1.60 m:
+0.105 m). **Fix:** for source `ankles` the height used is `camera_height_m - ankle_height_m`; `box_bottom` is unchanged
(the box bottom is the sole). New keyword `ankle_height_m=0.0`, so v3 calls are byte-for-byte unchanged; only the v4 360
path passes the value, from a new file `configs/v4/perception.json` (`ankle_height_m`).

**Value: measured, never fitted to distance errors.** Unity adds the truth field **`ankle_height_m`** to every
`truth.jsonl` row (mean world height of the avatar's two ankle bones above the floor under the worker; protocol amendment
P1; `gesture_data.py` accepts and type-checks it, optional for older sessions). The value in `configs/v4/perception.json`
is the **median over all rows of the development looks with phase `idle`** (standing) of the first development session
that has the field (U6), written with the session folder name. Until then the value is 0.0 (= the old behaviour) and the
distance figure E2 shows both.

## 4. Junction metrics and standoff summary (P3)

`hri_eval_dev_v4.py` gets two report blocks (evaluation code only):

- **Per ask** (each "Which direction?" shown): run, node, ask number, true command shown (the commander's truth
  `true_command` in `gesturing` / `holding` after the ask, the last one before the dialog ended), the command read
  (accepted label or the reading at the end), the branch chosen, the **true branch** (`Roadmap.command_toward(node, B)`),
  and the outcome of the **dialog** (all asks at one node visit): `correct` (branch chosen = true branch), `wrong`
  (another branch), `abort` (no branch). A WAIT ask is reported as WAIT and does not end the dialog.
- **Standoff**: at every ask, the 360 distance estimate of the approached person (logged by the controller at the ask,
  P8 record field) against the true distance robot root to commander from `trail.csv` and `truth.jsonl` at that time;
  error, median absolute error, per look and in total; plus the measured standoff (true distance) against the nominal
  2.0 m.

## 5. Hand zoom with tilt (P6; Unity U2)

**Supersedes decision (c) of 2026-11-07 (AUDIT.md 14.15: camera stays level, no tilt command).** That decision was made
because a level camera cannot narrow onto a raised hand at 2 m; tilting the camera toward the hand is what makes the zoom
act at the asking distance. Declared here as a change of an earlier decision (AUDIT.md section 15).

- **Protocol (amendment, `docs/protocol_v3.md`)**: `command` gains **`tilt_deg`** (number): the pan-tilt camera's tilt,
  **+ = up**, **-1 = the configured default (level, 0 deg)** exactly like `vertical_fov_deg` -1 (Unity keeps nothing from
  earlier commands); other values are clamped to Unity's tilt range. Because the range is **0 to `tilt_max_deg`** (up
  only; no hand is below the level camera at the asking distance), -1 is never a real request. `frame_pan_tilt` already
  carries `pan_deg` and `tilt_deg`: they become the values **at render time of that frame**, like the field of view and
  the intrinsics.
- **Unity**: `PanTiltCamera.SetTiltDeg` clamped to `pan_tilt_camera.tilt_min_deg` .. `tilt_max_deg` = **0 .. 35 deg** in
  `robot_unity_v4.json` (35 deg = the 23 deg of a raised hand at 2 m plus margin); the pan mount still rotates about the
  robot's up axis, the tilt about the camera's own x axis; frame headers report pan, tilt, field of view and intrinsics
  of the rendered frame; HUD shows zoom state, field of view and tilt. The self-visibility check covers every pan, tilt
  and field of view in range.
- **Zoom rule (`hri_control_v4.ZoomController`, `control*.json` -> `zoom`)**: while a commander is read, the tilt aims the
  **fit box** centre at the image centre (rate-limited by `tilt_max_change_deg_per_s` = 30, clamped 0..35), and the field
  of view narrows until the hand fills `hand_share` of the image height, never narrower than the fit box with
  `arm_fit_margin`. **Fit box** = nose, both shoulders, both hips and the elbow and wrist of the active arm: everything the
  reader and the facing test need, so a close-up loses no feature. Hand lost -> widen in steps as now; the tilt returns
  to level when the dialog ends. `zoom.enabled` false -> `vertical_fov_deg` -1 **and** `tilt_deg` -1 on every command.
- **Close-up hand reading**: MediaPipe reads the hand on the zoomed frame (the hand's pixels grow with the magnification);
  no separate crop.
- **Geometry corrected for tilt (Python, P6)**: every pixel ray is rotated from the tilted camera into a level camera
  frame before an azimuth or elevation is taken: ray `(a, b, 1)` -> `(a, b cos t - sin t, b sin t + cos t)` (y down,
  t = tilt up). Applies to the POINT 3D direction (`arm_solutions`), the hand cross-check, the person bearing
  (`box_bearing_deg`, `body_bearing_deg`) and `zoom_target`. Image-plane features (angles from up, torso units) stay in the
  image: a pitch keeps the centre column vertical and the deviation off-centre is small for the fit box; stated as a
  limitation. Unit tests with synthetic keypoints at tilt 0, 15 and 30 deg check that the tilt-corrected results equal the
  level-camera results of the same 3D scene.

## 6. Longer route, start search, timeout (P7, P8; Unity U3)

**Map (`robot_vision/configs/v4/roadmap.json`, new; v3 `configs/roadmap.json` unchanged).** Unity floor coordinates;
open aisles of the generated warehouse (racks at x = -12.5, 0, 12.5 and z = -15, -5, 5, 15, walls near +-26 m).

| node | x | z | kind | arrive from | branches |
|---|---|---|---|---|---|
| A | 6.25 | -20.0 | start (asks; `start_yaw_deg` 0) | - | FORWARD J1 |
| J1 | 6.25 | 0.0 | junction | A | FORWARD E1, RIGHT J3, LEFT J2 |
| J2 | -6.25 | 0.0 | junction | J1 | FORWARD J4, RIGHT E2 |
| J3 | 18.75 | 0.0 | junction | J1 | LEFT E3, RIGHT E4 |
| J4 | -18.75 | 0.0 | junction | J2 | RIGHT E5, LEFT E6 |
| E1 | 6.25 | 20.0 | endpoint | | |
| E2 | -6.25 | 20.0 | endpoint | | |
| E3 | 18.75 | 20.0 | endpoint | | |
| E4 | 18.75 | -20.0 | endpoint | | |
| E5 | -18.75 | 20.0 | endpoint | | |
| E6 | -18.75 | -20.0 | endpoint | | |

Route lengths along the roads: E1 40.0 m, E2 52.5, E3 52.5, E4 52.5, E5 65.0, E6 65.0 m; 4 junctions, 6 endpoints, 2 to
4 dialogs per run (A plus 1 to 3 junctions). PROCEED occurs at A (always), J1 (E1) and J2 (E5, E6); POINT at J1 (left,
right), J2 (right), J3 and J4 (left, right). Worker stands: the existing rule (2.5 m ahead and 2.5 m right of the node
in its arrival direction): A (8.75, -17.5), J1 (8.75, 2.5), J2 (-8.75, 2.5), J3 (21.25, -2.5), J4 (-21.25, 2.5). Unity
builds the v4 scene roadmap from this file, and an Edit Mode test requires the scene roadmap and the file to be
identical (as the v3 test does for v3). The grid and the A* are recomputed for every run as now; the A* length must still
equal Python's within 0.001 m.

**Worker layout (interpretation, stated for review).** "A worker at A and at each of the 4 junctions" is realised with
the existing **moved-commander layout**: the one commander stands at A's stand at the start and is moved to the stand of
the node the robot is sent to once it is idle, so from the robot's view a worker waits at A and at every junction it
reaches. Five standing avatars would make every run a bystander run in Python's evaluation (`Run.bystanders` = more than
one `worker_id` in `truth.jsonl`) and exceed `max_active_avatars` (4). Bystander scenes add up to 3 bystanders at
declared stands (stands for J3 and J4 added on the same rule: off every road by at least 1.5 m, at least 4 m from every
commander stand).

**Start search (P8).** The robot starts in `scan` at A (not `navigate`): it searches with the 360 camera, approaches the
nearest person to 2.0 m, asks, and drives toward J1 only after an accepted PROCEED. **The robot never drives along the
route (navigate / execute) without an accepted instruction**; approaching the person and the re-ask repositioning are
part of the dialog and stay. Abort at A as at any junction (scan timeout, two unclear asks). The controller also records,
at every ask, the 360 distance estimate of the approached person (`ask_distance_est_m`, for section 4).

**STOP while driving (U3 scenario).** In declared STOP scenarios the commander of the next junction, standing at its
stand, shows STOP once while the robot drives toward that junction (robot 6 to 9 m away), holds it 2.0 to 3.0 s, then
lowers it; the robot must stop while the palm is read and resume afterwards (the existing safety rule). STOP is scored as
a stop event, not as a junction answer.

**Timeout rule (P7, `final_plan.json` `timeout_s`).** v3's 240 s fitted a route of at most 37.5 m with two dialogs. The v4
final timeout is computed once, from the Stage C development session, as

  `timeout_s = ceil_to_10( 1.5 * L_max / v_run + wait_timeout_s )`, and never below 240 s,

with `L_max` = 65.0 m (the longest route), `v_run` = the median over the SUCCESSFUL Stage C runs of (road length of the
run's route / run duration), i.e. the measured average speed including dialogs, 1.5 = a 50 % margin, and
`wait_timeout_s` = 20 s so that one WAIT always fits. It is written to `final_plan.json` with the session folder and the
numbers, before Stage D. **Development sessions before that use a provisional 420 s** (= 65 m at a pessimistic 0.2 m/s
average plus 20 s, rounded up), declared now; a development timeout is not a result.

**Trial plan (P7).** `final_plan.json`: task Task2 (now on the v4 roadmap), seeds 1 / 2, 20 runs, success 0.3 m
unchanged; the goal order is `hri_trials.goal_order(seed, ["E1".."E6"], n)` (the same generator). **Disclosed:** with six
new endpoints the final goal order is no longer the v3 Task 2 order, so RQ1's "same goals" argument for B3 no longer
holds; RQ1 compares v3 and v4 as different routes and lists it among the declared differences.
`tests/test_v4_frozen.py`'s pinned goal order follows the new order (P7).

## 7. The new robot (U1) and the 360 bottom band (P9)

Our own design built by an Editor script from Unity primitives and our own materials (no third-party asset), as a **new
v4 prefab** (the v3 prefab and scene keep the red box): industrial AMR look, rounded chassis (box core with capsule
rounded ends), front and rear bumper strips, four visible wheels, a lidar puck on the chassis top, a slim mast carrying
the pan-tilt head at **1.20 m** and the 360 camera at **1.60 m** (heights and mounts exactly as now). Footprint,
colliders and the NavMesh agent are those of the current prefab (built from the same config values). **Status light
ring** (emissive, not a light source, so it lights nothing in the scene): green driving (`navigate`, `execute`), blue
searching or approaching (`scan`, `approach`), yellow asking or reading (`ask`, `read`, `wait`), red stopped or STOP
(any "stopped" state, `aborted`), white idle / done. **Front display**: the robot's message on a forward-facing panel
("Which direction?", "One moment...", "Going LEFT", ...), from the command's `screen_text` and the accepted branch.
Checks: the self-visibility check passes for every pan, tilt and field of view in range; the leak test passes; the
body's extent in the 360 image is measured (rows of the panorama that show robot pixels, rendered with and without the
body). **P9** changes the 360 excluded bottom band only if the body reaches above the current band limit, and then to the
measured extent; otherwise nothing changes.

## 8. Visualisation (U4, U5) and demo video (E4)

All on the `GroundTruth` layer (both robot cameras skip it; the leak test passes) or on screen-space overlays that no
robot camera renders:

- **Trail** coloured by robot state (the light-ring colours) with direction arrows every 2 m.
- **Ask markers** on the floor at each ask: command read, branch chosen, true command; green if the branch is correct,
  red if wrong, grey if aborted.
- **Instructed path**: after each accepted instruction the road segment to the next node is revealed (drawn separately
  from the optimal path).
- **Toggle keys**: F1 trail, F2 ask markers, F3 instructed path, F4 optimal path, F5 HUD minimap, F6 ground-truth
  minimap (labelled "GROUND TRUTH").
- **HUD minimap of the robot's own knowledge**: its pose, the people it detects (360, with distance), its current target
  and planned path (NavMesh corners it requested), the roadmap. No ground truth. The **optional ground-truth minimap** is
  separate, off by default, and labelled.
- **Demo-video mode (E4)**: follow camera plus picture-in-picture of both robot camera images and the HUD; off by default;
  Edit Mode tests prove it never changes either robot camera (culling masks, targets, transforms) or the leak test.

## 9. Bridge additions (P10, P11, P12)

- **P10** `bridge/server.py --control-config PATH` (default `configs/v4/control.json`, unchanged behaviour).
- **P11** `configs/v4/control_zoom_on.json` and `control_zoom_off.json`, identical to `control.json` except
  `zoom.enabled` (a test pins this). Both are in the freeze list. With `--final-setting NAME` the server refuses a
  `--control-config` other than the setting's file (`zoom_off` -> `control_zoom_off.json`; the other three settings ->
  `control_zoom_on.json`).
- **P12** `model_outputs.jsonl` in the bridge run folder: one compact JSON line per processed camera frame: camera,
  `time_s`, frame index, pose, pan, tilt, field of view and intrinsics; for the 360: per person box, 17 keypoints with
  scores, track id, bearing, distance and source; for the pan-tilt: per person box, track id, keypoints with scores and
  the linked hand(s) (21 landmarks, world landmarks, label and score, box). Numbers rounded (pixels 1 decimal, scores 3).
  Images stay at every 20th frame. It is what the calibration replays (P4).

## 10. Calibration (P4, Stage D3)

A sweep tool implementing **B12 exactly** (AUDIT.md 14.11 item 3): for each initial threshold, the value with the
highest development accuracy among those with coverage >= 0.8; ties go to the v3 value, else to the more conservative
value (the one that answers less often). Data: the Stage D2 recordings of `sunbox_m1` and `sunbox_f1` only (the tool
refuses any other look and any test clip). Method: the reader (and the commander rule) are re-run offline on
`model_outputs.jsonl`, one threshold at a time with all others at their committed values, and scored against the
commander's `truth.jsonl` rows in `gesturing` / `holding` (accuracy = correct among answered frames, coverage = answered
among those frames). Grids, fixed now:

| threshold | grid |
|---|---|
| `window.window_s` | 1.0, 1.5, 2.0 |
| `window.min_valid_fraction` | 0.5, 0.6, 0.7, 0.8 |
| `window.hold_min_s` | 0.3, 0.4, 0.5, 0.6 |
| `window.stop_window_s` | 0.2, 0.3, 0.4, 0.5 |
| `keypoints.arm_raised_margin` | 0.10, 0.15, 0.20, 0.25, 0.30, 0.35 |
| `motion.still_speed_max` | 0.2, 0.3, 0.4, 0.5, 0.6 |
| `motion.motion_path_min` | 0.2, 0.3, 0.4, 0.5, 0.6 |
| `point.point_arm_extension_min_deg` | 120, 130, 140, 150, 160 |
| `point.segment_disagreement_max_deg` | 30, 45, 60 |
| `point.point_elevation_max_deg` | 45, 60, 75 |
| `hand.finger_extended_ratio` | 1.4, 1.5, 1.6, 1.7, 1.8 |
| `hand.finger_curled_ratio` | 1.0, 1.1, 1.2, 1.3 |
| `hand.palm_spread_min_deg` | 10, 15, 20, 25, 30 |
| `hand.index_up_tol_deg` | 20, 30, 40, 50 |
| `hand.wait_forearm_vertical_tol_deg` | 30, 40, 50, 60 |
| `hand.wait_arm_extension_max_deg` | 110, 120, 130, 140 |
| `decision.class_share_min` | 0.5, 0.6, 0.7, 0.8, 0.9 |
| `decision.class_margin_min` | 0.1, 0.2, 0.3 |
| `proceed.window_s` | 1.5, 2.0, 2.5 |
| `proceed.cycles_min` | 1.5, 2, 2.5, 3 |
| `proceed.swing_min` | 0.20, 0.25, 0.30, 0.35, 0.40 |
| `proceed.vertical_share_min` | 0.5, 0.6, 0.7, 0.8 |
| commander `facing_shoulder_ratio_min` | 0.3, 0.4, 0.5, 0.6 |
| control `dialog.branch_match_max_deg` (scored on resolved held POINT frames) | 20, 25, 30, 35, 40 |

Measured, not swept: `point.arm_length_in_shoulder_widths` = the median YOLO ratio on the development looks (AUDIT.md
14.16 item 3) and `ankle_height_m` (section 3). Not swept (v3 frozen origin, logged-only, or no per-frame accuracy without
re-rendering): `frame_hz`, `body_kp_conf_min`, `raised_max_abs_deg`, `arm_length_min`, `hand_link_max_shoulder_widths`,
the score minima, the cross-check values, the zoom values and the dialog timings. The tool writes the chosen values into
the v4 configs her docs name (`gesture_reader.json`, `commander.json`, all three `control*.json` identically), each with
the date, the rule and the evidence (grid, accuracy and coverage per value), and the report lists every threshold old and
new.

## 11. Decision rules (declared now)

- **Stage U priority**: if not everything can be finished reliably, U2 and U3 first, then U1, then U4, then U5; what
  remains is reported.
- **Stage C** (20 trials, development seed 1, development looks alternating, development clips, zoom on, no bystanders,
  commander shows PROCEED / POINT, no WAIT or STOP script). Unit = a **dialog** (all asks at one node visit), outcome
  correct / wrong / abort as in section 4.
  - **Rule 1 (junction level):** for every development look and every (node, true command) pair that occurs (node in
    A, J1-J4; command PROCEED or POINT), the share of dialogs ending with the correct branch is **at least 0.8** (4 of 5;
    with n dialogs, at least ceil(0.8 n) correct), **and zero wrong-branch decisions overall**. Aborts count as failures,
    not as wrong branches.
  - **Rule 2 (distance):** the median absolute error of the 360 distance estimate against the true distance at the asks
    is **at most 0.10 m** (all asks of the session).
  - If rule 1 or rule 2 fails: **STOP and report per pair, without tuning.** Exception: if rule 1 fails only through
    aborts (no wrong branch), continue to Stage D and report it.
  - From the same session: `timeout_s` by the rule of section 6.
- **Stage D4** (3 trials per recorded condition, after the calibration): **STOP and report if more than one trial in any
  condition aborts, or if any wrong-branch decision occurs.**
- **No threshold changes outside D3.** A value changed after seeing development results is listed in AUDIT.md section 15
  with the reason.

## 12. Declared differences from earlier decisions (also in AUDIT.md section 15)

1. Commands: POINT, WAIT, STOP **plus PROCEED** (section 2); the spec's table gains a row (P2 amendment).
2. The pan-tilt camera **tilts** toward the hand (section 5), superseding AUDIT.md 14.15 decision (c).
3. The v4 route is **new** (section 6): RQ1 no longer compares the same goals as the v3 Task 2 final (B3 rationale), and
   the final timeout follows the rule of section 6 instead of v3's 240 s (B5).
4. The robot asks at the start node A before driving (P8): one more dialog per run than v3.
5. Distance from ankles corrects for the ankle height (P1).
6. New robot body (U1): the robot looks different in the workers' scenes; camera heights and mounts unchanged.

## 13. Changes after this declaration

Dated entries, each written before the changed design is tested in a Play session.

- **2026-11-12 (Stage U, before U6).**
  1. *New robot body (section 7):* built by `Tools > Warehouse v4 > Build v4 Robot Body` as additions to the robot instance in
     `WarehouseRobot_v4.unity` (child `BodyV4`, restyled wheel visuals, `RobotStatusDisplay`), with the v3 visuals of that instance
     deactivated, instead of a separate v4 prefab. Reason: every reference of the v4 scene (bridge, HUD, follow camera, trial
     runner) keeps pointing at the same robot root; root, Rigidbody, colliders, NavMesh settings, drive and both camera mounts and
     heights are untouched; the v3 prefab and scene are unchanged. The status "ring" is a lit collar on the mast plus a light bar
     above the front bumper.
  2. *Toggle keys (section 8):* F4 stays the HUD (as before); F5 trail, F6 ask markers, F7 instructed path, F8 optimal path, F9 the
     robot's minimap, F10 the ground-truth minimap.
  3. *STOP while driving (section 6):* the commander shows it the first moment the robot, driving toward the commander's node, is
     6 to 9 m away AND the commander has noticed it (`behaviour.notice_distance_m` 8 m), i.e. in practice at 6 to 8 m, so the open
     palm faces the robot.
  4. *Truth `ankle_height_m` (section 3):* the mean height of the two Humanoid foot bones (the ankle joints) above the worker's root
     (which stands on the floor), 4 decimals, in every row.
  5. *Commander at A:* spawned at A's stand at the start of each run; the moved-commander layout otherwise as before.
  6. *Session options:* the WAIT-then-direction, STOP and bystander sessions use declared copies of `trial_workers_v4.json` in
     `Avatar/Config/sessions/` (each differs only in its option; an Edit Mode test checks it), selected with `TrialPlayV4 -workersConfig`.
- **2026-11-12 (calibration details, before any calibration data exists; `robot_vision/calibrate_v4.py`).**
  1. B12 leaves open what happens when no grid value reaches coverage 0.8: the committed value stays, and the report says so.
     A tie in accuracy and coverage that B12 does not break keeps the committed value if it is among the tied, else the first of
     the grid.
  2. The arm ratio (`point.arm_length_in_shoulder_widths`, measured, AUDIT.md 14.16 item 3) is the median over held POINT frames of
     the development looks whose TRUE pointed direction lies within 30 deg of the camera's image plane (a foreshortened arm would
     bias the median low; the ratio models the full arm).
  3. Frames are scored against the commander's truth row nearest in time (within `truth_join_max_s`); the person read is the one
     whose bearing is nearest the commander's true bearing within `match_bearing_deg` (the matching of `hri_eval_dev_v4.py`).
- **2026-11-12 (Stage D2, bystander stands; written after the failed R3 session and before it is recorded again).**
  1. *Finding:* R3 (`trials_development_Task2_20261112_175544` + `bridge_guide_20261112_175450`, 10 runs) aborted 10 of 10 at J1
     ("gesture unclear after 2 asks"). The robot chooses the nearest person when it scans, stopped up to `arrive_junction_m`
     (0.3 m) before the node. The stand "J1 behind-right" (ahead -2.5, right +2.5) is exactly as far from J1 as the commander's
     stand, so a robot that stops short of the node is nearer to that bystander and approaches it. The commander was then behind
     the robot and out of the pan-tilt view. The two ahead-left stands were exact ties at the node as well (margin 0.0 m).
     It was a fault in where the bystanders stood; the reader played no part in it. The session is kept and reported; it is not
     used for the bystander measures.
  2. *New rule:* every bystander is at least `bystanders.nearer_margin_m` = **1.0 m** farther from the robot than the commander's
     stand at every point of the robot's approach to every ask node. The approach is the last `bystanders.approach_m` = **3.0 m**
     of the arrival road up to the node (= `drive.junction_slow_radius_m` of `configs/hri_control.json`, where the robot slows
     for the junction; an Edit Mode test pins the equality); at the start node A, the start position itself. Why 1.0 m: it covers
     the stop tolerance (0.3 m), the robot's lateral offset from the road centre and the error of the 360 distance estimate at
     once, with room to spare. `TrialRunnerV4` refuses a session whose stand breaks the rule (sampled every 0.05 m), next to
     the existing road-clearance, commander-distance, free-cell and collider checks, and the Edit Mode test checks every
     configured stand on `configs/v4/roadmap.json` (it checked the v3 map before).
  3. *New stands (the smallest 0.5 m steps that pass every check):* the J1 behind-right stand is **removed**; J1 ahead-left
     moves **ahead** to (ahead 4.0, right -2.5) = (3.75, 4.0), worst margin 1.18 m (moving it left instead would bring it
     nearer to J2's approach road); J2 ahead-left moves **left** to (ahead 2.5, right -4.5) = (-8.75, -4.5), worst margin
     1.07 m (moving it ahead would bring it nearer to J4's approach road). `bystanders.count` becomes **2** (D1 said 3), in
     `trial_workers_v4.json` and all three session copies; `max_active_avatars` stays 4.
  4. *R3 again:* 10 runs, seed 1, development looks, as declared in `recording_plan_d1.md` apart from the two points above.
     The calibration (D3) reports the failed R3 session but takes the bystander measures from the new one only.
