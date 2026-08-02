"""The ``feature_*`` mutation use cases.

Each tool validates its typed input, then executes one closure through
``transaction.run_mutation`` and rebinds the document that call returns into the registry. The
returned envelope carries the common ``mutation`` block plus a ``feature_state`` block read back
through ``verify_shape``.

Wire conventions: the target ``body`` and the created feature are named by immutable ``Name``;
the mandatory intent-bearing ``name`` becomes the feature's ``Label``. Every dimension is a
``{value, unit}`` quantity, and feature angles arrive and are applied in degrees. Enumerated
property values are checked against the live ``getEnumerationsOfProperty`` reading rather than a
hardcoded list.

Stdlib + FreeCAD App modules only; version-sensitive calls go through ``shim``.
"""

from __future__ import annotations

import math
import re
from typing import Callable

from freecad_buddy.contracts import ResultEnvelope
from freecad_buddy.usecases import confirm, shim, transaction, verify
from freecad_buddy.usecases.documents import DocumentRegistry, ValidationError

_ANGLE_UNITS = frozenset({"deg"})
_LENGTH_UNITS = frozenset({"mm"})

_BODY_TYPE = "PartDesign::Body"
_FEATURE_BASE_TYPE = "PartDesign::FeatureBase"

# FreeCAD rewrites any character outside this set when it names an object, so a name failing the
# pattern would silently become a different object name than the caller asked for.
_OBJECT_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")

# A pattern occurrence count above this is refused rather than handed to OCC: each occurrence is
# a full boolean against the base solid inside an open transaction under a 120 s timeout.
_MAX_OCCURRENCES = 1000

# The subelement names FeatureSketchBased resolves against a sketch when it is also the
# ReferenceAxis target (FeatureSketchBased.cpp getAxis).
_SKETCH_AXES = frozenset({"V_Axis", "H_Axis", "N_Axis"})

# The only revolution type that reads Angle2; every other type marks the property read-only.
_REVOLVE_TWO_ANGLES = "TwoAngles"

# The Hole ThreadType member meaning "no thread". Every other member makes Diameter read-only and
# derives it from the thread's size tables instead.
_HOLE_NO_THREAD = "None"

_PATTERN_TYPES = {
    "linear": "PartDesign::LinearPattern",
    "polar": "PartDesign::PolarPattern",
}

# The pattern Mode members, folded, that spread the occurrences across a total extent (driving
# Length for a linear pattern and Angle for a polar one). "length" and "angle" are the older
# spellings; "extent" is the newer one shared by both pattern types.
_PATTERN_EXTENT_MODES = frozenset({"length", "angle", "extent"})

# The pattern Mode members, folded, that step the occurrences by a fixed Offset instead.
_PATTERN_OFFSET_MODES = frozenset({"offset", "spacing"})

_DATUM_TYPES = {
    "plane": "PartDesign::Plane",
    "axis": "PartDesign::Line",
    "point": "PartDesign::Point",
    "cs": "PartDesign::CoordinateSystem",
}

# Two adjacent faces is what DressUp::getContinuousEdges requires of every requested edge.
_DRESSUP_ADJACENT_FACES = 2

# Surface normals this close to parallel on both sides of an edge make it tangent rather than
# C0, which is the second condition getContinuousEdges drops an edge for.
_TANGENT_DOT = 1.0 - 1e-6


def _require_partdesign() -> None:
    """Raise when the running build cannot create the PartDesign objects these tools drive."""
    if not shim.partdesign_available():
        raise ValidationError("PartDesign is unavailable on this FreeCAD build")


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


def _length_mm(value: object, what: str) -> float:
    """Return a wire length quantity in millimetres, FreeCAD's internal length unit."""
    return _quantity_value(value, _LENGTH_UNITS, what)


def _angle_degrees(value: object, what: str) -> float:
    """Return a wire angle quantity in degrees, which is what ``App::PropertyAngle`` reads."""
    return _quantity_value(value, _ANGLE_UNITS, what)


def _positive_length(value: object, what: str) -> float:
    """Return a length quantity that must be strictly positive."""
    length = _length_mm(value, what)
    if length <= 0.0:
        raise ValidationError(f"{what} must be positive, got {length}")
    return length


def _bounded_angle(
    value: object, what: str, low: float, high: float, include_high: bool = False
) -> float:
    """Return an angle quantity in degrees after checking it lies within its property's range.

    The lower bound is always exclusive; ``include_high`` makes the upper bound inclusive, which
    is what a full-turn revolution or polar pattern needs.

    :raises ValidationError: the quantity is malformed, or the angle is outside the range.
    """
    angle = _angle_degrees(value, what)
    if angle <= low or (angle > high if include_high else angle >= high):
        bound = f"({low}, {high}]" if include_high else f"({low}, {high})"
        raise ValidationError(f"{what} must be in {bound} degrees, got {angle}")
    return angle


def _selector_subelement(
    selector: object, what: str, whole_object: bool = False
) -> tuple[str, str]:
    """Return ``(object_name, subelement)`` from a contracts ``Selector``.

    Only the ``mapped_name`` variant resolves without a geometric query; a ``geometric``
    selector is rejected until the resolver that grades a query lands.

    :param whole_object: allow an omitted or empty ``mapped_name``, which addresses the whole
        object. Datum axes and planes are referenced that way, and FreeCAD spells such a link
        with a single empty subelement.
    :raises ValidationError: the selector is malformed or of an unresolvable kind.
    """
    if not isinstance(selector, dict):
        raise ValidationError(f"{what} must be an object, got {selector!r}")
    kind = selector.get("kind")
    obj = selector.get("object")
    if not isinstance(obj, str) or not obj:
        raise ValidationError(f"{what} requires an 'object' name")
    if kind != "mapped_name":
        raise ValidationError(
            f"{what} kind must be 'mapped_name'; {kind!r} is not resolvable by a feature tool"
        )
    mapped = selector.get("mapped_name")
    if mapped is None and whole_object:
        return obj, ""
    if not isinstance(mapped, str) or (not mapped and not whole_object):
        raise ValidationError(f"{what} mapped_name selector requires a 'mapped_name'")
    return obj, mapped


def _resolve_object(document: object, name: object, what: str) -> object:
    """Return the object named ``name``, or raise ``ValidationError``."""
    if not isinstance(name, str) or not name:
        raise ValidationError(f"missing required '{what}' name")
    obj = document.getObject(name)
    if obj is None:
        raise ValidationError(f"unknown object in {what}: {name}")
    return obj


def _resolve_body(document: object, name: object) -> object:
    """Return the ``PartDesign::Body`` named ``name``, or raise ``ValidationError``."""
    obj = _resolve_object(document, name, "body")
    if str(getattr(obj, "TypeId", "")) != _BODY_TYPE:
        raise ValidationError(f"object is not a PartDesign Body: {name}")
    return obj


def _resolve_sketch(document: object, name: object, what: str) -> object:
    """Return the ``Sketcher::`` object named ``name``, or raise ``ValidationError``."""
    obj = _resolve_object(document, name, what)
    if not str(getattr(obj, "TypeId", "")).startswith("Sketcher::"):
        raise ValidationError(f"object is not a sketch: {name}")
    return obj


def _require_shape(obj: object) -> object:
    """Return ``obj.Shape``, or raise ``ValidationError`` when it is absent or null."""
    shape = getattr(obj, "Shape", None)
    is_null = getattr(shape, "isNull", None)
    if shape is None or (is_null is not None and is_null()):
        raise ValidationError(f"{obj.Name} carries no shape")
    return shape


