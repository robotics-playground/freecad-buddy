"""The private venv a release install runs the MCP proxy from, provisioned with ``uv``.

A release addon carries the package wheel in ``wheels/`` but no interpreter that can import
``mcp`` (AD-12 keeps it out of FreeCAD's Python). On first start ``provision`` builds a venv from
that wheel; a marker holding the wheel's SHA-256 makes an upgraded addon re-provision. Stdlib
only, no Qt: it runs on a background thread and pytest imports it without FreeCAD.
"""

from __future__ import annotations

import hashlib
import logging
import os
import shutil
import subprocess
import threading
import time
from datetime import datetime
from pathlib import Path

from freecad_buddy import __version__

logger = logging.getLogger("freecad_buddy.hosts.gui_addon.managed_venv")

_MARKER = "freecad-buddy-wheel.sha256"
_LOCK = "venv.lock"
# A provisioning run downloads Python and the dependency wheels; ten minutes is well past a slow
# run, so an older lock is one a crashed FreeCAD left behind.
LOCK_STALE_S = 600.0
_POLL_S = 0.5


def no_window_kwargs(logfile) -> dict:
    """Popen kwargs that run a child silently in the background (no console window).

    On Windows a bare console-app child pops a cmd window; ``CREATE_NO_WINDOW`` suppresses it and
    ``DETACHED_PROCESS`` gives the child its own process group so it is not tied to FreeCAD's
    console. The child's stdout/stderr go to ``logfile`` (its own diagnostics), not a window. On
    POSIX, ``start_new_session`` detaches it.
    """
    kwargs: dict = {"stdin": subprocess.DEVNULL, "stdout": logfile, "stderr": logfile}
    if os.name == "nt":
        # 0x08000000 CREATE_NO_WINDOW | 0x00000008 DETACHED_PROCESS
        kwargs["creationflags"] = 0x08000000 | 0x00000008
    else:
        kwargs["start_new_session"] = True
    return kwargs


def find_uv(preferred: str = "") -> Path | None:
    """The ``uv`` executable: the preference path when it names a file, else ``uv`` on PATH."""
    if preferred:
        if Path(preferred).is_file():
            return Path(preferred)
        logger.warning(
            "uv path preference %r is not a file; ignoring it and using uv on PATH", preferred
        )
    found = shutil.which("uv")
    return Path(found) if found else None


def bundled_wheel(addon_root: Path, version: str = __version__) -> Path | None:
    """The wheel of the running ``version`` in ``<addon>/wheels``, or ``None`` for a dev copy.

    Matched by version, not picked by name order: a new zip extracted over an old folder leaves
    the old wheel beside the new one, and ``0.0.9`` sorts after ``0.0.10``.
    """
    wheels = sorted((addon_root / "wheels").glob(f"freecad_buddy-{version}-*.whl"))
    return wheels[0] if wheels else None


def venv_python(venv_dir: Path) -> Path:
    """The interpreter that runs the proxy from ``venv_dir``.

    On Windows this is ``pythonw.exe``: the console python re-execs through a launcher that opens
    its own console window even under ``CREATE_NO_WINDOW``.
    """
    if os.name == "nt":
        return venv_dir / "Scripts" / "pythonw.exe"
    return venv_dir / "bin" / "python"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def is_current(venv_dir: Path, wheel: Path) -> bool:
    """Whether ``venv_dir`` has an interpreter and was provisioned from this exact wheel."""
    try:
        marker = (venv_dir / _MARKER).read_text(encoding="utf-8").strip()
    except OSError:
        return False
    return venv_python(venv_dir).is_file() and marker == _sha256(wheel)


def _acquire_lock(lock: Path) -> bool:
    """Create ``lock`` exclusively; a lock older than ``LOCK_STALE_S`` is taken over."""
    lock.parent.mkdir(parents=True, exist_ok=True)
    try:
        if time.time() - lock.stat().st_mtime > LOCK_STALE_S:
            lock.unlink()
    except FileNotFoundError:
        pass
    try:
        os.close(os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY))
    except OSError:
        return False
    return True


def _run(command: list[str], logfile, cancel: threading.Event) -> bool:
    """Run ``command`` to completion; ``False`` on a non-zero exit or when ``cancel`` is set."""
    process = subprocess.Popen(command, **no_window_kwargs(logfile))  # noqa: S603 - fixed argv
    while True:
        try:
            return process.wait(timeout=_POLL_S) == 0
        except subprocess.TimeoutExpired:
            if cancel.is_set():
                process.terminate()
                process.wait()
                return False


def provision(
    uv: Path, wheel: Path, venv_dir: Path, log_path: Path, cancel: threading.Event
) -> bool:
    """Build ``venv_dir`` from ``wheel`` with ``uv``; ``True`` when the venv is current after.

    A lock file beside the venv lets one FreeCAD instance provision while another skips. The
    marker is written last, so an interrupted run is never mistaken for a current venv.
    """
    lock = venv_dir.parent / _LOCK
    if not _acquire_lock(lock):
        try:
            expiry = datetime.fromtimestamp(lock.stat().st_mtime + LOCK_STALE_S).isoformat(" ")
        except OSError:
            expiry = "unknown"
        logger.warning(
            "MCP proxy venv provisioning skipped: lock %s is held by another FreeCAD instance or "
            "left by one that was killed. It expires at %s. If no other FreeCAD is running, "
            "delete it and restart FreeCAD.",
            lock, expiry,
        )
        return False
    try:
        if is_current(venv_dir, wheel):
            return True
        steps = (
            [str(uv), "venv", "--clear", "--python", ">=3.11", str(venv_dir)],
            [str(uv), "pip", "install", "--python", str(venv_dir), str(wheel)],
        )
        with open(log_path, "a", encoding="utf-8") as logfile:
            for command in steps:
                if not _run(command, logfile, cancel):
                    if not cancel.is_set():
                        logger.error(
                            "MCP proxy venv provisioning failed at `%s`; see %s",
                            " ".join(command[1:3]), log_path,
                        )
                    return False
        (venv_dir / _MARKER).write_text(_sha256(wheel), encoding="utf-8")
        return True
    finally:
        lock.unlink(missing_ok=True)
