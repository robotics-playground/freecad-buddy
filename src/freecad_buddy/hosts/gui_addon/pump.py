"""Qt main-thread executor: the ``Marshal`` pump for the GUI host.

Constructed on the Qt main thread. ``submit`` is called from the listener accept thread and
posts a ``_CallEvent`` (``postEvent`` is thread-safe); ``customEvent`` runs the callable on the
main thread. This mirrors FreeCAD's own ``postEvent``/``customEvent`` main-thread handoff — Qt
lives only in the host per the ring rules.
"""

from __future__ import annotations

from typing import Callable

from PySide import QtCore

_CALL_EVENT_TYPE = QtCore.QEvent.Type(QtCore.QEvent.registerEventType())


class _CallEvent(QtCore.QEvent):
    """Carries a zero-arg callable to run on the Qt main thread."""

    def __init__(self, fn: Callable[[], None]) -> None:
        super().__init__(_CALL_EVENT_TYPE)
        self.fn = fn


class QtMainThreadExecutor(QtCore.QObject):
    """``Executor`` that runs submitted callables on the Qt main thread via ``postEvent``."""

    def submit(self, fn: Callable[[], None]) -> None:
        QtCore.QCoreApplication.postEvent(self, _CallEvent(fn))

    def customEvent(self, event: QtCore.QEvent) -> None:
        if isinstance(event, _CallEvent):
            event.fn()
