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
from typing import Literal

from freecad_buddy.contracts import CapabilityBanner, ResultEnvelope, summary_text
from freecad_buddy.usecases import shim
from freecad_buddy.usecases.documents import DocumentRegistry, ValidationError
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
    vol = sc.get("volume") or {}
    counts = sc.get("counts") or {}
    kind = "solid" if sc.get("solid") else "non-solid"
    v = shim.displayed(vol.get("value")) if isinstance(vol, dict) else None
    v_txt = f"{v} {vol.get('unit', '')}" if v is not None else "n/a"
    return (
        f"{sc.get('name', '?')}: volume {v_txt} ({kind}), "
        f"{counts.get('faces', '?')} faces, {counts.get('edges', '?')} edges."
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
        metrics = shape_metrics(shape)
        is_solid = metrics["solid"]
        xmin, ymin, zmin, xmax, ymax, zmax = metrics["bbox"]
        # CenterOfMass is meaningful only for a volumetric solid (and is unavailable on some shape
        # types, e.g. Part.Compound). Report null volume/com for a non-solid so an area/length
        # centroid is never presented as volumetric mass; bbox/area/counts stay valid. The com
        # branch keys on whether CenterOfMass was readable, not on `solid`: a compound of solids
        # is a solid that has none, and the bbox-centre fallback must not be published as one.
        com = metrics["com"] if (is_solid and metrics["com_readable"]) else None
        structured = {
            "name": obj.Name,
            "solid": is_solid,
            "volume": _quantity(metrics["volume"], "mm^3") if is_solid else None,
            "area": _quantity(metrics["area"], "mm^2"),
            "bbox": {
                "xmin": _quantity(xmin, "mm"),
                "xmax": _quantity(xmax, "mm"),
                "ymin": _quantity(ymin, "mm"),
                "ymax": _quantity(ymax, "mm"),
                "zmin": _quantity(zmin, "mm"),
                "zmax": _quantity(zmax, "mm"),
            },
            "com": None
            if com is None
            else {
                "x": _quantity(com[0], "mm"),
                "y": _quantity(com[1], "mm"),
                "z": _quantity(com[2], "mm"),
            },
            "counts": dict(metrics["counts"]),
        }
        return _ok_envelope(structured, summarize_mass_properties(structured))

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
