"""Gate G2 exit machinery (external / pytest, no FreeCAD).

Covers every I/O matrix row that does not need a live FreeCAD document:
  - the seal -> unseal -> burn ceremony over a tmp held-out set, recording G2 in the manifest;
  - ``run G2 --exit`` without the key -> exit-2, and a gate whose ``verdict.heldout`` is not
    ``sealed`` refusing the flag at all;
  - a dev run never extracting or reading the sealed held-out set;
  - each collector's pass/fail arithmetic against synthetic case outcomes, including the
    thresholds being read from ``gate.yaml`` rather than duplicated in Python;
  - the honest ``not_collected`` G2.6 row naming its Epic-6 dependency;
  - leg-b (the five cited validators' currency), leg-c and leg-d over G2's gate definition.
"""

from __future__ import annotations

import hashlib
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
BENCHMARKS = REPO_ROOT / "benchmarks"
sys.path.insert(0, str(REPO_ROOT))

from benchmarks import runner  # noqa: E402
from benchmarks.harness import g2_collect, seal  # noqa: E402
from benchmarks.harness.report_build import evidence_report  # noqa: E402
from benchmarks.harness.verdict import (  # noqa: E402
    bind_hash,
    check_exit_run,
    check_token,
    check_validator_currency,
)
from freecad_buddy.contracts.report import (  # noqa: E402
    derive_verdict,
    require_wilson_ci_for_rates,
)

KEY = "test-key-g2"

G2_GATE = yaml.safe_load((BENCHMARKS / "g2" / "gate.yaml").read_text(encoding="utf-8"))
CRITERIA = {c["id"]: c for c in G2_GATE["criteria"]}


@dataclass
class FakeOutcome:
    """A stand-in for ``case_run.CaseOutcome`` carrying only what the collectors read."""

    case_id: str
    op_type: str = "pad"
    status: str = "OK"
    checks: list = field(default_factory=list)
    mutation: dict | None = None
    undo: dict | None = None
    error: str | None = None
    fault_kind: str | None = None

    @property
    def passed(self) -> bool:
        return (
            self.status == "OK"
            and bool(self.checks)
            and all(c.get("passed") is True for c in self.checks)
        )


def _passing_checks():
    return [{"id": "assert.expect_volume", "passed": True}]


def _failing_checks():
    return [{"id": "assert.expect_volume", "passed": False}]


def _mutation(**overrides) -> dict:
    block = {
        "post_verify": {
            "passed": True,
            "fully_constrained": True,
            "tnp_audit": {"status": "CLEAN"},
            "explanation": None,
        },
        "rolled_back": False,
        "rollback_proven": None,
    }
    block.update(overrides)
    return block


# --------------------------------------------------------------------------- #
# Seal ceremony over a tmp held-out set
# --------------------------------------------------------------------------- #


def _stage_case(heldout: Path, case_id: str) -> None:
    case_dir = heldout / case_id
    case_dir.mkdir(parents=True)
    (case_dir / "case.yaml").write_text(f"id: {case_id}\n", encoding="utf-8")


def test_sealing_g2_records_g2_in_the_manifest(tmp_path):
    """A G2 seal that recorded ``gate: G1`` would misattribute the whole ceremony."""
    heldout = tmp_path / "heldout"
    for index in range(8):
        _stage_case(heldout, f"g2-heldout-{index:03d}")

    manifest = seal.seal_heldout(
        heldout, sealed_by="op", sealed_at="2026-07-31", key=KEY, gate="G2"
    )

    assert manifest["gate"] == "G2"
    assert manifest["case_count"] == 8


def test_seal_unseal_round_trip_restores_the_cases_and_appends_the_event(tmp_path):
    heldout = tmp_path / "heldout"
    _stage_case(heldout, "g2-heldout-001-sketch")
    seal.seal_heldout(heldout, sealed_by="op", sealed_at="t", key=KEY, gate="G2")

    extract = seal.unseal_heldout(
        heldout, key=KEY, run_id="exit-1", timestamp="t2", git_sha="abc123"
    )
    try:
        assert (extract / "g2-heldout-001-sketch" / "case.yaml").is_file()
    finally:
        import shutil

        shutil.rmtree(extract, ignore_errors=True)

    events = seal.read_manifest(heldout)["unseal_events"]
    assert events == [{"run_id": "exit-1", "timestamp": "t2", "git_sha": "abc123"}]


def test_a_tampered_g2_archive_refuses_to_unseal(tmp_path):
    heldout = tmp_path / "heldout"
    _stage_case(heldout, "g2-heldout-001-sketch")
    seal.seal_heldout(heldout, sealed_by="op", sealed_at="t", key=KEY, gate="G2")
    archive = heldout / seal.ARCHIVE_NAME
    archive.write_bytes(archive.read_bytes() + b"tamper")

    with pytest.raises(seal.SealError):
        seal.unseal_heldout(heldout, key=KEY, run_id="r", timestamp="t", git_sha="s")


def test_a_burned_g2_set_refuses_until_resealed(tmp_path):
    heldout = tmp_path / "heldout"
    _stage_case(heldout, "g2-heldout-001-sketch")
    seal.seal_heldout(heldout, sealed_by="op", sealed_at="t", key=KEY, gate="G2")
    seal.burn_seal(heldout, run_id="exit-1", reason="leg-a failures")

    with pytest.raises(seal.SealError):
        seal.unseal_heldout(heldout, key=KEY, run_id="exit-2", timestamp="t", git_sha="s")

    seal.seal_heldout(heldout, sealed_by="op", sealed_at="t3", key=KEY, gate="G2")
    extract = seal.unseal_heldout(
        heldout, key=KEY, run_id="exit-3", timestamp="t4", git_sha="s"
    )
    import shutil

    shutil.rmtree(extract, ignore_errors=True)


