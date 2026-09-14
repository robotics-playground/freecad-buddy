"""The eight parts the ``visual-judge/`` suite grades, built through the production path.

Each case in ``visual-judge/`` names a ``planted_op`` that resolves here. An op returns a PLAN,
exactly as the ``corrupted-plan/`` and ``assertions/`` ops in ``planted_plans.py`` do, and the plan
is driven through ``usecases.designer_loop.run_designer_loop``. A defect hand-carved into a saved
shape would validate nothing, because no production code path created it (DW-73/DW-93).

Why these parts are not built by ``planted_plans.BUILDERS``
-----------------------------------------------------------

The other two G3 suites build with ``Part`` primitives and write the result onto a
``Part::Feature``. That is enough for them: they are graded by geometry assertions, which measure a
shape.

This suite is graded from a DRAWING as well as a shape, and ``techdraw_for_judge`` sources every
callout from the part's declared driving parameters — it refuses to read a dimension off the
produced geometry, because a drawing derived from the shape would agree with the part however wrong
the part was. A ``Part::Feature`` carrying a computed shape exposes no length property for a
parameter to drive, so it can carry no declared dimension and gets no sheet. Measured: the call
raises ``ValidationError`` ("exposes no driving parameters").

So every part here is a tree of PARAMETRIC primitives (``Part::Box``, ``Part::Cylinder``,
``Part::Cut``, ``Part::Fuse``) whose driving lengths are declared through
``usecases.parameters.declare`` — the same façade a real part uses. The shape is still produced by
the production mutation bracket; what differs from the other two suites is the profile source, not
the mutation protocol.

Gauges
------

The façade binds a driven property to the expression ``Parameters.<name>`` verbatim, and it accepts
only a two-segment ``Feature.Property`` path. Two consequences shape every builder below.

* A DIAMETER cannot drive a ``Part::Cylinder.Radius``: the bound expression would write 21 into a
  radius and produce a part twice its stated size. Measured directly.
* A hole POSITION cannot be driven at all, because it lives at ``Placement.Base.x``, one segment
  deeper than the façade accepts.

Both are solved the same way: the parameter drives the ``Length`` of a zero-volume gauge box, and
the feature that needs the value follows that gauge by expression (``Gauge.Length / 2`` for a
radius, ``Gauge.Placement.Base.x + Gauge.Length`` for the far hole). A gauge carries no volume and
is hidden, so it never reaches the shape the assertions or the renderer see. The declared dimension
stays the diameter or the pitch the spec actually states, which is what the sheet must show.

The wrong-dimension-callout case depends on this split
------------------------------------------------------

That case's defect lives in the SHEET, not in the solid: the part is correct and its hole-pitch
callout reads 60 mm against an 80 mm pitch. The fault is only expressible because the callout comes
from a declared parameter rather than from the geometry. It is planted by declaring ``hole_pitch``
at the wrong value and then re-pinning the holes to their correct literal positions, so the number
on the drawing moves and the solid does not.
"""

from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parents[2]
SRC = REPO_ROOT / "src"
for _path in (str(SRC), str(REPO_ROOT)):
    if _path not in sys.path:
        sys.path.insert(0, _path)


# ------------------------------------------------------------------------------------------
# The referenced dev specs' driving numbers, taken from each ``case.yaml``'s own spec text.
# ------------------------------------------------------------------------------------------

# g3-dev-002-l-bracket: 5 mm plate; 60 x 40 horizontal leg, vertical leg rising to 50 mm, with one
# 9 mm clearance hole through the vertical leg, 12 mm from ONE edge and 30 mm up.
BRACKET_LEG_L = 60.0
BRACKET_WIDTH = 40.0
BRACKET_T = 5.0
BRACKET_HEIGHT = 50.0
BRACKET_HOLE_D = 9.0
# 12 mm from one 40 mm edge puts the hole off the mid-plane by 8 mm, so the mirror moves it 16 mm.
# That is 320 times the 0.05 mm linear band, which no assertion the spec declares can read, and it
# is large enough to be unmistakable in the render rather than a subtle shift a judge might excuse.
BRACKET_HOLE_INSET = 12.0
BRACKET_HOLE_HEIGHT = 30.0

