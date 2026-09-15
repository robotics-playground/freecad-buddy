"""Phase 4 per-job sandbox (external / pytest).

Covers every I/O matrix row in spec-5-3. The containment rows run the REAL jail and assert
against a REAL baseline: each one first proves the probe leaks without the sandbox, then proves
it is denied with it. A containment test that only checked the sandboxed side would pass on a
host with no network at all, proving nothing.

On Windows the Linux backend is reached through WSL, which is also how it reaches CI
(`ubuntu-latest`). Tests needing it skip when no WSL distribution answers.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from freecad_buddy.hosts.phase4 import job_dir, sandbox, sandbox_windows  # noqa: E402
from freecad_buddy.hosts.phase4.pool import WorkerPool  # noqa: E402
from freecad_buddy.hosts.phase4.sandbox import SandboxReport  # noqa: E402
from freecad_buddy.hosts.phase4.status_map import Outcome  # noqa: E402
from freecad_buddy.hosts.phase4.supervisor import Supervisor  # noqa: E402

# The probe a containment test runs inside and outside the jail. Reports three facts as JSON so
# one run yields the whole picture and a partial failure is legible.
_PROBE = textwrap.dedent(
    """
    import json, socket
    result = {}
    try:
        socket.create_connection(("1.1.1.1", 53), timeout=2)
        result["egress"] = "reachable"
    except Exception:
        result["egress"] = "denied"
    try:
        open("/tmp/fcb_outside_probe.txt", "w").write("x")
        result["outside"] = "writable"
    except Exception:
        result["outside"] = "refused"
    try:
        open("__JOB__/exports/probe.txt", "w").write("x")
        result["jobdir"] = "writable"
    except Exception as exc:
        result["jobdir"] = "refused:" + type(exc).__name__
    print(json.dumps(result))
    """
).strip()


def _wsl_available() -> bool:
    """Whether a WSL distribution can run a command."""
    if shutil.which("wsl.exe") is None and sys.platform == "win32":
        return False
    if sys.platform != "win32":
        return True
    probe = subprocess.run(
        ["wsl.exe", "-e", "bash", "-lc", "true"], capture_output=True, timeout=60
    )
    return probe.returncode == 0


# The repo as the Linux side sees it. WSL maps Windows drives under /mnt/<drive>.
_LINUX_REPO = "/mnt/" + str(REPO_ROOT).replace("\\", "/").replace(":", "", 1).lower()

_NEEDS_LINUX_JAIL = pytest.mark.skipif(
    not _wsl_available(), reason="no Linux host or WSL distribution for the namespace backend"
)


def _run_in_linux(script: str, timeout: int = 120) -> str:
    """Run ``script`` under bash on the Linux side and return its stdout."""
    if sys.platform == "win32":
        command = ["wsl.exe", "-e", "bash", "-lc", script]
    else:
        command = ["bash", "-lc", script]
    completed = subprocess.run(command, capture_output=True, text=True, timeout=timeout)
    return completed.stdout


def _probe_script(sandboxed: bool) -> str:
    """Build a bash script that runs the probe, with or without the jail around it."""
    setup = (
        "rm -rf /tmp/fcbsbx && mkdir -p /tmp/fcbsbx/exports && "
        "rm -f /tmp/fcb_outside_probe.txt && "
        f"cat > /tmp/fcb_probe.py <<'EOF'\n{_PROBE.replace('__JOB__', '/tmp/fcbsbx')}\nEOF\n"
    )
    repo = _LINUX_REPO if sys.platform == "win32" else str(REPO_ROOT)
    if not sandboxed:
        return setup + "python3 /tmp/fcb_probe.py"
    return setup + (
        f"cd {repo} && PYTHONPATH=src python3 -c \""
        "from pathlib import Path;"
        "from freecad_buddy.hosts.phase4 import sandbox_linux;"
        "import subprocess;"
        "cmd,rep = sandbox_linux.wrap(['python3','/tmp/fcb_probe.py'], Path('/tmp/fcbsbx'), {});"
        "print(subprocess.run(cmd,capture_output=True,text=True,timeout=60).stdout.strip())"
        "\""
    )


# --------------------------------------------------------------------------- #
# SandboxReport — the mechanism that keeps the jail honest
# --------------------------------------------------------------------------- #


def test_Should_report_contained_When_every_requested_control_took_effect():
    """``contained`` is the one-line answer a caller acts on."""
    # Arrange
    report = SandboxReport(backend="test")

    # Act
    report.apply(sandbox.EGRESS_DENIED)

    # Assert
    assert report.contained is True


def test_Should_report_uncontained_When_a_control_could_not_be_applied():
    """A jail that degraded silently would let an uncontained run read as contained."""
    # Arrange
    report = SandboxReport(backend="test")

    # Act
    report.miss(sandbox.EGRESS_DENIED, "no network namespace")

    # Assert
    assert report.contained is False
    assert "no network namespace" in report.unavailable[sandbox.EGRESS_DENIED]


def test_Should_stay_contained_When_a_control_applied_through_a_weaker_mechanism():
    """A weakened control is still a control; calling it unavailable would claim it was absent."""
    # Arrange
    report = SandboxReport(backend="test")

    # Act
    report.weaken(sandbox.MEMORY_CAPPED, "RLIMIT_AS instead of cgroup")

    # Assert
    assert report.contained is True
    assert sandbox.MEMORY_CAPPED in report.applied
    assert sandbox.MEMORY_CAPPED in report.weakened


def test_Should_clear_the_miss_When_a_control_is_later_applied():
    """A report that kept a stale miss would understate the containment it achieved."""
    # Arrange
    report = SandboxReport(backend="test")
    report.miss(sandbox.MEMORY_CAPPED, "not yet")

    # Act
    report.apply(sandbox.MEMORY_CAPPED)

    # Assert
    assert report.contained is True
    assert sandbox.MEMORY_CAPPED not in report.unavailable


def test_Should_serialize_every_field_When_the_report_is_rendered():
    """The report rides on a JobStatus, so it must survive JSON."""
    # Arrange
    report = SandboxReport(backend="test")
    report.apply(sandbox.EGRESS_DENIED)
    report.miss(sandbox.MEMORY_CAPPED, "unavailable here")
    report.weaken(sandbox.CPU_CAPPED, "rlimit only")

    # Act
    rendered = json.loads(json.dumps(report.as_dict()))

    # Assert
    assert rendered["backend"] == "test"
    assert rendered["applied"] == sorted([sandbox.EGRESS_DENIED, sandbox.CPU_CAPPED])
    assert rendered["contained"] is False


# --------------------------------------------------------------------------- #
# Real containment — baseline first, then the jail
# --------------------------------------------------------------------------- #


@_NEEDS_LINUX_JAIL
def test_Should_reach_the_network_and_write_anywhere_When_no_sandbox_is_applied():
    """The baseline. Without it, every containment assertion below could pass vacuously."""
    # Arrange
    script = _probe_script(sandboxed=False)

    # Act
    result = json.loads(_run_in_linux(script).strip().splitlines()[-1])

    # Assert
    assert result["egress"] == "reachable", "no baseline network; containment proves nothing"
    assert result["outside"] == "writable"


@_NEEDS_LINUX_JAIL
def test_Should_deny_egress_When_the_job_runs_inside_the_sandbox():
    """The worker needs no network, so an empty netns removes the exfiltration class outright."""
    # Arrange
    script = _probe_script(sandboxed=True)

    # Act
    result = json.loads(_run_in_linux(script).strip().splitlines()[-1])

    # Assert
    assert result["egress"] == "denied"


@_NEEDS_LINUX_JAIL
def test_Should_refuse_a_write_outside_the_job_directory_When_sandboxed():
    """Everything outside the one writable mount is read-only."""
    # Arrange
    script = _probe_script(sandboxed=True)

    # Act
    result = json.loads(_run_in_linux(script).strip().splitlines()[-1])

    # Assert
    assert result["outside"] == "refused"


@_NEEDS_LINUX_JAIL
def test_Should_allow_a_write_inside_the_job_directory_When_sandboxed():
    """A jail that contained the job's own output would contain it out of doing its work.

    This is the row the mount ORDER decides: binding the job directory before the read-only
    remount is what leaves a mount entry to reopen. Reversing them yields ``refused`` here.
    """
    # Arrange
    script = _probe_script(sandboxed=True)

    # Act
    result = json.loads(_run_in_linux(script).strip().splitlines()[-1])

    # Assert
    assert result["jobdir"] == "writable", result


# --------------------------------------------------------------------------- #
# Backend reports
# --------------------------------------------------------------------------- #


@pytest.mark.skipif(sys.platform != "win32", reason="Windows backend")
def test_Should_name_the_isolation_gap_When_the_windows_backend_reports():
    """Claiming egress denial a Job Object cannot deliver is the silent gap to prevent."""
    # Arrange
    limits = {"memory_bytes": 256 * 1024 * 1024}

    # Act
    _, report = sandbox_windows.wrap(["python"], Path("."), limits)

    # Assert
    assert sandbox.EGRESS_DENIED in report.unavailable
    assert "WSL2" in report.unavailable[sandbox.EGRESS_DENIED]
    assert report.contained is False


@pytest.mark.skipif(sys.platform != "win32", reason="Windows backend")
def test_Should_cap_memory_and_cpu_When_the_windows_backend_is_given_limits():
    """The Job Object's resource limits are real containment even without isolation."""
    # Arrange
    limits = {"memory_bytes": 256 * 1024 * 1024, "cpu_time_s": 30}

    # Act
    _, report = sandbox_windows.wrap(["python"], Path("."), limits)

    # Assert
    assert sandbox.MEMORY_CAPPED in report.applied
    assert sandbox.CPU_CAPPED in report.applied


