"""``resolve_env_overlay``: an env var that is set wins, else the preference, else the default."""

from pathlib import Path

from freecad_buddy.usecases.operator_settings import (
    PreferenceValues,
    environment_overrides,
    resolve_env_overlay,
)

DEFAULT_DIR = Path("C:/Users/operator/AppData/Roaming/FreeCAD/v1-1/freecad-buddy")


def test_Should_write_auto_approve_0_When_the_preference_is_off_and_the_env_is_unset():
    # Arrange
    prefs = PreferenceValues(auto_approve=False)

    # Act
    overlay = resolve_env_overlay({}, prefs, DEFAULT_DIR)

    # Assert
    assert overlay["FREECAD_BUDDY_AUTO_APPROVE"] == "0"


def test_Should_omit_auto_approve_When_the_env_sets_it():
    # Arrange
    environ = {"FREECAD_BUDDY_AUTO_APPROVE": "1"}
    prefs = PreferenceValues(auto_approve=False)

    # Act
    overlay = resolve_env_overlay(environ, prefs, DEFAULT_DIR)

    # Assert
    assert "FREECAD_BUDDY_AUTO_APPROVE" not in overlay


def test_Should_place_the_audit_log_and_workdir_under_the_data_dir_When_nothing_is_configured():
    # Arrange
    prefs = PreferenceValues()

    # Act
    overlay = resolve_env_overlay({}, prefs, DEFAULT_DIR)

    # Assert
    assert overlay["FREECAD_BUDDY_AUDIT_LOG"] == str(DEFAULT_DIR / "audit.jsonl")
    assert overlay["FREECAD_BUDDY_WORKDIR"] == str(DEFAULT_DIR / "workdir")


def test_Should_use_the_audit_log_preference_When_it_is_set():
    # Arrange
    prefs = PreferenceValues(audit_log_path="D:/logs/audit.jsonl")

    # Act
    overlay = resolve_env_overlay({}, prefs, DEFAULT_DIR)

    # Assert
    assert overlay["FREECAD_BUDDY_AUDIT_LOG"] == "D:/logs/audit.jsonl"


def test_Should_write_the_default_flags_When_the_preferences_are_defaults():
    # Arrange
    prefs = PreferenceValues()

    # Act
    overlay = resolve_env_overlay({}, prefs, DEFAULT_DIR)

    # Assert
    assert overlay["FREECAD_BUDDY_AUTO_APPROVE"] == "1"
    assert overlay["FREECAD_BUDDY_SCRIPT_EXEC"] == "1"
    assert "FREECAD_BUDDY_UNATTENDED" not in overlay
    assert "FREECAD_BUDDY_SCRIPT_EXEC_UNATTENDED" not in overlay
    assert "FREECAD_BUDDY_NO_AUTO_MCP" not in overlay
    assert "FREECAD_BUDDY_MCP_CMD" not in overlay


def test_Should_write_no_auto_mcp_When_auto_start_is_off():
    # Arrange
    prefs = PreferenceValues(auto_start_mcp=False)

    # Act
    overlay = resolve_env_overlay({}, prefs, DEFAULT_DIR)

    # Assert
    assert overlay["FREECAD_BUDDY_NO_AUTO_MCP"] == "1"


def test_Should_write_script_exec_0_and_the_mcp_command_When_the_preferences_set_them():
    # Arrange
    prefs = PreferenceValues(script_exec=False, mcp_command="uv run freecad-buddy serve")

    # Act
    overlay = resolve_env_overlay({}, prefs, DEFAULT_DIR)

    # Assert
    assert overlay["FREECAD_BUDDY_SCRIPT_EXEC"] == "0"
    assert overlay["FREECAD_BUDDY_MCP_CMD"] == "uv run freecad-buddy serve"


def test_Should_return_an_empty_overlay_When_the_env_sets_every_variable():
    # Arrange
    environ = {
        "FREECAD_BUDDY_AUTO_APPROVE": "0",
        "FREECAD_BUDDY_SCRIPT_EXEC": "1",
        "FREECAD_BUDDY_NO_AUTO_MCP": "1",
        "FREECAD_BUDDY_MCP_CMD": "custom",
        "FREECAD_BUDDY_AUDIT_LOG": "audit.jsonl",
        "FREECAD_BUDDY_WORKDIR": "work",
    }
    prefs = PreferenceValues(auto_start_mcp=False, mcp_command="other")

    # Act
    overlay = resolve_env_overlay(environ, prefs, DEFAULT_DIR)

    # Assert
    assert overlay == {}


def test_Should_use_the_default_audit_log_When_the_env_sets_it_empty():
    # Arrange
    environ = {"FREECAD_BUDDY_AUDIT_LOG": "", "FREECAD_BUDDY_WORKDIR": ""}
    prefs = PreferenceValues()

    # Act
    overlay = resolve_env_overlay(environ, prefs, DEFAULT_DIR)

    # Assert
    assert overlay["FREECAD_BUDDY_AUDIT_LOG"] == str(DEFAULT_DIR / "audit.jsonl")
    assert overlay["FREECAD_BUDDY_WORKDIR"] == str(DEFAULT_DIR / "workdir")


def test_Should_apply_the_auto_start_and_command_preferences_When_the_env_sets_them_empty():
    # Arrange
    environ = {"FREECAD_BUDDY_NO_AUTO_MCP": "", "FREECAD_BUDDY_MCP_CMD": ""}
    prefs = PreferenceValues(auto_start_mcp=False, mcp_command="custom-proxy")

    # Act
    overlay = resolve_env_overlay(environ, prefs, DEFAULT_DIR)

    # Assert
    assert overlay["FREECAD_BUDDY_NO_AUTO_MCP"] == "1"
    assert overlay["FREECAD_BUDDY_MCP_CMD"] == "custom-proxy"


def test_Should_keep_an_empty_flag_When_the_env_sets_auto_approve_or_script_exec_empty():
    # Arrange
    environ = {"FREECAD_BUDDY_AUTO_APPROVE": "", "FREECAD_BUDDY_SCRIPT_EXEC": ""}
    prefs = PreferenceValues(script_exec=True)

    # Act
    overlay = resolve_env_overlay(environ, prefs, DEFAULT_DIR)

    # Assert
    assert "FREECAD_BUDDY_AUTO_APPROVE" not in overlay
    assert "FREECAD_BUDDY_SCRIPT_EXEC" not in overlay


def test_Should_list_only_the_variables_that_count_as_set_When_reading_overrides():
    # Arrange
    environ = {
        "FREECAD_BUDDY_AUTO_APPROVE": "",
        "FREECAD_BUDDY_UNATTENDED": "",
        "FREECAD_BUDDY_SCRIPT_EXEC_UNATTENDED": "1",
        "FREECAD_BUDDY_AUDIT_LOG": "D:/audit.jsonl",
        "FREECAD_BUDDY_MCP_CMD": "",
        "PATH": "C:/Windows",
    }

    # Act
    overrides = environment_overrides(environ)

    # Assert
    assert overrides == {
        "FREECAD_BUDDY_AUTO_APPROVE": "",
        "FREECAD_BUDDY_UNATTENDED": "",
        "FREECAD_BUDDY_SCRIPT_EXEC_UNATTENDED": "1",
        "FREECAD_BUDDY_AUDIT_LOG": "D:/audit.jsonl",
    }
