"""GUI helper for UAT run 2026-10-03-04: FreeCAD's own Fit All, and window captures.

Usage (uv run python gui.py ...):
    fitall                 click the "Fit All" toolbar button by element_token (fresh snapshot)
    shot <name.png>        capture the FreeCAD main window to $RUN_DIR/evidence/<name.png>
    fitshot <name.png>     fitall, short wait, then shot
    view <iso|front|top|right>   click the matching standard-view toolbar button, if present
    click <label>          click the toolbar Button with that exact label
    buttons [substr]       list Button labels in the current snapshot (debug)

PID / WIN come from env FC_PID / FC_WIN, else from evidence/fc.json.
Only cua-driver touches the window; nothing here imports freecad_buddy.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

EVIDENCE = Path(__file__).resolve().parent


def _ids() -> tuple[int, int]:
    if os.environ.get("FC_PID") and os.environ.get("FC_WIN"):
        return int(os.environ["FC_PID"]), int(os.environ["FC_WIN"])
    data = json.loads((EVIDENCE / "fc.json").read_text())
    return int(data["pid"]), int(data["window_id"])


def _cua(tool: str, payload: dict) -> dict:
    out = subprocess.run(
        ["cua-driver", tool], input=json.dumps(payload), capture_output=True, text=True, timeout=60
    )
    try:
        return json.loads(out.stdout)
    except json.JSONDecodeError:
        return {"_raw": out.stdout, "_err": out.stderr}


def _snapshot() -> dict:
    pid, win = _ids()
    return _cua("get_window_state", {"pid": pid, "window_id": win, "include_screenshot": False})


def _click_label(label: str) -> dict:
    state = _snapshot()
    for element in state.get("elements", []):
        if element.get("role") == "Button" and element.get("label") == label:
            pid, _ = _ids()
            return _cua("click", {"pid": pid, "element_token": element["element_token"]})
    return {"error": f"no Button labelled {label!r} in snapshot", "count": state.get("element_count")}


def shot(name: str) -> dict:
    pid, win = _ids()
    path = str(EVIDENCE / name).replace("\\", "/")
    _cua("get_window_state", {"pid": pid, "window_id": win, "screenshot_out_file": path})
    return {"file": path, "exists": Path(path).exists()}


def main() -> int:
    command, *rest = sys.argv[1:] or ["help"]
    if command == "fitall":
        print(json.dumps(_click_label("Fit All")))
    elif command == "shot":
        print(json.dumps(shot(rest[0])))
    elif command == "fitshot":
        print(json.dumps(_click_label("Fit All")))
        time.sleep(1.0)
        print(json.dumps(shot(rest[0])))
    elif command == "view":
        labels = {"iso": "Isometric", "front": "Front", "top": "Top", "right": "Right"}
        print(json.dumps(_click_label(labels[rest[0]])))
    elif command == "click":
        print(json.dumps(_click_label(rest[0])))
    elif command == "buttons":
        needle = rest[0] if rest else ""
        for element in _snapshot().get("elements", []):
            label = element.get("label") or ""
            if element.get("role") == "Button" and needle.lower() in label.lower():
                print(element["element_token"], repr(label), element.get("frame"))
    else:
        print(__doc__)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
