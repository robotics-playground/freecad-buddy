"""Job-service seam for the G4 gate (AD-17) — the stub stories 5.2-5.4 replace.

The service's *contract* is what Story 5.1 owes: the terminal status vocabulary, the rule that a
crashed or killed worker can never surface as success, and the shape a JobStatus carries. The
supervisor, the worker pool and the sandbox behind it are 5.2-5.4's work. No repo code runs a job
today, so this module answers every submission from the case's own declaration — it plants no
fault, spawns no process and allocates nothing.

The status shape is fixed here so the fault cases under ``fault-injection/`` were authored against
a vocabulary that already existed, which is the whole point of an entry gate: a service cannot be
graded by measures written after it.

The vocabulary is NOT redefined here. ``contracts.status.TerminalStatus`` is the single source
(AD-17) and this module imports it, so a status added there without a fault case is caught by
``test_gate_g4_exit.py`` rather than drifting silently.

FreeCAD-free and dependency-free to import; the scorer and the gate tests both read it.
"""

from __future__ import annotations

import sys
from pathlib import Path

_SRC = Path(__file__).resolve().parents[2] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from typing import get_args  # noqa: E402

from freecad_buddy.contracts.status import TerminalStatus  # noqa: E402

# The closed terminal set, lifted from the contract rather than retyped. A status this module
# accepted but the contract did not would let the suite grade a service against a vocabulary the
# wire types cannot express.
TERMINAL_STATUSES = frozenset(get_args(TerminalStatus))

# The status a job carries before it resolves. Not terminal: a case whose stub answer is one of
# these has not finished, and `resolve` refuses rather than scoring it.
NON_TERMINAL_STATES = frozenset({"QUEUED", "RUNNING"})

# Every planted fault the G4 entry gate grades, mapped to the terminal status a CORRECT service
# must answer with. The first four are the canonical faults phase-gates.md:97 names; the fifth is
# the revision-diff fault the same line requires be fault-tested. The mapping is the entry gate's
# central claim: it is what a planted case asserts against, and it exists before any service can
# be tuned to it.
#
# The revision fault is graded by a different question than the other four — not "which status did
# the job end with" but "did the checker flag a change outside the requested scope" — and a
# checker that fails to flag it leaves the job wrongly OK, which is why it maps to SPEC_FAILED.
CANONICAL_FAULTS = {
    "infinite_loop": "TIMEOUT",
    "unbounded_alloc": "OOM_KILLED",
    "occt_segfault": "WORKER_CRASHED",
    "wrong_part_clean_report": "SPEC_FAILED",
    "unrelated_feature_changed": "SPEC_FAILED",
    "silent_terminal_failure": "WORKER_CRASHED",
}

# The one planted fault whose defect is the SHAPE of the answer rather than its status. A service
# that resolves a failed job to the right status but strips the structured detail has produced
# exactly the silent failure AD-17 forbids and G4.5 grades ("every failure carries a closed-set
# structured status, none silent"). `resolve` therefore answers it with a detail-less status, which
# `validate_job_status` refuses — the refusal IS the detection.
DETAIL_STRIPPING_FAULTS = frozenset({"silent_terminal_failure"})

# The fault leg each planted fault is authored under, so a case file and the fault it plants
# cannot drift apart without the scorer noticing.
LEG_BY_FAULT = {
    "infinite_loop": "timeout",
    "unbounded_alloc": "oom",
    "occt_segfault": "crash",
    "wrong_part_clean_report": "wrong-part",
    "unrelated_feature_changed": "revision-diff",
    "silent_terminal_failure": "lifecycle",
}

# What a clean control must resolve to. Any other value from a control is a false alarm.
CLEAN_STATUS = "OK"


class ServiceUnavailable(Exception):
    """No job service is implemented. Fail-closed: the job is NOT complete."""


class JobStatusSchemaError(Exception):
    """A job result does not match ``{job_id, state}`` with ``state`` in the closed set."""


