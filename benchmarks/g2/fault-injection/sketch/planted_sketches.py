"""The ``planted_op`` callables the ``sketch/`` fault cases name, and the seed each one starts from.

Every case in this suite names a ``planted_op``. This module is the single place those names
resolve to a callable. Each op takes the opened ``App.Document`` and returns the names of the
objects it touched, which is the ``op`` contract ``usecases.transaction.run_mutation`` takes — so a
fault is always applied through the production mutation bracket (fingerprint, reference snapshot,
transaction, recompute, ``post_verify``, commit-or-rollback) rather than by hand-editing a saved
document. A sketch carved into a fixture already broken would prove nothing about the validator; a
sketch the production path broke is what the suite exists to grade.

The faults cover the pass/fail policy ``verification-design.md`` §4.2 makes normative for
``verify_sketch``, one family per hard-fail trigger:

* **under-constrained** (``dof > 0``) — an unconstrained line, an unconstrained circle, a removed
  radius dimension. The solver reports the extra freedom and ``FullyConstrained`` goes False.
* **over-constrained / conflicting** (``dof < 0``, non-empty ``ConflictingConstraints``) — a
  contradicting dimension, a second dimension on a dimensioned side, a perpendicular forced onto
  parallel sides, an equality between unequal sides. Measured on FreeCAD 1.1.0, all four leave
  ``FullyConstrained == True`` while ``dof == -1``, so reading the PASS signal alone misses them.
* **bad-index (malformed)** — a constraint whose ``First`` / ``Second`` / ``Third`` slot names an
  index no geometry carries. ``addConstraint`` rejects these, so they are planted by assigning the
  ``Constraints`` property, which is the reachable route on this build.
* **degenerate geometry** (``degenerate_geometry_count > 0``) — a zero-length segment, a
  zero-radius circle, a segment collapsed by driving its own datum to 0 mm. All three leave
  ``dof == 0`` and ``FullyConstrained == True``, so only the degeneracy check separates them from a
  clean sketch.

The controls are chosen to discriminate rather than to be easy. Four of the seven carry a
``RedundantConstraints`` entry, which §4.2 makes WARN-never-fail: FreeCAD marks such a sketch
``isValid() == False``, so an implementation that took validity as the verdict would flag every one.
"""

from __future__ import annotations

import FreeCAD as App
import Part
import Sketcher

RECT_WIDTH = 20.0
RECT_HEIGHT = 10.0
SKETCH_NAME = "Sketch"

# The index of the rectangle's DistanceX datum in the seed's constraint list, used by the ops that
# drive an existing dimension rather than adding one.
RECT_WIDTH_DATUM = 8

CIRCLE_CENTRE_X = 10.0
CIRCLE_CENTRE_Y = 5.0
CIRCLE_RADIUS = 3.0

# detectDegeneratedGeometries is called at 1e-7 in usecases.verify, so a planted degeneracy must sit
# below that and a near-degenerate control must sit above it.
DEGENERATE_LENGTH = 1e-9
ABOVE_TOLERANCE_LENGTH = 0.001


class OpNotDriveable(RuntimeError):
    """An op whose fault has no reachable trigger on this build; the case is not scorable."""


def _sketch(document: object) -> object:
    """The seeded sketch, or raise naming what the document actually holds."""
    obj = document.getObject(SKETCH_NAME)
    if obj is None:
        held = ", ".join(o.Name for o in document.Objects)
        raise RuntimeError(f"fixture holds no object {SKETCH_NAME!r} (holds: {held})")
    return obj


def _append_constraint(sketch_obj: object, constraint: object) -> list[str]:
    """Append ``constraint`` by assigning the ``Constraints`` property.

    ``addConstraint`` validates indices and raises ``IndexError: Constraint has invalid indexes``,
    so it cannot plant a bad-index fault. Assigning the property bypasses that check — FreeCAD logs
    "Unmanaged change of Constraint Property results in invalid constraint indices" and keeps the
    constraint — which is the only route to the fault on FreeCAD 1.1.0.
    """
    sketch_obj.Constraints = [*list(sketch_obj.Constraints), constraint]
    return [sketch_obj.Name]


# ------------------------------------------------------------------------------------------
# Seeds: the documents the fixtures hold. A seed is always a clean, fully constrained sketch, so
# whatever the graded reading reports afterwards was produced by the op and not inherited.
# ------------------------------------------------------------------------------------------


