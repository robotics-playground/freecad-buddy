"""Fake MCP upstream for the cache-proxy tests: a real MCP server over stdio or streamable HTTP.

    python fake_mcp_upstream.py --tools-file F --marker M [--count-file C] [--port N]

The tool list is read from the JSON file `F` on every `tools/list`, so a test changes it without
restarting the process. Tools: `echo` (structuredContent), `fail` (isError), `flaky` (exits once).
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import threading
from pathlib import Path

from mcp import types
from mcp.server.fastmcp import FastMCP

parser = argparse.ArgumentParser()
parser.add_argument("--tools-file", type=Path, required=True)
parser.add_argument("--marker", type=Path, required=True)
parser.add_argument("--count-file", type=Path)
parser.add_argument("--port", type=int)
parser.add_argument("--instructions")
arguments = parser.parse_args()

app = FastMCP("fake-upstream", instructions=arguments.instructions, port=arguments.port or 8000)
low_level = app._mcp_server


async def list_tools(_request: types.ListToolsRequest) -> types.ServerResult:
    names = json.loads(arguments.tools_file.read_text(encoding="utf-8"))
    tools = [
        types.Tool(name=name, description=f"fake {name}", inputSchema={"type": "object"})
        for name in names
    ]
    return types.ServerResult(types.ListToolsResult(tools=tools))


async def call_tool(request: types.CallToolRequest) -> types.ServerResult:
    name, tool_arguments = request.params.name, request.params.arguments or {}
    if name == "flaky" and not arguments.marker.exists():
        arguments.marker.write_text("crashed", encoding="utf-8")
        os._exit(1)
    if name == "die":
        with arguments.count_file.open("a", encoding="utf-8") as count_file:
            count_file.write("executed" + chr(10))
        await asyncio.sleep(0.5)
        os._exit(1)
    if name == "exit_soon":
        threading.Timer(0.2, lambda: os._exit(0)).start()
    if name == "fail":
        result = types.CallToolResult(
            content=[types.TextContent(type="text", text="boom")],
            structuredContent={"error": "boom"},
            isError=True,
        )
    else:
        result = types.CallToolResult(
            content=[types.TextContent(type="text", text="human text")],
            structuredContent={"tool": name, "arguments": tool_arguments},
        )
    return types.ServerResult(result)


low_level.request_handlers[types.ListToolsRequest] = list_tools
low_level.request_handlers[types.CallToolRequest] = call_tool

app.run(transport="streamable-http" if arguments.port else "stdio")