def validate_job_status(status) -> dict:
    """Return ``status`` when it matches the JobStatus contract; raise if it does not.

    Stories 5.2-5.4's real supervisor returns worker output, which is untrusted: a result missing
    its ``state``, or carrying a state outside the closed set, would otherwise be read as success
    by a caller doing ``status.get("state") != "SPEC_FAILED"``. Validation is therefore the seam's
    job, not the caller's, and it exists before the supervisor does.

    :param status: the mapping a service backend returned.
    """
    if not isinstance(status, dict):
        raise JobStatusSchemaError(f"job status must be a mapping, got {type(status).__name__}")
    if "state" not in status:
        raise JobStatusSchemaError("job status declares no 'state'")
    state = status["state"]
    if state in NON_TERMINAL_STATES:
        raise JobStatusSchemaError(f"job status is still {state}, not a terminal outcome")
    if state not in TERMINAL_STATUSES:
        raise JobStatusSchemaError(
            f"state {state!r} is outside the closed set {sorted(TERMINAL_STATUSES)}"
        )
    if not isinstance(status.get("job_id"), str) or not status["job_id"]:
        raise JobStatusSchemaError("job status carries no job_id")
    # A failure must say why. AD-17's "none silent" rule is what G4.5 grades, and a terminal
    # failure with no detail is exactly the silent failure the soak leg exists to catch.
    if state != CLEAN_STATUS and not isinstance(status.get("detail"), dict):
        raise JobStatusSchemaError(f"terminal failure {state!r} carries no structured detail")
    return status


def resolve(case: dict) -> dict:
    """Return the JobStatus a CORRECT service would produce for ``case``.

    This is the stub's whole behaviour. It reads the fault the case declares and answers with the
    status that fault must map to — it does not run a job, so it proves nothing about a real
    service. What it does prove is that the suite can tell a planted fault from a clean control
    before any service exists, which is what an entry gate owes.

    A case naming a fault outside ``CANONICAL_FAULTS`` raises rather than defaulting to ``OK``: a
    typo in a case file would otherwise silently become a passing control.

    :param case: the loaded ``case.yaml`` mapping.
    """
    kind = (case.get("fault") or {}).get("kind")
    if kind == "clean_control":
        return _status(case, CLEAN_STATUS)
    if kind != "planted_defect":
        raise JobStatusSchemaError(
            f"case {case.get('id', '<no id>')!r}: unknown fault kind {kind!r}"
        )

    planted = case.get("planted_op")
    if planted not in CANONICAL_FAULTS:
        raise JobStatusSchemaError(
            f"case {case.get('id', '<no id>')!r}: planted_op {planted!r} is not one of "
            f"{sorted(CANONICAL_FAULTS)}"
        )
    return _status(
        case,
        CANONICAL_FAULTS[planted],
        with_detail=planted not in DETAIL_STRIPPING_FAULTS,
    )


def _status(case: dict, state: str, with_detail: bool = True) -> dict:
    """Build a JobStatus for ``case`` resolving to ``state``, validated before it is returned.

    ``with_detail=False`` plants the silent-failure defect: a terminal failure carrying no
    structured detail. ``validate_job_status`` raises on it, which is the intended outcome — the
    suite grades whether the shape is refused, not whether it can be constructed.
    """
    status: dict = {
        "schema": "fcb.job-status/1",
        "job_id": str(case.get("id", "unknown")),
        "state": state,
    }
    if state != CLEAN_STATUS and with_detail:
        status["detail"] = {
            "code": f"job.{state.lower()}",
            "message": f"stub service: {case.get('id', '<no id>')} resolved to {state}",
        }
    return validate_job_status(status)


def submit(_spec) -> dict:
    """Refuse a real submission: there is no service behind this seam yet.

    ``resolve`` answers the suite from a case declaration, which is how the entry gate grades its
    own machinery. A caller submitting a real spec is asking for a DELIVERABLE — a validated
    model, its exports and a report — and nothing produces one today.

    Story 5.2 landed the supervisor, the worker pool and whole-tree kill
    (``hosts/phase4/``), so a job's LIFECYCLE now runs: it can be spawned, deadlined, killed, and
    resolved to a closed-set status. That is not a deliverable. What is still missing is the
    designer payload and the job API that carries a spec to it (story 5.4), plus the sandbox the
    worker must run inside (story 5.3).

    So this stays raising. Flipping it once the lifecycle worked would make the gate report a
    capability the service does not have, which is the self-deception an entry gate exists to
    prevent.
    """
    raise ServiceUnavailable(
        "no job service implemented yet: the supervisor and worker pool exist (story 5.2), but "
        "the per-job sandbox (5.3) and the job API with its designer payload (5.4) do not, so "
        "no job can be run end to end and no deliverable can be produced"
    )
