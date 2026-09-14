"""In-FreeCAD tests for the §7.2 assertion primitives and the anchor frame (stdlib unittest).

Run via ``FreeCADCmd tests/run_tests.py``. Covers the six primitives story 4.2 adds
(``hole_diameter``, ``hole_position``, ``distance_between``, ``angle_between``, ``expect_bbox``,
``expect_extent``) and the anchor-frame resolver every frame-sensitive measurement transforms
into before comparing (DW-115).

**The rotated fixture is the load-bearing one.** An axis-aligned part measures the same in its
anchor frame as in global coordinates, so an axis-aligned test passes whether or not the
transform happens — which is exactly how the missing frame stayed invisible while 40 cases
declared one. Every frame assertion here therefore runs against a part rotated 30 degrees about
Z, whose global bounding box (71.96 x 64.64) differs from its in-frame one (60 x 40).

Fixtures are raw ``Part`` solids on ``Part::Feature`` objects, matching
``test_harness_assertions.py``: the grader reads only ``Shape``, so a PartDesign tree would add a
dependency the measurements do not have. Expected values are analytic — computed from the
fixture's own stated dimensions, never read off the grader (AD-13/AD-19).
"""

import math
import sys
import unittest
from pathlib import Path

import FreeCAD as App
import Part

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from benchmarks.harness import assertions  # noqa: E402

# The fixture plate every frame test measures: 60 x 40 x 10, turned 30 degrees about Z so the
# global box and the in-frame box cannot coincide.
_PLATE = (60.0, 40.0, 10.0)
_TURN_DEGREES = 30.0


class _ShapeFixture(unittest.TestCase):
    """A scratch document onto which a test drops one measured solid."""

    def setUp(self):
        self.document = App.newDocument("assertion_primitives")

    def tearDown(self):
        for name in list(App.listDocuments().keys()):
            App.closeDocument(name)

    def feature(self, shape, name="Solid"):
        """Put ``shape`` on the document as the object the grader will measure."""
        obj = self.document.addObject("Part::Feature", name)
        obj.Shape = shape
        self.document.recompute()
        return obj

    def grade(self, fn, expect, anchor_frame=None, **extra):
        """Run one grader check over the document and return the resulting ``Check``."""
        check = {"fn": fn, "expect": expect}
        check.update(extra)
        results = assertions.evaluate(self.document, [check], anchor_frame)
        self.assertEqual(len(results), 1)
        return results[0]

    def datum(self, name, position, degrees=0.0):
        """A datum plane the ``named_datum`` derivation can resolve against."""
        plane = self.document.addObject("PartDesign::Plane", name)
        plane.Placement = App.Placement(
            App.Vector(*position), App.Rotation(App.Vector(0, 0, 1), degrees)
        )
        self.document.recompute()
        return plane


def _turned(shape, degrees=_TURN_DEGREES):
    """``shape`` rotated about global Z, the placement an anchor frame has to undo."""
    turned = shape.copy()
    turned.Placement = App.Placement(
        App.Vector(0, 0, 0), App.Rotation(App.Vector(0, 0, 1), degrees)
    )
    return turned


