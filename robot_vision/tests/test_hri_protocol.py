"""Protocol v1 framing (hri_protocol.py) and the golden frame shared with the Unity tests. No Unity, no network."""

import json
import struct
import unittest
from pathlib import Path

import hri_protocol as hp

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "hri_frame_v1.frame"
# The exact header bytes inside the golden frame (also checked by HriProtocolTests.cs in Unity).
GOLDEN_HEADER = (
    '{"type":"observation","v":1,"seq":42,"t":16.625,"t_sim":4.1,'
    '"robot":{"x":6.25,"z":-6.0,"heading_deg":90.0,"v":0.95,"w_dps":-12.5},'
    '"state":"Read","pan_yaw_deg":-30.0,"note":"µ utf-8 check",'
    '"images":[{"name":"gesture","format":"jpeg","width":730,"height":530,"bytes":12},'
    '{"name":"cam360","format":"jpeg","width":1024,"height":512,"bytes":5}]}').encode("utf-8")
GOLDEN_IMAGES = [b"\xff\xd8gesture\xff\xd9\x00", b"\xff\xd8360"]


def obs(seq=1, images=()):
    entries = [{"name": f"img{i}", "format": "jpeg", "width": 2, "height": 2, "bytes": len(b)}
               for i, b in enumerate(images)]
    return hp.message("observation", seq, 1.5, images=entries)


class FramingTests(unittest.TestCase):
    def test_golden_frame_is_stable(self):
        self.assertEqual(hp.encode_raw(GOLDEN_HEADER, GOLDEN_IMAGES), FIXTURE.read_bytes())

    def test_golden_frame_decodes(self):
        data = FIXTURE.read_bytes()
        frame, used = hp.decode(data)
        self.assertEqual(used, len(data))
        self.assertEqual(struct.unpack(">I", data[:4])[0], len(GOLDEN_HEADER))  # big-endian length
        self.assertEqual(frame.header["seq"], 42)
        self.assertEqual(frame.header["robot"]["heading_deg"], 90.0)
        self.assertEqual(frame.header["note"], "µ utf-8 check")
        self.assertEqual(frame.images, GOLDEN_IMAGES)

    def test_round_trip_with_and_without_images(self):
        for images in ([], [b"abc"], [b"\x00" * 1000, b"xyz"]):
            frame, used = hp.decode(hp.encode(obs(images=images), images))
            self.assertEqual(frame.images, list(images))
            self.assertEqual(frame.header["type"], "observation")

    def test_incomplete_frame_is_rejected(self):
        data = hp.encode(obs(images=[b"abcdef"]), [b"abcdef"])
        for cut in (2, 6, len(data) - 1):
            with self.assertRaises(hp.ProtocolError):
                hp.decode(data[:cut])

    def test_image_count_and_length_must_match_header(self):
        h = obs(images=[b"abc"])
        with self.assertRaises(hp.ProtocolError):
            hp.encode(h, [])
        with self.assertRaises(hp.ProtocolError):
            hp.encode(h, [b"abcd"])
        bad = hp.encode_raw(json.dumps(h).encode(), [b"abcd"])  # header says 3 bytes, frame carries 4
        with self.assertRaises(hp.ProtocolError):
            hp.decode(bad)

    def test_limits_and_bad_headers(self):
        with self.assertRaises(hp.ProtocolError):
            hp.decode(struct.pack(">I", hp.MAX_HEADER + 1) + b"x")
        with self.assertRaises(hp.ProtocolError):
            hp.decode(hp.encode_raw(b"not json"))
        with self.assertRaises(hp.ProtocolError):
            hp.decode(hp.encode_raw(b'{"type":"observation","v":2,"seq":1,"t":0}'))  # wrong version
        with self.assertRaises(hp.ProtocolError):
            hp.decode(hp.encode_raw(b'[1, 2]'))

    def test_numpy_scalars_are_encoded(self):
        import numpy as np
        h = hp.perception_reply(1, 0.0, ack_seq=1, label="x", confidence=np.float32(0.5),
                                people=[{"bearing_deg": np.float32(12.5), "distance_m": np.float64(3.0), "track_id": np.int64(2)}])
        frame, _ = hp.decode(hp.encode(h))
        self.assertEqual(frame.header["people"][0], {"bearing_deg": 12.5, "distance_m": 3.0, "track_id": 2})
        self.assertEqual(frame.header["gesture"]["confidence"], 0.5)

    def test_perception_reply(self):
        r = hp.perception_reply(5, 2.0, ack_seq=42, label="stub", command="LEFT",
                                inference=[{"model": "a", "ms": 1.5}, {"model": "b", "ms": 2.0}])
        self.assertEqual((r["type"], r["ack_seq"], r["gesture"]["command"]), ("perception", 42, "LEFT"))
        self.assertAlmostEqual(r["inference_total_ms"], 3.5)
        self.assertAlmostEqual(hp.perception_reply(1, 0, 1, "x", total_ms=9.0)["inference_total_ms"], 9.0)
        with self.assertRaises(ValueError):
            hp.perception_reply(1, 0, 1, "x", command="MOVE")

    def test_commands_match_unity_enum(self):
        enum = (Path(__file__).resolve().parents[2] / "unity" / "Robotics-Warehouse" / "WarehouseProjectURP" /
                "Assets" / "Scripts" / "WarehouseHRI" / "GestureCommand.cs").read_text(encoding="utf-8")
        for i, name in enumerate(hp.COMMANDS):
            self.assertIn(f"{name} = {i},", enum)


class PanoramaTests(unittest.TestCase):
    def test_measured_axis(self):
        # Measured in Unity: world +x at column 1535 of 2048, world +z at the centre.
        self.assertAlmostEqual(hp.pano_world_yaw(1535, 2048), 90.0, delta=0.2)
        self.assertAlmostEqual(hp.pano_world_yaw(1023.5, 2048), 0.0, delta=1e-9)

    def test_bearing_relative_to_heading(self):
        self.assertAlmostEqual(hp.pano_bearing(1535, 2048, 90.0), 0.0, delta=0.2)   # facing +x, target at +x
        self.assertAlmostEqual(hp.pano_bearing(1535, 2048, 0.0), 90.0, delta=0.2)   # facing +z: target on the right
        self.assertAlmostEqual(hp.pano_bearing(511, 2048, 0.0), -90.0, delta=0.2)   # -x: on the left
        b = hp.pano_bearing(0, 2048, 0.0)
        self.assertTrue(-180.0 <= b < 180.0)


if __name__ == "__main__":
    unittest.main()
