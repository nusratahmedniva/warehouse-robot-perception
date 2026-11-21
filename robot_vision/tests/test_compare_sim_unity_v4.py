"""The sim / Unity comparison of AUDIT.md 16.28 item 3b (compare_sim_unity_v4.py): the workers_plan parser, the placement and liars given to the simulator, the validity check of the harness, the
decisions per junction visit read from Unity's dialogs, and the simulator run with Unity's liars. Synthetic inputs (the real zip is not in the repository). Analysis only: the simulator is not changed."""

import io
import json
import sys
import unittest
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import compare_sim_unity_v4 as cu  # noqa: E402

# the plan of run 1 of the step-5 B3 session (Unity's own text), with its two liars: J1 slot 1 shows RIGHT (true LEFT), J3 slot 2 shows RIGHT (true BACK)
PLAN_RUN1 = [
    "run 1 worker 1: A slot 1, sunbox_m_shirt_white, (4.25, -23.00), truthful FORWARD",
    "run 1 worker 2: A slot 2, sunbox_f_dress_red, (10.25, -23.00), truthful FORWARD",
    "run 1 worker 3: J1 slot 1, sunbox_m_tshirt_black, (4.25, -3.00), LIAR shows RIGHT (true LEFT)",
    "run 1 worker 4: J1 slot 2, sunbox_f_shirt_white, (10.25, 2.50), truthful LEFT",
    "run 1 worker 5: J2 slot 1, sunbox_m_shirt_white, (-3.25, -2.00), truthful FORWARD",
    "run 1 worker 6: J2 slot 2, sunbox_f_dress_red, (-8.75, 4.00), truthful FORWARD",
    "run 1 worker 7: J3 slot 1, sunbox_m_tshirt_black, (15.75, 2.00), truthful BACK",
    "run 1 worker 8: J3 slot 2, sunbox_f_shirt_white, (21.25, -4.00), LIAR shows RIGHT (true BACK)",
    "run 1 worker 9: J4 slot 1, sunbox_m_shirt_white, (-15.75, -2.00), truthful RIGHT",
    "run 1 worker 10: J4 slot 2, sunbox_f_dress_red, (-21.25, 4.00), truthful RIGHT",
]


def honest(nodes):
    return {n: [{**w, "lie": None} for w in ws] for n, ws in nodes.items()}


class Plan(unittest.TestCase):
    def test_the_lines_are_parsed_exactly(self):
        plan = cu.parse_workers_plan(PLAN_RUN1)
        self.assertEqual(sorted(plan), [1])
        self.assertEqual(list(plan[1]), ["A", "J1", "J2", "J3", "J4"])
        j1 = plan[1]["J1"]
        self.assertEqual([(w["slot"], w["x"], w["z"], w["lie"], w["true"]) for w in j1], [(1, 4.25, -3.0, "RIGHT", "LEFT"), (2, 10.25, 2.5, None, "LEFT")])
        self.assertEqual(plan[1]["J3"][0]["true"], "BACK")
        self.assertEqual(plan[1]["J3"][1]["lie"], "RIGHT")

    def test_a_liar_that_shows_back_where_there_is_no_such_branch(self):
        p = cu.parse_workers_plan(["run 2 worker 2: A slot 2, sunbox_f_shirt_white, (10.25, -23.00), LIAR shows BACK (no such branch) (true FORWARD)"])
        self.assertEqual((p[2]["A"][0]["lie"], p[2]["A"][0]["true"]), ("BACK", "FORWARD"))

    def test_the_workers_of_a_node_are_in_slot_order_and_a_bad_line_is_an_error(self):
        shuffled = [PLAN_RUN1[3], PLAN_RUN1[2]]
        self.assertEqual([w["slot"] for w in cu.parse_workers_plan(shuffled)[1]["J1"]], [1, 2])
        with self.assertRaisesRegex(ValueError, "not understood"):
            cu.parse_workers_plan(["run 1 worker 1: A slot 1, look, (1, 2), maybe FORWARD"])

    def test_the_simulators_layout_and_lie_table_follow_unity(self):
        nodes = cu.parse_workers_plan(PLAN_RUN1)[1]
        lay = cu.fixed_layout(nodes)
        self.assertEqual(lay["kind"], "fixed")
        self.assertEqual(lay["points"]["J1"], [[4.25, -3.0], [10.25, 2.5]])
        lies = cu.lie_table(nodes)
        self.assertEqual((lies[("J1", 1)], lies[("J1", 2)], lies[("J3", 1)], lies[("J3", 2)]), ("RIGHT", None, None, "RIGHT"))


