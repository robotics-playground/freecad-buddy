"""Assertion primitives: the closed §7.2 vocabulary, measured in a declared anchor frame.

``evaluate_checks`` validates every check, resolves the anchor frame once, and measures each
check over a shape in document coordinates, returning one contracts ``Check`` per entry plus the
resolved frame for the report banner. A check is ``(passed, measured, expected, tolerance,
detail)``; it never aggregates into a part verdict.

Malformed input (an ``fn`` outside the vocabulary, a key the ``fn`` does not take, an index
selector such as ``Face6``, a wrong ``expect`` arity, a malformed frame declaration) raises
``ValidationError``. A measurement that cannot be taken — a selector that matches nothing, an
anchor frame that does not resolve, geometry that cannot be sampled — is a failing check coded
``invalid_input.unsupported_assertion``, never a pass and never a skip.

Selector semantics follow ``benchmarks/g3/README.md`` §Assertion vocabulary; hole grouping follows
the ``verification-design.md`` §7.3 rules. Importable without FreeCAD: FreeCAD modules are
imported only inside the functions that build matrices.
"""

from __future__ import annotations

import math
import re
import sys as _sys

from freecad_buddy.contracts import ANCHOR_FRAME_KINDS, ASSERTION_FNS
from freecad_buddy.usecases.documents import ValidationError

# Default tolerances (verification-design.md §8). A declared ``tol`` replaces the default; the
# shape's own tolerance floors every linear and volume band.
_DEFAULT_LINEAR_ABS = 0.05
_DEFAULT_ANGLE_DEG = 0.1
_DEFAULT_VOLUME_REL = 0.01

# Coaxial grouping (§8): cylindrical faces merge into one logical entity when their axes are
# parallel within 0.1 deg and their centre lines are offset by no more than 0.01 mm.
_COAXIAL_ANGLE_TOL = math.radians(0.1)
_COAXIAL_OFFSET_TOL = 0.01

# A selector ``axis`` or ``normal`` matches within the angle band (README §Assertion vocabulary).
_SELECTOR_ANGLE_TOL = math.radians(_DEFAULT_ANGLE_DEG)

# A full circle sweeps 2*pi; a fillet wall is a partial arc and is excluded from a hole count.
_FULL_TURN = 2.0 * math.pi
_ARC_TOL = 1e-6

# The hole/boss probe samples the wall at this many angular positions and takes the majority, so a
# hole whose wall runs close to a part edge is not misread from the one sample backed by void. An
# odd count leaves no tie.
_WALL_PROBE_SAMPLES = 9

# Two candidate anchor faces tie when their areas differ by less than this fraction, or their
# centroids by less than this distance. Equal faces of one solid differ by floating-point noise
# (about 1e-14 relative), far below both.
_TIE_AREA_REL = 1e-6
_TIE_LINEAR = 1e-6

# An axis whose frame-Z component is below this never meets the anchor plane at a usable point.
_PARALLEL_EPSILON = 1e-9

INVALID_INPUT_CODE = "invalid_input.unsupported_assertion"

_INDEX_SELECTOR = re.compile(r"^(?:Face|Edge|Vertex)\d+$")

_COMMON_KEYS = frozenset({"fn", "expect"})
_KEYS = {
    "is_valid_solid": frozenset(),
    "count_cylindrical_holes": frozenset({"select"}),
    "hole_diameter": frozenset({"tol", "select"}),
    "hole_position": frozenset({"tol", "select"}),
    "hole_spacing": frozenset({"tol", "select", "select_a", "select_b", "pattern"}),
    "hole_through": frozenset({"select"}),
    "distance_between": frozenset({"tol", "select_a", "select_b"}),
    "angle_between": frozenset({"tol", "select_a", "select_b"}),
    "expect_bbox": frozenset({"tol"}),
    "expect_extent": frozenset({"tol", "direction"}),
    "expect_volume": frozenset({"tol"}),
}


class UnmeasurableGeometry(Exception):
    """A measurement could not be taken at all, as opposed to yielding a negative verdict."""


# -- check records --------------------------------------------------------------------------


def _check(fn: str, measured, expected, passed: bool, message: str, tolerance=None) -> dict:
    return {
        "id": f"assert.{fn}",
        "measured": measured,
        "expected": expected,
        "tolerance": tolerance,
        "passed": passed,
        "detail": {"message": message},
    }


def _invalid(fn: str, message: str) -> dict:
    return {
        "id": f"assert.{fn}",
        "measured": None,
        "expected": None,
        "tolerance": None,
        "passed": False,
        "detail": {"code": INVALID_INPUT_CODE, "message": message},
    }


def _one_or_all(values: list):
    """A single match reports its own value; several report the list, in match order."""
    return values[0] if len(values) == 1 else values


# -- validation -----------------------------------------------------------------------------


def _is_number(value) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _require_mapping(value, where: str) -> dict:
    """Return ``value`` when it is a mapping; name an index selector when it is one."""
    if isinstance(value, str) and _INDEX_SELECTOR.match(value):
        raise ValidationError(
            f"{where}: sub-element index selector {value!r} is banned (AD-13); "
            "use a geometric query"
        )
    if not isinstance(value, dict):
        raise ValidationError(f"{where} must be a mapping, got {value!r}")
    return value


def _require_vector(value, size: int, where: str) -> None:
    if (
        not isinstance(value, (list, tuple))
        or len(value) != size
        or not all(_is_number(component) for component in value)
    ):
        raise ValidationError(f"{where} needs {size} numbers, got {value!r}")


