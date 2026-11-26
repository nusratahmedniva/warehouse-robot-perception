"""AUDIT.md 16.36: supplementary experiment S1 (post-freeze, exploratory). The guard accepts anime_f_01 / cartoon_boxo_01 only with supplementary "S1" and ONE look per
run; load_sessions refuses S1 sessions in an ordinary evaluation (and ordinary sessions in S1 mode); the S1 tool pairs sessions by start time, never writes a FINAL marker,
refuses the finals' root, and compares with the finals by run index (Newcombe)."""

import json
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
    def test_the_four_looks(self):
        self.assertEqual(set(ds.SUPPLEMENTARY["S1"]), {"mixamo_worker", "anime_f_01", "anime_f_02_outfit_short", "cartoon_boxo_01"})
        for look in ds.SUPPLEMENTARY["S1"]:
            self.assertEqual(ds.guard_run([look], [], False, SPLITS, supplementary="S1"), "supplementary_S1")
            with self.assertRaises(SystemExit):
                ds.guard_run([look], [], False, SPLITS)


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
    def test_paired_by_plan_run_with_newcombe_and_four_way_table(self):
        import csv
        with tempfile.TemporaryDirectory() as t:
            root = Path(t)
            d = root / "export_B3"
            d.mkdir()
            (d / "FINAL_EXPORT_DONE.json").write_text('{"setting": "B3"}', encoding="utf-8")
            with (d / "runs.csv").open("w", newline="", encoding="utf-8") as f:
                w = csv.writer(f)
                w.writerow(["trial", "outcome", "goal"])
                for i in range(1, 21):
                    w.writerow([i, "FAILURE" if i == 7 else "SUCCESS", "E5"])
            real = ps.fg.markers
            ps.fg.markers = lambda r, s, k: [d / "FINAL_EXPORT_DONE.json"]
            try:
                runs = [{"trial": k, "plan_run": pr, "goal": "E5", "outcome": "FAILURE" if pr == 10 else "SUCCESS"} for k, pr in enumerate(ps.PLAN_RUNS["B3"], 1)]
                rates, pairs = ps.comparison_rows({("B3", A): {"runs": runs, "dialogs": []}}, root, 1.96)
                self.assertEqual(rates[0]["plan_runs"], "5 7 8 10 11")
                self.assertEqual((rates[0]["S1 successes"], rates[0]["Sunbox final successes (same plan runs)"]), (4, 4))
                p = pairs[0]
                self.assertEqual((p["both_succeed"], p["only_S1_succeeds"], p["only_Sunbox_succeeds"], p["neither"]), (3, 1, 1, 0))
                self.assertEqual(p["plan_runs_failed_in_S1"], "10")
                self.assertEqual(rates[0]["difference_pp (S1 - Sunbox)"], ex.newcombe(4, 5, 4, 5, 1.96)["difference_pp"])
                runs[0]["goal"] = "E1"                                                            # a goal that is not the final plan's goal for that plan run
                with self.assertRaisesRegex(pf.StepFailed, "final plan's goal"):
                    ps.comparison_rows({("B3", A): {"runs": runs, "dialogs": []}}, root, 1.96)
            finally:
                ps.fg.markers = real


