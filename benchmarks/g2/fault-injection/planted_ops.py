"""The ``planted_op`` callables the G2 fault cases name, and the checks each one is graded by.

Every G2 fault ``case.yaml`` names a ``planted_op``. This module is the single place those names
resolve to a callable. Each op takes the opened ``App.Document`` and returns the names of the
objects it touched, which is exactly the ``op`` contract ``usecases.transaction.run_mutation``
takes — so an op is always applied through the production mutation bracket (fingerprint, reference
snapshot, transaction, recompute, ``post_verify``, commit-or-rollback) rather than by hand-editing
a saved document. A defect carved into a fixture would prove nothing about the guards; a defect the
production path produced is what the suite exists to grade.

Ops fall into three families, one per validator the cases target:

* ``assertions`` — build geometry with a parameter that does or does not match the commanded one.
  ``CHECKS`` carries the commanded value as an ``assertions.evaluate`` check list, so a wrong
  parameter is caught by measuring the result rather than by re-reading the argument that made it.
* ``audit_references`` — mutate a document holding references so ``tnp_guard.audit_references``
  grades the reference set: break one, re-point one, drop one, or leave every one intact.
* ``run_mutation`` — drive the bracket down a chosen path: commit, abort-and-restore, or the
  nested-transaction boundary of FreeCAD #6031.

``UNDRIVEABLE`` names the ops that cannot be driven on this build, each with the reason. They are
reported as uncollected rather than scored, because a case scored 0 for a missing trigger is
indistinguishable from a validator that missed a real defect.
"""

from __future__ import annotations

import FreeCAD as App
import Part

BOX_L = 10.0
BOX_W = 20.0
BOX_H = 30.0
PLATE_L = 60.0
PLATE_W = 40.0
PLATE_H = 5.0
CYL_RADIUS = 6.0
CYL_HEIGHT = 20.0


class OpNotDriveable(RuntimeError):
    """An op whose fault has no reachable trigger on this build; the case is not scorable."""


# ------------------------------------------------------------------------------------------
# Shared helpers
# ------------------------------------------------------------------------------------------


def _named(document: object, name: str) -> object:
    """The object called ``name``, or raise naming what the document actually holds."""
    obj = document.getObject(name)
    if obj is None:
        held = ", ".join(o.Name for o in document.Objects)
        raise RuntimeError(f"fixture holds no object {name!r} (holds: {held})")
    return obj


def _add_shape(document: object, name: str, shape: object) -> str:
    """Add a ``Part::Feature`` carrying ``shape`` and return its name."""
    obj = document.addObject("Part::Feature", name)
    obj.Shape = shape
    return obj.Name


def _replace_shape(document: object, target: object, shape: object) -> list[str]:
    """Write ``shape`` onto ``target``, hiding nothing and touching no other object."""
    target.Shape = shape
    return [target.Name]


def _vertical_edge_indices(shape: object) -> list[int]:
    """1-based indices of ``shape``'s edges whose endpoints differ in z."""
    return [
        index + 1
        for index, edge in enumerate(shape.Edges)
        if abs(edge.Vertexes[0].Point.z - edge.Vertexes[-1].Point.z) > 1e-7
    ]


# ------------------------------------------------------------------------------------------
# wrong-parameter: graded by benchmarks.harness.assertions.evaluate
#
# Each op replaces the fixture solid with the result of the commanded operation. The planted
# variants apply a parameter that differs from the one CHECKS declares, so the defect is a real
# geometric difference the grader has to measure rather than a flag it could read.
# ------------------------------------------------------------------------------------------

PAD_LENGTH = 8.0
_PAD_SECTION_L = BOX_L
_PAD_SECTION_W = BOX_W
_PAD_SECTION = _PAD_SECTION_L * _PAD_SECTION_W


