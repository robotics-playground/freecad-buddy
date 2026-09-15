"""The service health surface: pool occupancy and per-process RSS, sampled at job boundaries.

G4.5 grades memory growth over a 50-job soak, and the design is explicit that the numbers come
from sampling this surface at job boundaries rather than from parsing logs afterwards. The
difference matters: a post-hoc parse can only see what something chose to print, and "the leak was
hidden by restart luck" is precisely the threat the soak exists to catch.

Stdlib only. ``psutil`` is not a dependency of this project, and adding one for a number the OS
already exposes would put a third-party package in the supervisor — the one process whose flat
memory is the measurement's whole foundation.

FreeCAD-free: reading a process's working set needs no geometry.
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass, field


@dataclass
class HealthSample:
    """One observation of the service, taken at a job boundary."""

    job_index: int
    supervisor_rss_bytes: int
    worker_rss_bytes: int
    jobs_completed: int
    queue_depth: int
    session_id: str = ""

    def as_dict(self) -> dict:
        return {
            "job_index": self.job_index,
            "supervisor_rss_bytes": self.supervisor_rss_bytes,
            "worker_rss_bytes": self.worker_rss_bytes,
            "jobs_completed": self.jobs_completed,
            "queue_depth": self.queue_depth,
            "session_id": self.session_id,
        }


@dataclass
class SoakReport:
    """What a soak run measured. Growth is computed, never asserted."""

    samples: list = field(default_factory=list)
    crashes: int = 0
    hangs: int = 0
    silent_failures: int = 0

    @property
    def supervisor_growth(self) -> float:
        """Fractional RSS growth of the supervisor from first sample to last.

        The supervisor never imports FreeCAD, so its RSS is flat by construction. A growing
        supervisor means the leak is in the part of the system that was supposed to be immune,
        which is a more serious finding than a leaking worker — the worker is replaced every job.
        """
        return _growth([s.supervisor_rss_bytes for s in self.samples])

    @property
    def worker_growth(self) -> float:
        """Fractional RSS growth across worker samples.

        With one task per child every worker is a fresh process, so this measures whether a NEW
        worker starts heavier than an early one — the signature of something accumulating outside
        the process, in a cache or a file the next worker inherits.
        """
        return _growth([s.worker_rss_bytes for s in self.samples if s.worker_rss_bytes > 0])

    def as_dict(self) -> dict:
        return {
            "schema": "fcb.g4-soak/1",
            "jobs": len(self.samples),
            "crashes": self.crashes,
            "hangs": self.hangs,
            "silent_failures": self.silent_failures,
            "supervisor_growth": round(self.supervisor_growth, 4),
            "worker_growth": round(self.worker_growth, 4),
            "samples": [s.as_dict() for s in self.samples],
        }


def _growth(values: list) -> float:
    """Fractional growth from the first value to the largest later one.

    The MAXIMUM rather than the final value on purpose: a leak that is reclaimed right before the
    run ends still happened, and comparing only the endpoints would report it as zero.
    """
    if len(values) < 2 or not values[0]:
        return 0.0
    first = float(values[0])
    peak = float(max(values[1:]))
    return max(0.0, (peak - first) / first)


def rss_bytes(pid: int | None = None) -> int:
    """The resident working set of ``pid`` in bytes; ``0`` when it cannot be read.

    Returns 0 rather than raising: a soak that aborted because one sample failed would lose the
    run that was being measured, and a missing sample is visible in the report as a zero.
    """
    target = os.getpid() if pid is None else pid
    if sys.platform == "win32":
        return _rss_windows(target)
    return _rss_posix(target)


def _rss_posix(pid: int) -> int:
    """Read RSS from ``/proc/<pid>/statm``, whose second field is resident pages."""
    try:
        with open(f"/proc/{pid}/statm", encoding="utf-8") as handle:
            fields = handle.read().split()
        return int(fields[1]) * os.sysconf("SC_PAGE_SIZE")
    except (OSError, IndexError, ValueError):
        return 0


def _rss_windows(pid: int) -> int:
    """Read the working set through ``GetProcessMemoryInfo``.

    ``WorkingSetSize`` is the Windows analogue of RSS: the physical memory the process currently
    occupies. ``psutil`` reports the same field; this reaches it directly so the supervisor keeps
    no third-party dependency.
    """
    import ctypes
    from ctypes import wintypes

    class _ProcessMemoryCounters(ctypes.Structure):
        _fields_ = [
            ("cb", wintypes.DWORD),
            ("PageFaultCount", wintypes.DWORD),
            ("PeakWorkingSetSize", ctypes.c_size_t),
            ("WorkingSetSize", ctypes.c_size_t),
            ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
            ("QuotaPagedPoolUsage", ctypes.c_size_t),
            ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
            ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
            ("PagefileUsage", ctypes.c_size_t),
            ("PeakPagefileUsage", ctypes.c_size_t),
        ]

    kernel32 = ctypes.windll.kernel32
    kernel32.OpenProcess.restype = wintypes.HANDLE
    # PROCESS_QUERY_LIMITED_INFORMATION | PROCESS_VM_READ
    handle = kernel32.OpenProcess(0x1000 | 0x0010, False, pid)
    if not handle:
        return 0
    counters = _ProcessMemoryCounters()
    counters.cb = ctypes.sizeof(_ProcessMemoryCounters)
    ok = ctypes.windll.psapi.GetProcessMemoryInfo(
        wintypes.HANDLE(handle), ctypes.byref(counters), ctypes.sizeof(counters)
    )
    kernel32.CloseHandle(wintypes.HANDLE(handle))
    return int(counters.WorkingSetSize) if ok else 0


def sample(
    pool, job_index: int, worker_pid: int | None = None, session_id: str = ""
) -> HealthSample:
    """Take one boundary sample from ``pool``.

    Called between jobs rather than during one, so the worker's RSS is read while it still exists
    but is no longer growing — which is what makes successive samples comparable.
    """
    return HealthSample(
        job_index=job_index,
        supervisor_rss_bytes=rss_bytes(),
        worker_rss_bytes=rss_bytes(worker_pid) if worker_pid else 0,
        jobs_completed=pool.stats.jobs_finished,
        queue_depth=pool.stats.queue_depth,
        session_id=session_id,
    )
