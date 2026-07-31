"""FreeCAD-free tests for the mutation contract, the emitted schema, and the module surfaces.

Confirms the ``mutation`` wire vocabulary is contracts-owned and stdlib-only, that its generated
JSON Schema carries the required fields and closed enums, and that ``usecases.transaction`` /
``usecases.tnp_guard`` / ``benchmarks.harness.assertions`` import with no FreeCAD present (ring
discipline: FreeCAD is imported lazily inside functions). The behavioural mutation tests run
in-FreeCAD in ``tests/infc/test_mutation_protocol.py``.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import get_args, get_type_hints

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from benchmarks.harness import assertions  # noqa: E402
from freecad_buddy.contracts import (  # noqa: E402
    MutationBlock,
    PostVerifyBlock,
    RefFinding,
    RefVerdict,
    RollbackProof,
    TnpAuditBlock,
    TnpStatus,
)
from freecad_buddy.usecases import tnp_guard, transaction  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[2]
SCHEMA_DIR = REPO_ROOT / "src" / "freecad_buddy" / "contracts" / "jsonschema"


def _schema() -> dict:
    return json.loads((SCHEMA_DIR / "mutation.schema.json").read_text(encoding="utf-8"))


def test_ref_verdict_is_the_closed_six_member_set():
    assert set(get_args(RefVerdict)) == {
        "PASS",
        "BROKEN",
        "REPOINTED",
        "DROPPED",
        "UNSUPPORTED",
        "RE_BASELINED",
    }


def test_rollback_proof_names_only_the_two_proven_paths():
    assert set(get_args(RollbackProof)) == {"rolled_back_verified", "rolled_back_via_snapshot"}


def test_tnp_status_never_offers_a_clean_synonym():
    assert set(get_args(TnpStatus)) == {"CLEAN", "FLAGGED", "UNSUPPORTED"}


def test_mutation_block_uses_the_shared_audit_field_names():
    """Story 3.6's diff reuses these identifiers, so a synonym here breaks it downstream."""
    hints = get_type_hints(MutationBlock)
    for field in ("fingerprint_before", "fingerprint_after", "verify_verdict", "params_digest"):
        assert field in hints


def test_post_verify_block_carries_the_four_checklist_signals_and_an_explanation():
    hints = get_type_hints(PostVerifyBlock)
    for field in ("recompute_clean", "is_valid", "fully_constrained", "tnp_audit", "explanation"):
        assert field in hints


def test_ref_finding_records_the_layer_that_decided_the_verdict():
    hints = get_type_hints(RefFinding)
    assert hints["layer"] is int
    for field in ("owner", "prop", "mapped_before", "state_after", "verdict", "detail"):
        assert field in hints


def test_tnp_audit_block_banners_the_element_map_version():
    assert "element_map_version" in get_type_hints(TnpAuditBlock)


def test_schema_requires_both_fingerprints_and_the_rollback_outcome():
    schema = _schema()
    assert schema["$id"] == "fcb.mutation/1"
    assert set(schema["required"]) == {
        "transaction_id",
        "fingerprint_before",
        "fingerprint_after",
        "post_verify",
        "rolled_back",
        "rollback_proven",
    }


def test_schema_validates_no_empty_object_for_the_nested_blocks():
    defs = _schema()["$defs"]
    assert defs["PostVerifyBlock"]["required"]
    assert defs["TnpAuditBlock"]["required"]
    assert defs["RefFinding"]["required"]


def test_schema_emits_the_closed_verdict_and_proof_enums():
    schema = _schema()
    verdict = schema["$defs"]["RefFinding"]["properties"]["verdict"]["enum"]
    assert set(verdict) == set(get_args(RefVerdict))
    proof = schema["properties"]["rollback_proven"]["anyOf"]
    members = next(branch["enum"] for branch in proof if "enum" in branch)
    assert set(members) == set(get_args(RollbackProof))


def test_transaction_module_imports_without_freecad():
    assert callable(transaction.run_mutation)
    assert callable(transaction.post_verify)
    assert callable(transaction.temp_snapshot_path)
    assert issubclass(transaction.RollbackNotProven, RuntimeError)


