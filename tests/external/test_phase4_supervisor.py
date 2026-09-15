"""Phase 4 supervisor, worker pool, and tree kill (external / pytest, no FreeCAD).

Covers every I/O matrix row in spec-5-2:
  - each exit condition resolving to its closed-set status with structured detail;
  - a deadline killing the WHOLE tree, asserted against a real grandchild process;
  - a dead worker resolving rather than hanging;
  - the bounded queue refusing under backpressure;
  - malformed and absent worker output being refused rather than read as success;
  - the supervisor importing no FreeCAD, transitively, and the guard that keeps it that way.

The lifecycle tests spawn real processes. That is the point: a pool whose kill was only tested
against a mock would pass while leaving orphans, which is the exact bug this story's development
hit and fixed.
"""

from __future__ import annotations

import re
import subprocess
import sys
import threading
import time
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from freecad_buddy.hosts.phase4 import status_map, tree_kill  # noqa: E402
from freecad_buddy.hosts.phase4.pool import QueueFull, WorkerPool  # noqa: E402
from freecad_buddy.hosts.phase4.status_map import Outcome  # noqa: E402
from freecad_buddy.hosts.phase4.supervisor import (  # noqa: E402
    Supervisor,
    build_capabilities,
    validate_spec,
)
from freecad_buddy.usecases.capabilities import exec_registered  # noqa: E402

PAYLOAD_MODULE = "freecad_buddy.hosts.phase4.lifecycle_payloads"

# Long enough that a slow machine does not flake, short enough that the suite stays usable.
_DEADLINE_S = 4.0


def _spec(kind: str, job_id: str | None = None, **limits) -> dict:
    """A well-formed job spec naming a lifecycle payload."""
    return {
        "schema": "fcb.job-spec/1",
        "job_id": job_id or f"j-{kind}",
        "kind": kind,
        "payload": {},
        "payload_module": PAYLOAD_MODULE,
        "limits": limits or None,
    }


def _python_pids() -> set[int]:
    """Every running python.exe pid. Windows-only helper for the orphan assertions."""
    result = subprocess.run(
        ["tasklist", "/FI", "IMAGENAME eq python.exe", "/NH"],
        capture_output=True,
        text=True,
    )
    return {int(m) for m in re.findall(r"python\.exe\s+(\d+)", result.stdout)}


# --------------------------------------------------------------------------- #
# status_map — the single place an observation becomes a status
# --------------------------------------------------------------------------- #


def test_Should_report_OK_When_the_worker_returned_and_nothing_failed():
    """The only path to OK: a clean return whose result survived validation."""
    # Arrange
    outcome = Outcome(returned=True, exit_code=0)

    # Act
    state, detail = status_map.resolve(outcome)

    # Assert
    assert (state, detail) == ("OK", None)


def test_Should_report_TIMEOUT_When_the_deadline_fired_even_though_the_kill_set_an_exit_code():
    """The non-zero exit is a consequence of OUR kill; reporting it would blame our own signal."""
    # Arrange
    outcome = Outcome(deadline_exceeded=True, exit_code=1, signal_number=9)

    # Act
    state, detail = status_map.resolve(outcome)

    # Assert
    assert state == "TIMEOUT"
    assert detail is not None and detail["code"] == "job.timeout"


def test_Should_report_OOM_KILLED_When_the_memory_cap_was_breached():
    """The memory cap outranks the signal it produced, for the same reason as the deadline."""
    # Arrange
    outcome = Outcome(memory_exceeded=True, signal_number=9)

    # Act
    state, _ = status_map.resolve(outcome)

    # Assert
    assert state == "OOM_KILLED"


def test_Should_report_SPEC_FAILED_When_a_clean_return_failed_validation():
    """A worker claiming success it cannot evidence is the "HTTP 200 for a bad part" case."""
    # Arrange
    outcome = Outcome(returned=False, exit_code=0, result_refused=True)

    # Act
    state, detail = status_map.resolve(outcome)

    # Assert
    assert state == "SPEC_FAILED"
    assert detail is not None and detail["code"] == "job.result_refused"


def test_Should_report_WORKER_CRASHED_When_the_process_exited_zero_without_returning():
    """Exit 0 with nothing returned ran nothing; calling it OK would report a no-op as success."""
    # Arrange
    outcome = Outcome(returned=False, exit_code=0)

    # Act
    state, _ = status_map.resolve(outcome)

    # Assert
    assert state == "WORKER_CRASHED"


