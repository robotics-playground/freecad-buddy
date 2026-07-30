"""Structural self-check for the G2 command benchmark and its fault suites.

Asserts the properties Story 3.1 is accountable for: the 40 dev commands partition 5-per-type
across the eight op types of decision 013, every case carries assertions against a committed
golden model, and each fault suite mixes planted defects with clean controls so sensitivity and
false alarm are both measurable.
"""

from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
G2 = REPO_ROOT / "benchmarks" / "g2"

OP_TYPES = frozenset({"sketch", "pad", "pocket", "revolve", "hole", "dressup", "pattern", "mirror"})
EXPECTED_DEV_CASES = 40
CASES_PER_OP_TYPE = 5
FAULT_SUITES = frozenset(
    {"tnp", "dressup-drop", "coincidental-hash", "rollback-boundary", "wrong-parameter"}
)


def _load(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _cases(root: Path) -> list[Path]:
    return sorted(root.glob("*/case.yaml"))


def _fault_cases() -> list[Path]:
    return sorted((G2 / "fault-injection").glob("*/*/case.yaml"))


DEV_CASES = _cases(G2 / "dev")
HELDOUT_CASES = _cases(G2 / "heldout")
FAULT_CASES = _fault_cases()


def test_gate_yaml_mirrors_the_six_g2_criteria():
    gate = _load(G2 / "gate.yaml")
    assert gate["gate"] == "G2"
    ids = [c["id"] for c in gate["criteria"]]
    assert ids == ["G2.1", "G2.2", "G2.3", "G2.4", "G2.5", "G2.6"]
    assert gate["verdict"]["heldout"] == "sealed"
    for criterion in gate["criteria"]:
        assert criterion["text"].strip()
        assert criterion["pass_rule"].strip()


def test_dev_split_is_forty_commands():
    assert len(DEV_CASES) == EXPECTED_DEV_CASES


def test_dev_split_partitions_evenly_across_the_eight_op_types():
    """Decision 013: 5 commands per op type, so no type can be over-weighted."""
    counts: dict[str, int] = {}
    for case in DEV_CASES:
        op_type = _load(case)["op_type"]
        counts[op_type] = counts.get(op_type, 0) + 1
    assert set(counts) == OP_TYPES
    assert set(counts.values()) == {CASES_PER_OP_TYPE}


def test_heldout_split_covers_every_op_type():
    op_types = {_load(case)["op_type"] for case in HELDOUT_CASES}
    assert op_types == OP_TYPES


def test_heldout_commands_are_disjoint_from_dev_commands():
    """A held-out command the agent already iterated on is not held out."""
    dev = {_load(case)["spec"] for case in DEV_CASES}
    heldout = {_load(case)["spec"] for case in HELDOUT_CASES}
    assert not (dev & heldout)


@pytest.mark.parametrize("case", DEV_CASES + HELDOUT_CASES, ids=lambda p: p.parent.name)
def test_command_case_is_well_formed(case: Path):
    data = _load(case)
    assert data["gate"] == "g2"
    assert data["criterion"] == "G2.1"
    assert data["op_type"] in OP_TYPES
    assert data["spec"].strip(), "a command case must carry the NL command"
    checks = data["assertions"]["checks"]
    assert checks, "a command case with no checks cannot grade anything"
    for check in checks:
        assert check["fn"].strip()
        assert "expect" in check


@pytest.mark.parametrize("case", DEV_CASES + HELDOUT_CASES, ids=lambda p: p.parent.name)
def test_command_case_targets_a_committed_golden_model(case: Path):
    document = Path(_load(case)["inputs"]["document"])
    assert (case.parent / document).resolve().is_file()


@pytest.mark.parametrize("case", FAULT_CASES, ids=lambda p: p.parent.name)
def test_fault_case_declares_its_fixture_pending(case: Path):
    """AD-19 lands the benchmark first, so the fixture is declared pending, never just absent.

    ``check_provenance`` exempts a case only when the pending state is explicit, so a fixture
    forgotten once the mutation runtime exists is still flagged.
    """
    assert _load(case)["fixture"] == "pending"


def test_all_five_fault_suites_are_present():
    suites = {path.parent.parent.name for path in FAULT_CASES}
    assert suites == FAULT_SUITES


@pytest.mark.parametrize("case", FAULT_CASES, ids=lambda p: p.parent.name)
def test_fault_case_is_well_formed(case: Path):
    fault = _load(case)["fault"]
    assert fault["kind"] in {"planted_defect", "clean_control"}
    assert fault["description"].strip()
    expected = "DETECT" if fault["kind"] == "planted_defect" else "PASS_CLEAN"
    assert fault["expectation"] == expected


def test_every_fault_suite_mixes_defects_with_controls():
    """Controls measure false alarms; defects measure sensitivity. A suite needs both."""
    by_suite: dict[str, list[str]] = {}
    for case in FAULT_CASES:
        by_suite.setdefault(case.parent.parent.name, []).append(_load(case)["fault"]["kind"])
    for suite, kinds in by_suite.items():
        assert "planted_defect" in kinds, f"{suite} measures no sensitivity"
        assert "clean_control" in kinds, f"{suite} measures no false alarm"


def test_the_five_tnp_scenarios_are_all_present():
    """G2.4 scores 5/5 flagged, so all five provoking scenarios must exist."""
    scenarios = {
        _load(case).get("expected", {}).get("scenario")
        for case in FAULT_CASES
        if case.parent.parent.name == "tnp"
    }
    assert {"a", "b", "c", "d", "e"} <= scenarios


def test_layer_defeating_faults_declare_what_must_not_catch_them():
    """The traps exist to force Layers 1 and 2 to be real, so they pin the shallow layer."""
    declared = {
        case.parent.name: _load(case)["expected"]["must_not_be_caught_by"]
        for case in FAULT_CASES
        if "must_not_be_caught_by" in (_load(case).get("expected") or {})
    }
    assert declared, "no fault pins a layer, so a Layer-0-only guard would score 100%"
    assert set(declared.values()) <= {"layer_0_error_sweep", "layer_1_witness_comparison"}
