# FreeCAD runs this file through exec() during GUI init, before the event loop starts. The
# single-shot timer defers the listener until the loop runs and the main window is up.
import probe_server
from PySide import QtCore

QtCore.QTimer.singleShot(0, probe_server.start)
