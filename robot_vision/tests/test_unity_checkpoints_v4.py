"""The checkpoint positions Nusrat sent and the ask from beside (AUDIT.md 16.26 item 1, 2026-11-19). Simulator and controller only.

Pinned: positions.csv's seven rows (SHA-256 c2026823...34d3) as configs/v4/experiments/checkpoints_unity.json; the spot of a branch = the junction plus s_m along it (the anchor
of the file); the controller key lie_detection.checkpoint_s_m (default none = the fraction) and its refusal; the runner's T4 carries it; the placement rules hold for A3 and A4
(check_checkpoints_v4); and in the runs the robot asks from 2.0 m across, the worker at 90 degrees to the road."""

import json
import math
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import check_checkpoints_v4 as cc  # noqa: E402
import commander_v4 as cm  # noqa: E402
import hri_control as hc  # noqa: E402
import hri_control_v4 as hv  # noqa: E402
import hri_sim as hs  # noqa: E402
import hri_sim_v4 as sv  # noqa: E402
import run_t3_v4 as rn  # noqa: E402

CPU = json.loads((ROOT / "configs/v4/experiments/checkpoints_unity.json").read_text(encoding="utf-8"))
# positions.csv, as sent: branch -> (s_m, right_m, x, z, anchor_x, anchor_z)
CSV = {"J1>FORWARD": (15.5, -4.0, 2.25, 15.5, 6.25, 15.5), "J1>RIGHT": (6.0, 4.0, 12.25, -4.0, 12.25, 0.0), "J2>RIGHT": (15.5, -4.0, -10.25, 15.5, -6.25, 15.5),
       "J3>LEFT": (15.5, -4.0, 14.75, 15.5, 18.75, 15.5), "J3>RIGHT": (14.5, -4.5, 23.25, -14.5, 18.75, -14.5), "J4>LEFT": (15.5, -4.0, -14.75, -15.5, -18.75, -15.5),
       "J4>RIGHT": (14.5, -4.5, -23.25, 14.5, -18.75, 14.5)}
T4U = rn.detection_for("T4", "on", CPU)


class PositionsFile(unittest.TestCase):
    def test_the_seven_rows_and_their_source(self):
        self.assertEqual(CPU["source"]["sha256"], "c20268236950485cd98b773fbbc65fbe1329fc57cf32957ddb2c2aefed9534d3")
        self.assertEqual(CPU["branches"], list(CSV))
        self.assertNotIn("J1>LEFT", CPU["positions"])                                 # no checkpoint on J1 to J2 and none on J2 to J4
        self.assertNotIn("J2>FORWARD", CPU["positions"])
        for k, (s, r, x, z, ax, az) in CSV.items():
            p = CPU["positions"][k]
            self.assertEqual((p["s_m"], p["right_m"], p["x"], p["z"], p["anchor"]), (s, r, x, z, [ax, az]), k)

    def test_the_arithmetic_of_the_file_is_consistent_with_the_map(self):
        road = hc.Roadmap(hc.load_json("configs/v4/roadmap.json"))
        for k, p in CPU["positions"].items():
            j, cmd = k.split(">")
            (x0, z0), (x1, z1) = road.pos(j), road.pos(road.next(j, cmd))
            length = math.hypot(x1 - x0, z1 - z0)
            ux, uz = (x1 - x0) / length, (z1 - z0) / length
            self.assertAlmostEqual(x0 + p["s_m"] * ux, p["anchor"][0], places=6, msg=k)           # the anchor is s_m along the branch
            self.assertAlmostEqual(z0 + p["s_m"] * uz, p["anchor"][1], places=6, msg=k)
            rx, rz = uz, -ux                                                                       # the right of the travel direction (x right, z up: (cos, -sin) of the heading)
            self.assertAlmostEqual(p["anchor"][0] + p["right_m"] * rx, p["x"], places=6, msg=k)    # the worker is right_m beside the anchor
            self.assertAlmostEqual(p["anchor"][1] + p["right_m"] * rz, p["z"], places=6, msg=k)
            self.assertLess(p["s_m"], length)
            self.assertLessEqual(abs(p["right_m"]), 4.7)                                           # R = 5.0 m of 16.25 holds (4.7 + 0.3 stop tolerance)


