from tc05lib import *

SPY = ("import os\n"
       "from freecad_buddy.usecases import transaction as _t\n"
       "_o = _t._delete_snapshot\n"
       "def _spy(path):\n"
       "    d = os.path.dirname(path)\n"
       "    FreeCAD._fcb_tc0502 = {'path': path, 'listing_before_delete': sorted(os.listdir(d)), 'size': os.path.getsize(path) if os.path.exists(path) else None}\n"
       "    _t._delete_snapshot = _o\n"
       "    return _o(path)\n"
       "_t._delete_snapshot = _spy\n"
       "result = 'armed'")


async def body(m, log):
    await close_all(m, log)
    doc = await body_sketch(m, "TC0502c")
    args = {"body": "Body", "profile": "Sketch", "name": "Pad", "length": q(30)}
    preview = await m.call("preview_dry_run", {"doc": doc, "operation": {"tool": "feature_pad", "args": args}})
    log.note("supplementary in-process observation for TC-05-02 (the shell cannot read FreeCAD-created snapshot dirs: ACL Access is denied). "
             "debug_exec wraps transaction._delete_snapshot once to list the snapshot dir just before the commit deletes it.")
    a = await m.call("debug_exec", {"doc": doc, "code": SPY})
    log.note(f"spy -> {sc(a).get('value_repr')}")
    env = await m.call("feature_pad", dict(args, doc=doc, confirm={"preview_id": sc(preview).get("preview_id"), "elicitation_action": "accept"}))
    r = await m.call("debug_exec", {"doc": doc, "code": "import os\nx = getattr(FreeCAD, '_fcb_tc0502', None)\nresult = (x, os.path.exists(os.path.dirname(x['path'])) if x else None)"})
    log.note(f"feature_pad -> {short(env)}; spy record -> {sc(r).get('value_repr')}")
    rec = sc(r).get("value_repr") or ""
    log.check("snapshot dir held <DocumentName>.FCStd (TC0502c.FCStd) while the bracket was open", "'TC0502c.FCStd'" in rec, rec)
    log.check("snapshot dir gone after commit (in-process os.path.exists -> False)", rec.rstrip(")").endswith("False"), rec[-40:])
    c = await m.call("document_close", {"doc": doc})
    log.note(f"close -> {c.get('status')}")


go("tc-05-02c", body)
