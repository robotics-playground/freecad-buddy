"""The FreeCAD Buddy page in Edit > Preferences.

FreeCAD builds the page from ``PreferencesPage().form`` and calls ``loadSettings`` when the dialog
opens and ``saveSettings`` on OK or Apply. Tool calls read ``RoundToDisplay`` on every call, so
that change applies to the next call. The bridge reads the other settings once at start, so they
apply after a restart; a ``FREECAD_BUDDY_*`` environment variable overrides the matching field.
"""

from __future__ import annotations

import FreeCAD
from PySide import QtWidgets

from freecad_buddy.usecases.capabilities import AUTO_APPROVE_VARIABLE
from freecad_buddy.usecases.operator_settings import (
    ALLOW_EXEC_VARIABLE,
    AUDIT_LOG_VARIABLE,
    MCP_CMD_VARIABLE,
    NO_AUTO_MCP_VARIABLE,
)
from freecad_buddy.usecases.shim import (
    ALLOW_EXEC_KEY,
    AUDIT_LOG_PATH_KEY,
    AUTO_APPROVE_KEY,
    AUTO_START_MCP_KEY,
    BUDDY_PARAM_PATH,
    MCP_COMMAND_KEY,
    ROUND_TO_DISPLAY_KEY,
    UV_PATH_KEY,
    read_operator_preferences,
)


class PreferencesPage:
    def __init__(self, parent=None) -> None:
        self.form = QtWidgets.QWidget(parent)
        self.form.setWindowTitle("FreeCAD Buddy")
        self.round_to_display = QtWidgets.QCheckBox("Round numbers to FreeCAD display precision")
        self.round_to_display.setToolTip(
            "Round every number in a tool result to the Decimals setting in General > Units, and "
            "compare checks at that precision. Off: results and checks use full floats."
        )
        self.auto_approve = QtWidgets.QCheckBox("Auto-approve mutations")
        self.auto_approve.setToolTip(
            "On: a sketch_* or feature_* call applies without a preview. Off: every mutation needs "
            "the preview_id of a preview_dry_run. FREECAD_BUDDY_AUTO_APPROVE overrides this."
        )
        self.allow_exec = QtWidgets.QCheckBox("Allow debug_exec")
        self.allow_exec.setToolTip("Registers debug_exec. FREECAD_BUDDY_ALLOW_EXEC overrides this.")
        exec_warning = QtWidgets.QLabel(
            "debug_exec runs any Python inside FreeCAD. Turn it on only for trusted bring-up, "
            "never for an unattended agent."
        )
        exec_warning.setWordWrap(True)
        exec_warning.setStyleSheet("color: red;")
        self.auto_start_mcp = QtWidgets.QCheckBox("Start the MCP server with FreeCAD")
        self.auto_start_mcp.setToolTip(
            "Serve http://127.0.0.1:8765/mcp while FreeCAD runs. "
            "FREECAD_BUDDY_NO_AUTO_MCP overrides this."
        )
        self.mcp_command = QtWidgets.QLineEdit()
        self.mcp_command.setToolTip(
            "Command that starts the MCP server. Empty: found automatically. The value is split on "
            "spaces with no quoting, so a path that contains a space is not supported. "
            "FREECAD_BUDDY_MCP_CMD overrides this."
        )
        self.uv_path = QtWidgets.QLineEdit()
        self.uv_path.setToolTip("Path to the uv executable. Empty: uv on PATH.")
        self.audit_log_path = QtWidgets.QLineEdit()
        self.audit_log_path.setToolTip(
            "Audit log file. Empty: audit.jsonl in the freecad-buddy folder of the FreeCAD user "
            "data directory. FREECAD_BUDDY_AUDIT_LOG overrides this."
        )
        note = QtWidgets.QLabel("Restart FreeCAD to apply (rounding applies at once).")
        note.setWordWrap(True)
        self.overridden = QtWidgets.QLabel()
        self.overridden.setWordWrap(True)
        self.overridden.hide()

        fields = QtWidgets.QFormLayout()
        fields.addRow("MCP command", self.mcp_command)
        fields.addRow("uv path", self.uv_path)
        fields.addRow("Audit log file", self.audit_log_path)
        layout = QtWidgets.QVBoxLayout(self.form)
        layout.addWidget(self.round_to_display)
        layout.addWidget(self.auto_approve)
        layout.addWidget(self.allow_exec)
        layout.addWidget(exec_warning)
        layout.addWidget(self.auto_start_mcp)
        layout.addLayout(fields)
        layout.addWidget(note)
        layout.addWidget(self.overridden)
        layout.addStretch()

    def loadSettings(self) -> None:  # noqa: N802 - FreeCAD preference page API
        preferences = FreeCAD.ParamGet(BUDDY_PARAM_PATH)
        self.round_to_display.setChecked(preferences.GetBool(ROUND_TO_DISPLAY_KEY, True))
        values = read_operator_preferences()
        self.auto_approve.setChecked(values.auto_approve)
        self.allow_exec.setChecked(values.allow_exec)
        self.auto_start_mcp.setChecked(values.auto_start_mcp)
        self.mcp_command.setText(values.mcp_command)
        self.uv_path.setText(values.uv_path)
        self.audit_log_path.setText(values.audit_log_path)
        self._show_environment_overrides()

    def _show_environment_overrides(self) -> None:
        """Show the variable's value in each field it sets, disable that field, and name it."""
        from freecad_buddy.hosts.gui_addon.bootstrap import startup_overrides

        overrides = startup_overrides()
        fields = {
            AUTO_APPROVE_VARIABLE: self.auto_approve,
            ALLOW_EXEC_VARIABLE: self.allow_exec,
            NO_AUTO_MCP_VARIABLE: self.auto_start_mcp,
            MCP_CMD_VARIABLE: self.mcp_command,
            AUDIT_LOG_VARIABLE: self.audit_log_path,
        }
        for name, field in fields.items():
            field.setEnabled(name not in overrides)
            if name not in overrides:
                continue
            value = overrides[name]
            if field is self.auto_start_mcp:
                field.setChecked(False)  # the host does not start the server when the key is set
            elif isinstance(field, QtWidgets.QCheckBox):
                field.setChecked(value == "1")
            else:
                field.setText(value)
        shown = [f"{name}='{overrides[name]}'" for name in fields if name in overrides]
        self.overridden.setText(
            "Set by the environment, so the matching fields are disabled: " + ", ".join(shown)
        )
        self.overridden.setVisible(bool(shown))

    def saveSettings(self) -> None:  # noqa: N802 - FreeCAD preference page API
        preferences = FreeCAD.ParamGet(BUDDY_PARAM_PATH)
        preferences.SetBool(ROUND_TO_DISPLAY_KEY, self.round_to_display.isChecked())
        preferences.SetString(UV_PATH_KEY, self.uv_path.text().strip())
        # A disabled field shows the environment's value, so saving it would overwrite the
        # stored preference with a value the operator never chose.
        for key, box in (
            (AUTO_APPROVE_KEY, self.auto_approve),
            (ALLOW_EXEC_KEY, self.allow_exec),
            (AUTO_START_MCP_KEY, self.auto_start_mcp),
        ):
            if box.isEnabled():
                preferences.SetBool(key, box.isChecked())
        for key, line in (
            (MCP_COMMAND_KEY, self.mcp_command),
            (AUDIT_LOG_PATH_KEY, self.audit_log_path),
        ):
            if line.isEnabled():
                preferences.SetString(key, line.text().strip())
