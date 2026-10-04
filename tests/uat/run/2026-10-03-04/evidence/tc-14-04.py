from tc14lib import *


async def body(m, log):
    created = await m.call("document_create", {"label": "tc14bar"})
    h = sc(created).get("doc")
    log.check("Given document_create tc14bar OK", created.get("status") == "OK", h)
    built = await m.bar(h)
    log.note(f"bar build statuses {built}")
    mp = await m.call("query_mass_properties", {"doc": h, "object": "Body"})
    log.check("Given bar volume 1280000.0 within 0.1%", abs(float(vol(mp) or 0) - 1280000.0) <= 1280.0, vol(mp))
    pre = await m.call("query_tree_summary", {"doc": h})
    log.note(f"pre-fit framing {fr(pre)}")
    fit = await m.call("view_fit_viewport", {"doc": h})
    log.note(f"fit {fit.get('status')} {sc(fit)} {fr(fit)}")
    tree = await m.call("query_tree_summary", {"doc": h})
    f = fr(tree)
    log.check("Then framing.fits true after single fit", f.get("fits") is True, f)
    log.check("Then framing.ratio >= 0.85", isinstance(f.get("ratio"), float) and f["ratio"] >= 0.85, f.get("ratio"))
    log.check("Then no overshoot: fits true (ratio <= 1.0)", f.get("fits") is True and f.get("ratio", 9) <= 1.0, f)
    log.write({"handle": h})
    print("HANDLE", h)
    shot("tc-14-04-after.png")


go("tc-14-04", body)
