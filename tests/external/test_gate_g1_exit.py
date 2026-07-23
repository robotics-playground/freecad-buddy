"""Gate G1 exit machinery (external / pytest, no FreeCAD).

Covers the seal ceremony and leg-c verdict I/O matrix:
  - seal <-> unseal round-trip over a tmp heldout: SHA verified, SEAL.json shape, unseal event
    appended, temp extraction owned + deleted by the caller;
  - a tampered archive -> SealError; a burned set -> SealError;
  - `run G1 --exit` without the key -> exit-2 (clean, no traceback), heldout untouched;
  - a dev run (`--stub`) never touches heldout;
  - leg-c PASS (R>=10 banners + gap <=15pp) and each FAIL variant (r<10, missing dev_rate.json,
    gap >15pp);
  - leg-c inert for a `verdict.heldout: inert` gate;
  - the `--exit` ceremony seals -> unseals -> verdicts -> deletes the temp extraction.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
BENCHMARKS = REPO_ROOT / "benchmarks"
sys.path.insert(0, str(REPO_ROOT))

from benchmarks import runner  # noqa: E402
from benchmarks.harness import seal  # noqa: E402
from benchmarks.harness.report_build import evidence_report  # noqa: E402
from benchmarks.harness.verdict import check_exit_run  # noqa: E402

KEY = "test-key-abc"


# --------------------------------------------------------------------------- #
# seal.py: round-trip, sha-verify, event append, burn
# --------------------------------------------------------------------------- #


def _stage_case(heldout: Path, case_id: str) -> None:
    case_dir = heldout / case_id
    case_dir.mkdir(parents=True)
    (case_dir / "case.yaml").write_text(f"id: {case_id}\n", encoding="utf-8")


def test_seal_placeholder_empty_is_case_count_zero(tmp_path):
    heldout = tmp_path / "heldout"
    manifest = seal.seal_heldout(heldout, sealed_by="op", sealed_at="2026-01-01", key=KEY)
    assert manifest["case_count"] == 0
    assert manifest["gate"] == "G1"
    assert set(manifest) == {
        "gate",
        "sealed_at",
        "sealed_by",
        "case_count",
        "archive_sha256",
        "case_id_list_sha256",
        "unseal_events",
    }
    assert manifest["unseal_events"] == []
    assert (heldout / seal.ARCHIVE_NAME).is_file()
    assert (heldout / seal.MANIFEST_NAME).is_file()


def test_seal_stdlib_only_archive_is_not_plaintext(tmp_path):
    heldout = tmp_path / "heldout"
    _stage_case(heldout, "g1-heldout-01")
    seal.seal_heldout(heldout, sealed_by="op", sealed_at="t", key=KEY)
    encrypted = (heldout / seal.ARCHIVE_NAME).read_bytes()
    assert b"g1-heldout-01" not in encrypted


def test_seal_unseal_round_trip_recovers_cases(tmp_path):
    heldout = tmp_path / "heldout"
    _stage_case(heldout, "g1-heldout-01")
    seal.seal_heldout(heldout, sealed_by="op", sealed_at="t", key=KEY)
    extract = seal.unseal_heldout(heldout, key=KEY, run_id="r1", timestamp="ts", git_sha="deadbeef")
    try:
        recovered = extract / "g1-heldout-01" / "case.yaml"
        assert recovered.is_file()
        assert "g1-heldout-01" in recovered.read_text(encoding="utf-8")
    finally:
        shutil.rmtree(extract)


def test_unseal_appends_event_to_manifest(tmp_path):
    heldout = tmp_path / "heldout"
    seal.seal_heldout(heldout, sealed_by="op", sealed_at="t", key=KEY)
    extract = seal.unseal_heldout(heldout, key=KEY, run_id="r1", timestamp="ts", git_sha="sha1")
    shutil.rmtree(extract)
    manifest = seal.read_manifest(heldout)
    assert manifest["unseal_events"] == [{"run_id": "r1", "timestamp": "ts", "git_sha": "sha1"}]


def test_unseal_sha_mismatch_raises_seal_error(tmp_path):
    heldout = tmp_path / "heldout"
    seal.seal_heldout(heldout, sealed_by="op", sealed_at="t", key=KEY)
    (heldout / seal.ARCHIVE_NAME).write_bytes(b"tampered")
    with pytest.raises(seal.SealError, match="mismatch"):
        seal.unseal_heldout(heldout, key=KEY, run_id="r1", timestamp="ts", git_sha="sha")


def test_unseal_absent_seal_raises(tmp_path):
    heldout = tmp_path / "heldout"
    heldout.mkdir()
    with pytest.raises(seal.SealError, match="no seal"):
        seal.unseal_heldout(heldout, key=KEY, run_id="r1", timestamp="ts", git_sha="sha")


def test_burn_then_unseal_refuses(tmp_path):
    heldout = tmp_path / "heldout"
    seal.seal_heldout(heldout, sealed_by="op", sealed_at="t", key=KEY)
    seal.burn_seal(heldout, run_id="r1", reason="verdict FAIL")
    manifest = seal.read_manifest(heldout)
    assert manifest["burned"] == {"run_id": "r1", "reason": "verdict FAIL"}
    with pytest.raises(seal.SealError, match="burned"):
        seal.unseal_heldout(heldout, key=KEY, run_id="r2", timestamp="ts", git_sha="sha")


def test_read_manifest_none_when_absent(tmp_path):
    assert seal.read_manifest(tmp_path) is None


# --------------------------------------------------------------------------- #
# leg-c: check_exit_run over stored reports
# --------------------------------------------------------------------------- #


def _exit_report(case_id: str, passed: bool, r: int | None) -> dict:
    report = evidence_report(
        case_id,
        [
            {
                "id": case_id,
                "measured": passed,
                "expected": True,
                "passed": passed,
                "detail": {"code": "ok" if passed else "spec_failed.x", "message": "m"},
            }
        ],
    )
    report["subject"]["criterion"] = case_id
    if r is not None:
        report["banner"]["wilson_ci"] = {"rate": 1.0, "low": 0.9, "high": 1.0, "n": 30, "r": r}
    return report


def _sealed_gate_def() -> dict:
    return {"gate": "G1", "verdict": {"heldout": "sealed"}, "criteria": []}


def _write_exit_run(run_dir: Path, reports: list[dict], dev_rate: float | None) -> None:
    reports_dir = run_dir / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    for report in reports:
        (reports_dir / f"{report['subject']['criterion']}.json").write_text(
            json.dumps(report), encoding="utf-8"
        )
    if dev_rate is not None:
        (run_dir / "dev_rate.json").write_text(json.dumps({"dev_rate": dev_rate}), encoding="utf-8")


def test_leg_c_pass_r_ge_10_and_gap_ok(tmp_path):
    reports = [_exit_report(f"c{i}", passed=True, r=30) for i in range(3)]
    _write_exit_run(tmp_path, reports, dev_rate=1.0)
    assert check_exit_run(tmp_path, _sealed_gate_def(), reports) == []


def test_leg_c_fail_banner_r_below_10(tmp_path):
    reports = [_exit_report("c0", passed=True, r=5)]
    _write_exit_run(tmp_path, reports, dev_rate=1.0)
    failures = check_exit_run(tmp_path, _sealed_gate_def(), reports)
    assert any("wilson_ci.r 5" in f for f in failures)


def test_leg_c_fail_banner_missing_rate(tmp_path):
    reports = [_exit_report("c0", passed=True, r=None)]
    _write_exit_run(tmp_path, reports, dev_rate=1.0)
    failures = check_exit_run(tmp_path, _sealed_gate_def(), reports)
    assert any("missing wilson_ci.r" in f for f in failures)


def test_leg_c_fail_dev_rate_absent(tmp_path):
    reports = [_exit_report("c0", passed=True, r=30)]
    _write_exit_run(tmp_path, reports, dev_rate=None)
    failures = check_exit_run(tmp_path, _sealed_gate_def(), reports)
    assert any("dev_rate.json absent" in f for f in failures)


def test_leg_c_fail_gap_exceeds_15pp(tmp_path):
    # held-out rate = 1.0 (all pass), dev_rate 0.80 -> gap 0.20 > 0.15
    reports = [_exit_report(f"c{i}", passed=True, r=30) for i in range(5)]
    _write_exit_run(tmp_path, reports, dev_rate=0.80)
    failures = check_exit_run(tmp_path, _sealed_gate_def(), reports)
    assert any("gap" in f for f in failures)


def test_leg_c_fail_dev_rate_non_finite(tmp_path):
    # stdlib json parses NaN; `NaN > 0.15` is False, so an unguarded gap check would launder a PASS.
    reports = [_exit_report("c0", passed=True, r=30)]
    _write_exit_run(tmp_path, reports, dev_rate=float("nan"))
    failures = check_exit_run(tmp_path, _sealed_gate_def(), reports)
    assert any("out-of-range dev_rate" in f for f in failures)


def test_leg_c_fail_dev_rate_out_of_range(tmp_path):
    reports = [_exit_report("c0", passed=True, r=30)]
    _write_exit_run(tmp_path, reports, dev_rate=5.0)
    failures = check_exit_run(tmp_path, _sealed_gate_def(), reports)
    assert any("out-of-range dev_rate" in f for f in failures)


def test_leg_c_inert_for_inert_gate(tmp_path):
    reports = [_exit_report("c0", passed=True, r=None)]
    _write_exit_run(tmp_path, reports, dev_rate=None)
    inert = {"gate": "G0", "verdict": {"heldout": "inert"}, "criteria": []}
    assert check_exit_run(tmp_path, inert, reports) == []


# --------------------------------------------------------------------------- #
# runner: seal_command / run --exit key gate, ceremony, burn, dev-run blindness
# --------------------------------------------------------------------------- #


def _isolated_benchmarks(tmp_path: Path, monkeypatch) -> Path:
    copy = tmp_path / "benchmarks"
    shutil.copytree(BENCHMARKS, copy)
    monkeypatch.setattr(runner, "BENCHMARKS_ROOT", copy)
    return copy


def test_seal_command_writes_pair(tmp_path, monkeypatch):
    copy = _isolated_benchmarks(tmp_path, monkeypatch)
    monkeypatch.setenv("FREECAD_BUDDY_UNSEAL_KEY", KEY)
    assert runner.seal_command("G1") == 0
    heldout = copy / "g1" / "heldout"
    assert (heldout / seal.MANIFEST_NAME).is_file()
    assert (heldout / seal.ARCHIVE_NAME).is_file()


def test_seal_command_without_key_exits_2(tmp_path, monkeypatch):
    _isolated_benchmarks(tmp_path, monkeypatch)
    monkeypatch.delenv("FREECAD_BUDDY_UNSEAL_KEY", raising=False)
    with pytest.raises(runner.UsageError, match="FREECAD_BUDDY_UNSEAL_KEY"):
        runner.seal_command("G1")


def test_run_exit_without_key_exits_2_no_traceback():
    result = subprocess.run(
        [sys.executable, str(BENCHMARKS / "runner.py"), "run", "G1", "--exit", "--run", "x"],
        capture_output=True,
        text=True,
        env={k: v for k, v in _clean_env().items() if k != "FREECAD_BUDDY_UNSEAL_KEY"},
    )
    assert result.returncode == 2, result.stdout
    assert "FREECAD_BUDDY_UNSEAL_KEY" in result.stderr
    assert "Traceback" not in result.stderr


def _clean_env() -> dict:
    import os

    env = dict(os.environ)
    env.pop("FREECAD_BUDDY_UNSEAL_KEY", None)
    return env


def test_run_exit_passing_eval_without_tokens_does_not_burn(tmp_path, monkeypatch):
    """`--exit` burns only on a substantive eval miss (leg-a/leg-c), never on not-yet-attested
    human tokens — those are bound at the later `verdict --run` step (spec I/O matrix)."""
    copy = _isolated_benchmarks(tmp_path, monkeypatch)
    monkeypatch.setenv("FREECAD_BUDDY_UNSEAL_KEY", KEY)
    runner.seal_command("G1")
    # The scripted double passes every case, so the exit eval PASSES even with no tokens attested.
    assert runner.run_exit_command("G1", "exit-notoken") == 0
    manifest = seal.read_manifest(copy / "g1" / "heldout")
    assert "burned" not in manifest, "a passing exit must not burn the set over absent tokens"


def test_run_exit_ceremony_passes_and_cleans_temp(tmp_path, monkeypatch):
    copy = _isolated_benchmarks(tmp_path, monkeypatch)
    monkeypatch.setenv("FREECAD_BUDDY_UNSEAL_KEY", KEY)
    assert runner.seal_command("G1") == 0
    # The offline scripted double answers every case correctly, so `--exit` PASSES (exit 0) — the
    # eval legs (a/c) drive the exit code + burn, not the human tokens.
    assert runner.run_exit_command("G1", "exit-run-1") == 0, "passing eval -> exit 0, no burn"

    run_dir = copy / "gate-artifacts" / "g1" / "exit-run-1"
    assert (run_dir / "dev_rate.json").is_file()
    reports = list((run_dir / "reports").glob("*.json"))
    assert reports, "exit run wrote no reports"
    for path in reports:
        report = json.loads(path.read_text(encoding="utf-8"))
        assert report["banner"]["wilson_ci"]["r"] >= 10

    # The full exit verdict (`verdict --run`) still needs the two human tokens (leg-d): it FAILs
    # until they are attested against the exit reports, then PASSes.
    assert runner.verdict_command("G1", "exit-run-1") == 1, "no tokens yet -> leg-d FAIL"
    runner.attest_command("G1", "exit-run-1", "rubric_review", "PASS")
    runner.attest_command("G1", "exit-run-1", "spot_audit", "PASS")
    assert runner.verdict_command("G1", "exit-run-1") == 0, "tokens bound -> exit PASS"

    # The unseal event was appended; verdict re-reads stored files (no temp extraction survives).
    manifest = seal.read_manifest(copy / "g1" / "heldout")
    assert manifest["unseal_events"], "unseal event not appended"


def test_run_exit_stores_majority_of_r_report_per_case(tmp_path, monkeypatch):
    """Each stored exit report is the case's MAJORITY-of-R aggregate, not one arbitrary repeat.

    R repeats of a case share a subject.case id, so writing per-repeat collapses to one arbitrary
    survivor on disk — the stored verdict would then be a single repeat, not the majority the banner
    claims. Assert each file records the majority tally (passes/repeats over R>=10) and its
    re-derived verdict matches that majority — the property a per-repeat survivor cannot guarantee.
    """
    from freecad_buddy.contracts.report import derive_verdict

    copy = _isolated_benchmarks(tmp_path, monkeypatch)
    monkeypatch.setenv("FREECAD_BUDDY_UNSEAL_KEY", KEY)
    runner.seal_command("G1")
    assert runner.run_exit_command("G1", "exit-percase") == 0

    run_dir = copy / "gate-artifacts" / "g1" / "exit-percase"
    report_files = sorted((run_dir / "reports").glob("*.json"))
    stored = [json.loads(p.read_text(encoding="utf-8")) for p in report_files]
    stored_case_ids = {r["subject"]["case"] for r in stored}
    assert report_files, "exit run wrote no reports"
    assert len(report_files) == len(stored_case_ids), "one report per distinct case (no collision)"
    for report in stored:
        tally = report["checks"][0]["detail"]["majority"]
        assert tally["repeats"] >= 10 and 0 <= tally["passes"] <= tally["repeats"]
        majority_ok = tally["passes"] * 2 > tally["repeats"]
        assert (derive_verdict(report) == "OK") == majority_ok, "stored verdict is the majority"


def test_run_exit_verdict_re_derives_all_legs(tmp_path, monkeypatch):
    _isolated_benchmarks(tmp_path, monkeypatch)
    monkeypatch.setenv("FREECAD_BUDDY_UNSEAL_KEY", KEY)
    runner.seal_command("G1")
    runner.run_exit_command("G1", "exit-run-2")
    runner.attest_command("G1", "exit-run-2", "rubric_review", "PASS")
    runner.attest_command("G1", "exit-run-2", "spot_audit", "PASS")
    assert runner.verdict_command("G1", "exit-run-2") == 0


def test_exit_verdict_re_derives_stored_verdict_field(tmp_path, monkeypatch):
    """A stored exit report claiming verdict:OK over a failing check re-derives to FAIL (AD-13)."""
    copy = _isolated_benchmarks(tmp_path, monkeypatch)
    monkeypatch.setenv("FREECAD_BUDDY_UNSEAL_KEY", KEY)
    runner.seal_command("G1")
    runner.run_exit_command("G1", "exit-lie")
    runner.attest_command("G1", "exit-lie", "rubric_review", "PASS")
    runner.attest_command("G1", "exit-lie", "spot_audit", "PASS")
    run_dir = copy / "gate-artifacts" / "g1" / "exit-lie"
    victim = sorted((run_dir / "reports").glob("*.json"))[0]
    report = json.loads(victim.read_text(encoding="utf-8"))
    report["verdict"] = "OK"
    report["checks"] = [
        {"id": "x", "passed": False, "detail": {"code": "spec_failed.x", "message": "no"}}
    ]
    victim.write_text(json.dumps(report), encoding="utf-8")
    # The stored verdict:OK is ignored; leg-a re-derives SPEC_FAILED -> exit FAIL.
    assert runner.verdict_command("G1", "exit-lie") == 1


def test_exit_verdict_malformed_report_is_usage_error(tmp_path, monkeypatch):
    """An unparseable stored exit report -> exit-2 UsageError on the auditor path, no traceback."""
    copy = _isolated_benchmarks(tmp_path, monkeypatch)
    monkeypatch.setenv("FREECAD_BUDDY_UNSEAL_KEY", KEY)
    runner.seal_command("G1")
    runner.run_exit_command("G1", "exit-bad")
    run_dir = copy / "gate-artifacts" / "g1" / "exit-bad"
    victim = sorted((run_dir / "reports").glob("*.json"))[0]
    victim.write_text("not json{", encoding="utf-8")
    assert runner.main(["verdict", "G1", "--run", "exit-bad"]) == 2


def test_run_exit_burns_set_on_fail_then_refuses(tmp_path, monkeypatch):
    copy = _isolated_benchmarks(tmp_path, monkeypatch)
    monkeypatch.setenv("FREECAD_BUDDY_UNSEAL_KEY", KEY)
    runner.seal_command("G1")

    # Force a FAIL by stripping the banner rate off every stored report after the eval writes them.
    real_reports = runner._exit_case_reports

    def _no_banner_rate(result, tier):
        reports = real_reports(result, tier)
        for report in reports:
            report["banner"].pop("wilson_ci", None)
        return reports

    monkeypatch.setattr(runner, "_exit_case_reports", _no_banner_rate)
    code = runner.run_exit_command("G1", "exit-fail")
    assert code == 1, "missing R>=10 banner must fail the exit"

    manifest = seal.read_manifest(copy / "g1" / "heldout")
    assert "burned" in manifest

    # A subsequent --exit on the burned set refuses (exit-2).
    monkeypatch.setattr(runner, "_exit_case_reports", real_reports)
    with pytest.raises(runner.UsageError, match="burned"):
        runner.run_exit_command("G1", "exit-after-burn")


def test_dev_stub_run_never_touches_heldout(tmp_path, monkeypatch):
    copy = _isolated_benchmarks(tmp_path, monkeypatch)
    heldout = copy / "g1" / "heldout"
    before = {p.name for p in heldout.iterdir()}
    reports, code = runner.run_gate("G1")
    assert code == 1  # honest stub fail, unchanged
    after = {p.name for p in heldout.iterdir()}
    assert before == after, "dev stub run must not write into heldout/"


def test_dev_actor_run_never_touches_heldout(tmp_path, monkeypatch):
    copy = _isolated_benchmarks(tmp_path, monkeypatch)
    heldout = copy / "g1" / "heldout"
    before = {p.name for p in heldout.iterdir()}
    runner.actor_run_command("G1")
    after = {p.name for p in heldout.iterdir()}
    assert before == after, "dev --actor-run must not write into heldout/"


def test_seal_only_gate_g1(tmp_path, monkeypatch):
    _isolated_benchmarks(tmp_path, monkeypatch)
    monkeypatch.setenv("FREECAD_BUDDY_UNSEAL_KEY", KEY)
    with pytest.raises(runner.UsageError, match="only defined for gate G1"):
        runner.seal_command("G0")
