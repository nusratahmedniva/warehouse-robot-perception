# The avatar experiment: protocol for Nusrat's review

Written by Anisha's side (Python). **Declared 2026-11-21 by Anisha, before any recording** (`AUDIT.md` 16.30 to 16.31.5, section 16.31.1 is the same protocol with its reasons; **changed on 2026-11-21 after your review, 16.31.5**). Three things in it are still waiting for your answer (marked **PENDING**: the session marker, the meaning of a group, the counts of section 2); none changes what is counted or how. One item (the Edit-mode floor, section 4) is a gap I found while writing this text and needs Anisha's confirmation. Please read it and tell us what is wrong, impossible or unclear in Unity; do not change anything on your side because of it before we agree.

## 1. The question, in one sentence

Does the kind of avatar change what the robot's frozen vision finds and reads: the **person**, the **arm**, the **hand** and the **gesture** (POINT, WAIT, STOP, PROCEED; NONE as the "nothing is shown" control)?

It is a **measurement, not a tuning run.** Nothing in the reader, the commander, the perception or the controller is changed because of a result. No look is added, dropped or replaced because of a result. Nothing from it is used for the navigation finals (it runs after them).

**A limitation, stated here:** the experiment measures **the pan-tilt camera only**. Finding people with the **360 camera**, per look, is **not measured** (the robot finds the nearest person with the 360 camera before it asks; whether that works equally for every look is a different question that this experiment does not answer).

## 2. What is recorded, and when

