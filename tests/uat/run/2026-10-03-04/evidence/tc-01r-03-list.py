import asyncio, json
from mcp.client.streamable_http import streamablehttp_client
from mcp import ClientSession
E = 'D:/Work/Personal/Sources/freecad-buddy/tests/uat/run/2026-10-03-04/evidence'
async def main():
    async with streamablehttp_client('http://127.0.0.1:8765/mcp') as (r, w, _):
        async with ClientSession(r, w) as s:
            await s.initialize()
            tools = (await s.list_tools()).tools
            names = sorted(t.name for t in tools)
            json.dump(names, open(f'{E}/tc-01r-03-tools_list.json', 'w'), indent=1)
            print(len(names))
            ap = {t.name: t.inputSchema.get('additionalProperties') for t in tools}
            json.dump(ap, open(f'{E}/tc-01r-03-additionalProperties.json', 'w'), indent=1, sort_keys=True)
            print('additionalProperties values:', sorted(set(map(repr, ap.values()))), 'count False:', sum(1 for v in ap.values() if v is False))
asyncio.run(main())