def seed_rectangle(document: object) -> object:
    """A fully constrained 20x10 mm rectangle anchored on the origin."""
    sketch_obj = document.addObject("Sketcher::SketchObject", SKETCH_NAME)
    corners = [(0, 0), (RECT_WIDTH, 0), (RECT_WIDTH, RECT_HEIGHT), (0, RECT_HEIGHT)]
    for index in range(4):
        start = corners[index]
        end = corners[(index + 1) % 4]
        sketch_obj.addGeometry(Part.LineSegment(App.Vector(*start, 0), App.Vector(*end, 0)), False)
    for index in range(4):
        sketch_obj.addConstraint(Sketcher.Constraint("Coincident", index, 2, (index + 1) % 4, 1))
    sketch_obj.addConstraint(Sketcher.Constraint("Horizontal", 0))
    sketch_obj.addConstraint(Sketcher.Constraint("Horizontal", 2))
    sketch_obj.addConstraint(Sketcher.Constraint("Vertical", 1))
    sketch_obj.addConstraint(Sketcher.Constraint("Vertical", 3))
    sketch_obj.addConstraint(Sketcher.Constraint("DistanceX", 0, 1, 0, 2, RECT_WIDTH))
    sketch_obj.addConstraint(Sketcher.Constraint("DistanceY", 1, 1, 1, 2, RECT_HEIGHT))
    sketch_obj.addConstraint(Sketcher.Constraint("Coincident", 0, 1, -1, 1))
    document.recompute()
    return sketch_obj


def seed_rectangle_with_circle(document: object) -> object:
    """The rectangle plus a fully constrained circle, for the ops that undo a circle dimension."""
    sketch_obj = seed_rectangle(document)
    index = sketch_obj.addGeometry(
        Part.Circle(
            App.Vector(CIRCLE_CENTRE_X, CIRCLE_CENTRE_Y, 0), App.Vector(0, 0, 1), CIRCLE_RADIUS
        ),
        False,
    )
    sketch_obj.addConstraint(Sketcher.Constraint("DistanceX", -1, 1, index, 3, CIRCLE_CENTRE_X))
    sketch_obj.addConstraint(Sketcher.Constraint("DistanceY", -1, 1, index, 3, CIRCLE_CENTRE_Y))
    sketch_obj.addConstraint(Sketcher.Constraint("Radius", index, CIRCLE_RADIUS))
    document.recompute()
    return sketch_obj


# ------------------------------------------------------------------------------------------
# Planted: under-constrained (dof > 0)
# ------------------------------------------------------------------------------------------


def add_unconstrained_line(document: object) -> list[str]:
    """Add a line carrying no constraint: four degrees of freedom the solver cannot remove."""
    sketch_obj = _sketch(document)
    sketch_obj.addGeometry(Part.LineSegment(App.Vector(2, 2, 0), App.Vector(8, 6, 0)), False)
    return [sketch_obj.Name]


def add_unconstrained_circle(document: object) -> list[str]:
    """Add a circle carrying no constraint: centre x, centre y and radius are all free."""
    sketch_obj = _sketch(document)
    sketch_obj.addGeometry(Part.Circle(App.Vector(6, 4, 0), App.Vector(0, 0, 1), 2.0), False)
    return [sketch_obj.Name]


def remove_radius_dimension(document: object) -> list[str]:
    """Delete the circle's radius dimension, leaving exactly one degree of freedom.

    The smallest under-constraint the policy still has to fail: the sketch looks finished, every
    element is placed, and only the radius is free.
    """
    sketch_obj = _sketch(document)
    sketch_obj.delConstraint(sketch_obj.ConstraintCount - 1)
    return [sketch_obj.Name]


# ------------------------------------------------------------------------------------------
# Planted: over-constrained / conflicting (dof < 0, non-empty ConflictingConstraints)
#
# Measured on FreeCAD 1.1.0: every op in this family leaves FullyConstrained == True while dof is
# -1. Reading the PASS signal alone reports these as clean, so they are the family that separates
# the policy §4.2 states from the one-property shortcut.
# ------------------------------------------------------------------------------------------


def add_contradicting_width(document: object) -> list[str]:
    """Dimension the already-20 mm side as 25 mm: two dimensions that cannot both hold."""
    sketch_obj = _sketch(document)
    sketch_obj.addConstraint(Sketcher.Constraint("DistanceX", 0, 1, 0, 2, 25.0))
    return [sketch_obj.Name]


def add_second_height_dimension(document: object) -> list[str]:
    """Dimension the opposite vertical side to a height the first dimension already fixed."""
    sketch_obj = _sketch(document)
    sketch_obj.addConstraint(Sketcher.Constraint("DistanceY", 3, 1, 3, 2, 14.0))
    return [sketch_obj.Name]


