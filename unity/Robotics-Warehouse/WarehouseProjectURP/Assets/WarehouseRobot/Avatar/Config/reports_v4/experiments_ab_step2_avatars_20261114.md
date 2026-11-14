# Experiments A/B, step 2: avatars (look check of every look of every kind)

Written 2026-11-14 by Claude for Nusrat and Anisha. Unity commit c573486 (branch nusrat/v4-experiments-ab). Design and every import fix declared in
`Avatar/Config/experiments_ab.md` section 2 before it was tested. An engineering check, not an evaluation: no reader, perception or control value
was changed because of it. Test looks (sunbox_f2 and the two proposed test looks) appear here only because this is the avatar experiment.

## Runs

| what | folder (robot_vision/outputs/) |
|---|---|
| character import (anime_f_01, cartoon_boxo_01) | `import_characters_20261114_043231` (last; earlier imports kept) |
| rig probe (scale, proportions, skinning, emission) | `probe_rigs_20261114_*` (last after the avatar rebuild) |
| Edit-mode look check, neutral stage, 13 looks | Unity `look_check_ab_20261114_030646`, tool `look_check_v4_20261114_030809` |
| **Play-mode look check at the real ask positions** (J1, J2 stands, bearings 15-50 deg, 2 and 4 m, real motion), 12 looks | Unity `look_check_play_ab_20261114_043454`, tool `look_check_v4_20261114_055358` |
| superseded (kept, not used): first Edit runs before the import fixes; the first Play run, whose anime_f_01 floated 11.6 m up (stale avatar) | `look_check_ab_20261114_022355`, `_023054`, `_025944`; `look_check_play_ab_20261114_031052`; tools `look_check_v4_20261114_023255` |

Free memory during the Play check: minimum 542 MB, median 2,592 MB; Unity working set up to 2,023 MB (first run: 343 MB minimum). Frame times are not
logged by the look check (they are in every telemetry message of a trial session).

## Per look, Play mode at the real ask positions (2 m groups, arms averaged; tool verdict over both arms)

| look | kind | verdict | person | POINT arm valid | POINT seq read | WAIT hand linked | WAIT cue | WAIT seq read | STOP hand | STOP cue | STOP seq read | wrong reads | facing | arm ratio p95 (vs 1.683) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| mixamo_worker | realistic | weak | 1.00 | 1.00 | 0.75 | 1.00 | 0.93 | 1.00 | 1.00 | 1.00 | 1.00 | 0.00 | 0.99 | 1.78 (+6 %) |
| sunbox_m1 | stylised | fails | 1.00 | 1.00 | 0.75 | 0.82 | 0.80 | 0.75 | 1.00 | 1.00 | 1.00 | 0.50 | 1.00 | 1.89 (+12 %) |
| sunbox_f1 | stylised | fails | 1.00 | 1.00 | 1.00 | 0.63 | 0.62 | 0.75 | 0.99 | 0.97 | 1.00 | 0.00 | 1.00 | 1.89 (+12 %) |
| sunbox_f2 | stylised (v4 test look) | fails | 1.00 | 1.00 | 0.75 | 0.91 | 0.88 | 1.00 | 0.99 | 0.99 | 1.00 | 0.50 | 0.92 | 2.10 (+25 %) |
| sunbox_m2 | stylised | weak | 1.00 | 1.00 | 1.00 | 0.95 | 0.93 | 1.00 | 1.00 | 1.00 | 1.00 | 0.00 | 0.86 | 2.05 (+22 %) |
| sunbox_m_shirt_white | stylised, nav | weak | 1.00 | 1.00 | 1.00 | 0.64 | 0.64 | 0.75 | 0.96 | 0.96 | 1.00 | 0.00 | 0.99 | 1.92 (+14 %) |
| sunbox_m_tshirt_black | stylised, nav | fails | 1.00 | 1.00 | 0.75 | 1.00 | 0.82 | 0.75 | 0.99 | 0.99 | 1.00 | 0.50 | 1.00 | 2.03 (+20 %) |
| sunbox_m_shirt_plaid | stylised, nav | fails | 1.00 | 1.00 | 1.00 | 0.66 | 0.50 | 0.50 | 0.99 | 0.99 | 1.00 | 0.00 | 0.98 | 1.92 (+14 %) |
| sunbox_f_shirt_white | stylised, nav | fails | 1.00 | 1.00 | 0.75 | 0.12 | 0.09 | 0.00 | 0.82 | 0.82 | 0.75 | 0.50 | 1.00 | 1.91 (+14 %) |
| sunbox_f_dress_red | stylised, nav | weak | 1.00 | 1.00 | 0.75 | 0.96 | 0.91 | 1.00 | 0.99 | 0.99 | 1.00 | 0.00 | 0.97 | 2.09 (+24 %) |
| sunbox_f_shirt_plaid | stylised, nav | fails | 1.00 | 1.00 | 1.00 | 0.20 | 0.20 | 0.25 | 1.00 | 0.99 | 1.00 | 0.00 | 0.94 | 1.98 (+18 %) |
| anime_f_01 | anime | fails | 0.79 | 0.87 | 0.25 | 0.01 | 0.01 | 0.00 | 0.01 | 0.01 | 0.00 | 0.00 | 0.70 | 1.36 (-19 %) |
| cartoon_boxo_01 | cartoon non-human | not in Play (Edit mode only) | 0.08 (Edit) | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.01 | - |
| (mannequin) | faceless mannequin | none present (no `mannequin_*.fbx`) | | | | | | | | | | | | |

