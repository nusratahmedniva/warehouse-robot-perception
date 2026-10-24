"""v4 results archive (make_results_archive_v4.py) on synthetic session folders: layout, checksums and zip, checks (done markers,
leak test, truth files, freeze), exclusions, run folders never modified, refusal to overwrite or to write inside the repository."""

import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))

import final_guard_v4 as fg  # noqa: E402
import freeze_v4 as fz  # noqa: E402
import make_results_archive as ma  # noqa: E402
import make_results_archive_v4 as mv  # noqa: E402
import test_v4_final as tf  # noqa: E402

CFG = mv.load_config()
NOW = datetime(2026, 12, 1, 10, 0, 0)


class World:
    """A temporary repository (frozen), an outputs folder with one final session and one development session, an archive root."""

    def __init__(self, tmp: Path, frozen: bool = True, complete: bool = True):
        self.root = tmp
        self.repo = tf.final_repo(tmp / "repo", freeze=frozen)
        (self.repo / "AUDIT.md").write_text("# audit\n")
        self.out = tmp / "outputs"
        self.out.mkdir()
        self.arch = tmp / "archives"
        u, b = tf.session(self.out, "final_zoom_on")
        self.unity, self.bridge = u, b
        lt = u / "leak_test"
        lt.mkdir()
        (lt / "cam360_on.png").write_bytes(b"\x89PNG-on")
        (lt / "cam360_off.png").write_bytes(b"\x89PNG-off")
        (lt / "leak_test.json").write_text(json.dumps({"passed": True}))
        if complete:
            fg.write_done(b, "zoom_on", "run")
            (b / "FINAL_SETTING.json").write_text(json.dumps({"setting": "zoom_on", "frozen_sha256": fz.sha256_lf(self.repo / fz.FROZEN_REL)}))
            self.eval = self.out / "hri_eval_final_v4_zoom_on_20261201_090000"
            self.eval.mkdir()
            fg.write_done(self.eval, "zoom_on", "evaluation")
            (self.eval / "eval.json").write_text("{}")
        du, db = tf.session(self.out, "dev", mode="development", seed=1, spec_kw={
            "commander_look": "placeholder_look_dev_1", "clips": {"POINT": "placeholder_point_dev_1", "WAIT": "placeholder_wait_dev_1",
                                                                  "STOP": "placeholder_stop_dev_1"}})
        self.ana = self.out / "hri_analysis_v4_20261201_080000"
        self.ana.mkdir()
        (self.ana / "analysis.md").write_text("# analysis\n")
        (self.ana / "rq1_comparison.csv").write_text("measure\n")
        self.cfg = {**CFG, "manifest": str(tmp / "manifest.json")}
        sessions = [{"setting": "zoom_on", "role": "final", "unity": u.name, "bridge": b.name,
                     "eval": "hri_eval_final_v4_zoom_on_20261201_090000", "analysis": self.ana.name},
                    {"setting": "dev_run", "role": "development", "unity": du.name, "bridge": db.name}]
        (tmp / "manifest.json").write_text(json.dumps({"sessions": sessions}))

    def build(self, **kw):
        return mv.build(self.cfg, archive_root=self.arch, output_root=self.out, repo=self.repo, audit=self.repo / "AUDIT.md", now=NOW,
                        include_pip=False, **kw)


class ArchiveTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.w = World(Path(self.tmp.name))

    def tearDown(self):
        self.tmp.cleanup()

    def problems(self, res):
        return [c for c in res["checks"] if c["status"] == "problem"]

    def test_layout_checksums_zip_and_everything_ok(self):
        res = self.w.build()
        a = res["archive"]
        self.assertEqual(a.name, "results_archive_v4_20261201_100000")
        for rel in ("README.md", "CHECKSUMS.sha256", "AUDIT.md", "checks.json", "archive_config/results_manifest.json",
                    "archive_config/build_info.json", "environment/machine.json", "environment/models.csv", "environment/pip_freeze.txt",
                    "frozen/hashes.csv", "frozen/robot_vision/configs/v4/frozen.json", "frozen/robot_vision/configs/v4/control.json",
                    "frozen/robot_vision/configs/roadmap.json"):
            self.assertTrue((a / rel).exists(), rel)
        base = a / "sessions" / "zoom_on" / "final"
        for rel in ("unity/run_001/truth.jsonl", "unity/run_001/run.json", "unity/leak_test/leak_test.json", "unity/leak_test/cam360_on.png",
                    "unity/session.json", "bridge/v4_log.jsonl", "bridge/FINAL_RUN_DONE.json", "eval/FINAL_DONE.json", "analysis/analysis.md"):
            self.assertTrue((base / rel).exists(), rel)
        self.assertEqual(self.problems(res), [])
        self.assertEqual((res["copy_mismatch"], res["originals_changed"], res["freeze_problems"]), ([], [], []))
        self.assertEqual(ma.verify(a), [])
        self.assertTrue(res["zip"].exists())
        self.assertEqual(ma.sha256_file(res["zip"]), res["zip_sha256"])
        self.assertTrue(res["frozen"])

    def test_copies_equal_the_originals_and_the_originals_are_untouched(self):
        before = ma.stat_snapshot(self.w.out)
        res = self.w.build()
        self.assertEqual(ma.stat_snapshot(self.w.out), before)
        a = res["archive"] / "sessions" / "zoom_on" / "final" / "unity"
        for p in self.w.unity.rglob("*"):
            if p.is_file():
                self.assertEqual((a / p.relative_to(self.w.unity)).read_bytes(), p.read_bytes(), p.name)

    def test_models_avatars_and_mixamo_are_never_copied_but_leak_test_images_are(self):
        (self.w.unity / "weights.pt").write_bytes(b"x")
        (self.w.unity / "avatar.vrm").write_bytes(b"x")
        (self.w.unity / "Mixamo_walk.txt").write_text("x")
        res = self.w.build()
        a = res["archive"] / "sessions" / "zoom_on" / "final" / "unity"
        for name in ("weights.pt", "avatar.vrm", "Mixamo_walk.txt"):
            self.assertFalse((a / name).exists(), name)
        self.assertTrue((a / "leak_test" / "cam360_off.png").exists())
        excluded = json.loads((res["archive"] / "checks.json").read_text())["excluded"]
        self.assertEqual({e["file"] for e in excluded}, {"weights.pt", "avatar.vrm", "Mixamo_walk.txt"})

    def test_freeze_is_recorded_with_hashes_that_match(self):
        res = self.w.build()
        text = (res["archive"] / "frozen" / "hashes.csv").read_text()
        self.assertIn("robot_vision/configs/v4/control.json", text)
        self.assertNotIn("False", text)
        self.assertIn("frozen = **True**", (res["archive"] / "README.md").read_text())

    def test_a_missing_done_marker_or_leak_test_is_a_problem_for_a_final(self):
        (self.w.bridge / "FINAL_RUN_DONE.json").unlink()
        (self.w.unity / "leak_test" / "leak_test.json").write_text(json.dumps({"passed": False}))
        p = {c["check"] for c in self.problems(self.w.build())}
        self.assertIn("FINAL_RUN_DONE.json", p)
        self.assertIn("leak test passed", p)

    def test_no_leak_test_and_a_non_final_unity_mode_are_problems(self):
        import shutil
        shutil.rmtree(self.w.unity / "leak_test")
        (self.w.unity / "session.json").write_text(json.dumps({"mode": "development"}))
        p = {c["check"] for c in self.problems(self.w.build())}
        self.assertIn("leak test passed", p)
        self.assertIn("Unity session mode is final", p)

    def test_a_run_folder_without_truth_files_is_a_problem(self):
        (self.w.unity / "run_001" / "truth.jsonl").unlink()
        self.assertIn("truth.jsonl and run.json in every run folder", {c["check"] for c in self.problems(self.w.build())})

    def test_a_run_started_under_another_freeze_is_a_problem(self):
        (self.w.bridge / "FINAL_SETTING.json").write_text(json.dumps({"setting": "zoom_on", "frozen_sha256": "0" * 64}))
        self.assertIn("run started with this freeze", {c["check"] for c in self.problems(self.w.build())})

    def test_a_final_without_its_evaluation_folder_is_a_problem(self):
        m = json.loads(Path(self.w.cfg["manifest"]).read_text())
        del m["sessions"][0]["eval"]
        Path(self.w.cfg["manifest"]).write_text(json.dumps(m))
        self.assertIn("final evaluation listed", {c["check"] for c in self.problems(self.w.build())})

    def test_folders_on_another_machine_are_reported_not_invented(self):
        import shutil
        shutil.rmtree(self.w.ana)
        res = self.w.build()
        away = [c for c in res["checks"] if c["status"] == "not_on_this_machine"]
        self.assertEqual([c["folder"] for c in away], [self.w.ana.name])
        self.assertFalse((res["archive"] / "sessions" / "zoom_on" / "final" / "analysis").exists())

    def test_repo_summary_copies_only_the_analysis_tables(self):
        dest = self.w.root / "summary"
        self.w.build(repo_summary=dest)
        self.assertTrue((dest / "zoom_on" / "final" / "analysis.md").exists())
        self.assertTrue((dest / "zoom_on" / "final" / "rq1_comparison.csv").exists())
        self.assertEqual({p.name for p in dest.rglob("*") if p.is_file()}, {"analysis.md", "rq1_comparison.csv"})

    def test_never_overwrites_and_never_writes_inside_the_repository(self):
        self.w.build()
        with self.assertRaisesRegex(SystemExit, "already exists"):
            self.w.build()
        w2 = World(Path(self.tmp.name) / "two")
        w2.arch = w2.repo / "archives"
        with self.assertRaisesRegex(SystemExit, "outside the repository"):
            w2.build()

    def test_verify_finds_a_changed_added_or_missing_file(self):
        a = self.w.build(make_zip=False)["archive"]
        self.assertEqual(ma.verify(a), [])
        f = a / "sessions" / "zoom_on" / "final" / "unity" / "run_001" / "truth.jsonl"
        f.write_text(f.read_text() + " ")
        (a / "extra.txt").write_text("x")
        (a / "AUDIT.md").unlink()
        p = ma.verify(a)
        self.assertIn("changed: sessions/zoom_on/final/unity/run_001/truth.jsonl", p)
        self.assertIn("not in CHECKSUMS.sha256: extra.txt", p)
        self.assertIn("missing: AUDIT.md", p)


