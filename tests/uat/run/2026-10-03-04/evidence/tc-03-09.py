from tc03lib import *  # noqa: F401,F403


async def body(m, log):
    doc = await new_doc(m, "BracketPlate")
    await m.call("sketch_create", {"doc": doc, "name": "LooseProfile", "plane": "XY"})
    v0 = await m.call("verify_sketch", {"doc": doc, "sketch": "LooseProfile"})
    s0 = sc(v0).get("subject") or {}
    log.check("Given LooseProfile dof=0 geometry_count=0", s0.get("dof") == 0 and s0.get("geometry_count") == 0, f"dof={s0.get('dof')} gc={s0.get('geometry_count')}")
    tree0 = await m.call("query_tree_summary", {"doc": doc})
    snaps0 = snap_temp()
    log.note(f"tree before: {[n.get('name') for n in sc(tree0).get('tree') or []]}; FCB_TMP_snap_* before: {snaps0}")
    fit0 = await m.fit(doc)
    log.note(f"before fit: {fit0}")
    log.write({"shot": shot("tc-03-09-before.png")})

    e = await m.call("sketch_add_geometry", {"doc": doc, "sketch": "LooseProfile",
                                             "geometry": [{"kind": "line_segment", "start": [0, 0], "end": [60, 0]}]})
    mu = mut(e)
    p = pv(e)
    log.check("status=SPEC_FAILED", e.get("status") == "SPEC_FAILED", short(e))
    log.check("rolled_back=true post_verify.passed=false", mu.get("rolled_back") is True and p.get("passed") is False,
              f"rolled_back={mu.get('rolled_back')} passed={p.get('passed')} rollback_proven={mu.get('rollback_proven')}")
    expl = p.get("explanation") or ""
    import re
    mdof = re.match(r"verify_sketch failed on LooseProfile \(dof=(\d+)", expl)
    log.check("explanation starts 'verify_sketch failed on LooseProfile (dof=' non-zero", bool(mdof) and int(mdof.group(1)) > 0, expl)
    info = await m.call("query_sketch_info", {"doc": doc, "sketch": "LooseProfile"})
    log.check("geometry=[] after rollback", sc(info).get("geometry") == [], f"geometry={sc(info).get('geometry')}")
    fb = (mu.get("fingerprint_before") or {}).get("digest")
    fa = (mu.get("fingerprint_after") or {}).get("digest")
    log.check("fingerprint_before.digest == fingerprint_after.digest or rolled_back_via_snapshot",
              (fb and fb == fa) or mu.get("rollback_proven") == "rolled_back_via_snapshot", f"before={fb} after={fa} proven={mu.get('rollback_proven')}")
    snaps1 = snap_temp()
    log.check("no FCB_TMP_snap_* left in %TEMP%", snaps1 == [] or snaps1 == snaps0, f"after={snaps1} snapshot_path={mu.get('snapshot_path')}")
    v1 = await m.call("verify_sketch", {"doc": doc, "sketch": "LooseProfile"})
    log.check("verify_sketch OK dof=0", v1.get("status") == "OK" and (sc(v1).get("subject") or {}).get("dof") == 0, short(v1))
    fit = await m.fit(doc)
    log.note(f"after fit: {fit}")
    log.write({"shot": shot("tc-03-09-after.png")})
    log.write({"edit": edit_capture("LooseProfile", "tc-03-09-edit-after.png")})


go("tc-03-09", body)
