"""v4 truth loader, truth-to-frame join and labelled clips (gesture_data.py) on small truth.jsonl and frame fixtures
generated here (no Unity). Also: hri_trials.py copies Unity's run_###/ folders (v4), and its v3 output is unchanged."""

import ast
import hashlib
import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))

import decision_io as dio  # noqa: E402
import gesture_data as gd  # noqa: E402
import hri_trials as ht  # noqa: E402

CFG = gd.load_config()


def row(t, worker=1, look="look_a", x=2.0, z=3.0, cmd="NONE", angle=-1, arm="none", phase="idle", commander=False, **extra):
    return {"time_s": t, "worker_id": worker, "look": look, "x": x, "z": z, "true_command": cmd, "point_angle_deg": angle,
            "arm": arm, "phase": phase, "is_commander": commander, **extra}


def lines(rows):
    return [json.dumps(r) for r in rows]


def scenario():
    """Worker 1 (commander) in one POINT then one WAIT gesture, worker 2 a bystander who only stands. Rows every 0.1 s."""
    rows = []
    for i in range(30):
        t = 100.0 + 0.1 * i
        if i < 3:
            c1 = dict(cmd="NONE", phase="idle")
        elif i < 5:
            c1 = dict(cmd="POINT", angle=40.0 + i, arm="right", phase="gesturing", clip="point_a")
        elif i < 10:
            c1 = dict(cmd="POINT", angle=50.0, arm="right", phase="holding", clip="point_a")
        elif i < 12:
            c1 = dict(cmd="NONE", phase="returning")
        elif i < 20:
            c1 = dict(cmd="WAIT", arm="left", phase="holding", clip="wait_a")
        else:
            c1 = dict(cmd="NONE", phase="idle")
        rows.append(row(t, 1, "look_a", 5.0, 5.0, commander=c1["cmd"] != "NONE", **c1))
        rows.append(row(t, 2, "look_b", 8.0, 5.0))
    return rows


def frames(t0, n, step=0.1, x=5.0, z=3.0):
    return [{"frame_index": i, "time_s": round(t0 + step * i, 6), "pose": {"x": x, "z": z, "yaw_deg": 0.0}} for i in range(n)]


