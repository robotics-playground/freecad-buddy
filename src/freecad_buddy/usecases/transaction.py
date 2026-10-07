"""The uniform mutation protocol: ``run_mutation()`` and ``post_verify()``.

``run_mutation(doc, op)`` is the only path a mutation executes through. Outside the transaction
it takes the pre-mutation fingerprint (the gate's, when the caller passes it), snapshots its
references and writes a ``saveCopy`` snapshot to a reserved-prefix temp path. It then opens one
transaction (never nested, never left open), applies the op, recomputes, and runs ``post_verify``.
On pass it commits and deletes the snapshot; on failure or exception it aborts, recomputes, and
proves restoration by a fresh re-hash, on the digest or else on mass properties — escalating to
restoring the snapshot only when the mass properties differ too.

Takes the already-resolved ``App.Document`` object, never a handle: ``DocumentRegistry
.with_document`` holds a non-reentrant lock, so re-resolving inside the callback would deadlock.
Stdlib + FreeCAD App API only.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import tempfile
from typing import Callable

from freecad_buddy.contracts import (
    NOT_MEASURED,
    FingerprintRecord,
    NotMeasured,
    PostVerifyBlock,
    ResultEnvelope,
    RollbackProof,
    TerminalStatus,
    TnpAuditBlock,
    fingerprints_equal,
    massprops_equal,
)
from freecad_buddy.usecases import confirm, result_projection, shim, tnp_guard, verify
from freecad_buddy.usecases.documents import ValidationError, temp_dir
from freecad_buddy.usecases.fingerprint import fingerprint

logger = logging.getLogger("freecad_buddy.usecases.transaction")

_SNAPSHOT_PREFIX = "FCB_TMP_snap_"

# The Python ``Document.openTransaction(name)`` binding exposes only the name; the C++ ``tid``
# defaults to the null transaction, so the fresh single-document id is implicit and cross-document
# grouping is never requested (App/DocumentPyImp.cpp openTransaction).
_TRANSACTION_ID = "0"

# Containers list every member in their OutList, so following one would pull in sketches the op
# never consumed.
_CONTAINER_TYPES = frozenset({"PartDesign::Body", "App::Part"})


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
    only this one can still be read. ``record`` is that document's fingerprint, the one the proof
    compared.
    """

    def __init__(self, message: str, document: object, record: FingerprintRecord) -> None:
        super().__init__(message)
        self.document = document
        self.record = record


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

    The private directory is minted inside the session workdir (AD-25) so a cleanup that fails
    leaves something the next session's sweep can still reach.
    """
    directory = tempfile.mkdtemp(prefix=_SNAPSHOT_PREFIX, dir=temp_dir())
    return os.path.join(directory, f"{doc.Name}.FCStd")


def _delete_snapshot(path: str) -> None:
    """Remove the snapshot file and its private temp directory, tolerating an absent path.

    Only a directory this module minted is emptied: the whole-directory removal exists to catch the
    sibling files ``saveCopy`` writes, so a path outside a reserved-prefix directory is left alone
    rather than having its contents deleted.

    A removal failure is logged and not raised: the mutation it belongs to has already completed,
    and failing it on a cleanup error would undo a committed result. The artifact stays inside the
    session workdir, so the next session's sweep reaches what this call could not remove — an
    orphan nothing reports and nothing collects is what let empty snapshot directories accumulate.
    """
    directory = os.path.dirname(path)
    if not os.path.basename(directory).startswith(_SNAPSHOT_PREFIX):
        try:
            os.remove(path)
        except OSError:
            logger.warning("could not remove snapshot file %s", path, exc_info=True)
        return
    try:
        for name in os.listdir(directory):
            os.remove(os.path.join(directory, name))
        os.rmdir(directory)
    except OSError:
        logger.warning("could not remove snapshot directory %s", directory, exc_info=True)


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


def _involved_sketches(document: object, touched: list[str]) -> list[str]:
    """Return the sketches in ``touched`` plus each sketch a touched non-container consumes.

    A pad touches the pad and its Body, never its profile, so the profile is found through the
    pad's ``OutList``. A container's ``OutList`` lists every member, so membership alone never
    pulls a sketch in.
    """
    names = list(touched)
    for name in touched:
        obj = document.getObject(name)
        if obj is None or str(getattr(obj, "TypeId", "")) in _CONTAINER_TYPES:
            continue
        for dependency in list(getattr(obj, "OutList", None) or []):
            if dependency.Name not in names:
                names.append(dependency.Name)
    return _sketches(document, names)


def _invalid_objects(document: object) -> list[tuple[str, str]]:
    """Return ``(name, status)`` for every object failing ``isValid()``.

    This includes a sketch with redundant constraints: FreeCAD fails its execute and builds no
    shape for it.
    """
    invalid = []
    for obj in sorted(document.Objects, key=lambda o: o.Name):
        if obj.isValid():
            continue
        getter = getattr(obj, "getStatusString", None)
        invalid.append((obj.Name, str(getter()) if callable(getter) else ""))
    return invalid


def _block(
    recompute_clean: bool,
    is_valid: bool | NotMeasured,
    fully_constrained: bool | None | NotMeasured,
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
    """An audit block for a path where ``audit_references`` never ran.

    That is a setup failure or an op that raised. It is ``UNSUPPORTED`` regardless of whether
    this build exposes an element map: "we did not look" and "we looked and saw nothing wrong"
    are different answers.
    """
    return {
        "status": "UNSUPPORTED",
        "element_map_version": shim.element_map_version_string(),
        "findings": [],
    }


def post_verify(
    document: object,
    handle: str,
    touched: list[str],
    refs_before: list,
    refs_written: list | None = None,
) -> PostVerifyBlock:
    """Run the mutation checklist in order, short-circuiting on the first hard failure.

    The order is (1) recompute clean — no object failing ``isValid()``, collecting
    ``getStatusString()`` per failure; (2) ``verify_shape`` on every shape-bearing object in
    ``touched``; (3) ``verify_sketch`` on every sketch in ``touched`` and every sketch a touched
    non-container consumes, which passes per ``verification-design.md`` §4.2 (a clean solve,
    ``FullyConstrained``, ``dof == 0``, and no conflicting, malformed, redundant or degenerate
    condition); (4) ``audit_references`` against ``refs_before``, where any finding other than
    ``RE_BASELINED`` fails. A failing step names its cause in ``explanation``.

    The audit runs on every return, including a short-circuit: its Layer-0 sweep reports each
    object a recompute broke, which steps (1)-(3) only name in prose.

    :param document: the already-resolved ``App.Document``.
    :param handle: the caller's document handle, threaded through to the verify reports.
    :param touched: names of the objects the op created or modified.
    :param refs_before: the pre-mutation ``snapshot_references`` result.
    :param refs_written: the post-op, pre-recompute ``snapshot_references`` result, which tells the
        audit which references carry the value the op itself assigned.
    """
    registry = _ResolvedRegistry(handle, document)

    def audit() -> TnpAuditBlock:
        return tnp_guard.audit_references(document, refs_before, refs_written)

    invalid = _invalid_objects(document)
    if invalid:
        explanation = "recompute left {} object(s) invalid: {}".format(
            len(invalid), "; ".join(f"{name}: {status}" for name, status in invalid)
        )
        return _block(False, False, NOT_MEASURED, audit(), False, explanation)

    for name in _shape_bearing(document, touched):
        try:
            envelope = verify.verify_shape(registry, doc=handle, object=name)
        except ValidationError as exc:
            explanation = f"verify_shape could not grade {name}: {exc}"
            return _block(True, False, NOT_MEASURED, audit(), False, explanation)
        if not _passed(envelope):
            detail = envelope.get("detail") or {}
            explanation = f"verify_shape failed on {name}: {detail.get('message', '')}"
            return _block(True, False, NOT_MEASURED, audit(), False, explanation)

    fully_constrained: bool | None = None
    for name in _involved_sketches(document, touched):
        try:
            envelope = verify.verify_sketch(registry, doc=handle, sketch=name)
        except ValidationError as exc:
            explanation = f"verify_sketch could not grade {name}: {exc}"
            return _block(True, NOT_MEASURED, NOT_MEASURED, audit(), False, explanation)
        subject = (envelope.get("structured_content") or {}).get("subject") or {}
        # Every sketch the op touched must be constrained, so the block reports the conjunction
        # rather than whichever sketch the loop happened to inspect last.
        constrained = bool(subject.get("fully_constrained"))
        fully_constrained = (
            constrained if fully_constrained is None else (fully_constrained and constrained)
        )
        if not _passed(envelope):
            detail = envelope.get("detail") or {}
            explanation = (
                f"verify_sketch failed on {name} "
                f"(dof={subject.get('dof')}): {detail.get('message', '')}"
            )
            return _block(True, True, fully_constrained, audit(), False, explanation)

    tnp_audit = audit()
    failing = [f for f in tnp_audit["findings"] if f["verdict"] not in ("PASS", "RE_BASELINED")]
    if tnp_audit["status"] == "FLAGGED" and failing:
        explanation = "TNP audit flagged {} reference(s): {}".format(
            len(failing),
            "; ".join(f"{f['owner']}.{f['prop']} {f['verdict']}" for f in failing),
        )
        return _block(True, True, fully_constrained, tnp_audit, False, explanation)

    return _block(True, True, fully_constrained, tnp_audit, True, None)


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
    document: object, fp_before: FingerprintRecord, snapshot_path: str, undo_enabled: bool
) -> tuple[object, RollbackProof, FingerprintRecord]:
    """Prove the document is back at ``fp_before``; return the document, proof path and record.

    Re-hashes after the caller's abort + recompute, computing every entry fresh. Digest equality
    or, failing it, mass-property equality over the same object names proves
    ``rolled_back_verified``: the recompute after an abort writes new B-rep bytes for the shapes it
    rebuilds while their geometry is unchanged. The mass-property fallback applies only when undo
    was enabled: otherwise the abort restored nothing, and a change mass properties cannot see,
    such as a 180 degree rotation about a principal axis through the centre of mass, would be
    proven. A mismatch (FreeCAD #6031: undo can fail to restore the pre-``openTransaction``
    boundary) restores from the snapshot, recomputes and compares again, giving
    ``rolled_back_via_snapshot``.

    The restored document is compared on mass properties too: reopening a file re-serializes every
    shape, so its B-rep bytes never match the in-memory shape they were saved from, while volume,
    area, centre of mass, principal moments and inertia tensor do. A null shape carries zeroed mass
    properties on both sides.

    The returned record is the fingerprint the proof compared, so the caller reports it as the
    after-fingerprint rather than hashing the document again.

    :raises RollbackNotProven: the restored document still does not match ``fp_before``.
    :raises ValueError: the fingerprints carry differing serializer tags.
    """
    record = fingerprint(document, fresh=True)
    if fingerprints_equal(record, fp_before) or (
        undo_enabled and massprops_equal(record, fp_before)
    ):
        return document, "rolled_back_verified", record

    restored = _restore_from_snapshot(document, snapshot_path)
    restored.recompute()
    record = fingerprint(restored, fresh=True)
    if not massprops_equal(record, fp_before):
        raise RollbackNotProven(
            "rollback could not be proven: the snapshot-restored document does not match the "
            f"pre-mutation fingerprint {fp_before['digest']}",
            restored,
            record,
        )
    return restored, "rolled_back_via_snapshot", record


def _mutation_block(
    fp_before: FingerprintRecord,
    fp_after: FingerprintRecord | None,
    report: PostVerifyBlock,
    rolled_back: bool,
    rollback_proven: RollbackProof | None,
    verdict: TerminalStatus,
    snapshot_path: str | None,
    params_digest: str | None = None,
    touched: list[str] | None = None,
) -> dict:
    """Build the full block: whole fingerprint records, every finding, the audit-only fields."""
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
        "touched": list(touched or []),
    }


def _setup_failed_envelope(
    exc: Exception, params_digest: str, fp_before: FingerprintRecord | None = None
) -> ResultEnvelope:
    """Report a pre-bracket failure. Nothing was mutated and no transaction was opened.

    ``fp_before`` is ``None`` when taking the fingerprint is the step that failed.
    """
    report = _block(True, True, None, _unrun_tnp_audit(), False, f"{type(exc).__name__}: {exc}")
    block = _mutation_block(
        fp_before, None, report, False, None, "SPEC_FAILED", None, params_digest, []
    )
    return _envelope(block, "SPEC_FAILED", summarize_mutation(block))


def _commit_failed_envelope(
    exc: Exception,
    fp_before: FingerprintRecord,
    tnp_audit: TnpAuditBlock,
    snapshot_path: str,
    params_digest: str,
    touched: list[str],
) -> ResultEnvelope:
    """Report a failed ``commitTransaction`` after the bracket has been aborted.

    ``tnp_audit`` is the audit the passing ``post_verify`` ran before the commit was attempted.
    """
    report = _block(True, True, None, tnp_audit, False, f"{type(exc).__name__}: {exc}")
    _delete_snapshot(snapshot_path)
    block = _mutation_block(
        fp_before, None, report, True, None, "SPEC_FAILED", None, params_digest, touched
    )
    return _envelope(block, "SPEC_FAILED", summarize_mutation(block))


def _unhashable_commit_envelope(
    exc: Exception,
    fp_before: FingerprintRecord,
    tnp_audit: TnpAuditBlock,
    snapshot_path: str,
    params_digest: str,
    touched: list[str],
) -> ResultEnvelope:
    """Report a commit that landed but could not be fingerprinted.

    The document is permanently changed, so ``rolled_back`` is False and the snapshot is kept
    and named: it is the only pre-mutation copy, and restoring is an operator decision.
    ``tnp_audit`` is the audit the passing ``post_verify`` ran before the commit.
    """
    report = _block(True, True, None, tnp_audit, False, f"{type(exc).__name__}: {exc}")
    block = _mutation_block(
        fp_before, None, report, False, None, "SPEC_FAILED", snapshot_path, params_digest, touched
    )
    return _envelope(block, "SPEC_FAILED", summarize_mutation(block))


def _envelope(block: dict, status: TerminalStatus, text: str) -> ResultEnvelope:
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


def summarize_mutation(block: dict) -> str:
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


def _rollback_record(block: dict) -> dict:
    """The audit record's rollback block: the outcome and the proof path that was taken."""
    return {
        "rolled_back": block["rolled_back"],
        "rollback_proven": block["rollback_proven"],
        "snapshot_path": block["snapshot_path"],
        "explanation": block["post_verify"]["explanation"],
    }


