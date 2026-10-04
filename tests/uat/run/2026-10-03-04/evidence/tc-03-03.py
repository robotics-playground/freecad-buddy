from tc03lib import *  # noqa: F401,F403


async def cylinder_doc(m) -> tuple[str, str]:
    """Scratch doc holding a padded circle, so a cylindrical face exists to select."""
    doc = await new_doc(m, "CylScratch")
    await m.call("feature_body_create", {"doc": doc, "name": "PinBody"})
    await m.call("sketch_create", {"doc": doc, "name": "PinProfile", "plane": "XY", "body": "PinBody"})
    await m.call("sketch_add_geometry", {"doc": doc, "sketch": "PinProfile",
        "geometry": [{"kind": "circle", "center": [0, 0], "radius": {"value": 5, "unit": "mm"}}],
        "constraints": [{"type": "Coincident", "first": 0, "first_pos": 3, "second": -1, "second_pos": 1},
                        {"type": "Radius", "first": 0, "value": {"value": 5, "unit": "mm"}}]})
    await m.call("feature_pad", {"doc": doc, "body": "PinBody", "profile": "PinProfile", "name": "PinPad",
                                 "length": {"value": 10, "unit": "mm"}})
    return doc, "PinPad"


async def body(m, log):
    doc = await new_doc(m, "BracketPlate")
    pad = await plate(m, doc)
    log.check("Given setup PlatePad OK", pad.get("status") == "OK", short(pad))
    mass = await m.call("query_mass_properties", {"doc": doc, "object": "PlatePad"})
    vol = (sc(mass).get("volume") or {})
    vol_v = vol.get("value") if isinstance(vol, dict) else vol
    log.check("Given PlatePad volume near 12000", vol_v is not None and abs(vol_v - 12000) < 12, f"volume={vol}")
    obj = await m.call("query_object", {"doc": doc, "object": "PlatePad"})
    log.check("Given query_object PlatePad lists face names", "Face6" in json.dumps(sc(obj)),
              json.dumps(sc(obj))[:600])
    sel = {"kind": "mapped_name", "object": "PlatePad", "mapped_name": "Face6"}
    e = await m.call("sketch_create", {"doc": doc, "name": "BossProfile", "face": sel, "body": "PlateBody"})
    log.check("create on Face6 commits OK rolled_back=false",
              e.get("status") == "OK" and mut(e).get("rolled_back") is False, short(e))
    plc = await m.call("query_placement", {"doc": doc, "object": "BossProfile"})
    z = ((sc(plc).get("global") or {}).get("position") or {}).get("z")
    zl = ((sc(plc).get("local") or {}).get("position") or {}).get("z")
    log.check("BossProfile position.z == 5 mm", z == {"value": 5.0, "unit": "mm"} or (isinstance(z, dict) and abs(z.get("value", 0) - 5) < 1e-6),
              f"global.z={z} local.z={zl} axis={(sc(plc).get('global') or {}).get('axis')}")
    v = await m.call("verify_sketch", {"doc": doc, "sketch": "BossProfile"})
    subj = sc(v).get("subject") or {}
    log.check("verify_sketch BossProfile OK fully_constrained=true",
              v.get("status") == "OK" and subj.get("fully_constrained") is True, f"status={v.get('status')} fc={subj.get('fully_constrained')}")
    both = await m.call("sketch_create", {"doc": doc, "name": "Both", "plane": "XY", "face": sel})
    log.check("plane+face INVALID_INPUT naming exactly-one message",
              both.get("status") == "INVALID_INPUT" and "sketch_create requires exactly one of 'plane' and 'face'" in json.dumps(both.get("detail")),
              short(both))
    geo = await m.call("sketch_create", {"doc": doc, "name": "Geo", "face": {"kind": "geometric", "object": "PlatePad"}})
    log.check("geometric selector INVALID_INPUT naming mapped_name rule",
              geo.get("status") == "INVALID_INPUT" and "selector kind must be 'mapped_name'" in json.dumps(geo.get("detail")),
              short(geo))
    cdoc, cpad = await cylinder_doc(m)
    cobj = await m.call("query_object", {"doc": cdoc, "object": cpad})
    log.note(f"cylinder scratch doc PinPad faces: {json.dumps(sc(cobj))[:400]}")
    found = None
    for face in ("Face1", "Face2", "Face3"):
        r = await m.call("sketch_create", {"doc": cdoc, "name": f"Cyl{face}",
                                           "face": {"kind": "mapped_name", "object": cpad, "mapped_name": face}})
        if r.get("status") != "OK":
            found = (face, r)
            if "is not a planar face" in json.dumps(r.get("detail")):
                break
    log.check("non-planar (cylindrical) face INVALID_INPUT naming 'is not a planar face'",
              bool(found) and found[1].get("status") == "INVALID_INPUT" and "is not a planar face" in json.dumps(found[1].get("detail")),
              f"face={found[0] if found else None} {short(found[1]) if found else ''}")
    await m.call("document_close", {"doc": cdoc})
    fit = await m.fit(doc)
    log.note(f"fit: {fit}")
    log.write({"shot": shot("tc-03-03-after.png")})


go("tc-03-03", body)
