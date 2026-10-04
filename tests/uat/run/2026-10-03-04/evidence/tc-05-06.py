from tc05lib import *


async def attempt(m, log, doc, tool, args, tag):
    preview, env = await apply(m, doc, tool, args)
    mb = mut(env)
    fpb = (sc(preview).get("diff") or {}).get("fingerprint_before")
    rec = {"tag": tag, "preview_status": preview.get("status"), "preview_detail": (preview.get("detail") or {}).get("message") if isinstance(preview.get("detail"), dict) else preview.get("_raw"),
           "status": env.get("status"), "rolled_back": mb.get("rolled_back"), "rollback_proven": mb.get("rollback_proven"),
           "snapshot_path": mb.get("snapshot_path"), "after_eq_preview_before": digest(env, "fingerprint_after") == fpb if fpb else None,
           "explanation": pv(env).get("explanation"), "detail": short(env, 300)}
    log.write({"reproducer": rec})
    log.note(f"{tag}: {json.dumps(rec)[:700]}")
    return env


async def body(m, log):
    docs = sc(await m.call("document_list", {})).get("documents") or []
    d0 = [d for d in docs if d["label"] == "TC0506"][0]
    doc, label0 = d0["doc"], d0["label"]
    fit, rec = await capture(m, doc, "tc-05-06-before.png")
    log.note(f"before fit={fit}")
    base = set(run_snaps())
    envs = []
    envs.append(await attempt(m, log, doc, "feature_pocket", {"body": "Body", "profile": "Sketch001", "name": "Pocket", "length": q(900)}, "pocket-900"))
    envs.append(await attempt(m, log, doc, "feature_pattern", {"body": "Body", "base": "Fillet", "name": "Pattern", "kind": "linear", "occurrences": 200, "direction": "X"}, "pattern-literal-200"))
    envs.append(await attempt(m, log, doc, "feature_pattern", {"body": "Body", "name": "Pattern", "kind": "linear", "originals": ["Fillet"], "direction": sel("Sketch", "H_Axis"), "length": q(400), "occurrences": 20}, "pattern-capped-20"))
    envs.append(await attempt(m, log, doc, "feature_set_parameters", {"feature": "Fillet", "parameters": {"Radius": q(400)}}, "set-radius-400"))
    proofs = [mut(e).get("rollback_proven") for e in envs]
    via = [e for e in envs if mut(e).get("rollback_proven") == "rolled_back_via_snapshot"]
    log.check("any reproducer hit rolled_back_via_snapshot", bool(via) if via else None, proofs)
    bad = [e for e in envs if mut(e).get("rolled_back") is True and mut(e).get("rollback_proven") is None]
    log.check("no run produced rolled_back true with rollback_proven null", not bad, [short(e) for e in bad])
    unproven = [e for e in envs if mut(e) and mut(e).get("rolled_back") is False and e.get("status") != "OK"]
    log.note(f"unproven-rollback envelopes: {[(e.get('text') or '')[:200] for e in unproven]}")
    tr = await m.call("query_tree_summary", {"doc": doc, "depth": 3})
    log.check("handle still usable: query_tree_summary OK", tr.get("status") == "OK", short(tr))
    log.note(f"tree after reproducers: {tree_names(tr)[:900]}")
    dl = sc(await m.call("document_list", {})).get("documents") or []
    log.check("document_list shows same label", any(d["label"] == label0 for d in dl), [(d["label"], d["doc"]) for d in dl])
    log.note(f"new snapshot dirs after reproducers: {sorted(set(run_snaps()) - base)}")
    fm = await m.call("query_mass_properties", {"doc": doc, "object": "Fillet"})
    log.note(f"Fillet volume after: {vol(fm)} status={fm.get('status')}")
    fit, rec = await capture(m, doc, "tc-05-06-after.png")
    log.note(f"after fit={fit}")


go("tc-05-06", body)
