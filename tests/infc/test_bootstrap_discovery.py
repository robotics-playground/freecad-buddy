"""Venv discovery for the MCP proxy across install layouts (stdlib unittest, run by run_tests.py).

``bootstrap`` imports PySide through ``pump``, so it is importable only under FreeCAD. Every case
builds a hermetic layout in a temp dir and passes a fake ``bootstrap.py`` path as ``here``.
"""

import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import FreeCAD  # noqa: F401 - FreeCAD init puts its Ext/PySide shim on sys.path for pump.py

from freecad_buddy.hosts.gui_addon import bootstrap

_ADDON_TAIL = ("freecad_buddy", "hosts", "gui_addon", "bootstrap.py")


def _make_venv_python(root: Path) -> Path:
    """Create an empty interpreter file where discovery probes for one, and return its path."""
    if os.name == "nt":
        python = root / ".venv" / "Scripts" / "python.exe"
    else:
        python = root / ".venv" / "bin" / "python"
    python.parent.mkdir(parents=True)
    python.write_bytes(b"")
    return python


class DiscoverExternalPythonTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.base = Path(self._tmp.name).resolve()
        self.repo = self.base / "repo"
        self.addon_root = self.base / "Mod" / "FreeCADBuddy"
        self.copy_here = self.addon_root.joinpath(*_ADDON_TAIL)
        env = mock.patch.dict(os.environ)
        env.start()
        self.addCleanup(env.stop)
        for name in ("FREECAD_BUDDY_REPO", "FREECAD_BUDDY_SRC"):
            os.environ.pop(name, None)

    def tearDown(self):
        self._tmp.cleanup()

    def _write_marker(self, text: str) -> None:
        self.addon_root.mkdir(parents=True)
        (self.addon_root / "repo-root.txt").write_text(text, encoding="utf-8")

    def test_Should_return_the_repo_venv_python_When_installed_as_a_src_junction(self):
        # Arrange
        expected = _make_venv_python(self.repo)
        here = self.repo.joinpath("src", *_ADDON_TAIL)

        # Act
        found = bootstrap._discover_external_python(here)

        # Assert
        self.assertEqual(found, expected)

    def test_Should_return_the_repo_venv_python_When_a_built_copy_has_a_marker(self):
        # Arrange
        expected = _make_venv_python(self.repo)
        self._write_marker(f"{self.repo}\n")

        # Act
        found = bootstrap._discover_external_python(self.copy_here)

        # Assert
        self.assertEqual(found, expected)

    def test_Should_return_none_When_the_marker_points_to_a_dir_without_a_venv(self):
        # Arrange
        self.repo.mkdir()
        self._write_marker(str(self.repo))

        # Act
        found = bootstrap._discover_external_python(self.copy_here)

        # Assert
        self.assertIsNone(found)

    def test_Should_return_none_When_a_built_copy_has_no_marker(self):
        # Arrange
        _make_venv_python(self.repo)
        self.addon_root.mkdir(parents=True)

        # Act
        found = bootstrap._discover_external_python(self.copy_here)

        # Assert
        self.assertIsNone(found)

    def test_Should_return_none_When_the_marker_is_empty(self):
        # Arrange
        _make_venv_python(self.repo)
        self._write_marker("")

        # Act
        found = bootstrap._discover_external_python(self.copy_here)

        # Assert
        self.assertIsNone(found)

    def test_Should_return_none_When_the_marker_holds_non_utf8_bytes(self):
        # Arrange
        _make_venv_python(self.repo)
        self.addon_root.mkdir(parents=True)
        (self.addon_root / "repo-root.txt").write_bytes(b"\xff\xfe\xfa")

        # Act
        found = bootstrap._discover_external_python(self.copy_here)

        # Assert
        self.assertIsNone(found)

    def test_Should_return_the_env_repo_venv_python_When_the_marker_is_stale(self):
        # Arrange
        self.repo.mkdir()
        self._write_marker(str(self.repo))
        env_repo = self.base / "env-repo"
        expected = _make_venv_python(env_repo)
        os.environ["FREECAD_BUDDY_REPO"] = str(env_repo)

        # Act
        found = bootstrap._discover_external_python(self.copy_here)

        # Assert
        self.assertEqual(found, expected)

    def test_Should_return_none_When_reading_the_marker_raises_an_os_error(self):
        # Arrange
        _make_venv_python(self.repo)
        (self.addon_root / "repo-root.txt").mkdir(parents=True)

        # Act
        found = bootstrap._discover_external_python(self.copy_here)

        # Assert
        self.assertIsNone(found)


if __name__ == "__main__":
    unittest.main()
