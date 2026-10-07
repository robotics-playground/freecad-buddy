"""Contract invariant tests. Non-tautological: schemas are validated
with the ``jsonschema`` dev dep, not just inspected for key presence."""

import json
import sys
import typing
from pathlib import Path
from types import MappingProxyType

import jsonschema
import pytest
from jsonschema import Draft202012Validator

REPO_ROOT = Path(__file__).resolve().parents[2]
PKG = REPO_ROOT / "src" / "freecad_buddy"
SCHEMA_DIR = PKG / "contracts" / "jsonschema"

sys.path.insert(0, str(REPO_ROOT / "scripts"))
import check_status_vocab  # noqa: E402
import gen_schemas  # noqa: E402

from freecad_buddy.contracts.envelope import mirror_text  # noqa: E402
from freecad_buddy.contracts.fingerprint import fingerprints_equal, massprops_equal  # noqa: E402
from freecad_buddy.contracts.report import (  # noqa: E402
    MeasuredKind,
    derive_verdict,
    require_wilson_ci_for_rates,
)


def _load(stem: str) -> dict:
    return json.loads((SCHEMA_DIR / f"{stem}.schema.json").read_text(encoding="utf-8"))


def _root_validator(stem: str) -> Draft202012Validator:
    return Draft202012Validator(_load(stem))


def _def_validator(stem: str, def_name: str) -> Draft202012Validator:
    """A validator scoped to an embedded ``$def`` (its ``$ref`` context resolved)."""
    schema = _load(stem)
    sub = dict(schema["$defs"][def_name])
    sub["$defs"] = schema["$defs"]
    return Draft202012Validator(sub)


# --------------------------------------------------------------------------- #
# byte-identical regeneration + drift/orphan failure path
# --------------------------------------------------------------------------- #


def test_schemas_regenerate_byte_identical():
    expected = gen_schemas.generate()
    for name, text in expected.items():
        on_disk = (SCHEMA_DIR / name).read_text(encoding="utf-8")
        assert on_disk == text, f"{name} drifted from generator output"


def test_gen_schemas_check_baseline_exits_zero():
    assert gen_schemas.check() == []


def test_gen_schemas_check_detects_drift(tmp_path):
    for name, text in gen_schemas.generate().items():
        (tmp_path / name).write_text(text, encoding="utf-8", newline="\n")
    drifted = tmp_path / "validation-report.schema.json"
    drifted.write_text(drifted.read_text(encoding="utf-8") + " ", encoding="utf-8")
    problems = gen_schemas.check(tmp_path)
    assert any("drift" in p for p in problems), problems


def test_gen_schemas_check_detects_orphan(tmp_path):
    for name, text in gen_schemas.generate().items():
        (tmp_path / name).write_text(text, encoding="utf-8", newline="\n")
    (tmp_path / "stale-removed.schema.json").write_text("{}\n", encoding="utf-8")
    problems = gen_schemas.check(tmp_path)
    assert any("orphan" in p for p in problems), problems


# --------------------------------------------------------------------------- #
# _schema_for tuple/set array projections
# --------------------------------------------------------------------------- #


def test_schema_for_variadic_tuple():
    assert gen_schemas._schema_for(tuple[float, ...], {}) == {
        "type": "array",
        "items": {"type": "number"},
    }


def test_schema_for_fixed_tuple():
    assert gen_schemas._schema_for(tuple[float, float, float], {}) == {
        "type": "array",
        "prefixItems": [{"type": "number"}, {"type": "number"}, {"type": "number"}],
        "minItems": 3,
        "maxItems": 3,
    }


def test_schema_for_bare_tuple():
    assert gen_schemas._schema_for(tuple, {}) == {"type": "array"}


def test_schema_for_empty_tuple():
    assert gen_schemas._schema_for(tuple[()], {}) == {"type": "array", "maxItems": 0}


def test_schema_for_parameterized_set():
    assert gen_schemas._schema_for(set[str], {}) == {
        "type": "array",
        "uniqueItems": True,
        "items": {"type": "string"},
    }


def test_schema_for_bare_set():
    assert gen_schemas._schema_for(set, {}) == {"type": "array", "uniqueItems": True}


def test_schema_for_single_element_tuple():
    assert gen_schemas._schema_for(tuple[float], {}) == {
        "type": "array",
        "prefixItems": [{"type": "number"}],
        "minItems": 1,
        "maxItems": 1,
    }


def test_schema_for_heterogeneous_fixed_tuple():
    assert gen_schemas._schema_for(tuple[str, int, bool], {}) == {
        "type": "array",
        "prefixItems": [
            {"type": "string"},
            {"type": "integer"},
            {"type": "boolean"},
        ],
        "minItems": 3,
        "maxItems": 3,
    }


def test_schema_for_parameterized_frozenset():
    assert gen_schemas._schema_for(frozenset[int], {}) == {
        "type": "array",
        "uniqueItems": True,
        "items": {"type": "integer"},
    }


def test_schema_for_bare_frozenset():
    assert gen_schemas._schema_for(frozenset, {}) == {"type": "array", "uniqueItems": True}


def test_schema_for_typing_alias_containers():
    assert gen_schemas._schema_for(typing.Tuple, {}) == {"type": "array"}
    assert gen_schemas._schema_for(typing.Set, {}) == {"type": "array", "uniqueItems": True}
    assert gen_schemas._schema_for(typing.FrozenSet, {}) == {
        "type": "array",
        "uniqueItems": True,
    }


def test_schema_for_misplaced_ellipsis_raises():
    with pytest.raises(ValueError, match="Ellipsis"):
        gen_schemas._schema_for(tuple[int, ..., str], {})


def test_schema_for_nested_typeddict_in_tuple_registers_def():
    from freecad_buddy.contracts.report import Check

    defs: dict = {}
    schema = gen_schemas._schema_for(tuple[Check, ...], defs)
    assert schema["items"] == {"$ref": "#/$defs/Check"}
    assert "Check" in defs


# --------------------------------------------------------------------------- #
# required-field enforcement — root + embedded $def {}-rejection
# --------------------------------------------------------------------------- #


def test_empty_object_rejected_for_every_wire_root():
    for stem in (
        "result-envelope",
        "validation-report",
        "job-status",
        "audit-record",
        "geometry-diff",
        "fingerprint",
        "capability-banner",
    ):
        assert not _root_validator(stem).is_valid({}), f"{stem} must reject {{}}"


