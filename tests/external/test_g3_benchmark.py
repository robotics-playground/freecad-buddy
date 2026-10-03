"""Structural self-check for the G3 entry gate: spec set, corrupted-plan suite, threat counters.

Covers every I/O matrix row of Story 4.1 that needs no live FreeCAD document: the stub run, a
banned selector, an unknown assertion fn, an orphan fault case, a threat with no counter, a plan
step outside the tool catalog or its input schema, a missing or misplaced planted step, and an
exit attempt. The mutation rows run the scorer over a deep copy of the real suite with one defect
planted, so each proves the check can fail rather than only that the real tree passes.
"""

from __future__ import annotations

import copy
import hashlib
import json
import shutil
import sys
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
BENCHMARKS = REPO_ROOT / "benchmarks"
G3 = BENCHMARKS / "g3"
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "scripts"))
sys.path.insert(0, str(G3 / "fault-injection"))

import check_provenance  # noqa: E402
import score_g3_validators as scorer  # noqa: E402

from benchmarks import runner  # noqa: E402
from freecad_buddy.contracts import ANCHOR_FRAME_KINDS, ASSERTION_FNS  # noqa: E402
from freecad_buddy.contracts.report import derive_verdict  # noqa: E402
from freecad_buddy.usecases import assertions as primitives  # noqa: E402
from freecad_buddy.usecases.documents import ValidationError  # noqa: E402

SUITE = scorer.load_suite()
TOOLS = scorer.tool_schemas()
BASELINE = scorer.check_suite(SUITE, TOOLS)

# Paths of the reverted bb42999 implementation that this gate must never bring back (AD-35):
# the must-not-restore list plus everything benchmarks/g3/reuse-survey.md marks Rejected.
MUST_NOT_RESTORE = (
    "src/freecad_buddy/usecases/designer_loop.py",
    "src/freecad_buddy/usecases/verify_visual.py",
    "src/freecad_buddy/contracts/designer.py",
    "src/freecad_buddy/contracts/visual.py",
    "src/freecad_buddy/contracts/jsonschema/designer-run.schema.json",
    "src/freecad_buddy/contracts/jsonschema/judge-verdict.schema.json",
    "src/freecad_buddy/adapters/visual_judge_client.py",
    "benchmarks/harness/judge_double.py",
    "benchmarks/g3/judge.py",
    "benchmarks/g3/actor_run.py",
    "benchmarks/g3/make_actor_plans.py",
    "benchmarks/g3/actor-plans",
    "benchmarks/g3/actor-results.json",
    "benchmarks/g3/fault-injection/planted_plans.py",
    "benchmarks/g3/fault-injection/score_g3_infc.py",
    "benchmarks/g3/fault-injection/visual-judge",
    "benchmarks/g3/fault-injection/render_visual_judge.py",
    "benchmarks/g3/fault-injection/visual_parts.py",
    "benchmarks/g3/fault-injection/assertions",
    "benchmarks/g3/fault-injection/recompute",
    "benchmarks/g3/fault-injection/planted_recomputes.py",
    "benchmarks/g3/fault-injection/score_recompute_infc.py",
    "benchmarks/g3/fault-injection/corrupted_plan.json",
    "benchmarks/g3/fault-injection/g3_assertions.json",
    "benchmarks/g3/fault-injection/verify_recompute.json",
    "benchmarks/g3/fault-injection/visual_judge.json",
)


def _mutated() -> dict:
    """A deep copy of the real suite that a test may plant one defect in."""
    return copy.deepcopy(SUITE)


def _by_id(cases: list[dict], case_id: str) -> dict:
    return next(case for case in cases if case["id"] == case_id)


def _failing(results: dict[str, list[str]]) -> dict[str, list[str]]:
    return {name: problems for name, problems in results.items() if problems}


def _benchmarks_copy(tmp_path: Path) -> Path:
    copy_root = tmp_path / "benchmarks"
    shutil.copytree(
        BENCHMARKS, copy_root, ignore=shutil.ignore_patterns("gate-artifacts", "__pycache__")
    )
    return copy_root


