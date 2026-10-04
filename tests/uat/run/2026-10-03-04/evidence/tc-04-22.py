from tc04lib import *  # noqa: F401,F403


def names(tr):
    out = []

    def walk(nodes):
        for n in nodes or []:
            out.append(n.get("name"))
            walk(n.get("children"))
    walk(sc(tr).get("tree"))
    return sorted(out)


async def body(m, log):
    h = sc(await m.call("document_create", {"label": "Orphans"})).get("doc")
    await body_pad(m, h, "PlateBody", "PlateProfile", "PlatePad", rect_profile(0, 0, 60, 40), 5)
    t0 = names(await m.call("query_tree_summary", {"doc": h, "depth": 3}))
    log.check("Given exactly PlateBody, PlateProfile, PlatePad", set(t0) == {"PlateBody", "PlateProfile", "PlatePad"}, t0)
    base = snaps()
    await capture(m, h, "tc-04-22-before.png")
    s1 = await m.call("feature_pad", {"doc": h, "body": "NoSuchBody", "profile": "PlateProfile", "name": "OrphanPad", "length": q(5)})
    s2 = await m.call("feature_pad", {"doc": h, "body": "PlateBody", "profile": "NoSuchSketch", "name": "OrphanPad", "length": q(5)})
    s3 = await m.call("feature_fillet", {"doc": h, "body": "PlateBody", "base": "NoSuchPad", "name": "OrphanFillet", "edges": [sel("NoSuchPad", "Edge1")]})
    s4 = await m.call("feature_pad", {"doc": h, "body": "PlateProfile", "profile": "PlateProfile", "name": "WrongTypePad", "length": q(5)})
    log.check("unknown Body 'unknown object in body: NoSuchBody'", s1.get("status") == "INVALID_INPUT" and "unknown object in body: NoSuchBody" in detail_msg(s1), short(s1))
    log.check("unknown profile 'unknown object in profile: NoSuchSketch'", s2.get("status") == "INVALID_INPUT" and "unknown object in profile: NoSuchSketch" in detail_msg(s2), short(s2))
    log.check("unknown base 'unknown object in base: NoSuchPad'", s3.get("status") == "INVALID_INPUT" and "unknown object in base: NoSuchPad" in detail_msg(s3), short(s3))
    log.check("wrong type 'object is not a PartDesign Body: PlateProfile'", s4.get("status") == "INVALID_INPUT" and "object is not a PartDesign Body: PlateProfile" in detail_msg(s4), short(s4))
    t1 = names(await m.call("query_tree_summary", {"doc": h, "depth": 3}))
    log.check("nothing created", t1 == t0, t1)
    log.check("no envelope carries snapshot_path", not any(mut(e).get("snapshot_path") for e in (s1, s2, s3, s4)), "")
    log.check("no snapshot written", set(snaps()) == set(base), f"new={sorted(set(snaps()) - set(base))}")
    await sketch(m, h, "SecondProfile", "PlateBody", rect_profile(10, 10, 10, 10), face=sel("PlatePad", "Face6"))
    s5 = await m.call("feature_pad", {"doc": h, "body": "PlateBody", "profile": "SecondProfile", "name": "PlatePad", "length": q(5)})
    log.check("taken name 'an object named PlatePad already exists'", s5.get("status") == "INVALID_INPUT" and "an object named PlatePad already exists" in detail_msg(s5), short(s5))
    log.note("SecondProfile (a 10 x 10 sketch on the top face) is the fixture for the taken-name check; it is a sketch, not a solid")
    await capture(m, h, "tc-04-22-after.png")
    log.write({"doc": h})


go("tc-04-22", body)