def test_validation_report_banner_required():
    v = _root_validator("validation-report")
    assert "banner" in _load("validation-report")["required"]
    good = {
        "schema": "fcb.validation-report/1",
        "banner": {"freecad_version": "1.0.2", "element_map_version": None},
        "checks": [],
        "verdict": "OK",
    }
    assert v.is_valid(good)
    del good["banner"]
    assert not v.is_valid(good)


def test_result_envelope_status_content_text_required():
    req = _load("result-envelope")["required"]
    for field in ("schema", "status", "structured_content", "text"):
        assert field in req
    v = _root_validator("result-envelope")
    assert not v.is_valid({"schema": "fcb.result-envelope/1", "status": "OK"})
    assert v.is_valid(
        {
            "schema": "fcb.result-envelope/1",
            "status": "OK",
            "structured_content": {},
            "text": "{}",
        }
    )


def test_audit_record_ts_actor_event_required():
    req = _load("audit-record")["required"]
    for field in ("ts", "actor", "event"):
        assert field in req
    assert not _root_validator("audit-record").is_valid({"schema": "fcb.audit-record/1"})


def test_job_status_state_required():
    assert "state" in _load("job-status")["required"]
    assert not _root_validator("job-status").is_valid({"schema": "fcb.job-status/1"})


def test_dochandle_handle_required_on_document_touching_objects():
    for stem in ("audit-record", "geometry-diff"):
        doc = _load(stem)["$defs"]["DocHandle"]
        assert "handle" in doc["required"]
        assert not _def_validator(stem, "DocHandle").is_valid({})
        assert _def_validator(stem, "DocHandle").is_valid({"handle": "d1"})


def test_error_detail_def_rejects_empty():
    assert not _def_validator("result-envelope", "ErrorDetail").is_valid({})
    assert _def_validator("result-envelope", "ErrorDetail").is_valid({"message": "boom"})


def test_report_banner_def_rejects_empty():
    v = _def_validator("validation-report", "ReportBanner")
    assert not v.is_valid({})
    assert v.is_valid({"freecad_version": "1.0.2", "element_map_version": None})


def test_check_def_rejects_empty():
    """Check.passed is design-required; the $def must reject {}."""
    ck = _load("validation-report")["$defs"]["Check"]
    assert "passed" in ck["required"]
    v = _def_validator("validation-report", "Check")
    assert not v.is_valid({}), "Check {} must FAIL"
    assert v.is_valid({"passed": True})


def test_capability_banner_positive_and_vocab_rejection():
    """A full valid banner validates; off-vocabulary render/serializer values are rejected."""
    v = _root_validator("capability-banner")
    good = {
        "freecad_version": "1.1.0",
        "element_map_available": True,
        "serializer": "exportBinary",
        "varset_backend": "varset",
        "render": "none",
        "sketcher_available": True,
        "partdesign_available": True,
        "enums": {},
        "exec_enabled": False,
    }
    assert v.is_valid(good)
    assert not v.is_valid({**good, "render": "offscren"})
    assert not v.is_valid({**good, "serializer": "bogus"})


def test_capability_banner_annotations_match_manifest():
    """The manifest's required set equals the TypedDict field set (no silent rot)."""
    from freecad_buddy.contracts.capabilities import CapabilityBanner

    assert set(CapabilityBanner.__annotations__) == set(
        gen_schemas.REQUIRED_FIELDS["CapabilityBanner"]
    )


# --------------------------------------------------------------------------- #
# manifest-completeness audit: expected-required table == emitted required
# --------------------------------------------------------------------------- #

EXPECTED_REQUIRED = {
    "ResultEnvelope": {"schema", "status", "structured_content", "text"},
    "ValidationReport": {"schema", "banner", "checks", "verdict"},
    "JobStatus": {"schema", "state"},
    "AuditRecord": {"schema", "ts", "actor", "event"},
    "GeometryDiff": {"schema", "deltas", "counts", "validity", "tnp_precheck"},
    "FingerprintRecord": {"schema", "serializer", "objects", "digest"},
    "CapabilityBanner": {
        "freecad_version",
        "element_map_available",
        "serializer",
        "varset_backend",
        "render",
        "sketcher_available",
        "partdesign_available",
        "enums",
        "exec_enabled",
    },
    # The grading fields are present only when `readable` is true.
    "SketchState": {"schema", "sketch", "readable"},
    "FeatureState": {"schema", "feature", "readable"},
    "ShapeSummary": {
        "volume",
        "area",
        "bbox",
        "solid_count",
        "face_count",
        "edge_count",
        "vertex_count",
        "is_valid",
    },
    "ConstraintRef": {"id"},
    "ErrorDetail": {"message"},
    "ReportBanner": {"freecad_version", "element_map_version"},
    "Check": {"passed"},
    "DocHandle": {"handle"},
    "ObjectFingerprint": {"name", "brep_sha256", "massprops"},
    "MassProps": {"volume", "area", "bbox", "com", "principal_moments", "quantum"},
    "WilsonCI": {"rate", "low", "high", "n", "r"},
    # ImageRef/ResultEnvelope-nested carry their own (or empty) required sets,
    # verified generically below.
}


def _all_titled_objects():
    """Yield (title, schema-obj) for every wire root and every emitted $def."""
    for stem, _ in gen_schemas.WIRE_ROOTS:
        schema = _load(stem)
        yield schema["title"], schema
        for def_name, def_obj in schema.get("$defs", {}).items():
            yield def_name, def_obj


def test_manifest_completeness_audit():
    """Every emitted root/$def whose type has an expected-required set matches it exactly,
    so a future added-but-unlisted required field fails here rather than shipping."""
    seen = set()
    for title, obj in _all_titled_objects():
        emitted = set(obj.get("required", []))
        if title in EXPECTED_REQUIRED:
            assert emitted == EXPECTED_REQUIRED[title], (
                f"{title}: emitted required {emitted} != expected "
                f"{EXPECTED_REQUIRED[title]}"
            )
            seen.add(title)
    for title in EXPECTED_REQUIRED:
        assert title in seen, f"expected type {title} was never emitted"


def test_every_required_field_is_a_property():
    """Self-consistency: required ⊆ properties for every emitted root/$def."""
    for title, obj in _all_titled_objects():
        req = set(obj.get("required", []))
        props = set(obj.get("properties", {}))
        assert req <= props, f"{title}: required {req - props} not in properties"


def test_generator_guard_raises_on_bogus_required(monkeypatch):
    """The self-consistency guard raises if a manifest entry names a non-property."""
    monkeypatch.setitem(
        gen_schemas.REQUIRED_FIELDS, "Check", ["passed", "does_not_exist"]
    )
    with pytest.raises(ValueError, match="does_not_exist"):
        gen_schemas.generate()


