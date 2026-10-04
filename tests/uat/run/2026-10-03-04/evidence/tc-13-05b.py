import asyncio, json
from tclib import *
log = Log("tc-13-05.jsonl")
async def main():
    async with mcp_session() as s:
        o = await call(s, "document_open", {"path": GOLD + "box40-hole-r5.FCStd"}, log); H = sc(o)["doc"]
        json.dump({"h": H}, open("cur.json", "w"))
        time.sleep(1.5)
        st = snap(); row = elements(st, role="TreeItem", label="BoxHole")[0]; log("row", f=row["frame"])
        pid, win = ids()
        # eye icon sits left of the row's icon; screenshot coords are scaled vs UIA frames
        sh = cua("get_window_state", {"pid": pid, "window_id": win, "screenshot_out_file": str(EVIDENCE / "tc-13-05-pre.png").replace("\\", "/")})
        log("scale", w=sh.get("screenshot_width"), h=sh.get("screenshot_height"), sf=sh.get("screenshot_scale_factor"))
        await call(s, "query_tree_summary", {"doc": H}, log)
        await call(s, "query_placement", {"doc": H, "object": "BoxHole"}, log)
        await call(s, "query_mass_properties", {"doc": H, "object": "BoxHole"}, log)
asyncio.run(main())
