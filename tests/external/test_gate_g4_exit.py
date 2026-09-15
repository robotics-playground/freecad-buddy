"""Gate G4 entry-gate machinery (external / pytest, no FreeCAD).

Covers every I/O matrix row in spec-5-1:
  - the gate definition loads, and a criteria-less gate is an error rather than a green report;
  - the stub service's status vocabulary stays tied to the contract's closed set;
  - each outcome mapping (DETECTED / MISSED / PASS_CLEAN / FALSE_ALARM) over the real suite;
  - a case whose ``fault.kind`` disagrees with its ``expectation`` raising ``SuiteError``;
  - the ``not_scored`` branches, so an unmeasured validator never reports a fabricated ``0.0``;
  - the scorer and runner digests agreeing, without which every G4 row reads stale forever;
  - G4 staying out of the sealable/exit machinery that belongs to story 5.5.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
BENCHMARKS = REPO_ROOT / "benchmarks"
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(BENCHMARKS / "g4"))
sys.path.insert(0, str(BENCHMARKS / "g4" / "fault-injection"))

from benchmarks import runner  # noqa: E402

import drive_g4_faults  # noqa: E402  isort:skip
import score_g4_validators as scorer  # noqa: E402  isort:skip
import stub_service  # noqa: E402  isort:skip

from freecad_buddy.contracts.status import TerminalStatus  # noqa: E402

G4_ROOT = BENCHMARKS / "g4"


def _case(kind: str, planted_op: str | None = None, **overrides) -> dict:
    """A minimal in-memory case mapping, shaped like a loaded ``case.yaml``."""
    case = {
        "id": overrides.pop("id", "g4-fault-test-case"),
        "fault": {
            "kind": kind,
            "expectation": "DETECT" if kind == "planted_defect" else "PASS_CLEAN",
        },
        "fixture": "driven-by-job-service",
        "dir": G4_ROOT,
    }
    if planted_op:
        case["planted_op"] = planted_op
    case.update(overrides)
    return case


# --------------------------------------------------------------------------- #
# Gate definition
# --------------------------------------------------------------------------- #


def test_Should_load_five_criteria_When_the_G4_gate_is_read():
    """The runner READS the criteria; a gate it cannot load can never grade anything."""
    # Arrange
    gate = "G4"

    # Act
    criteria = runner._load_gate(gate)

    # Assert
    assert [c["id"] for c in criteria] == ["G4.1", "G4.2", "G4.3", "G4.4", "G4.5"]


def test_Should_raise_UsageError_When_a_gate_declares_no_criteria(tmp_path, monkeypatch):
    """Zero criteria must be an error, never a vacuously green report."""
    # Arrange
    empty = tmp_path / "g4"
    empty.mkdir()
    (empty / "gate.yaml").write_text("gate: G4\ncriteria: []\n", encoding="utf-8")
    monkeypatch.setattr(runner, "BENCHMARKS_ROOT", tmp_path)

    # Act
    def act():
        return runner._load_gate("G4")

    # Assert
    with pytest.raises(runner.UsageError):
        act()


def test_Should_declare_heldout_inert_When_G4_has_no_sealed_split():
    """A ``sealed`` declaration would engage leg-c against reports no exit run has produced."""
    # Arrange
    gate_def = runner._load_gate_def("G4")

    # Act
    heldout = gate_def.get("verdict", {}).get("heldout")

    # Assert
    assert heldout == "inert", gate_def.get("verdict")


def test_Should_stay_out_of_the_sealable_gates_When_the_exit_split_is_story_5_5s():
    """Sealing, exit evaluation and exit preconditions all belong to story 5.5, not 5.1."""
    # Arrange
    gate = "G4"

    # Act
    registered = (
        gate in runner._SEALABLE_GATES,
        gate in runner._EXIT_EVALUATORS,
        gate in runner._EXIT_PRECONDITIONS,
    )

    # Assert
    assert registered == (False, False, False)


def test_Should_route_the_faults_command_When_G4_declares_a_scorer():
    """``runner.py faults G4`` must reach the G4 scorer rather than falling through."""
    # Arrange
    gate = "G4"

    # Act
    scorer_path = runner._FAULT_SCORERS[gate]

    # Assert
    assert (REPO_ROOT / scorer_path).is_file(), scorer_path


# --------------------------------------------------------------------------- #
# Stub service contract
# --------------------------------------------------------------------------- #


def test_Should_lift_the_terminal_set_from_the_contract_When_the_stub_declares_it():
    """AD-17 keeps ONE source for the vocabulary; a retyped copy would drift silently."""
    # Arrange
    from typing import get_args

    # Act
    contract_statuses = frozenset(get_args(TerminalStatus))

    # Assert
    assert stub_service.TERMINAL_STATUSES == contract_statuses


def test_Should_map_every_canonical_fault_to_a_closed_set_status_When_the_stub_resolves_it():
    """A fault mapped outside the closed set could never be expressed on the wire."""
    # Arrange
    faults = stub_service.CANONICAL_FAULTS

    # Act
    mapped = set(faults.values())

    # Assert
    assert mapped <= stub_service.TERMINAL_STATUSES, mapped - stub_service.TERMINAL_STATUSES


def test_Should_refuse_a_real_submission_When_no_service_is_implemented():
    """Fail-closed keeps a green G4 impossible before the supervisor of stories 5.2-5.4 lands."""
    # Arrange
    spec = {"part": "anything"}

    # Act
    def act():
        return stub_service.submit(spec)

    # Assert
    with pytest.raises(stub_service.ServiceUnavailable):
        act()


def test_Should_refuse_a_status_outside_the_closed_set_When_it_is_validated():
    """Untrusted worker output is the seam's job to reject, not the caller's."""
    # Arrange
    status = {"job_id": "j1", "state": "MOSTLY_FINE", "detail": {"message": "x"}}

    # Act
    def act():
        return stub_service.validate_job_status(status)

    # Assert
    with pytest.raises(stub_service.JobStatusSchemaError, match="outside the closed set"):
        act()


def test_Should_refuse_a_non_terminal_state_When_it_is_validated_as_a_result():
    """A job still RUNNING is not a result; accepting it would report an unfinished job as done."""
    # Arrange
    status = {"job_id": "j1", "state": "RUNNING"}

    # Act
    def act():
        return stub_service.validate_job_status(status)

    # Assert
    with pytest.raises(stub_service.JobStatusSchemaError, match="not a terminal outcome"):
        act()


def test_Should_refuse_a_terminal_failure_When_it_carries_no_structured_detail():
    """AD-17's "none silent" rule is what G4.5 grades; a detail-less failure is that silence."""
    # Arrange
    status = {"job_id": "j1", "state": "WORKER_CRASHED"}

    # Act
    def act():
        return stub_service.validate_job_status(status)

    # Assert
    with pytest.raises(stub_service.JobStatusSchemaError, match="no structured detail"):
        act()


