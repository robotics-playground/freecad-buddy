"""TC-06-02 GUI side: set each standard view with FreeCAD's own controls, Fit All, capture.

Standard Views toolbar button (main action = viewIsometric). Its dropdown arrow does not open under
cua-driver (background click routes to UIA Invoke; foreground click opens nothing), and
invoke_menu ['View','Standard Views',<leaf>] is refused at segment 2. The other six views therefore
go through FreeCAD's NaviCube (pixel clicks on its faces and arrows), which is FreeCAD's own GUI code.
"""
import sys, time
from tc06lib import *

FACE = {"TOP": (1487, 272), "FRONT": (1462, 318), "RIGHT": (1512, 318)}
ARROW = {"left": (1421, 300), "right": (1553, 300), "up": (1487, 237), "down": (1487, 366)}


def px(x, y):
    pid, win = ids()
    r = cua("click", {"pid": pid, "window_id": win, "x": x, "y": y})
    time.sleep(1.5)
    return {"xy": [x, y], "effect": r.get("effect"), "route": r.get("route")}


def iso():
    r = click_button("Standard Views")
    time.sleep(1.0)
    return r


steps = {
    "iso": [("btn", None)],
    "front": [("btn", None), ("face", "FRONT")],
    "top": [("btn", None), ("face", "TOP")],
    "right": [("btn", None), ("face", "RIGHT")],
    # one NaviCube arrow click turns the view 45 degrees (observed: one click from FRONT shows the LEFT|FRONT edge)
    "left": [("btn", None), ("face", "FRONT"), ("arrow", "right"), ("arrow", "right")],
    "back": [("btn", None), ("face", "FRONT")] + [("arrow", "right")] * 4,
    "bottom": [("btn", None), ("face", "FRONT"), ("arrow", sys.argv[2] if len(sys.argv) > 2 else "up"), ("arrow", sys.argv[2] if len(sys.argv) > 2 else "up")],
}
cam = sys.argv[1]
rec = []
for kind, arg in steps[cam]:
    if kind == "btn":
        rec.append({"Standard Views": iso()})
    elif kind == "face":
        rec.append({arg: px(*FACE[arg])})
    else:
        rec.append({"arrow " + arg: px(*ARROW[arg])})
rec.append({"Fit All": gui_fit()})
rec.append({"shot": shot(f"tc-06-02-{cam}-viewport.png")})
print(json.dumps(rec))
with open(EVIDENCE / "tc-06-02-gui.jsonl", "a", encoding="utf-8") as h:
    h.write(json.dumps({"camera": cam, "steps": rec}) + "\n")
