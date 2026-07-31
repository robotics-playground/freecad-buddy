"""The eight ``sketch_*`` mutation use cases.

Each tool validates its typed input, then executes one closure through
``transaction.run_mutation`` and rebinds the document that call returns into the registry. The
returned envelope carries the common ``mutation`` block plus a ``sketch_state`` block read back
through ``verify_sketch``.

Wire conventions: geometry is addressed by 0-based sketch-local ``geo_id``; constraint ids are
1-based solver ids naming ``Constraints[id-1]``; dimensional values arrive as ``{value, unit}``
and angles are converted from degrees to radians before any FreeCAD call. An empty sketch has
``DoF == 0`` and is therefore fully constrained; adding geometry without the constraints that
pin it leaves ``DoF > 0``, which ``post_verify`` hard-fails and rolls back.

Stdlib + FreeCAD App modules only; version-sensitive calls go through ``shim``.
"""

from __future__ import annotations

import math
from typing import Callable

from freecad_buddy.contracts import ResultEnvelope
from freecad_buddy.usecases import confirm, shim, transaction, verify
from freecad_buddy.usecases.documents import DocumentRegistry, ValidationError

# Sketcher GeoEnum: -1 is the horizontal axis (pos=none) and the root point (pos=start),
# -2 the vertical axis, and external geometry counts down from -3.
_H_AXIS = -1
_V_AXIS = -2
_EXTERNAL_FIRST = -3

# Sketcher PointPos: 0 none (the edge), 1 start, 2 end, 3 mid.
_POINT_POS = (0, 1, 2, 3)

# Base-plane rotation quaternions, matching FreeCAD's own Origin XY_Plane / XZ_Plane / YZ_Plane
# placements so a base-plane sketch lands in the same frame as a datum-plane one.
_BASE_PLANES = {
    "XY": (0.0, 0.0, 0.0, 1.0),
    "XZ": (0.7071067811865475, 0.0, 0.0, 0.7071067811865475),
    "YZ": (0.5, 0.5, 0.5, 0.5),
}

_ANGLE_UNITS = frozenset({"deg"})
_LENGTH_UNITS = frozenset({"mm"})

# Constraint arities verified against Sketcher ConstraintPyImp.cpp. Each entry lists the
# argument tuples the C++ constructor accepts for that type, in the form this module builds
# them; a request that matches none of its type's forms is rejected before the bracket opens.
_GEO_ONLY_PAIR = frozenset({"Parallel", "Equal"})
_VALUE_ON_GEO = frozenset({"Radius", "Diameter"})
_ANGLE_TYPES = frozenset({"Angle"})
_LENGTH_TYPES = frozenset({"Distance", "DistanceX", "DistanceY", "Radius", "Diameter"})
_DIMENSIONAL = _LENGTH_TYPES | _ANGLE_TYPES
# Datum sign rules verified against SketchObjectConstraints.cpp:200-204: setDatum refuses a
# non-positive Radius/Diameter/Weight and a zero Distance, and constrains no other type.
_POSITIVE_DATUM_TYPES = frozenset({"Radius", "Diameter", "Weight"})
_NONZERO_DATUM_TYPES = frozenset({"Distance"})

_CONSTRAINT_TYPES = frozenset(
    {
        "Coincident",
        "Horizontal",
        "Vertical",
        "Parallel",
        "Perpendicular",
        "Tangent",
        "Equal",
        "Symmetric",
        "PointOnObject",
        "Block",
        "Distance",
        "DistanceX",
        "DistanceY",
        "Radius",
        "Diameter",
        "Angle",
    }
)

_GEOMETRY_KINDS = frozenset({"line_segment", "circle", "arc_of_circle", "point"})


def _require_sketcher() -> None:
    """Raise when the running build exposes no usable Sketcher constraint constructor."""
    if not shim.sketcher_available():
        raise ValidationError("Sketcher is unavailable on this FreeCAD build")


def _resolve_sketch(document: object, name: str | None) -> object:
    """Return the ``Sketcher::`` object named ``name``, or raise ``ValidationError``."""
    if not name:
        raise ValidationError("missing required 'sketch' name")
    obj = document.getObject(name)
    if obj is None:
        raise ValidationError(f"unknown object: {name}")
    if not str(getattr(obj, "TypeId", "")).startswith("Sketcher::"):
        raise ValidationError(f"object is not a sketch: {name}")
    return obj


def _quantity_value(value: object, allowed_units: frozenset[str], what: str) -> float:
    """Return a ``{value, unit}`` quantity's magnitude after checking its unit.

    :param allowed_units: the units this dimension accepts; a unit outside the set is rejected
        rather than silently reinterpreted.
    :raises ValidationError: the quantity is malformed or carries a unit for another dimension.
    """
    if not isinstance(value, dict):
        raise ValidationError(f"{what} must be a {{value, unit}} quantity, got {value!r}")
    magnitude = value.get("value")
    unit = value.get("unit")
    if not isinstance(magnitude, (int, float)) or isinstance(magnitude, bool):
        raise ValidationError(f"{what} value must be a number, got {magnitude!r}")
    if not math.isfinite(float(magnitude)):
        raise ValidationError(f"{what} value must be finite, got {magnitude!r}")
    if unit not in allowed_units:
        raise ValidationError(f"{what} unit must be one of {sorted(allowed_units)}, got {unit!r}")
    return float(magnitude)


