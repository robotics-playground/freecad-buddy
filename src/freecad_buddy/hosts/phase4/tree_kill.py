"""Whole-tree kill for a worker process and everything it spawned.

The rule this module exists to enforce: never kill the top PID alone. FreeCAD's OCCT layer spawns
helper processes, and a top-PID kill orphans them. Orphans hold their memory, keep their file
handles, and wedge the pool that is trying to refill — the failure mode the Phase 4 design calls
out by name.

Two backends, one behaviour. POSIX puts the worker in its own process group and signals the
group. Windows assigns the worker to a Job Object and closes it, which terminates every process
in the job atomically. Both escalate: a graceful signal first, then force after a grace period,
because a worker mid-write to an artifact should get the chance to finish the line.

``subprocess`` is imported for the Windows ``CREATE_*`` flag constants; no FreeCAD, no
third-party.
"""

from __future__ import annotations

import os
import signal
import subprocess
import sys
import time

# The grace a worker gets between the polite signal and the forced one. Long enough for a worker
# to finish an in-flight artifact write and exit on its own; short enough that a deadline-killed
# job does not double its own deadline. Retune against the G4 soak, not by taste.
GRACE_SECONDS = 5.0

# How often the grace period is polled for the process having exited on its own.
_POLL_SECONDS = 0.05

_IS_WINDOWS = sys.platform == "win32"

# CREATE_SUSPENDED: the worker starts frozen so it can be assigned to its Job Object before it
# runs a single instruction. Without it the worker can spawn a helper between CreateProcess and
# the assignment, and that helper is outside the job forever.
_CREATE_SUSPENDED = 0x00000004


def spawn_kwargs(existing: dict | None = None) -> dict:
    """Return the ``Popen``/spawn keyword arguments that make a child tree-killable.

    POSIX: ``start_new_session`` puts the child in a new process group whose id equals its pid, so
    one ``killpg`` reaches every descendant that has not deliberately left the group.

    Windows: ``CREATE_NEW_PROCESS_GROUP | CREATE_SUSPENDED``. Both matter.

    ``CREATE_BREAKAWAY_FROM_JOB`` must NOT be set — it is the flag that lets a process LEAVE a
    job, so setting it on the worker lets the worker's own children break out of the job we are
    about to kill.

    ``CREATE_SUSPENDED`` closes a race that is otherwise unfixable from the parent. A job can
    only be assigned after ``CreateProcess`` returns, and an unsuspended worker may already have
    spawned a helper by then — that helper is outside the job and survives the kill. Measured:
    without suspension the worker died and its child kept running. The worker is resumed by
    ``JobHandle`` once it is inside the job, so every descendant it ever spawns inherits
    membership.

    This is also deliberately NOT the flag set ``gui_addon/bootstrap.py`` uses for the MCP proxy:
    ``DETACHED_PROCESS`` there makes the proxy survive its parent, the opposite of what a killable
    worker needs.

    :param existing: keyword arguments to extend rather than replace.
    """
    kwargs = dict(existing or {})
    if _IS_WINDOWS:
        flags = kwargs.get("creationflags", 0)
        kwargs["creationflags"] = (
            flags | subprocess.CREATE_NEW_PROCESS_GROUP | _CREATE_SUSPENDED
        )
    else:
        kwargs["start_new_session"] = True
    return kwargs


def kill_tree(pid: int, grace_seconds: float = GRACE_SECONDS) -> bool:
    """Kill ``pid`` and every process under it. Return whether the tree is gone.

    Escalates: a graceful signal, then ``grace_seconds`` to exit, then force. Returns ``True``
    when nothing of the tree remains, including the case where it had already exited before the
    first signal — an already-dead tree is a killed tree as far as the caller's status is
    concerned.

    A failure to kill is reported rather than raised: the caller is already resolving a job to a
    terminal status, and an exception here would replace a real status with a traceback.
    """
    if _IS_WINDOWS:
        return _kill_tree_windows(pid, grace_seconds)
    return _kill_tree_posix(pid, grace_seconds)