# --------------------------------------------------------------------------- #
# `run G2 --exit` refusals
# --------------------------------------------------------------------------- #


def test_exit_without_the_key_is_a_clean_exit_2(monkeypatch, capsys):
    monkeypatch.delenv(runner._UNSEAL_KEY_ENV, raising=False)

    code = runner.main(["run", "G2", "--exit", "--run", "exit-nokey"])

    assert code == 2
    assert runner._UNSEAL_KEY_ENV in capsys.readouterr().err


def test_exit_is_refused_for_a_gate_that_declares_no_sealed_heldout(monkeypatch, capsys):
    """G0 is ``heldout: inert``; the refusal keys off that, not off a gate-id branch."""
    monkeypatch.setenv(runner._UNSEAL_KEY_ENV, KEY)

    code = runner.main(["run", "G0", "--exit", "--run", "exit-g0"])

    assert code == 2
    assert "sealed" in capsys.readouterr().err


def test_a_dev_run_never_extracts_the_sealed_heldout(tmp_path, monkeypatch):
    """A dev run must leave ``g2/heldout/`` byte-identical — no extraction, no read.

    Hashes the contents rather than listing names: appending an unseal event to ``SEAL.json`` or
    re-sealing over the archive leaves the file names unchanged, so a name comparison would pass
    over exactly the tampering this guards against.
    """
    heldout = BENCHMARKS / "g2" / "heldout"

    def digests() -> dict[str, str]:
        if not heldout.is_dir():
            return {}
        return {
            p.name: hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(heldout.glob("*"))
            if p.is_file()
        }

    before = digests()

    runner.main(["run", "G2", "--run", "devrun-heldout-blind"])

    assert digests() == before


# --------------------------------------------------------------------------- #
# Collector arithmetic
# --------------------------------------------------------------------------- #


def test_g2_1_reads_its_threshold_from_the_gate_not_from_python():
    """Editing ``pass_rule`` must move the bar; a duplicated constant would not."""
    assert g2_collect.rate_bar(CRITERIA["G2.1"]["pass_rule"]) == 0.85
    assert g2_collect.rate_bar(CRITERIA["G2.5"]["pass_rule"]) == 0.90
    assert g2_collect.rate_bar(">=42% first-attempt pass") == 0.42


def test_g2_1_passes_at_the_declared_rate():
    outcomes = [
        FakeOutcome(case_id=f"c{i}", checks=_passing_checks()) for i in range(17)
    ] + [FakeOutcome(case_id=f"c{i}", checks=_failing_checks()) for i in range(17, 20)]

    report = g2_collect.collect_g2_1(CRITERIA["G2.1"], outcomes)

    assert derive_verdict(report) == "OK"
    assert report["checks"][0]["measured"] == 0.85


def test_g2_1_fails_below_the_declared_rate():
    outcomes = [
        FakeOutcome(case_id=f"c{i}", checks=_passing_checks()) for i in range(16)
    ] + [FakeOutcome(case_id=f"c{i}", checks=_failing_checks()) for i in range(16, 20)]

    report = g2_collect.collect_g2_1(CRITERIA["G2.1"], outcomes)

    assert derive_verdict(report) != "OK"


def test_g2_1_counts_an_errored_command_as_a_fail_not_an_exclusion():
    """Dropping an errored case would raise the rate by shrinking the denominator."""
    outcomes = [FakeOutcome(case_id="ok", checks=_passing_checks())] + [
        FakeOutcome(case_id="boom", status="RECOMPUTE_ERROR", checks=_failing_checks())
    ]

    report = g2_collect.collect_g2_1(CRITERIA["G2.1"], outcomes)

    assert report["checks"][0]["measured"] == 0.5


def test_g2_1_takes_the_majority_of_repeats_per_case():
    outcomes = [
        FakeOutcome(case_id="c1", checks=_passing_checks()),
        FakeOutcome(case_id="c1", checks=_passing_checks()),
        FakeOutcome(case_id="c1", checks=_failing_checks()),
    ]

    report = g2_collect.collect_g2_1(CRITERIA["G2.1"], outcomes)

    assert report["checks"][0]["measured"] == 1.0


def test_g2_1_is_uncollected_when_no_case_was_driven():
    report = g2_collect.collect_g2_1(CRITERIA["G2.1"], [])

    assert derive_verdict(report) == "INVALID_INPUT"


def test_g2_2_requires_a_post_verify_record_on_every_executed_op():
    outcomes = [
        FakeOutcome(case_id="c1", mutation=_mutation()),
        FakeOutcome(case_id="c2", mutation={}),
    ]

    report = g2_collect.collect_g2_2(CRITERIA["G2.2"], outcomes)

    assert derive_verdict(report) != "OK"
    assert report["checks"][0]["measured"] == 0.5


def test_g2_2_fails_a_failed_verify_whose_rollback_is_unproven():
    """``rolled_back`` with no proof is the unproven-rollback path, a failure not a record."""
    outcomes = [
        FakeOutcome(
            case_id="c1",
            mutation=_mutation(
                post_verify={
                    "passed": False,
                    "explanation": "shape invalid",
                    "tnp_audit": {"status": "CLEAN"},
                },
                rolled_back=True,
                rollback_proven=None,
            ),
        )
    ]

    report = g2_collect.collect_g2_2(CRITERIA["G2.2"], outcomes)

    assert derive_verdict(report) != "OK"
    assert "unproven" in json.dumps(report)


