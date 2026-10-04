"""TC-06-02 follow-up: is the square seen in the GUI BOTTOM view a solid edge or the visible TowerProfile sketch?"""
import importlib.util, time
from tc06lib import *
spec = importlib.util.spec_from_file_location("t607", "tc-06-07.py")


async def body(m, log):
    await close_all(m, log)
    src = open("tc-06-07.py", encoding="utf-8").read().split("async def body")[0]
    ns = {}
    exec(src, ns)
    doc, p = await ns["lblock"](m, "TC0602c")
    t = await m.call("query_tree_summary", {"doc": doc, "depth": 2})
    log.note("tree: " + json.dumps(sc(t).get("tree")))
    ob = await m.call("query_object", {"doc": doc, "object": "Tower"})
    log.note("Tower Refine: " + json.dumps((sc(ob).get("properties") or {}).get("Refine")))
    r, _ = await render(m, doc, {"camera": "bottom", "include": ["Tower", "TowerProfile"]}, "tc-06-02c-bottom-with-sketch.png")
    log.note(f"render bottom incl. TowerProfile: {objs(r)} {r.get('status')}")

go("tc-06-02c", body)
