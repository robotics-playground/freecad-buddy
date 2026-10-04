from tc03lib import *  # noqa: F401,F403


async def body(m, log):
    doc = await new_doc(m, "BracketPlate")
    await plate(m, doc)  # PlateProfile (consumed) + PlatePad, the non-sketch object the third When names
    i0 = await m.call("query_sketch_info", {"doc": doc, "sketch": "PlateProfile"})
    log.check("Given PlateProfile reports 4 entries", len(sc(i0).get("geometry") or []) == 4, f"{len(sc(i0).get('geometry') or [])}")
    snaps0 = snap_temp()
    log.check("Given %TEMP% holds no FCB_TMP_snap_*", snaps0 == [], f"{len(snaps0)} pre-existing dirs dated 2026-09-22 (not this run)")
    t0 = await m.call("query_tree_summary", {"doc": doc, "depth": 2})
    fit0 = await m.fit(doc)
    log.note(f"before fit: {fit0}")
    log.write({"shot": shot("tc-03-17-before.png")})

    a = await m.call("sketch_add_geometry", {"doc": doc, "sketch": "NoSuchSketch", "geometry": [{"kind": "point", "start": [0, 0]}]})
    b = await m.call("sketch_remove_geometry", {"doc": doc, "sketch": "PlateProfile", "geo_ids": [99]})
    c = await m.call("sketch_add_constraint", {"doc": doc, "sketch": "PlatePad", "constraints": [{"type": "Horizontal", "first": 0}]})

    log.check("unknown sketch INVALID_INPUT naming 'unknown object: NoSuchSketch'",
              a.get("status") == "INVALID_INPUT" and "unknown object: NoSuchSketch" in json.dumps(a.get("detail")), short(a))
    log.check("geo_id 99 INVALID_INPUT naming 'is outside the sketch (0..3)'",
              b.get("status") == "INVALID_INPUT" and "is outside the sketch (0..3)" in json.dumps(b.get("detail")), short(b))
    log.check("non-sketch INVALID_INPUT naming 'object is not a sketch: PlatePad'",
              c.get("status") == "INVALID_INPUT" and "object is not a sketch: PlatePad" in json.dumps(c.get("detail")), short(c))
    log.check("none carries mutation.snapshot_path", not any(mut(x).get("snapshot_path") for x in (a, b, c)), "")
    log.check("no new FCB_TMP_snap_* written", snap_temp() == snaps0, f"{len(snap_temp())}")
    t1 = await m.call("query_tree_summary", {"doc": doc, "depth": 2})
    log.check("tree unchanged", json.dumps(sc(t1).get("tree")) == json.dumps(sc(t0).get("tree")), "")
    log.check("each status exactly INVALID_INPUT", [x.get("status") for x in (a, b, c)] == ["INVALID_INPUT"] * 3, f"{[x.get('status') for x in (a, b, c)]}")
    fit = await m.fit(doc)
    log.note(f"after fit: {fit}")
    log.write({"shot": shot("tc-03-17-after.png")})
    log.write({"edit_after": edit_capture("PlateProfile", "tc-03-17-edit-after.png", parent=["PlateBody", "PlatePad"])})


go("tc-03-17", body)
