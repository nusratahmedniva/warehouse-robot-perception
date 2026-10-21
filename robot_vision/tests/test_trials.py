"""Step 5 live guide controller and Step 7 trial log, analysis and dev evaluation, on synthetic files (no Unity)."""

import csv
import json
import re
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import hri_analysis as ha  # noqa: E402
import hri_control as hc  # noqa: E402
import hri_eval_dev as he  # noqa: E402
import hri_trials as ht  # noqa: E402
from bridge import protocol as P  # noqa: E402
from bridge.guide import GuideController  # noqa: E402

BUILDER = ROOT.parent / "unity" / "Robotics-Warehouse" / "WarehouseProjectURP" / "Assets" / "WarehouseRobot" / "HRI" / "Editor" / "HriScenarioBuilder.cs"
ROAD = hc.load_json("configs/roadmap.json")


class RoadmapConsistencyTests(unittest.TestCase):
    def test_unity_builder_uses_the_same_roadmap(self):
        src = BUILDER.read_text(encoding="utf-8")
        consts = {m[0]: (float(m[1]), float(m[2])) for m in
                  re.findall(r"k_(\w+) = new Vector2\(([-\d.]+)f, ([-\d.]+)f\)", src)}
        nodes = ROAD["nodes"]
        self.assertEqual(set(consts), set(nodes))
        for k, (x, z) in consts.items():
            self.assertEqual((x, z), (nodes[k]["x"], nodes[k]["z"]), k)
        links = {m[0].upper(): [n.strip().upper() for n in m[2].split(",")] for m in
                 re.findall(r"Link\((\w+), (\w+), ([\w, ]+)\);", src)}
        for j, br in ROAD["branches"].items():
            self.assertEqual(sorted(links[j]), sorted(br.values()), j)
        self.assertIn(f"WorkerCornerOffset = {ROAD['worker_stand']['corner_offset_m']}f", src)


class GoalOrderTests(unittest.TestCase):
    def test_pinned_like_unity(self):
        self.assertEqual(ht.goal_order(1, ["E1", "E2", "E3", "E4"], 10), ["E4", "E2", "E1", "E4", "E2", "E1", "E3", "E4", "E1", "E4"])
        g = ht.GoalSequence(2)
        self.assertEqual([g.next_goal_index(4) for _ in range(10)], [0, 1, 3, 1, 0, 2, 3, 0, 3, 0])


def telemetry(seq, trial=-1, running=False, x=6.25, z=-10.0, yaw=0.0):
    h = {"type": "telemetry", "seq": seq, "time_s": 0.05 * seq, "pose": {"x": x, "z": z, "yaw_deg": yaw}, "v": 0.0,
         "omega": 0.0, "nav_has_target": False, "nav_target_x": 0.0, "nav_target_z": 0.0, "nav_status": "none",
         "nav_corners": [], "rtt_ms": 0.7, "watchdog_count": 0, "collision_count": 0,
         "trial_index": trial, "trial_running": running, "version": P.PROTOCOL_VERSION, "attachments": []}
    return P.Message(h, {})


class FakeWorker:
    label = "fake vision"

    def __init__(self, t):
        self.t = t

    def submit(self, msg):
        pass

    def snapshot(self):
        return {"people": [], "people_pose": {"x": 6.25, "z": -10.0, "yaw_deg": 0.0}, "people_time_s": self.t(),
                "gesture": "NONE", "gesture_time_s": None}


class GuideTests(unittest.TestCase):
    def test_idle_then_trial_then_logs(self):
        with tempfile.TemporaryDirectory() as d:
            now = {"t": 0.0}
            g = GuideController(hc.make_controller(), FakeWorker(lambda: now["t"]), Path(d), log_every=1)
            r = g.on_message(telemetry(1))
            self.assertEqual((r["v"], r["state"], r["has_target"]), (0.0, "idle", False))
            now["t"] = 0.1
            r = g.on_message(telemetry(2, trial=1, running=True))
            self.assertEqual(r["state"], "navigate")
            self.assertTrue(r["has_target"])
            self.assertEqual((r["target_x"], r["target_z"]), (6.25, 0.0))     # J1, never goal B
            self.assertGreater(r["v"], 0.0)
            g.on_message(telemetry(3, trial=1, running=False))                 # trial cut short by Unity
            g.close()
            s = json.loads((Path(d) / "python_trial_001.json").read_text())
            self.assertEqual((s["trial"], s["state"]), (1, "navigate"))
            rows = list(csv.DictReader((Path(d) / "decisions.csv").open()))
            self.assertEqual([x["state"] for x in rows], ["idle", "navigate", "idle"])

    def test_every_reply_carries_route_and_perception_ready(self):
        import task_route as tr
        now = {"t": 0.0}
        worker = FakeWorker(lambda: now["t"])
        g = GuideController(hc.make_controller(), worker, None, route="Task2")
        r = g.on_message(telemetry(1))
        self.assertEqual((r["route"], r["perception_ready"]), ("Task2", False))   # no ready attribute: not ready
        worker.ready = True
        self.assertTrue(g.on_message(telemetry(2))["perception_ready"])
        P.validate(P.Message({**r, "type": "command", "seq": 0, "reply_to": 1, "version": P.PROTOCOL_VERSION,
                              "attachments": []}), P.TO_UNITY)   # extra fields are allowed: raises otherwise
        road, route, _ = tr.map_for_task("Task1", hc.load_json)
        g1 = GuideController(hc.Controller(hc.load_json("configs/hri_control.json"), hc.Roadmap(road)), worker, None, route=route)
        g1.on_message(telemetry(1))
        r = g1.on_message(telemetry(2, trial=1, running=True))
        self.assertEqual(r["route"], "Task1:C1,J1,C3")
        self.assertEqual((r["target_x"], r["target_z"]), (6.25, -5.0))    # the first checkpoint, C1


