"""Per-process resource ceilings applied inside the worker.

A backstop, never a boundary. ``setrlimit`` stops an honest runaway — a job that allocates until
it falls over — and the OS refuses the allocation rather than letting the host swap to death. It
does not contain a hostile worker: a process can lower its own soft limits, and nothing here
restricts what the worker may read, write or connect to. The jail that does contain it is story
5.3's ``run_job_in_sandbox``.

The distinction is recorded because the statuses look identical from outside. A job killed by
this ceiling and a job killed by a cgroup both resolve to ``OOM_KILLED``; only the containment
claim differs, and ``benchmarks/g4/THREATS.md`` is where that limit is stated for the gate.

The ``resource`` module is POSIX-only. On Windows the ceilings come from the Job Object instead,
so ``apply`` is a no-op here and the limits are set by the supervisor at spawn time.
"""

from __future__ import annotations

try:
    import resource
except ImportError:  # Windows
    resource = None  # type: ignore[assignment]


def available() -> bool:
    """Whether per-process ceilings can be applied on this platform."""
    return resource is not None


def apply(limits: dict) -> list[str]:
    """Apply the ceilings in ``limits`` to the current process; return the ones that took effect.

    Unknown or absent members are skipped rather than defaulted: a caller that meant "no memory
    cap" and a caller that forgot to set one must not get different behaviour by accident, and
    the supervisor is what decides the default.

    A ceiling the OS refuses is skipped rather than raised. The worker is about to do real work,
    and failing to start it because a limit could not be lowered would turn a soft degradation
    into a hard failure.

    :param limits: a ``JobLimits`` mapping.
    """
    if resource is None:
        return []

    applied: list[str] = []
    memory_bytes = limits.get("memory_bytes")
    if isinstance(memory_bytes, int) and memory_bytes > 0:
        if _set(resource.RLIMIT_AS, memory_bytes):
            applied.append("memory_bytes")

    cpu_time_s = limits.get("cpu_time_s")
    if isinstance(cpu_time_s, (int, float)) and cpu_time_s > 0:
        # RLIMIT_CPU is whole seconds; round up so a sub-second budget is not truncated to an
        # immediate kill.
        if _set(resource.RLIMIT_CPU, max(1, int(cpu_time_s + 0.999))):
            applied.append("cpu_time_s")

    return applied


def _set(which: int, soft: int) -> bool:
    """Lower one soft limit, keeping the existing hard limit. Return whether it took."""
    if resource is None:
        return False
    try:
        _, hard = resource.getrlimit(which)
        if hard != resource.RLIM_INFINITY:
            soft = min(soft, hard)
        resource.setrlimit(which, (soft, hard))
    except (ValueError, OSError):
        return False
    return True
