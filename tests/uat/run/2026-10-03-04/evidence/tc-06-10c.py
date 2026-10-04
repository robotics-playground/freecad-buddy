"""TC-06-10 main path on the parametric block: BoxPad Length set to 25 mm through FreeCAD's property editor (cua-driver), no recompute."""
import os, time
from tc06lib import *


async def body(m, log):
    docs = sc(await m.call("document_list", {})).get("documents") or []
    doc = [d["doc"] for d in docs if d["label"] == "TC0610"][0]
    vr = await m.call("verify_recompute", {"doc": doc})
    log.note("verify_recompute (dirty?): " + json.dumps(sc(vr))[:500])
    ob = await m.call("query_object", {"doc": doc, "object": "BoxPad"})
    props = sc(ob).get("properties") or {}
    log.note("BoxPad Length/State: " + json.dumps({k: props.get(k) for k in ("Length", "State")}))
    r1, p1 = await render(m, doc, {"camera": "iso"}, "tc-06-10-dirty.png")
    rd = sc(r1).get("render") or {}
    log.check("dirty render status OK (not SPEC_FAILED/INVALID_INPUT)", r1.get("status") == "OK", short(r1, 300))
    log.check("dirty render dirty_document true", rd.get("dirty_document") is True, rd)
    log.check("dirty render: link non-null and PNG > 0 bytes", bool(link(r1)) and p1 and os.path.getsize(p1) > 0, os.path.getsize(p1) if p1 else None)
    log.check("dirty render text contains 'Document dirty (pending/broken recompute)'", "Document dirty (pending/broken recompute)" in (r1.get("text") or ""), (r1.get("text") or "")[:120])
    log.check("dirty_document present in structured_content.render", "dirty_document" in rd, sorted(rd.keys()))
    rc = await m.call("document_recompute", {"doc": doc})
    log.note("document_recompute: " + short(rc, 300))
    r2, p2 = await render(m, doc, {"camera": "iso"}, "tc-06-10-recomputed.png")
    log.check("post-recompute render dirty_document false", (sc(r2).get("render") or {}).get("dirty_document") is False, sc(r2).get("render"))
    log.check("dirty render rendered_objects == post-recompute list", objs(r1) == objs(r2), {"dirty": objs(r1), "clean": objs(r2)})
    mp = await m.call("query_mass_properties", {"doc": doc, "object": "BoxPad"})
    log.note(f"BoxPad volume after recompute (expect 10*20*25=5000): {sc(mp).get('volume')}")
    print(click_button("Standard Views"))
    fit = await m.call("view_fit_viewport", {"doc": doc})
    log.check("visual: view_fit_viewport returns OK", fit.get("status") == "OK", short(fit, 300))
    time.sleep(1.0)
    log.note(f"after shot: {shot('tc-06-10-after.png')}")

go("tc-06-10c", body)
