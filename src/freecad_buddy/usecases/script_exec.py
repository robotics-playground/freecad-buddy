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

_UNDO_UNAVAILABLE_NOTE = (
    "undo is unavailable on this document: document_undo cannot revert this call"
)
_NO_UNDO_STEP_NOTE = (
    "undo_steps 0: this call recorded no undo step, so document_undo would revert an earlier step"
)


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


def _added_undo_steps(before: list[str], after: list[str]) -> int:
    """Count the entries the call added to the most-recent-first undo list.

    A full stack drops its oldest entry for each new one, so the counts alone cannot tell. The
    smallest ``k`` for which ``after[k:]`` is the leading part of ``before`` is the number added.
    Repeated names on a full stack can make that undercount. A script that removed the newest
    entries (``doc.undo()``) leaves ``after`` as the tail of ``before``: nothing was added.
    """
    if len(after) < len(before) and after == before[len(before) - len(after) :]:
        return 0
    for added in range(len(after) + 1):
        remaining = after[added:]
        if remaining == before[: len(remaining)]:
            return added
    return len(after)


def _is_dead(document: object) -> bool:
    try:
        document.Name
    except ReferenceError:
        return True
    return False


def _any_touched(document: object) -> bool:
    return any("Touched" in obj.State for obj in document.Objects)


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
    # The commit runs after a failed recompute too: a transaction left open would take the name
    # of the next change by any caller.
    try:
        document.commitTransaction()
        shim.commit_active_transaction()
    except Exception as exc:  # noqa: BLE001 - the changes stay; report the phase
        return None, failure or ("commit", exc)
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
        invalid_before = {name for name, _status in invalid_objects(document)}
        names_before = list(document.UndoNames)
    except Exception as exc:  # noqa: BLE001 - nothing ran yet; report instead of raising
        message = f"{type(exc).__name__}: {exc}"
        return {
            "schema": "fcb.result-envelope/1",
            "status": "SPEC_FAILED",
            "detail": _error_detail(
                "exec.bracket_failed", message, {"phase": "fingerprint_before"}
            ),
            "structured_content": {},
            "text": f"script not run: fingerprint_before failed: {message}",
        }
    result_projection.remember(before)

    namespace = _script_namespace(document)
    buffer = io.StringIO()
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
    undo_steps = 0
    bracket_failure: tuple[str, Exception] | None = None
    gone = _is_dead(document)
    if gone:
        # closeDocument clears the application-level transaction only when the document held its
        # own, so a script that closed its document before writing leaves the name open.
        shim.commit_active_transaction()
    else:
        after, bracket_failure = _close_bracket(document, recompute)
        try:
            invalid_after = {name for name, _status in invalid_objects(document)}
            new_errors = sorted(invalid_after - invalid_before)
            undo_steps = _added_undo_steps(names_before, list(document.UndoNames))
            changed = result_projection.changed_objects(before, after, False)
        except Exception as exc:  # noqa: BLE001 - the script already ran; report, never raise
            bracket_failure = bracket_failure or ("observe", exc)

    value = namespace.get("result", _UNSET)
    structured = {
        "doc": handle,
        "stdout": buffer.getvalue(),
        "value_repr": repr(value) if value is not _UNSET else None,
        "fingerprint_before": before["digest"],
        "fingerprint_after": after["digest"] if after is not None else None,
        "changed": changed,
        "new_errors": new_errors,
        "undo_steps": undo_steps,
    }
    notes = []
    if gone:
        notes.append(f"the script closed its document {handle}; this handle is now stale")
    elif not undo_enabled:
        notes.append(_UNDO_UNAVAILABLE_NOTE)
    elif undo_steps == 0:
        notes.append(_NO_UNDO_STEP_NOTE)
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
        frames = frames.tb_next or frames if frames is not None else None
        trace = "".join(traceback.format_exception(type(script_error), script_error, frames))
        message = f"{type(script_error).__name__}: {script_error}"
        data = {"exception": type(script_error).__name__, "traceback": trace[-_TRACEBACK_LIMIT:]}
        if bracket_failure is not None:
            data["bracket_phase"] = bracket_failure[0]
        status, detail = "INVALID_INPUT", _error_detail("exec.python_error", message, data)
        notes.insert(0, f"script raised {message}; the changes it made so far are kept")
    elif bracket_failure is not None:
        phase, exc = bracket_failure
        message = f"{type(exc).__name__}: {exc}"
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
