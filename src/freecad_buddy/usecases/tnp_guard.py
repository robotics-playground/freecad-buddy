"""Topological-naming reference guard: ``snapshot_references`` / ``audit_references``.

``snapshot_references(doc)`` records one ``RefRecord`` per subelement link across the four
reference-holding subsystems (Sketcher external geometry, attachment/datums, PartDesign
profile/base, expression-engine dependencies), capturing the owner's ``ElementMapVersion``, each
entry's subname, its resolved mapped shadow, a geometric witness and its element ancestry, plus a
witness of the whole target shape (the support) for the record.
``audit_references(doc, snapshot, written, removed_bindings)`` runs the Layer-0 validity sweep over
``isValid()``/``getStatusString()``, then the Layer-1 per-entry diff (resolution, mapped name,
witness, entry count, ``ElementMapVersion`` re-baseline) and the Layer-2 ancestry cross-check over
the entries Layer 1 left ambiguous, returning a ``TnpAuditBlock``.

``written`` is the post-op, pre-recompute reading of the same references. A reference whose live
value equals what the op wrote is the mutation's intended target and is excused the entry-count
comparison; ownership by an object the op touched is never the exemption test.

Capability-gated: when ``shim.element_map_available()`` is false every verdict is
``UNSUPPORTED`` and no reference reports ``PASS``. Stdlib + FreeCAD App API only; FreeCAD is
never imported here — the document and its objects are passed in.
"""

from __future__ import annotations

import math
import re
from collections.abc import Collection
from typing import NotRequired, TypedDict

from freecad_buddy.contracts import RefFinding, RefVerdict, TnpAuditBlock
from freecad_buddy.usecases import shim

# App/ElementNamingUtils.h: ELEMENT_MAP_PREFIX = ";" marks a mapped (new-style) element name,
# MISSING_PREFIX = "?" marks a subname whose element could not be resolved.
_MAPPED_PREFIX = ";"
_MISSING_PREFIX = "?"

# The C++ property class names of the two subelement-link property kinds. Every reference-holding
# subsystem funnels through one of them, so one strategy covers all four.
_LINK_SUB_TYPES = frozenset({"App::PropertyLinkSub", "App::PropertyLinkSubList"})
_EXPRESSION_ENGINE_TYPE = "App::PropertyExpressionEngine"

# Sketch axes are pseudo-elements: FeatureSketchBased.cpp:1322-1340 resolves them through
# Part2DObject::getAxis, and they have no representation in the sketch's shape, so getElement
# reports them unresolvable however healthy the reference is. The named three plus the indexed
# construction axes ("Axis0", "Axis1", ...) are the four forms that file accepts.
_SKETCH_AXIS_NAMES = frozenset({"V_Axis", "H_Axis", "N_Axis"})
_SKETCH_AXIS_PREFIX = "Axis"
_SKETCH_TYPE_PREFIX = "Sketcher::"

# Floor for the per-component witness comparison, used when the element reports no tolerance of
# its own. Part.Shape.getTolerance(1) measures 1.0000000000000002e-07 on a padded solid.
_WITNESS_EPSILON = 1e-7

# FreeCAD 1.1 mapped-name markers whose number counts pieces in build order (ElementNamingUtils.h:
# POSTFIX_MOD ";:M", POSTFIX_GEN ";:G", POSTFIX_MODGEN ";:MG", POSTFIX_UPPER ";:U", appended with
# an index in TopoShapeExpansion.cpp:1768-1776 and :1871; the bare marker is index 1) and the
# random duplicate rename ";D<hex>" (ElementMap.cpp:753 renameDuplicateElement). No other marker
# starts with M, G or U. The number is printed only when the index exceeds 1 (:1782-1784); the
# indices 0 and 00 name coplanar or parallel faces with a fixed name (:1622-1625, :1776-1781), so
# ";:G0" is stable, but its extra sources are numbered ";K" (:1711-1727) and then hashed, so
# ";:G0#" is positional. A hash id of a multi-source name follows the marker directly, so a "#"
# after ";:G" marks the same positional form. ";K<n>" and ";:I<n>" (PartFeature.cpp:291) number
# extra sources and ancestor faces. A bare ";:G" or ";:U" is index 1 and is positional only while
# a sibling with an index exists (``_split_sibling_stems``).
_POSITIONAL_COUNTER = re.compile(
    r";:MG|;:M|;:[GU](?:[1-9]|0{0,2}#)|;K[0-9]|;:I[0-9]|;D[0-9a-f]+(?=;|$)"
)
_INDEXED_MARKER = re.compile(r";:[GU](?:[1-9]|#)")
_BARE_MARKER = re.compile(r";:[GU](?![0-9#])")

# The sub-shape type plus its bounding-box corners: (ShapeType, XMin, YMin, ZMin, XMax, YMax,
# ZMax). BoundBox reads on every shape type, while CenterOfMass does not — Part.Vertex raises
# AttributeError for it.
Witness = tuple[str, float, float, float, float, float, float]

# Signed bounding-box face shifts per axis, (minimum face, maximum face) for x, y and z.
AxisShifts = tuple[tuple[float, float], tuple[float, float], tuple[float, float]]

# A record's identity within one document: owner name, property name, target object name, and the
# occurrence index of that triple. A PropertyLinkSubList emits one record per (target, subs) pair,
# so the target is part of the identity; the index disambiguates a property that links the same
# target more than once.
RecordKey = tuple[str, str, str | None, int]


