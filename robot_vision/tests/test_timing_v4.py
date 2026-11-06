"""bridge/timing_v4.py, timing_check_v4.py and the v4 server wiring of the worker processes. No real model, no machine-speed
assert: the numbers are synthetic, and the loop monitor test only checks what was recorded, not how fast."""

import asyncio
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))

import decision_io as dio  # noqa: E402
import run_paths as rp  # noqa: E402
import timing_check_v4 as tc  # noqa: E402
from bridge import perception_mp_v4 as mpv  # noqa: E402
from bridge import server as S  # noqa: E402
from bridge import timing_v4 as T  # noqa: E402

V4 = json.loads((ROOT / "configs" / "v4" / "bridge.json").read_text(encoding="utf-8"))
V3 = json.loads((ROOT / "configs" / "bridge.json").read_text(encoding="utf-8"))


class StatsTests(unittest.TestCase):
    def test_nearest_rank_percentile(self):
        v = list(range(1, 101))
        self.assertEqual((T.pct(v, 50), T.pct(v, 99), T.pct(v, 100), T.pct(v, 0.1)), (50, 99, 100, 1))
        self.assertEqual(T.pct([5.0], 99), 5.0)
        self.assertIsNone(T.pct([], 99))

    def test_lag_stats(self):
        s = T.lag_stats([1.0] * 97 + [60.0, 120.0, 300.0])
        self.assertEqual((s["n"], s["p50_ms"], s["max_ms"]), (100, 1.0, 300.0))
        self.assertEqual((s["over_50ms"], s["over_100ms"], s["over_250ms"]), (3, 2, 1))
        self.assertEqual(s["p99_ms"], 120.0)
        self.assertEqual(T.lag_stats([]), {"n": 0})

    def test_reply_stats_round_trip_and_gaps(self):
        rows = [(1, 0.00, 0.01, 10.0), (2, 0.05, 0.06, 10.0), (3, 0.10, 0.31, 210.0), (4, 0.15, 0.32, 170.0)]
        s = T.reply_stats(rows, unanswered=2)
        self.assertEqual((s["n"], s["unanswered"]), (4, 2))
        self.assertEqual((s["round_trip_ms"]["max"], s["round_trip_ms"]["over_100ms"], s["round_trip_ms"]["over_300ms"]), (210.0, 2, 0))
        self.assertAlmostEqual(s["reply_gap_ms"]["max"], 250.0, places=3)           # 0.06 -> 0.31: the silence the watchdog sees
        self.assertEqual(s["reply_gap_ms"]["over_150ms"], 1)

    def test_reply_stats_unsorted_rows_and_empty(self):
        rows = [(2, 0.05, 0.06, 10.0), (1, 0.00, 0.01, 10.0)]
        self.assertAlmostEqual(T.reply_stats(rows)["reply_gap_ms"]["max"], 50.0, places=3)
        self.assertEqual(T.reply_stats([]), {"n": 0, "unanswered": 0})

    def test_handle_stats_reads_only_incoming_telemetry(self):
        with tempfile.TemporaryDirectory() as t:
            p = Path(t) / "messages.jsonl"
            lines = [{"dir": "in", "type": "telemetry", "handle_ms": 1.0}, {"dir": "in", "type": "telemetry", "handle_ms": 3.0},
                     {"dir": "in", "type": "frame_360", "handle_ms": 99.0}, {"dir": "out", "type": "command"},
                     {"dir": "in", "type": "telemetry"}]
            p.write_text("\n".join(json.dumps(x) for x in lines) + "\nnot json\n", encoding="utf-8")
            self.assertEqual(T.handle_stats(p), {"n": 2, "mean_ms": 2.0, "p99_ms": 3.0, "max_ms": 3.0})
            (Path(t) / "e.jsonl").write_text("", encoding="utf-8")
            self.assertEqual(T.handle_stats(Path(t) / "e.jsonl"), {"n": 0})

    def test_read_replies_round_trips_the_replay_clients_file(self):
        with tempfile.TemporaryDirectory() as t:
            p = Path(t) / "replies.csv"
            p.write_text("telemetry_seq,sent_s,reply_s,round_trip_ms\r\n3,0.1,0.101,1.0\r\n4,0.15,0.152,2.0\r\n", encoding="utf-8")
            self.assertEqual(T.read_replies(p), [(3, 0.1, 0.101, 1.0), (4, 0.15, 0.152, 2.0)])


