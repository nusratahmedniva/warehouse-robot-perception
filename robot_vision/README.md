# robot_vision — environment segmentation (stage 1)

First stage of the indoor service-robot vision system:
**THUD dataset loading → pretrained semantic segmentation → visualisations → evaluation.**

Depth, tracking, passage fitting, gestures and Unity integration are *not* part of this stage.
The teammate's gesture module (anisha274, https://github.com/anisha274/media_pipe_gesture, MIT licence) is a git
submodule at `../external/media_pipe_gesture` and is connected only through `gesture_adapter.py` (see
[Gesture adapter](#gesture-adapter)).

## Files

| File | Purpose |
|---|---|
| `configs/office.json` | Dataset root, capture, sensor, model + revision, class lists and label mappings. Edit this (or pass CLI options) instead of the Python code. |
| `check_environment.py` | Prints Python/PyTorch/package versions, CUDA/MPS availability, `nvidia-smi`; selects a device and runs a small tensor test on it. |
| `thud_data.py` | Reads `captures_*.json` and the semantic palette, matches RGB ↔ semantic files via metadata, checks steps/timestamps, decodes semantic colours. |
| `audit_dataset.py` | Validates a capture and N frames; writes `audit_report.json`. |
| `run_segmentation.py` | SegFormer inference, label grouping, saved masks/visualisations, confusion matrix and evaluation report. |
| `requirements.txt` | Common dependencies (PyTorch is installed separately, per platform). |
| `configs/tracking_office.json` | Stage 2: detector weights, thresholds, image size, tracker YAML, overlay steps. |
| `check_camera_streams.py` | Compares the two camera streams that share RGB basenames; checks RGB/label alignment. |
| `track_objects.py` | Stage 2: YOLO11n + ByteTrack on a segmentation run's frames, with box-level segmentation summaries. |
| `verify_tracking_run.py` | Integrity checks recomputed from a tracking run's files (not an accuracy evaluation). |
| `configs/depth_thud_synthetic.json` | Validated synthetic depth encoding and pixel intrinsics, with the evidence summary. |
| `thud_depth.py` | Depth decoding (raw → metres, saturation → invalid), intrinsics from FOV, back-projection. |
| `validate_depth.py` | Fits and tests the depth/intrinsics against dataset 3D boxes on several captures. |
| `tests/test_thud_depth.py` | Unit tests for `thud_depth.py`, plus one dataset check (`python -m unittest discover -s tests`). |
| `fuse_objects.py` | Step 4: per-tracked-object 3D position (camera and world frame) and floor context from depth + pose + predicted masks + tracks, with geometry checks and evaluation. |
| `configs/fusion_office.json` | Inputs, pixel-selection rules, floor-context rule and evaluation settings for `fuse_objects.py`. |
| `configs/robot.json` | Provisional robot width (0.60 m), safety margin per side (0.10 m), max speed (1.0 m/s), deceleration (0.5 m/s²); names the load file. |
| `tests/test_fuse_objects.py` | Unit tests for the pose convention, pixel selection and point-to-box distance. |
| `report_step4.py` | Step 4 report supplement: calibration used, fitted parameters, all-class table, unmatched-couch classification, timing and step sizes. Reads a fusion run; never modifies it. |
| `configs/data_splits.json` | Splits: Office/dynamic Capture_1 development, Capture_2 adjustment, Capture_3/4 final evaluation only; Gym/dynamic Captures 2–6 cross-scene final evaluation; Gym/dynamic Capture_1 excluded. |
| `motion.py` | Step 8 building blocks: observation quality, track resets, trailing-window velocity, labels with hysteresis, route geometry. |
| `estimate_motion.py` | Step 8: world and relative motion per tracked observation from a fusion run, proxy-route time-to-route, evaluation, plots. |
| `make_proxy_route.py` | Writes an explicit corridor config from the recorded camera path, with the one required width (`footprint.py`). |
| `configs/motion_office.json` | Step 8 settings (fixed before evaluation), input runs and config paths. |
| `configs/proxy_route_office_capture1.json` | The THUD `proxy_route` corridor: 16-point centreline, 3.70 m long, 0.80 m wide (robot only; predates the load). |
| `tests/test_motion.py` | Unit tests for `motion.py`. |
| `report_motion.py` | Step 8 supplement from a motion run: velocity window and delay, resets by cause and class, per-person errors, time-to-route verdict. |
| `run_paths.py` | Portable paths: run folders store `{dataset_root}/…`, `{output_root}/…`, `{project_root}/…` and resolve them on the current machine. |
| `migrate_run_paths.py` | Rewrites absolute paths in existing run folders as portable tokens, with a backup of each original file. |
| `tests/test_run_paths.py` | Path round trip, migration, loading a run under a different dataset root, no absolute paths in `outputs/`. |
| `data_splits.py` | Split lookup and the `--final-evaluation` guard used by every script that reads a capture. |
| `configs/motion_office_v1_equivalent.json` | Step 8 v1 settings expressed for the current code (development before/after only); reproduces the accepted baseline exactly. |
| `configs/motion_office_k2_candidate.json` | `uncertainty_k = 2` candidate, evaluated once on Capture_2 for the declared k decision. |
| `configs/proxy_route_office_capture2.json` | `proxy_route` corridor from the Capture_2 camera path (0.80 m, robot only; predates the load). |
| `configs/motion_frozen.json` | Frozen motion config: file name and SHA-256; required by `estimate_motion.py --final-evaluation`. |
| `tests/test_device_and_splits.py` | Device selection CUDA → MPS → CPU with mocked availability; split guard. |
| `../.github/workflows/tests.yml` | GitHub Actions: unit tests on windows-latest and macos-latest (runs when pushed). |
| `decision.py` | Step 9 core (standard library only): input dataclasses, required width, corridor geometry, gesture filter, rules 1–8 with timing. |
| `decision_io.py` | Step 9 configs, placeholder providers (scenario / script files), scenario runner, run-folder writers. |
| `run_decisions.py` | Runs scenario files through the rules; writes `decisions.csv` + `decision_log.json` per scenario. |
| `replay_decisions.py` | Optional demo: frozen Step 8 motion run + `proxy_route` + placeholder passage and scripted gestures. |
| `configs/decision.json` | Step 9 thresholds and timing, declared before any decision run. |
| `configs/load.json` | Carried load: centred Euro pallet, 0.80 m across travel, "configured, not measured". |
| `footprint.py` | The one required-width function (robot.json + load.json), the decision look-ahead and the caution distance; standard library only. |
| `person_box_depth.py` | Lower-bound distance (5th percentile of valid box depths) of tracked people, for Step 9 people without a position. |
| `configs/replay_script_office_capture2.json` | Placeholder passage and scripted gestures for the Capture_2 replay demo. |
| `tests/test_decision.py`, `tests/scenarios/*.json` | Step 9 tests; scenarios are plain JSON so they can be replayed in Unity. |
| `../external/media_pipe_gesture` | Git submodule: the teammate's gesture module (MediaPipe model + `gesture_heuristics.py`), pinned at `180e2796`. Not modified. |
| `configs/gesture.json` | Gesture adapter: source and commit, model hash, her category mapping, recognizer settings, the two modes, smoke and evaluation settings. |
| `gesture_adapter.py` | Gesture adapter: MediaPipe IMAGE mode, `full_frame` and `person_crop` modes, raw detections, `to_gesture_events` → `decision.GestureEvent`. |
| `gesture_smoke.py` | Optional smoke test: both modes on sample images (git-ignored `sample_images/gesture`), annotated copies. |
| `gesture_eval.py` | Evaluation hook: accuracy by distance bin and mode, confusion matrices, from Unity labels; `not_evaluated` until they exist. |
| `tests/test_gesture_adapter.py` | Mapping, crop geometry, duplicate hands and one owner per hand, NONE handling, no adapter threshold, lazy MediaPipe import, evaluation hook. |
| `tests/test_opencv.py` | `opencv-python` and `opencv-contrib-python` pinned to one version; `cv2` version and every `cv2` name the pipeline uses. |

## Setup

### Windows (tested: RTX 3060, driver 616.92, Python 3.12.14)

```powershell
cd E:\RobotVisionWorkspace\robot_vision
uv venv --python 3.12 .venv
# PyTorch with CUDA 13.0, command from the official selector at pytorch.org/get-started/locally
uv pip install --python .venv\Scripts\python.exe torch==2.14.1 torchvision --index-url https://download.pytorch.org/whl/cu130
uv pip install --python .venv\Scripts\python.exe -r requirements.txt
```

(Without `uv`: create the venv with `py -3.12 -m venv .venv`, then use `.venv\Scripts\python.exe -m pip install ...` with the same arguments.)

### macOS

The official selector gives the default package for macOS (MPS on Apple silicon, CPU otherwise):

```bash
python3.12 -m venv .venv
.venv/bin/python -m pip install torch torchvision
.venv/bin/python -m pip install -r requirements.txt
```

Point the code at the dataset without editing source, e.g.
`export THUD_DATASET_ROOT=/Volumes/Data/RGB-D` or `--dataset-root /Volumes/Data/RGB-D`.
Use `--device mps` (fails if MPS is missing) or `--device auto`.

### Tested versions

torch 2.14.1+cu130, torchvision 0.29.1+cu130, transformers 5.19.0, huggingface_hub 2.2.0,
numpy 2.5.2, pillow 12.3.0, matplotlib 3.11.2; stage 2 adds ultralytics 8.4.175, lap 0.5.13, scipy 1.18.1,
opencv-python 5.0.0.93; the gesture adapter adds mediapipe 1.1.1 (with opencv-contrib-python 5.0.0.93). Every run records the versions it used in
`evaluation_report.json`.

## Running (Windows PowerShell)

```powershell
cd E:\RobotVisionWorkspace\robot_vision
.\.venv\Scripts\python.exe check_environment.py --device cuda
.\.venv\Scripts\python.exe audit_dataset.py --config configs\office.json --frames 3
.\.venv\Scripts\python.exe run_segmentation.py --config configs\office.json --frames 3 --device cuda
.\.venv\Scripts\python.exe run_segmentation.py --config configs\office.json --frames 300 --device cuda
```

Useful options: `--start N` (first matched frame index), `--capture <path>` (relative to the dataset root or
absolute), `--dataset-root`, `--output-root`. `--device cuda|mps|cpu` never falls back to another device;
`--device auto` (the default of `run_segmentation.py`, `track_objects.py` and `check_environment.py`) picks CUDA,
then MPS, then CPU: `check_environment.select_device()`, lines 36–41. `tests/test_device_and_splits.py`
checks that order with mocked CUDA/MPS availability, and that explicit modes never fall back. Batch size is 1.
Use `--all-frames` to process every usable frame of a capture.

The model weights download once into the Hugging Face cache in your user profile
(`%USERPROFILE%\.cache\huggingface`), outside this repository.

## Dataset handling (THUD synthetic, Unity Perception format)

Checked on `Synthetic_Scenes/Office/dynamic/Capture_1`:

- `Label/captures_000.json … captures_019.json` hold 2980 records: 1490 for sensor `camera_0` and 1490 for
  sensor `camera`. Only `camera_0` records carry the `semantic segmentation` annotation, so `camera_0` is the
  RGB stream used (`rgb_sensor_id` in the config).
- Each record gives `sequence_id`, `step`, `timestamp`, the RGB file name and the semantic file name.
  Frames are matched through these metadata fields and ordered by step. Image numbers do **not** equal steps
  (step 0 → `rgb_2.png` / `segmentation_2.png`).
- The dataset copy on disk has flattened Unity's `RGB<uuid>/` and `SemanticSegmentation<uuid>/` folders into
  `RGB/` and `Label/Semantic/`, so files are found by basename. Both sensors name their RGB files
  identically and have identical poses, intrinsics and timestamps; the flattened folder cannot show which
  sensor rendered each file. This is reported as a warning in every audit/run.
- Duplicate steps or basenames, non-finite or non-increasing timestamps, missing files and too few frames
  stop the run. No FPS is assumed; only the recorded timestamps are used.

### Semantic colour decoding

The palette (`annotation_definitions.json`, 29 classes) stores colours as floats 0–1. Colour code =
`round(value × 255)` per RGBA channel. Pixels are matched exactly first; a pixel colour with no exact match
may match within ±1 per channel if exactly one class qualifies. Anything else (unmatched or ambiguous) gets
ignore ID **255**. In practice: `Bag` needs the ±1 tolerance (palette 176.51 → file value 176), and
pure-black `(0,0,0)` pixels match no class and are ignored.

## Classes and mappings

| ID | Project class | Model (ADE20K, resolved by name from `model.config.id2label`) | Dataset (THUD palette name) |
|---|---|---|---|
| 0 | other | every other model class | every other palette class: BookShelf, Bag, Desk, Table, Plants, Window, Curtain, Lamp, TV, laptop, PlantRack, Pot, Folder, Book, Box, Ceramics, cup, Computer, clock, Glass, Airconditioner, Beam, Spotlight |
| 1 | wall | wall (0) | wall |
| 2 | floor | floor (3) | Floor |
| 3 | ceiling | ceiling (5) | Ceiling |
| 4 | person | person (12) | people |
| 5 | chair | chair (19), armchair (30), swivel chair (75) | Chair |
| 6 | sofa | sofa (23) | Sofa |
| 255 | ignore | — | pixels whose colour cannot be decoded |

## Outputs

Each run creates a new folder `outputs/seg_<scene>_<split>_<capture>_<N>f_<date>_<time>/`:

| Path | Content |
|---|---|
| `pred_ade20k/step_XXXXXX.png` | Native model prediction, ADE20K class IDs 0–149 (8-bit, original size) |
| `pred_grouped/` | Project class IDs 0–6 |
| `ref_grouped/` | Reference labels as project IDs 0–6, 255 = ignored |
| `overlays/` | RGB blended with the grouped prediction colours |
| `floor_candidate/` | 255 where the model predicted floor, else 0 |
| `comparisons/` | RGB / reference / prediction side by side (all frames if ≤ 10, else first, middle, last) |
| `legend.png` | Colour legend |
| `confusion_matrix.csv/.png` | Rows = reference class, columns = predicted class, in pixels |
| `evaluation_report.json` | Metrics, settings, model revision, versions, device, timings, mappings |
| `manifest.jsonl` | One line per processed frame (metadata, file paths, timings, decoding stats), written as it goes |
| `run_info.json`, `run_status.json`, `COMPLETE` | Run settings and status. `COMPLETE` exists only after all frames and the evaluation finished |

A **floor-candidate mask** only shows pixels the model called floor. It is *not* a safe lane, verified free
space or a passable route; those need depth, obstacle geometry and robot dimensions.

## Reading the evaluation report

- **Confusion matrix**: for every valid reference pixel, counts (reference class, predicted class).
  The diagonal is correct pixels.
- **IoU** for a class = correct pixels ÷ (pixels that are that class in the reference **or** the prediction).
  1.0 is perfect, 0 means no overlap.
- **reference_pixels** (support): how many reference pixels belong to the class. Small support means a
  noisy IoU.
- **Pixel accuracy**: correct pixels ÷ all valid reference pixels, "other" included.
- **Mean IoU**: average IoU over wall, floor, ceiling, person, chair and sofa. "other" pixels stay in the
  matrix, so predicting e.g. wall on a bookshelf still lowers wall IoU. A class is left out of the mean only
  if its union is zero; the report lists the included classes.
- **Ignored pixels**: reference pixels whose colour could not be decoded; they are not scored.

These numbers come from consecutive frames of one development capture. They are **not** independent
held-out performance.

## Camera-stream provenance

`check_camera_streams.py` writes `outputs/camera_check_<date>_<time>/camera_stream_report.json` and
`alignment_step_*.png` images (semantic boundaries in red over the RGB frame).

Confirmed for Office/dynamic/Capture_1:
- `camera_0` and `camera` have 1490 common steps with identical sequence ID, timestamp, translation, rotation,
  intrinsics, projection, ego record and RGB basename at every step. The metadata names a different source
  RGB folder for each sensor.
- Only `camera_0` has semantic, instance and 2D box annotations; `camera` has only 3D boxes.
- At steps 0, 150 and 299 the on-disk RGB frames line up with the `camera_0` semantic labels: the edge-based
  shift search peaks at 0 or 1 px, within the method's resolution. `camera_0` instance masks match its
  2D boxes exactly (median IoU 1.0).

Still ambiguous:
- Which sensor rendered each on-disk RGB file cannot be proven: the folder is flattened, the basenames
  are shared, and both sensors have the same pose, so their renders would look the same.
- `check_camera_streams.py` projects 3D boxes with the *recorded* intrinsics, which are not pixel units (see
  the depth section). With the validated 60° intrinsics, `camera`'s 3D boxes project onto `camera_0`'s 2D boxes
  (median IoU about 0.72) and contain `camera_0`'s depth-mask points. That confirms shared geometry, not
  which sensor rendered each RGB file.

## Stage 2: 2D detection, tracking and segmentation association

```powershell
cd E:\RobotVisionWorkspace\robot_vision
.\.venv\Scripts\python.exe check_camera_streams.py --config configs\office.json --steps 0 150 299
.\.venv\Scripts\python.exe track_objects.py --segmentation-run outputs\seg_Office_dynamic_Capture_1_300f_20261010_032646 --frames 3 --device cuda
.\.venv\Scripts\python.exe track_objects.py --segmentation-run outputs\seg_Office_dynamic_Capture_1_300f_20261010_032646 --device cuda
.\.venv\Scripts\python.exe verify_tracking_run.py outputs\track_300f_<date>_<time>
```

- **Detector**: Ultralytics YOLO11n (`yolo11n.pt`, COCO classes), downloaded on first use to
  `robot_vision/models/` (ignored by Git). The SHA-256 is recorded in `tracking_summary.json`.
- **Tracker**: ByteTrack via `tracker="bytetrack.yaml"`, the Ultralytics default file. Its exact text is copied
  to `tracker_config.yaml` in every run. Detector inference runs on the selected device; the ByteTrack update
  runs on the CPU.
- **Baseline settings** (`configs/tracking_office.json`, or `--confidence`, `--nms-iou`, `--image-size`):
  confidence 0.10, NMS IoU 0.70, image size 640, batch size 1, all COCO classes.
- **Frames**: taken from the segmentation run's `manifest.jsonl` in its chronological order. Each frame's
  identifiers, timestamp and RGB file are re-checked against the dataset metadata, and segmentation masks
  are joined on `(sequence_id, sensor_id, step)`. Tracker state persists within a sequence and is reset at
  each new sequence and each new run (track IDs restart).
- Only tracks that ByteTrack reports are recorded. Detections that never become a confirmed track are not
  saved. Track IDs are not contiguous, because IDs are also allocated to tentative tracks.

### Tracking outputs (`outputs/track_<N>f_<date>_<time>/`)

| File | Content |
|---|---|
| `tracks.csv` | One row per tracked observation: sequence, camera, step, timestamp, track ID, COCO class ID/name, confidence, box `x1,y1,x2,y2` in original image pixels, validity/clipping flags, image size |
| `frames.jsonl` | One line per processed frame, including frames with no tracked objects |
| `object_segmentation_associations.csv` | Per observation: detector label and confidence, the pixel region used, and the share of each predicted segmentation class inside the box |
| `tracking_summary.json` | Counts, per-track class history, class-change warnings, integrity checks, settings, versions, weight hash, timings |
| `overlays/step_*.png` | Predicted segmentation, boxes, IDs, labels and timestamp (steps 0, 150, 299; all frames for runs of 10 frames or fewer) |
| `preview.mp4` | The same annotation for every frame (MPEG-4 Part 2, `mp4v`) |
| `tracker_config.yaml`, `run_status.json`, `COMPLETE` | Exact tracker configuration and run status |

**Segmentation proportions are bounding-box summaries.** The box is rounded outward to whole pixels and
clipped to the image. Background and overlapping objects inside the box contaminate the shares, so they
are neither instance masks nor a measure of object extent. The detector label is stored separately and is
not changed by them. Reference masks and reference object IDs are not used.

**Track IDs are not object counts.** One real object can receive several IDs (after occlusion or missed
detections), and one ID can drift between objects. A track's class can change between frames; such tracks
are listed under `class_change_warnings`.

**Video timing**: the playback rate is 1 / median timestamp difference (≈ 60.24 fps for this capture), and each
frame shows its recorded timestamp. The video is for viewing only. Use the timestamps in `frames.jsonl`,
never the video frame rate, for any motion measurement.

`verify_tracking_run.py` checks frame count and order against the manifest, the identifier join,
timestamps, box bounds, image sizes, duplicate `(sequence, camera, step, track ID)` observations, the
association arithmetic on a sample of boxes, and the video frame count. These are integrity checks, not a
detection or identity-accuracy evaluation; that is a separate future step.

## Stage 3: synthetic depth encoding and camera intrinsics (validated)

```powershell
cd E:\RobotVisionWorkspace\robot_vision
.\.venv\Scripts\python.exe validate_depth.py
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Result, recorded in `configs/depth_thud_synthetic.json` and used by `thud_depth.py`:

- **Depth**: `depth_m = raw / 65535 × 10.0`. The value is planar depth along the optical axis (Z), not distance
  along the pixel ray. `raw == 65535` means "10 m or more" and is treated as invalid. **Not millimetres.**
- **Intrinsics**: square pixels, vertical field of view 60°: `fx = fy = 265 / tan(30°) ≈ 459.0`, `cx = 365`,
  `cy = 265` for 730×530. The `camera_intrinsic` values in the metadata (1013.89 / 1520.83) are **not** pixel
  units; don't use them.

How it was established (`validate_depth.py`):
- **Evidence.** In each frame one sensor has instance masks and the other has 3D boxes in metres, with the
  same pose and timestamp. Each object's masked depth pixels are back-projected to 3D and tested against
  its 3D box.
- **Fit, then held-out test.** Far plane and field of view were fitted on Office/dynamic/Capture_1
  (9.97 m, 60.3°). The round values 10 m / 60° fit tighter and were tested unchanged on Office/dynamic/Capture_2,
  Office/static/Capture_1, Gym/dynamic/Capture_1 and Gym/static/Capture_1. The Gym scenes have the sensor
  roles swapped; the script detects the roles from the annotations.
- **Error estimate.** Chairs are 100% inside their boxes at 0 cm tolerance, desks 100% within 0.5 cm, and all
  Gym classes 100% within 2 cm. So combined depth + intrinsics error is within about 2 cm over roughly
  0.5–10 m, judged against Unity's boxes.
- **Rejected alternatives**: millimetres (0% inside), ray distance (25–42%), recorded intrinsics (6–16%).
  Projecting 3D boxes with the 60° intrinsics matches the 2D boxes (median IoU 0.71–0.82) vs about 0 with the
  recorded ones.
- **Known exception**: Office sofa boxes enclose only part of the sofa (about 44% inside). The overhang is
  one-sided and constant across hundreds of viewpoints, which points to an incomplete box annotation, not
  a depth error.

Outputs: `outputs/depth_check_<date>_<time>/depth_validation_report.json` and `depth_vs_3d_boxes.png`.

## Portable run folders

Run outputs never store absolute paths (`run_paths.py`). Paths are written as a root token plus a POSIX
relative path, and resolved against the roots configured on the machine reading them:

| Token | Root on the current machine |
|---|---|
| `{dataset_root}/Synthetic_Scenes/...` | `--dataset-root`, `THUD_DATASET_ROOT`, or `dataset_root` in `configs/office.json` |
| `{output_root}/track_300f_...` | `output_root` in the config (default `robot_vision/outputs`) |
| `{project_root}/configs/office.json` | the `robot_vision` folder |

Every JSON a run writes passes through the same function, so commands, notes and tracebacks are tokenised too.
A path outside every root is reduced to `<outside configured roots>/<file name>`.

Folders written before this rule are migrated without rerunning anything:

```powershell
.\.venv\Scripts\python.exe migrate_run_paths.py --all --dry-run   # list the files that would change
.\.venv\Scripts\python.exe migrate_run_paths.py --all
```
```bash
.venv/bin/python migrate_run_paths.py --all --old-dataset-root 'D:\RGB-D' --old-output-root 'E:\RobotVisionWorkspace\robot_vision\outputs' --old-project-root 'E:\RobotVisionWorkspace\robot_vision'
```

The second form migrates folders copied from another machine.
- Each original file is copied once to `<run>/_path_migration_backup/` and never overwritten.
- `path_migration.json` lists the changed files.
- Images are not touched.

All 11 run folders here were migrated (21 files). Every rewritten value resolves back to its original path.
Rerunning `verify_tracking_run.py` and a 3-frame `fuse_objects.py --check-only` on the migrated inputs passes,
and gives an `object_states.csv` byte-identical to the original.

## Continuous integration

`.github/workflows/tests.yml` (repository root) runs `python -m unittest discover -s tests -v` in `robot_vision/`
on `windows-latest` and `macos-latest` with Python 3.12, a CPU PyTorch build and `requirements.txt`. It runs on
push and pull request. The runners have no THUD data and no `outputs/`, so these tests skip:
- the dataset tests, because the configured dataset root does not exist there and `THUD_DATASET_ROOT` is not
  set;
- the run-folder checks, because there are no run folders.

## Data splits

Recorded in `configs/data_splits.json` and copied into every report:

| Capture | Split | Earlier use |
|---|---|---|
| Office/dynamic/Capture_1 | development | Stages 1–4, Step 8; Stage 3 depth/FOV fit |
| Office/dynamic/Capture_2 | adjustment: the only capture on which a parameter may be adjusted | Stage 3 held-out depth test; Step 8 v2 development (one full inference run) |
| Office/dynamic/Capture_3, Capture_4 | final evaluation: one run with a frozen config | not used |
| Gym/dynamic/Capture_2 – Capture_6 | cross-scene final evaluation: untouched cross-scene test | not used |
| Gym/dynamic/Capture_1 | excluded: not used for any evaluation | Stage 3 held-out depth test (reference masks vs reference 3D boxes; no model, fusion or motion output) |

The Gym/dynamic split was recorded on 2026-10-13, before any use of Capture_2 and before the motion config
was frozen. Gym/dynamic/Capture_1 was excluded on 2026-10-15, before any final evaluation, because its
Stage 3 use means it is not an untouched test capture.

**Guard.** `data_splits.guard()` runs in every script that reads a capture: `audit_dataset.py`,
`check_camera_streams.py`, `validate_depth.py`, `run_segmentation.py`, `track_objects.py`, `fuse_objects.py`
and `estimate_motion.py`.
- It refuses a final-evaluation capture unless `--final-evaluation` is passed, and refuses that flag on any
  other capture.
- It always refuses an excluded capture, even with `--final-evaluation`. Exclusions are checked first, so they
  win over a matching wildcard whatever the entry order in `data_splits.json`.
- `estimate_motion.py --final-evaluation` also requires the frozen motion config; see Step 8 v2.
- `validate_depth.py` no longer tests Gym/dynamic/Capture_1 by default. The recorded Stage 3 run did test it,
  before the split was declared.

## Stage 4: tracked-object 3D fusion (reference-depth baseline)

```powershell
.\.venv\Scripts\python.exe fuse_objects.py --check-only   # geometry checks + steps 0, 150, 299
.\.venv\Scripts\python.exe fuse_objects.py                # checks again, then all 300 tracked frames
```

**Depth source.** THUD reference depth (Unity render). Every result here is a *reference-depth fusion
baseline*; it says nothing about the accuracy of an RGB-only depth model.

**Prediction inputs, unchanged.** The 300-frame tracking run (YOLO11n + ByteTrack) and the SegFormer run it
references: boxes, track IDs, steps, timestamps and predicted grouped masks. Reference masks, boxes and object
positions are read only by the geometry checks and the evaluation.

**Geometry checks** (`geometry_checks.json`; the run stops before producing any positions if one fails):
- Tracked frames belong to the configured Office capture. RGB file name, step, timestamp, sequence and capture
  ID match the metadata. The tracked sensor is the labelled RGB sensor (`camera_0`).
- Depth, RGB and predicted mask have the same size. Depth edges coincide with RGB edges at zero shift.
- Depth encoding re-confirmed per frame: reference-instance points fall inside the 3D boxes when read as planar
  Z, but not when read as distance along the ray.
- Pose convention: `world = R(q) p_cam + t`, with `q` stored as `[x, y, z, w]`. Ego pose is identity, and both
  sensors share the pose. Static 3D boxes stay fixed in the world under this convention, and move by metres
  under the transposed one.

**Calibration actually used** (recorded in each run's `run_info.json`):
- Intrinsics: `fx = fy = 458.9935`, `cx = 365.0`, `cy = 265.0` for 730×530 px. Source: square-pixel pinhole from a
  60° vertical field of view, principal point at the image centre: `fy = (H/2) / tan(vfov/2)`, `fx = fy`,
  `cx = W/2`, `cy = H/2` (`configs/depth_thud_synthetic.json`, `thud_depth.pixel_intrinsics`).
- Back-projection of pixel (column `u`, row `v`; pixel centre at index + 0.5) with planar depth `Z`:
  `x = (u + 0.5 − cx)·Z / fx`, `y = −(v + 0.5 − cy)·Z / fy`, `z = Z`.
- World transform: `p_world = R(q)·p_cam + t`, with `q` the sensor rotation stored as `[x, y, z, w]` and `t` the
  sensor translation in metres. Ego pose is identity in this capture.
- Depth: `depth_m = raw / 65535 × 10.0`, planar Z along the optical axis. `raw = 65535` is invalid (at or beyond
  10 m). Evidence: reference-instance points fall inside reference 3D boxes (chairs 100% at 0 cm, desks 100%
  within 0.5 cm, Gym classes 100% within 2 cm). Millimetres put 0% inside, ray distance 25–42%.
- Field-of-view check: `fy = 458.99` with `cy = 265` gives `2·atan(cy/fy) = 60.0°`, Unity's default vertical
  camera field of view.
- Far plane: the fitted 9.966 m is within 0.34% of a round 10 m. The round value fits the held-out captures at
  least as well, so a 10 m depth range is the likely capture setting. It is not Unity's default far clip plane
  (1000 m), and the metadata does not state it, so this remains an inference from the fit.
- The metadata `camera_intrinsic` (1013.89 / 1520.83) was rejected because it is not in pixel units.
  Back-projecting with it puts only 6–16% of points inside their boxes. Projecting 3D boxes with it gives
  median IoU 0 against the 2D boxes, versus 0.72–0.82 with the 60° model.

**Parameters fitted on reference boxes.** Two were: the depth far plane (fitted 9.966 m, used 10.0) and the
vertical FOV (fitted 60.27°, used 60.0).
- The fit used **Office/dynamic/Capture_1**, the same capture Step 4 is evaluated on.
- The rounded values were then confirmed unchanged on four held-out captures: Office/dynamic/Capture_2,
  Office/static/Capture_1, and Gym dynamic and static. That is the independent evidence for the calibration.
- Step 4's inside-3D-box rates on Capture_1 are therefore **not** independent of the calibration.
- Nothing else was fitted. Pixel-selection rules, thresholds and the association IoU were set before the full
  run and were not tuned on reference data.

**What the checks do and do not show.**
- The static-box check verifies the pose convention: 3D boxes stay fixed to about 1 µm under `R(q)·p + t` and
  move by metres under the transpose. It does **not** show micrometre-level perception accuracy.
- Stored axes: `cam_x/cam_y/cam_z` are camera-frame metres (x right, y up, z forward; Unity, left-handed).
  `world_x/world_y/world_z` are Unity world metres with **y up**, so the ground plane is world x–z.
- With rendered reference depth, the estimate and the reference point come from the same depth map. So
  **visible-point error measures pixel-selection / segmentation error, not depth error.**

**What a position is.** For each tracked box, pixels are chosen from the *predicted* mask:
1. the detector's own class (person, chair, couch→sofa);
2. otherwise box pixels that are not wall, floor or ceiling;
3. otherwise the box is flagged invalid.

The estimate is the per-axis median of those pixels back-projected with depth. That is a point on the visible
object surface, not a 3D box centre. `object_states.csv` gives it in camera coordinates (x right, y up, z
forward) and world coordinates, plus validity flags. `floor_context` says whether predicted floor touches the
box's bottom edge. `bottom_height_above_floor_m` uses the floor height measured from predicted floor pixels.

**Evaluation** (`evaluation_report.json`, `association_evaluation.csv`):
- *Association.* Each frame, tracked boxes are matched to reference 2D boxes with a class-compatible label and
  IoU >= 0.5 (Hungarian).
- *Visible-point error.* Distance to the median of the reference instance mask back-projected with the same
  depth. Because the depth is the same, this isolates pixel-selection error.
- *3D-box test.* Only Chair, Desk and Sofa have 3D boxes in this capture; **people have none**.
- *World spread.* Spread of a static object's track position, compared with the same spread for the
  reference visible point.

Run `fuse_300f_20261011_042733` (300 frames, development capture):

| Summary | Result |
|---|---|
| Tracked observations / valid 3D positions | 1903 / 1793 |
| Associated with a reference object (valid position) | 1380 |
| Visible-point error, all classes: median / p90 | 0.07 m / 0.41 m |
| Static-object track spread in world: estimate vs reference visible point | 0.20 m vs 0.06 m |

Every associated class (rows sum to 1380):

| Reference label | Associated (valid) | Visible-point error n | median | p90 | With 3D box | Inside 3D box (+5 cm) |
|---|---|---|---|---|---|---|
| people | 546 | 546 | 0.023 m | 0.201 m | 0 | — |
| Chair | 379 | 369 | 0.129 m | 0.663 m | 369 | 94% |
| Computer | 328 | 328 | 0.063 m | 0.188 m | 0 | — |
| Sofa | 98 | 98 | 0.398 m | 0.602 m | 98 | 66% |
| Plants | 22 | 22 | 0.113 m | 0.138 m | 0 | — |
| Book | 7 | 7 | 0.053 m | 0.060 m | 0 | — |

Chair has 10 associated observations with no visible-point error, because their reference instance had
fewer than 20 valid-depth pixels.

**The 263 unmatched couch boxes** (10 tracks) are classified by the reference 2D box, of any label, that they
overlap most:

| Category | Boxes |
|---|---|
| Same label (Sofa), IoU < 0.5 (median 0.42) | 185 |
| Another label: Chair (41 of these with IoU ≥ 0.5, i.e. the detector called a chair a couch) | 48 |
| Same label, IoU ≥ 0.5, but that sofa was already matched to another couch track (duplicate box) | 30 |
| No overlap with any reference box | 0 |

**Timing and frame-to-frame world step.**
- Timing: 300 frames, median dt 0.0166 s (60.24 Hz), constant.
- Ground-plane (x–z) step between consecutive valid positions of one track:

| Group | Step pairs | Median | p90 | Max |
|---|---|---|---|---|
| People | 570 | 0.016 m | 0.026 m | 3.25 m |
| Static (Chair / Desk / Sofa) | 768 | 0.025 m | 0.234 m | 5.38 m |

- For static objects the true step is 0, so their step size is pure pixel-selection jitter. It is larger than a
  walking person's step, which is why Step 8 estimates velocity over a time window, not from adjacent frames.
- Groups come from each track's most frequent associated reference label, used for evaluation only.

Failure modes seen:
- The box-minus-background fallback can pick an object behind or in front of the target. This causes the
  multi-metre outliers.
- Predicted sofa pixels cover only part of the sofa.

The selection rules were fixed before the full run and were not tuned on these results.

Supplement (does not modify the fusion run):

```powershell
.\.venv\Scripts\python.exe report_step4.py --fusion-run outputs\fuse_300f_20261011_042733 --depth-validation-run outputs\depth_check_20261011_031941
```

It writes `outputs/step4_supplement_<date>_<time>/`:
- `step4_supplement.json` and `step4_report.md`: calibration, fitted parameters, per-class table, couch
  classification, timing.
- `couch_unmatched.csv`.

## Step 8: temporal motion (reference-depth and reference-camera-pose baseline)

Windows PowerShell:

```powershell
cd E:\RobotVisionWorkspace\robot_vision
.\.venv\Scripts\python.exe make_proxy_route.py --fusion-run outputs\fuse_300f_20261011_042733 --out configs\proxy_route_office_capture1.json
.\.venv\Scripts\python.exe estimate_motion.py --fusion-run outputs\fuse_300f_20261011_042733 --route-config configs\proxy_route_office_capture1.json
.\.venv\Scripts\python.exe report_motion.py --motion-run outputs\motion_300f_<date>_<time>
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

macOS Terminal:

```bash
cd /path/to/RobotVisionWorkspace/robot_vision
export THUD_DATASET_ROOT=/Volumes/Data/RGB-D
.venv/bin/python make_proxy_route.py --fusion-run outputs/fuse_300f_20261011_042733 --out configs/proxy_route_office_capture1.json
.venv/bin/python estimate_motion.py --fusion-run outputs/fuse_300f_20261011_042733 --route-config configs/proxy_route_office_capture1.json
.venv/bin/python report_motion.py --motion-run outputs/motion_300f_<date>_<time>
.venv/bin/python -m unittest discover -s tests -v
```

The fusion run must exist locally. `make_proxy_route.py` needs re-running only if the robot or load footprint
changes; `estimate_motion.py` refuses a corridor whose width disagrees with the one required width
(`footprint.load_footprint`, see Step 9).
- **Width change since Step 9 (2026-10-15).** The `proxy_route` files were regenerated with `make_proxy_route.py`
  at the required 1.00 m (Euro pallet). Only `width_m`, `width_rule` and `width_note` changed; the centrelines are
  identical.
  - The recorded Step 8 runs used the earlier 0.80 m (robot-only) files. Copies of those are kept in each run's
    `config_used/` and in git history.
  - The frozen motion config is not affected, because the route is a command-line input.
- **Step 8 route fields are proxies.** `route_label`, `route_status`, `dist_to_route_centreline_m`,
  `time_to_route_*` and `p_enter_route_within_horizon` in `motion_states.csv`, and the `proxy_route` `width_m`, are
  not read by Step 9 decisions. Decisions read only the `proxy_route` centreline.

Without `--route-config` every
route field is `not_evaluated`. The motion config holds settings only; the fusion run and corridor are
command-line inputs. On a final-evaluation capture the script refuses to run without `--final-evaluation`, and that
flag also requires the frozen config (see Step 8 v2).

**Baseline.** Positions are Step 4 visible-surface points, computed from THUD reference depth and the recorded
camera poses. Treat every result as a controlled experimental baseline.
- No inference is rerun; `object_states.csv` is reused.
- World positions already include camera-motion compensation (`p_world = R p_cam + t`), so camera movement is
  not subtracted again.

**Ground plane, checked from data.** Predicted-floor points have world y = −0.957 m. The within-frame IQR is
0.03 mm and the range across 300 frames is 0.02 mm, both well under the 2 cm limit. So y is vertical and the
ground plane is world x–z. The camera stays 1.219 m above the floor.

**Observation quality** (`configs/motion_office.json` → `quality`; no reference data):
- `pixel_source` is `class_mask`, `fallback` or `none`.
- An observation is `reliable` when its position is valid and the depth IQR of its selected pixels is ≤ 0.5 m
  (class mask) or ≤ 0.25 m (fallback).
- A larger spread means two surfaces, such as an occluder, so the observation is flagged unreliable. The
  nearest depth cluster is never picked instead.

**Motion.**
- Velocity is the least-squares slope of x(t) and z(t) over a **0.5 s trailing window** of reliable observations,
  using real timestamps. It needs at least 10 observations spanning 0.3 s; otherwise the status is
  `insufficient_history`.
- The line's value at the current time is the filtered position. Raw and filtered positions are both saved.
- **Window:** 0.5 s = 30.1 frame intervals at 60.24 Hz, so up to 31 observations (observed median 31). The
  minimum is 10 observations spanning 0.3 s (18 frames). The first estimate comes a median 0.32 s after a
  segment starts.
- **Delay:** for a changing velocity the estimate describes the window's mean time, about 0.25 s (15 frames) ago;
  the measured median is 0.249 s. Label persistence adds up to 0.2 s (12 frames), so a label can trail a real
  change by up to 0.45 s.
- **Resets** start a new segment when one of these happens: a gap over 0.2 s; a jump over 0.5 m + 3 m/s × dt;
  a detector class change.
- Uncertainty is the line-fit standard error. It assumes independent residuals, so it understates slow
  pixel-selection drift.

**Two separate measurements.**
- *World motion:* ground-plane speed and heading (`atan2(vx, vz)`). `motion_label` is one of:
  - `stationary` / moving, with hysteresis: moving at ≥ 0.35 m/s, stationary at ≤ 0.20 m/s.
  - For moving objects: `approaching` / `moving_away` when the **object's own** velocity component toward or away
    from `camera_proxy` is at least 0.2 m/s, otherwise `moving_lateral`.
  - A label must persist 0.2 s before it is emitted; otherwise `unknown`.
  - `moving_lateral` was added because a sideways-walking person is neither stationary nor approaching.
- *Relative motion:* `range_rate_mps` is d/dt of the ground-plane distance to `camera_proxy`. It is split into
  `range_rate_object_mps` and `range_rate_camera_mps`. `range_label` is `range_decreasing` / `range_increasing` /
  `range_steady`, with a ±0.2 m/s dead band.
- A stationary person whose distance shrinks because the camera moved is `stationary` + `range_decreasing`,
  never `approaching`.
- `camera_proxy` is the camera position. The camera-to-robot offset is not defined yet.

**Route.**
- Crossing and time-to-route are computed only when a corridor config is given; otherwise `not_evaluated`.
- For THUD the corridor is `proxy_route`: the recorded camera path, 0.80 m wide.
  - That width is the robot's 0.60 m + 2 × 0.10 m; the load is not measured yet, so it is a lower bound.
  - It is a test fixture built from reference poses, not a planned route.
- `time_to_route_s` is the first time a **constant-velocity** extrapolation of the filtered position enters the
  corridor, within a 5 s horizon.
  - p10/p90 and `p_enter_route_within_horizon` come from 200 Monte Carlo velocity samples.
  - **It is not a time to collision:** the corridor is static and the robot's own motion is not modelled.

**Evaluation** (reference used only here):
- Each reference instance has a visible-surface-point trajectory: the median of its instance-mask pixels,
  from reference depth and poses. Instance IDs are stable over time.
- Its velocity, from the same estimator, is a **proxy**, not the person-centre velocity.
- Tracks link to instances through the Step 4 per-frame association.

Accepted baseline run `motion_300f_20261013_210331` (development capture; code commit d247bba). The current run
`motion_300f_20261013_214008` (commit 5948eff) reproduces every value and adds the `reset_reason` and
`motion_trusted` columns.

| People (607 observations) | Result |
|---|---|
| Estimated / insufficient history / unreliable | 437 / 97 / 73 |
| Pixel source | class mask 549, fallback 49, none 9 |
| Reference-proxy speed (median) | 0.94 m/s (people are walking) |
| Speed error vs proxy: median abs / p90 abs / max | 0.013 / 0.096 / 1.28 m/s (435 pairs) |
| Heading error (both ≥ 0.3 m/s): median / p90 / max | 0.75° / 5.7° / 132° |
| `motion_label` agreement with proxy | 99.0% (386 pairs; 4 `moving_away` → `moving_lateral`) |
| `range_label` agreement | 97.9% |
| Identity | 4 people instances; one is split across 3 tracks, one across 2; 3 of 36 tracks switch reference ID (11 switches) |

**n_people = 4, and frames are highly correlated.** Frames are 1/60 s apart, and consecutive estimates share
most of their 0.5 s window, so the pair counts above overstate the independent evidence.

Per person (`report_motion.py`):

| Reference person | Tracks | Pairs | ~Independent 0.5 s windows | Abs speed error median / p90 / max | Heading error median / p90 / max | Label agreement |
|---|---|---|---|---|---|---|
| 36 | 1 | 244 | 8.1 | 0.010 / 0.024 / 0.04 m/s | 0.4° / 1.7° / 3° | 100% of 231 |
| 78 | 63, 191 | 181 | 7.7 | 0.035 / 0.117 / 0.33 m/s | 2.5° / 7.2° / 23° | 97% of 155 |
| 41 | 112, 173, 236 | 10 | 0.3 | 0.45 / 1.07 / 1.28 m/s | 128° / 131° / 132° | — |
| 45 | 137 | 0 (17 associated) | — | — | — | — |

- Person 41 is the weak case: about 10 m away, in short fragments.
- Person 45 has no motion pairs: all 17 positions are invalid, and its reference mask never has 50 valid-depth
  pixels.
- The overall averages are dominated by persons 36 and 78.

**Resets (71), by cause and detector class** (class before the reset):

| Cause | person | chair | couch | tv | laptop | remote | book | bench | Total |
|---|---|---|---|---|---|---|---|---|---|
| Class change | 2 | 9 | 8 | 9 | 8 | 6 | 5 | 2 | 49 |
| Position jump | 7 | 0 | 7 | 1 | 0 | 0 | 0 | 0 | 15 |
| Observation gap | 1 | 3 | 3 | 0 | 0 | 0 | 0 | 0 | 7 |

- **ID switch** is not a reset cause the system can observe. ByteTrack never reports a switch: a new ID starts a
  new track rather than resetting one.
- A class change is the inference-side sign of an identity problem. The commonest are tv ↔ laptop (16),
  chair ↔ couch (11) and remote ↔ book (10).
- Evaluation only: 22 resets keep the same reference object on both sides, and 49 are on unassociated
  observations. **None** coincides with a change of reference object.

**Time to route: inconclusive: 23 entries, ~0.22 s horizon, 5 s sequence.**
- The 23 entries that could be checked were only a median 0.22 s ahead. There, estimated − realized is a median
  0.014 s, max 0.042 s.
- The **265 censored cases** are reported separately: 38 `crossing_route` and 227 `not_crossing`. In each, the
  5 s horizon ran past the end of the sequence.
- No false alarm or miss was observed. This does not test time-to-route at useful look-ahead times.

Static-furniture control: the same estimator on objects whose true velocity is 0.

| Group | Estimates (tracks) | Speed median / p90 | False motion (labelled) | Reference proxy, same instances |
|---|---|---|---|---|
| Chair / Desk / Sofa, static verified in Step 4 | 123 (5) | 0.62 / 1.32 m/s | **100% of 67** | 0.27 m/s median, 46% false motion |
| Computer / Plants / Book, static assumed, not verified | 162 (4) | 0.04 / 0.70 m/s | 12% of 124 | 0.02 m/s, 12% |

**Reading the static control.** The estimator does **not** separate stationary furniture from moving objects:
- 50 of the 67 labelled static estimates come from chair track 212. Its predicted chair mask grows from about
  90 to about 25,000 pixels as more of the chair is segmented. The visible-surface median slides about 0.3 m,
  which reads as about 0.6 m/s "approaching". The reference point for that chair moves 0.03 m/s.
- Even the reference visible point moves (46% false motion), because it slides over large objects as the camera
  walks past.
- People give good results because the person mask is compact and stable: Step 4 visible-point error was
  0.02 m.
- **No setting was changed after these results.**

**Motion trust** (design decision, not tuning; `configs/motion_office.json` → `motion_trust`):
- `motion_trusted` is true only for an estimated motion of a detector class in `dynamic_classes` (default:
  `person`).
- Other classes keep their motion values, with `motion_trusted = false`. In the current run that is 437
  trusted person estimates, and 285 untrusted estimates (tv, chair, couch).
- **For Step 9:** decision rules use only trusted motion. Static obstacles enter decisions through the
  passage-width map, not through motion labels.
- **Why:** the furniture error is systematic drift, not noise. Two things cause it:
  - The predicted mask's coverage changes, as with chair track 212.
  - The visible-surface point depends on the viewpoint. Even the reference visible point shows 46% false motion.
- Both drifts follow the camera's path. A longer window averages noise but cannot remove drift that persists
  for seconds.

**Waiting for your confirmation (not started):** two candidate rules, to be developed only on the full Capture_2
in one inference run and then frozen:
- a mask-coverage-change rule;
- an uncertainty-scaled "moving" threshold.

Supplement: `outputs/motion_supplement_<date>_<time>/` holds `motion_supplement.json`, `motion_supplement.md` and
`resets.csv` (one row per reset).

Outputs in `outputs/motion_300f_<date>_<time>/`:

| File | Content |
|---|---|
| `motion_states.csv` | One row per tracked observation: quality fields, raw and filtered world position, velocity ± SE, speed, heading, window size/span/lag, resets and `reset_reason`, labels, `motion_trusted`, camera_proxy range and rates, route status, time-to-route p10/p90 |
| `motion_evaluation.json` | Baseline label, split, git commit, ground-plane check, definitions, coverage, evaluation |
| `reference_motion_eval_only.csv` | The reference-proxy estimates (evaluation only) |
| `birdseye_trajectories.png` | Camera path, proxy route corridor, person tracks (raw and filtered), reference proxies, static tracks |
| `speed_vs_time_people.png`, `speed_vs_time_static_control.png` | Speed vs timestamp against the proxy and the thresholds |
| `overlays/step_*.png` | Labels, speed ± SE, range trend, route status and projected velocity arrow (steps 45, 150, 299) |
| `run_info.json`, `config_used/` | Exact configs, git commit hash and dirty flag, versions, command |

## Step 8 v2: Capture_2 adjustment and frozen motion config

All results here remain a **reference-depth and reference-camera-pose baseline**.

### Rules declared before any Capture_2 use (`configs/motion_office.json`)
- **Heading error** is reported only where the *reference* speed is ≥ `heading_min_speed_mps` (0.3 m/s). Excluded
  pairs are counted.
- **Distance bins** are 0–3 m, 3–6 m and 6+ m, measured as the ground-plane distance from `camera_proxy` to the
  visible-surface point.
  - The distance uses any valid-depth pixels, so invalid positions are binned too.
  - `unknown` means the observation had no valid depth at all.
- **Time-to-route** is binned by estimated look-ahead: 0–1 s, 1–3 s and 3–5 s. Censored cases are reported
  separately.
- **Class vote** (`motion.class_vote_window_s` = 1.0 s): `motion_class` is the majority detector class of the track
  over the trailing second. It replaces reset-on-class-change, so resets come only from observation gaps and
  position jumps. It is used for `motion_trusted` and per-class reporting. Step 4 pixel selection is unchanged.
- **Mask-coverage-change rule** (`quality.coverage_change`): an observation is flagged `mask_coverage_change` if
  its selected-pixel count is more than 2× larger or smaller than that of any observation of the same track in
  the previous 0.25 s. Flagged observations do not update motion.
  - Because 0.25 s exceeds the 0.2 s gap limit, a step change also restarts the segment.
  - Gradual coverage changes slower than this are not caught.
- **Uncertainty-scaled moving threshold** (`labels.uncertainty_k`): an object is moving if speed − k·SE ≥ 0.35, and
  stationary if speed + k·SE ≤ 0.20; otherwise it keeps its previous state.
  - Decision rule, declared beforehand: adopt k = 2 only if, on Capture_2, it lowers the static-verified
    false-motion rate and costs at most 2 points of person label agreement.

### Capture_2: one full inference run (same models and settings as Capture_1)

| Run | Folder |
|---|---|
| SegFormer-b0, all 1388 frames | `outputs/seg_Office_dynamic_Capture_2_1388f_20261013_220700` (mean IoU 0.58) |
| YOLO11n + ByteTrack, `--device auto` → CUDA | `outputs/track_1388f_20261013_221603` (integrity checks passed) |
| Fusion (reference depth) | `outputs/fuse_1388f_20261013_222006` (geometry checks passed; 8617 of 8890 positions valid) |
| Proxy route | `configs/proxy_route_office_capture2.json` (14.42 m, 0.80 m wide) |

- **Capture size:** 1388 frames, 23.04 s, 60.24 Hz. 3 reference people appear in the 2D boxes.
- **Earlier tracking attempt:** an earlier `track_objects.py` attempt stopped before loading the detector. It
  re-read the Capture_1 metadata because the segmentation run had used `--capture`. That is fixed, and inference
  ran once.
- **Ground-plane check:**
  - The v1 rule needed every frame within 2 cm, and it failed on Capture_2. In 65 of 1237 frames, SegFormer
    labels desk tops as floor (about 0.70 m above it).
  - The axis check now needs ≥ 90% of frames within 2 cm of the median and lists the outliers. Capture_2 gives
    94.7%, Capture_1 100%.

### Results (frozen config, sha256 `15821ff9…1625`)

Capture_2 (adjustment). "Before" is the v1-equivalent settings; "after" is the frozen v2:

| Metric | v1-equivalent | Frozen v2 |
|---|---|---|
| People pairs (track + reference estimate) | 366 | 300 |
| People abs speed error median / p90 | 0.006 / 0.083 m/s | 0.005 / 0.025 m/s |
| People heading error median / p90 (excluded: ref speed < 0.3) | 1.3° / 3.0° (118) | 1.2° / 2.8° (108) |
| People motion-label agreement | 100% | 100% |
| Static verified (Chair/Desk/Sofa): estimates / false motion | 949 / 8.9% | 363 / 0% |
| Static unverified: false motion | 0% | 0% |
| Resets | 261 | 57 (54 gaps, 3 jumps) |
| Class changes between consecutive observations (detector → voted) | 303 | 36 |
| Observations flagged by the coverage rule | — | 3244 of 8890 (1859 made unreliable) |

Capture_2 per person, frozen v2. n_people = 3; frames are highly correlated:

| Person | Tracks | Pairs | ~Independent 0.5 s windows | Ref speed | Abs speed error median / p90 | Heading error median / p90 |
|---|---|---|---|---|---|---|
| 41 | 4, 382 | 141 | 4.6 | 0.24 m/s | 0.004 / 0.011 m/s | 0.9° / 1.8° |
| 45 | 2, 380, 455 | 134 | 4.4 | 0.73 m/s | 0.006 / 0.018 m/s | 1.3° / 2.6° |
| 78 | 773 | 25 | 0.9 | 1.03 m/s | 0.028 / 0.043 m/s | 1.1° / 3.8° |

Capture_2 by distance bin, frozen v2:

| Bin | Observations | Invalid positions | Estimated | People obs / invalid / pairs | People abs speed error median |
|---|---|---|---|---|---|
| 0–3 m | 5267 | 15 | 1432 | 352 / 0 / 275 | 0.004 m/s |
| 3–6 m | 3285 | 204 | 482 | 96 / 2 / 25 | 0.028 m/s |
| 6+ m | 337 | 53 | 0 | 32 / 14 / 0 | — |
| unknown (no valid depth) | 1 | 1 | 0 | 0 | — |

Nothing beyond 6 m reaches a motion estimate. Those positions are invalid, or fail the quality rules, mostly
through large depth spread.

**Time-to-route on Capture_2: inconclusive: 41 entries, ~0.48 s horizon, 23 s sequence.**
- 0–1 s look-ahead: 41 entered. Estimated − realized is a median −0.38 s, so entry is called early. 20 are
  censored.
- 1–3 s: 52, all censored. 3–5 s: none.
- 12 `not_crossing` cases are censored.
- Censoring here mostly means the person's reference visibility ended before the 5 s horizon.

**k decision.** On Capture_2, k = 2 gives the same static-verified false-motion rate as k = 0 (0%), and the same
person label agreement (100%). The declared rule therefore keeps **k = 0**. The k = 2 run is kept as the
evidence: `outputs/motion_1388f_20261013_223951`.

Capture_1 (development; no inference). Before and after, both from the current code:

| Metric | v1-equivalent (= accepted baseline) | Frozen v2 |
|---|---|---|
| People pairs | 435 | 391 |
| People abs speed error median / p90 | 0.013 / 0.096 m/s | 0.013 / 0.087 m/s |
| People heading error median / p90 | 0.75° / 5.7° | 0.73° / 4.9° |
| People motion-label agreement | 99.0% | 98.9% |
| Static verified: estimates / labelled / false motion | 123 / 67 / 100% | 4 / 0 / — |
| Static unverified: false motion | 12% | 0% |
| Resets | 71 | 8 (all gaps) |
| Person 41 (far, fragmented) pairs | 10 | 0 |

What the Capture_1 change means:
- The v1-equivalent run reproduces the accepted Step 8 `motion_states.csv` exactly.
- Under v2, the coverage rule removes chair track 212's growing mask almost entirely. Static furniture is
  therefore *not measured* on Capture_1 any more; this does not show it is fixed.
- On Capture_2 the static control still has 230 labelled estimates, at 0% false motion.

**Freeze.** `configs/motion_frozen.json` records:
- the SHA-256 of `configs/motion_office.json` (`15821ff9ad4ebf4c5c9eda5f33d36ffa4d2faf08a6c4418df92019ec52661625`);
- the Capture_2 decisions.

Every motion run records its config hash and whether it is frozen. `--final-evaluation` refuses any other
config. Captures 3–4 and Gym/dynamic have not been touched.

```powershell
.\.venv\Scripts\python.exe run_segmentation.py --capture Synthetic_Scenes/Office/dynamic/Capture_2 --all-frames
.\.venv\Scripts\python.exe track_objects.py --segmentation-run outputs\seg_Office_dynamic_Capture_2_1388f_20261013_220700
.\.venv\Scripts\python.exe verify_tracking_run.py outputs\track_1388f_20261013_221603
.\.venv\Scripts\python.exe fuse_objects.py --tracking-run outputs\track_1388f_20261013_221603 --capture Synthetic_Scenes/Office/dynamic/Capture_2
.\.venv\Scripts\python.exe make_proxy_route.py --fusion-run outputs\fuse_1388f_20261013_222006 --out configs\proxy_route_office_capture2.json
.\.venv\Scripts\python.exe estimate_motion.py --fusion-run outputs\fuse_1388f_20261013_222006 --route-config configs\proxy_route_office_capture2.json
.\.venv\Scripts\python.exe report_motion.py --motion-run outputs\motion_1388f_<date>_<time> --before-run outputs\motion_1388f_<v1-equivalent run> --label adjustment
```

On macOS, use `.venv/bin/python` and forward slashes, and set `THUD_DATASET_ROOT`.

## Step 9: decision rules (MOVE / STOP / WAIT)

Windows PowerShell:

```powershell
cd E:\RobotVisionWorkspace\robot_vision
.\.venv\Scripts\python.exe -m unittest tests.test_decision -v
.\.venv\Scripts\python.exe run_decisions.py --all-scenarios
.\.venv\Scripts\python.exe person_box_depth.py --motion-run outputs\motion_1388f_20261013_223619
.\.venv\Scripts\python.exe replay_decisions.py --motion-run outputs\motion_1388f_20261013_223619 --route-config configs\proxy_route_office_capture2.json --script configs\replay_script_office_capture2.json --person-depth-run outputs\person_box_depth_511obs_20261015_220051
```

macOS Terminal:

```bash
cd /path/to/RobotVisionWorkspace/robot_vision
.venv/bin/python -m unittest tests.test_decision -v
.venv/bin/python run_decisions.py --all-scenarios
.venv/bin/python person_box_depth.py --motion-run outputs/motion_1388f_20261013_223619
.venv/bin/python replay_decisions.py --motion-run outputs/motion_1388f_20261013_223619 --route-config configs/proxy_route_office_capture2.json --script configs/replay_script_office_capture2.json --person-depth-run outputs/person_box_depth_511obs_20261015_220051
```

The tests and `run_decisions.py` need no dataset. `replay_decisions.py` needs only the local Step 8 and Step 4 run
folders. `person_box_depth.py` also reads the capture's depth images from the dataset root. No inference is rerun.

### Input contract (`decision.py`)

A caller builds one `DecisionFrame` per timestamp and passes it to `DecisionEngine.step()`. THUD replays and,
later, Unity frames use the same code; only the providers differ.

| Dataclass | Fields |
|---|---|
| `PersonState` | `track_id`, `timestamp`, `position_xz` (ground plane, or None), `distance_m`, `motion_label`, `velocity_xz` (or None), `motion_trusted`, `distance_lower_bound_m` (or None; used only for a person without a position) |
| `PassageState` | `status` (clear / too_narrow / blocked / unknown / not_evaluated), `available_width_m` (or None), `required_width_m` |
| `GestureEvent` | `timestamp`, `track_id` (or None), `gesture` (STOP / MOVE / NONE), `confidence` |
| `RouteCorridor` | `centreline_xz` (polyline in travel order), `width_m`, `label` |
| `DecisionFrame` | `timestamp`, `persons`, `passage`, `gestures`, `robot_xz` (or None: the whole corridor counts as ahead) |

- **Providers** (`decision_io.py`): `persons_at(t)`, `passage_at(t)`, `gestures_at(t)`.
  - Step 6 and the gesture module are not connected yet. `ScriptedPassage` and `ScriptedGestures` are placeholders
    that read scenario or script files.
  - The real gesture module will connect later through an adapter that outputs `GestureEvent`. The gesture
    module's own code is not touched.
- **Scenario files** (`tests/scenarios/*.json`) are plain JSON: corridor, time grid, robot position, person /
  passage / gesture segments, and expected decisions. Each one also lists the config values its timing assumes
  (`config_assumptions`); a test fails if `decision.json` no longer matches them.

### Changes after the replay demo (design decisions, not tuning)

All of these were made on 2026-10-15 by the project owner, in two reviews of the Capture_2 replay demo, and
before any evaluation. They were not tuned on any result, and no decision result is a measurement.

| Review | Change | Before | Now |
|---|---|---|---|
| 1 | Look-ahead | Rule 1 used the whole corridor ahead. In the demo, a person 6.70 m ahead on the route caused STOP | Rule 1 applies only inside the **stop zone**: the corridor within `look_ahead_m` = 3.0 m. Rule 2 predicts entry into the stop zone |
| 1 | Robot speed | not configured | `robot.json`: `max_speed_mps` 1.0, `decel_mps2` 0.5 |
| 1 | Load | 0.70 m tray, required width 0.90 m | Centred Euro pallet (1.20 × 0.80 m, 0.80 m side across travel): required width **1.00 m** |
| 1 | Required width | Computed in `decision.py`; Step 8 used its own robot-only rule; the engine widened narrower corridors | One function, `footprint.required_width`, reached through `footprint.load_footprint`. Used by decisions, `make_proxy_route.py` and the `estimate_motion.py` corridor check. A corridor of any other width is refused |
| 2 | Caution band | `caution_ahead_m` = 3.0 m, equal to the look-ahead, so no corridor lay in the caution zone beyond the stop zone | `caution_ahead_m` = robot stopping distance + `person_speed_mps` × robot stopping time = 1.5 + 1.4 × 2.5 = **5.0 m** |
| 2 | Unlocated person | Released by `distance_m` > caution distance, where `distance_m` is a median | Released only by `distance_lower_bound_m` > caution distance. This is the 5th percentile of valid depths in the person's box. No valid depth → no release |
| 2 | STOP gesture hold | `stop_hold_frames` = 3 (accepted on the 3rd event: 0.03 s at 60 Hz, 0.2 s at 10 Hz) | `stop_hold_s` = 0.2 s, independent of the frame rate |
| 2 | Proxy routes | 0.80 m (robot only) | Regenerated at 1.00 m with `make_proxy_route.py`; centrelines unchanged |

Fixes found while checking the replays. These are implementation errors, not rule changes:
- **Zone end at the route end (`cc89948`).** The flat zone end was also applied where the route itself ends, so a
  person just past the end of a short remaining route was outside every zone. The zones now stay round there.
- **Reason text (`5ffd04e`).** A person inside the corridor beyond the stop zone was described as "−0.03 m from
  corridor edge". The reason now reads "inside the corridor beyond the stop zone, X m ahead".
- **Absolute path (`5ffd04e`).** `person_box_depth.py` copied `office.json` raw, which put the absolute dataset root
  into its run folder; `test_run_paths` caught this. The script now writes portable paths. The one affected folder
  was rewritten with `migrate_run_paths.py`; the original is in `_path_migration_backup/`.
- **Correction of an earlier statement.** The first review said the median exception "released each" of the 16
  replay observations without a valid position. That count came from `motion_states.csv`, not from the engine.
  - In the engine, 14 of the 16 (track 2, steps 6–31) still had a remembered valid position from less than 1 s
    earlier. They were assessed with it, and the unlocated rule did not apply to them.
  - The rule applied to 2 assessments (track 773, steps 765–766). The median (8.96 and 8.94 m) released both.
    The decision was STOP rule 3 anyway, because of the scripted STOP gesture.

### Required width (configured, not measured)

`required_width_m` = (furthest right − furthest left extent of robot and load, measured from the robot centre
line) + 2 × `safety_margin_per_side_m`. It is computed only by `footprint.required_width`.
- **Robot:** `configs/robot.json`, 0.60 m wide and centred, with a margin of 0.10 m per side.
- **Load:** the file `robot.json` names (`configs/load.json`). It is a Euro pallet carried with its 0.80 m side
  across travel, centred (offset 0.00 m), labelled **"configured, not measured"**. `length_m` (1.20 m) is recorded
  but not used by any rule yet.
- **Configured result:** extents −0.40 to +0.40 m, so 0.80 + 0.20 = **1.00 m**.
- **Tested examples:**
  - the same pallet at +0.20 m: extents −0.30 to +0.60 m, so 1.10 m (likewise mirrored to the left);
  - a load narrower than the robot: 0.80 m;
  - no load: 0.80 m.
- **Corridor width.** The decision corridor width must equal `required_width_m`. The `proxy_route` files are now
  1.00 m too, but decisions read only their centreline. Decisions never read the Step 8 route fields in
  `motion_states.csv`; those stay labelled as proxies.

### Look-ahead, caution distance and zones

| Quantity | Formula | Inputs | Value |
|---|---|---|---|
| `look_ahead_m` | v × reaction_s + v² / (2 × decel) + buffer_m | v 1.0 m/s, decel 0.5 m/s² (robot.json); reaction_s 0.5 s, buffer_m 1.5 m (decision.json) | 0.5 + 1.0 + 1.5 = **3.0 m** |
| stopping distance | v × reaction_s + v² / (2 × decel) | as above | 0.5 + 1.0 = 1.5 m |
| stopping time | reaction_s + v / decel | as above | 0.5 + 2.0 = 2.5 s |
| `caution_ahead_m` | stopping distance + person_speed_mps × stopping time | person_speed_mps 1.4 m/s (decision.json) | 1.5 + 1.4 × 2.5 = **5.0 m** |

- **Stored values.** `decision.json` stores both formulas, their inputs and the computed values (`look_ahead`,
  `caution_ahead`).
- **Checks.** `footprint.look_ahead` and `footprint.caution_ahead` recompute the values and refuse a stale one.
  Loading also refuses `caution_ahead_m` < `look_ahead_m`.
- **Stop zone.** The corridor from the robot's projected position to `look_ahead_m` ahead, with a flat far end.
  The near end is round, which covers the robot body. Where the route itself ends sooner, that end is round too.
- **Caution zone.** Outside the stop zone, within `caution_lateral_m` (1.0 m) of the corridor edge, up to
  `caution_ahead_m` (5.0 m) ahead, with a flat far end. It includes the corridor itself between 3.0 m and 5.0 m.
  For people standing in the corridor:
  - untrusted at 4.5 m → STOP (rule 4);
  - trusted stationary at 4.5 m → no STOP;
  - untrusted at 5.5 m → no STOP.
- **Rule 2 prediction.** The person's constant velocity is checked against the current stop zone, sampled every
  0.05 s up to `entry_horizon_s` (3.0 s).
  - This covers sideways entry and head-on approach.
  - Robot motion is not added, because it is what the look-ahead (reaction, braking and buffer) covers.
  - The reason gives the gap to the stop zone and the closing speed (gap ÷ time to entry).
  - It is not a time to collision.

### Rules (checked top-down; the first match wins)

| # | Condition | Decision | Reason (example) |
|---|---|---|---|
| 1 | Person inside the stop zone (latest valid position; no motion needed) | STOP | `person in route: track 1 0.20 m from centre line, 2.50 m ahead (stop zone 3.00 m)` |
| 2 | Person predicted to enter the stop zone within `entry_horizon_s` (trusted motion only) | STOP | `person entering stop zone: track 21 predicted to enter in 2.00 s (within 3.0 s), 2.00 m away, closing at 1.00 m/s` |
| 3 | Valid STOP gesture from anyone | STOP | `STOP gesture: track 7 (confidence 0.90, held 0.20 s)` |
| 4 | Person in the caution zone without trusted motion | STOP | `cannot confirm person's movement: track 30 in caution zone (inside the corridor beyond the stop zone, 4.50 m ahead), motion untrusted` |
| 5 | Passage blocked / unknown / not_evaluated | WAIT | `cannot confirm passage is clear: status unknown` |
| 6 | MOVE requested but passage too narrow | STOP | `load too wide: 0.85 m available, 1.00 m needed` |
| 7 | Valid MOVE held for `move_hold_s` and passage clear | MOVE | `passage clear: 1.50 m available, 1.00 m needed` |
| 8 | Otherwise | WAIT | `waiting for instruction` |

Definitions (also in `configs/decision.json` → `conventions`):
- **Corridor.** Only the part of the route from the robot's projected position onwards counts. A person behind
  the robot is not "in route".
- **Trusted motion.** All of the following must hold; otherwise motion counts as unknown:
  - `motion_trusted` is true;
  - the label is not `unknown` or `insufficient_history`;
  - there is a velocity and a current position;
  - `distance_m` ≤ `motion_range_m` (6.0 m).
- **Person memory.** A tracked person who drops out, or whose position becomes invalid, keeps the latest valid
  position for `person_memory_s` (1.0 s). It still counts for rule 1 and the caution zone (reason:
  `(remembered position)`). `person_memory_s` equals `resume_hold_s` (1.0 s), so after a dropout nothing is released
  for at least memory + resume hold = 2 s.
- **STOP overrides MOVE.** Any current STOP gesture cancels every MOVE gesture, even before it is accepted, so a
  STOP from one person always overrides a MOVE from another. While the STOP is unconfirmed the result is WAIT
  (rule 8); once accepted, it is STOP (rule 3).
- **Passage consistency.** These cases are not taken at face value:
  - `clear` without a width → unknown;
  - `clear` with a width below `required_width_m` → too_narrow;
  - a passage evaluated for a different required width → unknown.

### A person without a position ("unlocated")

A person is detected but has neither a current nor a remembered ground-plane position. They count as **in the
caution zone** unless `PersonState.distance_lower_bound_m` is greater than `caution_ahead_m` (5.0 m). `distance_m`
(a median in THUD) is never used for this.
- **THUD (`person_box_depth.py`, reference-depth baseline).** The lower bound is the 5th percentile
  (`decision.json` → `unlocated_distance.box_depth_percentile`) of the valid planar depths inside the person's
  detection box.
  - Background and other objects in the box only add depths, so low percentiles stay at or below the person's own
    depth: errors go in the safe direction.
  - The recorded camera pitch and roll are exactly 0 in every frame (checked: max |qx| = max |qz| = 0), so the
    ground distance from the camera is at least the planar depth.
  - Saturated pixels are invalid. A box without valid depth gets no lower bound, so the person stays in the
    caution zone.
  - Only predicted boxes (Step 4) and depth images are read; no annotations or reference masks.
- **Unity (later).** The scene adapter must supply its own lower bound, or None.
- **Check.** In 1 of 511 person boxes, the 5th percentile is above Step 4's selected-pixel median, by 0.15 mm (a
  close person filling the box).
- **Replay result.** Of the 16 person observations without a valid position, **none is released now**.
  - 14 are assessed with a remembered position (unchanged).
  - 2 are unlocated (track 773, steps 765–766): lower bounds 3.85 and 3.83 m, below 5.0 m, so both are kept in
    the caution zone.
  - Before this change, the median (8.96 and 8.94 m) released both.

### Timing (`configs/decision.json`)

| Setting | Value | Meaning |
|---|---|---|
| `stop_hold_s` | 0.2 s | STOP gesture accepted after being held 0.2 s |
| `move_hold_s` | 0.5 s | MOVE gesture accepted after being held 0.5 s |
| `gesture_timeout_s` | 0.5 s | a gesture older than this counts as NONE; a gesture is held while its events arrive at most this far apart |
| `gesture_min_confidence` | 0.6 | below this a gesture counts as NONE |
| `resume_hold_s` | 1.0 s | MOVE only after the rule-7 conditions hold continuously for 1 s |

- **Asymmetric switching.** Switching to STOP takes effect at once. Switching to MOVE, from any non-MOVE state
  including the first start, needs `resume_hold_s`. During that hold the output is WAIT (rule 8) with the hold
  progress in the reason.
- **Provenance.**
  - The first version's values were declared on 2026-10-15 before any decision run, chosen from physical
    reasoning (`decision.json` → `why`).
  - The changes in the table above came after the replay demo.
  - Nothing has been tuned, and nothing has been evaluated.

### Outputs

Each run writes a new folder; existing folders are never overwritten.
- `person_box_depth.py` → `outputs/person_box_depth_<N>obs_<date>_<time>/`:
  - `person_box_depth.csv`: box, valid-depth pixel count, depth percentile and box median per person observation;
  - `run_info.json`: git commit, config hashes, pitch/roll check, coverage;
  - `config_used/`.
- `run_decisions.py` → `outputs/decisions_scenarios_<date>_<time>/`:
  - `run_info.json`: git commit, config hashes, footprint, look-ahead and caution distance;
  - `config_used/`: decision.json, robot.json, load.json;
  - `summary.json`: expectation check per scenario;
  - one subfolder per scenario, holding the scenario file, `decisions.csv` and `decision_log.json`.
- `replay_decisions.py` → `outputs/decisions_replay_<N>f_<date>_<time>/`: the same files plus the route, script
  and frozen-motion records in `config_used/`, and `decision_timeline.png`. Give `--person-depth-run` to supply the
  lower bounds; without it, unlocated people always count as in the caution zone.
- **`decisions.csv`** has one row per timestamp: decision, rule, rule name, plain-English reason with numbers,
  contributing track IDs, passage status (input and effective), widths, person counts and active gestures.
- **`decision_log.json`** holds the same records with a full snapshot of the inputs: every person's assessment,
  including stop-zone and caution-zone membership, gap, closing speed and lower bound, plus the passage and the
  gesture state.

### Tests (`tests/test_decision.py`, no dataset)

- One scenario per rule: `rule1_…` to `rule8_…`.
- Conflicts:
  - `conflict_stop_vs_move`: STOP vs MOVE from different people;
  - `conflict_person_in_route_with_move`;
  - `conflict_narrow_passage_with_move`.
- Gestures: `gesture_timeout` and `gesture_low_confidence`.
- Timing and motion: `asymmetric_timing`, `unknown_motion` and `beyond_motion_range`.
- Zones: `look_ahead_boundary`, `head_on_approach`, `caution_band` and `unlocated_person`.
- Look-ahead and caution unit tests:
  - both formulas, and stale declared values are refused;
  - `caution_ahead_m` ≥ `look_ahead_m` is enforced;
  - in route at `look_ahead_m` − 0.1 m → STOP;
  - at `look_ahead_m` + 0.1 m, standing still → not STOP;
  - in the corridor at 4.5 m: untrusted → STOP, trusted stationary → not STOP; untrusted at 5.5 m → not STOP;
  - head-on approach from 5 m → STOP (rule 2) while the person is still outside the stop zone;
  - sideways entry, with the gap reported;
  - the flat stop-zone end, and a round end where the route ends.
- Width unit tests:
  - Euro pallet maths (centred, off-centre left/right, narrow load, no load);
  - `required_width` is defined only in `footprint.py`;
  - a corridor of any other width is refused.
- Other unit tests:
  - the unlocated-person exception uses only the lower bound (a far median releases nothing);
  - the STOP hold is accepted at 0.2 s at 10, 60 and 240 Hz;
  - partial-polyline geometry;
  - a person behind the robot;
  - a passage evaluated for a different width;
  - monotonic timestamps.
- Isolation checks:
  - `decision.py` and `footprint.py` import only the standard library;
  - no Step 9 file, including `person_box_depth.py`, imports a reference loader;
  - output files are written;
  - an existing run folder is never reused.

Scenario run: `outputs/decisions_scenarios_20261015_220230` (commit `5ffd04e`). All 20 scenarios pass. Earlier
scenario runs are superseded: `…_212507`, `…_214114`, `…_214223` and `…_220051`.

### Demo: replay with placeholder passage and gestures (not an evaluation)

The demo replays the frozen Step 8 motion run on Office/dynamic/Capture_2 (adjustment split):
`outputs/motion_1388f_20261013_223619`, config sha256 `15821ff9…1625`, checked by the script.
- **People:** Step 8 motion output, a reference-depth and reference-camera-pose baseline.
- **Lower bounds:** from `outputs/person_box_depth_511obs_20261015_220051`.
- **Corridor:** the `proxy_route` centreline at the required 1.00 m.
- **Robot position:** `camera_proxy`. The stop zone is 3.0 m and the caution distance 5.0 m.
- **Passage:** a placeholder, "clear, 1.50 m". This is scripted, not measured.
- **Gestures:** scripted. A MOVE runs from 0.5 s to the end; a second gesturer shows STOP from 12.0 to 13.0 s.
- **Output:** `outputs/decisions_replay_1388f_20261015_220231` (commit `5ffd04e`), including `decision_timeline.png`.
- **Superseded runs:**
  - `…_212508` and `…_212612` (first version);
  - `…_214115` (route-end bug);
  - `…_214224` (first review);
  - `…_220052` (same decisions as `…_220231`, older reason text).

| Decision (of 1388 frames) | First version (`…_212612`) | First review (`…_214224`) | Second review (`…_220231`) |
|---|---|---|---|
| STOP rule 1 person in stop zone | 237 (17.1%) | 185 (13.3%) | 185 (13.3%) |
| STOP rule 2 entering stop zone | 64 (4.6%) | 64 (4.6%) | 64 (4.6%) |
| STOP rule 3 STOP gesture | 89 (6.4%) | 89 (6.4%) | 78 (5.6%) |
| STOP rule 4 movement unconfirmed | 154 (11.1%) | 191 (13.8%) | 204 (14.7%) |
| MOVE rule 7 | 590 (42.5%) | 605 (43.6%) | 592 (42.7%) |
| WAIT rule 8 (MOVE held / resume hold) | 254 (18.3%) | 254 (18.3%) | 265 (19.1%) |

What changed in the second review:
- **4.08 s:** STOP starts with rule 4 for track 382, inside the corridor 3.41 m ahead (in the new caution band). In
  the first review it started 0.2 s later, at 4.30 s.
- **12.0 s:** the scripted STOP gesture is now accepted after 0.22 s (12.22 s) instead of 3 frames (12.03 s). The
  WAIT in between comes from the rule that an unconfirmed STOP cancels every MOVE.
- **Unchanged:** the later events, namely rule 2 then rule 4 for track 455 (8.1–10.2 s) and rule 4 for track
  1440 at 21.6 s.

None of this is a correctness measurement: there is no decision ground truth, and the passage and gestures are
scripted.

## Gesture adapter

**Credit.** The gesture module is by anisha274 (https://github.com/anisha274/media_pipe_gesture), distributed
under the MIT licence as stated in its README (the repository has no separate LICENSE file at the pinned commit).
It is a git submodule at `external/media_pipe_gesture`, pinned at commit
`180e27962117611cc3e0ec0433a3202765cefd0f` (2026-10-08). Its code and model are not modified; the adapter uses
the same model file (`gesture_recognizer.task`, sha256 `97952348…0482`, checked when the recognizer is created) and
the same mapping as her `gesture_heuristics.py`.

After cloning this repository: `git submodule update --init` (from the repository root).

**MediaPipe.** `mediapipe==1.1.1` is in `requirements.txt` and installs into our Python 3.12.14 venv next to
numpy 2.5.2 (unchanged). Its wheels are tagged `py3-none` with no `requires_python`, so the package does not
restrict the Python version; wheels exist for Windows x64/arm64, macOS arm64 and Linux x64/arm64, not Intel macOS.
On Intel macOS the requirement is skipped by an environment marker.

**MediaPipe is optional for the rest of the pipeline.** It is imported only inside
`gesture_adapter.GestureRecognizerAdapter` (and nowhere else), so every other module, including the adapter's
geometry, mapping and ownership functions, imports and runs without it. Creating the recognizer without MediaPipe
raises an ImportError that says so. `tests/test_gesture_adapter.py` checks both: no other file imports mediapipe,
and every module imports with mediapipe blocked.

**OpenCV: two packages, one `cv2`.** ultralytics 8.4.175 requires `opencv-python` and mediapipe 1.1.1 requires
`opencv-contrib-python`; both install the same `cv2` module, so neither can be dropped (pip would reinstall it).
Both are pinned to 5.0.0.93. **Never upgrade one without the other.** `tests/test_opencv.py` checks that the two
pins are equal, that the installed packages and `cv2.__version__` match them, that every `cv2` name used in
`robot_vision/*.py` exists, and that those functions work.

**Mapping** (`configs/gesture.json` → `mapping`, citing her file and commit):

| MediaPipe category (top category of each hand) | Gesture |
|---|---|
| `Open_Palm`, `Closed_Fist` | STOP |
| `Pointing_Up`, `Victory`, `Thumb_Up` | MOVE |
| `Thumb_Down`, `ILoveYou`, `None`, any other; no hand | NONE |

**Recognizer.** IMAGE running mode (her code: LIVE_STREAM), frames never mirrored (her code mirrors the webcam).
`min_hand_detection_confidence` and `min_hand_presence_confidence` stay at her 0.5: they are MediaPipe's hand
detector settings, not a gesture threshold. The canned classifier's `score_threshold` stays unset.

**Modes** (`configs/gesture.json` → `modes`, declared before any gesture run):
- `full_frame` (her approach, baseline): the whole frame, `num_hands` 1 as in her code.
- `person_crop`: per tracked person, the upper 0.6 of the box plus a margin of 0.1 × box height on every side,
  clipped to the image, resized so the longer side is 256 px (aspect kept); `num_hands` 2. Reasons for each value
  are in the config (`why`).

**One owner per hand** (`configs/gesture.json` → `assignment`, same rule in both modes). Added after the first
smoke run, before any evaluation (disclosed in the config):
1. **Duplicates.** Overlapping crops can find the same hand. Hands whose boxes, in full-image pixels, overlap with
   IoU ≥ `duplicate_hand_iou_threshold` (0.5) are one hand; the highest-scoring copy is kept and the others are
   listed in its `duplicates` field.
2. **Candidates.** The persons whose crop region contains the wrist, plus the persons whose crop found the hand.
3. **Depth.** The candidate whose `depth_m` best matches the depth at the wrist (median of valid depths in a 5 × 5
   window) owns the hand, if that gap is ≤ `depth_match_max_m` (0.8 m) and the next candidate's gap is larger by
   ≥ `depth_margin_m` (0.3 m). The caller supplies the depth image and person depths (THUD: planar reference depth
   and Step 4 person depth, a reference-depth baseline; Unity: the scene adapter).
4. **Fallback.** Otherwise the person whose box contains the wrist, if exactly one box does; otherwise none
   (`track_id` null, `ambiguous` or `no_containing_box`).

In `person_crop`, a cropped person who owns no hand gets one NONE detection (`no_hand`, or `no_owned_hand` when
their crop's hands went to someone else or to nobody).

**Effect on decisions.** The current decision rules are unaffected by who owns a hand: rule 3 stops for an
accepted STOP from any track (including null), and any current STOP cancels every MOVE. Ownership enters only
through the per-track hold timing: a hand whose owner changes between frames restarts its hold, which can delay
acceptance but never makes it earlier. **Evaluation needs one owner per hand**: the per-person accuracy in
`gesture_eval.py` would count a duplicated hand once for each person.

**Output.** Every hand is a `GestureDetection`: timestamp, frame_id, mode, track_id, gesture, raw_category, raw
confidence (category score), hand box and wrist in full-image pixels, handedness, assignment (`depth`,
`wrist_in_single_box`, `ambiguous`, `no_containing_box`), crop box, wrist depth, candidates and merged duplicates.
A frame without a hand (`full_frame`) gives one NONE detection with confidence null. **No
confidence threshold is applied in the adapter**; `gesture_min_confidence` lives only in `decision.json`.
`to_gesture_events()` gives one `decision.GestureEvent` (reused, not redefined) per track_id per frame: STOP if any
detection of that track is STOP, else MOVE, else NONE, with the highest raw score of the chosen gesture. This is
needed because the decision's gesture filter keeps one state per track; preferring STOP keeps the safe direction.

**Tests** (`tests/test_gesture_adapter.py`, no dataset): the mapping table, and the mapping equals the lists in
her file (when the submodule is checked out; CI checks it out); crop geometry box → crop → image coordinates,
including clipping and resize invariance; the wrist rule (inside, edge, none, ambiguous); duplicates and owners
(box IoU, one hand from two crops kept once and owned by depth, the farther person chosen by depth, a depth tie
or too-large gap falling back to the wrist rule, a person without depth, two different hands kept, the depth
window); MediaPipe imported only lazily and the pipeline importing without it; NONE
handling (no hand, `None` / `Thumb_Down` categories keep their raw score); one event per track with STOP first;
no adapter file defines a confidence threshold and `gesture.json` has no gesture threshold key; the adapter
imports no reference loader and no evaluation code; the model hash; a blank frame gives NONE in both modes.

Windows PowerShell:

```powershell
cd E:\RobotVisionWorkspace
git submodule update --init
cd robot_vision
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m unittest tests.test_gesture_adapter -v
.\.venv\Scripts\python.exe gesture_smoke.py
.\.venv\Scripts\python.exe gesture_eval.py
```

macOS Terminal:

```bash
cd /path/to/RobotVisionWorkspace
git submodule update --init
cd robot_vision
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m unittest tests.test_gesture_adapter -v
.venv/bin/python gesture_smoke.py
.venv/bin/python gesture_eval.py
```

**Smoke test (not an evaluation).** `gesture_smoke.py` runs both modes on the images in `sample_images/gesture`
(git-ignored; `--image-dir` overrides it). Person boxes come from the Stage 2 detector settings
(`configs/tracking_office.json`), image by image, without tracking (`det<k>`). Output:
`outputs/gesture_smoke_<N>img_<date>_<time>/` with `annotated/full_frame/`, `annotated/person_crop/`,
`detections.jsonl`, `run_info.json` and `config_used/`.

Run `outputs/gesture_smoke_4img_20261015_233032` (commit `f87a035`, clean tree): MediaPipe's four public sample
images (`thumbs_up`, `victory`, `pointing_up`, `thumbs_down`; close-up single hands, not robot views). Both modes
give MOVE for the first three (raw scores 0.73–0.91, owner by the wrist rule) and NONE (`Thumb_Down`, 0.77) for
the fourth. On `thumbs_down` the detector found two overlapping person boxes and no depth is available: in
`person_crop` the hand found in both crops is reported once (the 0.57 copy from `det1` is listed under
`duplicates`) and stays unowned (`ambiguous`, wrist in both boxes), so both persons get `no_owned_hand`; in
`full_frame` the same hand is `ambiguous`. Superseded: `…_231147` (before deduplication, uncommitted code; it
reported that hand for both persons).

**Evaluation hook (`gesture_eval.py`): not_evaluated.** It will report, per mode and distance bin (1, 2, 3, 4, 5 m
± 0.5 m; others in `outside_bins`), accuracy raw and at `decision.json` `gesture_min_confidence`, each with its
coverage (labelled people whose track received a hand detection), plus confusion matrices. Input: Unity labels
(CSV `frame_id, track_id, gesture_true, distance_m`) and an adapter run's `detections.jsonl`, set in
`configs/gesture.json` → `evaluation`. Until Unity recordings exist both are null and the script prints
`not_evaluated` and writes nothing. It is the only gesture file that reads labels.

## Known limitations

- Depth decoding is validated only for the THUD **synthetic** captures above. Real-scene depth and any
  monocular or relative depth model are not validated.
- Steps 4 and 8 are a **reference-depth and reference-camera-pose baseline**. They do not measure an RGB-only
  depth model or an estimated camera pose.
- Step 8 has been evaluated on development and adjustment data only: Capture_1 (5 s, 4 people) and Capture_2
  (23 s, 3 people). Frames are highly correlated, and time-to-route evaluation is inconclusive on both.
- The mask-coverage rule drops many observations: 36% of all observations on Capture_2, and 102 of 509 person
  observations.
- Static furniture is still not a trusted motion class. On Capture_1 it is mostly removed, not measured.
- The reference is a visible-surface proxy, not person-centre ground truth. Capture_3 and Capture_4 have not
  been used.
- No passage width, clearance or occupancy map is computed yet (Step 6). Step 9 decisions run on scenario files
  and a replay with a placeholder passage and scripted gestures; they have not been evaluated. `camera_proxy` is
  not the robot position.
- The load size is configured, not measured.
- Gestures have not been evaluated: there are no robot-view images with gesture labels yet (Unity). The smoke
  test uses four close-up sample photos. `gesture_min_confidence` (0.6) has not been checked against the
  module's scores.
- Hand ownership by depth is tested only on constructed cases. Without depth (as in the smoke test) a hand whose
  wrist lies in two overlapping boxes stays unowned (`ambiguous`); the depth rule cannot separate two people at
  nearly the same depth.
- `person_crop` needs person boxes; in the smoke test they are per-image detections without tracking.
- The unlocated-person lower bound is a box depth percentile (reference-depth baseline in THUD). The Unity
  adapter must supply its own.
- Code is kept macOS-compatible and checked by CI on macos-latest.
- Semantic labels are used only as evaluation references, never as model input.
- Real-scene (`Real_Scenes/store`) captures use a different layout and are not supported yet.
