"""Read-only introspection use cases.

Exposes ``query_capabilities`` (runtime capability probes) and the six Phase-0 read-only
``query_*`` tools over an explicit ``doc`` handle: tree summary, object properties, mass
properties, dependency edges, sketch geometry/constraints, and placement. Every query resolves
its handle through the ``DocumentRegistry`` lock and never mutates: no recompute, no property
write, no viewport touch.
"""

from __future__ import annotations

import math

from freecad_buddy.contracts import ResultEnvelope, mirror_text
from freecad_buddy.usecases import shim
from freecad_buddy.usecases.documents import DocumentRegistry, ValidationError


def _ok_envelope(structured: dict) -> ResultEnvelope:
    return {
        "schema": "fcb.result-envelope/1",
        "status": "OK",
        "detail": None,
        "structured_content": structured,
        "text": mirror_text(structured),
    }


def query_capabilities(exec_enabled: bool = False, render: str = "none") -> ResultEnvelope:
    """Report runtime capabilities: FreeCAD version, element-map, serializer, VarSet, render, exec.

    Every field is a live probe. ``render`` is the host-probed render-ladder mode and
    ``exec_enabled`` reflects whether the exec tool is reachable.
    """
    structured = dict(shim.capability_banner(render))
    structured["exec_enabled"] = exec_enabled
    return _ok_envelope(structured)


def _quantity(value: float, unit: str) -> dict:
    """Wrap a dimensional value as a ``{value, unit}`` Quantity.

    A non-finite value (``nan``/``inf`` from a degenerate shape) is reported as ``None`` so the
    envelope stays valid JSON.
    """
    number = float(value)
    return {"value": number if math.isfinite(number) else None, "unit": unit}


_CLEAN_STATUS = {"", "Valid", "Touched"}


def _status_string(obj: object) -> str | None:
    """Return ``obj.getStatusString()`` when it reports an error state, else ``None``.

    A clean object reports ``"Valid"`` (or ``"Touched"`` when pending a recompute); those are
    surfaced as ``None`` so ``error`` carries only a genuine error string.
    """
    getter = getattr(obj, "getStatusString", None)
    if getter is None:
        return None
    status = getter()
    return None if status in _CLEAN_STATUS else status


def _resolve_object(document: object, name: str | None):
    """Return the object named ``name`` on ``document``, or raise ``ValidationError``.

    Resolves by immutable ``Name``; never keys on ``Label``.
    """
    if not name:
        raise ValidationError("missing required 'object' name")
    obj = document.getObject(name)
    if obj is None:
        raise ValidationError(f"unknown object: {name}")
    return obj


def _json_safe(value: object) -> object:
    """Return a JSON-safe view of a property value, stringifying anything unsupported."""
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    return str(value)


def _read_property(obj: object, prop: str) -> object:
    """Return a JSON-safe view of ``obj.prop``, or ``None`` if reading it raises."""
    try:
        raw = getattr(obj, prop)
    except Exception:
        return None
    return _json_safe(raw)


def _node_cap(max_nodes: int) -> int:
    """Coerce ``max_nodes`` to a non-negative int; a non-integer raises ``ValidationError``."""
    try:
        return max(0, int(max_nodes))
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValidationError(f"invalid max_nodes: {max_nodes!r}") from exc


_ANGLE_CONSTRAINT_TYPES = {"Angle", "AngleViaPoint"}
_DIMENSIONAL_LENGTH_TYPES = {"Distance", "DistanceX", "DistanceY", "Radius", "Diameter"}


def _constraint_quantity(constraint_type: str, value: float) -> dict | None:
    """Wrap a constraint value with its unit, or ``None`` if the type carries no dimension.

    Angle constraints store radians and are reported in degrees; length constraints report mm.
    """
    if constraint_type in _ANGLE_CONSTRAINT_TYPES:
        return _quantity(math.degrees(value), "deg")
    if constraint_type in _DIMENSIONAL_LENGTH_TYPES:
        return _quantity(value, "mm")
    return None


