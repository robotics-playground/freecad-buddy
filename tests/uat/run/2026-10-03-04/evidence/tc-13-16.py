import asyncio, json, shutil
from tclib import *
log = Log("tc-13-16.jsonl")
c = json.load(open("cur.json")); B = c["b"]
async def main():
    async with mcp_session() as s:
        before = await call(s, "document_list", {}, log)
        st = snap()
        card = [e for e in elements(st, role="ListItem") if (e.get("frame") or {}).get("y", 0) > 500 and (e.get("frame") or {}).get("y", 0) < 900]
        log("card", n=len(card), tok=card[0]["element_token"] if card else None)
        r = click_token(card[0]["element_token"]); log("click_card", r=slim(r)); time.sleep(3)
        st = snap("tc-13-16-after-open.png"); log("tree", t=tree_items(st))
        if "box-10-20-30" not in tree_items(st):
            pid, win = ids()
            log("pixel_card", r=cua("click", {"pid": pid, "window_id": win, "x": 416, "y": 620, "count": 2})); time.sleep(3)
            st = snap("tc-13-16-after-open.png"); log("tree2", t=tree_items(st))
        after = await call(s, "document_list", {}, log)
        new = [d for d in sc(after).get("documents", []) if d["doc"] not in [x["doc"] for x in sc(before).get("documents", [])]]
        log("new", d=new)
        if new:
            N = new[0]["doc"]; c["n"] = N; json.dump(c, open("cur.json", "w"))
            t = await call(s, "query_tree_summary", {"doc": N}, log)
            await call(s, "query_mass_properties", {"doc": N, "object": "Box"}, log)
            await call(s, "query_tree_summary", {"doc": B}, log)
            await call(s, "view_fit_viewport", {"doc": N}, log)
            log("fitall", r=slim(fitall())); time.sleep(1.5)
            snap("tc-13-16-after.png")
asyncio.run(main())
