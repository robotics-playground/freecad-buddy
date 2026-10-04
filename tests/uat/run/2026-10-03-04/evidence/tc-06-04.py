"""TC-06-04: styles transparency and color. Fixture: PadA 20x10x10 at y 0..10 (front), PadB 30x10x20 at x -5..25, y 20..30 (behind)."""
import time
from tc06lib import *


async def mkbody(m, doc, body, sketch, pad, x0, y0, w, h, length):
    await apply(m, doc, "feature_body_create", {"name": body})
    await apply(m, doc, "sketch_create", {"name": sketch, "body": body, "plane": "XY"})
    g, c = rect_profile(x0, y0, w, h)
    await apply(m, doc, "sketch_add_geometry", {"sketch": sketch, "geometry": g, "constraints": c})
    _, p = await apply(m, doc, "feature_pad", {"body": body, "profile": sketch, "name": pad, "length": q(length)})
    return p


async def body(m, log):
    await close_all(m, log)
    doc = sc(await m.call("document_create", {"label": "TC0604"})).get("doc")
    pa = await mkbody(m, doc, "BodyA", "SketchA", "PadA", 0, 0, 20, 10, 10)
    pb = await mkbody(m, doc, "BodyB", "SketchB", "PadB", -5, 20, 30, 10, 20)
    log.check("fixture: PadA and PadB committed", pa.get("status") == "OK" and pb.get("status") == "OK", short(pa) + short(pb))
    ts = await m.call("query_tree_summary", {"doc": doc, "depth": 2})
    t = json.dumps(sc(ts))
    log.check("Given: tree names PadA and PadB", '"PadA"' in t and '"PadB"' in t, "")
    fit = await m.call("view_fit_viewport", {"doc": doc})
    log.check("visual: view_fit_viewport returns OK (before the before.png)", fit.get("status") == "OK", short(fit, 500))
    time.sleep(1.0)
    log.note(f"before shot: {shot('tc-06-04-before.png')}")
    r1, _ = await render(m, doc, {"camera": "front", "styles": [{"object": "PadA", "color": [1.0, 0.0, 0.0]}]}, "tc-06-04-red.png")
    r2, _ = await render(m, doc, {"camera": "front", "styles": [{"object": "PadA", "color": [1.0, 0.0, 0.0], "transparency": 80}]}, "tc-06-04-red-t80.png")
    log.check("red render OK", r1.get("status") == "OK", short(r1))
    log.check("red t80 render OK", r2.get("status") == "OK", short(r2))
    time.sleep(0.5)
    log.note(f"styled viewport shot: {shot('tc-06-04-styled.png')}")
    r3 = await m.call("query_screenshot", {"doc": doc, "view": {"styles": [{"object": "PadA", "transparency": 150}]}})
    log.check("transparency 150 rejected (schema maximum 100)", r3.get("_isError") and "150" in json.dumps(r3) or r3.get("status") == "INVALID_INPUT", short(r3, 300))
    r4 = await m.call("query_screenshot", {"doc": doc, "view": {"styles": [{"object": "PadA", "color": [1.0, 0.0]}]}})
    log.check("two-element color rejected (schema minItems 3)", r4.get("_isError") and "short" in json.dumps(r4) or r4.get("status") == "INVALID_INPUT", short(r4, 300))
    r5, _ = await render(m, doc, {"styles": [{"object": "PadA", "transparency": 0}]}, "tc-06-04-t0.png")
    r6, _ = await render(m, doc, {"styles": [{"object": "PadA", "transparency": 100}]}, "tc-06-04-t100.png")
    log.check("transparency 0 and 100 both OK", r5.get("status") == "OK" and r6.get("status") == "OK", short(r5) + short(r6))
    r7 = await m.call("query_screenshot", {"doc": doc, "view": {"styles": [{"object": "NoSuchObject", "color": [0, 0, 1]}]}})
    log.check("style on NoSuchObject -> INVALID_INPUT 'unknown object: NoSuchObject'",
              r7.get("status") == "INVALID_INPUT" and "unknown object: NoSuchObject" in detail_text(r7), short(r7, 200))
    fit = await m.call("view_fit_viewport", {"doc": doc})
    log.check("visual: view_fit_viewport returns OK (before after.png)", fit.get("status") == "OK", short(fit, 300))
    time.sleep(1.0)
    log.note(f"after shot: {shot('tc-06-04-after.png')}")

go("tc-06-04", body)
