"""GUI actions for phase P10 (TC-12), in addition to p1_gui.py / p2_gui.py / p5_gui.py.

    p10_gui.py els "<text>" [<role>]       fresh snapshot; list elements whose label contains <text>
                                           (role filter optional): token, role, label, enabled, frame
    p10_gui.py menubar                     fresh snapshot; the MenuItem labels the menu bar exposes
    p10_gui.py click "<label>" [<role>] [--right|--double]
                                           fresh snapshot, then click the topmost enabled element whose
                                           label equals <label> (and role), by element_token
    p10_gui.py px <x> <y> [count] [--right] background pixel click on the main window
    p10_gui.py type "<label>" [<role>] "<text>"
                                           fresh snapshot, type_text into the element by element_token
    p10_gui.py key <key> [modifier ...]    press_key / hotkey to the pid
    p10_gui.py snap <stem>                 get_window_state with the tree to evidence/<stem>-tree.json and
                                           its screenshot to evidence/<stem>.png
    p10_gui.py winstate <window_id> <stem> get_window_state of another window of the pid (popup, dialog)
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "runner"))

import capture  # noqa: E402
import launch  # noqa: E402

EVIDENCE = Path(__file__).resolve().parent


def state(pid, window_id, stem=None):
    payload = {"pid": pid, "window_id": window_id}
    if stem:
        payload["screenshot_out_file"] = str(EVIDENCE / f"{stem}.png")
    else:
        payload["include_screenshot"] = False
    return capture.cua("get_window_state", payload)


def pick(elements, label, role):
    found = [e for e in elements if (e.get("label") or "").strip() == label and e.get("enabled", True)
             and (role is None or e.get("role") == role)]
    if not found:
        raise SystemExit(f"no enabled element {label!r} role={role}")
    return min(found, key=lambda e: (e.get("frame") or {}).get("y", 0))


def main():
    pid = launch.running_freecad_pids()[0]
    main_id = capture.main_window(pid)["window_id"]
    flags = [a for a in sys.argv[1:] if a.startswith("--")]
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    action, rest = args[0], args[1:]
    if action == "els":
        role = rest[1] if len(rest) > 1 else None
        for e in state(pid, main_id)["elements"]:
            if rest[0].lower() in (e.get("label") or "").lower() and (role is None or e.get("role") == role):
                print(e["element_token"], e.get("role"), repr(e.get("label"))[:100], e.get("enabled"),
                      e.get("frame"), e.get("selected", ""))
    elif action == "menubar":
        print([e.get("label") for e in state(pid, main_id)["elements"] if e.get("role") == "MenuItem"])
    elif action == "click":
        role = rest[1] if len(rest) > 1 else None
        target = pick(state(pid, main_id)["elements"], rest[0], role)
        tool = "right_click" if "--right" in flags else "double_click" if "--double" in flags else "click"
        print(json.dumps(capture.cua(tool, {"pid": pid, "window_id": main_id,
                                            "element_token": target["element_token"]}))[:500])
    elif action == "px":
        payload = {"pid": pid, "window_id": main_id, "x": int(rest[0]), "y": int(rest[1])}
        if len(rest) > 2:
            payload["count"] = int(rest[2])
        tool = "right_click" if "--right" in flags else "click"
        print(json.dumps(capture.cua(tool, payload))[:500])
    elif action == "type":
        role = rest[1] if len(rest) > 2 else None
        target = pick(state(pid, main_id)["elements"], rest[0], role)
        print(json.dumps(capture.cua("type_text", {"pid": pid, "window_id": main_id, "text": rest[-1],
                                                   "element_token": target["element_token"]}))[:500])
    elif action == "key":
        if len(rest) > 1:
            print(json.dumps(capture.cua("hotkey", {"pid": pid, "window_id": main_id, "keys": rest[1:] + rest[:1]}))[:400])
        else:
            print(json.dumps(capture.cua("press_key", {"pid": pid, "window_id": main_id, "key": rest[0]}))[:400])
    elif action == "snap":
        snapshot = state(pid, main_id, rest[0])
        (EVIDENCE / f"{rest[0]}-tree.json").write_text(json.dumps(snapshot, indent=1), encoding="utf-8")
        print(f"elements={len(snapshot['elements'])} degraded={snapshot.get('degraded')}")
    elif action == "winstate":
        snapshot = state(pid, int(rest[0]), rest[1])
        (EVIDENCE / f"{rest[1]}-tree.json").write_text(json.dumps(snapshot, indent=1), encoding="utf-8")
        for e in snapshot["elements"]:
            print(e["element_token"], e.get("role"), repr(e.get("label"))[:100], e.get("enabled"))
    print(f"pid={pid} window_id={main_id}")


if __name__ == "__main__":
    main()
