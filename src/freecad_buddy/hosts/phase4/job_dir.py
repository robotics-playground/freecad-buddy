"""The ``jobs/<id>/`` data plane — the sandbox's only writable mount.

The layout is part of the containment rather than a filing convention. The sandbox makes exactly
one path writable, so every artifact a job produces must land inside this directory or not at
all, and the supervisor owns creating and cleaning it. A worker that could choose its own output
path would need a second writable mount, and the jail would be that much weaker.

Small JSON crosses the control plane; artifacts cross as paths. No FreeCAD or OCCT object ever
crosses the process boundary.
"""

from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
from pathlib import Path

# The subdirectories every job gets. Created up front so a worker never has to mkdir inside a
# read-only filesystem it has only one hole in.
_SUBDIRS = ("exports", "renders")

SPEC_FILE = "spec.json"
VALIDATION_FILE = "validation.json"
AUDIT_FILE = "audit.log"
STDERR_FILE = "worker.stderr.log"


@dataclass(frozen=True)
class JobDir:
    """One job's directory and the paths inside it the supervisor and worker agree on."""

    root: Path

    @property
    def spec(self) -> Path:
        return self.root / SPEC_FILE

    @property
    def exports(self) -> Path:
        return self.root / "exports"

    @property
    def renders(self) -> Path:
        return self.root / "renders"

    @property
    def validation(self) -> Path:
        return self.root / VALIDATION_FILE

    @property
    def audit(self) -> Path:
        return self.root / AUDIT_FILE

    @property
    def stderr(self) -> Path:
        return self.root / STDERR_FILE


def create(jobs_root: Path, job_id: str, spec: dict | None = None) -> JobDir:
    """Create ``jobs_root/<job_id>/`` with its subdirectories; write ``spec.json`` when given.

    The spec is written by the SUPERVISOR before the worker starts, so the worker reads its
    instructions from inside the one directory it can see rather than receiving them through an
    environment the jail would have to widen for.

    :param jobs_root: the directory holding every job.
    :param job_id: the job's id; must not traverse out of ``jobs_root``.
    """
    safe_id = _safe_id(job_id)
    root = Path(jobs_root) / safe_id
    root.mkdir(parents=True, exist_ok=True)
    for name in _SUBDIRS:
        (root / name).mkdir(exist_ok=True)
    job = JobDir(root=root)
    if spec is not None:
        job.spec.write_text(json.dumps(spec, indent=2), encoding="utf-8")
    return job


def clean(job: JobDir) -> None:
    """Remove the job directory and everything in it.

    Retention is the supervisor's decision, not the worker's — a worker that could delete its own
    evidence could hide a failure it had already reported.
    """
    shutil.rmtree(job.root, ignore_errors=True)


def _safe_id(job_id: str) -> str:
    """Reject a job id that would escape ``jobs_root``.

    Job ids arrive from untrusted submissions. ``../..`` in an id would place the one writable
    mount outside the jobs tree, which would hand the job exactly the filesystem access the
    sandbox exists to deny.
    """
    candidate = str(job_id).strip()
    if not candidate:
        raise ValueError("job id is empty")
    if candidate != Path(candidate).name or candidate in (".", ".."):
        raise ValueError(f"job id {job_id!r} is not a single path segment")
    return candidate