def _angle_radians(value: object, what: str) -> float:
    """Convert a wire angle quantity to radians; the FreeCAD API reads a bare float as radians."""
    return math.radians(_quantity_value(value, _ANGLE_UNITS, what))


def _length_mm(value: object, what: str) -> float:
    """Return a wire length quantity in millimetres, FreeCAD's internal length unit."""
    return _quantity_value(value, _LENGTH_UNITS, what)


def _datum_value(constraint_type: str, value: object) -> float:
    """Convert a wire datum quantity to the raw float the FreeCAD API expects for its type."""
    if constraint_type in _ANGLE_TYPES:
        return _angle_radians(value, f"{constraint_type} value")
    return _length_mm(value, f"{constraint_type} value")


def _positive_datum(constraint_type: str, value: object, what: str) -> float:
    """Convert a datum quantity and reject the values FreeCAD's ``setDatum`` refuses.

    ``SketchObjectConstraints.cpp:200-204`` returns an error for a non-positive
    ``Radius``/``Diameter``/``Weight`` and for a zero ``Distance``; every other datum, including
    a negative ``Angle`` or ``Distance``, is accepted. Rejecting only what the API rejects keeps
    a sign error outside the transaction without refusing a legal value.
    """
    datum = _datum_value(constraint_type, value)
    if constraint_type in _POSITIVE_DATUM_TYPES and datum <= 0.0:
        raise ValidationError(
            f"{what} {constraint_type} value must be positive, got {datum}"
        )
    if constraint_type in _NONZERO_DATUM_TYPES and datum == 0.0:
        raise ValidationError(f"{what} {constraint_type} value must be non-zero")
    return datum


def _point(raw: object, what: str) -> object:
    """Build an ``App.Vector`` from a wire ``[x, y]`` or ``[x, y, z]`` coordinate list."""
    import FreeCAD

    if not isinstance(raw, (list, tuple)) or not 2 <= len(raw) <= 3:
        raise ValidationError(f"{what} must be a list of 2 or 3 numbers, got {raw!r}")
    for component in raw:
        if not isinstance(component, (int, float)) or isinstance(component, bool):
            raise ValidationError(f"{what} components must be numbers, got {raw!r}")
        if not math.isfinite(float(component)):
            raise ValidationError(f"{what} components must be finite, got {raw!r}")
    x, y = float(raw[0]), float(raw[1])
    z = float(raw[2]) if len(raw) == 3 else 0.0
    return FreeCAD.Vector(x, y, z)


def _build_geometry(spec: object, index: int) -> tuple[object, bool]:
    """Build one FreeCAD geometry object from a typed spec, with its construction flag.

    :raises ValidationError: the kind is unknown or a field the kind requires is absent.
    """
    import Part

    what = f"geometry[{index}]"
    if not isinstance(spec, dict):
        raise ValidationError(f"{what} must be an object, got {spec!r}")
    kind = spec.get("kind")
    if kind not in _GEOMETRY_KINDS:
        raise ValidationError(f"{what} kind must be one of {sorted(_GEOMETRY_KINDS)}, got {kind!r}")
    construction = bool(spec.get("construction", False))

    if kind == "line_segment":
        start = _point(spec.get("start"), f"{what}.start")
        end = _point(spec.get("end"), f"{what}.end")
        if start.distanceToPoint(end) == 0.0:
            raise ValidationError(f"{what} start and end are the same point")
        return Part.LineSegment(start, end), construction

    if kind == "point":
        return Part.Point(_point(spec.get("center"), f"{what}.center")), construction

    import FreeCAD

    center = _point(spec.get("center"), f"{what}.center")
    radius = _length_mm(spec.get("radius"), f"{what}.radius")
    if radius <= 0.0:
        raise ValidationError(f"{what} radius must be positive, got {radius}")
    circle = Part.Circle(center, FreeCAD.Vector(0, 0, 1), radius)
    if kind == "circle":
        return circle, construction

    start_angle = _angle_radians(spec.get("start_angle"), f"{what}.start_angle")
    end_angle = _angle_radians(spec.get("end_angle"), f"{what}.end_angle")
    # The span is taken modulo a full turn, so 0..360 is as degenerate as 0..0.
    if math.isclose(math.fmod(end_angle - start_angle, 2 * math.pi), 0.0, abs_tol=1e-12):
        raise ValidationError(
            f"{what} start_angle and end_angle span zero or a whole turn"
        )
    return Part.ArcOfCircle(circle, start_angle, end_angle), construction


def _external_curve_count(sketch_obj: object) -> int:
    """Return how many external curves the sketch has projected.

    The negative geo-id space counts projected curves, which is the size of the ``ExternalGeo``
    geometry list (``SketchObject.h:106,307`` — ``getExternalGeometryCount()`` is that size, and
    is C++-only). It includes the two sketch axes ``ExternalGeo`` always carries, so they are
    discounted. A build without the property falls back to the ``ExternalGeometry`` link count,
    which undercounts a multi-curve link but never invents ids the sketch does not have.
    """
    external_geo = getattr(sketch_obj, "ExternalGeo", None)
    if external_geo is not None:
        return max(len(external_geo) - 2, 0)
    return len(getattr(sketch_obj, "ExternalGeometry", []) or [])


