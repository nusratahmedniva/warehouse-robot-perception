"""v4 timing instruments and the analysis behind timing_check_v4.py (AUDIT.md section 14.14).

Why: Unity stops the robot when Python is silent for watchdog_timeout_s (0.3 s). Heavy Python work in the server process
(MediaPipe, the tracker, garbage collection) can hold the GIL and stall the asyncio loop that answers telemetry. These
helpers measure that, in the same way before and after the worker-process change:

- LoopLagMonitorV4: bridge/diagnostics.LoopLagMonitor (unchanged, still used by protocol 2) plus every lag sample, so the
  report can give p99 and max, not only the lags over the 50 ms threshold. Used by the server only for protocol 3.
- reply_stats / handle_stats / lag_stats: pure functions over numbers (no clock, no models): unit-tested on synthetic data.
- evaluate: compares the measured numbers with the limits declared in configs/v4/bridge.json ("timing_limits").

Nothing here changes a decision or a command.
"""

from __future__ import annotations

import asyncio
import csv
import faulthandler
import json
import math
import threading
import time
from pathlib import Path

from bridge import diagnostics as diag

# the metrics the limits can name (configs/v4/bridge.json -> timing_limits), all "measured value <= limit"
METRICS = ("loop_lag_p99_ms", "loop_lag_max_ms", "reply_gap_max_ms", "round_trip_p99_ms", "round_trip_max_ms",
           "unanswered_telemetry", "perception_worker_events")


def pct(values: list[float], q: float) -> float | None:
    """Nearest-rank percentile (q in 0..100) of an unsorted list; None for an empty list."""
    if not values:
        return None
    v = sorted(values)
    return v[min(len(v) - 1, max(0, math.ceil(q / 100.0 * len(v)) - 1))]


def _r(x, n=3):
    return None if x is None else round(float(x), n)


def lag_stats(samples_ms: list[float]) -> dict:
    """Event-loop lag samples (ms): how late each 10 ms sleep woke up."""
    s = sorted(samples_ms)
    if not s:
        return {"n": 0}
    return {"n": len(s), "mean_ms": _r(sum(s) / len(s)), "p50_ms": _r(pct(s, 50)), "p99_ms": _r(pct(s, 99)),
            "p999_ms": _r(pct(s, 99.9)), "max_ms": _r(s[-1]), "over_50ms": sum(1 for x in s if x > 50.0),
            "over_100ms": sum(1 for x in s if x > 100.0), "over_250ms": sum(1 for x in s if x > 250.0)}


def reply_stats(rows: list[tuple], unanswered: int = 0) -> dict:
    """Telemetry -> command as the client (Unity's stand-in) sees it. rows: (telemetry_seq, sent_s, reply_s, round_trip_ms).
    round trip = telemetry written -> its command read; gap = time between two consecutive commands (the silence Unity's
    watchdog sees: it stops when a command is missing for telemetry sent more than watchdog_timeout_s ago)."""
    rtt = [float(r[3]) for r in rows]
    t = sorted(float(r[2]) for r in rows)
    gaps = [(b - a) * 1000.0 for a, b in zip(t, t[1:])]
    out = {"n": len(rows), "unanswered": int(unanswered)}
    if rtt:
        out["round_trip_ms"] = {"mean": _r(sum(rtt) / len(rtt)), "p50": _r(pct(rtt, 50)), "p99": _r(pct(rtt, 99)),
                                "p999": _r(pct(rtt, 99.9)), "max": _r(max(rtt)), "over_100ms": sum(1 for x in rtt if x > 100.0),
                                "over_300ms": sum(1 for x in rtt if x > 300.0)}
    if gaps:
        out["reply_gap_ms"] = {"mean": _r(sum(gaps) / len(gaps)), "p50": _r(pct(gaps, 50)), "p99": _r(pct(gaps, 99)),
                               "max": _r(max(gaps)), "over_150ms": sum(1 for x in gaps if x > 150.0),
                               "over_300ms": sum(1 for x in gaps if x > 300.0)}
    return out