class AnchorFrameResolverTest(_ShapeFixture):
    """The three derivations must each be total and deterministic, or refuse (§7.1)."""

    def test_a_named_datum_resolves_to_that_datums_placement(self):
        self.feature(Part.makeBox(*_PLATE))
        self.datum("PlateCornerDatum", (5.0, 6.0, 7.0), 30.0)

        frame = assertions.resolve_frame(
            self.document,
            assertions._graded_shape(self.document),
            {"kind": "named_datum", "ref": "PlateCornerDatum"},
        )

        self.assertEqual(frame.kind, "named_datum")
        for measured, expected in zip(frame.origin, (5.0, 6.0, 7.0)):
            self.assertAlmostEqual(measured, expected, places=9)
        # The datum is turned 30 deg about Z, so its own X axis is (cos30, sin30, 0).
        for measured, expected in zip(
            frame.basis[0], (math.cos(math.radians(30.0)), math.sin(math.radians(30.0)), 0.0)
        ):
            self.assertAlmostEqual(measured, expected, places=9)

    def test_a_named_datum_that_names_nothing_is_refused_rather_than_guessed(self):
        self.feature(Part.makeBox(*_PLATE))

        act = lambda: assertions.resolve_frame(  # noqa: E731
            self.document,
            assertions._graded_shape(self.document),
            {"kind": "named_datum", "ref": "NoSuchDatum"},
        )

        with self.assertRaises(assertions.UnresolvableFrame):
            act()

    def test_a_base_sketch_plane_resolves_the_origin_plane_it_names(self):
        # A Body's XY_Plane / XZ_Plane are real App::Plane objects carrying the placement the
        # profile was drawn on, so the derivation resolves them by name directly.
        self.document.addObject("PartDesign::Body", "Body")
        self.document.recompute()
        self.feature(Part.makeBox(*_PLATE))

        frame = assertions.resolve_frame(
            self.document,
            assertions._graded_shape(self.document),
            {"kind": "base_sketch_plane", "ref": "XZ_Plane"},
        )

        self.assertEqual(frame.kind, "base_sketch_plane")
        # XZ_Plane is the global XY plane rolled 90 deg about X, so its Z axis is global -Y.
        for measured, expected in zip(frame.basis[2], (0.0, -1.0, 0.0)):
            self.assertAlmostEqual(measured, expected, places=9)

    def test_an_unknown_frame_kind_is_refused_rather_than_read_as_global(self):
        self.feature(Part.makeBox(*_PLATE))

        act = lambda: assertions.resolve_frame(  # noqa: E731
            self.document,
            assertions._graded_shape(self.document),
            {"kind": "centre_of_mass", "ref": None},
        )

        with self.assertRaises(assertions.UnresolvableFrame):
            act()

    def test_no_declaration_measures_in_global_coordinates(self):
        # Every G2 case predates the frame and is axis-aligned; an absent declaration must keep
        # measuring exactly where those cases already measured.
        self.feature(Part.makeBox(*_PLATE))

        frame = assertions.resolve_frame(
            self.document, assertions._graded_shape(self.document), None
        )

        self.assertEqual(frame.origin, (0.0, 0.0, 0.0))
        self.assertEqual(frame.basis, ((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0)))


class LargestPlanarFaceTieBreakTest(_ShapeFixture):
    """The tie-break is mandatory: without it a symmetric part's frame flips between legs."""

    def test_the_largest_face_is_chosen_over_smaller_ones(self):
        # A 60 x 40 x 10 box: the two 60x40 faces (2400) beat the 60x10 (600) and 40x10 (400).
        self.feature(Part.makeBox(*_PLATE))

        frame = assertions.resolve_frame(
            self.document,
            assertions._graded_shape(self.document),
            {"kind": "largest_planar_face", "ref": None},
        )

        self.assertIn("area=2400", frame.witness)

    def test_two_equal_area_faces_resolve_the_lower_one_every_run(self):
        # A box's top and bottom faces are exactly equal in area, so area alone cannot order
        # them. The declared tie-break takes the lower centroid along global Z, which is the
        # z=0 face — and it must be the same face on every one of ten resolutions, not merely
        # on the first.
        self.feature(Part.makeBox(*_PLATE))
        shape = assertions._graded_shape(self.document)
        declaration = {"kind": "largest_planar_face", "ref": None}

        resolved = [
            assertions.resolve_frame(self.document, shape, declaration) for _ in range(10)
        ]

        witnesses = {frame.witness for frame in resolved}
        origins = {frame.origin for frame in resolved}
        self.assertEqual(len(witnesses), 1, f"the frame flipped between runs: {witnesses}")
        self.assertEqual(len(origins), 1, f"the origin moved between runs: {origins}")
        self.assertAlmostEqual(resolved[0].origin[2], 0.0, places=9)

    def test_the_chosen_face_is_recorded_in_the_result_detail(self):
        # A report a reader cannot trace back to a face cannot distinguish a frame that flipped
        # from a part that moved (§7.1: the resolution goes in the banner).
        self.feature(Part.makeBox(*_PLATE))

        result = self.grade(
            "expect_bbox",
            [60.0, 40.0, 10.0],
            anchor_frame={"kind": "largest_planar_face", "ref": None},
            tol={"abs": 0.05},
        )

        self.assertTrue(result["passed"], result["detail"])
        self.assertIn("largest_planar_face", result["detail"]["message"])
        self.assertIn("area=", result["detail"]["message"])


