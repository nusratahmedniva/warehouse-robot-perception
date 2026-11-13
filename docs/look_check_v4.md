# v4 look check: do the real models see each avatar look?

Status: **tool and rules declared 2026-11-06, before any real frame of any look exists.** Tool: `robot_vision/look_check_v4.py`.
Rules: `robot_vision/configs/v4/look_check.json` (proposed by Claude with reasons, accepted by Anisha as proposed).

## Why

Every v4 gesture test so far uses synthetic keypoints. Before the clips and recordings are built, we need to know whether the
real YOLO11s-pose and MediaPipe hand models find the body and the hands of each avatar look (VRoid, stylised), and whether the v4
reader reads POINT, WAIT and STOP on it. **A look that fails is swapped.**

It is an **engineering check, not an evaluation**:

- nothing is tuned on it: no reader, commander, perception or control value changes because of its result; the only action it
  can cause is swapping a look (or re-posing it);
- it never reads `truth.jsonl`, `data_splits.json` or any ground-truth loader (a test checks the tool's imports); a look is judged
  by how it looks to the models, whatever its split;
- the commands it compares against are the recording labels in the file names, which Nusrat sets when recording.

## What Nusrat records

For **each look** (all of them, including the unseen one), one pan-tilt camera frame stream exactly as the robot would see it:
730 x 530, the default field of view (`vertical_fov_deg` 60), the camera aimed at the person so the person is near the image centre
and the head, both shoulders, both hips and both arms are in view. One person in the frame.

| what | values |
|---|---|
| command | `POINT`, `WAIT`, `STOP` (required); `NONE` (optional negative control: arms down, nothing to read) |
| distance | **2.0 m** (the asking distance: it decides the verdict) and **4.0 m** (a commander seen from afar; it can only lower a look from usable to weak) |
| arm | **both**: `left` and `right` are the person's own arms (the avatar's left arm appears on the image right) |
| sequences | at least **2 per command, distance and arm**: 1 s at 10 Hz, **11 frames** (t = 0.0 to 1.0 s; 10 to 20 frames are accepted). The arm is already up and **held still for the whole second**: the check is about the look, not about the raising motion |
| single frames | recommended **5 per command, distance and arm**, with small differences between them (hand height, finger spread, a slightly different arm direction) |

How each command should look (these are the poses of `docs/gesture_reader_v4.md`):

- **POINT**: arm outstretched. Make the two sequences of each arm different: one **sideways in the image plane** (the person's left arm
  toward the image right, the right arm toward the image left) and one at about 45 degrees toward the front. The sideways take lets the
  tool measure the arm length in shoulder widths against the assumed 1.683 (calibrated 2026-11-13; it was 1.4 when this check was declared).
- **WAIT**: one hand raised near the head, forearm vertical, index finger up, the other three fingers curled.
- **STOP**: open palm toward the camera, four fingers extended and spread, arm bent or extended toward the robot.
- **NONE** (optional): arms hanging.

A complete set for one look is 3 commands x 2 arms x 2 distances = 12 groups, each with 2 sequences (and about 5 single frames):
24 sequences and about 60 single frames.

### Folder layout and names

One folder (not in the repo: datasets and recordings are never copied into it). Names use two underscores as separators:

```
<look>__<command>__<distance_m>__<n>
```

`<look>` may contain single underscores but not `__`; `<command>` is in capitals; `<distance_m>` is a number (`2`, `2.0`, `4.0`);
`<n>` is any take number or label. A single frame is a PNG with a header next to it; a sequence is a **subfolder** with that name
holding `frame_000.png`, `frame_001.png`, ... (numbers sort numerically):

```
looks_check/
  Mia__POINT__2.0__1.png          Mia__POINT__2.0__1.json        (single frame and its header)
  Mia__WAIT__4.0__3.png           Mia__WAIT__4.0__3.json
  Mia__STOP__2.0__1/              (sequence: one folder per take)
    frame_000.png  frame_000.json
    frame_001.png  frame_001.json
    ...
    frame_010.png  frame_010.json
```

### The header JSON next to every PNG

