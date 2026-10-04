from tc04lib import *  # noqa: F401,F403


async def body(m, log):
    h = sc(await m.call("document_create", {"label": "Datums"})).get("doc")
    await body_pad(m, h, "PlateBody", "PlateProfile", "PlatePad", rect_profile(0, 0, 60, 40), 5)
    mp = await m.call("query_mass_properties", {"doc": h, "object": "PlatePad"})
    log.check("Given PlatePad vol 12000", near(vol(mp), 12000.0), vol(mp))
    log.note("face names come from the outside oracle (query_object lists properties only): Face6 = top z=5, Edge1 = vertical edge at (0,0), Vertex1 = (0,0,0)")
    d1 = await m.call("feature_datum", {"doc": h, "body": "PlateBody", "name": "RaisedPlane", "kind": "plane",
                                        "attachment": sel("PlatePad", "Face6"), "offset": q(10)})
    d2 = await m.call("feature_datum", {"doc": h, "body": "PlateBody", "name": "EdgeAxis", "kind": "axis",
                                        "attachment": sel("PlatePad", "Edge1"), "map_mode": "ObjectXY"})
    d3 = await m.call("feature_datum", {"doc": h, "body": "PlateBody", "name": "CornerPoint", "kind": "point",
                                        "attachment": sel("PlatePad", "Vertex1"), "map_mode": "ObjectOrigin"})
    d4 = await m.call("feature_datum", {"doc": h, "body": "PlateBody", "name": "FaceCS", "kind": "cs",
                                        "attachment": sel("PlatePad", "Face6")})
    log.check("all four kinds commit OK rolled_back=false", all(ok_commit(e) for e in (d1, d2, d3, d4)),
              [short(e, 300) for e in (d1, d2, d3, d4)])
    pl = await m.call("query_placement", {"doc": h, "object": "RaisedPlane"})
    log.write({"RaisedPlane_placement": sc(pl)})
    pos = (sc(pl).get("global") or sc(pl).get("local") or {}).get("position") or {}
    log.check("RaisedPlane position.z = 15 mm", near((pos.get("z") or {}).get("value"), 15) and (pos.get("z") or {}).get("unit") == "mm",
              json.dumps(sc(pl))[:500])
    qo = await m.call("query_object", {"doc": h, "object": "RaisedPlane"})
    props = sc(qo).get("properties") or {}
    log.check("MapMode=FlatFace", props.get("MapMode") == "FlatFace", props.get("MapMode"))
    sup = props.get("AttachmentSupport")
    log.check("AttachmentSupport names PlatePad and Face6", "PlatePad" in json.dumps(sup) and "Face6" in json.dumps(sup), json.dumps(sup))
    mm = await m.call("query_mass_properties", {"doc": h, "object": "RaisedPlane"})
    log.check("datum carries no solid volume", mm.get("status") != "OK" or not sc(mm).get("solid") or not vol(mm), short(mm, 300) + " " + json.dumps(sc(mm))[:300])
    tr = await m.call("query_tree_summary", {"doc": h, "depth": 3})
    t = tree_names(tr)
    log.check("tree lists RaisedPlane, EdgeAxis, CornerPoint, FaceCS under PlateBody", all(n in t for n in ("RaisedPlane", "EdgeAxis", "CornerPoint", "FaceCS")), t[:800])
    sch = await m.call("feature_datum", {"doc": h, "body": "PlateBody", "name": "CurveDatum", "kind": "curve", "attachment": sel("PlatePad", "Edge1")})
    log.check("kind curve schema reject", schema_reject(sch), short(sch))
    before = set(snap_temp())
    bad = await m.call("feature_datum", {"doc": h, "body": "PlateBody", "name": "BadPoint", "kind": "point",
                                         "attachment": sel("PlatePad", "Face6"), "map_mode": "FlatFace"})
    log.check("map_mode the kind cannot use INVALID_INPUT 'is not implemented for kind', no snapshot",
              bad.get("status") == "INVALID_INPUT" and "is not implemented for kind" in detail_msg(bad) and not mut(bad).get("snapshot_path")
              and set(snap_temp()) == before, short(bad))
    await capture(m, h, "tc-04-13-after.png")
    log.write({"doc": h})


go("tc-04-13", body)