class B3Rule(unittest.TestCase):
    """The B3 run choice of AUDIT.md 16.37: from the plan only; A is the start, not a junction."""

    def road(self):
        import hri_control as hc
        return hc.Roadmap(json.loads((ROOT / "configs/v4/roadmap.json").read_text(encoding="utf-8")))

    def test_synthetic_plan(self):
        goals = ["E5", "E3", "E1", "E2"]
        plan = ["run 1 worker 1: A slot 1, x, (0.00, 0.00), LIAR shows LEFT (true FORWARD)",          # liar at A only: not a junction
                "run 2 worker 1: J4 slot 1, x, (0.00, 0.00), LIAR shows LEFT (true FORWARD)",          # J4 is not on A->J1->J3->E3
                "run 3 worker 1: J1 slot 1, x, (0.00, 0.00), LIAR shows LEFT (true FORWARD)",          # J1 is on A->J1->E1
                "run 4 worker 1: J2 slot 1, x, (0.00, 0.00), truthful FORWARD"]
        self.assertEqual(ps.b3_plan_runs(plan, goals, self.road(), n=5), [3])

    def test_the_declared_list_equals_the_rule_on_the_final_b3_plan_when_it_is_present(self):
        import glob
        import os
        found = sorted(glob.glob(os.path.expanduser("~/RobotVisionResults/phase_b_final/trials_final_Task2_B3_2*/session.json")))
        if not found:
            self.skipTest("the final B3 session is not on this machine")
        s = json.loads(Path(found[0]).read_text(encoding="utf-8"))
        self.assertEqual(ps.b3_plan_runs(s["workers_plan"], s["goal_order"], self.road()), ps.PLAN_RUNS["B3"])

    def test_declared_runs(self):
        self.assertEqual(ps.PLAN_RUNS, {"A1": [1, 2, 3, 4, 5], "A3": [1, 2, 3, 4, 5], "B3": [5, 7, 8, 10, 11]})
        self.assertEqual(len(ps.LOOKS) * len(ps.SETTINGS) * ps.RUNS, 60)


class Tables(unittest.TestCase):
    def sessions(self):
        run = lambda i, ok: {"trial": i, "plan_run": i, "goal": "E1", "outcome": "SUCCESS" if ok else "FAILURE", "failure_reason": "" if ok else "wrong_goal", "time_s": 100.0 + i,
                             "stop_gestures_true": 0, "stop_gestures_false": 1 if i == 2 else 0}
        dl = [{"dialog": "1", "truthful": "false", "decision": "rejected_impossible", "outvoted": "false", "withdrawn": "false", "final_branch": "LEFT", "true_branch": "LEFT",
               "branch_read": "RIGHT", "command_shown": "RIGHT", "command_read": "RIGHT"},
              {"dialog": "1", "truthful": "false", "decision": "accepted", "outvoted": "false", "withdrawn": "false", "final_branch": "RIGHT", "true_branch": "LEFT",
               "branch_read": "RIGHT", "command_shown": "RIGHT", "command_read": "RIGHT"},
              {"dialog": "2", "truthful": "true", "decision": "accepted", "outvoted": "false", "withdrawn": "false", "final_branch": "LEFT", "true_branch": "LEFT",
               "branch_read": "FORWARD", "command_shown": "LEFT", "command_read": "FORWARD"}]
        return {("B3", A): {"runs": [run(1, True), run(2, False)], "dialogs": dl}, ("A1", A): {"runs": [run(1, True)], "dialogs": dl[2:]}}

    def test_cells_lies_and_confusions(self):
        sess = self.sessions()
        cells = ps.cell_rows(sess, 1.96)
        b3 = [c for c in cells if c["scene"] == "B3"][0]
        self.assertEqual((b3["character"], b3["n"], b3["successes"], b3["failed_wrong_goal"], b3["stop_episodes_false"], b3["asks"], b3["asks_read_as_shown"]), (A, 2, 1, 1, 1, 3, 2))
        lies = {r["asked"]: r for r in ps.lie_rows(sess)}
        self.assertEqual((lies["all"]["given"], lies["all"]["detected"], lies["all"]["corrected"], lies["all"]["fooled"]), (2, 1, 1, 1))
        self.assertEqual({r["scene"] for r in ps.lie_rows(sess)}, {"B3"})                           # lies are a B3 table only
        with tempfile.TemporaryDirectory() as t:
            ps.confusion_tables(sess, Path(t), {"gesture_labels": ["LEFT", "RIGHT", "FORWARD"], "branch_labels": ["LEFT", "RIGHT", "FORWARD"]})
            names = sorted(p.name for p in Path(t).iterdir())
        self.assertEqual(names, ["s1_e_gesture_confusion.csv", "s1_e_gesture_confusion.md", "s1_f_branch_confusion.csv", "s1_f_branch_confusion.md"])


