"""GUI actions through cua-driver on the running FreeCAD, for the §9 agent follow-ups.

    p0_gui.py fitall                 click the Fit All toolbar button by element_token
    p0_gui.py click "<label>"        click the first enabled element whose label equals <label>
    p0_gui.py find "<text>"          list elements whose label contains <text>
    p0_gui.py menu A B C             invoke_menu on the path
    p0_gui.py shot <file stem>       capture the window to evidence/<stem>.png

The FreeCAD is the single running one; its main window is the largest on-screen window.
"""

import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "runner"))

import capture  # noqa: E402
import launch  # noqa: E402

EVIDENCE = Path(__file__).resolve().parent


def state(pid, window_id):
    completed = subprocess.run(
        [capture.CUA_DRIVER, "call", "get_window_state"],
        input=json.dumps({"pid": pid, "window_id": window_id, "include_screenshot": False}),
        capture_output=True, text=True, encoding="utf-8", timeout=60,
    )
    return json.loads(completed.stdout)["elements"]


def click_label(pid, window_id, label):
    for element in state(pid, window_id):
        if (element.get("label") or "").strip() == label and element.get("enabled"):
            answer = capture.cua("click", {"pid": pid, "window_id": window_id,
                                           "element_token": element["element_token"]})
            print(json.dumps(answer)[:400])
            return
    raise SystemExit(f"no enabled element labelled {label!r}")


def main():
    pid = launch.running_freecad_pids()[0]
    window_id = capture.main_window(pid)["window_id"]
    action, rest = sys.argv[1], sys.argv[2:]
    if action == "fitall":
        click_label(pid, window_id, "Fit All")
    elif action == "click":
        click_label(pid, window_id, rest[0])
    elif action == "find":
        for element in state(pid, window_id):
            if rest[0].lower() in (element.get("label") or "").lower():
                print(element["element_token"], element.get("role"), element.get("enabled"),
                      repr(element.get("label"))[:120], element.get("frame"))
    elif action == "expand":
        # The tree expander sits left of the item; captures are scaled by width 1568 / 1600.
        bounds = capture.window_bounds(pid, window_id)
        scale = 1568 / bounds["width"]
        for element in state(pid, window_id):
            if element.get("role") == "TreeItem" and (element.get("label") or "").strip() == rest[0]:
                frame = element["frame"]
                point = {"x": round((frame["x"] - 10) * scale), "y": round((frame["y"] + frame["h"] / 2) * scale)}
                print(json.dumps(capture.cua("click", {"pid": pid, "window_id": window_id, **point}))[:200])
                break
    elif action == "menu":
        print(json.dumps(capture.cua("invoke_menu", {"pid": pid, "window_id": window_id, "path": rest}))[:400])
    elif action == "shot":
        out = EVIDENCE / f"{rest[0]}.png"
        capture.capture(pid, window_id, out)
        print(out)
    print(f"pid={pid} window_id={window_id}")


if __name__ == "__main__":
    main()
