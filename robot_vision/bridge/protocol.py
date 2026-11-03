"""Bridge protocol (docs/protocol.md version 2, docs/protocol_v3.md version 3): framing, schema and validation,
shared by the server and its tests. The version a connection speaks comes from its bridge config (configs/bridge.json
= 2, configs/v4/bridge.json = 3); version 2 is unchanged by version 3.

Message = 4-byte big-endian header length + UTF-8 JSON header + attachments (sizes listed in the header).
FramingError and VersionError end the connection; MessageError rejects one message and keeps it.
"""

from __future__ import annotations

import asyncio
import json
import math
import struct
from dataclasses import dataclass, field

PROTOCOL_VERSION = 2          # the default (v3 study); a version 3 config selects the v4 schemas
SUPPORTED_VERSIONS = (2, 3)
LENGTH = struct.Struct(">I")

# Keys that would carry goal B (or any end-point coordinate) to Python. Rejected at any depth.
FORBIDDEN_KEYS = frozenset({"goal", "goal_point", "goal_x", "goal_z", "end_point", "end_point_x", "end_point_z",
                            "point_b", "b"})

# Version 3 (v4 study) also rejects keys that would carry ground truth about the workers, at any depth.
TRUTH_KEYS = frozenset({"true_gesture", "true_commander", "commander_truth", "gesture_truth", "worker_label", "truth"})
FORBIDDEN_KEYS_V3 = FORBIDDEN_KEYS | TRUTH_KEYS

NUM, INT, STR, BOOL = "number", "int", "string", "bool"
POSE = {"x": NUM, "z": NUM, "yaw_deg": NUM}
CORNER = {"x": NUM, "z": NUM}

# Required fields per message type (beyond the envelope: version, type, seq, attachments). Extra fields are allowed.
SCHEMAS: dict[str, dict] = {
    # Unity -> Python
    "hello": {"time_s": NUM, "client": STR, "unity_version": STR, "telemetry_hz": NUM, "frame_360_hz": NUM,
              "frame_pan_tilt_hz": NUM, "watchdog_timeout_s": NUM},
    "telemetry": {"time_s": NUM, "pose": POSE, "v": NUM, "omega": NUM, "v_cmd": NUM, "omega_cmd": NUM,
                  "pan_deg": NUM, "collision_count": INT, "reached_end_point": BOOL, "nav_has_target": BOOL,
                  "nav_target_x": NUM, "nav_target_z": NUM, "nav_status": STR, "nav_start_snap_m": NUM,
                  "nav_target_snap_m": NUM, "nav_corners": [CORNER], "last_command_seq": INT, "rtt_telemetry_seq": INT,
                  "rtt_ms": NUM, "watchdog_stopped": BOOL, "watchdog_count": INT, "keyboard_override": BOOL,
                  "estop": BOOL, "frames_360_sent": INT, "frames_360_dropped": INT, "frames_pan_tilt_sent": INT,
                  "frames_pan_tilt_dropped": INT},
    "frame_360": {"time_s": NUM, "frame_index": INT, "width": INT, "height": INT, "camera_height_m": NUM,
                  "centre_world_yaw_deg": NUM, "pose": POSE, "encoding": STR},
    "frame_pan_tilt": {"time_s": NUM, "frame_index": INT, "width": INT, "height": INT, "fx": NUM, "fy": NUM,
                       "cx": NUM, "cy": NUM, "vertical_fov_deg": NUM, "pan_deg": NUM, "tilt_deg": NUM,
                       "camera_height_m": NUM, "pose": POSE, "encoding": STR},
    # Python -> Unity
    "command": {"reply_to": INT, "v": NUM, "omega": NUM, "pan_deg": NUM, "has_target": BOOL, "target_x": NUM,
                "target_z": NUM, "state": STR, "screen_text": STR},
    "error": {"error": STR, "fatal": BOOL},
}

# Version 3: the command gains vertical_fov_deg (pan-tilt zoom) and the hud block (docs/protocol_v3.md).
GESTURES_V3 = frozenset({"POINT", "WAIT", "STOP", "NONE"})
HUD_PERSON = {"id": INT, "bearing_deg": NUM, "distance_m": NUM, "is_commander": BOOL}
HUD_LOG_ENTRY = {"dir": STR, "type": STR, "seq": INT, "text": STR}
HUD = {"state": STR, "screen_text": STR, "commander_id": INT, "gesture": STR, "gesture_score": NUM,
       "gesture_raw": STR, "gesture_accepted": STR, "point_angle_deg": NUM, "people": [HUD_PERSON],
       "log": [HUD_LOG_ENTRY]}
SCHEMAS_V3: dict[str, dict] = {
    **SCHEMAS,
    "command": {**SCHEMAS["command"], "vertical_fov_deg": NUM, "hud": HUD},
}
SCHEMAS_BY_VERSION = {2: SCHEMAS, 3: SCHEMAS_V3}
FORBIDDEN_BY_VERSION = {2: FORBIDDEN_KEYS, 3: FORBIDDEN_KEYS_V3}
FROM_UNITY = frozenset({"hello", "telemetry", "frame_360", "frame_pan_tilt"})
TO_UNITY = frozenset({"command", "error"})
REQUIRED_ATTACHMENTS = {"frame_360": ("image",), "frame_pan_tilt": ("image",)}
NAV_STATUSES = frozenset({"none", "complete", "partial", "invalid", "start_off_navmesh", "target_off_navmesh",
                          "no_agent_type"})