def test_Should_carry_structured_detail_When_any_status_is_not_OK():
    """AD-17's "none silent" rule: a terminal failure with no machine-readable detail is silent."""
    # Arrange
    outcomes = [
        Outcome(deadline_exceeded=True),
        Outcome(memory_exceeded=True),
        Outcome(result_refused=True),
        Outcome(signal_number=11),
        Outcome(exit_code=3),
        Outcome(returned=False),
    ]

    # Act
    resolved = [status_map.resolve(outcome) for outcome in outcomes]

    # Assert
    for state, detail in resolved:
        assert state != "OK"
        assert detail is not None and detail.get("code") and detail.get("message")


def test_Should_stay_inside_the_closed_set_When_any_outcome_is_resolved():
    """A status outside the contract's closed set could not be expressed on the wire."""
    # Arrange
    from freecad_buddy.contracts.status import TerminalStatus
    from typing import get_args

    closed = set(get_args(TerminalStatus))
    outcomes = [
        Outcome(returned=True),
        Outcome(deadline_exceeded=True),
        Outcome(memory_exceeded=True),
        Outcome(result_refused=True),
        Outcome(signal_number=9),
        Outcome(exit_code=7),
        Outcome(returned=False),
    ]

    # Act
    states = {status_map.resolve(outcome)[0] for outcome in outcomes}

    # Assert
    assert states <= closed, states - closed


# --------------------------------------------------------------------------- #
# Spec validation — refuse before a worker is bound
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    ("spec", "expected"),
    [
        ("not-a-mapping", "must be a mapping"),
        ({}, "no job_id"),
        ({"job_id": "j"}, "no kind"),
        ({"job_id": "j", "kind": "echo", "limits": "nope"}, "limits must be a mapping"),
        (
            {"job_id": "j", "kind": "echo", "limits": {"wall_deadline_s": 0}},
            "must be a positive number",
        ),
        (
            {"job_id": "j", "kind": "echo", "limits": {"memory_bytes": -1}},
            "must be a positive number",
        ),
    ],
)
def test_Should_refuse_When_a_submission_is_malformed(spec, expected):
    """An invalid submission must cost no worker, so it is refused before anything is enqueued."""
    # Arrange
    candidate = spec

    # Act
    problem = validate_spec(candidate)

    # Assert
    assert problem is not None and expected in problem["message"]


def test_Should_accept_When_a_submission_is_well_formed():
    """The happy path of validation, so the refusals above are not vacuously passing."""
    # Arrange
    spec = _spec("echo")

    # Act
    problem = validate_spec(spec)

    # Assert
    assert problem is None


def test_Should_resolve_INVALID_INPUT_When_an_invalid_spec_is_submitted():
    """The refusal must surface as a closed-set status, not as an exception to the caller."""
    # Arrange
    supervisor = Supervisor(pool=WorkerPool(default_deadline_s=_DEADLINE_S))

    # Act
    status = supervisor.submit({"kind": "echo"})

    # Assert
    assert status["state"] == "INVALID_INPUT"
    assert status["detail"]["code"] == "job.invalid_input"


# --------------------------------------------------------------------------- #
# Bounded queue
# --------------------------------------------------------------------------- #


def test_Should_refuse_the_submission_When_the_queue_is_at_its_bound():
    """An unbounded queue converts a traffic burst into host memory exhaustion."""
    # Arrange
    pool = WorkerPool(queue_bound=2, default_deadline_s=_DEADLINE_S)
    pool.submit(_spec("echo", job_id="a"))
    pool.submit(_spec("echo", job_id="b"))

    # Act
    def act():
        return pool.submit(_spec("echo", job_id="c"))

    # Assert
    with pytest.raises(QueueFull):
        act()


def test_Should_report_queue_full_as_a_status_When_the_supervisor_is_over_its_bound():
    """The caller needs a status to act on, not a traceback."""
    # Arrange
    supervisor = Supervisor(pool=WorkerPool(queue_bound=1, default_deadline_s=_DEADLINE_S))
    supervisor.submit(_spec("echo", job_id="a"))

    # Act
    status = supervisor.submit(_spec("echo", job_id="b"))

    # Assert
    assert status["detail"]["code"] == "job.queue_full"


