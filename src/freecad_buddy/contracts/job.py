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


class RevisionRequest(TypedDict, total=False):
    """A change to a part a previous job produced, plus the scope it is allowed to touch.

    ``scope`` is the whole of the G4.2 criterion. A revision asks for one thing to change; a
    revision that also changes something nobody asked about is the failure the gate grades, and
    without a DECLARED scope there is nothing to judge "out of scope" against. The requester
    names what may change, and the diff is graded against that list rather than against whatever
    the result happened to touch.

    ``changes`` carries the edit itself: ``{parameter_name: new_value}`` for a driving dimension.
    Keeping it to declared parameters is deliberate — a revision that could rewrite arbitrary
    feature properties would have no stable scope to grade.
    """

    schema: Literal["fcb.revision-request/1"]
    job_id: str  # required; the NEW job this revision creates
    base_job_id: str  # required; the job whose result is being revised
    changes: dict  # required
    scope: list[str]  # required; object names the change may touch
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
