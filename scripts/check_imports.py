"""Architecture-ring + Qt-whitelist import enforcer.

Static AST analysis over ``src/freecad_buddy/**/*.py``. Runs with NO FreeCAD installed.

Rules enforced (dependencies point inward only):
  contracts/ ..... stdlib-only (+ firstparty freecad_buddy inward). No third-party, no FreeCAD.
  usecases/ ...... stdlib + FreeCAD-App whitelist {FreeCAD, Part, Sketcher, PartDesign,
                   Mesh, MeshPart} + firstparty inward (contracts). No third-party, no Qt.
  adapters/ ...... may import contracts/usecases + third-party; NOT hosts.
  hosts/ ......... top ring; may import anything inward.
  Qt / FreeCADGui / PySide* allowed ONLY in hosts/**, adapters/marshal.py, adapters/render_probe.py.
  ActiveDocument . no ``FreeCAD.ActiveDocument`` / ``App.ActiveDocument`` /
                   ``setActiveDocument`` anywhere: every tool operates on an explicit doc handle,
                   never the process-global active document (a screenshot/query keying on it
                   would silently target the wrong document).

On any violation: print ``relpath:line -- <rule>`` to stdout and exit 1.
Clean tree: exit 0 (prints "check_imports OK").

Importable: call ``check_tree(root)`` for a list[Violation] (unit-testable, no subprocess).
Runnable: ``python scripts/check_imports.py``.
"""

from __future__ import annotations

import ast
import sys
from dataclasses import dataclass
from pathlib import Path

FIRSTPARTY = "freecad_buddy"

FREECAD_APP_WHITELIST = frozenset(
    {"FreeCAD", "Part", "Sketcher", "PartDesign", "Mesh", "MeshPart"}
)

# Module names FreeCAD is bound to; ``<name>.ActiveDocument`` on any of these is the banned form.
FREECAD_MODULE_ALIASES = frozenset({"FreeCAD", "App"})
ACTIVE_DOCUMENT_ATTRS = frozenset({"ActiveDocument", "setActiveDocument"})

QT_MODULES = frozenset(
    {"FreeCADGui", "PySide", "PySide2", "PySide6", "PyQt5", "PyQt6", "shiboken2", "shiboken6"}
)

# Rings ordered inner -> outer; index gives ring rank for inward-only checks.
RING_ORDER = ["contracts", "usecases", "adapters", "hosts"]


@dataclass(frozen=True)
class Violation:
    relpath: str
    line: int
    rule: str

    def __str__(self) -> str:
        return f"{self.relpath}:{self.line} -- {self.rule}"


def _stdlib_names() -> frozenset[str]:
    # sys.stdlib_module_names available on 3.11+ (requires-python floor).
    return frozenset(sys.stdlib_module_names)


def _ring_of(relparts: tuple[str, ...]) -> str | None:
    """Map path parts (relative to src/freecad_buddy) to a ring name, or None."""
    if not relparts:
        return None
    head = relparts[0]
    return head if head in RING_ORDER else None


QT_EXEMPT_ADAPTERS = frozenset({"adapters/marshal.py", "adapters/render_probe.py"})


def _qt_allowed(ring: str | None, relpath: str) -> bool:
    if ring == "hosts":
        return True
    # Match the full package-relative path, not just the basename, so a nested
    # adapters/sub/marshal.py cannot inherit the exemption.
    if ring == "adapters" and relpath in QT_EXEMPT_ADAPTERS:
        return True
    return False


def _top_module(node: ast.Import | ast.ImportFrom) -> list[tuple[str, int]]:
    """Return (top-level-module-name, lineno) for each imported module in a node.

    Relative imports (``from . import x`` / ``from ..ring import x``) are handled
    separately in ``_check_file`` (they can still point outward across rings), so
    they are intentionally not surfaced here.
    """
    out: list[tuple[str, int]] = []
    if isinstance(node, ast.Import):
        for alias in node.names:
            out.append((alias.name.split(".")[0], node.lineno))
    else:  # ImportFrom
        if node.level and node.level > 0:
            return out
        if node.module:
            out.append((node.module.split(".")[0], node.lineno))
    return out


def _relative_base(relparts: tuple[str, ...], node: ast.ImportFrom) -> list[str] | None:
    """Return the package parts a relative import resolves against, or None if it climbs out.

    ``relparts`` are the current file's path parts under the package root (e.g.
    ``('usecases', 'foo.py')``). A ``level`` of 1 is the file's own package; each extra
    level climbs one directory. Returning None means the import escapes the package root.
    """
    pkg_parts = list(relparts[:-1])
    climb = node.level - 1  # level 1 = current package; level N climbs N-1 dirs above it.
    if climb > len(pkg_parts):
        return None  # climbs above the package root
    return pkg_parts[: len(pkg_parts) - climb]