# --------------------------------------------------------------------------- #
# The real tree
# --------------------------------------------------------------------------- #


def test_should_report_no_problem_when_the_real_suite_is_checked():
    # Arrange
    suite = SUITE

    # Act
    results = scorer.check_suite(suite, TOOLS)

    # Assert
    assert _failing(results) == {}


def test_should_hold_twenty_specs_ten_planted_plans_controls_and_four_threats_when_loaded():
    # Arrange
    plans = SUITE["plans"]

    # Act
    planted = [case for case in plans if case["fault"]["expectation"] == "DETECT"]
    controls = [case for case in plans if case["fault"]["expectation"] == "PASS_CLEAN"]
    threats = {threat["id"] for threat in SUITE["gate"]["threats"]}

    # Assert
    assert len(SUITE["specs"]) == 20
    assert len(planted) >= 10
    assert controls
    assert threats == scorer.G3_THREATS


def test_should_mirror_the_six_g3_criteria_when_gate_yaml_is_read():
    # Arrange
    gate = SUITE["gate"]

    # Act
    ids = [criterion["id"] for criterion in gate["criteria"]]

    # Assert
    assert gate["gate"] == "G3"
    assert ids == ["G3.1", "G3.2", "G3.3", "G3.4", "G3.5", "G3.6"]
    assert gate["verdict"]["heldout"] == "sealed"
    for criterion in gate["criteria"]:
        assert criterion["text"].strip()
        assert criterion["pass_rule"].strip()


def test_should_list_every_g3e_item_with_its_owning_story_when_gate_yaml_is_read():
    # Arrange
    entry = SUITE["gate"]["entry"]

    # Act
    owners = [item["owner"] for item in entry]

    # Assert
    assert owners == ["4.1", "4.1", "4.2b", "4.2b", "4.3", "6.5", "4.1"]


def test_should_report_invalid_input_for_other_stories_when_the_suite_is_sound():
    # Arrange
    gate = SUITE["gate"]

    # Act
    rows = scorer.entry_status(gate, sound=True)

    # Assert
    statuses = {item_id: status for item_id, _, status in rows}
    assert statuses["G3.E.1"].startswith("OK (structural check only;")
    assert "stub" in statuses["G3.E.1"]
    for item_id in ("G3.E.2", "G3.E.7"):
        assert statuses[item_id] == "OK (structural check only)"
    for item_id in ("G3.E.3", "G3.E.4", "G3.E.5", "G3.E.6"):
        assert statuses[item_id].startswith("INVALID_INPUT")


def test_should_report_fail_for_every_owned_item_when_the_suite_is_not_sound():
    # Arrange
    gate = SUITE["gate"]

    # Act
    rows = scorer.entry_status(gate, sound=False)

    # Assert
    statuses = {item_id: status for item_id, _, status in rows}
    for item_id in ("G3.E.1", "G3.E.2", "G3.E.7"):
        assert statuses[item_id].startswith("FAIL")


def test_should_exit_one_when_main_checks_a_broken_suite(monkeypatch):
    # Arrange
    broken = _mutated()
    broken["specs"] = broken["specs"][:-1]
    monkeypatch.setattr(scorer, "load_suite", lambda: broken)

    # Act
    exit_code = scorer.main()

    # Assert
    assert exit_code == 1


def test_should_hold_only_the_sealed_pair_with_no_unseal_spent_when_heldout_is_read():
    # Arrange
    heldout = G3 / "heldout"

    # Act
    manifest = json.loads((heldout / "SEAL.json").read_text(encoding="utf-8"))
    archive = (heldout / "heldout.tar.enc").read_bytes()

    # Assert
    assert sorted(p.name for p in heldout.iterdir()) == ["SEAL.json", "heldout.tar.enc"]
    assert manifest["gate"] == "G3"
    assert manifest["case_count"] == 7
    assert manifest["unseal_events"] == []
    assert hashlib.sha256(archive).hexdigest() == manifest["archive_sha256"]


