"""TC-07 file Precondition for phase P6: list the live tools of the :8765 proxy and write
evidence/tool_surface.json as {name: {"mut": not readOnlyHint, "props": [input property names]}}.
Then print every mutating tool whose schema declares ``confirm``: p6_tools.py"""
import asyncio
import json
from pathlib import Path

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

EVIDENCE = Path(__file__).resolve().parent


async def main():
    async with streamablehttp_client("http://127.0.0.1:8765/mcp") as (read, write, _):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools = (await session.list_tools()).tools
    surface = {}
    for tool in tools:
        read_only = bool(tool.annotations and tool.annotations.readOnlyHint)
        surface[tool.name] = {"mut": not read_only, "props": sorted((tool.inputSchema or {}).get("properties", {})),
                              "additionalProperties": (tool.inputSchema or {}).get("additionalProperties")}
    (EVIDENCE / "tool_surface.json").write_text(json.dumps(surface, indent=1, sort_keys=True), encoding="utf-8")
    print("tools:", len(surface), "script_exec listed:", "script_exec" in surface)
    print("mut tools with confirm:", [k for k, v in surface.items() if v["mut"] and "confirm" in v["props"]])
    print("export_* props:", {k: v["props"] for k, v in surface.items() if k.startswith("export_")})
    print("export_* additionalProperties:", {k: v["additionalProperties"] for k, v in surface.items()
                                             if k.startswith("export_")})


asyncio.run(main())
