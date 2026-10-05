"""Dump input schemas of named tools from the live bridge."""
import asyncio, json, sys
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

async def main():
    async with streamablehttp_client("http://127.0.0.1:8765/mcp") as (r, w, _):
        async with ClientSession(r, w) as s:
            await s.initialize()
            for t in (await s.list_tools()).tools:
                if t.name in sys.argv[1:]:
                    print("==", t.name, "\n", t.description, "\n", json.dumps(t.inputSchema, indent=1))
asyncio.run(main())
