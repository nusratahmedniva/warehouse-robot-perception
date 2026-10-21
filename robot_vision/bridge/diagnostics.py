"""Bridge server diagnostics (infrastructure, 2026-10-21; AUDIT.md section 9): what stalls the reply loop.

- LoopLagMonitor: an asyncio task that sleeps interval_s and logs every wake-up later than threshold_ms (the loop
  could not run: something held it or the GIL). Before each sleep it arms faulthandler.dump_traceback_later, which
  runs on a C thread without the GIL, so a stall longer than dump_after_s writes the Python stacks of every thread
  (what was running while the loop could not) to stall_tracebacks.txt. t0 should be the run log's clock origin so
  that loop_lag.csv and messages.jsonl share t_wall_s.
- GcMonitor: times every garbage collection (gc.callbacks); collections run on whichever thread allocates and hold
  the GIL, so a long one stalls the loop too.
- thread_info(): thread counts of torch (intra-op, inter-op), OpenCV and the whole process (psutil), the device.

Nothing here changes a decision or a command; it only writes loop_lag.csv, gc_pauses.csv and the summary block.
"""

from __future__ import annotations

import asyncio
import csv
import faulthandler
import gc
import threading
import time
from pathlib import Path


class LoopLagMonitor:
    def __init__(self, out_dir: Path | None, interval_s: float = 0.01, threshold_ms: float = 50.0,
                 dump_after_s: float = 0.25, clock=time.monotonic, t0: float | None = None):
        self.interval_s = interval_s
        self.threshold_ms = threshold_ms
        self.dump_after_s = dump_after_s
        self.clock = clock
        self.t0 = clock() if t0 is None else t0
        self.ticks = 0
        self.events: list[tuple[float, float]] = []   # (t_wall_s at wake-up, lag ms)
        self.max_lag_ms = 0.0
        self._task: asyncio.Task | None = None
        self._csv = self._dump = None
        if out_dir is not None:
            self._csv_file = (Path(out_dir) / "loop_lag.csv").open("x", newline="", encoding="utf-8", buffering=1)
            self._csv = csv.writer(self._csv_file)
            self._csv.writerow(["t_wall_s", "lag_ms", "threads"])
            self._dump = (Path(out_dir) / "stall_tracebacks.txt").open("x", encoding="utf-8")

    def start(self) -> None:
        self._task = asyncio.get_running_loop().create_task(self._run(), name="loop-lag-monitor")

    async def _run(self) -> None:
        while True:
            if self._dump is not None:
                faulthandler.dump_traceback_later(self.dump_after_s, repeat=False, file=self._dump)
            t = self.clock()
            await asyncio.sleep(self.interval_s)
            lag_ms = (self.clock() - t - self.interval_s) * 1000.0
            self.ticks += 1
            self.max_lag_ms = max(self.max_lag_ms, lag_ms)
            if lag_ms > self.threshold_ms:
                now = round(self.clock() - self.t0, 4)
                self.events.append((now, round(lag_ms, 2)))
                if self._csv is not None:
                    self._csv.writerow([now, round(lag_ms, 2), threading.active_count()])
                if self._dump is not None and lag_ms > self.dump_after_s * 1000.0:
                    self._dump.write(f"--- the stall dumped above ended at t_wall_s {now} (loop lag {lag_ms:.1f} ms)\n\n")
                    self._dump.flush()

    async def stop(self) -> None:
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        if self._dump is not None:
            faulthandler.cancel_dump_traceback_later()
            self._dump.close()
            self._csv_file.close()

    def summary(self) -> dict:
        lags = sorted(lag for _, lag in self.events)
        return {"interval_ms": self.interval_s * 1000.0, "threshold_ms": self.threshold_ms, "ticks": self.ticks,
                "over_threshold": len(self.events), "max_lag_ms": round(self.max_lag_ms, 2),
                "over_250ms": sum(1 for x in lags if x > 250.0),
                "worst": sorted(self.events, key=lambda e: -e[1])[:10],
                "note": "event-loop lag = how late a 10 ms sleep woke up; a lag > 250 ms writes the stacks of all "
                        "threads to stall_tracebacks.txt (faulthandler, no GIL needed)"}


