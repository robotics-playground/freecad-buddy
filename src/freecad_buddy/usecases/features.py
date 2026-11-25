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
from freecad_buddy.usecases.documents import (
    CodedValidationError,
    DocumentRegistry,
    ValidationError,
)
from freecad_buddy.usecases.parameter_types import PARAMETER_PROPERTY_TYPES

_ANGLE_UNITS = frozenset({"deg"})
_LENGTH_UNITS = frozenset({"mm"})

_BODY_TYPE = "PartDesign::Body"
_ORIGIN_TYPE = "App::Origin"
_LINK_TYPE = "App::Link"

# Types that carry ``App::GroupExtension`` but whose ``Group`` is an operand list, not a member
# list: a ``PartDesign::Boolean`` keeps the Bodies it fuses, cuts or intersects there (probed on
# 1.1.4: ``hasExtension("App::GroupExtension")`` is true for it).
_OPERAND_GROUP_TYPES = ("PartDesign::Boolean",)
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

# The extrude type FreeCAD 1.1 retired in favour of a second side (FeaturePad.cpp:39-44). Its
# enumeration slot survives only as a "?"-prefixed tombstone member, so the value cannot be set.
_EXTRUDE_RETIRED_TWO_LENGTHS = "TwoLengths"

# The Hole ThreadType member meaning "no thread". Every other member makes Diameter read-only and
# derives it from the thread's size tables instead.
_HOLE_NO_THREAD = "None"

_PATTERN_TYPES = {
    "linear": "PartDesign::LinearPattern",
    "polar": "PartDesign::PolarPattern",
}

# The pattern Mode members, folded, that spread the occurrences across a total extent (driving
# Length for a linear pattern and Angle for a polar one).
_PATTERN_EXTENT_MODES = frozenset({"extent"})

# The pattern Mode members, folded, that step the occurrences by a fixed Offset instead.
_PATTERN_OFFSET_MODES = frozenset({"spacing"})

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


