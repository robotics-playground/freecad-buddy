"""``managed_venv``: uv lookup, bundled wheel, currency marker and the provisioning lock.

``provision`` runs ``uv`` through ``_run``; the tests replace it with a fake that builds the venv
layout, so no subprocess runs.
"""

import os
import subprocess
import sys
import threading
import time
from pathlib import Path

import pytest

from freecad_buddy import __version__
from freecad_buddy.hosts.gui_addon import managed_venv


@pytest.fixture
def wheel(tmp_path):
    path = tmp_path / "addon" / "wheels" / f"freecad_buddy-{__version__}-py3-none-any.whl"
    path.parent.mkdir(parents=True)
    path.write_bytes(b"wheel-current")
    return path


@pytest.fixture
def fake_uv(monkeypatch):
    """Replace ``_run`` with a fake whose ``uv venv`` step creates the venv interpreter."""
    commands = []

    def _run(command, logfile, cancel):
        commands.append(command)
        if command[1] == "venv":
            python = managed_venv.venv_python(Path(command[-1]))
            python.parent.mkdir(parents=True, exist_ok=True)
            python.write_bytes(b"")
        return True

    monkeypatch.setattr(managed_venv, "_run", _run)
    return commands


def _provision(tmp_path, wheel):
    return managed_venv.provision(
        tmp_path / "uv.exe", wheel, tmp_path / "data" / "venv", tmp_path / "provision.log",
        threading.Event(),
    )


def test_Should_return_the_preferred_uv_When_the_preference_names_a_file(tmp_path, monkeypatch):
    # Arrange
    preferred = tmp_path / "uv.exe"
    preferred.write_bytes(b"")
    monkeypatch.setattr(managed_venv.shutil, "which", lambda name: None)

    # Act
    found = managed_venv.find_uv(str(preferred))

    # Assert
    assert found == preferred


def test_Should_return_uv_on_path_When_the_preference_names_no_file(tmp_path, monkeypatch):
    # Arrange
    on_path = str(tmp_path / "bin" / "uv")
    monkeypatch.setattr(managed_venv.shutil, "which", lambda name: on_path)

    # Act
    found = managed_venv.find_uv(str(tmp_path / "missing.exe"))

    # Assert
    assert found == Path(on_path)


def test_Should_return_none_When_uv_is_nowhere(monkeypatch):
    # Arrange
    monkeypatch.setattr(managed_venv.shutil, "which", lambda name: None)
    preferred = ""

    # Act
    found = managed_venv.find_uv(preferred)

    # Assert
    assert found is None


def test_Should_find_the_wheel_When_a_release_build_bundled_it(wheel):
    # Arrange
    addon_root = wheel.parent.parent

    # Act
    found = managed_venv.bundled_wheel(addon_root)

    # Assert
    assert found == wheel


def test_Should_pick_the_running_version_When_an_older_wheel_was_left_beside_it(tmp_path):
    # Arrange
    wheels = tmp_path / "addon" / "wheels"
    wheels.mkdir(parents=True)
    for version in ("0.0.9", "0.0.10"):
        (wheels / f"freecad_buddy-{version}-py3-none-any.whl").write_bytes(b"")

    # Act
    found = managed_venv.bundled_wheel(tmp_path / "addon", version="0.0.10")

    # Assert
    assert found == wheels / "freecad_buddy-0.0.10-py3-none-any.whl"


def test_Should_return_none_When_the_addon_has_no_wheels_folder(tmp_path):
    # Arrange
    addon_root = tmp_path / "addon"

    # Act
    found = managed_venv.bundled_wheel(addon_root)

    # Assert
    assert found is None


def test_Should_report_current_When_the_venv_was_provisioned_from_this_wheel(
    tmp_path, wheel, fake_uv
):
    # Arrange
    venv = tmp_path / "data" / "venv"
    _provision(tmp_path, wheel)

    # Act
    current = managed_venv.is_current(venv, wheel)

    # Assert
    assert current is True


def test_Should_report_stale_When_the_bundled_wheel_changed(tmp_path, wheel, fake_uv):
    # Arrange
    venv = tmp_path / "data" / "venv"
    _provision(tmp_path, wheel)
    wheel.write_bytes(b"wheel-next")

    # Act
    current = managed_venv.is_current(venv, wheel)

    # Assert
    assert current is False


