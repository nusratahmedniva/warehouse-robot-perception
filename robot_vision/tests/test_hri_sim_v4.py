"""v4 simulator groundwork (hri_sim_v4.py): commander and bystanders, synthetic POINT / WAIT / STOP with coverage,
accuracy and angle noise, truth rows for gesture_data.py. v3 simulation is untouched (covered by test_hri_control)."""

import ast
import statistics as st
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import gesture_data as gd  # noqa: E402
import hri_control as hc  # noqa: E402
import hri_sim_v4 as sv  # noqa: E402
from hri_sim import SimConfig  # noqa: E402


def episode(command="WAIT", t0=10.0, angle=None, **kw):
    kw = {"start_delay_s": 0.5, "gesturing_s": 0.5, "hold_s": 1.0, "returning_s": 0.5, "arm": "right", "clip": "clipA", **kw}
    if command == "POINT" and angle is None:
        angle = 40.0
    return sv.Episode(command, t0, world_angle_deg=angle if command == "POINT" else None, **kw)


def person(pid, x, z, role="bystander", ep=None, look="look_a"):
    return sv.Person(pid, x, z, look, role, ep)


def scene(command="WAIT", **kw):
    return sv.Scene([person(1, 0.0, 2.0, "commander", episode(command, **kw)), person(2, 1.5, 2.0, look="look_b")])


class EpisodeTests(unittest.TestCase):
    def test_phases_in_order(self):
        e = episode()
        got = [e.phase(t)[0] for t in (9.9, 10.0, 10.49, 10.5, 10.99, 11.0, 11.99, 12.0, 12.49, 12.5, 20.0)]
        self.assertEqual(got, ["idle", "start_delay", "start_delay", "gesturing", "gesturing", "holding", "holding",
                               "returning", "returning", "idle", "idle"])
        self.assertAlmostEqual(e.end(), 12.5)

    def test_validation(self):
        with self.assertRaises(ValueError):
            sv.Episode("WAVE", 0, 0, 1, 1, 1)
        with self.assertRaises(ValueError):
            sv.Episode("POINT", 0, 0, 1, 1, 1)                          # POINT needs an angle
        with self.assertRaises(ValueError):
            sv.Episode("WAIT", 0, 0, 1, 1, 1, world_angle_deg=10.0)     # only POINT has one

    def test_person_state(self):
        p = person(1, 0, 0, ep=episode("POINT", angle=60.0))
        self.assertEqual(p.state(10.2)["command"], "NONE")                # start delay: nothing shown yet
        g = p.state(10.75)                                               # halfway through gesturing
        self.assertEqual((g["phase"], g["command"], g["world_angle_deg"]), ("gesturing", "POINT", 30.0))
        h = p.state(11.5)
        self.assertEqual((h["phase"], h["world_angle_deg"], h["arm"], h["clip"]), ("holding", 60.0, "right", "clipA"))
        self.assertEqual(p.state(12.1)["command"], "NONE")                # returning
        self.assertEqual(person(2, 0, 0).state(11.0)["command"], "NONE")  # no episode


class SceneTests(unittest.TestCase):
    def test_needs_exactly_one_commander_and_unique_ids(self):
        with self.assertRaises(ValueError):
            sv.Scene([person(1, 0, 0), person(2, 1, 1)])
        with self.assertRaises(ValueError):
            sv.Scene([person(1, 0, 0, "commander"), person(2, 1, 1, "commander")])
        with self.assertRaises(ValueError):
            sv.Scene([person(1, 0, 0, "commander"), person(1, 1, 1)])
        with self.assertRaises(ValueError):
            sv.Scene([person(1, 0, 0, "commander"), person(2, 1, 1, "spectator")])
        self.assertEqual(scene().commander.id, 1)

    def test_truth_rows_follow_the_protocol(self):
        s = sv.Scene([person(1, 0.0, 2.0, "commander", episode("POINT", angle=120.0)), person(2, 1.5, 2.0, look="look_b")])
        rows = s.truth_rows(11.5, robot_yaw_deg=90.0)
        parsed = gd.parse_truth([__import__("json").dumps(r) for r in rows])          # passes the loader's checks
        c, b = parsed
        self.assertEqual((c.true_command, c.point_angle_deg, c.arm, c.phase, c.is_commander, c.clip),
                         ("POINT", 30.0, "right", "holding", True, "clipA"))          # 120 world, robot faces 90
        self.assertEqual((b.true_command, b.point_angle_deg, b.arm, b.is_commander, b.look),
                         ("NONE", -1, "none", False, "look_b"))
        self.assertNotIn("clip", rows[1])

    def test_junction_scene_uses_the_worker_stand(self):
        road = hc.Roadmap(hc.load_json("configs/roadmap.json"))
        sx, sz, _ = road.stand("J1")
        sc = sv.junction_scene(road, "J1", person(7, 0, 0, ep=episode()), [(1.0, 0.0), (-1.0, 1.0)], ["b1", "b2"])
        self.assertEqual((sc.commander.x, sc.commander.z, sc.commander.id), (sx, sz, 7))
        self.assertEqual([(p.id, p.role, round(p.x - sx, 3), round(p.z - sz, 3)) for p in sc.people[1:]],
                         [(8, "bystander", 1.0, 0.0), (9, "bystander", -1.0, 1.0)])
        with self.assertRaises(ValueError):
            sv.junction_scene(road, "J1", person(7, 0, 0), [(1.0, 0.0)], [])


