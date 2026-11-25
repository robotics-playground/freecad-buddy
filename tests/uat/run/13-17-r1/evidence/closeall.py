"""Close every open document on the container MCP proxy; print document_list before and after."""
import asyncio
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

async def main():
    async with streamablehttp_client("http://127.0.0.1:18765/mcp", timeout=60) as (r, w, _):
        async with ClientSession(r, w) as s:
            await s.initialize()
            res = (await s.call_tool("document_list", {})).structuredContent
            docs = (res.get("structured_content") or {}).get("documents") or []
            print("before:", [(d.get("doc"), d.get("label")) for d in docs])
            for d in docs:
                out = (await s.call_tool("document_close", {"doc": d["doc"]})).structuredContent
                print("close", d.get("label"), out.get("status"), (out.get("detail") or {}).get("message"))
            res = (await s.call_tool("document_list", {})).structuredContent
            print("after:", (res.get("structured_content") or {}).get("documents"))

asyncio.run(main())
