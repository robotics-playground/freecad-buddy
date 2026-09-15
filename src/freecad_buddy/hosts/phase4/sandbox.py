"""The per-job sandbox: one API over two backends, and an honest account of what it applied.

A Phase 4 job spec is fully untrusted input with no human in the loop, so the worker runs inside
an OS jail rather than merely inside a process the supervisor can kill. Story 5.2 made a job
killable; this makes it contained.

The API is deliberately one function plus one report. ``wrap`` turns a command into a sandboxed
command, and ``SandboxReport`` says which controls actually took effect on this host. The report
is not diagnostics — it is the mechanism that keeps the sandbox honest. A jail that silently
degraded to nothing on a host missing one control would let an uncontained run be reported as
contained, which is a worse failure than refusing to run at all.

FreeCAD-free: containment is decided before any geometry exists.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path

# The controls a backend may apply. Each names a threat from the Phase 4 threat list rather than
# a mechanism, so a backend that achieves one differently still reports the same name.
EGRESS_DENIED = "egress_denied"
FILESYSTEM_READONLY = "filesystem_readonly"
UNPRIVILEGED_UID = "unprivileged_uid"
MEMORY_CAPPED = "memory_capped"
CPU_CAPPED = "cpu_capped"
GPU_NONE = "gpu_none"

ALL_CONTROLS = (
    EGRESS_DENIED,
    FILESYSTEM_READONLY,
    UNPRIVILEGED_UID,
    MEMORY_CAPPED,
    CPU_CAPPED,
    GPU_NONE,
)


@dataclass
class SandboxReport:
    """Which controls a backend applied, which it could not, and how strong the applied ones are.

    Three states, deliberately, because two would lose a distinction that matters:

    - ``applied`` — the control took effect.
    - ``unavailable`` — the control did NOT take effect, with a reason. A job carrying one of
      these ran without that protection, which is the whole point of reporting rather than
      silently skipping.
    - ``weakened`` — the control took effect, but through a weaker mechanism than the host could
      in principle offer. A memory cap enforced by ``setrlimit`` rather than a cgroup is real but
      self-lowerable; calling that "unavailable" would claim the job was uncapped, and calling it
      plain "applied" would hide that it stops an honest runaway and not a determined one.

    ``contained`` reflects only ``unavailable``: a weakened control is still a control.
    """

    backend: str = "none"
    applied: set = field(default_factory=set)
    unavailable: dict = field(default_factory=dict)
    weakened: dict = field(default_factory=dict)

    @property
    def contained(self) -> bool:
        """Whether every control this host was asked for took effect, weakened or not."""
        return not self.unavailable

    def apply(self, control: str) -> None:
        """Record that ``control`` took effect."""
        self.applied.add(control)
        self.unavailable.pop(control, None)

    def miss(self, control: str, reason: str) -> None:
        """Record that ``control`` did NOT take effect, and why."""
        self.unavailable[control] = reason
        self.applied.discard(control)

    def weaken(self, control: str, reason: str) -> None:
        """Record that ``control`` took effect through a weaker mechanism than ideal."""
        self.applied.add(control)
        self.unavailable.pop(control, None)
        self.weakened[control] = reason

    def as_dict(self) -> dict:
        """A JSON-safe view for the job status."""
        return {
            "backend": self.backend,
            "applied": sorted(self.applied),
            "unavailable": dict(sorted(self.unavailable.items())),
            "weakened": dict(sorted(self.weakened.items())),
            "contained": self.contained,
        }


def wrap(
    command: list[str], job_dir: Path, limits: dict | None = None
) -> tuple[list[str], SandboxReport]:
    """Return ``command`` rewritten to run sandboxed, plus the report of what was applied.

    The command is rewritten rather than executed here so the caller keeps ownership of the
    process — story 5.2's pool needs the pid to kill the tree, and a sandbox that spawned its own
    process would hide it.

    :param command: the worker command to contain.
    :param job_dir: the ONLY path the job may write to.
    :param limits: a ``JobLimits`` mapping.
    """
    limits = limits or {}
    if sys.platform == "win32":
        from freecad_buddy.hosts.phase4 import sandbox_windows

        return sandbox_windows.wrap(command, job_dir, limits)

    from freecad_buddy.hosts.phase4 import sandbox_linux

    return sandbox_linux.wrap(command, job_dir, limits)


def available() -> tuple[bool, str]:
    """Whether a sandbox backend can be applied here, and what is missing when it cannot."""
    if sys.platform == "win32":
        from freecad_buddy.hosts.phase4 import sandbox_windows

        return sandbox_windows.available()

    from freecad_buddy.hosts.phase4 import sandbox_linux

    return sandbox_linux.available()
