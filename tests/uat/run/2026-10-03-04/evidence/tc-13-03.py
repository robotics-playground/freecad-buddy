import asyncio, json, sys, base64, shutil
from tclib import *
log = Log("tc-13-03.jsonl")
H = json.load(open("cur.json"))["h"]
def save_png(env, name):
    s = sc(env); r = s.get("render") or {}
    link = r.get("resource_link") or s.get("resource_link")
    log("render_link", name=name, link=link)
    if isinstance(link, dict): link = link.get("uri") or link.get("path")
    if link and isinstance(link, str):
        p = link.replace("file:///", "").replace("file://", "")
        try: shutil.copy(p, EVIDENCE / name); return True
        except Exception as e: log("copy_fail", e=str(e))
    return False
async def main():
    async with mcp_session() as s:
        t1 = await call(s, "query_tree_summary", {"doc": H}, log)
        q1 = await call(s, "query_screenshot", {"doc": H}, log)
        m1 = await call(s, "query_mass_properties", {"doc": H, "object": "Box"}, log)
        qi = await call(s, "query_screenshot", {"doc": H, "view": {"include": ["Box"]}}, log)
        save_png(qi, "tc-13-03-mcp-include-hidden.png")
        log("gui_fit_before", r=slim(fitall())); time.sleep(1)
        st = snap("tc-13-03-hidden.png")
        log("menu_selectall", r=menu(["Edit", "Select All"]))
        time.sleep(1)
        st = snap()
        log("sel", items=[(e["label"], e.get("selected")) for e in elements(st, role="TreeItem") if e["label"] in ("box-10-20-30","Box")])
        for path in (["View","Visibility","Toggle visibility"], ["View","Visibility","Toggle Visibility"]):
            r = menu(path); log("menu_toggle", path=path, r=r)
            if r.get("status") != "refused": break
        time.sleep(1.5)
        t2 = await call(s, "query_tree_summary", {"doc": H}, log)
        q2 = await call(s, "query_screenshot", {"doc": H}, log)
        save_png(q2, "tc-13-03-mcp-visible.png")
        m2 = await call(s, "query_mass_properties", {"doc": H, "object": "Box"}, log)
        st = snap("tc-13-03-visible.png")
        f = await call(s, "view_fit_viewport", {"doc": H}, log)
        time.sleep(1)
        snap("tc-13-03-after.png")
asyncio.run(main())
