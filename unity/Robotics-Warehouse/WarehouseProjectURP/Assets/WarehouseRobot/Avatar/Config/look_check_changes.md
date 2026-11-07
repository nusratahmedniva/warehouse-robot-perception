# Play-mode look check: changes declared before the Phase 2D rerun

Written **2026-11-08** by Nusrat (Unity side, with Claude Code), **committed before the look check is run again**. The
look check stays an engineering check, not an evaluation (docs/look_check_v4.md): Anisha's `look_check_v4.py`, its
config `configs/v4/look_check.json` and its verdict rules are used unchanged, and no reader, commander, perception,
control or gesture value is set or changed because of any look-check result. The only actions a result can cause are
keeping, re-posing or swapping a look.

The last run before these changes: recordings `look_check_play_20261108_031857`, report `look_check_v4_20261108_032808`
(commit e2c282c), all three looks `fails`.

## 1. Venue: the real warehouse lighting at the robot's real asking positions

**Why.** The Phase 2B/2C stage (a grey floor and backdrop under one directional key light from `look_check.json`
render, the person lit from behind relative to the camera) does not represent the conditions the robot works in, so a
verdict on it says little about the study.

**What changes.**

- The check runs in `Assets/Scenes/WarehouseRobot_v4.unity` itself (its directional light, its 16 shadowed spot lights,
  its baked lighting data, skybox ambient and the warehouse around the person). The scene file is not changed: the
  driver is added only in Play mode, and in Play mode only the study's own runtime parts are switched off (trial
  runner, bridge client, the v3 placeholder workers, the robot body), so nothing connects to Python and no session
  folder is written.
- The person stands at a Task 2 junction's worker stand, as in the study (`TrialRunnerV4`, roadmap rule): J1
  (8.75, 2.50) and J2 (-8.75, 2.50).
- The camera stands where the robot asks. In the v4 development session `bridge_guide_20261108_033956` (3 trials) the
  robot asked 8 times; measured at the worker from the stand's facing direction toward the junction side, the robot
  was at 47, 25, 44, 21, 43, 20 deg (J1) and 39, 18 deg (J2), 1.65 to 1.89 m from the worker. The camera pose of every
  take is drawn from a seeded stream:
  - bearing: uniform in **[15, 50] deg** toward the junction side (the band holding all 8 asks);
  - distance: the nominal **2.0 m** and **4.0 m** of docs/look_check_v4.md, each drawn uniformly within
    **+-0.15 m** (`approach_distance_m` 2.0 and `approach_tolerance_m` 0.15 of `robot_vision/configs/hri_control.json`).
    The recordings keep the nominal distance in their names (`__2.0__`, `__4.0__`) so the tool groups them as before;
    the drawn distance goes into `recordings.jsonl` and the frame header. Note: the 8 measured asks were 1.65 to 1.89 m
    from the worker's root, a little nearer than this band;
  - height and orientation: the pan-tilt camera of `robot_unity_v4.json` (1.20 m, level, 730 x 530, 60 deg), aimed
    horizontally at the stand (the person near the image centre, as docs/look_check_v4.md asks);
  - a pose is used only if both cameras keep 0.35 m from every collider and see the person's head and hips without
    an obstacle in between; otherwise it is drawn again from the same stream (the number of draws is recorded).
- One performance is recorded by a 2 m camera and a 4 m camera on the same bearing. The person turns to face the 2 m
  camera (the robot that asks) as before.
- Every look is recorded at both junctions: three rounds, J1 and J2 at the same time with different looks
  (round 1 J1 sunbox_m1 / J2 sunbox_f1, round 2 sunbox_f1 / sunbox_f2, round 3 sunbox_f2 / sunbox_m1), half of each
  group's takes at each junction.

## 2. sunbox_f1: a plain-sleeved top

The blouse (`Blouse`, variation 1, white) has a gathered cuff over the wrist. It becomes the free pack's long-sleeved
**`Shirt`, variation 1 (white)**: same colour, plain sleeves. Appearance only (`worker_v4.json` and `look_check.json`
kept equal); nothing else of the look changes.

## 3. More independent views per group

Before: per group (look, command, distance, arm) 3 sequences of 11 frames and 5 single frames, from 8 performances seen
from one camera pose; the pose is held still, so the 11 frames of a sequence are near copies and 33 of the 38 frames
came from 3 views.

Now, per group:

- **2 sequences** (docs/look_check_v4.md minimum; 11 frames at 10 Hz, held still, unchanged format) and
  **16 single frames**: 38 frames as before, but from **18 independent performances** and **18 camera poses**;
- every performance has its own variation stream (worker seed 1, run = take number, so speed, size, start delay and
  hold differ) and its own drawn camera pose;
- variants: sequence 1 the command's first variant, sequence 2 its second, singles in turn through all three;
  POINT directions: sequence 1 sideways in the image plane, sequence 2 at 45 deg toward the front (the doc's two
  takes), singles in turn through 0, 10, 20, 30, 45, 60 deg;
- NONE (negative control): 2 sequences and 16 singles per look and distance, each at its own camera pose.

Sequences at J1 / J2: one each; singles: even take numbers at J1, odd at J2.

## 4. Left-arm WAIT: a code defect, found and fixed before the rerun

**Symptom** (report `look_check_v4_20261108_032808`): WAIT with the person's left arm gave own cue 0.00 on every look;
the per-frame cues show the finger-up geometry passing and MediaPipe's category failing (`None` instead of
`Pointing_Up`). Crops of the frames show the left thumb sticking straight out sideways (an "L") while the right thumb
is tucked.

