"""The track-consistent recount of AUDIT.md 16.26.4 (analyse_live_association_v4.py): the declared constants, the identity of a commander by its 360 track, the truth category of a worker,
the live chain state, the verification against the log and the declared pass / fail / inconclusive, on synthetic inputs. The module is evaluation code; inference never imports it."""

import ast
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import analyse_live_association_v4 as la  # noqa: E402

CFG = {"truth_join_max_s": 0.06, "shown_phases": ["holding", "gesturing"]}


def worker_rows(x, z, command="NONE", phase="idle", t0=0.0, n=5):
    return [{"time_s": t0 + 0.0166 * i, "x": x, "z": z, "true_command": command, "phase": phase, "point_angle_deg": 90.0} for i in range(n)]


def commander(link=35, x=0.0, z=0.0, yaw=0.0, bearing=0.0, dist=2.0):
    class P:                                                            # the commander's PersonReading, only what the identity needs
        track_id = 105
    return {"person": P(), "link": link, "f360": (0.04, {"x": x, "z": z, "yaw_deg": yaw}, [{"track_id": 35, "bearing_deg": bearing, "distance_m": dist}])}


class Constants(unittest.TestCase):
    def test_the_declared_values_are_the_audit_values(self):
        self.assertEqual((la.IDENT_RADIUS_M, la.IDENT_MARGIN_M, la.CHAIN_GAP_S, la.GROUP_GAP_S), (1.0, 0.3, 1.0, 30.0))


class Identity(unittest.TestCase):
    def test_the_nearest_worker_by_position_not_by_bearing(self):
        # two workers on the same bearing (north of the robot), 2.0 m and 3.5 m away: the 360 track at 2.0 m is the near one, even though both are at bearing 0
        truth = {1: worker_rows(0.0, 2.0, "POINT", "holding"), 2: worker_rows(0.0, 3.5)}
        self.assertEqual(la.identity(commander(), truth, CFG), (1, ""))
        self.assertEqual(la.identity(commander(dist=3.4), truth, CFG)[0], 2)

    def test_not_resolved_is_not_guessed(self):
        truth = {1: worker_rows(0.0, 2.0), 2: worker_rows(0.2, 2.0)}                          # 0.2 m apart: closer than the 0.3 m margin
        self.assertEqual(la.identity(commander(), truth, CFG)[0], None)
        self.assertIn("two workers", la.identity(commander(), truth, CFG)[1])
        self.assertEqual(la.identity(commander(), {1: worker_rows(0.0, 5.0)}, CFG)[0], None)   # none within 1.0 m
        self.assertEqual(la.identity(commander(link=None), {1: worker_rows(0.0, 2.0)}, CFG), (None, "no 360 track"))
        self.assertEqual(la.identity({"person": None, "link": None, "f360": None}, {1: worker_rows(0.0, 2.0)}, CFG), (None, "no commander"))
        self.assertEqual(la.identity(commander(), {1: worker_rows(0.0, 2.0, t0=10.0)}, CFG)[0], None)   # no truth row within 0.06 s of the 360 frame

    def test_the_bearing_is_relative_to_the_robot_yaw(self):
        truth = {1: worker_rows(2.0, 0.0)}                                                    # east of the robot
        self.assertEqual(la.identity(commander(yaw=90.0, bearing=0.0), truth, CFG)[0], 1)     # robot faces east, person straight ahead
        self.assertEqual(la.identity(commander(yaw=0.0, bearing=90.0), truth, CFG)[0], 1)     # robot faces north, person 90 degrees to the right
        self.assertEqual(la.identity(commander(yaw=0.0, bearing=0.0), truth, CFG)[0], None)


class Category(unittest.TestCase):
    def test_what_the_worker_shows(self):
        t = {1: worker_rows(0.0, 0.0, "POINT", "holding"), 2: worker_rows(0.0, 0.0, "NONE", "idle"), 3: worker_rows(0.0, 0.0, "POINT", "returning"),
             4: worker_rows(0.0, 0.0, "NONE", "start_delay")}
        self.assertEqual(la.category_of_worker(t, 1, 0.02, CFG)[0], "POINT")
        self.assertEqual(la.category_of_worker(t, 2, 0.02, CFG)[0], "nothing")
        self.assertEqual(la.category_of_worker(t, 3, 0.02, CFG)[0], None)                      # returning: left out, never counted as a POINT or as nothing
        self.assertEqual(la.category_of_worker(t, 4, 0.02, CFG)[0], "nothing")
        self.assertEqual(la.category_of_worker(t, 1, 5.0, CFG)[0], None)                       # no truth row near the time


class Chain(unittest.TestCase):
    def test_the_logged_previous_commander_only_if_recent(self):
        rows = [{"t": 1.0, "commander": {"commander": 7}}, {"t": 1.5, "commander": {"commander": 8}}, {"t": 3.0, "commander": {"commander": 9}}]
        self.assertIsNone(la.logged_previous(rows, 0, 1.0))
        self.assertEqual(la.logged_previous(rows, 1, 1.5), 7)
        self.assertIsNone(la.logged_previous(rows, 2, 3.0))                                    # the row before is 1.5 s older: the live state is gone

    def test_the_question_time_of_a_dialog(self):
        groups = [{"first": 100.0, "last": 110.0, "node": "J1"}, {"first": 200.0, "last": 200.0, "node": "J2"}]
        self.assertEqual(la.t_ask_of(groups, 100.0), 100.0)
        self.assertEqual(la.t_ask_of(groups, 115.9), 100.0)                                    # last ask + 5.0 s window + 1.0 s margin
        self.assertIsNone(la.t_ask_of(groups, 99.0))                                           # before the first ask: no question yet
        self.assertIsNone(la.t_ask_of(groups, 150.0))
        self.assertEqual(la.t_ask_of(groups, 203.0), 200.0)