def test_should_carry_no_designer_loop_field_when_any_fault_case_is_read():
    # Arrange
    case_files = sorted((G3 / "fault-injection").rglob("case.yaml"))

    # Act
    texts = {path.parent.name: path.read_text(encoding="utf-8") for path in case_files}

    # Assert
    for name, text in texts.items():
        assert "planted_op" not in yaml.safe_load(text), name
        assert "designer" not in text, name


def test_should_restore_no_reverted_path_when_the_tree_is_searched():
    # Arrange
    paths = [REPO_ROOT / relative for relative in MUST_NOT_RESTORE]

    # Act
    found = [path.relative_to(REPO_ROOT).as_posix() for path in paths if path.exists()]

    # Assert
    assert found == []


# --------------------------------------------------------------------------- #
# I/O matrix: stub run and exit attempt
# --------------------------------------------------------------------------- #


def test_should_fail_all_six_criteria_with_invalid_input_when_run_against_the_stub():
    # Arrange
    gate = "G3"

    # Act
    reports, exit_code = runner.run_gate(gate)

    # Assert
    assert exit_code == 1
    assert [r["subject"]["criterion"] for r in reports] == [f"G3.{n}" for n in range(1, 7)]
    assert {r["verdict"] for r in reports} == {"INVALID_INPUT"}


def test_should_write_six_failing_reports_when_a_dev_run_has_no_actor(monkeypatch):
    # Arrange
    monkeypatch.setattr(runner, "BENCHMARKS_ROOT", BENCHMARKS)
    run_dir = BENCHMARKS / "gate-artifacts" / "g3" / "pytest-g3-offline"
    # The run dir is gitignored and survives between sessions; stale reports must not count.
    shutil.rmtree(run_dir, ignore_errors=True)

    # Act
    exit_code = runner.main(["run", "G3", "--run", "pytest-g3-offline"])

    # Assert
    assert exit_code == 1
    reports = sorted((run_dir / "reports").glob("*.json"))
    assert len(reports) == 6
    for path in reports:
        report = json.loads(path.read_text(encoding="utf-8"))
        assert derive_verdict(report) == "INVALID_INPUT", path.stem


def test_should_refuse_and_spend_no_unseal_when_exit_runs_without_the_key(monkeypatch, capsys):
    # Arrange
    monkeypatch.delenv(runner._UNSEAL_KEY_ENV, raising=False)
    seal_before = (G3 / "heldout" / "SEAL.json").read_bytes()

    # Act
    exit_code = runner.main(["run", "G3", "--exit", "--run", "pytest-g3-exit-nokey"])

    # Assert
    assert exit_code == 2
    assert runner._UNSEAL_KEY_ENV in capsys.readouterr().err
    assert (G3 / "heldout" / "SEAL.json").read_bytes() == seal_before


def test_should_refuse_before_the_unseal_when_exit_runs_with_a_key(monkeypatch, capsys):
    # Arrange
    monkeypatch.setenv(runner._UNSEAL_KEY_ENV, "not-the-operator-key")
    seal_before = (G3 / "heldout" / "SEAL.json").read_bytes()

    # Act
    exit_code = runner.main(["run", "G3", "--exit", "--run", "pytest-g3-exit-key"])

    # Assert
    assert exit_code == 2
    assert "evaluator" in capsys.readouterr().err
    assert (G3 / "heldout" / "SEAL.json").read_bytes() == seal_before


def test_should_route_to_the_structural_scorer_when_faults_g3_runs():
    # Arrange
    argv = ["faults", "G3"]

    # Act
    exit_code = runner.main(argv)

    # Assert
    assert exit_code == 0


# --------------------------------------------------------------------------- #
# I/O matrix: each structural defect fails the check that owns it
# --------------------------------------------------------------------------- #


