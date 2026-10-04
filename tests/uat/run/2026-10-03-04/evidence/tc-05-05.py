from tc05lib import *


async def body(m, log):
    await close_all(m, log)
    doc = await body_sketch(m, "TC0505", pad=30)
    pm = await m.call("query_mass_properties", {"doc": doc, "object": "Pad"})
    log.check("Given Pad volume 12000.0", near(vol(pm), 12000.0, 1e-6), vol(pm))
    fit, rec = await capture(m, doc, "tc-05-05-before.png")
    log.note(f"before fit={fit}")
    base_snaps = set(run_snaps())
    args = {"body": "Body", "base": "Pad", "name": "Fillet", "edges": [sel("Pad", "Edge1")], "radius": q(500)}
    preview, env = await apply(m, doc, "feature_fillet", args)
    fpb = (sc(preview).get("diff") or {}).get("fingerprint_before")
    mb = mut(env)
    log.note(f"preview validity={json.dumps((sc(preview).get('diff') or {}).get('validity'))[:300]}")
    log.check("returned a ResultEnvelope, not MCP isError", env.get("_isError") is False and "status" in env, short(env))
    log.check("rolled_back true, rollback_proven 'rolled_back_verified'", mb.get("rolled_back") is True and mb.get("rollback_proven") == "rolled_back_verified",
              {k: mb.get(k) for k in ("rolled_back", "rollback_proven")})
    log.check("snapshot_path null", mb.get("snapshot_path", "MISSING") is None, mb.get("snapshot_path", "MISSING"))
    log.check("fingerprint_after.digest == preview diff.fingerprint_before", digest(env, "fingerprint_after") == fpb and fpb is not None, {"after": digest(env, "fingerprint_after"), "preview_before": fpb})
    st = env.get("status")
    code = (env.get("detail") or {}).get("code")
    log.check("status SPEC_FAILED or RECOMPUTE_ERROR, detail.code == 'mutation.'+lower", st in ("SPEC_FAILED", "RECOMPUTE_ERROR") and code == f"mutation.{str(st).lower()}", {"status": st, "code": code})
    log.check("text starts 'Mutation rolled back (rolled_back_verified): '", str(env.get("text") or "").startswith("Mutation rolled back (rolled_back_verified): "), env.get("text"))
    pm2 = await m.call("query_mass_properties", {"doc": doc, "object": "Pad"})
    tr = await m.call("query_tree_summary", {"doc": doc, "depth": 3})
    log.check("Pad volume still 12000.0 and no Fillet in tree", near(vol(pm2), 12000.0, 1e-6) and not tree_has(tr, "Fillet"), {"vol": vol(pm2), "fillet": tree_has(tr, "Fillet")})
    log.check("snapshot cleaned up (no new FCB_TMP_snap_*)", set(run_snaps()) - base_snaps == set(), sorted(set(run_snaps()) - base_snaps))
    fit, rec = await capture(m, doc, "tc-05-05-after.png")
    log.note(f"after fit={fit}")
    log.write({"doc": doc})


go("tc-05-05", body)
