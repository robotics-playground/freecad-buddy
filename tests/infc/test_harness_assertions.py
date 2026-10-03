"""In-FreeCAD tests for the G2 grader's geometric measurements (stdlib unittest).

Run via ``FreeCADCmd tests/run_tests.py``. Covers the two measurements that read real B-rep
geometry rather than a document attribute: ``hole_through``, which must compare a hole wall
against the material the hole's own axis crosses, and ``count_cylindrical_holes``, whose
hole-versus-boss probe must survive a hole bored close to a part edge.

Fixtures are raw ``Part`` solids on ``Part::Feature`` objects: the grader reads only ``Shape``,
so a PartDesign tree would add a dependency the measurements do not have.
"""

import sys
import unittest
from pathlib import Path

import FreeCAD as App
import Part

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from benchmarks.harness import assertions  # noqa: E402
from freecad_buddy.usecases import assertions as primitives  # noqa: E402


class _ShapeFixture(unittest.TestCase):
    """A scratch document onto which a test drops one measured solid."""

    def setUp(self):
        self.document = App.newDocument("harness_assertions")

    def tearDown(self):
        for name in list(App.listDocuments().keys()):
            App.closeDocument(name)

    def feature(self, shape, name="Solid"):
        """Put ``shape`` on the document as the object the grader will measure."""
        obj = self.document.addObject("Part::Feature", name)
        obj.Shape = shape
        self.document.recompute()
        return obj

    def grade(self, fn, expect, **extra):
        """Run one grader check over the document and return the resulting ``Check``."""
        check = {"fn": fn, "expect": expect}
        check.update(extra)
        results = assertions.evaluate(self.document, [check])
        self.assertEqual(len(results), 1)
        return results[0]


class HoleThroughLocalThicknessTest(_ShapeFixture):
    """``hole_through`` must measure the material the hole's own axis crosses.

    A stepped part's overall extent along the hole axis is larger than the thickness the hole
    passes through, so a whole-solid comparison mis-grades in both directions.
    """

    def stepped_plate(self):
        """A two-step plate: a 40x40x30 tall block joined to a 40x40x5 thin ledge.

        The thin ledge spans z=0..5 over x=40..80; the tall block spans z=0..30 over x=0..40.
        A hole drilled down through the ledge crosses 5 mm of material while the solid's Z
        extent is 30 mm.
        """
        tall = Part.makeBox(40.0, 40.0, 30.0, App.Vector(0, 0, 0))
        ledge = Part.makeBox(40.0, 40.0, 5.0, App.Vector(40, 0, 0))
        return tall.fuse(ledge).removeSplitter()

    def test_a_hole_through_the_thin_ledge_grades_as_through(self):
        # The bore spans the ledge's full 5 mm thickness and exits both faces, so it is through
        # no matter that the fused solid is 30 mm tall elsewhere.
        bore = Part.makeCylinder(3.0, 5.0, App.Vector(60, 20, 0), App.Vector(0, 0, 1))
        self.feature(self.stepped_plate().cut(bore))

        result = self.grade("hole_through", True)

        self.assertTrue(result["passed"], result["detail"])
        self.assertTrue(result["measured"], result["detail"])

    def test_a_blind_hole_in_the_thick_step_grades_as_blind(self):
        # A 5 mm deep bore into a 30 mm tall step does not exit: it must not be rescued by the
        # ledge's 5 mm thickness happening to match the bore's length.
        bore = Part.makeCylinder(3.0, 5.0, App.Vector(20, 20, 25), App.Vector(0, 0, 1))
        self.feature(self.stepped_plate().cut(bore))

        result = self.grade("hole_through", False)

        self.assertTrue(result["passed"], result["detail"])
        self.assertFalse(result["measured"], result["detail"])

    def test_a_through_hole_in_a_plain_plate_still_grades_as_through(self):
        plate = Part.makeBox(40.0, 40.0, 10.0)
        bore = Part.makeCylinder(3.0, 10.0, App.Vector(20, 20, 0), App.Vector(0, 0, 1))
        self.feature(plate.cut(bore))

        result = self.grade("hole_through", True)

        self.assertTrue(result["passed"], result["detail"])
        self.assertTrue(result["measured"], result["detail"])

    def test_a_blind_hole_in_a_plain_plate_still_grades_as_blind(self):
        plate = Part.makeBox(40.0, 40.0, 10.0)
        bore = Part.makeCylinder(3.0, 4.0, App.Vector(20, 20, 6), App.Vector(0, 0, 1))
        self.feature(plate.cut(bore))

        result = self.grade("hole_through", False)

        self.assertTrue(result["passed"], result["detail"])
        self.assertFalse(result["measured"], result["detail"])


