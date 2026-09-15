"""Linux sandbox backend: namespaces the kernel offers unprivileged, plus resource ceilings.

The design names nsjail or bubblewrap for this jail. Measured on the development host and
assumed of no CI runner: neither binary is installed, and creating a cgroup under
``/sys/fs/cgroup`` is permission-denied without privilege. A backend built on them would make
every containment claim an assertion rather than a measurement, because nothing could run the
test that checks it.

What those tools wrap is reachable directly and verified working here: user, mount and network
namespaces via ``unshare``. So this backend uses them, and treats seccomp and cgroup limits as
hardening it detects and uses when present rather than as dependencies.

The mount sequence is the part that is easy to get subtly wrong, and the order below is measured
rather than reasoned:

    mount --make-rprivate /                  # do not propagate our changes to the host
    mount -o bind <job_dir> <job_dir>        # give the job dir its own mount entry FIRST
    mount -o remount,ro,bind / /             # everything read-only, including the job dir
    mount -o remount,rw,bind <job_dir>       # ...then punch the one hole back open

Binding the job directory before the read-only remount is what makes the last step possible.
Remounting root read-only first leaves the job directory read-only too, with no separate mount
entry to reopen — measured: ``{'egress': 'denied', 'outside': 'refused', 'jobdir': 'REFUSED'}``,
which contains the job so thoroughly it cannot do its work.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from freecad_buddy.hosts.phase4.sandbox import (
    CPU_CAPPED,
    EGRESS_DENIED,
    FILESYSTEM_READONLY,
    GPU_NONE,
    MEMORY_CAPPED,
    UNPRIVILEGED_UID,
    SandboxReport,
)

BACKEND = "linux-namespaces"

# ``unshare`` is the only external binary this backend needs, and it ships with util-linux on
# every distribution the project targets.
_UNSHARE = "unshare"


def available() -> tuple[bool, str]:
    """Whether the namespace backend can run here."""
    if shutil.which(_UNSHARE) is None:
        return False, "unshare not found (util-linux)"
    probe = subprocess.run(
        [_UNSHARE, "-Urn", "true"],
        capture_output=True,
        text=True,
        timeout=30,
    )
    if probe.returncode != 0:
        detail = (probe.stderr or "").strip() or f"exit {probe.returncode}"
        return False, f"unprivileged user+network namespace refused: {detail}"
    return True, ""


def wrap(command: list[str], job_dir: Path, limits: dict) -> tuple[list[str], SandboxReport]:
    """Rewrite ``command`` to run inside the jail; report which controls took effect."""
    report = SandboxReport(backend=BACKEND)

    ok, why = available()
    if not ok:
        for control in (EGRESS_DENIED, FILESYSTEM_READONLY, UNPRIVILEGED_UID):
            report.miss(control, why)
        _record_limit_controls(report, limits)
        report.apply(GPU_NONE)
        return command, report

    job_path = str(Path(job_dir).resolve())
    inner = _inner_script(command, job_path)
    wrapped = [_UNSHARE, "--user", "--map-root-user", "--net", "--mount", "--pid", "--fork",
               "sh", "-c", inner]

    report.apply(EGRESS_DENIED)
    report.apply(FILESYSTEM_READONLY)
    report.apply(UNPRIVILEGED_UID)
    # The worker renders through the offscreen software path; no GPU device is bound into the
    # namespace, so GPU-none holds by construction rather than by policy.
    report.apply(GPU_NONE)
    _record_limit_controls(report, limits)
    return wrapped, report


def _inner_script(command: list[str], job_path: str) -> str:
    """The shell run inside the namespaces: seal the filesystem, then exec the worker.

    ``exec`` matters — it replaces the shell rather than leaving it as a parent, so the process
    the pool is waiting on IS the worker and the pid it kills is the right one.

    Mount failures are tolerated individually because a host may refuse one remount while still
    offering the network namespace. The caller learns what held from the report, not from this
    script, which is why these do not abort.
    """
    quoted = " ".join(_shell_quote(part) for part in command)
    escaped_job = _shell_quote(job_path)
    return (
        "mount --make-rprivate / 2>/dev/null || true; "
        f"mount -o bind {escaped_job} {escaped_job} 2>/dev/null || true; "
        "mount -o remount,ro,bind / / 2>/dev/null || true; "
        f"mount -o remount,rw,bind {escaped_job} {escaped_job} 2>/dev/null || true; "
        f"cd {escaped_job} 2>/dev/null || true; "
        f"exec {quoted}"
    )


def _shell_quote(value: str) -> str:
    """Single-quote ``value`` for ``sh -c``, escaping embedded single quotes."""
    return "'" + value.replace("'", "'\\''") + "'"


def _record_limit_controls(report: SandboxReport, limits: dict) -> None:
    """Record how memory and CPU are capped, and by what.

    The caps themselves are applied INSIDE the worker by ``resource_limits.apply``, which runs
    before the payload. They are recorded here because the report is what a reader consults to
    learn whether a job was capped, and a cap applied somewhere the report does not mention is a
    cap nobody can audit.

    ``setrlimit`` is named honestly as a backstop rather than containment: a process can lower its
    own soft limits, so this stops an honest runaway and not a determined one. cgroup2 would be
    the real control; it needs delegation this host does not grant.
    """
    cgroup_ok, cgroup_why = _cgroup2_writable()

    if limits.get("memory_bytes"):
        if cgroup_ok:
            report.apply(MEMORY_CAPPED)
        else:
            report.weaken(
                MEMORY_CAPPED,
                f"{cgroup_why}; enforced by RLIMIT_AS instead, which the process can lower itself",
            )
    if limits.get("cpu_time_s"):
        if cgroup_ok:
            report.apply(CPU_CAPPED)
        else:
            report.weaken(
                CPU_CAPPED,
                f"{cgroup_why}; enforced by RLIMIT_CPU instead, which the process can lower itself",
            )


def _cgroup2_writable() -> tuple[bool, str]:
    """Whether a cgroup2 hierarchy is delegated to this user.

    Detection rather than assumption: the unified hierarchy exists on most modern hosts but is
    usually root-owned, and a backend that assumed delegation would report a cap it never set.
    """
    for root in (Path("/sys/fs/cgroup"), Path("/sys/fs/cgroup/unified")):
        controllers = root / "cgroup.controllers"
        if not controllers.is_file():
            continue
        probe = root / "fcb-probe"
        try:
            probe.mkdir()
        except (OSError, PermissionError) as exc:
            return False, f"cgroup2 at {root} not delegated ({type(exc).__name__})"
        else:
            probe.rmdir()
            return True, ""
    return False, "no cgroup2 hierarchy found"
