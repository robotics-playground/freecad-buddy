import asyncio, json
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client
async def call(s, t, a):
    r = await s.call_tool(t, a); txt = "".join(b.text for b in r.content if hasattr(b, "text"))
    try: return json.loads(txt)
    except Exception: return {"_raw": txt}
async def main():
    async with streamablehttp_client("http://127.0.0.1:8765/mcp") as (r, w, _):
        async with ClientSession(r, w) as s:
            await s.initialize()
            tools = (await s.list_tools()).tools
            print("tools", len(tools))
            d = await call(s, "document_create", {"label": "AutoApproveProbe"}); h = d["structured_content"]["doc"]
            m = await call(s, "feature_body_create", {"doc": h, "name": "Body"})
            print("body without confirm:", m["status"], json.dumps(m.get("detail"))[:300], json.dumps((m.get("structured_content") or {}).get("confirm") or (m.get("structured_content") or {}).get("approval"))[:300])
            print(json.dumps(m)[:1500])
            c = await call(s, "document_close", {"doc": h}); print("close", c["status"])
asyncio.run(main())
