"""Read-only deterministic validators: ``verify_shape``, ``verify_sketch``, ``verify_recompute``.

Each resolves its document through the registry lock, builds a contracts-owned
``ValidationReport`` whose verdict is DERIVED from its checks (never asserted), and returns it
inside a ``ResultEnvelope``. ``verify_shape`` measures ``obj.Shape`` against the closed §7.2
assertion vocabulary (``usecases.assertions``) in an optional anchor frame, plus
``expect_solid_count``/``expect_valid``/``expect_watertight``, and never recomputes.
``verify_sketch`` and ``verify_recompute`` call ``doc.recompute()`` as a read-refresh but open no
transaction and write no property. Unknown object, null ``Shape``, or a non-sketch raises
``ValidationError`` so the dispatch boundary maps it to ``INVALID_INPUT``.
"""

from __future__ import annotations

from freecad_buddy.contracts import ASSERTION_FNS, ResultEnvelope, derive_verdict, summary_text
from freecad_buddy.usecases import assertions, shim
from freecad_buddy.usecases.documents import DocumentRegistry, ValidationError

# FreeCAD marks a failed object with "Invalid"/"Error" in obj.State; an object still "Touched"
# after a full recompute was silently skipped (dependencies unresolved) — also an error state.
_RECOMPUTE_ERROR_STATES = frozenset({"Invalid", "Error", "Touched"})


def _recompute_error_state(state: list) -> bool:
    """Whether an object's post-recompute ``State`` indicates it did not compute cleanly."""
    return any(token in _RECOMPUTE_ERROR_STATES for token in state)


def _banner() -> dict:
    """Return the report banner: FreeCAD version and element-map version (int or None)."""
    return {
        "freecad_version": shim.freecad_version(),
        "element_map_version": shim.element_map_version(),
    }


def _failure_detail(report: dict) -> dict:
    """Build the envelope ``ErrorDetail`` from the report's failed checks.

    The envelope contract requires a non-null ``detail`` whenever the status is not ``OK``. The
    code mirrors the verdict and the message names each failed check's id.
    """
    failed = [c for c in report.get("checks", []) if not c.get("passed")]
    ids = [c.get("id") for c in failed]
    return {
        "code": report["verdict"],
        "message": "; ".join(str(i) for i in ids) or report["verdict"],
        "objects": [report.get("subject", {}).get("object")]
        if report.get("subject", {}).get("object")
        else [],
    }


def summarize_recompute(report: dict) -> str:
    """One-line recompute summary: clean or failing object names."""
    failing = report.get("subject", {}).get("failing_objects", [])
    if not failing:
        return "Recompute clean: no errors."
    n = len(failing)
    names = ", ".join(failing[:3])
    suffix = f" (+{n - 3} more)" if n > 3 else ""
    return f"Recompute: {n} error(s): {names}{suffix}."


def summarize_shape(report: dict) -> str:
    """One-line shape summary: verdict + first failing check."""
    verdict = report.get("verdict", "?")
    obj = report.get("subject", {}).get("object", "?")
    failed = [c for c in report.get("checks", []) if not c.get("passed")]
    if not failed:
        return f"{obj}: shape checks passed ({verdict})."
    first = failed[0]
    return f"{obj}: {first.get('id', 'check')} failed ({verdict})."


def _report_envelope(report: dict, summary: str | None = None) -> ResultEnvelope:
    """Wrap a ValidationReport as a ResultEnvelope whose status mirrors the derived verdict.

    A non-``OK`` verdict carries a non-null ``detail`` per the envelope contract; an ``OK``
    verdict carries ``detail: None``.
    """
    verdict = report["verdict"]
    return {
        "schema": "fcb.result-envelope/1",
        "status": verdict,
        "detail": None if verdict == "OK" else _failure_detail(report),
        "structured_content": report,
        "text": summary if summary is not None else summary_text(report),
    }


def _finish(report: dict, summary: str | None = None) -> ResultEnvelope:
    """Attach schema/banner, derive the verdict, and wrap the report in an envelope."""
    report["schema"] = "fcb.validation-report/1"
    report["banner"] = _banner()
    report["verdict"] = derive_verdict(report)
    return _report_envelope(report, summary)


