import asyncio, json, shutil
from tclib import *
log = Log("tc-13-06.jsonl")
H = json.load(open("cur.json"))["h"]
def save_png(env, name):
    link = (sc(env).get("render") or {}).get("resource_link")
    if link: shutil.copy(link, EVIDENCE / name)
    log("render_saved", name=name, link=link)
async def main():
    async with mcp_session() as s:
        await call(s, "query_tree_summary", {"doc": H}, log)
        await call(s, "query_mass_properties", {"doc": H, "object": "BoxHole"}, log)
        st = snap(); sv = elements(st, role="Button", label="Standard Views"); log("stdviews_btn", n=len(sv), frame=[e.get("frame") for e in sv])
        log("iso", r=slim(click_label("Button", "Standard Views"))); time.sleep(1)
        snap("tc-13-06-menu.png")
        log("fitall", r=slim(fitall())); time.sleep(1.5)
        q = await call(s, "query_screenshot", {"doc": H, "view": {"camera": "iso", "include": ["BoxHole"]}}, log)
        save_png(q, "tc-13-06-mcp.png")
        snap("tc-13-06-viewport.png")
        await call(s, "query_mass_properties", {"doc": H, "object": "BoxHole"}, log)
        await call(s, "verify_recompute", {"doc": H}, log)
        f = await call(s, "view_fit_viewport", {"doc": H}, log); time.sleep(1)
        snap("tc-13-06-after.png")
asyncio.run(main())
