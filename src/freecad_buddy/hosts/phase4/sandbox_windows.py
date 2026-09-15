"""Windows sandbox backend: the Job Object's resource limits, and an honest gap where there is one.

A Job Object gives real, kernel-enforced memory and CPU ceilings on top of the atomic tree kill
story 5.2 already uses. It gives no network isolation and no filesystem confinement. The design's
answer to that is WSL2 running the identical Linux stack, which is a deployment decision rather
than something this backend can assert on an arbitrary Windows host.

So this backend reports what it enforces and names what it does not. Claiming egress denial it
cannot deliver would be exactly the silent gap the sandbox report exists to prevent — and the
consequence would be an operator running untrusted job specs on Windows believing the worker
cannot reach the network.

The limits are applied to the job handle rather than by rewriting the command, so ``wrap``
returns the command untouched and the containment happens at spawn time through
``apply_limits``.
"""

from __future__ import annotations

import sys
from pathlib import Path

from freecad_buddy.hosts.phase4.sandbox import (
    CPU_CAPPED,
    EGRESS_DENIED,
    FILESYSTEM_READONLY,
    GPU_NONE,
    MEMORY_CAPPED,
    UNPRIVILEGED_UID,
    SandboxReport,
)

BACKEND = "windows-job-object"

# Why the two filesystem/network controls are absent rather than merely unimplemented. Stated once
# and reused so every report carries the same reason and the same remedy.
_NO_ISOLATION = (
    "a Job Object enforces resource limits but provides no network or filesystem isolation; run "
    "the service under WSL2 for the Linux namespace backend if the worker must be contained"
)


def available() -> tuple[bool, str]:
    """Whether the Job Object backend can run here."""
    if sys.platform != "win32":
        return False, "not a Windows host"
    return True, ""


def wrap(command: list[str], job_dir: Path, limits: dict) -> tuple[list[str], SandboxReport]:
    """Report what a Job Object can contain; the command itself needs no rewriting.

    Containment is applied to the process AFTER it is created, through ``apply_limits`` on the
    handle the pool already holds. Returning the command unchanged keeps the pool's spawn path
    identical on both operating systems.
    """
    report = SandboxReport(backend=BACKEND)

    report.miss(EGRESS_DENIED, _NO_ISOLATION)
    report.miss(FILESYSTEM_READONLY, _NO_ISOLATION)
    report.miss(
        UNPRIVILEGED_UID,
        "the worker runs as the operator's own user; an AppContainer or restricted token would "
        "be needed to drop that, and neither is applied here",
    )
    # No GPU device is bound to the worker and rendering goes through the offscreen software
    # path, so GPU-none holds on this backend as it does on Linux.
    report.apply(GPU_NONE)

    if limits.get("memory_bytes"):
        report.apply(MEMORY_CAPPED)
    if limits.get("cpu_time_s"):
        report.apply(CPU_CAPPED)
    return command, report


def apply_limits(job_handle, limits: dict) -> bool:
    """Set memory and CPU ceilings on an existing Job Object handle. Return whether they took.

    Extends the ``JOBOBJECT_EXTENDED_LIMIT_INFORMATION`` story 5.2 already sets for
    ``KILL_ON_JOB_CLOSE``: the structure's ``ProcessMemoryLimit`` and the basic limits'
    ``PerJobUserTimeLimit`` are declared there and were left unset. Setting them here is why this
    backend needs no second kernel primitive.

    :param job_handle: the raw job handle held by ``tree_kill.JobHandle``.
    :param limits: a ``JobLimits`` mapping.
    """
    if sys.platform != "win32" or job_handle is None:
        return False
    memory_bytes = limits.get("memory_bytes")
    cpu_time_s = limits.get("cpu_time_s")
    if not memory_bytes and not cpu_time_s:
        return False

    import ctypes
    from ctypes import wintypes

    class _IoCounters(ctypes.Structure):
        _fields_ = [
            ("ReadOperationCount", ctypes.c_ulonglong),
            ("WriteOperationCount", ctypes.c_ulonglong),
            ("OtherOperationCount", ctypes.c_ulonglong),
            ("ReadTransferCount", ctypes.c_ulonglong),
            ("WriteTransferCount", ctypes.c_ulonglong),
            ("OtherTransferCount", ctypes.c_ulonglong),
        ]

    class _BasicLimits(ctypes.Structure):
        _fields_ = [
            ("PerProcessUserTimeLimit", wintypes.LARGE_INTEGER),
            ("PerJobUserTimeLimit", wintypes.LARGE_INTEGER),
            ("LimitFlags", wintypes.DWORD),
            ("MinimumWorkingSetSize", ctypes.c_size_t),
            ("MaximumWorkingSetSize", ctypes.c_size_t),
            ("ActiveProcessLimit", wintypes.DWORD),
            ("Affinity", ctypes.POINTER(wintypes.ULONG)),
            ("PriorityClass", wintypes.DWORD),
            ("SchedulingClass", wintypes.DWORD),
        ]

    class _ExtendedLimits(ctypes.Structure):
        _fields_ = [
            ("BasicLimitInformation", _BasicLimits),
            ("IoInfo", _IoCounters),
            ("ProcessMemoryLimit", ctypes.c_size_t),
            ("JobMemoryLimit", ctypes.c_size_t),
            ("PeakProcessMemoryUsed", ctypes.c_size_t),
            ("PeakJobMemoryUsed", ctypes.c_size_t),
        ]

    info = _ExtendedLimits()
    flags = 0x00002000  # KILL_ON_JOB_CLOSE, preserved from the handle's creation
    if memory_bytes:
        info.ProcessMemoryLimit = int(memory_bytes)
        flags |= 0x00000100  # JOB_OBJECT_LIMIT_PROCESS_MEMORY
    if cpu_time_s:
        # PerJobUserTimeLimit counts in 100-nanosecond units.
        info.BasicLimitInformation.PerJobUserTimeLimit = int(cpu_time_s * 10_000_000)
        flags |= 0x00000004  # JOB_OBJECT_LIMIT_JOB_TIME
    info.BasicLimitInformation.LimitFlags = flags

    ok = ctypes.windll.kernel32.SetInformationJobObject(
        ctypes.c_void_p(job_handle), 9, ctypes.byref(info), ctypes.sizeof(info)
    )  # 9 = JobObjectExtendedLimitInformation
    return bool(ok)
