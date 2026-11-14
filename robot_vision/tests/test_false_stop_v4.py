"""analyse_false_stop_v4.py (AUDIT.md 16.14): the candidate cues on synthetic landmarks, the truth categories, the stop episodes, the development
guard, that a variant leaves the reader as it was, and a whole analysis on a tiny synthetic zip (no real data, no models)."""

import ast
import io
import json
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))

import analyse_false_stop_v4 as fs  # noqa: E402
import commander_v4 as cm  # noqa: E402
import gesture_motion as gm  # noqa: E402
import v4_synth as vs  # noqa: E402

CFG = fs.load_config()
RC, CC = gm.load_config(), cm.load_config()


def lm(index=(10.0, -20.0), pinky=(-10.0, -20.0), index_tip=(14.0, -60.0), pinky_tip=(-14.0, -50.0)):
    a = np.zeros((21, 2))
    a[gm.INDEX_MCP], a[17], a[gm.INDEX_TIP], a[gm.PINKY_TIP] = index, pinky, index_tip, pinky_tip
    return a


class CueTests(unittest.TestCase):
    def test_palm_facing_sign_follows_the_persons_own_side(self):
        right_palm_to_camera = lm()                                   # thumb side (index knuckle) at the image right: a right hand, palm toward the camera
        self.assertGreater(fs.palm_facing(right_palm_to_camera, "right"), 0.5)
        self.assertLess(fs.palm_facing(right_palm_to_camera, "left"), -0.5)
        mirrored = lm(index=(-10.0, -20.0), pinky=(10.0, -20.0))      # the left hand with its palm toward the camera
        self.assertGreater(fs.palm_facing(mirrored, "left"), 0.5)
        self.assertLess(fs.palm_facing(mirrored, "right"), -0.5)
        self.assertEqual(fs.palm_facing(np.zeros((21, 2)), "right"), 0.0)                      # degenerate hand: no sign

    def test_fingertip_spread_is_one_for_fingers_together_and_larger_for_a_fan(self):
        together = lm(index_tip=(10.0, -60.0), pinky_tip=(-10.0, -60.0))
        fan = lm(index_tip=(30.0, -60.0), pinky_tip=(-30.0, -50.0))
        self.assertAlmostEqual(fs.fingertip_spread(together), 1.0, places=6)
        self.assertGreater(fs.fingertip_spread(fan), 2.5)
        self.assertEqual(fs.fingertip_spread(np.zeros((21, 2))), 0.0)

    def test_wrist_speed_in_torso_lengths_and_none_without_enough_samples(self):
        def sample(t, x):
            kp, conf = vs.body()
            h = vs.hand(kp[gm.ARMS["right"][2]] + np.array([x, 0.0]), axis=(0.0, -1.0))
            return vs.sample(t, kp, conf, {"right": h})
        torso = gm.torso_frame(*vs.body(), RC["keypoints"]["body_kp_conf_min"])[0]
        s = [sample(0.0, 0.0), sample(0.1, 0.1 * torso), sample(0.2, 0.2 * torso)]
        self.assertAlmostEqual(fs.wrist_speed(s, "right", RC, 0.2, 0.3), 1.0, places=2)         # one torso length per second
        self.assertIsNone(fs.wrist_speed(s[:1], "right", RC, 0.0, 0.3))
        self.assertIsNone(fs.wrist_speed(s, "left", RC, 0.2, 0.3))                               # no hand on that side


class EpisodeAndCategoryTests(unittest.TestCase):
    def test_episodes_merge_close_readings(self):
        ev = [(1.0, "PROCEED"), (1.2, "PROCEED"), (3.0, "POINT"), (3.3, "nothing")]
        got = fs.episodes(ev, 0.5)
        self.assertEqual([(e["t0"], e["t1"], e["category"]) for e in got], [(1.0, 1.2, "PROCEED"), (3.0, 3.3, "POINT")])

    def test_live_stop_episodes_come_from_the_state_text(self):
        rows = [{"time_s": str(t), "trial": "1", "state": s, "v": str(v)} for t, s, v in
                [(0.0, "navigate", 0.8), (0.1, "navigate (stopped: STOP gesture)", 0.8), (0.2, "navigate (stopped: STOP gesture)", 0.7),
                 (0.3, "navigate", 0.6), (5.0, "read (stopped: STOP gesture)", 0.0)]]
        eps = fs.live_stop_episodes(rows)
        self.assertEqual([(e["state"], e["rows"], e["v_before"]) for e in eps], [("navigate", 2, 0.8), ("read", 1, 0.6)])

    def truth(self, command, phase):
        rows = [{"time_s": t / 20.0, "worker_id": 1, "look": "sunbox_m1", "x": 0.0, "z": 5.0, "true_command": command, "point_angle_deg": -1,
                 "arm": "right", "phase": phase, "is_commander": True} for t in range(0, 40)]
        return {1: rows}

    def test_category_is_what_the_matched_worker_shows(self):
        frame = {"time_s": 1.0, "pose": {"x": 0.0, "z": 0.0, "yaw_deg": 0.0}}
        near = type("P", (), {"bearing_deg": 2.0})()
        far = type("P", (), {"bearing_deg": 40.0})()
        self.assertEqual(fs.category_of(frame, near, self.truth("PROCEED", "holding"), CFG), (1, "PROCEED"))
        self.assertEqual(fs.category_of(frame, near, self.truth("POINT", "gesturing"), CFG), (1, "POINT"))
        self.assertEqual(fs.category_of(frame, near, self.truth("NONE", "idle"), CFG), (1, "nothing"))
        self.assertEqual(fs.category_of(frame, near, self.truth("PROCEED", "start_delay"), CFG)[1], "nothing")
        self.assertEqual(fs.category_of(frame, near, self.truth("PROCEED", "returning"), CFG), (1, None))         # left out
        self.assertEqual(fs.category_of(frame, far, self.truth("PROCEED", "holding"), CFG), (None, "unmatched"))