class ExpectBboxInFrameTest(_ShapeFixture):
    """``expect_bbox`` measures in the anchor frame, never the naive global box (§7.2)."""

    def test_a_rotated_plate_reports_its_in_frame_extents(self):
        # 60 x 40 turned 30 deg spans 60*cos30 + 40*sin30 = 71.96 in global X and
        # 60*sin30 + 40*cos30 = 64.64 in global Y. In its own frame it is still 60 x 40 x 10.
        self.feature(_turned(Part.makeBox(*_PLATE)))
        self.datum("BaseDatum", (0.0, 0.0, 0.0), _TURN_DEGREES)

        result = self.grade(
            "expect_bbox",
            [60.0, 40.0, 10.0],
            anchor_frame={"kind": "named_datum", "ref": "BaseDatum"},
            tol={"abs": 0.05},
        )

        self.assertTrue(result["passed"], result["detail"])
        for measured, expected in zip(sorted(result["measured"]), [10.0, 40.0, 60.0]):
            self.assertAlmostEqual(measured, expected, places=6)

    def test_the_same_rotated_plate_fails_when_measured_globally(self):
        # The falsifier for the test above: if the transform were skipped, the measurement would
        # be this one. A frame implementation that silently did nothing would make the previous
        # test fail and this one pass, so the pair pins the direction of the effect.
        self.feature(_turned(Part.makeBox(*_PLATE)))

        result = self.grade("expect_bbox", [60.0, 40.0, 10.0], tol={"abs": 0.05})

        self.assertFalse(result["passed"], result["detail"])
        span_x = _PLATE[0] * math.cos(math.radians(_TURN_DEGREES)) + _PLATE[1] * math.sin(
            math.radians(_TURN_DEGREES)
        )
        self.assertAlmostEqual(max(result["measured"]), span_x, places=6)

    def test_an_axis_aligned_plate_measures_the_same_in_frame_and_globally(self):
        self.feature(Part.makeBox(*_PLATE))
        self.datum("BaseDatum", (0.0, 0.0, 0.0), 0.0)

        in_frame = self.grade(
            "expect_bbox",
            [60.0, 40.0, 10.0],
            anchor_frame={"kind": "named_datum", "ref": "BaseDatum"},
            tol={"abs": 0.05},
        )
        globally = self.grade("expect_bbox", [60.0, 40.0, 10.0], tol={"abs": 0.05})

        self.assertTrue(in_frame["passed"], in_frame["detail"])
        self.assertTrue(globally["passed"], globally["detail"])

    def test_a_plate_of_the_wrong_size_fails_in_its_own_frame(self):
        # The frame must not rescue a genuinely wrong part: a 50 mm plate graded against 60 is
        # out of band whichever frame it is measured in.
        self.feature(_turned(Part.makeBox(50.0, 40.0, 10.0)))
        self.datum("BaseDatum", (0.0, 0.0, 0.0), _TURN_DEGREES)

        result = self.grade(
            "expect_bbox",
            [60.0, 40.0, 10.0],
            anchor_frame={"kind": "named_datum", "ref": "BaseDatum"},
            tol={"abs": 0.05},
        )

        self.assertFalse(result["passed"], result["detail"])


