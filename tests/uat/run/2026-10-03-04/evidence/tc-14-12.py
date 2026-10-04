from tc14lib import *
from tc08h1 import h1

ERR = f"{EV}/tc-14-12-h1.stderr.log"


def valid(f):
    if f is None:
        return True
    if f.get("fits") not in (True, False, None):
        return False
    if f.get("fits") is None:
        return f.get("checked") == "unavailable" and bool(f.get("stale_reason"))
    return True


async def body(m, log):
    o = await m.call("document_open", {"path": BOX})
    g = sc(o).get("doc")
    log.note(f"show all {menu(['View', 'Visibility', 'Show All Objects'])}")
    log.check("Given GUI document_open OK", o.get("status") == "OK", g)
    async with h1(log, "tc-14-12", ERR) as hh:
        ho = await hh.call("document_open", {"path": BOX})
        hd = sc(ho).get("doc")
        r = await hh.call("query_tree_summary", {"doc": hd})
        keys = sorted(k for k in r if not k.startswith("_"))
        log.note(f"H1 envelope keys {keys}; framing={r.get('framing', '<absent>')!r}; text={r.get('text')!r}")
        log.check("Then H1 envelope has no framing key at all", "framing" not in r, keys)
        log.check("Then H1 text has no Warning:", "Warning:" not in (r.get("text") or ""), r.get("text"))
        h1f = r.get("framing")
        await hh.call("document_close", {"doc": hd})
    q = await m.call("query_tree_summary", {"doc": g})
    log.note(f"GUI framing {q.get('framing', '<absent>')}")
    log.check("Then GUI envelope has framing with checked computed/cached",
              isinstance(q.get("framing"), dict) and q["framing"].get("checked") in ("computed", "cached"), q.get("framing"))
    log.check("Then fits never a guess (both hosts)", valid(h1f) and valid(q.get("framing")), [h1f, q.get("framing")])
    f = await m.call("view_fit_viewport", {"doc": g})
    log.check("Then fit GUI handle OK", f.get("status") == "OK", f.get("text"))
    shot("tc-14-12-after.png")
    print("GUI", g)


go("tc-14-12", body)
