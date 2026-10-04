import asyncio, json
from tclib import *
log = Log("tc-13-09.jsonl")
async def main():
    async with mcp_session() as s:
        await call(s, "document_list", {}, log)
        time.sleep(1)
        st = snap("tc-13-09-before.png"); log("before", tree=tree_items(st))
        await call(s, "document_open", {"path": "benchmarks/g0/golden-models/box-10-20-30.FCStd"}, log)
        o = await call(s, "document_open", {"path": GOLD + "box-10-20-30.FCStd"}, log); H = sc(o)["doc"]
        time.sleep(1.5)
        st = snap("tc-13-09-after-open.png"); log("after", tree=tree_items(st))
        await call(s, "query_tree_summary", {"doc": H}, log)
        await call(s, "query_mass_properties", {"doc": H, "object": "Box"}, log)
        await call(s, "document_list", {}, log)
        await call(s, "view_fit_viewport", {"doc": H}, log)
        log("fitall", r=slim(fitall())); time.sleep(1.5)
        snap("tc-13-09-after.png")
        json.dump({"h": H}, open("cur.json", "w"))
asyncio.run(main())
