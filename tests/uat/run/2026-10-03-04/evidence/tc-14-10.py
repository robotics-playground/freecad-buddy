import os
from tc14lib import *

AUDIT = EVIDENCE / "tc-14-10-audit.jsonl"


def records():
    if not AUDIT.exists():
        return []
    return [json.loads(line) for line in AUDIT.read_text(encoding="utf-8").splitlines() if line.strip()]


async def body(m, log):
    log.check("Given audit file absent or empty at start", (not AUDIT.exists()) or AUDIT.stat().st_size == 0,
              AUDIT.exists())
    o = await m.call("document_open", {"path": BOX})
    h = sc(o).get("doc")
    log.check("Given document_open OK", o.get("status") == "OK", h)
    log.note(f"show all {menu(['View', 'Visibility', 'Show All Objects'])}")
    log.note(f"trimetric {menu(['View', 'Standard Views', 'Axonometric', 'Trimetric'])}")
    for _ in range(4):
        menu(["View", "Zoom", "Zoom In"])
    t0 = await m.call("query_tree_summary", {"doc": h})
    log.check("Given framing.fits false", fr(t0).get("fits") is False, fr(t0))
    shot("tc-14-10-before.png")
    n0 = len(records())
    f1 = await m.call("view_fit_viewport", {"doc": h})
    log.check("When fit #1 OK", f1.get("status") == "OK", f1.get("text"))
    new1 = records()[n0:]
    log.write({"audit_new_after_fit1": new1})
    shot("tc-14-10-after.png")
    n1 = len(records())
    f2 = await m.call("view_fit_viewport", {"doc": h})
    log.note(f"fit #2 (from the fitted camera) {f2.get('status')}")
    new2 = records()[n1:]
    log.write({"audit_new_after_fit2": new2})
    print("HANDLE", h)


go("tc-14-10", body)
