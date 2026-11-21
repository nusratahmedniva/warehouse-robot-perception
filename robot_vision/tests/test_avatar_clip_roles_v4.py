"""AUDIT.md 16.31.5 item 4 (Q5 closed): the clip of each take comes from recordings.jsonl. Edit takes (clip "", pose "posed") and NONE takes are
excluded from the clip-role split, a gesture take without a clip is not evaluated, an unlisted clip is refused, the split is per distance, and
the interval is the take bootstrap of configs/v4/analysis.json. Synthetic recordings.jsonl only."""

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import avatar_clip_roles_v4 as ac  # noqa: E402
import data_splits_v4 as ds  # noqa: E402

SPLITS = ds.load()                                         # the shipped roles: point_ik_01 development, point_mixamo_02 test, ...


def row(name, look="anime_f_01", command="POINT", distance=2.0, arm="left", take=1, clip="point_ik_01", **extra):
    return {"name": name, "kind": "sequence", "look": look, "command": command, "distance_m": distance, "arm": arm, "take": take, "clip": clip, **extra}


ROWS = [
    row("a__POINT__2.0__left_seq1", clip="point_ik_01"),
    row("a__POINT__2.0__left_seq2", clip="point_mixamo_02", take=2),
    row("a__WAIT__2.0__left_f1", command="WAIT", clip="wait_ik_01"),
    row("a__STOP__2.0__left_f1", command="STOP", clip="stop_ik_02"),
    row("b__POINT__2.0__left_seq1", look="mixamo_worker", clip="point_ik_01"),
    row("b__POINT__2.0__left_seq2", look="mixamo_worker", clip="point_mixamo_02", take=2),
    row("a__NONE__2.0__s1", command="NONE", arm="", clip=""),
    row("a__POINT__2.0__left_nc", clip="", take=9),                                    # a gesture take with no clip
    row("e__POINT__2.0__left_seq1", clip="", pose="posed"),                            # an Edit take
    row("a__POINT__4.0__left_seq1", distance=4.0, clip="point_ik_01"),                  # the same take at the 4 m camera
]


class LoadTests(unittest.TestCase):
    def test_a_recordings_file_is_read_line_by_line(self):
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / "recordings.jsonl"
            f.write_text("".join(json.dumps(r) + "\n" for r in ROWS) + "\n", encoding="utf-8")
            self.assertEqual(ac.load_recordings(f), ROWS)
            f.write_text('{"name": "x"}\n{not json\n', encoding="utf-8")
            with self.assertRaisesRegex(SystemExit, "line 2 is not JSON"):
                ac.load_recordings(f)

    def test_the_bootstrap_settings_are_those_of_analysis_json(self):
        self.assertEqual(ac.bootstrap_settings(), {"n_resamples": 2000, "seed": 1, "percentiles": [2.5, 97.5]})


class ClassifyTests(unittest.TestCase):
    def test_every_kind_of_take(self):
        c = ac.classify(ROWS, SPLITS)
        self.assertEqual((c["a__POINT__2.0__left_seq1"]["status"], c["a__POINT__2.0__left_seq1"]["clip_role"]), ("clip", "development"))
        self.assertEqual((c["a__POINT__2.0__left_seq2"]["status"], c["a__POINT__2.0__left_seq2"]["clip_role"]), ("clip", "test"))
        self.assertEqual(c["a__STOP__2.0__left_f1"]["clip_role"], "test")
        self.assertEqual(c["e__POINT__2.0__left_seq1"]["status"], "posed")
        self.assertIsNone(c["e__POINT__2.0__left_seq1"]["clip_role"])                      # a posed take is never given a role
        self.assertEqual(c["a__NONE__2.0__s1"]["status"], "no_gesture_clip")
        self.assertEqual(c["a__POINT__2.0__left_nc"]["status"], "missing_clip")             # not guessed

    def test_an_edit_row_without_the_pose_key_is_not_evaluated_not_guessed(self):
        c = ac.classify([row("e1", clip="")], SPLITS)                                      # the Edit writer before it writes pose "posed"
        self.assertEqual(c["e1"]["status"], "missing_clip")

    def test_refusals(self):
        with self.assertRaisesRegex(SystemExit, "not listed in the v4 data splits"):
            ac.classify([row("x", clip="point_unlisted_09")], SPLITS)
        with self.assertRaisesRegex(SystemExit, "two recordings are named 'x'"):
            ac.classify([row("x"), row("x")], SPLITS)
        with self.assertRaisesRegex(SystemExit, "has no name"):
            ac.classify([{"look": "a", "clip": "point_ik_01"}], SPLITS)
        with self.assertRaisesRegex(SystemExit, "posed but names the clip"):
            ac.classify([row("x", pose="posed", clip="point_ik_01")], SPLITS)

    def test_a_clip_of_a_none_take_is_not_read_for_a_role(self):
        self.assertEqual(ac.classify([row("n", command="NONE", clip="")], SPLITS)["n"]["status"], "no_gesture_clip")


