from tc04lib import *  # noqa: F401,F403


async def plate_hole(m, label):
    h = sc(await m.call("document_create", {"label": label})).get("doc")
    await body_pad(m, h, "PlateBody", "PlateProfile", "PlatePad", rect_profile(0, 0, 60, 40), 5)
    await sketch(m, h, "HoleProfile", "PlateBody", point_profile(10, 20), face=sel("PlatePad", "Face6"))
    await m.call("feature_hole", {"doc": h, "body": "PlateBody", "profile": "HoleProfile", "name": "ClearanceHole",
                                  "diameter": q(5.5), "depth_type": "ThroughAll"})
    return h


def names(tr):
    out = []

    def walk(nodes):
        for n in nodes or []:
            out.append(n.get("name"))
            walk(n.get("children"))
    walk(sc(tr).get("tree"))
    return sorted(out)


async def body(m, log):
    h = await plate_hole(m, "PatternRefusals")
    vs = await m.call("verify_shape", {"doc": h, "object": "ClearanceHole"})
    log.check("Given ClearanceHole verify_shape OK", vs.get("status") == "OK", short(vs))
    t0 = names(await m.call("query_tree_summary", {"doc": h, "depth": 3}))
    log.note(f"objects before: {t0}")
    await capture(m, h, "tc-04-18-before.png")
    d = sel("PlateProfile", "H_Axis")
    s1 = await m.call("feature_pattern", {"doc": h, "body": "PlateBody", "name": "OnePattern", "kind": "linear", "direction": d, "length": q(40), "occurrences": 1})
    s2a = await m.call("feature_pattern", {"doc": h, "body": "PlateBody", "name": "ZeroPattern", "kind": "linear", "direction": d, "length": q(40), "occurrences": 0})
    s2b = await m.call("feature_pattern", {"doc": h, "body": "PlateBody", "name": "NoDirection", "kind": "linear", "length": q(40), "occurrences": 3})
    s3 = await m.call("feature_pattern", {"doc": h, "body": "PlateBody", "name": "NoAxis", "kind": "polar", "angle": q(360, "deg"), "occurrences": 4})
    log.check("occurrences 1 schema reject (minimum 2)", schema_reject(s1) and "minimum" in (s1.get("_raw") or "").lower() or "less than the minimum" in (s1.get("_raw") or ""), short(s1))
    log.check("occurrences 0 schema reject", schema_reject(s2a), short(s2a))
    log.check("linear without direction refused by the if/then branch", schema_reject(s2b) and "direction" in (s2b.get("_raw") or ""), short(s2b))
    log.check("polar without axis refused by the if/then branch", schema_reject(s3) and "axis" in (s3.get("_raw") or ""), short(s3))
    h2 = await plate_hole(m, "PatternValidLinear")
    ok = await m.call("feature_pattern", {"doc": h2, "body": "PlateBody", "name": "ValidRow", "kind": "linear", "direction": d, "length": q(40), "occurrences": 2})
    log.check("valid linear with direction and no axis OK (run on an equivalent plate)", ok_commit(ok), short(ok, 300))
    await m.call("document_close", {"doc": h2})
    log.check("occurrences 5000 -> INVALID_INPUT 'occurrences must be an integer between 2 and 1000'", None,
              "NOT RUN: run rule caps pattern occurrences at 20 to protect FreeCAD's main thread. Code read: "
              "src/freecad_buddy/usecases/features.py:1324-1331 raises this ValidationError before any document access (_MAX_OCCURRENCES=1000 at :39)")
    t1 = names(await m.call("query_tree_summary", {"doc": h, "depth": 3}))
    log.check("nothing created: same objects, none of OnePattern/ZeroPattern/NoDirection/NoAxis", t1 == t0 and not set(t1) & {"OnePattern", "ZeroPattern", "NoDirection", "NoAxis"}, t1)
    await capture(m, h, "tc-04-18-after.png")
    log.write({"doc": h})


go("tc-04-18", body)