def _check_geo_id(raw: object, sketch_obj: object, what: str) -> int:
    """Validate a sketch-local geo id.

    Three ranges are legal: an existing 0-based geometry index, the -1/-2 sketch axes, and an
    external-geometry id counting down from -3, whose depth is bounded by the projected curves.

    The bound is the projected-curve count, not the ``ExternalGeometry`` link count: one link
    entry can project several curves (a face contributes each of its edges), and the negative id
    space counts curves. ``SketchObject.h:1222`` names the two as distinct index spaces.
    """
    if not isinstance(raw, int) or isinstance(raw, bool):
        raise ValidationError(f"{what} must be an integer geo_id, got {raw!r}")
    if raw in (_H_AXIS, _V_AXIS):
        return raw
    if raw <= _EXTERNAL_FIRST:
        external = _external_curve_count(sketch_obj)
        if -raw - -_EXTERNAL_FIRST >= external:
            raise ValidationError(
                f"{what} geo_id {raw} names external geometry the sketch has not projected "
                f"({external} projected)"
            )
        return raw
    geometry_count = int(sketch_obj.GeometryCount)
    if not 0 <= raw < geometry_count:
        raise ValidationError(
            f"{what} geo_id {raw} is outside the sketch (0..{geometry_count - 1}, or -1/-2 axes)"
        )
    return raw


def _check_pos(raw: object, what: str) -> int:
    """Validate a PointPos: 0 none, 1 start, 2 end, 3 mid."""
    if raw not in _POINT_POS or isinstance(raw, bool):
        raise ValidationError(f"{what} must be a PointPos in {list(_POINT_POS)}, got {raw!r}")
    return int(raw)


def _constraint_args(spec: object, index: int, sketch_obj: object) -> tuple:
    """Build the verified ``Sketcher.Constraint`` argument tuple for one typed constraint spec.

    Each type is matched to the arities its C++ constructor accepts; a request that matches none
    is rejected here so an arity violation never reaches the solver inside a transaction.

    :raises ValidationError: unknown type, bad geo id or PointPos, or an arity the type rejects.
    """
    what = f"constraints[{index}]"
    if not isinstance(spec, dict):
        raise ValidationError(f"{what} must be an object, got {spec!r}")
    constraint_type = spec.get("type")
    if constraint_type not in _CONSTRAINT_TYPES:
        raise ValidationError(
            f"{what} type must be one of {sorted(_CONSTRAINT_TYPES)}, got {constraint_type!r}"
        )
    first = _check_geo_id(spec.get("first"), sketch_obj, f"{what}.first")
    has_second = spec.get("second") is not None
    has_value = spec.get("value") is not None
    second = (
        _check_geo_id(spec.get("second"), sketch_obj, f"{what}.second") if has_second else None
    )
    third = (
        _check_geo_id(spec.get("third"), sketch_obj, f"{what}.third")
        if spec.get("third") is not None
        else None
    )

    if constraint_type == "Coincident":
        if second is None or spec.get("first_pos") is None or spec.get("second_pos") is None:
            raise ValidationError(
                f"{what} Coincident requires first, first_pos, second and second_pos"
            )
        return (
            "Coincident",
            first,
            _check_pos(spec.get("first_pos"), f"{what}.first_pos"),
            second,
            _check_pos(spec.get("second_pos"), f"{what}.second_pos"),
        )

    if constraint_type in ("Horizontal", "Vertical", "Block"):
        if has_second or has_value:
            raise ValidationError(f"{what} {constraint_type} takes only 'first'")
        return (constraint_type, first)

    if constraint_type in _VALUE_ON_GEO:
        if has_second or not has_value:
            raise ValidationError(f"{what} {constraint_type} takes only 'first' and 'value'")
        if first < 0:
            raise ValidationError(
                f"{what} {constraint_type} needs a curve in the sketch; geo_id {first} is an "
                "axis or external geometry and has no editable radius"
            )
        return (
            constraint_type,
            first,
            _positive_datum(constraint_type, spec.get("value"), what),
        )

    if constraint_type in _GEO_ONLY_PAIR:
        if second is None or has_value:
            raise ValidationError(f"{what} {constraint_type} takes only 'first' and 'second'")
        return (constraint_type, first, second)

    if constraint_type in ("Perpendicular", "Tangent"):
        if second is None or has_value:
            raise ValidationError(f"{what} {constraint_type} takes only 'first' and 'second'")
        has_first_pos = spec.get("first_pos") is not None
        has_second_pos = spec.get("second_pos") is not None
        if has_first_pos != has_second_pos:
            raise ValidationError(
                f"{what} {constraint_type} endpoint form requires both first_pos and second_pos; "
                "omit both for the edge-to-edge form"
            )
        if has_first_pos:
            return (
                constraint_type,
                first,
                _check_pos(spec.get("first_pos"), f"{what}.first_pos"),
                second,
                _check_pos(spec.get("second_pos"), f"{what}.second_pos"),
            )
        return (constraint_type, first, second)

    if constraint_type == "PointOnObject":
        if second is None or spec.get("first_pos") is None or has_value:
            raise ValidationError(f"{what} PointOnObject requires first, first_pos and second")
        return (
            "PointOnObject",
            first,
            _check_pos(spec.get("first_pos"), f"{what}.first_pos"),
            second,
        )

    if constraint_type == "Symmetric":
        if (
            second is None
            or third is None
            or spec.get("first_pos") is None
            or spec.get("second_pos") is None
        ):
            raise ValidationError(
                f"{what} Symmetric requires first, first_pos, second, second_pos and third"
            )
        args = (
            "Symmetric",
            first,
            _check_pos(spec.get("first_pos"), f"{what}.first_pos"),
            second,
            _check_pos(spec.get("second_pos"), f"{what}.second_pos"),
            third,
        )
        # Symmetry about a point takes the third element's position; about a line it does not.
        if spec.get("third_pos") is None:
            return args
        return args + (_check_pos(spec.get("third_pos"), f"{what}.third_pos"),)

    if not has_value:
        raise ValidationError(f"{what} {constraint_type} requires a 'value' quantity")
    value = _positive_datum(constraint_type, spec.get("value"), what)
    if constraint_type == "Angle" and second is not None:
        # Angle has both an edge-to-edge form and a 5-arg endpoint form
        # (ConstraintPyImp.cpp:685-693). Dropping half-given positions would silently build the
        # edge-to-edge constraint instead of the endpoint one the caller asked for.
        has_first_pos = spec.get("first_pos") is not None
        has_second_pos = spec.get("second_pos") is not None
        if has_first_pos != has_second_pos:
            raise ValidationError(
                f"{what} Angle endpoint form requires both first_pos and second_pos; "
                "omit both for the edge-to-edge form"
            )
        if has_first_pos:
            return (
                "Angle",
                first,
                _check_pos(spec.get("first_pos"), f"{what}.first_pos"),
                second,
                _check_pos(spec.get("second_pos"), f"{what}.second_pos"),
                value,
            )
        return ("Angle", first, second, value)
    if second is not None:
        if spec.get("first_pos") is None or spec.get("second_pos") is None:
            raise ValidationError(
                f"{what} {constraint_type} between two geometries requires first_pos "
                "and second_pos"
            )
        return (
            constraint_type,
            first,
            _check_pos(spec.get("first_pos"), f"{what}.first_pos"),
            second,
            _check_pos(spec.get("second_pos"), f"{what}.second_pos"),
            value,
        )
    if spec.get("first_pos") is not None:
        raise ValidationError(
            f"{what} {constraint_type} with a first_pos also requires 'second' and 'second_pos'"
        )
    return (constraint_type, first, value)


