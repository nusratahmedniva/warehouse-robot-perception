"""The side view (AUDIT.md 16.26 item 2, 4a): a raised arm that fails the POINT cue on length or elbow is read again from the viewpoint whose line of sight is perpendicular to the
BACK axis (rotation round the worker clamped to 60 to 90 degrees), once per ask, never closer than 2.0 m, clear of other people. Off by default."""

import math
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import commander_v4 as cm  # noqa: E402
import gesture_motion as gm  # noqa: E402
import hri_control as hc  # noqa: E402
import hri_control_v4 as hv  # noqa: E402

W = (10.25, 2.5)                                      # a worker beside J1's arrival road (heading north, the road at x = 6.25), 4.0 m to the right


def controller(**sv):
    base, v4 = hv.load_control()
    v4["side_view"] = {"enabled": True, **sv}
    c = hv.ControllerV4(base, v4, cm.load_config(), hv.load_roadmap())
    c.begin(0.0)
    c.node = "J1"
    c.person = W
    return c


def inp(x, z, people=()):
    return hv.TickInputV4(time_s=5.0, x=x, z=z, yaw_deg=0.0, people_time_s=5.0, persons_time_s=5.0,
                          people=[{"x": px, "z": pz, "track_id": 10 + i, "distance_m": 1.0, "bearing_deg": 0.0} for i, (px, pz) in enumerate(people)])


class Geometry(unittest.TestCase):
    def test_off_by_default_and_refusals(self):
        base, v4 = hv.load_control()
        self.assertFalse(hv.ControllerV4(base, v4, cm.load_config(), hv.load_roadmap()).sv["enabled"])
        self.assertEqual(hv.SIDE_VIEW_DEFAULTS, {"enabled": False, "rotation_min_deg": 60.0, "rotation_max_deg": 90.0, "waypoint_step_deg": 30.0, "keep_m": None})
        with self.assertRaisesRegex(ValueError, "side_view"):
            controller(rotation_min_deg=100.0)
        with self.assertRaisesRegex(ValueError, "side_view"):
            controller(waypoint_step_deg=0.0)

    def test_the_back_axis_is_the_arrival_road_at_a_junction_and_the_way_to_the_junction_at_a_checkpoint(self):
        c = controller()
        self.assertAlmostEqual(abs(hc.wrap(c._back_axis_yaw() - 180.0)), 0.0, places=6)        # J1 was reached from A, due south
        c.cp = {"junction": "J1", "branch": "RIGHT", "next": "J3", "point": (12.25, 0.0), "stage": "dialog"}
        self.assertAlmostEqual(abs(hc.wrap(c._back_axis_yaw() - 270.0)), 0.0, places=6)        # from the spot back west to J1

    def test_the_viewpoint_is_perpendicular_to_the_axis_on_the_road_side(self):
        c = controller()
        plan, why = c._side_view_plan(inp(10.25, 0.5), c._back_axis_yaw())                      # the robot due south of the worker, 2.0 m away
        self.assertEqual(why, "")
        self.assertAlmostEqual(plan["rotation_deg"], 90.0, places=4)
        self.assertAlmostEqual(plan["target"][0], 8.25, places=6)                                # west of the worker: the road side, looking east
        self.assertAlmostEqual(plan["target"][1], 2.5, places=6)
        sight = hc.yaw_to(*plan["target"], *W)
        self.assertAlmostEqual(abs(hc.wrap(sight - 180.0)), 90.0, places=4)                      # the line of sight is 90 degrees to the BACK axis: a BACK is mid-band

    def test_the_rotation_is_clamped_to_60_to_90(self):
        c = controller()
        sw = (W[0] + 2.0 * math.sin(math.radians(225.0)), W[1] + 2.0 * math.cos(math.radians(225.0)))        # 45 degrees from the perpendicular: clamped up to 60
        plan, _ = c._side_view_plan(inp(*sw), c._back_axis_yaw())
        self.assertAlmostEqual(abs(plan["rotation_deg"]), 60.0, places=4)
        self.assertAlmostEqual(abs(plan["perpendicular_deg"]), 45.0, places=3)
        far = (W[0] + 2.0 * math.sin(math.radians(150.0)), W[1] + 2.0 * math.cos(math.radians(150.0)))      # 120 degrees from it: clamped down to 90
        plan2, _ = c._side_view_plan(inp(*far), c._back_axis_yaw())
        self.assertAlmostEqual(abs(plan2["rotation_deg"]), 90.0, places=4)
        for plan_ in (plan, plan2):
            self.assertAlmostEqual(math.dist(plan_["target"], W), 2.0, places=6)

    def test_the_way_never_gets_closer_than_the_ask_distance(self):
        c = controller()
        plan, _ = c._side_view_plan(inp(10.25, 0.5), c._back_axis_yaw())
        pts = [(10.25, 0.5)] + plan["waypoints"] + [plan["target"]]
        self.assertEqual(len(plan["waypoints"]), 3)                                              # 90 degrees in three arcs of 30
        for a, b in zip(pts, pts[1:]):
            for f in (0.0, 0.25, 0.5, 0.75, 1.0):
                q = (a[0] + f * (b[0] - a[0]), a[1] + f * (b[1] - a[1]))
                self.assertGreaterEqual(math.dist(q, W), 2.0 - 1e-6)

    def test_somebody_in_the_way_blocks_it(self):
        c = controller()
        plan, why = c._side_view_plan(inp(10.25, 0.5, people=[(8.25, 3.0)]), c._back_axis_yaw())      # 0.5 m from the viewpoint
        self.assertIsNone(plan)
        self.assertIn("within 1.2 m", why)
        ok, _ = c._side_view_plan(inp(10.25, 0.5, people=[(8.25, 5.0)]), c._back_axis_yaw())
        self.assertIsNotNone(ok)
        wide, _ = controller(keep_m=3.0)._side_view_plan(inp(10.25, 0.5, people=[(8.25, 5.0)]), 180.0)
        self.assertIsNone(wide)