class HolePositionInFrameTest(_ShapeFixture):
    """``hole_position`` projects the axis onto the anchor plane in frame coordinates (§7.2)."""

    def rotated_pivot_plate(self):
        """The g3-dev-019 geometry: a 60 x 60 x 6 plate with a 10 mm bore at (20, 15).

        Built at the origin, then turned 30 degrees about Z. In global coordinates the bore's
        centre is nowhere near (20, 15); in the plate's own corner frame it is exactly there.
        """
        plate = Part.makeBox(60.0, 60.0, 6.0)
        bore = Part.makeCylinder(5.0, 6.0, App.Vector(20.0, 15.0, 0.0), App.Vector(0, 0, 1))
        return _turned(plate.cut(bore))

    def test_a_rotated_plates_hole_reports_its_frame_position(self):
        self.feature(self.rotated_pivot_plate())
        self.datum("PlateCornerDatum", (0.0, 0.0, 0.0), _TURN_DEGREES)

        result = self.grade(
            "hole_position",
            [20.0, 15.0],
            anchor_frame={"kind": "named_datum", "ref": "PlateCornerDatum"},
            tol={"abs": 0.05},
        )

        self.assertTrue(result["passed"], result["detail"])
        self.assertAlmostEqual(result["measured"][0], 20.0, places=6)
        self.assertAlmostEqual(result["measured"][1], 15.0, places=6)

    def test_the_same_hole_fails_when_measured_globally(self):
        # The falsifier: (20, 15) turned 30 deg about Z is (9.82, 22.99), which is 14.4 mm from
        # where the spec says the hole is. Measured globally the check must fail.
        self.feature(self.rotated_pivot_plate())

        result = self.grade("hole_position", [20.0, 15.0], tol={"abs": 0.05})

        self.assertFalse(result["passed"], result["detail"])
        angle = math.radians(_TURN_DEGREES)
        self.assertAlmostEqual(
            result["measured"][0], 20.0 * math.cos(angle) - 15.0 * math.sin(angle), places=6
        )

    def test_a_datum_at_the_plate_centre_shifts_the_reported_position(self):
        # The frame's origin is load-bearing, not only its rotation: read from the plate's centre
        # the same bore sits at (20-30, 15-30) = (-10, -15).
        self.feature(self.rotated_pivot_plate())
        centre = App.Rotation(App.Vector(0, 0, 1), _TURN_DEGREES).multVec(
            App.Vector(30.0, 30.0, 0.0)
        )
        self.datum("PlateCentreDatum", (centre.x, centre.y, centre.z), _TURN_DEGREES)

        result = self.grade(
            "hole_position",
            [-10.0, -15.0],
            anchor_frame={"kind": "named_datum", "ref": "PlateCentreDatum"},
            tol={"abs": 0.05},
        )

        self.assertTrue(result["passed"], result["detail"])

    def test_a_hole_at_the_wrong_position_fails_in_its_own_frame(self):
        plate = Part.makeBox(60.0, 60.0, 6.0)
        bore = Part.makeCylinder(5.0, 6.0, App.Vector(25.0, 15.0, 0.0), App.Vector(0, 0, 1))
        self.feature(_turned(plate.cut(bore)))
        self.datum("PlateCornerDatum", (0.0, 0.0, 0.0), _TURN_DEGREES)

        result = self.grade(
            "hole_position",
            [20.0, 15.0],
            anchor_frame={"kind": "named_datum", "ref": "PlateCornerDatum"},
            tol={"abs": 0.05},
        )

        self.assertFalse(result["passed"], result["detail"])


