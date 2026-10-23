# Unity <-> Python bridge protocol (version 3, v4 study)

Version 3 is `docs/protocol.md` (version 2) plus the changes below. Everything not listed here is **exactly as in
version 2**: framing, envelope, errors, conventions (positions, `yaw_deg`, `omega`, `pan_deg`, no nulls), `hello`,
`telemetry`, `frame_360`, frame rates and drops, safety in Unity (emergency stop, 0.3 s watchdog, disconnect), round-trip
measurement. Read `protocol.md` first; this file lists only what Unity must add or change.

Version 2 is not touched: the v3 study keeps running with `robot_vision/configs/bridge.json` (`protocol_version` 2).
Version 3 is selected only by `robot_vision/configs/v4/bridge.json` (`protocol_version` 3), which Python starts with
`python -m bridge.server --config configs/v4/bridge.json ...`. Both sides read the same file, as in version 2.

## Version negotiation

- Every header `version` must equal `protocol_version` in the config the peer was started with (3 here).
- A peer that receives another version answers `error` with `fatal: true` and closes the connection. A version 2 Unity
  build is therefore refused by a version 3 Python, and the reverse.
- The v4 scene (`WarehouseRobot_v4.unity`) reads `configs/v4/bridge.json`; the v3 scene keeps reading
  `configs/bridge.json`.

## Changes from version 2

### 1. `command` gains `vertical_fov_deg` and `hud`

All version 2 command fields stay (`reply_to`, `v`, `omega`, `pan_deg`, `has_target`, `target_x`, `target_z`, `state`,
`screen_text`, and the optional `route`, `perception_ready`). Two required fields are added:

| field | type | meaning |
|---|---|---|
| `vertical_fov_deg` | number | Pan-tilt camera vertical field of view in degrees, for zoom. **-1 = keep the configured default** (no zoom change). Otherwise 0 < value < 180. Unity clamps it to the zoom range in its own config and always reports the value actually used in the next `frame_pan_tilt`. Phase 1 Python sends -1 on every command. |
| `hud` | object | What Unity draws on the heads-up display panel (below). Display only: Unity never acts on it and it never appears in a camera image. |

As in version 2, every command carries the complete desired state; Unity keeps nothing from earlier commands.

#### The `hud` object

| field | type | meaning |
|---|---|---|
| `state` | string | State-machine state name (same text as the command's `state`). |
| `screen_text` | string | Same text as the command's `screen_text` ("" = none). |
| `commander_id` | int | `id` of the person Python treats as the commander, **-1 = none**. |
| `gesture` | string | The v4 gesture class Python currently reads: `POINT`, `WAIT`, `STOP` or `NONE`. |
| `gesture_score` | number | Reader's score for the current reading, 0 to 1 (0 when there is no reading). |
| `gesture_raw` | string | The current per-frame reading in the reader's own words (e.g. `LEFT`, `FORWARD`, `STOP`, `NONE`): what the robot sees right now. |
| `gesture_accepted` | string | The command the dialog accepted after its hold time, or `NONE` until then: what the robot decided. |
| `point_angle_deg` | number | Pointed direction in degrees relative to the robot's forward axis (+ = right), **-1 if none**. Because -1 is also a possible angle, Unity treats `gesture != "POINT"` as "no angle". |
| `people` | list | `[{"id": int, "bearing_deg": number, "distance_m": number, "is_commander": bool}, ...]`: every person the robot currently sees. `bearing_deg` is relative to the robot's heading (+ = right); `distance_m` is -1 when unknown; `id` is the tracker id. `[]` if nobody. |
| `log` | list | `[{"dir": "in" or "out", "type": string, "seq": int, "text": string}, ...]`: the last N message summaries per direction (N = `hud.log_messages_per_direction` in the config, 15), oldest first, `in` entries then `out` entries. For `in`, `seq` is the message's `seq`; for `out` (commands), `seq` is the `seq` of the telemetry it answers (the command's own `seq` is not known until it is sent). `text` is a short human-readable summary. |

No nulls: empty values are `""`, `[]`, `-1` or `NONE`.

**What Python fills in at which phase.** Phase 1 (this version of Python): `state`, `screen_text`, `people` (all
`is_commander` false), `gesture` (`STOP` when the v3 reader reads STOP, otherwise `NONE`; the v3 reader has no POINT or
WAIT), `gesture_score`, `gesture_raw`, `gesture_accepted`, `log`. **`commander_id` is always -1 and `point_angle_deg` is
always -1** until Phase 3 (commander rule, gesture reader). Unity draws whatever arrives and must not assume more.

