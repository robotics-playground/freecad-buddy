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

from freecad_buddy.adapters.audit_log import AuditSink
from freecad_buddy.adapters.marshal import InlineExecutor, Marshal
from freecad_buddy.adapters.mcp_server import (
    Capabilities,
    build_server,
    configure_stderr_logging,
    exec_registered,
    serve_stdio,
)
from freecad_buddy.adapters.rpc_dispatch import MethodRegistry, RpcMethod
from freecad_buddy.usecases import debug_exec as debug_exec_uc
from freecad_buddy.usecases import queries
from freecad_buddy.usecases.documents import DocumentRegistry

logger = logging.getLogger("freecad_buddy.hosts.headless")

_DOC_SCHEMA = {"type": "string", "description": "opaque fcb-doc handle"}


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
    """Register the tool surface, each handler marshaled onto the FreeCAD thread."""
    methods = MethodRegistry()

    def marshaled(fn, timeout_s):
        def handler(**params):
            return marshal.call(lambda: fn(**params), timeout_s)

        return handler

    methods.register(
        RpcMethod(
            name="document_create",
            handler=marshaled(registry.document_create, 30.0),
            input_schema={
                "type": "object",
                "properties": {"label": {"type": "string"}, "path": {"type": "string"}},
                "required": ["label"],
                "additionalProperties": False,
            },
            description="Create a new document; mint and return its opaque handle.",
            mutating=True,
        )
    )
    methods.register(
        RpcMethod(
            name="document_open",
            handler=marshaled(registry.document_open, 60.0),
            input_schema={
                "type": "object",
                "properties": {"path": {"type": "string"}},
                "required": ["path"],
                "additionalProperties": False,
            },
            description="Open an .FCStd file; return its opaque handle.",
            mutating=True,
        )
    )
    methods.register(
        RpcMethod(
            name="document_save",
            handler=marshaled(registry.document_save, 120.0),
            input_schema={
                "type": "object",
                "properties": {"doc": _DOC_SCHEMA, "path": {"type": "string"}},
                "required": ["doc"],
                "additionalProperties": False,
            },
            description="Save (or save-as) the document named by its handle.",
            mutating=True,
        )
    )
    methods.register(
        RpcMethod(
            name="document_close",
            handler=marshaled(registry.document_close, 30.0),
            input_schema={
                "type": "object",
                "properties": {"doc": _DOC_SCHEMA},
                "required": ["doc"],
                "additionalProperties": False,
            },
            description="Close the document by handle; releases the handle.",
            mutating=True,
        )
    )
    methods.register(
        RpcMethod(
            name="document_recompute",
            handler=marshaled(registry.document_recompute, 120.0),
            input_schema={
                "type": "object",
                "properties": {"doc": _DOC_SCHEMA},
                "required": ["doc"],
                "additionalProperties": False,
            },
            description="Full recompute; report touched-object count and per-object error states.",
            mutating=True,
        )
    )
    methods.register(
        RpcMethod(
            name="document_list",
            handler=marshaled(registry.document_list, 30.0),
            input_schema={"type": "object", "properties": {}, "additionalProperties": False},
            description="List open documents with handle, name, label, and transient flag.",
            mutating=False,
        )
    )
    methods.register(
        RpcMethod(
            name="query_capabilities",
            handler=marshaled(
                lambda: queries.query_capabilities(exec_enabled=exec_registered(caps)), 30.0
            ),
            input_schema={"type": "object", "properties": {}, "additionalProperties": False},
            description="Runtime capability probes: version, element_map, serializer, "
            "varset backend, render, exec state.",
            mutating=False,
        )
    )

    # Gate the exec path at registration: when disabled the handler never enters the registry,
    # so no dispatch path can reach it. The tools/list and call-tool guards are defense in depth.
    if exec_registered(caps):

        def _debug_exec(**params):
            return marshal.call(
                lambda: debug_exec_uc.debug_exec(
                    registry, params.get("doc"), params.get("code", "")
                ),
                30.0,
            )

        methods.register(
            RpcMethod(
                name="debug_exec",
                handler=_debug_exec,
                input_schema={
                    "type": "object",
                    "properties": {"doc": _DOC_SCHEMA, "code": {"type": "string"}},
                    "required": ["doc", "code"],
                    "additionalProperties": False,
                },
                description="Operator-only Python exec for bring-up. Off unless "
                "FREECAD_BUDDY_ALLOW_EXEC=1; every call is audit-logged.",
                mutating=True,
                audit_event="exec",
            )
        )
    return methods


def _default_audit_path() -> Path:
    return Path(os.environ.get("FREECAD_BUDDY_AUDIT_LOG", "freecad-buddy-audit.jsonl"))


def run(argv: list[str] | None = None) -> int:  # noqa: ARG001 - reserved for future flags
    """Verify FreeCAD, build the H1 stack, and serve the MCP surface over stdio."""
    configure_stderr_logging()
    try:
        verify_freecad_importable()
    except FreeCADUnavailable as exc:
        sys.stderr.write(f"{exc}\n")
        return 2

    caps = Capabilities.from_env(dict(os.environ))
    doc_registry = DocumentRegistry()
    marshal = Marshal(InlineExecutor())
    methods = build_registry(doc_registry, caps, marshal)
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