class ExpectExtentInFrameTest(_ShapeFixture):
    """``expect_extent`` spans a *frame* direction, not a global one (§7.2)."""

    def test_a_tilted_bar_measures_its_length_along_the_frame_axis(self):
        # A 10 x 10 x 150 bar laid over 90 deg about Y: its 150 mm length now runs along global
        # X, and the frame's Z with it. An extent along frame Z must still read 150.
        bar = Part.makeBox(10.0, 10.0, 150.0)
        bar.Placement = App.Placement(App.Vector(0, 0, 0), App.Rotation(App.Vector(0, 1, 0), 90.0))
        self.feature(bar)
        plane = self.document.addObject("PartDesign::Plane", "BarBaseDatum")
        plane.Placement = App.Placement(
            App.Vector(0, 0, 0), App.Rotation(App.Vector(0, 1, 0), 90.0)
        )
        self.document.recompute()

        result = self.grade(
            "expect_extent",
            150.0,
            anchor_frame={"kind": "named_datum", "ref": "BarBaseDatum"},
            direction=[0, 0, 1],
            tol={"abs": 0.05},
        )

        self.assertTrue(result["passed"], result["detail"])
        self.assertAlmostEqual(result["measured"], 150.0, places=6)

    def test_the_same_bar_measures_ten_along_global_z(self):
        # The falsifier: global Z now crosses the bar's 10 mm side. Skipping the frame transform
        # would report 10 where the spec says 150.
        bar = Part.makeBox(10.0, 10.0, 150.0)
        bar.Placement = App.Placement(App.Vector(0, 0, 0), App.Rotation(App.Vector(0, 1, 0), 90.0))
        self.feature(bar)

        result = self.grade("expect_extent", 150.0, direction=[0, 0, 1], tol={"abs": 0.05})

        self.assertFalse(result["passed"], result["detail"])
        self.assertAlmostEqual(result["measured"], 10.0, places=6)

    def test_a_degenerate_direction_is_refused(self):
        self.feature(Part.makeBox(*_PLATE))

        result = self.grade("expect_extent", 60.0, direction=[0, 0, 0])

        self.assertFalse(result["passed"], result["detail"])
        self.assertEqual(result["detail"].get("code"), assertions._INVALID_INPUT)


class HoleDiameterTest(_ShapeFixture):
    """``hole_diameter`` is ``2 * Part.Cylinder.Radius`` (§7.2)."""

    def test_a_six_millimetre_bore_measures_six(self):
        plate = Part.makeBox(40.0, 40.0, 10.0)
        bore = Part.makeCylinder(3.0, 10.0, App.Vector(20, 20, 0), App.Vector(0, 0, 1))
        self.feature(plate.cut(bore))

        result = self.grade("hole_diameter", 6.0, tol={"abs": 0.05})

        self.assertTrue(result["passed"], result["detail"])
        self.assertAlmostEqual(result["measured"][0], 6.0, places=6)

    def test_a_bore_half_a_millimetre_oversize_fails(self):
        # The planted "wrong diameter" fault: 6.5 against a declared 6.0 at +/-0.05.
        plate = Part.makeBox(40.0, 40.0, 10.0)
        bore = Part.makeCylinder(3.25, 10.0, App.Vector(20, 20, 0), App.Vector(0, 0, 1))
        self.feature(plate.cut(bore))

        result = self.grade("hole_diameter", 6.0, tol={"abs": 0.05})

        self.assertFalse(result["passed"], result["detail"])

    def test_every_hole_must_match_not_merely_the_closest_one(self):
        # A part that drilled one bore right and one wrong must fail: grading only the nearest
        # measurement to the declared value would pass it.
        plate = Part.makeBox(60.0, 40.0, 10.0)
        good = Part.makeCylinder(3.0, 10.0, App.Vector(15, 20, 0), App.Vector(0, 0, 1))
        bad = Part.makeCylinder(4.0, 10.0, App.Vector(45, 20, 0), App.Vector(0, 0, 1))
        self.feature(plate.cut(good).cut(bad))

        result = self.grade("hole_diameter", 6.0, tol={"abs": 0.05})

        self.assertFalse(result["passed"], result["detail"])
        self.assertEqual(len(result["measured"]), 2)

    def test_a_shape_with_no_hole_fails_naming_the_miss(self):
        self.feature(Part.makeBox(40.0, 40.0, 10.0))

        result = self.grade("hole_diameter", 6.0, tol={"abs": 0.05})

        self.assertFalse(result["passed"], result["detail"])
        self.assertIn("no logical hole", result["detail"]["message"])

    def test_a_rotated_plates_bore_measures_the_same_diameter(self):
        # A diameter is frame-invariant — a rigid transform cannot change it — so the rotated
        # fixture must measure exactly what the unrotated one does.
        plate = Part.makeBox(40.0, 40.0, 10.0)
        bore = Part.makeCylinder(3.0, 10.0, App.Vector(20, 20, 0), App.Vector(0, 0, 1))
        self.feature(_turned(plate.cut(bore)))

        result = self.grade("hole_diameter", 6.0, tol={"abs": 0.05})

        self.assertTrue(result["passed"], result["detail"])