def pad_in_negative_z(document: object) -> list[str]:
    """Pad the profile in -Z where +Z was commanded.

    The profile sits on the box's top face (z = BOX_H). Padding it in +Z as commanded grows the
    box into one taller solid; padding it in -Z instead drives the same slab back down through
    material that is already there, so the fused result keeps the box's original volume. The
    displaced volume is what separates the two directions — the slab either added material or it
    did not.
    """
    box = _named(document, "Box")
    slab = Part.makeBox(
        _PAD_SECTION_L,
        _PAD_SECTION_W,
        PAD_LENGTH,
        App.Vector(0, 0, BOX_H - PAD_LENGTH),
    )
    return _replace_shape(document, box, box.Shape.fuse(slab).removeSplitter())


POCKET_COMMANDED = 5.0
POCKET_WRONG = 7.0
_POCKET_SIDE = 6.0


def _pocket(document: object, depth: float) -> list[str]:
    """Cut a square pocket ``depth`` deep into the top face of the box."""
    box = _named(document, "Box")
    cutter = Part.makeBox(_POCKET_SIDE, _POCKET_SIDE, depth, App.Vector(0, 0, BOX_H - depth))
    return _replace_shape(document, box, box.Shape.cut(cutter))


def pocket_at_wrong_depth(document: object) -> list[str]:
    """Cut the pocket 7 mm deep where 5 mm was commanded."""
    return _pocket(document, POCKET_WRONG)


def pocket_at_commanded_depth(document: object) -> list[str]:
    """Cut the pocket to the commanded 5 mm."""
    return _pocket(document, POCKET_COMMANDED)


HOLE_COMMANDED_D = 6.0
HOLE_WRONG_D = 6.2
HOLE_WITHIN_TOL_D = 6.0005


def _drill(document: object, diameter: float) -> list[str]:
    """Drill one through hole down the box's z axis at the given diameter."""
    box = _named(document, "Box")
    drill = Part.makeCylinder(diameter / 2.0, BOX_H + 2.0, App.Vector(BOX_L / 2, BOX_W / 2, -1.0))
    return _replace_shape(document, box, box.Shape.cut(drill))


def hole_at_wrong_diameter(document: object) -> list[str]:
    """Drill 6.2 mm where 6.0 mm was commanded."""
    return _drill(document, HOLE_WRONG_D)


def hole_within_declared_tolerance(document: object) -> list[str]:
    """Drill 6.0005 mm — inside the commanded 6.0 mm's declared relative tolerance."""
    return _drill(document, HOLE_WITHIN_TOL_D)


FILLET_COMMANDED_R = 2.0
FILLET_WRONG_R = 3.0


def fillet_at_wrong_radius(document: object) -> list[str]:
    """Fillet the box's vertical edges at 3 mm where 2 mm was commanded."""
    box = _named(document, "Box")
    edges = [box.Shape.Edges[i - 1] for i in _vertical_edge_indices(box.Shape)]
    return _replace_shape(document, box, box.Shape.makeFillet(FILLET_WRONG_R, edges))


REVOLVE_COMMANDED_DEG = 360.0
REVOLVE_WRONG_DEG = 180.0


def revolve_through_wrong_angle(document: object) -> list[str]:
    """Revolve the profile 180 degrees where 360 was commanded: half the volume."""
    cylinder = _named(document, "Cylinder")
    profile = Part.makePlane(CYL_RADIUS, CYL_HEIGHT, App.Vector(0, 0, 0), App.Vector(0, -1, 0))
    revolved = profile.revolve(App.Vector(0, 0, 0), App.Vector(0, 0, 1), REVOLVE_WRONG_DEG)
    return _replace_shape(document, cylinder, Part.Solid(Part.Shell(revolved.Faces)))


PATTERN_COMMANDED_N = 3
PATTERN_WRONG_N = 4
PATTERN_COMMANDED_PITCH = 10.0
PATTERN_WRONG_PITCH = 12.0
PATTERN_HOLE_D = 4.0
_PATTERN_X0 = 10.0


