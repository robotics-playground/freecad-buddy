import os

from tc09lib import *  # noqa
from tc05lib import body_sketch, point_profile  # noqa


async def body(m, log):
    await close_all(m, log)
    doc = await body_sketch(m, "TC0906")
    si0 = await m.call("query_sketch_info", {"doc": doc, "sketch": "Sketch"})
    g0 = len(sc(si0).get("geometry") or [])
    log.check("Given query_sketch_info OK for <SK>", si0.get("status") == "OK", g0)
    # mint <P> from a valid preview of a fully constrained single point
    geom, cons = point_profile(5, 5)
    pv_ = await m.call("preview_dry_run", {"doc": doc, "operation": {"tool": "sketch_add_geometry",
                                           "args": {"sketch": "Sketch", "geometry": geom, "constraints": cons}}})
    P = sc(pv_).get("preview_id") or "fcb-preview:none"
    log.note(f"<P> = {P} (preview status {pv_.get('status')})")
    await frame_shot(m, doc, "tc-09-06-before.png")
    conf = {"preview_id": P}
    a = await m.call("sketch_add_geometry", {"doc": doc, "sketch": "Sketch", "geometry": [], "confirm": conf})
    b = await m.call("sketch_add_geometry", {"doc": doc, "sketch": "Sketch", "geometry": [
        {"kind": "line_segment", "start": [0], "end": [10, 0]}], "confirm": conf})
    c = await m.call("sketch_add_geometry", {"doc": doc, "sketch": "Sketch", "geometry": [
        {"kind": "line_segment", "start": [0, 0, 0, 0], "end": [10, 0]}], "confirm": conf})
    e = await m.call("export_step", {"doc": doc, "path": f"{EV}/tc-09-06-e.step", "objects": []})
    log.check("empty geometry -> protocol rejection (minItems 1)", is_reject(a), raw(a) or short(a))
    log.check("1-element coord -> protocol rejection (minItems 2)", is_reject(b), raw(b) or short(b))
    log.check("4-element coord -> protocol rejection (maxItems 3)", is_reject(c), raw(c) or short(c))
    log.check("bounds distinct: both rejected, neither envelope, different messages", is_reject(b) and is_reject(c) and raw(b) != raw(c),
              [raw(b), raw(c)])
    log.check("empty objects[] on export -> real envelope (not schema error)", e.get("_sc") is True and "status" in e, short(e))
    log.note(f"export objects[] wrote file: {os.path.exists(EV + '/tc-09-06-e.step')}")
    si1 = await m.call("query_sketch_info", {"doc": doc, "sketch": "Sketch"})
    log.check("sketch geometry_count unchanged", len(sc(si1).get("geometry") or []) == g0 and g0 == 4, (g0, len(sc(si1).get("geometry") or []), "no geometry_count field: len(geometry)"))
    await frame_shot(m, doc, "tc-09-06-after.png")


go("tc-09-06", body)