class ControllerKey(unittest.TestCase):
    def controller(self, **ld):
        base, v4 = hv.load_control()
        v4["lie_detection"] = {**v4["lie_detection"], **T4U, **ld}
        return hv.ControllerV4(base, v4, cm.load_config(), hv.load_roadmap())

    def test_default_is_none_and_no_shipped_control_file_has_it_yet(self):
        self.assertIsNone(hv.LIE_DEFAULTS["checkpoint_s_m"])
        for f in sorted((ROOT / "configs/v4").rglob("*.json")):
            if f.name == "checkpoints_unity.json":
                continue
            self.assertNotIn("checkpoint_s_m", json.loads(f.read_text(encoding="utf-8")).get("lie_detection", {}), f.name)

    def test_the_spot_is_the_anchor_and_the_fraction_is_the_fallback(self):
        c = self.controller()
        road = c.road
        for k, (s, r, x, z, ax, az) in CSV.items():
            j, cmd = k.split(">")
            pt = c._cp_point(j, road.next(j, cmd))
            self.assertAlmostEqual(pt[0], ax, places=9, msg=k)
            self.assertAlmostEqual(pt[1], az, places=9, msg=k)
        self.assertEqual(sorted(c._cp_spots()), sorted(tuple(k.split(">")) for k in CSV))
        no_table = self.controller(checkpoint_s_m=None)                                          # the fraction: the midpoint
        self.assertEqual(no_table._cp_point("J1", "E1"), (6.25, 10.0))
        partial = self.controller(checkpoint_s_m={"J1>FORWARD": 15.5})
        self.assertEqual(partial._cp_point("J1", "E1"), (6.25, 15.5))
        self.assertEqual(partial._cp_point("J1", "J3"), (12.5, 0.0))                              # not in the table: the midpoint

    def test_an_entry_outside_the_branch_is_refused_and_one_for_another_map_is_ignored(self):
        with self.assertRaisesRegex(ValueError, "checkpoint_s_m"):
            self.controller(checkpoint_s_m={"J1>FORWARD": 25.0})
        with self.assertRaisesRegex(ValueError, "checkpoint_s_m"):
            self.controller(checkpoint_s_m={"J1>FORWARD": 0.0})
        self.assertIsNotNone(self.controller(checkpoint_s_m={"J9>FORWARD": 50.0}))                  # a node this map does not have: ignored (the table is the deployment's)

    def test_the_runners_t4_carries_the_table_only_with_positions(self):
        self.assertEqual(T4U["checkpoint_s_m"], {k: v[0] for k, v in CSV.items()})
        provisional = json.loads((ROOT / "configs/v4/experiments/checkpoints.json").read_text(encoding="utf-8"))
        self.assertNotIn("checkpoint_s_m", rn.detection_for("T4", "on", provisional))
        self.assertNotIn("checkpoint_s_m", rn.detection_for("T0", "on", CPU))
        self.assertNotIn("checkpoint_s_m", rn.detection_for("T4", "off", CPU))


class Placement(unittest.TestCase):
    def test_the_positions_are_the_plan_in_every_seed_and_both_layouts(self):
        want = {tuple(k.split(">")): (v[2], v[3]) for k, v in CSV.items()}
        for name in ("A3", "A4"):
            for seed in (1, 7, 20):
                sc = sv.scenario_ab(name, seed, T4U, checkpoints=CPU)
                sim = sc["sim"]
                sim._plan, sim._cp_plan = {}, {}
                sim._cp_plan = sim.plan_checkpoints()
                self.assertEqual({k: (v["x"], v["z"]) for k, v in sim._cp_plan.items()}, want, (name, seed))

    def test_every_placement_rule_holds_for_every_checkpoint_in_a3_and_a4(self):
        rows = {"A3": cc.measure("A3", 1, CPU), "A4": [r for s in range(1, 9) for r in cc.measure("A4", s, CPU)]}
        for name, rs in rows.items():
            v = cc.verdicts(cc.summarise(rs))
            self.assertEqual(v, {k: True for k in v}, name)
            self.assertEqual(len(cc.summarise(rs)), 7, name)

    def test_the_across_point_is_2_m_from_the_worker_on_the_perpendicular(self):
        sc = sv.scenario_ab("A3", 1, T4U, checkpoints=CPU)
        sim = sc["sim"]
        sim._plan, sim._cp_plan = {}, {}
        sim._cp_plan = sim.plan_checkpoints()
        for (j, cmd), v in sim._cp_plan.items():
            a = sv.ask_position((v["x"], v["z"]), v["point"], 2.0)
            self.assertAlmostEqual(math.dist(a, (v["x"], v["z"])), 2.0, places=9)
            (x0, z0), (x1, z1) = sim.road.pos(j), sim.road.pos(v["next"])
            road_dir = (x1 - x0, z1 - z0)
            across = (v["x"] - a[0], v["z"] - a[1])
            self.assertAlmostEqual(road_dir[0] * across[0] + road_dir[1] * across[1], 0.0, places=6, msg=f"{j}>{cmd}")        # the view line is perpendicular to the road


class InTheRuns(unittest.TestCase):
    def test_the_robot_asks_from_2_m_across_and_the_worker_is_seen_at_90_degrees(self):
        found = 0
        for name, seeds in (("A3", (1, 2, 3, 4)), ("A4", (1, 2))):
            for seed in seeds:
                sc = sv.scenario_ab(name, seed, T4U, checkpoints=CPU, sim_cfg=hs.SimConfig(timeout_s=900.0))
                r = sc["sim"].run(sc["goal"])
                self.assertEqual(r["outcome"], "SUCCESS", (name, seed))
                road = sc["road"]
                for rec in r["junctions"]:
                    if not rec.get("checkpoint"):
                        continue
                    j, cmd = rec["checkpoint"].split(">")
                    pos = CPU["positions"][rec["checkpoint"]]
                    robot = rec["asks_log"][0]["robot"]
                    d = math.dist((robot["x"], robot["z"]), (pos["x"], pos["z"]))
                    self.assertAlmostEqual(d, 2.0, delta=0.35, msg=(name, seed, rec["checkpoint"]))                         # 2.0 m from the worker (the approach tolerance)
                    (x0, z0), (x1, z1) = road.pos(j), road.pos(road.next(j, cmd))
                    ang = abs(hc.wrap(hc.yaw_to(robot["x"], robot["z"], pos["x"], pos["z"]) - hc.yaw_to(x0, z0, x1, z1)))
                    self.assertAlmostEqual(ang, 90.0, delta=12.0, msg=(name, seed, rec["checkpoint"]))                      # the line of sight is perpendicular to the road
                    self.assertGreaterEqual(rec["person_360"], 100)                                                         # the checkpoint worker
                    found += 1
        self.assertGreaterEqual(found, 8)


if __name__ == "__main__":
    unittest.main()
