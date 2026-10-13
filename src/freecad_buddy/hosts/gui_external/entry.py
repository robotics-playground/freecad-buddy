"""External GUI-attached MCP server: proxy the tool surface to the in-FreeCAD listener.

Builds a ``MethodRegistry`` from the shared catalog whose handlers forward to a single shared
``RpcClient`` (serialized with a lock, since one connection's socket/buffer/id counter are not
concurrency-safe). Tools are listed from that registry and served over streamable HTTP; each
tool call runs the blocking ``RpcClient.call`` off the asyncio event loop so one in-flight call
cannot stall the ASGI server.

The proxy is bound to one FreeCAD (AD-2): its client pins the discovery record it first connects
to, a watchdog ends the process once that FreeCAD is gone, and ``GET /healthz`` names it.
"""

from __future__ import annotations

import contextlib
import hashlib
import logging
import os
import threading
import time

import anyio
import uvicorn
from mcp import types
from mcp.server.lowlevel import Server
from mcp.server.streamable_http_manager import StreamableHTTPSessionManager
from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.routing import Mount, Route

from freecad_buddy.adapters.mcp_server import (
    Capabilities,
    _to_call_result,
    registered_tools,
)
from freecad_buddy.adapters.rpc_client import RpcClient
from freecad_buddy.adapters.rpc_dispatch import MethodRegistry
from freecad_buddy.contracts.rpc import MCP_PROXY_SERVICE
from freecad_buddy.hosts.rpc_proxy import build_proxy_registry
from freecad_buddy.usecases.process import pid_alive

logger = logging.getLogger("freecad_buddy.hosts.gui_external")

_HOST = "127.0.0.1"
_PORT = 8765
# AD-2 asks the orphan to exit within a few seconds; a liveness check costs one OpenProcess.
_WATCHDOG_INTERVAL_S = 1.0
# A call in flight when FreeCAD died fails at once with WORKER_CRASHED; this delay lets its HTTP
# reply reach the client before the process ends.
_EXIT_GRACE_S = 1.0


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


def _session_id(token: object) -> str | None:
    """A public name for the listener session: a digest prefix that does not disclose the token."""
    if not isinstance(token, str):
        return None
    return hashlib.sha256(token.encode("utf-8")).hexdigest()[:16]


def health(client: RpcClient) -> dict:
    """The ``/healthz`` body: service, pinned FreeCAD pid and session id. Never the token."""
    record = client.pinned_record or {}
    return {
        "service": MCP_PROXY_SERVICE,
        "freecad_pid": record.get("pid"),
        "session_id": _session_id(record.get("token")),
    }


def exit_when_freecad_exits(client: RpcClient, port: int) -> None:
    """Watchdog thread: end this process once the FreeCAD the client is pinned to has exited.

    A clean FreeCAD quit terminates the proxy; after a kill nothing does, and the orphan would
    hold the port against the next FreeCAD. ``os._exit`` because uvicorn's graceful shutdown waits
    for open MCP streams, which a connected client holds for as long as it runs.
    """
    while True:
        time.sleep(_WATCHDOG_INTERVAL_S)
        pid = (client.pinned_record or {}).get("pid")
        if isinstance(pid, int) and not pid_alive(pid):
            logger.warning(
                "FreeCAD pid %s has exited; the MCP proxy exits and frees port %s", pid, port
            )
            time.sleep(_EXIT_GRACE_S)
            logging.shutdown()
            os._exit(0)


def build_app(server: Server, client: RpcClient) -> Starlette:
    """Mount the MCP streamable-HTTP endpoint at ``/mcp`` and the health probe at ``/healthz``."""
    manager = StreamableHTTPSessionManager(app=server)

    async def _handle(scope, receive, send):
        await manager.handle_request(scope, receive, send)

    async def _healthz(request):  # noqa: ANN001, ARG001 - starlette endpoint signature
        return JSONResponse(health(client))

    @contextlib.asynccontextmanager
    async def _lifespan(app):  # noqa: ANN001, ARG001 - starlette lifespan signature
        async with manager.run():
            yield

    return Starlette(
        routes=[Route("/healthz", _healthz, methods=["GET"]), Mount("/mcp", app=_handle)],
        lifespan=_lifespan,
    )


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
    client = RpcClient(pin=True)
    # The addon writes its discovery record before it spawns the proxy, so the pin is that
    # FreeCAD's even when no tool is ever called; started before any FreeCAD, the first call pins.
    pinned = client.pin()
    logger.info("pinned to FreeCAD pid %s", pinned.get("pid") if pinned else None)
    threading.Thread(
        target=exit_when_freecad_exits,
        args=(client, port),
        name="freecad-buddy-watchdog",
        daemon=True,
    ).start()
    registry = build_proxy_registry(client, caps)
    server = build_proxy_server(registry, caps)
    app = build_app(server, client)

    logger.info("freecad-buddy GUI-external MCP server on http://%s:%s/mcp", host, port)
    config = uvicorn.Config(app, host=host, port=port, log_level="warning", log_config=None)
    uvicorn.Server(config).run()
    return 0
