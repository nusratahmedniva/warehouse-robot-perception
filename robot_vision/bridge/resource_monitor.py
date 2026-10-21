"""Resource log for a trial session (2026-10-22, AUDIT.md section 9 measurement correction).

Runs in its own process (started by bridge.server --resource-log), so sampling never holds the server's GIL. Once per
second it appends one row to resources.csv:
- machine: CPU (% of all logical CPUs), memory available / used, page file or swap used, hard paging
  (Windows: Memory\\Pages Input/sec, page reads from disk; macOS: swap-in bytes per second);
- per process (the bridge server, Unity, this monitor): CPU in % of ONE logical CPU (can exceed 100), resident memory,
  private memory (Windows), page faults per second (soft + hard);
- the 3 other processes using most CPU (% of one logical CPU). Windows: one PDH wildcard query per second (instance
  names, no PIDs); elsewhere psutil every 5 s. psutil's per-process CPU of processes the user cannot open costs about
  3 ms each on Windows (0.8 s per second for 290 processes), so psutil is used only for the server, Unity and itself;
- GPU (nvidia-smi, when present): utilisation, memory-controller utilisation, memory used / total, performance state,
  temperature. Per-process GPU memory is not available for Unity (graphics, not compute), so it is not logged.
It stops when the server process (--parent-pid) exits. A value that cannot be read is left empty.

    python -m bridge.resource_monitor --out outputs/x/resources.csv --parent-pid 1234
"""

from __future__ import annotations

import argparse
import csv
import os
import platform
import shutil
import statistics
import subprocess
import sys
import time
from pathlib import Path

COLUMNS = ["t_unix_s", "cpu_total_pct", "mem_total_mb", "mem_available_mb", "mem_used_pct", "swap_used_mb", "swap_used_pct",
           "hard_paging_per_s", "hard_paging_unit",
           "server_pid", "server_cpu_pct", "server_rss_mb", "server_private_mb", "server_page_faults_per_s",
           "unity_pid", "unity_cpu_pct", "unity_rss_mb", "unity_private_mb", "unity_page_faults_per_s",
           "monitor_cpu_pct", "top_other_cpu",
           "gpu_util_pct", "gpu_mem_util_pct", "gpu_mem_used_mb", "gpu_mem_total_mb", "gpu_pstate", "gpu_temp_c"]
UNITY_NAMES = {"unity.exe", "unity"}
MB = 1024.0 * 1024.0


class WindowsCounters:
    """PDH counters (Windows): hard page reads/s, page file usage, CPU of every process (one wildcard query)."""

    PDH_FMT_DOUBLE, PDH_FMT_NOCAP100 = 0x200, 0x8000

    def __init__(self):
        import ctypes
        from ctypes import wintypes
        self.ct, self.wt = ctypes, wintypes
        self.pdh = ctypes.WinDLL("pdh")

        class Value(ctypes.Structure):
            _fields_ = [("CStatus", wintypes.DWORD), ("doubleValue", ctypes.c_double)]

        class Item(ctypes.Structure):
            _fields_ = [("szName", wintypes.LPWSTR), ("FmtValue", Value)]

        self.Value, self.Item = Value, Item
        self.q = wintypes.HANDLE()
        if self.pdh.PdhOpenQueryW(None, 0, ctypes.byref(self.q)) != 0:
            raise OSError("PdhOpenQueryW failed")
        self.c = {}
        for key, path in (("paging", "\\Memory\\Pages Input/sec"), ("pagefile", "\\Paging File(_Total)\\% Usage"),
                          ("procs", "\\Process(*)\\% Processor Time")):
            h = wintypes.HANDLE()
            if self.pdh.PdhAddEnglishCounterW(self.q, path, 0, ctypes.byref(h)) == 0:
                self.c[key] = h
        self.pdh.PdhCollectQueryData(self.q)

    def collect(self) -> None:
        self.pdh.PdhCollectQueryData(self.q)

    def value(self, key: str):
        if key not in self.c:
            return None
        v = self.Value()
        ok = self.pdh.PdhGetFormattedCounterValue(self.c[key], self.PDH_FMT_DOUBLE, None, self.ct.byref(v)) == 0
        return round(v.doubleValue, 1) if ok else None

    def top_processes(self, skip_names: set[str], n: int = 3) -> str:
        if "procs" not in self.c:
            return ""
        size, count = self.wt.DWORD(0), self.wt.DWORD(0)
        fmt = self.PDH_FMT_DOUBLE | self.PDH_FMT_NOCAP100
        self.pdh.PdhGetFormattedCounterArrayW(self.c["procs"], fmt, self.ct.byref(size), self.ct.byref(count), None)
        if not size.value:
            return ""
        buf = (self.ct.c_byte * size.value)()
        if self.pdh.PdhGetFormattedCounterArrayW(self.c["procs"], fmt, self.ct.byref(size), self.ct.byref(count), buf) != 0:
            return ""
        items = self.ct.cast(buf, self.ct.POINTER(self.Item * count.value)).contents
        top = sorted(((i.FmtValue.doubleValue, i.szName) for i in items
                      if i.szName not in ("_Total", "Idle") and i.szName.split("#")[0].lower() not in skip_names),
                     reverse=True)
        return ";".join(f"{name}:{cpu:.0f}" for cpu, name in top[:n])


