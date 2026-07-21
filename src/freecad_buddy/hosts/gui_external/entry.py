"""External GUI-attached MCP server: proxy the tool surface to the in-FreeCAD listener.

Builds a ``MethodRegistry`` from the shared catalog whose handlers forward to a single shared
``RpcClient`` (serialized with a lock, since one connection's socket/buffer/id counter are not
concurrency-safe). Tools are listed from that registry and served over streamable HTTP; each
tool call runs the blocking ``RpcClient.call`` off the asyncio event loop so one in-flight call
cannot stall the ASGI server.
"""

from __future__ import annotations

import contextlib
import logging
import os
import threading

import anyio
import uvicorn
from mcp import types
from mcp.server.lowlevel import Server
from mcp.server.streamable_http_manager import StreamableHTTPSessionManager
from starlette.applications import Starlette
from starlette.routing import Mount

from freecad_buddy.adapters.mcp_server import (
    Capabilities,
    _to_call_result,
    exec_registered,
    registered_tools,
)
from freecad_buddy.adapters.rpc_client import RpcClient
from freecad_buddy.adapters.rpc_dispatch import MethodRegistry, RpcMethod
from freecad_buddy.hosts.tool_catalog import DEBUG_EXEC_SPEC, tool_specs

logger = logging.getLogger("freecad_buddy.hosts.gui_external")

_HOST = "127.0.0.1"
_PORT = 8765


def build_proxy_registry(client: RpcClient, caps: Capabilities) -> MethodRegistry:
    """Build a registry whose handlers forward each call to the listener via ``client``.

    ``RpcClient.call`` never raises, so every proxy handler returns a wire envelope directly. A
    single lock serializes access to the shared client.
    """
    lock = threading.Lock()
    methods = MethodRegistry()

    def make(name):
        def handler(**params):
            with lock:
                return client.call(name, params)

        return handler

    specs = list(tool_specs())
    if exec_registered(caps):
        specs.append(DEBUG_EXEC_SPEC)

    for spec in specs:
        methods.register(
            RpcMethod(
                name=spec.name,
                handler=make(spec.name),
                input_schema=spec.input_schema,
                description=spec.description,
                timeout_s=spec.timeout_s,
                mutating=spec.mutating,
                audit_event=spec.audit_event,
            )
        )
    return methods


def build_proxy_server(registry: MethodRegistry, caps: Capabilities) -> Server:
    """Wire tools/list + tools/call, running each blocking proxy call off the event loop."""
    server: Server = Server("freecad-buddy-gui-external")

    @server.list_tools()
    async def _list_tools() -> list[types.Tool]:
        return registered_tools(registry, caps)

    @server.call_tool()
    async def _call_tool(tool_name: str, arguments: dict) -> types.CallToolResult:
        args = arguments if isinstance(arguments, dict) else {}
        envelope = await anyio.to_thread.run_sync(lambda: registry.dispatch(tool_name, args))
        return _to_call_result(envelope)

    return server


def build_app(server: Server) -> Starlette:
    """Mount the MCP streamable-HTTP endpoint at ``/mcp``."""
    manager = StreamableHTTPSessionManager(app=server)

    async def _handle(scope, receive, send):
        await manager.handle_request(scope, receive, send)

    @contextlib.asynccontextmanager
    async def _lifespan(app):  # noqa: ANN001, ARG001 - starlette lifespan signature
        async with manager.run():
            yield

    return Starlette(routes=[Mount("/mcp", app=_handle)], lifespan=_lifespan)


def run(host: str = _HOST, port: int = _PORT) -> int:
    """Serve the proxy MCP surface over streamable HTTP at ``host:port/mcp``."""
    from freecad_buddy.adapters.mcp_server import configure_stderr_logging

    configure_stderr_logging()
    caps = Capabilities.from_env(dict(os.environ))
    client = RpcClient()
    registry = build_proxy_registry(client, caps)
    server = build_proxy_server(registry, caps)
    app = build_app(server)

    logger.info("freecad-buddy GUI-external MCP server on http://%s:%s/mcp", host, port)
    config = uvicorn.Config(app, host=host, port=port, log_level="warning")
    uvicorn.Server(config).run()
    return 0
