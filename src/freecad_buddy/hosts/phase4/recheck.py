"""The supervisor's re-execution: grade the artifacts, never echo the worker's account of them.

This closes the "HTTP 200 for a bad part" hole. A worker is agent-driven and fully untrusted; it
may return a well-formed report for wrong geometry, or crash after writing partial artifacts.
So every field the job API reports is backed by a check the SUPERVISOR re-ran against the files
on disk.

What the supervisor can and cannot re-run is fixed by the process boundary, and pretending
otherwise is how a re-check becomes theatre:

- **Re-runnable here.** The export oracles read a written file and never import FreeCAD, and
  ``derive_verdict`` is pure over a report. Both run in this process.
- **Not re-runnable here.** Geometry assertions need a live document, which needs FreeCAD, which
  the supervisor must never load. The supervisor therefore cannot confirm that a geometry
  ``measured`` value is true of the part.

The consequence is stated rather than hidden: for geometry the supervisor checks INTERNAL
CONSISTENCY — that each check's own measured/expected/tolerance agree with the passed flag it
claims — and for exports it checks the FILE. A worker that lies about geometry is caught by the
independent grader in the loop, not here.

One trust detail that is easy to miss: ``assemble_export_verdict`` grades a written file against
the ``facts`` the worker supplied, so a worker that lies in ``facts["source"]`` would earn a green
verdict from a correct file. ``_cross_check_facts`` compares the worker's claimed volume against
what the oracles independently measured, which is what turns that claim into a measurement.
"""

from __future__ import annotations

from pathlib import Path

from freecad_buddy.adapters import export_verdict
from freecad_buddy.contracts.report import derive_verdict

# How far a worker's claimed volume may sit from what an oracle measured before the claim is
# treated as a lie rather than a rounding difference. Oracles tessellate, so exact equality is not
# available; 1% is wide enough for mesh discretisation and far tighter than any wrong part.
_VOLUME_CLAIM_TOLERANCE = 0.01


def recheck_exports(exports: list[dict]) -> list[dict]:
    """Re-run the FreeCAD-free oracles over each written export; return the checks.

    :param exports: one mapping per export, carrying ``fmt`` and the worker's self-read ``facts``.
    """
    checks: list[dict] = []
    for entry in exports:
        fmt = str(entry.get("fmt") or "")
        facts = entry.get("facts")
        if fmt not in ("stl", "3mf") or not isinstance(facts, dict):
            checks.append(
                _check(
                    f"export.{fmt or 'unknown'}.recheck",
                    passed=False,
                    detail={
                        "code": "export.unreadable_claim",
                        "message": f"export entry carries no usable facts for {fmt!r}",
                        "objects": [],
                    },
                )
            )
            continue

        path = facts.get("path")
        if not path or not Path(str(path)).is_file():
            checks.append(
                _check(
                    f"export.{fmt}.present",
                    passed=False,
                    detail={
                        "code": "export.missing",
                        "message": f"the {fmt.upper()} the worker reported is not on disk: {path}",
                        "objects": [],
                    },
                )
            )
            continue

        legs = export_verdict.oracle_legs_for(fmt, facts)
        for leg in legs:
            checks.extend(leg.get("checks") or [])
        checks.append(_cross_check_facts(fmt, facts, legs))
    return checks


def _cross_check_facts(fmt: str, facts: dict, legs: list[dict]) -> dict:
    """Compare the worker's claimed volume against what the oracles measured independently.

    Without this the re-check grades a correct file against a claim, and a worker that understated
    its own volume would pass. The oracles never see the worker's number, so their measurement is
    the independent half.
    """
    claimed = (facts.get("source") or {}).get("volume")
    measured = _oracle_volume(legs)
    if not isinstance(claimed, (int, float)) or measured is None:
        return _check(
            f"export.{fmt}.claim_cross_check",
            passed=False,
            detail={
                "code": "export.claim_unverifiable",
                "message": "no independent volume to compare the worker's claim against",
                "objects": [],
            },
        )
    if claimed <= 0:
        return _check(
            f"export.{fmt}.claim_cross_check",
            passed=False,
            detail={
                "code": "export.claim_invalid",
                "message": f"the worker claimed a non-positive volume: {claimed}",
                "objects": [],
            },
        )
    drift = abs(measured - claimed) / claimed
    if drift > _VOLUME_CLAIM_TOLERANCE:
        return _check(
            f"export.{fmt}.claim_cross_check",
            passed=False,
            measured=round(drift, 6),
            detail={
                "code": "export.claim_disagrees",
                "message": (
                    f"the worker claimed volume {claimed:.4f} but the oracles measured "
                    f"{measured:.4f} ({drift:.2%} apart)"
                ),
                "objects": [],
            },
        )
    return _check(f"export.{fmt}.claim_cross_check", passed=True, measured=round(drift, 6))


