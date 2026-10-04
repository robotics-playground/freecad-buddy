from tc04lib import *  # noqa: F401,F403


def bb(mp):
    b = sc(mp).get("bbox") or {}
    return {k: (v or {}).get("value") for k, v in b.items()}


async def build(m, label):
    h = sc(await m.call("document_create", {"label": label})).get("doc")
    await m.call("feature_body_create", {"doc": h, "name": "PlateBody"})
    await sketch(m, h, "BaseProfile", "PlateBody", rect_profile(0, 20, 60, 5), plane="XZ")
    base = await m.call("feature_pad", {"doc": h, "body": "PlateBody", "profile": "BaseProfile", "name": "BasePad",
                                        "length": q(40), "midplane": True})
    await sketch(m, h, "RiserProfile", "PlateBody", rect_profile(25, -5, 10, 10))
    return h, base


async def body(m, log):
    log.note("BasePad = 60 x 40 x 5 slab at z 20..25 (XZ sketch, midplane 40); RiserProfile = 10 x 10 square on XY (z=0) below it. "
             "Outside oracle (tc-04-topology-oracle3.txt): BasePad Face1 = bottom face z=20; Face5 = side face y=+20")
    h, base = await build(m, "UpToFace")
    vs0 = await m.call("verify_shape", {"doc": h, "object": "BasePad"})
    vsk = await m.call("verify_sketch", {"doc": h, "sketch": "RiserProfile"})
    log.check("Given BasePad verify_shape OK and RiserProfile dof=0", vs0.get("status") == "OK" and (sc(vsk).get("subject") or {}).get("dof") == 0,
              f"{short(vs0)} base_bbox={ss(base).get('bbox')} {short(vsk)}")
    caps = await m.call("query_capabilities", {})
    log.note(f"live Pad Type enum: {((sc(caps).get('enums') or {}).get('PartDesign::Pad') or {}).get('Type')}")
    s1 = await m.call("feature_pad", {"doc": h, "body": "PlateBody", "profile": "RiserProfile", "name": "RiserPad",
                                      "up_to": "UpToFace", "up_to_face": sel("BasePad", "Face1")})
    s2 = await m.call("feature_pad", {"doc": h, "body": "PlateBody", "profile": "RiserProfile", "name": "BadTypePad", "up_to": "UpToInfinity"})
    log.check("step 1 OK rolled_back=false", ok_commit(s1), short(s1, 400))
    mr = await m.call("query_mass_properties", {"doc": h, "object": "RiserPad"})
    b = bb(mr)
    log.check("extrude stopped at the face: body z 0..25 and vol 12000 + 10x10x20", near(b.get("zmax"), 25) and abs(b.get("zmin", 9)) < 1e-6 and near(vol(mr), 14000.0),
              f"bbox={b} vol={vol(mr)} shape_summary_bbox={ss(s1).get('bbox')}")
    log.check("UpToFace needed no length (step 1 sent none)", ok_commit(s1), "")
    qo = await m.call("query_object", {"doc": h, "object": "RiserPad"})
    p = sc(qo).get("properties") or {}
    log.check("Type=UpToFace and UpToFace names BasePad Face1", p.get("Type") == "UpToFace" and "Face1" in json.dumps(p.get("UpToFace")) and "BasePad" in json.dumps(p.get("UpToFace")),
              f"Type={p.get('Type')} UpToFace={json.dumps(p.get('UpToFace'))}")
    log.check("bad enum INVALID_INPUT \"up_to 'UpToInfinity' is not one of\"", s2.get("status") == "INVALID_INPUT" and "up_to 'UpToInfinity' is not one of" in detail_msg(s2), short(s2))
    tr = await m.call("query_tree_summary", {"doc": h, "depth": 3})
    log.check("rejection pre-transaction: no snapshot_path, no BadTypePad in tree", not mut(s2).get("snapshot_path") and "BadTypePad" not in tree_names(tr), "")
    vs = await m.call("verify_shape", {"doc": h, "object": "RiserPad"})
    log.check("verify_shape RiserPad OK", vs.get("status") == "OK", short(vs))
    # literal TC face name on a copy
    hc, _ = await build(m, "UpToFaceLiteral")
    lit = await m.call("feature_pad", {"doc": hc, "body": "PlateBody", "profile": "RiserProfile", "name": "RiserPad",
                                       "up_to": "UpToFace", "up_to_face": sel("BasePad", "Face5")})
    ml = await m.call("query_mass_properties", {"doc": hc, "object": "RiserPad"})
    log.note(f"literal up_to_face BasePad Face5 (a side face here) on a copy -> {short(lit, 400)} bbox={bb(ml)} vol={vol(ml)} explanation={pv(lit).get('explanation')}")
    await m.call("document_close", {"doc": hc})
    await capture(m, h, "tc-04-15-after.png")
    log.write({"doc": h})


go("tc-04-15", body)
