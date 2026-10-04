from tc08lib import *  # noqa


async def body(m, log):
    await close_all(m, log)
    a = await body_sketch(m, "TC0810A")
    b = await body_sketch(m, "TC0810B")
    dl = await m.call("document_list", {})
    hs = [x["doc"] for x in sc(dl).get("documents") or []]
    log.check("Given document_list returns two handles", sorted(hs) == sorted([a, b]), sc(dl).get("documents"))
    ta = await m.call("query_tree_summary", {"doc": a, "depth": 3})
    tb = await m.call("query_tree_summary", {"doc": b, "depth": 3})
    _, rb = await frame_shot(m, b, "tc-08-10-before.png")
    pr = await preview(m, a, "feature_pad", PAD30)
    tok = token(pr)
    r = await call_with(m, b, "feature_pad", PAD30, {"preview_id": tok})
    want = "confirm.preview_id was issued for a different document"
    log.check("A's token on B refused 'issued for a different document'", r.get("status") != "OK" and want in msg(r), short(r, 300))
    _, rr = await frame_shot(m, b, "tc-08-10-after.png")
    nb = await names(m, b)
    na = await names(m, a)
    log.check("B not mutated (no Pad)", "Pad" not in nb, nb)
    log.check("A not mutated (no Pad)", "Pad" not in na, na)
    sa = json.dumps(sc(ta).get("tree")); sb = json.dumps(sc(tb).get("tree"))
    log.check("binding holds although the two docs have identical trees (handle comparison, not content)",
              sa == sb and want in msg(r), {"identical_trees": sa == sb})
    log.check("refusal not an argument complaint", "was issued for different arguments" not in msg(r), msg(r))
    ok = await call_with(m, a, "feature_pad", PAD30, {"preview_id": tok})
    log.check("A's token on A returns OK", ok.get("status") == "OK", short(ok))
    log.write({"window_title_before": rb.get("title"), "window_title_after": rr.get("title")})
    print("DOCS", a, b)


go("tc-08-10", body)
