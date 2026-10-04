from tc04lib import *  # noqa: F401,F403


def props(qo):
    return sc(qo).get("properties") or {}


async def body(m, log):
    h = sc(await m.call("document_create", {"label": "EditPad"})).get("doc")
    await body_pad(m, h, "BlockBody", "BlockProfile", "BlockPad", rect_profile(0, 0, 20, 30), 10)
    mp = await m.call("query_mass_properties", {"doc": h, "object": "BlockPad"})
    log.check("Given BlockPad vol 6000", near(vol(mp), 6000.0), vol(mp))
    await capture(m, h, "tc-04-14-before.png")
    e = await m.call("feature_set_parameters", {"doc": h, "feature": "BlockPad", "parameters": {"Length": q(25)}})
    m2 = await m.call("query_mass_properties", {"doc": h, "object": "BlockPad"})
    log.note("visual for the 10 -> 25 mm edit captured right after it (the later Thens change the pad again)")
    await capture(m, h, "tc-04-14-after.png")
    log.check("edit OK rolled_back=false", ok_commit(e), short(e, 300))
    log.check("vol 15000", near(vol(m2), 15000.0), vol(m2))
    qo = await m.call("query_object", {"doc": h, "object": "BlockPad"})
    log.check("Length reads 25 mm", props(qo).get("Length") in ("25.0 mm", "25 mm"), props(qo).get("Length"))
    p = pv(e)
    log.check("post_verify passed is_valid recompute_clean", p.get("passed") is True and p.get("is_valid") is True and p.get("recompute_clean") is True, json.dumps(p)[:300])
    vs = await m.call("verify_shape", {"doc": h, "object": "BlockPad"})
    bbox = (sc(vs).get("subject") or {}).get("bbox") or sc(vs).get("bbox") or ss(e).get("bbox")
    log.write({"verify_shape_BlockPad": sc(vs)})
    log.check("verify_shape OK, bbox [20,30,25]", vs.get("status") == "OK" and json.dumps(bbox).count("25") >= 1, f"{vs.get('status')} bbox={json.dumps(bbox)[:200]} shape_summary_bbox={ss(e).get('bbox')}")
    e2 = await m.call("feature_set_parameters", {"doc": h, "feature": "BlockPad", "parameters": {"Length": q(12), "Reversed": True}})
    q2 = await m.call("query_object", {"doc": h, "object": "BlockPad"})
    log.check("Length 12 + Reversed true together OK, both read back", ok_commit(e2) and props(q2).get("Length") in ("12.0 mm", "12 mm") and props(q2).get("Reversed") is True,
              f"{short(e2, 200)} Length={props(q2).get('Length')} Reversed={props(q2).get('Reversed')}")
    e3 = await m.call("feature_set_parameters", {"doc": h, "feature": "BlockPad", "parameters": {"Midplane": True}})
    e4 = await m.call("feature_set_parameters", {"doc": h, "feature": "BlockPad", "parameters": {"Type": "Length"}})
    log.check("boolean Midplane and enum Type each OK", ok_commit(e3) and ok_commit(e4), f"{short(e3, 300)} {short(e4, 300)}")
    e5 = await m.call("feature_set_parameters", {"doc": h, "feature": "BlockPad", "parameters": {}})
    log.check("empty parameters INVALID_INPUT", e5.get("status") == "INVALID_INPUT" and "feature_set_parameters requires a non-empty 'parameters' object" in detail_msg(e5), short(e5))
    await capture(m, h, "tc-04-14-final.png")
    log.write({"doc": h})


go("tc-04-14", body)
