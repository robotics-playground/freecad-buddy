from tc04lib import *  # noqa: F401,F403


async def body(m, log):
    h = sc(await m.call("document_create", {"label": "Loose"})).get("doc")
    await m.call("feature_body_create", {"doc": h, "name": "LooseBody"})
    c, a = await sketch(m, h, "LooseProfile", "LooseBody", rect_profile(10, 10, 20, 30))
    v = await m.call("verify_sketch", {"doc": h, "sketch": "LooseProfile"})
    log.note(f"fully constrained LooseProfile built through MCP: add={short(a)} verify={short(v)} dof={(sc(v).get('subject') or {}).get('dof')}")
    log.note("MCP cannot leave a sketch under-constrained (sketch_* post_verify rolls back dof>0), so the two position "
             "constraints are deleted in FreeCAD's own Python console (GUI, cua-driver type_text) - fixture step only")
    log.write({"doc": h})


go("tc-04-23-given", body)