Unity's drawing: one panel, in the game view only. The panel must not be rendered by either robot camera (draw it in a
screen-space overlay that is excluded from the 360 and pan-tilt cameras, or on the `HUD` layer both cameras skip).

### 2. `frame_pan_tilt`: intrinsics must match the zoom

The fields are unchanged (`time_s`, `frame_index`, `width`, `height`, `fx`, `fy`, `cx`, `cy`, `vertical_fov_deg`,
`pan_deg`, `tilt_deg`, `camera_height_m`, `pose`, `encoding`), but now:

- `vertical_fov_deg`, `fx`, `fy`, `cx`, `cy` are the values **at render time of that frame**, i.e. after any zoom.
- Python **rejects** a frame (`error`, `fatal: false`, frame ignored) unless, within a relative tolerance
  (`intrinsics_rel_tol`, 0.001, in `configs/v4/bridge.json`):
  `fy = (height / 2) / tan(vertical_fov_deg / 2)`, `fx = fy`, `cx = width / 2`, `cy = height / 2`, and
  0 < `vertical_fov_deg` < 180.
- When a zoom command arrives, frames rendered before the camera reached the new field of view still carry the old
  value. Unity never sends a frame whose intrinsics belong to a different field of view than its pixels.

### 3. Forbidden keys from Unity

Version 2 rejects, at any depth, a key named `goal`, `goal_point`, `goal_x`, `goal_z`, `end_point`, `end_point_x`,
`end_point_z`, `point_b` or `b`. Version 3 additionally rejects:

`true_gesture`, `true_commander`, `commander_truth`, `gesture_truth`, `worker_label`, `truth`

(compared case-insensitively, as in version 2). A message from Unity containing any of them, even nested inside a list
or object, is answered with `error` (`fatal: false`) and ignored. Truth about the workers reaches Python only through the
run files below, and only evaluation code reads them. Python-to-Unity messages are not checked for these keys (the HUD
`is_commander` is a perception result, not truth).

## Per-run files Unity writes (never sent over the bridge)

These files are written by Unity into the trial runner's session folder (`outputs/trials_<mode>_<task>_<time>/`, the
folder that already holds `session.json` and `truth_run###.json`). **Per-run files go in the run's own subfolder
`run_###/`** (`###` = trial number, zero-padded to 3, as in `truth_run###.json`); the session-level leak test goes in
`leak_test/` at the session folder's top level. A file is created once and never overwritten. All numbers are Unity
world metres, `x`-`z` ground plane, `yaw_deg` as in `protocol.md`. **Every `time_s` in these files is Unity `Time.time`**, the same clock as the `time_s` in
telemetry and frame headers (decided 2026-10-23, below), so truth and trail rows join to frames without any offset.
Python's inference code never reads any of them;
`robot_vision/gt_path.py`, `robot_vision/gesture_data.py` and `hri_analysis.py` do.

### `run_###/run.json`

```json
{"run_start_s": 123.456}
```

`run_start_s` is Unity `Time.time` at the start of the run, written once, for reference only. No evaluation step depends
on it: every `time_s` in the run files is already on the frame clock.

### `run_###/grid.json`

The floor grid, with A and B. (This file contains goal B; that is why it is a file and not a message.)

```json
{
  "cell_size_m": 0.5,
  "origin_x": -2.0,
  "origin_z": -12.0,
  "cells_x": 40,
  "cells_z": 60,
  "blocked_rows": ["0000...", "0110...", "..."],
  "start": {"x": 6.25, "z": -10.0},
  "goal":  {"x": 1.0, "z": 2.0}
}
```

- Cell `(ix, iz)` covers `x` in `[origin_x + ix * cell_size_m, origin_x + (ix + 1) * cell_size_m)` and the same for `z`;
  its centre is half a cell further. `ix` runs along +x, `iz` along +z.
