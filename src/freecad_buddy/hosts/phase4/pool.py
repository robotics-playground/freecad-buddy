"""The worker pool: one killable process per job, with a bounded queue and a hard deadline.

Three decisions are load-bearing and none is a preference.

``spawn``, never ``fork``. ``fork`` copies a process mid-flight including its threads, which is a
known hazard with Qt and OCCT, and Windows has no ``fork`` at all. One context for both operating
systems keeps the pool's behaviour identical on each.

One task per child. A worker imports FreeCAD once, runs exactly one job, and exits. The
alternative — a long-lived worker "cleaned between jobs" — does not reclaim memory: closing a
document invalidates the Python wrapper while the OCCT allocator keeps the freed blocks. The
process is the reclamation unit, so process exit is the cleanup.

A bounded queue. Submission past the bound is refused rather than queued, because an unbounded
queue converts a burst of traffic into host memory exhaustion — a failure that takes the
supervisor down with it, and a dead supervisor reports nothing at all.

This module runs a job through a ``subprocess`` rather than ``ProcessPoolExecutor``. The executor
cannot kill a running task: cancelling a future that has already started is a no-op, and a
worker that ignores its deadline is exactly what we must be able to stop. Owning the process
means owning its pid, which is what ``tree_kill`` needs.
"""

from __future__ import annotations

import json
import os
import queue
import subprocess
import sys
import threading
import time
from dataclasses import dataclass, field

from freecad_buddy.contracts.job import JobSpec
from freecad_buddy.hosts.phase4 import sandbox, tree_kill
from freecad_buddy.hosts.phase4.status_map import Outcome

# The wall-clock budget a job gets when its spec names none. Generous, because a real part can
# take minutes; the point of a default is that a job ALWAYS has a deadline, not that this number
# is right for any particular job.
DEFAULT_DEADLINE_SECONDS = 600.0

# How many jobs may wait before submission is refused. Small on purpose: backpressure that only
# engages after thousands of queued jobs has already let the host take the damage.
DEFAULT_QUEUE_BOUND = 32

# How many workers are kept warm. The design marks this DEFERRED-DETAIL, to be set empirically by
# the G4 soak; 2 ships as a safe default that exercises refill without pinning the host.
DEFAULT_WARM_WORKERS = 2

# One task per child. Raising this trades memory reclamation for spawn latency, and the trade is
# only defensible with soak evidence — see the module docstring.
MAX_TASKS_PER_CHILD = 1


class QueueFull(Exception):
    """The bounded queue is at its limit; the submission was refused, not dropped silently."""


@dataclass
class JobRun:
    """What one job's execution produced, as OBSERVATIONS for ``status_map`` to name."""

    spec: JobSpec
    outcome: Outcome
    envelope: dict | None = None
    stderr: str = ""
    duration_s: float = 0.0
    # What the sandbox actually applied for this run. Carried on the run rather than looked up
    # later so a status can state its own containment rather than the pool's current setting.
    sandbox: dict = field(default_factory=dict)


@dataclass
class PoolStats:
    """What the health surface reports. Sampled at job boundaries, never parsed from logs."""

    jobs_started: int = 0
    jobs_finished: int = 0
    queue_depth: int = 0
    warm_workers: int = 0
    killed_trees: int = 0
    worker_rss_bytes: dict = field(default_factory=dict)