class EvaluateTests(unittest.TestCase):
    LIM = {"loop_lag_p99_ms": 25, "loop_lag_max_ms": 100, "unanswered_telemetry": 0, "declared": "text", "note": "text"}

    def test_pass_and_fail(self):
        ok = T.evaluate(self.LIM, {"loop_lag_p99_ms": 25.0, "loop_lag_max_ms": 99.0, "unanswered_telemetry": 0})
        self.assertTrue(ok["declared"] and ok["passed"])
        bad = T.evaluate(self.LIM, {"loop_lag_p99_ms": 25.1, "loop_lag_max_ms": 99.0, "unanswered_telemetry": 0})
        self.assertFalse(bad["passed"])
        self.assertEqual([c["metric"] for c in bad["checks"] if not c["ok"]], ["loop_lag_p99_ms"])

    def test_a_limit_that_was_not_measured_fails(self):
        r = T.evaluate(self.LIM, {"loop_lag_p99_ms": 1.0, "loop_lag_max_ms": None, "unanswered_telemetry": 0})
        self.assertFalse(r["passed"])

    def test_unknown_numeric_limit_name_fails_and_text_entries_are_ignored(self):
        r = T.evaluate({**self.LIM, "loop_lag_p95_ms": 10}, {"loop_lag_p99_ms": 1.0, "loop_lag_max_ms": 1.0, "unanswered_telemetry": 0})
        self.assertFalse(r["passed"])
        self.assertEqual(r["unknown_limit_names"], ["loop_lag_p95_ms"])

    def test_no_limits_declared_is_numbers_only(self):
        r = T.evaluate(None, {"loop_lag_p99_ms": 1.0})
        self.assertEqual((r["declared"], r["passed"]), (False, None))


class DeclaredConfigTests(unittest.TestCase):
    def test_limits_name_known_metrics_only_and_are_at_most_half_the_watchdog(self):
        lim = V4["timing_limits"]
        numeric = {k: v for k, v in lim.items() if isinstance(v, (int, float))}
        self.assertEqual(set(numeric), set(T.METRICS))
        self.assertIn("BEFORE the worker-process fix was measured", lim["declared"])
        wd_ms = V4["watchdog_timeout_s"] * 1000.0
        for k in ("loop_lag_max_ms", "round_trip_max_ms", "reply_gap_max_ms"):
            self.assertLessEqual(lim[k], wd_ms / 2, k)
        for k in ("unanswered_telemetry", "perception_worker_events"):
            self.assertEqual(lim[k], 0)

    def test_worker_settings(self):
        w = V4["perception_workers"]
        self.assertIn(w["mode"], ("threads", "processes"))
        self.assertEqual(w["start_method"], "spawn")
        self.assertEqual(set(w) - {"note"}, {"mode", "start_method", "ready_timeout_s", "behind_after_s", "health_poll_s", "stop_timeout_s"})
        self.assertLessEqual(w["behind_after_s"], 1.0)                 # people_stale_s of the frozen v3 control config

    def test_protocol_2_config_is_untouched_by_the_timing_work(self):
        for k in ("timing", "timing_limits", "perception_workers"):
            self.assertNotIn(k, V3)
        self.assertEqual(V3["protocol_version"], 2)

    def test_v4_rates_and_watchdog_are_still_the_v3_ones(self):
        for k in ("telemetry_hz", "frame_360_hz", "frame_pan_tilt_hz", "watchdog_timeout_s", "jpeg_quality", "max_pending_frames"):
            self.assertEqual(V4[k], V3[k], k)


class LoopLagMonitorTests(unittest.IsolatedAsyncioTestCase):
    async def test_every_sample_is_kept_and_summarised(self):
        with tempfile.TemporaryDirectory() as t:
            m = T.LoopLagMonitorV4(Path(t), interval_s=0.002, threshold_ms=1e9, dump_after_s=3600.0)
            m.start()
            await asyncio.sleep(0.15)
            await m.stop()
            s = m.summary()
            self.assertGreater(m.ticks, 5)
            self.assertEqual((len(m.samples), s["all_samples"]["n"], s["ticks"]), (m.ticks, m.ticks, m.ticks))
            self.assertEqual(s["all_samples"]["max_ms"], round(max(m.samples), 3))
            self.assertIn("p99_ms", s["all_samples"])
            self.assertIn("worst", s)                                  # the v3 summary keys are kept

    async def test_a_stall_is_recorded_and_dumped(self):
        import time
        with tempfile.TemporaryDirectory() as t:
            m = T.LoopLagMonitorV4(Path(t), interval_s=0.002, threshold_ms=20.0, dump_after_s=0.05)
            m.start()
            await asyncio.sleep(0.02)
            time.sleep(0.12)                                           # the loop cannot run: a synthetic stall
            await asyncio.sleep(0.02)
            await m.stop()
            self.assertGreaterEqual(len(m.events), 1)
            self.assertGreater(m.summary()["all_samples"]["max_ms"], 20.0)
            dump = (Path(t) / "stall_tracebacks.txt").read_text(encoding="utf-8")
            self.assertIn("the stall dumped above ended", dump)

    def test_protocol_2_monitor_is_still_the_old_class(self):
        import bridge.diagnostics as diag
        self.assertFalse(hasattr(diag.LoopLagMonitor, "samples"))
        self.assertTrue(issubclass(T.LoopLagMonitorV4, diag.LoopLagMonitor))