def _feature_state(document: object, feature: str) -> dict:
    """Read the post-op feature summary, gated on ``verify_shape`` being able to grade it.

    A feature a rollback removed, or whose shape is null or unreadable for any reason, reports
    ``readable: False`` and carries no grading fields rather than a null a consumer would
    dereference. ``schema``, ``feature`` and ``readable`` are present on both paths, and no
    failure to read the state discards the mutation's own envelope.
    """
    try:
        graded = verify.read_shape(document, feature)
    except Exception:  # noqa: BLE001 - an ungradeable feature is reported, never raised
        return _unreadable_state(feature)
    if graded.get("status") != "OK":
        return _unreadable_state(feature)

    try:
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
    report: Callable[[object], dict] | None = None,
    state_probe: Callable[[object], object] | None = None,
    deleted: set[str] | None = None,
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
    :param report: for an op that creates no shape: reads the fields to add to an ``OK`` result
        from the returned document, in place of ``feature`` and ``feature_state``.
    :param state_probe: reads state the shape fingerprint cannot see; passed to ``run_mutation``.
    :param deleted: the names ``op`` deletes on purpose, filled by ``precheck``; read when the
        bracket opens and passed to ``run_mutation``.
    :raises ValidationError: the call carries no confirm authorizing it, or the request is
        malformed; neither writes a snapshot nor opens a transaction.
    """

    rebound: list = []

    def call(handle: str, document: object):
        approval, fp_before = confirm.gate_mutation(document, handle, tool, params)
        if precheck is not None:
            precheck(document)
        confirm.spend_confirm(approval, params)
        confirm.audit_approval(audit_sink, approval, params)
        rebound.append(document)
        result = transaction.run_mutation(
            document,
            handle,
            label,
            op,
            audit_sink=audit_sink,
            tool=tool,
            params=params,
            fp_before=fp_before,
            state_probe=state_probe,
            deleted=frozenset(deleted or ()),
        )
        rebound.append(result[0])
        # The reported state is read here, in the window that produced it: reading it after this
        # one closed would let a concurrent mutation land in between and leave `feature_state`
        # describing a document generation the `mutation` block did not create. `run_mutation`
        # may have reopened the document, so the state is read off what it returned.
        content = result[1].get("structured_content")
        if not isinstance(content, dict):
            content = {}
            result[1]["structured_content"] = content
        if report is None:
            content["feature"] = feature
            content["feature_state"] = _feature_state(result[0], feature)
        elif result[1]["status"] == "OK":
            content.update(report(result[0]))
        return result

    try:
        _, envelope = registry.with_document(doc, call)
    finally:
        if rebound:
            try:
                registry.rebind(doc, rebound[-1])
            except Exception:  # noqa: BLE001 - a failed rebind must not mask the real outcome
                pass
    return envelope


# --------------------------------------------------------------------------------------------
# Extrudes: pad and pocket
# --------------------------------------------------------------------------------------------


def _extrude_type(feature: object, up_to: object) -> str:
    """Return the extrude ``Type`` string, defaulting to ``Length``, checked against the build.

    The enumeration is never indexed: one of its positions carries a deprecation tombstone.

    :raises ValidationError: ``up_to`` is outside the build's enumeration, or names the retired
        two-length type, whose replacement ``second_length`` the message names.
    """
    # The tombstone spelling itself is a live enumeration member, so it is caught here too.
    if isinstance(up_to, str) and up_to.lstrip("?") == _EXTRUDE_RETIRED_TWO_LENGTHS:
        raise ValidationError(
            f"up_to={_EXTRUDE_RETIRED_TWO_LENGTHS!r} is retired in FreeCAD 1.1; give "
            "'second_length' for a second side opposite the first instead"
        )
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
    second_length: object,
    midplane: bool,
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
    if second_length is not None:
        if midplane:
            raise ValidationError(
                "second_length and midplane are exclusive: midplane splits 'length' evenly "
                "across both sides, while second_length sets the second side's own length"
            )
        _positive_length(second_length, "second_length")
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
        _precheck_extrude(
            document,
            body,
            profile,
            name,
            up_to,
            length,
            second_length,
            midplane,
            taper_angle,
            face,
            type_id,
        )

    def op(document: object) -> list[str]:
        body_obj = _resolve_body(document, body)
        profile_obj = _resolve_sketch(document, profile, "profile")
        feature = _add_feature(document, body_obj, type_id, name)
        feature.Profile = profile_obj
        feature.Type = _extrude_type(feature, up_to)
        if _extrude_needs_length(feature.Type):
            feature.Length = _length_mm(length, "length")
        if second_length is not None:
            shim.extrude_second_side(feature, _positive_length(second_length, "second_length"))
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
    rather than moving the total volume. ``second_length`` adds a second side of that length
    opposite the first.

    :raises ValidationError: the body or profile is unknown, the name is taken, ``up_to`` is
        outside the build's enumeration or is the retired ``"TwoLengths"``, a length-driven pad
        carries no ``length``, or ``second_length`` is given with ``midplane``.
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
    against the live enumeration of the feature being built. ``second_length`` adds a second side
    of that length opposite the first.

    :raises ValidationError: the body or profile is unknown, the name is taken, ``up_to`` is
        outside the build's enumeration or is the retired ``"TwoLengths"``, a length-driven
        pocket carries no ``length``, or ``second_length`` is given with ``midplane``.
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
# Loft and sweep
# --------------------------------------------------------------------------------------------

# Cost limits. Both OCC builds hold the Python interpreter lock, so the bridge timeout cannot stop
# a slow one; the request is measured and refused before the bracket instead. Timings are whole
# `recompute` calls on a development host, FreeCAD 1.1.4.
#
# Loft cost units are the edges of the profile and every section, a BSpline counting its poles:
# 50 sections of 100 line edges (5,000) 1.6 s; 100 of 200 (20,000) 11 s; 200 of 300 (60,000) 49 s;
# 20 closed BSplines of 200 poles (4,000) 1.6 s; 40 of 400 poles (16,000) 23 s. Accepted at the
# limit: 40 sections of 200 line edges (8,000) 4.9 s; 19 BSplines of 400 poles (7,619) 4.0 s;
# 39 of 200 poles (7,839) 6.7 s.
_LOFT_MAX_COST = 8000
# Sections are bounded on their own, because one-edge sections cost one unit each: smooth loft
# of 100 circles 0.09 s, 500 circles 1.6 s, 1,500 circles 19 s.
_LOFT_MAX_SECTIONS = 500
# Sweep cost units are profile units times spine units. A profile edge counts its poles (1 for
# any other curve); a spine edge counts 1 plus a tenth of its poles, rounded down. A 200-pole
# BSpline profile along a 20-turn helix of 194 poles (4,020) took 1.3 s. Line profiles: 100
# profile edges along 100 spine lines (10,000) 5.8 s; 200 along 200 (40,000) 69 s;
# 8 along 400 (3,200) 1.1 s; 200 along a 20-turn helix of 194 poles (4,000) 4.2 s; 400 along a
# 25-turn helix of 392 poles (16,000) 8.7 s.
_SWEEP_MAX_COST = 10000
_SWEEP_POLES_PER_UNIT = 10

# Only BSpline-like spine edges are sampled (a line or an analytic curve cannot reverse), and at
# most _SPINE_MAX_SAMPLED_EDGES of them, so the check itself stays short.
# A spine edge is sampled at this many parameters. A BSpline that doubles back on itself has a
# point of zero velocity: an AdditivePipe over one held the interpreter for more than 280 s
# (8 points through x = 0.5 i cos(0.3 i)). Its consecutive tangents flip to dot = -1.0; every
# legitimate spine tried (helix, sine, hairpin, circle, 100-segment polyline) stays above 0.98.
_SPINE_TANGENT_SAMPLES = 400
_SPINE_MAX_SAMPLED_EDGES = 100

_SWEEP_MODES = {"standard": "Standard", "frenet": "Frenet"}
_SPINE_SHAPE_TYPES = frozenset({"Edge", "Wire"})


class LoftSweepRefusal(CodedValidationError):
    """A refused ``feature_loft`` or ``feature_sweep`` request, carrying its ``detail.code``."""


def _require_bool(value: object, what: str) -> bool:
    if not isinstance(value, bool):
        raise ValidationError(f"{what} must be true or false, got {value!r}")
    return value


def _edge_poles(edge: object) -> int:
    """Return the pole count of a BSpline-like edge, or 0 for any other curve."""
    try:
        return len(edge.Curve.getPoles())
    except Exception:  # noqa: BLE001 - a curve that cannot report poles counts as plain
        return 0


def _section_shape(document: object, name: object, what: str) -> object:
    """Return the shape of the sketch ``name``, which must carry at least one wire."""
    sketch = _resolve_sketch(document, name, what)
    shape = _require_shape(sketch)
    if not shape.Wires:
        raise ValidationError(f"{what} {name} carries no wire")
    return shape


def _loft_sections(document: object, profile: object, sections: object) -> list[object]:
    """Return the section shapes after checking the section list against the profile.

    :raises ValidationError: the list is empty or malformed, repeats a sketch, holds the profile,
        or names a sketch whose wire count differs from the profile's (FreeCAD raises at
        recompute for that).
    """
    if not isinstance(sections, list) or not sections:
        raise LoftSweepRefusal(
            "loft.invalid_sections", "sections must be a non-empty list of sketch names"
        )
    if len(sections) > _LOFT_MAX_SECTIONS:
        raise LoftSweepRefusal(
            "loft.too_complex",
            f"{len(sections)} sections is above the limit of {_LOFT_MAX_SECTIONS}: loft fewer "
            "sections",
        )
    if len(set(map(str, sections))) != len(sections):
        raise LoftSweepRefusal("loft.invalid_sections", "sections must not repeat a sketch")
    if profile in sections:
        raise LoftSweepRefusal(
            "loft.invalid_sections", f"sections must not hold the profile {profile}"
        )
    wanted = len(_section_shape(document, profile, "profile").Wires)
    shapes = []
    for section in sections:
        shape = _section_shape(document, section, "section")
        if len(shape.Wires) != wanted:
            raise LoftSweepRefusal(
                "loft.wire_count_mismatch",
                f"section {section} has {len(shape.Wires)} wires, the profile has {wanted}; "
                "every section needs the same number of wires",
            )
        shapes.append(shape)
    return shapes


def _loft_cost(shapes: list[object]) -> int:
    return sum(_edge_poles(edge) or 1 for shape in shapes for edge in shape.Edges)


def feature_loft(
    registry: DocumentRegistry,
    doc: str | None = None,
    body: str | None = None,
    profile: str | None = None,
    sections: list[str] | None = None,
    name: str | None = None,
    ruled: bool = False,
    closed: bool = False,
    subtractive: bool = False,
    confirm: dict | None = None,
    audit_sink: object = None,
) -> ResultEnvelope:
    """Loft through the profile sketch and the section sketches, in the order given.

    ``ruled`` joins consecutive sections with straight surfaces; ``closed`` also joins the last
    section back to the profile and needs at least two sections (FreeCAD resets it silently
    otherwise). ``subtractive`` removes the lofted solid from the Body.

    :raises ValidationError: an input is unknown or not a sketch, or a flag is not a boolean.
    :raises LoftSweepRefusal: ``loft.invalid_sections`` (empty, repeated, or holding the
        profile), ``loft.wire_count_mismatch``, ``loft.closed_needs_sections`` or
        ``loft.too_complex`` (too many sections, or the sections cost more than the limit).
    """
    _require_partdesign()

    def precheck(document: object) -> None:
        _resolve_body(document, body)
        _name_available(document, name)
        shapes = _loft_sections(document, profile, sections)
        _require_bool(ruled, "ruled")
        _require_bool(subtractive, "subtractive")
        if _require_bool(closed, "closed") and len(sections) < 2:
            raise LoftSweepRefusal(
                "loft.closed_needs_sections",
                "closed needs at least 2 sections: FreeCAD ignores it for a single section",
            )
        cost = _loft_cost([_section_shape(document, profile, "profile"), *shapes])
        if cost > _LOFT_MAX_COST:
            raise LoftSweepRefusal(
                "loft.too_complex",
                f"the profile and sections hold {cost} edge units (a BSpline counts its poles), "
                f"above the limit of {_LOFT_MAX_COST}: loft fewer or simpler sections",
            )

    def op(document: object) -> list[str]:
        body_obj = _resolve_body(document, body)
        type_id = "PartDesign::SubtractiveLoft" if subtractive else "PartDesign::AdditiveLoft"
        feature = _add_feature(document, body_obj, type_id, name)
        feature.Profile = _resolve_sketch(document, profile, "profile")
        feature.Sections = [(_resolve_sketch(document, s, "section"), [""]) for s in sections]
        feature.Ruled = ruled
        feature.Closed = closed
        return [feature.Name, body_obj.Name]

    params = {
        "doc": doc,
        "body": body,
        "profile": profile,
        "sections": sections,
        "name": name,
        "ruled": ruled,
        "closed": closed,
        "subtractive": subtractive,
        "confirm": confirm,
    }
    return _feature_mutation(
        registry,
        doc,
        name,
        f"loft {name}",
        "feature_loft",
        params,
        op,
        audit_sink,
        precheck,
    )


def _spine_target(document: object, spine: object) -> tuple[object, str, list[object]]:
    """Return ``(object, subelement, edges)`` for a sweep spine.

    ``spine`` is a sketch Name, or a ``mapped_name`` selector naming one Edge, or a whole object
    (no ``mapped_name``). A whole object must be an Edge, a Wire or a compound of those.

    :raises ValidationError: the spine is unknown or, for a string, not a sketch.
    :raises LoftSweepRefusal: ``sweep.invalid_spine``: a Body, a subelement that is not an Edge,
        or a whole object that is not an edge, a wire or a compound of those.
    """
    if isinstance(spine, str):
        obj = _resolve_sketch(document, spine, "spine")
        subelement = ""
    else:
        obj_name, subelement = _selector_subelement(spine, "spine", whole_object=True)
        obj = _resolve_object(document, obj_name, "spine")
        if str(getattr(obj, "TypeId", "")) == _BODY_TYPE:
            raise LoftSweepRefusal("sweep.invalid_spine", f"spine must not be a Body: {obj_name}")
    shape = _require_shape(obj)
    if subelement:
        try:
            element = shape.getElement(subelement)
        except Exception as exc:  # noqa: BLE001 - an unresolvable subelement is caller input
            raise ValidationError(f"unresolvable spine selector {subelement!r}: {exc}") from exc
        if getattr(element, "ShapeType", "") != "Edge":
            raise LoftSweepRefusal(
                "sweep.invalid_spine",
                f"spine selector {subelement!r} resolves to a "
                f"{getattr(element, 'ShapeType', 'unknown')}, not an Edge",
            )
        return obj, subelement, [element]
    kinds = {shape.ShapeType}
    if shape.ShapeType == "Compound":
        kinds = {sub.ShapeType for sub in shape.SubShapes}
    if not shape.Edges or not kinds <= _SPINE_SHAPE_TYPES:
        raise LoftSweepRefusal(
            "sweep.invalid_spine",
            f"spine {obj.Name} is a {shape.ShapeType}; a spine must be an edge or a wire",
        )
    return obj, "", list(shape.Edges)


def _check_spine_tangents(edges: list[object]) -> None:
    """Refuse a spine edge whose direction reverses between two samples.

    :raises LoftSweepRefusal: ``sweep.degenerate_spine``, or ``sweep.too_complex`` when the
        spine holds more curved edges than the check samples.
    """
    curved = [edge for edge in edges if _edge_poles(edge)]
    if len(curved) > _SPINE_MAX_SAMPLED_EDGES:
        raise LoftSweepRefusal(
            "sweep.too_complex",
            f"the spine holds {len(curved)} BSpline edges, above the limit of "
            f"{_SPINE_MAX_SAMPLED_EDGES}: use fewer spine edges",
        )
    for edge in curved:
        first, last = edge.ParameterRange
        previous = None
        for index in range(_SPINE_TANGENT_SAMPLES + 1):
            parameter = first + (last - first) * index / _SPINE_TANGENT_SAMPLES
            try:
                tangent = edge.tangentAt(parameter)
            except Exception as exc:  # noqa: BLE001 - no tangent means zero velocity
                raise LoftSweepRefusal(
                    "sweep.degenerate_spine",
                    f"the spine has no tangent at parameter {parameter:g}: {exc}",
                ) from exc
            if previous is not None and previous.dot(tangent) < 0.0:
                raise LoftSweepRefusal(
                    "sweep.degenerate_spine",
                    "the spine doubles back on itself inside one edge; FreeCAD cannot sweep "
                    "along it and would hold the bridge. Split it into separate edges or "
                    "redraw it",
                )
            previous = tangent


def _sweep_cost(profile_shape: object, spine_edges: list[object]) -> int:
    profile_units = sum(_edge_poles(edge) or 1 for edge in profile_shape.Edges)
    spine_units = sum(1 + _edge_poles(edge) // _SWEEP_POLES_PER_UNIT for edge in spine_edges)
    return profile_units * spine_units


def feature_sweep(
    registry: DocumentRegistry,
    doc: str | None = None,
    body: str | None = None,
    profile: str | None = None,
    spine: str | dict | None = None,
    name: str | None = None,
    mode: str = "standard",
    subtractive: bool = False,
    confirm: dict | None = None,
    audit_sink: object = None,
) -> ResultEnvelope:
    """Sweep the profile sketch along a spine.

    ``spine`` is a sketch Name or a selector for one Edge or a whole edge or wire object.
    ``mode`` ``"standard"`` keeps the profile's orientation by the Standard law; ``"frenet"``
    follows the Frenet trihedron of the spine. ``subtractive`` removes the swept solid from the
    Body.

    :raises ValidationError: an input is unknown or not a sketch, or a flag is not a boolean.
    :raises LoftSweepRefusal: ``sweep.invalid_spine`` (the profile, a Body, or not an edge or
        wire), ``sweep.invalid_mode``, ``sweep.too_complex`` or ``sweep.degenerate_spine``.
    """
    _require_partdesign()

    def member() -> str:
        if not isinstance(mode, str) or mode not in _SWEEP_MODES:
            raise LoftSweepRefusal(
                "sweep.invalid_mode", f"mode must be one of {sorted(_SWEEP_MODES)}, got {mode!r}"
            )
        return _SWEEP_MODES[mode]

    def precheck(document: object) -> None:
        _resolve_body(document, body)
        _name_available(document, name)
        profile_shape = _section_shape(document, profile, "profile")
        obj, _, edges = _spine_target(document, spine)
        if obj.Name == profile:
            raise LoftSweepRefusal("sweep.invalid_spine", "spine must not be the profile sketch")
        _require_bool(subtractive, "subtractive")
        resolved = member()
        shim.probe_object(
            "PartDesign::AdditivePipe",
            lambda probe: _checked_enum(probe, "Mode", resolved, "mode"),
        )
        cost = _sweep_cost(profile_shape, edges)
        if cost > _SWEEP_MAX_COST:
            raise LoftSweepRefusal(
                "sweep.too_complex",
                f"the profile and spine cost {cost} units (profile units times spine units), "
                f"above the limit of {_SWEEP_MAX_COST}: use a simpler profile or spine",
            )
        _check_spine_tangents(edges)

    def op(document: object) -> list[str]:
        body_obj = _resolve_body(document, body)
        type_id = "PartDesign::SubtractivePipe" if subtractive else "PartDesign::AdditivePipe"
        feature = _add_feature(document, body_obj, type_id, name)
        feature.Profile = _resolve_sketch(document, profile, "profile")
        obj, subelement, _ = _spine_target(document, spine)
        feature.Spine = (obj, [subelement])
        feature.Mode = _checked_enum(feature, "Mode", member(), "mode")
        return [feature.Name, body_obj.Name]

    params = {
        "doc": doc,
        "body": body,
        "profile": profile,
        "spine": spine,
        "name": name,
        "mode": mode,
        "subtractive": subtractive,
        "confirm": confirm,
    }
    return _feature_mutation(
        registry,
        doc,
        name,
        f"sweep {name}",
        "feature_sweep",
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

    The base must also be the Body's ``Tip``. The new feature becomes the Tip and its solid is
    built from its base alone, so a base below the Tip would silently drop every feature after
    it. FreeCAD's GUI allows that; this bridge refuses it.

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
    tip = getattr(body, "Tip", None)
    tip_name = str(getattr(tip, "Name", "")) if tip is not None else ""
    if base_obj.Name != tip_name:
        raise ValidationError(
            f"dress-up base {base_obj.Name} is not the Tip of Body {body.Name}; the Tip is "
            f"{tip_name or 'unset'}. A dress-up builds from its base alone, so it would drop "
            "every feature after the base; name the Tip as the base"
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
        if radius is not None:
            _positive_length(radius, "radius")

    def apply_sizes(feature: object) -> None:
        if radius is not None:
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
        if size is not None:
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
        if size is not None:
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

    The live member is mapped to the dimension it drives: ``Extent`` to the extent dimension,
    ``Spacing`` to ``Offset``. A live member outside that mapping, such as one a future build
    adds, is refused rather than guessed. ``None`` leaves the build default, which is the extent
    mode.

    :raises ValidationError: the mode is outside the build's enumeration, or it is a live member
        this mapping does not cover.
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
    enumeration. The extent mode spreads the occurrences across ``length`` (linear) or ``angle``
    (polar); the offset mode steps them by ``offset`` instead. Only the dimension the resolved
    mode reads may be supplied, because FreeCAD marks the other one read-only. Omitting ``mode``
    leaves the build's default, which is the extent mode.

    :raises ValidationError: the body is unknown, the name is taken, ``kind`` is not
        ``"linear"``/``"polar"``, the direction or axis target is unknown, an original is
        unknown, repeated or outside the Body, ``mode`` is outside the build's enumeration, the
        supplied dimension does not match the resolved mode, or ``occurrences`` is out of range.
    """
    _require_partdesign()
    if kind not in _PATTERN_TYPES:
        raise ValidationError(f"kind must be one of {sorted(_PATTERN_TYPES)}, got {kind!r}")
    type_id = _PATTERN_TYPES[kind]
    if occurrences is not None and (
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
        if occurrences is not None:
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


def _is_number(value: object) -> bool:
    """Whether ``value`` is an int or float; ``bool`` is an ``int`` subclass and is excluded."""
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _property_family(feature: object, prop: str, type_id: str) -> str | None:
    """Return the wire value family ``feature.prop`` accepts, or ``None`` when it takes none.

    ``"bool"`` for ``App::PropertyBool`` and ``"enum"`` for ``App::PropertyEnumeration``. The
    numeric families are read from the current value: ``"quantity"`` when it is a ``Quantity``
    (every unit-bearing property), ``"integer"`` when it is an int, ``"float"`` when it is a plain
    float. A type-id list would miss the many unit property types.
    """
    if type_id == "App::PropertyBool":
        return "bool"
    if type_id == "App::PropertyEnumeration":
        return "enum"
    import FreeCAD

    current = getattr(feature, prop)
    if isinstance(current, FreeCAD.Units.Quantity):
        return "quantity"
    if isinstance(current, int) and not isinstance(current, bool):
        return "integer"
    if isinstance(current, float):
        return "float"
    return None


def _parameter_value(feature: object, prop: str, raw: object) -> object:
    """Return the raw value to write to ``feature.prop`` from one wire parameter value.

    The value must match the property's family: a ``{value, unit}`` quantity or a bare number for
    a quantity property, a bare number for a unitless float property, an int for an integer
    property, a boolean for a boolean property, and a member string for an enumeration. FreeCAD
    would raise on any other pairing inside the transaction.

    :raises ValidationError: naming ``<feature>.<prop>`` and its type when the value does not
        match the family, or when the property is of a type this tool cannot write.
    """
    type_id = str(feature.getTypeIdOfProperty(prop))
    family = _property_family(feature, prop, type_id)
    where = f"{feature.Name}.{prop}"
    if family is None:
        raise ValidationError(f"{where} is a {type_id}, which feature_set_parameters cannot write")
    if family == "quantity" and isinstance(raw, dict):
        if type_id == "App::PropertyAngle":
            return _angle_degrees(raw, f"{prop} value")
        return _length_mm(raw, f"{prop} value")
    if family in ("quantity", "float") and _is_number(raw):
        if not math.isfinite(float(raw)):
            raise ValidationError(f"{prop} value must be finite, got {raw!r}")
        return raw
    if family == "integer" and isinstance(raw, int) and not isinstance(raw, bool):
        return raw
    if family == "bool" and isinstance(raw, bool):
        return raw
    if family == "enum" and isinstance(raw, str):
        return _checked_enum(feature, prop, raw, f"{prop} value")
    expected = {
        "quantity": "a {value, unit} quantity or a number",
        "float": "a number",
        "integer": "an integer",
        "bool": "a boolean",
        "enum": "an enumeration member string",
    }[family]
    raise ValidationError(f"{where} is a {type_id} and takes {expected}, got {raw!r}")


def feature_set_parameters(
    registry: DocumentRegistry,
    doc: str | None = None,
    feature: str | None = None,
    parameters: dict | None = None,
    confirm: dict | None = None,
    audit_sink: object = None,
) -> ResultEnvelope:
    """Edit a feature's driving properties and re-verify the solid inside the same transaction.

    ``parameters`` maps property names to values: a ``{value, unit}`` quantity or a bare number
    for a quantity property (``deg`` for an angle property, ``mm`` otherwise), a bare number for
    a unitless float property, an int for an integer property, a boolean for a boolean property,
    or a string for an enumerated property. Each is validated
    against the live feature before the bracket opens.

    :raises ValidationError: the feature is unknown, a named property does not exist, is
        read-only or is of a type this tool cannot write, or a value's type, unit or enumeration
        member is wrong for its property.
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


# --------------------------------------------------------------------------------------------
# VarSet parameters
# --------------------------------------------------------------------------------------------

_VARSET_TYPE = "App::VarSet"

_DEFAULT_PARAMETER_GROUP = "Parameters"
_MAX_PARAMETERS = 100

# ``App::PropertyInteger`` stores a C ``long``, which is 32 bits on Windows: a larger value raises
# ``OverflowError`` inside the transaction. The bound is the one every platform holds.
_MAX_INTEGER_PARAMETER = 2**31 - 1

# Every ASCII spelling the expression lexer returns as UNIT or CONSTANT
# (docs/references/FreeCAD/src/App/Expression.l). A VarSet property with one of these names adds
# without error, but ``<VarSet>.<name>`` then fails to parse in every expression, e.g.
# ``Failed to parse expression 'VS.W'`` (probed on FreeCAD 1.1.4). Longer names that merely begin
# with a symbol (``W2``, ``min2``) parse.
_EXPRESSION_RESERVED_NAMES = frozenset(
    (
        "A AS C CV F False G GHz GPa H Hz J K M MA MHz MN MOhm MPa MS MeV Mpsi N Nm None Ohm "
        "Pa S T THz Torr True V VA VAs W Wb Ws bar cal cd cft cm cwt deg dm e eV false ft g "
        "gon h in kA kHz kJ kN kOhm kPa kS kV kW kWh kcal keV kg km ksi l lb lbf lbm m mA mF "
        "mH mJ mK mN mS mTorr mV mW mbar mg mi mil min ml mm mmol mol mph nF nH nm oz pF pi "
        "psi rad s sqft st t thou true uF uH uK uS uTorr ug um yd"
    ).split()
)


# The names ``ObjectIdentifier::resolveProperty`` answers itself (App/ObjectIdentifier.cpp, the
# ``_props`` table) before it looks up a property, so ``<VarSet>._pla`` reads the placement and
# never a parameter of that name. ``addProperty`` accepts all of them without error.
_EXPRESSION_PSEUDO_PROPERTIES = frozenset(
    "_shape _pla _matrix __pla __matrix _self _app _part _re _py _math _coll _gui _cq".split()
)

# ``App::PropertyAngle`` and ``App::PropertyLength`` clamp a value to their bounds without an
# error (PropertyUnits.cpp ``AngleStandard``, ``LengthStandard``; probed: -5 mm reads 0 mm and
# 720 deg reads 360 deg), so a value outside them is refused instead of stored changed.
_ANGLE_LIMIT_DEGREES = 360.0


# Names the mutation bracket and the fingerprint read with ``getattr`` from every object they
# touch (``transaction._shape_bearing``, ``fingerprint.fingerprint``, ``tnp_guard``). A VarSet
# property of that name makes the VarSet look like a shape-bearing object, and the call always
# ends ``SPEC_FAILED`` (probed: parameter ``Shape``).
_PROJECT_READ_NAMES = frozenset({"Shape", "ElementMapVersion"})


def _unstorable(character: str) -> bool:
    """Whether FreeCAD fails to keep ``character`` in a string property.

    NUL cuts the value in memory. The characters below read back as ``_`` after the document is
    saved and reopened, which is how a snapshot restore reads it: the C0 controls except tab, line
    feed and carriage return, U+007F to U+0084, U+0086 to U+009F, U+FDD0 to U+FDEF and the last two
    code points of every plane. A lone surrogate cannot be encoded. Every other code point was
    kept in a save and reopen of the whole range (probed on FreeCAD 1.1.4).
    """
    code = ord(character)
    return (
        (code < 0x20 and character not in "\t\n\r")
        or 0x7F <= code <= 0x84
        or 0x86 <= code <= 0x9F
        or 0xD800 <= code <= 0xDFFF
        or 0xFDD0 <= code <= 0xFDEF
        or code & 0xFFFE == 0xFFFE
    )


class ParameterRefusal(CodedValidationError):
    """A refused ``feature_parameters_define`` request, carrying its ``detail.code`` (AD-17)."""


def _storable_text(text: str, what: str) -> str:
    """Return ``text`` after checking FreeCAD keeps it unchanged.

    :raises ParameterRefusal: ``parameters.invalid_string`` when it holds a character FreeCAD
        cuts or rewrites.
    """
    for index, character in enumerate(text):
        if _unstorable(character):
            raise ParameterRefusal(
                "parameters.invalid_string",
                f"{what} holds U+{ord(character):04X} at index {index}, a character FreeCAD "
                "cuts or changes when it stores the string",
            )
    return text


def _parameter_spec(
    raw: object, index: int, builtin: frozenset[str], attributes: frozenset[str]
) -> dict:
    """Return one validated parameter as ``{name, type, value, group, description}``.

    ``value`` is what the property takes: a float in mm or degrees for ``length`` and ``angle``.

    :raises ParameterRefusal: the name is a lexer unit or constant, or a name a VarSet or an
        expression already uses.
    :raises ValidationError: any other malformed field.
    """
    where = f"parameters[{index}]"
    if not isinstance(raw, dict):
        raise ValidationError(f"{where} must be an object, got {raw!r}")
    name, kind, value = raw.get("name"), raw.get("type"), raw.get("value")
    if not isinstance(name, str) or not _OBJECT_NAME.fullmatch(name):
        raise ValidationError(
            f"{where}.name {name!r} must start with a letter or underscore and hold only ASCII "
            "letters, digits and underscores"
        )
    if name in _EXPRESSION_RESERVED_NAMES:
        raise ParameterRefusal(
            "parameters.unit_symbol_name",
            f"{where}.name {name!r} is a unit or constant to FreeCAD's expression parser, so any "
            "expression that reads it fails to parse; choose another name, for example "
            f"{name}_value",
        )
    if (
        name in builtin
        or name in attributes
        or name in _EXPRESSION_PSEUDO_PROPERTIES
        or name in _PROJECT_READ_NAMES
    ):
        raise ParameterRefusal(
            "parameters.reserved_name",
            f"{where}.name {name!r} is a name a VarSet or an expression already uses",
        )
    if kind not in PARAMETER_PROPERTY_TYPES:
        raise ValidationError(
            f"{where}.type must be one of {sorted(PARAMETER_PROPERTY_TYPES)}, got {kind!r}"
        )
    group, description = raw.get("group"), raw.get("description")
    if group is not None and (not isinstance(group, str) or not group):
        raise ValidationError(f"{where}.group must be a non-empty string, got {group!r}")
    if description is not None and not isinstance(description, str):
        raise ValidationError(f"{where}.description must be a string, got {description!r}")
    for text, field in ((group, "group"), (description, "description")):
        if text is not None:
            _storable_text(text, f"{where}.{field}")
    try:
        parsed = _parameter_write_value(kind, value, f"{where}.value")
    except OverflowError:
        raise ValidationError(f"{where}.value is too large to be a number") from None
    return {
        "name": name,
        "type": kind,
        "value": parsed,
        "group": group,
        "description": description,
    }


def _parameter_write_value(kind: str, value: object, what: str) -> object:
    """Return ``value`` as the Python value the ``kind`` property takes.

    A ``length`` or ``angle`` is a float in mm or degrees, from a ``{value, unit}`` quantity.

    :raises ValidationError: the value does not match ``kind``.
    """
    if kind == "length":
        millimetres = _length_mm(value, what)
        if millimetres < 0:
            raise ValidationError(f"{what} must not be negative, got {millimetres} mm")
        return millimetres
    if kind == "angle":
        degrees = _angle_degrees(value, what)
        if abs(degrees) > _ANGLE_LIMIT_DEGREES:
            raise ValidationError(
                f"{what} must be within +-{_ANGLE_LIMIT_DEGREES:g} deg, got {degrees} deg"
            )
        return degrees
    if kind == "float":
        if not _is_number(value) or not math.isfinite(float(value)):
            raise ValidationError(f"{what} must be a finite number, got {value!r}")
        return float(value)
    if kind == "integer":
        if (
            not isinstance(value, int)
            or isinstance(value, bool)
            or abs(value) > _MAX_INTEGER_PARAMETER
        ):
            raise ValidationError(
                f"{what} must be an integer within +-{_MAX_INTEGER_PARAMETER}, got {value!r}"
            )
        return value
    if kind == "bool":
        if not isinstance(value, bool):
            raise ValidationError(f"{what} must be true or false, got {value!r}")
        return value
    if not isinstance(value, str):
        raise ValidationError(f"{what} must be a string, got {value!r}")
    return _storable_text(value, what)


def _parameter_specs(parameters: object) -> list[dict]:
    """Return every parameter of the request, validated, in request order.

    :raises ParameterRefusal: a name appears twice.
    :raises ValidationError: the list is empty or too long, or an item is malformed.
    """
    if not isinstance(parameters, list) or not 1 <= len(parameters) <= _MAX_PARAMETERS:
        raise ValidationError(f"'parameters' must be a list of 1 to {_MAX_PARAMETERS} items")
    builtin = shim.varset_builtin_properties()
    if not builtin:
        raise ValidationError("the built-in properties of App::VarSet could not be read")
    attributes = shim.varset_attribute_names()
    specs = [
        _parameter_spec(raw, index, builtin, attributes) for index, raw in enumerate(parameters)
    ]
    names = [spec["name"] for spec in specs]
    for name in names:
        if names.count(name) > 1:
            raise ParameterRefusal(
                "parameters.duplicate_name", f"parameter {name!r} appears more than once"
            )
    return specs


def _precheck_parameters(document: object, varset: object, specs: list[dict]) -> None:
    """Refuse a request the document cannot take, before the bracket opens.

    :raises ParameterRefusal: ``varset`` names another kind of object, an existing property has
        a different type than the request, or an updated property is bound by an expression.
    :raises ValidationError: ``varset`` is not a usable object name, or an updated property is
        read-only.
    """
    if not isinstance(varset, str) or not _OBJECT_NAME.fullmatch(varset):
        raise ValidationError(
            f"varset {varset!r} must start with a letter or underscore and hold only ASCII "
            "letters, digits and underscores"
        )
    if varset in _EXPRESSION_RESERVED_NAMES:
        raise ParameterRefusal(
            "parameters.unit_symbol_name",
            f"varset {varset!r} is a unit or constant to FreeCAD's expression parser, so no "
            f"expression could name it; choose another name, for example {varset}_params",
        )
    target = document.getObject(varset)
    if target is None:
        return
    if target.TypeId != _VARSET_TYPE:
        raise ParameterRefusal(
            "parameters.not_a_varset", f"{varset} is a {target.TypeId}, not an {_VARSET_TYPE}"
        )
    bound = {path for path, _ in target.ExpressionEngine}
    for spec in specs:
        name = spec["name"]
        if name not in target.PropertiesList:
            continue
        existing = target.getTypeIdOfProperty(name)
        wanted = PARAMETER_PROPERTY_TYPES[spec["type"]]
        if existing != wanted:
            raise ParameterRefusal(
                "parameters.type_conflict",
                f"{varset}.{name} is a {existing}; a {spec['type']} parameter is a {wanted}",
            )
        for given, current, field in (
            (spec["group"], target.getGroupOfProperty(name), "group"),
            (spec["description"], target.getDocumentationOfProperty(name), "description"),
        ):
            if given is not None and given != current:
                raise ParameterRefusal(
                    "parameters.metadata_immutable",
                    f"{varset}.{name} exists with {field} {current!r}; FreeCAD does not undo a "
                    f"{field} change, so it is set only when the parameter is created",
                )
        if name in bound:
            raise ParameterRefusal(
                "parameters.bound_by_expression",
                f"{varset}.{name} is bound by an expression, which the next recompute would "
                "apply over the new value; clear the binding first",
            )
        if "ReadOnly" in target.getPropertyStatus(name):
            raise ValidationError(f"{varset}.{name} is read-only")


def _holds_value(target: object, spec: dict) -> bool:
    """Whether ``target`` already has the property with exactly the requested value."""
    name = spec["name"]
    if name not in target.PropertiesList:
        return False
    current = getattr(target, name)
    if spec["type"] == "length":
        return current.getValueAs("mm") == spec["value"]
    if spec["type"] == "angle":
        return current.getValueAs("deg") == spec["value"]
    return current == spec["value"]


def _write_parameter(target: object, spec: dict) -> str:
    """Add or update one parameter on ``target``; return ``added``, ``updated`` or ``unchanged``.

    A property already holding the value is not written: FreeCAD records no undo step for some
    same-value writes (a string), and a call that wrote only those would leave ``document_undo``
    reverting the step before it. Group and description are set when the property is created and
    never after, because FreeCAD does not undo them.
    """
    name = spec["name"]
    if name not in target.PropertiesList:
        target.addProperty(
            PARAMETER_PROPERTY_TYPES[spec["type"]],
            name,
            spec["group"] or _DEFAULT_PARAMETER_GROUP,
            spec["description"] or "",
        )
        setattr(target, name, spec["value"])
        return "added"
    if _holds_value(target, spec):
        return "unchanged"
    setattr(target, name, spec["value"])
    return "updated"


# Property types whose repr carries a memory address or an object handle, so two readings of the
# same value differ and a snapshot restore would never compare equal.
_UNSTABLE_REPR_TYPES = ("App::PropertyPythonObject", "App::PropertyLink", "App::PropertyXLink")


def _varset_state(varset: str) -> Callable[[object], object]:
    """Return a reader of ``varset``'s full property state, for the rollback proof.

    The state is ``None`` while the object does not exist, else every property's type, group,
    documentation, value and bound expression. The shape fingerprint holds none of it.
    """

    def read(document: object) -> object:
        target = document.getObject(varset)
        if target is None:
            return None
        expressions = dict(target.ExpressionEngine)
        state = {}
        for prop in sorted(target.PropertiesList):
            type_id = target.getTypeIdOfProperty(prop)
            try:
                # Such a property has no stable repr and this tool never writes one, so only
                # its presence and type are compared.
                unstable = type_id.startswith(_UNSTABLE_REPR_TYPES)
                value = "<skipped>" if unstable else repr(getattr(target, prop))
            except Exception:  # noqa: BLE001 - an unreadable value still differs from a readable one
                value = "<unreadable>"
            state[prop] = (
                type_id,
                target.getGroupOfProperty(prop),
                target.getDocumentationOfProperty(prop),
                value,
                expressions.get(prop),
            )
        return (target.TypeId, state)

    return read


def _unchanged_envelope(varset: str, names: list[str]) -> ResultEnvelope:
    """The ``OK`` result of a call that changes nothing: no transaction, no mutation block."""
    content = {
        "varset": varset,
        "added": [],
        "updated": [],
        "unchanged": names,
        "undo_steps": 0,
    }
    return {
        "schema": "fcb.result-envelope/1",
        "status": "OK",
        "detail": None,
        "structured_content": content,
        "text": f"{varset}: {len(names)} parameter(s) already hold the values; no undo "
        "step recorded, so document_undo would revert an earlier step.",
    }


def feature_parameters_define(
    registry: DocumentRegistry,
    doc: str | None = None,
    varset: str | None = None,
    parameters: list | None = None,
    confirm: dict | None = None,
    audit_sink: object = None,
) -> ResultEnvelope:
    """Create the VarSet ``varset`` when missing, then add or update typed parameters on it.

    Each parameter is ``{name, type, value, group?, description?}``; a ``length`` or ``angle``
    value is a ``{value, unit}`` quantity in ``mm`` or ``deg``. A name the VarSet lacks is added;
    one it holds with the same type is updated. ``added``, ``updated`` and ``unchanged`` (already
    holding the value, not written) name them in request order and appear on an ``OK`` result
    only, with ``undo_steps``: 1 when the call recorded an undo step, 0 when it changed nothing.
    A call that changes nothing opens no transaction and has no ``mutation`` block, so
    ``document_undo`` after it would revert an earlier step.

    The rollback proof also reads the VarSet's properties back against their pre-mutation state,
    because the shape fingerprint cannot see a VarSet change.

    :raises ValidationError: the build has no ``App::VarSet``, or a field is malformed.
    :raises ParameterRefusal: a ``ValidationError`` whose ``code`` is one of
        ``parameters.unit_symbol_name``, ``parameters.reserved_name``,
        ``parameters.duplicate_name``, ``parameters.not_a_varset``, ``parameters.type_conflict``
        ``parameters.bound_by_expression``, ``parameters.metadata_immutable`` and
        ``parameters.invalid_string``; the dispatcher puts it in ``detail.code``.
    """
    if not shim.varset_available():
        raise ValidationError("App::VarSet is unavailable on this FreeCAD build")
    outcome: dict[str, list[str]] = {"added": [], "updated": [], "unchanged": []}

    def changes_nothing(_handle: str, document: object) -> bool:
        specs = _parameter_specs(parameters)
        _precheck_parameters(document, varset, specs)
        target = document.getObject(varset)
        return target is not None and all(_holds_value(target, spec) for spec in specs)

    if registry.with_document(doc, changes_nothing):
        return _unchanged_envelope(varset, [p["name"] for p in parameters])

    def precheck(document: object) -> None:
        _precheck_parameters(document, varset, _parameter_specs(parameters))

    def op(document: object) -> list[str]:
        target = document.getObject(varset)
        if target is None:
            target = document.addObject(_VARSET_TYPE, varset)
            if target.Name != varset:
                raise ValidationError(f"{varset} is not a usable FreeCAD object name")
            target.Label = varset
        for spec in _parameter_specs(parameters):
            outcome[_write_parameter(target, spec)].append(spec["name"])
        return [target.Name]

    def report(document: object) -> dict:
        # Undo is switched on inside the bracket when it can be; a document that stays at
        # UndoMode 0 commits no step.
        recorded = bool(outcome["added"] or outcome["updated"]) and bool(document.UndoMode)
        steps = 1 if recorded else 0
        return {"varset": varset, **outcome, "undo_steps": steps}

    params = {"doc": doc, "varset": varset, "parameters": parameters, "confirm": confirm}
    return _feature_mutation(
        registry,
        doc,
        varset,
        f"define parameters on {varset}",
        "feature_parameters_define",
        params,
        op,
        audit_sink,
        precheck,
        report,
        _varset_state(varset),
    )


# --------------------------------------------------------------------------------------------
# Object deletion
# --------------------------------------------------------------------------------------------


class ObjectDeleteRefusal(CodedValidationError):
    """A refused ``document_object_delete`` request, carrying its ``detail.code`` (AD-17)."""


def _names(objects: object) -> set[str]:
    return {obj.Name for obj in objects or ()}


def _origin_objects(owner: object) -> list[object]:
    """Return the origin objects ``owner`` owns: its ``App::Origin`` and that Origin's features.

    A Part::LocalCoordinateSystem carries its axes and planes itself (``OriginFeatures`` with no
    ``Origin`` link). The ``Origin`` attribute is checked by type: a FEM post function has an
    ``Origin`` property that is a vector.
    """
    origin = getattr(owner, "Origin", None)
    if getattr(origin, "TypeId", None) == _ORIGIN_TYPE:
        return [origin, *(origin.OriginFeatures or ())]
    return list(getattr(owner, "OriginFeatures", None) or ())


def _origin_owner(document: object, obj: object) -> object | None:
    """Return the object that owns the origin object ``obj``; ``None`` when ``obj`` is not one.

    A Body, Part or local coordinate system owns axes, planes and a point. Deleting one of them
    alone leaves the owner without a plane the sketches attach to.
    """
    for candidate in document.Objects:
        if candidate.TypeId == _ORIGIN_TYPE or candidate.Name == obj.Name:
            continue
        if obj.Name in _names(_origin_objects(candidate)):
            return candidate
    return None


def _owned_by(owner: object) -> list[object]:
    """Return what deleting ``owner`` takes with it: a Body's group, and its origin objects."""
    owned = []
    if owner.TypeId == _BODY_TYPE:
        owned.extend(owner.Group)
    owned.extend(_origin_objects(owner))
    if owner.isDerivedFrom(_LINK_TYPE) and owner.ElementCount:
        # The GUI delete removes the elements of a link array with it (ViewProviderLink::onDelete).
        owned.extend(owner.ElementList)
    return owned


def _with_owned(document: object, names: set[str]) -> set[str]:
    """Return ``names`` plus everything the Bodies and Parts among them own."""
    expanded = set(names)
    for name in names:
        expanded.update(_names(_owned_by(document.getObject(name))))
    return expanded


def _is_member_container(obj: object) -> bool:
    """Whether ``obj`` only lists members in ``Group``: a Body, Part, group or a subclass of one."""
    return obj.hasExtension("App::GroupExtension") and not any(
        obj.isDerivedFrom(type_id) for type_id in _OPERAND_GROUP_TYPES
    )


def _expression_names(obj: object, members: list[object]) -> bool:
    """Whether an expression on ``obj`` names one of ``members``, by Name or as ``<<Label>>``.

    A Name counts at the start of an identifier path only, so ``VS.Pad2`` (a property of another
    object) does not name the object ``Pad2``. A match that is not a real reference makes the
    caller refuse, which is the safe side.
    """
    for _path, expression in getattr(obj, "ExpressionEngine", None) or ():
        text = str(expression)
        for member in members:
            by_name = rf"(?<![A-Za-z0-9_.#]){re.escape(member.Name)}(?![A-Za-z0-9_])"
            if re.search(by_name, text) or f"<<{member.Label}>>" in text:
                return True
    return False


def _dependents(document: object, delete_set: set[str]) -> list[str]:
    """Return the objects outside ``delete_set`` whose ``OutList`` holds a member of it.

    A pure container (a Body, Part or group) that holds a member only in its ``Group`` is not a
    dependent: removing the member leaves the container valid. Any other holder is, including a
    ``PartDesign::Boolean``, whose ``Group`` is its list of operand Bodies. A container with an
    expression that names a member is a dependent too, because the expression fails once the
    member is gone. ``OutList`` includes the objects an expression names, so an object bound to a
    deleted one is a dependent.
    """
    found = []
    for obj in document.Objects:
        if obj.Name in delete_set:
            continue
        held = _names(obj.OutList) & delete_set
        if not held:
            continue
        only_members = _is_member_container(obj) and held <= _names(obj.Group)
        if only_members and not _expression_names(obj, [document.getObject(n) for n in held]):
            continue
        found.append(obj.Name)
    return found


def _delete_plan(
    document: object, objects: object, with_dependents: bool
) -> tuple[list[str], list[str]]:
    """Return ``(names to delete, names deleted only as dependents)``, both in document order.

    :raises ValidationError: ``objects`` is empty or malformed, or names an unknown object.
    :raises ObjectDeleteRefusal: ``delete.origin_object`` for an Origin or Origin feature whose
        owner is not deleted too; ``delete.has_dependents`` when objects outside the set depend on
        it and ``with_dependents`` is false.
    """
    if not isinstance(objects, list) or not objects:
        raise ValidationError("objects must be a non-empty list of object names")
    requested = {_resolve_object(document, name, "objects").Name for name in objects}
    for name in sorted(requested):
        owner = _origin_owner(document, document.getObject(name))
        if owner is not None and owner.Name not in requested:
            raise ObjectDeleteRefusal(
                "delete.origin_object",
                f"{name} belongs to the Origin of {owner.Name}; delete {owner.Name} to remove it",
            )
    base_set = _with_owned(document, requested)
    delete_set = set(base_set)
    dependents = _dependents(document, delete_set)
    if dependents and not with_dependents:
        raise ObjectDeleteRefusal(
            "delete.has_dependents",
            f"objects that depend on the delete set: {', '.join(dependents)}; "
            "pass with_dependents true to delete them too",
        )
    while dependents:
        delete_set = _with_owned(document, delete_set | set(dependents))
        dependents = _dependents(document, delete_set)
    ordered = [obj.Name for obj in document.Objects if obj.Name in delete_set]
    return ordered, [name for name in ordered if name not in base_set]


def _owning_body(document: object, obj: object) -> object | None:
    """Return the Body whose ``Group`` holds ``obj``, or ``None``."""
    for candidate in document.Objects:
        if candidate.TypeId == _BODY_TYPE and obj.Name in _names(candidate.Group):
            return candidate
    return None


def _object_state(document: object) -> tuple:
    """Read the object set the shape fingerprint cannot see, for the rollback proof.

    Per object: name, label, type, the names it depends on, for a Body its ``Tip`` and ``Group``,
    and ``Visibility``. The dependency names matter: an object that FreeCAD restores without its
    expression dependency has the same name and label as before.
    """
    state = []
    for obj in document.Objects:
        body_state = ()
        if obj.TypeId == _BODY_TYPE:
            tip = obj.Tip.Name if obj.Tip is not None else None
            body_state = (tip, tuple(member.Name for member in obj.Group))
        state.append(
            (
                obj.Name,
                obj.Label,
                obj.TypeId,
                tuple(sorted(_names(obj.OutList))),
                body_state,
                getattr(obj, "Visibility", None),
            )
        )
    return tuple(sorted(state))


def document_object_delete(
    registry: DocumentRegistry,
    doc: str | None = None,
    objects: list | None = None,
    with_dependents: bool = False,
    confirm: dict | None = None,
    audit_sink: object = None,
) -> ResultEnvelope:
    """Delete objects, and with them what a Body, Part or link array owns, inside the AD-5 bracket.

    A Body takes its ``Group`` members, its Origin and the Origin features with it. A feature of a
    Body that stays goes through ``Body.removeObject`` first, so ``Tip`` and the next feature's
    ``BaseFeature`` stay valid. Objects outside the delete set whose ``OutList`` holds a deleted
    object are dependents: with ``with_dependents`` false any dependent refuses the call, with
    true the closure of dependents is deleted too. ``deleted`` on an ``OK`` result names every
    removed object in document order and ``dependents`` the ones removed only for that reason.

    The rollback proof reads the object set back (``_object_state``), because a deleted shape-less
    object does not change the shape fingerprint.

    :raises ValidationError: ``objects`` is empty or names an unknown object.
    :raises ObjectDeleteRefusal: ``delete.has_dependents`` or ``delete.origin_object``; the
        dispatcher puts the code in ``detail.code``.
    """
    plan: dict[str, list[str]] = {"deleted": [], "dependents": []}
    deleted: set[str] = set()

    def precheck(document: object) -> None:
        plan["deleted"], plan["dependents"] = _delete_plan(document, objects, with_dependents)
        deleted.update(plan["deleted"])

    def op(document: object) -> list[str]:
        touched = list(plan["deleted"])
        for name in reversed(plan["deleted"]):
            target = document.getObject(name)
            if target is None:
                # Removing a Body can remove its Origin and members first; that is the delete
                # this loop is carrying out, and the survivors check below still runs.
                continue
            body = _owning_body(document, target)
            if body is not None and body.Name not in deleted:
                previous = getattr(target, "BaseFeature", None)
                shown = target.Visibility
                body.removeObject(target)
                if shown and previous is not None and previous.Name not in deleted:
                    # PartDesign ViewProvider::onDelete shows the previous feature when the
                    # deleted one was visible; Document.removeObject alone leaves the Body empty.
                    previous.Visibility = True
                    touched.append(previous.Name)
                if body.Name not in touched:
                    touched.append(body.Name)
            document.removeObject(name)
        survivors = [name for name in plan["deleted"] if document.getObject(name) is not None]
        if survivors:
            raise RuntimeError(f"FreeCAD did not delete: {', '.join(survivors)}")
        return touched

    def report(_document: object) -> dict:
        return dict(plan)

    params = {
        "doc": doc,
        "objects": objects,
        "with_dependents": with_dependents,
        "confirm": confirm,
    }
    first = objects[0] if isinstance(objects, list) and objects else ""
    return _feature_mutation(
        registry,
        doc,
        first,
        f"delete {', '.join(map(str, objects or ()))}",
        "document_object_delete",
        params,
        op,
        audit_sink,
        precheck,
        report,
        _object_state,
        deleted,
    )
