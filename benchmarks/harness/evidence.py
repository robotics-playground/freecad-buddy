"""Per-criterion evidence collectors (FreeCAD-free, contracts-only).

Each collector produces one contracts ``ValidationReport`` whose verdict is DERIVED from
measured checks via ``report_build.evidence_report`` — never a stored/asserted verdict. A
collector that cannot measure its criterion (absent/malformed/empty-checks evidence) returns a
failing ``INVALID_INPUT`` report, never a fabricated pass (AD-13).
"""

from __future__ import annotations

import json
from pathlib import Path

from benchmarks.harness.report_build import evidence_report, not_collected_report
from freecad_buddy.contracts.report import Check, ValidationReport

# The three namespaces the G0.2 count is drawn from. Out-of-namespace tools (verify_/sketch_)
# do NOT count toward the >=15 bar.
_G0_2_NAMESPACES = ("query_", "document_", "export_")
_G0_2_MIN_TOOLS = 15


def collect_g0_2(tool_specs: list) -> ValidationReport:
    """Introspect the tool catalog into a G0.2 report — headless, no FreeCAD.

    The >=15 count is of tools whose ``.name`` is IN the query_/document_/export_ namespaces
    (out-of-namespace tools do NOT count). Every counted spec must carry an ``input_schema``
    object plus a non-empty description. A non-string ``.name`` is treated as malformed (it
    fails the schema/name check) and never raises.
    """
    in_namespace = 0
    malformed: list[str] = []
    for spec in tool_specs:
        name = getattr(spec, "name", None)
        if not isinstance(name, str):
            malformed.append(repr(name))
            continue
        if not name.startswith(_G0_2_NAMESPACES):
            continue
        in_namespace += 1
        schema = getattr(spec, "input_schema", None)
        description = getattr(spec, "description", None)
        if not isinstance(schema, dict):
            malformed.append(name)
        elif not (isinstance(description, str) and description.strip()):
            malformed.append(name)

    count_check: Check = {
        "id": "G0.2.count",
        "measured": in_namespace,
        "expected": f">={_G0_2_MIN_TOOLS}",
        "passed": in_namespace >= _G0_2_MIN_TOOLS,
        "detail": {
            "code": "invalid_input.tool_count" if in_namespace < _G0_2_MIN_TOOLS else "ok",
            "message": (
                f"{in_namespace} tools in {'/'.join(_G0_2_NAMESPACES)} (need >={_G0_2_MIN_TOOLS})"
            ),
        },
    }
    schema_check: Check = {
        "id": "G0.2.schema",
        "measured": sorted(malformed),
        "expected": [],
        "passed": not malformed,
        "detail": {
            "code": "invalid_input.tool_schema.malformed" if malformed else "ok",
            "message": (
                f"malformed tool specs: {sorted(malformed)}" if malformed else "all specs valid"
            ),
        },
    }
    return evidence_report("G0.2", [count_check, schema_check])


def ingest_report(criterion: str, path: Path) -> ValidationReport:
    """Parse + shape-validate a dropped evidence report JSON and RE-DERIVE its verdict.

    The stored ``verdict`` is dropped; the returned report's verdict is derived from the
    file's ``checks`` via ``evidence_report`` so an ingested file can never self-grade. A
    missing/unparseable file, a non-mapping body, or an empty/non-list ``checks`` yields a
    failing ``INVALID_INPUT`` report — never a fabricated pass.
    """
    if not path.is_file():
        return not_collected_report(criterion, f"evidence not collected: {path.name} absent")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return not_collected_report(
            criterion, f"evidence malformed: {path.name} ({exc.__class__.__name__})"
        )
    if not isinstance(data, dict):
        return not_collected_report(criterion, f"evidence malformed: {path.name} not a mapping")
    checks = data.get("checks")
    if not isinstance(checks, list) or not checks:
        return not_collected_report(
            criterion, f"evidence malformed: {path.name} has empty/non-list checks"
        )
    banner = data.get("banner") if isinstance(data.get("banner"), dict) else None
    return evidence_report(criterion, checks, banner)
