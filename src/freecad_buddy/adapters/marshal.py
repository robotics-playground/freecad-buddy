"""Main-thread marshal.

Separates the queue/blocking logic (here, stdlib-only) from the Qt pump. The headless host
uses ``InlineExecutor`` (no Qt loop, already on the main thread) so use cases go through
``Marshal.call`` regardless of host.

This module imports no Qt at all: the Qt event pump lives in ``hosts/gui_addon/pump.py``,
where Qt is legal without an AD-1 adapters exemption. ``render_probe.py`` is therefore the
single Qt carve-out in this ring.
"""

from __future__ import annotations

import threading
from typing import Callable, Protocol, TypeVar

T = TypeVar("T")


class Executor(Protocol):
    """Schedules a callable on the FreeCAD execution thread. Thread-safe."""

    def submit(self, fn: Callable[[], None]) -> None: ...


class InlineExecutor:
    """Executor that runs the callable inline on the current thread."""

    def submit(self, fn: Callable[[], None]) -> None:
        fn()


class ThreadExecutor:
    """Executor that runs each submitted callable on its own daemon thread.

    A per-submission thread, never a pool: a pooled worker left wedged by an abandoned body
    would silently starve every later call. Threads cannot be killed, so a callable that
    overruns its budget keeps running after ``Marshal.call`` has already raised — the caller
    must treat such a timeout as document-suspect and refuse to blind-retry a mutation.

    This runs the callable off the main thread, which is why the inline host uses it for the
    operator exec path alone; all other FreeCAD state must be touched on the main thread. Hosts
    that already marshal onto a Qt main thread bound that path through their own pump instead.
    """

    def submit(self, fn: Callable[[], None]) -> None:
        threading.Thread(target=fn, daemon=True).start()


class MarshalTimeout(Exception):
    """Raised when a marshaled call does not complete within its budget.

    The wrapped callable may still execute later, so the session is document-suspect until a
    read confirms the document still responds; do not blind-retry a mutation after this.
    """


class Marshal:
    """Runs a callable on the FreeCAD execution thread and waits (bounded) for its result.

    With ``InlineExecutor`` the callable runs synchronously and the wait never blocks, so the
    budget is not enforced; the timeout is real only with an executor whose ``submit`` hands
    off to another thread (``ThreadExecutor``) or to a Qt pump.
    """

    def __init__(self, executor: Executor) -> None:
        self._executor = executor

    def call(self, fn: Callable[[], T], timeout_s: float) -> T:
        result: list[T] = []
        error: list[BaseException] = []
        done = threading.Event()

        def _run() -> None:
            try:
                result.append(fn())
            except BaseException as exc:  # noqa: BLE001 - captured, re-raised on the caller thread
                error.append(exc)
            finally:
                done.set()

        self._executor.submit(_run)
        if not done.wait(timeout_s):
            raise MarshalTimeout(f"marshaled call exceeded {timeout_s}s")
        if error:
            raise error[0]
        return result[0]
