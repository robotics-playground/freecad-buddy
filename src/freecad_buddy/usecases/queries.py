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
import time
from collections.abc import Callable
from typing import Literal

from freecad_buddy.contracts import CapabilityBanner, ResultEnvelope, summary_text
from freecad_buddy.usecases import shim
from freecad_buddy.usecases.documents import DocumentRegistry, ValidationError
from freecad_buddy.usecases.parameter_types import PARAMETER_PROPERTY_TYPES
from freecad_buddy.usecases.tree_text import (
    LINE_CAP,
    TreeNode,
    cap_lines,
    path_line,
    tree_lines,
    type_code,
)


def _ok_envelope(structured: dict, summary: str | None = None) -> ResultEnvelope:
    return {
        "schema": "fcb.result-envelope/1",
        "status": "OK",
        "detail": None,
        "structured_content": structured,
        "text": summary if summary is not None else summary_text(structured),
    }


def summarize_tree(sc: dict, errors: list[str] | None = None) -> str:
    """One-line tree summary: object count, lines shown, filter matches, a cut by the cap, and
    every error.

    ``errors`` holds ``"<Name>: <status>"`` for each errored object in the start subtree, so an
    error below a collapsed line still reaches the agent.
    """
    head = f"{sc.get('total_objects', '?')} objects, {sc.get('shown', '?')} shown"
    if "matches" in sc:
        head += f", {sc['matches']} matches"
    if sc.get("truncated"):
        head += ", truncated"
    if errors:
        return f"{head}. Errors: " + "; ".join(errors)
    return head + "."


def summarize_sketch_info(sc: dict) -> str:
    """One-line sketch summary: geometry count and constraint count."""
    geo = sc.get("geometry") or []
    con = sc.get("constraints") or []
    return f"{sc.get('sketch', '?')}: {len(geo)} geo, {len(con)} constraint(s)."


def summarize_placement(sc: dict) -> str:
    """One-line placement summary: object name and local position."""
    local = sc.get("local") or {}
    pos = local.get("position") or {}
    x = shim.displayed((pos.get("x") or {}).get("value", "?"))
    y = shim.displayed((pos.get("y") or {}).get("value", "?"))
    z = shim.displayed((pos.get("z") or {}).get("value", "?"))
    angle = shim.displayed((local.get("angle") or {}).get("value", "?"))
    return f"{sc.get('object', '?')} at ({x}, {y}, {z}) mm, rotated {angle} deg."


def summarize_dependencies(sc: dict) -> str:
    """One-line dependency summary: edge count or per-object in/out counts.

    The whole-doc branch appends a truncation note when ``truncated`` is set.
    """
    if "edges" in sc:
        returned = sc.get("returned_edges", len(sc["edges"]))
        if sc.get("truncated"):
            return f"{returned} dependency edge(s) (truncated from {sc.get('total_edges', '?')})."
        return f"{returned} dependency edge(s)."
    in_list = sc.get("in_list") or []
    out_list = sc.get("out_list") or []
    return f"{sc.get('object', '?')}: {len(in_list)} upstream, {len(out_list)} downstream."


def summarize_mass_properties(sc: dict) -> str:
    """One-line mass-properties summary: volume headline + topology counts."""
    if "shape" in sc:
        return f"{sc.get('name', '?')}: no shape."
    vol = sc.get("volume") or {}
    counts = sc.get("counts") or {}
    kind = "solid" if sc.get("solid") else "non-solid"
    v = shim.displayed(vol.get("value")) if isinstance(vol, dict) else None
    v_txt = f"{v} {vol.get('unit', '')}" if v is not None else "n/a"
    return (
        f"{sc.get('name', '?')}: volume {v_txt} ({kind}), "
        f"{counts.get('faces', '?')} faces, {counts.get('edges', '?')} edges"
        f"{'' if sc.get('is_valid', True) else ', INVALID shape'}."
    )


def query_capabilities(
    exec_enabled: bool = False,
    render: Literal["gui_constructed", "offscreen", "none"] = "none",
) -> ResultEnvelope:
    """Report runtime capabilities: FreeCAD version, element-map, serializer, VarSet, render, exec.

    Every field is a live probe. ``render`` is the host-probed render-ladder mode and
    ``exec_enabled`` reflects whether the exec tool is reachable.
    """
    structured: CapabilityBanner = {**shim.capability_banner(render), "exec_enabled": exec_enabled}
    return _ok_envelope(structured)


def _quantity(value: float, unit: str) -> dict:
    """Wrap a dimensional value as a ``{value, unit}`` Quantity.

    A non-finite value (``nan``/``inf`` from a degenerate shape) is reported as ``None`` so the
    envelope stays valid JSON.
    """
    number = float(value)
    return {"value": number if math.isfinite(number) else None, "unit": unit}


def shape_metrics(shape: object) -> dict:
    """Read a shape's volume, area, bbox, centre and topology counts as plain summable floats.

    Values are in internal units (mm) with no ``Quantity`` wrapping, so a caller can sum them
    across objects. ``volume`` is ``0.0`` for a shape enclosing no volume and ``com`` falls back
    to the bounding-box centre when ``CenterOfMass`` is unreadable.

    :param shape: a non-null ``Part.Shape``.
    :returns: ``{solid, com_readable, volume, area, bbox, com, counts}`` where ``solid`` records
        whether the shape encloses volume, ``com_readable`` whether ``CenterOfMass`` could be
        read, ``bbox`` is ``[xmin, ymin, zmin, xmax, ymax, zmax]``, ``com`` an ``[x, y, z]``
        triple, and ``counts`` holds ``faces``/``edges``/``vertices``/``solids``.
    """
    bbox = shape.BoundBox
    center = getattr(shape, "CenterOfMass", None)
    com_readable = center is not None
    if com_readable:
        com = [float(center.x), float(center.y), float(center.z)]
    else:
        com = [
            float(bbox.XMin + bbox.XMax) / 2,
            float(bbox.YMin + bbox.YMax) / 2,
            float(bbox.ZMin + bbox.ZMax) / 2,
        ]
    return {
        "solid": len(shape.Solids) > 0,
        "com_readable": com_readable,
        "volume": float(shape.Volume),
        "area": float(shape.Area),
        "bbox": [
            float(bbox.XMin),
            float(bbox.YMin),
            float(bbox.ZMin),
            float(bbox.XMax),
            float(bbox.YMax),
            float(bbox.ZMax),
        ],
        "com": com,
        "counts": {
            "faces": len(shape.Faces),
            "edges": len(shape.Edges),
            "vertices": len(shape.Vertexes),
            "solids": len(shape.Solids),
        },
    }


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


_JSON_MAX_DEPTH = 8


