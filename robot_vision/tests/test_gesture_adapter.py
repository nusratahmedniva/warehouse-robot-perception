"""Tests for the gesture adapter and its evaluation hook. No dataset, model or MediaPipe needed (two tests that
use the model skip when the submodule or MediaPipe is missing). Run from robot_vision/:
    python -m unittest discover -s tests -v"""

import ast
import json
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import gesture_adapter as ga  # noqa: E402
import gesture_eval as ge  # noqa: E402
from decision import GestureEvent  # noqa: E402

CFG = ga.load_gesture_config()
MAP = CFG["mapping"]
CROP = CFG["modes"]["person_crop"]
HER_FILE = ROOT.parent / "external" / "media_pipe_gesture" / "gesture_heuristics.py"
ADAPTER_FILES = ["gesture_adapter.py", "gesture_smoke.py", "gesture_eval.py"]


def hand(category, score=0.9, wrist=(0.5, 0.5), others=((0.4, 0.3), (0.6, 0.7))):
    return ga.RawHand(category, score, "Right", (wrist,) + tuple(others))


def imports(f: str) -> set[str]:
    tree = ast.parse((ROOT / f).read_text(encoding="utf-8"))
    mods = {a.name for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names}
    return mods | {n.module for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) and n.module}


class MappingTests(unittest.TestCase):
    def test_mapping_table(self):
        expected = {"Open_Palm": "STOP", "Closed_Fist": "STOP", "Pointing_Up": "MOVE", "Victory": "MOVE",
                    "Thumb_Up": "MOVE", "Thumb_Down": "NONE", "ILoveYou": "NONE", "None": "NONE",
                    "SomethingNew": "NONE", None: "NONE"}
        for cat, g in expected.items():
            self.assertEqual(ga.map_category(cat, MAP), g, cat)

    def test_every_model_category_has_a_mapping_result(self):
        mapped = set(MAP["STOP"]) | set(MAP["MOVE"])
        self.assertTrue(mapped <= set(CFG["model"]["categories"]))
        for c in CFG["model"]["categories"]:
            self.assertIn(ga.map_category(c, MAP), ("STOP", "MOVE", "NONE"))

    def test_config_cites_her_file_and_commit(self):
        self.assertEqual(CFG["source"]["file"], "gesture_heuristics.py")
        self.assertRegex(CFG["source"]["commit"], r"^[0-9a-f]{40}$")
        self.assertIn(CFG["source"]["commit"][:8], MAP["source"])

    def test_category_in_two_commands_refused(self):
        bad = json.loads((ROOT / "configs" / "gesture.json").read_text(encoding="utf-8"))
        bad["mapping"]["MOVE"].append("Open_Palm")
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "g.json"
            p.write_text(json.dumps(bad), encoding="utf-8")
            with self.assertRaises(ValueError):
                ga.load_gesture_config(p)

    @unittest.skipUnless(HER_FILE.exists(), "submodule external/media_pipe_gesture not checked out")
    def test_mapping_equals_her_file(self):
        src = HER_FILE.read_text(encoding="utf-8")
        lists = re.findall(r'gesture_name in \[([^\]]*)\]:\s*\n\s*latest_result\["gesture"\] = "(STOP|MOVE)"', src)
        her = {g: sorted(re.findall(r'"(\w+)"', names)) for names, g in lists}
        self.assertEqual(her, {"STOP": sorted(MAP["STOP"]), "MOVE": sorted(MAP["MOVE"])})
        self.assertIn("num_hands=1", src)  # full_frame baseline keeps her num_hands
        self.assertEqual(CFG["modes"]["full_frame"]["num_hands"], 1)
        for k in ("min_hand_detection_confidence", "min_hand_presence_confidence"):
            self.assertIn(f"{k}={CFG['recognizer'][k]}", src)


