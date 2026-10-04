import os
from tc05lib import *

BOX = "D:/Work/Personal/Sources/freecad-buddy/benchmarks/g0/golden-models/box-10-20-30.FCStd"


async def body(m, log):
    await close_all(m, log)
    log.check("Given golden box present", os.path.exists(BOX), BOX)
    a = await m.call("document_open", {"path": BOX})
    b = await m.call("document_open", {"path": BOX})
    ha, hb = sc(a).get("doc"), sc(b).get("doc")
    log.note(f"open #1 -> {short(a)} {ha} name={sc(a).get('name')}; open #2 -> {short(b)} {hb} name={sc(b).get('name')}")
    log.check("two independent handles", bool(ha and hb and ha != hb), [ha, hb])
    pa = await m.call("preview_dry_run", {"doc": ha, "operation": {"tool": "feature_body_create", "args": {"name": "Probe"}}})
    pb = await m.call("preview_dry_run", {"doc": hb, "operation": {"tool": "feature_body_create", "args": {"name": "Probe"}}}) if hb else {}
    da = (sc(pa).get("diff") or {}).get("fingerprint_before")
    db = (sc(pb).get("diff") or {}).get("fingerprint_before")
    log.check("identical documents give identical digests", da is not None and da == db, [da, db])
    log.check("digest matches ^[0-9a-f]{64}$", bool(da and HEX64.match(da)), da)
    tok = sc(pa).get("preview_id")
    env = await m.call("feature_body_create", {"doc": ha, "name": "Probe", "confirm": {"preview_id": tok, "elicitation_action": "accept"}})
    mb = mut(env)
    fb, fa = mb.get("fingerprint_before") or {}, mb.get("fingerprint_after") or {}
    log.note(f"feature_body_create Probe on handle-a -> {short(env)}")
    log.check("serializer tag non-null non-empty on fingerprint_before", isinstance(fb.get("serializer"), str) and bool(fb.get("serializer")), fb.get("serializer"))
    log.check("serializer before == after", fb.get("serializer") == fa.get("serializer"), [fb.get("serializer"), fa.get("serializer")])
    objs = fb.get("objects")
    log.check("objects list, each with name, brep_sha256, massprops", isinstance(objs, list) and bool(objs) and all({"name", "brep_sha256", "massprops"} <= set(o) for o in objs), [sorted(o) for o in (objs or [])][:3])
    d = await body_sketch(m, "TC0513pad")
    p, pad = await apply(m, d, "feature_pad", {"body": "Body", "profile": "Sketch", "name": "Pad", "length": q(30)})
    log.check("real geometry change moves the digest (feature_pad)", pad.get("status") == "OK" and digest(pad, "fingerprint_before") != digest(pad, "fingerprint_after"),
              [digest(pad, "fingerprint_before"), digest(pad, "fingerprint_after")])
    c = await m.call("document_close", {"doc": d})
    log.note(f"TC0513pad closed -> {c.get('status')}")
    for h in (hb, ha):
        r = await m.call("query_tree_summary", {"doc": h, "depth": 1})
        log.note(f"{h}: {tree_names(r)[:200]}")
    fit, rec = await capture(m, ha, "tc-05-13-after.png")
    log.note(f"after fit (handle-a) = {fit}")


go("tc-05-13", body)