class RefEntry(TypedDict):
    mapped: str | None
    indexed: str | None
    missing: bool
    witness: Witness | None
    history: tuple[int, str] | None
    # True when a positional piece counter appears anywhere in the element's recorded lineage, or
    # the lineage cannot be read (``_lineage_has_counter``). Absent in an older snapshot record.
    lineage_counter: NotRequired[bool]
    # True when the mapped name carries a bare ";:G" or ";:U" and the same shape holds a sibling
    # with an indexed marker after the same text. Absent in a record from an older snapshot.
    split_siblings: NotRequired[bool]


class RefRecord(TypedDict):
    owner: str
    prop: str
    target: str | None
    entries: list[RefEntry]
    element_map_version: str | None
    target_witness: Witness | None


def _element_map_version(obj: object) -> str | None:
    """Return the owner's ``ElementMapVersion`` as a string, or ``None`` when unexposed.

    ``GeoFeature.ElementMapVersion`` is a string property (``App/GeoFeature.pyi``); a non-
    ``GeoFeature`` object does not carry it.
    """
    raw = getattr(obj, "ElementMapVersion", None)
    return None if raw is None else str(raw)


def _split_subname(subname: str) -> RefEntry:
    """Split a link subname into its mapped and indexed halves.

    A mapped subname starts with ``;`` and may carry the indexed name after a trailing ``.``
    (``App/ElementNamingUtils.h``). A plain indexed subname (``Face6``) has no mapped half. A
    subname prefixed ``?`` is one FreeCAD could not resolve; the prefix is stripped and the entry
    is marked ``missing`` so it is distinguishable from a healthy reference. The ``witness`` and
    ``history`` halves are left unresolved; ``_capture_entry`` fills them from the live shape.
    """
    text = str(subname)
    missing = text.startswith(_MISSING_PREFIX)
    if missing:
        text = text[len(_MISSING_PREFIX) :]
    if not text.startswith(_MAPPED_PREFIX):
        return {
            "mapped": None,
            "indexed": text,
            "missing": missing,
            "witness": None,
            "history": None,
        }
    head, dot, tail = text.rpartition(".")
    if dot and tail:
        return {
            "mapped": head,
            "indexed": tail,
            "missing": missing,
            "witness": None,
            "history": None,
        }
    return {"mapped": text, "indexed": None, "missing": missing, "witness": None, "history": None}


def _shape_of(target: object) -> object | None:
    """Return ``target``'s ``Shape``, or ``None`` when it carries none or a null one."""
    shape = getattr(target, "Shape", None)
    if shape is None:
        return None
    is_null = getattr(shape, "isNull", None)
    if callable(is_null) and is_null():
        return None
    return shape


def _resolve_element(shape: object, name: str) -> object | None:
    """Return the sub-shape ``name`` names on ``shape``, or ``None`` when it does not resolve.

    ``TopoShape.getElement``'s ``silent`` argument is positional-only
    (``PyArg_ParseTuple(args, "s|O")``, ``Mod/Part/App/TopoShapePyImp.cpp``), and an unresolvable
    name yields a null ``Shape`` rather than ``None`` or a raise.
    """
    getter = getattr(shape, "getElement", None)
    if not callable(getter):
        return None
    try:
        element = getter(name, True)
    except Exception:  # noqa: BLE001 - a name the build cannot parse resolves to nothing
        return None
    is_null = getattr(element, "isNull", None)
    if element is None or (callable(is_null) and is_null()):
        return None
    return element


def _mapped_name(shape: object, indexed: str) -> str | None:
    """Return the mapped shadow of the indexed element name ``indexed``, or ``None``.

    Link properties store the indexed name (``Edge2``), so the mapped half a name comparison
    needs is read from the owning shape rather than parsed out of the subname.
    """
    getter = getattr(shape, "getElementMappedName", None)
    if not callable(getter):
        return None
    try:
        mapped = getter(indexed)
    except Exception:  # noqa: BLE001 - an element with no mapped shadow reports none
        return None
    return str(mapped) if mapped else None


def _witness(element: object) -> Witness | None:
    """Return ``element``'s type-plus-bounding-box witness, or ``None`` when unreadable.

    The box comes from the exact geometry (``optimalBoundingBox(False, False)``: no triangulation,
    no shape tolerance). ``BoundBox`` reads the display mesh once a view has tessellated the shape,
    and the mesh nodes sit off a curved face's extreme (2.0 became 2.0009 on a r3 cylinder after
    ``tessellate(0.5)``), so the same face would read as moved in the GUI and not headless.
    """
    try:
        bbox = element.optimalBoundingBox(False, False)
        return (
            str(element.ShapeType),
            float(bbox.XMin),
            float(bbox.YMin),
            float(bbox.ZMin),
            float(bbox.XMax),
            float(bbox.YMax),
            float(bbox.ZMax),
        )
    except Exception:  # noqa: BLE001 - a shape exposing no bounding box carries no witness
        return None


def _element_tolerance(element: object) -> float:
    """Return the comparison epsilon for ``element``: its own tolerance, floored at the default."""
    getter = getattr(element, "getTolerance", None)
    if not callable(getter):
        return _WITNESS_EPSILON
    try:
        return max(float(getter(1)), _WITNESS_EPSILON)
    except Exception:  # noqa: BLE001 - an element reporting no tolerance uses the default floor
        return _WITNESS_EPSILON


def _axis_shifts(before: Witness | None, after: Witness | None) -> AxisShifts | None:
    """Return the signed shift of a witness's bounding-box faces per axis, or ``None``.

    Each axis carries ``(minimum-face shift, maximum-face shift)``, after minus before. The sign is
    kept so that a face that grew upward and a face that moved downward stay different. Not
    comparable: a side that could not be read, a changed ``ShapeType``, or a non-finite component
    (NaN, infinity). Callers read ``None`` as "no bound", never as "no movement".
    """
    if before is None or after is None or before[0] != after[0]:
        return None
    deltas = [a - b for a, b in zip(after[1:], before[1:])]
    if not all(math.isfinite(delta) for delta in deltas):
        return None
    return ((deltas[0], deltas[3]), (deltas[1], deltas[4]), (deltas[2], deltas[5]))


