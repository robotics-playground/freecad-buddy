"""Foreground cua-driver actions for phase R3 (tree-row select and keys, which background delivery
drops on FreeCAD 1.1.4; lead log W6). After each action the real pointer is moved outside the
FreeCAD window (move_cursor scope desktop to 2480,700).

    r3_fg.py clicktree "<label>"     foreground click on the topmost TreeItem with that label
    r3_fg.py clickel "<label>" <role> [action]   foreground click on the topmost enabled element
    r3_fg.py px <x> <y>              foreground pixel click (window-local screenshot pixels)
    r3_fg.py key <key>               foreground press_key to the main window
"""

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "runner"))

import capture  # noqa: E402
import launch  # noqa: E402


def main():
    pid = launch.running_freecad_pids()[0]
    main_id = capture.main_window(pid)["window_id"]
    action, rest = sys.argv[1], sys.argv[2:]
    if action == "clicktree":
        elements = capture.cua("get_window_state", {"pid": pid, "window_id": main_id,
                                                    "include_screenshot": False})["elements"]
        item = min((e for e in elements if e.get("role") == "TreeItem" and (e.get("label") or "").strip() == rest[0]),
                   key=lambda e: e["frame"]["y"])
        print(json.dumps(capture.cua("click", {"pid": pid, "window_id": main_id, "element_token": item["element_token"],
                                               "delivery_mode": "foreground"}))[:400])
    elif action == "clickel":
        elements = capture.cua("get_window_state", {"pid": pid, "window_id": main_id,
                                                    "include_screenshot": False})["elements"]
        item = min((e for e in elements if e.get("role") == rest[1] and (e.get("label") or "").strip() == rest[0]
                    and e.get("enabled", True)), key=lambda e: e["frame"]["y"])
        extra = {"action": rest[2]} if len(rest) > 2 else {}
        print(json.dumps(capture.cua("click", {"pid": pid, "window_id": main_id, "element_token": item["element_token"],
                                               "delivery_mode": "foreground", **extra}))[:400])
    elif action == "px":
        print(json.dumps(capture.cua("click", {"pid": pid, "window_id": main_id, "x": int(rest[0]), "y": int(rest[1]),
                                               "delivery_mode": "foreground"}))[:400])
    elif action == "key":
        print(json.dumps(capture.cua("press_key", {"pid": pid, "window_id": main_id, "key": rest[0],
                                                   "delivery_mode": "foreground"}))[:400])
    print(json.dumps(capture.cua("move_cursor", {"x": 2480, "y": 700, "scope": "desktop"}))[:200])
    time.sleep(1)


if __name__ == "__main__":
    main()