def query_tree_summary(
    registry: DocumentRegistry,
    doc: str | None = None,
    max_nodes: int = 100,
) -> ResultEnvelope:
    """Summarize the document feature tree, bounded by ``max_nodes``.

    Emits at most ``max_nodes`` nodes drawn from the flat ``document.Objects`` list, each with
    name, label, type, ``children_count`` (``OutList`` size), and ``error`` (``getStatusString()``
    or null). ``total_objects`` is the full count; ``truncated`` is true when the cap clipped it.
    """

    def read(_handle: str, document: object) -> ResultEnvelope:
        objects = list(document.Objects)
        total = len(objects)
        cap = _node_cap(max_nodes)
        emitted = objects[:cap]
        nodes = [
            {
                "name": obj.Name,
                "label": obj.Label,
                "type": obj.TypeId,
                "children_count": len(list(getattr(obj, "OutList", []) or [])),
                "error": _status_string(obj),
            }
            for obj in emitted
        ]
        structured = {
            "nodes": nodes,
            "total_objects": total,
            "truncated": total > len(nodes),
        }
        return _ok_envelope(structured)

    return registry.with_document(doc, read)


def query_object(
    registry: DocumentRegistry, doc: str | None = None, object: str | None = None
) -> ResultEnvelope:
    """Report an object's name, label, type, public property values, and error state.

    ``properties`` is a JSON-safe dict of the object's public property values (non-JSON-safe
    values stringified). ``type`` is ``obj.TypeId``; ``error`` is ``getStatusString()`` or null.
    """

    def read(_handle: str, document: object) -> ResultEnvelope:
        obj = _resolve_object(document, object)
        properties = {
            prop: _read_property(obj, prop)
            for prop in list(getattr(obj, "PropertiesList", []) or [])
        }
        structured = {
            "name": obj.Name,
            "label": obj.Label,
            "type": obj.TypeId,
            "properties": properties,
            "error": _status_string(obj),
        }
        return _ok_envelope(structured)

    return registry.with_document(doc, read)


def query_mass_properties(
    registry: DocumentRegistry, doc: str | None = None, object: str | None = None
) -> ResultEnvelope:
    """Report volume, area, bounding box, centre of mass, and topology counts of an object's shape.

    Reads the currently-stored ``obj.Shape``. Dimensional fields carry explicit units
    (``mm``/``mm^2``/``mm^3``). An object with no ``Shape`` raises ``ValidationError``.
    """

    def read(_handle: str, document: object) -> ResultEnvelope:
        obj = _resolve_object(document, object)
        shape = getattr(obj, "Shape", None)
        is_null = getattr(shape, "isNull", None)
        if shape is None or (is_null is not None and is_null()):
            raise ValidationError(f"object has no queryable shape: {object}")
        bbox = shape.BoundBox
        com = shape.CenterOfMass
        structured = {
            "name": obj.Name,
            "volume": _quantity(shape.Volume, "mm^3"),
            "area": _quantity(shape.Area, "mm^2"),
            "bbox": {
                "xmin": _quantity(bbox.XMin, "mm"),
                "xmax": _quantity(bbox.XMax, "mm"),
                "ymin": _quantity(bbox.YMin, "mm"),
                "ymax": _quantity(bbox.YMax, "mm"),
                "zmin": _quantity(bbox.ZMin, "mm"),
                "zmax": _quantity(bbox.ZMax, "mm"),
            },
            "com": {
                "x": _quantity(com.x, "mm"),
                "y": _quantity(com.y, "mm"),
                "z": _quantity(com.z, "mm"),
            },
            "counts": {
                "faces": len(shape.Faces),
                "edges": len(shape.Edges),
                "solids": len(shape.Solids),
            },
        }
        return _ok_envelope(structured)

    return registry.with_document(doc, read)


