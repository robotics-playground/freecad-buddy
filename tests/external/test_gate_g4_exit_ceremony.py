"""G4 exit: the agent-to-agent cycle, the soak, and the gate's own collectors.

Asserts the recorded evidence rather than re-running the measurements. A 50-job soak inside a unit
test would make the suite's runtime depend on the machine, and a gate verdict must be reproducible
over committed files rather than recomputed per reader.

The health surface IS exercised live, because a sampler that silently returned zero would make
every soak pass and nothing else would catch it.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from benchmarks import runner  # noqa: E402
from freecad_buddy.hosts.phase4 import health  # noqa: E402

G4_DIR = REPO_ROOT / "benchmarks" / "g4"
SOAK = G4_DIR / "soak-results.json"
CYCLE = G4_DIR / "agent-cycle-results.json"


def _load(path: Path) -> dict:
    assert path.is_file(), f"missing evidence: {path.name}"
    return json.loads(path.read_text(encoding="utf-8"))


# --------------------------------------------------------------------------- #
# The health surface — sampled, not assumed
# --------------------------------------------------------------------------- #


def test_Should_read_a_positive_resident_size_When_the_current_process_is_sampled():
    """A sampler that silently returned zero would make every soak pass its growth bar."""
    # Arrange
    pid = os.getpid()

    # Act
    measured = health.rss_bytes(pid)

    # Assert
    assert measured > 0, "RSS sampling returned nothing; the soak bar would be unenforceable"


def test_Should_return_zero_When_the_process_does_not_exist():
    """A missing sample must be visible as a zero, never abort the run being measured."""
    # Arrange
    absent_pid = 999_999_999

    # Act
    measured = health.rss_bytes(absent_pid)

    # Assert
    assert measured == 0


def test_Should_report_no_growth_When_every_sample_is_identical():
    """The flat case, so the growth arithmetic is not passing by accident."""
    # Arrange
    report = health.SoakReport(
        samples=[health.HealthSample(i, 100, 0, i, 0) for i in range(5)]
    )

    # Act
    growth = report.supervisor_growth

    # Assert
    assert growth == 0.0


def test_Should_measure_growth_against_the_peak_When_memory_is_reclaimed_before_the_end():
    """A leak reclaimed just before the run ends still happened; endpoints alone would miss it."""
    # Arrange
    sizes = [100, 100, 200, 100]
    report = health.SoakReport(
        samples=[health.HealthSample(i, size, 0, i, 0) for i, size in enumerate(sizes)]
    )

    # Act
    growth = report.supervisor_growth

    # Assert
    assert growth == pytest.approx(1.0), "growth read the last sample instead of the peak"


def test_Should_sample_the_pool_state_When_a_boundary_sample_is_taken():
    """The soak numbers come from this surface, so it must carry the pool's own counters."""
    # Arrange
    from freecad_buddy.hosts.phase4.pool import WorkerPool

    pool = WorkerPool()

    # Act
    sample = health.sample(pool, job_index=3, session_id="unit")

    # Assert
    assert sample.job_index == 3
    assert sample.session_id == "unit"
    assert sample.supervisor_rss_bytes > 0


# --------------------------------------------------------------------------- #
# G4.5 — the recorded soak
# --------------------------------------------------------------------------- #


def test_Should_run_fifty_jobs_When_the_soak_is_recorded():
    """A soak over fewer jobs is not the 50-job soak the criterion names."""
    # Arrange
    artifact = _load(SOAK)

    # Act
    jobs = artifact["jobs"]

    # Assert
    assert jobs == 50


def test_Should_hold_supervisor_growth_under_the_bar_When_the_soak_ran():
    """The supervisor never imports FreeCAD, so its growth is the load-bearing number."""
    # Arrange
    artifact = _load(SOAK)

    # Act
    growth = artifact["supervisor_growth"]

    # Assert
    assert growth < artifact["growth_bar"], artifact


def test_Should_record_no_hang_and_no_silent_failure_When_the_soak_ran():
    """"No silent failures" is the AD-17 rule the soak exists to enforce."""
    # Arrange
    artifact = _load(SOAK)

    # Act
    hangs, silent = artifact["hangs"], artifact["silent_failures"]

    # Assert
    assert (hangs, silent) == (0, 0), artifact


