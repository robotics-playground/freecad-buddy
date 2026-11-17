"""Right-click the topmost TreeItem labelled <tree label>, wait up to 10 s for its context menu to list
<menu item>, click it, then Escape any popup left open: p5_ctx.py "<tree label>" "<menu item>".
A slower variant of p2_gui.py ctxmenu: the menu window can appear before its items are in the UIA tree."""
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "runner"))
import capture  # noqa: E402
import launch  # noqa: E402

pid = launch.running_freecad_pids()[0]
wid = capture.main_window(pid)["window_id"]
label, wanted = sys.argv[1], sys.argv[2]
state = capture.cua("get_window_state", {"pid": pid, "window_id": wid, "include_screenshot": False})
item = min((e for e in state["elements"] if e.get("role") == "TreeItem" and (e.get("label") or "").strip() == label),
           key=lambda e: e["frame"]["y"])
print(json.dumps(capture.cua("right_click", {"pid": pid, "window_id": wid, "element_token": item["element_token"]})))
entry = popup = None
deadline = time.monotonic() + 10
while entry is None and time.monotonic() < deadline:
    time.sleep(0.5)
    for popup in [w for w in capture.cua("list_windows", {"pid": pid})["windows"] if w["window_id"] != wid]:
        elements = capture.cua("get_window_state", {"pid": pid, "window_id": popup["window_id"],
                                                    "include_screenshot": False})["elements"]
        entry = next((e for e in elements if e.get("role") == "MenuItem" and (e.get("label") or "").strip() == wanted), None)
        if entry:
            break
if entry is None:
    raise SystemExit(f"no context menu item {wanted!r}")
print(json.dumps(capture.cua("click", {"pid": pid, "window_id": popup["window_id"], "element_token": entry["element_token"]})))
for _ in range(4):
    if not [w for w in capture.cua("list_windows", {"pid": pid})["windows"] if w["window_id"] != wid]:
        break
    capture.cua("press_key", {"pid": pid, "window_id": wid, "key": "escape"})