def write_csv(p, rows):
    with p.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)


def fake_session(base: Path, mode="development", seed=1):
    u, b = base / "trials_x", base / "bridge_x"
    (u / "config_used").mkdir(parents=True)
    (b / "config_used").mkdir(parents=True)
    (u / "config_used" / "trials.json").write_text(json.dumps({"mode": mode, "dev_seed": 1, "final_seed": 2}))
    (u / "session.json").write_text(json.dumps({"task": "Task2", "mode": mode, "seed": seed, "endpoints": ["E1", "E2", "E3", "E4"],
                                                "goal_order": ["E4", "E2"], "git_commit": "abc"}))
    for i, (goal, ok) in enumerate([("E4", True), ("E2", False)], 1):
        t = {"trial": i, "task": "Task2", "mode": mode, "seed": seed, "a_name": "A", "b_name": goal, "a_x": 6.25, "a_z": -10.0,
             "b_x": 1.0, "b_z": 2.0, "outcome": "SUCCESS" if ok else "FAILURE", "failure_reason": "none" if ok else "aborted",
             "detail": "x", "python_final_state": "done" if ok else "aborted", "final_x": 0, "final_z": 0,
             "final_distance_to_b_m": 0.05 if ok else 4.0, "straight_line_m": 20.0, "travelled_m": 30.0, "total_s": 60.0,
             "t_start": 10.0 * i, "t_end": 10.0 * i + 5, "avg_speed_mps": 0.5, "max_speed_mps": 0.8, "avg_turn_dps": 3.0,
             "max_turn_dps": 50.0, "collisions": 0, "human_collisions": 0, "collided_with": "", "closest_human_m": 1.2,
             "closest_human_note": "n", "shown": [{"junction": "J1", "shown": "LEFT", "t_placed": 10.0 * i}], "truth_file": "t"}
        (u / f"truth_run{i:03d}.json").write_text(json.dumps(t))
        (b / f"python_trial_{i:03d}.json").write_text(json.dumps({
            "trial": i, "state": t["python_final_state"], "perception": "vision", "abort_reason": "" if ok else "gesture unclear after 2 asks at J1",
            "step_s": {s: 1.0 for s in ht.STEPS}, "safety_stop_s": 0.5, "trace": ["0.00:navigate", "5.00:scan", "6.00:approach"],
            "junctions": [{"junction": "J1", "read": "LEFT" if ok else "NONE", "asks": 1 if ok else 2, "result": "accepted" if ok else "aborted"}]}))
    write_csv(b / "decisions.csv", [{"trial": "1", "time_s": "10.5", "rtt_ms": "0.8", "watchdog_count": "0"},
                                    {"trial": "2", "time_s": "20.5", "rtt_ms": "1.2", "watchdog_count": "1"}])
    write_csv(b / "perception.csv", [{"type": "frame_360", "time_s": "10.5", "decode_ms": "4", "model_ms": "yolo11s-pose/cam360:200",
                                      "total_ms": "210", "pose_x": "6.25", "pose_z": "-10", "yaw_deg": "0", "gesture_read": "",
                                      "people_json": json.dumps([{"bearing_deg": 0.0, "distance_m": 3.1, "distance_source": "ankles"}])}])
    write_csv(u / "truth_run001.csv", [{"time_s": "10.5", "worker_x": "6.25", "worker_z": "-7.0"}])
    return u, b


