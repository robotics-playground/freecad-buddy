"""The worker side of the process boundary — the only place in this package FreeCAD may load.

The supervisor never imports FreeCAD; this module runs in the child process, where importing it
is both legal and necessary. Keeping the import here is not a style choice: it is what makes the
supervisor's RSS flat by construction, and a flat supervisor is what makes the G4 soak's leak
measurement mean anything.

The payload is INJECTED rather than hard-wired. A job kind resolves to a callable through
``PAYLOADS``, so the lifecycle this story proves — spawn, run, deadline, kill, status — is
measurable with payloads that sleep, allocate, crash or return, and does not have to be rebuilt
when the real designer payload arrives with story 5.4.
"""

from __future__ import annotations

import os
from typing import Callable

from freecad_buddy.contracts.envelope import ResultEnvelope
from freecad_buddy.contracts.job import JobSpec
from freecad_buddy.hosts.phase4 import resource_limits

# A payload takes the validated spec and returns a result envelope. It runs inside the worker
# process with FreeCAD available; anything it raises is caught by ``run_job`` and reported rather
# than escaping as a traceback across the process boundary.
Payload = Callable[[JobSpec], ResultEnvelope]

# Job kind -> payload, populated inside the WORKER process. The parent's copy of this dict is
# irrelevant: the worker is a fresh interpreter, so a payload registered in the supervisor never
# reaches it. Registration happens through ``payload_module`` on the spec, which the worker
# imports before dispatch — see ``load_payloads``.
PAYLOADS: dict[str, Payload] = {}


class UnknownJobKind(ValueError):
    """The spec named a job kind no payload is registered for."""


def register(kind: str, payload: Payload) -> None:
    """Register ``payload`` for ``kind`` in THIS process.

    Called by a payload module's import side effect, which the worker triggers via
    ``load_payloads``. Registering in the supervisor does nothing for the worker and is a mistake
    worth naming: the two are different interpreters.
    """
    PAYLOADS[kind] = payload


def load_payloads(spec: JobSpec) -> None:
    """Import the module that registers this job's payload, if the spec names one.

    The spec carries the module PATH rather than the callable because a callable cannot cross a
    process boundary that started with a fresh interpreter. Importing by name is also what keeps
    the worker honest about what it will run: the module is resolved from the spec, not chosen by
    the worker.
    """
    module = spec.get("payload_module")
    if not module:
        return
    __import__(str(module))


def run_job(spec: JobSpec) -> ResultEnvelope:
    """Run one job to completion in this process and return its envelope.

    Applies the spec's resource limits to THIS process before dispatching, so a payload that
    allocates without bound is stopped by a ceiling it cannot raise. The limits are a per-process
    backstop, not a jail — the jail is story 5.3's, and the difference matters: a `setrlimit`
    ceiling stops an honest runaway, while a sandbox contains a hostile one.

    Every failure resolves to a raised exception rather than a status. The supervisor owns status
    (``status_map``), and a worker that named its own outcome could call a failed job ``OK``.
    """
    limits = spec.get("limits") or {}
    resource_limits.apply(limits)
    load_payloads(spec)

    kind = spec.get("kind")
    payload = PAYLOADS.get(str(kind))
    if payload is None:
        raise UnknownJobKind(f"no payload registered for job kind {kind!r}")
    return payload(spec)


def worker_main(spec: JobSpec) -> ResultEnvelope:
    """Process entry point the pool calls in the spawned child.

    Thin on purpose: the pool needs one picklable module-level callable to hand the child, and
    keeping the logic in ``run_job`` lets a test exercise it in-process without a pool.
    """
    return run_job(spec)


def worker_pid() -> int:
    """This worker's pid, for the supervisor's tree-kill bookkeeping."""
    return os.getpid()