def _resolve_constraint_index(sketch_obj: object, reference: object) -> int:
    """Map a wire constraint reference to its 0-based FreeCAD index.

    A reference is either a 1-based solver id naming ``Constraints[id-1]`` or a constraint Name.

    :raises ValidationError: the id is out of range or no constraint carries that name.
    """
    constraints = list(getattr(sketch_obj, "Constraints", []) or [])
    if isinstance(reference, bool) or reference is None:
        raise ValidationError(f"constraint must be a 1-based id or a name, got {reference!r}")
    if isinstance(reference, int):
        if not 1 <= reference <= len(constraints):
            raise ValidationError(
                f"constraint id {reference} is outside the sketch (1..{len(constraints)})"
            )
        return reference - 1
    if isinstance(reference, str):
        # An unnamed constraint carries Name == "", so an empty reference would match the first
        # of them rather than naming nothing.
        if not reference:
            raise ValidationError("constraint name must be non-empty")
        for index, constraint in enumerate(constraints):
            if getattr(constraint, "Name", "") == reference:
                return index
        raise ValidationError(f"no constraint named {reference!r} in the sketch")
    raise ValidationError(f"constraint must be a 1-based id or a name, got {reference!r}")


def _sketch_state(registry: DocumentRegistry, doc: str, sketch: str) -> dict:
    """Read the post-op sketch summary through ``verify_sketch``.

    Returns the ``verify_sketch`` subject fields as a ``fcb.sketch-state/1`` block. A sketch the
    op deleted or rolled back out of existence cannot be graded, so the block reports
    ``readable: False`` and carries no grading fields rather than a null a consumer would
    dereference. ``readable`` tracks whether the grading fields are actually present, so a
    subject the verify path could not populate reports ``False`` rather than an empty grade.
    ``schema``, ``sketch`` and ``readable`` are present on both paths.
    """
    unreadable = {"schema": "fcb.sketch-state/1", "sketch": sketch, "readable": False}
    try:
        envelope = verify.verify_sketch(registry, doc=doc, sketch=sketch)
    except ValidationError:
        return unreadable
    subject = (envelope.get("structured_content") or {}).get("subject") or {}
    if "dof" not in subject or "fully_constrained" not in subject:
        return unreadable
    return {"schema": "fcb.sketch-state/1", "sketch": sketch, "readable": True, **subject}


def _ids_survived(envelope: ResultEnvelope) -> bool:
    """Report whether the ids an op collected still name anything in the document.

    Only a committed mutation leaves them addressable. A proven rollback removed them, and an
    unproven one (``rolled_back`` false, snapshot kept — ``transaction.py:501-517``) cannot say
    they exist, so both suppress the ids rather than naming geometry a caller may not be able to
    reach.
    """
    return str(envelope.get("status")) == "OK"


