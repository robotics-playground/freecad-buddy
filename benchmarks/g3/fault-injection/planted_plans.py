"""The ``planted_op`` callables the G3 fault cases name, and the specs they corrupt.

Every driveable G3 fault ``case.yaml`` names a ``planted_op``. This module is the single place
those names resolve to a callable — the G3 analogue of ``benchmarks/g2/fault-injection/
planted_ops.py``, and written because the G2 history (DW-73) is that unresolved ``planted_op``
names left a whole suite unscoreable for months.

**A G3 planted op returns a PLAN, not geometry.** A corrupted plan is a plan, and planting the
fault means driving that plan through ``usecases.designer_loop.run_designer_loop`` so the deviant
part is produced by the production path. A defect hand-carved into a saved ``.FCStd`` would
validate nothing, because no production code path created it — which is exactly why all 29 G3
fault fixtures declared ``fixture: pending`` until the loop existed.

Two suites resolve here:

* ``corrupted-plan/`` (14 cases, validator ``corrupted_plan``) — does the LOOP notice that the
  part it built violates the spec it was given?
* ``assertions/`` (7 cases, validator ``g3_assertions``) — do the assertion PRIMITIVES catch a
  wrong part?

The eight ``visual-judge/`` cases resolve to nothing here and stay ``fixture: pending``: their
verdict needs a credentialed vision call, which decision 017 keeps out of unattended CI, so the
geometry is driveable and the verdict is not.

Each op returns a ``DesignPlan`` whose steps the loop executes. A corrupted op and the control it
pairs with call the SAME builder and differ in exactly the one thing the ``corruption_class``
names. Sharing the builder is load-bearing: without it the suite would measure the difference
between two hand-written plans rather than the corruption.

``UNDRIVEABLE`` names the ops whose corruption has no reachable trigger, each with the reason;
scoring those as misses would blame the validator for a trigger the suite cannot pull.
"""

from __future__ import annotations

import math

# The six referenced dev specs' driving numbers, taken from each ``case.yaml``'s own spec text.
# Named constants rather than literals inside the builders so a control and its defect provably
# differ in one substituted value.

# g3-dev-001-mounting-plate: 80 x 60 x 6 plate, four 5.5 mm holes 10 mm in from both edges.
PLATE_L = 80.0
PLATE_W = 60.0
PLATE_T = 6.0
PLATE_HOLE_D = 5.5
PLATE_HOLE_INSET = 10.0
# The substitutions the value-class defects make.
PLATE_HOLE_D_WRONG = 8.0
PLATE_T_WRONG = 8.0
# The tolerance-edge control: 0.04 mm oversize, inside the declared 0.05 mm band.
PLATE_HOLE_D_EDGE = 5.54

# g3-dev-003-shaft-collar: 40 mm OD, 16 mm bore, 15 mm wide.
COLLAR_OD = 40.0
COLLAR_BORE_D = 16.0
COLLAR_WIDTH = 15.0
# radius-for-diameter: the plan reads "16 mm bore" as a radius and sketches a 32 mm circle.
COLLAR_BORE_D_WRONG = 32.0

# g3-dev-007-jig-block-blind-bore: 50 mm square, 25 mm tall, 12 mm bore 15 mm deep in the top.
JIG_SIDE = 50.0
JIG_H = 25.0
JIG_BORE_D = 12.0
JIG_BORE_DEPTH = 15.0

# g3-dev-008-flange-gasket: 100 mm OD, 60 mm bore, 2 mm thick, six 8 mm holes on an 80 mm PCD.
GASKET_OD = 100.0
GASKET_BORE_D = 60.0
GASKET_T = 2.0
GASKET_BOLT_D = 8.0
GASKET_PCD = 80.0
GASKET_BOLT_N = 6

# g3-dev-010-cover-panel-window: 120 x 80 x 3 panel with a 60 x 30 window.
PANEL_L = 120.0
PANEL_W = 80.0
PANEL_T = 3.0
PANEL_WINDOW_L = 60.0
PANEL_WINDOW_W = 30.0
# The insertion defect's unrequested lightening pocket.
PANEL_EXTRA_POCKET = (20.0, 20.0, 1.5)

# g3-dev-011-lever-arm: 90 x 20 x 8 plate, 12 mm pivot and 8 mm linkage bore, both 15 mm in.
LEVER_L = 90.0
LEVER_W = 20.0
LEVER_T = 8.0
LEVER_PIVOT_D = 12.0
LEVER_LINK_D = 8.0
LEVER_INSET = 15.0

# g3-dev-012-clamp-pad-slot: 40 mm square, 20 mm tall, 20 x 10 slot across the top.
PAD_SIDE = 40.0
PAD_H = 20.0
PAD_SLOT_W = 20.0
PAD_SLOT_DEPTH = 10.0

# g3-dev-019-offset-pivot-plate: 60 mm square, 6 mm thick, one 10 mm hole at (20, 15) from the
# named corner datum.
PIVOT_SIDE = 60.0
PIVOT_T = 6.0
PIVOT_HOLE_D = 10.0
PIVOT_HOLE_X = 20.0
PIVOT_HOLE_Y = 15.0
# The mirrored-pattern assertion defect: the hole reflected about the plate's own mid-plane in Y,
# so the count and the diameter are unchanged and only a position measurement separates the two.
PIVOT_HOLE_Y_MIRRORED = PIVOT_SIDE - PIVOT_HOLE_Y

