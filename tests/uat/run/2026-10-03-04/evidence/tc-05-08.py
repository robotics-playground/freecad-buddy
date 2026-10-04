from tc05lib import *

PATCH = ("from freecad_buddy.usecases import shim as _s\n"
         "_o = _s.enable_undo\n"
         "def _eu(d):\n"
         "    _s.enable_undo = _o\n"
         "    return bool(getattr(d, 'UndoMode', 0))\n"
         "_s.enable_undo = _eu\n"
         "doc.UndoMode = 0\n"
         "result = doc.UndoMode")
FILLET = {"body": "Body", "base": "Pad", "name": "Fillet", "edges": [sel("Pad", "Edge1")], "radius": q(500)}


async def body(m, log):
    await close_all(m, log)
    doc = await body_sketch(m, "TC0508", pad=30)
    probe = await m.call("debug_exec", {"doc": doc, "code": "1"})
    log.check("debug_exec enabled (exec host)", probe.get("status") == "OK", short(probe))
    preview = await m.call("preview_dry_run", {"doc": doc, "operation": {"tool": "feature_fillet", "args": FILLET}})
    fpb = (sc(preview).get("diff") or {}).get("fingerprint_before")
    token = sc(preview).get("preview_id")
    log.note("No GUI document has UndoMode 0 and shim.enable_undo turns undo on (shim.py:366-378), so the precondition is forced: "
             "debug_exec sets doc.UndoMode=0 and makes the NEXT shim.enable_undo call report the mode without writing it (one-shot). Patch applied AFTER the preview so the preview's copy does not consume it.")
    pe = await m.call("debug_exec", {"doc": doc, "code": PATCH})
    log.note(f"patch -> {short(pe)} value_repr={sc(pe).get('value_repr')}")
    u = await m.call("document_undo", {"doc": doc})
    msg = (u.get("detail") or {}).get("message") if isinstance(u.get("detail"), dict) else u.get("_raw")
    log.check("Given document_undo refused 'undo is unavailable on <Name>: the document reports UndoMode 0'",
              u.get("status") != "OK" and "undo is unavailable on TC0508: the document reports UndoMode 0" in str(msg), msg)
    fit, rec = await capture(m, doc, "tc-05-08-before.png")
    log.note(f"before fit={fit}")
    log.note("attempt 1 showed document_undo itself calls shim.enable_undo (documents.py:427) and consumed the one-shot patch; re-arm it right before the apply")
    pe2 = await m.call("debug_exec", {"doc": doc, "code": PATCH})
    log.note(f"re-armed patch -> {short(pe2)} UndoMode={sc(pe2).get('value_repr')}")
    env = await m.call("feature_fillet", dict(FILLET, doc=doc, confirm={"preview_id": token, "elicitation_action": "accept"}))
    mb = mut(env)
    ex = pv(env).get("explanation") or ""
    log.note(f"envelope status={env.get('status')} text={env.get('text')!r}")
    log.check("explanation ends '; undo unavailable on this document'", ex.endswith("; undo unavailable on this document"), ex)
    log.check("rollback_proven 'rolled_back_via_snapshot'", mb.get("rollback_proven") == "rolled_back_via_snapshot", mb.get("rollback_proven"))
    log.check("rolled_back true and fingerprint_after == preview fingerprint_before",
              mb.get("rolled_back") is True and digest(env, "fingerprint_after") == fpb, {"rolled_back": mb.get("rolled_back"), "after": digest(env, "fingerprint_after"), "preview_before": fpb})
    docs = sc(await m.call("document_list", {})).get("documents") or []
    log.note(f"document_list after: {[(d['label'], d['doc']) for d in docs]}")
    pm = await m.call("query_mass_properties", {"doc": doc, "object": "Pad"})
    log.check("Pad volume = pre-mutation 12000.0", near(vol(pm), 12000.0, 1e-6), {"status": pm.get("status"), "vol": vol(pm)})
    tr = await m.call("query_tree_summary", {"doc": doc, "depth": 3})
    log.note(f"Fillet in tree after: {tree_has(tr, 'Fillet')}")
    fit, rec = await capture(m, doc, "tc-05-08-after.png")
    log.note(f"after fit={fit}")
    # control: same failing mutation on a GUI-created document with undo
    d2 = await body_sketch(m, "TC0508ctl", pad=30)
    p2, e2 = await apply(m, d2, "feature_fillet", FILLET)
    ex2 = pv(e2).get("explanation") or ""
    log.check("control doc WITH undo: explanation does NOT contain 'undo unavailable'", "undo unavailable" not in ex2 and bool(ex2), ex2)
    log.note(f"control: status={e2.get('status')} proof={mut(e2).get('rollback_proven')}")
    c = await m.call("document_close", {"doc": d2})
    log.note(f"control doc closed -> {c.get('status')}")


go("tc-05-08", body)
