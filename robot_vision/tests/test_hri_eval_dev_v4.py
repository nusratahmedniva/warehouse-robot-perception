"""Development evaluation (hri_eval_dev_v4.py) on synthetic run folders written by the v4 simulator: metrics with their
coverage, the split guard that refuses test data, matching of people to workers, and the output folder."""

import ast
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
import hri_eval_dev_v4 as ev  # noqa: E402
import hri_sim_v4 as sv  # noqa: E402
import test_hri_sim_v4_trials as tt  # noqa: E402

GC, EC = gd.load_config(), ev.load_config()
DEV = dict(bystander_offsets_m=[(1.2, 0.3), (-1.6, -0.2)],
           bystander_looks=["placeholder_look_dev_2", "placeholder_look_dev_1"])


def session(root: Path, name: str, results: list, zoom: bool) -> tuple:
    return sv.export_session(results, root, zoom, name=name)


class MatchTests(unittest.TestCase):
    def test_nearest_within_tolerance_and_not_a_tie(self):
        self.assertEqual(ev.match_worker(5.0, {1: 0.0, 2: 30.0}, 10.0), 1)
        self.assertIsNone(ev.match_worker(15.0, {1: 0.0, 2: 30.0}, 10.0))            # equally near both
        self.assertIsNone(ev.match_worker(25.0, {1: 0.0}, 10.0))                      # beyond the tolerance
        self.assertIsNone(ev.match_worker(0.0, {}, 10.0))
        self.assertEqual(ev.match_worker(-178.0, {3: 179.0}, 10.0), 3)                # wraps

    def test_distance_bins(self):
        bins = EC["distance_bins_m"]
        self.assertEqual(ev.distance_bin({"distance_m": 2.0}, bins), "1.5-2.5 m")
        self.assertEqual(ev.distance_bin({"distance_m": 7.0}, bins), ">= 6 m")
        self.assertIsNone(ev.distance_bin({"distance_m": None}, bins))


class EvaluationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        root = Path(cls.tmp.name)
        spec = sv.SceneSpec(**DEV)
        on = [tt.good("E2", spec, seed=1), tt.good("E4", spec, seed=3)]
        off = [tt.trial("E2", spec, zoom=False, seed=4), tt.trial("E1", spec, zoom=False, seed=5, two_view=False, shift=0.4)]   # E1: ambiguous, aborts
        cls.pairs = [session(root, "on", on, True), session(root, "off", off, False)]
        cls.runs = ev.load_sessions(cls.pairs, GC)
        cls.res = ev.evaluate(cls.runs, EC, GC)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_runs_and_zoom_labels(self):
        self.assertEqual(len(self.runs), 4)
        self.assertEqual([r.zoom_on for r in self.runs], [True, True, False, False])
        self.assertTrue(all(r.bystanders for r in self.runs))
        self.assertEqual(self.res["per_zoom"]["zoom_on"]["runs"], 2)
        self.assertEqual(self.res["per_zoom"]["zoom_off"]["runs"], 2)

    def test_gesture_reading_has_coverage_and_perfect_simulated_accuracy(self):
        pc = self.res["gesture"]["per_command"]["POINT"]
        self.assertGreater(pc["frames"], 50)
        self.assertTrue(0 < pc["coverage"] < 1)                      # the reader needs a hold: early frames are not answered
        self.assertEqual(pc["accuracy_of_answered"], 1.0)
        self.assertEqual(self.res["gesture"]["per_command"]["WAIT"]["accuracy_of_answered"], ev.NOT_EVALUATED)   # no WAIT shown
        self.assertEqual(self.res["gesture"]["false_reads"]["read_as_a_command"], 0)
        self.assertEqual(self.res["gesture"]["frames_unmatched"], 0)
        conf = self.res["gesture"]["confusion"]
        self.assertEqual(conf["POINT"]["POINT"], pc["correct"])
        self.assertEqual(sum(conf["POINT"].values()), pc["frames"])

    def test_grouping_by_look_distance_and_zoom(self):
        self.assertEqual(set(self.res["per_look"]), {"placeholder_look_dev_1"})                  # only the commander gestured
        d = self.res["per_distance"]
        self.assertEqual(sum(v["frames"] for v in d.values()), self.res["gesture"]["per_command"]["POINT"]["frames"])
        # the robot approaches the NEAREST person (the v3 rule), here a bystander, so the commander is seen from 2.5 to 4 m
        self.assertTrue(any(v["frames"] for k, v in d.items() if k.startswith("2.5-4")))
        for blk in self.res["per_zoom"].values():
            self.assertGreater(blk["gesture"]["per_command"]["POINT"]["frames"], 0)

    def test_point_angle_error_and_ambiguity(self):
        a = self.res["angle"]
        self.assertGreater(a["read_as_point"], 10)
        self.assertLess(a["error_deg_resolved_reading"]["max"], 1.0)                 # the simulator has no angle noise
        self.assertGreater(a["ambiguous"], 0)                                         # the E1 run: FORWARD from the v3 viewpoint
        self.assertTrue(0 < a["ambiguous_share"] < 1)

    def test_branch_and_timing_with_coverage(self):
        b = self.res["branch"]
        self.assertEqual(b["junction_asks"], 5)                                       # E2: J1; E4: J1+J2; E2: J1; E1: J1 (aborted)
        self.assertEqual(b["accepted"], 4)
        self.assertEqual(b["answered_share"], 0.8)
        self.assertEqual((b["correct"], b["not_evaluated"]), (4, 0))
        self.assertEqual(b["correct_rate_of_scored"], 1.0)
        t = self.res["timing"]
        self.assertEqual((t["accepted"], t["junction_asks"]), (4, 5))
        self.assertGreater(t["ask_to_accepted_s"]["median"], 1.0)

    def test_commander_accuracy_with_bystanders(self):
        c = self.res["commander"]["with_bystanders"]
        self.assertGreater(c["frames"], 50)
        self.assertEqual(c["wrong"], 0)
        self.assertGreater(c["correct"], 30)
        self.assertTrue(0 < c["coverage"] <= 1)
        self.assertEqual(self.res["commander"]["without_bystanders"]["accuracy_of_decided"], ev.NOT_EVALUATED)

    def test_second_view_and_reapproach_are_counted(self):
        self.assertEqual(self.res["branch"]["second_view"]["asks_with_a_second_view"], 0)      # tie-break sessions need none
        with tempfile.TemporaryDirectory() as d:
            results = [tt.trial("E3", sv.SceneSpec(), seed=1), tt.trial("E2", sv.SceneSpec(), seed=2),
                       tt.trial("E1", sv.SceneSpec(bystander_offsets_m=[(-1.95, -0.7)], bystander_looks=["placeholder_look_dev_2"]), seed=1)]
            res = ev.evaluate(ev.load_sessions([session(Path(d), "tv", results, True)], GC), EC, GC)
        b = res["branch"]
        self.assertEqual((b["second_view"]["asks_with_a_second_view"], b["second_view"]["accepted_after_it"]), (2, 2))
        self.assertEqual(b["reapproached"]["asks"], 1)
        self.assertEqual((b["junction_asks"], b["accepted"], b["correct"]), (4, 4, 4))
        self.assertIn("Second view", ev.markdown(res))

    def test_zoom_blocks_are_independent(self):
        on, off = self.res["per_zoom"]["zoom_on"], self.res["per_zoom"]["zoom_off"]
        self.assertEqual(on["branch"]["accepted"], 3)
        self.assertEqual(off["branch"]["accepted"], 1)

    def test_markdown_reports_coverage_everywhere(self):
        md = ev.markdown(self.res)
        for word in ("coverage", "Per look", "Per distance", "Zoom on vs off", "not_evaluated", "Commander", "answered"):
            self.assertIn(word, md)


