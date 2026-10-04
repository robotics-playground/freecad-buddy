from tc08lib import *  # noqa

PAD60 = dict(PAD30, length={"value": 60, "unit": "mm"})
PAD1 = dict(PAD30, name="Pad1")
WANT = "confirm.preview_id was issued for different arguments"


async def body(m, log):
    await close_all(m, log)
    doc = await body_sketch(m, "TC0809")
    await frame_shot(m, doc, "tc-08-09-before.png")
    pr = await preview(m, doc, "feature_pad", PAD30)
    tok = token(pr)
    r60 = await call_with(m, doc, "feature_pad", PAD60, {"preview_id": tok})
    log.check("60 mm with 30 mm token refused 'issued for different arguments'", r60.get("status") != "OK" and WANT in msg(r60), short(r60, 300))
    tr = await names(m, doc)
    log.check("tree does not list Pad", "Pad" not in tr, tr)
    await frame_shot(m, doc, "tc-08-09-refused.png")
    r1 = await call_with(m, doc, "feature_pad", PAD1, {"preview_id": tok})
    log.check("name Pad1 (one char) refused with same message", r1.get("status") != "OK" and WANT in msg(r1), msg(r1))
    log.check("refusal is NOT 'issued for a different document'",
              "issued for a different document" not in msg(r60) and "issued for a different document" not in msg(r1), [msg(r60), msg(r1)])
    ra = await call_with(m, doc, "feature_pad", PAD30, {"preview_id": tok, "elicitation_action": "accept"})
    log.check("same token + elicitation_action accept + 30 mm args -> OK (confirm excluded from digest)", ra.get("status") == "OK", short(ra))
    # 'identical call still authorized with a FRESH token': the pad now exists, so prove it on a fresh doc of the same shape
    doc2 = await body_sketch(m, "TC0809b")
    pr2 = await preview(m, doc2, "feature_pad", PAD30)
    rf = await call_with(m, doc2, "feature_pad", PAD30, {"preview_id": token(pr2)})
    log.check("FRESH 30 mm token with 30 mm args -> OK (side doc TC0809b; Pad already exists in TC0809)", rf.get("status") == "OK", short(rf))
    c = await m.call("document_close", {"doc": doc2})
    log.note(f"side doc TC0809b closed -> {c.get('status')}")
    mp = await m.call("query_mass_properties", {"doc": doc, "object": "Pad"})
    log.note(f"TC0809 Pad volume after authorized apply: {vol(mp)} (bbox {json.dumps(sc(mp).get('bbox'))[:200]})")
    await frame_shot(m, doc, "tc-08-09-after.png")
    print("DOC", doc)


go("tc-08-09", body)
