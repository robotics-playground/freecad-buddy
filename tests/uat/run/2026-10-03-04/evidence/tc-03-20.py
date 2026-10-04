from tc03lib import *  # noqa: F401,F403

FACE6 = {"kind": "mapped_name", "object": "PlatePad", "mapped_name": "Face6"}


async def body(m, log):
    doc = await new_doc(m, "BracketPlate")
    await plate(m, doc)
    await m.call("sketch_create", {"doc": doc, "name": "BossProfile", "face": FACE6, "body": "PlateBody"})
    ext = await m.call("sketch_add_external_geometry", {"doc": doc, "sketch": "BossProfile",
                                                        "edge": {"kind": "mapped_name", "object": "PlatePad", "mapped_name": "Edge3"}})
    dep = await m.call("query_dependencies", {"doc": doc})
    log.check("Given dependency BossProfile -> PlatePad", {"from": "BossProfile", "to": "PlatePad"} in (sc(dep).get("edges") or []), f"ext={ext.get('status')}")
    t0 = pv(ext).get("tnp_audit") or {}
    log.check("Given add_external_geometry tnp_audit.status=CLEAN", t0.get("status") == "CLEAN", json.dumps(t0)[:300])
    fit0 = await m.fit(doc)
    log.note(f"before fit: {fit0}")
    log.write({"shot": shot("tc-03-20-before.png")})

    p = await m.call("feature_set_parameters", {"doc": doc, "feature": "PlatePad", "parameters": {"Length": {"value": 30, "unit": "mm"}}})
    c = await m.call("sketch_add_constraint", {"doc": doc, "sketch": "BossProfile", "constraints": [{"type": "Horizontal", "first": 0}]})
    log.note(f"feature_set_parameters: {p.get('status')} tnp={json.dumps(pv(p).get('tnp_audit'))[:400]}")
    log.note(f"sketch_add_constraint: {p.get('status') and c.get('status')} {json.dumps(c.get('detail'))[:200]} tnp={json.dumps(pv(c).get('tnp_audit'))[:300]}")

    muts = [x for x in (p, c) if mut(x)]
    log.check("each mutation envelope carries tnp_audit with status and findings",
              len(muts) == 2 and all("status" in (pv(x).get("tnp_audit") or {}) and "findings" in (pv(x).get("tnp_audit") or {}) for x in muts),
              f"feature_set_parameters has={bool(pv(p).get('tnp_audit'))}; sketch_add_constraint status={c.get('status')} has_mutation={bool(mut(c))}")
    findings = (pv(p).get("tnp_audit") or {}).get("findings", []) + (pv(c).get("tnp_audit") or {}).get("findings", [])
    broken = [f for f in findings if f.get("verdict") == "BROKEN"]
    log.check("a BROKEN finding names BossProfile as owner", any(f.get("owner") == "BossProfile" for f in broken), json.dumps(findings)[:500])
    log.check("BROKEN fails the mutation (SPEC_FAILED rolled_back)", None if not broken else any(x.get("status") == "SPEC_FAILED" and mut(x).get("rolled_back") for x in (p, c)),
              "no BROKEN finding was produced, so not reachable" if not broken else "")
    log.check("explanation starts 'TNP audit flagged'", None if not broken else any((pv(x).get("explanation") or "").startswith("TNP audit flagged") for x in (p, c)),
              "not reachable" if not broken else "")
    rb = [f for f in findings if f.get("verdict") == "RE_BASELINED"]
    log.check("RE_BASELINED leaves status=OK", None if not rb else all(x.get("status") == "OK" for x in (p, c) if any(f in (pv(x).get("tnp_audit") or {}).get("findings", []) for f in rb)),
              "no RE_BASELINED finding produced" if not rb else json.dumps(rb)[:300])
    log.check("element_map_version non-empty on clean and flagged readings", bool(t0.get("element_map_version")) and bool((pv(p).get("tnp_audit") or {}).get("element_map_version")),
              f"clean={t0.get('element_map_version')} after={(pv(p).get('tnp_audit') or {}).get('element_map_version')}")
    vr = await m.call("verify_recompute", {"doc": doc})
    log.check("verify_recompute OK after", vr.get("status") == "OK", short(vr))
    mp = await m.call("query_mass_properties", {"doc": doc, "object": "PlatePad"})
    log.note(f"PlatePad volume after: {(sc(mp).get('volume') or {}).get('value')}")
    fit = await m.fit(doc)
    log.note(f"after fit: {fit}")
    log.write({"shot": shot("tc-03-20-after.png")})
    log.write({"edit_after": edit_capture("BossProfile", "tc-03-20-edit-after.png", parent="PlateBody")})
    log.write({"doc": doc})


go("tc-03-20", body)
