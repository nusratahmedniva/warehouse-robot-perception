"""Step 5: state machine, dialog, steering and the simulator end to end (no Unity, no models)."""

import ast
import math
import unittest
from pathlib import Path

import hri_control as hc
import hri_sim as hs

HERE = Path(__file__).resolve().parents[1]
ROAD = hc.Roadmap(hc.load_json("configs/roadmap.json"))
CFG = hc.load_json("configs/hri_control.json")


class RoadmapTests(unittest.TestCase):
    def test_labels_match_geometry(self):
        self.assertEqual(ROAD.check_labels(), [])

    def test_next_and_command_toward(self):
        self.assertEqual(ROAD.next("J1", "LEFT"), "J2")
        self.assertIsNone(ROAD.next("J1", "FORWARD_LEFT"))
        self.assertEqual(ROAD.command_toward("J1", "E4"), "LEFT")
        self.assertEqual(ROAD.command_toward("J2", "E1"), "NONE")
        self.assertEqual(sorted(ROAD.endpoints()), ["E1", "E2", "E3", "E4"])

    def test_worker_stand_is_ahead_right_and_faces_back(self):
        x, z, yaw = ROAD.stand("J1")                     # arrival from A is +z, right is +x
        self.assertAlmostEqual(x, 8.75)
        self.assertAlmostEqual(z, 2.5)
        self.assertAlmostEqual(abs(yaw), 180.0)

    def test_controller_never_sees_the_goal(self):
        src = (HERE / "hri_control.py").read_text(encoding="utf-8")
        tree = ast.parse(src)
        calls = [n.func.attr for n in ast.walk(tree) if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)]
        self.assertNotIn("command_toward", calls)
        ctrl = [n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "Controller"][0]
        args = {a.arg for f in ctrl.body if isinstance(f, ast.FunctionDef) for a in f.args.args}
        self.assertFalse(args & {"goal", "goal_node", "b"})


class DialogTests(unittest.TestCase):
    def d(self):
        g = hc.GestureDialog(1.0, 5.0, 2)
        g.begin_ask(0.0)
        return g

    def test_hold_one_second(self):
        g = self.d()
        self.assertEqual(g.update("LEFT", 0.0, 0.0), "pending")
        self.assertEqual(g.update("LEFT", 0.9, 0.9), "pending")
        self.assertEqual(g.update("LEFT", 1.0, 1.05), "accepted")

    def test_change_or_none_restarts(self):
        g = self.d()
        g.update("LEFT", 0.0, 0.0)
        g.update("NONE", 0.5, 0.5)
        g.update("LEFT", 0.6, 0.6)
        self.assertEqual(g.update("LEFT", 1.5, 1.5), "pending")
        self.assertEqual(g.update("LEFT", 1.6, 1.6), "accepted")

    def test_stop_is_not_an_answer(self):
        g = self.d()
        for i in range(20):
            self.assertEqual(g.update("STOP", i * 0.1, i * 0.1), "pending")

    def test_short_none_gap_is_tolerated(self):
        g = hc.GestureDialog(1.0, 5.0, 2, max_none_gap_s=0.3)
        g.begin_ask(0.0)
        g.update("FORWARD", 0.0, 0.0)
        g.update("NONE", 0.1, 0.1)       # one missed frame
        g.update("FORWARD", 0.2, 0.2)
        self.assertEqual(g.update("FORWARD", 1.0, 1.0), "accepted")
        g.begin_ask(2.0)
        g.update("FORWARD", 2.0, 2.0)
        g.update("NONE", 2.5, 2.5)       # 0.5 s gap: restarts
        g.update("FORWARD", 2.6, 2.6)
        self.assertEqual(g.update("FORWARD", 3.0, 3.0), "pending")
        self.assertEqual(g.update("LEFT", 3.5, 3.5), "pending")    # a different answer always restarts

    def test_ask_once_more_then_abort(self):
        g = self.d()
        self.assertEqual(g.update("NONE", 5.0, 5.0), "ask_again")
        g.begin_ask(5.5)
        self.assertEqual(g.update("NONE", 10.5, 10.5), "abort")


