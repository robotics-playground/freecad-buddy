"""Print pid, parent pid, and command line of every python/pythonw process (or the pids given).

Win32_Process.CommandLine is empty from this non-elevated shell, so the command line is read with
NtQueryInformationProcess(ProcessCommandLineInformation = 60).
"""

import ctypes
import subprocess
import sys
from ctypes import wintypes

ntdll = ctypes.WinDLL("ntdll")
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
kernel32.OpenProcess.restype = wintypes.HANDLE


class UNICODE_STRING(ctypes.Structure):
    _fields_ = [("Length", wintypes.USHORT), ("MaximumLength", wintypes.USHORT), ("Buffer", ctypes.c_void_p)]


def cmdline(pid: int) -> str:
    handle = kernel32.OpenProcess(0x1000, False, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
    if not handle:
        return f"<OpenProcess failed {ctypes.get_last_error()}>"
    size = wintypes.ULONG(0)
    buf = ctypes.create_string_buffer(65536)
    status = ntdll.NtQueryInformationProcess(handle, 60, buf, len(buf), ctypes.byref(size))
    kernel32.CloseHandle(handle)
    if status != 0:
        return f"<NtQueryInformationProcess status {status & 0xFFFFFFFF:#x}>"
    us = UNICODE_STRING.from_buffer(buf)
    return ctypes.wstring_at(us.Buffer, us.Length // 2)


def processes() -> list[tuple[int, int, str]]:
    out = subprocess.run(
        ["powershell", "-NoProfile", "-c",
         "Get-CimInstance Win32_Process | ? { $_.Name -like 'python*' } | % { \"$($_.ProcessId) $($_.ParentProcessId) $($_.Name)\" }"],
        capture_output=True, text=True).stdout.split()
    return [(int(out[i]), int(out[i + 1]), out[i + 2]) for i in range(0, len(out), 3)]


if __name__ == "__main__":
    wanted = {int(a) for a in sys.argv[1:]}
    for pid, ppid, name in processes():
        if wanted and pid not in wanted:
            continue
        print(f"pid {pid} parent {ppid} {name}: {cmdline(pid)}")
