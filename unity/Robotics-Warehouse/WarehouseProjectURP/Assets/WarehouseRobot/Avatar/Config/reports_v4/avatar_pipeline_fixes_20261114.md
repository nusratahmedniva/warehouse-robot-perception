# Avatar pipeline fixes before the freeze (2026-11-14)

Branch `nusrat/v4-finals-ab`, commits 67efb67 (declaration) to aa3db71 (B9); design and every rule in
`Avatar/Config/experiments_ab.md` section 10 with addenda 1 to 3, each written before the change it declares. Unity side only;
nothing frozen, no final run. **No perception was run on any avatar-experiment look**: everything below is bone geometry, mesh
skinning or file format. Paths are relative to `robot_vision/outputs/`.

## Runs

| what | folder | commit |
|---|---|---|
| import (Boxo v2, anime_f_02, anime_f_03) | `import_characters_20261114_180918` | 3e6054b tree |
| finger skin probe | `probe_fingers_20261114_181109` | 3e6054b tree |
| arm-skin probe | `probe_arm_skin_20261114_184211` | 7c44fb2 tree |
| controlled-variant probe | `probe_variants_20261114_184319` | 7c44fb2 tree |
| geometry, baseline (targets unchanged) | `gesture_geometry_baseline_20261114_182535` | 3e6054b |
| geometry, final (Play, worker template) | `gesture_geometry_final_20261114_193832` | aa3db71 (clean) |
| pose geometry (Edit mode, LookPoser) | `pose_geometry_20261114_194216` | aa3db71 (clean) |
| format check, Edit PROCEED (Boxo) | `look_check_ab_20261114_192051` | full tree before the step split |
| format check, Play PROCEED (anime_f_02, quick) | `look_check_play_ab_debug_20261114_192553` | full tree before the step split |

**Screenshots** (neutral camera: 3.0 m in front, 20 deg to the right, 1.3 m high, 35 deg field of view, 1280 x 960; not the robot's cameras):
- anime looks, worker template in Play mode: `gesture_geometry_final_20261114_193832/screens/` (24 PNG: anime_f_01, anime_f_02_outfit_short,
  anime_f_03_bangs_parted x POINT, PROCEED, WAIT, STOP x left, right; PROCEED at the top of the swing).
- Boxo, Edit-mode poses: `pose_geometry_20261114_194216/screens/` (8 PNG: POINT, PROCEED, WAIT, STOP x left, right).

## 1. Arm scaling: per-look geometry (worker template, Play mode)

Tolerance (declared): elbow angle 10 deg, shoulder-to-wrist direction 5 deg, forearm direction 10 deg (WAIT: vertical; PROCEED: toward the
intended elbow's goal); no fold: POINT and STOP elbow at least 120 deg. Every clip of every command, both arms, POINT at side azimuth 0 and 45 deg;
5 frames per hold, PROCEED every frame of 2.0 s of swing. Worst values per look.

| look | kind | upper / forearm (m) | arm / shoulder width | POINT elbow min (err max) | PROCEED forearm err, baseline -> final | WAIT forearm err | STOP elbow err | STOP frames below 120 deg | PROCEED target shift (mm) | rendering |
|---|---|---|---|---|---|---|---|---|---|---|
| mixamo_worker | realistic_human | 0.257 / 0.223 | 1.10 | 150.8 (2.5) | 11.1 -> 0.0 | 9.4 | 0.5 | 10 of 30 | 3 | all within tolerance |
| sunbox_m1 | stylised_human | 0.285 / 0.272 | 1.59 | 151.2 (1.8) | 12.6 -> 0.0 | 7.4 | 0.7 | 5 of 30 | 22 | all within tolerance |
| sunbox_f1 | stylised_human | 0.285 / 0.272 | 1.59 | 151.2 (1.8) | 12.8 -> 0.0 | 9.1 | 6.0 | 5 of 30 | 22 | all within tolerance |
| sunbox_f2 | stylised_human | 0.285 / 0.272 | 1.59 | 151.2 (1.8) | 12.7 -> 0.0 | 6.1 | 9.5 | 5 of 30 | 22 | all within tolerance |
| sunbox_m2 | stylised_human | 0.285 / 0.272 | 1.59 | 151.2 (1.9) | 12.3 -> 0.0 | 9.5 | 0.0 | 5 of 30 | 22 | all within tolerance |
| sunbox_m_shirt_white | stylised_human | 0.285 / 0.272 | 1.59 | 151.2 (1.8) | 12.6 -> 0.0 | 8.8 | 5.9 | 5 of 30 | 22 | all within tolerance |
| sunbox_m_tshirt_black | stylised_human | 0.285 / 0.272 | 1.59 | 151.2 (1.9) | 12.8 -> 0.0 | 6.7 | 4.8 | 10 of 30 | 22 | all within tolerance |
| sunbox_m_shirt_plaid | stylised_human | 0.285 / 0.272 | 1.59 | 151.2 (1.8) | 12.6 -> 0.0 | 9.1 | 0.7 | 0 of 30 | 22 | all within tolerance |
| sunbox_f_shirt_white | stylised_human | 0.285 / 0.272 | 1.59 | 151.2 (1.8) | 12.7 -> 0.0 | 9.4 | 0.7 | 5 of 30 | 22 | all within tolerance |
| sunbox_f_dress_red | stylised_human | 0.285 / 0.272 | 1.59 | 151.2 (1.9) | 12.5 -> 0.0 | 9.4 | 0.7 | 0 of 30 | 22 | all within tolerance |
| sunbox_f_shirt_plaid | stylised_human | 0.285 / 0.272 | 1.59 | 151.2 (1.8) | 12.9 -> 0.0 | 9.1 | 1.0 | 5 of 30 | 22 | all within tolerance |
| anime_f_01 | anime | 0.228 / 0.215 | 2.24 | 150.9 (2.4) | 12.3 -> 0.0 | 9.0 | 0.9 | 0 of 30 | 16 | all within tolerance |
| anime_f_02_outfit_short | anime | 0.228 / 0.215 | 2.24 | 150.9 (2.4) | not in baseline -> 0.0 | 9.1 | 11.2 | 10 of 30 | 15 | **STOP outside** (one take) |
| anime_f_03_bangs_parted | anime | 0.228 / 0.215 | 2.24 | 150.9 (2.4) | not in baseline -> 0.0 | 8.4 | 0.9 | 0 of 30 | 16 | all within tolerance |
| cartoon_boxo_01 | cartoon_non_human | not spawned by the worker template (no little finger); Edit-mode poses below | | | | | | | | |

Full tables: `reports_v4/gesture_geometry_baseline_20261114_182535_table.md`, `reports_v4/gesture_geometry_final_20261114_193832_table.md`.

How to read it:
- **The anime forearm does not fold, and did not fold before the change.** anime_f_01's POINT elbow is never below 150.9 deg (intended 151.9 to
  157.0) in the baseline or the final run; the hand sits on its IK target. The "fold" of section 5 came from YOLO's wrist on the rendered frames
  (the wide sleeve), which this work does not measure. Its proportions are Sunbox-like (upper-arm share 0.514 vs 0.512); its shoulders are narrow
  (arm 2.24 shoulder widths vs 1.59).
- **What the arm scaling fixed: PROCEED.** With Sunbox's 0.53/0.47 split and the old hint, the forearm missed its goal by 11.1 to 12.9 deg on
  every look (Sunbox included). With the rig's own upper arm and forearm (addendum 3: the elbow hint now keeps the intended elbow in the bend
  plane) it is 0.0 deg on every look. PROCEED's hand target moved by at most 22 mm (Sunbox), 16 mm (anime), 3 mm (mixamo_worker).
  POINT, WAIT and STOP targets are unchanged (they depend on the arm length only, as before).
