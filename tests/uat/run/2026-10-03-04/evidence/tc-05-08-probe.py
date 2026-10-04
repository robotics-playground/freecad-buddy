from tc05lib import *


async def body(m, log):
    docs = sc(await m.call("document_list", {})).get("documents") or []
    doc = [d for d in docs if d["label"] == "TC0508"][0]["doc"]
    for o in ("Body", "Fillet", "Pad"):
        r = await m.call("query_mass_properties", {"doc": doc, "object": o})
        log.note(f"{o}: status={r.get('status')} vol={vol(r)} detail={(r.get('detail') or {}).get('message') if isinstance(r.get('detail'), dict) else ''}")
    qb = await m.call("query_object", {"doc": doc, "object": "Body"})
    log.note(f"Body Tip={json.dumps((sc(qb).get('properties') or {}).get('Tip'))[:200]}")
    vr = await m.call("verify_recompute", {"doc": doc})
    log.note(f"verify_recompute -> {short(vr, 500)}")
    x = await m.call("debug_exec", {"doc": doc, "code": "result = [(o.Name, o.TypeId, o.isValid(), o.getStatusString(), (o.Shape.isNull() if hasattr(o,'Shape') else None)) for o in doc.Objects if not o.TypeId.startswith('App::')] + [('Tip', doc.getObject('Body').Tip.Name), ('UndoMode', doc.UndoMode)]"})
    log.note(f"in-process object states: {sc(x).get('value_repr')}")


go("tc-05-08-probe", body)
