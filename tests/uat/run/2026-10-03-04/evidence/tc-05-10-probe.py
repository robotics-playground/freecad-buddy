from tc05lib import *


async def body(m, log):
    docs = sc(await m.call("document_list", {})).get("documents") or []
    doc = [d for d in docs if d["label"] == "TC0510"][0]["doc"]
    code = ("_d = FreeCAD.getDocument('TC0510')\n"
            "try:\n    _d.commitTransaction = lambda: None\n    r1 = 'instance setattr accepted: ' + repr(_d.commitTransaction)\nexcept Exception as e:\n    r1 = 'instance setattr refused: %s: %s' % (type(e).__name__, e)\n"
            "result = r1")
    r = await m.call("debug_exec", {"doc": doc, "code": code})
    log.note(f"alternative injection probe (instance attribute) -> {short(r)} {sc(r).get('value_repr')}")


go("tc-05-10-probe", body)
