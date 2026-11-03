# v4 gesture reader: design (no code yet)

Status: **design for review, 2026-10-23**. Nothing here is implemented, and **no threshold has a value**: every value in
the table at the end is empty for Anisha to decide, and each is set on development data only (looks and clips marked
`development` in `configs/v4/data_splits.json`, enforced by `data_splits_v4.guard_run`). Test looks and clips are never
used to set or look at a value.

Parts that are proposals rather than consequences of the spec are marked **(proposal)**. Open questions are collected
in the last section.

## What the reader does

It reads a short window of the commander's wrist, elbow and hand movement from the pan-tilt camera and answers, for the
robot's state machine and the HUD (`hud.gesture`, `gesture_score`, `gesture_raw`, `point_angle_deg`,
`docs/protocol_v3.md`):

| answer | meaning |
|---|---|
| `POINT` + angle | the person points; the angle is the pointed direction relative to the robot's forward axis (+ = right) |
| `WAIT` | one hand raised, index finger up ("one moment") |
| `STOP` | open palm pushed toward the robot |
| `NONE` | the window shows no command, or the reader cannot tell which; never a guess |
| `insufficient_history` | fewer valid frames than needed so far; reported as such, not as `NONE` |

Following the project rule (unknown over guess), anything ambiguous is `NONE` with a reason string (`why`), as in the v3
reader (`hri_perception.classify_gesture`). STOP is the safety command: it is read on its own short hold and may
interrupt anything (the v3 rule, `stop_hold_s`), so STOP decisions use their own thresholds.

## Inputs

**Frames.** `frame_pan_tilt` JPEGs, 730 x 530, at `frame_pan_tilt_hz` (10 Hz, `configs/v4/bridge.json`), each with its
render-time intrinsics and `vertical_fov_deg` (protocol v3). The camera is aimed at the commander (`pan_deg`), so the
person is near the image centre. Zoom (Phase 4) changes the pixel size of the person, never the angles computed below
(they come from keypoint differences, which are scale-invariant at fx = fy), so the reader works on pixel vectors and
normalises lengths by the torso, not by pixels.

**Body keypoints: YOLO11s-pose (COCO 17), already in `hri_perception.py`.** Used: shoulders (5, 6), elbows (7, 8),
wrists (9, 10), hips (11, 12) for the torso length, nose and eyes (0 to 2) only to know the head height. Each with its
confidence; a keypoint under `body_kp_conf_min` is missing for that frame. Known weakness from v3: YOLO places elbow and
wrist too low on raised arms of the Mixamo avatar, so segment agreement is checked, not assumed.

**Hand landmarks: MediaPipe Gesture Recognizer through the adapter (`gesture_adapter.py`, mode `person_crop`).** Used:
the 21 hand landmarks (wrist 0; thumb 1 to 4; index MCP 5, tip 8; middle 9 to 12; ring 13 to 16; pinky 17 to 20), the
handedness, and the raw category with its raw score (`Pointing_Up`, `Open_Palm`, `Closed_Fist`, ...). The adapter
applies no threshold, so thresholds are the reader's. The crop is placed on the YOLO wrist of the arm being read
(`hand_crop_margin`) so the hand is attributed to the commander's body (hand linked to body by keypoints).

**Window.** The last `window_s` seconds (spec: 1 to 2 s, i.e. 10 to 20 frames at 10 Hz) of both streams, sliding, one
answer per new frame. Frames without a usable body keypoint set or hand are kept as gaps, not interpolated; the reader
needs at least `min_valid_fraction` of the window valid, else `insufficient_history`.

**Not used:** the 360 camera (who the commander is belongs to the commander rule, Phase 3), depth (none is rendered) and
the ground-truth files (evaluation only).

## Which arm

Both arms are read each frame. The active arm is the one whose wrist is raised (above the hip line by
`arm_raised_margin`) and moves or is held in a pose; if both qualify with different answers the result is `NONE` (v3
rule). The commander is gesturing with one hand at a time by construction of the avatar clips (`arm` in
`truth.jsonl`).

## Moving gesture or still hand

