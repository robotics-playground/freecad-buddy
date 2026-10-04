from tc05lib import *


async def body(m, log):
    docs = sc(await m.call("document_list", {})).get("documents") or []
    doc = [d for d in docs if d["label"] == "TC0506"][0]["doc"]
    tr = await m.call("query_tree_summary", {"doc": doc, "depth": 1})
    log.note("body children: " + json.dumps([(c["name"], c["type"], c.get("visibility")) for c in sc(tr)["tree"][0].get("children", [])]))
    for o in ("Body", "Pocket", "Pattern"):
        r = await m.call("query_mass_properties", {"doc": doc, "object": o})
        log.note(f"{o}: status={r.get('status')} volume={vol(r)}")
    qb = await m.call("query_object", {"doc": doc, "object": "Body"})
    log.note(f"Body Tip={json.dumps((sc(qb).get('properties') or {}).get('Tip'))[:200]}")


go("tc-05-06-probe", body)
