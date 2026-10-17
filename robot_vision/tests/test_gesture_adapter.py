"""Tests for the gesture adapter and its evaluation hook. No dataset, model or MediaPipe needed (two tests that
use the model skip when the submodule or MediaPipe is missing). Run from robot_vision/:
    python -m unittest discover -s tests -v"""

import ast
import json
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import gesture_adapter as ga  # noqa: E402
import gesture_eval as ge  # noqa: E402
from decision import GestureEvent  # noqa: E402

CFG = ga.load_gesture_config()
MAP = CFG["mapping"]
CROP = CFG["modes"]["person_crop"]
ACFG = CFG["assignment"]
HER_FILE = ROOT.parent / "external" / "media_pipe_gesture" / "gesture_heuristics.py"
ADAPTER_FILES = ["gesture_adapter.py", "gesture_smoke.py", "gesture_eval.py"]


def hand(category, score=0.9, wrist=(0.5, 0.5), others=((0.4, 0.3), (0.6, 0.7))):
    return ga.RawHand(category, score, "Right", (wrist,) + tuple(others))


def hand_in(region, pts, category="Open_Palm", score=0.9):
    """RawHand whose landmarks are the full-image points pts (wrist first), seen in region (crop or full frame)."""
    x0, y0, x1, y1 = region
    return ga.RawHand(category, score, "Right", tuple(((x - x0) / (x1 - x0), (y - y0) / (y1 - y0)) for x, y in pts))


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
        (d,) = ga.person_crop_detections(
            {7: (crop, [hand("Open_Palm", 0.8, (0.5, 0.5), ((0.25, 0.25), (0.75, 1.1)))])}, 730, 530, [person],
            2.0, CFG)
        self.assertEqual((d.track_id, d.gesture, d.raw_category, d.confidence, d.mode, d.assignment),
                         (7, "STOP", "Open_Palm", 0.8, "person_crop", "wrist_in_single_box"))
        self.assertEqual(d.wrist_xy, (150, 110))
        self.assertEqual(d.hand_box_xyxy, (115, 70, 185, 206))
        self.assertEqual(d.crop_box_xyxy, crop)

    def test_full_frame_hand_box_clipped(self):
        (d,) = ga.full_frame_detections([hand("Victory", 0.7, (0.5, 0.5), ((-0.1, 0.2), (0.6, 0.4)))], 100, 200,
                                        [], 0.0, CFG)
        self.assertEqual(d.hand_box_xyxy, (0.0, 40.0, 60.0, 100.0))
        self.assertEqual(d.wrist_xy, (50, 100))


class WristRuleTests(unittest.TestCase):
    """Fallback ownership without depth: the wrist inside exactly one person box."""
    P = [ga.PersonBox(1, 0, 0, 100, 200), ga.PersonBox(2, 300, 0, 400, 200), ga.PersonBox(3, 350, 50, 450, 250)]

    def test_wrist_in_one_box(self):
        self.assertEqual(ga.assign_track((50, 100), self.P), (1, "wrist_in_single_box"))
        self.assertEqual(ga.assign_track((100, 200), self.P), (1, "wrist_in_single_box"))  # edge included
        self.assertEqual(ga.assign_track((420, 220), self.P), (3, "wrist_in_single_box"))

    def test_no_box_or_several(self):
        self.assertEqual(ga.assign_track((200, 100), self.P), (None, "no_containing_box"))
        self.assertEqual(ga.assign_track((375, 100), self.P), (None, "ambiguous"))
        self.assertEqual(ga.assign_track((50, 100), []), (None, "no_containing_box"))

    def test_full_frame_uses_wrist_not_hand_centre(self):
        # wrist inside person 1, rest of the hand outside every box
        h = hand("Thumb_Up", 0.9, (0.09, 0.5), ((0.2, 0.1), (0.25, 0.2)))
        (d,) = ga.full_frame_detections([h], 1000, 400, self.P, 1.0, CFG)
        self.assertEqual((d.track_id, d.assignment, d.gesture), (1, "wrist_in_single_box", "MOVE"))

    def test_full_frame_unassigned_hand(self):
        (d,) = ga.full_frame_detections([hand("Open_Palm", 0.9, (0.2, 0.5))], 1000, 400, self.P, 1.0, CFG)
        self.assertEqual((d.track_id, d.assignment, d.gesture), (None, "no_containing_box", "STOP"))


