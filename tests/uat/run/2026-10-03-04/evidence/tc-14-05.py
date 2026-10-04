import os, re, shutil, subprocess
from tc14lib import *

H = "fcb-doc:vw4fHzI2S8155WdMTRV6_g"
CFG = os.path.join(os.environ["APPDATA"], "FreeCAD", "v1-1", "user.cfg")


def anim_pref():
    text = open(CFG, encoding="utf-8").read()
    m = re.search(r'<FCBool Name="UseNavigationAnimations" Value="(\d)"/>', text)
    return m.group(1) if m else None


async def body(m, log):
    mp = await m.call("query_mass_properties", {"doc": H, "object": "Body"})
    log.check("Given bar volume 1280000 within 0.1%", abs(float(vol(mp) or 0) - 1280000.0) <= 1280.0, vol(mp))
    pid, win = ids()
    lw = cua("list_windows", {"pid": pid})
    log.check("Given list_windows returns pid/window", any(w["window_id"] == win for w in lw.get("windows", [])), win)
    pre = await m.call("query_tree_summary", {"doc": H})
    log.check("Given framing.fits false (camera off part via GUI Trimetric + Zoom In x3)", fr(pre).get("fits") is False, fr(pre))
    before_pref = anim_pref()
    log.note(f"user.cfg UseNavigationAnimations before = {before_pref}")
    shot("tc-14-05-before.png")
    fit = await m.call("view_fit_viewport", {"doc": H})
    log.note(f"fit {fit.get('status')} {sc(fit)} {fr(fit)}")
    shot("tc-14-05-after.png")
    render = await m.call("query_screenshot", {"doc": H})
    log.note(f"query_screenshot {render.get('status')} {json.dumps(sc(render))[:400]}")
    uri = sc(render).get("uri") or sc(render).get("resource_link") or sc(render).get("path")
    if isinstance(uri, dict):
        uri = uri.get("uri")
    if uri:
        path = uri.replace("file:///", "").replace("file://", "")
        if os.path.exists(path):
            shutil.copy(path, f"{EV}/tc-14-05-render.png")
            log.note(f"render copied from {path}")
    after_pref = anim_pref()
    log.note(f"user.cfg UseNavigationAnimations after = {after_pref}")
    same = subprocess.run(["cmp", f"{EV}/tc-14-05-before.png", f"{EV}/tc-14-05-after.png"], capture_output=True, text=True)
    log.check("Then after image differs from before (cmp)", same.returncode != 0, same.stdout.strip())


go("tc-14-05", body)