def _require_direction(value, where: str) -> None:
    _require_vector(value, 3, where)
    if not any(float(component) for component in value):
        raise ValidationError(f"{where} is the zero vector")


def _validate_hole_query(query, where: str) -> None:
    query = _require_mapping(query, where)
    unknown = set(query) - {"diameter", "axis"}
    if unknown:
        raise ValidationError(f"{where} does not take {sorted(unknown)}")
    if "diameter" in query and not (_is_number(query["diameter"]) and query["diameter"] > 0):
        raise ValidationError(f"{where}.diameter must be a positive number")
    if "axis" in query:
        _require_direction(query["axis"], f"{where}.axis")


def _validate_face_query(query, where: str) -> None:
    query = _require_mapping(query, where)
    if len(query) != 1 or next(iter(query)) not in ("normal", "diameter"):
        raise ValidationError(f"{where} needs exactly one of 'normal' or 'diameter'")
    if "normal" in query:
        _require_direction(query["normal"], f"{where}.normal")
    elif not (_is_number(query["diameter"]) and query["diameter"] > 0):
        raise ValidationError(f"{where}.diameter must be a positive number")


def _validate_side(selector, where: str, holes_only: bool) -> None:
    selector = _require_mapping(selector, where)
    if len(selector) != 1 or next(iter(selector)) not in ("hole", "face"):
        raise ValidationError(f"{where} needs exactly one of 'hole' or 'face'")
    if "hole" in selector:
        _validate_hole_query(selector["hole"], f"{where}.hole")
    elif holes_only:
        raise ValidationError(f"{where} must select a hole")
    else:
        _validate_face_query(selector["face"], f"{where}.face")


def _validate_tol(tol, fn: str) -> None:
    if tol is None:
        return
    tol = _require_mapping(tol, f"{fn}.tol")
    unknown = set(tol) - {"abs", "rel"}
    if unknown:
        raise ValidationError(f"{fn}.tol does not take {sorted(unknown)}")
    for key, value in tol.items():
        if value is not None and not (_is_number(value) and value >= 0):
            raise ValidationError(f"{fn}.tol.{key} must be a non-negative number")


def _validate_expect(fn: str, check: dict) -> None:
    expect = check["expect"]
    if fn in ("is_valid_solid", "hole_through"):
        valid = isinstance(expect, bool)
    elif fn == "count_cylindrical_holes":
        valid = isinstance(expect, int) and not isinstance(expect, bool) and expect >= 0
    elif fn == "expect_bbox":
        _require_vector(expect, 3, f"{fn}.expect")
        valid = True
    elif fn == "hole_position":
        _require_vector(expect, 2, f"{fn}.expect")
        valid = True
    elif fn == "hole_spacing" and "select_a" not in check and isinstance(expect, (list, tuple)):
        valid = bool(expect) and all(_is_number(pitch) for pitch in expect)
    else:
        valid = _is_number(expect)
    if not valid:
        raise ValidationError(f"{fn}.expect has the wrong shape: {expect!r}")


def validate_check(check) -> None:
    """Refuse a check outside the closed vocabulary or not shaped as its ``fn`` requires.

    :raises ValidationError: naming the first defect found.
    """
    check = _require_mapping(check, "check")
    fn = check.get("fn")
    if fn not in ASSERTION_FNS:
        raise ValidationError(f"unknown assertion fn: {fn!r}")
    unknown = set(check) - _COMMON_KEYS - _KEYS[fn]
    if unknown:
        raise ValidationError(f"{fn} does not take {sorted(unknown)}")
    if "expect" not in check:
        raise ValidationError(f"{fn} needs 'expect'")
    _validate_tol(check.get("tol"), fn)
    if "select" in check:
        _validate_hole_query(check["select"], f"{fn}.select")
    two_sided = "select_a" in check or "select_b" in check
    if fn in ("distance_between", "angle_between") and not two_sided:
        raise ValidationError(f"{fn} needs both 'select_a' and 'select_b'")
    if two_sided:
        if "select_a" not in check or "select_b" not in check:
            raise ValidationError(f"{fn} needs both 'select_a' and 'select_b'")
        if "select" in check:
            raise ValidationError(f"{fn} takes 'select' or 'select_a'/'select_b', not both")
        holes_only = fn == "hole_spacing"
        _validate_side(check["select_a"], f"{fn}.select_a", holes_only)
        _validate_side(check["select_b"], f"{fn}.select_b", holes_only)
    if fn == "expect_extent":
        if "direction" not in check:
            raise ValidationError("expect_extent needs 'direction'")
        _require_direction(check["direction"], "expect_extent.direction")
    _validate_expect(fn, check)


def _validate_declared_frame(declared) -> None:
    declared = _require_mapping(declared, "anchor_frame")
    unknown = set(declared) - {"kind", "ref"}
    if unknown:
        raise ValidationError(f"anchor_frame does not take {sorted(unknown)}")
    kind = declared.get("kind")
    if kind not in ANCHOR_FRAME_KINDS:
        raise ValidationError(
            f"anchor_frame.kind must be one of {sorted(ANCHOR_FRAME_KINDS)}, got {kind!r}"
        )
    ref = declared.get("ref")
    if kind == "largest_planar_face":
        if ref is not None:
            raise ValidationError("anchor_frame.ref must be null for largest_planar_face")
    elif not (isinstance(ref, str) and ref):
        raise ValidationError(f"anchor_frame.ref must name an object for {kind}")


