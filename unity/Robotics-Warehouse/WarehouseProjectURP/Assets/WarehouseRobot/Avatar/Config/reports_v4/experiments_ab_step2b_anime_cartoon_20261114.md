# Experiments A/B, step 2b: anime_f_01 re-export and cartoon_boxo_01 (look check of two looks)

Written 2026-11-14 by Claude for Nusrat and Anisha. Unity commits d8aa6df and 66f41f6, now on branch `nusrat/v4-experiments-ab-anime` (see "Branch" below).
Everything was declared before it ran in `Avatar/Config/experiments_ab.md` section 5 (and its two addenda). This is an engineering check, not an
evaluation: no reader, perception or control value was changed because of it. It updates the anime_f_01 and cartoon_boxo_01 rows of
`experiments_ab_step2_avatars_20261114.md`; every other row there stands.

## Licences

`unity/downloads/characters_v4/SOURCES.txt` exists now but is **empty (0 bytes)**. The licences of anime_f_01 and cartoon_boxo_01 therefore
**could not be checked and stay not verified**. No character file, texture or material is committed (all git-ignored); `looks_ab.json` says
"not verified: SOURCES.txt is empty". To close it: write in SOURCES.txt, per character, where it comes from (e.g. VRoid Studio version and the
model's own terms; the tool that generated cartoon_boxo_01) and the licence that allows use in the study.

## Runs

| what | folder (robot_vision/outputs/) |
|---|---|
| arm-skin probe, controls before the move (old anime_f_01 import in place) | `probe_arm_skin_20261114_133039` |
| re-import 1 (re-export; materials without textures, superseded) | `import_characters_20261114_133118`, probe `probe_arm_skin_20261114_133152` |
| **re-import 2 (texture link fixed, used)** | `import_characters_20261114_134655`, rigs `probe_rigs_20261114_*` (last), **arm skin `probe_arm_skin_20261114_134730`** |
| **Edit-mode look check, both looks** | Unity `look_check_ab_20261114_134755`, tool `look_check_v4_20261114_135659` |
| Play-mode look check, anime_f_01, run 1 (56 of 76 NONE frames cyan, not used) | Unity `look_check_play_ab_20261114_134932`, tool `look_check_v4_20261114_135803` |
| **Play-mode look check, anime_f_01, run 2 (0 cyan frames, used)** | Unity `look_check_play_ab_20261114_140152`, tool `look_check_v4_20261114_140845` |

Superseded imports were moved, not deleted: `unity/downloads/superseded/anime_f_01_79f49bc1/` (the old export) and
`unity/downloads/superseded/anime_f_01_fe304543_unlinked/` (re-import 1). Free memory during Play run 2: minimum 2,285 MB, median 2,691 MB;
Unity working set up to 1,783 MB (`look_check_play_ab_memory_20261114_140114.csv`).

## Does the arm mesh follow the bones? Yes

Arm-skin probe (upper arm rotated 45 deg, every skinned mesh baked before and after; a side follows when >= 95 % of its arm-region vertices
move with the bone):

| look (FBX sha256) | left arm | left hand | right arm | right hand | verdict |
|---|---|---|---|---|---|
| mixamo_worker (control, `d883783c`) | 371/371 | 618/618 | 400/400 | 601/601 | follows |
| anime_f_01, old export (control, `79f49bc1`) | **115/183** | 406/545 | **115/183** | 406/545 | **does not follow** |
| **anime_f_01, re-export (`fe304543`)** | **183/183** | 545/545 | **183/183** | 543/543 | **follows** |
| cartoon_boxo_01 (`431e6cb2`, unchanged) | 116/116 | 106/106 | 116/116 | 110/110 | follows |

Both controls came out as declared, so the verdict is used. The Play frames show the same: in the old export the sleeves stay in a T-pose
while the posed hand floats; in the re-export the whole arm and sleeve lift with the hand (e.g.
`look_check_play_ab_20261114_140152/looks_check_20261114_140152/anime_f_01__STOP__2.0__left_f1_j1_stop_ik_01.png`).

## Re-import of anime_f_01

- The re-export is already in metres (head to foot 1.404 m, humanScale 1.038): no unit-scale change, no avatar rebuild.
- Its 25 textures carry an extension now, so nothing was renamed. That exposed an ordering gap in the declared texture-link fix (re-import 1 linked 0
  of 18 base textures); fixed in 66f41f6 (materials are re-created when an import newly extracts textures; declared first). Re-import 2: **18 of 18**.
- White-emission rule: **not applied** this time; every material now has an emission map (17 the all-black `Shader_NoneBlack.png`, the hair
  `_21.png`, the export's own dark highlight map), which the rule leaves alone.
- 0 material problems, 0 magenta pixels (Edit-mode inventory).

## Per look, Play mode at the real ask positions (2 m groups, arms averaged; tool verdict over both arms)

| look | kind | verdict | person | POINT arm valid | POINT seq read | WAIT hand linked | WAIT cue | WAIT seq read | STOP hand | STOP cue | STOP seq read | wrong reads | facing | arm ratio p95 (vs 1.683) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| **anime_f_01 (re-export, run 2)** | anime | **fails** | **0.99** | 0.70 | 0.00 | 0.00 | 0.00 | 0.00 | 0.01 | 0.01 | 0.00 | 0.00 | 0.07 | 1.99 (+18 %) |
| anime_f_01 (re-export, run 1, not used: cyan NONE frames) | anime | fails | 0.94 | 0.55 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.08 | 3.33 (+98 %) |
| anime_f_01 (old export, step 2) | anime | fails | 0.79 | 0.87 | 0.25 | 0.01 | 0.01 | 0.00 | 0.01 | 0.01 | 0.00 | 0.00 | 0.70 | 1.36 (-19 %) |
| cartoon_boxo_01 | cartoon non-human | not in Play (Edit mode only, unchanged rule) | 0.08 (Edit) | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.01 | - |

Edit mode (neutral stage), same columns: anime_f_01 re-export fails, person 0.28, POINT arm valid 0.24, all reads 0.00, facing 0.13, arm ratio p95
1.41 (-16 %) (old export: 0.14, 0.04, facing 0.14, 0.85). cartoon_boxo_01: identical to step 2 (same file): person 0.08, everything else 0.00, facing 0.01.

How to read it:
- **The re-export is seen as a person far better** (2 m: 0.99, was 0.79; 4 m groups 0.24 to 0.97) and its arm moves, **but nothing is read**: 0 of 12
  POINT, WAIT and STOP sequences at 2 m, and no POINT frame is classed POINT (all NONE). It **stays "fails"**.
- **POINT:** with the worker template's POINT clips the forearm folds back toward the shoulder on this rig, so YOLO's wrist lands near the elbow
  (extension ratio about 0.9; annotated `look_check_v4_20261114_140845/annotated/anime_f_01__POINT__2.0__left_f1_j1_point_mixamo_01.png`).
  Bone arm-to-shoulder ratio 2.28 (+35 %, narrow anime shoulders) is the likely reason the clip does not fit; not changed.
- **WAIT and STOP:** MediaPipe finds a hand in 0 to 5 % of the frames (the VRoid finding of AUDIT.md 14.15). For WAIT the wide flared sleeve hides
  the raised hand; for STOP the open palm is visible but small and stylised.
- **Facing fell to 0.07** (was 0.70): YOLO finds one eye; the other is under the bangs of the re-exported hair (annotated NONE frames). The cause is
  read from the frames only, not measured.
- **Run 1** recorded NONE first, and 56 of its 76 NONE frames show the Editor's flat-cyan placeholder of a shader variant still compiling (the first
  renders of the new materials). POINT/WAIT/STOP frames were clean. As declared (addendum 2), the check ran once more unchanged on the same commit;
  run 2 has 0 cyan frames and is the one used. Run 1 is kept.

## Pitfall checks per look (Play run 2; cartoon from the probes)

| look | bone arm-to-shoulder ratio (vs 1.683) | YOLO p95 ratio (vs 1.683) | mirror fix (largest correction) | hand reach: hand to IK target, median / max | import / material | clothing, face |
|---|---|---|---|---|---|---|
| anime_f_01 (re-export) | 2.28 (+35 %) | 1.99 (+18 %) (2 m: left 1.73, right 1.99) | none needed (< 1 mm) | 0.000 / 0.000 m; **arm mesh follows** (183/183 per side) | metres, no scale fix; 25 textures with extension, 18/18 linked after the 66f41f6 fix; emission maps present (rule not applied) | wide flared sleeves hide the hand (WAIT); bangs over one eye; MediaPipe finds hands in 0-5 % of frames |
| cartoon_boxo_01 | 0.97 (-42 %) (probe) | - | not possible | not in Play; arm mesh follows (116/116 per side) | unchanged (same file); 2 materials recoloured earlier | one finger chain per hand: no hand shape at all; YOLO finds a person in 8 % of frames |

## What this means for the avatar experiment (NOT decided)

- anime_f_01 is now a fair *visual* anime look (textured, moving arm), and body detection at 2 m is high (0.99); its gestures are still not read.
  Whether it stays in the avatar experiment as "anime: body detected, gestures unread" is Nusrat's and Anisha's decision.
- cartoon_boxo_01 is unchanged: WAIT/STOP impossible by construction (no fingers), body barely detected.

## Branch

The two commits were first made on local `main`: the repository had been switched to `main` and fast-forwarded to PR #30 at 13:05, before this
work, and the branch was not checked again before committing. They were moved unchanged to the new branch `nusrat/v4-experiments-ab-anime`, and local
`main` was reset to `origin/main` (cc95b9e). Nothing was pushed. The run_info.json files of the three look-check runs therefore say
`git_branch: main`; their `git_commit` 66f41f6 is the commit on the new branch.
