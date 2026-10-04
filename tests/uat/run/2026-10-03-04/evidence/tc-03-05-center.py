from tc03lib import *  # noqa: F401,F403

GEOMETRY = [
    {"kind": "line_segment", "start": [0, 0], "end": [40, 0]},
    {"kind": "circle", "center": [20, 20], "radius": {"value": 2.5, "unit": "mm"}},
    {"kind": "arc_of_circle", "center": [50, 20], "radius": {"value": 8, "unit": "mm"},
     "start_angle": {"value": 0, "unit": "deg"}, "end_angle": {"value": 90, "unit": "deg"}},
    {"kind": "point", "center": [10, 30]},
]
CONSTRAINTS = [
    {"type": "Coincident", "first": 0, "first_pos": 1, "second": -1, "second_pos": 1},
    {"type": "Horizontal", "first": 0},
    {"type": "DistanceX", "first": 0, "first_pos": 1, "second": 0, "second_pos": 2, "value": {"value": 40, "unit": "mm"}},
    {"type": "DistanceX", "first": 1, "first_pos": 3, "value": {"value": 20, "unit": "mm"}},
    {"type": "DistanceY", "first": 1, "first_pos": 3, "value": {"value": 20, "unit": "mm"}},
    {"type": "Radius", "first": 1, "value": {"value": 2.5, "unit": "mm"}},
    {"type": "DistanceX", "first": 2, "first_pos": 3, "value": {"value": 50, "unit": "mm"}},
    {"type": "DistanceY", "first": 2, "first_pos": 3, "value": {"value": 20, "unit": "mm"}},
    {"type": "Radius", "first": 2, "value": {"value": 8, "unit": "mm"}},
    {"type": "DistanceX", "first": 2, "first_pos": 1, "value": {"value": 58, "unit": "mm"}},
    {"type": "DistanceY", "first": 2, "first_pos": 1, "value": {"value": 20, "unit": "mm"}},
    {"type": "DistanceX", "first": 2, "first_pos": 2, "value": {"value": 50, "unit": "mm"}},
    {"type": "DistanceY", "first": 2, "first_pos": 2, "value": {"value": 28, "unit": "mm"}},
    {"type": "DistanceX", "first": 3, "first_pos": 1, "value": {"value": 10, "unit": "mm"}},
    {"type": "DistanceY", "first": 3, "first_pos": 1, "value": {"value": 30, "unit": "mm"}},
]


async def body(m, log):
    doc = await new_doc(m, "BracketPlate")
    await m.call("sketch_create", {"doc": doc, "name": "MixedProfile", "plane": "XY"})
    g = await m.call("query_sketch_info", {"doc": doc, "sketch": "MixedProfile"})
    log.check("Given MixedProfile geometry=[]", sc(g).get("geometry") == [], f"geometry={sc(g).get('geometry')}")

    e = await m.call("sketch_add_geometry", {"doc": doc, "sketch": "MixedProfile",
                                             "geometry": GEOMETRY, "constraints": CONSTRAINTS})
    log.note(f"mutation status={e.get('status')} detail={json.dumps(e.get('detail'))[:400]}")
    info = await m.call("query_sketch_info", {"doc": doc, "sketch": "MixedProfile"})
    geo = sc(info).get("geometry") or []
    log.check("4 geometry entries at index 0..3", [x.get("index") for x in geo] == [0, 1, 2, 3],
              f"indexes={[x.get('index') for x in geo]}")
    types = [x.get("type") for x in geo]
    log.check("types map to FreeCAD types in order",
              types == ["Part::GeomLineSegment", "Part::GeomCircle", "Part::GeomArcOfCircle", "Part::GeomPoint"], f"types={types}")
    created = sc(e).get("geo_ids") or sc(e).get("created") or sc(e).get("geometry")
    log.check("mutation envelope names created geometry starting at 0",
              isinstance(created, list) and len(created) >= 1 and (created[0] == 0 or (isinstance(created[0], dict) and created[0].get("index", created[0].get("geo_id")) == 0)),
              f"structured keys={list(sc(e).keys())} created={json.dumps(created)[:200]}")
    v = await m.call("verify_sketch", {"doc": doc, "sketch": "MixedProfile"})
    subj = sc(v).get("subject") or {}
    log.check("verify_sketch OK dof=0", v.get("status") == "OK" and subj.get("dof") == 0,
              f"status={v.get('status')} dof={subj.get('dof')} fc={subj.get('fully_constrained')}")
    r = await m.call("sketch_add_geometry", {"doc": doc, "sketch": "MixedProfile", "geometry": [{"kind": "ellipse", "center": [0, 0]}]})
    log.check("kind ellipse is a schema reject", schema_reject(r), short(r))
    r4 = await m.call("sketch_add_geometry", {"doc": doc, "sketch": "MixedProfile", "geometry": [{"kind": "point", "start": [0, 0, 0, 0]}]})
    r1 = await m.call("sketch_add_geometry", {"doc": doc, "sketch": "MixedProfile", "geometry": [{"kind": "point", "start": [0]}]})
    log.check("start [0,0,0,0] (maxItems 3) and [0] (minItems 2) are schema rejects",
              schema_reject(r4) and schema_reject(r1), f"{short(r4, 200)} || {short(r1, 200)}")
    rb = await m.call("sketch_add_geometry", {"doc": doc, "sketch": "MixedProfile",
                                              "geometry": [{"kind": "circle", "center": [5, 5], "radius": 2.5}]})
    log.check("bare number radius is a schema reject", schema_reject(rb), short(rb))
    info2 = await m.call("query_sketch_info", {"doc": doc, "sketch": "MixedProfile"})
    log.note(f"geometry count after rejects: {len(sc(info2).get('geometry') or [])}")
    fit = await m.fit(doc)
    log.note(f"fit: {fit}")
    log.write({"shot": shot("tc-03-05-after.png")})
    log.write({"edit": edit_capture("MixedProfile", "tc-03-05-edit-MixedProfile.png")})


go("tc-03-05", body)  # variant: point uses center (product contract); as-is run kept as tc-03-05-asis-*
