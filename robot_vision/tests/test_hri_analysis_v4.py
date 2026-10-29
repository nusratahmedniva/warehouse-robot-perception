"""v4 analysis (hri_analysis_v4.py): intervals, the blocks per setting with coverage, the v3 archive columns of the RQ1 table, the
split guard (development data only unless --final after the freeze check), and the output folder. Synthetic run folders from the
v4 simulator."""

import io
import json
import shutil
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))

import decision_io as dio  # noqa: E402
import final_guard_v4 as fg  # noqa: E402
import freeze_v4 as fz  # noqa: E402
import hri_analysis as ha  # noqa: E402
import hri_analysis_v4 as an  # noqa: E402
import hri_sim_v4 as sv  # noqa: E402
import run_paths as rp  # noqa: E402
import test_gt_path as tg  # noqa: E402
import test_hri_sim_v4_trials as tt  # noqa: E402
import test_v4_final as tf  # noqa: E402

CFG = an.load_config()
DEV = dict(bystander_offsets_m=[(1.2, 0.3), (2.0, -0.5)], bystander_looks=["placeholder_look_dev_2", "placeholder_look_dev_1"])


class IntervalTests(unittest.TestCase):
    def test_wilson_matches_the_v3_analysis(self):
        w = an.wilson(10, 10, CFG)
        self.assertEqual((w["k"], w["n"], w["ratio"]), (10, 10, 1.0))
        self.assertEqual(w["wilson95"], list(ha.wilson(10, 10)))
        self.assertAlmostEqual(w["wilson95"][0], 0.7225, places=3)                   # the v3 figure 0.72-1.0
        self.assertEqual(an.wilson(0, 0, CFG)["wilson95"], an.NE)

    def test_bootstrap_is_reproducible_and_resamples_runs_not_frames(self):
        items = [(10, 10, 10), (10, 10, 0), (10, 10, 10), (10, 10, 10)]               # one bad run of four
        a, b = an.bootstrap(items, an._ratio_stat(2, 1), CFG), an.bootstrap(items, an._ratio_stat(2, 1), CFG)
        self.assertEqual(a, b)
        self.assertEqual((a["estimate"], a["n_runs"], a["unit"]), (0.75, 4, "run (cluster bootstrap)"))
        self.assertLess(a["lo"], 0.75)
        self.assertEqual(a["hi"], 1.0)
        pooled = an.wilson(30, 40, CFG)["wilson95"]
        self.assertLess(a["lo"], pooled[0])                                           # run-level interval is wider than the frame-level one

    def test_bootstrap_edge_cases(self):
        self.assertEqual(an.bootstrap([], an._median_stat, CFG), {"status": an.NE, "n_runs": 0})
        one = an.bootstrap([[2.0, 4.0]], an._median_stat, CFG)
        self.assertEqual((one["lo"], one["hi"], one["estimate"]), (3.0, 3.0, 3.0))
        none = an.bootstrap([(0, 0, 0)], an._ratio_stat(2, 1), CFG)
        self.assertIsNone(none["estimate"])

    def test_spread_median_and_95th_percentile(self):
        s = an.spread([float(i) for i in range(1, 101)], CFG, [[float(i) for i in range(1, 51)], [float(i) for i in range(51, 101)]])
        self.assertEqual((s["n"], s["median"]), (100, 50.5))
        self.assertAlmostEqual(s["p95"], 95.05, places=2)
        self.assertEqual(s["max"], 100.0)
        self.assertIn("median_ci", s)
        self.assertIn("p95_ci", s)
        self.assertEqual(an.spread([], CFG), {"n": 0, "status": an.NE})

    def test_the_bootstrap_settings_come_from_the_config_and_are_declared(self):
        self.assertEqual((CFG["bootstrap"]["n_resamples"], CFG["bootstrap"]["seed"], CFG["bootstrap"]["unit"]), (2000, 1, "run"))
        self.assertEqual(CFG["status"], "declared")


