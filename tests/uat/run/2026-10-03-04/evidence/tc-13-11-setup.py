import asyncio, json
from tclib import *
log = Log("tc-13-11-setup.jsonl")
async def main():
    async with mcp_session() as s:
        c = await call(s, "document_create", {"label": "TC13Box"}, log); H = sc(c)["doc"]
        json.dump({"h": H}, open("cur.json", "w"))
        time.sleep(1)
        st = snap()
        cb = [e for e in elements(st, role="ComboBox") if "Part Design" in (e.get("label") or "") or "Part Design" in str(e.get("value"))]
        log("combos", c=[(e.get("label"), e.get("value"), e.get("element_token")) for e in elements(st, role="ComboBox")])
        if cb:
            pid, _ = ids()
            log("wb", r=cua("set_value", {"pid": pid, "element_token": cb[0]["element_token"], "value": "Part"}))
        time.sleep(2)
        log("cube", r=menu_retry(["Part", "Primitives", "Cube"]))
        time.sleep(2)
        await call(s, "query_tree_summary", {"doc": H}, log)
        snap("tc-13-11-setup.png")
asyncio.run(main())
