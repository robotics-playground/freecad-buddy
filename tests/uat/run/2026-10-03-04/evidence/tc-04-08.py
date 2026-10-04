from tc04lib import *  # noqa: F401,F403

TOP = sel("PlatePad", "Face6")


async def body(m, log):
    h = sc(await m.call("document_create", {"label": "ThreadPlate"})).get("doc")
    await body_pad(m, h, "PlateBody", "PlateProfile", "PlatePad", rect_profile(0, 0, 60, 40), 5)
    await sketch(m, h, "ThreadProfile", "PlateBody", point_profile(30, 20), face=TOP)
    v = await m.call("verify_sketch", {"doc": h, "sketch": "ThreadProfile"})
    log.check("Given ThreadProfile dof=0", (sc(v).get("subject") or {}).get("dof") == 0, short(v))
    caps = await m.call("query_capabilities", {})
    en = (sc(caps).get("enums") or {}).get("PartDesign::Hole") or {}
    log.check("Given ThreadType and HoleCutType enumerations known (query_capabilities)",
              "ISOMetricProfile" in (en.get("ThreadType") or []) and "Counterbore" in (en.get("HoleCutType") or []), json.dumps(en))
    th = await m.call("feature_hole", {"doc": h, "body": "PlateBody", "profile": "ThreadProfile", "name": "ThreadedHole",
                                       "thread_type": "ISOMetricProfile", "cut_type": "Counterbore", "depth": q(4)})
    qo = await m.call("query_object", {"doc": h, "object": "ThreadedHole"})
    p = sc(qo).get("properties") or {}
    log.write({"ThreadedHole_props": {k: p.get(k) for k in ("ThreadType", "HoleCutType", "Threaded", "ThreadSize", "Diameter",
                                                           "HoleCutDiameter", "HoleCutDepth", "Depth", "ModelThread", "DrillPoint")}})
    log.check("threaded hole OK rolled_back=false", ok_commit(th), short(th, 500))
    log.check("ThreadType=ISOMetricProfile and HoleCutType=Counterbore", p.get("ThreadType") == "ISOMetricProfile" and p.get("HoleCutType") == "Counterbore",
              {k: p.get(k) for k in ("ThreadType", "HoleCutType")})
    log.check("Threaded=true", p.get("Threaded") is True, p.get("Threaded"))
    before = set(snap_temp())
    d = await m.call("feature_hole", {"doc": h, "body": "PlateBody", "profile": "ThreadProfile", "name": "DiaThread",
                                      "thread_type": "ISOMetricProfile", "cut_type": "Counterbore", "depth": q(4), "diameter": q(5)})
    log.check("diameter + thread_type INVALID_INPUT", d.get("status") == "INVALID_INPUT" and "'diameter' cannot be combined with thread_type=" in detail_msg(d), short(d))
    c = await m.call("feature_hole", {"doc": h, "body": "PlateBody", "profile": "ThreadProfile", "name": "BadCut",
                                      "thread_type": "ISOMetricProfile", "cut_type": "Spotface", "depth": q(4)})
    log.check("cut_type outside the re-populated set INVALID_INPUT 'is not one of'", c.get("status") == "INVALID_INPUT" and "is not one of" in detail_msg(c), short(c, 600))
    f = await m.call("feature_hole", {"doc": h, "body": "PlateBody", "profile": "ThreadProfile", "name": "FakeThread",
                                      "thread_type": "ISOMetricFake", "depth": q(4)})
    log.check("unknown thread_type INVALID_INPUT, no snapshot_path", f.get("status") == "INVALID_INPUT" and not mut(f).get("snapshot_path"), short(f))
    log.note(f"new temp snapshots during refusals: {sorted(set(snap_temp()) - before)}")
    vs = await m.call("verify_shape", {"doc": h, "object": "ThreadedHole"})
    log.check("verify_shape OK", vs.get("status") == "OK", short(vs))
    log.write({"shape_summary": ss(th)})
    await capture(m, h, "tc-04-08-after.png")
    log.write({"doc": h})


go("tc-04-08", body)
