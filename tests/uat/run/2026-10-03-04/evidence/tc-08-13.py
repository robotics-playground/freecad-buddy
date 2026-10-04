from tc08lib import *  # noqa

PAD60 = dict(PAD30, length={"value": 60, "unit": "mm"})
SPENT = "confirm.preview_id has already authorized a mutation; re-run preview_dry_run"


async def body(m, log):
    await close_all(m, log)
    doc = await body_sketch(m, "TC0813")
    await frame_shot(m, doc, "tc-08-13-before.png")
    pr = await preview(m, doc, "feature_pad", PAD30)
    tok = token(pr)
    bad = await call_with(m, doc, "feature_pad", PAD60, {"preview_id": tok})
    log.check("wrong-argument call refused 'issued for different arguments'",
              bad.get("status") != "OK" and "confirm.preview_id was issued for different arguments" in msg(bad), msg(bad))
    await frame_shot(m, doc, "tc-08-13-refused.png")
    good = await call_with(m, doc, "feature_pad", PAD30, {"preview_id": tok})
    log.check("corrected call (same token) OK", good.get("status") == "OK", short(good))
    log.check("corrected call not refused as spent", SPENT not in json.dumps(good), msg(good))
    mp = await m.call("query_mass_properties", {"doc": doc, "object": "Pad"})
    log.check("Pad volume 12000.0", near(vol(mp), 12000.0), vol(mp))
    fourth = await call_with(m, doc, "feature_pad", PAD30, {"preview_id": tok})
    log.check("4th send of same token -> already-authorized", fourth.get("status") != "OK" and SPENT in msg(fourth), msg(fourth))
    await frame_shot(m, doc, "tc-08-13-after.png")
    side = await body_sketch(m, "TC0813b")
    ps = await preview(m, side, "feature_pad", PAD30)
    dec = await call_with(m, side, "feature_pad", PAD30, {"preview_id": token(ps), "elicitation_action": "decline"})
    cor = await call_with(m, side, "feature_pad", PAD30, {"preview_id": token(ps)})
    log.write({"decline_call": dec, "corrected_after_decline": {"status": cor.get("status")}})
    log.check("middle call with elicitation_action decline refused, corrected call then OK (side doc TC0813b)",
              dec.get("status") != "OK" and cor.get("status") == "OK",
              {"decline": msg(dec)[:200], "corrected": cor.get("status")})
    log.note("decline refusal text: " + msg(dec)[:300])
    c = await m.call("document_close", {"doc": side})
    log.note(f"side doc TC0813b closed -> {c.get('status')}")
    print("DOC", doc)


go("tc-08-13", body)
