from tc14lib import *


async def body(m, log):
    o = await m.call("document_open", {"path": BOX})
    h = sc(o).get("doc")
    menu(["View", "Visibility", "Show All Objects"])
    f = await m.call("view_fit_viewport", {"doc": h})
    log.note(f"fit {f.get('status')} {fr(f)}")
    pid, win = ids()
    cua("set_window_frame", {"pid": pid, "window_id": win, "x": 0, "y": 0, "width": 640, "height": 400})
    time.sleep(1.5)
    q = await m.call("query_tree_summary", {"doc": h})
    log.note(f"small-window framing {fr(q)}")
    f2 = await m.call("view_fit_viewport", {"doc": h})
    log.note(f"fit in small window {f2.get('status')} {sc(f2)} {fr(f2)}")
    shot("tc-14-13-repro-small-after-fit.png")
    cua("set_window_frame", {"pid": pid, "window_id": win, "x": 0, "y": 0, "width": 1775, "height": 1380})
    time.sleep(1.5)
    await m.call("document_close", {"doc": h})


go("tc-14-13-repro", body)