def _kill_tree_posix(pid: int, grace_seconds: float) -> bool:
    """Signal the worker's whole process GROUP, not the single pid."""
    try:
        group = os.getpgid(pid)
    except (ProcessLookupError, PermissionError):
        return True  # Already gone, or not ours to inspect; either way we are not leaving a tree.

    if not _signal_group(group, signal.SIGTERM):
        return True

    deadline = time.monotonic() + grace_seconds
    while time.monotonic() < deadline:
        if not _group_alive(group):
            return True
        time.sleep(_POLL_SECONDS)

    _signal_group(group, signal.SIGKILL)
    # SIGKILL cannot be caught or ignored, but the kernel still needs a moment to reap.
    reap_deadline = time.monotonic() + grace_seconds
    while time.monotonic() < reap_deadline:
        if not _group_alive(group):
            return True
        time.sleep(_POLL_SECONDS)
    return not _group_alive(group)


def _signal_group(group: int, sig: int) -> bool:
    """Send ``sig`` to a process group; return whether the group was there to receive it."""
    try:
        os.killpg(group, sig)
    except ProcessLookupError:
        return False
    except PermissionError:
        return False
    return True


def _group_alive(group: int) -> bool:
    """Whether any process remains in ``group``. Signal 0 checks existence without delivering."""
    return _signal_group(group, 0)


def _kill_tree_windows(pid: int, grace_seconds: float) -> bool:
    """Terminate the worker's Job Object, which kills every process assigned to it atomically.

    Falls back to ``taskkill /T`` when no job handle is held for the pid. The fallback is weaker —
    it walks the parent/child table rather than using a kernel-enforced set — so a process that
    re-parented escapes it. That is why ``JobHandle`` below is the intended path and this is only
    the path for a pid the caller did not start through it.
    """
    handle = _JOB_HANDLES.get(pid)
    if handle is not None:
        return handle.terminate()
    completed = subprocess.run(
        ["taskkill", "/PID", str(pid), "/T", "/F"],
        capture_output=True,
        timeout=grace_seconds,
        check=False,
    )
    # 128 is "process not found", which for our purposes is a tree that is already gone.
    return completed.returncode in (0, 128)


# Job Object handles held for pids this process started, keyed by pid. A handle must outlive the
# spawn call: closing it is what kills the job, so dropping it early would kill the worker we
# just started.
_JOB_HANDLES: dict[int, "JobHandle"] = {}


class JobHandle:
    """A Windows Job Object owning one worker tree.

    Assigning the worker to a job and setting ``JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE`` makes the
    kill atomic and total: every process in the job dies when the handle closes, including ones
    spawned after assignment. That is the property ``taskkill /T`` cannot offer, and the reason
    the design names a Job Object specifically rather than "kill the children".

    Inert on POSIX, where the process group is the equivalent primitive.
    """

    def __init__(self, pid: int, resume: bool = True) -> None:
        """Assign ``pid`` to a fresh job and, by default, resume it.

        The worker is spawned suspended (see ``spawn_kwargs``) so this assignment wins the race
        against its first ``CreateProcess``. Resuming is therefore part of taking ownership: a
        caller that skipped it would leave the worker frozen forever.
        """
        self.pid = pid
        self._handle = None
        if _IS_WINDOWS:
            self._handle = _create_job_for(pid)
            if self._handle is not None:
                _JOB_HANDLES[pid] = self
            if resume:
                resume_process(pid)

    def terminate(self, grace_seconds: float = GRACE_SECONDS) -> bool:
        """Terminate the job, killing every process in it. Return whether the tree is gone.

        The handle is closed only AFTER termination has been observed. Closing it immediately
        races the kernel: measured, a close issued in the same breath as the terminate left the
        worker dead and its grandchild running, because the job was torn down before every
        member had been signalled. Waiting for the job's process list to empty is what makes the
        kill total rather than usually-total.
        """
        if self._handle is None:
            return False
        import ctypes

        kernel32 = ctypes.windll.kernel32
        ok = bool(kernel32.TerminateJobObject(ctypes.c_void_p(self._handle), 1))

        deadline = time.monotonic() + grace_seconds
        while time.monotonic() < deadline:
            if _job_process_count(self._handle) == 0:
                break
            time.sleep(_POLL_SECONDS)
        gone = _job_process_count(self._handle) == 0

        kernel32.CloseHandle(ctypes.c_void_p(self._handle))
        self._handle = None
        _JOB_HANDLES.pop(self.pid, None)
        return ok and gone

    def release(self) -> None:
        """Drop the handle WITHOUT killing the job — for a worker that exited on its own."""
        if self._handle is None:
            return
        import ctypes

        ctypes.windll.kernel32.CloseHandle(ctypes.c_void_p(self._handle))
        self._handle = None
        _JOB_HANDLES.pop(self.pid, None)