def test_Should_report_gpu_none_When_any_backend_runs():
    """Rendering goes through the offscreen software path on both backends."""
    # Arrange
    limits: dict = {}

    # Act
    _, report = sandbox.wrap(["python"], Path("."), limits)

    # Assert
    assert sandbox.GPU_NONE in report.applied


def test_Should_mark_every_control_unavailable_When_no_job_directory_is_supplied():
    """No writable mount means nothing to contain access TO; it is recorded, never skipped."""
    # Arrange
    pool = WorkerPool(default_deadline_s=30.0)
    spec = {
        "schema": "fcb.job-spec/1",
        "job_id": "j-nosandbox",
        "kind": "echo",
        "payload": {},
        "payload_module": "freecad_buddy.hosts.phase4.lifecycle_payloads",
        "limits": None,
    }

    # Act
    run = pool.run(spec)

    # Assert
    assert run.sandbox["backend"] == "none"
    assert run.sandbox["contained"] is False


# --------------------------------------------------------------------------- #
# The job directory — the one writable mount
# --------------------------------------------------------------------------- #


def test_Should_create_the_documented_layout_When_a_job_directory_is_made(tmp_path):
    """The worker writes into a read-only filesystem with one hole; the hole must be shaped."""
    # Arrange
    spec = {"job_id": "j1", "kind": "echo"}

    # Act
    job = job_dir.create(tmp_path, "j1", spec)

    # Assert
    assert job.exports.is_dir() and job.renders.is_dir()
    assert json.loads(job.spec.read_text(encoding="utf-8"))["job_id"] == "j1"