class Holds(unittest.TestCase):
    def test_false_and_unresolved_frames_in_a_hold(self):
        class P:
            def __init__(self, cmd):
                self.reading = type("R", (), {"command": cmd})()
                self.track_id = 1
        L = [{"t": float(i)} for i in range(5)]
        C = [{"person": P("POINT")}, {"person": P("POINT")}, {"person": P("NONE")}, {"person": None}, {"person": P("POINT")}]
        T = [{"worker": 1, "cat": "POINT", "why": "", "phase": "holding"}, {"worker": 1, "cat": "nothing", "why": "", "phase": "idle"}, {"worker": 1, "cat": "nothing", "why": "", "phase": "idle"},
             {"worker": None, "cat": None, "why": "no commander", "phase": None}, {"worker": None, "cat": None, "why": "no 360 track", "phase": None}]
        h = la.hold_check(L, C, T, 0, 4)
        self.assertEqual([x["t"] for x in h["false"]], [1.0])                                   # POINT read, the worker shows nothing
        self.assertEqual([x["t"] for x in h["unresolved"]], [4.0])                              # POINT read, no identity
        self.assertEqual(la.hold_check(L, C, T, 0, 0), {"false": [], "unresolved": []})         # a correct POINT is neither


class Verification(unittest.TestCase):
    def test_rows_that_differ_from_the_log_are_found(self):
        class P:
            def __init__(self, tid, b, cmd, n):
                self.track_id, self.bearing_deg = tid, b
                self.reading = type("R", (), {"command": cmd, "valid_frames": n})()
        def row(t, cmd_id, c360, persons):
            return {"t": t, "commander": {"commander": cmd_id}, "commander_360": c360, "persons": [{"id": i, "bearing_deg": b, "reading": {"command": c, "valid_frames": n}} for i, b, c, n in persons]}
        rows = [row(1.0, 105, 35, [(105, -2.38, "NONE", 6)]), row(1.2, 105, 35, [(105, -2.38, "NONE", 6)]), row(1.4, None, None, [])]
        L = [{"t": r["t"], "row": r} for r in rows]
        good = [{"persons": [P(105, -2.381, "NONE", 6)], "commander": 105, "link": 35}, {"persons": [P(105, -2.38, "NONE", 6)], "commander": 105, "link": 35}, {"persons": [], "commander": None, "link": None}]
        v = la.verify(L, good, rows)
        self.assertEqual((len(v["v1_bad"]), len(v["v2_bad"]), len(v["v3_bad"]), v["no_frame"]), (0, 0, 0, 0))
        bad = [{"persons": [P(105, -2.30, "NONE", 6)], "commander": 106, "link": 35}, {"persons": [P(105, -2.38, "POINT", 6)], "commander": 105, "link": 36}, {"persons": [P(7, 0.0, "NONE", 1)], "commander": None, "link": None}]
        v = la.verify(L, bad, rows)
        self.assertEqual((len(v["v1_bad"]), len(v["v2_bad"]), len(v["v3_bad"])), (3, 1, 1))     # a bearing, a command and an id each make V1 fail
        self.assertEqual(la.verify(L[:2], good[:2], rows)["no_frame"], 1)                      # a logged row without a replayed frame counts


class Verdict(unittest.TestCase):
    def rep(self, ver_ok=True, wrong=False, false=False, unresolved=False, stream_false=False):
        def ask(**kw):
            return {"session": "A3", "run": 1, "node": "J1", "t0": 1.0, "accepted": "LEFT", "right": not wrong, "wrong": wrong, "false_point": [1] if false else [], "unresolved": [1] if unresolved else [], **kw}
        stream = {"session": "STOP", "run": 1, "accepted": [{"false_point": [1] if stream_false else [], "unresolved": []}]}
        ok = {"rows": 10, "no_frame": 0, "v1_bad": [], "v2_bad": [], "v3_bad": []}
        bad = {**ok, "v2_bad": [1]}
        return {"verification": {"S5": {"A3/run_001": ok if ver_ok else bad}}, "variants": {"ii": {"S5": [ask()], "STOP": [stream], "D4*": []}}}

    def test_pass_fail_and_inconclusive_as_declared(self):
        self.assertEqual(la.condition(self.rep(), None)["verdict"], "PASS")
        self.assertTrue(la.condition(self.rep(ver_ok=False), None)["verdict"].startswith("FAIL"))
        self.assertTrue(la.condition(self.rep(wrong=True), None)["verdict"].startswith("FAIL"))
        self.assertTrue(la.condition(self.rep(false=True), None)["verdict"].startswith("FAIL"))
        self.assertTrue(la.condition(self.rep(stream_false=True), None)["verdict"].startswith("FAIL"))
        self.assertTrue(la.condition(self.rep(unresolved=True), None)["verdict"].startswith("INCONCLUSIVE"))
        self.assertEqual(la.condition(self.rep(false=True), None)["flagged_still_false"], 1)


class Isolation(unittest.TestCase):
    def test_no_inference_module_imports_the_recount(self):
        offenders = []
        for p in ROOT.rglob("*.py"):
            rel = p.relative_to(ROOT)
            if ".venv" in rel.parts or rel.parts[0] == "tests" or rel.name == "analyse_live_association_v4.py":
                continue
            tree = ast.parse(p.read_text(encoding="utf-8"))
            mods = {a.name.split(".")[0] for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names}
            mods |= {n.module.split(".")[0] for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) and n.module}
            if "analyse_live_association_v4" in mods:
                offenders.append(str(rel))
        self.assertEqual(offenders, [])


if __name__ == "__main__":
    unittest.main()