- **Sunbox: no regression.** Every Sunbox look is within tolerance on every command after the change, as before; only PROCEED changed, and it
  went from outside to inside.
- **STOP, found, not changed (decision for Nusrat):** the "below 120 deg" frames are the frozen STOP design itself: `worker_v4.json`
  `limits.stop_reach` lower bound 0.85 arm lengths gives a 116 deg elbow, and the rendered pose equals the intended one there (elbow error <= 0.7
  deg). The declared no-fold threshold (120) is stricter than that design; neither was changed after seeing it (addendum 2).
- **anime_f_02 STOP, found, not changed:** one take (stop_ik_03, left arm, size 1.07) pushes the target beyond the arm's reach (intended 180 deg,
  straight); Mecanim stops at 168.8 deg, the direction exact (0.0 deg). A slight bend short of an out-of-reach target, not a fold; outside the
  10 deg elbow tolerance by 1.2 deg on those 5 frames. sunbox_f2's same take comes to 9.5 deg.

## 2. Boxo v2 (`cartoon_boxo_01.fbx` 00fbf466, generator `unity/tools/avatars/make_cartoon_boxo.py` v2)

- Import: unit scale x100 and avatar rebuilt (section 2 rules), height 1.138 m (head-to-foot bones), 46 Humanoid bones, **finger bones 24 of 30**.
- **Bones of each hand** (both hands mirror each other; left shown):

| chain under `mixamorig:LeftHand` | bones | Humanoid mapping | own region moved | most moved other finger | verdict |
|---|---|---|---|---|---|
| Thumb | LeftHandThumb1 > 2 > 3 > 4 | Left Thumb Proximal, Intermediate, Distal | 0.96 (68/71) | 0.03 (Index1) | separate |
| Index | LeftHandIndex1 > 2 > 3 > 4 | Left Index Proximal, Intermediate, Distal | 1.00 (69/69) | 0.04 (Thumb1) | separate |
| Middle | LeftHandMiddle1 > 2 > 3 > 4 | Left Middle Proximal, Intermediate, Distal | 1.00 (66/66) | 0.00 | separate |
| Ring | LeftHandRing1 > 2 > 3 > 4 | Left Ring Proximal, Intermediate, Distal | 1.00 (72/72) | 0.00 | separate |

  Right hand: the same, own 0.93 to 1.00, others at most 0.04. **The fingers are no longer one chain; every finger moves alone.** There is no
  little finger (Mixamo mapped the three fingers to index, middle and ring), so `HandShaper` (index to little) still refuses it: the worker
  template cannot shape its hand, Boxo stays out of the Play look check (exclusion reason updated) and gets its PROCEED as a posed swing in Edit mode.
  A three-finger hand shape in the template would be a template change (decision for Nusrat).