Features per arm over the window, with lengths in torso lengths (shoulder midpoint to hip midpoint) so distance and
zoom do not matter:

- wrist speed per frame pair, its peak and the window's path length;
- net displacement of the wrist (first to last valid frame);
- elbow angle change over the window.

A frame pair is *moving* when the wrist speed exceeds `still_speed_max` and *still* otherwise. A window is a
**moving gesture** when its path length is at least `motion_path_min`; it is a **held pose** when the last
`hold_min_s` of the window are all still. The three commands use these differently:

- POINT is a movement toward a target followed by a hold (spec: "points with a moving arm"). The angle is taken **only
  from the held part** (the last still stretch of at least `hold_min_s`), never from the swing. A window with motion
  and no hold yet is `NONE` with `why = "moving, no hold yet"`, so the robot waits for the arm to settle rather than
  reading an angle mid-swing.
- WAIT may be fully still or a small raise-and-hold; it is a held pose of the raised hand near the head.
- STOP is a push: hand scale grows over the window, then holds.

A still hand with no raised arm is not a gesture (`NONE`). Whether a *still raised* hand counts is exactly the case
that distinguishes WAIT (index up) from a bystander resting a hand on the head; the facing and gesturing test for that
is the commander rule (Phase 3), not this reader.

## POINT: the direction angle (Phase 2 proposal, superseded by the Phase 3 geometry below)

**(proposal)** Keep the v3 geometry, which was validated for five fixed directions, and make it continuous:

1. For the active arm, take the two image directions shoulder to wrist and elbow to wrist, measured from straight up
   in the image (`arm_angle_deg`); both must exist and agree within `segment_disagreement_max_deg`, as in v3. Their
   circular mean is the arm angle theta in the image. Negative = image left = the robot's left, because the commander
   faces the robot.
2. Over the held stretch, take the circular mean of theta over its frames (`hold_min_s` or more, frames with both
   segments valid). The pointed route angle relative to the robot's forward axis is **that mean** (arm straight up = 0,
   arm sideways = +/- 90, positive to the robot's right).
3. The arm must be long enough in the image: shoulder-to-wrist at least `arm_length_min` shoulder widths, so a
   foreshortened arm pointing at the camera is not given an angle (v3 `min_arm_to_shoulder_width`).
4. An arm lower than `raised_max_abs_deg` from straight up is treated as down (v3).
5. The state machine then takes the branch whose direction is closest to this angle, if within `branch_match_max_deg`;
   otherwise it asks again (that tolerance belongs to the decision rules, listed here because it fixes how accurate the
   angle must be).

Why the image-plane angle: with one RGB camera there is no depth, so the 3D pointing vector is not observable. Pointing
in the image plane is what the v3 reader measured and what the avatar clips (Mixamo, a person facing the robot) have to
produce. If the clips point *toward* the camera or away from it, theta is wrong by construction; that is a limit of the
sensor and is reported (angle error per clip, not hidden). Pointing behind the commander and pointing toward the camera
are both outside what this reader can resolve. **(open question 1.)**

The quantity compared with the truth is `point_angle_deg` of `truth.jsonl` (hold-phase mean,
`gesture_data.Clip.point_angle_hold_deg`); the angle error is the wrapped difference.

## POINT, Phase 3 geometry (implemented in `gesture_motion.py`)

Decided 2026-10-24 (see Decided): the pointed direction is a 3D direction, not the image-plane angle alone.

1. **Rays.** For the shoulder and the wrist of the pointing arm take the pixel rays `((u - cx) / fx, (v - cy) / fy, 1)` of
   the frame (intrinsics at render time, so zoom is handled). Put the shoulder at depth 1.
2. **Arm length.** The full length of the arm is `arm_length_in_shoulder_widths` (1.4) times the shoulder width, measured in
   the same units from the two shoulder rays (the metric shoulder width cancels out).
3. **Depth of the wrist.** The wrist is at `Zw` along its ray with `|Zw * ray_wrist - ray_shoulder| = arm length`. This has two
   roots: the arm points away from the camera (`away`, larger `Zw`) or toward it (`toward`). They are two physically possible
   arms behind the same pixels; foreshortening is ill-conditioned near the image plane (a 10 per cent error in the arm length
   ratio moves the wrist depth by up to 0.2 arm lengths), so the reader does not discard either. If no root is real the
   wrist is taken at the shoulder's depth (one solution).
