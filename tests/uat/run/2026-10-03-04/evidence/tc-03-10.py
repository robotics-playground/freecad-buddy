from tc03lib import *  # noqa: F401,F403


async def body(m, log):
    doc = await new_doc(m, "BracketPlate")
    await rect_sketch(m, doc, "PlateProfile")
    v0 = await m.call("verify_sketch", {"doc": doc, "sketch": "PlateProfile"})
    s0 = sc(v0).get("subject") or {}
    log.check("Given geometry_count=4 constraint_count=11", s0.get("geometry_count") == 4 and s0.get("constraint_count") == 11,
              f"gc={s0.get('geometry_count')} cc={s0.get('constraint_count')}")
    i0 = await m.call("query_sketch_info", {"doc": doc, "sketch": "PlateProfile"})
    c0 = [(c.get("id"), c.get("type")) for c in sc(i0).get("constraints") or []]
    log.check("Given constraint list ids 1..11 recorded", [i for i, _ in c0] == list(range(1, 12)), f"{c0}")
    fit0 = await m.fit(doc)
    log.note(f"before fit: {fit0}")
    log.write({"shot": shot("tc-03-10-before.png")})

    e = await m.call("sketch_remove_geometry", {"doc": doc, "sketch": "PlateProfile", "geo_ids": [3]})
    i1 = await m.call("query_sketch_info", {"doc": doc, "sketch": "PlateProfile"})
    log.check("SPEC_FAILED with rolled_back=true", e.get("status") == "SPEC_FAILED" and mut(e).get("rolled_back") is True, short(e))
    log.check("explanation names 'verify_sketch failed on PlateProfile (dof='",
              (pv(e).get("explanation") or "").startswith("verify_sketch failed on PlateProfile (dof="), pv(e).get("explanation"))
    log.check("4 geometry entries again", len(sc(i1).get("geometry") or []) == 4, f"{len(sc(i1).get('geometry') or [])}")
    c1 = [(c.get("id"), c.get("type")) for c in sc(i1).get("constraints") or []]
    log.check("11 constraints again (same list)", c1 == c0, f"{c1}")

    # cascade on a sketch whose removed geometry carries only its own constraints
    await m.call("sketch_create", {"doc": doc, "name": "CascadeProfile", "plane": "XY"})
    cg = await m.call("sketch_add_geometry", {"doc": doc, "sketch": "CascadeProfile",
        "geometry": [{"kind": "line_segment", "start": [0, 60], "end": [60, 60]}, {"kind": "point", "center": [30, 70]}],
        "constraints": [{"type": "Block", "first": 0},
                        {"type": "DistanceX", "first": -1, "first_pos": 1, "second": 1, "second_pos": 1, "value": {"value": 30, "unit": "mm"}},
                        {"type": "DistanceY", "first": -1, "first_pos": 1, "second": 1, "second_pos": 1, "value": {"value": 70, "unit": "mm"}}]})
    vb = await m.call("verify_sketch", {"doc": doc, "sketch": "CascadeProfile"})
    cb = (sc(vb).get("subject") or {}).get("constraint_count")
    rc = await m.call("sketch_remove_geometry", {"doc": doc, "sketch": "CascadeProfile", "geo_ids": [1]})
    va = await m.call("verify_sketch", {"doc": doc, "sketch": "CascadeProfile"})
    ca = (sc(va).get("subject") or {}).get("constraint_count")
    log.check("cascade: OK and constraint_count drops by exactly 2 (the point's own constraints)",
              rc.get("status") == "OK" and cb is not None and ca == cb - 2,
              f"build={cg.get('status')} remove={rc.get('status')} before={cb} after={ca}")
    r7 = await m.call("sketch_remove_geometry", {"doc": doc, "sketch": "PlateProfile", "geo_ids": [7]})
    log.check("geo_ids [7] INVALID_INPUT naming (0..3), no snapshot_path",
              r7.get("status") == "INVALID_INPUT" and "is outside the sketch (0..3)" in json.dumps(r7.get("detail")) and not mut(r7).get("snapshot_path"), short(r7))
    re_ = await m.call("sketch_remove_geometry", {"doc": doc, "sketch": "PlateProfile", "geo_ids": []})
    log.check("geo_ids [] schema reject", schema_reject(re_), short(re_))
    # the cascade sketch is not part of the TC's visual; hide nothing, just note it
    fit = await m.fit(doc)
    log.note(f"after fit: {fit}")
    log.write({"shot": shot("tc-03-10-after.png")})
    log.write({"edit": edit_capture("PlateProfile", "tc-03-10-edit-after.png")})


go("tc-03-10", body)
