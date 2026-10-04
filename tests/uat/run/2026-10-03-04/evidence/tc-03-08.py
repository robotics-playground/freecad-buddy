from tc03lib import *  # noqa: F401,F403

DIAG = {"kind": "line_segment", "start": [0, 0], "end": [60, 40]}
DIAG_C = [{"type": "Coincident", "first": 4, "first_pos": 1, "second": 0, "second_pos": 1},
          {"type": "Coincident", "first": 4, "first_pos": 2, "second": 1, "second_pos": 2}]


async def body(m, log):
    doc = await new_doc(m, "BracketPlate")
    await m.call("sketch_create", {"doc": doc, "name": "PlateProfile", "plane": "XY"})
    g = await m.call("sketch_add_geometry", {"doc": doc, "sketch": "PlateProfile", "geometry": RECT_GEOMETRY + [DIAG],
                                             "constraints": rect_constraints() + DIAG_C})
    log.note(f"Given build: {g.get('status')} {json.dumps(g.get('detail'))[:200]}")
    info = await m.call("query_sketch_info", {"doc": doc, "sketch": "PlateProfile"})
    geo = sc(info).get("geometry") or []
    log.check("Given 5 geometry entries all construction=false", len(geo) == 5 and all(x.get("construction") is False for x in geo),
              f"{[(x.get('index'), x.get('construction')) for x in geo]}")
    fit0 = await m.fit(doc)
    log.note(f"before fit: {fit0}")
    log.write({"shot": shot("tc-03-08-before.png")})
    log.write({"edit_before": edit_capture("PlateProfile", "tc-03-08-edit-before.png")})

    t1 = await m.call("sketch_toggle_construction", {"doc": doc, "sketch": "PlateProfile", "geo_ids": [4]})
    mid = await m.call("query_sketch_info", {"doc": doc, "sketch": "PlateProfile"})
    vmid = await m.call("verify_sketch", {"doc": doc, "sketch": "PlateProfile"})
    log.write({"shot_mid": shot("tc-03-08-mid.png")})
    log.write({"edit_mid": edit_capture("PlateProfile", "tc-03-08-edit-mid.png")})
    t2 = await m.call("sketch_toggle_construction", {"doc": doc, "sketch": "PlateProfile", "geo_ids": [4]})
    end = await m.call("query_sketch_info", {"doc": doc, "sketch": "PlateProfile"})
    vend = await m.call("verify_sketch", {"doc": doc, "sketch": "PlateProfile"})

    log.check("first toggle commits OK rolled_back=false", t1.get("status") == "OK" and mut(t1).get("rolled_back") is False, short(t1))
    mg = sc(mid).get("geometry") or []
    log.check("after first toggle index 4 construction=true", len(mg) == 5 and mg[4].get("construction") is True, f"{[(x.get('index'), x.get('construction')) for x in mg]}")
    log.check("indexes 0..3 still construction=false", all(x.get("construction") is False for x in mg[:4]), "")
    eg = sc(end).get("geometry") or []
    log.check("after second toggle index 4 construction=false", len(eg) == 5 and eg[4].get("construction") is False,
              f"t2={t2.get('status')} {[(x.get('index'), x.get('construction')) for x in eg]}")
    d1 = (sc(vmid).get("subject") or {}).get("dof")
    d2 = (sc(vend).get("subject") or {}).get("dof")
    log.check("dof=0 after each toggle", d1 == 0 and d2 == 0, f"mid={vmid.get('status')} dof={d1}; end={vend.get('status')} dof={d2}")
    r = await m.call("sketch_toggle_construction", {"doc": doc, "sketch": "PlateProfile", "geo_ids": [4, 4]})
    log.check("geo_ids [4,4] INVALID_INPUT naming listed-twice message",
              r.get("status") == "INVALID_INPUT" and "is listed twice; a double toggle is a no-op" in json.dumps(r.get("detail")), short(r))
    r = await m.call("sketch_toggle_construction", {"doc": doc, "sketch": "PlateProfile", "geo_ids": [99]})
    log.check("geo_ids [99] INVALID_INPUT naming outside (0..4)",
              r.get("status") == "INVALID_INPUT" and "is outside the sketch (0..4)" in json.dumps(r.get("detail")), short(r))
    fit = await m.fit(doc)
    log.note(f"after fit: {fit}")
    log.write({"shot": shot("tc-03-08-after.png")})
    log.write({"edit_after": edit_capture("PlateProfile", "tc-03-08-edit-after.png")})


go("tc-03-08", body)