- **When:** once, after the freeze **and after the LAST final sitting** (the test looks are no longer needed for finals), on the frozen commit (your guard, `experiments_ab.md` section 10 item 6, already requires this). **About 3 h are reserved** (the Play part's `-lookCheckTimeout 10800`).
- **Two parts, never mixed:** **Play** (the worker template in `WarehouseRobot_v4.unity`, real motion, J1 and J2 stands, asking bearings 15 to 50 degrees, seed 1) is the **headline**. **Edit** (held poses on the neutral stage) is the **control**. Their numbers are never pooled.
- **Looks: 15** (`looks_ab.json` `avatar_experiment`). Kind groups: **stylised_human = all ten Sunbox looks** (`sunbox_m1`, `sunbox_f1`, `sunbox_f2`, `sunbox_m2`, `sunbox_m_shirt_white`, `sunbox_m_tshirt_black`, `sunbox_m_shirt_plaid`, `sunbox_f_shirt_white`, `sunbox_f_dress_red`, `sunbox_f_shirt_plaid`); **realistic_human** = `mixamo_worker`; **anime** = `anime_f_01`, `anime_f_02_outfit_short`, `anime_f_03_bangs_parted`; **cartoon_non_human** = `cartoon_boxo_01`. A kind with one look describes that look; it is not generalised to the kind.
- **Roles of the looks** (in `configs/v4/data_splits.json`): six looks are `avatar_experiment` only (`sunbox_m2`, `mixamo_worker`, the three anime looks, `cartoon_boxo_01`); six are development (`sunbox_m1`, `sunbox_f1`, `sunbox_m_shirt_white`, `sunbox_m_tshirt_black`, `sunbox_f_shirt_white`, `sunbox_f_dress_red`); three are test (`sunbox_f2`, `sunbox_m_shirt_plaid`, `sunbox_f_shirt_plaid`). Python refuses the six avatar-only looks everywhere except in this experiment. Results are reported by role as well.
- **Commands:** POINT, WAIT, STOP, PROCEED, and NONE (the worker idle, facing the robot).
- **Distances:** 2.0 m (the asking distance; it decides the verdict) and 4.0 m (it can only lower a look from usable to weak).
- **Arms:** left and right (the person's own arm); NONE has no arm.
- **The recording tool is unchanged:** `look_check_v4.py` with `configs/v4/look_check.json`, exactly as it is frozen.

### Exact counts (Play, from `look_check_play_ab.json`)

| | per look | 15 looks |
|---|---|---|
| groups (look x command x distance x arm) | 18 | 270 |
| POINT, WAIT, STOP groups (3 commands x 2 arms x 2 distances) | 12 | 180 |
| PROCEED groups (2 arms x 2 distances) | 4 | 60 |
| NONE groups (2 distances) | 2 | 30 |
| frames per POINT / WAIT / STOP group | 2 sequences x 11 + 16 singles = 38 | |
| frames per PROCEED group | 2 sequences x 21 + 16 singles = 58 | |
| frames per NONE group | 2 x 11 + 16 = 38 | |
| frames in total | **764** | **11,460** |
| independent takes, gesturing commands | 4 commands x 2 arms x 18 = 144 | 2,160 |
| independent takes, NONE | 18 per distance = 36 | 540 |

A **take** is one performance with its own variation and its own drawn camera pose: a sequence (11 frames; PROCEED 21) or a single frame. The 2 m and the 4 m camera see **the same** take, so a take is counted once per arm, not once per distance. (NONE: you declare each NONE take "at its own drawn pose" per distance, so it is counted per distance. Please confirm.)

Edit mode (`look_check.json`): per look, command, distance and arm 2 sequences (11 frames, or 21 for PROCEED, all identical because the pose is held) and 5 single frames.

## 3. What is measured (per look, per kind, per command, per distance)

| name | meaning |
|---|---|
| **person detected** | the share of frames in which the pose model finds a person |
| **hand detected (primary)** | a hand is found **and linked to the gesturing arm** (the hand model's wrist matches that arm's wrist): what the reader needs for WAIT and STOP |
| **hand detected (secondary)** | a hand is found anywhere in the frame (any hand in the person crop) |
| arm valid | both shoulders, both hips, and that arm's elbow and wrist are seen above the confidence floor |
| own cue | all the cues of the shown command pass in the single frame (finger and arm geometry, not the hand model's label) |
| wrong class | the single frame alone would read as another command |
| sequence read | the reader's answer at the end of a sequence: as shown, as another command, or not read |
| facing | the commander rule's facing test passes (both eyes and the nose visible, shoulders wide enough). **Goes into the per-look tables**, as a per-take share with its mean over takes and bootstrap like the other frame measures; **reported only, not in the verdict** |
| POINT arm ratio | reported only (as the tool already does) |

The **verdict per look** (usable / weak / fails / insufficient_data) is the unchanged tool's: its thresholds in `look_check.json` (for example person found at least 0.95 for usable and 0.80 for weak; hand linked at least 0.80 and 0.50 for WAIT and STOP; sequences read as shown at least 0.80 and 0.50). The 2.0 m groups decide.

**PROCEED is evaluated in Play only.** If Edit mode records a posed swing, it is not evaluated (`not_evaluated`), never filled in.

## 4. Counts, the floor and gaps

Every table shows, for each look x command: takes **recorded**, takes **valid**, takes **used**, and the frames behind each mean. Nothing missing is filled in; `not_evaluated` and `insufficient_data` stay as they are.

**Floor (Play).** A look x command cell is evaluated only if, among its **valid** takes, there are **at least 2 sequences and at least 10 single-frame takes per arm and distance**. Unity records 2 and 16, so up to 6 singles per arm and distance may be lost, but **no sequence may be lost** unless the group is repeated (section 6). Below the floor the cell is `insufficient_data`.

**A gap, for Anisha to confirm (PROPOSED, not decided):** Edit mode records only 5 singles and its takes are fixed posed variants, so the floor of 10 cannot hold there, and Edit takes are not independent performances. Proposal: the floor of 10 singles applies to Play only; the Edit floor is the recording as declared (2 sequences, 5 singles), Edit is the control, and its intervals are labelled "variation across the posed variants only".

## 5. Intervals: the take is the unit

Frames inside one take are one performance seen many times, so they are **not independent**.

- A frame-level measure (person found, hand found, hand linked, arm valid, own cue, wrong class) is first computed **as a share per take** (for a single frame it is 0 or 1). The reported value is the **mean over takes** (each take counts once), with a **bootstrap over takes**: **2000 resamples, seed 1, 2.5 and 97.5 percentiles** (`configs/v4/analysis.json`). Takes are resampled within each look x command x distance x arm cell. A pooled cell (a kind group, a command, a role) resamples the takes of each of its looks separately, so its look mix stays fixed: the looks are fixed avatars, not a random sample of looks, so the interval describes take-to-take variation only.
- Only a **yes/no outcome of a take** (a sequence is read as shown / as another command / not read; single-frame takes counted on their own) gets a **Wilson 95 % interval** on the count of takes.
- **Never a Wilson interval over frames.**
- No hypothesis test. A difference between kinds or roles is shown as the difference of two reported values with their counts.
- Where the take-based mean and the tool's pooled verdict disagree about a look, both are shown; the verdict stays the tool's.

## 6. A recording that is INVALID, and repeats

**One seeded pass** is the experiment. A group may be recorded again **only if it is INVALID, and only after it is declared**, never because of its result. **INVALID = a technical failure of the recording, nothing else:**

1. frames or headers are missing or truncated (fewer than the declared 11 or 21 frames, a PNG that cannot be read, a missing header);
2. a header whose intrinsics fail the check of `docs/look_check_v4.md` (the tool already lists such frames);
3. a Unity exception or crash during the take, or a frame time that breaks the declared timing rule: **each frame less than 0.100 s from its 0.1 s mark, and consecutive frames at most 0.2 s apart** (your `experiments_ab.md` section 15 addendum 10, `finals_v4/avatar_rehearsal_check.py`);
4. the wrong look, command, distance or arm was recorded (the name or header disagrees with Unity's own record);
5. **a frame with the placeholder colour (the cyan placeholder or the error-shader magenta) recorded while Unity's shader warm-up record shows compilation still running.** Unity pre-warms all shaders before recording and keeps the warm-up record (a log or file) with the session. The decision is made **from that record and the frame's time, never by inspecting images.**

**Not invalid, so never repeated:** no person found, no hand found or linked, a wrong read, a failing verdict, **and a placeholder colour after the warm-up finished** (a look defect: the look is reported as failing).

A repeat is declared before it is made (the group, the reason, the evidence such as the Unity log). The first recording is kept and listed; the repeat replaces it in the counts; every repeated group is reported. At most one repeat per group. **If the repeat is invalid for the same reason (for example the placeholder colour again while compilation is running), the group is reported INVALID, not failing.**

**What item 5 needs from Unity (proposed; the file and its fields are yours):** the warm-up's finish time on the same clock as the frames' `time_s` (or, per recording, a flag "compilation running at the time of this frame"), kept in the session folder. The Edit part has no `Time.time` in its headers, so for Edit the record is per recording.

## 7. If Unity or the machine crashes during the experiment

The same rule as for the navigation finals (`AUDIT.md` 16.30.1) applies, per part (Edit or Play): the crash is **declared with evidence**; the part may be **resumed once, from the interrupted group** (the first group without a complete recording, in Unity's recording order; that group is listed, not scored, and recorded again from the start), with the same seed, the same configs and the frozen hashes unchanged. **A second interruption makes that part INVALID** (reported with its reason; the other part stands). The two recording folders of a resumed part are reported as one session. **PENDING (yours):** what a "group" is in Unity's recording order, and which option resumes a look check. The Python side is built after you answer.

## 8. How the results are shown

- **Headline table (Play):** all 15 looks, with the summary by kind group. **Edit** is a second table, the control.
- Secondary tables by **look role** (development, test, avatar_experiment) and by **clip role** (development, test), because a group shows every clip of its command on every look. **The clip of each take is read from `recordings.jsonl` (look, command, distance, arm, take, clip).** Edit takes (clip "", pose "posed") are excluded from the clip-role split, so are Play NONE takes (no gesture); a Play gesture take without a clip is `not_evaluated`; an unlisted clip name is refused. The split is computed per distance (the 2 m and 4 m cameras see the same take). The test looks are shown like the others: the experiment runs after the finals.
- Every number carries its counts. Looks per verdict are counted, never averaged.

## 9. What does not happen

No retuning. No look replaced for failing: a failing look is reported as failed (as `anime_f_01` and `cartoon_boxo_01` were in `experiments_ab.md` section 6). No rerun after seeing a result. The earlier engineering look checks (same seed) are not part of the experiment. No avatar result is used for navigation.

## 10. The guard

Python refuses to report an avatar experiment unless: every look and clip name is listed in `data_splits.json` (any role); the session is marked as an avatar-experiment session; the frozen hashes match (the experiment runs after the freeze, so nothing can be tuned on it). The development/test mixing rule does not apply here. The report is written once.

## 11. What we need from you

1. **Q5 is closed** (the clip per take comes from `recordings.jsonl`). **One thing to add on your side:** the Edit writer's rows have no `clip` and no `pose` field yet; please write `clip` "" and `pose` "posed" for Edit takes (until then an Edit row is counted `not_evaluated`).
2. **PENDING Q6:** how is an **avatar-experiment session marked**? (Candidates: `AVATAR_EXPERIMENT_STARTED.json` and `AVATAR_EXPERIMENT_DONE.json`, the commit in `run_info.json`.)
3. **PENDING:** what a **group** is in Unity's recording order, and the option that resumes a look check (section 7).
4. Do the counts in section 2 match what Unity records (18 groups and 764 frames per look in Play; 144 takes per look for the four commands; NONE takes per distance)? Does anything in section 6 (INVALID) describe a failure that cannot be detected from the recording or from Unity's own record?
5. **Before the freeze (must fix):** Unity's `DataSplitsV4.GuardRun` accepts a run whose looks all have one role (a lone `avatar_experiment` look); see `docs/handoff_freeze_v4.md` section 5.
