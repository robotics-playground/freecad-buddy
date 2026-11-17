"""A stand-in for ``FreeCAD.Console`` in a GUI session, shared by the notification-area tests."""

from freecad_buddy.usecases import shim


class NotificationAreaConsole:
    """Holds the notification observer that only a GUI session attaches.

    FreeCADCmd attaches no notification area, so the real console has nothing to switch. The
    ``Notification`` level starts off, as a human who silenced plain notifications leaves it, so a
    restore that forces every level on cannot pass for one that puts the saved values back.
    """

    def __init__(self):
        self.levels = dict.fromkeys(shim._NOTIFICATION_LEVELS, True)
        self.levels["Notification"] = False

    def GetStatus(self, observer, level):  # noqa: N802 - FreeCAD.Console API name
        return self.levels[level] if observer == shim._NOTIFICATION_OBSERVER else None

    def SetStatus(self, observer, level, status):  # noqa: N802 - FreeCAD.Console API name
        if observer == shim._NOTIFICATION_OBSERVER:
            self.levels[level] = status
