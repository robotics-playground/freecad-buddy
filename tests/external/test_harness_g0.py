"""G0 harness tests (external / pytest). NON-tautological: validate real ValidationReport
objects against the committed schema + real exit codes; assert the ACTUAL reachable verdict
class; prove every honest-fail guard and every check_provenance failure path."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
import yaml
from jsonschema import Draft202012Validator

REPO_ROOT = Path(__file__).resolve().parents[2]
BENCHMARKS = REPO_ROOT / "benchmarks"
FAULT_DIR = BENCHMARKS / "g0" / "fault-injection"
SCHEMA = (
    REPO_ROOT
    / "src"
    / "freecad_buddy"
    / "contracts"
    / "jsonschema"
    / "validation-report.schema.json"
)

sys.path.insert(0, str(REPO_ROOT / "scripts"))
sys.path.insert(0, str(REPO_ROOT))

import check_provenance  # noqa: E402

from benchmarks import runner  # noqa: E402

CLOSED_FAULT_KINDS = {"planted_defect", "clean_control"}
RESERVED_ASSERTION_FNS = {
    "expect_volume",
    "expect_bbox",
    "expect_solid_count",
    "expect_valid",
    "expect_watertight",
}


def _report_validator() -> Draft202012Validator:
    return Draft202012Validator(json.loads(SCHEMA.read_text(encoding="utf-8")))


def _load_cases() -> list[dict]:
    cases = []
    for case_yaml in sorted(FAULT_DIR.rglob("case.yaml")):
        data = yaml.safe_load(case_yaml.read_text(encoding="utf-8"))
        data["_dir"] = case_yaml.parent
        cases.append(data)
    return cases


# --------------------------------------------------------------------------- #
# (a) stub run: report per criterion, schema-valid, INVALID_INPUT, exit 1
# --------------------------------------------------------------------------- #


def test_stub_run_report_per_criterion_schema_valid_invalid_input():
    reports, exit_code = runner.run_gate("G0")
    gate = yaml.safe_load((BENCHMARKS / "g0" / "gate.yaml").read_text(encoding="utf-8"))
    assert len(reports) == len(gate["criteria"])
    assert exit_code == 1  # honest FAIL

    validator = _report_validator()
    for report in reports:
        validator.validate(report)  # raises on schema violation
        assert report["verdict"] != "OK"
        # The ACTUAL single reachable class — not a permissive 3-value set.
        assert report["verdict"] == "INVALID_INPUT", report["subject"]


def test_stub_report_banner_element_map_version_is_none():
    reports, _ = runner.run_gate("G0")
    for report in reports:
        assert report["banner"]["element_map_version"] is None
        assert report["banner"]["freecad_version"] == "stub"


def test_runner_file_path_invocation_exits_1():
    result = subprocess.run(
        [sys.executable, str(BENCHMARKS / "runner.py"), "--gate", "G0", "--stub"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 1, result.stderr
    assert "FAILED" in result.stdout


# --------------------------------------------------------------------------- #
# (b) fault inventory: >=10 defects + >=1 control, closed kinds, bound, fixtures exist
# --------------------------------------------------------------------------- #


def test_fault_inventory_counts_and_binding():
    cases = _load_cases()
    validators = yaml.safe_load(
        (BENCHMARKS / "_registry" / "validators.yaml").read_text(encoding="utf-8")
    )
    assert "verify_shape" in validators
    last_run = validators["verify_shape"]["last_run"]
    assert last_run is not None  # scored by score_verify_shape.py (Story 1.6)
    assert last_run["sensitivity"] >= 0.95
    assert last_run["false_alarm"] <= 0.05
    assert validators["verify_shape"]["validator_sha"] is not None

    defects = [c for c in cases if c["fault"]["kind"] == "planted_defect"]
    controls = [c for c in cases if c["fault"]["kind"] == "clean_control"]
    assert len(defects) >= 10, f"need >=10 planted defects, got {len(defects)}"
    assert len(controls) >= 1

    for case in cases:
        kind = case["fault"]["kind"]
        assert kind in CLOSED_FAULT_KINDS, f"{case['id']}: bad fault.kind {kind!r}"
        assert case["targets_validator"] == "verify_shape", case["id"]
        assert case["fault"]["expectation"] in {"DETECT", "PASS_CLEAN"}
        # declared fixture exists
        fixture = case["_dir"] / case["fixture"]
        assert fixture.is_file(), f"{case['id']}: missing fixture {fixture}"


def test_fault_assertions_use_reserved_vocabulary_only():
    for case in _load_cases():
        for check in case["assertions"]["checks"]:
            assert check["fn"] in RESERVED_ASSERTION_FNS, f"{case['id']}: {check['fn']}"


# --------------------------------------------------------------------------- #
# (c) check_provenance: exits 0 on real tree; fails on deleted/duplicate/missing-fixture
# --------------------------------------------------------------------------- #


def test_check_provenance_clean_on_real_tree():
    assert check_provenance.check_tree(BENCHMARKS) == []


def test_check_provenance_flags_deleted_manifest(tmp_path):
    copy = tmp_path / "benchmarks"
    shutil.copytree(BENCHMARKS, copy)
    manifest = copy / "_registry" / "provenance" / "g0-golden-box-10-20-30.yaml"
    manifest.unlink()
    problems = check_provenance.check_tree(copy)
    assert any("box-10-20-30" in p and "no provenance manifest" in p for p in problems), problems


def test_check_provenance_flags_duplicate_artifact_id(tmp_path):
    copy = tmp_path / "benchmarks"
    shutil.copytree(BENCHMARKS, copy)
    prov = copy / "_registry" / "provenance"
    original = (prov / "g0-golden-box-10-20-30.yaml").read_text(encoding="utf-8")
    (prov / "g0-golden-box-10-20-30-dup.yaml").write_text(original, encoding="utf-8")
    problems = check_provenance.check_tree(copy)
    assert any("duplicate artifact id" in p for p in problems), problems


def test_check_provenance_flags_case_missing_fixture(tmp_path):
    copy = tmp_path / "benchmarks"
    shutil.copytree(BENCHMARKS, copy)
    fixture = copy / "g0" / "fault-injection" / "wrong-volume" / "fixture.FCStd"
    fixture.unlink()
    problems = check_provenance.check_tree(copy)
    assert any("fixture.FCStd missing" in p for p in problems), problems


def test_check_provenance_runnable_exit_0():
    result = subprocess.run(
        [sys.executable, str(REPO_ROOT / "scripts" / "check_provenance.py")],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr


# --------------------------------------------------------------------------- #
# (d) runner honest-fail guards -> exit 2, never 0, never a traceback
# --------------------------------------------------------------------------- #


def _run_runner(args: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(BENCHMARKS / "runner.py"), *args],
        capture_output=True,
        text=True,
    )


def test_unknown_gate_exits_2_no_traceback():
    result = _run_runner(["--gate", "G9", "--stub"])
    assert result.returncode == 2
    assert "Traceback" not in result.stderr


def test_lowercase_gate_exits_2():
    result = _run_runner(["--gate", "g0", "--stub"])
    assert result.returncode == 2
    assert "Traceback" not in result.stderr


def test_criterion_matching_nothing_exits_2():
    result = _run_runner(["--gate", "G0", "--stub", "--criterion", "G0.99"])
    assert result.returncode == 2
    assert "Traceback" not in result.stderr


def test_case_flag_rejected_exits_2():
    result = _run_runner(["--gate", "G0", "--stub", "--case", "anything"])
    assert result.returncode == 2
    assert "Traceback" not in result.stderr


def test_missing_stub_flag_exits_2():
    """--stub is the only shipped mode; a bare invocation is a clean usage error, not a no-op."""
    result = _run_runner(["--gate", "G0"])
    assert result.returncode == 2
    assert "Traceback" not in result.stderr


def _patched_gate(tmp_path: Path, contents: str) -> Path:
    """Copy benchmarks into tmp, overwrite g0/gate.yaml, return the runner-importable root."""
    copy = tmp_path / "benchmarks"
    shutil.copytree(BENCHMARKS, copy)
    (copy / "g0" / "gate.yaml").write_text(contents, encoding="utf-8")
    return copy


def test_empty_criteria_exits_2_not_0(tmp_path, monkeypatch):
    copy = _patched_gate(tmp_path, "gate: G0\ncriteria: []\n")
    monkeypatch.setattr(runner, "BENCHMARKS_ROOT", copy)
    with pytest.raises(runner.UsageError):
        runner.run_gate("G0")


def test_missing_criteria_exits_2(tmp_path, monkeypatch):
    copy = _patched_gate(tmp_path, "gate: G0\n")
    monkeypatch.setattr(runner, "BENCHMARKS_ROOT", copy)
    with pytest.raises(runner.UsageError):
        runner.run_gate("G0")


def test_non_mapping_gate_exits_2(tmp_path, monkeypatch):
    copy = _patched_gate(tmp_path, "- just\n- a\n- list\n")
    monkeypatch.setattr(runner, "BENCHMARKS_ROOT", copy)
    with pytest.raises(runner.UsageError):
        runner.run_gate("G0")


def test_malformed_gate_yaml_exits_2(tmp_path, monkeypatch):
    copy = _patched_gate(tmp_path, "criteria: [unbalanced\n")
    monkeypatch.setattr(runner, "BENCHMARKS_ROOT", copy)
    with pytest.raises(runner.UsageError):
        runner.run_gate("G0")


def test_criterion_missing_id_exits_2(tmp_path, monkeypatch):
    copy = _patched_gate(tmp_path, "gate: G0\ncriteria:\n  - {text: no id here}\n")
    monkeypatch.setattr(runner, "BENCHMARKS_ROOT", copy)
    with pytest.raises(runner.UsageError):
        runner.run_gate("G0")


def test_main_returns_2_on_empty_criteria(tmp_path, monkeypatch):
    """main() converts UsageError to exit 2 (never 0) with no traceback."""
    copy = _patched_gate(tmp_path, "gate: G0\ncriteria: []\n")
    monkeypatch.setattr(runner, "BENCHMARKS_ROOT", copy)
    assert runner.main(["--gate", "G0", "--stub"]) == 2
