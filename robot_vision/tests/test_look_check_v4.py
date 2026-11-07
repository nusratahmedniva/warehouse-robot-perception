"""look_check_v4.py on synthetic recordings: file names, folders, headers, the per-group checks, the declared verdict rules,
the report files and the annotated images. No real model is loaded: a scripted detector returns the keypoints and hands of
tests/v4_synth.py for every PNG (the PNG carries the id of its detection in its first pixel)."""

import ast
import json
import math
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))

import gesture_motion as gm  # noqa: E402
import look_check_v4 as lc  # noqa: E402
import v4_synth as vs  # noqa: E402

CFG = lc.load_config()
CFG_PATH = ROOT / lc.DEFAULT_CONFIG
VFOV = math.degrees(2.0 * math.atan(vs.HEIGHT / 2.0 / vs.FY))
N_SEQ_FRAMES = 11                                         # 1 s at 10 Hz, both ends included


def lf(b: bytes) -> bytes:
    return b.replace(b"\r\n", b"\n")


def person(kp, conf, hands=None):
    box = (float(kp[:, 0].min()) - 20, float(kp[:, 1].min()) - 20, float(kp[:, 0].max()) + 20, float(kp[:, 1].max()) + 20)
    return lc.Detection([{"box": box, "kp": kp, "conf": conf}], 0, list((hands or {}).values()))


def pose(command, side="left", z=2.0, hand=True, arm_scale=1.0, shown=None):
    """The synthetic Detection of one avatar pose. shown: the hand the models see instead of the one the command needs."""
    s = 1.0 if side == "left" else -1.0
    shown = shown or command
    if command == "NONE":
        kp, conf = vs.body(z0=z)
        return person(kp, conf)
    if command == "WAIT":
        kw = {side: vs.direction(90.0 * s), side + "_fore": (0.0, -1.0, 0.0)}
    elif command == "STOP":
        kw = {side: vs.direction(90.0 * s, 10.0)}
    else:
        kw = {side: vs.direction(90.0 * s)}
    kp, conf = vs.body(z0=z, **kw)
    if arm_scale != 1.0:
        sh, el, wr = gm.ARMS[side]
        kp = kp.copy()
        kp[el] = kp[sh] + arm_scale * (kp[el] - kp[sh])
        kp[wr] = kp[sh] + arm_scale * (kp[wr] - kp[sh])
    hands = {}
    if hand:
        w = kp[gm.ARMS[side][2]]
        if shown == "WAIT":
            hands[side] = vs.hand(w, axis=(0.0, -1.0), z=z, extended=("index",), category="Pointing_Up", fan_deg=4.0)
        elif shown == "STOP":
            hands[side] = vs.hand(w, axis=(s, 0.0), z=z, category="Open_Palm", fan_deg=18.0)
        else:
            hands[side] = vs.hand(w, axis=(s, 0.0), z=z, extended=(), category="Closed_Fist", fan_deg=4.0)
    return person(kp, conf, hands)