- `blocked_rows` has `cells_z` strings (index = `iz`, row 0 is the smallest `z`), each `cells_x` characters (index =
  `ix`): `"1"` blocked, `"0"` free. (Strings, because Unity's `JsonUtility` cannot read nested arrays.)
- Blocked = racks, boxes, stations and walls, **already widened** by the robot's half-width plus the safety margin
  (`docs/project_flow_v4.md`). Python adds no further inflation.
- `start` is A, `goal` is B, in world metres. Their cells are `floor((x - origin_x) / cell_size_m)` and the same for
  `z`, and both must be free.

### `run_###/optimal_path.json`

The shortest path from A's cell to B's cell on that grid, as Unity computed it.

```json
{
  "length_m": 31.4558,
  "cells":  [{"ix": 18, "iz": 4}, {"ix": 18, "iz": 5}, "..."],
  "points": [{"x": 6.25, "z": -9.75}, {"x": 6.25, "z": -9.25}, "..."]
}
```

- A* on the grid, **8-connected**: a straight step costs 1 cell, a diagonal step costs sqrt(2) cells, a diagonal step is
  allowed only when both orthogonal neighbour cells are free (**no corner cutting** through a blocked cell). Cells in
  order from A's cell to B's cell, both included.
- `points` are the centres of those cells in the same order (the polyline drawn in the scene and used for the distance
  measures).
- `length_m` = (sum of step costs in cells) x `cell_size_m`, computed from `cells` (not from the exact A and B
  positions). Python recomputes the optimal length with its own A* and requires equality within
  `optimal_length_tolerance_m` (0.001 m, `configs/v4/gt_eval.json`). Several equally short paths may exist; only the
  length must match.

### `run_###/trail.csv`

The robot's position every 0.1 s of simulation time, from the start of the run to its end.

```
time_s,x,z,yaw_deg
0.000,6.250,-10.000,0.00
0.100,6.250,-10.000,0.00
```

Header exactly as above; `time_s` is Unity `Time.time` (absolute, not relative to the run start); `x`, `z`, `yaw_deg`
from the robot root, 3 decimals. The first row is at the run start, the last row is the final position of the run.

### `run_###/truth.jsonl`

One JSON object per line, one line per frame of the gesture logger (every Unity `FixedUpdate`, or at least every 0.1 s,
and always on every phase change). For every worker standing in the scene (bystanders included):

| field | type | meaning |
|---|---|---|
| `time_s` | number | Unity `Time.time`, same clock as `trail.csv` and as the `time_s` of telemetry and frame headers |
| `worker_id` | int | worker id in the scene (the same worker keeps the same id for the whole run) |
| `look` | string | avatar look name (e.g. `look_03`); which looks are test looks is declared in `configs/v4/` |
| `x`, `z` | number | worker position |
| `true_command` | string | `POINT`, `WAIT`, `STOP` or `NONE` (the command the worker is performing now) |
| `point_angle_deg` | number | true pointed direction relative to the robot's forward axis (+ = right) while `true_command` is `POINT`, otherwise -1 |
| `arm` | string | `left`, `right` or `none` |
| `phase` | string | `idle`, `start_delay`, `gesturing`, `holding`, `returning` (the worker's own state; the list may be extended by agreement) |
| `is_commander` | bool | true for the one worker who commands at this moment |

Optional field `clip` (string): the animation clip being played (empty or absent when none); it is what the clip split
(`configs/v4/data_splits.json`) uses. The field name is a proposal, to be confirmed by Nusrat. The random gesture
parameters of the run (speed, size, start delay) may be added as further extra fields; extra fields are ignored.

These keys are allowed here because the file is not a bridge message. Python reads this file only in evaluation code
(`robot_vision/gesture_data.py`): it checks every line against this table (types, `true_command` in POINT/WAIT/STOP/NONE,
`arm` in left/right/none, `phase` in the list in `configs/v4/gesture_data.json`, `point_angle_deg` = -1 unless
`true_command` is POINT, one `look` per `worker_id`, at most one commander per `time_s`) and refuses a bad line with its
line number.

### `leak_test/` (once per session, before the first run)

Before every session Unity renders **both** robot cameras (360 and pan-tilt) twice from the same pose, with the
`GroundTruth` layer on and off, and writes **lossless** images (PNG) named
`<camera>_on.png` and `<camera>_off.png`, e.g. `cam360_on.png`, `cam360_off.png`, `pan_tilt_on.png`, `pan_tilt_off.png`
(more pairs, from other poses, use other prefixes: `cam360_p2_on.png`, ...). Both images of a pair have the same size
and pose; nothing else in the scene moves between the two renders (animation and physics paused, same frame).

Python (`python gt_path.py leak outputs/trials_X/leak_test`) compares each pair pixel by pixel and writes
`leak_test/leak_test.json` (`passed`, `max_diff`, per-pair results). **The images must be identical
(`leak_max_pixel_diff` 0 in `configs/v4/gt_eval.json`), or no run may start**; the Unity trial runner should refuse to
start until it has run the check (its own pixel comparison, or Python's) and it passed. JPEG must not be used here: its
compression would make identical scenes differ.

## What Nusrat implements in Unity from this document

1. **Bridge client, version 3**: read `configs/v4/bridge.json` (`protocol_version` 3); send `version: 3`; accept
   commands with the two new fields; parse `hud` (`JsonUtility` classes with the types above; `people` and `log` as
   lists of classes; no nulls arrive).
2. **Zoom**: apply `vertical_fov_deg` to the pan-tilt camera (-1 = keep default; clamp to your own range); put the
   field of view actually rendered, and `fx`, `fy`, `cx`, `cy` computed from it (`fy = (height / 2) / tan(fov / 2)`),
   in every `frame_pan_tilt`.
3. **HUD panel**: draw `hud` in the game view only (state, screen text, people list with bearing and distance, gesture
   class with score, raw and accepted gesture, commander, POINT angle, the message log); invisible to both robot cameras.
4. **Forbidden keys**: never put the six truth keys (or the goal keys) in any message to Python.
5. **Run files**: `run_###/run.json`, `grid.json`, `optimal_path.json`, `trail.csv`, `truth.jsonl` (all `time_s` in Unity
   `Time.time`), and the session `leak_test/`
   with the layer-on/off image pairs, in the formats above; the A* in Unity must follow the stated rules exactly (8
   neighbours, diagonal cost sqrt(2), no corner cutting, widened blocked cells).
6. **Leak-test guard**: no run starts unless the pairs are identical.
7. Keep version 2 behaviour in the v3 scene configuration (v3 study scene) untouched.

## Decided

- 2026-10-23 (Phase 1 review): `intrinsics_rel_tol` 0.001 accepted (a consistency check on the camera intrinsics).
- 2026-10-23: the `truth.jsonl` phase names `idle`, `start_delay`, `gesturing`, `holding`, `returning` accepted.
- 2026-10-23: the leak-test image names `<camera>_on.png` / `<camera>_off.png` accepted.
- 2026-10-23: `leak_test/` stays at the session level (once per session), not per run.
- 2026-10-23 (Phase 2): `time_s` in `truth.jsonl` and `trail.csv` is Unity `Time.time` (the frame clock), not time since
  the run start; `run_###/run.json` keeps `run_start_s` for reference only. Nusrat had not started the Unity side.
- 2026-10-23: the truth-to-frame join tolerance is 0.06 s (`truth_join_max_s` in `configs/v4/gesture_data.json`, the v3
  value of `configs/hri_perception.json`).

- 2026-10-24 (Phase 2 review): 2 development looks + 1 test look accepted as the split structure; the optional `clip`
  field of `truth.jsonl`, the clip definition (an uninterrupted stretch of rows of one worker with the same non-NONE
  `true_command`, `arm` and `clip`) and the simulator's default confusion table (POINT to WAIT, WAIT to STOP, STOP to
  WAIT) accepted.
- 2026-10-24: the merged `hri_trials` output also carries the session's `leak_test/` (images and `leak_test.json`).
- 2026-10-24 (Phase 3): the WAIT timeout is 20 s; when it expires without a POINT the ask counts as unclear (ask again,
  then abort, as in v3).
- 2026-10-24 (Phase 3): hud ids. `hud.people[].id` are 360-camera track ids. `commander_id` is the 360 track id linked to
  the commander found in the pan-tilt view (by bearing), -1 when the commander cannot be linked to a 360 person.
  `gesture` is the window decision (POINT/WAIT/STOP/NONE), `gesture_raw` the reader's per-frame class, `gesture_accepted`
  the branch command the dialog accepted (or WAIT), `point_angle_deg` the resolved pointed angle relative to the robot's
  forward axis (+ = right) or -1.

- 2026-10-24 (Phase 3 review, recorded in Phase 4): STOP does not need the push motion; the hand cross-check tie-break stays
  off until measured; the robot may move sideways for a second look at a POINT (two-view) and may approach the commander
  again, neither using up an ask; only a gesture that starts after "Which direction?" counts (details in
  `docs/gesture_reader_v4.md`, Decided). The question text can therefore be shown more than once per ask; nothing changes in
  the messages. `screen_text` and the HUD fields are as before.

## Changes

- 2026-10-24 (Phase 3, still version 3): the HUD fields left at -1/NONE in Phase 1 are filled by the v4 controller.
- 2026-10-23 (Phase 2, still version 3): `truth.jsonl` and `trail.csv` times are Unity `Time.time`; `run_###/run.json`
  and the optional `clip` field of `truth.jsonl` are added. These are file formats, not bridge messages.
- Version 3 (2026-10-23, Phase 1): `command` gains `vertical_fov_deg` and `hud`; `frame_pan_tilt` intrinsics are
  checked against `vertical_fov_deg`; truth keys are forbidden at any depth; per-run ground-truth files are specified.
  Version 2 peers are refused by a version 3 server and the reverse.