# g3-dev-005-rail-shim: 100 x 20 x 3 strip, two 6 mm holes 10 mm from each end (80 mm apart).
SHIM_L = 100.0
SHIM_W = 20.0
SHIM_T = 3.0
SHIM_HOLE_D = 6.0
SHIM_SPACING = 80.0
# The two spacing cases that calibrate the linear band rather than merely exercising it: 0.5 mm
# out is ten times the 0.05 mm band and must be caught; 0.04 mm out is inside it and must not be.
SHIM_SPACING_ERROR = 80.5
SHIM_SPACING_WITHIN_BAND = 80.04

# g3-dev-009-flanged-bushing: 30 mm flange 4 mm thick, 18 mm body 16 mm long, 10 mm bore through.
BUSHING_FLANGE_D = 30.0
BUSHING_FLANGE_T = 4.0
BUSHING_BODY_D = 18.0
BUSHING_BODY_L = 16.0
BUSHING_BORE_D = 10.0

# The mounting-plate assertion defects: one hole absent, and every hole 1 mm oversize.
PLATE_HOLE_COUNT = 4
PLATE_HOLE_COUNT_MISSING = 3
PLATE_HOLE_D_OVERSIZE = 6.5


class PlanNotDriveable(RuntimeError):
    """A corruption with no reachable trigger on this build; the case is not scorable."""


# The frame holder each referenced spec's ``anchor_frame`` resolves against, read off that spec's
# own ``case.yaml``. A ``largest_planar_face`` spec maps to ``None``: its frame comes from the
# part's geometry and needs no holder. Kept here rather than parsed from the case because a plan
# builds the datum it measures from — that IS a plan decision, and the frame-class corruption is
# exactly a plan measuring from the wrong one.
ANCHOR_BY_SPEC = {
    "g3-dev-001-mounting-plate": "XY_Plane",
    "g3-dev-003-shaft-collar": "XY_Plane",
    "g3-dev-005-rail-shim": "XY_Plane",
    "g3-dev-007-jig-block-blind-bore": None,  # largest_planar_face
    "g3-dev-008-flange-gasket": "XY_Plane",
    "g3-dev-009-flanged-bushing": "XZ_Plane",
    "g3-dev-010-cover-panel-window": "XY_Plane",
    "g3-dev-011-lever-arm": "XY_Plane",
    "g3-dev-012-clamp-pad-slot": None,  # largest_planar_face
    "g3-dev-019-offset-pivot-plate": "PlateCornerDatum",
}


def _plan(spec_id: str, steps: list[dict], rationale: str) -> dict:
    """Wrap ``steps`` as an approved ``DesignPlan`` for ``spec_id``.

    ``approved: True`` stands in for the one human approval the epic gives a real run. A fault
    case's plan is approved by construction: the suite measures whether the loop notices that the
    part it built violates the spec, which is a question about what happens *after* approval.

    The spec's declared anchor is written into every step here rather than by each op, so a defect
    and its control cannot accidentally build different datums and be separated by that instead of
    by the corruption.
    """
    anchor = ANCHOR_BY_SPEC.get(spec_id)
    for step in steps:
        step["args"].setdefault("anchor", anchor)
    return {
        "schema": "fcb.design-plan/1",
        "spec_id": spec_id,
        "spec_text": f"the {spec_id} spec",
        "steps": steps,
        "approved": True,
        "approved_by": "g3-fault-suite",
        "rationale": rationale,
    }


def _solid(builder: str, **params) -> dict:
    """One ``plan_shape`` step: build a solid from named parameters.

    The Phase-2 feature surface builds inside a ``PartDesign::Body`` from sketch profiles, which
    needs a sketch per feature and a solver solution per sketch. These fault cases measure whether
    the LOOP notices a violating part, not whether Sketcher converges, so they drive a step that
    produces the same geometry through ``Part`` primitives inside the same mutation bracket. The
    step still runs through ``run_mutation``: the production transaction, recompute, post-verify
    and commit-or-rollback path. What differs from a spec-to-part run is the profile source, not
    the mutation protocol.
    """
    return {"tool": "plan_shape", "args": {"builder": builder, **params}, "intent": builder}


# ------------------------------------------------------------------------------------------
# The shape builders each ``plan_shape`` step names. Executed by ``shape_step``, below.
# ------------------------------------------------------------------------------------------


def _drill(shape, diameter: float, centre, axis, length: float, start=None):
    """Cut one cylindrical bore of ``diameter`` through ``shape`` along ``axis``."""
    import FreeCAD as App
    import Part

    base = App.Vector(*(start if start is not None else centre))
    return shape.cut(Part.makeCylinder(diameter / 2.0, length, base, App.Vector(*axis)))


def build_plate(
    document,
    length: float,
    width: float,
    thickness: float,
    hole_diameter: float,
    inset: float,
    hole_count: int = 4,
    name: str = "Plate",
) -> list[str]:
    """A rectangular plate with a through hole at each corner, inset from both edges.

    ``hole_count`` drills the first N of the four corners, so the missing-hole defect differs from
    the correct part by exactly one absent feature and in nothing else.
    """
    import Part

    shape = Part.makeBox(length, width, thickness)
    corners = [(x, y) for x in (inset, length - inset) for y in (inset, width - inset)][:hole_count]
    for x, y in corners:
        shape = _drill(shape, hole_diameter, (x, y, 0.0), (0, 0, 1), thickness + 2.0, (x, y, -1.0))
    return _write(document, name, shape)