# g3-dev-005-rail-shim: 100 x 20 x 3 strip, two 6 mm holes 80 mm apart on the long centreline.
SHIM_L = 100.0
SHIM_W = 20.0
SHIM_T = 3.0
SHIM_HOLE_D = 6.0
SHIM_PITCH = 80.0
# wrong-proportions: 60 mm wide instead of 20 mm. Three times the stated width, so the error reads
# from the iso view without measurement, which is what that case is authored to test.
SHIM_W_WRONG = 60.0
# wrong-dimension-callout: the number the SHEET carries. The part keeps SHIM_PITCH.
SHIM_PITCH_CALLOUT_WRONG = 60.0

# g3-dev-009-flanged-bushing: 30 mm flange 4 mm thick, 18 mm body 16 mm long, 10 mm bore through.
BUSHING_FLANGE_D = 30.0
BUSHING_FLANGE_T = 4.0
BUSHING_BODY_D = 18.0
BUSHING_BODY_L = 16.0
BUSHING_BORE_D = 10.0

# g3-dev-015-ribbed-pad: 60 x 40 x 5 base, a 60 x 6 rib rising 20 mm above it.
PAD_L = 60.0
PAD_W = 40.0
PAD_T = 5.0
RIB_L = 60.0
RIB_T = 6.0
RIB_H = 20.0

# g3-dev-018-flat-washer: 21 mm OD, 10.3 mm bore, 2 mm thick.
WASHER_OD = 21.0
WASHER_BORE_D = 10.3
WASHER_T = 2.0

# Every cut tool overshoots the material it passes through by this much at each end, so a through
# feature is unambiguously through and leaves no zero-thickness face for OCCT to resolve.
_OVERSHOOT = 1.0

# A gauge's cross-section. Measured: ``Part::Box`` recomputes to ``Invalid`` at 1e-7 mm and to
# ``Up-to-date`` at 1e-6, so this is the smallest section that yields a valid shape. A gauge is
# never fused into the part, so the section only has to keep the box itself recomputable.
_GAUGE_SECTION = 1e-6


def _box(document, name, length, width, height, at=(0.0, 0.0, 0.0)):
    """One ``Part::Box`` at ``at``, with its three driving lengths set."""
    import FreeCAD as App

    box = document.addObject("Part::Box", name)
    box.Length, box.Width, box.Height = length, width, height
    box.Placement.Base = App.Vector(*at)
    return box


def _gauge(document, name, value, at=(0.0, 0.0, 0.0)):
    """A zero-volume box whose ``Length`` carries a declared dimension for features to follow.

    Hidden and never fused into the part: it exists only to give a diameter or a pitch a
    two-segment ``Feature.Property`` path the parameter façade can bind to.
    """
    box = _box(document, name, value, _GAUGE_SECTION, _GAUGE_SECTION, at=at)
    box.Visibility = False
    return box


def _cylinder(document, name, diameter_gauge, height, at=(0.0, 0.0, 0.0)):
    """One ``Part::Cylinder`` whose radius follows ``diameter_gauge``'s length, axis +Z."""
    import FreeCAD as App

    cylinder = document.addObject("Part::Cylinder", name)
    cylinder.Height = height
    cylinder.Placement.Base = App.Vector(*at)
    cylinder.setExpression("Radius", f"{diameter_gauge.Name}.Length / 2")
    return cylinder


def _consume(base, tool) -> None:
    """Hide the two children a boolean consumed.

    The FreeCAD GUI hides an operand when a boolean absorbs it; headless ``addObject`` does not, so
    every intermediate stays visible and ``screenshot._build_scene`` renders the tool cylinders and
    the un-bored stock alongside the finished part. Two measured consequences, both fixed by
    hiding: the judge's iso view shows scaffolding rather than the part, and rendering a child that
    shares its parent's underlying shape re-tessellates it — which moved the flangeless sleeve's
    reported centre of mass by 0.02 mm and tripped the screenshot read-only guard.
    """
    base.Visibility = False
    tool.Visibility = False


def _cut(document, name, base, tool):
    """One ``Part::Cut`` of ``tool`` out of ``base``."""
    cut = document.addObject("Part::Cut", name)
    cut.Base, cut.Tool = base, tool
    _consume(base, tool)
    return cut


def _fuse(document, name, base, tool):
    """One ``Part::Fuse`` of ``base`` and ``tool``, refined so the joint leaves no seam face."""
    fuse = document.addObject("Part::Fuse", name)
    fuse.Base, fuse.Tool = base, tool
    fuse.Refine = True
    _consume(base, tool)
    return fuse