def _json_safe(value: object, _depth: int = 0) -> object:
    """Return a JSON-safe view of a property value, stringifying anything unsupported.

    A ``Quantity`` or ``Vector`` is stringified with its numbers at the display precision.

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
    kind = type(value).__name__
    if kind == "Quantity":
        # ``str`` of a Quantity is the full-length float, then a space and the unit text.
        unit = str(value).partition(" ")[2]
        number = shim.displayed(float(value.Value))
        return f"{number} {unit}" if unit else str(number)
    if kind == "Vector":
        x, y, z = shim.displayed([value.x, value.y, value.z])
        return f"Vector ({x}, {y}, {z})"
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
    focus: str | None = None,
    expand: list[str] | None = None,
    depth: int = 1,
    filters: dict | None = None,
) -> ResultEnvelope:
    """Render the document tree as plain text in the shape of FreeCAD's Model panel.

    Children are containment, not dependencies (see :func:`_containment_children`). The start is
    ``focus`` or the top level; ``depth`` levels open below it. ``expand`` opens each named node
    one level and opens its ancestors only along the path. ``filters.name_pattern``/
    ``filters.types`` select matches inside the start subtree and open only their paths, in place
    of ``depth``.

    The tree text travels in ``text_blocks``; ``structured_content`` holds only the counts, and
    ``text`` names every errored object in the start subtree, shown or not. Raises
    ``ValidationError`` for an unknown ``focus``/``expand`` name, an ``expand`` name outside the
    ``focus`` subtree, a ``depth`` below ``1``, or a ``name_pattern`` that is not a regular
    expression.
    """
    if not isinstance(depth, int) or isinstance(depth, bool) or depth < 1:
        raise ValidationError(f"depth must be an integer >= 1: {depth!r}")
    reveal = filters or {}
    pattern = _compile_name_pattern(reveal.get("name_pattern"))
    types = reveal.get("types")
    revealing = pattern is not None or types is not None
    expanded = list(expand or [])

    def read(handle: str, document: object) -> ResultEnvelope:
        objects = list(document.Objects)
        names = {obj.Name for obj in objects}
        for name in ([focus] if focus is not None else []) + expanded:
            if name not in names:
                raise ValidationError(f"unknown object: {name}")

        children = {obj.Name: _containment_children(obj) for obj in objects}
        parent: dict[str, str] = {}
        for obj in objects:
            for child in children[obj.Name]:
                parent.setdefault(child.Name, obj.Name)

        def chain(name: str) -> list[str]:
            """Names from the top level down to ``name``; a containment cycle ends the walk."""
            upward = [name]
            while upward[-1] in parent and parent[upward[-1]] not in upward:
                upward.append(parent[upward[-1]])
            return upward[::-1]

        def below_start(name: str) -> list[str] | None:
            """The chain from the start down to ``name``; ``None`` outside the start subtree."""
            full = chain(name)
            if focus is None:
                return full
            return full[full.index(focus) :] if focus in full else None

        for name in expanded:
            if below_start(name) is None:
                raise ValidationError(f"{name} is outside focus {focus}")
        in_start = [obj for obj in objects if below_start(obj.Name) is not None]
        matched = [obj.Name for obj in in_start if revealing and _reveals(obj, pattern, types)]
        errors = [
            f"{obj.Name}: {' '.join(status.split())}"
            for obj in in_start
            if (status := _status_string(obj)) is not None
        ]
        on_path: set[str] = set()
        marked: set[str] = set()
        for target in expanded + matched:
            path = below_start(target)
            on_path.update(path[:-1])
            marked.update(path)
        open_names = set(expanded)
        tips = {
            obj.Tip.Name
            for obj in objects
            if obj.isDerivedFrom("PartDesign::Body") and getattr(obj, "Tip", None) is not None
        }

        def build(obj: object, remaining: int, ancestors: frozenset[str]) -> TreeNode:
            kids = [kid for kid in children.get(obj.Name, []) if kid.Name not in ancestors]
            inner = ancestors | {obj.Name}
            if remaining >= 1 or obj.Name in open_names:
                shown = [build(kid, remaining - 1, inner) for kid in kids]
            elif obj.Name in on_path:
                shown = [build(kid, 0, inner) for kid in kids if kid.Name in marked]
            else:
                shown = []
            return TreeNode(
                name=obj.Name,
                label=obj.Label,
                type_id=obj.TypeId,
                visible=bool(getattr(obj, "Visibility", False)),
                tip=obj.Name in tips,
                status=_status_string(obj),
                link_target=_link_target(obj),
                children=shown,
                not_shown=len(kids) - len(shown),
            )

        budget = 0 if revealing else depth
        if focus is None:
            roots = [
                build(obj, budget - 1, frozenset()) for obj in objects if obj.Name not in parent
            ]
            head: list[str] = []
        else:
            roots = [build(document.getObject(focus), budget, frozenset())]
            head = [path_line(chain(focus))]
        lines = tree_lines(roots)
        capped, truncated = cap_lines(lines)
        structured = {
            "doc": handle,
            "total_objects": len(objects),
            "shown": min(len(lines), LINE_CAP),
            "truncated": truncated,
        }
        if revealing:
            structured["matches"] = len(matched)
        envelope = _ok_envelope(structured, summarize_tree(structured, errors))
        envelope["text_blocks"] = ["\n".join(head + capped)]
        return envelope

    return registry.with_document(doc, read)


def _compile_name_pattern(pattern: str | None) -> re.Pattern | None:
    if pattern is None:
        return None
    try:
        return re.compile(pattern)
    except re.error as exc:
        raise ValidationError(f"invalid name_pattern {pattern!r}: {exc}") from exc


def _reveals(obj: object, pattern: re.Pattern | None, types: list[str] | None) -> bool:
    """Whether ``obj`` passes every given reveal filter.

    ``types`` takes tree codes in any case (``PAD``, ``pad``) or exact ``TypeId``s; ``pattern``
    searches ``"Name Label"``.
    """
    if types is not None and obj.TypeId not in types:
        if type_code(obj.TypeId) not in {entry.upper() for entry in types}:
            return False
    return pattern is None or pattern.search(f"{obj.Name} {obj.Label}") is not None


def _linked_objects(value: object) -> list:
    """The objects a link property holds, for ``PropertyLink`` through ``PropertyLinkSubList``.

    A sub-link reads as ``(object, subnames)`` and a sub-link list repeats one object per
    subname, so each entry is unwrapped and repeats are dropped.
    """
    entries = value if isinstance(value, list) else [value]
    targets = [entry[0] if isinstance(entry, tuple) else entry for entry in entries]
    return _dedup_by_name(target for target in targets if target is not None)


_CLAIMED_PROPERTIES: tuple[tuple[str, tuple[str, ...], bool], ...] = (
    ("Part::Boolean", ("Base", "Tool"), False),
    ("Part::MultiFuse", ("Shapes",), False),
    ("Part::MultiCommon", ("Shapes",), False),
    ("PartDesign::Loft", ("Profile", "Sections"), True),
    ("PartDesign::Pipe", ("Profile", "Sections", "Spine", "AuxiliarySpine"), True),
    ("PartDesign::MultiTransform", ("Transformations",), False),
)


def _claimed_children(obj: object) -> list:
    """The objects a feature's view provider claims as tree children.

    Each ``_CLAIMED_PROPERTIES`` row copies a ``claimChildren`` in
    ``docs/references/FreeCAD/src``; the flag keeps only ``Part::Part2DObject`` targets, as the
    source does:

    - ``Part::Boolean``: ``Mod/Part/Gui/ViewProviderBoolean.cpp:109-116``.
    - ``Part::MultiFuse``/``Part::MultiCommon``: ``ViewProviderBoolean.cpp:260-263,404-407``.
    - ``PartDesign::Loft``: ``Mod/PartDesign/Gui/ViewProviderLoft.cpp:43-61``.
    - ``PartDesign::Pipe``: ``Mod/PartDesign/Gui/ViewProviderPipe.cpp:43-71``.
    - ``PartDesign::MultiTransform``: ``Mod/PartDesign/Gui/ViewProviderMultiTransform.cpp:51-60``.
    - any other feature with a ``Profile`` sketch:
      ``Mod/PartDesign/Gui/ViewProviderSketchBased.cpp:75-84``, narrowed to sketches.
    """
    for type_id, properties, only_2d in _CLAIMED_PROPERTIES:
        if obj.isDerivedFrom(type_id):
            targets = _dedup_by_name(
                target
                for prop in properties
                for target in _linked_objects(getattr(obj, prop, None))
            )
            if only_2d:
                return [target for target in targets if target.isDerivedFrom("Part::Part2DObject")]
            return targets
    profile = _profile_sketch(obj)
    return [profile] if profile is not None else []


def _profile_sketch(obj: object) -> object | None:
    """The sketch a sketch-based feature claims as its ``Profile``, else ``None``."""
    if "Profile" not in getattr(obj, "PropertiesList", ()):
        return None
    value = obj.Profile
    target = value[0] if isinstance(value, tuple) else value
    if str(getattr(target, "TypeId", "")).startswith("Sketcher::SketchObject"):
        return target
    return None


def _containment_children(obj: object) -> list:
    """The children FreeCAD's Model panel shows under ``obj``, in panel order.

    Every origin group puts its ``Origin`` first, as ``ViewProviderOriginGroupExtension`` does;
    without that an ``App::Part``'s origin would be listed as a top-level object. A geometry group
    (Body, Part) leaves out each member that another member claims, as
    ``Gui/ViewProviderGeoFeatureGroupExtension.cpp:78-108`` does. An ``App::LinkGroup`` lists its
    ``ElementList``; an ``App::Link`` lists nothing.
    """
    if _is_link(obj):
        return []
    if obj.TypeId.startswith("App::LinkGroup"):
        return _linked_objects(list(obj.ElementList))
    if obj.isDerivedFrom("App::Origin"):
        return list(obj.OriginFeatures)
    claimed = _claimed_children(obj)
    if claimed:
        return claimed
    group = list(obj.Group) if obj.hasExtension("App::GroupExtension") else []
    if obj.hasExtension("App::GeoFeatureGroupExtension"):
        taken = {
            child.Name
            for member in group
            if not member.hasExtension("App::GeoFeatureGroupExtension")
            for child in _claimed_children(member)
        }
        group = [member for member in group if member.Name not in taken]
    origin = obj.Origin if obj.hasExtension("App::OriginGroupExtension") else None
    return ([origin] if origin is not None else []) + group


def _link_target(obj: object) -> str | None:
    """The ``Name`` an ``App::Link`` points at, else ``None``."""
    if not _is_link(obj):
        return None
    target = getattr(obj, "LinkedObject", None)
    if isinstance(target, tuple):
        target = target[0]
    return getattr(target, "Name", None)


def _dedup_by_name(objects) -> list:
    """Drop repeated objects, keeping first-seen order.

    ``getOutList`` walks every link property and appends each target it finds, so an object
    reachable through two properties (a Pad's ``Profile`` and its Body ``Group`` membership)
    is returned twice. The duplicates are an artefact of the traversal, not distinct children.
    """
    seen: set[str] = set()
    unique = []
    for obj in objects:
        name = getattr(obj, "Name", None)
        if name in seen:
            continue
        if name is not None:
            seen.add(name)
        unique.append(obj)
    return unique


def _out_list(obj: object) -> list:
    """The object's distinct direct children (``OutList``), empty when absent."""
    return _dedup_by_name(getattr(obj, "OutList", []) or [])


_LEAF_LINK_TYPES = frozenset({"App::Link", "App::LinkPython"})


def _is_link(obj: object) -> bool:
    """Whether ``obj`` is an ``App::Link``, which the tree shows without children.

    ``App::LinkGroup`` and ``App::LinkElement`` are not: a link group lists its elements.
    """
    return str(getattr(obj, "TypeId", "")) in _LEAF_LINK_TYPES


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


_MAX_MASS_OBJECTS = 50


def _queryable_shape(obj: object) -> object | None:
    """The object's shape, or ``None`` when it has no shape or a null one."""
    shape = getattr(obj, "Shape", None)
    is_null = getattr(shape, "isNull", None)
    if shape is None or (is_null is not None and is_null()):
        return None
    return shape


def _bbox_record(
    xmin: float, ymin: float, zmin: float, xmax: float, ymax: float, zmax: float
) -> dict:
    """A bounding box as six mm Quantities, the record ``query_mass_properties`` returns."""
    return {
        "xmin": _quantity(xmin, "mm"),
        "xmax": _quantity(xmax, "mm"),
        "ymin": _quantity(ymin, "mm"),
        "ymax": _quantity(ymax, "mm"),
        "zmin": _quantity(zmin, "mm"),
        "zmax": _quantity(zmax, "mm"),
    }


def _mass_record(obj: object, shape: object) -> dict:
    """One object's mass-properties record; ``volume`` and ``com`` are null for a non-solid."""
    metrics = shape_metrics(shape)
    is_solid = metrics["solid"]
    # CenterOfMass is meaningful only for a volumetric solid (and is unavailable on some shape
    # types, e.g. Part.Compound). Report null volume/com for a non-solid so an area/length
    # centroid is never presented as volumetric mass; bbox/area/counts stay valid. The com
    # branch keys on whether CenterOfMass was readable, not on `solid`: a compound of solids
    # is a solid that has none, and the bbox-centre fallback must not be published as one.
    com = metrics["com"] if (is_solid and metrics["com_readable"]) else None
    return {
        "name": obj.Name,
        "solid": is_solid,
        "volume": _quantity(metrics["volume"], "mm^3") if is_solid else None,
        "area": _quantity(metrics["area"], "mm^2"),
        "bbox": _bbox_record(*metrics["bbox"]),
        "com": None
        if com is None
        else {
            "x": _quantity(com[0], "mm"),
            "y": _quantity(com[1], "mm"),
            "z": _quantity(com[2], "mm"),
        },
        "counts": dict(metrics["counts"]),
        "is_valid": bool(shape.isValid()),
    }


def _mass_object_names(object: str | None, objects: list[str] | None) -> list[str]:
    """The names to measure, or raise ``ValidationError`` unless exactly one input form is given."""
    if (object is None) == (objects is None):
        raise ValidationError("give exactly one of 'object' and 'objects'")
    if objects is None:
        return [object]
    if not isinstance(objects, list) or not 1 <= len(objects) <= _MAX_MASS_OBJECTS:
        raise ValidationError(f"objects must be a list of 1 to {_MAX_MASS_OBJECTS} names")
    if not all(isinstance(name, str) and name for name in objects):
        raise ValidationError("objects must contain only non-empty object names (strings)")
    return objects


def query_mass_properties(
    registry: DocumentRegistry,
    doc: str | None = None,
    object: str | None = None,
    objects: list[str] | None = None,
) -> ResultEnvelope:
    """Report volume, area, bounding box, centre of mass, and topology counts of object shapes.

    Reads the currently-stored ``obj.Shape``. Dimensional fields carry explicit units
    (``mm``/``mm^2``/``mm^3``). A ``solid`` flag records whether the shape encloses volume; for a
    non-solid (shell/wire/face/compound-of-open) ``volume`` and ``com`` are reported ``null`` so
    an area/length-based centroid is never presented as volumetric mass. ``is_valid`` is the
    shape's ``isValid()``.

    With ``object`` the result is one record, and an object with no ``Shape`` raises
    ``ValidationError``. With ``objects`` (1 to 50 names) the result is ``{"objects": [...]}``
    in input order, and an object with no shape gives ``{"name", "shape": null}``. Exactly one of
    the two is required.
    """
    names = _mass_object_names(object, objects)

    def read(_handle: str, document: object) -> ResultEnvelope:
        resolved = [_resolve_object(document, name) for name in names]
        shapes = [_queryable_shape(obj) for obj in resolved]
        if objects is None:
            if shapes[0] is None:
                raise ValidationError(f"object has no queryable shape: {object}")
            record = _mass_record(resolved[0], shapes[0])
            return _ok_envelope(record, summarize_mass_properties(record))
        # An empty compound is not null but has an inverted +-1.797e308 bounding box; in a list it
        # reads as no shape. The single-object path keeps its existing response.
        records = [
            {"name": obj.Name, "shape": None}
            if shape is None or not shape.BoundBox.isValid()
            else _mass_record(obj, shape)
            for obj, shape in zip(resolved, shapes)
        ]
        text = "\n".join(summarize_mass_properties(record) for record in records)
        return _ok_envelope({"objects": records}, text)

    return registry.with_document(doc, read)


_MAX_INTERFERENCE_OBJECTS = 20
_MAX_INTERFERENCE_PAIRS = 100
# OCC's own tolerance for "touching" (Precision::Confusion). A distance at or below it is contact.
_CONTACT_DISTANCE_MM = 1e-7
# Largest faces(a) x faces(b) accepted for one pair. Measured on the development host with two
# interleaved box compounds one millimetre apart (the slowest geometry found, ``distToShape`` runs
# because ``common`` finds no volume): 129,600 -> 9.5 s, 230,400 -> 17.8 s, 360,000 -> 29.4 s.
# 150,000 keeps one pair near 10 s against the 60 s query budget. Above it ``distToShape`` holds
# the interpreter lock and the marshal timeout cannot fire (two 900-box compounds hung the worker
# for minutes in the container). Realistic parts sit far below it: a plate with 81 holes has 87
# faces.
_MAX_PAIR_FACE_PRODUCT = 150_000
# A call stops between pairs once this much time has passed. Worst case is this deadline plus one
# pair at the per-pair limit (about 12 s on the development host: 129,600 -> 9.5 s, 230,400 ->
# 17.8 s in the dense layout, and the limit is 150,000), which stays under the 60 s query budget.
# Face counts are a poor cost proxy across layouts (87-face plates cost about 12 microseconds per
# unit, dense boxes about 80), so the sum of a call is bounded by time, not by faces.
_CALL_DEADLINE_SECONDS = 40.0


def summarize_interference(sc: dict) -> str:
    """Count line, then one line per pair whose boolean failed or whose shapes overlap."""
    pairs = sc.get("pairs") or []
    failed = [pair for pair in pairs if pair.get("boolean_failed")]
    # A volume the result rounds to zero is not counted, so the text agrees with the numbers.
    overlapping = [
        pair
        for pair in pairs
        if pair.get("common_volume") and shim.displayed(pair["common_volume"]["value"])
    ]
    head = f"{len(pairs)} pair(s), {len(overlapping)} overlapping, {len(failed)} boolean failed."
    lines = [head]
    for pair in failed:
        lines.append(f"{pair['a']}/{pair['b']}: BOOLEAN FAILED, overlap unknown.")
    for pair in overlapping:
        volume = shim.displayed(pair["common_volume"]["value"])
        lines.append(f"{pair['a']}/{pair['b']}: common volume {volume} mm^3.")
    return "\n".join(lines)


def _interference_pairs(objects: list[str] | None, pairs: list[list[str]] | None):
    """The name pairs to measure, or raise ``ValidationError`` unless exactly one form is given."""
    if (objects is None) == (pairs is None):
        raise ValidationError("give exactly one of 'objects' and 'pairs'")
    if objects is not None:
        if not isinstance(objects, list) or not 2 <= len(objects) <= _MAX_INTERFERENCE_OBJECTS:
            raise ValidationError(
                f"objects must be a list of 2 to {_MAX_INTERFERENCE_OBJECTS} names"
            )
        if not all(isinstance(name, str) and name for name in objects):
            raise ValidationError("objects must contain only non-empty object names (strings)")
        if len(set(objects)) != len(objects):
            raise ValidationError("objects must not repeat a name")
        return [
            (objects[i], objects[j])
            for i in range(len(objects))
            for j in range(i + 1, len(objects))
        ]
    if not isinstance(pairs, list) or not 1 <= len(pairs) <= _MAX_INTERFERENCE_PAIRS:
        raise ValidationError(f"pairs must be a list of 1 to {_MAX_INTERFERENCE_PAIRS} pairs")
    for pair in pairs:
        valid = isinstance(pair, list) and len(pair) == 2
        if not (valid and all(isinstance(name, str) and name for name in pair)):
            raise ValidationError("each pair must be two non-empty object names (strings)")
        if pair[0] == pair[1]:
            raise ValidationError(f"a pair must name two different objects: {pair[0]}")
    return [(pair[0], pair[1]) for pair in pairs]


def _named_shape(document: object, name: str) -> object:
    """The named object's own shape, or raise ``ValidationError`` when it has none.

    A skipped object would read as "no overlap" and an empty shape as "no section", so a missing,
    null or empty shape is refused.
    """
    obj = _resolve_object(document, name)
    shape = _queryable_shape(obj)
    if shape is None or not shape.BoundBox.isValid():
        raise ValidationError(f"object has no queryable shape: {name}")
    return shape


def _copied_queryable_shape(document: object, name: str) -> object:
    """A copy of the named object's shape, for a call that runs booleans or a cut on it."""
    # ``Shape.common`` clears a BREP flag on its inputs, which would change a fresh fingerprint
    # digest of the document; the booleans and the distance run on a copy.
    return _named_shape(document, name).copy()


def _solid_volumes(shape: object):
    """Yield the signed volume of each solid in ``shape``, and ``None`` for any other content.

    A ``Compound`` or ``CompSolid`` is walked; a shell, face, wire or edge yields ``None``. A solid
    with reversed orientation reports a negative volume (``Part::Reverse``).
    """
    if shape.ShapeType == "Solid":
        yield float(shape.Volume)
    elif shape.ShapeType in ("Compound", "CompSolid"):
        for sub in shape.SubShapes:
            yield from _solid_volumes(sub)
    else:
        yield None


def _is_measurable_solid(shape: object) -> bool:
    """Whether the boolean and distance kernels can be trusted on ``shape``.

    True only for a valid shape made of solids that all have a positive volume. OCC reads a
    reversed solid as the material outside its faces, finds no inner distance solution for an
    invalid solid, and a shell encloses no volume, so each of those can turn a real overlap into
    an empty ``common`` with a positive distance.
    """
    try:
        volumes = list(_solid_volumes(shape))
        return (
            bool(volumes)
            and all(
                volume is not None and volume > 0 and math.isfinite(volume) for volume in volumes
            )
            and bool(shape.isValid())
        )
    except Exception:  # noqa: BLE001 -- a shape the kernel cannot even inspect is not measurable
        return False


def _measure_interference(
    shape_a: object, shape_b: object
) -> tuple[float | None, float | None, bool]:
    """``(common_volume, min_distance, boolean_failed)`` for one shape pair, in mm^3 and mm.

    The caller has checked both shapes with ``_is_measurable_solid``. ``common`` runs first because
    it is cheap, and a non-zero common volume proves a distance of 0. ``distToShape`` is the slow
    call on large compounds, so it runs only when ``common`` gives no volume. A ``common`` that
    raises or returns an empty compound is not proof of no overlap (a self-intersecting solid
    returns empty at distance 0), so it is a failed boolean unless the distance is positive.
    ``None`` means unmeasured.
    """
    try:
        common = shape_a.common(shape_b)
    except Exception:  # noqa: BLE001 -- Part.OCCError is the only expected type; any raise = failed
        common = None
    empty = common is None or common.isNull() or not common.BoundBox.isValid()
    volume = None if empty else float(common.Volume)
    if volume is not None and (volume < 0 or not math.isfinite(volume)):
        return None, None, True
    if volume:
        return volume, 0.0, False
    try:
        distance = float(shape_a.distToShape(shape_b)[0])
    except Exception:  # noqa: BLE001 -- a failed distance leaves the overlap unproven
        distance = None
    if distance is not None and not math.isfinite(distance):
        distance = None
    if distance is not None and distance > _CONTACT_DISTANCE_MM:
        return 0.0, distance, False
    if not empty and distance is not None:
        return 0.0, distance, False
    return None, distance, True


def _refusal_envelope(code: str, message: str) -> ResultEnvelope:
    """An ``INVALID_INPUT`` result whose ``detail.code`` names the refusal (AD-17)."""
    return {
        "schema": "fcb.result-envelope/1",
        "status": "INVALID_INPUT",
        "detail": {"code": code, "message": message},
        "structured_content": {},
        "text": message,
    }


def _too_complex_envelope(message: str) -> ResultEnvelope:
    """The refusal for a call whose boolean and distance cost would pass the query budget."""
    return _refusal_envelope("interference.too_complex", message)


def _pair_complexity_refusal(
    name_pairs: list[tuple[str, str]], face_counts: dict[str, int], measurable: dict[str, bool]
) -> ResultEnvelope | None:
    """A refusal naming the first measured pair whose face product is above the per-pair limit."""
    for name_a, name_b in name_pairs:
        if not (measurable[name_a] and measurable[name_b]):
            continue
        if face_counts[name_a] * face_counts[name_b] > _MAX_PAIR_FACE_PRODUCT:
            return _too_complex_envelope(
                f"pair {name_a}/{name_b} is too complex to measure: {face_counts[name_a]} and "
                f"{face_counts[name_b]} faces, limit {_MAX_PAIR_FACE_PRODUCT} for their product. "
                "Measure simpler shapes, or fewer faces per object."
            )
    return None


def query_interference(
    registry: DocumentRegistry,
    doc: str | None = None,
    objects: list[str] | None = None,
    pairs: list[list[str]] | None = None,
    clock: Callable[[], float] = time.monotonic,
) -> ResultEnvelope:
    """Measure common volume and minimum distance for object pairs.

    Give exactly one of ``objects`` (2 to 20 names, every pair measured in order ``(i, j)``,
    ``i < j``) or ``pairs`` (1 to 100 ``[a, b]`` pairs). Each record is ``{a, b, common_volume,
    min_distance, boolean_failed}``. ``boolean_failed`` is true, and ``common_volume`` null, when
    either shape is not a valid solid-only shape with positive volume (``min_distance`` is then
    null too), or when the boolean raised or returned nothing while the shapes touch or the
    distance is unknown: an empty result must never read as no overlap. Reports numbers only,
    never a verdict. Raises ``ValidationError`` for bad input, an unknown name, or an object with
    no shape, and returns ``INVALID_INPUT`` with code ``interference.too_complex`` for a pair above
    ``_MAX_PAIR_FACE_PRODUCT``, or for a call still measuring after ``_CALL_DEADLINE_SECONDS`` as
    read from ``clock``.
    """
    name_pairs = _interference_pairs(objects, pairs)

    def read(_handle: str, document: object) -> ResultEnvelope:
        names = {name for pair in name_pairs for name in pair}
        shapes = {name: _copied_queryable_shape(document, name) for name in sorted(names)}
        measurable = {name: _is_measurable_solid(shape) for name, shape in shapes.items()}
        # The trust check runs once per object, not per pair: 20 plates and 190 pairs took 10.7 s
        # with it per object and 69.7 s with it per pair.
        face_counts = {name: len(shape.Faces) for name, shape in shapes.items()}
        refusal = _pair_complexity_refusal(name_pairs, face_counts, measurable)
        if refusal is not None:
            return refusal
        records = []
        started = clock()
        for name_a, name_b in name_pairs:
            if clock() - started > _CALL_DEADLINE_SECONDS:
                return _too_complex_envelope(
                    f"stopped after {len(records)} of {len(name_pairs)} pairs; "
                    "measure fewer pairs per call"
                )
            if measurable[name_a] and measurable[name_b]:
                volume, distance, failed = _measure_interference(shapes[name_a], shapes[name_b])
            else:
                volume, distance, failed = None, None, True
            records.append(
                {
                    "a": name_a,
                    "b": name_b,
                    "common_volume": None if volume is None else _quantity(volume, "mm^3"),
                    "min_distance": None if distance is None else _quantity(distance, "mm"),
                    "boolean_failed": failed,
                }
            )
        structured = {"pairs": records}
        return _ok_envelope(structured, summarize_interference(structured))

    return registry.with_document(doc, read)


# Largest face count cut in one call. ``Shape.isValid``, ``Shape.section`` and ``Shape.common`` hold
# the interpreter lock, so the 60 s marshal timeout cannot stop them, and on one solid they grow
# with the square of the face count. Whole tool call on the development host, plane through a
# regular prism or a plate with hexagonal holes: 1,002 faces -> 1.0 s, 2,002 -> 3.1 s, 3,002 ->
# 6.1 s (prism); 1,806 -> 3.0 s, 3,006 -> 7.1 s, 4,206 -> 13 s (plate); 5,000-face prism 27 s,
# 8,406-face plate 42.6 s, 9,992-face prism 95.7 s (red team). 3,000 keeps one call near 7 s.
_MAX_SECTION_FACES = 3000
# Largest sum, over the BSpline and Bezier faces of a shape, of the square of the face's pole count
# (``NbUPoles * NbVPoles``). ``Shape.section`` on a swept BSpline face grows with the square of its
# poles, with only 3 faces: a coil spring of 3 turns (246 poles) -> 0.8 s, 5 turns (414) -> 1.9 s,
# 10 turns (822) -> 7.8 s, 30 turns (about 2,400) -> 112 s, 60 turns -> 210 s (red team). Many
# small patches cost little: 1,000 NURBS cylinders (3,000 faces, 20,000 poles in all, load 135,000)
# -> 11.8 s. 800 poles in one face (load 640,000) keep one call near 8 s. Surfaces of extrusion
# or revolution over a BSpline curve are not counted (not measured).
_MAX_BSPLINE_POLE_LOAD = 800**2
# Largest wire count for which the area is measured. The area needs ``Shape.common`` and a face
# built from the wires with ``FaceMakerBullseye``, and both grow with the square of the wire
# count. ``common``: separate boxes 1,600 wires -> 4.7 s, 3,200 -> 16 s; a plate with 3,000 holes
# -> 21 s and with 9,000 holes -> 103 s. ``FaceMakerBullseye``: separate cylinders 100 wires ->
# 0.11 s, 300 -> 0.91 s, 600 -> 7.9 s; a plate with 600 holes -> 2.4 s. 300 wires keep both near
# 2 s. Above it the area is null, never 0.
_MAX_AREA_WIRES = 300
# A plane within this distance of a planar face of the shape (``Precision::Confusion``), or within
# the face's own tolerance when that is larger, lies on the face: ``Shape.section`` then returns the
# inner edges of the face as well (a box with tolerance 1e-5 cut 1e-6 mm from a face gave an open
# wire of 82.4 mm against a perimeter of 60 mm).
_COINCIDENT_TOLERANCE_MM = 1e-7
_BSPLINE_SURFACE_TYPES = ("Part::GeomBSplineSurface", "Part::GeomBezierSurface")
# The area from ``Shape.common`` and the area bounded by the section wires must agree this closely.
# On a section whose edges are approximated curves the two differ slightly (a NURBS cylinder of
# radius 10: 314.157 against 313.931, 7e-4 relative); with a plane that confuses the kernel they
# differ widely (a void floor: 400 against 300).
_AREA_AGREEMENT_REL_TOL = 5e-3
_MAX_POLYLINE_POINTS = 5000
_MIN_POLYLINE_POINTS = 2
_DEFAULT_POLYLINE_POINTS = 1000
# ``Wire.discretize(Deflection=0)`` never returns, and a tiny deflection makes one wire cost
# millions of points; a deflection under this share of the bounding-box diagonal is refused.
_MIN_DEFLECTION_RATIO = 1e-6
_AXIS_NORMALS = {"x": (1.0, 0.0, 0.0), "y": (0.0, 1.0, 0.0), "z": (0.0, 0.0, 1.0)}


def _is_finite_number(value: object) -> bool:
    """Whether ``value`` is a finite int or float (a JSON integer beyond float range is not)."""
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        return False
    try:
        return math.isfinite(value)
    except OverflowError:
        return False


def _mm_quantity(value: object, what: str) -> float:
    """The magnitude of a finite ``{value, unit: "mm"}`` quantity, or raise ``ValidationError``."""
    if not isinstance(value, dict) or set(value) != {"value", "unit"}:
        raise ValidationError(f"{what} must be a {{value, unit}} quantity, got {value!r}")
    magnitude = value["value"]
    if not _is_finite_number(magnitude):
        raise ValidationError(f"{what} value must be a finite number, got {magnitude!r}")
    if value["unit"] != "mm":
        raise ValidationError(f"{what} unit must be 'mm', got {value['unit']!r}")
    return float(magnitude)


def _section_plane(plane: object) -> tuple[tuple[float, float, float], float]:
    """``(unit normal, offset in mm)`` of the cut plane ``normal . p = offset``."""
    if not isinstance(plane, dict) or set(plane) != {"normal", "offset"}:
        raise ValidationError("plane must be an object with 'normal' and 'offset'")
    offset = _mm_quantity(plane["offset"], "plane.offset")
    raw = plane["normal"]
    if isinstance(raw, str):
        if raw not in _AXIS_NORMALS:
            raise ValidationError(
                f"plane.normal must be 'x', 'y', 'z' or [nx, ny, nz], got {raw!r}"
            )
        return _AXIS_NORMALS[raw], offset
    is_vector = isinstance(raw, list) and len(raw) == 3
    if not is_vector or not all(_is_finite_number(item) for item in raw):
        raise ValidationError("plane.normal must be 'x', 'y', 'z' or three finite numbers")
    # Scaled by the largest component first: ``hypot`` of components near the float limit is inf
    # and of subnormal ones is rounded, and a zero vector reaching ``Part.Plane`` aborts the
    # process.
    scale = max(abs(item) for item in raw)
    if scale == 0:
        raise ValidationError("plane.normal must not be the zero vector")
    scaled = [item / scale for item in raw]
    length = math.hypot(*scaled)
    return (scaled[0] / length, scaled[1] / length, scaled[2] / length), offset


def _section_points(points: object) -> tuple[float, int]:
    """``(deflection in mm, max_points)`` of the polyline request."""
    if not isinstance(points, dict) or "deflection" not in points:
        raise ValidationError(
            "points must be an object with 'deflection' and optional 'max_points'"
        )
    if set(points) - {"deflection", "max_points"}:
        raise ValidationError("points accepts only 'deflection' and 'max_points'")
    deflection = _mm_quantity(points["deflection"], "points.deflection")
    if deflection <= 0.0:
        raise ValidationError(f"points.deflection must be positive, got {deflection}")
    limit = points.get("max_points", _DEFAULT_POLYLINE_POINTS)
    if not isinstance(limit, int) or isinstance(limit, bool):
        raise ValidationError(f"points.max_points must be an integer, got {limit!r}")
    if not _MIN_POLYLINE_POINTS <= limit <= _MAX_POLYLINE_POINTS:
        raise ValidationError(
            f"points.max_points must be {_MIN_POLYLINE_POINTS} to {_MAX_POLYLINE_POINTS}"
        )
    return deflection, limit


def _bspline_pole_load(shape: object) -> int:
    """The sum over BSpline and Bezier faces of the square of ``NbUPoles * NbVPoles``."""
    load = 0
    for face in shape.Faces:
        surface = face.Surface
        if hasattr(surface, "NbUPoles"):
            load += (surface.NbUPoles * surface.NbVPoles) ** 2
    return load


def _face_plane(face: object) -> object | None:
    """The plane a planar face lies in, or ``None`` for a curved face.

    A planar BSpline or Bezier face (a box after ``toNurbs()``) is found with ``findPlane``; the
    other curved surfaces are not tried because the search costs time on every face.
    """
    surface = face.Surface
    if surface.TypeId == "Part::GeomPlane":
        return surface
    if surface.TypeId in _BSPLINE_SURFACE_TYPES:
        return face.findPlane()
    return None


def _plane_on_face(shape: object, normal: tuple[float, float, float], offset: float) -> bool:
    """Whether the plane ``normal . p = offset`` coincides with a planar face of ``shape``.

    A face coincides when its normal is parallel to ``normal`` closely enough that the two planes
    stay within the tolerance across the face, and one of its vertices is on the plane. The
    tolerance is ``_COINCIDENT_TOLERANCE_MM`` or the face's own tolerance, whichever is larger.
    """
    for face in shape.Faces:
        plane = _face_plane(face)
        if plane is None or not face.Vertexes:
            continue
        tolerance = max(_COINCIDENT_TOLERANCE_MM, face.Tolerance)
        axis = plane.Axis
        tilt = math.hypot(
            axis.y * normal[2] - axis.z * normal[1],
            axis.z * normal[0] - axis.x * normal[2],
            axis.x * normal[1] - axis.y * normal[0],
        )
        if tilt * max(face.BoundBox.DiagonalLength, 1.0) > tolerance:
            continue
        point = face.Vertexes[0].Point
        distance = normal[0] * point.x + normal[1] * point.y + normal[2] * point.z - offset
        if abs(distance) <= tolerance:
            return True
    return False


def _section_untrusted_reason(shape: object) -> str | None:
    """Why the section kernel cannot be trusted on ``shape``, or ``None`` when it can.

    A valid shell or face is cut. An invalid shape, a solid of non-positive volume (reversed) and a
    shape with no face (a wire or edge cuts to points, never to wires) each read as an empty
    section, which would pass for a plane that misses.
    """
    try:
        if not shape.isValid():
            return "the shape is not valid"
        if not shape.Faces:
            return "the shape has no face to cut"
        for volume in _solid_volumes(shape):
            if volume is not None and not (volume > 0 and math.isfinite(volume)):
                return "the shape holds a solid with non-positive volume (reversed)"
    except Exception:  # noqa: BLE001 -- a shape the kernel cannot even inspect is not cuttable
        return "the shape cannot be inspected"
    return None


def _untrusted_envelope(name: str, reason: str) -> ResultEnvelope:
    """The refusal for a shape the section kernel cannot be trusted on."""
    return _refusal_envelope(
        "section.untrusted_shape", f"object {name} cannot be sectioned: {reason}"
    )


def _section_plane_face(shape: object, normal: tuple[float, float, float], offset: float):
    """A planar face on ``normal . p = offset`` that spans the whole shape."""
    import FreeCAD
    import Part

    direction = FreeCAD.Vector(*normal)
    box = shape.BoundBox
    base = box.Center + direction * (offset - direction.dot(box.Center))
    half = box.DiagonalLength + 1.0
    return Part.Plane(base, direction).toShape(-half, half, -half, half)


def _section_area(shape: object, plane_face: object) -> float | None:
    """The area of the plane face inside ``shape``, or ``None`` when ``common`` gives none."""
    try:
        common = shape.common(plane_face)
        if common.isNull() or not common.BoundBox.isValid():
            return None
        area = float(common.Area)
    except Exception:  # noqa: BLE001 -- a failed boolean leaves the area unmeasured
        return None
    return area if area > 0 and math.isfinite(area) else None


def _wire_face_area(wires: list) -> float | None:
    """The area bounded by closed coplanar ``wires`` (holes respected), or ``None`` if not built."""
    import Part

    try:
        area = float(Part.makeFace(wires, "Part::FaceMakerBullseye").Area)
    except Exception:  # noqa: BLE001 -- a face the kernel cannot build leaves the area unmeasured
        return None
    return area if area > 0 and math.isfinite(area) else None


def _checked_section_area(shape: object, plane_face: object, wires: list) -> float | None:
    """The ``common`` area when the area bounded by the wires agrees with it, else ``None``.

    The two come from different calls, so a plane that confuses ``Shape.section`` (inner edges of
    a coincident face) or ``Shape.common`` makes them differ. A section the kernel loses in both
    calls is not caught.
    """
    from_common = _section_area(shape, plane_face)
    from_wires = _wire_face_area(wires)
    if from_common is None or from_wires is None:
        return None
    if not math.isclose(from_common, from_wires, rel_tol=_AREA_AGREEMENT_REL_TOL):
        return None
    return from_common


def _section_polylines(wires: list, deflection: float, max_points: int) -> tuple[list, bool]:
    """Each wire as ``[[x, y, z], ...]`` up to ``max_points`` points; true when any is left out."""
    polylines: list[list[list[float]]] = []
    used = 0
    for wire in wires:
        remaining = max_points - used
        if remaining < 2:
            return polylines, True
        vertices = wire.discretize(Deflection=deflection)
        kept = vertices[:remaining]
        polylines.append([[float(v.x), float(v.y), float(v.z)] for v in kept])
        used += len(kept)
        if len(kept) < len(vertices):
            return polylines, True
    return polylines, False


def summarize_section(sc: dict) -> str:
    """One line: wire counts, length and area (or unmeasured), plus a truncation note."""
    length = shim.displayed(sc["length"]["value"])
    area = sc["area"]
    area_text = "area unmeasured" if area is None else f"area {shim.displayed(area['value'])} mm^2"
    text = f"{sc['wires']} wire(s), {sc['closed_wires']} closed, length {length} mm, {area_text}."
    return f"{text} Polylines truncated at max_points." if sc.get("truncated") else text


def query_section(
    registry: DocumentRegistry,
    doc: str | None = None,
    object: str | None = None,
    plane: dict | None = None,
    points: dict | None = None,
) -> ResultEnvelope:
    """Cut one object with a plane and report wire counts, length, area and bounding box.

    The plane is ``normal . p = offset`` in the frame of the object's container: the object's own
    ``Placement`` is applied (``obj.Shape``), the container's is not. The cut is ``Shape.section``
    with a plane face on a copy of the shape; ``Shape.slice`` is not used because it returns no
    wires for a plane within 1e-5 mm of a face. ``area`` is the area of the plane face inside the
    shape (``Shape.common``), so holes and islands are right; it is ``null``, never 0, for a shape
    that is not solids only, with an open wire, above ``_MAX_AREA_WIRES`` wires, when the boolean
    gives nothing, and when the area bounded by the wires disagrees with the boolean's. A plane
    that misses gives ``wires`` 0, ``area`` 0 and ``bbox`` null. Solids that overlap or
    touch inside one compound are not detected: the area counts each solid and touching solids
    share edges in the wires. With ``points`` each wire is discretised to ``deflection`` into
    ``polylines``, stopping at ``max_points`` points in total (``truncated``). Returns
    ``INVALID_INPUT`` with code ``section.untrusted_shape`` for an invalid, reversed or face-less
    shape, ``section.too_complex`` above ``_MAX_SECTION_FACES`` faces or ``_MAX_BSPLINE_POLE_LOAD``
    and ``section.plane_on_face`` for a plane that lies on a planar face. Numbers only.
    """
    if not isinstance(object, str) or not object:
        raise ValidationError("object must be a non-empty object name")
    normal, offset = _section_plane(plane)
    request = None if points is None else _section_points(points)

    def read(_handle: str, document: object) -> ResultEnvelope:
        import Part

        # The face limit is checked on the object's own shape: the copy and ``isValid`` of a shape
        # of 240,000 faces took 9.6 s and 42 s with the interpreter lock held.
        own_shape = _named_shape(document, object)
        face_count = len(own_shape.Faces)
        if face_count > _MAX_SECTION_FACES:
            return _refusal_envelope(
                "section.too_complex",
                f"object {object} has {face_count} faces, limit {_MAX_SECTION_FACES}. "
                "Section a simpler object.",
            )
        try:
            pole_load = _bspline_pole_load(own_shape)
        except Exception:  # noqa: BLE001 -- a face whose surface cannot be read is not cuttable
            return _untrusted_envelope(object, "the shape cannot be inspected")
        if pole_load > _MAX_BSPLINE_POLE_LOAD:
            return _refusal_envelope(
                "section.too_complex",
                f"object {object} has a BSpline and Bezier pole load of {pole_load}, limit "
                f"{_MAX_BSPLINE_POLE_LOAD}: the sum over its faces of the square of the pole "
                "count (one face of 800 poles reaches it). Section a simpler object.",
            )
        shape = _copied_queryable_shape(document, object)
        reason = _section_untrusted_reason(shape)
        if reason is not None:
            return _untrusted_envelope(object, reason)
        try:
            on_face = _plane_on_face(shape, normal, offset)
        except Exception:  # noqa: BLE001 -- a face whose surface cannot be read is not cuttable
            return _untrusted_envelope(object, "the shape cannot be inspected")
        if on_face:
            return _refusal_envelope(
                "section.plane_on_face",
                f"the plane lies on a face of {object}; offset it by a small amount "
                "(1e-6 mm or more, more for a shape with a larger tolerance)",
            )
        if request is not None:
            floor = shape.BoundBox.DiagonalLength * _MIN_DEFLECTION_RATIO
            if request[0] < floor:
                raise ValidationError(
                    f"points.deflection {request[0]} is below the minimum {floor} mm "
                    f"({_MIN_DEFLECTION_RATIO} of the object's bounding-box diagonal)"
                )
        plane_face = _section_plane_face(shape, normal, offset)
        edges = shape.section(plane_face).Edges
        wires = [Part.Wire(group) for group in Part.sortEdges(edges)]
        closed = sum(1 for wire in wires if wire.isClosed())
        solids_only = None not in list(_solid_volumes(shape))
        if not wires:
            area = 0.0
        elif solids_only and closed == len(wires) and len(wires) <= _MAX_AREA_WIRES:
            area = _checked_section_area(shape, plane_face, wires)
        else:
            area = None
        structured: dict = {
            "wires": len(wires),
            "closed_wires": closed,
            "area": None if area is None else _quantity(area, "mm^2"),
            "length": _quantity(sum(float(wire.Length) for wire in wires), "mm"),
            "bbox": None,
        }
        if edges:
            # ``BoundBox`` bounds a BSpline edge by its poles (2 mm too wide on a 20 mm NURBS
            # circle); the optimal box is exact.
            hull = Part.Compound(edges).optimalBoundingBox()
            structured["bbox"] = _bbox_record(
                hull.XMin, hull.YMin, hull.ZMin, hull.XMax, hull.YMax, hull.ZMax
            )
        if request is not None:
            structured["polylines"], structured["truncated"] = _section_polylines(wires, *request)
        return _ok_envelope(structured, summarize_section(structured))

    return registry.with_document(doc, read)


def query_dependencies(
    registry: DocumentRegistry,
    doc: str | None = None,
    object: str | None = None,
    max_edges: int = 2000,
) -> ResultEnvelope:
    """Report dependency links by immutable ``Name``.

    With ``object`` → ``{object, in_list, out_list}`` from ``InList``/``OutList``. Without
    ``object`` → the whole-doc ``{edges:[{from,to}], total_edges, returned_edges, truncated}``
    over every object's ``OutList``, capped at ``max_edges``: the first ``max_edges`` edges in
    document/``OutList`` order are kept and ``truncated`` is set when the full count exceeds it.

    Raises ``ValidationError`` when ``max_edges`` is not an integer or is below ``1``.
    """
    if not isinstance(max_edges, int) or isinstance(max_edges, bool):
        raise ValidationError(f"max_edges must be an integer: {max_edges!r}")
    if max_edges < 1:
        raise ValidationError(f"max_edges must be >= 1: {max_edges}")

    def read(_handle: str, document: object) -> ResultEnvelope:
        if object:
            obj = _resolve_object(document, object)
            structured = {
                "object": obj.Name,
                "in_list": [dep.Name for dep in _dedup_by_name(getattr(obj, "InList", []) or [])],
                "out_list": [dep.Name for dep in _out_list(obj)],
            }
            return _ok_envelope(structured, summarize_dependencies(structured))
        edges = [
            {"from": obj.Name, "to": dep.Name} for obj in document.Objects for dep in _out_list(obj)
        ]
        total_edges = len(edges)
        structured = {
            "edges": edges[:max_edges],
            "total_edges": total_edges,
            "returned_edges": min(total_edges, max_edges),
            "truncated": total_edges > max_edges,
        }
        return _ok_envelope(structured, summarize_dependencies(structured))

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
        return _ok_envelope(structured, summarize_sketch_info(structured))

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
        return _ok_envelope(structured, summarize_placement(structured))

    return registry.with_document(doc, read)


_VARSET_TYPE_ID = "App::VarSet"
_SPREADSHEET_TYPE_ID = "Spreadsheet::Sheet"
_PARAMETER_TYPE_NAMES = {type_id: name for name, type_id in PARAMETER_PROPERTY_TYPES.items()}

# Rows returned per list. A document holds a handful of parameters and bindings; the cap keeps a
# generated model with thousands of expressions from filling the agent's context.
_MAX_PARAMETER_ROWS = 500

_QUANTITY_UNITS = {"Length": "mm", "Angle": "deg"}

# ``Spreadsheet.get`` returns a failed formula's error as a string with this prefix (probed on
# FreeCAD 1.1.4: ``=1/0`` reads ``"ERR: division by zero..."``). A text cell holding the same
# words has contents that do not start with ``=``, so only a formula is read as an error.
_CELL_ERROR_PREFIX = "ERR: "


def scalar_reading(value: object) -> tuple[object, str | None, str | None]:
    """Return ``(value, unit, reason)`` for one property or cell value.

    A ``Quantity`` is read in mm for a length and degrees for an angle, else in the preferred
    unit of the active unit schema, with ``unit`` null for a dimensionless one. A number that is
    not finite, or a value of a kind this tool does not report, gives ``None`` with the reason:
    unmeasured, never 0.
    """
    if hasattr(value, "getValueAs"):
        unit = _QUANTITY_UNITS.get(str(value.Unit.Type)) or value.getUserPreferred()[2]
        # ``getValueAs("")`` on a dimensionless quantity returns about 1e308 (probed on 1.1.4).
        number = float(value.getValueAs(unit) if unit else value.Value)
        if not math.isfinite(number):
            return None, unit or None, "the value is not finite"
        return number, unit or None, None
    if isinstance(value, float):
        if not math.isfinite(value):
            return None, None, "the value is not finite"
        return value, None, None
    if isinstance(value, (bool, int, str)):
        return value, None, None
    return None, None, f"a {type(value).__name__} value is not reported"


def _varset_parameter_row(varset: object, prop: str) -> dict:
    """One VarSet property as ``{name, type, value, unit, group, description}``."""
    type_id = varset.getTypeIdOfProperty(prop)
    row = {"name": prop, "type": _PARAMETER_TYPE_NAMES.get(type_id, type_id)}
    try:
        value, unit, reason = scalar_reading(getattr(varset, prop))
    except Exception as exc:  # noqa: BLE001 - an unreadable property is reported, not raised
        value, unit, reason = None, None, f"{type(exc).__name__}: {exc}"
    row.update(
        {
            "value": value,
            "unit": unit,
            "group": varset.getGroupOfProperty(prop),
            "description": varset.getDocumentationOfProperty(prop),
        }
    )
    if reason is not None:
        row["reason"] = reason
    return row


def _spreadsheet_parameter_row(sheet: object, cell: str, alias: str) -> dict:
    """One aliased spreadsheet cell as ``{name, cell, contents, value, unit}``."""
    contents = sheet.getContents(cell)
    row = {"name": alias, "cell": cell, "contents": contents}
    try:
        raw = sheet.get(cell)
        if contents.startswith("=") and isinstance(raw, str) and raw.startswith(_CELL_ERROR_PREFIX):
            value, unit, reason = None, None, raw[len(_CELL_ERROR_PREFIX) :]
        else:
            value, unit, reason = scalar_reading(raw)
    except Exception as exc:  # noqa: BLE001 - a cell that cannot be read is reported, not raised
        value, unit, reason = None, None, f"{type(exc).__name__}: {exc}"
    row.update({"value": value, "unit": unit})
    if reason is not None:
        row["reason"] = reason
    return row


def _parameter_lists(document: object, objects: list) -> tuple[dict, dict]:
    """Read the VarSet, spreadsheet and binding lists; return ``(lists, totals)``.

    Each list holds at most ``_MAX_PARAMETER_ROWS`` rows and ``totals`` counts every row, so a cut
    is visible.
    """
    builtin = shim.varset_builtin_properties()
    varsets: list[dict] = []
    sheets: list[dict] = []
    bindings: list[dict] = []
    totals = {"varset_parameters": 0, "spreadsheet_parameters": 0, "bindings": 0}
    for obj in objects:
        if obj.TypeId == _VARSET_TYPE_ID:
            names = [prop for prop in obj.PropertiesList if prop not in builtin]
            rows = []
            for prop in names:
                if totals["varset_parameters"] < _MAX_PARAMETER_ROWS:
                    rows.append(_varset_parameter_row(obj, prop))
                totals["varset_parameters"] += 1
            varsets.append({"object": obj.Name, "label": obj.Label, "parameters": rows})
        elif obj.TypeId == _SPREADSHEET_TYPE_ID:
            rows = []
            for cell in sorted(obj.getUsedCells()):
                alias = obj.getAlias(cell)
                if not alias:
                    continue
                if totals["spreadsheet_parameters"] < _MAX_PARAMETER_ROWS:
                    rows.append(_spreadsheet_parameter_row(obj, cell, alias))
                totals["spreadsheet_parameters"] += 1
            sheets.append({"object": obj.Name, "label": obj.Label, "parameters": rows})
        for path, expression in list(getattr(obj, "ExpressionEngine", None) or []):
            if totals["bindings"] < _MAX_PARAMETER_ROWS:
                bindings.append({"object": obj.Name, "path": path, "expression": expression})
            totals["bindings"] += 1
    return {"varsets": varsets, "spreadsheets": sheets, "bindings": bindings}, totals


def summarize_parameters(sc: dict) -> str:
    """One-line parameters summary: the three totals, and a note when a list was cut."""
    totals = sc.get("totals") or {}
    line = (
        f"{totals.get('varset_parameters', '?')} VarSet parameter(s) in "
        f"{len(sc.get('varsets') or [])} VarSet(s), "
        f"{totals.get('spreadsheet_parameters', '?')} spreadsheet parameter(s), "
        f"{totals.get('bindings', '?')} binding(s)."
    )
    return f"{line} Lists truncated at {_MAX_PARAMETER_ROWS} rows." if sc.get("truncated") else line


def query_parameters(registry: DocumentRegistry, doc: str | None = None) -> ResultEnvelope:
    """Report the document's VarSet parameters, aliased spreadsheet cells and expression bindings.

    ``varsets`` lists every non-built-in property of each ``App::VarSet``. ``spreadsheets`` lists
    the aliased cells of each ``Spreadsheet::Sheet``; a cell without an alias is not a named
    parameter and is left out. ``bindings`` lists every ``{object, path, expression}`` held in an
    ``ExpressionEngine``. A value that cannot be read is ``null`` with a ``reason``.

    Each list holds at most 500 rows; ``totals`` counts them all and ``truncated`` is true when a
    list was cut. The call reads property values without a recompute and writes nothing.
    """

    def read(_handle: str, document: object) -> ResultEnvelope:
        lists, totals = _parameter_lists(document, sorted(document.Objects, key=lambda o: o.Name))
        structured = {
            **lists,
            "totals": totals,
            "truncated": any(count > _MAX_PARAMETER_ROWS for count in totals.values()),
        }
        return _ok_envelope(structured, summarize_parameters(structured))

    return registry.with_document(doc, read)