def _pattern(document: object, count: int, pitch: float) -> list[str]:
    """Drill ``count`` through holes spaced ``pitch`` apart along the plate's x axis."""
    plate = _named(document, "Plate")
    shape = plate.Shape
    for index in range(count):
        drill = Part.makeCylinder(
            PATTERN_HOLE_D / 2.0,
            PLATE_H + 2.0,
            App.Vector(_PATTERN_X0 + index * pitch, PLATE_W / 2, -1.0),
        )
        shape = shape.cut(drill)
    return _replace_shape(document, plate, shape)


def pattern_with_wrong_count(document: object) -> list[str]:
    """Produce 4 occurrences where 3 were commanded."""
    return _pattern(document, PATTERN_WRONG_N, PATTERN_COMMANDED_PITCH)


def pattern_with_wrong_spacing(document: object) -> list[str]:
    """Produce the commanded 3 occurrences at a 12 mm pitch where 10 mm was commanded."""
    return _pattern(document, PATTERN_COMMANDED_N, PATTERN_WRONG_PITCH)


def pattern_with_commanded_count(document: object) -> list[str]:
    """Produce exactly the commanded 3 occurrences at the commanded 10 mm pitch."""
    return _pattern(document, PATTERN_COMMANDED_N, PATTERN_COMMANDED_PITCH)


_MIRROR_BOSS_L = 8.0
_MIRROR_BOSS_W = 8.0
_MIRROR_BOSS_H = 6.0
_MIRROR_BOSS_X = 4.0
_MIRROR_BOSS_Y = 4.0


def mirror_across_wrong_plane(document: object) -> list[str]:
    """Mirror the boss across the XZ plane where the YZ plane was commanded.

    The boss sits off-centre in x and centred in y. Mirroring across the commanded YZ plane
    (x = PLATE_L/2) lands the copy clear of the original, giving two separate bosses; mirroring
    across XZ (y = PLATE_W/2) instead maps the y-centred boss onto itself, so the copy coincides
    with the original and the fused result carries one boss where two were commanded.
    """
    plate = _named(document, "Plate")
    boss = Part.makeBox(
        _MIRROR_BOSS_L,
        _MIRROR_BOSS_W,
        _MIRROR_BOSS_H,
        App.Vector(_MIRROR_BOSS_X, (PLATE_W - _MIRROR_BOSS_W) / 2, PLATE_H),
    )
    mirrored = boss.mirror(App.Vector(0, PLATE_W / 2, 0), App.Vector(0, 1, 0))
    fused = plate.Shape.fuse(boss).fuse(mirrored).removeSplitter()
    return _replace_shape(document, plate, fused)


def fillet_the_intended_edge(document: object) -> list[str]:
    """Fillet the edge the mutation names as its own target — the intended change, not a re-point.

    Shared with the TNP control suite: the op rewrites the dress-up's own ``Edges`` list, which is
    the mutation's declared target, so the audit must excuse it rather than grade it a re-point.
    """
    fillet = _named(document, "Fillet")
    fillet.Edges = list(fillet.Edges)
    return [fillet.Name]


