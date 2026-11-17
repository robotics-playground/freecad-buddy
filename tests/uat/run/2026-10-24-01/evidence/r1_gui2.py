"""GUI actions for phase P2 on the single running FreeCAD, in addition to p1_gui.py.

    p2_gui.py frame                    set the main window to the runner frame (1600 x 1000 at 0,0)
    p2_gui.py tree [<text>]            list TreeItem elements (token, label, frame), filtered by text
    p2_gui.py clicktree "<label>"      click the first TreeItem whose label equals <label>
    p2_gui.py ctxmenu "<tree label>" "<menu item>"
                                       right-click a TreeItem, click an item of its context menu,
                                       then Escape any popup left open
    p2_gui.py key <key>               press_key to the pid (goes to its current focus)
    p2_gui.py menu A B C               invoke_menu on the path
    p2_gui.py title                    print the main window title
    p2_gui.py verify '<expect json>'   verify_state on the main window
    p2_gui.py exit                     File > Exit, wait for the process to end, write the end time
                                       into the matching launch-log.tsv line

The FreeCAD is the single running one; its main window is the largest on-screen window.
"""

import json
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "runner"))

import capture  # noqa: E402
import launch  # noqa: E402

EVIDENCE = Path(__file__).resolve().parent


def elements(pid, window_id):
    return capture.cua("get_window_state", {"pid": pid, "window_id": window_id,
                                            "include_screenshot": False})["elements"]


def end_in_launch_log(pid):
    log = EVIDENCE / "launch-log.tsv"
    end = datetime.now().astimezone().isoformat()
    lines = []
    for line in log.read_text(encoding="utf-8").splitlines():
        cells = line.split("\t")
        if len(cells) >= 6 and cells[2] == str(pid) and cells[5] == "":
            cells[5] = end
            line = "\t".join(cells)
        lines.append(line)
    log.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return end


def main():
    pid = launch.running_freecad_pids()[0]
    main_id = capture.main_window(pid)["window_id"]
    action, rest = sys.argv[1], sys.argv[2:]
    if action == "frame":
        capture.set_frame(pid, main_id)
        print(capture.window_bounds(pid, main_id))
    elif action in ("tree", "clicktree"):
        needle = rest[0] if rest else ""
        # Property editor rows are TreeItems too; model tree rows sit above them, so walk by y.
        for element in sorted(elements(pid, main_id), key=lambda e: (e.get("frame") or {}).get("y", 0)):
            if element.get("role") != "TreeItem":
                continue
            label = (element.get("label") or "").strip()
            if action == "tree" and needle.lower() in label.lower():
                print(element["element_token"], repr(label)[:120], element.get("frame"))
            elif action == "clicktree" and label == needle:
                print(json.dumps(capture.cua("click", {"pid": pid, "window_id": main_id,
                                                       "element_token": element["element_token"]}))[:400])
                break
        else:
            if action == "clicktree":
                raise SystemExit(f"no TreeItem labelled {needle!r}")
    elif action == "ctxmenu":
        # Background Space to the tree is dropped (delivery_failed); the tree item's context menu
        # reaches Std_ToggleVisibility instead. A UIA-invoked menu item leaves the popup open.
        # The property editor also has TreeItem rows ("Pad" group); the model tree is the one
        # above it, so take the matching item nearest the top.
        item = min((e for e in elements(pid, main_id)
                    if e.get("role") == "TreeItem" and (e.get("label") or "").strip() == rest[0]),
                   key=lambda e: e["frame"]["y"])
        print(json.dumps(capture.cua("right_click", {"pid": pid, "window_id": main_id,
                                                     "element_token": item["element_token"]}))[:300])
        entry = None
        for _ in range(20):
            time.sleep(0.3)
            popups = [w for w in capture.cua("list_windows", {"pid": pid})["windows"] if w["window_id"] != main_id]
            for popup in popups:
                entry = next((e for e in elements(pid, popup["window_id"])
                              if e.get("role") == "MenuItem" and (e.get("label") or "").strip() == rest[1]), None)
                if entry:
                    break
            if entry:
                break
        if entry is None:
            raise SystemExit(f"no context menu item {rest[1]!r}")
        print(json.dumps(capture.cua("click", {"pid": pid, "window_id": popup["window_id"],
                                               "element_token": entry["element_token"]}))[:300])
        for window in capture.cua("list_windows", {"pid": pid})["windows"]:
            if window["window_id"] != main_id:
                try:
                    capture.cua("press_key", {"pid": pid, "window_id": window["window_id"], "key": "escape"})
                except capture.CuaError as exc:
                    print(f"escape: {exc}"[:200])
    elif action == "key":
        print(json.dumps(capture.cua("press_key", {"pid": pid, "window_id": main_id, "key": rest[0]}))[:400])
    elif action == "menu":
        print(json.dumps(capture.cua("invoke_menu", {"pid": pid, "window_id": main_id, "path": rest}))[:400])
    elif action == "title":
        print(next(w["title"] for w in capture.cua("list_windows", {"pid": pid})["windows"]
                   if w["window_id"] == main_id))
    elif action == "verify":
        print(json.dumps(capture.cua("verify_state", {"pid": pid, "window_id": main_id,
                                                      "expect": json.loads(rest[0])}))[:1500])
    elif action == "exit":
        try:
            print(json.dumps(capture.cua("invoke_menu", {"pid": pid, "window_id": main_id,
                                                         "path": ["File", "Exit"]}))[:300])
        except (capture.CuaError, subprocess.TimeoutExpired) as exc:
            print(f"invoke_menu File > Exit: {exc}"[:300])
        deadline = time.monotonic() + 60
        while pid in launch.running_freecad_pids() and time.monotonic() < deadline:
            time.sleep(0.5)
        if pid in launch.running_freecad_pids():
            raise SystemExit(f"pid {pid} still running after File > Exit")
        deadline = time.monotonic() + 15
        while launch.port_held() and time.monotonic() < deadline:
            time.sleep(0.5)
        print(f"ended {end_in_launch_log(pid)} listen8765={launch.port_held()}")
        return
    print(f"pid={pid} window_id={main_id}")


if __name__ == "__main__":
    main()
