from tc04lib import *  # noqa: F401,F403


async def body(m, log):
    h = sc(await m.call("document_create", {"label": "Shaft"})).get("doc")
    await m.call("feature_body_create", {"doc": h, "name": "ShaftBody"})
    await sketch(m, h, "ShaftProfile", "ShaftBody", rect_profile(0, 0, 5, 20), plane="XZ")
    v = await m.call("verify_sketch", {"doc": h, "sketch": "ShaftProfile"})
    log.check("Given ShaftProfile dof=0", (sc(v).get("subject") or {}).get("dof") == 0, short(v))
    rv = await m.call("feature_revolve", {"doc": h, "body": "ShaftBody", "profile": "ShaftProfile", "name": "ShaftRev",
                                          "axis": sel("ShaftProfile", "V_Axis"), "angle": q(360, "deg")})
    mp = await m.call("query_mass_properties", {"doc": h, "object": "ShaftRev"})
    log.check("revolve OK rolled_back=false", ok_commit(rv), short(rv))
    log.check("volume 1570.7963 within 0.1%", near(vol(mp), 1570.7963), vol(mp))
    s = ss(rv)
    log.check("shape_summary solid_count=1 face_count=3 is_valid=true",
              s.get("solid_count") == 1 and s.get("face_count") == 3 and s.get("is_valid") is True, json.dumps(s))
    qo = await m.call("query_object", {"doc": h, "object": "ShaftRev"})
    ra = (sc(qo).get("properties") or {}).get("ReferenceAxis")
    log.check("ReferenceAxis names ShaftProfile and V_Axis", "ShaftProfile" in json.dumps(ra) and "V_Axis" in json.dumps(ra), json.dumps(ra))
    vs = await m.call("verify_shape", {"doc": h, "object": "ShaftRev"})
    log.check("verify_shape OK", vs.get("status") == "OK", short(vs))
    before = set(snap_temp())
    e1 = await m.call("feature_revolve", {"doc": h, "body": "ShaftBody", "profile": "ShaftProfile", "name": "EdgeRev",
                                          "axis": sel("ShaftProfile", "Edge1"), "angle": q(360, "deg")})
    log.check("axis Edge1 on profile INVALID_INPUT naming the allowed axes",
              e1.get("status") == "INVALID_INPUT" and "axis on the profile sketch must be one of ['H_Axis', 'N_Axis', 'V_Axis']" in detail_msg(e1), short(e1))
    e2 = await m.call("feature_revolve", {"doc": h, "body": "ShaftBody", "profile": "ShaftProfile", "name": "OverRev",
                                          "axis": sel("ShaftProfile", "V_Axis"), "angle": q(400, "deg")})
    log.check("angle 400 INVALID_INPUT, no snapshot_path", e2.get("status") == "INVALID_INPUT" and not mut(e2).get("snapshot_path"), short(e2))
    e3 = await m.call("feature_revolve", {"doc": h, "body": "ShaftBody", "profile": "ShaftProfile", "name": "SecondRev",
                                          "axis": sel("ShaftProfile", "V_Axis"), "angle": q(180, "deg"), "second_angle": q(90, "deg")})
    log.check("second_angle without TwoAngles INVALID_INPUT", e3.get("status") == "INVALID_INPUT"
              and "second_angle is only read when up_to='TwoAngles'" in detail_msg(e3), short(e3))
    log.note(f"new temp snapshots during the three refusals: {sorted(set(snap_temp()) - before)}")
    await capture(m, h, "tc-04-06-after.png")
    log.write({"doc": h})


go("tc-04-06", body)