def resume_process(pid: int) -> bool:
    """Resume every thread of a process started with ``CREATE_SUSPENDED``.

    Inert off Windows, where nothing is suspended in the first place. Walks the thread table
    because ``ResumeThread`` takes a thread, not a process, and a freshly created process has
    exactly one thread — but walking is correct even if that ever stops being true.
    """
    if not _IS_WINDOWS:
        return True
    import ctypes
    from ctypes import wintypes

    kernel32 = ctypes.windll.kernel32
    kernel32.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
    kernel32.OpenThread.restype = wintypes.HANDLE

    class _ThreadEntry(ctypes.Structure):
        _fields_ = [
            ("dwSize", wintypes.DWORD),
            ("cntUsage", wintypes.DWORD),
            ("th32ThreadID", wintypes.DWORD),
            ("th32OwnerProcessID", wintypes.DWORD),
            ("tpBasePri", ctypes.c_long),
            ("tpDeltaPri", ctypes.c_long),
            ("dwFlags", wintypes.DWORD),
        ]

    snapshot = kernel32.CreateToolhelp32Snapshot(0x00000004, 0)  # TH32CS_SNAPTHREAD
    if snapshot in (None, -1, 0xFFFFFFFFFFFFFFFF):
        return False
    entry = _ThreadEntry()
    entry.dwSize = ctypes.sizeof(_ThreadEntry)
    resumed = False
    try:
        if not kernel32.Thread32First(ctypes.c_void_p(snapshot), ctypes.byref(entry)):
            return False
        while True:
            if entry.th32OwnerProcessID == pid:
                thread = kernel32.OpenThread(0x0002, False, entry.th32ThreadID)  # SUSPEND_RESUME
                if thread:
                    kernel32.ResumeThread(ctypes.c_void_p(thread))
                    kernel32.CloseHandle(ctypes.c_void_p(thread))
                    resumed = True
            if not kernel32.Thread32Next(ctypes.c_void_p(snapshot), ctypes.byref(entry)):
                break
    finally:
        kernel32.CloseHandle(ctypes.c_void_p(snapshot))
    return resumed


def _job_process_count(handle) -> int:
    """How many processes remain assigned to ``handle``. ``-1`` when it cannot be queried.

    Reads ``JobObjectBasicAccountingInformation``'s ActiveProcesses. A job whose count has
    reached zero has no member left to kill, which is the only evidence that a terminate was
    total rather than partial.
    """
    if not _IS_WINDOWS or handle is None:
        return -1
    import ctypes

    class _BasicAccounting(ctypes.Structure):
        _fields_ = [
            ("TotalUserTime", ctypes.c_longlong),
            ("TotalKernelTime", ctypes.c_longlong),
            ("ThisPeriodTotalUserTime", ctypes.c_longlong),
            ("ThisPeriodTotalKernelTime", ctypes.c_longlong),
            ("TotalPageFaultCount", ctypes.c_ulong),
            ("TotalProcesses", ctypes.c_ulong),
            ("ActiveProcesses", ctypes.c_ulong),
            ("TotalTerminatedProcesses", ctypes.c_ulong),
        ]

    info = _BasicAccounting()
    ok = ctypes.windll.kernel32.QueryInformationJobObject(
        ctypes.c_void_p(handle), 1, ctypes.byref(info), ctypes.sizeof(info), None
    )  # 1 = JobObjectBasicAccountingInformation
    if not ok:
        return -1
    return int(info.ActiveProcesses)