def _has_positional_counter(name: str | None) -> bool:
    """Whether a mapped name carries a build-order piece counter or a duplicate-rename marker.

    FreeCAD numbers the pieces of a split face or edge by position (``;:M``, ``;:M2``, ...). An edit
    that changes the piece count shifts every counter, so one name and one history source can
    then denote a different piece. Such a name proves nothing about identity.
    """
    return bool(name) and _POSITIONAL_COUNTER.search(name) is not None


def _split_sibling_stems(shape: object) -> frozenset[str]:
    """Return the text before each indexed ``;:G``/``;:U`` marker in ``shape``'s element map.

    An element named with the bare marker is piece 1 of that stem; a stem that also appears here
    has further pieces, so piece 1 can name another piece after a piece-count change.
    """
    try:
        names = shape.ElementMap
    except Exception:  # noqa: BLE001 - a shape without an element map has no sibling evidence
        return frozenset()
    return frozenset(
        name[: match.start()] for name in names for match in _INDEXED_MARKER.finditer(name)
    )


def _has_split_siblings(name: str | None, stems: frozenset[str]) -> bool:
    """Whether a bare-marker mapped name shares its leading text with an indexed sibling."""
    return bool(name) and any(
        name[: match.start()] in stems for match in _BARE_MARKER.finditer(name)
    )


def _lineage_has_counter(target: object, name: str) -> bool:
    """Whether any name in the element's whole history chain carries a positional counter.

    FreeCAD folds the older part of a mapped name into a ``#id`` hash (``ElementMap.cpp:668``), and
    ``TopoShape.getElementHistory`` steps back one object only, so a counter can sit two features
    behind the visible name. ``Part.Feature.getElementHistory(recursive=True)`` walks to the origin
    and returns each source name and its intermediate names. A lineage that cannot be read counts
    as positional: no proof of identity, no excuse.
    """
    getter = getattr(target, "getElementHistory", None)
    if not callable(getter):
        return True
    try:
        chain = getter(name, recursive=True, showName=True)
    except Exception:  # noqa: BLE001 - an unreadable lineage proves nothing about identity
        return True
    if not chain:
        return False
    try:
        return any(
            _has_positional_counter(candidate)
            for item in chain
            for candidate in [item[1], *item[2]]
        )
    except Exception:  # noqa: BLE001 - an unexpected record shape proves nothing about identity
        return True


def _follows_support(
    before: RefEntry, after: RefEntry, support_shift: AxisShifts | None, tolerance: float
) -> bool:
    """Whether a moved witness is the same element carried along by its support object.

    FreeCAD itself must call it the same element — an equal mapped name and an equal history
    source on both sides, neither unreadable — and the support object must really have changed.
    Each face shift of the element must then lie in the range spanned by zero and both of the
    support's face shifts on that axis. A shift along an axis the support did not move on, or
    outside that range, stays ``REPOINTED``. The range joins both support faces because a face
    must be able to follow the support's other face (midplane growth); the cost is that a tampered
    shift opposite to its own face but inside that range is excused.

    A mapped name or history source name that carries a positional piece counter
    (``_has_positional_counter``) anywhere in its lineage (``lineage_counter``), or a bare
    ``;:G``/``;:U`` name whose shape holds indexed
    siblings (``split_siblings``), is never excused: after a piece-count change the same name can
    denote another piece, so equality of the two names no longer shows the same element.
    """
    element_shift = _axis_shifts(before["witness"], after["witness"])
    if element_shift is None or support_shift is None:
        return False
    same_element = (
        before["mapped"] is not None
        and before["mapped"] == after["mapped"]
        and before["history"] is not None
        and before["history"] == after["history"]
        and not before.get("lineage_counter", False)
        and not after.get("lineage_counter", False)
        and not before.get("split_siblings", False)
        and not after.get("split_siblings", False)
        and not any(
            _has_positional_counter(name)
            for name in (
                before["mapped"],
                after["mapped"],
                before["history"][1],
                after["history"][1],
            )
        )
    )
    support_moved = any(abs(shift) > tolerance for axis in support_shift for shift in axis)
    inside_support_shift = all(
        min(0.0, *support_axis) - tolerance <= shift <= max(0.0, *support_axis) + tolerance
        for element_axis, support_axis in zip(element_shift, support_shift)
        for shift in element_axis
    )
    return same_element and support_moved and inside_support_shift


def _witness_moved(before: Witness | None, after: Witness | None, tolerance: float) -> bool:
    """Whether two witnesses differ: a type change, a missing side, or a component beyond epsilon.

    A side that could not be read counts as moved rather than as unchanged — losing the ability
    to read a witness is evidence of change. The component test is written as
    ``not (delta <= tolerance)`` so a NaN coordinate reads as moved rather than as equal.
    """
    if before is None or after is None:
        return before is not after
    if before[0] != after[0]:
        return True
    return any(not (abs(a - b) <= tolerance) for a, b in zip(before[1:], after[1:]))


def _history(shape: object, mapped: str | None) -> tuple[int, str] | None:
    """Return ``(sourceTag, sourceName)`` for the mapped element name, or ``None``.

    ``TopoShape.getElementHistory`` yields ``(sourceTag, sourceName, [intermediates])`` for a
    mapped name and ``None`` for an indexed or unmapped one. The intermediate list is
    rebuild-order sensitive, so only the source pair is kept.
    """
    if not mapped:
        return None
    getter = getattr(shape, "getElementHistory", None)
    if not callable(getter):
        return None
    try:
        record = getter(mapped)
        if not record or len(record) < 2:
            return None
        return (int(record[0]), str(record[1]))
    except Exception:  # noqa: BLE001 - a name the build cannot trace has no history
        return None


