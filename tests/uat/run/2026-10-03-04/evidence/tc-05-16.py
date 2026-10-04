from tc05lib import *


async def body(m, log):
    await close_all(m, log)
    doc = await body_sketch(m, "TC0516", pad=30)
    p, f = await apply(m, doc, "feature_fillet", {"body": "Body", "base": "Pad", "name": "Fillet", "edges": [sel("Pad", "Edge1")], "radius": q(2)})
    log.note(f"fixture Fillet -> {short(f)}")
    qo = await m.call("query_object", {"doc": doc, "object": "Fillet"})
    base = (sc(qo).get("properties") or {}).get("Base")
    log.check("Given Fillet Base names Pad and Edge1", "Pad" in json.dumps(base) and "Edge1" in json.dumps(base), json.dumps(base)[:200])
    fit, rec = await capture(m, doc, "tc-05-16-before.png")
    log.note(f"before fit={fit}")
    preview, env = await apply(m, doc, "feature_chamfer", {"body": "Body", "base": "Pad", "name": "Chamfer", "edges": [sel("Pad", "Edge2")], "size": q(3)})
    t = pv(env).get("tnp_audit") or {}
    mb = mut(env)
    pre = (sc(preview).get("diff") or {}).get("tnp_precheck") or {}
    log.note(f"preview validity={json.dumps((sc(preview).get('diff') or {}).get('validity'))[:300]} tnp_precheck={json.dumps(pre)[:300]}")
    log.note(f"envelope status={env.get('status')} text={env.get('text')!r} tnp={json.dumps(t)[:600]}")
    log.check("tnp_audit.status FLAGGED", t.get("status") == "FLAGGED", t.get("status"))
    rp = [x for x in (t.get("findings") or []) if x.get("verdict") == "REPOINTED" and x.get("owner") == "Fillet"]
    log.check("REPOINTED finding owned by Fillet", bool(rp), t.get("findings"))
    log.check("finding layer 1 or 2", bool(rp) and rp[0].get("layer") in (1, 2), rp[:1])
    p = pv(env)
    log.check("recompute_clean true, is_valid true, explanation starts 'TNP audit flagged '", p.get("recompute_clean") is True and p.get("is_valid") is True and str(p.get("explanation") or "").startswith("TNP audit flagged "),
              {k: p.get(k) for k in ("recompute_clean", "is_valid", "explanation")})
    log.check("rolled_back true, proof verified/via_snapshot", mb.get("rolled_back") is True and mb.get("rollback_proven") in ("rolled_back_verified", "rolled_back_via_snapshot"), {k: mb.get(k) for k in ("rolled_back", "rollback_proven")})
    tr = await m.call("query_tree_summary", {"doc": doc, "depth": 3})
    log.check("Chamfer not in tree", not tree_has(tr, "Chamfer"), tree_has(tr, "Chamfer"))
    log.check("preview diff.tnp_precheck.status FLAGGED", pre.get("status") == "FLAGGED", pre.get("status"))
    fit, rec = await capture(m, doc, "tc-05-16-after.png")
    log.note(f"after fit={fit}")


go("tc-05-16", body)
