"""Unity <-> Python message format, protocol v1 (docs/protocol.md). Standard library only.

A frame is: uint32 big-endian header length, UTF-8 JSON header, then for each entry of header["images"] a
uint32 big-endian length and that many bytes. The same framing is implemented in Unity (HriProtocol.cs); the
golden frame tests/fixtures/hri_frame_v1.frame is checked byte-for-byte on both sides.
"""

from __future__ import annotations

import json
import socket
import struct
from dataclasses import dataclass, field

VERSION = 1
MAX_HEADER = 1 << 20      # 1 MiB
MAX_IMAGE = 16 << 20      # 16 MiB
COMMANDS = ("NONE", "LEFT", "FORWARD_LEFT", "FORWARD", "FORWARD_RIGHT", "RIGHT", "STOP")
UNITY_TYPES = ("hello", "observation", "bye")
PYTHON_TYPES = ("hello_ack", "perception", "heartbeat", "command")

_U32 = struct.Struct(">I")


class ProtocolError(ValueError):
    """Malformed or oversized frame; the connection is closed."""


@dataclass
class Frame:
    header: dict
    images: list[bytes] = field(default_factory=list)


def encode_raw(header_json: bytes, images: list[bytes] = ()) -> bytes:
    """Frame from an already serialised header (used for the golden fixture)."""
    if len(header_json) > MAX_HEADER:
        raise ProtocolError(f"header too large: {len(header_json)} bytes")
    parts = [_U32.pack(len(header_json)), header_json]
    for img in images:
        if len(img) > MAX_IMAGE:
            raise ProtocolError(f"image too large: {len(img)} bytes")
        parts += [_U32.pack(len(img)), img]
    return b"".join(parts)


def encode(header: dict, images: list[bytes] = ()) -> bytes:
    """Serialise a header (compact JSON, UTF-8) and its images. header["images"] must describe them in order."""
    entries = header.get("images", [])
    if len(entries) != len(images):
        raise ProtocolError(f"header lists {len(entries)} images, {len(images)} given")
    for e, img in zip(entries, images):
        if e.get("bytes") != len(img):
            raise ProtocolError(f"image {e.get('name')!r}: header says {e.get('bytes')} bytes, got {len(img)}")
    return encode_raw(json.dumps(header, separators=(",", ":"), ensure_ascii=False).encode("utf-8"), images)


def _parse_header(raw: bytes) -> dict:
    try:
        header = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as e:
        raise ProtocolError(f"bad JSON header: {e}") from e
    if not isinstance(header, dict) or not isinstance(header.get("type"), str):
        raise ProtocolError("header is not an object with a 'type'")
    if header.get("v") != VERSION:
        raise ProtocolError(f"protocol version {header.get('v')!r}, expected {VERSION}")
    images = header.get("images", [])
    if not isinstance(images, list) or any(not isinstance(e, dict) or not isinstance(e.get("bytes"), int)
                                           for e in images):
        raise ProtocolError("'images' must be a list of objects with integer 'bytes'")
    return header


def decode(data: bytes) -> tuple[Frame, int]:
    """Decode one frame from the start of data. Returns (frame, bytes used); raises ProtocolError if incomplete."""
    pos = 0

    def take(n: int) -> bytes:
        nonlocal pos
        if pos + n > len(data):
            raise ProtocolError("incomplete frame")
        chunk = data[pos:pos + n]
        pos += n
        return chunk

    (hlen,) = _U32.unpack(take(4))
    if hlen > MAX_HEADER:
        raise ProtocolError(f"header length {hlen} exceeds {MAX_HEADER}")
    header = _parse_header(take(hlen))
    images = []
    for e in header.get("images", []):
        (n,) = _U32.unpack(take(4))
        if n > MAX_IMAGE or n != e["bytes"]:
            raise ProtocolError(f"image {e.get('name')!r}: length {n}, header says {e['bytes']}")
        images.append(take(n))
    return Frame(header, images), pos


def _recv_exact(sock: socket.socket, n: int) -> bytes:
    buf = bytearray()
    while len(buf) < n:
        chunk = sock.recv(min(n - len(buf), 1 << 20))
        if not chunk:
            raise ConnectionError("connection closed")
        buf += chunk
    return bytes(buf)


def read_frame(sock: socket.socket) -> Frame:
    """Read one complete frame from a socket (blocking, honours the socket timeout)."""
    (hlen,) = _U32.unpack(_recv_exact(sock, 4))
    if hlen > MAX_HEADER:
        raise ProtocolError(f"header length {hlen} exceeds {MAX_HEADER}")
    header = _parse_header(_recv_exact(sock, hlen))
    images = []
    for e in header.get("images", []):
        (n,) = _U32.unpack(_recv_exact(sock, 4))
        if n > MAX_IMAGE or n != e["bytes"]:
            raise ProtocolError(f"image {e.get('name')!r}: length {n}, header says {e['bytes']}")
        images.append(_recv_exact(sock, n))
    return Frame(header, images)


def send_frame(sock: socket.socket, header: dict, images: list[bytes] = ()) -> None:
    sock.sendall(encode(header, images))


def message(type_: str, seq: int, t: float, **fields) -> dict:
    """A header with the common fields."""
    return {"type": type_, "v": VERSION, "seq": seq, "t": t, **fields}


def perception_reply(seq: int, t: float, ack_seq: int, label: str, people: list[dict] | None = None,
                     command: str = "NONE", confidence: float = 0.0,
                     inference: list[dict] | None = None, total_ms: float | None = None) -> dict:
    """A perception message. total_ms (decoding + all models) defaults to the sum of the per-model times."""
    if command not in COMMANDS:
        raise ValueError(f"command {command!r} not in {COMMANDS}")
    inference = inference or []
    return message("perception", seq, t, ack_seq=ack_seq, label=label, people=people or [],
                   gesture={"command": command, "confidence": confidence}, inference=inference,
                   inference_total_ms=round(total_ms if total_ms is not None else sum(i["ms"] for i in inference), 3))


def pano_world_yaw(u: float, width: int) -> float:
    """World yaw (deg, Unity: 0 = +z, 90 = +x) of panorama column u; measured mapping, docs/protocol.md."""
    return ((u + 0.5) / width - 0.5) * 360.0


def pano_bearing(u: float, width: int, heading_deg: float) -> float:
    """Bearing of panorama column u relative to the robot heading, deg in [-180, 180), + = right."""
    return (pano_world_yaw(u, width) - heading_deg + 180.0) % 360.0 - 180.0