class CropGeometryTests(unittest.TestCase):
    def test_box_to_crop(self):
        # box height 200: upper 0.6 -> 120 px, margin 0.1 * 200 = 20 px on every side
        self.assertEqual(ga.crop_box(ga.PersonBox(1, 100, 50, 200, 250), 730, 530, CROP), (80, 30, 220, 190))

    def test_crop_clipped_to_image(self):
        self.assertEqual(ga.crop_box(ga.PersonBox(1, 5, 10, 60, 210), 100, 530, CROP), (0, 0, 80, 150))
        self.assertIsNone(ga.crop_box(ga.PersonBox(1, 760, 10, 800, 200), 730, 530, CROP))

    def test_resize_keeps_aspect(self):
        self.assertEqual(ga.resized_size(140, 160, 256), (224, 256))
        self.assertEqual(ga.resized_size(64, 32, 256), (256, 128))

    def test_crop_to_image_coordinates(self):
        crop = (80, 30, 220, 190)
        self.assertEqual(ga.to_image_xy(0, 0, crop), (80, 30))
        self.assertEqual(ga.to_image_xy(1, 1, crop), (220, 190))
        self.assertEqual(ga.to_image_xy(0.5, 0.25, crop), (150, 70))
        # a pixel (u, v) in the resized crop maps back through the scale factors
        rw, rh = ga.resized_size(140, 160, 256)
        u, v = 112.0, 64.0
        x, y = ga.to_image_xy(u / rw, v / rh, crop)
        self.assertAlmostEqual(x, 80 + u * 140 / rw)
        self.assertAlmostEqual(y, 30 + v * 160 / rh)

    def test_crop_detection_in_full_image_pixels(self):
        person = ga.PersonBox(7, 100, 50, 200, 250)
        crop = ga.crop_box(person, 730, 530, CROP)
        (d,) = ga.crop_detections([hand("Open_Palm", 0.8, (0.5, 0.5), ((0.25, 0.25), (0.75, 1.1)))], crop,
                                  person, 730, 530, 2.0, MAP)
        self.assertEqual((d.track_id, d.gesture, d.raw_category, d.confidence, d.mode),
                         (7, "STOP", "Open_Palm", 0.8, "person_crop"))
        self.assertEqual(d.wrist_xy, (150, 110))
        self.assertEqual(d.hand_box_xyxy, (115, 70, 185, 206))
        self.assertEqual(d.crop_box_xyxy, crop)

    def test_full_frame_hand_box_clipped(self):
        (d,) = ga.full_frame_detections([hand("Victory", 0.7, (0.5, 0.5), ((-0.1, 0.2), (0.6, 0.4)))], 100, 200,
                                        [], 0.0, MAP)
        self.assertEqual(d.hand_box_xyxy, (0.0, 40.0, 60.0, 100.0))
        self.assertEqual(d.wrist_xy, (50, 100))


class TrackAssignmentTests(unittest.TestCase):
    P = [ga.PersonBox(1, 0, 0, 100, 200), ga.PersonBox(2, 300, 0, 400, 200), ga.PersonBox(3, 350, 50, 450, 250)]

    def test_wrist_in_one_box(self):
        self.assertEqual(ga.assign_track((50, 100), self.P), (1, "wrist_in_person_box"))
        self.assertEqual(ga.assign_track((100, 200), self.P), (1, "wrist_in_person_box"))  # edge included
        self.assertEqual(ga.assign_track((420, 220), self.P), (3, "wrist_in_person_box"))

    def test_no_box_or_several(self):
        self.assertEqual(ga.assign_track((200, 100), self.P), (None, "no_containing_box"))
        self.assertEqual(ga.assign_track((375, 100), self.P), (None, "ambiguous"))
        self.assertEqual(ga.assign_track((50, 100), []), (None, "no_containing_box"))

    def test_full_frame_uses_wrist_not_hand_centre(self):
        # wrist inside person 1, rest of the hand outside every box
        h = hand("Thumb_Up", 0.9, (0.09, 0.5), ((0.2, 0.1), (0.25, 0.2)))
        (d,) = ga.full_frame_detections([h], 1000, 400, self.P, 1.0, MAP)
        self.assertEqual((d.track_id, d.assignment, d.gesture), (1, "wrist_in_person_box", "MOVE"))

    def test_full_frame_unassigned_hand(self):
        (d,) = ga.full_frame_detections([hand("Open_Palm", 0.9, (0.2, 0.5))], 1000, 400, self.P, 1.0, MAP)
        self.assertEqual((d.track_id, d.assignment, d.gesture), (None, "no_containing_box", "STOP"))


