from tc14lib import *


async def body(m, log):
    o = await m.call("document_open", {"path": BOX})
    h = sc(o).get("doc")
    log.note(f"show all: {menu(['View', 'Visibility', 'Show All Objects'])}")
    f = await m.call("view_fit_viewport", {"doc": h})
    log.check("Given open OK and fit OK", o.get("status") == "OK" and f.get("status") == "OK", f.get("text"))
    t0 = await m.call("query_tree_summary", {"doc": h})
    ratio_before = fr(t0).get("ratio")
    log.note(f"ratio_before {fr(t0)}")
    shot("tc-14-08-before.png")
    r1 = await m.call("view_fit_viewport", {"doc": h, "factor": 0.5})
    r2 = await m.call("view_fit_viewport", {"doc": h, "confirm": True})
    for name, r in (("factor", r1), ("confirm", r2)):
        log.note(f"{name}: status={r.get('status')} raw={json.dumps(r.get('detail') or r.get('_raw'))[:300]}")
    log.check("Then unknown key factor rejected as INVALID_INPUT", r1.get("status") == "INVALID_INPUT", r1.get("status") or r1.get("_raw"))
    log.check("Then confirm rejected as INVALID_INPUT", r2.get("status") == "INVALID_INPUT", r2.get("status") or r2.get("_raw"))
    t1 = await m.call("query_tree_summary", {"doc": h})
    log.check("Then ratio unchanged", fr(t1).get("ratio") == ratio_before, f"{fr(t1)} vs {ratio_before}")
    shot("tc-14-08-after.png")
    print("HANDLE", h)


go("tc-14-08", body)
