"""Window geometry, menu commands and window captures through the ``cua-driver`` CLI.

Runs inside the ``fcb-desktop`` container, where ``cua-driver`` is the pinned release binary.
"""

import json
import subprocess
import time

# A bare ``cua-driver`` resolves to the base image's Python wrapper in /opt/venv/bin, which fails
# as user cua (tests/close-loop/README.md).
CUA_DRIVER = "/usr/local/bin/cua-driver"
CUA_TIMEOUT_S = 60.0
MENU_ENABLE_S = 5.0
MENU_POLL_S = 0.25
MENU_UNAVAILABLE = "menu_path_unavailable"
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
    """Run one ``cua-driver call`` with ``payload`` on stdin; return its JSON answer."""
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
    """The largest on-screen window of ``pid``: the main window, not the splash or a tool tip.

    The Linux driver reports no ``minimized`` key; a minimized X11 window is not on screen.
    """
    windows = [
        window
        for window in cua("list_windows", {"pid": pid})["windows"]
        if window["is_on_screen"] and not window.get("minimized", False)
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


def _menu_leaf(elements, path):
    """The element of the menu item at ``path``, found one level at a time from the menu bar."""
    parent = None
    found = None
    for label in path:
        matches = [
            element
            for element in elements
            if element.get("role") == "menu item"
            and element.get("label") == label
            and element.get("parent_index") == parent
        ]
        if len(matches) != 1:
            raise CuaError(
                f"menu_path_unavailable: {len(matches)} menu items {label!r} under "
                f"{found.get('label') if found else 'the menu bar'!r} in {list(path)}"
            )
        found = matches[0]
        parent = found["element_index"]
    return found


# The driver's own menu-path tool refuses a Qt menu bar: its top-level items offer only ShowMenu,
# which it does not count as a safe activation (measured on 0.28.1: "menu path segment 0 has no
# safe activation action"). The leaf item offers Press, so the runner resolves the path in the
# element tree and presses the leaf, without opening the menus.
def invoke_menu(pid, window_id, path):
    """Press the allow-listed menu item through its AT-SPI action once the item is usable.

    A command that acts on the active document can be disabled, or missing from a partial element
    tree, right after the first document opens. The item is read again every ``MENU_POLL_S`` for up
    to ``MENU_ENABLE_S``; a click the driver refuses is raised with the ``menu_path_unavailable``
    prefix, so the caller treats it as a refusal.
    """
    if tuple(path) not in MENU_ALLOW_LIST:
        raise ValueError(f"menu path {list(path)} is not in the allow-list {MENU_ALLOW_LIST}")
    deadline = time.monotonic() + MENU_ENABLE_S
    while True:
        state = cua(
            "get_window_state",
            {"pid": pid, "window_id": window_id, "include_screenshot": False},
        )
        try:
            leaf = _menu_leaf(state.get("elements", []), path)
        except CuaError as missing:
            problem = missing
        else:
            if leaf.get("enabled") is not False:
                break
            problem = CuaError(
                f"menu_path_unavailable: menu item {leaf['label']!r} is still disabled "
                f"after {MENU_ENABLE_S:.0f} s in {list(path)}"
            )
        if time.monotonic() > deadline:
            raise problem
        time.sleep(MENU_POLL_S)
    try:
        cua("click", {"pid": pid, "window_id": window_id, "element_token": leaf["element_token"]})
    except CuaError as exc:
        # Only an answer the driver refused is a refusal; a timeout, an exit code or a reply that
        # is not JSON is a fault, raised as it is so that it is not delivered again.
        if " refused: " in str(exc) and MENU_UNAVAILABLE not in str(exc):
            raise CuaError(f"{MENU_UNAVAILABLE}: click refused: {exc}") from exc
        raise
