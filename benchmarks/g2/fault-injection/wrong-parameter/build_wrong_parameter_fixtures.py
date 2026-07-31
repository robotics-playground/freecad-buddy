"""Deterministic FreeCADCmd generator for the G2 wrong-parameter fixtures.

Run under FreeCADCmd (``FreeCADCmd build_wrong_parameter_fixtures.py``).

These cases grade the deterministic assertion grader rather than a reference guard: each plants a
mutation run with a parameter that differs from the commanded one, and the suite measures whether
``assertions.evaluate`` rejects the result. The fixture is the pre-mutation input document; the
wrong parameter is applied by the op named in each ``case.yaml``'s ``planted_op``, so the defect
is produced by the production mutation path and not hand-carved into a shape.

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
PLATE_L = 60.0
PLATE_W = 40.0
PLATE_H = 5.0
CYL_RADIUS = 6.0
CYL_HEIGHT = 20.0


def _box_document(name: str):
    """A plain 10x20x30 mm box — the neutral input for the linear-dimension parameter faults."""
    document = App.newDocument(name)
    obj = document.addObject("Part::Feature", "Box")
    obj.Shape = Part.makeBox(BOX_L, BOX_W, BOX_H)
    document.recompute()
    return document


def _plate_document(name: str):
    """A wide flat plate — the input for the pattern and mirror parameter faults.

    A pattern of copies needs room to lay them out; the 10 mm-wide box would push copies off the
    solid and turn a wrong spacing into a recompute error rather than the silent wrong-geometry
    result these cases measure.
    """
    document = App.newDocument(name)
    obj = document.addObject("Part::Feature", "Plate")
    obj.Shape = Part.makeBox(PLATE_L, PLATE_W, PLATE_H)
    document.recompute()
    return document


def _cylinder_document(name: str):
    """A cylinder — the input for the revolve-angle fault, whose result is a solid of revolution."""
    document = App.newDocument(name)
    obj = document.addObject("Part::Feature", "Cylinder")
    obj.Shape = Part.makeCylinder(CYL_RADIUS, CYL_HEIGHT)
    document.recompute()
    return document


FIXTURES = {
    "g2-fault-wrong-param-pad-direction": _box_document,
    "g2-fault-wrong-param-pocket-depth": _box_document,
    "g2-fault-wrong-param-hole-diameter": _box_document,
    "g2-fault-wrong-param-fillet-radius": _box_document,
    "g2-fault-wrong-param-revolve-angle": _cylinder_document,
    "g2-fault-wrong-param-pattern-count": _plate_document,
    "g2-fault-wrong-param-pattern-spacing": _plate_document,
    "g2-fault-wrong-param-mirror-plane": _plate_document,
    "g2-fault-wrong-param-within-tolerance": _box_document,
    "g2-fault-wrong-param-correct-pocket": _box_document,
    "g2-fault-wrong-param-correct-pattern": _plate_document,
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
