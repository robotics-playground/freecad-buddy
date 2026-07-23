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

from freecad_buddy.adapters import export_oracle, export_verdict
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


# Mesh verifiers whose oracle legs (trimesh/lib3mf) must run in this external process, never in
# FreeCAD (AD-9/AD-12). The proxy RPCs only the FreeCAD self-read leg and assembles locally.
_MESH_VERIFY_SELF_READ = {
    "verify_export_stl": "export_self_read_stl",
    "verify_export_3mf": "export_self_read_3mf",
}


def _mesh_verify_proxy_handler(client: RpcClient, lock, tool_name: str):
    """Handler for a mesh verifier: RPC the FreeCAD self-read leg, run oracles here, assemble."""
    fmt = "stl" if tool_name.endswith("stl") else "3mf"
    self_read_method = _MESH_VERIFY_SELF_READ[tool_name]

    def handler(**params):
        with lock:
            self_read = client.call(self_read_method, params)
        if self_read.get("status") != "OK":
            return self_read
        facts = self_read["structured_content"]
        source = facts["source"]
        band = facts["volume_band"]
        path = facts["path"]
        if fmt == "stl":
            oracle_legs = [
                export_oracle.safe_oracle(
                    "trimesh_stl", lambda: export_oracle.stl_oracle(path, source["volume"], band)
                ),
                export_oracle.safe_oracle(
                    "stdlib_stl", lambda: export_oracle.StdlibStlOracle().check(path)
                ),
            ]
        else:
            oracle_legs = [
                export_oracle.safe_oracle(
                    "lib3mf",
                    lambda: export_oracle.mesh3mf_oracle(
                        path, source["is_mm"], source["volume"], band
                    ),
                ),
            ]
        return export_verdict.assemble_export_verdict(oracle_legs, facts, facts["banner"])

    return handler


def build_proxy_registry(client: RpcClient, caps: Capabilities) -> MethodRegistry:
    """Build a registry whose handlers forward each call to the listener via ``client``.

    Most tools forward wholesale; the mesh verifiers run their third-party oracle legs in this
    process and RPC only the FreeCAD self-read leg (AD-9). ``RpcClient.call`` never raises, so
    every proxy handler returns a wire envelope directly. A single lock serializes the shared
    client.
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
        if spec.name in _MESH_VERIFY_SELF_READ:
            handler = _mesh_verify_proxy_handler(client, lock, spec.name)
        else:
            handler = make(spec.name)
        methods.register(
            RpcMethod(
                name=spec.name,
                handler=handler,
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
