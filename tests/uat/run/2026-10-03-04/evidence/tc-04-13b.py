from tc04lib import *  # noqa: F401,F403

DOC = [json.loads(l)["doc"] for l in open(EVIDENCE / "tc-04-13-mcp.jsonl", encoding="utf-8") if '"doc": "fcb-doc' in l and l.startswith('{"doc"')][-1]


async def body(m, log):
    h = DOC
    log.note(f"supplement on the TC-04-13 document {h}: substitute modes this build's attach engines implement for the literal subelements")
    d2 = await m.call("feature_datum", {"doc": h, "body": "PlateBody", "name": "EdgeAxis", "kind": "axis",
                                        "attachment": sel("PlatePad", "Edge1"), "map_mode": "TwoPointLine"})
    d3 = await m.call("feature_datum", {"doc": h, "body": "PlateBody", "name": "CornerPoint", "kind": "point",
                                        "attachment": sel("PlatePad", "Vertex1"), "map_mode": "Vertex"})
    log.check("EdgeAxis (TwoPointLine on Edge1) OK", ok_commit(d2), short(d2, 300))
    log.check("CornerPoint (Vertex on Vertex1) OK", ok_commit(d3), short(d3, 300))
    tr = await m.call("query_tree_summary", {"doc": h, "depth": 3})
    kids = [c.get("name") for n in (sc(tr).get("tree") or []) if n.get("name") == "PlateBody" for c in (n.get("children") or [])]
    log.check("tree lists RaisedPlane, EdgeAxis, CornerPoint, FaceCS under PlateBody",
              all(n in kids for n in ("RaisedPlane", "EdgeAxis", "CornerPoint", "FaceCS")), kids)
    mp = await m.call("query_mass_properties", {"doc": h, "object": "PlatePad"})
    log.check("plate solid unchanged vol 12000", near(vol(mp), 12000.0), vol(mp))
    await capture(m, h, "tc-04-13-after.png")


go("tc-04-13b", body)
