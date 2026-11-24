"""AUDIT.md 16.36: supplementary experiment S1 (post-freeze, exploratory). The guard accepts anime_f_01 / cartoon_boxo_01 only with supplementary "S1" and ONE look per
run; load_sessions refuses S1 sessions in an ordinary evaluation (and ordinary sessions in S1 mode); the S1 tool pairs sessions by start time, never writes a FINAL marker,
refuses the finals' root, and compares with the finals by run index (Newcombe)."""

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))

import data_splits_v4 as ds  # noqa: E402
import export_csv_v4 as ex  # noqa: E402
import process_final_zip_v4 as pf  # noqa: E402
import process_supplementary_zip_v4 as ps  # noqa: E402

SPLITS = ds.load()
A, C = "anime_f_01", "cartoon_boxo_01"


class GuardS1(unittest.TestCase):
    def test_accepted_only_with_s1_and_one_look(self):
        for look in (A, C):
            self.assertEqual(ds.guard_run([look], [], False, SPLITS, supplementary="S1"), "supplementary_S1")

    def test_refused_everywhere_else(self):
        for final in (False, True):
            with self.assertRaises(SystemExit):
                ds.guard_run([A], [], final, SPLITS)                              # no supplementary: the avatar_experiment role is refused
        with self.assertRaises(SystemExit):
            ds.guard_run([A], [], True, SPLITS, supplementary="S1")              # never in a final evaluation
        with self.assertRaises(SystemExit):
            ds.guard_run([A], [], False, SPLITS, supplementary="S2")             # unknown name

    def test_one_look_from_the_pair_only(self):
        with self.assertRaises(SystemExit):
            ds.guard_run([A, C], [], False, SPLITS, supplementary="S1")          # two looks in one run
        with self.assertRaises(SystemExit):
            ds.guard_run(["sunbox_m1"], [], False, SPLITS, supplementary="S1")   # a look outside the pair
        with self.assertRaises(SystemExit):
            ds.guard_run([], [], False, SPLITS, supplementary="S1")

    def test_clips_must_be_listed_and_of_one_role(self):
        with self.assertRaises(SystemExit):
            ds.guard_run([A], ["no_such_clip"], False, SPLITS, supplementary="S1")
        dev = [n for n, r in SPLITS["clips"].items() if r == "development"][0]
        tst = [n for n, r in SPLITS["clips"].items() if r == "test"][0]
        with self.assertRaises(SystemExit):
            ds.guard_run([A], [dev, tst], False, SPLITS, supplementary="S1")
        self.assertEqual(ds.guard_run([A], [dev], False, SPLITS, supplementary="S1"), "supplementary_S1")


class Pairing(unittest.TestCase):
    def make(self, base: Path, unity: dict, bridge: dict) -> tuple[list[Path], list[Path]]:
        u, b = [], []
        for name, runs in unity.items():
            d = base / name
            d.mkdir()
            (d / "session.json").write_text("{}", encoding="utf-8")
            for r in runs:
                (d / f"truth_run{r:03d}.json").write_text("{}", encoding="utf-8")
            u.append(d)
        for name, runs in bridge.items():
            d = base / name
            d.mkdir()
            for r in runs:
                (d / f"python_trial_{r:03d}.json").write_text("{}", encoding="utf-8")
            b.append(d)
        return u, b

    def test_started_last_before_the_unity_session(self):
        with tempfile.TemporaryDirectory() as t:
            u, b = self.make(Path(t), {"trials_final_Task2_A1_20261125_100500": [1, 2], "trials_final_Task2_A1_20261125_120500": [1, 2]},
                             {"bridge_guide_20261125_100000": [1, 2], "bridge_guide_20261125_120000": [1, 2]})
            pairs = ps.pair_sessions(u, b)
            self.assertEqual([(x.name[-6:], y.name[-6:]) for x, y in pairs], [("100500", "100000"), ("120500", "120000")])

    def test_each_bridge_once_and_runs_must_agree(self):
        with tempfile.TemporaryDirectory() as t:
            u, b = self.make(Path(t), {"trials_20261125_100500": [1, 2]}, {"bridge_20261125_100000": [1, 2, 3]})
            with self.assertRaisesRegex(pf.StepFailed, "same runs"):
                ps.pair_sessions(u, b)
        with tempfile.TemporaryDirectory() as t:
            u, b = self.make(Path(t), {"trials_20261125_100500": [1], "trials_20261125_110500": [1]}, {"bridge_20261125_100000": [1]})
            with self.assertRaisesRegex(pf.StepFailed, "cannot be paired"):
                ps.pair_sessions(u, b)
        with tempfile.TemporaryDirectory() as t:
            u, b = self.make(Path(t), {"trials_20261125_090500": [1]}, {"bridge_20261125_100000": [1]})
            with self.assertRaisesRegex(pf.StepFailed, "no bridge folder started before"):
                ps.pair_sessions(u, b)


