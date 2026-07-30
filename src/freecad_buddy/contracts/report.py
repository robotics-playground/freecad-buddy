"""Validation report shape, the ``derive_verdict`` rule, and the rate/CI guard.

``derive_verdict`` derives the terminal verdict from a report's checks.
``require_wilson_ci_for_rates`` raises when a check declares a rate but the banner
carries no complete ``WilsonCI``.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any, Literal, TypedDict, get_args, get_type_hints

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


MeasuredKind = Literal["rate", "quantity", "count", "flag", "text"]


class Check(TypedDict, total=False):
    id: str
    measured: float | str | bool | list | None
    measured_kind: MeasuredKind | None  # None ⇔ kind not declared
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


_MEASURED_KINDS: frozenset[str] = frozenset(get_args(MeasuredKind))
_WILSON_CI_KEYS: frozenset[str] = frozenset(WilsonCI.__required_keys__)
_WILSON_CI_INT_KEYS: frozenset[str] = frozenset(
    key for key, tp in get_type_hints(WilsonCI).items() if tp is int and key in _WILSON_CI_KEYS
)


def _check_label(check: Mapping) -> str:
    """Return a check's ``id`` for messages, or ``"<unnamed>"`` when it has none."""
    check_id = check.get("id")
    return check_id if isinstance(check_id, str) else "<unnamed>"


def _rate_check_ids(report: Mapping) -> list[str]:
    """Collect the ids of checks whose ``measured_kind`` is ``"rate"``.

    Reads ``checks`` and ``warnings`` defensively: a container that is not a
    non-string sequence, or an entry that is not a mapping, is skipped rather than
    raising. An entry without an ``id`` reports as ``"<unnamed>"``; ids are
    de-duplicated in first-seen order.

    :raises ValueError: An entry declares a ``measured_kind`` that is neither
        ``None`` nor a ``MeasuredKind`` member.
    """
    ids: list[str] = []
    for key in ("checks", "warnings"):
        container = report.get(key)
        if not isinstance(container, Sequence) or isinstance(container, str | bytes):
            continue
        for check in container:
            if not isinstance(check, Mapping):
                continue
            kind = check.get("measured_kind")
            if kind is None:
                continue
            if not isinstance(kind, str) or kind not in _MEASURED_KINDS:
                raise ValueError(
                    f"unknown measured_kind {kind!r} on check "
                    f"'{_check_label(check)}'; expected one of "
                    f"{sorted(_MEASURED_KINDS)} or None"
                )
            if kind == "rate":
                ids.append(_check_label(check))
    return list(dict.fromkeys(ids))


def _mistyped_wilson_ci_keys(wilson_ci: Mapping) -> list[str]:
    """Return the ``WilsonCI`` keys whose value is not of the declared type.

    ``n`` and ``r`` accept an integral ``float`` (``30.0``), matching JSON Schema's
    ``integer``. ``bool`` is rejected everywhere.
    """
    bad: list[str] = []
    for key in sorted(_WILSON_CI_KEYS):
        value = wilson_ci[key]
        if isinstance(value, bool) or not isinstance(value, int | float):
            bad.append(key)
            continue
        if key in _WILSON_CI_INT_KEYS and isinstance(value, float) and not value.is_integer():
            bad.append(key)
    return bad


def _incoherent_wilson_ci(wilson_ci: Mapping) -> str | None:
    """Return why ``wilson_ci`` cannot describe a real interval, or ``None`` when it can.

    Assumes every key is present and numeric. Rejects non-finite values, proportions
    outside ``[0, 1]``, a bound ordering other than ``low <= rate <= high``, a negative
    or zero trial count, and a success count outside ``0 <= r <= n``.
    """
    proportions = {key: float(wilson_ci[key]) for key in ("rate", "low", "high")}
    counts = {key: float(wilson_ci[key]) for key in ("n", "r")}

    for key, value in (*proportions.items(), *counts.items()):
        if value != value or value in (float("inf"), float("-inf")):
            return f"{key} is not finite"
    for key, value in proportions.items():
        if not 0.0 <= value <= 1.0:
            return f"{key} is outside [0, 1]"
    if not proportions["low"] <= proportions["rate"] <= proportions["high"]:
        return "bounds are not ordered low <= rate <= high"
    if counts["n"] <= 0:
        return "n is not a positive trial count"
    if not 0.0 <= counts["r"] <= counts["n"]:
        return "r is outside [0, n]"
    return None


def require_wilson_ci_for_rates(report: Any) -> None:
    """Raise when a rate-measuring check is present without ``banner.wilson_ci``.

    A check declares its ``measured`` value to be a rate by setting
    ``measured_kind`` to ``"rate"``; ``checks`` and ``warnings`` are both scanned.
    The CI must carry every ``WilsonCI`` key with a value of the declared numeric
    type. Returns ``None`` when no rate check exists, when ``banner.wilson_ci`` is
    a complete interval, or when ``report`` is not a mapping.

    :param report: ValidationReport-shaped mapping.
    :raises ValueError: A rate check is present and ``banner.wilson_ci`` is
        absent, ``None``, not a mapping, carries a missing or mistyped key, or
        cannot describe a real interval (non-finite, a proportion outside
        ``[0, 1]``, bounds not ordered ``low <= rate <= high``, ``n`` not
        positive, or ``r`` outside ``[0, n]``) — the message names the offending
        check ids — or a check declares a ``measured_kind`` outside
        ``MeasuredKind``.
    """
    if not isinstance(report, Mapping):
        return

    rate_ids = _rate_check_ids(report)
    if not rate_ids:
        return

    banner = report.get("banner")
    wilson_ci = banner.get("wilson_ci") if isinstance(banner, Mapping) else None
    if not isinstance(wilson_ci, Mapping):
        raise ValueError(
            "banner.wilson_ci is required when a check measures a rate; "
            f"offending check id(s): {rate_ids}"
        )

    absent = sorted(_WILSON_CI_KEYS - set(wilson_ci))
    if absent:
        raise ValueError(
            f"banner.wilson_ci is missing key(s) {absent} but a check measures a "
            f"rate; offending check id(s): {rate_ids}"
        )

    mistyped = _mistyped_wilson_ci_keys(wilson_ci)
    if mistyped:
        raise ValueError(
            f"banner.wilson_ci has non-numeric key(s) {mistyped} but a check "
            f"measures a rate; offending check id(s): {rate_ids}"
        )

    incoherent = _incoherent_wilson_ci(wilson_ci)
    if incoherent:
        raise ValueError(
            f"banner.wilson_ci {incoherent} but a check measures a rate; "
            f"offending check id(s): {rate_ids}"
        )
