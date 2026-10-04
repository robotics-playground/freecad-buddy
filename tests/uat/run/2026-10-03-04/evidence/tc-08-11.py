from tc08lib import *  # noqa

DATUM = {"sketch": "Sketch", "constraint": "Width", "value": {"value": 40, "unit": "mm"}}


async def body(m, log):
    await close_all(m, log)
    doc = sc(await m.call("document_create", {"label": "TC0811"})).get("doc")
    await apply(m, doc, "feature_body_create", {"name": "Body"})
    await apply(m, doc, "sketch_create", {"name": "Sketch", "body": "Body", "plane": "XY"})
    g, c = rect_profile(0, 0, 20, 20)
    for k in c:
        if k["type"] == "DistanceX":
            k["name"] = "Width"
        if k["type"] == "DistanceY" and k.get("first") == 1:
            k["name"] = "Height"
    _, sg = await apply(m, doc, "sketch_add_geometry", {"sketch": "Sketch", "geometry": g, "constraints": c})
    log.check("Given 20x20 sketch with named Width constraint committed", sg.get("status") == "OK", short(sg))
    await frame_shot(m, doc, "tc-08-11-before.png")

    pr = await preview(m, doc, "feature_pad", PAD30)
    tok = token(pr)
    pd = await preview(m, doc, "sketch_set_datum", DATUM)
    ad = await call_with(m, doc, "sketch_set_datum", DATUM, {"preview_id": token(pd)})
    stale = await call_with(m, doc, "feature_pad", PAD30, {"preview_id": tok})
    want = "the document has changed since the preview was taken; re-run preview_dry_run"
    log.check("stale token refused with fingerprint message", stale.get("status") != "OK" and want in msg(stale), short(stale, 300))
    si = await m.call("query_sketch_info", {"doc": doc, "sketch": "Sketch"})
    wc = [x for x in sc(si).get("constraints") or [] if x.get("name") == "Width"]
    log.check("sketch_set_datum apply OK and query_sketch_info Width == 40 mm",
              ad.get("status") == "OK" and wc and abs(float(wc[0]["value"]["value"]) - 40.0) < 1e-9, {"apply": ad.get("status"), "width": wc})
    tr = await names(m, doc)
    log.check("no Pad in tree", "Pad" not in tr, tr)
    log.check("refusal not a spent-token complaint", "has already authorized a mutation" not in msg(stale), msg(stale))
    await frame_shot(m, doc, "tc-08-11-after.png")
    pr2 = await preview(m, doc, "feature_pad", PAD30)
    ok = await call_with(m, doc, "feature_pad", PAD30, {"preview_id": token(pr2)})
    log.check("re-preview + apply returns OK", ok.get("status") == "OK", short(ok))
    mp = await m.call("query_mass_properties", {"doc": doc, "object": "Pad"})
    log.note(f"recovered pad volume {vol(mp)} (40x20x30 expected 24000)")
    log.check("unreadable live state refusal 'cannot read the state of <handle>'", None,
              "NOT RUN: no wire-reachable way to make a document whose shape cannot be serialized (debug_exec disabled, exec_enabled:false)")
    print("DOC", doc)


go("tc-08-11", body)
