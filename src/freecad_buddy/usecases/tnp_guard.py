"""Topological-naming reference guard: ``snapshot_references`` / ``audit_references``.

``snapshot_references(doc)`` records one ``RefRecord`` per subelement link across the four
reference-holding subsystems (Sketcher external geometry, attachment/datums, PartDesign
profile/base, expression-engine dependencies), capturing the owner's ``ElementMapVersion``, each
entry's subname, its resolved mapped shadow, a geometric witness and its element ancestry.
``audit_references(doc, snapshot, written)`` runs the Layer-0 validity sweep over
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

from typing import TypedDict

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

# Floor for the per-component witness comparison, used when the element reports no tolerance of
# its own. Part.Shape.getTolerance(1) measures 1.0000000000000002e-07 on a padded solid.
_WITNESS_EPSILON = 1e-7

# The sub-shape type plus its bounding-box corners: (ShapeType, XMin, YMin, ZMin, XMax, YMax,
# ZMax). BoundBox reads on every shape type, while CenterOfMass does not — Part.Vertex raises
# AttributeError for it.
Witness = tuple[str, float, float, float, float, float, float]

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


class RefRecord(TypedDict):
    owner: str
    prop: str
    target: str | None
    entries: list[RefEntry]
    element_map_version: str | None


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
    """Return ``element``'s type-plus-bounding-box witness, or ``None`` when unreadable."""
    try:
        bbox = element.BoundBox
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


