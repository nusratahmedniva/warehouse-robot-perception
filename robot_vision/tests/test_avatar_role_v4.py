"""AUDIT.md 16.31 / 16.31.2: the role avatar_experiment of data_splits.json. A look with that role is never used for navigation,
development or the A/B finals: data_splits_v4.guard_run refuses it in every mode (a lone third role used to be returned as the run's
split), and every caller of guard_run, which are all the callers of a split, inherits that. The avatar experiment has its own guard,
guard_avatar_experiment: the session marked, the frozen hashes matching, every name listed in any role; no development/test mixing rule."""

import copy
import json
import re
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))

import data_splits_v4 as ds  # noqa: E402
import freeze_v4 as fz  # noqa: E402
import gesture_data as gd  # noqa: E402
import hri_eval_dev_v4 as ev  # noqa: E402
import run_paths as rp  # noqa: E402
import test_v4_final as tf  # noqa: E402

AVATAR_ONLY = ("sunbox_m2", "mixamo_worker", "anime_f_01", "anime_f_02_outfit_short", "anime_f_03_bangs_parted", "cartoon_boxo_01")
NINE = {"sunbox_m1": "development", "sunbox_f1": "development", "sunbox_f2": "test", "sunbox_m_shirt_white": "development",
        "sunbox_m_tshirt_black": "development", "sunbox_f_shirt_white": "development", "sunbox_f_dress_red": "development",
        "sunbox_m_shirt_plaid": "test", "sunbox_f_shirt_plaid": "test"}
REAL = {"placeholder": False,
        "looks": {"dev_a": "development", "test_a": "test", "avatar_a": "avatar_experiment", "avatar_b": "avatar_experiment"},
        "clips": {"pd1": "development", "pt1": "test"},
        "kind_groups": {"dev_a": "stylised_human", "test_a": "stylised_human", "avatar_a": "anime", "avatar_b": "cartoon_non_human"},
        "final_evaluation_splits": ["test"]}


class ShippedConfigTests(unittest.TestCase):
    def test_the_six_looks_have_the_role_and_the_nine_keep_theirs(self):
        s = ds.load()
        self.assertEqual(ds.check_config(s), [])
        self.assertEqual({n: s["looks"][n] for n in AVATAR_ONLY}, {n: "avatar_experiment" for n in AVATAR_ONLY})
        self.assertEqual({n: s["looks"][n] for n in NINE}, NINE)
        self.assertEqual(len(s["looks"]), 15)
        self.assertEqual(set(s["clips"].values()), {"development", "test"})                 # no avatar-only clip
        self.assertEqual(s["final_evaluation_splits"], ["test"])

    def test_kind_groups_cover_the_fifteen_looks_and_the_ten_sunbox_looks_are_stylised(self):
        s = ds.load()
        self.assertEqual(set(s["kind_groups"]), set(s["looks"]))
        self.assertEqual(sorted(n for n, g in s["kind_groups"].items() if g == "stylised_human"),
                         sorted(n for n in s["looks"] if n.startswith("sunbox_")))
        self.assertEqual(len([n for n in s["looks"] if n.startswith("sunbox_")]), 10)
        self.assertEqual({n: s["kind_groups"][n] for n in AVATAR_ONLY},
                         {"sunbox_m2": "stylised_human", "mixamo_worker": "realistic_human", "anime_f_01": "anime",
                          "anime_f_02_outfit_short": "anime", "anime_f_03_bangs_parted": "anime", "cartoon_boxo_01": "cartoon_non_human"})
        self.assertEqual(set(s["styles"]), set(NINE))                                       # the per-style table of the navigation looks is unchanged

    def test_the_config_is_a_flat_table_for_unity_and_names_never_repeat(self):
        s = ds.load()
        self.assertTrue(all(isinstance(v, str) for v in s["looks"].values()))
        self.assertFalse(set(s["looks"]) & set(s["clips"]))
        raw = (ROOT / "configs/v4/data_splits.json").read_text(encoding="utf-8")
        self.assertEqual(len(re.findall(r'"looks"\s*:', raw)), 1)                             # Unity's reader takes the first "looks" object
        self.assertEqual(len(re.findall(r'"clips"\s*:', raw)), 1)
        self.assertIn("2026-11-21", s["recorded"]["avatar_experiment_looks"])


