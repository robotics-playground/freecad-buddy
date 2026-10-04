import time
from tc08lib import *  # noqa


async def body(m, log):
    await close_all(m, log)
    doc = await body_sketch(m, "TC0808")
    vs = await m.call("verify_sketch", {"doc": doc, "sketch": "Sketch"})
    log.check("Given sketch fully constrained (verify_sketch; query_sketch_info has no fully_constrained field)",
              (sc(vs).get("subject") or {}).get("fully_constrained") is True, (sc(vs).get("subject") or {}).get("dof"))
    await frame_shot(m, doc, "tc-08-08-before.png")
    pr = await preview(m, doc, "feature_pad", PAD30)
    tok = token(pr)
    r = await call_with(m, doc, "feature_pocket", PAD30, {"preview_id": tok})
    want = "confirm.preview_id was issued for 'feature_pad', not 'feature_pocket'"
    log.check("pocket refused with tool-binding message", r.get("status") != "OK" and want in msg(r), short(r, 400))
    mm = msg(r)
    log.check("minting tool named first, called tool second", 0 <= mm.find("feature_pad") < mm.find("feature_pocket"), mm)
    tr = await names(m, doc)
    log.check("tree lists neither Pad nor a pocket", "Pad" not in tr and not any("Pocket" in (n or "") for n in tr), tr)
    log.check("refusal is not an argument complaint", "was issued for different arguments" not in mm, mm)
    time.sleep(0.5)
    fit, rec = await frame_shot(m, doc, "tc-08-08-refused.png")
    ok = await call_with(m, doc, "feature_pad", PAD30, {"preview_id": tok})
    log.check("same token on feature_pad with same args returns OK", ok.get("status") == "OK", short(ok))
    await frame_shot(m, doc, "tc-08-08-after.png")
    print("DOC", doc)


go("tc-08-08", body)
