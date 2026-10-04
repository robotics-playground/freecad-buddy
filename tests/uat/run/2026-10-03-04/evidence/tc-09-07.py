from tc09lib import *  # noqa


async def body(m, log):
    doc, obj = await scene(m, log, "tc-09-07", "box40-hole-r5")
    t0 = await m.call("query_tree_summary", {"doc": doc})
    log.check("Given query_tree_summary OK", t0.get("status") == "OK", sc(t0).get("returned_nodes"))
    mark = addon_mark()
    d0 = await m.call("query_tree_summary", {"doc": doc, "depth": 0})
    dm = await m.call("query_tree_summary", {"doc": doc, "depth": -1})
    dbig = await m.call("query_tree_summary", {"doc": doc, "depth": 2147483647})
    d1 = await m.call("query_tree_summary", {"doc": doc, "depth": 1})
    e0 = await m.call("query_dependencies", {"doc": doc, "max_edges": 0})
    em = await m.call("query_dependencies", {"doc": doc, "max_edges": -1})
    e1 = await m.call("query_dependencies", {"doc": doc, "max_edges": 1})
    pat = {"doc": doc, "body": "Body", "name": "Pattern", "kind": "linear", "direction": {"kind": "geometric", "object": obj},
           "length": {"value": 60, "unit": "mm"}, "confirm": {"preview_id": "fcb-preview:placeholder"}}
    p0 = await m.call("feature_pattern", dict(pat, occurrences=0))
    p1 = await m.call("feature_pattern", dict(pat, occurrences=1))
    log.check("depth 0 -> protocol rejection", is_reject(d0), raw(d0) or short(d0))
    log.check("depth -1 -> protocol rejection", is_reject(dm), raw(dm) or short(dm))
    big = sc(dbig)
    actual = count_nodes(big.get("tree"))
    log.check("depth 2147483647 OK, returned_nodes == actual node count, no hang", dbig.get("status") == "OK" and big.get("returned_nodes") == actual,
              {"returned_nodes": big.get("returned_nodes"), "counted": actual})
    s1 = sc(d1)
    log.check("depth 1 OK, returned_nodes == len(tree)", d1.get("status") == "OK" and s1.get("returned_nodes") == len(s1.get("tree") or []),
              {"returned_nodes": s1.get("returned_nodes"), "len_tree": len(s1.get("tree") or [])})
    log.check("max_edges 0 and -1 -> protocol rejection", is_reject(e0) and is_reject(em), [raw(e0), raw(em)])
    edges = sc(e1).get("edges")
    log.check("max_edges 1 OK with at most one edge", e1.get("status") == "OK" and edges is not None and len(edges) <= 1,
              {"status": e1.get("status"), "edges": edges, "keys": list(sc(e1).keys())})
    log.check("occurrences 0 and 1 -> protocol rejection", is_reject(p0) and is_reject(p1), [raw(p0), raw(p1)])
    since = addon_since(mark)
    (EVIDENCE / "tc-09-07-addonlog.txt").write_text(since, encoding="utf-8")
    log.check("addon log: no ValidationError traceback for rejected boundary calls",
              "ValidationError" not in since and "Traceback" not in since, f"{len(since)} bytes; lines: {since.count(chr(10))}")
    await frame_shot(m, doc, "tc-09-07-after.png")


go("tc-09-07", body)
