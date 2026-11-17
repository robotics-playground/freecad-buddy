"""GUI actions for phase R2 (from 2026-10-23-02 p5_gui.py), in addition to p1_gui.py / p2_gui.py.

    r2_gui5.py find "<text>"                 list elements of the main window whose label contains <text>
    r2_gui5.py click "<label>" [<stem>]      fresh snapshot (its screenshot to evidence/<stem>.png when given),
                                            then click the first enabled element whose label equals <label>
    r2_gui5.py dblclicktree "<label>"        double-click the topmost TreeItem whose label equals <label>
    r2_gui5.py popup "<item>"                click a MenuItem labelled <item> in any open popup window of the pid
    r2_gui5.py popups                        list MenuItems of every popup window of the pid
    r2_gui5.py escape                        Escape to the main window until no popup window is left (max 4)
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


def popups(pid, main_id):
    return [w for w in capture.cua("list_windows", {"pid": pid})["windows"] if w["window_id"] != main_id]


def main():
    pid = launch.running_freecad_pids()[0]
    main_id = capture.main_window(pid)["window_id"]
    action, rest = sys.argv[1], sys.argv[2:]
    if action == "find":
        for e in state(pid, main_id)["elements"]:
            if rest[0].lower() in (e.get("label") or "").lower():
                print(e["element_token"], e.get("role"), repr(e.get("label")), e.get("enabled"), e.get("frame"),
                      e.get("actions"))
    elif action == "click":
        elements = state(pid, main_id, rest[1] if len(rest) > 1 else None)["elements"]
        target = next(e for e in elements if (e.get("label") or "").strip() == rest[0] and e.get("enabled", True))
        print(json.dumps(capture.cua("click", {"pid": pid, "window_id": main_id,
                                               "element_token": target["element_token"]}))[:400])
    elif action == "dblclicktree":
        item = min((e for e in state(pid, main_id)["elements"]
                    if e.get("role") == "TreeItem" and (e.get("label") or "").strip() == rest[0]),
                   key=lambda e: e["frame"]["y"])
        print(json.dumps(capture.cua("double_click", {"pid": pid, "window_id": main_id,
                                                      "element_token": item["element_token"]}))[:400])
    elif action in ("popup", "popups"):
        for window in popups(pid, main_id):
            items = [e for e in state(pid, window["window_id"])["elements"] if e.get("role") == "MenuItem"]
            if action == "popups":
                print(window["window_id"], window["title"], window["bounds"])
                for e in items:
                    print("   ", repr(e.get("label")), e.get("enabled"))
                continue
            entry = next((e for e in items if (e.get("label") or "").strip() == rest[0]), None)
            if entry:
                print(json.dumps(capture.cua("click", {"pid": pid, "window_id": window["window_id"],
                                                       "element_token": entry["element_token"]}))[:400])
                break
        else:
            if action == "popup":
                raise SystemExit(f"no popup MenuItem {rest[0]!r}")
    elif action == "escape":
        for _ in range(4):
            if not popups(pid, main_id):
                break
            capture.cua("press_key", {"pid": pid, "window_id": main_id, "key": "escape"})
        print("popups left:", [(w["window_id"], w["title"]) for w in popups(pid, main_id)])
    print(f"pid={pid} window_id={main_id}")


if __name__ == "__main__":
    main()
