import os
from tc05lib import *


async def body(m, log):
    await close_all(m, log)
    log.note("attempt 1 (fresh pad+fillet, Radius 400) rolled back VERIFIED -> not a snapshot-path document (tc-05-07-attempt1-*). "
             "Attempt 2 rebuilds the TC-05-06 history (fillet, Sketch001 on Fillet.Face5, committed pocket 900) that went unproven in tc-05-06.")
    doc = await body_sketch(m, "TC0507", pad=30)
    await apply(m, doc, "feature_fillet", {"body": "Body", "base": "Pad", "name": "Fillet", "edges": [sel("Pad", "Edge1")], "radius": q(2)})
    await apply(m, doc, "sketch_create", {"name": "Sketch001", "body": "Body", "face": sel("Fillet", "Face5")})
    g, c = rect_profile(5, 5, 5, 5)
    await apply(m, doc, "sketch_add_geometry", {"sketch": "Sketch001", "geometry": g, "constraints": c})
    p, k = await apply(m, doc, "feature_pocket", {"body": "Body", "profile": "Sketch001", "name": "Pocket", "length": q(900)})
    log.note(f"fixture pocket -> {short(k)}")
    fit, rec = await capture(m, doc, "tc-05-07-before.png")
    log.note(f"before fit={fit}")
    preview, env = await apply(m, doc, "feature_set_parameters", {"feature": "Fillet", "parameters": {"Radius": q(400)}})
    mb = mut(env)
    fb = digest(env, "fingerprint_before")
    sp = mb.get("snapshot_path")
    log.note(f"envelope: status={env.get('status')} text={env.get('text')!r}")
    log.check("rolled_back false", mb.get("rolled_back") is False, mb.get("rolled_back"))
    log.check("rollback_proven null", mb.get("rollback_proven") is None, mb.get("rollback_proven"))
    log.check("status SPEC_FAILED", env.get("status") == "SPEC_FAILED", env.get("status"))
    log.check("snapshot_path non-null", bool(sp), sp)
    full = os.path.join(os.path.expanduser("~"), sp) if sp and not os.path.isabs(sp) else sp
    d = os.path.dirname(full) if full else None
    log.note(f"snapshot_path is relative ({sp!r}); resolved against home -> {full}")
    log.check("snapshot dir still on disk (dir visible; file listing ACL-denied to this shell)", bool(d and os.path.isdir(d)), d)
    log.write({"kept_snapshot": full})
    text = env.get("text") or ""
    log.check("text exactly 'Mutation failed and its rollback could not be proven: {snapshot_path}.' and no 'rolled back'/'restored'",
              text == f"Mutation failed and its rollback could not be proven: {sp}." and "rolled back" not in text and "restored" not in text, text)
    ex = pv(env).get("explanation") or ""
    log.check("explanation ends 'rollback could not be proven: ... pre-mutation fingerprint ' + before digest",
              ex.endswith(f"rollback could not be proven: the snapshot-restored document does not match the pre-mutation fingerprint {fb}"), ex)
    fb_objs = {o['name']: o for o in (mb.get('fingerprint_before') or {}).get('objects', [])}
    fa_objs = {o['name']: o for o in (mb.get('fingerprint_after') or {}).get('objects', [])}
    diffs = [{"name": n, "brep_equal": (fb_objs.get(n) or {}).get("brep_sha256") == (fa_objs.get(n) or {}).get("brep_sha256"),
              "massprops_equal": (fb_objs.get(n) or {}).get("massprops") == (fa_objs.get(n) or {}).get("massprops")}
             for n in sorted(set(fb_objs) | set(fa_objs)) if fb_objs.get(n) != fa_objs.get(n)]
    log.note(f"before vs after fingerprint object diffs: {diffs}")
    for o in ("Fillet", "Body"):
        r = await m.call("query_mass_properties", {"doc": doc, "object": o})
        log.note(f"{o} volume after: {vol(r)}")
    fit, rec = await capture(m, doc, "tc-05-07-after.png")
    log.note(f"after fit={fit}")


go("tc-05-07", body)