class NoneHandlingTests(unittest.TestCase):
    def test_no_hand_full_frame(self):
        (d,) = ga.full_frame_detections([], 730, 530, [ga.PersonBox(1, 0, 0, 10, 10)], 3.0, MAP, "f3")
        self.assertEqual((d.gesture, d.raw_category, d.confidence, d.track_id, d.assignment, d.hand_box_xyxy),
                         ("NONE", None, None, None, "no_hand", None))

    def test_no_hand_person_crop(self):
        person = ga.PersonBox(4, 100, 50, 200, 250)
        (d,) = ga.crop_detections([], (80, 30, 220, 190), person, 730, 530, 3.0, MAP)
        self.assertEqual((d.gesture, d.confidence, d.track_id, d.assignment), ("NONE", None, 4, "no_hand"))

    def test_unmapped_categories_keep_raw_score(self):
        ds = ga.full_frame_detections([hand("None", 0.83), hand("Thumb_Down", 0.6)], 100, 100, [], 0.0, MAP)
        self.assertEqual([(d.gesture, d.raw_category, d.confidence) for d in ds],
                         [("NONE", "None", 0.83), ("NONE", "Thumb_Down", 0.6)])

    def test_events_one_per_track_stop_first(self):
        p = ga.PersonBox(1, 0, 0, 100, 100)
        crop = (0, 0, 100, 100)
        ds = (ga.crop_detections([hand("Victory", 0.95), hand("Closed_Fist", 0.4)], crop, p, 100, 100, 1.0, MAP)
              + ga.full_frame_detections([], 100, 100, [], 1.0, MAP)
              + ga.crop_detections([hand("Pointing_Up", 0.5), hand("Thumb_Up", 0.7)], crop,
                                   ga.PersonBox(2, 0, 0, 100, 100), 100, 100, 1.0, MAP))
        ev = {e.track_id: e for e in ga.to_gesture_events(ds)}
        self.assertEqual(ev[1], GestureEvent(1.0, 1, "STOP", 0.4))  # raw score passed on, not filtered
        self.assertEqual(ev[None], GestureEvent(1.0, None, "NONE", 0.0))
        self.assertEqual(ev[2], GestureEvent(1.0, 2, "MOVE", 0.7))


class NoThresholdTests(unittest.TestCase):
    def test_no_adapter_file_defines_a_confidence_threshold(self):
        num = r"-?\d+(\.\d+)?"
        patterns = [rf"(confidence|score|conf)\w*\s*(>=|<=|>|<|==)\s*{num}",
                    rf"{num}\s*(>=|<=|>|<)\s*\w*(confidence|score|conf)",
                    rf"\w*(threshold|min_conf)\w*\s*=\s*{num}", r"score_threshold"]
        for f in ADAPTER_FILES:
            src = (ROOT / f).read_text(encoding="utf-8")
            for pat in patterns:
                self.assertIsNone(re.search(pat, src), f"{f} matches {pat}")
        # the adapter and smoke script never even read the decision threshold
        for f in ("gesture_adapter.py", "gesture_smoke.py"):
            self.assertFalse("gesture_min_confidence" in (ROOT / f).read_text(encoding="utf-8"), f)

    def test_gesture_config_has_no_gesture_threshold(self):
        allowed = {"min_hand_detection_confidence", "min_hand_presence_confidence"}  # MediaPipe hand detector

        def keys(o):
            if isinstance(o, dict):
                for k, v in o.items():
                    yield k
                    yield from keys(v)
            elif isinstance(o, list):
                for v in o:
                    yield from keys(v)
        bad = [k for k in keys(CFG) if re.search(r"confidence|min_conf|threshold|score", k, re.I) and k not in allowed]
        self.assertEqual(bad, [])
        self.assertEqual(set(CFG["recognizer"]) & allowed, allowed)
        dec = json.loads((ROOT / "configs" / "decision.json").read_text(encoding="utf-8"))
        self.assertIn("gesture_min_confidence", dec)

    def test_isolation(self):
        banned = {"gesture_eval", "thud_data", "fuse_objects", "estimate_motion", "validate_depth",
                  "report_motion", "report_step4"}
        for f in ("gesture_adapter.py", "gesture_smoke.py"):
            self.assertFalse(imports(f) & banned, f)
        # the adapter reuses decision.GestureEvent and defines no gesture event class of its own
        tree = ast.parse((ROOT / "gesture_adapter.py").read_text(encoding="utf-8"))
        classes = {n.name for n in ast.walk(tree) if isinstance(n, ast.ClassDef)}
        self.assertNotIn("GestureEvent", classes)
        self.assertIs(ga.GestureEvent, GestureEvent)


