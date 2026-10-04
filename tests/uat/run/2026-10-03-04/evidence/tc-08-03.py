import re
from tc08lib import *  # noqa


async def body(m, log):
    await close_all(m, log)
    doc = await body_sketch(m, "TC0803")
    tr = await names(m, doc)
    log.check("Given tree lists Body and Sketch, not Pad", "Body" in tr and "Sketch" in tr and "Pad" not in tr, tr)
    await frame_shot(m, doc, "tc-08-03-before.png")

    pr = await preview(m, doc, "feature_pad", PAD30)
    tok = token(pr)
    d = diff(pr)
    log.write({"preview_sc": sc(pr)})
    ap = await call_with(m, doc, "feature_pad", PAD30, {"preview_id": tok})
    mu = mut(ap)
    log.check("apply status OK, detail null", ap.get("status") == "OK" and ap.get("detail") is None, short(ap))
    fa = mu.get("fingerprint_after") or {}
    log.check("mutation.rolled_back false and fingerprint_after a full record",
              mu.get("rolled_back") is False and isinstance(fa, dict) and all(k in fa for k in ("schema", "serializer", "objects", "digest")),
              {"rolled_back": mu.get("rolled_back"), "fa_keys": sorted(fa) if isinstance(fa, dict) else fa})
    fb = (mu.get("fingerprint_before") or {}).get("digest")
    log.check("mutation.fingerprint_before.digest == preview diff.fingerprint_before",
              fb is not None and fb == d.get("fingerprint_before"), {"apply": fb, "preview": d.get("fingerprint_before")})
    mp = await m.call("query_mass_properties", {"doc": doc, "object": "Pad"})
    dv = (d.get("deltas") or {}).get("volume") or {}
    log.check("Pad volume 12000.0 equals diff.deltas.volume.after", near(vol(mp), 12000.0) and near(vol(mp), dv.get("after") or -1),
              {"live": vol(mp), "predicted": dv.get("after")})
    log.check("token matches ^fcb-preview:[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+$",
              bool(re.match(r"^fcb-preview:[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+$", tok or "")), (tok or "")[:60])
    await frame_shot(m, doc, "tc-08-03-after.png")
    # explicit accept on the same flow, in a fresh document (side document, captured separately)
    doc2 = await body_sketch(m, "TC0803b")
    pr2 = await preview(m, doc2, "feature_pad", PAD30)
    ap2 = await call_with(m, doc2, "feature_pad", PAD30, {"preview_id": token(pr2), "elicitation_action": "accept"})
    log.check("same flow with elicitation_action accept returns OK", ap2.get("status") == "OK", short(ap2))
    c = await m.call("document_close", {"doc": doc2})
    log.note(f"side doc TC0803b closed -> {c.get('status')}")
    print("DOC", doc)


go("tc-08-03", body)
