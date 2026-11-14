"""v4 data splits by avatar look and animation clip (data_splits_v4.py): the guard refuses any run that mixes
development and test looks or clips, unknown names, and a final evaluation on placeholder names (the shipped file has the real
names since 2026-11-08; the placeholder rule is tested on a copy with placeholder true)."""

import copy
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import data_splits as v3  # noqa: E402
import data_splits_v4 as ds  # noqa: E402

REAL = {
    "placeholder": False,
    "looks": {"dev_a": "development", "dev_b": "development", "test_a": "test"},
    "clips": {"pd1": "development", "pd2": "development", "pt1": "test", "wd1": "development", "wt1": "test"},
    "final_evaluation_splits": ["test"],
}


class ExperimentLooksTests(unittest.TestCase):
    """2026-11-14 (Anisha, AUDIT.md 16.12 item 5): Nusrat's look names of experiments A and B."""
    DEV = ("sunbox_m_shirt_white", "sunbox_m_tshirt_black", "sunbox_f_shirt_white", "sunbox_f_dress_red")
    TEST = ("sunbox_m_shirt_plaid", "sunbox_f_shirt_plaid")

    def test_split_and_style(self):
        s = ds.load()
        self.assertEqual(ds.check_config(s), [])
        for n in self.DEV:
            self.assertEqual((s["looks"][n], s["styles"][n]), ("development", "sunbox"), n)
        for n in self.TEST:
            self.assertEqual((s["looks"][n], s["styles"][n]), ("test", "sunbox"), n)
        self.assertEqual(s["looks"]["sunbox_f2"], "test")                          # the earlier test look keeps its role
        self.assertEqual(ds.load()["clips"]["proceed_ik_03"], "test")

    def test_the_guard_accepts_development_looks_and_refuses_the_plaid_ones_and_mixes(self):
        self.assertEqual(ds.guard_run(list(self.DEV), ["point_ik_01"]), "development")
        for plaid in self.TEST:
            with self.assertRaises(SystemExit):
                ds.guard_run([plaid], ["point_ik_01"])                                 # a test look in a development run
        with self.assertRaises(SystemExit):
            ds.guard_run([self.DEV[0], self.TEST[0]], ["point_ik_01"])                 # a mix of the two
        self.assertEqual(ds.guard_run(list(self.TEST), ["point_mixamo_02"], True), "test")


class ConfigTests(unittest.TestCase):
    def test_shipped_config_is_valid_and_has_the_real_names_of_2026_11_08(self):
        s = ds.load()
        self.assertFalse(s["placeholder"])
        self.assertEqual(ds.check_config(s), [])
        self.assertFalse(s["final_evaluation_done"])
        self.assertEqual({k: v for k, v in s["looks"].items() if k in ("sunbox_m1", "sunbox_f1", "sunbox_f2")},
                         {"sunbox_m1": "development", "sunbox_f1": "development", "sunbox_f2": "test"})   # the looks of 2026-11-08, unchanged
        self.assertEqual(s["clips"], {
            "point_mixamo_01": "development", "point_ik_01": "development", "point_mixamo_02": "test",
            "wait_ik_01": "development", "wait_raise_01": "development", "wait_ik_02": "test",
            "stop_ik_01": "development", "stop_ik_03": "development", "stop_ik_02": "test",
            "proceed_ik_01": "development", "proceed_ik_02": "development", "proceed_ik_03": "test"})   # PROCEED: 2026-11-12 (P2)
        self.assertFalse(any(n.startswith("placeholder_") for n in list(s["looks"]) + list(s["clips"])))
        self.assertIn("2026-11-08", s["recorded"]["looks_and_clips"])

    def test_one_style_for_the_sunbox_family(self):
        s = ds.load()
        self.assertEqual(set(s["styles"]), set(s["looks"]))
        self.assertEqual(set(s["styles"].values()), {"sunbox"})

    def test_every_gesture_has_a_development_and_a_test_clip(self):
        s = ds.load()
        for g in ("point", "wait", "stop", "proceed"):
            splits = {v for k, v in s["clips"].items() if k.startswith(g + "_")}
            self.assertEqual(splits, {"development", "test"}, g)

    def test_no_name_is_development_and_test(self):
        s = ds.load()
        self.assertFalse(set(s["looks"]) & set(s["clips"]))      # a name is a look or a clip, never both

    def test_config_problems_are_found(self):
        bad = copy.deepcopy(REAL)
        bad["looks"]["dev_a"] = "adjustment"
        del bad["clips"]["pt1"], bad["clips"]["wt1"]
        bad["final_evaluation_splits"] = ["development"]
        problems = " | ".join(ds.check_config(bad))
        self.assertIn("'dev_a' has split 'adjustment'", problems)
        self.assertIn("clips has no test entry", problems)
        self.assertIn("final_evaluation_splits", problems)
        with tempfile.TemporaryDirectory() as d:
            tmp = Path(d) / "splits.json"
            tmp.write_text('{"looks": {"a": "development"}, "clips": {"c": "development"}, "final_evaluation_splits": ["test"]}')
            with self.assertRaisesRegex(ValueError, "no test"):
                ds.load(tmp)

    def test_v3_splits_untouched(self):
        self.assertEqual(v3.load()["final_evaluation_splits"], ["final_evaluation", "cross_scene_final_evaluation"])
        self.assertNotIn("looks", v3.load())


