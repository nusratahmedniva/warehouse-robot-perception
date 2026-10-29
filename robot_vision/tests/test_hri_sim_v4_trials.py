"""Whole v4 trials in the simulator (hri_sim_v4.SimulatorV4 + hri_control_v4.ControllerV4): seeded, with bystanders, POINT
angles, WAIT, STOP, noise and zoom on / off. They check the outcome, the HUD fields and the logs a real run would write.

The reader returns two depth readings of a pointing arm (toward / away from the camera, mirror images about the image
plane). From the viewpoint the v3 approach gives at the roadmap's worker stand (about 45 deg off the arrival axis) the
mirror of FORWARD lands on LEFT, so FORWARD and LEFT at J1 are ambiguous for the roadmap alone: the robot then fails SAFE
(unclear, ask again, abort) and never takes a wrong branch. "good_crosscheck" models a MediaPipe hand cross-check that
always prefers the true reading (use_hand_crosscheck_as_tiebreak on); with a wrong one the robot takes the wrong branch.
Both are simulation assumptions, not measurements."""

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import commander_v4 as cm  # noqa: E402
import gesture_data as gd  # noqa: E402
import hri_control as hc  # noqa: E402
import hri_control_v4 as hv  # noqa: E402
import hri_sim_v4 as sv  # noqa: E402
from hri_sim import SimConfig  # noqa: E402


def trial(goal="E2", spec=None, gcfg=None, cfg=None, seed=1, zoom=True, wait_timeout=None, tiebreak=False, two_view=True,
          reapproach=True, shift=None):
    base, v4 = hv.load_control()
    v4["zoom"]["enabled"] = zoom
    v4["dialog"]["use_hand_crosscheck_as_tiebreak"] = tiebreak
    v4["dialog"]["two_view_enabled"] = two_view
    v4["dialog"]["reapproach_commander"] = reapproach
    if shift is not None:
        base["dialog"]["reask_shift_m"] = shift
    if wait_timeout is not None:
        v4["dialog"]["wait_timeout_s"] = wait_timeout
    ctrl = hv.ControllerV4(base, v4, cm.load_config(), hc.Roadmap(hc.load_json("configs/roadmap.json")))
    return sv.SimulatorV4(ctrl, cfg or SimConfig(), gcfg or sv.GestureSimConfig(), spec or sv.SceneSpec(), seed).run(goal)


def good(goal="E2", spec=None, seed=1, **gkw):
    """A trial with a perfect hand cross-check used as the tie-break."""
    return trial(goal, spec, sv.GestureSimConfig(crosscheck_accuracy=1.0, **gkw), seed=seed, tiebreak=True)


# Two bystanders, both FARTHER from the junction than the commander, off the aisles: the robot walks up to the commander.
BYSTANDERS = dict(bystander_offsets_m=[(1.2, 0.3), (2.0, -0.5)], bystander_looks=["look_b", "look_c"])
# The second bystander stands NEARER to the junction than the commander, at (6.8, 1.8), in the camera's view of the
# commander and clear of the robot's route to the commander (the simulator's routes are straight lines and the v3
# person-in-path stop holds the robot for good, so a bystander between robot and commander would block it): the robot
# first walks up to the wrong person and has to go to the commander. The layout is for J1 only.
NEARER = dict(bystander_offsets_m=[(1.2, 0.3), (-1.95, -0.7)], bystander_looks=["look_b", "look_c"])


