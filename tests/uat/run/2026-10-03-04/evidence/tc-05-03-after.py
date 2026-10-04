from tc05lib import *


async def body(m, log):
    docs = sc(await m.call("document_list", {})).get("documents") or []
    doc = [d for d in docs if d["label"] == "TC0503"][0]["doc"]
    fit, rec = await capture(m, doc, "tc-05-03-after.png")
    log.note(f"after fit={fit}")
    pm = await m.call("query_mass_properties", {"doc": doc, "object": "Pad"})
    log.note(f"Pad volume after commit = {vol(pm)} (20x20x10 = 4000 expected if committed)")


go("tc-05-03-after", body)