class GuardTests(unittest.TestCase):
    def test_lookup(self):
        self.assertEqual(ds.split_of_look("dev_a", REAL), "development")
        self.assertEqual(ds.split_of_clip("pt1", REAL), "test")
        self.assertIsNone(ds.split_of_look("nobody", REAL))

    def test_development_run(self):
        self.assertEqual(ds.guard_run(["dev_a", "dev_b"], ["pd1", "wd1"], False, REAL), "development")
        self.assertEqual(ds.guard_run(["dev_a"], [], False, REAL), "development")      # a run with no gestures yet

    def test_test_run_needs_the_flag(self):
        with self.assertRaisesRegex(SystemExit, "final evaluation only"):
            ds.guard_run(["test_a"], ["pt1"], False, REAL)
        self.assertEqual(ds.guard_run(["test_a"], ["pt1", "wt1"], True, REAL), "test")

    def test_flag_refused_on_development_data(self):
        with self.assertRaisesRegex(SystemExit, "--final-evaluation given"):
            ds.guard_run(["dev_a"], ["pd1"], True, REAL)

    def test_mixed_looks_refused(self):
        with self.assertRaisesRegex(SystemExit, "mixes development and test"):
            ds.guard_run(["dev_a", "test_a"], ["pd1"], False, REAL)
        with self.assertRaisesRegex(SystemExit, "mixes development and test"):
            ds.guard_run(["dev_a", "test_a"], ["pt1"], True, REAL)             # not rescued by the flag

    def test_mixed_clips_refused(self):
        for flag in (False, True):
            with self.assertRaisesRegex(SystemExit, "mixes development and test"):
                ds.guard_run(["dev_a"], ["pd1", "pt1"], flag, REAL)

    def test_look_and_clip_from_different_splits_refused(self):
        for looks, clips in ((["dev_a"], ["pt1"]), (["test_a"], ["pd1"])):
            for flag in (False, True):
                with self.assertRaises(SystemExit) as cm:
                    ds.guard_run(looks, clips, flag, REAL)
                self.assertIn("mixes development and test", str(cm.exception))

    def test_mix_message_names_what_is_mixed(self):
        with self.assertRaises(SystemExit) as cm:
            ds.guard_run(["dev_a", "test_a"], ["pd1"], False, REAL)
        msg = str(cm.exception)
        self.assertIn("development: look dev_a, clip pd1", msg)
        self.assertIn("test: look test_a", msg)

    def test_unknown_names_refused_not_assumed_development(self):
        with self.assertRaisesRegex(SystemExit, "look 'stranger' is not listed"):
            ds.guard_run(["stranger"], ["pd1"], False, REAL)
        with self.assertRaisesRegex(SystemExit, "clip 'mystery' is not listed"):
            ds.guard_run(["dev_a"], ["mystery"], False, REAL)

    def test_missing_look_or_clip_name_refused(self):
        with self.assertRaisesRegex(SystemExit, "no avatar look"):
            ds.guard_run([], ["pd1"], False, REAL)
        with self.assertRaisesRegex(SystemExit, "no animation clip name"):
            ds.guard_run(["dev_a"], [""], False, REAL)

    def test_final_evaluation_refused_on_placeholder_names(self):
        ph = {**REAL, "placeholder": True}
        self.assertEqual(ds.guard_run(["dev_a"], ["pd1"], False, ph), "development")      # development is fine
        with self.assertRaisesRegex(SystemExit, "placeholders"):
            ds.guard_run(["test_a"], ["pt1"], True, ph)

    def test_shipped_config_end_to_end(self):
        self.assertEqual(ds.guard_run(["sunbox_m1"], ["point_ik_01"]), "development")
        self.assertEqual(ds.guard_run(["sunbox_m1", "sunbox_f1"], ["wait_ik_01", "wait_raise_01", "stop_ik_03"]), "development")
        with self.assertRaisesRegex(SystemExit, "final evaluation only"):
            ds.guard_run(["sunbox_f2"], ["point_mixamo_02"])
        with self.assertRaisesRegex(SystemExit, "mixes"):
            ds.guard_run(["sunbox_m1"], ["wait_ik_02"])
        with self.assertRaisesRegex(SystemExit, "mixes"):
            ds.guard_run(["sunbox_f2"], ["stop_ik_01"], True)
        self.assertEqual(ds.guard_run(["sunbox_f2"], ["point_mixamo_02", "wait_ik_02", "stop_ik_02"], True), "test")   # no longer placeholders
        with self.assertRaisesRegex(SystemExit, "--final-evaluation given"):
            ds.guard_run(["sunbox_f1"], ["point_ik_01"], True)

    def test_the_test_look_is_never_replaced_because_of_its_results_is_written_in_the_rules(self):
        rules = " ".join(ds.load()["rules"])
        self.assertIn("never replaced because of its results", rules)
        self.assertIn("2026-11-08", rules)

    def test_works_with_clips_built_from_a_truth_file(self):
        import gesture_data as gd
        rows = gd.parse_truth([
            '{"time_s":1.0,"worker_id":1,"look":"dev_a","x":0,"z":0,"true_command":"POINT","point_angle_deg":10,"arm":"left","phase":"holding","is_commander":true,"clip":"pd1"}',
            '{"time_s":1.0,"worker_id":2,"look":"test_a","x":3,"z":0,"true_command":"NONE","point_angle_deg":-1,"arm":"none","phase":"idle","is_commander":false}'])
        clips = gd.build_clips(rows)
        looks = {r.look for r in rows}
        with self.assertRaisesRegex(SystemExit, "mixes"):
            ds.guard_run(looks, {c.clip for c in clips}, False, REAL)       # a bystander with a test look joined the run


if __name__ == "__main__":
    unittest.main()
