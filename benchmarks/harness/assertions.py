"""Deterministic grader for the command benchmarks: ``evaluate(document, checks, anchor_frame)``.

Measures a mutated document against a case's ``assertions.checks`` and returns one contracts
``Check`` per entry. Every measurement is a re-execution over the document's own geometry; a
value the actor reported is never echoed.

Fourteen ``fn`` names are supported. Eleven are the closed ``verification-design.md`` §7.2
vocabulary (``is_valid_solid``, ``count_cylindrical_holes``, ``hole_diameter``, ``hole_position``,
``hole_spacing``, ``hole_through``, ``distance_between``, ``angle_between``, ``expect_bbox``,
``expect_extent``, ``expect_volume``); three are the declared G2 extensions
(``expect_solid_count``, ``expect_sketch_fully_constrained``, ``expect_sketch_geometry_count``)
documented in ``benchmarks/g2/README.md``. An unsupported ``fn`` yields a failing
``INVALID_INPUT`` check, never a silent pass, as does a measurement that cannot be taken at all —
a grading failure is reported as one rather than folded into a negative verdict.

Measurements that depend on where the part sits are taken in the case's declared **anchor frame**
(§7.1), resolved once per ``evaluate`` call from the closed derivation set ``named_datum`` |
``base_sketch_plane`` | ``largest_planar_face``. A case that declares no frame measures in global
coordinates, which is what every axis-aligned G2 case already did.

FreeCAD-free to import: the module holds no FreeCAD import, and every measurement reads only
attributes off the document/shape objects it is handed. Runs in-FreeCAD (where the shapes live).
"""

from __future__ import annotations

import math
import sys as _sys

# Default tolerances (verification-design.md §8): a linear dimension bands at 0.05 mm absolute, an
# angle at 0.1 deg and a volume at 1 % relative unless the case declares its own.
_DEFAULT_LINEAR_ABS = 0.05
_DEFAULT_ANGLE_ABS = 0.1
_DEFAULT_VOLUME_REL = 0.01

# Coaxial grouping (§8): cylindrical faces merge into one logical hole when their axes are
# parallel within 0.1 deg and their centre lines are offset by no more than 0.01 mm.
_COAXIAL_ANGLE_TOL = math.radians(0.1)
_COAXIAL_OFFSET_TOL = 0.01

# A full circle sweeps 2*pi; a fillet wall is a partial arc and is excluded from a hole count.
_FULL_TURN = 2.0 * math.pi
_ARC_TOL = 1e-6

# The hole/boss probe samples the wall at this many angular positions and takes the majority, so a
# hole whose wall runs close to a part edge is not misread from the one sample backed by void. An
# odd count leaves no tie.
_WALL_PROBE_SAMPLES = 9

_INVALID_INPUT = "invalid_input.unsupported_assertion"

# The closed anchor-frame derivation set (verification-design.md §7.1). A kind outside it is a
# broken spec, not a failing part, so it is refused rather than silently read as global.
_FRAME_KINDS = ("named_datum", "base_sketch_plane", "largest_planar_face")


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


class ToleranceBelowKernelFloor(Exception):
    """A declared tolerance is tighter than the measured B-rep's own ``Shape.getTolerance``."""


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


def _shape_tolerance(shape) -> float:
    """``shape``'s own B-rep tolerance, or 0.0 when it does not report one.

    ``getTolerance(1)`` asks for the maximum over the shape's sub-elements — the floor an
    assertion has to clear. A shape that offers no such reading imposes no floor rather than an
    invented one.
    """
    getter = getattr(shape, "getTolerance", None)
    if getter is None:
        return 0.0
    try:
        return float(getter(1))
    except Exception:  # noqa: BLE001 - an unreadable tolerance imposes no floor
        return 0.0


def _linear_band(shape, tol, expected: float, default_abs=None, default_rel=None) -> float:
    """A linear allowance that the measured shape's own tolerance can actually support.

    A B-rep does not know its own geometry more precisely than ``Shape.getTolerance``, so an
    assertion banded tighter than that is measuring the kernel's noise (§8, "Floor for all of the
    above"). Refusing it is the point: a tolerance below the floor would otherwise pass or fail on
    which way the tessellation rounded, which is neither a part verdict nor a reproducible one.

    :raises ToleranceBelowKernelFloor: the resolved band is tighter than the shape's tolerance.
    """
    band = _band(tol, expected, default_abs, default_rel)
    floor = _shape_tolerance(shape)
    if band < floor:
        raise ToleranceBelowKernelFloor(
            f"tolerance {band} is tighter than the shape's own getTolerance {floor}"
        )
    return band


# Datum features carry construction geometry, not model shape, and every one of them bears a
# ``Shape``: an App::Plane is an infinite face and a PartDesign::Plane a large finite one. A
# document that declares a named_datum frame therefore ends with a datum as its last shape-bearing
# object, and grading that instead of the part reports "too few vertexes" on a perfectly good
# solid. The same exclusion is made for the same reason in usecases/fingerprint.py:135.
_DATUM_TYPE_PREFIXES = (
    "App::Origin",
    "App::Line",
    "App::Plane",
    "App::Point",
    "PartDesign::Plane",
    "PartDesign::Line",
    "PartDesign::Point",
    "PartDesign::CoordinateSystem",
)


