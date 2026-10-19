"""hri_eval_dev on small synthetic Unity/bridge files (no Unity, no models)."""

import csv
import json
import tempfile
import unittest
from pathlib import Path

import hri_eval_dev as ev
import hri_perception as hpm

EV = hpm.load_config()["evaluation"]


def write_csv(p: Path, rows: list[dict]):
    with p.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)


class EvalTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.d = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def session(self, mode="development", seed=1):
        s = self.d / "session"
        s.mkdir()
        (s / "session.json").write_text(json.dumps({"mode": mode, "seed": seed}))
        (s / "hri_config.json").write_text(json.dumps({"trials": {"mode": mode, "dev_seed": 1, "final_seed": 2}}))
        return s

    def test_hold_acceptance(self):
        win = [{"t_sim_f": 0.1 * i, "gesture_read": g} for i, g in enumerate(["NONE"] + ["LEFT"] * 11)]
        self.assertEqual(ev.hold_accept(win, 1.0), "LEFT")
        flicker = [{"t_sim_f": 0.1 * i, "gesture_read": "LEFT" if i % 3 else "NONE"} for i in range(30)]
        self.assertIsNone(ev.hold_accept(flicker, 1.0))

    def test_gesture_confusion_coverage_and_accuracy(self):
        s = self.session()
        write_csv(s / "truth_sweep.csv", [
            {"sample": 1, "gesture_shown": "LEFT", "t_start": 0.0, "t_end": 2.0, "distance_m": 2.0},
            {"sample": 2, "gesture_shown": "FORWARD_LEFT", "t_start": 3.0, "t_end": 5.0, "distance_m": 2.3}])
        conn = self.d / "conn"
        conn.mkdir()
        rows = []
        for i in range(21):   # LEFT: 15 correct, 5 NONE, 1 RIGHT
            rows.append({"type": "observation", "t_sim": f"{0.1 * i:.2f}", "gesture_read": "LEFT" if i < 15 else "NONE" if i < 20 else "RIGHT"})
        for i in range(21):   # FORWARD_LEFT: 10 FORWARD, 11 NONE
            rows.append({"type": "observation", "t_sim": f"{3 + 0.1 * i:.2f}", "gesture_read": "FORWARD" if i < 10 else "NONE"})
        write_csv(conn / "frames.csv", rows)
        g = ev.eval_gestures(s, conn, EV)
        left = g["per_command"]["LEFT"]
        self.assertEqual(left["frames"], 21)
        self.assertAlmostEqual(left["coverage"], 16 / 21, places=3)
        self.assertAlmostEqual(left["accuracy"], 15 / 16, places=3)
        self.assertEqual(left["samples_accepted_correct"], 1)
        fl = g["per_command"]["FORWARD_LEFT"]
        self.assertEqual((fl["accuracy"], fl["samples_accepted_wrong"]), (0.0, 0))  # 10 frames = 0.9 s < 1.0 s hold
        self.assertEqual(g["confusion"]["FORWARD_LEFT"]["FORWARD"], 10)
        self.assertFalse(g["diagonals_reliable"])

    def test_refuses_final_or_wrong_seed(self):
        with self.assertRaises(SystemExit):
            ev.guard_development(self.session(mode="final", seed=2))

    def test_refuses_final_seed_in_development(self):
        with self.assertRaises(SystemExit):
            ev.guard_development(self.session(seed=2))

    def test_accepts_dev_session(self):
        self.assertEqual(ev.guard_development(self.session())["seed"], 1)


if __name__ == "__main__":
    unittest.main()