- Probe controls: mixamo_worker 5 separate chains per hand (own 0.87 to 0.96, others at most 0.07). anime_f_01 reads "merged" by the declared
  rule (own 0.61 to 0.89, others at most 0.15): no finger moves its neighbour, but this small hand's 4 cm region reaches palm vertices.
- Arm skin: follows (112/112 arm vertices per side). Colours: 11 URP Lit materials (bodymat, vestmat, stripemat, eye_whitemat, pupilmat,
  mouthmat, helmetmat, limbmat, glovemat, trousersmat, bootmat); glovemat and helmetmat recoloured by the rule (colourless); eye_whitemat and
  stripemat colourless and matched by no rule (white). **Error shader: none; 0 magenta pixels** (neutral render `probe_fingers_20261114_181109/cartoon_boxo_01_neutral.png`).
- Edit-mode poses (pose geometry): every POINT, WAIT, STOP and PROCEED take within tolerance (elbow, upper-arm and forearm error <= 0.1 deg).
  The hand shapes (fist, index up, open palm) are not formed: `LookPoser` needs the index and little fingers to find the palm.

## 3. Anime variants

| variant | sha256 | arm skin | Humanoid bones vs anime_f_01 | meshes vs anime_f_01 | materials only in the variant |
|---|---|---|---|---|---|
| anime_f_02_outfit_short | d94b472a | follows (457/457 per side) | every one of 55 bones offset by the same 1.55 mm (whole skeleton shifted; "different body" by the 1 mm rule) | Face, Hair identical; Body (VRoid merges clothing into it) 9146 -> 9391 vertices | Tops, Onepiece, Shoes (outfit and shoes) |
| anime_f_03_bangs_parted | a3cf3439 | follows (183/183 per side) | all body bones within 1 mm; only "Jaw" 21.7 mm, which the auto-mapping put on a hair bone (J_Sec_Hair2_05) | Body, Face identical; Hair 14822 -> 17613 vertices | none |

Both imported by the unchanged importer (25 textures extracted each and the materials re-created to link them, as the section 5 rule;
18 URP Lit materials each; no scale fix); listed in `looks_ab.json` under kind anime (`variant_of`
anime_f_01) and in the avatar experiment (15 looks). Licences from `SOURCES.txt` (Nusrat's own VRoid characters); **SOURCES.txt names the third
file `anime_f_03_hairback.fbx` ("hair tied back")**, while the file is `anime_f_03_bangs_parted.fbx`: please correct SOURCES.txt.
Visual note (screenshots): anime_f_02's dress shows black triangular patches (likely cut-out materials rendered opaque); not changed.

## 4. PROCEED in the look-check recordings

- Play mode (`look_check_play_ab.json` `proceed`): every spawnable look, same takes as the other commands, 21-frame sequences during the swing.
  The first quick format check found sequences of 1.990 s (a late frame 0); frames are now timed from frame 0's real time: 2.006 to 2.015 s
  (Anisha's tool refuses less than 2.0 s, EPS 1e-9). Headers: `arm`, real `time_s`.
- Edit mode (`look_check.json` PROCEED): every look incl. Boxo, a posed swing (21 frames rendered one by one, no `time_s`: the tool's 10 Hz
  fallback = 2.0 s), singles at fixed forearm angles. Format check on Boxo: 8 sequences of 21 frames, 20 singles.

## 5. Run-once guard of the avatar experiment

`avatar_experiment.json` + `AvatarExperimentGuard`: `-avatarExperiment` on `LookCheckMenu.BatchRunExperiment` (edit) or
`LookCheckPlayMenu.CommandLineRunAB` (play) needs the freeze (every B9 file recorded and unchanged), all nine finals done, no look subset and
no earlier marker of that part; it writes `AVATAR_EXPERIMENT_STARTED.json` first and `AVATAR_EXPERIMENT_DONE.json` last. Checked live today:
both parts refused (not frozen, finals not done), nothing written.

## Decisions for Nusrat ([N])

1. STOP's design (reach 0.85 L -> 116 deg) vs the declared 120 deg no-fold threshold: keep both as reported, or change one (declared, before the freeze).
2. Boxo: a three-finger hand shape in the worker template (template change) or Boxo stays Edit-mode only.
3. SOURCES.txt: the name and description of the third anime file.