def _selector_subelement(selector: object) -> tuple[str, str]:
    """Return ``(object_name, subelement)`` from a contracts ``Selector``.

    Only the ``mapped_name`` variant resolves without a geometric query; a ``geometric``
    selector is rejected until the resolver that grades a query lands.

    :raises ValidationError: the selector is malformed or of an unresolvable kind.
    """
    if not isinstance(selector, dict):
        raise ValidationError(f"selector must be an object, got {selector!r}")
    kind = selector.get("kind")
    obj = selector.get("object")
    if not isinstance(obj, str) or not obj:
        raise ValidationError("selector requires an 'object' name")
    if kind != "mapped_name":
        raise ValidationError(
            f"selector kind must be 'mapped_name'; {kind!r} is not resolvable by a sketch tool"
        )
    mapped = selector.get("mapped_name")
    if not isinstance(mapped, str) or not mapped:
        raise ValidationError("a mapped_name selector requires a 'mapped_name'")
    return obj, mapped


def _sketch_mutation(
    registry: DocumentRegistry,
    doc: str | None,
    sketch: str,
    label: str,
    tool: str,
    params: dict,
    op: Callable[[object], list[str]],
    audit_sink: object = None,
    precheck: Callable[[object], None] | None = None,
) -> ResultEnvelope:
    """Run ``op`` through the mutation bracket and attach the post-op ``sketch_state``.

    The document is resolved once and passed into ``run_mutation`` (re-entering the registry lock
    would deadlock), and the document that call returns is rebound into the registry on every
    exit path: the snapshot-restore rollback closes and reopens the document, so a handle left
    pointing at the original object would address a closed document.

    :param sketch: the sketch whose state the envelope reports; it need not exist yet.
    :param op: applies the typed operation and returns the names of the objects it touched.
    :param precheck: validates the request against the resolved document before the bracket
        opens, so a malformed request raises ``ValidationError`` without writing a snapshot.
    :raises ValidationError: the call carries no confirm authorizing it, or the request is
        malformed; neither writes a snapshot nor opens a transaction.
    """

    rebound: list = []

    def call(handle: str, document: object):
        approval = confirm.gate_mutation(document, handle, tool, params)
        if precheck is not None:
            precheck(document)
        confirm.audit_approval(audit_sink, approval, params)
        result = transaction.run_mutation(
            document, handle, label, op, audit_sink=audit_sink, tool=tool, params=params
        )
        rebound.append(result[0])
        return result

    try:
        _, envelope = registry.with_document(doc, call)
    finally:
        # run_mutation can raise after the snapshot restore already closed and reopened the
        # document, so the handle is rebound from whatever the bracket last reached.
        if rebound:
            registry.rebind(doc, rebound[-1])
    envelope["structured_content"]["sketch"] = sketch
    envelope["structured_content"]["sketch_state"] = _sketch_state(registry, doc, sketch)
    return envelope


def sketch_create(
    registry: DocumentRegistry,
    doc: str | None = None,
    name: str | None = None,
    plane: str | None = None,
    face: dict | None = None,
    confirm: dict | None = None,
    audit_sink: object = None,
) -> ResultEnvelope:
    """Create a sketch on a base plane or attached to a planar face.

    Exactly one of ``plane`` (``"XY"``/``"XZ"``/``"YZ"``) and ``face`` (a ``mapped_name``
    selector) targets the sketch. A base-plane sketch carries the plane's rotation in its
    placement; a face-attached sketch is attached through ``AttachmentSupport`` with
    ``MapMode="FlatFace"``. The new sketch is empty, so it commits with ``DoF == 0``.

    :raises ValidationError: no or both targets given, an unknown plane, a name already in use,
        or a face selector that does not name a planar face.
    """
    _require_sketcher()
    if not name:
        raise ValidationError("sketch_create requires a 'name'")
    if (plane is None) == (face is None):
        raise ValidationError("sketch_create requires exactly one of 'plane' and 'face'")
    if plane is not None and plane not in _BASE_PLANES:
        raise ValidationError(f"plane must be one of {sorted(_BASE_PLANES)}, got {plane!r}")
    support = _selector_subelement(face) if face is not None else None

    def precheck(document: object) -> None:
        if document.getObject(name) is not None:
            raise ValidationError(f"an object named {name} already exists")
        if support is not None:
            target = document.getObject(support[0])
            if target is None:
                raise ValidationError(f"unknown object in face selector: {support[0]}")
            _require_planar_face(target, support[1])

    def op(document: object) -> list[str]:
        import FreeCAD

        sketch = document.addObject("Sketcher::SketchObject", name)
        if sketch.Name != name:
            raise ValidationError(f"{name} is not a usable FreeCAD object name")
        if support is None:
            sketch.Placement = FreeCAD.Placement(
                FreeCAD.Vector(0, 0, 0), FreeCAD.Rotation(*_BASE_PLANES[plane])
            )
            return [name]
        target = document.getObject(support[0])
        if target is None:
            raise ValidationError(f"unknown object in face selector: {support[0]}")
        _require_planar_face(target, support[1])
        shim.set_attachment(sketch, [(target, [support[1]])], "FlatFace")
        return [name]

    params = {"doc": doc, "name": name, "plane": plane, "face": face, "confirm": confirm}
    return _sketch_mutation(
        registry,
        doc,
        name,
        f"create sketch {name}",
        "sketch_create",
        params,
        op,
        audit_sink,
        precheck,
    )