class DistanceBetweenTest(_ShapeFixture):
    """``distance_between`` grades a declared distance against the ones the part presents."""

    def test_two_parallel_faces_forty_apart_measure_forty(self):
        self.feature(Part.makeBox(40.0, 25.0, 10.0))

        result = self.grade("distance_between", 40.0, tol={"abs": 0.05})

        self.assertTrue(result["passed"], result["detail"])
        self.assertAlmostEqual(result["measured"], 40.0, places=6)

    def test_two_boss_axes_fifty_apart_measure_fifty(self):
        # The g3-dev-020 reading: the declared 50 mm is an axis spacing, which no pair of planar
        # faces on that part carries. A face-only implementation would fail a correct part.
        block = Part.makeBox(80.0, 30.0, 10.0)
        left = Part.makeCylinder(3.0, 10.0, App.Vector(15, 15, 0), App.Vector(0, 0, 1))
        right = Part.makeCylinder(3.0, 10.0, App.Vector(65, 15, 0), App.Vector(0, 0, 1))
        self.feature(block.cut(left).cut(right))

        result = self.grade("distance_between", 50.0, tol={"abs": 0.05})

        self.assertTrue(result["passed"], result["detail"])
        self.assertAlmostEqual(result["measured"], 50.0, places=6)

    def test_a_distance_the_part_does_not_carry_fails_and_names_what_it_has(self):
        self.feature(Part.makeBox(40.0, 25.0, 10.0))

        result = self.grade("distance_between", 37.0, tol={"abs": 0.05})

        self.assertFalse(result["passed"], result["detail"])
        self.assertIn("measured distances", result["detail"]["message"])

    def test_a_rotated_block_carries_the_same_distances(self):
        # Distance is frame-invariant, so the rotated fixture must measure identically.
        self.feature(_turned(Part.makeBox(40.0, 25.0, 10.0)))

        result = self.grade("distance_between", 40.0, tol={"abs": 0.05})

        self.assertTrue(result["passed"], result["detail"])


class AngleBetweenTest(_ShapeFixture):
    """``angle_between`` grades face normals, with 90 and 0 degrees as its named cases (§7.2)."""

    def l_bracket(self):
        """The g3-dev-002 geometry: a 60 x 40 x 5 leg with a 5 x 40 x 50 leg on its corner."""
        horizontal = Part.makeBox(60.0, 40.0, 5.0)
        vertical = Part.makeBox(5.0, 40.0, 50.0)
        return horizontal.fuse(vertical).removeSplitter()

    def test_two_perpendicular_legs_measure_ninety_degrees(self):
        self.feature(self.l_bracket())

        result = self.grade("angle_between", 90.0, tol={"abs": 0.1})

        self.assertTrue(result["passed"], result["detail"])
        self.assertAlmostEqual(result["measured"], 90.0, places=4)

    def test_parallel_faces_measure_zero_degrees(self):
        self.feature(Part.makeBox(*_PLATE))

        result = self.grade("angle_between", 0.0, tol={"abs": 0.1})

        self.assertTrue(result["passed"], result["detail"])

    def test_an_angle_the_part_does_not_present_fails(self):
        # A plain box presents 0 and 90 degrees only; 45 must not be found in it.
        self.feature(Part.makeBox(*_PLATE))

        result = self.grade("angle_between", 45.0, tol={"abs": 0.1})

        self.assertFalse(result["passed"], result["detail"])

    def test_a_rotated_bracket_still_measures_ninety(self):
        # An angle between two faces of one solid is frame-invariant: rotating the whole part
        # turns both normals together.
        self.feature(_turned(self.l_bracket()))

        result = self.grade("angle_between", 90.0, tol={"abs": 0.1})

        self.assertTrue(result["passed"], result["detail"])

    def test_a_shape_with_one_planar_face_cannot_carry_an_angle(self):
        self.feature(Part.makeSphere(10.0))

        result = self.grade("angle_between", 90.0, tol={"abs": 0.1})

        self.assertFalse(result["passed"], result["detail"])
        self.assertIn("an angle needs 2", result["detail"]["message"])


