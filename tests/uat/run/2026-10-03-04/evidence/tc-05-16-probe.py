from tc05lib import *


async def body(m, log):
    docs = sc(await m.call("document_list", {})).get("documents") or []
    doc = [d for d in docs if d["label"] == "TC0516"][0]["doc"]
    x = await m.call("debug_exec", {"doc": doc, "code": "b = doc.getObject('Body')\nc = doc.getObject('Chamfer'); f = doc.getObject('Fillet')\nresult = {'Group': [o.Name for o in b.Group], 'Tip': b.Tip.Name, 'Chamfer.BaseFeature': c.BaseFeature.Name if c.BaseFeature else None, 'Chamfer.Base': (c.Base[0].Name, c.Base[1]), 'Fillet.BaseFeature': f.BaseFeature.Name if f.BaseFeature else None, 'Body.vol': b.Shape.Volume, 'Chamfer.vol': c.Shape.Volume, 'Fillet.vol': f.Shape.Volume}"})
    log.note(f"post-commit body chain (in-process) -> {sc(x).get('value_repr')}")


go("tc-05-16-probe", body)
