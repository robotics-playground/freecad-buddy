"""The uniform mutation protocol: ``run_mutation()`` and ``post_verify()``.

``run_mutation(doc, op)`` is the only path a mutation executes through. Outside the transaction
it fingerprints the document, snapshots its references and writes a ``saveCopy`` snapshot to a
reserved-prefix temp path. It then opens one transaction (never nested, never left open), applies
the op, recomputes, and runs ``post_verify``. On pass it commits and deletes the snapshot; on
failure or exception it aborts, recomputes, and proves restoration by re-hashing — escalating to
restoring the snapshot when the hash does not match.

Takes the already-resolved ``App.Document`` object, never a handle: ``DocumentRegistry
.with_document`` holds a non-reentrant lock, so re-resolving inside the callback would deadlock.
Stdlib + FreeCAD App API only.
"""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from typing import Callable

from freecad_buddy.contracts import (
    FingerprintRecord,
    MutationBlock,
    PostVerifyBlock,
    ResultEnvelope,
    RollbackProof,
    TerminalStatus,
    TnpAuditBlock,
    fingerprints_equal,
)
from freecad_buddy.usecases import shim, tnp_guard, verify
from freecad_buddy.usecases.documents import ValidationError
from freecad_buddy.usecases.fingerprint import fingerprint

_SNAPSHOT_PREFIX = "FCB_TMP_snap_"

# The Python ``Document.openTransaction(name)`` binding exposes only the name; the C++ ``tid``
# defaults to the null transaction, so the fresh single-document id is implicit and cross-document
# grouping is never requested (App/DocumentPyImp.cpp openTransaction).
_TRANSACTION_ID = "0"


def _params_digest(params: dict) -> str:
    """Return the SHA-256 digest of ``params``, matching the audit sink's ``params_digest``.

    The serialization is byte-identical to ``adapters/audit_log._digest`` so a mutation block and
    its audit lines carry the same digest for the same arguments; ``default=repr`` keeps a
    non-JSON-serializable argument from raising.
    """
    payload = json.dumps(params, sort_keys=True, ensure_ascii=False, default=repr).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


class RollbackNotProven(RuntimeError):
    """Raised when neither abort nor snapshot restore reproduces the pre-mutation fingerprint.

    Carries the document the restore attempt left open in ``document``: the snapshot restore closes
    and reopens the document, so the caller's original object is dead by the time this raises and
    only this one can still be read.
    """

    def __init__(self, message: str, document: object) -> None:
        super().__init__(message)
        self.document = document


class _ResolvedRegistry:
    """A ``DocumentRegistry``-shaped façade over one already-resolved document, holding no lock.

    ``verify_shape``/``verify_sketch`` take a registry and call ``with_document``; the real
    registry's lock is already held by the caller that resolved this document, so re-entering it
    would deadlock. This runs the callback directly on the resolved document instead.
    """

    def __init__(self, handle: str, document: object) -> None:
        self._handle = handle
        self._document = document

    def with_document(self, _doc: str | None, fn: Callable[[str, object], object]) -> object:
        return fn(self._handle, self._document)


def temp_snapshot_path(doc: object) -> str:
    """Return a reserved-prefix temp path for ``doc``'s pre-mutation ``saveCopy`` snapshot.

    The path names a file that does not yet exist, inside a freshly created private temp
    directory. Pre-creating the file would make ``saveCopy`` treat it as an existing document and
    write a sibling ``.FCBak`` backup, which nothing would then clean up.
    """
    directory = tempfile.mkdtemp(prefix=_SNAPSHOT_PREFIX)
    return os.path.join(directory, f"{doc.Name}.FCStd")


def _delete_snapshot(path: str) -> None:
    """Remove the snapshot file and its private temp directory, tolerating an absent path.

    Only a directory this module minted is emptied: the whole-directory removal exists to catch the
    sibling files ``saveCopy`` writes, so a path outside a reserved-prefix directory is left alone
    rather than having its contents deleted.
    """
    directory = os.path.dirname(path)
    if not os.path.basename(directory).startswith(_SNAPSHOT_PREFIX):
        try:
            os.remove(path)
        except OSError:
            pass
        return
    try:
        for name in os.listdir(directory):
            os.remove(os.path.join(directory, name))
        os.rmdir(directory)
    except OSError:
        pass