# -- vector arithmetic on (x, y, z) tuples ---------------------------------------------------


def _tuple(vector) -> tuple[float, float, float]:
    return (float(vector.x), float(vector.y), float(vector.z))


def _dot(a, b) -> float:
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _cross(a, b) -> tuple[float, float, float]:
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def _sub(a, b) -> tuple[float, float, float]:
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def _scale(a, factor: float) -> tuple[float, float, float]:
    return (a[0] * factor, a[1] * factor, a[2] * factor)


def _norm(a) -> float:
    return math.sqrt(_dot(a, a))


def _unit(a) -> tuple[float, float, float]:
    length = _norm(a)
    if length <= 0.0:
        raise UnmeasurableGeometry("a direction has zero length")
    return _scale(a, 1.0 / length)


def _rounded(a) -> list[float]:
    """A vector for the banner, with float noise and negative zero removed."""
    return [round(component, 9) + 0.0 for component in a]


# -- anchor frame ---------------------------------------------------------------------------


class _Frame:
    """A right-handed frame in document coordinates, or the reason it could not be resolved."""

    def __init__(self, banner: dict, origin=None, axes=None):
        self.banner = banner
        self._origin = origin
        self._axes = axes

    @property
    def is_global(self) -> bool:
        return self.banner["kind"] == "global"

    def _require(self):
        if self._axes is None:
            raise UnmeasurableGeometry(
                f"anchor frame {self.banner['kind']} did not resolve: {self.banner['unresolved']}"
            )
        return self._origin, self._axes

    def point(self, world) -> tuple[float, float, float]:
        origin, axes = self._require()
        delta = _sub(world, origin)
        return (_dot(delta, axes[0]), _dot(delta, axes[1]), _dot(delta, axes[2]))

    def direction(self, world) -> tuple[float, float, float]:
        _, axes = self._require()
        return (_dot(world, axes[0]), _dot(world, axes[1]), _dot(world, axes[2]))

    def to_world(self, local) -> tuple[float, float, float]:
        _, axes = self._require()
        return tuple(
            local[0] * axes[0][i] + local[1] * axes[1][i] + local[2] * axes[2][i] for i in range(3)
        )

    def to_frame_matrix(self):
        """The ``FreeCAD.Matrix`` that maps document coordinates into this frame."""
        import FreeCAD

        origin, (x, y, z) = self._require()
        return FreeCAD.Matrix(
            x[0], x[1], x[2], -_dot(origin, x),
            y[0], y[1], y[2], -_dot(origin, y),
            z[0], z[1], z[2], -_dot(origin, z),
            0.0, 0.0, 0.0, 1.0,
        )  # fmt: skip


def _resolved(kind: str, ref, entity, origin, axes) -> _Frame:
    banner = {
        "kind": kind,
        "ref": ref,
        "entity": entity,
        "origin": _rounded(origin),
        "axes": [_rounded(axis) for axis in axes],
        "units": "mm",
    }
    return _Frame(banner, origin, axes)


def _global_frame() -> _Frame:
    axes = ((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0))
    return _resolved("global", None, None, (0.0, 0.0, 0.0), axes)


def _named_object(document, ref: str):
    """The object whose ``Name`` is ``ref``, else the one object whose ``Label`` is ``ref``.

    :raises UnmeasurableGeometry: no object, or more than one by label, answers to ``ref``.
    """
    obj = document.getObject(ref) if document is not None else None
    if obj is not None:
        return obj
    labelled = [o for o in getattr(document, "Objects", ()) or () if o.Label == ref]
    if len(labelled) > 1:
        names = sorted(o.Name for o in labelled)
        raise UnmeasurableGeometry(f"{ref!r} is the label of several objects: {names}")
    if not labelled:
        raise UnmeasurableGeometry(f"no object is named or labelled {ref!r}")
    return labelled[0]


def _placement_frame(kind: str, document, ref: str) -> _Frame:
    obj = _named_object(document, ref)
    getter = getattr(obj, "getGlobalPlacement", None)
    if getter is None:
        raise UnmeasurableGeometry(f"{obj.Name} carries no placement")
    placement = getter()
    rotation = placement.Rotation
    vector = type(placement.Base)
    axes = tuple(
        _unit(_tuple(rotation.multVec(vector(*basis))))
        for basis in ((1, 0, 0), (0, 1, 0), (0, 0, 1))
    )
    return _resolved(kind, ref, obj.Name, _tuple(placement.Base), axes)


def _mapped_name(shape, index: int) -> str:
    """The face's mapped element name, or ``""`` when the shape carries no element map."""
    getter = getattr(shape, "getElementMappedName", None)
    if getter is None:
        return ""
    try:
        name = getter(f"Face{index}")
    except Exception:  # noqa: BLE001 - an unreadable map is the same as no map
        return ""
    if isinstance(name, tuple):
        name = name[0]
    return str(name or "")


