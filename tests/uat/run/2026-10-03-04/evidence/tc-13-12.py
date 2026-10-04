import asyncio, json
from tclib import *
log = Log("tc-13-12.jsonl")
H = json.load(open("cur.json"))["h"]
async def main():
    async with mcp_session() as s:
        await call(s, "query_mass_properties", {"doc": H, "object": "Box"}, log)
        await call(s, "query_tree_summary", {"doc": H}, log)
        snap("tc-13-12-mutated.png")
        await call(s, "document_undo", {"doc": H}, log)
        time.sleep(1.5)
        st = snap("tc-13-12-after-undo.png"); log("tree", t=tree_items(st))
        await call(s, "query_mass_properties", {"doc": H, "object": "Box"}, log)
        await call(s, "query_tree_summary", {"doc": H}, log)
        await call(s, "verify_recompute", {"doc": H}, log)
        await call(s, "view_fit_viewport", {"doc": H}, log); time.sleep(1)
        snap("tc-13-12-after.png")
asyncio.run(main())