def write_server_run(d: Path, lag_p99=3.0, lag_max=20.0, events=0, dumps=0):
    d.mkdir(parents=True)
    summary = {"event_loop_lag": {"max_lag_ms": lag_max, "worst": [], "all_samples": {"n": 1000, "p99_ms": lag_p99, "max_ms": lag_max}},
               "perception": {"worker_events": [{"event": "behind"}] * events}, "python_receive_lag": {"max_ms": 1.0},
               "gc_pauses": {"max_ms": 1.0}}
    (d / "summary.json").write_text(json.dumps(summary), encoding="utf-8")
    (d / "messages.jsonl").write_text(json.dumps({"dir": "in", "type": "telemetry", "handle_ms": 0.5}) + "\n", encoding="utf-8")
    (d / "stall_tracebacks.txt").write_text("--- the stall dumped above ended at t\n" * dumps, encoding="utf-8")


def write_replay(d: Path, rtt=2.0, gap=0.05, n=40, unanswered=0):
    d.mkdir(parents=True)
    rows = ["telemetry_seq,sent_s,reply_s,round_trip_ms"] + [f"{i},{i * gap:.4f},{i * gap + rtt / 1000:.4f},{rtt}" for i in range(n)]
    (d / "replies.csv").write_text("\n".join(rows) + "\n", encoding="utf-8")
    return {"unanswered": unanswered}


class CheckScriptTests(unittest.TestCase):
    def test_measure_passes_within_the_declared_limits(self):
        with tempfile.TemporaryDirectory() as t:
            sd, rd = Path(t) / "server", Path(t) / "replay"
            write_server_run(sd)
            rs = write_replay(rd)
            r = tc.measure(sd, rd, rs, V4["timing_limits"])
            self.assertTrue(r["evaluation"]["passed"], r["evaluation"])
            self.assertEqual((r["measured"]["loop_lag_p99_ms"], r["measured"]["unanswered_telemetry"]), (3.0, 0))
            self.assertAlmostEqual(r["measured"]["reply_gap_max_ms"], 50.0, places=2)
            self.assertEqual(r["stall_dumps"], 0)

    def test_measure_fails_on_a_stall_a_missed_reply_or_a_worker_event(self):
        for kw_server, kw_replay, metric in (({"lag_max": 250.0}, {}, "loop_lag_max_ms"), ({"events": 1}, {}, "perception_worker_events"),
                                             ({}, {"unanswered": 1}, "unanswered_telemetry"), ({}, {"gap": 0.2}, "reply_gap_max_ms"),
                                             ({}, {"rtt": 160.0}, "round_trip_max_ms")):
            with tempfile.TemporaryDirectory() as t:
                sd, rd = Path(t) / "server", Path(t) / "replay"
                write_server_run(sd, **kw_server)
                rs = write_replay(rd, **kw_replay)
                r = tc.measure(sd, rd, rs, V4["timing_limits"])
                self.assertFalse(r["evaluation"]["passed"], metric)
                self.assertIn(metric, [c["metric"] for c in r["evaluation"]["checks"] if not c["ok"]])

    def test_report_markdown_lists_limits_stacks_and_mode(self):
        with tempfile.TemporaryDirectory() as t:
            sd, rd = Path(t) / "server", Path(t) / "replay"
            write_server_run(sd, dumps=2)
            rs = write_replay(rd)
            rep = {"label": "unit test", "perception_mode": "processes", "duration_s": 60.0, "git": {"commit": "abc1234567"},
                   "platform": "test", "result": tc.measure(sd, rd, rs, V4["timing_limits"]), "stall_traceback_excerpt": "STACK",
                   "server_run_folder": "{output_root}/x"}
            md = tc.markdown(rep)
            for word in ("unit test", "**processes**", "All limits met", "loop_lag_p99_ms", "2 dump(s)", "STACK"):
                self.assertIn(word, md)
            rep["result"] = tc.measure(sd, rd, rs, None)
            self.assertIn("No limits declared", tc.markdown(rep))

    def test_wait_for_listening_finds_the_run_folder_and_reports_an_early_exit(self):
        with tempfile.TemporaryDirectory() as t:
            log = Path(t) / "server.log"
            line = "[bridge] mode guide: listening on 127.0.0.1:5005; run folder /some/where/bridge_guide_1"
            log.write_text("noise\n" + line + "\n", encoding="utf-8")
            proc = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"])
            try:
                self.assertEqual(tc.wait_for_listening(proc, log, 5.0), Path("/some/where/bridge_guide_1"))
            finally:
                proc.kill()
                proc.wait()
            log.write_text("Traceback: boom\n", encoding="utf-8")
            dead = subprocess.Popen([sys.executable, "-c", "pass"])
            dead.wait()
            with self.assertRaises(SystemExit) as e:
                tc.wait_for_listening(dead, log, 5.0)
            self.assertIn("boom", str(e.exception))

    def test_script_refuses_a_protocol_2_config(self):
        with self.assertRaises(SystemExit):
            tc.main(["--frames", "x", "--config", "configs/bridge.json"])


