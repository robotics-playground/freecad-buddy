import asyncio, json, shutil
from tclib import *
log = Log("tc-13-04.jsonl")
def save_png(env, name):
    link = (sc(env).get("render") or {}).get("resource_link")
    if link: shutil.copy(link, EVIDENCE / name)
    log("render_saved", name=name, link=link)
async def main():
    async with mcp_session() as s:
        o = await call(s, "document_open", {"path": GOLD + "box40-hole-r5.FCStd"}, log)
        H = sc(o)["doc"]; json.dump({"h": H}, open("cur.json", "w"))
        await call(s, "query_tree_summary", {"doc": H}, log)
        await call(s, "query_capabilities", {}, log)
        await call(s, "query_mass_properties", {"doc": H, "object": "BoxHole"}, log)
        await call(s, "verify_shape", {"doc": H, "object": "BoxHole"}, log)
        time.sleep(1)
        log("selectall", r=menu(["Edit", "Select All"])); time.sleep(1)
        log("show", r=menu(["View", "Visibility", "Show Selection"])); time.sleep(1.5)
        await call(s, "query_tree_summary", {"doc": H}, log)
        log("iso", r=slim(click_label("Button", "Standard Views"))); time.sleep(1)
        log("fitall", r=slim(fitall())); time.sleep(1.5)
        snap("tc-13-04-viewport.png")
        q = await call(s, "query_screenshot", {"doc": H, "view": {"camera": "iso", "include": ["BoxHole"]}}, log)
        save_png(q, "tc-13-04-mcp.png")
        await call(s, "view_fit_viewport", {"doc": H}, log)
        time.sleep(1)
        snap("tc-13-04-after.png")
asyncio.run(main())