class CleanTrials(unittest.TestCase):
    def test_every_goal_is_reached_with_a_cross_check(self):
        for goal in ("E1", "E2", "E3", "E4"):
            r = good(goal)
            self.assertEqual((r["outcome"], r["failure_reason"]), ("SUCCESS", "none"), goal)
            self.assertTrue(all(j["result"] == "accepted" and j["read"] == j["shown"] for j in r["junctions"]), goal)
        self.assertEqual(len(good("E4")["junctions"]), 2)                       # J1 then J2

    def test_the_branch_is_the_one_pointed_at(self):
        for goal, branch in (("E1", "FORWARD"), ("E2", "RIGHT"), ("E3", "FORWARD"), ("E4", "RIGHT")):
            self.assertEqual(good(goal)["junctions"][-1]["read"], branch, goal)

    def test_hud_fields_are_filled(self):
        r = trial("E2")
        hud = r["hud_log"]
        self.assertEqual(r["outcome"], "SUCCESS")
        self.assertTrue(any(h["commander_id"] >= 0 for h in hud))
        self.assertTrue(any(h["gesture"] == "POINT" and h["gesture_raw"] == "POINT" for h in hud))
        self.assertTrue(any(h["gesture_score"] > 0 for h in hud))
        self.assertTrue(any(h["gesture_accepted"] == "RIGHT" for h in hud))
        angles = [h["point_angle_deg"] for h in hud if h["point_angle_deg"] != -1.0]
        self.assertTrue(angles and all(-180.0 <= a <= 180.0 for a in angles))
        before = [h for h in hud if h["t"] < 1.0]
        self.assertTrue(all(h["commander_id"] == -1 and h["gesture"] == "NONE" for h in before))      # nobody yet

    def test_same_seed_same_trial(self):
        a, b = good("E4", seed=3, coverage={"POINT": 0.8}, point_angle_sigma_deg=8.0), good("E4", seed=3, coverage={"POINT": 0.8}, point_angle_sigma_deg=8.0)
        self.assertEqual((a["outcome"], a["time_s"], a["trace"]), (b["outcome"], b["time_s"], b["trace"]))

    def test_logs_a_real_run_would_write(self):
        r = trial("E2")
        self.assertGreater(len(r["frame_log"]), 5)
        row = r["frame_log"][-1]
        for key in ("t", "junction", "mode", "robot", "pan_deg", "fov_deg", "persons", "commander", "commander_360", "label",
                    "resolution", "fov_cmd"):
            self.assertIn(key, row)
        self.assertEqual(row["commander"]["commander"], 1)
        rows = gd.parse_truth([json.dumps(x) for x in r["truth_rows"]])                      # valid truth.jsonl lines
        self.assertEqual([(c.worker_id, c.command) for c in gd.build_clips(rows)], [(1, "POINT")])
        self.assertGreater(len(gd.join(r["frames"], rows).labels), 20)


class Ambiguity(unittest.TestCase):
    def test_forward_and_left_fail_safe_from_the_v3_viewpoint_without_the_second_view(self):
        for goal in ("E1", "E3", "E4"):
            r = trial(goal, two_view=False, shift=0.4)               # the v3 re-ask shift: the second ask sees nearly the same mirror
            self.assertEqual((r["outcome"], r["failure_reason"]), ("FAILURE", "aborted"), goal)
            self.assertIn("gesture unclear", r["abort_reason"])
            res = [row["resolution"] for row in r["frame_log"] if row["resolution"]]
            self.assertTrue(any(x["ambiguous"] for x in res), goal)
            self.assertTrue(all(x["command"] is None for x in res if x["ambiguous"]))

    def test_with_the_v4_shift_of_0_8_m_even_a_plain_re_ask_resolves_them_by_geometry(self):
        # from 0.8 m to the side the mirror of FORWARD lands between the branches and is dropped: the second ask is unambiguous
        for goal in ("E1", "E3"):
            r = trial(goal, two_view=False)
            self.assertEqual((r["outcome"], r["junctions"][0]["asks"]), ("SUCCESS", 2), goal)

    def test_the_second_view_resolves_forward_and_left(self):
        for goal in ("E1", "E3", "E4"):
            r = trial(goal)
            self.assertEqual((r["outcome"], r["failure_reason"]), ("SUCCESS", "none"), goal)
            j1 = r["junctions"][0]
            self.assertEqual((j1["views"], j1["asks"]), (2, 1), goal)               # two viewpoints, still one ask
            self.assertIn("second_view", " ".join(r["trace"]))
            self.assertTrue(all(j["read"] == j["shown"] for j in r["junctions"]))

    def test_right_is_unambiguous_and_needs_no_second_view(self):
        r = trial("E2")
        self.assertEqual((r["outcome"], r["junctions"][0]["views"]), ("SUCCESS", 1))
        self.assertNotIn("second_view", " ".join(r["trace"]))
        res = [row["resolution"] for row in r["frame_log"] if row["resolution"]]
        self.assertTrue(all(not x["ambiguous"] for x in res))
        self.assertTrue(any(any(c["target"] == "ARRIVAL" for c in x["candidates"]) for x in res))

    def test_a_wrong_cross_check_sends_the_robot_the_wrong_way(self):
        g = sv.GestureSimConfig(crosscheck_accuracy=0.0)
        r = trial("E3", gcfg=g, tiebreak=True)
        self.assertEqual((r["outcome"], r["failure_reason"]), ("FAILURE", "wrong_goal"))      # why the tie-break is off by default
        r = trial("E3", gcfg=g, tiebreak=False)                                             # off: the second view decides
        self.assertEqual(r["outcome"], "SUCCESS")

    def test_second_view_with_a_larger_shift_survives_more_noise(self):
        # angle noise 8 deg: a 0.4 m shift (mirror candidate moves ~23 deg) is borderline for a 10 deg tolerance; 1.0 m is not
        g = sv.GestureSimConfig(point_angle_sigma_deg=8.0)
        small = [trial("E1", gcfg=g, seed=s, shift=0.4)["outcome"] for s in range(1, 9)]
        large = [trial("E1", gcfg=g, seed=s, shift=1.0)["outcome"] for s in range(1, 9)]
        self.assertGreaterEqual(large.count("SUCCESS"), small.count("SUCCESS"))


