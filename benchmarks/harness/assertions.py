"""Deterministic grader for the G2 command benchmark: ``evaluate(document, checks)``.

Measures a mutated document against a case's ``assertions.checks`` and returns one contracts
``Check`` per entry. Every measurement is a re-execution over the document's own geometry; a
value the actor reported is never echoed.

Eight ``fn`` names are supported. Five are ``verification-design.md`` §7.2 primitives
(``is_valid_solid``, ``count_cylindrical_holes``, ``hole_spacing``, ``hole_through``,
``expect_volume``); three are the declared G2 extensions (``expect_solid_count``,
``expect_sketch_fully_constrained``, ``expect_sketch_geometry_count``) documented in
``benchmarks/g2/README.md``. An unsupported ``fn`` yields a failing ``INVALID_INPUT`` check, never
a silent pass.

FreeCAD-free to import: the module holds no FreeCAD import, and every measurement reads only
attributes off the document/shape objects it is handed. Runs in-FreeCAD (where the shapes live).
"""

from __future__ import annotations

import math

# Default tolerances (verification-design.md §8): a linear dimension bands at 0.05 mm absolute and
# a volume at 1 % relative unless the case declares its own.
_DEFAULT_LINEAR_ABS = 0.05
_DEFAULT_VOLUME_REL = 0.01

# Coaxial grouping (§8): cylindrical faces merge into one logical hole when their axes are
# parallel within 0.1 deg and their centre lines are offset by no more than 0.01 mm.
_COAXIAL_ANGLE_TOL = math.radians(0.1)
_COAXIAL_OFFSET_TOL = 0.01

# A full circle sweeps 2*pi; a fillet wall is a partial arc and is excluded from a hole count.
_FULL_TURN = 2.0 * math.pi
_ARC_TOL = 1e-6

_INVALID_INPUT = "invalid_input.unsupported_assertion"


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


