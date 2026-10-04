from tc04lib import *  # noqa: F401,F403


async def body(m, log):
    h = sc(await m.call("document_create", {"label": "Block"})).get("doc")
    await m.call("feature_body_create", {"doc": h, "name": "BlockBody"})
    tr = await m.call("query_tree_summary", {"doc": h, "depth": 2})
    log.check("Given BlockBody in tree", "BlockBody" in tree_names(tr), "")
    await sketch(m, h, "BlockProfile", "BlockBody", rect_profile(0, 0, 20, 30))
    vsk = await m.call("verify_sketch", {"doc": h, "sketch": "BlockProfile"})
    log.check("Given BlockProfile verify_sketch OK dof=0", vsk.get("status") == "OK" and (sc(vsk).get("subject") or {}).get("dof") == 0, short(vsk))

    pad = await m.call("feature_pad", {"doc": h, "body": "BlockBody", "profile": "BlockProfile",
                                       "name": "BlockPad", "length": q(10)})
    mp = await m.call("query_mass_properties", {"doc": h, "object": "BlockPad"})
    log.write({"feature_state": fs(pad)})
    log.check("pad OK rolled_back=false", ok_commit(pad), short(pad))
    log.check("volume 6000.0 within 0.1%", near(vol(mp), 6000.0), vol(mp))
    vs = await m.call("verify_shape", {"doc": h, "object": "BlockPad"})
    s = ss(pad)
    log.check("verify_shape OK; shape_summary solid_count=1 is_valid=true",
              vs.get("status") == "OK" and s.get("solid_count") == 1 and s.get("is_valid") is True,
              f"verify={vs.get('status')} summary={json.dumps(s)[:300]}")
    bbox = s.get("bbox")
    log.check("bbox=[20,30,10] within 0.1%", isinstance(bbox, list) and all(near(a, b) for a, b in zip(bbox, [20, 30, 10])), bbox)
    log.check("face/edge/vertex 6/12/8", (s.get("face_count"), s.get("edge_count"), s.get("vertex_count")) == (6, 12, 8),
              (s.get("face_count"), s.get("edge_count"), s.get("vertex_count")))
    f = fs(pad)
    log.check("feature_state body=BlockBody is_tip=true", f.get("body") == "BlockBody" and f.get("is_tip") is True,
              {k: f.get(k) for k in ("body", "is_tip")})
    qo = await m.call("query_object", {"doc": h, "object": "BlockPad"})
    props = sc(qo).get("properties") or {}
    log.write({"query_object_BlockPad": sc(qo)})
    typ = props.get("Type")
    log.check("query_object Type=Length", "Length" in json.dumps(typ), json.dumps(typ)[:200])
    p = pv(pad)
    log.check("post_verify passed/recompute_clean/is_valid true, tnp CLEAN",
              p.get("passed") is True and p.get("recompute_clean") is True and p.get("is_valid") is True
              and (p.get("tnp_audit") or {}).get("status") == "CLEAN", json.dumps(p)[:300])
    log.write({"mass": sc(mp)})
    await capture(m, h, "tc-04-02-after.png")
    log.write({"doc": h})


go("tc-04-02", body)
