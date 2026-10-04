import asyncio, json
from tclib import *
log = Log("tc-13-01.jsonl")
async def main():
    async with mcp_session() as s:
        o = await call(s, "document_open", {"path": GOLD + "box40-hole-r5.FCStd"}, log)
        h = sc(o).get("doc") or sc(o).get("handle")
        print("HANDLE", h, list(sc(o).keys()))
        await call(s, "query_tree_summary", {"doc": h, "depth": 2}, log)
        await call(s, "document_list", {}, log)
        st = snap("tc-13-01-tree.png")
        log("gui", treeitems=tree_items(st), trees=[e.get("label") for e in elements(st, role="Tree")],
            roles=sorted({e.get("role") for e in st.get("elements", [])}))
        fit = await call(s, "view_fit_viewport", {"doc": h}, log)
        log("gui_fitall", r=slim(fitall()))
        time.sleep(1)
        st = snap("tc-13-01-after.png")
        log("gui_after", treeitems=tree_items(st))
asyncio.run(main())
