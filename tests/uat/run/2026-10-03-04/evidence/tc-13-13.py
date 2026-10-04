import asyncio, json
from tclib import *
log = Log("tc-13-13.jsonl")
c = json.load(open("cur.json")); A, B = c["h"], c["g"]
async def main():
    async with mcp_session() as s:
        await call(s, "document_list", {}, log)
        await call(s, "query_tree_summary", {"doc": A}, log); await call(s, "query_tree_summary", {"doc": B}, log)
        st = snap("tc-13-13-before.png"); log("before", tree=tree_items(st))
        await call(s, "document_close", {"doc": A}, log)
        time.sleep(1.5)
        st = snap("tc-13-13-after-close.png"); log("after", tree=tree_items(st))
        pid, win = ids()
        v = cua("verify_state", {"pid": pid, "window_id": win, "expect": [{"element": {"selector": {"label_contains": "TC13Parity"}, "exists": False}}]})
        log("verify_state", r=v)
        await call(s, "document_list", {}, log)
        await call(s, "query_tree_summary", {"doc": A}, log)
        await call(s, "query_tree_summary", {"doc": B}, log)
        await call(s, "view_fit_viewport", {"doc": B}, log)
        log("fitall", r=slim(fitall())); time.sleep(1.5)
        snap("tc-13-13-after.png")
asyncio.run(main())
