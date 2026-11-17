"""dialog.return_speed_mps (AUDIT.md 16.20.5, 2026-11-17): the return to the junction point (D, 16.19) drives at the cruise speed 0.8 m/s instead of the approach speed 0.4 m/s;
absent = the earlier behaviour. v4 only: v3 and hri_control.json are untouched."""

import json
import statistics
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
from test_step5_fixes_v4 import ROAD_X, dist, drive, events  # noqa: E402

FILES = [ROOT / "configs/v4/control.json", ROOT / "configs/v4/control_zoom_on.json", ROOT / "configs/v4/control_zoom_off.json"] + \
        sorted((ROOT / "configs/v4/experiments").glob("control_lie_*.json"))


def make(speed="config", return_to_junction=True):
    base, v4 = hv.load_control()
    v4["recovery"]["enabled"] = False
    v4["dialog"]["return_to_junction"] = return_to_junction
    if speed is None:
        v4["dialog"].pop("return_speed_mps", None)
    elif speed != "config":
        v4["dialog"]["return_speed_mps"] = speed
    return hv.ControllerV4(base, v4, cm.load_config(), hv.load_roadmap())


class Config(unittest.TestCase):
    def test_every_control_file_has_the_cruise_speed_and_its_reason(self):
        self.assertEqual(len(FILES), 11)
        cruise = hc.load_json("configs/hri_control.json")["drive"]["cruise_speed_mps"]
        self.assertEqual(cruise, 0.8)
        for f in FILES:
            d = json.loads(f.read_text(encoding="utf-8"))["dialog"]
            self.assertEqual(d["return_speed_mps"], cruise, f.name)
            self.assertTrue(d["return_to_junction"], f.name)
            self.assertIn("DECIDED 2026-11-17", d["why"]["return_speed_mps"])
            self.assertIn("16.20.5", d["why"]["return_speed_mps"])

    def test_v3_is_untouched(self):
        self.assertNotIn("return_speed", (ROOT / "hri_control.py").read_text(encoding="utf-8"))
        self.assertNotIn("return_speed", (ROOT / "configs/hri_control.json").read_text(encoding="utf-8"))
        self.assertEqual(hc.load_json("configs/hri_control.json")["drive"]["approach_speed_mps"], 0.4)

    def test_a_value_above_the_cruise_speed_or_not_positive_is_refused(self):
        for bad in (0.0, -0.4, 0.81, 2.0):
            with self.assertRaisesRegex(ValueError, "return_speed_mps"):
                make(bad)
        make(0.8)
        make(0.4)
        make(None)


class Drive(unittest.TestCase):
    """Execute at J1 from 5 m south of the junction point, no people; the robot's own speed ramp."""

    def go(self, speed):
        c = make(speed)
        trail = drive(c, lambda t: [], 40, x=ROAD_X, z=-5.0, yaw=0.0, start="execute")
        return c, trail

    def test_the_return_is_faster_and_the_peak_speed_follows_the_key(self):
        _, fast = self.go("config")
        _, slow = self.go(None)
        t_fast = next(r["t"] for r in fast if dist(r, (ROAD_X, 0.0)) < 0.35)
        t_slow = next(r["t"] for r in slow if dist(r, (ROAD_X, 0.0)) < 0.35)
        self.assertLess(t_fast, t_slow - 3.0)
        self.assertGreater(max(r["v"] for r in fast), 0.7)
        self.assertLessEqual(max(r["v"] for r in fast), 0.8 + 1e-9)
        self.assertLessEqual(max(r["v"] for r in slow[:int(t_slow / 0.1)]), 0.4 + 1e-9)       # absent = the approach speed, as before

    def test_absent_equals_the_explicit_approach_speed(self):
        _, a = self.go(None)
        _, b = self.go(0.4)
        self.assertEqual([(r["x"], r["z"]) for r in a], [(r["x"], r["z"]) for r in b])

    def test_it_still_reaches_the_junction_point_and_goes_on_along_the_branch(self):
        c, trail = self.go("config")
        self.assertEqual(len(events(c, "returned_to_junction")), 1)
        self.assertGreater(trail[-1]["z"], 5.0)

    def test_it_changes_the_return_only(self):
        """The approach to a person and the navigation use the same speeds as before (the key is read in the return branch only)."""
        c = make("config")
        trail = drive(c, lambda t: [], 20, x=ROAD_X, z=-12.0, start="navigate")
        c0 = make(None)
        trail0 = drive(c0, lambda t: [], 20, x=ROAD_X, z=-12.0, start="navigate")
        self.assertEqual([(r["x"], r["z"]) for r in trail], [(r["x"], r["z"]) for r in trail0])


class InTheSimulator(unittest.TestCase):
    def run_e5(self, speed):
        import analyse_a3_timeouts_v4 as a3
        scen = a3.scenarios("old")

        def hook(c):
            if speed is None:
                c.v4["dialog"].pop("return_speed_mps", None)
        sc = sv.scenario_ab("A3", 4, sv.DETECTION_ON, scen=scen, hook=hook, sim_cfg=sv.SimConfig(timeout_s=600.0))
        r = sc["sim"].run(sc["goal"])
        return r, a3.visits({**r, "_road": sc["road"]})

    def test_the_e5_run_of_a3_fits_the_270_s_floor_on_the_old_slots_only_with_the_key(self):
        fast, vf = self.run_e5("config")
        slow, vs = self.run_e5(None)
        self.assertEqual((fast["outcome"], fast["time_s"]), ("SUCCESS", 254.7))
        self.assertEqual((slow["outcome"], slow["time_s"]), ("SUCCESS", 270.3))
        self.assertLess(statistics.median(x["return_s"] for x in vf), 9.0)
        self.assertGreater(statistics.median(x["return_s"] for x in vs), 12.0)
        self.assertEqual(fast["closest_person_m"], slow["closest_person_m"])


if __name__ == "__main__":
    unittest.main()
