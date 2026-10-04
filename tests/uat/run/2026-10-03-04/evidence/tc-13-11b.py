import asyncio, json
from tclib import *
log = Log("tc-13-11b.jsonl")
H = json.load(open("cur.json"))["h"]
def rows(st):
    items = [e["label"] for e in elements(st, role="TreeItem")]
    return [(items[i], items[i + 1]) for i in range(len(items) - 1) if items[i] in ("Length",) and "mm" in (items[i + 1] or "")]
def sel():
    pid, win = ids()
    log("select_click", r=cua("click", {"pid": pid, "window_id": win, "x": 900, "y": 560})); time.sleep(1)
async def main():
    async with mcp_session() as s:
        await call(s, "query_mass_properties", {"doc": H, "object": "Pad"}, log)
        await call(s, "view_fit_viewport", {"doc": H}, log); time.sleep(1)
        sel()
        st = snap("tc-13-11b-before.png"); log("before_rows", rows=rows(st))
        args = {"doc": H, "feature": "Pad", "parameters": {"Length": {"value": 12, "unit": "mm"}}}
        await mutate(s, H, "feature_set_parameters", args, log); time.sleep(1.5)
        st = snap("tc-13-11b-after-change.png"); log("after_rows", rows=rows(st))
        await call(s, "query_mass_properties", {"doc": H, "object": "Pad"}, log)
        await call(s, "verify_recompute", {"doc": H}, log)
        await call(s, "view_fit_viewport", {"doc": H}, log); time.sleep(1)
        sel()
        st = snap("tc-13-11-after.png"); log("final_rows", rows=rows(st))
        # TC-13-12 on the same state
        snap("tc-13-12b-mutated.png")
        await call(s, "document_undo", {"doc": H}, log); time.sleep(1.5)
        st = snap("tc-13-12b-after-undo.png"); log("undo_rows", rows=rows(st))
        await call(s, "query_mass_properties", {"doc": H, "object": "Pad"}, log)
        await call(s, "query_tree_summary", {"doc": H, "depth": 2}, log)
        await call(s, "verify_recompute", {"doc": H}, log)
        await call(s, "view_fit_viewport", {"doc": H}, log); time.sleep(1)
        sel()
        st = snap("tc-13-12-after.png"); log("undo_final_rows", rows=rows(st))
asyncio.run(main())
