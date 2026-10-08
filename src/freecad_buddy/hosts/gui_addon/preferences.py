"""The FreeCAD Buddy page in Edit > Preferences.

FreeCAD builds the page from ``PreferencesPage().form`` and calls ``loadSettings`` when the dialog
opens and ``saveSettings`` on OK or Apply. Tool calls read the stored value on every call, so a
change applies to the next call without a restart.
"""

from __future__ import annotations

import FreeCAD
from PySide import QtWidgets

from freecad_buddy.usecases.shim import BUDDY_PARAM_PATH, ROUND_TO_DISPLAY_KEY


class PreferencesPage:
    def __init__(self, parent=None) -> None:
        self.form = QtWidgets.QWidget(parent)
        self.form.setWindowTitle("FreeCAD Buddy")
        self.round_to_display = QtWidgets.QCheckBox("Round numbers to FreeCAD display precision")
        self.round_to_display.setToolTip(
            "Round every number in a tool result to the Decimals setting in General > Units, and "
            "compare checks at that precision. Off: results and checks use full floats."
        )
        layout = QtWidgets.QVBoxLayout(self.form)
        layout.addWidget(self.round_to_display)
        layout.addStretch()

    def loadSettings(self) -> None:  # noqa: N802 - FreeCAD preference page API
        preferences = FreeCAD.ParamGet(BUDDY_PARAM_PATH)
        self.round_to_display.setChecked(preferences.GetBool(ROUND_TO_DISPLAY_KEY, True))

    def saveSettings(self) -> None:  # noqa: N802 - FreeCAD preference page API
        preferences = FreeCAD.ParamGet(BUDDY_PARAM_PATH)
        preferences.SetBool(ROUND_TO_DISPLAY_KEY, self.round_to_display.isChecked())
