"""Topological-naming reference guard: ``snapshot_references`` / ``audit_references``.

``snapshot_references(doc)`` records one ``RefRecord`` per subelement link across the four
reference-holding subsystems (Sketcher external geometry, attachment/datums, PartDesign
profile/base, expression-engine dependencies), capturing the owner's ``ElementMapVersion`` and
each entry's subname. ``audit_references(doc, snapshot)`` runs the Layer-0 validity sweep over
``isValid()``/``getStatusString()`` and returns a ``TnpAuditBlock``.

Capability-gated: when ``shim.element_map_available()`` is false every verdict is
``UNSUPPORTED`` and no reference reports ``PASS``. Stdlib + FreeCAD App API only; FreeCAD is
never imported here — the document and its objects are passed in.
"""

from __future__ import annotations

from typing import TypedDict

from freecad_buddy.contracts import RefFinding, TnpAuditBlock
from freecad_buddy.usecases import shim

# App/ElementNamingUtils.h: ELEMENT_MAP_PREFIX = ";" marks a mapped (new-style) element name,
# MISSING_PREFIX = "?" marks a subname whose element could not be resolved.
_MAPPED_PREFIX = ";"
_MISSING_PREFIX = "?"

# The C++ property class names of the two subelement-link property kinds. Every reference-holding
# subsystem funnels through one of them, so one strategy covers all four.
_LINK_SUB_TYPES = frozenset({"App::PropertyLinkSub", "App::PropertyLinkSubList"})
_EXPRESSION_ENGINE_TYPE = "App::PropertyExpressionEngine"


class RefEntry(TypedDict):
    mapped: str | None
    indexed: str | None
    missing: bool


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
    is marked ``missing`` so it is distinguishable from a healthy reference.
    """
    text = str(subname)
    missing = text.startswith(_MISSING_PREFIX)
    if missing:
        text = text[len(_MISSING_PREFIX) :]
    if not text.startswith(_MAPPED_PREFIX):
        return {"mapped": None, "indexed": text, "missing": missing}
    head, dot, tail = text.rpartition(".")
    if dot and tail:
        return {"mapped": head, "indexed": tail, "missing": missing}
    return {"mapped": text, "indexed": None, "missing": missing}


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
                "entries": [{"mapped": None, "indexed": str(expression), "missing": False}],
                "element_map_version": version,
            }
        )
    return records


def snapshot_references(doc: object) -> list[RefRecord]:
    """Return one ``RefRecord`` per subelement link and expression binding on ``doc``.

    Walks every object's ``PropertiesList``, selecting the properties whose
    ``getTypeIdOfProperty`` names a subelement-link or expression-engine property. Each record
    carries the owner ``Name``, the property name, the target object ``Name``, one entry per
    subname (split into its mapped/indexed halves) and the owner's ``ElementMapVersion``. A
    property that cannot be read is skipped, never raised.
    """
    records: list[RefRecord] = []
    for obj in sorted(doc.Objects, key=lambda o: o.Name):
        for prop in sorted(getattr(obj, "PropertiesList", None) or ()):
            try:
                type_id = obj.getTypeIdOfProperty(prop)
                value = getattr(obj, prop, None)
            except Exception:  # noqa: BLE001 - an unreadable property records no reference
                continue
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
                        "entries": [_split_subname(sub) for sub in subs],
                        "element_map_version": version,
                    }
                )
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


def audit_references(doc: object, snapshot: list[RefRecord]) -> TnpAuditBlock:
    """Audit ``doc``'s references against ``snapshot`` and return a ``TnpAuditBlock``.

    Runs the Layer-0 validity sweep: every object failing ``isValid()`` yields a ``BROKEN``
    finding carrying its ``getStatusString()``, and every reference now carrying an unresolved
    element marker yields a ``BROKEN`` finding too. ``status`` is ``UNSUPPORTED`` when
    ``shim.element_map_available()`` is false (no reference reports ``PASS`` in that case),
    ``FLAGGED`` when any finding is present, else ``CLEAN``. The validity sweep runs on both paths:
    an object that is broken outright is reportable without an element map. Call after
    mutate -> recompute.
    """
    version = _element_map_version_banner()
    findings = _invalid_object_findings(doc, snapshot) + _missing_element_findings(doc)

    if not shim.element_map_available():
        return {
            "status": "UNSUPPORTED",
            "element_map_version": version,
            "findings": findings + _unsupported_findings(snapshot),
        }

    return {
        "status": "FLAGGED" if findings else "CLEAN",
        "element_map_version": version,
        "findings": findings,
    }


def _missing_element_findings(doc: object) -> list[RefFinding]:
    """Return one ``BROKEN`` finding per reference whose element no longer resolves.

    Re-reads the live subelement links and reports every entry FreeCAD marked with the missing
    prefix, which an ``isValid()`` sweep alone does not surface.
    """
    findings: list[RefFinding] = []
    for record in snapshot_references(doc):
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
    raw = shim.element_map_version()
    return None if raw is None else str(raw)
