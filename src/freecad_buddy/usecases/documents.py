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
import re
import secrets
import shutil
import threading
from pathlib import Path
from typing import Callable, TypeVar

from freecad_buddy.contracts import (
    ResultEnvelope,
    fingerprints_equal,
    massprops_equal,
    summary_text,
)
from freecad_buddy.usecases.process import pid_alive

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


_TEMP_PREFIX = "FCB_TMP_"
# Pid plus a per-process token: a recycled pid can never name a folder an earlier process left.
_SESSION_DIR = re.compile(rf"{_TEMP_PREFIX}session_(\d{{1,10}})_[0-9a-f]+")
_SESSION_TOKEN = secrets.token_hex(4)


def temp_dir() -> str:
    """This host's session temp directory, ``<workdir>/tmp/FCB_TMP_session_<pid>_<token>``.

    Every temp file the bridge creates is passed this as ``dir=``, which is what puts it inside
    the tree :func:`sweep_temp_dir` owns. Each host process gets its own folder because a GUI and
    a headless host can share one workdir, and a sweep must tell a live host's files from a dead
    one's. A creation failure is the caller's to report — a temp file that cannot be placed inside
    the workdir must not silently fall back to the OS temp directory, because nothing would then
    sweep it.
    """
    path = workdir_root() / "tmp" / f"{_TEMP_PREFIX}session_{os.getpid()}_{_SESSION_TOKEN}"
    path.mkdir(parents=True, exist_ok=True)
    return str(path)


def sweep_temp_dir() -> int:
    """Remove dead sessions' temp files from ``<workdir>/tmp``; return the count removed.

    Runs once at session start, never as an immediate unlink: a render link may still be being
    read when the call that returned it completes. The scope is exactly ``<workdir>/tmp`` — the OS
    temp directory is another session's territory and is never scanned.

    Only ``FCB_TMP_`` entries are touched; anything else in the folder belongs to someone else. A
    session folder is removed only when the pid in its name is dead, so a live host sharing the
    workdir keeps its files. Any other ``FCB_TMP_`` entry sits outside every session folder, so no
    live host owns it. An in-memory FreeCAD document carrying a reserved ``FCB_TMP_`` name can
    never appear here, because this reads a real directory and a document is not a directory
    entry.

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
        if not entry.name.startswith(_TEMP_PREFIX):
            continue
        session = _SESSION_DIR.fullmatch(entry.name)
        if session is not None and pid_alive(int(session.group(1))):
            continue
        try:
            if entry.is_dir() and not entry.is_symlink():
                shutil.rmtree(entry)
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
    """One-line summary of a document_save result: the label and path the save left."""
    return (
        f"Saved {sc.get('name', '?')} as {sc.get('label', '?')!r} to {sc.get('path', '?')} "
        f"(doc={sc.get('doc', '?')})."
    )


def summarize_document_close(sc: dict) -> str:
    """One-line summary of a document_close result."""
    return f"Closed {sc.get('name', '?')} (doc={sc.get('doc', '?')})."


def summarize_document_undo(sc: dict, digest_only: bool = False) -> str:
    """One-line summary of a document_undo result: what was undone and whether it restored.

    ``digest_only`` marks a string expectation. A byte difference alone does not show the undo
    failed — re-serializing an untouched shape changes the bytes too — so that mismatch is
    reported as the measurement it is, never as a failed restore.
    """
    matches = sc.get("matches_pre_op")
    if matches is None:
        verdict = "no pre-op digest supplied to compare against"
    elif matches:
        verdict = "restored the pre-op state"
    elif digest_only:
        verdict = (
            "the digest differs from the expected one on byte comparison; pass the whole "
            "FingerprintRecord as expect_fingerprint to also compare the geometry"
        )
    else:
        verdict = "did NOT restore the pre-op state"
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
    representations — the bytes then differ while volume, area, centre of mass, principal
    moments and inertia tensor do not.
    """
    if expected is None:
        return None
    if isinstance(expected, str):
        return after["digest"] == expected
    return after["digest"] == expected.get("digest") or massprops_equal(after, expected)


_DIGEST = re.compile(r"[0-9a-f]{64}")


