"""Deterministic FreeCADCmd generator for the G2 dress-up silent-edge-drop fixtures.

Run under FreeCADCmd (``FreeCADCmd build_dressup_fixtures.py``).

The trap this suite exists for is a dress-up whose ``Base`` LinkSubList loses an entry while the
feature keeps recomputing cleanly and reports no status string, so a Layer-0 error sweep sees
nothing and only an entry-count comparison detects it. The fixture is therefore the pre-mutation
document carrying a multi-entry LinkSubList; the drop itself is planted by the op named in each
``case.yaml``'s ``planted_op`` running through ``run_mutation``.

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
FILLET_RADIUS = 1.0


def _filleted_box_document(name: str):
    """A box whose fillet names all four vertical edges in one ``Edges`` LinkSubList.

    Four entries is the smallest count that lets a single silent drop stay invisible to an error
    sweep: the remaining three still recompute into a valid solid, so only comparing the entry
    count against the snapshot reveals the loss.
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
    fillet.Edges = [(index, FILLET_RADIUS, FILLET_RADIUS) for index in vertical]
    base.Visibility = False
    document.recompute()
    return document


FIXTURES = {
    "g2-fault-dressup-silent-edge-drop": _filleted_box_document,
    "g2-fault-dressup-intended-edge-removal": _filleted_box_document,
    "g2-fault-dressup-all-edges-retained": _filleted_box_document,
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