def force_perpendicular_on_parallel_sides(document: object) -> list[str]:
    """Declare the two horizontal sides perpendicular: geometrically impossible."""
    sketch_obj = _sketch(document)
    sketch_obj.addConstraint(Sketcher.Constraint("Perpendicular", 0, 2))
    return [sketch_obj.Name]


def equate_unequal_sides(document: object) -> list[str]:
    """Declare the 20 mm and 10 mm sides equal while both dimensions still hold."""
    sketch_obj = _sketch(document)
    sketch_obj.addConstraint(Sketcher.Constraint("Equal", 0, 1))
    return [sketch_obj.Name]


# ------------------------------------------------------------------------------------------
# Planted: bad-index constraints
#
# Measured on FreeCAD 1.1.0: the solver drops the whole constraint set rather than flagging the one
# bad entry, so dof reads 16 (the unconstrained rectangle) and evaluateConstraints() returns False.
# MalformedConstraints stays EMPTY on every route probed — see UNDRIVEABLE below.
# ------------------------------------------------------------------------------------------


def add_constraint_with_bad_first_index(document: object) -> list[str]:
    """Plant a Horizontal constraint whose ``First`` names geometry index 99."""
    constraint = Sketcher.Constraint("Horizontal", 0)
    constraint.First = 99
    return _append_constraint(_sketch(document), constraint)


def add_constraint_with_bad_second_index(document: object) -> list[str]:
    """Plant a Coincident constraint whose ``Second`` names geometry index 500."""
    constraint = Sketcher.Constraint("Coincident", 0, 1, 1, 1)
    constraint.Second = 500
    return _append_constraint(_sketch(document), constraint)


def add_constraint_with_bad_third_index(document: object) -> list[str]:
    """Plant a DistanceX constraint whose ``Third`` slot names index 77 on a two-element type."""
    constraint = Sketcher.Constraint("DistanceX", 0, 1, 0, 2, RECT_WIDTH)
    constraint.Third = 77
    return _append_constraint(_sketch(document), constraint)


# ------------------------------------------------------------------------------------------
# Planted: degenerate geometry
#
# Each leaves dof == 0, FullyConstrained == True, no conflict and no redundancy — every signal a
# clean sketch shows. detectDegeneratedGeometries is the only property that separates them.
# ------------------------------------------------------------------------------------------


def add_zero_length_segment(document: object) -> list[str]:
    """Add a fully dimensioned segment 1 nm long: below the 1e-7 degeneracy tolerance."""
    sketch_obj = _sketch(document)
    index = sketch_obj.addGeometry(
        Part.LineSegment(App.Vector(5, 5, 0), App.Vector(5 + DEGENERATE_LENGTH, 5, 0)), False
    )
    sketch_obj.addConstraint(Sketcher.Constraint("DistanceX", -1, 1, index, 1, 5.0))
    sketch_obj.addConstraint(Sketcher.Constraint("DistanceY", -1, 1, index, 1, 5.0))
    sketch_obj.addConstraint(Sketcher.Constraint("DistanceX", -1, 1, index, 2, 5.0))
    sketch_obj.addConstraint(Sketcher.Constraint("DistanceY", -1, 1, index, 2, 5.0))
    return [sketch_obj.Name]


def add_zero_radius_circle(document: object) -> list[str]:
    """Add a fully dimensioned circle whose radius datum is 1 nm."""
    sketch_obj = _sketch(document)
    index = sketch_obj.addGeometry(
        Part.Circle(App.Vector(15, 8, 0), App.Vector(0, 0, 1), DEGENERATE_LENGTH), False
    )
    sketch_obj.addConstraint(Sketcher.Constraint("DistanceX", -1, 1, index, 3, 15.0))
    sketch_obj.addConstraint(Sketcher.Constraint("DistanceY", -1, 1, index, 3, 8.0))
    sketch_obj.addConstraint(Sketcher.Constraint("Radius", index, DEGENERATE_LENGTH))
    return [sketch_obj.Name]


def collapse_segment_by_datum(document: object) -> list[str]:
    """Collapse a healthy dimensioned segment by driving its own length datum to 0 mm.

    The nearest thing to a real editing mistake in the family: the geometry is added well formed
    and constrained, and the degeneracy is produced afterwards by the solver honouring a datum the
    user set, not by the coordinates the op wrote.
    """
    sketch_obj = _sketch(document)
    index = sketch_obj.addGeometry(
        Part.LineSegment(App.Vector(4, 2, 0), App.Vector(9, 2, 0)), False
    )
    sketch_obj.addConstraint(Sketcher.Constraint("Horizontal", index))
    sketch_obj.addConstraint(Sketcher.Constraint("DistanceX", -1, 1, index, 1, 4.0))
    sketch_obj.addConstraint(Sketcher.Constraint("DistanceY", -1, 1, index, 1, 2.0))
    datum = sketch_obj.addConstraint(Sketcher.Constraint("DistanceX", index, 1, index, 2, 5.0))
    sketch_obj.setDatum(datum, App.Units.Quantity("0.0 mm"))
    return [sketch_obj.Name]