# --------------------------------------------------------------------------- #
# status vocabulary enforcement
# --------------------------------------------------------------------------- #


def test_status_members_has_all_nine():
    members = check_status_vocab._status_members()
    assert len(members) == 9
    assert {"QUEUED", "RUNNING"} <= members


def test_status_vocab_clean_on_real_tree():
    assert check_status_vocab.check_tree(PKG) == []


def _plant(tmp_path: Path, filename: str, source: str) -> Path:
    pkg = tmp_path / "freecad_buddy"
    (pkg / "contracts").mkdir(parents=True)
    (pkg / "contracts" / "status.py").write_text("", encoding="utf-8")
    target = pkg / filename
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(source, encoding="utf-8")
    return pkg


def test_status_vocab_flags_plain_literal_leak(tmp_path):
    pkg = _plant(
        tmp_path,
        "usecases/leak.py",
        'from typing import Literal\nBad = Literal["OK", "SPEC_FAILED"]\n',
    )
    v = check_status_vocab.check_tree(pkg)
    assert any("leak.py" in str(x) for x in v)


def test_status_vocab_flags_alias_import_leak(tmp_path):
    pkg = _plant(
        tmp_path,
        "usecases/leak.py",
        'from typing import Literal as L\nBad = L["OK", "INVALID_INPUT"]\n',
    )
    v = check_status_vocab.check_tree(pkg)
    assert any("leak.py" in str(x) for x in v)


def test_status_vocab_flags_attribute_form_leak(tmp_path):
    pkg = _plant(
        tmp_path,
        "usecases/leak.py",
        'import typing\nBad = typing.Literal["OK", "TIMEOUT"]\n',
    )
    v = check_status_vocab.check_tree(pkg)
    assert any("leak.py" in str(x) for x in v)


def test_status_vocab_flags_jobstate_leak(tmp_path):
    pkg = _plant(
        tmp_path,
        "usecases/leak.py",
        'from typing import Literal\nBad = Literal["QUEUED", "RUNNING"]\n',
    )
    v = check_status_vocab.check_tree(pkg)
    assert any("leak.py" in str(x) for x in v), "job-state QUEUED/RUNNING leak must flag"


def test_status_vocab_owner_exempt_only_by_relative_path(tmp_path):
    """A file merely named status.py in another ring is NOT exempt."""
    pkg = _plant(
        tmp_path,
        "usecases/status.py",
        'from typing import Literal\nBad = Literal["OK", "SPEC_FAILED"]\n',
    )
    v = check_status_vocab.check_tree(pkg)
    assert any("usecases/status.py" in str(x) for x in v)


# --------------------------------------------------------------------------- #
# text-mirror round-trip
# --------------------------------------------------------------------------- #


def test_text_mirror_round_trip():
    content = {"report": {"verdict": "OK"}, "z": 1, "a": [3, 2, 1]}
    text = mirror_text(content)
    # Verify determinism: calling mirror_text twice returns the same text
    assert text == mirror_text(content)
    # Verify compact format: shows container counts, not full JSON dump
    assert "report: {1 fields}" in text
    assert "a: [3 items]" in text
    assert "z: 1" in text


# --------------------------------------------------------------------------- #
# diff/audit vocabulary identity
# --------------------------------------------------------------------------- #


def test_diff_audit_vocabulary_identity():
    from freecad_buddy.contracts.audit import AuditRecord
    from freecad_buddy.contracts.diff import GeometryDiff

    diff_fields = set(GeometryDiff.__annotations__)
    audit_fields = set(AuditRecord.__annotations__)
    shared = {"touched", "new", "deleted"}
    assert shared & diff_fields == shared
    assert "fingerprint_before" in diff_fields
    assert "fingerprint_before" in audit_fields


# --------------------------------------------------------------------------- #
# fingerprints_equal
# --------------------------------------------------------------------------- #


def _fp(serializer, digest):
    return {
        "schema": "fcb.fingerprint/1",
        "serializer": serializer,
        "objects": [],
        "digest": digest,
    }


def test_fingerprints_equal_equal_and_differ():
    assert fingerprints_equal(_fp("exportBinary", "sha256:aa"), _fp("exportBinary", "sha256:aa"))
    assert not fingerprints_equal(
        _fp("exportBinary", "sha256:aa"), _fp("exportBinary", "sha256:bb")
    )


def test_fingerprints_equal_cross_tag_raises():
    with pytest.raises(ValueError):
        fingerprints_equal(_fp("exportBinary", "sha256:aa"), _fp("exportBrep", "sha256:aa"))


def test_fingerprints_equal_missing_serializer_raises():
    with pytest.raises(ValueError):
        fingerprints_equal({"digest": "sha256:aa"}, _fp("exportBinary", "sha256:aa"))


def test_fingerprints_equal_missing_digest_both_none_raises():
    with pytest.raises(ValueError):
        fingerprints_equal(_fp("exportBinary", None), _fp("exportBinary", None))


def _massprops(volume):
    return {
        "volume": volume,
        "area": 0.0 if volume == 0.0 else 6.0,
        "bbox": [0.0] * 6,
        "com": [0.0] * 3,
        "principal_moments": [0.0] * 3,
        "inertia": [0.0] * 6,
        "quantum": 1e-6,
    }


def _fp_objects(*entries):
    record = _fp("exportBinary", "sha256:aa")
    record["objects"] = [
        {"name": name, "brep_sha256": "b", "massprops": massprops} for name, massprops in entries
    ]
    return record


def test_massprops_equal_is_false_when_the_object_name_sets_differ():
    left = _fp_objects(("Pad", _massprops(1.0)))
    right = _fp_objects(("Pad", _massprops(1.0)), ("Fillet", _massprops(1.0)))

    assert not massprops_equal(left, right)


def test_a_zeroed_null_shape_entry_equals_itself_and_differs_from_a_real_one():
    null_shape = _fp_objects(("Fillet", _massprops(0.0)))
    real_shape = _fp_objects(("Fillet", _massprops(1.0)))

    assert massprops_equal(null_shape, _fp_objects(("Fillet", _massprops(0.0))))
    assert not massprops_equal(null_shape, real_shape)


def test_should_be_unequal_when_only_the_inertia_tensor_differs():
    # Arrange
    mirrored = _massprops(1.0)
    mirrored["inertia"] = [0.0, 0.0, 0.0, 180000.0, 0.0, 0.0]
    before = _fp_objects(("Pad", _massprops(1.0)))
    after = _fp_objects(("Pad", mirrored))

    # Act
    equal = massprops_equal(before, after)

    # Assert
    assert not equal