def build_shim(
    document,
    length: float,
    width: float,
    thickness: float,
    hole_diameter: float,
    spacing: float,
    name: str = "Shim",
) -> list[str]:
    """A shim strip with two through holes on the long centreline, ``spacing`` apart.

    The pair is centred on the strip, so a spacing substitution moves both holes symmetrically and
    changes nothing else — which is what makes the 0.5 mm defect and the 0.04 mm control differ in
    exactly the quantity ``hole_spacing`` measures.
    """
    import Part

    shape = Part.makeBox(length, width, thickness)
    centre_y = width / 2.0
    for x in ((length - spacing) / 2.0, (length + spacing) / 2.0):
        shape = _drill(
            shape,
            hole_diameter,
            (x, centre_y, 0.0),
            (0, 0, 1),
            thickness + 2.0,
            (x, centre_y, -1.0),
        )
    return _write(document, name, shape)


def build_flanged_bushing(
    document,
    flange_diameter: float,
    flange_thickness: float,
    body_diameter: float,
    body_length: float,
    bore_diameter: float,
    name: str = "Bushing",
) -> list[str]:
    """A flanged bushing bored right through: one logical hole with a stepped wall.

    The bore passes through both the flange and the body, so the shape presents two coaxial
    cylindrical faces that §7.3 rule 2's coaxial grouping must merge into one logical hole. That is
    the whole point of the stepped-bore control: an implementation that counts faces reports 2 and
    flags a correct part.
    """
    import FreeCAD as App
    import Part

    flange = Part.makeCylinder(flange_diameter / 2.0, flange_thickness)
    body = Part.makeCylinder(body_diameter / 2.0, body_length, App.Vector(0, 0, flange_thickness))
    shape = flange.fuse(body).removeSplitter()
    total = flange_thickness + body_length
    shape = _drill(shape, bore_diameter, (0, 0, 0), (0, 0, 1), total + 2.0, (0, 0, -1.0))
    return _write(document, name, shape)


def build_collar(
    document, outside_diameter: float, bore_diameter: float, width: float, name: str = "Collar"
) -> list[str]:
    """An annular collar: a cylinder of ``outside_diameter`` bored through its full width."""
    import Part

    shape = Part.makeCylinder(outside_diameter / 2.0, width)
    shape = _drill(shape, bore_diameter, (0, 0, 0), (0, 0, 1), width + 2.0, (0, 0, -1.0))
    return _write(document, name, shape)


def build_jig_block(
    document,
    side: float,
    height: float,
    bore_diameter: float,
    depth: float,
    face: str = "top",
    name: str = "JigBlock",
) -> list[str]:
    """A square block with one bore of ``depth`` into the named face.

    ``face`` selects which face the bore enters: ``"top"`` is the face the spec names, and
    ``"side"`` is the topology-class corruption — same diameter, same depth, a perpendicular axis.
    """
    import Part

    shape = Part.makeBox(side, side, height)
    centre = side / 2.0
    if face == "top":
        return _write(
            document,
            name,
            _drill(
                shape,
                bore_diameter,
                (centre, centre, height),
                (0, 0, -1),
                depth,
                (centre, centre, height),
            ),
        )
    return _write(
        document,
        name,
        _drill(
            shape,
            bore_diameter,
            (0.0, centre, height / 2.0),
            (1, 0, 0),
            depth,
            (0.0, centre, height / 2.0),
        ),
    )


def build_jig_block_through(
    document, side: float, height: float, bore_diameter: float, name: str = "JigBlock"
) -> list[str]:
    """The blind-bore block with the bore taken Through-All: the value-class corruption."""
    import Part

    shape = Part.makeBox(side, side, height)
    centre = side / 2.0
    return _write(
        document,
        name,
        _drill(
            shape,
            bore_diameter,
            (centre, centre, 0.0),
            (0, 0, 1),
            height + 2.0,
            (centre, centre, -1.0),
        ),
    )


def build_gasket(
    document,
    outside_diameter: float,
    bore_diameter: float,
    thickness: float,
    bolt_diameter: float,
    pitch_circle: float,
    bolt_count: int,
    name: str = "Gasket",
) -> list[str]:
    """A flange gasket ring with ``bolt_count`` bolt holes evenly spaced on ``pitch_circle``.

    ``bolt_count: 0`` builds the omission-class corruption: the ring and its bore, no bolt holes.
    """
    import Part

    shape = Part.makeCylinder(outside_diameter / 2.0, thickness)
    shape = _drill(shape, bore_diameter, (0, 0, 0), (0, 0, 1), thickness + 2.0, (0, 0, -1.0))
    radius = pitch_circle / 2.0
    for index in range(bolt_count):
        angle = 2.0 * math.pi * index / bolt_count
        x, y = radius * math.cos(angle), radius * math.sin(angle)
        shape = _drill(shape, bolt_diameter, (x, y, 0.0), (0, 0, 1), thickness + 2.0, (x, y, -1.0))
    return _write(document, name, shape)