class MergeAnalysisEvalTests(unittest.TestCase):
    def test_merge_has_every_metric(self):
        with tempfile.TemporaryDirectory() as d:
            u, b = fake_session(Path(d))
            runs, meta = ht.merge(u, b)
            self.assertTrue(meta["check"]["goal_order_matches"])
            self.assertEqual([r["success_ratio"] for r in runs], [1.0, 0.5])
            r = runs[0]
            self.assertEqual(r["junctions"], [{"junction": "J1", "shown": "LEFT", "read": "LEFT", "asks": 1, "result": "accepted"}])
            self.assertEqual(r["inference_ms"]["yolo11s-pose/cam360"]["mean"], 200.0)
            self.assertEqual(r["round_trip_ms"]["mean"], 0.8)
            row = ht.csv_row(r)
            missing = [c for c in ht.COLUMNS if c not in row]
            self.assertEqual(missing, [])

    def test_analysis(self):
        with tempfile.TemporaryDirectory() as d:
            u, b = fake_session(Path(d))
            runs, _ = ht.merge(u, b)
            for r in runs:
                r["_folder"] = "x"
            a = ha.analyse(runs)
            self.assertEqual(a["success"]["k"], 1)
            lo, hi = a["success"]["wilson95"]
            self.assertTrue(0 < lo < 0.5 < hi < 1)
            self.assertEqual(a["junctions"]["shown_vs_read"]["LEFT"], {"LEFT": 1, "NONE": 1})
            self.assertIn("Success 1/2", ha.markdown(a))

    def test_time_excluding_stale_stops(self):
        rows = [{"trial": "1", "time_s": t, "safety": s} for t, s in
                [("10.0", ""), ("10.1", "perception stale"), ("10.2", "perception stale"), ("10.3", ""),
                 ("10.4", "person in path"), ("10.5", "perception stale")]]   # the last row has no next row: not counted
        self.assertAlmostEqual(ht.stale_stop_s(rows), 0.2)
        self.assertIsNone(ht.stale_stop_s([{"trial": "1", "time_s": "10.0"}]))   # older log without a safety column
        with tempfile.TemporaryDirectory() as d:
            u, b = fake_session(Path(d))
            write_csv(b / "decisions.csv", [dict(r, rtt_ms="0.8", watchdog_count="0") for r in rows])
            runs, _ = ht.merge(u, b)
            self.assertEqual((runs[0]["total_s"], runs[0]["stale_stop_s"], runs[0]["time_excl_stale_stops_s"]),
                             (60.0, 0.2, 59.8))
            self.assertEqual((runs[1]["stale_stop_s"], runs[1]["time_excl_stale_stops_s"]), (None, None))  # no rows, trial 2
            for r in runs:
                r["_folder"] = "x"
            a = ha.analyse(runs)
            self.assertEqual((a["time_excl_stale_stops_s"]["n"], a["time_excl_stale_stops_s"]["mean"]), (1, 59.8))
            self.assertEqual(a["total_s"]["n"], 2)
            self.assertIn("| time excl. stale stops | 1 | 59.8 |", ha.markdown(a))

    def test_in_motion_time(self):
        rows = [{"time_s": t, "v_mps": v} for t, v in
                [("10.0", "0.0"), ("10.1", "0.05"), ("10.2", "0.06"), ("10.3", "0.8"), ("10.4", "-0.2"), ("10.5", "0.0"),
                 ("10.6", "0.9")]]   # 0.05 is not above the threshold; the last row has no next row: not counted
        self.assertAlmostEqual(ht.in_motion_s(rows, 0.05), 0.3)
        self.assertIsNone(ht.in_motion_s([{"time_s": "10.0", "worker_x": "1"}], 0.05))   # older log without speed
        self.assertEqual(ht.load_metrics_config()["in_motion_speed_threshold_mps"], 0.05)
        with tempfile.TemporaryDirectory() as d:
            u, b = fake_session(Path(d))      # truth_run001.csv has no v_mps; trial 2 has no truth csv
            runs, _ = ht.merge(u, b)
            self.assertEqual([r["in_motion_s"] for r in runs], [None, None])
            write_csv(u / "truth_run001.csv", rows)
            runs, _ = ht.merge(u, b, {"in_motion_speed_threshold_mps": 0.05})
            self.assertEqual((runs[0]["in_motion_s"], runs[0]["in_motion_speed_threshold_mps"]), (0.3, 0.05))
            for r in runs:
                r["_folder"] = "x"
            a = ha.analyse(runs)
            self.assertIn("| in motion | 1 | 0.3 |", ha.markdown(a))
            self.assertIn("above 0.05 m/s", ha.markdown(a))

    def test_eval_people_and_guard(self):
        with tempfile.TemporaryDirectory() as d:
            u, b = fake_session(Path(d))
            p = he.eval_people(u, b, {"match_bearing_deg": 10, "truth_join_max_s": 0.06, "detection_range_m": 12,
                                      "distance_bins_m": [0, 3, 6, 9, 12]})
            self.assertEqual((p["frames_eligible"], p["frames_detected"]), (1, 1))
            self.assertAlmostEqual(p["distance_error"]["ankles"]["mean_signed_m"], 0.1)
        with tempfile.TemporaryDirectory() as d:
            u, _ = fake_session(Path(d), mode="final", seed=2)
            with self.assertRaises(SystemExit):
                he.guard_development(u)

    def test_hold_strict_versus_tolerant(self):
        frames = [{"t": 0.1 * i, "read": "NONE" if i == 5 else "FORWARD"} for i in range(15)]
        self.assertIsNone(he.hold_result(frames, 1.0, 0.0))          # the one missed frame breaks the strict hold
        self.assertEqual(he.hold_result(frames, 1.0, 0.3), "FORWARD")


if __name__ == "__main__":
    unittest.main()
