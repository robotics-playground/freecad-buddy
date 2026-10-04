"""TC-06-03: include and exclude select the right objects. Fixture: BodyA/PadA 20x20x10 at origin, BodyB/PadB 20x10x15 at x=30."""
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
    doc = sc(await m.call("document_create", {"label": "TC0603"})).get("doc")
    pa = await mkbody(m, doc, "BodyA", "SketchA", "PadA", 0, 0, 20, 20, 10)
    pb = await mkbody(m, doc, "BodyB", "SketchB", "PadB", 30, 0, 20, 10, 15)
    log.check("fixture: PadA and PadB committed", pa.get("status") == "OK" and pb.get("status") == "OK", short(pa) + short(pb))
    ts = await m.call("query_tree_summary", {"doc": doc, "depth": 2})
    t = json.dumps(sc(ts))
    log.check("Given: tree depth 2 lists PadA, PadB and a Body", all(n in t for n in ('"PadA"', '"PadB"', '"BodyA"')), "")
    r1, _ = await render(m, doc, None, "tc-06-03-default.png")
    r2, _ = await render(m, doc, {"include": ["PadA"]}, "tc-06-03-includeA.png")
    r3, _ = await render(m, doc, {"exclude": ["PadA"]}, "tc-06-03-excludeA.png")
    r4 = await m.call("query_screenshot", {"doc": doc, "view": {"include": ["NoSuchObject"]}})
    o1 = objs(r1) or []
    log.check("default skips containers/sketches/datums", not any(n.startswith(("Body", "Sketch", "Origin", "X_Axis", "Y_Axis", "Z_Axis", "XY_Plane", "XZ_Plane", "YZ_Plane")) for n in o1), o1)
    log.check("include is the exact set ['PadA']", objs(r2) == ["PadA"], objs(r2))
    log.check("exclude removes exactly PadA", objs(r3) == [n for n in o1 if n != "PadA"], {"exclude": objs(r3), "default": o1})
    log.check("unknown include -> INVALID_INPUT 'unknown object: NoSuchObject'",
              r4.get("status") == "INVALID_INPUT" and "unknown object: NoSuchObject" in detail_text(r4), short(r4, 400))
    r5, _ = await render(m, doc, {"include": ["BodyA"]}, "tc-06-03-includeBodyA.png")
    log.check("explicit include of BodyA renders it", r5.get("status") == "OK" and "BodyA" in (objs(r5) or []), {"status": r5.get("status"), "objs": objs(r5), "detail": detail_text(r5)[:300]})
    pid, win = ids()
    fit = await m.call("view_fit_viewport", {"doc": doc})
    log.check("visual: view_fit_viewport returns OK", fit.get("status") == "OK", short(fit, 500))
    time.sleep(1.0)
    log.note(f"after shot: {shot('tc-06-03-after.png')}")

go("tc-06-03", body)
