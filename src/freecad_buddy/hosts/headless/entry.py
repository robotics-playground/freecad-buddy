"""Headless host entry.

A single process where the MCP server, the use cases, and ``import FreeCAD`` all live
together. FreeCAD calls run inline through ``Marshal(InlineExecutor())``. Transport is stdio
and logging is stderr-only.

If this interpreter cannot ``import FreeCAD`` the host is unavailable and exits with a clear
message rather than degrading.
"""

from __future__ import annotations

import asyncio
import logging
import os
import sys
from pathlib import Path

from freecad_buddy.adapters.audit_log import AuditSink, default_audit_path
from freecad_buddy.adapters.marshal import InlineExecutor, Marshal
from freecad_buddy.adapters.mcp_server import (
    Capabilities,
    build_server,
    configure_stderr_logging,
    serve_stdio,
)
from freecad_buddy.adapters.render_probe import OffscreenRenderPort
from freecad_buddy.adapters.rpc_dispatch import MethodRegistry
from freecad_buddy.hosts.tool_catalog import build_inline_handlers
from freecad_buddy.usecases import shim
from freecad_buddy.usecases.documents import DocumentRegistry, sweep_temp_dir
from freecad_buddy.usecases.exports import ExportRegistry

logger = logging.getLogger("freecad_buddy.hosts.headless")


class FreeCADUnavailable(RuntimeError):
    """Raised when the interpreter cannot ``import FreeCAD``."""


def verify_freecad_importable() -> None:
    """Confirm the host is viable; raise ``FreeCADUnavailable`` when FreeCAD cannot be imported."""
    try:
        import FreeCAD  # noqa: F401
    except ImportError as exc:
        raise FreeCADUnavailable(
            "headless host requires `import FreeCAD` in this interpreter; it failed"
        ) from exc


def build_registry(
    registry: DocumentRegistry, caps: Capabilities, marshal: Marshal
) -> MethodRegistry:
    """Register the tool surface, each handler marshaled onto the FreeCAD thread.

    ``viewport_port=None`` is stated, not defaulted by omission: this host has no live 3D view, so
    the framing capability is unavailable here even though the offscreen render probe may report
    itself available (AD-29 — the two predicates are independent).
    """
    return build_inline_handlers(
        registry,
        ExportRegistry(),
        caps,
        marshal,
        OffscreenRenderPort(),
        viewport_port=None,
    )


def _default_audit_path() -> Path:
    return default_audit_path()


def run(argv: list[str] | None = None) -> int:  # noqa: ARG001 - reserved for future flags
    """Verify FreeCAD, build the H1 stack, and serve the MCP surface over stdio."""
    configure_stderr_logging()
    try:
        verify_freecad_importable()
    except FreeCADUnavailable as exc:
        sys.stderr.write(f"{exc}\n")
        return 2

    # Session start is the only safe moment to clear temp artifacts: a render link the previous
    # session returned may still have been being read when that call completed (AD-25).
    logger.info("session-start sweep removed %s leftover temp artifact(s)", sweep_temp_dir())
    caps = Capabilities.from_env(dict(os.environ))
    doc_registry = DocumentRegistry()
    marshal = Marshal(InlineExecutor())
    methods = build_registry(doc_registry, caps, marshal)
    try:
        marshal.call(shim.warm_capability_probes, 30.0)
    except Exception:  # noqa: BLE001 - warm-up is best-effort; degrade to lazy probing
        logger.warning("capability-probe warm-up failed; probing lazily", exc_info=True)
    audit_path = _default_audit_path().resolve()
    logger.info("audit log: %s", audit_path)
    audit = AuditSink(audit_path)
    server = build_server(methods, caps, audit)

    logger.info("freecad-buddy headless MCP server starting (stdio)")
    try:
        asyncio.run(serve_stdio(server))
    except KeyboardInterrupt:
        logger.info("headless MCP server interrupted; shutting down")
        return 0
    except Exception:
        logger.exception("headless MCP server terminated with an error")
        return 1
    return 0
