"""Startup capability record and the debug-exec gating rule.

Stdlib-only so in-FreeCAD hosts (the GUI addon bootstrap) can import it without pulling in the
external ``mcp`` package.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Capabilities:
    """Immutable startup capability record; ``allow_exec`` is read once from the env flag."""

    allow_exec: bool
    service_mode: bool = False

    @classmethod
    def from_env(cls, environ: dict[str, str], *, service_mode: bool = False) -> "Capabilities":
        """Read ``FREECAD_BUDDY_ALLOW_EXEC``; exactly ``"1"`` enables, anything else disables."""
        return cls(
            allow_exec=environ.get("FREECAD_BUDDY_ALLOW_EXEC") == "1",
            service_mode=service_mode,
        )


def exec_registered(caps: Capabilities) -> bool:
    """Whether ``debug_exec`` is reachable: the exec flag is set and not in service mode."""
    return caps.allow_exec and not caps.service_mode
