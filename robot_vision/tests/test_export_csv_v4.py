"""export_csv_v4.py and run_experiments_ab_v4.py (AUDIT.md section 16): runs.csv and dialogs.csv from simulated session folders, the
configurable columns, the lie counts (given / detected / corrected / fooled), the one-row-per-ask rule and the rule that inference
code never imports the exporter. Simulator sessions only; no data, no models."""

import ast
import csv
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))

import commander_v4 as cm  # noqa: E402
import data_splits_v4 as ds  # noqa: E402
import export_csv_v4 as ex  # noqa: E402
import hri_control_v4 as hv  # noqa: E402
import gesture_data as gd  # noqa: E402
import hri_eval_dev_v4 as ev  # noqa: E402
import hri_sim_v4 as sv  # noqa: E402
import run_experiments_ab_v4 as ab  # noqa: E402
import test_lie_detection_v4 as T  # noqa: E402

CFG = ex.load_config()


def session(results, tmp, name, extra=None):
    return sv.export_session(results, tmp, True, seed=1, name=name, road_cfg=results[0]["road_cfg"], v4_override=results[0]["v4_config"],
                             session_extra={"experiment": results[0].get("experiment"), "set": results[0].get("set"),
                                            "lie_probability": results[0].get("lie_probability"), **(extra or {})})


THREE_SLOTS = [{"before_m": 3.0, "right_m": -2.0}, {"before_m": 5.5, "right_m": 2.0}, {"before_m": 6.0, "right_m": -2.0}]   # 16.13 slots: three voters (the layout has two since 16.21)


def scripted(name, goal, script, detection, layout=None, xcheck=False, people=None):
    """A scripted run packaged like run_scenario's result so that export_session can write it."""
    sc = sv.scenario_ab(name, 1, detection)
    sc["spec"].lie_script = script
    if layout is not None:
        sc["spec"].layout = layout
    if people is not None:
        sc["spec"].layout["people"] = people
        sc["spec"].layout.pop("people_by_node", None)
        if people > 2 and "junction_slots" in sc["spec"].layout:
            sc["spec"].layout["junction_slots"] = [dict(x) for x in THREE_SLOTS]
    if xcheck:
        sc["sim"].g.crosscheck_accuracy = 1.0
        sc["sim"].c.v4["dialog"]["use_hand_crosscheck_as_tiebreak"] = True
    r = sc["sim"].run(goal)
    r.update({k: sc[k] for k in ("experiment", "set", "seed", "lie_probability", "optimal_m")})
    r["v4_config"], r["road_cfg"] = sc["v4"], sc["road"].cfg
    return r


def tables(results, name="t"):
    tmp = Path(tempfile.mkdtemp())
    u, b = session(results, tmp, name)
    runs = ev.load_sessions([(u, b)], gd.load_config())
    return ex.build_tables(runs), runs


class Columns(unittest.TestCase):
    def test_the_config_names_known_fields_only(self):
        ex.check_columns(CFG)
        self.assertEqual(set(RUN for RUN in (c["field"] for c in CFG["runs"])) - set(ex.RUN_FIELDS), set())

    def test_the_plans_columns_come_first_in_the_plans_order(self):
        runs = [c["field"] for c in CFG["runs"]]
        self.assertEqual(runs[:12], ["experiment", "set", "seed", "looks", "route", "goal", "outcome", "failure_reason", "time_s", "trail_m",
                                     "optimal_m", "trail_over_optimal"])
        self.assertEqual(runs[12:18], ["stops", "collisions", "lies_given", "lies_detected", "lies_corrected", "lies_fooled"])
        d = [c["field"] for c in CFG["dialogs"]]
        self.assertEqual(d[:10], ["experiment", "set", "seed", "junction", "worker", "look", "command_shown", "truthful", "command_read", "correct"])
        self.assertEqual(d[10:13], ["time_to_read_s", "distance_m", "decision"])

    def test_an_unknown_or_repeated_field_is_refused_with_the_known_ones(self):
        with self.assertRaisesRegex(SystemExit, "unknown field.*nonsense.*known fields"):
            ex.check_columns({"runs": [{"field": "nonsense"}], "dialogs": []})
        with self.assertRaisesRegex(SystemExit, "listed twice"):
            ex.check_columns({"runs": [{"field": "set"}, {"field": "set"}], "dialogs": []})

    def test_every_known_field_is_produced_and_defined(self):
        (rr, dr), _ = tables([sv.run_scenario("B3", 1, sv.DETECTION_ON)])
        self.assertEqual(set(ex.RUN_FIELDS) - set(rr[0]), set())
        self.assertEqual(set(ex.DIALOG_FIELDS) - set(dr[0]), set())
        for k in ("lies_given", "lies_detected", "lies_corrected", "lies_fooled", "trail_over_optimal", "correct"):
            self.assertTrue(ex.RUN_FIELDS.get(k) or ex.DIALOG_FIELDS.get(k), k)                 # the ones that need a definition have one

    def test_headers_order_and_formatting_follow_the_config(self):
        (rr, _), _ = tables([sv.run_scenario("A3", 1, sv.DETECTION_OFF)])
        cols = [{"field": "outcome", "header": "result"}, {"field": "experiment"}, {"field": "backtrack_on"}, {"field": "trail_source"}]
        buf = Path(tempfile.mkdtemp()) / "x.csv"
        ex.write_csv(buf, rr, cols)
        rows = list(csv.reader(buf.read_text(encoding="utf-8").splitlines()))
        self.assertEqual(rows[0], ["result", "experiment", "backtrack_on", "trail_source"])
        self.assertEqual(rows[1], ["SUCCESS", "A3", "false", "road_route"])                # booleans are true / false
        ex.write_csv(buf, [{"outcome": None}], [{"field": "outcome"}], empty="n/a")
        self.assertEqual(buf.read_text(encoding="utf-8").splitlines()[1], "n/a")


