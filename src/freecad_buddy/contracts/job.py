"""Job status: the job API result shape.

``JobState`` is imported from ``status.py`` and never redefined here.
"""

from __future__ import annotations

from typing import Literal, TypedDict

from freecad_buddy.contracts.envelope import ResultEnvelope
from freecad_buddy.contracts.status import ErrorDetail, JobState


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