class TwoViewStudy(unittest.TestCase):
    def test_noise_free_the_second_view_resolves_every_ambiguous_ask(self):
        rows = sv.two_view_study(seeds=range(1, 4))
        by = {r["branch"]: r for r in rows}
        self.assertEqual((by["FORWARD"]["ambiguous"], by["FORWARD"]["resolved_right"]), (3, 3))
        self.assertEqual((by["LEFT"]["ambiguous"], by["LEFT"]["resolved_right"]), (3, 3))
        self.assertEqual((by["RIGHT"]["ambiguous"], by["RIGHT"]["no_ambiguity_right"]), (0, 3))
        for r in rows:
            self.assertEqual(r["resolved_wrong"], 0)

    def test_without_the_second_view_the_same_asks_end_unresolved(self):
        rows = sv.two_view_study(goals=("E1",), seeds=range(1, 3), two_view=False)
        self.assertEqual((rows[0]["ambiguous"], rows[0]["no_ambiguity_right"], rows[0]["no_ambiguity_wrong"]), (0, 0, 0))

    def test_a_small_tolerance_rejects_noisy_agreement(self):
        rows = sv.two_view_study(goals=("E1",), sigmas=(10.0,), seeds=range(1, 9), tolerance_deg=1.0)
        self.assertGreater(rows[0]["unresolved"], 0)                           # nothing agrees within 1 deg: ask again, abort


