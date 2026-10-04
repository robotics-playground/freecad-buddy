from tc05lib import *

FIL = {"body": "Body", "base": "Pad", "name": "Fillet", "edges": [sel("Pad", "Edge1")], "radius": q(2)}
PATCH = ("from freecad_buddy.usecases import transaction as _t\n_orig = _t.fingerprint\n"
         "def _fp(d):\n    _t.fingerprint = _orig\n    raise RuntimeError('injected setup failure')\n_t.fingerprint = _fp")


async def body(m, log):
    docs = sc(await m.call("document_list", {})).get("documents") or []
    for d in docs:
        if d["label"] == "TC0511":
            x = await m.call("debug_exec", {"doc": d["doc"], "code": "import shutil, glob, os\nds = glob.glob(os.path.expanduser('~/freecad-buddy-workdir/tmp/FCB_TMP_snap_*'))\nfor p in ds: shutil.rmtree(p)\nresult = ds"})
            log.note(f"TC-05-11 cleanup: rm snapshot dirs in-process -> {sc(x).get('value_repr')}")
    await close_all(m, log)
    doc = await body_sketch(m, "TC0512", pad=30)
    probe = await m.call("debug_exec", {"doc": doc, "code": "1"})
    log.check("Given debug_exec NOT refused", probe.get("status") == "OK", short(probe))
    pm = await m.call("query_mass_properties", {"doc": doc, "object": "Pad"})
    log.check("Given Pad volume 12000.0", near(vol(pm), 12000.0, 1e-6), vol(pm))
    fit, rec = await capture(m, doc, "tc-05-12-before.png")
    log.note(f"before fit={fit}")
    preview = await m.call("preview_dry_run", {"doc": doc, "operation": {"tool": "feature_fillet", "args": FIL}})
    token = sc(preview).get("preview_id")
    p = await m.call("debug_exec", {"doc": doc, "code": PATCH})
    log.note(f"literal TC patch (after preview) -> {short(p)}")
    env = await m.call("feature_fillet", dict(FIL, doc=doc, confirm={"preview_id": token, "elicitation_action": "accept"}))
    mb = mut(env)
    log.note(f"envelope status={env.get('status')} text={env.get('text')!r} explanation={pv(env).get('explanation')!r}")
    log.check("fingerprint_before null", mb.get("fingerprint_before", "MISSING") is None, mb.get("fingerprint_before", "MISSING"))
    log.check("fingerprint_after null", mb.get("fingerprint_after", "MISSING") is None, mb.get("fingerprint_after", "MISSING"))
    log.check("rolled_back false, rollback_proven null", mb.get("rolled_back") is False and mb.get("rollback_proven") is None, {k: mb.get(k) for k in ("rolled_back", "rollback_proven")})
    log.check("touched == []", mb.get("touched") == [], mb.get("touched"))
    log.check("snapshot_path null and no snapshot dir", mb.get("snapshot_path", "MISSING") is None and run_snaps() == [], {"sp": mb.get("snapshot_path", "MISSING"), "dirs": run_snaps()})
    fit, rec = await capture(m, doc, "tc-05-12-after.png")
    log.note(f"after fit (BEFORE document_undo) = {fit}")
    pm2 = await m.call("query_mass_properties", {"doc": doc, "object": "Pad"})
    tr = await m.call("query_tree_summary", {"doc": doc, "depth": 3})
    log.check("document untouched: Pad 12000.0, no Fillet", near(vol(pm2), 12000.0, 1e-6) and not tree_has(tr, "Fillet"), vol(pm2))
    u = await m.call("document_undo", {"doc": doc})
    log.check("document_undo undone == last successful mutation label ('buddy: feature_pad Pad'), not the failed one",
              sc(u).get("undone") == "buddy: feature_pad Pad", {"status": u.get("status"), "undone": sc(u).get("undone")})


go("tc-05-12", body)