def handle_stats(messages_jsonl: Path) -> dict:
    """Server-side cost of answering: handle_ms of every incoming telemetry message in messages.jsonl (validate -> command
    computed, on the event loop). A stall before the message was read does not show here (see the loop lag)."""
    vals = []
    with Path(messages_jsonl).open(encoding="utf-8") as f:
        for line in f:
            try:
                d = json.loads(line)
            except ValueError:
                continue
            if d.get("dir") == "in" and d.get("type") == "telemetry" and "handle_ms" in d:
                vals.append(float(d["handle_ms"]))
    if not vals:
        return {"n": 0}
    return {"n": len(vals), "mean_ms": _r(sum(vals) / len(vals)), "p99_ms": _r(pct(vals, 99)), "max_ms": _r(max(vals))}


def read_replies(path: Path) -> list[tuple]:
    rows = []
    with Path(path).open(newline="", encoding="utf-8") as f:
        r = csv.reader(f)
        next(r, None)
        for row in r:
            rows.append((int(row[0]), float(row[1]), float(row[2]), float(row[3])))
    return rows


def evaluate(limits: dict | None, measured: dict) -> dict:
    """measured: metric -> value (None = not measured). limits: metric -> maximum allowed (configs/v4/bridge.json). A metric
    with a limit that was not measured fails (unknown is not a pass)."""
    if not limits:
        return {"declared": False, "checks": [], "passed": None,
                "note": "no timing_limits declared in the bridge config: numbers only"}
    checks = []
    for name in METRICS:
        if name not in limits:
            continue
        v = measured.get(name)
        checks.append({"metric": name, "value": _r(v) if v is not None else None, "limit": limits[name],
                       "ok": v is not None and v <= limits[name]})
    unknown = [k for k, v in limits.items() if isinstance(v, (int, float)) and not isinstance(v, bool) and k not in METRICS]
    return {"declared": True, "checks": checks, "passed": all(c["ok"] for c in checks) and not unknown,
            "unknown_limit_names": unknown}


class LoopLagMonitorV4(diag.LoopLagMonitor):
    """LoopLagMonitor that also keeps every lag sample (10 ms sleeps: 100 per second, 8 bytes each)."""

    def __init__(self, out_dir: Path | None, interval_s: float = 0.01, threshold_ms: float = 50.0, dump_after_s: float = 0.25,
                 clock=time.monotonic, t0: float | None = None):
        super().__init__(out_dir, interval_s, threshold_ms, dump_after_s, clock, t0)
        self.samples: list[float] = []

    async def _run(self) -> None:
        while True:
            if self._dump is not None:
                faulthandler.dump_traceback_later(self.dump_after_s, repeat=False, file=self._dump)
            t = self.clock()
            await asyncio.sleep(self.interval_s)
            lag_ms = (self.clock() - t - self.interval_s) * 1000.0
            self.ticks += 1
            self.samples.append(lag_ms)
            self.max_lag_ms = max(self.max_lag_ms, lag_ms)
            if lag_ms > self.threshold_ms:
                now = round(self.clock() - self.t0, 4)
                self.events.append((now, round(lag_ms, 2)))
                if self._csv is not None:
                    self._csv.writerow([now, round(lag_ms, 2), threading.active_count()])
                if self._dump is not None and lag_ms > self.dump_after_s * 1000.0:
                    self._dump.write(f"--- the stall dumped above ended at t_wall_s {now} (loop lag {lag_ms:.1f} ms)\n\n")
                    self._dump.flush()

    def summary(self) -> dict:
        out = super().summary()
        out["all_samples"] = lag_stats(self.samples)
        out["stall_dump_after_s"] = self.dump_after_s
        out["note"] += ("; all_samples covers every 10 ms sleep (protocol 3 only), the stack dump is written when a stall "
                        "exceeds stall_dump_after_s")
        return out
