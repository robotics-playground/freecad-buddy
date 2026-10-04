from tc04lib import *  # noqa: F401,F403


def bb(mp):
    b = sc(mp).get("bbox") or {}
    return {k: (v or {}).get("value") for k, v in b.items()}


async def body(m, log):
    h = sc(await m.call("document_create", {"label": "Mid"})).get("doc")
    await m.call("feature_body_create", {"doc": h, "name": "MidBody"})
    await sketch(m, h, "MidProfile", "MidBody", rect_profile(0, 0, 20, 30))
    vsk = await m.call("verify_sketch", {"doc": h, "sketch": "MidProfile"})
    log.check("Given MidProfile dof=0", (sc(vsk).get("subject") or {}).get("dof") == 0, short(vsk))
    log.note("Given comparison: TC-04-02 recorded BlockPad volume 6000.0, bbox z 0..10 (tc-04-02-mcp.jsonl)")
    pad = await m.call("feature_pad", {"doc": h, "body": "MidBody", "profile": "MidProfile", "name": "MidPad",
                                       "length": q(10), "midplane": True})
    mp = await m.call("query_mass_properties", {"doc": h, "object": "MidPad"})
    pl = await m.call("query_placement", {"doc": h, "object": "MidPad"})
    log.write({"mass": sc(mp), "placement": sc(pl)})
    log.check("midplane pad OK rolled_back=false", ok_commit(pad), short(pad))
    log.check("volume 6000.0", near(vol(mp), 6000.0), vol(mp))
    bbox = ss(pad).get("bbox")
    log.check("shape_summary bbox [20,30,10]", isinstance(bbox, list) and all(near(a, b) for a, b in zip(bbox, [20, 30, 10])), bbox)
    b = bb(mp)
    log.check("bbox z -5..+5", near(b.get("zmin"), -5) and near(b.get("zmax"), 5), b)
    com = (sc(mp).get("com") or {}).get("z") or {}
    log.check("com.z = 0 mm", abs(float(com.get("value", 99))) < 1e-6 and com.get("unit") == "mm", com)
    vs = await m.call("verify_shape", {"doc": h, "object": "MidPad"})
    log.check("verify_shape OK", vs.get("status") == "OK", short(vs))
    await capture(m, h, "tc-04-03-after.png")
    log.write({"doc": h})


go("tc-04-03", body)
