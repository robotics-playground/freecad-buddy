from tc04lib import *  # noqa: F401,F403


async def case(m, log, label, edge, tag, capture_name=None):
    h = sc(await m.call("document_create", {"label": label})).get("doc")
    await body_pad(m, h, "PlateBody", "PlateProfile", "PlatePad", rect_profile(0, 0, 60, 40), 5)
    mp = await m.call("query_mass_properties", {"doc": h, "object": "PlatePad"})
    log.check(f"[{tag}] Given PlatePad vol 12000", near(vol(mp), 12000.0), vol(mp))
    base = snaps()
    log.note(f"[{tag}] snapshot dirs before (TEMP + workdir/tmp): {base}")
    if capture_name:
        await capture(m, h, capture_name + "-before.png")
    f = await m.call("feature_fillet", {"doc": h, "body": "PlateBody", "base": "PlatePad", "name": "TooBigFillet",
                                        "edges": [sel("PlatePad", edge)], "radius": q(20)})
    mu = mut(f)
    log.write({"tag": tag, "mutation_summary": {k: mu.get(k) for k in ("rolled_back", "rollback_proven", "snapshot_path", "verify_verdict")},
               "post_verify": pv(f), "fp_before": (mu.get("fingerprint_before") or {}).get("digest"), "fp_after": (mu.get("fingerprint_after") or {}).get("digest")})
    log.check(f"[{tag}] non-OK status RECOMPUTE_ERROR or SPEC_FAILED", f.get("status") in ("RECOMPUTE_ERROR", "SPEC_FAILED"), short(f, 500))
    log.check(f"[{tag}] mutation.rolled_back=true", mu.get("rolled_back") is True, {k: mu.get(k) for k in ("rolled_back", "rollback_proven", "snapshot_path")})
    ex = pv(f).get("explanation") or ""
    log.check(f"[{tag}] explanation non-empty, names TooBigFillet and the engine status", bool(ex) and "TooBigFillet" in ex, ex[:400])
    tr = await m.call("query_tree_summary", {"doc": h, "depth": 3})
    log.check(f"[{tag}] tree names no TooBigFillet", "TooBigFillet" not in tree_names(tr), "")
    mp2 = await m.call("query_mass_properties", {"doc": h, "object": "PlatePad"})
    log.check(f"[{tag}] PlatePad vol 12000 again", near(vol(mp2), 12000.0), vol(mp2))
    fb, fa = (mu.get("fingerprint_before") or {}).get("digest"), (mu.get("fingerprint_after") or {}).get("digest")
    log.check(f"[{tag}] fingerprint before == after, or rolled_back_via_snapshot", (fb and fb == fa) or mu.get("rollback_proven") == "rolled_back_via_snapshot",
              f"before={fb} after={fa} rollback_proven={mu.get('rollback_proven')}")
    after = snaps()
    log.check(f"[{tag}] snapshot deleted (no new snapshot dir)", set(after) == set(base), f"new={sorted(set(after) - set(base))}")
    vr = await m.call("verify_recompute", {"doc": h})
    log.check(f"[{tag}] verify_recompute OK", vr.get("status") == "OK", short(vr, 300))
    return h, f


async def body(m, log):
    log.note("Literal Edge1 is a 5 mm VERTICAL corner edge on 1.1.4 (oracle); a 20 mm round on it fits inside the 60/40 mm side faces. "
             "The TC intent (20 mm on a 5 mm thick plate) is a horizontal edge: Edge3 (60 mm bottom edge) is also run.")
    h1, f1 = await case(m, log, "TooBigLiteral", "Edge1", "literal Edge1", capture_name="tc-04-16-literal")
    if f1.get("status") == "OK":
        await capture(m, h1, "tc-04-16-literal-after.png")
    await m.call("document_close", {"doc": h1})
    h2, f2 = await case(m, log, "TooBigFillet", "Edge3", "horizontal Edge3", capture_name="tc-04-16")
    await capture(m, h2, "tc-04-16-after.png")
    log.write({"doc": h2})


go("tc-04-16", body)