class V3ArchiveTests(unittest.TestCase):
    """The columns read from the committed results/summary/ tables."""

    @classmethod
    def setUpClass(cls):
        cls.cols = an.v3_columns(CFG)

    def test_the_three_archived_sources_are_read(self):
        self.assertEqual(list(self.cols), ["v3 Task 2 final (original)", "v3 Task 2 replication", "v3 Task 1 final"])
        for c in self.cols.values():
            self.assertNotIn("status", c)

    def test_task2_original(self):
        c = self.cols["v3 Task 2 final (original)"]
        self.assertEqual((c["runs"], c["success"]["k"], c["junction_reads"], c["read_as_shown"]), (10, 10, 14, 14))
        self.assertEqual((c["collisions"], c["collisions_with_a_person"]), (0, 0))
        self.assertIn("stated in AUDIT.md section 2", c["read_as_shown_at_first_ask"])
        self.assertEqual(c["closest_person_min_m"], 1.033)
        self.assertEqual(c["time_excl_stale_stops_s"], an.NE)                          # not available for the original

    def test_task2_replication_and_task1(self):
        c = self.cols["v3 Task 2 replication"]
        self.assertEqual((c["success"]["k"], c["read_as_shown_at_first_ask"], c["collisions"]), (10, "14 of 14", 0))
        self.assertEqual(c["closest_person_min_m"], 1.002)
        t = self.cols["v3 Task 1 final"]
        self.assertEqual((t["success"]["k"], t["read_as_shown_at_first_ask"], t["junction_reads"]), (10, "30 of 30", 30))
        self.assertEqual(t["closest_person_min_m"], 1.352)

    def test_a_missing_source_is_not_evaluated_not_invented(self):
        cfg = json.loads(json.dumps(CFG))
        cfg["v3_results"]["task1_final"] = "../results/summary/nothing.csv"
        self.assertEqual(an.v3_columns(cfg)["v3 Task 1 final"]["status"], an.NE)
        row = an.rq1_table({}, cfg)["rows"][1]
        self.assertEqual(row["v3 Task 1 final"], an.NE)


class AnalysisTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        root = Path(cls.tmp.name)
        spec = sv.SceneSpec(**DEV)
        on = [tt.trial("E2", spec, seed=s) for s in (1, 2, 3)] + [tt.trial("E1", spec, seed=1)]
        off = [tt.trial("E2", spec, zoom=False, seed=s) for s in (4, 5)] + [tt.trial("E1", spec, zoom=False, seed=5, two_view=False, shift=0.4)]
        cls.u1, cls.b1 = sv.export_session(on, root, True, name="on")
        cls.u2, cls.b2 = sv.export_session(off, root, False, name="off")
        tgdir = root / "paths"
        tg.write_run(tgdir / "run", [(0.25, 0.25), (0.75, 0.75), (1.25, 1.25), (1.75, 1.75)])
        for f in (tgdir / "run").iterdir():
            shutil.copy2(f, cls.u1 / "run_001" / f.name)
        cls.res = an.analyse([("zoom_on", cls.u1, cls.b1), ("zoom_off", cls.u2, cls.b2)], CFG)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_settings_are_grouped_by_label(self):
        self.assertEqual(set(self.res["settings"]), {"zoom_on", "zoom_off"})
        self.assertEqual((self.res["settings"]["zoom_on"]["runs"], self.res["settings"]["zoom_off"]["runs"]), (4, 3))
        self.assertFalse(self.res["final"])

    def test_success_with_wilson_over_runs(self):
        on, off = self.res["settings"]["zoom_on"]["success"], self.res["settings"]["zoom_off"]["success"]
        self.assertEqual((on["k"], on["n"], on["unit"]), (4, 4, "runs"))
        self.assertEqual((off["k"], off["n"]), (2, 3))
        self.assertEqual(off["failure_reasons"], {"aborted": 1})
        self.assertTrue(off["wilson95"][0] < 2 / 3 < off["wilson95"][1])

    def test_gesture_block_has_coverage_and_both_kinds_of_interval(self):
        p = self.res["settings"]["zoom_on"]["gesture"]["per_command"]["POINT"]
        self.assertTrue(0 < p["coverage"]["ratio"] < 1)
        self.assertEqual(p["accuracy_of_answered"]["ratio"], 1.0)
        for k in ("coverage", "accuracy_of_answered"):
            self.assertIn("wilson95", p[k])
            self.assertEqual(p[k]["bootstrap"]["unit"], "run (cluster bootstrap)")
            self.assertEqual(p[k]["bootstrap"]["n_runs"], 4)
        self.assertEqual(self.res["settings"]["zoom_on"]["gesture"]["per_command"]["WAIT"]["accuracy_of_answered"]["ratio"], an.NE)

    def test_angle_block_median_p95_and_bootstrap(self):
        a = self.res["settings"]["zoom_on"]["angle"]
        r = a["resolved_reading_deg"]
        self.assertGreater(r["n"], 10)
        self.assertLess(r["p95"], 1.0)
        self.assertEqual(r["median_ci"]["n_runs"], 4)
        self.assertIn("p95_ci", r)
        self.assertTrue(0 < a["ambiguous_share"]["ratio"] < 1)                         # the E1 run needed a second look
        self.assertEqual(a["coverage"]["n"], a["held_point_frames"])

    def test_branch_commander_and_timing(self):
        s = self.res["settings"]["zoom_on"]
        self.assertEqual(s["branch"]["correct_of_scored"]["ratio"], 1.0)
        self.assertEqual(s["branch"]["second_view"]["asks_with_a_second_view"], 1)
        self.assertEqual(s["branch"]["correct_at_the_first_ask_of_all_asks"]["k"], 4)
        c = s["commander"]["with_bystanders"]
        self.assertEqual(c["accuracy_of_decided"]["ratio"], 1.0)
        self.assertEqual(s["commander"]["without_bystanders"]["accuracy_of_decided"]["ratio"], an.NE)
        self.assertGreater(s["timing"]["ask_to_accepted_s"]["median"], 1.0)
        self.assertEqual(s["timing"]["accepted"], 4)

    def test_path_measures_only_where_the_files_exist(self):
        p = self.res["settings"]["zoom_on"]["path"]
        self.assertEqual(p["coverage"], "1 of 4 runs have the v4 path files")
        self.assertEqual(p["optimal_path_matches_astar"], "1 of 1")
        self.assertEqual(p["final_distance_from_b_m"]["max"], 0.0)
        self.assertIn("optimal corridor", p["reference"])
        self.assertEqual(p["unity_path_inside_the_corridor"], "1 of 1")
        self.assertEqual(p["corridor_cells"]["n"], 1)
        self.assertIn("runs_with_several_shortest_paths", p)
        self.assertIn("optimal corridor", an.markdown(self.res))
        self.assertEqual(self.res["settings"]["zoom_off"]["path"]["status"], an.NE)

    def test_safety_system_and_times(self):
        s = self.res["settings"]["zoom_on"]
        self.assertEqual((s["safety"]["collisions"], s["safety"]["runs_with_an_outcome"]), (0, 4))
        self.assertGreater(s["safety"]["closest_person_m"]["min"], 0.65)
        self.assertEqual(s["system"]["round_trip_ms"]["n"], 20)
        self.assertEqual(s["system"]["inference_ms"]["yolo11s-pose/cam360"]["mean"], 200.0)
        self.assertEqual(s["times"]["total_s"]["n"], 4)
        self.assertEqual(s["times"]["time_excl_stale_stops_s"]["n"], 0)                # no safety column in the synthetic logs

    def test_groups_per_look_style_distance_and_zoom(self):
        s = self.res["settings"]["zoom_on"]
        self.assertEqual(set(s["per_look"]), {"placeholder_look_dev_1"})
        self.assertEqual(set(s["per_style"]), {"placeholder_style_a"})
        self.assertIn("accuracy_interval", s["per_look"]["placeholder_look_dev_1"])
        self.assertTrue(any(v["frames"] for v in s["per_distance"].values()))
        self.assertEqual(s["per_zoom"]["zoom_off"], an.NE)                             # this setting has only zoom-on runs
        self.assertEqual(s["per_zoom"]["zoom_on"]["runs"], 4)

    def test_rq1_table_lists_v3_and_every_v4_setting_with_the_differences(self):
        t = self.res["rq1"]
        self.assertEqual(t["columns"], ["v3 Task 2 final (original)", "v3 Task 2 replication", "v3 Task 1 final", "v4 zoom_off", "v4 zoom_on"])
        by = {r["measure"]: r for r in t["rows"]}
        self.assertIn("4/4", by["Success"]["v4 zoom_on"])
        self.assertIn("2/3", by["Success"]["v4 zoom_off"])
        self.assertIn("10/10", by["Success"]["v3 Task 2 final (original)"])
        self.assertEqual(by["Collisions (with a person)"]["v4 zoom_on"], "0 (0)")
        self.assertEqual(len(t["declared_differences"]), len(CFG["declared_differences"]))
        md = an.markdown(self.res)
        self.assertIn("Declared differences between v3 and v4", md)
        self.assertIn("Dialog hold: v4 accepts a reading held 0.5 s", md)
        self.assertIn("not_evaluated", md)

    def test_the_markdown_gives_intervals_and_coverage(self):
        md = an.markdown(self.res)
        for word in ("Wilson", "bootstrap", "coverage", "Per look style", "Zoom on vs off", "run-level"):
            self.assertIn(word, md)


