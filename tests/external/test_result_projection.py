"""``result_projection`` tests: the ``fcb.mutation/2`` wire block and the record cache (no FreeCAD).

Covers the story 11.2 I/O matrix rows that need no document: a commit, a no-op, a proven and an
unproven rollback, an object on one side only, a missing after-record and a FLAGGED audit. The undo
rows run in-FreeCAD in ``tests/infc/test_document_undo.py``. Every projected block is validated
against the emitted ``/2`` schema, and the input full blocks against the retained ``/1`` schema.
"""

from __future__ import annotations

import json
from pathlib import Path

import jsonschema
import pytest

from freecad_buddy.contracts import massprops_changed, massprops_equal
from freecad_buddy.usecases import result_projection
from freecad_buddy.usecases.result_projection import (
    changed_objects,
    project_mutation,
    recall,
    remember,
    wire_audit,
    wire_fingerprint,
)

SCHEMA_DIR = Path(__file__).resolve().parents[2] / "src/freecad_buddy/contracts/jsonschema"


def _schema(relative: str) -> dict:
    return json.loads((SCHEMA_DIR / relative).read_text(encoding="utf-8"))


def _massprops(volume: float, area: float = 100.0, com=(1.0, 2.0, 3.0), inertia=True) -> dict:
    massprops = {
        "volume": volume,
        "area": area,
        "bbox": [0.0, 0.0, 0.0, 10.0, 10.0, 10.0],
        "com": list(com),
        "principal_moments": [volume, volume, volume],
        "quantum": 1e-6,
    }
    if inertia:
        massprops["inertia"] = [volume, volume, volume, 0.0, 0.0, 0.0]
    return massprops


def _record(digest: str, **objects: dict) -> dict:
    return {
        "schema": "fcb.fingerprint/1",
        "serializer": "exportBinary",
        "objects": [
            {"name": name, "brep_sha256": f"{name}-{digest}", "massprops": massprops}
            for name, massprops in sorted(objects.items())
        ],
        "digest": digest,
    }


def _finding(owner: str, verdict: str) -> dict:
    return {"owner": owner, "prop": "Profile", "verdict": verdict, "layer": 1}


def _full_block(
    before: dict | None,
    after: dict | None,
    passed: bool = True,
    rolled_back: bool = False,
    rollback_proven: str | None = None,
    snapshot_path: str | None = None,
    findings: list | None = None,
) -> dict:
    """A full block exactly as ``transaction._mutation_block`` builds it."""
    return {
        "schema": "fcb.mutation/1",
        "transaction_id": "0",
        "fingerprint_before": before,
        "fingerprint_after": after,
        "post_verify": {
            "recompute_clean": True,
            "is_valid": True,
            "fully_constrained": None,
            "tnp_audit": {
                "status": "CLEAN",
                "element_map_version": "4",
                "findings": list(findings or []),
            },
            "passed": passed,
            "explanation": None if passed else "verify_shape failed on Pad: volume",
        },
        "rolled_back": rolled_back,
        "rollback_proven": rollback_proven,
        "snapshot_path": snapshot_path,
        "verify_verdict": "OK" if passed else "SPEC_FAILED",
        "params_digest": "e" * 64,
        "touched": ["Pad"],
    }


BOX = _massprops(1000.0)
BOX_RESIZED = _massprops(1500.0, area=130.0, com=(1.5, 2.0, 3.0))
PAD = _massprops(200.0, area=40.0, com=(5.0, 5.0, 1.0))


@pytest.fixture(autouse=True)
def _empty_cache():
    result_projection._records.clear()
    yield
    result_projection._records.clear()


# ---- the I/O matrix ----------------------------------------------------------------------------


def test_should_list_each_new_and_modified_object_with_its_after_values_when_a_pad_commits():
    # Arrange
    before = _record("a" * 64, Box=BOX)
    after = _record("b" * 64, Box=BOX_RESIZED, Pad=PAD)
    target = _full_block(before, after)

    # Act
    block = project_mutation(target)

    # Assert
    assert block["fingerprint_before"] == {"digest": "a" * 64, "serializer": "exportBinary"}
    assert block["fingerprint_after"] == {"digest": "b" * 64, "serializer": "exportBinary"}
    assert block["changed"] == [
        {"name": "Box", "volume": 1500.0, "area": 130.0, "com": [1.5, 2.0, 3.0]},
        {"name": "Pad", "volume": 200.0, "area": 40.0, "com": [5.0, 5.0, 1.0]},
    ]