class VariantTests(unittest.TestCase):
    def stop_samples(self, raised: bool):
        """A person who holds an open hand for 0.5 s, the arm raised or hanging."""
        out = []
        for i in range(6):
            kw = {"right": vs.direction(90.0)} if raised else {}
            kp, conf = vs.body(**kw)
            w = kp[gm.ARMS["right"][2]]
            h = vs.hand(w, axis=(0.0, -1.0), category="Open_Palm", fan_deg=18.0)
            out.append(vs.sample(i * 0.1, kp, conf, {"right": h}))
        return out

    def test_the_reader_reads_stop_before_and_a_variant_changes_it_only_inside_the_block(self):
        flags_before, window_before = gm.frame_flags, gm._arm_window
        hanging = self.stop_samples(False)
        r0 = gm.read_window(hanging, RC, hanging[-1].t)
        self.assertEqual(r0.command, "STOP")                                                   # a hanging open hand reads STOP: the false STOP
        with fs.candidate({"raised": True}, RC):
            self.assertIsNot(gm.frame_flags, flags_before)
            self.assertNotEqual(gm.read_window(hanging, RC, hanging[-1].t).command, "STOP")
            self.assertEqual(gm.read_window(self.stop_samples(True), RC, 0.5).command, "STOP")      # a raised arm still reads STOP
        self.assertIs(gm.frame_flags, flags_before)
        self.assertIs(gm._arm_window, window_before)
        self.assertEqual(gm.read_window(hanging, RC, hanging[-1].t).command, "STOP")

    def test_the_variant_is_restored_after_an_error(self):
        before = gm.frame_flags
        with self.assertRaises(RuntimeError):
            with fs.candidate({"palm": 0.1}, RC):
                raise RuntimeError("x")
        self.assertIs(gm.frame_flags, before)

    def test_spread_and_palm_variants_veto_a_stop_hand(self):
        s = self.stop_samples(True)
        self.assertEqual(gm.read_window(s, RC, 0.5).command, "STOP")
        with fs.candidate({"spread": 50.0}, RC):                                              # no hand spreads that far
            self.assertNotEqual(gm.read_window(s, RC, 0.5).command, "STOP")

    def test_the_variants_listed_in_the_config(self):
        names = [v["name"] for v in fs.variants(CFG)]
        self.assertEqual(names[0], "before (the live reader)")
        self.assertEqual(len(names), 1 + 4 + 5 + 2 + 4 + 2)                                  # palm grid, spread grid, static modes, combined, extras
        self.assertTrue(any(n.startswith("EXTRA") for n in names))
        self.assertTrue(any(n.startswith("all three") for n in names))


class GuardTests(unittest.TestCase):
    def test_test_looks_and_clips_are_refused(self):
        def tr(look, clip):
            return {1: [{"look": look, "clip": clip}]}
        self.assertEqual(fs.guard(tr("sunbox_m1", "proceed_ik_01")), "development")
        for look, clip in (("sunbox_f2", "proceed_ik_01"), ("sunbox_m1", "proceed_ik_03"), ("sunbox_m_shirt_plaid", "point_ik_01"),
                           ("sunbox_unlisted", "point_ik_01"), ("sunbox_m1", "point_mixamo_02")):
            with self.assertRaises(SystemExit, msg=(look, clip)):
                fs.guard(tr(look, clip))