def test_g2_2_fails_a_rollback_with_no_human_readable_explanation():
    outcomes = [
        FakeOutcome(
            case_id="c1",
            mutation=_mutation(
                post_verify={"passed": False, "explanation": "", "tnp_audit": {}},
                rolled_back=True,
                rollback_proven="rolled_back_verified",
            ),
        )
    ]

    report = g2_collect.collect_g2_2(CRITERIA["G2.2"], outcomes)

    assert derive_verdict(report) != "OK"
    assert "explanation" in json.dumps(report)


def test_g2_2_passes_a_proven_rollback_carrying_its_reason():
    outcomes = [
        FakeOutcome(
            case_id="c1",
            mutation=_mutation(
                post_verify={
                    "passed": False,
                    "explanation": "recompute produced an invalid shape",
                    "tnp_audit": {},
                },
                rolled_back=True,
                rollback_proven="rolled_back_verified",
            ),
        )
    ]

    report = g2_collect.collect_g2_2(CRITERIA["G2.2"], outcomes)

    assert derive_verdict(report) == "OK"


def test_g2_3_requires_matches_pre_op_on_every_op():
    outcomes = [
        FakeOutcome(case_id="c1", mutation=_mutation(), undo={"matches_pre_op": True}),
        FakeOutcome(case_id="c2", mutation=_mutation(), undo={"matches_pre_op": False}),
    ]

    report = g2_collect.collect_g2_3(CRITERIA["G2.3"], outcomes)

    assert derive_verdict(report) != "OK"
    assert report["checks"][0]["measured"] == 0.5


def test_g2_3_treats_a_none_matches_pre_op_as_a_collector_defect():
    """``None`` means no expectation was supplied — a defect, never a passing undo."""
    outcomes = [
        FakeOutcome(case_id="c1", mutation=_mutation(), undo={"matches_pre_op": None})
    ]

    report = g2_collect.collect_g2_3(CRITERIA["G2.3"], outcomes)

    assert derive_verdict(report) != "OK"
    assert "expect_fingerprint" in json.dumps(report)


def test_g2_3_reports_the_snapshot_restore_path_when_taken():
    outcomes = [
        FakeOutcome(
            case_id="c1",
            mutation=_mutation(rollback_proven="rolled_back_via_snapshot"),
            undo={"matches_pre_op": True},
        )
    ]

    report = g2_collect.collect_g2_3(CRITERIA["G2.3"], outcomes)

    assert derive_verdict(report) == "OK"
    assert "c1" in json.dumps(report["checks"][-1])


def test_g2_4_fails_when_the_element_map_is_unavailable():
    """``audit_references`` returns wholesale UNSUPPORTED — it must never read as clean."""
    outcomes = [
        FakeOutcome(
            case_id="tnp-a",
            mutation=_mutation(
                post_verify={"passed": True, "tnp_audit": {"status": "FLAGGED"}}
            ),
        )
    ]

    report = g2_collect.collect_g2_4(CRITERIA["G2.4"], outcomes, element_map_available=False)

    assert derive_verdict(report) != "OK"
    assert "UNSUPPORTED" in json.dumps(report)


def test_g2_4_also_fails_when_the_probe_result_is_unknown():
    report = g2_collect.collect_g2_4(CRITERIA["G2.4"], [], element_map_available=None)

    assert derive_verdict(report) != "OK"


def test_g2_4_requires_every_declared_scenario_flagged():
    assert g2_collect.flagged_bar(CRITERIA["G2.4"]["pass_rule"]) == 5
    outcomes = [
        FakeOutcome(
            case_id=f"tnp-{i}",
            fault_kind="planted_defect",
            mutation=_mutation(
                post_verify={"passed": True, "tnp_audit": {"status": "FLAGGED"}}
            ),
        )
        for i in range(5)
    ]

    report = g2_collect.collect_g2_4(CRITERIA["G2.4"], outcomes, element_map_available=True)

    assert derive_verdict(report) == "OK"


def test_g2_4_fails_a_false_clean_scenario():
    outcomes = [
        FakeOutcome(
            case_id=f"tnp-{i}",
            fault_kind="planted_defect",
            mutation=_mutation(
                post_verify={"passed": True, "tnp_audit": {"status": "FLAGGED"}}
            ),
        )
        for i in range(4)
    ] + [
        FakeOutcome(
            case_id="tnp-4",
            fault_kind="planted_defect",
            mutation=_mutation(post_verify={"passed": True, "tnp_audit": {"status": "CLEAN"}}),
        )
    ]

    report = g2_collect.collect_g2_4(CRITERIA["G2.4"], outcomes, element_map_available=True)

    assert derive_verdict(report) != "OK"
    assert "tnp-4" in json.dumps(report)


def test_g2_4_fails_a_control_that_was_flagged():
    outcomes = [
        FakeOutcome(
            case_id=f"tnp-{i}",
            fault_kind="planted_defect",
            mutation=_mutation(
                post_verify={"passed": True, "tnp_audit": {"status": "FLAGGED"}}
            ),
        )
        for i in range(5)
    ] + [
        FakeOutcome(
            case_id="control-1",
            fault_kind="clean_control",
            mutation=_mutation(
                post_verify={"passed": True, "tnp_audit": {"status": "FLAGGED"}}
            ),
        )
    ]

    report = g2_collect.collect_g2_4(CRITERIA["G2.4"], outcomes, element_map_available=True)

    assert derive_verdict(report) != "OK"
    assert "control-1" in json.dumps(report)


