"""TC-06-10 main path: BoxPad marked Touched via FreeCAD's tree context menu 'Mark to Recompute' (cua-driver); no bridge call in between."""
import os, time
from tc06lib import *


async def body(m, log):
    docs = sc(await m.call("document_list", {})).get("documents") or []
    doc = [d["doc"] for d in docs if d["label"] == "TC0610"][0]
    r1, p1 = await render(m, doc, {"camera": "iso"}, "tc-06-10-dirty.png")
    rd = sc(r1).get("render") or {}
    log.check("dirty render status OK (not SPEC_FAILED/INVALID_INPUT)", r1.get("status") == "OK", short(r1, 300))
    log.check("dirty render dirty_document true", rd.get("dirty_document") is True, rd)
    log.check("dirty render: link non-null and PNG > 0 bytes", bool(link(r1)) and bool(p1) and os.path.getsize(p1) > 0, os.path.getsize(p1) if p1 else None)
    log.check("dirty render text contains 'Document dirty (pending/broken recompute)'", "Document dirty (pending/broken recompute)" in (r1.get("text") or ""), (r1.get("text") or "")[:120])
    log.check("guard-skip signal lives in structured_content.render.dirty_document", "dirty_document" in rd, sorted(rd.keys()))
    vr = await m.call("verify_recompute", {"doc": doc})
    log.note("verify_recompute AFTER the dirty render (it recomputes itself, verify.py:411): " + json.dumps(sc(vr))[:300])
    rc = await m.call("document_recompute", {"doc": doc})
    log.note("document_recompute: " + short(rc, 300))
    r2, p2 = await render(m, doc, {"camera": "iso"}, "tc-06-10-recomputed.png")
    log.check("post-recompute render dirty_document false", (sc(r2).get("render") or {}).get("dirty_document") is False, sc(r2).get("render"))
    log.check("dirty render rendered_objects == post-recompute list", objs(r1) == objs(r2), {"dirty": objs(r1), "clean": objs(r2)})
    mp = await m.call("query_mass_properties", {"doc": doc, "object": "BoxPad"})
    log.note(f"BoxPad volume after recompute: {sc(mp).get('volume')}")
    print(click_button("Standard Views"))
    fit = await m.call("view_fit_viewport", {"doc": doc})
    log.check("visual: view_fit_viewport returns OK", fit.get("status") == "OK", short(fit, 300))
    time.sleep(1.0)
    log.note(f"after shot: {shot('tc-06-10-after.png')}")

go("tc-06-10e", body)
