"""MCP surface over the method registry.

Builds the low-level ``mcp.server.lowlevel.Server`` and exposes ``tools/list`` and
``tools/call`` over a ``MethodRegistry``. Each tool carries a hand-authored ``inputSchema``,
the shared result-envelope ``outputSchema``, and a description. ``debug_exec`` is surfaced
only when the startup capability record enables it. Mutating and exec calls are audit-logged
before and after execution; all logging goes to stderr.

A marshaled call that overruns its budget returns ``TIMEOUT`` while its body may still be
running, so ``tools/call`` also keeps a per-server document-suspect set: after such a timeout on
a mutating call the document is refused further mutations until a read on it returns ``OK``.
"""

from __future__ import annotations

import json
import logging
import sys
from pathlib import Path

from mcp import types
from mcp.server.lowlevel import Server

from freecad_buddy.adapters.audit_log import AuditSink
from freecad_buddy.adapters.rpc_dispatch import (
    MethodRegistry,
    RpcMethod,
    is_audited,
    wrote_own_audit,
)
from freecad_buddy.usecases import confirm, view_fit
from freecad_buddy.usecases.capabilities import (
    Capabilities,
    auto_approve_enabled,
    exec_registered,
)

__all__ = ["Capabilities", "exec_registered", "build_server", "configure_stderr_logging"]

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
        if method.internal:
            continue
        if method.name == "debug_exec" and not exec_registered(caps):
            continue
        tools.append(_tool_for(method))
    return tools


def _to_call_result(envelope: dict) -> types.CallToolResult:
    """Wrap a result envelope as a ``CallToolResult``, flagging non-OK statuses as errors."""
    text = json.dumps(envelope, separators=(",", ":"), ensure_ascii=False)
    return types.CallToolResult(
        content=[types.TextContent(type="text", text=text)],
        structuredContent=dict(envelope),
        isError=envelope.get("status") != "OK",
    )


class _SuspectDocuments:
    """Document handles whose state is unknown because a call on them timed out.

    A ``doc``-less call gets its own slot so it cannot be confused with a handle. The tool-call
    boundary processes one call at a time, so this needs no lock.
    """

    def __init__(self) -> None:
        self._docs: set[str] = set()
        self._no_doc = False

    def is_suspect(self, doc) -> bool:
        if doc is None:
            return self._no_doc
        return isinstance(doc, str) and doc in self._docs

    def mark(self, doc) -> None:
        if doc is None:
            self._no_doc = True
        elif isinstance(doc, str):
            self._docs.add(doc)

    def clear(self, doc) -> None:
        if doc is None:
            self._no_doc = False
        elif isinstance(doc, str):
            self._docs.discard(doc)


def _is_marshal_timeout(envelope: dict) -> bool:
    if envelope.get("status") != "TIMEOUT":
        return False
    detail = envelope.get("detail")
    data = detail.get("data") if isinstance(detail, dict) else None
    return bool(isinstance(data, dict) and data.get("marshal_timeout"))


def _with_suspect_message(envelope: dict, *, marked_suspect: bool) -> dict:
    """Restate a marshal ``TIMEOUT`` so the operator reads the consequence, not just the budget.

    ``marked_suspect`` selects the wording: a mutating call leaves the document refused until a
    read clears it, while a read that timed out only leaves a body still running.
    """
    detail = envelope.get("detail")
    if not isinstance(detail, dict):
        return envelope
    consequence = (
        "the document is now suspect: do not blind-retry, run a query_* read first to confirm "
        "the document still responds"
        if marked_suspect
        else "no mutation was attempted, so the document is not marked suspect"
    )
    amended = dict(envelope)
    amended_detail = dict(detail)
    amended_detail["message"] = (
        f"{detail.get('message') or 'marshaled call timed out'}; "
        f"the body may still be running and {consequence}"
    )
    amended["detail"] = amended_detail
    return amended


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
    if auto_approve_enabled(caps):
        logger.warning("SECURITY: mutation auto-approve ENABLED by operator flag")
    # The mutation gate and the camera fit write their own records through this sink; the handlers
    # the registry holds take no sink argument of their own.
    confirm.set_approval_sink(audit)
    view_fit.set_audit_sink(audit)

    server: Server = Server(name)
    suspect = _SuspectDocuments()

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
        mutating = bool(method is not None and method.mutating)
        audited = method is not None and is_audited(method)
        event = method.audit_event if method is not None else "mutation"

        if doc is not None and not isinstance(doc, str):
            if audited:
                _audit_safe(audit.before, event, tool_name, None, args)
            envelope = _invalid_input_envelope("doc handle must be a string")
            if audited:
                _audit_safe(audit.after, event, tool_name, None, args, envelope.get("status"))
            return _to_call_result(envelope)

        if mutating and suspect.is_suspect(doc):
            _audit_safe(audit.before, event, tool_name, doc, args)
            envelope = _invalid_input_envelope(
                "document-suspect: a prior call timed out on this document and its body may "
                "still be running; run a query_* read to confirm the document still responds "
                "before mutating"
            )
            _audit_safe(audit.after, event, tool_name, doc, args, envelope.get("status"))
            return _to_call_result(envelope)

        # A mutating call's pair is written after dispatch so a bracketed mutation, which wrote
        # its own joinable pair, gets no second one. Every other audited call (debug_exec,
        # preview_dry_run) records its `before` line ahead of execution, so the line survives a
        # call that never returns.
        if audited and not mutating:
            _audit_safe(audit.before, event, tool_name, doc, args)
        envelope = registry.dispatch(tool_name, args)
        if _is_marshal_timeout(envelope):
            if mutating:
                suspect.mark(doc)
            envelope = _with_suspect_message(envelope, marked_suspect=mutating)
        elif method is not None and not mutating and envelope.get("status") == "OK":
            suspect.clear(doc)
        if audited and not (mutating and wrote_own_audit(envelope)):
            if mutating:
                _audit_safe(audit.before, event, tool_name, doc, args)
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


def _invalid_input_envelope(message: str) -> dict:
    from freecad_buddy.contracts import mirror_text

    structured: dict = {}
    return {
        "schema": "fcb.result-envelope/1",
        "status": "INVALID_INPUT",
        "detail": {"code": "INVALID_INPUT", "message": message, "data": {}},
        "structured_content": structured,
        "text": mirror_text(structured),
    }


def _denied_exec_envelope() -> dict:
    return _invalid_input_envelope(
        "debug_exec is disabled (set FREECAD_BUDDY_ALLOW_EXEC=1 to enable)"
    )


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
