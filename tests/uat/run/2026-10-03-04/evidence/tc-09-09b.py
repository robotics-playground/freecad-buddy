from tc09lib import *  # noqa


async def body(m, log):
    docs = sc(await m.call("document_list", {})).get("documents") or []
    long_doc = [d["doc"] for d in docs if len(d.get("label") or "") == 4096]
    golden = [d["doc"] for d in docs if d.get("label") == "box-10-20-30"][0]
    c = await m.call("document_close", {"doc": long_doc[0]})
    log.note(f"cleanup step 1 run early: document_close long-labelled doc -> {c.get('status')}")
    await frame_shot(m, golden, "tc-09-09-after-golden.png")


go("tc-09-09b", body)