4. **Direction.** `d = Zw * ray_wrist - ray_shoulder`; camera azimuth `atan2(d_x, d_z)`, elevation above horizontal. A
   candidate steeper than `point_elevation_max_deg` has no ground direction and is dropped. The camera is assumed level
   (`tilt_deg` is not used).
5. **World direction.** Camera yaw = robot yaw minus `pan_deg` (pan > 0 = left); the world yaw of a candidate is the camera yaw
   plus its azimuth. Averaged over the held stretch.
6. **Roadmap resolution (`hri_control_v4.resolve_point`).** Each candidate goes to the nearest of the junction's branches and
   the **arrival direction**. A candidate nearest to the arrival direction is dropped (the branch the robot came from is never
   an answer); one farther than `branch_match_max_deg` (30) from its branch is dropped. One distinct branch left = the answer;
   none = unclear; two = ambiguous = unclear (ask again, then abort).
7. **Hand cross-check.** The MediaPipe hand world landmarks (index MCP to tip, or the hand axis when the index is not
   extended) give an independent finger azimuth. It names the supported candidate (`prefers`). It is logged always and decides
   a two-branch tie only with `use_hand_crosscheck_as_tiebreak` (off). Assumption to verify: world z increases away from the
   camera (`hand_world_z_away_positive`).

**What the simulation shows (tests/test_hri_sim_v4_trials.py; a property of the geometry, not a measurement).** The two
candidates are mirror images about the image plane. LEFT and RIGHT (arm in the image plane) are their own mirrors. From a
viewpoint along the arrival axis the mirror of FORWARD is the arrival direction, so all three branches resolve. From the
viewpoint the v3 approach gives at the roadmap's worker stand (about 45 deg off that axis) the mirror of FORWARD lands on LEFT
and the mirror of LEFT on FORWARD: those two are ambiguous for the roadmap alone and the robot fails safe (unclear, ask again,
abort), never taking a wrong branch. A perfect hand cross-check as tie-break resolves them; a wrong one sends the robot the
wrong way. To be measured in the development evaluation (`hri_eval_dev_v4.py`: ambiguous share, angle error of the better and
of the resolved reading, correct-branch rate).

## Two-view study (simulator, `hri_sim_v4.two_view_study`; not a measurement)

J1, no bystanders, 20 seeds per row, angle noise added per pan-tilt frame (the reader averages it over the held pose, so a
systematic error such as a wrong arm-length ratio is NOT modelled). FORWARD and LEFT are ambiguous from the v3 viewpoint
(the mirror of FORWARD is LEFT and the reverse); RIGHT never is.

| angle noise (deg) | re-ask shift (m) | FORWARD: ambiguous asks, resolved right / wrong | LEFT: ambiguous asks, resolved right / wrong | RIGHT: ambiguous asks |
|---|---|---|---|---|
| 0, 3, 6 | 0.4, 0.8, 1.2 | 20 of 20: 20 / 0 | 20 of 20: 20 / 0 | 0 of 20 |
| 10 | 0.4 | 20 of 20: 18 / 2 | 20 of 20: 18 / 2 | 0 of 20 |
| 10 | 0.8, 1.2 | 20 of 20: 20 / 0 | 20 of 20: 20 / 0 | 0 of 20 |

A 0.4 m shift at 2 m turns the camera by about 11 deg, so the mirror candidate moves by about 23 deg while the true direction
stays put; with the 10 deg tolerance this stops separating them once the noise approaches 10 deg, and then a wrong branch can
be accepted (2 of 40 here). A larger shift separates them with more noise. Anisha decides whether to raise `reask_shift_m`
for v4 (it is a frozen v3 value for v3 and is not changed for v3).

## WAIT (index finger up) versus STOP (open palm)

They must look clearly different (spec), so the reader uses three independent cues and requires them to agree:

