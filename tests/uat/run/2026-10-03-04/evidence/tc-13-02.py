import asyncio, json
from tclib import *
log = Log("tc-13-02.jsonl")
H = json.load(open("cur.json"))["h"]
async def main():
    async with mcp_session() as s:
        await call(s, "query_tree_summary", {"doc": H}, log)
        await call(s, "query_object", {"doc": H, "object": "BoxHole"}, log)
        await call(s, "query_mass_properties", {"doc": H, "object": "BoxHole"}, log)
        st = snap()
        log("gui_status_elems", sb=[(e.get("role"), e.get("label")) for e in st["elements"] if e.get("role") in ("StatusBar",)])
        r = click_label("TreeItem", "BoxHole")
        log("click_boxhole", r=slim(r))
        time.sleep(1)
        st = snap("tc-13-02-selected.png")
        sel = elements(st, role="TreeItem")
        log("gui_after_select", treeitems=[(e.get("label"), e.get("selected"), e.get("states")) for e in sel],
            statusbar=[e for e in st["elements"] if e.get("role")=="StatusBar"][:3],
            props=[e.get("label") for e in st["elements"] if e.get("role") in ("TreeItem","Text","Edit") and e.get("label")][:80])
        await call(s, "query_mass_properties", {"doc": H, "object": "BoxHole"}, log)
asyncio.run(main())
