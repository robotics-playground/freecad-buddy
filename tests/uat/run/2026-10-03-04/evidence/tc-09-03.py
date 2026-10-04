from tc09lib import *  # noqa


async def body(m, log):
    doc, obj = await scene(m, log, "tc-09-03")
    log.check("Given sole object resolved", obj == "Box", obj)
    a = await m.call("export_step", {"doc": doc, "objects": [obj]})
    b = await m.call("verify_shape", {"object": obj})
    c = await m.call("verify_export_stl", {"doc": doc})
    d = await m.call("query_object", {"doc": doc})
    for name, e in (("missing path", a), ("missing doc", b), ("missing export_id", c), ("missing object", d)):
        log.check(f"{name} -> protocol rejection (isError, no envelope)", is_reject(e), raw(e) or short(e))
    log.check("none of the four has a status", all("status" not in e for e in (a, b, c, d)), [status(e) for e in (a, b, c, d)])
    x = await m.call("verify_export_stl", {"doc": doc, "export_id": "fcb-export:bogus"})
    log.check("contrast: bogus export_id -> envelope INVALID_INPUT", x.get("status") == "INVALID_INPUT" and x.get("_sc") is True,
              short(x))
    await frame_shot(m, doc, "tc-09-03-after.png")


go("tc-09-03", body)