@pytest.mark.parametrize("job_id", ["../escape", "a/b", "..", ".", ""])
def test_Should_refuse_a_job_id_that_escapes_the_jobs_root_When_creating(tmp_path, job_id):
    """A traversing id would place the one writable mount outside the jobs tree entirely."""
    # Arrange
    root = tmp_path

    # Act
    def act():
        return job_dir.create(root, job_id)

    # Assert
    with pytest.raises(ValueError):
        act()


def test_Should_remove_everything_When_a_job_directory_is_cleaned(tmp_path):
    """Retention is the supervisor's call; a worker must not be able to hide its own evidence."""
    # Arrange
    job = job_dir.create(tmp_path, "j2", {"job_id": "j2"})
    (job.exports / "part.step").write_text("x", encoding="utf-8")

    # Act
    job_dir.clean(job)

    # Assert
    assert not job.root.exists()


# --------------------------------------------------------------------------- #
# OOM_KILLED becomes reachable
# --------------------------------------------------------------------------- #


def test_Should_resolve_OOM_KILLED_When_the_worker_hit_its_memory_ceiling():
    """``status_map`` has always mapped this flag; until the sandbox, nothing ever set it."""
    # Arrange
    supervisor = Supervisor()
    from freecad_buddy.hosts.phase4.pool import JobRun

    run = JobRun(
        spec={"job_id": "j-oom"},
        outcome=Outcome(exit_code=1, message=""),
        stderr="Traceback (most recent call last):\nMemoryError\n",
    )

    # Act
    status = supervisor.resolve(run)

    # Assert
    assert status["state"] == "OOM_KILLED"
    assert status["detail"]["code"] == "job.oom_killed"


