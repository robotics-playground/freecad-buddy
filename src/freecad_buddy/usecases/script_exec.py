"""``script_exec`` handler: Python inside FreeCAD for an operation no typed tool covers.

The call runs inside an observe-only bracket (T-6, AD-5): fingerprint, one transaction named after
the script, the script, a recompute, a commit, fingerprint. The bracket never aborts and never
rolls back: a script that raises keeps the changes it made, and a late return after a ``TIMEOUT``
commits them (AD-27). It also runs no post-verify and no TNP audit. Registration follows the
operator switches and every call is audit-logged by the dispatch boundary, which takes both
digests from the result. The reduced namespace is blast-radius hygiene, not a security boundary.
Requires an explicit ``doc`` handle.
"""

from __future__ import annotations

import io
import traceback
from contextlib import redirect_stdout
from dataclasses import dataclass, field

from freecad_buddy.contracts import FingerprintRecord, ResultEnvelope, summary_text
from freecad_buddy.usecases import result_projection, shim
from freecad_buddy.usecases.documents import DocumentRegistry, ValidationError
from freecad_buddy.usecases.fingerprint import fingerprint

# A bytes-level hash of ``transaction.py`` pins the G2 ``run_mutation`` validator score
# (``benchmarks/runner.py``), so the shared helper is reused under its private name instead of
# being renamed there.
from freecad_buddy.usecases.transaction import _invalid_objects as invalid_objects

_UNSET = object()

_NAME_PREFIX = "script_exec"
# Keeps the Undo list readable; FreeCAD stores any length unchanged.
_NAME_SOURCE_LIMIT = 80
_TRACEBACK_LIMIT = 4000
# FreeCAD stops growing the undo list at its default limit, so a full list hides new entries.
_FULL_UNDO_STACK = 20

_UNDO_UNAVAILABLE_NOTE = (
    "undo is unavailable on this document: document_undo cannot revert this call"
)
_NO_UNDO_STEP_NOTE = (
    "undo_steps 0: this call recorded no undo step, so document_undo would revert an earlier step"
)
_UNDO_CLEARED_NOTE = (
    "undo_steps 0: the script switched undo off or emptied the undo list, so document_undo "
    "cannot revert earlier steps"
)
_UNDO_UNKNOWN_NOTE = (
    "undo_steps null: the undo list is full of identical entries, so the count is unknown"
)
_SCRIPT_UNDID_NOTE = (
    "the script undid steps itself: document_undo cannot restore the state before this call"
)


class _CapturedOutput(io.StringIO):
    """Script stdout that a script calling ``sys.stdout.close()`` cannot make unreadable."""

    def close(self) -> None:
        pass


def script_exec(
    registry: DocumentRegistry, doc: str | None, code: str, recompute: bool = True
) -> ResultEnvelope:
    """Execute the caller's ``code`` against the document named by ``doc``, inside the bracket.

    ``value_repr`` is the repr of a bound ``result`` variable when the code sets one. ``recompute``
    false skips the bracket's recompute, so an object the script touched stays ``Touched``.
    """
    if not code:
        raise ValidationError("script_exec requires 'code'")

    # Resolve and run under the registry lock so the handle cannot be closed mid-exec.
    return registry.with_document(
        doc, lambda handle, document: _run_bracket(handle, document, code, recompute)
    )


def _transaction_name(code: str) -> str:
    for line in code.splitlines():
        stripped = line.strip()
        if stripped:
            return f"{_NAME_PREFIX} {stripped[:_NAME_SOURCE_LIMIT]}"
    return _NAME_PREFIX


