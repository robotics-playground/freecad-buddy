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
    registered_tools,
)
from freecad_buddy.adapters.rpc_client import RpcClient
from freecad_buddy.adapters.rpc_dispatch import MethodRegistry
from freecad_buddy.hosts.rpc_proxy import build_proxy_registry

logger = logging.getLogger("freecad_buddy.hosts.gui_external")

_HOST = "127.0.0.1"
_PORT = 8765


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
        method = registry.get(tool_name)
        return _to_call_result(envelope, structured=method is None or method.structured_output)

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
    """Serve the proxy MCP surface over streamable HTTP at ``host:port/mcp``.

    Windowless-safe: when launched under ``pythonw.exe`` (the addon spawns it that way so no
    console window appears) ``sys.stdout``/``sys.stderr`` are ``None``. A stream-logging config
    would then crash at startup, so logging is only wired to stderr when it exists, and uvicorn's
    default stdout logging config is disabled (``log_config=None``).
    """
    import sys

    if sys.stderr is not None:
        from freecad_buddy.adapters.mcp_server import configure_stderr_logging

        configure_stderr_logging()

    caps = Capabilities.from_env(dict(os.environ))
    client = RpcClient()
    registry = build_proxy_registry(client, caps)
    server = build_proxy_server(registry, caps)
    app = build_app(server)

    logger.info("freecad-buddy GUI-external MCP server on http://%s:%s/mcp", host, port)
    config = uvicorn.Config(app, host=host, port=port, log_level="warning", log_config=None)
    uvicorn.Server(config).run()
    return 0
