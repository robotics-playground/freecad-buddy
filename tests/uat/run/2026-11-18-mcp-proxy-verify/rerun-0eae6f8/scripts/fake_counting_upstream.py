"""Verifier fake: counts executions of each tool in a file, then crashes, hangs or answers.

    python fake_counting_upstream.py --count-file F [--port N]
"""

from __future__ import annotations

import argparse
import asyncio
import os
from pathlib import Path

from mcp import types
from mcp.server.fastmcp import FastMCP

parser = argparse.ArgumentParser()
parser.add_argument("--count-file", type=Path, required=True)
parser.add_argument("--port", type=int)
arguments = parser.parse_args()

app = FastMCP("counting-upstream", port=arguments.port or 8000)
low_level = app._mcp_server
TOOLS = ["count_crash", "count_hang", "slow", "pid"]


async def list_tools(_request: types.ListToolsRequest) -> types.ServerResult:
    tools = [types.Tool(name=n, inputSchema={"type": "object"}) for n in TOOLS]
    return types.ServerResult(types.ListToolsResult(tools=tools))


async def call_tool(request: types.CallToolRequest) -> types.ServerResult:
    name, args = request.params.name, request.params.arguments or {}
    with arguments.count_file.open("a", encoding="utf-8") as handle:
        handle.write(f"{name} {os.getpid()}\n")
    if name == "count_crash":
        await asyncio.sleep(float(args.get("delay", 0.0)))
        os._exit(1)
    if name == "count_hang":
        await asyncio.sleep(10**6)
    if name == "slow":
        await asyncio.sleep(float(args.get("seconds", 1.0)))
    result = types.CallToolResult(
        content=[types.TextContent(type="text", text="ok")],
        structuredContent={"tool": name, "pid": os.getpid()},
    )
    return types.ServerResult(result)


low_level.request_handlers[types.ListToolsRequest] = list_tools
low_level.request_handlers[types.CallToolRequest] = call_tool

app.run(transport="streamable-http" if arguments.port else "stdio")
