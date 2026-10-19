# Unity <-> Python message format (protocol v1)

Shared by `unity/.../Assets/Scripts/WarehouseHRI/HriProtocol.cs` and `robot_vision/hri_protocol.py`.
A golden frame (`robot_vision/tests/fixtures/hri_frame_v1.frame`) is decoded and re-encoded byte-for-byte by
the tests on both sides.

## Transport and framing

- TCP, one connection. Unity is the client, Python the server (`host`/`port` in
  `hri_config.json -> link` and `robot_vision/configs/bridge.json`; default `127.0.0.1:5050`).
- Every message is one **frame**:

  ```
  uint32 big-endian  H  = length of the JSON header in bytes
  H bytes            UTF-8 JSON header (one object)
  for each entry in header["images"], in order:
      uint32 big-endian  N = entry["bytes"]
      N bytes            the image (JPEG)
  ```

- Limits: header <= 1 MiB, each image <= 16 MiB. A frame that breaks a limit, has malformed JSON, or whose
  image length differs from `entry["bytes"]` closes the connection.

## Common header fields

| Field | Type | Meaning |
|---|---|---|
| `type` | string | message type (below) |
| `v` | int | protocol version, `1` |
| `seq` | int | sender's message counter, starts at 1 per connection |
| `t` | float | sender's clock in seconds (Unity: realtime since start; Python: `time.monotonic()`); used only by the sender |

## Conventions

- Floor coordinates `x`, `z` in metres (Unity world, `y` up). Heading = Unity yaw in degrees, 0 = +z, 90 = +x.
- Angles relative to the robot (`bearing_deg`, `pan_yaw_deg`): degrees, 0 = straight ahead, + = to the right.
- Turn rate `w_dps`: degrees per second, + = turning right.
- Gesture camera: 730 x 530 px, vertical FOV 60 deg, square pixels: fx = fy = 265 / tan(30 deg) = 458.99,
  cx = 365, cy = 265 (pixel centres at index + 0.5), level (pitch = roll = 0), height 1.2 m.
- 360 deg image: equirectangular, width = 2 x height, **world-aligned** (not rotated with the robot);
  the centre column looks along world +z and world yaw grows to the right: for pixel column u (0-based,
  centre at u + 0.5), world yaw = ((u + 0.5) / width - 0.5) * 360 deg (Unity yaw: 0 = +z, 90 = +x).
  Measured 2026-10-20 with a red marker at world +x, found at column 1535 of 2048 (89.8 deg).
  Bearing relative to the robot = world yaw - `robot.heading_deg` (wrapped to -180..180).
- Commands (gestures): `NONE, LEFT, FORWARD_LEFT, FORWARD, FORWARD_RIGHT, RIGHT, STOP`, from the robot's
  point of view.

## Unity -> Python

### `hello` (first message after connecting)

```json
{"type": "hello", "v": 1, "seq": 1, "t": 12.5,
 "client": "unity", "unity_version": "2022.3.62f3", "config_sha256": "…",
 "perception_mode": "scripted baseline (link in shadow mode)",
 "gesture_camera": {"width": 730, "height": 530, "vfov_deg": 60, "fx": 458.99, "fy": 458.99,
                    "cx": 365, "cy": 265, "height_m": 1.2},
 "cam360": {"width": 1024, "height": 512, "height_m": 1.5, "projection": "equirect_world_aligned",
            "plus_x_column": "right_of_centre (world yaw = (u / width - 0.5) * 360 deg)"}}
```

### `observation` (every `send_interval_s`, 0.1 s)

```json
{"type": "observation", "v": 1, "seq": 42, "t": 16.6, "t_sim": 4.1,
 "robot": {"x": 6.25, "z": -6.0, "heading_deg": 0.0, "v": 0.95, "w_dps": 0.0},
 "state": "Navigate", "pan_yaw_deg": 0.0,
 "images": [{"name": "gesture", "format": "jpeg", "width": 730, "height": 530, "bytes": 51234},
            {"name": "cam360",  "format": "jpeg", "width": 1024, "height": 512, "bytes": 88001}]}
```