class Tables(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.results = [sv.run_scenario("B3", s, sv.DETECTION_ON) for s in range(1, 9)]
        (cls.rr, cls.dr), cls.runs = tables(cls.results, "B3_on")

    def test_one_row_per_run_and_one_row_per_ask(self):
        self.assertEqual(len(self.rr), 8)
        asks = sum(len(j.get("asks_log", [])) for run in self.runs for j in run.junctions)
        self.assertEqual(len(self.dr), asks)
        self.assertEqual(sorted({r["serial"] for r in self.dr if r["run"] == self.rr[0]["run"]}),
                         list(range(1, 1 + sum(r["run"] == self.rr[0]["run"] for r in self.dr))))
        self.assertEqual([r["asks"] for r in self.rr], [sum(d["run"] == r["run"] for d in self.dr) for r in self.rr])

    def test_run_row_facts_come_from_the_session(self):
        for res, r in zip(self.results, self.rr):
            self.assertEqual((r["experiment"], r["set"], r["seed"], r["goal"], r["outcome"]), ("B3", "B", res["seed"], res["goal"], res["outcome"]))
            self.assertEqual(r["route"], ">".join(res["v4"]["route"]))
            self.assertEqual((r["second_opinion_on"], r["reject_impossible_on"], r["backtrack_on"]), (True, True, False))   # 'on' = a + b, backtrack off
            self.assertAlmostEqual(r["optimal_m"], res["optimal_m"])
            self.assertEqual(r["trail_source"], "road_route")
            self.assertEqual(r["looks"], "sunbox_f1+sunbox_m1")
            self.assertEqual(r["lie_probability"], 0.2)

    def test_lies_given_equal_the_lying_gestures_the_simulator_staged(self):
        for res, r in zip(self.results, self.rr):
            self.assertEqual(r["lies_given"], sum(not g["truthful"] for g in res["gestures"]), r["run"])

    def test_the_lie_counts_are_consistent(self):
        for r in self.rr:
            self.assertLessEqual(r["lies_detected"], r["lies_given"])
            self.assertLessEqual(r["lies_corrected"], r["lies_detected"])
            self.assertLessEqual(r["lies_detected"] + r["lies_fooled"], r["lies_given"])
        self.assertGreater(sum(r["lies_given"] for r in self.rr), 3)

    def test_every_ask_has_a_decision_and_the_truthful_flag(self):
        for d in self.dr:
            self.assertTrue(d["decision"] == "accepted" or d["decision"] == "unclear" or d["decision"].startswith("rejected:"), d["decision"])
            self.assertIn(d["truthful"], (True, False))
            self.assertIn(d["command_shown"], ("POINT", "PROCEED", "WAIT", "STOP", "NONE"))
        self.assertGreaterEqual(len([d for d in self.dr if d["truthful"] is False]), 1)

    def test_worker_and_look_are_those_of_the_ask(self):
        for d in self.dr:
            self.assertIn(d["worker"], (1, 2, 3))                           # 3 workers at J1 since 16.12
            self.assertEqual(d["look"], {1: "sunbox_m1", 2: "sunbox_f1", 3: "sunbox_m1"}[d["worker"]])

    def test_a_truthful_accepted_ask_reads_the_true_branch(self):
        ok = [d for d in self.dr if d["truthful"] and d["decision"] == "accepted" and d["true_branch"] in ("LEFT", "FORWARD", "RIGHT")]
        self.assertTrue(ok)
        for d in ok:
            self.assertEqual((d["correct_branch"], d["branch_read"]), (True, d["true_branch"]))

    def test_times_and_distances_are_present_where_an_answer_exists(self):
        for d in self.dr:
            if d["decision"] != "unclear":
                self.assertGreater(d["time_to_read_s"], 0.5)
            # in the simulator the truth's commander is worker 1, so for a second opinion this is the distance to worker 1, not to the person asked (as before); with the clearance
            # layout (AUDIT.md 16.20) the second and third workers stand 4.5 to 5.0 m ahead of the node and the robot asks them from there: 7.9 m in these runs (16.13.2: 4.0 -> 5.0).
            # The bound is the ask zone plus the worker distance: 5.5 m + 6.5 m
            self.assertTrue(1.0 < d["distance_m"] < 12.0, d["distance_m"])
        self.assertEqual(len({(d["run"], d["serial"]) for d in self.dr}), len(self.dr))


class DecisionsAreVisible(unittest.TestCase):
    def test_a_rejected_lie(self):
        r = scripted("A3", "E3", [None, None, "FORWARD"], T.REJECT, T.WALL_AT_J3, xcheck=True)
        (rr, dr), _ = tables([r])
        lie = [d for d in dr if d["truthful"] is False]
        self.assertEqual(len(lie), 1)
        self.assertEqual((lie[0]["decision"], lie[0]["junction"], lie[0]["direction_shown"], lie[0]["branch_shown"]),
                         ("rejected:no_branch", "J3", "FORWARD", "none"))
        self.assertEqual((rr[0]["lies_given"], rr[0]["lies_detected"], rr[0]["lies_corrected"], rr[0]["lies_fooled"]), (1, 1, 1, 0))
        self.assertEqual(rr[0]["rejections"], 1)
        self.assertIsNone(lie[0]["correct_branch"])                                       # nothing was read: not evaluated, not a guess
        self.assertTrue(lie[0]["correct"])                                                # the reader did read the POINT that was shown

    def test_an_outvoted_lie(self):
        r = scripted("A3", "E2", [None, None, None, "RIGHT"], T.SECOND, xcheck=True, people=3)   # J1: p1 LEFT, p2 lies RIGHT, p3 LEFT
        (rr, dr), _ = tables([r])
        lie = [d for d in dr if d["truthful"] is False]
        self.assertEqual((len(lie), lie[0]["junction"], lie[0]["outvoted"], lie[0]["decision"], lie[0]["final_branch"]),
                         (1, "J1", True, "accepted", "LEFT"))
        self.assertEqual((rr[0]["lies_given"], rr[0]["lies_detected"], rr[0]["lies_corrected"], rr[0]["lies_fooled"]), (1, 1, 1, 0))
        self.assertEqual(r["outcome"], "SUCCESS")

    def test_a_lie_outvoted_at_the_tie_by_asking_the_first_person_again(self):
        r = scripted("A3", "E2", [None, None, "RIGHT"], T.SECOND, xcheck=True, people=2)
        (rr, dr), _ = tables([r])
        self.assertEqual((rr[0]["lies_given"], rr[0]["lies_detected"], rr[0]["lies_corrected"], rr[0]["lies_fooled"]), (1, 1, 1, 0))
        self.assertEqual([d["dialog"] for d in dr if d["junction"] == "J1"], [1, 2, 3])        # first, second, the first asked again

    def test_a_withdrawn_lie_is_detected_and_corrected_by_the_backtrack(self):
        r = scripted("A3", "E3", [None, "LEFT"], T.BACKTRACK, T.NORTH)
        self.assertEqual(r["outcome"], "SUCCESS")
        (rr, dr), _ = tables([r])
        lie = [d for d in dr if d["truthful"] is False]
        self.assertEqual((len(lie), lie[0]["junction"], lie[0]["withdrawn"]), (1, "J1", True))
        self.assertEqual((rr[0]["lies_given"], rr[0]["lies_detected"], rr[0]["lies_corrected"], rr[0]["lies_fooled"]), (1, 1, 1, 0))
        self.assertEqual((rr[0]["backtracks"], rr[0]["route"]), (1, "A>J1>J2>J1>J3>E3"))
        self.assertEqual([d["visit"] for d in dr if d["junction"] == "J1"], [1, 2])         # the return to J1 is a second visit

    def test_a_lie_the_robot_acts_on_is_fooled(self):
        r = scripted("A3", "E3", [None, "LEFT"], T.OFF, T.NORTH)                          # no detection: follows the lie to J2 and aborts there
        (rr, dr), _ = tables([r])
        self.assertEqual((rr[0]["lies_given"], rr[0]["lies_detected"], rr[0]["lies_fooled"]), (1, 0, 1))
        self.assertEqual(rr[0]["outcome"], "FAILURE")

    def test_the_two_view_ambiguity_can_hide_a_lie_so_it_is_given_only(self):
        # B3 seed 3 with detection off: lies that were read as nothing or as the right branch are neither detected nor fooled
        (rr, _), _ = tables([sv.run_scenario("B3", s, sv.DETECTION_OFF) for s in range(1, 8)])
        for r in rr:
            self.assertLessEqual(r["lies_detected"] + r["lies_fooled"], r["lies_given"])
            self.assertEqual(r["lies_detected"], 0)                                       # nothing is detected with the switches off

    def test_set_a_has_no_lies(self):
        (rr, dr), _ = tables([sv.run_scenario("A3", s, sv.DETECTION_ON) for s in (1, 2)])
        self.assertEqual([(r["lies_given"], r["lies_detected"], r["lies_fooled"]) for r in rr], [(0, 0, 0)] * 2)
        self.assertTrue(all(d["truthful"] is True for d in dr))


class ArrivalMirror(unittest.TestCase):
    def test_the_setting_label_and_the_arrival_reading_are_exported(self):
        res = [sv.run_scenario("B3", s, sv.DETECTION_ON) for s in range(1, 6)]
        tmp = Path(tempfile.mkdtemp())
        u, b = session(res, tmp, "B3_on", {"lie_detection": "on"})
        runs = ev.load_sessions([(u, b)], gd.load_config())
        rr, dr = ex.build_tables(runs)
        self.assertEqual({r["setting"] for r in rr}, {"on"})
        self.assertEqual(ab.detection_label(rr[0]), "on")
        self.assertTrue(any(d["arrival_candidate"] for d in dr))                       # the mirror reading is the arrival road in some asks
        self.assertTrue(all(d["arrival_candidate"] in (True, False, None) for d in dr))
        rows = ab.arrival_mirror_report(rr, dr)["rows"]
        self.assertEqual(rows[0]["experiment"], "B3")
        self.assertEqual(rows[0]["back_shown"], rows[0]["back_read_as_a_branch"] + rows[0]["back_rejected"] + rows[0]["back_unclear"])
        self.assertEqual(rows[0]["accepted_with_arrival_reading"], rows[0]["of_which_truthful_and_correct"] + rows[0]["of_which_wrong_or_lie"])

class OlderSessions(unittest.TestCase):
    def test_a_session_without_the_truthful_field_leaves_the_lie_columns_empty(self):
        import golden_sim_v4 as golden
        r = golden.run("E2", road="configs/v4/roadmap.json", spec=sv.SceneSpec(proceed_forward=True))     # no experiment, no lies recorded
        tmp = Path(tempfile.mkdtemp())
        u, b = sv.export_session([r], tmp, True, seed=1, name="old")
        runs = ev.load_sessions([(u, b)], gd.load_config())
        rr, dr = ex.build_tables(runs)
        self.assertEqual({(x["lies_given"], x["lies_detected"], x["lies_corrected"], x["lies_fooled"]) for x in rr}, {(None,) * 4})
        self.assertTrue(dr and all(d["truthful"] is None for d in dr))
        self.assertEqual((rr[0]["experiment"], rr[0]["set"], rr[0]["lie_probability"]), (None, None, None))
        self.assertEqual(rr[0]["outcome"], "SUCCESS")


class Runner(unittest.TestCase):
    def test_a_small_run_writes_sessions_and_a_table(self):
        tmp = Path(tempfile.mkdtemp())
        pairs = ab.run_all(tmp, 2, 270.0, ("A1", "B2"))
        self.assertEqual(len(pairs), 4)                                                    # two experiments x detection off / on
        runs = ev.load_sessions(pairs, gd.load_config())
        rr, dr = ex.build_tables(runs)
        table = ab.summarise(rr)
        self.assertEqual([(t["experiment"], t["detection"], t["runs"]) for t in table],
                         [("A1", "off", 2), ("A1", "on", 2), ("B2", "off", 2), ("B2", "on", 2)])
        md = ab.markdown(table, {"runs": 2, "timeout_s": 270.0, "first_seed": 1})
        self.assertIn("SIMULATOR", md)
        self.assertIn("| A1 | off | 2 |", md)
        for t in table:
            lo, hi = t["success_ci95"]
            self.assertTrue(lo <= t["success_rate"] <= hi)

    def test_the_same_seeds_give_the_same_table(self):
        a = [sv.run_scenario("B4", s, sv.DETECTION_ON) for s in (1, 2, 3)]
        b = [sv.run_scenario("B4", s, sv.DETECTION_ON) for s in (1, 2, 3)]
        self.assertEqual(ab.summarise(tables(a)[0][0]), ab.summarise(tables(b)[0][0]))


class NewColumns(unittest.TestCase):
    """AUDIT.md 16.31.6 decision 2: dialogs.csv clip, look_role, clip_role; runs.csv stop_gestures_true / _false, resume_from_run, resume_of,
    interrupted. Simulator sessions; the roles come from data_splits.json."""

    @classmethod
    def setUpClass(cls):
        cls.results = [sv.run_scenario("B3", s_, sv.DETECTION_ON) for s_ in range(1, 3)]
        (cls.rr, cls.dr), cls.runs = tables(cls.results, "cols")
        cls.splits = ds.load()

    def test_the_columns_are_known_defined_and_appended_before_the_identifiers(self):
        for f in ("stop_gestures_true", "stop_gestures_false", "resume_from_run", "resume_of", "interrupted"):
            self.assertIn(f, ex.RUN_FIELDS)
        for f in ("clip", "look_role", "clip_role"):
            self.assertIn(f, ex.DIALOG_FIELDS)
        runs = [c["field"] for c in CFG["runs"]]
        dialogs = [c["field"] for c in CFG["dialogs"]]
        self.assertEqual(runs[runs.index("watchdog_stops") + 1:runs.index("watchdog_stops") + 6],
                         ["stop_gestures_true", "stop_gestures_false", "resume_from_run", "resume_of", "interrupted"])
        self.assertEqual(runs[-3:], ["session", "run", "trial"])
        self.assertEqual(dialogs[dialogs.index("t_s") + 1:dialogs.index("t_s") + 4], ["clip", "look_role", "clip_role"])
        self.assertEqual(dialogs[-3:], ["session", "run", "trial"])

    def test_the_clip_and_the_roles_of_every_ask(self):
        self.assertTrue(self.dr)
        for d in self.dr:
            if d["command_shown"] in ("POINT", "PROCEED", "WAIT", "STOP"):
                self.assertTrue(d["clip"], d)
                self.assertEqual(d["clip_role"], self.splits["clips"][d["clip"]])
            else:
                self.assertEqual((d["clip"], d["clip_role"]), ("", None))                  # NONE: nobody gestures, no clip
            self.assertEqual(d["look_role"], self.splits["looks"][d["look"]])

    def test_roles_follow_data_splits_and_an_unlisted_name_leaves_the_cell_empty(self):
        sp = {**self.splits, "looks": {**self.splits["looks"], "sunbox_m1": "test"},
              "clips": {k: v for k, v in self.splits["clips"].items() if k != "point_mixamo_01"}}
        _, dr = ex.build_tables(self.runs, splits=sp)
        point = [d for d in dr if d["clip"] == "point_mixamo_01"]
        self.assertTrue(point)
        self.assertTrue(all(d["clip_role"] is None for d in point))                          # not listed: empty, never guessed
        self.assertTrue(all(d["look_role"] == "test" for d in dr if d["look"] == "sunbox_m1"))
        for f in ("clip", "look_role", "clip_role"):                                        # and the CSV cells
            self.assertEqual(ex._fmt(point[0][f]), point[0][f] or "")

    def test_without_the_resume_keys_the_resume_columns_are_empty(self):
        for r in self.rr:
            self.assertEqual((r["resume_from_run"], r["resume_of"], r["interrupted"]), (None, None, None))

    def test_a_resumed_session_names_its_start_and_marks_the_interrupted_run(self):
        tmp = Path(tempfile.mkdtemp())
        u, b = session(self.results, tmp, "resumed", extra={"resume_from_run": 2, "resume_of": "trials_part1", "start_run": 2})
        runs = ev.load_sessions([(u, b)], gd.load_config())
        rr, _ = ex.build_tables(runs)
        self.assertEqual([(r["trial"], r["resume_from_run"], r["resume_of"], r["interrupted"]) for r in rr],
                         [(1, 2, "trials_part1", False), (2, 2, "trials_part1", True)])
        self.assertEqual([ex._fmt(r["interrupted"]) for r in rr], ["false", "true"])

    def test_a_non_integer_resume_key_is_not_a_resume(self):
        tmp = Path(tempfile.mkdtemp())
        u, b = session(self.results, tmp, "odd", extra={"resume_from_run": "2", "resume_of": "x"})
        rr, _ = ex.build_tables(ev.load_sessions([(u, b)], gd.load_config()))
        self.assertEqual({(r["resume_from_run"], r["resume_of"], r["interrupted"]) for r in rr}, {(None, None, None)})


class StopGestureSplit(unittest.TestCase):
    """AUDIT.md 16.31.6: accepted STOP gesture episodes of a run, split by truth (the definitions of finals_v4/step5_report.py, 16.28)."""
    PHASES = ["gesturing", "holding"]

    @staticmethod
    def truth(*rows):
        from types import SimpleNamespace
        return [SimpleNamespace(time_s=t, worker_id=w, true_command=c, phase=ph) for t, w, c, ph in rows]

    @staticmethod
    def decisions(*rows):
        return [{"trial": str(tr), "time_s": str(t), "safety": s} for tr, t, s in rows]

    def run(self, truth, trial=1):
        from types import SimpleNamespace
        return SimpleNamespace(trial=trial, truth=truth)

    def test_a_true_and_a_false_episode(self):
        run = self.run(self.truth((0.0, 1, "NONE", "idle"), (5.0, 1, "STOP", "gesturing"), (9.0, 1, "NONE", "idle"), (20.0, 2, "PROCEED", "holding")))
        dec = self.decisions((1, 4.0, ""), (1, 6.0, "STOP gesture"), (1, 6.1, "STOP gesture"), (1, 7.0, ""), (1, 21.0, "STOP gesture"))
        self.assertEqual(ex.stop_gestures(run, dec, self.PHASES), (1, 1))             # the first: worker 1 showed STOP; the second: only PROCEED

    def test_consecutive_rows_are_one_episode_and_a_gap_or_another_trial_breaks_it(self):
        run = self.run(self.truth((0.0, 1, "STOP", "holding")))
        dec = self.decisions((1, 1.0, "STOP gesture"), (1, 1.1, "STOP gesture"), (1, 1.2, ""), (1, 1.3, "STOP gesture"), (2, 1.4, "STOP gesture"),
                             (2, 1.5, "STOP gesture"))
        self.assertEqual(ex.stop_gestures(run, dec, self.PHASES), (2, 0))             # two episodes of trial 1; trial 2's are not this run's
        self.assertEqual(ex.stop_gestures(self.run(run.truth, trial=2), dec, self.PHASES), (1, 0))
        dec = self.decisions((1, 1.0, "STOP gesture"), (2, 1.1, "STOP gesture"), (1, 1.2, "STOP gesture"))
        self.assertEqual(ex.stop_gestures(run, dec, self.PHASES), (2, 0))             # a row of another trial between ends an episode

    def test_the_latest_truth_row_and_the_phase_decide(self):
        run = self.run(self.truth((0.0, 1, "STOP", "gesturing"), (2.0, 1, "STOP", "returning"), (3.0, 1, "NONE", "idle")))
        self.assertEqual(ex.stop_gestures(run, self.decisions((1, 1.0, "STOP gesture")), self.PHASES), (1, 0))
        self.assertEqual(ex.stop_gestures(run, self.decisions((1, 2.5, "STOP gesture")), self.PHASES), (0, 1))   # STOP but the hand is returning
        self.assertEqual(ex.stop_gestures(run, self.decisions((1, 3.5, "STOP gesture")), self.PHASES), (0, 1))   # a later NONE row
        self.assertEqual(ex.stop_gestures(run, self.decisions((1, -1.0, "STOP gesture")), self.PHASES), (0, 1))  # before any truth row

    def test_any_worker_showing_stop_makes_it_true(self):
        run = self.run(self.truth((0.0, 1, "POINT", "holding"), (0.0, 2, "STOP", "holding")))
        self.assertEqual(ex.stop_gestures(run, self.decisions((1, 1.0, "STOP gesture")), self.PHASES), (1, 0))

    def test_no_episode_is_zero_and_no_usable_decisions_csv_is_not_evaluated(self):
        run = self.run(self.truth((0.0, 1, "STOP", "holding")))
        self.assertEqual(ex.stop_gestures(run, self.decisions((1, 1.0, "")), self.PHASES), (0, 0))
        self.assertEqual(ex.stop_gestures(run, None, self.PHASES), (None, None))

    def test_read_decisions_needs_the_safety_column(self):
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            self.assertIsNone(ex.read_decisions(d))                                       # no file
            (d / "decisions.csv").write_text("trial,time_s,rtt_ms\n1,0.1,0.5\n", encoding="utf-8")
            self.assertIsNone(ex.read_decisions(d))                                       # no safety column (the simulator's file)
            (d / "decisions.csv").write_text("trial,time_s,safety\n1,0.1,STOP gesture\n", encoding="utf-8")
            self.assertEqual(ex.read_decisions(d), [{"trial": "1", "time_s": "0.1", "safety": "STOP gesture"}])

    def test_the_run_row_uses_the_bridge_decisions_and_is_empty_without_them(self):
        results = [sv.run_scenario("B3", 1, sv.DETECTION_ON)]
        tmp = Path(tempfile.mkdtemp())
        u, b = session(results, tmp, "stops")
        runs = ev.load_sessions([(u, b)], gd.load_config())
        rr, _ = ex.build_tables(runs)
        self.assertEqual((rr[0]["stop_gestures_true"], rr[0]["stop_gestures_false"]), (None, None))     # the simulator's decisions.csv has no safety column
        # a real-shaped file: one STOP gesture episode while the worker holds a POINT (nobody shows STOP): false
        hold = next(t for t in runs[0].truth if t.true_command == "POINT" and t.phase == "holding")
        (b / "decisions.csv").write_text(f"trial,time_s,safety\n1,{hold.time_s + 0.01},STOP gesture\n1,{hold.time_s + 0.11},STOP gesture\n", encoding="utf-8")
        rr, _ = ex.build_tables(runs)
        self.assertEqual((rr[0]["stop_gestures_true"], rr[0]["stop_gestures_false"]), (0, 1))
        self.assertEqual([ex._fmt(rr[0][k]) for k in ("stop_gestures_true", "stop_gestures_false")], ["0", "1"])


class Isolation(unittest.TestCase):
    def test_inference_code_never_imports_the_exporter_or_the_runner(self):
        # hri_eval_final_v4.py is evaluation code: since 2026-11-14 (AUDIT.md 16.15) it takes the experiment numbers from the exporter.
        # The rule is unchanged for every other file (inference code, the controller, the server).
        offenders = []
        for p in ROOT.rglob("*.py"):
            rel = p.relative_to(ROOT)
            if ".venv" in rel.parts or rel.parts[0] == "tests" or rel.name in ("export_csv_v4.py", "run_experiments_ab_v4.py", "hri_eval_final_v4.py",
                                                                                                 "process_final_zip_v4.py", "process_avatar_zip_v4.py"):   # the Phase B runbooks (AUDIT.md 16.33) are evaluation code
                continue
            tree = ast.parse(p.read_text(encoding="utf-8"))
            mods = {a.name.split(".")[0] for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names}
            mods |= {n.module.split(".")[0] for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) and n.module}
            if mods & {"export_csv_v4", "run_experiments_ab_v4"}:
                offenders.append(str(rel))
        self.assertEqual(offenders, [])

    def test_the_controller_and_the_simulator_never_import_evaluation_code(self):
        for name in ("hri_control_v4.py", "hri_sim_v4.py"):
            tree = ast.parse((ROOT / name).read_text(encoding="utf-8"))
            mods = {a.name.split(".")[0] for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names}
            mods |= {n.module.split(".")[0] for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) and n.module}
            self.assertFalse(mods & {"export_csv_v4", "gesture_data", "gt_path", "hri_eval_dev_v4", "run_experiments_ab_v4"}, name)


if __name__ == "__main__":
    unittest.main()
