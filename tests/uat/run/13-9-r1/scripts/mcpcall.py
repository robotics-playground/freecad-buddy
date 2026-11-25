"""Tiny MCP client: `mcpcall.py list` or `mcpcall.py <tool> '<json args>'`."""

import asyncio
import json
import sys
import time

from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

URL = "http://127.0.0.1:18765/mcp"


async def main() -> None:
    async with streamable_http_client(URL) as (read, write, _):
        async with ClientSession(read, write) as session:
            await session.initialize()
            if sys.argv[1] == "list":
                tools = await session.list_tools()
                for tool in tools.tools:
                    if len(sys.argv) > 2 and tool.name != sys.argv[2]:
                        continue
                    print(tool.name)
                    if len(sys.argv) > 2:
                        print(tool.description)
                        print(json.dumps(tool.inputSchema, indent=1))
                return
            start = time.perf_counter()
            reply = await session.call_tool(sys.argv[1], json.loads(sys.argv[2]))
            elapsed = time.perf_counter() - start
            print(json.dumps({"elapsed_s": round(elapsed, 3), "isError": reply.isError,
                              "result": reply.structuredContent}, indent=1))


asyncio.run(main())