def _capture_entry(
    target: object, subname: str, sibling_stems: dict[str | None, frozenset[str]] | None = None
) -> RefEntry:
    """Split ``subname`` and fill its mapped shadow, witness and ancestry from ``target``.

    ``sibling_stems`` caches ``_split_sibling_stems`` per target name across one walk.

    An entry that names no element (a whole-object link), a target carrying no shape, or an
    element that does not resolve leaves the resolved halves ``None`` rather than raising.
    """
    entry = _split_subname(subname)
    name = entry["indexed"] or entry["mapped"]
    if not name:
        return entry
    shape = _shape_of(target)
    if shape is None:
        return entry
    if entry["mapped"] is None and entry["indexed"]:
        entry["mapped"] = _mapped_name(shape, entry["indexed"])
    element = _resolve_element(shape, name)
    if element is not None:
        entry["witness"] = _witness(element)
    entry["history"] = _history(shape, entry["mapped"])
    if entry["mapped"]:
        entry["lineage_counter"] = _lineage_has_counter(target, entry["mapped"])
    if entry["mapped"] and _BARE_MARKER.search(entry["mapped"]):
        cache = sibling_stems if sibling_stems is not None else {}
        key = getattr(target, "Name", None)
        if key not in cache:
            cache[key] = _split_sibling_stems(shape)
        entry["split_siblings"] = _has_split_siblings(entry["mapped"], cache[key])
    return entry


def _support_witness(target: object) -> Witness | None:
    """Return the witness of ``target``'s whole shape, or ``None`` when it carries none.

    A whole-object link never read its target's shape before, so a shape that cannot be read here
    must cost only the excuse, never the reference record.
    """
    try:
        shape = _shape_of(target)
    except Exception:  # noqa: BLE001 - an unreadable shape leaves the support unwitnessed
        return None
    return None if shape is None else _witness(shape)


def _link_sub_entries(value: object) -> list[tuple[object, list[str]]]:
    """Normalize a ``PropertyLinkSub``/``PropertyLinkSubList`` value to ``[(target, subs)]``.

    ``PropertyLinkSub`` yields ``(obj, [sub, ...])`` or ``None``; ``PropertyLinkSubList`` yields
    ``[(obj, (sub, ...)), ...]`` (``App/PropertyLinks.cpp``). An unrecognized shape yields no
    pairs rather than raising.
    """
    if value is None:
        return []
    if isinstance(value, tuple) and len(value) == 2:
        target, subs = value
        return [(target, [str(s) for s in subs or ()])]
    if isinstance(value, list):
        pairs: list[tuple[object, list[str]]] = []
        for item in value:
            if isinstance(item, tuple) and len(item) == 2:
                target, subs = item
                pairs.append((target, [str(s) for s in subs or ()]))
        return pairs
    return []


def _expression_records(obj: object, prop: str, value: object) -> list[RefRecord]:
    """Record one ``RefRecord`` per expression binding on ``obj``.

    A ``PropertyExpressionEngine`` value is a list of ``(property_path, expression)`` pairs; the
    expression text is the reference witness.
    """
    records: list[RefRecord] = []
    version = _element_map_version(obj)
    for item in value or ():
        if not (isinstance(item, (tuple, list)) and len(item) == 2):
            continue
        path, expression = item
        records.append(
            {
                "owner": obj.Name,
                "prop": f"{prop}[{path}]",
                "target": None,
                "entries": [
                    {
                        "mapped": None,
                        "indexed": str(expression),
                        "missing": False,
                        "witness": None,
                        "history": None,
                    }
                ],
                "element_map_version": version,
                "target_witness": None,
            }
        )
    return records


def snapshot_references(doc: object) -> list[RefRecord]:
    """Return one ``RefRecord`` per subelement link and expression binding on ``doc``.

    Walks every object's ``PropertiesList``, selecting the properties whose
    ``getTypeIdOfProperty`` names a subelement-link or expression-engine property. Each record
    carries the owner ``Name``, the property name, the target object ``Name``, one entry per
    subname (split into its mapped/indexed halves and resolved against the target's shape for
    its mapped shadow, geometric witness and element ancestry), a witness of the whole target
    shape (``target_witness``) and the owner's ``ElementMapVersion``. A property that cannot be
    read is skipped, never raised.
    """
    records: list[RefRecord] = []
    support_witnesses: dict[str | None, Witness | None] = {}
    sibling_stems: dict[str | None, frozenset[str]] = {}
    for obj in sorted(doc.Objects, key=lambda o: o.Name):
        for prop in sorted(getattr(obj, "PropertiesList", None) or ()):
            try:
                type_id = obj.getTypeIdOfProperty(prop)
                # A value is read only once its type passes: reading ``Shape`` copies the object's
                # ``TopoShape`` with its element map into a new Python object.
                if type_id == _EXPRESSION_ENGINE_TYPE:
                    records.extend(_expression_records(obj, prop, getattr(obj, prop, None)))
                    continue
                if type_id not in _LINK_SUB_TYPES:
                    continue
                value = getattr(obj, prop, None)
                version = _element_map_version(obj)
                for target, subs in _link_sub_entries(value):
                    target_name = getattr(target, "Name", None)
                    if target_name not in support_witnesses:
                        support_witnesses[target_name] = _support_witness(target)
                    records.append(
                        {
                            "owner": obj.Name,
                            "prop": prop,
                            "target": target_name,
                            "entries": [_capture_entry(target, sub, sibling_stems) for sub in subs],
                            "element_map_version": version,
                            "target_witness": support_witnesses[target_name],
                        }
                    )
            except Exception:  # noqa: BLE001 - an unreadable property records no reference
                continue
    return records