def _largest_planar_face(shape) -> tuple[int, object, str]:
    """Pick the anchor face: largest area, then lowest centroid Z, then lowest mapped name.

    Without mapped names the last tie-break is the lowest centroid X, then Y.

    :raises UnmeasurableGeometry: the shape has no planar face, or a tie survives every rule.
    """
    planes = [
        (index, face)
        for index, face in enumerate(getattr(shape, "Faces", ()) or (), start=1)
        if type(face.Surface).__name__ == "Plane"
    ]
    if not planes:
        raise UnmeasurableGeometry("the shape has no planar face")
    largest = max(float(face.Area) for _, face in planes)
    tied = [entry for entry in planes if float(entry[1].Area) >= largest * (1.0 - _TIE_AREA_REL)]
    centroids = {index: _tuple(face.CenterOfMass) for index, face in tied}

    def lowest(entries: list, axis: int) -> list:
        low = min(centroids[index][axis] for index, _ in entries)
        return [entry for entry in entries if centroids[entry[0]][axis] <= low + _TIE_LINEAR]

    tied = lowest(tied, 2)
    names = {index: _mapped_name(shape, index) for index, _ in tied}
    if len(tied) > 1 and all(names.values()):
        tied = [min(tied, key=lambda entry: names[entry[0]])]
    if len(tied) > 1:
        tied = lowest(lowest(tied, 0), 1)
    if len(tied) > 1:
        faces = [f"Face{index}" for index, _ in tied]
        raise UnmeasurableGeometry(f"largest planar faces {faces} tie on every rule")
    index, face = tied[0]
    return index, face, names[index] or f"Face{index}"


def _face_frame(shape) -> _Frame:
    """Frame on the largest planar face: origin at its centroid, +Z into the part.

    In-plane X is document X projected onto the face, or document Y when the face is normal to X.
    """
    _, face, entity = _largest_planar_face(shape)
    u_min, u_max, v_min, v_max = (float(value) for value in face.ParameterRange)
    outward = _unit(_tuple(face.normalAt((u_min + u_max) / 2.0, (v_min + v_max) / 2.0)))
    z = _scale(outward, -1.0)
    for reference in ((1.0, 0.0, 0.0), (0.0, 1.0, 0.0)):
        projected = _sub(reference, _scale(z, _dot(reference, z)))
        if _norm(projected) > _PARALLEL_EPSILON:
            break
    x = _unit(projected)
    y = _cross(z, x)
    return _resolved("largest_planar_face", None, entity, _tuple(face.CenterOfMass), (x, y, z))


def resolve_anchor_frame(document, shape, declared) -> _Frame:
    """Resolve a declared ``{kind, ref}`` frame; the global frame when nothing is declared.

    A frame that cannot be resolved is returned unresolved rather than raised, so the checks
    that do not depend on it are still measured.

    :raises ValidationError: the declaration is malformed.
    """
    if declared is None:
        return _global_frame()
    _validate_declared_frame(declared)
    kind, ref = declared["kind"], declared.get("ref")
    try:
        if kind == "largest_planar_face":
            return _face_frame(shape)
        return _placement_frame(kind, document, ref)
    except UnmeasurableGeometry as exc:
        return _Frame({"kind": kind, "ref": ref, "entity": None, "unresolved": str(exc)})


def document_shape(obj, shape):
    """``shape`` placed in document coordinates, as the anchor frames are.

    A feature inside a container (a PartDesign Body) carries its shape in the container's
    coordinates; its global placement maps it into the document.
    """
    getter = getattr(obj, "getGlobalPlacement", None)
    current = getattr(shape, "Placement", None)
    if getter is None or current is None:
        return shape
    placement = getter()
    if placement.isSame(current):
        return shape
    placed = shape.copy()
    placed.Placement = placement
    return placed


# -- tolerances -----------------------------------------------------------------------------


def _band(tol, expected: float, default_abs: float | None, default_rel: float | None) -> float:
    """Resolve a check's tolerance to one absolute allowance.

    Takes the larger of the declared ``abs`` and ``rel`` allowances, falling back to the
    per-quantity default when the check declares neither.
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


def shape_floor(shape) -> float:
    """The shape's own tolerance, ``0.0`` when the shape has no tolerance concept.

    :raises ValidationError: ``getTolerance`` exists but raises, which is not a ``0.0`` floor.
    """
    getter = getattr(shape, "getTolerance", None)
    if getter is None:
        return 0.0
    try:
        return float(getter(1))
    except Exception as exc:  # noqa: BLE001
        raise ValidationError(f"cannot measure shape tolerance: {exc}") from exc


def _floored(band: float, floor: float) -> tuple[float, str]:
    """The allowance actually applied, and a note when the shape's tolerance raised it."""
    if floor > band:
        return floor, f" (clamped to shape tolerance floor {floor})"
    return band, ""


def _linear_band(check: dict, expected: float, floor: float) -> tuple[float, str]:
    """The floored allowance for a linear quantity: the declared ``tol``, else ±0.05 mm."""
    return _floored(_band(check.get("tol"), expected, _DEFAULT_LINEAR_ABS, None), floor)


# -- logical holes and faces ----------------------------------------------------------------


class _Entity:
    """A logical hole, an outside cylinder, or a planar face, with its direction in the document.

    ``is_axis`` marks a cylinder axis, which is a line: its sign carries no meaning.
    """

    def __init__(self, key, faces, direction, point, diameters, is_axis):
        self.key = key
        self.faces = faces
        self.direction = direction
        self.point = point
        self.diameters = diameters
        self.is_axis = is_axis

    def describe(self) -> str:
        return "+".join(f"Face{index}" for index in self.key)


def _cylindrical_faces(shape) -> list:
    """Every ``(index, face)`` of ``shape`` whose surface is a cylinder, index 1-based."""
    return [
        (index, face)
        for index, face in enumerate(getattr(shape, "Faces", ()) or (), start=1)
        if type(getattr(face, "Surface", None)).__name__ == "Cylinder"
    ]