def gpu() -> dict:
    exe = shutil.which("nvidia-smi")
    if not exe:
        return {}
    try:
        out = subprocess.run([exe, "--query-gpu=utilization.gpu,utilization.memory,memory.used,memory.total,pstate,"
                              "temperature.gpu", "--format=csv,noheader,nounits"],
                             capture_output=True, text=True, timeout=2, check=False).stdout
        f = [x.strip() for x in out.splitlines()[0].split(",")]
        return dict(zip(["gpu_util_pct", "gpu_mem_util_pct", "gpu_mem_used_mb", "gpu_mem_total_mb", "gpu_pstate",
                         "gpu_temp_c"], f))
    except (OSError, subprocess.SubprocessError, IndexError):
        return {}


class ProcSample:
    """CPU and page-fault rates of one process between two samples."""

    def __init__(self, proc):
        self.proc = proc
        self.faults = None
        proc.cpu_percent(None)

    def sample(self, prefix: str, dt: float) -> dict:
        p = self.proc
        with p.oneshot():
            cpu = p.cpu_percent(None)
            mi = p.memory_info()
        faults = getattr(mi, "num_page_faults", None) or getattr(mi, "pfaults", None)
        rate = None if faults is None or self.faults is None or dt <= 0 else round((faults - self.faults) / dt, 1)
        self.faults = faults
        return {f"{prefix}_pid": p.pid, f"{prefix}_cpu_pct": round(cpu, 1), f"{prefix}_rss_mb": round(mi.rss / MB, 1),
                f"{prefix}_private_mb": round(mi.private / MB, 1) if hasattr(mi, "private") else None,
                f"{prefix}_page_faults_per_s": rate}


def find_unity(psutil):
    """The Unity editor process (largest resident memory among processes named Unity / Unity.exe), or None."""
    best, best_rss = None, -1
    for p in psutil.process_iter(["name"]):
        if (p.info["name"] or "").lower() not in UNITY_NAMES:
            continue
        try:
            rss = p.memory_info().rss
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
        if rss > best_rss:
            best, best_rss = p, rss
    return best


def top_other_psutil(psutil, others: dict, skip: set[int], n: int = 3) -> str:
    """Other processes using most CPU since the previous call (psutil; macOS / Linux)."""
    top, alive = [], set()
    for p in psutil.process_iter(["name"]):
        alive.add(p.pid)
        if p.pid in skip:
            continue
        try:
            if p.pid not in others:
                p.cpu_percent(None)
                others[p.pid] = p
                continue
            top.append((others[p.pid].cpu_percent(None), p.info["name"], p.pid))
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    for pid in set(others) - alive:
        del others[pid]
    top.sort(reverse=True)
    return ";".join(f"{name}:{pid}:{cpu:.0f}" for cpu, name, pid in top[:n])