def _checked_enum(obj: object, prop: str, value: object, what: str) -> str:
    """Return ``value`` after checking it against ``obj``'s live enumeration for ``prop``.

    :raises ValidationError: the value is not a string, the property exposes no enumeration, or
        the value is outside it.
    """
    if not isinstance(value, str):
        raise ValidationError(f"{what} must be a string, got {value!r}")
    legal = shim.enum_values(obj, prop)
    if not legal:
        raise ValidationError(f"{obj.Name} exposes no {prop} enumeration on this build")
    if value not in legal:
        raise ValidationError(f"{what} {value!r} is not one of {legal}")
    return value


def _name_available(document: object, name: object) -> str:
    """Return the intent-bearing feature name after checking it is a usable, unused name.

    Usable means FreeCAD will accept the name verbatim: a leading digit, punctuation or any
    non-ASCII character is rewritten by ``addObject``, which would create an object under a name
    the caller never asked for.

    :raises ValidationError: the name is missing, not a legal FreeCAD object name, or in use.
    """
    if not isinstance(name, str) or not name:
        raise ValidationError("a feature tool requires a 'name'")
    if not _OBJECT_NAME.match(name):
        raise ValidationError(
            f"{name!r} is not a usable FreeCAD object name; use ASCII letters, digits and "
            "underscores, starting with a letter or underscore"
        )
    if document.getObject(name) is not None:
        raise ValidationError(f"an object named {name} already exists")
    return name


def _add_feature(document: object, body: object, type_id: str, name: str) -> object:
    """Create ``type_id`` named ``name``, label it, and add it to ``body``.

    ``Body.addObject`` validates the feature, inserts it in the tree and advances ``Tip`` for a
    solid feature; the ``Group`` property is written by that call and never here.
    """
    feature = document.addObject(type_id, name)
    if feature.Name != name:
        raise ValidationError(f"{name} is not a usable FreeCAD object name")
    feature.Label = name
    body.addObject(feature)
    return feature


def _finite(value: object) -> float | None:
    """Return ``value`` as a float, or ``None`` when it is not a finite number.

    A degenerate solid can report a NaN or infinite measurement, which no JSON encoder can emit
    and no consumer of the summary schema accepts.
    """
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _shape_summary(obj: object) -> dict | None:
    """Return the created feature's shape summary, or ``None`` when it carries no shape.

    Measurements a degenerate shape reports as non-finite are omitted rather than emitted, so the
    block is always JSON-encodable.
    """
    shape = getattr(obj, "Shape", None)
    is_null = getattr(shape, "isNull", None)
    if shape is None or (is_null is not None and is_null()):
        return None
    bbox = [
        _finite(shape.BoundBox.XLength),
        _finite(shape.BoundBox.YLength),
        _finite(shape.BoundBox.ZLength),
    ]
    summary = {
        "solid_count": len(shape.Solids),
        "face_count": len(shape.Faces),
        "edge_count": len(shape.Edges),
        "vertex_count": len(shape.Vertexes),
        "is_valid": bool(shape.isValid()),
    }
    for field, value in (("volume", _finite(shape.Volume)), ("area", _finite(shape.Area))):
        if value is not None:
            summary[field] = value
    if all(length is not None for length in bbox):
        summary["bbox"] = bbox
    return summary


def _unreadable_state(feature: str) -> dict:
    """A ``feature_state`` block for a feature that could not be graded."""
    return {"schema": "fcb.feature-state/1", "feature": feature, "readable": False}


def _feature_state(registry: DocumentRegistry, doc: str | None, feature: str) -> dict:
    """Read the post-op feature summary, gated on ``verify_shape`` being able to grade it.

    A feature a rollback removed, or whose shape is null or unreadable for any reason, reports
    ``readable: False`` and carries no grading fields rather than a null a consumer would
    dereference. ``schema``, ``feature`` and ``readable`` are present on both paths, and no
    failure to read the state discards the mutation's own envelope.
    """
    try:
        graded = verify.verify_shape(registry, doc=doc, object=feature)
    except Exception:  # noqa: BLE001 - an ungradeable feature is reported, never raised
        return _unreadable_state(feature)
    if graded.get("status") != "OK":
        return _unreadable_state(feature)

    def read(_handle: str, document: object) -> dict:
        obj = document.getObject(feature)
        summary = _shape_summary(obj) if obj is not None else None
        if summary is None:
            return _unreadable_state(feature)
        body = getattr(obj, "_Body", None)
        tip = getattr(body, "Tip", None) if body is not None else None
        return {
            "schema": "fcb.feature-state/1",
            "feature": feature,
            "readable": True,
            "body": str(body.Name) if body is not None else "",
            "is_tip": tip is not None and str(getattr(tip, "Name", "")) == feature,
            "shape_summary": summary,
        }

    try:
        return registry.with_document(doc, read)
    except Exception:  # noqa: BLE001 - an unreadable document is reported, never raised
        return _unreadable_state(feature)