class SteeringTests(unittest.TestCase):
    D = CFG["drive"]

    def test_straight_ahead(self):
        v, w, arrived = hc.pure_pursuit(0, 0, 0, [(0, 0), (0, 10)], self.D, 0.8, 0.1)
        self.assertAlmostEqual(v, 0.8)
        self.assertAlmostEqual(w, 0.0)
        self.assertFalse(arrived)

    def test_target_right_gives_negative_omega(self):   # REP-103: omega > 0 = left
        _, w, _ = hc.pure_pursuit(0, 0, 0, [(0, 0), (1, 10)], self.D, 0.8, 0.1)
        self.assertLess(w, 0.0)

    def test_behind_rotates_in_place(self):
        v, w, _ = hc.pure_pursuit(0, 0, 0, [(0, 0), (-5, -1)], self.D, 0.8, 0.1)
        self.assertEqual(v, 0.0)
        self.assertGreater(w, 0.0)

    def test_in_path(self):
        self.assertAlmostEqual(hc.stop_distance(0.8, CFG["safety"]), 1.89, places=2)
        self.assertLess(hc.stop_distance(CFG["drive"]["approach_speed_mps"], CFG["safety"]), CFG["dialog"]["approach_distance_m"])
        self.assertTrue(hc.in_path(0, 0, 0, 0.2, 1.0, 1.2, 0.6))
        self.assertFalse(hc.in_path(0, 0, 0, 0.0, 2.0, 1.2, 0.6))
        self.assertFalse(hc.in_path(0, 0, 0, 0.9, 0.5, 1.2, 0.6))
        self.assertFalse(hc.in_path(0, 0, 0, 0.0, -0.5, 1.2, 0.6))


def run(goal, seed=1, **kw):
    return hs.Simulator(hc.make_controller(), hs.SimConfig(**kw), seed=seed).run(goal)


