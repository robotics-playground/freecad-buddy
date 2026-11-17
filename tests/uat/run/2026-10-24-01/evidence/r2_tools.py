"""List the :8765 proxy's tools/list and write every tool's inputSchema to evidence/<out>; print the
tools whose inputSchema has a ``confirm`` property: r2_tools.py <out.json>."""
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
    surface = {t.name: t.inputSchema for t in tools}
    (EVIDENCE / sys.argv[1]).write_text(json.dumps(surface, indent=1), encoding="utf-8")
    gated = sorted(n for n, s in surface.items() if "confirm" in (s.get("properties") or {}))
    print("tools", len(surface), "with confirm", len(gated))
    print(gated)


asyncio.run(main())