def _digest_of(record: FingerprintRecord | None) -> str | None:
    return record["digest"] if record else None


def _audit_before(
    sink: object, tool: str, handle: str, params: dict, fp_before: FingerprintRecord | None
) -> None:
    """Append the pre-execution mutation line through ``sink``, if one was supplied.

    ``fp_before`` is ``None`` when the pre-mutation fingerprint could not be taken.

    A sink that cannot write (full disk, revoked permission) must not abort a mutation mid-bracket
    and leave a transaction open, so a write failure is swallowed here.
    """
    if sink is None:
        return
    try:
        sink.before("mutation", tool, handle, params, fingerprint_before=_digest_of(fp_before))
    except Exception:  # noqa: BLE001 - an unwritable audit sink must not abort the mutation
        pass


def _audit_after(sink: object, tool: str, handle: str, params: dict, block: dict) -> None:
    """Append the post-execution mutation line: both digests, the verdict, the rollback block.

    A write failure is swallowed for the same reason as in ``_audit_before``.
    """
    if sink is None:
        return
    try:
        sink.after(
            "mutation",
            tool,
            handle,
            params,
            block["verify_verdict"],
            fingerprint_before=_digest_of(block["fingerprint_before"]),
            fingerprint_after=_digest_of(block["fingerprint_after"]),
            rollback=_rollback_record(block),
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
    fp_before: FingerprintRecord | None = None,
) -> tuple[object, ResultEnvelope]:
    """Execute ``op`` on ``document`` inside the mutation bracket; return the document + envelope.

    Outside the transaction: enable the document's undo stack (headless leaves it off, which makes
    ``abortTransaction`` restore nothing), fingerprint the document unless ``fp_before`` is given,
    snapshot its references, write a ``saveCopy`` snapshot. Then open one transaction named
    ``label``, apply ``op``, re-read the references it wrote, recompute, and run ``post_verify``.
    On pass: commit, delete the snapshot, return an ``OK`` envelope carrying the after-fingerprint.
    On failure or exception: abort, recompute (mandatory — undo skips recompute, so verifying first
    reads stale state), and prove restoration by a fresh re-hash, escalating to a snapshot restore
    when neither the digest nor the mass properties match. The proof's record is the block's
    after-fingerprint. The snapshot is deleted only after commit or proven rollback.

    The returned document is the caller's document, or the reopened one when the snapshot-restore
    path ran (restoring closes and reopens the document, so the original handle's object is dead).
    A rollback that neither path can prove yields a ``SPEC_FAILED`` envelope saying so, with
    ``rolled_back`` false and the snapshot kept on disk — never a claim of restoration; the
    returned document is the one the restore attempt left open.

    Every return writes one ``before`` and one ``after`` audit line, both digested over the full
    ``params``, which is what joins them to the call's approval line. The adapters write no lines
    of their own for an envelope carrying a ``mutation`` block, so no return path may skip them.
    The ``after`` line and the summary text are written from the full block; the envelope then
    carries its ``fcb.mutation/2`` projection (``result_projection.project_mutation``).

    :param document: the already-resolved ``App.Document``; never a handle to re-resolve.
    :param handle: the caller's document handle, threaded into the verify reports.
    :param label: the transaction name.
    :param op: applies the typed operation and returns the names of the objects it touched.
    :param audit_sink: sink exposing ``before``/``after``. ``None`` falls back to the host's sink
        (``confirm.host_audit_sink``), which is itself ``None`` while a preview runs its copy.
    :param tool: the tool name recorded on the audit lines.
    :param params: the tool arguments whose digest the audit lines record.
    :param fp_before: the fingerprint the mutation gate took of ``document`` under the same lock;
        ``None`` (a preview's copy, which the gate exempts) makes the bracket take its own.
    :raises ValueError: two fingerprints carry differing serializer tags.
    """
    params = params or {}
    sink = audit_sink if audit_sink is not None else confirm.host_audit_sink()
    document, envelope = _bracket(document, handle, label, op, sink, tool, params, fp_before)
    full_block = envelope["structured_content"]["mutation"]
    _audit_after(sink, tool, handle, params, full_block)
    envelope["structured_content"]["mutation"] = result_projection.project_mutation(full_block)
    return document, envelope