def _shape_bearing_objects(document) -> list:
    """Every object on ``document`` carrying a non-null model ``Shape``, in ``Name`` order.

    Datum features are excluded: they bear a shape but are construction geometry, never the part
    the assertions grade.
    """
    found = []
    for obj in sorted(document.Objects, key=lambda o: o.Name):
        if str(getattr(obj, "TypeId", "")).startswith(_DATUM_TYPE_PREFIXES):
            continue
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


def _dot(a, b) -> float:
    """The dot product of two 3-vectors."""
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _cross(a, b) -> tuple:
    """The cross product of two 3-vectors."""
    return (
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0],
    )


def _normalized(vector) -> tuple:
    """``vector`` scaled to unit length.

    :raises UnmeasurableGeometry: the vector is degenerate and names no direction.
    """
    length = math.sqrt(_dot(vector, vector))
    if length <= 0.0:
        raise UnmeasurableGeometry(f"a zero-length vector names no direction: {vector!r}")
    return (vector[0] / length, vector[1] / length, vector[2] / length)


def _as_tuple(vector) -> tuple:
    """A FreeCAD ``Base.Vector`` or any 3-sequence as a plain ``(x, y, z)`` tuple."""
    if hasattr(vector, "x"):
        return (float(vector.x), float(vector.y), float(vector.z))
    return tuple(float(component) for component in vector)[:3]


class UnmeasurableGeometry(Exception):
    """A measurement could not be taken at all, as opposed to yielding a negative verdict."""


class UnresolvableFrame(Exception):
    """The declared anchor frame does not resolve to exactly one frame on this document.

    A frame that resolves differently on two CI legs is a broken spec rather than a failing part
    (§7.1), so the resolver raises instead of guessing — every derivation member is total or it
    refuses.
    """


class Frame:
    """An anchor frame: an origin and an orthonormal basis, both in global coordinates.

    ``basis`` is ``(x, y, z)`` — the frame's own axes expressed globally — so transforming a
    global point in is a translation followed by a projection onto each axis. The witness records
    which derivation produced the frame and what it resolved against, which is what lets a report
    reader tell a frame that flipped from a part that moved.
    """

    def __init__(self, origin, basis, kind: str, ref=None, witness: str = ""):
        self.origin = tuple(float(component) for component in origin)
        self.basis = tuple(tuple(float(component) for component in axis) for axis in basis)
        self.kind = kind
        self.ref = ref
        self.witness = witness

    def point(self, global_point) -> tuple:
        """``global_point`` in frame coordinates."""
        position = _as_tuple(global_point)
        delta = tuple(position[i] - self.origin[i] for i in range(3))
        return tuple(_dot(delta, axis) for axis in self.basis)

    def to_global(self, local_direction) -> tuple:
        """A direction stated in frame coordinates, expressed globally.

        The origin does not apply to a direction, so this is the basis recombination only: the
        frame's own axes scaled by the local components and summed.
        """
        local = _as_tuple(local_direction)
        return tuple(
            sum(local[i] * self.basis[i][component] for i in range(3)) for component in range(3)
        )

    def describe(self) -> str:
        """The frame's one-line report banner (§7.1: the resolution goes in the report)."""
        return f"frame {self.kind}({self.ref!r}) via {self.witness}"


# The frame every measurement falls back to when a case declares none: the document's own global
# coordinates, which is where every G2 case's axis-aligned geometry already sits.
_GLOBAL_FRAME = Frame(
    origin=(0.0, 0.0, 0.0),
    basis=((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0)),
    kind="global",
    ref=None,
    witness="no anchor_frame declared",
)


def _basis_from_normal(normal) -> tuple:
    """An orthonormal ``(x, y, z)`` basis whose ``z`` is ``normal``.

    A normal fixes two of the three axes only up to a rotation about itself, so the in-plane pair
    needs its own rule or the frame spins freely and every in-frame X/Y reading changes run to
    run. The rule: seed from whichever global axis is *least* parallel to the normal, so the seed
    never degenerates to a near-zero cross product, and break the resulting tie by the fixed
    X, Y, Z order.
    """
    z = _normalized(_as_tuple(normal))
    global_axes = ((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0))
    seed = min(
        global_axes,
        key=lambda axis: (round(abs(_dot(z, axis)), 9), global_axes.index(axis)),
    )
    x = _normalized(tuple(seed[i] - _dot(seed, z) * z[i] for i in range(3)))
    return (x, _cross(z, x), z)


def _basis_from_placement(placement) -> tuple:
    """The ``(x, y, z)`` basis a FreeCAD ``Placement``'s rotation maps the global axes onto."""
    rotation = placement.Rotation
    return tuple(
        _as_tuple(rotation.multVec(type(placement.Base)(*axis)))
        for axis in ((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0))
    )


def _objects_named(document, ref: str) -> list:
    """Every object on ``document`` whose ``Name`` or ``Label`` is ``ref``, in ``Name`` order.

    Both are matched because a spec names the datum the designer sees, which is its ``Label``,
    while the document's stable identity is its ``Name``. Returning the whole list rather than the
    first match is what lets the caller refuse an ambiguous reference instead of picking one.
    """
    return sorted(
        (
            obj
            for obj in document.Objects
            if str(getattr(obj, "Name", "")) == ref or str(getattr(obj, "Label", "")) == ref
        ),
        key=lambda obj: obj.Name,
    )