def test_should_name_the_case_when_a_spec_check_uses_an_index_selector():
    # Arrange
    suite = _mutated()
    spec = _by_id(suite["specs"], "g3-dev-001-mounting-plate")
    spec["assertions"]["checks"].append({"fn": "hole_diameter", "select": "Face6", "expect": 5.5})

    # Act
    problems = scorer.check_suite(suite, TOOLS)["spec_selectors"]

    # Assert
    assert any("g3-dev-001-mounting-plate" in p and "Face6" in p for p in problems), problems


def test_should_name_the_case_when_a_spec_check_reads_feature_metadata():
    # Arrange
    suite = _mutated()
    spec = _by_id(suite["specs"], "g3-dev-001-mounting-plate")
    spec["assertions"]["checks"].append(
        {"fn": "hole_diameter", "source": "PartDesign::Hole.Diameter", "expect": 5.5}
    )

    # Act
    problems = scorer.check_suite(suite, TOOLS)["spec_selectors"]

    # Assert
    assert any("g3-dev-001-mounting-plate" in p and "PartDesign::" in p for p in problems)


def test_should_name_the_case_when_a_spec_uses_an_unknown_fn():
    # Arrange
    suite = _mutated()
    spec = _by_id(suite["specs"], "g3-dev-003-shaft-collar")
    spec["assertions"]["checks"].append({"fn": "expect_color", "expect": "red"})

    # Act
    problems = scorer.check_suite(suite, TOOLS)["spec_vocabulary"]

    # Assert
    assert any("g3-dev-003-shaft-collar" in p and "expect_color" in p for p in problems)


def test_should_name_the_case_when_a_two_selector_primitive_lacks_a_selector():
    # Arrange
    suite = _mutated()
    spec = _by_id(suite["specs"], "g3-dev-002-l-bracket")
    angle = next(c for c in spec["assertions"]["checks"] if c["fn"] == "angle_between")
    del angle["select_b"]

    # Act
    problems = scorer.check_suite(suite, TOOLS)["spec_vocabulary"]

    # Assert
    assert any("g3-dev-002-l-bracket" in p and "angle_between" in p for p in problems), problems


def test_should_name_the_case_when_a_spec_declares_no_checks():
    # Arrange
    suite = _mutated()
    _by_id(suite["specs"], "g3-dev-018-flat-washer")["assertions"]["checks"] = []

    # Act
    problems = scorer.check_suite(suite, TOOLS)["spec_vocabulary"]

    # Assert
    assert any("g3-dev-018-flat-washer" in p and "no checks" in p for p in problems), problems


def test_should_name_the_case_when_an_anchor_frame_is_outside_the_closed_set():
    # Arrange
    suite = _mutated()
    spec = _by_id(suite["specs"], "g3-dev-003-shaft-collar")
    spec["assertions"]["anchor_frame"]["kind"] = "global"

    # Act
    problems = scorer.check_suite(suite, TOOLS)["spec_vocabulary"]

    # Assert
    assert any("g3-dev-003-shaft-collar" in p and "anchor_frame" in p for p in problems)


def test_should_name_the_case_when_a_fault_names_no_dev_spec():
    # Arrange
    suite = _mutated()
    _by_id(suite["plans"], "g3-fault-plan-wrong-hole-diameter")["spec_ref"] = "g3-dev-999-none"

    # Act
    problems = scorer.check_suite(suite, TOOLS)["fault_mapping"]

    # Assert
    assert any("g3-fault-plan-wrong-hole-diameter" in p for p in problems), problems


def test_should_name_the_case_when_a_fault_is_detected_by_a_check_its_spec_lacks():
    """The DW-122 defect: a planted plan detected only by a check its spec never declared."""
    # Arrange
    suite = _mutated()
    spec = _by_id(suite["specs"], "g3-dev-011-lever-arm")
    spec["assertions"]["checks"] = [
        check for check in spec["assertions"]["checks"] if check["fn"] != "hole_position"
    ]

    # Act
    problems = scorer.check_suite(suite, TOOLS)["fault_mapping"]

    # Assert
    assert any("g3-fault-plan-mirrored-hole-pattern" in p for p in problems), problems


