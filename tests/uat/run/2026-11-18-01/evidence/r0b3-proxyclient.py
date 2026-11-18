import asyncio, json, sys
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client
URL = "http://127.0.0.1:8765/mcp"
print("URL", URL)
async def main():
    async with streamablehttp_client(URL) as (r, w, _):
        async with ClientSession(r, w) as s:
            await s.initialize()
            names = [t.name for t in (await s.list_tools()).tools]
            print("proxy tools/list length", len(names), "script_exec listed", "script_exec" in names)
            q = await s.call_tool("query_capabilities", {})
            print("proxy exec_enabled", q.structuredContent["structured_content"]["exec_enabled"])
            if len(sys.argv) > 1:
                h = sys.argv[1]
                e = await s.call_tool("script_exec", {"doc": h, "code": "doc.addObject('Part::Box', 'Leak'); doc.recompute()"})
                print("script_exec isError", e.isError, json.dumps(e.structuredContent)[:700], [getattr(c, 'text', None) for c in e.content][:1])
                t = await s.call_tool("query_tree_summary", {"doc": h})
                print("tree", [getattr(c, 'text', None) for c in t.content])
asyncio.run(main())