def _capture_entry(target: object, subname: str) -> RefEntry:
    """Split ``subname`` and fill its mapped shadow, witness and ancestry from ``target``.

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
    return entry


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
            }
        )
    return records


def snapshot_references(doc: object) -> list[RefRecord]:
    """Return one ``RefRecord`` per subelement link and expression binding on ``doc``.

    Walks every object's ``PropertiesList``, selecting the properties whose
    ``getTypeIdOfProperty`` names a subelement-link or expression-engine property. Each record
    carries the owner ``Name``, the property name, the target object ``Name``, one entry per
    subname (split into its mapped/indexed halves and resolved against the target's shape for
    its mapped shadow, geometric witness and element ancestry) and the owner's
    ``ElementMapVersion``. A property that cannot be read is skipped, never raised.
    """
    records: list[RefRecord] = []
    for obj in sorted(doc.Objects, key=lambda o: o.Name):
        for prop in sorted(getattr(obj, "PropertiesList", None) or ()):
            try:
                type_id = obj.getTypeIdOfProperty(prop)
                value = getattr(obj, prop, None)
                if type_id == _EXPRESSION_ENGINE_TYPE:
                    records.extend(_expression_records(obj, prop, value))
                    continue
                if type_id not in _LINK_SUB_TYPES:
                    continue
                version = _element_map_version(obj)
                for target, subs in _link_sub_entries(value):
                    records.append(
                        {
                            "owner": obj.Name,
                            "prop": prop,
                            "target": getattr(target, "Name", None),
                            "entries": [_capture_entry(target, sub) for sub in subs],
                            "element_map_version": version,
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
    otherwise a single finding names the object with no property. A sketch whose sole invalidity
    is redundant constraints is skipped only when the snapshot recorded no references for it:
    redundancy is a warning graded by the sketch verifier, but it must not hide a broken
    reference on the same object.
    """
    by_owner: dict[str, list[RefRecord]] = {}
    for record in snapshot:
        by_owner.setdefault(record["owner"], []).append(record)

    findings: list[RefFinding] = []
    for obj in sorted(doc.Objects, key=lambda o: o.Name):
        if obj.isValid():
            continue
        if shim.redundant_only_sketch(obj) and not by_owner.get(obj.Name):
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
) -> TnpAuditBlock:
    """Audit ``doc``'s references against ``snapshot`` and return a ``TnpAuditBlock``.

    Layer 0 is the validity sweep: every object failing ``isValid()`` yields a ``BROKEN`` finding
    carrying its ``getStatusString()``, and every reference now carrying an unresolved element
    marker yields one too. Layer 1 then diffs each snapshotted record against its live reading —
    a vanished owner is ``BROKEN``, a changed target object is ``REPOINTED``, an
    ``ElementMapVersion`` bump adds a ``RE_BASELINED`` annotation, a lost entry is ``DROPPED``,
    and per entry a non-resolving element is ``BROKEN`` while a changed mapped name or a moved
    witness is ``REPOINTED``. Layer 2 cross-checks the ancestry of the entries Layer 1 left
    ambiguous, reporting ``REPOINTED`` on a divergent ``(sourceTag, sourceName)`` and abstaining
    where no history is available.

    ``status`` is ``UNSUPPORTED`` when ``shim.element_map_available()`` is false (no reference
    reports ``PASS`` in that case), ``FLAGGED`` when any finding carries a verdict other than
    ``PASS`` or ``RE_BASELINED``, else ``CLEAN``. The validity sweep runs on both paths: an object
    that is broken outright is reportable without an element map. Call after mutate -> recompute.

    :param doc: the live document, already recomputed.
    :param snapshot: the pre-mutation ``snapshot_references`` result.
    :param written: the post-op, pre-recompute reading of the same references. A reference whose
        live value matches what the op wrote is the mutation's intended target and is excused the
        entry-count comparison.
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

    findings += _reference_findings(doc, snapshot, live, written or [])
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


def _grade_resolution(doc: object, record: RefRecord, entry: RefEntry) -> RefFinding | None:
    """Return a ``BROKEN`` finding when ``entry`` no longer names a resolvable element, else None.

    An entry naming no element (a whole-object link) has nothing to resolve and yields no finding.
    """
    name = _entry_name(entry)
    if not name:
        return None
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


def _grade_entry(doc: object, record: RefRecord, before: RefEntry, after: RefEntry) -> RefFinding:
    """Layer 1: grade one entry, escalating to Layer 2 only where Layer 1 is ambiguous.

    The order is: an entry naming no element (a whole-object link) passes; an entry FreeCAD
    marked missing or whose element no longer resolves is ``BROKEN``; a changed mapped name is
    ``REPOINTED``; a witness moved beyond the element's own tolerance is ``REPOINTED``. An entry
    surviving all four resolves and matches on both name and witness — the design's definition of
    ambiguous — so Layer 2 grades it.
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
    if _witness_moved(before["witness"], after["witness"], tolerance):
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
    doc: object, record: RefRecord, before: list[RefEntry], after: list[RefEntry]
) -> list[RefFinding]:
    """Grade each ``(before, after)`` entry pair, or report a lone ``PASS`` when there are none."""
    if not after:
        return [
            _finding(
                record, None, "PASS", 1, f"{record['owner']}.{record['prop']} names no element"
            )
        ]
    return [_grade_entry(doc, record, b, a) for b, a in zip(before, after)]


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
        return findings + _grade_entries(doc, record, written["entries"], live["entries"])

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

    return findings + _grade_entries(doc, record, record["entries"], live["entries"])


def _reference_findings(
    doc: object,
    snapshot: list[RefRecord],
    live: list[RefRecord],
    written: list[RefRecord],
) -> list[RefFinding]:
    """Run the Layer-1/2 diff over every snapshotted record, skipping the ones Layer 0 reported.

    An entry FreeCAD already marked missing is reported once, by the Layer-0 sweep; re-grading it
    here would double-count one broken reference in the operator-facing failure count.
    """
    live_by_key = _pair_records(snapshot, live)
    written_by_key = _pair_records(snapshot, written)

    findings: list[RefFinding] = []
    for key, record in _keyed(snapshot).items():
        paired = live_by_key.get(key)
        if paired is not None and any(entry["missing"] for entry in paired["entries"]):
            continue
        findings.extend(_grade_record(doc, record, paired, written_by_key.get(key)))
    return findings


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
