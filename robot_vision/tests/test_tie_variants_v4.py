"""The tie-rule variants T0 / T1 / T2 of AUDIT.md 16.22 (2026-11-18). Simulator only; nothing is tuned.

T0 = the current "on" (backtrack off); T1 = + backtrack; T2 = T1 with lie_detection.backtrack_scope "disagreed": a backtrack goes only to a decision junction
at which the accepted answers of the visit named more than one branch. The new key defaults to "any" (= T1), so every existing behaviour is unchanged."""

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import commander_v4 as cm  # noqa: E402
import hri_control_v4 as hv  # noqa: E402
import hri_sim_v4 as sv  # noqa: E402
import report_tie_variants_v4 as rt  # noqa: E402
import run_experiments_ab_v4 as rx  # noqa: E402
from tests.test_lie_detection_v4 import BACKTRACK, NORTH, SECOND, events, run  # noqa: E402

DISAGREED = {**BACKTRACK, "backtrack_scope": "disagreed"}


def controller(detection):
    base, v4 = hv.load_control()
    v4["lie_detection"] = {**v4["lie_detection"], **detection}
    return hv.ControllerV4(base, v4, cm.load_config(), hv.load_roadmap())


class Variants(unittest.TestCase):
    def test_the_three_variants_are_the_declared_ones(self):
        self.assertEqual(rx.TIE_VARIANTS["T0"], sv.DETECTION_ON)
        self.assertEqual(rx.TIE_VARIANTS["T0"]["backtrack"], False)
        self.assertEqual(rx.TIE_VARIANTS["T1"], {**sv.DETECTION_ON, "backtrack": True})
        self.assertEqual(rx.TIE_VARIANTS["T2"], {**sv.DETECTION_ON, "backtrack": True, "backtrack_scope": "disagreed"})

    def test_no_shipped_config_carries_the_new_key_and_the_default_is_any(self):
        self.assertEqual(hv.LIE_DEFAULTS["backtrack_scope"], "any")
        for f in sorted((ROOT / "configs/v4").rglob("*.json")):
            self.assertNotIn("backtrack_scope", json.loads(f.read_text(encoding="utf-8")).get("lie_detection", {}), f.name)
        self.assertEqual(controller({}).ld["backtrack_scope"], "any")
        self.assertEqual(sv.load_scenarios()["detection"]["on"].get("backtrack_scope"), None)

    def test_a_bad_scope_is_refused(self):
        with self.assertRaisesRegex(ValueError, "backtrack_scope"):
            controller({"reject_impossible": True, "backtrack": True, "backtrack_scope": "everywhere"})


