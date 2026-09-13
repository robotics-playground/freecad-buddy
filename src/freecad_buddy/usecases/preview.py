"""``preview_dry_run``: run a proposed mutation on a throwaway copy and report the diff.

The live document is snapshotted with ``saveCopy`` to a reserved-prefix temp path and reopened
as a TempDoc, the named mutation use case runs against that copy through its own
``run_mutation`` bracket, before/after metrics are measured on both documents, and the TempDoc
is closed and its temp directory removed on every path. The live document is proven unchanged by
comparing its mass properties before and after.

The operation table is injected by the host: ``usecases/`` cannot import the tool catalog, so
the caller supplies a ``{tool name: use-case function}`` mapping and this module validates the
requested tool against it. Stdlib + FreeCAD App API only.
"""

from __future__ import annotations

import os
import secrets
import tempfile
from datetime import datetime, timedelta, timezone
from typing import Callable, Mapping

from freecad_buddy.contracts import (
    GeometryDiff,
    ResultEnvelope,
    TnpAuditBlock,
    massprops_equal,
)
from freecad_buddy.usecases import confirm, shim
from freecad_buddy.usecases.documents import DocumentRegistry, ValidationError, temp_dir
from freecad_buddy.usecases.fingerprint import fingerprint
from freecad_buddy.usecases.queries import shape_metrics

_TEMPDOC_PREFIX = "FCB_TMP_prev_"

# The lifetime of a returned ``preview_id``: it is carried inside the signed token as well as
# advertised on the envelope, so the deadline the caller reads is the one the gate enforces.
_PREVIEW_TTL_SECONDS = 900

# A datum plane, line or local coordinate system is modelled as an unbounded shape: FreeCAD gives
# it a 2e+100-long bounding box and an 8e+100 area. Any extent at or above this is that sentinel,
# never a real measurement.
_INFINITE_EXTENT = 1e50


# --------------------------------------------------------------------------------------------
# Which objects the diff measures
# --------------------------------------------------------------------------------------------


def _has_shape(obj: object) -> bool:
    """Whether ``obj`` carries a non-null ``Shape``."""
    shape = getattr(obj, "Shape", None)
    is_null = getattr(shape, "isNull", None)
    return shape is not None and not (is_null is not None and is_null())


def _is_measurable(obj: object) -> bool:
    """Whether ``obj``'s shape yields a finite measurement of at least one quantity.

    Construction geometry fails this test on its own terms rather than by type name: a datum
    plane, datum line or local coordinate system is unbounded, so its bounding box and area carry
    FreeCAD's infinity sentinel, and a datum point encloses no volume, spans no area and holds no
    edge, so it contributes nothing a diff can report.
    """
    shape = obj.Shape
    bbox = shape.BoundBox
    if not bbox.isValid() or float(bbox.DiagonalLength) >= _INFINITE_EXTENT:
        return False
    if float(shape.Area) >= _INFINITE_EXTENT:
        return False
    return bool(len(shape.Solids) or len(shape.Faces) or len(shape.Edges))


def _is_container(obj: object) -> bool:
    """Whether ``obj`` is a group that republishes a member's shape as its own.

    A ``PartDesign::Body`` reports its tip's shape and an ``App::Part`` its children's, so
    measuring both the container and its member counts the same geometry twice.
    """
    has_extension = getattr(obj, "hasExtension", None)
    return bool(has_extension is not None and has_extension("App::GroupExtension"))


def metric_objects(document: object) -> list[str]:
    """Return the ``Name``s whose shapes the diff sums over, in document order.

    An object qualifies when it bears a non-null shape, that shape yields a finite measurement,
    and it is not a container republishing a member's shape. A qualifying object that another
    qualifying object links to is then dropped: a ``PartDesign::Fillet`` does not replace the
    ``Pad`` it consumes and both keep a live shape, so summing both would report the pad's volume
    twice. ``InList`` catches every link-property shape (``PropertyLink``, ``PropertyLinkSub``,
    ``PropertyLinkList``) without enumerating any of them.
    """
    candidates = [
        obj
        for obj in document.Objects
        if _has_shape(obj) and not _is_container(obj) and _is_measurable(obj)
    ]
    names = {obj.Name for obj in candidates}
    return [obj.Name for obj in candidates if not names.intersection(o.Name for o in obj.InList)]