def test_Should_exercise_failure_paths_When_the_soak_mix_is_chosen():
    """A soak of 50 clean jobs would miss the leak a killed worker leaves behind."""
    # Arrange
    artifact = _load(SOAK)

    # Act
    statuses = artifact["statuses"]

    # Assert
    assert statuses.get("OK", 0) > 0
    assert set(statuses) - {"OK"}, "the mix never exercised a failure path"


def test_Should_resolve_every_job_inside_the_closed_set_When_the_soak_ran():
    """A status nothing downstream can interpret is a silent failure by definition."""
    # Arrange
    artifact = _load(SOAK)
    closed = {
        "OK",
        "SPEC_FAILED",
        "RECOMPUTE_ERROR",
        "TIMEOUT",
        "OOM_KILLED",
        "WORKER_CRASHED",
        "INVALID_INPUT",
    }

    # Act
    observed = set(artifact["statuses"])

    # Assert
    assert observed <= closed, observed - closed


# --------------------------------------------------------------------------- #
# G4.4 — the agent cycle
# --------------------------------------------------------------------------- #


def test_Should_complete_every_step_When_the_agent_cycle_ran():
    """submit -> inspect -> revise -> accept, with nothing waiting on a person."""
    # Arrange
    artifact = _load(CYCLE)

    # Act
    steps = [s["step"] for s in artifact["steps"]]

    # Assert
    assert steps == ["submit", "inspect", "revise", "accept"], artifact
    assert artifact["completed"] is True


def test_Should_record_zero_human_inputs_When_the_cycle_completed():
    """The criterion is "with zero human input", so the count is asserted, not implied."""
    # Arrange
    artifact = _load(CYCLE)

    # Act
    human_inputs = artifact["human_inputs"]

    # Assert
    assert human_inputs == 0


def test_Should_keep_auto_approve_off_When_the_cycle_completed():
    """A cycle completed under a global auto-approve flag proves the flag, not the service.

    The flag IS a human's approval left permanently on, so a run holding it has not shown the
    service can be driven without one.
    """
    # Arrange
    artifact = _load(CYCLE)

    # Act
    auto_approve_off = artifact["auto_approve_off"]

    # Assert
    assert auto_approve_off is True


# --------------------------------------------------------------------------- #
# The gate's own collectors
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("criterion_id", ["G4.4", "G4.5"])
def test_Should_collect_a_passing_report_When_the_evidence_supports_it(criterion_id):
    """The measurable criteria must actually reach OK, or the gate could never turn green."""
    # Arrange
    expected = "OK"

    # Act
    report = runner._collect_g4(criterion_id)

    # Assert
    assert report["verdict"] == expected, report


@pytest.mark.parametrize("criterion_id", ["G4.1", "G4.2", "G4.3"])
def test_Should_name_the_specific_gap_When_a_criterion_is_unmeasured(criterion_id):
    """A generic "no collector" would read as wiring missing rather than a measurement blocked."""
    # Arrange
    report = runner._collect_g4(criterion_id)

    # Act
    message = json.dumps(report)

    # Assert
    assert report["verdict"] != "OK"
    assert "no collector" not in message, "the gap is unnamed"


def test_Should_report_not_collected_When_a_criterions_artifact_is_absent(tmp_path, monkeypatch):
    """A missing artifact must name the command that produces it, not fail opaquely."""
    # Arrange
    monkeypatch.setattr(runner, "BENCHMARKS_ROOT", tmp_path)

    # Act
    report = runner._collect_g4("G4.5")

    # Assert
    assert report["verdict"] != "OK"
    assert "run_soak.py" in json.dumps(report)


def test_Should_derive_the_verdict_When_a_G4_report_is_built():
    """Every report in this runner derives its verdict; a self-graded one could never fail."""
    # Arrange
    failing = runner._g4_check_report("G4.5", passed=False, measured=0.5, detail=None)

    # Act
    verdict = failing["verdict"]

    # Assert
    assert verdict != "OK"


def test_Should_stay_out_of_the_sealable_gates_When_G4_has_no_heldout_split():
    """G4 declares `heldout: inert`; sealing a split that does not exist would burn nothing."""
    # Arrange
    gate_def = runner._load_gate_def("G4")

    # Act
    heldout = gate_def.get("verdict", {}).get("heldout")

    # Assert
    assert heldout == "inert"
    assert "G4" not in runner._SEALABLE_GATES
