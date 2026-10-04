from tc08lib import *  # noqa


async def body(m, log):
    await close_all(m, log)
    doc = await body_sketch(m, "TC0807")
    await frame_shot(m, doc, "tc-08-07-before.png")
    pr = await preview(m, doc, "feature_body_create", {"name": "Probe"})
    tok = token(pr)
    a1 = await call_with(m, doc, "feature_body_create", {"name": "Probe"}, {"preview_id": tok})
    r = await call_with(m, doc, "feature_body_create", {"name": "Probe"}, {"preview_id": tok})
    log.check("first apply OK", a1.get("status") == "OK", short(a1))
    mu = mut(a1)
    log.check("apply fingerprint_before.digest == fingerprint_after.digest",
              (mu.get("fingerprint_before") or {}).get("digest") == (mu.get("fingerprint_after") or {}).get("digest")
              and (mu.get("fingerprint_before") or {}).get("digest") is not None,
              {"before": (mu.get("fingerprint_before") or {}).get("digest"), "after": (mu.get("fingerprint_after") or {}).get("digest")})
    want = "confirm.preview_id has already authorized a mutation; re-run preview_dry_run"
    log.check("replay refused with spent message", r.get("status") != "OK" and want in msg(r), short(r, 400))
    log.check("refusal not a fingerprint complaint", "the document has changed since the preview was taken" not in msg(r), msg(r))
    tr = await names(m, doc, 2)
    log.check("tree depth 2 lists exactly one Probe", tr.count("Probe") == 1 and not any(n and n.startswith("Probe0") for n in tr), tr)
    log.write({"tree_after_replay": tr})
    await frame_shot(m, doc, "tc-08-07-after.png")
    # fresh preview restores ability to apply (same operation; FreeCAD will auto-rename the 2nd body)
    pr2 = await preview(m, doc, "feature_body_create", {"name": "Probe"})
    a2 = await call_with(m, doc, "feature_body_create", {"name": "Probe"}, {"preview_id": token(pr2)})
    log.check("fresh preview token apply returns OK", a2.get("status") == "OK", short(a2, 400))
    log.write({"tree_after_fresh": await names(m, doc, 2)})
    print("DOC", doc)


go("tc-08-07", body)