def _is_full_circle_wall(face) -> bool:
    """Whether a cylindrical face wraps a full turn — not a fillet's partial arc.

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
    return _unit(_tuple(surface.Axis)), _tuple(surface.Center)


def _parallel(a, b, tolerance: float = _COAXIAL_ANGLE_TOL) -> bool:
    """Whether two unit directions are parallel, either sense, within ``tolerance`` radians."""
    return abs(_dot(a, b)) >= math.cos(tolerance)


def _axis_offset(axis, point_a, point_b) -> float:
    """The perpendicular distance between two parallel axes through ``point_a`` and ``point_b``."""
    delta = _sub(point_b, point_a)
    return _norm(_sub(delta, _scale(axis, _dot(delta, axis))))


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
        delta = _sub(_tuple(point), origin)
        radial = _sub(delta, _scale(axis, _dot(delta, axis)))
        length = _norm(radial)
        if length <= 0.0:
            raise UnmeasurableGeometry("a wall sample landed on the cylinder's own axis")
        # ``point.add`` returns a Base.Vector without this module importing FreeCAD: the vector
        # class comes from the shape the caller handed in.
        probe = point.add(point.__class__(*_scale(radial, step / length)))
        if _probe_is_inside(shape, probe):
            inside += 1
    return inside * 2 > _WALL_PROBE_SAMPLES


def _group_coaxial(faces: list, same_diameter: bool) -> list[list]:
    """Merge ``(index, face)`` cylinders sharing an axis line into groups (§7.3 rule 2).

    With ``same_diameter`` only equal radii merge, so a stepped outside keeps one entity per
    diameter while a hole keeps its counterbore (rule 4).
    """
    groups: list[list] = []
    for entry in faces:
        axis, point = _axis_of(entry[1])
        radius = float(entry[1].Surface.Radius)
        for group in groups:
            group_axis, group_point = _axis_of(group[0][1])
            if (
                _parallel(axis, group_axis)
                and _axis_offset(group_axis, group_point, point) <= _COAXIAL_OFFSET_TOL
                and (
                    not same_diameter
                    or abs(float(group[0][1].Surface.Radius) - radius) <= _COAXIAL_OFFSET_TOL
                )
            ):
                group.append(entry)
                break
        else:
            groups.append([entry])
    return groups


def _cylinder_entity(group: list) -> _Entity:
    axis, point = _axis_of(group[0][1])
    return _Entity(
        key=tuple(index for index, _ in group),
        faces=[face for _, face in group],
        direction=axis,
        point=point,
        diameters=[2.0 * float(face.Surface.Radius) for _, face in group],
        is_axis=True,
    )


class _Measured:
    """The measured shape with its frame, tolerance floor and lazily derived entities."""

    def __init__(self, shape, frame: _Frame, floor: float):
        self.shape = shape
        self.frame = frame
        self.floor = floor
        self._walls = None

    def _classified_walls(self) -> tuple[list, list]:
        """Full-circle cylinders split into hole walls and outside (boss) walls (§7.3 rules 1, 3).

        :raises UnmeasurableGeometry: a candidate wall could not be classified either way.
        """
        if self._walls is None:
            holes, bosses = [], []
            for entry in _cylindrical_faces(self.shape):
                if not _is_full_circle_wall(entry[1]):
                    continue
                (holes if _is_hole_wall(self.shape, entry[1]) else bosses).append(entry)
            self._walls = (holes, bosses)
        return self._walls

    def holes(self) -> list[_Entity]:
        return [_cylinder_entity(g) for g in _group_coaxial(self._classified_walls()[0], False)]

    def bosses(self) -> list[_Entity]:
        return [_cylinder_entity(g) for g in _group_coaxial(self._classified_walls()[1], True)]

    def planes(self) -> list[_Entity]:
        entities = []
        for index, face in enumerate(getattr(self.shape, "Faces", ()) or (), start=1):
            if type(face.Surface).__name__ != "Plane":
                continue
            u_min, u_max, v_min, v_max = (float(value) for value in face.ParameterRange)
            normal = face.normalAt((u_min + u_max) / 2.0, (v_min + v_max) / 2.0)
            entities.append(
                _Entity((index,), [face], _unit(_tuple(normal)), None, [], is_axis=False)
            )
        return entities

    def linear_band(self) -> float:
        return max(_DEFAULT_LINEAR_ABS, self.floor)


def _matches_diameter(entity: _Entity, diameter: float, band: float) -> bool:
    return any(abs(measured - float(diameter)) <= band for measured in entity.diameters)


def _matches_hole_query(measured: _Measured, entity: _Entity, query: dict) -> bool:
    if "diameter" in query and not _matches_diameter(
        entity, query["diameter"], measured.linear_band()
    ):
        return False
    if "axis" in query:
        wanted = _unit(tuple(float(component) for component in query["axis"]))
        if not _parallel(measured.frame.direction(entity.direction), wanted, _SELECTOR_ANGLE_TOL):
            return False
    return True


def _selected_holes(measured: _Measured, query) -> list[_Entity]:
    """The logical holes ``query`` narrows to; every hole when there is no query.

    :raises UnmeasurableGeometry: a query matches no hole.
    """
    holes = measured.holes()
    if query is None:
        return holes
    chosen = [hole for hole in holes if _matches_hole_query(measured, hole, query)]
    if not chosen:
        raise UnmeasurableGeometry(f"select {query} matches no logical hole")
    return chosen


def _selected_side(measured: _Measured, selector: dict, where: str) -> list[_Entity]:
    """The entities one side of a two-selector check names.

    :raises UnmeasurableGeometry: the side matches nothing.
    """
    if "hole" in selector:
        query = selector["hole"]
        chosen = [hole for hole in measured.holes() if _matches_hole_query(measured, hole, query)]
    elif "normal" in selector["face"]:
        wanted = _unit(tuple(float(component) for component in selector["face"]["normal"]))
        minimum = math.cos(_SELECTOR_ANGLE_TOL)
        chosen = [
            plane
            for plane in measured.planes()
            if _dot(measured.frame.direction(plane.direction), wanted) >= minimum
        ]
    else:
        diameter = selector["face"]["diameter"]
        band = measured.linear_band()
        chosen = [boss for boss in measured.bosses() if _matches_diameter(boss, diameter, band)]
    if not chosen:
        raise UnmeasurableGeometry(f"{where} {selector} matches nothing")
    return chosen


def _surface_distance(a: _Entity, b: _Entity) -> float:
    return min(face_a.distToShape(face_b)[0] for face_a in a.faces for face_b in b.faces)


def _axis_distance(a: _Entity, b: _Entity) -> float:
    """Axis-to-axis distance: the offset of parallel axes, else the skew-line distance."""
    cross = _cross(a.direction, b.direction)
    length = _norm(cross)
    if length <= math.sin(_COAXIAL_ANGLE_TOL):
        return _axis_offset(a.direction, a.point, b.point)
    return abs(_dot(_sub(b.point, a.point), cross)) / length


def _nearest_pairs(measured: _Measured, check: dict, metric) -> list[tuple]:
    """Pair every ``select_b`` entity with its nearest ``select_a`` entity other than itself.

    Returns ``(nearest_a, entity_b, metric_value)`` per ``select_b`` entity.

    :raises UnmeasurableGeometry: a side matches nothing, or nothing but the entity itself.
    """
    side_a = _selected_side(measured, check["select_a"], "select_a")
    side_b = _selected_side(measured, check["select_b"], "select_b")
    pairs = []
    for entity_b in side_b:
        others = [entity_a for entity_a in side_a if entity_a.key != entity_b.key]
        if not others:
            raise UnmeasurableGeometry(f"select_a matches nothing other than {entity_b.describe()}")
        value, nearest = min(
            ((metric(entity_a, entity_b), entity_a) for entity_a in others),
            key=lambda entry: entry[0],
        )
        pairs.append((nearest, entity_b, value))
    return pairs


def _compare_all(fn: str, check: dict, values: list, band: float, note: str, unit: str) -> dict:
    """Pass when every measured value equals ``expect`` within ``band``."""
    expected = float(check["expect"])
    deviations = [abs(value - expected) for value in values]
    passed = all(deviation <= band for deviation in deviations)
    message = f"{fn} {values} vs {expected} {unit}, max deviation {max(deviations)} <= {band}{note}"
    return _check(fn, _one_or_all(values), check["expect"], passed, message, check.get("tol"))


# -- the eleven primitives ------------------------------------------------------------------


def _measure_is_valid_solid(measured: _Measured, check: dict) -> dict:
    shape = measured.shape
    is_valid = bool(shape.isValid())
    solids = len(shape.Solids)
    value = is_valid and solids >= 1
    expected = check["expect"]
    return _check(
        "is_valid_solid", value, expected, value == expected, f"isValid={is_valid} solids={solids}"
    )


def _measure_expect_volume(measured: _Measured, check: dict) -> dict:
    expected = float(check["expect"])
    value = float(measured.shape.Volume)
    band, note = _floored(
        _band(check.get("tol"), expected, None, _DEFAULT_VOLUME_REL), measured.floor
    )
    delta = abs(value - expected)
    return _check(
        "expect_volume",
        value,
        check["expect"],
        delta <= band,
        f"|{value} - {expected}| = {delta} <= {band} mm^3{note}",
        check.get("tol"),
    )


def _optimal_extents(shape) -> list[float]:
    """Exact extents of ``shape``: no triangulation, no tolerance gap (unlike ``BoundBox``)."""
    box = shape.optimalBoundingBox(False, False)
    return [float(box.XLength), float(box.YLength), float(box.ZLength)]


def _measure_expect_bbox(measured: _Measured, check: dict) -> dict:
    """Compare extents measured in the anchor frame, sorted, so axis order does not matter."""
    frame = measured.frame
    shape = measured.shape
    in_frame = shape if frame.is_global else shape.transformed(frame.to_frame_matrix())
    extents = _optimal_extents(in_frame)
    expected = sorted(float(value) for value in check["expect"])
    actual = sorted(extents)
    parts, passed = [], True
    for value, wanted in zip(actual, expected, strict=True):
        band, note = _linear_band(check, wanted, measured.floor)
        delta = abs(value - wanted)
        passed = passed and delta <= band
        parts.append(f"|{value} - {wanted}| = {delta} <= {band}{note}")
    return _check(
        "expect_bbox",
        extents,
        check["expect"],
        passed,
        f"frame extents {extents}; sorted: " + "; ".join(parts),
        check.get("tol"),
    )


def _measure_expect_extent(measured: _Measured, check: dict) -> dict:
    """The part's length along one frame direction, the sign of the direction ignored."""
    import FreeCAD

    direction = _unit(tuple(float(component) for component in check["direction"]))
    along = _unit(measured.frame.to_world(direction))
    helper = (1.0, 0.0, 0.0) if abs(along[0]) < 0.9 else (0.0, 1.0, 0.0)
    first = _unit(_sub(helper, _scale(along, _dot(helper, along))))
    second = _cross(along, first)
    rotation = FreeCAD.Matrix(
        first[0], first[1], first[2], 0.0,
        second[0], second[1], second[2], 0.0,
        along[0], along[1], along[2], 0.0,
        0.0, 0.0, 0.0, 1.0,
    )  # fmt: skip
    value = _optimal_extents(measured.shape.transformed(rotation))[2]
    expected = float(check["expect"])
    band, note = _linear_band(check, expected, measured.floor)
    delta = abs(value - expected)
    return _check(
        "expect_extent",
        value,
        check["expect"],
        delta <= band,
        f"extent along {list(direction)}: |{value} - {expected}| = {delta} <= {band}{note}",
        check.get("tol"),
    )


