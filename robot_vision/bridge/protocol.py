"""Bridge protocol (docs/protocol.md): framing, schema and validation, shared by the server and its tests.

Message = 4-byte big-endian header length + UTF-8 JSON header + attachments (sizes listed in the header).
FramingError and VersionError end the connection; MessageError rejects one message and keeps it.
"""

from __future__ import annotations

import asyncio
import json
import math
import struct
from dataclasses import dataclass, field

PROTOCOL_VERSION = 1
LENGTH = struct.Struct(">I")

# Keys that would carry goal B (or any end-point coordinate) to Python. Rejected at any depth.
FORBIDDEN_KEYS = frozenset({"goal", "goal_point", "goal_x", "goal_z", "end_point", "end_point_x", "end_point_z",
                            "point_b", "b"})

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
                  "nav_target_x": NUM, "nav_target_z": NUM, "nav_status": STR, "nav_corners": [CORNER],
                  "last_command_seq": INT, "rtt_telemetry_seq": INT, "rtt_ms": NUM, "watchdog_stopped": BOOL,
                  "watchdog_count": INT, "keyboard_override": BOOL},
    "frame_360": {"time_s": NUM, "frame_index": INT, "width": INT, "height": INT, "camera_height_m": NUM,
                  "centre_world_yaw_deg": NUM, "centre_yaw_status": STR, "pose": POSE, "encoding": STR},
    "frame_pan_tilt": {"time_s": NUM, "frame_index": INT, "width": INT, "height": INT, "fx": NUM, "fy": NUM,
                       "cx": NUM, "cy": NUM, "vertical_fov_deg": NUM, "pan_deg": NUM, "tilt_deg": NUM,
                       "camera_height_m": NUM, "pose": POSE, "encoding": STR},
    # Python -> Unity
    "command": {"reply_to": INT, "v": NUM, "omega": NUM, "pan_deg": NUM, "has_target": BOOL, "target_x": NUM,
                "target_z": NUM, "state": STR, "screen_text": STR},
    "error": {"error": STR, "fatal": BOOL},
}
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

    @classmethod
    def from_config(cls, cfg: dict) -> "Limits":
        return cls(int(cfg["max_header_bytes"]), int(cfg["max_attachment_bytes"]), int(cfg["protocol_version"]))


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


def _forbidden_keys(obj, path: str = "") -> list[str]:
    found = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k.lower() in FORBIDDEN_KEYS:
                found.append(f"{path}{k}")
            found += _forbidden_keys(v, f"{path}{k}.")
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            found += _forbidden_keys(v, f"{path}{i}.")
    return found


def validate(msg: Message, allowed_types: frozenset[str]) -> None:
    """Check a framed message against SCHEMAS. Raises MessageError."""
    h = msg.header
    t = h.get("type")
    if not isinstance(t, str) or t not in allowed_types:
        raise MessageError(f"unknown or unexpected message type {t!r}")
    if not _is_int(h.get("seq")) or h["seq"] < 0:
        raise MessageError(f"{t}: 'seq' must be an integer >= 0")
    _check_fields(h, SCHEMAS[t], t)
    if t in FROM_UNITY:
        bad = _forbidden_keys(h)
        if bad:
            raise MessageError(f"{t}: forbidden goal field(s) {bad}; Python never receives B")
    for name in REQUIRED_ATTACHMENTS.get(t, ()):
        if name not in msg.attachments:
            raise MessageError(f"{t}: missing attachment {name!r}")
    if t in ("frame_360", "frame_pan_tilt"):
        if h["encoding"] != "jpeg" or not msg.attachments["image"].startswith(JPEG_MAGIC):
            raise MessageError(f"{t}: image is not a JPEG")
        if h["width"] <= 0 or h["height"] <= 0:
            raise MessageError(f"{t}: bad image size")
    if t == "telemetry" and h["nav_status"] not in NAV_STATUSES:
        raise MessageError(f"telemetry: unknown nav_status {h['nav_status']!r}")
