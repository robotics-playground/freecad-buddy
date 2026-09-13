"""Document lifecycle operations, the opaque-handle registry, and the session workdir.

Mints an opaque ``fcb-doc:<token>`` handle per document and targets every operation by that
handle. A call that omits a required handle, or names a stale or unknown handle, raises
``ValidationError``. A single process-wide lock serializes mutating operations.

This module also owns the session workdir (AD-25): every file the bridge writes on its own
initiative lives under it, so the session-start sweep can reach them.
"""

from __future__ import annotations

import logging
import os
import secrets
import threading
from pathlib import Path
from typing import Callable, TypeVar

from freecad_buddy.contracts import ResultEnvelope, massprops_equal, summary_text

T = TypeVar("T")

logger = logging.getLogger("freecad_buddy.usecases.documents")


class ValidationError(Exception):
    """Caller-facing input validation failure for a document operation."""


# -- session workdir (AD-25) ------------------------------------------------------------

_WORKDIR_ENV = "FREECAD_BUDDY_WORKDIR"
_DEFAULT_WORKDIR = "freecad-buddy-workdir"


def workdir_root() -> Path:
    """The session workdir root, from ``FREECAD_BUDDY_WORKDIR`` or a cwd-relative default.

    Follows the ``FREECAD_BUDDY_AUDIT_LOG`` precedent: an operator overrides the location by
    environment variable, and the default is cwd-relative so no absolute path is baked in.
    """
    return Path(os.environ.get(_WORKDIR_ENV, _DEFAULT_WORKDIR))


def temp_dir() -> str:
    """The session temp directory (``<workdir>/tmp``), created on demand.

    Every temp file the bridge creates is passed this as ``dir=``, which is what puts it inside
    the tree :func:`sweep_temp_dir` owns. A creation failure is the caller's to report — a temp
    file that cannot be placed inside the workdir must not silently fall back to the OS temp
    directory, because nothing would then sweep it.
    """
    path = workdir_root() / "tmp"
    path.mkdir(parents=True, exist_ok=True)
    return str(path)


def sweep_temp_dir() -> int:
    """Remove the previous session's temp files from ``<workdir>/tmp``; return the count removed.

    Runs once at session start, never as an immediate unlink: a render link may still be being
    read when the call that returned it completes. The scope is exactly ``<workdir>/tmp`` — the OS
    temp directory is another session's territory and is never scanned.

    Only regular files and the bridge's own snapshot directories are removed; the walk is one
    level deep, so no path outside the workdir can be reached. An in-memory FreeCAD document
    carrying a reserved ``FCB_TMP_`` name can never appear here, because this reads a real
    directory and a document is not a directory entry.

    Every failure is logged and skipped rather than raised: one locked file must not keep the rest
    of the previous session's leftovers alive, and an unreadable workdir must not stop a host from
    starting — the leftovers simply stay for the next start to retry.
    """
    root = workdir_root() / "tmp"
    removed = 0
    try:
        entries = list(root.iterdir()) if root.is_dir() else []
    except OSError:
        logger.warning("session sweep could not read %s", root, exc_info=True)
        return 0
    for entry in entries:
        try:
            if entry.is_dir():
                for child in entry.iterdir():
                    child.unlink()
                entry.rmdir()
            else:
                entry.unlink()
            removed += 1
        except OSError:
            logger.warning("session sweep could not remove %s", entry, exc_info=True)
    return removed


def _ok_envelope(structured: dict, summary: str | None = None) -> ResultEnvelope:
    return {
        "schema": "fcb.result-envelope/1",
        "status": "OK",
        "detail": None,
        "structured_content": structured,
        "text": summary if summary is not None else summary_text(structured),
    }


def summarize_document_list(sc: dict) -> str:
    """One-line summary of open documents: count and labels."""
    docs = sc.get("documents") or []
    labels = ", ".join(d.get("label", "?") for d in docs)
    suffix = f": {labels}" if labels else ""
    return f"{len(docs)} open document(s){suffix}."