def _added_undo_steps(before: list[str], after: list[str]) -> int | None:
    """Count the entries the call added to the most-recent-first undo list.

    Two alignments cover what a call can do. A full stack drops its oldest entry for each new
    one, so ``after[k:]`` is the leading part of ``before``. A script that undid entries
    (``doc.undo()``) and then recorded its own leaves ``after[k:]`` as the tail of ``before``.
    The smaller ``k`` is the number added. Three limits follow from comparing names alone:
    repeated names can make the result too low (a script that calls ``doc.undo()`` and whose
    first line matches an earlier entry on a short stack), a full stack of 20 entries can make it
    too high (it reports 20 for a call that added 2), and a full stack of one repeated name gives
    ``None``, because a write and a read-only script leave the same list.
    """
    if len(before) >= _FULL_UNDO_STACK and after == before and len(set(before)) == 1:
        return None
    size = len(before)
    for added in range(len(after) + 1):
        remaining = after[added:]
        if remaining == before[: len(remaining)] or remaining == before[size - len(remaining) :]:
            return added
    return len(after)


def _describe(exc: BaseException) -> str:
    """``<Type>: <message>``; an exception whose ``__str__`` raises still gets a description."""
    if isinstance(exc, _CombinedFailure):
        return str(exc)
    try:
        text = str(exc)
    except BaseException:  # noqa: BLE001 - a script-defined __str__ may raise SystemExit
        text = "<str failed>"
    return f"{type(exc).__name__}: {text}"


def _value_repr(value: object) -> tuple[str | None, str | None]:
    """The repr of ``result`` and a note; the repr of a deleted FreeCAD object raises."""
    if value is _UNSET:
        return None, None
    try:
        return repr(value), None
    except BaseException as exc:  # noqa: BLE001 - a script-defined __repr__ may raise SystemExit
        text = f"<repr failed: {_describe(exc)}>"
        return text, f"result {type(value).__name__} has no repr: {_describe(exc)}"


def _is_dead(document: object) -> bool:
    try:
        document.Name
    except ReferenceError:
        return True
    return False


def _any_touched(document: object) -> bool:
    return any("Touched" in obj.State for obj in document.Objects)


class _CombinedFailure(RuntimeError):
    """Two bracket phases failed; the message already names both exception types."""


def _error_detail(code: str, message: str, data: dict) -> dict:
    return {"code": code, "message": message, "data": data}


def _script_namespace(document: object) -> dict:
    import FreeCAD

    namespace: dict = {"FreeCAD": FreeCAD, "App": FreeCAD, "doc": document}
    try:
        import Part

        namespace["Part"] = Part
    except ImportError:
        pass
    return namespace


def _with_failure(
    failure: tuple[str, Exception] | None, phase: str, exc: Exception
) -> tuple[str, Exception]:
    """``failure`` extended by a later failing ``phase``; the first phase keeps the name."""
    if failure is None:
        return phase, exc
    first_phase, first = failure
    combined = _CombinedFailure(f"{_describe(first)}; {phase} also failed: {_describe(exc)}")
    return first_phase, combined


@dataclass
class _Observation:
    changed: list = field(default_factory=list)
    new_errors: list[str] = field(default_factory=list)
    undo_steps: int | None = None
    script_undid_steps: bool = False
    undo_disabled_by_script: bool = False
    failure: tuple[str, Exception] | None = None


def _undid_entries(before: list[str], after: list[str], added: int) -> bool:
    """Whether ``after`` lost entries of ``before`` beyond the oldest ones a full stack drops."""
    remaining = after[added:]
    expected = min(len(before), _FULL_UNDO_STACK - added)
    return remaining != before[: len(remaining)] or len(remaining) < expected