def build_panel(
    document,
    length: float,
    width: float,
    thickness: float,
    window_length: float,
    window_width: float,
    extra_pocket=None,
    name: str = "Panel",
) -> list[str]:
    """A cover panel with a central rectangular window, optionally with an extra pocket.

    ``extra_pocket`` is the insertion-class corruption: a lightening pocket the spec never asked
    for. Every stated feature is present and correct; the part carries one that is not.
    """
    import FreeCAD as App
    import Part

    shape = Part.makeBox(length, width, thickness)
    window = Part.makeBox(
        window_length,
        window_width,
        thickness + 2.0,
        App.Vector((length - window_length) / 2.0, (width - window_width) / 2.0, -1.0),
    )
    shape = shape.cut(window)
    if extra_pocket is not None:
        pocket_l, pocket_w, pocket_d = extra_pocket
        shape = shape.cut(
            Part.makeBox(pocket_l, pocket_w, pocket_d, App.Vector(5.0, 5.0, thickness - pocket_d))
        )
    return _write(document, name, shape)


def build_lever(
    document,
    length: float,
    width: float,
    thickness: float,
    pivot_diameter: float,
    link_diameter: float,
    inset: float,
    mirrored: bool = False,
    name: str = "Lever",
) -> list[str]:
    """A lever arm with a pivot bore at one end and a linkage hole at the other.

    ``mirrored`` is the topology-class corruption: the two bores swap ends. Both holes exist at the
    right spacing and the right diameters — only which end each sits at is wrong.
    """
    import Part

    shape = Part.makeBox(length, width, thickness)
    centre = width / 2.0
    near, far = inset, length - inset
    pivot_x, link_x = (far, near) if mirrored else (near, far)
    shape = _drill(
        shape,
        pivot_diameter,
        (pivot_x, centre, 0.0),
        (0, 0, 1),
        thickness + 2.0,
        (pivot_x, centre, -1.0),
    )
    shape = _drill(
        shape,
        link_diameter,
        (link_x, centre, 0.0),
        (0, 0, 1),
        thickness + 2.0,
        (link_x, centre, -1.0),
    )
    return _write(document, name, shape)


def build_clamp_pad(
    document,
    side: float,
    height: float,
    slot_width: float,
    slot_depth: float,
    slot_buried: bool = False,
    name: str = "ClampPad",
) -> list[str]:
    """A clamp pad with a slot cut right across its top face, built as the spec's two operations.

    The spec's plan pads the block to its full height, then pockets the slot down from the top
    face. A pocket's depth is measured from whatever the top face is when it runs, which is what
    the ordering case turns on.

    ``slot_buried`` is the ordering-class corruption: the pocket runs before the block reaches full
    height, so it cuts into an intermediate face, and the remaining pad then closes over it. Every
    step and every dimension is the one the spec states; only their order is wrong.

    **Measured, not assumed:** the two parts differ by 4000 mm^3 (24000 correct, 28000 buried), and
    that surplus is the cavity the second pad sealed — the part carries material where the spec
    requires an open channel. Both remain single valid solids with the same bounding box and the
    same face count, so ``expect_volume`` is the only one of this spec's four assertions that
    separates them. That is the case working as intended: it is the ordering-class corruption
    precisely because the part looks right on every coarser measure.
    """
    import FreeCAD as App
    import Part

    x0 = (side - slot_width) / 2.0

    if slot_buried:
        # The pocket lands on the intermediate face at `slot_depth` and cuts half its depth, so it
        # does not sever the lower block; the covering pad then seals the cavity inside the solid.
        buried_depth = slot_depth / 2.0
        lower = Part.makeBox(side, side, slot_depth)
        pocket = Part.makeBox(
            slot_width, side, buried_depth, App.Vector(x0, 0.0, slot_depth - buried_depth)
        )
        cover = Part.makeBox(side, side, height - slot_depth, App.Vector(0.0, 0.0, slot_depth))
        return _write(document, name, lower.cut(pocket).fuse(cover).removeSplitter())

    # Pad to full height, then pocket the slot down from the real top face. The cutter overshoots
    # upward so the channel is open rather than sealed by a coincident face.
    block = Part.makeBox(side, side, height)
    slot = Part.makeBox(
        slot_width, side, slot_depth + 1.0, App.Vector(x0, 0.0, height - slot_depth)
    )
    return _write(document, name, block.cut(slot))


def build_pivot_plate(
    document,
    side: float,
    thickness: float,
    hole_diameter: float,
    hole_x: float,
    hole_y: float,
    from_centre: bool = False,
    name: str = "PivotPlate",
) -> list[str]:
    """A square pivot plate with one off-centre through hole.

    ``from_centre`` is the frame-class corruption: the same stated offsets applied from the plate
    CENTRE instead of the corner datum the spec declares. The hole is the right diameter and goes
    through; it sits at the wrong place because the frame the plan measured from is wrong. The
    datum itself is created by the step's ``anchor``, so the defect and its control build the same
    datum and differ only in where the plan measured from.
    """
    import Part

    shape = Part.makeBox(side, side, thickness)
    origin = (side / 2.0, side / 2.0) if from_centre else (0.0, 0.0)
    x, y = origin[0] + hole_x, origin[1] + hole_y
    shape = _drill(shape, hole_diameter, (x, y, 0.0), (0, 0, 1), thickness + 2.0, (x, y, -1.0))
    return _write(document, name, shape)


