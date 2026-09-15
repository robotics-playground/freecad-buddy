"""The single place an exit condition becomes a terminal status (AD-17).

Every way a job can end — a clean return, a deadline, an abnormal exit, a memory cap, a refused
result — resolves here and nowhere else. One decision point is what makes "no failure is silent"
checkable: a caller that invented its own status could emit a value outside the closed set, or
emit none at all, and the closed set would stop meaning anything.

FreeCAD-free and dependency-free: it decides a status from an exit condition, which needs no
geometry and no live document.
"""

from __future__ import annotations

from dataclasses import dataclass

from freecad_buddy.contracts.status import ErrorDetail, TerminalStatus

# The status a job carries when its worker returned normally and its result validated.
OK: TerminalStatus = "OK"


@dataclass(frozen=True)
class Outcome:
    """What was observed when a job ended, before it is named.

    Deliberately a record of OBSERVATIONS rather than a status: the caller reports what it saw
    (the worker returned, the deadline fired, the process exited with a code), and this module
    alone decides which closed-set member that is. A caller that passed a status in would be
    making the decision this module exists to centralize.

    :param returned: whether the worker returned a result at all.
    :param deadline_exceeded: whether the wall-clock deadline fired.
    :param memory_exceeded: whether a memory cap was observed to be breached.
    :param exit_code: the process exit code, when the process exited on its own.
    :param signal_number: the signal that terminated the process, when one did.
    :param result_refused: whether the worker returned something that failed validation.
    :param message: a human-readable note carried into the detail.
    """

    returned: bool = False
    deadline_exceeded: bool = False
    memory_exceeded: bool = False
    exit_code: int | None = None
    signal_number: int | None = None
    result_refused: bool = False
    message: str = ""


def resolve(outcome: Outcome) -> tuple[TerminalStatus, ErrorDetail | None]:
    """Return the terminal status and structured detail for ``outcome``.

    Order matters and encodes precedence. A job that both blew its deadline and exited non-zero
    is a ``TIMEOUT``: the non-zero exit is a CONSEQUENCE of the kill we issued, so reporting the
    exit code would name our own kill as the fault. The same reasoning puts the memory cap ahead
    of the signal it produced.

    A clean return that failed validation is ``SPEC_FAILED``, never ``OK``: the worker claimed
    success and the claim did not survive checking, which is exactly the "HTTP 200 for a bad
    part" case the supervisor exists to close.
    """
    if outcome.deadline_exceeded:
        return "TIMEOUT", _detail(
            "job.timeout",
            outcome.message or "wall-clock deadline exceeded; worker tree killed",
        )
    if outcome.memory_exceeded:
        return "OOM_KILLED", _detail(
            "job.oom_killed",
            outcome.message or "memory cap exceeded; worker tree killed",
        )
    if outcome.result_refused:
        return "SPEC_FAILED", _detail(
            "job.result_refused",
            outcome.message or "worker result failed validation",
        )
    if outcome.signal_number is not None:
        return "WORKER_CRASHED", _detail(
            "job.worker_crashed",
            outcome.message or f"worker terminated by signal {outcome.signal_number}",
            {"signal": outcome.signal_number},
        )
    if outcome.exit_code:
        # Truthy, so a clean 0 falls through to the returned/absent check below.
        return "WORKER_CRASHED", _detail(
            "job.worker_crashed",
            outcome.message or f"worker exited with code {outcome.exit_code}",
            {"exit_code": outcome.exit_code},
        )
    if not outcome.returned:
        # Exit code 0 with nothing returned: the process ended without producing a result. Naming
        # this OK would report a job that ran nothing as a job that succeeded.
        return "WORKER_CRASHED", _detail(
            "job.worker_crashed",
            outcome.message or "worker exited without returning a result",
        )
    return OK, None


def _detail(code: str, message: str, data: dict | None = None) -> ErrorDetail:
    """Build the structured detail every non-OK status carries.

    A terminal failure with no machine-readable detail is the silent failure AD-17 forbids and
    G4.5 grades, so the detail is built here rather than left to each caller to remember.
    """
    detail: ErrorDetail = {"code": code, "message": message}
    if data:
        detail["data"] = data
    return detail