def _passed(envelope: dict) -> bool:
    """Whether a ``verify_*`` envelope reports a pass: ``OK`` status and no error detail."""
    return envelope.get("status") == "OK" and envelope.get("detail") is None


def _shape_bearing(document: object, names: list[str]) -> list[str]:
    """Return the subset of ``names`` whose object carries a non-null ``Shape``."""
    bearing = []
    for name in names:
        obj = document.getObject(name)
        shape = getattr(obj, "Shape", None)
        is_null = getattr(shape, "isNull", None)
        if shape is not None and not (is_null is not None and is_null()):
            bearing.append(name)
    return bearing


def _sketches(document: object, names: list[str]) -> list[str]:
    """Return the subset of ``names`` whose object is a Sketcher object."""
    return [
        name
        for name in names
        if str(getattr(document.getObject(name), "TypeId", "")).startswith("Sketcher::")
    ]


def _invalid_objects(document: object, touched: list[str]) -> list[tuple[str, str]]:
    """Return ``(name, status)`` for every object failing ``isValid()``.

    A sketch the op touched whose sole invalidity is redundant constraints is not reported:
    FreeCAD marks it invalid, while redundancy is only a warning, so the sketch check below owns
    that verdict. The deferral is limited to touched sketches — an untouched invalid object must
    still block the commit, because no later step grades it.
    """
    invalid = []
    graded = set(touched)
    for obj in sorted(document.Objects, key=lambda o: o.Name):
        if obj.isValid():
            continue
        if obj.Name in graded and shim.redundant_only_sketch(obj):
            continue
        getter = getattr(obj, "getStatusString", None)
        invalid.append((obj.Name, str(getter()) if callable(getter) else ""))
    return invalid


def _block(
    recompute_clean: bool,
    is_valid: bool,
    fully_constrained: bool | None,
    tnp_audit: TnpAuditBlock,
    passed: bool,
    explanation: str | None,
) -> PostVerifyBlock:
    return {
        "recompute_clean": recompute_clean,
        "is_valid": is_valid,
        "fully_constrained": fully_constrained,
        "tnp_audit": tnp_audit,
        "passed": passed,
        "explanation": explanation,
    }


def _unrun_tnp_audit() -> TnpAuditBlock:
    """An audit block for a post_verify that short-circuited before the TNP step ran."""
    raw = shim.element_map_version()
    return {
        "status": "UNSUPPORTED" if not shim.element_map_available() else "CLEAN",
        "element_map_version": None if raw is None else str(raw),
        "findings": [],
    }