def test_Should_refuse_a_planted_op_outside_the_mapping_When_a_case_names_one():
    """A typo in a case file must not silently become a passing control."""
    # Arrange
    case = _case("planted_defect", planted_op="typo_not_a_fault")

    # Act
    def act():
        return stub_service.resolve(case)

    # Assert
    with pytest.raises(stub_service.JobStatusSchemaError, match="is not one of"):
        act()


# --------------------------------------------------------------------------- #
# Outcome mapping
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    ("planted_op", "expected_state"),
    sorted(stub_service.CANONICAL_FAULTS.items()),
)
def test_Should_resolve_to_the_declared_status_When_a_planted_fault_is_driven(
    planted_op, expected_state
):
    """The fault-to-status mapping is the entry gate's central claim, so it is asserted directly."""
    # Arrange
    case = _case("planted_defect", planted_op=planted_op)

    # Act
    outcome = drive_g4_faults.drive_case(case)

    # Assert
    assert outcome == "DETECTED", f"{planted_op} -> {expected_state}"


def test_Should_report_PASS_CLEAN_When_a_clean_control_is_driven():
    """A control the service resolves clean is the no-false-alarm arm of the measurement."""
    # Arrange
    case = _case("clean_control")

    # Act
    outcome = drive_g4_faults.drive_case(case)

    # Assert
    assert outcome == "PASS_CLEAN"


def test_Should_report_DETECTED_When_a_planted_failure_carries_no_detail():
    """The silent-failure defect is detected by the SHAPE refusal, not by a failure status."""
    # Arrange
    case = _case("planted_defect", planted_op="silent_terminal_failure")

    # Act
    outcome = drive_g4_faults.drive_case(case)

    # Assert
    assert outcome == "DETECTED"


def test_Should_report_MISSED_When_a_planted_fault_resolves_clean(monkeypatch):
    """A service that answers OK to a planted fault must score as a miss, never be excluded."""
    # Arrange
    monkeypatch.setattr(
        drive_g4_faults, "resolve", lambda _case: {"state": stub_service.CLEAN_STATUS}
    )
    case = _case("planted_defect", planted_op="infinite_loop")

    # Act
    outcome = drive_g4_faults.drive_case(case)

    # Assert
    assert outcome == "MISSED"


def test_Should_report_FALSE_ALARM_When_a_control_resolves_to_a_fault(monkeypatch):
    """A control flagged as a fault counts against the false-alarm bar."""
    # Arrange
    monkeypatch.setattr(drive_g4_faults, "resolve", lambda _case: {"state": "TIMEOUT"})
    case = _case("clean_control")

    # Act
    outcome = drive_g4_faults.drive_case(case)

    # Assert
    assert outcome == "FALSE_ALARM"


