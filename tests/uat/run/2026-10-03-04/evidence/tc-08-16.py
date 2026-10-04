from tc08lib import *  # noqa


async def body(m, log):
    await close_all(m, log)
    doc = await body_sketch(m, "TC0816")
    pr = await preview(m, doc, "feature_pad", PAD30)
    tok = token(pr)
    await frame_shot(m, doc, "tc-08-16-before.png")
    out = {}
    for v in ("decline", "cancel", None):
        r = await call_with(m, doc, "feature_pad", PAD30, {"preview_id": tok, "elicitation_action": v})
        out[repr(v)] = {"status": r.get("status"), "message": msg(r)[:300]}
        print(repr(v), out[repr(v)])
    log.write({"declines": out})
    gate = {"'decline'": "confirm.elicitation_action must be 'accept', got 'decline'",
            "'cancel'": "confirm.elicitation_action must be 'accept', got 'cancel'",
            "None": "confirm.elicitation_action must be 'accept', got None"}
    for k, want in gate.items():
        o = out[k]
        log.check(f"{k} refused (gate message or JSON-Schema enum rejection)",
                  o["status"] != "OK" and (want in o["message"] or "is not one of ['accept']" in o["message"]), o)
    log.check("rejected value quoted back as Python repr (gate layer)",
              all(gate[k] in out[k]["message"] for k in gate), {k: out[k]["message"][:120] for k in out})
    tr = await names(m, doc)
    log.check("no Pad after declining calls", "Pad" not in tr, tr)
    await frame_shot(m, doc, "tc-08-16-refused.png")
    ok = await call_with(m, doc, "feature_pad", PAD30, {"preview_id": tok, "elicitation_action": "accept"})
    log.check("token survives: same token with accept -> OK", ok.get("status") == "OK", short(ok))
    await frame_shot(m, doc, "tc-08-16-after.png")
    side = await body_sketch(m, "TC0816b")
    ps = await preview(m, side, "feature_pad", PAD30)
    a = await call_with(m, side, "feature_pad", PAD30, {"preview_id": token(ps)})
    log.check("omitting elicitation_action defaults to accept: fresh token alone -> OK (side doc TC0816b)",
              a.get("status") == "OK", short(a))
    c = await m.call("document_close", {"doc": side})
    log.note(f"side doc TC0816b closed -> {c.get('status')}")
    print("DOC", doc)


go("tc-08-16", body)
