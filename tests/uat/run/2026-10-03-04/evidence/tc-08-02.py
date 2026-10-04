from tc08lib import *  # noqa


async def body(m, log):
    await close_all(m, log)
    doc = await body_sketch(m, "TC0802", pad=30)
    mp0 = await m.call("query_mass_properties", {"doc": doc, "object": "Pad"})
    log.check("Given Pad volume 12000.0", near(vol(mp0), 12000.0), vol(mp0))
    log.check("Given no stale preview TempDocs", prev_dirs() == [], prev_dirs())
    await frame_shot(m, doc, "tc-08-02-before.png")

    mp1 = await m.call("query_mass_properties", {"doc": doc, "object": "Pad"})
    dl1 = await m.call("document_list", {})
    pr = await preview(m, doc, "feature_set_parameters", {"feature": "Pad", "parameters": {"Length": {"value": 80, "unit": "mm"}}})
    d = diff(pr)
    log.write({"preview_sc": sc(pr)})
    mp2 = await m.call("query_mass_properties", {"doc": doc, "object": "Pad"})
    dl2 = await m.call("document_list", {})

    dv = (d.get("deltas") or {}).get("volume") or {}
    log.check("diff.deltas.volume.after == 32000.0", near(dv.get("after"), 32000.0), dv)
    s1, s2 = sc(mp1), sc(mp2)
    log.check("live volume unchanged 12000.0, byte-identical to first read",
              near(vol(mp2), 12000.0) and json.dumps(s1.get("volume"), sort_keys=True) == json.dumps(s2.get("volume"), sort_keys=True),
              {"first": s1.get("volume"), "second": s2.get("volume")})
    log.check("live bbox and com unchanged", s1.get("bbox") == s2.get("bbox") and s1.get("com") == s2.get("com") and s1.get("bbox") is not None,
              {"bbox1": s1.get("bbox"), "bbox2": s2.get("bbox"), "com1": s1.get("com"), "com2": s2.get("com")})
    h1 = sorted(x["doc"] for x in sc(dl1).get("documents") or [])
    h2 = sorted(x["doc"] for x in sc(dl2).get("documents") or [])
    n2 = [x["name"] for x in sc(dl2).get("documents") or []]
    log.check("document_list same handles, no FCB_TMP_prev_ name", h1 == h2 and not any(n.startswith("FCB_TMP_prev_") for n in n2),
              {"before": h1, "after": h2, "names": n2})
    log.check("TempDoc directory gone after preview", prev_dirs() == [], prev_dirs())
    log.check("envelope OK, not SPEC_FAILED 'preview changed the live document'",
              pr.get("status") == "OK" and "preview changed the live document" not in json.dumps(pr), short(pr))
    # failing path: preview an operation that fails on the copy
    bad = await preview(m, doc, "feature_set_parameters", {"feature": "Pad", "parameters": {"Length": {"value": -5, "unit": "mm"}}})
    log.write({"failing_preview": {"status": bad.get("status"), "validity": diff(bad).get("validity"), "detail": bad.get("detail")}})
    bad2 = await preview(m, doc, "feature_fillet", {"body": "Body", "base": "Pad", "name": "Fillet",
                                                    "edges": [{"kind": "mapped_name", "object": "Pad", "mapped_name": "Edge1"}],
                                                    "radius": {"value": 500, "unit": "mm"}})
    log.write({"failing_preview2": {"status": bad2.get("status"), "validity": diff(bad2).get("validity"), "detail": bad2.get("detail")}})
    fails = [(b.get("status"), (diff(b).get("validity") or {}).get("is_valid")) for b in (bad, bad2)]
    log.check("an op FAILING on the copy also leaves no FCB_TMP_prev_ dir",
              any(st != "OK" or iv is False for st, iv in fails) and prev_dirs() == [], {"fails": fails, "dirs": prev_dirs()})
    mp3 = await m.call("query_mass_properties", {"doc": doc, "object": "Pad"})
    log.check("live volume still 12000.0 after failing previews", near(vol(mp3), 12000.0), vol(mp3))
    await frame_shot(m, doc, "tc-08-02-after.png")
    print("DOC", doc)


go("tc-08-02", body)
