"""Start and end the FreeCAD a scenario group runs in.

Runs inside the ``fcb-desktop`` container (``tests/close-loop/README.md``), started through
``fcb-py``: FreeCAD is the Linux AppImage under ``/opt/freecad``, found by its command line under
``/proc``, and the probe discovery file is under the user's ``~/.local/share``. The runner starts
FreeCAD with ``subprocess`` in a new session, so it can end the whole ``AppRun`` process group, and
it ends only the process it started.
"""

import contextlib
import json
import os
import shutil
import signal
import socket
import subprocess
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

from capture import CUA_DRIVER

PROBE_DIR = Path(__file__).resolve().parents[1] / "probe"
FREECAD_APPRUN = os.environ.get("FREECAD_APPRUN", "/opt/freecad/AppRun")
# AppRun starts this binary as its child, not with exec: ``/healthz`` names this pid, not AppRun's.
FREECAD_BINARY = "/opt/freecad/usr/bin/freecad"
PROXY_PORT = 8765
HEALTHZ_URL = f"http://127.0.0.1:{PROXY_PORT}/healthz"
START_TIMEOUT_S = 120.0
# The proxy exits about 2 s after its FreeCAD is gone (AD-2 watchdog); allow for a slow machine.
PORT_FREE_TIMEOUT_S = 15.0
POLL_S = 0.5
REQUEST_TIMEOUT_S = 30.0
# The operator's bridge settings must not leak into a launch: a group starts from the default
# posture plus its own ``launch`` map.
BRIDGE_ENV_PREFIX = "FREECAD_BUDDY_"
# ``fcb-py`` points these at the runner's own Python; FreeCAD must keep the AppImage's.
PYTHON_ENV = ("PYTHONPATH", "PYTHONHOME")
# With the AT-SPI bridge on, Qt warns "Received text event for invalid interface" while FreeCAD
# builds a notification label, and FreeCAD's message handler re-enters
# NotificationArea::pushNotification while showInNotificationArea (NotificationArea.cpp:1143) holds
# its mutex: the main thread deadlocks. `fcb-freecad start` sets the same rule.
QT_LOGGING_RULES = "qt.accessibility.atspi.warning=false"


class LaunchError(Exception):
    pass


_PROC_ROOT = "/proc"


def _process_table(proc_root):
    """``{pid: (parent pid, argv, process group)}`` of every readable process in ``proc_root``."""
    table = {}
    try:
        entries = list(Path(proc_root).iterdir())
    except OSError as exc:
        raise LaunchError(f"cannot list processes under {proc_root}: {exc}") from exc
    for entry in entries:
        if not entry.name.isdigit():
            continue
        try:
            argv = (entry / "cmdline").read_bytes().split(b"\0")
            # ``comm`` may hold spaces or parentheses, so the parent is read after the last ``)``.
            fields = (entry / "stat").read_text().rpartition(")")[2].split()
            parent, group = int(fields[1]), int(fields[2])
        except (OSError, ValueError, IndexError):
            continue
        table[int(entry.name)] = (parent, [part.decode(errors="replace") for part in argv], group)
    return table


def running_freecad_pids(proc_root=None):
    table = _process_table(proc_root or _PROC_ROOT)
    return sorted(pid for pid, (_, argv, _) in table.items() if argv[0] == FREECAD_BINARY)


def descendant_pids(root, proc_root=None):
    """``root`` and every process below it."""
    table = _process_table(proc_root or _PROC_ROOT)
    found = {root}
    grew = True
    while grew:
        grew = False
        for pid, (parent, _, _) in table.items():
            if parent in found and pid not in found:
                found.add(pid)
                grew = True
    return found


def started_pids(root, proc_root=None):
    """Every process the runner started: ``root``, its descendants, and its process group.

    A FreeCAD whose ``AppRun`` parent has exited is a child of init, so only its group, which is
    ``root``'s while ``root`` leads a new session, still names it.
    """
    table = _process_table(proc_root or _PROC_ROOT)
    return descendant_pids(root, proc_root) | {
        pid for pid, (_, _, group) in table.items() if group == root
    }


def port_held(port=PROXY_PORT):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.settimeout(1.0)
        return probe.connect_ex(("127.0.0.1", port)) == 0


