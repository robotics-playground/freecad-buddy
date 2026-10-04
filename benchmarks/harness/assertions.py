"""Deterministic grader for the G2 and G3 benchmarks: ``evaluate(document, checks, anchor_frame)``.

Measures a document against a case's ``assertions.checks`` and returns one contracts ``Check``
per entry. Every measurement is a re-execution over the document's own geometry; a value the
actor reported is never echoed.

The eleven ``verification-design.md`` §7.2 primitives are measured by
``freecad_buddy.usecases.assertions``, the same code ``verify_shape`` runs, in the case's declared
anchor frame. Three declared G2 extensions are measured here (``expect_solid_count``,
``expect_sketch_fully_constrained``, ``expect_sketch_geometry_count``; see
``benchmarks/g2/README.md``). An unsupported ``fn``, a malformed check, and a measurement that
cannot be taken each yield a failing ``INVALID_INPUT`` check, never a silent pass — a grading
failure is reported as one rather than folded into a negative verdict.

FreeCAD-free to import: neither this module nor the primitives module imports FreeCAD at module
level. Runs in-FreeCAD (where the shapes live).
"""

from __future__ import annotations

from freecad_buddy.contracts import ASSERTION_FNS
from freecad_buddy.usecases import assertions as primitives
from freecad_buddy.usecases import verify
from freecad_buddy.usecases.documents import ValidationError

_INVALID_INPUT = primitives.INVALID_INPUT_CODE


def _check(
    check_id: str,
    measured,
    expected,
    passed: bool,
    message: str,
    tolerance=None,
) -> dict:
    return {
        "id": check_id,
        "measured": measured,
        "expected": expected,
        "tolerance": tolerance,
        "passed": passed,
        "detail": {"message": message},
    }


def _invalid(check_id: str, message: str) -> dict:
    return {
        "id": check_id,
        "measured": None,
        "expected": None,
        "tolerance": None,
        "passed": False,
        "detail": {"code": _INVALID_INPUT, "message": message},
    }


def _shape_bearing_objects(document) -> list:
    """Every object on ``document`` carrying a non-null ``Shape``, in immutable ``Name`` order."""
    found = []
    for obj in sorted(document.Objects, key=lambda o: o.Name):
        shape = getattr(obj, "Shape", None)
        is_null = getattr(shape, "isNull", None)
        if shape is not None and not (is_null is not None and is_null()):
            found.append(obj)
    return found


def _graded_shape(document):
    """The last shape-bearing object's shape, in document coordinates, or ``None``.

    A PartDesign build appends each feature, so the last object in dependency order carries the
    finished solid. Membership is tested by immutable ``Name`` rather than object equality, which
    FreeCAD proxies do not define as identity.
    """
    objects = _shape_bearing_objects(document)
    if not objects:
        return None
    names = {obj.Name for obj in objects}
    for obj in reversed(list(document.Objects)):
        if obj.Name in names:
            return primitives.document_shape(obj, obj.Shape)
    return primitives.document_shape(objects[-1], objects[-1].Shape)


def _sketches(document) -> list:
    """Every Sketcher object on ``document``, in immutable ``Name`` order."""
    return [
        obj
        for obj in sorted(document.Objects, key=lambda o: o.Name)
        if str(getattr(obj, "TypeId", "")).startswith("Sketcher::")
    ]


def _measure_primitives(document, checks, anchor_frame) -> list[dict]:
    """Measure validated §7.2 checks in one ``usecases.assertions`` call, in order.

    One call resolves the anchor frame and classifies the hole walls once for all of them. A
    failure that stops the whole batch fails every check in it with ``INVALID_INPUT``.
    """
    try:
        shape = _graded_shape(document)
        if shape is None:
            reason = "document carries no shape to measure"
        else:
            results, _ = primitives.evaluate_checks(document, shape, anchor_frame, checks)
            return results
    except Exception as exc:  # noqa: BLE001 - a grading failure is a failing check
        reason = f"measurement could not be taken: {type(exc).__name__}: {exc}"
    return [_invalid(f"assert.{check['fn']}", reason) for check in checks]


def _measure_expect_solid_count(document, check) -> dict:
    shape = _graded_shape(document)
    if shape is None:
        return _invalid("assert.expect_solid_count", "document carries no shape to measure")
    expected = int(check.get("expect"))
    measured = len(shape.Solids)
    return _check(
        "assert.expect_solid_count",
        measured,
        expected,
        measured == expected,
        f"solids {measured} vs {expected}",
    )