@pytest.mark.parametrize("criterion_id", ["G2.2", "G2.3", "G2.5"])
def test_a_partly_driven_split_is_uncollected_not_a_clean_rate(criterion_id):
    """One clean case among 39 refused ones must not report a 100 % rate.

    Counting only the cases that executed divides by a denominator the split silently shrank, so
    a run where nearly every command was refused would report the criterion green off a single
    measurement. Any unresolved case makes the criterion uncollected instead.
    """
    driven = FakeOutcome(
        case_id="c0",
        op_type="sketch",
        checks=_passing_checks(),
        mutation=_mutation(),
        undo={"matches_pre_op": True},
    )
    refused = [
        FakeOutcome(
            case_id=f"c{i}",
            op_type="sketch",
            status="UNRESOLVED",
            error="preview refused the command",
        )
        for i in range(1, 40)
    ]
    collect = getattr(g2_collect, "collect_" + criterion_id.replace(".", "_").lower())

    report = collect(CRITERIA[criterion_id], [driven, *refused])

    assert derive_verdict(report) != "OK"
    assert "preview refused the command" in json.dumps(report)


def test_g2_5_grades_only_the_sketch_benchmark():
    outcomes = [
        FakeOutcome(
            case_id=f"s{i}",
            op_type="sketch",
            mutation=_mutation(
                post_verify={"passed": True, "fully_constrained": True, "tnp_audit": {}}
            ),
        )
        for i in range(9)
    ] + [
        FakeOutcome(
            case_id="s9",
            op_type="sketch",
            mutation=_mutation(
                post_verify={"passed": True, "fully_constrained": False, "tnp_audit": {}}
            ),
        ),
        FakeOutcome(case_id="pad1", op_type="pad", mutation=_mutation()),
    ]

    report = g2_collect.collect_g2_5(CRITERIA["G2.5"], outcomes)

    assert derive_verdict(report) == "OK"
    assert report["checks"][0]["measured"] == 0.9


def test_g2_5_counts_a_sketch_that_never_built_as_not_constrained():
    """Excluding it would let a benchmark that produced no sketches report a high rate."""
    outcomes = [
        FakeOutcome(case_id="s1", op_type="sketch", mutation=None),
        FakeOutcome(
            case_id="s2",
            op_type="sketch",
            mutation=_mutation(
                post_verify={"passed": True, "fully_constrained": True, "tnp_audit": {}}
            ),
        ),
    ]

    report = g2_collect.collect_g2_5(CRITERIA["G2.5"], outcomes)

    assert report["checks"][0]["measured"] == 0.5
    assert derive_verdict(report) != "OK"


def test_g2_6_is_an_honest_not_collected_naming_its_epic_6_dependency():
    report = g2_collect.collect_g2_6(CRITERIA["G2.6"])

    assert derive_verdict(report) == "INVALID_INPUT"
    message = report["checks"][0]["detail"]["message"]
    assert "ablation" in message
    assert "Epic-6" in message or "Epic 6" in message


# --------------------------------------------------------------------------- #
# Verdict legs over G2's gate definition
# --------------------------------------------------------------------------- #


def test_leg_b_covers_all_five_cited_g2_validators():
    """An unscored validator is not citable (NFR2), so leg-b must name each missing one."""
    failures = check_validator_currency(G2_GATE, {}, lambda _n: "")

    named = " ".join(failures)
    for validator in ("assertions", "run_mutation", "fingerprint", "audit_references",
                      "verify_sketch"):
        assert validator in named


def test_leg_b_is_current_for_the_committed_g2_scores():
    """A clean working tree must read CURRENT — the runner and the scorer hash identically."""
    validators = runner._load_validators()

    failures = check_validator_currency(G2_GATE, validators, runner._validator_src_hasher)

    stale = [f for f in failures if "stale" in f or "not in registry" in f]
    assert stale == [], stale


def test_leg_b_stales_a_validator_whose_source_changed():
    validators = runner._load_validators()

    failures = check_validator_currency(
        G2_GATE, validators, lambda name: "0" * 64
    )

    assert any("assertions" in f and "stale" in f for f in failures)


def test_leg_c_engages_for_g2_because_its_heldout_is_sealed(tmp_path):
    """``check_exit_run`` keys off the gate's own declaration, so G2 engages with no edit."""
    report = evidence_report("c1", [{"id": "c1", "passed": True, "detail": {}}])
    report["banner"]["wilson_ci"] = {"r": 3, "n": 10, "rate": 0.3, "low": 0.1, "high": 0.6}

    failures = check_exit_run(tmp_path, G2_GATE, [report])

    assert any("wilson_ci.r 3" in f for f in failures)


def test_leg_c_passes_with_r_at_least_ten_and_a_gap_within_fifteen_points(tmp_path):
    reports = []
    for index in range(10):
        report = evidence_report(f"c{index}", [{"id": "c", "passed": True, "detail": {}}])
        report["banner"]["wilson_ci"] = {"r": 10, "n": 10, "rate": 1.0, "low": 0.7, "high": 1.0}
        report["subject"]["case"] = f"c{index}"
        reports.append(report)
    (tmp_path / "dev_rate.json").write_text(json.dumps({"dev_rate": 0.9}), encoding="utf-8")

    assert check_exit_run(tmp_path, G2_GATE, reports) == []