def _check_expectation(expected: object, serializer: str) -> None:
    """Refuse an ``expect_fingerprint`` that cannot be compared with this build's fingerprint.

    An incomparable expectation can never match, so accepting one would report
    ``matches_pre_op: false`` — "the undo did not restore" — for what is a caller error.

    :raises ValidationError: naming the first defect found.
    """
    if isinstance(expected, str):
        if not _DIGEST.fullmatch(expected):
            raise ValidationError(
                f"expect_fingerprint digest must be 64 lowercase hex characters, got {expected!r}"
            )
        return
    if not isinstance(expected, dict):
        raise ValidationError(
            "expect_fingerprint must be a fingerprint digest string or a FingerprintRecord, "
            f"got {type(expected).__name__}"
        )
    if not isinstance(expected.get("objects"), list):
        raise ValidationError(
            f"expect_fingerprint record must carry an 'objects' list; got keys {sorted(expected)}"
        )
    try:
        fingerprints_equal(expected, {"serializer": serializer, "digest": ""})
    except ValueError as exc:
        raise ValidationError(f"expect_fingerprint record: {exc}") from exc
    if not isinstance(expected["digest"], str):
        raise ValidationError(
            "expect_fingerprint record digest must be a string, got "
            f"{type(expected['digest']).__name__}"
        )
    for index, entry in enumerate(expected["objects"]):
        if not (
            isinstance(entry, dict)
            and isinstance(entry.get("name"), str)
            and isinstance(entry.get("massprops"), dict)
        ):
            raise ValidationError(
                f"expect_fingerprint record objects[{index}] must carry a 'name' string and a "
                f"'massprops' object, got {entry!r}"
            )


def _fcstd_path(path: str) -> str:
    """The file ``Document.saveAs(path)`` writes: FreeCAD appends ``.FCStd`` when it is missing.

    Mirrors ``checkFileName`` (``App/Document.cpp:1677-1696``), including its
    ``CheckExtension`` preference, so the target checked is the file FreeCAD will open.
    """
    import FreeCAD

    preferences = FreeCAD.ParamGet("User parameter:BaseApp/Preferences/Document")
    if not preferences.GetBool("CheckExtension", True) or path.lower().endswith(".fcstd"):
        return path
    return path + ("FCStd" if path.endswith(".") else ".FCStd")


def _check_save_target(path: str) -> None:
    """Refuse a save target FreeCAD would mishandle, before anything is written.

    FreeCAD saves to a directory path as ``<dir>.FCStd``, creates a missing parent folder, and
    sets the document's ``FileName`` before it finds a read-only target, so each is refused here.

    :raises ValidationError: naming the bad path or folder.
    """
    if os.path.isdir(path):
        raise ValidationError(f"save path is a directory, not a file: {path}")
    target = _fcstd_path(path)
    folder = os.path.dirname(os.path.abspath(target))
    if not os.path.isdir(folder):
        raise ValidationError(f"save folder does not exist: {folder}")
    if os.path.isdir(target):
        raise ValidationError(f"save path is a directory, not a file: {target}")
    if os.path.exists(target) and not os.access(target, os.W_OK):
        raise ValidationError(f"save target is not writable: {target}")