class GcMonitor:
    def __init__(self, out_dir: Path | None, log_over_ms: float = 10.0, clock=time.perf_counter):
        self.clock = clock
        self.log_over_ms = log_over_ms
        self.count = {0: 0, 1: 0, 2: 0}
        self.total_ms = 0.0
        self.max_ms = 0.0
        self.long: list[tuple[float, int, float, str]] = []
        self._start: dict[int, float] = {}
        self._t0 = time.monotonic()
        self._csv = None
        if out_dir is not None:
            self._csv_file = (Path(out_dir) / "gc_pauses.csv").open("x", newline="", encoding="utf-8", buffering=1)
            self._csv = csv.writer(self._csv_file)
            self._csv.writerow(["t_wall_s", "generation", "ms", "thread", "collected"])
        gc.callbacks.append(self._callback)

    def _callback(self, phase: str, info: dict) -> None:
        tid = threading.get_ident()
        if phase == "start":
            self._start[tid] = self.clock()
            return
        t = self._start.pop(tid, None)
        if t is None:
            return
        ms = (self.clock() - t) * 1000.0
        gen = int(info.get("generation", -1))
        self.count[gen] = self.count.get(gen, 0) + 1
        self.total_ms += ms
        self.max_ms = max(self.max_ms, ms)
        if ms > self.log_over_ms:
            name = threading.current_thread().name
            row = (round(time.monotonic() - self._t0, 4), gen, round(ms, 2), name)
            self.long.append(row)
            if self._csv is not None:
                self._csv.writerow([*row, info.get("collected")])

    def close(self) -> None:
        if self._callback in gc.callbacks:
            gc.callbacks.remove(self._callback)
        if self._csv is not None:
            self._csv_file.close()

    def summary(self) -> dict:
        return {"collections": {f"gen{k}": v for k, v in sorted(self.count.items())}, "total_ms": round(self.total_ms, 1),
                "max_ms": round(self.max_ms, 2), f"over_{self.log_over_ms:g}ms": len(self.long),
                "worst": sorted(self.long, key=lambda r: -r[2])[:10]}


def freeze_heap() -> dict:
    """Collect once, then move every object alive now (the loaded models, MediaPipe, the warm-up state: about 400 000
    tracked objects) into the permanent generation (gc.freeze), so later full collections scan only objects created
    afterwards. Measured on the PC (2026-10-21): a full collection took 230 ms with the models loaded and held the GIL,
    stalling the reply loop (one 224 ms loop stall in a 180 s replay was exactly a 232 ms generation-2 collection on
    the perception thread); after freezing it takes under 1 ms. Changes no computation: frozen objects are the
    long-lived ones, still freed by reference counting. Call after the models are warmed up, before listening."""
    t = time.perf_counter()
    gc.collect()
    collect_ms = (time.perf_counter() - t) * 1000.0
    gc.freeze()
    t = time.perf_counter()
    gc.collect()
    after_ms = (time.perf_counter() - t) * 1000.0
    return {"frozen_objects": gc.get_freeze_count(), "full_collect_ms_before": round(collect_ms, 2),
            "full_collect_ms_after": round(after_ms, 2)}


def thread_info() -> dict:
    """Thread counts of the libraries that start their own pools (recorded at start-up and at close)."""
    out: dict = {"python_threads": threading.active_count(),
                 "python_thread_names": sorted(t.name for t in threading.enumerate())}
    try:
        import psutil
        out["process_threads"] = psutil.Process().num_threads()
        out["cpu_count_logical"] = psutil.cpu_count(logical=True)
    except Exception as e:  # noqa: BLE001 - diagnostics only
        out["process_threads"] = f"unavailable: {e!r}"
    try:
        import torch
        out["torch_intra_op_threads"] = torch.get_num_threads()
        out["torch_inter_op_threads"] = torch.get_num_interop_threads()
        out["torch_cuda"] = torch.cuda.is_available()
    except Exception as e:  # noqa: BLE001
        out["torch"] = f"unavailable: {e!r}"
    try:
        import cv2
        out["opencv_threads"] = cv2.getNumThreads()
    except Exception as e:  # noqa: BLE001
        out["opencv"] = f"unavailable: {e!r}"
    out["mediapipe_note"] = "MediaPipe exposes no thread setting; its threads are in process_threads"
    return out
