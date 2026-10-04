from tc03lib import *  # noqa: F401,F403


async def body(m, log):
    doc = sc(await m.call("document_create", {"label": "BracketPlate"})).get("doc")
    log.check("Given document_create returns a handle", bool(doc), doc)
    b = await m.call("feature_body_create", {"doc": doc, "name": "PlateBody"})
    log.check("Given feature_body_create PlateBody OK", b.get("status") == "OK", short(b))

    e = await m.call("sketch_create", {"doc": doc, "name": "PlateProfile", "plane": "XY", "body": "PlateBody"})
    tree = await m.call("query_tree_summary", {"doc": doc, "depth": 3})

    log.check("create commits OK rolled_back=false", e.get("status") == "OK" and mut(e).get("rolled_back") is False,
              f"status={e.get('status')} rolled_back={mut(e).get('rolled_back')}")
    roots = sc(tree).get("tree") or []
    root_names = [n.get("name") for n in roots]
    body_node = next((n for n in roots if n.get("name") == "PlateBody"), {})
    child_names = json.dumps(body_node.get("children"))
    log.check("PlateProfile is a child of PlateBody, not at root",
              "PlateProfile" in child_names and "PlateProfile" not in root_names,
              f"roots={root_names} body_children={child_names[:300]}")
    obj = await m.call("query_object", {"doc": doc, "object": "PlateBody"})
    props = json.dumps(sc(obj))
    tip = (sc(obj).get("properties") or {}).get("Tip")
    log.check("PlateBody reports no Tip feature", tip in (None, "", "None", {}), f"Tip={json.dumps(tip)[:200]} status={obj.get('status')}")
    v = await m.call("verify_sketch", {"doc": doc, "sketch": "PlateProfile"})
    subj = sc(v).get("subject") or {}
    log.check("verify_sketch PlateProfile OK dof=0", v.get("status") == "OK" and subj.get("dof") == 0,
              f"status={v.get('status')} dof={subj.get('dof')}")
    orphan = await m.call("sketch_create", {"doc": doc, "name": "Orphan", "plane": "XY", "body": "NoSuchBody"})
    log.check("unknown body INVALID_INPUT, no mutation.snapshot_path",
              orphan.get("status") == "INVALID_INPUT" and not mut(orphan).get("snapshot_path"), short(orphan))
    fit = await m.fit(doc)
    log.note(f"fit: {fit}")
    log.write({"shot": shot("tc-03-02-after.png")})
    log.write({"edit": edit_capture("PlateProfile", "tc-03-02-edit-PlateProfile.png")})


go("tc-03-02", body)