def document_metrics(document: object) -> dict:
    """Sum ``shape_metrics`` over the document's metric objects.

    Volume, area and the topology counts add; the bounding box is the union of the parts and the
    centre is volume-weighted, falling back to the mean of the part centres when nothing in the
    set encloses volume. A document with no metric object reports zeros and an origin-centred,
    zero-extent box so a diff against it still produces numbers rather than absent keys.
    """
    parts = []
    for name in metric_objects(document):
        parts.append(shape_metrics(document.getObject(name).Shape))

    if not parts:
        return {
            "volume": 0.0,
            "area": 0.0,
            "bbox": [0.0] * 6,
            "com": [0.0, 0.0, 0.0],
            "counts": {"faces": 0, "edges": 0, "vertices": 0, "solids": 0},
        }

    volume = sum(p["volume"] for p in parts)
    area = sum(p["area"] for p in parts)
    bbox = [
        min(p["bbox"][i] for p in parts) if i < 3 else max(p["bbox"][i] for p in parts)
        for i in range(6)
    ]
    # A compound of solids has real volume but no readable CenterOfMass; its bbox centre is the
    # only figure available and is acceptable inside a diff, where it is a delta rather than a
    # published centre of mass.
    weights = [p["volume"] if p["solid"] else 0.0 for p in parts]
    total = sum(weights)
    if total > 0:
        com = [sum(p["com"][i] * w for p, w in zip(parts, weights)) / total for i in range(3)]
    else:
        com = [sum(p["com"][i] for p in parts) / len(parts) for i in range(3)]

    counts = {
        key: sum(p["counts"][key] for p in parts)
        for key in ("faces", "edges", "vertices", "solids")
    }
    return {"volume": volume, "area": area, "bbox": bbox, "com": com, "counts": counts}


# --------------------------------------------------------------------------------------------
# Delta construction
# --------------------------------------------------------------------------------------------


def _scalar(before: float, after: float, units: str) -> dict:
    return {"before": before, "after": after, "delta": after - before, "units": units}


def _count(before: int, after: int) -> dict:
    return {"before": before, "after": after, "delta": after - before}


def _center(bbox: list) -> list[float]:
    return [(bbox[i] + bbox[i + 3]) / 2 for i in range(3)]


def _deltas(before: dict, after: dict) -> dict:
    """Build the ``deltas`` block: volume, area, bbox and centre, each with explicit units."""
    center_before = _center(before["bbox"])
    center_after = _center(after["bbox"])
    return {
        "volume": _scalar(before["volume"], after["volume"], "mm^3"),
        "area": _scalar(before["area"], after["area"], "mm^2"),
        "bbox": {
            "before": list(before["bbox"]),
            "after": list(after["bbox"]),
            "center_shift": [center_after[i] - center_before[i] for i in range(3)],
            "units": "mm",
        },
        "com": {
            "before": list(before["com"]),
            "after": list(after["com"]),
            "shift": [after["com"][i] - before["com"][i] for i in range(3)],
            "units": "mm",
        },
    }


def _counts(before: dict, after: dict) -> dict:
    return {
        key: _count(before["counts"][key], after["counts"][key])
        for key in ("faces", "edges", "vertices", "solids")
    }


# --------------------------------------------------------------------------------------------
# Projections of the op's own post_verify block
# --------------------------------------------------------------------------------------------


_ERROR_STATES = frozenset({"Invalid", "Error", "Touched"})


def _error_sweep(document: object) -> list[dict]:
    """Return ``{object, error}`` for every object left in a pending or failed recompute state."""
    errors = []
    for obj in document.Objects:
        state = list(getattr(obj, "State", None) or [])
        if not _ERROR_STATES.intersection(state):
            continue
        getter = getattr(obj, "getStatusString", None)
        message = str(getter()) if callable(getter) else "; ".join(state)
        errors.append({"object": obj.Name, "error": message})
    return errors


_INVALID_PREFIX = "recompute left "


def _attributed_errors(post_verify: dict | None) -> list[dict]:
    """Return the recompute errors the op's own ``post_verify`` attributes to it.

    Parsed out of the block's ``explanation``, which is where ``post_verify`` records the objects
    its recompute check found invalid, in ``"<name>: <status>"`` form. Re-sweeping the copy is not
    an alternative: a failing op is rolled back before this runs, so the document no longer holds
    the error state, and a sweep would also pick up breakage the op did not cause.
    """
    if post_verify is None or post_verify.get("recompute_clean", True):
        return []
    explanation = post_verify.get("explanation") or ""
    head, _, tail = explanation.partition("invalid: ")
    if not head.startswith(_INVALID_PREFIX) or not tail:
        return []
    errors = []
    for chunk in tail.split("; "):
        name, sep, status = chunk.partition(": ")
        if sep:
            errors.append({"object": name, "error": status})
    return errors


