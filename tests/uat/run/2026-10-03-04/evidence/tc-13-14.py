import asyncio, json
from tclib import *
log = Log("tc-13-14.jsonl")
H = json.load(open("cur.json"))["h"]
def vis_token():
    st = snap(); items = elements(st, role="TreeItem")
    for i, e in enumerate(items[:-1]):
        if e["label"] == "Visibility":
            return items[i + 1]
async def reads(s, tag):
    a = await call(s, "query_tree_summary", {"doc": H}, log)
    b = await call(s, "query_tree_summary", {"doc": H, "filters": {"visible_only": True}}, log)
    m = await call(s, "query_mass_properties", {"doc": H, "object": "BoxHole"}, log)
    log("summary", tag=tag, vis=[(n["label"], n["visibility"]) for n in sc(a).get("tree", [])],
        visible_only=[n["name"] for n in sc(b).get("tree", [])], volume=sc(m).get("volume"))
async def main():
    async with mcp_session() as s:
        await reads(s, "pre")
        pid, _ = ids()
        for target in ("false", "true", "false"):
            v = vis_token(); log("row", before=v["label"])
            r = cua("set_value", {"pid": pid, "element_token": v["element_token"], "value": target}); log("set_value", target=target, r=r)
            time.sleep(1.5)
            snap(f"tc-13-14-{target}-{int(time.time())%1000}.png")
            await reads(s, f"after_{target}")
asyncio.run(main())
