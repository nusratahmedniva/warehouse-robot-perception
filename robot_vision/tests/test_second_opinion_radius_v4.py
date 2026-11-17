"""Second opinions only from people of the junction (AUDIT.md 16.19 item 2): a person is asked for a second opinion only if they are within
lie_detection.second_opinion_radius_m of the node AND the node is their nearest node of the roadmap, so the robot never drives toward another junction
to ask (step 5, A3: a second opinion asked 3.7 m away at J2). A radius that is absent or null is the earlier behaviour. The first person of a visit and the
tie rule's re-ask of the first person are unchanged."""

import json
import math
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))

import hri_control_v4 as hv  # noqa: E402
import hri_sim_v4 as sv  # noqa: E402

SECOND = {"second_opinion": True, "reject_impossible": False, "backtrack": False}
# J1 has the worker the robot is sent to (north of the node) and a person who stands 6.0 m before J2: 6.5 m from J1, 6.0 m from J2, i.e. a worker of J2
NEXT_JUNCTION = {"kind": "fixed", "points": {"A": [[6.25, -17.5]], "J1": [[6.25, 2.5], [-0.25, 0.0]], "J2": [[-6.25, 2.5]], "J3": [[20.55, 1.8]], "J4": [[-18.75, 2.5]]}}


def controller(radius="default", node="J1"):
    c = hv.make_controller_v4()
    if radius != "default":
        c.ld["second_opinion_radius_m"] = radius
    c.node = node
    return c


def person(x, z, tid=1):
    return {"x": x, "z": z, "track_id": tid, "distance_m": 3.0}


class BelongsHere(unittest.TestCase):
    def test_the_nearest_node_and_the_radius_decide(self):
        c = controller()
        self.assertEqual(c.ld["second_opinion_radius_m"], 6.5)
        for pt, want, nearest in (((6.25, 2.5), True, "J1"),                 # a worker of J1, north of it
                                  ((6.25, -6.0 - 0.0), True, "J1"),            # 6.0 m before J1 on the arrival road
                                  ((8.25, -6.0), True, "J1"),                  # the farthest slot: 6.0 m before and 2.0 m aside (6.3 m)
                                  ((-0.25, 0.0), False, "J2"),                 # 6.0 m before J2: 6.5 m from J1 but J2 is nearer: a worker of J2
                                  ((6.25, 7.0), False, "J1"),                  # nearest node is J1 but 7.0 m away: beyond the radius
                                  ((6.25, 19.0), False, "E1"),                 # beside an endpoint: nobody asks there
                                  ((20.0, 0.0), False, "J3")):
            ok, d, near = c._belongs_here(person(*pt))
            self.assertEqual((ok, near), (want, nearest), pt)
        ok, d, _ = c._belongs_here(person(6.25, 6.5))                          # exactly on the radius, J1 the nearest node: kept
        self.assertTrue(ok)
        self.assertAlmostEqual(d, 6.5)

    def test_null_or_absent_is_everybody_as_before(self):
        for radius in (None,):
            c = controller(radius)
            self.assertTrue(c._belongs_here(person(-0.25, 0.0))[0])
            self.assertTrue(c._belongs_here(person(6.25, 19.0))[0])
        c = controller()
        del c.ld["second_opinion_radius_m"]                                    # a controller built without the key
        self.assertTrue(c._belongs_here(person(-0.25, 0.0))[0])
        self.assertIsNone(hv.LIE_DEFAULTS["second_opinion_radius_m"])

    def test_the_start_node_asks_like_a_junction(self):
        c = controller(node="A")
        self.assertTrue(c._belongs_here(person(8.25, -17.0))[0])               # a start slot (3.0 m before, 2.0 aside)
        self.assertFalse(c._belongs_here(person(6.25, -8.0))[0])               # 12 m on the way to J1: J1's side


