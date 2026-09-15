"""Revisions: change one thing in a prior part, and prove nothing else changed.

The G4.2 criterion is not "did the revision work" — it is "did the geometry diff stay confined to
the requested change". Those are different questions, and only the second catches the failure the
gate plants: a revision that moves the dimension it was asked to move AND silently breaks a
feature nobody mentioned.

So a revision carries a DECLARED SCOPE and is graded against it. Without one there is nothing to
be out of, and "confined to the requested change" would reduce to whatever the result happened to
touch — a check that can never fail.

``diff_scope`` is the check this module exists to produce. It fails when the diff touches, adds or
deletes anything the request did not name, and it fails CLOSED: a diff it cannot read is an
unproven revision, not a passing one.
"""

from __future__ import annotations

from freecad_buddy.contracts.status import ErrorDetail

# The check id the G4 fault suite names. The `revision-diff` leg's cases declare
# `detected_by: diff_scope`, so this string is the contract between the suite and the checker.
DIFF_SCOPE_CHECK_ID = "diff_scope"


class RevisionInvalid(ValueError):
    """The revision request cannot be run as asked. Maps to ``INVALID_INPUT``."""


def validate_request(request: object, known_jobs) -> ErrorDetail | None:
    """Return the problem with ``request``, or ``None`` when it is runnable.

    A revision naming a base job that does not exist is refused BEFORE a worker binds: there is
    no prior state to revise, so running it would build a part from nothing and report it as a
    revision of something.

    :param request: the candidate ``RevisionRequest``.
    :param known_jobs: a container answering ``in`` for completed job ids.
    """
    if not isinstance(request, dict):
        return {
            "code": "revision.invalid_input",
            "message": f"revision request must be a mapping, got {type(request).__name__}",
        }
    for field in ("job_id", "base_job_id"):
        value = request.get(field)
        if not isinstance(value, str) or not value:
            return {"code": "revision.invalid_input", "message": f"revision carries no {field}"}
    if request["base_job_id"] not in known_jobs:
        return {
            "code": "revision.invalid_input",
            "message": f"base job {request['base_job_id']!r} has no recorded result to revise",
        }
    changes = request.get("changes")
    if not isinstance(changes, dict) or not changes:
        return {"code": "revision.invalid_input", "message": "revision requests no change"}
    scope = request.get("scope")
    if not isinstance(scope, list) or not scope:
        # An empty scope is refused rather than treated as "nothing may change". A revision that
        # may touch nothing cannot succeed, and silently accepting one would produce a failure
        # that looks like an out-of-scope violation.
        return {
            "code": "revision.invalid_input",
            "message": "revision declares no scope; there is nothing to grade the diff against",
        }
    return None


def check_diff_scope(diff: object, scope: list[str]) -> dict:
    """Grade a ``GeometryDiff`` against the declared ``scope``; return the ``diff_scope`` check.

    Every object the diff reports as touched, added or deleted must be named in ``scope``. One
    that is not is the out-of-scope change G4.2 exists to catch.

    Fails closed. A diff that is missing, malformed, or carries no object lists at all cannot show
    the change was confined, and an unproven revision must not read as a confined one.
    """
    if not isinstance(diff, dict):
        return _check(
            passed=False,
            measured=None,
            detail={
                "code": "revision.diff_unreadable",
                "message": f"no readable geometry diff to grade (got {type(diff).__name__})",
                "objects": [],
            },
        )

    declared = {str(name) for name in scope}
    changed: list[str] = []
    for field in ("touched", "new", "deleted"):
        entries = diff.get(field)
        if isinstance(entries, list):
            changed.extend(str(entry) for entry in entries)

    if not changed:
        # A diff reporting no change at all did not perform the revision. Passing it would let a
        # no-op revision clear the bar that a correct one has to meet.
        return _check(
            passed=False,
            measured=[],
            detail={
                "code": "revision.no_change",
                "message": "the diff reports no changed object, so the revision did nothing",
                "objects": [],
            },
        )

    outside = sorted(set(changed) - declared)
    if outside:
        return _check(
            passed=False,
            measured=outside,
            detail={
                "code": "revision.out_of_scope",
                "message": (
                    f"the revision changed {', '.join(outside)}, which the request did not name; "
                    f"declared scope was {', '.join(sorted(declared))}"
                ),
                "objects": outside,
            },
        )
    return _check(passed=True, measured=sorted(set(changed)), detail=None)


def _check(passed: bool, measured, detail) -> dict:
    """Build the ``diff_scope`` check in the shape every grader returns."""
    check = {
        "id": DIFF_SCOPE_CHECK_ID,
        "measured": measured,
        "measured_kind": "text",
        "expected": True,
        "tolerance": None,
        "passed": passed,
    }
    if detail is not None:
        check["detail"] = detail
    return check
