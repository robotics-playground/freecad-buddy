from tc09lib import *  # noqa


async def body(m, log):
    await close_all(m, log)
    op = await m.call("document_open", {"path": f"{EV}/tc-09-18-fixture.FCStd"})
    doc = sc(op).get("doc")
    log.check("Given broken-reference fixture opens (Pad whose Sketch was deleted)", op.get("status") == "OK", status(op))
    show_all(log)
    r = await m.call("verify_recompute", {"doc": doc})
    dep = await m.call("query_dependencies", {"doc": doc})
    s = sc(r)
    fo = (s.get("subject") or {}).get("failing_objects") or []
    log.check("failing_objects contains Pad", "Pad" in fo, (status(r), fo))
    pad = [c for c in s.get("checks") or [] if c.get("id") == "recompute.object" and "Pad" in ((c.get("detail") or {}).get("objects") or [])]
    log.note(f"checks: {s.get('checks')}")
    meas = pad[0].get("measured") if pad else None
    log.check("measured == FreeCAD getStatusString (headless build: 'No object linked')", meas == "No object linked", meas)
    log.check("detail.message == '<Name>: <status string>'", bool(pad) and pad[0]["detail"].get("message") == f"Pad: {meas}", pad[0]["detail"] if pad else None)
    log.check("detail.objects == ['Pad']", bool(pad) and pad[0]["detail"].get("objects") == ["Pad"], pad[0]["detail"].get("objects") if pad else None)
    log.check("one check per failing object", len(s.get("checks") or []) == len(fo), (len(s.get("checks") or []), len(fo)))
    log.check("status string non-empty", bool(meas), meas)
    log.check("dependency query OK; graph shows the missing target", dep.get("status") == "OK", {"status": status(dep), "sc": sc(dep)})
    await frame_shot(m, doc, "tc-09-18-after.png")


go("tc-09-18", body)
