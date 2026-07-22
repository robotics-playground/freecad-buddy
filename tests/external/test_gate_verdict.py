"""Gate-verdict matrix (external / pytest, no FreeCAD).

Covers the full I/O matrix over a fabricated ``gate-artifacts/g0/<run-id>/`` tmp dir — full
PASS, every single-leg FAIL, exit-2 loader errors, the purity assertion, the ``collect_g0_2``
introspection over the real ``tool_specs()``, and the loop-1 (a)-(f) + loop-2 (g)-(l)
regressions that pin every no-self-grade / no-false-PASS fix.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
BENCHMARKS = REPO_ROOT / "benchmarks"
sys.path.insert(0, str(REPO_ROOT))

from benchmarks import runner  # noqa: E402
from benchmarks.harness.evidence import collect_g0_2, ingest_report  # noqa: E402
from benchmarks.harness.report_build import evidence_report  # noqa: E402
from benchmarks.harness.verdict import (  # noqa: E402
    ArtifactError,
    bind_hash,
    check_token,
    check_validator_currency,
    compute_verdict,
    load_reports,
)

EXPECTED_IDS = ["G0.1", "G0.2", "G0.3", "G0.4", "G0.5"]
CITED = "verify_shape"


# --------------------------------------------------------------------------- #
# fixtures / builders
# --------------------------------------------------------------------------- #


def _ok_report(criterion: str) -> dict:
    return evidence_report(
        criterion,
        [
            {
                "id": criterion,
                "measured": 1,
                "expected": 1,
                "passed": True,
                "detail": {"code": "ok", "message": "ok"},
            }
        ],
    )


def _fail_report(criterion: str) -> dict:
    return evidence_report(
        criterion,
        [
            {
                "id": criterion,
                "measured": 0,
                "expected": 1,
                "passed": False,
                "detail": {"code": "spec_failed.mismatch", "message": "bad"},
            }
        ],
    )


def _write_reports(run_dir: Path, reports: dict[str, dict]) -> None:
    reports_dir = run_dir / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    for criterion, report in reports.items():
        (reports_dir / f"{criterion}.json").write_text(json.dumps(report), encoding="utf-8")


def _all_ok_run(run_dir: Path) -> dict[str, dict]:
    reports = {cid: _ok_report(cid) for cid in EXPECTED_IDS}
    _write_reports(run_dir, reports)
    return reports


def _gate_def() -> dict:
    return {
        "gate": "G0",
        "required_tokens": ["gui_smoke"],
        "criteria": [
            {"id": "G0.1", "cited_validators": []},
            {"id": "G0.2", "cited_validators": []},
            {"id": "G0.3", "cited_validators": [CITED]},
            {"id": "G0.4", "cited_validators": []},
            {"id": "G0.5", "cited_validators": [CITED]},
        ],
    }


def _current_validators() -> dict:
    return {
        CITED: {
            "validator_sha": "SHA_OK",
            "last_run": {"sensitivity": 1.0, "false_alarm": 0.0},
        }
    }


def _hasher(_name: str) -> str:
    return "SHA_OK"


def _bound_token(run_dir: Path, reports: dict[str, dict], **overrides) -> None:
    human = run_dir / "human"
    human.mkdir(parents=True, exist_ok=True)
    token = {
        "token_type": "gui_smoke",
        "binds_reports_sha256": bind_hash(list(reports.values())),
        "outcome": "PASS",
    }
    token.update(overrides)
    name = overrides.pop("_filename", "gui_smoke_2026-07-22.json")
    (human / name).write_text(json.dumps(token), encoding="utf-8")


# --------------------------------------------------------------------------- #
# full PASS + purity
# --------------------------------------------------------------------------- #


def test_full_pass(tmp_path):
    reports = _all_ok_run(tmp_path)
    _bound_token(tmp_path, reports)
    result = compute_verdict(tmp_path, _gate_def(), _current_validators(), _hasher)
    assert result.passed, result.failures
    assert all(v == "PASS" for v in result.per_criterion.values())


def test_purity_identical_result_on_rerun(tmp_path):
    reports = _all_ok_run(tmp_path)
    _bound_token(tmp_path, reports)
    a = compute_verdict(tmp_path, _gate_def(), _current_validators(), _hasher)
    b = compute_verdict(tmp_path, _gate_def(), _current_validators(), _hasher)
    assert (a.passed, a.per_criterion, a.failures) == (b.passed, b.per_criterion, b.failures)


def test_verdict_module_importable_without_freecad():
    """harness.verdict must import with FreeCAD absent (pure auditor)."""
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "import sys; sys.modules['FreeCAD']=None; "
            "sys.path.insert(0, r'%s'); "
            "import benchmarks.harness.verdict as v; print(v.bind_hash([]))" % REPO_ROOT,
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr


# --------------------------------------------------------------------------- #
# single-leg FAIL paths
# --------------------------------------------------------------------------- #


def test_leg_a_report_fail(tmp_path):
    reports = _all_ok_run(tmp_path)
    reports["G0.3"] = _fail_report("G0.3")
    _write_reports(tmp_path, reports)
    _bound_token(tmp_path, reports)
    result = compute_verdict(tmp_path, _gate_def(), _current_validators(), _hasher)
    assert not result.passed
    assert result.per_criterion["G0.3"] == "FAIL"
    assert any("G0.3" in f for f in result.failures)


def test_leg_b_stale_validator(tmp_path):
    reports = _all_ok_run(tmp_path)
    _bound_token(tmp_path, reports)
    validators = {
        CITED: {"validator_sha": "STALE", "last_run": {"sensitivity": 1.0, "false_alarm": 0.0}}
    }
    result = compute_verdict(tmp_path, _gate_def(), validators, _hasher)
    assert not result.passed
    assert any("leg-b" in f and CITED in f for f in result.failures)


def test_leg_b_failing_validator(tmp_path):
    reports = _all_ok_run(tmp_path)
    _bound_token(tmp_path, reports)
    validators = {
        CITED: {"validator_sha": "SHA_OK", "last_run": {"sensitivity": 0.90, "false_alarm": 0.0}}
    }
    result = compute_verdict(tmp_path, _gate_def(), validators, _hasher)
    assert not result.passed
    assert any("leg-b" in f and CITED in f for f in result.failures)


def test_leg_d_missing_token(tmp_path):
    _all_ok_run(tmp_path)
    result = compute_verdict(tmp_path, _gate_def(), _current_validators(), _hasher)
    assert not result.passed
    assert any("absent" in f for f in result.failures)


def test_leg_d_recycled_token(tmp_path):
    reports = _all_ok_run(tmp_path)
    _bound_token(tmp_path, reports, binds_reports_sha256="deadbeef")
    result = compute_verdict(tmp_path, _gate_def(), _current_validators(), _hasher)
    assert not result.passed
    assert any("not bound" in f for f in result.failures)


def test_leg_d_fail_outcome_token(tmp_path):
    reports = _all_ok_run(tmp_path)
    _bound_token(tmp_path, reports, outcome="FAIL")
    result = compute_verdict(tmp_path, _gate_def(), _current_validators(), _hasher)
    assert not result.passed
    assert any("FAIL" in f for f in result.failures)


# --------------------------------------------------------------------------- #
# exit-2 loader errors
# --------------------------------------------------------------------------- #


def test_missing_report_raises_artifact_error(tmp_path):
    (tmp_path / "reports").mkdir()
    with pytest.raises(ArtifactError):
        load_reports(tmp_path, EXPECTED_IDS)


def test_malformed_report_raises_artifact_error(tmp_path):
    reports_dir = tmp_path / "reports"
    reports_dir.mkdir()
    for cid in EXPECTED_IDS:
        (reports_dir / f"{cid}.json").write_text("not json{", encoding="utf-8")
    with pytest.raises(ArtifactError):
        load_reports(tmp_path, EXPECTED_IDS)


# --------------------------------------------------------------------------- #
# G0.2 introspection over the real catalog
# --------------------------------------------------------------------------- #


def test_collect_g0_2_real_catalog():
    from freecad_buddy.hosts.tool_catalog import tool_specs

    report = collect_g0_2(list(tool_specs()))
    assert report["verdict"] == "OK", report["checks"]
    count_check = report["checks"][0]
    assert count_check["measured"] >= 15
    assert count_check["passed"]


# --------------------------------------------------------------------------- #
# loop-1 regressions (a)-(f)
# --------------------------------------------------------------------------- #


def test_regression_a_self_grade_ingest_derives_fail(tmp_path):
    """A stamped verdict:OK over a failing check re-derives to non-OK at ingest."""
    path = tmp_path / "G0.3.json"
    path.write_text(
        json.dumps(
            {
                "verdict": "OK",
                "checks": [
                    {
                        "id": "x",
                        "passed": False,
                        "detail": {"code": "spec_failed.x", "message": "no"},
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    report = ingest_report("G0.3", path)
    assert report["verdict"] != "OK"


def test_regression_b_empty_checks_ingest_invalid_input(tmp_path):
    path = tmp_path / "G0.3.json"
    path.write_text(json.dumps({"verdict": "OK", "checks": []}), encoding="utf-8")
    report = ingest_report("G0.3", path)
    assert report["verdict"] == "INVALID_INPUT"


def test_regression_c_boolean_bar_rejected():
    validators = {
        CITED: {"validator_sha": "SHA_OK", "last_run": {"sensitivity": True, "false_alarm": 0.0}}
    }
    failures = check_validator_currency(_gate_def(), validators, _hasher)
    assert any(CITED in f for f in failures)


def test_regression_d_orphan_file_ignored(tmp_path):
    reports = _all_ok_run(tmp_path)
    (tmp_path / "reports" / "orphan.json").write_text(json.dumps({"junk": 1}), encoding="utf-8")
    _bound_token(tmp_path, reports)
    result = compute_verdict(tmp_path, _gate_def(), _current_validators(), _hasher)
    assert result.passed, result.failures


def test_regression_e_non_string_name_malformed():
    class Spec:
        name = None
        input_schema = {"type": "object"}
        description = "d"

    report = collect_g0_2([Spec()])
    assert report["verdict"] != "OK"


def test_regression_f_one_red_g0_4_leg_fails(tmp_path):
    """_ingest_g0_4 with one red leg -> combined G0.4 non-OK."""
    evidence = tmp_path / "evidence"
    evidence.mkdir()
    (evidence / "G0.4.1.0.x.json").write_text(json.dumps({"green": True, "test_count": 42}))
    (evidence / "G0.4.1.1.x.json").write_text(json.dumps({"green": False, "test_count": 42}))
    report = runner._ingest_g0_4(tmp_path)
    assert report["verdict"] != "OK"


# --------------------------------------------------------------------------- #
# loop-2 regressions (g)-(l)
# --------------------------------------------------------------------------- #


def test_regression_g_subject_mismatch_fails(tmp_path):
    """A reports/G0.3.json whose subject.criterion is wrong -> leg-a FAIL, never {}->OK."""
    reports = _all_ok_run(tmp_path)
    bad = _ok_report("G0.3")
    bad["subject"]["criterion"] = "WRONG"
    (tmp_path / "reports" / "G0.3.json").write_text(json.dumps(bad), encoding="utf-8")
    _bound_token(tmp_path, reports)
    result = compute_verdict(tmp_path, _gate_def(), _current_validators(), _hasher)
    assert not result.passed
    assert result.per_criterion["G0.3"] == "FAIL"
    assert any("subject mismatch" in f for f in result.failures)


def test_regression_h_empty_checks_at_verdict_time(tmp_path):
    """A hand-placed reports/G0.3.json with checks:[] -> leg-a FAIL (never vacuous-OK)."""
    _all_ok_run(tmp_path)
    (tmp_path / "reports" / "G0.3.json").write_text(
        json.dumps({"subject": {"criterion": "G0.3"}, "checks": []}), encoding="utf-8"
    )
    with pytest.raises(ArtifactError):
        compute_verdict(tmp_path, _gate_def(), _current_validators(), _hasher)


def test_regression_i_one_roster_leg_present_fails(tmp_path):
    """Only ONE roster leg present (green) -> combined G0.4 non-OK (missing blocking leg)."""
    evidence = tmp_path / "evidence"
    evidence.mkdir()
    (evidence / "G0.4.1.0.x.json").write_text(json.dumps({"green": True, "test_count": 42}))
    report = runner._ingest_g0_4(tmp_path)
    assert report["verdict"] != "OK"


def test_regression_j_no_stale_token_shadow(tmp_path):
    """Two same-type tokens: earlier stale/FAIL + later bound-PASS -> leg-d PASSES."""
    reports = _all_ok_run(tmp_path)
    human = tmp_path / "human"
    human.mkdir()
    (human / "gui_smoke_2026-07-01.json").write_text(
        json.dumps(
            {
                "token_type": "gui_smoke",
                "binds_reports_sha256": "stale",
                "outcome": "FAIL",
            }
        ),
        encoding="utf-8",
    )
    (human / "gui_smoke_2026-07-22.json").write_text(
        json.dumps(
            {
                "token_type": "gui_smoke",
                "binds_reports_sha256": bind_hash(list(reports.values())),
                "outcome": "PASS",
            }
        ),
        encoding="utf-8",
    )
    failures = check_token(tmp_path, list(reports.values()), ["gui_smoke"])
    assert failures == []


def test_regression_k_out_of_namespace_not_counted():
    """3 namespaces hold <15 but total >=15 -> G0.2 count check FAILS."""

    class Spec:
        def __init__(self, name):
            self.name = name
            self.input_schema = {"type": "object"}
            self.description = "d"

    specs = [Spec(f"query_{i}") for i in range(5)] + [Spec(f"verify_{i}") for i in range(20)]
    report = collect_g0_2(specs)
    count_check = report["checks"][0]
    assert not count_check["passed"]
    assert count_check["measured"] == 5


def test_regression_l_scalar_required_tokens_exit_2(tmp_path, monkeypatch):
    """gate.yaml required_tokens as a scalar string -> UsageError exit-2."""
    import shutil

    copy = tmp_path / "benchmarks"
    shutil.copytree(BENCHMARKS, copy)
    gate_file = copy / "g0" / "gate.yaml"
    gate_file.write_text(
        gate_file.read_text(encoding="utf-8").replace(
            "required_tokens: [gui_smoke]", "required_tokens: gui_smoke"
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(runner, "BENCHMARKS_ROOT", copy)
    # a run dir must exist so we reach the required_tokens validation, not the missing-dir path.
    (copy / "gate-artifacts" / "g0" / "t" / "reports").mkdir(parents=True)
    assert runner.main(["verdict", "G0", "--run", "t"]) == 2


def test_validator_src_hasher_missing_source_is_stale_not_traceback(tmp_path):
    """A cited validator whose source file is unreadable returns "" (leg-b stale), never raises."""
    missing = tmp_path / "gone.py"
    original = runner._VALIDATOR_SOURCES.get("verify_shape")
    runner._VALIDATOR_SOURCES["verify_shape"] = (missing,)
    try:
        assert runner._validator_src_hasher("verify_shape") == ""
    finally:
        if original is not None:
            runner._VALIDATOR_SOURCES["verify_shape"] = original
