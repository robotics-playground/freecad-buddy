from tc03lib import *  # noqa: F401,F403

# ScrapProfile: two Block-pinned points, so removing one leaves the other fully constrained.
SCRAP_GEO = [{"kind": "point", "center": [80, 10]}, {"kind": "point", "center": [80, 30]}]
SCRAP_CON = [{"type": "Block", "first": 0}, {"type": "Block", "first": 1}]


async def body(m, log):
    doc = await new_doc(m, "BracketPlate")
    await rect_sketch(m, doc, "PlateProfile")
    v0 = await m.call("verify_sketch", {"doc": doc, "sketch": "PlateProfile"})
    s0 = sc(v0).get("subject") or {}
    log.check("Given PlateProfile geometry_count=4 malformed=[]", s0.get("geometry_count") == 4 and s0.get("malformed") == [], f"{s0.get('geometry_count')} {s0.get('malformed')}")
    await m.call("sketch_create", {"doc": doc, "name": "ScrapProfile", "plane": "XY"})
    sg = await m.call("sketch_add_geometry", {"doc": doc, "sketch": "ScrapProfile", "geometry": SCRAP_GEO, "constraints": SCRAP_CON})
    si = await m.call("query_sketch_info", {"doc": doc, "sketch": "ScrapProfile"})
    log.check("Given ScrapProfile reports its entries", len(sc(si).get("geometry") or []) == 2, f"build={sg.get('status')} entries={len(sc(si).get('geometry') or [])}")
    snaps0 = snap_temp()
    fit0 = await m.fit(doc)
    log.note(f"before fit: {fit0}")
    log.write({"shot": shot("tc-03-19-before.png")})
    log.write({"edit_before_plate": edit_capture("PlateProfile", "tc-03-19-edit-before-PlateProfile.png")})
    log.write({"edit_before_scrap": edit_capture("ScrapProfile", "tc-03-19-edit-before-ScrapProfile.png")})
    pi0 = await m.call("query_sketch_info", {"doc": doc, "sketch": "PlateProfile"})

    r1 = await m.call("sketch_remove_geometry", {"doc": doc, "sketch": "ScrapProfile", "geo_ids": [1]})
    log.note(f"remove ScrapProfile geo 1: {r1.get('status')} {json.dumps(r1.get('detail'))[:200]}")
    r2 = await m.call("sketch_add_constraint", {"doc": doc, "sketch": "ScrapProfile", "constraints": [{"type": "Horizontal", "first": 1}]})
    r3 = await m.call("sketch_add_constraint", {"doc": doc, "sketch": "PlateProfile", "constraints": [{"type": "Horizontal", "first": 0}, {"type": "Horizontal", "first": 88}]})

    log.check("stale geo_id INVALID_INPUT naming outside the sketch", r2.get("status") == "INVALID_INPUT" and "outside the sketch" in json.dumps(r2.get("detail")), short(r2))
    log.check("stale refusal pre-transaction (no snapshot_path)", not mut(r2).get("snapshot_path"), "")
    log.check("mixed batch non-OK", r3.get("status") != "OK", short(r3))
    pi1 = await m.call("query_sketch_info", {"doc": doc, "sketch": "PlateProfile"})
    log.check("PlateProfile constraints unchanged by the batch", sc(pi1).get("constraints") == sc(pi0).get("constraints"), f"{len(sc(pi0).get('constraints') or [])} -> {len(sc(pi1).get('constraints') or [])}")
    v1 = await m.call("verify_sketch", {"doc": doc, "sketch": "PlateProfile"})
    s1 = sc(v1).get("subject") or {}
    log.check("malformed=[]", s1.get("malformed") == [], json.dumps(s1.get("malformed")))
    log.check("OK dof=0", v1.get("status") == "OK" and s1.get("dof") == 0, short(v1))
    log.check("no FCB_TMP_snap_* left by this run", snap_temp() == snaps0, f"{len(snaps0)} -> {len(snap_temp())}")
    fit = await m.fit(doc)
    log.note(f"after fit: {fit}")
    log.write({"shot": shot("tc-03-19-after.png")})
    log.write({"edit_after_plate": edit_capture("PlateProfile", "tc-03-19-edit-after-PlateProfile.png")})
    log.write({"edit_after_scrap": edit_capture("ScrapProfile", "tc-03-19-edit-after-ScrapProfile.png")})


go("tc-03-19", body)