def _observe(
    document: object,
    before: FingerprintRecord,
    after: FingerprintRecord | None,
    invalid_before: set[str],
    names_before: list[str],
) -> _Observation:
    """Read ``new_errors``, ``undo_steps`` and ``changed``; each read fails alone.

    A read that raises gives ``None`` (``undo_steps``) or an empty list and the failure, so one
    broken read never turns a recorded undo step into a reported zero.
    """
    observation = _Observation()
    failure: tuple[str, Exception] | None = None
    new_errors: list[str] = []
    undo_steps: int | None = None
    changed: list = []
    try:
        invalid_after = {name for name, _status in invalid_objects(document)}
        new_errors = sorted(invalid_after - invalid_before)
    except Exception as exc:  # noqa: BLE001 - the script already ran; report, never raise
        failure = failure or ("observe", exc)
    try:
        names_after = list(document.UndoNames)
        undo_steps = _added_undo_steps(names_before, names_after)
        if undo_steps is not None:
            observation.script_undid_steps = _undid_entries(names_before, names_after, undo_steps)
        observation.undo_disabled_by_script = not document.UndoMode or (
            bool(names_before) and not names_after
        )
    except Exception as exc:  # noqa: BLE001 - the script already ran; report, never raise
        failure = failure or ("observe", exc)
    try:
        changed = result_projection.changed_objects(before, after, False)
    except Exception as exc:  # noqa: BLE001 - the script already ran; report, never raise
        failure = failure or ("observe", exc)
    observation.changed = changed
    observation.new_errors = new_errors
    observation.undo_steps = undo_steps
    observation.failure = failure
    return observation


def _setup_failed(phase: str, exc: Exception) -> ResultEnvelope:
    """The result when a read before the script failed: nothing ran and nothing is open."""
    message = _describe(exc)
    return {
        "schema": "fcb.result-envelope/1",
        "status": "SPEC_FAILED",
        "detail": _error_detail("exec.bracket_failed", message, {"phase": phase}),
        "structured_content": {},
        "text": f"script not run: {phase} failed: {message}",
    }


def _close_bracket(
    document: object, recompute: bool
) -> tuple[FingerprintRecord | None, tuple[str, Exception] | None]:
    """Recompute, commit and fingerprint after the script; return the record and any failure.

    A phase that raises leaves the changes in place and names the phase, so the caller reports it
    instead of aborting (AD-5).
    """
    failure: tuple[str, Exception] | None = None
    try:
        if recompute and _any_touched(document):
            document.recompute()
    except Exception as exc:  # noqa: BLE001 - the transaction must still close
        failure = ("recompute", exc)
    # Both commits run whatever failed before them: a transaction left open would take the name
    # of the next change by any caller.
    try:
        document.commitTransaction()
    except Exception as exc:  # noqa: BLE001 - the application-level close below must still run
        failure = _with_failure(failure, "commit", exc)
    try:
        shim.commit_active_transaction()
    except Exception as exc:  # noqa: BLE001 - the changes stay; report the phase
        failure = _with_failure(failure, "commit", exc)
    if failure is not None:
        return None, failure
    try:
        after = fingerprint(document)
        result_projection.remember(after)
    except Exception as exc:  # noqa: BLE001 - the changes stay; report the phase
        return None, ("fingerprint_after", exc)
    return after, None


