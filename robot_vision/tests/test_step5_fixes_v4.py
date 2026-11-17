"""AUDIT.md 16.19.2 items D and E (2026-11-17), v4 only:
D  before taking a branch the robot returns to the junction point (dialog.return_to_junction);
E  person-in-path recovery: after 15 s stopped behind a person who moved less than 0.3 m, back up 1.0 m at -0.2 m/s (rear check), go past them
   on the clear side at 1.0 m, at most 2 attempts per person, then wait as v3 does. The v3 stop itself is unchanged.
The robot is driven by the simulator's own speed ramp (hri_sim_v4._ramp, SimConfig limits) with scripted people."""

import ast
import json
import math
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))

import commander_v4 as cm  # noqa: E402
import hri_control as hc  # noqa: E402
import hri_control_v4 as hv  # noqa: E402
import hri_sim_v4 as sv  # noqa: E402
from hri_sim import SimConfig  # noqa: E402

ROAD_X = 6.25                                    # the road A -> J1 of the v4 map runs north along x = 6.25 (A at z = -20, J1 at z = 0)


def make(recovery=True, return_to_junction=True):
    base, v4 = hv.load_control()
    v4["recovery"]["enabled"] = recovery
    v4["dialog"]["return_to_junction"] = return_to_junction
    return hv.ControllerV4(base, v4, cm.load_config(), hv.load_roadmap())


def drive(c, people_at, seconds, x=ROAD_X, z=-12.0, yaw=0.0, dt=0.1, start="navigate", with_robot=False):
    """Step the controller with the simulator's kinematics; people_at(t) (or people_at(t, (x, z, yaw)) with with_robot) -> [(track id, (x, z))] seen
    by the 360 camera. Returns the trail."""
    cfg = SimConfig()
    c.reset(0.0)
    c.begin(0.0)
    if start == "navigate":
        c._navigate("J1", 0.0)
    else:                                         # "execute": at the ask position, the branch to E1 accepted at J1
        c.node, c.next_node = "J1", "E1"
        c._set("execute", 0.0)
    v = w = t = 0.0
    trail = []
    while t < seconds:
        seen = people_at(t, (x, z, yaw)) if with_robot else people_at(t)
        ppl = [{"x": px, "z": pz, "distance_m": math.hypot(px - x, pz - z), "bearing_deg": 0.0, "track_id": tid} for tid, (px, pz) in seen]
        inp = hv.TickInputV4(time_s=t, x=x, z=z, yaw_deg=yaw, v=v, omega=w, people=ppl, people_time_s=t, persons=[], persons_time_s=t)
        cmd = c.step(inp)
        v = sv._ramp(v, max(-1.0, min(1.0, cmd.v)), cfg.max_accel_mps2, cfg.decel_mps2, dt)
        w = sv._ramp(w, max(-1.0, min(1.0, cmd.omega)), cfg.max_angular_accel_radps2, cfg.max_angular_accel_radps2, dt)
        yaw = hc.wrap(yaw - math.degrees(w * dt))
        x, z = x + math.sin(math.radians(yaw)) * v * dt, z + math.cos(math.radians(yaw)) * v * dt
        trail.append({"t": round(t, 2), "x": x, "z": z, "v": v, "state": cmd.state})
        t += dt
    return trail


def events(c, *names):
    return [d for d in c.decisions if not names or d["event"] in names]


def dist(row, p):
    return math.hypot(row["x"] - p[0], row["z"] - p[1])


STAND = (ROAD_X, -8.0)                           # a worker standing on the road, 8 m before J1


