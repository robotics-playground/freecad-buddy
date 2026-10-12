"""Startup capability record and the script-exec gating rule.

Stdlib-only so in-FreeCAD hosts (the GUI addon bootstrap) can import it without pulling in the
external ``mcp`` package.
"""

from __future__ import annotations

from dataclasses import dataclass

AUTO_APPROVE_VARIABLE = "FREECAD_BUDDY_AUTO_APPROVE"
AUTO_APPROVE_WARNING = (
    "SECURITY: mutation auto-approve ENABLED (to require preview_id, clear Auto-approve mutations "
    "in the FreeCAD GUI: Edit > Preferences > FreeCAD Buddy, "
    f"or set {AUTO_APPROVE_VARIABLE}=0)"
)
SCRIPT_EXEC_VARIABLE = "FREECAD_BUDDY_SCRIPT_EXEC"
UNATTENDED_VARIABLE = "FREECAD_BUDDY_UNATTENDED"
SCRIPT_EXEC_UNATTENDED_VARIABLE = "FREECAD_BUDDY_SCRIPT_EXEC_UNATTENDED"
SCRIPT_EXEC_WARNING = (
    "SECURITY: script_exec ENABLED: any MCP client of this bridge can run Python with your user "
    "rights (to turn it off, clear Allow script_exec in Edit > Preferences > FreeCAD Buddy, "
    f"or set {SCRIPT_EXEC_VARIABLE}=0)"
)


@dataclass(frozen=True)
class Capabilities:
    """Immutable startup capability record; each flag is read once from the environment."""

    script_exec: bool
    service_mode: bool = False
    auto_approve: bool = False
    unattended: bool = False
    script_exec_unattended: bool = False

    @classmethod
    def from_env(cls, environ: dict[str, str], *, service_mode: bool = False) -> "Capabilities":
        """Read the operator flags; exactly ``"1"`` enables one, any other value disables it.

        ``FREECAD_BUDDY_SCRIPT_EXEC`` and ``FREECAD_BUDDY_AUTO_APPROVE`` are on when unset:
        ``"0"``, ``"false"`` or ``""`` turns them off. ``FREECAD_BUDDY_UNATTENDED`` and
        ``FREECAD_BUDDY_SCRIPT_EXEC_UNATTENDED`` are off when unset.
        """
        return cls(
            script_exec=environ.get(SCRIPT_EXEC_VARIABLE, "1") == "1",
            service_mode=service_mode,
            auto_approve=environ.get(AUTO_APPROVE_VARIABLE, "1") == "1",
            unattended=environ.get(UNATTENDED_VARIABLE) == "1",
            script_exec_unattended=environ.get(SCRIPT_EXEC_UNATTENDED_VARIABLE) == "1",
        )


def exec_registered(caps: Capabilities) -> bool:
    """Whether ``script_exec`` is reachable.

    The switch is on, an unattended run has the operator's opt-in, and not in service mode.
    """
    unattended_ok = not caps.unattended or caps.script_exec_unattended
    return caps.script_exec and unattended_ok and not caps.service_mode


def auto_approve_enabled(caps: Capabilities) -> bool:
    """Whether a geometry mutation may run without a confirm token."""
    return caps.auto_approve
