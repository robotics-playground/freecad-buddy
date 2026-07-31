"""Deterministic FreeCADCmd generator for the G2 rollback-boundary fixtures.

Run under FreeCADCmd (``FreeCADCmd build_rollback_fixtures.py``).

A rollback-boundary fault is a *runtime path*, not defective geometry: the fixture is the
pre-mutation input document, and the fault is planted by the op the scorer wraps in
``run_mutation``. Each ``case.yaml`` names its op in ``planted_op``; this generator writes only
the input document, so the expected rollback path stays derivable from the case rather than baked
into a shape.

Fixtures are written next to their ``case.yaml`` as ``<case-id>/fixture.FCStd``.
"""

from __future__ import annotations

from pathlib import Path

import FreeCAD as App
import Part

HERE = Path(__file__).resolve().parent

BOX_L = 10.0
BOX_W = 20.0
BOX_H = 30.0


def _plain_box_document(name: str):
    """A document holding one 10x20x30 mm box — the neutral pre-mutation state.

    Both #6031 cases and the abort-clean control mutate this same input, so the fixtures differ
    only in the op the case plants, never in the starting geometry.
    """
    document = App.newDocument(name)
    obj = document.addObject("Part::Feature", "Box")
    obj.Shape = Part.makeBox(BOX_L, BOX_W, BOX_H)
    document.recompute()
    return document


def _body_document(name: str):
    """A document holding an empty PartDesign Body and its Origin datum planes.

    The sketch-on-plane #6031 pattern needs a Body whose datum planes a sketch can attach to.
    """
    document = App.newDocument(name)
    document.addObject("PartDesign::Body", "Body")
    document.recompute()
    return document


FIXTURES = {
    "g2-fault-rollback-6031-sketch-on-plane": _body_document,
    "g2-fault-rollback-6031-nested-transaction": _plain_box_document,
    "g2-fault-rollback-failing-op-abort-clean": _plain_box_document,
    "g2-fault-rollback-successful-op-no-rollback": _plain_box_document,
}


def build() -> list[Path]:
    """Write every fixture beside its ``case.yaml``; return the paths written."""
    written = []
    for case_id, factory in sorted(FIXTURES.items()):
        target = HERE / case_id / "fixture.FCStd"
        document = factory(case_id.replace("-", "_"))
        try:
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
    import sys

    if __name__ == "__main__":
        return True
    if len(sys.argv) > 1:
        return Path(sys.argv[1]).resolve() == Path(__file__).resolve()
    return False


if _is_top_level_script():
    import sys

    for path in build():
        sys.stderr.write(f"wrote {path}\n")
