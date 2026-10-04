import asyncio, json
from tclib import *
log = Log("tc-13-05.jsonl")
H = json.load(open("cur.json"))["h"]
async def main():
    async with mcp_session() as s:
        await call(s, "query_tree_summary", {"doc": H}, log)
        await call(s, "query_placement", {"doc": H, "object": "BoxHole"}, log)
        await call(s, "query_mass_properties", {"doc": H, "object": "BoxHole"}, log)
        r = click_label("TreeItem", "BoxHole"); log("click_row", r=slim(r)); time.sleep(1)
        st = snap(); sel = [(e["label"], e.get("selected")) for e in elements(st, role="TreeItem") if e["label"] == "BoxHole"]
        log("sel_after_rowclick", sel=sel)
        if not any(x[1] for x in sel):
            log("selectall", r=menu(["Edit", "Select All"])); time.sleep(1)
        log("datatab", r=slim(click_label("TabItem", "Data"))); time.sleep(1)
        st = snap("tc-13-05-props.png")
        items = [e["label"] for e in elements(st, role="TreeItem")]
        log("prop_rows", items=items)
        await call(s, "view_fit_viewport", {"doc": H}, log); time.sleep(1)
        snap("tc-13-05-after.png")
asyncio.run(main())
