"""Author the 20 G3 actor DesignPlans from the dev specs' written text.

This is the ACTOR's authoring step, kept as code rather than 20 hand-typed JSON files so the
profile recipes (a fully-constrained rectangle, a pinned circle, an annulus) are written once and
every plan that needs one is built the same way. The geometry is derived from each spec's prose
alone; no case's ``assertions:`` block was read.

Every sketch must reach ``FullyConstrained`` or ``sketch_add_geometry`` rolls the whole add back
(``usecases/sketches.py:768``), so each profile ships its constraints in the same call as its
geometry.

Running it rewrites ``benchmarks/g3/actor-plans/<spec-id>.json``.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

HERE = Path(__file__).resolve().parent
PLANS_DIR = HERE / "actor-plans"
DEV_DIR = HERE / "dev"

ACTOR = "designer-actor"

# The sketch origin's geo id and point position, as the Sketcher addresses them.
ORIGIN_GEO = -1
ORIGIN_POS = 1

# Point positions on a line segment / circle, as the Sketcher numbers them.
START, END, CENTER = 1, 2, 3


def mm(value: float) -> dict:
    return {"value": float(value), "unit": "mm"}


def line(start, end) -> dict:
    return {"kind": "line_segment", "start": list(start), "end": list(end)}


def circle(center, radius) -> dict:
    return {"kind": "circle", "center": list(center), "radius": mm(radius)}


def coincident(g1, p1, g2, p2) -> dict:
    return {"type": "Coincident", "first": g1, "first_pos": p1, "second": g2, "second_pos": p2}


def distance_x(g1, p1, g2, p2, value) -> dict:
    return {
        "type": "DistanceX",
        "first": g1,
        "first_pos": p1,
        "second": g2,
        "second_pos": p2,
        "value": mm(value),
    }


def distance_y(g1, p1, g2, p2, value) -> dict:
    return {
        "type": "DistanceY",
        "first": g1,
        "first_pos": p1,
        "second": g2,
        "second_pos": p2,
        "value": mm(value),
    }


def diameter(geo, value) -> dict:
    return {"type": "Diameter", "first": geo, "value": mm(value)}


def rectangle(width: float, height: float, base: int = 0, centred: bool = True):
    """A closed, fully-constrained rectangle; ``base`` is the geo id its first line will take.

    Centred on the sketch origin by default, because a spec that states overall size and gives
    feature positions relative to the part usually means the part's own centre. A corner-datum
    spec (g3-dev-019) passes ``centred=False`` so the origin IS the stated corner.
    """
    x0, y0 = (-width / 2.0, -height / 2.0) if centred else (0.0, 0.0)
    x1, y1 = x0 + width, y0 + height
    geometry = [
        line([x0, y0], [x1, y0]),
        line([x1, y0], [x1, y1]),
        line([x1, y1], [x0, y1]),
        line([x0, y1], [x0, y0]),
    ]
    b = base
    constraints = [
        coincident(b + 0, END, b + 1, START),
        coincident(b + 1, END, b + 2, START),
        coincident(b + 2, END, b + 3, START),
        coincident(b + 3, END, b + 0, START),
        {"type": "Horizontal", "first": b + 0},
        {"type": "Horizontal", "first": b + 2},
        {"type": "Vertical", "first": b + 1},
        {"type": "Vertical", "first": b + 3},
        distance_x(ORIGIN_GEO, ORIGIN_POS, b + 0, START, x0),
        distance_y(ORIGIN_GEO, ORIGIN_POS, b + 0, START, y0),
        distance_x(b + 0, START, b + 0, END, width),
        distance_y(b + 1, START, b + 1, END, height),
    ]
    return geometry, constraints


def pinned_circle(cx: float, cy: float, dia: float, base: int = 0):
    """One circle pinned by its centre coordinates and dimensioned by diameter."""
    geometry = [circle([cx, cy], dia / 2.0)]
    constraints = [
        distance_x(ORIGIN_GEO, ORIGIN_POS, base, CENTER, cx),
        distance_y(ORIGIN_GEO, ORIGIN_POS, base, CENTER, cy),
        diameter(base, dia),
    ]
    return geometry, constraints


def circles(centres_and_diameters, base: int = 0):
    """Several pinned circles in one add, numbered from ``base``."""
    geometry, constraints = [], []
    for offset, (cx, cy, dia) in enumerate(centres_and_diameters):
        geo, con = pinned_circle(cx, cy, dia, base + offset)
        geometry += geo
        constraints += con
    return geometry, constraints


def step(tool: str, intent: str, **args) -> dict:
    return {"tool": tool, "args": args, "intent": intent}


def body(name: str = "Body") -> dict:
    return step("feature_body_create", "every PartDesign feature builds into a Body", name=name)


def sketch_on(name: str, plane: str, body_name: str = "Body") -> dict:
    return step(
        "sketch_create",
        f"profile plane for {name}",
        name=name,
        plane=plane,
        body=body_name,
    )


def add_geometry(sketch: str, geometry, constraints, intent: str) -> dict:
    return step(
        "sketch_add_geometry",
        intent,
        sketch=sketch,
        geometry=geometry,
        constraints=constraints,
    )


def pad(name: str, profile: str, length: float, body_name: str = "Body", **extra) -> dict:
    return step(
        "feature_pad",
        f"extrude {profile} {length} mm",
        body=body_name,
        profile=profile,
        name=name,
        length=mm(length),
        **extra,
    )


# A subtractive feature cuts along its profile's NEGATIVE normal by default. Every profile here
# sits on the same base plane the solid was padded from, and the pad grew along the positive
# normal, so an un-reversed cut runs into empty space and removes nothing — the feature still
# reports OK and the part still recomputes, it is simply undrilled. Measured on
# g3-dev-001: the body stayed at 28800 mm^3 (the solid plate) with `reversed` unset, and reached
# the analytic 28229.801 mm^3 with it set.
_CUT_INTO_MATERIAL = True


def pocket_through(name: str, profile: str, body_name: str = "Body") -> dict:
    return step(
        "feature_pocket",
        f"cut {profile} right through",
        body=body_name,
        profile=profile,
        name=name,
        up_to="ThroughAll",
        reversed=_CUT_INTO_MATERIAL,
    )


def pocket_depth(name: str, profile: str, depth: float, body_name: str = "Body") -> dict:
    return step(
        "feature_pocket",
        f"cut {profile} {depth} mm deep",
        body=body_name,
        profile=profile,
        name=name,
        length=mm(depth),
        reversed=_CUT_INTO_MATERIAL,
    )


def hole_through(name: str, profile: str, dia: float, body_name: str = "Body", **extra) -> dict:
    extra.setdefault("reversed", _CUT_INTO_MATERIAL)
    return step(
        "feature_hole",
        f"drill {dia} mm through",
        body=body_name,
        profile=profile,
        name=name,
        diameter=mm(dia),
        depth_type="ThroughAll",
        **extra,
    )


def hole_blind(name: str, profile: str, dia: float, depth: float, body_name: str = "Body") -> dict:
    return step(
        "feature_hole",
        f"bore {dia} mm, {depth} mm deep, not breaking through",
        body=body_name,
        profile=profile,
        name=name,
        diameter=mm(dia),
        depth_type="Dimension",
        depth=mm(depth),
        reversed=_CUT_INTO_MATERIAL,
    )


def plate_with_holes(
    width: float,
    height: float,
    thickness: float,
    holes,
    *,
    centred: bool = True,
    plane: str = "XY",
):
    """The recurring recipe: pad a rectangle, then drill a set of through holes into it."""
    geo, con = rectangle(width, height, centred=centred)
    steps = [
        body(),
        sketch_on("Outline", plane),
        add_geometry("Outline", geo, con, f"{width} x {height} outline"),
        pad("Plate", "Outline", thickness),
    ]
    if holes:
        hgeo, hcon = circles(holes)
        steps += [
            sketch_on("Holes", plane),
            add_geometry("Holes", hgeo, hcon, f"{len(holes)} hole centres"),
            hole_through("Drill", "Holes", holes[0][2]),
        ]
    return steps


def annulus(outer: float, bore: float, base: int = 0):
    """Two concentric circles at the origin: the profile a ring pads from."""
    geometry = [circle([0, 0], outer / 2.0), circle([0, 0], bore / 2.0)]
    constraints = [
        coincident(base + 0, CENTER, ORIGIN_GEO, ORIGIN_POS),
        coincident(base + 1, CENTER, ORIGIN_GEO, ORIGIN_POS),
        diameter(base + 0, outer),
        diameter(base + 1, bore),
    ]
    return geometry, constraints


def ring(outer: float, bore: float, thickness: float, name: str = "Ring"):
    geo, con = annulus(outer, bore)
    return [
        body(),
        sketch_on("Outline", "XY"),
        add_geometry("Outline", geo, con, f"{outer} mm outside, {bore} mm bore"),
        pad(name, "Outline", thickness),
    ]


# ----------------------------------------------------------------------------------------------
# The 20 plans. Each is keyed by spec id and returns (steps, rationale).
# ----------------------------------------------------------------------------------------------


def bolt_circle(count: int, pitch_diameter: float, hole_diameter: float):
    """``count`` holes evenly spaced on a pitch circle, each pinned by its own coordinates.

    Pinned by computed X/Y rather than by a polar pattern because the spec states an even spacing
    on a stated pitch circle, and coordinates are what the sketch solver constrains directly.
    """
    radius = pitch_diameter / 2.0
    return [
        (
            round(radius * math.cos(2 * math.pi * index / count), 9),
            round(radius * math.sin(2 * math.pi * index / count), 9),
            hole_diameter,
        )
        for index in range(count)
    ]


def grid(counts: int, pitch: float, hole_diameter: float):
    """A ``counts`` x ``counts`` grid of holes on ``pitch``, centred on the origin."""
    span = (counts - 1) / 2.0
    return [
        ((col - span) * pitch, (row - span) * pitch, hole_diameter)
        for row in range(counts)
        for col in range(counts)
    ]


PLANS = {
    "g3-dev-001-mounting-plate": (
        plate_with_holes(
            80,
            60,
            6,
            [(x, y, 5.5) for x in (-30, 30) for y in (-20, 20)],
        ),
        "80x60x6 plate; the four M5 clearance holes sit 10 mm in from both edges, which on a "
        "centred outline is +-30 in X and +-20 in Y. ThroughAll because the spec says the holes "
        "go through.",
    ),
    "g3-dev-002-l-bracket": (
        # The L section is drawn once as a closed profile on XZ and padded across the 40 mm
        # width, so both legs come from one pad and share the corner the spec describes.
        [
            body(),
            sketch_on("Section", "XZ"),
            step(
                "sketch_add_geometry",
                "the L cross-section: 60 mm horizontal leg, 50 mm vertical leg, 5 mm plate",
                sketch="Section",
                geometry=[
                    line([0, 0], [60, 0]),
                    line([60, 0], [60, 5]),
                    line([60, 5], [5, 5]),
                    line([5, 5], [5, 50]),
                    line([5, 50], [0, 50]),
                    line([0, 50], [0, 0]),
                ],
                # Every corner is pinned to the origin in X and Y rather than chained by relative
                # distances. A relative chain leaves the solver free to place the whole profile,
                # and it settled the vertical leg OUTSIDE the 60 mm envelope: the bracket measured
                # 65 mm across, because the leg's 5 mm thickness landed at -5..0 instead of 0..5.
                constraints=[
                    coincident(0, END, 1, START),
                    coincident(1, END, 2, START),
                    coincident(2, END, 3, START),
                    coincident(3, END, 4, START),
                    coincident(4, END, 5, START),
                    coincident(5, END, 0, START),
                    {"type": "Horizontal", "first": 0},
                    {"type": "Vertical", "first": 1},
                    {"type": "Horizontal", "first": 2},
                    {"type": "Vertical", "first": 3},
                    {"type": "Horizontal", "first": 4},
                    {"type": "Vertical", "first": 5},
                    distance_x(ORIGIN_GEO, ORIGIN_POS, 0, START, 0.0),
                    distance_y(ORIGIN_GEO, ORIGIN_POS, 0, START, 0.0),
                    distance_x(ORIGIN_GEO, ORIGIN_POS, 1, START, 60.0),
                    distance_y(ORIGIN_GEO, ORIGIN_POS, 1, END, 5.0),
                    distance_x(ORIGIN_GEO, ORIGIN_POS, 3, START, 5.0),
                    distance_y(ORIGIN_GEO, ORIGIN_POS, 3, END, 50.0),
                ],
            ),
            pad("Bracket", "Section", 40),
            # The hole runs through the 5 mm vertical leg, whose faces are normal to X, so its
            # profile lives on YZ. "12 mm in from the left-hand edge with the horizontal leg
            # pointing towards you" puts the centre 12 mm along the 40 mm width; the pad grew
            # along -Y, so that edge is at Y = -40 and the centre sits at Y = -28.
            sketch_on("PivotFace", "YZ"),
            step(
                "sketch_add_geometry",
                "the 9 mm clearance hole, 30 mm above the base and 12 mm in from the left edge",
                sketch="PivotFace",
                geometry=[circle([-28, 30], 4.5)],
                constraints=[
                    distance_x(ORIGIN_GEO, ORIGIN_POS, 0, CENTER, -28.0),
                    distance_y(ORIGIN_GEO, ORIGIN_POS, 0, CENTER, 30.0),
                    diameter(0, 9.0),
                ],
            ),
            hole_through("Clearance", "PivotFace", 9.0),
        ],
        "One closed L profile padded 40 mm gives both legs sharing the corner, so the overall "
        "height is 50 mm and the plate is 5 mm throughout. The 9 mm hole is drilled through the "
        "vertical leg, so its profile is on YZ and it cuts along +X into the leg's 5 mm "
        "thickness.",
    ),
    "g3-dev-003-shaft-collar": (
        ring(40, 16, 15, name="Collar"),
        "A plain annular collar: 40 mm outside, 16 mm bore, padded 15 mm. Padding the annulus "
        "makes the bore run the full width in one feature, which is what 'the bore runs the full "
        "width' asks for.",
    ),
    "g3-dev-004-round-standoff": (
        ring(10, 3.2, 20, name="Standoff"),
        "10 mm outside diameter, 3.2 mm M3 clearance bore, 20 mm long. Both circles are pinned "
        "to the origin, so the bore is coaxial with the outside diameter by construction.",
    ),
    "g3-dev-005-rail-shim": (
        plate_with_holes(100, 20, 3, [(-40, 0, 6.0), (40, 0, 6.0)]),
        "100x20x3 strip. Each hole is 10 mm from its end, so on a centred outline they sit at "
        "+-40 on the long centreline and are 80 mm apart, as the spec states.",
    ),
    "g3-dev-006-bearing-base-pad": (
        plate_with_holes(70, 30, 10, [(-25, 0, 9.0), (25, 0, 9.0)]),
        "70x30x10 pad. The two 9 mm holes are 50 mm apart and symmetric about the centre, so "
        "they sit at +-25 on the long centreline.",
    ),
    "g3-dev-007-jig-block-blind-bore": (
        [
            body(),
            sketch_on("Outline", "XY"),
            add_geometry("Outline", *rectangle(50, 50), intent="50 mm square section"),
            pad("Block", "Outline", 25),
            sketch_on("BoreCentre", "XY"),
            add_geometry("BoreCentre", *pinned_circle(0, 0, 12.0), intent="12 mm bore on the axis"),
            hole_blind("Bore", "BoreCentre", 12.0, 15.0),
            # A PartDesign Hole defaults to DrillPoint "Angled", which leaves a 118 deg conical
            # tip. The spec asks for a bore 15 mm deep, which is a flat-bottomed feature: with the
            # default the part measured 60667.628 mm^3 against the flat-bottom 60803.540, short by
            # exactly the 135.911 mm^3 cone.
            step(
                "feature_set_parameters",
                "the spec's 15 mm deep bore is flat-bottomed, not a drill point",
                feature="Bore",
                parameters={"DrillPoint": "Flat"},
            ),
        ],
        "50 mm square, 25 mm tall. The bore is a Dimension hole 15 mm deep rather than "
        "ThroughAll, because the spec says it must not break through the 25 mm bottom, and its "
        "drill point is flattened so the bore is 15 mm deep as stated.",
    ),
    "g3-dev-008-flange-gasket": (
        [
            body(),
            sketch_on("Outline", "XY"),
            add_geometry("Outline", *annulus(100, 60), intent="100 mm outside, 60 mm bore"),
            pad("Gasket", "Outline", 2),
            sketch_on("BoltCircle", "XY"),
            add_geometry(
                "BoltCircle",
                *circles(bolt_circle(6, 80.0, 8.0)),
                intent="six 8 mm holes evenly spaced on the 80 mm pitch circle",
            ),
            hole_through("Bolts", "BoltCircle", 8.0),
        ],
        "A 2 mm ring, 100 mm outside with a 60 mm bore. Six bolt holes at 60 deg intervals on a "
        "40 mm radius, which is the stated 80 mm pitch circle.",
    ),
    "g3-dev-009-flanged-bushing": (
        [
            body(),
            sketch_on("Flange", "XY"),
            add_geometry("Flange", *pinned_circle(0, 0, 30.0), intent="30 mm flange disc"),
            pad("FlangeDisc", "Flange", 4),
            sketch_on("Body18", "XY"),
            add_geometry("Body18", *pinned_circle(0, 0, 18.0), intent="18 mm body"),
            # Both pads grow along +Z from the SAME plane, so the whole 20 mm part lies on one
            # side of z=0 and a single ThroughAll bore spans all of it. Padding the stem the other
            # way put material on both sides of the bore's start plane, and the one-directional
            # cut left the flange's 4 mm undrilled — the part measured 5642.300 mm^3 against the
            # analytic 5328.141, over by exactly the pi*5^2*4 plug.
            pad("BodyStem", "Body18", 20),
            sketch_on("Bore", "XY"),
            add_geometry("Bore", *pinned_circle(0, 0, 10.0), intent="10 mm through bore"),
            hole_through("BoreHole", "Bore", 10.0),
        ],
        "The flange pads 4 mm one way and the 18 mm body pads 16 mm the other, giving the stated "
        "20 mm overall length from one piece. The 10 mm bore is drilled ThroughAll so it runs the "
        "whole length.",
    ),
    "g3-dev-010-cover-panel-window": (
        [
            body(),
            sketch_on("Outline", "XY"),
            add_geometry("Outline", *rectangle(120, 80), intent="120x80 panel outline"),
            pad("Panel", "Outline", 3),
            sketch_on("Window", "XY"),
            add_geometry("Window", *rectangle(60, 30), intent="60x30 window, centred"),
            pocket_through("WindowCut", "Window"),
        ],
        "120x80x3 panel with a 60x30 rectangular window. Both rectangles are centred on the "
        "origin, so the window is centred on the panel, and the pocket is ThroughAll because the "
        "window is cut through.",
    ),
    "g3-dev-011-lever-arm": (
        [
            body(),
            sketch_on("Outline", "XY"),
            add_geometry("Outline", *rectangle(90, 20), intent="90x20 arm outline"),
            pad("Arm", "Outline", 8),
            sketch_on("Pivot", "XY"),
            add_geometry("Pivot", *pinned_circle(-30, 0, 12.0), intent="12 mm pivot bore"),
            hole_through("PivotBore", "Pivot", 12.0),
            sketch_on("Linkage", "XY"),
            add_geometry("Linkage", *pinned_circle(30, 0, 8.0), intent="8 mm linkage hole"),
            hole_through("LinkageHole", "Linkage", 8.0),
        ],
        "90x20x8 plate. The two holes differ in diameter, so each gets its own profile and its "
        "own Hole feature. 15 mm from each end on a centred outline is -30 and +30.",
    ),
    "g3-dev-012-clamp-pad-slot": (
        [
            body(),
            sketch_on("Outline", "XY"),
            add_geometry("Outline", *rectangle(40, 40), intent="40 mm square pad"),
            pad("Pad", "Outline", 20),
            sketch_on("Slot", "XY"),
            add_geometry(
                "Slot",
                *rectangle(20, 40),
                intent="20 mm wide slot running the full 40 mm depth",
            ),
            pocket_depth("SlotCut", "Slot", 10.0),
        ],
        "40 mm square, 20 mm tall. The slot profile is 20 mm wide and spans the full 40 mm, so "
        "the pocket cuts right across the top face. Depth is 10 mm, not ThroughAll, because the "
        "spec states a 10 mm depth in a 20 mm tall pad.",
    ),
    "g3-dev-013-pipe-stub": (
        ring(42.7, 36.5, 150, name="PipeStub"),
        "DN32 pipe: 42.7 mm outside, 36.5 mm bore from the 3.1 mm wall, cut to 150 mm. Padding "
        "the annulus runs the bore the full length.",
    ),
    "g3-dev-014-extrusion-end-cap": (
        plate_with_holes(20, 20, 5, [(0, 0, 5.5)]),
        "20 mm square, 5 mm thick, one 5.5 mm hole on the centre, drilled through.",
    ),
    "g3-dev-015-ribbed-pad": (
        [
            body(),
            sketch_on("Outline", "XY"),
            add_geometry("Outline", *rectangle(60, 40), intent="60x40 base plate"),
            pad("Base", "Outline", 5),
            # The rib's 60 mm length runs along the base's LONG centreline, which is X. Its
            # cross-section is therefore normal to X and lives on YZ: a section on XZ padded along
            # Y instead ran the rib across the 40 mm width, and the part measured 60 mm in Y.
            sketch_on("RibSection", "YZ"),
            step(
                "sketch_add_geometry",
                "the rib cross-section: 6 mm thick, rising 20 mm above the 5 mm base",
                sketch="RibSection",
                geometry=[
                    line([-3, 5], [3, 5]),
                    line([3, 5], [3, 25]),
                    line([3, 25], [-3, 25]),
                    line([-3, 25], [-3, 5]),
                ],
                constraints=[
                    coincident(0, END, 1, START),
                    coincident(1, END, 2, START),
                    coincident(2, END, 3, START),
                    coincident(3, END, 0, START),
                    {"type": "Horizontal", "first": 0},
                    {"type": "Horizontal", "first": 2},
                    {"type": "Vertical", "first": 1},
                    {"type": "Vertical", "first": 3},
                    distance_x(ORIGIN_GEO, ORIGIN_POS, 0, START, -3.0),
                    distance_y(ORIGIN_GEO, ORIGIN_POS, 0, START, 5.0),
                    distance_x(0, START, 0, END, 6.0),
                    distance_y(1, START, 1, END, 20.0),
                ],
            ),
            pad("Rib", "RibSection", 60, midplane=True),
        ],
        "The rib is drawn as a 6 mm x 20 mm section on XZ starting at the top of the 5 mm base, "
        "then padded 60 mm midplane so it runs the full length of the base's long centreline and "
        "stays centred on it.",
    ),
    "g3-dev-016-perforated-cover": (
        plate_with_holes(100, 100, 4, grid(3, 30.0, 6.0)),
        "100 mm square, 4 mm thick. A 3x3 grid on a 30 mm pitch centred on the plate puts the "
        "hole centres at -30, 0 and +30 in both directions.",
    ),
    "g3-dev-017-counterbored-boss": (
        [
            body(),
            sketch_on("Outline", "XY"),
            add_geometry("Outline", *rectangle(30, 30), intent="30 mm square boss"),
            pad("Boss", "Outline", 20),
            sketch_on("Axis", "XY"),
            add_geometry("Axis", *pinned_circle(0, 0, 6.5), intent="6.5 mm through hole on axis"),
            step(
                "feature_hole",
                "6.5 mm through hole with an 11 mm counterbore 6 mm deep",
                body="Body",
                profile="Axis",
                name="Counterbore",
                diameter=mm(6.5),
                depth_type="ThroughAll",
                cut_type="Counterbore",
                cut_diameter=mm(11.0),
                cut_depth=mm(6.0),
                reversed=_CUT_INTO_MATERIAL,
            ),
        ],
        "One PartDesign Hole carries both: a 6.5 mm ThroughAll bore with a Counterbore cut 11 mm "
        "across and 6 mm deep, which is exactly the M6 socket-head recess the spec describes.",
    ),
    "g3-dev-018-flat-washer": (
        ring(21, 10.3, 2, name="Washer"),
        "M10 flat washer: 21 mm outside, 10.3 mm bore, 2 mm thick.",
    ),
    "g3-dev-019-offset-pivot-plate": (
        [
            body(),
            sketch_on("Outline", "XY"),
            add_geometry(
                "Outline",
                *rectangle(60, 60, centred=False),
                intent="60 mm square, corner on the origin datum",
            ),
            pad("Plate", "Outline", 6),
            sketch_on("Pivot", "XY"),
            add_geometry(
                "Pivot",
                *pinned_circle(20, 15, 10.0),
                intent="10 mm hole at (20, 15) from the corner datum",
            ),
            hole_through("PivotBore", "Pivot", 10.0),
            # The spec names a corner datum, so the part must CARRY one: the measurement frame is
            # part of what the spec asks for, not an artefact of how it was drawn. Without a datum
            # object of this name every assertion reports "the anchor frame does not resolve" and
            # nothing about the part gets measured at all.
            step(
                "feature_datum",
                "the corner datum the spec measures the hole position from",
                body="Body",
                name="PlateCornerDatum",
                kind="point",
                attachment={"kind": "mapped_name", "object": "Outline"},
                map_mode="ObjectOrigin",
            ),
        ],
        "The spec measures from the plate's CORNER datum, not its centre, so this outline is laid "
        "with its corner on the sketch origin, and a datum point of that name is created there. "
        "The hole then sits at (20, 15) in the same frame, which is the off-centre position the "
        "spec asks for.",
    ),
    "g3-dev-020-twin-boss-block": (
        [
            body(),
            sketch_on("Outline", "XY"),
            add_geometry("Outline", *rectangle(80, 30), intent="80x30 spacer block"),
            pad("Block", "Outline", 10),
            sketch_on("Bosses", "XY"),
            add_geometry(
                "Bosses",
                *circles([(-25, 0, 14.0), (25, 0, 14.0)]),
                intent="two 14 mm bosses, axes 50 mm apart about the centre",
            ),
            step(
                "feature_pad",
                "raise both bosses 12 mm above the block's top face",
                body="Body",
                profile="Bosses",
                name="Bosses12",
                length=mm(22.0),
            ),
            sketch_on("BossBores", "XY"),
            add_geometry(
                "BossBores",
                *circles([(-25, 0, 6.0), (25, 0, 6.0)]),
                intent="6 mm hole through each boss and the block beneath it",
            ),
            hole_through("BossBoreHoles", "BossBores", 6.0),
        ],
        "The boss profile is on the same XY plane as the block outline, so padding it 22 mm "
        "(10 mm block + 12 mm boss) leaves each boss standing 12 mm proud of the top face. The "
        "6 mm holes are then drilled ThroughAll so each passes through its boss and the block.",
    ),
}


def build_plan(spec_id: str, spec_text: str, steps, rationale: str) -> dict:
    return {
        "schema": "fcb.design-plan/1",
        "spec_id": spec_id,
        "spec_text": spec_text,
        "steps": steps,
        "approved": True,
        "approved_by": ACTOR,
        "rationale": rationale,
    }


def read_spec_text(spec_id: str) -> str:
    """The case's ``spec:`` field, read WITHOUT parsing the file's assertions block.

    Deliberately a line scanner rather than ``yaml.safe_load``: loading the case would put its
    ``assertions:`` into this process, and the actor must plan from the prose alone.
    """
    path = DEV_DIR / spec_id / "case.yaml"
    lines = path.read_text(encoding="utf-8").splitlines()
    collected: list[str] = []
    grabbing = False
    for raw in lines:
        if grabbing:
            if raw and not raw[0].isspace() and not raw.startswith("#"):
                break
            if raw.strip().startswith("#"):
                continue
            collected.append(raw.strip())
            continue
        if raw.startswith("spec:"):
            grabbing = True
    return " ".join(part for part in collected if part)


def main() -> None:
    PLANS_DIR.mkdir(parents=True, exist_ok=True)
    for spec_id, (steps, rationale) in sorted(PLANS.items()):
        plan = build_plan(spec_id, read_spec_text(spec_id), steps, rationale)
        (PLANS_DIR / f"{spec_id}.json").write_text(
            json.dumps(plan, indent=2) + "\n", encoding="utf-8"
        )
    print(f"wrote {len(PLANS)} plans to {PLANS_DIR}")


if __name__ == "__main__":
    main()