def _frame_from_placement_holder(document, ref: str, kind: str) -> Frame:
    """The frame carried by the single document object named ``ref``.

    :raises UnresolvableFrame: no object carries that name, more than one does, or the one that
        does carries no ``Placement`` to read a frame from.
    """
    matches = _objects_named(document, ref)
    if not matches:
        raise UnresolvableFrame(f"{kind} names {ref!r}, which no object on the document carries")
    if len(matches) > 1:
        names = ", ".join(obj.Name for obj in matches)
        raise UnresolvableFrame(f"{kind} names {ref!r}, which is ambiguous between: {names}")
    holder = matches[0]
    placement = getattr(holder, "Placement", None)
    if placement is None:
        raise UnresolvableFrame(f"{ref!r} carries no Placement, so it derives no frame")
    return Frame(
        origin=_as_tuple(placement.Base),
        basis=_basis_from_placement(placement),
        kind=kind,
        ref=ref,
        witness=f"{holder.Name} ({getattr(holder, 'TypeId', '?')}) Placement",
    )


def _frame_from_named_datum(document, shape, ref) -> Frame:
    if not ref:
        raise UnresolvableFrame("named_datum names no datum, so it resolves to nothing")
    return _frame_from_placement_holder(document, str(ref), "named_datum")


def _frame_from_base_sketch_plane(document, shape, ref) -> Frame:
    """The frame of the plane a part's base profile was drawn on.

    ``ref`` usually names an object directly — a Body's ``XY_Plane`` or a datum plane — so that is
    tried first. When it names nothing on the document the document's own base sketch is used,
    which is the earliest sketch in dependency order; its ``Placement`` *is* the plane it was
    drawn on.
    """
    if ref:
        try:
            return _frame_from_placement_holder(document, str(ref), "base_sketch_plane")
        except UnresolvableFrame:
            pass
    sketches = [
        sketch
        for sketch in document.Objects
        if str(getattr(sketch, "TypeId", "")).startswith("Sketcher::")
    ]
    if not sketches:
        raise UnresolvableFrame(
            f"base_sketch_plane names {ref!r}, which is absent, and the document carries no sketch"
        )
    base = sketches[0]
    placement = getattr(base, "Placement", None)
    if placement is None:
        raise UnresolvableFrame(f"the base sketch {base.Name} carries no Placement")
    return Frame(
        origin=_as_tuple(placement.Base),
        basis=_basis_from_placement(placement),
        kind="base_sketch_plane",
        ref=ref,
        witness=f"base sketch {base.Name} Placement",
    )


def _planar_faces(shape) -> list:
    """Every face of ``shape`` whose surface is a plane."""
    return [
        face
        for face in getattr(shape, "Faces", ()) or ()
        if type(getattr(face, "Surface", None)).__name__ == "Plane"
    ]


def _face_sort_key(shape, face, index: int) -> tuple:
    """The mandatory ``largest_planar_face`` tie-break key (§7.1), smallest first.

    Largest area, then the lowest centroid along global Z, then the lowest mapped name. Every term
    is load-bearing: a symmetric part has faces of *equal* area, and face order differs between
    FreeCAD legs, so area alone resolves a different origin on each leg and the frame silently
    flips. Area and centroid are rounded before comparison so two faces that are equal to within
    kernel noise compare equal and fall through to the name, rather than ordering on the last bit.
    """
    centre = _as_tuple(face.CenterOfMass)
    return (
        -round(float(face.Area), 6),
        round(centre[2], 6),
        _mapped_name(shape, face, index),
    )


def _mapped_name(shape, face, index: int) -> str:
    """The face's element name, or a positional stand-in when the shape maps no names.

    A raw ``Part`` solid carries no element map, so ``Face<n>`` is the only stable label available.
    It is used as the last tie-break term and never as a selector — AD-13 bans an index selector
    in a spec, not in a resolved witness.
    """
    finder = getattr(shape, "findSubShape", None)
    if finder is not None:
        try:
            name = finder(face)[0]
            if name:
                return str(name)
        except Exception:  # noqa: BLE001 - an unmapped shape falls back to the positional label
            pass
    return f"Face{index + 1}"


def _frame_from_largest_planar_face(document, shape, ref) -> Frame:
    """The frame of the shape's largest planar face, tie-broken deterministically.

    :raises UnresolvableFrame: the shape carries no planar face to anchor to.
    """
    faces = _planar_faces(shape)
    if not faces:
        raise UnresolvableFrame("largest_planar_face: the shape carries no planar face")
    indexed = {id(face): index for index, face in enumerate(getattr(shape, "Faces", ()) or ())}
    chosen = min(faces, key=lambda face: _face_sort_key(shape, face, indexed.get(id(face), 0)))
    name = _mapped_name(shape, chosen, indexed.get(id(chosen), 0))
    return Frame(
        origin=_as_tuple(chosen.CenterOfMass),
        basis=_basis_from_normal(chosen.Surface.Axis),
        kind="largest_planar_face",
        ref=ref,
        witness=f"{name} area={float(chosen.Area):.6f}",
    )