class Harness(unittest.TestCase):
    def test_every_honest_direction_agrees_with_the_simulators_map(self):
        nodes = cu.parse_workers_plan(PLAN_RUN1)[1]
        self.assertEqual(cu.harness_check("B3", nodes, "E5"), [])                  # the goal of run 1: LEFT at J1, BACK at J3 (E5 is not reachable from J3)
        bad = cu.harness_check("B3", nodes, "E6")                                  # another goal: Unity's recorded directions no longer fit
        self.assertTrue(bad)
        self.assertTrue(all({"node", "slot", "unity_true", "sim_true"} <= set(b) for b in bad))

    def test_wrong_decisions_are_the_junction_decisions_off_the_route(self):
        dec = [{"event": "go", "node": "J1", "branch": "RIGHT"}, {"event": "answer_accepted", "node": "J1"}, {"event": "go", "node": "J2", "branch": "FORWARD"}]
        truth = {"J1": "LEFT", "J2": "FORWARD"}
        self.assertEqual(cu.wrong_decisions(dec, truth.get), [{"node": "J1", "drove": "RIGHT", "true": "LEFT"}])


class SimWithUnitysLiars(unittest.TestCase):
    def setUp(self):
        self.nodes = cu.parse_workers_plan(PLAN_RUN1)[1]

    def test_all_honest_reaches_the_goal(self):
        r = cu.run_sim("B3_off", honest(self.nodes), "E5")
        self.assertEqual((r["outcome"], r["route"]), ("SUCCESS", "A>J1>J2>J4>E5"))
        self.assertEqual((r["asks_of_liars"], r["wrong_decisions"]), (0, []))

    def test_the_liar_of_unity_is_followed_without_lie_detection(self):
        r = cu.run_sim("B3_off", self.nodes, "E5")                                # J1 slot 1 is a liar showing RIGHT: with one answer asked, the robot follows it
        self.assertEqual(r["outcome"], "FAILURE")
        self.assertEqual(r["wrong_decisions"][0], {"node": "J1", "drove": "RIGHT", "true": "LEFT"})
        self.assertGreaterEqual(r["asks_of_liars"], 1)
        self.assertTrue(r["route"].startswith("A>J1>J3"))

    def test_the_same_workers_with_the_liar_made_honest_succeed(self):
        nodes = {n: [{**w, "lie": None if (n, w["slot"]) == ("J1", 1) else w["lie"]} for w in ws] for n, ws in self.nodes.items()}
        nodes["J3"] = [{**w, "lie": None} for w in nodes["J3"]]
        self.assertEqual(cu.run_sim("B3_off", nodes, "E5")["outcome"], "SUCCESS")

    def test_a_liar_in_the_second_slot_is_not_asked_when_the_first_is_honest(self):
        nodes = {n: [{**w, "lie": None} for w in ws] for n, ws in self.nodes.items()}
        nodes["J1"][1]["lie"] = "RIGHT"                                            # slot 2 lies; slot 1 (the one the robot asks first) is honest
        r = cu.run_sim("B3_off", nodes, "E5")
        self.assertEqual((r["outcome"], r["asks_of_liars"]), ("SUCCESS", 0))

    def test_the_run_does_not_depend_on_the_seed_without_noise(self):
        a, b = cu.run_sim("B3", self.nodes, "E5", seed=1), cu.run_sim("B3", self.nodes, "E5", seed=7)
        self.assertEqual((a["outcome"], a["route"], a["wrong_decisions"]), (b["outcome"], b["route"], b["wrong_decisions"]))


def make_zip(path: Path, dialogs: list[dict], runs: list[dict], plan_lines: list[str]) -> None:
    def csv_text(rows):
        cols = list(rows[0])
        return "\n".join([",".join(cols)] + [",".join(str(r[c]) for c in cols) for r in rows]) + "\n"
    man = {"sessions": [{"setting": "t0_B3", "unity": "trials_development_Task2_B3_x", "bridge": "bridge_guide_x", "export": "export_csv_v4_x", "timeout_s": 900}]}
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("MANIFEST.json", json.dumps(man))
        z.writestr("t0_B3/trials_development_Task2_B3_x/session.json", json.dumps({"workers_plan": plan_lines, "goals_override": "E5,E6,E5", "seed": 1, "lie_rule": "per worker"}))
        z.writestr("t0_B3/export_csv_v4_x/runs.csv", csv_text(runs))
        z.writestr("t0_B3/export_csv_v4_x/dialogs.csv", csv_text(dialogs))