# ------------------------------------------------------------------------------------------
# The shape builders. Each returns ``(object_names, parameter_declarations)``.
#
# A declaration is ``(parameter_name, value, [driven paths])``, applied by ``visual_step`` through
# ``usecases.parameters.declare`` after the shape is built, because a parameter can only bind to a
# property that already exists.
# ------------------------------------------------------------------------------------------


def build_l_bracket(
    document,
    leg_length,
    width,
    thickness,
    height,
    hole_diameter,
    hole_inset,
    hole_height,
    mirrored=False,
    name="Bracket",
):
    """An L-shaped angle bracket with one clearance hole through its vertical leg.

    The hole is what makes this part CHIRAL, and the chirality is the whole point of the case that
    mirrors it. The bare L is not: its vertical leg spans the full 40 mm width, so the solid is
    symmetric about its own mid-plane in Y, and reflecting it is the same as turning it 180 degrees
    about the vertical axis. Measured — mirror the bare L, rotate the result 180 degrees about Z,
    and intersect it with the original: the common volume is the full 21000 mm^3, so the two builds
    are one part in two orientations and no judge could call either wrong (DW-127). Setting the
    hole ``hole_inset`` from ONE edge breaks that symmetry, and only then does a mirror produce a
    part that cannot be rotated back.

    ``mirrored`` reflects the part in Y, about the mid-plane of its own width. The hole moves to
    the opposite edge; every other dimension is unchanged. Volume, bounding box, the angle between
    the legs, the hole count and the hole diameter are all invariant under that reflection, which
    is what keeps the case's ``must_not_be_caught_by: geometry_assertions_pass`` true. What the
    reflection does change is which edge the hole sits near, and the dev spec states that edge, so
    the mirrored build violates a stated requirement the assertions cannot measure.
    """
    horizontal = _box(document, f"{name}Leg", leg_length, width, thickness)
    # The vertical leg sits above the shared corner thickness, so the legs meet without overlapping
    # volume and the total height is the spec's stated height.
    vertical = _box(
        document,
        f"{name}Riser",
        thickness,
        width,
        height - thickness,
        at=(0.0, 0.0, thickness),
    )
    stock = _fuse(document, f"{name}Stock", horizontal, vertical)

    hole_gauge = _gauge(document, f"{name}HoleGauge", hole_diameter)
    hole_y = width - hole_inset if mirrored else hole_inset
    # The bore runs through the vertical leg along X, so it is turned onto that axis and started
    # clear of the leg's outer face.
    hole = _cylinder(
        document,
        f"{name}Hole",
        hole_gauge,
        thickness + 2.0 * _OVERSHOOT,
        at=(-_OVERSHOOT, hole_y, hole_height),
    )
    hole.Placement.Rotation = _rotation_about_y_to_x()
    shape = _cut(document, name, stock, hole)
    declarations = [
        ("bracket_leg_length", leg_length, [f"{horizontal.Name}.Length"]),
        ("bracket_width", width, [f"{horizontal.Name}.Width"]),
        ("bracket_thickness", thickness, [f"{horizontal.Name}.Height", f"{vertical.Name}.Length"]),
        ("hole_diameter", hole_diameter, [f"{hole_gauge.Name}.Length"]),
    ]
    return [shape.Name], declarations


def _rotation_about_y_to_x():
    """The rotation that turns a +Z cylinder axis onto +X."""
    import FreeCAD as App

    return App.Rotation(App.Vector(0, 1, 0), 90)


def build_ribbed_pad(
    document,
    length,
    width,
    thickness,
    rib_length,
    rib_thickness,
    rib_height,
    on_short_edge=False,
    name="RibbedPad",
):
    """A base plate with one vertical rib standing on it.

    The spec puts the rib on the base's LONG centreline, running the full 60 mm length. Every rib
    dimension below is the spec's; ``on_short_edge`` changes only which centreline it stands on,
    turning it 90 degrees to run across the 40 mm width instead. That is the feature-on-wrong-face
    defect: the rib's own dimensions stay correct and only its host edge is wrong.
    """
    base = _box(document, f"{name}Base", length, width, thickness)
    if on_short_edge:
        rib = _box(
            document,
            f"{name}Rib",
            rib_thickness,
            rib_length,
            rib_height,
            at=((length - rib_thickness) / 2.0, (width - rib_length) / 2.0, thickness),
        )
    else:
        rib = _box(
            document,
            f"{name}Rib",
            rib_length,
            rib_thickness,
            rib_height,
            at=((length - rib_length) / 2.0, (width - rib_thickness) / 2.0, thickness),
        )
    shape = _fuse(document, name, base, rib)
    declarations = [
        ("pad_length", length, [f"{base.Name}.Length"]),
        ("pad_width", width, [f"{base.Name}.Width"]),
        ("pad_thickness", thickness, [f"{base.Name}.Height"]),
        ("rib_height", rib_height, [f"{rib.Name}.Height"]),
    ]
    return [shape.Name], declarations