def test_should_report_no_changed_object_when_the_invariants_are_equal():
    # Arrange
    before = _record("a" * 64, Box=BOX)
    after = _record("c" * 64, Box=dict(BOX, bbox=[0.0, 0.0, 0.0, 10.1, 10.0, 10.0]))

    # Act
    block = project_mutation(_full_block(before, after))

    # Assert
    assert block["changed"] == []


def test_should_report_no_changed_object_when_a_failed_mutation_was_rolled_back_and_proven():
    # Arrange
    before = _record("a" * 64, Box=BOX)
    after = _record("a" * 64, Box=BOX)
    target = _full_block(
        before, after, passed=False, rolled_back=True, rollback_proven="rolled_back_verified"
    )

    # Act
    block = project_mutation(target)

    # Assert
    assert block["changed"] == []
    assert block["rolled_back"] is True
    assert block["rollback_proven"] == "rolled_back_verified"


def test_should_carry_both_mass_properties_on_each_entry_when_the_rollback_was_not_proven():
    # Arrange
    before = _record("a" * 64, Box=BOX)
    after = _record("b" * 64, Box=BOX_RESIZED)
    snapshot_path = "C:/work/FCB_TMP_snap_1/D.FCStd"
    target = _full_block(before, after, passed=False, snapshot_path=snapshot_path)

    # Act
    block = project_mutation(target)

    # Assert
    assert block["changed"] == [
        {
            "name": "Box",
            "volume": 1500.0,
            "area": 130.0,
            "com": [1.5, 2.0, 3.0],
            "before": BOX,
            "after": BOX_RESIZED,
        }
    ]
    assert block["rolled_back"] is False
    assert block["rollback_proven"] is None
    assert block["snapshot_path"] == "C:/work/FCB_TMP_snap_1/D.FCStd"


def test_should_report_null_after_values_when_a_committed_mutation_deleted_an_object():
    # Arrange
    before = _record("a" * 64, Box=BOX, Pad=PAD)
    after = _record("b" * 64, Box=BOX)

    # Act
    block = project_mutation(_full_block(before, after))

    # Assert
    assert block["changed"] == [{"name": "Pad", "volume": None, "area": None, "com": None}]


def test_should_report_a_null_before_side_when_a_failed_mutation_kept_a_created_object():
    # Arrange
    before = _record("a" * 64, Box=BOX)
    after = _record("b" * 64, Box=BOX, Pad=PAD)

    # Act
    block = project_mutation(_full_block(before, after, passed=False))

    # Assert
    assert block["changed"] == [
        {
            "name": "Pad",
            "volume": 200.0,
            "area": 40.0,
            "com": [5.0, 5.0, 1.0],
            "before": None,
            "after": PAD,
        }
    ]


@pytest.mark.parametrize("before", [_record("a" * 64, Box=BOX), None])
def test_should_report_a_null_after_fingerprint_and_no_change_when_no_after_record_exists(before):
    # Arrange
    target = _full_block(before, None, passed=False)

    # Act
    block = project_mutation(target)

    # Assert
    assert block["fingerprint_after"] is None
    assert block["changed"] == []


def test_should_count_every_verdict_and_keep_only_non_pass_findings_when_the_audit_flagged():
    # Arrange
    findings = (
        [_finding(f"Pad{i:03d}", "PASS") for i in range(40)]
        + [_finding("Fillet", "REPOINTED"), _finding("Chamfer", "REPOINTED")]
        + [_finding("Sketch", "RE_BASELINED")]
    )
    target = {"status": "FLAGGED", "element_map_version": "4", "findings": findings}

    # Act
    audit = wire_audit(target)

    # Assert
    assert audit == {
        "status": "FLAGGED",
        "element_map_version": "4",
        "counts": {"PASS": 40, "REPOINTED": 2, "RE_BASELINED": 1},
        "findings": findings[40:],
    }


def test_should_project_the_post_verify_audit_when_a_mutation_is_projected():
    # Arrange
    findings = [_finding("Pad", "PASS"), _finding("Sketch", "RE_BASELINED")]
    target = _full_block(_record("a" * 64, Box=BOX), _record("a" * 64, Box=BOX), findings=findings)

    # Act
    audit = project_mutation(target)["post_verify"]["tnp_audit"]

    # Assert
    assert audit["counts"] == {"PASS": 1, "RE_BASELINED": 1}
    assert audit["findings"] == [findings[1]]


# ---- the dropped fields ------------------------------------------------------------------------


