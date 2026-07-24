"""Read-only introspection use cases.

Exposes ``query_capabilities`` (runtime capability probes) and the six Phase-0 read-only
``query_*`` tools over an explicit ``doc`` handle: tree summary, object properties, mass
properties, dependency edges, sketch geometry/constraints, and placement. Every query resolves
its handle through the ``DocumentRegistry`` lock and never mutates: no recompute, no property
write, no viewport touch.
"""

from __future__ import annotations

import math
import re

from freecad_buddy.contracts import ResultEnvelope, summary_text
from freecad_buddy.usecases import shim
from freecad_buddy.usecases.documents import DocumentRegistry, ValidationError


def _ok_envelope(structured: dict, summary: str | None = None) -> ResultEnvelope:
    return {
        "schema": "fcb.result-envelope/1",
        "status": "OK",
        "detail": None,
        "structured_content": structured,
        "text": summary if summary is not None else summary_text(structured),
    }


def summarize_tree(sc: dict) -> str:
    """One-line tree summary: object counts + any errored nodes."""
    errors = _collect_errors(sc.get("tree", []))
    head = f"{sc.get('total_objects', '?')} objects, {sc.get('returned_nodes', '?')} shown"
    if errors:
        return f"{head}. Errors: " + "; ".join(errors)
    return head + "."


def _collect_errors(nodes: list) -> list:
    out = []
    for n in nodes:
        if "error" in n:
            out.append(f"{n['name']}: {n['error']}")
        out += _collect_errors(n.get("children", []))
        out += _collect_errors(n.get("links", []))
    return out


def summarize_mass_properties(sc: dict) -> str:
    """One-line mass-properties summary: volume headline + topology counts."""
    vol = sc.get("volume") or {}
    counts = sc.get("counts") or {}
    kind = "solid" if sc.get("solid") else "non-solid"
    v = vol.get("value") if isinstance(vol, dict) else None
    v_txt = f"{v} {vol.get('unit', '')}" if v is not None else "n/a"
    return (
        f"{sc.get('name', '?')}: volume {v_txt} ({kind}), "
        f"{counts.get('faces', '?')} faces, {counts.get('edges', '?')} edges."
    )


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


_DATUM_EXCLUDE_DEFAULT = ("App::Plane", "App::Line", "App::Point", "App::Origin")

# A shape-bearing leaf the offscreen renderer draws — mirrors the render skip-set: datum/origin
# features and the two container types (Body/Sketch has a Shape but is not a drawable leaf).
_RENDER_SKIP_PREFIXES = ("App::Origin", "App::Line", "App::Plane", "App::Point")
_RENDER_SKIP_TYPES = frozenset({"PartDesign::Body", "Sketcher::SketchObject"})


def _is_renderable(obj: object) -> bool:
    """Whether ``obj`` is a shape-bearing leaf the default render would draw (not datum/container)."""  # noqa: E501
    type_id = str(getattr(obj, "TypeId", ""))
    if type_id in _RENDER_SKIP_TYPES or type_id.startswith(_RENDER_SKIP_PREFIXES):
        return False
    shape = getattr(obj, "Shape", None)
    is_null = getattr(shape, "isNull", None)
    return shape is not None and not (is_null is not None and is_null())


def _node_passes(obj: object, filters: dict) -> bool:
    """Whether ``obj`` survives every provided filter (AND-stacked)."""
    type_id = str(getattr(obj, "TypeId", ""))
    types = filters.get("types")
    if types is not None and type_id not in types:
        return False
    exclude = filters.get("exclude_types")
    if exclude is not None and type_id in exclude:
        return False
    if filters.get("renderable_only") and not _is_renderable(obj):
        return False
    if filters.get("visible_only") and not bool(getattr(obj, "Visibility", False)):
        return False
    pattern = filters.get("name_pattern")
    if pattern is not None:
        haystack = f"{getattr(obj, 'Name', '')} {getattr(obj, 'Label', '')}"
        if not re.search(pattern, haystack):
            return False
    return True


def _sparse_node(
    obj: object,
    children: list,
    links: list,
    children_count: int,
    links_count: int,
) -> dict:
    """Assemble a tree node, omitting any field that carries no value.

    Always emits name/label/type/visibility. Emits ``error`` only for a genuine error status,
    ``children``/``links`` only when a non-empty expanded array is supplied, and
    ``children_count``/``links_count`` only when non-zero.
    """
    node = {
        "name": obj.Name,
        "label": obj.Label,
        "type": obj.TypeId,
        "visibility": bool(getattr(obj, "Visibility", False)),
    }
    error = _status_string(obj)
    if error is not None:
        node["error"] = error
    if children_count:
        node["children_count"] = children_count
    if links_count:
        node["links_count"] = links_count
    if children:
        node["children"] = children
    if links:
        node["links"] = links
    return node


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


_JSON_MAX_DEPTH = 8


def _json_safe(value: object, _depth: int = 0) -> object:
    """Return a JSON-safe view of a property value, stringifying anything unsupported.

    Recursion is bounded at ``_JSON_MAX_DEPTH`` so a deeply-nested or self-referential property
    value (a scripted ``PropertyPythonObject`` holding a cycle) is stringified at the depth cap
    rather than overflowing the stack.
    """
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if _depth >= _JSON_MAX_DEPTH:
        return str(value)
    if isinstance(value, (list, tuple)):
        return [_json_safe(item, _depth + 1) for item in value]
    if isinstance(value, dict):
        return {str(key): _json_safe(item, _depth + 1) for key, item in value.items()}
    return str(value)