class GuardAndOutputTests(unittest.TestCase):
    def tearDown(self):
        rp.set_active_roots({})

    def test_test_data_is_refused_without_final(self):
        with tempfile.TemporaryDirectory() as d:
            u, b = tf.session(Path(d), "t")
            with self.assertRaisesRegex(SystemExit, "final evaluation only"):
                an.analyse([("zoom_on", u, b)], CFG)

    def test_final_is_refused_while_not_frozen(self):
        with tempfile.TemporaryDirectory() as d:
            u, b = tf.session(Path(d), "t")
            with self.assertRaisesRegex(SystemExit, "not frozen"):
                an.analyse([("zoom_on", u, b)], CFG, final=True)

    def test_final_on_a_frozen_repo_with_test_data(self):
        with tempfile.TemporaryDirectory() as d:
            repo = tf.final_repo(Path(d) / "r")
            u, b = tf.session(Path(d), "t")
            res = an.analyse([("zoom_on", u, b)], CFG, final=True, repo=repo)
            self.assertTrue(res["final"])
            self.assertIn("TEST", res["splits"])
            self.assertEqual(res["settings"]["zoom_on"]["runs"], 2)
            self.assertIn("FINAL settings, test data", an.markdown(res))

    def test_final_checks_the_setting_and_refuses_development_data(self):
        with tempfile.TemporaryDirectory() as d:
            repo = tf.final_repo(Path(d) / "r")
            u, b = tf.session(Path(d), "z", zoom=False)
            with self.assertRaisesRegex(SystemExit, "needs zoom on"):
                an.analyse([("zoom_on", u, b)], CFG, final=True, repo=repo)
            du, db = tf.session(Path(d), "dev", spec_kw={"commander_look": "placeholder_look_dev_1",
                                                         "clips": {"POINT": "placeholder_point_dev_1", "WAIT": "placeholder_wait_dev_1",
                                                                   "STOP": "placeholder_stop_dev_1"}})
            with self.assertRaisesRegex(SystemExit, "--final-evaluation given"):
                an.analyse([("zoom_on", du, db)], CFG, final=True, repo=repo)

    def test_the_analysis_may_be_repeated_unlike_the_final_evaluation(self):
        with tempfile.TemporaryDirectory() as d:
            repo = tf.final_repo(Path(d) / "r")
            u, b = tf.session(Path(d), "t")
            an.analyse([("zoom_on", u, b)], CFG, final=True, repo=repo)
            an.analyse([("zoom_on", u, b)], CFG, final=True, repo=repo)
            self.assertEqual(fg.markers(d, "zoom_on", "evaluation"), [])

    def test_main_writes_a_new_folder_with_the_table_and_the_commit(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            u, b = sv.export_session([tt.trial("E2", sv.SceneSpec(), seed=1), tt.trial("E2", sv.SceneSpec(), seed=2)], root, True, name="m")
            out = root / "out"
            out.mkdir()
            real = dio.new_run_dir
            dio.new_run_dir = lambda cfg, prefix: out
            try:
                with redirect_stdout(io.StringIO()):
                    an.main(["--session", "dev", str(u), str(b)])
            finally:
                dio.new_run_dir = real
            for name in ("analysis.json", "analysis.md", "rq1_comparison.csv", "run.json", "config_used/analysis.json",
                         "config_used/data_splits.json"):
                self.assertTrue((out / name).exists(), name)
            self.assertIn("commit", json.loads((out / "run.json").read_text())["git"])
            self.assertEqual(json.loads((out / "analysis.json").read_text())["settings"]["dev"]["runs"], 2)
            self.assertIn("v4 dev", (out / "rq1_comparison.csv").read_text())

    def test_main_refuses_test_data_without_final(self):
        with tempfile.TemporaryDirectory() as d:
            u, b = tf.session(Path(d), "t")
            with self.assertRaises(SystemExit):
                an.main(["--session", "zoom_on", str(u), str(b)])


class IsolationTests(unittest.TestCase):
    def test_inference_never_imports_the_analysis(self):
        import ast
        for p in ROOT.rglob("*.py"):
            rel = p.relative_to(ROOT)
            if ".venv" in rel.parts or rel.parts[0] == "tests" or rel.name in ("hri_analysis_v4.py",):
                continue
            tree = ast.parse(p.read_text(encoding="utf-8"))
            mods = {a.name.split(".")[0] for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names}
            mods |= {n.module.split(".")[0] for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) and n.module}
            self.assertNotIn("hri_analysis_v4", mods, str(rel))


if __name__ == "__main__":
    unittest.main()
