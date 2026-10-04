import asyncio, json
from tclib import *
log = Log("tc-13-11.jsonl")
H = json.load(open("cur.json"))["h"]
def length_rows(st):
    items = [e["label"] for e in elements(st, role="TreeItem")]
    out = []
    for i, lab in enumerate(items):
        if lab in ("Length", "Width", "Height") and i + 1 < len(items):
            out.append((lab, items[i + 1]))
    return out
async def main():
    async with mcp_session() as s:
        await call(s, "query_mass_properties", {"doc": H, "object": "Box"}, log)
        log("sel", r=menu_retry(["Edit", "Select All"], tries=8, wait=6)); time.sleep(1)
        log("datatab", r=slim(click_label("TabItem", "Data"))); time.sleep(1)
        log("fitall", r=slim(fitall())); time.sleep(1)
        st = snap("tc-13-11-before.png"); log("before_rows", rows=length_rows(st))
        args = {"doc": H, "feature": "Box", "parameters": {"Length": {"value": 25, "unit": "mm"}}}
        await mutate(s, H, "feature_set_parameters", args, log)
        time.sleep(1.5)
        st = snap("tc-13-11-after-change.png"); log("after_rows", rows=length_rows(st))
        await call(s, "query_mass_properties", {"doc": H, "object": "Box"}, log)
        await call(s, "verify_recompute", {"doc": H}, log)
        await call(s, "feature_set_parameters", args, log)
        await call(s, "view_fit_viewport", {"doc": H}, log); time.sleep(1)
        st = snap("tc-13-11-after.png"); log("final_rows", rows=length_rows(st))
asyncio.run(main())