def check_tools():
    """Raise ``LaunchError`` when ``AppRun`` or a running ``cua-driver`` daemon is missing."""
    if not Path(FREECAD_APPRUN).is_file():
        raise LaunchError(f"FREECAD_APPRUN {FREECAD_APPRUN} is not a file")
    if not os.environ.get("DISPLAY"):
        raise LaunchError("DISPLAY is not set: run through fcb-py once the desktop session is up")
    if shutil.which(CUA_DRIVER) is None:
        raise LaunchError(f"{CUA_DRIVER} is not an executable file")
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
    environment = {
        k: v
        for k, v in os.environ.items()
        if not k.startswith(BRIDGE_ENV_PREFIX) and k not in PYTHON_ENV
    }
    environment["FREECAD_BUDDY_AUDIT_LOG"] = str(audit_log)
    environment.update(launch)
    # Qt applies the last matching rule, so the silencing rule goes after any other.
    environment["QT_LOGGING_RULES"] = ";".join(
        rule for rule in (environment.get("QT_LOGGING_RULES"), QT_LOGGING_RULES) if rule
    )
    return environment


def freecad_command(work):
    """The AppImage command: probe module and a temporary profile under ``work``."""
    return [
        FREECAD_APPRUN,
        "-M",
        str(PROBE_DIR),
        "-u",
        str(Path(work) / "user.cfg"),
        "-s",
        str(Path(work) / "system.cfg"),
    ]


def discovery_file(pid, data_home=None):
    data_home = Path(data_home or os.environ.get("XDG_DATA_HOME") or Path.home() / ".local/share")
    return next(data_home.glob(f"FreeCAD/*/fcb-uat-probe/probe-{pid}.json"), None)


def _healthz():
    try:
        with urllib.request.urlopen(HEALTHZ_URL, timeout=2.0) as response:
            return json.load(response)
    except (OSError, ValueError):
        return None


def wait_until_ready(process):
    """Wait until ``/healthz`` names a FreeCAD below ``process`` and its probe wrote its file."""
    deadline = time.monotonic() + START_TIMEOUT_S
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise LaunchError(f"FreeCAD exited with code {process.returncode}")
        health = _healthz()
        freecad_pid = health and health.get("freecad_pid")
        discovery = freecad_pid and discovery_file(freecad_pid)
        if discovery and freecad_pid in descendant_pids(process.pid):
            record = json.loads(discovery.read_text(encoding="utf-8"))
            # The probe writes into FreeCAD's user app data folder: the one whose Mod it loaded.
            return record | {"user_app_data": str(discovery.parent.parent)}
        time.sleep(POLL_S)
    raise LaunchError(
        f"pid {process.pid}: no /healthz naming a FreeCAD below it or no probe discovery file "
        f"after {START_TIMEOUT_S:.0f} s"
    )


def get_snapshot(record):
    request = urllib.request.Request(
        f"http://127.0.0.1:{record['port']}/snapshot",
        headers={"X-Probe-Token": record["token"]},
    )
    with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT_S) as response:
        return json.load(response)


def stop(process, freecad_pid=None):
    """End the FreeCAD this runner started, then wait until its proxy frees ``:8765``."""
    try:
        started = started_pids(process.pid)
    except LaunchError:
        started = {process.pid}
    with contextlib.suppress(ProcessLookupError):
        # The process is a session leader, so its pid is its process group: AppRun and FreeCAD.
        os.killpg(process.pid, signal.SIGKILL)
    process.wait()
    # A killed FreeCAD cannot delete its own probe discovery file, and a FreeCAD that was killed
    # before it was ready may already have written one.
    for pid in started | {freecad_pid}:
        discovery = discovery_file(pid) if pid else None
        if discovery is not None:
            discovery.unlink(missing_ok=True)
    deadline = time.monotonic() + PORT_FREE_TIMEOUT_S
    while port_held():
        if time.monotonic() > deadline:
            raise LaunchError(f":{PROXY_PORT} still held {PORT_FREE_TIMEOUT_S:.0f} s after exit")
        time.sleep(POLL_S)


@contextlib.contextmanager
def freecad(launch, audit_log):
    """Start FreeCAD with the probe and a temporary profile; yield ``(process, record)``.

    FreeCAD writes both profile files on exit, so the temporary ``-u`` and ``-s`` files keep the
    container user's ``user.cfg`` and ``system.cfg`` unchanged and give the bridge its default
    preferences. Refuses, before starting anything, when a FreeCAD runs or ``:8765`` is held, for
    example by the previous group's proxy. ``record["pid"]`` is the FreeCAD pid, not ``AppRun``'s.
    """
    check_free()
    with tempfile.TemporaryDirectory(prefix="fcb-uat-run-", ignore_cleanup_errors=True) as work:
        process = subprocess.Popen(
            freecad_command(work),
            env=launch_environment(launch, audit_log),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        record = None
        try:
            record = wait_until_ready(process)
            yield process, record
        finally:
            stop(process, record["pid"] if record else None)


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