How to read it:
- **"wrong reads" 0.50 = 1 of the 2 sequences of a group read as another command, and every one is POINT read as STOP** (4 sequences at 2 m, 9 at 4 m, over all
  looks). This is the reader's open-palm geometry (step 1 report: spread from the wrist, no palm direction, MediaPipe's label not required since 2026-11-08), not the
  look; the 8 November Play check (label still required) had no such reads. It turns sunbox_m1, f2, m_tshirt_black and f_shirt_white to "fails".
- **WAIT is weak on the long-sleeved Sunbox "Shirt" item** (hand not linked while raised beside the head): f1 0.63, f_shirt_white 0.12, f_shirt_plaid 0.20, m_shirt
  white 0.64, m_shirt_plaid 0.66, against the T-shirt and dress looks 0.91-1.00. It matches the known f1 WAIT weakness (AUDIT.md 15, D3/D4).
- **Sets A and B use POINT and PROCEED only**: for them every Sunbox look has person 1.00 and POINT arm valid 1.00. PROCEED is not in the tool's commands, so its
  readability per look is not evaluated (a Python change, for Anisha).
- **mixamo_worker** was excluded on 2026-11-07 for its face keypoints (0-11 % on the neutral stage); at the real ask positions it faces 0.97-1.00.

## Pitfall checks per look (Unity side; Play run)

| look | bone arm-to-shoulder ratio (vs 1.683) | YOLO p95 ratio (vs 1.683) | mirror fix (largest correction) | hand reach: hand to IK target, median / max | import / material | clothing, face |
|---|---|---|---|---|---|---|
| mixamo_worker | 1.12 (-33 %) | 1.78 (+6 %) | 1.5 mm | 0.000 / 0.000 m | URP material override, no magenta | |
| Sunbox male looks | 1.57-1.58 (-6 to -7 %) | 1.89-2.05 (+12 to +22 %) | 49.1 mm (fix applied) | 0.000 / 0.006 m | converted materials, no magenta | long-sleeved Shirt weakens WAIT |
| Sunbox female looks | 1.57-1.58 (-6 %) | 1.89-2.10 (+12 to +25 %) | 50.7 mm (fix applied) | 0.000 / 0.005 m (HumanAvatarFix rebuilds the avatar: the old 0.73 reach is gone) | no magenta | long-sleeved Shirt weakens WAIT; f2 no glasses |
| anime_f_01 | 2.28 (+35 %) | 1.36 (-19 %) | none needed (0 mm) | 0.000 / 0.000 m (bones), but the **arm mesh does not follow the arm bones** | import fixes: unit scale x100 + avatar rebuilt, 25 textures without extension, white emission off | MediaPipe finds its hands in 1 % of WAIT/STOP frames (as the VRoid finding of AUDIT.md 14.15) |
| cartoon_boxo_01 | 0.97 (-42 %) (probe) | - | not possible | not in Play | unit scale x100 + avatar rebuilt; imported with colours (gloves and helmet recoloured by the declared rule) | one finger chain per hand: no hand shape at all; YOLO finds a person in 8 % of frames |

Error-shader check: 0 magenta pixels and no material problem on every look in every render (Edit-mode inventory).

## Shortlist and proposals (NOT decided: for Anisha's data_splits.json and Nusrat)

**Licences.** Sunbox: Unity Asset Store EULA (use in a published study; never redistributed). Mixamo: Adobe terms (use in projects; never redistributed).
anime_f_01 and cartoon_boxo_01: **not verified: `unity/downloads/characters_v4/SOURCES.txt` does not exist**; the task says both are Nusrat's own characters.

**Navigation looks (Sets A and B), proposal as declared before the check:**

| | development | test (unseen until the finals) |
|---|---|---|
| male | `sunbox_m_shirt_white`, `sunbox_m_tshirt_black` | `sunbox_m_shirt_plaid` |
| female | `sunbox_f_shirt_white`, `sunbox_f_dress_red` | `sunbox_f_shirt_plaid` |

All six read POINT at 2 m with person 1.00 and arm valid 1.00 (Sets A/B use POINT and PROCEED). Caveat for the decision: the three long-sleeved shirt looks per
gender read WAIT poorly; if the navigation looks should also serve WAIT/STOP studies, swapping the shirt looks for T-shirt or dress costumes (e.g. TShirt white
for both genders) would need one more look check before recording.

**Avatar experiment per kind:** realistic `mixamo_worker`; stylised `sunbox_m1`, `sunbox_f1`, `sunbox_f2`, `sunbox_m2` and the six navigation looks; anime
`anime_f_01` (its arm mesh cannot be posed: a re-export of the character, e.g. VRM through UniVRM, is needed for a fair gesture test; detection of the body and
face is measurable now); cartoon non-human `cartoon_boxo_01` (body barely detected; no fingers: WAIT/STOP impossible by construction); faceless mannequin:
none available (add a `mannequin_*.fbx` to `unity/downloads/characters_v4/` with its licence to include one).