def post_verify(
    document: object,
    handle: str,
    touched: list[str],
    refs_before: list,
) -> PostVerifyBlock:
    """Run the mutation checklist in order, short-circuiting on the first hard failure.

    The order is (1) recompute clean — no object failing ``isValid()``, collecting
    ``getStatusString()`` per failure; (2) ``verify_shape`` on every shape-bearing object in
    ``touched``; (3) ``verify_sketch`` on every sketch in ``touched``, requiring
    ``FullyConstrained``; (4) ``audit_references`` against ``refs_before``, where any finding
    other than ``RE_BASELINED`` fails. A failing step names its cause in ``explanation``.

    :param document: the already-resolved ``App.Document``.
    :param handle: the caller's document handle, threaded through to the verify reports.
    :param touched: names of the objects the op created or modified.
    :param refs_before: the pre-mutation ``snapshot_references`` result.
    """
    registry = _ResolvedRegistry(handle, document)

    invalid = _invalid_objects(document, touched)
    if invalid:
        explanation = "recompute left {} object(s) invalid: {}".format(
            len(invalid), "; ".join(f"{name}: {status}" for name, status in invalid)
        )
        return _block(False, False, None, _unrun_tnp_audit(), False, explanation)

    for name in _shape_bearing(document, touched):
        try:
            envelope = verify.verify_shape(registry, doc=handle, object=name)
        except ValidationError as exc:
            explanation = f"verify_shape could not grade {name}: {exc}"
            return _block(True, False, None, _unrun_tnp_audit(), False, explanation)
        if not _passed(envelope):
            detail = envelope.get("detail") or {}
            explanation = f"verify_shape failed on {name}: {detail.get('message', '')}"
            return _block(True, False, None, _unrun_tnp_audit(), False, explanation)

    fully_constrained: bool | None = None
    for name in _sketches(document, touched):
        try:
            envelope = verify.verify_sketch(registry, doc=handle, sketch=name)
        except ValidationError as exc:
            explanation = f"verify_sketch could not grade {name}: {exc}"
            return _block(True, True, None, _unrun_tnp_audit(), False, explanation)
        subject = (envelope.get("structured_content") or {}).get("subject") or {}
        # Every sketch the op touched must be constrained, so the block reports the conjunction
        # rather than whichever sketch the loop happened to inspect last.
        constrained = bool(subject.get("fully_constrained"))
        fully_constrained = constrained if fully_constrained is None else (
            fully_constrained and constrained
        )
        if not _passed(envelope):
            detail = envelope.get("detail") or {}
            explanation = (
                f"verify_sketch failed on {name} "
                f"(dof={subject.get('dof')}): {detail.get('message', '')}"
            )
            return _block(True, True, fully_constrained, _unrun_tnp_audit(), False, explanation)

    audit = tnp_guard.audit_references(document, refs_before)
    failing = [f for f in audit["findings"] if f["verdict"] not in ("PASS", "RE_BASELINED")]
    if audit["status"] == "FLAGGED" and failing:
        explanation = "TNP audit flagged {} reference(s): {}".format(
            len(failing),
            "; ".join(f"{f['owner']}.{f['prop']} {f['verdict']}" for f in failing),
        )
        return _block(True, True, fully_constrained, audit, False, explanation)

    return _block(True, True, fully_constrained, audit, True, None)


def _rollback_status(block: PostVerifyBlock) -> TerminalStatus:
    """Map a failed ``post_verify`` block to its closed-set status.

    A recompute that left an object invalid classes as ``RECOMPUTE_ERROR``; every other failing
    check is a specification failure.
    """
    return "RECOMPUTE_ERROR" if not block["recompute_clean"] else "SPEC_FAILED"


def _restore_from_snapshot(document: object, snapshot_path: str) -> object:
    """Close ``document`` and reopen it from ``snapshot_path``, returning the reopened document.

    The reopened document takes its ``Name`` from the snapshot file, which is immutable, so the
    caller must rebind its handle to the returned object. The displayed ``Label`` and the original
    ``FileName`` save target are carried over so the document's identity to the user is unchanged.
    """
    import FreeCAD

    label = document.Label
    filename = document.FileName
    FreeCAD.closeDocument(document.Name)
    restored = FreeCAD.openDocument(snapshot_path)
    restored.Label = label
    restored.FileName = filename
    return restored


def _prove_rollback(
    document: object, fp_before: FingerprintRecord, snapshot_path: str
) -> tuple[object, RollbackProof]:
    """Prove the document is back at ``fp_before``, returning the document and the proof path.

    Re-hashes after the caller's abort + recompute. Equality proves ``rolled_back_verified``.
    A mismatch (FreeCAD #6031: undo can fail to restore the pre-``openTransaction`` boundary)
    restores from the snapshot, recomputes and re-asserts equality, giving
    ``rolled_back_via_snapshot``.

    :raises RollbackNotProven: the restored document still does not match ``fp_before``.
    :raises ValueError: the fingerprints carry differing serializer tags.
    """
    if fingerprints_equal(fingerprint(document), fp_before):
        return document, "rolled_back_verified"

    restored = _restore_from_snapshot(document, snapshot_path)
    restored.recompute()
    if not fingerprints_equal(fingerprint(restored), fp_before):
        raise RollbackNotProven(
            "rollback could not be proven: the snapshot-restored document does not match the "
            f"pre-mutation fingerprint {fp_before['digest']}",
            restored,
        )
    return restored, "rolled_back_via_snapshot"


