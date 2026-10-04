import asyncio, json
from tclib import *
log = Log("tc-13-10.jsonl")
def rectangle(width, height):
    corners = [(0, 0), (width, 0), (width, height), (0, height)]
    geometry = [{"kind": "line_segment", "start": list(corners[i]), "end": list(corners[(i + 1) % 4])} for i in range(4)]
    constraints = [{"type": "Coincident", "first": i, "first_pos": 2, "second": (i + 1) % 4, "second_pos": 1} for i in range(4)]
    constraints += [{"type": "Horizontal", "first": 0}, {"type": "Horizontal", "first": 2}, {"type": "Vertical", "first": 1}, {"type": "Vertical", "first": 3},
        {"type": "Coincident", "first": 0, "first_pos": 1, "second": -1, "second_pos": 1},
        {"type": "DistanceX", "first": 0, "first_pos": 1, "second": 0, "second_pos": 2, "value": {"value": width, "unit": "mm"}},
        {"type": "DistanceY", "first": 1, "first_pos": 1, "second": 1, "second_pos": 2, "value": {"value": height, "unit": "mm"}}]
    return {"geometry": geometry, "constraints": constraints}
async def main():
    async with mcp_session() as s:
        c = await call(s, "document_create", {"label": "TC13Pad"}, log); H = sc(c)["doc"]
        json.dump({"h": H}, open("cur.json", "w"))
        await mutate(s, H, "feature_body_create", {"doc": H, "name": "Body"}, log)
        await mutate(s, H, "sketch_create", {"doc": H, "name": "Sketch", "plane": "XY", "body": "Body"}, log)
        await mutate(s, H, "sketch_add_geometry", {"doc": H, "sketch": "Sketch", **rectangle(30, 20)}, log)
        time.sleep(1); log("fitall0", r=slim(fitall())); time.sleep(1)
        st = snap("tc-13-10-before.png"); log("before", tree=tree_items(st))
        p = await mutate(s, H, "feature_pad", {"doc": H, "body": "Body", "profile": "Sketch", "name": "Pad", "length": {"value": 5, "unit": "mm"}}, log)
        time.sleep(1.5)
        st = snap(); fa = elements(st, role="Button", label="Fit All"); log("fitall_present", n=len(fa))
        log("fitall", r=slim(fitall())); time.sleep(1.5)
        st = snap("tc-13-10-after-pad.png"); log("after_flat", tree=tree_items(st))
        body = [e for e in elements(st, role="TreeItem", label="Body")]
        log("body_actions", a=[e.get("actions") for e in body])
        snap("tc-13-10-viewport.png")
        await call(s, "query_tree_summary", {"doc": H, "depth": 2}, log)
        await call(s, "query_mass_properties", {"doc": H, "object": "Pad"}, log)
        bad = await call(s, "preview_dry_run", {"doc": H, "operation": {"tool": "feature_pad", "args": {"body": "Body", "profile": "Sketch", "name": "Pad2", "length": 5}}}, log)
        await call(s, "view_fit_viewport", {"doc": H}, log); time.sleep(1)
        snap("tc-13-10-after.png")
asyncio.run(main())
