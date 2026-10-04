from tc03lib import *  # noqa: F401,F403


async def body(m, log):
    doc = await new_doc(m, "BracketPlate")
    await m.call("sketch_create", {"doc": doc, "name": "PlateProfile", "plane": "XY"})
    g = await m.call("query_sketch_info", {"doc": doc, "sketch": "PlateProfile"})
    log.check("Given PlateProfile geometry=[]", sc(g).get("geometry") == [], f"geometry={sc(g).get('geometry')}")

    e = await m.call("sketch_add_geometry", {"doc": doc, "sketch": "PlateProfile",
                                             "geometry": RECT_GEOMETRY, "constraints": rect_constraints()})
    v = await m.call("verify_sketch", {"doc": doc, "sketch": "PlateProfile"})
    subj = sc(v).get("subject") or {}

    log.check("call commits OK rolled_back=false", e.get("status") == "OK" and mut(e).get("rolled_back") is False, short(e))
    log.check("verify_sketch OK dof=0 fully_constrained=true",
              v.get("status") == "OK" and subj.get("dof") == 0 and subj.get("fully_constrained") is True,
              f"status={v.get('status')} dof={subj.get('dof')} fc={subj.get('fully_constrained')}")
    checks = sc(v).get("checks") or []
    fc = [c for c in checks if c.get("id") == "sketch.fully_constrained"]
    log.check("passed check id=sketch.fully_constrained expected=true",
              bool(fc) and fc[0].get("passed") is True and fc[0].get("expected") is True, json.dumps(fc)[:300])
    p = pv(e)
    log.check("post_verify fully_constrained=true passed=true",
              p.get("fully_constrained") is True and p.get("passed") is True, json.dumps(p)[:300])
    log.check("geometry_count=4 constraint_count=11",
              subj.get("geometry_count") == 4 and subj.get("constraint_count") == 11,
              f"geometry_count={subj.get('geometry_count')} constraint_count={subj.get('constraint_count')}")
    log.check("conflicting=[] malformed=[]", subj.get("conflicting") == [] and subj.get("malformed") == [],
              f"conflicting={subj.get('conflicting')} malformed={subj.get('malformed')}")
    info = await m.call("query_sketch_info", {"doc": doc, "sketch": "PlateProfile"})
    cons = sc(info).get("constraints") or []
    named = {c.get("name"): c for c in cons if c.get("name")}
    log.check("PlateWidth and PlateDepth present with driving=true",
              all(n in named and named[n].get("driving") is True for n in ("PlateWidth", "PlateDepth")),
              json.dumps({k: {"driving": c.get("driving"), "value": c.get("value")} for k, c in named.items()}))
    st = sc(e).get("sketch_state") or {}
    log.check("sketch_state readable=true dof=0 fully_constrained=true",
              st.get("readable") is True and st.get("dof") == 0 and st.get("fully_constrained") is True, json.dumps(st)[:300])
    fit = await m.fit(doc)
    log.note(f"fit: {fit}")
    log.write({"shot": shot("tc-03-04-after.png")})
    log.write({"edit": edit_capture("PlateProfile", "tc-03-04-edit-PlateProfile.png")})


go("tc-03-04", body)