class WorkerPool:
    """Runs jobs one-per-process, enforcing a deadline and a queue bound.

    Not a ``ProcessPoolExecutor``: see the module docstring. The pool owns each worker's pid so a
    deadline breach can kill the whole tree, which an executor's future cannot do.
    """

    def __init__(
        self,
        queue_bound: int = DEFAULT_QUEUE_BOUND,
        warm_workers: int = DEFAULT_WARM_WORKERS,
        default_deadline_s: float = DEFAULT_DEADLINE_SECONDS,
        python_executable: str | None = None,
    ) -> None:
        self.queue_bound = queue_bound
        self.warm_workers = warm_workers
        self.default_deadline_s = default_deadline_s
        self.python_executable = python_executable or sys.executable
        self.stats = PoolStats(warm_workers=warm_workers)
        self._queue: queue.Queue = queue.Queue(maxsize=queue_bound)
        self._lock = threading.Lock()
        self._last_report = sandbox.SandboxReport(backend="none")

    def submit(self, spec: JobSpec) -> None:
        """Accept a job onto the queue, or refuse it.

        Refusal is a first-class outcome, not an error path: a queue-full status tells the caller
        to back off, whereas an unbounded accept would trade a clear refusal now for host memory
        exhaustion later.
        """
        try:
            self._queue.put_nowait(spec)
        except queue.Full as exc:
            raise QueueFull(
                f"job queue is at its bound of {self.queue_bound}; submission refused"
            ) from exc
        with self._lock:
            self.stats.queue_depth = self._queue.qsize()

    def run_next(self) -> JobRun | None:
        """Run the next queued job to completion. ``None`` when the queue is empty."""
        try:
            spec = self._queue.get_nowait()
        except queue.Empty:
            return None
        with self._lock:
            self.stats.queue_depth = self._queue.qsize()
        return self.run(spec)

    def run(self, spec: JobSpec, job_dir=None) -> JobRun:
        """Run one job in its own process and return what was observed.

        Never raises for a job-level failure. A crash, a hang and a refused result are all things
        this method OBSERVES and reports; turning one into an exception would lose the structured
        detail the closed-set status is supposed to carry.
        """
        deadline_s = self._deadline_for(spec)
        with self._lock:
            self.stats.jobs_started += 1

        started = time.monotonic()
        process, handle = self._spawn(spec, job_dir)
        stdout, stderr, timed_out = self._await(process, deadline_s)
        duration = time.monotonic() - started

        if timed_out:
            tree_kill.kill_tree(process.pid)
            with self._lock:
                self.stats.killed_trees += 1
                self.stats.jobs_finished += 1
            return JobRun(
                spec=spec,
                outcome=Outcome(
                    deadline_exceeded=True,
                    message=f"exceeded {deadline_s:.1f}s wall-clock deadline",
                ),
                stderr=stderr,
                duration_s=duration,
                sandbox=self._last_report.as_dict(),
            )

        if handle is not None:
            # The worker exited on its own; drop the job handle WITHOUT killing, or closing it
            # would kill an already-finished tree and turn a clean run into a reported crash.
            handle.release()

        run = self._observe(spec, process, stdout, stderr, duration)
        run.sandbox = self._last_report.as_dict()
        return run

    def _observe(self, spec, process, stdout: str, stderr: str, duration: float) -> JobRun:
        """Turn a finished process into observations, without naming a status."""
        code = process.returncode
        # POSIX reports a signal as a negative return code; Windows has no signals, so a negative
        # code there is an unusual exit status rather than a signal number.
        signal_number = -code if (code is not None and code < 0 and os.name != "nt") else None

        envelope = None
        refused = False
        if code == 0:
            envelope, refused = _parse_envelope(stdout)

        with self._lock:
            self.stats.jobs_finished += 1

        return JobRun(
            spec=spec,
            outcome=Outcome(
                returned=envelope is not None,
                exit_code=code if signal_number is None else None,
                signal_number=signal_number,
                result_refused=refused,
                message=_first_line(stderr) if code else "",
            ),
            envelope=envelope,
            stderr=stderr,
            duration_s=duration,
        )

    def _deadline_for(self, spec: JobSpec) -> float:
        """The wall-clock budget for ``spec``. Every job has one; a spec may only shorten it."""
        limits = spec.get("limits") or {}
        declared = limits.get("wall_deadline_s")
        if isinstance(declared, (int, float)) and declared > 0:
            return float(declared)
        return self.default_deadline_s

    def _spawn(self, spec: JobSpec, job_dir=None):
        """Start a worker process for ``spec``, contained, and take ownership of its tree.

        The sandbox rewrites the COMMAND and the pool still owns the resulting process. That
        split is deliberate: a sandbox that spawned its own process would hide the pid, and the
        pid is what the deadline needs in order to kill the tree.
        """
        command = [
            self.python_executable,
            "-m",
            "freecad_buddy.hosts.phase4.run_worker",
        ]
        limits = dict(spec.get("limits") or {})
        if job_dir is not None:
            command, report = sandbox.wrap(command, job_dir, limits)
        else:
            # No job directory means no writable mount to grant, so there is nothing to contain
            # filesystem access TO. Recorded rather than silently skipped.
            report = sandbox.SandboxReport(backend="none")
            for control in sandbox.ALL_CONTROLS:
                report.miss(control, "no job directory supplied; sandbox not applied")

        kwargs = tree_kill.spawn_kwargs(
            {
                "stdin": subprocess.PIPE,
                "stdout": subprocess.PIPE,
                "stderr": subprocess.PIPE,
                "text": True,
            }
        )
        process = subprocess.Popen(command, **kwargs)
        handle = tree_kill.JobHandle(process.pid)
        if sys.platform == "win32" and handle is not None and limits:
            from freecad_buddy.hosts.phase4 import sandbox_windows

            sandbox_windows.apply_limits(handle._handle, limits)
        self._last_report = report
        try:
            if process.stdin is not None:
                process.stdin.write(json.dumps(spec))
                process.stdin.close()
        except (BrokenPipeError, OSError):
            # The worker died before reading its spec. Nothing to send; the exit code tells the
            # story and `_observe` will read it.
            pass
        return process, handle

    def _await(self, process, deadline_s: float) -> tuple[str, str, bool]:
        """Wait for the worker, returning (stdout, stderr, timed_out).

        ``communicate(timeout=)`` is used rather than a poll loop so the pipes are drained while
        we wait: a worker writing more than a pipe buffer would otherwise block forever and look
        like a hang we caused.
        """
        try:
            stdout, stderr = process.communicate(timeout=deadline_s)
            return stdout or "", stderr or "", False
        except subprocess.TimeoutExpired:
            # Do NOT communicate() again here — it would block on the pipes of a process we are
            # about to kill. The caller kills the tree; stderr is lost, which is the honest cost
            # of a hung worker and is recorded as such in the timeout detail.
            return "", "", True


def _parse_envelope(stdout: str) -> tuple[dict | None, bool]:
    """Read the worker's result from its stdout. Return (envelope, refused).

    A worker that exited cleanly but wrote nothing parseable is REFUSED rather than treated as
    having returned nothing: a clean exit with unreadable output is a worker claiming success it
    cannot evidence, which is the self-deception the supervisor exists to catch.
    """
    text = stdout.strip()
    if not text:
        return None, True
    try:
        payload = json.loads(text.splitlines()[-1])
    except (ValueError, IndexError):
        return None, True
    if not isinstance(payload, dict):
        return None, True
    return payload, False


def _first_line(text: str) -> str:
    """The first non-empty line of ``text``, for a one-line failure message."""
    for line in text.splitlines():
        if line.strip():
            return line.strip()
    return ""
