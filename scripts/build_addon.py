"""Assemble the installable FreeCAD addon under ``dist/addon/``.

Copies the ``freecad_buddy`` package, drops in ``addon/package.xml``, and writes a top-level
``InitGui.py`` shim that puts the package on ``sys.path`` and imports the real addon entry. With
``FREECAD_BUDDY_SRC`` set, the shim points at the dev source tree instead of the bundled copy so
edits are picked up without a rebuild.

This is external tooling (not shipped inside FreeCAD), so ``print`` is fine here.
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SRC_PKG = REPO_ROOT / "src" / "freecad_buddy"
PACKAGE_XML = REPO_ROOT / "addon" / "package.xml"

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


def build(dist_dir: Path | None = None) -> Path:
    """Assemble the addon tree and return its path."""
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
    return dist_dir


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    dist_dir = Path(argv[0]) if argv else None
    out = build(dist_dir)
    print(f"addon assembled at {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
