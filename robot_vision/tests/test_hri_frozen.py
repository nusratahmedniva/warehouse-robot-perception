"""The configuration of the final guided-robot trials is frozen: hashes and fixed trial settings must not change.

The shared hashes (perception, gesture, state machine, roadmap, bridge, Unity configs) are those of the Task 2
final; every task runs with them. Route and trial settings are checked per task.
"""

import hashlib
import json
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
CONFIGS = REPO / "robot_vision" / "configs"
FROZEN = json.loads((CONFIGS / "hri_frozen.json").read_text(encoding="utf-8"))

# configs/hri_frozen.json -> sha256 at the Task 2 final commit ce37a56 (frozen in 1a574cb).
TASK2_FINAL_SHA256 = {
    "robot_vision/configs/hri_control.json": "79662c4b603cf4b966f7cdb76c21672cc6e20fceb026a1053e061c0f84f93b72",
    "robot_vision/configs/hri_perception.json": "cdfd268b8baa53e79c6e10a416bf5cc79a4f4ca2cc2a87e567b0d9eec0e9a6f8",
    "robot_vision/configs/gesture_hri.json": "c32182cc997c07a359c1f00de30bfb14abc85b29c3703c5b9885f07998d5a26c",
    "robot_vision/configs/roadmap.json": "d7ee36b5de9b815d9a2d936831ad38c67f979d34c98401714a745fb54a16a421",
    "robot_vision/configs/bridge.json": "df792cc96e11179086aa8274ccc58a3566c8d5be52badddce28cf7bf8cec1e8a",
    "unity/Robotics-Warehouse/WarehouseProjectURP/Assets/WarehouseRobot/Robot/Config/robot_unity.json": "c7d59e8dfdcd24413e25af09d5419afeaa87d4f4b7ab7ae28f714528d731cbb5",
    "unity/Robotics-Warehouse/WarehouseProjectURP/Assets/WarehouseRobot/Bridge/Config/bridge_unity.json": "db856234c9893836316b51a96aab2b12cc0091f286c339c140c42b89943d24b5",
}


def file_sha256(rel: str) -> str:
    # Hashes were taken with LF endings; a Windows checkout (core.autocrlf) has CRLF, same content.
    return hashlib.sha256((REPO / rel).read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def read_json(name: str) -> dict:
    return json.loads((CONFIGS / name).read_text(encoding="utf-8"))


class FrozenConfigTests(unittest.TestCase):
    def test_shared_hashes_are_the_task2_final(self):
        self.assertEqual(FROZEN["sha256"], TASK2_FINAL_SHA256)

    def test_hashes_unchanged(self):
        for rel, digest in {**FROZEN["sha256"], **FROZEN["sha256_added_2026_10_21"]}.items():
            self.assertEqual(file_sha256(rel), digest, f"{rel} changed after freezing (disclose and re-freeze)")

    def test_robot_and_metrics_configs_in_frozen_set(self):
        for rel in ("robot_vision/configs/robot.json", "robot_vision/configs/hri_trials_metrics.json"):
            self.assertIn(rel, FROZEN["sha256_added_2026_10_21"])
        self.assertEqual(read_json("hri_trials_metrics.json")["in_motion_speed_threshold_mps"], 0.05)

    def test_flags_set(self):
        for name in ("hri_control.json", "hri_perception.json"):
            self.assertTrue(read_json(name)["frozen"], name)

    def test_pose_weights_hash_matches_perception_config(self):
        w = FROZEN["pose_weights"]
        perception = read_json("hri_perception.json")["pose_model"]
        self.assertEqual(w["sha256"], perception["sha256"])
        self.assertEqual(Path(w["path"]), Path("robot_vision") / perception["weights"])

    def test_local_pose_weights_match(self):
        w = FROZEN["pose_weights"]
        p = REPO / w["path"]
        if not p.exists():
            self.skipTest(f"{w['path']} not present (weights are git-ignored)")
        self.assertEqual(hashlib.sha256(p.read_bytes()).hexdigest(), w["sha256"])

    def test_trial_settings_fixed_for_configured_task(self):
        trials = read_json("trials.json")
        self.assertIn(trials["task"], FROZEN["tasks"])
        for k, v in FROZEN["tasks"][trials["task"]]["trials_fixed"].items():
            self.assertEqual(trials[k], v, k)

    def test_each_task_names_itself(self):
        for task, spec in FROZEN["tasks"].items():
            self.assertEqual(spec["trials_fixed"]["task"], task)

    def test_task1_uses_the_task2_trial_settings(self):
        t1 = dict(FROZEN["tasks"]["Task1"]["trials_fixed"], task=None)
        t2 = dict(FROZEN["tasks"]["Task2"]["trials_fixed"], task=None)
        self.assertEqual(t1, t2)

    def test_task2_settings_are_those_of_its_final(self):
        # configs/hri_frozen.json -> trials_fixed at ce37a56.
        self.assertEqual(FROZEN["tasks"]["Task2"]["trials_fixed"],
                         {"task": "Task2", "dev_seed": 1, "final_seed": 2, "trial_count": 10, "timeout_s": 240,
                          "stuck_s": 10, "stuck_min_progress_m": 0.25, "success_radius_m": 0.3})

    def test_task1_route_config_frozen_per_task(self):
        rc = FROZEN["tasks"]["Task1"]["route_config"]
        self.assertEqual(file_sha256(rc["path"]), rc["sha256"], f"{rc['path']} changed (disclose and re-record)")
        self.assertNotIn(rc["path"], FROZEN["sha256"])                       # per task, not a shared setting
        self.assertNotIn("route_config", FROZEN["tasks"]["Task2"])           # Task 2 does not read it

    def test_task1_recorded_stops_are_those_of_the_config(self):
        import sys
        sys.path.insert(0, str(REPO / "robot_vision"))
        import hri_control as hc
        import task_route as tr
        route = FROZEN["tasks"]["Task1"]["route"]
        cfg = read_json("task1_route.json")
        self.assertEqual(route["checkpoints"], cfg["checkpoints"])
        road, map_id, _ = tr.map_for_task("Task1", hc.load_json)
        self.assertEqual(route["stops"], road["task1_stops"])
        self.assertEqual(route["map"], map_id)
        self.assertEqual(route["goal"], tr.straight_line(read_json("roadmap.json"))[-1])
        self.assertEqual([tuple(w) for w in route["workers"]],
                         tr.task1_worker_stands(read_json("roadmap.json"), cfg))   # one standing worker per stop

    def test_routes_match_roadmap(self):
        roadmap = read_json("roadmap.json")
        endpoints = {n for n, v in roadmap["nodes"].items() if v["kind"] == "endpoint"}
        for task, spec in FROZEN["tasks"].items():
            self.assertEqual(spec["route"]["start"], roadmap["start"], task)
        self.assertEqual(FROZEN["tasks"]["Task1"]["route"]["goal"], roadmap["task1_goal"])
        self.assertIn(roadmap["task1_goal"], endpoints)
        self.assertEqual(FROZEN["tasks"]["Task2"]["route"]["goal"], "seeded")


if __name__ == "__main__":
    unittest.main()
