from tc04lib import *  # noqa: F401,F403

TOP = sel("PlatePad", "Face6")


async def plate_with_point(m, label, sk="HoleProfile", x=10, y=20):
    h = sc(await m.call("document_create", {"label": label})).get("doc")
    await body_pad(m, h, "PlateBody", "PlateProfile", "PlatePad", rect_profile(0, 0, 60, 40), 5)
    await sketch(m, h, sk, "PlateBody", point_profile(x, y), face=TOP)
    return h


async def body(m, log):
    h = await plate_with_point(m, "HolePlate")
    mp = await m.call("query_mass_properties", {"doc": h, "object": "PlatePad"})
    log.check("Given PlatePad vol 12000", near(vol(mp), 12000.0), vol(mp))
    v = await m.call("verify_sketch", {"doc": h, "sketch": "HoleProfile"})
    log.check("Given HoleProfile dof=0", (sc(v).get("subject") or {}).get("dof") == 0, short(v))
    hole = await m.call("feature_hole", {"doc": h, "body": "PlateBody", "profile": "HoleProfile", "name": "ClearanceHole",
                                         "diameter": q(5.5), "depth": q(3)})
    mh = await m.call("query_mass_properties", {"doc": h, "object": "ClearanceHole"})
    log.check("hole OK rolled_back=false", ok_commit(hole), short(hole))
    log.check("volume 11928.7 within 0.1%", near(vol(mh), 11928.73), vol(mh))
    qo = await m.call("query_object", {"doc": h, "object": "ClearanceHole"})
    props = sc(qo).get("properties") or {}
    log.check("DepthType=Dimension", props.get("DepthType") == "Dimension", props.get("DepthType"))
    s = ss(hole)
    log.check("solid_count=1 face_count > 6", s.get("solid_count") == 1 and (s.get("face_count") or 0) > 6, json.dumps(s))
    vs = await m.call("verify_shape", {"doc": h, "object": "ClearanceHole"})
    log.check("verify_shape OK", vs.get("status") == "OK", short(vs))
    nd = await m.call("feature_hole", {"doc": h, "body": "PlateBody", "profile": "HoleProfile", "name": "NoDepthHole", "diameter": q(5.5)})
    log.check("Dimension without depth INVALID_INPUT", nd.get("status") == "INVALID_INPUT"
              and "depth_type='Dimension' is depth-driven; 'depth' is required" in detail_msg(nd), short(nd))
    zd = await m.call("feature_hole", {"doc": h, "body": "PlateBody", "profile": "HoleProfile", "name": "ZeroHole",
                                       "diameter": q(0), "depth": q(3)})
    log.check("zero diameter INVALID_INPUT 'diameter must be positive'", zd.get("status") == "INVALID_INPUT" and "diameter must be positive" in detail_msg(zd), short(zd))
    # ThroughAll on a fresh identical plate, so the blind bore in the captured model stays blind
    h2 = await plate_with_point(m, "HolePlateThrough")
    ta = await m.call("feature_hole", {"doc": h2, "body": "PlateBody", "profile": "HoleProfile", "name": "ThroughHole",
                                       "diameter": q(5.5), "depth_type": "ThroughAll"})
    mt = await m.call("query_mass_properties", {"doc": h2, "object": "ThroughHole"})
    log.check("ThroughAll no depth OK vol 11881.2", ok_commit(ta) and near(vol(mt), 11881.21), f"{short(ta, 200)} vol={vol(mt)}")
    await m.call("document_close", {"doc": h2})
    log.note("ThroughAll check ran on a second identical plate (HolePlateThrough), closed before the capture")
    await capture(m, h, "tc-04-07-after.png")
    log.write({"doc": h})


go("tc-04-07", body)