class DuplicateAndOwnerTests(unittest.TestCase):
    """Two overlapping people: A (nearer, 3.0 m) and B (4.0 m). One hand at wrist (180, 150) lies in both crops
    and both boxes; another wrist at (120, 150) lies in both crops but only in A's box."""
    A = ga.PersonBox("A", 100, 50, 200, 350, depth_m=3.0)
    B = ga.PersonBox("B", 150, 40, 260, 360, depth_m=4.0)
    C = ga.PersonBox("C", 500, 50, 600, 350, depth_m=2.7)  # far to the side: never a candidate
    W, H = 730, 530
    PTS = [(180, 150), (170, 120), (200, 160)]

    def crops(self, persons):
        return {p.track_id: ga.crop_box(p, self.W, self.H, CROP) for p in persons}

    def run_crop(self, pts, depth, persons=None, score_b=0.7):
        persons = persons or [self.A, self.B, self.C]
        cr = self.crops(persons)
        by = {"A": (cr["A"], [hand_in(cr["A"], pts, "Open_Palm", 0.9)]),
              "B": (cr["B"], [hand_in(cr["B"], pts, "Victory", score_b)])}
        if "C" in cr:
            by["C"] = (cr["C"], [])
        return ga.person_crop_detections(by, self.W, self.H, persons, 0.0, CFG, depth)

    @staticmethod
    def depth_image(value):
        d = np.full((530, 730), np.nan, np.float32)
        d[140:161, 170:191] = value
        return d

    def test_iou(self):
        self.assertEqual(ga.box_iou((0, 0, 10, 10), (0, 0, 10, 10)), 1.0)
        self.assertAlmostEqual(ga.box_iou((0, 0, 10, 10), (5, 0, 15, 10)), 50 / 150)
        self.assertEqual(ga.box_iou((0, 0, 10, 10), (20, 20, 30, 30)), 0.0)

    def test_deduplicate_keeps_highest_score(self):
        h1 = ga.ImageHand("Open_Palm", 0.6, None, (0, 0, 10, 10), (5, 5), "A")
        h2 = ga.ImageHand("Victory", 0.8, None, (1, 0, 11, 10), (6, 5), "B")
        h3 = ga.ImageHand("Victory", 0.9, None, (50, 50, 60, 60), (55, 55), "B")
        groups = ga.deduplicate([h1, h2, h3], ACFG["duplicate_hand_iou_threshold"])
        self.assertEqual([(k.score, [c.score for c in cs]) for k, cs in groups], [(0.9, []), (0.8, [0.6])])

    def test_same_hand_in_two_crops_is_one_hand_owned_by_depth(self):
        ds = self.run_crop(self.PTS, self.depth_image(2.7))  # gaps: A 0.3, B 1.3
        hands = [d for d in ds if d.raw_category is not None]
        self.assertEqual(len(hands), 1)
        (h,) = hands
        self.assertEqual((h.track_id, h.assignment, h.raw_category, h.confidence), ("A", "depth", "Open_Palm", 0.9))
        self.assertAlmostEqual(h.wrist_depth_m, 2.7, places=5)
        self.assertEqual(sorted(h.candidates), ["A", "B"])  # C has the closest depth but is not a candidate
        self.assertEqual(h.duplicates, (("B", "Victory", 0.7),))
        none = {d.track_id: d.assignment for d in ds if d.raw_category is None}
        self.assertEqual(none, {"B": "no_owned_hand", "C": "no_hand"})

    def test_depth_picks_the_farther_person(self):
        (h,) = [d for d in self.run_crop(self.PTS, self.depth_image(3.8)) if d.raw_category]
        self.assertEqual((h.track_id, h.assignment), ("B", "depth"))

    def test_depth_tie_falls_back_to_wrist_rule(self):
        ds = self.run_crop(self.PTS, self.depth_image(3.5))  # gaps 0.5 and 0.5 < depth_margin_m apart
        (h,) = [d for d in ds if d.raw_category]
        self.assertEqual((h.track_id, h.assignment), (None, "ambiguous"))  # wrist in both boxes
        self.assertEqual({d.track_id for d in ds if d.raw_category is None}, {"A", "B", "C"})

    def test_depth_too_far_falls_back_to_wrist_rule(self):
        pts = [(120, 150), (110, 120), (140, 160)]
        d = np.full((530, 730), 5.5, np.float32)  # gaps 2.5 and 1.5 > depth_match_max_m
        (h,) = [x for x in self.run_crop(pts, d) if x.raw_category]
        self.assertEqual((h.track_id, h.assignment), ("A", "wrist_in_single_box"))

    def test_no_depth_uses_wrist_rule(self):
        (h,) = [x for x in self.run_crop(self.PTS, None) if x.raw_category]
        self.assertEqual((h.track_id, h.assignment, h.wrist_depth_m), (None, "ambiguous", None))
        pts = [(120, 150), (110, 120), (140, 160)]
        (h,) = [x for x in self.run_crop(pts, None) if x.raw_category]
        self.assertEqual((h.track_id, h.assignment), ("A", "wrist_in_single_box"))

    def test_person_without_depth_is_skipped_by_depth_rule(self):
        a = ga.PersonBox("A", 100, 50, 200, 350)  # no depth_m
        (h,) = [x for x in self.run_crop(self.PTS, self.depth_image(2.7), [a, self.B]) if x.raw_category]
        self.assertEqual((h.track_id, h.assignment), (None, "ambiguous"))  # B alone is 1.3 m off

    def test_full_frame_uses_the_same_owner_rule(self):
        (h,) = ga.full_frame_detections([hand_in((0, 0, self.W, self.H), self.PTS)], self.W, self.H,
                                        [self.A, self.B, self.C], 0.0, CFG, self.depth_image(3.8))
        self.assertEqual((h.track_id, h.assignment), ("B", "depth"))

    def test_two_different_hands_are_kept(self):
        cr = self.crops([self.A, self.B])
        far = [(240, 100), (230, 80), (255, 115)]  # B's other hand, only in B's crop and box
        by = {"A": (cr["A"], [hand_in(cr["A"], self.PTS)]),
              "B": (cr["B"], [hand_in(cr["B"], self.PTS, "Victory", 0.7), hand_in(cr["B"], far, "Thumb_Up", 0.8)])}
        ds = ga.person_crop_detections(by, self.W, self.H, [self.A, self.B], 0.0, CFG, self.depth_image(2.7))
        self.assertEqual(sorted((d.track_id, d.raw_category) for d in ds if d.raw_category),
                         [("A", "Open_Palm"), ("B", "Thumb_Up")])

    def test_depth_at_window(self):
        d = np.zeros((10, 10), np.float32)
        d[4:7, 4:7] = [[1, 2, 3], [np.nan, 5, 6], [7, 8, np.inf]]
        self.assertEqual(ga.depth_at(d, (5, 5), 1), 5.0)  # median of the valid 1, 2, 3, 5, 6, 7, 8
        self.assertIsNone(ga.depth_at(np.zeros((10, 10)), (5, 5), 1))
        self.assertIsNone(ga.depth_at(d, (20, 5), 1))
        self.assertIsNone(ga.depth_at(None, (5, 5), 1))


