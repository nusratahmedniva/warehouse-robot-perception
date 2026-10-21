"""Measurement correction (2026-10-22, AUDIT.md section 9): Unity's new telemetry diagnostics in summary.json (watchdog
events, network-thread and queued round trip, every frame time), the session check's side-by-side measures, the
resource monitor, the machine state and the launchers' development-only --trials override. No Unity, no models."""

import json
import sys
import tempfile
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import hri_session_check as sc  # noqa: E402
import launch_prep as lp  # noqa: E402
from bridge import machine_state as ms  # noqa: E402
from bridge import resource_monitor as rm  # noqa: E402
from bridge import server as S  # noqa: E402
from test_bridge import telemetry  # noqa: E402

NEW = {"rtt_clock": "network_thread", "watchdog_rule": "unanswered_sent_telemetry"}


class SummaryTests(unittest.TestCase):
    def test_watchdog_events_round_trips_and_frame_times(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            log = S.RunLog(out, 0)
            log.event("connect", peer="x")
            frames = [16.0] * 198 + [120.0, 320.0]
            stall = {"kind": "unity_frame_stall", "cause": "no_telemetry_sent", "start_realtime_s": 10.0,
                     "gap_ms": 345.0, "frame_ms_max": 320.0, "ended_by_disconnect": False}
            for seq, extra in enumerate([
                    {"frame_ms_list": frames[:100], "rtt_window_n": 2, "rtt_window_max_ms": 3.0, "rtt_window_sum_ms": 5.0,
                     "rtt_queue_window_n": 2, "rtt_queue_window_max_ms": 4.0, "rtt_queue_window_sum_ms": 7.0},
                    {"frame_ms_list": frames[100:], "unity_frame_stall_count": 1, "watchdog_events": [stall],
                     "rtt_window_n": 1, "rtt_window_max_ms": 2.0, "rtt_window_sum_ms": 2.0}]):
                h = telemetry(seq, realtime_s=10.0 + 0.05 * seq, frame_ms_max=max(extra["frame_ms_list"]), **NEW, **extra)
                log.message("in", {**h, "version": 2}, {})
            log.close()
            s = json.loads((out / "summary.json").read_text())
            self.assertEqual(s["round_trip"]["all_messages"]["clock"], "network_thread")
            self.assertEqual(s["round_trip"]["all_messages"]["max_ms"], 3.0)
            self.assertEqual(s["round_trip"]["all_messages_queued"]["max_ms"], 4.0)
            uf = s["unity_frames"]
            self.assertEqual((uf["frames"], uf["frame_ms_max_all"], uf["frames_over_100ms"], uf["frames_over_250ms"]),
                             (200, 320.0, 2, 1))
            self.assertEqual(uf["frame_ms_p99"], 16.0)       # nearest rank: the 198th of 200 frames
            wd = s["watchdog"]
            self.assertEqual((wd["rule"], wd["stops_reported_by_unity"], wd["unity_frame_stalls_reported_by_unity"]),
                             ("unanswered_sent_telemetry", 0, 1))
            self.assertEqual(wd["events_by_kind"], {"unity_frame_stall": {"n": 1, "max_gap_ms": 345.0}})

    def test_old_build_has_no_new_blocks(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            log = S.RunLog(out, 0)
            log.message("in", {**telemetry(0, realtime_s=1.0, frame_ms_max=16.0, rtt_window_n=1, rtt_window_max_ms=9.0,
                                           rtt_window_sum_ms=9.0), "version": 2}, {})
            log.close()
            s = json.loads((out / "summary.json").read_text())
            self.assertIsNone(s["watchdog"])
            self.assertNotIn("all_messages_queued", s["round_trip"])
            self.assertTrue(s["round_trip"]["all_messages"]["clock"].startswith("main_thread_queued"))


class SessionCheckMeasureTests(unittest.TestCase):
    def test_new_build_side_by_side(self):
        tel = [{"watchdog_count": 1, "unity_frame_stall_count": 0, **NEW, "frame_ms_list": [16.0] * 99 + [300.0]},
               {"watchdog_count": 1, "unity_frame_stall_count": 2, **NEW, "rtt_window_n": 1, "rtt_window_max_ms": 2.0,
                "rtt_window_sum_ms": 2.0, "rtt_queue_window_n": 1, "rtt_queue_window_max_ms": 2.5,
                "rtt_queue_window_sum_ms": 2.5, "watchdog_events": [{"kind": "unity_frame_stall", "gap_ms": 333.0}]}]
        m = sc.telemetry_measures(tel)
        self.assertEqual((m["watchdog_stops"], m["unity_frame_stalls"], m["old_rule_stops"]), (0, 2, 2))
        self.assertEqual((m["round_trip_ms"]["max"], m["round_trip_queued_ms"]["max"]), (2.0, 2.5))
        self.assertEqual(m["unity_frames"], {"frames": 100, "max_ms": 300.0, "p99_ms": 16.0, "over_100ms": 1})

    def test_old_build_reports_its_counter_as_the_old_rule(self):
        tel = [{"watchdog_count": 2, "rtt_window_n": 1, "rtt_window_max_ms": 250.0, "rtt_window_sum_ms": 250.0},
               {"watchdog_count": 3}]
        m = sc.telemetry_measures(tel)
        self.assertEqual((m["watchdog_stops"], m["old_rule_stops"]), (None, 1))
        self.assertEqual((m["round_trip_ms"]["max"], m["round_trip_queued_ms"]["max"]), (None, 250.0))


class LaunchPrepTests(unittest.TestCase):
    def configs(self, d: Path, mode="development", task="Task1") -> Path:
        c = d / "configs"
        c.mkdir()
        (c / "trials.json").write_text(json.dumps({"task": task, "mode": mode, "trial_count": 10}), encoding="utf-8")
        return c

    def test_trials_override_written_and_removed(self):
        with tempfile.TemporaryDirectory() as d:
            c = self.configs(Path(d))
            self.assertEqual(lp.prepare("Task1", 5, c), ("trials.local.json", "development"))
            local = json.loads((c / "trials.local.json").read_text(encoding="utf-8"))
            self.assertEqual((local["trial_count"], local["generated_by"]), (5, lp.MARKER))
            self.assertTrue(lp.cleanup(c))
            self.assertFalse((c / "trials.local.json").exists())
            self.assertEqual(json.loads((c / "trials.json").read_text())["trial_count"], 10)   # untouched

    def test_trials_refused_outside_development(self):
        for mode in ("final", "replication"):
            with tempfile.TemporaryDirectory() as d:
                c = self.configs(Path(d), mode=mode)
                with self.assertRaises(SystemExit) as cm:
                    lp.prepare("Task1", 5, c)
                self.assertIn("development", str(cm.exception))
                self.assertFalse((c / "trials.local.json").exists())
                self.assertEqual(lp.prepare("Task1", None, c), ("trials.json", mode))   # the full run is allowed

    def test_user_local_file_is_never_overwritten_or_removed(self):
        with tempfile.TemporaryDirectory() as d:
            c = self.configs(Path(d))
            (c / "trials.local.json").write_text(json.dumps({"task": "Task1", "mode": "development"}), encoding="utf-8")
            with self.assertRaises(SystemExit):
                lp.prepare("Task1", 5, c)
            self.assertFalse(lp.cleanup(c))
            self.assertTrue((c / "trials.local.json").exists())

    def test_task_mismatch_and_leftover(self):
        with tempfile.TemporaryDirectory() as d:
            c = self.configs(Path(d), task="Task2")
            with self.assertRaises(SystemExit):
                lp.prepare("Task1", None, c)
            # a leftover override from a killed launch is removed first, then the task is checked against trials.json
            (c / "trials.local.json").write_text(json.dumps({"task": "Task1", "mode": "development",
                                                             "generated_by": lp.MARKER}), encoding="utf-8")
            self.assertEqual(lp.prepare("Task2", None, c), ("trials.json", "development"))
            self.assertFalse((c / "trials.local.json").exists())

    def test_both_launchers_use_the_helper_and_the_resource_log(self):
        for name in ("run_trials.ps1", "run_trials.sh"):
            src = (ROOT / name).read_text(encoding="utf-8")
            self.assertIn("launch_prep.py", src, name)
            self.assertIn("--cleanup", src, name)
            self.assertIn("--resource-log", src, name)
            self.assertRegex(src, r"-Trials|--trials", name)


class MachineStateTests(unittest.TestCase):
    def test_read_never_raises_and_has_the_fields(self):
        s = ms.read()
        for k in ("system", "power_source", "power_mode", "warnings"):
            self.assertIn(k, s)

    def test_warnings(self):
        self.assertEqual(ms.warnings({"system": "Windows", "power_mode": "Best performance",
                                      "power_source": "mains (no battery)"}), [])
        w = ms.warnings({"system": "Windows", "power_mode": "Balanced", "power_source": "battery"})
        self.assertEqual(len(w), 2)
        self.assertEqual(ms.warnings({"system": "Darwin", "power_mode": "Low Power Mode off",
                                      "power_source": "mains (charger connected)"}), [])


class ResourceMonitorTests(unittest.TestCase):
    def test_rows_and_summary(self):
        with tempfile.TemporaryDirectory() as d:
            out = Path(d) / "resources.csv"
            t0 = time.monotonic()
            self.assertEqual(rm.run(out, None, interval_s=0.2, samples=2), 2)
            self.assertLess(time.monotonic() - t0, 10.0)
            s = rm.summarise(out)
            self.assertEqual(s["samples"], 2)
            self.assertIn("cpu_total_pct", s)
            self.assertIn("mem_available_mb", s)

    def test_server_accepts_the_flag(self):
        import argparse
        import contextlib
        import io
        err = io.StringIO()
        with contextlib.redirect_stderr(err), self.assertRaises(SystemExit):
            S.main(["--mode", "guide", "--resource-log"])          # refused for the missing --task, not the flag
        self.assertIn("--task", err.getvalue())
        self.assertNotIn("unrecognized", err.getvalue())
        del argparse


if __name__ == "__main__":
    unittest.main()