class SimulatorTests(unittest.TestCase):
    def test_every_goal_with_perfect_perception(self):
        for g in ROAD.endpoints():
            r = run(g)
            self.assertEqual(r["outcome"], "SUCCESS", (g, r["abort_reason"], r["trace"][-3:]))
            self.assertLessEqual(r["final_distance_m"], 0.3)
            for j in r["junctions"]:
                self.assertEqual(j["read"], j["shown"])
                self.assertEqual(j["asks"], 1)

    def test_measured_detection_rate_and_noise(self):
        # 84 % panorama detection (Unity smoke run), distance bias and noise like the v1 dev evaluation.
        cov = {"LEFT": 0.95, "FORWARD_LEFT": 0.98, "FORWARD": 0.80, "FORWARD_RIGHT": 0.91, "RIGHT": 1.0}
        acc = {"FORWARD_LEFT": 0.93}
        for seed, g in enumerate(["E1", "E2", "E3", "E4"]):
            r = run(g, seed=seed, p_detect=0.84, distance_bias_m=0.28, distance_sigma_m=0.2, bearing_sigma_deg=1.0,
                    coverage=cov, accuracy=acc)
            self.assertEqual(r["outcome"], "SUCCESS", (g, r["abort_reason"]))

    def test_stop_gesture_halts_the_robot(self):
        r = run("E1", stop_gesture=(24.3, 27.3))   # during the dialog, while the pan-tilt camera looks at the worker
        self.assertEqual(r["outcome"], "SUCCESS")
        self.assertGreater(r["safety_stop_s"], 2.0)

    def test_person_in_path_stops_without_collision(self):
        r = run("E1", intruder={"t": 3.0, "x": 6.25, "z": -6.0})   # stands in the lane between A and J1
        self.assertEqual(r["outcome"], "FAILURE")
        self.assertEqual(r["failure_reason"], "timeout")             # it never drives through the person
        self.assertGreater(r["closest_person_m"], 0.65)
        self.assertGreater(r["safety_stop_s"], 100.0)

    def test_unclear_gesture_asks_again_then_aborts(self):
        r = run("E1", coverage={c: 0.0 for c in hc.DIRECTIONS})
        self.assertEqual(r["failure_reason"], "aborted")
        self.assertIn("gesture unclear after 2 asks", r["abort_reason"])
        self.assertEqual(r["junctions"][0]["asks"], 2)

    def test_second_ask_from_a_new_viewpoint(self):
        # The first ask position at J1 (on the 2.0 m circle, on the line to the worker) is a blind spot.
        wx, wz = ROAD.stand("J1")[:2]
        jx, jz = ROAD.pos("J1")
        n = math.hypot(jx - wx, jz - wz)
        spot = {"x": wx + (jx - wx) / n * 2.0, "z": wz + (jz - wz) / n * 2.0, "r": 0.25}
        r = run("E1", blind_spot=spot)
        self.assertEqual(r["outcome"], "SUCCESS", (r["abort_reason"], r["trace"][-6:]))
        self.assertEqual(r["junctions"][0]["asks"], 2)
        self.assertEqual(sum(s.endswith(":approach") for s in r["trace"]), 2)   # moved before asking again

    def test_detector_that_sees_nobody_aborts_at_the_junction(self):
        r = run("E1", p_detect=0.0)
        self.assertEqual(r["failure_reason"], "aborted")
        self.assertIn("no person found at J1", r["abort_reason"])

    def test_no_perception_results_never_drives_blind(self):
        r = run("E1", people_latency_s=1e6, timeout_s=30.0)          # no panorama result ever arrives
        self.assertEqual(r["outcome"], "FAILURE")
        self.assertLess(r["travelled_m"], 0.1)

    def test_wrong_reading_gives_wrong_goal(self):
        r = run("E2", accuracy={"RIGHT": 0.0})                      # RIGHT read as FORWARD_RIGHT: no such branch
        self.assertEqual(r["failure_reason"], "aborted")

    def test_reproducible(self):
        a = run("E3", seed=5, p_detect=0.84, distance_sigma_m=0.2)
        b = run("E3", seed=5, p_detect=0.84, distance_sigma_m=0.2)
        self.assertEqual((a["time_s"], a["final_distance_m"]), (b["time_s"], b["final_distance_m"]))


class StalePerceptionTests(unittest.TestCase):
    """The existing stale-perception stop (frozen safety.people_stale_s, unchanged) is what old perception results
    trigger now that inference runs on its own threads: exactly above the threshold, never at or below it."""

    def tick(self, age_s: float) -> hc.Controller:
        c = hc.make_controller()
        c.begin(0.0)
        self.assertEqual(c.state, "navigate")
        t = 10.0
        c.step(hc.TickInput(time_s=t, x=6.25, z=-10.0, yaw_deg=0.0, people=[], people_time_s=t - age_s))
        return c

    def test_stop_exactly_above_the_frozen_threshold(self):
        limit = CFG["safety"]["people_stale_s"]
        self.assertEqual(limit, 1.0)                              # frozen value (hri_frozen.json)
        self.assertEqual(self.tick(limit).safety_reason, "")
        self.assertEqual(self.tick(limit - 0.05).safety_reason, "")
        self.assertEqual(self.tick(limit + 0.001).safety_reason, "perception stale")
        self.assertEqual(self.tick(1.5).safety_reason, "perception stale")   # e.g. results held by a 1.5 s call

    def test_no_result_at_all_is_stale(self):
        c = hc.make_controller()
        c.begin(0.0)
        cmd = c.step(hc.TickInput(time_s=1.0, x=6.25, z=-10.0, yaw_deg=0.0, people_time_s=None))
        self.assertEqual((c.safety_reason, cmd.v), ("perception stale", 0.0))


if __name__ == "__main__":
    unittest.main()
