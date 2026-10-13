"""Fixtures shared by the external suite."""

from __future__ import annotations

import sys
import types

import pytest


@pytest.fixture
def stub_qt(monkeypatch):
    """Stub ``PySide.QtCore`` so ``hosts.gui_addon.pump`` imports without Qt installed.

    ``pump`` subclasses ``QtCore.QObject`` and calls ``QEvent.registerEventType()`` at module
    import, so the stub must supply both before ``bootstrap`` can be imported at all.
    """

    class _QEvent:
        Type = staticmethod(lambda value: value)

        def __init__(self, *args):
            pass

        @staticmethod
        def registerEventType():  # noqa: N802 - Qt API name
            return 1000

    class _QObject:
        def __init__(self, *args, **kwargs):
            pass

    class _QCoreApplication:
        @staticmethod
        def instance():
            return None

        @staticmethod
        def postEvent(receiver, event):
            pass

    qtcore = types.ModuleType("PySide.QtCore")
    qtcore.QEvent = _QEvent
    qtcore.QObject = _QObject
    qtcore.QCoreApplication = _QCoreApplication
    pyside = types.ModuleType("PySide")
    pyside.QtCore = qtcore
    monkeypatch.setitem(sys.modules, "PySide", pyside)
    monkeypatch.setitem(sys.modules, "PySide.QtCore", qtcore)
