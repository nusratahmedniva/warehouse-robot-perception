"""v4 data splits by avatar look and animation clip (data_splits_v4.py): the guard refuses any run that mixes
development and test looks or clips, unknown names, and a final evaluation on placeholder names."""

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


class ConfigTests(unittest.TestCase):
    def test_shipped_config_is_valid_and_placeholder(self):
        s = ds.load()
        self.assertTrue(s["placeholder"])
        self.assertEqual(ds.check_config(s), [])
        self.assertFalse(s["final_evaluation_done"])
        names = list(s["looks"]) + list(s["clips"])
        self.assertTrue(all(n.startswith("placeholder_") for n in names))

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

    def test_shipped_placeholder_config_end_to_end(self):
        self.assertEqual(ds.guard_run(["placeholder_look_dev_1"], ["placeholder_point_dev_2"]), "development")
        with self.assertRaisesRegex(SystemExit, "final evaluation only"):
            ds.guard_run(["placeholder_look_test_1"], ["placeholder_point_test_1"])
        with self.assertRaisesRegex(SystemExit, "mixes"):
            ds.guard_run(["placeholder_look_dev_1"], ["placeholder_wait_test_1"])
        with self.assertRaisesRegex(SystemExit, "placeholders"):
            ds.guard_run(["placeholder_look_test_1"], ["placeholder_point_test_1"], True)

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
