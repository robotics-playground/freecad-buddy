import asyncio, json, shutil
from tclib import *
log = Log("tc-13-03b.jsonl")
H = json.load(open("cur.json"))["h"]
def save_png(env, name):
    link = (sc(env).get("render") or {}).get("resource_link")
    if link: shutil.copy(link, EVIDENCE / name)
    log("render_saved", name=name, link=link)
async def main():
    async with mcp_session() as s:
        await call(s, "query_tree_summary", {"doc": H}, log)
        q2 = await call(s, "query_screenshot", {"doc": H}, log); save_png(q2, "tc-13-03-mcp-visible.png")
        await call(s, "query_mass_properties", {"doc": H, "object": "Box"}, log)
        snap("tc-13-03-visible.png")
        await call(s, "view_fit_viewport", {"doc": H}, log)
        time.sleep(1)
        snap("tc-13-03-after.png")
        # cleanup: hide again through GUI
        st = snap(); log("sel", items=[(e["label"], e.get("selected")) for e in elements(st, role="TreeItem")][-3:])
        log("menu_hide", r=menu(["View", "Visibility", "Hide Selection"]))
        time.sleep(1.5)
        await call(s, "query_tree_summary", {"doc": H}, log)
        snap("tc-13-03-cleanup.png")
asyncio.run(main())