def _write(document, name: str, shape) -> list[str]:
    """Put ``shape`` on the document's ``name`` object, creating it when absent."""
    obj = document.getObject(name)
    if obj is None:
        obj = document.addObject("Part::Feature", name)
    obj.Shape = shape
    return [obj.Name]


def ensure_anchor(document, anchor: str | None) -> list[str]:
    """Create the frame holder a spec's declared ``anchor_frame`` resolves against.

    Sixteen of the twenty G3 specs declare ``base_sketch_plane`` with a ``ref`` of ``XY_Plane`` or
    ``XZ_Plane``, and one declares a ``named_datum``. Those names are the design datum the spec's
    numbers are stated from, so the resolver needs an object carrying them
    (``assertions._frame_from_placement_holder`` matches ``Name`` or ``Label``). A part built from
    ``Part`` primitives carries none, and without one the frame does not resolve — which reports
    every check ``INVALID_INPUT`` and makes a defect and its control indistinguishable.

    An ``App::Placement`` is used rather than a Body origin plane: it carries a ``Placement`` (all
    the resolver reads) and no ``Shape``, so it cannot become the object the assertions grade.
    ``_shape_bearing_objects`` excludes datum TYPES, not names, so a shape-bearing stand-in would
    silently be measured instead of the part.

    ``None`` creates nothing, which is what a ``largest_planar_face`` spec needs: its frame is
    derived from the part's own geometry.
    """
    if not anchor:
        return []
    import FreeCAD as App

    holder = document.getObject(anchor)
    if holder is None:
        holder = document.addObject("App::Placement", anchor)
        holder.Label = anchor
    holder.Placement = App.Placement(
        App.Vector(0, 0, 0), App.Rotation(*_ANCHOR_ROTATIONS.get(anchor, IDENTITY))
    )
    return [holder.Name]


# The rotation each named base plane carries, matching ``sketches._BASE_PLANES``: a sketch on XY
# is unrotated, and one on XZ is turned 90 degrees about X. The frame's basis comes from this
# rotation, so a spec measuring in XZ must get the XZ basis or its in-frame extents are permuted.
IDENTITY = (0.0, 0.0, 0.0, 1.0)
_SIN_45 = 0.7071067811865476
_ANCHOR_ROTATIONS = {
    "XY_Plane": IDENTITY,
    "XZ_Plane": (_SIN_45, 0.0, 0.0, _SIN_45),
    "YZ_Plane": (0.5, 0.5, 0.5, 0.5),
}


BUILDERS = {
    "plate": build_plate,
    "shim": build_shim,
    "flanged_bushing": build_flanged_bushing,
    "collar": build_collar,
    "jig_block": build_jig_block,
    "jig_block_through": build_jig_block_through,
    "gasket": build_gasket,
    "panel": build_panel,
    "lever": build_lever,
    "clamp_pad": build_clamp_pad,
    "pivot_plate": build_pivot_plate,
}


def shape_step(
    registry, doc=None, builder=None, anchor=None, confirm=None, audit_sink=None, **params
):
    """The ``plan_shape`` tool: run a named builder through the production mutation bracket.

    Signature-compatible with the ``usecases.sketches`` / ``usecases.features`` tools the loop
    resolves, so the loop drives it by the same path and through the same ``run_mutation``
    protocol. It lives here rather than in ``usecases/`` because it exists only to give the fault
    suite a deterministic profile source; no shipped tool call reaches it.

    ``anchor`` names the frame holder the spec's ``anchor_frame`` resolves against, created in the
    same mutation as the shape. It has to be the same mutation: ``post_verify`` grades what the op
    touched, so a datum added by a second bracket would be verified separately from the part it
    anchors, and a rolled-back shape would leave an orphan datum behind.
    """
    from freecad_buddy.usecases import transaction

    function = BUILDERS.get(builder)
    if function is None:
        raise KeyError(f"no shape builder named {builder!r} (known: {sorted(BUILDERS)})")

    def op(target):
        return ensure_anchor(target, anchor) + function(target, **params)

    rebound = []

    def call(handle, document):
        result = transaction.run_mutation(
            document,
            handle,
            f"plan_shape {builder}",
            op,
            audit_sink=audit_sink,
            tool="plan_shape",
            params={"builder": builder, "anchor": anchor, **params},
        )
        rebound.append(result[0])
        return result

    try:
        _, envelope = registry.with_document(doc, call)
    finally:
        # DW-71: the snapshot-restore path closes and reopens the document, so the handle is
        # rebound from whatever the bracket last reached — including when it raised.
        if rebound:
            registry.rebind(doc, rebound[-1])
    return envelope


# ------------------------------------------------------------------------------------------
# The planted ops. Each returns the plan its case drives.
# ------------------------------------------------------------------------------------------


def faithful_mounting_plate() -> dict:
    """The plan the mounting-plate spec actually asks for."""
    return _plan(
        "g3-dev-001-mounting-plate",
        [
            _solid(
                "plate",
                length=PLATE_L,
                width=PLATE_W,
                thickness=PLATE_T,
                hole_diameter=PLATE_HOLE_D,
                inset=PLATE_HOLE_INSET,
            )
        ],
        "the spec's own numbers, unsubstituted",
    )