def _status_string(obj: object) -> str:
    """Return ``obj.getStatusString()`` or an empty string when unavailable."""
    getter = getattr(obj, "getStatusString", None)
    return str(getter()) if callable(getter) else ""


def _unsupported_findings(snapshot: list[RefRecord]) -> list[RefFinding]:
    """Return one ``UNSUPPORTED`` finding per snapshotted reference."""
    return [
        {
            "owner": record["owner"],
            "prop": record["prop"],
            "mapped_before": record["entries"][0]["mapped"] if record["entries"] else None,
            "state_after": None,
            "verdict": "UNSUPPORTED",
            "layer": 0,
            "detail": "element map unavailable on this build; no reference can be graded",
        }
        for record in snapshot
    ]


def _invalid_object_findings(doc: object, snapshot: list[RefRecord]) -> list[RefFinding]:
    """Return one ``BROKEN`` finding per object failing ``isValid()`` — the Layer-0 sweep.

    A failing object's own references are attributed to it where the snapshot recorded any;
    otherwise a single finding names the object with no property.
    """
    by_owner: dict[str, list[RefRecord]] = {}
    for record in snapshot:
        by_owner.setdefault(record["owner"], []).append(record)

    findings: list[RefFinding] = []
    for obj in sorted(doc.Objects, key=lambda o: o.Name):
        if obj.isValid():
            continue
        status = _status_string(obj)
        owned = by_owner.get(obj.Name, [])
        if not owned:
            findings.append(
                {
                    "owner": obj.Name,
                    "prop": "",
                    "mapped_before": None,
                    "state_after": status,
                    "verdict": "BROKEN",
                    "layer": 0,
                    "detail": f"{obj.Name} is invalid after the mutation: {status}",
                }
            )
            continue
        for record in owned:
            findings.append(
                {
                    "owner": record["owner"],
                    "prop": record["prop"],
                    "mapped_before": record["entries"][0]["mapped"] if record["entries"] else None,
                    "state_after": status,
                    "verdict": "BROKEN",
                    "layer": 0,
                    "detail": f"{obj.Name} is invalid after the mutation: {status}",
                }
            )
    return findings


def audit_references(
    doc: object,
    snapshot: list[RefRecord],
    written: list[RefRecord] | None = None,
    deleted: frozenset[str] = frozenset(),
    removed_bindings: Collection[tuple[str, str]] = (),
) -> TnpAuditBlock:
    """Audit ``doc``'s references against ``snapshot`` and return a ``TnpAuditBlock``.

    Layer 0 is the validity sweep: every object failing ``isValid()`` yields a ``BROKEN`` finding
    carrying its ``getStatusString()``, and every reference now carrying an unresolved element
    marker yields one too. Layer 1 then diffs each snapshotted record against its live reading —
    a vanished owner is ``BROKEN``, a changed target object is ``REPOINTED``, an
    ``ElementMapVersion`` bump adds a ``RE_BASELINED`` annotation, a lost entry is ``DROPPED``,
    and per entry a non-resolving element is ``BROKEN`` while a changed mapped name or a moved
    witness is ``REPOINTED`` (a witness move is excused when the same element rode a support that
    moved the same way and at least as far). Layer 2 cross-checks the ancestry of the entries
    Layer 1 left ambiguous, reporting ``REPOINTED`` on a divergent ``(sourceTag, sourceName)`` and
    abstaining where no history is available.

    ``status`` is ``UNSUPPORTED`` when ``shim.element_map_available()`` is false (no reference
    reports ``PASS`` in that case), ``FLAGGED`` when any finding carries a verdict other than
    ``PASS`` or ``RE_BASELINED``, else ``CLEAN``. The validity sweep runs on both paths: an object
    that is broken outright is reportable without an element map. Call after mutate -> recompute.

    :param doc: the live document, already recomputed.
    :param snapshot: the pre-mutation ``snapshot_references`` result.
    :param written: the post-op, pre-recompute reading of the same references. A reference whose
        live value matches what the op wrote is the mutation's intended target and is excused the
        entry-count comparison.
    :param deleted: names of the objects the op deleted on purpose. A snapshotted record whose
        owner is in this set and absent from ``doc`` is excused; an owner that vanished any other
        way stays ``BROKEN``.
    :param removed_bindings: ``(owner, record prop)`` of each expression binding the op reports
        it removed. Such a binding, absent from ``written`` and from the live reading on an owner
        that still exists, passes; a binding removed by anything else grades ``BROKEN``, as does
        every removal when no ``written`` reading is given.
    """
    version = _element_map_version_banner()
    live = snapshot_references(doc)
    findings = _invalid_object_findings(doc, snapshot) + _missing_element_findings(live)

    if not shim.element_map_available():
        return {
            "status": "UNSUPPORTED",
            "element_map_version": version,
            "findings": findings + _unsupported_findings(snapshot),
        }

    findings += _reference_findings(doc, snapshot, live, written, deleted, removed_bindings)
    failing = [f for f in findings if f["verdict"] not in ("PASS", "RE_BASELINED")]
    return {
        "status": "FLAGGED" if failing else "CLEAN",
        "element_map_version": version,
        "findings": findings,
    }


