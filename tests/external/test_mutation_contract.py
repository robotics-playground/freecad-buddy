"""FreeCAD-free tests for the mutation contract, the emitted schema, and the module surfaces.

Confirms the ``mutation`` wire vocabulary is contracts-owned and stdlib-only, that its generated
JSON Schema carries the required fields and closed enums, and that ``usecases.transaction`` /
``usecases.tnp_guard`` / ``benchmarks.harness.assertions`` import with no FreeCAD present (ring
discipline: FreeCAD is imported lazily inside functions). The behavioural mutation tests run
in-FreeCAD in ``tests/infc/test_mutation_protocol.py``.
"""

from __future__ import annotations

import inspect
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
from freecad_buddy.usecases import assertions as primitives  # noqa: E402
from freecad_buddy.usecases import shim, tnp_guard, transaction  # noqa: E402

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
    for field in ("fingerprint_before", "fingerprint_after"):
        assert field in hints


def test_should_leave_the_audit_only_fields_out_of_the_wire_block():
    # Arrange
    audit_only = ("transaction_id", "verify_verdict", "params_digest")

    # Act
    hints = get_type_hints(MutationBlock)

    # Assert
    assert not set(audit_only) & set(hints)


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
    assert schema["$id"] == "fcb.mutation/2"
    assert set(schema["required"]) == {
        "fingerprint_before",
        "fingerprint_after",
        "changed",
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
    assert entry == {
        "mapped": mapped,
        "indexed": indexed,
        "missing": missing,
        "witness": None,
        "history": None,
    }


def test_audit_references_accepts_the_op_written_reference_reading():
    params = inspect.signature(tnp_guard.audit_references).parameters
    assert list(params) == ["doc", "snapshot", "written"]
    assert params["written"].default is None


def test_post_verify_threads_the_written_reading_into_the_audit():
    params = inspect.signature(transaction.post_verify).parameters
    assert "refs_written" in params
    source = inspect.getsource(transaction.post_verify)
    assert "audit_references(document, refs_before, refs_written)" in source


def test_run_mutation_captures_the_written_references_before_recompute():
    """The capture must sit between the op returning and recompute, or it reads FreeCAD's edit."""
    source = inspect.getsource(transaction._bracket)
    op_line = source.index("touched = list(op(document)")
    capture_line = source.index("refs_written = tnp_guard.snapshot_references(document)")
    recompute_line = source.index("document.recompute()")
    assert op_line < capture_line < recompute_line


def test_the_owner_level_exemption_is_absent_from_the_guard():
    """The reverted design exempted `record["owner"] in touched`, disabling the DROPPED check."""
    source = inspect.getsource(tnp_guard)
    assert "in touched" not in source
    assert "touched" not in inspect.signature(tnp_guard.audit_references).parameters


def test_the_guard_never_uses_hash_code_as_the_witness():
    """ShapeMapHasher.h hashes the TShape pointer plus Location, so it moves on every rebuild."""
    assert "hashCode" not in inspect.getsource(tnp_guard)


def test_get_element_is_called_positionally_because_silent_is_positional_only():
    """TopoShapePyImp.cpp: PyArg_ParseTuple(args, "s|O") — getElement takes no keyword args."""
    source = inspect.getsource(tnp_guard._resolve_element)
    assert "silent=" not in source
    assert "getter(name, True)" in source


def test_the_witness_is_type_plus_bounding_box_and_excludes_centre_of_mass():
    """Part.Vertex raises AttributeError for CenterOfMass, so a CoM witness cannot be captured."""
    source = inspect.getsource(tnp_guard._witness)
    assert "BoundBox" in source
    assert "ShapeType" in source
    assert "CenterOfMass" not in source


def test_the_witness_comparison_is_tolerant_rather_than_exact():
    source = inspect.getsource(tnp_guard._witness_moved)
    assert "tolerance" in source
    assert "==" not in source.split('"""')[-1]


def test_layer_two_compares_only_the_source_pair():
    """getElementHistory's intermediates are rebuild-order sensitive, so they must not be kept."""
    source = inspect.getsource(tnp_guard._history)
    assert "record[0]" in source and "record[1]" in source
    assert "record[2]" not in source


def test_the_record_key_includes_the_target_object():
    """A PropertyLinkSubList emits one record per (target, subs) pair; omitting the target
    collapses a multi-target property onto its last pair."""
    records = [
        {"owner": "S", "prop": "AttachmentSupport", "target": "BoxA", "entries": []},
        {"owner": "S", "prop": "AttachmentSupport", "target": "BoxB", "entries": []},
    ]
    keyed = tnp_guard._keyed(records)
    assert len(keyed) == 2
    assert {key[2] for key in keyed} == {"BoxA", "BoxB"}


def test_the_record_key_disambiguates_a_property_linking_one_target_twice():
    records = [
        {"owner": "S", "prop": "ExternalGeometry", "target": "BoxA", "entries": []},
        {"owner": "S", "prop": "ExternalGeometry", "target": "BoxA", "entries": []},
    ]
    keyed = tnp_guard._keyed(records)
    assert len(keyed) == 2
    assert {key[3] for key in keyed} == {0, 1}


def test_the_re_baseline_branch_does_not_short_circuit_the_record():
    """RE_BASELINED is filtered as non-failing, so an early return hides a concurrent drop."""
    source = inspect.getsource(tnp_guard._grade_record)
    head, _, tail = source.partition('"RE_BASELINED"')
    assert "DROPPED" in tail, "the entry-count comparison must still run after a re-baseline"


def test_the_exemption_runs_the_same_per_entry_grading_as_an_unexempt_record():
    """The exemption excuses the entry-count comparison and nothing else."""
    source = inspect.getsource(tnp_guard._grade_record)
    assert source.count("_grade_entries(doc, record") == 2


def test_the_element_map_version_probes_keep_both_declared_wire_types():
    hints = get_type_hints(shim.element_map_version)
    assert hints["return"] == (int | None)
    assert get_type_hints(shim.element_map_version_string)["return"] == (str | None)


def test_both_element_map_probes_are_warmed():
    source = inspect.getsource(shim.warm_capability_probes)
    assert "element_map_version_string()" in source
    assert "element_map_version()" in source


def test_the_audit_banner_reads_the_verbatim_version_string():
    """TnpAuditBlock types element_map_version str | None; the int probe would truncate it."""
    assert "element_map_version_string" in inspect.getsource(tnp_guard._element_map_version_banner)
    assert "element_map_version_string" in inspect.getsource(transaction._unrun_tnp_audit)


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


def test_assertions_module_imports_without_freecad_and_declares_fourteen_fns():
    assert assertions.SUPPORTED_FNS == {
        "is_valid_solid",
        "count_cylindrical_holes",
        "hole_diameter",
        "hole_position",
        "hole_spacing",
        "hole_through",
        "distance_between",
        "angle_between",
        "expect_bbox",
        "expect_extent",
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
    assert primitives._band({"abs": 0.5}, 100.0, 0.05, None) == 0.5
    assert primitives._band({"rel": 0.001}, 100.0, None, 0.01) == pytest.approx(0.1)
    assert primitives._band(None, 100.0, None, 0.01) == pytest.approx(1.0)
    assert primitives._band(None, 10.0, 0.05, None) == 0.05
