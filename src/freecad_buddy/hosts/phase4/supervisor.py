"""The Phase 4 supervisor: the long-lived process that owns job lifecycle and status.

**This module must never import FreeCAD, directly or through a first-party import.** Its RSS is
flat by construction, which is the only reason the G4 soak's leak measurement means anything: a
supervisor that loaded FreeCAD would grow for reasons unrelated to any worker leak, and the
number would stop being interpretable. ``scripts/check_imports.py`` enforces this; the guard
exists because nothing else would catch a later edit adding the import.

The supervisor decides three things the worker is never trusted with:

- **Whether a submission is even a job.** A spec failing contract validation is refused before a
  worker is bound, so a malformed request costs nothing.
- **When a job has run too long.** The deadline is enforced from outside the worker, because a
  worker that has hung cannot enforce its own.
- **What the outcome is called.** Status comes from ``status_map`` over observations, never from
  the worker's own claim. A worker that could name itself ``OK`` would be the unchecked claim the
  whole design refuses.
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass, replace

from freecad_buddy.contracts.job import JobSpec, JobStatus
from freecad_buddy.contracts.status import ErrorDetail
from freecad_buddy.hosts.phase4 import revision, status_map
from freecad_buddy.hosts.phase4.pool import JobRun, QueueFull, WorkerPool
from freecad_buddy.usecases.capabilities import Capabilities

# The job kinds a submission may name. Story 5.4 adds the designer kind; until then the
# supervisor accepts only what a payload module can actually serve, so an unknown kind is refused
# at the boundary rather than discovered by a spawned worker.
KNOWN_KINDS: set[str] = set()


@dataclass
class Submission:
    """A validated submission and the status it currently carries."""

    spec: JobSpec
    status: JobStatus


class Supervisor:
    """Validates, runs, and resolves jobs. Never imports FreeCAD.

    :param pool: the worker pool; injected so a test can substitute one without spawning.
    :param caps: the capability record. Built with ``service_mode=True`` by ``build_capabilities``
        so ``debug_exec`` is unreachable regardless of the operator's environment.
    """

    def __init__(self, pool: WorkerPool | None = None, caps: Capabilities | None = None) -> None:
        self.pool = pool or WorkerPool()
        self.caps = caps or build_capabilities()
        # Completed jobs, by id. A revision names the job it revises, and a revision of a job
        # that never ran has no prior state to change — refusing it needs this record.
        self.completed: dict[str, JobStatus] = {}

    def submit_revision(self, request: object) -> JobStatus:
        """Validate a revision against the jobs that actually completed.

        Refused BEFORE a worker binds when the base job is unknown: running it would build a part
        from nothing and report it as a revision of something.
        """
        problem = revision.validate_request(request, self.completed)
        if problem is not None:
            return _status(_revision_id(request), "INVALID_INPUT", problem)
        return _status(_revision_id(request), "QUEUED", None)

    def grade_revision(self, request: dict, diff: object) -> JobStatus:
        """Grade a completed revision's geometry diff against its declared scope.

        The G4.2 question is not "did the revision work" but "did it stay inside what was asked",
        so the scope check is what decides the status here.
        """
        check = revision.check_diff_scope(diff, list(request.get("scope") or []))
        if check["passed"]:
            return _status(_revision_id(request), "OK", None)
        return _status(_revision_id(request), "SPEC_FAILED", check.get("detail"))

    def submit(self, spec: object) -> JobStatus:
        """Validate and enqueue ``spec``; return the status it starts life with.

        Validation happens BEFORE anything is enqueued, so an invalid submission never binds a
        worker. A full queue is refused rather than accepted, because an unbounded queue turns a
        traffic burst into host memory exhaustion — and a dead supervisor reports nothing at all.
        """
        problem = validate_spec(spec)
        if problem is not None:
            return _status(_job_id(spec), "INVALID_INPUT", problem)

        job_spec: JobSpec = spec  # type: ignore[assignment]
        try:
            self.pool.submit(job_spec)
        except QueueFull as exc:
            return _status(
                _job_id(spec),
                "INVALID_INPUT",
                {"code": "job.queue_full", "message": str(exc)},
            )
        return _status(_job_id(spec), "QUEUED", None)

    def run_next(self) -> JobStatus | None:
        """Run the next queued job and resolve it. ``None`` when nothing is queued."""
        run = self.pool.run_next()
        if run is None:
            return None
        return self.resolve(run)

    def run(self, spec: object) -> JobStatus:
        """Validate, run, and resolve one job end to end."""
        problem = validate_spec(spec)
        if problem is not None:
            return _status(_job_id(spec), "INVALID_INPUT", problem)
        return self.resolve(self.pool.run(spec))  # type: ignore[arg-type]

    def resolve(self, run: JobRun) -> JobStatus:
        """Name the outcome of a finished run and build its ``JobStatus``.

        The envelope a worker returned is attached only when the status is ``OK``. A failed job
        that still carried an envelope would invite a reader to treat the worker's own account of
        a failure as the result.

        The sandbox report rides on every status, passing or failing. A caller judging whether to
        trust a result needs to know what contained the job that produced it, and a report present
        only on success would be missing exactly when containment mattered most.
        """
        outcome = _with_memory_observation(run)
        state, detail = status_map.resolve(outcome)
        status = _status(str(run.spec.get("job_id", "")), state, detail)
        if run.sandbox:
            status["artifacts"] = {"sandbox": run.sandbox}
        if state == status_map.OK and run.envelope is not None:
            status["result"] = run.envelope  # type: ignore[typeddict-item]
        job_id = str(run.spec.get("job_id", ""))
        if job_id:
            self.completed[job_id] = status
        return status


# What a worker killed by a memory ceiling leaves behind. ``RLIMIT_AS`` makes the allocation fail
# inside the process, so Python raises ``MemoryError`` and the traceback reaches the worker's
# stderr; a cgroup or Job Object kill instead terminates the process outright, which surfaces as a
# signal or an exit code. Both are memory-cap breaches and both must reach ``OOM_KILLED`` — the
# mapping already exists in ``status_map`` and has been unreachable until something set the flag.
_MEMORY_MARKERS = ("MemoryError", "Cannot allocate memory", "out of memory")

# The Windows Job Object reports a process killed for exceeding ``ProcessMemoryLimit`` with this
# exit code.
_WIN_JOB_MEMORY_EXIT = 0xC0000017  # STATUS_NO_MEMORY


def _with_memory_observation(run: JobRun) -> "status_map.Outcome":
    """Return the run's outcome, with ``memory_exceeded`` set when the evidence says so.

    Kept out of ``status_map`` on purpose: that module decides what an observation is CALLED, and
    this decides what was observed. Folding the evidence-reading in there would give the naming
    rule a second job and make it depend on stderr text.
    """
    outcome = run.outcome
    if outcome.deadline_exceeded or outcome.memory_exceeded:
        return outcome
    stderr = run.stderr or ""
    hit = any(marker in stderr for marker in _MEMORY_MARKERS)
    if not hit and outcome.exit_code is not None:
        hit = (outcome.exit_code & 0xFFFFFFFF) == _WIN_JOB_MEMORY_EXIT
    if not hit:
        return outcome
    return replace(
        outcome,
        memory_exceeded=True,
        message=outcome.message or "worker exceeded its memory ceiling",
    )


def build_capabilities(environ: dict | None = None) -> Capabilities:
    """The supervisor's capability record: service mode is on, unconditionally.

    ``service_mode=True`` is passed as an argument rather than read from the environment on
    purpose. AD-4 makes ``debug_exec`` permanently off in the Phase 4 service, and a value read
    from the environment could be unset by whoever starts the process. A constant cannot.
    """
    return Capabilities.from_env(dict(environ if environ is not None else os.environ),
                                 service_mode=True)


def validate_spec(spec: object) -> ErrorDetail | None:
    """Return the problem with ``spec``, or ``None`` when it is a usable job spec.

    Checks only what the supervisor itself depends on: an id to report against, a kind to
    dispatch, and well-formed limits. The payload stays unvalidated here because its shape is the
    job kind's business — story 5.4's designer spec has its own schema, and validating it in two
    places would let the two disagree.
    """
    if not isinstance(spec, dict):
        return {
            "code": "job.invalid_input",
            "message": f"job spec must be a mapping, got {type(spec).__name__}",
        }
    job_id = spec.get("job_id")
    if not isinstance(job_id, str) or not job_id:
        return {"code": "job.invalid_input", "message": "job spec carries no job_id"}
    kind = spec.get("kind")
    if not isinstance(kind, str) or not kind:
        return {"code": "job.invalid_input", "message": "job spec carries no kind"}
    if KNOWN_KINDS and kind not in KNOWN_KINDS:
        return {
            "code": "job.invalid_input",
            "message": f"unknown job kind {kind!r}; known: {sorted(KNOWN_KINDS)}",
        }

    limits = spec.get("limits")
    if limits is not None:
        if not isinstance(limits, dict):
            return {
                "code": "job.invalid_input",
                "message": f"limits must be a mapping, got {type(limits).__name__}",
            }
        for field in ("wall_deadline_s", "memory_bytes", "cpu_time_s"):
            value = limits.get(field)
            if value is None:
                continue
            if isinstance(value, bool) or not isinstance(value, (int, float)) or value <= 0:
                return {
                    "code": "job.invalid_input",
                    "message": f"limits.{field} must be a positive number, got {value!r}",
                }
    return None


def _status(job_id: str, state: str, detail: ErrorDetail | None) -> JobStatus:
    """Build a ``JobStatus``. A non-OK state always carries detail — AD-17 forbids a silent one."""
    status: JobStatus = {
        "schema": "fcb.job-status/1",
        "job_id": job_id,
        "state": state,  # type: ignore[typeddict-item]
        "finished_at": _now(),
    }
    if detail is not None:
        status["detail"] = detail
    return status


def _revision_id(request: object) -> str:
    """The id to report a revision against; empty when the request did not carry one."""
    if isinstance(request, dict):
        value = request.get("job_id")
        if isinstance(value, str):
            return value
    return ""


def _job_id(spec: object) -> str:
    """The id to report a rejection against; empty when the spec did not carry one."""
    if isinstance(spec, dict):
        value = spec.get("job_id")
        if isinstance(value, str):
            return value
    return ""


def _now() -> str:
    """An ISO-8601 UTC timestamp for a status transition."""
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
