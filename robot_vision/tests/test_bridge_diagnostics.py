"""Bridge diagnostics and launch safety (infrastructure, 2026-10-21): event-loop lag monitor, GC pause timer, heap
freeze, Unity's optional telemetry diagnostics in summary.json, hello mode refused without --allow-hello, guide mode
needs --task. No Unity, no models."""

import asyncio
import contextlib
import gc
import io
import sys
import tempfile
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from bridge import diagnostics as D  # noqa: E402
from bridge import server as S  # noqa: E402
from test_bridge import telemetry  # noqa: E402


class LoopLagTests(unittest.IsolatedAsyncioTestCase):
    async def test_blocking_call_on_the_loop_is_recorded_with_stacks(self):
        with tempfile.TemporaryDirectory() as tmp:
            m = D.LoopLagMonitor(Path(tmp), dump_after_s=0.1)
            m.start()
            await asyncio.sleep(0.05)
            time.sleep(0.3)                       # holds the loop, as a GIL-holding call would
            await asyncio.sleep(0.05)
            await m.stop()
            s = m.summary()
            self.assertEqual(s["over_threshold"], 1)
            self.assertGreater(s["max_lag_ms"], 250.0)
            self.assertIn("over_250ms", s)
            dump = (Path(tmp) / "stall_tracebacks.txt").read_text(encoding="utf-8")
            self.assertIn("test_blocking_call_on_the_loop_is_recorded_with_stacks", dump)   # where the loop was held
            self.assertIn("ended at t_wall_s", dump)
            self.assertNotRegex(dump, r"(?<![A-Za-z0-9])[A-Za-z]:[\\/]")              # no absolute paths
            self.assertIn("{project_root}/tests/test_bridge_diagnostics.py", dump)
            self.assertEqual(len((Path(tmp) / "loop_lag.csv").read_text().splitlines()), 2)

    async def test_quiet_loop_records_nothing(self):
        m = D.LoopLagMonitor(None)
        m.start()
        await asyncio.sleep(0.2)
        await m.stop()
        self.assertEqual(m.summary()["over_threshold"], 0)
        self.assertGreater(m.summary()["ticks"], 5)


class GcTests(unittest.TestCase):
    def test_collections_are_timed(self):
        m = D.GcMonitor(None, log_over_ms=0.0)
        try:
            gc.collect()
        finally:
            m.close()
        s = m.summary()
        self.assertGreaterEqual(s["collections"]["gen2"], 1)
        self.assertGreaterEqual(len(s["worst"]), 1)

    def test_freeze_makes_full_collections_cheap(self):
        keep = [[i] for i in range(200_000)]      # long-lived objects, like the loaded models
        try:
            info = D.freeze_heap()
            self.assertGreaterEqual(info["frozen_objects"], 200_000)
            self.assertLess(info["full_collect_ms_after"], info["full_collect_ms_before"])
        finally:
            gc.unfreeze()
            del keep

    def test_thread_info_lists_the_pools(self):
        info = D.thread_info()
        self.assertIn("python_threads", info)
        self.assertIn("process_threads", info)


class UnityDiagnosticsInSummaryTests(unittest.TestCase):
    def test_every_round_trip_and_receive_lag(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            log = S.RunLog(out, 0)
            log.event("connect", peer="x")
            # Python reads message 3 0.4 s late (by Unity's real-time clock); Unity measured 3 replies, worst 412 ms.
            for seq, (sent, extra) in enumerate([(0.00, {}), (0.05, {}), (0.10, {"rtt_window_n": 3, "rtt_window_max_ms": 412.0, "rtt_window_sum_ms": 420.0})]):
                h = telemetry(seq, realtime_s=10.0 + sent, frame_ms_max=16.0, **extra)
                log.t0 = time.monotonic() - sent - (0.4 if seq == 2 else 0.0)   # what now() returns at receipt
                log.message("in", {**h, "version": 2}, {})
            log.close()
            import json
            s = json.loads((out / "summary.json").read_text())
            self.assertEqual(s["round_trip"]["all_messages"]["max_ms"], 412.0)
            self.assertEqual(s["round_trip"]["all_messages"]["n"], 3)
            self.assertEqual(s["round_trip"]["all_messages"]["mean_ms"], 140.0)
            self.assertAlmostEqual(s["python_receive_lag"]["max_ms"], 400.0, delta=20.0)
            self.assertEqual(s["python_receive_lag"]["over_250ms"], 1)
            self.assertEqual(s["unity_frames"]["frame_ms_max"], 16.0)


class LaunchSafetyTests(unittest.TestCase):
    def refused(self, argv) -> str:
        err = io.StringIO()
        with contextlib.redirect_stderr(err), self.assertRaises(SystemExit) as cm:
            S.main(argv)
        self.assertNotEqual(cm.exception.code, 0)
        return err.getvalue()

    def test_hello_needs_allow_hello(self):
        self.assertIn("--allow-hello", self.refused(["--mode", "hello"]))

    def test_mode_is_required(self):
        self.assertIn("--mode", self.refused([]))

    def test_guide_needs_a_task(self):
        self.assertIn("--task", self.refused(["--mode", "guide", "--perception", "vision"]))


if __name__ == "__main__":
    unittest.main()
