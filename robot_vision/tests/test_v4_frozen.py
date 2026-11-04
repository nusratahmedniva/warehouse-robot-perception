"""The v4 freeze (freeze_v4.py, configs/v4/frozen.json): same pattern as test_hri_frozen.py. While frozen is false the
record only lists the files; once frozen, any change to a v4 config, a v3 file v4 reads, or a model file fails here."""

import hashlib
import json
import shutil
import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import freeze_v4 as fz  # noqa: E402

REPO = ROOT.parent
REC = fz.read()


def make_repo(tmp: Path, fill_plan: bool = True) -> Path:
    """A small copy of the repository: robot_vision/configs, dummy model files whose hashes the copied v3 configs expect."""
    repo = tmp / "repo"
    shutil.copytree(ROOT / "configs", repo / "robot_vision" / "configs")
    (repo / "robot_vision" / "models").mkdir()
    (repo / "external" / "media_pipe_gesture").mkdir(parents=True)
    weights, task = repo / "robot_vision" / "models" / "yolo11s-pose.pt", repo / "external" / "media_pipe_gesture" / "gesture_recognizer.task"
    weights.write_bytes(b"weights")
    task.write_bytes(b"task")
    perc = repo / "robot_vision" / "configs" / "hri_perception.json"
    d = json.loads(perc.read_text())
    d["pose_model"]["sha256"] = hashlib.sha256(b"weights").hexdigest()
    perc.write_text(json.dumps(d))
    gest = repo / "robot_vision" / "configs" / "gesture_hri.json"
    d = json.loads(gest.read_text())
    d["model"]["sha256"] = hashlib.sha256(b"task").hexdigest()
    gest.write_text(json.dumps(d))
    if fill_plan:
        plan = repo / fz.PLAN_REL
        d = json.loads(plan.read_text())
        d.update(task="Task2", dev_seed=1, final_seed=7, runs_per_setting=10, timeout_s=240, success_radius_m=0.3,
                 test_assignment="x", unity_files_and_guard="x", acceptance_criteria="x")
        plan.write_text(json.dumps(d))
        sp = repo / fz.SPLITS_REL
        d = json.loads(sp.read_text())
        d["placeholder"] = False
        sp.write_text(json.dumps(d))
    return repo


