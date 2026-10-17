"""make_demo_video.py: still selection, labels, frame layout and the MP4 writer round trip. No dataset or run
folders needed. Run from robot_vision/:  python -m unittest discover -s tests -v"""

import json
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import make_demo_video as mdv  # noqa: E402

CFG = json.loads((ROOT / "configs" / "demo_video.json").read_text(encoding="utf-8"))


def dec(name, t=0.0, persons=(), reason="r", track_ids=()):
    return {"timestamp": t, "decision": name, "rule": 1, "reason": reason, "track_ids": list(track_ids),
            "snapshot": {"persons": list(persons), "gestures": [{"track_id": "op", "gesture": "MOVE"}]}}


def person(tid, **kw):
    return {"track_id": tid, "observed": True, "distance_m": 2.5, "motion_label": "approaching",
            "in_stop_zone": False, "in_caution_zone": False, "entry_in_s": None, **kw}


class StillTests(unittest.TestCase):
    seq = [dec(n) for n in "WAIT WAIT MOVE STOP STOP STOP MOVE MOVE MOVE MOVE WAIT".split()]

    def test_longest_runs(self):
        self.assertEqual(mdv.longest_runs(self.seq), {"WAIT": (0, 2), "MOVE": (6, 10), "STOP": (3, 6)})

    def test_default_stills_are_middle_of_longest_run(self):
        st = mdv.pick_stills(self.seq, {})
        self.assertEqual({k: v["index"] for k, v in st.items()}, {"STOP": 4, "MOVE": 7, "WAIT": 0})

    def test_stills_prefer_frames_with_a_person(self):
        seen = [person(1)]
        seq = [dec("MOVE"), dec("MOVE"), dec("MOVE"), dec("MOVE", persons=seen), dec("STOP"),
               dec("MOVE", persons=seen), dec("MOVE", persons=seen), dec("MOVE", persons=[person(2, observed=False)])]
        self.assertEqual(mdv.longest_runs(seq, mdv.person_visible), {"MOVE": (5, 7)})
        st = mdv.pick_stills(seq, {})
        self.assertEqual((st["MOVE"]["index"], st["STOP"]["index"]), (5, 4))
        self.assertIn("no frame of it shows a person", st["STOP"]["chosen_by"])

    def test_override_must_match_the_decision(self):
        self.assertEqual(mdv.pick_stills(self.seq, {"WAIT": 10})["WAIT"]["index"], 10)
        with self.assertRaises(SystemExit):
            mdv.pick_stills(self.seq, {"WAIT": 4})

    def test_parse_stills(self):
        self.assertEqual(mdv.parse_stills(["STOP=12", "MOVE=3"]), {"STOP": 12, "MOVE": 3})
        for bad in ["GO=1", "STOP=x", "STOP"]:
            with self.assertRaises(SystemExit):
                mdv.parse_stills([bad])


class LabelTests(unittest.TestCase):
    def test_person_text(self):
        self.assertEqual(mdv.person_text(person(7, motion_label="moving_lateral")), "ID 7 | 2.50 m | moving lateral")
        self.assertEqual(mdv.person_text(person(7, distance_m=None, distance_lower_bound_m=4.0, motion_label=None)),
                         "ID 7 | >= 4.00 m | unknown")
        self.assertEqual(mdv.person_text(person(7, distance_m=None)), "ID 7 | distance unknown | approaching")

    def test_box_colour_by_zone(self):
        c = CFG["colors_bgr"]
        self.assertEqual(mdv.box_colour(person(1, in_stop_zone=True), c), tuple(c["box_stop_zone"]))
        self.assertEqual(mdv.box_colour(person(1, entry_in_s=0.4), c), tuple(c["box_caution"]))
        self.assertEqual(mdv.box_colour(person(1, in_caution_zone=True), c), tuple(c["box_caution"]))
        self.assertEqual(mdv.box_colour(person(1), c), tuple(c["box_other"]))

    def test_label_stays_inside_the_frame(self):
        self.assertEqual(mdv.place_label((100, 20), (950, 300, 990, 500), (1000, 800), [], 2), (900, 278, 1000, 298))
        self.assertEqual(mdv.place_label((100, 20), (-5, 5, 40, 500), (1000, 800), [], 2), (0, 7, 100, 27))

    def test_labels_never_overlap(self):
        placed = []
        for box in [(500, 300, 540, 400), (480, 310, 520, 420), (510, 305, 560, 410)]:
            placed.append(mdv.place_label((120, 20), box, (1000, 800), placed, 2))
        for i, a in enumerate(placed):
            for b in placed[i + 1:]:
                self.assertTrue(a[2] <= b[0] or b[2] <= a[0] or a[3] <= b[1] or b[3] <= a[1], (a, b))
            self.assertTrue(0 <= a[0] and a[2] <= 1000 and 0 <= a[1] and a[3] <= 800)

    def test_wrap_keeps_every_word(self):
        text = "person entering stop zone: track 382 predicted to enter in 0.10 s (within 3.0 s), 0.02 m away"
        lines = mdv.wrap(text, 200, 0.5, 1)
        self.assertGreater(len(lines), 1)
        self.assertEqual(" ".join(lines), text)


class RenderAndVideoTests(unittest.TestCase):
    def frames(self):
        rgb = np.full((53, 73, 3), 90, np.uint8)
        seq = [dec("STOP", 0.0, [person(3, in_stop_zone=True), person(4, observed=False)], "x " * 40, [3]),
               dec("MOVE", 0.1, [person(3)]), dec("WAIT", 0.2)]
        cfg = {**CFG, "scale": 2}
        width = 73 * 2
        rows = max(len(mdv.banner_lines(d, width, 2.0)) for d in seq)
        strip = mdv.timeline_strip(seq, width, 18, cfg["colors_bgr"])
        boxes = {3: (10.0, 10.0, 30.0, 40.0)}
        return [mdv.render(rgb, d, boxes, i, len(seq), strip, cfg, rows) for i, d in enumerate(seq)]

    def test_frames_have_one_even_size(self):
        imgs = self.frames()
        self.assertEqual(len({im.shape for im in imgs}), 1)
        h, w, _ = imgs[0].shape
        self.assertEqual((h % 2, w % 2), (0, 0))
        self.assertGreater(h, 53 * 2)

    def test_decision_colour_in_banner(self):
        for im, name in zip(self.frames(), ("STOP", "MOVE", "WAIT")):
            self.assertEqual(tuple(int(v) for v in im[5, 2]), tuple(CFG["colors_bgr"][name]))

    def test_mp4_round_trip(self):
        imgs = self.frames()
        h, w, _ = imgs[0].shape
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "t.mp4"
            writer, codec = mdv.open_writer(path, 10.0, (w, h), CFG["codec_preference"])
            for _ in range(4):
                for im in imgs:
                    writer.write(im)
            writer.release()
            probe = mdv.probe_video(path)
        self.assertIn(codec, CFG["codec_preference"])
        self.assertTrue(probe["readable"])
        self.assertEqual((probe["width"], probe["height"], probe["frames"]), (w, h, 12))


if __name__ == "__main__":
    unittest.main()
