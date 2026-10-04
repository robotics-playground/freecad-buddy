from tc14lib import *


async def body(m, log):
    caps = await m.call("query_capabilities", {})
    log.check("Given query_capabilities OK", caps.get("status") == "OK", caps.get("status"))
    o = await m.call("document_open", {"path": BOX})
    good = sc(o).get("doc")
    log.note(f"show all: {menu(['View', 'Visibility', 'Show All Objects'])}")
    f = await m.call("view_fit_viewport", {"doc": good})
    log.check("Given good doc open and fitted OK", o.get("status") == "OK" and f.get("status") == "OK", f.get("text"))
    o2 = await m.call("document_open", {"path": f"{GOLDEN}/cylinder-r5-h20.FCStd"})
    stale = sc(o2).get("doc")
    c2 = await m.call("document_close", {"doc": stale})
    log.note(f"stale handle {stale}: open {o2.get('status')} close {c2.get('status')}")
    r1 = await m.call("view_fit_viewport", {"doc": "no-such-handle"})
    r2 = await m.call("view_fit_viewport", {"doc": stale})
    r3 = await m.call("view_fit_viewport", {})
    for name, r in (("unknown", r1), ("stale", r2), ("missing", r3)):
        log.note(f"{name}: {r.get('status')} {json.dumps(r.get('detail') or r.get('_raw'))[:300]}")
    m1 = (r1.get("detail") or {}).get("message", "")
    m2 = (r2.get("detail") or {}).get("message", "")
    m3 = r3.get("_raw") or json.dumps(r3)
    log.check("Then unknown handle INVALID_INPUT", r1.get("status") == "INVALID_INPUT", r1.get("status"))
    log.check("Then message names no-such-handle", "no-such-handle" in m1, m1)
    log.check("Then stale handle INVALID_INPUT", r2.get("status") == "INVALID_INPUT", r2.get("status"))
    log.check("Then missing doc is schema reject", "validation error" in m3.lower() and "doc" in m3, m3[:200])
    no_vp = all(("viewport" not in x.lower() and "3d view" not in x.lower()) for x in (m1, m2, m3))
    log.check("Then no message mentions viewport / 3D view", no_vp, [m1, m2, m3[:150]])
    f2 = await m.call("view_fit_viewport", {"doc": good})
    log.check("Then fit good handle OK", f2.get("status") == "OK", f2.get("text"))
    pid, _ = ids()
    log.note(f"windows after: {[w['title'] for w in cua('list_windows', {'pid': pid}).get('windows', [])]}")
    shot("tc-14-07-after.png")
    print("GOOD", good)


go("tc-14-07", body)