def _resolve_relative_rings(relparts: tuple[str, ...], node: ast.ImportFrom) -> list[str]:
    """Every ring a relative ImportFrom targets, via both ``node.module`` and ``node.names``.

    ``from ..hosts import x`` targets via the module head; ``from .. import hosts`` targets
    via the imported name. Both forms must be direction-checked or the ring gate leaks.
    """
    base = _relative_base(relparts, node)
    if base is None:
        return []
    rings: list[str] = []
    if node.module:
        head = node.module.split(".")[0]
        resolved = base + [head]
        if resolved[0] in RING_ORDER:
            rings.append(resolved[0])
    else:
        # ``from . / .. import <name>`` — each name resolves as a sibling of ``base``.
        for alias in node.names:
            resolved = base + [alias.name]
            if resolved[0] in RING_ORDER:
                rings.append(resolved[0])
    return rings


def _check_active_document(tree: ast.Module, relpath: str) -> list[Violation]:
    """Flag every ``FreeCAD.ActiveDocument`` / ``App.setActiveDocument`` access in ``tree``.

    Matches ``<alias>.<attr>`` where ``<alias>`` is a FreeCAD module binding and ``<attr>`` is
    ``ActiveDocument`` or ``setActiveDocument``. Tools must key on the explicit doc handle passed
    to them, never the process-global active document.
    """
    violations: list[Violation] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Attribute) or node.attr not in ACTIVE_DOCUMENT_ATTRS:
            continue
        base = node.value
        if isinstance(base, ast.Name) and base.id in FREECAD_MODULE_ALIASES:
            violations.append(
                Violation(
                    relpath, node.lineno,
                    f"'{base.id}.{node.attr}' is banned; operate on the explicit doc handle, "
                    f"never the process-global active document",
                )
            )
    return violations


def _check_file(path: Path, relpath: str, stdlib: frozenset[str]) -> list[Violation]:
    relparts = tuple(Path(relpath).parts)
    ring = _ring_of(relparts)
    if ring is None:
        # Non-ring files (package-root e.g. freecad_buddy/util.py, or a non-ring subpackage
        # e.g. freecad_buddy/util/helper.py) are not in a ring but still run inside FreeCAD:
        # enforce the Qt-ban + stdlib/FreeCAD-App floor so a stray third-party or Qt import
        # anywhere outside a ring cannot slip the gate.
        return _check_root_file(path, relpath, stdlib)

    ring_rank = RING_ORDER.index(ring)
    violations: list[Violation] = []
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except (SyntaxError, UnicodeDecodeError) as exc:
        return [Violation(relpath, getattr(exc, "lineno", 0) or 0, f"unparseable file: {exc}")]

    violations.extend(_check_active_document(tree, relpath))

    for node in ast.walk(tree):
        if not isinstance(node, (ast.Import, ast.ImportFrom)):
            continue

        # Relative firstparty imports can still point outward across rings.
        if isinstance(node, ast.ImportFrom) and node.level and node.level > 0:
            if _relative_base(relparts, node) is None:
                violations.append(
                    Violation(
                        relpath, node.lineno,
                        f"relative import climbs above the package root "
                        f"(level {node.level})",
                    )
                )
                continue
            for target_ring in _resolve_relative_rings(relparts, node):
                _flag_outward(target_ring, ring_rank, relpath, node.lineno, violations)
            continue

        for mod, line in _top_module(node):
            # Firstparty inward imports: verify direction, then allow.
            if mod == FIRSTPARTY:
                _check_firstparty_direction(node, ring_rank, relpath, line, violations)
                continue

            # Qt / GUI whitelist (checked before stdlib since these are third-party anyway).
            if mod in QT_MODULES:
                if not _qt_allowed(ring, relpath):
                    violations.append(
                        Violation(
                            relpath, line,
                            f"Qt/FreeCADGui/PySide import '{mod}' allowed only in "
                            f"hosts/**, adapters/marshal.py, adapters/render_probe.py",
                        )
                    )
                continue

            is_stdlib = mod in stdlib

            if ring == "contracts":
                if not is_stdlib:
                    violations.append(
                        Violation(
                            relpath, line,
                            f"contracts/ is stdlib-only; '{mod}' is not stdlib",
                        )
                    )
            elif ring == "usecases":
                if not is_stdlib and mod not in FREECAD_APP_WHITELIST:
                    violations.append(
                        Violation(
                            relpath, line,
                            f"usecases/ allows stdlib + FreeCAD-App whitelist only; "
                            f"'{mod}' is neither",
                        )
                    )
            # adapters/ and hosts/ may import third-party freely (subject to Qt + inward rules).

    return violations