class LossyAndWaitTests(unittest.TestCase):
    def test_wrong_classes_and_misses_show_up_as_confusion_and_lower_coverage(self):
        with tempfile.TemporaryDirectory() as d:
            spec = sv.SceneSpec(**DEV, wait_first_s=3.0, distractors=[(0, "STOP", 0.0, None)])
            g = sv.GestureSimConfig(coverage={"POINT": 0.7, "WAIT": 0.7, "STOP": 0.7}, accuracy={"POINT": 0.6, "WAIT": 0.8, "STOP": 0.8})
            results = [tt.trial("E2", spec, g, seed=s) for s in (1, 2, 3)]
            res = ev.evaluate(ev.load_sessions([session(Path(d), "lossy", results, True)], GC), EC, GC)
        conf = res["gesture"]["confusion"]
        self.assertGreater(conf["POINT"]["WAIT"] + conf["WAIT"]["STOP"] + conf["STOP"]["WAIT"], 0)
        self.assertGreater(res["gesture"]["per_command"]["WAIT"]["frames"], 0)
        for s in ("POINT", "WAIT", "STOP"):
            self.assertLess(res["gesture"]["per_command"][s]["coverage"], 1.0)
            self.assertLess(res["gesture"]["per_command"][s]["accuracy_of_answered"], 1.0 + 1e-9)

    def test_wait_time_is_taken_out_of_the_second_timing(self):
        with tempfile.TemporaryDirectory() as d:
            results = [tt.trial("E2", sv.SceneSpec(wait_first_s=4.0), seed=1)]
            res = ev.evaluate(ev.load_sessions([session(Path(d), "wait", results, True)], GC), EC, GC)
        t = res["timing"]
        self.assertGreater(t["ask_to_accepted_s"]["median"], t["ask_to_accepted_without_wait_s"]["median"] + 1.0)


