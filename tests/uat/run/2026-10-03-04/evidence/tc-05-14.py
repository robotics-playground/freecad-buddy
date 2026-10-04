from tc05lib import *


async def body(m, log):
    await close_all(m, log)
    doc = sc(await m.call("document_create", {"label": "TC0514"})).get("doc")
    await apply(m, doc, "feature_body_create", {"name": "Body"})
    await apply(m, doc, "sketch_create", {"name": "Sketch", "body": "Body", "plane": "XY"})
    g, c = rect_profile(0, 0, 20, 20)
    await apply(m, doc, "sketch_add_geometry", {"sketch": "Sketch", "geometry": g, "constraints": c})
    p, pad = await apply(m, doc, "feature_pad", {"body": "Body", "profile": "Sketch", "name": "Pad", "length": q(30)})
    pm = await m.call("query_mass_properties", {"doc": doc, "object": "Pad"})
    log.check("Given Pad volume 12000.0", near(vol(pm), 12000.0, 1e-6), vol(pm))
    log.check("CONDITIONAL second build with the other serializer", None, "NOT RUN: only FreeCAD 1.1.4 (exportBinary) is installed for the GUI")
    fit, rec = await capture(m, doc, "tc-05-14-before.png")
    log.note(f"before fit={fit}")
    fb, fa = (mut(pad).get("fingerprint_before") or {}), (mut(pad).get("fingerprint_after") or {})
    log.check("tag carried on a successful mutation's fingerprint_before", bool(fb.get("serializer")), fb.get("serializer"))
    log.check("fingerprint_before.serializer == fingerprint_after.serializer", fb.get("serializer") == fa.get("serializer"), [fb.get("serializer"), fa.get("serializer")])
    u1 = await m.call("document_undo", {"doc": doc, "expect_fingerprint": {"objects": [], "digest": "0" * 64}})
    msg1 = (u1.get("detail") or {}).get("message") if isinstance(u1.get("detail"), dict) else u1.get("_raw")
    log.note(f"degraded form: tagless record {{objects:[], digest:0*64}} -> status={u1.get('status')} msg={msg1!r} sc={json.dumps(sc(u1))[:300]}")
    log.check("tagless record is refused with a comparison error, not a quiet 'not equal'",
              u1.get("status") != "OK" and "cannot compare fingerprints" in str(msg1), msg1)
    u2 = await m.call("document_undo", {"doc": doc, "expect_fingerprint": {"digest": "abc"}})
    msg2 = (u2.get("detail") or {}).get("message") if isinstance(u2.get("detail"), dict) else u2.get("_raw")
    log.check("record missing 'objects' refused: \"expect_fingerprint record must carry an 'objects' list; got keys ['digest']\"",
              u2.get("status") != "OK" and "expect_fingerprint record must carry an 'objects' list; got keys ['digest']" in str(msg2), msg2)
    quiet = [u for u in (u1, u2) if "matches_pre_op" in json.dumps(sc(u)) and '"matches_pre_op": false' in json.dumps(sc(u))]
    log.check("no tag mismatch surfaced as matches_pre_op:false without a comparison error", not quiet, [short(u) for u in quiet])
    pm2 = await m.call("query_mass_properties", {"doc": doc, "object": "Pad"})
    tr = await m.call("query_tree_summary", {"doc": doc, "depth": 3})
    log.note(f"after refused undos: Pad present={tree_has(tr, 'Pad')} vol={vol(pm2)}")
    fit, rec = await capture(m, doc, "tc-05-14-after.png")
    log.note(f"after fit={fit}")


go("tc-05-14", body)