def dlg(trial, junction, visit, dialog, ask, decision, final, true, truthful="True", reason=""):
    return {"trial": trial, "junction": junction, "visit": visit, "dialog": dialog, "ask": ask, "decision": decision, "decision_reason": reason, "final_branch": final, "true_branch": true, "truthful": truthful}


def run_row(trial, goal, outcome, reason, route, given=0, fooled=0):
    return {"trial": trial, "goal": goal, "outcome": outcome, "failure_reason": reason, "route": route, "time_s": 100.0, "lies_given": given, "lies_detected": 0, "lies_corrected": 0, "lies_fooled": fooled}


class UnityReader(unittest.TestCase):
    def test_the_decision_is_taken_once_per_visit_by_its_last_dialog_and_aborts_are_found(self):
        import tempfile
        with tempfile.TemporaryDirectory() as t:
            p = Path(t) / "s.zip"
            dialogs = [dlg(1, "J1", "1", "1", 1, "accepted", "RIGHT", "LEFT", "False"), dlg(1, "J1", "1", "2", 1, "accepted", "RIGHT", "LEFT", "True"),       # two dialogs of one visit: ONE wrong decision
                       dlg(1, "J3", "1", "1", 1, "unclear", "", "BACK"), dlg(1, "J3", "1", "1", 2, "unclear", "", "BACK", reason="abort: gesture unclear after 2 asks at J3"),
                       dlg(2, "J1", "1", "1", 1, "accepted", "LEFT", "LEFT")]
            runs = [run_row(1, "E5", "FAILURE", "aborted", "A>J1>J3", 2, 1), run_row(2, "E6", "SUCCESS", "none", "A>J1>J2>E6")]
            make_zip(p, dialogs, runs, PLAN_RUN1 + [line.replace("run 1", "run 2") for line in PLAN_RUN1])
            with zipfile.ZipFile(p) as z:
                u = cu.unity_session(z, "B3")
        self.assertEqual(u["goals"], "E5,E6,E5")
        r1, r2 = u["runs"][1], u["runs"][2]
        self.assertEqual(r1["wrong_decisions"], [{"node": "J1", "drove": "RIGHT", "true": "LEFT"}])
        self.assertEqual([a["node"] for a in r1["unclear_dialogs"]], ["J3"])
        self.assertEqual((r1["outcome"], r1["failure_reason"], r1["lies"], r1["asks_of_liars"], r1["dialogs"]), ("FAILURE", "aborted", [2, 0, 0, 1], 1, 3))
        self.assertEqual((r2["wrong_decisions"], r2["unclear_dialogs"], r2["outcome"]), ([], [], "SUCCESS"))
        self.assertIn("J1", r1["nodes"])

    def test_compare_says_what_agrees(self):
        u = {"outcome": "FAILURE", "failure_reason": "aborted", "route": "A>J1>J3", "wrong_decisions": [{"node": "J1", "drove": "RIGHT", "true": "LEFT"}]}
        s = {"outcome": "FAILURE", "failure_reason": "wrong_goal", "route": "A>J1>J3>E4", "wrong_decisions": [{"node": "J1", "drove": "RIGHT", "true": "LEFT"}, {"node": "J3", "drove": "RIGHT", "true": "NONE"}]}
        c = cu.compare(u, s)
        self.assertEqual((c["same_outcome"], c["same_failure_reason"], c["same_route"], c["same_wrong_decisions"]), (True, False, False, False))
        self.assertTrue(cu.compare(u, u)["same_route"])


class Isolation(unittest.TestCase):
    def test_the_simulator_is_not_changed_and_nothing_imports_the_comparison(self):
        import ast
        offenders = []
        for p in ROOT.rglob("*.py"):
            rel = p.relative_to(ROOT)
            if ".venv" in rel.parts or rel.parts[0] == "tests" or rel.name == "compare_sim_unity_v4.py":
                continue
            tree = ast.parse(p.read_text(encoding="utf-8"))
            mods = {a.name for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names} | {n.module for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) and n.module}
            if "compare_sim_unity_v4" in mods:
                offenders.append(str(rel))
        self.assertEqual(offenders, [])
        src = (ROOT / "compare_sim_unity_v4.py").read_text(encoding="utf-8")
        self.assertIn("sim._stage_ask = types.MethodType(staged, sim)", src)            # the liars go in through the instance, not by editing hri_sim_v4


if __name__ == "__main__":
    unittest.main()