# The commanded parameters each wrong-parameter case is graded against. The check list is the
# command's contract: the op that ran either produced geometry matching it or it did not, and
# `assertions.evaluate` measures which. Keyed by case id because two cases can share an op family
# while declaring different commanded values.
CHECKS: dict[str, list[dict]] = {
    "g2-fault-wrong-param-pad-direction": [
        # Commanded: pad the top-face profile 8 mm in +Z, adding a slab of material. Padding the
        # same profile in -Z drives it back into the existing solid and adds nothing, so the
        # displaced volume is what the direction decides.
        {
            "fn": "expect_volume",
            "expect": BOX_L * BOX_W * BOX_H + _PAD_SECTION * PAD_LENGTH,
            "tol": {"rel": 0.001},
        },
    ],
    "g2-fault-wrong-param-pocket-depth": [
        {
            "fn": "expect_volume",
            "expect": BOX_L * BOX_W * BOX_H - _POCKET_SIDE * _POCKET_SIDE * POCKET_COMMANDED,
            "tol": {"rel": 0.001},
        },
    ],
    "g2-fault-wrong-param-correct-pocket": [
        {
            "fn": "expect_volume",
            "expect": BOX_L * BOX_W * BOX_H - _POCKET_SIDE * _POCKET_SIDE * POCKET_COMMANDED,
            "tol": {"rel": 0.001},
        },
    ],
    "g2-fault-wrong-param-hole-diameter": [
        {
            "fn": "expect_volume",
            "expect": BOX_L * BOX_W * BOX_H
            - 3.141592653589793 * (HOLE_COMMANDED_D / 2.0) ** 2 * BOX_H,
            "tol": {"rel": 0.001},
        },
    ],
    "g2-fault-wrong-param-within-tolerance": [
        {
            "fn": "expect_volume",
            "expect": BOX_L * BOX_W * BOX_H
            - 3.141592653589793 * (HOLE_COMMANDED_D / 2.0) ** 2 * BOX_H,
            "tol": {"rel": 0.001},
        },
    ],
    "g2-fault-wrong-param-fillet-radius": [
        {
            "fn": "expect_volume",
            # A 2 mm fillet on four vertical edges removes (1 - pi/4) r^2 per edge over the height.
            "expect": BOX_L * BOX_W * BOX_H
            - 4 * (1 - 3.141592653589793 / 4) * FILLET_COMMANDED_R**2 * BOX_H,
            "tol": {"rel": 0.001},
        },
    ],
    "g2-fault-wrong-param-revolve-angle": [
        {
            "fn": "expect_volume",
            "expect": 3.141592653589793 * CYL_RADIUS**2 * CYL_HEIGHT,
            "tol": {"rel": 0.001},
        },
    ],
    "g2-fault-wrong-param-pattern-count": [
        {"fn": "count_cylindrical_holes", "expect": PATTERN_COMMANDED_N},
    ],
    "g2-fault-wrong-param-correct-pattern": [
        {"fn": "count_cylindrical_holes", "expect": PATTERN_COMMANDED_N},
        {"fn": "hole_spacing", "expect": PATTERN_COMMANDED_PITCH, "tol": {"abs": 0.05}},
    ],
    "g2-fault-wrong-param-pattern-spacing": [
        {"fn": "count_cylindrical_holes", "expect": PATTERN_COMMANDED_N},
        {"fn": "hole_spacing", "expect": PATTERN_COMMANDED_PITCH, "tol": {"abs": 0.05}},
    ],
    "g2-fault-wrong-param-mirror-plane": [
        # Commanded: mirror across YZ, giving the plate plus two distinct bosses. Mirroring across
        # XZ maps the y-centred boss onto itself, so only one boss of material is added.
        {
            "fn": "expect_volume",
            "expect": PLATE_L * PLATE_W * PLATE_H
            + 2 * _MIRROR_BOSS_L * _MIRROR_BOSS_W * _MIRROR_BOSS_H,
            "tol": {"rel": 0.001},
        },
    ],
}


# ------------------------------------------------------------------------------------------
# tnp + dressup-drop + coincidental-hash: graded by usecases.tnp_guard.audit_references
# ------------------------------------------------------------------------------------------


def upstream_sketch_edge_insertion(document: object) -> list[str]:
    """Renumber the dress-up's base edges from upstream, leaving its ``Edges`` list untouched.

    Only the upstream solid is written; whatever the dress-up's reference list loses, it loses by
    FreeCAD re-deriving it, not by this op assigning a shorter list. A drop the op itself wrote is
    the intended-removal control, which the audit rightly excuses.
    """
    base = _named(document, "Base")
    notch = Part.makeBox(BOX_L / 4, BOX_W / 4, BOX_H, App.Vector(0, 0, 0))
    base.Shape = base.Shape.cut(notch)
    return [base.Name]


