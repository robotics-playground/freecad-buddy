"""TC-06-10 fallback fixture: the literal When cannot run (golden Box is a static Part::Feature with no Length).
Build a parametric 10x20x30 PartDesign block (BoxBody/BoxProfile/BoxPad) for the dirty-state path."""
from tc06lib import *


async def body(m, log):
    await close_all(m, log)
    doc = sc(await m.call("document_create", {"label": "TC0610"})).get("doc")
    await apply(m, doc, "feature_body_create", {"name": "BoxBody"})
    await apply(m, doc, "sketch_create", {"name": "BoxProfile", "body": "BoxBody", "plane": "XY"})
    g, c = rect_profile(0, 0, 10, 20)
    await apply(m, doc, "sketch_add_geometry", {"sketch": "BoxProfile", "geometry": g, "constraints": c})
    _, p = await apply(m, doc, "feature_pad", {"body": "BoxBody", "profile": "BoxProfile", "name": "BoxPad", "length": q(30)})
    log.check("fixture BoxPad 10x20x30 committed", p.get("status") == "OK", short(p))
    r0, _ = await render(m, doc, None, "tc-06-10-clean2.png")
    log.check("Given: clean render dirty_document false", (sc(r0).get("render") or {}).get("dirty_document") is False, sc(r0).get("render"))
    log.note(f"doc={doc}")

go("tc-06-10b", body)