def build_shim(
    document,
    length,
    width,
    thickness,
    hole_diameter,
    pitch,
    callout_pitch=None,
    name="Shim",
):
    """A shim strip with two through holes on the long centreline, ``pitch`` apart.

    ``callout_pitch`` declares the pitch parameter at a DIFFERENT value from the one that positions
    the holes. The solid keeps ``pitch``; only the sheet's callout moves. That is the
    wrong-dimension-callout defect, and it is the one fault in this suite the geometry leg cannot
    see, because the geometry is correct.
    """
    strip = _box(document, f"{name}Strip", length, width, thickness)
    centre_y = width / 2.0
    first_x = (length - pitch) / 2.0

    pitch_gauge = _gauge(document, f"{name}PitchGauge", pitch, at=(first_x, centre_y, 0.0))
    hole_gauge = _gauge(document, f"{name}HoleGauge", hole_diameter)
    holes = []
    for index in range(2):
        hole = _cylinder(
            document,
            f"{name}Hole{index}",
            hole_gauge,
            thickness + 2.0 * _OVERSHOOT,
            at=(0.0, 0.0, -_OVERSHOOT),
        )
        offset = f" + {pitch_gauge.Name}.Length" if index else ""
        hole.setExpression("Placement.Base.x", f"{pitch_gauge.Name}.Placement.Base.x{offset}")
        hole.setExpression("Placement.Base.y", f"{pitch_gauge.Name}.Placement.Base.y")
        holes.append(hole)

    tool = _fuse(document, f"{name}Holes", holes[0], holes[1])
    shape = _cut(document, name, strip, tool)
    declarations = [
        ("shim_length", length, [f"{strip.Name}.Length"]),
        ("shim_width", width, [f"{strip.Name}.Width"]),
        ("shim_thickness", thickness, [f"{strip.Name}.Height"]),
        ("hole_diameter", hole_diameter, [f"{hole_gauge.Name}.Length"]),
        (
            "hole_pitch",
            pitch if callout_pitch is None else callout_pitch,
            [f"{pitch_gauge.Name}.Length"],
        ),
    ]
    return [shape.Name], declarations


def repin_shim_holes(document, pitch, name="Shim"):
    """Detach the shim's holes from the pitch gauge and pin them at the correct ``pitch``.

    Only the wrong-dimension-callout case calls this, and it is what makes that fault sheet-only.
    Declaring ``hole_pitch`` at 60 mm drives the gauge, and the gauge positions the holes — so
    without this the wrong number would move the part too and the geometry leg would catch it,
    which is precisely what the case asserts must not happen.
    """
    import FreeCAD as App

    strip = document.getObject(f"{name}Strip")
    centre_y = strip.Width.Value / 2.0
    first_x = (strip.Length.Value - pitch) / 2.0
    for index in range(2):
        hole = document.getObject(f"{name}Hole{index}")
        hole.setExpression("Placement.Base.x", None)
        hole.setExpression("Placement.Base.y", None)
        hole.Placement.Base = App.Vector(first_x + index * pitch, centre_y, -_OVERSHOOT)


