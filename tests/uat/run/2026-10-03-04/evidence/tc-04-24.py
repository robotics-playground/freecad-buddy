from tc04lib import *  # noqa: F401,F403


def props(qo):
    return sc(qo).get("properties") or {}


async def chain(m, label):
    h = sc(await m.call("document_create", {"label": label})).get("doc")
    await body_pad(m, h, "PlateBody", "PlateProfile", "PlatePad", rect_profile(0, 0, 60, 40), 5)
    await sketch(m, h, "SlotProfile", "PlateBody", rect_profile(10, 10, 10, 10), face=sel("PlatePad", "Face6"))
    await m.call("feature_pocket", {"doc": h, "body": "PlateBody", "profile": "SlotProfile", "name": "SlotPocket", "length": q(2)})
    await m.call("feature_fillet", {"doc": h, "body": "PlateBody", "base": "SlotPocket", "name": "CornerFillet",
                                    "edges": [sel("SlotPocket", "Edge1")], "radius": q(2)})
    return h


async def drive(m, log, tag, h, feature, prop, value, capture_name):
    vr0 = await m.call("verify_recompute", {"doc": h})
    log.check(f"[{tag}] Given verify_recompute OK", vr0.get("status") == "OK", short(vr0))
    before_val = props(await m.call("query_object", {"doc": h, "object": feature})).get(prop)
    base = snaps()
    await capture(m, h, capture_name + "-before.png")
    e = await m.call("feature_set_parameters", {"doc": h, "feature": feature, "parameters": {prop: value}})
    vr = await m.call("verify_recompute", {"doc": h})
    mu, p = mut(e), pv(e)
    log.write({"tag": tag, "mutation_summary": {k: mu.get(k) for k in ("rolled_back", "rollback_proven", "snapshot_path", "verify_verdict")}, "post_verify": p})
    log.check(f"[{tag}] status RECOMPUTE_ERROR", e.get("status") == "RECOMPUTE_ERROR", short(e, 500))
    log.check(f"[{tag}] recompute_clean=false", p.get("recompute_clean") is False, p.get("recompute_clean"))
    log.check(f"[{tag}] is_valid and fully_constrained not measured", p.get("is_valid") in ("not_measured", None, False) and p.get("fully_constrained") == "not_measured",
              {k: p.get(k) for k in ("is_valid", "fully_constrained")})
    ex = p.get("explanation") or ""
    log.check(f"[{tag}] explanation starts 'recompute left' and names {feature}", ex.startswith("recompute left") and feature in ex, ex[:300])
    log.check(f"[{tag}] rolled_back=true", mu.get("rolled_back") is True, {k: mu.get(k) for k in ("rolled_back", "rollback_proven", "snapshot_path")})
    after_val = props(await m.call("query_object", {"doc": h, "object": feature})).get(prop)
    log.check(f"[{tag}] old {prop} restored", after_val == before_val, f"before={before_val} after={after_val}")
    vr2 = await m.call("verify_recompute", {"doc": h})
    log.check(f"[{tag}] verify_recompute OK again", vr2.get("status") == "OK", short(vr2, 300))
    log.check(f"[{tag}] snapshot deleted", set(snaps()) == set(base), f"new={sorted(set(snaps()) - set(base))}")
    await capture(m, h, capture_name + "-after.png")
    return e


async def body(m, log):
    h = await chain(m, "RecomputeError")
    log.note("chain: PlatePad -> SlotPocket (10x10x2 on top face) -> CornerFillet (r=2 on SlotPocket Edge1)")
    e = await drive(m, log, "literal SlotPocket Length 500", h, "SlotPocket", "Length", q(500), "tc-04-24")
    if e.get("status") == "OK":
        log.note("literal step committed OK: a 500 mm pocket simply cuts through a 5 mm plate - no engine failure. "
                 "Running the TC's other named trigger, a fillet whose radius consumes its face, on a fresh identical chain")
        h2 = await chain(m, "RecomputeErrorFillet")
        await drive(m, log, "fillet Radius 30", h2, "CornerFillet", "Radius", q(30), "tc-04-24-fillet")
        log.write({"doc2": h2})
    log.write({"doc": h})


go("tc-04-24", body)