def _resolve_object(document: object, name: str | None):
    """Return the object named ``name`` on ``document``, or raise ``ValidationError``."""
    if not name:
        raise ValidationError("missing required 'object' name")
    obj = document.getObject(name)
    if obj is None:
        raise ValidationError(f"unknown object: {name}")
    return obj


def _require_shape(obj: object, name: str):
    """Return ``obj.Shape`` or raise ``ValidationError`` when it is null/absent."""
    shape = getattr(obj, "Shape", None)
    is_null = getattr(shape, "isNull", None)
    if shape is None or (is_null is not None and is_null()):
        raise ValidationError(f"object has no shape: {name}")
    return shape


def _bbox_extents(shape: object) -> list[float]:
    bb = shape.BoundBox
    return [bb.XLength, bb.YLength, bb.ZLength]


def _is_watertight(shape: object) -> bool:
    """Whether ``shape`` is a single closed solid: exactly one solid and ``isClosed()``.

    A shape whose ``isClosed`` is absent or raises cannot report closure and surfaces as
    ``ValidationError`` rather than a false ``not watertight``.
    """
    if len(shape.Solids) != 1:
        return False
    is_closed = getattr(shape, "isClosed", None)
    if is_closed is None:
        raise ValidationError("shape does not support closure measurement")
    try:
        return bool(is_closed())
    except Exception as exc:  # noqa: BLE001
        raise ValidationError(f"cannot measure shape closure: {exc}") from exc


def _check_expect_solid_count(shape: object, expect) -> dict:
    measured = len(shape.Solids)
    expected = int(expect)
    passed = measured == expected
    return {
        "id": "shape.solid_count",
        "measured": measured,
        "expected": expected,
        "tolerance": None,
        "passed": passed,
        "detail": {"message": f"solids {measured} vs {expected}"},
    }


def _check_expect_valid(shape: object, expect) -> dict:
    measured = bool(shape.isValid())
    expected = bool(expect)
    passed = measured == expected
    return {
        "id": "shape.valid",
        "measured": measured,
        "expected": expected,
        "tolerance": None,
        "passed": passed,
        "detail": {"message": f"isValid() {measured} vs {expected}"},
    }


def _check_expect_watertight(shape: object, expect) -> dict:
    measured = _is_watertight(shape)
    expected = bool(expect)
    passed = measured == expected
    return {
        "id": "shape.watertight",
        "measured": measured,
        "expected": expected,
        "tolerance": None,
        "passed": passed,
        "detail": {"message": f"watertight {measured} vs {expected}"},
    }


_ASSERTIONS = {
    "expect_solid_count": _check_expect_solid_count,
    "expect_valid": _check_expect_valid,
    "expect_watertight": _check_expect_watertight,
}


def _measured_facts(shape: object) -> list[dict]:
    """Return the bare measured shape facts (all passed, no expected) for a checkless call."""
    return [
        {"id": "shape.volume", "measured": float(shape.Volume), "passed": True},
        {"id": "shape.bbox", "measured": _bbox_extents(shape), "passed": True},
        {"id": "shape.solid_count", "measured": len(shape.Solids), "passed": True},
        {"id": "shape.valid", "measured": bool(shape.isValid()), "passed": True},
        {"id": "shape.watertight", "measured": _is_watertight(shape), "passed": True},
    ]


def verify_shape(
    registry: DocumentRegistry,
    doc: str | None = None,
    object: str | None = None,
    checks: list | None = None,
    anchor_frame: dict | None = None,
) -> ResultEnvelope:
    """Measure an object's shape against the closed assertion vocabulary, read-only.

    ``checks`` is a list of ``{fn, expect, ...}``; a §7.2 ``fn`` is measured by
    ``usecases.assertions`` in ``anchor_frame`` (``{kind, ref}``, the global frame when omitted),
    and ``expect_solid_count``/``expect_valid``/``expect_watertight`` here. When ``checks`` is
    omitted the report carries the bare measured shape facts with ``passed=true`` and no expected.
    When ``object`` is omitted the document's first object is measured. The banner records the
    resolved frame. Never recomputes. An unknown object, a null ``Shape``, or a malformed check or
    frame raises ``ValidationError``.
    """
    return registry.with_document(
        doc, lambda _h, document: read_shape(document, object, checks, anchor_frame)
    )