def zip_of(tmp: Path, look="sunbox_m1", clip="proceed_ik_01") -> Path:
    """A tiny session: one worker 5 m ahead holds an open hand (truth PROCEED) for 2 s; pan-tilt frames at 10 Hz with the person and the hand."""
    root = "logs/"
    frames, rows = [], []
    for i in range(30):
        t = round(i * 0.1, 4)
        kp, conf = vs.body(z0=5.0)
        h = vs.hand(kp[gm.ARMS["right"][2]], axis=(0.0, -1.0), z=5.0, category="Open_Palm", fan_deg=18.0)
        frames.append({"cam": "pan_tilt", "time_s": t, "frame_index": i, "pose": {"x": 0.0, "z": 0.0, "yaw_deg": 0.0}, "pan_deg": 0.0, "tilt_deg": 0.0,
                       "vertical_fov_deg": 60.0, "fx": vs.FX, "fy": vs.FY, "cx": vs.CX, "cy": vs.CY, "width": vs.WIDTH, "height": vs.HEIGHT,
                       "people": [{"track_id": 1, "box": [float(kp[:, 0].min()) - 20, float(kp[:, 1].min()) - 20, float(kp[:, 0].max()) + 20, float(kp[:, 1].max()) + 20],
                                   "kp": [[float(x), float(y), 1.0] for x, y in kp]}],
                       "hands": [{"track_id": 1, "category": "Open_Palm", "score": 0.9, "handedness": "Right", "lm": h.landmarks_px.tolist(), "world": None,
                                  "box": list(h.box), "wrist": list(h.wrist)}]})
    for k in range(60):
        rows.append({"time_s": k * 0.05, "worker_id": 1, "look": look, "x": 0.0, "z": 5.0, "true_command": "PROCEED", "point_angle_deg": -1, "arm": "right",
                     "phase": "holding", "is_commander": True, "clip": clip})
    p = tmp / "logs.zip"
    with zipfile.ZipFile(p, "w") as z:
        z.writestr(root + "bridge_x/model_outputs.jsonl", "".join(json.dumps(f) + "\n" for f in frames))
        z.writestr(root + "bridge_x/decisions.csv", "trial,time_s,state,x,z,yaw_deg,v,omega,v_cmd,gesture,safety\n"
                   "1,1.0,read,0,0,0,0.0,0,0,NONE,\n1,1.5,read (stopped: STOP gesture),0,0,0,0.0,0,0,STOP,STOP gesture\n")
        z.writestr(root + "trials_x/run_001/truth.jsonl", "".join(json.dumps(r) + "\n" for r in rows))
    return p


class WholeAnalysisTests(unittest.TestCase):
    cfg = {**CFG, "sessions": {"S": {"bridge": "bridge_x", "unity": "trials_x", "what": "synthetic"}}}

    def test_a_tiny_zip_is_read_in_place_and_the_cues_do_what_they_say(self):
        with tempfile.TemporaryDirectory() as t:
            p = zip_of(Path(t))
            before = sorted(Path(t).iterdir())
            rep = fs.analyse(fs.Logs(p), self.cfg, RC, CC)
            self.assertEqual(sorted(Path(t).iterdir()), before)                                   # nothing extracted or written
            self.assertEqual(len(rep["zip"]["sha256"]), 64)
            self.assertEqual(rep["guard"], {"S/run_001": "development"})
            by = {v["name"]: v["by_category"] for v in rep["variants"]}
            base = by["before (the live reader)"]["PROCEED"]
            self.assertGreater(base["person_frames"], 20)
            self.assertGreater(base["stop_frames"], 10)                                           # a held open hand reads STOP, here on a PROCEED recording
            self.assertEqual(by["EXTRA: arm raised (the reader's flag) alone"]["PROCEED"]["stop_frames"], 0)    # its arm hangs
            counts = [by[f"fingertip spread >= {v:g}"]["PROCEED"]["stop_frames"] for v in CFG["candidates"]["spread"]["min_values"]]
            self.assertEqual(counts, sorted(counts, reverse=True))                                # a stricter spread never reads more STOPs
            self.assertLessEqual(by["EXTRA: all three + arm raised"]["PROCEED"]["stop_frames"], base["stop_frames"])
            self.assertEqual(rep["true_stop"]["frames_with_a_true_STOP_in_the_zip"], 0)
            self.assertEqual(rep["replay_check"]["S"]["decisions_STOP_rows"], 1)
            md = fs.markdown(rep)
            self.assertIn("before (the live reader)", md)

    def test_a_test_look_in_the_zip_stops_everything(self):
        with tempfile.TemporaryDirectory() as t:
            p = zip_of(Path(t), look="sunbox_f2")
            with self.assertRaises(SystemExit):
                fs.analyse(fs.Logs(p), self.cfg, RC, CC)


class IsolationTests(unittest.TestCase):
    def test_inference_code_never_imports_the_analysis(self):
        offenders = []
        for p in ROOT.rglob("*.py"):
            rel = p.relative_to(ROOT)
            if ".venv" in rel.parts or rel.parts[0] == "tests" or rel.name == "analyse_false_stop_v4.py":
                continue
            tree = ast.parse(p.read_text(encoding="utf-8"))
            mods = {a.name.split(".")[0] for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names}
            mods |= {n.module.split(".")[0] for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) and n.module}
            if "analyse_false_stop_v4" in mods:
                offenders.append(str(rel))
        self.assertEqual(offenders, [])

    def test_the_reader_is_not_changed_by_importing_it(self):
        import importlib
        self.assertIs(gm.frame_flags, importlib.import_module("gesture_motion").frame_flags)


if __name__ == "__main__":
    unittest.main()
