import math

from tc04lib import *  # noqa: F401,F403

BORE = math.pi * 2.75 ** 2 * 5


async def plate_hole(m, h, x0=40):
    await body_pad(m, h, "PlateBody", "PlateProfile", "PlatePad", rect_profile(x0, 0, 60, 40), 5)
    await sketch(m, h, "HoleProfile", "PlateBody", point_profile(x0 + 10, 20), face=sel("PlatePad", "Face6"))
    return await m.call("feature_hole", {"doc": h, "body": "PlateBody", "profile": "HoleProfile", "name": "ClearanceHole",
                                         "diameter": q(5.5), "depth_type": "ThroughAll"})


async def body(m, log):
    log.note("plate drawn at x=40..100 so it does not overlap the r=30 disc centred on the origin (polar axis = DiscProfile N_Axis)")
    h = sc(await m.call("document_create", {"label": "Patterns"})).get("doc")
    await plate_hole(m, h)
    mh = await m.call("query_mass_properties", {"doc": h, "object": "ClearanceHole"})
    log.check("Given ClearanceHole (through) vol 11881.2", near(vol(mh), 12000 - BORE), vol(mh))
    await m.call("feature_body_create", {"doc": h, "name": "DiscBody"})
    await sketch(m, h, "DiscProfile", "DiscBody", circle_profile(0, 0, 30))
    await m.call("feature_pad", {"doc": h, "body": "DiscBody", "profile": "DiscProfile", "name": "DiscPad", "length": q(5)})
    await sketch(m, h, "DiscHoleProfile", "DiscBody", point_profile(20, 0), face=sel("DiscPad", "Face3"))
    await m.call("feature_hole", {"doc": h, "body": "DiscBody", "profile": "DiscHoleProfile", "name": "DiscHole",
                                  "diameter": q(5.5), "depth_type": "ThroughAll"})
    vd = await m.call("verify_shape", {"doc": h, "object": "DiscHole"})
    log.check("Given DiscHole verify_shape OK", vd.get("status") == "OK", short(vd))
    md0 = await m.call("query_mass_properties", {"doc": h, "object": "DiscHole"})
    disc = math.pi * 900 * 5
    log.check("Given DiscHole removes one bore", near(vol(md0), disc - BORE), vol(md0))

    p1 = await m.call("feature_pattern", {"doc": h, "body": "PlateBody", "name": "HoleRow", "kind": "linear",
                                          "originals": ["ClearanceHole"], "direction": sel("PlateProfile", "H_Axis"),
                                          "length": q(40), "occurrences": 2})
    p2 = await m.call("feature_pattern", {"doc": h, "body": "DiscBody", "name": "HoleRing", "kind": "polar",
                                          "originals": ["DiscHole"], "axis": sel("DiscProfile", "N_Axis"),
                                          "angle": q(360, "deg"), "occurrences": 6})
    log.check("linear pattern OK rolled_back=false", ok_commit(p1), short(p1, 400))
    m1 = await m.call("query_mass_properties", {"doc": h, "object": "HoleRow"})
    log.check("HoleRow vol 11762.4 (two bores total)", near(vol(m1), 12000 - 2 * BORE), vol(m1))
    bb = ss(p1).get("bbox")
    log.check("HoleRow bbox unchanged [60,40,5]", isinstance(bb, list) and all(near(a, b) for a, b in zip(bb, [60, 40, 5])), bb)
    log.check("polar pattern OK rolled_back=false", ok_commit(p2), short(p2, 400))
    m2 = await m.call("query_mass_properties", {"doc": h, "object": "HoleRing"})
    log.check("HoleRing removes exactly 6 bores", near(vol(m2), disc - 6 * BORE), f"vol={vol(m2)} expected={disc - 6 * BORE:.2f}")
    vs = [await m.call("verify_shape", {"doc": h, "object": o}) for o in ("HoleRow", "HoleRing")]
    log.check("verify_shape OK for HoleRow and HoleRing", all(v.get("status") == "OK" for v in vs), [v.get("status") for v in vs])
    sch = await m.call("feature_pattern", {"doc": h, "body": "PlateBody", "name": "MirrorKind", "kind": "mirror",
                                           "direction": sel("PlateProfile", "H_Axis"), "length": q(40), "occurrences": 2})
    log.check("kind mirror is a schema reject", schema_reject(sch), short(sch))
    # originals default, on an equivalent plate in its own document
    h2 = sc(await m.call("document_create", {"label": "PatternTipDefault"})).get("doc")
    await plate_hole(m, h2)
    p3 = await m.call("feature_pattern", {"doc": h2, "body": "PlateBody", "name": "TipRow", "kind": "linear",
                                          "direction": sel("PlateProfile", "H_Axis"), "length": q(40), "occurrences": 2})
    q3 = await m.call("query_object", {"doc": h2, "object": "TipRow"})
    originals = (sc(q3).get("properties") or {}).get("Originals")
    m3 = await m.call("query_mass_properties", {"doc": h2, "object": "TipRow"})
    log.check("originals omitted -> OK, patterns the Tip (ClearanceHole)", ok_commit(p3) and near(vol(m3), 12000 - 2 * BORE),
              f"{short(p3, 200)} Originals={originals} vol={vol(m3)}")
    await m.call("document_close", {"doc": h2})
    await capture(m, h, "tc-04-11-after.png")
    log.write({"doc": h})


go("tc-04-11", body)
