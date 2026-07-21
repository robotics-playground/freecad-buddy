"""FreeCAD GUI addon entry: register the workbench and defer the bridge start.

FreeCAD executes this at GUI startup. The workbench registration does no listener work; the
bridge starts only after ``FreeCAD.GuiUp`` is true, polled every 500 ms via
``QTimer.singleShot`` and given up (with a stderr warning) after 60 s to avoid a startup-race
crash. Imports of ``FreeCAD``/``FreeCADGui`` are guarded so a structural import outside a GUI
does not crash.
"""

from __future__ import annotations

import logging
import sys
import time

logger = logging.getLogger("freecad_buddy.hosts.gui_addon.InitGui")

_START_DEADLINE_S = 60.0
_POLL_MS = 500

try:
    import FreeCADGui as Gui

    class FreeCADBuddyWorkbench(Gui.Workbench):
        """Registration-only workbench; the bridge is started by ``_deferred_start``."""

        MenuText = "FreeCAD Buddy"
        ToolTip = "Verify-first MCP bridge for FreeCAD"

        def Initialize(self) -> None:  # noqa: N802 - FreeCAD workbench API
            pass

        def GetClassName(self) -> str:  # noqa: N802 - FreeCAD workbench API
            return "Gui::PythonWorkbench"

    Gui.addWorkbench(FreeCADBuddyWorkbench())
except Exception:  # noqa: BLE001 - no GUI (structural import / headless): skip registration
    logger.debug("FreeCADGui unavailable; workbench not registered", exc_info=True)


def _deferred_start(deadline: float | None = None) -> None:
    """Start the bridge once ``FreeCAD.GuiUp``; re-poll until then, capped at 60 s."""
    try:
        import FreeCAD
        from PySide import QtCore
    except Exception:  # noqa: BLE001 - no FreeCAD/Qt: nothing to start
        return

    if deadline is None:
        deadline = time.monotonic() + _START_DEADLINE_S

    if not getattr(FreeCAD, "GuiUp", False):
        if time.monotonic() >= deadline:
            sys.stderr.write("freecad-buddy: GUI never came up within 60 s; bridge not started\n")
            return
        QtCore.QTimer.singleShot(_POLL_MS, lambda: _deferred_start(deadline))
        return

    from freecad_buddy.hosts.gui_addon.bootstrap import start_bridge

    start_bridge()


try:
    from PySide import QtCore

    QtCore.QTimer.singleShot(0, _deferred_start)
except Exception:  # noqa: BLE001 - no Qt (structural import): skip deferred start
    logger.debug("PySide unavailable; deferred start not scheduled", exc_info=True)
