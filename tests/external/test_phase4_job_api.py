"""Phase 4 job API, deliverable re-check, and revisions (external / pytest, no FreeCAD).

Covers the I/O matrix rows in spec-5-4 that do not need a live document. The rows that DO need one
— a design job actually building a part — run under FreeCADCmd via `benchmarks/g4/run_parity.py`,
whose recorded result is asserted here rather than re-run, because this suite must stay
FreeCAD-free.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from freecad_buddy.hosts.phase4 import recheck, revision  # noqa: E402
from freecad_buddy.hosts.phase4.supervisor import Supervisor  # noqa: E402

PARITY_RESULTS = REPO_ROOT / "benchmarks" / "g4" / "parity-results.json"


def _revision(**overrides) -> dict:
    """A well-formed revision request, before overrides."""
    request = {
        "schema": "fcb.revision-request/1",
        "job_id": "rev-1",
        "base_job_id": "job-1",
        "changes": {"plate_thickness": 8.0},
        "scope": ["Plate"],
    }
    request.update(overrides)
    return request


def _diff(touched=(), new=(), deleted=()) -> dict:
    """A minimal ``GeometryDiff`` carrying only the fields the scope check reads."""
    return {
        "schema": "fcb.geometry-diff/1",
        "touched": list(touched),
        "new": list(new),
        "deleted": list(deleted),
    }


# --------------------------------------------------------------------------- #
# Revision validation — refuse before a worker binds
# --------------------------------------------------------------------------- #


def test_Should_accept_When_a_revision_names_a_completed_base_job():
    """The happy path, so the refusals below are not vacuously passing."""
    # Arrange
    known = {"job-1": {"state": "OK"}}

    # Act
    problem = revision.validate_request(_revision(), known)

    # Assert
    assert problem is None


def test_Should_refuse_When_the_base_job_never_ran():
    """There is no prior state to revise; running it would build a part from nothing."""
    # Arrange
    known: dict = {}

    # Act
    problem = revision.validate_request(_revision(), known)

    # Assert
    assert problem is not None and "no recorded result" in problem["message"]


def test_Should_refuse_When_a_revision_declares_no_scope():
    """Without a declared scope there is nothing for a change to be OUT of."""
    # Arrange
    known = {"job-1": {"state": "OK"}}

    # Act
    problem = revision.validate_request(_revision(scope=[]), known)

    # Assert
    assert problem is not None and "no scope" in problem["message"]


def test_Should_refuse_When_a_revision_requests_no_change():
    """A revision that changes nothing is not a revision."""
    # Arrange
    known = {"job-1": {"state": "OK"}}

    # Act
    problem = revision.validate_request(_revision(changes={}), known)

    # Assert
    assert problem is not None and "no change" in problem["message"]


def test_Should_resolve_INVALID_INPUT_When_the_supervisor_gets_an_unknown_base_job():
    """The refusal must surface as a closed-set status, not an exception."""
    # Arrange
    supervisor = Supervisor()

    # Act
    status = supervisor.submit_revision(_revision())

    # Assert
    assert status["state"] == "INVALID_INPUT"


def test_Should_accept_When_the_base_job_completed_through_the_supervisor():
    """A revision is admissible exactly when the job it names actually finished."""
    # Arrange
    from freecad_buddy.hosts.phase4.pool import JobRun
    from freecad_buddy.hosts.phase4.status_map import Outcome

    supervisor = Supervisor()
    supervisor.resolve(
        JobRun(spec={"job_id": "job-1"}, outcome=Outcome(returned=True, exit_code=0))
    )

    # Act
    status = supervisor.submit_revision(_revision())

    # Assert
    assert status["state"] == "QUEUED"


# --------------------------------------------------------------------------- #
# diff_scope — the G4.2 question
# --------------------------------------------------------------------------- #


def test_Should_pass_When_the_revision_touched_only_the_declared_scope():
    """A revision confined to what was asked is the criterion's passing case."""
    # Arrange
    diff = _diff(touched=["Plate"])

    # Act
    check = revision.check_diff_scope(diff, ["Plate"])

    # Assert
    assert check["passed"] is True