def test_should_be_unequal_when_a_record_has_no_inertia():
    # Arrange
    old_massprops = _massprops(1.0)
    del old_massprops["inertia"]
    old_record = _fp_objects(("Pad", old_massprops))
    new_record = _fp_objects(("Pad", _massprops(1.0)))

    # Act
    old_against_new = massprops_equal(old_record, new_record)
    old_against_itself = massprops_equal(old_record, old_record)

    # Assert
    assert not old_against_new
    assert not old_against_itself


# --------------------------------------------------------------------------- #
# derive_verdict
# --------------------------------------------------------------------------- #


def _ck(passed, code=None):
    check = {"passed": passed}
    if code is not None:
        check["detail"] = {"code": code}
    return check


def test_verdict_all_pass_ok():
    assert derive_verdict({"checks": [_ck(True), _ck(True)]}) == "OK"


def test_verdict_spec_fail():
    assert derive_verdict({"checks": [_ck(True), _ck(False)]}) == "SPEC_FAILED"


def test_verdict_recompute_fail():
    assert derive_verdict({"checks": [_ck(False, "recompute.failed_objects")]}) == "RECOMPUTE_ERROR"


def test_verdict_invalid_input_prefix():
    assert derive_verdict({"checks": [_ck(False, "invalid_input.bad_param")]}) == "INVALID_INPUT"


def test_verdict_malformed_suffix():
    assert derive_verdict({"checks": [_ck(False, "sketch.malformed")]}) == "INVALID_INPUT"


def test_verdict_tnp_unsupported_is_spec_failed():
    assert derive_verdict({"checks": [_ck(False, "tnp.unsupported")]}) == "SPEC_FAILED"


def test_verdict_precedence_order_independent():
    forward = [_ck(False, "shape.volume_mismatch"), _ck(False, "recompute.failed_objects")]
    assert derive_verdict({"checks": forward}) == "RECOMPUTE_ERROR"
    assert derive_verdict({"checks": list(reversed(forward))}) == "RECOMPUTE_ERROR"


def test_verdict_invalid_over_spec_precedence():
    checks = [_ck(False, "shape.volume_mismatch"), _ck(False, "invalid_input.bad")]
    assert derive_verdict({"checks": checks}) == "INVALID_INPUT"
    assert derive_verdict({"checks": list(reversed(checks))}) == "INVALID_INPUT"


def test_verdict_empty_and_missing_checks_ok():
    assert derive_verdict({"checks": []}) == "OK"
    assert derive_verdict({}) == "OK"


def test_verdict_non_list_checks_safe():
    assert derive_verdict({"checks": {"not": "a list"}}) == "OK"
    assert derive_verdict({"checks": "nope"}) == "OK"


def test_verdict_non_dict_detail_degrades_to_spec_failed():
    assert derive_verdict({"checks": [{"passed": False, "detail": None}]}) == "SPEC_FAILED"
    assert derive_verdict({"checks": [{"passed": False, "detail": "oops"}]}) == "SPEC_FAILED"
    assert derive_verdict({"checks": [{"passed": False}]}) == "SPEC_FAILED"


# --------------------------------------------------------------------------- #
# rate check ⇒ banner.wilson_ci (schema conditional + runtime guard)
# --------------------------------------------------------------------------- #

_WILSON_CI = {"rate": 0.9, "low": 0.8, "high": 0.95, "n": 30, "r": 27}


def _rate_ck(kind="rate", check_id="gate.pass_rate"):
    check = {"id": check_id, "passed": True, "measured": 0.9}
    if kind is not None:
        check["measured_kind"] = kind
    return check


def _report(checks=None, warnings=None, banner_extra=None):
    banner = {"freecad_version": "1.0.2", "element_map_version": None}
    if banner_extra is not None:
        banner.update(banner_extra)
    report = {
        "schema": "fcb.validation-report/1",
        "banner": banner,
        "checks": [] if checks is None else checks,
        "verdict": "OK",
    }
    if warnings is not None:
        report["warnings"] = warnings
    return report


def test_check_def_exposes_measured_kind_discriminator():
    props = _load("validation-report")["$defs"]["Check"]["properties"]
    assert "measured_kind" in props
    enum = props["measured_kind"]["anyOf"][0]["enum"]
    assert "rate" in enum
    assert "measured_kind" not in _load("validation-report")["$defs"]["Check"]["required"]


def test_validation_report_emits_draft2020_conditional():
    schema = _load("validation-report")
    assert "if" in schema and "then" in schema
    antecedent_fields = [
        next(iter(branch["properties"])) for branch in schema["if"]["anyOf"]
    ]
    assert antecedent_fields == ["checks", "warnings"]
    for field, branch in zip(antecedent_fields, schema["if"]["anyOf"], strict=True):
        assert branch["required"] == [field]
        array_field = branch["properties"][field]
        assert array_field["type"] == "array"
        contains = array_field["contains"]
        assert contains["properties"]["measured_kind"] == {"const": "rate"}
        assert contains["required"] == ["measured_kind"]
    banner_then = schema["then"]["properties"]["banner"]
    assert banner_then["type"] == "object"
    assert banner_then["required"] == ["wilson_ci"]
    assert banner_then["properties"]["wilson_ci"] == {"$ref": "#/$defs/WilsonCI"}


def test_no_rate_declared_schema_valid_and_guard_silent():
    report = _report(checks=[{"id": "shape.volume", "passed": True, "measured": 12.0}])
    assert _root_validator("validation-report").is_valid(report)
    assert require_wilson_ci_for_rates(report) is None


def test_rate_declared_with_wilson_ci_schema_valid_and_guard_silent():
    report = _report(checks=[_rate_ck()], banner_extra={"wilson_ci": _WILSON_CI})
    assert _root_validator("validation-report").is_valid(report)
    assert require_wilson_ci_for_rates(report) is None


def test_rate_declared_without_wilson_ci_rejected_by_both_surfaces():
    report = _report(checks=[_rate_ck()])
    assert not _root_validator("validation-report").is_valid(report)
    with pytest.raises(ValueError, match="gate.pass_rate"):
        require_wilson_ci_for_rates(report)


def test_rate_declared_with_null_wilson_ci_rejected_by_both_surfaces():
    report = _report(checks=[_rate_ck()], banner_extra={"wilson_ci": None})
    assert not _root_validator("validation-report").is_valid(report)
    with pytest.raises(ValueError, match="gate.pass_rate"):
        require_wilson_ci_for_rates(report)


