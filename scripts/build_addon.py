"""Assemble the installable FreeCAD addon under ``dist/addon/``.

Copies the ``freecad_buddy`` package, drops in ``addon/package.xml``, and writes a top-level
``InitGui.py`` shim that puts the package on ``sys.path`` and imports the real addon entry. With
``FREECAD_BUDDY_SRC`` set, the shim points at the dev source tree instead of the bundled copy so
edits are picked up without a rebuild.

``--release`` bundles the package wheel instead of the repo marker and writes
``dist/FreeCADBuddy-<version>.zip``, the addon users extract into FreeCAD's ``Mod`` folder.

This is external tooling (not shipped inside FreeCAD), so ``print`` is fine here.
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import tomllib
import zipfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SRC_PKG = REPO_ROOT / "src" / "freecad_buddy"
PACKAGE_XML = REPO_ROOT / "addon" / "package.xml"
# Read by hosts/gui_addon/bootstrap.py: a copied addon has no path relation to the repo, so this
# marker is its only route back to the project .venv that runs the MCP proxy.
REPO_ROOT_MARKER = "repo-root.txt"

_INITGUI_SHIM = '''\
"""Generated addon shim: put freecad_buddy on sys.path and run the real InitGui."""

import os
import sys
from pathlib import Path

# FreeCAD exec()s this file without a module __file__, so resolve the addon dir defensively:
# an explicit dev-source override, else this file's dir when __file__ exists, else FreeCAD's
# user Mod/<addon> path. FreeCAD already adds the addon dir to sys.path before running InitGui,
# so the import resolves even if none of these yield a path.
_src = os.environ.get("FREECAD_BUDDY_SRC")
if _src:
    _pkg_parent = Path(_src)
elif "__file__" in globals():
    _pkg_parent = Path(__file__).resolve().parent
else:
    try:
        import FreeCAD

        _pkg_parent = Path(FreeCAD.getUserAppDataDir()) / "Mod" / "FreeCADBuddy"
    except Exception:  # noqa: BLE001 - fall back to FreeCAD's own sys.path entry
        _pkg_parent = None

if _pkg_parent is not None and str(_pkg_parent) not in sys.path:
    sys.path.insert(0, str(_pkg_parent))

import freecad_buddy.hosts.gui_addon.InitGui  # noqa: E402,F401
'''


def build(dist_dir: Path | None = None, release: bool = False, wheel: Path | None = None) -> Path:
    """Assemble the addon tree and return its path.

    A release tree carries ``wheel`` in ``wheels/``, from which the addon provisions the MCP proxy
    venv on first start, and no repo marker: an installed release has no repo to point at.
    """
    dist_dir = dist_dir or (REPO_ROOT / "dist" / "addon")
    if dist_dir.exists():
        shutil.rmtree(dist_dir)
    dist_dir.mkdir(parents=True)

    shutil.copytree(
        SRC_PKG,
        dist_dir / "freecad_buddy",
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
    )
    shutil.copy2(PACKAGE_XML, dist_dir / "package.xml")
    (dist_dir / "InitGui.py").write_text(_INITGUI_SHIM, encoding="utf-8")
    if release:
        (dist_dir / "wheels").mkdir()
        shutil.copy2(wheel, dist_dir / "wheels" / wheel.name)
    else:
        (dist_dir / REPO_ROOT_MARKER).write_text(str(REPO_ROOT), encoding="utf-8")
    return dist_dir


def package_zip(tree: Path, version: str) -> Path:
    """Zip ``tree`` as ``FreeCADBuddy-<version>.zip`` beside it, under a ``FreeCADBuddy/`` folder.

    The top folder is the name FreeCAD loads the addon by, so extracting the zip into ``Mod``
    gives ``Mod/FreeCADBuddy``.
    """
    archive = tree.parent / f"FreeCADBuddy-{version}.zip"
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as bundle:
        for path in sorted(tree.rglob("*")):
            if path.is_file():
                bundle.write(path, Path("FreeCADBuddy") / path.relative_to(tree))
    return archive


def project_version() -> str:
    with open(REPO_ROOT / "pyproject.toml", "rb") as handle:
        return tomllib.load(handle)["project"]["version"]


def _build_wheel(version: str) -> Path:
    out_dir = REPO_ROOT / "dist"
    subprocess.run(["uv", "build", "--wheel", "--out-dir", str(out_dir)], cwd=REPO_ROOT, check=True)
    return out_dir / f"freecad_buddy-{version}-py3-none-any.whl"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("dist_dir", nargs="?", type=Path, help="addon tree output directory")
    parser.add_argument(
        "--release", action="store_true", help="bundle the wheel and write the addon zip"
    )
    parser.add_argument("--wheel", type=Path, help="wheel to bundle; default: build one with uv")
    args = parser.parse_args(sys.argv[1:] if argv is None else argv)

    if not args.release:
        out = build(args.dist_dir)
        print(f"addon assembled at {out}")
        return 0
    version = project_version()
    wheel = args.wheel or _build_wheel(version)
    out = build(args.dist_dir, release=True, wheel=wheel)
    print(f"addon zip written to {package_zip(out, version)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
