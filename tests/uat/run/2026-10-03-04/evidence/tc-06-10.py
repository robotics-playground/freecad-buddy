"""TC-06-10: a dirty document renders with dirty_document true. Golden box-10-20-30 (Box opens hidden; shown via GUI)."""
import time
from tc06lib import *

GOLD = "D:/Work/Personal/Sources/freecad-buddy/benchmarks/g0/golden-models/box-10-20-30.FCStd"


async def body(m, log):
    await close_all(m, log)
    op = await m.call("document_open", {"path": GOLD})
    doc = sc(op).get("doc")
    log.check("Given: document_open returns a handle", op.get("status") == "OK" and bool(doc), short(op))
    pid, win = ids()
    time.sleep(1.0)
    sa = cua("invoke_menu", {"pid": pid, "window_id": win, "path": ["View", "Visibility", "Show All Objects"]})
    time.sleep(1.0)
    log.note(f"Show All Objects -> {sa.get('route') or sa}")
    ob = await m.call("query_object", {"doc": doc, "object": "Box"})
    log.note("Box: " + json.dumps({k: v for k, v in sc(ob).items() if k != 'properties'})[:300] + " props=" + json.dumps(sorted((sc(ob).get('properties') or {}).keys()))[:400])
    r0, _ = await render(m, doc, None, "tc-06-10-clean.png")
    log.check("Given: clean render dirty_document false", (sc(r0).get("render") or {}).get("dirty_document") is False, sc(r0).get("render"))
    args = {"feature": "Box", "parameters": {"Length": {"value": 25, "unit": "mm"}}}
    pv_, ap = await apply(m, doc, "feature_set_parameters", args)
    log.note("literal When: preview " + short(pv_, 400) + " | apply " + short(ap, 400))
    vr = await m.call("verify_recompute", {"doc": doc})
    log.note("verify_recompute after literal When: " + json.dumps(sc(vr))[:400])

go("tc-06-10", body)