def _unrun_audit() -> TnpAuditBlock:
    """The TNP pre-check for an op that produced no ``post_verify`` block.

    An audit that did not run is ``UNSUPPORTED`` regardless of whether this build exposes an
    element map: "we did not look" and "we looked and saw nothing wrong" are different answers.
    """
    return {
        "status": "UNSUPPORTED",
        "element_map_version": shim.element_map_version_string(),
        "findings": [],
    }


def _validity(
    post_verify: dict | None,
    status: str | None,
    pre_existing: list[dict],
) -> dict:
    """Project ``validity`` from the op's ``post_verify`` block alone.

    ``is_valid`` and ``recompute_clean`` are the op's own verdict; the preview runs no second
    document sweep of its own. It does discount one thing the copy inherited rather than caused:
    ``post_verify``'s recompute check sweeps the whole document, so an object already broken on
    the live document arrives broken on the copy and fails the op's verdict for breakage the op
    did not introduce. Those errors are moved into ``pre_existing_errors``, and the verdict is
    restored only when nothing else remains to blame the op for. The op's terminal ``status`` and
    its ``explanation`` travel with the verdict so an ``is_valid: false`` is never reported
    without a reason.
    """
    if post_verify is None:
        return {
            "is_valid": False,
            "recompute_clean": False,
            "recompute_errors": [],
            "pre_existing_errors": pre_existing,
            "status": status,
            "explanation": None,
        }

    inherited = {entry["object"] for entry in pre_existing}
    attributed = [e for e in _attributed_errors(post_verify) if e["object"] not in inherited]
    is_valid = bool(post_verify.get("is_valid"))
    recompute_clean = bool(post_verify.get("recompute_clean"))
    explanation = post_verify.get("explanation")
    if not recompute_clean and not attributed and inherited:
        # Every object the op's recompute check named was already broken before the preview ran.
        is_valid = True
        recompute_clean = True
        explanation = None
        status = "OK"
    return {
        "is_valid": is_valid,
        "recompute_clean": recompute_clean,
        "recompute_errors": attributed,
        "pre_existing_errors": pre_existing,
        "status": status,
        "explanation": explanation,
    }


def _tnp_precheck(post_verify: dict | None) -> TnpAuditBlock:
    """Surface the copy's own TNP audit block verbatim, or ``UNSUPPORTED`` when none ran."""
    if post_verify is None:
        return _unrun_audit()
    audit = post_verify.get("tnp_audit")
    return audit if isinstance(audit, dict) else _unrun_audit()


# --------------------------------------------------------------------------------------------
# TempDoc lifecycle
# --------------------------------------------------------------------------------------------


def _tempdoc_path() -> str:
    """Return a reserved-prefix temp path for the preview copy, inside a fresh temp directory.

    The prefix is carried by the filename as well as the directory: the reopened document takes
    its ``Name`` from the file stem, so this is what makes the TempDoc identifiable as one.

    The directory is minted inside the session workdir (AD-25) so a cleanup that fails leaves
    something the next session's sweep can still reach.
    """
    directory = tempfile.mkdtemp(prefix=_TEMPDOC_PREFIX, dir=temp_dir())
    return os.path.join(directory, f"{_TEMPDOC_PREFIX}{secrets.token_hex(8)}.FCStd")


def _remove_tempdir(path: str) -> None:
    """Remove the temp file and its private directory, tolerating an absent path.

    Only a directory this module minted is emptied; a path outside a reserved-prefix directory is
    left alone rather than having its contents deleted.
    """
    directory = os.path.dirname(path)
    if not os.path.basename(directory).startswith(_TEMPDOC_PREFIX):
        return
    try:
        for name in os.listdir(directory):
            os.remove(os.path.join(directory, name))
        os.rmdir(directory)
    except OSError:
        pass


def _discard_tempdoc(registry: DocumentRegistry, handle: str | None, path: str) -> None:
    """Close the TempDoc and remove its temp directory, swallowing every failure.

    Runs on the success, failure and exception paths alike. A leaked TempDoc is adopted by
    ``document_list`` and surfaced to the caller mislabeled, so cleanup must not itself raise and
    mask the outcome being reported.
    """
    if handle is not None:
        try:
            registry.document_close(handle)
        except Exception:  # noqa: BLE001 - a failed close must not mask the preview's outcome
            pass
    _remove_tempdir(path)


# --------------------------------------------------------------------------------------------
# The tool
# --------------------------------------------------------------------------------------------


