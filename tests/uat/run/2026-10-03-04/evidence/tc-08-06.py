import re
from tc08lib import *  # noqa

HEX = re.compile(r"^[0-9a-f]{64}$")


async def pad(m, doc):
    pr = await preview(m, doc, "feature_pad", PAD30)
    return await call_with(m, doc, "feature_pad", PAD30, {"preview_id": token(pr)})


async def body(m, log):
    await close_all(m, log)
    doc = await body_sketch(m, "TC0806")
    # Given "undo available": verify with an extra harmless transaction so the Given state survives
    _, probe = await apply(m, doc, "feature_body_create", {"name": "UndoProbe"})
    gu = await m.call("document_undo", {"doc": doc})
    log.check("Given undo available: document_undo not refused 'undo is unavailable' (undid a probe body)",
              gu.get("status") == "OK" and "undo is unavailable" not in msg(gu),
              {"probe_apply": probe.get("status"), "undo": gu.get("status"), "undone": sc(gu).get("undone"),
               "restored": sc(gu).get("restored_objects")})
    await frame_shot(m, doc, "tc-08-06-before.png")

    a1 = await pad(m, doc)
    fb1 = mut(a1).get("fingerprint_before") or {}
    u1 = await m.call("document_undo", {"doc": doc, "expect_fingerprint": fb1.get("digest")})
    a2 = await pad(m, doc)
    fb2 = mut(a2).get("fingerprint_before") or {}
    u2 = await m.call("document_undo", {"doc": doc, "expect_fingerprint": fb2})
    log.write({"apply1": a1.get("status"), "apply2": a2.get("status"), "u1": sc(u1), "u2": sc(u2)})
    log.check("string-form undo matches_pre_op true", sc(u1).get("matches_pre_op") is True,
              {"status": u1.get("status"), "matches": sc(u1).get("matches_pre_op"), "after": sc(u1).get("fingerprint_after"),
               "expected": fb1.get("digest")})
    log.check("record-form undo matches_pre_op true", sc(u2).get("matches_pre_op") is True,
              {"status": u2.get("status"), "matches": sc(u2).get("matches_pre_op")})
    for tag, u in (("string", u1), ("record", u2)):
        s = sc(u)
        log.check(f"{tag}: fingerprint_before/after 64-hex and differ",
                  bool(HEX.match(str(s.get("fingerprint_before")))) and bool(HEX.match(str(s.get("fingerprint_after"))))
                  and s.get("fingerprint_before") != s.get("fingerprint_after"),
                  {"before": s.get("fingerprint_before"), "after": s.get("fingerprint_after")})
        log.check(f"{tag}: undone == 'buddy: <pad transaction label>'", str(s.get("undone") or "").startswith("buddy: "),
                  s.get("undone"))
        log.check(f"{tag}: text contains 'restored the pre-op state'", "restored the pre-op state" in (u.get("text") or ""),
                  u.get("text"))
        ro = s.get("restored_objects") or []
        log.check(f"{tag}: restored_objects lists Body, Sketch, Origin members and not Pad",
                  "Body" in ro and "Sketch" in ro and any(o.startswith("Origin") for o in ro) and "Pad" not in ro, ro)
    a3 = await pad(m, doc)
    u3 = await m.call("document_undo", {"doc": doc})
    log.check("no expect_fingerprint -> matches_pre_op null and text 'no pre-op digest supplied to compare against'",
              a3.get("status") == "OK" and "matches_pre_op" in sc(u3) and sc(u3).get("matches_pre_op") is None
              and "no pre-op digest supplied to compare against" in (u3.get("text") or ""),
              {"apply3": a3.get("status"), "matches": sc(u3).get("matches_pre_op"), "text": u3.get("text")})
    u4 = await m.call("document_undo", {"doc": doc, "expect_fingerprint": 42})
    want = "expect_fingerprint must be a fingerprint digest string or a FingerprintRecord, got int"
    log.check("expect_fingerprint 42 refused with exact message", u4.get("status") != "OK" and want in msg(u4), short(u4, 400))
    tr = await names(m, doc)
    log.check("tree after: Body + Sketch, no Pad (corroborating)", "Pad" not in tr and "Sketch" in tr, tr)
    await frame_shot(m, doc, "tc-08-06-after.png")
    print("DOC", doc)


go("tc-08-06", body)
