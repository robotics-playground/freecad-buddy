"""List the windows of the running FreeCAD (main window and any open popup menu): r0_popups.py."""
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "runner"))
import capture  # noqa: E402
import launch  # noqa: E402

pid = launch.running_freecad_pids()[0]
out = subprocess.run([capture.CUA_DRIVER, "call", "list_windows"], input=json.dumps({"pid": pid}),
                     capture_output=True, text=True, encoding="utf-8", timeout=60)
for window in json.loads(out.stdout).get("windows", []):
    print(window.get("window_id"), repr(window.get("title")), window.get("bounds"))