class ReturnToJunction(unittest.TestCase):
    def run_execute(self, on):
        c = make(recovery=False, return_to_junction=on)
        trail = drive(c, lambda t: [], 70, x=8.75, z=0.5, yaw=-90.0, start="execute")       # 2.5 m east of J1, facing west, branch FORWARD to E1
        return c, trail

    def test_the_robot_goes_to_the_junction_point_before_the_branch(self):
        c, trail = self.run_execute(True)
        self.assertLess(min(dist(r, (ROAD_X, 0.0)) for r in trail), 0.35)               # it reached the junction point (arrive_junction_m 0.3)
        self.assertEqual(len(events(c, "returned_to_junction")), 1)
        i = next(k for k, r in enumerate(trail) if dist(r, (ROAD_X, 0.0)) < 0.35)
        self.assertTrue(all(abs(r["x"] - ROAD_X) < 0.6 for r in trail[i + 40:]))        # then straight along the branch to E1
        self.assertGreater(trail[-1]["z"], 5.0)

    def test_without_the_switch_it_leaves_from_where_it_stands_as_before(self):
        c, trail = self.run_execute(False)
        self.assertGreater(min(dist(r, (ROAD_X, 0.0)) for r in trail), 1.0)             # the earlier behaviour: it never touches the junction point
        self.assertEqual(events(c, "returned_to_junction"), [])

    def test_the_target_sent_to_unity_is_the_junction_point_first(self):
        c = make()
        c.reset(0.0)
        c.node, c.next_node = "J1", "E1"
        c._set("execute", 0.0)
        self.assertEqual(c._target(), c.road.pos("J1"))
        c._returned = True
        self.assertEqual(c._target(), c.road.pos("E1"))


class Recovery(unittest.TestCase):
    def test_without_recovery_the_person_in_path_stop_holds_for_good(self):
        c = make(recovery=False)
        trail = drive(c, lambda t: [(1, STAND)], 90)
        self.assertIn("stopped: person in path", trail[-1]["state"])
        self.assertLess(trail[-1]["z"], STAND[1])                                       # never got past them
        self.assertEqual(events(c), [])

    def test_after_15_s_it_backs_1_m_slowly_and_goes_around_on_the_clear_side(self):
        c = make()
        trail = drive(c, lambda t: [(1, STAND)], 110)
        stop = next(r for r in trail if "person in path" in r["state"] and r["v"] < 0.03)
        start = events(c, "recovery_started")[0]
        self.assertGreaterEqual(start["t"] - next(r["t"] for r in trail if "person in path" in r["state"]), 15.0 - 0.3)    # only after 15 s stopped
        self.assertEqual((start["attempt"], start["side"]), (1, "right"))
        back = [r for r in trail if "recovery: backing" in r["state"]]
        self.assertTrue(back)
        self.assertGreaterEqual(math.hypot(back[-1]["x"] - stop["x"], back[-1]["z"] - stop["z"]), 0.95)    # 1.0 m back (it stops after the command)
        self.assertGreaterEqual(min(r["v"] for r in trail), -0.2 - 1e-6)                # never faster than 0.2 m/s backwards
        self.assertLess(min(r["v"] for r in trail), -0.15)
        d_back = [dist(r, STAND) for r in back]
        self.assertEqual(d_back, sorted(d_back))                                         # backing only ever increases the distance to the person
        after = trail[trail.index(back[-1]):]
        self.assertGreaterEqual(min(dist(r, STAND) for r in after), 0.85)               # never inside the standstill stop zone while going around
        self.assertGreater(max(r["x"] for r in after[:300]), ROAD_X + 0.6)             # it really went to the right
        self.assertEqual(c.route[-1], "J1")                                              # and on to the junction
        self.assertEqual(c.summary()["v4"]["recoveries"], 1)
        self.assertEqual([d["event"] for d in events(c)][:2], ["recovery_started", "recovery_detour"])

    def test_the_left_side_when_the_right_is_taken(self):
        c = make()
        trail = drive(c, lambda t: [(1, STAND), (2, (ROAD_X + 1.0, -8.0))], 110)         # somebody stands on the right waypoint
        self.assertEqual(events(c, "recovery_started")[0]["side"], "left")
        self.assertEqual(c.route[-1], "J1")
        self.assertGreaterEqual(min(dist(r, (ROAD_X + 1.0, -8.0)) for r in trail[trail.index(next(r for r in trail if "backing" in r["state"])):]), 0.85)

    def test_nobody_behind_the_robot_is_a_rule_of_the_back_up(self):
        c = make()
        # the robot stops 0.85 m before the person (z -8.85); from t = 8 s a second person stands 1.5 m behind it, inside the back-up reach (1.0 + 0.99 m)
        trail = drive(c, lambda t: [(1, STAND)] + ([(3, (ROAD_X, -10.35))] if t >= 8.0 else []), 90)
        self.assertEqual(events(c, "recovery_started"), [])
        self.assertEqual(len(events(c, "recovery_waiting")), 1)                          # logged once, not every tick
        self.assertTrue(all(r["v"] > -0.01 for r in trail))                              # it never reversed
        self.assertIn("stopped: person in path", trail[-1]["state"])

    def test_a_person_who_moves_is_waited_for_not_driven_around(self):
        def swing(t):
            return [(1, (ROAD_X, -8.0 + 0.45 * (0.5 - 0.5 * math.cos(t / 4.0))))]         # drifts 0.45 m along the road and back, still in the path
        c = make()
        drive(c, swing, 90)
        self.assertEqual(events(c, "recovery_started"), [])

    def test_no_clear_side_means_no_back_up(self):
        c = make()
        drive(c, lambda t: [(1, STAND), (2, (ROAD_X + 1.0, -8.0)), (3, (ROAD_X - 1.0, -8.0))], 90)
        self.assertEqual(events(c, "recovery_started"), [])
        self.assertEqual(len(events(c, "recovery_waiting")), 1)

    def test_two_attempts_per_person_then_the_robot_waits_as_v3_does(self):
        """The same track blocks again after each detour (it steps 1.2 m in front of the robot): a first and a second recovery start, a third does not."""
        c = make()
        st = {"moves": 0, "pos": STAND}

        def people(t, robot):
            x, z, yaw = robot
            if st["moves"] < 2 and z > st["pos"][1] + 2.0:                               # the robot has gone around: the same person steps in front of it again
                st["moves"] += 1
                a = math.radians(yaw)
                st["pos"] = (x + math.sin(a) * 1.2, z + math.cos(a) * 1.2)
            return [(1, st["pos"])]

        trail = drive(c, people, 400, with_robot=True)
        self.assertEqual([d["attempt"] for d in events(c, "recovery_started")], [1, 2])   # the third time it does not start
        self.assertEqual(st["moves"], 2)
        self.assertIn("stopped: person in path", trail[-1]["state"])
        self.assertEqual(c.rec_attempts[1], 2)
        self.assertLess(trail[-1]["z"], 0.0)                                                # waiting, not at the junction

    def test_the_v3_controller_is_not_changed(self):
        self.assertFalse(hasattr(hc.Controller, "_recovery"))
        base, _ = hv.load_control()
        self.assertEqual(hc.load_json("configs/hri_control.json")["safety"]["corridor_half_width_m"], 0.6)       # the v3 stop numbers are as they were
        self.assertEqual(base["safety"]["body_and_person_m"], 0.65)


