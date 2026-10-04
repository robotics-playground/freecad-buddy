from tc04lib import *  # noqa: F401,F403


async def body(m, log):
    h = sc(await m.call("document_create", {"label": "Defaults"})).get("doc")
    await body_pad(m, h, "PlateBody", "PlateProfile", "PlatePad", rect_profile(0, 0, 60, 40), 5)
    mp = await m.call("query_mass_properties", {"doc": h, "object": "PlatePad"})
    log.check("Given PlatePad vol 12000", near(vol(mp), 12000.0), vol(mp))
    log.note("edge names from the outside oracle: PlatePad Edge1 = vertical corner (0,0); DefaultFillet Edge3 = vertical corner (60,0) (tc-04-topology-oracle2.txt)")
    f = await m.call("feature_fillet", {"doc": h, "body": "PlateBody", "base": "PlatePad", "name": "DefaultFillet",
                                        "edges": [sel("PlatePad", "Edge1")]})
    c = await m.call("feature_chamfer", {"doc": h, "body": "PlateBody", "base": "DefaultFillet", "name": "DefaultChamfer",
                                         "edges": [sel("DefaultFillet", "Edge3")]})
    log.check("fillet without radius OK", ok_commit(f), short(f, 300))
    qf = await m.call("query_object", {"doc": h, "object": "DefaultFillet"})
    log.check("Radius = 1 mm", (sc(qf).get("properties") or {}).get("Radius") in ("1.0 mm", "1 mm"), (sc(qf).get("properties") or {}).get("Radius"))
    mf = await m.call("query_mass_properties", {"doc": h, "object": "DefaultFillet"})
    log.check("DefaultFillet vol 11998.9", near(vol(mf), 11998.927), vol(mf))
    log.check("chamfer without size OK", ok_commit(c), short(c, 300))
    qc = await m.call("query_object", {"doc": h, "object": "DefaultChamfer"})
    log.check("Size = 1 mm", (sc(qc).get("properties") or {}).get("Size") in ("1.0 mm", "1 mm"), (sc(qc).get("properties") or {}).get("Size"))
    vs = await m.call("verify_shape", {"doc": h, "object": "DefaultChamfer"})
    log.check("verify_shape DefaultChamfer OK solid_count=1", vs.get("status") == "OK" and ss(c).get("solid_count") == 1, short(vs))
    mc = await m.call("query_mass_properties", {"doc": h, "object": "DefaultChamfer"})
    log.note(f"DefaultChamfer vol={vol(mc)} (expected 11998.927 - 0.5*1*1*5 = 11996.427)")
    await capture(m, h, "tc-04-20-after.png")
    log.write({"doc": h})


go("tc-04-20", body)
