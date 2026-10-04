from tc03lib import *  # noqa: F401,F403


async def body(m, log):
    doc = await new_doc(m, "BracketPlate")
    await rect_sketch(m, doc, "PlateProfile")
    extra = await m.call("sketch_add_constraint", {"doc": doc, "sketch": "PlateProfile", "constraints": [
        {"type": "Horizontal", "first": 0},
        {"type": "Distance", "first": 0, "first_pos": 1, "second": 0, "second_pos": 2, "value": {"value": 60, "unit": "mm"}, "name": "SpareWidth"}]})
    log.note(f"Given extras (redundant Horizontal + SpareWidth): {extra.get('status')} ids={sc(extra).get('constraint_ids')} {json.dumps(extra.get('detail'))[:200]}")
    i0 = await m.call("query_sketch_info", {"doc": doc, "sketch": "PlateProfile"})
    c0 = [(c.get("id"), c.get("type"), c.get("name")) for c in sc(i0).get("constraints") or []]
    log.check("Given lists SpareWidth and a Horizontal at a known id (12)",
              any(n == "SpareWidth" for _, _, n in c0) and (12, "Horizontal", "") in [(i, t, n or "") for i, t, n in c0], f"{c0}")
    fit0 = await m.fit(doc)
    log.note(f"before fit: {fit0}")
    log.write({"shot": shot("tc-03-11-before.png")})
    log.write({"edit_before": edit_capture("PlateProfile", "tc-03-11-edit-before.png")})

    r1 = await m.call("sketch_remove_constraint", {"doc": doc, "sketch": "PlateProfile", "constraints": [12]})
    i1 = await m.call("query_sketch_info", {"doc": doc, "sketch": "PlateProfile"})
    r2 = await m.call("sketch_remove_constraint", {"doc": doc, "sketch": "PlateProfile", "constraints": ["SpareWidth"]})
    i2 = await m.call("query_sketch_info", {"doc": doc, "sketch": "PlateProfile"})

    log.check("id branch: OK rolled_back=false", r1.get("status") == "OK" and mut(r1).get("rolled_back") is False, short(r1))
    log.check("name branch: OK rolled_back=false", r2.get("status") == "OK" and mut(r2).get("rolled_back") is False, short(r2))
    n0, n1, n2 = len(c0), len(sc(i1).get("constraints") or []), len(sc(i2).get("constraints") or [])
    log.check("count drops by one each time", n1 == n0 - 1 and n2 == n1 - 1, f"{n0} -> {n1} -> {n2}")
    log.check("no constraint named SpareWidth", not any(c.get("name") == "SpareWidth" for c in sc(i2).get("constraints") or []), "")
    z = await m.call("sketch_remove_constraint", {"doc": doc, "sketch": "PlateProfile", "constraints": [0]})
    log.check("constraints [0] schema reject", schema_reject(z), short(z))
    u = await m.call("sketch_remove_constraint", {"doc": doc, "sketch": "PlateProfile", "constraints": ["NoSuchConstraint"]})
    log.check("unknown name INVALID_INPUT naming message",
              u.get("status") == "INVALID_INPUT" and "no constraint named 'NoSuchConstraint' in the sketch" in json.dumps(u.get("detail")), short(u))
    w = await m.call("sketch_remove_constraint", {"doc": doc, "sketch": "PlateProfile", "constraints": [{"id": 3}]})
    log.check("constraints [{id:3}] schema reject", schema_reject(w), short(w))
    fit = await m.fit(doc)
    log.note(f"after fit: {fit}")
    log.write({"shot": shot("tc-03-11-after.png")})
    log.write({"edit_after": edit_capture("PlateProfile", "tc-03-11-edit-after.png")})


go("tc-03-11", body)