1. **MediaPipe category and score** from the adapter: `Pointing_Up` for WAIT, `Open_Palm` for STOP. Its raw score must
   reach `wait_score_min` or `stop_score_min`.
2. **Finger extension from the 21 landmarks.** A finger is *extended* when its tip is farther from the wrist than its
   MCP joint by at least `finger_extended_ratio` (tip distance over MCP distance, from the wrist). WAIT: index extended,
   middle, ring and pinky curled (ratio under `finger_curled_ratio`). STOP: the four fingers extended, and the hand
   open (`palm_spread_min`: the angle between the index and pinky directions, or the spread of the four fingertips).
3. **Pose of the arm.** WAIT: hand raised near head height (wrist above the shoulder line by `wait_raise_margin`) with the
   forearm roughly vertical (elbow to wrist within `wait_forearm_vertical_tol_deg` of straight up) and the index
   direction (MCP to tip) within `index_up_tol_deg` of up. STOP: arm bent or extended toward the robot, palm facing the
   camera (hand box width/height ratio and landmark order consistent with a palm, not the back of the hand), and the
   hand growing: hand-box scale ratio, last frame over first, at least `push_scale_ratio_min` (the "pushed toward the
   robot" movement; the arm may foreshorten at the same time).

A window passes as `WAIT` or `STOP` only when all three cues agree and the other class's cues clearly fail (margin
`class_margin_min` between the two class scores); a window that matches neither or both is `NONE` with `why`. Three
confusions get explicit checks, because they are the research question: WAIT/STOP (finger up vs palm), WAIT/POINT
(both use the index: WAIT has a bent arm and a short shoulder-to-wrist distance, POINT a long arm; separated by the
arm-length and elbow-angle cues, `point_arm_extension_min_deg` and `wait_arm_extension_max_deg`), and STOP/POINT (an
open palm with an extended arm is not a point). A fist raised straight up (the v3 FORWARD pose) is none of the three.

STOP also keeps the v3 safety behaviour: it overrides the others, has the shortest hold, and a STOP-like open palm seen
by the reader while the robot drives stops it even if the dialog is not asking.

## Output

Per new frame: `command`, `score` (the winning class score, 0 to 1; 0 when `NONE`), `angle_deg` (POINT only),
`why`, the per-class scores, the active arm and the window's valid-frame count. The HUD fills `gesture`,
`gesture_score` and `point_angle_deg` from this and keeps `gesture_raw` for the per-frame reading before the window
decision. The dialog's hold times (a command must be read for a hold before it is accepted) stay in the decision rules;
they are part of the threshold table only where the reader itself needs them.

## Evaluation (with the existing tooling)

Labelled clips come from `gesture_data.py` (truth joined to frames within 0.06 s). Accuracy is always reported with
coverage (rows `NONE`/`insufficient_history` are coverage, not errors), per command, per look, per distance and with and
without zoom; the confusion matrix is POINT/WAIT/STOP/NONE; POINT also gets the angle error. All thresholds are set on
the development split first, written to `configs/v4/` and frozen (hash in `configs/v4/frozen.json`) before any test
look or clip is read.

## Threshold table

Every value is **empty**. "Set from" says how the value will be set on development data only; those procedures are
proposals for Anisha to confirm or replace. No value is chosen from test data or from final-run results.