def _resolve_operation(
    op_table: Mapping[str, Callable], operation: dict | None
) -> tuple[str, Callable, dict]:
    """Validate the requested operation against the injected table before any file is written.

    :raises ValidationError: ``operation`` is malformed, or names a tool the table does not hold.
    """
    if not isinstance(operation, dict):
        raise ValidationError("preview_dry_run requires an 'operation' object")
    tool = operation.get("tool")
    if not isinstance(tool, str) or not tool:
        raise ValidationError("preview_dry_run requires operation.tool")
    args = operation.get("args", {})
    if args is None:
        args = {}
    if not isinstance(args, dict):
        raise ValidationError("operation.args must be an object")
    if tool not in op_table:
        raise ValidationError(
            f"not a previewable mutation tool: {tool!r} "
            f"(previewable: {', '.join(sorted(op_table))})"
        )
    if "doc" in args:
        raise ValidationError("operation.args must not carry 'doc'; the preview supplies it")
    return tool, op_table[tool], args


def _failed_envelope(message: str) -> ResultEnvelope:
    return {
        "schema": "fcb.result-envelope/1",
        "status": "SPEC_FAILED",
        "detail": {"code": "preview.failed", "message": message},
        "structured_content": {"preview_id": None, "diff": None, "expires_at": None},
        "text": message,
    }


def summarize_preview(sc: dict) -> str:
    """One-line preview summary: the measured volume delta and the pre-check verdicts."""
    diff = sc.get("diff") or {}
    deltas = diff.get("deltas") or {}
    volume = (deltas.get("volume") or {}).get("delta", 0.0)
    counts = diff.get("counts") or {}
    faces = (counts.get("faces") or {}).get("delta", 0)
    validity = diff.get("validity") or {}
    tnp = (diff.get("tnp_precheck") or {}).get("status", "UNSUPPORTED")
    return (
        f"Preview {sc.get('preview_id', '?')}: volume {volume:+.4f} mm^3, faces {faces:+d}, "
        f"valid={validity.get('is_valid')}, tnp={tnp}."
    )


def preview_dry_run(
    registry: DocumentRegistry,
    op_table: Mapping[str, Callable],
    render_port: object = None,
    doc: str | None = None,
    operation: dict | None = None,
    render: str = "auto",
    view: dict | None = None,
    audit_sink: object = None,
) -> ResultEnvelope:
    """Run ``operation`` on a throwaway copy of ``doc``; report the geometry it would change.

    The live document is never mutated: it is copied with ``saveCopy`` to a reserved-prefix temp
    path, reopened as a TempDoc, and the named use case runs against that copy alone. The TempDoc
    is closed and its temp directory removed before this returns, on every path. The live
    document's mass properties are compared before and after; an inequality is reported as a
    failure rather than an ``OK`` envelope carrying a diff that is not trustworthy.

    An operation that fails on the copy is a successful preview reporting a failing diff: the
    envelope is ``OK`` and ``validity`` carries the op's terminal status and its explanation.

    :param registry: the document registry holding the live document.
    :param op_table: ``{tool name: use-case function}``; the host builds it from the catalog, and
        a tool absent from it is rejected before any file is written.
    :param render_port: the render capability; ``None`` or ``render="off"`` reports the render
        unavailable, which is not an error.
    :param doc: the live document handle.
    :param operation: ``{"tool": str, "args": dict}`` naming a registered mutation tool.
    :param render: ``"auto"`` to attempt a render, ``"off"`` to skip it.
    :param view: the view-control object passed through to the render.
    :param audit_sink: sink exposing ``before``/``after``; one ``preview`` record is written on
        each side of the call. ``None`` writes none.
    :raises ValidationError: ``doc`` is missing or stale, or ``operation`` names no previewable
        tool.
    """
    tool, op_fn, args = _resolve_operation(op_table, operation)
    params = {"doc": doc, "operation": {"tool": tool, "args": args}, "render": render}
    _audit(audit_sink, "before", tool, doc, params, None)

    handle, live = registry.with_document(doc, lambda h, d: (h, d))
    fp_before = fingerprint(live)
    before = document_metrics(live)
    names_before = [o.Name for o in live.Objects]
    pre_existing = _error_sweep(live)

    path = _tempdoc_path()
    temp_handle: str | None = None
    gated_args_digest: str | None = None
    try:
        live.saveCopy(path)
        opened = registry.document_open(path)
        temp_handle = opened["structured_content"]["doc"]
        copy = registry.with_document(temp_handle, lambda h, d: d)
        copy.recompute()

        # The op runs OUTSIDE registry.with_document: the registry lock is non-reentrant, so
        # calling a mutation use case (which resolves its own document) from inside a callback
        # holding it self-deadlocks even though the two handles name different documents.
        # The confirm gate is exempted for exactly this call: it runs against the throwaway copy,
        # and it is what mints the token a live apply of the same op must present. The exemption
        # reports the argument digest the gate computed, which is what the token is signed over.
        with confirm.preview_exemption() as exemption:
            op_envelope = op_fn(registry, doc=temp_handle, **args)
        gated_args_digest = exemption.args_digest

        copy = registry.with_document(temp_handle, lambda h, d: d)
        after = document_metrics(copy)
        names_after = [o.Name for o in copy.Objects]
        content = op_envelope.get("structured_content") or {}
        mutation = content.get("mutation") or {}
        post = mutation.get("post_verify")
        touched = [n for n in list(mutation.get("touched") or []) if n in set(names_after)]
        diff = _diff(
            doc_handle=handle,
            tool=tool,
            args=args,
            before=before,
            after=after,
            names_before=names_before,
            names_after=names_after,
            touched=touched,
            post_verify=post,
            status=op_envelope.get("status"),
            pre_existing=pre_existing,
            fingerprint_before=fp_before["digest"],
            render_block=_render_block(render, render_port),
        )
    finally:
        _discard_tempdoc(registry, temp_handle, path)

    # Run after the cleanup so a preview that did leak is still cleaned before it is reported.
    if not massprops_equal(fp_before, fingerprint(live)):
        message = (
            "preview changed the live document: its mass properties differ from the "
            f"pre-preview reading {fp_before['digest'][:12]}"
        )
        _audit(audit_sink, "after", tool, doc, params, "SPEC_FAILED")
        return _failed_envelope(message)

    # One deadline drives both the advertised `expires_at` and the expiry the gate enforces.
    expires_at = datetime.now(timezone.utc) + timedelta(seconds=_PREVIEW_TTL_SECONDS)
    # An operation that returned without passing the gate leaves no digest an apply could be
    # checked against, so no token is issued rather than one that would match nothing. The diff
    # is still reported: measuring the change and authorizing it are separate answers.
    structured = {
        "preview_id": (
            None
            if gated_args_digest is None
            else confirm.mint_preview_token(
                {
                    "jti": confirm.new_token_id(),
                    "doc": handle,
                    "tool": tool,
                    "args_digest": gated_args_digest,
                    "fingerprint_before": fp_before["digest"],
                    "exp": int(expires_at.timestamp()),
                }
            )
        ),
        "diff": diff,
        "expires_at": expires_at.isoformat(),
    }
    _audit(audit_sink, "after", tool, doc, params, "OK")
    return {
        "schema": "fcb.result-envelope/1",
        "status": "OK",
        "detail": None,
        "structured_content": structured,
        "text": summarize_preview(structured),
    }


