from tc09lib import *  # noqa

BAD = "fcb-doc:does-not-exist"


async def body(m, log):
    await close_all(m, log)
    dl = await m.call("document_list", {})
    log.check("Given handle not listed", BAD not in json.dumps(sc(dl)), "")
    doc, obj = await scene(m, log, "tc-09-12")
    res = [await m.call("query_tree_summary", {"doc": BAD}), await m.call("verify_recompute", {"doc": BAD}),
           await m.call("query_object", {"doc": BAD, "object": "Box"}), await m.call("document_close", {"doc": BAD})]
    log.check("all four never-issued handle calls -> INVALID_INPUT envelope", all(e.get("status") == "INVALID_INPUT" and e.get("_sc") for e in res),
              [status(e) for e in res])
    log.check("each detail.message contains the handle", all(BAD in msg(e) for e in res), [msg(e)[:90] for e in res])
    log.check("detail.code == INVALID_INPUT", all((e.get("detail") or {}).get("code") == "INVALID_INPUT" for e in res), "")
    other, op = await open_golden(m, "cylinder-r5-h20")
    c1 = await m.call("document_close", {"doc": other})
    stale = await m.call("query_tree_summary", {"doc": other})
    c2 = await m.call("document_close", {"doc": other})
    log.check("stale handle after close -> INVALID_INPUT; second close INVALID_INPUT no crash",
              op.get("status") == "OK" and c1.get("status") == "OK" and stale.get("status") == "INVALID_INPUT" and c2.get("status") == "INVALID_INPUT",
              [status(op), status(c1), status(stale), msg(stale)[:80], status(c2)])
    mal = await m.call("query_tree_summary", {"doc": "not-a-handle at all"})
    log.check("malformed string also INVALID_INPUT (registry lookup, not format)", mal.get("status") == "INVALID_INPUT", (status(mal), msg(mal)[:80]))
    await frame_shot(m, doc, "tc-09-12-after.png")


go("tc-09-12", body)