def _check_root_file(path: Path, relpath: str, stdlib: frozenset[str]) -> list[Violation]:
    """Enforce Qt-ban + stdlib/FreeCAD-App floor on a non-ring file.

    Covers both a package-root file (depth 1, e.g. freecad_buddy/util.py) and a non-ring
    subpackage file (depth >= 2 whose first path segment is not a ring, e.g.
    freecad_buddy/util/helper.py) — neither is in a ring but both still run inside FreeCAD,
    so a stray third-party or Qt import there must be flagged, not skipped. Firstparty
    imports are allowed — a non-ring layer is outermost, so any ring is inward of it.
    """
    violations: list[Violation] = []
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except (SyntaxError, UnicodeDecodeError) as exc:
        return [Violation(relpath, getattr(exc, "lineno", 0) or 0, f"unparseable file: {exc}")]

    violations.extend(_check_active_document(tree, relpath))

    relparts = tuple(Path(relpath).parts)
    for node in ast.walk(tree):
        if not isinstance(node, (ast.Import, ast.ImportFrom)):
            continue
        if isinstance(node, ast.ImportFrom) and node.level and node.level > 0:
            # A relative import can only target inward rings (allowed) UNLESS it climbs above
            # the package root — possible for a depth >= 2 non-ring subpackage file. Flag the
            # over-climb, mirroring _check_file, instead of silently allowing the escape.
            if _relative_base(relparts, node) is None:
                violations.append(
                    Violation(
                        relpath, node.lineno,
                        f"relative import climbs above the package root "
                        f"(level {node.level})",
                    )
                )
            continue
        for mod, line in _top_module(node):
            if mod == FIRSTPARTY:
                continue
            if mod in QT_MODULES:
                violations.append(
                    Violation(
                        relpath, line,
                        f"Qt/FreeCADGui/PySide import '{mod}' allowed only in "
                        f"hosts/**, adapters/marshal.py, adapters/render_probe.py",
                    )
                )
                continue
            if mod not in stdlib and mod not in FREECAD_APP_WHITELIST:
                violations.append(
                    Violation(
                        relpath, line,
                        f"non-ring files allow stdlib + FreeCAD-App whitelist only; "
                        f"'{mod}' is neither",
                    )
                )
    return violations


def _flag_outward(
    target_ring: str | None,
    ring_rank: int,
    relpath: str,
    line: int,
    violations: list[Violation],
) -> None:
    """Append a violation if ``target_ring`` is outward of the current ring."""
    if target_ring is None:
        return
    if RING_ORDER.index(target_ring) > ring_rank:
        violations.append(
            Violation(
                relpath, line,
                f"outward import: {RING_ORDER[ring_rank]}/ must not import "
                f"'{target_ring}/' (dependencies point inward only)",
            )
        )


def _firstparty_target_rings(node: ast.Import | ast.ImportFrom) -> list[str]:
    """Every ring named by an absolute freecad_buddy.<ring>... import in this node.

    Covers three forms: ``import freecad_buddy.<ring>...`` (ring in the dotted path),
    ``from freecad_buddy.<ring> import x`` (ring in the module), and
    ``from freecad_buddy import <ring>`` (ring in the imported names).
    """
    rings: list[str] = []
    if isinstance(node, ast.ImportFrom) and node.module:
        parts = node.module.split(".")
        if len(parts) >= 2 and parts[1] in RING_ORDER:
            rings.append(parts[1])
        elif node.module == FIRSTPARTY:
            # from freecad_buddy import <ring>[, <ring2>]
            rings.extend(a.name for a in node.names if a.name in RING_ORDER)
    elif isinstance(node, ast.Import):
        for alias in node.names:
            parts = alias.name.split(".")
            if len(parts) >= 2 and parts[1] in RING_ORDER:
                rings.append(parts[1])
    return rings


def _check_firstparty_direction(
    node: ast.Import | ast.ImportFrom,
    ring_rank: int,
    relpath: str,
    line: int,
    violations: list[Violation],
) -> None:
    """A freecad_buddy.<ring>... import must target a ring at or inward of the current ring."""
    for target_ring in _firstparty_target_rings(node):
        _flag_outward(target_ring, ring_rank, relpath, line, violations)


def check_tree(root: Path) -> list[Violation]:
    """Scan every .py under ``root`` (a freecad_buddy package dir) and return violations."""
    stdlib = _stdlib_names()
    violations: list[Violation] = []
    for path in sorted(root.rglob("*.py")):
        relpath = path.relative_to(root).as_posix()
        violations.extend(_check_file(path, relpath, stdlib))
    return violations


def _default_root() -> Path:
    return Path(__file__).resolve().parent.parent / "src" / "freecad_buddy"


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    root = Path(argv[0]) if argv else _default_root()

    if not root.exists():
        print(f"check_imports: root not found: {root}")
        return 1

    violations = check_tree(root)
    if violations:
        for v in violations:
            print(str(v))
        return 1

    print("check_imports OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
