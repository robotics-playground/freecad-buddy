"""Read the whole Block bounding box in the open TC-18-04 document (R1-D1 support side)."""
import asyncio, json, sys
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client


async def main():
    async with streamablehttp_client("http://127.0.0.1:18765/mcp", timeout=60) as (rd, wr, _):
        async with ClientSession(rd, wr) as s:
            await s.initialize()
            docs = (await s.call_tool("document_list", {})).structuredContent["structured_content"]["documents"]
            doc = docs[0].get("doc") or docs[0].get("handle")
            code = ("b = doc.getObject('Block').Shape.BoundBox\n"
                    "result = [round(v, 9) for v in (b.XMin, b.YMin, b.ZMin, b.XMax, b.YMax, b.ZMax)]")
            res = await s.call_tool("script_exec", {"doc": doc, "code": code})
            print(json.dumps(res.structuredContent["structured_content"]["value_repr"]))


asyncio.run(main())
