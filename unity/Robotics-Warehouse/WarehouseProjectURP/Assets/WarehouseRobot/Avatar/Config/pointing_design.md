# POINT at the junctions: option A (angled stance and torso turn), declared before it is tested

Written **2026-11-09** by Nusrat (Unity side, with Claude Code), **committed before option A is implemented or
tested**. It changes only how the commander's body shows a POINT (Unity, `worker_v4.json` and `WorkerV4`). No Python
file, threshold or rule changes; nothing in the v3 scene reads any of it.

## 1. The problem (evidence: the development sessions of 2026-11-08)

The commander stands at the roadmap's worker stand of each junction (2.5 m ahead of and 2.5 m right of the junction,
seen from the arriving robot) and faces the robot. The robot asks from about 1.6 to 1.9 m away, from the junction side.
Two of the three J1 branches and both J2 branches then lie **behind** the worker's body. `WorkerV4` clamps every POINT at
`limits.point_max_body_azimuth_deg` = 120 deg from the body front, so the arm shows a direction up to 42 deg away from
the branch.

J1 outcomes in the six development sessions of 2026-11-08 (`bridge_guide_20261108_033525`, `_033956`, `_041803`,
`_042700`, `_125656`, `_235531`; 17 runs; every failure "gesture unclear after 2 asks at J1"): FORWARD (goal E1)
accepted 0 of 5, RIGHT (goal E2) 1 of 6, LEFT (goals E3, E4) 4 of 6; J2 RIGHT 4 of 4 (J2 FORWARD never reached). In `_235531` the reader resolved RIGHT at 120 deg world (30 to 31 deg from the RIGHT branch,
over the controller's 30 deg limit) and FORWARD at -50 deg (dropped: 40 deg from LEFT, 50 deg from FORWARD).

## 2. Option A (what changes)

For a POINT only (WAIT and STOP are unchanged), with `alpha` = the branch direction's signed azimuth from the worker's
body front at the request (the worker faces the robot then; + = the worker's right):

1. **Angled stance.** `need = max(0, |alpha| - arm_target_body_azimuth_deg)`. The worker turns its whole body (root yaw,
   in place, at the behaviour's turn speed, during the start delay after "Which direction?") by
   `stand = min(need, stand_angle_max_deg)` toward the branch's side, and keeps that stance until the gesture has
   returned (then it faces the robot again, as before).
2. **Torso turn.** During the gesture the chest turns further toward the branch by
   `torso = min(need - stand, torso_turn_max_deg)` (spread over the spine bones, faded in and out with the arm's IK
   weight). The legs stay; **the head stays on the robot** (its world orientation from the look-at is kept).
3. **The arm** points at `alpha - stand - torso` from the chest; the existing 120 deg clamp still applies after the
   turn. The shown world direction (truth.jsonl `point_angle_deg`) is the clamped one, exactly as before.
4. With `stand_angle_max_deg` = `torso_turn_max_deg` = 0 the behaviour is the Phase 3A behaviour.

Values (`worker_v4.json` -> `pointing`, chosen now, from geometry only, never tuned on a result):

| key | value | why |
|---|---|---|
| `arm_target_body_azimuth_deg` | 110 | turn only as far as needed to bring the arm within 110 deg of the chest (10 deg inside the 120 deg clamp), so the shoulders stay as square to the robot as possible (the commander's facing test needs them) |
| `stand_angle_max_deg` | 15 | a natural half-step of the feet; also the behaviour's `turn_start_deg` |
| `torso_turn_max_deg` | 30 | a comfortable chest twist on fixed hips; chest at most 45 deg from the robot in total |

## 3. Required pointing angle relative to the worker's body, before and after

From all 39 ask positions of the 2026-11-08 sessions (robot position at each "Which direction?", worker at its stand;
J1: worker-to-robot yaw -162.1 to -133.1 deg, J2: 108.0 to 132.4 deg). Branch yaw = junction to next node (Unity yaw).
Angles: + = worker's right; "chest" = stand + torso.

| junction | branch | before: arm from body front | before: shown error (120 clamp) | after: stand | after: torso | after: chest | after: arm from chest | after: shown error |
|---|---|---|---|---|---|---|---|---|
| J1 | FORWARD (E1) | 133.1 to 162.1 | up to 42.1 | 15 | 8.1 to 30 | 23.1 to 45 | 110.0 to 117.1 | 0 |
| J1 | RIGHT (E2) | -136.9 to -107.9 | up to 16.9 | 0 to -15 | 0 to -11.9 | 0 to -26.9 | -110.0 to -107.9 | 0 |
| J1 | LEFT (J2) | 43.1 to 72.1 | 0 | 0 | 0 | 0 | 43.1 to 72.1 | 0 |
| J2 | FORWARD (E3) | 137.6 to 162.0 | up to 42.0 | 15 | 12.6 to 30 | 27.6 to 45 | 110.0 to 117.0 | 0 |
| J2 | RIGHT (E4) | -132.4 to -108.0 | up to 12.4 | 0 to -15 | 0 to -7.4 | 0 to -22.4 | -110.0 to -108.0 | 0 |

**Risk, stated before the test.** The chest turned 20 to 45 deg from the robot narrows the shoulders in the robot's
image by cos 20 to cos 45 (0.94 to 0.71). Two Python rules use that width: the commander's facing test
(`facing_shoulder_ratio_min` 0.5; on 2026-11-08 already 308 of about 1,200 commander rows failed it with the body square,
at ratios of 0.39 to 0.48), and the reader's arm-length model (`arm_length_in_shoulder_widths` x the apparent shoulder width,
so a narrower chest makes the arm look less foreshortened). Option A can therefore remove the clamp error and still fail.
That is what the decision rule below tests.

## 4. Decision rule (declared now, before the check)

**Option A is adopted if, in a development check of every branch at J1 and J2 with both development looks, the reader
resolves the correct branch in at least 50 % of held frames for EVERY branch, and the facing rate is at least 0.8.
If not: STOP and report; no fallback is implemented.**

How it is measured (fixed now):

- **Check session:** `WarehouseRobot_v4.unity`, `TrialRunnerV4`, development mode, development seed 1, **20 trials**
  (`launch_prep.py --trials 20`, development only), development looks `sunbox_f1` / `sunbox_m1` (alternating per run) and
  development POINT clips only, Python `bridge.server --mode guide --task Task2 --perception vision --config configs/v4/bridge.json`
  unchanged (zoom on, threads, every threshold as committed). 20 trials because the seed-1 goal order reaches J2 FORWARD
  (goal E3) with `sunbox_m1` only in runs 18 and 20.
- **Frames:** the rows of the bridge's `v4_log.jsonl` (one per pan-tilt frame read in the READ state), joined to the
  commander's row of `truth.jsonl` nearest in `time_s` within 0.06 s (`configs/v4/gesture_data.json` `truth_join_max_s`).
  **Held frame** = the commander's truth phase is `holding` and `true_command` is POINT.
- **Correct branch:** the row's `resolution.command` equals the branch from that junction toward the run's goal
  (roadmap.json). A held frame without a resolution counts as not resolved.
- **Facing rate:** share of held frames in which the person the controller logged (the commander rule's `people`) is
  `facing`; a held frame with no person counts as not facing.
- **Every branch:** the five (junction, branch) pairs of the table, each pooled over both looks; a pair with no held
  frame of one of the two looks counts as **not met** (no evidence is not a pass). Per-look figures are reported too.
- **Facing rate:** over all held frames of the session (also reported per branch).

The result, whatever it is, is added below this line with the session folders, before anything else is done.

## 5. Result

(to be filled after the check)
