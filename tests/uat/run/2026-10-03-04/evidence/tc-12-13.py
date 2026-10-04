import asyncio, json
from tclib import *
log = Log("tc-12-13.jsonl")
async def main():
    async with mcp_session() as s:
        b = await call(s, "document_open", {"path": GOLD + "cylinder-r5-h20.FCStd"}, log); B = sc(b)["doc"]
        a = await call(s, "document_open", {"path": GOLD + "box-10-20-30.FCStd"}, log); A = sc(a)["doc"]
        await call(s, "document_list", {}, log)
        await call(s, "query_tree_summary", {"doc": A}, log); await call(s, "query_tree_summary", {"doc": B}, log)
        tb = await call(s, "query_tree_summary", {"doc": B}, log); objB = sc(tb)["tree"][0]["name"]
        mb = await call(s, "query_mass_properties", {"doc": B, "object": objB}, log)
        time.sleep(1)
        st = snap("tc-12-13-tree.png"); log("tree_before", t=tree_items(st))
        log("click_root", r=slim(click_label("TreeItem", "box-10-20-30"))); time.sleep(1)
        r = menu_retry(["File", "Close"], tries=10, wait=6); log("menu_close", r=r); time.sleep(2)
        pid, win = ids()
        log("windows", w=cua("list_windows", {"pid": pid}).get("windows"))
        st = snap(); log("tree_after", t=tree_items(st))
        log("verify_state", r=cua("verify_state", {"pid": pid, "window_id": win, "expect": [{"element": {"selector": {"label_contains": "box-10-20-30"}, "exists": False}}]}))
        await call(s, "query_tree_summary", {"doc": A}, log)
        await call(s, "query_mass_properties", {"doc": A}, log)
        await call(s, "query_screenshot", {"doc": A}, log)
        await call(s, "document_close", {"doc": A}, log)
        await call(s, "document_list", {}, log)
        await call(s, "query_mass_properties", {"doc": B}, log)
        await call(s, "query_mass_properties", {"doc": B, "object": objB}, log)
        await call(s, "query_capabilities", {}, log)
        await call(s, "view_fit_viewport", {"doc": B}, log)
        log("fitall", r=slim(fitall())); time.sleep(1.5)
        snap("tc-12-13-after.png")
        json.dump({"h": B}, open("cur.json", "w"))
asyncio.run(main())
