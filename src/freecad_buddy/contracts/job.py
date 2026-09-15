"""Job spec and job status: the job API request and result shapes.

``JobState`` is imported from ``status.py`` and never redefined here.
"""

from __future__ import annotations

from typing import Literal, TypedDict

from freecad_buddy.contracts.envelope import ResultEnvelope
from freecad_buddy.contracts.status import ErrorDetail, JobState


class JobLimits(TypedDict, total=False):
    """The resource ceilings a job runs under. Absent members take the supervisor's defaults.

    Every limit is a number the supervisor ENFORCES, not a hint it passes down: a worker cannot
    raise its own ceiling, because the ceiling is applied from outside the process.
    """

    wall_deadline_s: float
    memory_bytes: int
    cpu_time_s: float


class JobSpec(TypedDict, total=False):
    """A submitted job: what to build and the ceilings to build it under.

    The supervisor validates a submission against this shape BEFORE anything is enqueued, so a
    malformed request costs no worker (``INVALID_INPUT``, AD-17). ``payload`` carries the
    job-kind-specific request and stays an open mapping here: the designer job's own schema is
    story 5.4's, and pinning it now would fix a shape nothing yet produces.
    """

    schema: Literal["fcb.job-spec/1"]
    job_id: str  # required
    kind: str  # required
    payload: dict
    # Import path of the module that registers the payload for ``kind``. The worker is a fresh
    # interpreter, so a callable cannot cross the boundary — the spec names a module and the
    # worker imports it. Absent means the worker's built-in registrations must already cover
    # ``kind``.
    payload_module: str | None
    limits: JobLimits | None


class JobStatus(TypedDict, total=False):
    schema: Literal["fcb.job-status/1"]
    job_id: str
    state: JobState  # required
    submitted_at: str
    started_at: str | None
    finished_at: str | None
    detail: ErrorDetail | None
    progress: dict | None
    result: ResultEnvelope | None
    artifacts: dict | None
