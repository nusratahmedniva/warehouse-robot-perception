"""bridge/perception_mp_v4.py: the v4 perception in worker processes ("spawn"), with fake models. Nothing here depends on machine
speed: every wait is for a condition (a bound of 60 s only ends a test that would otherwise hang), and a worker is made "busy"
with a gate file, not with a sleep. The real models are not loaded (they are checked by timing_check_v4.py)."""

import csv
import json
import os
import signal
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))

import commander_v4 as cm  # noqa: E402
import gesture_motion as gm  # noqa: E402
from bridge import perception as bp  # noqa: E402
from bridge import perception_mp_v4 as mpv  # noqa: E402
from bridge import protocol as P  # noqa: E402
from bridge.perception_v4 import PerceptionWorkerV4  # noqa: E402

WAIT_S = 60.0                                   # only ever reached when something is broken


# ---------------------------------------------------------------- fake models (module level: the workers import them)

def _frame_index(img: bytes) -> int:
    return int.from_bytes(img[:4], "big")


def _gate(args: dict) -> None:
    g = args.get("gate")
    while g and Path(g).exists():
        time.sleep(0.005)


class FakePeople:
    label = "fake people"
    decode_jpeg = staticmethod(lambda b: b)

    def __init__(self, args=None):
        self.args = args or {}

    def people(self, img, heading, top, bottom, camera_height_m=None, centre_world_yaw_deg=0.0):
        _gate(self.args)
        i = _frame_index(img)
        if self.args.get("die_at") == i:
            os._exit(3)
        return [{"track_id": 1, "bearing_deg": float(i), "distance_m": 2.0 + i, "distance_source": "box_bottom",
                 "confidence": 0.9, "box_h": 100.0}], 1.5

    def inference_devices(self):
        return {"requested_device": "fake", "models": {"fake/people": {"device": "cpu"}}, "versions": {"fake": "1"}}


class FakeGesture:
    label = "fake gesture"
    decode_jpeg = staticmethod(lambda b: b)

    def __init__(self, args=None):
        self.args = args or {}

    def persons(self, img, meta):
        _gate(self.args)
        i = _frame_index(img)
        rd = gm.Reading("POINT" if i % 2 else "NONE", 0.5, "ok", meta["t"], arm="left")
        return [cm.PersonReading(i, float(i), True, "facing", rd, (1.0, 2.0, 3.0, 4.0))], {
            "yolo11s-pose/gesture": 2.0, "mediapipe/hands": 1.0, "reader/window": 0.5}

    def inference_devices(self):
        return {"requested_device": "fake", "models": {"fake/gesture": {"device": "cpu"}}, "versions": {"fake": "1"}}


class FakeBoth(FakePeople, FakeGesture):
    label = "fake both"


def fake_people(spec):
    if spec["args"].get("fail_start"):
        raise RuntimeError("cannot load the fake model")
    return FakePeople(spec["args"])


def fake_gesture(spec):
    return FakeGesture(spec["args"])


def specs(people=True, gesture=True, **args):
    out = []
    if people:
        out.append({"name": "people", "kind": "frame_360", "factory": "test_perception_mp_v4:fake_people", "args": args})
    if gesture:
        out.append({"name": "gesture", "kind": "frame_pan_tilt", "factory": "test_perception_mp_v4:fake_gesture", "args": args})
    return out


def frame(kind: str, i: int, size: int = 64) -> P.Message:
    h = {"type": kind, "seq": 10 + i, "time_s": round(0.1 * i, 3), "frame_index": i, "width": 730, "height": 530,
         "camera_height_m": 1.6, "pose": {"x": 1.0, "z": 2.0, "yaw_deg": 30.0}, "encoding": "jpeg"}
    if kind == "frame_360":
        h["centre_world_yaw_deg"] = 0.0
    else:
        h.update(fx=458.99, fy=458.99, cx=365.0, cy=265.0, vertical_fov_deg=60.0, pan_deg=0.0, tilt_deg=0.0)
    return P.Message(h, {"image": i.to_bytes(4, "big") + b"x" * size})


def wait_for(cond, what="condition"):
    t_end = time.monotonic() + WAIT_S
    while time.monotonic() < t_end:
        if cond():
            return
        time.sleep(0.01)
    raise AssertionError(f"timed out waiting for {what}")