def wrong_hole_diameter() -> dict:
    """Drill 8 mm holes where the spec states 5.5 mm M5 clearance (value class)."""
    return _plan(
        "g3-dev-001-mounting-plate",
        [
            _solid(
                "plate",
                length=PLATE_L,
                width=PLATE_W,
                thickness=PLATE_T,
                hole_diameter=PLATE_HOLE_D_WRONG,
                inset=PLATE_HOLE_INSET,
            )
        ],
        f"hole diameter {PLATE_HOLE_D_WRONG} substituted for {PLATE_HOLE_D}",
    )


def wrong_plate_thickness() -> dict:
    """Pad the base sketch 8 mm where the spec states 6 mm (value class)."""
    return _plan(
        "g3-dev-001-mounting-plate",
        [
            _solid(
                "plate",
                length=PLATE_L,
                width=PLATE_W,
                thickness=PLATE_T_WRONG,
                hole_diameter=PLATE_HOLE_D,
                inset=PLATE_HOLE_INSET,
            )
        ],
        f"thickness {PLATE_T_WRONG} substituted for {PLATE_T}",
    )


def tolerance_edge_hole() -> dict:
    """A faithful plan whose hole lands 0.04 mm oversize — inside the 0.05 mm band."""
    return _plan(
        "g3-dev-001-mounting-plate",
        [
            _solid(
                "plate",
                length=PLATE_L,
                width=PLATE_W,
                thickness=PLATE_T,
                hole_diameter=PLATE_HOLE_D_EDGE,
                inset=PLATE_HOLE_INSET,
            )
        ],
        f"hole diameter {PLATE_HOLE_D_EDGE}: {PLATE_HOLE_D_EDGE - PLATE_HOLE_D:.2f} mm oversize, "
        "inside the declared 0.05 mm band",
    )


def radius_for_diameter() -> dict:
    """Read the collar's 16 mm bore as a radius and sketch a 32 mm circle (value class)."""
    return _plan(
        "g3-dev-003-shaft-collar",
        [
            _solid(
                "collar",
                outside_diameter=COLLAR_OD,
                bore_diameter=COLLAR_BORE_D_WRONG,
                width=COLLAR_WIDTH,
            )
        ],
        f"bore {COLLAR_BORE_D} read as a radius and sketched as {COLLAR_BORE_D_WRONG}",
    )


def blind_hole_made_through() -> dict:
    """Give the jig block's bore a Through-All depth where 15 mm blind was stated (value class)."""
    return _plan(
        "g3-dev-007-jig-block-blind-bore",
        [_solid("jig_block_through", side=JIG_SIDE, height=JIG_H, bore_diameter=JIG_BORE_D)],
        f"Through-All substituted for the stated {JIG_BORE_DEPTH} mm blind depth",
    )


def hole_on_wrong_face() -> dict:
    """Sketch the bore on a side face instead of the top face the spec names (topology class)."""
    return _plan(
        "g3-dev-007-jig-block-blind-bore",
        [
            _solid(
                "jig_block",
                side=JIG_SIDE,
                height=JIG_H,
                bore_diameter=JIG_BORE_D,
                depth=JIG_BORE_DEPTH,
                face="side",
            )
        ],
        "the bore's profile placed on a side face; diameter and depth unchanged",
    )


def missing_bolt_holes() -> dict:
    """Build the gasket ring and its bore but omit the six bolt holes (omission class)."""
    return _plan(
        "g3-dev-008-flange-gasket",
        [
            _solid(
                "gasket",
                outside_diameter=GASKET_OD,
                bore_diameter=GASKET_BORE_D,
                thickness=GASKET_T,
                bolt_diameter=GASKET_BOLT_D,
                pitch_circle=GASKET_PCD,
                bolt_count=0,
            )
        ],
        f"the {GASKET_BOLT_N} bolt holes the spec requires are absent from the plan",
    )


def extra_unrequested_pocket() -> dict:
    """Add a lightening pocket the cover-panel spec never asked for (insertion class)."""
    return _plan(
        "g3-dev-010-cover-panel-window",
        [
            _solid(
                "panel",
                length=PANEL_L,
                width=PANEL_W,
                thickness=PANEL_T,
                window_length=PANEL_WINDOW_L,
                window_width=PANEL_WINDOW_W,
                extra_pocket=list(PANEL_EXTRA_POCKET),
            )
        ],
        "one step added that no spec sentence asks for",
    )


def mirrored_hole_pattern() -> dict:
    """Mirror the lever arm's holes about the wrong axis, swapping ends (topology class)."""
    return _plan(
        "g3-dev-011-lever-arm",
        [
            _solid(
                "lever",
                length=LEVER_L,
                width=LEVER_W,
                thickness=LEVER_T,
                pivot_diameter=LEVER_PIVOT_D,
                link_diameter=LEVER_LINK_D,
                inset=LEVER_INSET,
                mirrored=True,
            )
        ],
        "the mirror plane substituted; both diameters and the spacing unchanged",
    )