def test_leg_c_fails_a_gap_wider_than_fifteen_points(tmp_path):
    reports = []
    for index in range(10):
        report = evidence_report(f"c{index}", [{"id": "c", "passed": True, "detail": {}}])
        report["banner"]["wilson_ci"] = {"r": 10, "n": 10, "rate": 1.0, "low": 0.7, "high": 1.0}
        report["subject"]["case"] = f"c{index}"
        reports.append(report)
    (tmp_path / "dev_rate.json").write_text(json.dumps({"dev_rate": 0.5}), encoding="utf-8")

    failures = check_exit_run(tmp_path, G2_GATE, reports)

    assert any("gap" in f for f in failures)


def test_leg_c_fails_a_sealed_gate_with_no_dev_rate(tmp_path):
    report = evidence_report("c1", [{"id": "c1", "passed": True, "detail": {}}])
    report["banner"]["wilson_ci"] = {"r": 10, "n": 10, "rate": 1.0, "low": 0.7, "high": 1.0}

    failures = check_exit_run(tmp_path, G2_GATE, [report])

    assert any("dev_rate.json absent" in f for f in failures)


def test_leg_d_requires_both_g2_tokens_bound_to_the_exit_reports(tmp_path):
    assert G2_GATE["required_tokens"] == ["assertion_review", "spot_audit"]
    reports = [evidence_report("c1", [{"id": "c1", "passed": True, "detail": {}}])]
    human = tmp_path / "human"
    human.mkdir()

    assert len(check_token(tmp_path, reports, G2_GATE["required_tokens"])) == 2

    for token_type in G2_GATE["required_tokens"]:
        (human / f"{token_type}.json").write_text(
            json.dumps(
                {
                    "token_type": token_type,
                    "binds_reports_sha256": bind_hash(reports),
                    "outcome": "PASS",
                }
            ),
            encoding="utf-8",
        )

    assert check_token(tmp_path, reports, G2_GATE["required_tokens"]) == []


def test_leg_d_rejects_a_token_bound_to_different_reports(tmp_path):
    reports = [evidence_report("c1", [{"id": "c1", "passed": True, "detail": {}}])]
    other = [evidence_report("c2", [{"id": "c2", "passed": True, "detail": {}}])]
    human = tmp_path / "human"
    human.mkdir()
    for token_type in G2_GATE["required_tokens"]:
        (human / f"{token_type}.json").write_text(
            json.dumps(
                {
                    "token_type": token_type,
                    "binds_reports_sha256": bind_hash(other),
                    "outcome": "PASS",
                }
            ),
            encoding="utf-8",
        )

    failures = check_token(tmp_path, reports, G2_GATE["required_tokens"])

    assert len(failures) == 2
    assert all("not bound" in f for f in failures)


# --------------------------------------------------------------------------- #
# The whole `run G2` path
# --------------------------------------------------------------------------- #


def test_run_g2_writes_six_reports_and_exits_one_without_a_live_runtime(tmp_path, monkeypatch):
    monkeypatch.setattr(runner, "BENCHMARKS_ROOT", BENCHMARKS)

    code = runner.main(["run", "G2", "--run", "pytest-g2-offline"])

    assert code == 1
    reports_dir = BENCHMARKS / "gate-artifacts" / "g2" / "pytest-g2-offline" / "reports"
    written = sorted(p.stem for p in reports_dir.glob("*.json"))
    assert written == ["G2.1", "G2.2", "G2.3", "G2.4", "G2.5", "G2.6"]
    for path in reports_dir.glob("*.json"):
        report = json.loads(path.read_text(encoding="utf-8"))
        assert derive_verdict(report) != "OK", f"{path.stem} claims a pass with no live runtime"


def test_every_run_g2_report_names_why_it_could_not_be_collected(tmp_path, monkeypatch):
    """An honest failure states its cause; a bare "no collector" would hide the real gap.

    The run is driven here rather than read from a previous test's artifacts: depending on a
    sibling test's side effect in a gitignored directory made this skip silently under `-k` and
    under a sharded CI run, so the assertion never executed.
    """
    monkeypatch.setattr(runner, "BENCHMARKS_ROOT", BENCHMARKS)

    runner.main(["run", "G2", "--run", "pytest-g2-report-messages"])

    reports_dir = BENCHMARKS / "gate-artifacts" / "g2" / "pytest-g2-report-messages" / "reports"
    paths = sorted(reports_dir.glob("*.json"))
    assert len(paths) == 6
    for path in paths:
        report = json.loads(path.read_text(encoding="utf-8"))
        message = report["checks"][0]["detail"]["message"]
        assert message.strip()
        assert "no collector for" not in message


def test_a_g2_report_is_filed_under_g2_not_g0():
    """The stored evidence must name the gate that produced it.

    ``evidence_report`` hardcoded ``gate: "G0"``, so every G2 report an auditor sorts by
    ``subject.gate`` at the exit ceremony filed itself under the wrong gate.
    """
    report = evidence_report("G2.4", [{"id": "x", "measured": 1, "expected": 1, "passed": True}])

    assert report["subject"]["gate"] == "G2"
    assert g2_collect.collect_g2_6(CRITERIA["G2.6"])["subject"]["gate"] == "G2"


