import asyncio, json
from tclib import *
log = Log("tc-13-05c.jsonl")
H = json.load(open("cur.json"))["h"]
async def main():
    async with mcp_session() as s:
        # harness workaround: the include render (F13-1) makes BoxHole visible so a viewport click can select it
        await call(s, "query_screenshot", {"doc": H, "view": {"include": ["BoxHole"]}}, log)
        await call(s, "view_fit_viewport", {"doc": H}, log); time.sleep(1)
        pid, win = ids()
        log("select_click", r=cua("click", {"pid": pid, "window_id": win, "x": 700, "y": 640})); time.sleep(1)
        log("datatab", r=slim(click_label("TabItem", "Data"))); time.sleep(1)
        st = snap("tc-13-05-props.png")
        items = [e["label"] for e in elements(st, role="TreeItem")]
        log("prop_rows", items=items[:12])
        await call(s, "query_placement", {"doc": H, "object": "BoxHole"}, log)
        await call(s, "query_mass_properties", {"doc": H, "object": "BoxHole"}, log)
        snap("tc-13-05-after.png")
asyncio.run(main())
