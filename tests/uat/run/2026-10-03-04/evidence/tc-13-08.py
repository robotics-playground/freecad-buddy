import asyncio, json
from tclib import *
log = Log("tc-13-08.jsonl")
async def main():
    async with mcp_session() as s:
        g = await call(s, "document_open", {"path": GOLD + "box-10-20-30.FCStd"}, log); G = sc(g)["doc"]
        await call(s, "document_list", {}, log)
        time.sleep(1)
        st = snap("tc-13-08-before.png"); before = tree_items(st)
        tabs_b = [e["label"] for e in elements(st, role="TabItem")]
        log("before", tree=before, tabs=tabs_b)
        c = await call(s, "document_create", {"label": "TC13Parity"}, log); N = sc(c).get("doc")
        time.sleep(1.5)
        st = snap("tc-13-08-after-create.png"); after = tree_items(st)
        tabs_a = [e["label"] for e in elements(st, role="TabItem")]
        log("after", tree=after, tabs=tabs_a)
        await call(s, "document_list", {}, log)
        await call(s, "query_tree_summary", {"doc": N}, log)
        await call(s, "query_tree_summary", {"doc": G}, log)
        await call(s, "view_fit_viewport", {"doc": G}, log)
        time.sleep(1)
        st = snap("tc-13-08-after.png")
        json.dump({"h": N, "g": G}, open("cur.json", "w"))
asyncio.run(main())
