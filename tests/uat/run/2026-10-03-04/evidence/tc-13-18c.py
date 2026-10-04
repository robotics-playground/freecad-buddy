import asyncio, json
from tclib import *
log = Log("tc-13-18c.jsonl")
c = json.load(open("cur.json")); B = c["b"]
async def main():
    async with mcp_session() as s:
        o = await call(s, "document_open", {"path": GOLD + "box-10-20-30.FCStd"}, log); A = sc(o)["doc"]
        c["a"] = A; json.dump(c, open("cur.json", "w"))
        await call(s, "document_list", {}, log)
        await call(s, "verify_recompute", {"doc": A}, log)
        time.sleep(1)
        snap("tc-13-18-before.png")
        log("click_root", r=slim(click_label("TreeItem", "box-10-20-30"))); time.sleep(1)
        r = menu_retry(["File", "Close"], tries=10, wait=6); log("menu_close", r=r)
        time.sleep(2)
        st = snap("tc-13-18-after-close.png"); log("tree", t=tree_items(st))
        await call(s, "document_list", {}, log)
        await call(s, "query_tree_summary", {"doc": A}, log)
        await call(s, "query_mass_properties", {"doc": A, "object": "Box"}, log)
        await call(s, "document_close", {"doc": A}, log)
        await call(s, "query_capabilities", {}, log)
        await call(s, "query_tree_summary", {"doc": B}, log)
        await call(s, "view_fit_viewport", {"doc": B}, log)
        log("fitall", r=slim(fitall())); time.sleep(1.5)
        snap("tc-13-18-after.png")
asyncio.run(main())
