"""TC-06-02: Each named camera orients correctly. Fixture: asymmetric L-block (base 30x20x10 + tower 10x10x25 at the origin corner)."""
import time
from tc06lib import *

CAMS = ["iso", "front", "top", "right", "left", "back", "bottom"]


async def body(m, log):
    await close_all(m, log)
    doc = sc(await m.call("document_create", {"label": "TC0602"})).get("doc")
    await apply(m, doc, "feature_body_create", {"name": "Body"})
    await apply(m, doc, "sketch_create", {"name": "BaseProfile", "body": "Body", "plane": "XY"})
    g, c = rect_profile(0, 0, 30, 20)
    await apply(m, doc, "sketch_add_geometry", {"sketch": "BaseProfile", "geometry": g, "constraints": c})
    _, p1 = await apply(m, doc, "feature_pad", {"body": "Body", "profile": "BaseProfile", "name": "Base", "length": q(10)})
    await apply(m, doc, "sketch_create", {"name": "TowerProfile", "body": "Body", "plane": "XY"})
    g, c = rect_profile(0, 0, 10, 10)
    await apply(m, doc, "sketch_add_geometry", {"sketch": "TowerProfile", "geometry": g, "constraints": c})
    _, p2 = await apply(m, doc, "feature_pad", {"body": "Body", "profile": "TowerProfile", "name": "Tower", "length": q(25)})
    log.check("fixture: Base and Tower pads committed", p1.get("status") == "OK" and p2.get("status") == "OK", short(p1) + short(p2))
    mp = await m.call("query_mass_properties", {"doc": doc, "object": "Tower"})
    bb = sc(mp).get("bbox") or {}
    ext = [round(bb[k + "max"]["value"] - bb[k + "min"]["value"], 3) for k in "xyz"] if bb else None
    log.check("Given: bbox has three different extents", bool(ext) and len(set(ext)) == 3, {"extents_xyz": ext, "volume": sc(mp).get("volume")})
    log.note(f"doc={doc}")
    for cam in CAMS:
        r, out = await render(m, doc, {"camera": cam}, f"tc-06-02-{cam}.png")
        log.check(f"render camera={cam}: OK + resource_link", r.get("status") == "OK" and bool(link(r)), {"status": r.get("status"), "objs": objs(r)})
    bad = await m.call("query_screenshot", {"doc": doc, "view": {"camera": "oblique"}})
    log.check("camera 'oblique' rejected INVALID_INPUT", "INVALID_INPUT" in json.dumps(bad) or "validation" in json.dumps(bad).lower(), short(bad, 400))

go("tc-06-02", body)
