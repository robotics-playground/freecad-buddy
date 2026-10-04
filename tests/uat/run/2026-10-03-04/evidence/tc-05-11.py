import os
from tc05lib import *

ARGS = {"body": "Body", "profile": "Sketch", "name": "Pad", "length": q(30)}
PATCH = ("from freecad_buddy.usecases import transaction as _t\n_orig = _t.fingerprint\n_state = {'n': 0}\n"
         "def _fp(d):\n    _state['n'] += 1\n    if _state['n'] == 2:\n        _t.fingerprint = _orig\n        raise RuntimeError('injected serializer failure')\n    return _orig(d)\n"
         "_t.fingerprint = _fp")


async def body(m, log):
    await close_all(m, log)
    doc = await body_sketch(m, "TC0511")
    probe = await m.call("debug_exec", {"doc": doc, "code": "1"})
    log.check("Given debug_exec NOT refused", probe.get("status") == "OK", short(probe))
    v = await m.call("verify_sketch", {"doc": doc, "sketch": "Sketch"})
    log.check("Given Sketch fully constrained dof 0 (verify_sketch)", (sc(v).get("subject") or {}).get("dof") == 0, (sc(v).get("subject") or {}).get("dof"))
    preview = await m.call("preview_dry_run", {"doc": doc, "operation": {"tool": "feature_pad", "args": ARGS}})
    token = sc(preview).get("preview_id")
    log.note("patch applied AFTER preview_dry_run (the preview runs the bracket on a copy and would consume the call counter)")
    p = await m.call("debug_exec", {"doc": doc, "code": PATCH})
    log.note(f"literal TC patch -> {short(p)}")
    env = await m.call("feature_pad", dict(ARGS, doc=doc, confirm={"preview_id": token, "elicitation_action": "accept"}))
    mb = mut(env)
    sp = mb.get("snapshot_path")
    log.note(f"envelope status={env.get('status')} text={env.get('text')!r}")
    log.check("rolled_back false", mb.get("rolled_back") is False, mb.get("rolled_back"))
    log.check("status SPEC_FAILED", env.get("status") == "SPEC_FAILED", env.get("status"))
    log.check("snapshot_path non-null", bool(sp), sp)
    chk = await m.call("debug_exec", {"doc": doc, "code": f"import os\nresult = (os.path.exists({sp!r}), os.path.abspath({sp!r}), sorted(os.listdir(os.path.dirname({sp!r}))))"}) if sp else {}
    log.check("snapshot file still on disk (in-process os.path.exists; shell is ACL-denied)", "(True," in str(sc(chk).get("value_repr")), sc(chk).get("value_repr"))
    full = os.path.join(os.path.expanduser("~"), sp) if sp else None
    log.note(f"shell view: dir exists={os.path.isdir(os.path.dirname(full)) if full else None}")
    log.check("fingerprint_after null", mb.get("fingerprint_after", "MISSING") is None, mb.get("fingerprint_after", "MISSING"))
    tr = await m.call("query_tree_summary", {"doc": doc, "depth": 3})
    pm = await m.call("query_mass_properties", {"doc": doc, "object": "Pad"})
    log.check("mutation really committed: Pad in tree, volume 12000.0", tree_has(tr, "Pad") and near(vol(pm), 12000.0, 1e-6), vol(pm))
    t = env.get("text") or ""
    log.check("text is 'Mutation failed and its rollback could not be proven: {snapshot_path}.' never 'Mutation rolled back'",
              t == f"Mutation failed and its rollback could not be proven: {sp}." and "Mutation rolled back" not in t, t)
    log.note(f"explanation={pv(env).get('explanation')!r}")
    fit, rec = await capture(m, doc, "tc-05-11-after.png")
    log.note(f"after fit={fit}")


go("tc-05-11", body)
