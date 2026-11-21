"""The stall stack dump of the v4 server has an explicit switch (AUDIT.md 16.27, an instrument setting, not a decision rule): configs/v4/bridge.json timing.stall_dump.

A dump of a stalled process crashed a step-5 server natively (python312.dll, 0xc0000005, inside CPython's _Py_DumpTracebackThreads, reached through faulthandler.dump_traceback_later).
OFF (false): no stall_tracebacks.txt, faulthandler.dump_traceback_later is never scheduled and never cancelled, the loop-lag log (loop_lag.csv), the events and every sample stay.
Absent or true: as before 16.27. The protocol 2 monitor (bridge/diagnostics.py) is not touched."""

import asyncio
import csv
import json
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))

import run_paths as rp  # noqa: E402
from bridge import diagnostics as diag  # noqa: E402
from bridge import server as S  # noqa: E402
from bridge import timing_v4 as T  # noqa: E402
from test_protocol_v3 import V3_CFG  # noqa: E402
from test_v4_integration import FakeWorkerV4  # noqa: E402

V4 = json.loads((ROOT / "configs" / "v4" / "bridge.json").read_text(encoding="utf-8"))


async def stalled_run(out: Path | None, **kw):
    """A monitor with a 20 ms threshold and a 50 ms dump time, one synthetic stall of 120 ms (the loop cannot run), with faulthandler replaced by recorders."""
    with mock.patch.object(T.faulthandler, "dump_traceback_later") as dump, mock.patch.object(T.faulthandler, "cancel_dump_traceback_later") as cancel:
        m = T.LoopLagMonitorV4(out, interval_s=0.002, threshold_ms=20.0, dump_after_s=0.05, **kw)
        m.start()
        await asyncio.sleep(0.02)
        time.sleep(0.12)
        await asyncio.sleep(0.02)
        await m.stop()
    return m, dump, cancel


class DumpOff(unittest.IsolatedAsyncioTestCase):
    async def test_nothing_is_scheduled_nor_cancelled_and_the_lag_is_still_logged(self):
        with tempfile.TemporaryDirectory() as t:
            m, dump, cancel = await stalled_run(Path(t), stall_dump=False)
            self.assertEqual(dump.call_count, 0)                                               # never scheduled
            self.assertEqual(cancel.call_count, 0)                                             # never cancelled: faulthandler is not touched at all
            self.assertGreaterEqual(len(m.events), 1)                                          # the stall is recorded ...
            self.assertGreater(m.summary()["all_samples"]["max_ms"], 20.0)                     # ... and every sample is kept
            self.assertEqual(len(m.samples), m.ticks)
            with (Path(t) / "loop_lag.csv").open(encoding="utf-8") as fh:                      # the lag log is written as before
                rows = list(csv.reader(fh))
            self.assertEqual(rows[0], ["t_wall_s", "lag_ms", "threads"])
            self.assertGreaterEqual(len(rows) - 1, 1)
            self.assertGreater(float(rows[1][1]), 20.0)
            self.assertEqual(sorted(p.name for p in Path(t).iterdir()), ["loop_lag.csv"])      # no stall_tracebacks.txt
            self.assertTrue(m._csv_file.closed)                                                # the lag log is closed (a run folder can be zipped or deleted)

    async def test_the_summary_says_the_dump_was_off(self):
        with tempfile.TemporaryDirectory() as t:
            m, _, _ = await stalled_run(Path(t), stall_dump=False)
            s = m.summary()
            self.assertIs(s["stall_dump"], False)
            self.assertIsNone(s["stall_dump_after_s"])
            self.assertIn("OFF (AUDIT.md 16.27)", s["note"])
            self.assertNotIn("writes the stacks", s["note"])
            for k in ("interval_ms", "threshold_ms", "ticks", "over_threshold", "max_lag_ms", "over_250ms", "worst", "all_samples"):
                self.assertIn(k, s)                                                            # the lag summary keeps every key
            self.assertGreaterEqual(s["over_threshold"], 1)

    async def test_without_a_run_folder_it_still_measures(self):
        m, dump, cancel = await stalled_run(None, stall_dump=False)
        self.assertEqual((dump.call_count, cancel.call_count), (0, 0))
        self.assertGreaterEqual(len(m.events), 1)

    async def test_a_real_stall_with_the_dump_off_writes_no_stack(self):
        """No mock: the real faulthandler, a stall far longer than dump_after_s, and still nothing is dumped."""
        with tempfile.TemporaryDirectory() as t:
            m = T.LoopLagMonitorV4(Path(t), interval_s=0.002, threshold_ms=20.0, dump_after_s=0.05, stall_dump=False)
            m.start()
            await asyncio.sleep(0.02)
            time.sleep(0.2)
            await asyncio.sleep(0.02)
            await m.stop()
            self.assertGreaterEqual(len(m.events), 1)
            self.assertFalse((Path(t) / "stall_tracebacks.txt").exists())


