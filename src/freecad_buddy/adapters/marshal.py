"""Main-thread marshal.

Separates the queue/blocking logic (here, stdlib-only) from the Qt pump. The headless host
uses ``InlineExecutor`` (no Qt loop, already on the main thread) so use cases go through
``Marshal.call`` regardless of host.

QtCore may be imported here, but only inside functions at call time so the module import
stays Qt-free for headless use.
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


class MarshalTimeout(Exception):
    """Raised when a marshaled call does not complete within its budget.

    The wrapped callable may still execute later, so the session is document-suspect until a
    fingerprint check confirms state; do not blind-retry a mutation after this.
    """


class Marshal:
    """Runs a callable on the FreeCAD execution thread and waits (bounded) for its result.

    With ``InlineExecutor`` the callable runs synchronously and the wait never blocks; the
    timeout path exists for hosts where ``submit`` hands off to another thread.
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
