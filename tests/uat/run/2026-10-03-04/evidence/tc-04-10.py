from tc04lib import *  # noqa: F401,F403


async def chain(m, log, label, tag):
    h = sc(await m.call("document_create", {"label": label})).get("doc")
    pp = await body_pad(m, h, "PlateBody", "PlateProfile", "PlatePad", rect_profile(0, 0, 60, 40), 5)
    mp = await m.call("query_mass_properties", {"doc": h, "object": "PlatePad"})
    log.check(f"[{tag}] Given PlatePad vol 12000", near(vol(mp), 12000.0), vol(mp))
    c1 = await m.call("feature_chamfer", {"doc": h, "body": "PlateBody", "base": "PlatePad", "name": "EqualChamfer",
                                          "edges": [sel("PlatePad", "Edge1")], "size": q(1.5)})
    c2 = await m.call("feature_chamfer", {"doc": h, "body": "PlateBody", "base": "EqualChamfer", "name": "TwoSizeChamfer",
                                          "edges": [sel("EqualChamfer", "Edge3")], "chamfer_type": "Two distances",
                                          "size": q(2), "second_size": q(1)})
    return h, ss(pp), c1, c2


async def body(m, log):
    h, s0, c1, c2 = await chain(m, log, "ChamferPlate", "main")
    caps = await m.call("query_capabilities", {})
    members = ((sc(caps).get("enums") or {}).get("PartDesign::Chamfer") or {}).get("ChamferType")
    log.check("Given ChamferType enumeration known", bool(members), members)
    lit = await m.call("feature_chamfer", {"doc": h, "body": "PlateBody", "base": "TwoSizeChamfer", "name": "AngleChamfer",
                                           "edges": [sel("TwoSizeChamfer", "Edge5")], "chamfer_type": "Distance and angle",
                                           "size": q(2), "angle": q(30, "deg")})
    log.note(f"step 3 literal chamfer_type 'Distance and angle' -> {short(lit, 300)}")
    log.note("substitute this build's member 'Distance and Angle'. Oracle: TwoSizeChamfer Edge5 is the 2.24 mm bottom edge of the "
             "new bevel face, Edge17 the vertical corner at (60,40); the main model uses Edge17, the literal Edge5 runs on a copy")
    c3 = await m.call("feature_chamfer", {"doc": h, "body": "PlateBody", "base": "TwoSizeChamfer", "name": "AngleChamfer",
                                          "edges": [sel("TwoSizeChamfer", "Edge17")], "chamfer_type": "Distance and Angle",
                                          "size": q(2), "angle": q(30, "deg")})
    log.check("all three chamfers commit OK rolled_back=false", all(ok_commit(e) for e in (c1, c2, c3)), [short(e, 200) for e in (c1, c2, c3)])
    me = await m.call("query_mass_properties", {"doc": h, "object": "EqualChamfer"})
    log.check("EqualChamfer vol 11994.4", near(vol(me), 11994.375), vol(me))
    fc = [s0.get("face_count")] + [ss(e).get("face_count") for e in (c1, c2, c3)]
    log.check("each chamfer adds exactly one face", all(b == a + 1 for a, b in zip(fc, fc[1:])), fc)
    before = set(snap_temp())
    b1 = await m.call("feature_chamfer", {"doc": h, "body": "PlateBody", "base": "AngleChamfer", "name": "BevelChamfer",
                                          "edges": [sel("AngleChamfer", "Edge1")], "chamfer_type": "Bevel", "size": q(1)})
    log.check("chamfer_type Bevel INVALID_INPUT 'chamfer_type 'Bevel' is not one of'", b1.get("status") == "INVALID_INPUT" and "chamfer_type 'Bevel' is not one of" in detail_msg(b1), short(b1))
    b2 = await m.call("feature_chamfer", {"doc": h, "body": "PlateBody", "base": "AngleChamfer", "name": "WideAngle",
                                          "edges": [sel("AngleChamfer", "Edge1")], "chamfer_type": "Distance and Angle",
                                          "size": q(1), "angle": q(200, "deg")})
    log.check("angle 200 INVALID_INPUT 'angle must be in'", b2.get("status") == "INVALID_INPUT" and "angle must be in" in detail_msg(b2), short(b2))
    b3 = await m.call("feature_chamfer", {"doc": h, "body": "PlateBody", "base": "AngleChamfer", "name": "ZeroChamfer",
                                          "edges": [sel("AngleChamfer", "Edge1")], "size": q(0)})
    log.check("size 0 INVALID_INPUT 'size must be positive'", b3.get("status") == "INVALID_INPUT" and "size must be positive" in detail_msg(b3), short(b3))
    log.note(f"new temp snapshots during refusals: {sorted(set(snap_temp()) - before)}")
    vs = await m.call("verify_shape", {"doc": h, "object": "AngleChamfer"})
    log.check("verify_shape AngleChamfer OK solid_count=1", vs.get("status") == "OK" and ss(c3).get("solid_count") == 1, short(vs))
    # literal Edge5 with the live spelling, on a copy
    hc, _, _, _ = await chain(m, log, "ChamferLiteralEdge5", "copy")
    lit5 = await m.call("feature_chamfer", {"doc": hc, "body": "PlateBody", "base": "TwoSizeChamfer", "name": "AngleChamfer",
                                            "edges": [sel("TwoSizeChamfer", "Edge5")], "chamfer_type": "Distance and Angle",
                                            "size": q(2), "angle": q(30, "deg")})
    log.note(f"literal Edge5 + 'Distance and Angle' on the copy -> {short(lit5, 400)} summary={json.dumps(ss(lit5))} explanation={pv(lit5).get('explanation')}")
    await m.call("document_close", {"doc": hc})
    await capture(m, h, "tc-04-10-after.png")
    log.write({"doc": h})


go("tc-04-10", body)
