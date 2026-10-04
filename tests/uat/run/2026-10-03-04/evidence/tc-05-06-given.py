from tc05lib import *


async def body(m, log):
    await close_all(m, log)
    doc = await body_sketch(m, "TC0506", pad=30)
    p, f = await apply(m, doc, "feature_fillet", {"body": "Body", "base": "Pad", "name": "Fillet", "edges": [sel("Pad", "Edge1")], "radius": q(2)})
    log.note(f"Fillet r2 on Pad.Edge1 -> {short(f)}")
    chosen = None
    for n in (6, 7, 5, 8, 1, 2, 3, 4):
        pr, s = await apply(m, doc, "sketch_create", {"name": "Sketch001", "body": "Body", "face": sel("Fillet", f"Face{n}")})
        if s.get("status") != "OK":
            log.note(f"sketch_create on Fillet.Face{n} -> {short(s)}")
            continue
        pl = await m.call("query_placement", {"doc": doc, "object": "Sketch001"})
        log.note(f"Sketch001 on Fillet.Face{n}: placement={json.dumps(sc(pl))[:400]}")
        txt = json.dumps(sc(pl))
        top = '30.0' in txt
        if top:
            chosen = n
            break
        u = await m.call("document_undo", {"doc": doc})
        log.note(f"not the top face; document_undo -> {short(u)}")
    log.check("Sketch001 attached to the Fillet's top (z=30) face", chosen is not None, chosen)
    g, c = rect_profile(5, 5, 5, 5)
    pr, a = await apply(m, doc, "sketch_add_geometry", {"sketch": "Sketch001", "geometry": g, "constraints": c})
    log.note(f"Sketch001 5x5 square at (5,5) -> {short(a)}")
    dep = await m.call("query_dependencies", {"doc": doc})
    log.write({"deps": sc(dep)})
    txt = json.dumps(sc(dep))
    log.note(f"query_dependencies: {txt[:800]}")
    log.write({"doc": doc})


go("tc-05-06-given", body)