_FRAME_DERIVATIONS = {
    "named_datum": _frame_from_named_datum,
    "base_sketch_plane": _frame_from_base_sketch_plane,
    "largest_planar_face": _frame_from_largest_planar_face,
}


def resolve_frame(document, shape, declaration) -> Frame:
    """Resolve a case's ``assertions.anchor_frame`` to the one frame its measurements run in.

    :param declaration: the case's ``anchor_frame`` mapping, or ``None`` for global coordinates.
    :raises UnresolvableFrame: the declaration names a kind outside the closed derivation set, or
        the named derivation does not resolve to exactly one frame on this document.
    """
    if not declaration:
        return _GLOBAL_FRAME
    if not isinstance(declaration, dict):
        raise UnresolvableFrame(f"anchor_frame must be a mapping, got {declaration!r}")
    kind = declaration.get("kind")
    derive = _FRAME_DERIVATIONS.get(kind)
    if derive is None:
        raise UnresolvableFrame(
            f"anchor_frame kind {kind!r} is outside the closed derivation set {list(_FRAME_KINDS)}"
        )
    if shape is None:
        raise UnresolvableFrame(f"anchor_frame {kind!r} needs a shape to resolve against")
    return derive(document, shape, declaration.get("ref"))


def _probe_is_inside(shape, point) -> bool:
    """Whether ``point`` lies in ``shape``'s material.

    :raises UnmeasurableGeometry: the shape does not support a membership test.
    """
    try:
        return bool(shape.isInside(point, _COAXIAL_OFFSET_TOL, True))
    except Exception as exc:
        raise UnmeasurableGeometry(f"isInside is unavailable on this shape: {exc}") from exc


def _is_hole_wall(shape, face) -> bool:
    """Whether a cylindrical face is a hole wall rather than a boss (§7.3 rule 1).

    Material lies outside a hole's cylinder and inside a boss's. The test samples the wall at
    several angular positions, steps radially *away* from the axis at each, and takes the
    majority verdict: a hole bored close to a part edge has some of its wall backed by void, so a
    single sample would misread it as a boss. Face orientation is not consulted — the radial
    direction is derived from the cylinder's own axis and centre, which no orientation flag can
    flip.

    :raises UnmeasurableGeometry: the face cannot be sampled, carries no usable parameter range,
        or the shape does not support a membership test — none of which is a boss verdict.
    """
    radius = float(face.Surface.Radius)
    span = getattr(face, "ParameterRange", None)
    if not span or len(span) < 4:
        raise UnmeasurableGeometry(f"cylindrical face carries no 4-value ParameterRange: {span!r}")
    u_min, u_max = float(span[0]), float(span[1])
    v = (float(span[2]) + float(span[3])) / 2.0
    axis, origin = _axis_of(face)
    step = min(radius / 2.0, _DEFAULT_LINEAR_ABS * 10)

    inside = 0
    for index in range(_WALL_PROBE_SAMPLES):
        u = u_min + (u_max - u_min) * (index + 0.5) / _WALL_PROBE_SAMPLES
        try:
            point = face.valueAt(u, v)
        except Exception as exc:
            raise UnmeasurableGeometry(f"cylindrical face cannot be sampled: {exc}") from exc
        delta = (point.x - origin[0], point.y - origin[1], point.z - origin[2])
        along = delta[0] * axis[0] + delta[1] * axis[1] + delta[2] * axis[2]
        radial = [delta[i] - along * axis[i] for i in range(3)]
        length = math.sqrt(sum(component**2 for component in radial))
        if length <= 0.0:
            raise UnmeasurableGeometry("a wall sample landed on the cylinder's own axis")
        # ``point.add`` returns a Base.Vector without this module importing FreeCAD: the vector
        # class comes from the shape the caller handed in.
        probe = point.add(point.__class__(*(component / length * step for component in radial)))
        if _probe_is_inside(shape, probe):
            inside += 1
    return inside * 2 > _WALL_PROBE_SAMPLES


