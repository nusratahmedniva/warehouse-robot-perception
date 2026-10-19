# AUDIT: guided-robot task vs. repository state

Audit date: 2026-10-19. Phase 1, read-only: no code, config, scene or
test was changed. This file is the only addition. The only git operation
that wrote anything was `git fetch origin`, which updated remote-tracking
refs so that remote branches could be inspected.

Audited state: branch `anisha/bridge-health-check` at `38ba35d` (same as
local `main`), plus the uncommitted working-tree changes listed in §0.

Status values: **done**, **partial**, **not started**, **unverified** (no
evidence either way; nothing is guessed).

---

## Update 2026-10-20 (3): viewer camera and overlay

`FollowCamera.cs` (C: chase / top-down / gesture camera; chase is the Game-view default), `HriHud.cs` rewritten
as an overlay (state, junction, gesture shown vs read, goal B with marker and label, running success ratio,
Python link), goal marker built by the builder on a new `ViewerOnly` layer (ProjectSettings/TagManager.asset)
that the gesture and 360 deg cameras exclude. Builder: `BatchBuild()` entry point for batch mode; the committed
scene was rebuilt with it (adds HriBridgeClient, view camera, marker; old Main Camera disabled).
Verified in batch Play mode: Camera.main is the view camera in chase mode; images of all three views checked;
marker 3 m ahead of the robot: 508 marker pixels in the chase view, 0 in the gesture camera. The IMGUI overlay
itself cannot be captured in batch mode: compile-checked only, check it in the Editor. Unity EditMode: 38/38.

---

## Update 2026-10-20 (2): Step 0 message format and Step 3 TCP link + watchdog

| Step | Status | Evidence | Still missing |
|---|---|---|---|
| **0** Message format | **done** | `docs/protocol.md` (framing, message types, units, camera intrinsics, panorama axis); `hri_protocol.py` and `HriProtocol.cs`; golden frame `robot_vision/tests/fixtures/hri_frame_v1.frame` checked byte-for-byte in Python and Unity | `command` message (v, w from Python) is reserved, used in Step 5 |
| **3** TCP link + watchdog | **done (shadow mode)** | `hri_bridge_server.py` (+ `configs/bridge.json`), `HriBridgeClient.cs`, `PythonLinkWatchdog.cs`; `RttTracker` | Python perception is a stub until Step 4; decisions still use the scripted sources |

Per-run metrics added: Unity-Python round-trip delay (mean/max per run, latest per 0.1 s row) and Python-side
inference time (mean/max, per model when Step 4 reports models). With the stub, "inference" is only the JPEG
check, so it is not a model timing.

Verification (macOS, batch mode; the Python server ran as a separate process):
- Unity EditMode tests on the real project: 37/37 (adds golden frame decode/re-encode, round trip, invalid
  frames, perception parsing, RttTracker, SHA-256). Python: protocol, server end-to-end (hello, observations
  with real JPEGs, ack_seq, heartbeat gaps < 0.3 s, bad image flagged, protocol error then reconnect), panorama
  bearing.
- One full Task 2 trial with `link_required` true: SUCCESS; 627 observations, 0 bad images, round trip mean
  3.0 ms / max 58 ms (localhost), max gap between observations 0.17 s, `bye` received on exit.
- Watchdog: Python killed while the robot drove at 0.5 m/s: watchdog stop logged 0.3-0.4 s after the link
  dropped (0.1 s telemetry rows), robot at 0 m/s 0.4 s later (emergency deceleration), stayed stopped.
- Panorama axis measured: centre column = world +z, world +x at column 1535/2048, so world yaw grows to the right.
- An image received by Python was checked by eye (730 x 530, upright, worker visible).

Found while verifying: scenes built before this step have no HriBridgeClient; with `link_required` true the
robot never moved. TrialManager now refuses to start in that case and says to run Build Guided Scene again.

---

## Update 2026-10-20: Steps 1, 2 and the Unity part of Step 6

Sections 1-5 below are the original audit; this update supersedes them for the rows listed here.