def build_flanged_bushing(
    document,
    flange_diameter,
    flange_thickness,
    body_diameter,
    body_length,
    bore_diameter,
    with_flange=True,
    name="Bushing",
):
    """A flanged bushing bored right through: one logical hole with a stepped wall.

    ``with_flange: False`` is the missing-flange defect. The body keeps its stated 18 mm diameter
    and its stated 16 mm length, and the bore still runs the full length — so what the judge sees
    is a plain sleeve where the spec's drawing shows a flange, and nothing else differs.
    """
    body_gauge = _gauge(document, f"{name}BodyGauge", body_diameter)
    bore_gauge = _gauge(document, f"{name}BoreGauge", bore_diameter)
    body_z = flange_thickness if with_flange else 0.0
    body = _cylinder(document, f"{name}Body", body_gauge, body_length, at=(0.0, 0.0, body_z))

    if with_flange:
        flange_gauge = _gauge(document, f"{name}FlangeGauge", flange_diameter)
        flange = _cylinder(document, f"{name}Flange", flange_gauge, flange_thickness)
        stock = _fuse(document, f"{name}Stock", flange, body)
        total_length = flange_thickness + body_length
        flange_declarations = [
            ("flange_diameter", flange_diameter, [f"{flange_gauge.Name}.Length"]),
            ("flange_thickness", flange_thickness, [f"{flange.Name}.Height"]),
        ]
    else:
        # Without the flange the sleeve is one solid of the stated body length, starting at the
        # origin rather than floating 4 mm above nothing.
        stock = body
        total_length = body_length
        flange_declarations = []

    bore = _cylinder(
        document,
        f"{name}Bore",
        bore_gauge,
        total_length + 2.0 * _OVERSHOOT,
        at=(0.0, 0.0, -_OVERSHOOT),
    )
    shape = _cut(document, name, stock, bore)
    declarations = flange_declarations + [
        ("body_diameter", body_diameter, [f"{body_gauge.Name}.Length"]),
        ("body_length", body_length, [f"{body.Name}.Height"]),
        ("bore_diameter", bore_diameter, [f"{bore_gauge.Name}.Length"]),
    ]
    return [shape.Name], declarations


def build_washer(document, outside_diameter, bore_diameter, thickness, name="Washer"):
    """A flat washer: an annulus bored through its full thickness.

    Its spec states three diameters and a thickness, all rotationally symmetric, so the part is its
    own mirror image. That is what the symmetric-part control asserts: the mirror operation the
    mirrored-part defect uses is applied here and produces the SAME part, so a judge that flags
    every mirror fails this control.
    """
    disc_gauge = _gauge(document, f"{name}DiscGauge", outside_diameter)
    bore_gauge = _gauge(document, f"{name}BoreGauge", bore_diameter)
    disc = _cylinder(document, f"{name}Disc", disc_gauge, thickness)
    bore = _cylinder(
        document,
        f"{name}Bore",
        bore_gauge,
        thickness + 2.0 * _OVERSHOOT,
        at=(0.0, 0.0, -_OVERSHOOT),
    )
    shape = _cut(document, name, disc, bore)
    declarations = [
        ("washer_outside_diameter", outside_diameter, [f"{disc_gauge.Name}.Length"]),
        ("washer_thickness", thickness, [f"{disc.Name}.Height"]),
        ("washer_bore_diameter", bore_diameter, [f"{bore_gauge.Name}.Length"]),
    ]
    return [shape.Name], declarations


BUILDERS = {
    "flanged_bushing": build_flanged_bushing,
    "l_bracket": build_l_bracket,
    "ribbed_pad": build_ribbed_pad,
    "shim": build_shim,
    "washer": build_washer,
}


# ------------------------------------------------------------------------------------------
# The step executor the plans name.
# ------------------------------------------------------------------------------------------