def _create_job_for(pid: int):
    """Create a kill-on-close Job Object and assign ``pid`` to it; ``None`` if that is not possible.

    Returns ``None`` rather than raising when the Win32 calls are unavailable or refused: the
    caller falls back to ``taskkill``, and a supervisor that crashed while setting up a kill
    primitive would be worse than one that kills less precisely.
    """
    if not _IS_WINDOWS:
        return None
    try:
        import ctypes
        from ctypes import wintypes
    except ImportError:
        return None

    kernel32 = ctypes.windll.kernel32
    # Declare the handle-returning calls explicitly. ctypes defaults a return value to C int,
    # which truncates a 64-bit HANDLE and yields a handle that fails every later call.
    kernel32.CreateJobObjectW.restype = wintypes.HANDLE
    kernel32.OpenProcess.restype = wintypes.HANDLE
    job = kernel32.CreateJobObjectW(None, None)
    if not job:
        return None

    # JOBOBJECT_EXTENDED_LIMIT_INFORMATION, laid out by hand: ctypes has no binding for it, and
    # the only field we set is the kill-on-close flag in the basic-limits header.
    class _IoCounters(ctypes.Structure):
        _fields_ = [
            ("ReadOperationCount", ctypes.c_ulonglong),
            ("WriteOperationCount", ctypes.c_ulonglong),
            ("OtherOperationCount", ctypes.c_ulonglong),
            ("ReadTransferCount", ctypes.c_ulonglong),
            ("WriteTransferCount", ctypes.c_ulonglong),
            ("OtherTransferCount", ctypes.c_ulonglong),
        ]

    class _BasicLimits(ctypes.Structure):
        _fields_ = [
            ("PerProcessUserTimeLimit", wintypes.LARGE_INTEGER),
            ("PerJobUserTimeLimit", wintypes.LARGE_INTEGER),
            ("LimitFlags", wintypes.DWORD),
            ("MinimumWorkingSetSize", ctypes.c_size_t),
            ("MaximumWorkingSetSize", ctypes.c_size_t),
            ("ActiveProcessLimit", wintypes.DWORD),
            ("Affinity", ctypes.POINTER(wintypes.ULONG)),
            ("PriorityClass", wintypes.DWORD),
            ("SchedulingClass", wintypes.DWORD),
        ]

    class _ExtendedLimits(ctypes.Structure):
        _fields_ = [
            ("BasicLimitInformation", _BasicLimits),
            ("IoInfo", _IoCounters),
            ("ProcessMemoryLimit", ctypes.c_size_t),
            ("JobMemoryLimit", ctypes.c_size_t),
            ("PeakProcessMemoryUsed", ctypes.c_size_t),
            ("PeakJobMemoryUsed", ctypes.c_size_t),
        ]

    info = _ExtendedLimits()
    info.BasicLimitInformation.LimitFlags = 0x00002000  # KILL_ON_JOB_CLOSE
    if not kernel32.SetInformationJobObject(
        job, 9, ctypes.byref(info), ctypes.sizeof(info)
    ):  # 9 = JobObjectExtendedLimitInformation
        kernel32.CloseHandle(job)
        return None

    process = kernel32.OpenProcess(0x1F0FFF, False, pid)  # PROCESS_ALL_ACCESS
    if not process:
        kernel32.CloseHandle(job)
        return None
    assigned = kernel32.AssignProcessToJobObject(job, process)
    kernel32.CloseHandle(process)
    if not assigned:
        kernel32.CloseHandle(job)
        return None
    return job