def test_g2_4_grades_the_fault_suite_not_the_command_benchmark():
    """A dev command case declares no fault kind and must not be scored as a TNP scenario.

    Keyed on ``fault_kind != "clean_control"``, all 40 dev cases counted as planted defects, so a
    silent guard reported 40 false-cleans — a failure naming a cause that never happened.
    """
    dev = [
        FakeOutcome(
            case_id=f"dev-{i}",
            mutation=_mutation(post_verify={"passed": True, "tnp_audit": {"status": "CLEAN"}}),
        )
        for i in range(40)
    ]

    report = g2_collect.collect_g2_4(CRITERIA["G2.4"], dev, element_map_available=True)

    assert derive_verdict(report) != "OK"
    message = json.dumps(report)
    assert "no TNP scenario driven" in message
    assert "dev-0" not in message


def test_a_wired_resolver_without_an_evaluator_refuses_before_the_unseal(monkeypatch):
    """Whatever makes the G2 eval raise must refuse before the set is decrypted, never after.

    The precondition gated on the resolver alone while ``_g2_exit_eval`` is still a stub, so
    wiring a resolver would spend an unseal event on a run that measures nothing.
    """
    monkeypatch.setattr(runner, "_command_resolver", lambda: (lambda case: {"tool": "t"}))

    with pytest.raises(runner.UsageError) as excinfo:
        runner._g2_exit_precondition()

    assert "evaluator" in str(excinfo.value)


def test_a_reused_run_dir_is_refused_whatever_the_report_is_named(tmp_path, monkeypatch):
    """``_load_exit_reports`` globs every ``*.json``, so the reuse guard must too.

    Matching only ``G2.*.json`` let a stray report join the held-out gap math and burn the set
    over contamination the guard exists to prevent.
    """
    monkeypatch.setattr(runner, "BENCHMARKS_ROOT", tmp_path)
    reports = tmp_path / "gate-artifacts" / "g2" / "reused" / "reports"
    reports.mkdir(parents=True)
    (reports / "g2-heldout-001-sketch.json").write_text("{}", encoding="utf-8")

    with pytest.raises(runner.UsageError) as excinfo:
        runner._refuse_reused_run_dir("G2", "reused")

    assert "g2-heldout-001-sketch.json" in str(excinfo.value)


def test_every_targets_validator_names_the_module_that_defines_it():
    """A dead ``name@module.path`` pointer reads as authoritative and misdirects an edit.

    All 13 ``audit_references`` cases pointed at ``usecases.verify``, which does not define it.
    """
    import importlib

    for case_yaml in sorted((BENCHMARKS / "g2" / "fault-injection").glob("*/*/case.yaml")):
        case = yaml.safe_load(case_yaml.read_text(encoding="utf-8"))
        target = (case or {}).get("targets_validator")
        if not target or "@" not in target:
            continue
        _, dotted = target.split("@", 1)
        module_path, _, fn_name = dotted.rpartition(".")
        prefix = "benchmarks." if module_path.startswith("harness.") else "freecad_buddy."
        module = importlib.import_module(prefix + module_path)
        assert hasattr(module, fn_name), f"{case_yaml.name}: {dotted} does not exist"


# --------------------------------------------------------------------------- #
# Populations: repeats are folded per case, and only executed ops are graded
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("criterion_id", ["G2.3", "G2.5"])
def test_a_rate_criterion_folds_repeats_before_measuring(criterion_id):
    """A split is driven at R repeats per case, so a rate must count cases, not driven rows.

    Counting rows makes R a multiplier on the population instead of a majority vote: one case
    failing every repeat and one passing every repeat is 50 % of cases either way, but a collector
    reading rows silently reweights whichever case was driven more often.
    """
    collect = {
        "G2.2": g2_collect.collect_g2_2,
        "G2.3": g2_collect.collect_g2_3,
        "G2.5": g2_collect.collect_g2_5,
    }[criterion_id]
    good = _mutation()
    bad = _mutation(post_verify={"passed": False, "fully_constrained": False}, rolled_back=False)
    outcomes = [
        FakeOutcome(
            case_id="c-good",
            op_type="sketch",
            checks=_passing_checks(),
            mutation=good,
            undo={"matches_pre_op": True},
        )
        for _ in range(5)
    ] + [
        FakeOutcome(
            case_id="c-bad",
            op_type="sketch",
            checks=_passing_checks(),
            mutation=bad,
            undo={"matches_pre_op": False},
        )
        for _ in range(5)
    ]

    report = collect(CRITERIA[criterion_id], outcomes)

    rate = next(c for c in report["checks"] if c.get("measured_kind") == "rate")
    assert rate["measured"] == 0.5, "two cases, one passing: the rate is over cases not repeats"
    assert report["banner"]["wilson_ci"]["n"] == 2


def test_g2_2_folds_repeats_before_measuring_record_presence():
    """One of two cases missing its ``post_verify`` is 50 %, whatever R it was driven at.

    Counting driven rows made the measured rate a function of the repeat count rather than of how
    many cases carried a record.
    """
    recorded = [
        FakeOutcome(
            case_id="c-recorded",
            checks=_passing_checks(),
            mutation=_mutation(),
            undo={"matches_pre_op": True},
        )
        for _ in range(5)
    ]
    unrecorded = [
        FakeOutcome(
            case_id="c-unrecorded",
            checks=_passing_checks(),
            mutation={"rolled_back": False},
            undo={"matches_pre_op": True},
        )
        for _ in range(5)
    ]

    report = g2_collect.collect_g2_2(CRITERIA["G2.2"], [*recorded, *unrecorded])

    rate = next(c for c in report["checks"] if c.get("measured_kind") == "rate")
    assert rate["measured"] == 0.5
    assert report["banner"]["wilson_ci"]["n"] == 2
    rollback = next(c for c in report["checks"] if c["id"] == "G2.2.rollback")
    assert rollback["detail"]["message"].count("c-unrecorded") == 1, "one message per case, not R"


