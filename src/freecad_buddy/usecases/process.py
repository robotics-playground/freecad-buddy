"""Process liveness, shared by listener discovery and the session-workdir sweep (stdlib only)."""

from __future__ import annotations

import os

_PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
_STILL_ACTIVE = 259
_ERROR_ACCESS_DENIED = 5


def pid_alive(pid: int) -> bool:
    """Cross-platform best-effort liveness check for a recorded ``pid``."""
    if pid <= 0:
        return False
    if os.name == "nt":
        try:
            import ctypes

            kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
            process = kernel32.OpenProcess(_PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
            if not process:
                # Access denied means the process exists but belongs to another user or a
                # higher integrity level; any other failure means there is no such process.
                return ctypes.get_last_error() == _ERROR_ACCESS_DENIED
            # An exited process keeps its kernel object, and OpenProcess still succeeds, while
            # any handle to it stays open; only the exit code tells it apart from a live one.
            exit_code = ctypes.c_ulong()
            queried = kernel32.GetExitCodeProcess(process, ctypes.byref(exit_code))
            kernel32.CloseHandle(process)
            return not queried or exit_code.value == _STILL_ACTIVE
        except Exception:  # noqa: BLE001 - liveness is best-effort
            return True
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return False
    return True