class Studio:
    """Writes recordings into a folder and is the detector that finds what each PNG was written with."""

    def __init__(self, root: Path):
        self.root, self.script = root, {}

    def png(self, path: Path, det) -> None:
        import cv2
        img = np.zeros((vs.HEIGHT, vs.WIDTH, 3), np.uint8)
        i = len(self.script)
        img[0, 0] = (i % 256, i // 256, 0)
        self.script[i] = det
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(cv2.imencode(".png", img)[1].tobytes())

    def header(self, png: Path, arm=None, time_s=None, crlf=False, **over) -> None:
        h = {"width": vs.WIDTH, "height": vs.HEIGHT, "fx": vs.FX, "fy": vs.FY, "cx": vs.CX, "cy": vs.CY,
             "vertical_fov_deg": VFOV, "pan_deg": 0.0}
        if arm:
            h["arm"] = arm
        if time_s is not None:
            h["time_s"] = time_s
        h.update(over)
        text = json.dumps(h, indent=2)
        png.with_suffix(".json").write_bytes((text.replace("\n", "\r\n") if crlf else text).encode("utf-8"))

    def frame(self, name, det, arm=None, **kw) -> None:
        p = self.root / f"{name}.png"
        self.png(p, det)
        self.header(p, arm, **kw)

    def sequence(self, name, dets, arm=None, **kw) -> None:
        for i, det in enumerate(dets):
            p = self.root / name / f"frame_{i:03d}.png"
            self.png(p, det)
            self.header(p, arm, **kw)

    def detect(self, bgr):
        return self.script[int(bgr[0, 0, 0]) + 256 * int(bgr[0, 0, 1])]


def record_look(st: Studio, look, commands=("POINT", "WAIT", "STOP"), arms=("left", "right"), dists=(2.0,), n_seq=2,
                label=True, per_command=None, **pose_kw):
    """The complete recording set of one look: every command x arm x distance, n_seq sequences each."""
    per_command = per_command or {}
    for d in dists:
        for c in commands:
            for arm in arms:
                kw = {**pose_kw, **per_command.get(c, {})}
                for n in range(n_seq):
                    det = pose(c, arm, z=d, **kw)
                    st.sequence(f"{look}__{c}__{d:g}__{arm[0]}{n}", [det] * N_SEQ_FRAMES, arm if label else None)


def run(st: Studio, tmp: Path, cfg=None, annotate=True):
    out = tmp / "out"
    out.mkdir()
    return lc.run_check(st.root, st, cfg or CFG, CFG_PATH, out, annotate_png=annotate), out


class NameTests(unittest.TestCase):
    def test_valid_names(self):
        self.assertEqual(lc.parse_name("Mia_01__POINT__2.0__3", CFG), ("Mia_01", "POINT", 2.0, "3"))
        self.assertEqual(lc.parse_name("A__WAIT__4__12", CFG), ("A", "WAIT", 4.0, "12"))
        self.assertEqual(lc.parse_name("A__NONE__2__1", CFG)[1], "NONE")

    def test_invalid_names_say_why(self):
        for bad in ("A__POINT__2.0", "A__point__2.0__1", "A__POINT__far__1", "A__POINT__0__1", "A__POINT__-2__1",
                    "A__POINT__2.0__1__x", "__POINT__2.0__1", "A__POINT__nan__1", "A__GO__2.0__1"):
            with self.assertRaises(ValueError, msg=bad):
                lc.parse_name(bad, CFG)


class DiscoverTests(unittest.TestCase):
    def test_singles_sequences_problems_and_natural_order(self):
        with tempfile.TemporaryDirectory() as t:
            root = Path(t)
            st = Studio(root)
            st.frame("A__POINT__2.0__1", pose("POINT"))
            st.sequence("A__WAIT__2.0__1", [pose("WAIT")] * 12)
            st.frame("badname", pose("POINT"))
            (root / ".hidden.png").write_bytes(b"x")
            (root / "notes.txt").write_text("x")
            (root / "emptydir").mkdir()
            items, problems = lc.discover(root, CFG)
            self.assertEqual([(i.name, i.kind) for i in items], [("A__POINT__2.0__1", "frame"), ("A__WAIT__2.0__1", "sequence")])
            names = [p[0].name for p in items[1].files]
            self.assertEqual(names, [f"frame_{i:03d}.png" for i in range(12)])
            self.assertEqual(len(problems), 2)
            self.assertTrue(any("badname" in p for p in problems) and any("emptydir" in p for p in problems))

    def test_frame_numbers_without_padding_sort_numerically(self):
        with tempfile.TemporaryDirectory() as t:
            root = Path(t)
            for i in (1, 2, 10, 11):
                (root / "S__POINT__2__1").mkdir(exist_ok=True)
                (root / "S__POINT__2__1" / f"frame_{i}.png").write_bytes(b"x")
            items, _ = lc.discover(root, CFG)
            self.assertEqual([p[0].name for p in items[0].files], ["frame_1.png", "frame_2.png", "frame_10.png", "frame_11.png"])


class HeaderTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.st = Studio(self.root)

    def tearDown(self):
        self.tmp.cleanup()

    def read(self, **over):
        p = self.root / "f.png"
        self.st.header(p, **over)
        return lc.read_header(p.with_suffix(".json"), vs.WIDTH, vs.HEIGHT, CFG, 1e-3)

    def test_valid_header_with_crlf_and_optional_keys(self):
        h, err = self.read(arm="left", time_s=1.5, pan_deg=12.0, crlf=True)
        self.assertIsNone(err)
        self.assertEqual((h.arm, h.time_s, h.pan_deg), ("left", 1.5, 12.0))

    def test_header_without_width_and_height_takes_them_from_the_image(self):
        p = self.root / "f.json"
        p.write_text(json.dumps({"fx": vs.FX, "fy": vs.FY, "cx": vs.CX, "cy": vs.CY, "vertical_fov_deg": VFOV}), encoding="utf-8")
        h, err = lc.read_header(p, vs.WIDTH, vs.HEIGHT, CFG, 1e-3)
        self.assertIsNone(err)
        self.assertEqual((h.width, h.height), (vs.WIDTH, vs.HEIGHT))

    def test_bad_headers_are_refused_with_a_reason(self):
        for over, word in (({"fx": 500.0}, "fx"), ({"vertical_fov_deg": 45.0}, "fy"), ({"cx": 300.0}, "cx"), ({"width": 640}, "width"),
                           ({"arm": "both"}, "arm"), ({"vertical_fov_deg": 200.0}, "outside"), ({"fx": None}, "fx"),
                           ({"time_s": "soon"}, "time_s"), ({"pan_deg": "left"}, "pan_deg")):
            h, err = self.read(**over)
            self.assertIsNone(h, msg=str(over))
            self.assertIn(word, err, msg=str(over))

    def test_nan_intrinsics_are_refused(self):
        p = self.root / "f.json"
        p.write_text('{"fx": NaN, "fy": 458.99, "cx": 365, "cy": 265, "vertical_fov_deg": 60.0}', encoding="utf-8")
        h, err = lc.read_header(p, vs.WIDTH, vs.HEIGHT, CFG, 1e-3)
        self.assertIsNone(h)

    def test_missing_and_broken_files(self):
        self.assertIn("missing", lc.read_header(self.root / "none.json", 730, 530, CFG, 1e-3)[1])
        (self.root / "b.json").write_text("{not json", encoding="utf-8")
        self.assertIn("unreadable", lc.read_header(self.root / "b.json", 730, 530, CFG, 1e-3)[1])
        (self.root / "l.json").write_text("[1, 2]", encoding="utf-8")
        self.assertIn("not a JSON object", lc.read_header(self.root / "l.json", 730, 530, CFG, 1e-3)[1])


class ConfigTests(unittest.TestCase):
    def test_declared_before_real_frames_and_complete(self):
        self.assertEqual(CFG["status"], "declared")
        self.assertIn("before any real frame", CFG["declared"])
        for name in ("person_rate", "arm_valid_rate", "hand_linked_rate", "own_cue_rate", "wrong_class_rate",
                     "sequence_read_rate", "wrong_read_rate", "arm_ratio_p95"):
            self.assertIn("why", CFG["checks"][name], msg=name)
        self.assertEqual(set(CFG["checks"]["hand_linked_rate"]["hand_required"]), {"POINT", "WAIT", "STOP"})
        self.assertEqual(set(CFG["checks"]["arm_valid_rate"]["required"]), {"POINT", "WAIT", "STOP"})
        self.assertEqual(CFG["distances"]["decisive_m"], [2.0])
        self.assertEqual(CFG["distances"]["secondary_m"], [4.0])

    def test_bounds_are_ordered(self):
        for name, c in CFG["checks"].items():
            if "usable_min" in c:
                self.assertGreater(c["usable_min"], c["weak_min"], msg=name)
            if "usable_max" in c:
                self.assertLess(c["usable_max"], c["weak_max"], msg=name)

    def test_own_cue_bound_is_the_readers_class_share_and_the_ratio_is_the_readers_arm_length(self):
        rc = gm.load_config()
        self.assertEqual(CFG["checks"]["own_cue_rate"]["usable_min"], rc["decision"]["class_share_min"])
        self.assertEqual(CFG["checks"]["arm_ratio_p95"]["assumed"], rc["point"]["arm_length_in_shoulder_widths"])
        self.assertEqual(CFG["input"]["fallback_frame_hz"], rc["frame_hz"])
        bridge = json.loads((ROOT / "configs/v4/bridge.json").read_text(encoding="utf-8"))
        self.assertEqual(CFG["input"]["fallback_frame_hz"], bridge["frame_pan_tilt_hz"])

    def test_no_ground_truth_or_split_code_is_imported(self):
        tree = ast.parse((ROOT / "look_check_v4.py").read_text(encoding="utf-8"))
        mods = set()
        for n in ast.walk(tree):
            if isinstance(n, ast.Import):
                mods |= {a.name.split(".")[0] for a in n.names}
            elif isinstance(n, ast.ImportFrom) and n.module:
                mods.add(n.module.split(".")[0])
        for forbidden in ("gt_path", "gesture_data", "data_splits", "data_splits_v4", "hri_sim_v4", "hri_eval_dev_v4",
                          "hri_eval_final_v4", "final_guard_v4", "freeze_v4", "hri_trials"):
            self.assertNotIn(forbidden, mods)


class GoodLookTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.root = Path(cls.tmp.name)
        cls.st = Studio(cls.root / "in")
        record_look(cls.st, "Mia", dists=(2.0, 4.0))
        cls.report, cls.out = run(cls.st, cls.root)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_verdict_usable_with_every_decisive_check_passed(self):
        v = self.report["verdicts"]["Mia"]
        self.assertEqual(v["verdict"], "usable", msg=v["reasons"])
        self.assertTrue(v["arms_labelled"])

    def test_groups_cover_command_distance_and_arm(self):
        keys = {(g["command"], g["distance_m"], g["arm"]) for g in self.report["groups"]}
        self.assertEqual(len(keys), 3 * 2 * 2)
        for g in self.report["groups"]:
            self.assertEqual(g["grade"], "usable", msg=(g["command"], g["distance_m"], g["arm"], g["checks"]))
            self.assertEqual(g["role"], "decisive" if g["distance_m"] == 2.0 else "secondary")
            self.assertEqual((g["metrics"]["n_sequences"], g["metrics"]["n_frames"]), (2, 2 * N_SEQ_FRAMES))

    def test_the_reader_reads_the_recorded_command_in_every_sequence(self):
        for rec in self.report["recordings"]:
            self.assertEqual(rec["sequence"]["final"]["command"], rec["command"], msg=rec["name"])
            self.assertGreaterEqual(rec["sequence"]["final"]["score"], 0.7)
            self.assertIsNotNone(rec["sequence"]["first_expected_frame"])

    def test_metrics_are_the_requested_numbers(self):
        g = next(g for g in self.report["groups"] if g["command"] == "WAIT" and g["distance_m"] == 2.0 and g["arm"] == "left")
        m = g["metrics"]
        self.assertEqual((m["person_rate"], m["arm_valid_rate"], m["hand_linked_rate"], m["own_cue_rate"], m["wrong_class_rate"]),
                         (1.0, 1.0, 1.0, 1.0, 0.0))
        self.assertEqual((m["keypoint_rates"]["left_shoulder"], m["keypoint_rates"]["left_elbow"], m["keypoint_rates"]["left_wrist"]), (1.0, 1.0, 1.0))
        self.assertEqual((m["hand_any_rate"], m["hand_landmarks_inside_rate"], m["category_rate"], m["finger_up_rate"], m["raised_rate"]),
                         (1.0, 1.0, 1.0, 1.0, 1.0))
        self.assertEqual(m["open_palm_rate"], 0.0)
        self.assertGreater(m["hand_box_h_px_median"], 0)
        self.assertEqual(m["sequence_reads"], {"WAIT": 2})
        self.assertEqual(m["frame_classes"], {"WAIT": 2 * N_SEQ_FRAMES})

    def test_point_arm_ratio_is_near_the_assumed_arm_length(self):
        g = next(g for g in self.report["groups"] if g["command"] == "POINT" and g["distance_m"] == 2.0 and g["arm"] == "left")
        self.assertAlmostEqual(g["metrics"]["arm_ratio"]["p95"], 1.4, delta=0.1)
        self.assertEqual(g["checks"]["arm_ratio_p95"]["grade"], "usable")

    def test_stop_group_has_no_arm_valid_check(self):
        g = next(g for g in self.report["groups"] if g["command"] == "STOP")
        self.assertNotIn("arm_valid_rate", g["checks"])
        self.assertIn("hand_linked_rate", g["checks"])

    def test_files_in_the_output_folder(self):
        for name in ("report.json", "report.md", "run.json"):
            self.assertTrue((self.out / name).is_file(), msg=name)
        data = json.loads((self.out / "report.json").read_text(encoding="utf-8"))
        self.assertEqual(data["verdicts"]["Mia"]["verdict"], "usable")
        self.assertEqual(len(data["recordings"]), 12 * 2)
        md = (self.out / "report.md").read_text(encoding="utf-8")
        for word in ("Verdict per look", "### Mia: **usable**", "Groups (look, command, distance, arm)", "Per look and command"):
            self.assertIn(word, md)

    def test_config_and_commit_are_saved(self):
        run_json = json.loads((self.out / "run.json").read_text(encoding="utf-8"))
        self.assertIn("commit", run_json["git"])
        self.assertEqual(run_json["input_folder"], "in")
        for name in ("look_check.json", "gesture_reader.json", "commander.json", "bridge.json", "hri_perception.json", "gesture_hri.json"):
            copy = self.out / "config_used" / name
            self.assertTrue(copy.is_file(), msg=name)
            self.assertIn(name, run_json["config_sha256"])
        orig = (ROOT / "configs/v4/look_check.json").read_bytes()
        self.assertEqual(lf((self.out / "config_used" / "look_check.json").read_bytes()), lf(orig))

    def test_run_json_has_no_absolute_path_of_the_input_or_the_output(self):
        text = (self.out / "run.json").read_text(encoding="utf-8")
        self.assertNotIn(str(self.root), text)
        self.assertNotIn(str(self.root).replace("\\", "/"), text)
        manifest = json.loads(text)["input_manifest"]
        self.assertEqual(len(manifest), 24 * N_SEQ_FRAMES * 2)                       # 24 sequences, a PNG and a header per frame
        self.assertTrue(all(len(m["sha256"]) == 64 and not m["path"].startswith("/") and ":" not in m["path"] for m in manifest))

    def test_annotated_pngs_are_drawn(self):
        import cv2
        p = self.out / "annotated" / "Mia__WAIT__2__l0" / "frame_005.png"
        self.assertTrue(p.is_file())
        img = cv2.imdecode(np.fromfile(str(p), np.uint8), cv2.IMREAD_COLOR)
        self.assertEqual(img.shape[:2], (vs.HEIGHT, vs.WIDTH))
        self.assertGreater(int((img.sum(axis=2) > 0).sum()), 500)                    # the source image is black: this is all drawing
        count = len(list((self.out / "annotated").rglob("*.png")))
        self.assertEqual(count, 12 * 2 * N_SEQ_FRAMES)

    def test_no_annotation_flag(self):
        with tempfile.TemporaryDirectory() as t:
            _, out = run(self.st, Path(t), annotate=False)
            self.assertFalse((out / "annotated").exists())


class FailureTests(unittest.TestCase):
    def build(self, **kw):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        st = Studio(Path(tmp.name) / "in")
        record_look(st, kw.pop("look", "Bad"), **kw)
        return run(st, Path(tmp.name), annotate=False)[0]

    def test_wait_hand_never_found_fails_with_the_check_named(self):
        rep = self.build(per_command={"WAIT": {"hand": False}})
        v = rep["verdicts"]["Bad"]
        self.assertEqual(v["verdict"], "fails")
        self.assertTrue(any("WAIT at 2 m" in r and "hand_linked_rate 0.0" in r and r.startswith("fails") for r in v["reasons"]), msg=v["reasons"])
        stop = [g for g in rep["groups"] if g["command"] == "STOP"]
        self.assertTrue(all(g["grade"] == "usable" for g in stop))

    def test_point_without_a_hand_is_only_weak(self):
        rep = self.build(per_command={"POINT": {"hand": False}})
        v = rep["verdicts"]["Bad"]
        self.assertEqual(v["verdict"], "weak", msg=v["reasons"])
        self.assertTrue(any("POINT at 2 m" in r and "capped at weak" in r for r in v["reasons"]), msg=v["reasons"])

    def test_wait_shown_as_open_palm_is_a_wrong_reading(self):
        rep = self.build(per_command={"WAIT": {"shown": "STOP"}})
        v = rep["verdicts"]["Bad"]
        self.assertEqual(v["verdict"], "fails")
        g = next(g for g in rep["groups"] if g["command"] == "WAIT" and g["arm"] == "left")
        self.assertEqual(g["metrics"]["wrong_class_rate"], 1.0)
        self.assertEqual(g["metrics"]["wrong_read_rate"], 1.0)
        self.assertEqual(g["metrics"]["sequence_reads"], {"STOP": 2})
        self.assertEqual(g["checks"]["wrong_read_rate"]["grade"], "fails")
        self.assertEqual(g["checks"]["sequence_read_rate"]["grade"], "fails")

    def test_arm_too_long_for_the_assumed_ratio_is_weak_never_fails(self):
        rep = self.build(per_command={"POINT": {"arm_scale": 1.6}})
        v = rep["verdicts"]["Bad"]
        self.assertEqual(v["verdict"], "weak", msg=v["reasons"])
        g = next(g for g in rep["groups"] if g["command"] == "POINT" and g["arm"] == "left")
        self.assertEqual(g["checks"]["arm_ratio_p95"]["grade"], "weak")
        self.assertGreater(g["metrics"]["arm_ratio"]["p95"], 1.75)
        self.assertTrue(all(r["sequence"]["final"]["command"] == "POINT" for r in rep["recordings"] if r["command"] == "POINT"))

    def test_lost_person_counts_as_lost_frames(self):
        with tempfile.TemporaryDirectory() as t:
            st = Studio(Path(t) / "in")
            record_look(st, "L", commands=("WAIT",), arms=("left",), n_seq=0)
            for n in range(2):                                      # 4 of 11 frames without a person
                dets = [pose("WAIT")] * 7 + [lc.Detection()] * 4
                st.sequence(f"L__WAIT__2__l{n}", dets, "left")
            rep, _ = run(st, Path(t), annotate=False)
            g = rep["groups"][0]
            self.assertAlmostEqual(g["metrics"]["person_rate"], 14 / 22, places=3)
            self.assertEqual(g["checks"]["person_rate"]["grade"], "fails")
            self.assertEqual(rep["recordings"][0]["frames"][-1]["person"], False)
            self.assertEqual(rep["recordings"][0]["sequence"]["final"]["why"], "no person in the last frame")

    def test_negative_control_that_reads_a_command_fails_the_look(self):
        rep = self.build(commands=("POINT", "WAIT", "STOP", "NONE"), per_command={"NONE": {}})
        self.assertEqual(rep["verdicts"]["Bad"]["verdict"], "usable")
        with tempfile.TemporaryDirectory() as t:
            st = Studio(Path(t) / "in")
            record_look(st, "N", commands=("POINT", "WAIT", "STOP"))
            for arm in ("left", "right"):
                for n in range(2):
                    st.sequence(f"N__NONE__2__{arm[0]}{n}", [pose("STOP", arm)] * N_SEQ_FRAMES, arm)    # recorded as arms down, shows STOP
            rep, _ = run(st, Path(t), annotate=False)
            v = rep["verdicts"]["N"]
            self.assertEqual(v["verdict"], "fails")
            self.assertTrue(any("negative control" in r for r in v["reasons"]))


class DataAmountTests(unittest.TestCase):
    def build(self, **kw):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        st = Studio(Path(tmp.name) / "in")
        record_look(st, kw.pop("look", "Few"), **kw)
        return run(st, Path(tmp.name), annotate=False)[0]

    def test_missing_command_is_insufficient_data_not_usable(self):
        v = self.build(commands=("POINT", "WAIT"))["verdicts"]["Few"]
        self.assertEqual(v["verdict"], "insufficient_data")
        self.assertTrue(any("STOP at 2 m, left arm: no recording" in r for r in v["reasons"]), msg=v["reasons"])

    def test_one_sequence_per_group_is_not_enough(self):
        v = self.build(n_seq=1)["verdicts"]["Few"]
        self.assertEqual(v["verdict"], "insufficient_data")
        self.assertTrue(any("sequence_read_rate not evaluated" in r for r in v["reasons"]), msg=v["reasons"])

    def test_only_the_4_m_distance_is_not_enough(self):
        v = self.build(dists=(4.0,))["verdicts"]["Few"]
        self.assertEqual(v["verdict"], "insufficient_data")

    def test_one_arm_missing_when_arms_are_labelled(self):
        v = self.build(arms=("left",))["verdicts"]["Few"]
        self.assertEqual(v["verdict"], "insufficient_data")
        self.assertTrue(any("right arm: no recording" in r for r in v["reasons"]), msg=v["reasons"])

    def test_unlabelled_arms_are_pooled_and_inferred(self):
        rep = self.build(arms=("left", "right"), label=False, n_seq=2)
        v = rep["verdicts"]["Few"]
        self.assertFalse(v["arms_labelled"])
        self.assertEqual(v["verdict"], "usable", msg=v["reasons"])
        self.assertEqual({g["arm"] for g in rep["groups"]}, {"?"})
        frames = [f for r in rep["recordings"] for f in r["frames"] if r["command"] == "WAIT"]
        self.assertTrue(all(f["arm_source"] == "inferred" for f in frames))

    def test_4_m_failure_lowers_to_weak_only(self):
        with tempfile.TemporaryDirectory() as t:
            st = Studio(Path(t) / "in")
            record_look(st, "Far", dists=(2.0,))
            record_look(st, "Far", dists=(4.0,), per_command={"WAIT": {"hand": False}})
            rep, _ = run(st, Path(t), annotate=False)
            v = rep["verdicts"]["Far"]
            self.assertEqual(v["verdict"], "weak", msg=v["reasons"])
            self.assertTrue(any("WAIT at 4 m" in r and "not the asking distance" in r for r in v["reasons"]))
            g = next(g for g in rep["groups"] if g["command"] == "WAIT" and g["distance_m"] == 4.0 and g["arm"] == "left")
            self.assertEqual(g["grade"], "fails")

    def test_other_distances_are_reported_not_judged(self):
        with tempfile.TemporaryDirectory() as t:
            st = Studio(Path(t) / "in")
            record_look(st, "Mid", dists=(2.0,))
            record_look(st, "Mid", dists=(3.0,), per_command={"WAIT": {"hand": False}})
            rep, _ = run(st, Path(t), annotate=False)
            self.assertEqual(rep["verdicts"]["Mid"]["verdict"], "usable")
            self.assertTrue(any(g["role"] == "other" and g["distance_m"] == 3.0 for g in rep["groups"]))

    def test_distance_within_tolerance_joins_the_decisive_group(self):
        with tempfile.TemporaryDirectory() as t:
            st = Studio(Path(t) / "in")
            for n in range(2):
                for arm in ("left", "right"):
                    for c in ("POINT", "WAIT", "STOP"):
                        d = 2.1 if n else 1.9
                        st.sequence(f"T__{c}__{d:g}__{arm[0]}{n}", [pose(c, arm)] * N_SEQ_FRAMES, arm)
            rep, _ = run(st, Path(t), annotate=False)
            self.assertEqual(rep["verdicts"]["T"]["verdict"], "usable", msg=rep["verdicts"]["T"]["reasons"])
            self.assertEqual({g["distance_m"] for g in rep["groups"]}, {2.0})


class SinglesAndErrorsTests(unittest.TestCase):
    def test_single_frames_report_frame_cues_but_no_sequence_read(self):
        with tempfile.TemporaryDirectory() as t:
            st = Studio(Path(t) / "in")
            for n in range(12):
                st.frame(f"S__WAIT__2.0__{n}", pose("WAIT"), "left")
            rep, out = run(st, Path(t))
            g = rep["groups"][0]
            self.assertEqual((g["metrics"]["n_singles"], g["metrics"]["n_sequences"]), (12, 0))
            self.assertEqual(g["metrics"]["own_cue_rate"], 1.0)
            self.assertIsNone(g["metrics"]["sequence_read_rate"])
            self.assertEqual(g["checks"]["sequence_read_rate"]["grade"], "not_evaluated")
            self.assertEqual(rep["verdicts"]["S"]["verdict"], "insufficient_data")
            self.assertTrue((out / "annotated" / "S__WAIT__2.0__3.png").is_file())

    def test_bad_header_frame_is_excluded_and_listed(self):
        with tempfile.TemporaryDirectory() as t:
            st = Studio(Path(t) / "in")
            record_look(st, "H", commands=("WAIT",), arms=("left",), n_seq=0)
            st.sequence("H__WAIT__2__a", [pose("WAIT")] * N_SEQ_FRAMES, "left")
            st.header(Path(t) / "in" / "H__WAIT__2__a" / "frame_004.png", "left", fx=999.0)
            (Path(t) / "in" / "H__WAIT__2__a" / "frame_007.json").unlink()
            rep, out = run(st, Path(t), annotate=False)
            r = rep["recordings"][0]
            self.assertEqual((r["n_files"], r["n_frames"], len(r["errors"])), (N_SEQ_FRAMES, N_SEQ_FRAMES - 2, 2))
            self.assertEqual(len(rep["problems"]), 2)
            self.assertIn("Problems with the input", (out / "report.md").read_text(encoding="utf-8"))

    def test_unparsable_names_are_listed_not_fatal(self):
        with tempfile.TemporaryDirectory() as t:
            st = Studio(Path(t) / "in")
            st.frame("oops", pose("WAIT"))
            st.frame("S__WAIT__2__1", pose("WAIT"), "left")
            rep, _ = run(st, Path(t), annotate=False)
            self.assertTrue(any("oops" in p for p in rep["problems"]))
            self.assertEqual(len(rep["recordings"]), 1)

    def test_empty_folder_gives_an_empty_report(self):
        with tempfile.TemporaryDirectory() as t:
            (Path(t) / "in").mkdir()
            rep, out = run(Studio(Path(t) / "in"), Path(t))
            self.assertEqual(rep["verdicts"], {})
            self.assertTrue((out / "report.md").is_file())

    def test_header_times_are_used_when_all_frames_have_them(self):
        with tempfile.TemporaryDirectory() as t:
            st = Studio(Path(t) / "in")
            for i in range(N_SEQ_FRAMES):
                p = Path(t) / "in" / "S__POINT__2__1" / f"frame_{i:03d}.png"
                st.png(p, pose("POINT"))
                st.header(p, "left", time_s=5.0 + 0.1 * i)
            rep, _ = run(st, Path(t), annotate=False)
            ts = [f["t"] for f in rep["recordings"][0]["frames"]]
            self.assertEqual((ts[0], ts[-1]), (5.0, 6.0))
            self.assertEqual(rep["recordings"][0]["sequence"]["final"]["command"], "POINT")

    def test_conflicting_arm_labels_are_reported(self):
        with tempfile.TemporaryDirectory() as t:
            st = Studio(Path(t) / "in")
            st.sequence("S__POINT__2__1", [pose("POINT")] * 3, "left")
            st.header(Path(t) / "in" / "S__POINT__2__1" / "frame_002.png", "right")
            rep, _ = run(st, Path(t), annotate=False)
            self.assertTrue(any("different arm labels" in e for e in rep["recordings"][0]["errors"]))
            self.assertEqual(rep["recordings"][0]["arm"], "left")


class DrawingTests(unittest.TestCase):
    def test_line_and_marker_clip_to_the_image_and_skip_bad_points(self):
        img = np.zeros((20, 30, 3), np.uint8)
        lc._line(img, np.array([-10.0, 5.0]), np.array([100.0, 5.0]), (1, 2, 3), 2)
        self.assertTrue((img[5, 0] == (1, 2, 3)).all() and (img[5, 29] == (1, 2, 3)).all())
        before = img.copy()
        lc._line(img, np.array([np.nan, 0.0]), np.array([5.0, 5.0]), (9, 9, 9))
        lc._marker(img, np.array([np.inf, 1.0]), 3, (9, 9, 9), True)
        self.assertTrue(np.array_equal(img, before))
        lc._marker(img, np.array([-50.0, 400.0]), 3, (9, 9, 9), True)                 # fully outside: nothing, no error
        lc._marker(img, np.array([15.0, 10.0]), 2, (7, 7, 7), True)
        self.assertTrue((img[10, 15] == (7, 7, 7)).all())

    def test_only_cv2_names_allowed_by_the_pipeline_pin_are_used(self):
        import re
        from test_opencv import USED
        names = set(re.findall(r"\bcv2\.(\w+)", (ROOT / "look_check_v4.py").read_text(encoding="utf-8")))
        self.assertEqual(sorted(names - set(USED)), [])


class CommandLineTests(unittest.TestCase):
    def test_main_writes_a_new_timestamped_folder_and_prints_verdicts(self):
        import contextlib
        import io
        with tempfile.TemporaryDirectory() as t:
            root = Path(t)
            st = Studio(root / "in")
            record_look(st, "Mia")
            cfg = json.loads(json.dumps(CFG))
            cfg["paths"]["output_root"] = str(root / "outputs")
            (root / "cfg.json").write_text(json.dumps(cfg), encoding="utf-8")
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                rc = lc.main(["--input", str(root / "in"), "--config", str(root / "cfg.json"), "--no-annotate"], detector=st)
            self.assertEqual(rc, 0)
            folders = list((root / "outputs").glob("look_check_v4_*"))
            self.assertEqual(len(folders), 1)
            self.assertIn("Mia: usable", buf.getvalue())
            self.assertTrue((folders[0] / "report.json").is_file())
            run_json = json.loads((folders[0] / "run.json").read_text(encoding="utf-8"))
            self.assertIn("--no-annotate", run_json["command"])
            self.assertNotIn(str(root), run_json["command"])

    def test_missing_input_folder_stops_with_a_message(self):
        with self.assertRaises(SystemExit):
            lc.main(["--input", str(ROOT / "no_such_folder_here")], detector=object())


if __name__ == "__main__":
    unittest.main()
