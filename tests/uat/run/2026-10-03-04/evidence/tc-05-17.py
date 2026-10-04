from tc05lib import *


async def body(m, log):
    await close_all(m, log)
    doc = await body_sketch(m, "TC0517", pad=30)
    p, f = await apply(m, doc, "feature_fillet", {"body": "Body", "base": "Pad", "name": "Fillet", "edges": [sel("Pad", "Edge1")], "radius": q(2)})
    log.note(f"fixture Fillet -> {short(f)}")
    fit, rec = await capture(m, doc, "tc-05-17-before.png")
    log.note(f"before fit={fit}")
    preview, env = await apply(m, doc, "sketch_remove_geometry", {"sketch": "Sketch", "geometry": [0]})
    mb, p = mut(env), pv(env)
    t = p.get("tnp_audit") or {}
    log.note(f"preview={short(preview, 300)} validity={json.dumps((sc(preview).get('diff') or {}).get('validity'))[:300]} tnp_precheck={json.dumps((sc(preview).get('diff') or {}).get('tnp_precheck'))[:300]}")
    log.note(f"envelope status={env.get('status')} text={env.get('text')!r}")
    log.note(f"post_verify={json.dumps(p)[:900]}")
    log.check("tnp_audit.status FLAGGED", t.get("status") == "FLAGGED", t.get("status"))
    br = [x for x in (t.get("findings") or []) if x.get("verdict") == "BROKEN"]
    log.check("a BROKEN finding present", bool(br), t.get("findings"))
    log.check("BROKEN finding at layer 0 or 1", bool(br) and br[0].get("layer") in (0, 1), br[:1])
    log.check("BROKEN owner == 'Fillet'", bool(br) and br[0].get("owner") == "Fillet", br[:1])
    log.check("rolled_back true", mb.get("rolled_back") is True, {k: mb.get(k) for k in ("rolled_back", "rollback_proven")})
    fm = await m.call("query_mass_properties", {"doc": doc, "object": "Fillet"})
    log.check("Fillet intact after rollback: query_mass_properties OK", fm.get("status") == "OK", {"status": fm.get("status"), "vol": vol(fm)})
    log.check("if recompute_clean false, tnp_audit.status is not CLEAN", (p.get("recompute_clean") is not False) or t.get("status") != "CLEAN", {"recompute_clean": p.get("recompute_clean"), "tnp": t.get("status")})
    fit, rec = await capture(m, doc, "tc-05-17-after.png")
    log.note(f"after fit={fit}")


go("tc-05-17", body)
