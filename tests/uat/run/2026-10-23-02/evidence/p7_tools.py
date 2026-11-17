"""tools/list against the :8765 proxy for phase P7.

    p7_tools.py <out.json>     write {name: {"addProps": <inputSchema.additionalProperties>,
                               "props": [property names in schema order]}} and print the count

The TC-09 surface commands read ``addProps`` and ``props``.
"""
import asyncio
import json
import sys
from pathlib import Path

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

EVIDENCE = Path(__file__).resolve().parent


async def main():
    async with streamablehttp_client("http://127.0.0.1:8765/mcp") as (read, write, _):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools = (await session.list_tools()).tools
    surface = {tool.name: {"addProps": (tool.inputSchema or {}).get("additionalProperties"),
                           "props": list((tool.inputSchema or {}).get("properties", {}))} for tool in tools}
    (EVIDENCE / sys.argv[1]).write_text(json.dumps(surface, indent=1), encoding="utf-8")
    print(f"tools/list answered: {len(surface)} tools, script_exec listed: {'script_exec' in surface}")


asyncio.run(main())