class ServerWiringTests(unittest.IsolatedAsyncioTestCase):
    async def run_server(self, mode):
        from test_perception_mp_v4 import specs
        made = []

        def fake_processes(out, perception_config, reader, commander, wcfg):
            made.append(wcfg)
            w = mpv.ProcessPerceptionV4(specs(), out, wcfg, verbose=False)
            w.wait_started()
            return w

        real_p, real_t = S.make_perception_processes_v4, S.make_perception_worker_v4
        S.make_perception_processes_v4 = fake_processes
        S.make_perception_worker_v4 = lambda *a, **k: self.fail("the threaded worker must not be built in processes mode")
        try:
            with tempfile.TemporaryDirectory() as tmp:
                cfg = {**V4, "port": 0, "paths": {"output_root": tmp}, "perception_workers": {**V4["perception_workers"], "mode": mode}}
                try:
                    out = await S.run(cfg, ROOT / "configs" / "v4" / "bridge.json", "guide", duration_s=0.4, perception="vision", task="Task2")
                finally:
                    rp.set_active_roots({})
                info = json.loads((out / "run_info.json").read_text(encoding="utf-8"))
                summary = json.loads((out / "summary.json").read_text(encoding="utf-8"))
                files = sorted(p.name for p in out.iterdir())
                return made, info, summary, files
        finally:
            S.make_perception_processes_v4, S.make_perception_worker_v4 = real_p, real_t

    async def test_processes_mode_builds_the_worker_processes_and_records_it(self):
        made, info, summary, files = await self.run_server("processes")
        self.assertEqual(len(made), 1)
        self.assertEqual(info["perception_workers"], "processes")
        self.assertEqual(summary["perception"]["mode"], "processes")
        self.assertEqual(summary["perception"]["worker_events"], [])
        self.assertIn("all_samples", summary["event_loop_lag"])
        self.assertIn("perception_events.jsonl", files)
        self.assertIn("perception.csv", files)
        self.assertEqual(info["inference_devices"]["worker_processes"], True)

    async def test_threads_mode_does_not_start_processes(self):
        called = []
        real = S.make_perception_worker_v4

        class FakeThreads:
            label = "fake"
            p = object()

            def summary(self):
                return {"mode": "threads"}

            def close(self):
                pass

            def snapshot(self):
                return {}

            ready = False

        S.make_perception_worker_v4 = lambda *a, **k: called.append(1) or FakeThreads()
        real_p = S.make_perception_processes_v4
        S.make_perception_processes_v4 = lambda *a, **k: self.fail("processes in threads mode")
        try:
            with tempfile.TemporaryDirectory() as tmp:
                cfg = {**V4, "port": 0, "paths": {"output_root": tmp}, "perception_workers": {**V4["perception_workers"], "mode": "threads"}}
                try:
                    out = await S.run(cfg, ROOT / "configs" / "v4" / "bridge.json", "guide", duration_s=0.2, perception="vision", task="Task2")
                finally:
                    rp.set_active_roots({})
                self.assertEqual(json.loads((out / "run_info.json").read_text(encoding="utf-8"))["perception_workers"], "threads")
        finally:
            S.make_perception_worker_v4, S.make_perception_processes_v4 = real, real_p
        self.assertEqual(called, [1])

    async def test_protocol_2_run_records_nothing_about_workers_and_keeps_the_old_monitor(self):
        cfg, cfg_path = S.load_config()
        with tempfile.TemporaryDirectory() as tmp:
            cfg = {**cfg, "port": 0, "paths": {"output_root": tmp}}
            try:
                out = await S.run(cfg, cfg_path, "guide", duration_s=0.2, perception="off", task="Task2")
            finally:
                rp.set_active_roots({})
            self.assertNotIn("perception_workers", json.loads((out / "run_info.json").read_text(encoding="utf-8")))
            self.assertNotIn("all_samples", json.loads((out / "summary.json").read_text(encoding="utf-8"))["event_loop_lag"])


if __name__ == "__main__":
    unittest.main()
