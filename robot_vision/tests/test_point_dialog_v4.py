"""The dialog replay of AUDIT.md 16.26.3 (analyse_point_dialog_v4.py): labels as the controller gives them, the true direction, the dialog feed, the false-POINT test and the summaries,
on synthetic records. The replay is evaluation code and changes nothing in the reader or the controller."""

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import analyse_point_dialog_v4 as pd  # noqa: E402
import gesture_motion as gm  # noqa: E402
import hri_control as hc  # noqa: E402

DV = pd.dialog_values()
ROAD = hc.Roadmap(hc.load_json("configs/v4/roadmap.json"))
J1 = "J1"                                                             # arrival from A (heading north); branches LEFT to J2, FORWARD to E1, RIGHT to J3


def point(world_away, world_toward=None):
    return gm.PointEstimate(0.0, 0.0, {"away": world_away, "toward": world_toward}, {}, False, 10, {"available": False, "prefers": None, "diff_deg": {}, "why": ""})


def rec(t, cmd="POINT", world=None, cat="POINT", phase="holding", truth_world=None, yaw=0.0, tid=1):
    r = {"key": ("s", 1, round(t, 4), tid), "t": t, "tid": tid, "yaw": yaw, "point": point(world) if (cmd == "POINT" and world is not None) else None, "cat": cat, "cmd": cmd, "phase": phase}
    if truth_world is not None:
        r["truth_rel"] = hc.wrap(truth_world - yaw)
    return r


class Labels(unittest.TestCase):
    def test_a_point_resolves_to_its_branch_and_everything_else_is_none(self):
        self.assertEqual(pd.label_of(rec(0.0, world=-90.0), ROAD, J1, DV, True), "LEFT")
        self.assertEqual(pd.label_of(rec(0.0, world=0.0), ROAD, J1, DV, True), "FORWARD")
        self.assertEqual(pd.label_of(rec(0.0, world=90.0), ROAD, J1, DV, True), "RIGHT")
        self.assertEqual(pd.label_of(rec(0.0, world=180.0), ROAD, J1, DV, True), "NONE")           # the arrival road is no answer
        self.assertEqual(pd.label_of(rec(0.0, cmd="NONE"), ROAD, J1, DV, True), "NONE")
        self.assertEqual(pd.label_of(rec(0.0, cmd="insufficient_history"), ROAD, J1, DV, True), "NONE")
        self.assertEqual(pd.label_of(rec(0.0, world=-61.0), ROAD, J1, DV, True), "LEFT")            # 29 degrees from LEFT: inside the 30 degree tolerance
        self.assertEqual(pd.label_of(rec(0.0, world=-50.0), ROAD, J1, DV, True), "NONE")            # 40 degrees from LEFT and 50 from FORWARD: no branch

    def test_the_true_direction_is_the_nearest_target_within_the_tolerance(self):
        frames = [rec(t / 10, truth_world=-90.0 + 5.0) for t in range(5)]
        self.assertEqual(pd.true_label(frames, ROAD, J1, 30.0), "LEFT")
        self.assertEqual(pd.true_label([rec(0.0, truth_world=178.0)], ROAD, J1, 30.0), "BACK")
        self.assertEqual(pd.true_label([rec(0.0, truth_world=-45.0)], ROAD, J1, 20.0), "none")     # 45 degrees from both LEFT and FORWARD
        self.assertEqual(pd.true_label([rec(0.0, cat="nothing")], ROAD, J1, 30.0), "none")


class Dialog(unittest.TestCase):
    def labels(self, frames):
        return [pd.label_of(r, ROAD, J1, DV, True) for r in frames]

    def test_a_held_label_is_accepted_after_the_hold(self):
        frames = [rec(t / 10, world=-90.0) for t in range(10)]
        acc, i, first = pd.feed(frames, self.labels(frames), DV, 0.0)
        self.assertEqual((acc, first), ("LEFT", 0))
        self.assertGreaterEqual(frames[i]["t"] - frames[first]["t"], DV["hold"] - 1e-9)

    def test_a_gap_or_a_change_restarts_the_hold(self):
        frames = [rec(0.0, world=-90.0), rec(0.1, world=-90.0), rec(0.2, cmd="NONE"), rec(0.8, cmd="NONE"), rec(0.9, world=90.0), rec(1.0, world=-90.0)]
        self.assertEqual(pd.feed(frames, self.labels(frames), DV, 0.0), (None, None, None))

    def test_a_false_point_frame_inside_the_hold_is_found(self):
        frames = [rec(t / 10, world=0.0, cat="nothing" if t == 2 else "POINT") for t in range(8)]
        acc, i, first = pd.feed(frames, self.labels(frames), DV, 0.0)
        self.assertEqual(acc, "FORWARD")
        self.assertTrue(pd.false_in_hold(frames, first, i))
        clean = [rec(t / 10, world=0.0) for t in range(8)]
        acc, i, first = pd.feed(clean, self.labels(clean), DV, 0.0)
        self.assertFalse(pd.false_in_hold(clean, first, i))


class Summaries(unittest.TestCase):
    def test_summary_rows_and_the_condition_text(self):
        asks = [{"accepted": "LEFT", "right": True, "wrong": False, "from_false_point": False, "others_accepted": []},
                {"accepted": "RIGHT", "right": False, "wrong": True, "from_false_point": False, "others_accepted": [{"tid": 3}]},
                {"accepted": None, "right": False, "wrong": False, "from_false_point": False, "others_accepted": []}]
        self.assertEqual(pd.summary_rows(asks), {"asks": 3, "accepted": 2, "right": 1, "wrong": 1, "from_false_point": 0, "others_accepted": 1})

    def test_the_roadmaps_of_the_sessions_exist_and_the_variants_are_the_reference_and_ii(self):
        for name, f in pd.ROADMAPS.items():
            self.assertTrue((ROOT / f).is_file(), name)
        self.assertEqual([v["key"] for v in pd.VARIANTS], ["ref", "ii"])
        self.assertEqual((DV["hold"], DV["gap"], DV["window"], DV["tol"]), (0.5, 0.3, 5.0, 30.0))


if __name__ == "__main__":
    unittest.main()
