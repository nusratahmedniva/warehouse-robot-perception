"""report_rows_ab_v4.py (AUDIT.md 16.21.2): the per-row report and the lie split, on synthetic dialogue rows and on one real simulated session."""

import csv
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import report_rows_ab_v4 as rp  # noqa: E402


def d(run, junction, dialog, worker, truthful, decision="accepted", outvoted=False, withdrawn=False, read="", final="", true="LEFT", serial=None, visit=1, session="s1"):
    return {"experiment": "B3", "session": session, "run": str(run), "junction": junction, "visit": str(visit), "dialog": str(dialog), "worker": str(worker), "truthful": str(truthful).lower(),   # the real CSVs write true / false
            "decision": decision, "outvoted": str(outvoted).lower(), "withdrawn": str(withdrawn).lower(), "branch_read": read, "final_branch": final, "true_branch": true, "serial": str(serial or dialog)}


class Classify(unittest.TestCase):
    def test_the_five_outcomes(self):
        self.assertEqual(rp.classify(d(1, "J1", 1, 1, False, decision="rejected:no_branch")), "caught_by_reject_impossible")
        self.assertEqual(rp.classify(d(1, "J1", 2, 2, False, outvoted=True)), "outvoted")
        self.assertEqual(rp.classify(d(1, "J1", 2, 2, False, withdrawn=True)), "withdrawn")
        self.assertEqual(rp.classify(d(1, "J1", 1, 1, False, read="RIGHT", final="RIGHT")), "fooled")
        self.assertEqual(rp.classify(d(1, "J1", 1, 1, False, read="LEFT", final="LEFT")), "neither")            # read as the true branch (mirror ambiguity)
        self.assertEqual(rp.classify(d(1, "J1", 1, 1, False, decision="unclear")), "neither")


class Split(unittest.TestCase):
    def test_first_and_later_askers_and_the_tie_re_ask(self):
        rows = [d(1, "J1", 1, 1, False, read="RIGHT", final="RIGHT"),               # the first worker lies and is followed (tie: asked again, counted twice)
                d(1, "J1", 2, 2, True, read="LEFT", final="RIGHT"),
                d(1, "J1", 3, 1, False, read="RIGHT", final="RIGHT", serial=3),       # the re-ask of the first worker is the first asker again
                d(2, "J1", 1, 1, True, read="LEFT", final="LEFT"),
                d(2, "J1", 2, 2, False, outvoted=True),                              # a later-asked liar, outvoted
                d(3, "J2", 1, 2, False, decision="rejected:wall")]                   # worker numbering is per node; here the first-asked is worker 2
        sp = rp.lie_split(rows)
        self.assertEqual(dict(sp["first"]), {"fooled": 2, "caught_by_reject_impossible": 1})
        self.assertEqual(dict(sp["later"]), {"outvoted": 1})
        self.assertEqual(sp["lying_asks"], 4)

    def test_visits_are_separate(self):
        rows = [d(1, "J1", 1, 1, True), d(1, "J1", 2, 2, False, read="RIGHT", final="RIGHT"), d(1, "J2", 1, 2, False, read="RIGHT", final="RIGHT", visit=1)]
        sp = rp.lie_split(rows)
        self.assertEqual((dict(sp["later"]), dict(sp["first"])), ({"fooled": 1}, {"fooled": 1}))


class FinalRows(unittest.TestCase):
    def test_the_thirteen_settings_give_twelve_rows_of_the_sixteen(self):
        f = rp.final_rows()
        self.assertEqual(len(f), 12)                                               # the 13th final setting, A2 left, is not a row of the 16-row table
        self.assertEqual({e for e, s in f if s == "on"}, {"A1", "A2", "A3", "A4", "B1", "B2", "B3", "B4"})
        self.assertEqual({e for e, s in f if s == "off"}, {"B1", "B2", "B3", "B4"})


class OnARealSession(unittest.TestCase):
    def test_the_split_agrees_with_runs_csv_on_simulated_b3(self):
        import export_csv_v4 as ex  # noqa: F401  (the same definitions)
        import hri_sim_v4 as sv
        sys.path.insert(0, str(ROOT / "tests"))
        import test_export_csv_v4 as te
        results = [sv.run_scenario("B3", s, sv.DETECTION_ON) for s in range(1, 7)]
        tmp = Path(tempfile.mkdtemp())
        u, b = te.session(results, tmp, "B3_on")
        import gesture_data as gd
        import hri_eval_dev_v4 as ev
        runs = ev.load_sessions([(u, b)], gd.load_config())
        rr, dr = ex.build_tables(runs)
        cell = lambda v: "" if v is None else (str(v).lower() if isinstance(v, bool) else str(v))             # as the csv writer does
        rr_s = [{k: cell(v) for k, v in r.items()} for r in rr]
        dr_s = [{k: cell(v) for k, v in r.items()} for r in dr]
        for r in rr_s:
            r["setting"] = "on"
        out = rp.row_summary(rr_s, dr_s, "B3", "on")
        self.assertGreater(out["lies"]["lying_asks"], 0)                                                       # the split is not trivially empty
        self.assertTrue(out["lies"]["consistent_with_runs_csv"], out["lies"])
        self.assertEqual(out["runs"], 6)


if __name__ == "__main__":
    unittest.main()
