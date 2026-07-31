"""Deterministic FreeCADCmd generator for the G2 coincidental-hash fixtures.

Run under FreeCADCmd (``FreeCADCmd build_coincidental_fixtures.py``).

This suite's trap defeats Layer 1: a reference is re-pointed to a *different* element whose
witness coincides with the original, so a mapped-name/witness comparison sees no change and only
``getElementHistory`` divergence detects it. The fixture is therefore a document holding two
geometrically indistinguishable candidate elements; the re-point is planted by the op named in
each ``case.yaml``'s ``planted_op`` running through ``run_mutation``.

Fixtures are written next to their ``case.yaml`` as ``<case-id>/fixture.FCStd``.
"""

from __future__ import annotations

from pathlib import Path

import FreeCAD as App
import Part

HERE = Path(__file__).resolve().parent

BOX_SIDE = 10.0
GAP = 20.0


def _twin_boxes_document(name: str):
    """Two identical boxes separated along X, fused, with a fillet on one twin's edge.

    The twins are congruent, so an element on one has the same witness as its counterpart on the
    other: re-pointing the reference from one twin to the other changes which element is
    referenced without changing any witness Layer 1 compares. Only ancestry divergence separates
    them.
    """
    document = App.newDocument(name)
    first = document.addObject("Part::Feature", "TwinA")
    first.Shape = Part.makeBox(BOX_SIDE, BOX_SIDE, BOX_SIDE)
    second = document.addObject("Part::Feature", "TwinB")
    second.Shape = Part.makeBox(BOX_SIDE, BOX_SIDE, BOX_SIDE, App.Vector(GAP, 0, 0))
    document.recompute()
    fusion = document.addObject("Part::MultiFuse", "Fusion")
    fusion.Shapes = [first, second]
    first.Visibility = False
    second.Visibility = False
    document.recompute()
    fillet = document.addObject("Part::Fillet", "Fillet")
    fillet.Base = fusion
    fillet.Edges = [(1, 1.0, 1.0)]
    fusion.Visibility = False
    document.recompute()
    return document


FIXTURES = {
    "g2-fault-coincidental-witness-match": _twin_boxes_document,
    "g2-fault-coincidental-genuine-match": _twin_boxes_document,
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
