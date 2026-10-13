"""Window geometry, menu commands and window captures through the ``cua-driver`` CLI."""

import json
import subprocess

CUA_DRIVER = "cua-driver"
CUA_TIMEOUT_S = 60.0
# Desktop pixels. A fixed frame gives every capture of a run the same view size; it must fit the
# smallest monitor the suite runs on.
WINDOW_FRAME = {"x": 0, "y": 0, "width": 1600, "height": 1000}
# Only non-modal commands: a modal dialog blocks invoke_menu and keeps the UIA provider busy
# (freecad-gui-e2e-harness.md, Drive the GUI).
MENU_ALLOW_LIST = (
    ("View", "Visibility", "Show All Objects"),
    ("Edit", "Recompute"),
)


class CuaError(Exception):
    pass


def cua(tool, payload):
    """Run one ``cua-driver call`` with ``payload`` on stdin; return its JSON answer.

    JSON goes on stdin because the positional form does not parse Windows backslashes.
    """
    completed = subprocess.run(
        [CUA_DRIVER, "call", tool],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=CUA_TIMEOUT_S,
    )
    if completed.returncode != 0:
        raise CuaError(f"{tool} exited {completed.returncode}: {completed.stderr.strip()}")
    try:
        answer = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise CuaError(f"{tool} answered no JSON: {completed.stdout.strip()[:200]}") from exc
    # A refusal such as menu_path_unavailable exits 0 with "status": "refused", not isError.
    if isinstance(answer, dict) and (answer.get("isError") or answer.get("status") == "refused"):
        raise CuaError(f"{tool} refused: {completed.stdout.strip()[:500]}")
    return answer


def main_window(pid):
    """The largest on-screen window of ``pid``: the main window, not the splash or a tool tip."""
    windows = [
        window
        for window in cua("list_windows", {"pid": pid})["windows"]
        if window["is_on_screen"] and not window["minimized"]
    ]
    if not windows:
        raise CuaError(f"pid {pid} has no on-screen window")
    return max(windows, key=lambda w: w["bounds"]["width"] * w["bounds"]["height"])


def set_frame(pid, window_id):
    cua("set_window_frame", {"pid": pid, "window_id": window_id, **WINDOW_FRAME})


def window_bounds(pid, window_id):
    for window in cua("list_windows", {"pid": pid})["windows"]:
        if window["window_id"] == window_id:
            return window["bounds"]
    raise CuaError(f"window {window_id} of pid {pid} is gone")


def capture(pid, window_id, out_file):
    """Write a PNG of the window to ``out_file``; return the window bounds it was taken at."""
    bounds = window_bounds(pid, window_id)
    cua(
        "get_window_state",
        {
            "pid": pid,
            "window_id": window_id,
            "include_accessibility_tree": False,
            "screenshot_out_file": str(out_file),
        },
    )
    return bounds


def invoke_menu(pid, window_id, path):
    if tuple(path) not in MENU_ALLOW_LIST:
        raise ValueError(f"menu path {list(path)} is not in the allow-list {MENU_ALLOW_LIST}")
    cua("invoke_menu", {"pid": pid, "window_id": window_id, "path": list(path)})
