"""``scripts/automation/fcb_py.sh``: argument and environment rewriting for the container, with a
fake ``docker`` that prints what it receives (no container, no FreeCAD)."""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
WRAPPER = REPO_ROOT / "scripts" / "automation" / "fcb_py.sh"
BASH = shutil.which("bash")

pytestmark = pytest.mark.skipif(BASH is None, reason="needs bash")


def _run(tmp_path: Path, args: list[str], environment: dict[str, str]):
    fake_docker = tmp_path / "docker"
    fake_docker.write_text('#!/bin/bash\nprintf "%s\\n" "$@"\n', encoding="utf-8", newline="\n")
    fake_docker.chmod(0o755)
    env = {k: v for k, v in os.environ.items() if not k.startswith("FREECAD_BUDDY_")}
    env.pop("PROJECT_ROOT", None)
    env["MSYS_NO_PATHCONV"] = "1"  # Git Bash on Windows must not rewrite the test paths
    env["PATH"] = f"{tmp_path}{os.pathsep}{env['PATH']}"
    env.update(environment)
    # The wrapper is read through its POSIX path so a Windows checkout runs under Git Bash too.
    script = WRAPPER.as_posix()
    return subprocess.run([BASH, script, *args], capture_output=True, text=True, env=env)


def test_Should_rewrite_the_repository_prefix_When_arguments_and_variables_hold_it(tmp_path):
    # Arrange
    root = "/work/freecad-buddy"
    environment = {
        "PROJECT_ROOT": root,
        "FREECAD_BUDDY_WORKDIR": f"{root}/tests/uat/run/x/workdir",
    }

    # Act
    done = _run(tmp_path, ["-c", f"open({root}/a.txt)"], environment)

    # Assert
    lines = done.stdout.splitlines()
    assert done.returncode == 0
    assert "FREECAD_BUDDY_WORKDIR=/repo/tests/uat/run/x/workdir" in lines
    assert "open(/repo/a.txt)" in lines
    assert lines[-3:-1] == ["fcb-py", "-c"]


def test_Should_rewrite_the_backslash_spelling_When_the_argument_uses_it(tmp_path):
    # Arrange
    environment = {"PROJECT_ROOT": "/work/freecad-buddy"}

    # Act
    done = _run(tmp_path, ["\\work\\freecad-buddy\\tests"], environment)

    # Assert
    assert done.returncode == 0
    assert "/repo/tests" in done.stdout.splitlines()


def test_Should_exit_2_naming_the_variable_When_project_root_is_not_set(tmp_path):
    # Arrange
    environment: dict[str, str] = {}

    # Act
    done = _run(tmp_path, ["-c", "pass"], environment)

    # Assert
    assert done.returncode == 2
    assert "PROJECT_ROOT is not set" in done.stderr


def test_Should_warn_and_pass_the_value_on_When_a_variable_holds_a_path_outside_the_repository(
    tmp_path,
):
    # Arrange
    environment = {
        "PROJECT_ROOT": "/work/freecad-buddy",
        "FREECAD_BUDDY_AUDIT_LOG": "C:\\logs\\audit.jsonl",
    }

    # Act
    done = _run(tmp_path, ["-c", "pass"], environment)

    # Assert
    assert done.returncode == 0
    assert "FREECAD_BUDDY_AUDIT_LOG=C:\\logs\\audit.jsonl" in done.stdout.splitlines()
    assert "FREECAD_BUDDY_AUDIT_LOG=C:\\logs\\audit.jsonl looks like a host path" in done.stderr


def test_Should_run_docker_exec_as_cua_with_stdin_and_the_addon_path_When_it_starts(tmp_path):
    # Arrange
    environment = {"PROJECT_ROOT": "/work/freecad-buddy"}

    # Act
    done = _run(tmp_path, ["-m", "freecad_buddy.hosts.main"], environment)

    # Assert
    lines = done.stdout.splitlines()
    assert lines[:4] == ["exec", "-i", "-u", "cua"]
    assert "PYTHONPATH=/home/cua/.local/share/FreeCAD/v1-1/Mod/FreeCADBuddy" in lines
    assert lines[-4:] == ["fcb-desktop", "fcb-py", "-m", "freecad_buddy.hosts.main"]


def test_Should_use_the_addon_override_When_fcb_addon_is_set(tmp_path):
    # Arrange
    environment = {"PROJECT_ROOT": "/work/freecad-buddy", "FCB_ADDON": "/opt/other-addon"}

    # Act
    done = _run(tmp_path, ["-c", "pass"], environment)

    # Assert
    assert "PYTHONPATH=/opt/other-addon" in done.stdout.splitlines()


def test_Should_keep_a_trailing_equals_sign_When_a_variable_value_ends_with_one(tmp_path):
    # Arrange
    environment = {"PROJECT_ROOT": "/work/freecad-buddy", "FREECAD_BUDDY_TOKEN": "abc="}

    # Act
    done = _run(tmp_path, ["-c", "pass"], environment)

    # Assert
    assert "FREECAD_BUDDY_TOKEN=abc=" in done.stdout.splitlines()


def test_Should_leave_a_sibling_folder_alone_When_its_name_starts_with_the_repository_path(
    tmp_path,
):
    # Arrange
    environment = {"PROJECT_ROOT": "/work/freecad-buddy"}

    # Act
    done = _run(tmp_path, ["/work/freecad-buddy-other/a", "/work/freecad-buddy"], environment)

    # Assert
    lines = done.stdout.splitlines()
    assert "/work/freecad-buddy-other/a" in lines
    assert lines[-1] == "/repo"


def test_Should_rewrite_a_path_below_the_root_When_project_root_has_a_trailing_slash(tmp_path):
    # Arrange
    environment = {"PROJECT_ROOT": "/work/freecad-buddy/"}

    # Act
    done = _run(tmp_path, ["/work/freecad-buddy/tests"], environment)

    # Assert
    assert done.stdout.splitlines()[-1] == "/repo/tests"