**Cause.** The hand shapes are applied from the rig's rest pose, and the Sunbox base mesh's two hands are not mirror
images at rest: every finger joint matches its mirror image to 0.0 mm except the left thumb's distal joint, 17 mm off
(left thumb straight, right thumb bent at the intermediate joint), the same on all three looks. The shaping code
itself is mirror-exact (measured on the real rig).

**Fix.** `HandShaper.MirrorRest` (called once by `WorkerV4` when the look is spawned): the left hand's rest finger
bones are set to the mirror image of the right hand's (rotations included, using the rig's own left/right axis
convention measured on the four fingers that already match), so both hands start every shape from mirror-image
fingers. The right hand's rest pose is not touched.

A second, independent defect was found by the new left/right test: the STOP spread chose its direction from the
finger base's offset to the middle finger including the part along the fingers, so on one hand the ring or little
finger could fan toward the middle finger instead of away. The spread now uses the sideways offset only. This can
change STOP on either hand; it makes STOP what `worker_v4.json` already declares (fingers fanned away from the middle
finger).

Tests: `HandShape_LeftIsTheMirrorOfTheRight_EvenWhenTheRigsRestPoseIsNot` (a test rig with the Sunbox-like bent
thumb: without the fix the hands differ, with it they agree within 1 mm for POINT, WAIT and STOP) and
`EveryLook_LeftAndRightHandShapes_AreMirrorImages` (every installed look: joints and fingertips within 1 mm, tip
ratios within 0.02). No hand-shape value in `worker_v4.json` changes.

## 5. What does not change

`look_check_v4.py` and its config and rules; the recording format, names, headers and the 10 Hz, 11-frame held
sequences; both arms, forced; the 60 deg view; the three looks (except f1's top); every value of `worker_v4.json`
(poses, hand shapes, variation, behaviour) except f1's top; the seed (1).

## Results

Added after the rerun, below this line, without changing the declaration above.

### Fix after the declaration, before the full rerun (2026-11-08)

A smoke run of the new venue (`-lookCheckQuick`, `look_check_play_debug_20261108_050313`, not evaluated) showed the
person as a flat cyan (0, 255, 255) silhouette in the first takes, at both distances: the Editor's placeholder for a
shader variant that is still compiling asynchronously (the scene's spot lights and shadows need variants the stage
never used; the stage run `look_check_play_20261108_031857` has 0 such frames out of 1530). The menu now turns the
Editor's asynchronous shader compilation off while the check runs and restores it afterwards. A second smoke run
(`look_check_play_debug_20261108_050703`) had 0 cyan frames out of 308. A rendering defect of the check itself;
nothing about the looks or gestures was changed.

### Rerun (2026-11-08, commit 21ecad4)

Recordings `look_check_play_20261108_051252` (756 recordings, 1596 frames = 38 per group, 0 frames outside the hold,
0 cyan frames; every pose clear at the first draw; bearings 15.2 to 50.0 deg; camera distances 1.85 to 2.15 m and
3.85 to 4.15 m; hand and shoulder still to 0.0 mm over every sequence). Report `look_check_v4_20261108_053315`
(`look_check_v4.py` and its config unchanged).

| look | before (`look_check_v4_20261108_032808`) | after |
|---|---|---|
| sunbox_m1 | fails | **weak** |
| sunbox_f1 | fails | fails |
| sunbox_f2 | fails | fails |

2 m groups, own cue (before -> after) and grade:

| look | WAIT left | WAIT right | STOP left | STOP right | POINT left | POINT right |
|---|---|---|---|---|---|---|
| sunbox_m1 | 0.00 -> 0.89 usable | 1.00 -> 0.92 usable | 0.71 -> 0.95 usable | 0.71 -> 0.66 weak | 0.97 -> 0.97 weak | 1.00 -> 0.95 weak |
| sunbox_f1 | 0.00 -> 0.11 fails | 0.00 -> 0.34 fails | 0.37 -> 0.05 fails | 0.00 -> 0.55 weak | 0.68 -> 0.97 weak | 1.00 -> 1.00 weak |
| sunbox_f2 | 0.00 -> 0.76 usable | 0.00 -> 0.13 fails | 0.03 -> 0.05 fails | 0.68 -> 0.95 usable | 0.08 -> 0.95 weak | 0.39 -> 1.00 weak |

What the report shows (observations only; nothing was changed on them):

- The left-arm WAIT bug is gone where the hand is found: m1 left 0.00 -> 0.89, f2 left 0.00 -> 0.76.
- Every POINT group is `weak`, not failing: the reader reads POINT (own cue 0.95 to 1.00), but the hand is rarely
  linked (not required for POINT) and the 95th-percentile arm ratio is 1.87 to 2.00 against the accepted 0.98 to 1.75
  (the template's arm is longer in shoulder widths than the reader's assumed 1.4).
- The remaining failures are MediaPipe's category, not the geometry: f1 and f2 STOP left show an open palm in 0.66 and
  0.97 of the frames but `Open_Palm` in 0.05; f2 WAIT right shows the finger up in 0.66 but `Pointing_Up` in 0.13;
  f1 WAIT finds and links the hand in only 0.39 to 0.45 of the frames.
- `weak` and `fails` decisions are Anisha's and Nusrat's (docs/look_check_v4.md: keep with the reasons, re-pose, or
  swap); this rerun proposes none.
