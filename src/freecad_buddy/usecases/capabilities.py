"""Startup capability record and the debug-exec gating rule.

Stdlib-only so in-FreeCAD hosts (the GUI addon bootstrap) can import it without pulling in the
external ``mcp`` package.
"""

from __future__ import annotations

from dataclasses import dataclass

AUTO_APPROVE_VARIABLE = "FREECAD_BUDDY_AUTO_APPROVE"
AUTO_APPROVE_WARNING = (
    "SECURITY: mutation auto-approve ENABLED "
    f"({AUTO_APPROVE_VARIABLE} unset or 1; set it to 0 to require preview_id)"
)


@dataclass(frozen=True)
class Capabilities:
    """Immutable startup capability record; each flag is read once from the environment."""

    allow_exec: bool
    service_mode: bool = False
    auto_approve: bool = False

    @classmethod
    def from_env(cls, environ: dict[str, str], *, service_mode: bool = False) -> "Capabilities":
        """Read the operator flags; exactly ``"1"`` enables one, any other value disables it.

        ``FREECAD_BUDDY_ALLOW_EXEC`` gates ``debug_exec`` and is off when unset.
        ``FREECAD_BUDDY_AUTO_APPROVE`` lifts the mutation confirm requirement and is on when
        unset: ``"0"``, ``"false"`` or ``""`` restores the confirm gate.
        """
        return cls(
            allow_exec=environ.get("FREECAD_BUDDY_ALLOW_EXEC") == "1",
            service_mode=service_mode,
            auto_approve=environ.get(AUTO_APPROVE_VARIABLE, "1") == "1",
        )


def exec_registered(caps: Capabilities) -> bool:
    """Whether ``debug_exec`` is reachable: the exec flag is set and not in service mode."""
    return caps.allow_exec and not caps.service_mode


def auto_approve_enabled(caps: Capabilities) -> bool:
    """Whether a geometry mutation may run without a confirm token."""
    return caps.auto_approve