JPEG_MAGIC = b"\xff\xd8"


class ProtocolError(Exception):
    """Base class."""


class FramingError(ProtocolError):
    """The byte stream cannot be trusted any more: close the connection."""


class VersionError(FramingError):
    """The peer speaks another protocol version: close the connection."""


class MessageError(ProtocolError):
    """One message is invalid; framing is intact, so the connection can continue."""


@dataclass(frozen=True)
class Limits:
    max_header_bytes: int
    max_attachment_bytes: int
    version: int = PROTOCOL_VERSION
    intrinsics_rel_tol: float = 1e-3     # version 3 only: frame_pan_tilt intrinsics vs vertical_fov_deg

    @classmethod
    def from_config(cls, cfg: dict) -> "Limits":
        return cls(int(cfg["max_header_bytes"]), int(cfg["max_attachment_bytes"]), int(cfg["protocol_version"]),
                   float(cfg.get("intrinsics_rel_tol", 1e-3)))


@dataclass
class Message:
    header: dict
    attachments: dict[str, bytes] = field(default_factory=dict)

    @property
    def type(self) -> str:
        return self.header["type"]

    @property
    def seq(self) -> int:
        return self.header["seq"]


def encode(header: dict, attachments: dict[str, bytes] | None = None, version: int = PROTOCOL_VERSION) -> bytes:
    """Frame one message. Fills in version and the attachment list; header must already hold type and seq."""
    attachments = attachments or {}
    h = {**header, "version": version, "attachments": [{"name": n, "size": len(b)} for n, b in attachments.items()]}
    hb = json.dumps(h, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode("utf-8")
    return LENGTH.pack(len(hb)) + hb + b"".join(attachments.values())


def _is_int(x) -> bool:
    return isinstance(x, int) and not isinstance(x, bool)


def _is_num(x) -> bool:
    return (_is_int(x) or isinstance(x, float)) and math.isfinite(x)


def _reject_constant(name: str):
    raise ValueError(f"non-finite number {name}")


def parse_header(data: bytes, limits: Limits) -> tuple[dict, list[tuple[str, int]]]:
    """Decode and check the envelope. Raises FramingError / VersionError."""
    try:
        header = json.loads(data.decode("utf-8"), parse_constant=_reject_constant)
    except (UnicodeDecodeError, ValueError) as e:
        raise FramingError(f"header is not valid UTF-8 JSON: {e}") from None
    if not isinstance(header, dict):
        raise FramingError("header is not a JSON object")
    version = header.get("version")
    if not _is_int(version):
        raise FramingError("header has no integer 'version'")
    if version != limits.version:
        raise VersionError(f"protocol version {version}, expected {limits.version}")
    specs = header.get("attachments")
    if not isinstance(specs, list):
        raise FramingError("header has no 'attachments' list")
    out, names, total = [], set(), 0
    for s in specs:
        if not (isinstance(s, dict) and isinstance(s.get("name"), str) and _is_int(s.get("size"))):
            raise FramingError(f"bad attachment entry {s!r}")
        if s["size"] < 0 or s["name"] in names:
            raise FramingError(f"bad attachment entry {s!r} (negative size or duplicate name)")
        names.add(s["name"])
        total += s["size"]
        out.append((s["name"], s["size"]))
    if total > limits.max_attachment_bytes:
        raise FramingError(f"attachments total {total} bytes > max_attachment_bytes {limits.max_attachment_bytes}")
    return header, out


async def read_message(reader: asyncio.StreamReader, limits: Limits) -> Message | None:
    """Next message, or None on a clean end of stream between messages. Raises FramingError / VersionError."""
    try:
        prefix = await reader.readexactly(LENGTH.size)
    except asyncio.IncompleteReadError as e:
        if not e.partial:
            return None
        raise FramingError("stream ended inside the length prefix") from None
    (n,) = LENGTH.unpack(prefix)
    if n == 0 or n > limits.max_header_bytes:
        raise FramingError(f"header length {n} outside 1..{limits.max_header_bytes}")
    try:
        header, specs = parse_header(await reader.readexactly(n), limits)
        attachments = {name: await reader.readexactly(size) for name, size in specs}
    except asyncio.IncompleteReadError:
        raise FramingError("stream ended inside a message") from None
    return Message(header, attachments)


def decode(data: bytes, limits: Limits) -> tuple[Message, int]:
    """Decode one message from the start of data. Returns (message, bytes used). For tests and offline tools."""
    if len(data) < LENGTH.size:
        raise FramingError("incomplete length prefix")
    (n,) = LENGTH.unpack_from(data)
    if n == 0 or n > limits.max_header_bytes:
        raise FramingError(f"header length {n} outside 1..{limits.max_header_bytes}")
    end = LENGTH.size + n
    if len(data) < end:
        raise FramingError("incomplete header")
    header, specs = parse_header(data[LENGTH.size:end], limits)
    attachments = {}
    for name, size in specs:
        if len(data) < end + size:
            raise FramingError(f"incomplete attachment {name!r}")
        attachments[name] = data[end:end + size]
        end += size
    return Message(header, attachments), end


def _check_fields(obj: dict, schema: dict, where: str) -> None:
    for key, kind in schema.items():
        if key not in obj:
            raise MessageError(f"{where}: missing field {key!r}")
        v, path = obj[key], f"{where}.{key}"
        if isinstance(kind, dict):
            if not isinstance(v, dict):
                raise MessageError(f"{path}: expected an object")
            _check_fields(v, kind, path)
        elif isinstance(kind, list):
            if not isinstance(v, list):
                raise MessageError(f"{path}: expected a list")
            for i, item in enumerate(v):
                if not isinstance(item, dict):
                    raise MessageError(f"{path}[{i}]: expected an object")
                _check_fields(item, kind[0], f"{path}[{i}]")
        elif not {NUM: _is_num, INT: _is_int, STR: lambda x: isinstance(x, str),
                  BOOL: lambda x: isinstance(x, bool)}[kind](v):
            raise MessageError(f"{path}: expected {kind}, got {type(v).__name__}")


def _forbidden_keys(obj, path: str = "", keys: frozenset = FORBIDDEN_KEYS) -> list[str]:
    found = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k.lower() in keys:
                found.append(f"{path}{k}")
            found += _forbidden_keys(v, f"{path}{k}.", keys)
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            found += _forbidden_keys(v, f"{path}{i}.", keys)
    return found


def _check_v3(t: str, h: dict, rel_tol: float) -> None:
    """Version 3 checks beyond field types."""
    if t == "frame_pan_tilt":
        fov, w, ht = h["vertical_fov_deg"], h["width"], h["height"]
        if not 0.0 < fov < 180.0:
            raise MessageError(f"frame_pan_tilt: vertical_fov_deg {fov} outside (0, 180)")
        fy = (ht / 2.0) / math.tan(math.radians(fov) / 2.0)
        for name, want in (("fy", fy), ("fx", fy), ("cx", w / 2.0), ("cy", ht / 2.0)):
            if abs(h[name] - want) > rel_tol * abs(want):
                raise MessageError(f"frame_pan_tilt: {name} {h[name]} does not match vertical_fov_deg {fov} "
                                   f"and size {w}x{ht} (expected {want:.4f}, relative tolerance {rel_tol})")
    elif t == "command":
        fov = h["vertical_fov_deg"]
        if fov != -1 and not 0.0 < fov < 180.0:
            raise MessageError(f"command: vertical_fov_deg {fov} must be -1 (keep) or in (0, 180)")
        hud = h["hud"]
        if hud["gesture"] not in GESTURES_V3:
            raise MessageError(f"command: hud.gesture {hud['gesture']!r} not in {sorted(GESTURES_V3)}")
        if hud["commander_id"] < -1:
            raise MessageError("command: hud.commander_id must be -1 (none) or an id >= 0")


def validate(msg: Message, allowed_types: frozenset[str], limits: Limits | None = None) -> None:
    """Check a framed message against the schemas of its protocol version (SCHEMAS or SCHEMAS_V3). Raises MessageError."""
    h = msg.header
    version = h.get("version", PROTOCOL_VERSION)
    if version not in SCHEMAS_BY_VERSION:
        raise MessageError(f"unsupported protocol version {version!r}")
    t = h.get("type")
    if not isinstance(t, str) or t not in allowed_types:
        raise MessageError(f"unknown or unexpected message type {t!r}")
    if not _is_int(h.get("seq")) or h["seq"] < 0:
        raise MessageError(f"{t}: 'seq' must be an integer >= 0")
    _check_fields(h, SCHEMAS_BY_VERSION[version][t], t)
    if t in FROM_UNITY:
        bad = _forbidden_keys(h, keys=FORBIDDEN_BY_VERSION[version])
        if bad:
            raise MessageError(f"{t}: forbidden goal or truth field(s) {bad}; Python never receives B or ground truth")
    for name in REQUIRED_ATTACHMENTS.get(t, ()):
        if name not in msg.attachments:
            raise MessageError(f"{t}: missing attachment {name!r}")
    if t in ("frame_360", "frame_pan_tilt"):
        if h["encoding"] != "jpeg" or not msg.attachments["image"].startswith(JPEG_MAGIC):
            raise MessageError(f"{t}: image is not a JPEG")
        if h["width"] <= 0 or h["height"] <= 0:
            raise MessageError(f"{t}: bad image size")
    if version >= 3:
        _check_v3(t, h, limits.intrinsics_rel_tol if limits is not None else 1e-3)
    if t == "telemetry" and h["nav_status"] not in NAV_STATUSES:
        raise MessageError(f"telemetry: unknown nav_status {h['nav_status']!r}")
