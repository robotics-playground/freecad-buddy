"""TC-06-06 consistency probe: toggle PadB via space on its tree row; after each toggle compare bridge visibility with the window."""
import time
from tc06lib import *
from tc06_06_vis import vis


async def body(m, log):
    docs = sc(await m.call("document_list", {})).get("documents") or []
    doc = [d["doc"] for d in docs if d["label"] == "TC0604"][0]
    pid, win = ids()
    for i in range(1, 5):
        items = [e for e in snapshot().get("elements", []) if e.get("role") == "TreeItem" and e.get("label") == "PadB" and (e.get("frame") or {}).get("y", 0) < 500]
        r = cua("press_key", {"pid": pid, "element_token": items[0]["element_token"], "key": "space", "delivery_mode": "foreground"})
        time.sleep(1.0)
        t1 = await m.call("query_tree_summary", {"doc": doc, "depth": 2})
        s = shot(f"tc-06-06-probe-toggle{i}.png")
        time.sleep(2.0)
        t2 = await m.call("query_tree_summary", {"doc": doc, "depth": 2})
        r1 = await m.call("query_screenshot", {"doc": doc})
        log.note(f"toggle {i}: route={r.get('route')} bridge PadB vis @1s={vis(t1, 'PadB')} @3s={vis(t2, 'PadB')} default render={objs(r1)} shot={s['file'].split('/')[-1]}")

go("tc-06-06d", body)