def pocket_before_pad() -> dict:
    """Pocket the slot before padding the block to full height (ordering class)."""
    return _plan(
        "g3-dev-012-clamp-pad-slot",
        [
            _solid(
                "clamp_pad",
                side=PAD_SIDE,
                height=PAD_H,
                slot_width=PAD_SLOT_W,
                slot_depth=PAD_SLOT_DEPTH,
                slot_buried=True,
            )
        ],
        "the same two steps in the order that buries the slot",
    )


def equivalent_step_order() -> dict:
    """The same two steps reordered, geometry-preserving — the discriminating control.

    Pairs with :func:`pocket_before_pad`: the same reordering, but this one produces the part the
    spec asks for. A guard that flags any reorder fails here; only measuring the produced part
    separates the two.
    """
    return _plan(
        "g3-dev-012-clamp-pad-slot",
        [
            _solid(
                "clamp_pad",
                side=PAD_SIDE,
                height=PAD_H,
                slot_width=PAD_SLOT_W,
                slot_depth=PAD_SLOT_DEPTH,
                slot_buried=False,
            )
        ],
        "steps reordered with no effect on the produced geometry",
    )


def datum_origin_swapped() -> dict:
    """Measure the pivot plate's hole offsets from the plate centre, not the datum (frame class)."""
    return _plan(
        "g3-dev-019-offset-pivot-plate",
        [
            _solid(
                "pivot_plate",
                side=PIVOT_SIDE,
                thickness=PIVOT_T,
                hole_diameter=PIVOT_HOLE_D,
                hole_x=PIVOT_HOLE_X,
                hole_y=PIVOT_HOLE_Y,
                from_centre=True,
            )
        ],
        "the same offsets measured from the plate centre instead of the named corner datum",
    )


def named_datum_honoured() -> dict:
    """The faithful pivot-plate plan: the offsets measured from the named corner datum."""
    return _plan(
        "g3-dev-019-offset-pivot-plate",
        [
            _solid(
                "pivot_plate",
                side=PIVOT_SIDE,
                thickness=PIVOT_T,
                hole_diameter=PIVOT_HOLE_D,
                hole_x=PIVOT_HOLE_X,
                hole_y=PIVOT_HOLE_Y,
                from_centre=False,
            )
        ],
        "the spec's declared frame honoured; identical operation list to datum_origin_swapped",
    )


# ------------------------------------------------------------------------------------------
# The assertion-suite ops (``assertions/``, targeting ``g3_assertions``).
#
# These plant a geometry defect rather than a plan corruption, so what they measure is whether the
# assertion PRIMITIVES catch a wrong part — not whether the loop notices. They are driven through
# the same loop for the same reason: a defect the production path produced is what the suite
# exists to grade, and a defect hand-carved into a fixture proves nothing about the guards.
# ------------------------------------------------------------------------------------------


def assert_correct_part() -> dict:
    """The mounting plate the spec asks for: the control missing-hole and wrong-diameter pair to."""
    return faithful_mounting_plate()


def assert_missing_hole() -> dict:
    """Drill three of the four corner holes (count_cylindrical_holes measures 3 against 4)."""
    return _plan(
        "g3-dev-001-mounting-plate",
        [
            _solid(
                "plate",
                length=PLATE_L,
                width=PLATE_W,
                thickness=PLATE_T,
                hole_diameter=PLATE_HOLE_D,
                inset=PLATE_HOLE_INSET,
                hole_count=PLATE_HOLE_COUNT_MISSING,
            )
        ],
        f"{PLATE_HOLE_COUNT_MISSING} of {PLATE_HOLE_COUNT} corner holes drilled",
    )


def assert_wrong_diameter() -> dict:
    """Drill every hole 6.5 mm instead of 5.5 mm — twenty times the 0.05 mm linear band."""
    return _plan(
        "g3-dev-001-mounting-plate",
        [
            _solid(
                "plate",
                length=PLATE_L,
                width=PLATE_W,
                thickness=PLATE_T,
                hole_diameter=PLATE_HOLE_D_OVERSIZE,
                inset=PLATE_HOLE_INSET,
            )
        ],
        f"hole diameter {PLATE_HOLE_D_OVERSIZE} substituted for {PLATE_HOLE_D}",
    )


def assert_mirrored_pattern() -> dict:
    """Mirror the pivot plate's hole about the plate's own mid-plane in Y.

    The count and the diameter are unchanged, so only ``hole_position`` — measured in the spec's
    named corner datum — separates it from the correct part.
    """
    return _plan(
        "g3-dev-019-offset-pivot-plate",
        [
            _solid(
                "pivot_plate",
                side=PIVOT_SIDE,
                thickness=PIVOT_T,
                hole_diameter=PIVOT_HOLE_D,
                hole_x=PIVOT_HOLE_X,
                hole_y=PIVOT_HOLE_Y_MIRRORED,
                from_centre=False,
            )
        ],
        f"hole Y mirrored from {PIVOT_HOLE_Y} to {PIVOT_HOLE_Y_MIRRORED}; count and diameter kept",
    )


def assert_spacing_error_0p5mm() -> dict:
    """Space the shim's holes 80.5 mm apart where the spec states 80 mm."""
    return _plan(
        "g3-dev-005-rail-shim",
        [
            _solid(
                "shim",
                length=SHIM_L,
                width=SHIM_W,
                thickness=SHIM_T,
                hole_diameter=SHIM_HOLE_D,
                spacing=SHIM_SPACING_ERROR,
            )
        ],
        f"spacing {SHIM_SPACING_ERROR} substituted for {SHIM_SPACING}: ten times the 0.05 mm band",
    )