# ------------------------------------------------------------------------------------------
# Controls
#
# Four of the seven carry a RedundantConstraints entry. §4.2 makes redundancy WARN-never-fail, and
# FreeCAD marks such a sketch isValid() == False with status "Sketch with redundant constraints" —
# so an implementation that read validity, or the status string, as the verdict flags all four.
# ------------------------------------------------------------------------------------------


def set_width_datum_unchanged(document: object) -> list[str]:
    """Re-set the width datum to the value it already carries: the neutral clean control."""
    sketch_obj = _sketch(document)
    sketch_obj.setDatum(RECT_WIDTH_DATUM, App.Units.Quantity(f"{RECT_WIDTH} mm"))
    return [sketch_obj.Name]


def resize_width_datum(document: object) -> list[str]:
    """Drive the width to 24 mm: the sketch changes shape and stays fully constrained."""
    sketch_obj = _sketch(document)
    sketch_obj.setDatum(RECT_WIDTH_DATUM, App.Units.Quantity("24.0 mm"))
    return [sketch_obj.Name]


def add_constrained_construction_line(document: object) -> list[str]:
    """Add a construction diagonal pinned to two corners: new geometry, no new freedom."""
    sketch_obj = _sketch(document)
    index = sketch_obj.addGeometry(
        Part.LineSegment(App.Vector(0, 0, 0), App.Vector(RECT_WIDTH, RECT_HEIGHT, 0)), True
    )
    sketch_obj.addConstraint(Sketcher.Constraint("Coincident", index, 1, 0, 1))
    sketch_obj.addConstraint(Sketcher.Constraint("Coincident", index, 2, 2, 1))
    return [sketch_obj.Name]


def add_redundant_duplicate_dimension(document: object) -> list[str]:
    """Re-dimension the top side at the width the bottom side already fixes.

    The duplicate dimension §9 names. It agrees with the dimension already there, so the solver
    reports it redundant rather than conflicting: the sketch stays fully constrained and must PASS.
    """
    sketch_obj = _sketch(document)
    sketch_obj.addConstraint(Sketcher.Constraint("DistanceX", 2, 2, 2, 1, RECT_WIDTH))
    return [sketch_obj.Name]


def add_redundant_equal_horizontals(document: object) -> list[str]:
    """Declare the two horizontal sides equal: already true, so redundant not conflicting."""
    sketch_obj = _sketch(document)
    sketch_obj.addConstraint(Sketcher.Constraint("Equal", 0, 2))
    return [sketch_obj.Name]


def add_redundant_equal_verticals(document: object) -> list[str]:
    """Declare the two vertical sides equal: the same redundancy on the other axis."""
    sketch_obj = _sketch(document)
    sketch_obj.addConstraint(Sketcher.Constraint("Equal", 1, 3))
    return [sketch_obj.Name]


def add_short_segment_above_tolerance(document: object) -> list[str]:
    """Add a fully dimensioned 1 um segment: short, but above the 1e-7 degeneracy tolerance.

    The discriminating pair for ``add_zero_length_segment``: identical in every respect except that
    this one is long enough not to be degenerate. An implementation flagging short geometry rather
    than measuring it against the tolerance fails here and passes there.
    """
    sketch_obj = _sketch(document)
    index = sketch_obj.addGeometry(
        Part.LineSegment(App.Vector(5, 5, 0), App.Vector(5 + ABOVE_TOLERANCE_LENGTH, 5, 0)), False
    )
    sketch_obj.addConstraint(Sketcher.Constraint("Horizontal", index))
    sketch_obj.addConstraint(Sketcher.Constraint("DistanceX", -1, 1, index, 1, 5.0))
    sketch_obj.addConstraint(Sketcher.Constraint("DistanceY", -1, 1, index, 1, 5.0))
    sketch_obj.addConstraint(
        Sketcher.Constraint("DistanceX", index, 1, index, 2, ABOVE_TOLERANCE_LENGTH)
    )
    return [sketch_obj.Name]