def test_Should_report_stale_When_the_venv_has_no_marker(tmp_path, wheel):
    # Arrange
    venv = tmp_path / "data" / "venv"
    python = managed_venv.venv_python(venv)
    python.parent.mkdir(parents=True)
    python.write_bytes(b"")

    # Act
    current = managed_venv.is_current(venv, wheel)

    # Assert
    assert current is False


def test_Should_create_the_venv_and_install_the_wheel_When_provisioning(tmp_path, wheel, fake_uv):
    # Arrange
    venv = tmp_path / "data" / "venv"

    # Act
    ready = _provision(tmp_path, wheel)

    # Assert
    assert ready is True
    assert [command[1:3] for command in fake_uv] == [["venv", "--clear"], ["pip", "install"]]
    assert fake_uv[1][-1] == str(wheel)
    assert managed_venv.is_current(venv, wheel)
    assert not (venv.parent / "venv.lock").exists()


def test_Should_skip_When_another_instance_holds_a_fresh_lock(tmp_path, wheel, fake_uv):
    # Arrange
    lock = tmp_path / "data" / "venv.lock"
    lock.parent.mkdir(parents=True)
    lock.write_bytes(b"")

    # Act
    ready = _provision(tmp_path, wheel)

    # Assert
    assert ready is False
    assert fake_uv == []
    assert lock.exists()


def test_Should_take_over_the_lock_When_it_is_older_than_ten_minutes(tmp_path, wheel, fake_uv):
    # Arrange
    lock = tmp_path / "data" / "venv.lock"
    lock.parent.mkdir(parents=True)
    lock.write_bytes(b"")
    stale = time.time() - managed_venv.LOCK_STALE_S - 60
    os.utime(lock, (stale, stale))

    # Act
    ready = _provision(tmp_path, wheel)

    # Assert
    assert ready is True
    assert not lock.exists()


def test_Should_leave_the_venv_stale_When_a_uv_step_fails(tmp_path, wheel, monkeypatch):
    # Arrange
    monkeypatch.setattr(managed_venv, "_run", lambda command, logfile, cancel: False)
    venv = tmp_path / "data" / "venv"

    # Act
    ready = _provision(tmp_path, wheel)

    # Assert
    assert ready is False
    assert not managed_venv.is_current(venv, wheel)
    assert not (venv.parent / "venv.lock").exists()


def test_Should_stop_the_child_promptly_When_cancel_is_set(tmp_path, monkeypatch):
    # Arrange
    started = []
    real_popen = subprocess.Popen

    def _popen(*args, **kwargs):
        started.append(real_popen(*args, **kwargs))
        return started[-1]

    monkeypatch.setattr(managed_venv.subprocess, "Popen", _popen)
    cancel = threading.Event()
    cancel.set()
    command = [sys.executable, "-c", "import time; time.sleep(30)"]

    # Act
    with open(tmp_path / "run.log", "w", encoding="utf-8") as logfile:
        began = time.monotonic()
        finished = managed_venv._run(command, logfile, cancel)
        elapsed = time.monotonic() - began

    # Assert
    assert finished is False
    assert elapsed < 10
    assert started[0].poll() is not None


def test_Should_return_false_When_the_child_exits_non_zero(tmp_path):
    # Arrange
    command = [sys.executable, "-c", "raise SystemExit(3)"]

    # Act
    with open(tmp_path / "run.log", "w", encoding="utf-8") as logfile:
        finished = managed_venv._run(command, logfile, threading.Event())

    # Assert
    assert finished is False


def test_Should_start_a_venv_interpreter_When_FreeCAD_set_its_own_python_home(
    tmp_path, monkeypatch
):
    # Arrange
    freecad_resources = tmp_path / "FreeCAD.app" / "Contents" / "Resources"
    freecad_resources.mkdir(parents=True)
    monkeypatch.setenv("PYTHONHOME", str(freecad_resources))
    monkeypatch.setenv("PYTHONPATH", str(freecad_resources))
    command = [sys.executable, "-c", "pass"]

    # Act
    with open(tmp_path / "run.log", "w", encoding="utf-8") as logfile:
        finished = managed_venv._run(command, logfile, threading.Event())

    # Assert
    assert finished is True
