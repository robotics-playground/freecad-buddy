import re

from tc09lib import *  # noqa


async def body(m, log):
    await close_all(m, log)
    op = await m.call("document_open", {"path": f"{EV}/tc-09-17-fixture.FCStd"})
    doc = sc(op).get("doc")
    log.check("Given faulted fixture opens (Pad over emptied Sketch)", op.get("status") == "OK", (status(op), msg(op)[:120]))
    show_all(log)
    r1 = await m.call("verify_recompute", {"doc": doc})
    r2 = await m.call("verify_recompute", {"doc": doc})
    s1, s2 = sc(r1), sc(r2)
    log.check("status RECOMPUTE_ERROR, never OK", r1.get("status") == "RECOMPUTE_ERROR", status(r1))
    log.check("verdict == RECOMPUTE_ERROR == status", s1.get("verdict") == "RECOMPUTE_ERROR" == r1.get("status"), s1.get("verdict"))
    tagged = [c for c in s1.get("checks") or [] if c.get("id") == "recompute.object" and c.get("passed") is False
              and (c.get("detail") or {}).get("code") == "recompute.error"]
    log.check("a recompute.object check passed:false detail.code recompute.error", len(tagged) >= 1, s1.get("checks"))
    text = r1.get("text") or ""
    log.check("text matches 'Recompute: <n> error(s): <names>.'", re.fullmatch(r"Recompute: \d+ error\(s\): .+\.", text) is not None, text)
    import subprocess
    g = subprocess.run(["C:/Program Files/Git/bin/bash.exe", "-c", f'cd "{PROJECT}"; grep -n "_RECOMPUTE_ERROR_STATES =" src/freecad_buddy/usecases/verify.py'],
                       capture_output=True, text=True).stdout.strip()
    log.check("_RECOMPUTE_ERROR_STATES includes Touched", "Touched" in g, g + " (TC cites verify.py:24)")
    fo1, fo2 = (s1.get("subject") or {}).get("failing_objects"), (s2.get("subject") or {}).get("failing_objects")
    log.check("stable across two calls: same status and failing_objects", r2.get("status") == r1.get("status") and fo1 == fo2 and fo1, (fo1, fo2))
    box, _ = await open_golden(m)
    clean = await m.call("verify_recompute", {"doc": box})
    log.check("clean box-10-20-30 in same session -> OK", clean.get("status") == "OK", status(clean))
    await m.call("document_close", {"doc": box})
    await frame_shot(m, doc, "tc-09-17-after.png")
    print("DOC", doc)


go("tc-09-17", body)
