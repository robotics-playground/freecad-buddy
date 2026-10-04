import os

from tc09lib import *  # noqa


async def body(m, log):
    doc, obj = await scene(m, log, "tc-09-13")
    reads = [await m.call(t, {"doc": doc, "object": "NoSuchObject"}) for t in ("query_object", "query_mass_properties", "query_placement", "verify_shape")]
    log.check("all four reads -> INVALID_INPUT", all(e.get("status") == "INVALID_INPUT" for e in reads), [status(e) for e in reads])
    log.check("verify_shape message == 'unknown object: NoSuchObject'", msg(reads[3]) == "unknown object: NoSuchObject", msg(reads[3]))
    log.note(f"other read messages: {[msg(e)[:80] for e in reads[:3]]}")
    ex = await m.call("export_step", {"doc": doc, "path": f"{EV}/tc-09-13-o.step", "objects": ["NoSuchObject"]})
    log.check("export message == 'unknown object: NoSuchObject'", ex.get("status") == "INVALID_INPUT" and msg(ex) == "unknown object: NoSuchObject",
              (status(ex), msg(ex)))
    log.check("failed export wrote nothing", not os.path.exists(f"{EV}/tc-09-13-o.step"), "")
    cs = await m.call("verify_shape", {"doc": doc, "object": "box"})
    log.check("case-differing 'box' -> INVALID_INPUT", cs.get("status") == "INVALID_INPUT", (status(cs), msg(cs)))
    em = await m.call("verify_shape", {"doc": doc, "object": ""})
    log.check("empty object -> INVALID_INPUT \"missing required 'object' name\"", em.get("status") == "INVALID_INPUT" and msg(em) == "missing required 'object' name",
              (status(em), msg(em), raw(em)))
    await frame_shot(m, doc, "tc-09-13-after.png")


go("tc-09-13", body)
