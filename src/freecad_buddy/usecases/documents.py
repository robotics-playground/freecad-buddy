"""Document lifecycle operations and the opaque-handle registry.

Mints an opaque ``fcb-doc:<token>`` handle per document and targets every operation by that
handle. A call that omits a required handle, or names a stale or unknown handle, raises
``ValidationError``. A single process-wide lock serializes mutating operations.
"""

from __future__ import annotations

import secrets
import threading
from typing import Callable, TypeVar

from freecad_buddy.contracts import ResultEnvelope, summary_text

T = TypeVar("T")


class ValidationError(Exception):
    """Caller-facing input validation failure for a document operation."""


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