def test_should_name_the_threat_when_it_has_no_counter_case():
    # Arrange
    suite = _mutated()
    _by_id(suite["gate"]["threats"], "part_never_looked_at")["counter_cases"] = []

    # Act
    problems = scorer.check_suite(suite, TOOLS)["threat_coverage"]

    # Assert
    assert any("part_never_looked_at" in p for p in problems), problems


def test_should_fail_exactly_one_check_when_one_threat_case_is_removed():
    # Arrange
    suite = _mutated()
    suite["threat_cases"] = [
        case for case in suite["threat_cases"] if case["id"] != "g3-threat-banner-actor-mismatch"
    ]

    # Act
    failing = _failing(scorer.check_suite(suite, TOOLS))

    # Assert
    assert list(failing) == ["threat_coverage"]
    assert "rate_cited_for_wrong_actor" in failing["threat_coverage"][0]


def test_should_name_case_and_step_when_a_plan_step_names_an_uncatalogued_tool():
    # Arrange
    suite = _mutated()
    plan = _by_id(suite["plans"], "g3-fault-plan-wrong-hole-diameter")["plan"]
    plan[4] = {"tool": "plan_shape", "args": {"builder": "plate"}}

    # Act
    problems = scorer.check_suite(suite, TOOLS)["plan_steps"]

    # Assert
    assert any("g3-fault-plan-wrong-hole-diameter: step 4" in p for p in problems), problems


def test_should_name_case_and_step_when_the_tool_schema_rejects_step_args():
    # Arrange
    suite = _mutated()
    plan = _by_id(suite["plans"], "g3-fault-plan-radius-for-diameter")["plan"]
    plan[4]["args"]["length"] = 15

    # Act
    problems = scorer.check_suite(suite, TOOLS)["plan_steps"]

    # Assert
    assert any("g3-fault-plan-radius-for-diameter: step 4" in p for p in problems), problems


def test_should_name_case_and_step_when_a_step_carries_a_third_key():
    # Arrange
    suite = _mutated()
    _by_id(suite["plans"], "g3-fault-plan-wrong-hole-diameter")["plan"][1]["note"] = "extra"

    # Act
    problems = scorer.check_suite(suite, TOOLS)["plan_steps"]

    # Assert
    assert any("g3-fault-plan-wrong-hole-diameter: step 1" in p for p in problems), problems


def test_should_name_the_case_when_a_plan_is_missing():
    # Arrange
    suite = _mutated()
    del _by_id(suite["plans"], "g3-fault-plan-missing-bolt-holes")["plan"]

    # Act
    problems = scorer.check_suite(suite, TOOLS)["plan_steps"]

    # Assert
    assert any("g3-fault-plan-missing-bolt-holes" in p and "no plan" in p for p in problems)


def test_should_name_the_case_when_a_planted_case_marks_no_step():
    # Arrange
    suite = _mutated()
    del _by_id(suite["plans"], "g3-fault-plan-wrong-hole-diameter")["planted_step"]

    # Act
    problems = scorer.check_suite(suite, TOOLS)["planted_steps"]

    # Assert
    assert any("g3-fault-plan-wrong-hole-diameter" in p for p in problems), problems


def test_should_name_the_case_when_a_control_marks_a_planted_step():
    # Arrange
    suite = _mutated()
    _by_id(suite["plans"], "g3-fault-plan-control-faithful-mounting-plate")["planted_step"] = 7

    # Act
    problems = scorer.check_suite(suite, TOOLS)["planted_steps"]

    # Assert
    assert any("g3-fault-plan-control-faithful-mounting-plate" in p for p in problems)


def test_should_fail_the_counts_when_fewer_than_ten_plans_are_planted():
    # Arrange
    suite = _mutated()
    suite["plans"] = [
        case for case in suite["plans"] if case["id"] != "g3-fault-plan-wrong-plate-thickness"
    ]

    # Act
    problems = scorer.check_suite(suite, TOOLS)["fault_counts"]

    # Assert
    assert any("9 planted plans" in p for p in problems), problems