class ConfigRuleTests(unittest.TestCase):
    def test_a_clip_cannot_have_the_role(self):
        bad = copy.deepcopy(REAL)
        bad["clips"]["pa"] = "avatar_experiment"
        self.assertIn("clips 'pa' has split 'avatar_experiment'", " | ".join(ds.check_config(bad)))

    def test_an_avatar_look_needs_a_kind_group_and_a_group_needs_a_listed_look(self):
        bad = copy.deepcopy(REAL)
        del bad["kind_groups"]["avatar_a"]
        self.assertIn("avatar_a' is an avatar_experiment look and has no kind group", " | ".join(ds.check_config(bad)))
        bad = copy.deepcopy(REAL)
        bad["kind_groups"]["ghost"] = "anime"
        bad["kind_groups"]["dev_a"] = "robot"
        problems = " | ".join(ds.check_config(bad))
        self.assertIn("'ghost', which is not a listed look", problems)
        self.assertIn("group 'robot'", problems)

    def test_the_role_is_valid_for_looks(self):
        self.assertEqual(ds.check_config(REAL), [])
        self.assertEqual(ds.split_of_look("avatar_a", REAL), "avatar_experiment")


class GuardRunRefusesTheRoleTests(unittest.TestCase):
    def test_refused_in_every_mode_alone_and_mixed(self):
        for kw in ({}, {"final_evaluation": True}):
            for looks, clips in ((["avatar_a"], []), (["avatar_a"], ["pd1"]), (["avatar_a"], ["pt1"]), (["avatar_a", "avatar_b"], ["pd1"]),
                                 (["avatar_a", "dev_a"], ["pd1"]), (["avatar_a", "test_a"], ["pt1"]), (["test_a", "avatar_b"], [])):
                with self.assertRaisesRegex(SystemExit, "avatar_experiment", msg=f"{looks} {clips} {kw}"):
                    ds.guard_run(looks, clips, splits=REAL, **kw)

    def test_the_other_roles_still_work(self):
        self.assertEqual(ds.guard_run(["dev_a"], ["pd1"], False, REAL), "development")
        self.assertEqual(ds.guard_run(["test_a"], ["pt1"], True, REAL), "test")

    def test_a_hand_edited_clip_with_the_role_is_refused_too(self):
        bad = copy.deepcopy(REAL)
        bad["clips"]["pa"] = "avatar_experiment"
        with self.assertRaisesRegex(SystemExit, "clip 'pa' has the role avatar_experiment"):
            ds.guard_run(["dev_a"], ["pa"], False, bad)

    def test_every_shipped_avatar_look_is_refused_by_the_shipped_config(self):
        for look in AVATAR_ONLY:
            for final in (False, True):
                with self.assertRaisesRegex(SystemExit, "avatar_experiment"):
                    ds.guard_run([look], ["point_ik_01"], final)