| Step | Status | Evidence | Still missing |
|---|---|---|---|
| **1** Robot + drive | **done (box stand-in)** | `DiffDriveRobot.cs` (Rigidbody, v/w only, planar: height/roll/pitch frozen, NavMesh path + pure pursuit `PurePursuit.cs`, straight-line fallback, optional wheels, collision event), built by `GuidedSceneBuilder.cs` | MiR100 URDF/mesh (cut order item 1); nominal footprint 0.89 x 0.58 x 0.35 m used |
| **2** Cameras + telemetry | **done** | `Camera360.cs` (cubemap -> equirect every 0.1 s), `PanTiltCamera.cs` (730x530, 60 deg, yaw only, pitch 0), `RobotTelemetry.cs` (0.1 s CSV) | Panorama column of world +z not checked; inference and round-trip columns are stubs (Steps 3-4) |
| **3** TCP + watchdog | **partial** (unchanged + hook) | `PythonLinkWatchdog.cs` (0.3 s rule, DiffDriveRobot stops on it; `link_required` false) | TCP framing, Python side |
| **5** State machine | **partial** (Unity side) | `RobotBrain.cs`: Idle, Navigate, Scan, Approach (2.0 m), Ask, Read (`GestureDialog.cs`: 1.0 s hold, ask once more, abort), Execute, Done; always-on STOP / person-in-path / watchdog stop | Python state machine + simulator (Step 5 as specified) |
| **6** Roadmap, worker, scenarios | **done (Unity part)** | `RoadNode.cs` (2 junctions, 4 endpoints, gizmos), `GestureWorker.cs` (world-space bone aiming on any Humanoid rig, fists except STOP; capsule placeholder), NavMesh baked by the builder, seeded `GoalSequence` | Mixamo worker.fbx is not on this machine: only the placeholder was run; Humanoid posing is compile-checked only. Scenario files beyond the built-in roadmap |
| **7** Trial runner + log | **partial** | `TrialManager.cs`: seeded goals (dev/final seed), reset to A, timeout/stuck/collision, per-run JSON, `results.csv`, session.json with config SHA-256 and git commit, final-run-once guard | Analysis script; inference/round-trip metrics |

Per-run metrics now logged (`run_###.json`, `results.csv`): outcome + failure reason, running success ratio,
A and B (x, z), straight-line vs travelled distance, total and per-step time (navigate, scan, approach, ask,
gesture, execute, plus safety-stop time), avg/max speed, avg/max turn rate, final distance from B, gesture
shown vs read per junction (with ask count), collisions (and what was hit), closest distance to a human.
**Still missing:** per-model inference time and Unity-Python round-trip delay (empty columns, `not_evaluated`).

Verification done (macOS, Unity 2022.3.62f3 batch mode on a scratch copy of the project; the open Editor
was not touched):
- Compile: no errors, no warnings from WarehouseHRI assemblies.
- Unity EditMode tests: 29/29 pass (RoadNode lookup/Reaches/CommandToward, seeded goals pinned to an
  independent Python computation, 0.3 m scoring, 1.0 s hold rule, ask once more then abort, pure pursuit,
  safety corridor, watchdog rule, config defaults).
- Builder run twice: no duplicate objects; NavMesh baked (423 vertices); all 6 branch paths complete.
- Play mode, Task 2, dev seed 1, 4 trials, placeholder worker, scripted baselines: 4/4 SUCCESS
  (goals E4, E2, E1, E4; each stopped 0.007 m from B; shown = read at every junction, 1 ask each).
  This is a scripted-baseline smoke run, not an evaluation.
- Captured images: gesture camera shows LEFT on the viewer's left and FORWARD_RIGHT up-right (placeholder);
  the 360 deg panorama renders under URP.

Rules: decisions use only IPersonSource / IGestureSource (scripted baselines, labelled in every log);
`CommandToward` is called only by TrialManager. Obstacle avoidance = NavMesh (README says so).
Thresholds in `hri_config.json`, `frozen: false` until the development trials are done.

Problems found and fixed in the scene (by the builder, vendored files unchanged): zero-thickness floor
colliders (floor slab added); 12 upstream rack NavMeshObstacles with carving extents about 120 x 370 x 370 m
that erased the NavMesh (disabled).

---

## 0. Repository facts found during the audit (read first)

