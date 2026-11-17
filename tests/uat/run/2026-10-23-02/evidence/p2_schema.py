"""Print the MCP input schema of one tool from tools/list on :8765: p2_schema.py <tool>."""
import asyncio
import json
import sys

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client


async def main(name):
    async with streamablehttp_client("http://127.0.0.1:8765/mcp") as (read, write, _):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools = (await session.list_tools()).tools
            print(f"tools/list count {len(tools)}")
            tool = next(t for t in tools if t.name == name)
            print(json.dumps(tool.inputSchema, indent=1))

asyncio.run(main(sys.argv[1]))