class NoneHandlingTests(unittest.TestCase):
    def test_no_hand_full_frame(self):
        (d,) = ga.full_frame_detections([], 730, 530, [ga.PersonBox(1, 0, 0, 10, 10)], 3.0, CFG, None, "f3")
        self.assertEqual((d.gesture, d.raw_category, d.confidence, d.track_id, d.assignment, d.hand_box_xyxy),
                         ("NONE", None, None, None, "no_hand", None))

    def test_no_hand_person_crop(self):
        person = ga.PersonBox(4, 100, 50, 200, 250)
        (d,) = ga.person_crop_detections({4: ((80, 30, 220, 190), [])}, 730, 530, [person], 3.0, CFG)
        self.assertEqual((d.gesture, d.confidence, d.track_id, d.assignment), ("NONE", None, 4, "no_hand"))

    def test_unmapped_categories_keep_raw_score(self):
        ds = ga.full_frame_detections([hand("None", 0.83, (0.2, 0.2), ((0.1, 0.1), (0.3, 0.3))),
                                       hand("Thumb_Down", 0.6, (0.8, 0.8), ((0.7, 0.7), (0.9, 0.9)))],
                                      100, 100, [], 0.0, CFG)
        self.assertEqual([(d.gesture, d.raw_category, d.confidence) for d in ds],
                         [("NONE", "None", 0.83), ("NONE", "Thumb_Down", 0.6)])

    def test_events_one_per_track_stop_first(self):
        def det(tid, g, conf):
            return ga.GestureDetection(1.0, None, "person_crop", tid, g, "x" if conf else None, conf, None, None,
                                       None, "depth")
        ds = [det(1, "MOVE", 0.95), det(1, "STOP", 0.4), det(None, "NONE", None), det(2, "MOVE", 0.5),
              det(2, "MOVE", 0.7)]
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
        allowed = {"min_hand_detection_confidence", "min_hand_presence_confidence",  # MediaPipe hand detector
                   "duplicate_hand_iou_threshold"}  # box overlap (geometry), not a confidence

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
        self.assertEqual(set(CFG["recognizer"]) & allowed, allowed - {"duplicate_hand_iou_threshold"})
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