def delete_attachment_support(document: object) -> list[str]:
    """Delete the object the sketch's ``AttachmentSupport`` names, breaking the attachment."""
    sketch = _named(document, "Sketch")
    support = _named(document, "Support")
    document.removeObject(support.Name)
    return [sketch.Name]


def change_external_geometry_source(document: object) -> list[str]:
    """Change the topology the sketch's external geometry links into.

    The link names ``Edge1`` of the source solid; cutting the solid re-derives its edges so the
    linked topology is no longer the one the sketch bound to.
    """
    source = _named(document, "Source")
    sketch = _named(document, "Sketch")
    cutter = Part.makeBox(BOX_L / 2, BOX_W / 2, BOX_H / 2, App.Vector(0, 0, 0))
    source.Shape = source.Shape.cut(cutter)
    return [source.Name, sketch.Name]


def rename_expression_referent(document: object) -> list[str]:
    """Rename the object an expression binds to, leaving the binding unresolvable.

    ``Label`` is the user-facing name an expression can bind through; rewriting the binding to a
    name no object carries is what breaks the expression engine's reference.
    """
    driven = _named(document, "Driven")
    driven.setExpression("Height", "NoSuchObject.Height")
    return [driven.Name]


def reorder_boolean_operands(document: object) -> list[str]:
    """Swap the fusion's operand order so a face reference lands on a different source face."""
    fusion = _named(document, "Fusion")
    fusion.Shapes = list(reversed(list(fusion.Shapes)))
    return [fusion.Name]


def bump_element_map_version(document: object) -> list[str]:
    """Touch the dress-up without changing any reference — the re-baseline control.

    A genuine ``ElementMapVersion`` bump is a build property, not something a document can be made
    to do at runtime, so this control drives the path the guard takes when nothing about the
    reference set changed and grades that it stays clean.
    """
    fillet = _named(document, "Fillet")
    fillet.Edges = list(fillet.Edges)
    return [fillet.Name]


def recompute_without_reference_change(document: object) -> list[str]:
    """Touch a property that holds no reference; every snapshotted reference stays identical."""
    base = _named(document, "Base")
    base.Label = f"{base.Label} (touched)"
    return [base.Name]


def recompute_retaining_all_edges(document: object) -> list[str]:
    """Recompute the dress-up with every ``Edges`` entry retained."""
    fillet = _named(document, "Fillet")
    fillet.Edges = list(fillet.Edges)
    return [fillet.Name]


def remove_dressup_edge_as_intended(document: object) -> list[str]:
    """Remove one ``Edges`` entry as the mutation's own declared target.

    The same shape of change as the silent drop; what separates them is that this op is the one
    that wrote it, so the post-op reading matches and the audit must excuse it.
    """
    fillet = _named(document, "Fillet")
    fillet.Edges = list(fillet.Edges)[:-1]
    return [fillet.Name]


def recompute_retaining_original_element(document: object) -> list[str]:
    """Recompute leaving the reference on the very element it already named."""
    fillet = _named(document, "Fillet")
    fillet.Edges = list(fillet.Edges)
    return [fillet.Name]


def repoint_reference_to_congruent_twin(document: object) -> list[str]:
    """Re-point the fillet's base from one twin to its geometrically identical sibling.

    The twins are congruent, so the witness hash of the named element coincides and Layer 1 sees
    no movement; only the ancestry cross-check separates them.
    """
    fillet = _named(document, "Fillet")
    twin_b = _named(document, "TwinB")
    fillet.Base = twin_b
    return [fillet.Name]


