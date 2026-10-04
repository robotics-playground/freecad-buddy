from tc05lib import *


async def body(m, log):
    doc = await body_sketch(m, "TC0501")
    si = await m.call("query_sketch_info", {"doc": doc, "sketch": "Sketch"})
    s = sc(si)
    log.check("Given Sketch fully_constrained true, dof 0", s.get("fully_constrained") is True and s.get("dof") == 0,
              {k: s.get(k) for k in ("fully_constrained", "dof")})
    before_mp = await m.call("query_mass_properties", {"doc": doc, "object": "Body"})
    log.note(f"pre-mutation Body mass props: {short(before_mp, 400)}")
    preview, env = await apply(m, doc, "feature_pad", {"body": "Body", "profile": "Sketch", "name": "Pad", "length": q(30)})
    mb = mut(env)
    log.check("status OK, detail null", env.get("status") == "OK" and env.get("detail") is None, short(env))
    b, a = digest(env, "fingerprint_before"), digest(env, "fingerprint_after")
    log.check("fingerprints 64-hex and different", bool(b and a and HEX64.match(b) and HEX64.match(a) and a != b), f"{b} / {a}")
    p = pv(env)
    log.check("post_verify.passed true, explanation null", p.get("passed") is True and p.get("explanation") is None, {k: p.get(k) for k in ("passed", "explanation")})
    log.check("rolled_back false, rollback_proven null", mb.get("rolled_back") is False and mb.get("rollback_proven") is None,
              {k: mb.get(k) for k in ("rolled_back", "rollback_proven")})
    log.check("transaction_id '0', schema fcb.mutation/1", mb.get("transaction_id") == "0" and mb.get("schema") == "fcb.mutation/1",
              {k: mb.get(k) for k in ("transaction_id", "schema")})
    text = env.get("text") or ""
    log.check("text starts 'Mutation committed; fingerprint ' + first 12 of after", text.startswith("Mutation committed; fingerprint ") and bool(a) and a[:12] in text, text)
    pm = await m.call("query_mass_properties", {"doc": doc, "object": "Pad"})
    log.check("Pad volume 12000.0", near(vol(pm), 12000.0, 1e-6), vol(pm))
    fit, rec = await capture(m, doc, "tc-05-01-after.png")
    log.note(f"fit={fit}")
    log.write({"doc": doc})


go("tc-05-01", body)