def _measure_count_cylindrical_holes(measured: _Measured, check: dict) -> dict:
    value = len(_selected_holes(measured, check.get("select")))
    expected = check["expect"]
    return _check(
        "count_cylindrical_holes",
        value,
        expected,
        value == expected,
        f"logical holes {value} vs {expected}",
    )


def _measure_hole_diameter(measured: _Measured, check: dict) -> dict:
    """The through bore of each selected hole: the smallest of its coaxial cylinders."""
    holes = _selected_holes(measured, check.get("select"))
    if not holes:
        raise UnmeasurableGeometry("the shape has no logical hole")
    expected = float(check["expect"])
    band, note = _linear_band(check, expected, measured.floor)
    values = [min(hole.diameters) for hole in holes]
    return _compare_all("hole_diameter", check, values, band, note, "mm")


def _measure_hole_position(measured: _Measured, check: dict) -> dict:
    """Where each selected hole's axis meets the anchor plane, in frame coordinates."""
    holes = _selected_holes(measured, check.get("select"))
    if not holes:
        raise UnmeasurableGeometry("the shape has no logical hole")
    frame = measured.frame
    expected = [float(value) for value in check["expect"]]
    positions, passed, bands = [], True, []
    for hole in holes:
        point = frame.point(hole.point)
        direction = frame.direction(hole.direction)
        if abs(direction[2]) < _PARALLEL_EPSILON:
            raise UnmeasurableGeometry(
                f"hole {hole.describe()} runs parallel to the anchor plane and never meets it"
            )
        step = -point[2] / direction[2]
        position = [point[0] + step * direction[0], point[1] + step * direction[1]]
        positions.append(position)
        for value, wanted in zip(position, expected, strict=True):
            band, _ = _linear_band(check, wanted, measured.floor)
            bands.append(band)
            passed = passed and abs(value - wanted) <= band
    return _check(
        "hole_position",
        _one_or_all(positions),
        check["expect"],
        passed,
        f"axis meets the anchor plane at {positions} vs {expected}, band {max(bands)} mm",
        check.get("tol"),
    )


