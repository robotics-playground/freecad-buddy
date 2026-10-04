from tc03lib import *  # noqa: F401,F403

FACE6 = {"kind": "mapped_name", "object": "PlatePad", "mapped_name": "Face6"}


async def body(m, log):
    doc = await new_doc(m, "BracketPlate")
    await plate(m, doc)
    mp = await m.call("query_mass_properties", {"doc": doc, "object": "PlatePad"})
    vol = (sc(mp).get("volume") or {}).get("value")
    log.check("Given PlatePad volume near 12000", vol is not None and abs(vol - 12000) < 12, f"volume={vol}")
    bc = await m.call("sketch_create", {"doc": doc, "name": "BossProfile", "face": FACE6, "body": "PlateBody"})
    vb = await m.call("verify_sketch", {"doc": doc, "sketch": "BossProfile"})
    log.check("Given BossProfile on top face verify OK", bc.get("status") == "OK" and vb.get("status") == "OK", f"create={bc.get('status')} verify={vb.get('status')}")
    obj = await m.call("query_object", {"doc": doc, "object": "PlatePad"})
    log.check("Given query_object PlatePad lists edge names", "Edge1" in json.dumps(sc(obj)), "query_object returns properties only (no sub-element list); see TC-03-03")
    fit0 = await m.fit(doc)
    log.note(f"before fit: {fit0}")
    log.write({"shot": shot("tc-03-13-before.png")})

    e = await m.call("sketch_add_external_geometry", {"doc": doc, "sketch": "BossProfile",
                                                      "edge": {"kind": "mapped_name", "object": "PlatePad", "mapped_name": "Edge1"}})
    log.check("projection commits OK rolled_back=false", e.get("status") == "OK" and mut(e).get("rolled_back") is False, short(e))
    v = await m.call("verify_sketch", {"doc": doc, "sketch": "BossProfile"})
    log.check("verify_sketch OK dof=0", v.get("status") == "OK" and (sc(v).get("subject") or {}).get("dof") == 0, short(v))
    tnp = pv(e).get("tnp_audit") or {}
    log.check("tnp_audit.status=CLEAN findings=[]", tnp.get("status") == "CLEAN" and tnp.get("findings") == [], json.dumps(tnp))
    log.check("tnp_audit.element_map_version non-empty", bool(tnp.get("element_map_version")), json.dumps(tnp.get("element_map_version")))
    dep = await m.call("query_dependencies", {"doc": doc})
    edges = sc(dep).get("edges") or sc(dep).get("dependencies") or []
    found = any((("BossProfile" in json.dumps(x)) and ("PlatePad" in json.dumps(x))) for x in edges) if isinstance(edges, list) else False
    log.check("query_dependencies shows BossProfile -> PlatePad", found, json.dumps(sc(dep))[:600])
    u = await m.call("sketch_add_external_geometry", {"doc": doc, "sketch": "BossProfile",
                                                      "edge": {"kind": "mapped_name", "object": "NoSuchPad", "mapped_name": "Edge1"}})
    log.check("unknown source INVALID_INPUT naming 'unknown object in edge selector: NoSuchPad'",
              u.get("status") == "INVALID_INPUT" and "unknown object in edge selector: NoSuchPad" in json.dumps(u.get("detail")), short(u))
    f = await m.call("sketch_add_external_geometry", {"doc": doc, "sketch": "BossProfile",
                                                      "edge": {"kind": "mapped_name", "object": "PlatePad", "mapped_name": "Face1"}})
    log.check("face selector INVALID_INPUT naming 'resolves to a Face, not an Edge'",
              f.get("status") == "INVALID_INPUT" and "resolves to a Face, not an Edge" in json.dumps(f.get("detail")), short(f))
    fit = await m.fit(doc)
    log.note(f"after fit: {fit}")
    log.write({"shot": shot("tc-03-13-after.png")})
    log.write({"edit_after": edit_capture("BossProfile", "tc-03-13-edit-after.png", parent="PlateBody")})


go("tc-03-13", body)
