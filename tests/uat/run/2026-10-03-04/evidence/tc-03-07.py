from tc03lib import *  # noqa: F401,F403


def tab_constraints() -> list[dict]:
    c = rect_constraints(10, 40, names=False)
    c[9]["name"] = "TabWidth"
    c[10]["name"] = "TabDepth"
    return c


async def body(m, log):
    doc = await new_doc(m, "BracketPlate")
    await m.call("feature_body_create", {"doc": doc, "name": "TabBody"})
    await m.call("sketch_create", {"doc": doc, "name": "TabProfile", "plane": "XY", "body": "TabBody"})
    g = await m.call("sketch_add_geometry", {"doc": doc, "sketch": "TabProfile", "geometry": rect_geometry(10, 40),
                                             "constraints": tab_constraints()})
    log.note(f"Given sketch build: {g.get('status')}")
    p = await m.call("feature_pad", {"doc": doc, "body": "TabBody", "profile": "TabProfile", "name": "TabPad",
                                     "length": {"value": 5, "unit": "mm"}})
    log.note(f"Given pad: {p.get('status')} {json.dumps(p.get('detail'))[:200]}")
    # a reference (non-driving) dimension for the read-only datum Then
    ref = await m.call("sketch_add_constraint", {"doc": doc, "sketch": "TabProfile", "constraints": [
        {"type": "Distance", "first": 0, "first_pos": 1, "second": 2, "second_pos": 1,
         "value": {"value": 40, "unit": "mm"}, "name": "TabDiagRef", "driving": False}]})
    log.note(f"reference constraint TabDiagRef: {ref.get('status')} {json.dumps(ref.get('detail'))[:200]}")
    info = await m.call("query_sketch_info", {"doc": doc, "sketch": "TabProfile"})
    tw = next((c for c in sc(info).get("constraints") or [] if c.get("name") == "TabWidth"), {})
    log.check("Given TabWidth value {10 mm} driving=true", tw.get("value") == {"value": 10.0, "unit": "mm"} and tw.get("driving") is True, json.dumps(tw))
    mp = await m.call("query_mass_properties", {"doc": doc, "object": "TabPad"})
    v0 = (sc(mp).get("volume") or {}).get("value")
    log.check("Given TabPad volume near 2000", v0 is not None and abs(v0 - 2000) < 2, f"volume={v0}")
    fit0 = await m.fit(doc)
    log.note(f"before fit: {fit0}")
    log.write({"shot": shot("tc-03-07-before.png")})

    e = await m.call("sketch_set_datum", {"doc": doc, "sketch": "TabProfile", "constraint": "TabWidth", "value": {"value": 25, "unit": "mm"}})
    rc = await m.call("document_recompute", {"doc": doc})
    mp2 = await m.call("query_mass_properties", {"doc": doc, "object": "TabPad"})

    log.check("datum edit commits OK rolled_back=false", e.get("status") == "OK" and mut(e).get("rolled_back") is False, short(e))
    info2 = await m.call("query_sketch_info", {"doc": doc, "sketch": "TabProfile"})
    tw2 = next((c for c in sc(info2).get("constraints") or [] if c.get("name") == "TabWidth"), {})
    log.check("TabWidth now {25 mm}", tw2.get("value") == {"value": 25.0, "unit": "mm"}, json.dumps(tw2))
    v = await m.call("verify_sketch", {"doc": doc, "sketch": "TabProfile"})
    subj = sc(v).get("subject") or {}
    log.check("verify_sketch OK dof=0", v.get("status") == "OK" and subj.get("dof") == 0, f"status={v.get('status')} dof={subj.get('dof')}")
    v1 = (sc(mp2).get("volume") or {}).get("value")
    log.check("TabPad volume near 5000 within 0.1%", v1 is not None and abs(v1 - 5000) <= 5, f"recompute={rc.get('status')} volume={v1}")
    vs = await m.call("verify_shape", {"doc": doc, "object": "TabPad"})
    log.check("verify_shape TabPad OK", vs.get("status") == "OK", short(vs))
    both = await m.call("sketch_set_datum", {"doc": doc, "sketch": "TabProfile", "constraint": "TabWidth",
                                             "value": {"value": 25, "unit": "mm"}, "sense": "internal"})
    log.check("value+sense INVALID_INPUT naming exactly-one message",
              both.get("status") == "INVALID_INPUT" and "sketch_set_datum requires exactly one of 'value' and 'sense'" in json.dumps(both.get("detail")), short(both))
    nd = await m.call("sketch_set_datum", {"doc": doc, "sketch": "TabProfile", "constraint": "TabDiagRef",
                                           "value": {"value": 30, "unit": "mm"}})
    log.check("non-driving datum INVALID_INPUT naming read-only message",
              nd.get("status") == "INVALID_INPUT" and "is not driving; its datum is read-only" in json.dumps(nd.get("detail")), short(nd))
    fit = await m.fit(doc)
    log.note(f"after fit: {fit}")
    log.write({"shot": shot("tc-03-07-after.png")})
    log.write({"edit": edit_capture("TabProfile", "tc-03-07-edit-TabProfile.png", parent="TabBody")})


go("tc-03-07", body)
