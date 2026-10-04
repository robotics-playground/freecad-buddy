import asyncio, json
from tclib import *
log = Log("tc-13-15b.jsonl")
H = json.load(open("cur.json"))["h"]
async def main():
    async with mcp_session() as s:
        pid, win = ids()
        log("vp_click", r=cua("click", {"pid": pid, "window_id": win, "x": 640, "y": 700})); time.sleep(1)
        st = snap("tc-13-15-renamed.png"); log("tree_renamed", t=tree_items(st))
        await call(s, "query_tree_summary", {"doc": H}, log)
        items = elements(st, role="TreeItem")
        tok = [items[i + 1]["element_token"] for i, e in enumerate(items[:-1]) if e["label"] == "Label"][0]
        log("revert_set_value", r=cua("set_value", {"pid": pid, "element_token": tok, "value": "BoxHole"})); time.sleep(1.5)
        await call(s, "query_tree_summary", {"doc": H}, log)
        await call(s, "query_object", {"doc": H, "object": "BoxHole"}, log)
        await call(s, "query_mass_properties", {"doc": H, "object": "BoxHole"}, log)
        await call(s, "view_fit_viewport", {"doc": H}, log); time.sleep(1)
        st = snap("tc-13-15-after.png"); log("tree_after", t=tree_items(st))
asyncio.run(main())