class Trigger(unittest.TestCase):
    def ready(self, **sv):
        c = controller(**sv)
        c.sv_since = 4.0
        return c

    def test_conditions_and_once_per_ask(self):
        c = self.ready()                                                           # the frame time of inp is 5.0, the failure has lasted 1.0 s >= gesture_hold_s 0.5
        c.last_point_fail = "length"
        self.assertTrue(c._start_side_view(inp(10.25, 0.5), 5.0))
        self.assertEqual(c.state, "approach")
        self.assertEqual(c.free_asks, 1)
        self.assertIsNotNone(c.approach_point)
        self.assertEqual(len(c.detour), 3)
        self.assertEqual(len(c.side_views), 1)
        self.assertEqual(c.summary()["v4"]["side_views"][0]["rotation_deg"], 90.0)
        c.sv_since = 4.0
        self.assertFalse(c._start_side_view(inp(10.25, 0.5), 6.0))                 # once per ask
        c._ask(6.0, hv.CommandV4())                                                # a new ask (the free one is used first)
        c._ask(7.0, hv.CommandV4())
        self.assertFalse(c.side_view_used)                                         # a real ask allows one again

    def test_not_when_off_when_too_recent_when_waiting_or_blocked(self):
        c = self.ready()
        c.sv["enabled"] = False
        self.assertFalse(c._start_side_view(inp(10.25, 0.5), 5.0))
        c = self.ready()
        c.sv_since = 4.8
        self.assertFalse(c._start_side_view(inp(10.25, 0.5), 5.0))                 # the failure has lasted 0.2 s < gesture_hold_s
        c = self.ready()
        c.waiting = True
        self.assertFalse(c._start_side_view(inp(10.25, 0.5), 5.0))
        c = self.ready()
        self.assertFalse(c._start_side_view(inp(10.25, 0.5, people=[(8.25, 3.0)]), 5.0))      # blocked: logged, and not tried again for this ask
        self.assertTrue(c.side_view_used)
        self.assertEqual([d["event"] for d in c.decisions if d["event"].startswith("side_view")], ["side_view_blocked"])


def person(tid, bearing, fail="length", command="NONE", raised=True, moving=False, facing=True):
    r = gm.Reading(command, 0.0, "x", 5.0, arm="right" if raised else None, frame_class="NONE", moving=moving, raised=raised, hold_s=1.0, valid_frames=8, n_frames=10)
    r.point_fail = fail
    return cm.PersonReading(tid, bearing, facing, "facing" if facing else "turned away", r)


class TriggerFromTheFrames(unittest.TestCase):
    """AUDIT.md 16.26.6: the trigger is evaluated from the person being asked, not only from a selected commander (a held arm that fails the cue reads NONE and is never one)."""

    def frame(self, persons, x=10.25, z=0.5):
        c = controller()
        i = inp(x, z)
        i.persons = persons
        return c, i

    def test_a_held_arm_that_fails_the_cue_starts_the_clock_though_nobody_is_the_commander(self):
        c, i = self.frame([person(7, 0.0)])                                        # the robot due south of the worker: the worker is straight ahead
        self.assertEqual(c._interpret(i), "NONE")
        self.assertIsNone(c.commander_pt)                                          # still no commander
        self.assertEqual((c.sv_since, c.last_point_fail), (5.0, "length"))

    def test_only_the_person_asked_counts(self):
        c, i = self.frame([person(7, 40.0)])                                       # 40 degrees off the direction of the worker the robot approached (link tolerance 10)
        c._interpret(i)
        self.assertIsNone(c.sv_since)
        c, i = self.frame([person(7, 40.0), person(8, 4.0)])                       # the second is the worker
        c._interpret(i)
        self.assertEqual(c.sv_since, 5.0)

    def test_the_clock_needs_a_facing_raised_arm_that_fails_the_cue_unread(self):
        for kw in ({"facing": False}, {"raised": False}, {"fail": ""}, {"command": "POINT"}, {"command": "WAIT"}):
            c, i = self.frame([person(7, 0.0, **kw)])
            c._interpret(i)
            self.assertIsNone(c.sv_since, kw)

    def test_a_moving_commander_still_counts_and_the_clock_runs_once(self):
        c, i = self.frame([person(7, 30.0, moving=True)])                          # the commander (a mover), far from the asked direction: its own reading counts
        c._interpret(i)
        self.assertEqual(c.commander_pt, 7)
        self.assertEqual(c.sv_since, 5.0)
        i2 = inp(10.25, 0.5)
        i2.persons, i2.time_s, i2.persons_time_s = [person(7, 30.0, moving=True)], 5.2, 5.2
        c._interpret(i2)
        self.assertEqual(c.sv_since, 5.0)                                          # not restarted

    def test_off_means_off(self):
        c, i = self.frame([person(7, 0.0)])
        c.sv["enabled"] = False
        c._interpret(i)
        self.assertIsNone(c.sv_since)


if __name__ == "__main__":
    unittest.main()
