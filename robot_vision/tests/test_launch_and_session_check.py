"""Trial launchers (run_trials.ps1 / run_trials.sh) and the Task 1 session check helpers (2026-10-21). No Unity."""

import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import hri_session_check as sc  # noqa: E402


class LauncherTests(unittest.TestCase):
    def test_both_launchers_run_guide_mode_with_vision_and_a_task(self):
        for name in ("run_trials.ps1", "run_trials.sh"):
            src = (ROOT / name).read_text(encoding="utf-8")
            self.assertRegex(src, r'"--mode",\s*"guide"|--mode guide', name)
            self.assertRegex(src, r'"--perception",\s*"vision"|--perception vision', name)
            self.assertIn("--task", src, name)
            self.assertNotRegex(src, r'--mode"?,?\s*"?hello', name)        # never the hello test
            self.assertNotIn("--allow-hello", src, name)
            self.assertIn("trials.local.json", src, name)                   # refuses a task other than trials.json's
            self.assertIsNone(re.search(r"[A-Z]:\\\\", src), name)          # no drive letters

    def test_shell_launcher_has_lf_endings(self):
        self.assertNotIn(b"\r\n", (ROOT / "run_trials.sh").read_bytes())


class SessionCheckHelperTests(unittest.TestCase):
    def test_worker_positions_from_session_json(self):
        s = {"workers": ["Worker_C1 (8.75, -4.00)", "Worker_J1 (8.75, 1.00)", "Worker_C3 (8.75, 6.00)"]}
        self.assertEqual(sc.worker_positions(s), {"C1": (8.75, -4.0), "J1": (8.75, 1.0), "C3": (8.75, 6.0)})

    def test_stop_segments_split_at_each_scan(self):
        trace = sc.parse_trace(["0.00:navigate", "9.10:scan", "9.60:approach", "12.0:ask", "12.5:read", "13.6:execute",
                                "15.0:navigate", "28.0:scan", "28.5:approach", "30.0:ask", "30.5:read", "31.6:execute",
                                "33.0:navigate", "60.0:done"])
        segs = sc.stop_segments(trace)
        self.assertEqual([s["t_scan"] for s in segs], [9.1, 28.0])
        self.assertEqual([st for _, st in segs[0]["states"]], ["scan", "approach", "ask", "read", "execute", "navigate"])
        self.assertEqual(sc.first(segs[1]["states"], "execute"), 31.6)


if __name__ == "__main__":
    unittest.main()
