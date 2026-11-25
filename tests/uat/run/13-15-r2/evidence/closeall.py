"""Close every document the container FreeCAD holds (run hygiene between TC-18 scenarios)."""
import asyncio
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client


async def main():
    async with streamablehttp_client("http://127.0.0.1:18765/mcp", timeout=60) as (rd, wr, _):
        async with ClientSession(rd, wr) as s:
            await s.initialize()
            res = await s.call_tool("document_list", {})
            docs = (res.structuredContent.get("structured_content") or {}).get("documents") or []
            for d in docs:
                handle = d.get("doc") or d.get("handle")
                r = await s.call_tool("document_close", {"doc": handle})
                print("closed", handle, d.get("label"), r.structuredContent.get("status"))
            print("documents before close:", len(docs))


asyncio.run(main())