def summarize_document_open(sc: dict) -> str:
    """One-line summary of a document_open result."""
    return f"Opened {sc.get('label', sc.get('name', '?'))} -> {sc.get('doc', '?')}."


def summarize_document_save(sc: dict) -> str:
    """One-line summary of a document_save result."""
    return f"Saved {sc.get('name', '?')} (doc={sc.get('doc', '?')})."


def summarize_document_close(sc: dict) -> str:
    """One-line summary of a document_close result."""
    return f"Closed {sc.get('name', '?')} (doc={sc.get('doc', '?')})."


def summarize_document_undo(sc: dict) -> str:
    """One-line summary of a document_undo result: what was undone and whether it restored."""
    matches = sc.get("matches_pre_op")
    if matches is None:
        verdict = "no pre-op digest supplied to compare against"
    else:
        verdict = "restored the pre-op state" if matches else "did NOT restore the pre-op state"
    return (
        f"Undid {sc.get('undone')!r} on {sc.get('name', '?')}: {verdict} "
        f"({str(sc.get('fingerprint_before'))[:12]} -> "
        f"{str(sc.get('fingerprint_after'))[:12]})."
    )


def summarize_document_recompute(sc: dict) -> str:
    """One-line summary of a document_recompute result."""
    errors = sc.get("errors") or []
    touched = sc.get("touched", 0)
    if errors:
        names = ", ".join(e.get("name", "?") for e in errors)
        return f"Recompute {sc.get('name', '?')}: {len(errors)} error(s): {names}."
    return f"Recompute {sc.get('name', '?')}: clean, {touched} object(s) touched."


# FreeCAD marks a failed object with "Invalid"/"Error" in obj.State; an object still "Touched"
# after a full recompute was silently skipped (its dependencies never resolved) — also an error.
_RECOMPUTE_ERROR_STATES = frozenset({"Invalid", "Error", "Touched"})


def _recompute_error_state(state: list) -> bool:
    """Whether an object's post-recompute ``State`` list indicates it did not compute cleanly."""
    return any(token in _RECOMPUTE_ERROR_STATES for token in state)


def _matches_pre_op(after: dict, expected: str | dict | None) -> bool | None:
    """Whether ``after`` reaches ``expected``; ``None`` when the caller supplied no expectation.

    A digest string is compared byte-exactly. A whole ``FingerprintRecord`` also passes when the
    per-object geometric invariants match, because consuming a shape as a profile makes OCCT
    store its edges several ways and an undo removes the feature without dropping the extra
    representations — the bytes then differ while volume, area, centre of mass and principal
    moments do not.
    """
    if expected is None:
        return None
    if isinstance(expected, str):
        return after["digest"] == expected
    return after["digest"] == expected.get("digest") or massprops_equal(after, expected)


def _recompute_error_envelope(structured: dict, errors: list) -> ResultEnvelope:
    """A ``RECOMPUTE_ERROR`` envelope naming every object left in an error state."""
    names = [entry["name"] for entry in errors]
    return {
        "schema": "fcb.result-envelope/1",
        "status": "RECOMPUTE_ERROR",
        "detail": {
            "code": "recompute.failed_objects",
            "message": "; ".join(f"{e['name']}: {e['error']}" for e in errors),
            "objects": names,
        },
        "structured_content": structured,
        "text": summarize_document_recompute(structured),
    }