def test_g2_4_counts_distinct_scenarios_not_driven_repeats():
    """The rule is 5/5 flagged over five SCENARIOS; one scenario driven at R=5 is not five.

    Tallying driven rows let a single flagged scenario satisfy the criterion outright.
    """
    outcomes = [
        FakeOutcome(
            case_id="tnp-a",
            checks=_passing_checks(),
            mutation=_mutation(post_verify={"passed": True, "tnp_audit": {"status": "FLAGGED"}}),
            fault_kind="planted_defect",
        )
        for _ in range(5)
    ]

    report = g2_collect.collect_g2_4(CRITERIA["G2.4"], outcomes, element_map_available=True)

    flagged = next(c for c in report["checks"] if c["id"] == "G2.4.flagged")
    assert flagged["measured"] == 1
    assert flagged["passed"] is False
    assert report["verdict"] != "OK"


def test_g2_4_does_not_credit_a_falsely_flagged_control_toward_the_bar():
    """A flagged control is a false alarm; it must not raise the flagged-scenario count.

    Both branches incremented the same counter, so a control could substitute for a scenario.
    """
    flagged_defects = [
        FakeOutcome(
            case_id=f"tnp-{name}",
            checks=_passing_checks(),
            mutation=_mutation(post_verify={"passed": True, "tnp_audit": {"status": "FLAGGED"}}),
            fault_kind="planted_defect",
        )
        for name in ("a", "b", "c", "d")
    ]
    flagged_control = FakeOutcome(
        case_id="tnp-control",
        checks=_passing_checks(),
        mutation=_mutation(post_verify={"passed": True, "tnp_audit": {"status": "FLAGGED"}}),
        fault_kind="clean_control",
    )

    report = g2_collect.collect_g2_4(
        CRITERIA["G2.4"], [*flagged_defects, flagged_control], element_map_available=True
    )

    flagged = next(c for c in report["checks"] if c["id"] == "G2.4.flagged")
    assert flagged["measured"] == 4, "the control must not count as a fifth flagged scenario"
    assert any(c["id"] == "G2.4.false_flag" for c in report["checks"])


@pytest.mark.parametrize("criterion_id", ["G2.2", "G2.3"])
def test_a_refused_apply_is_not_counted_as_an_executed_op(criterion_id):
    """G2.2/G2.3 grade EXECUTED ops; a refused apply executed nothing.

    ``case_run._apply`` returns an ``INVALID_INPUT`` envelope with no ``mutation`` for a refused
    confirm, and ``run_case`` then skips the undo. Counting that row against a 100 % bar made a
    benchmark performing exactly at G2.1's >=85 % bar structurally unable to pass either.
    """
    collect = {"G2.2": g2_collect.collect_g2_2, "G2.3": g2_collect.collect_g2_3}[criterion_id]
    executed = [
        FakeOutcome(
            case_id=f"c{i}",
            checks=_passing_checks(),
            mutation=_mutation(),
            undo={"matches_pre_op": True},
        )
        for i in range(9)
    ]
    refused = FakeOutcome(case_id="c-refused", status="INVALID_INPUT", mutation=None, undo=None)

    report = collect(CRITERIA[criterion_id], [*executed, refused])

    rate = next(c for c in report["checks"] if c.get("measured_kind") == "rate")
    assert rate["measured"] == 1.0
    assert report["verdict"] == "OK"
    assert "c-refused" in rate["detail"]["message"], "the refused case must still be named"


def test_a_refused_apply_is_not_reported_as_a_missing_expectation():
    """G2.3 must not blame a cause the driver makes impossible.

    ``run_case`` always passes ``expect_fingerprint``, so "no expect_fingerprint supplied" named a
    collector defect that cannot occur; the real cause is an apply that never committed.
    """
    refused = [
        FakeOutcome(case_id="c-refused", status="INVALID_INPUT", mutation=None, undo=None)
        for _ in range(5)
    ]
    executed = [
        FakeOutcome(
            case_id="c-ok",
            checks=_passing_checks(),
            mutation=_mutation(),
            undo={"matches_pre_op": True},
        )
    ]

    report = g2_collect.collect_g2_3(CRITERIA["G2.3"], [*executed, *refused])

    assert not any(c["id"] == "G2.3.expectation" for c in report["checks"])


@pytest.mark.parametrize("criterion_id", ["G2.2", "G2.3"])
def test_a_split_where_nothing_executed_is_uncollected(criterion_id):
    """Every driven case refused: there is no executed population, so nothing was measured."""
    collect = {"G2.2": g2_collect.collect_g2_2, "G2.3": g2_collect.collect_g2_3}[criterion_id]
    refused = [
        FakeOutcome(case_id=f"c{i}", status="INVALID_INPUT", mutation=None, undo=None)
        for i in range(4)
    ]

    report = collect(CRITERIA[criterion_id], refused)

    assert report["verdict"] == "INVALID_INPUT"
    assert "executed an op" in report["checks"][0]["detail"]["message"]