def _require_planar_face(target: object, subelement: str) -> None:
    """Raise unless ``subelement`` names a planar face on ``target``'s shape."""
    shape = getattr(target, "Shape", None)
    if shape is None:
        raise ValidationError(f"{target.Name} carries no shape to attach to")
    try:
        element = shape.getElement(subelement)
    except Exception as exc:  # noqa: BLE001 - an unresolvable subelement is caller input
        raise ValidationError(f"unresolvable face selector {subelement!r}: {exc}") from exc
    surface = getattr(element, "Surface", None)
    if type(surface).__name__ != "Plane":
        raise ValidationError(f"{subelement} on {target.Name} is not a planar face")


class _PendingGeometry:
    """A sketch view whose ``GeometryCount`` includes geometry a pending op will add.

    Constraints sent alongside new geometry address ids that do not exist yet, so validating them
    before the bracket opens needs the count the additions will produce.
    """

    def __init__(self, sketch_obj: object, pending: int) -> None:
        self._sketch_obj = sketch_obj
        self.GeometryCount = int(sketch_obj.GeometryCount) + pending

    def __getattr__(self, name: str) -> object:
        return getattr(self._sketch_obj, name)


def _check_constraint_specs(sketch_obj: object, constraints: list | None, pending: int = 0) -> None:
    """Validate every constraint spec's type, arity, geo ids and quantities without applying any.

    :param pending: geometry a paired op will add before the constraints are applied.
    :raises ValidationError: any spec is malformed.
    """
    if not constraints:
        return
    target = _PendingGeometry(sketch_obj, pending) if pending else sketch_obj
    for index, spec in enumerate(constraints):
        _constraint_args(spec, index, target)


def _apply_constraints(sketch_obj: object, constraints: list, collected: list[int]) -> None:
    """Add typed constraints to a sketch, appending their 1-based solver ids to ``collected``.

    Every spec's arity is validated against the verified constraint constructor before the first
    ``addConstraint`` call. A solver-side failure part-way through the list is undone by the
    enclosing transaction, not here.
    """
    import Sketcher

    built = [_constraint_args(spec, index, sketch_obj) for index, spec in enumerate(constraints)]
    for spec, args in zip(constraints, built):
        index = int(sketch_obj.addConstraint(Sketcher.Constraint(*args)))
        name = spec.get("name")
        if name:
            sketch_obj.renameConstraint(index, str(name))
        if spec.get("driving") is False and args[0] in _DIMENSIONAL:
            sketch_obj.setDriving(index, False)
        collected.append(index + 1)


def sketch_add_geometry(
    registry: DocumentRegistry,
    doc: str | None = None,
    sketch: str | None = None,
    geometry: list | None = None,
    constraints: list | None = None,
    confirm: dict | None = None,
    audit_sink: object = None,
) -> ResultEnvelope:
    """Add typed geometry to a sketch, returning the new 0-based ``geo_ids``.

    ``constraints`` are applied inside the same transaction as the geometry, so the sketch is
    already pinned when ``post_verify`` grades it. Geometry sent alone leaves ``DoF > 0``, which
    ``post_verify`` hard-fails and rolls back — including the geometry — so a shape reaches
    ``FullyConstrained`` only when its constraints travel with it.

    :raises ValidationError: the sketch is unknown, or a geometry or constraint spec is
        malformed.
    """
    _require_sketcher()
    if not geometry:
        raise ValidationError("sketch_add_geometry requires a non-empty 'geometry' list")

    geo_ids: list[int] = []
    constraint_ids: list[int] = []

    def precheck(document: object) -> None:
        sketch_obj = _resolve_sketch(document, sketch)
        for index, spec in enumerate(geometry):
            _build_geometry(spec, index)
        # Constraint geo ids address geometry this call has not added yet, so their ids are
        # validated against the count the additions will produce.
        _check_constraint_specs(sketch_obj, constraints, len(geometry))

    def op(document: object) -> list[str]:
        sketch_obj = _resolve_sketch(document, sketch)
        for index, spec in enumerate(geometry):
            geo, construction = _build_geometry(spec, index)
            geo_ids.append(int(sketch_obj.addGeometry(geo, construction)))
        if constraints:
            _apply_constraints(sketch_obj, constraints, constraint_ids)
        return [sketch_obj.Name]

    params = {
        "doc": doc,
        "sketch": sketch,
        "geometry": geometry,
        "constraints": constraints,
        "confirm": confirm,
    }
    envelope = _sketch_mutation(
        registry,
        doc,
        sketch,
        f"add geometry to {sketch}",
        "sketch_add_geometry",
        params,
        op,
        audit_sink,
        precheck,
    )
    # A non-committed add leaves none of its geometry addressable, so reporting the ids it held
    # mid-transaction would name geometry a caller cannot reach.
    survived = _ids_survived(envelope)
    envelope["structured_content"]["geo_ids"] = geo_ids if survived else []
    envelope["structured_content"]["constraint_ids"] = constraint_ids if survived else []
    return envelope