def query_dependencies(
    registry: DocumentRegistry, doc: str | None = None, object: str | None = None
) -> ResultEnvelope:
    """Report dependency links by immutable ``Name``.

    With ``object`` → ``{object, in_list, out_list}`` from ``InList``/``OutList``. Without
    ``object`` → ``{edges:[{from,to}]}`` over every object's ``OutList``.
    """

    def read(_handle: str, document: object) -> ResultEnvelope:
        if object:
            obj = _resolve_object(document, object)
            structured = {
                "object": obj.Name,
                "in_list": [dep.Name for dep in getattr(obj, "InList", []) or []],
                "out_list": [dep.Name for dep in getattr(obj, "OutList", []) or []],
            }
            return _ok_envelope(structured)
        edges = [
            {"from": obj.Name, "to": dep.Name}
            for obj in document.Objects
            for dep in getattr(obj, "OutList", []) or []
        ]
        return _ok_envelope({"edges": edges})

    return registry.with_document(doc, read)


def query_sketch_info(
    registry: DocumentRegistry, doc: str | None = None, sketch: str | None = None
) -> ResultEnvelope:
    """List a Sketcher sketch's geometry and constraints.

    ``geometry`` entries carry ``index``, ``type``, and ``construction``. ``constraints`` entries
    carry a 1-based ``id``, ``type``, ``name``, an optional ``value`` (with unit for dimensional
    constraints), and ``driving``. A non-sketch object raises ``ValidationError``.
    """

    def read(_handle: str, document: object) -> ResultEnvelope:
        obj = _resolve_object(document, sketch)
        if not str(getattr(obj, "TypeId", "")).startswith("Sketcher::"):
            raise ValidationError(f"object is not a sketch: {sketch}")
        geometry = [
            {
                "index": index,
                "type": type(geo).__name__,
                "construction": bool(getattr(geo, "Construction", False)),
            }
            for index, geo in enumerate(obj.Geometry)
        ]
        constraints = []
        for index, constraint in enumerate(obj.Constraints):
            entry = {
                "id": index + 1,
                "type": constraint.Type,
                "name": constraint.Name,
            }
            if hasattr(constraint, "Driving"):
                entry["driving"] = bool(constraint.Driving)
            value = getattr(constraint, "Value", None)
            if value is not None:
                quantity = _constraint_quantity(constraint.Type, value)
                entry["value"] = quantity if quantity is not None else _quantity(value, None)
            constraints.append(entry)
        structured = {"sketch": obj.Name, "geometry": geometry, "constraints": constraints}
        return _ok_envelope(structured)

    return registry.with_document(doc, read)


def _placement_dict(placement: object) -> dict:
    """Render a FreeCAD ``Placement`` as position/axis/angle with explicit units."""
    base = placement.Base
    axis = placement.Rotation.Axis
    return {
        "position": {
            "x": _quantity(base.x, "mm"),
            "y": _quantity(base.y, "mm"),
            "z": _quantity(base.z, "mm"),
        },
        "axis": {"x": float(axis.x), "y": float(axis.y), "z": float(axis.z)},
        "angle": _quantity(math.degrees(placement.Rotation.Angle), "deg"),
    }


def query_placement(
    registry: DocumentRegistry, doc: str | None = None, object: str | None = None
) -> ResultEnvelope:
    """Report an object's local and global placement (position, axis, angle in degrees).

    ``local`` is ``obj.Placement``; ``global`` is ``obj.getGlobalPlacement()`` when available,
    else the local placement.
    """

    def read(_handle: str, document: object) -> ResultEnvelope:
        obj = _resolve_object(document, object)
        local = getattr(obj, "Placement", None)
        if local is None:
            raise ValidationError(f"object has no placement: {object}")
        global_getter = getattr(obj, "getGlobalPlacement", None)
        try:
            global_placement = global_getter() if global_getter is not None else local
        except Exception:
            global_placement = local
        if global_placement is None:
            global_placement = local
        structured = {
            "object": obj.Name,
            "local": _placement_dict(local),
            "global": _placement_dict(global_placement),
        }
        return _ok_envelope(structured)

    return registry.with_document(doc, read)