def test_Should_keep_TIMEOUT_When_a_killed_job_also_shows_memory_pressure():
    """The deadline still outranks: the kill is ours, and blaming memory would misattribute it."""
    # Arrange
    supervisor = Supervisor()
    from freecad_buddy.hosts.phase4.pool import JobRun

    run = JobRun(
        spec={"job_id": "j-both"},
        outcome=Outcome(deadline_exceeded=True),
        stderr="MemoryError",
    )

    # Act
    status = supervisor.resolve(run)

    # Assert
    assert status["state"] == "TIMEOUT"


def test_Should_not_claim_memory_pressure_When_the_stderr_says_nothing_about_it():
    """A crash is a crash; reading OOM into every failure would overstate what was observed."""
    # Arrange
    supervisor = Supervisor()
    from freecad_buddy.hosts.phase4.pool import JobRun

    run = JobRun(
        spec={"job_id": "j-crash"},
        outcome=Outcome(exit_code=1),
        stderr="ValueError: bad input",
    )

    # Act
    status = supervisor.resolve(run)

    # Assert
    assert status["state"] == "WORKER_CRASHED"


def test_Should_attach_the_sandbox_report_When_a_job_resolves(tmp_path):
    """A caller judging a result needs to know what contained the job that produced it."""
    # Arrange
    supervisor = Supervisor()
    from freecad_buddy.hosts.phase4.pool import JobRun

    run = JobRun(
        spec={"job_id": "j-report"},
        outcome=Outcome(returned=True, exit_code=0),
        envelope={"schema": "fcb.result-envelope/1", "status": "OK"},
        sandbox={"backend": "test", "applied": ["egress_denied"], "contained": True},
    )

    # Act
    status = supervisor.resolve(run)

    # Assert
    assert status["artifacts"]["sandbox"]["backend"] == "test"


def test_Should_attach_the_sandbox_report_When_a_job_fails():
    """A report present only on success would be missing when containment mattered most."""
    # Arrange
    supervisor = Supervisor()
    from freecad_buddy.hosts.phase4.pool import JobRun

    run = JobRun(
        spec={"job_id": "j-failreport"},
        outcome=Outcome(exit_code=2),
        sandbox={"backend": "test", "contained": False},
    )

    # Act
    status = supervisor.resolve(run)

    # Assert
    assert status["state"] == "WORKER_CRASHED"
    assert status["artifacts"]["sandbox"]["contained"] is False
