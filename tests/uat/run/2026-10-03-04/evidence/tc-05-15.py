from tc05lib import *


async def fixture(m, log, label):
    doc = await body_sketch(m, label, pad=30)
    p, f = await apply(m, doc, "feature_fillet", {"body": "Body", "base": "Pad", "name": "Fillet", "edges": [sel("Pad", "Edge1")], "radius": q(2)})
    log.note(f"fixture Fillet r2 on Pad.Edge1 -> {short(f)}")
    return doc


async def body(m, log):
    await close_all(m, log)
    doc = await fixture(m, log, "TC0515")
    dep = await m.call("query_dependencies", {"doc": doc})
    log.check("Given Fillet depends on Pad", {"from": "Fillet", "to": "Pad"} in (sc(dep).get("edges") or []), "")
    cap = sc(await m.call("query_capabilities", {}))
    log.check("Given element map available (query_capabilities.element_map_available; no version field there)", cap.get("element_map_available") is True, {k: cap.get(k) for k in ("element_map_available",)})
    fit, rec = await capture(m, doc, "tc-05-15-before.png")
    log.note(f"before fit={fit}")
    preview, env = await apply(m, doc, "feature_set_parameters", {"feature": "Pad", "parameters": {"Length": q(32)}})
    t = pv(env).get("tnp_audit") or {}
    log.note(f"envelope status={env.get('status')} tnp_audit={json.dumps(t)[:800]}")
    log.check("status OK", env.get("status") == "OK", short(env))
    log.check("tnp_audit.status CLEAN", t.get("status") == "CLEAN", t.get("status"))
    f = t.get("findings")
    log.check("every finding verdict in [PASS, RE_BASELINED]", isinstance(f, list) and all(x.get("verdict") in ("PASS", "RE_BASELINED") for x in f), [x.get("verdict") for x in (f or [])])
    log.check("element_map_version non-null string", isinstance(t.get("element_map_version"), str) and bool(t.get("element_map_version")), t.get("element_map_version"))
    log.check("findings NOT empty (check 4 graded the fillet reference)", bool(f), f)
    fm = await m.call("query_mass_properties", {"doc": doc, "object": "Fillet"})
    tr = await m.call("query_tree_summary", {"doc": doc, "depth": 3})
    log.check("Fillet query OK and still in tree", fm.get("status") == "OK" and tree_has(tr, "Fillet"), {"status": fm.get("status"), "vol": vol(fm)})
    fit, rec = await capture(m, doc, "tc-05-15-after.png")
    log.note(f"after fit={fit}")


go("tc-05-15", body)
