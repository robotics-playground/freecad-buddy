"""TC-06-06: default scene honors live GUI Visibility. Doc TC0604: ObjectA=PadA, ObjectB=PadB (in BodyB)."""
import time
from tc06lib import *
from tc03lib import expand


def vis(env, name):
    def walk(nodes):
        for n in nodes or []:
            if n.get("name") == name:
                return n.get("visibility")
            v = walk(n.get("children"))
            if v is not None:
                return v
        return None
    return walk(sc(env).get("tree"))


def toggle_padb(log, tag):
    pid, win = ids()
    st = snapshot()
    items = model_items(st, "PadB")
    if not items:
        log.note(f"{tag}: PadB TreeItem not in snapshot")
        return None
    sel = cua("click", {"pid": pid, "element_token": items[0]["element_token"]})
    time.sleep(0.8)
    st = snapshot()
    items = model_items(st, "PadB")
    r = cua("press_key", {"pid": pid, "element_token": items[0]["element_token"], "key": "space", "delivery_mode": "foreground"})
    time.sleep(1.0)
    rec = {"select": [sel.get("effect"), sel.get("route")], "space": [r.get("effect"), r.get("route")], "token_role": items[0].get("role"), "token_label": items[0].get("label")}
    log.note(f"{tag}: {rec}")
    return rec


async def body(m, log):
    docs = sc(await m.call("document_list", {})).get("documents") or []
    doc = [d["doc"] for d in docs if d["label"] == "TC0604"][0]
    ts = await m.call("query_tree_summary", {"doc": doc, "depth": 2})
    log.check("Given: PadA and PadB visibility true", vis(ts, "PadA") is True and vis(ts, "PadB") is True, {"PadA": vis(ts, "PadA"), "PadB": vis(ts, "PadB")})
    st = snapshot()
    log.check("Given: accessibility tree lists a Tree role element", any(e.get("role") == "Tree" for e in st.get("elements", [])), sorted({e.get("role") for e in st.get("elements", [])}))
    r0, _ = await render(m, doc, None, "tc-06-06-default-before.png")
    log.note(f"default before: {objs(r0)}")
    log.note(f"expand BodyB: {expand('BodyB')}")
    shot("tc-06-06-tree.png")
    hidden = False
    for attempt in range(4):
        toggle_padb(log, f"hide attempt {attempt + 1}")
        t = await m.call("query_tree_summary", {"doc": doc, "depth": 2})
        log.note(f"after hide attempt {attempt + 1}: PadB visibility={vis(t, 'PadB')}, labels ok={'\"label\": \"PadB\"' in json.dumps(sc(t))}")
        if vis(t, "PadB") is False:
            hidden = True
            break
    pid, win = ids()
    vsr = cua("verify_state", {"pid": pid, "window_id": win, "expect": [{"element": {"selector": {"label_contains": "PadB"}, "exists": True}}]})
    log.check("hide landed: verify_state label_contains PadB satisfied", vsr.get("status") == "satisfied", json.dumps(vsr)[:300])
    log.check("bridge sees PadB visibility false", hidden, "")
    r1, _ = await render(m, doc, None, "tc-06-06-default-hidden.png")
    r2, _ = await render(m, doc, {"include": ["PadB"]}, "tc-06-06-include-PadB.png")
    log.check("post-hide default render lacks PadB", "PadB" not in (objs(r1) or []), objs(r1))
    log.check("explicit include PadB == ['PadB'] + link", objs(r2) == ["PadB"] and bool(link(r2)), objs(r2))
    fit = await m.call("view_fit_viewport", {"doc": doc})
    log.note(f"fit before hidden.png: {short(fit, 300)}")
    time.sleep(1.0)
    shot("tc-06-06-hidden.png")
    restored = False
    for attempt in range(4):
        toggle_padb(log, f"restore attempt {attempt + 1}")
        t = await m.call("query_tree_summary", {"doc": doc, "depth": 2})
        if vis(t, "PadB") is True:
            restored = True
            break
    log.check("restored: PadB visibility true", restored, "")
    t = await m.call("query_tree_summary", {"doc": doc, "depth": 2})
    log.check("labels intact (no stray rename)", '"label": "PadB"' in json.dumps(sc(t)) and '"label": "PadA"' in json.dumps(sc(t)), "")
    r3, _ = await render(m, doc, None, "tc-06-06-default-restored.png")
    log.check("restored default render lists PadB again", "PadB" in (objs(r3) or []), objs(r3))
    fit = await m.call("view_fit_viewport", {"doc": doc})
    log.check("visual: view_fit_viewport returns OK", fit.get("status") == "OK", short(fit, 300))
    time.sleep(1.0)
    shot("tc-06-06-after.png")

go("tc-06-06", body)