# --------------------------------------------------------------------------- #
# Suite integrity
# --------------------------------------------------------------------------- #


def test_Should_raise_SuiteError_When_a_case_kind_disagrees_with_its_expectation():
    """A mis-tagged case is silently mis-partitioned and both bars measure the wrong population."""
    # Arrange
    mistagged = _case("planted_defect", planted_op="infinite_loop")
    mistagged["fault"]["expectation"] = "PASS_CLEAN"

    # Act
    def act():
        return scorer._partition([mistagged])

    # Assert
    with pytest.raises(scorer.SuiteError, match="disagrees with"):
        act()


def test_Should_author_at_least_ten_cases_When_the_entry_gate_requires_a_suite():
    """phase-gates.md:3 requires a >=10-case fault-injection suite at the sensitivity bar."""
    # Arrange
    case_files = scorer._suite_case_files()

    # Act
    count = len(case_files)

    # Assert
    assert count >= 10, f"only {count} case(s) authored"


def test_Should_pair_every_planted_leg_with_a_control_When_the_suite_is_partitioned():
    """Without a control arm the false-alarm rate is vacuously 0 rather than measured."""
    # Arrange
    cases = [scorer._load_case(p) for p in scorer._suite_case_files()]

    # Act
    planted, controls = scorer._partition(cases)

    # Assert
    assert planted and controls, (len(planted), len(controls))


def test_Should_target_only_declared_validators_When_every_case_is_read():
    """A case naming an undeclared validator would be scored into a registry row nothing backs."""
    # Arrange
    cases = [scorer._load_case(p) for p in scorer._suite_case_files()]

    # Act
    targeted = {scorer._validator_name(case) for case in cases}

    # Assert
    assert targeted <= set(scorer.VALIDATOR_SOURCES), targeted - set(scorer.VALIDATOR_SOURCES)


def test_Should_cite_only_scored_validators_When_the_gate_declares_its_criteria():
    """A criterion citing a validator with no row reports "not in registry" at leg-b."""
    # Arrange
    gate_def = runner._load_gate_def("G4")

    # Act
    cited = {v for c in gate_def["criteria"] for v in c.get("cited_validators", [])}

    # Assert
    assert cited <= set(scorer.VALIDATOR_SOURCES), cited - set(scorer.VALIDATOR_SOURCES)


# --------------------------------------------------------------------------- #
# not_scored — never a fabricated zero
# --------------------------------------------------------------------------- #


def test_Should_report_not_scored_When_a_validator_has_no_case_at_all():
    """An absent suite is an unauthored measurement, not a validator that missed everything."""
    # Arrange
    name = "job_lifecycle"

    # Act
    result = scorer.score_validator(name, [])

    # Assert
    assert result["not_scored"] and "no fault case targets" in result["not_scored"]


def test_Should_report_not_scored_When_every_case_declares_a_pending_fixture():
    """An undriven defect says nothing about sensitivity, so it scores nothing rather than zero."""
    # Arrange
    pending = [
        _case("planted_defect", planted_op="infinite_loop", fixture="pending", id="a"),
        _case("clean_control", fixture="pending", id="b"),
    ]

    # Act
    result = scorer.score_validator("job_lifecycle", pending)

    # Assert
    assert result["not_scored"] and "no driveable case" in result["not_scored"]


def test_Should_report_not_scored_When_a_driveable_case_carries_no_measured_outcome(monkeypatch):
    """Counting an undriven case as a miss would blame the validator for a run nobody made."""
    # Arrange
    monkeypatch.setattr(scorer, "_driven_results", lambda _name: {"rows": [], "skipped": []})
    cases = [
        _case("planted_defect", planted_op="infinite_loop", id="ungraded-planted"),
        _case("clean_control", id="ungraded-control"),
    ]

    # Act
    result = scorer.score_validator("job_lifecycle", cases)

    # Assert
    assert result["not_scored"] and "no measured outcome" in result["not_scored"]


def test_Should_never_fabricate_a_zero_When_sensitivity_is_unmeasured(monkeypatch):
    """The whole point of ``not_scored``: an unmeasured bar must not read as a measured failure.

    The control is GRADED here so the ungraded branch cannot fire first; what is missing is the
    planted arm, which is the condition that would otherwise report ``sensitivity: 0.0`` over an
    empty population.
    """
    # Arrange
    monkeypatch.setattr(
        scorer,
        "_driven_results",
        lambda _name: {"rows": [{"id": "only-control", "outcome": "PASS_CLEAN"}], "skipped": []},
    )
    controls_only = [_case("clean_control", id="only-control")]

    # Act
    result = scorer.score_validator("job_lifecycle", controls_only)

    # Assert
    assert result["not_scored"] and "sensitivity is unmeasured rather than zero" in (
        result["not_scored"]
    )
    assert result["sensitivity"] == 0.0 and result["driveable_planted"] == 0