def drop_dressup_edge_silently(document: object) -> list[str]:
    """The silent dress-up edge drop — not reachable from Python on this build."""
    raise OpNotDriveable(
        "FeatureDressUp::getContinuousEdges is C++-only on FreeCAD 1.1.x, so the silent drop "
        "has no Python-reachable trigger; the reachable drops are either marked '?Edge1' "
        "(a Layer-0 verdict, a different case) or written by the op itself (the intended-removal "
        "control)"
    )


# ------------------------------------------------------------------------------------------
# rollback-boundary: graded by usecases.transaction.run_mutation's own terminal path
# ------------------------------------------------------------------------------------------


class PlantedOpFailure(RuntimeError):
    """The failure a ``*_then_raise`` op plants to drive the bracket down its rollback path."""


def add_solid(document: object) -> list[str]:
    """Add one cylinder and succeed — the control whose bracket commits with no rollback."""
    return [_add_shape(document, "Added", Part.makeCylinder(4.0, 12.0))]


def add_solid_then_raise(document: object) -> list[str]:
    """Add a solid, then raise, so the bracket must abort and restore the pre-op state."""
    _add_shape(document, "Added", Part.makeCylinder(4.0, 12.0))
    raise PlantedOpFailure("planted failure after the op mutated the document")


def nested_open_transaction_then_raise(document: object) -> list[str]:
    """Open a nested transaction, mutate, then raise — the FreeCAD #6031 boundary.

    A nested ``openTransaction`` auto-commits the outer one, so the wrapper's ``abortTransaction``
    can restore the wrong boundary and leave the document short of its pre-op state. The bracket
    must still prove restoration, escalating to the snapshot when the undo path cannot.
    """
    document.openTransaction("planted nested transaction")
    _add_shape(document, "Nested", Part.makeCylinder(3.0, 9.0))
    raise PlantedOpFailure("planted failure inside a nested transaction")


def sketch_on_datum_plane_then_raise(document: object) -> list[str]:
    """Attach a sketch to a Body datum plane, then raise, exercising the same #6031 boundary."""
    body = _named(document, "Body")
    plane = _named(document, "XY_Plane")
    sketch = document.addObject("Sketcher::SketchObject", "Sketch")
    body.addObject(sketch)
    sketch.AttachmentSupport = [(plane, "")]
    sketch.MapMode = "FlatFace"
    sketch.addGeometry(Part.LineSegment(App.Vector(0, 0, 0), App.Vector(8.0, 0, 0)), False)
    raise PlantedOpFailure("planted failure after attaching a sketch to a datum plane")