def _measure_hole_spacing(measured: _Measured, check: dict) -> dict:
    """Axis-to-axis spacing: two selected sides, or the nearest-neighbour pitch of a pattern.

    With ``select_a``/``select_b`` every ``select_b`` hole is measured against its nearest
    ``select_a`` hole. Otherwise ``expect`` is one pitch (a linear pattern) or one per pattern
    direction (a rectangular pattern, e.g. ``[15.0, 15.0]``): every declared pitch must be matched
    by at least one hole's nearest-neighbour distance and every such distance must match a declared
    pitch, so a pattern at the wrong pitch, and one missing a direction, both fail.
    """
    if "select_a" in check:
        pairs = _nearest_pairs(measured, check, _axis_distance)
        expected = float(check["expect"])
        band, note = _linear_band(check, expected, measured.floor)
        values = [value for _, _, value in pairs]
        return _compare_all("hole_spacing", check, values, band, note, "mm")

    raw = check["expect"]
    expected = [float(value) for value in raw] if isinstance(raw, (list, tuple)) else [float(raw)]
    holes = _selected_holes(measured, check.get("select"))
    if len(holes) < 2:
        return _check(
            "hole_spacing",
            None,
            raw,
            False,
            f"{len(holes)} hole(s) measured; spacing needs at least 2",
            check.get("tol"),
        )
    nearest = [
        min(_axis_distance(hole, other) for other in holes if other is not hole) for hole in holes
    ]
    bands = {pitch: _linear_band(check, pitch, measured.floor)[0] for pitch in expected}
    unmatched_pitches = [
        pitch for pitch in expected if not any(abs(gap - pitch) <= bands[pitch] for gap in nearest)
    ]
    stray_gaps = [
        gap for gap in nearest if not any(abs(gap - pitch) <= bands[pitch] for pitch in expected)
    ]
    detail = f"nearest-neighbour gaps {nearest} vs declared {expected}"
    if unmatched_pitches:
        detail += f"; no gap matches pitch(es) {unmatched_pitches}"
    if stray_gaps:
        detail += f"; gap(s) {stray_gaps} match no declared pitch"
    return _check(
        "hole_spacing",
        nearest,
        raw,
        not unmatched_pitches and not stray_gaps,
        detail,
        check.get("tol"),
    )