def _logical_holes(shape) -> list:
    """Group the shape's hole-wall cylindrical faces into logical holes.

    Applies the §7.3 disambiguation rules in order: keep only full-circle walls (excluding
    fillets' partial arcs), keep only walls with material outside the cylinder (hole, not boss),
    then merge faces sharing an axis direction and a collinear centre line into one hole.

    :raises UnmeasurableGeometry: a candidate wall could not be classified either way.
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


def _measure_is_valid_solid(document, check, frame) -> dict:
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


def _measure_expect_volume(document, check, frame) -> dict:
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


def _measure_expect_solid_count(document, check, frame) -> dict:
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


def _measure_count_cylindrical_holes(document, check, frame) -> dict:
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


def _hole_radii(shape) -> list:
    """One radius per logical hole, smallest first.

    A stepped bore's faces have merged into one logical hole by this point, so the group carries
    more than one radius; the smallest is the bore the spec calls "the hole", with the wider
    counterbore reported alongside it rather than instead of it (§7.3 rule 4).
    """
    return sorted(
        min(float(face.Surface.Radius) for face in group) for group in _logical_holes(shape)
    )


def _measure_hole_diameter(document, check, frame) -> dict:
    """Grade every logical hole's diameter against one declared value (§7.2: ``2 * Radius``).

    ``expect`` is one diameter: a spec stating "a 6 mm hole" is a statement about every hole it
    names, so every logical hole must match it. Grading only the closest hole would pass a part
    that drilled one bore right and the rest wrong.
    """
    shape = _graded_shape(document)
    if shape is None:
        return _invalid("assert.hole_diameter", "document carries no shape to measure")
    expected = float(check.get("expect"))
    band = _linear_band(shape, check.get("tol"), expected, _DEFAULT_LINEAR_ABS)
    measured = [2.0 * radius for radius in _hole_radii(shape)]
    if not measured:
        return _check(
            "assert.hole_diameter",
            None,
            expected,
            False,
            "no logical hole measured",
            check.get("tol"),
        )
    off_band = [diameter for diameter in measured if abs(diameter - expected) > band]
    return _check(
        "assert.hole_diameter",
        measured,
        expected,
        not off_band,
        f"diameters {measured} vs {expected} +/- {band} mm"
        + (f"; outside the band: {off_band}" if off_band else ""),
        check.get("tol"),
    )


def _measure_hole_position(document, check, frame) -> dict:
    """Grade a hole's centre against its declared position **in the anchor frame** (§7.2).

    The cylinder axis is projected onto the anchor plane — the frame's own XY plane — and the
    resulting (x, y) pair is what the spec's numbers name. Measured globally this returns
    plausible values that are wrong by exactly the part's placement, which is the failure mode
    hardest to notice in a report that otherwise looks right (DW-115).

    ``expect`` is one ``[x, y]`` pair, matched by whichever hole lands nearest it, so a spec
    naming one hole's position on a multi-hole part grades that hole rather than an arbitrary one.
    """
    shape = _graded_shape(document)
    if shape is None:
        return _invalid("assert.hole_position", "document carries no shape to measure")
    raw = check.get("expect")
    if not isinstance(raw, (list, tuple)) or len(raw) != 2:
        return _invalid("assert.hole_position", f"expect must be an [x, y] pair, got {raw!r}")
    expected = (float(raw[0]), float(raw[1]))
    band = _linear_band(shape, check.get("tol"), max(abs(v) for v in expected), _DEFAULT_LINEAR_ABS)

    positions = [frame.point(point)[:2] for _, point in _hole_axis_points(shape)]
    if not positions:
        return _check(
            "assert.hole_position",
            None,
            list(expected),
            False,
            "no logical hole measured",
            check.get("tol"),
        )
    nearest = min(positions, key=lambda xy: math.hypot(xy[0] - expected[0], xy[1] - expected[1]))
    offset = math.hypot(nearest[0] - expected[0], nearest[1] - expected[1])
    return _check(
        "assert.hole_position",
        list(nearest),
        list(expected),
        offset <= band,
        f"{frame.describe()}: nearest hole at {nearest} vs {expected}, "
        f"offset {offset} <= {band} mm; all holes in frame: {positions}",
        check.get("tol"),
    )


def _measure_distance_between(document, check, frame) -> dict:
    """Grade a declared distance against every distance the part actually presents (§7.2).

    A spec states a distance — "the axes are 50 mm apart", "the faces are 40 mm apart" — without
    naming which two entities carry it, and AD-13 bans an index selector from doing so. The
    measurement therefore takes the closed set of distances the part offers: the gap between each
    pair of parallel planar faces (``distToShape`` min distance) and the axis-to-axis distance
    between each pair of logical holes. The check passes when some pair carries the declared
    distance, and the full measured set is reported so a failing report names what the part has
    instead of only what it lacks.
    """
    shape = _graded_shape(document)
    if shape is None:
        return _invalid("assert.distance_between", "document carries no shape to measure")
    expected = float(check.get("expect"))
    band = _linear_band(shape, check.get("tol"), expected, _DEFAULT_LINEAR_ABS)
    candidates = _candidate_distances(shape)
    if not candidates:
        return _check(
            "assert.distance_between",
            None,
            expected,
            False,
            "the shape presents no pair of parallel faces or hole axes to measure between",
            check.get("tol"),
        )
    measured, passed = _reported_value(candidates, expected, band)
    return _check(
        "assert.distance_between",
        measured,
        expected,
        passed,
        f"{expected} +/- {band} mm against measured distances {sorted(candidates)}",
        check.get("tol"),
    )


def _reported_value(candidates, expected: float, band: float):
    """The value a selector-free check reports: the one that matched, else the nearest miss.

    Reporting the nearest miss rather than nothing is what makes a failing report diagnostic: it
    says what the part carries instead of only that it lacks the declared value.

    :returns: ``(measured, passed)``.
    """
    matched = [value for value in candidates if abs(value - expected) <= band]
    if matched:
        return matched[0], True
    return min(candidates, key=lambda value: abs(value - expected)), False


def _candidate_distances(shape) -> list:
    """Every distance the shape presents: parallel-planar-face gaps and hole axis separations.

    Rounded before de-duplication so two readings that differ only in kernel noise report as the
    one distance the part has rather than as two.
    """
    found = set()
    planes = _planar_faces(shape)
    for index, face in enumerate(planes):
        for other in planes[index + 1 :]:
            if not _parallel(_as_tuple(face.Surface.Axis), _as_tuple(other.Surface.Axis)):
                continue
            try:
                found.add(round(float(face.distToShape(other)[0]), 6))
            except Exception as exc:  # noqa: BLE001 - an unmeasurable pair is not a distance
                raise UnmeasurableGeometry(
                    f"two planar faces could not be measured: {exc}"
                ) from exc
    axes = _hole_axis_points(shape)
    for index, (axis, point) in enumerate(axes):
        for other_axis, other_point in axes[index + 1 :]:
            if _parallel(axis, other_axis):
                found.add(round(_axis_offset(axis, point, other_point), 6))
            else:
                found.add(round(_distance(point, other_point), 6))
    return [value for value in found if value > 0.0]


def _measure_angle_between(document, check, frame) -> dict:
    """Grade a declared angle against every angle the part's planar faces present (§7.2).

    Same selector-free reading as ``distance_between``: the spec states an angle, and the closed
    candidate set is the unsigned angle between each pair of planar-face normals. Unsigned because
    a face normal's sign is an orientation flag — the same two faces would otherwise measure 90 or
    270 degrees depending on which way the kernel wound them, which is not a property of the part.
    Perpendicular and parallel are this primitive at 90 and 0 degrees, per §7.2.
    """
    shape = _graded_shape(document)
    if shape is None:
        return _invalid("assert.angle_between", "document carries no shape to measure")
    expected = float(check.get("expect"))
    band = _band(check.get("tol"), expected, _DEFAULT_ANGLE_ABS, None)
    planes = _planar_faces(shape)
    if len(planes) < 2:
        return _check(
            "assert.angle_between",
            None,
            expected,
            False,
            f"{len(planes)} planar face(s); an angle needs 2",
            check.get("tol"),
        )
    candidates = set()
    for index, face in enumerate(planes):
        for other in planes[index + 1 :]:
            dot = abs(_dot(_as_tuple(face.Surface.Axis), _as_tuple(other.Surface.Axis)))
            candidates.add(round(math.degrees(math.acos(max(-1.0, min(1.0, dot)))), 6))
    measured, passed = _reported_value(candidates, expected, band)
    return _check(
        "assert.angle_between",
        measured,
        expected,
        passed,
        f"{expected} +/- {band} deg against measured face angles {sorted(candidates)}",
        check.get("tol"),
    )


def _measure_expect_bbox(document, check, frame) -> dict:
    """Grade the part's extents **in the anchor frame**, never the global bounding box (§7.2).

    A part rotated in its document has a global bounding box larger than the part — a 60x40 plate
    turned 30 degrees about Z reads 72x65 globally. The frame's own axes are what the spec's
    numbers are stated along, so the shape's points are transformed into the frame first and the
    extents taken there. ``Shape.BoundBox`` cannot be used for the same reason: it is axis-aligned
    to the document, not to the frame.

    The points come from :func:`_bounding_points`, not from the vertexes alone — a body of
    revolution has no vertex at its widest point.
    """
    shape = _graded_shape(document)
    if shape is None:
        return _invalid("assert.expect_bbox", "document carries no shape to measure")
    raw = check.get("expect")
    if not isinstance(raw, (list, tuple)) or len(raw) != 3:
        return _invalid("assert.expect_bbox", f"expect must be an [x, y, z] triple, got {raw!r}")
    expected = [float(value) for value in raw]
    band = _linear_band(shape, check.get("tol"), max(expected), _DEFAULT_LINEAR_ABS)
    points = [frame.point(point) for point in _bounding_points(shape)]
    if len(points) < 2:
        raise UnmeasurableGeometry("the shape carries too few points to bound")
    measured = [
        max(point[axis] for point in points) - min(point[axis] for point in points)
        for axis in range(3)
    ]
    # The spec's triple names the part's three extents, not which frame axis carries which: a
    # 60x40x5 plate is the same plate whether its long side runs along the frame's X or Y. Both
    # sides are sorted so the check grades the part's proportions rather than its labelling.
    off_band = [(m, e) for m, e in zip(sorted(measured), sorted(expected)) if abs(m - e) > band]
    return _check(
        "assert.expect_bbox",
        measured,
        expected,
        not off_band,
        f"{frame.describe()}: in-frame extents {measured} vs {expected} +/- {band} mm"
        + (f"; outside the band: {off_band}" if off_band else ""),
        check.get("tol"),
    )


def _measure_expect_extent(document, check, frame) -> dict:
    """Grade the part's span along one **frame** direction (§7.2: an oriented extent).

    ``direction`` is declared in frame coordinates — ``[0, 0, 1]`` is the frame's own Z, not the
    document's — so a spec that says "150 mm along the pipe" measures along the pipe however the
    part is placed. Defaults to the frame's Z when the case declares none.
    """
    shape = _graded_shape(document)
    if shape is None:
        return _invalid("assert.expect_extent", "document carries no shape to measure")
    expected = float(check.get("expect"))
    band = _linear_band(shape, check.get("tol"), expected, _DEFAULT_LINEAR_ABS)
    declared = check.get("direction", (0.0, 0.0, 1.0))
    if not isinstance(declared, (list, tuple)) or len(declared) != 3:
        return _invalid(
            "assert.expect_extent", f"direction must be an [x, y, z] triple, got {declared!r}"
        )
    local = tuple(float(component) for component in declared)
    if math.sqrt(_dot(local, local)) <= 0.0:
        return _invalid("assert.expect_extent", "direction [0, 0, 0] names no direction")
    # The declared direction is in frame coordinates, so it is mapped back out to global before
    # projecting the shape's own points onto it.
    axis = _normalized(frame.to_global(_normalized(local)))
    measured = _extent_along(_bounding_points(shape), axis)
    if measured is None:
        raise UnmeasurableGeometry("the shape carries too few points to measure an extent")
    delta = abs(measured - expected)
    return _check(
        "assert.expect_extent",
        measured,
        expected,
        delta <= band,
        f"{frame.describe()}: extent along frame {list(local)} (global {list(axis)}) "
        f"= {measured}; |{measured} - {expected}| = {delta} <= {band} mm",
        check.get("tol"),
    )


def _measure_hole_spacing(document, check, frame) -> dict:
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

    bands = {
        pitch: _linear_band(shape, check.get("tol"), pitch, _DEFAULT_LINEAR_ABS)
        for pitch in expected
    }
    unmatched_pitches = [
        pitch for pitch in expected if not any(abs(gap - pitch) <= bands[pitch] for gap in nearest)
    ]
    stray_gaps = [
        gap for gap in nearest if not any(abs(gap - pitch) <= bands[pitch] for pitch in expected)
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


def _measure_hole_through(document, check, frame) -> dict:
    """Grade whether every logical hole exits both sides of the material it passes through.

    A through hole's wall spans the whole thickness of material its own axis crosses. That local
    thickness is measured, not the solid's overall extent: on a stepped or filleted part the two
    differ, and comparing against the overall extent grades a through hole in a thin section as
    blind and a blind hole in a thin boss as through.
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
        if wall is None:
            raise UnmeasurableGeometry("a hole wall carries too few vertexes to measure")
        material = _local_material_extent(shape, group)
        per_hole.append(wall >= material - _DEFAULT_LINEAR_ABS)
    measured = all(per_hole)
    return _check(
        "assert.hole_through",
        measured,
        expected,
        measured == expected,
        f"{sum(per_hole)}/{len(per_hole)} hole(s) span the material their axis crosses",
    )