# --------------------------------------------------------------------------- #
# Rate reports carry the interval the contract obliges
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("criterion_id", ["G2.1", "G2.2", "G2.3", "G2.5"])
def test_every_g2_rate_check_declares_its_kind_and_carries_an_interval(criterion_id):
    """A bare rate with no interval is what AD-14 forbids, and the guard keys off the declaration.

    ``require_wilson_ci_for_rates`` only fires for a check declaring ``measured_kind: "rate"``, so
    a collector omitting the declaration silently opts every G2 rate out of the enforcement.
    """
    collect = {
        "G2.1": g2_collect.collect_g2_1,
        "G2.2": g2_collect.collect_g2_2,
        "G2.3": g2_collect.collect_g2_3,
        "G2.5": g2_collect.collect_g2_5,
    }[criterion_id]
    outcomes = [
        FakeOutcome(
            case_id=f"c{i}",
            op_type="sketch",
            checks=_passing_checks(),
            mutation=_mutation(),
            undo={"matches_pre_op": True},
        )
        for i in range(4)
    ]

    report = collect(CRITERIA[criterion_id], outcomes)

    rates = [c for c in report["checks"] if c.get("measured_kind") == "rate"]
    assert rates, f"{criterion_id} measures a rate and must declare it"
    ci = report["banner"]["wilson_ci"]
    assert ci["n"] == 4 and ci["r"] == 4
    require_wilson_ci_for_rates(report)


# --------------------------------------------------------------------------- #
# Splits driven, and run-dir contamination in both directions
# --------------------------------------------------------------------------- #


def test_the_fault_suite_is_driven_so_g2_4_has_a_population():
    """G2.4 grades only fault-declaring cases, so a dev-only drive leaves it with none.

    ``_drive_live_cases`` drove ``dev/`` alone, where every case reports ``fault_kind`` of None.
    """
    assert "fault-injection" in runner._G2_DEV_SPLITS
    cases = runner._load_g2_cases("G2", "fault-injection")
    assert cases, "the fault split must load; its cases nest one level deeper than dev/"
    kinds = {runner._declared_fault_kind(c) for c in cases}
    assert "planted_defect" in kinds and "clean_control" in kinds


def test_the_case_loader_finds_cases_nested_at_any_depth(tmp_path):
    """A fault case sits two levels deep, a dev case one.

    A one-level glob returned zero cases for a fault split instead of failing.
    """
    from benchmarks.g2 import case_run

    nested = tmp_path / "suite" / "case-a"
    nested.mkdir(parents=True)
    (nested / "case.yaml").write_text("id: case-a\n", encoding="utf-8")
    flat = tmp_path / "case-b"
    flat.mkdir()
    (flat / "case.yaml").write_text("id: case-b\n", encoding="utf-8")

    assert {c["id"] for c in case_run.load_cases(tmp_path)} == {"case-a", "case-b"}


def test_a_dev_run_refuses_an_exit_ceremony_run_dir(tmp_path, monkeypatch):
    """Contamination runs both ways: a dev run must not write into an exit run dir.

    ``dev_rate.json`` routes verdict/attest through ``_load_exit_reports``, which globs every
    stored report — so six dev criterion reports would join the held-out gap math.
    """
    monkeypatch.setattr(runner, "BENCHMARKS_ROOT", tmp_path)
    run_dir = tmp_path / "gate-artifacts" / "g2" / "exit-1"
    run_dir.mkdir(parents=True)
    (run_dir / "dev_rate.json").write_text('{"dev_rate": 0.9}', encoding="utf-8")

    with pytest.raises(runner.UsageError) as excinfo:
        runner._refuse_exit_run_dir("G2", "exit-1")

    assert "exit ceremony" in str(excinfo.value)
    runner._refuse_exit_run_dir("G2", "fresh-id")


def test_an_unscored_validator_records_that_it_was_not_measured():
    """A zero score beside a date, a run id and an n=0 interval reads as a measurement.

    ``n: 0`` yields the interval [0, 1], which a leg-b reader can take as evidence rather than as
    its absence, so a block that was not measured must say why. A validator that WAS measured
    carries its rate and no reason; the two states must stay distinguishable, and a bare zero with
    neither is the one thing that must never appear.
    """
    registry = yaml.safe_load(
        (BENCHMARKS / "_registry" / "validators.yaml").read_text(encoding="utf-8")
    )
    for name in ("assertions", "run_mutation", "fingerprint", "audit_references", "verify_sketch"):
        last_run = registry[name]["last_run"]
        if last_run.get("not_scored"):
            assert last_run["sensitivity"] == 0.0, (
                f"{name} carries a not_scored reason beside a non-zero rate"
            )
            continue
        assert last_run["sensitivity"] > 0.0, (
            f"{name} records a zero score with no reason saying why it was not measured"
        )
        assert last_run["wilson_ci"]["n"] > 0, (
            f"{name} reports a scored rate over an empty population"
        )


def test_a_scored_g2_validator_measured_a_real_population():
    """The suite exists to produce a number; at least one validator must actually carry one."""
    registry = yaml.safe_load(
        (BENCHMARKS / "_registry" / "validators.yaml").read_text(encoding="utf-8")
    )
    scored = [
        name
        for name in ("assertions", "run_mutation", "fingerprint", "audit_references",
                     "verify_sketch")
        if not registry[name]["last_run"].get("not_scored")
    ]

    assert scored, "no G2 validator is scored; the fault suite measured nothing"
