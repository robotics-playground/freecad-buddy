"""Operator settings: the preference page values and the precedence rule that merges them.

An environment variable that is already set wins; otherwise the preference applies; otherwise the
default. The GUI host turns the preferences into ``FREECAD_BUDDY_*`` variables once, at bridge
start, so every reader — including the MCP proxy child, which inherits the environment — sees one
effective value. Stdlib-only so pytest can import it without FreeCAD.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

from freecad_buddy.usecases.capabilities import AUTO_APPROVE_VARIABLE

ALLOW_EXEC_VARIABLE = "FREECAD_BUDDY_ALLOW_EXEC"
NO_AUTO_MCP_VARIABLE = "FREECAD_BUDDY_NO_AUTO_MCP"
MCP_CMD_VARIABLE = "FREECAD_BUDDY_MCP_CMD"
AUDIT_LOG_VARIABLE = "FREECAD_BUDDY_AUDIT_LOG"
WORKDIR_VARIABLE = "FREECAD_BUDDY_WORKDIR"

OPERATOR_VARIABLES = (
    AUTO_APPROVE_VARIABLE,
    ALLOW_EXEC_VARIABLE,
    NO_AUTO_MCP_VARIABLE,
    MCP_CMD_VARIABLE,
    AUDIT_LOG_VARIABLE,
    WORKDIR_VARIABLE,
)


@dataclass(frozen=True)
class PreferenceValues:
    """The operator settings stored on the FreeCAD Buddy preference page."""

    auto_approve: bool = True
    allow_exec: bool = False
    auto_start_mcp: bool = True
    mcp_command: str = ""
    uv_path: str = ""
    audit_log_path: str = ""


def _flag(enabled: bool) -> str:
    return "1" if enabled else "0"


def variable_is_set(environ: Mapping[str, str], name: str) -> bool:
    """Whether ``environ`` sets the operator variable ``name``, so it wins over the preference.

    The two flags count as set when present, even empty, because ``Capabilities.from_env`` reads
    an empty flag as off. A path or command counts only when non-empty: the host treats an empty
    one as absent, and an empty ``FREECAD_BUDDY_AUDIT_LOG`` would name no file.
    """
    if name in (AUTO_APPROVE_VARIABLE, ALLOW_EXEC_VARIABLE):
        return name in environ
    return bool(environ.get(name))


def environment_overrides(environ: Mapping[str, str]) -> dict[str, str]:
    """The operator variables ``environ`` sets, which win over the matching preferences."""
    return {name: environ[name] for name in OPERATOR_VARIABLES if variable_is_set(environ, name)}


def resolve_env_overlay(
    environ: Mapping[str, str], prefs: PreferenceValues, default_dir: Path
) -> dict[str, str]:
    """The ``FREECAD_BUDDY_*`` variables to add to ``environ``: only the ones it does not set.

    ``default_dir`` is the per-user data folder that replaces the cwd-relative defaults of the
    audit log and the workdir, which fail when FreeCAD starts from its install directory.
    """
    wanted = {
        AUTO_APPROVE_VARIABLE: _flag(prefs.auto_approve),
        ALLOW_EXEC_VARIABLE: _flag(prefs.allow_exec),
        AUDIT_LOG_VARIABLE: prefs.audit_log_path or str(default_dir / "audit.jsonl"),
        WORKDIR_VARIABLE: str(default_dir / "workdir"),
    }
    # The host treats any non-empty value as "do not start", so the key is written only to opt out.
    if not prefs.auto_start_mcp:
        wanted[NO_AUTO_MCP_VARIABLE] = "1"
    if prefs.mcp_command:
        wanted[MCP_CMD_VARIABLE] = prefs.mcp_command
    overrides = environment_overrides(environ)
    return {key: value for key, value in wanted.items() if key not in overrides}