def _keyed(records: list[RefRecord]) -> dict[RecordKey, RefRecord]:
    """Index ``records`` by ``(owner, prop, target, occurrence)``.

    A ``PropertyLinkSubList`` emits one record per ``(target, subs)`` pair, so the target belongs
    to the identity or a multi-target property collapses to its last pair. The occurrence counter
    disambiguates a property that links the same target more than once.
    """
    seen: dict[tuple[str, str, str | None], int] = {}
    keyed: dict[RecordKey, RefRecord] = {}
    for record in records:
        triple = (record["owner"], record["prop"], record["target"])
        index = seen.get(triple, 0)
        seen[triple] = index + 1
        keyed[triple + (index,)] = record
    return keyed


def _position(records: list[RefRecord]) -> dict[RecordKey, int]:
    """Map each record's key to its ordinal position within its ``(owner, prop)`` group.

    The position is what pairs a snapshot record with its live counterpart when the target itself
    changed, since a re-point alters the key and no exact match survives.
    """
    seen: dict[tuple[str, str], int] = {}
    positions: dict[RecordKey, int] = {}
    for key, record in _keyed(records).items():
        pair = (record["owner"], record["prop"])
        index = seen.get(pair, 0)
        seen[pair] = index + 1
        positions[key] = index
    return positions


def _pair_records(snapshot: list[RefRecord], other: list[RefRecord]) -> dict[RecordKey, RefRecord]:
    """Pair each snapshot record with its counterpart in ``other``, keyed by the snapshot's key.

    An exact ``(owner, prop, target, occurrence)`` match wins. A snapshot record left unmatched
    falls back to the record holding the same ordinal position within its ``(owner, prop)`` group,
    which is how a link re-pointed to a different object is paired with its replacement rather than
    read as a vanished owner.
    """
    other_by_key = _keyed(other)
    paired: dict[RecordKey, RefRecord] = {}
    unmatched: list[RecordKey] = []
    for key in _keyed(snapshot):
        if key in other_by_key:
            paired[key] = other_by_key[key]
        else:
            unmatched.append(key)
    if not unmatched:
        return paired

    taken = {id(record) for record in paired.values()}
    other_positions = _position(other)
    by_slot = {
        (record["owner"], record["prop"], other_positions[key]): record
        for key, record in other_by_key.items()
        if id(record) not in taken
    }
    snapshot_positions = _position(snapshot)
    for key in unmatched:
        slot = (key[0], key[1], snapshot_positions[key])
        if slot in by_slot:
            paired[key] = by_slot[slot]
    return paired


def _entry_name(entry: RefEntry) -> str:
    """The element name an entry references, for reporting."""
    return entry["indexed"] or entry["mapped"] or ""


def _entry_values(record: RefRecord | None) -> list[str]:
    """The element names a record references, in order — the value comparison the op is held to."""
    return [] if record is None else [_entry_name(entry) for entry in record["entries"]]


def _finding(
    record: RefRecord,
    entry: RefEntry | None,
    verdict: RefVerdict,
    layer: int,
    detail: str,
    state_after: str | None = None,
) -> RefFinding:
    """Build one ``RefFinding`` for ``record`` (optionally a specific ``entry``)."""
    return {
        "owner": record["owner"],
        "prop": record["prop"],
        "mapped_before": entry["mapped"] if entry else None,
        "state_after": state_after,
        "verdict": verdict,
        "layer": layer,
        "detail": detail,
    }


def _grade_ancestry(record: RefRecord, before: RefEntry, after: RefEntry) -> RefFinding:
    """Layer 2: compare an ambiguous entry's element ancestry against its snapshot.

    Compares only ``(sourceTag, sourceName)`` — ``getElementHistory``'s intermediate list is
    rebuild-order sensitive, so including it would flag legitimate recomputes. A missing history
    on either side abstains: Layer 1 already graded the entry ``PASS``, and an abstention never
    produces a failure.
    """
    name = _entry_name(before)
    if before["history"] is None or after["history"] is None:
        return _finding(record, before, "PASS", 2, f"{name} has no comparable element history")
    if before["history"] != after["history"]:
        return _finding(
            record,
            before,
            "REPOINTED",
            2,
            (
                f"{record['owner']}.{record['prop']} entry {name} resolves to an element with a "
                f"different source: {before['history']} -> {after['history']}"
            ),
            state_after=str(after["history"]),
        )
    return _finding(record, before, "PASS", 2, f"{name} descends from the same source element")


def _live_element(doc: object, record: RefRecord, name: str) -> object | None:
    """Resolve ``name`` against the live target of ``record``, or ``None`` when it does not."""
    target = doc.getObject(record["target"]) if record["target"] else None
    shape = _shape_of(target) if target is not None else None
    return _resolve_element(shape, name) if shape is not None else None


def _is_sketch_axis(doc: object, record: RefRecord, name: str) -> bool:
    """Whether ``name`` is a sketch-axis pseudo-element on ``record``'s target.

    ``FeatureSketchBased.cpp:1322-1340`` accepts four forms — ``V_Axis``, ``H_Axis``, ``N_Axis``
    and the indexed ``Axis<N>`` construction axes — and resolves each through
    ``Part2DObject::getAxis``. None has a shape representation, measured on FreeCAD 1.1.1:
    ``getElement`` returns a null shape for all four while ``Edge1`` resolves normally.

    Scoped to a ``Sketcher::`` target, so an element that merely shares one of these names on
    another object is still resolved and graded.
    """
    target = doc.getObject(record["target"]) if record["target"] else None
    if target is None:
        return False
    if not str(getattr(target, "TypeId", "")).startswith(_SKETCH_TYPE_PREFIX):
        return False
    if name in _SKETCH_AXIS_NAMES:
        return True
    return name.startswith(_SKETCH_AXIS_PREFIX) and name[len(_SKETCH_AXIS_PREFIX) :].isdigit()