def _bracket(
    document: object,
    handle: str,
    label: str,
    op: Callable[[object], list[str]],
    sink: object,
    tool: str,
    params: dict,
    fp_before: FingerprintRecord | None,
) -> tuple[object, ResultEnvelope]:
    """The bracket ``run_mutation`` wraps; it writes the ``before`` line, not the ``after``."""
    params_digest = _params_digest(params)
    undo_enabled = shim.enable_undo(document)

    # Setup runs before any transaction is open, so a failure here has mutated nothing. It still
    # has to return an envelope rather than escape: `fingerprint` raises SerializerUnavailable on
    # a shape exposing neither exporter, and `saveCopy` raises on an unwritable temp dir.
    if fp_before is None:
        try:
            fp_before = fingerprint(document)
        except Exception as exc:  # noqa: BLE001 - setup failure must not escape as a raw exception
            _audit_before(sink, tool, handle, params, None)
            return document, _setup_failed_envelope(exc, params_digest)
    _audit_before(sink, tool, handle, params, fp_before)

    snapshot_path = None
    try:
        refs_before = tnp_guard.snapshot_references(document)
        snapshot_path = temp_snapshot_path(document)
        document.saveCopy(snapshot_path)
    except Exception as exc:  # noqa: BLE001 - setup failure must not escape as a raw exception
        if snapshot_path is not None:
            _delete_snapshot(snapshot_path)
        return document, _setup_failed_envelope(exc, params_digest, fp_before)

    document.openTransaction(f"buddy: {label}")
    touched: list[str] = []
    try:
        touched = list(op(document) or [])
        # Read the references the op leaves behind before recompute runs, so the audit can tell
        # what the op wrote from what FreeCAD changed underneath it.
        refs_written = tnp_guard.snapshot_references(document)
        document.recompute()
        report = post_verify(document, handle, touched, refs_before, refs_written)
    except Exception as exc:  # noqa: BLE001 - any op failure maps to the proven-rollback path
        report = _block(
            True, False, None, _unrun_tnp_audit(), False, f"{type(exc).__name__}: {exc}"
        )

    if report["passed"]:
        try:
            document.commitTransaction()
        except Exception as exc:  # noqa: BLE001 - a failed commit must not leave the bracket open
            # R5: never leave a transaction open. abortTransaction no-ops when there is no active
            # transaction (App/Document.cpp:622-639), so it is safe whether the commit got far
            # enough to close one or not.
            document.abortTransaction()
            document.recompute()
            return document, _commit_failed_envelope(
                exc, fp_before, report["tnp_audit"], snapshot_path, params_digest, touched
            )
        # The after-fingerprint is taken while the snapshot still exists: it serializes every shape
        # and can raise, and the snapshot is the only pre-mutation copy until it succeeds.
        try:
            fp_after = fingerprint(document)
        except Exception as exc:  # noqa: BLE001 - the commit already landed; report, never raise
            # The mutation IS committed and the document permanently changed, so this is not a
            # rollback: the snapshot is kept and named so an operator can restore deliberately.
            return document, _unhashable_commit_envelope(
                exc, fp_before, report["tnp_audit"], snapshot_path, params_digest, touched
            )
        _delete_snapshot(snapshot_path)
        block = _mutation_block(
            fp_before, fp_after, report, False, None, "OK", None, params_digest, touched
        )
        return document, _envelope(block, "OK", summarize_mutation(block))

    document.abortTransaction()
    document.recompute()
    if not undo_enabled:
        # Undo could not be turned on, so abort restores nothing and the snapshot path below is
        # expected. Recorded so it is not misread as the #6031 undo-boundary defect.
        report["explanation"] = f"{report['explanation']}; undo unavailable on this document"
    try:
        document, proof, fp_after = _prove_rollback(
            document, fp_before, snapshot_path, undo_enabled
        )
    except RollbackNotProven as exc:
        # R6: the snapshot is deleted only after commit or PROVEN rollback. An unproven rollback
        # keeps it so an operator still has the restore path, and reports it.
        document = exc.document
        report["explanation"] = f"{report['explanation']}; {exc}"
        block = _mutation_block(
            fp_before,
            exc.record,
            report,
            False,
            None,
            "SPEC_FAILED",
            snapshot_path,
            params_digest,
            touched,
        )
        return document, _envelope(block, "SPEC_FAILED", summarize_mutation(block))

    _delete_snapshot(snapshot_path)
    status = _rollback_status(report)
    block = _mutation_block(
        fp_before,
        fp_after,
        report,
        True,
        proof,
        status,
        snapshot_path if proof == "rolled_back_via_snapshot" else None,
        params_digest,
        touched,
    )
    return document, _envelope(block, status, summarize_mutation(block))