class RecordedFreezeTests(unittest.TestCase):
    """The real record in the repository."""

    def test_structure(self):
        for k in ("frozen", "frozen_at", "git_commit", "files", "sha256", "v3_dependencies", "models"):
            self.assertIn(k, REC)
        self.assertIsInstance(REC["frozen"], bool)

    def test_every_v4_config_is_listed_and_nothing_else(self):
        self.assertEqual(REC["files"], fz.config_files())
        self.assertNotIn(fz.FROZEN_REL, REC["files"])
        for must in ("bridge.json", "control.json", "commander.json", "gesture_reader.json", "data_splits.json", "eval_dev.json",
                     "gesture_data.json", "gt_eval.json", "final_plan.json", "analysis.json"):
            self.assertIn(f"{fz.V4_DIR}/{must}", REC["files"], must)

    def test_unfrozen_holds_no_hashes(self):
        if REC["frozen"]:
            self.skipTest("frozen: see the next test")
        self.assertEqual((REC["sha256"], REC["v3_dependencies"], REC["models"], REC["frozen_at"]), ({}, {}, {}, None))

    def test_if_frozen_every_hash_matches(self):
        if not REC["frozen"]:
            self.skipTest("configs/v4/frozen.json is not frozen yet")
        self.assertEqual(fz.problems(REPO), [], "a v4 file changed after freezing (disclose in AUDIT.md and re-freeze)")
        self.assertEqual(set(REC["sha256"]), set(REC["files"]))
        self.assertEqual(set(REC["v3_dependencies"]), set(fz.V3_DEPENDENCIES))
        self.assertEqual(fz.blanks(REPO), [])

    def test_v3_dependencies_exist_and_the_v3_freeze_still_covers_them(self):
        v3 = json.loads((ROOT / "configs" / "hri_frozen.json").read_text())
        covered = {k for grp in ("sha256", "sha256_added_2026_10_21") for k in v3[grp]}
        for f in fz.V3_DEPENDENCIES:
            self.assertTrue((REPO / f).exists(), f)
            self.assertIn(f, covered, f"{f} is read by v4 and must be in the frozen v3 set")

    def test_the_blanks_are_listed_while_the_plan_has_any(self):
        plan = json.loads((REPO / fz.PLAN_REL).read_text())
        want = [f"final_plan.json: {k}" for k in fz.PLAN_BLANK_KEYS if plan.get(k) is None]
        if json.loads((REPO / fz.SPLITS_REL).read_text()).get("placeholder"):
            want.append("data_splits.json: look and clip names are still placeholders")
        self.assertEqual(fz.blanks(REPO), want)

    def test_decided_values_of_the_plan_and_the_blanks_still_open(self):
        """Decided 2026-10-24 by Anisha; B7, B9, B11 and the real names (B8) are open and must keep the freeze refused."""
        plan = json.loads((REPO / fz.PLAN_REL).read_text())
        v3 = json.loads((ROOT / "configs/trials.json").read_text())
        self.assertEqual((plan["task"], plan["dev_seed"], plan["final_seed"], plan["runs_per_setting"], plan["success_radius_m"]),
                         ("Task2", 1, 2, 20, 0.3))
        self.assertEqual((plan["timeout_s"], plan["success_radius_m"], plan["dev_seed"], plan["final_seed"]),
                         (v3["timeout_s"], v3["success_radius_m"], v3["dev_seed"], v3["final_seed"]))     # the v3 values, read from the v3 config
        self.assertIn("RTX 3060", plan["machine"])
        self.assertIn("highest development accuracy", plan["threshold_rule"])
        self.assertIn("coverage >= 0.8", plan["threshold_rule"])
        if not REC["frozen"]:
            for k in ("test_assignment", "unity_files_and_guard", "acceptance_criteria"):
                self.assertIsNone(plan[k], k)
            self.assertEqual(len(fz.blanks(REPO)), 4)                                              # B7, B9, B11 and the placeholder names

    def test_the_goal_order_of_the_final_seed_is_that_of_the_v3_final(self):
        import hri_trials as ht
        plan = json.loads((REPO / fz.PLAN_REL).read_text())
        self.assertEqual(ht.goal_order(plan["final_seed"], ["E1", "E2", "E3", "E4"], 10),
                         ["E1", "E2", "E4", "E2", "E1", "E3", "E4", "E1", "E4", "E1"])               # AUDIT.md section 2

    def test_v4_re_ask_shift_is_a_declared_difference_and_v3_is_unchanged(self):
        import hri_control as hc
        import hri_control_v4 as hv
        base, v4 = hv.load_control()
        self.assertEqual(v4["dialog"]["reask_shift_m"], 0.8)
        self.assertEqual(base["dialog"]["reask_shift_m"], 0.8)                                       # applied to the v4 controller
        self.assertEqual(hc.load_json("configs/hri_control.json")["dialog"]["reask_shift_m"], 0.4)  # v3 file untouched
        self.assertIn("0.8", " ".join(json.loads((ROOT / "configs/v4/analysis.json").read_text())["declared_differences"]))

    def test_settings_of_the_plan_are_the_four_final_settings(self):
        plan = json.loads((REPO / fz.PLAN_REL).read_text())
        self.assertEqual(set(plan["settings"]), {"zoom_on", "zoom_off", "bystanders", "unseen_look"})

    def test_models_are_located_from_the_frozen_v3_configs(self):
        st = fz.model_status(REPO)
        self.assertEqual(set(st), {"pose_weights", "mediapipe_model"})
        self.assertEqual(st["pose_weights"]["expected_sha256"], json.loads((ROOT / "configs/hri_perception.json").read_text())["pose_model"]["sha256"])
        for s in st.values():
            if s["present"]:
                self.assertEqual(s["sha256"], s["expected_sha256"])


class FreezeMechanicsTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.repo = make_repo(Path(self.tmp.name))
        fz.refresh_list(self.repo)

    def tearDown(self):
        self.tmp.cleanup()

    def test_freeze_writes_hashes_and_then_everything_matches(self):
        rec = fz.freeze(self.repo, datetime(2026, 11, 1, 12, 0), "abc123")
        self.assertTrue(rec["frozen"])
        self.assertEqual((rec["frozen_at"], rec["git_commit"]), ("2026-11-01T12:00:00", "abc123"))
        self.assertEqual(set(rec["sha256"]), set(fz.config_files(self.repo)))
        self.assertEqual(set(rec["v3_dependencies"]), set(fz.V3_DEPENDENCIES))
        self.assertEqual(set(rec["models"]), {"pose_weights", "mediapipe_model"})
        self.assertEqual(fz.problems(self.repo, require_models=True), [])
        self.assertEqual(fz.require_frozen(self.repo)["git_commit"], "abc123")

    def test_a_changed_v4_config_is_found(self):
        fz.freeze(self.repo)
        f = self.repo / fz.V4_DIR / "control.json"
        f.write_text(f.read_text() + " ")
        self.assertEqual(fz.problems(self.repo), [f"{fz.V4_DIR}/control.json changed after freezing"])
        with self.assertRaisesRegex(SystemExit, "freeze is broken"):
            fz.require_frozen(self.repo)

    def test_a_changed_v3_file_v4_reads_is_found(self):
        fz.freeze(self.repo)
        f = self.repo / "robot_vision" / "configs" / "roadmap.json"
        f.write_text(f.read_text() + " ")
        self.assertIn("roadmap.json changed after freezing", " ".join(fz.problems(self.repo)))

    def test_a_new_or_removed_config_is_found(self):
        fz.freeze(self.repo)
        (self.repo / fz.V4_DIR / "extra.json").write_text("{}")
        self.assertTrue(any("file list is out of date" in p for p in fz.problems(self.repo)))
        (self.repo / fz.V4_DIR / "extra.json").unlink()
        (self.repo / fz.V4_DIR / "gt_eval.json").unlink()
        self.assertTrue(fz.problems(self.repo))

    def test_a_changed_model_file_is_found_and_a_missing_one_only_when_required(self):
        fz.freeze(self.repo)
        w = self.repo / "robot_vision" / "models" / "yolo11s-pose.pt"
        w.write_bytes(b"other weights")
        self.assertIn("pose_weights does not match the frozen hash", fz.problems(self.repo))
        w.unlink()
        self.assertEqual(fz.problems(self.repo), [])                              # absent: git-ignored, checked where present
        self.assertIn("pose_weights not found", " ".join(fz.problems(self.repo, require_models=True)))
        with self.assertRaisesRegex(SystemExit, "not found"):
            fz.require_frozen(self.repo)

    def test_line_endings_do_not_matter(self):
        fz.freeze(self.repo)
        f = self.repo / fz.V4_DIR / "commander.json"
        # From LF first: a Windows checkout (core.autocrlf) is already CRLF, and "\n" -> "\r\n" would make "\r\r\n".
        f.write_bytes(f.read_bytes().replace(b"\r\n", b"\n").replace(b"\n", b"\r\n"))
        self.assertEqual(fz.problems(self.repo), [])

    def test_freeze_is_refused_while_a_blank_is_left(self):
        repo = make_repo(Path(self.tmp.name) / "b", fill_plan=False)
        fz.refresh_list(repo)
        with self.assertRaisesRegex(SystemExit, "blanks left"):
            fz.freeze(repo)
        self.assertFalse(fz.read(repo)["frozen"])

    def test_freeze_is_refused_without_the_model_files_or_with_the_wrong_ones(self):
        (self.repo / "robot_vision" / "models" / "yolo11s-pose.pt").unlink()
        with self.assertRaisesRegex(SystemExit, "model file"):
            fz.freeze(self.repo)
        (self.repo / "robot_vision" / "models" / "yolo11s-pose.pt").write_bytes(b"not the frozen weights")
        with self.assertRaisesRegex(SystemExit, "do not match"):
            fz.freeze(self.repo)

    def test_never_overwritten_and_the_list_is_not_rewritten_once_frozen(self):
        fz.freeze(self.repo)
        with self.assertRaisesRegex(SystemExit, "already frozen"):
            fz.freeze(self.repo)
        with self.assertRaisesRegex(SystemExit, "not rewritten"):
            fz.refresh_list(self.repo)

    def test_unfrozen_is_refused_by_require_frozen(self):
        with self.assertRaisesRegex(SystemExit, "not frozen"):
            fz.require_frozen(self.repo)

    def test_the_freeze_record_itself_is_not_hashed(self):
        fz.freeze(self.repo)
        self.assertNotIn(fz.FROZEN_REL, fz.read(self.repo)["sha256"])


class ScriptTests(unittest.TestCase):
    def test_report_runs_without_freezing(self):
        import io
        from contextlib import redirect_stdout
        before = (REPO / fz.FROZEN_REL).read_bytes()
        buf = io.StringIO()
        with redirect_stdout(buf):
            try:
                fz.main([])
            except SystemExit:
                pass
        self.assertIn("frozen:", buf.getvalue())
        self.assertEqual((REPO / fz.FROZEN_REL).read_bytes(), before)               # reporting never writes


if __name__ == "__main__":
    unittest.main()
