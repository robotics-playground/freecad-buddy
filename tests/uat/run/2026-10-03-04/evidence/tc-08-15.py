from tc08lib import *  # noqa


async def body(m, log):
    await close_all(m, log)
    doc = await body_sketch(m, "TC0815")
    pr = await preview(m, doc, "feature_pad", PAD30)
    tok = token(pr)
    await frame_shot(m, doc, "tc-08-15-before.png")
    r1 = await call_with(m, doc, "feature_pad", PAD30, {"preview_id": tok, "autoApprove": True})
    r2 = await call_with(m, doc, "feature_pad", PAD30, {"preview_id": tok, "autoApprove": True, "force": 1})
    r3 = await call_with(m, doc, "feature_pad", PAD30, "yes")
    for t, r in (("one-field", r1), ("two-field", r2), ("confirm-yes", r3)):
        print(t, r.get("status"), msg(r)[:300])
    log.check("single undeclared field refused: confirm carries field(s) the schema does not declare: ['autoApprove']",
              r1.get("status") != "OK" and "confirm carries field(s) the schema does not declare: ['autoApprove']" in msg(r1),
              msg(r1)[:300])
    log.check("two undeclared fields listed sorted: ['autoApprove', 'force']",
              r2.get("status") != "OK" and "['autoApprove', 'force']" in msg(r2), msg(r2)[:300])
    tr = await names(m, doc)
    log.check("single-field call not OK and no Pad in tree (not silently dropped)", r1.get("status") != "OK" and "Pad" not in tr, tr)
    log.check("confirm 'yes' refused (schema reject for non-object, or 'confirm must be an object')",
              r3.get("status") != "OK" and ("confirm must be an object" in msg(r3) or "is not of type 'object'" in msg(r3)),
              msg(r3)[:300])
    await frame_shot(m, doc, "tc-08-15-refused.png")
    ok = await call_with(m, doc, "feature_pad", PAD30, {"preview_id": tok})
    log.check("token survives: same token with preview_id alone -> OK", ok.get("status") == "OK", short(ok))
    await frame_shot(m, doc, "tc-08-15-after.png")
    side = await body_sketch(m, "TC0815b")
    ps = await preview(m, side, "feature_pad", PAD30)
    x = await call_with(m, side, "feature_pad", PAD30, {"preview_id": token(ps), "elicitation_action": "accept", "note": "x"})
    a = await call_with(m, side, "feature_pad", PAD30, {"preview_id": token(ps), "elicitation_action": "accept"})
    log.check("only two declared fields accepted: a third key refused; fresh token + accept OK (side doc TC0815b)",
              a.get("status") == "OK" and x.get("status") != "OK", {"accept": a.get("status"), "third_key": msg(x)[:200]})
    c = await m.call("document_close", {"doc": side})
    log.note(f"side doc TC0815b closed -> {c.get('status')}")
    print("DOC", doc)


go("tc-08-15", body)
