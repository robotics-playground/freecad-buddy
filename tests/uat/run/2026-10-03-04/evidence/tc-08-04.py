from tc08lib import *  # noqa

FILLET = {"body": "Body", "base": "Pad", "name": "Fillet",
          "edges": [{"kind": "mapped_name", "object": "Pad", "mapped_name": "Edge1"}],
          "radius": {"value": 500, "unit": "mm"}}


async def body(m, log):
    await close_all(m, log)
    doc = await body_sketch(m, "TC0804", pad=30)
    mp0 = await m.call("query_mass_properties", {"doc": doc, "object": "Pad"})
    log.check("Given Pad volume 12000.0", near(vol(mp0), 12000.0), vol(mp0))
    await frame_shot(m, doc, "tc-08-04-before.png")
    pr = await preview(m, doc, "feature_fillet", FILLET)
    d = diff(pr)
    log.write({"preview_sc": sc(pr)})
    log.check("envelope status OK, detail null", pr.get("status") == "OK" and pr.get("detail") is None, short(pr))
    v = d.get("validity") or {}
    log.check("validity.is_valid false and status SPEC_FAILED or RECOMPUTE_ERROR",
              v.get("is_valid") is False and v.get("status") in ("SPEC_FAILED", "RECOMPUTE_ERROR"), v)
    log.check("validity.explanation non-empty string", isinstance(v.get("explanation"), str) and v.get("explanation").strip() != "",
              v.get("explanation"))
    dv = (d.get("deltas") or {}).get("volume") or {}
    log.check("deltas.volume has before/after/delta/units", all(k in dv for k in ("before", "after", "delta", "units")), dv)
    log.check("diff.new is []", d.get("new") == [], {"new": d.get("new"), "touched": d.get("touched")})
    log.check("preview_id non-null", bool(token(pr)), (token(pr) or "")[:40])
    mp = await m.call("query_mass_properties", {"doc": doc, "object": "Pad"})
    log.check("live Pad volume 12000.0", near(vol(mp), 12000.0), vol(mp))
    log.check("live tree has no Fillet (corroborating)", "Fillet" not in await names(m, doc), "")
    await frame_shot(m, doc, "tc-08-04-after.png")
    print("DOC", doc)


go("tc-08-04", body)