The `frame_pan_tilt` header of the bridge for that frame (protocol 3, `docs/protocol_v3.md` section 2), saved as `<same name>.json`:

```json
{
  "width": 730, "height": 530,
  "fx": 458.99, "fy": 458.99, "cx": 365.0, "cy": 265.0,
  "vertical_fov_deg": 60.0,
  "pan_deg": 0.0,
  "time_s": 12.4,
  "arm": "left"
}
```

| key | | meaning |
|---|---|---|
| `fx`, `fy`, `cx`, `cy`, `vertical_fov_deg` | required | render-time intrinsics. They are checked like a live frame: `fy = (height / 2) / tan(vertical_fov_deg / 2)`, `fx = fy`, `cx = width / 2`, `cy = height / 2`, relative tolerance 0.001 (`configs/v4/bridge.json`). A frame that fails is left out and listed in the report |
| `width`, `height` | optional | must equal the PNG size when present |
| `pan_deg` | optional (0) | pan of the camera, as in the bridge |
| `time_s` | optional | Unity `Time.time` of the frame. If every frame of a sequence has it, it is used; otherwise the frames are taken to be 0.1 s apart (10 Hz) |
| `arm` | **recommended** | `"left"` or `"right"`: the person's own arm that makes the gesture. Without it the tool infers the raised arm and cannot separate left from right, so the look cannot be judged per arm (the report says so). All frames of a sequence carry the same value |

Other keys (pose, camera height, ...) may stay in the file; they are ignored.

Note: the live bridge sends JPEG, the check reads lossless PNG, so the check is slightly kinder than live. A look that ends up only
`weak` because of a hand cue should be looked at again with JPEG-compressed frames.

## How to run

From `robot_vision/`, with the project venv. The real models are YOLO11s-pose (`models/yolo11s-pose.pt`, git-ignored) and the MediaPipe
recognizer of the gesture submodule; both are loaded through `hri_perception_v4.HriPerceptionV4` (CUDA, then MPS, then CPU).

Windows PowerShell:

```powershell
.\.venv\Scripts\python.exe look_check_v4.py --input D:\path\to\looks_check
```

macOS Terminal:

```bash
.venv/bin/python look_check_v4.py --input /path/to/looks_check
```

Options: `--no-annotate` (skip the annotated PNGs), `--device cpu|cuda|mps`, `--config` (another declared rule file; the default is
`configs/v4/look_check.json`). The folder is read only. Each run writes a **new** folder `outputs/look_check_v4_<time>/`; nothing is
overwritten.

Output folder:

| file | content |
|---|---|
| `report.md` | the verdict per look with its reasons, then the tables below |
| `report.json` | everything, including every frame (keypoint confidences, hand, cues, the reader's answer per frame) |
| `annotated/` | each frame with the YOLO keypoints (green above `body_kp_conf_min`, red below it = missing for the reader), the hand landmarks (orange), the hand box (magenta) and a text strip |
| `config_used/`, `run.json` | the exact configs, the git commit, the model weights hash, devices and a sha256 manifest of the input files (the input folder's name only, no local paths) |

## What it measures

Per group (look, command, distance, arm), over **all frames of the group; a frame without a person counts as lost**:

| number | meaning |
|---|---|
| person found | YOLO found a person (the largest box is read, as v3 does) |
| shoulder, elbow, wrist, hip keypoints | share of frames with each keypoint above `body_kp_conf_min` (0.5) |
| arm valid | both shoulders, both hips, the elbow and the wrist of the recorded arm above it: what the reader needs to use the arm |
| hand found / linked / 21 landmarks inside / world landmarks / hand box height | MediaPipe found a hand in the person crop; it is linked to the recorded arm by its wrist; all 21 landmarks are inside the image; its size in pixels |
| arm-to-shoulder ratio | `|shoulder to wrist| / shoulder width` in the image (median, min, max, 95th percentile) against the assumed 1.683 (POINT geometry; 1.4 when this check was declared, calibrated 2026-11-13). Foreshortening only shortens it, so the 95th percentile of a group with a sideways take reaches the true ratio |
| cues per frame | raised arm, finger up (index extended, others curled, pointing up), open palm (four fingers extended and spread), MediaPipe category as the command needs it (**reported only**, since 2026-11-08 the reader does not require it); `own cue` = **all** cues of the recorded command pass in that frame (`gesture_motion.frame_flags`: finger geometry and arm pose, **not** the MediaPipe label) |
| wrong class | the frame alone would read as another command (STOP > WAIT > POINT as in the reader) |
| sequence read | the reader's answer at the last frame of each sequence (the live window and thresholds): as recorded, or another command (`NONE` and `insufficient_history` are lost coverage, not a wrong command) |
| facing | the commander rule's facing test passes (both eyes and the nose visible, shoulders wide enough). **Reported only**, not in the verdict: if a look never shows its face keypoints it can never be the commander, which is a reason to look at it |

## Verdict rules (declared in `configs/v4/look_check.json`)

A group is graded by its worst check. `usable` / `weak` / otherwise `fails`; a check without enough data is `not_evaluated`
(at least 10 frames, and for the sequence checks at least 2 sequences, per group).

| check | usable | weak | else |
|---|---|---|---|
| person found | >= 0.95 | >= 0.80 | fails |
| arm valid (POINT, WAIT; not STOP, which needs only the hand) | >= 0.90 | >= 0.70 | fails |
| hand linked (WAIT, STOP required; POINT: can only make it weak) | >= 0.80 | >= 0.50 | fails |
| own cue | >= 0.70 (the reader's `class_share_min`) | >= 0.50 | fails |
| frames read as another command | <= 0.10 | <= 0.25 | fails |
| sequences read as recorded | >= 0.80 | >= 0.50 | fails |
| sequences read as a different command | <= 0.10 | <= 0.25 | fails |
| POINT arm ratio, 95th percentile | 1.18 to 2.10 (1.683 -30 % / +25 %; 0.98 to 1.75 around 1.4 when declared) | outside | never fails |

A **look** is judged on its **2 m** groups of POINT, WAIT and STOP (both arms when any recording of the look carries an arm label;
a negative-control `NONE` group is graded too when present), in this order:

1. `fails` if any decisive group fails;
2. `insufficient_data` if a required decisive group is missing or not evaluated (**never** `usable` on missing data);
3. `weak` if any decisive check is weak, or a 4 m (or other secondary) group is not usable (it can only lower a look to weak);
4. `usable` otherwise.

Recordings at distances other than 2 and 4 m are reported and not judged.

## What happens with a result

- `usable`: record the look's clips.
- `weak`: Anisha and Nusrat decide, with the reasons in the report, whether to keep it (and say so in the study) or to swap it.
- `fails`: swap the look. Nothing else changes.
- `insufficient_data`: record what the reasons list.

A look is checked before the clips are recorded; a swapped look is checked again with the same rules.

## Limits

- Synthetic and real-photo tests only so far: the tool is tested with a scripted detector (no model) and was run once on two
  ordinary photographs only to see that the real model path works. No avatar has been checked yet.
- PNG instead of the live JPEG (above).
- One person per frame is read (the largest box); no tracker, so nothing carries over between recordings.
- Sequences are a held pose. The raising and swinging of the arm, and the commander rule with several people, are not tested here.
- The arm label is the recording's, not a measurement; the check does not verify that the avatar really raised the labelled arm
  (a wrong label shows up as a failing `arm valid` or `own cue`).

## Decided

- 2026-11-06 (Anisha): verdict rules accepted as proposed (table above); the arm label is the optional `arm` key in the header JSON, the
  file name format stays `<look>__<command>__<distance_m>__<n>`.
- 2026-11-06: `arm valid` is not checked for STOP (the reader reads STOP from the linked hand alone); this refinement is part of the
  declared config.
- 2026-11-08 (Anisha): the reader no longer requires MediaPipe's label for STOP and WAIT (AUDIT.md 14.16), so `own cue` and the sequence reads of a look check
  now follow the finger geometry; the label stays in the report per frame (`category`). The declared verdict rules of `configs/v4/look_check.json` are unchanged (its
  `own_cue_rate` text still lists "category and score" among the cues; the check itself uses `frame_flags`). Results of look checks made before this date were
  computed with the label required.