def test_should_fail_the_counts_when_the_suite_has_no_clean_control():
    # Arrange
    suite = _mutated()
    suite["plans"] = [case for case in suite["plans"] if case["fault"]["kind"] != "clean_control"]

    # Act
    problems = scorer.check_suite(suite, TOOLS)["fault_counts"]

    # Assert
    assert any("no clean control" in p for p in problems), problems


def test_should_fail_the_spec_count_when_only_nineteen_specs_exist():
    # Arrange
    suite = _mutated()
    suite["specs"] = suite["specs"][:-1]

    # Act
    problems = scorer.check_suite(suite, TOOLS)["spec_count"]

    # Assert
    assert any("19 specs" in p for p in problems), problems


def test_should_name_the_case_when_a_spec_loses_its_inline_derivation():
    # Arrange
    suite = _mutated()
    spec = _by_id(suite["specs"], "g3-dev-004-round-standoff")
    spec["_text"] = spec["_text"].replace("Derivations:", "")

    # Act
    problems = scorer.check_suite(suite, TOOLS)["spec_derivations"]

    # Assert
    assert any("g3-dev-004-round-standoff" in p for p in problems), problems


def test_should_name_the_case_when_a_plan_targets_another_validator():
    # Arrange
    suite = _mutated()
    case = _by_id(suite["plans"], "g3-fault-plan-wrong-hole-diameter")
    case["targets_validator"] = "corrupted_plan@usecases.designer_loop.detect_spec_violation"

    # Act
    problems = scorer.check_suite(suite, TOOLS)["fault_shape"]

    # Assert
    assert any("g3-fault-plan-wrong-hole-diameter" in p for p in problems), problems


def test_should_name_the_case_when_fault_kind_disagrees_with_expectation():
    # Arrange
    suite = _mutated()
    _by_id(suite["plans"], "g3-fault-plan-wrong-hole-diameter")["fault"]["kind"] = "clean_control"

    # Act
    problems = scorer.check_suite(suite, TOOLS)["fault_shape"]

    # Assert
    assert any("g3-fault-plan-wrong-hole-diameter" in p and "disagrees" in p for p in problems)


def test_should_name_the_case_when_its_criterion_is_not_a_g3_criterion():
    # Arrange
    suite = _mutated()
    _by_id(suite["plans"], "g3-fault-plan-extra-unrequested-pocket")["criterion"] = "G2.1"

    # Act
    problems = scorer.check_suite(suite, TOOLS)["fault_shape"]

    # Assert
    assert any("g3-fault-plan-extra-unrequested-pocket" in p and "G2.1" in p for p in problems)


def test_should_name_the_case_when_a_fault_fixture_is_not_pending():
    # Arrange
    suite = _mutated()
    _by_id(suite["plans"], "g3-fault-plan-radius-for-diameter")["fixture"] = "fixture.FCStd"

    # Act
    problems = scorer.check_suite(suite, TOOLS)["fault_shape"]

    # Assert
    assert any("g3-fault-plan-radius-for-diameter" in p for p in problems), problems


def test_should_name_the_case_when_a_threat_counter_is_not_planted():
    # Arrange
    suite = _mutated()
    fault = _by_id(suite["threat_cases"], "g3-threat-no-visual-findings")["fault"]
    fault["kind"], fault["expectation"] = "clean_control", "PASS_CLEAN"

    # Act
    problems = scorer.check_suite(suite, TOOLS)["fault_shape"]

    # Assert
    assert any("g3-threat-no-visual-findings" in p and "planted defect" in p for p in problems)


def test_should_name_the_case_when_a_threat_plan_ref_names_a_planted_plan():
    # Arrange
    suite = _mutated()
    case = _by_id(suite["threat_cases"], "g3-threat-no-visual-findings")
    case["plan_ref"] = "g3-fault-plan-wrong-hole-diameter"

    # Act
    problems = scorer.check_suite(suite, TOOLS)["fault_shape"]

    # Assert
    assert any("g3-threat-no-visual-findings" in p and "plan_ref" in p for p in problems)