def read_shape(
    document: object,
    object: str | None = None,
    checks: list | None = None,
    anchor_frame: dict | None = None,
) -> ResultEnvelope:
    """Measure ``object``'s shape on an already-resolved ``document``, holding no registry lock.

    The registry lock is not reentrant, so a caller already inside ``with_document`` — a mutation
    reporting the state it just produced — must reach the measurement this way rather than
    through :func:`verify_shape`, which would deadlock.

    :raises ValidationError: the object is unknown, its ``Shape`` is null, or a check or the
        anchor frame is malformed.
    """
    if object:
        obj = _resolve_object(document, object)
    else:
        objects = list(document.Objects)
        if not objects:
            raise ValidationError("document has no objects to verify")
        obj = objects[0]
    shape = assertions.document_shape(obj, _require_shape(obj, obj.Name))

    checks = checks or []
    for check in checks:
        if not isinstance(check, dict):
            raise ValidationError(f"check must be an object, got {check!r}")
        fn = check.get("fn")
        if fn not in ASSERTION_FNS and fn not in _ASSERTIONS:
            raise ValidationError(f"unknown assertion fn: {fn!r}")
    primitives = [check for check in checks if check["fn"] in ASSERTION_FNS]
    measured, frame = assertions.evaluate_checks(document, shape, anchor_frame, primitives)

    report: dict = {"subject": {"object": obj.Name}}
    if checks:
        pending = iter(measured)
        report["checks"] = [
            next(pending)
            if check["fn"] in ASSERTION_FNS
            else _ASSERTIONS[check["fn"]](shape, check.get("expect"))
            for check in checks
        ]
    else:
        report["checks"] = _measured_facts(shape)
    report["schema"] = "fcb.validation-report/1"
    report["banner"] = {**_banner(), "anchor_frame": frame}
    report["verdict"] = derive_verdict(report)
    return _report_envelope(report, summarize_shape(report))


def _getattr_list(obj: object, name: str) -> list:
    """Return ``obj.name`` coerced to a list, or ``[]`` when the attribute is absent/unreadable."""
    value = getattr(obj, name, None)
    if value is None:
        return []
    try:
        return list(value)
    except TypeError:
        return [value]


def constraint_refs(sketch_obj: object, solver_ids: list) -> list[dict]:
    """Map 1-based solver ids to ``{id, name, type}`` refs naming ``Constraints[id-1]``.

    An id outside the constraint list (a diagnostic naming a constraint the solver has already
    dropped) yields a ref carrying only its id.
    """
    constraints = list(getattr(sketch_obj, "Constraints", []) or [])
    refs = []
    for raw in solver_ids:
        solver_id = int(raw)
        ref: dict = {"id": solver_id}
        if 1 <= solver_id <= len(constraints):
            constraint = constraints[solver_id - 1]
            ref["name"] = str(getattr(constraint, "Name", "") or "")
            ref["type"] = str(getattr(constraint, "Type", "") or "")
        refs.append(ref)
    return refs


def verify_sketch(
    registry: DocumentRegistry, doc: str | None = None, sketch: str | None = None
) -> ResultEnvelope:
    """Grade a Sketcher sketch per AD-8, reading properties after a read-refresh recompute.

    PASS ⇔ ``FullyConstrained`` after ``doc.recompute()``. HARD FAIL on non-empty
    conflicting/malformed, a truthy ``evaluateConstraints()``, ``dof < 0`` or ``dof > 0``, or
    any degenerate geometry. Redundant / partially-redundant constraints are WARN only (never
    fail, never auto-removed). A non-sketch object raises ``ValidationError``.
    """
    return registry.with_document(doc, lambda _h, document: read_sketch(document, sketch))