def _local_material_extent(shape, group) -> float:
    """The thickness of material a logical hole's axis crosses, measured along that axis.

    The hole's own cylindrical surface, extended past both ends of the shape, is intersected with
    the solid. What survives is the material standing against the wall, whose axial span is the
    thickness the hole must clear to be through. The axis line itself cannot be used: it runs
    inside the bore, where there is no material to intersect.

    :raises UnmeasurableGeometry: the intersection cannot be built or yields nothing.
    """
    part = _sys.modules.get(type(shape).__module__)
    if part is None or not hasattr(part, "makeCylinder"):
        raise UnmeasurableGeometry("the shape's module offers no makeCylinder to probe with")
    axis, centre = _axis_of(group[0])
    radius = float(group[0].Surface.Radius)
    vector = type(shape.BoundBox.Center)
    reach = float(shape.BoundBox.DiagonalLength) * 2.0 or 1.0
    base = vector(*(centre[i] - axis[i] * reach for i in range(3)))
    try:
        wall = next(
            face
            for face in part.makeCylinder(radius, 2.0 * reach, base, vector(*axis)).Faces
            if type(face.Surface).__name__ == "Cylinder"
        )
        material = shape.common(wall)
    except Exception as exc:
        raise UnmeasurableGeometry(f"the hole's wall could not be intersected: {exc}") from exc
    extent = _extent_along(_shape_vertexes(material), axis)
    if extent is None:
        raise UnmeasurableGeometry("no material stands against the hole's wall")
    return extent


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