def test_should_name_the_case_when_a_threat_case_has_no_planted_evidence():
    # Arrange
    suite = _mutated()
    del _by_id(suite["threat_cases"], "g3-threat-banner-actor-mismatch")["planted_evidence"]

    # Act
    problems = scorer.check_suite(suite, TOOLS)["fault_shape"]

    # Assert
    assert any("g3-threat-banner-actor-mismatch" in p for p in problems), problems


def test_should_name_the_case_when_it_has_no_provenance_key():
    # Arrange
    suite = _mutated()
    del _by_id(suite["specs"], "g3-dev-009-flanged-bushing")["provenance"]

    # Act
    problems = scorer.check_suite(suite, TOOLS)["provenance"]

    # Assert
    assert any("g3-dev-009-flanged-bushing" in p and "names no" in p for p in problems), problems


def test_should_name_the_case_when_its_manifest_is_missing():
    # Arrange
    suite = _mutated()
    case = _by_id(suite["specs"], "g3-dev-013-pipe-stub")
    case["provenance"] = "../../../_registry/provenance/g3-dev-013-no-such-manifest.yaml"

    # Act
    problems = scorer.check_suite(suite, TOOLS)["provenance"]

    # Assert
    assert any("g3-dev-013-pipe-stub" in p for p in problems), problems


def test_should_name_the_case_when_its_manifest_binds_another_case():
    # Arrange
    suite = _mutated()
    case = _by_id(suite["plans"], "g3-fault-plan-wrong-hole-diameter")
    case["provenance"] = "../../../../_registry/provenance/g3-fault-plan-wrong-plate-thickness.yaml"

    # Act
    problems = scorer.check_suite(suite, TOOLS)["provenance"]

    # Assert
    assert any("g3-fault-plan-wrong-hole-diameter" in p and "binds" in p for p in problems)


def test_should_fail_when_the_reuse_survey_is_missing():
    # Arrange
    suite = _mutated()
    suite["reuse_survey"] = suite["reuse_survey"].with_name("no-such-survey.md")

    # Act
    problems = scorer.check_suite(suite, TOOLS)["reuse_survey"]

    # Assert
    assert any("reuse survey is missing" in p for p in problems), problems


# A planted plan and the control it pairs with share every step but the planted one, so the suite
# measures the corruption and not the difference between two hand-written plans.
PAIRED_WITH_CONTROL = [
    ("g3-fault-plan-wrong-hole-diameter", "g3-fault-plan-control-faithful-mounting-plate"),
    ("g3-fault-plan-wrong-plate-thickness", "g3-fault-plan-control-faithful-mounting-plate"),
    ("g3-fault-plan-datum-origin-swapped", "g3-fault-plan-control-named-datum-honoured"),
]


@pytest.mark.parametrize(("planted_id", "control_id"), PAIRED_WITH_CONTROL)
def test_should_differ_only_in_the_planted_step_when_compared_with_its_control(
    planted_id, control_id
):
    # Arrange
    planted = _by_id(SUITE["plans"], planted_id)
    control = _by_id(SUITE["plans"], control_id)

    # Act
    differing = [
        index
        for index, (ours, theirs) in enumerate(zip(planted["plan"], control["plan"]))
        if index > 0 and ours != theirs
    ]

    # Assert
    assert len(planted["plan"]) == len(control["plan"])
    assert differing == [planted["planted_step"]]


# --------------------------------------------------------------------------- #
# check_provenance: case-file manifests
# --------------------------------------------------------------------------- #


def test_should_flag_an_orphan_when_a_spec_case_is_gone(tmp_path):
    # Arrange
    copy_root = _benchmarks_copy(tmp_path)
    (copy_root / "g3" / "dev" / "g3-dev-005-rail-shim" / "case.yaml").unlink()

    # Act
    problems = check_provenance.check_tree(copy_root)

    # Assert
    assert any("orphan manifest" in p and "g3-dev-005-rail-shim" in p for p in problems)


