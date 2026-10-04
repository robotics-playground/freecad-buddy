"""TC-06-06 recheck: does the GUI window stop drawing PadB when PadB.Visibility is false?"""
import time
from tc06lib import *
from tc06_06_vis import vis
from importlib import import_module
b = import_module("tc-06-06b".replace("-", "_")) if False else None


async def body(m, log):
    docs = sc(await m.call("document_list", {})).get("documents") or []
    doc = [d["doc"] for d in docs if d["label"] == "TC0604"][0]
    pid, win = ids()
    # deselect first (click empty viewport background), so the selection highlight does not mask the drawing
    log.note(f"deselect click: {cua('click', {'pid': pid, 'window_id': win, 'x': 450, 'y': 820}).get('route')}")
    time.sleep(0.8)
    items = [e for e in snapshot().get("elements", []) if e.get("role") == "TreeItem" and e.get("label") == "PadB"]
    log.note(f"PadB TreeItems: {[e.get('frame') for e in items]}")
    tree_item = [e for e in items if (e.get("frame") or {}).get("y", 0) < 500]
    target = tree_item[0] if tree_item else items[0]
    r = cua("press_key", {"pid": pid, "element_token": target["element_token"], "key": "space", "delivery_mode": "foreground"})
    time.sleep(3.0)
    t = await m.call("query_tree_summary", {"doc": doc, "depth": 2})
    tb = await m.call("query_object", {"doc": doc, "object": "BodyB"})
    log.note(f"space -> {r.get('route')}; PadB visibility={vis(t, 'PadB')}; BodyB visibility={vis(t, 'BodyB')}")
    log.note("BodyB props: " + json.dumps({k: v for k, v in (sc(tb).get('properties') or {}).items() if k in ('Tip', 'Visibility', 'DisplayModeBody', 'Group')})[:400])
    log.note(f"hidden2 shot: {shot('tc-06-06-hidden2.png')}")
    r1, _ = await render(m, doc, None, "tc-06-06-default-hidden2.png")
    log.note(f"default render while hidden: {objs(r1)}")

go("tc-06-06c", body)
