"""Step 9 decision rules: scenario files (one per rule, conflicts, timing, motion trust, look-ahead),
required-width and look-ahead maths, geometry and output files. No dataset needed."""

import ast
import csv
import json
import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import decision as dec  # noqa: E402
import decision_io as dio  # noqa: E402
import footprint as fp  # noqa: E402

SCENARIOS = sorted((ROOT / "tests" / "scenarios").glob("*.json"))
ROBOT = {"robot_width_m": 0.60, "safety_margin_per_side_m": 0.10, "max_speed_mps": 1.0, "decel_mps2": 0.5}
PALLET = {"width_m": 0.80, "length_m": 1.20, "lateral_offset_m": 0.0, "label": "configured, not measured"}
REQ = fp.load_footprint()["required_width_m"]
CORRIDOR = dec.RouteCorridor(((0.0, 0.0), (0.0, 20.0)), REQ)
CLEAR = dec.PassageState("clear", 1.5, REQ)


def person(tid, pos, dist=None, label="unknown", vel=None, trusted=False, t=0.0, lower=None):
    return dec.PersonState(tid, t, pos, dist, label, vel, trusted, lower)


class ScenarioTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cfg, _, _, cls.req = dio.load_decision_config()

    def test_every_rule_and_case_has_a_scenario(self):
        names = {p.stem for p in SCENARIOS}
        for need in [f"rule{i}_" for i in range(1, 9)] + [
                "conflict_stop_vs_move", "conflict_person_in_route_with_move", "conflict_narrow_passage_with_move",
                "gesture_timeout", "asymmetric_timing", "unknown_motion", "beyond_motion_range",
                "look_ahead_boundary", "head_on_approach", "caution_band", "unlocated_person"]:
            self.assertTrue(any(n.startswith(need) for n in names), need)

    def test_scenarios(self):
        for p in SCENARIOS:
            with self.subTest(scenario=p.stem):
                sc = json.loads(p.read_text(encoding="utf-8"))
                self.assertEqual(dio.check_assumptions(sc, self.cfg, self.req), [])
                ds = dio.run_scenario(sc, self.cfg, self.req)
                self.assertEqual(dio.check_expectations(sc, ds), [])
                rules = {e["rule"] for e in sc["expect"]}
                self.assertTrue(rules, "scenario has no expectations")

    def test_every_rule_reached(self):
        seen = set()
        for p in SCENARIOS:
            sc = json.loads(p.read_text(encoding="utf-8"))
            seen |= {(d.decision, d.rule) for d in dio.run_scenario(sc, self.cfg, self.req)}
        self.assertEqual({r for _, r in seen}, set(range(1, 9)))
        self.assertTrue({("STOP", 1), ("STOP", 2), ("STOP", 3), ("STOP", 4), ("WAIT", 5), ("STOP", 6),
                         ("MOVE", 7), ("WAIT", 8)} <= seen)


class RequiredWidthTests(unittest.TestCase):
    def test_centred_euro_pallet(self):
        # pallet 0.80 m across travel, centred: extents -0.40..0.40 -> 0.80 + 2 * 0.10
        r = fp.required_width(ROBOT, PALLET)
        self.assertAlmostEqual(r["required_width_m"], 1.00)
        self.assertEqual((r["left_extent_m"], r["right_extent_m"]), (-0.40, 0.40))
        self.assertEqual(r["load_label"], "configured, not measured")

    def test_off_centre_load(self):
        # robot -0.30..0.30, pallet 0.20 +- 0.40 = -0.20..0.60 -> 0.90 + 0.20
        r = fp.required_width(ROBOT, {**PALLET, "lateral_offset_m": 0.20})
        self.assertAlmostEqual(r["required_width_m"], 1.10)
        self.assertEqual((r["left_extent_m"], r["right_extent_m"]), (-0.30, 0.60))
        left = fp.required_width(ROBOT, {**PALLET, "lateral_offset_m": -0.20})
        self.assertAlmostEqual(left["required_width_m"], 1.10)
        self.assertEqual((left["left_extent_m"], left["right_extent_m"]), (-0.60, 0.30))

    def test_load_narrower_than_robot_and_no_load(self):
        self.assertAlmostEqual(fp.required_width(ROBOT, {"width_m": 0.40, "lateral_offset_m": 0.1})["required_width_m"], 0.80)
        self.assertAlmostEqual(fp.required_width(ROBOT, None)["required_width_m"], 0.80)

    def test_configured_files(self):
        foot = fp.load_footprint()
        load = foot["load"]
        self.assertEqual(load["label"], "configured, not measured")
        self.assertEqual((load["width_m"], load["length_m"], load["lateral_offset_m"]), (0.80, 1.20, 0.0))
        self.assertAlmostEqual(foot["required_width_m"], 1.00)
        self.assertEqual(dio.load_decision_config()[3]["required_width_m"], foot["required_width_m"])

    def test_one_required_width_function(self):
        defs = []
        for f in ROOT.glob("*.py"):
            tree = ast.parse(f.read_text(encoding="utf-8"))
            defs += [f.name for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == "required_width"]
        self.assertEqual(defs, ["footprint.py"])
        for f in ["make_proxy_route.py", "estimate_motion.py", "decision_io.py"]:
            self.assertIn("load_footprint", (ROOT / f).read_text(encoding="utf-8"), f)


class LookAheadTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cfg, _, _, cls.req = dio.load_decision_config()
        cls.L = cls.cfg["look_ahead"]["look_ahead_m"]

    def engine(self):
        return dec.DecisionEngine(self.cfg, self.req, CORRIDOR)

    def test_formula(self):
        la = fp.look_ahead(ROBOT, {"reaction_s": 0.5, "buffer_m": 1.5})
        self.assertAlmostEqual(la["look_ahead_m"], 1.0 * 0.5 + 1.0 / (2 * 0.5) + 1.5)
        self.assertAlmostEqual(la["look_ahead_m"], 3.0)
        self.assertAlmostEqual(self.L, 3.0)
        with self.assertRaises(ValueError):  # declared value no longer matches its inputs
            fp.look_ahead({**ROBOT, "max_speed_mps": 1.5}, {"reaction_s": 0.5, "buffer_m": 1.5, "look_ahead_m": 3.0})

    def test_caution_formula(self):
        ca = fp.caution_ahead(ROBOT, {"reaction_s": 0.5}, {"person_speed_mps": 1.4})
        self.assertAlmostEqual(ca["stopping_distance_m"], 1.5)
        self.assertAlmostEqual(ca["stopping_time_s"], 2.5)
        self.assertAlmostEqual(ca["caution_ahead_m"], 1.5 + 1.4 * 2.5)
        self.assertAlmostEqual(self.cfg["caution_ahead_m"], 5.0)
        with self.assertRaises(ValueError):  # stale declared value
            fp.caution_ahead({**ROBOT, "decel_mps2": 1.0}, {"reaction_s": 0.5},
                             {"person_speed_mps": 1.4, "caution_ahead_m": 5.0})

    def _one(self, pos, trusted):
        p = person(1, pos, pos[1], "stationary" if trusted else "unknown", (0.0, 0.0) if trusted else None, trusted)
        return self.engine().step(dec.DecisionFrame(0.0, (p,), CLEAR, (), (0.0, 0.0)))

    def test_caution_band_in_corridor(self):
        d = self._one((0.0, 4.5), trusted=False)
        self.assertEqual((d.decision, d.rule), ("STOP", 4))
        d = self._one((0.0, 4.5), trusted=True)
        self.assertNotEqual(d.decision, "STOP")
        d = self._one((0.0, 5.5), trusted=False)
        self.assertNotEqual(d.decision, "STOP")

    def test_caution_ahead_must_cover_look_ahead(self):
        self.assertGreaterEqual(self.cfg["caution_ahead_m"], self.L)
        with self.assertRaises(ValueError):
            dec.DecisionEngine({**self.cfg, "caution_ahead_m": self.L - 0.5}, self.req, CORRIDOR)

    def test_in_route_inside_look_ahead_stops(self):
        d = self.engine().step(dec.DecisionFrame(0.0, (person(1, (0.0, self.L - 0.1), self.L - 0.1),), CLEAR, (),
                                                 (0.0, 0.0)))
        self.assertEqual((d.decision, d.rule), ("STOP", 1))

    def test_in_route_beyond_look_ahead_standing_still_does_not_stop(self):
        d = self.engine().step(dec.DecisionFrame(
            0.0, (person(1, (0.0, self.L + 0.1), self.L + 0.1, "stationary", (0.0, 0.0), True),), CLEAR, (), (0.0, 0.0)))
        self.assertEqual(d.decision, "WAIT")
        self.assertEqual(d.rule, 8)
        self.assertFalse(d.snapshot["persons"][0]["in_stop_zone"])

    def test_stop_zone_end_is_flat(self):
        # inside the round cap a half-width past the end would be "inside"; the flat end excludes it
        e = self.engine()
        half = self.req["required_width_m"] / 2
        self.assertFalse(e._in_stop_zone((0.0, self.L + half * 0.8), 0.0)[0])
        self.assertTrue(e._in_stop_zone((half * 0.9, self.L - 0.01), 0.0)[0])

    def test_route_end_is_not_cut_flat(self):
        # route ends 0.8 m ahead of the robot, before the look-ahead: the zones keep a round end there
        e = dec.DecisionEngine(self.cfg, self.req, dec.RouteCorridor(((0.0, 0.0), (0.0, 0.8)), REQ))
        half = self.req["required_width_m"] / 2
        self.assertTrue(e._in_stop_zone((0.0, 0.8 + half * 0.8), 0.0)[0])
        d = e.step(dec.DecisionFrame(0.0, (person(1, (0.6, 1.0), 1.2),), CLEAR, (), (0.0, 0.0)))
        self.assertEqual((d.decision, d.rule), ("STOP", 4))  # untrusted, just past the route end, beside it

    def test_head_on_approach_from_5_m_stops_before_stop_zone(self):
        e = self.engine()
        first_stop = None
        for k in range(0, 31):  # 3 s at 10 Hz, walking head-on at 1 m/s from 5 m
            t = k * 0.1
            z = 5.0 - t
            d = e.step(dec.DecisionFrame(t, (person(1, (0.0, z), z, "approaching", (0.0, -1.0), True, t),), CLEAR,
                                         (), (0.0, 0.0)))
            if d.decision == "STOP" and first_stop is None:
                first_stop = (t, z, d)
        t, z, d = first_stop
        self.assertEqual(d.rule, 2)
        self.assertGreater(z, self.L)  # stopped while the person was still outside the stop zone
        self.assertIn("closing at 1.00 m/s", d.reason)

    def test_sideways_entry(self):
        d = self.engine().step(dec.DecisionFrame(
            0.0, (person(1, (3.0, 2.0), 3.6, "moving_lateral", (-1.0, 0.0), True),), CLEAR, (), (0.0, 0.0)))
        self.assertEqual((d.decision, d.rule), ("STOP", 2))
        self.assertAlmostEqual(d.snapshot["persons"][0]["gap_to_stop_zone_m"], 3.0 - self.req["required_width_m"] / 2)


class GeometryAndEdgeCaseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cfg, _, _, cls.req = dio.load_decision_config()

    def engine(self, corridor=CORRIDOR):
        return dec.DecisionEngine(self.cfg, self.req, corridor)

    def test_polyline_nearest_and_portion(self):
        line = dec.Polyline([(0, 0), (0, 10), (10, 10)])
        self.assertEqual(line.length, 20)
        d, s = line.nearest((1, 5))
        self.assertAlmostEqual(d, 1)
        self.assertAlmostEqual(s, 5)
        d, s = line.nearest((1, 5), s0=12)  # only (2, 10) onwards counts
        self.assertAlmostEqual(d, 26 ** 0.5)
        self.assertAlmostEqual(s, 12)
        d, s = line.nearest((5, 0), s1=4)  # only (0, 0)..(0, 4) counts
        self.assertAlmostEqual(d, 5)
        self.assertAlmostEqual(s, 0)

    def test_person_behind_robot_is_not_in_route(self):
        e = self.engine()
        d = e.step(dec.DecisionFrame(0.0, (person(1, (0.0, 2.0), 3.0),), CLEAR, (), (0.0, 5.0)))
        self.assertEqual((d.decision, d.rule), ("WAIT", 8))
        d = e.step(dec.DecisionFrame(0.1, (person(1, (0.0, 7.0), 2.0),), CLEAR, (), (0.0, 5.0)))
        self.assertEqual((d.decision, d.rule), ("STOP", 1))

    def test_unlocated_person_uses_only_the_lower_bound(self):
        e = self.engine()
        ca = self.cfg["caution_ahead_m"]
        d = e.step(dec.DecisionFrame(0.0, (person(1, None, 2.0, lower=2.0),), CLEAR, (), (0.0, 0.0)))
        self.assertEqual((d.decision, d.rule), ("STOP", 4))
        self.assertIn("position unknown, at least 2.00 m away", d.reason)
        d = e.step(dec.DecisionFrame(0.1, (person(2, None, 8.0, lower=ca + 0.5),), CLEAR, (), (0.0, 0.0)))
        self.assertEqual((d.decision, d.rule), ("WAIT", 8))
        # a far median distance without a lower bound releases nothing
        d = e.step(dec.DecisionFrame(0.2, (person(3, None, 8.0),), CLEAR, (), (0.0, 0.0)))
        self.assertEqual((d.decision, d.rule), ("STOP", 4))
        d = e.step(dec.DecisionFrame(0.3, (person(4, None, None),), CLEAR, (), (0.0, 0.0)))
        self.assertEqual((d.decision, d.rule), ("STOP", 4))

    def test_corridor_width_must_be_the_required_width(self):
        with self.assertRaises(ValueError):
            self.engine(dec.RouteCorridor(((0.0, 0.0), (0.0, 20.0)), 0.8))  # e.g. the robot-only proxy_route width
        e = self.engine()
        d = e.step(dec.DecisionFrame(0.0, (person(1, (0.45, 2.0), 2.0),), CLEAR, (), (0.0, 0.0)))
        self.assertEqual(d.rule, 1)  # 0.45 m off-centre: inside the 1.00 m pallet footprint

    def test_passage_for_other_required_width_is_unknown(self):
        d = self.engine().step(dec.DecisionFrame(0.0, (), dec.PassageState("clear", 1.5, 0.8), (), (0.0, 0.0)))  # 0.8 != 1.0
        self.assertEqual((d.decision, d.rule), ("WAIT", 5))
        self.assertIn("evaluated for 0.80 m", d.reason)

    def test_timestamps_must_increase(self):
        e = self.engine()
        e.step(dec.DecisionFrame(1.0, (), CLEAR))
        with self.assertRaises(ValueError):
            e.step(dec.DecisionFrame(1.0, (), CLEAR))

    def test_invalid_inputs_rejected(self):
        with self.assertRaises(ValueError):
            dec.PassageState("open", None, None)
        with self.assertRaises(ValueError):
            dec.GestureEvent(0.0, 1, "WAVE", 1.0)

    def test_stop_hold_is_time_not_frames(self):
        hold = self.cfg["stop_hold_s"]
        for hz in (10, 60, 240):
            e, accepted = self.engine(), None
            for k in range(int(hz * 0.5)):
                t = k / hz
                d = e.step(dec.DecisionFrame(t, (), CLEAR, (dec.GestureEvent(t, 1, "STOP", 0.9),)))
                if d.decision == "STOP" and accepted is None:
                    accepted = t
                    self.assertEqual(d.rule, 3)
            self.assertAlmostEqual(accepted, hold, delta=1 / hz + 1e-9, msg=f"{hz} Hz")
            self.assertGreaterEqual(accepted, hold - 1e-9)