def _read_property(obj: object, prop: str) -> object:
    """Return a JSON-safe view of ``obj.prop``, or ``None`` if reading it raises."""
    try:
        raw = getattr(obj, prop)
    except Exception:
        return None
    return _json_safe(raw)



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
    depth: int = 1,
    root: str | None = None,
    filters: dict | None = None,
) -> ResultEnvelope:
    """Summarize the feature tree as a nested, depth-bounded, filtered node tree.

    Expands ``depth`` levels from the document roots (or from ``root`` when given). Each object's
    children are partitioned into structural ``children`` and ``App::Link`` ``links``; at the depth
    boundary a node reports only its ``children_count``/``links_count``. ``filters`` AND-stacks
    ``types``/``exclude_types``/``renderable_only``/``visible_only``/``name_pattern``;
    ``exclude_types`` defaults to the datum/origin clutter set. Nodes are sparse — a field appears
    only when it carries a value; ``name``/``label``/``type``/``visibility`` are always present.
    """
    effective = dict(filters or {})
    effective.setdefault("exclude_types", list(_DATUM_EXCLUDE_DEFAULT))

    def read(_handle: str, document: object) -> ResultEnvelope:
        by_name = {obj.Name: obj for obj in document.Objects}
        if root is not None:
            root_obj = by_name.get(root)
            if root_obj is None:
                raise ValidationError(f"unknown object: {root}")
            roots = [root_obj]
        else:
            in_lists = {c.Name for o in document.Objects for c in _out_list(o)}
            roots = [o for o in document.Objects if o.Name not in in_lists]

        counter = {"n": 0}

        def build(obj: object, remaining: int) -> dict:
            out = _out_list(obj)
            child_objs = [c for c in out if not _is_link(c)]
            link_objs = [c for c in out if _is_link(c)]
            children, links = [], []
            if remaining > 1:
                children = [
                    build(c, remaining - 1) for c in child_objs if _node_passes(c, effective)
                ]
                links = [
                    build(c, remaining - 1) for c in link_objs if _node_passes(c, effective)
                ]
            counter["n"] += 1
            return _sparse_node(obj, children, links, len(child_objs), len(link_objs))

        tree = [build(o, depth) for o in roots if _node_passes(o, effective)]
        structured = {
            "doc": _handle,
            "total_objects": len(document.Objects),
            "returned_nodes": counter["n"],
            "depth": depth,
            "filters_applied": effective,
            "tree": tree,
        }
        return _ok_envelope(structured, summarize_tree(structured))

    return registry.with_document(doc, read)


def _out_list(obj: object) -> list:
    """The object's direct children (``OutList``), empty when absent."""
    return list(getattr(obj, "OutList", []) or [])


def _is_link(obj: object) -> bool:
    """Whether ``obj`` is an ``App::Link`` instance, grouped separately from structural children."""
    return str(getattr(obj, "TypeId", "")).startswith("App::Link")


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
    (``mm``/``mm^2``/``mm^3``). A ``solid`` flag records whether the shape encloses volume; for a
    non-solid (shell/wire/face/compound-of-open) ``volume`` and ``com`` are reported ``null`` so
    an area/length-based centroid is never presented as volumetric mass. An object with no
    ``Shape`` raises ``ValidationError``.
    """

    def read(_handle: str, document: object) -> ResultEnvelope:
        obj = _resolve_object(document, object)
        shape = getattr(obj, "Shape", None)
        is_null = getattr(shape, "isNull", None)
        if shape is None or (is_null is not None and is_null()):
            raise ValidationError(f"object has no queryable shape: {object}")
        bbox = shape.BoundBox
        is_solid = len(shape.Solids) > 0
        # CenterOfMass is meaningful only for a volumetric solid (and is unavailable on some shape
        # types, e.g. Part.Compound). Report null volume/com for a non-solid so an area/length
        # centroid is never presented as volumetric mass; bbox/area/counts stay valid.
        com = getattr(shape, "CenterOfMass", None) if is_solid else None
        structured = {
            "name": obj.Name,
            "solid": is_solid,
            "volume": _quantity(shape.Volume, "mm^3") if is_solid else None,
            "area": _quantity(shape.Area, "mm^2"),
            "bbox": {
                "xmin": _quantity(bbox.XMin, "mm"),
                "xmax": _quantity(bbox.XMax, "mm"),
                "ymin": _quantity(bbox.YMin, "mm"),
                "ymax": _quantity(bbox.YMax, "mm"),
                "zmin": _quantity(bbox.ZMin, "mm"),
                "zmax": _quantity(bbox.ZMax, "mm"),
            },
            "com": None
            if com is None
            else {
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
        return _ok_envelope(structured, summarize_mass_properties(structured))

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


def _construction_flag(sketch_obj: object, geo: object, index: int) -> bool:
    """Whether the sketch geometry at ``index`` is construction geometry.

    Prefers ``SketchObject.getConstruction(index)`` (authoritative on builds that migrate the
    flag off the raw geometry onto the ``GeometryFacade``); falls back to the raw geometry's
    ``Construction`` attribute when the method is unavailable.
    """
    getter = getattr(sketch_obj, "getConstruction", None)
    if callable(getter):
        try:
            return bool(getter(index))
        except Exception:  # noqa: BLE001 - fall back to the raw attribute if the call is unusable
            pass
    return bool(getattr(geo, "Construction", False))


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
                "construction": _construction_flag(obj, geo, index),
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
