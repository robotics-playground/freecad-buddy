from tc03lib import *  # noqa: F401,F403


async def body(m, log):
    doc = await new_doc(m, "BracketPlate")
    await rect_sketch(m, doc, "PlateProfile")
    v0 = await m.call("verify_sketch", {"doc": doc, "sketch": "PlateProfile"})
    s0 = sc(v0).get("subject") or {}
    log.check("Given dof=0 conflicting=[]", s0.get("dof") == 0 and s0.get("conflicting") == [], f"dof={s0.get('dof')} conflicting={s0.get('conflicting')}")
    n0 = s0.get("constraint_count")
    log.note(f"Given constraint_count={n0}")
    fit0 = await m.fit(doc)
    log.note(f"before fit: {fit0}")
    log.write({"shot": shot("tc-03-16-before.png")})
    log.write({"edit_before": edit_capture("PlateProfile", "tc-03-16-edit-before.png")})

    e = await m.call("sketch_add_constraint", {"doc": doc, "sketch": "PlateProfile", "constraints": [
        {"type": "DistanceX", "first": 0, "first_pos": 1, "second": 0, "second_pos": 2, "value": {"value": 45, "unit": "mm"}, "name": "ConflictWidth"}]})
    log.check("status=SPEC_FAILED", e.get("status") == "SPEC_FAILED", short(e))
    log.check("rolled_back=true", mut(e).get("rolled_back") is True, f"rolled_back={mut(e).get('rolled_back')} proven={mut(e).get('rollback_proven')}")
    expl = pv(e).get("explanation") or ""
    log.check("explanation starts 'verify_sketch failed on PlateProfile (dof='", expl.startswith("verify_sketch failed on PlateProfile (dof="), expl)
    blob = json.dumps({"detail": e.get("detail"), "post_verify": pv(e), "sketch_state": sc(e).get("sketch_state")})
    st = sc(e).get("sketch_state") or {}
    log.check("failure detail or sketch_state names the conflicting solver ids",
              bool(st.get("conflicting")) or "conflict" in blob.lower(), f"sketch_state.conflicting={st.get('conflicting')} detail={json.dumps(e.get('detail'))[:200]}")
    i1 = await m.call("query_sketch_info", {"doc": doc, "sketch": "PlateProfile"})
    log.check("no ConflictWidth", not any(c.get("name") == "ConflictWidth" for c in sc(i1).get("constraints") or []), "")
    v1 = await m.call("verify_sketch", {"doc": doc, "sketch": "PlateProfile"})
    s1 = sc(v1).get("subject") or {}
    log.check("constraint_count back to Given", s1.get("constraint_count") == n0, f"{s1.get('constraint_count')} vs {n0}")
    log.check("OK dof=0 conflicting=[]", v1.get("status") == "OK" and s1.get("dof") == 0 and s1.get("conflicting") == [], short(v1))
    fit = await m.fit(doc)
    log.note(f"after fit: {fit}")
    log.write({"shot": shot("tc-03-16-after.png")})
    log.write({"edit_after": edit_capture("PlateProfile", "tc-03-16-edit-after.png")})


go("tc-03-16", body)
