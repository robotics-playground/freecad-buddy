"""Skill shape check (AD-15): every ``skills/*/SKILL.md`` has the four sections and fits the cap.

Per ``SKILL.md``:

  - the body's H2 headings are exactly ``## Scope``, ``## Decision Rules``,
    ``## Worked Examples``, ``## Anti-Patterns``, in that order, and each has text under it;
  - the body is at most 1,500 words. The body is everything after the front matter's closing
    ``---``; a word is one whitespace-separated token.

On any violation: print ``path -- rule`` and exit 1. Clean tree: exit 0 with no output.

Importable: ``check_tree(skills_dir)`` returns a list[str] of violations (unit-testable).
Runnable: ``python scripts/check_skill_shape.py [skills_dir]``.
"""

from __future__ import annotations

import sys
from pathlib import Path

SECTIONS = ("Scope", "Decision Rules", "Worked Examples", "Anti-Patterns")
MAX_WORDS = 1500


def _body(text: str) -> str:
    lines = text.splitlines()
    if lines and lines[0].strip() == "---":
        for index, line in enumerate(lines[1:], start=1):
            if line.strip() == "---":
                return "\n".join(lines[index + 1 :])
    return text


def _sections(body: str) -> list[tuple[str, str]]:
    """Return ``(heading, text under it)`` for each H2 in ``body``, in order."""
    sections: list[tuple[str, list[str]]] = []
    for line in body.splitlines():
        if line.startswith("## "):
            sections.append((line[3:].strip(), []))
        elif sections:
            sections[-1][1].append(line)
    return [(heading, "\n".join(lines)) for heading, lines in sections]


def check_skill(path: Path, relpath: str) -> list[str]:
    body = _body(path.read_text(encoding="utf-8"))
    violations: list[str] = []
    sections = _sections(body)
    headings = [heading for heading, _ in sections]
    if tuple(headings) != SECTIONS:
        violations.append(
            f"{relpath} -- H2 sections must be {list(SECTIONS)} in order; found {headings}"
        )
    for heading, text in sections:
        if heading in SECTIONS and not text.strip():
            violations.append(f"{relpath} -- section '## {heading}' is empty")
    words = len(body.split())
    if words > MAX_WORDS:
        violations.append(f"{relpath} -- body has {words} words; limit is {MAX_WORDS}")
    return violations


def check_tree(skills_dir: Path) -> list[str]:
    """Check every ``<skill>/SKILL.md`` under ``skills_dir`` and return violations."""
    violations: list[str] = []
    for path in sorted(skills_dir.glob("*/SKILL.md")):
        violations.extend(check_skill(path, path.relative_to(skills_dir).as_posix()))
    return violations


def _default_root() -> Path:
    return Path(__file__).resolve().parent.parent / "skills"


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    root = Path(argv[0]) if argv else _default_root()

    if not root.exists():
        print(f"check_skill_shape: root not found: {root}")
        return 1

    violations = check_tree(root)
    for violation in violations:
        print(violation)
    return 1 if violations else 0


if __name__ == "__main__":
    raise SystemExit(main())
