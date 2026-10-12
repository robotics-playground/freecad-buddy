"""Operator settings at bridge start, and the MCP-proxy command order (stdlib unittest).

``bootstrap`` imports PySide through ``pump``, so it is importable only under FreeCAD. The
start-order cases stop ``start_bridge`` at the capability read, so no listener or Qt object is
built.
"""

import hashlib
import os
import tempfile
import threading
import unittest
from pathlib import Path
from unittest import mock

import FreeCAD  # noqa: F401 - FreeCAD init puts its Ext/PySide shim on sys.path for pump.py

from freecad_buddy.hosts.gui_addon import bootstrap, managed_venv
from freecad_buddy.usecases import shim
from freecad_buddy.usecases.capabilities import Capabilities, exec_registered
from freecad_buddy.usecases.operator_settings import (
    OPERATOR_VARIABLES,
    PreferenceValues,
    resolve_env_overlay,
)


class _StopAtCapabilityRead(Exception):
    pass


class _TempEnvTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.base = Path(self._tmp.name).resolve()
        env = mock.patch.dict(os.environ)
        env.start()
        self.addCleanup(env.stop)
        for name in (*OPERATOR_VARIABLES, "FREECAD_BUDDY_REPO", "FREECAD_BUDDY_SRC"):
            os.environ.pop(name, None)

    def _patch(self, target, name, **kwargs):
        patcher = mock.patch.object(target, name, **kwargs)
        self.addCleanup(patcher.stop)
        return patcher.start()


class StartBridgeSettingsTest(_TempEnvTest):
    def setUp(self):
        super().setUp()
        self.data_dir = self.base / "freecad-buddy"
        self.capability_env = {}
        self.sweep_workdir = []
        self._patch(bootstrap, "_listener", new=None)
        self._patch(bootstrap, "_configure_file_logging")
        self._patch(bootstrap, "_data_dir", return_value=self.data_dir)
        self._patch(
            bootstrap.shim, "read_operator_preferences",
            return_value=PreferenceValues(auto_approve=False),
        )
        self._patch(bootstrap, "sweep_temp_dir", side_effect=self._record_sweep)
        self._real_capability_read = bootstrap.Capabilities.from_env
        self.capability_read = self._patch(
            bootstrap.Capabilities, "from_env", side_effect=self._record_capability_read
        )

    def _record_sweep(self):
        self.sweep_workdir.append(os.environ.get("FREECAD_BUDDY_WORKDIR"))
        return 0

    def _record_capability_read(self, environ, **kwargs):
        self.capability_env.update(environ)
        raise _StopAtCapabilityRead

    def test_Should_read_the_preference_at_the_capability_read_When_the_env_is_unset(self):
        # Arrange
        expected_audit_log = str(self.data_dir / "audit.jsonl")

        # Act
        with self.assertRaises(_StopAtCapabilityRead):
            bootstrap.start_bridge()

        # Assert
        self.assertEqual(self.capability_env["FREECAD_BUDDY_AUTO_APPROVE"], "0")
        self.assertEqual(self.capability_env["FREECAD_BUDDY_AUDIT_LOG"], expected_audit_log)

    def test_Should_keep_the_env_value_When_the_env_sets_auto_approve(self):
        # Arrange
        os.environ["FREECAD_BUDDY_AUTO_APPROVE"] = "1"

        # Act
        with self.assertRaises(_StopAtCapabilityRead):
            bootstrap.start_bridge()

        # Assert
        self.assertEqual(self.capability_env["FREECAD_BUDDY_AUTO_APPROVE"], "1")

    def _start_logs_past_the_capability_read(self) -> list[str]:
        self.capability_read.side_effect = self._real_capability_read
        self._patch(bootstrap, "QtMainThreadExecutor", side_effect=_StopAtCapabilityRead)
        with self.assertLogs(bootstrap.logger, "INFO") as logs:
            with self.assertRaises(_StopAtCapabilityRead):
                bootstrap.start_bridge()
        return [record.getMessage() for record in logs.records]

    def test_Should_log_the_script_exec_warning_When_exec_is_on(self):
        # Arrange
        expected = bootstrap.SCRIPT_EXEC_WARNING

        # Act
        messages = self._start_logs_past_the_capability_read()

        # Assert
        self.assertEqual(messages.count(expected), 1)

    def test_Should_not_log_the_script_exec_warning_When_the_env_turns_exec_off(self):
        # Arrange
        os.environ["FREECAD_BUDDY_SCRIPT_EXEC"] = "0"

        # Act
        messages = self._start_logs_past_the_capability_read()

        # Assert
        self.assertNotIn(bootstrap.SCRIPT_EXEC_WARNING, messages)

    def test_Should_sweep_the_data_dir_workdir_When_no_workdir_is_configured(self):
        # Arrange
        expected = str(self.data_dir / "workdir")

        # Act
        with self.assertRaises(_StopAtCapabilityRead):
            bootstrap.start_bridge()

        # Assert
        self.assertEqual(self.sweep_workdir, [expected])


