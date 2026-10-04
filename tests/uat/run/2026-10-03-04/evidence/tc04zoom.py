"""FreeCAD's own View > Zoom actions through UIA (cua-driver), plus Box Zoom by a pixel drag."""
import sys
import time

from tc03lib import cua, ids, shot


def _popup(pid, main, exclude=()):
    for w in cua("list_windows", {"pid": pid}).get("windows", []):
        if w["window_id"] != main and w["window_id"] not in exclude:
            return w["window_id"]
    return None


def _token(pid, win, label):
    st = cua("get_window_state", {"pid": pid, "window_id": win, "include_screenshot": False})
    for e in st.get("elements", []):
        if e.get("label") == label:
            return e["element_token"]
    return None


def zoom_action(label):
    pid, win = ids()
    cua("invoke_menu", {"pid": pid, "window_id": win, "path": ["View", "Zoom"]})
    time.sleep(0.8)
    view_menu = _popup(pid, win)
    if not view_menu:
        return "no View popup"
    cua("click", {"pid": pid, "element_token": _token(pid, view_menu, "Zoom"), "action": "expand"})
    time.sleep(0.8)
    sub = _popup(pid, win, exclude=(view_menu,))
    if not sub:
        return "no Zoom submenu"
    r = cua("click", {"pid": pid, "element_token": _token(pid, sub, label)})
    time.sleep(0.8)
    for w in cua("list_windows", {"pid": pid}).get("windows", []):
        if w["window_id"] != win:
            cua("press_key", {"pid": pid, "window_id": w["window_id"], "key": "escape"})
    return r.get("effect")


def box_zoom(x1, y1, x2, y2):
    pid, win = ids()
    first = zoom_action("Box Zoom")
    time.sleep(0.5)
    r = cua("drag", {"pid": pid, "window_id": win, "from_x": x1, "from_y": y1, "to_x": x2, "to_y": y2})
    time.sleep(1.0)
    return first, r


if __name__ == "__main__":
    cmd = sys.argv[1]
    if cmd == "in":
        print([zoom_action("Zoom In") for _ in range(int(sys.argv[2]))])
    elif cmd == "box":
        print(box_zoom(*[int(v) for v in sys.argv[2:6]]))
    if sys.argv[-1].endswith(".png"):
        print(shot(sys.argv[-1]))