def _render_block(render: str, render_port: object) -> dict:
    """Report the render capability; unavailability is never an error.

    ``render="off"`` is an explicit opt-out, recorded as such rather than as a missing capability.
    """
    if render == "off":
        return {"available": False, "reason": "off"}
    if render_port is None:
        return {"available": False, "reason": "no render port"}
    available, reason = render_port.available()
    return {"available": bool(available), "reason": reason}


def _diff(
    doc_handle: str,
    tool: str,
    args: dict,
    before: dict,
    after: dict,
    names_before: list[str],
    names_after: list[str],
    touched: list[str],
    post_verify: dict | None,
    status: str | None,
    pre_existing: list[dict],
    fingerprint_before: str,
    render_block: dict,
) -> GeometryDiff:
    """Assemble the ``GeometryDiff`` from the measured metrics and the op's own verdict."""
    set_before = set(names_before)
    set_after = set(names_after)
    return {
        "schema": "fcb.geometry-diff/1",
        "op": {"tool": tool, "args": args},
        "doc": {"handle": doc_handle},
        "deltas": _deltas(before, after),
        "counts": _counts(before, after),
        "touched": sorted(touched),
        "new": sorted(set_after - set_before),
        "deleted": sorted(set_before - set_after),
        "validity": _validity(post_verify, status, pre_existing),
        "tnp_precheck": _tnp_precheck(post_verify),
        "fingerprint_before": fingerprint_before,
        "render": render_block,
    }


def _audit(
    sink: object, phase: str, tool: str, doc: str | None, params: dict, verdict: str | None
) -> None:
    """Append one ``preview`` audit line through the injected sink, if one was supplied.

    A sink that cannot write must not convert a completed preview into a raised exception, so a
    write failure is swallowed here.
    """
    if sink is None:
        return
    try:
        if phase == "before":
            sink.before("preview", tool, doc, params)
        else:
            sink.after("preview", tool, doc, params, verdict)
    except Exception:  # noqa: BLE001 - an unwritable audit sink must not abort the preview
        pass