class McpProxyCommandOrderTest(_TempEnvTest):
    def setUp(self):
        super().setUp()
        self.venv = self.base / "FreeCADBuddy" / "venv"
        self.wheel = self.base / "wheels" / "freecad_buddy-0.0.1-py3-none-any.whl"
        self.wheel.parent.mkdir(parents=True)
        self.wheel.write_bytes(b"wheel-0.0.1")
        self.repo_python = self.base / "repo" / ".venv" / "python"
        self._patch(bootstrap, "_managed_venv_dir", return_value=self.venv)
        self.discover = self._patch(bootstrap, "_discover_external_python", return_value=None)

    def _provision_managed_venv(self) -> Path:
        python = managed_venv.venv_python(self.venv)
        python.parent.mkdir(parents=True)
        python.write_bytes(b"")
        digest = hashlib.sha256(self.wheel.read_bytes()).hexdigest()
        (self.venv / managed_venv._MARKER).write_text(digest, encoding="utf-8")
        return python

    def test_Should_run_the_managed_venv_When_it_matches_the_bundled_wheel(self):
        # Arrange
        python = self._provision_managed_venv()

        # Act
        command = bootstrap._mcp_proxy_command(None, self.wheel)

        # Assert
        self.assertEqual(command[0], str(python))

    def test_Should_return_none_When_the_managed_venv_is_from_another_wheel(self):
        # Arrange
        self._provision_managed_venv()
        self.wheel.write_bytes(b"wheel-0.0.2")

        # Act
        command = bootstrap._mcp_proxy_command(None, self.wheel)

        # Assert
        self.assertIsNone(command)

    def test_Should_run_the_repo_venv_When_the_dev_install_finds_one(self):
        # Arrange
        self._provision_managed_venv()
        self.discover.return_value = self.repo_python

        # Act
        command = bootstrap._mcp_proxy_command(None, self.wheel)

        # Assert
        self.assertEqual(command[0], str(self.repo_python))

    def test_Should_run_the_explicit_command_When_mcp_cmd_is_set(self):
        # Arrange
        self._provision_managed_venv()
        self.discover.return_value = self.repo_python
        os.environ["FREECAD_BUDDY_MCP_CMD"] = "custom-proxy --port 8765"

        # Act
        command = bootstrap._mcp_proxy_command(None, self.wheel)

        # Assert
        self.assertEqual(command, ["custom-proxy", "--port", "8765"])

    def test_Should_run_uv_on_the_repo_When_freecad_buddy_repo_is_set(self):
        # Arrange
        self._provision_managed_venv()
        repo = self.base / "repo"
        uv = self.base / "uv.exe"
        os.environ["FREECAD_BUDDY_REPO"] = str(repo)

        # Act
        command = bootstrap._mcp_proxy_command(uv, self.wheel)

        # Assert
        self.assertEqual(command[:4], [str(uv), "run", "--project", str(repo)])