def _mutation_block(
    fp_before: FingerprintRecord,
    fp_after: FingerprintRecord | None,
    report: PostVerifyBlock,
    rolled_back: bool,
    rollback_proven: RollbackProof | None,
    verdict: TerminalStatus,
    snapshot_path: str | None,
    params_digest: str | None = None,
) -> MutationBlock:
    return {
        "schema": "fcb.mutation/1",
        "transaction_id": _TRANSACTION_ID,
        "fingerprint_before": fp_before,
        "fingerprint_after": fp_after,
        "post_verify": report,
        "rolled_back": rolled_back,
        "rollback_proven": rollback_proven,
        "snapshot_path": snapshot_path,
        "verify_verdict": verdict,
        "params_digest": params_digest,
    }


def _envelope(block: MutationBlock, status: TerminalStatus, text: str) -> ResultEnvelope:
    detail = (
        None
        if status == "OK"
        else {
            "code": f"mutation.{status.lower()}",
            "message": block["post_verify"]["explanation"] or status,
        }
    )
    return {
        "schema": "fcb.result-envelope/1",
        "status": status,
        "detail": detail,
        "structured_content": {"mutation": block},
        "text": text,
    }


def summarize_mutation(block: MutationBlock) -> str:
    """One-line mutation summary: the proven rollback path, or the commit and its fingerprint.

    A block that reports neither a rollback nor a passing post-verify is the unproven-rollback
    case, which is summarized as such rather than as a commit.
    """
    if block["rolled_back"]:
        return (
            f"Mutation rolled back ({block['rollback_proven']}): "
            f"{block['post_verify']['explanation']}"
        )
    if not block["post_verify"]["passed"]:
        return f"Mutation failed and its rollback could not be proven: {block['snapshot_path']}."
    return f"Mutation committed; fingerprint {block['fingerprint_after']['digest'][:12]}."


def _rollback_record(block: MutationBlock) -> dict:
    """The audit record's rollback block: the outcome and the proof path that was taken."""
    return {
        "rolled_back": block["rolled_back"],
        "rollback_proven": block["rollback_proven"],
        "snapshot_path": block["snapshot_path"],
        "explanation": block["post_verify"]["explanation"],
    }


def _audit(
    sink: object,
    phase: str,
    tool: str,
    handle: str,
    params: dict,
    block: MutationBlock | None,
    fp_before: FingerprintRecord,
    verdict: TerminalStatus | None,
) -> None:
    """Append one mutation audit line through the injected sink, if one was supplied.

    ``phase`` selects ``sink.before`` (pre-execution, carrying only the before-digest) or
    ``sink.after`` (post-execution, carrying both digests, the verdict and the rollback block).

    A sink that cannot write (full disk, revoked permission) must not abort a mutation mid-bracket
    and leave a transaction open, so a write failure is swallowed here.
    """
    if sink is None:
        return
    try:
        if phase == "before":
            sink.before("mutation", tool, handle, params, fingerprint_before=fp_before["digest"])
            return
        after = block["fingerprint_after"] if block else None
        sink.after(
            "mutation",
            tool,
            handle,
            params,
            verdict,
            fingerprint_before=fp_before["digest"],
            fingerprint_after=after["digest"] if after else None,
            rollback=_rollback_record(block) if block else None,
        )
    except Exception:  # noqa: BLE001 - an unwritable audit sink must not abort the mutation
        pass