class EveryPlacedWorkerBelongsToItsNode(unittest.TestCase):
    def test_the_radius_never_excludes_a_worker_of_the_scenarios(self):
        """Every worker of every scenario, seed and asking node (beside and random layouts, the 20 simulator seeds) belongs to the node they stand at."""
        checked = 0
        for name in ("A1", "A2", "A3", "A4"):
            for seed in range(1, 21):
                sc = sv.scenario_ab(name, seed)
                c = sc["sim"].c
                for node, v in sc["road"].nodes.items():
                    if v["kind"] not in ("start", "junction"):
                        continue
                    c.node = node
                    for p in sc["sim"]._scene_at(node).people:
                        ok, d, near = c._belongs_here({"x": p.x, "z": p.z})
                        self.assertTrue(ok, (name, seed, node, round(d, 2), near))
                        checked += 1
        self.assertGreater(checked, 500)

    def test_the_declared_distances_behind_6_5_m(self):
        sc = sv.load_scenarios()["scenarios"]
        far = max(math.hypot(s["before_m"], s["right_m"]) for s in sc["3"]["layout"]["junction_slots"] + sc["3"]["layout"]["start_slots"])
        self.assertLess(far, 6.5)                                              # AUDIT.md 16.19: 6.3 m for the beside slots (start slots 6.3 m too)
        self.assertLess(math.hypot(sc["4"]["layout"]["half_size_m"], sc["4"]["layout"]["half_size_m"]), 6.5)
        road = json.loads((ROOT / "configs/v4/roadmap.json").read_text())["nodes"]
        asking = [(v["x"], v["z"]) for v in road.values() if v["kind"] in ("junction", "start")]
        self.assertEqual(min(math.dist(a, b) for a in asking for b in asking if a != b), 12.5)


class InTheSimulator(unittest.TestCase):
    def run_j1(self, detection):
        sc = sv.scenario_ab("A3", 1, detection)
        sc["spec"].layout = NEXT_JUNCTION
        return sc["sim"].run("E2")

    def test_a_person_of_the_next_junction_is_skipped_logged_once_and_not_asked(self):
        r = self.run_j1(SECOND)
        dec = r["v4"]["decisions"]
        skipped = [d for d in dec if d["event"] == "second_opinion_skipped" and d["node"] == "J1"]
        self.assertEqual(len(skipped), 1)                                      # logged once per person and visit, not on every tick
        self.assertEqual((skipped[0]["nearest_node"], skipped[0]["radius_m"]), ("J2", 6.5))
        self.assertGreater(skipped[0]["distance_to_node_m"], 6.4)
        self.assertEqual([d for d in dec if d["event"] == "ask_next" and d["node"] == "J1"], [])     # nobody else at J1 to ask: no walk toward J2
        go = [d for d in dec if d["event"] == "go" and d["node"] == "J1"][0]
        self.assertIn(go["reason"], ("one person only", "one usable answer, nobody else to ask"))
        self.assertEqual(r["outcome"], "SUCCESS")

    def test_without_the_radius_the_robot_asks_the_person_of_the_next_junction(self):
        r = self.run_j1({**SECOND, "second_opinion_radius_m": None})        # the earlier behaviour, the fault of step 5
        asked = [d for d in r["v4"]["decisions"] if d["event"] == "ask_next" and d["node"] == "J1"]
        self.assertTrue(asked)
        self.assertEqual([d for d in r["v4"]["decisions"] if d["event"] == "second_opinion_skipped"], [])

    def test_a_worker_of_the_junction_is_still_asked(self):
        sc = sv.scenario_ab("A3", 1, SECOND)
        r = sc["sim"].run("E2")
        self.assertTrue([d for d in r["v4"]["decisions"] if d["event"] == "ask_next" and d["node"] == "J1"])     # the 3 workers of J1: a second and a third opinion
        self.assertEqual([d for d in r["v4"]["decisions"] if d["event"] == "second_opinion_skipped"], [])


class ConfigFiles(unittest.TestCase):
    def test_every_control_file_carries_the_declared_radius_with_its_reason(self):
        files = [ROOT / "configs/v4/control.json", ROOT / "configs/v4/control_zoom_on.json", ROOT / "configs/v4/control_zoom_off.json"] + \
                sorted((ROOT / "configs/v4/experiments").glob("control_lie_*.json"))
        self.assertEqual(len(files), 11)
        for f in files:
            ld = json.loads(f.read_text(encoding="utf-8"))["lie_detection"]
            self.assertEqual(ld["second_opinion_radius_m"], 6.5, f.name)
            self.assertIn("DECIDED 2026-11-17", ld["why"]["second_opinion_radius_m"])


if __name__ == "__main__":
    unittest.main()
