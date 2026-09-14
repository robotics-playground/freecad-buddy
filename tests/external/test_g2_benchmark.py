"""Structural self-check for the G2 command benchmark and its fault suites.

Asserts the properties Story 3.1 is accountable for: the 40 dev commands partition 5-per-type
across the eight op types of decision 013, every case carries assertions against a committed
golden model, and each fault suite mixes planted defects with clean controls so sensitivity and
false alarm are both measurable.
"""

import json
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
G2 = REPO_ROOT / "benchmarks" / "g2"

OP_TYPES = frozenset({"sketch", "pad", "pocket", "revolve", "hole", "dressup", "pattern", "mirror"})
EXPECTED_DEV_CASES = 40
CASES_PER_OP_TYPE = 5
FAULT_SUITES = frozenset(
    {"tnp", "dressup-drop", "coincidental-hash", "rollback-boundary", "wrong-parameter", "sketch"}
)


def _load(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _cases(root: Path) -> list[Path]:
    return sorted(root.glob("*/case.yaml"))


def _fault_cases() -> list[Path]:
    return sorted((G2 / "fault-injection").glob("*/*/case.yaml"))


DEV_CASES = _cases(G2 / "dev")
# The held-out split is sealed (story 3.8): its cases are unreadable outside `--exit`, so the
# structural checks below cover the dev split only and the seal is asserted separately.
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


def test_heldout_holds_only_the_sealed_pair():
    """After the G2 seal no readable case may sit in ``heldout/`` — the manifest attests the set.

    Reading a held-out command is what the seal exists to prevent, so the op-type coverage and
    dev-disjointness this suite used to assert over the plaintext are now attested by the
    manifest's ``case_count`` and re-checked only inside the ``--exit`` unseal path.
    """
    heldout = G2 / "heldout"
    present = sorted(p.name for p in heldout.iterdir())
    assert present == ["SEAL.json", "heldout.tar.enc"]

    manifest = json.loads((heldout / "SEAL.json").read_text(encoding="utf-8"))
    assert manifest["gate"] == "G2"
    assert manifest["case_count"] == len(OP_TYPES)
    assert manifest["archive_sha256"]


def test_the_sealed_archive_is_not_readable_plaintext():
    """A sealed archive that still spelled its cases in the clear would seal nothing."""
    blob = (G2 / "heldout" / "heldout.tar.enc").read_bytes()

    assert b"g2-heldout" not in blob
    assert b"op_type" not in blob


@pytest.mark.parametrize("case", DEV_CASES, ids=lambda p: p.parent.name)
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


@pytest.mark.parametrize("case", DEV_CASES, ids=lambda p: p.parent.name)
def test_command_case_targets_a_committed_golden_model(case: Path):
    document = Path(_load(case)["inputs"]["document"])
    assert (case.parent / document).resolve().is_file()


@pytest.mark.parametrize("case", FAULT_CASES, ids=lambda p: p.parent.name)
def test_fault_case_carries_its_materialized_fixture(case: Path):
    """Every fault fixture is materialized, with its ``.FCStd`` and provenance manifest present.

    ``check_provenance`` exempts a case only while a ``fixture: pending`` state is explicit, so a
    fixture forgotten after materialization cannot hide behind the exemption.
    """
    data = _load(case)
    fixture = data["fixture"]
    assert fixture != "pending", "every fixture is materialized as of story 3.8"
    assert (case.parent / fixture).is_file()
    assert (case.parent / data["provenance"]).resolve().is_file()


def test_no_fault_case_still_declares_a_pending_fixture():
    """A benchmark that grades validators cannot leave a suite unbuilt and still be cited."""
    pending = [c.parent.name for c in FAULT_CASES if _load(c)["fixture"] == "pending"]
    assert pending == []


@pytest.mark.parametrize("case", FAULT_CASES, ids=lambda p: p.parent.name)
def test_materialized_fault_case_names_the_op_that_plants_it(case: Path):
    """The fixture is a pre-mutation input; ``planted_op`` names what turns it into the defect.

    Without it a fixture is just a document, and the defect it is meant to carry is unstated.
    """
    assert str(_load(case).get("planted_op") or "").strip()


@pytest.mark.parametrize("case", FAULT_CASES, ids=lambda p: p.parent.name)
def test_fault_case_declares_the_validator_it_targets(case: Path):
    """The scorer routes a case to its validator by this key, never by a hardcoded suite map."""
    assert str(_load(case).get("targets_validator") or "").strip()


def test_every_fault_suite_is_present():
    suites = {path.parent.parent.name for path in FAULT_CASES}
    assert suites == FAULT_SUITES


# The cited validators that still have no fault case behind them. A cited validator with an empty
# suite passes leg-b having validated nothing, because `check_validator_currency` compares only the
# stored validator_sha against the working tree and never asserts the suite exists (DW-98). This set
# is the remaining debt, and it only ever shrinks: authoring a suite removes a name, and the test
# below fails if a name is added or if a name here turns out to be covered after all.
G2_VALIDATORS_WITHOUT_A_FAULT_SUITE = frozenset({"fingerprint"})


def test_no_cited_g2_validator_loses_the_fault_cases_behind_it():
    """Every cited validator is targeted by a case, except the named remaining debt."""
    cited = {
        validator
        for criterion in _load(G2 / "gate.yaml")["criteria"]
        for validator in criterion.get("cited_validators") or []
    }
    targeted = {
        str(_load(case).get("targets_validator") or "").split("@", 1)[0] for case in FAULT_CASES
    }
    assert cited - targeted == G2_VALIDATORS_WITHOUT_A_FAULT_SUITE


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


VOCABULARY_FNS = frozenset(
    {"is_valid_solid", "count_cylindrical_holes", "hole_spacing", "hole_through", "expect_volume"}
)
G2_EXTENSION_FNS = frozenset(
    {"expect_solid_count", "expect_sketch_fully_constrained", "expect_sketch_geometry_count"}
)


def test_assertion_fns_are_declared():
    """Every fn is either a verification-design 7.2 primitive or a declared G2 extension.

    A near-miss rename (expect_through for hole_through) silently forks the vocabulary, and a
    new name added without a decision leaves the grader with nothing to implement against.
    """
    used = {
        check["fn"]
        for case in DEV_CASES
        for check in _load(case)["assertions"]["checks"]
    }
    assert used <= VOCABULARY_FNS | G2_EXTENSION_FNS
    assert used & G2_EXTENSION_FNS <= G2_EXTENSION_FNS