class CallersTests(unittest.TestCase):
    """Every caller of a split goes through guard_run (read 2026-11-21): none reads a role itself, so none can take the new one for another."""

    def test_no_module_reads_a_role_outside_the_guard(self):
        offenders = []
        for f in sorted(ROOT.glob("*.py")) + sorted((ROOT / "bridge").glob("*.py")):
            if f.name in ("data_splits_v4.py", "data_splits.py"):
                continue
            if f.name in ("process_avatar_zip_v4.py",):          # AUDIT.md 16.33.1: the avatar runbook reads roles for the report by role, after guard_avatar_experiment
                continue
            if f.name == "export_csv_v4.py":          # AUDIT.md 16.31.6: it only LABELS rows (look_role, clip_role) of runs that guard_run has already accepted
                continue
            text = f.read_text(encoding="utf-8")
            if re.search(r"split_of_look|split_of_clip", text) or re.search(r'splits\[\s*["\']looks["\']\s*\]|splits\.get\(\s*["\']looks["\']', text):
                offenders.append(f.name)
        self.assertEqual(offenders, [], "a module reads a look's role itself; route it through data_splits_v4.guard_run")

    def test_the_session_loader_refuses_an_avatar_look_in_development_and_in_a_final(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            pair = tf.session(root, "av", n=1, spec_kw={"commander_look": "sunbox_m2"})
            gcfg = gd.load_config(fz.REPO / "robot_vision/configs/v4/gesture_data.json")
            for final in (False, True):
                with self.assertRaisesRegex(SystemExit, "avatar_experiment"):
                    ev.load_sessions([pair], gcfg, final_evaluation=final)
            rp.set_active_roots({})


class AvatarGuardTests(unittest.TestCase):
    """guard_avatar_experiment, wired to the session marker (AUDIT.md 16.31.6 decision 1; Q6 closed): run_info.json avatar_experiment_part and the
    run-once markers AVATAR_EXPERIMENT_STARTED.json / AVATAR_EXPERIMENT_DONE.json of the run folder."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.repo = tf.final_repo(self.root / "r")
        self.splits = ds.load(self.repo / "robot_vision/configs/v4/data_splits.json")

    def tearDown(self):
        self.tmp.cleanup()

    def run_folder(self, part="play", name="look_check_play_ab_20261122_090000", commit="abc123", started=True, done=True, **edit):
        """An official run folder as Unity leaves it: run_info.json and the two markers (MarkerJson: marker, part, commit, folder, written)."""
        d = self.root / name
        d.mkdir(exist_ok=True)
        info = {"avatar_experiment_part": part, "git_commit": commit, "status": "finished"}
        info.update(edit.get("run_info", {}))
        (d / "run_info.json").write_text(json.dumps(info), encoding="utf-8")
        for flag, file, kind in ((started, ds.AVATAR_STARTED, "started"), (done, ds.AVATAR_DONE, "done")):
            if flag:
                m = {"avatar_experiment_part": part, "marker": kind, "git_commit": commit, "folder": name, "written": "2026-11-22T09:00:00"}
                m.update(edit.get(kind, {}))
                (d / file).write_text(json.dumps(m), encoding="utf-8")
        return d

    def guard(self, looks, clips, folder=None, repo=None, splits=None, session=None):
        session = session if session is not None else ds.load_avatar_session(folder or self.run_folder())
        return ds.guard_avatar_experiment(looks, clips, session, splits or self.splits, repo or self.repo)

    def test_accepts_every_role_together_and_reports_the_part_the_roles_and_kinds(self):
        out = self.guard(["mixamo_worker", "sunbox_f2", "sunbox_m1", "anime_f_01"], ["point_ik_01", "point_mixamo_02", "wait_ik_02"])
        self.assertEqual((out["part"], out["commit"], out["status"]), ("play", "abc123", ""))
        self.assertEqual(out["look_roles"], {"anime_f_01": "avatar_experiment", "mixamo_worker": "avatar_experiment", "sunbox_f2": "test",
                                             "sunbox_m1": "development"})
        self.assertEqual(out["clip_roles"], {"point_ik_01": "development", "point_mixamo_02": "test", "wait_ik_02": "test"})
        self.assertEqual(out["kind_groups"], {"anime_f_01": "anime", "mixamo_worker": "realistic_human", "sunbox_f2": "stylised_human",
                                              "sunbox_m1": "stylised_human"})

    def test_both_official_parts_are_accepted_and_the_done_status_is_reported(self):
        self.assertEqual(self.guard(["anime_f_01"], [], self.run_folder("edit", "look_check_ab_20261122_080000"))["part"], "edit")
        self.assertEqual(self.guard(["anime_f_01"], [], self.run_folder("play", "look_check_play_ab_y"))["part"], "play")
        d = self.run_folder("play", "look_check_play_ab_z")
        m = json.loads((d / ds.AVATAR_DONE).read_text())
        m["status"] = "timeout"
        (d / ds.AVATAR_DONE).write_text(json.dumps(m))
        self.assertEqual(self.guard(["anime_f_01"], [], d)["status"], "timeout")                 # reported, not judged here

    def test_an_engineering_check_is_refused_as_not_official(self):
        with self.assertRaisesRegex(SystemExit, "avatar_experiment_part is empty.*engineering check, not an official"):
            self.guard(["anime_f_01"], [], self.run_folder(part=""))

    def test_other_parts_and_missing_or_unreadable_files_are_refused(self):
        with self.assertRaisesRegex(SystemExit, "'finals' in run_info.json is not one of"):
            self.guard(["anime_f_01"], [], self.run_folder(part="finals"))
        d = self.run_folder(name="look_check_play_ab_nr")
        (d / "run_info.json").unlink()
        with self.assertRaisesRegex(SystemExit, "no run_info.json"):
            self.guard(["anime_f_01"], [], d)
        with self.assertRaisesRegex(SystemExit, "no session record"):
            ds.guard_avatar_experiment(["anime_f_01"], [], None, self.splits, self.repo)
        d = self.run_folder(name="look_check_play_ab_ns", started=False)
        with self.assertRaisesRegex(SystemExit, "no AVATAR_EXPERIMENT_STARTED.json"):
            self.guard(["anime_f_01"], [], d)
        d = self.run_folder(name="look_check_play_ab_nd", done=False)                           # a crashed run has the started marker only
        with self.assertRaisesRegex(SystemExit, "no AVATAR_EXPERIMENT_DONE.json: the part did not finish"):
            self.guard(["anime_f_01"], [], d)
        d = self.run_folder(name="look_check_play_ab_bad")
        (d / ds.AVATAR_DONE).write_text("{not json")
        with self.assertRaisesRegex(SystemExit, "no AVATAR_EXPERIMENT_DONE.json"):
            self.guard(["anime_f_01"], [], d)

    def test_a_part_commit_kind_or_folder_that_disagrees_is_refused(self):
        with self.assertRaisesRegex(SystemExit, r"AVATAR_EXPERIMENT_DONE.json has avatar_experiment_part 'edit' but run_info.json has 'play'"):
            self.guard(["anime_f_01"], [], self._tamper("look_check_play_ab_p", ds.AVATAR_DONE, avatar_experiment_part="edit"))
        with self.assertRaisesRegex(SystemExit, "AVATAR_EXPERIMENT_STARTED.json has git_commit 'zzz' but run_info.json has 'abc123'"):
            self.guard(["anime_f_01"], [], self._tamper("look_check_play_ab_c", ds.AVATAR_STARTED, git_commit="zzz"))
        with self.assertRaisesRegex(SystemExit, "says marker 'started', expected 'done'"):
            self.guard(["anime_f_01"], [], self._tamper("look_check_play_ab_k", ds.AVATAR_DONE, marker="started"))
        with self.assertRaisesRegex(SystemExit, "names the folder 'elsewhere'"):
            self.guard(["anime_f_01"], [], self._tamper("look_check_play_ab_f", ds.AVATAR_STARTED, folder="elsewhere"))

    def _tamper(self, name, file, **changes):
        d = self.run_folder(name=name)
        m = json.loads((d / file).read_text())
        m.update(changes)
        (d / file).write_text(json.dumps(m))
        return d

    def test_not_frozen_or_a_changed_config_is_refused(self):
        with self.assertRaisesRegex(SystemExit, "not frozen"):
            ds.guard_avatar_experiment(["anime_f_01"], [], ds.load_avatar_session(self.run_folder()), self.splits)   # the real repository is not frozen
        f = self.repo / fz.V4_DIR / "gesture_reader.json"
        f.write_text(f.read_text() + " ")
        with self.assertRaises(SystemExit):
            self.guard(["anime_f_01"], [])

    def test_the_session_is_checked_before_the_names(self):
        with self.assertRaisesRegex(SystemExit, "not an official avatar-experiment session"):
            self.guard(["nobody"], [], self.run_folder(part=""))

    def test_every_name_must_be_listed_in_any_role(self):
        with self.assertRaisesRegex(SystemExit, "look 'nobody' is not listed"):
            self.guard(["anime_f_01", "nobody"], [])
        with self.assertRaisesRegex(SystemExit, "clip 'no_clip' is not listed"):
            self.guard(["anime_f_01"], ["no_clip"])
        with self.assertRaisesRegex(SystemExit, "clip is empty"):
            self.guard(["anime_f_01"], [""])
        with self.assertRaisesRegex(SystemExit, "no avatar look given"):
            self.guard([], ["point_ik_01"])

    def test_the_mixing_rule_of_guard_run_does_not_apply_but_guard_run_still_refuses_the_looks(self):
        self.guard(["sunbox_m1", "sunbox_f2", "sunbox_m2"], ["point_ik_01", "point_mixamo_02"])      # development + test + avatar, both clip roles
        with self.assertRaises(SystemExit):
            ds.guard_run(["sunbox_m1", "sunbox_f2"], ["point_ik_01"], False, self.splits)          # the same mix in navigation: refused
        with self.assertRaises(SystemExit):
            ds.guard_run(["sunbox_m2"], ["point_ik_01"], False, self.splits)                       # an avatar look in navigation: refused


if __name__ == "__main__":
    unittest.main()
