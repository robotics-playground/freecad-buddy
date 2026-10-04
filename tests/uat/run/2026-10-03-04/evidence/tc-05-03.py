from tc05lib import *


async def body(m, log):
    docs = sc(await m.call("document_list", {})).get("documents") or []
    doc = [d for d in docs if d["label"] == "TC0503"][0]["doc"]
    si = await m.call("query_sketch_info", {"doc": doc, "sketch": "Sketch"})
    log.note(f"query_sketch_info (TC verify) reports no dof field: keys={sorted(sc(si))}; constraints={len(sc(si).get('constraints') or [])}")
    v = await m.call("verify_sketch", {"doc": doc, "sketch": "Sketch"})
    s = sc(v).get("subject") or {}
    log.check("Given Sketch dof > 0 (verify_sketch, second domain)", (s.get("dof") or 0) > 0, {k: s.get(k) for k in ("dof", "fully_constrained")})
    fit, rec = await capture(m, doc, "tc-05-03-before.png")
    log.note(f"before fit={fit}")
    preview, env = await apply(m, doc, "feature_pad", {"body": "Body", "profile": "Sketch", "name": "Pad", "length": q(10)})
    p = pv(env)
    log.note(f"preview validity={json.dumps(sc(preview).get('diff', {}).get('validity'))[:300]}")
    log.note(f"feature_pad -> status={env.get('status')} rolled_back={mut(env).get('rolled_back')} post_verify={json.dumps(p)[:600]}")
    log.check("recompute_clean true", p.get("recompute_clean") is True, p.get("recompute_clean"))
    log.check("is_valid true", p.get("is_valid") is True, p.get("is_valid"))
    log.check("fully_constrained false and explanation starts 'verify_sketch failed on Sketch (dof='",
              p.get("fully_constrained") is False and str(p.get("explanation") or "").startswith("verify_sketch failed on Sketch (dof="),
              {"fully_constrained": p.get("fully_constrained"), "explanation": p.get("explanation")})
    log.check("tnp_audit.findings == [] (short-circuit block)", (p.get("tnp_audit") or {}).get("findings") == [], json.dumps(p.get("tnp_audit"))[:300])
    log.check("status SPEC_FAILED", env.get("status") == "SPEC_FAILED", short(env))
    tr = await m.call("query_tree_summary", {"doc": doc, "depth": 2})
    log.check("Pad not in tree", not tree_has(tr, "Pad"), tree_names(tr)[:500])
    log.write({"doc": doc})


go("tc-05-03", body)
