from tc05lib import *

ARGS = {"body": "Body", "profile": "Sketch", "name": "Pad", "length": q(30)}


async def body(m, log):
    await close_all(m, log)
    doc = await body_sketch(m, "TC0510")
    probe = await m.call("debug_exec", {"doc": doc, "code": "1"})
    log.check("Given debug_exec NOT refused 'debug_exec is disabled ...'", probe.get("status") == "OK", short(probe))
    v = await m.call("verify_sketch", {"doc": doc, "sketch": "Sketch"})
    s = sc(v).get("subject") or {}
    log.check("Given Sketch fully constrained dof 0 (verify_sketch; query_sketch_info has no dof)", s.get("fully_constrained") is True and s.get("dof") == 0, s.get("dof"))
    fit, rec = await capture(m, doc, "tc-05-10-before.png")
    log.note(f"before fit={fit}")
    preview = await m.call("preview_dry_run", {"doc": doc, "operation": {"tool": "feature_pad", "args": ARGS}})
    token = sc(preview).get("preview_id")
    code = ("import FreeCAD\n_d = FreeCAD.getDocument('TC0510')\n_orig = type(_d).commitTransaction\n"
            "def _boom(self):\n    type(_d).commitTransaction = _orig\n    raise RuntimeError('injected commit failure')\n"
            "type(_d).commitTransaction = _boom")
    patch = await m.call("debug_exec", {"doc": doc, "code": code})
    log.note(f"literal commit patch (TC text) -> {short(patch, 500)}")
    log.write({"literal_patch_ok": patch.get("status") == "OK"})
    log.write({"doc": doc, "token": token})


go("tc-05-10", body)
