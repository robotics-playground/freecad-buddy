from tc05lib import *


async def body(m, log):
    docs = sc(await m.call("document_list", {})).get("documents") or []
    doc = [d for d in docs if d["label"] == "TC0517"][0]["doc"]
    log.note("literal TC args {geometry:[0]} were refused (sketch_remove_geometry() got an unexpected keyword argument 'geometry'; tc-05-17-checks.txt). Shipped parameter is geo_ids (sketches.py:848). Same document, unchanged.")
    preview, env = await apply(m, doc, "sketch_remove_geometry", {"sketch": "Sketch", "geo_ids": [0]})
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


go("tc-05-17b", body)