def _band(tol, expected: float, default_abs: float | None, default_rel: float | None) -> float:
    """Resolve a check's tolerance to one absolute allowance.

    Takes the larger of the declared ``abs`` and ``rel`` allowances, falling back to the
    per-quantity default when the case declares neither.
    """
    allowances = []
    if isinstance(tol, dict):
        if tol.get("abs") is not None:
            allowances.append(float(tol["abs"]))
        if tol.get("rel") is not None:
            allowances.append(abs(float(expected)) * float(tol["rel"]))
    if not allowances:
        if default_abs is not None:
            allowances.append(default_abs)
        if default_rel is not None:
            allowances.append(abs(float(expected)) * default_rel)
    return max(allowances) if allowances else 0.0


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
    """The shape the assertions measure: the last shape-bearing object's, or ``None``.

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
            return obj.Shape
    return objects[-1].Shape


def _sketches(document) -> list:
    """Every Sketcher object on ``document``, in immutable ``Name`` order."""
    return [
        obj
        for obj in sorted(document.Objects, key=lambda o: o.Name)
        if str(getattr(obj, "TypeId", "")).startswith("Sketcher::")
    ]


def _cylindrical_faces(shape) -> list:
    """Every face of ``shape`` whose surface is a cylinder."""
    faces = []
    for face in getattr(shape, "Faces", ()) or ():
        surface = getattr(face, "Surface", None)
        if type(surface).__name__ == "Cylinder":
            faces.append(face)
    return faces


def _is_full_circle_wall(face) -> bool:
    """Whether a cylindrical face wraps a full turn — a hole wall, not a fillet's partial arc.

    ``ParameterRange`` on a cylindrical face is ``(uMin, uMax, vMin, vMax)`` with ``u`` the angular
    parameter; a full wall spans ``2*pi``.
    """
    span = getattr(face, "ParameterRange", None)
    if not span or len(span) < 2:
        return False
    return abs(float(span[1]) - float(span[0])) >= _FULL_TURN - _ARC_TOL


def _axis_of(face):
    """Return ``(axis_unit_vector, point_on_axis)`` for a cylindrical face."""
    surface = face.Surface
    axis = surface.Axis
    length = math.sqrt(axis.x**2 + axis.y**2 + axis.z**2) or 1.0
    unit = (axis.x / length, axis.y / length, axis.z / length)
    centre = surface.Center
    return unit, (centre.x, centre.y, centre.z)


def _parallel(a, b) -> bool:
    """Whether two unit axes are parallel (either direction) within the coaxial angle tolerance."""
    dot = abs(a[0] * b[0] + a[1] * b[1] + a[2] * b[2])
    return dot >= math.cos(_COAXIAL_ANGLE_TOL)


def _axis_offset(axis, point_a, point_b) -> float:
    """The perpendicular distance between two parallel axes through ``point_a`` and ``point_b``."""
    delta = (point_b[0] - point_a[0], point_b[1] - point_a[1], point_b[2] - point_a[2])
    along = delta[0] * axis[0] + delta[1] * axis[1] + delta[2] * axis[2]
    perpendicular = (
        delta[0] - along * axis[0],
        delta[1] - along * axis[1],
        delta[2] - along * axis[2],
    )
    return math.sqrt(sum(component**2 for component in perpendicular))


def _distance(point_a, point_b) -> float:
    """The straight-line distance between two points."""
    return math.sqrt(sum((point_b[i] - point_a[i]) ** 2 for i in range(3)))


def _is_hole_wall(shape, face) -> bool:
    """Whether a cylindrical face is a hole wall rather than a boss (§7.3 rule 1).

    Material lies outside a hole's cylinder and inside a boss's. The test samples a point on the
    wall and steps radially *away* from the axis: on a hole that lands in the material, on a boss
    it lands in the void. Face orientation is not consulted — the radial direction is derived from
    the cylinder's own axis and centre, which no orientation flag can flip.
    """
    surface = face.Surface
    radius = float(surface.Radius)
    span = getattr(face, "ParameterRange", None)
    if not span or len(span) < 4:
        return False
    u = (float(span[0]) + float(span[1])) / 2.0
    v = (float(span[2]) + float(span[3])) / 2.0
    try:
        point = face.valueAt(u, v)
    except Exception:  # noqa: BLE001 - a face that cannot be sampled is not counted as a hole
        return False

    axis, origin = _axis_of(face)
    delta = (point.x - origin[0], point.y - origin[1], point.z - origin[2])
    along = delta[0] * axis[0] + delta[1] * axis[1] + delta[2] * axis[2]
    radial = [delta[i] - along * axis[i] for i in range(3)]
    length = math.sqrt(sum(component**2 for component in radial))
    if length <= 0.0:
        return False
    step = min(radius / 2.0, _DEFAULT_LINEAR_ABS * 10)
    # ``point.add`` returns a Base.Vector without this module importing FreeCAD: the vector class
    # comes from the shape the caller handed in.
    probe = point.add(point.__class__(*(component / length * step for component in radial)))
    try:
        return bool(shape.isInside(probe, _COAXIAL_OFFSET_TOL, True))
    except Exception:  # noqa: BLE001 - an unsupported membership test is not a hole verdict
        return False


def _logical_holes(shape) -> list:
    """Group the shape's hole-wall cylindrical faces into logical holes.

    Applies the §7.3 disambiguation rules in order: keep only full-circle walls (excluding
    fillets' partial arcs), keep only walls with material outside the cylinder (hole, not boss),
    then merge faces sharing an axis direction and a collinear centre line into one hole.
    """
    walls = [
        face
        for face in _cylindrical_faces(shape)
        if _is_full_circle_wall(face) and _is_hole_wall(shape, face)
    ]
    groups: list[list] = []
    for face in walls:
        axis, point = _axis_of(face)
        for group in groups:
            group_axis, group_point = _axis_of(group[0])
            if _parallel(axis, group_axis) and (
                _axis_offset(group_axis, group_point, point) <= _COAXIAL_OFFSET_TOL
            ):
                group.append(face)
                break
        else:
            groups.append([face])
    return groups


def _hole_axis_points(shape) -> list:
    """One representative ``(axis, point)`` per logical hole, in a stable positional order.

    The pitch of a linear pattern is the gap between neighbouring axes, so the representatives are
    ordered by their centre coordinates to make "neighbouring" well defined.
    """
    representatives = [_axis_of(group[0]) for group in _logical_holes(shape)]
    return sorted(representatives, key=lambda entry: entry[1])


def _measure_is_valid_solid(document, check) -> dict:
    shape = _graded_shape(document)
    if shape is None:
        return _invalid("assert.is_valid_solid", "document carries no shape to measure")
    expected = bool(check.get("expect"))
    measured = bool(shape.isValid()) and len(shape.Solids) >= 1
    return _check(
        "assert.is_valid_solid",
        measured,
        expected,
        measured == expected,
        f"isValid={shape.isValid()} solids={len(shape.Solids)}",
    )


def _measure_expect_volume(document, check) -> dict:
    shape = _graded_shape(document)
    if shape is None:
        return _invalid("assert.expect_volume", "document carries no shape to measure")
    expected = float(check.get("expect"))
    measured = float(shape.Volume)
    band = _band(check.get("tol"), expected, None, _DEFAULT_VOLUME_REL)
    delta = abs(measured - expected)
    return _check(
        "assert.expect_volume",
        measured,
        expected,
        delta <= band,
        f"|{measured} - {expected}| = {delta} <= {band} mm^3",
        check.get("tol"),
    )


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


def _measure_count_cylindrical_holes(document, check) -> dict:
    shape = _graded_shape(document)
    if shape is None:
        return _invalid("assert.count_cylindrical_holes", "document carries no shape to measure")
    expected = int(check.get("expect"))
    measured = len(_logical_holes(shape))
    return _check(
        "assert.count_cylindrical_holes",
        measured,
        expected,
        measured == expected,
        f"logical holes {measured} vs {expected}",
    )


def _measure_hole_spacing(document, check) -> dict:
    """Grade the nearest-neighbour pitch of a hole pattern.

    ``expect`` is either one pitch (a linear pattern) or one pitch per pattern direction (a
    rectangular pattern, e.g. ``[15.0, 15.0]``). Each hole's distance to its nearest other hole is
    measured, and every declared pitch must be matched by at least one measured distance while
    every measured distance must match some declared pitch — so a pattern at the wrong pitch, and
    one missing a direction, both fail.
    """
    shape = _graded_shape(document)
    if shape is None:
        return _invalid("assert.hole_spacing", "document carries no shape to measure")
    raw = check.get("expect")
    if isinstance(raw, (list, tuple)):
        if not raw:
            return _invalid("assert.hole_spacing", "expect declares no pitch")
        expected = [float(value) for value in raw]
    else:
        expected = [float(raw)]
    axes = _hole_axis_points(shape)
    if len(axes) < 2:
        return _check(
            "assert.hole_spacing",
            None,
            raw,
            False,
            f"{len(axes)} hole(s) measured; spacing needs at least 2",
            check.get("tol"),
        )

    points = [entry[1] for entry in axes]
    nearest = []
    for index, point in enumerate(points):
        distances = [
            _distance(point, other) for position, other in enumerate(points) if position != index
        ]
        nearest.append(min(distances))

    bands = {pitch: _band(check.get("tol"), pitch, _DEFAULT_LINEAR_ABS, None) for pitch in expected}
    unmatched_pitches = [
        pitch for pitch in expected if not any(abs(gap - pitch) <= bands[pitch] for gap in nearest)
    ]
    stray_gaps = [
        gap
        for gap in nearest
        if not any(abs(gap - pitch) <= bands[pitch] for pitch in expected)
    ]
    passed = not unmatched_pitches and not stray_gaps
    detail = f"nearest-neighbour gaps {nearest} vs declared {expected}"
    if unmatched_pitches:
        detail += f"; no gap matches pitch(es) {unmatched_pitches}"
    if stray_gaps:
        detail += f"; gap(s) {stray_gaps} match no declared pitch"
    return _check(
        "assert.hole_spacing",
        nearest,
        raw,
        passed,
        detail,
        check.get("tol"),
    )


def _measure_hole_through(document, check) -> dict:
    """Grade whether every logical hole exits both sides of the solid.

    A through hole's wall spans the solid's full extent along its own axis, so the wall's axial
    extent is compared against the solid's extent projected onto that axis.
    """
    shape = _graded_shape(document)
    if shape is None:
        return _invalid("assert.hole_through", "document carries no shape to measure")
    expected = bool(check.get("expect"))
    groups = _logical_holes(shape)
    if not groups:
        return _check(
            "assert.hole_through", False, expected, expected is False, "no logical hole measured"
        )

    per_hole = []
    for group in groups:
        axis, _ = _axis_of(group[0])
        wall = _extent_along(_group_vertexes(group), axis)
        solid = _extent_along(_shape_vertexes(shape), axis)
        per_hole.append(wall >= solid - _DEFAULT_LINEAR_ABS)
    measured = all(per_hole)
    return _check(
        "assert.hole_through",
        measured,
        expected,
        measured == expected,
        f"{sum(per_hole)}/{len(per_hole)} hole(s) span the solid's axial extent",
    )


def _group_vertexes(group) -> list:
    """Every vertex point of every face in a logical-hole group."""
    points = []
    for face in group:
        for vertex in getattr(face, "Vertexes", ()) or ():
            points.append(vertex.Point)
    return points


def _shape_vertexes(shape) -> list:
    """Every vertex point of ``shape``."""
    return [vertex.Point for vertex in getattr(shape, "Vertexes", ()) or ()]


def _extent_along(points, axis) -> float:
    """The span of ``points`` projected onto ``axis``; ``0.0`` for fewer than two points."""
    if len(points) < 2:
        return 0.0
    projections = [p.x * axis[0] + p.y * axis[1] + p.z * axis[2] for p in points]
    return max(projections) - min(projections)


def _measure_expect_sketch_fully_constrained(document, check) -> dict:
    sketches = _sketches(document)
    if not sketches:
        return _invalid(
            "assert.expect_sketch_fully_constrained", "document carries no sketch to measure"
        )
    expected = bool(check.get("expect"))
    document.recompute()
    states = {sketch.Name: bool(getattr(sketch, "FullyConstrained", False)) for sketch in sketches}
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


_MEASUREMENTS = {
    "is_valid_solid": _measure_is_valid_solid,
    "count_cylindrical_holes": _measure_count_cylindrical_holes,
    "hole_spacing": _measure_hole_spacing,
    "hole_through": _measure_hole_through,
    "expect_volume": _measure_expect_volume,
    "expect_solid_count": _measure_expect_solid_count,
    "expect_sketch_fully_constrained": _measure_expect_sketch_fully_constrained,
    "expect_sketch_geometry_count": _measure_expect_sketch_geometry_count,
}

SUPPORTED_FNS = frozenset(_MEASUREMENTS)


def evaluate(document, checks) -> list[dict]:
    """Grade ``document`` against a case's ``assertions.checks``; return one ``Check`` each.

    Each entry is a mapping carrying ``fn`` plus that primitive's parameters (``expect``, and
    optionally ``tol``, ``kind``, ``pattern``). An entry that is not a mapping, names no ``fn``, or
    names an ``fn`` outside ``SUPPORTED_FNS`` yields a failing ``INVALID_INPUT`` check rather than
    being skipped, so an unimplemented assertion can never read as a pass. A measurement that
    raises is reported as a failing check naming the exception.

    :param document: the mutated ``App.Document`` to measure.
    :param checks: the case's ``assertions.checks`` list.
    """
    results = []
    for entry in checks or ():
        if not isinstance(entry, dict):
            results.append(_invalid("assert.unknown", f"check must be a mapping, got {entry!r}"))
            continue
        fn = entry.get("fn")
        measurement = _MEASUREMENTS.get(fn)
        if measurement is None:
            results.append(_invalid(f"assert.{fn}", f"unsupported assertion fn: {fn!r}"))
            continue
        try:
            results.append(measurement(document, entry))
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
    return results
