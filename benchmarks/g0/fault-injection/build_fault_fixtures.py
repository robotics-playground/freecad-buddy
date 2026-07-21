"""Deterministic FreeCADCmd generator for the G0 planted-fault + clean-control fixtures.

Run under FreeCADCmd (``FreeCADCmd build_fault_fixtures.py``). Each fixture carries a REAL
geometric defect (open shell, planar lamina, invalid self-intersecting solid, overlapping
compound, degenerate face, wrong measurements). The paired ``case.yaml`` asserts the value a
CORRECT reference shape yields for the targeted property, so a Story-1.6 validator detects
the defect by the fixture DEVIATING from that reference — the assertion is never hand-set to
the defective value.

Fixtures are written next to their ``case.yaml`` as ``<case-id>/fixture.FCStd``.
"""

from __future__ import annotations

from pathlib import Path

import FreeCAD as App
import Part

HERE = Path(__file__).resolve().parent


def _wrong_volume():
    # 12*20*30 = 7200; correct reference box-10-20-30 is 6000.
    return Part.makeBox(12, 20, 30)


def _wrong_bbox():
    # Z stretched to 60; correct reference bbox is [10,20,30].
    return Part.makeBox(10, 20, 60)


def _non_watertight_open_shell():
    # Single face -> open (non-watertight) shell, 0 solids; a correct solid IS watertight.
    face = Part.makeBox(10, 10, 1).Faces[0]
    return Part.Shell([face])


def _degenerate_face():
    # Collinear polygon -> zero-area face, isValid() == False; a correct shape is valid.
    wire = Part.makePolygon(
        [App.Vector(0, 0, 0), App.Vector(5, 0, 0), App.Vector(10, 0, 0), App.Vector(0, 0, 0)]
    )
    return Part.Face(wire)


def _zero_volume_lamina():
    # Planar 10x10 face, volume 0; a solid of that footprint (10x10x1) would be 100.
    return Part.makePlane(10, 10)


def _dropped_solid():
    # One box where the two-box reference compound has 2 solids.
    return Part.makeBox(10, 10, 10)


def _wrong_solid_count():
    # Three disjoint boxes where the reference compound has 2 solids.
    return Part.makeCompound(
        [
            Part.makeBox(5, 5, 5),
            Part.makeBox(5, 5, 5, App.Vector(10, 0, 0)),
            Part.makeBox(5, 5, 5, App.Vector(20, 0, 0)),
        ]
    )


def _unit_lie():
    # 1/10-scale box (1x2x3, vol 6) mislabelled as the mm reference (10x20x30, vol 6000).
    return Part.makeBox(1, 2, 3)


def _invalid_self_intersecting_solid():
    # Bowtie (figure-8) profile extruded -> a single solid that OCCT flags isValid()==False.
    # Robust validity defect (replaces the version-fragile signed-volume case).
    wire = Part.makePolygon(
        [
            App.Vector(0, 0, 0),
            App.Vector(10, 10, 0),
            App.Vector(10, 0, 0),
            App.Vector(0, 10, 0),
            App.Vector(0, 0, 0),
        ]
    )
    return Part.Face(wire).extrude(App.Vector(0, 0, 5))


def _self_intersecting_compound():
    # Two overlapping boxes left as a 2-solid compound; a correct boolean union is 1 solid.
    return Part.makeCompound(
        [Part.makeBox(10, 10, 10), Part.makeBox(10, 10, 10, App.Vector(5, 0, 0))]
    )


def _non_manifold_shell():
    # Three faces sharing one vertical edge (edge adjacency 3 > 2) -> non-manifold, open shell.
    base = App.Vector(0, 0, 0)
    top = App.Vector(0, 0, 10)

    def face(direction: App.Vector) -> Part.Face:
        far_base = base + direction
        far_top = top + direction
        wire = Part.makePolygon([base, top, far_top, far_base, base])
        return Part.Face(wire)

    return Part.Shell(
        [
            face(App.Vector(10, 0, 0)),
            face(App.Vector(0, 10, 0)),
            face(App.Vector(-7, -7, 0)),
        ]
    )


def _clean_control():
    # Exact box-10-20-30 rebuild; passes every reference assertion (PASS_CLEAN).
    return Part.makeBox(10, 20, 30)


# case-id -> (object Name, shape builder). Order fixed for determinism.
FIXTURES: dict[str, tuple[str, callable]] = {
    "wrong-volume": ("WrongVolume", _wrong_volume),
    "wrong-bbox": ("WrongBBox", _wrong_bbox),
    "non-watertight-open-shell": ("OpenShell", _non_watertight_open_shell),
    "degenerate-face": ("DegenerateFace", _degenerate_face),
    "zero-volume-lamina": ("Lamina", _zero_volume_lamina),
    "dropped-solid": ("DroppedSolid", _dropped_solid),
    "wrong-solid-count": ("WrongSolidCount", _wrong_solid_count),
    "unit-lie": ("UnitLie", _unit_lie),
    "invalid-self-intersecting-solid": ("InvalidSolid", _invalid_self_intersecting_solid),
    "self-intersecting-compound": ("SelfIntersecting", _self_intersecting_compound),
    "non-manifold": ("NonManifold", _non_manifold_shell),
    "clean-control": ("CleanControl", _clean_control),
}


def build_fixture(case_id: str) -> Part.Shape:
    """Return the fixture shape for ``case_id`` (no document involved)."""
    _, builder = FIXTURES[case_id]
    return builder()


def _save(case_id: str, base_dir: Path) -> Path:
    obj_name, _ = FIXTURES[case_id]
    shape = build_fixture(case_id)
    doc = App.newDocument(case_id)
    feature = doc.addObject("Part::Feature", obj_name)
    feature.Shape = shape
    doc.recompute()
    case_dir = base_dir / case_id
    case_dir.mkdir(parents=True, exist_ok=True)
    target = case_dir / "fixture.FCStd"
    doc.saveAs(str(target))
    App.closeDocument(doc.Name)
    return target


def build_all(base_dir: Path | None = None) -> list[Path]:
    base_dir = base_dir or HERE
    return [_save(case_id, base_dir) for case_id in FIXTURES]


if __name__ == "__main__":
    for path in build_all():
        print(f"wrote {path}")
