import os
from tc05lib import *


async def body(m, log):
    await close_all(m, log)
    log.check("Given swap payload sphere-r10.FCStd present", os.path.exists("D:/Work/Personal/Sources/freecad-buddy/benchmarks/g0/golden-models/sphere-r10.FCStd"), "")
    log.note("file-swap harness NOT armed: snapshot dirs are created by the FreeCAD process with an ACL this (non-elevated) shell cannot read or write "
             "(listdir/icacls -> Access is denied, tc-05-02b-snapwatch.log). Using the 'document known to take the snapshot-restore path' branch of the Given: "
             "feature_set_parameters Fillet Radius 400 (TC-05-06 reproducer) reached the unproven path in tc-05-06.")
    doc = await body_sketch(m, "TC0507", pad=30)
    p, f = await apply(m, doc, "feature_fillet", {"body": "Body", "base": "Pad", "name": "Fillet", "edges": [sel("Pad", "Edge1")], "radius": q(2)})
    log.note(f"fixture Fillet r2 -> {short(f)}")
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
    home = os.path.expanduser("~")
    full = os.path.join(home, sp) if sp and not os.path.isabs(sp) else sp
    d = os.path.dirname(full) if full else None
    log.note(f"snapshot_path is relative ({sp!r}); resolved against home -> {full}")
    log.check("snapshot dir still on disk (shell can see the dir; file listing is ACL-denied)", bool(d and os.path.isdir(d)), d)
    log.write({"kept_snapshot": full})
    text = env.get("text") or ""
    log.check("text exactly 'Mutation failed and its rollback could not be proven: {snapshot_path}.' and no 'rolled back'/'restored'",
              text == f"Mutation failed and its rollback could not be proven: {sp}." and "rolled back" not in text and "restored" not in text, text)
    ex = pv(env).get("explanation") or ""
    log.check("explanation ends 'rollback could not be proven: ... pre-mutation fingerprint ' + before digest",
              ex.endswith(f"rollback could not be proven: the snapshot-restored document does not match the pre-mutation fingerprint {fb}"), ex)
    fm = await m.call("query_mass_properties", {"doc": doc, "object": "Fillet"})
    log.note(f"Fillet volume after (r2 => 11974.2478): {vol(fm)}")
    fb_objs = {o['name']: o for o in (mb.get('fingerprint_before') or {}).get('objects', [])}
    fa_objs = {o['name']: o for o in (mb.get('fingerprint_after') or {}).get('objects', [])}
    diffs = []
    for n in sorted(set(fb_objs) | set(fa_objs)):
        a, b = fb_objs.get(n) or {}, fa_objs.get(n) or {}
        if a != b:
            diffs.append({"name": n, "brep_equal": a.get("brep_sha256") == b.get("brep_sha256"), "massprops_equal": a.get("massprops") == b.get("massprops")})
    log.note(f"before/after fingerprint object diffs: {diffs}")
    fit, rec = await capture(m, doc, "tc-05-07-after.png")
    log.note(f"after fit={fit}")


go("tc-05-07", body)
