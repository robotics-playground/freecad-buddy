import asyncio, json, sys
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client
async def call(s, t, a):
    r = await s.call_tool(t, a); txt = "".join(b.text for b in r.content if hasattr(b, "text"))
    return json.loads(txt)
async def main():
    async with streamablehttp_client("http://127.0.0.1:8765/mcp") as (r, w, _):
        async with ClientSession(r, w) as s:
            await s.initialize()
            d = await call(s, "document_create", {"label": "Scratch6a"}); print(json.dumps(d)[:400])
            h = d["structured_content"]["doc"]
            p = await call(s, "preview_dry_run", {"doc": h, "operation": {"tool": "feature_body_create", "args": {"name": "Body"}}}); print(p["status"])
            pid = p["structured_content"]["preview_id"]
            m = await call(s, "feature_body_create", {"doc": h, "name": "Body", "confirm": {"preview_id": pid, "elicitation_action": "accept"}})
            print(m["status"], json.dumps(m["structured_content"].get("post_verify")))
            c = await call(s, "document_close", {"doc": h}); print("close", c["status"])
asyncio.run(main())