# How many points each edge is sampled at when bounding a shape. A B-rep's vertexes sit only where
# edges meet, so a body of revolution has almost none: a plain shaft collar carries FOUR, all on
# one seam line, and a bounding measurement taken from them reads a 40 mm collar as 12 mm wide.
# Sampling the edges instead covers the curved silhouette.
#
# The count is set by the error it leaves, not by taste. Sampling a circle of radius R at N points
# under-reads its extent by at most 2*R*(1 - cos(pi/N)). Measured against the largest radius in the
# G3 set (the 100 mm gasket, R=50) and the 0.05 mm default linear band:
#
#     N=64  -> 0.120 mm   over the band: fails a correct gasket
#     N=128 -> 0.030 mm   inside, but only 1.7x margin
#     N=256 -> 0.0075 mm  6.6x margin        <- chosen
#
# Confirmed empirically at N=256 on an R=50 cylinder: 99.9962 mm measured against 100.0.
_EDGE_SAMPLES = 256


def _bounding_points(shape) -> list:
    """The points a bounding measurement is taken over: vertexes plus sampled edge points.

    Vertexes alone are correct only for a polyhedron. Every curved part in the G3 set — collar,
    gasket, standoff, bushing — has its extents defined by surfaces that carry no vertex at their
    widest point, so measuring vertexes alone fails a part that is exactly right.

    Falls back to the vertexes for an edge that cannot be discretized, so an unusual curve degrades
    to the old reading rather than losing the whole measurement.
    """
    points = _shape_vertexes(shape)
    for edge in getattr(shape, "Edges", ()) or ():
        discretize = getattr(edge, "discretize", None)
        if discretize is None:
            continue
        try:
            points.extend(discretize(Number=_EDGE_SAMPLES))
        except Exception:  # noqa: BLE001 - an undiscretizable edge contributes its vertexes only
            continue
    return points


