"""Deterministic FreeCADCmd generator for the G2 sketch fault fixtures.

Run under FreeCADCmd (``FreeCADCmd build_sketch_fixtures.py``).

Every fixture is a CLEAN, fully constrained sketch — the pre-mutation input. The fault is applied
by the op each ``case.yaml`` names in ``planted_op``, driven through ``run_mutation``, so the
defective sketch is produced by the production mutation path and never carved into a saved
document. Which seed a case starts from is decided by ``planted_sketches.seed_for``, so the fixture
and the op can never disagree about what the op expects to find.

Fixtures are written next to their ``case.yaml`` as ``<case-id>/fixture.FCStd``.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import FreeCAD as App

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import planted_sketches  # noqa: E402


def _planted_op(case_yaml: Path) -> str:
    """The ``planted_op`` the case names.

    :raises RuntimeError: the case declares no op, so no seed can be chosen for it.
    """
    match = re.search(
        r"^planted_op:\s*(.+?)\s*$", case_yaml.read_text(encoding="utf-8"), re.MULTILINE
    )
    if match is None:
        raise RuntimeError(f"{case_yaml}: no 'planted_op'")
    return match.group(1).strip().strip("'\"")


def build() -> list[Path]:
    """Write every fixture beside its ``case.yaml``; return the paths written."""
    written = []
    for case_yaml in sorted(HERE.rglob("case.yaml"), key=lambda p: p.as_posix()):
        if case_yaml.name != "case.yaml":
            continue
        case_dir = case_yaml.parent
        seed = planted_sketches.seed_for(_planted_op(case_yaml))
        document = App.newDocument(case_dir.name.replace("-", "_"))
        try:
            seed(document)
            document.recompute()
            target = case_dir / "fixture.FCStd"
            document.saveAs(str(target))
            written.append(target)
        finally:
            App.closeDocument(document.Name)
    return written


def _is_top_level_script() -> bool:
    """Whether this file is the script the interpreter was launched with.

    FreeCADCmd sets ``__name__`` to the file stem rather than ``"__main__"`` on some platforms, so
    the standard guard alone would silently skip the build; this also matches ``__file__`` against
    the launched ``sys.argv[1]``.
    """
    if __name__ == "__main__":
        return True
    if len(sys.argv) > 1:
        return Path(sys.argv[1]).resolve() == Path(__file__).resolve()
    return False


if _is_top_level_script():
    for path in build():
        sys.stderr.write(f"wrote {path}\n")
