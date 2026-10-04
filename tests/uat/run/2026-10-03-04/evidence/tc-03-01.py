from tc03lib import *  # noqa: F401,F403


async def body(m, log):
    created = await m.call("document_create", {"label": "BracketPlate"})
    doc = sc(created).get("doc")
    log.check("Given document_create returns a handle", bool(doc), doc)

    envs = {}
    for name, plane in (("PlateProfileXY", "XY"), ("RibProfileXZ", "XZ"), ("EndProfileYZ", "YZ")):
        envs[name] = await m.call("sketch_create", {"doc": doc, "name": name, "plane": plane})
    graded = await m.call("verify_sketch", {"doc": doc, "sketch": "PlateProfileXY"})

    for name, e in envs.items():
        log.check(f"{name} commits OK rolled_back=false", e.get("status") == "OK" and mut(e).get("rolled_back") is False,
                  f"status={e.get('status')} rolled_back={mut(e).get('rolled_back')}")
    subj = sc(graded).get("subject") or {}
    log.check("verify_sketch PlateProfileXY OK dof=0 fully_constrained=true",
              graded.get("status") == "OK" and subj.get("dof") == 0 and subj.get("fully_constrained") is True,
              f"status={graded.get('status')} dof={subj.get('dof')} fc={subj.get('fully_constrained')}")
    for name, e in envs.items():
        p = pv(e)
        log.check(f"{name} post_verify fully_constrained=true passed=true",
                  p.get("fully_constrained") is True and p.get("passed") is True,
                  f"fully_constrained={p.get('fully_constrained')} passed={p.get('passed')}")
    info = await m.call("query_sketch_info", {"doc": doc, "sketch": "RibProfileXZ"})
    s = sc(info)
    log.check("RibProfileXZ geometry=[] constraints=[]", s.get("geometry") == [] and s.get("constraints") == [],
              f"geometry={s.get('geometry')} constraints={s.get('constraints')}")
    p_yz = await m.call("query_placement", {"doc": doc, "object": "EndProfileYZ"})
    p_xy = await m.call("query_placement", {"doc": doc, "object": "PlateProfileXY"})
    r_yz = json.dumps(sc(p_yz).get("rotation") or sc(p_yz).get("placement"))
    r_xy = json.dumps(sc(p_xy).get("rotation") or sc(p_xy).get("placement"))
    log.check("EndProfileYZ rotation distinct from PlateProfileXY", r_yz != r_xy and r_yz != "null",
              f"YZ={r_yz[:200]} XY={r_xy[:200]}")
    bad = await m.call("sketch_create", {"doc": doc, "name": "BadPlane", "plane": "ZX"})
    log.check("plane ZX is a schema reject", schema_reject(bad), short(bad))
    tree = await m.call("query_tree_summary", {"doc": doc})
    log.check("tree names no BadPlane", "BadPlane" not in json.dumps(sc(tree)), json.dumps(sc(tree))[:400])
    fit = await m.fit(doc)
    log.note(f"fit: {fit}")
    log.write({"shot": shot("tc-03-01-after.png")})
    log.write({"doc": doc})


go("tc-03-01", body)
