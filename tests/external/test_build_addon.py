"""``build_addon.build`` output: the copied package plus the repo-root marker a copy needs.

A release build bundles the wheel instead of the marker, and ``package_zip`` wraps the tree.
"""

import sys
import zipfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

sys.path.insert(0, str(REPO_ROOT / "scripts"))
import build_addon  # noqa: E402


def test_Should_write_the_repo_root_marker_When_the_addon_is_built(tmp_path):
    # Arrange
    dist_dir = tmp_path / "addon"

    # Act
    out = build_addon.build(dist_dir)

    # Assert
    marker = out / "repo-root.txt"
    assert marker.is_file()
    assert marker.read_text(encoding="utf-8") == str(REPO_ROOT)


def test_Should_copy_the_package_unchanged_When_the_addon_is_built(tmp_path):
    # Arrange
    dist_dir = tmp_path / "addon"
    source = REPO_ROOT / "src" / "freecad_buddy" / "hosts" / "gui_addon" / "bootstrap.py"

    # Act
    out = build_addon.build(dist_dir)

    # Assert
    copied = out / "freecad_buddy" / "hosts" / "gui_addon" / "bootstrap.py"
    assert copied.read_bytes() == source.read_bytes()
    assert not (out / "freecad_buddy" / build_addon.REPO_ROOT_MARKER).exists()


def _fake_wheel(tmp_path):
    wheel = tmp_path / "freecad_buddy-0.0.1-py3-none-any.whl"
    wheel.write_bytes(b"wheel")
    return wheel


def test_Should_bundle_the_wheel_without_a_marker_When_built_for_release(tmp_path):
    # Arrange
    dist_dir = tmp_path / "addon"
    wheel = _fake_wheel(tmp_path)

    # Act
    out = build_addon.build(dist_dir, release=True, wheel=wheel)

    # Assert
    assert (out / "wheels" / wheel.name).read_bytes() == b"wheel"
    assert not (out / build_addon.REPO_ROOT_MARKER).exists()


def test_Should_zip_the_tree_under_a_FreeCADBuddy_folder_When_packaged(tmp_path):
    # Arrange
    out = build_addon.build(tmp_path / "addon", release=True, wheel=_fake_wheel(tmp_path))

    # Act
    archive = build_addon.package_zip(out, "0.0.1")

    # Assert
    assert archive == tmp_path / "FreeCADBuddy-0.0.1.zip"
    with zipfile.ZipFile(archive) as bundle:
        names = bundle.namelist()
    assert all(name.startswith("FreeCADBuddy/") for name in names)
    assert "FreeCADBuddy/InitGui.py" in names
    assert "FreeCADBuddy/package.xml" in names
    assert "FreeCADBuddy/wheels/freecad_buddy-0.0.1-py3-none-any.whl" in names
    assert "FreeCADBuddy/freecad_buddy/hosts/gui_addon/managed_venv.py" in names


def test_Should_write_the_versioned_zip_with_the_wheel_When_main_runs_in_release_mode(tmp_path):
    # Arrange
    wheel = _fake_wheel(tmp_path)
    version = build_addon.project_version()
    argv = ["--release", "--wheel", str(wheel), str(tmp_path / "addon")]

    # Act
    exit_code = build_addon.main(argv)

    # Assert
    assert exit_code == 0
    with zipfile.ZipFile(tmp_path / f"FreeCADBuddy-{version}.zip") as bundle:
        assert f"FreeCADBuddy/wheels/{wheel.name}" in bundle.namelist()