class UnfrozenAndManifestTests(unittest.TestCase):
    def test_a_final_session_in_an_unfrozen_repo_is_a_problem(self):
        with tempfile.TemporaryDirectory() as d:
            w = World(Path(d), frozen=False)
            res = w.build()
            self.assertIn("v4 configs frozen", {c["check"] for c in res["checks"] if c["status"] == "problem"})
            self.assertFalse(res["frozen"])
            self.assertIn("NOT frozen", (res["archive"] / "README.md").read_text())

    def test_manifest_validation(self):
        good = {"sessions": [{"setting": "zoom_on", "role": "final", "unity": "u", "bridge": "b"}]}
        self.assertEqual(mv.validate_manifest(good), [])
        self.assertTrue(mv.validate_manifest({"sessions": [{"setting": "zoom_on", "role": "gold", "unity": "u", "bridge": "b"}]}))
        self.assertTrue(mv.validate_manifest({"sessions": [{"setting": "zoom_sideways", "role": "final", "unity": "u", "bridge": "b"}]}))
        self.assertTrue(mv.validate_manifest({"sessions": [{"setting": "zoom_on", "role": "final", "unity": "u"}]}))
        dup = {"sessions": [good["sessions"][0], good["sessions"][0]]}
        self.assertIn("listed more than once", " ".join(mv.validate_manifest(dup)))

    def test_the_shipped_manifest_is_empty_and_valid_and_the_archive_config_is_outside_the_freeze(self):
        m = json.loads((ROOT / "configs/v4/archive/results_manifest.json").read_text())
        self.assertEqual((m["sessions"], mv.validate_manifest(m)), ([], []))
        self.assertTrue(all("archive" not in f for f in fz.config_files()))

    def test_main_verify(self):
        with tempfile.TemporaryDirectory() as d:
            w = World(Path(d))
            a = w.build(make_zip=False)["archive"]
            buf = io.StringIO()
            with redirect_stdout(buf), self.assertRaises(SystemExit) as cm:
                mv.main(["--verify", str(a)])
            self.assertEqual(cm.exception.code, 0)
            self.assertIn("OK", buf.getvalue())
            (a / "README.md").write_text("changed")
            with redirect_stdout(io.StringIO()), self.assertRaises(SystemExit) as cm:
                mv.main(["--verify", str(a)])
            self.assertEqual(cm.exception.code, 1)


if __name__ == "__main__":
    unittest.main()
