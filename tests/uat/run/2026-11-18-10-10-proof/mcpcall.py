"""Proof helper: call one MCP tool on the container proxy and print the text result.

Run in the container: docker exec -u cua fcb-desktop fcb-py /repo/tests/uat/run/2026-11-18-10-10-proof/mcpcall.py
<tool> '<json arguments>'
"""

import asyncio
import json
import sys

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client


async def main(tool: str, arguments: dict) -> None:
    async with streamablehttp_client("http://127.0.0.1:8765/mcp") as (read, write, _):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.call_tool(tool, arguments)
            print("".join(b.text for b in result.content if hasattr(b, "text")))


asyncio.run(main(sys.argv[1], json.loads(sys.argv[2]) if len(sys.argv) > 2 else {}))