def sketch_remove_geometry(
    registry: DocumentRegistry,
    doc: str | None = None,
    sketch: str | None = None,
    geo_ids: list | None = None,
    confirm: dict | None = None,
    audit_sink: object = None,
) -> ResultEnvelope:
    """Remove sketch geometry by 0-based ``geo_id``; FreeCAD drops its dependent constraints.

    Ids are deleted highest-first so a deletion does not renumber an id still to be removed.

    :raises ValidationError: the sketch is unknown or an id is not an existing geometry index.
    """
    _require_sketcher()
    if not geo_ids:
        raise ValidationError("sketch_remove_geometry requires a non-empty 'geo_ids' list")

    def _targets(document: object) -> tuple[object, set]:
        sketch_obj = _resolve_sketch(document, sketch)
        count = int(sketch_obj.GeometryCount)
        targets = set()
        for raw in geo_ids:
            if not isinstance(raw, int) or isinstance(raw, bool) or not 0 <= raw < count:
                raise ValidationError(f"geo_id {raw!r} is outside the sketch (0..{count - 1})")
            targets.add(int(raw))
        return sketch_obj, targets

    def precheck(document: object) -> None:
        _targets(document)

    def op(document: object) -> list[str]:
        sketch_obj, targets = _targets(document)
        for geo_id in sorted(targets, reverse=True):
            sketch_obj.delGeometry(geo_id)
        return [sketch_obj.Name]

    params = {"doc": doc, "sketch": sketch, "geo_ids": geo_ids, "confirm": confirm}
    return _sketch_mutation(
        registry,
        doc,
        sketch,
        f"remove geometry from {sketch}",
        "sketch_remove_geometry",
        params,
        op,
        audit_sink,
        precheck,
    )


def sketch_add_constraint(
    registry: DocumentRegistry,
    doc: str | None = None,
    sketch: str | None = None,
    constraints: list | None = None,
    confirm: dict | None = None,
    audit_sink: object = None,
) -> ResultEnvelope:
    """Add typed constraints to a sketch, returning their 1-based solver ids.

    Arity is checked against the verified constraint constructor before the transaction opens.
    A conflicting or malformed set fails ``post_verify`` and rolls back with the offending ids
    named in ``sketch_state``; redundant constraints warn and commit.

    :raises ValidationError: the sketch is unknown, or a constraint's type, arity, geo id,
        PointPos or value quantity is invalid.
    """
    _require_sketcher()
    if not constraints:
        raise ValidationError("sketch_add_constraint requires a non-empty 'constraints' list")

    constraint_ids: list[int] = []

    def precheck(document: object) -> None:
        _check_constraint_specs(_resolve_sketch(document, sketch), constraints)

    def op(document: object) -> list[str]:
        sketch_obj = _resolve_sketch(document, sketch)
        _apply_constraints(sketch_obj, constraints, constraint_ids)
        return [sketch_obj.Name]

    params = {"doc": doc, "sketch": sketch, "constraints": constraints, "confirm": confirm}
    envelope = _sketch_mutation(
        registry,
        doc,
        sketch,
        f"add constraints to {sketch}",
        "sketch_add_constraint",
        params,
        op,
        audit_sink,
        precheck,
    )
    # A non-committed add leaves none of its constraints in the sketch, so reporting the solver
    # ids it held mid-transaction would name constraints a caller cannot address.
    envelope["structured_content"]["constraint_ids"] = (
        constraint_ids if _ids_survived(envelope) else []
    )
    return envelope


def sketch_remove_constraint(
    registry: DocumentRegistry,
    doc: str | None = None,
    sketch: str | None = None,
    constraints: list | None = None,
    confirm: dict | None = None,
    audit_sink: object = None,
) -> ResultEnvelope:
    """Remove constraints named by 1-based solver id or by name.

    Removals run highest-index-first so an earlier deletion does not renumber a later target.

    :raises ValidationError: the sketch is unknown, or a reference names no constraint.
    """
    _require_sketcher()
    if not constraints:
        raise ValidationError("sketch_remove_constraint requires a non-empty 'constraints' list")

    def _indices(document: object) -> tuple[object, set]:
        sketch_obj = _resolve_sketch(document, sketch)
        return sketch_obj, {_resolve_constraint_index(sketch_obj, ref) for ref in constraints}

    def precheck(document: object) -> None:
        _indices(document)

    def op(document: object) -> list[str]:
        sketch_obj, indices = _indices(document)
        for index in sorted(indices, reverse=True):
            sketch_obj.delConstraint(index)
        return [sketch_obj.Name]

    params = {"doc": doc, "sketch": sketch, "constraints": constraints, "confirm": confirm}
    return _sketch_mutation(
        registry,
        doc,
        sketch,
        f"remove constraints from {sketch}",
        "sketch_remove_constraint",
        params,
        op,
        audit_sink,
        precheck,
    )


