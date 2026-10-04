from tc14lib import *

W = ("Warning: the model does not fully fit the live viewport, so the human is seeing only part of it. "
     "Call view_fit_viewport to fit it, if they need to see this change.")


async def body(m, log):
    o = await m.call("document_open", {"path": BOX})
    h = sc(o).get("doc")
    log.note(f"show all {menu(['View', 'Visibility', 'Show All Objects'])}")
    log.note(f"GUI Fit All {click_button('Fit All')}")
    for _ in range(6):
        log.note(f"zoom in {menu(['View', 'Zoom', 'Zoom In'])}")
        g = await m.call("query_tree_summary", {"doc": h})
        if fr(g).get("fits") is False:
            break
    log.check("Given framing.fits false", fr(g).get("fits") is False, fr(g))
    shot("tc-14-11-before.png")
    q1 = await m.call("query_tree_summary", {"doc": h})
    t1 = q1.get("text") or ""
    log.note(f"call1 framing {fr(q1)} text={t1!r}")
    log.check("Then call1 text ends with warning sentence", t1.endswith(W), t1[-200:])
    log.check("Then summary precedes warning separated by blank line",
              t1.endswith("\n\n" + W) and len(t1) > len(W) + 2, t1[:120])
    f = await m.call("view_fit_viewport", {"doc": h})
    q2 = await m.call("query_tree_summary", {"doc": h})
    t2 = q2.get("text") or ""
    log.note(f"fit {f.get('status')}; call2 framing {fr(q2)} text={t2!r}")
    log.check("Then call2 carries no Warning:", "Warning:" not in t2, t2)
    log.check("Then fits:true produces no warning", fr(q2).get("fits") is True and "Warning:" not in t2, fr(q2))
    shot("tc-14-11-after.png")
    # unmeasurable verdict: golden cylinder opens with its object hidden -> nothing visible to measure
    o2 = await m.call("document_open", {"path": f"{GOLDEN}/cylinder-r5-h20.FCStd"})
    h2 = sc(o2).get("doc")
    q3 = await m.call("query_tree_summary", {"doc": h2})
    log.note(f"unavailable doc framing {fr(q3)} text={q3.get('text')!r}")
    log.check("Then checked unavailable earns no warning",
              fr(q3).get("checked") == "unavailable" and fr(q3).get("fits") is None and "Warning:" not in (q3.get("text") or ""),
              fr(q3))
    await m.call("document_close", {"doc": h2})
    print("HANDLE", h)


go("tc-14-11", body)
