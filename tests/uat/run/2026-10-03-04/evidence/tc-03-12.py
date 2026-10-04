from tc03lib import *  # noqa: F401,F403


async def body(m, log):
    doc = await new_doc(m, "BracketPlate")
    await rect_sketch(m, doc, "PlateProfile")
    v0 = await m.call("verify_sketch", {"doc": doc, "sketch": "PlateProfile"})
    s0 = sc(v0).get("subject") or {}
    log.check("Given OK dof=0 redundant=[]", v0.get("status") == "OK" and s0.get("dof") == 0 and s0.get("redundant") == [], f"{v0.get('status')} dof={s0.get('dof')} redundant={s0.get('redundant')}")
    i0 = await m.call("query_sketch_info", {"doc": doc, "sketch": "PlateProfile"})
    n0 = len(sc(i0).get("constraints") or [])
    fit0 = await m.fit(doc)
    log.note(f"before fit: {fit0}")
    log.write({"shot": shot("tc-03-12-before.png")})
    log.write({"edit_before": edit_capture("PlateProfile", "tc-03-12-edit-before.png")})

    e = await m.call("sketch_add_constraint", {"doc": doc, "sketch": "PlateProfile", "constraints": [{"type": "Horizontal", "first": 0}]})
    v = await m.call("verify_sketch", {"doc": doc, "sketch": "PlateProfile"})
    subj = sc(v).get("subject") or {}
    log.check("mutation OK rolled_back=false (never SPEC_FAILED)", e.get("status") == "OK" and mut(e).get("rolled_back") is False, short(e))
    log.check("verify_sketch status=OK", v.get("status") == "OK", short(v))
    warns = sc(v).get("warnings") or v.get("warnings") or []
    w = [x for x in warns if x.get("id") == "sketch.redundant"]
    log.check("warnings entry id=sketch.redundant with message 'redundant constraints present (warning only)'",
              bool(w) and (w[0].get("detail") or {}).get("message") == "redundant constraints present (warning only)", json.dumps(w)[:300])
    log.check("subject.redundant non-empty", bool(subj.get("redundant")), json.dumps(subj.get("redundant")))
    fc = [c for c in sc(v).get("checks") or [] if c.get("id") == "sketch.fully_constrained"]
    log.check("sketch.fully_constrained passed=true measured=true", bool(fc) and fc[0].get("passed") is True and fc[0].get("measured") is True, json.dumps(fc)[:300])
    i1 = await m.call("query_sketch_info", {"doc": doc, "sketch": "PlateProfile"})
    n1 = len(sc(i1).get("constraints") or [])
    log.check("constraint count one higher", n1 == n0 + 1, f"{n0} -> {n1} (subject.constraint_count={subj.get('constraint_count')})")
    log.check("dof=0", subj.get("dof") == 0, f"dof={subj.get('dof')}")
    fit = await m.fit(doc)
    log.note(f"after fit: {fit}")
    log.write({"shot": shot("tc-03-12-after.png")})
    log.write({"edit_after": edit_capture("PlateProfile", "tc-03-12-edit-after.png")})


go("tc-03-12", body)
