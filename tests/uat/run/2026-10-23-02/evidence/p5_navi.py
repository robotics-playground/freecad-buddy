"""TC-06-02 GUI side for phase P5: set one standard view with FreeCAD's own controls, GUI Fit All,
capture to evidence/tc-06-02-<camera>-viewport.png: p5_navi.py <camera>.

The Standard Views toolbar button's main action is Isometric; its drop-down arrow does not open under
cua-driver (background click routes to UIA Invoke). The other six views go through FreeCAD's NaviCube
(pixel clicks in the 1568-wide screenshot space, window frame 1600 x 1000 at 0,0). One arrow click
turns the view 45 degrees.
"""

import json
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "runner"))

import capture  # noqa: E402
import launch  # noqa: E402

EVIDENCE = Path(__file__).resolve().parent
FACE = {"TOP": (1479, 265), "FRONT": (1450, 315), "RIGHT": (1505, 312)}
ARROW = {"left": (1406, 296), "right": (1552, 296), "up": (1479, 224), "down": (1479, 368)}
STEPS = {
    "iso": [],
    "front": [("face", "FRONT")],
    "top": [("face", "TOP")],
    "right": [("face", "RIGHT")],
    "left": [("face", "FRONT"), ("arrow", "right"), ("arrow", "right")],
    "back": [("face", "FRONT")] + [("arrow", "right")] * 4,
    "bottom": [("face", "FRONT"), ("arrow", "up"), ("arrow", "up")],
}


def click_label(pid, wid, label):
    state = capture.cua("get_window_state", {"pid": pid, "window_id": wid, "include_screenshot": False})
    button = next(e for e in state["elements"] if (e.get("label") or "").strip() == label and e.get("enabled"))
    return capture.cua("click", {"pid": pid, "window_id": wid, "element_token": button["element_token"]})


def main():
    camera = sys.argv[1]
    pid = launch.running_freecad_pids()[0]
    wid = capture.main_window(pid)["window_id"]
    record = [{"Standard Views": click_label(pid, wid, "Standard Views")}]
    time.sleep(1.0)
    for kind, name in STEPS[camera]:
        x, y = (FACE if kind == "face" else ARROW)[name]
        result = capture.cua("click", {"pid": pid, "window_id": wid, "x": x, "y": y})
        record.append({f"{kind} {name}": [x, y, result.get("effect"), result.get("route")]})
        time.sleep(1.5)
    record.append({"Fit All": click_label(pid, wid, "Fit All")})
    time.sleep(1.0)
    stem = f"tc-06-02-{camera}-viewport"
    subprocess.run([sys.executable, str(EVIDENCE / "p1_gui.py"), "shot", stem], check=True)
    with (EVIDENCE / "tc-06-02-gui.jsonl").open("a", encoding="utf-8") as log:
        log.write(json.dumps({"camera": camera, "steps": record}) + "\n")
    print(json.dumps(record))


if __name__ == "__main__":
    main()