def test_rate_declared_in_warnings_only_rejected_by_both_surfaces():
    report = _report(warnings=[_rate_ck(check_id="warn.flake_rate")])
    assert not _root_validator("validation-report").is_valid(report)
    with pytest.raises(ValueError, match="warn.flake_rate"):
        require_wilson_ci_for_rates(report)


def test_rate_declared_in_warnings_with_wilson_ci_accepted():
    report = _report(
        warnings=[_rate_ck(check_id="warn.flake_rate")],
        banner_extra={"wilson_ci": _WILSON_CI},
    )
    assert _root_validator("validation-report").is_valid(report)
    assert require_wilson_ci_for_rates(report) is None


def test_non_rate_discriminator_does_not_require_wilson_ci():
    for kind in ("quantity", "count", "flag", "text"):
        report = _report(checks=[_rate_ck(kind=kind)])
        assert _root_validator("validation-report").is_valid(report), kind
        assert require_wilson_ci_for_rates(report) is None


def test_null_discriminator_does_not_require_wilson_ci():
    explicit_null = _report(checks=[dict(_rate_ck(), measured_kind=None)])
    omitted = _report(checks=[_rate_ck(kind=None)])
    for report in (explicit_null, omitted):
        assert _root_validator("validation-report").is_valid(report)
        assert require_wilson_ci_for_rates(report) is None


def test_unknown_discriminator_value_rejected_by_schema():
    report = _report(checks=[_rate_ck(kind="ratio")])
    assert not _root_validator("validation-report").is_valid(report)


def test_guard_degrades_on_malformed_containers():
    for container in ({"not": "a list"}, "nope", None, 7):
        assert require_wilson_ci_for_rates({"checks": container}) is None
        assert require_wilson_ci_for_rates({"warnings": container}) is None
    assert require_wilson_ci_for_rates({"checks": ["nope", None, 7]}) is None
    assert require_wilson_ci_for_rates({}) is None


def test_a_rate_discriminator_over_a_non_numeric_measured_is_rejected():
    # measured_kind is the sole load-bearing signal of the wilson_ci rule and is declared
    # independently of measured's type, so without this a check satisfies the letter of the rule
    # while describing something that is not a rate.
    for measured in ("not-a-number", None, [0.9], True, False):
        report = _report(
            checks=[dict(_rate_ck(), measured=measured)],
            banner_extra={"wilson_ci": _WILSON_CI},
        )
        with pytest.raises(ValueError, match="gate.pass_rate"):
            require_wilson_ci_for_rates(report)


def test_a_rate_measured_outside_the_unit_interval_is_rejected():
    for measured in (-0.1, 1.1, float("nan"), float("inf")):
        report = _report(
            checks=[dict(_rate_ck(), measured=measured)],
            banner_extra={"wilson_ci": _WILSON_CI},
        )
        with pytest.raises(ValueError, match=r"not a number in \[0, 1\]"):
            require_wilson_ci_for_rates(report)


def test_the_unit_interval_bounds_are_inclusive_for_a_rate():
    for measured in (0, 1, 0.0, 1.0):
        report = _report(
            checks=[dict(_rate_ck(), measured=measured)],
            banner_extra={"wilson_ci": _WILSON_CI},
        )
        assert require_wilson_ci_for_rates(report) is None


def test_a_non_rate_discriminator_may_carry_any_measured_value():
    # The constraint is scoped to the rate discriminator; a count or a text check is free to
    # measure a string or a list.
    for kind in ("quantity", "count", "flag", "text"):
        report = _report(checks=[dict(_rate_ck(kind=kind), measured="anything")])
        assert require_wilson_ci_for_rates(report) is None


def test_guard_reports_unnamed_rate_check_without_id():
    report = _report(checks=[{"passed": True, "measured_kind": "rate"}])
    with pytest.raises(ValueError, match="<unnamed>"):
        require_wilson_ci_for_rates(report)


def test_guard_raises_on_non_dict_banner():
    report = {"checks": [_rate_ck()], "banner": "nope"}
    with pytest.raises(ValueError, match="gate.pass_rate"):
        require_wilson_ci_for_rates(report)


def test_guard_names_every_offending_rate_check():
    report = _report(
        checks=[_rate_ck(check_id="a.rate")],
        warnings=[_rate_ck(check_id="b.rate")],
    )
    with pytest.raises(ValueError, match="a.rate.*b.rate"):
        require_wilson_ci_for_rates(report)


def test_wilson_ci_def_requires_every_interval_field():
    """WilsonCI is total=True; the $def must reject {} and each partial interval."""
    full = _load("validation-report")["$defs"]["WilsonCI"]
    assert set(full["required"]) == set(_WILSON_CI)
    v = _def_validator("validation-report", "WilsonCI")
    assert not v.is_valid({})
    assert v.is_valid(_WILSON_CI)
    for dropped in _WILSON_CI:
        partial = {k: val for k, val in _WILSON_CI.items() if k != dropped}
        assert not v.is_valid(partial), f"WilsonCI without '{dropped}' must FAIL"


def test_rate_declared_with_empty_wilson_ci_rejected_by_both_surfaces():
    """An empty CI is not a CI: the real consumer reads wilson_ci['r']."""
    report = _report(checks=[_rate_ck()], banner_extra={"wilson_ci": {}})
    assert not _root_validator("validation-report").is_valid(report)
    with pytest.raises(ValueError, match="gate.pass_rate"):
        require_wilson_ci_for_rates(report)


def test_rate_declared_with_partial_wilson_ci_rejected_by_both_surfaces():
    for dropped in _WILSON_CI:
        partial = {k: v for k, v in _WILSON_CI.items() if k != dropped}
        report = _report(checks=[_rate_ck()], banner_extra={"wilson_ci": partial})
        assert not _root_validator("validation-report").is_valid(report), dropped
        with pytest.raises(ValueError, match=f"missing key\\(s\\) \\['{dropped}'\\]"):
            require_wilson_ci_for_rates(report)


def test_rate_declared_with_non_mapping_wilson_ci_rejected_by_both_surfaces():
    for ci in ("nope", 7, [0.9, 0.8]):
        report = _report(checks=[_rate_ck()], banner_extra={"wilson_ci": ci})
        assert not _root_validator("validation-report").is_valid(report), ci
        with pytest.raises(ValueError, match="gate.pass_rate"):
            require_wilson_ci_for_rates(report)


def test_guard_wilson_ci_key_set_tracks_the_typeddict():
    from freecad_buddy.contracts.report import _WILSON_CI_KEYS, WilsonCI

    assert _WILSON_CI_KEYS == {"rate", "low", "high", "n", "r"}
    assert _WILSON_CI_KEYS == set(WilsonCI.__required_keys__)