def vision(sc=None, gcfg=None, cfg=None, seed=1):
    return sv.VisionSim(sc or scene(), cfg or SimConfig(), gcfg or sv.GestureSimConfig(), seed)


class DetectionTests(unittest.TestCase):
    def test_everybody_in_range_with_ids(self):
        d = vision().detect(0.0, 0.0, 0.0)
        self.assertEqual({q["id"] for q in d}, {1, 2})
        c = [q for q in d if q["id"] == 1][0]
        self.assertAlmostEqual(c["distance_m"], 2.0)
        self.assertAlmostEqual(c["bearing_deg"], 0.0)

    def test_range_and_detection_probability(self):
        self.assertEqual(vision(cfg=SimConfig(detection_range_m=1.0)).detect(0.0, 0.0, 0.0), [])
        self.assertEqual(vision(cfg=SimConfig(p_detect=0.0)).detect(0.0, 0.0, 0.0), [])
        v = vision(cfg=SimConfig(p_detect=0.5))
        n = sum(len(v.detect(0.0, 0.0, 0.0)) for _ in range(400))
        self.assertTrue(300 < n < 500, n)                                # 800 chances at 0.5


class ReadTests(unittest.TestCase):
    ROBOT = (0.0, 0.0, 0.0)          # at the origin facing +Z; the commander is straight ahead at 2 m

    def test_perfect_reading_of_each_command(self):
        for cmd in sv.COMMANDS:
            r = vision(scene(cmd)).read(11.5, *self.ROBOT, pan_deg=0.0)       # holding
            self.assertEqual((r["person_id"], r["command"]), (1, cmd))
            self.assertEqual(r["angle_deg"] is not None, cmd == "POINT")

    def test_point_angle_is_relative_to_the_robot(self):
        r = vision(scene("POINT", angle=40.0)).read(11.5, 0.0, 0.0, 10.0, pan_deg=0.0)   # robot yaw 10 -> 30 right
        self.assertAlmostEqual(r["angle_deg"], 30.0)
        alone = sv.Scene([person(1, 0.0, 2.0, "commander", episode("POINT", angle=-170.0))])
        self.assertAlmostEqual(vision(alone).read(11.5, 0.0, 0.0, 20.0, 0.0)["angle_deg"], 170.0)    # -190 wrapped

    def test_nothing_shown_reads_none_but_names_the_person_in_view(self):
        r = vision().read(9.0, *self.ROBOT, pan_deg=0.0)                  # before the episode
        self.assertEqual((r["person_id"], r["command"], r["angle_deg"]), (1, "NONE", None))

    def test_nobody_in_view_or_range(self):
        v = vision()
        self.assertEqual(v.read(11.5, 0.0, 0.0, 180.0, 0.0)["person_id"], -1)             # facing away
        self.assertEqual(vision(cfg=SimConfig(gesture_range_m=1.0)).read(11.5, *self.ROBOT, 0.0)["person_id"], -1)

    def test_pan_turns_the_camera_left_positive(self):
        sc = sv.Scene([person(1, 0.0, 2.0, "commander", episode("WAIT")), person(2, -2.0, 2.0, ep=episode("STOP"))])
        v = vision(sc)
        self.assertEqual(v.read(11.5, *self.ROBOT, pan_deg=0.0)["person_id"], 1)
        self.assertEqual(v.read(11.5, *self.ROBOT, pan_deg=45.0)["person_id"], 2)         # turned left: the one at x < 0

    def test_a_gesturing_bystander_nearer_the_axis_is_read_instead_of_the_commander(self):
        sc = sv.Scene([person(1, 1.5, 2.0, "commander", episode("WAIT")), person(2, 0.3, 2.0, ep=episode("STOP"))])
        r = vision(sc).read(11.5, *self.ROBOT, pan_deg=0.0)
        self.assertEqual((r["person_id"], r["command"]), (2, "STOP"))

    def test_coverage(self):
        g = sv.GestureSimConfig(coverage={"WAIT": 0.0})
        self.assertTrue(all(vision(gcfg=g).read(11.5, *self.ROBOT, 0.0)["command"] == "NONE" for _ in range(20)))
        g = sv.GestureSimConfig(coverage={"WAIT": 0.5})
        v = vision(gcfg=g)
        n = sum(v.read(11.5, *self.ROBOT, 0.0)["command"] != "NONE" for _ in range(400))
        self.assertTrue(140 < n < 260, n)
        g = sv.GestureSimConfig(coverage={"STOP": 0.0})                    # per command: WAIT unaffected
        self.assertEqual(vision(scene("WAIT"), g).read(11.5, *self.ROBOT, 0.0)["command"], "WAIT")

    def test_accuracy_uses_the_confusion_table(self):
        g = sv.GestureSimConfig(accuracy={"WAIT": 0.0, "STOP": 0.0, "POINT": 0.0})
        for cmd, wrong in (("WAIT", "STOP"), ("STOP", "WAIT"), ("POINT", "WAIT")):
            r = vision(scene(cmd), g).read(11.5, *self.ROBOT, 0.0)
            self.assertEqual(r["command"], wrong, cmd)
            self.assertIsNone(r["angle_deg"])
        g = sv.GestureSimConfig(accuracy={"WAIT": 0.0}, confusion={**sv.DEFAULT_CONFUSION, "WAIT": ["POINT"]})
        r = vision(scene("WAIT"), g).read(11.5, *self.ROBOT, 0.0)
        self.assertEqual(r["command"], "POINT")
        self.assertTrue(-180 <= r["angle_deg"] < 180)                      # a made-up angle: there was no true one
        g = sv.GestureSimConfig(accuracy={"WAIT": 0.7})
        v = vision(gcfg=g)
        ok = sum(v.read(11.5, *self.ROBOT, 0.0)["command"] == "WAIT" for _ in range(500))
        self.assertTrue(310 < ok < 390, ok)

    def test_point_angle_noise(self):
        v = vision(scene("POINT", angle=40.0), sv.GestureSimConfig(point_angle_sigma_deg=5.0))
        a = [v.read(11.5, *self.ROBOT, 0.0)["angle_deg"] for _ in range(600)]
        self.assertAlmostEqual(st.fmean(a), 40.0, delta=1.0)
        self.assertAlmostEqual(st.pstdev(a), 5.0, delta=0.8)
        exact = vision(scene("POINT", angle=40.0)).read(11.5, *self.ROBOT, 0.0)["angle_deg"]
        self.assertEqual(exact, 40.0)                                      # default: no noise

    def test_defaults_are_neutral(self):
        g = sv.GestureSimConfig()
        self.assertEqual((g.coverage, g.accuracy, g.point_angle_sigma_deg), ({}, {}, 0.0))

    def test_same_seed_same_readings(self):
        g = sv.GestureSimConfig(coverage={"POINT": 0.6}, accuracy={"POINT": 0.6}, point_angle_sigma_deg=7.0)
        def run(seed):
            v = vision(scene("POINT"), g, seed=seed)
            return [v.read(11.5, *self.ROBOT, 0.0) for _ in range(30)]
        self.assertEqual(run(3), run(3))
        self.assertNotEqual(run(3), run(4))

    def test_bad_confusion_table_rejected(self):
        for bad in ({"WAIT": ["WAIT"]}, {"WAIT": []}, {"WAIT": ["WAVE"]}):
            with self.assertRaises(ValueError):
                vision(gcfg=sv.GestureSimConfig(confusion={**sv.DEFAULT_CONFUSION, **bad}))