class Bystanders(unittest.TestCase):
    def test_commander_is_found_among_bystanders(self):
        spec = sv.SceneSpec(**BYSTANDERS, bystander_facing=[True, False])
        for goal in ("E1", "E2"):                                  # the layout is for J1
            r = trial(goal, spec)
            self.assertEqual(r["outcome"], "SUCCESS", (goal, r["abort_reason"]))
            self.assertTrue(all(j["commander_pt"] == 1 and not j["reapproached"] for j in r["junctions"]))
        log = trial("E2", spec)["frame_log"]
        self.assertTrue({1, 2}.issubset({p["id"] for row in log for p in row["persons"]}))      # the bystander was in view
        self.assertTrue(all(row["commander"]["commander"] in (None, 1) for row in log))

    def test_a_late_distractor_does_not_take_over(self):
        r = trial("E2", sv.SceneSpec(**BYSTANDERS, distractors=[(0, "POINT", 1.0, -90.0)]))
        self.assertEqual((r["outcome"], r["junctions"][0]["read"]), ("SUCCESS", "RIGHT"))

    def test_two_people_gesturing_at_once_is_a_tie_and_never_a_guess(self):
        r = trial("E2", sv.SceneSpec(**BYSTANDERS, distractors=[(0, "POINT", 0.0, -90.0)]))
        self.assertNotEqual(r["failure_reason"], "wrong_goal")
        self.assertEqual((r["outcome"], r["failure_reason"]), ("FAILURE", "aborted"))
        self.assertIn("gesture unclear", r["abort_reason"])
        self.assertTrue(any("tie" in (row["commander"] or {}).get("reason", "") for row in r["frame_log"]))

    def test_whoever_starts_first_after_the_question_is_followed_known_limit(self):
        # a bystander that starts earlier than the commander (but after the question) is chosen and then kept
        spec = sv.SceneSpec(**BYSTANDERS, hold_s=3.0)
        spec.distractors = [(0, "POINT", -0.4, 90.0)]
        r = trial("E2", spec)
        self.assertTrue(any(row["commander"]["commander"] == 2 for row in r["frame_log"]))

    def test_a_gesture_that_started_before_the_question_is_ignored(self):
        # bystander 0 raises the arm while the robot is still driving up and keeps it up: it never counts
        spec = sv.SceneSpec(**BYSTANDERS, early_distractors=[(0, "POINT", 0.0, -90.0, 60.0)])
        r = trial("E2", spec)
        self.assertEqual((r["outcome"], r["junctions"][0]["read"]), ("SUCCESS", "RIGHT"))
        self.assertTrue(all(row["commander"]["commander"] in (None, 1) for row in r["frame_log"]))
        why = {p["id"]: p["left_out"] for row in r["frame_log"] for p in (row["commander"] or {}).get("people", [])}
        self.assertEqual(why.get(2), "gesture started before the question was shown")

    def test_without_the_timing_rule_that_bystander_would_have_been_followed(self):
        spec = sv.SceneSpec(**BYSTANDERS, early_distractors=[(0, "POINT", 0.0, -90.0, 60.0)])
        r = trial("E2", spec)
        persons = [p for row in r["frame_log"] for p in row["persons"] if p["id"] == 2]
        self.assertTrue(persons and any(p["reading"]["command"] == "POINT" for p in persons))   # it was gesturing and readable


class Reapproach(unittest.TestCase):
    def test_a_bystander_nearer_than_the_commander_is_approached_first_then_the_commander(self):
        spec = sv.SceneSpec(**NEARER)
        r = trial("E2", spec)
        self.assertEqual(r["outcome"], "SUCCESS", r["abort_reason"])
        j = r["junctions"][0]
        self.assertTrue(j["reapproached"])
        self.assertEqual((j["reapproach"]["from_360"], j["reapproach"]["to_360"]), (3, 1))
        self.assertEqual((j["asks"], j["commander_pt"]), (1, 1))                          # the extra question is not an ask
        self.assertIn("reapproach", " ".join(r["trace"]))
        self.assertEqual(r["trace"].count([x for x in r["trace"] if "reapproach" in x][0]), 1)    # once

    def test_the_robot_ends_two_metres_from_the_commander(self):
        r = trial("E2", sv.SceneSpec(**NEARER))
        rows = [row for row in r["frame_log"] if row["commander"] and row["commander"]["commander"] == 1]
        last = rows[-1]
        cmdr = [x for x in r["truth_rows"] if x["worker_id"] == 1][0]
        d = ((last["robot"]["x"] - cmdr["x"]) ** 2 + (last["robot"]["z"] - cmdr["z"]) ** 2) ** 0.5
        self.assertAlmostEqual(d, 2.0, delta=0.3)

    def test_without_the_re_approach_the_commander_is_still_read_from_farther_away(self):
        r = trial("E2", sv.SceneSpec(**NEARER), reapproach=False)
        self.assertEqual(r["outcome"], "SUCCESS")
        self.assertFalse(r["junctions"][0]["reapproached"])

    def test_forward_with_a_nearer_bystander_uses_both_mechanisms(self):
        r = trial("E1", sv.SceneSpec(**NEARER))
        self.assertEqual(r["outcome"], "SUCCESS", r["abort_reason"])
        j = r["junctions"][0]
        self.assertEqual((j["reapproached"], j["views"], j["asks"]), (True, 2, 1))

    def test_stop_by_a_bystander_stops_the_robot_then_the_trial_continues(self):
        r = trial("E2", sv.SceneSpec(**BYSTANDERS, stop={"who": 0, "after_ask_s": 0.2, "hold_s": 1.0}))
        self.assertTrue(any("stopped: STOP gesture" in h["state"] for h in r["hud_log"]))
        self.assertTrue(any(h["gesture"] == "STOP" for h in r["hud_log"]))
        self.assertEqual(r["outcome"], "SUCCESS")

    def test_stop_by_the_commander(self):
        r = trial("E2", sv.SceneSpec(stop={"who": "commander", "after_ask_s": 0.0, "hold_s": 1.0}))
        self.assertTrue(any("stopped: STOP gesture" in h["state"] for h in r["hud_log"]))
        self.assertEqual(r["outcome"], "SUCCESS")