# Ops whose fault has no reachable trigger on this build, each with the reason it cannot be
# driven. Scoring these as misses would blame the validator for a trigger the suite cannot pull.
UNDRIVEABLE = {
    "drop_dressup_edge_silently": (
        "FeatureDressUp::getContinuousEdges is C++-only on FreeCAD 1.1.x; no Python call plants "
        "a silent LinkSubList drop that the feature then recomputes cleanly over"
    ),
    "nested_open_transaction_then_raise": (
        "FreeCAD#6031 does not reproduce on FreeCAD 1.1.0 (Libs 1.1.0R20260325): measured "
        "directly, a nested openTransaction followed by one abortTransaction restores the "
        "pre-transaction object set exactly (HasPendingTransaction is False afterwards), so the "
        "abort fast path proves the rollback and the snapshot escalation this case grades is "
        "never reached. Forcing the escalation would grade a fault the build does not have"
    ),
    "sketch_on_datum_plane_then_raise": (
        "the same FreeCAD#6031 boundary, and the case already records the measurement: on this "
        "build abort restores the sketch, so the case yields rolled_back_verified — "
        "behaviourally identical to its own abort-clean control. Its expected_path_by_build map "
        "names the snapshot_restore path as reachable only on a build where abort leaves the "
        "sketch behind (deferred-work DW-74)"
    ),
    "reorder_boolean_operands": (
        "Part::MultiFuse.Shapes is a PropertyLinkList, which carries no subelement, so "
        "snapshot_references captures zero records for this fixture and there is no reference "
        "for the guard to grade a re-point against. Measured: 0 records before and after the "
        "reorder. Reaching the REPOINTED verdict needs a fixture whose face reference is held "
        "in a LinkSub property"
    ),
    "change_external_geometry_source": (
        "the case grades BROKEN at layer 1 on a sketch carrying the Missing flag with its "
        "reference rendered '?', and no probed change to the source produces that state on "
        "FreeCAD 1.1.0. Measured three ways: replacing Source.Shape with a smaller box keeps the "
        "link resolving and correctly grades PASS; replacing it with a shape carrying no edges "
        "makes FreeCAD silently EMPTY the sketch's ExternalGeometry (measured "
        "'ExternalGeometry = []', sketch still isValid() and status 'Valid'), so "
        "snapshot_references returns zero records and there is no reference left to grade rather "
        "than a broken one; and removing the Source object outright makes the guard report "
        "'Sketch is no longer present in the document' although the Sketch object is present, "
        "which is a record-pairing defect in the guard, not a detection of this fault. Scoring "
        "any of these as a detection would credit the guard for a verdict it did not reach"
    ),
    "upstream_sketch_edge_insertion": (
        "the case grades DROPPED at layer 1 with must_not_be_caught_by: layer_0_error_sweep, and "
        "that combination is not reachable on FreeCAD 1.1.0. Measured over a parametric "
        "Part::Cut upstream of the fillet: renumbering that the element map survives keeps every "
        "mapped name (Edge1 -> Edge4 indexed, mapped 'Edge1;:H2b3,E' unchanged) and correctly "
        "grades PASS, while destroying the referenced topology outright marks the entry missing "
        "and the dress-up invalid, which is a layer-0 BROKEN verdict — the one the case excludes. "
        "A silent layer-1 drop needs the C++-only path DW-91 records"
    ),
}


REGISTRY = {
    "add_solid": add_solid,
    "add_solid_then_raise": add_solid_then_raise,
    "bump_element_map_version": bump_element_map_version,
    "change_external_geometry_source": change_external_geometry_source,
    "delete_attachment_support": delete_attachment_support,
    "drop_dressup_edge_silently": drop_dressup_edge_silently,
    "fillet_at_wrong_radius": fillet_at_wrong_radius,
    "fillet_the_intended_edge": fillet_the_intended_edge,
    "hole_at_wrong_diameter": hole_at_wrong_diameter,
    "hole_within_declared_tolerance": hole_within_declared_tolerance,
    "mirror_across_wrong_plane": mirror_across_wrong_plane,
    "nested_open_transaction_then_raise": nested_open_transaction_then_raise,
    "pad_in_negative_z": pad_in_negative_z,
    "pattern_with_commanded_count": pattern_with_commanded_count,
    "pattern_with_wrong_count": pattern_with_wrong_count,
    "pattern_with_wrong_spacing": pattern_with_wrong_spacing,
    "pocket_at_commanded_depth": pocket_at_commanded_depth,
    "pocket_at_wrong_depth": pocket_at_wrong_depth,
    "recompute_retaining_all_edges": recompute_retaining_all_edges,
    "recompute_retaining_original_element": recompute_retaining_original_element,
    "recompute_without_reference_change": recompute_without_reference_change,
    "remove_dressup_edge_as_intended": remove_dressup_edge_as_intended,
    "rename_expression_referent": rename_expression_referent,
    "reorder_boolean_operands": reorder_boolean_operands,
    "repoint_reference_to_congruent_twin": repoint_reference_to_congruent_twin,
    "revolve_through_wrong_angle": revolve_through_wrong_angle,
    "sketch_on_datum_plane_then_raise": sketch_on_datum_plane_then_raise,
    "upstream_sketch_edge_insertion": upstream_sketch_edge_insertion,
}


def resolve(name: str):
    """The callable ``name`` denotes.

    :raises KeyError: no op carries that name.
    """
    return REGISTRY[name]