class DumpOn(unittest.IsolatedAsyncioTestCase):
    async def test_absent_and_true_are_the_behaviour_before_16_27(self):
        for kw in ({}, {"stall_dump": True}):
            with tempfile.TemporaryDirectory() as t:
                m, dump, cancel = await stalled_run(Path(t), **kw)
                self.assertGreater(dump.call_count, 1, kw)                                     # re-armed before every sleep
                for call in dump.call_args_list:
                    self.assertEqual(call.args, (0.05,))
                    self.assertIs(call.kwargs["repeat"], False)
                self.assertGreaterEqual(cancel.call_count, 1, kw)                              # cancelled at stop
                self.assertEqual(sorted(p.name for p in Path(t).iterdir()), ["loop_lag.csv", "stall_tracebacks.txt"], kw)
                self.assertIn("the stall dumped above ended", (Path(t) / "stall_tracebacks.txt").read_text(encoding="utf-8"), kw)      # the end-of-stall marker of the base class
                s = m.summary()
                self.assertEqual((s["stall_dump"], s["stall_dump_after_s"]), (True, 0.05))
                self.assertIn("the stack dump is written when a stall exceeds stall_dump_after_s", s["note"])

    async def test_with_the_real_faulthandler_a_stall_is_still_dumped(self):
        with tempfile.TemporaryDirectory() as t:
            m = T.LoopLagMonitorV4(Path(t), interval_s=0.002, threshold_ms=20.0, dump_after_s=0.05, stall_dump=True)
            m.start()
            await asyncio.sleep(0.02)
            time.sleep(0.12)
            await asyncio.sleep(0.02)
            await m.stop()
            self.assertIn("the stall dumped above ended", (Path(t) / "stall_tracebacks.txt").read_text(encoding="utf-8"))


class Refusals(unittest.TestCase):
    def test_off_is_an_explicit_false_not_anything_else(self):
        for bad in (0, 1, None, "false", "off", 0.0):
            with self.assertRaisesRegex(ValueError, "stall_dump must be true or false"):
                T.LoopLagMonitorV4(None, stall_dump=bad)

    def test_the_protocol_2_monitor_is_untouched(self):
        import inspect
        self.assertNotIn("stall_dump", inspect.signature(diag.LoopLagMonitor.__init__).parameters)
        self.assertFalse(hasattr(diag.LoopLagMonitor, "stall_dump"))
        self.assertTrue(issubclass(T.LoopLagMonitorV4, diag.LoopLagMonitor))


class Config(unittest.TestCase):
    def test_the_v4_bridge_config_has_the_dump_off(self):
        self.assertIs(V4["timing"]["stall_dump"], False)                                        # an explicit false ...
        self.assertEqual(V4["timing"]["stall_dump_after_s"], 0.1)                               # ... not a large stall_dump_after_s: the setting for when it is on
        self.assertEqual(V4["timing"]["loop_lag_threshold_ms"], 50.0)                           # the lag measurement is unchanged
        self.assertIn("16.27", V4["timing"]["note"])
        self.assertEqual(V4["protocol_version"], 3)

    def test_the_v3_bridge_config_is_untouched(self):
        v3 = json.loads((ROOT / "configs" / "bridge.json").read_text(encoding="utf-8"))
        self.assertNotIn("stall_dump", json.dumps(v3))

    def test_a_non_boolean_in_the_config_is_refused_before_the_server_starts(self):
        for bad in ("false", 0, None):
            cfg = json.loads(json.dumps(V4))
            cfg["timing"]["stall_dump"] = bad
            with tempfile.TemporaryDirectory() as t:
                p = Path(t) / "bridge.json"
                p.write_text(json.dumps(cfg), encoding="utf-8")
                with self.assertRaisesRegex(ValueError, "timing.stall_dump must be true or false"):
                    S.load_config(p)
        for ok in (True, False):                                                                # true and false load; an absent key loads too
            cfg = json.loads(json.dumps(V4))
            cfg["timing"]["stall_dump"] = ok
            with tempfile.TemporaryDirectory() as t:
                p = Path(t) / "bridge.json"
                p.write_text(json.dumps(cfg), encoding="utf-8")
                self.assertEqual(S.load_config(p)[0]["timing"]["stall_dump"], ok)
        cfg = json.loads(json.dumps(V4))
        del cfg["timing"]["stall_dump"]
        with tempfile.TemporaryDirectory() as t:
            p = Path(t) / "bridge.json"
            p.write_text(json.dumps(cfg), encoding="utf-8")
            S.load_config(p)


