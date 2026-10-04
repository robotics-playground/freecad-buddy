from tc03lib import *  # noqa: F401,F403

GEO = [{"kind": "circle", "center": [0, 0], "radius": {"value": 2.5, "unit": "mm"}},
       {"kind": "circle", "center": [40, 0], "radius": {"value": 2.5, "unit": "mm"}}]
CON = [{"type": "Coincident", "first": 0, "first_pos": 3, "second": -1, "second_pos": 1},
       {"type": "Radius", "first": 0, "value": {"value": 2.5, "unit": "mm"}, "name": "BossRadius"},
       {"type": "PointOnObject", "first": 1, "first_pos": 3, "second": -1},
       {"type": "Distance", "first": 0, "first_pos": 3, "second": 1, "second_pos": 3, "value": {"value": 40, "unit": "mm"}, "name": "HoleSpacing"},
       {"type": "Radius", "first": 1, "value": {"value": 2.5, "unit": "mm"}}]


def datum(info: dict, name: str) -> dict:
    return next((c for c in sc(info).get("constraints") or [] if c.get("name") == name), {})


async def body(m, log):
    doc = await new_doc(m, "BracketPlate")
    await m.call("sketch_create", {"doc": doc, "name": "BossProfile", "plane": "XY"})
    g = await m.call("sketch_add_geometry", {"doc": doc, "sketch": "BossProfile", "geometry": GEO, "constraints": CON})
    log.note(f"Given build: {g.get('status')} {json.dumps(g.get('detail'))[:200]}")
    i0 = await m.call("query_sketch_info", {"doc": doc, "sketch": "BossProfile"})
    br, hs = datum(i0, "BossRadius"), datum(i0, "HoleSpacing")
    log.check("Given BossRadius and HoleSpacing driving=true", br.get("driving") is True and hs.get("driving") is True, json.dumps([br, hs]))
    snaps0 = snap_temp()
    fit0 = await m.fit(doc)
    log.note(f"before fit: {fit0}")
    log.write({"shot": shot("tc-03-15-before.png")})
    log.write({"edit_before": edit_capture("BossProfile", "tc-03-15-edit-before.png")})

    z = await m.call("sketch_set_datum", {"doc": doc, "sketch": "BossProfile", "constraint": "BossRadius", "value": {"value": 0, "unit": "mm"}})
    n = await m.call("sketch_set_datum", {"doc": doc, "sketch": "BossProfile", "constraint": "HoleSpacing", "value": {"value": -5, "unit": "mm"}})
    h = await m.call("sketch_set_datum", {"doc": doc, "sketch": "BossProfile", "constraint": "HoleSpacing", "value": {"value": 1e9, "unit": "mm"}})

    log.check("zero radius non-OK", z.get("status") != "OK", short(z))
    log.check("zero radius pre-transaction (no mutation.snapshot_path)", not mut(z).get("snapshot_path") and not mut(z), f"mutation={json.dumps(mut(z))[:200]}")
    log.check("negative distance INVALID_INPUT or SPEC_FAILED rolled_back", n.get("status") == "INVALID_INPUT" or (n.get("status") == "SPEC_FAILED" and mut(n).get("rolled_back") is True), short(n))
    vh = await m.call("verify_sketch", {"doc": doc, "sketch": "BossProfile"})
    sh = sc(vh).get("subject") or {}
    log.check("1e9: INVALID_INPUT, or OK with dof=0 malformed=[]",
              h.get("status") == "INVALID_INPUT" or (h.get("status") == "OK" and sh.get("dof") == 0 and sh.get("malformed") == []),
              f"{short(h)} verify dof={sh.get('dof')} malformed={sh.get('malformed')}")
    i1 = await m.call("query_sketch_info", {"doc": doc, "sketch": "BossProfile"})
    log.check("BossRadius still {2.5 mm}", datum(i1, "BossRadius").get("value") == {"value": 2.5, "unit": "mm"},
              f"BossRadius={datum(i1, 'BossRadius').get('value')} HoleSpacing={datum(i1, 'HoleSpacing').get('value')}")
    try:
        inf = await m.call("sketch_set_datum", {"doc": doc, "sketch": "BossProfile", "constraint": "HoleSpacing", "value": {"value": float("inf"), "unit": "mm"}})
        log.check("1e999 (infinity) INVALID_INPUT naming 'must be finite'",
                  inf.get("status") == "INVALID_INPUT" and "must be finite" in json.dumps(inf.get("detail")), short(inf))
    except Exception as exc:  # the client may refuse to encode infinity
        log.check("1e999 (infinity) INVALID_INPUT naming 'must be finite'", None, f"client could not send infinity: {type(exc).__name__}: {exc}")
    snaps1 = snap_temp()
    log.check("no FCB_TMP_snap_* orphaned by this run", snaps1 == snaps0, f"before={len(snaps0)} after={len(snaps1)}")
    fit = await m.fit(doc)
    log.note(f"after fit: {fit}")
    log.write({"shot": shot("tc-03-15-after.png")})
    log.write({"edit_after": edit_capture("BossProfile", "tc-03-15-edit-after.png")})


go("tc-03-15", body)