def test_should_drop_the_audit_only_fields_and_a_null_snapshot_path_when_projecting():
    # Arrange
    target = _full_block(_record("a" * 64, Box=BOX), _record("b" * 64, Box=BOX_RESIZED))

    # Act
    block = project_mutation(target)

    # Assert
    assert block["schema"] == "fcb.mutation/2"
    for field in ("transaction_id", "verify_verdict", "params_digest", "snapshot_path"):
        assert field not in block
    assert block["touched"] == ["Pad"]


def test_should_leave_the_full_block_unchanged_when_projecting():
    # Arrange
    target = _full_block(
        _record("a" * 64, Box=BOX), _record("b" * 64, Box=BOX), findings=[_finding("P", "PASS")]
    )
    snapshot = json.dumps(target, sort_keys=True)

    # Act
    project_mutation(target)

    # Assert
    assert json.dumps(target, sort_keys=True) == snapshot


# ---- the schemas -------------------------------------------------------------------------------


def test_should_validate_against_the_v2_schema_when_a_recorded_v1_block_is_projected():
    # Arrange
    target = _full_block(
        _record("a" * 64, Box=BOX),
        _record("b" * 64, Box=BOX, Pad=PAD),
        passed=False,
        snapshot_path="C:/work/FCB_TMP_snap_1/D.FCStd",
        findings=[_finding("Pad", "PASS"), _finding("Sketch", "BROKEN")],
    )
    jsonschema.Draft202012Validator(_schema("retained/mutation-1.schema.json")).validate(target)

    # Act
    block = project_mutation(target)

    # Assert
    jsonschema.Draft202012Validator(_schema("mutation.schema.json")).validate(block)


@pytest.mark.parametrize(
    ("relative", "schema_id"),
    [
        ("mutation.schema.json", "fcb.mutation/2"),
        ("geometry-diff.schema.json", "fcb.geometry-diff/2"),
        ("retained/mutation-1.schema.json", "fcb.mutation/1"),
        ("retained/geometry-diff-1.schema.json", "fcb.geometry-diff/1"),
    ],
)
def test_should_carry_its_major_in_the_id_when_a_schema_is_emitted_or_retained(relative, schema_id):
    # Arrange
    path = relative

    # Act
    schema = _schema(path)

    # Assert
    assert schema["$id"] == schema_id


# ---- the record cache --------------------------------------------------------------------------


def test_should_recall_the_full_record_when_its_wire_form_was_published():
    # Arrange
    record = _record("a" * 64, Box=BOX)

    # Act
    wire_fingerprint(record)

    # Assert
    assert recall("a" * 64) is record


def test_should_recall_nothing_when_a_digest_was_never_published():
    # Arrange
    digest = "f" * 64

    # Act
    record = recall(digest)

    # Assert
    assert record is None


def test_should_evict_the_least_recently_used_record_when_the_bound_is_exceeded():
    # Arrange
    bound = result_projection._CACHE_SIZE
    digests = [f"{i:064x}" for i in range(bound + 1)]
    for digest in digests[:bound]:
        remember(_record(digest, Box=BOX))
    recall(digests[0])

    # Act
    remember(_record(digests[bound], Box=BOX))

    # Assert
    assert len(result_projection._records) == bound
    assert recall(digests[0]) is not None
    assert recall(digests[1]) is None
    assert recall(digests[bound]) is not None


# ---- the comparison it shares with massprops_equal --------------------------------------------


@pytest.mark.parametrize(
    ("before", "after", "expected"),
    [
        ({"Box": BOX}, {"Box": BOX}, []),
        ({"Box": BOX}, {"Box": BOX_RESIZED}, ["Box"]),
        ({"Box": BOX}, {"Box": BOX, "Pad": PAD}, ["Pad"]),
        ({"Box": _massprops(1000.0, inertia=False)}, {"Box": BOX}, ["Box"]),
    ],
)
def test_should_name_exactly_the_objects_massprops_equal_would_reject(before, after, expected):
    # Arrange
    left = _record("a" * 64, **before)
    right = _record("b" * 64, **after)

    # Act
    names = massprops_changed(left, right)

    # Assert
    assert names == expected
    assert massprops_equal(left, right) is (not expected)


def test_should_report_no_changed_object_when_either_record_is_missing():
    # Arrange
    record = _record("a" * 64, Box=BOX)

    # Act
    changed = [changed_objects(record, None, True), changed_objects(None, record, False)]

    # Assert
    assert changed == [[], []]
