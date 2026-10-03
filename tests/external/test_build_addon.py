"""``build_addon.build`` output: the copied package plus the repo-root marker a copy needs."""

import sys
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