def _grade_resolution(doc: object, record: RefRecord, entry: RefEntry) -> RefFinding | None:
    """Return a ``BROKEN`` finding when ``entry`` no longer names a resolvable element, else None.

    An entry naming no element (a whole-object link) has nothing to resolve and yields no finding.

    A named target the document no longer holds is unresolved rather than unchecked: the object is
    gone, so the element it carried is gone with it. Reading a missing object as "nothing to
    compare" graded that reference ``PASS``, and whether anything else caught it depended on
    FreeCAD marking the owner invalid — which for a ``FeatureDressUp`` is the silent case this
    guard exists to cover. A target that is present but carries no shape stays unchecked, because
    a shapeless object has no elements to resolve against and never did.

    A sketch axis is exempt from the resolution test: it is a pseudo-element with no shape
    representation, so ``getElement`` reports it unresolvable however healthy the reference is.
    Grading it by shape resolution flagged an ``Up-to-date`` Pad's ``ReferenceAxis`` as ``BROKEN``,
    and ``post_verify`` fails on a flagged audit, so the false positive rolled back correct
    mutations on any document whose pad carries a reference axis.
    """
    name = _entry_name(entry)
    if not name:
        return None
    if _is_sketch_axis(doc, record, name):
        return None
    if record["target"] and doc.getObject(record["target"]) is None:
        return _finding(
            record,
            entry,
            "BROKEN",
            1,
            (
                f"{record['owner']}.{record['prop']} entry {name} names an element on "
                f"{record['target']}, which is no longer in the document"
            ),
            state_after=name,
        )
    target = doc.getObject(record["target"]) if record["target"] else None
    shape = _shape_of(target) if target is not None else None
    unresolved = shape is not None and _resolve_element(shape, name) is None
    if entry["missing"] or unresolved:
        return _finding(
            record,
            entry,
            "BROKEN",
            1,
            f"{record['owner']}.{record['prop']} entry {name} no longer resolves",
            state_after=name,
        )
    return None


def _grade_entry(
    doc: object,
    record: RefRecord,
    before: RefEntry,
    after: RefEntry,
    support_shift: AxisShifts | None,
) -> RefFinding:
    """Layer 1: grade one entry, escalating to Layer 2 only where Layer 1 is ambiguous.

    The order is: an entry naming no element (a whole-object link) passes; an entry FreeCAD
    marked missing or whose element no longer resolves is ``BROKEN``; a changed mapped name is
    ``REPOINTED``; a witness moved beyond the element's own tolerance is ``REPOINTED`` unless
    ``_follows_support`` excuses it. An entry surviving all four resolves and matches on name and
    either matches on witness or moved with its support — the design's definition of ambiguous —
    so Layer 2 grades it. ``support_shift`` is how the record's whole target shape moved on each
    axis.
    """
    name = _entry_name(before)
    if not name:
        return _finding(record, before, "PASS", 1, "whole-object link names no element")

    broken = _grade_resolution(doc, record, after)
    if broken is not None:
        return broken
    element = _live_element(doc, record, name)

    if before["mapped"] and after["mapped"] and before["mapped"] != after["mapped"]:
        return _finding(
            record,
            before,
            "REPOINTED",
            1,
            (
                f"{record['owner']}.{record['prop']} entry {name} now maps to a different "
                f"element: {before['mapped']} -> {after['mapped']}"
            ),
            state_after=after["mapped"],
        )

    tolerance = _element_tolerance(element) if element is not None else _WITNESS_EPSILON
    if _witness_moved(before["witness"], after["witness"], tolerance) and not _follows_support(
        before, after, support_shift, tolerance
    ):
        return _finding(
            record,
            before,
            "REPOINTED",
            1,
            (
                f"{record['owner']}.{record['prop']} entry {name} resolves to a sub-shape whose "
                f"witness moved: {before['witness']} -> {after['witness']}"
            ),
            state_after=str(after["witness"]),
        )

    return _grade_ancestry(record, before, after)


def _grade_entries(
    doc: object, record: RefRecord, baseline: RefRecord, live: RefRecord
) -> list[RefFinding]:
    """Grade each ``(baseline, live)`` entry pair, or report a lone ``PASS`` when there are none.

    ``baseline`` is the snapshot record, or the op-written one for an exempt record; it shares
    ``record``'s owner, property and target.
    """
    before, after = baseline["entries"], live["entries"]
    if not after:
        return [
            _finding(
                record, None, "PASS", 1, f"{record['owner']}.{record['prop']} names no element"
            )
        ]
    support_shift = _axis_shifts(baseline["target_witness"], live["target_witness"])
    return [_grade_entry(doc, record, b, a, support_shift) for b, a in zip(before, after)]


