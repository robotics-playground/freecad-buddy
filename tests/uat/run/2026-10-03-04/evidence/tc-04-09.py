import math

from tc04lib import *  # noqa: F401,F403

EXPECTED_AREA = 5800 - 8 * (4 - math.pi) - 4 * (2 * 2 * 5) + 4 * (math.pi * 2 / 2 * 5)


async def fillet_case(m, log, label, edges, tag):
    h = sc(await m.call("document_create", {"label": label})).get("doc")
    await body_pad(m, h, "PlateBody", "PlateProfile", "PlatePad", rect_profile(0, 0, 60, 40), 5)
    mp = await m.call("query_mass_properties", {"doc": h, "object": "PlatePad"})
    log.check(f"[{tag}] Given PlatePad vol 12000", near(vol(mp), 12000.0), vol(mp))
    f = await m.call("feature_fillet", {"doc": h, "body": "PlateBody", "base": "PlatePad", "name": "CornerFillet",
                                        "edges": [sel("PlatePad", e) for e in edges], "radius": q(2)})
    mf = await m.call("query_mass_properties", {"doc": h, "object": "CornerFillet"})
    s = ss(f)
    log.check(f"[{tag}] fillet OK rolled_back=false", ok_commit(f), short(f, 400))
    log.check(f"[{tag}] volume 11982.8 within 0.1%", near(vol(mf), 11982.83), vol(mf))
    log.check(f"[{tag}] face_count=10", s.get("face_count") == 10, json.dumps(s))
    vs = await m.call("verify_shape", {"doc": h, "object": "CornerFillet"})
    log.check(f"[{tag}] solid_count=1 is_valid=true, verify_shape OK", s.get("solid_count") == 1 and s.get("is_valid") is True and vs.get("status") == "OK", short(vs))
    area = (sc(mf).get("area") or {}).get("value")
    log.check(f"[{tag}] area consistent with four 2 mm quarter-cylinders (analytic {EXPECTED_AREA:.2f}; plate 5800)",
              near(area, EXPECTED_AREA), area)
    return h


async def body(m, log):
    log.note("TC literal edges Edge1/3/5/7. Outside oracle (tc-04-topology-oracle.txt): on this pad Edge1, Edge2, Edge5, Edge8 "
             "are the vertical corners; Edge3 and Edge7 are 60 mm / 40 mm horizontal edges. Both sets are run.")
    h_lit = await fillet_case(m, log, "FilletLiteral", ["Edge1", "Edge3", "Edge5", "Edge7"], "literal 1,3,5,7")
    await capture(m, h_lit, "tc-04-09-literal-after.png")
    await m.call("document_close", {"doc": h_lit})
    h = await fillet_case(m, log, "FilletCorners", ["Edge1", "Edge2", "Edge5", "Edge8"], "vertical 1,2,5,8")
    await m.call("feature_body_create", {"doc": h, "name": "OtherBody"})
    await sketch(m, h, "OtherProfile", "OtherBody", rect_profile(80, 0, 20, 20))
    await m.call("feature_pad", {"doc": h, "body": "OtherBody", "profile": "OtherProfile", "name": "OtherPad", "length": q(5)})
    before = set(snap_temp())
    e1 = await m.call("feature_fillet", {"doc": h, "body": "PlateBody", "base": "OtherPad", "name": "CrossFillet",
                                         "edges": [sel("OtherPad", "Edge1")], "radius": q(1)})
    log.check("base in another Body INVALID_INPUT 'is not in Body'", e1.get("status") == "INVALID_INPUT" and "is not in Body" in detail_msg(e1), short(e1))
    e2 = await m.call("feature_fillet", {"doc": h, "body": "PlateBody", "base": "CornerFillet", "name": "MixFillet",
                                         "edges": [sel("OtherPad", "Edge1")], "radius": q(1)})
    log.check("edge object != base INVALID_INPUT 'not the dress-up base'", e2.get("status") == "INVALID_INPUT" and "not the dress-up base" in detail_msg(e2), short(e2))
    e3 = await m.call("feature_fillet", {"doc": h, "body": "PlateBody", "base": "CornerFillet", "name": "RepFillet",
                                         "edges": [sel("CornerFillet", "Edge1"), sel("CornerFillet", "Edge1")], "radius": q(1)})
    log.check("repeated edge INVALID_INPUT 'repeats Edge1'", e3.get("status") == "INVALID_INPUT" and "repeats Edge1" in detail_msg(e3), short(e3))
    log.note(f"new temp snapshots during refusals: {sorted(set(snap_temp()) - before)}")
    await m.call("document_close", {"doc": h})
    # visual on a document holding only the filleted plate
    h2 = await fillet_case(m, log, "FilletVisual", ["Edge1", "Edge2", "Edge5", "Edge8"], "visual copy")
    await capture(m, h2, "tc-04-09-after.png")
    log.write({"doc": h2})


go("tc-04-09", body)
