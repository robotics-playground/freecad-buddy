"""Start and end the FreeCAD a scenario group runs in.

Windows only, like ``tests/uat/probe/run_faults.py``: FreeCAD is found by image name with
``tasklist``, the probe discovery file under ``%APPDATA%``, and the default ``freecad.exe`` is the
FreeCAD 1.1 install path (override with ``FREECAD_EXE``). The runner starts FreeCAD with
``subprocess``, so FreeCAD runs at the runner's integrity level and the runner can end it. It
ends only the process it started.
"""

import contextlib
import csv
import io
import json
import os
import shutil
import socket
import subprocess
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

from capture import CUA_DRIVER

PROBE_DIR = Path(__file__).resolve().parents[1] / "probe"
FREECAD_EXE = os.environ.get("FREECAD_EXE", r"C:\Program Files\FreeCAD 1.1\bin\freecad.exe")
PROXY_PORT = 8765
HEALTHZ_URL = f"http://127.0.0.1:{PROXY_PORT}/healthz"
START_TIMEOUT_S = 120.0
# The proxy exits about 2 s after its FreeCAD is gone (AD-2 watchdog); allow for a slow machine.
PORT_FREE_TIMEOUT_S = 15.0
POLL_S = 0.5
REQUEST_TIMEOUT_S = 30.0
# The developer's bridge settings must not leak into a launch: a group starts from the default
# posture plus its own ``launch`` map.
BRIDGE_ENV_PREFIX = "FREECAD_BUDDY_"


class LaunchError(Exception):
    pass


def running_freecad_pids():
    try:
        listing = subprocess.run(
            ["tasklist", "/FI", "IMAGENAME eq freecad*", "/FO", "CSV", "/NH"],
            capture_output=True,
            text=True,
            check=True,
        ).stdout
    except (OSError, subprocess.CalledProcessError) as exc:
        raise LaunchError(f"cannot list processes with tasklist: {exc}") from exc
    return [
        int(row[1])
        for row in csv.reader(io.StringIO(listing))
        if len(row) > 1 and row[0].lower().startswith("freecad")
    ]


def port_held(port=PROXY_PORT):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.settimeout(1.0)
        return probe.connect_ex(("127.0.0.1", port)) == 0


def check_tools():
    """Raise ``LaunchError`` when ``FREECAD_EXE`` or a running ``cua-driver`` daemon is missing."""
    if not Path(FREECAD_EXE).is_file():
        raise LaunchError(f"FREECAD_EXE {FREECAD_EXE} is not a file")
    if shutil.which(CUA_DRIVER) is None:
        raise LaunchError(f"{CUA_DRIVER} is not on PATH")
    try:
        status = subprocess.run(
            [CUA_DRIVER, "status"], capture_output=True, text=True, timeout=REQUEST_TIMEOUT_S
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise LaunchError(f"{CUA_DRIVER} status failed: {exc}") from exc
    if status.returncode != 0 or "is running" not in status.stdout:
        raise LaunchError(f"{CUA_DRIVER} daemon is not running: {status.stdout.strip()[:200]}")


def check_free():
    """Raise ``LaunchError`` when another FreeCAD runs or ``:8765`` is held."""
    pids = running_freecad_pids()
    if pids:
        raise LaunchError(f"another FreeCAD is running (pid {', '.join(map(str, pids))})")
    if port_held():
        raise LaunchError(f"127.0.0.1:{PROXY_PORT} is held by another process")


def preflight():
    check_tools()
    check_free()


def group_by_launch(scenarios):
    """Scenarios grouped by their ``launch`` map, groups and members in first-seen order."""
    groups = {}
    for scenario in scenarios:
        key = tuple(sorted(scenario["launch"].items()))
        groups.setdefault(key, []).append(scenario)
    return [(dict(key), members) for key, members in groups.items()]


def launch_environment(launch, audit_log):
    environment = {k: v for k, v in os.environ.items() if not k.startswith(BRIDGE_ENV_PREFIX)}
    environment["FREECAD_BUDDY_AUDIT_LOG"] = str(audit_log)
    environment.update(launch)
    return environment


def discovery_file(pid):
    pattern = f"FreeCAD/*/fcb-uat-probe/probe-{pid}.json"
    return next(Path(os.environ["APPDATA"]).glob(pattern), None)


def _healthz():
    try:
        with urllib.request.urlopen(HEALTHZ_URL, timeout=2.0) as response:
            return json.load(response)
    except (OSError, ValueError):
        return None


def wait_until_ready(process):
    """Wait until ``/healthz`` names ``process`` and the probe wrote its discovery file."""
    deadline = time.monotonic() + START_TIMEOUT_S
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise LaunchError(f"FreeCAD exited with code {process.returncode}")
        health = _healthz()
        discovery = discovery_file(process.pid)
        if health and health.get("freecad_pid") == process.pid and discovery is not None:
            record = json.loads(discovery.read_text(encoding="utf-8"))
            # The probe writes into FreeCAD's user app data folder: the one whose Mod it loaded.
            return record | {"user_app_data": str(discovery.parent.parent)}
        time.sleep(POLL_S)
    raise LaunchError(
        f"pid {process.pid}: no /healthz naming it or no probe discovery file "
        f"after {START_TIMEOUT_S:.0f} s"
    )


def get_snapshot(record):
    request = urllib.request.Request(
        f"http://127.0.0.1:{record['port']}/snapshot",
        headers={"X-Probe-Token": record["token"]},
    )
    with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT_S) as response:
        return json.load(response)


def stop(process):
    """End the FreeCAD this runner started, then wait until its proxy frees ``:8765``."""
    if process.poll() is None:
        process.kill()
    process.wait()
    # A killed FreeCAD cannot delete its own probe discovery file.
    discovery = discovery_file(process.pid)
    if discovery is not None:
        discovery.unlink(missing_ok=True)
    deadline = time.monotonic() + PORT_FREE_TIMEOUT_S
    while port_held():
        if time.monotonic() > deadline:
            raise LaunchError(f":{PROXY_PORT} still held {PORT_FREE_TIMEOUT_S:.0f} s after exit")
        time.sleep(POLL_S)


@contextlib.contextmanager
def freecad(launch, audit_log):
    """Start FreeCAD with the probe and a temporary ``-u`` profile; yield ``(process, record)``.

    The temporary profile keeps the developer's ``user.cfg`` unchanged and gives the bridge its
    default preferences. Refuses, before starting anything, when a FreeCAD runs or ``:8765`` is
    held, for example by the previous group's proxy.
    """
    check_free()
    with tempfile.TemporaryDirectory(prefix="fcb-uat-run-", ignore_cleanup_errors=True) as work:
        command = [FREECAD_EXE, "-M", str(PROBE_DIR), "-u", str(Path(work) / "user.cfg")]
        process = subprocess.Popen(
            command,
            env=launch_environment(launch, audit_log),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        try:
            yield process, wait_until_ready(process)
        finally:
            stop(process)


def addon_info(user_app_data):
    """Where FreeCAD loads the bridge addon from, and whether its package links elsewhere.

    ``linked`` is true when ``Mod/FreeCADBuddy/freecad_buddy`` is a junction or symlink (the dev
    install points it at ``src/freecad_buddy``); ``target`` is the folder it resolves to.
    """
    addon = Path(user_app_data) / "Mod" / "FreeCADBuddy"
    package = addon / "freecad_buddy"
    target = os.path.realpath(package)
    return {
        "path": str(addon),
        "exists": addon.is_dir(),
        "linked": os.path.normcase(target) != os.path.normcase(os.path.abspath(package)),
        "target": target,
    }