def _save_as(document: object, path: str) -> None:
    """``saveAs`` with a file-system failure reported as invalid input naming the path.

    ``Document::saveAs`` sets ``FileName`` and ``Label`` before it writes
    (``App/Document.cpp:1704-1710``), so a failed write would leave the document renamed to a
    file that does not exist; both are put back before the refusal is raised.
    """
    file_name, label = document.FileName, document.Label
    try:
        document.saveAs(path)
    except OSError as exc:
        document.FileName = file_name
        document.Label = label
        raise ValidationError(f"cannot save to {path}: {exc}") from exc


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

    def _lookup(self, doc: str | None) -> tuple[str, object]:
        """Return ``(handle, bound object)`` for a caller-supplied handle, without probing it.

        A missing handle or an unknown handle both raise ``ValidationError``.
        """
        if not doc:
            raise ValidationError("missing required 'doc' handle")
        document = self._by_handle.get(doc)
        if document is None:
            raise ValidationError(f"unknown or stale document handle: {doc}")
        return doc, document

    def _resolve(self, doc: str | None) -> tuple[str, object]:
        """Return ``(handle, App.Document)`` for a caller-supplied handle, or raise.

        A missing, unknown, or stale handle raises ``ValidationError``. A document closed outside
        the registry — the GUI's File > Close — leaves a dead object behind its handle, and the
        first attribute read on it raises ``ReferenceError``; every alias of it is dropped then.
        """
        handle, document = self._lookup(doc)
        try:
            document.Name
        except ReferenceError:
            self._release(document)
            raise ValidationError(f"unknown or stale document handle: {doc}") from None
        return handle, document

    def _release(self, document: object) -> None:
        """Drop every handle bound to ``document`` (lock held)."""
        for alias in [h for h, d in self._by_handle.items() if d is document]:
            del self._by_handle[alias]
            self._transient.pop(alias, None)

    def with_document(self, doc: str | None, fn: Callable[[str, object], T]) -> T:
        """Resolve ``doc`` and run ``fn(handle, document)`` while holding the registry lock."""
        with self._lock:
            handle, document = self._resolve(doc)
            return fn(handle, document)

    def rebind(self, doc: str | None, document: object) -> None:
        """Point ``doc`` at ``document``, replacing whatever object the handle held.

        The snapshot-restore rollback path closes the original document and reopens it from the
        snapshot, so the object a handle holds can be dead by the time a mutation returns. Every
        mutation tool call site rebinds the document ``run_mutation`` returned. Every alias of the
        replaced object moves with ``doc``, so none stays on the dead original. Rebinding to the
        object the handle already holds is a no-op. The bound object is not probed, because it
        may be exactly that dead original.

        :raises ValidationError: ``doc`` is missing or unknown.
        """
        with self._lock:
            _, existing = self._lookup(doc)
            if existing is document:
                return
            for alias in [h for h, d in self._by_handle.items() if d is existing]:
                self._by_handle[alias] = document

    def _handle_for(self, document: object) -> str | None:
        """Return an existing handle already bound to ``document``, or ``None``."""
        for handle, existing in self._by_handle.items():
            if existing is document:
                return handle
        return None

    # -- lifecycle ops (each returns a ResultEnvelope) ----------------------------------

    def document_create(self, label: str, path: str | None = None) -> ResultEnvelope:
        """Create a new document, mint and return its handle.

        With a ``path`` the document is saved there at once, and FreeCAD renames its ``Label``
        to the file stem as GUI Save As does; the result reports that label and the file path.
        """
        import FreeCAD

        if not label:
            raise ValidationError("document_create requires a non-empty 'label'")
        if path:
            _check_save_target(path)
        with self._lock:
            try:
                document = FreeCAD.newDocument(label)
            except Exception as exc:
                raise ValidationError(f"document_create failed for label {label!r}: {exc}") from exc
            try:
                document.Label = label
                if path:
                    _save_as(document, path)
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
            if path:
                structured["path"] = document.FileName
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
        """Save (or save-as) the document named by ``doc``.

        A save-as renames the document's ``Label`` to the file stem, as GUI Save As does, and
        FreeCAD appends ``.FCStd`` to a path without it; the result reports both as they are.
        """
        with self._lock:
            handle, document = self._resolve(doc)
            if path:
                _check_save_target(path)
                _save_as(document, path)
                self._transient[handle] = False
            else:
                if self._transient.get(handle, False):
                    raise ValidationError(
                        "document has no save target; call document_save with a 'path' first"
                    )
                try:
                    document.save()
                except OSError as exc:
                    raise ValidationError(f"cannot save to {document.FileName}: {exc}") from exc
            structured = {
                "doc": handle,
                "name": document.Name,
                "label": document.Label,
                "path": document.FileName,
                "saved": True,
            }
            return _ok_envelope(structured, summarize_document_save(structured))

    def document_close(self, doc: str | None = None) -> ResultEnvelope:
        """Close the document named by ``doc`` and release every handle bound to it."""
        import FreeCAD

        with self._lock:
            handle, document = self._resolve(doc)
            name = document.Name
            FreeCAD.closeDocument(name)
            self._release(document)
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
        :raises ValidationError: ``doc`` is missing or stale, ``expect_fingerprint`` is not a
            64-hex digest string or a record comparable with this build's fingerprint, undo is
            unavailable on the document, or there is nothing to undo.
        """
        from freecad_buddy.usecases import shim
        from freecad_buddy.usecases.fingerprint import fingerprint

        if expect_fingerprint is not None:
            _check_expectation(expect_fingerprint, shim.serializer_tag())

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
            return _ok_envelope(
                structured,
                summarize_document_undo(structured, isinstance(expect_fingerprint, str)),
            )

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