# Ops whose fault has no reachable trigger on this build, each with the reason it cannot be driven.
# Scoring these as misses would blame the validator for a trigger the suite cannot pull.
UNDRIVEABLE: dict[str, str] = {
    "populate_malformed_constraints": (
        "MalformedConstraints stays EMPTY for every bad-index route reachable on FreeCAD 1.1.0 "
        "(Libs 1.1.0R20260325). Measured four ways over a fully constrained rectangle: "
        "addConstraint with an out-of-range geometry index raises IndexError('Constraint has "
        "invalid indexes') before anything is stored; assigning the Constraints property with "
        "First=99, with Second=500, or with Third=77 is accepted (FreeCAD logs 'Unmanaged change "
        "of Constraint Property results in invalid constraint indices') and in all three cases the "
        "post-recompute reading is MalformedConstraints=[] with evaluateConstraints()=False and "
        "dof=16 — the solver drops the whole constraint set rather than naming the bad entry; and "
        "setting FirstPos to an out-of-range PosId raises SystemError inside the Constraint "
        "constructor. Because verify.py gates evaluateConstraints() behind bool(malformed) "
        "(deferred-work DW-29, documented inline at usecases/verify.py:421-425), neither the "
        "malformed nor the evaluate_bad hard-fail trigger fires on this build. The three "
        "bad-index cases in this suite are scored on the trigger that DOES fire — dof=16 > 0 with "
        "FullyConstrained=False — so the defect is graded honestly by the signal the validator "
        "actually reads. A case asserting the MalformedConstraints signal itself would be scoring "
        "a property FreeCAD 1.1.0 never populates"
    ),
    "populate_partially_redundant_constraints": (
        "PartiallyRedundantConstraints stays EMPTY on FreeCAD 1.1.0 for every partial-redundancy "
        "pattern probed; the solver classes each as fully redundant instead. Measured over six "
        "constructions: two circles with Equal plus both Radius dimensions -> redundant=[6] "
        "partial=[]; a line-arc tangency chain with an explicit Coincident -> redundant=[1] "
        "partial=[]; Symmetric about the Y axis plus both DistanceX dimensions -> redundant=[1,4] "
        "partial=[]; Distance plus DistanceX on a horizontal line -> redundant=[4] partial=[]; an "
        "extra Horizontal on an already-horizontal line -> redundant=[12] partial=[]; and a "
        "duplicate Coincident -> redundant=[12] partial=[]. The WARN-never-fail half of the policy "
        "is therefore exercised by the four RedundantConstraints controls in this suite, which "
        "cover the same branch of verify.py (usecases/verify.py:451, 'if redundant or "
        "partially_redundant'). A case asserting the partially-redundant signal would be scoring a "
        "property this build never populates"
    ),
}


REGISTRY = {
    "add_constrained_construction_line": add_constrained_construction_line,
    "add_constraint_with_bad_first_index": add_constraint_with_bad_first_index,
    "add_constraint_with_bad_second_index": add_constraint_with_bad_second_index,
    "add_constraint_with_bad_third_index": add_constraint_with_bad_third_index,
    "add_contradicting_width": add_contradicting_width,
    "add_redundant_duplicate_dimension": add_redundant_duplicate_dimension,
    "add_redundant_equal_horizontals": add_redundant_equal_horizontals,
    "add_redundant_equal_verticals": add_redundant_equal_verticals,
    "add_second_height_dimension": add_second_height_dimension,
    "add_short_segment_above_tolerance": add_short_segment_above_tolerance,
    "add_unconstrained_circle": add_unconstrained_circle,
    "add_unconstrained_line": add_unconstrained_line,
    "add_zero_length_segment": add_zero_length_segment,
    "add_zero_radius_circle": add_zero_radius_circle,
    "collapse_segment_by_datum": collapse_segment_by_datum,
    "equate_unequal_sides": equate_unequal_sides,
    "force_perpendicular_on_parallel_sides": force_perpendicular_on_parallel_sides,
    "remove_radius_dimension": remove_radius_dimension,
    "resize_width_datum": resize_width_datum,
    "set_width_datum_unchanged": set_width_datum_unchanged,
}

# The seed each case's fixture holds, keyed by planted_op. Every op but the radius removal starts
# from the plain rectangle; that one needs a circle to take a dimension off.
SEEDS = {
    "remove_radius_dimension": seed_rectangle_with_circle,
}


def seed_for(planted_op: str):
    """The seed factory the case named by ``planted_op`` builds its fixture from."""
    return SEEDS.get(planted_op, seed_rectangle)


def resolve(name: str):
    """The callable ``name`` denotes.

    :raises KeyError: no op carries that name.
    """
    return REGISTRY[name]
