import asyncio, json
from tclib import *
log = Log("tc-13-18b.jsonl")
c = json.load(open("cur.json")); A, B = c["a"], c["b"]
async def main():
    st = snap("tc-13-18-after-close.png"); log("tree", t=tree_items(st))
    pid, win = ids()
    log("verify_state", r=cua("verify_state", {"pid": pid, "window_id": win, "expect": [{"element": {"selector": {"label_contains": "box-10-20-30"}, "exists": False}}]}))
    async with mcp_session() as s:
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
