"""TC-06-05: focus and highlight. Reuses the TC0604 two-box document (PadA 20x10x10 front, PadB 30x10x20 behind)."""
import time
from tc06lib import *


async def body(m, log):
    docs = sc(await m.call("document_list", {})).get("documents") or []
    doc = [d["doc"] for d in docs if d["label"] == "TC0604"][0]
    vs = await m.call("verify_shape", {"doc": doc, "object": "PadA"})
    log.check("Given: verify_shape reports a face count", "face" in json.dumps(sc(vs)).lower(), json.dumps(sc(vs).get("checks"))[:400])
    r0, u = await render(m, doc, {"camera": "iso"}, "tc-06-05-unfocused.png")
    r1, f = await render(m, doc, {"camera": "iso", "focus": {"object": "PadA", "element_type": "face", "index": 0}}, "tc-06-05-focus-face0.png")
    r2, h = await render(m, doc, {"camera": "iso", "highlight": {"object": "PadA"}}, "tc-06-05-highlight.png")
    r3, _ = await render(m, doc, {"focus": {"object": "PadA", "element_type": "face", "index": 9999}}, "tc-06-05-focus-9999.png")
    r4 = await m.call("query_screenshot", {"doc": doc, "view": {"focus": {"object": "PadA", "element_type": "face"}}})
    r5 = await m.call("query_screenshot", {"doc": doc, "view": {"focus": {"object": "PadA", "mapped_name": "Face1", "element_type": "face", "index": 0}}})
    su, sf = png_stats(u), png_stats(f)
    log.check("focus frames tighter (fill fraction grows)", sf["fill"] > su["fill"], {"unfocused": su, "focused": sf})
    log.check("focus echo == {object:PadA, element_type:face, index:0}", (sc(r1).get("scene") or {}).get("focused_on") == {"object": "PadA", "element_type": "face", "index": 0}, (sc(r1).get("scene") or {}).get("focused_on"))
    log.check("out-of-range index: OK, focused_on == {object:PadA} only", r3.get("status") == "OK" and (sc(r3).get("scene") or {}).get("focused_on") == {"object": "PadA"}, {"status": r3.get("status"), "focused_on": (sc(r3).get("scene") or {}).get("focused_on")})
    log.check("partial selector -> INVALID_INPUT 'sub-element selector requires both element_type and index'",
              r4.get("status") == "INVALID_INPUT" and "sub-element selector requires both element_type and index" in detail_text(r4), short(r4, 200))
    log.check("mixed selector -> INVALID_INPUT 'selector cannot carry both mapped_name and element_type/index'",
              r5.get("status") == "INVALID_INPUT" and "selector cannot carry both mapped_name and element_type/index" in detail_text(r5), short(r5, 200))
    fit = await m.call("view_fit_viewport", {"doc": doc})
    log.check("visual: view_fit_viewport returns OK", fit.get("status") == "OK", short(fit, 300))
    time.sleep(1.0)
    log.note(f"after shot: {shot('tc-06-05-after.png')}")

go("tc-06-05", body)