def _run_bracket(handle: str, document: object, code: str, recompute: bool) -> ResultEnvelope:
    undo_enabled = shim.enable_undo(document)
    try:
        before = fingerprint(document)
    except Exception as exc:  # noqa: BLE001 - nothing ran yet; report instead of raising
        return _setup_failed("fingerprint_before", exc)
    try:
        invalid_before = {name for name, _status in invalid_objects(document)}
        names_before = list(document.UndoNames)
    except Exception as exc:  # noqa: BLE001 - nothing ran yet; report instead of raising
        return _setup_failed("observe_before", exc)
    result_projection.remember(before)

    namespace = _script_namespace(document)
    buffer = _CapturedOutput()
    document.openTransaction(_transaction_name(code))
    script_error: BaseException | None = None
    try:
        with redirect_stdout(buffer):
            exec(code, namespace)  # noqa: S102 - raw exec is the tool's purpose
    except BaseException as exc:  # noqa: BLE001 - SystemExit must not end the serve loop
        script_error = exc

    after = None
    changed: list = []
    new_errors: list[str] = []
    undo_steps: int | None = 0
    observation = _Observation()
    bracket_failure: tuple[str, Exception] | None = None
    gone = _is_dead(document)
    if gone:
        # closeDocument clears the application-level transaction only when the document held its
        # own, so a script that closed its document before writing leaves the name open.
        try:
            shim.commit_active_transaction()
        except Exception as exc:  # noqa: BLE001 - the script already ran; report, never raise
            bracket_failure = ("commit", exc)
    else:
        after, bracket_failure = _close_bracket(document, recompute)
        observation = _observe(document, before, after, invalid_before, names_before)
        changed, new_errors = observation.changed, observation.new_errors
        undo_steps = observation.undo_steps
        bracket_failure = bracket_failure or observation.failure

    value = namespace.get("result", _UNSET)
    value_repr, repr_note = _value_repr(value)
    structured = {
        "doc": handle,
        "stdout": buffer.getvalue(),
        "value_repr": value_repr,
        "fingerprint_before": before["digest"],
        "fingerprint_after": after["digest"] if after is not None else None,
        "changed": changed,
        "new_errors": new_errors,
        "undo_steps": undo_steps,
    }
    notes = []
    if repr_note is not None:
        notes.append(repr_note)
    if gone:
        notes.append(f"the script closed its document {handle}; this handle is now stale")
    elif not undo_enabled:
        notes.append(_UNDO_UNAVAILABLE_NOTE)
    elif undo_steps == 0:
        notes.append(
            _UNDO_CLEARED_NOTE if observation.undo_disabled_by_script else _NO_UNDO_STEP_NOTE
        )
    elif undo_steps is None and bracket_failure is None:
        notes.append(_UNDO_UNKNOWN_NOTE)
    if observation.script_undid_steps:
        notes.append(_SCRIPT_UNDID_NOTE)
    if new_errors:
        notes.append(f"new invalid objects: {', '.join(new_errors)}")
    return _envelope(structured, script_error, bracket_failure, new_errors, notes)


def _envelope(
    structured: dict,
    script_error: BaseException | None,
    bracket_failure: tuple[str, Exception] | None,
    new_errors: list[str],
    notes: list[str],
) -> ResultEnvelope:
    status = "OK"
    detail = None
    if script_error is not None:
        # The first frame is the bridge's own exec call; the last lines name the exception.
        frames = script_error.__traceback__
        frames = frames.tb_next if frames is not None else None
        trace = "".join(traceback.format_exception(type(script_error), script_error, frames))
        message = _describe(script_error)
        data = {"exception": type(script_error).__name__, "traceback": trace[-_TRACEBACK_LIMIT:]}
        if bracket_failure is not None:
            data["bracket_phase"] = bracket_failure[0]
            data["bracket_message"] = _describe(bracket_failure[1])
        status, detail = "INVALID_INPUT", _error_detail("exec.python_error", message, data)
        kept = "; the changes it made so far are kept" if structured["changed"] else ""
        notes.insert(0, f"script raised {message}{kept}")
    elif bracket_failure is not None:
        phase, exc = bracket_failure
        message = _describe(exc)
        status = "RECOMPUTE_ERROR"
        detail = _error_detail("exec.bracket_failed", message, {"phase": phase})
        notes.insert(0, f"bracket phase {phase} failed: {message}; the changes are kept")
    elif new_errors:
        status = "RECOMPUTE_ERROR"
        detail = _error_detail(
            "recompute.failed_objects",
            f"the script left invalid objects: {', '.join(new_errors)}",
            {"objects": new_errors},
        )
    text = "\n".join([summary_text(structured), *notes])
    return {
        "schema": "fcb.result-envelope/1",
        "status": status,  # type: ignore[typeddict-item]
        "detail": detail,  # type: ignore[typeddict-item]
        "structured_content": structured,
        "text": text,
    }
