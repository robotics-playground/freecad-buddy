from tc09lib import *  # noqa


async def body(m, log):
    tools = (await m.session.list_tools()).tools
    surface = {t.name: {"addProps": t.inputSchema.get("additionalProperties"), "props": list((t.inputSchema.get("properties") or {}).keys()),
                        "required": t.inputSchema.get("required") or []} for t in tools}
    (EVIDENCE / "tc-09-05-tool_surface.json").write_text(json.dumps(surface, indent=1), encoding="utf-8")
    log.note(f"tool_surface.json regenerated from tools/list: {len(surface)} tools")
    doc, obj = await scene(m, log, "tc-09-05")
    bad = sorted(k for k, v in surface.items() if v["addProps"] is not False)
    log.check("surface command prints [] (every schema additionalProperties false)", bad == [], bad)
    calls = [
        ("verify_shape", {"doc": doc, "object": obj, "strict": True}),
        ("query_tree_summary", {"doc": doc, "max_nodes": 50}),
        ("export_step", {"doc": doc, "path": f"{EV}/tc-09-05-u.step", "overwrite": True}),
        ("document_close", {"doc": doc, "force": True}),
        ("query_capabilities", {"verbose": True}),
    ]
    res = []
    for tool, args in calls:
        e = await m.call(tool, args)
        res.append(e)
        log.check(f"{tool} + unknown key -> protocol rejection", is_reject(e), raw(e) or short(e))
    dl = await m.call("document_list", {})
    handles = [d["doc"] for d in sc(dl).get("documents") or []]
    log.check("document_close rejected: document_list still names <H>", doc in handles, handles)
    log.check("query_capabilities empty-props schema still rejects extras", is_reject(res[4]) and surface["query_capabilities"]["props"] == [],
              surface["query_capabilities"])
    log.check("none of the five returned OK", all(e.get("status") != "OK" for e in res), [status(e) for e in res])
    import os
    log.check("(extra) export_step with unknown key wrote nothing", not os.path.exists(f"{EV}/tc-09-05-u.step"), "")
    await frame_shot(m, doc, "tc-09-05-after.png")


go("tc-09-05", body)