def visual_step(
    registry, doc=None, builder=None, anchor=None, confirm=None, audit_sink=None, **params
):
    """The ``plan_visual_part`` tool: run a named builder through the production mutation bracket.

    Signature-compatible with the ``usecases.sketches`` / ``usecases.features`` tools the loop
    resolves, so the loop drives it by the same path and through the same ``run_mutation``
    protocol — the same arrangement ``planted_plans.shape_step`` uses, and for the same reason.

    The shape and its anchor datum are built in one bracket, then each declared parameter is bound
    through ``usecases.parameters.declare``. The declarations run as their own mutations because
    the façade is itself a mutating tool and a parameter can only bind to a property that already
    exists: the shape has to be committed before anything can drive it.
    """
    from freecad_buddy.usecases import parameters, transaction

    from planted_plans import ensure_anchor

    function = BUILDERS.get(builder)
    if function is None:
        raise KeyError(f"no visual part builder named {builder!r} (known: {sorted(BUILDERS)})")

    repin_pitch = params.pop("repin_pitch", None)
    declared: list = []
    rebound: list = []

    def op(target):
        # The anchor datum is created BEFORE the shape, so the part is the document's last
        # drawable object. ``techdraw._subject_object`` draws the last one, and an
        # ``App::Placement`` presents a degenerate single-face shape that is drawable by that
        # test — measured: picking it makes the hidden-line-removal pass return no path geometry
        # and the sheet build fails after 3000 settle attempts.
        anchored = ensure_anchor(target, anchor)
        names, declarations = function(target, **params)
        declared.append(declarations)
        return anchored + names

    def call(handle, document):
        result = transaction.run_mutation(
            document,
            handle,
            f"plan_visual_part {builder}",
            op,
            audit_sink=audit_sink,
            tool="plan_visual_part",
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

    for name, value, drives in declared[0] if declared else []:
        parameters.declare(
            registry, doc=doc, name=name, value=value, drives=drives, audit_sink=audit_sink
        )

    if repin_pitch is not None:

        def repin(_handle, document):
            repin_shim_holes(document, repin_pitch)
            document.recompute()
            return envelope

        registry.with_document(doc, repin)
    return envelope


def _plan(spec_id: str, steps: list, rationale: str) -> dict:
    """Wrap ``steps`` as an approved ``DesignPlan`` for ``spec_id``.

    ``approved: True`` stands in for the one human approval a real run gives. A fault case's plan
    is approved by construction: the suite measures what the visual judge sees in the part the loop
    built, which is a question about what happens *after* approval.
    """
    from planted_plans import ANCHOR_BY_SPEC

    anchor = ANCHOR_BY_SPEC.get(spec_id, "XY_Plane")
    for step in steps:
        step["args"].setdefault("anchor", anchor)
    return {
        "schema": "fcb.design-plan/1",
        "spec_id": spec_id,
        "spec_text": f"the {spec_id} spec",
        "steps": steps,
        "approved": True,
        "approved_by": "g3-visual-judge-suite",
        "rationale": rationale,
    }


def _part(builder: str, **params) -> dict:
    """One ``plan_visual_part`` step: build a parametric part from named parameters."""
    return {
        "tool": "plan_visual_part",
        "args": {"builder": builder, **params},
        "intent": builder,
    }


# ------------------------------------------------------------------------------------------
# The planted ops. Each returns the plan its case drives.
# ------------------------------------------------------------------------------------------

_BRACKET = dict(
    leg_length=BRACKET_LEG_L,
    width=BRACKET_WIDTH,
    thickness=BRACKET_T,
    height=BRACKET_HEIGHT,
    hole_diameter=BRACKET_HOLE_D,
    hole_inset=BRACKET_HOLE_INSET,
    hole_height=BRACKET_HOLE_HEIGHT,
)

_PAD = dict(
    length=PAD_L,
    width=PAD_W,
    thickness=PAD_T,
    rib_thickness=RIB_T,
    rib_height=RIB_H,
)

_SHIM = dict(length=SHIM_L, width=SHIM_W, thickness=SHIM_T, hole_diameter=SHIM_HOLE_D)

_BUSHING = dict(
    flange_diameter=BUSHING_FLANGE_D,
    flange_thickness=BUSHING_FLANGE_T,
    body_diameter=BUSHING_BODY_D,
    body_length=BUSHING_BODY_L,
    bore_diameter=BUSHING_BORE_D,
)


def visual_correct_part() -> dict:
    """The L-bracket the spec asks for, hole 12 mm from the edge the spec names."""
    return _plan(
        "g3-dev-002-l-bracket",
        [_part("l_bracket", **_BRACKET)],
        f"the bracket the spec states, hole {BRACKET_HOLE_INSET} mm from the stated edge",
    )


def visual_mirrored_part() -> dict:
    """The same bracket reflected in Y, so the hole sits against the opposite edge.

    Every declared assertion is invariant under the reflection — volume, bbox [60, 40, 50], 90
    degrees between the legs, one hole, and that hole's diameter — which is what the case's
    ``must_not_be_caught_by: geometry_assertions_pass`` requires. What changes is which edge the
    hole is near, and the spec names that edge, so this is a stated requirement violated where no
    declared assertion can reach it.
    """
    return _plan(
        "g3-dev-002-l-bracket",
        [_part("l_bracket", mirrored=True, **_BRACKET)],
        "the bracket built as its own mirror image; every dimension measures correct",
    )


def visual_cosmetic_render_difference() -> dict:
    """The ribbed pad the spec asks for; its render options differ, its geometry does not.

    The camera azimuth and the material tone are applied by the RENDER, not by the plan, so this op
    returns exactly the plan ``visual_feature_on_wrong_face`` corrupts. That is the point of the
    control: the two parts differ in the rib's host edge and in nothing else, and this one also
    differs from the reference IMAGES in ways that are not geometry at all.
    """
    return _plan(
        "g3-dev-015-ribbed-pad",
        [_part("ribbed_pad", rib_length=RIB_L, **_PAD)],
        "the pad the spec states; the camera and tone differ from the reference images",
    )


def visual_symmetric_part_either_hand() -> dict:
    """The flat washer, which is its own mirror image.

    Pairs with ``visual_mirrored_part``: the same reflection, and here it is not a defect, because
    the spec states only rotationally symmetric dimensions. A judge that flags every mirror fails
    this control.
    """
    return _plan(
        "g3-dev-018-flat-washer",
        [
            _part(
                "washer",
                outside_diameter=WASHER_OD,
                bore_diameter=WASHER_BORE_D,
                thickness=WASHER_T,
            )
        ],
        "a washer whose spec is symmetric, so the mirrored build IS the correct build",
    )


def visual_missing_flange() -> dict:
    """The bushing built without its 30 mm flange; the body and the bore are correct."""
    return _plan(
        "g3-dev-009-flanged-bushing",
        [_part("flanged_bushing", with_flange=False, **_BUSHING)],
        f"the {BUSHING_FLANGE_D} mm flange omitted; an {BUSHING_BODY_D} mm sleeve remains",
    )


def visual_feature_on_wrong_face() -> dict:
    """The rib turned onto the pad's short centreline; its own dimensions stay correct.

    The rib spans the 40 mm width rather than the 60 mm length, so the rib LENGTH follows the edge
    it stands on. Keeping the spec's 60 mm rib on a 40 mm edge would make it overhang the base,
    which is a second defect and would stop the case measuring the one it names.
    """
    return _plan(
        "g3-dev-015-ribbed-pad",
        [_part("ribbed_pad", rib_length=PAD_W, on_short_edge=True, **_PAD)],
        "the rib stands on the short centreline rather than the long one the spec states",
    )


def visual_wrong_proportions() -> dict:
    """The shim built 100 x 60 where the spec states 100 x 20."""
    return _plan(
        "g3-dev-005-rail-shim",
        [_part("shim", pitch=SHIM_PITCH, **{**_SHIM, "width": SHIM_W_WRONG})],
        f"strip width {SHIM_W_WRONG} substituted for {SHIM_W}; three times the stated width",
    )


def visual_wrong_dimension_callout() -> dict:
    """The correct shim, with a 60 mm callout on its 80 mm hole pitch.

    The only fault in this suite that lives in the DRAWING rather than the part. ``callout_pitch``
    declares ``hole_pitch`` at the wrong value and ``repin_pitch`` puts the holes back at the
    correct one, so every geometry assertion passes and only the sheet is wrong.
    """
    return _plan(
        "g3-dev-005-rail-shim",
        [
            _part(
                "shim",
                pitch=SHIM_PITCH,
                callout_pitch=SHIM_PITCH_CALLOUT_WRONG,
                repin_pitch=SHIM_PITCH,
                **_SHIM,
            )
        ],
        f"sheet callout {SHIM_PITCH_CALLOUT_WRONG} on a correct {SHIM_PITCH} mm pitch",
    )


REGISTRY = {
    "visual_correct_part": visual_correct_part,
    "visual_cosmetic_render_difference": visual_cosmetic_render_difference,
    "visual_feature_on_wrong_face": visual_feature_on_wrong_face,
    "visual_mirrored_part": visual_mirrored_part,
    "visual_missing_flange": visual_missing_flange,
    "visual_symmetric_part_either_hand": visual_symmetric_part_either_hand,
    "visual_wrong_dimension_callout": visual_wrong_dimension_callout,
    "visual_wrong_proportions": visual_wrong_proportions,
}


def resolve(name: str):
    """The plan builder ``name`` denotes.

    :raises KeyError: no op carries that name.
    """
    return REGISTRY[name]
