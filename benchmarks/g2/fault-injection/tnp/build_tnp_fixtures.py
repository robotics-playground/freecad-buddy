"""Deterministic FreeCADCmd generator for the G2 TNP fault fixtures.

Run under FreeCADCmd (``FreeCADCmd build_tnp_fixtures.py``).

A TNP fault is a *runtime path*, not defective geometry: the fixture is the pre-mutation input
document holding the references the guard snapshots, and the fault is planted by the op named in
each ``case.yaml``'s ``planted_op`` when it runs through ``run_mutation``. A fixture hand-built to
already look broken would validate nothing — the guard must catch a break the production mutation
path produced.

Fixtures are written next to their ``case.yaml`` as ``<case-id>/fixture.FCStd``.
"""

from __future__ import annotations

import sys
from pathlib import Path

import FreeCAD as App
import Part

HERE = Path(__file__).resolve().parent

# Unlike its sibling generators this one reads a shim accessor, so `src/` must be importable.
# FreeCADCmd puts only this script's directory on sys.path, and the package is not installed into
# FreeCAD's Mod/ on a clean checkout.
_SRC = HERE.parents[3] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from freecad_buddy.usecases import shim  # noqa: E402

BOX_L = 10.0
BOX_W = 20.0
BOX_H = 30.0
SQUARE = 8.0


def _filleted_box_document(name: str):
    """A box carrying a fillet whose ``Base`` LinkSubList names four vertical edges.

    Scenario (a) renumbers those edges from upstream; the dress-up keeps recomputing cleanly while
    its LinkSubList quietly loses an entry, so the fixture must carry a multi-entry reference for
    the entry-count comparison to have something to compare.
    """
    document = App.newDocument(name)
    base = document.addObject("Part::Feature", "Base")
    base.Shape = Part.makeBox(BOX_L, BOX_W, BOX_H)
    document.recompute()
    fillet = document.addObject("Part::Fillet", "Fillet")
    fillet.Base = base
    vertical = [
        index + 1
        for index, edge in enumerate(base.Shape.Edges)
        if abs(edge.Vertexes[0].Point.z - edge.Vertexes[-1].Point.z) > 1e-7
    ]
    fillet.Edges = [(index, 1.0, 1.0) for index in vertical]
    base.Visibility = False
    document.recompute()
    return document


def _attached_sketch_document(name: str):
    """A sketch attached to a box face — the attachment reference scenario (b) deletes.

    ``AttachmentSupport`` is the 1.0+ spelling of the property that names the supporting face;
    the sketch resolves through it, so deleting the support is what breaks the reference.
    """
    document = App.newDocument(name)
    base = document.addObject("Part::Feature", "Support")
    base.Shape = Part.makeBox(BOX_L, BOX_W, BOX_H)
    document.recompute()
    sketch = document.addObject("Sketcher::SketchObject", "Sketch")
    shim.set_attachment(sketch, [(base, ["Face6"])], "FlatFace")
    sketch.addGeometry(Part.LineSegment(App.Vector(0, 0, 0), App.Vector(SQUARE, 0, 0)), False)
    document.recompute()
    return document


def _external_geometry_document(name: str):
    """A sketch carrying external geometry linked to a separate source solid.

    Scenario (c) changes the source; the external-geometry link is one of the four
    reference-holding subsystems the guard snapshots, and it needs a real linked edge to break.
    """
    document = App.newDocument(name)
    source = document.addObject("Part::Feature", "Source")
    source.Shape = Part.makeBox(BOX_L, BOX_W, BOX_H)
    document.recompute()
    sketch = document.addObject("Sketcher::SketchObject", "Sketch")
    sketch.Placement = App.Placement(App.Vector(0, 0, BOX_H), App.Rotation(App.Vector(0, 0, 1), 0))
    sketch.addExternal(source.Name, "Edge1")
    document.recompute()
    return document


def _expression_document(name: str):
    """A box whose Height is bound by an expression to another object's property.

    Scenario (d) renames the referenced object; the expression engine is the fourth
    reference-holding subsystem, and an expression only breaks if one is actually bound.
    """
    document = App.newDocument(name)
    driver = document.addObject("Part::Box", "Driver")
    driver.Length = BOX_L
    driver.Width = BOX_W
    driver.Height = BOX_H
    driven = document.addObject("Part::Box", "Driven")
    driven.Length = BOX_L
    driven.Width = BOX_W
    driven.setExpression("Height", "Driver.Height")
    document.recompute()
    return document


def _boolean_document(name: str):
    """Two overlapping solids fused into a boolean whose operand order scenario (e) reorders.

    A reorder re-points a reference to a different element whose witness coincides, so Layer 1
    sees nothing and only ``getElementHistory`` divergence detects it.
    """
    document = App.newDocument(name)
    first = document.addObject("Part::Feature", "First")
    first.Shape = Part.makeBox(BOX_L, BOX_W, BOX_H)
    second = document.addObject("Part::Feature", "Second")
    second.Shape = Part.makeBox(BOX_L, BOX_W, BOX_H, App.Vector(BOX_L / 2, 0, 0))
    document.recompute()
    fusion = document.addObject("Part::MultiFuse", "Fusion")
    fusion.Shapes = [first, second]
    first.Visibility = False
    second.Visibility = False
    document.recompute()
    return document


FIXTURES = {
    "g2-fault-tnp-a-fillet-edge-renumber": _filleted_box_document,
    "g2-fault-tnp-b-attachment-support-deleted": _attached_sketch_document,
    "g2-fault-tnp-c-external-geometry-source-changed": _external_geometry_document,
    "g2-fault-tnp-d-expression-rename-break": _expression_document,
    "g2-fault-tnp-e-boolean-reorder-repoint": _boolean_document,
    "g2-fault-tnp-control-unchanged-references": _filleted_box_document,
    "g2-fault-tnp-control-intended-target": _filleted_box_document,
    "g2-fault-tnp-control-elementmap-version-bump": _filleted_box_document,
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