def test_transaction_never_requests_cross_document_transaction_grouping():
    """A non-zero transaction id groups documents so they undo together — an unwanted channel."""
    assert transaction._TRANSACTION_ID == "0"


def test_tnp_guard_module_imports_without_freecad():
    assert callable(tnp_guard.snapshot_references)
    assert callable(tnp_guard.audit_references)


def test_tnp_guard_uses_the_source_verified_element_name_prefixes():
    """App/ElementNamingUtils.h: ELEMENT_MAP_PREFIX = ";" and MISSING_PREFIX = "?"."""
    assert tnp_guard._MAPPED_PREFIX == ";"
    assert tnp_guard._MISSING_PREFIX == "?"


@pytest.mark.parametrize(
    ("subname", "mapped", "indexed", "missing"),
    [
        ("Face6", None, "Face6", False),
        (";M;:H,F.Face3", ";M;:H,F", "Face3", False),
        (";M;:H,F", ";M;:H,F", None, False),
        ("?Face6", None, "Face6", True),
        ("?;M;:H,F.Face3", ";M;:H,F", "Face3", True),
    ],
)
def test_split_subname_separates_the_mapped_and_indexed_halves(subname, mapped, indexed, missing):
    entry = tnp_guard._split_subname(subname)
    assert entry == {"mapped": mapped, "indexed": indexed, "missing": missing}


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (None, []),
        (("obj", ["Face1", "Face2"]), [("obj", ["Face1", "Face2"])]),
        ([("a", ("Edge1",)), ("b", ("Edge2",))], [("a", ["Edge1"]), ("b", ["Edge2"])]),
        ("not a link value", []),
    ],
)
def test_link_sub_entries_normalizes_both_property_shapes(value, expected):
    """App/PropertyLinks.cpp: LinkSub yields (obj, [subs]); LinkSubList yields [(obj, (subs,))]."""
    assert tnp_guard._link_sub_entries(value) == expected


def test_assertions_module_imports_without_freecad_and_declares_the_eight_fns():
    assert assertions.SUPPORTED_FNS == {
        "is_valid_solid",
        "count_cylindrical_holes",
        "hole_spacing",
        "hole_through",
        "expect_volume",
        "expect_solid_count",
        "expect_sketch_fully_constrained",
        "expect_sketch_geometry_count",
    }


def test_assertions_fail_an_unsupported_fn_as_invalid_input_never_as_a_pass():
    results = assertions.evaluate(None, [{"fn": "no_such_primitive", "expect": 1}])
    assert len(results) == 1
    assert results[0]["passed"] is False
    assert results[0]["detail"]["code"] == "invalid_input.unsupported_assertion"


def test_assertions_fail_a_non_mapping_check_rather_than_skipping_it():
    results = assertions.evaluate(None, ["expect_volume"])
    assert [check["passed"] for check in results] == [False]


def test_assertions_grade_every_declared_g2_fn():
    """A case fn with no measurement would silently grade nothing, so the sets must match.

    Reads the ``fn`` names out of the committed G2 cases rather than a hand-kept list: a literal
    copy would stay green when a case introduces an assertion the grader cannot measure.
    """
    root = Path(__file__).resolve().parents[2] / "benchmarks/g2"
    # heldout/ is sealed: it is never opened outside a `gate run --exit`.
    cases = sorted(c for c in root.rglob("case.yaml") if "heldout" not in c.parts)
    assert cases, "no G2 case.yaml found to read assertion fns from"

    declared = {
        match.group(1)
        for case in cases
        for match in re.finditer(r"\bfn:\s*([A-Za-z_][A-Za-z0-9_]*)", case.read_text("utf-8"))
    }
    assert declared, "no assertion fn declared by any G2 case"
    assert declared <= assertions.SUPPORTED_FNS


def test_tolerance_band_prefers_the_declared_allowance_over_the_default():
    assert assertions._band({"abs": 0.5}, 100.0, 0.05, None) == 0.5
    assert assertions._band({"rel": 0.001}, 100.0, None, 0.01) == pytest.approx(0.1)
    assert assertions._band(None, 100.0, None, 0.01) == pytest.approx(1.0)
    assert assertions._band(None, 10.0, 0.05, None) == 0.05