def test_guard_int_key_set_tracks_the_typeddict():
    from freecad_buddy.contracts.report import _WILSON_CI_INT_KEYS

    assert _WILSON_CI_INT_KEYS == {"n", "r"}
    integer_props = {
        key
        for key, prop in _load("validation-report")["$defs"]["WilsonCI"]["properties"].items()
        if prop.get("type") == "integer"
    }
    assert _WILSON_CI_INT_KEYS == integer_props


def _conditional_validator(stem: str) -> Draft202012Validator:
    """A validator carrying ONLY the schema's ``if``/``then`` (plus ``$defs``).

    Isolates the conditional so the base property types cannot mask whether the
    conditional itself accepts or rejects an instance.
    """
    schema = _load(stem)
    return Draft202012Validator(
        {
            "$schema": schema["$schema"],
            "if": schema["if"],
            "then": schema["then"],
            "$defs": schema["$defs"],
        }
    )


def test_conditional_antecedent_ignores_non_array_checks():
    """A non-array ``checks`` carries no rate check, so wilson_ci is not demanded."""
    v = _conditional_validator("validation-report")
    for container in ("not-a-list", 7, None, {"measured_kind": "rate"}):
        assert v.is_valid({"checks": container, "banner": {}}), container


def test_non_array_checks_not_accused_of_missing_wilson_ci():
    """The full schema rejects a non-array ``checks`` on type, never on wilson_ci."""
    report = _report()
    report["checks"] = "not-a-list"
    errors = list(_root_validator("validation-report").iter_errors(report))
    assert errors
    assert not any("wilson_ci" in e.message for e in errors), [e.message for e in errors]
    assert require_wilson_ci_for_rates(report) is None


def test_conditional_then_rejects_non_object_banner_on_its_own():
    """``then`` carries its own ``type: object`` so it does not rely on ReportBanner."""
    v = _conditional_validator("validation-report")
    for banner in ("nope", 7, [], None):
        assert not v.is_valid({"checks": [_rate_ck()], "banner": banner}), banner
    assert v.is_valid({"checks": [_rate_ck()], "banner": {"wilson_ci": _WILSON_CI}})


def test_guard_rejects_unknown_measured_kind():
    for kind in ("Rate", "rate ", "ratio", "RATE", 7):
        report = _report(checks=[_rate_ck(kind=kind)], banner_extra={"wilson_ci": _WILSON_CI})
        with pytest.raises(ValueError, match="unknown measured_kind"):
            require_wilson_ci_for_rates(report)


def test_guard_rejects_unknown_measured_kind_in_warnings():
    report = _report(warnings=[_rate_ck(kind="Rate", check_id="warn.flake_rate")])
    with pytest.raises(ValueError, match="warn.flake_rate"):
        require_wilson_ci_for_rates(report)


def test_guard_and_schema_agree_on_miscased_measured_kind():
    report = _report(checks=[_rate_ck(kind="Rate")], banner_extra={"wilson_ci": _WILSON_CI})
    assert not _root_validator("validation-report").is_valid(report)
    with pytest.raises(ValueError):
        require_wilson_ci_for_rates(report)


def test_guard_accepts_every_declared_measured_kind():
    for kind in typing.get_args(MeasuredKind):
        report = _report(
            checks=[_rate_ck(kind=kind)],
            banner_extra={"wilson_ci": _WILSON_CI},
        )
        assert require_wilson_ci_for_rates(report) is None, kind


def test_guard_degrades_on_non_mapping_report():
    """Like derive_verdict, the guard never raises on a malformed report argument."""
    for report in (None, "nope", 7, [], ["checks"], object()):
        assert require_wilson_ci_for_rates(report) is None


def test_generator_conditional_guard_raises_on_empty_array_fields(monkeypatch):
    """An empty antecedent would emit a meta-schema-invalid `anyOf: []`."""
    monkeypatch.setitem(
        gen_schemas.CONDITIONALS,
        "ValidationReport",
        dict(gen_schemas.CONDITIONALS["ValidationReport"], when_array_fields=[]),
    )
    with pytest.raises(ValueError, match="no array field"):
        gen_schemas.generate()


def test_generator_conditional_guard_raises_on_off_enum_entry_value(monkeypatch):
    """An entry value outside the emitted enum would make the rule never fire."""
    monkeypatch.setitem(
        gen_schemas.CONDITIONALS,
        "ValidationReport",
        dict(gen_schemas.CONDITIONALS["ValidationReport"], entry_value="Rate"),
    )
    with pytest.raises(ValueError, match="not among 'measured_kind' enum members"):
        gen_schemas.generate()


def test_generator_conditional_guard_raises_on_non_array_when_field(monkeypatch):
    """A non-array `when_array_fields` entry names THAT problem, not a missing item."""
    monkeypatch.setitem(
        gen_schemas.CONDITIONALS,
        "ValidationReport",
        dict(gen_schemas.CONDITIONALS["ValidationReport"], when_array_fields=["subject"]),
    )
    with pytest.raises(ValueError, match="not array-typed"):
        gen_schemas.generate()


def test_generator_conditional_guard_raises_on_bogus_field(monkeypatch):
    """The conditional manifest cannot name a field absent from emitted properties."""
    monkeypatch.setitem(
        gen_schemas.CONDITIONALS,
        "ValidationReport",
        dict(
            gen_schemas.CONDITIONALS["ValidationReport"],
            entry_field="does_not_exist",
        ),
    )
    with pytest.raises(ValueError, match="does_not_exist"):
        gen_schemas.generate()


def test_generator_conditional_guard_raises_on_bogus_array_field(monkeypatch):
    monkeypatch.setitem(
        gen_schemas.CONDITIONALS,
        "ValidationReport",
        dict(
            gen_schemas.CONDITIONALS["ValidationReport"],
            when_array_fields=["no_such_array"],
        ),
    )
    with pytest.raises(ValueError, match="no_such_array"):
        gen_schemas.generate()


def test_generator_conditional_guard_raises_on_bogus_required_field(monkeypatch):
    monkeypatch.setitem(
        gen_schemas.CONDITIONALS,
        "ValidationReport",
        dict(
            gen_schemas.CONDITIONALS["ValidationReport"],
            then_required_field="no_such_banner_field",
        ),
    )
    with pytest.raises(ValueError, match="no_such_banner_field"):
        gen_schemas.generate()


