from tc09lib import *  # noqa


async def body(m, log):
    doc, obj = await scene(m, log, "tc-09-11")
    a = await m.call("query_tree_summary", {"doc": doc, "max_nodes": 0})
    b = await m.call("query_tree_summary", {"doc": doc, "max_nodes": 50})
    props = json.loads((EVIDENCE / "tc-09-05-tool_surface.json").read_text())["query_tree_summary"]["props"]
    log.check("max_nodes 0 -> protocol rejection", is_reject(a), raw(a))
    log.check("max_nodes 50 -> protocol rejection", is_reject(b), raw(b))
    log.check("old behaviour gone: neither OK, no nodes, no truncated", all(e.get("status") != "OK" and "truncated" not in json.dumps(sc(e)) for e in (a, b)), "")
    log.check("property list == ['doc','depth','root','filters']", props == ["doc", "depth", "root", "filters"], props)
    ok = await m.call("query_tree_summary", {"doc": doc})
    log.check("successful call has no 'truncated' key", ok.get("status") == "OK" and "truncated" not in sc(ok), list(sc(ok).keys()))
    d1 = await m.call("query_tree_summary", {"doc": doc, "depth": 1})
    s = sc(d1)
    log.check("depth 1 -> roots only, returned_nodes == len(tree)", d1.get("status") == "OK" and s.get("returned_nodes") == len(s.get("tree") or []),
              (s.get("returned_nodes"), len(s.get("tree") or [])))
    rep = json.loads((EVIDENCE / "tc-09-01-edge_report.json").read_text())
    hit = [c for c in rep["checks"] if c["tool"] == "retired_max_nodes_rejected"]
    log.check("edge report names retired_max_nodes_rejected as passed", len(hit) == 1 and hit[0]["ok"] is True, hit)
    await frame_shot(m, doc, "tc-09-11-after.png")


go("tc-09-11", body)
