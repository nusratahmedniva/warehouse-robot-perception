"""AUDIT.md 16.35: the pieces of final_results_v4.py that compute something (lies by first / later asked, C2s counts, Wilson cells, percentiles) on tiny synthetic inputs."""

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import final_results_v4 as fr  # noqa: E402


def ask(dialog, truthful, decision="accepted", outvoted="false", withdrawn="false", final="LEFT", read="LEFT", true="RIGHT"):
    return {"dialog": str(dialog), "truthful": truthful, "decision": decision, "outvoted": outvoted, "withdrawn": withdrawn, "final_branch": final, "branch_read": read, "true_branch": true}


class LieSplit(unittest.TestCase):
    def test_first_and_later_asked_and_the_four_counts(self):
        rows = [ask(1, "false"),                                                  # a lie, accepted, taken, wrong: fooled
                ask(1, "false", decision="rejected:impossible", final="RIGHT"),   # detected and corrected
                ask(2, "false", outvoted="true", final="RIGHT"),                  # a later person's lie, outvoted, corrected
                ask(2, "false", withdrawn="true"),                                # detected, withdrawn: corrected not derivable per ask
                ask(1, "true"), ask(1, "")]                                        # truthful and not recorded: not lies
        r = fr.lie_split(rows)
        self.assertEqual(r["first"], {"given": 2, "detected": 1, "corrected": 1, "corrected_not_derivable_withdrawn": 0, "fooled": 1})
        self.assertEqual(r["later"], {"given": 2, "detected": 2, "corrected": 1, "corrected_not_derivable_withdrawn": 1, "fooled": 0})

    def test_a_lie_toward_the_true_branch_is_not_fooled(self):
        r = fr.lie_split([ask(1, "false", final="RIGHT", read="RIGHT", true="RIGHT")])
        self.assertEqual(r["first"]["fooled"], 0)


class C2sAndStats(unittest.TestCase):
    def test_c2s_counts(self):
        with tempfile.TemporaryDirectory() as d:
            b = Path(d)
            rows = [{"switch": True, "applies": False, "stop_used": [], "stop_other": []},
                    {"switch": True, "applies": True, "stop_used": [7], "stop_other": []},       # C2s made the difference
                    {"switch": True, "applies": True, "stop_used": [], "stop_other": []}]
            (b / "stop_reading.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
            c = fr.c2s_counts([b])
            self.assertEqual((c["rows"], c["c2s_applied_rows"], c["c2s_changed_the_stop_reading_rows"]), (3, 2, 1))
            self.assertEqual(round(c["share_applied"], 4), round(2 / 3, 4))
            self.assertEqual(fr.c2s_counts([b / "missing"])["rows"], fr.ND)               # no file: not evaluated, not 0

    def test_percentiles_and_wilson(self):
        self.assertEqual(fr.pct([], 50), fr.ND)
        self.assertEqual(fr.pct([1, 2, 3, 4], 50), 2.5)
        w = fr.wilson_cell(20, 20, 1.96)
        self.assertEqual(w["rate"], 1.0)
        self.assertAlmostEqual(w["wilson_lo"], 0.8389, places=3)
        self.assertEqual(fr.floats([{"x": ""}, {"x": "1.5"}, {"x": "bad"}], "x"), [1.5])


if __name__ == "__main__":
    unittest.main()
