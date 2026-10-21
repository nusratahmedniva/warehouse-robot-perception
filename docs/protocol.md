# Unity <-> Python bridge protocol (version 2)

One TCP connection. Unity is the client, Python the server
(`robot_vision/bridge/server.py`). Host, port, rates and limits come from
`robot_vision/configs/bridge.json`, which both sides read.

## Framing

Every message, in both directions:

```
+---------------------------+----------------------------+-----------------------------+
| 4 bytes: header length N  | N bytes: UTF-8 JSON header | attachments, back to back   |
| unsigned, big-endian      | (one JSON object)          | (sizes listed in the header)|
+---------------------------+----------------------------+-----------------------------+
```

Every header holds:

| field         | type   | meaning                                                              |
|---------------|--------|----------------------------------------------------------------------|
| `version`     | int    | protocol version; must equal `protocol_version` in bridge.json (2)   |
| `type`        | string | message type (below)                                                 |
| `seq`         | int    | sender's message counter, >= 0, unique and increasing in creation order (a frame can arrive after later telemetry, since it is encoded in the background) |
| `attachments` | list   | `[{"name": str, "size": int}, ...]` in the order the bytes follow; `[]` if none |

Limits: `0 < N <= max_header_bytes`; each attachment size `>= 0` and the
total `<= max_attachment_bytes`; attachment names unique. Numbers must be
finite (no NaN or Infinity).

Errors:
- **Framing error** (bad length, header that is not a JSON object, bad
  attachment list, truncated stream) or **version mismatch**: the receiver
  sends `error` with `fatal: true` (if it can) and closes the connection.
- **Message error** (framing intact, but unknown type, missing or
  wrongly typed field, missing attachment, forbidden field): the receiver
  answers `error` with `fatal: false`, ignores the message and keeps the
  connection.

The schema is checked in `robot_vision/bridge/protocol.py` (`SCHEMAS`).

## Conventions

- Positions are Unity world metres: `x`, `z` on the ground plane (y is up).
- `yaw_deg` is Unity's rotation about +Y (`transform.eulerAngles.y`):
  0 = facing world +Z, 90 = facing world +X (clockwise seen from above).
- `omega` (rad/s) > 0 turns left (counter-clockwise from above), so it
  *decreases* `yaw_deg`. `v` (m/s) > 0 drives forward.
- `pan_deg` > 0 turns the pan-tilt camera left of the robot's forward
  axis; 0 looks forward.
- `time_s` is Unity `Time.time` (simulation seconds since Play).
- JSON has no nulls in this protocol (Unity's JsonUtility cannot read
  them): optional values use a flag (`has_target`) or `-1`.

## Unity -> Python

### `hello` (once, first message after connecting)
`time_s`, `client` ("unity"), `unity_version`, `telemetry_hz`,
`frame_360_hz`, `frame_pan_tilt_hz`, `watchdog_timeout_s`.

### `telemetry` (`telemetry_hz`, 20 Hz)

| field | meaning |
|---|---|
| `time_s` | Unity time |
| `pose` | `{"x", "z", "yaw_deg"}` robot pose |
| `v`, `omega` | speed and turn rate applied now (after the acceleration limits) |
| `v_cmd`, `omega_cmd` | last command after clamping to the maximum speeds |
| `pan_deg` | current pan angle |
| `collision_count` | collisions recorded since Play |
| `reached_end_point` | true once the scenario says the robot reached the end point |
| `trial_index`, `trial_running` | set by the Step 7 trial runner: trial number (-1 = none) and whether it is running. A new index while running starts a new run of the Python state machine at the roadmap start; `trial_running` false keeps it idle. Optional for Python (older Unity builds omit them). Never carries goal B. |
| `nav_has_target`, `nav_target_x`, `nav_target_z` | the target point Python requested |
| `nav_status` | `none`, `complete`, `partial`, `invalid`, `start_off_navmesh`, `target_off_navmesh`, `no_agent_type` (no enabled, baked NavMesh Surface for the agent type `nav.agent_type`, "AMR"; all queries use that agent type) |
| `nav_start_snap_m`, `nav_target_snap_m` | horizontal distance (m) by which the robot position and the target were moved onto the NavMesh (`NavMesh.SamplePosition`, at most `nav.snap_max_distance_m` in bridge_unity.json); -1 if that end could not be snapped |
| `nav_corners` | `[{"x", "z"}, ...]` NavMesh path corners from the snapped start to the snapped target (`NavMesh.CalculatePath`, recomputed every telemetry tick) |
| `last_command_seq` | `seq` of the last command received (-1 before any) |
| `rtt_telemetry_seq`, `rtt_ms` | round-trip delay of the most recent answered telemetry: from Unity queuing telemetry `rtt_telemetry_seq` to receiving the command whose `reply_to` names it (-1 if none yet) |
| `watchdog_stopped` | true while the watchdog holds the robot stopped |
| `watchdog_count` | watchdog stops since Play |
| `keyboard_override` | true while the debug keyboard control drives the robot (bridge commands are then ignored) |
| `estop` | true while the emergency stop is latched (v = 0, omega = 0; bridge and keyboard commands ignored until released) |
| `frames_360_sent`, `frames_360_dropped`, `frames_pan_tilt_sent`, `frames_pan_tilt_dropped` | frame counters of this connection (see "Frame rates and drops") |