class HoleWallNearEdgeTest(_ShapeFixture):
    """``count_cylindrical_holes`` must count a hole bored close to a part edge.

    The hole/boss probe steps off the wall by up to 0.5 mm. When the wall sits nearer than that
    to the outside of the part, a single outward step lands in the void and the hole is dropped.
    """

    def test_a_hole_a_quarter_millimetre_from_the_edge_is_counted(self):
        # A r=3 bore centred 3.25 mm from the x=0 face leaves 0.25 mm of material at its
        # closest point — inside the probe's own 0.5 mm step.
        plate = Part.makeBox(40.0, 40.0, 10.0)
        bore = Part.makeCylinder(3.0, 10.0, App.Vector(3.25, 20, 0), App.Vector(0, 0, 1))
        self.feature(plate.cut(bore))

        result = self.grade("count_cylindrical_holes", 1)

        self.assertTrue(result["passed"], result["detail"])
        self.assertEqual(result["measured"], 1)

    def test_a_boss_a_quarter_millimetre_from_the_edge_is_not_counted(self):
        # The mirror case: material inside the cylinder, void outside. A probe made tolerant of
        # a nearby edge must still refuse to count a boss.
        plate = Part.makeBox(40.0, 40.0, 10.0)
        boss = Part.makeCylinder(3.0, 6.0, App.Vector(3.25, 20, 10), App.Vector(0, 0, 1))
        self.feature(plate.fuse(boss).removeSplitter())

        result = self.grade("count_cylindrical_holes", 0)

        self.assertTrue(result["passed"], result["detail"])
        self.assertEqual(result["measured"], 0)

    def test_a_hole_well_inside_the_plate_is_still_counted(self):
        plate = Part.makeBox(40.0, 40.0, 10.0)
        bore = Part.makeCylinder(3.0, 10.0, App.Vector(20, 20, 0), App.Vector(0, 0, 1))
        self.feature(plate.cut(bore))

        result = self.grade("count_cylindrical_holes", 1)

        self.assertTrue(result["passed"], result["detail"])
        self.assertEqual(result["measured"], 1)


class GradingFailureIsReportedTest(_ShapeFixture):
    """A measurement that cannot be taken must report a grading failure, not "not a hole"."""

    def test_a_shape_whose_membership_test_refuses_reports_invalid_input(self):
        # A membership test that cannot run is a grading failure, not a boss verdict: the check
        # must carry the INVALID_INPUT code so an operator can tell the two apart.
        plate = Part.makeBox(40.0, 40.0, 10.0)
        bore = Part.makeCylinder(3.0, 10.0, App.Vector(20, 20, 0), App.Vector(0, 0, 1))
        obj = self.feature(plate.cut(bore))

        class _RefusingShape:
            """Wraps a real shape but refuses the membership test the probe depends on."""

            def __init__(self, shape):
                self._shape = shape

            def __getattr__(self, name):
                return getattr(self._shape, name)

            def isInside(self, *args):
                raise RuntimeError("planted membership-test failure")

        real_shape = obj.Shape
        original = assertions._graded_shape
        assertions._graded_shape = lambda document: _RefusingShape(real_shape)
        try:
            result = self.grade("count_cylindrical_holes", 1)
        finally:
            assertions._graded_shape = original

        self.assertFalse(result["passed"], result["detail"])
        self.assertEqual(result["detail"].get("code"), assertions._INVALID_INPUT)
        self.assertIn("planted membership-test failure", result["detail"]["message"])

    def test_an_unsampleable_wall_reports_invalid_input(self):
        # The same distinction for the other failure mode: a face carrying no usable parameter
        # range must not silently count as "not a hole".
        plate = Part.makeBox(40.0, 40.0, 10.0)
        bore = Part.makeCylinder(3.0, 10.0, App.Vector(20, 20, 0), App.Vector(0, 0, 1))
        self.feature(plate.cut(bore))

        original = primitives._cylindrical_faces

        class _RangelessFace:
            """A cylindrical face that reports a full turn but no usable parameter range."""

            def __init__(self, face):
                self._face = face
                self.ParameterRange = (0.0, 2.0 * 3.141592653589793)

            def __getattr__(self, name):
                return getattr(self._face, name)

        primitives._cylindrical_faces = lambda shape: [
            (index, _RangelessFace(face)) for index, face in original(shape)
        ]
        try:
            result = self.grade("count_cylindrical_holes", 1)
        finally:
            primitives._cylindrical_faces = original

        self.assertFalse(result["passed"], result["detail"])
        self.assertEqual(result["detail"].get("code"), assertions._INVALID_INPUT)
        self.assertIn("ParameterRange", result["detail"]["message"])

    def test_an_unmeasurable_extent_is_reported_rather_than_read_as_zero(self):
        self.assertIsNone(primitives._extent_along([], (0.0, 0.0, 1.0)))
        point = App.Vector(1.0, 2.0, 3.0)
        self.assertIsNone(primitives._extent_along([point], (0.0, 0.0, 1.0)))
        self.assertEqual(primitives._extent_along([point, point], (0.0, 0.0, 1.0)), 0.0)


if __name__ == "__main__":
    unittest.main()
