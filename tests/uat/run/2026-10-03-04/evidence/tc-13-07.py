import asyncio, json, sys
from tclib import *
case = sys.argv[1]; tag = sys.argv[2]
log = Log(f"tc-13-07-{tag}.jsonl")
CHECKS = {"non-watertight-open-shell": [{"fn": "expect_watertight", "expect": True}, {"fn": "expect_solid_count", "expect": 1}],
          "clean-control": [{"fn": "expect_volume", "expect": 6000, "tol": {"rel": 0.001}}, {"fn": "expect_bbox", "expect": [10, 20, 30], "tol": {"rel": 0.001}}, {"fn": "expect_solid_count", "expect": 1}]}
async def main():
    async with mcp_session() as s:
        o = await call(s, "document_open", {"path": f"{ROOT}/benchmarks/g0/fault-injection/{case}/fixture.FCStd"}, log)
        H = sc(o).get("doc"); json.dump({"h": H}, open("cur.json", "w"))
        t = await call(s, "query_tree_summary", {"doc": H}, log)
        objs = [n["name"] for n in sc(t).get("tree", [])]
        for name in objs:
            await call(s, "query_object", {"doc": H, "object": name}, log)
        await call(s, "verify_recompute", {"doc": H}, log)
        for name in objs:
            await call(s, "verify_shape", {"doc": H, "object": name, "checks": CHECKS[case]}, log)
        time.sleep(1)
        st = snap(f"tc-13-07-{tag}-tree.png")
        log("tree", items=[(e["label"]) for e in elements(st, role="TreeItem")])
        r = click_label("TreeItem", objs[0]); log("click_row", r=slim(r)); time.sleep(1)
        snap(f"tc-13-07-{tag}-status.png")
        f = await call(s, "view_fit_viewport", {"doc": H}, log)
        log("fitall", r=slim(fitall())); time.sleep(1.5)
        snap(f"tc-13-07-{tag}-after.png")
asyncio.run(main())
