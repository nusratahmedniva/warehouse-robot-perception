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
        if REC["frozen"]:
            self.assertEqual(REC["files"], fz.config_files())
        else:       # unfrozen the list is documentation, rewritten by --refresh-list; it may lag behind but never name a file that is not frozen
            self.assertTrue(set(REC["files"]) <= set(fz.config_files()))
        self.assertNotIn(fz.FROZEN_REL, REC["files"])
        for must in ("bridge.json", "control.json", "commander.json", "gesture_reader.json", "data_splits.json", "eval_dev.json",
                     "gesture_data.json", "gt_eval.json", "final_plan.json", "analysis.json"):
            self.assertIn(f"{fz.V4_DIR}/{must}", REC["files"], must)

    def test_the_experiments_file_is_frozen_and_the_csv_columns_are_not(self):
        files = fz.config_files()
        self.assertIn(f"{fz.V4_DIR}/experiments/scenarios_ab.json", files)
        self.assertNotIn(f"{fz.V4_DIR}/experiments/export_csv.json", files)
        self.assertEqual([f for f in files if "/experiments/" in f], list(fz.FROZEN_EXTRA))


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
        """Decided 2026-10-24 by Anisha; B7, B9 and B11 filled 2026-11-13 by Nusrat in her absence; B7 and B11 confirmed by Anisha on
        2026-11-13, B11 updated the same day (AUDIT.md section 15)."""
        plan = json.loads((REPO / fz.PLAN_REL).read_text())
        v3 = json.loads((ROOT / "configs/trials.json").read_text())
        self.assertEqual((plan["task"], plan["dev_seed"], plan["final_seed"], plan["runs_per_setting"], plan["success_radius_m"]),
                         ("Task2", 1, 2, 20, 0.3))
        self.assertEqual((plan["success_radius_m"], plan["dev_seed"], plan["final_seed"]),
                         (v3["success_radius_m"], v3["dev_seed"], v3["final_seed"]))     # the v3 values, read from the v3 config
        # 2026-11-12 (P7): the timeout follows the declared rule for the longer v4 route (upgrade_design.md section 6), not v3's 240 s
        self.assertEqual(plan["timeout_s"], max(240, 10 * -(-(1.5 * 65.0 / 0.3944 + 20) // 10)))
        self.assertGreaterEqual(plan["timeout_s"], v3["timeout_s"])
        self.assertIn("RTX 3060", plan["machine"])
        self.assertIn("highest development accuracy", plan["threshold_rule"])
        self.assertIn("coverage >= 0.8", plan["threshold_rule"])
        # 2026-11-13: B7 (plan (b): sunbox_f2 + test clips in every setting, zoom_on_repeat a repeat of zoom_on), B9 and B11 filled
        for k in ("test_assignment", "unity_files_and_guard", "acceptance_criteria"):
            self.assertIsNotNone(plan[k], k)
        self.assertEqual(plan["test_assignment"]["zoom_on_repeat"]["repeat_of"], "zoom_on")
        for s, a in plan["test_assignment"].items():
            self.assertEqual(a["looks"], ["sunbox_f2"], s)
        self.assertEqual(len(plan["acceptance_criteria"]), 7)
        self.assertEqual(fz.blanks(REPO), [])

    def test_b11_is_validity_only_and_a_watchdog_stop_is_a_result(self):
        """B11 update of 2026-11-13 (AUDIT.md section 15): no watchdog criterion; frozen hashes, split guard and all runs added;
        a setting that fails is reported as invalid and never rerun. check_session_v4.ps1 checks exactly these criteria."""
        plan = json.loads((REPO / fz.PLAN_REL).read_text())
        crit = plan["acceptance_criteria"]
        self.assertFalse([c for c in crit if "watchdog" in c.lower()], "a watchdog stop is a result, never an invalidity reason")
        labels = ("leak test passed", "frozen hashes match", "split guard passed", "all runs present", "every outcome recorded",
                  "every truth and run file accepted", "run protocol recorded")
        self.assertEqual(len(crit), len(labels))
        for c, label in zip(crit, labels):
            self.assertTrue(c.startswith(label), label)
        note = plan["acceptance_criteria_note"]
        for want in ("watchdog stop is a RESULT", "never a reason for invalidity", "reported as invalid", "never rerun"):
            self.assertIn(want, note)
        script = (REPO / "finals_v4" / "check_session_v4.ps1").read_text(encoding="utf-8")
        import re
        numbers = [int(n) for n in re.findall(r"^\s*Report (\d+) ", script, re.M)]
        self.assertEqual(numbers, list(range(1, len(crit) + 1)), "one Report line per criterion, in the plan's order")
        for n, label in enumerate(labels, 1):
            self.assertRegex(script, rf"(?m)^\s*Report {n} .*\"{re.escape(label)}", f"criterion {n} is '{label}' in the script")
        self.assertNotRegex(script, r"(?m)^\s*Report \d+ .*watchdog")
        self.assertIn("never rerun", script)

    def test_the_goal_order_of_the_final_seed_is_that_of_the_v3_final(self):
        import hri_trials as ht
        plan = json.loads((REPO / fz.PLAN_REL).read_text())
        self.assertEqual(ht.goal_order(plan["final_seed"], ["E1", "E2", "E3", "E4"], 10),
                         ["E1", "E2", "E4", "E2", "E1", "E3", "E4", "E1", "E4", "E1"])               # AUDIT.md section 2 (v3 map)
        # 2026-11-12 (P7): the v4 map has six endpoints; the final goal order on it (a declared difference for RQ1)
        road = json.loads((ROOT / plan["roadmap"]).read_text(encoding="utf-8"))
        ends = sorted(k for k, v in road["nodes"].items() if v["kind"] == "endpoint")
        self.assertEqual(ht.goal_order(plan["final_seed"], ends, plan["runs_per_setting"]),
                         ["E5", "E1", "E5", "E2", "E5", "E3", "E5", "E3", "E4", "E3", "E5", "E3", "E5", "E6", "E2", "E5", "E3", "E1", "E4", "E2"])

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
        self.assertEqual(set(plan["settings"]), {"zoom_on", "zoom_off", "bystanders", "zoom_on_repeat"})   # unseen_look renamed 2026-11-13

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

    def test_a_changed_experiments_file_is_found_but_the_csv_columns_may_change(self):
        fz.freeze(self.repo)
        csv_cfg = self.repo / fz.V4_DIR / "experiments" / "export_csv.json"
        csv_cfg.write_text(csv_cfg.read_text() + " ")
        self.assertEqual(fz.problems(self.repo), [])
        f = self.repo / fz.V4_DIR / "experiments" / "scenarios_ab.json"
        f.write_text(f.read_text() + " ")
        self.assertEqual(fz.problems(self.repo), [f"{fz.V4_DIR}/experiments/scenarios_ab.json changed after freezing"])

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
        plan = repo / fz.PLAN_REL                                    # the real plan has no blank since 2026-11-13: make one
        d = json.loads(plan.read_text())
        d["acceptance_criteria"] = None
        plan.write_text(json.dumps(d))
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


class UnityFilesFreezeTests(unittest.TestCase):
    """2026-11-13 (Nusrat in Anisha's absence, AUDIT.md section 15): the freeze also records the Unity files of the B9 list, keyed by
    their repository path, which is what the Unity final guard (FinalGuardV4) looks up."""

    LIST = "unity/P/Assets/WarehouseRobot/Avatar/Config/final_v4.json"
    FILES = ["unity/P/Assets/Scenes/WarehouseRobot_v4.unity", "unity/P/Assets/WarehouseRobot/Bridge/Config/bridge_unity_v4.json", LIST]

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.repo = make_repo(Path(self.tmp.name))
        plan = self.repo / fz.PLAN_REL
        d = json.loads(plan.read_text())
        d["unity_files_and_guard"] = {"freeze_list": self.LIST, "freeze_list_key": "freeze_files", "guard": "FinalGuardV4"}
        plan.write_text(json.dumps(d))
        for f in self.FILES[:-1]:
            (self.repo / f).parent.mkdir(parents=True, exist_ok=True)
            (self.repo / f).write_text(f"content of {f}\n")
        (self.repo / self.LIST).parent.mkdir(parents=True, exist_ok=True)
        (self.repo / self.LIST).write_text(json.dumps({"freeze_files": self.FILES}))
        fz.refresh_list(self.repo)

    def tearDown(self):
        self.tmp.cleanup()

    def test_the_list_comes_from_the_plan_and_the_unity_config(self):
        self.assertEqual(fz.unity_files(self.repo), sorted(self.FILES))

    def test_freeze_records_every_unity_file_by_path_with_the_lf_hash(self):
        rec = fz.freeze(self.repo)
        self.assertEqual(set(rec["unity_files"]), set(self.FILES))
        for f in self.FILES:
            self.assertEqual(rec["unity_files"][f], hashlib.sha256((self.repo / f).read_bytes().replace(b"\r\n", b"\n")).hexdigest())
        # the form the Unity guard reads: "<path>": "<64 hex>" in frozen.json
        text = (self.repo / fz.FROZEN_REL).read_text()
        for f in self.FILES:
            self.assertIn(f'"{f}": "{rec["unity_files"][f]}"', text)
        self.assertEqual(fz.problems(self.repo), [])

    def test_a_changed_or_removed_unity_file_breaks_the_freeze(self):
        fz.freeze(self.repo)
        scene = self.repo / self.FILES[0]
        scene.write_text(scene.read_text() + "moved a light\n")
        self.assertEqual(fz.problems(self.repo), [f"{self.FILES[0]} changed after freezing"])
        with self.assertRaisesRegex(SystemExit, "freeze is broken"):
            fz.require_frozen(self.repo, require_models=False)
        scene.unlink()
        self.assertIn(f"{self.FILES[0]} added or removed since freezing", fz.problems(self.repo))

    def test_line_endings_of_unity_files_do_not_matter(self):
        fz.freeze(self.repo)
        f = self.repo / self.FILES[1]
        f.write_bytes(f.read_bytes().replace(b"\r\n", b"\n").replace(b"\n", b"\r\n"))
        self.assertEqual(fz.problems(self.repo), [])

    def test_freeze_is_refused_while_a_listed_unity_file_is_missing(self):
        (self.repo / self.FILES[0]).unlink()
        with self.assertRaisesRegex(SystemExit, "Unity file"):
            fz.freeze(self.repo)
        self.assertFalse(fz.read(self.repo)["frozen"])

    def test_the_real_plan_names_the_unity_b9_list_and_every_file_exists(self):
        files = fz.unity_files(REPO)
        unity = json.loads((REPO / json.loads((REPO / fz.PLAN_REL).read_text())["unity_files_and_guard"]["freeze_list"]).read_text())
        self.assertEqual(files, sorted(unity["freeze_files"]))
        self.assertIn("unity/Robotics-Warehouse/WarehouseProjectURP/Assets/Scenes/WarehouseRobot_v4.unity", files)
        for f in files:
            self.assertTrue((REPO / f).is_file(), f)


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