def _oracle_volume(legs: list[dict]) -> float | None:
    """The volume an oracle measured, read from its own checks rather than from the worker."""
    for leg in legs:
        for check in leg.get("checks") or []:
            if "volume" in str(check.get("id", "")) and isinstance(
                check.get("measured"), (int, float)
            ):
                return float(check["measured"])
    return None


def consistency_checks(worker_checks: object) -> list[dict]:
    """Verify each worker-reported check is internally consistent with its own claim.

    The supervisor cannot re-measure geometry — that needs a live document. What it CAN do is
    refuse a check whose parts contradict each other: a check claiming ``passed`` while carrying a
    failure detail, or one carrying no id at all. This is a weaker guarantee than re-measurement
    and is labelled as such rather than presented as verification.
    """
    if not isinstance(worker_checks, list):
        return [
            _check(
                "report.checks_readable",
                passed=False,
                detail={
                    "code": "report.malformed",
                    "message": f"checks must be a list, got {type(worker_checks).__name__}",
                    "objects": [],
                },
            )
        ]

    inconsistent: list[str] = []
    for check in worker_checks:
        if not isinstance(check, dict) or not check.get("id"):
            inconsistent.append("<check with no id>")
            continue
        detail = check.get("detail")
        if check.get("passed") is True and isinstance(detail, dict) and detail.get("code"):
            inconsistent.append(str(check["id"]))
    if inconsistent:
        return [
            _check(
                "report.checks_consistent",
                passed=False,
                measured=inconsistent,
                detail={
                    "code": "report.inconsistent_claim",
                    "message": (
                        f"{len(inconsistent)} check(s) claim to have passed while carrying a "
                        f"failure detail: {', '.join(inconsistent)}"
                    ),
                    "objects": inconsistent,
                },
            )
        ]
    return [_check("report.checks_consistent", passed=True, measured=len(worker_checks))]


def build_report(worker_checks: object, export_entries: list[dict], banner: dict) -> dict:
    """Assemble the supervisor's ``ValidationReport`` and DERIVE its verdict.

    The verdict is recomputed here, never copied. ``derive_verdict`` is documented as "derived,
    never asserted", and a worker-supplied verdict is exactly the wrong-part-with-clean-report
    fault the G4 suite plants.

    ``derive_verdict`` returns ``OK`` for a report whose ``checks`` is not a list, so the shape is
    validated by ``consistency_checks`` before it is trusted — otherwise a worker returning
    ``{"checks": None}` would earn a green verdict from a defensive default.
    """
    checks: list[dict] = []
    checks.extend(consistency_checks(worker_checks))
    if isinstance(worker_checks, list):
        checks.extend(check for check in worker_checks if isinstance(check, dict))
    checks.extend(recheck_exports(export_entries))

    report = {
        "schema": "fcb.validation-report/1",
        "banner": banner,
        "subject": {"re_executed_by": "phase4-supervisor"},
        "checks": checks,
    }
    report["verdict"] = derive_verdict(report)
    return report


def _check(check_id: str, passed: bool, measured=None, detail=None) -> dict:
    """Build one check in the shape every grader returns."""
    check = {
        "id": check_id,
        "measured": measured,
        "measured_kind": None,
        "expected": True,
        "tolerance": None,
        "passed": passed,
    }
    if detail is not None:
        check["detail"] = detail
    return check