class Config(unittest.TestCase):
    FILES = [ROOT / "configs/v4/control.json", ROOT / "configs/v4/control_zoom_on.json", ROOT / "configs/v4/control_zoom_off.json"] + \
        sorted((ROOT / "configs/v4/experiments").glob("control_lie_*.json"))

    def test_every_control_file_declares_the_accepted_numbers(self):
        self.assertEqual(len(self.FILES), 11)
        for f in self.FILES:
            d = json.loads(f.read_text(encoding="utf-8"))
            r = d["recovery"]
            self.assertEqual({k: r[k] for k in ("enabled", "blocked_s", "person_moved_max_m", "back_m", "back_speed_mps", "side_m", "beyond_m", "max_attempts")},
                             {"enabled": True, "blocked_s": 15.0, "person_moved_max_m": 0.3, "back_m": 1.0, "back_speed_mps": 0.2, "side_m": 1.0,
                              "beyond_m": 1.0, "max_attempts": 2}, f.name)
            self.assertIn("DECIDED 2026-11-17", r["why"]["declared"])
            self.assertIn("NavMesh rack fix", r["why"]["declared"])
            self.assertIs(d["dialog"]["return_to_junction"], True, f.name)

    def test_the_controller_never_reads_the_ground_truth_grid(self):
        tree = ast.parse((ROOT / "hri_control_v4.py").read_text(encoding="utf-8"))
        mods = {a.name.split(".")[0] for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names}
        mods |= {n.module.split(".")[0] for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) and n.module}
        self.assertFalse(mods & {"gt_path", "gesture_data", "hri_eval_dev_v4", "export_csv_v4"})


if __name__ == "__main__":
    unittest.main()
