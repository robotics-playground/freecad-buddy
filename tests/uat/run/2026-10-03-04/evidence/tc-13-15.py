import asyncio, json
from tclib import *
log = Log("tc-13-15.jsonl")
H = json.load(open("cur.json"))["h"]
async def main():
    async with mcp_session() as s:
        log("note", n="rename already applied by set_value on the property-panel Label value row (token s000007df:130) at the previous step")
        st = snap("tc-13-15-editing.png"); log("tree_after_rename", t=tree_items(st)[-3:])
        await call(s, "query_tree_summary", {"doc": H}, log)
        await call(s, "query_object", {"doc": H, "object": "BoxHole"}, log)
        await call(s, "query_mass_properties", {"doc": H, "object": "BoxHole"}, log)
        st = snap("tc-13-15-renamed.png"); log("tree", t=tree_items(st)[-3:])
        r = menu_retry(["Edit", "Undo"], tries=6, wait=5); log("undo_menu", r=r)
        time.sleep(1.5)
        await call(s, "query_tree_summary", {"doc": H}, log)
        st = snap(); log("tree_after_undo", t=tree_items(st)[-3:])
asyncio.run(main())
