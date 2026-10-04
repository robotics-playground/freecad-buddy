from tc04lib import *  # noqa: F401,F403


def bb(mp):
    b = sc(mp).get("bbox") or {}
    return {k: (v or {}).get("value") for k, v in b.items()}


def prop(qo, name):
    return (sc(qo).get("properties") or {}).get(name)


async def body(m, log):
    h = sc(await m.call("document_create", {"label": "PadOptions"})).get("doc")
    log.note("profiles are identical 20x30 rectangles, placed at x=0, x=40, x=80 so the three solids do not overlap in the view")
    for i, (b, p) in enumerate((("RevBody", "RevProfile"), ("TwoBody", "TwoProfile"), ("TaperBody", "TaperProfile"))):
        await m.call("feature_body_create", {"doc": h, "name": b})
        await sketch(m, h, p, b, rect_profile(40 * i, 0, 20, 30))
        v = await m.call("verify_sketch", {"doc": h, "sketch": p})
        log.check(f"Given {p} dof=0", (sc(v).get("subject") or {}).get("dof") == 0, short(v))
    rev = await m.call("feature_pad", {"doc": h, "body": "RevBody", "profile": "RevProfile", "name": "RevPad",
                                       "length": q(10), "reversed": True})
    two = await m.call("feature_pad", {"doc": h, "body": "TwoBody", "profile": "TwoProfile", "name": "TwoPad",
                                       "length": q(10), "second_length": q(4)})
    tap = await m.call("feature_pad", {"doc": h, "body": "TaperBody", "profile": "TaperProfile", "name": "TaperPad",
                                       "length": q(10), "taper_angle": q(5, "deg")})
    log.check("all three commit OK rolled_back=false", all(ok_commit(e) for e in (rev, two, tap)),
              [short(e, 200) for e in (rev, two, tap)])
    mr = await m.call("query_mass_properties", {"doc": h, "object": "RevPad"})
    b = bb(mr)
    log.check("RevPad vol 6000 and bbox z -10..0", near(vol(mr), 6000.0) and near(b.get("zmin"), -10) and abs(b.get("zmax") or 9) < 1e-6,
              f"vol={vol(mr)} bbox={b}")
    qr = await m.call("query_object", {"doc": h, "object": "RevPad"})
    log.check("RevPad Reversed=true", prop(qr, "Reversed") is True, prop(qr, "Reversed"))
    mt = await m.call("query_mass_properties", {"doc": h, "object": "TwoPad"})
    qt = await m.call("query_object", {"doc": h, "object": "TwoPad"})
    log.write({"TwoPad_props": {k: prop(qt, k) for k in ("Type", "Length", "Length2", "Midplane")}, "TwoPad_bbox": bb(mt)})
    l2 = prop(qt, "Length2")
    log.check("TwoPad vol > 6000 and Length2 = 4 mm", (vol(mt) or 0) > 6000.0 and "4" in json.dumps(l2),
              f"vol={vol(mt)} Length2={l2} Type={prop(qt, 'Type')} bbox={bb(mt)}")
    mtp = await m.call("query_mass_properties", {"doc": h, "object": "TaperPad"})
    qtp = await m.call("query_object", {"doc": h, "object": "TaperPad"})
    ta = prop(qtp, "TaperAngle")
    log.check("TaperPad vol != 6000 and TaperAngle = 5 deg", vol(mtp) is not None and not near(vol(mtp), 6000.0) and "5" in json.dumps(ta),
              f"vol={vol(mtp)} TaperAngle={ta}")
    vs = [await m.call("verify_shape", {"doc": h, "object": o}) for o in ("RevPad", "TwoPad", "TaperPad")]
    log.check("verify_shape OK x3", all(v.get("status") == "OK" for v in vs), [v.get("status") for v in vs])
    before = set(snap_temp())
    await m.call("feature_body_create", {"doc": h, "name": "BadTaperBody"})
    await sketch(m, h, "BadTaperProfile", "BadTaperBody", rect_profile(120, 0, 20, 30))
    bad = await m.call("feature_pad", {"doc": h, "body": "BadTaperBody", "profile": "BadTaperProfile", "name": "BadTaperPad",
                                       "length": q(10), "taper_angle": q(120, "deg")})
    log.check("taper 120 deg INVALID_INPUT 'taper_angle must be in', no snapshot_path",
              bad.get("status") == "INVALID_INPUT" and "taper_angle must be in" in detail_msg(bad) and not mut(bad).get("snapshot_path")
              and set(snap_temp()) == before, short(bad))
    log.note("BadTaperBody/BadTaperProfile (fixture for the refusal) is deleted from the view by closing? no - left; it holds only a sketch")
    await capture(m, h, "tc-04-04-after.png")
    log.write({"doc": h})


go("tc-04-04", body)
