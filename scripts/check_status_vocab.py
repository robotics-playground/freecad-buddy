"""Status-vocabulary enforcer. No `Literal` status/verdict/state member
set outside `contracts/status.py`.

AST-scan ``src/freecad_buddy/**/*.py``. Any ``Literal[...]`` whose string members
intersect the terminal-status/job-state/verdict set — when written outside the sole
owner ``contracts/status.py`` (matched by package-RELATIVE path, not basename) — is a
violation.

The status set is derived at runtime from ``contracts.status`` (never hand-copied), so
the enforcer cannot drift from the single source. ``JobState`` is a Union
(``Literal["QUEUED","RUNNING"] | TerminalStatus``); the derivation flattens nested
Literals so all 9 members (7 terminal + QUEUED + RUNNING) are in scope.

``Literal`` is resolved by BOTH its ``from typing import Literal [as L]`` bound local
name(s) AND its attribute form (``import typing; typing.Literal[...]``) so aliased or
attribute-qualified redefinitions are still detected. Non-``Literal`` duplications (str
Enum, tuple, frozenset) are out of the Literal-only scope — not flagged here.

On violation: print ``relpath:line -- rule`` and exit 1; clean = exit 0.
"""

from __future__ import annotations

import ast
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, get_args, get_origin

OWNER_RELPATH = "contracts/status.py"


def _flatten_literal_members(members: tuple, out: set[str]) -> None:
    for m in members:
        nested = get_args(m)
        if nested and get_origin(m) is Literal:
            _flatten_literal_members(nested, out)
        elif isinstance(m, str):
            out.add(m)


def _status_members() -> frozenset[str]:
    """Derive the closed status/job-state member set from ``contracts.status``.

    Flattens the ``JobState`` union so the nested ``Literal["QUEUED","RUNNING"]`` object
    contributes its string members alongside the terminal strings — all 9 members.
    """
    from freecad_buddy.contracts import status as status_mod

    members: set[str] = set()
    for name in ("TerminalStatus", "JobState"):
        tp = getattr(status_mod, name)
        _flatten_literal_members(get_args(tp), members)
    return frozenset(members)


@dataclass(frozen=True)
class Violation:
    relpath: str
    line: int
    rule: str

    def __str__(self) -> str:
        return f"{self.relpath}:{self.line} -- {self.rule}"


def _literal_local_names(tree: ast.AST) -> set[str]:
    """Local names bound to ``typing.Literal`` / ``typing_extensions.Literal`` in a file.

    Covers ``from typing import Literal`` (name ``Literal``), ``... import Literal as L``
    (name ``L``). The attribute form ``typing.Literal[...]`` is matched separately in the
    subscript walk, keyed off the module alias tracked here.
    """
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module in (
            "typing",
            "typing_extensions",
        ):
            for alias in node.names:
                if alias.name == "Literal":
                    names.add(alias.asname or alias.name)
    return names


def _typing_module_aliases(tree: ast.AST) -> set[str]:
    """Local names bound to the ``typing``/``typing_extensions`` module itself."""
    aliases: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name in ("typing", "typing_extensions"):
                    aliases.add(alias.asname or alias.name)
    return aliases


def _is_literal_subscript(
    node: ast.Subscript, literal_names: set[str], module_aliases: set[str]
) -> bool:
    value = node.value
    if isinstance(value, ast.Name) and value.id in literal_names:
        return True
    if (
        isinstance(value, ast.Attribute)
        and value.attr == "Literal"
        and isinstance(value.value, ast.Name)
        and value.value.id in module_aliases
    ):
        return True
    return False


def _literal_string_members(node: ast.Subscript) -> set[str]:
    """String constants inside a ``Literal[...]`` subscript."""
    members: set[str] = set()
    slice_node = node.slice
    elts = slice_node.elts if isinstance(slice_node, ast.Tuple) else [slice_node]
    for elt in elts:
        if isinstance(elt, ast.Constant) and isinstance(elt.value, str):
            members.add(elt.value)
    return members


def _check_file(path: Path, relpath: str, vocab: frozenset[str]) -> list[Violation]:
    if relpath == OWNER_RELPATH:
        return []
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except (SyntaxError, UnicodeDecodeError) as exc:
        return [Violation(relpath, getattr(exc, "lineno", 0) or 0, f"unparseable file: {exc}")]

    literal_names = _literal_local_names(tree)
    module_aliases = _typing_module_aliases(tree)
    violations: list[Violation] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Subscript):
            continue
        if not _is_literal_subscript(node, literal_names, module_aliases):
            continue
        members = _literal_string_members(node)
        if members & vocab:
            violations.append(
                Violation(
                    relpath,
                    node.lineno,
                    "Literal status/verdict/state member set defined outside "
                    "contracts/status.py",
                )
            )
    return violations


def check_tree(root: Path) -> list[Violation]:
    vocab = _status_members()
    violations: list[Violation] = []
    for path in sorted(root.rglob("*.py")):
        relpath = path.relative_to(root).as_posix()
        violations.extend(_check_file(path, relpath, vocab))
    return violations


def _default_root() -> Path:
    return Path(__file__).resolve().parent.parent / "src" / "freecad_buddy"


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    root = Path(argv[0]) if argv else _default_root()

    if not root.exists():
        print(f"check_status_vocab: root not found: {root}")
        return 1

    violations = check_tree(root)
    if violations:
        for v in violations:
            print(str(v))
        return 1

    print("check_status_vocab OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
