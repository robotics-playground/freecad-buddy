"""Single builder of the contracts ``ValidationReport`` from a criterion + stub outcome.

No report shape is invented here — the shape and verdict rule come from the contracts. The
stub outcome maps to a ``Check`` with ``detail.code = "invalid_input.not_implemented"``, which
``derive_verdict`` classifies as ``INVALID_INPUT`` — the honest "this criterion cannot be
evaluated: no bridge/tool exists yet" class (NOT ``RECOMPUTE_ERROR``: no recompute was
attempted, and criteria like G0.1/G0.2/G0.4 are not recompute checks at all).
"""

from __future__ import annotations

from freecad_buddy.contracts.report import (
    Check,
    ReportBanner,
    ValidationReport,
    derive_verdict,
)

# Honest "cannot evaluate" code. `invalid_input.` prefix -> INVALID_INPUT via
# derive_verdict.
STUB_NOT_IMPLEMENTED_CODE = "invalid_input.not_implemented"

# Honest "evidence absent" code for a criterion whose external evidence file never landed.
NOT_COLLECTED_CODE = "invalid_input.evidence_not_collected"


def stub_outcome() -> dict:
    """The structured "not implemented" a StubBridge returns for every tool call."""
    return {
        "implemented": False,
        "code": STUB_NOT_IMPLEMENTED_CODE,
        "message": "no bridge/tool implemented yet (Story 1.4/1.6)",
    }


def build_report(criterion: dict, outcome: dict) -> ValidationReport:
    """Build one schema-valid ``ValidationReport`` for ``criterion`` from a stub ``outcome``.

    ``element_map_version`` is ``None`` (schema: ``integer | null``), never the string
    ``"n/a"``. The verdict is derived, never asserted.
    """
    check: Check = {
        "id": criterion["id"],
        "measured": None,
        "expected": criterion.get("pass_rule"),
        # `is True` (not bool()): only a genuine boolean True flips this to passed — a stub
        # returning a truthy non-bool must not turn an honest fail green.
        "passed": outcome.get("implemented") is True,
        "detail": {
            "code": outcome.get("code", STUB_NOT_IMPLEMENTED_CODE),
            "message": outcome.get("message", "not implemented"),
        },
    }
    banner: ReportBanner = {
        "freecad_version": "stub",
        "element_map_version": None,
    }
    report: ValidationReport = {
        "schema": "fcb.validation-report/1",
        "banner": banner,
        "subject": {"criterion": criterion["id"], "gate": criterion.get("gate", "G0")},
        "checks": [check],
    }
    report["verdict"] = derive_verdict(report)
    return report


def evidence_report(criterion: str, checks: list, banner: dict | None = None) -> ValidationReport:
    """Assemble a ``ValidationReport`` for ``criterion`` from real measured ``checks``.

    The verdict is DERIVED from ``checks`` via ``derive_verdict`` — any incoming ``verdict``
    on a source artifact is ignored, so an evidence file can never self-grade. ``banner``
    defaults to a headless stub banner when the caller has no measured banner.
    """
    report_banner: ReportBanner = (
        dict(banner)
        if banner
        else {
            "freecad_version": "headless",
            "element_map_version": None,
        }
    )
    report_banner.setdefault("element_map_version", None)
    report: ValidationReport = {
        "schema": "fcb.validation-report/1",
        "banner": report_banner,
        "subject": {"criterion": criterion, "gate": "G0"},
        "checks": list(checks),
    }
    report["verdict"] = derive_verdict(report)
    return report


def not_collected_report(criterion: str, reason: str) -> ValidationReport:
    """A failing ``INVALID_INPUT`` report for a criterion whose evidence never landed."""
    check: Check = {
        "id": criterion,
        "measured": None,
        "expected": None,
        "passed": False,
        "detail": {"code": NOT_COLLECTED_CODE, "message": reason},
    }
    return evidence_report(criterion, [check])
