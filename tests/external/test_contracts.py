"""Contract invariant tests. Non-tautological: schemas are validated
with the ``jsonschema`` dev dep, not just inspected for key presence."""

import json
import sys
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

REPO_ROOT = Path(__file__).resolve().parents[2]
PKG = REPO_ROOT / "src" / "freecad_buddy"
SCHEMA_DIR = PKG / "contracts" / "jsonschema"

sys.path.insert(0, str(REPO_ROOT / "scripts"))
import check_status_vocab  # noqa: E402
import gen_schemas  # noqa: E402

from freecad_buddy.contracts.envelope import mirror_text  # noqa: E402
from freecad_buddy.contracts.fingerprint import fingerprints_equal  # noqa: E402
from freecad_buddy.contracts.report import derive_verdict  # noqa: E402


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
    "ErrorDetail": {"message"},
    "ReportBanner": {"freecad_version", "element_map_version"},
    "Check": {"passed"},
    "DocHandle": {"handle"},
    "ObjectFingerprint": {"name", "brep_sha256", "massprops"},
    "MassProps": {"volume", "area", "bbox", "com", "principal_moments", "quantum"},
    # WilsonCI/ImageRef/ResultEnvelope-nested carry their own (or empty) required sets,
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