class StartMcpProxyTest(_TempEnvTest):
    def setUp(self):
        super().setUp()
        self.uv = self.base / "uv.exe"
        self.wheel = self.base / "wheels" / "freecad_buddy-0.0.1-py3-none-any.whl"
        self._patch(bootstrap, "_port_open", return_value=False)
        self._patch(bootstrap, "_mcp_proxy_command", return_value=None)
        self._patch(bootstrap.managed_venv, "bundled_wheel", return_value=self.wheel)
        self.spawn = self._patch(bootstrap, "_spawn_mcp_proxy")
        self.provision = self._patch(bootstrap, "_provision_and_spawn")
        self._patch(bootstrap, "_provisioner", new=None)

    def test_Should_provision_on_a_background_thread_When_a_release_install_has_no_venv(self):
        # Arrange
        self._patch(bootstrap.managed_venv, "find_uv", return_value=self.uv)

        # Act
        bootstrap._start_mcp_proxy("")
        bootstrap._provisioner.join(timeout=5)

        # Assert
        self.provision.assert_called_once_with(self.uv, self.wheel)
        self.spawn.assert_not_called()

    def test_Should_start_no_thread_and_name_the_preference_When_uv_is_missing(self):
        # Arrange
        self._patch(bootstrap.managed_venv, "find_uv", return_value=None)

        # Act
        with self.assertLogs(bootstrap.logger, level="WARNING") as logs:
            bootstrap._start_mcp_proxy("")

        # Assert
        self.assertIsNone(bootstrap._provisioner)
        self.provision.assert_not_called()
        self.assertIn("Edit > Preferences > FreeCAD Buddy", logs.output[0])


class ProvisionAndSpawnTest(_TempEnvTest):
    def setUp(self):
        super().setUp()
        self.venv = self.base / "FreeCADBuddy" / "venv"
        self.uv = self.base / "uv.exe"
        self.wheel = self.base / "wheels" / "freecad_buddy-0.0.1-py3-none-any.whl"
        self._patch(bootstrap, "_managed_venv_dir", return_value=self.venv)
        self._patch(bootstrap, "_log_file_path", return_value=self.base / "addon.log")
        self._patch(bootstrap, "_port_open", return_value=False)
        self._patch(bootstrap, "_cancel_provisioning", new=threading.Event())
        self.spawn = self._patch(bootstrap, "_spawn_mcp_proxy")

    def test_Should_spawn_the_proxy_from_the_venv_When_provisioning_succeeds(self):
        # Arrange
        self._patch(bootstrap.managed_venv, "provision", return_value=True)
        expected = [str(managed_venv.venv_python(self.venv)), *bootstrap._SERVE_ARGS]

        # Act
        bootstrap._provision_and_spawn(self.uv, self.wheel)

        # Assert
        self.spawn.assert_called_once_with(expected)

    def test_Should_not_spawn_When_provisioning_fails(self):
        # Arrange
        self._patch(bootstrap.managed_venv, "provision", return_value=False)

        # Act
        bootstrap._provision_and_spawn(self.uv, self.wheel)

        # Assert
        self.spawn.assert_not_called()

    def test_Should_not_spawn_When_provisioning_raises(self):
        # Arrange
        self._patch(bootstrap.managed_venv, "provision", side_effect=OSError("disk full"))

        # Act
        with self.assertLogs(bootstrap.logger, level="ERROR"):
            bootstrap._provision_and_spawn(self.uv, self.wheel)

        # Assert
        self.spawn.assert_not_called()


class AddonRootTest(unittest.TestCase):
    def test_Should_hold_the_package_When_resolved_from_bootstrap(self):
        # Arrange
        expected = Path(bootstrap.__file__).resolve()

        # Act
        root = bootstrap._addon_root()

        # Assert
        self.assertEqual(root / "freecad_buddy" / "hosts" / "gui_addon" / "bootstrap.py", expected)