class AbortReasons(unittest.TestCase):
    def test_rule_order(self):
        frame = lambda persons, raised=False: {"persons": persons, "t": 1.0, "junction": "J1",
                                               "persons_x": None} | ({"persons": [{"reading": {"arms": {"left": {"raised": raised}}}}]} if persons else {})
        ask = lambda shown, read, dec="unclear": {"command_shown": shown, "command_read": read, "decision": dec}
        self.assertEqual(ps.ask_reason(ask("POINT", ""), [frame(False)]), "person_never_detected")
        self.assertEqual(ps.ask_reason(ask("POINT", ""), [frame(True, False)]), "arm_not_raised")
        self.assertEqual(ps.ask_reason(ask("POINT", "NONE"), [frame(True, True)]), "POINT_not_read")
        self.assertEqual(ps.ask_reason(ask("PROCEED", "NONE"), [frame(True, True)]), "PROCEED_not_read")
        self.assertEqual(ps.ask_reason(ask("POINT", "WAIT"), [frame(True, True)]), "read_as_WAIT")
        self.assertEqual(ps.ask_reason(ask("POINT", "POINT", "rejected:arrival"), [frame(True, True)]), "rejected_arrival")
        self.assertEqual(ps.ask_reason(ask("POINT", "POINT", "accepted"), [frame(True, True)]), "accepted")
        self.assertEqual(ps.ask_reason(ask("POINT", "POINT", "unclear"), [frame(True, True)]), "unknown")
        self.assertEqual(ps.ask_reason(ask("POINT", "NONE"), []), "no_frames_logged")         # no logged frame is NOT "no person" (AUDIT 16.39.2)

    def test_rows_only_for_aborted_runs_and_window_on_the_bridge_clock(self):
        """The dialog's t_s is seconds since the run start; the log's t is the bridge clock (here ~300 s later): the window is placed with python_trial asks_log, by serial (AUDIT 16.39.2)."""
        with tempfile.TemporaryDirectory() as t:
            b = Path(t)
            asks_log = [{"junction": "J1", "asks_log": [{"t": 310.0, "serial": 1, "ask": 1}, {"t": 330.0, "serial": 2, "ask": 2}]}]
            (b / "python_trial_002.json").write_text(json.dumps({"abort_reason": "gesture unclear after 2 asks at J1", "junctions": asks_log}), encoding="utf-8")
            person = {"reading": {"arms": {"left": {"raised": True}}}}
            rows = [json.dumps({"trial": 2, "t": 311.0, "junction": "J1", "persons": []}), json.dumps({"trial": 2, "t": 335.0, "junction": "J1", "persons": [person]}),
                    json.dumps({"trial": 1, "t": 311.0, "junction": "J1", "persons": []})]
            (b / "v4_log.jsonl").write_text("\n".join(rows), encoding="utf-8")
            runs = [{"trial": 1, "failure_reason": "", "plan_run": 1}, {"trial": 2, "failure_reason": "aborted", "plan_run": 2}]
            dl = [{"trial": "2", "t_s": "10", "serial": "1", "junction": "J1", "command_shown": "POINT", "command_read": "", "decision": "unclear"},
                  {"trial": "2", "t_s": "30", "serial": "2", "junction": "J1", "command_shown": "POINT", "command_read": "POINT", "decision": "accepted"},
                  {"trial": "2", "t_s": "50", "serial": "3", "junction": "J1", "command_shown": "POINT", "command_read": "", "decision": "unclear"},
                  {"trial": "1", "t_s": "10", "serial": "1", "junction": "J1", "command_shown": "POINT", "command_read": "", "decision": "unclear"}]
            out = ps.abort_ask_rows(runs, dl, b, "A1", A)
        self.assertEqual([o["trial"] for o in out], [2, 2, 2])
        self.assertEqual([(o["frames_in_window"], o["reason"]) for o in out], [(1, "person_never_detected"), (1, "accepted"), (0, "unknown")])
        self.assertEqual(out[0]["run_abort_reason"], "gesture unclear after 2 asks at J1")


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
