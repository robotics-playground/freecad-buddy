import os, subprocess
from tc05lib import *


async def body(m, log):
    ns = subprocess.run(["netstat", "-ano"], capture_output=True, text=True).stdout
    log.check(":8765 LISTENING", any("127.0.0.1:8765" in l and "LISTENING" in l for l in ns.splitlines()), "")
    log.check("golden box present", os.path.exists("D:/Work/Personal/Sources/freecad-buddy/benchmarks/g0/golden-models/box-10-20-30.FCStd"), "")
    cap = await m.call("query_capabilities", {})
    s = sc(cap)
    log.note(f"query_capabilities keys={sorted(s)}; auto_approve field present={'auto_approve' in s}")
    d = sc(await m.call("document_create", {"label": "Posture"})).get("doc")
    unconfirmed = await m.call("feature_body_create", {"doc": d, "name": "Body"})
    log.check("host NOT auto-approve: mutation without confirm is refused", unconfirmed.get("status") != "OK", short(unconfirmed))
    await m.call("document_close", {"doc": d})
    temp = os.environ.get("TEMP")
    stale = sorted(p for p in os.listdir(temp) if p.startswith("FCB_TMP_snap_"))
    log.note(f"$TEMP FCB_TMP_snap_* count={len(stale)} (pre-existing, dated 2026-09-22, not from this run): {stale[:3]}...")
    wd = [p for p in os.listdir("C:/Users/thuan/freecad-buddy-workdir/tmp") if p.startswith("FCB_TMP_snap_")]
    log.check("bridge workdir tmp free of FCB_TMP_snap_*", wd == [], wd)
    pid, win = ids()
    st = cua("get_window_state", {"pid": pid, "window_id": win, "include_screenshot": False})
    tree = st.get("tree_markdown") or ""
    log.check("cua-driver get_window_state reaches FreeCAD window", bool(st.get("elements")), f"elements={len(st.get('elements', []))}")
    log.note(f"QOpenGLWidget in tree: {'QOpenGLWidget' in tree} (no 3D view open on Start page)")


go("tc-05-00", body)