def test_Should_fail_When_the_revision_touched_a_feature_nobody_asked_about():
    """The G4.2 threat: a revision silently breaking an unrelated feature."""
    # Arrange
    diff = _diff(touched=["Plate", "MountingBoss"])

    # Act
    check = revision.check_diff_scope(diff, ["Plate"])

    # Assert
    assert check["passed"] is False
    assert check["detail"]["code"] == "revision.out_of_scope"
    assert "MountingBoss" in check["detail"]["objects"]


@pytest.mark.parametrize("field", ["new", "deleted"])
def test_Should_fail_When_the_revision_added_or_removed_an_object_outside_scope(field):
    """Adding or deleting outside the scope is as out-of-scope as modifying."""
    # Arrange
    diff = _diff(touched=["Plate"], **{field: ["Rib"]})

    # Act
    check = revision.check_diff_scope(diff, ["Plate"])

    # Assert
    assert check["passed"] is False
    assert "Rib" in check["detail"]["objects"]


def test_Should_fail_When_the_diff_reports_no_change_at_all():
    """A no-op must not clear the bar a real revision has to meet."""
    # Arrange
    diff = _diff()

    # Act
    check = revision.check_diff_scope(diff, ["Plate"])

    # Assert
    assert check["passed"] is False
    assert check["detail"]["code"] == "revision.no_change"


@pytest.mark.parametrize("bad", [None, "not-a-diff", 42, []])
def test_Should_fail_closed_When_the_diff_cannot_be_read(bad):
    """An unproven revision must never read as a confined one."""
    # Arrange
    scope = ["Plate"]

    # Act
    check = revision.check_diff_scope(bad, scope)

    # Assert
    assert check["passed"] is False


def test_Should_resolve_SPEC_FAILED_When_the_supervisor_grades_an_out_of_scope_revision():
    """The scope check is what decides the revision's status."""
    # Arrange
    supervisor = Supervisor()

    # Act
    status = supervisor.grade_revision(_revision(), _diff(touched=["Plate", "Other"]))

    # Assert
    assert status["state"] == "SPEC_FAILED"


# --------------------------------------------------------------------------- #
# Supervisor re-check — worker claims are hints
# --------------------------------------------------------------------------- #


def test_Should_re_derive_the_verdict_When_a_worker_claims_everything_passed():
    """`derive_verdict` is "derived, never asserted"; a worker's verdict is never echoed."""
    # Arrange
    worker_checks = [
        {"id": "geometry.volume", "passed": False, "detail": {"code": "spec.volume_mismatch"}},
    ]

    # Act
    report = recheck.build_report(worker_checks, [], banner={})

    # Assert
    assert report["verdict"] == "SPEC_FAILED"


def test_Should_refuse_When_a_check_claims_to_pass_while_carrying_a_failure_detail():
    """A self-contradicting check is the cheapest lie to tell and must not survive."""
    # Arrange
    worker_checks = [
        {"id": "geometry.volume", "passed": True, "detail": {"code": "spec.volume_mismatch"}},
    ]

    # Act
    checks = recheck.consistency_checks(worker_checks)

    # Assert
    assert checks[0]["passed"] is False
    assert checks[0]["detail"]["code"] == "report.inconsistent_claim"


@pytest.mark.parametrize("malformed", [None, "checks", 7, {"not": "a list"}])
def test_Should_refuse_When_the_checks_payload_is_not_a_list(malformed):
    """`derive_verdict` returns OK for a non-list, so the shape is validated before trusting it."""
    # Arrange
    banner: dict = {}

    # Act
    report = recheck.build_report(malformed, [], banner)

    # Assert
    assert report["verdict"] != "OK"


def test_Should_fail_When_an_export_the_worker_reported_is_not_on_disk(tmp_path):
    """A worker that crashed after claiming an export must not pass the deliverables check."""
    # Arrange
    entries = [
        {"fmt": "stl", "facts": {"path": str(tmp_path / "absent.stl"), "source": {"volume": 1.0}}}
    ]

    # Act
    checks = recheck.recheck_exports(entries)

    # Assert
    assert any(c["detail"]["code"] == "export.missing" for c in checks if c.get("detail"))