def _measure_expect_sketch_fully_constrained(document, check) -> dict:
    sketches = _sketches(document)
    if not sketches:
        return _invalid(
            "assert.expect_sketch_fully_constrained", "document carries no sketch to measure"
        )
    expected = bool(check.get("expect"))
    # The grader applies verify_sketch's own rule (AD-8), so the two cannot disagree on a sketch.
    states = {
        sketch.Name: verify.read_sketch(document, sketch.Name)["status"] == "OK"
        for sketch in sketches
    }
    measured = all(states.values())
    loose = sorted(name for name, state in states.items() if not state)
    return _check(
        "assert.expect_sketch_fully_constrained",
        measured,
        expected,
        measured == expected,
        "every sketch is fully constrained"
        if measured
        else f"not fully constrained: {', '.join(loose)}",
    )


# Sketcher geometry class names per the case vocabulary's ``kind`` discriminator.
_GEOMETRY_KINDS = {
    "line_segment": "LineSegment",
    "circle": "Circle",
    "arc_of_circle": "ArcOfCircle",
    "ellipse": "Ellipse",
    "point": "Point",
}


def _measure_expect_sketch_geometry_count(document, check) -> dict:
    sketches = _sketches(document)
    if not sketches:
        return _invalid(
            "assert.expect_sketch_geometry_count", "document carries no sketch to measure"
        )
    expected = int(check.get("expect"))
    kind = check.get("kind")
    if kind is not None and kind not in _GEOMETRY_KINDS:
        return _invalid(
            "assert.expect_sketch_geometry_count",
            f"unknown geometry kind {kind!r}; expected one of {sorted(_GEOMETRY_KINDS)}",
        )
    wanted = _GEOMETRY_KINDS.get(kind) if kind else None

    measured = 0
    for sketch in sketches:
        for geometry in getattr(sketch, "Geometry", ()) or ():
            if wanted is None or type(geometry).__name__ == wanted:
                measured += 1
    label = kind or "geometry"
    return _check(
        "assert.expect_sketch_geometry_count",
        measured,
        expected,
        measured == expected,
        f"{label} count {measured} vs {expected}",
    )


_EXTENSIONS = {
    "expect_solid_count": _measure_expect_solid_count,
    "expect_sketch_fully_constrained": _measure_expect_sketch_fully_constrained,
    "expect_sketch_geometry_count": _measure_expect_sketch_geometry_count,
}

SUPPORTED_FNS = ASSERTION_FNS | frozenset(_EXTENSIONS)


def evaluate(document, checks, anchor_frame=None) -> list[dict]:
    """Grade ``document`` against a case's ``assertions.checks``; return one ``Check`` each.

    Each entry is a mapping carrying ``fn`` plus that primitive's parameters (``expect``, and
    optionally ``tol``, ``select``, ``select_a``/``select_b``, ``direction``, ``kind``,
    ``pattern``). An entry that is not a mapping, names no ``fn``, names an ``fn`` outside
    ``SUPPORTED_FNS``, or is malformed for its ``fn`` yields a failing ``INVALID_INPUT`` check
    rather than being skipped, so an unimplemented assertion can never read as a pass. The valid
    §7.2 checks are measured together, in one anchor frame. A measurement that raises is reported
    as a failing check naming the exception.

    :param document: the mutated ``App.Document`` to measure.
    :param checks: the case's ``assertions.checks`` list.
    :param anchor_frame: the case's ``assertions.anchor_frame`` (``{kind, ref}``); ``None``
        measures in the global frame.
    """
    results: list = []
    primitive_slots, primitive_checks = [], []
    for entry in checks or ():
        if not isinstance(entry, dict):
            results.append(_invalid("assert.unknown", f"check must be a mapping, got {entry!r}"))
            continue
        fn = entry.get("fn")
        if fn not in SUPPORTED_FNS:
            results.append(_invalid(f"assert.{fn}", f"unsupported assertion fn: {fn!r}"))
            continue
        if fn in ASSERTION_FNS:
            try:
                primitives.validate_check(entry)
            except ValidationError as exc:
                results.append(_invalid(f"assert.{fn}", f"malformed check: {exc}"))
                continue
            primitive_slots.append(len(results))
            primitive_checks.append(entry)
            results.append(None)
            continue
        try:
            results.append(_EXTENSIONS[fn](document, entry))
        except Exception as exc:  # noqa: BLE001 - a measurement failure is a failing check
            results.append(
                _check(
                    f"assert.{fn}",
                    None,
                    entry.get("expect"),
                    False,
                    f"{type(exc).__name__}: {exc}",
                    entry.get("tol"),
                )
            )
    if primitive_checks:
        measured = _measure_primitives(document, primitive_checks, anchor_frame)
        for slot, result in zip(primitive_slots, measured, strict=True):
            results[slot] = result
    return results