def test_generator_conditional_guard_raises_on_missing_spec_key(monkeypatch):
    """A spec key typo must surface as the manifest ValueError, never a KeyError."""
    original = dict(gen_schemas.CONDITIONALS["ValidationReport"])
    for dropped in original:
        monkeypatch.setitem(
            gen_schemas.CONDITIONALS,
            "ValidationReport",
            {k: v for k, v in original.items() if k != dropped},
        )
        with pytest.raises(ValueError, match=f"missing spec key\\(s\\): \\['{dropped}'\\]"):
            gen_schemas.generate()


def test_generator_conditional_guard_raises_on_non_wire_root_key(monkeypatch):
    """An entry keyed on a non-root type would never be emitted; that must not pass."""
    monkeypatch.setitem(
        gen_schemas.CONDITIONALS,
        "Check",
        dict(gen_schemas.CONDITIONALS["ValidationReport"]),
    )
    with pytest.raises(ValueError, match="non-wire-root type\\(s\\) \\['Check'\\]"):
        gen_schemas.generate()


def test_generator_conditional_guard_raises_on_non_ref_object_field(monkeypatch):
    """`subject` is an inline object with no $def, so it cannot be constrained."""
    monkeypatch.setitem(
        gen_schemas.CONDITIONALS,
        "ValidationReport",
        dict(gen_schemas.CONDITIONALS["ValidationReport"], then_object_field="subject"),
    )
    with pytest.raises(ValueError, match="object field 'subject', which is not a \\$ref"):
        gen_schemas.generate()


def test_generator_conditional_guard_raises_on_inline_array_items(monkeypatch):
    """An array of inline items names THAT problem, not an absent entry field."""
    monkeypatch.setitem(
        gen_schemas.CONDITIONALS,
        "GeometryDiff",
        dict(
            gen_schemas.CONDITIONALS["ValidationReport"],
            when_array_fields=["touched"],
            then_object_field="counts",
        ),
    )
    with pytest.raises(ValueError, match="items of 'touched', which is not a \\$ref"):
        gen_schemas.generate()


def test_guard_rejects_unhashable_measured_kind():
    """An unhashable kind must give the documented ValueError, not a TypeError."""
    for kind in ([], {}, {"a"}, [1, 2]):
        report = _report(
            checks=[{"id": "x.rate", "passed": True, "measured_kind": kind}],
            banner_extra={"wilson_ci": _WILSON_CI},
        )
        with pytest.raises(ValueError, match="unknown measured_kind"):
            require_wilson_ci_for_rates(report)


def test_guard_scans_tuple_containers():
    """In-code assembly may hand a tuple; enforcement must not silently drop it."""
    report = _report()
    report["checks"] = (_rate_ck(),)
    with pytest.raises(ValueError, match="gate.pass_rate"):
        require_wilson_ci_for_rates(report)
    report["banner"]["wilson_ci"] = _WILSON_CI
    assert require_wilson_ci_for_rates(report) is None


def test_guard_still_skips_string_containers():
    """A string is a Sequence but never a check list; it must degrade, not iterate."""
    assert require_wilson_ci_for_rates({"checks": "rate"}) is None
    assert require_wilson_ci_for_rates({"warnings": b"rate"}) is None


def test_guard_rejects_mistyped_wilson_ci_values():
    report = _report(
        checks=[_rate_ck()],
        banner_extra={"wilson_ci": {"rate": "x", "low": None, "high": [], "n": "z", "r": {}}},
    )
    assert not _root_validator("validation-report").is_valid(report)
    with pytest.raises(ValueError, match=r"non-numeric key\(s\).*gate.pass_rate"):
        require_wilson_ci_for_rates(report)


def test_guard_rejects_all_null_wilson_ci_values():
    report = _report(
        checks=[_rate_ck()],
        banner_extra={"wilson_ci": dict.fromkeys(_WILSON_CI)},
    )
    assert not _root_validator("validation-report").is_valid(report)
    with pytest.raises(ValueError, match="non-numeric key"):
        require_wilson_ci_for_rates(report)


def test_guard_rejects_bool_wilson_ci_counts():
    report = _report(
        checks=[_rate_ck()],
        banner_extra={"wilson_ci": dict(_WILSON_CI, n=True, r=False)},
    )
    with pytest.raises(ValueError, match=r"non-numeric key\(s\) \['n', 'r'\]"):
        require_wilson_ci_for_rates(report)


def test_guard_accepts_integral_rate_bounds():
    report = _report(
        checks=[_rate_ck()],
        banner_extra={"wilson_ci": {"rate": 1, "low": 0, "high": 1, "n": 30, "r": 30}},
    )
    assert _root_validator("validation-report").is_valid(report)
    assert require_wilson_ci_for_rates(report) is None


def test_guard_accepts_integral_float_counts():
    """Draft 2020-12 ``integer`` admits ``30.0``; both surfaces must agree."""
    report = _report(
        checks=[_rate_ck()],
        banner_extra={"wilson_ci": dict(_WILSON_CI, n=30.0, r=27.0)},
    )
    assert _root_validator("validation-report").is_valid(report)
    assert require_wilson_ci_for_rates(report) is None


def test_guard_rejects_fractional_counts():
    report = _report(
        checks=[_rate_ck()],
        banner_extra={"wilson_ci": dict(_WILSON_CI, n=29.5)},
    )
    assert not _root_validator("validation-report").is_valid(report)
    with pytest.raises(ValueError, match=r"non-numeric key\(s\) \['n'\]"):
        require_wilson_ci_for_rates(report)


def test_guard_scans_non_dict_mapping_entries():
    """A frozen or proxied check entry must not bypass enforcement."""
    report = _report()
    report["checks"] = [MappingProxyType(_rate_ck())]
    with pytest.raises(ValueError, match="gate.pass_rate"):
        require_wilson_ci_for_rates(report)
    report["banner"]["wilson_ci"] = _WILSON_CI
    assert require_wilson_ci_for_rates(report) is None


def test_guard_deduplicates_offending_ids():
    report = _report(checks=[_rate_ck(), _rate_ck()], warnings=[_rate_ck()])
    with pytest.raises(ValueError) as excinfo:
        require_wilson_ci_for_rates(report)
    assert "['gate.pass_rate']" in str(excinfo.value)


def test_conditional_then_rejects_incomplete_wilson_ci_on_its_own():
    """``then`` $refs WilsonCI, so it rejects a partial CI without ReportBanner."""
    v = _conditional_validator("validation-report")
    for bad in ({}, "nope", 7, [], {"rate": 0.9}):
        assert not v.is_valid({"checks": [_rate_ck()], "banner": {"wilson_ci": bad}}), bad
    assert v.is_valid({"checks": [_rate_ck()], "banner": {"wilson_ci": _WILSON_CI}})


