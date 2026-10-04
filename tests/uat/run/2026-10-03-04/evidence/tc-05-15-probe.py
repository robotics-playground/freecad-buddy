from tc05lib import *


async def body(m, log):
    docs = sc(await m.call("document_list", {})).get("documents") or []
    doc = [d for d in docs if d["label"] == "TC0515"][0]["doc"]
    x = await m.call("debug_exec", {"doc": doc, "code": "f = doc.getObject('Fillet')\nresult = (f.Base, f.getSubObjects() if hasattr(f,'getSubObjects') else None, [ (l[0].Name, l[1]) for l in f.getPropertyByName('Base', 2)] if False else None, f.ExpressionEngine)"})
    log.note(f"Fillet.Base in-process -> {sc(x).get('value_repr')} {short(x)}")
    y = await m.call("debug_exec", {"doc": doc, "code": "f = doc.getObject('Fillet')\ntry:\n    result = f.getPropertyByName('Base', 1)\nexcept Exception as e:\n    result = repr(e)"})
    log.note(f"Fillet Base (with shadow names) -> {sc(y).get('value_repr')}")


go("tc-05-15-probe", body)