def _grade_record(
    doc: object,
    record: RefRecord,
    live: RefRecord | None,
    written: RefRecord | None,
) -> list[RefFinding]:
    """Grade one snapshotted record: the record-level checks, then the per-entry diff.

    An absent owner or a changed target object supersedes every entry verdict, so each returns
    alone. An ``ElementMapVersion`` bump adds a ``RE_BASELINED`` annotation and grading continues,
    because that verdict does not fail the audit and would otherwise mask a concurrent drop.

    The exemption is keyed to the value the op wrote, never to ownership by a touched object: when
    a record's live entry names equal the post-op ones the op assigned, the entry-count comparison
    is suppressed — and only that comparison. An exempt record runs the same per-entry grading
    (resolution, mapped name, witness, ancestry) that a non-exempt record runs, against the value
    the op wrote.
    """
    if live is None:
        return [
            _finding(
                record,
                None,
                "BROKEN",
                1,
                f"{record['owner']} is no longer present in the document",
            )
        ]

    if record["target"] != live["target"]:
        return [
            _finding(
                record,
                None,
                "REPOINTED",
                1,
                (
                    f"{record['owner']}.{record['prop']} now links a different object: "
                    f"{record['target']} -> {live['target']}"
                ),
                state_after=live["target"],
            )
        ]

    findings: list[RefFinding] = []
    if record["element_map_version"] != live["element_map_version"]:
        findings.append(
            _finding(
                record,
                None,
                "RE_BASELINED",
                1,
                (
                    f"{record['owner']} rebuilt its element map "
                    f"({record['element_map_version']} -> {live['element_map_version']}); its "
                    "references are re-baselined, not failed"
                ),
                state_after=live["element_map_version"],
            )
        )

    intended = written is not None and _entry_values(live) == _entry_values(written)
    if intended:
        return findings + _grade_entries(doc, record, written, live)

    before_count = len(record["entries"])
    after_count = len(live["entries"])
    if after_count != before_count:
        findings.append(
            _finding(
                record,
                None,
                "DROPPED" if after_count < before_count else "REPOINTED",
                1,
                (
                    f"{record['owner']}.{record['prop']} holds {after_count} entr"
                    f"{'y' if after_count == 1 else 'ies'} where the snapshot recorded "
                    f"{before_count}"
                ),
                state_after=str(after_count),
            )
        )
        return findings

    return findings + _grade_entries(doc, record, record, live)


def _reference_findings(
    doc: object,
    snapshot: list[RefRecord],
    live: list[RefRecord],
    written: list[RefRecord] | None,
    deleted: frozenset[str] = frozenset(),
    removed_bindings: Collection[tuple[str, str]] = (),
) -> list[RefFinding]:
    """Run the Layer-1/2 diff over every snapshotted record, skipping the entries Layer 0 reported.

    An entry FreeCAD already marked missing is reported once, by the Layer-0 sweep; re-grading it
    here would double-count one broken reference in the operator-facing failure count. The skip is
    per entry rather than per record, so a record holding a missing entry alongside a re-pointed
    one still has the re-point graded instead of being suppressed with it.

    A record whose every entry is missing is skipped outright: Layer 0 has reported all of it, and
    grading the empty remainder would emit a spurious "names no element" PASS.

    A record whose owner the op deleted on purpose (``deleted``) and that is gone from ``doc`` is
    excused: the delete set is what the op wrote, in the sense of decision 014. The owner must be
    in the set AND absent, so a delete that did not happen, or an owner that vanished any other
    way, still grades ``BROKEN``.
    """
    live_by_key = _pair_records(snapshot, live)
    written_by_key = _pair_records(snapshot, written or [])

    findings: list[RefFinding] = []
    for key, record in _keyed(snapshot).items():
        paired = live_by_key.get(key)
        if (
            paired is None
            and written is not None
            and key not in written_by_key
            and (record["owner"], record["prop"]) in removed_bindings
            and doc.getObject(record["owner"]) is not None
        ):
            findings.append(
                _finding(
                    record,
                    None,
                    "PASS",
                    1,
                    f"{record['owner']}.{record['prop']} was cleared by the op",
                )
            )
            continue
        if paired is not None and any(entry["missing"] for entry in paired["entries"]):
            record, paired = _without_missing_entries(record, paired)
            if paired is None:
                continue
        if paired is None and record["owner"] in deleted and doc.getObject(record["owner"]) is None:
            findings.append(
                _finding(
                    record,
                    None,
                    "PASS",
                    1,
                    f"{record['owner']} was deleted by the operation",
                )
            )
            continue
        findings.extend(_grade_record(doc, record, paired, written_by_key.get(key)))
    return findings


def _without_missing_entries(
    record: RefRecord, live: RefRecord
) -> tuple[RefRecord, RefRecord | None]:
    """Drop the entries Layer 0 already reported, from both sides at the same positions.

    ``_grade_entries`` pairs the two entry lists positionally, so removing an entry from the live
    side alone would shift every later pair and grade one reference against another's snapshot.
    Filtering by index keeps the pairing intact. Entry counts that already differ are left
    untouched, because the count comparison is itself the finding.

    :return: the record and live pair to grade, with ``None`` for live when nothing remains.
    """
    if len(record["entries"]) != len(live["entries"]):
        return record, live
    keep = [i for i, entry in enumerate(live["entries"]) if not entry["missing"]]
    if not keep:
        return record, None
    return (
        {**record, "entries": [record["entries"][i] for i in keep]},
        {**live, "entries": [live["entries"][i] for i in keep]},
    )


def _missing_element_findings(live: list[RefRecord]) -> list[RefFinding]:
    """Return one ``BROKEN`` finding per live reference whose element no longer resolves.

    Reports every entry FreeCAD marked with the missing prefix, which an ``isValid()`` sweep
    alone does not surface.
    """
    findings: list[RefFinding] = []
    for record in live:
        for entry in record["entries"]:
            if not entry["missing"]:
                continue
            findings.append(
                {
                    "owner": record["owner"],
                    "prop": record["prop"],
                    "mapped_before": entry["mapped"],
                    "state_after": entry["indexed"],
                    "verdict": "BROKEN",
                    "layer": 0,
                    "detail": (
                        f"{record['owner']}.{record['prop']} references an element that no "
                        f"longer resolves: {entry['indexed']}"
                    ),
                }
            )
    return findings


def _element_map_version_banner() -> str | None:
    """Return the build's element-map version as a string, or ``None`` when unexposed."""
    return shim.element_map_version_string()