# --------------------------------------------------------------------------- #
# Lifecycle — real processes
# --------------------------------------------------------------------------- #


def test_Should_resolve_OK_and_carry_the_envelope_When_a_payload_returns_cleanly():
    """The clean path end to end, through a real spawned worker."""
    # Arrange
    supervisor = Supervisor(pool=WorkerPool(default_deadline_s=_DEADLINE_S))

    # Act
    status = supervisor.run(_spec("echo"))

    # Assert
    assert status["state"] == "OK"
    assert status["result"]["status"] == "OK"


def test_Should_resolve_WORKER_CRASHED_When_the_payload_raises():
    """A worker that dies mid-job must resolve, never leave its caller waiting."""
    # Arrange
    supervisor = Supervisor(pool=WorkerPool(default_deadline_s=_DEADLINE_S))

    # Act
    status = supervisor.run(_spec("crash"))

    # Assert
    assert status["state"] == "WORKER_CRASHED"
    assert status["detail"]["code"] == "job.worker_crashed"


def test_Should_resolve_WORKER_CRASHED_When_the_worker_exits_without_unwinding():
    """``os._exit`` is the closest a Python payload gets to the native fault G4 plants."""
    # Arrange
    supervisor = Supervisor(pool=WorkerPool(default_deadline_s=_DEADLINE_S))

    # Act
    status = supervisor.run(_spec("hard_exit"))

    # Assert
    assert status["state"] == "WORKER_CRASHED"


def test_Should_refuse_the_result_When_the_worker_exits_cleanly_having_written_nothing():
    """A clean exit with no evidence is a claim, not a result. It must never read as OK."""
    # Arrange
    supervisor = Supervisor(pool=WorkerPool(default_deadline_s=_DEADLINE_S))

    # Act
    status = supervisor.run(_spec("silent_success"))

    # Assert
    assert status["state"] == "SPEC_FAILED"
    assert "result" not in status


def test_Should_resolve_TIMEOUT_When_the_payload_outlives_its_deadline():
    """A hung worker cannot enforce its own deadline, so the supervisor enforces it from outside."""
    # Arrange
    supervisor = Supervisor(pool=WorkerPool(default_deadline_s=60.0))
    started = time.monotonic()

    # Act
    status = supervisor.run(_spec("sleep", wall_deadline_s=1.5))

    # Assert
    assert status["state"] == "TIMEOUT"
    assert time.monotonic() - started < 30.0, "the deadline did not fire"


def test_Should_attach_no_envelope_When_the_job_failed():
    """A failed job carrying the worker's own account would invite trusting it."""
    # Arrange
    supervisor = Supervisor(pool=WorkerPool(default_deadline_s=_DEADLINE_S))

    # Act
    status = supervisor.run(_spec("crash"))

    # Assert
    assert "result" not in status


@pytest.mark.skipif(sys.platform != "win32", reason="orphan probe uses tasklist")
def test_Should_kill_the_grandchild_too_When_a_deadline_kills_the_tree():
    """The failure this story exists to prevent: a top-PID kill that leaves OCCT helpers running.

    Measured during development, twice: first a breakaway flag let the child escape the job, then
    a spawn/assign race let it start before the job existed. Both passed a worker-only assertion
    and left a live orphan, so the assertion has to be about the TREE.
    """
    # Arrange
    pool = WorkerPool(default_deadline_s=60.0)
    spec = _spec("spawn_child_then_sleep", wall_deadline_s=2.0)
    before = _python_pids()
    captured: dict = {}

    # Act
    thread = threading.Thread(target=lambda: captured.update(run=pool.run(spec)))
    thread.start()
    time.sleep(1.2)
    during = _python_pids() - before
    thread.join()
    time.sleep(1.2)
    leaked = sorted(during & _python_pids())

    # Assert
    for pid in leaked:  # never leave a strays behind for the next test
        subprocess.run(["taskkill", "/PID", str(pid), "/F"], capture_output=True)
    assert during, "the payload spawned nothing, so the test proves nothing"
    assert status_map.resolve(captured["run"].outcome)[0] == "TIMEOUT"
    assert leaked == [], f"orphaned processes survived the tree kill: {leaked}"