class SimulateAskTests(unittest.TestCase):
    def run_ask(self, sc, gcfg=None, **kw):
        return sv.simulate_ask(sc, SimConfig(), gcfg or sv.GestureSimConfig(), (0.0, 0.0), 0.0, t0=9.0, duration_s=5.0,
                               truth_dt_s=0.02, **kw)

    def test_streams_and_counts(self):
        out = self.run_ask(scene("POINT"))
        self.assertEqual((len(out["frames"]), len(out["readings"]), len(out["detections"])), (50, 50, 25))
        self.assertEqual(len(out["truth_rows"]), 250 * 2)                    # 250 steps x 2 people
        self.assertAlmostEqual(out["pan_deg"], 0.0)
        self.assertAlmostEqual(out["frames"][1]["time_s"], 9.1)
        self.assertAlmostEqual(out["readings"][0]["available_s"] - out["readings"][0]["time_s"], SimConfig().gesture_latency_s)

    def test_pan_points_at_the_commander(self):
        sc = sv.Scene([person(1, 2.0, 2.0, "commander", episode("WAIT"))])
        out = sv.simulate_ask(sc, SimConfig(), sv.GestureSimConfig(), (0.0, 0.0), 0.0, 9.0, 1.0, 0.1)
        self.assertAlmostEqual(out["pan_deg"], -45.0)                         # commander 45 deg to the right
        self.assertEqual({r["person_id"] for r in out["readings"]}, {1})

    def test_perfect_perception_matches_the_joined_truth(self):
        out = self.run_ask(scene("POINT"))
        rows = gd.parse_truth([__import__("json").dumps(r) for r in out["truth_rows"]])
        j = gd.join(out["frames"], rows)
        self.assertEqual(j.unlabelled_frames, [])
        for lab in j.labels:
            if lab["worker_id"] != 1:
                continue
            reading = out["readings"][lab["frame_index"]]
            self.assertEqual(reading["command"], lab["row"].true_command, lab["frame_index"])
            if reading["command"] == "POINT":
                self.assertAlmostEqual(reading["angle_deg"], lab["row"].point_angle_deg, delta=3.0)   # frame vs nearest row
        clips = gd.attach_frames(gd.build_clips(rows), j)
        self.assertEqual([(c.worker_id, c.command, c.look) for c in clips], [(1, "POINT", "look_a")])
        self.assertEqual(clips[0].phases, ["gesturing", "holding"])
        self.assertEqual(clips[0].distance_m, 2.0)

    def test_lossy_perception_is_measurable_against_truth(self):
        out = self.run_ask(scene("STOP"), sv.GestureSimConfig(coverage={"STOP": 0.5}, accuracy={"STOP": 0.8}), seed=5)
        rows = gd.parse_truth([__import__("json").dumps(r) for r in out["truth_rows"]])
        j = gd.join(out["frames"], rows)
        shown = [lab for lab in j.labels if lab["worker_id"] == 1 and lab["row"].true_command == "STOP"]
        read = [out["readings"][lab["frame_index"]]["command"] for lab in shown]
        self.assertTrue(len(shown) >= 10)
        covered = [r for r in read if r != "NONE"]
        self.assertTrue(0 < len(covered) < len(read))                       # coverage < 1 is visible
        self.assertTrue(set(covered) <= {"STOP", "WAIT"})                   # STOP is only confused with WAIT


class IsolationTests(unittest.TestCase):
    def test_v3_code_does_not_import_the_v4_simulator(self):
        for p in ROOT.rglob("*.py"):
            rel = p.relative_to(ROOT)
            if ".venv" in rel.parts or rel.parts[0] == "tests" or rel.name == "hri_sim_v4.py":
                continue
            tree = ast.parse(p.read_text(encoding="utf-8"))
            mods = {a.name for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names}
            mods |= {n.module for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) and n.module}
            self.assertNotIn("hri_sim_v4", mods, str(rel))

    def test_simulator_does_not_read_truth_or_controller_state(self):
        src = (ROOT / "hri_sim_v4.py").read_text(encoding="utf-8")
        for word in ("gt_path", "data_splits"):
            self.assertNotIn(word, src)


if __name__ == "__main__":
    unittest.main()