def _extent_along(points, axis):
    """The span of ``points`` projected onto ``axis``; ``None`` when fewer than two points.

    ``None`` distinguishes an unmeasurable extent from a genuine zero-thickness one.
    """
    if len(points) < 2:
        return None
    projections = [p.x * axis[0] + p.y * axis[1] + p.z * axis[2] for p in points]
    return max(projections) - min(projections)


def _measure_expect_sketch_fully_constrained(document, check, frame) -> dict:
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


def _measure_expect_sketch_geometry_count(document, check, frame) -> dict:
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


# The eleven closed §7.2 primitives plus the three declared G2 extensions. A name outside this
# dict is a fork of the vocabulary, not a case (benchmarks/g2/README.md, benchmarks/g3/README.md).
_MEASUREMENTS = {
    "is_valid_solid": _measure_is_valid_solid,
    "count_cylindrical_holes": _measure_count_cylindrical_holes,
    "hole_diameter": _measure_hole_diameter,
    "hole_position": _measure_hole_position,
    "hole_spacing": _measure_hole_spacing,
    "hole_through": _measure_hole_through,
    "distance_between": _measure_distance_between,
    "angle_between": _measure_angle_between,
    "expect_bbox": _measure_expect_bbox,
    "expect_extent": _measure_expect_extent,
    "expect_volume": _measure_expect_volume,
    "expect_solid_count": _measure_expect_solid_count,
    "expect_sketch_fully_constrained": _measure_expect_sketch_fully_constrained,
    "expect_sketch_geometry_count": _measure_expect_sketch_geometry_count,
}

SUPPORTED_FNS = frozenset(_MEASUREMENTS)


def evaluate(document, checks, anchor_frame=None) -> list[dict]:
    """Grade ``document`` against a case's ``assertions.checks``; return one ``Check`` each.

    Each entry is a mapping carrying ``fn`` plus that primitive's parameters (``expect``, and
    optionally ``tol``, ``kind``, ``direction``). An entry that is not a mapping, names no ``fn``,
    or names an ``fn`` outside ``SUPPORTED_FNS`` yields a failing ``INVALID_INPUT`` check rather
    than being skipped, so an unimplemented assertion can never read as a pass. A measurement that
    raises is reported as a failing check naming the exception.

    The anchor frame is resolved once, before any check runs, so every measurement in one case is
    taken in the same frame and a frame that does not resolve fails the whole check list with one
    named reason rather than each check with its own.

    :param document: the mutated ``App.Document`` to measure.
    :param checks: the case's ``assertions.checks`` list.
    :param anchor_frame: the case's ``assertions.anchor_frame`` mapping. ``None`` measures in
        global coordinates, which is the frame an axis-aligned case's declaration resolves to
        anyway.
    """
    entries = list(checks or ())
    try:
        # The global frame needs no shape to resolve against, and asking for one would make this
        # module require a live document to reject an unsupported `fn` — which is the contract
        # ring-boundary tests exercise with no document at all.
        shape = _graded_shape(document) if anchor_frame else None
        frame = resolve_frame(document, shape, anchor_frame)
    except (UnresolvableFrame, UnmeasurableGeometry) as exc:
        # A frame that does not resolve is a broken spec (§7.1). Every check is refused by name
        # rather than measured in a frame nobody declared, which would report wrong numbers as if
        # they were the spec's.
        return [
            _invalid(
                f"assert.{entry.get('fn') if isinstance(entry, dict) else '?'}",
                f"the case's anchor_frame does not resolve: {exc}",
            )
            for entry in entries
        ]

    results = []
    for entry in entries:
        if not isinstance(entry, dict):
            results.append(_invalid("assert.unknown", f"check must be a mapping, got {entry!r}"))
            continue
        fn = entry.get("fn")
        measurement = _MEASUREMENTS.get(fn)
        if measurement is None:
            results.append(_invalid(f"assert.{fn}", f"unsupported assertion fn: {fn!r}"))
            continue
        try:
            results.append(measurement(document, entry, frame))
        except UnmeasurableGeometry as exc:
            results.append(_invalid(f"assert.{fn}", f"measurement could not be taken: {exc}"))
        except ToleranceBelowKernelFloor as exc:
            # A tolerance under the kernel floor is an invalid assertion, not a failing part: it
            # must never read as "the part is out of band" (§8).
            results.append(_invalid(f"assert.{fn}", f"tolerance is invalid: {exc}"))
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