def test_Should_count_a_killed_tree_When_a_deadline_fires():
    """The health surface reports kills; a kill it did not count is a kill nobody can see."""
    # Arrange
    pool = WorkerPool(default_deadline_s=60.0)

    # Act
    pool.run(_spec("sleep", wall_deadline_s=1.5))

    # Assert
    assert pool.stats.killed_trees == 1
    assert pool.stats.jobs_started == pool.stats.jobs_finished == 1


# --------------------------------------------------------------------------- #
# Tree kill primitives
# --------------------------------------------------------------------------- #


def test_Should_never_set_breakaway_When_spawn_kwargs_are_built():
    """CREATE_BREAKAWAY_FROM_JOB is what lets a child LEAVE the job we are about to kill."""
    # Arrange
    kwargs = tree_kill.spawn_kwargs()

    # Act
    flags = kwargs.get("creationflags", 0)

    # Assert
    assert not flags & 0x01000000, "breakaway set; the worker's children can escape the job"


@pytest.mark.skipif(sys.platform != "win32", reason="suspended spawn is a Windows primitive")
def test_Should_start_the_worker_suspended_When_spawn_kwargs_are_built():
    """Assignment must win the race against the worker's first CreateProcess."""
    # Arrange
    kwargs = tree_kill.spawn_kwargs()

    # Act
    flags = kwargs.get("creationflags", 0)

    # Assert
    assert flags & 0x00000004, "not suspended; a helper can spawn before the job exists"


def test_Should_report_success_When_the_tree_is_already_gone():
    """An already-dead tree is a killed tree as far as the caller's status is concerned."""
    # Arrange
    process = subprocess.Popen([sys.executable, "-c", "pass"], **tree_kill.spawn_kwargs())
    handle = tree_kill.JobHandle(process.pid)
    process.wait(timeout=30)
    handle.release()

    # Act
    killed = tree_kill.kill_tree(process.pid, grace_seconds=2.0)

    # Assert
    assert killed is True


# --------------------------------------------------------------------------- #
# The AD-18 invariant and the AD-4 gate
# --------------------------------------------------------------------------- #


def test_Should_import_no_freecad_When_the_supervisor_module_is_loaded():
    """The supervisor's flat RSS is what makes the G4 soak's leak number interpretable."""
    # Arrange
    import freecad_buddy.hosts.phase4.supervisor  # noqa: F401

    # Act
    loaded = {name.split(".")[0] for name in sys.modules}

    # Assert
    assert "FreeCAD" not in loaded


def test_Should_flag_a_declared_module_When_it_reaches_freecad_transitively(tmp_path):
    """The guard must follow first-party imports, or a one-hop indirection defeats it."""
    # Arrange
    import importlib

    check_imports = importlib.import_module("scripts.check_imports")
    pkg = tmp_path / "freecad_buddy"
    (pkg / "hosts" / "phase4").mkdir(parents=True)
    (pkg / "hosts" / "phase4" / "supervisor.py").write_text(
        "from freecad_buddy.hosts.phase4 import status_map\n", encoding="utf-8"
    )
    (pkg / "hosts" / "phase4" / "status_map.py").write_text("import FreeCAD\n", encoding="utf-8")

    # Act
    violations = check_imports._freecad_free_violations(pkg)

    # Assert
    flagged = {v.relpath for v in violations}
    assert "hosts/phase4/supervisor.py" in flagged, violations


def test_Should_declare_the_supervisor_freecad_free_When_the_checker_is_configured():
    """A guard that did not name the supervisor would defend nothing."""
    # Arrange
    import importlib

    check_imports = importlib.import_module("scripts.check_imports")

    # Act
    declared = check_imports.FREECAD_FREE_MODULES

    # Assert
    assert "hosts/phase4/supervisor.py" in declared
    assert "hosts/phase4/worker.py" not in declared, "the worker is SUPPOSED to import FreeCAD"


def test_Should_disable_debug_exec_When_the_supervisor_builds_its_capabilities():
    """AD-4: permanently off in the Phase 4 service, even with the operator flag set."""
    # Arrange
    environ = {"FREECAD_BUDDY_ALLOW_EXEC": "1"}

    # Act
    caps = build_capabilities(environ)

    # Assert
    assert caps.service_mode is True
    assert caps.allow_exec is True, "the flag itself is still read; service mode is what gates"
    assert exec_registered(caps) is False