class DocumentRegistry:
    """Maps opaque session handles to live FreeCAD ``App.Document`` objects.

    The handle is a session token, never the FreeCAD ``Name``. A single lock serializes every
    mutating operation.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._by_handle: dict[str, object] = {}
        self._transient: dict[str, bool] = {}

    # -- handle helpers -----------------------------------------------------------------

    def _mint_handle(self) -> str:
        return f"fcb-doc:{secrets.token_urlsafe(16)}"

    def _resolve(self, doc: str | None) -> tuple[str, object]:
        """Return ``(handle, App.Document)`` for a caller-supplied handle, or raise.

        A missing handle or a stale/unknown handle both raise ``ValidationError``.
        """
        if not doc:
            raise ValidationError("missing required 'doc' handle")
        document = self._by_handle.get(doc)
        if document is None:
            raise ValidationError(f"unknown or stale document handle: {doc}")
        return doc, document

    def with_document(self, doc: str | None, fn: Callable[[str, object], T]) -> T:
        """Resolve ``doc`` and run ``fn(handle, document)`` while holding the registry lock."""
        with self._lock:
            handle, document = self._resolve(doc)
            return fn(handle, document)

    def rebind(self, doc: str | None, document: object) -> None:
        """Point ``doc`` at ``document``, replacing whatever object the handle held.

        The snapshot-restore rollback path closes the original document and reopens it from the
        snapshot, so the object a handle holds can be dead by the time a mutation returns. Every
        mutation tool call site rebinds the document ``run_mutation`` returned. Rebinding to the
        object the handle already holds is a no-op.

        :raises ValidationError: ``doc`` is missing, unknown, or stale.
        """
        with self._lock:
            handle, existing = self._resolve(doc)
            if existing is document:
                return
            self._by_handle[handle] = document

    def _handle_for(self, document: object) -> str | None:
        """Return an existing handle already bound to ``document``, or ``None``."""
        for handle, existing in self._by_handle.items():
            if existing is document:
                return handle
        return None

    # -- lifecycle ops (each returns a ResultEnvelope) ----------------------------------

    def document_create(self, label: str, path: str | None = None) -> ResultEnvelope:
        """Create a new document, mint and return its handle."""
        import FreeCAD

        if not label:
            raise ValidationError("document_create requires a non-empty 'label'")
        with self._lock:
            try:
                document = FreeCAD.newDocument(label)
            except Exception as exc:
                raise ValidationError(f"document_create failed for label {label!r}: {exc}") from exc
            try:
                document.Label = label
                if path:
                    document.saveAs(path)
                handle = self._mint_handle()
                self._by_handle[handle] = document
                self._transient[handle] = path is None
            except Exception:
                # Never leave a created document untracked if post-create bookkeeping fails.
                FreeCAD.closeDocument(document.Name)
                raise
            structured = {
                "doc": handle,
                "name": document.Name,
                "label": document.Label,
            }
            return _ok_envelope(structured)

    def document_open(self, path: str) -> ResultEnvelope:
        """Open an ``.FCStd`` file and return its handle.

        Opening a path whose document is already tracked reuses the existing handle rather
        than minting a second handle for the same document.
        """
        import FreeCAD

        if not path:
            raise ValidationError("document_open requires a 'path'")
        with self._lock:
            try:
                document = FreeCAD.openDocument(path)
            except Exception as exc:
                raise ValidationError(f"document_open failed for {path!r}: {exc}") from exc
            existing = self._handle_for(document)
            if existing is not None:
                handle = existing
            else:
                handle = self._mint_handle()
                self._by_handle[handle] = document
                self._transient[handle] = False
            structured = {
                "doc": handle,
                "name": document.Name,
                "label": document.Label,
                "path": path,
            }
            return _ok_envelope(structured, summarize_document_open(structured))

    def document_save(self, doc: str | None = None, path: str | None = None) -> ResultEnvelope:
        """Save (or save-as) the document named by ``doc``."""
        with self._lock:
            handle, document = self._resolve(doc)
            if path:
                document.saveAs(path)
                self._transient[handle] = False
            else:
                if self._transient.get(handle, False):
                    raise ValidationError(
                        "document has no save target; call document_save with a 'path' first"
                    )
                document.save()
            structured = {"doc": handle, "name": document.Name, "saved": True}
            return _ok_envelope(structured, summarize_document_save(structured))

    def document_close(self, doc: str | None = None) -> ResultEnvelope:
        """Close the document named by ``doc`` and release every handle bound to it."""
        import FreeCAD

        with self._lock:
            handle, document = self._resolve(doc)
            name = document.Name
            FreeCAD.closeDocument(name)
            for alias in [h for h, d in self._by_handle.items() if d is document]:
                del self._by_handle[alias]
                self._transient.pop(alias, None)
            structured = {"doc": handle, "name": name, "closed": True}
            return _ok_envelope(structured, summarize_document_close(structured))

    def document_recompute(self, doc: str | None = None) -> ResultEnvelope:
        """Full recompute; report per-object error states and fail on any error.

        An object left in an error state ("Invalid"/"Error" in ``State``, or still "Touched"
        after the recompute — a silent skip) is reported. When any error is present the envelope
        status is ``RECOMPUTE_ERROR``; a clean recompute is ``OK``.
        """
        with self._lock:
            handle, document = self._resolve(doc)
            touched = document.recompute()
            errors = [
                {"name": obj.Name, "error": state}
                for obj in document.Objects
                for state in [list(getattr(obj, "State", None) or [])]
                if _recompute_error_state(state)
            ]
            structured = {
                "doc": handle,
                "name": document.Name,
                "touched": int(touched) if touched is not None else 0,
                "errors": errors,
            }
            if errors:
                return _recompute_error_envelope(structured, errors)
            return _ok_envelope(structured, summarize_document_recompute(structured))

    def document_undo(
        self, doc: str | None = None, expect_fingerprint: str | dict | None = None
    ) -> ResultEnvelope:
        """Undo the last committed transaction, recompute, and report the fingerprint comparison.

        Refuses when the build reports undo unavailable on the document, and when the undo stack
        is empty — ``Document.undo()`` is a silent no-op in both cases, so an unchecked call would
        report a successful undo that never happened. ``UndoCount`` is read here rather than
        inside a mutation bracket, where it would also count the open transaction.

        The recompute after the undo is mandatory: undo replays property deltas and leaves the
        objects it touched dirty without recomputing them, so a fingerprint taken before it would
        read stale shapes.

        Restoration is reported, never assumed. ``fingerprint_before`` is the state this call
        found, ``fingerprint_after`` the state it left. When the caller supplies
        ``expect_fingerprint`` — the digest the document carried before the mutation being undone
        — ``matches_pre_op`` states whether the undo actually reached it; without one it is
        ``None``, because this call never saw the pre-mutation state.

        ``restored_objects`` reports the object set the undo left, so a digest mismatch caused by
        OCCT re-serializing an untouched shape can be told apart from one caused by an object the
        undo failed to remove or restore.

        The mandatory recompute is swept for error states exactly as ``document_recompute`` sweeps
        its own: an undo that left an object invalid is ``RECOMPUTE_ERROR``, never an ``OK`` whose
        digest happens not to match.

        :param expect_fingerprint: the pre-mutation digest string, or the whole
            ``FingerprintRecord``, to compare the result against. A record also matches on the
            per-object geometric invariants, so an op that changed a shape's serialization
            without changing its geometry still reports the undo as restoring.
        :raises ValidationError: ``doc`` is missing or stale, ``expect_fingerprint`` is neither a
            digest string nor a record carrying an ``objects`` list, undo is unavailable on the
            document, or there is nothing to undo.
        """
        from freecad_buddy.usecases import shim
        from freecad_buddy.usecases.fingerprint import fingerprint

        # An expectation of any other type can never equal a digest and carries no comparable
        # geometry, so accepting one would report matches_pre_op: false — "the undo did not
        # restore" — for what is a caller type error.
        if expect_fingerprint is not None and not isinstance(expect_fingerprint, (str, dict)):
            raise ValidationError(
                "expect_fingerprint must be a fingerprint digest string or a FingerprintRecord, "
                f"got {type(expect_fingerprint).__name__}"
            )
        if isinstance(expect_fingerprint, dict) and not isinstance(
            expect_fingerprint.get("objects"), list
        ):
            raise ValidationError(
                "expect_fingerprint record must carry an 'objects' list; got keys "
                f"{sorted(expect_fingerprint)}"
            )

        with self._lock:
            handle, document = self._resolve(doc)
            if not shim.enable_undo(document):
                raise ValidationError(
                    f"undo is unavailable on {document.Name}: the document reports UndoMode 0"
                )
            # An open transaction (one the GUI, a macro, or another workbench left running —
            # this bridge always closes its own) makes both readings wrong: getAvailableUndoNames
            # prepends it (Document.cpp:318-330) and getAvailableUndos counts it
            # (Document.cpp:791-794), while undo() commits it first and then reverts the
            # transaction *below* it (Document.cpp:188-195). Undoing here would revert a
            # different transaction than the one reported. Refuse instead of guessing.
            if getattr(document, "HasPendingTransaction", False):
                raise ValidationError(
                    f"{document.Name} has an open transaction; undo would commit it and revert "
                    "the transaction beneath it. Commit or abort it first."
                )
            # UndoNames is most-recent-first, so the transaction undo() reverts is names[0].
            names = list(getattr(document, "UndoNames", None) or [])
            if int(getattr(document, "UndoCount", 0) or 0) < 1:
                raise ValidationError(
                    f"nothing to undo on {document.Name}: the undo stack is empty"
                )

            before = fingerprint(document)
            document.undo()
            document.recompute()
            after = fingerprint(document)

            # The recompute after the undo can leave objects invalid, and this call reports
            # restoration as a measured result. Reporting OK for that would present a broken
            # document as an undo whose digest merely happened not to match, so the same sweep
            # document_recompute runs decides the status here too.
            errors = [
                {"name": obj.Name, "error": state}
                for obj in document.Objects
                for state in [list(getattr(obj, "State", None) or [])]
                if _recompute_error_state(state)
            ]

            structured = {
                "doc": handle,
                "name": document.Name,
                "undone": names[0] if names else None,
                "fingerprint_before": before["digest"],
                "fingerprint_after": after["digest"],
                "matches_pre_op": _matches_pre_op(after, expect_fingerprint),
                # Read from the document, not from the fingerprint: fingerprint() skips every
                # shape-less object (an Origin, a Body, a datum, an empty Sketch), and those are
                # exactly the ones a caller asks this list about after an undo.
                "restored_objects": [obj.Name for obj in document.Objects],
                "undo_count": int(getattr(document, "UndoCount", 0) or 0),
                "errors": errors,
            }
            if errors:
                return _recompute_error_envelope(structured, errors)
            return _ok_envelope(structured, summarize_document_undo(structured))

    def document_list(self) -> ResultEnvelope:
        """List every open FreeCAD document with handle, name, label, and transient flag.

        Documents opened directly in the GUI (not through the bridge) are adopted here: each is
        given a handle on first sight so it is addressable by later tool calls, while documents
        the bridge already tracks keep their existing handle.
        """
        import FreeCAD

        with self._lock:
            self._prune_closed()
            for document in FreeCAD.listDocuments().values():
                if self._handle_for(document) is None:
                    handle = self._mint_handle()
                    self._by_handle[handle] = document
                    self._transient[handle] = False
            documents = [
                {
                    "doc": handle,
                    "name": document.Name,
                    "label": document.Label,
                    "transient": self._transient.get(handle, False),
                }
                for handle, document in self._by_handle.items()
            ]
            structured = {"documents": documents}
            return _ok_envelope(structured, summarize_document_list(structured))

    def _prune_closed(self) -> None:
        """Drop handles whose FreeCAD document has been closed (best-effort; lock held)."""
        import FreeCAD

        live = set(FreeCAD.listDocuments().values())
        for handle in [h for h, d in self._by_handle.items() if d not in live]:
            self._by_handle.pop(handle, None)
            self._transient.pop(handle, None)