### `frame_360` (`frame_360_hz`; attachment `image`, JPEG)
`time_s`, `frame_index` (Camera360 capture counter), `width`, `height`
(equirectangular, 2:1), `camera_height_m`, `pose` (robot pose at
capture), `encoding` ("jpeg"), and:
- `centre_world_yaw_deg`: the world direction (same convention as
  `yaw_deg`) that the image centre column faces: 0, i.e. world +Z.
  Confirmed in Unity on 2026-10-20: a cube placed along world +Z appears
  at the image centre. The image is world-aligned (it does not turn with
  the robot).

### `frame_pan_tilt` (`frame_pan_tilt_hz`; attachment `image`, JPEG)
`time_s`, `frame_index`, `width`, `height`, intrinsics `fx`, `fy`, `cx`,
`cy` (pixels; `fy = (height / 2) / tan(vfov / 2)`, `fx = fy`,
`cx = width / 2`, `cy = height / 2`), `vertical_fov_deg`, `pan_deg` and
`tilt_deg` at render time, `camera_height_m`, `pose`, `encoding` ("jpeg").

Images are encoded from GPU readbacks (`AsyncGPUReadback`) on one
background thread per camera; row 0 of the JPEG is the top of the image
(confirmed in Unity).

### Frame rates and drops

Each camera stream has slots every `1 / frame_*_hz` seconds. When a slot
falls due while the previous frame of that camera is still being read
back or encoded, the slot waits (the frame is sent late); it is counted
as dropped only when a whole further period passes without a frame, or
when its readback or encoding fails. Unity reports the per-connection
counters in every telemetry message; the server writes the drop rate per
camera, `dropped / (sent + dropped)`, to `summary.json` (`frames`).

## Python -> Unity

### `command` (one per telemetry message)

| field | meaning |
|---|---|
| `reply_to` | `seq` of the telemetry this answers (-1 if unsolicited) |
| `v`, `omega` | commanded speed and turn rate (Unity clamps to robot.json limits) |
| `pan_deg` | pan angle for the pan-tilt camera |
| `has_target`, `target_x`, `target_z` | target point for the next NavMesh path (`has_target: false` clears it) |
| `state` | state-machine state name (shown in the bridge panel) |
| `screen_text` | text shown on screen ("" = none), e.g. "Which direction?" |
| `route` (optional, guide mode) | the map the state machine uses: `Task2` (roadmap.json) or `Task1:<stops>` (e.g. `Task1:C1,J1,C3`); the trial runner refuses trials when it is not the map of its task |
| `perception_ready` (optional, guide mode) | true once the models are warmed up and one frame of each camera has been processed; the trial runner starts trial 1 only after it |

The two optional fields were added on 21 October 2026 (infrastructure; extra fields were already allowed, so
`protocol_version` stays 2). Absent, Unity reads `""` and `false`.

Every command carries the complete desired state; Unity keeps nothing
from earlier commands.

### `error`
`error` (string), `fatal` (bool).

## Goal B never reaches Python

No message carries goal B or any end-point coordinate; only the
`reached_end_point` flag. `protocol.py` rejects any Unity message that
contains a key named `goal`, `goal_point`, `goal_x`, `goal_z`, `end_point`,
`end_point_x`, `end_point_z`, `point_b` or `b`, at any depth.

## Safety in Unity

- **Emergency stop**: the debug panel's "Stop robot" button latches it
  (`DiffDriveController.EngageEmergencyStop`): v = 0, omega = 0, braking
  at `estop_decel_mps2` (1.5 m/s², robot.json) instead of `decel_mps2`, and
  bridge and keyboard commands are ignored until it is released with two
  deliberate clicks ("Release stop...", then "Confirm release" within
  3 s). Engaging and releasing are logged; telemetry carries `estop`.
- **Watchdog**: once a command has arrived, if no command arrives for
  `watchdog_timeout_s` (0.3 s), Unity sets v = 0, omega = 0 (the drive
  brakes at `decel_mps2`), logs a warning and counts it
  (`watchdog_count`). The next command releases it.
- **Disconnect**: when the connection drops, Unity stops the robot at
  once and logs it; it reconnects every `reconnect_interval_s`.

## Round-trip delay

Unity measures each telemetry -> command round trip (above) and reports
it in the next telemetry. The Python server writes one line per message
to `messages.jsonl` in its run folder, including `rtt_ms`, and a summary
(mean, median, 95th percentile, maximum, with coverage) in
`summary.json`.

## Changes

- 2026-10-20 (additive, still version 2): telemetry gains the optional `trial_index` and `trial_running`
  (Step 7 trial runner). Python's `guide` mode (bridge/guide.py) answers every telemetry with the Step 5
  state machine's command (hri_control.py).

- Version 2 (2026-10-20, after the first Unity test): telemetry gains
  `nav_start_snap_m`, `nav_target_snap_m`, `estop` and the four frame
  counters; `frame_360` drops `centre_yaw_status` (the centre direction is
  confirmed). Version 1 peers are refused.
