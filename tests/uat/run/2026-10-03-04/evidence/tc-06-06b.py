"""TC-06-06 second pass: label recovered by Ctrl+Z; hide PadB via space on its TreeItem (no re-select click), eye-icon fallback."""
import time
from tc06lib import *
from tc06_06_vis import vis


def space_padb():
    pid, win = ids()
    items = model_items(snapshot(), "PadB")
    if not items:
        return {"error": "no PadB TreeItem"}
    r = cua("press_key", {"pid": pid, "element_token": items[0]["element_token"], "key": "space", "delivery_mode": "foreground"})
    time.sleep(1.0)
    return {"space": [r.get("effect"), r.get("route")], "frame": items[0].get("frame")}


def eye_padb():
    """FreeCAD 1.1 tree eye icon (visibility toggle) left of the PadB label, pixel click."""
    pid, win = ids()
    items = model_items(snapshot(), "PadB")
    if not items:
        return {"error": "no PadB TreeItem"}
    f = items[0]["frame"]
    scale = 1568 / 1775
    x, y = round((f["x"] + 12) * scale), round((f["y"] + f["h"] / 2) * scale)
    r = cua("click", {"pid": pid, "window_id": win, "x": x, "y": y})
    time.sleep(1.0)
    return {"eye_click": [x, y], "effect": r.get("effect"), "route": r.get("route")}


async def toggle(m, doc, log, want, tag):
    for attempt, fn in enumerate([space_padb, space_padb, eye_padb, eye_padb]):
        rec = fn()
        t = await m.call("query_tree_summary", {"doc": doc, "depth": 2})
        v = vis(t, "PadB")
        labels = '"label": "PadB"' in json.dumps(sc(t))
        log.note(f"{tag} attempt {attempt + 1} via {fn.__name__}: {rec} -> PadB visibility={v}, label intact={labels}")
        if not labels:
            log.note("label damaged; stop")
            return False, fn.__name__
        if v is want:
            return True, fn.__name__
    return False, None


async def body(m, log):
    docs = sc(await m.call("document_list", {})).get("documents") or []
    doc = [d["doc"] for d in docs if d["label"] == "TC0604"][0]
    t = await m.call("query_tree_summary", {"doc": doc, "depth": 2})
    log.check("pre: labels PadA/PadB intact after Ctrl+Z, both visible", '"label": "PadB"' in json.dumps(sc(t)) and vis(t, "PadB") is True and vis(t, "PadA") is True, "")
    mp = await m.call("query_mass_properties", {"doc": doc, "object": "PadB"})
    log.note(f"PadB volume after undo (expect 6000): {sc(mp).get('volume')}")
    r0, _ = await render(m, doc, None, "tc-06-06-default-before.png")
    log.note(f"default before: {objs(r0)}")
    ok, how = await toggle(m, doc, log, False, "hide")
    pid, win = ids()
    vsr = cua("verify_state", {"pid": pid, "window_id": win, "expect": [{"element": {"selector": {"label_contains": "PadB"}, "exists": True}}]})
    log.check("hide landed: verify_state label_contains PadB satisfied", vsr.get("status") == "satisfied", json.dumps(vsr)[:300])
    log.check(f"bridge sees PadB visibility false (route: {how})", ok, how)
    r1, _ = await render(m, doc, None, "tc-06-06-default-hidden.png")
    r2, _ = await render(m, doc, {"include": ["PadB"]}, "tc-06-06-include-PadB.png")
    log.check("post-hide default render lacks PadB", "PadB" not in (objs(r1) or []), objs(r1))
    log.check("explicit include PadB == ['PadB'] + link", objs(r2) == ["PadB"] and bool(link(r2)), objs(r2))
    fit = await m.call("view_fit_viewport", {"doc": doc})
    log.note(f"fit before hidden.png: {short(fit, 300)}")
    time.sleep(1.0)
    log.note(f"hidden shot: {shot('tc-06-06-hidden.png')}")
    ok2, how2 = await toggle(m, doc, log, True, "restore")
    log.check(f"restored: PadB visibility true (route: {how2})", ok2, how2)
    r3, _ = await render(m, doc, None, "tc-06-06-default-restored.png")
    log.check("restored default render lists PadB again", "PadB" in (objs(r3) or []), objs(r3))
    fit = await m.call("view_fit_viewport", {"doc": doc})
    log.check("visual: view_fit_viewport returns OK", fit.get("status") == "OK", short(fit, 300))
    time.sleep(1.0)
    log.note(f"after shot: {shot('tc-06-06-after.png')}")

go("tc-06-06b", body)
