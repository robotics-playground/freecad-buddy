from tc14lib import *


def frame():
    pid, win = ids()
    for w in cua("list_windows", {"pid": pid}).get("windows", []):
        if w["window_id"] == win:
            return w["bounds"]


async def body(m, log):
    o = await m.call("document_open", {"path": BOX})
    h = sc(o).get("doc")
    log.note(f"show all {menu(['View', 'Visibility', 'Show All Objects'])}")
    f = await m.call("view_fit_viewport", {"doc": h})
    t0 = await m.call("query_tree_summary", {"doc": h})
    log.check("Given fit OK and fits true", f.get("status") == "OK" and fr(t0).get("fits") is True, fr(t0))
    ratio_before = fr(t0).get("ratio")
    orig = frame()
    log.note(f"orig frame {orig}; ratio_before {ratio_before}")
    shot("tc-14-13-before.png")
    t1 = await m.call("query_tree_summary", {"doc": h})
    log.check("Then second identical read is cached", fr(t1).get("checked") == "cached", fr(t1))
    log.check("Then cached stale_reason names geometry", "geometry" in (fr(t1).get("stale_reason") or ""), fr(t1).get("stale_reason"))
    pid, win = ids()
    sf = cua("set_window_frame", {"pid": pid, "window_id": win, "x": orig["x"], "y": orig["y"], "width": 640, "height": 400})
    log.note(f"set_window_frame -> {json.dumps(sf)[:300]}")
    time.sleep(1.5)
    new = frame()
    log.check("Then list_windows reports 640x400", new and new["width"] == 640 and new["height"] == 400, new)
    t2 = await m.call("query_tree_summary", {"doc": h})
    log.note(f"third read {fr(t2)}")
    log.check("Then resize invalidates cache (computed)", fr(t2).get("checked") == "computed", fr(t2))
    r2 = fr(t2).get("ratio")
    log.check("Then ratio larger than ratio_before", isinstance(r2, float) and r2 > ratio_before, f"{r2} vs {ratio_before}")
    shot("tc-14-13-after.png")
    sb = cua("set_window_frame", {"pid": pid, "window_id": win, "x": orig["x"], "y": orig["y"],
                                  "width": orig["width"], "height": orig["height"]})
    time.sleep(1.5)
    log.note(f"restore -> {json.dumps(sb)[:200]}; frame now {frame()}")
    print("HANDLE", h)


go("tc-14-13", body)