def assert_within_band_spacing() -> dict:
    """Space the shim's holes 80.04 mm apart — inside the 0.05 mm band, so it must not flag.

    The calibration control: a tolerance tightened until the 0.5 mm defect is caught but this one
    is too is mis-calibrated, and this case is what measures that.
    """
    return _plan(
        "g3-dev-005-rail-shim",
        [
            _solid(
                "shim",
                length=SHIM_L,
                width=SHIM_W,
                thickness=SHIM_T,
                hole_diameter=SHIM_HOLE_D,
                spacing=SHIM_SPACING_WITHIN_BAND,
            )
        ],
        f"spacing {SHIM_SPACING_WITHIN_BAND}: "
        f"{SHIM_SPACING_WITHIN_BAND - SHIM_SPACING:.2f} mm out, inside the 0.05 mm band",
    )


def assert_stepped_bore_one_hole() -> dict:
    """The flanged bushing whose stepped bore must group into ONE logical hole."""
    return _plan(
        "g3-dev-009-flanged-bushing",
        [
            _solid(
                "flanged_bushing",
                flange_diameter=BUSHING_FLANGE_D,
                flange_thickness=BUSHING_FLANGE_T,
                body_diameter=BUSHING_BODY_D,
                body_length=BUSHING_BODY_L,
                bore_diameter=BUSHING_BORE_D,
            )
        ],
        "two coaxial bore faces that coaxial grouping must merge into one logical hole",
    )


# Ops whose corruption is UNSCORABLE against its own spec, each with the measured reason. Excluded
# from the validator's population rather than counted as misses: scoring a case the spec cannot
# decide would blame the loop for an assertion set that was never authored to catch it.
#
# Both entries are the same defect, found by running the suite: the case declares
# ``detected_by: hole_position``, and the spec it references declares no ``hole_position`` check.
# The corruption is therefore invisible to every assertion the spec DOES declare. Fixing it means
# editing the dev spec's assertion set — which AD-19 forbids doing to make a fault case pass, since
# those assertions were compiled before any designer code existed. It is recorded here and reported
# by the scorer so the gap is visible rather than absorbed into a sensitivity number.
UNDRIVEABLE: dict[str, str] = {
    "hole_on_wrong_face": (
        "g3-fault-plan-hole-on-wrong-face declares detected_by: hole_position, but its spec "
        "g3-dev-007-jig-block-blind-bore declares no hole_position check. Measured: moving the "
        "12 mm x 15 mm bore from the top face to a side face leaves every declared assertion "
        "passing — volume 60803.540 (expect 60803.54), bbox [50, 50, 25], one logical hole, "
        "diameter 12.0, hole_through False. The axis direction is what changed and no declared "
        "assertion reads it. Scoring this as a miss would blame the loop for a spec that cannot "
        "decide the case; the fix is a hole_position or expect_extent check on the dev spec, which "
        "is an assertion-set change and not this story's to make (AD-19)"
    ),
    "mirrored_hole_pattern": (
        "g3-fault-plan-mirrored-hole-pattern declares detected_by: hole_position, but its spec "
        "g3-dev-011-lever-arm declares no hole_position check. Measured: swapping the 12 mm pivot "
        "and the 8 mm linkage bore between the two ends leaves volume 13093.097, bbox "
        "[90, 20, 8], two logical holes, spacing 60.0 and hole_through True — every declared "
        "assertion passes, because the pattern is symmetric under the mirror in all of them. Only "
        "WHICH end carries WHICH diameter changed, and that needs a per-hole position or a "
        "diameter-banded position check the spec does not declare"
    ),
}


REGISTRY = {
    "assert_correct_part": assert_correct_part,
    "assert_mirrored_pattern": assert_mirrored_pattern,
    "assert_missing_hole": assert_missing_hole,
    "assert_spacing_error_0p5mm": assert_spacing_error_0p5mm,
    "assert_stepped_bore_one_hole": assert_stepped_bore_one_hole,
    "assert_within_band_spacing": assert_within_band_spacing,
    "assert_wrong_diameter": assert_wrong_diameter,
    "blind_hole_made_through": blind_hole_made_through,
    "datum_origin_swapped": datum_origin_swapped,
    "equivalent_step_order": equivalent_step_order,
    "extra_unrequested_pocket": extra_unrequested_pocket,
    "faithful_mounting_plate": faithful_mounting_plate,
    "hole_on_wrong_face": hole_on_wrong_face,
    "missing_bolt_holes": missing_bolt_holes,
    "mirrored_hole_pattern": mirrored_hole_pattern,
    "named_datum_honoured": named_datum_honoured,
    "pocket_before_pad": pocket_before_pad,
    "radius_for_diameter": radius_for_diameter,
    "tolerance_edge_hole": tolerance_edge_hole,
    "wrong_hole_diameter": wrong_hole_diameter,
    "wrong_plate_thickness": wrong_plate_thickness,
}


def resolve(name: str):
    """The plan builder ``name`` denotes.

    :raises KeyError: no op carries that name.
    """
    return REGISTRY[name]
