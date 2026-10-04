from tc04lib import *  # noqa: F401,F403

TOP = sel("PlatePad", "Face6")


async def body(m, log):
    h = sc(await m.call("document_create", {"label": "PocketPlate"})).get("doc")
    pp = await body_pad(m, h, "PlateBody", "PlateProfile", "PlatePad", rect_profile(0, 0, 60, 40), 5)
    mp = await m.call("query_mass_properties", {"doc": h, "object": "PlatePad"})
    log.check("Given PlatePad vol 12000", near(vol(mp), 12000.0), vol(mp))
    c1, a1 = await sketch(m, h, "SlotProfile", "PlateBody", rect_profile(10, 10, 10, 10), face=TOP)
    c2, a2 = await sketch(m, h, "ThroughProfile", "PlateBody", rect_profile(40, 15, 10, 10), face=TOP)
    log.note(f"sketch_create on PlatePad Face6: {short(c1, 150)} {short(c2, 150)}; add: {short(a1, 150)} {short(a2, 150)}")
    for s in ("SlotProfile", "ThroughProfile"):
        v = await m.call("verify_sketch", {"doc": h, "sketch": s})
        log.check(f"Given {s} dof=0", (sc(v).get("subject") or {}).get("dof") == 0, short(v))
    p1 = await m.call("feature_pocket", {"doc": h, "body": "PlateBody", "profile": "SlotProfile", "name": "SlotPocket", "length": q(2)})
    p2 = await m.call("feature_pocket", {"doc": h, "body": "PlateBody", "profile": "ThroughProfile", "name": "ThroughPocket", "up_to": "ThroughAll"})
    log.check("step 1 OK rolled_back=false", ok_commit(p1), short(p1))
    m1 = await m.call("query_mass_properties", {"doc": h, "object": "SlotPocket"})
    log.check("SlotPocket vol 11800", near(vol(m1), 11800.0), vol(m1))
    log.check("step 2 OK rolled_back=false", ok_commit(p2), short(p2))
    m2 = await m.call("query_mass_properties", {"doc": h, "object": "ThroughPocket"})
    log.check("ThroughPocket vol 11300", near(vol(m2), 11300.0), vol(m2))
    s2 = ss(p2)
    log.check("shape_summary face_count > 6, solid_count=1", (s2.get("face_count") or 0) > 6 and s2.get("solid_count") == 1, json.dumps(s2))
    vs = await m.call("verify_shape", {"doc": h, "object": "ThroughPocket"})
    log.check("verify_shape ThroughPocket OK", vs.get("status") == "OK", short(vs))
    qo = await m.call("query_object", {"doc": h, "object": "ThroughPocket"})
    log.check("ThroughPocket Type=ThroughAll", (sc(qo).get("properties") or {}).get("Type") == "ThroughAll", (sc(qo).get("properties") or {}).get("Type"))
    bad = await m.call("feature_pad", {"doc": h, "body": "PlateBody", "profile": "SlotProfile", "name": "ThroughPadProbe", "up_to": "ThroughAll"})
    log.check("ThroughAll on feature_pad refused", bad.get("status") == "INVALID_INPUT" and "not one of" in detail_msg(bad), short(bad))
    log.check("ThroughAll pocket needed no length (step 2 sent no length and committed)", ok_commit(p2), "")
    await capture(m, h, "tc-04-05-after.png")
    log.write({"doc": h})


go("tc-04-05", body)