def _measure_hole_through(measured: _Measured, check: dict) -> dict:
    """Whether every selected hole exits both sides of the material it passes through.

    A through hole's wall spans the whole thickness of material its own axis crosses. That local
    thickness is measured, not the solid's overall extent: on a stepped or filleted part the two
    differ, and comparing against the overall extent grades a through hole in a thin section as
    blind and a blind hole in a thin boss as through.
    """
    expected = check["expect"]
    holes = _selected_holes(measured, check.get("select"))
    if not holes:
        return _check(
            "hole_through", False, expected, expected is False, "no logical hole measured"
        )
    per_hole = []
    for hole in holes:
        wall = _extent_along(_face_vertexes(hole.faces), hole.direction)
        if wall is None:
            raise UnmeasurableGeometry("a hole wall carries too few vertexes to measure")
        material = _local_material_extent(measured.shape, hole)
        per_hole.append(wall >= material - _DEFAULT_LINEAR_ABS)
    value = all(per_hole)
    return _check(
        "hole_through",
        value,
        expected,
        value == expected,
        f"{sum(per_hole)}/{len(per_hole)} hole(s) span the material their axis crosses",
    )


def _local_material_extent(shape, hole: _Entity) -> float:
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
    radius = float(hole.faces[0].Surface.Radius)
    vector = type(shape.BoundBox.Center)
    reach = float(shape.BoundBox.DiagonalLength) * 2.0 or 1.0
    base = vector(*_sub(hole.point, _scale(hole.direction, reach)))
    try:
        wall = next(
            face
            for face in part.makeCylinder(radius, 2.0 * reach, base, vector(*hole.direction)).Faces
            if type(face.Surface).__name__ == "Cylinder"
        )
        material = shape.common(wall)
    except Exception as exc:
        raise UnmeasurableGeometry(f"the hole's wall could not be intersected: {exc}") from exc
    extent = _extent_along(_face_vertexes([material]), hole.direction)
    if extent is None:
        raise UnmeasurableGeometry("no material stands against the hole's wall")
    return extent


def _face_vertexes(shapes) -> list:
    """Every vertex point of every shape in ``shapes``."""
    return [vertex.Point for shape in shapes for vertex in getattr(shape, "Vertexes", ()) or ()]


def _extent_along(points, axis):
    """The span of ``points`` projected onto ``axis``; ``None`` when fewer than two points.

    ``None`` distinguishes an unmeasurable extent from a genuine zero-thickness one.
    """
    if len(points) < 2:
        return None
    projections = [p.x * axis[0] + p.y * axis[1] + p.z * axis[2] for p in points]
    return max(projections) - min(projections)


def _measure_distance_between(measured: _Measured, check: dict) -> dict:
    """``distToShape`` from each ``select_b`` entity to its nearest ``select_a`` entity."""
    pairs = _nearest_pairs(measured, check, _surface_distance)
    expected = float(check["expect"])
    band, note = _linear_band(check, expected, measured.floor)
    values = [value for _, _, value in pairs]
    return _compare_all("distance_between", check, values, band, note, "mm")


def _angle(a: _Entity, b: _Entity) -> float:
    """Degrees between two directions; folded into [0, 90] when either is an axis line."""
    cosine = max(-1.0, min(1.0, _dot(a.direction, b.direction)))
    angle = math.degrees(math.acos(cosine))
    if a.is_axis or b.is_axis:
        angle = min(angle, 180.0 - angle)
    return angle


def _measure_angle_between(measured: _Measured, check: dict) -> dict:
    """The angle between each ``select_b`` entity and its nearest ``select_a`` entity."""
    pairs = _nearest_pairs(measured, check, _surface_distance)
    band = _band(check.get("tol"), float(check["expect"]), _DEFAULT_ANGLE_DEG, None)
    values = [_angle(a, b) for a, b, _ in pairs]
    return _compare_all("angle_between", check, values, band, "", "deg")


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
}


def evaluate_checks(document, shape, anchor_frame, checks) -> tuple[list[dict], dict]:
    """Measure ``shape`` against §7.2 ``checks`` in the declared ``anchor_frame``.

    Every check is validated before anything is measured. A measurement that cannot be taken,
    or that raises, becomes a failing ``invalid_input.unsupported_assertion`` check naming why.

    :param document: the document the frame's ``ref`` is looked up in.
    :param shape: the measured shape, in document coordinates (see :func:`document_shape`).
    :param anchor_frame: the declared ``{kind, ref}``, or ``None`` for the global frame.
    :param checks: ``{fn, expect, ...}`` mappings, every ``fn`` in ``ASSERTION_FNS``.
    :returns: one ``Check`` per entry, in order, and the resolved frame for the banner.
    :raises ValidationError: a check or the frame declaration is malformed, or the shape's
        tolerance cannot be read.
    """
    for check in checks:
        validate_check(check)
    frame = resolve_anchor_frame(document, shape, anchor_frame)
    if not checks:
        return [], frame.banner
    measured = _Measured(shape, frame, shape_floor(shape))
    results = []
    for check in checks:
        fn = check["fn"]
        try:
            results.append(_MEASUREMENTS[fn](measured, check))
        except UnmeasurableGeometry as exc:
            results.append(_invalid(fn, f"measurement could not be taken: {exc}"))
        except Exception as exc:  # noqa: BLE001 - a measurement failure is a failing check
            results.append(
                _invalid(fn, f"measurement could not be taken: {type(exc).__name__}: {exc}")
            )
    return results, frame.banner