| # | Finding | Evidence | Consequence |
|---|---|---|---|
| F1 | **origin/main is ahead of this branch and holds the v3 spec.** `origin/main` = `d1099a5` (merge of PR #4, `nusrat/v3-spec`: `ee70cd9`, `5249faf`). It adds `docs/project_flow.md` (approved flow + metric list) and rewrites `CLAUDE.md` for the guided-robot task. This branch is based on `04b1242` and has neither. | `git log 38ba35d..origin/main`; `git show origin/main:docs/project_flow.md` | Before Phase 2 this branch should be merged with `origin/main` (no file overlap with `fdc9bf3`/`38ba35d`, so no conflict expected; not tried). The local `CLAUDE.md` is the old THUD++ version. |
| F2 | Local `main` points at `38ba35d` (the PR #5 head), not at `origin/main` (`d1099a5`). | `git for-each-ref` | Local `main` is not the team's main. |
| F3 | Open PR #5 = this branch (`refs/pull/5/head` = `38ba35d`). | `git ls-remote origin` | Merge state unverified (`gh` CLI not installed). |
| F4 | **Uncommitted:** `PythonBridgePingClient.cs` reworked into a periodic health monitor (status field, `Task.Run`, 2 s interval). Not compiled here. Declares unused `exception` variables in three `catch` blocks (compiler warnings CS0168, not errors). | `git diff` | Compile status unverified; needs Unity Editor. |
| F5 | **Uncommitted:** deletion of `Characters/Idle.fbx.meta`, `Stop.fbx.meta`, `Walking.fbx.meta`, `worker.fbx.meta`. The `.fbx` files are not on disk (the folder is empty), so Unity removed the orphan metas. | `ls Assets/WarehouseRobot/Characters/` | Committing the deletion loses the import settings (rig, clip ranges) the team would need when re-adding Mixamo files. Owner decision. |
| F6 | **`robot_vision/.venv` does not exist.** A venv exists at the repo root (`.venv`, Python 3.12.8, torch 2.14.1, ultralytics 8.4.175, mediapipe 1.1.1). CLAUDE.md requires `robot_vision/.venv/bin/python`. | `ls robot_vision/.venv` | Tests in this audit ran with `../.venv/bin/python` (project venv, not system Python). Either move the venv or update CLAUDE.md. |
| F7 | `.DS_Store` and `unity/.DS_Store` are untracked and not git-ignored. | `git status` | Add `.DS_Store` to `.gitignore`. |
| F8 | `ProjectSettings/EditorBuildSettings.asset` lists `Assets/Scenes/SampleScene.unity`, which does not exist; the real scene is `Assets/Scenes/WarehouseRobot.unity`. | file contents | A player build would contain no valid scene. |
| F9 | `refs/agents/*` (66 refs) are local checkpoint refs created by an agent host, not team branches. They contain the same Unity meshes as the real history and no Mixamo files. | `git for-each-ref` | Not pushed; ignore. |

## Test suite

Command (macOS, from `robot_vision/`): `../.venv/bin/python -m unittest discover -s tests -v`

Result: **131 tests, OK (skipped = 2), exit status 0.**
Skips: `THUD dataset not available` (dataset not on this Mac) and
`no local run folders` (`outputs/` absent). No test covers
`bridge_ping_server.py` or any Unity C#. CI status on GitHub: unverified
(`gh` not installed).

---

## 1. Build steps 0-7 and Final

| Step | Status | Evidence | Missing |
|---|---|---|---|
| **0** Shared spec / message format | **partial** | Flow spec `docs/project_flow.md` exists on `origin/main` only (F1). README describes the goal. | Not on this branch. No message-format spec: no JSON schema for Unity→Python telemetry/images or Python→Unity commands (v, ω, UI text, pan-tilt), no version field, no units/frames convention for Unity (x, z floor; heading sign), no gesture enum `LEFT…STOP/NONE` anywhere in code. |
| **1** Robot model + drive physics | **not started** | Scene `WarehouseRobot.unity` contains only the generated warehouse, `Main Camera`, `Directional Light`, lights and the ping client (object names listed by `m_Name`). No robot asset, URDF, Rigidbody/WheelCollider/ArticulationBody, or drive script in `Assets/`. | MiR100 model (or primitive stand-in), differential-drive Rigidbody controller taking (v, ω) with limits, collision reporting. |
| **2** 360° + pan-tilt cameras + telemetry | **not started** | Only `Main Camera` + `SimpleCameraController.cs` (URP template fly-camera). | 360° capture (or the cut-order fallback: one wide turning camera), pan-tilt rig 730x530 @ 60° vFOV, JPEG encode, telemetry (pose, speed, ω, time). |
| **3** TCP link + watchdog | **partial** | `fdc9bf3`: `robot_vision/bridge_ping_server.py` (line-based `PING`→`PONG`, port 5000) and `Assets/Scripts/PythonBridgePingClient.cs` (one-shot ping; reworked into a periodic monitor in the uncommitted diff, F4). Component present in the scene (script GUID `3a8b1b8d…`). | Length-prefixed JSON + JPEG framing, persistent connection, request/response loop, 0.3 s watchdog that stops the robot in Unity, round-trip delay measurement, Python tests for the framing. Unity compile unverified. |
| **4** Perception (people, distance, arm direction, STOP) | **partial** | YOLO11n + ByteTrack: `track_objects.py` (offline, on THUD segmentation-run folders, `configs/tracking_office.json`). STOP: `gesture_adapter.py` + submodule `external/media_pipe_gesture` @ `180e2796` (`tests/test_gesture_adapter.py` passes). Distance: `person_box_depth.py` uses THUD **reference depth**. | Live per-frame API on Unity JPEGs (current code reads dataset/run folders). YOLO **pose** model and keypoint arm-direction classifier (5 directions + NONE, robot-frame mirroring). 1.0 s hold filter and ask-again logic. Monocular distance (Unity sends no depth; e.g. pinhole from box/keypoint height, labelled as such). Nearest-person selection across the 360° view. Per-model inference timing for the live path. STOP mapping mismatch: her mapping also maps `Closed_Fist` → STOP (spec: open palm only). |
| **5** State machine + steering, Python simulator | **not started** | `decision.py` (MOVE/STOP/WAIT safety rules for THUD replays) is the only decision logic. No state machine, pure pursuit, or simulator. | States NAVIGATE→SCAN→APPROACH→ASK→GESTURE→EXECUTE (+ STOPPED, ABORT, DONE), pure-pursuit (v, ω), 2.0 m approach + face, retry-once-then-abort, always-on STOP / person-in-path override, kinematic Python simulator + tests. |
| **6** Roadmap, worker poses, scenario files | **not started** | `passage.py` / `configs/passage.json` ("Step 6" of the old plan, occupancy grid; unrelated to this step). `tests/scenarios/*.json` are THUD decision-rule fixtures, not trial scenarios. Worker poses assigned to Anisha (origin/main CLAUDE.md). | Baked NavMesh (`m_NavMeshData: {fileID: 0}` in the scene: not baked; `com.unity.ai.navigation` 1.1.6 installed). Junction graph / endpoints, worker avatar with 7 pose animations (5 directions, STOP, idle), scenario JSON (A, B, junction → correct command, seed), scripted-gesture driver in Unity. |
| **7** Trial runner, results log, analysis | **not started** | Reusable building blocks: `decision_io.new_run_dir` (new timestamped folder, never reused), `decision_io` git commit/branch capture (line 209), `run_paths.py` (portable relative paths), `data_splits.py` guard pattern. | Trial runner (Task 1, Task 2, dev seed vs final seed, frozen-config hash check), per-run JSON + CSV, 0.1 s time series, running success ratio, analysis script. |
| **Final** Final trials, report, slides, demo video | **not started** | `make_demo_video.py` exists for THUD replays (reusable MP4 writer). | Everything. |

## 2. Per-run log metrics

None of these is implemented for the guided-robot task. "Building block"
names existing code that could be reused.

| Metric | Status | Where / building block |
|---|---|---|
| Outcome + failure reason (timeout, collision, stuck, wrong goal, abort) | missing | — |
| Running success ratio | missing | — |
| A and B (x, z floor coords) | missing | — |
| Straight-line vs travelled distance | missing | — |
| Total time + per-step time (navigate, scan, approach, ask, gesture, execute) | missing | — |
| Avg / max speed | missing | — |
| Avg / max turn rate | missing | — |
| Final distance from B | missing | — |
| Gesture shown vs read at every junction | missing | `gesture_eval.py` (confusion matrix, `not_evaluated`; STOP/MOVE/NONE only) |
| Per-frame inference time (per model + total) | missing (live path) | THUD-only timing in `run_segmentation.py:295-372`, `track_objects.py:286-292` |
| Unity-Python round-trip delay | missing | — |
| Collisions + closest distance to any human | missing | — |
| 0.1 s time series (CSV) | missing | — |
| Exact config + git commit per run | building block exists | `decision_io.py:209`, `decision_io.new_run_dir` |

## 3. Rules

| Rule | Verdict | Evidence |
|---|---|---|
| Decisions are vision-only (true positions / scripted gestures used only for scoring) | **unchecked** | No decision code for the new task exists. The old pipeline has the equivalent separation (inference never imports reference loaders; `data_splits` guard) and can serve as the pattern. |
| Obstacle avoidance uses the NavMesh, not the camera; report says so | **unchecked** | No NavMesh baked, no report. |
| Dev trials one seed; thresholds frozen; final trials different seed, run once | **unchecked** | No trial runner. Pattern exists: `configs/motion_frozen.json` (sha256 freeze) + `data_splits.py` guard. |
| Mixamo files never on GitHub | **followed** | No `.fbx` under `Characters/` in any commit, any remote branch or any `refs/agents` ref; the only tracked `.fbx` files are Unity's warehouse meshes (Apache-2.0). `.gitignore` ignores `Characters/**/*.fbx/png/jpg/tga`. Only the four `.fbx.meta` files were pushed (import settings, no Mixamo content; 0 matches for "mixamo" in `worker.fbx.meta`). |
| Every third-party part credited with its licence | **partial** | README credits Robotics-Warehouse (Apache-2.0, `MODIFICATIONS.md`), media_pipe_gesture (MIT), Ultralytics (AGPL-3.0), MediaPipe (Apache-2.0), THUD++. Missing: SegFormer weights `nvidia/segformer-b0-finetuned-ade-512-512` (`configs/office.json`, licence not stated), Hugging Face `transformers`, ByteTrack (via Ultralytics), MediaPipe model file `gesture_recognizer.task`, Unity AI Navigation package, Mixamo (Adobe terms), MiR100 model (when added). The submodule README says "MIT, see LICENSE" but the submodule contains no LICENSE file. README's Mixamo file names (`worker.fbx`, `walking.fbx`, `idle.fbx`) do not match the meta names (`worker`, `Walking`, `Idle`, `Stop`). |
| Windows + macOS compatible, pathlib, paths from config | **followed** (Python) | CI matrix `windows-latest` + `macos-latest` (`.github/workflows/tests.yml`). `configs/office.json` holds `"dataset_root": "D:/RGB-D"`, a drive letter in config (allowed: config, overridden by `THUD_DATASET_ROOT`). |
| Venv Python only | **partial** | Venv is at repo root, not `robot_vision/.venv` (F6). |
| Never push | **followed** by this audit | — |
| Do not modify `external/media_pipe_gesture` | **followed** | Submodule clean at `180e2796`. |
| Commit only after full suite passes | **unchecked** for past commits | Current suite passes (exit 0). |
| Datasets / weights / outputs git-ignored | **followed** | `.gitignore`; no `models/` or `outputs/` in the repo. |
| Unity runtime scripts avoid Editor-only APIs | **followed** for the 2 project scripts | `PythonBridgePingClient.cs`, `SimpleCameraController.cs` use `UnityEngine` and `System.*` only. Compile unverified. |

## 4. Old THUD++ work vs. new task

**Reuse as is or with small changes**

| Part | Use in the new task |
|---|---|
| `gesture_adapter.py` + submodule | STOP detection (open palm) on the pan-tilt crop of the chosen person; `person_crop` mode fits. Needs a new STOP-only mapping in config (drop `Closed_Fist`, ignore MOVE) without touching the submodule. |
| YOLO11n (Ultralytics) + ByteTrack setup | Person detection/tracking on Unity frames; swap to the pose variant (`yolo11n-pose`) for keypoints. |
| `check_environment.select_device` | Device choice (CUDA → MPS → CPU). |
| `decision.py` `GestureFilter` idea, rule ordering, `PersonState` / route-corridor geometry, `motion.time_to_route` | "Person stepping into the path" stop; hold-time filter pattern for the 1.0 s direction hold. |
| `footprint.py` look-ahead | Stopping distance for the person-in-path rule (robot.json values must become MiR100 values). |
| `decision_io.new_run_dir`, git-commit capture, `run_paths.py` | Trial run folders with config + commit. |
| `data_splits.py` guard + `motion_frozen.json` sha256 pattern | Dev-seed / final-seed guard and frozen-threshold check. |
| `make_demo_video.py` MP4 writer | Demo video. |
| Test style (`unittest`, no data needed, CI matrix) | All new tests. |

**Must be written:** message schema + length-prefixed JSON/JPEG framing
(Python and C#), Unity watchdog, robot drive controller, camera rigs,
pose-based arm-direction classifier, monocular distance estimate, state
machine, pure pursuit, Python simulator, scenario format, roadmap/junction
data, worker pose animations + scripted gesture driver, trial runner,
per-run log, analysis script, report.

**Dead code for the new task (keep, do not delete; candidates to move to
a `thud/` folder later):** `run_segmentation.py`, `audit_dataset.py`,
`check_camera_streams.py`, `validate_depth.py`, `thud_data.py`,
`thud_depth.py`, `fuse_objects.py`, `report_step4.py`,
`estimate_motion.py`, `report_motion.py`, `verify_tracking_run.py`,
`migrate_run_paths.py`, `make_proxy_route.py`, `replay_decisions.py`,
`person_box_depth.py` (reference depth), `passage.py` + `configs/passage.json`
(origin/main CLAUDE.md: "kept but not used in v3"), the `configs/*office*`,
`proxy_route_*`, `replay_script_*`, `load.json` (pallet; no load in the
spec) files, and `tests/scenarios/*`. SegFormer floor segmentation is not
needed (NavMesh handles obstacles).

**Conflicts to note:** decision.py's gesture set is STOP/MOVE/NONE, not the
7 commands; `robot.json` is a provisional 0.60 m robot, not the MiR100
(about 0.58 x 0.89 m, unverified); a FORWARD pose with an open hand would
be read as STOP by MediaPipe, so the avatar's direction poses must not use
an open palm.

## 5. Remaining work, in build order

Size: S < 0.5 day, M 0.5-1.5 days, L > 1.5 days. Deadline in README: 22 October 2026 (3 days from this audit).

| # | Item | Size | Blockers | Cut order if short |
|---|---|---|---|---|
| 0a | Merge `origin/main` into this branch (spec + CLAUDE.md); decide on the uncommitted `.cs` change and the `.fbx.meta` deletions; fix venv location or CLAUDE.md; ignore `.DS_Store` | S | Owner decisions (F4, F5, F6) | — |
| 0b | Message spec `docs/protocol.md` + `robot_vision/protocol.py` (schema, enums, units) + tests | S | — | — |
| 1 | Differential-drive Rigidbody controller (C#), MiR100 stand-in (primitive box with correct dimensions); URDF import optional | M | Unity Editor: create robot object, assign references | **URDF import** (first cut) |
| 2 | Pan-tilt camera (730x530, 60°) + 360° capture + telemetry packer (C#) | M | Unity Editor wiring | **360° camera → one wide turning camera** (third cut) |
| 3 | Length-prefixed JSON + JPEG TCP bridge (Python server, C# client), 0.3 s Unity watchdog, round-trip timing; Python framing tests | M | — | — |
| 4 | Live perception: YOLO11n-pose people + keypoint arm-direction classifier, monocular distance, nearest-person pick, STOP via gesture adapter, per-model timing; tests on synthetic keypoints | L | `yolo11n-pose.pt` download (git-ignored); real Unity frames for any accuracy figure (else `not_evaluated`) | **Diagonal directions** (second cut: keep LEFT / FORWARD / RIGHT / STOP / NONE) |
| 5 | State machine + pure pursuit + kinematic Python simulator + tests (hold 1.0 s, retry once, abort, STOP override, person-in-path stop) | L | Message spec (0b) | — |
| 6 | NavMesh bake, roadmap/junction file, worker avatar poses + scripted gesture driver, scenario files for Task 1 and Task 2 | M | Mixamo download, animation setup (Anisha), NavMesh bake (Editor) | **Junctions beyond two** (fourth cut) |
| 7 | Trial runner, per-run JSON + CSV, 0.1 s series, success ratio, all §2 metrics, analysis script, frozen-config + seed guard | M | Steps 3, 5, 6 | **Never cut** (per-run log, success ratio, timing) |
| Final | Dev trials (seed 1) → freeze → final trials (seed 2, once) → report (states NavMesh obstacle avoidance and vision-only decisions), slides, demo video, licence credits | M | All above | — |

Not verified in this audit: Unity compile state of either C# script,
whether the scene opens without errors, CI results on GitHub, PR #5 merge
status, MiR100 dimensions.
