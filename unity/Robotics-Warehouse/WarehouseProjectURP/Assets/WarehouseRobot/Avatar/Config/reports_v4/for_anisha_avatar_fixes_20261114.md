# For Anisha: avatar pipeline fixes and what they change for the Python side (2026-11-14)

From Nusrat's Unity branch `nusrat/v4-avatar-fixes` (design notes: `Avatar/Config/experiments_ab.md` sections 10 and 11; report:
`reports_v4/avatar_pipeline_fixes_20261114.md`). Nothing under `robot_vision/`, `docs/` or `external/` was changed. No perception
model was run on any avatar-experiment look.

## 1. PROCEED changed on every look: please confirm your false-STOP fix on the new pose in step 5

The worker template's PROCEED targets now come from each rig's own upper-arm and forearm lengths, not Sunbox's 0.53 / 0.47 split.
The elbow hint now keeps the arm in the intended bend plane (section 10 item 1 and addendum 3).

- **Rendered forearm direction against its goal:** 11.1 to 12.9 deg off before, 0.0 deg after, on every look
  (`gesture_geometry_baseline_20261114_182535` against `gesture_geometry_final_20261114_193832`).
- **How far the PROCEED hand target moved:** up to 22 mm on the Sunbox looks, 15 to 16 mm on the anime looks, 3 mm on mixamo_worker.
- **Unchanged:** the swing itself (upper arm forward angle, forearm low and high angles, rate) and the hand shape (flat, fingers together).

Your false-STOP analysis (PR #35, `analyse_false_stop_v4.py`) and any fix built on it were measured on the OLD PROCEED pose.
**Please confirm the fix on the new PROCEED pose in step 5** (development recordings, development looks only). The avatar experiment
measures perception once, after the finals, and nothing may be tuned on it.

## 2. The anime "forearm folds back" was YOLO, not the bones

The bones never folded: anime_f_01's POINT elbow is at least 150.9 deg before and after the change, with an intended 151.9 to 157.0 deg
(section 10 addendum 2). The fold seen in the step 2b look check was YOLO placing the wrist keypoint on the wide sleeve. It is a property of how
the model reads that look, not a pose error, so nothing on the Unity side was changed for it.

## 3. Other changes that alter what the cameras see (section 11)

- **STOP reach cap:** a STOP target is never farther from the shoulder than 0.97 of the rig's own arm length, size and push included. Before,
  a pushed take could ask for more than the arm can reach. Only pushed STOP takes move, toward the shoulder in the same direction.
- **Anime materials:** the importer now uses alpha clipping (cutoff 0.5) for every material whose base texture carries a cut-out mask. This
  removes anime_f_02's black patches on the dress, and also changes the hair, eyelashes and body masking of anime_f_01, 02 and 03.
- **cartoon_boxo_01** is now spawned by the worker template (its hands have no little finger; the shapes use the four fingers present). It
  is in the Play-mode look check of the avatar experiment, PROCEED included, as `looks_excluded` is now empty.
- **Geometry check:** the no-fold rule now covers POINT only. STOP, PROCEED and WAIT are checked against their own designed elbow angle.

None of these touches a Python file, config or threshold. The look and clip names are unchanged.

## 4. Rerun (geometry only, no perception)

- **Every look** of the avatar experiment (15, Boxo included) is within the declared tolerance for every command
  (`reports_v4/gesture_geometry_decisions_20261114_210047_table.md`).
- **The five-finger hands are value-for-value identical** to before (`reports_v4/hand_shapes_20261114_203658_compare.md`).
- **Boxo's Play recordings follow your format:** PROCEED sequences have 21 frames spanning 2.005 to 2.018 s
  (`look_check_play_ab_debug_20261114_210603`, a format check only).