def _feature_mutation(
    registry: DocumentRegistry,
    doc: str | None,
    feature: str,
    label: str,
    tool: str,
    params: dict,
    op: Callable[[object], list[str]],
    audit_sink: object = None,
    precheck: Callable[[object], None] | None = None,
) -> ResultEnvelope:
    """Run ``op`` through the mutation bracket and attach the post-op ``feature_state``.

    The document is resolved once and passed into ``run_mutation`` (re-entering the registry lock
    would deadlock), and the document that call returns is rebound into the registry on every
    exit path: the snapshot-restore rollback closes and reopens the document, so a handle left
    pointing at the original object would address a closed document.

    :param feature: the feature whose state the envelope reports; it need not exist yet.
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
        rebound.append(document)
        result = transaction.run_mutation(
            document, handle, label, op, audit_sink=audit_sink, tool=tool, params=params
        )
        rebound.append(result[0])
        return result

    try:
        _, envelope = registry.with_document(doc, call)
    finally:
        if rebound:
            try:
                registry.rebind(doc, rebound[-1])
            except Exception:  # noqa: BLE001 - a failed rebind must not mask the real outcome
                pass
    content = envelope.get("structured_content")
    if not isinstance(content, dict):
        content = {}
        envelope["structured_content"] = content
    content["feature"] = feature
    content["feature_state"] = _feature_state(registry, doc, feature)
    return envelope


# --------------------------------------------------------------------------------------------
# Extrudes: pad and pocket
# --------------------------------------------------------------------------------------------


def _extrude_type(feature: object, up_to: object) -> str:
    """Return the extrude ``Type`` string, defaulting to ``Length``, checked against the build.

    The enumeration is never indexed: its members differ in spelling between the supported
    builds and one position carries a deprecation tombstone on the newer of them.
    """
    requested = "Length" if up_to is None else up_to
    return _checked_enum(feature, "Type", requested, "up_to")


def _extrude_needs_length(extrude_type: str) -> bool:
    """Whether an extrude of this type is driven by its ``Length`` property."""
    return extrude_type == "Length"


def _precheck_extrude(
    document: object,
    body: object,
    profile: object,
    name: object,
    up_to: object,
    length: object,
    taper_angle: object,
    up_to_face: tuple[str, str] | None,
    type_id: str,
) -> None:
    """Validate an extrude request against the resolved document before the bracket opens.

    The type enumeration is read from a scratch instance of the feature type, because the
    enumeration is a property of the class and the real feature does not exist yet.
    """
    _resolve_body(document, body)
    _resolve_sketch(document, profile, "profile")
    _name_available(document, name)
    extrude_type = shim.probe_object(type_id, lambda probe: _extrude_type(probe, up_to))
    if _extrude_needs_length(extrude_type):
        if length is None:
            raise ValidationError(f"up_to={extrude_type!r} is length-driven; 'length' is required")
        _positive_length(length, "length")
    if taper_angle is not None:
        _bounded_angle(taper_angle, "taper_angle", -90.0, 90.0)
    if up_to_face is not None:
        _resolve_object(document, up_to_face[0], "up_to_face")


def _extrude_tool(
    type_id: str,
    tool: str,
    registry: DocumentRegistry,
    doc: str | None,
    body: str | None,
    profile: str | None,
    name: str | None,
    length: dict | None,
    second_length: dict | None,
    up_to: str | None,
    up_to_face: dict | None,
    reversed_: bool,
    midplane: bool,
    taper_angle: dict | None,
    confirm: dict | None,
    audit_sink: object,
) -> ResultEnvelope:
    """Create one extrude feature (Pad or Pocket) through the mutation bracket."""
    _require_partdesign()
    face = _selector_subelement(up_to_face, "up_to_face") if up_to_face is not None else None

    def precheck(document: object) -> None:
        _precheck_extrude(document, body, profile, name, up_to, length, taper_angle, face, type_id)

    def op(document: object) -> list[str]:
        body_obj = _resolve_body(document, body)
        profile_obj = _resolve_sketch(document, profile, "profile")
        feature = _add_feature(document, body_obj, type_id, name)
        feature.Profile = profile_obj
        feature.Type = _extrude_type(feature, up_to)
        if _extrude_needs_length(feature.Type):
            feature.Length = _length_mm(length, "length")
        if second_length is not None:
            feature.Length2 = _length_mm(second_length, "second_length")
        if face is not None:
            feature.UpToFace = (_resolve_object(document, face[0], "up_to_face"), [face[1]])
        feature.Reversed = bool(reversed_)
        shim.extrude_symmetric(feature, bool(midplane))
        if taper_angle is not None:
            feature.TaperAngle = _bounded_angle(taper_angle, "taper_angle", -90.0, 90.0)
        return [feature.Name, body_obj.Name]

    params = {
        "doc": doc,
        "body": body,
        "profile": profile,
        "name": name,
        "length": length,
        "second_length": second_length,
        "up_to": up_to,
        "up_to_face": up_to_face,
        "reversed": reversed_,
        "midplane": midplane,
        "taper_angle": taper_angle,
        "confirm": confirm,
    }
    return _feature_mutation(
        registry, doc, name, f"{tool} {name}", tool, params, op, audit_sink, precheck
    )


def feature_pad(
    registry: DocumentRegistry,
    doc: str | None = None,
    body: str | None = None,
    profile: str | None = None,
    name: str | None = None,
    length: dict | None = None,
    second_length: dict | None = None,
    up_to: str | None = None,
    up_to_face: dict | None = None,
    reversed: bool = False,  # noqa: A002 - the wire field name
    midplane: bool = False,
    taper_angle: dict | None = None,
    confirm: dict | None = None,
    audit_sink: object = None,
) -> ResultEnvelope:
    """Pad a sketch profile into the target Body, advancing its ``Tip``.

    ``up_to`` selects the extrude type and defaults to ``"Length"``, which requires a positive
    ``length``; every other value is checked against the build's live ``Type`` enumeration.
    ``midplane`` makes the pad straddle the profile plane, adding half its length to each side
    rather than moving the total volume.

    :raises ValidationError: the body or profile is unknown, the name is taken, ``up_to`` is
        outside the build's enumeration, or a length-driven pad carries no ``length``.
    """
    return _extrude_tool(
        "PartDesign::Pad",
        "feature_pad",
        registry,
        doc,
        body,
        profile,
        name,
        length,
        second_length,
        up_to,
        up_to_face,
        reversed,
        midplane,
        taper_angle,
        confirm,
        audit_sink,
    )


def feature_pocket(
    registry: DocumentRegistry,
    doc: str | None = None,
    body: str | None = None,
    profile: str | None = None,
    name: str | None = None,
    length: dict | None = None,
    second_length: dict | None = None,
    up_to: str | None = None,
    up_to_face: dict | None = None,
    reversed: bool = False,  # noqa: A002 - the wire field name
    midplane: bool = False,
    taper_angle: dict | None = None,
    confirm: dict | None = None,
    audit_sink: object = None,
) -> ResultEnvelope:
    """Cut a pocket from a sketch profile into the target Body, advancing its ``Tip``.

    ``up_to`` selects the extrude type and defaults to ``"Length"``, which requires a positive
    ``length``. ``"ThroughAll"`` cuts the whole body and is a Pocket-only value — the Pad
    enumeration carries a different member at that position, which is why the value is checked
    against the live enumeration of the feature being built.

    :raises ValidationError: the body or profile is unknown, the name is taken, ``up_to`` is
        outside the build's enumeration, or a length-driven pocket carries no ``length``.
    """
    return _extrude_tool(
        "PartDesign::Pocket",
        "feature_pocket",
        registry,
        doc,
        body,
        profile,
        name,
        length,
        second_length,
        up_to,
        up_to_face,
        reversed,
        midplane,
        taper_angle,
        confirm,
        audit_sink,
    )


# --------------------------------------------------------------------------------------------
# Revolution
# --------------------------------------------------------------------------------------------


def _revolve_axis(document: object, profile_name: object, axis: dict | None) -> tuple[str, str]:
    """Return the validated ``(object, subelement)`` the revolution's ``ReferenceAxis`` names.

    A subelement on the profile sketch itself must be one of the sketch axes the C++ resolver
    recognises; a subelement on any other object is resolved as a shape edge.
    """
    if axis is None:
        raise ValidationError("feature_revolve requires an 'axis' selector")
    target_name, subelement = _selector_subelement(axis, "axis")
    if target_name == profile_name:
        if subelement not in _SKETCH_AXES:
            raise ValidationError(
                f"axis on the profile sketch must be one of {sorted(_SKETCH_AXES)}, "
                f"got {subelement!r}"
            )
        return target_name, subelement
    target = _resolve_object(document, target_name, "axis")
    if subelement in _SKETCH_AXES:
        return target_name, subelement
    shape = _require_shape(target)
    try:
        element = shape.getElement(subelement)
    except Exception as exc:  # noqa: BLE001 - an unresolvable subelement is caller input
        raise ValidationError(f"unresolvable axis selector {subelement!r}: {exc}") from exc
    if getattr(element, "ShapeType", "") != "Edge":
        raise ValidationError(
            f"axis selector {subelement!r} resolves to a "
            f"{getattr(element, 'ShapeType', 'unknown')}, not an Edge"
        )
    return target_name, subelement


def _check_two_angles(up_to: str | None, second_angle: object) -> None:
    """Check the revolution's second angle against the type that reads it.

    FreeCAD only reads ``Angle2`` for the two-angle revolution type and marks it read-only
    otherwise, so a second angle supplied for any other type would be discarded, and a two-angle
    revolution without one would silently take the property's build default.

    :raises ValidationError: exactly one of the two-angle type and ``second_angle`` is present.
    """
    two_angles = up_to == _REVOLVE_TWO_ANGLES
    if second_angle is not None and not two_angles:
        raise ValidationError(
            f"second_angle is only read when up_to={_REVOLVE_TWO_ANGLES!r}; got up_to={up_to!r}"
        )
    if two_angles and second_angle is None:
        raise ValidationError(
            f"up_to={_REVOLVE_TWO_ANGLES!r} is driven by two angles; 'second_angle' is required"
        )


def feature_revolve(
    registry: DocumentRegistry,
    doc: str | None = None,
    body: str | None = None,
    profile: str | None = None,
    name: str | None = None,
    axis: dict | None = None,
    angle: dict | None = None,
    second_angle: dict | None = None,
    up_to: str | None = None,
    reversed: bool = False,  # noqa: A002 - the wire field name
    midplane: bool = False,
    confirm: dict | None = None,
    audit_sink: object = None,
) -> ResultEnvelope:
    """Revolve a sketch profile about an axis into the target Body.

    ``axis`` is a selector naming either one of the profile sketch's own axes
    (``V_Axis``/``H_Axis``/``N_Axis``) or an edge on another object; it is written to
    ``ReferenceAxis``, from which FreeCAD computes the read-only ``Base`` and ``Axis``.
    ``angle`` carries ``deg`` and is applied in degrees.

    :raises ValidationError: the body, profile or axis target is unknown, the axis subelement is
        not a sketch axis or an edge, the name is taken, or ``up_to`` is outside the build's
        enumeration.
    """
    _require_partdesign()

    def precheck(document: object) -> None:
        _resolve_body(document, body)
        _resolve_sketch(document, profile, "profile")
        _name_available(document, name)
        _revolve_axis(document, profile, axis)
        if angle is not None:
            _bounded_angle(angle, "angle", 0.0, 360.0, include_high=True)
        if second_angle is not None:
            _bounded_angle(second_angle, "second_angle", 0.0, 360.0, include_high=True)
        resolved = None
        if up_to is not None:
            resolved = shim.probe_object(
                "PartDesign::Revolution",
                lambda probe: _checked_enum(probe, "Type", up_to, "up_to"),
            )
        _check_two_angles(resolved, second_angle)

    def op(document: object) -> list[str]:
        body_obj = _resolve_body(document, body)
        profile_obj = _resolve_sketch(document, profile, "profile")
        axis_name, subelement = _revolve_axis(document, profile, axis)
        feature = _add_feature(document, body_obj, "PartDesign::Revolution", name)
        feature.Profile = profile_obj
        feature.ReferenceAxis = (_resolve_object(document, axis_name, "axis"), [subelement])
        if up_to is not None:
            feature.Type = _checked_enum(feature, "Type", up_to, "up_to")
        if angle is not None:
            feature.Angle = _bounded_angle(angle, "angle", 0.0, 360.0, include_high=True)
        if second_angle is not None:
            feature.Angle2 = _bounded_angle(
                second_angle, "second_angle", 0.0, 360.0, include_high=True
            )
        feature.Reversed = bool(reversed)
        shim.extrude_symmetric(feature, bool(midplane))
        return [feature.Name, body_obj.Name]

    params = {
        "doc": doc,
        "body": body,
        "profile": profile,
        "name": name,
        "axis": axis,
        "angle": angle,
        "second_angle": second_angle,
        "up_to": up_to,
        "reversed": reversed,
        "midplane": midplane,
        "confirm": confirm,
    }
    return _feature_mutation(
        registry,
        doc,
        name,
        f"revolve {name}",
        "feature_revolve",
        params,
        op,
        audit_sink,
        precheck,
    )


# --------------------------------------------------------------------------------------------
# Hole
# --------------------------------------------------------------------------------------------


def _is_threading(thread_type: str) -> bool:
    """Whether a resolved ``ThreadType`` member describes a thread rather than a plain bore."""
    return thread_type.strip().casefold() != _HOLE_NO_THREAD.casefold()


def _apply_hole_thread(feature: object, thread_type: object, cut_type: object) -> str | None:
    """Set the hole's thread type first, then the enumerations it re-populates.

    ``Hole::onChanged`` rewrites ``HoleCutType``, ``ThreadSize``, ``ThreadClass`` and
    ``ThreadFit`` on every ``ThreadType`` write, so a dependent value is only meaningful once
    the thread type it belongs to is in place. ``Threaded`` is only written for a threading type:
    FreeCAD makes the property read-only and clears it for the unthreaded member itself.

    :return: the resolved thread type, or ``None`` when none was requested.
    """
    resolved = None
    if thread_type is not None:
        resolved = _checked_enum(feature, "ThreadType", thread_type, "thread_type")
        feature.ThreadType = resolved
        if _is_threading(resolved):
            feature.Threaded = True
    if cut_type is not None:
        feature.HoleCutType = _checked_enum(feature, "HoleCutType", cut_type, "cut_type")
    return resolved


def feature_hole(
    registry: DocumentRegistry,
    doc: str | None = None,
    body: str | None = None,
    profile: str | None = None,
    name: str | None = None,
    diameter: dict | None = None,
    depth: dict | None = None,
    depth_type: str | None = None,
    thread_type: str | None = None,
    cut_type: str | None = None,
    cut_diameter: dict | None = None,
    cut_depth: dict | None = None,
    reversed: bool = False,  # noqa: A002 - the wire field name
    confirm: dict | None = None,
    audit_sink: object = None,
) -> ResultEnvelope:
    """Drill a PartDesign Hole from a sketch profile into the target Body.

    ``depth_type`` defaults to ``"Dimension"``, which requires a positive ``depth``;
    ``"ThroughAll"`` cuts the whole body. ``thread_type`` is applied before ``cut_type``, because
    FreeCAD re-populates the cut-type enumeration from the thread type, so the legal cut types
    depend on which thread was selected. A threaded hole's diameter comes from the thread size
    tables, so ``diameter`` and a threading ``thread_type`` cannot be combined.

    :raises ValidationError: the body or profile is unknown, the name is taken, an enumerated
        value is outside the build's live enumeration for that property, a dimensioned hole
        carries no ``depth``, or ``diameter`` is combined with a threading ``thread_type``.
    """
    _require_partdesign()

    def _validate_enums(probe: object) -> tuple[str, str | None]:
        """Check every enumerated value against ``probe``.

        :return: the resolved ``(depth_type, thread_type)``; the thread type is ``None`` when
            none was requested.
        """
        resolved = _checked_enum(
            probe, "DepthType", "Dimension" if depth_type is None else depth_type, "depth_type"
        )
        return resolved, _apply_hole_thread(probe, thread_type, cut_type)

    def precheck(document: object) -> None:
        _resolve_body(document, body)
        _resolve_sketch(document, profile, "profile")
        _name_available(document, name)
        resolved, thread = shim.probe_object("PartDesign::Hole", _validate_enums)
        if diameter is not None:
            if thread is not None and _is_threading(thread):
                raise ValidationError(
                    f"'diameter' cannot be combined with thread_type={thread!r}: FreeCAD sizes a "
                    "threaded hole from its ThreadSize table entry, so the requested diameter is "
                    "stored but never reaches the geometry. Drop 'diameter', or use "
                    "thread_type='None' to drill a plain bore."
                )
            _positive_length(diameter, "diameter")
        if resolved == "Dimension":
            if depth is None:
                raise ValidationError("depth_type='Dimension' is depth-driven; 'depth' is required")
            _positive_length(depth, "depth")
        if cut_diameter is not None:
            _positive_length(cut_diameter, "cut_diameter")
        if cut_depth is not None:
            _positive_length(cut_depth, "cut_depth")

    def op(document: object) -> list[str]:
        body_obj = _resolve_body(document, body)
        profile_obj = _resolve_sketch(document, profile, "profile")
        feature = _add_feature(document, body_obj, "PartDesign::Hole", name)
        feature.Profile = profile_obj
        feature.DepthType = _checked_enum(
            feature, "DepthType", "Dimension" if depth_type is None else depth_type, "depth_type"
        )
        if diameter is not None:
            feature.Diameter = _positive_length(diameter, "diameter")
        if feature.DepthType == "Dimension":
            feature.Depth = _positive_length(depth, "depth")
        _apply_hole_thread(feature, thread_type, cut_type)
        if cut_diameter is not None:
            feature.HoleCutDiameter = _positive_length(cut_diameter, "cut_diameter")
        if cut_depth is not None:
            feature.HoleCutDepth = _positive_length(cut_depth, "cut_depth")
        feature.Reversed = bool(reversed)
        return [feature.Name, body_obj.Name]

    params = {
        "doc": doc,
        "body": body,
        "profile": profile,
        "name": name,
        "diameter": diameter,
        "depth": depth,
        "depth_type": depth_type,
        "thread_type": thread_type,
        "cut_type": cut_type,
        "cut_diameter": cut_diameter,
        "cut_depth": cut_depth,
        "reversed": reversed,
        "confirm": confirm,
    }
    return _feature_mutation(
        registry, doc, name, f"hole {name}", "feature_hole", params, op, audit_sink, precheck
    )


# --------------------------------------------------------------------------------------------
# Dress-ups: fillet and chamfer
# --------------------------------------------------------------------------------------------


def _edge_survives_continuity(edge: object, faces: list) -> bool:
    """Whether ``edge``'s two adjacent faces meet at a crease FreeCAD keeps.

    FreeCAD keeps only edges whose face-to-face continuity is ``C0``; a tangent join is a higher
    continuity and is dropped. Tangency is measured by comparing the two surface normals at a
    point on the edge, which is the observable form of that condition.

    The measurement fails closed: an edge whose normals cannot be read — a missing parameter
    range or surface, or a parameterisation that will not invert, as periodic and seam surfaces
    routinely will not — is reported as not surviving. Treating an unmeasurable edge as a keeper
    would reinstate the silent drop the guard exists to prevent.
    """
    parameters = getattr(edge, "ParameterRange", None)
    if not parameters or len(parameters) != 2:
        return False
    try:
        point = edge.valueAt((float(parameters[0]) + float(parameters[1])) / 2.0)
    except Exception:  # noqa: BLE001 - an edge that cannot be sampled cannot be measured
        return False
    normals = []
    for face in faces:
        surface = getattr(face, "Surface", None)
        if surface is None:
            return False
        try:
            u, v = surface.parameter(point)
            normals.append(face.normalAt(u, v))
        except Exception:  # noqa: BLE001 - a normal that cannot be read cannot prove a crease
            return False
    # Parallel normals are a tangent join; anti-parallel normals are a fold, which is a crease.
    return normals[0].dot(normals[1]) < _TANGENT_DOT


def _dropped_dressup_edges(shape: object, subelements: list[str]) -> list[str]:
    """Return the requested subelements a dress-up cannot be shown to keep.

    ``DressUp::getContinuousEdges`` drops, with no error and no return value, any edge that does
    not have exactly two adjacent faces and any edge whose two faces meet at a continuity above
    ``C0``. A dress-up built from a selection those checks thinned still reports ``Up-to-date``
    and a valid shape, so the committed feature would silently ignore part of the request.

    An edge is returned when it fails either check and also when its continuity cannot be
    measured at all, so the result is every edge not positively shown to survive rather than only
    those proven to be dropped.

    :raises ValidationError: a subelement is unresolvable or does not name an edge.
    """
    import Part

    dropped = []
    for subelement in subelements:
        try:
            element = shape.getElement(subelement)
        except Exception as exc:  # noqa: BLE001 - an unresolvable subelement is caller input
            raise ValidationError(f"unresolvable edge selector {subelement!r}: {exc}") from exc
        if getattr(element, "ShapeType", "") != "Edge":
            raise ValidationError(
                f"edge selector {subelement!r} resolves to a "
                f"{getattr(element, 'ShapeType', 'unknown')}, not an Edge"
            )
        faces = shape.ancestorsOfType(element, Part.Face)
        if len(faces) != _DRESSUP_ADJACENT_FACES:
            dropped.append(subelement)
            continue
        if not _edge_survives_continuity(element, faces):
            dropped.append(subelement)
    return dropped


def _dressup_base(
    document: object, body: object, base: object, edges: object
) -> tuple[str, list[str]]:
    """Return the validated ``(base_name, subelements)`` a dress-up's ``Base`` will name.

    The base must already belong to ``body``: FreeCAD only warns when a dress-up links out of
    its Body's scope, leaving a feature whose reference the tree does not own.

    Every requested edge is checked against the base shape's own topology and rejected when
    FreeCAD would drop it, so a dress-up that would ignore part of the selection never opens a
    transaction.
    """
    if not isinstance(edges, list) or not edges:
        raise ValidationError("a dress-up requires a non-empty 'edges' list")
    base_obj = _resolve_object(document, base, "base")
    members = {obj.Name for obj in list(getattr(body, "Group", []) or [])}
    if base_obj.Name not in members:
        raise ValidationError(
            f"dress-up base {base_obj.Name} is not in Body {body.Name}; "
            f"name a feature the Body owns ({sorted(members)})"
        )
    shape = _require_shape(base_obj)
    subelements: list[str] = []
    for index, selector in enumerate(edges):
        target_name, subelement = _selector_subelement(selector, f"edges[{index}]")
        if target_name != base_obj.Name:
            raise ValidationError(
                f"edges[{index}] names {target_name}, not the dress-up base {base_obj.Name}"
            )
        if subelement in subelements:
            raise ValidationError(f"edges[{index}] repeats {subelement}")
        subelements.append(subelement)
    dropped = _dropped_dressup_edges(shape, subelements)
    if dropped:
        raise ValidationError(
            f"{len(dropped)} of {len(subelements)} requested edge(s) on {base_obj.Name} cannot "
            f"be shown to survive the dress-up: {dropped}; each needs exactly two adjacent faces "
            "meeting at a measurable crease, and FreeCAD drops the rest without reporting it"
        )
    return base_obj.Name, subelements


def _check_dressed_every_edge(feature: object, subelements: list[str], base_faces: int) -> None:
    """Raise when the built dress-up covered fewer edges than were requested.

    Each dressed edge becomes one new face, so a clean dress-up of ``n`` edges adds exactly ``n``
    faces. ``getContinuousEdges`` drops an edge it will not dress without an error and without a
    return value, leaving the feature ``Valid`` and ``Up-to-date``, so the face count is the only
    signal that the committed feature is thinner than the request.

    This counts what FreeCAD actually did rather than predicting it, so it holds for every reason
    an edge is dropped, including the face-to-face continuity Python cannot read. It runs inside
    the transaction, so the enclosing bracket rolls the feature back and proves it.

    A feature whose recompute failed is left alone: it carries no usable shape, and the bracket's
    own validity sweep reports that failure with the engine's message. Counting faces there would
    replace a ``RECOMPUTE_ERROR`` with a misleading dropped-edge verdict.

    :raises ValidationError: fewer faces were added than edges requested.
    """
    if not feature.isValid():
        return
    added = len(feature.Shape.Faces) - base_faces
    if added >= len(subelements):
        return
    raise ValidationError(
        f"{feature.Name} dressed {added} of the {len(subelements)} requested edge(s) "
        f"{subelements}: FreeCAD silently drops an edge it will not dress, so the feature would "
        "have committed smaller than the request"
    )


def _dressup_tool(
    type_id: str,
    tool: str,
    registry: DocumentRegistry,
    doc: str | None,
    body: str | None,
    base: str | None,
    name: str | None,
    edges: list | None,
    apply_sizes: Callable[[object], None],
    validate_sizes: Callable[[object], None],
    params: dict,
    audit_sink: object,
) -> ResultEnvelope:
    """Create one dress-up feature (Fillet or Chamfer) through the mutation bracket."""
    _require_partdesign()

    def precheck(document: object) -> None:
        body_obj = _resolve_body(document, body)
        _name_available(document, name)
        _dressup_base(document, body_obj, base, edges)
        shim.probe_object(type_id, validate_sizes)

    def op(document: object) -> list[str]:
        body_obj = _resolve_body(document, body)
        base_name, subelements = _dressup_base(document, body_obj, base, edges)
        base_obj = document.getObject(base_name)
        before = len(base_obj.Shape.Faces)
        feature = _add_feature(document, body_obj, type_id, name)
        feature.Base = (base_obj, subelements)
        apply_sizes(feature)
        document.recompute()
        _check_dressed_every_edge(feature, subelements, before)
        return [feature.Name, body_obj.Name]

    return _feature_mutation(
        registry, doc, name, f"{tool} {name}", tool, params, op, audit_sink, precheck
    )


def feature_fillet(
    registry: DocumentRegistry,
    doc: str | None = None,
    body: str | None = None,
    base: str | None = None,
    name: str | None = None,
    edges: list | None = None,
    radius: dict | None = None,
    confirm: dict | None = None,
    audit_sink: object = None,
) -> ResultEnvelope:
    """Fillet the named edges of a feature already in the Body.

    Every requested edge is checked against the base shape before the transaction opens: FreeCAD
    silently discards an edge that does not have exactly two adjacent faces or whose faces meet
    tangentially, and commits the thinner selection as a valid feature. A request naming any such
    edge is rejected rather than committed as a smaller fillet than was asked for.

    :raises ValidationError: the body or base is unknown, the name is taken, an edge selector is
        unresolvable or names a non-edge, or any requested edge would be silently dropped.
    """

    def validate_sizes(_probe: object) -> None:
        _positive_length(radius, "radius")

    def apply_sizes(feature: object) -> None:
        feature.Radius = _positive_length(radius, "radius")

    params = {
        "doc": doc,
        "body": body,
        "base": base,
        "name": name,
        "edges": edges,
        "radius": radius,
        "confirm": confirm,
    }
    return _dressup_tool(
        "PartDesign::Fillet",
        "feature_fillet",
        registry,
        doc,
        body,
        base,
        name,
        edges,
        apply_sizes,
        validate_sizes,
        params,
        audit_sink,
    )


def feature_chamfer(
    registry: DocumentRegistry,
    doc: str | None = None,
    body: str | None = None,
    base: str | None = None,
    name: str | None = None,
    edges: list | None = None,
    size: dict | None = None,
    second_size: dict | None = None,
    angle: dict | None = None,
    chamfer_type: str | None = None,
    confirm: dict | None = None,
    audit_sink: object = None,
) -> ResultEnvelope:
    """Chamfer the named edges of a feature already in the Body.

    ``chamfer_type`` defaults to the build's first chamfer type and is checked against the live
    enumeration. Every requested edge is checked against the base shape before the transaction
    opens, for the same silent-drop reason as ``feature_fillet``.

    :raises ValidationError: the body or base is unknown, the name is taken, an edge selector is
        unresolvable or names a non-edge, ``chamfer_type`` is outside the build's enumeration, or
        any requested edge would be silently dropped.
    """

    def validate_sizes(probe: object) -> None:
        _positive_length(size, "size")
        if second_size is not None:
            _positive_length(second_size, "second_size")
        if angle is not None:
            _bounded_angle(angle, "angle", 0.0, 180.0)
        if chamfer_type is not None:
            _checked_enum(probe, "ChamferType", chamfer_type, "chamfer_type")

    def apply_sizes(feature: object) -> None:
        if chamfer_type is not None:
            feature.ChamferType = _checked_enum(
                feature, "ChamferType", chamfer_type, "chamfer_type"
            )
        feature.Size = _positive_length(size, "size")
        if second_size is not None:
            feature.Size2 = _positive_length(second_size, "second_size")
        if angle is not None:
            feature.Angle = _bounded_angle(angle, "angle", 0.0, 180.0)

    params = {
        "doc": doc,
        "body": body,
        "base": base,
        "name": name,
        "edges": edges,
        "size": size,
        "second_size": second_size,
        "angle": angle,
        "chamfer_type": chamfer_type,
        "confirm": confirm,
    }
    return _dressup_tool(
        "PartDesign::Chamfer",
        "feature_chamfer",
        registry,
        doc,
        body,
        base,
        name,
        edges,
        apply_sizes,
        validate_sizes,
        params,
        audit_sink,
    )


# --------------------------------------------------------------------------------------------
# Transformations: pattern and mirror
# --------------------------------------------------------------------------------------------


def _resolve_originals(document: object, body: object, originals: object) -> list[object]:
    """Return the features a transformation repeats, defaulting to the Body's ``Tip``.

    Each named original must be a distinct member of the target Body: a transformation only
    repeats features its own Body owns, and a repeated name would ask FreeCAD to transform the
    same feature twice.

    :raises ValidationError: the list is empty or malformed, names an unknown object, repeats a
        name, or names a feature the Body does not own.
    """
    if originals is None:
        tip = getattr(body, "Tip", None)
        if tip is None:
            raise ValidationError(f"{body.Name} has no Tip to transform; name 'originals'")
        return [tip]
    if not isinstance(originals, list) or not originals:
        raise ValidationError("'originals' must be a non-empty list of feature names")
    members = {obj.Name for obj in list(getattr(body, "Group", []) or [])}
    resolved: list[object] = []
    seen: set[str] = set()
    for index, item in enumerate(originals):
        obj = _resolve_object(document, item, "originals")
        if obj.Name in seen:
            raise ValidationError(f"originals[{index}] repeats {obj.Name}")
        if obj.Name not in members:
            raise ValidationError(
                f"originals[{index}] names {obj.Name}, which is not in Body {body.Name}; "
                f"name a feature the Body owns ({sorted(members)})"
            )
        seen.add(obj.Name)
        resolved.append(obj)
    return resolved


def _resolve_direction(document: object, selector: object, what: str) -> tuple[object, list[str]]:
    """Return the ``(object, [subelement])`` link a pattern's direction or axis property takes.

    A selector naming a whole datum object omits ``mapped_name``, which FreeCAD spells as a
    single empty subelement; one naming an edge, a face or a sketch axis carries it.
    """
    if selector is None:
        raise ValidationError(f"a transformation requires a '{what}' selector")
    target_name, subelement = _selector_subelement(selector, what, whole_object=True)
    target = _resolve_object(document, target_name, what)
    return target, [subelement]


def _mode_drives_offset(probe: object, mode: str | None) -> bool:
    """Whether the pattern ``mode`` drives ``Offset`` rather than the extent dimension.

    A pattern's two modes are mutually exclusive: one spreads the occurrences across a total
    extent (``Length`` for linear, ``Angle`` for polar) and the other steps them by a fixed
    ``Offset``. FreeCAD marks the property the active mode does not read as read-only, so a write
    to the wrong one is silently discarded.

    The offset mode is spelled differently across the supported builds, so the resolved member is
    matched case-insensitively against the spellings each build uses rather than against a single
    literal. ``None`` leaves the build default, which is the extent mode.

    :raises ValidationError: the mode is outside the build's enumeration, or the build spells it
        in a way this mapping does not recognise.
    """
    if mode is None:
        return False
    resolved = _checked_enum(probe, "Mode", mode, "mode")
    folded = resolved.strip().casefold()
    if folded in _PATTERN_OFFSET_MODES:
        return True
    if folded in _PATTERN_EXTENT_MODES:
        return False
    raise ValidationError(
        f"mode {resolved!r} is legal on this build but drives an unknown dimension; "
        f"expected one of {sorted(_PATTERN_EXTENT_MODES | _PATTERN_OFFSET_MODES)}"
    )


def feature_pattern(
    registry: DocumentRegistry,
    doc: str | None = None,
    body: str | None = None,
    name: str | None = None,
    kind: str | None = None,
    originals: list | None = None,
    direction: dict | None = None,
    axis: dict | None = None,
    length: dict | None = None,
    angle: dict | None = None,
    offset: dict | None = None,
    occurrences: int | None = None,
    mode: str | None = None,
    reversed: bool = False,  # noqa: A002 - the wire field name
    confirm: dict | None = None,
    audit_sink: object = None,
) -> ResultEnvelope:
    """Repeat features linearly along a direction or polarly about an axis.

    ``occurrences`` counts the original, so three occurrences is the original plus two copies.
    A polar pattern spanning a full turn steps by ``angle / occurrences``, not
    ``angle / (occurrences - 1)``, so six occurrences over 360 degrees land 60 degrees apart.

    ``mode`` selects which dimension drives the spacing and is checked against the build's live
    enumeration, whose members are spelled differently across the supported builds. The extent
    mode spreads the occurrences across ``length`` (linear) or ``angle`` (polar); the offset mode
    steps them by ``offset`` instead. Only the dimension the resolved mode reads may be supplied,
    because FreeCAD marks the other one read-only. Omitting ``mode`` leaves the build's default,
    which is the extent mode.

    :raises ValidationError: the body is unknown, the name is taken, ``kind`` is not
        ``"linear"``/``"polar"``, the direction or axis target is unknown, an original is
        unknown, repeated or outside the Body, ``mode`` is outside the build's enumeration, the
        supplied dimension does not match the resolved mode, or ``occurrences`` is out of range.
    """
    _require_partdesign()
    if kind not in _PATTERN_TYPES:
        raise ValidationError(f"kind must be one of {sorted(_PATTERN_TYPES)}, got {kind!r}")
    type_id = _PATTERN_TYPES[kind]
    if (
        not isinstance(occurrences, int)
        or isinstance(occurrences, bool)
        or not 2 <= occurrences <= _MAX_OCCURRENCES
    ):
        raise ValidationError(
            f"occurrences must be an integer between 2 and {_MAX_OCCURRENCES}, got {occurrences!r}"
        )
    selector = direction if kind == "linear" else axis
    what = "direction" if kind == "linear" else "axis"
    extent = length if kind == "linear" else angle
    extent_field = "length" if kind == "linear" else "angle"

    def resolve_extent() -> float:
        if kind == "linear":
            return _positive_length(length, "length")
        return _bounded_angle(angle, "angle", 0.0, 360.0, include_high=True)

    def validate_dimensions(probe: object) -> bool:
        """Check the supplied dimension against the mode that will read it.

        The dimension the resolved mode does not read is refused rather than written, because
        FreeCAD marks it read-only and would discard the write. A linear pattern always needs its
        driving dimension; a polar one may omit it to take the build's default sweep.
        """
        drives_offset = _mode_drives_offset(probe, mode)
        wanted, unwanted = ("offset", extent_field) if drives_offset else (extent_field, "offset")
        if (extent if drives_offset else offset) is not None:
            raise ValidationError(
                f"mode={mode!r} reads {wanted!r}, so {unwanted!r} would be discarded; "
                f"supply only {wanted!r}"
            )
        if drives_offset:
            if offset is None:
                raise ValidationError(f"mode={mode!r} is driven by 'offset'; it is required")
            if kind == "linear":
                _positive_length(offset, "offset")
            else:
                _bounded_angle(offset, "offset", 0.0, 360.0, include_high=True)
        elif kind == "linear" or extent is not None:
            resolve_extent()
        return drives_offset

    def precheck(document: object) -> None:
        body_obj = _resolve_body(document, body)
        _name_available(document, name)
        _resolve_originals(document, body_obj, originals)
        _resolve_direction(document, selector, what)
        shim.probe_object(type_id, validate_dimensions)

    def op(document: object) -> list[str]:
        body_obj = _resolve_body(document, body)
        targets = _resolve_originals(document, body_obj, originals)
        link = _resolve_direction(document, selector, what)
        feature = _add_feature(document, body_obj, type_id, name)
        feature.Originals = targets
        if kind == "linear":
            feature.Direction = link
        else:
            feature.Axis = link
        # Mode is written before either dimension: it decides which of the two FreeCAD leaves
        # writable, and a write to the read-only one is discarded without an error.
        drives_offset = _mode_drives_offset(feature, mode)
        if mode is not None:
            feature.Mode = _checked_enum(feature, "Mode", mode, "mode")
        if drives_offset:
            feature.Offset = (
                _positive_length(offset, "offset")
                if kind == "linear"
                else _bounded_angle(offset, "offset", 0.0, 360.0, include_high=True)
            )
        elif kind == "linear":
            feature.Length = resolve_extent()
        elif angle is not None:
            feature.Angle = resolve_extent()
        feature.Occurrences = int(occurrences)
        feature.Reversed = bool(reversed)
        return [feature.Name, body_obj.Name]

    params = {
        "doc": doc,
        "body": body,
        "name": name,
        "kind": kind,
        "originals": originals,
        "direction": direction,
        "axis": axis,
        "length": length,
        "angle": angle,
        "offset": offset,
        "occurrences": occurrences,
        "mode": mode,
        "reversed": reversed,
        "confirm": confirm,
    }
    return _feature_mutation(
        registry,
        doc,
        name,
        f"{kind} pattern {name}",
        "feature_pattern",
        params,
        op,
        audit_sink,
        precheck,
    )


def feature_mirror(
    registry: DocumentRegistry,
    doc: str | None = None,
    body: str | None = None,
    name: str | None = None,
    mirror_plane: dict | None = None,
    originals: list | None = None,
    confirm: dict | None = None,
    audit_sink: object = None,
) -> ResultEnvelope:
    """Mirror features across a plane into the target Body.

    ``mirror_plane`` is a selector naming a datum plane, one of the Body origin's base planes, or
    a planar face. ``originals`` defaults to the Body's ``Tip``.

    :raises ValidationError: the body or plane target is unknown, the name is taken, or an
        original names no object.
    """
    _require_partdesign()

    def precheck(document: object) -> None:
        body_obj = _resolve_body(document, body)
        _name_available(document, name)
        _resolve_originals(document, body_obj, originals)
        _resolve_direction(document, mirror_plane, "mirror_plane")

    def op(document: object) -> list[str]:
        body_obj = _resolve_body(document, body)
        targets = _resolve_originals(document, body_obj, originals)
        plane = _resolve_direction(document, mirror_plane, "mirror_plane")
        feature = _add_feature(document, body_obj, "PartDesign::Mirrored", name)
        feature.Originals = targets
        feature.MirrorPlane = plane
        return [feature.Name, body_obj.Name]

    params = {
        "doc": doc,
        "body": body,
        "name": name,
        "mirror_plane": mirror_plane,
        "originals": originals,
        "confirm": confirm,
    }
    return _feature_mutation(
        registry, doc, name, f"mirror {name}", "feature_mirror", params, op, audit_sink, precheck
    )


# --------------------------------------------------------------------------------------------
# Datums and parameter edits
# --------------------------------------------------------------------------------------------


def _check_map_mode(type_id: str, kind: str, mode: str) -> None:
    """Reject a ``map_mode`` the datum kind's own attach engine does not implement.

    The ``MapMode`` enumeration is the union across every attach engine, so the value being
    advertised does not mean this kind can use it. An unimplemented mode is only reported at
    recompute, which is inside the bracket, so an unchecked one costs a snapshot and a rollback
    instead of the pre-bracket rejection unresolvable attachment input is specified to get.

    A build whose engine cannot be probed leaves the mode unchecked rather than guessing.

    :raises ValidationError: ``mode`` is advertised but unimplemented for ``kind``.
    """
    implemented = shim.implemented_map_modes(type_id)
    if implemented is None or mode in implemented:
        return
    raise ValidationError(
        f"map_mode {mode!r} is not implemented for kind {kind!r}; "
        f"{kind} accepts {sorted(implemented)}"
    )


def feature_datum(
    registry: DocumentRegistry,
    doc: str | None = None,
    body: str | None = None,
    name: str | None = None,
    kind: str | None = None,
    attachment: dict | None = None,
    map_mode: str | None = None,
    offset: dict | None = None,
    confirm: dict | None = None,
    audit_sink: object = None,
) -> ResultEnvelope:
    """Create a datum plane, axis, point or coordinate system attached to existing geometry.

    ``attachment`` is a selector naming the object and subelement the datum attaches to;
    ``map_mode`` is the attachment mode and defaults to ``"FlatFace"``. ``offset`` displaces the
    datum along its own local Z after attachment.

    :raises ValidationError: the body or attachment target is unknown, the name is taken, or
        ``kind`` is not one of ``plane``/``axis``/``point``/``cs``.
    """
    _require_partdesign()
    if kind not in _DATUM_TYPES:
        raise ValidationError(f"kind must be one of {sorted(_DATUM_TYPES)}, got {kind!r}")
    type_id = _DATUM_TYPES[kind]
    if attachment is None:
        raise ValidationError("feature_datum requires an 'attachment' selector")
    target_name, subelement = _selector_subelement(attachment, "attachment", whole_object=True)
    mode = "FlatFace" if map_mode is None else map_mode

    def precheck(document: object) -> None:
        _resolve_body(document, body)
        _name_available(document, name)
        _resolve_object(document, target_name, "attachment")
        _check_map_mode(type_id, kind, mode)
        if offset is not None:
            _length_mm(offset, "offset")

    def op(document: object) -> list[str]:
        import FreeCAD

        body_obj = _resolve_body(document, body)
        target = _resolve_object(document, target_name, "attachment")
        feature = _add_feature(document, body_obj, type_id, name)
        shim.set_attachment(feature, [(target, [subelement])], mode)
        if offset is not None:
            feature.AttachmentOffset = FreeCAD.Placement(
                FreeCAD.Vector(0, 0, _length_mm(offset, "offset")), FreeCAD.Rotation()
            )
        return [feature.Name, body_obj.Name]

    params = {
        "doc": doc,
        "body": body,
        "name": name,
        "kind": kind,
        "attachment": attachment,
        "map_mode": map_mode,
        "offset": offset,
        "confirm": confirm,
    }
    return _feature_mutation(
        registry, doc, name, f"datum {name}", "feature_datum", params, op, audit_sink, precheck
    )


def _resolve_base_feature(document: object, name: str) -> object:
    """Return the object ``name`` for adoption as a Body's ``BaseFeature``.

    FreeCAD accepts an unusable target silently — a sketch or a shapeless object leaves the Body
    with a null shape, and a solid a second Body already adopted leaves both Bodies reporting the
    same geometry — so each is rejected here rather than committed.

    Adoption is read from the candidate's ``InList``: an adopted object gains a
    ``PartDesign::FeatureBase`` entry there, which a merely referenced object does not.

    :raises ValidationError: the object is unknown, carries no usable shape, or is already
        adopted by another Body.
    """
    target = _resolve_object(document, name, "base_feature")
    shape = getattr(target, "Shape", None)
    if shape is None or shape.isNull():
        raise ValidationError(f"base_feature {name} carries no shape to adopt")
    owners = [str(getattr(obj, "TypeId", "")) for obj in target.InList]
    if _FEATURE_BASE_TYPE in owners:
        raise ValidationError(f"base_feature {name} is already adopted by a Body")
    return target


def feature_body_create(
    registry: DocumentRegistry,
    doc: str | None = None,
    name: str | None = None,
    base_feature: str | None = None,
    confirm: dict | None = None,
    audit_sink: object = None,
) -> ResultEnvelope:
    """Create an empty PartDesign Body, the container every feature tool builds into.

    The new Body carries no solid: its ``Tip`` is unset and its ``Shape`` is null until a
    feature is added, which FreeCAD reports as valid and up to date. It brings an ``App::Origin``
    and that origin's plane, line and point children, all of which the fingerprint and the render
    set already exclude as datum features.

    ``base_feature`` optionally names an existing solid for the Body to adopt, so later features
    modify that solid instead of building from nothing.

    :raises ValidationError: the name is missing, already in use, or one FreeCAD would rewrite;
        or ``base_feature`` is unknown, carries no shape, or is already adopted by another Body.
    """
    _require_partdesign()

    def precheck(document: object) -> None:
        _name_available(document, name)
        if base_feature is not None:
            _resolve_base_feature(document, base_feature)

    def op(document: object) -> list[str]:
        body = document.addObject(_BODY_TYPE, name)
        if body.Name != name:
            raise ValidationError(f"{name} is not a usable FreeCAD object name")
        body.Label = name
        if base_feature is not None:
            body.BaseFeature = _resolve_base_feature(document, base_feature)
        return [body.Name]

    params = {"doc": doc, "name": name, "base_feature": base_feature, "confirm": confirm}
    return _feature_mutation(
        registry,
        doc,
        name,
        f"create body {name}",
        "feature_body_create",
        params,
        op,
        audit_sink,
        precheck,
    )


def _parameter_writes(feature: object, parameters: object) -> list[tuple[str, object]]:
    """Return the validated ``(property, value)`` writes a parameter edit will apply.

    A property the feature does not carry, one FreeCAD marks read-only, and a quantity whose
    unit does not match the property's dimension are all caller errors, so each is rejected
    before the transaction opens rather than raising inside it.
    """
    if not isinstance(parameters, dict) or not parameters:
        raise ValidationError("feature_set_parameters requires a non-empty 'parameters' object")
    writes: list[tuple[str, object]] = []
    for prop, raw in parameters.items():
        if prop not in list(feature.PropertiesList):
            raise ValidationError(f"{feature.Name} has no property named {prop!r}")
        if "ReadOnly" in list(feature.getEditorMode(prop) or []):
            raise ValidationError(f"{feature.Name}.{prop} is read-only")
        writes.append((prop, _parameter_value(feature, prop, raw)))
    return writes


def _parameter_value(feature: object, prop: str, raw: object) -> object:
    """Return the raw value to write to ``feature.prop`` from one wire parameter value."""
    type_id = str(feature.getTypeIdOfProperty(prop))
    if isinstance(raw, dict):
        if type_id == "App::PropertyAngle":
            return _angle_degrees(raw, f"{prop} value")
        return _length_mm(raw, f"{prop} value")
    if isinstance(raw, str):
        return _checked_enum(feature, prop, raw, f"{prop} value")
    if isinstance(raw, bool):
        return raw
    if isinstance(raw, (int, float)):
        if not math.isfinite(float(raw)):
            raise ValidationError(f"{prop} value must be finite, got {raw!r}")
        return raw
    raise ValidationError(f"{prop} value must be a quantity, number, boolean or enum string")


def feature_set_parameters(
    registry: DocumentRegistry,
    doc: str | None = None,
    feature: str | None = None,
    parameters: dict | None = None,
    confirm: dict | None = None,
    audit_sink: object = None,
) -> ResultEnvelope:
    """Edit a feature's driving properties and re-verify the solid inside the same transaction.

    ``parameters`` maps property names to values: a ``{value, unit}`` quantity for a dimension
    (``deg`` for an angle property, ``mm`` otherwise), a string for an enumerated property, or a
    bare number or boolean. Each is validated against the live feature before the bracket opens.

    :raises ValidationError: the feature is unknown, a named property does not exist or is
        read-only, or a value's unit or enumeration member is wrong for its property.
    """
    _require_partdesign()

    def precheck(document: object) -> None:
        _parameter_writes(_resolve_object(document, feature, "feature"), parameters)

    def op(document: object) -> list[str]:
        target = _resolve_object(document, feature, "feature")
        for prop, value in _parameter_writes(target, parameters):
            setattr(target, prop, value)
        body = getattr(target, "_Body", None)
        touched = [target.Name]
        if body is not None:
            touched.append(body.Name)
        return touched

    params = {"doc": doc, "feature": feature, "parameters": parameters, "confirm": confirm}
    return _feature_mutation(
        registry,
        doc,
        feature,
        f"set parameters on {feature}",
        "feature_set_parameters",
        params,
        op,
        audit_sink,
        precheck,
    )
