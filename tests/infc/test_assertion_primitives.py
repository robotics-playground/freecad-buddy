"""In-FreeCAD tests for the §7.2 assertion primitives reached through ``verify_shape``.

Run via ``FreeCADCmd tests/run_tests.py``. Every expected value is derived by hand from the
fixture's own construction (``verification-design.md`` §7, ``benchmarks/g3/README.md``
§Assertion vocabulary), never read off the implementation under test.

Fixtures are raw ``Part`` solids on ``Part::Feature`` objects, except where a frame needs a
PartDesign Body: the origin planes, a coordinate-system datum, a body moved off the origin, and
the element map that names faces.
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

from benchmarks.harness import assertions as harness  # noqa: E402
from freecad_buddy.adapters.rpc_dispatch import MethodRegistry, RpcMethod  # noqa: E402
from freecad_buddy.usecases import verify  # noqa: E402
from freecad_buddy.usecases.assertions import INVALID_INPUT_CODE  # noqa: E402
from freecad_buddy.usecases.documents import DocumentRegistry, ValidationError  # noqa: E402

V = App.Vector
UP = V(0, 0, 1)
XY_PLANE = {"kind": "base_sketch_plane", "ref": "XY_Plane"}
FACE_FRAME = {"kind": "largest_planar_face", "ref": None}


def _bore(radius, height, x=0.0, y=0.0, z=0.0, direction=UP):
    return Part.makeCylinder(radius, height, V(x, y, z), direction)


def _plate(length, width, thickness, holes=(), radius=2.75):
    """A plate centred on the origin in X and Y, z=0..thickness, with through holes at ``holes``."""
    plate = Part.makeBox(length, width, thickness, V(-length / 2, -width / 2, 0))
    for x, y in holes:
        plate = plate.cut(_bore(radius, thickness, x, y))
    return plate


def _jig_block():
    """A 50 x 50 x 25 block, z=0..25, with a 12 mm bore 15 mm deep into the centre of its top."""
    return Part.makeBox(50, 50, 25).cut(_bore(6.0, 15.0, 25, 25, 10))


class _PartFixture(unittest.TestCase):
    def setUp(self):
        self.registry = DocumentRegistry()
        self.handle = self.registry.document_create("assertion_primitives")["structured_content"][
            "doc"
        ]
        _, self.document = self.registry.with_document(self.handle, lambda h, d: (h, d))

    def tearDown(self):
        for name in list(App.listDocuments().keys()):
            App.closeDocument(name)

    def part(self, shape, name="Part"):
        obj = self.document.addObject("Part::Feature", name)
        obj.Shape = shape
        self.document.recompute()
        return obj

    def measure(self, checks, anchor_frame=None, target="Part"):
        return verify.verify_shape(
            self.registry, doc=self.handle, object=target, checks=checks, anchor_frame=anchor_frame
        )["structured_content"]

    def check(self, fn, expect, anchor_frame=None, target="Part", **parameters):
        return self.measure([{"fn": fn, "expect": expect, **parameters}], anchor_frame, target)[
            "checks"
        ][0]

    def body(self):
        body = self.document.addObject("PartDesign::Body", "Body")
        self.document.recompute()
        return body

    def drilled_body(self):
        """An 80 x 60 x 6 box in a Body, corner on the origin, with a 5.5 mm hole at (20, 15)."""
        body = self.body()
        box = body.newObject("PartDesign::AdditiveBox", "Box")
        box.Length, box.Width, box.Height = 80, 60, 6
        hole = body.newObject("PartDesign::SubtractiveCylinder", "Hole")
        hole.Radius, hole.Height = 2.75, 6
        hole.Placement = App.Placement(V(20, 15, 0), App.Rotation())
        self.document.recompute()
        return body


class IsValidSolidTest(_PartFixture):
    def test_should_pass_when_the_shape_is_a_valid_solid(self):
        # Arrange
        self.part(Part.makeBox(10, 10, 10))

        # Act
        result = self.check("is_valid_solid", True)

        # Assert
        self.assertTrue(result["passed"], result["detail"])

    def test_should_fail_when_the_shape_is_a_shell_with_no_solid(self):
        # Arrange
        self.part(Part.makeBox(10, 10, 10).Shells[0])

        # Act
        result = self.check("is_valid_solid", True)

        # Assert
        self.assertFalse(result["passed"])
        self.assertIs(result["measured"], False)


class CountCylindricalHolesTest(_PartFixture):
    def test_should_pass_when_the_plate_carries_the_declared_holes(self):
        # Arrange
        self.part(_plate(80, 60, 6, [(-30, -20), (30, -20), (-30, 20), (30, 20)]))

        # Act
        result = self.check("count_cylindrical_holes", 4)

        # Assert
        self.assertTrue(result["passed"], result["detail"])
        self.assertEqual(result["measured"], 4)

    def test_should_fail_when_a_hole_is_missing(self):
        # Arrange
        self.part(_plate(80, 60, 6, [(-30, -20), (30, -20), (-30, 20)]))

        # Act
        result = self.check("count_cylindrical_holes", 4)

        # Assert
        self.assertFalse(result["passed"])
        self.assertEqual(result["measured"], 3)


class HoleDiameterTest(_PartFixture):
    def test_should_pass_when_the_bore_has_the_declared_diameter(self):
        # Arrange
        self.part(_plate(40, 40, 6, [(0, 0)], radius=2.75))

        # Act
        result = self.check("hole_diameter", 5.5, tol={"abs": 0.05})

        # Assert
        self.assertTrue(result["passed"], result["detail"])
        self.assertAlmostEqual(result["measured"], 5.5, places=6)

    def test_should_fail_when_the_bore_is_drilled_to_another_diameter(self):
        # Arrange
        self.part(_plate(40, 40, 6, [(0, 0)], radius=3.0))

        # Act
        result = self.check("hole_diameter", 5.5, tol={"abs": 0.05})

        # Assert
        self.assertFalse(result["passed"])
        self.assertAlmostEqual(result["measured"], 6.0, places=6)

    def test_should_report_the_through_bore_when_the_hole_is_counterbored(self):
        # Arrange: a 6.5 mm through hole under an 11 mm counterbore 6 mm deep (g3-dev-017).
        boss = _plate(30, 30, 20, [(0, 0)], radius=3.25).cut(_bore(5.5, 6.0, 0, 0, 14))
        self.part(boss)

        # Act
        content = self.measure(
            [
                {"fn": "count_cylindrical_holes", "expect": 1},
                {"fn": "hole_diameter", "expect": 6.5, "select": {"axis": [0, 0, 1]}},
                {"fn": "hole_position", "expect": [0, 0], "select": {"diameter": 11.0}},
            ],
            FACE_FRAME,
        )

        # Assert
        self.assertTrue(all(c["passed"] for c in content["checks"]), content["checks"])


class HolePositionTest(_PartFixture):
    def test_should_pass_with_the_axis_at_the_frame_origin_when_the_bore_sits_there(self):
        # Arrange
        self.part(_plate(40, 40, 6, [(0, 0)], radius=6.0))

        # Act
        result = self.check("hole_position", [0.0, 0.0], select={"diameter": 12})

        # Assert
        self.assertTrue(result["passed"], result["detail"])
        self.assertAlmostEqual(result["measured"][0], 0.0, places=6)
        self.assertAlmostEqual(result["measured"][1], 0.0, places=6)

    def test_should_fail_when_the_bore_is_off_the_declared_position(self):
        # Arrange
        self.part(_plate(40, 40, 6, [(5, 0)], radius=6.0))

        # Act
        result = self.check("hole_position", [0.0, 0.0], select={"diameter": 12})

        # Assert
        self.assertFalse(result["passed"])
        self.assertAlmostEqual(result["measured"][0], 5.0, places=6)


class HoleSpacingTest(_PartFixture):
    def test_should_pass_when_the_holes_sit_at_the_declared_pitch(self):
        # Arrange
        self.part(_plate(80, 20, 3, [(-20, 0), (20, 0)]))

        # Act
        result = self.check("hole_spacing", 40.0, tol={"abs": 0.05})

        # Assert
        self.assertTrue(result["passed"], result["detail"])

    def test_should_fail_when_the_pitch_is_off_by_one_millimetre(self):
        # Arrange
        self.part(_plate(80, 20, 3, [(-20, 0), (21, 0)]))

        # Act
        result = self.check("hole_spacing", 40.0, tol={"abs": 0.05})

        # Assert
        self.assertFalse(result["passed"])

    def test_should_measure_each_bolt_against_the_bore_when_two_selectors_are_given(self):
        # Arrange: g3-dev-008 — six 8 mm bolt holes on an 80 mm pitch circle round a 60 mm bore.
        gasket = _bore(50.0, 2.0).cut(_bore(30.0, 2.0))
        for index in range(6):
            angle = math.radians(60 * index)
            gasket = gasket.cut(_bore(4.0, 2.0, 40 * math.cos(angle), 40 * math.sin(angle)))
        self.part(gasket)

        # Act
        result = self.check(
            "hole_spacing",
            40.0,
            select_a={"hole": {"diameter": 60.0}},
            select_b={"hole": {"diameter": 8.0}},
        )

        # Assert
        self.assertTrue(result["passed"], result["detail"])
        self.assertEqual(len(result["measured"]), 6)


class HoleThroughTest(_PartFixture):
    def test_should_pass_when_the_bore_exits_both_faces(self):
        # Arrange
        self.part(_plate(40, 40, 10, [(0, 0)], radius=3.0))

        # Act
        result = self.check("hole_through", True)

        # Assert
        self.assertTrue(result["passed"], result["detail"])

    def test_should_fail_when_the_bore_is_blind(self):
        # Arrange
        self.part(_jig_block())

        # Act
        result = self.check("hole_through", True)

        # Assert
        self.assertFalse(result["passed"])
        self.assertIs(result["measured"], False)


class DistanceBetweenTest(_PartFixture):
    def test_should_pass_when_every_hole_wall_sits_the_declared_distance_from_the_edge(self):
        # Arrange: g3-dev-001 — 5.5 mm holes centred 10 mm from each edge leave 7.25 mm.
        self.part(_plate(80, 60, 6, [(-30, -20), (30, -20), (-30, 20), (30, 20)]))

        # Act
        result = self.check(
            "distance_between",
            7.25,
            select_a={"hole": {"diameter": 5.5}},
            select_b={"face": {"normal": [-1, 0, 0]}},
        )

        # Assert
        self.assertTrue(result["passed"], result["detail"])
        self.assertAlmostEqual(result["measured"], 7.25, places=6)

    def test_should_fail_when_the_hole_rectangle_is_shifted_towards_one_edge(self):
        # Arrange
        self.part(_plate(80, 60, 6, [(-31, -20), (29, -20), (-31, 20), (29, 20)]))

        # Act
        result = self.check(
            "distance_between",
            7.25,
            select_a={"hole": {"diameter": 5.5}},
            select_b={"face": {"normal": [-1, 0, 0]}},
        )

        # Assert
        self.assertFalse(result["passed"])
        self.assertAlmostEqual(result["measured"], 6.25, places=6)

    def test_should_pair_distinct_faces_when_both_sides_use_the_same_selector(self):
        # Arrange: g3-dev-015 — a 6 mm rib on the centreline of a 40 mm wide base: the base's
        # +Y side and the rib's +Y side are 20 - 3 = 17 mm apart.
        rib = Part.makeBox(60, 6, 20, V(-30, -3, 5))
        self.part(_plate(60, 40, 5).fuse(rib).removeSplitter())

        # Act
        result = self.check(
            "distance_between",
            17.0,
            select_a={"face": {"normal": [0, 1, 0]}},
            select_b={"face": {"normal": [0, 1, 0]}},
        )

        # Assert
        self.assertTrue(result["passed"], result["detail"])
        self.assertEqual(len(result["measured"]), 2)
        for value in result["measured"]:
            self.assertAlmostEqual(value, 17.0, places=6)

    def test_should_measure_between_outside_cylinders_when_the_faces_are_selected_by_diameter(
        self,
    ):
        # Arrange: g3-dev-020 — two 14 mm bosses with axes 50 mm apart are 36 mm apart.
        block = _plate(80, 30, 10)
        for x in (-25, 25):
            block = block.fuse(_bore(7.0, 12.0, x, 0, 10))
        self.part(block.removeSplitter())

        # Act
        result = self.check(
            "distance_between",
            36.0,
            select_a={"face": {"diameter": 14.0}},
            select_b={"face": {"diameter": 14.0}},
        )

        # Assert
        self.assertTrue(result["passed"], result["detail"])


class AngleBetweenTest(_PartFixture):
    def test_should_pass_when_the_two_legs_are_perpendicular(self):
        # Arrange: g3-dev-002 — the underside and the vertical leg's outer face.
        bracket = Part.makeBox(60, 40, 5).fuse(Part.makeBox(5, 40, 50)).removeSplitter()
        self.part(bracket)

        # Act
        result = self.check(
            "angle_between",
            90.0,
            select_a={"face": {"normal": [0, 0, -1]}},
            select_b={"face": {"normal": [-1, 0, 0]}},
        )

        # Assert
        self.assertTrue(result["passed"], result["detail"])
        self.assertAlmostEqual(result["measured"], 90.0, places=6)

    def test_should_fail_when_the_hole_is_drilled_five_degrees_off_the_face_normal(self):
        # Arrange
        tilted = V(math.sin(math.radians(5)), 0, math.cos(math.radians(5)))
        plate = Part.makeBox(40, 40, 10, V(-20, -20, 0))
        self.part(plate.cut(Part.makeCylinder(3.0, 30.0, V(0, 0, -10), tilted)))

        # Act
        result = self.check(
            "angle_between",
            0.0,
            select_a={"face": {"normal": [0, 0, 1]}},
            select_b={"hole": {"diameter": 6.0}},
        )

        # Assert
        self.assertFalse(result["passed"])
        self.assertAlmostEqual(result["measured"], 5.0, places=6)


class ExpectBboxTest(_PartFixture):
    def test_should_pass_when_the_frame_extents_match_in_any_order(self):
        # Arrange
        self.part(_plate(80, 60, 6))

        # Act
        result = self.check("expect_bbox", [6.0, 80.0, 60.0])

        # Assert
        self.assertTrue(result["passed"], result["detail"])

    def test_should_fail_when_the_plate_is_thicker_than_declared(self):
        # Arrange
        self.part(_plate(80, 60, 8))

        # Act
        result = self.check("expect_bbox", [80.0, 60.0, 6.0])

        # Assert
        self.assertFalse(result["passed"])


class ExpectExtentTest(_PartFixture):
    def test_should_pass_when_the_length_along_the_direction_matches(self):
        # Arrange
        self.part(_bore(21.35, 150.0).cut(_bore(18.25, 150.0)))

        # Act
        result = self.check("expect_extent", 150.0, direction=[0, 0, 1])

        # Assert
        self.assertTrue(result["passed"], result["detail"])

    def test_should_fail_when_the_part_is_cut_short(self):
        # Arrange
        self.part(_bore(21.35, 140.0).cut(_bore(18.25, 140.0)))

        # Act
        result = self.check("expect_extent", 150.0, direction=[0, 0, 1])

        # Assert
        self.assertFalse(result["passed"])
        self.assertAlmostEqual(result["measured"], 140.0, places=6)


class ExpectVolumeTest(_PartFixture):
    def test_should_pass_when_the_volume_is_within_one_percent(self):
        # Arrange
        self.part(Part.makeBox(10, 20, 30))

        # Act
        result = self.check("expect_volume", 6000.0 * 1.009)

        # Assert
        self.assertTrue(result["passed"], result["detail"])

    def test_should_fail_when_the_volume_is_outside_the_declared_band(self):
        # Arrange
        self.part(Part.makeBox(12, 20, 30))

        # Act
        result = self.check("expect_volume", 6000.0, tol={"rel": 0.001})

        # Assert
        self.assertFalse(result["passed"])


class FrameInvarianceTest(_PartFixture):
    """A frame-relative measurement does not change when the part and its frame move together."""

    BODY_MOVE = App.Placement(V(100, -40, 25), App.Rotation(V(1, 1, 1), 40))

    def body_checks(self):
        return [
            {"fn": "hole_position", "expect": [20.0, 15.0], "select": {"diameter": 5.5}},
            {"fn": "expect_bbox", "expect": [80.0, 60.0, 6.0]},
            {"fn": "expect_extent", "expect": 80.0, "direction": [1, 0, 0]},
            {
                "fn": "distance_between",
                "expect": 17.25,
                "select_a": {"hole": {"diameter": 5.5}},
                "select_b": {"face": {"normal": [-1, 0, 0]}},
            },
        ]

    def assert_same(self, before, after):
        for first, second in zip(before["checks"], after["checks"], strict=True):
            self.assertTrue(first["passed"], first)
            self.assertTrue(second["passed"], second)
            flat_first = (
                first["measured"] if isinstance(first["measured"], list) else [first["measured"]]
            )
            flat_second = (
                second["measured"] if isinstance(second["measured"], list) else [second["measured"]]
            )
            for a, b in zip(flat_first, flat_second, strict=True):
                self.assertAlmostEqual(a, b, places=6)

    def test_should_measure_the_same_in_the_sketch_plane_frame_when_the_body_is_moved(self):
        # Arrange
        body = self.drilled_body()
        before = self.measure(self.body_checks(), XY_PLANE, target="Hole")
        body.Placement = self.BODY_MOVE
        self.document.recompute()

        # Act
        after = self.measure(self.body_checks(), XY_PLANE, target="Hole")

        # Assert
        self.assert_same(before, after)
        self.assertEqual(after["banner"]["anchor_frame"]["entity"], "XY_Plane")

    def test_should_forward_the_frame_when_the_harness_grades_a_moved_body(self):
        # Arrange
        body = self.drilled_body()
        checks = [{"fn": "hole_position", "expect": [20.0, 15.0], "select": {"diameter": 5.5}}]
        before = harness.evaluate(self.document, checks, XY_PLANE)
        body.Placement = self.BODY_MOVE
        self.document.recompute()

        # Act
        in_frame = harness.evaluate(self.document, checks, XY_PLANE)
        in_global = harness.evaluate(self.document, checks)

        # Assert
        self.assertTrue(before[0]["passed"], before[0]["detail"])
        self.assertTrue(in_frame[0]["passed"], in_frame[0]["detail"])
        self.assertFalse(in_global[0]["passed"], "the moved hole must not sit at (20, 15) globally")

    def test_should_measure_from_the_datum_in_the_named_datum_frame_when_the_body_is_moved(self):
        # Arrange: the datum sits at (10, 5), so the hole at (20, 15) reads (10, 10) from it.
        body = self.drilled_body()
        datum = body.newObject("PartDesign::CoordinateSystem", "PlateCornerDatum")
        datum.MapMode = "Deactivated"
        datum.Placement = App.Placement(V(10, 5, 0), App.Rotation())
        self.document.recompute()
        frame = {"kind": "named_datum", "ref": "PlateCornerDatum"}
        checks = [{"fn": "hole_position", "expect": [10.0, 10.0], "select": {"diameter": 5.5}}]
        before = self.measure(checks, frame, target="Hole")
        body.Placement = self.BODY_MOVE
        self.document.recompute()

        # Act
        after = self.measure(checks, frame, target="Hole")

        # Assert
        self.assert_same(before, after)
        self.assertEqual(after["banner"]["anchor_frame"]["entity"], "PlateCornerDatum")

    def test_should_measure_the_same_in_the_largest_face_frame_when_the_part_is_moved(self):
        # Arrange: a rotation about document X tilts the face but keeps its in-plane X axis.
        obj = self.part(_jig_block())
        checks = [
            {"fn": "hole_position", "expect": [0.0, 0.0], "select": {"axis": [0, 0, 1]}},
            {"fn": "expect_bbox", "expect": [50.0, 50.0, 25.0]},
            {"fn": "expect_extent", "expect": 25.0, "direction": [0, 0, 1]},
        ]
        before = self.measure(checks, FACE_FRAME)
        obj.Placement = App.Placement(V(30, -20, 15), App.Rotation(V(1, 0, 0), 35))
        self.document.recompute()

        # Act
        after = self.measure(checks, FACE_FRAME)

        # Assert
        self.assert_same(before, after)


class LargestPlanarFaceTieBreakTest(_PartFixture):
    def test_should_pick_the_lower_face_when_two_largest_faces_tie_on_area(self):
        # Arrange: a 40 x 40 x 10 plate's top and bottom faces are equal.
        self.part(Part.makeBox(40, 40, 10))

        # Act
        frame = self.measure([{"fn": "expect_volume", "expect": 16000.0}], FACE_FRAME)["banner"][
            "anchor_frame"
        ]

        # Assert
        self.assertEqual(frame["entity"], "Face5")
        self.assertEqual(frame["origin"], [20.0, 20.0, 0.0])
        self.assertEqual(frame["axes"], [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]])

    def test_should_pick_the_lowest_centroid_x_when_tied_faces_carry_no_mapped_names(self):
        # Arrange: a 10 x 40 x 40 block's x=0 and x=10 faces tie on area and on centroid Z.
        self.part(Part.makeBox(10, 40, 40))

        # Act
        frame = self.measure([{"fn": "expect_volume", "expect": 16000.0}], FACE_FRAME)["banner"][
            "anchor_frame"
        ]

        # Assert
        self.assertEqual(frame["entity"], "Face1")
        # Document X projects to nothing on a face normal to X, so in-plane X falls back to Y.
        self.assertEqual(frame["axes"], [[0.0, 1.0, 0.0], [0.0, 0.0, 1.0], [1.0, 0.0, 0.0]])

    def test_should_measure_an_off_centre_bore_from_the_face_centroid_in_the_face_frame(self):
        # Arrange: the 50 x 50 bottom face's centroid is (25, 25); the bore sits at (35, 30).
        self.part(Part.makeBox(50, 50, 25).cut(_bore(6.0, 15.0, 35, 30, 10)))

        # Act
        result = self.check("hole_position", [10.0, 5.0], FACE_FRAME, select={"diameter": 12.0})

        # Assert
        self.assertTrue(result["passed"], result["detail"])
        self.assertAlmostEqual(result["measured"][0], 10.0, places=6)
        self.assertAlmostEqual(result["measured"][1], 5.0, places=6)

    def test_should_name_the_lowest_mapped_name_when_tied_faces_carry_an_element_map(self):
        # Arrange
        body = self.body()
        box = body.newObject("PartDesign::AdditiveBox", "Box")
        box.Length, box.Width, box.Height = 10, 40, 40
        self.document.recompute()
        names = [body.Shape.getElementMappedName(face) for face in ("Face1", "Face2")]
        if not all(names):
            self.skipTest("this FreeCAD build attaches no element map to the body shape")

        # Act
        frame = self.measure([{"fn": "expect_volume", "expect": 16000.0}], FACE_FRAME, "Body")[
            "banner"
        ]["anchor_frame"]

        # Assert
        self.assertEqual(frame["entity"], min(names))

    def test_should_fail_frame_checks_and_still_measure_volume_when_the_tie_is_unresolvable(self):
        # Arrange: two coincident boxes duplicate every face, centroid included, and
        # ``Part.Compound`` attaches no element map to break the tie with.
        box = Part.makeBox(20, 20, 10).cut(_bore(3.0, 10.0, 10, 10))
        self.part(Part.Compound([box, box.copy()]))
        volume = 2 * (4000.0 - math.pi * 9.0 * 10.0)

        # Act
        content = self.measure(
            [
                {"fn": "hole_position", "expect": [0.0, 0.0]},
                {"fn": "expect_volume", "expect": volume},
            ],
            FACE_FRAME,
        )

        # Assert
        position, volume_check = content["checks"]
        self.assertFalse(position["passed"])
        self.assertEqual(position["detail"]["code"], INVALID_INPUT_CODE)
        self.assertTrue(volume_check["passed"], volume_check["detail"])
        self.assertIn("tie", content["banner"]["anchor_frame"]["unresolved"])


class NamedFrameLabelTest(_PartFixture):
    """A named frame ``ref`` matches an object ``Name`` first, then a ``Label`` only one carries."""

    PREFERENCES = "User parameter:BaseApp/Preferences/Document"

    def setUp(self):
        super().setUp()
        self.part(_plate(80, 60, 6, [(20, 15)]))
        self.frame = {"kind": "named_datum", "ref": "CornerDatum"}
        self.checks = [{"fn": "hole_position", "expect": [10.0, 10.0], "select": {"diameter": 5.5}}]

    def datum(self, name):
        datum = self.document.addObject("Part::Feature", name)
        datum.Label = "CornerDatum"
        datum.Placement = App.Placement(V(10, 5, 0), App.Rotation())
        self.document.recompute()
        return datum

    def test_should_resolve_the_frame_by_label_when_no_object_has_that_name(self):
        # Arrange
        self.datum("Datum")

        # Act
        content = self.measure(self.checks, self.frame)

        # Assert
        self.assertTrue(content["checks"][0]["passed"], content["checks"][0]["detail"])
        self.assertEqual(content["banner"]["anchor_frame"]["entity"], "Datum")

    def test_should_fail_frame_checks_when_two_objects_share_the_label(self):
        # Arrange: FreeCAD renames a duplicate label unless the document preference allows it.
        preferences = App.ParamGet(self.PREFERENCES)
        had_setting = "DuplicateLabels" in preferences.GetBools()
        previous = preferences.GetBool("DuplicateLabels", False)
        preferences.SetBool("DuplicateLabels", True)
        try:
            self.datum("DatumA")
            self.datum("DatumB")
        finally:
            if had_setting:
                preferences.SetBool("DuplicateLabels", previous)
            else:
                preferences.RemBool("DuplicateLabels")

        # Act
        content = self.measure(self.checks, self.frame)

        # Assert
        self.assertFalse(content["checks"][0]["passed"])
        self.assertEqual(content["checks"][0]["detail"]["code"], INVALID_INPUT_CODE)
        self.assertIn("several objects", content["banner"]["anchor_frame"]["unresolved"])


class CanonicalFrameTest(_PartFixture):
    """Every ``(kind, ref)`` the 20 G3 dev specs declare resolves to a hand-derived frame.

    The in-FreeCAD suite runs on both CI legs, so these fixtures are the cross-leg proof for the
    specs no corrupted plan builds (G3.E.3). The entity of a ``largest_planar_face`` frame is a
    mapped name on a Body shape and is not asserted.
    """

    IDENTITY = [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]]

    def setUp(self):
        super().setUp()
        body = self.body()
        box = body.newObject("PartDesign::AdditiveBox", "Box")
        box.Length, box.Width, box.Height = 10, 40, 40
        datum = body.newObject("PartDesign::CoordinateSystem", "PlateCornerDatum")
        datum.MapMode = "Deactivated"
        datum.Placement = App.Placement(V(25, 30, 0), App.Rotation())
        self.document.recompute()

    def frame(self, anchor_frame):
        checks = [{"fn": "expect_volume", "expect": 16000.0}]
        return self.measure(checks, anchor_frame, target="Box")["banner"]["anchor_frame"]

    def test_should_resolve_the_origin_xy_plane_to_the_document_axes(self):
        # Arrange
        declared = XY_PLANE

        # Act
        frame = self.frame(declared)

        # Assert
        self.assertEqual(frame["entity"], "XY_Plane")
        self.assertEqual(frame["origin"], [0.0, 0.0, 0.0])
        self.assertEqual(frame["axes"], self.IDENTITY)

    def test_should_resolve_the_origin_xz_plane_with_its_normal_along_minus_y(self):
        # Arrange: a sketch on XZ maps (u, v) to (u, 0, v), so frame Y is document +Z and the
        # right-handed normal is document -Y.
        declared = {"kind": "base_sketch_plane", "ref": "XZ_Plane"}

        # Act
        frame = self.frame(declared)

        # Assert
        self.assertEqual(frame["entity"], "XZ_Plane")
        self.assertEqual(frame["origin"], [0.0, 0.0, 0.0])
        self.assertEqual(frame["axes"], [[1.0, 0.0, 0.0], [0.0, 0.0, 1.0], [0.0, -1.0, 0.0]])

    def test_should_resolve_the_plate_corner_datum_to_its_placement(self):
        # Arrange
        declared = {"kind": "named_datum", "ref": "PlateCornerDatum"}

        # Act
        frame = self.frame(declared)

        # Assert
        self.assertEqual(frame["entity"], "PlateCornerDatum")
        self.assertEqual(frame["origin"], [25.0, 30.0, 0.0])
        self.assertEqual(frame["axes"], self.IDENTITY)

    def test_should_break_the_symmetric_face_tie_on_centroid_x_for_a_body_feature(self):
        # Arrange: the 10 x 40 x 40 box's x=0 and x=10 faces tie on area and centroid Z; the
        # x=0 face wins, and in-plane X falls back to document Y on a face normal to X.
        declared = FACE_FRAME

        # Act
        frame = self.frame(declared)

        # Assert
        self.assertEqual(frame["origin"], [0.0, 20.0, 20.0])
        self.assertEqual(frame["axes"], [[0.0, 1.0, 0.0], [0.0, 0.0, 1.0], [1.0, 0.0, 0.0]])


class ToleranceFloorTest(_PartFixture):
    def test_should_pass_within_the_shape_tolerance_when_it_exceeds_the_declared_band(self):
        # Arrange: a 0.5 mm shape tolerance floors the 0.05 mm band, so 0.3 mm passes.
        box = Part.makeBox(10, 20, 30)
        box.fixTolerance(0.5)
        self.part(box)

        # Act
        result = self.check("expect_bbox", [10.3, 20.0, 30.0], tol={"abs": 0.05})

        # Assert
        self.assertTrue(result["passed"], result["detail"])
        self.assertIn("clamped to shape tolerance floor", result["detail"]["message"])


class IoMatrixTest(_PartFixture):
    """The spec's I/O and edge-case rows that the per-primitive tests do not already cover."""

    def test_should_fail_with_invalid_input_when_a_selector_matches_nothing(self):
        # Arrange
        self.part(_plate(40, 40, 6, [(0, 0)]))

        # Act
        result = self.check("hole_diameter", 20.0, select={"diameter": 20.0})

        # Assert
        self.assertFalse(result["passed"])
        self.assertEqual(result["detail"]["code"], INVALID_INPUT_CODE)

    def test_should_fail_frame_checks_and_measure_the_rest_when_the_named_datum_is_absent(self):
        # Arrange
        self.part(_plate(40, 40, 6, [(0, 0)]))
        frame = {"kind": "named_datum", "ref": "NoSuchDatum"}

        # Act
        content = self.measure(
            [
                {"fn": "is_valid_solid", "expect": True},
                {"fn": "expect_volume", "expect": 9600.0 - math.pi * 2.75**2 * 6},
                {"fn": "hole_position", "expect": [0.0, 0.0]},
                {"fn": "expect_bbox", "expect": [40.0, 40.0, 6.0]},
            ],
            frame,
        )

        # Assert
        self.assertEqual([c["passed"] for c in content["checks"]], [True, True, False, False])
        for frame_check in content["checks"][2:]:
            self.assertEqual(frame_check["detail"]["code"], INVALID_INPUT_CODE)
        self.assertIn("NoSuchDatum", content["banner"]["anchor_frame"]["unresolved"])
        self.assertEqual(content["verdict"], "INVALID_INPUT")

    def test_should_raise_validation_error_when_verify_shape_gets_a_malformed_check(self):
        # Arrange
        self.part(_plate(40, 40, 6, [(0, 0)]))
        malformed = [
            {"fn": "no_such_primitive", "expect": 1},
            {"fn": "hole_diameter", "expect": 5.5, "select": "Face6"},
            {"fn": "hole_position", "expect": [0.0, 0.0, 0.0]},
        ]

        # Act
        acts = [lambda check=check: self.measure([check]) for check in malformed]

        # Assert
        for check, act in zip(malformed, acts, strict=True):
            with self.subTest(check=check), self.assertRaises(ValidationError):
                act()

    def test_should_map_a_malformed_check_to_invalid_input_status_through_dispatch(self):
        # Arrange
        self.part(_plate(40, 40, 6, [(0, 0)]))
        methods = MethodRegistry()
        methods.register(
            RpcMethod(
                name="verify_shape",
                handler=lambda **p: verify.verify_shape(self.registry, **p),
                mutating=False,
            )
        )
        request = {
            "doc": self.handle,
            "object": "Part",
            "checks": [{"fn": "hole_diameter", "expect": 5.5, "select": "Face6"}],
        }

        # Act
        envelope = methods.dispatch("verify_shape", request)

        # Assert
        self.assertEqual(envelope["status"], "INVALID_INPUT")

    def test_should_turn_a_malformed_check_into_a_failing_check_when_the_harness_grades_it(self):
        # Arrange
        self.part(_plate(40, 40, 6, [(0, 0)]))
        malformed = [
            {"fn": "hole_diameter", "expect": 5.5, "select": "Face6"},
            {"fn": "expect_bbox", "expect": [40.0, 40.0]},
        ]

        # Act
        results = harness.evaluate(self.document, malformed, FACE_FRAME)

        # Assert
        self.assertEqual([r["passed"] for r in results], [False, False])
        self.assertEqual({r["detail"]["code"] for r in results}, {INVALID_INPUT_CODE})

    def test_should_report_the_global_frame_when_no_anchor_frame_is_given(self):
        # Arrange
        self.part(Part.makeBox(10, 20, 30))

        # Act
        content = self.measure([{"fn": "expect_bbox", "expect": [10.0, 20.0, 30.0]}])

        # Assert
        self.assertEqual(content["banner"]["anchor_frame"]["kind"], "global")
        self.assertTrue(content["checks"][0]["passed"], content["checks"][0]["detail"])


if __name__ == "__main__":
    unittest.main()