class EvaluationHookTests(unittest.TestCase):
    def test_status_not_evaluated_until_unity(self):
        ev = CFG["evaluation"]
        self.assertEqual(ev["status"], "not_evaluated")
        self.assertIsNone(ev["unity_labels"])
        self.assertEqual(ev["distance_bins_m"], [1, 2, 3, 4, 5])

    def test_accuracy_by_bin_mode_with_coverage(self):
        crop = (0, 0, 10, 10)
        labels = [{"frame_id": "a", "track_id": "1", "gesture_true": "STOP", "distance_m": 1.2},
                  {"frame_id": "a", "track_id": "2", "gesture_true": "MOVE", "distance_m": 3.0},
                  {"frame_id": "b", "track_id": "1", "gesture_true": "NONE", "distance_m": 4.9},
                  {"frame_id": "b", "track_id": "2", "gesture_true": "STOP", "distance_m": 7.0}]
        p1, p2 = ga.PersonBox(1, 0, 0, 10, 10), ga.PersonBox(2, 0, 0, 10, 10)
        dets = (ga.crop_detections([hand("Open_Palm", 0.9)], crop, p1, 10, 10, 0, MAP, "a")
                + ga.crop_detections([hand("Victory", 0.5)], crop, p2, 10, 10, 0, MAP, "a")
                + ga.crop_detections([], crop, p1, 10, 10, 1, MAP, "b")
                + ga.full_frame_detections([hand("Open_Palm", 0.9, (0.5, 0.5))], 10, 10, [p1], 0, MAP, "a"))
        r = ge.evaluate(labels, dets, CFG["evaluation"], 0.6)
        pc = r["person_crop"]
        self.assertEqual((pc["overall"]["n_labels"], pc["overall"]["covered"]), (4, 2))
        self.assertEqual(pc["overall"]["coverage"], 0.5)
        self.assertEqual(pc["overall"]["accuracy_raw"], 0.75)  # STOP, MOVE, NONE (no hand) right; STOP missed
        self.assertEqual(pc["overall"]["accuracy_at_min_confidence"], 0.5)  # MOVE 0.5 < 0.6 -> NONE
        self.assertEqual(pc["by_distance_bin"]["1m"]["accuracy_raw"], 1.0)
        self.assertEqual(pc["by_distance_bin"]["5m"]["coverage"], 0.0)
        self.assertEqual(pc["by_distance_bin"]["outside_bins"]["n_labels"], 1)
        self.assertIsNone(pc["by_distance_bin"]["2m"]["accuracy_raw"])
        self.assertEqual(pc["overall"]["confusion_at_min_confidence"]["MOVE"]["NONE"], 1)
        self.assertEqual(r["full_frame"]["overall"]["covered"], 1)


class ModelTests(unittest.TestCase):
    @unittest.skipUnless(ga.model_path(CFG).exists(), "submodule external/media_pipe_gesture not checked out")
    def test_model_hash(self):
        self.assertEqual(ga.sha256_file(ga.model_path(CFG)), CFG["model"]["sha256"])

    @unittest.skipUnless(ga.model_path(CFG).exists(), "submodule external/media_pipe_gesture not checked out")
    def test_blank_frame_gives_none_in_both_modes(self):
        try:
            import mediapipe  # noqa: F401
            import numpy as np
        except ImportError:
            self.skipTest("mediapipe not installed")
        rgb = np.zeros((530, 730, 3), np.uint8)
        persons = [ga.PersonBox(5, 300, 100, 400, 400)]
        with ga.GestureRecognizerAdapter(CFG, "full_frame") as ad:
            (d,) = ad.detect(rgb, 0.0, persons)
            self.assertEqual((d.gesture, d.assignment), ("NONE", "no_hand"))
        with ga.GestureRecognizerAdapter(CFG, "person_crop") as ad:
            (d,) = ad.detect(rgb, 0.0, persons)
            self.assertEqual((d.gesture, d.track_id, d.assignment), ("NONE", 5, "no_hand"))


if __name__ == "__main__":
    unittest.main()