def test_Should_fail_When_an_export_entry_carries_no_usable_facts():
    """An unreadable claim is not a passing export."""
    # Arrange
    entries = [{"fmt": "stl", "facts": None}]

    # Act
    checks = recheck.recheck_exports(entries)

    # Assert
    assert checks[0]["passed"] is False


def test_Should_flag_When_the_workers_claimed_volume_disagrees_with_the_oracles(monkeypatch):
    """`assemble_export_verdict` grades a file AGAINST the worker's facts, so the claim itself
    has to be cross-checked or a lying worker earns a green verdict from a correct file."""
    # Arrange
    legs = [{"checks": [{"id": "stl.volume", "measured": 100.0, "passed": True}]}]
    facts = {"source": {"volume": 50.0}}

    # Act
    check = recheck._cross_check_facts("stl", facts, legs)

    # Assert
    assert check["passed"] is False
    assert check["detail"]["code"] == "export.claim_disagrees"


def test_Should_accept_When_the_claimed_volume_matches_what_the_oracles_measured():
    """Tessellation makes exact equality unavailable, so the check is a tolerance not equality."""
    # Arrange
    legs = [{"checks": [{"id": "stl.volume", "measured": 100.2, "passed": True}]}]
    facts = {"source": {"volume": 100.0}}

    # Act
    check = recheck._cross_check_facts("stl", facts, legs)

    # Assert
    assert check["passed"] is True


def test_Should_fail_When_there_is_no_independent_volume_to_compare_against():
    """A claim nothing can check is unverified, not verified."""
    # Arrange
    legs = [{"checks": []}]
    facts = {"source": {"volume": 100.0}}

    # Act
    check = recheck._cross_check_facts("stl", facts, legs)

    # Assert
    assert check["passed"] is False
    assert check["detail"]["code"] == "export.claim_unverifiable"


# --------------------------------------------------------------------------- #
# The recorded parity measurement
# --------------------------------------------------------------------------- #


def test_Should_record_what_the_parity_run_measured_When_the_artifact_is_read():
    """A bare rate will be read as the criterion it resembles, so the scope travels with it."""
    # Arrange
    assert PARITY_RESULTS.is_file(), "run benchmarks/g4/run_parity.py under FreeCADCmd first"

    # Act
    artifact = json.loads(PARITY_RESULTS.read_text(encoding="utf-8"))

    # Assert
    assert "not the G4.1 criterion" in artifact["scope"]
    assert "spec-to-plan translator exists" in artifact["scope"]


def test_Should_report_geometry_and_convergence_separately_When_parity_is_recorded():
    """Collapsing them would turn a measurable geometry result into an unmeasurable zero."""
    # Arrange
    artifact = json.loads(PARITY_RESULTS.read_text(encoding="utf-8"))

    # Act
    geometry_rate = artifact["geometry_rate"]
    converged_rate = artifact["converged_rate"]

    # Assert
    assert geometry_rate == 1.0, artifact
    assert converged_rate == 0.0, "the visual leg is unavailable on this branch"


def test_Should_name_why_convergence_is_zero_When_the_artifact_is_read():
    """A zero with no stated cause reads as a defect in the thing being measured."""
    # Arrange
    artifact = json.loads(PARITY_RESULTS.read_text(encoding="utf-8"))

    # Act
    visual_scope = artifact["visual_scope"]

    # Assert
    assert "no vision backend" in visual_scope
    assert "driving parameters" in visual_scope


def test_Should_drive_every_committed_plan_When_parity_runs():
    """A rate over a subset is not the rate it looks like."""
    # Arrange
    artifact = json.loads(PARITY_RESULTS.read_text(encoding="utf-8"))
    plans = list((REPO_ROOT / "benchmarks" / "g3" / "actor-plans").glob("*.json"))

    # Act
    total = artifact["total"]

    # Assert
    assert total == len(plans) == 20
