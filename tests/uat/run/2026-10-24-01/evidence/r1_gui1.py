"""GUI actions for phase P1 on the single running FreeCAD (main window = largest on-screen window).

    p1_gui.py showall          invoke_menu View > Visibility > Show All Objects, then close the
                               menu popups it leaves open (Escape to each extra window)
    p1_gui.py fitall           click the Fit All toolbar button by element_token
    p1_gui.py shot <stem>      capture the main window to evidence/<stem>.png and write every
                               top-level window of the pid to evidence/<stem>-windows.txt: a
                               window capture does not show a separate dialog or popup window
    p1_gui.py windows          print the pid's top-level windows

invoke_menu on FreeCAD 1.1.4 leaves the View menu and its Visibility submenu open as two extra
top-level windows; they do not appear in a capture of the main window.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "runner"))

import capture  # noqa: E402
import launch  # noqa: E402

EVIDENCE = Path(__file__).resolve().parent


def windows(pid):
    return capture.cua("list_windows", {"pid": pid})["windows"]


def close_popups(pid, main_id):
    # One Escape to the main window closes the innermost open menu.
    for _ in range(4):
        extra = [w for w in windows(pid) if w["window_id"] != main_id]
        if not extra:
            return
        try:
            capture.cua("press_key", {"pid": pid, "window_id": main_id, "key": "escape"})
        except capture.CuaError as exc:
            print(f"escape: {exc}"[:200])


def main():
    pid = launch.running_freecad_pids()[0]
    main_id = capture.main_window(pid)["window_id"]
    action, rest = sys.argv[1], sys.argv[2:]
    if action == "showall":
        print(json.dumps(capture.cua("invoke_menu", {"pid": pid, "window_id": main_id,
                                                     "path": ["View", "Visibility", "Show All Objects"]}))[:300])
        close_popups(pid, main_id)
    elif action == "fitall":
        state = capture.cua("get_window_state", {"pid": pid, "window_id": main_id, "include_screenshot": False})
        button = next(e for e in state["elements"] if (e.get("label") or "").strip() == "Fit All" and e.get("enabled"))
        print(json.dumps(capture.cua("click", {"pid": pid, "window_id": main_id,
                                               "element_token": button["element_token"]}))[:300])
    elif action == "shot":
        out = EVIDENCE / f"{rest[0]}.png"
        capture.capture(pid, main_id, out)
        listing = "\n".join(f"{w['window_id']}\t{w['title']}\t{w['bounds']}" for w in windows(pid))
        (EVIDENCE / f"{rest[0]}-windows.txt").write_text(listing + "\n", encoding="utf-8")
        print(out)
        print(listing)
    elif action == "windows":
        for w in windows(pid):
            print(w["window_id"], w["title"], w["bounds"])
    print(f"pid={pid} window_id={main_id}")


if __name__ == "__main__":
    main()
