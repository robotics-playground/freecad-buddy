from tc14lib import *


async def body(m, log):
    a = await m.call("document_create", {"label": "DocA"})
    ha = sc(a).get("doc")
    log.note(f"DocA {a.get('status')} {ha} build {await m.bar(ha, 30, 20, 10)}")
    fa = await m.call("view_fit_viewport", {"doc": ha})
    log.check("Given fit DocA OK while DocA focused", fa.get("status") == "OK", fa.get("text"))
    b = await m.call("document_create", {"label": "DocB"})
    hb = sc(b).get("doc")
    log.note(f"DocB {b.get('status')} {hb} build {await m.bar(hb, 20, 20, 40)}")
    dl = await m.call("document_list", {})
    log.check("Given document_list lists both", "DocA" in json.dumps(dl) and "DocB" in json.dumps(dl), dl.get("text"))
    pid, win = ids()
    titles = [w["title"] for w in cua("list_windows", {"pid": pid}).get("windows", [])]
    log.check("Given active window title names DocB", any("DocB" in t for t in titles), titles)
    fb = await m.call("view_fit_viewport", {"doc": hb})
    log.check("Given fit DocB OK", fb.get("status") == "OK", fb.get("text"))
    t0 = await m.call("query_tree_summary", {"doc": hb})
    ratio_before = fr(t0).get("ratio")
    log.note(f"ratio_before {fr(t0)}")
    shot("tc-14-06-before.png")
    bad = await m.call("view_fit_viewport", {"doc": ha})
    msg = (bad.get("detail") or {}).get("message", "")
    log.note(f"wrong-doc fit -> {bad.get('status')} {bad.get('detail')}")
    log.check("Then status INVALID_INPUT", bad.get("status") == "INVALID_INPUT", bad.get("status"))
    log.check("Then message names both DocA and DocB", "DocA" in msg and "DocB" in msg, msg)
    expected = ("the live viewport is showing 'DocB', not the targeted 'DocA'; call view_fit_viewport with the "
                "handle for 'DocB', or open a 3D view for 'DocA'")
    log.check("Then message states the remedy verbatim", expected in msg, msg)
    log.check("Then refusal is not 'no live 3D view'", "no live 3D view" not in msg, msg)
    t1 = await m.call("query_tree_summary", {"doc": hb})
    log.check("Then DocB ratio unchanged", fr(t1).get("ratio") == ratio_before, f"{fr(t1)} vs {ratio_before}")
    titles = [w["title"] for w in cua("list_windows", {"pid": pid}).get("windows", [])]
    log.check("Then window title still names DocB", any("DocB" in t for t in titles), titles)
    shot("tc-14-06-after.png")
    log.write({"handles": {"DocA": ha, "DocB": hb}})
    print("HANDLES", ha, hb)


go("tc-14-06", body)