class Scope(unittest.TestCase):
    def test_scope_any_is_the_existing_backtrack(self):
        r = run("A3", "E3", [None, "LEFT"], {**BACKTRACK, "backtrack_scope": "any"}, NORTH)
        self.assertEqual((r["outcome"], r["v4"]["route"]), ("SUCCESS", ["A", "J1", "J2", "J1", "J3", "E3"]))
        self.assertEqual(len(events(r, "backtrack")), 1)

    def test_scope_disagreed_does_not_backtrack_to_a_junction_where_the_answers_agreed(self):
        r = run("A3", "E3", [None, "LEFT"], DISAGREED, NORTH)                 # J1 had one answer: nothing disagreed there
        self.assertEqual((r["outcome"], r["failure_reason"]), ("FAILURE", "aborted"))
        self.assertEqual(events(r, "backtrack"), [])
        blocked = events(r, "backtrack_blocked")
        self.assertEqual(len(blocked), 1)
        self.assertIn("did not disagree", blocked[0]["reason"])

    def test_the_junction_record_says_whether_the_answers_disagreed(self):
        c = controller({"second_opinion": True, "reject_impossible": True})
        c.begin(0.0)
        c.node, c.ask_serial = "J1", 4
        c.votes = [{"person_360": 1, "branch": "RIGHT", "serial": 1}, {"person_360": 2, "branch": "LEFT", "serial": 2}, {"person_360": 1, "branch": "RIGHT", "serial": 3}]
        c._decide_go(1.0, "RIGHT", "tie: the first, counted twice")
        self.assertTrue(c.last_choice["disagreed"])
        c.votes = [{"person_360": 1, "branch": "LEFT", "serial": 1}, {"person_360": 2, "branch": "LEFT", "serial": 2}]
        c._decide_go(2.0, "LEFT", "agreed")
        self.assertFalse(c.last_choice["disagreed"])
        c.votes = [{"person_360": 1, "branch": "LEFT", "serial": 1}]
        c._decide_go(3.0, "LEFT", "one answer")
        self.assertFalse(c.last_choice["disagreed"])

    def test_scope_disagreed_backtracks_after_a_disagreement(self):
        c = controller(DISAGREED)
        c.begin(0.0)
        c.node, c.rejections = "J2", ["arrival", "arrival"]
        c.last_choice = {"node": "J1", "branch": "LEFT", "serial": 3, "disagreed": True}
        c.tried = {"J1": {"LEFT"}}
        inp = hv.TickInputV4(time_s=1.0, x=0.0, z=0.0, yaw_deg=0.0)
        self.assertTrue(c._start_backtrack(inp, 1.0))
        self.assertEqual(c.backtrack_target, "J1")
        c2 = controller(DISAGREED)
        c2.begin(0.0)
        c2.node, c2.rejections = "J2", ["arrival", "arrival"]
        c2.last_choice = {"node": "J1", "branch": "LEFT", "serial": 3, "disagreed": False}
        c2.tried = {"J1": {"LEFT"}}
        self.assertFalse(c2._start_backtrack(inp, 1.0))
        self.assertIsNone(c2.backtrack_target)

    def test_a_tie_with_a_lying_first_worker_is_recorded_as_a_disagreement_in_a_whole_run(self):
        sc = sv.scenario_ab("A3", 1, {**SECOND, "reject_impossible": True})
        sc["spec"].lie_script = [None, None, "RIGHT", None, "RIGHT"]
        sc["spec"].layout["people"] = 2
        r = sc["sim"].run("E2")
        goes = [d for d in events(r, "go") if d["node"] == "J1"]
        self.assertTrue(goes and len({v["branch"] for v in goes[0]["votes"]}) > 1, goes)


class RunnerOption(unittest.TestCase):
    def test_tie_variant_defaults_to_the_current_on(self):
        src = (ROOT / "run_experiments_ab_v4.py").read_text(encoding="utf-8")
        self.assertIn('"--tie-variant", choices=list(TIE_VARIANTS), default="T0"', src)
        self.assertIn('SETTINGS["on"] = dict(TIE_VARIANTS[a.tie_variant])', src)


def _row(success, backtracks=0, sig=("a",), exp="B3", setting="on"):
    return {"experiment": exp, "setting": setting, "runs": 20, "success": success, "wrong_goal": 7, "aborted": 1, "collisions": 0, "longest_successful_s": 100.0,
            "backtracks": backtracks, "runs_with_backtrack": int(backtracks > 0), "signature": list(sig), "failures": {},
            "lies": {"first": {"fooled": 3, "caught_by_reject_impossible": 2}, "later": {"fooled": 1}}}


class Report(unittest.TestCase):
    def test_cell_and_checks(self):
        self.assertIn("fooled 3 first / 1 later, caught by reject_impossible 2", rt.cell(_row(11)))
        self.assertIn("backtracks 2 (1 runs)", rt.cell(_row(11, 2)))
        data = {"T0": {("A3", "on"): _row(20, exp="A3"), ("B3", "off"): _row(10, setting="off")},
                "T1": {("A3", "on"): _row(19, 1, exp="A3"), ("B3", "off"): _row(10, setting="off")},
                "T2": {("A3", "on"): _row(20, exp="A3"), ("B3", "off"): _row(10, sig=("b",), setting="off")}}
        c = rt.checks(data)
        self.assertFalse(c["off_rows_identical"])
        self.assertEqual(c["A_success_lost_vs_T0"], {"T1": {"A3 on": 1}, "T2": {}})
        self.assertEqual(c["A_backtracks"], {"T1": {"A3 on": 1}, "T2": {}})


if __name__ == "__main__":
    unittest.main()
