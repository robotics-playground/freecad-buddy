from tc04lib import *  # noqa: F401,F403


def origin_name(tree, body, base):
    for node in sc(tree).get("tree") or []:
        if node.get("name") == body:
            for child in node.get("children") or []:
                for leaf in child.get("children") or []:
                    if leaf.get("name", "").startswith(base):
                        return leaf["name"]
    return None


def bb(mp):
    b = sc(mp).get("bbox") or {}
    return {k: (v or {}).get("value") for k, v in b.items()}


async def body(m, log):
    h = sc(await m.call("document_create", {"label": "Mirrors"})).get("doc")
    log.note("bodies placed apart in Y (HalfBody y 0..30, DatumBody y 45..75, FaceBody y 120..150) so the three mirrored results do not overlap")
    await body_pad(m, h, "HalfBody", "HalfProfile", "HalfPad", rect_profile(5, 0, 20, 30), 10)
    await body_pad(m, h, "DatumBody", "DatumProfile", "DatumPad", rect_profile(5, 45, 20, 30), 10)
    await body_pad(m, h, "FaceBody", "FaceProfile", "FacePad", rect_profile(5, 120, 20, 30), 10)
    tree = await m.call("query_tree_summary", {"doc": h, "depth": 3, "filters": {"exclude_types": []}})
    yz_half, yz_datum = origin_name(tree, "HalfBody", "YZ_Plane"), origin_name(tree, "DatumBody", "YZ_Plane")
    log.note(f"origin plane names: HalfBody {yz_half}, DatumBody {yz_datum}")
    dm = await m.call("feature_datum", {"doc": h, "body": "DatumBody", "name": "MirrorPlane", "kind": "plane",
                                        "attachment": sel(yz_datum), "offset": q(30)})
    log.note(f"MirrorPlane datum (DatumBody YZ plane, offset 30 mm -> x=30): {short(dm, 300)}")
    mh = await m.call("query_mass_properties", {"doc": h, "object": "HalfPad"})
    log.check("Given HalfPad vol 6000 and x 5..25", near(vol(mh), 6000) and near(bb(mh).get("xmin"), 5) and near(bb(mh).get("xmax"), 25), bb(mh))
    pl = await m.call("query_placement", {"doc": h, "object": "MirrorPlane"})
    log.check("Given MirrorPlane query_placement OK", pl.get("status") == "OK", json.dumps(sc(pl))[:300])
    m1 = await m.call("feature_mirror", {"doc": h, "body": "HalfBody", "name": "PlaneMirror", "mirror_plane": sel(yz_half), "originals": ["HalfPad"]})
    m2 = await m.call("feature_mirror", {"doc": h, "body": "DatumBody", "name": "DatumMirror", "mirror_plane": sel("MirrorPlane"), "originals": ["DatumPad"]})
    m3 = await m.call("feature_mirror", {"doc": h, "body": "FaceBody", "name": "FaceMirror", "mirror_plane": sel("FacePad", "Face1"), "originals": ["FacePad"]})
    log.check("all three mirrors OK rolled_back=false", all(ok_commit(e) for e in (m1, m2, m3)), [short(e, 300) for e in (m1, m2, m3)])
    q1 = await m.call("query_mass_properties", {"doc": h, "object": "PlaneMirror"})
    log.check("PlaneMirror vol 12000", near(vol(q1), 12000), vol(q1))
    b1 = ss(m1).get("bbox")
    log.check("PlaneMirror bbox [50,30,10]", isinstance(b1, list) and all(near(a, b) for a, b in zip(b1, [50, 30, 10])), b1)
    log.check("whole-object selectors (no mapped_name) accepted for steps 1 and 2", ok_commit(m1) and ok_commit(m2), "")
    log.check("face selector with mapped_name Face1 accepted", ok_commit(m3), "")
    vs = [await m.call("verify_shape", {"doc": h, "object": o}) for o in ("PlaneMirror", "DatumMirror", "FaceMirror")]
    sols = [ss(e).get("solid_count") for e in (m1, m2, m3)]
    log.check("verify_shape OK and solid_count=1 for all three", all(v.get("status") == "OK" for v in vs) and sols == [1, 1, 1],
              f"{[v.get('status') for v in vs]} solids={sols}")
    for name in ("DatumMirror", "FaceMirror"):
        mm = await m.call("query_mass_properties", {"doc": h, "object": name})
        log.note(f"{name}: vol={vol(mm)} bbox={bb(mm)}")
    before = set(snap_temp())
    bad = await m.call("feature_mirror", {"doc": h, "body": "HalfBody", "name": "GhostMirror", "mirror_plane": sel("NoSuchPlane"), "originals": ["HalfPad"]})
    log.check("unknown mirror plane INVALID_INPUT 'unknown object in mirror_plane', no snapshot",
              bad.get("status") == "INVALID_INPUT" and "unknown object in mirror_plane" in detail_msg(bad) and not mut(bad).get("snapshot_path")
              and set(snap_temp()) == before, short(bad))
    await capture(m, h, "tc-04-12-after.png")
    log.write({"doc": h})


go("tc-04-12", body)
