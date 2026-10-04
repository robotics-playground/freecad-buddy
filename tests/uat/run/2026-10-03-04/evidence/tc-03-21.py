from tc03lib import *  # noqa: F401,F403


async def body(m, log):
    doc = await new_doc(m, "BracketPlate")
    await plate(m, doc)  # PlatePad exists for the selector When; PlateProfile is its consumed sketch
    v0 = await m.call("verify_sketch", {"doc": doc, "sketch": "PlateProfile"})
    log.check("Given verify_sketch PlateProfile OK", v0.get("status") == "OK", short(v0))
    t0 = await m.call("query_tree_summary", {"doc": doc, "depth": 2})
    i0 = await m.call("query_sketch_info", {"doc": doc, "sketch": "PlateProfile"})
    fit0 = await m.fit(doc)
    log.note(f"before fit: {fit0}")
    log.write({"shot": shot("tc-03-21-before.png")})

    a = await m.call("sketch_create", {"doc": doc, "name": "ExtraKey", "plane": "XY", "visible": True})
    b = await m.call("sketch_add_geometry", {"doc": doc, "sketch": "PlateProfile", "geometry": [{"kind": "point", "start": [5, 5], "color": "red"}]})
    c = await m.call("sketch_add_constraint", {"doc": doc, "sketch": "PlateProfile", "constraints": [{"type": "Horizontal", "first": 0, "weight": 2}]})
    d = await m.call("sketch_add_external_geometry", {"doc": doc, "sketch": "PlateProfile",
                                                      "edge": {"kind": "mapped_name", "object": "PlatePad", "mapped_name": "Edge1", "hint": "top"}})
    for label, env, key in (("top-level visible", a, "visible"), ("geometry color", b, "color"), ("constraint weight", c, "weight"), ("selector hint", d, "hint")):
        log.check(f"{label} rejected at schema (protocol error, no status, no mutation)", schema_reject(env) and key in (env.get("_raw") or ""), short(env))
    t1 = await m.call("query_tree_summary", {"doc": doc, "depth": 2})
    log.check("tree unchanged, no ExtraKey", json.dumps(sc(t1).get("tree")) == json.dumps(sc(t0).get("tree")) and "ExtraKey" not in json.dumps(sc(t1)), "")
    i1 = await m.call("query_sketch_info", {"doc": doc, "sketch": "PlateProfile"})
    log.check("PlateProfile geometry and constraints unchanged",
              sc(i1).get("geometry") == sc(i0).get("geometry") and sc(i1).get("constraints") == sc(i0).get("constraints"), "")
    fit = await m.fit(doc)
    log.note(f"after fit: {fit}")
    log.write({"shot": shot("tc-03-21-after.png")})
    log.write({"edit_after": edit_capture("PlateProfile", "tc-03-21-edit-after.png", parent=["PlateBody", "PlatePad"])})


go("tc-03-21", body)
