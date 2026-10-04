from tc03lib import *  # noqa: F401,F403

# Two holes 40 mm apart on the X axis, and a 40 mm rib line from the origin at 45 deg to the H axis.
GEO = [{"kind": "circle", "center": [0, 0], "radius": {"value": 2.5, "unit": "mm"}},
       {"kind": "circle", "center": [40, 0], "radius": {"value": 2.5, "unit": "mm"}},
       {"kind": "line_segment", "start": [0, 0], "end": [28.284, 28.284]}]
CON = [{"type": "Coincident", "first": 0, "first_pos": 3, "second": -1, "second_pos": 1},
       {"type": "Radius", "first": 0, "value": {"value": 2.5, "unit": "mm"}},
       {"type": "PointOnObject", "first": 1, "first_pos": 3, "second": -1},
       {"type": "Distance", "first": 0, "first_pos": 3, "second": 1, "second_pos": 3, "value": {"value": 40, "unit": "mm"}, "name": "HoleSpacing"},
       {"type": "Radius", "first": 1, "value": {"value": 2.5, "unit": "mm"}},
       {"type": "Coincident", "first": 2, "first_pos": 1, "second": -1, "second_pos": 1},
       {"type": "Distance", "first": 2, "first_pos": 1, "second": 2, "second_pos": 2, "value": {"value": 40, "unit": "mm"}},
       {"type": "Angle", "first": -1, "second": 2, "value": {"value": 45, "unit": "deg"}, "name": "RibAngle"}]


def datum(info: dict, name: str) -> dict:
    return next((c for c in sc(info).get("constraints") or [] if c.get("name") == name), {})


async def body(m, log):
    doc = await new_doc(m, "BracketPlate")
    await m.call("sketch_create", {"doc": doc, "name": "BracketProfile", "plane": "XY"})
    g = await m.call("sketch_add_geometry", {"doc": doc, "sketch": "BracketProfile", "geometry": GEO, "constraints": CON})
    log.note(f"Given build: {g.get('status')} {json.dumps(g.get('detail'))[:200]}")
    i0 = await m.call("query_sketch_info", {"doc": doc, "sketch": "BracketProfile"})
    hs, ra = datum(i0, "HoleSpacing"), datum(i0, "RibAngle")
    log.check("Given HoleSpacing unit mm and RibAngle unit deg", (hs.get("value") or {}).get("unit") == "mm" and (ra.get("value") or {}).get("unit") == "deg", json.dumps([hs, ra]))
    fit0 = await m.fit(doc)
    log.note(f"before fit: {fit0}")
    log.write({"shot": shot("tc-03-18-before.png")})
    log.write({"edit_before": edit_capture("BracketProfile", "tc-03-18-edit-before.png")})

    a = await m.call("sketch_set_datum", {"doc": doc, "sketch": "BracketProfile", "constraint": "HoleSpacing", "value": {"value": 10, "unit": "deg"}})
    b = await m.call("sketch_add_geometry", {"doc": doc, "sketch": "BracketProfile", "geometry": [{"kind": "circle", "center": [20, 20], "radius": 2.5}]})
    c = await m.call("sketch_set_datum", {"doc": doc, "sketch": "BracketProfile", "constraint": "HoleSpacing", "value": {"unit": "mm"}})

    log.check("deg on Distance non-OK", a.get("status") != "OK" and not a.get("_isError"), short(a))
    log.check("refusal names the allowed unit for that constraint type", "mm" in json.dumps(a.get("detail")), json.dumps(a.get("detail"))[:300])
    rd = await m.call("sketch_add_geometry", {"doc": doc, "sketch": "BracketProfile", "geometry": [{"kind": "circle", "center": [20, 20], "radius": {"value": 2.5, "unit": "deg"}}]})
    log.check("radius {2.5 deg} schema reject", schema_reject(rd), short(rd))
    log.check("bare number radius schema reject", schema_reject(b), short(b))
    log.check("missing value schema reject", schema_reject(c), short(c))
    x = await m.call("sketch_set_datum", {"doc": doc, "sketch": "BracketProfile", "constraint": "HoleSpacing", "value": {"value": 10, "unit": "mm", "tolerance": 0.1}})
    log.check("extra key tolerance schema reject", schema_reject(x), short(x))
    i1 = await m.call("query_sketch_info", {"doc": doc, "sketch": "BracketProfile"})
    log.check("HoleSpacing still {40 mm}", datum(i1, "HoleSpacing").get("value") == {"value": 40.0, "unit": "mm"}, json.dumps(datum(i1, "HoleSpacing")))
    ok = await m.call("sketch_set_datum", {"doc": doc, "sketch": "BracketProfile", "constraint": "RibAngle", "value": {"value": 30, "unit": "deg"}})
    log.check("RibAngle 30 deg OK", ok.get("status") == "OK", short(ok))
    fit = await m.fit(doc)
    log.note(f"after fit: {fit}")
    log.write({"shot": shot("tc-03-18-after.png")})
    log.write({"edit_after": edit_capture("BracketProfile", "tc-03-18-edit-after.png")})


go("tc-03-18", body)
