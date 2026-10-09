"""The five version strings release-please bumps together stay equal."""

import json
import re
import tomllib
import xml.etree.ElementTree as ElementTree
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def _versions() -> dict[str, str]:
    pyproject = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    init = (REPO_ROOT / "src" / "freecad_buddy" / "__init__.py").read_text(encoding="utf-8")
    package = ElementTree.parse(REPO_ROOT / "addon" / "package.xml").getroot()
    namespace = {"package": "https://wiki.freecad.org/Package_Metadata"}
    marketplace = json.loads(
        (REPO_ROOT / ".claude-plugin" / "marketplace.json").read_text(encoding="utf-8")
    )
    lock = tomllib.loads((REPO_ROOT / "uv.lock").read_text(encoding="utf-8"))
    (locked,) = [package for package in lock["package"] if package["name"] == "freecad-buddy"]
    return {
        "pyproject.toml": pyproject["project"]["version"],
        "__init__.py": re.search(r'__version__ = "([^"]+)"', init).group(1),
        "package.xml": package.find("package:version", namespace).text,
        "marketplace.json": marketplace["plugins"][0]["version"],
        "uv.lock": locked["version"],
    }


def test_Should_match_every_version_When_the_release_files_are_read():
    # Arrange
    expected = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))[
        "project"
    ]["version"]

    # Act
    versions = _versions()

    # Assert
    assert versions == dict.fromkeys(versions, expected)