class IsolationAndOutputTests(unittest.TestCase):
    def test_decision_core_uses_standard_library_only(self):
        tree = ast.parse((ROOT / "decision.py").read_text(encoding="utf-8"))
        mods = {a.name.split(".")[0] for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names}
        mods |= {n.module.split(".")[0] for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) and n.module}
        self.assertTrue(mods <= {"__future__", "math", "dataclasses"}, mods)
        tree = ast.parse((ROOT / "footprint.py").read_text(encoding="utf-8"))
        mods = {a.name.split(".")[0] for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names}
        mods |= {n.module.split(".")[0] for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) and n.module}
        self.assertTrue(mods <= {"__future__", "json", "pathlib"}, mods)

    def test_no_reference_loaders_imported(self):
        banned = {"thud_data", "fuse_objects", "estimate_motion", "validate_depth", "report_motion", "report_step4"}
        for f in ["decision.py", "decision_io.py", "footprint.py", "run_decisions.py", "replay_decisions.py",
                  "person_box_depth.py"]:
            p = ROOT / f
            if not p.exists():
                continue
            tree = ast.parse(p.read_text(encoding="utf-8"))
            mods = {a.name for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names}
            mods |= {n.module for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) and n.module}
            self.assertFalse(mods & banned, f"{f} imports {mods & banned}")

    def test_outputs_written(self):
        cfg, _, _, req = dio.load_decision_config()
        sc = json.loads((ROOT / "tests" / "scenarios" / "rule7_move.json").read_text(encoding="utf-8"))
        ds = dio.run_scenario(sc, cfg, req)
        with tempfile.TemporaryDirectory() as d:
            out = Path(d)
            dio.write_decisions(out, ds, {"scenario": sc["name"]})
            with (out / "decisions.csv").open(encoding="utf-8") as f:
                rows = list(csv.DictReader(f))
            self.assertEqual(len(rows), len(ds))
            self.assertEqual(rows[-1]["decision"], "MOVE")
            self.assertEqual(rows[-1]["rule_name"], "passage clear")
            log = json.loads((out / "decision_log.json").read_text(encoding="utf-8"))
            self.assertEqual(log["n_decisions"], len(ds))
            self.assertIn("snapshot", log["decisions"][0])
            self.assertIn("persons", log["decisions"][0]["snapshot"])

    def test_new_run_dir_never_reuses(self):
        fixed = datetime(2026, 1, 1, 12, 0, 0)
        with tempfile.TemporaryDirectory() as d, mock.patch.object(dio, "datetime") as dt:
            dt.now.return_value = fixed
            cfg = {"paths": {"output_root": d}}
            first = dio.new_run_dir(cfg, "x")
            (first / "keep.txt").write_text("existing", encoding="utf-8")
            with self.assertRaises(SystemExit):
                dio.new_run_dir(cfg, "x")
            self.assertEqual((first / "keep.txt").read_text(encoding="utf-8"), "existing")


if __name__ == "__main__":
    unittest.main()
