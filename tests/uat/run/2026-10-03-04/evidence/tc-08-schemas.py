import asyncio, json
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client


async def main():
    async with streamablehttp_client("http://127.0.0.1:8765/mcp") as (r, w, _):
        async with ClientSession(r, w) as s:
            await s.initialize()
            tools = (await s.list_tools()).tools
            out = {t.name: t.inputSchema for t in tools}
            with open("tc-08-tools-schemas.json", "w", encoding="utf-8") as f:
                json.dump(out, f, indent=1)
            conf = sorted(n for n, sch in out.items() if "confirm" in (sch.get("properties") or {}))
            print(len(out), "tools;", len(conf), "with confirm:", conf)
            print("confirm schema:", json.dumps(out["feature_pad"]["properties"]["confirm"]))
            print("preview render:", json.dumps(out["preview_dry_run"]["properties"].get("render")), "required", out["preview_dry_run"].get("required"))
            print("undo expect:", json.dumps(out["document_undo"]["properties"].get("expect_fingerprint"))[:300])
asyncio.run(main())
