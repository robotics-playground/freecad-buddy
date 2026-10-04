"""TC-06-06 final restore: one toggle back to visible, deselect, fit, after capture, final default render."""
import time
from tc06lib import *
from tc06_06_vis import vis


async def body(m, log):
    docs = sc(await m.call("document_list", {})).get("documents") or []
    doc = [d["doc"] for d in docs if d["label"] == "TC0604"][0]
    pid, win = ids()
    items = [e for e in snapshot().get("elements", []) if e.get("role") == "TreeItem" and e.get("label") == "PadB" and (e.get("frame") or {}).get("y", 0) < 500]
    cua("press_key", {"pid": pid, "element_token": items[0]["element_token"], "key": "space", "delivery_mode": "foreground"})
    time.sleep(1.5)
    t = await m.call("query_tree_summary", {"doc": doc, "depth": 2})
    log.check("restored: PadB visibility true, labels intact", vis(t, "PadB") is True and '"label": "PadB"' in json.dumps(sc(t)), vis(t, "PadB"))
    cua("click", {"pid": pid, "window_id": win, "x": 450, "y": 820})
    time.sleep(0.8)
    r3, _ = await render(m, doc, None, "tc-06-06-default-restored.png")
    log.check("restored default render lists PadB again", objs(r3) == ["PadA", "PadB"], objs(r3))
    fit = await m.call("view_fit_viewport", {"doc": doc})
    log.check("visual: view_fit_viewport returns OK", fit.get("status") == "OK", short(fit, 300))
    time.sleep(1.0)
    log.note(f"after shot: {shot('tc-06-06-after.png')}")

go("tc-06-06e", body)
