from tc04lib import *  # noqa: F401,F403


async def body(m, log):
    h = sc(await m.call("document_create", {"label": "SetParamRefusals"})).get("doc")
    await body_pad(m, h, "BlockBody", "BlockProfile", "BlockPad", rect_profile(0, 0, 20, 30), 10)
    mp = await m.call("query_mass_properties", {"doc": h, "object": "BlockPad"})
    log.check("Given BlockPad vol 6000", near(vol(mp), 6000.0), vol(mp))
    base = snaps()
    await capture(m, h, "tc-04-21-before.png")
    a = {"doc": h, "feature": "BlockPad"}
    s1 = await m.call("feature_set_parameters", {**a, "parameters": {"Thickness": q(3)}})
    s2 = await m.call("feature_set_parameters", {**a, "parameters": {"Shape": 1}})
    s3 = await m.call("feature_set_parameters", {**a, "parameters": {"Length": q(25, "deg")}})
    s4 = await m.call("feature_set_parameters", {**a, "parameters": {"Length": [25]}})
    log.check("unknown property 'BlockPad has no property named 'Thickness''", s1.get("status") == "INVALID_INPUT" and "BlockPad has no property named 'Thickness'" in detail_msg(s1), short(s1))
    log.check("read-only 'BlockPad.Shape is read-only'", s2.get("status") == "INVALID_INPUT" and "BlockPad.Shape is read-only" in detail_msg(s2), short(s2))
    log.check("wrong unit \"Length value unit must be one of ['mm'], got 'deg'\"", s3.get("status") == "INVALID_INPUT" and "Length value unit must be one of ['mm'], got 'deg'" in detail_msg(s3), short(s3))
    log.check("unsupported type 'Length value must be a quantity, number, boolean or enum string'",
              s4.get("status") == "INVALID_INPUT" and "Length value must be a quantity, number, boolean or enum string" in detail_msg(s4), short(s4))
    log.check("no envelope carries snapshot_path", not any(mut(e).get("snapshot_path") for e in (s1, s2, s3, s4)), "")
    log.check("no snapshot written", set(snaps()) == set(base), f"new={sorted(set(snaps()) - set(base))}")
    mp2 = await m.call("query_mass_properties", {"doc": h, "object": "BlockPad"})
    log.check("BlockPad vol 6000 again", near(vol(mp2), 6000.0), vol(mp2))
    s5 = await m.call("feature_set_parameters", {**a, "parameters": {"Length": q(12), "Thickness": 3}})
    qo = await m.call("query_object", {"doc": h, "object": "BlockPad"})
    L = (sc(qo).get("properties") or {}).get("Length")
    log.check("whole batch refused when one entry is bad; Length still 10 mm", s5.get("status") == "INVALID_INPUT" and L in ("10.0 mm", "10 mm"), f"{short(s5)} Length={L}")
    await capture(m, h, "tc-04-21-after.png")
    log.write({"doc": h})


go("tc-04-21", body)
