from tc05lib import *


async def body(m, log):
    docs = sc(await m.call("document_list", {})).get("documents") or []
    doc = [d for d in docs if d["label"] == "TC0501"][0]["doc"]
    v = await m.call("verify_sketch", {"doc": doc, "sketch": "Sketch"})
    s = sc(v).get("subject") or {}
    log.check("Given (second domain, verify_sketch) Sketch fully_constrained true, dof 0", v.get("status") == "OK" and s.get("fully_constrained") is True and s.get("dof") == 0, {k: s.get(k) for k in ("fully_constrained", "dof")})
    c = await m.call("document_close", {"doc": doc})
    log.check("cleanup document_close OK", c.get("status") == "OK", short(c))


go("tc-05-01b", body)
