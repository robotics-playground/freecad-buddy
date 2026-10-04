import asyncio, json
from tclib import *
log = Log("tc-13-03-repro.jsonl")
async def main():
    async with mcp_session() as s:
        o = await call(s, "document_open", {"path": GOLD + "box-10-20-30.FCStd"}, log)
        H = sc(o)["doc"]; json.dump({"h": H}, open("cur.json", "w"))
        time.sleep(1.5)
        await call(s, "query_tree_summary", {"doc": H}, log)
        await call(s, "verify_recompute", {"doc": H}, log)
        st = snap("tc-13-03-repro-1-opened.png")
        await call(s, "query_screenshot", {"doc": H, "view": {"include": ["Box"]}}, log)
        time.sleep(1.5)
        await call(s, "query_tree_summary", {"doc": H}, log)
        st = snap("tc-13-03-repro-2-after-include-render.png")
        log("title", t=[e.get("label") for e in st["elements"] if e.get("role") in ("TitleBar","Window")][:3])
asyncio.run(main())