class Comparison(unittest.TestCase):
    def test_paired_by_run_index_with_newcombe_and_four_way_table(self):
        import csv
        with tempfile.TemporaryDirectory() as t:
            root = Path(t)
            fin = {}
            for s, outcomes in (("A1", "SSSSSSSSSF"), ("A2_right", "SSSSSSSSFF")):
                d = root / f"export_{s}"
                d.mkdir()
                (d / "FINAL_EXPORT_DONE.json").write_text('{"setting": "%s"}' % s, encoding="utf-8")
                with (d / "runs.csv").open("w", newline="", encoding="utf-8") as f:
                    w = csv.writer(f)
                    w.writerow(["trial", "outcome"])
                    for i, o in enumerate(outcomes, 1):
                        w.writerow([i, "SUCCESS" if o == "S" else "FAILURE"])
                fin[s] = d
            real = ps.fg.markers
            ps.fg.markers = lambda r, s, k: [fin[s] / "FINAL_EXPORT_DONE.json"]
            try:
                sess = {("A1", A): {"runs": [{"trial": i, "outcome": "SUCCESS" if i != 3 else "FAILURE"} for i in range(1, 11)], "dialogs": []}}
                rates, pairs = ps.comparison_rows(sess, root, 1.96)
            finally:
                ps.fg.markers = real
        self.assertEqual(rates[0]["S1 successes"], 9)
        self.assertEqual(rates[0]["Sunbox final successes (same run indices)"], 9)
        p = pairs[0]
        self.assertEqual((p["both_succeed"], p["only_S1_succeeds"], p["only_final_succeeds"], p["neither"]), (8, 1, 1, 0))
        self.assertEqual(p["run_indices_failed_in_S1"], "3")
        self.assertEqual(rates[0]["difference_pp (S1 - final)"], ex.newcombe(9, 10, 9, 10, 1.96)["difference_pp"])


class LoadSessionsS1(unittest.TestCase):
    def setUp(self):
        import gesture_data as gd
        import hri_eval_dev_v4 as ev
        import hri_sim_v4 as sv
        import test_export_csv_v4 as tx
        self.gd, self.ev = gd, ev
        res = [sv.run_scenario("A1", s, sv.DETECTION_ON, side="right") for s in (1, 2)]
        self.plain = tx.session(res, Path(tempfile.mkdtemp()), "plain")
        self.tagged = tx.session(res, Path(tempfile.mkdtemp()), "tagged", extra={"supplementary": "S1"})

    def test_an_ordinary_evaluation_refuses_an_s1_session(self):
        with self.assertRaisesRegex(SystemExit, "never loads a supplementary session"):
            self.ev.load_sessions([self.tagged], self.gd.load_config())
        self.assertTrue(self.ev.load_sessions([self.plain], self.gd.load_config()))      # the untagged one still loads

    def test_s1_mode_refuses_an_untagged_session_and_a_look_outside_the_pair(self):
        with self.assertRaisesRegex(SystemExit, "supplementary mode"):
            self.ev.load_sessions([self.plain], self.gd.load_config(), supplementary="S1")
        with self.assertRaises(SystemExit):                                              # tagged, but the workers wear Sunbox looks, not anime_f_01 / cartoon_boxo_01
            self.ev.load_sessions([self.tagged], self.gd.load_config(), supplementary="S1")


class NoFinalsWrites(unittest.TestCase):
    def test_out_root_inside_the_finals_root_is_refused(self):
        with tempfile.TemporaryDirectory() as t:
            fin = Path(t) / "finals"
            fin.mkdir()
            for out in (fin, fin / "sub"):
                with self.assertRaisesRegex(SystemExit, "finals' root"):
                    ps.run(Path(t) / "x.zip", "0" * 64, finals_root=fin, out_root=out)
            self.assertEqual(list(fin.iterdir()), [])

    def test_no_final_marker_file_names_in_the_tool_output_contract(self):
        self.assertIn("FINAL_DONE.json", ps.FINAL_MARKERS)
        self.assertIn("FINAL_EXPORT_DONE.json", ps.FINAL_MARKERS)


if __name__ == "__main__":
    unittest.main()
