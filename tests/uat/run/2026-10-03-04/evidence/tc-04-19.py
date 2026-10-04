from tc04lib import *  # noqa: F401,F403


async def body(m, log):
    h = sc(await m.call("document_create", {"label": "PadLengths"})).get("doc")
    await m.call("feature_body_create", {"doc": h, "name": "BlockBody"})
    await sketch(m, h, "BlockProfile", "BlockBody", rect_profile(0, 0, 20, 30))
    v = await m.call("verify_sketch", {"doc": h, "sketch": "BlockProfile"})
    log.check("Given BlockProfile dof=0", (sc(v).get("subject") or {}).get("dof") == 0, short(v))
    base = snaps()
    await capture(m, h, "tc-04-19-before.png")
    a = {"doc": h, "body": "BlockBody", "profile": "BlockProfile"}
    s1 = await m.call("feature_pad", {**a, "name": "ZeroPad", "length": q(0)})
    s2 = await m.call("feature_pad", {**a, "name": "NegPad", "length": q(-10)})
    s3 = await m.call("feature_pad", {**a, "name": "NoLenPad"})
    log.check("zero refused 'length must be positive, got 0'", s1.get("status") == "INVALID_INPUT" and "length must be positive, got 0" in detail_msg(s1), short(s1))
    log.check("negative refused 'length must be positive, got -10'", s2.get("status") == "INVALID_INPUT" and "length must be positive, got -10" in detail_msg(s2), short(s2))
    log.check("missing length refused \"up_to='Length' is length-driven; 'length' is required\"",
              s3.get("status") == "INVALID_INPUT" and "up_to='Length' is length-driven; 'length' is required" in detail_msg(s3), short(s3))
    log.check("no envelope carries snapshot_path", not any(mut(e).get("snapshot_path") for e in (s1, s2, s3)), "")
    log.check("no snapshot written", set(snaps()) == set(base), f"new={sorted(set(snaps()) - set(base))}")
    tr = await m.call("query_tree_summary", {"doc": h, "depth": 3})
    log.check("no ZeroPad/NegPad/NoLenPad in tree", not any(n in tree_names(tr) for n in ("ZeroPad", "NegPad", "NoLenPad")), "")
    try:
        s4 = await m.call("feature_pad", {**a, "name": "InfPad", "length": {"value": float("inf"), "unit": "mm"}})
        log.check("non-finite length refused 'must be finite'", s4.get("status") == "INVALID_INPUT" and "must be finite" in detail_msg(s4), short(s4, 400))
    except Exception as exc:  # client could not encode it
        log.check("non-finite length refused 'must be finite'", None, f"NOT RUN: client raised {type(exc).__name__}: {exc}")
    qo = await m.call("query_object", {"doc": h, "object": "BlockBody"})
    log.check("BlockBody Tip is null", (sc(qo).get("properties") or {}).get("Tip") is None, (sc(qo).get("properties") or {}).get("Tip"))
    await capture(m, h, "tc-04-19-after.png")
    log.write({"doc": h})


go("tc-04-19", body)