| # | name | meaning | unit | set from (development data only) | value |
|---|---|---|---|---|---|
| 1 | `window_s` | length of the sliding window the answer is based on (spec: 1 to 2 s) | s | try the allowed range on development clips; choose by the declared rule (shortest window that reaches the coverage target) | |
| 2 | `min_valid_fraction` | share of window frames with usable keypoints needed, else `insufficient_history` | 0 to 1 | distribution of valid-frame share over development clips of each command | |
| 3 | `body_kp_conf_min` | YOLO keypoint confidence below which a body keypoint is missing | 0 to 1 | development keypoint confidence of shoulders, elbows, wrists on raised arms | |
| 4 | `hand_conf_min` | MediaPipe hand presence/landmark confidence below which the hand is missing | 0 to 1 | hand detections on development frames with the hand visible vs hidden | |
| 5 | `hand_crop_margin` | margin around the YOLO wrist for the MediaPipe crop | fraction of torso | hit rate of the hand landmark detector on development frames, at each distance | |
| 6 | `arm_raised_margin` | how far above the hip line the wrist must be for the arm to count as raised | torso lengths | wrist height of development clips (gesturing vs resting arms) | |
| 7 | `raised_max_abs_deg` | arm angle from straight up beyond which the arm is down (v3: 120) | deg | development POINT clips, angle at the hold | |
| 8 | `still_speed_max` | wrist speed under which a frame pair is still | torso lengths per s | wrist speed of development hold phases vs gesturing phases (from `truth.jsonl` phases) | |
| 9 | `motion_path_min` | wrist path length over the window that makes it a moving gesture | torso lengths | path lengths of development windows with and without a gesture | |
| 10 | `hold_min_s` | how long the arm must stay still for a held pose / the POINT angle to be read | s | duration of development hold phases | |
| 11 | `segment_disagreement_max_deg` | largest difference between the shoulder-to-wrist and elbow-to-wrist directions (v3: 45) | deg | development POINT clips: disagreement when the keypoints are right vs wrong | |
| 12 | `arm_length_min` | shoulder-to-wrist length as a multiple of shoulder width below which the arm is too foreshortened for an angle (v3: 0.8) | shoulder widths | development POINT clips at each distance | |
| 13 | `branch_match_max_deg` | largest angle between the read angle and the nearest branch for the robot to take it | deg | angle error of development POINT clips against the junction geometry (branch spacing is fixed by the map) | |
| 14 | `wait_score_min` | MediaPipe `Pointing_Up` score needed for WAIT | 0 to 1 | scores on development WAIT clips vs all other development clips | |
| 15 | `stop_score_min` | MediaPipe `Open_Palm` score needed for STOP | 0 to 1 | same, for STOP | |
| 16 | `finger_extended_ratio` | tip-to-wrist over MCP-to-wrist distance above which a finger is extended | ratio | landmarks of development hands with known finger states | |
| 17 | `finger_curled_ratio` | the same ratio below which a finger is curled | ratio | same | |
| 18 | `palm_spread_min` | spread of the four fingers needed for an open palm | deg | development STOP hands vs closed or pointing hands | |
| 19 | `index_up_tol_deg` | largest angle of the index (MCP to tip) from straight up for WAIT | deg | index angle of development WAIT clips | |
| 20 | `wait_raise_margin` | how far above the shoulder line the wrist must be for WAIT | torso lengths | wrist height of development WAIT clips | |
| 21 | `wait_forearm_vertical_tol_deg` | largest angle of elbow to wrist from straight up for WAIT | deg | development WAIT clips | |
| 22 | `point_arm_extension_min_deg` | smallest elbow angle (straighter arm) for POINT | deg | elbow angle of development POINT clips vs WAIT clips | |
| 23 | `wait_arm_extension_max_deg` | largest elbow angle (more bent arm) for WAIT | deg | same | |
| 24 | `push_scale_ratio_min` | hand-box scale growth (last over first frame of the push) that marks the push of STOP | ratio | development STOP clips vs still open hands | |
| 25 | `class_margin_min` | smallest gap between the best class score and the next for the best class to win | 0 to 1 | development confusion between WAIT, STOP and POINT clips | |
| 26 | `stop_hold_s` | how long a STOP reading must last to stop the robot (v3: 0.2) | s | development STOP clips: false-stop rate on non-STOP clips vs delay | |
| 27 | `dialog_hold_s` | how long a POINT or WAIT reading must last to be accepted by the dialog | s | development clips: time to stable reading | |
| 28 | `max_none_gap_s` | longest `NONE` gap inside a held reading before the hold restarts (v3 dialog) | s | development gaps inside correct readings | |

## Decided

- 2026-10-24 (Phase 2 review): 2 development looks + 1 test look; the `clip` field name and the clip definition (see
  `docs/protocol_v3.md`, Decided); the simulator's default confusion table.