class ToleranceFloorTest(_ShapeFixture):
    """No assertion may be tighter than the measured shape's own ``getTolerance`` (§8)."""

    def test_a_tolerance_under_the_kernel_floor_is_refused_as_invalid(self):
        # An OCCT solid reports 1e-7; a 1e-12 band is below the precision the B-rep itself holds,
        # so it would pass or fail on rounding rather than on the part.
        self.feature(Part.makeBox(*_PLATE))
        floor = assertions._graded_shape(self.document).getTolerance(1)

        result = self.grade("expect_bbox", [60.0, 40.0, 10.0], tol={"abs": 1e-12})

        self.assertFalse(result["passed"], result["detail"])
        self.assertEqual(result["detail"].get("code"), assertions._INVALID_INPUT)
        self.assertIn(str(floor), result["detail"]["message"])

    def test_a_sub_floor_tolerance_is_refused_rather_than_passed(self):
        # The distinction that matters: the part is correct, so a naive implementation would
        # report a PASS at an impossible tolerance. It must read INVALID_INPUT instead.
        self.feature(Part.makeBox(*_PLATE))

        result = self.grade("expect_extent", 10.0, direction=[0, 0, 1], tol={"abs": 1e-15})

        self.assertFalse(result["passed"], result["detail"])
        self.assertEqual(result["detail"].get("code"), assertions._INVALID_INPUT)

    def test_a_tolerance_above_the_floor_is_honoured(self):
        self.feature(Part.makeBox(*_PLATE))

        result = self.grade("expect_bbox", [60.0, 40.0, 10.0], tol={"abs": 0.05})

        self.assertTrue(result["passed"], result["detail"])


class VocabularyTest(_ShapeFixture):
    """The vocabulary is closed: eleven §7.2 names plus the three declared G2 extensions."""

    def test_all_eleven_closed_primitives_are_supported(self):
        vocabulary = {
            "is_valid_solid",
            "count_cylindrical_holes",
            "hole_diameter",
            "hole_position",
            "hole_spacing",
            "hole_through",
            "distance_between",
            "angle_between",
            "expect_bbox",
            "expect_extent",
            "expect_volume",
        }

        supported = assertions.SUPPORTED_FNS

        self.assertEqual(vocabulary - supported, set())

    def test_no_name_outside_the_vocabulary_and_the_declared_extensions_exists(self):
        # A fourteenth name would be a silent fork of a closed vocabulary (AD-13).
        declared_extensions = {
            "expect_solid_count",
            "expect_sketch_fully_constrained",
            "expect_sketch_geometry_count",
        }
        vocabulary = {
            "is_valid_solid",
            "count_cylindrical_holes",
            "hole_diameter",
            "hole_position",
            "hole_spacing",
            "hole_through",
            "distance_between",
            "angle_between",
            "expect_bbox",
            "expect_extent",
            "expect_volume",
        }

        supported = assertions.SUPPORTED_FNS

        self.assertEqual(supported - vocabulary - declared_extensions, set())


class UnresolvableFrameIsReportedTest(_ShapeFixture):
    """A frame that does not resolve fails every check by name, never measures in another."""

    def test_every_check_is_refused_when_the_frame_names_a_missing_datum(self):
        self.feature(Part.makeBox(*_PLATE))

        results = assertions.evaluate(
            self.document,
            [
                {"fn": "expect_bbox", "expect": [60.0, 40.0, 10.0]},
                {"fn": "expect_volume", "expect": 24000.0},
            ],
            {"kind": "named_datum", "ref": "AbsentDatum"},
        )

        self.assertEqual(len(results), 2)
        for result in results:
            self.assertFalse(result["passed"], result["detail"])
            self.assertEqual(result["detail"].get("code"), assertions._INVALID_INPUT)
            self.assertIn("anchor_frame does not resolve", result["detail"]["message"])


if __name__ == "__main__":
    unittest.main()