def norm_v4(s: dict) -> dict:
    return {"persons": [(p.track_id, p.bearing_deg, p.facing, p.facing_why, p.reading.to_dict(), p.box) for p in s["persons"]],
            "persons_time_s": s["persons_time_s"], "fov_deg": s["fov_deg"], "pan_deg": s["pan_deg"]}


def csv_rows(path: Path) -> list[dict]:
    with path.open(newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    for r in rows:
        for k in ("t_wall_s", "decode_ms", "total_ms"):
            r.pop(k)
    return sorted(rows, key=lambda r: (r["type"], int(r["frame_index"])))


class SameResultsAsThreadsTests(unittest.TestCase):
    def test_snapshots_and_csv_rows_equal_the_threaded_worker_frame_by_frame(self):
        with tempfile.TemporaryDirectory() as t:
            (Path(t) / "thr").mkdir()
            (Path(t) / "mp").mkdir()
            thr = PerceptionWorkerV4(FakeBoth(), Path(t) / "thr", verbose=False)
            mp = mpv.ProcessPerceptionV4(specs(), Path(t) / "mp", verbose=False)
            try:
                mp.wait_started()
                self.assertFalse(mp.ready)
                for i in range(6):
                    for kind in ("frame_360", "frame_pan_tilt"):
                        for w in (thr, mp):
                            w.submit(frame(kind, i))
                        wait_for(lambda: thr.processed[kind] == i + 1 and mp.processed[kind] == i + 1, f"{kind} {i} processed")
                    a, b = thr.snapshot(), mp.snapshot()
                    self.assertEqual({k: a[k] for k in a if k != "inference_ms"}, {k: b[k] for k in b if k != "inference_ms"})
                    self.assertEqual(a["inference_ms"], b["inference_ms"])
                    self.assertEqual(norm_v4(thr.snapshot_v4()), norm_v4(mp.snapshot_v4()))
                self.assertTrue(thr.ready and mp.ready)
                self.assertEqual(mp.snapshot()["people_time_s"], 0.5)
                self.assertEqual(mp.snapshot()["target"]["distance_m"], 7.0)
                self.assertEqual(mp.snapshot()["people_pose"], {"x": 1.0, "z": 2.0, "yaw_deg": 30.0})
            finally:
                thr.close()
                mp.close()
            self.assertEqual(csv_rows(Path(t) / "thr" / "perception.csv"), csv_rows(Path(t) / "mp" / "perception.csv"))
            with (Path(t) / "mp" / "perception.csv").open(newline="", encoding="utf-8") as f:
                self.assertEqual(next(csv.reader(f)), bp.FIELDS)

    def test_snapshot_is_a_copy_and_the_interface_matches(self):
        mp = mpv.ProcessPerceptionV4(specs(), None, verbose=False)
        try:
            mp.wait_started()
            mp.submit(frame("frame_360", 3))
            wait_for(lambda: mp.processed["frame_360"] == 1)
            s = mp.snapshot()
            s["people"].clear()
            s["target"]["distance_m"] = -5
            self.assertEqual(len(mp.snapshot()["people"]), 1)
            self.assertEqual(mp.snapshot()["target"]["distance_m"], 5.0)
            for name in ("submit", "snapshot", "snapshot_v4", "summary", "close"):
                self.assertTrue(callable(getattr(mp, name)), name)
            self.assertTrue(mp.label.startswith("fake gesture"))
            dev = mp.p.inference_devices()
            self.assertEqual(set(dev["models"]), {"fake/people", "fake/gesture"})
            self.assertTrue(dev["worker_processes"])
        finally:
            mp.close()

    def test_ready_needs_a_processed_frame_of_each_camera(self):
        mp = mpv.ProcessPerceptionV4(specs(), None, verbose=False)
        try:
            mp.wait_started()
            self.assertFalse(mp.ready)
            mp.submit(frame("frame_360", 0))
            wait_for(lambda: mp.processed["frame_360"] == 1)
            self.assertFalse(mp.ready)
            mp.submit(frame("frame_pan_tilt", 0))
            wait_for(lambda: mp.ready, "ready")
        finally:
            mp.close()


class LatestFrameOnlyTests(unittest.TestCase):
    def test_a_busy_worker_gets_only_the_newest_frame_and_every_frame_is_accounted_for(self):
        with tempfile.TemporaryDirectory() as t:
            gate = Path(t) / "gate"
            gate.write_text("closed")
            mp = mpv.ProcessPerceptionV4(specs(people=False, gate=str(gate)), None, verbose=False)
            try:
                mp.wait_started()
                n = 40
                for i in range(n):
                    mp.submit(frame("frame_pan_tilt", i))
                gate.unlink()
                wait_for(lambda: mp.snapshot_v4()["persons_time_s"] == round(0.1 * (n - 1), 3), "the newest frame processed")
                s = mp.summary()["frame_pan_tilt"]
                wait_for(lambda: mp.summary()["frame_pan_tilt"]["processed"] + mp.summary()["frame_pan_tilt"]["dropped_in_server_mailbox"]
                         + mp.summary()["frame_pan_tilt"]["dropped_in_worker_mailbox"] == n, "every frame processed or dropped")
                s = mp.summary()["frame_pan_tilt"]
                self.assertEqual(s["submitted"], n)
                self.assertLess(s["processed"], n)                    # the busy worker skipped frames
                self.assertGreaterEqual(s["processed"], 1)            # at least the newest one
                self.assertEqual(s["alive"], True)
                self.assertEqual(mp.summary()["worker_events"], [])
            finally:
                mp.close()

    def pump(self, mp, n=300, size=1_000_000):
        for i in range(n):
            mp.submit(frame("frame_pan_tilt", i, size=size))
        for _ in range(200):
            mp.snapshot()
            mp.snapshot_v4()

    def run_pump(self, mp):
        th = threading.Thread(target=self.pump, args=(mp,), daemon=True)
        th.start()
        th.join(WAIT_S)
        self.assertFalse(th.is_alive(), "submit or snapshot blocked on a stuck worker")
        s = mp.summary()["frame_pan_tilt"]
        self.assertEqual(s["submitted"], 300)

    def test_submit_and_snapshot_never_block_while_the_worker_is_busy(self):
        with tempfile.TemporaryDirectory() as t:
            gate = Path(t) / "gate"
            gate.write_text("closed")
            mp = mpv.ProcessPerceptionV4(specs(people=False, gate=str(gate)), None, verbose=False)
            try:
                mp.wait_started()
                self.run_pump(mp)
            finally:
                gate.unlink()
                mp.close()

    @unittest.skipUnless(hasattr(signal, "SIGSTOP"), "needs SIGSTOP (POSIX)")
    def test_submit_and_snapshot_never_block_while_the_worker_reads_nothing(self):
        """The worker process is stopped (SIGSTOP): its pipe fills and only the sender thread blocks."""
        mp = mpv.ProcessPerceptionV4(specs(people=False), None, {"behind_after_s": 3600.0}, verbose=False)
        pid = None
        try:
            mp.wait_started()
            pid = mp.links["frame_pan_tilt"].proc.pid
            os.kill(pid, signal.SIGSTOP)
            self.run_pump(mp)
            self.assertGreater(mp.summary()["frame_pan_tilt"]["dropped_in_server_mailbox"], 0)
        finally:
            if pid is not None:
                os.kill(pid, signal.SIGCONT)
            mp.close()



class BehindRuleTests(unittest.TestCase):
    def test_pure_rule(self):
        self.assertFalse(mpv.is_behind(None, 1000.0, 0.5))               # nothing waiting (start-up, Unity idle): never behind
        self.assertFalse(mpv.is_behind(10.0, 10.5, 0.5))                 # exactly the limit is not over it
        self.assertTrue(mpv.is_behind(10.0, 10.6, 0.5))
        self.assertFalse(mpv.is_behind(10.4, 10.6, 0.5))

    def test_wait_state_follows_submit_and_result(self):
        """No clock involved: the wait starts at the first unanswered submit, restarts at the pending newer frame, ends with the answer."""
        with tempfile.TemporaryDirectory() as t:
            gate = Path(t) / "gate"
            gate.write_text("closed")
            mp = mpv.ProcessPerceptionV4(specs(people=False, gate=str(gate)), None, {"behind_after_s": 3600.0}, verbose=False)
            try:
                mp.wait_started()
                link = mp.links["frame_pan_tilt"]
                self.assertIsNone(link.waiting_since)                      # models ready, no frame yet: not waiting
                mp.submit(frame("frame_pan_tilt", 0))
                first = link.waiting_since
                self.assertIsNotNone(first)
                mp.submit(frame("frame_pan_tilt", 1))
                mp.submit(frame("frame_pan_tilt", 2))
                self.assertEqual(link.waiting_since, first)                # still the first unanswered one
                gate.unlink()
                wait_for(lambda: mp.processed["frame_pan_tilt"] >= 1 and link.waiting_since is None
                         and mp.snapshot_v4()["persons_time_s"] == 0.2, "the newest frame answered")
                self.assertIsNone(link.waiting_since)                      # all answered: nothing waits any more
                self.assertEqual(mp.summary()["worker_events"], [])
            finally:
                if gate.exists():
                    gate.unlink()
                mp.close()


class FailureTests(unittest.TestCase):
    def test_a_worker_that_dies_is_logged_and_the_last_results_stay(self):
        with tempfile.TemporaryDirectory() as t:
            mp = mpv.ProcessPerceptionV4(specs(die_at=2), Path(t), {"behind_after_s": 3600.0}, verbose=False)
            try:
                mp.wait_started()
                for i in (0, 1):
                    mp.submit(frame("frame_360", i))
                    mp.submit(frame("frame_pan_tilt", i))
                    wait_for(lambda: mp.processed["frame_360"] == i + 1 and mp.processed["frame_pan_tilt"] == i + 1)
                before = mp.snapshot()
                mp.submit(frame("frame_360", 2))                       # the people worker exits (os._exit(3)) on frame 2
                wait_for(lambda: any(e["event"] == "died" for e in mp.summary()["worker_events"]), "the death logged")
                ev = [e for e in mp.summary()["worker_events"] if e["event"] == "died"][0]
                self.assertEqual((ev["worker"], ev["exitcode"]), ("people", 3))
                for i in range(3, 50):                                  # the server keeps going: no raise, no block
                    mp.submit(frame("frame_360", i))
                after = mp.snapshot()
                self.assertEqual(after["people"], before["people"])
                self.assertEqual(after["people_time_s"], before["people_time_s"])    # stale by its capture time: unknown to the controller
                mp.submit(frame("frame_pan_tilt", 2))                  # the other worker is not affected
                wait_for(lambda: mp.processed["frame_pan_tilt"] == 3)
                self.assertEqual(mp.snapshot_v4()["persons_time_s"], 0.2)
                s = mp.summary()
                self.assertFalse(s["frame_360"]["alive"])
                self.assertTrue(s["frame_pan_tilt"]["alive"])
            finally:
                mp.close()
            lines = (Path(t) / "perception_events.jsonl").read_text(encoding="utf-8").splitlines()
            self.assertEqual([json.loads(x)["event"] for x in lines], ["died"])

    def test_a_worker_that_falls_behind_is_logged_and_recovers(self):
        with tempfile.TemporaryDirectory() as t:
            gate = Path(t) / "gate"
            mp = mpv.ProcessPerceptionV4(specs(people=False, gate=str(gate)), None,
                                         {"behind_after_s": 0.2, "health_poll_s": 0.02}, verbose=False)
            try:
                mp.wait_started()
                mp.submit(frame("frame_pan_tilt", 0))
                wait_for(lambda: mp.processed["frame_pan_tilt"] == 1)
                gate.write_text("closed")
                i = 1
                t_end = time.monotonic() + WAIT_S
                while time.monotonic() < t_end and not any(e["event"] == "behind" for e in mp.summary()["worker_events_all"]):
                    mp.submit(frame("frame_pan_tilt", i))               # frames keep arriving, none comes back
                    i += 1
                    time.sleep(0.02)
                self.assertTrue(any(e["event"] == "behind" for e in mp.summary()["worker_events_all"]), "no behind event")
                gate.unlink()
                mp.submit(frame("frame_pan_tilt", i))
                wait_for(lambda: any(e["event"] == "recovered" for e in mp.summary()["worker_events_all"]), "recovery logged")
                s = mp.summary()
                self.assertEqual([e["event"] for e in s["worker_events"]], ["behind"])         # recoveries are not events to count
                self.assertTrue(s["frame_pan_tilt"]["alive"])
            finally:
                if gate.exists():
                    gate.unlink()
                mp.close()

    def test_a_worker_that_cannot_start_stops_the_start_with_its_traceback(self):
        mp = mpv.ProcessPerceptionV4(specs(gesture=False, fail_start=True), None, verbose=False)
        with self.assertRaises(RuntimeError) as cm_:
            mp.wait_started()
        self.assertIn("cannot load the fake model", str(cm_.exception))
        self.assertIn("people", str(cm_.exception))

    def test_start_timeout_when_a_worker_never_reports(self):
        mp = mpv.ProcessPerceptionV4(specs(gesture=False), None, {"ready_timeout_s": 0.0}, verbose=False)
        try:
            with self.assertRaises(RuntimeError) as cm_:
                mp.wait_started(timeout_s=0.0)
            self.assertIn("not ready", str(cm_.exception))
        finally:
            mp.close()

    def test_close_stops_every_process_and_can_be_called_twice(self):
        mp = mpv.ProcessPerceptionV4(specs(), None, verbose=False)
        mp.wait_started()
        procs = [link.proc for link in mp.links.values()]
        self.assertTrue(all(p.is_alive() for p in procs))
        mp.close()
        self.assertFalse(any(p.is_alive() for p in procs))
        mp.close()
        self.assertEqual(mp.summary()["worker_events"], [])           # a normal stop is not a death


class FileWritesNeverHoldTheResultsLockTests(unittest.TestCase):
    def test_a_blocked_file_write_does_not_delay_the_results_the_loop_reads(self):
        """The csv write has its own lock: while it is held (a slow disk, an antivirus scan) the newest result is already visible."""
        with tempfile.TemporaryDirectory() as t:
            mp = mpv.ProcessPerceptionV4(specs(gesture=False), Path(t), verbose=False)
            try:
                mp.wait_started()
                mp._io_lock.acquire()
                try:
                    mp.submit(frame("frame_360", 0))
                    wait_for(lambda: mp.snapshot()["people_time_s"] == 0.0, "the result visible while the file write is blocked")
                    self.assertEqual(mp.processed["frame_360"], 0)       # the counter that announces it waits for the write
                finally:
                    mp._io_lock.release()
                wait_for(lambda: mp.processed["frame_360"] == 1, "the write done")
            finally:
                mp.close()

    def test_loop_facing_reads_take_no_file_lock(self):
        import inspect
        for fn in (mpv.ProcessPerceptionV4.snapshot, mpv.ProcessPerceptionV4.snapshot_v4, mpv.ProcessPerceptionV4.submit):
            self.assertNotIn("_io_lock", inspect.getsource(fn))


class StructureTests(unittest.TestCase):
    def test_the_asyncio_facing_methods_do_no_io_and_take_no_slow_lock(self):
        """submit() touches only the mailbox lock (assignments); snapshot() only the results lock. Neither opens a pipe."""
        import inspect
        src_submit = inspect.getsource(mpv._Link.submit) + inspect.getsource(mpv.ProcessPerceptionV4.submit)
        src_snap = inspect.getsource(mpv.ProcessPerceptionV4.snapshot) + inspect.getsource(mpv.ProcessPerceptionV4.snapshot_v4)
        for src in (src_submit, src_snap):
            for forbidden in (".send(", ".recv(", ".join(", "sleep(", ".wait("):
                self.assertNotIn(forbidden, src)
        # the only place a pipe is written is the sender thread (and the stop message)
        self.assertEqual(inspect.getsource(mpv._Link).count("self._tx.send("), 2)

    def test_the_start_method_is_spawn_by_default(self):
        self.assertEqual(mpv.DEFAULTS["start_method"], "spawn")

    def test_child_module_level_entry_points_are_importable_by_name(self):
        for dotted in ("bridge.perception_mp_v4:real_people", "bridge.perception_mp_v4:real_gesture"):
            self.assertTrue(callable(mpv._resolve(dotted)))
        self.assertTrue(callable(mpv.child_main))

    def test_real_perception_classes_borrow_the_v3_v4_functions_unchanged(self):
        import hri_perception as hpm
        import hri_perception_v4 as hv4
        self.assertIs(mpv.PeoplePerception.people, hv4.HriPerceptionV4.people)     # 2026-11-12 (P1): the v4 people() with the ankle height
        self.assertIs(hv4.HriPerceptionV4.people, hv4.people_v4)
        self.assertIsNot(hv4.people_v4, hpm.HriPerception.people)
        src = Path(mpv.__file__).read_text(encoding="utf-8")
        self.assertIn("hv4.HriPerceptionV4.persons(self", src)
        self.assertNotIn("def persons", src)


if __name__ == "__main__":
    unittest.main()