def test_measured_kind_and_guard_are_package_exports():
    import freecad_buddy.contracts as contracts_pkg

    assert contracts_pkg.require_wilson_ci_for_rates is require_wilson_ci_for_rates
    assert "MeasuredKind" in contracts_pkg.__all__
    assert "require_wilson_ci_for_rates" in contracts_pkg.__all__


def test_guard_rejects_a_second_rate_check_the_banner_interval_cannot_describe():
    """One banner interval describes one rate. A second would silently inherit the first's.

    The interval is measured over one population, so two checks with different denominators
    cannot both be covered by it.
    """
    report = _report(
        checks=[_rate_ck(check_id="gate.pass_rate"), _rate_ck(check_id="gate.detect_rate")],
        banner_extra={"wilson_ci": _WILSON_CI},
    )

    with pytest.raises(ValueError, match="one rate"):
        require_wilson_ci_for_rates(report)


def test_guard_counts_rate_checks_across_checks_and_warnings():
    """A rate in warnings is as uncovered as one in checks."""
    report = _report(
        checks=[_rate_ck(check_id="gate.pass_rate")],
        warnings=[_rate_ck(check_id="gate.warn_rate")],
        banner_extra={"wilson_ci": _WILSON_CI},
    )

    with pytest.raises(ValueError, match="one rate"):
        require_wilson_ci_for_rates(report)


def test_guard_rejects_two_rate_checks_that_share_an_id():
    """Counted by occurrence, not by distinct id — two checks sharing an id are still two."""
    report = _report(
        checks=[_rate_ck(check_id="same"), _rate_ck(check_id="same")],
        banner_extra={"wilson_ci": _WILSON_CI},
    )

    with pytest.raises(ValueError, match="one rate"):
        require_wilson_ci_for_rates(report)


def test_guard_accepts_a_single_rate_check_alongside_non_rate_checks():
    """The rule bounds rate checks only; other checks are unaffected."""
    report = _report(
        checks=[
            _rate_ck(check_id="gate.pass_rate"),
            {"id": "gate.other", "passed": True, "measured": 7},
            _rate_ck(kind=None, check_id="gate.unmarked"),
        ],
        banner_extra={"wilson_ci": _WILSON_CI},
    )

    assert require_wilson_ci_for_rates(report) is None


@pytest.mark.parametrize(
    ("wilson_ci", "reason"),
    [
        ({**_WILSON_CI, "rate": float("nan")}, "not finite"),
        ({**_WILSON_CI, "low": float("-inf")}, "not finite"),
        ({**_WILSON_CI, "rate": 5.0, "high": 5.0}, r"outside \[0, 1\]"),
        ({**_WILSON_CI, "low": -0.5}, r"outside \[0, 1\]"),
        ({**_WILSON_CI, "low": 0.95, "high": 0.8}, "not ordered"),
        ({**_WILSON_CI, "rate": 0.99}, "not ordered"),
        ({**_WILSON_CI, "n": 0, "r": 0}, "positive trial count"),
        ({**_WILSON_CI, "n": -3}, "positive trial count"),
        ({**_WILSON_CI, "r": 99}, r"outside \[0, n\]"),
        ({**_WILSON_CI, "r": -1}, r"outside \[0, n\]"),
    ],
)
def test_guard_rejects_an_impossible_interval(wilson_ci, reason):
    """A present, correctly-typed CI that cannot describe a real interval still fails."""
    report = _report(checks=[_rate_ck()], banner_extra={"wilson_ci": wilson_ci})
    with pytest.raises(ValueError, match=reason):
        require_wilson_ci_for_rates(report)


def test_guard_accepts_the_degenerate_but_possible_interval():
    """rate=low=high=1.0 with r == n is unusual but real, and must not be rejected."""
    report = _report(
        checks=[_rate_ck()],
        banner_extra={"wilson_ci": {"rate": 1.0, "low": 1.0, "high": 1.0, "n": 10, "r": 10}},
    )
    assert require_wilson_ci_for_rates(report) is None


def test_guard_coherence_only_applies_when_a_rate_is_declared():
    """An impossible CI on a report with no rate check is out of this guard's scope."""
    report = _report(
        checks=[{"id": "shape.volume", "passed": True, "measured": 12.0}],
        banner_extra={"wilson_ci": {**_WILSON_CI, "r": 99}},
    )
    assert require_wilson_ci_for_rates(report) is None


# --------------------------------------------------------------------------- #
# mutation blocks: required keys and closed schemas
# --------------------------------------------------------------------------- #

MUTATION_BLOCKS = ("MutationBlock", "PostVerifyBlock", "TnpAuditBlock", "RefFinding")


@pytest.mark.parametrize("name", MUTATION_BLOCKS)
def test_mutation_block_required_keys_match_the_manifest(name):
    """The TypedDict states what is required; the manifest must agree, or they drift.

    A `# required` comment is prose the type checker cannot read, which is how a producer could
    omit a mandatory field, type-check clean, and fail only at wire validation.
    """
    from freecad_buddy.contracts import mutation

    block = getattr(mutation, name)

    assert set(block.__required_keys__) == set(gen_schemas.REQUIRED_FIELDS[name])


@pytest.mark.parametrize("name", MUTATION_BLOCKS)
def test_mutation_block_schemas_are_closed(name):
    """A misspelled field must be rejected, not silently defaulted."""
    schema = _load("mutation")
    body = schema if name == "MutationBlock" else schema["$defs"][name]

    assert body["additionalProperties"] is False


def _valid_mutation_block() -> dict:
    """A block that satisfies every required key, so a test can introduce exactly one defect."""
    return {
        "fingerprint_before": {"digest": "d", "serializer": "exportBinary"},
        "fingerprint_after": None,
        "changed": [],
        "post_verify": {
            "recompute_clean": True,
            "is_valid": True,
            "fully_constrained": None,
            "tnp_audit": {
                "status": "CLEAN",
                "element_map_version": None,
                "counts": {},
                "findings": [],
            },
            "passed": True,
        },
        "rolled_back": False,
        "rollback_proven": None,
    }


def test_a_valid_mutation_block_is_accepted():
    """Guards the fixture itself: if this fails, the misspelling test proves nothing."""
    jsonschema.Draft202012Validator(_load("mutation")).validate(_valid_mutation_block())


def test_a_misspelled_mutation_field_is_rejected():
    block = _valid_mutation_block()
    block["roled_back"] = True

    with pytest.raises(jsonschema.ValidationError):
        jsonschema.Draft202012Validator(_load("mutation")).validate(block)
