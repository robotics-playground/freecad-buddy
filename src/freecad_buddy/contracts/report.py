"""Validation report shape and the ``derive_verdict`` rule.

``derive_verdict`` is the one behavior-bearing helper here: it derives the terminal
verdict from a report's checks.
"""

from __future__ import annotations

from typing import Literal, TypedDict

from freecad_buddy.contracts.status import ErrorDetail, TerminalStatus


class WilsonCI(TypedDict):
    rate: float
    low: float
    high: float
    n: int
    r: int


class ReportBanner(TypedDict, total=False):
    freecad_version: str  # required
    element_map_version: int | None  # required; None ⇔ no element map
    validator_sensitivity: dict | None
    wilson_ci: WilsonCI | None


class Check(TypedDict, total=False):
    id: str
    measured: float | str | bool | list | None
    expected: float | str | bool | list | None
    tolerance: dict | None
    passed: bool  # required
    detail: ErrorDetail | None


class ValidationReport(TypedDict, total=False):
    schema: Literal["fcb.validation-report/1"]
    banner: ReportBanner  # required
    subject: dict
    checks: list[Check]  # required
    warnings: list[Check]
    verdict: TerminalStatus  # required; derived, never asserted


# Failure-class precedence (highest wins), independent of check order.
_PRECEDENCE: dict[TerminalStatus, int] = {
    "RECOMPUTE_ERROR": 3,
    "INVALID_INPUT": 2,
    "SPEC_FAILED": 1,
}


def _classify(check: dict) -> TerminalStatus:
    """Map a failed check to its failure class by ``detail.code``."""
    detail = check.get("detail")
    code = detail.get("code") if isinstance(detail, dict) else None
    if not isinstance(code, str):
        return "SPEC_FAILED"
    if code.startswith("recompute."):
        return "RECOMPUTE_ERROR"
    if code.startswith("invalid_input.") or code.endswith(".malformed"):
        return "INVALID_INPUT"
    return "SPEC_FAILED"


def derive_verdict(report: dict) -> TerminalStatus:
    """Derive the terminal verdict from a ValidationReport.

    ``OK`` iff every check passed. Otherwise scan ALL failed checks and keep the
    highest-precedence failure class (``RECOMPUTE_ERROR`` > ``INVALID_INPUT`` >
    ``SPEC_FAILED``) so the verdict is order-independent. Both the ``checks``
    container and each ``detail`` are read defensively — a non-list ``checks`` or an
    absent/non-dict ``detail`` degrades safely, never raises.
    """
    checks = report.get("checks")
    if not isinstance(checks, list):
        return "OK"

    worst: TerminalStatus | None = None
    for check in checks:
        passed = check.get("passed") if isinstance(check, dict) else None
        if passed is True:
            continue
        cls = _classify(check if isinstance(check, dict) else {})
        if worst is None or _PRECEDENCE[cls] > _PRECEDENCE[worst]:
            worst = cls

    return worst if worst is not None else "OK"