class ParseTests(unittest.TestCase):
    def test_valid_file(self):
        rows = gd.parse_truth(lines(scenario()), CFG)
        self.assertEqual(len(rows), 60)
        self.assertEqual((rows[0].worker_id, rows[0].look, rows[0].true_command, rows[0].clip), (1, "look_a", "NONE", ""))

    def test_blank_lines_skipped_but_counted(self):
        text = lines([row(1.0)]) + ["", "  "] + lines([row(1.1, cmd="NONE")])
        rows = gd.parse_truth(text, CFG)
        self.assertEqual([r.line for r in rows], [1, 4])

    def test_each_bad_line_names_file_and_line(self):
        good = row(1.0)
        cases = [
            ("{oops", "not valid JSON"),
            ("[1, 2]", "not a JSON object"),
            (json.dumps({k: v for k, v in good.items() if k != "look"}), "missing field 'look'"),
            (json.dumps({**good, "worker_id": "1"}), "'worker_id' has a wrong type"),
            (json.dumps({**good, "is_commander": 1}), "'is_commander' has a wrong type"),
            (json.dumps({**good, "time_s": True}), "'time_s' has a wrong type"),
            (json.dumps({**good, "look": ""}), "'look' has a wrong type or value"),
            (json.dumps({**good, "true_command": "WAVE"}), "true_command 'WAVE' is not one of"),
            (json.dumps({**good, "arm": "both"}), "arm 'both' is not one of"),
            (json.dumps({**good, "phase": "dancing"}), "phase 'dancing' is not one of"),
            (json.dumps({**good, "point_angle_deg": 30.0}), "point_angle_deg must be -1 unless true_command is POINT"),
            (json.dumps({**good, "clip": 3}), "'clip' must be a string"),
            ('{"time_s": NaN, "worker_id": 1}', "not valid JSON"),
        ]
        for bad, expect in cases:
            with self.subTest(expect):
                with self.assertRaises(gd.TruthError) as cm:
                    gd.parse_truth([json.dumps(good), bad], CFG, where="truth.jsonl")
                self.assertTrue(str(cm.exception).startswith("truth.jsonl line 2: "), str(cm.exception))
                self.assertIn(expect, str(cm.exception))

    def test_point_may_have_any_angle_including_minus_one(self):
        gd.parse_truth(lines([row(1.0, cmd="POINT", angle=-1, arm="left", phase="holding")]), CFG)

    def test_look_must_stay_the_same_per_worker(self):
        with self.assertRaisesRegex(gd.TruthError, "line 2: worker 1 has look 'b' but 'a' earlier"):
            gd.parse_truth(lines([row(1.0, look="a"), row(1.1, look="b")]), CFG)

    def test_time_must_not_go_backwards_per_worker(self):
        gd.parse_truth(lines([row(1.0, 1), row(0.5, 2), row(1.1, 1)]), CFG)          # other workers may interleave
        with self.assertRaisesRegex(gd.TruthError, "line 2: time_s 0.9 goes backwards"):
            gd.parse_truth(lines([row(1.0), row(0.9)]), CFG)

    def test_two_commanders_at_one_time(self):
        with self.assertRaisesRegex(gd.TruthError, "line 2: two commanders at time_s 1.0"):
            gd.parse_truth(lines([row(1.0, 1, commander=True), row(1.0, 2, look="b", commander=True)]), CFG)
        gd.parse_truth(lines([row(1.0, 1, commander=True), row(1.1, 2, look="b", commander=True)]), CFG)

    def test_load_truth_reads_a_file_and_names_it(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "truth.jsonl"
            p.write_text("\n".join(lines(scenario())) + "\n", encoding="utf-8")
            self.assertEqual(len(gd.load_truth(p, CFG)), 60)
            p.write_text("{}\n", encoding="utf-8")
            with self.assertRaisesRegex(gd.TruthError, r"truth\.jsonl line 1"):
                gd.load_truth(p, CFG)

    def test_config_lists_are_the_protocol_ones(self):
        self.assertEqual(CFG["truth_join_max_s"], 0.06)
        self.assertEqual(CFG["commands"], ["POINT", "WAIT", "STOP", "NONE"])
        self.assertEqual(CFG["phases"], ["idle", "start_delay", "gesturing", "holding", "returning"])


class JoinTests(unittest.TestCase):
    def setUp(self):
        self.rows = gd.parse_truth(lines(scenario()), CFG)

    def test_frames_within_tolerance_get_each_workers_row(self):
        j = gd.join(frames(100.5, 3), self.rows, CFG)       # exactly on rows 100.5, 100.6, 100.7
        self.assertEqual(len(j.labels), 6)                  # 3 frames x 2 workers
        self.assertEqual(j.unlabelled_frames, [])
        first = [lab for lab in j.labels if lab["frame_index"] == 0 and lab["worker_id"] == 1][0]
        self.assertEqual((first["row"].true_command, first["dt_s"]), ("POINT", 0.0))
        self.assertEqual(first["distance_m"], round(((5 - 5) ** 2 + (5 - 3) ** 2) ** 0.5, 4))

    def test_nearest_row_wins_and_dt_is_signed(self):
        j = gd.join([{"frame_index": 7, "time_s": 100.53, "pose": {"x": 5.0, "z": 3.0}}], self.rows, CFG)
        lab = [x for x in j.labels if x["worker_id"] == 1][0]
        self.assertEqual(lab["row"].time_s, 100.5)
        self.assertAlmostEqual(lab["dt_s"], -0.03)

    def test_outside_tolerance_is_unlabelled_not_guessed(self):
        rows = [r for r in self.rows if not 100.3 < r.time_s < 100.8]     # a gap in the truth
        j = gd.join([{"frame_index": 1, "time_s": 100.55}, {"frame_index": 2, "time_s": 100.0}], rows, CFG)
        self.assertEqual(j.unlabelled_frames, [1])
        self.assertEqual({lab["frame_index"] for lab in j.labels}, {2})

    def test_tolerance_is_taken_from_the_config(self):
        rows = [r for r in self.rows if r.time_s in (100.0, 101.0)]
        f = [{"frame_index": 0, "time_s": 100.05}]
        self.assertEqual(len(gd.join(f, rows, {**CFG, "truth_join_max_s": 0.06}).labels), 2)
        self.assertEqual(len(gd.join(f, rows, {**CFG, "truth_join_max_s": 0.04}).labels), 0)

    def test_frames_before_and_after_the_truth_and_no_pose(self):
        j = gd.join([{"frame_index": 0, "time_s": 90.0}, {"frame_index": 1, "time_s": 100.0},
                     {"frame_index": 2, "time_s": 110.0}], self.rows, CFG)
        self.assertEqual(j.unlabelled_frames, [0, 2])
        self.assertIsNone(j.labels[0]["distance_m"])
        self.assertEqual(j.coverage(), "1 of 3 frames have a truth label within 0.06 s")

    def test_no_clock_offset_is_applied(self):
        # frames carry Unity Time.time and so do the rows: a frame at 0.0 does not match rows at 100.0
        self.assertEqual(len(gd.join([{"frame_index": 0, "time_s": 0.0}], self.rows, CFG).labels), 0)

    def test_frames_from_messages(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "messages.jsonl"
            msgs = [{"dir": "in", "type": "telemetry", "header": {"time_s": 1.0}},
                    {"dir": "in", "type": "frame_pan_tilt", "header": {"frame_index": 4, "time_s": 100.5, "pose": {"x": 5.0, "z": 3.0, "yaw_deg": 0.0}}},
                    {"dir": "in", "type": "frame_360", "header": {"frame_index": 9, "time_s": 100.5}},
                    {"dir": "out", "type": "command", "header": {}},
                    {"dir": "in", "type": "frame_pan_tilt", "header": {"frame_index": 5, "time_s": 100.6}}]
            p.write_text("\n".join(json.dumps(m) for m in msgs) + "\n")
            f = gd.frames_from_messages(p)
            self.assertEqual([x["frame_index"] for x in f], [4, 5])
            self.assertIsNone(f[1]["pose"])


class ClipTests(unittest.TestCase):
    def setUp(self):
        self.rows = gd.parse_truth(lines(scenario()), CFG)
        self.clips = gd.build_clips(self.rows)

    def test_clips_per_worker_and_gesture(self):
        self.assertEqual([(c.worker_id, c.command, c.arm, c.look, c.clip) for c in self.clips],
                         [(1, "POINT", "right", "look_a", "point_a"), (1, "WAIT", "left", "look_a", "wait_a")])
        point, wait = self.clips
        self.assertEqual((point.n_rows, point.phases), (7, ["gesturing", "holding"]))
        self.assertEqual((point.t_start, point.t_end), (100.3, 100.9))
        self.assertEqual(point.commander_share, 1.0)
        self.assertEqual(point.point_angle_hold_deg, 50.0)         # holding rows only, not the moving 43 / 44
        self.assertIsNone(wait.point_angle_hold_deg)
        self.assertEqual(wait.phases, ["holding"])

    def test_bystander_who_never_gestures_has_no_clip(self):
        self.assertTrue(all(c.worker_id == 1 for c in self.clips))

    def test_a_change_of_command_arm_or_clip_starts_a_new_clip(self):
        base = dict(look="a", phase="holding")
        rows = gd.parse_truth(lines([
            row(1.0, cmd="WAIT", arm="left", **base), row(1.1, cmd="WAIT", arm="left", **base),
            row(1.2, cmd="WAIT", arm="right", **base),                      # arm changes
            row(1.3, cmd="WAIT", arm="right", clip="c2", **base),           # animation clip changes
            row(1.4, cmd="STOP", arm="right", clip="c2", **base),           # command changes
            row(1.5, cmd="STOP", arm="right", clip="c2", **base)]), CFG)
        self.assertEqual([(c.command, c.arm, c.clip, c.n_rows) for c in gd.build_clips(rows)],
                         [("WAIT", "left", "", 2), ("WAIT", "right", "", 1), ("WAIT", "right", "c2", 1),
                          ("STOP", "right", "c2", 2)])

    def test_a_none_row_splits_two_clips_of_the_same_command(self):
        rows = gd.parse_truth(lines([row(1.0, cmd="STOP", arm="left", phase="holding"), row(1.1),
                                     row(1.2, cmd="STOP", arm="left", phase="holding")]), CFG)
        self.assertEqual(len(gd.build_clips(rows)), 2)

    def test_point_angle_mean_is_circular(self):
        rows = gd.parse_truth(lines([row(1.0, cmd="POINT", angle=170.0, arm="left", phase="holding"),
                                     row(1.1, cmd="POINT", angle=-170.0, arm="left", phase="holding")]), CFG)
        self.assertAlmostEqual(abs(gd.build_clips(rows)[0].point_angle_hold_deg), 180.0, places=2)

    def test_attach_frames_and_distance(self):
        fr = frames(100.0, 25, x=5.0, z=3.0)                            # robot 2 m from worker 1 at (5, 5)
        fr[10]["pose"] = {"x": 5.0, "z": 1.0, "yaw_deg": 0.0}           # one frame at 4 m
        j = gd.join(fr, self.rows, CFG)
        point, wait = gd.attach_frames(self.clips, j)
        self.assertEqual(point.frame_indices, [3, 4, 5, 6, 7, 8, 9])
        self.assertEqual(point.distance_m, 2.0)
        self.assertEqual(wait.frame_indices, list(range(12, 20)))
        self.assertEqual(wait.distance_m, 2.0)
        self.assertEqual(wait.label()["look"], "look_a")

    def test_clips_without_frames_have_no_distance(self):
        gd.attach_frames(self.clips, gd.join([], self.rows, CFG))
        self.assertTrue(all(c.frame_indices == [] and c.distance_m is None for c in self.clips))
        self.assertEqual(gd.clip_summary(self.clips)["without_frames"], 2)

    def test_summary_counts(self):
        s = gd.clip_summary(self.clips)
        self.assertEqual((s["clips"], s["per_command"], s["per_look"]), (2, {"POINT": 1, "WAIT": 1}, {"look_a": 2}))
        self.assertEqual(s["per_clip_name"], {"point_a": 1, "wait_a": 1})


class IsolationTests(unittest.TestCase):
    def test_only_evaluation_code_imports_gesture_data(self):
        allowed = {"hri_eval_dev_v4.py"}                    # the v4 development evaluation (evaluation code)
        offenders = []
        for p in ROOT.rglob("*.py"):
            rel = p.relative_to(ROOT)
            if ".venv" in rel.parts or rel.parts[0] == "tests" or rel.name == "gesture_data.py":
                continue
            tree = ast.parse(p.read_text(encoding="utf-8"))
            mods = set()
            for n in ast.walk(tree):
                if isinstance(n, ast.Import):
                    mods |= {a.name.split(".")[0] for a in n.names}
                elif isinstance(n, ast.ImportFrom) and n.module:
                    mods.add(n.module.split(".")[0])
                    mods |= {a.name for a in n.names}
            if "gesture_data" in mods and rel.name not in allowed:
                offenders.append(str(rel))
        self.assertEqual(offenders, [], "inference code must never import gesture_data.py (evaluation only)")

    def test_inference_modules_do_not_mention_v4_truth(self):
        for name in ("hri_control.py", "hri_perception.py", "bridge/perception.py", "bridge/guide.py", "bridge/server.py",
                     "bridge/protocol.py", "gesture_adapter.py"):
            src = (ROOT / name).read_text(encoding="utf-8")
            self.assertNotIn("gesture_data", src, name)
            self.assertNotIn("truth.jsonl", src.replace("docs/protocol_v3.md", ""), name)


# sha256 of every file hri_trials.py writes for the v3-style fixture (tests/test_trials.py fake_session), taken before
# the v4 copy step was added (2026-10-23). run.json holds the git commit and is not hashed.
V3_TRIALS_SHA256 = {
    "config_used/hri_trials_metrics.json": "522f4a12e87b31b29732bec0e37f72a215bc0a42069e3b1a4a0a650b4b073b10",
    "config_used/trials.json": "702175261ea79c3744110d1042880a0ce431c1c2ef6013b3924e0f41d649a1cc",
    "results.csv": "98c97a690a336948e47510cf31bccc6f2a5b6b9c93172536824e738c7f3918ac",
    "run_001.json": "7240c5673f0e1056bbb023e595a9f00df3c7447a0ad3f03cdb439a0945913e11",
    "run_002.json": "1949c873a2ff05cfffb2b0935c17db4456ec50e9afb1d4b84f2fb09a5bd9b024",
    "summary.json": "8b20b2b7eb0420a3f888e18ef73eaa9d46a860a0a3284d8727aa3bfcc102e181",
}


def merge_main(unity: Path, bridge: Path, out: Path) -> None:
    real = dio.new_run_dir
    dio.new_run_dir = lambda cfg, prefix: out          # keep the test out of outputs/
    try:
        with redirect_stdout(io.StringIO()):
            ht.main(["--unity", str(unity), "--bridge", str(bridge)])
    finally:
        dio.new_run_dir = real


def tree_hashes(out: Path) -> dict:
    return {p.relative_to(out).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(out.rglob("*")) if p.is_file() and p.name != "run.json"}


class TrialsCopyStepTests(unittest.TestCase):
    def test_v3_output_is_byte_identical(self):
        import test_trials as tt
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            u, b = tt.fake_session(d)
            out = d / "out"
            out.mkdir()
            merge_main(u, b, out)
            self.assertEqual(tree_hashes(out), V3_TRIALS_SHA256)

    def test_v4_run_folders_are_copied_unchanged(self):
        import test_trials as tt
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            u, b = tt.fake_session(d)
            (u / "run_001").mkdir()
            files = {"grid.json": b'{"a": 1}', "trail.csv": b"time_s,x,z,yaw_deg\n1,2,3,0\n", "truth.jsonl": b"{}\n",
                     "optimal_path.json": b"{}", "run.json": b'{"run_start_s": 1.0}'}
            for name, data in files.items():
                (u / "run_001" / name).write_bytes(data)
            (u / "leak_test").mkdir()                     # session level: copied separately
            (u / "leak_test" / "cam360_on.png").write_bytes(b"png-on")
            (u / "leak_test" / "leak_test.json").write_bytes(b'{"passed": true}')
            out = d / "out"
            out.mkdir()
            merge_main(u, b, out)
            self.assertTrue((out / "run_001").is_dir())
            self.assertFalse((out / "run_002").exists())  # run 2 has no v4 folder
            self.assertEqual({p.name: p.read_bytes() for p in (out / "run_001").iterdir()}, files)
            # everything else is exactly the v3 output
            self.assertEqual({p.name: p.read_bytes() for p in (out / "leak_test").iterdir()},
                             {"cam360_on.png": b"png-on", "leak_test.json": b'{"passed": true}'})
            rest = {k: v for k, v in tree_hashes(out).items()
                    if not k.startswith(("run_001/", "leak_test/"))}
            self.assertEqual(rest, V3_TRIALS_SHA256)

    def test_copy_function_returns_what_it_copied(self):
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            (d / "u" / "run_003").mkdir(parents=True)
            (d / "u" / "run_003" / "trail.csv").write_text("x")
            (d / "out").mkdir()
            self.assertEqual(ht.copy_v4_run_files(d / "u", d / "out", [{"trial": 3}, {"trial": 4}]), ["run_003"])

    def test_analysis_finds_the_copied_files(self):
        import hri_analysis as ha
        import test_gt_path as tg
        import test_trials as tt
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            u, b = tt.fake_session(d)
            tg.write_run(u / "run_001", [(0.25, 0.25), (0.75, 0.75), (1.25, 1.25), (1.75, 1.75)])
            out = d / "out"
            out.mkdir()
            merge_main(u, b, out)
            runs = ha.load_runs([out])
            sec = ha.path_section(runs, [out])
            self.assertEqual(sec["coverage"], "1 of 2 runs have the v4 files")


if __name__ == "__main__":
    unittest.main()