# A user.cfg can still hold this key; nothing reads it, so a stored value must not turn exec off.
_STALE_ALLOW_EXEC_KEY = "AllowExec"
_BOOL_KEYS = (
    shim.AUTO_APPROVE_KEY,
    shim.SCRIPT_EXEC_KEY,
    shim.AUTO_START_MCP_KEY,
    _STALE_ALLOW_EXEC_KEY,
)
_STRING_KEYS = (shim.MCP_COMMAND_KEY, shim.UV_PATH_KEY, shim.AUDIT_LOG_PATH_KEY)


class ReadOperatorPreferencesTest(unittest.TestCase):
    """The addon's preference group; the user's own values are restored after each case."""

    def setUp(self):
        self.group = FreeCAD.ParamGet(shim.BUDDY_PARAM_PATH)
        bools, strings = self.group.GetBools(), self.group.GetStrings()
        self.saved_bools = {key: self.group.GetBool(key) for key in _BOOL_KEYS if key in bools}
        self.saved_strings = {
            key: self.group.GetString(key) for key in _STRING_KEYS if key in strings
        }
        for key in _BOOL_KEYS:
            self.group.RemBool(key)
        for key in _STRING_KEYS:
            self.group.RemString(key)

    def tearDown(self):
        for key in _BOOL_KEYS:
            self.group.RemBool(key)
        for key in _STRING_KEYS:
            self.group.RemString(key)
        for key, value in self.saved_bools.items():
            self.group.SetBool(key, value)
        for key, value in self.saved_strings.items():
            self.group.SetString(key, value)

    def test_Should_return_the_defaults_When_no_key_is_stored(self):
        # Arrange
        expected = PreferenceValues()

        # Act
        values = shim.read_operator_preferences()

        # Assert
        self.assertEqual(values, expected)

    def test_Should_map_each_key_When_every_key_is_stored(self):
        # Arrange
        self.group.SetBool(shim.AUTO_APPROVE_KEY, False)
        self.group.SetBool(shim.SCRIPT_EXEC_KEY, False)
        self.group.SetBool(shim.AUTO_START_MCP_KEY, False)
        self.group.SetString(shim.MCP_COMMAND_KEY, "custom-proxy")
        self.group.SetString(shim.UV_PATH_KEY, "D:/tools/uv.exe")
        self.group.SetString(shim.AUDIT_LOG_PATH_KEY, "D:/logs/audit.jsonl")

        # Act
        values = shim.read_operator_preferences()

        # Assert
        self.assertEqual(
            values,
            PreferenceValues(
                auto_approve=False,
                script_exec=False,
                auto_start_mcp=False,
                mcp_command="custom-proxy",
                uv_path="D:/tools/uv.exe",
                audit_log_path="D:/logs/audit.jsonl",
            ),
        )

    def test_Should_register_script_exec_When_only_a_stale_allow_exec_false_is_stored(self):
        # Arrange
        self.group.SetBool(_STALE_ALLOW_EXEC_KEY, False)

        # Act
        values = shim.read_operator_preferences()
        overlay = resolve_env_overlay({}, values, Path(tempfile.gettempdir()))
        registered = exec_registered(Capabilities.from_env(overlay))

        # Assert
        self.assertTrue(values.script_exec)
        self.assertTrue(registered)


class StopBridgeTest(_TempEnvTest):
    def test_Should_cancel_and_join_provisioning_When_the_bridge_stops(self):
        # Arrange
        cancel = self._patch(bootstrap, "_cancel_provisioning", new=threading.Event())
        provisioner = mock.Mock(spec=threading.Thread)
        self._patch(bootstrap, "_provisioner", new=provisioner)
        self._patch(bootstrap, "_mcp_proxy", new=None)
        self._patch(bootstrap, "_listener", new=None)

        # Act
        bootstrap.stop_bridge()

        # Assert
        self.assertTrue(cancel.is_set())
        provisioner.join.assert_called_once()
        self.assertIsNone(bootstrap._provisioner)


if __name__ == "__main__":
    unittest.main()
