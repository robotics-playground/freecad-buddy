from tc04lib import *  # noqa: F401,F403

DOC = [json.loads(l)["doc"] for l in open(EVIDENCE / "tc-04-23-given-mcp.jsonl", encoding="utf-8") if l.startswith('{"doc"')][-1]


async def body(m, log):
    h = DOC
    v = await m.call("verify_sketch", {"doc": h, "sketch": "LooseProfile"})
    dof = (sc(v).get("subject") or {}).get("dof")
    log.check("Given LooseProfile verify_sketch non-OK with dof > 0", v.get("status") != "OK" and (dof or 0) > 0, f"{short(v, 300)} dof={dof}")
    base = snaps()
    log.note(f"snapshot dirs before: {base}")
    await capture(m, h, "tc-04-23-before.png")
    e = await m.call("feature_pad", {"doc": h, "body": "LooseBody", "profile": "LooseProfile", "name": "LoosePad", "length": q(10)})
    mu, p = mut(e), pv(e)
    log.write({"mutation_summary": {k: mu.get(k) for k in ("rolled_back", "rollback_proven", "snapshot_path", "verify_verdict")}, "post_verify": p})
    log.check("status SPEC_FAILED", e.get("status") == "SPEC_FAILED", short(e, 500))
    log.check("rolled_back=true and post_verify.passed=false", mu.get("rolled_back") is True and p.get("passed") is False,
              {k: mu.get(k) for k in ("rolled_back", "rollback_proven")})
    ex = p.get("explanation") or ""
    log.check("explanation starts 'verify_sketch failed on LooseProfile (dof=' non-zero", ex.startswith("verify_sketch failed on LooseProfile (dof=") and "(dof=0" not in ex, ex[:300])
    log.check("recompute_clean=true, is_valid=true, fully_constrained=false", p.get("recompute_clean") is True and p.get("is_valid") is True and p.get("fully_constrained") is False,
              {k: p.get(k) for k in ("recompute_clean", "is_valid", "fully_constrained")})
    tr = await m.call("query_tree_summary", {"doc": h, "depth": 3})
    log.check("no LoosePad in tree", "LoosePad" not in tree_names(tr), "")
    qo = await m.call("query_object", {"doc": h, "object": "LooseBody"})
    log.check("LooseBody Tip null", (sc(qo).get("properties") or {}).get("Tip") is None, (sc(qo).get("properties") or {}).get("Tip"))
    fb, fa = (mu.get("fingerprint_before") or {}).get("digest"), (mu.get("fingerprint_after") or {}).get("digest")
    log.check("fingerprint before == after, or rolled_back_via_snapshot", (fb and fb == fa) or mu.get("rollback_proven") == "rolled_back_via_snapshot",
              f"before={fb} after={fa} rollback_proven={mu.get('rollback_proven')}")
    log.check("snapshot deleted (no new snapshot dir)", set(snaps()) == set(base), f"new={sorted(set(snaps()) - set(base))}")
    await capture(m, h, "tc-04-23-after.png")


go("tc-04-23", body)
