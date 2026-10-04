from tc08lib import *  # noqa

WANT = "operation.args must not carry 'doc'; the preview supplies it"


async def body(m, log):
    await close_all(m, log)
    b = await body_sketch(m, "TC0820B")
    a = await body_sketch(m, "TC0820A")
    dl = await m.call("document_list", {})
    log.check("Given document_list returns two handles", len(sc(dl).get("documents") or []) == 2, sc(dl).get("documents"))
    _, rb = await frame_shot(m, a, "tc-08-20-before.png")
    r1 = await preview(m, a, "feature_pad", dict(PAD30, doc=a))
    r2 = await preview(m, a, "feature_pad", dict(PAD30, doc=b))
    dirs = prev_dirs()
    log.check("args.doc == outer handle refused with exact message", r1.get("status") != "OK" and msg(r1) == WANT, msg(r1)[:300])
    log.check("args.doc naming the other doc refused identically", r2.get("status") != "OK" and msg(r2) == WANT, msg(r2)[:300])
    log.check("no FCB_TMP_prev_ dir after both calls", dirs == [], dirs)
    na, nb = await names(m, a), await names(m, b)
    log.check("neither document has a Pad", "Pad" not in na and "Pad" not in nb, {"A": na, "B": nb})
    _, ra = await frame_shot(m, a, "tc-08-20-after.png")
    ok = await preview(m, a, "feature_pad", PAD30)
    log.check("same preview without args.doc returns OK", ok.get("status") == "OK", short(ok))
    rb2 = await call_with(m, b, "feature_pad", PAD30, {"preview_id": token(ok)})
    log.check("its token applied against B -> 'issued for a different document'",
              rb2.get("status") != "OK" and "confirm.preview_id was issued for a different document" in msg(rb2), msg(rb2)[:200])
    log.write({"title_before": rb.get("title"), "title_after": ra.get("title")})
    print("DOCS", a, b)


go("tc-08-20", body)