- 2026-10-24: **POINT direction is not the image-plane angle alone.** (1) The out-of-plane component of the pointing arm is
  estimated from foreshortening: the shoulder-to-wrist length in the image against the shoulder width (see "POINT,
  Phase 3 geometry" below). (2) The remaining toward/away ambiguity is resolved with the roadmap: the branch the robot
  arrived from is never a valid answer. (3) MediaPipe hand world landmarks are a cross-check on the finger direction
  (the Phase 2 adapter does not expose them; `gesture_adapter_v4.py` does). The remaining ambiguity is reported as a
  limitation and measured in the development evaluation (`hri_eval_dev_v4.py`).
- 2026-10-24: WAIT timeout 20 s; after it the ask counts as unclear (ask again, then abort).
- 2026-10-24 (Phase 3 review): `stop_requires_push` stays false: an open palm stops the robot without the push motion.
- 2026-10-24: the hand cross-check tie-break stays off until the development evaluation has measured the cross-check.
- 2026-10-24: **two-view POINT disambiguation.** When the two mirror candidates fit two different branches the robot does not
  abort: after the candidates have been stable for `gesture_hold_s` it moves sideways by the re-ask shift (`reask_shift_m`,
  0.4 m, to its right; a larger shift only after asking Anisha), reads again and accepts the candidate that is consistent
  across both views within `view_consistency_deg` (10, initial). At most once per junction; the second view does not use up
  an ask. Still unclear: ask again, then abort as before. Study below.
- 2026-10-24: **approach the commander.** If the commander (linked by bearing to a 360-camera person) is not the person the
  robot approached, it approaches the commander to 2.0 m and asks again, at most once per junction; this question does not use
  up an ask. It needs the commander to be in the pan-tilt view while the robot faces the other person.
- 2026-10-24: **commander timing.** A person counts as commander only if their gesture starts after "Which direction?" is
  first shown at the junction: the arm must go up after that moment. A person whose arm was already up is ignored until it
  has been lowered and raised again. (Re-asks do not move the reference time.) The earlier "whoever gestures first is
  followed" test now applies to gestures that start after the question.
- 2026-10-24 (Phase 4): `reask_shift_m` is 0.8 m for v4 (initial, to be confirmed on development data; v3: 0.4 m, unchanged in the frozen
  v3 config): the two-view study below resolved 20 of 20 ambiguous asks at 10 deg noise with 0.8 m against 18 of 20 with 0.4 m. Threshold rule
  for the development data: highest development accuracy with coverage >= 0.8, ties to the v3 value or the more conservative one.
- 2026-10-24: the dialog hold is 0.5 s (v3: 1.0 s); kept, and listed in AUDIT.md section 14 as a declared v4 difference for RQ1.

## Phase 3: initial values

The threshold table below stays empty for Anisha. The initial values the code runs with, each with its reasoning and the
status "initial, to be set on development data", are in `configs/v4/gesture_reader.json` (window, keypoints, motion, POINT
geometry, hand cues, decision), `configs/v4/commander.json` (facing, motion margin, 360 link), `configs/v4/control.json`
(dialog hold, branch gap, WAIT, zoom) and `configs/v4/eval_dev.json` (matching and distance bins for the evaluation). Values
inherited unchanged from v3 are marked as such. WAIT timeout 20 s and its action are decided, not initial.

## Open questions for Anisha

1. **POINT angle model.** Is the image-plane arm angle (v3 geometry, continuous) acceptable as "the pointed direction",
   given that the 3D vector is not observable? Or should the clips be restricted (avatars never point toward or away
   from the camera), or should the angle be calibrated against the true angle per distance?
2. **Which cues are mandatory.** All three cues for WAIT/STOP (category, finger landmarks, arm pose), or does the
   category score alone count when it is high? (Proposal: all three, cost is lower coverage.)
3. **Selection rules.** The "set from" column proposes what data each threshold is read from; the decision rule that turns
   the data into a value (a percentile, a coverage target, an equal-error point) has to be declared before the sweep and
   written to `configs/v4/` with the date. Which rules?
4. **Trained sequence model.** The spec lists a trained sequence model next to this rule-based reader as open. This design
   covers only the rule-based reader; a model would reuse the same window, inputs, labels and splits.
