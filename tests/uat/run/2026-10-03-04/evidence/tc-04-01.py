from tc04lib import *  # noqa: F401,F403

BOX = "D:/Work/Personal/Sources/freecad-buddy/benchmarks/g0/golden-models/box-10-20-30.FCStd"


async def body(m, log):
    h = sc(await m.call("document_create", {"label": "Bracket"})).get("doc")
    log.check("Given document_create Bracket returns a handle", bool(h), h)
    opened = await m.call("document_open", {"path": BOX})
    bh = sc(opened).get("doc")
    mp = await m.call("query_mass_properties", {"doc": bh, "object": "Box"})
    log.check("Given golden box opens, volume=6000.0", bool(bh) and near(vol(mp), 6000.0), f"doc={bh} vol={vol(mp)}")

    s1 = await m.call("feature_body_create", {"doc": h, "name": "PlateBody"})
    s2 = await m.call("feature_body_create", {"doc": bh, "name": "AdoptBody", "base_feature": "Box"})

    log.check("step 1 empty Body OK rolled_back=false", ok_commit(s1), short(s1))
    qo = await m.call("query_object", {"doc": h, "object": "PlateBody"})
    props = sc(qo).get("properties") or sc(qo)
    tip = props.get("Tip") if isinstance(props, dict) else None
    log.check("empty Body has no Tip", tip in (None, "", [], {}) or (isinstance(tip, dict) and not tip.get("value")),
              f"Tip={json.dumps(tip)[:200]}")
    log.write({"query_object_PlateBody_keys": list(props)[:80] if isinstance(props, dict) else None})
    tr = await m.call("query_tree_summary", {"doc": h, "depth": 3})
    t = tree_names(tr)
    log.check("PlateBody has an App::Origin child with planes/lines/point",
              "App::Origin" in t and "XY_Plane" in t and "X_Axis" in t and ("Origin" in t), t[:700])
    log.check("step 2 adoption OK rolled_back=false", ok_commit(s2), short(s2))
    am = await m.call("query_mass_properties", {"doc": bh, "object": "AdoptBody"})
    log.check("AdoptBody volume=6000.0 within 0.1%", near(vol(am), 6000.0), vol(am))
    vs = await m.call("verify_shape", {"doc": bh, "object": "AdoptBody"})
    log.check("verify_shape AdoptBody OK", vs.get("status") == "OK", short(vs))
    dbl = await m.call("feature_body_create", {"doc": bh, "name": "AdoptBody2", "base_feature": "Box"})
    log.check("double adoption INVALID_INPUT 'is already adopted by a Body'",
              dbl.get("status") == "INVALID_INPUT" and "is already adopted by a Body" in detail_msg(dbl), short(dbl))
    sk = await m.call("sketch_create", {"doc": bh, "name": "LooseSketch", "plane": "XY"})
    log.note(f"shapeless base fixture: sketch_create LooseSketch -> {sk.get('status')}")
    shp = await m.call("feature_body_create", {"doc": bh, "name": "SketchBody", "base_feature": "LooseSketch"})
    log.check("shapeless base INVALID_INPUT 'carries no shape to adopt'",
              shp.get("status") == "INVALID_INPUT" and "carries no shape to adopt" in detail_msg(shp), short(shp))
    tr2 = await m.call("query_tree_summary", {"doc": bh, "depth": 3})
    log.write({"box_tree": sc(tr2)})
    await capture(m, bh, "tc-04-01-after.png")
    log.write({"docs": [h, bh]})


go("tc-04-01", body)