Since Step 4 the `cam360` image is a horizon band of the 2048 x 1024 panorama (default +30 to -60 deg
elevation, 2048 x 512) and its entry carries `"elevation_top_deg"` and `"elevation_bottom_deg"`; row v (0 =
top) has elevation top - (v + 0.5) / height * (top - bottom). Without these fields the image is the full
+90..-90 panorama. Columns still cover the full 360 deg (world-aligned).

`images` may be empty (rendering unavailable). Nothing in an observation is ground truth about people or
gestures; true positions never leave Unity's scoring code.

### `bye`

`{"type": "bye", "v": 1, "seq": 99, "t": 80.0, "reason": "play mode stopped"}`

## Python -> Unity

### `hello_ack`

`{"type": "hello_ack", "v": 1, "seq": 1, "t": 1001.2, "server": "robot_vision", "perception": "stub"}`

### `perception` (one per observation)

```json
{"type": "perception", "v": 1, "seq": 42, "t": 1005.3, "ack_seq": 42,
 "label": "vision (YOLO11s-pose arm direction + MediaPipe STOP)",
 "people": [{"track_id": 3, "bearing_deg": 12.5, "distance_m": 4.2, "distance_source": "ankles", "confidence": 0.91}],
 "target": {"track_id": 3, "bearing_deg": 12.5, "distance_m": 4.2, "distance_source": "ankles", "confidence": 0.91},
 "gesture": {"command": "FORWARD_LEFT", "confidence": 0.88, "source": "arm", "why": "ok",
             "right_arm_deg": -999.0, "left_arm_deg": -43.1},
 "inference": [{"model": "jpeg_decode", "ms": 3.1}, {"model": "yolo11s-pose/cam360", "ms": 38.0},
               {"model": "yolo11s-pose/gesture", "ms": 33.5}, {"model": "mediapipe/stop", "ms": 17.9}],
 "inference_total_ms": 95.2}
```

`ack_seq` echoes the observation's `seq`; Unity computes the round-trip delay from its own send time of
that `seq`. `inference_total_ms` covers decoding and all models for that observation.

Fields added in Step 4 (still protocol v1: only new fields, all optional for the receiver):
- `people[].distance_source`: `ankles` (feet keypoints on the floor), `box_bottom` (bottom of the box; too far
  if the feet are hidden) or `unknown`; `distance_m` is `-1` when unknown. Bearings are relative to the robot
  pose sent with the observation `ack_seq` (Unity keeps that pose per `seq`).
- `target`: the chosen (nearest) person, `track_id` -1 when nobody is seen.
- `gesture.source` (`arm`, `mediapipe` for STOP, `none`), `gesture.why`, the two arm angles (image angle from
  straight up, + = image right; -999 = not measured).
- `inference[].model` names: `jpeg_decode`, `yolo11s-pose/cam360`, `yolo11s-pose/gesture`, `mediapipe/stop`.

The stub (`perception: "stub"` in bridge.json) sends the same message with no people, `target.track_id` -1
and gesture NONE. When Python has several observations waiting, it answers only the newest one; the older
ones get no reply (logged as `observation_skipped`).

### `heartbeat`

`{"type": "heartbeat", "v": 1, "seq": 7, "t": 1002.0}`, sent whenever Python has sent nothing for
`heartbeat_s` (0.1 s).

### `command` (reserved for Step 5; Unity ignores it until then)

`{"type": "command", "v": 1, "seq": 50, "t": 1006.0, "v_mps": 0.6, "w_dps": -12.0}`

## Watchdog

Unity treats *any* frame from Python as a sign of life. When `link_required` is true and nothing has
arrived for `watchdog_s` (0.3 s), `DiffDriveRobot` brakes to a stop by itself (emergency deceleration) and
the run log marks `watchdog_stop`. Python's heartbeat (0.1 s) keeps a silent-but-healthy server alive.
