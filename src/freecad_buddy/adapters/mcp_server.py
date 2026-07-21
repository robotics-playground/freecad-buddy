"""MCP surface over the method registry.

Builds the low-level ``mcp.server.lowlevel.Server`` and exposes ``tools/list`` and
``tools/call`` over a ``MethodRegistry``. Each tool carries a hand-authored ``inputSchema``,
the shared result-envelope ``outputSchema``, and a description. ``debug_exec`` is surfaced
only when the startup capability record enables it. Mutating and exec calls are audit-logged
before and after execution; all logging goes to stderr.
"""

from __future__ import annotations

import json
import logging
import sys
from dataclasses import dataclass
from pathlib import Path

from mcp import types
from mcp.server.lowlevel import Server

from freecad_buddy.adapters.audit_log import AuditSink
from freecad_buddy.adapters.rpc_dispatch import MethodRegistry, RpcMethod

logger = logging.getLogger("freecad_buddy.mcp_server")

# Load the generated result-envelope schema rather than duplicating the status set inline.
_SCHEMA_PATH = Path(__file__).resolve().parents[1] / "contracts" / "jsonschema"
_ENVELOPE_SCHEMA_FILE = _SCHEMA_PATH / "result-envelope.schema.json"
try:
    _RESULT_ENVELOPE_SCHEMA: dict = json.loads(_ENVELOPE_SCHEMA_FILE.read_text(encoding="utf-8"))
except (OSError, ValueError) as exc:
    raise RuntimeError(
        f"result-envelope output schema is missing or malformed at {_ENVELOPE_SCHEMA_FILE}"
    ) from exc


@dataclass(frozen=True)
class Capabilities:
    """Immutable startup capability record; ``allow_exec`` is read once from the env flag."""

    allow_exec: bool
    service_mode: bool = False

    @classmethod
    def from_env(cls, environ: dict[str, str], *, service_mode: bool = False) -> Capabilities:
        """Read ``FREECAD_BUDDY_ALLOW_EXEC``; exactly ``"1"`` enables, anything else disables."""
        return cls(
            allow_exec=environ.get("FREECAD_BUDDY_ALLOW_EXEC") == "1",
            service_mode=service_mode,
        )


def configure_stderr_logging(level: int = logging.INFO) -> None:
    """Route all logging to stderr; stdout carries the stdio MCP protocol."""
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    root = logging.getLogger("freecad_buddy")
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level)


def _tool_for(method: RpcMethod) -> types.Tool:
    return types.Tool(
        name=method.name,
        description=method.description,
        inputSchema=method.input_schema or {"type": "object", "properties": {}},
        outputSchema=_RESULT_ENVELOPE_SCHEMA,
    )


def registered_tools(registry: MethodRegistry, caps: Capabilities) -> list[types.Tool]:
    """Tools surfaced by ``tools/list``; ``debug_exec`` is present only when enabled."""
    tools: list[types.Tool] = []
    for method in registry.methods():
        if method.name == "debug_exec" and not exec_registered(caps):
            continue
        tools.append(_tool_for(method))
    return tools


def exec_registered(caps: Capabilities) -> bool:
    """Whether ``debug_exec`` is reachable: the exec flag is set and not in service mode."""
    return caps.allow_exec and not caps.service_mode


def _to_call_result(envelope: dict) -> types.CallToolResult:
    """Wrap a result envelope as a ``CallToolResult``, flagging non-OK statuses as errors."""
    text = json.dumps(envelope, indent=2, ensure_ascii=False)
    return types.CallToolResult(
        content=[types.TextContent(type="text", text=text)],
        structuredContent=dict(envelope),
        isError=envelope.get("status") != "OK",
    )


def build_server(
    registry: MethodRegistry,
    caps: Capabilities,
    audit: AuditSink,
    *,
    name: str = "freecad-buddy",
) -> Server:
    """Wire the low-level MCP ``Server``: ``tools/list`` and ``tools/call`` over the registry."""
    if exec_registered(caps):
        logger.warning("SECURITY: debug_exec ENABLED by operator flag")

    server: Server = Server(name)

    @server.list_tools()
    async def _list_tools() -> list[types.Tool]:
        return registered_tools(registry, caps)

    @server.call_tool()
    async def _call_tool(tool_name: str, arguments: dict) -> types.CallToolResult:
        args = arguments if isinstance(arguments, dict) else {}
        doc = args.get("doc")

        if tool_name == "debug_exec" and not exec_registered(caps):
            # Unreachable via tools/list, but still fail closed and audit the denied attempt.
            _audit_safe(audit.before, "exec", tool_name, doc, args)
            envelope = _denied_exec_envelope()
            _audit_safe(audit.after, "exec", tool_name, doc, args, envelope.get("status"))
            return _to_call_result(envelope)

        method = registry.get(tool_name)
        audited = method is not None and (method.mutating or method.name == "debug_exec")
        event = method.audit_event if method is not None else "mutation"

        if audited:
            _audit_safe(audit.before, event, tool_name, doc, args)
        envelope = registry.dispatch(tool_name, args)
        if audited:
            _audit_safe(audit.after, event, tool_name, doc, args, envelope.get("status"))
        return _to_call_result(envelope)

    return server


def _audit_safe(fn, *args) -> None:
    """Run an audit write, logging (never raising) if the write fails.

    A failed audit write is reported to stderr but never converts a completed tool call
    into a raised exception.
    """
    try:
        fn(*args)
    except Exception:  # noqa: BLE001 - audit failure must not break the tool-call boundary
        logger.exception("audit write failed")


def _denied_exec_envelope() -> dict:
    from freecad_buddy.contracts import mirror_text

    structured: dict = {}
    return {
        "schema": "fcb.result-envelope/1",
        "status": "INVALID_INPUT",
        "detail": {
            "code": "INVALID_INPUT",
            "message": "debug_exec is disabled (set FREECAD_BUDDY_ALLOW_EXEC=1 to enable)",
            "data": {},
        },
        "structured_content": structured,
        "text": mirror_text(structured),
    }


async def serve_stdio(server: Server) -> None:
    """Serve the MCP ``Server`` over stdio; stdout carries protocol, logs go to stderr."""
    from mcp.server.stdio import stdio_server

    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options(),
        )


__all__ = [
    "Capabilities",
    "build_server",
    "configure_stderr_logging",
    "exec_registered",
    "registered_tools",
    "serve_stdio",
]