class LazyMediaPipeTests(unittest.TestCase):
    def test_only_the_adapter_imports_mediapipe_and_not_at_module_level(self):
        for f in sorted(ROOT.glob("*.py")) + sorted((ROOT / "tests").glob("*.py")):
            mods = {m.split(".")[0] for m in imports(str(f.relative_to(ROOT)))}
            if f.name in ("gesture_adapter.py", "test_gesture_adapter.py"):
                continue
            self.assertNotIn("mediapipe", mods, f.name)
        tree = ast.parse((ROOT / "gesture_adapter.py").read_text(encoding="utf-8"))
        top = {a.name.split(".")[0] for n in tree.body if isinstance(n, ast.Import) for a in n.names}
        top |= {n.module.split(".")[0] for n in tree.body if isinstance(n, ast.ImportFrom) and n.module}
        self.assertNotIn("mediapipe", top)

    def test_pipeline_imports_and_runs_without_mediapipe(self):
        # verify_tracking_run.py is a script that reads sys.argv on import; the AST test covers its imports
        mods = sorted(f.stem for f in ROOT.glob("*.py") if f.name != "verify_tracking_run.py")
        code = ("import sys; sys.modules['mediapipe'] = None\n"
                f"for m in {mods!r}: __import__(m)\n"
                "import gesture_adapter as ga\n"
                "cfg = ga.load_gesture_config()\n"
                "assert ga.full_frame_detections([], 10, 10, [], 0.0, cfg)[0].gesture == 'NONE'\n"
                "try:\n    ga.GestureRecognizerAdapter(cfg, 'full_frame')\n"
                "except ImportError as e:\n    assert 'mediapipe' in str(e)\n"
                "else:\n    raise SystemExit('adapter created without mediapipe')\n"
                "print('ok')\n")
        r = subprocess.run([sys.executable, "-c", code], cwd=ROOT, capture_output=True, text=True, timeout=600)
        self.assertEqual(r.returncode, 0, r.stderr[-2000:])
        self.assertIn("ok", r.stdout)


class EvaluationHookTests(unittest.TestCase):
    def test_status_not_evaluated_until_unity(self):
        ev = CFG["evaluation"]
        self.assertEqual(ev["status"], "not_evaluated")
        self.assertIsNone(ev["unity_labels"])
        self.assertEqual(ev["distance_bins_m"], [1, 2, 3, 4, 5])

    def test_accuracy_by_bin_mode_with_coverage(self):
        def det(mode, frame, tid, g, cat, conf):
            return ga.GestureDetection(0.0, frame, mode, tid, g, cat, conf, None, None, None, "depth")
        labels = [{"frame_id": "a", "track_id": "1", "gesture_true": "STOP", "distance_m": 1.2},
                  {"frame_id": "a", "track_id": "2", "gesture_true": "MOVE", "distance_m": 3.0},
                  {"frame_id": "b", "track_id": "1", "gesture_true": "NONE", "distance_m": 4.9},
                  {"frame_id": "b", "track_id": "2", "gesture_true": "STOP", "distance_m": 7.0}]
        dets = [det("person_crop", "a", 1, "STOP", "Open_Palm", 0.9),
                det("person_crop", "a", 2, "MOVE", "Victory", 0.5),
                det("person_crop", "b", 1, "NONE", None, None),
                det("full_frame", "a", 1, "STOP", "Open_Palm", 0.9),
                det("full_frame", "a", None, "MOVE", "Victory", 0.9)]
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
        self.assertEqual(r["full_frame"]["overall"]["covered"], 1)  # the unowned hand covers nobody

    def test_detections_round_trip(self):
        d = ga.full_frame_detections([hand_in((0, 0, 730, 530), [(180, 150), (170, 120), (200, 160)])], 730, 530,
                                     [DuplicateAndOwnerTests.A], 0.0, CFG, DuplicateAndOwnerTests.depth_image(3.0),
                                     "f")[0]
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "d.jsonl"
            p.write_text(json.dumps(d.as_dict()) + "\n", encoding="utf-8")
            (back,) = ge.read_detections(p)
        self.assertEqual((back.track_id, back.assignment, back.candidates), ("A", "depth", ("A",)))


class ModelTests(unittest.TestCase):
    @unittest.skipUnless(ga.model_path(CFG).exists(), "submodule external/media_pipe_gesture not checked out")
    def test_model_hash(self):
        self.assertEqual(ga.sha256_file(ga.model_path(CFG)), CFG["model"]["sha256"])

    @unittest.skipUnless(ga.model_path(CFG).exists(), "submodule external/media_pipe_gesture not checked out")
    def test_blank_frame_gives_none_in_both_modes(self):
        try:
            import mediapipe  # noqa: F401
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
