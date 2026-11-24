"""AUDIT.md 16.35.1: the evaluation scores every run on the map it was driven on (config_used/map_used.json of its bridge folder), not on the default v4 map; and a
superseded evaluation (wrong map / crashed) is the one thing that unlocks a setting for a second evaluation. Synthetic sessions only."""

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))

import final_guard_v4 as fg  # noqa: E402
import gesture_data as gd  # noqa: E402
import hri_control as hc  # noqa: E402
import hri_control_v4 as hv  # noqa: E402
import hri_eval_dev_v4 as ev  # noqa: E402
import hri_sim_v4 as sv  # noqa: E402
import test_export_csv_v4 as tx  # noqa: E402

DEFAULT = hv.load_roadmap(hv.roadmap_path(hv.load_control()[1]))


def nodes(rm) -> set:
    return set(rm.nodes)


class EachMapTests(unittest.TestCase):
    """One test per map: default (A3), A1 (roadmap_a1), A2 right and A2 left."""

    def check(self, name: str, side: str, expect_own_map: bool):
        tmp = Path(tempfile.mkdtemp())
        res = [sv.run_scenario(name, s, sv.DETECTION_ON, side=side) for s in (1, 2)]
        u, b = tx.session(res, tmp, "m")
        runs = ev.load_sessions([(u, b)], gd.load_config())
        own = hc.Roadmap(json.loads((b / "config_used" / "map_used.json").read_text(encoding="utf-8")))
        self.assertEqual(nodes(ev.road_of_run(runs[0])), nodes(own))                       # the run's own map, from its bridge folder
        self.assertEqual(nodes(own) != nodes(DEFAULT), expect_own_map)                     # (the default map is not the run's map for the experiments A1 and A2)
        by_default_resolver = ev.evaluate(runs)
        explicit = ev.evaluate(runs, road=own)                                             # the same runs scored with the true map handed in
        self.assertEqual(by_default_resolver["junction_level"]["dialog_detail"], explicit["junction_level"]["dialog_detail"])
        self.assertEqual(by_default_resolver["branch"], explicit["branch"])
        return by_default_resolver

    def test_default_map_a3(self):
        self.check("A3", "right", expect_own_map=False)

    def test_a1_map(self):
        self.check("A1", "right", expect_own_map=True)

    def test_a2_right_map(self):
        self.check("A2", "right", expect_own_map=True)

    def test_a2_left_map(self):
        self.check("A2", "left", expect_own_map=True)

    def test_the_old_default_map_fails_on_a_session_that_only_its_own_map_describes(self):
        tmp = Path(tempfile.mkdtemp())
        res = [sv.run_scenario("A2", s, sv.DETECTION_ON, side="right") for s in (1, 2, 3)]
        u, b = tx.session(res, tmp, "defect")
        runs = ev.load_sessions([(u, b)], gd.load_config())
        used = {j["junction"] for r in runs for j in r.junctions}
        if used <= nodes(DEFAULT):
            self.skipTest("the synthetic runs only used nodes the default map also has")
        with self.assertRaises(KeyError):
            ev.evaluate(runs, road=DEFAULT)                                                # what evaluate_final did before the fix (KeyError 'B' on the final data)

    def test_two_sessions_on_two_maps_are_each_scored_on_their_own(self):
        tmp = Path(tempfile.mkdtemp())
        a = tx.session([sv.run_scenario("A1", 1, sv.DETECTION_ON)], tmp, "one")
        b = tx.session([sv.run_scenario("A2", 1, sv.DETECTION_ON, side="left")], tmp, "two")
        runs = ev.load_sessions([a, b], gd.load_config())
        res = ev.evaluate(runs)
        self.assertEqual(len(res["junction_level"]["dialog_detail"]), sum(len(r.junctions) for r in runs))

    def test_without_map_used_the_control_files_roadmap_then_the_default(self):
        tmp = Path(tempfile.mkdtemp())
        u, b = tx.session([sv.run_scenario("A3", 1, sv.DETECTION_ON)], tmp, "fallback")
        runs = ev.load_sessions([(u, b)], gd.load_config())
        (b / "config_used" / "map_used.json").unlink()
        self.assertEqual(nodes(ev.road_of_run(runs[0], {})), nodes(DEFAULT))                # control.json names the default roadmap
        (b / "config_used" / "control.json").unlink()
        self.assertEqual(nodes(ev.road_of_run(runs[0], {})), nodes(DEFAULT))                # neither file: the default v4 map


class SupersededEvaluationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        for name, setting in (("hri_eval_final_v4_B1_x", "B1"), ("hri_eval_final_v4_B1_off_x", "B1_off")):
            (self.root / name).mkdir()
            fg.write_done(self.root / name, setting, "evaluation")

    def tearDown(self):
        self.tmp.cleanup()

    def test_a_declaration_unlocks_exactly_that_folder_and_leaves_it_untouched(self):
        before = (self.root / "hri_eval_final_v4_B1_x" / "FINAL_DONE.json").read_bytes()
        with self.assertRaisesRegex(SystemExit, "already evaluated"):
            fg.ensure_not_done(self.root, "B1", "evaluation")
        m = fg.declare_evaluation_superseded("B1", "hri_eval_final_v4_B1_x", "evaluated with the default map instead of the session's own", self.root)
        self.assertEqual(json.loads(m.read_text())["superseded_folder"], "hri_eval_final_v4_B1_x")
        fg.ensure_not_done(self.root, "B1", "evaluation")                                  # unlocked
        with self.assertRaisesRegex(SystemExit, "already evaluated"):                        # B1_off is a different setting and stays locked
            fg.ensure_not_done(self.root, "B1_off", "evaluation")
        self.assertEqual((self.root / "hri_eval_final_v4_B1_x" / "FINAL_DONE.json").read_bytes(), before)   # the old output is untouched
        (self.root / "hri_eval_final_v4_B1_new").mkdir()
        fg.write_done(self.root / "hri_eval_final_v4_B1_new", "B1", "evaluation")          # the corrected evaluation, once
        with self.assertRaisesRegex(SystemExit, "already evaluated"):
            fg.ensure_not_done(self.root, "B1", "evaluation")

    def test_refusals(self):
        with self.assertRaisesRegex(SystemExit, "--reason is required"):
            fg.declare_evaluation_superseded("B1", "hri_eval_final_v4_B1_x", " ", self.root)
        with self.assertRaisesRegex(SystemExit, "not an evaluation folder of 'B1'"):
            fg.declare_evaluation_superseded("B1", "hri_eval_final_v4_B1_off_x", "x", self.root)       # another setting's folder
        with self.assertRaisesRegex(SystemExit, "not an evaluation folder"):
            fg.declare_evaluation_superseded("B1", "nonexistent", "x", self.root)
        fg.declare_evaluation_superseded("B1", "hri_eval_final_v4_B1_x", "x", self.root)
        with self.assertRaisesRegex(SystemExit, "already superseded"):
            fg.declare_evaluation_superseded("B1", "hri_eval_final_v4_B1_x", "again", self.root)
        with self.assertRaisesRegex(SystemExit, "unknown final setting"):
            fg.declare_evaluation_superseded("nonsense", "x", "x", self.root)

    def test_the_command_line(self):
        import contextlib, io
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            code = fg.main(["--supersede-evaluation", "B1", "--folder", "hri_eval_final_v4_B1_x", "--reason", "wrong map", "--output-root", str(self.root)])
        self.assertEqual(code, 0)
        self.assertIn("FINAL_EVAL_SUPERSEDED.json written", buf.getvalue())
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as c:
            fg.main(["--supersede-evaluation", "B1", "--output-root", str(self.root)])             # no --folder / --reason
        self.assertEqual(c.exception.code, 2)


if __name__ == "__main__":
    unittest.main()
