import glob
from tc05lib import *


def scan():
    hits, n = [], 0
    for path in sorted(glob.glob(str(EVIDENCE / "tc-05-*-mcp.jsonl"))):
        for line in open(path, encoding="utf-8"):
            text = line
            if '"tnp_' not in text:
                continue
            rec = json.loads(line)
            def walk(o):
                nonlocal n
                if isinstance(o, dict):
                    if "status" in o and "element_map_version" in o and "findings" in o:
                        n += 1
                        if o["status"] == "CLEAN" and o.get("element_map_version") is None:
                            hits.append(path)
                    for v in o.values():
                        walk(v)
                elif isinstance(o, list):
                    for v in o:
                        walk(v)
            walk(rec.get("envelope"))
    return n, hits


async def body(m, log):
    await close_all(m, log)
    cap = sc(await m.call("query_capabilities", {}))
    log.check("CONDITIONAL build with no element map", None, f"NOT RUN: this build reports element_map_available={cap.get('element_map_available')}")
    doc = await body_sketch(m, "TC0518", pad=30)
    fit, rec = await capture(m, doc, "tc-05-18-before.png")
    log.note(f"before fit={fit}")
    pr = await m.call("preview_dry_run", {"doc": doc, "operation": {"tool": "feature_fillet", "args": {"body": "Body", "base": "NoSuchFeature", "name": "Fillet", "edges": [sel("NoSuchFeature", "Edge1")], "radius": q(2)}}})
    d = sc(pr).get("diff") or {}
    tp = d.get("tnp_precheck")
    log.note(f"preview -> {short(pr, 400)} diff present={bool(d)}")
    log.check("preview diff.tnp_precheck.status == UNSUPPORTED", (tp or {}).get("status") == "UNSUPPORTED", tp)
    log.check("UNSUPPORTED carries findings == []", tp is not None and tp.get("findings") == [], tp)
    log.check("element_map_version present on the precheck", tp is not None and "element_map_version" in tp, tp)
    n, hits = scan()
    log.check(f"across TC-05 envelopes no tnp block is CLEAN with element_map_version null ({n} blocks scanned)", not hits, hits)
    tr = await m.call("query_tree_summary", {"doc": doc, "depth": 3})
    log.note(f"Fillet in tree after refused preview: {tree_has(tr, 'Fillet')}")
    fit, rec = await capture(m, doc, "tc-05-18-after.png")
    log.note(f"after fit={fit}")


go("tc-05-18", body)