def sketch_set_datum(
    registry: DocumentRegistry,
    doc: str | None = None,
    sketch: str | None = None,
    constraint: object = None,
    value: dict | None = None,
    confirm: dict | None = None,
    audit_sink: object = None,
) -> ResultEnvelope:
    """Change a dimensional constraint's value, named by 1-based solver id or by name.

    ``value`` is a ``{value, unit}`` quantity: ``mm`` for a length constraint, ``deg`` for an
    angle. Angles are converted to radians because ``setDatum`` reads a bare float as radians.

    :raises ValidationError: the sketch or constraint is unknown, the target is not a driving
        dimensional constraint, or the unit does not match the constraint's dimension.
    """
    _require_sketcher()
    if value is None:
        raise ValidationError("sketch_set_datum requires a 'value' quantity")

    def _target(document: object) -> tuple[object, int, float]:
        sketch_obj = _resolve_sketch(document, sketch)
        index = _resolve_constraint_index(sketch_obj, constraint)
        target = sketch_obj.Constraints[index]
        constraint_type = str(getattr(target, "Type", ""))
        if constraint_type not in _DIMENSIONAL:
            raise ValidationError(
                f"constraint {index + 1} is a {constraint_type}, not a dimensional constraint"
            )
        if not bool(getattr(target, "Driving", True)):
            raise ValidationError(f"constraint {index + 1} is not driving; its datum is read-only")
        datum = _positive_datum(constraint_type, value, f"constraint {index + 1}")
        return sketch_obj, index, datum

    def precheck(document: object) -> None:
        _target(document)

    def op(document: object) -> list[str]:
        sketch_obj, index, datum = _target(document)
        sketch_obj.setDatum(index, datum)
        return [sketch_obj.Name]

    params = {
        "doc": doc,
        "sketch": sketch,
        "constraint": constraint,
        "value": value,
        "confirm": confirm,
    }
    return _sketch_mutation(
        registry,
        doc,
        sketch,
        f"set datum on {sketch}",
        "sketch_set_datum",
        params,
        op,
        audit_sink,
        precheck,
    )


def sketch_toggle_construction(
    registry: DocumentRegistry,
    doc: str | None = None,
    sketch: str | None = None,
    geo_ids: list | None = None,
    confirm: dict | None = None,
    audit_sink: object = None,
) -> ResultEnvelope:
    """Toggle construction mode on the named 0-based sketch geometry.

    :raises ValidationError: the sketch is unknown or an id is not an existing geometry index.
    """
    _require_sketcher()
    if not geo_ids:
        raise ValidationError("sketch_toggle_construction requires a non-empty 'geo_ids' list")

    def _targets(document: object) -> tuple[object, list[int]]:
        sketch_obj = _resolve_sketch(document, sketch)
        count = int(sketch_obj.GeometryCount)
        seen: list[int] = []
        for raw in geo_ids:
            if not isinstance(raw, int) or isinstance(raw, bool) or not 0 <= raw < count:
                raise ValidationError(f"geo_id {raw!r} is outside the sketch (0..{count - 1})")
            if int(raw) in seen:
                raise ValidationError(f"geo_id {raw} is listed twice; a double toggle is a no-op")
            seen.append(int(raw))
        return sketch_obj, seen

    def precheck(document: object) -> None:
        _targets(document)

    def op(document: object) -> list[str]:
        sketch_obj, targets = _targets(document)
        for geo_id in targets:
            sketch_obj.toggleConstruction(geo_id)
        return [sketch_obj.Name]

    params = {"doc": doc, "sketch": sketch, "geo_ids": geo_ids, "confirm": confirm}
    return _sketch_mutation(
        registry,
        doc,
        sketch,
        f"toggle construction on {sketch}",
        "sketch_toggle_construction",
        params,
        op,
        audit_sink,
        precheck,
    )


def sketch_add_external_geometry(
    registry: DocumentRegistry,
    doc: str | None = None,
    sketch: str | None = None,
    edge: dict | None = None,
    confirm: dict | None = None,
    audit_sink: object = None,
) -> ResultEnvelope:
    """Project a model edge into a sketch as external geometry, addressed by a ``Selector``.

    :raises ValidationError: the sketch is unknown, or the selector names no resolvable
        subelement on an existing object.
    """
    _require_sketcher()
    if edge is None:
        raise ValidationError("sketch_add_external_geometry requires an 'edge' selector")
    target_name, subelement = _selector_subelement(edge)

    def _resolve(document: object) -> object:
        sketch_obj = _resolve_sketch(document, sketch)
        target = document.getObject(target_name)
        if target is None:
            raise ValidationError(f"unknown object in edge selector: {target_name}")
        shape = getattr(target, "Shape", None)
        if shape is None:
            raise ValidationError(f"{target_name} carries no shape to project")
        element = None
        try:
            element = shape.getElement(subelement)
        except Exception as exc:  # noqa: BLE001 - an unresolvable subelement is caller input
            raise ValidationError(f"unresolvable edge selector {subelement!r}: {exc}") from exc
        if getattr(element, "ShapeType", "") != "Edge":
            raise ValidationError(
                f"edge selector {subelement!r} resolves to a "
                f"{getattr(element, 'ShapeType', 'unknown')}, not an Edge"
            )
        return sketch_obj

    def precheck(document: object) -> None:
        _resolve(document)

    def op(document: object) -> list[str]:
        sketch_obj = _resolve(document)
        sketch_obj.addExternal(target_name, subelement)
        return [sketch_obj.Name]

    params = {"doc": doc, "sketch": sketch, "edge": edge, "confirm": confirm}
    return _sketch_mutation(
        registry,
        doc,
        sketch,
        f"add external geometry to {sketch}",
        "sketch_add_external_geometry",
        params,
        op,
        audit_sink,
        precheck,
    )