class ServerRun(unittest.IsolatedAsyncioTestCase):
    """A real (short) protocol 3 server run in guide mode, the monitor made by the server from the config."""

    async def run_server(self, stall_dump):
        cfg = {**V3_CFG, "port": 0, "perception_workers": {"mode": "threads"}, "timing": dict(V3_CFG["timing"])}
        if stall_dump == "absent":
            cfg["timing"].pop("stall_dump", None)
        else:
            cfg["timing"]["stall_dump"] = stall_dump
        real = S.make_perception_worker_v4
        S.make_perception_worker_v4 = lambda *a, **k: FakeWorkerV4()
        try:
            with tempfile.TemporaryDirectory() as tmp:
                cfg["paths"] = {"output_root": tmp}
                try:
                    out = await S.run(cfg, ROOT / "configs" / "v4" / "bridge.json", "guide", duration_s=0.3, perception="vision", task="Task2")
                finally:
                    rp.set_active_roots({})
                files = sorted(p.name for p in out.iterdir())
                summary = json.loads((out / "summary.json").read_text(encoding="utf-8"))["event_loop_lag"]
                return files, summary
        finally:
            S.make_perception_worker_v4 = real

    async def test_the_shipped_config_gives_a_run_without_a_stack_file_and_with_the_lag_log(self):
        files, lag = await self.run_server(V4["timing"]["stall_dump"])
        self.assertIn("loop_lag.csv", files)
        self.assertNotIn("stall_tracebacks.txt", files)
        self.assertIs(lag["stall_dump"], False)
        self.assertIsNone(lag["stall_dump_after_s"])
        self.assertGreater(lag["ticks"], 0)
        self.assertIn("all_samples", lag)

    async def test_true_and_an_absent_key_keep_the_stack_file(self):
        for value in (True, "absent"):
            files, lag = await self.run_server(value)
            self.assertIn("stall_tracebacks.txt", files, value)
            self.assertIn("loop_lag.csv", files, value)
            self.assertIs(lag["stall_dump"], True, value)
            self.assertEqual(lag["stall_dump_after_s"], 0.1, value)


class TimingReport(unittest.TestCase):
    """timing_check_v4.py must not let '0 dumps' read as 'no stalls' when the dump was off."""

    def report(self, stall_dump):
        import timing_check_v4 as tc
        from test_timing_v4 import write_replay, write_server_run
        with tempfile.TemporaryDirectory() as t:
            sd, rd = Path(t) / "server", Path(t) / "replay"
            write_server_run(sd)
            if stall_dump is not None:
                summary = json.loads((sd / "summary.json").read_text(encoding="utf-8"))
                summary["event_loop_lag"]["stall_dump"] = stall_dump
                (sd / "summary.json").write_text(json.dumps(summary), encoding="utf-8")
            rs = write_replay(rd)
            rep = {"label": "unit test", "perception_mode": "threads", "duration_s": 60.0, "git": {"commit": "abc1234567"}, "platform": "test",
                   "result": tc.measure(sd, rd, rs, V4["timing_limits"]), "stall_traceback_excerpt": "", "server_run_folder": "{output_root}/x"}
            return tc.markdown(rep)

    def test_the_off_state_is_stated_and_the_missing_file_is_fine(self):
        md = self.report(False)
        self.assertIn("## Stall stacks: 0 dump(s) in stall_tracebacks.txt (the stack dump was OFF, AUDIT.md 16.27", md)
        self.assertIn("All limits met", md)                                                     # the limits (lag, round trip, ...) are evaluated as before

    def test_on_and_older_summaries_read_as_before(self):
        for state in (True, None):
            md = self.report(state)
            self.assertIn("## Stall stacks: 0 dump(s) in stall_tracebacks.txt\n", md + "\n")
            self.assertNotIn("OFF", md)


class Isolation(unittest.TestCase):
    def test_only_the_v4_monitor_and_the_server_wiring_changed(self):
        src = (ROOT / "bridge" / "server.py").read_text(encoding="utf-8")
        self.assertIn('stall_dump=t4.get("stall_dump", True)', src)
        self.assertIn("lag = diag.LoopLagMonitor(out, t0=log.t0)", src)                         # protocol 2: the old class, the old call
        self.assertNotIn("faulthandler", src)                                                   # the server itself never touches faulthandler


if __name__ == "__main__":
    unittest.main()
