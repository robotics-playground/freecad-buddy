"""Small MCP HTTP client for the container bridge: python mcpcall.py <tool> '<json args>'."""
import asyncio, json, sys, time
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client
URL = "http://127.0.0.1:18765/mcp"

async def call_many(calls):
    out = []
    async with streamable_http_client(URL) as (r, w, _):
        async with ClientSession(r, w) as s:
            await s.initialize()
            for name, args in calls:
                t = time.monotonic()
                try:
                    res = await s.call_tool(name, args)
                    sc = res.structuredContent
                    txt = [c.text for c in res.content if getattr(c, "text", None)]
                    out.append({"tool": name, "args": args, "elapsed_s": round(time.monotonic() - t, 3), "isError": res.isError, "structured": sc, "text": txt})
                except Exception as e:
                    out.append({"tool": name, "args": args, "elapsed_s": round(time.monotonic() - t, 3), "exception": repr(e)})
    return out

if __name__ == "__main__":
    print(json.dumps(asyncio.run(call_many([(sys.argv[1], json.loads(sys.argv[2]))])), indent=1, default=str))