def read_sketch(document: object, sketch: str | None = None) -> ResultEnvelope:
    """Grade ``sketch`` on an already-resolved ``document``, holding no registry lock.

    The registry lock is not reentrant, so a caller already inside ``with_document`` — a
    mutation reporting the state it just produced — must reach the grading this way rather than
    through :func:`verify_sketch`, which would deadlock.

    :raises ValidationError: ``sketch`` names no object, or names one that is not a sketch.
    """

    obj = _resolve_object(document, sketch)
    if not str(getattr(obj, "TypeId", "")).startswith("Sketcher::"):
        raise ValidationError(f"object is not a sketch: {sketch}")

    document.recompute()

    dof = int(getattr(obj, "DoF", getattr(obj, "DoFs", 0)) or 0)
    fully_constrained = bool(getattr(obj, "FullyConstrained", False))
    conflicting = _getattr_list(obj, "ConflictingConstraints")
    malformed = _getattr_list(obj, "MalformedConstraints")
    redundant = _getattr_list(obj, "RedundantConstraints")
    partially_redundant = _getattr_list(obj, "PartiallyRedundantConstraints")

    # evaluateConstraints() detects invalid-index constraints, but on FreeCAD 1.1 it returns
    # True even for a healthy sketch; MalformedConstraints is the authoritative signal, so the
    # method only counts when malformed constraints are actually present.
    evaluate = getattr(obj, "evaluateConstraints", None)
    evaluate_bad = bool(malformed) and (bool(evaluate()) if callable(evaluate) else False)

    detect = getattr(obj, "detectDegeneratedGeometries", None)
    degenerate_count = int(detect(1e-7)) if callable(detect) else 0

    checks = [
        {
            "id": "sketch.fully_constrained",
            "measured": fully_constrained,
            "expected": True,
            "passed": fully_constrained
            and dof == 0
            and not conflicting
            and not malformed
            and not evaluate_bad
            and degenerate_count == 0,
            "detail": {
                "message": (
                    f"dof={dof}, conflicting={len(conflicting)}, malformed={len(malformed)}, "
                    f"evaluate_bad={evaluate_bad}, degenerate={degenerate_count}"
                )
            },
        }
    ]

    warnings = []
    if redundant or partially_redundant:
        warnings.append(
            {
                "id": "sketch.redundant",
                "measured": {
                    "redundant": [int(i) for i in redundant],
                    "partially_redundant": [int(i) for i in partially_redundant],
                },
                "passed": False,
                "detail": {"message": "redundant constraints present (warning only)"},
            }
        )

    report = {
        "subject": {
            "sketch": obj.Name,
            "dof": dof,
            "fully_constrained": fully_constrained,
            "geometry_count": int(getattr(obj, "GeometryCount", 0) or 0),
            "constraint_count": int(getattr(obj, "ConstraintCount", 0) or 0),
            "conflicting": constraint_refs(obj, conflicting),
            "malformed": constraint_refs(obj, malformed),
            "redundant": constraint_refs(obj, redundant),
            "partially_redundant": constraint_refs(obj, partially_redundant),
        },
        "checks": checks,
        "warnings": warnings,
    }
    return _finish(report)


def verify_recompute(registry: DocumentRegistry, doc: str | None = None) -> ResultEnvelope:
    """Recompute the document and report every object left in an error state, read-only.

    Calls ``doc.recompute()`` (a read-refresh) then collects every object left in an error state
    ("Invalid"/"Error", or still "Touched" — a silent skip), reporting its ``Name`` and
    ``getStatusString()`` in a failed check tagged ``recompute.*`` so the verdict classes as
    ``RECOMPUTE_ERROR``. A clean document yields a single passed check.
    """

    def read(_handle: str, document: object) -> ResultEnvelope:
        document.recompute()

        failing = [
            {"name": obj.Name, "status": _status_string(obj)}
            for obj in document.Objects
            if _recompute_error_state(list(getattr(obj, "State", None) or []))
        ]

        if failing:
            checks = [
                {
                    "id": "recompute.object",
                    "measured": entry["status"],
                    "expected": None,
                    "passed": False,
                    "detail": {
                        "code": "recompute.error",
                        "message": f"{entry['name']}: {entry['status']}",
                        "objects": [entry["name"]],
                    },
                }
                for entry in failing
            ]
        else:
            checks = [
                {
                    "id": "recompute.clean",
                    "measured": 0,
                    "expected": 0,
                    "passed": True,
                    "detail": {"message": "no object left in an error state"},
                }
            ]

        report = {
            "subject": {"failing_objects": [entry["name"] for entry in failing]},
            "checks": checks,
        }
        report["schema"] = "fcb.validation-report/1"
        report["banner"] = _banner()
        report["verdict"] = derive_verdict(report)
        return _report_envelope(report, summarize_recompute(report))

    return registry.with_document(doc, read)


def _status_string(obj: object) -> str:
    """Return ``obj.getStatusString()`` or an empty string when unavailable."""
    getter = getattr(obj, "getStatusString", None)
    return getter() if callable(getter) else ""