class SplitGuardTests(unittest.TestCase):
    def pairs(self, root, edit=None, **spec_kw):
        results = [tt.good("E2", sv.SceneSpec(**{**DEV, **spec_kw}), seed=1)]
        u, b = session(root, "s", results, True)
        if edit:
            f = u / "run_001" / "truth.jsonl"
            f.write_text(edit(f.read_text(encoding="utf-8")), encoding="utf-8")
        return [(u, b)]

    def test_development_data_is_accepted(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertEqual(len(ev.load_sessions(self.pairs(Path(d)), GC)), 1)

    def test_a_test_look_is_refused(self):
        with tempfile.TemporaryDirectory() as d:
            pairs = self.pairs(Path(d), lambda t: t.replace("placeholder_look_dev_2", "placeholder_look_test_1"))
            with self.assertRaisesRegex(SystemExit, "mixes development and test"):
                ev.load_sessions(pairs, GC)

    def test_only_test_data_is_refused_without_the_final_flag(self):
        with tempfile.TemporaryDirectory() as d:
            def edit(t):
                for a, b in (("placeholder_look_dev_1", "placeholder_look_test_1"), ("placeholder_look_dev_2", "placeholder_look_test_1"),
                             ("placeholder_point_dev_1", "placeholder_point_test_1")):
                    t = t.replace(a, b)
                return t
            with self.assertRaisesRegex(SystemExit, "final evaluation only"):
                ev.load_sessions(self.pairs(Path(d), edit), GC)

    def test_a_test_clip_with_a_development_look_is_refused(self):
        with tempfile.TemporaryDirectory() as d:
            pairs = self.pairs(Path(d), lambda t: t.replace("placeholder_point_dev_1", "placeholder_point_test_1"))
            with self.assertRaisesRegex(SystemExit, "mixes development and test"):
                ev.load_sessions(pairs, GC)

    def test_unknown_names_and_missing_clip_names_are_refused(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaisesRegex(SystemExit, "not listed"):
                ev.load_sessions(self.pairs(Path(d), lambda t: t.replace("placeholder_look_dev_2", "stranger")), GC)
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaisesRegex(SystemExit, "no animation clip name"):
                ev.load_sessions(self.pairs(Path(d), lambda t: t.replace('"clip": "placeholder_point_dev_1"', '"clip": ""')), GC)

    def test_the_refusal_names_the_run(self):
        with tempfile.TemporaryDirectory() as d:
            pairs = self.pairs(Path(d), lambda t: t.replace("placeholder_look_dev_2", "stranger"))
            with self.assertRaises(SystemExit) as cm:
                ev.load_sessions(pairs, GC)
            self.assertIn("trials_s/run_001", str(cm.exception))

    def test_a_bad_truth_line_is_a_clear_error(self):
        with tempfile.TemporaryDirectory() as d:
            pairs = self.pairs(Path(d), lambda t: t + "{broken\n")
            with self.assertRaisesRegex(gd.TruthError, "truth.jsonl line"):
                ev.load_sessions(pairs, GC)


class MainTests(unittest.TestCase):
    def test_main_writes_a_new_folder_with_config_and_commit(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            u, b = session(root, "m", [tt.good("E2", sv.SceneSpec(**DEV), seed=1)], True)
            out = root / "hri_eval_dev_v4_out"
            out.mkdir()
            real = dio.new_run_dir
            dio.new_run_dir = lambda cfg, prefix: out
            try:
                with redirect_stdout(io.StringIO()):
                    ev.main(["--session", str(u), str(b)])
            finally:
                dio.new_run_dir = real
            for name in ("eval.json", "eval.md", "run.json", "config_used/eval_dev.json", "config_used/gesture_data.json",
                         "config_used/data_splits.json"):
                self.assertTrue((out / name).exists(), name)
            self.assertIn("commit", json.loads((out / "run.json").read_text())["git"])
            self.assertEqual(json.loads((out / "eval.json").read_text())["runs"], 1)

    def test_main_refuses_test_data(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            u, b = session(root, "m", [tt.good("E2", sv.SceneSpec(**DEV), seed=1)], True)
            f = u / "run_001" / "truth.jsonl"
            f.write_text(f.read_text().replace("placeholder_look_dev_2", "placeholder_look_test_1"))
            with self.assertRaises(SystemExit):
                ev.main(["--session", str(u), str(b)])


class IsolationTests(unittest.TestCase):
    def test_inference_code_never_imports_the_evaluation_script(self):
        offenders = []
        for p in ROOT.rglob("*.py"):
            rel = p.relative_to(ROOT)
            # the evaluation modules themselves (final evaluation and analysis are evaluation code too)
            if ".venv" in rel.parts or rel.parts[0] == "tests" or rel.name in (
                    "hri_eval_dev_v4.py", "hri_eval_final_v4.py", "hri_analysis_v4.py"):
                continue
            tree = ast.parse(p.read_text(encoding="utf-8"))
            mods = {a.name.split(".")[0] for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names}
            mods |= {n.module.split(".")[0] for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) and n.module}
            if "hri_eval_dev_v4" in mods:
                offenders.append(str(rel))
        self.assertEqual(offenders, [])

    def test_inference_modules_do_not_import_truth_or_split_code(self):
        banned = {"gesture_data", "gt_path", "hri_eval_dev_v4"}
        for name in ("hri_control_v4.py", "commander_v4.py", "gesture_motion.py", "hri_perception_v4.py", "gesture_adapter_v4.py",
                     "bridge/perception_v4.py", "bridge/guide_v4.py", "hri_sim_v4.py"):
            tree = ast.parse((ROOT / name).read_text(encoding="utf-8"))
            mods = {a.name.split(".")[0] for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names}
            mods |= {n.module.split(".")[0] for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) and n.module}
            self.assertFalse(mods & banned, (name, mods & banned))


if __name__ == "__main__":
    unittest.main()