class SplitTests(unittest.TestCase):
    FAST = {"n_resamples": 200, "seed": 1, "percentiles": [2.5, 97.5]}

    def values(self, **over):
        v = {"a__POINT__2.0__left_seq1": 1.0, "a__POINT__2.0__left_seq2": 0.5, "a__WAIT__2.0__left_f1": 0.0, "a__STOP__2.0__left_f1": 1.0,
             "b__POINT__2.0__left_seq1": 0.0, "b__POINT__2.0__left_seq2": 1.0, "a__NONE__2.0__s1": 1.0, "a__POINT__2.0__left_nc": 1.0,
             "e__POINT__2.0__left_seq1": 1.0}
        v.update(over)
        return v

    def test_the_split_counts_means_and_exclusions_at_one_distance(self):
        out = ac.split_by_clip_role(self.values(), ROWS, 2.0, SPLITS, self.FAST)
        dev, test = out["roles"]["development"], out["roles"]["test"]
        self.assertEqual((dev["takes"], dev["mean"]), (3, (1.0 + 0.0 + 0.0) / 3))             # point_ik_01 (a, b) and wait_ik_01
        self.assertEqual((test["takes"], test["mean"]), (3, (0.5 + 1.0 + 1.0) / 3))           # point_mixamo_02 (a, b) and stop_ik_02
        self.assertEqual(out["excluded"]["posed"], {"takes": 1, "names": ["e__POINT__2.0__left_seq1"]})
        self.assertEqual(out["excluded"]["no_gesture_clip"]["takes"], 1)
        self.assertEqual(out["not_evaluated"]["missing_clip"], {"takes": 1, "names": ["a__POINT__2.0__left_nc"]})
        self.assertEqual(out["takes_by_look"]["development"], {"anime_f_01": 2, "mixamo_worker": 1})
        self.assertEqual(out["distance_m"], 2.0)
        for r in (dev, test):
            lo, hi = r["interval"]
            self.assertTrue(0.0 <= lo <= r["mean"] <= hi <= 1.0, r)

    def test_a_value_for_another_distance_is_refused_never_pooled(self):
        with self.assertRaisesRegex(SystemExit, "recorded at 4.0 m, not 2.0 m"):
            ac.split_by_clip_role(self.values(**{"a__POINT__4.0__left_seq1": 1.0}), ROWS, 2.0, SPLITS, self.FAST)
        out = ac.split_by_clip_role({"a__POINT__4.0__left_seq1": 1.0}, ROWS, 4.0, SPLITS, self.FAST)       # asked at its own distance
        self.assertEqual(out["roles"]["development"]["takes"], 1)

    def test_a_value_without_a_recording_is_listed_not_guessed(self):
        out = ac.split_by_clip_role({"unknown_take": 0.5}, ROWS, 2.0, SPLITS, self.FAST)
        self.assertEqual(out["not_evaluated"]["no_recording"], {"takes": 1, "names": ["unknown_take"]})
        self.assertEqual(out["roles"]["development"], {"takes": 0, "mean": None, "interval": None})

    def test_values_must_be_shares(self):
        for bad in (-0.1, 1.5, True, "1", None):
            with self.assertRaisesRegex(SystemExit, "not a share"):
                ac.split_by_clip_role({"a__POINT__2.0__left_seq1": bad}, ROWS, 2.0, SPLITS, self.FAST)

    def test_the_bootstrap_is_reproducible_stratified_and_uses_the_config_numbers(self):
        a = ac.mean_with_bootstrap({"x": [0.0, 1.0, 1.0], "y": [0.0, 0.0]})
        b = ac.mean_with_bootstrap({"y": [0.0, 0.0], "x": [0.0, 1.0, 1.0]})                   # the order of the looks does not matter
        self.assertEqual(a, b)
        self.assertEqual((a["takes"], a["mean"]), (5, 2 / 5))
        # all takes equal: the interval is that value
        self.assertEqual(ac.mean_with_bootstrap({"x": [0.25, 0.25]})["interval"], [0.25, 0.25])
        # a look whose takes are all 0 stays 0 in every resample, so the upper end cannot reach 1 (stratified by look)
        self.assertLess(ac.mean_with_bootstrap({"x": [1.0, 1.0], "y": [0.0, 0.0]})["interval"][1], 1.0 + 1e-12)
        self.assertEqual(ac.mean_with_bootstrap({"x": [1.0, 1.0], "y": [0.0, 0.0]})["interval"], [0.5, 0.5])   # each look's mean is fixed
        self.assertEqual(ac.mean_with_bootstrap({}), {"takes": 0, "mean": None, "interval": None})

    def test_the_shipped_roles_are_used(self):
        self.assertEqual(SPLITS["clips"]["point_ik_01"], "development")
        self.assertEqual(SPLITS["clips"]["point_mixamo_02"], "test")


if __name__ == "__main__":
    unittest.main()
