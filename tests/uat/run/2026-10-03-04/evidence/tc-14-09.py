from tc14lib import *
from tc08h1 import h1

ERR = f"{EV}/tc-14-09-h1.stderr.log"


async def body(m, log):
    o = await m.call("document_open", {"path": BOX})
    g = sc(o).get("doc")
    log.note(f"show all: {menu(['View', 'Visibility', 'Show All Objects'])}")
    f = await m.call("view_fit_viewport", {"doc": g})
    log.check("Given GUI doc open and fitted OK", f.get("status") == "OK", f.get("text"))
    shot("tc-14-09-before.png")
    async with h1(log, "tc-14-09", ERR) as hh:
        ho = await hh.call("document_open", {"path": BOX})
        hd = sc(ho).get("doc")
        log.note(f"H1 open {ho.get('status')} {hd}")
        r = await hh.call("view_fit_viewport", {"doc": hd})
        log.note(f"H1 fit -> {json.dumps({k: r.get(k) for k in ('status', 'detail', 'structured_content', 'text', 'framing')})}")
        d = r.get("detail") or {}
        log.check("Then status SPEC_FAILED", r.get("status") == "SPEC_FAILED", r.get("status"))
        log.check("Then detail.code view_fit.no_viewport", d.get("code") == "view_fit.no_viewport", d.get("code"))
        sentence = "this host has no live viewport: no camera to fit"
        log.check("Then detail.message exact", d.get("message") == sentence, d.get("message"))
        s = sc(r)
        log.check("Then fitted false and reason same sentence", s.get("fitted") is False and s.get("reason") == sentence, s)
        t = await hh.call("query_tree_summary", {"doc": hd})
        log.check("Then H1 handle still resolves (query_tree_summary OK)", t.get("status") == "OK", t.get("status"))
        await hh.call("document_close", {"doc": hd})
    err = open(ERR, encoding="utf-8", errors="replace").read()
    log.check("Then no traceback in H1 stderr", "Traceback" not in err, f"stderr bytes={len(err)}")
    shot("tc-14-09-after.png")
    print("GUI", g)


go("tc-14-09", body)