def run(out: Path, parent_pid: int | None, interval_s: float = 1.0, samples: int | None = None) -> int:
    import psutil
    parent = psutil.Process(parent_pid) if parent_pid else None
    me = ProcSample(psutil.Process())
    server = ProcSample(parent) if parent else None
    unity, unity_checked = None, -1e9
    others: dict[int, object] = {}
    win = None
    if platform.system() == "Windows":
        try:
            win = WindowsCounters()
        except (OSError, AttributeError):
            win = None
    swap_in_last, top_other, top_checked = None, "", -1e9
    psutil.cpu_percent(None)
    new = not out.exists()
    n = 0
    with out.open("a", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNS)
        if new:
            w.writeheader()
        last = time.monotonic()
        next_t = last + interval_s
        while samples is None or n < samples:
            time.sleep(max(0.0, next_t - time.monotonic()))
            next_t = max(next_t + interval_s, time.monotonic())
            if parent is not None and not parent.is_running():
                break
            now = time.monotonic()
            dt, last = now - last, now
            if unity is None and now - unity_checked > 5.0:
                unity_checked = now
                u = find_unity(psutil)
                unity = ProcSample(u) if u else None
            vm = psutil.virtual_memory()
            row = {"t_unix_s": round(time.time(), 3), "cpu_total_pct": psutil.cpu_percent(None),
                   "mem_total_mb": round(vm.total / MB), "mem_available_mb": round(vm.available / MB),
                   "mem_used_pct": vm.percent}
            if win is not None:                     # psutil.swap_memory() costs about 70 ms on Windows
                win.collect()
                row.update(swap_used_pct=win.value("pagefile"), hard_paging_per_s=win.value("paging"),
                           hard_paging_unit="pages_input_per_s")
            else:
                sw = psutil.swap_memory()
                rate = None if swap_in_last is None or dt <= 0 else round((sw.sin - swap_in_last) / dt, 1)
                swap_in_last = sw.sin
                row.update(swap_used_mb=round(sw.used / MB), swap_used_pct=sw.percent, hard_paging_per_s=rate,
                           hard_paging_unit="swap_in_bytes_per_s")
            skip = {os.getpid(), 0}
            for prefix, ps in (("server", server), ("unity", unity)):
                if ps is None:
                    continue
                try:
                    row.update(ps.sample(prefix, dt))
                    skip.add(ps.proc.pid)
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    if prefix == "unity":
                        unity = None
            row["monitor_cpu_pct"] = me.sample("monitor", dt)["monitor_cpu_pct"]
            if win is not None:
                row["top_other_cpu"] = win.top_processes({"unity", "python"})   # server and Unity are logged above
            else:
                if now - top_checked >= 5.0:
                    top_checked = now
                    top_other = top_other_psutil(psutil, others, skip)
                row["top_other_cpu"] = top_other
            row.update(gpu())
            w.writerow(row)
            f.flush()
            n += 1
    return n


def start(out: Path):
    """Start the monitor in its own process for this (server) process; returns the Popen."""
    root = Path(__file__).resolve().parents[1]
    log = open(out.with_suffix(".log"), "w", encoding="utf-8")   # noqa: SIM115 (inherited by the child)
    try:
        return subprocess.Popen([sys.executable, "-m", "bridge.resource_monitor", "--out", str(out), "--parent-pid",
                                 str(os.getpid())], cwd=str(root), stdout=log, stderr=subprocess.STDOUT)
    finally:
        log.close()


def stop(proc, timeout_s: float = 5.0) -> None:
    proc.terminate()
    try:
        proc.wait(timeout_s)
    except subprocess.TimeoutExpired:
        proc.kill()


def summarise(path: Path) -> dict | None:
    """Min, max and mean of each numeric column of resources.csv (None without rows)."""
    if not path.exists():
        return None
    with path.open(encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    if not rows:
        return None
    out = {"samples": len(rows), "file": path.name}
    for c in COLUMNS:
        if c in ("t_unix_s", "server_pid", "unity_pid", "hard_paging_unit", "top_other_cpu", "gpu_pstate"):
            continue
        v = []
        for r in rows:
            try:
                v.append(float(r.get(c) or "nan"))
            except ValueError:
                continue
        v = [x for x in v if x == x]
        if v:
            out[c] = {"min": round(min(v), 1), "max": round(max(v), 1), "mean": round(statistics.fmean(v), 1)}
    out["hard_paging_unit"] = rows[-1].get("hard_paging_unit", "")
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", required=True)
    ap.add_argument("--parent-pid", type=int, default=None, help="stop when this process exits")
    ap.add_argument("--interval-s", type=float, default=1.0)
    ap.add_argument("--samples", type=int, default=None, help="stop after this many rows (tests)")
    a = ap.parse_args(argv)
    run(Path(a.out), a.parent_pid, a.interval_s, a.samples)
    return 0


if __name__ == "__main__":
    sys.exit(main())
