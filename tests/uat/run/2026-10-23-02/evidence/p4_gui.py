"""GUI actions for phase P4, in addition to p1_gui.py / p2_gui.py.

    p4_gui.py tab "<text>"    click the first document tab (TabItem) whose label contains <text>
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "runner"))

import capture  # noqa: E402
import launch  # noqa: E402


def main():
    pid = launch.running_freecad_pids()[0]
    main_id = capture.main_window(pid)["window_id"]
    action, rest = sys.argv[1], sys.argv[2:]
    if action == "tab":
        state = capture.cua("get_window_state", {"pid": pid, "window_id": main_id, "include_screenshot": False})
        tabs = [e for e in state["elements"] if e.get("role") in ("TabItem", "Tab") ]
        for tab in tabs:
            print(tab["element_token"], repr(tab.get("label")), tab.get("frame"))
        target = next(t for t in tabs if rest[0] in (t.get("label") or ""))
        print(json.dumps(capture.cua("click", {"pid": pid, "window_id": main_id,
                                               "element_token": target["element_token"]}))[:300])
    print(f"pid={pid} window_id={main_id}")


if __name__ == "__main__":
    main()
