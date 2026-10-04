import asyncio, json
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client
async def main():
    async with streamablehttp_client("http://127.0.0.1:8765/mcp") as (r, w, _):
        async with ClientSession(r, w) as s:
            await s.initialize()
            tools = (await s.list_tools()).tools
            out = {t.name: t.inputSchema for t in tools}
            json.dump(out, open("tc-03-00-schemas.json", "w"), indent=1)
            print(sorted(out))
asyncio.run(main())
