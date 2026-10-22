"""Task 2 with one standing worker per junction (declared design change 2026-10-22, AUDIT.md section 12): copies of the
one worker at J1's and J2's stands (roadmap rule) for the whole trial, as the Unity trial runner places them
(Task2Workers.cs). Simulator with the frozen controller; pure Python, no Unity."""

import math
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import hri_control as hc  # noqa: E402
import hri_sim as hs  # noqa: E402

ROAD = hc.load_json("configs/roadmap.json")
# The stands Unity's trial runner uses (RoadNode.workerStand, built from the same rule): 2.5 m ahead and 2.5 m right.
EXPECTED_STANDS = {"J1": (8.75, 2.5), "J2": (-8.75, 2.5)}
EXPECTED_READS = {"E1": [("J1", "FORWARD")], "E2": [("J1", "RIGHT")],
                  "E3": [("J1", "LEFT"), ("J2", "FORWARD")], "E4": [("J1", "LEFT"), ("J2", "RIGHT")]}


class Task2StandingWorkersTests(unittest.TestCase):
    def stands(self):
        road = hc.Roadmap(ROAD)
        return [(j, *road.stand(j)) for j in sorted(n for n, v in ROAD["nodes"].items() if v["kind"] == "junction")]

    def test_one_worker_per_junction_at_the_roadmap_stand(self):
        got = {j: (round(x, 3), round(z, 3)) for j, x, z, _ in self.stands()}
        self.assertEqual(got, EXPECTED_STANDS)

    def test_every_goal_read_at_its_junctions_from_that_junctions_worker(self):
        stands = self.stands()
        pos = {j: (x, z) for j, x, z, _ in stands}
        for seed, kw in ((1, {}), (2, {"p_detect": 0.84, "distance_sigma_m": 0.2, "bearing_sigma_deg": 2.0})):
            for goal, reads in EXPECTED_READS.items():
                c = hc.Controller(hc.load_json("configs/hri_control.json"), hc.Roadmap(ROAD))
                out = hs.Simulator(c, hs.SimConfig(**kw), seed=seed).run(goal, workers=stands)
                self.assertEqual(out["outcome"], "SUCCESS", (seed, goal, out))
                self.assertEqual([(j["junction"], j["shown"], j["read"], j["asks"]) for j in out["junctions"]],
                                 [(j, cmd, cmd, 1) for j, cmd in reads], (seed, goal))
                for j in out["junctions"]:   # approached that junction's own worker, not the other one
                    wx, wz = pos[j["junction"]]
                    self.assertLess(math.hypot(j["person_x"] - wx, j["person_z"] - wz), 0.5, (seed, goal, j["junction"]))
                self.assertGreater(out["closest_person_m"], 1.0, (seed, goal))


if __name__ == "__main__":
    unittest.main()