class WaitTrials(unittest.TestCase):
    def test_wait_then_point(self):
        r = trial("E2", sv.SceneSpec(wait_first_s=4.0))
        self.assertEqual(r["outcome"], "SUCCESS")
        self.assertTrue(any(h["state"] == "wait" for h in r["hud_log"]))
        self.assertTrue(any(h["gesture"] == "WAIT" and h["gesture_accepted"] == "WAIT" for h in r["hud_log"]))
        self.assertGreater(r["junctions"][0]["waited_s"], 1.0)
        self.assertEqual(r["junctions"][0]["asks"], 1)

    def test_a_wait_that_never_ends_times_out_twice_and_aborts(self):
        r = trial("E2", sv.SceneSpec(wait_first_s=8.0), wait_timeout=2.0)
        self.assertEqual((r["outcome"], r["failure_reason"]), ("FAILURE", "aborted"))
        self.assertIn("wait timeout", r["abort_reason"])


class Noise(unittest.TestCase):
    def test_angle_noise_still_reaches_the_goal(self):
        for seed in range(1, 5):
            for goal in ("E1", "E2", "E4"):
                self.assertEqual(good(goal, seed=seed, point_angle_sigma_deg=8.0)["outcome"], "SUCCESS", (goal, seed))

    def test_lossy_readings_may_fail_but_never_reach_the_wrong_goal(self):
        g = sv.GestureSimConfig(coverage={"POINT": 0.7}, accuracy={"POINT": 0.7}, point_angle_sigma_deg=10.0)
        reasons = {trial("E1", sv.SceneSpec(**BYSTANDERS), g, seed=seed)["failure_reason"] for seed in range(1, 7)}
        self.assertTrue(reasons <= {"none", "aborted", "timeout"}, reasons)

    def test_a_commander_that_is_never_read_aborts(self):
        r = trial("E2", gcfg=sv.GestureSimConfig(coverage={"POINT": 0.0}))
        self.assertEqual((r["outcome"], r["failure_reason"]), ("FAILURE", "aborted"))


class ZoomTrials(unittest.TestCase):
    def test_zoom_on_narrows_the_view_and_off_does_not(self):
        on, off = trial("E2", zoom=True), trial("E2", zoom=False)
        self.assertEqual((on["outcome"], off["outcome"]), ("SUCCESS", "SUCCESS"))
        self.assertTrue(any(0 < h["fov_cmd"] < 60.0 for h in on["hud_log"]))
        self.assertEqual({h["fov_cmd"] for h in off["hud_log"]}, {-1.0})
        self.assertTrue(all(row["fov_cmd"] == -1.0 for row in off["frame_log"]))
        self.assertTrue(any(row["fov_deg"] and row["fov_deg"] < 60.0 for row in on["frame_log"]))
        self.assertTrue(on["v4"]["zoom_enabled"] and not off["v4"]["zoom_enabled"])


if __name__ == "__main__":
    unittest.main()
