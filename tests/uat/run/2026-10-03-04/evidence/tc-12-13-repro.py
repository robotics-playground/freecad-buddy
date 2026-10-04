import asyncio, json
from tclib import *
log = Log("tc-12-13-repro.jsonl")
async def main():
    async with mcp_session() as s:
        a = await call(s, "document_open", {"path": GOLD + "box-10-20-30.FCStd"}, log); A = sc(a)["doc"]
        time.sleep(1)
        r = menu_retry(["File", "Close"], tries=10, wait=6); log("menu_close", r=r); time.sleep(2)
        await call(s, "query_tree_summary", {"doc": A}, log)
        await call(s, "query_mass_properties", {"doc": A, "object": "Box"}, log)
        await call(s, "document_list", {}, log)
        await call(s, "query_tree_summary", {"doc": A}, log)
        await call(s, "query_mass_properties", {"doc": A, "object": "Box"}, log)
        await call(s, "document_close", {"doc": A}, log)
asyncio.run(main())
