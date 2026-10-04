from tc08lib import *  # noqa
import subprocess


async def body(m, log):
    ns = subprocess.run("netstat -ano", shell=True, capture_output=True, text=True).stdout
    listen = [l.strip() for l in ns.splitlines() if "127.0.0.1:8765" in l and "LISTENING" in l]
    log.check("P1 :8765 LISTENING", bool(listen), listen)
    cap = await m.call("query_capabilities", {})
    s = sc(cap)
    log.check("P2 query_capabilities reports auto_approve:false (literal field)", "auto_approve" in s and s.get("auto_approve") is False,
              f"auto_approve key present={('auto_approve' in s)} keys={sorted(s)}")
    doc = sc(await m.call("document_create", {"label": "PostureProbe"})).get("doc")
    r = await m.call("feature_body_create", {"doc": doc, "name": "Body"})
    log.check("P2b posture probe: no-confirm feature_body_create fails closed (not auto-approve)",
              r.get("status") != "OK" and "requires a confirm" in msg(r), short(r))
    await m.call("document_close", {"doc": doc})
    gold = "D:/Work/Personal/Sources/freecad-buddy/benchmarks/g0/golden-models/box-10-20-30.FCStd"
    log.check("P3 golden box present", os.path.exists(gold), gold)
    log.check("P4 no stale preview TempDocs (excluding pre-run 2026-09-22 dir)", prev_dirs() == [], prev_dirs())
    log.note(f"$TEMP holds pre-existing {STALE_PREV} dated 2026-09-22 15:57 (before this run); listing it is Permission denied")
    pid, win = ids()
    st = cua("get_window_state", {"pid": pid, "window_id": win, "include_screenshot": False})
    tm = st.get("tree_markdown") or ""
    log.check("P5 get_window_state returns QOpenGLWidget", "QOpenGLWidget" in tm or "OpenGL" in tm,
              [l for l in tm.splitlines() if "OpenGL" in l][:2])
    fa = [e for e in st.get("elements", []) if e.get("role") == "Button" and e.get("label") == "Fit All"]
    log.check("P6 Fit All toolbar button with element_token", bool(fa and fa[0].get("element_token")), fa[:1])
    log.check("P7 evidence dir writable", os.access(str(EVIDENCE), os.W_OK), str(EVIDENCE))


go("tc-08-00", body)