def test_should_flag_an_orphan_when_a_fault_case_is_gone(tmp_path):
    # Arrange
    copy_root = _benchmarks_copy(tmp_path)
    case_dir = copy_root / "g3" / "fault-injection" / "threat-counters"
    (case_dir / "g3-threat-no-visual-findings" / "case.yaml").unlink()

    # Act
    problems = check_provenance.check_tree(copy_root)

    # Assert
    assert any("orphan manifest" in p and "g3-threat-no-visual-findings" in p for p in problems)


def test_should_flag_a_missing_fixture_when_a_spec_case_declares_no_fixture_state(tmp_path):
    # Arrange
    copy_root = _benchmarks_copy(tmp_path)
    case_yaml = copy_root / "g3" / "dev" / "g3-dev-005-rail-shim" / "case.yaml"
    text = case_yaml.read_text(encoding="utf-8")
    case_yaml.write_text(text.replace("fixture: none-spec-to-part\n", ""), encoding="utf-8")

    # Act
    problems = check_provenance.check_tree(copy_root)

    # Assert
    assert any("g3-dev-005-rail-shim" in p and "fixture.FCStd missing" in p for p in problems)


def test_should_name_the_manifest_when_a_case_file_manifest_has_an_invalid_source_kind(tmp_path):
    # Arrange
    copy_root = _benchmarks_copy(tmp_path)
    manifest = copy_root / "_registry" / "provenance" / "g3-fault-plan-pocket-before-pad.yaml"
    data = yaml.safe_load(manifest.read_text(encoding="utf-8"))
    data["source"]["kind"] = "deepcad"
    manifest.write_text(yaml.safe_dump(data), encoding="utf-8")

    # Act
    problems = check_provenance.check_tree(copy_root)

    # Assert
    assert any(
        "g3-fault-plan-pocket-before-pad.yaml" in p and "not in closed set" in p for p in problems
    ), problems


# The shipped validator: every committed dev spec must be a check `verify_shape` accepts. The
# sealed held-out split is never read outside `gate run --exit`.
DEV_CASES = sorted((G3 / "dev").glob("*/case.yaml"))


def _dev_assertions(case_yaml: Path) -> dict:
    return yaml.safe_load(case_yaml.read_text(encoding="utf-8"))["assertions"]


@pytest.mark.parametrize("case_yaml", DEV_CASES, ids=lambda path: path.parent.name)
def test_should_accept_every_check_and_frame_when_a_dev_spec_is_validated(case_yaml):
    # Arrange
    spec = _dev_assertions(case_yaml)

    # Act
    def act():
        primitives._validate_declared_frame(spec["anchor_frame"])
        for check in spec["checks"]:
            primitives.validate_check(check)

    # Assert
    act()


def test_should_share_the_vocabulary_when_the_structural_check_and_the_validator_are_compared():
    # Arrange
    contract_fns, contract_kinds = ASSERTION_FNS, ANCHOR_FRAME_KINDS

    # Act
    structural_fns, structural_kinds = scorer.CLOSED_FNS, scorer.ANCHOR_KINDS

    # Assert
    assert DEV_CASES, "no G3 dev case.yaml found"
    assert structural_fns == contract_fns
    assert structural_kinds == contract_kinds


@pytest.mark.parametrize(
    "declared",
    [
        {"kind": "named_origin", "ref": "XY_Plane"},
        {"kind": "base_sketch_plane", "ref": "XY_Plane", "offset": 5},
        {"kind": "largest_planar_face", "ref": "Face6"},
        {"kind": "named_datum", "ref": ""},
    ],
    ids=["unknown-kind", "extra-key", "ref-on-largest-face", "empty-ref"],
)
def test_should_raise_validation_error_when_the_anchor_frame_is_malformed(declared):
    # Arrange
    frame = copy.deepcopy(declared)

    # Act
    def act():
        primitives._validate_declared_frame(frame)

    # Assert
    with pytest.raises(ValidationError):
        act()