# --------------------------------------------------------------------------- #
# Digest agreement and measured bars
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("name", sorted(scorer.VALIDATOR_SOURCES))
def test_Should_agree_with_the_runner_digest_When_a_validator_sha_is_computed(name):
    """A disagreement here makes every G4 row read stale forever on a clean working tree."""
    # Arrange
    scorer_sha = scorer._validator_sha(name)

    # Act
    runner_sha = runner._validator_src_hasher(name)

    # Assert
    assert scorer_sha == runner_sha != "", (scorer_sha, runner_sha)


@pytest.mark.parametrize("name", sorted(scorer.VALIDATOR_SOURCES))
def test_Should_meet_the_entry_gate_bars_When_the_suite_is_scored_against_the_stub(name):
    """G4.E requires >=95% of planted faults caught with <=5% false alarms."""
    # Arrange
    results = scorer.score()

    # Act
    result = results[name]

    # Assert
    assert result["not_scored"] is None, result["not_scored"]
    assert result["sensitivity"] >= scorer.SENSITIVITY_BAR, result
    assert result["false_alarm"] <= scorer.FALSE_ALARM_BAR, result


def test_Should_record_the_stub_provenance_When_a_row_is_scored():
    """A bar measured against a stub must say so, or the row reads as a service result."""
    # Arrange
    results = scorer.score()

    # Act
    row = results["soak_status"]

    # Assert
    assert "stub_service.py" in row.get("graded_by", "")
    assert "NOT a service measurement" in row.get("independence_caveat", "")


def test_Should_leave_the_registry_unwritten_When_the_scorer_runs_with_check(tmp_path, monkeypatch):
    """``--check`` lets CI verify the suite's structure while the working tree stays clean."""
    # Arrange
    untouched = tmp_path / "validators.yaml"
    untouched.write_text("sentinel: true\n", encoding="utf-8")
    monkeypatch.setattr(scorer, "VALIDATORS_YAML", untouched)

    # Act
    code = scorer.main(["--check"])

    # Assert
    assert code == 0
    assert untouched.read_text(encoding="utf-8") == "sentinel: true\n"


def test_Should_carry_a_wilson_interval_When_a_rate_is_reported():
    """A rate over a short n reads as authoritative unless its interval travels beside it."""
    # Arrange
    results = scorer.score()

    # Act
    wilson = results["soak_status"]["wilson_ci"]

    # Assert
    assert set(wilson) >= {"rate", "low", "high", "n", "r"}, wilson
    assert wilson["low"] < wilson["high"], wilson


# --------------------------------------------------------------------------- #
# The entry-gate property
# --------------------------------------------------------------------------- #


def test_Should_declare_every_canonical_fault_When_the_suite_is_authored():
    """The four canonical G4.E faults plus the fault-tested revision checker must all be planted."""
    # Arrange
    cases = [scorer._load_case(p) for p in scorer._suite_case_files()]

    # Act
    planted_ops = {c.get("planted_op") for c in cases if c.get("planted_op")}

    # Assert
    required = {
        "infinite_loop",
        "unbounded_alloc",
        "occt_segfault",
        "wrong_part_clean_report",
        "unrelated_feature_changed",
    }
    assert required <= planted_ops, required - planted_ops


def test_Should_name_a_real_leg_When_a_planted_fault_declares_one():
    """A case file and the fault it plants must not drift apart unnoticed."""
    # Arrange
    cases = [scorer._load_case(p) for p in scorer._suite_case_files()]

    # Act
    mismatched = [
        c["id"]
        for c in cases
        if c.get("planted_op")
        and stub_service.LEG_BY_FAULT.get(c["planted_op"]) != c["dir"].parent.name
    ]

    # Assert
    assert mismatched == [], mismatched


def test_Should_mirror_the_phase_gate_table_When_the_gate_declares_its_criteria():
    """The gate.yaml is a declarative MIRROR; a criterion the table lacks grades nothing."""
    # Arrange
    gates_doc = REPO_ROOT / "_bmad-output" / "specs" / "spec-freecad-buddy" / "phase-gates.md"
    table = gates_doc.read_text(encoding="utf-8")

    # Act
    criteria = yaml.safe_load((G4_ROOT / "gate.yaml").read_text(encoding="utf-8"))["criteria"]

    # Assert
    for criterion in criteria:
        assert f"| {criterion['id']} |" in table, criterion["id"]