def run_mutation(
    document: object,
    handle: str,
    label: str,
    op: Callable[[object], list[str]],
    audit_sink: object = None,
    tool: str = "",
    params: dict | None = None,
) -> tuple[object, ResultEnvelope]:
    """Execute ``op`` on ``document`` inside the mutation bracket; return the document + envelope.

    Outside the transaction: enable the document's undo stack (headless leaves it off, which makes
    ``abortTransaction`` restore nothing), fingerprint the document, snapshot its references, write
    a ``saveCopy`` snapshot. Then open one transaction named ``label``, apply ``op``, recompute, and
    run ``post_verify``. On pass: commit, delete the snapshot, return an ``OK`` envelope carrying
    the after-fingerprint. On failure or exception: abort, recompute (mandatory — undo skips
    recompute, so verifying first reads stale state), and prove restoration by re-hashing,
    escalating to a snapshot restore on mismatch. The snapshot is deleted only after commit or
    proven rollback.

    The returned document is the caller's document, or the reopened one when the snapshot-restore
    path ran (restoring closes and reopens the document, so the original handle's object is dead).
    A rollback that neither path can prove yields a ``SPEC_FAILED`` envelope saying so, with
    ``rolled_back`` false and the snapshot kept on disk — never a claim of restoration; the
    returned document is the one the restore attempt left open.

    :param document: the already-resolved ``App.Document``; never a handle to re-resolve.
    :param handle: the caller's document handle, threaded into the verify reports.
    :param label: the transaction name.
    :param op: applies the typed operation and returns the names of the objects it touched.
    :param audit_sink: sink exposing ``before``/``after``; one record is written on each side of
        the bracket carrying the real digests and the rollback outcome. ``None`` writes none.
    :param tool: the tool name recorded on the audit lines.
    :param params: the tool arguments whose digest the audit lines record.
    :raises ValueError: two fingerprints carry differing serializer tags.
    """
    params = params or {}
    params_digest = _params_digest(params)
    undo_enabled = shim.enable_undo(document)
    fp_before = fingerprint(document)
    _audit(audit_sink, "before", tool, handle, params, None, fp_before, None)
    refs_before = tnp_guard.snapshot_references(document)
    snapshot_path = temp_snapshot_path(document)
    document.saveCopy(snapshot_path)

    document.openTransaction(f"buddy: {label}")
    try:
        touched = list(op(document) or [])
        document.recompute()
        report = post_verify(document, handle, touched, refs_before)
    except Exception as exc:  # noqa: BLE001 - any op failure maps to the proven-rollback path
        report = _block(
            True, False, None, _unrun_tnp_audit(), False, f"{type(exc).__name__}: {exc}"
        )

    if report["passed"]:
        document.commitTransaction()
        # The after-fingerprint is taken while the snapshot still exists: it serializes every shape
        # and can raise, and the snapshot is the only pre-mutation copy until it succeeds.
        fp_after = fingerprint(document)
        _delete_snapshot(snapshot_path)
        block = _mutation_block(
            fp_before, fp_after, report, False, None, "OK", None, params_digest
        )
        _audit(audit_sink, "after", tool, handle, params, block, fp_before, "OK")
        return document, _envelope(block, "OK", summarize_mutation(block))

    document.abortTransaction()
    document.recompute()
    if not undo_enabled:
        # Undo could not be turned on, so abort restores nothing and the snapshot path below is
        # expected. Recorded so it is not misread as the #6031 undo-boundary defect.
        report["explanation"] = f"{report['explanation']}; undo unavailable on this document"
    try:
        document, proof = _prove_rollback(document, fp_before, snapshot_path)
    except RollbackNotProven as exc:
        # R6: the snapshot is deleted only after commit or PROVEN rollback. An unproven rollback
        # keeps it so an operator still has the restore path, and reports it.
        document = exc.document
        report["explanation"] = f"{report['explanation']}; {exc}"
        block = _mutation_block(
            fp_before,
            fingerprint(document),
            report,
            False,
            None,
            "SPEC_FAILED",
            snapshot_path,
            params_digest,
        )
        _audit(audit_sink, "after", tool, handle, params, block, fp_before, "SPEC_FAILED")
        return document, _envelope(block, "SPEC_FAILED", summarize_mutation(block))

    _delete_snapshot(snapshot_path)
    status = _rollback_status(report)
    block = _mutation_block(
        fp_before,
        fingerprint(document),
        report,
        True,
        proof,
        status,
        snapshot_path if proof == "rolled_back_via_snapshot" else None,
        params_digest,
    )
    _audit(audit_sink, "after", tool, handle, params, block, fp_before, status)
    return document, _envelope(block, status, summarize_mutation(block))
