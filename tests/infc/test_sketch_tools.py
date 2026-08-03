"""In-FreeCAD tests for the eight ``sketch_*`` tools (stdlib unittest).

Run via ``FreeCADCmd tests/run_tests.py``. Covers the five benchmark sketch shapes reaching
``FullyConstrained``, the deg-to-rad datum conversion, every pre-bracket validation rejection,
the conflicting-set rollback with named diagnostics, and a forced snapshot restore proving the
registry was rebound.

Expected values are analytic — hand-computed geometry and the FreeCAD-source constraint recipes
that pin it — never captured from ``verify_sketch`` or any tool under test.
"""

import glob
import math
import os
import tempfile
import unittest

import FreeCAD as App

from freecad_buddy.usecases import confirm, sketches, transaction
from freecad_buddy.usecases.documents import DocumentRegistry, ValidationError

_SNAPSHOT_GLOB = os.path.join(tempfile.gettempdir(), "FCB_TMP_snap_*")


def _snapshot_leftovers():
    """Every reserved-prefix snapshot directory currently on disk."""
    return sorted(glob.glob(_SNAPSHOT_GLOB))


def mm(value):
    return {"value": value, "unit": "mm"}


def deg(value):
    return {"value": value, "unit": "deg"}


def line(start, end):
    return {"kind": "line_segment", "start": start, "end": end}


def arc(center, radius, start_angle, end_angle):
    return {
        "kind": "arc_of_circle",
        "center": center,
        "radius": mm(radius),
        "start_angle": deg(start_angle),
        "end_angle": deg(end_angle),
    }


def coincident(g1, p1, g2, p2):
    return {"type": "Coincident", "first": g1, "first_pos": p1, "second": g2, "second_pos": p2}


def tangent(g1, p1, g2, p2):
    return {"type": "Tangent", "first": g1, "first_pos": p1, "second": g2, "second_pos": p2}


def distance_x(g1, p1, g2, p2, value):
    return {
        "type": "DistanceX",
        "first": g1,
        "first_pos": p1,
        "second": g2,
        "second_pos": p2,
        "value": mm(value),
    }


def distance_y(g1, p1, g2, p2, value):
    return {
        "type": "DistanceY",
        "first": g1,
        "first_pos": p1,
        "second": g2,
        "second_pos": p2,
        "value": mm(value),
    }


def circle_radius(geo_id, value):
    return {"type": "Radius", "first": geo_id, "value": mm(value)}


# Origin: geo -1 with pos=start is the sketch root point (Sketcher GeoEnum).
ORIGIN_GEO = -1
ORIGIN_POS = 1

# A circle pinned at the origin and dimensioned: DoF 0, so the add commits.
CIRCLE_AT_ORIGIN = {"kind": "circle", "center": [0, 0], "radius": mm(5.0)}
CIRCLE_CONSTRAINTS = [
    coincident(0, 3, ORIGIN_GEO, ORIGIN_POS),
    circle_radius(0, 5.0),
]

# A closed rectangle: four segments joined end-to-start, alternately horizontal and vertical,
# pinned to the origin and dimensioned in X and Y.
RECTANGLE_GEOMETRY = [
    line([0, 0], [16, 0]),
    line([16, 0], [16, 8]),
    line([16, 8], [0, 8]),
    line([0, 8], [0, 0]),
]
RECTANGLE_CONSTRAINTS = [
    coincident(0, 2, 1, 1),
    coincident(1, 2, 2, 1),
    coincident(2, 2, 3, 1),
    coincident(3, 2, 0, 1),
    {"type": "Horizontal", "first": 0},
    {"type": "Horizontal", "first": 2},
    {"type": "Vertical", "first": 1},
    {"type": "Vertical", "first": 3},
    coincident(0, 1, ORIGIN_GEO, ORIGIN_POS),
    distance_x(0, 1, 0, 2, 16.0),
    distance_y(1, 1, 1, 2, 8.0),
]

TRIANGLE_HEIGHT = 6.0 * math.sqrt(3.0) / 2.0

# FreeCAD's own slot recipe (DrawSketchHandlerSlot::createShape): two cap arcs, two flank lines,
# joined by endpoint tangents plus one Equal, then located and dimensioned.
SLOT_GEOMETRY = [
    arc([-5, 0], 5.0, 90, 270),
    arc([5, 0], 5.0, 270, 90),
    line([-5, 5], [5, 5]),
    line([-5, -5], [5, -5]),
]
SLOT_CONSTRAINTS = [
    tangent(0, 1, 2, 1),
    tangent(0, 2, 3, 1),
    tangent(1, 2, 2, 2),
    tangent(1, 1, 3, 2),
    {"type": "Equal", "first": 0, "second": 1},
    {"type": "Horizontal", "first": 2},
    coincident(0, 3, ORIGIN_GEO, ORIGIN_POS),
    {"type": "Radius", "first": 0, "value": mm(5.0)},
    distance_x(0, 3, 1, 3, 10.0),
]


class _SketchFixture(unittest.TestCase):
    def setUp(self):
        for path in _snapshot_leftovers():
            for name in os.listdir(path):
                os.remove(os.path.join(path, name))
            os.rmdir(path)
        # These tests call the use cases directly, with no host to read the operator flag, so the
        # posture is set here. The gate itself is covered in test_confirm_gate.py.
        self._posture = confirm.set_auto_approve(True)
        self.registry = DocumentRegistry()
        created = self.registry.document_create("sketch_tools")
        self.handle = created["structured_content"]["doc"]

    def tearDown(self):
        confirm.set_auto_approve(self._posture)
        for name in list(App.listDocuments().keys()):
            App.closeDocument(name)

    def assert_rejected_pre_bracket(self, probe, call, *args, **kwargs):
        """Assert ``call`` raises ``ValidationError`` without opening the mutation bracket.

        The I/O matrix requires ``INVALID_INPUT`` pre-bracket: the document untouched and no
        snapshot written. Unchanged state alone would not discriminate — validation moved back
        inside the bracket leaves the document unchanged too, because the rollback restores it.
        The snapshot does discriminate: ``run_mutation`` mints one before it opens its
        transaction, so a snapshot path handed out at all proves the bracket ran.

        :param probe: reads the state the call must not change; compared before and after.
        """
        before = probe()
        real_snapshot_path = transaction.temp_snapshot_path
        minted = []

        def counting_snapshot_path(doc):
            minted.append(doc)
            return real_snapshot_path(doc)

        transaction.temp_snapshot_path = counting_snapshot_path
        try:
            with self.assertRaises(ValidationError):
                call(*args, **kwargs)
        finally:
            transaction.temp_snapshot_path = real_snapshot_path

        self.assertEqual(minted, [], "the mutation bracket opened and wrote a snapshot")
        self.assertEqual(probe(), before)
        self.assertEqual(_snapshot_leftovers(), [])

    def document(self):
        return self.registry.with_document(self.handle, lambda h, d: d)

    def create(self, name, plane="XY", face=None):
        envelope = sketches.sketch_create(
            self.registry, doc=self.handle, name=name, plane=plane, face=face
        )
        self.assertEqual(envelope["status"], "OK", envelope.get("detail"))
        return envelope

    def add(self, name, geometry, constraints=None):
        return sketches.sketch_add_geometry(
            self.registry,
            doc=self.handle,
            sketch=name,
            geometry=geometry,
            constraints=constraints,
        )

    def state(self, envelope):
        return envelope["structured_content"]["sketch_state"]

    def assert_fully_constrained(self, envelope):
        self.assertEqual(
            envelope["status"],
            "OK",
            envelope["structured_content"]["mutation"]["post_verify"]["explanation"],
        )
        state = self.state(envelope)
        self.assertTrue(state["fully_constrained"])
        self.assertEqual(state["dof"], 0)
        self.assertEqual(state["conflicting"], [])
        self.assertEqual(state["malformed"], [])

    def add_plate(self, name="Plate", length=40.0, width=40.0, height=10.0):
        document = self.document()
        box = document.addObject("Part::Box", name)
        box.Length = length
        box.Width = width
        box.Height = height
        document.recompute()
        return box


class SketchCreateTest(_SketchFixture):
    def test_base_plane_sketch_commits_empty_and_fully_constrained(self):
        envelope = self.create("Base", plane="XY")
        state = self.state(envelope)
        self.assertEqual(state["schema"], "fcb.sketch-state/1")
        self.assertEqual(state["dof"], 0)
        self.assertTrue(state["fully_constrained"])
        self.assertEqual(state["geometry_count"], 0)
        self.assertIn("mutation", envelope["structured_content"])

    def test_each_base_plane_matches_the_freecad_origin_plane_rotation(self):
        # Analytic: the sketch normal is the plane's own normal — +Z for XY, -Y for XZ, +X for YZ.
        expected = {
            "XY": (0.0, 0.0, 1.0),
            "XZ": (0.0, -1.0, 0.0),
            "YZ": (1.0, 0.0, 0.0),
        }
        for plane, normal in expected.items():
            self.create(f"On{plane}", plane=plane)
            rotation = self.document().getObject(f"On{plane}").Placement.Rotation
            axis = rotation.multVec(App.Vector(0, 0, 1))
            for measured, want in zip((axis.x, axis.y, axis.z), normal):
                self.assertAlmostEqual(measured, want, places=9, msg=plane)

    def test_planar_face_sketch_attaches_through_attachment_support(self):
        self.add_plate()
        selector = {"kind": "mapped_name", "object": "Plate", "mapped_name": "Face6"}
        self.create("OnFace", plane=None, face=selector)
        sketch = self.document().getObject("OnFace")
        self.assertEqual(sketch.MapMode, "FlatFace")
        self.assertEqual(sketch.AttachmentSupport[0][0].Name, "Plate")
        self.assertEqual(list(sketch.AttachmentSupport[0][1]), ["Face6"])

    def test_non_planar_face_is_rejected_before_the_transaction_opens(self):
        document = self.document()
        cylinder = document.addObject("Part::Cylinder", "Cyl")
        cylinder.Radius = 5.0
        cylinder.Height = 20.0
        document.recompute()
        selector = {"kind": "mapped_name", "object": "Cyl", "mapped_name": "Face1"}

        self.assert_rejected_pre_bracket(
            lambda: len(document.Objects),
            sketches.sketch_create,
            self.registry,
            doc=self.handle,
            name="Bad",
            plane=None,
            face=selector,
        )

        self.assertIsNone(document.getObject("Bad"))

    def test_missing_and_double_target_are_rejected_pre_bracket(self):
        with self.assertRaises(ValidationError):
            sketches.sketch_create(self.registry, doc=self.handle, name="X")
        with self.assertRaises(ValidationError):
            sketches.sketch_create(
                self.registry,
                doc=self.handle,
                name="X",
                plane="XY",
                face={"kind": "mapped_name", "object": "Plate", "mapped_name": "Face6"},
            )

    def test_unknown_plane_is_rejected_pre_bracket(self):
        with self.assertRaises(ValidationError):
            sketches.sketch_create(self.registry, doc=self.handle, name="X", plane="ZZ")

    def test_geometric_selector_is_rejected_pre_bracket(self):
        with self.assertRaises(ValidationError):
            sketches.sketch_create(
                self.registry,
                doc=self.handle,
                name="X",
                face={"kind": "geometric", "object": "Plate", "query": {}},
            )


class BenchmarkShapeTest(_SketchFixture):
    """The five ``benchmarks/g2/dev/*-sketch`` commands driven through the typed tools."""

    def test_g2_dev_001_rectangle_8_by_16_on_xy(self):
        self.create("Rect", plane="XY")
        envelope = self.add("Rect", RECTANGLE_GEOMETRY, RECTANGLE_CONSTRAINTS)

        self.assert_fully_constrained(envelope)
        self.assertEqual(envelope["structured_content"]["geo_ids"], [0, 1, 2, 3])
        self.assertEqual(self.state(envelope)["geometry_count"], 4)
        sketch = self.document().getObject("Rect")
        kinds = [type(geo).__name__ for geo in sketch.Geometry]
        self.assertEqual(kinds, ["LineSegment"] * 4)

    def test_g2_dev_002_circle_diameter_12_at_origin_on_xy(self):
        self.create("Circ", plane="XY")
        envelope = self.add(
            "Circ",
            [{"kind": "circle", "center": [0, 0], "radius": mm(6.0)}],
            [
                coincident(0, 3, ORIGIN_GEO, ORIGIN_POS),
                {"type": "Diameter", "first": 0, "value": mm(12.0)},
            ],
        )

        self.assert_fully_constrained(envelope)
        sketch = self.document().getObject("Circ")
        self.assertEqual([type(geo).__name__ for geo in sketch.Geometry], ["Circle"])
        self.assertAlmostEqual(sketch.Geometry[0].Radius, 6.0, places=6)

    def test_g2_dev_003_square_30_on_a_planar_face(self):
        self.add_plate()
        selector = {"kind": "mapped_name", "object": "Plate", "mapped_name": "Face6"}
        self.create("Sq", plane=None, face=selector)
        envelope = self.add(
            "Sq",
            [line([0, 0], [30, 0]), line([30, 0], [30, 30]), line([30, 30], [0, 30]),
             line([0, 30], [0, 0])],
            [
                coincident(0, 2, 1, 1),
                coincident(1, 2, 2, 1),
                coincident(2, 2, 3, 1),
                coincident(3, 2, 0, 1),
                {"type": "Horizontal", "first": 0},
                {"type": "Horizontal", "first": 2},
                {"type": "Vertical", "first": 1},
                {"type": "Vertical", "first": 3},
                coincident(0, 1, ORIGIN_GEO, ORIGIN_POS),
                distance_x(0, 1, 0, 2, 30.0),
                distance_y(1, 1, 1, 2, 30.0),
            ],
        )

        self.assert_fully_constrained(envelope)
        self.assertEqual(self.state(envelope)["geometry_count"], 4)

    def test_g2_dev_004_equilateral_triangle_side_6_on_xz(self):
        self.create("Tri", plane="XZ")
        envelope = self.add(
            "Tri",
            [
                line([0, 0], [6, 0]),
                line([6, 0], [3, TRIANGLE_HEIGHT]),
                line([3, TRIANGLE_HEIGHT], [0, 0]),
            ],
            [
                coincident(0, 2, 1, 1),
                coincident(1, 2, 2, 1),
                coincident(2, 2, 0, 1),
                coincident(0, 1, ORIGIN_GEO, ORIGIN_POS),
                {"type": "Horizontal", "first": 0},
                {"type": "Equal", "first": 0, "second": 1},
                {"type": "Equal", "first": 1, "second": 2},
                {"type": "Distance", "first": 0, "value": mm(6.0)},
            ],
        )

        self.assert_fully_constrained(envelope)
        sketch = self.document().getObject("Tri")
        self.assertEqual([type(geo).__name__ for geo in sketch.Geometry], ["LineSegment"] * 3)
        for geo in sketch.Geometry:
            self.assertAlmostEqual(geo.StartPoint.distanceToPoint(geo.EndPoint), 6.0, places=5)

    def test_g2_dev_005_slot_20_by_10_with_r5_ends_on_xy(self):
        self.create("Slot", plane="XY")
        envelope = self.add("Slot", SLOT_GEOMETRY, SLOT_CONSTRAINTS)

        self.assert_fully_constrained(envelope)
        sketch = self.document().getObject("Slot")
        kinds = [type(geo).__name__ for geo in sketch.Geometry]
        self.assertEqual(kinds.count("ArcOfCircle"), 2)
        self.assertEqual(kinds.count("LineSegment"), 2)
        for geo in sketch.Geometry:
            if type(geo).__name__ == "ArcOfCircle":
                self.assertAlmostEqual(geo.Radius, 5.0, places=5)


class AddGeometryTest(_SketchFixture):
    def test_geometry_without_constraints_rolls_back_and_names_the_dof(self):
        self.create("Loose", plane="XY")

        envelope = self.add("Loose", [line([0, 0], [10, 0])])

        self.assertEqual(envelope["status"], "SPEC_FAILED")
        block = envelope["structured_content"]["mutation"]
        self.assertTrue(block["rolled_back"])
        self.assertFalse(block["post_verify"]["fully_constrained"])
        self.assertIn("Loose", block["post_verify"]["explanation"])
        self.assertEqual(self.document().getObject("Loose").GeometryCount, 0)

    def test_construction_flag_is_honoured(self):
        self.create("Constr", plane="XY")
        geometry = [dict(spec) for spec in RECTANGLE_GEOMETRY]
        geometry[3]["construction"] = True

        envelope = self.add("Constr", geometry, RECTANGLE_CONSTRAINTS)

        self.assertEqual(envelope["status"], "OK")
        sketch = self.document().getObject("Constr")
        self.assertTrue(sketch.getConstruction(3))
        self.assertFalse(sketch.getConstruction(0))

    def test_malformed_geometry_specs_are_rejected_pre_bracket(self):
        self.create("Reject", plane="XY")
        sketch = self.document().getObject("Reject")
        for geometry in (
            [{"kind": "spiral", "start": [0, 0], "end": [1, 1]}],
            [{"kind": "line_segment", "start": [0, 0]}],
            [{"kind": "line_segment", "start": [0, 0], "end": [0, 0]}],
            [{"kind": "circle", "center": [0, 0], "radius": mm(0.0)}],
            [{"kind": "circle", "center": [0, 0], "radius": {"value": 5.0, "unit": "deg"}}],
            [{"kind": "line_segment", "start": "0,0", "end": [1, 1]}],
        ):
            with self.subTest(geometry=geometry):
                self.assert_rejected_pre_bracket(
                    lambda: sketch.GeometryCount, self.add, "Reject", geometry
                )

    def test_unknown_and_non_sketch_targets_are_rejected(self):
        self.add_plate()
        document = self.document()
        for name in ("Nope", "Plate"):
            with self.subTest(target=name):
                self.assert_rejected_pre_bracket(
                    lambda: len(document.Objects), self.add, name, [line([0, 0], [1, 0])]
                )

    def test_an_empty_geometry_list_is_rejected_pre_bracket(self):
        self.create("Empty", plane="XY")
        with self.assertRaises(ValidationError):
            self.add("Empty", [])

    def test_a_rolled_back_add_reports_no_geo_ids_and_no_constraint_ids(self):
        # The rollback removes the geometry, so the mid-transaction ids name nothing a caller can
        # address; reporting them would hand out dangling references.
        self.create("Loose", plane="XY")

        envelope = self.add(
            "Loose", [line([0, 0], [10, 0])], [{"type": "Horizontal", "first": 0}]
        )

        self.assertEqual(envelope["status"], "SPEC_FAILED")
        self.assertTrue(envelope["structured_content"]["mutation"]["rolled_back"])
        self.assertEqual(envelope["structured_content"]["geo_ids"], [])
        self.assertEqual(envelope["structured_content"]["constraint_ids"], [])
        self.assertEqual(self.document().getObject("Loose").GeometryCount, 0)


class NonFiniteAndUnitGuardTest(_SketchFixture):
    """NaN/inf and wrong-dimension units are rejected before the bracket opens.

    NaN defeats every ordering guard — ``nan <= 0.0`` and ``nan == nan`` are both false — so a NaN
    radius would slip past the zero-radius check and a NaN endpoint past the zero-length check.
    """

    def setUp(self):
        super().setUp()
        self.create("Guard", plane="XY")
        self.sketch = self.document().getObject("Guard")

    def test_a_non_finite_quantity_value_is_rejected(self):
        for magnitude in (float("nan"), float("inf"), float("-inf")):
            with self.subTest(radius=magnitude):
                self.assert_rejected_pre_bracket(
                    lambda: self.sketch.GeometryCount,
                    self.add,
                    "Guard",
                    [{"kind": "circle", "center": [0, 0], "radius": mm(magnitude)}],
                )

    def test_a_non_finite_coordinate_is_rejected(self):
        for magnitude in (float("nan"), float("inf")):
            with self.subTest(x=magnitude):
                self.assert_rejected_pre_bracket(
                    lambda: self.sketch.GeometryCount,
                    self.add,
                    "Guard",
                    [line([magnitude, 0], [10, 0])],
                )

    def test_a_non_finite_datum_value_is_rejected(self):
        self.assert_rejected_pre_bracket(
            lambda: self.sketch.ConstraintCount,
            self.add,
            "Guard",
            [line([0, 0], [10, 0])],
            [{"type": "Distance", "first": 0, "value": mm(float("nan"))}],
        )

    def test_rad_is_not_an_accepted_angle_unit(self):
        # Only deg crosses the wire; the deg-to-rad conversion happens inside the use case, so a
        # rad input would be converted a second time and silently shrink the angle by 57x.
        self.assert_rejected_pre_bracket(
            lambda: self.sketch.GeometryCount,
            self.add,
            "Guard",
            [
                {
                    "kind": "arc_of_circle",
                    "center": [0, 0],
                    "radius": mm(5.0),
                    "start_angle": {"value": 0.0, "unit": "rad"},
                    "end_angle": {"value": 1.5707963267948966, "unit": "rad"},
                }
            ],
        )

    def test_a_rad_datum_on_an_angle_constraint_is_rejected(self):
        self.assert_rejected_pre_bracket(
            lambda: self.sketch.ConstraintCount,
            self.add,
            "Guard",
            [line([0, 0], [10, 0]), line([0, 0], [7.07, 7.07])],
            [
                {
                    "type": "Angle",
                    "first": 0,
                    "second": 1,
                    "value": {"value": 0.5235987755982988, "unit": "rad"},
                }
            ],
        )


class SymmetricConstraintTest(_SketchFixture):
    """``Symmetric`` takes explicit PointPos arguments; it never defaults them to 1."""

    def test_symmetry_about_the_vertical_axis_pins_a_line(self):
        # A horizontal line whose endpoints are symmetric about the V axis (geo -2) is centred in
        # X; its length and its height above the H axis then leave DoF 0.
        self.create("Sym", plane="XY")

        envelope = self.add(
            "Sym",
            [line([-5, 3], [5, 3])],
            [
                {
                    "type": "Symmetric",
                    "first": 0,
                    "first_pos": 1,
                    "second": 0,
                    "second_pos": 2,
                    "third": -2,
                },
                {"type": "Distance", "first": 0, "value": mm(10.0)},
                distance_y(-1, 1, 0, 1, 3.0),
            ],
        )

        self.assert_fully_constrained(envelope)
        sketch = self.document().getObject("Sym")
        start, end = sketch.Geometry[0].StartPoint, sketch.Geometry[0].EndPoint
        # Symmetric about x=0 means the midpoint sits on the V axis and the span is the 10 mm
        # Distance: the endpoints are -5 and +5.
        self.assertAlmostEqual((start.x + end.x) / 2.0, 0.0, places=6)
        self.assertAlmostEqual(abs(end.x - start.x), 10.0, places=6)

    def test_point_symmetry_takes_an_optional_third_pos(self):
        # third=-1 with third_pos=1 is the sketch root point, so the line is symmetric about the
        # origin rather than about a line.
        self.create("Sym", plane="XY")

        envelope = self.add(
            "Sym",
            [line([-5, 0], [5, 0])],
            [
                {
                    "type": "Symmetric",
                    "first": 0,
                    "first_pos": 1,
                    "second": 0,
                    "second_pos": 2,
                    "third": ORIGIN_GEO,
                    "third_pos": ORIGIN_POS,
                },
                {"type": "Horizontal", "first": 0},
                {"type": "Distance", "first": 0, "value": mm(10.0)},
            ],
        )

        self.assert_fully_constrained(envelope)
        sketch = self.document().getObject("Sym")
        start, end = sketch.Geometry[0].StartPoint, sketch.Geometry[0].EndPoint
        self.assertAlmostEqual((start.x + end.x) / 2.0, 0.0, places=6)
        self.assertAlmostEqual((start.y + end.y) / 2.0, 0.0, places=6)

    def test_symmetric_without_explicit_point_positions_is_rejected(self):
        self.create("Sym", plane="XY")
        self.add(
            "Sym",
            [line([-5, 3], [5, 3])],
            [
                {
                    "type": "Symmetric",
                    "first": 0,
                    "first_pos": 1,
                    "second": 0,
                    "second_pos": 2,
                    "third": -2,
                },
                {"type": "Distance", "first": 0, "value": mm(10.0)},
                distance_y(-1, 1, 0, 1, 3.0),
            ],
        )
        sketch = self.document().getObject("Sym")
        for spec in (
            {"type": "Symmetric", "first": 0, "second": 0, "third": -2},
            {"type": "Symmetric", "first": 0, "first_pos": 1, "second": 0, "third": -2},
            {"type": "Symmetric", "first": 0, "first_pos": 1, "second": 0, "second_pos": 2},
        ):
            with self.subTest(constraint=spec):
                self.assert_rejected_pre_bracket(
                    lambda: sketch.ConstraintCount,
                    sketches.sketch_add_constraint,
                    self.registry,
                    doc=self.handle,
                    sketch="Sym",
                    constraints=[spec],
                )


class AddConstraintTest(_SketchFixture):
    def _rectangle_without_dimensions(self, name="Rect"):
        """A rectangle pinned in shape and position but not yet dimensioned (DoF 2)."""
        self.create(name, plane="XY")
        document = self.document()
        sketch = document.getObject(name)
        import Part

        for spec in RECTANGLE_GEOMETRY:
            sketch.addGeometry(
                Part.LineSegment(
                    App.Vector(spec["start"][0], spec["start"][1], 0),
                    App.Vector(spec["end"][0], spec["end"][1], 0),
                ),
                False,
            )
        import Sketcher

        for args in (
            ("Coincident", 0, 2, 1, 1),
            ("Coincident", 1, 2, 2, 1),
            ("Coincident", 2, 2, 3, 1),
            ("Coincident", 3, 2, 0, 1),
            ("Horizontal", 0),
            ("Horizontal", 2),
            ("Vertical", 1),
            ("Vertical", 3),
            ("Coincident", 0, 1, -1, 1),
        ):
            sketch.addConstraint(Sketcher.Constraint(*args))
        document.recompute()
        return sketch

    def test_constraints_that_reach_zero_dof_return_one_based_ids(self):
        # The fixture adds 9 constraints (4 Coincident corners, 2 Horizontal, 2 Vertical, 1
        # Coincident to the origin), so the two this call adds are solver ids 10 and 11. Literal,
        # not derived: this test is what pins the 1-based convention, so a 0-based tool would
        # return [9, 10] and must fail here.
        self._rectangle_without_dimensions()

        envelope = sketches.sketch_add_constraint(
            self.registry,
            doc=self.handle,
            sketch="Rect",
            constraints=[distance_x(0, 1, 0, 2, 16.0), distance_y(1, 1, 1, 2, 8.0)],
        )

        self.assert_fully_constrained(envelope)
        self.assertEqual(envelope["structured_content"]["constraint_ids"], [10, 11])

    def test_a_named_constraint_lands_on_the_id_the_tool_reports(self):
        self._rectangle_without_dimensions()

        envelope = sketches.sketch_add_constraint(
            self.registry,
            doc=self.handle,
            sketch="Rect",
            constraints=[
                dict(distance_x(0, 1, 0, 2, 16.0), name="Width"),
                dict(distance_y(1, 1, 1, 2, 8.0), name="Height"),
            ],
        )

        # Same fixture: 9 existing constraints, so Width lands on solver id 10 and Height on 11.
        self.assertEqual(envelope["status"], "OK")
        self.assertEqual(envelope["structured_content"]["constraint_ids"], [10, 11])
        sketch = self.document().getObject("Rect")
        self.assertEqual(sketch.Constraints[9].Name, "Width")
        self.assertEqual(sketch.Constraints[10].Name, "Height")

    def test_a_conflicting_set_rolls_back_with_named_diagnostics(self):
        self._rectangle_without_dimensions()

        envelope = sketches.sketch_add_constraint(
            self.registry,
            doc=self.handle,
            sketch="Rect",
            constraints=[
                dict(distance_x(0, 1, 0, 2, 16.0), name="Width"),
                dict(distance_y(1, 1, 1, 2, 8.0), name="Height"),
                dict(distance_x(0, 1, 0, 2, 20.0), name="Conflict"),
            ],
        )

        # A conflicting sketch fails FreeCAD's own recompute, so the bracket classes it
        # RECOMPUTE_ERROR rather than SPEC_FAILED; both are non-OK and both roll back.
        self.assertIn(envelope["status"], ("SPEC_FAILED", "RECOMPUTE_ERROR"))
        block = envelope["structured_content"]["mutation"]
        self.assertTrue(block["rolled_back"])
        self.assertIn("Rect", block["post_verify"]["explanation"])
        self.assertEqual(self.document().getObject("Rect").ConstraintCount, 9)

    def test_the_conflicting_ids_are_reported_as_named_one_based_refs(self):
        # Read the diagnostics off a live conflicting sketch: the rollback removes them from the
        # committed document, so the refs are graded on the state the solver actually reached.
        sketch = self._rectangle_without_dimensions()
        import Sketcher

        for args, name in (
            (("DistanceX", 0, 1, 0, 2, 16.0), "Width"),
            (("DistanceX", 0, 1, 0, 2, 20.0), "Conflict"),
        ):
            index = sketch.addConstraint(Sketcher.Constraint(*args))
            sketch.renameConstraint(index, name)
        self.document().recompute()

        from freecad_buddy.usecases import verify

        refs = verify.constraint_refs(sketch, list(sketch.ConflictingConstraints))

        # The fixture leaves 9 constraints, so Width is solver id 10 and Conflict is 11. Both are
        # DistanceX on the same two points, so both are named in the conflict. Stated as literals
        # rather than read back through Constraints[ref["id"] - 1], which is the formula
        # constraint_refs itself applies and so could not disagree with its own output.
        self.assertEqual(
            refs,
            [
                {"id": 10, "name": "Width", "type": "DistanceX"},
                {"id": 11, "name": "Conflict", "type": "DistanceX"},
            ],
        )

    def test_a_redundant_constraint_commits_and_warns(self):
        self._rectangle_without_dimensions()

        envelope = sketches.sketch_add_constraint(
            self.registry,
            doc=self.handle,
            sketch="Rect",
            constraints=[
                distance_x(0, 1, 0, 2, 16.0),
                distance_y(1, 1, 1, 2, 8.0),
                {"type": "Horizontal", "first": 0},
            ],
        )

        self.assertEqual(envelope["status"], "OK")
        state = self.state(envelope)
        self.assertTrue(state["fully_constrained"])
        self.assertTrue(state["redundant"] or state["partially_redundant"])

    def test_bad_arity_is_rejected_before_the_transaction_opens(self):
        sketch = self._rectangle_without_dimensions()
        for constraint in (
            {"type": "Radius", "first": 0, "second": 1},
            {"type": "Coincident", "first": 0, "second": 1},
            {"type": "Coincident", "first": 0, "first_pos": 2, "second": 1},
            {"type": "Equal", "first": 0, "second": 1, "value": mm(5.0)},
            {"type": "Horizontal", "first": 0, "second": 1},
            {"type": "Distance", "first": 0},
            {"type": "NotAConstraint", "first": 0},
        ):
            with self.subTest(constraint=constraint):
                self.assert_rejected_pre_bracket(
                    lambda: sketch.ConstraintCount,
                    sketches.sketch_add_constraint,
                    self.registry,
                    doc=self.handle,
                    sketch="Rect",
                    constraints=[constraint],
                )

    def test_a_geo_id_outside_the_sketch_is_rejected_but_the_axes_are_not(self):
        sketch = self._rectangle_without_dimensions()

        self.assert_rejected_pre_bracket(
            lambda: sketch.ConstraintCount,
            sketches.sketch_add_constraint,
            self.registry,
            doc=self.handle,
            sketch="Rect",
            constraints=[{"type": "Horizontal", "first": 99}],
        )

        # -1 (HAxis / RootPoint) and -2 (VAxis) are legal geo ids, not out-of-range indices.
        for axis in (-1, -2):
            args = sketches._constraint_args({"type": "Horizontal", "first": axis}, 0, sketch)
            self.assertEqual(args, ("Horizontal", axis))

    def test_a_bad_point_pos_is_rejected(self):
        sketch = self._rectangle_without_dimensions()

        self.assert_rejected_pre_bracket(
            lambda: sketch.ConstraintCount,
            sketches.sketch_add_constraint,
            self.registry,
            doc=self.handle,
            sketch="Rect",
            constraints=[coincident(0, 7, 1, 1)],
        )

    def test_a_non_driving_dimensional_constraint_does_not_constrain(self):
        self._rectangle_without_dimensions()

        envelope = sketches.sketch_add_constraint(
            self.registry,
            doc=self.handle,
            sketch="Rect",
            constraints=[
                distance_x(0, 1, 0, 2, 16.0),
                distance_y(1, 1, 1, 2, 8.0),
                dict(distance_x(0, 1, 0, 2, 99.0), driving=False),
            ],
        )

        # 9 fixture constraints + these 3 => solver ids 10, 11, 12; the non-driving one is 12.
        self.assertEqual(envelope["status"], "OK")
        self.assertEqual(envelope["structured_content"]["constraint_ids"], [10, 11, 12])
        sketch = self.document().getObject("Rect")
        self.assertFalse(sketch.Constraints[11].Driving)
        self.assertTrue(sketch.Constraints[9].Driving)


# RECTANGLE_CONSTRAINTS in order: ids 1-4 the Coincident corners, 5-6 Horizontal, 7-8 Vertical,
# 9 the Coincident origin pin, 10 DistanceX, 11 DistanceY. The dimensioned fixture below names
# the DistanceX "Width", so these are the 1-based solver ids every SetDatum test addresses.
WIDTH_ID = 10
HEIGHT_ID = 11
FIRST_HORIZONTAL_ID = 5


class SetDatumTest(_SketchFixture):
    def _dimensioned_rectangle(self):
        self.create("Rect", plane="XY")
        envelope = self.add(
            "Rect",
            RECTANGLE_GEOMETRY,
            [
                dict(spec, name="Width") if spec.get("type") == "DistanceX" else spec
                for spec in RECTANGLE_CONSTRAINTS
            ],
        )
        self.assertEqual(envelope["status"], "OK")
        self.assertEqual(
            envelope["structured_content"]["constraint_ids"], list(range(1, HEIGHT_ID + 1))
        )

    def test_a_length_datum_is_applied_by_one_based_id(self):
        self._dimensioned_rectangle()

        envelope = sketches.sketch_set_datum(
            self.registry, doc=self.handle, sketch="Rect", constraint=WIDTH_ID, value=mm(24.0)
        )

        self.assert_fully_constrained(envelope)
        sketch = self.document().getObject("Rect")
        self.assertEqual(sketch.Constraints[WIDTH_ID - 1].Name, "Width")
        self.assertAlmostEqual(sketch.Constraints[WIDTH_ID - 1].Value, 24.0, places=9)
        self.assertAlmostEqual(
            sketch.Geometry[0].StartPoint.distanceToPoint(sketch.Geometry[0].EndPoint),
            24.0,
            places=5,
        )

    def test_a_datum_can_be_named_by_constraint_name(self):
        self._dimensioned_rectangle()

        envelope = sketches.sketch_set_datum(
            self.registry, doc=self.handle, sketch="Rect", constraint="Width", value=mm(20.0)
        )

        self.assertEqual(envelope["status"], "OK")
        sketch = self.document().getObject("Rect")
        self.assertAlmostEqual(
            sketch.Geometry[0].StartPoint.distanceToPoint(sketch.Geometry[0].EndPoint),
            20.0,
            places=5,
        )

    def test_an_angle_datum_in_degrees_is_converted_to_radians(self):
        # Two segments sharing a start point, pinned at the origin, angle-dimensioned. The wire
        # unit is deg; the FreeCAD API reads a bare float angle as RADIANS, so 45 sent raw would
        # store 45 rad (a 2578-degree error) — the stored value must be pi/4.
        self.create("Wedge", plane="XY")
        envelope = self.add(
            "Wedge",
            [line([0, 0], [10, 0]), line([0, 0], [7.07, 7.07])],
            [
                coincident(0, 1, 1, 1),
                coincident(0, 1, ORIGIN_GEO, ORIGIN_POS),
                {"type": "Horizontal", "first": 0},
                {"type": "Distance", "first": 0, "value": mm(10.0)},
                {"type": "Distance", "first": 1, "value": mm(10.0)},
                dict(
                    {"type": "Angle", "first": 0, "second": 1, "value": deg(30.0)}, name="Wedge"
                ),
            ],
        )
        self.assert_fully_constrained(envelope)

        sketches.sketch_set_datum(
            self.registry, doc=self.handle, sketch="Wedge", constraint="Wedge", value=deg(45.0)
        )

        sketch = self.document().getObject("Wedge")
        stored = sketch.Constraints[
            [c.Name for c in sketch.Constraints].index("Wedge")
        ].Value
        self.assertAlmostEqual(stored, math.pi / 4.0, places=9)
        second = sketch.Geometry[1]
        measured = math.degrees(
            math.atan2(
                second.EndPoint.y - second.StartPoint.y,
                second.EndPoint.x - second.StartPoint.x,
            )
        )
        self.assertAlmostEqual(abs(measured), 45.0, places=4)

    def test_a_deg_value_on_a_length_constraint_is_rejected(self):
        self._dimensioned_rectangle()
        sketch = self.document().getObject("Rect")

        self.assert_rejected_pre_bracket(
            lambda: sketch.Constraints[WIDTH_ID - 1].Value,
            sketches.sketch_set_datum,
            self.registry,
            doc=self.handle,
            sketch="Rect",
            constraint=WIDTH_ID,
            value=deg(30.0),
        )

        self.assertAlmostEqual(sketch.Constraints[WIDTH_ID - 1].Value, 16.0, places=9)

    def test_a_non_dimensional_target_is_rejected(self):
        self._dimensioned_rectangle()
        sketch = self.document().getObject("Rect")
        self.assertEqual(sketch.Constraints[FIRST_HORIZONTAL_ID - 1].Type, "Horizontal")

        self.assert_rejected_pre_bracket(
            lambda: sketch.ConstraintCount,
            sketches.sketch_set_datum,
            self.registry,
            doc=self.handle,
            sketch="Rect",
            constraint=FIRST_HORIZONTAL_ID,
            value=mm(5.0),
        )

    def test_an_out_of_range_or_unknown_constraint_is_rejected(self):
        self._dimensioned_rectangle()
        sketch = self.document().getObject("Rect")
        for reference in (0, 999, "NoSuchName"):
            with self.subTest(constraint=reference):
                self.assert_rejected_pre_bracket(
                    lambda: sketch.Constraints[WIDTH_ID - 1].Value,
                    sketches.sketch_set_datum,
                    self.registry,
                    doc=self.handle,
                    sketch="Rect",
                    constraint=reference,
                    value=mm(5.0),
                )

    def test_a_missing_value_is_rejected_pre_bracket(self):
        self._dimensioned_rectangle()
        with self.assertRaises(ValidationError):
            sketches.sketch_set_datum(
                self.registry, doc=self.handle, sketch="Rect", constraint=1, value=None
            )


class RemoveTest(_SketchFixture):
    def _dimensioned_rectangle(self):
        self.create("Rect", plane="XY")
        envelope = self.add("Rect", RECTANGLE_GEOMETRY, RECTANGLE_CONSTRAINTS)
        self.assertEqual(envelope["status"], "OK")

    def test_removing_geometry_that_leaves_the_sketch_loose_rolls_back(self):
        self._dimensioned_rectangle()

        envelope = sketches.sketch_remove_geometry(
            self.registry, doc=self.handle, sketch="Rect", geo_ids=[2]
        )

        self.assertEqual(envelope["status"], "SPEC_FAILED")
        self.assertTrue(envelope["structured_content"]["mutation"]["rolled_back"])
        self.assertEqual(self.document().getObject("Rect").GeometryCount, 4)

    def test_removing_every_geometry_leaves_an_empty_constrained_sketch(self):
        self._dimensioned_rectangle()

        envelope = sketches.sketch_remove_geometry(
            self.registry, doc=self.handle, sketch="Rect", geo_ids=[0, 1, 2, 3]
        )

        self.assert_fully_constrained(envelope)
        self.assertEqual(self.state(envelope)["geometry_count"], 0)
        self.assertEqual(self.state(envelope)["constraint_count"], 0)

    def test_removing_a_geo_id_outside_the_sketch_is_rejected(self):
        self._dimensioned_rectangle()
        sketch = self.document().getObject("Rect")

        self.assert_rejected_pre_bracket(
            lambda: sketch.GeometryCount,
            sketches.sketch_remove_geometry,
            self.registry,
            doc=self.handle,
            sketch="Rect",
            geo_ids=[9],
        )

        self.assertEqual(sketch.GeometryCount, 4)

    def test_removing_a_dimension_leaves_the_sketch_loose_and_rolls_back(self):
        # RECTANGLE_CONSTRAINTS puts the DistanceX at solver id 10 (see the SetDatum block above).
        self._dimensioned_rectangle()
        sketch = self.document().getObject("Rect")
        self.assertEqual(sketch.Constraints[WIDTH_ID - 1].Type, "DistanceX")

        envelope = sketches.sketch_remove_constraint(
            self.registry, doc=self.handle, sketch="Rect", constraints=[WIDTH_ID]
        )

        self.assertEqual(envelope["status"], "SPEC_FAILED")
        self.assertEqual(self.document().getObject("Rect").ConstraintCount, HEIGHT_ID)

    def test_removing_a_redundant_constraint_commits(self):
        self._dimensioned_rectangle()
        added = sketches.sketch_add_constraint(
            self.registry,
            doc=self.handle,
            sketch="Rect",
            constraints=[dict({"type": "Horizontal", "first": 0}, name="Extra")],
        )
        self.assertEqual(added["status"], "OK")

        envelope = sketches.sketch_remove_constraint(
            self.registry, doc=self.handle, sketch="Rect", constraints=["Extra"]
        )

        self.assert_fully_constrained(envelope)
        self.assertEqual(self.state(envelope)["redundant"], [])

    def test_removing_an_unknown_constraint_is_rejected(self):
        self._dimensioned_rectangle()
        sketch = self.document().getObject("Rect")
        for reference in (0, 999, "Nope"):
            with self.subTest(constraint=reference):
                self.assert_rejected_pre_bracket(
                    lambda: sketch.ConstraintCount,
                    sketches.sketch_remove_constraint,
                    self.registry,
                    doc=self.handle,
                    sketch="Rect",
                    constraints=[reference],
                )

    def test_empty_removal_lists_are_rejected_pre_bracket(self):
        self._dimensioned_rectangle()
        with self.assertRaises(ValidationError):
            sketches.sketch_remove_geometry(
                self.registry, doc=self.handle, sketch="Rect", geo_ids=[]
            )
        with self.assertRaises(ValidationError):
            sketches.sketch_remove_constraint(
                self.registry, doc=self.handle, sketch="Rect", constraints=[]
            )


class ToggleConstructionTest(_SketchFixture):
    def test_toggling_construction_commits_and_flips_the_flag(self):
        self.create("Rect", plane="XY")
        self.add("Rect", RECTANGLE_GEOMETRY, RECTANGLE_CONSTRAINTS)

        envelope = sketches.sketch_toggle_construction(
            self.registry, doc=self.handle, sketch="Rect", geo_ids=[3]
        )

        self.assertEqual(envelope["status"], "OK")
        sketch = self.document().getObject("Rect")
        self.assertTrue(sketch.getConstruction(3))
        self.assertFalse(sketch.getConstruction(0))

    def test_toggling_an_unknown_geo_id_is_rejected(self):
        self.create("Rect", plane="XY")
        self.add("Rect", RECTANGLE_GEOMETRY, RECTANGLE_CONSTRAINTS)
        sketch = self.document().getObject("Rect")

        self.assert_rejected_pre_bracket(
            lambda: [sketch.getConstruction(i) for i in range(sketch.GeometryCount)],
            sketches.sketch_toggle_construction,
            self.registry,
            doc=self.handle,
            sketch="Rect",
            geo_ids=[9],
        )

    def test_a_geo_id_listed_twice_is_rejected_because_a_double_toggle_is_a_no_op(self):
        self.create("Rect", plane="XY")
        self.add("Rect", RECTANGLE_GEOMETRY, RECTANGLE_CONSTRAINTS)
        sketch = self.document().getObject("Rect")

        self.assert_rejected_pre_bracket(
            lambda: [sketch.getConstruction(i) for i in range(sketch.GeometryCount)],
            sketches.sketch_toggle_construction,
            self.registry,
            doc=self.handle,
            sketch="Rect",
            geo_ids=[1, 1],
        )

        # A silently accepted double toggle would have left every flag at its original False.
        self.assertFalse(sketch.getConstruction(1))


class ExternalGeometryTest(_SketchFixture):
    def test_projecting_a_model_edge_grows_the_external_geometry_list(self):
        self.add_plate()
        selector = {"kind": "mapped_name", "object": "Plate", "mapped_name": "Face6"}
        self.create("Ext", plane=None, face=selector)

        envelope = sketches.sketch_add_external_geometry(
            self.registry,
            doc=self.handle,
            sketch="Ext",
            edge={"kind": "mapped_name", "object": "Plate", "mapped_name": "Edge1"},
        )

        self.assertEqual(
            envelope["status"],
            "OK",
            envelope["structured_content"]["mutation"]["post_verify"]["explanation"],
        )
        sketch = self.document().getObject("Ext")
        self.assertEqual(len(sketch.ExternalGeometry), 1)
        self.assertEqual(sketch.ExternalGeometry[0][0].Name, "Plate")

    def test_an_unresolvable_selector_is_rejected(self):
        self.add_plate()
        self.create("Ext", plane="XY")
        sketch = self.document().getObject("Ext")

        self.assert_rejected_pre_bracket(
            lambda: len(sketch.ExternalGeometry),
            sketches.sketch_add_external_geometry,
            self.registry,
            doc=self.handle,
            sketch="Ext",
            edge={"kind": "mapped_name", "object": "Plate", "mapped_name": "Edge999"},
        )

        self.assertEqual(len(sketch.ExternalGeometry), 0)

    def test_a_missing_edge_selector_is_rejected_pre_bracket(self):
        self.create("Ext", plane="XY")
        with self.assertRaises(ValidationError):
            sketches.sketch_add_external_geometry(
                self.registry, doc=self.handle, sketch="Ext", edge=None
            )

    def _plate_with_one_projected_edge(self):
        """A face-attached sketch carrying exactly one projected model edge, addressable as -3."""
        self.add_plate()
        self.create(
            "Ext",
            plane=None,
            face={"kind": "mapped_name", "object": "Plate", "mapped_name": "Face6"},
        )
        envelope = sketches.sketch_add_external_geometry(
            self.registry,
            doc=self.handle,
            sketch="Ext",
            edge={"kind": "mapped_name", "object": "Plate", "mapped_name": "Edge1"},
        )
        self.assertEqual(envelope["status"], "OK")
        self.assertEqual(len(self.document().getObject("Ext").ExternalGeometry), 1)

    def test_geometry_can_be_constrained_to_the_first_projected_external_edge(self):
        # Sketcher GeoEnum counts external geometry down from -3, so the single projected edge is
        # geo id -3. A point coincident with its start point is pinned, so the sketch reaches
        # DoF 0 only if the constraint actually bound to the external edge.
        self._plate_with_one_projected_edge()

        envelope = self.add(
            "Ext",
            [{"kind": "point", "center": [1.0, 1.0]}],
            [{"type": "Coincident", "first": 0, "first_pos": 1, "second": -3, "second_pos": 1}],
        )

        self.assert_fully_constrained(envelope)
        self.assertEqual(envelope["structured_content"]["geo_ids"], [0])

    def test_an_external_geo_id_deeper_than_the_projection_list_is_rejected(self):
        # Only one edge is projected, so -3 exists and -4 names a projection that was never made.
        self._plate_with_one_projected_edge()
        sketch = self.document().getObject("Ext")

        self.assert_rejected_pre_bracket(
            lambda: sketch.GeometryCount,
            self.add,
            "Ext",
            [{"kind": "point", "center": [1.0, 1.0]}],
            [{"type": "Coincident", "first": 0, "first_pos": 1, "second": -4, "second_pos": 1}],
        )


class RegistryRebindTest(_SketchFixture):
    def _force_snapshot_restore(self):
        """Drive a failing sketch op down the snapshot-restore path and return its envelope.

        Abort restores this pattern cleanly on FreeCAD 1.1.x, so the escalation is forced by
        making the post-abort re-hash disagree once — the same state ``run_mutation`` reaches
        when undo fails to restore the pre-transaction boundary (FreeCAD #6031).
        """
        self.create("Keep", plane="XY")

        def op(document):
            document.addObject("Sketcher::SketchObject", "Ghost")
            raise RuntimeError("planted rollback-boundary failure")

        real_equal = transaction.fingerprints_equal
        calls = []

        def once_unequal(left, right):
            calls.append(1)
            return False if len(calls) == 1 else real_equal(left, right)

        transaction.fingerprints_equal = once_unequal
        try:
            return sketches._sketch_mutation(
                self.registry, self.handle, "Keep", "forced restore", "test", {}, op
            )
        finally:
            transaction.fingerprints_equal = real_equal

    def test_a_forced_snapshot_restore_rebinds_the_registry_to_the_live_document(self):
        original = self.document()

        envelope = self._force_snapshot_restore()

        block = envelope["structured_content"]["mutation"]
        self.assertTrue(block["rolled_back"])
        self.assertEqual(block["rollback_proven"], "rolled_back_via_snapshot")

        rebound = self.document()
        self.assertIsNot(rebound, original)
        self.assertIn(rebound, App.listDocuments().values())
        self.assertIsNotNone(rebound.getObject("Keep"))
        self.assertIsNone(rebound.getObject("Ghost"))

    def test_the_next_tool_call_on_the_rebound_handle_succeeds(self):
        self._force_snapshot_restore()

        envelope = self.add("Keep", RECTANGLE_GEOMETRY, RECTANGLE_CONSTRAINTS)

        self.assert_fully_constrained(envelope)

    def test_rebind_replaces_the_object_a_handle_holds(self):
        other = App.newDocument("rebind_target")
        self.registry.rebind(self.handle, other)
        self.assertIs(self.document(), other)

    def test_rebind_rejects_an_unknown_handle(self):
        with self.assertRaises(ValidationError):
            self.registry.rebind("fcb-doc:missing", self.document())


class BodyAdoptionTest(_SketchFixture):
    """A profile sketch belongs inside the Body that consumes it.

    Without adoption the sketch sits at document root and PartDesign reports the pad's profile
    link as out of the allowed scope, because those link properties are LinkScope::Child.
    """

    def geometry_count(self):
        sketch = self.document().getObject("Prof")
        return None if sketch is None else int(sketch.GeometryCount)

    def make_body(self, name="Bracket"):
        document = self.document()
        body = document.addObject("PartDesign::Body", name)
        document.recompute()
        return body

    def test_a_sketch_created_with_a_body_is_adopted_into_it(self):
        body = self.make_body()

        envelope = sketches.sketch_create(
            self.registry, doc=self.handle, name="Prof", plane="XY", body="Bracket"
        )

        self.assertEqual(envelope["status"], "OK", envelope.get("detail"))
        self.assertIn("Prof", [obj.Name for obj in body.Group])

    def test_a_sketch_created_without_a_body_stays_at_document_root(self):
        body = self.make_body()

        envelope = sketches.sketch_create(
            self.registry, doc=self.handle, name="Prof", plane="XY"
        )

        self.assertEqual(envelope["status"], "OK", envelope.get("detail"))
        self.assertNotIn("Prof", [obj.Name for obj in body.Group])

    def test_a_face_attached_sketch_is_adopted_too(self):
        # The two creation branches return separately, so a fix applied to the base-plane path
        # alone would leave this one unadopted.
        body = self.make_body()
        document = self.document()
        document.addObject("Part::Box", "Box")
        document.recompute()

        envelope = sketches.sketch_create(
            self.registry,
            doc=self.handle,
            name="Prof",
            face={"kind": "mapped_name", "object": "Box", "mapped_name": "Face1"},
            body="Bracket",
        )

        self.assertEqual(envelope["status"], "OK", envelope.get("detail"))
        self.assertIn("Prof", [obj.Name for obj in body.Group])

    def test_adopting_a_sketch_leaves_the_body_tip_unset(self):
        """Adoption must place the sketch in the Body without promoting it to the Tip.

        ``Body::addObject`` advances ``Tip`` only when ``isSolidFeature`` holds, and that
        requires a ``PartDesign::Feature`` (``Body.cpp:176-194``), which a sketch is not. The
        adoption is asserted alongside it: ``Tip is None`` holds even when nothing was adopted
        at all, so on its own it would pass against a completely broken adoption path.
        """
        body = self.make_body()

        sketches.sketch_create(
            self.registry, doc=self.handle, name="Prof", plane="XY", body="Bracket"
        )

        self.assertIn("Prof", [obj.Name for obj in body.Group])
        self.assertIsNone(body.Tip)

    def test_an_unknown_body_is_rejected_before_the_bracket(self):
        self.assert_rejected_pre_bracket(
            self.geometry_count,
            sketches.sketch_create,
            self.registry,
            doc=self.handle,
            name="Prof",
            plane="XY",
            body="NoSuchBody",
        )

    def test_a_body_naming_a_non_body_object_is_rejected_before_the_bracket(self):
        document = self.document()
        document.addObject("Part::Box", "Box")
        document.recompute()

        self.assert_rejected_pre_bracket(
            self.geometry_count,
            sketches.sketch_create,
            self.registry,
            doc=self.handle,
            name="Prof",
            plane="XY",
            body="Box",
        )


class TangencySenseTest(_SketchFixture):
    """FreeCAD admits a datum on Tangent and Perpendicular, where it selects a sense.

    SketchObjectConstraints.cpp:194-197 accepts those two alongside the dimensional types, and
    the value chooses the tangency: 0 autodecide, +Pi/2 external, -Pi/2 internal.
    """

    def geometry_count(self):
        sketch = self.document().getObject("Circles")
        return None if sketch is None else int(sketch.GeometryCount)

    def tangent_sketch(self):
        """A fully constrained sketch with a Tangent between two circles; returns its 1-based id.

        The circles are pinned as well as made tangent. ``post_verify`` requires every committed
        sketch to be fully constrained, and a Tangent alone leaves five degrees of freedom, so an
        unpinned pair would fail the commit for a reason unrelated to the datum under test.
        """
        import Part
        import Sketcher

        self.create("Circles", plane="XY")
        document = self.document()
        sketch = document.getObject("Circles")
        sketch.addGeometry(
            Part.Circle(App.Vector(0, 0, 0), App.Vector(0, 0, 1), 5.0), False
        )
        sketch.addGeometry(
            Part.Circle(App.Vector(12, 0, 0), App.Vector(0, 0, 1), 4.0), False
        )
        index = sketch.addConstraint(Sketcher.Constraint("Tangent", 0, 1))
        sketch.addConstraint(Sketcher.Constraint("Coincident", 0, 3, -1, 1))
        sketch.addConstraint(Sketcher.Constraint("Radius", 0, 5.0))
        sketch.addConstraint(Sketcher.Constraint("Radius", 1, 4.0))
        sketch.addConstraint(Sketcher.Constraint("PointOnObject", 1, 3, -1))
        document.recompute()
        self.assertEqual(sketch.DoF, 0, "the fixture must be fully constrained")
        return index + 1

    def test_each_sense_commits_on_a_tangent_constraint(self):
        # All three are asserted, not just the first: a mapping that sent every sense to the
        # same radian value would pass a single-sense test.
        for sense in ("autodecide", "external", "internal"):
            with self.subTest(sense=sense):
                constraint_id = self.tangent_sketch()

                envelope = sketches.sketch_set_datum(
                    self.registry,
                    doc=self.handle,
                    sketch="Circles",
                    constraint=constraint_id,
                    sense=sense,
                )

                self.assertEqual(envelope["status"], "OK", envelope.get("detail"))
                self.assertTrue(self.document().getObject("Circles").isValid())
                self.document().removeObject("Circles")
                self.document().recompute()

    def test_a_value_on_a_tangent_is_rejected_before_the_bracket(self):
        constraint_id = self.tangent_sketch()

        self.assert_rejected_pre_bracket(
            self.geometry_count,
            sketches.sketch_set_datum,
            self.registry,
            doc=self.handle,
            sketch="Circles",
            constraint=constraint_id,
            value=mm(5.0),
        )

    def test_a_sense_on_a_dimensional_constraint_is_rejected_before_the_bracket(self):
        self.create("Rect", plane="XY")
        self.add("Rect", RECTANGLE_GEOMETRY, RECTANGLE_CONSTRAINTS)

        self.assert_rejected_pre_bracket(
            lambda: int(self.document().getObject("Rect").GeometryCount),
            sketches.sketch_set_datum,
            self.registry,
            doc=self.handle,
            sketch="Rect",
            constraint=10,
            sense="external",
        )

    def test_neither_value_nor_sense_is_rejected(self):
        constraint_id = self.tangent_sketch()

        self.assert_rejected_pre_bracket(
            self.geometry_count,
            sketches.sketch_set_datum,
            self.registry,
            doc=self.handle,
            sketch="Circles",
            constraint=constraint_id,
        )

    def test_both_value_and_sense_is_rejected(self):
        constraint_id = self.tangent_sketch()

        self.assert_rejected_pre_bracket(
            self.geometry_count,
            sketches.sketch_set_datum,
            self.registry,
            doc=self.handle,
            sketch="Circles",
            constraint=constraint_id,
            value=mm(5.0),
            sense="external",
        )

    def test_a_dimensional_datum_still_commits_with_a_value(self):
        # Pins that widening the tool did not disturb the path that already worked.
        self.create("Rect", plane="XY")
        self.add("Rect", RECTANGLE_GEOMETRY, RECTANGLE_CONSTRAINTS)

        envelope = sketches.sketch_set_datum(
            self.registry, doc=self.handle, sketch="Rect", constraint=10, value=mm(20.0)
        )

        self.assertEqual(envelope["status"], "OK", envelope.get("detail"))


class NoTransactionLeftOpenTest(_SketchFixture):
    """AD-5 asserted behaviourally: no sketch tool leaves a transaction open on any exit path.

    ``test_sketch_contract.py`` greps the module source for ``openTransaction`` and friends, which
    a ``getattr(document, "open" + "Transaction")()`` would walk straight past. ``Document``'s
    ``HasPendingTransaction`` reads the real thing: it is True while an opened transaction holds
    changes and False once it has been committed or aborted, so a leak is directly observable.
    """

    def assert_no_pending(self, tag):
        self.assertFalse(
            self.document().HasPendingTransaction,
            f"{tag} left a transaction open holding changes",
        )

    def test_no_sketch_tool_leaves_a_transaction_open_on_its_success_path(self):
        self.create("Rect", plane="XY")
        self.assert_no_pending("sketch_create")
        self.add("Rect", RECTANGLE_GEOMETRY, RECTANGLE_CONSTRAINTS)
        self.assert_no_pending("sketch_add_geometry")

        calls = (
            (
                "sketch_add_constraint",
                lambda: sketches.sketch_add_constraint(
                    self.registry,
                    doc=self.handle,
                    sketch="Rect",
                    constraints=[{"type": "Horizontal", "first": 1}],
                ),
            ),
            (
                "sketch_set_datum",
                lambda: sketches.sketch_set_datum(
                    self.registry,
                    doc=self.handle,
                    sketch="Rect",
                    constraint=10,
                    value=mm(20.0),
                ),
            ),
            (
                "sketch_toggle_construction",
                lambda: sketches.sketch_toggle_construction(
                    self.registry, doc=self.handle, sketch="Rect", geo_ids=[0]
                ),
            ),
            (
                "sketch_remove_constraint",
                lambda: sketches.sketch_remove_constraint(
                    self.registry, doc=self.handle, sketch="Rect", constraints=[11]
                ),
            ),
        )
        for tag, call in calls:
            with self.subTest(tool=tag):
                call()
                self.assert_no_pending(tag)

    def test_a_rolled_back_op_leaves_no_transaction_open(self):
        self.create("Rect", plane="XY")
        self.add("Rect", RECTANGLE_GEOMETRY, RECTANGLE_CONSTRAINTS)

        envelope = sketches.sketch_add_constraint(
            self.registry,
            doc=self.handle,
            sketch="Rect",
            constraints=[distance_x(0, 1, 0, 2, 99.0)],
        )

        self.assertNotEqual(envelope["status"], "OK")
        self.assertTrue(envelope["structured_content"]["mutation"]["rolled_back"])
        self.assert_no_pending("a rolled-back sketch_add_constraint")

    def test_an_op_that_raised_inside_the_bracket_leaves_no_transaction_open(self):
        # The raising path is the one that would leak: the tool never reaches its own commit, so
        # only the bracket's abort closes the transaction.
        self.create("Keep", plane="XY")

        def op(document):
            document.addObject("Sketcher::SketchObject", "Ghost")
            raise RuntimeError("planted failure inside the bracket")

        envelope = sketches._sketch_mutation(
            self.registry, self.handle, "Keep", "planted", "test", {}, op
        )

        self.assertNotEqual(envelope["status"], "OK")
        self.assert_no_pending("an op that raised inside the bracket")

    def test_a_raise_after_the_snapshot_restore_still_rebinds_the_handle(self):
        """The rebind runs in a ``finally``, so it survives a raise on the way out of the bracket.

        The snapshot restore has already closed the caller's document by the time ``run_mutation``
        returns, so a rebind skipped on the exception path would leave the handle holding a deleted
        object and every later call would fail on it.
        """
        self.create("Keep", plane="XY")
        original = self.document()

        def failing_op(document):
            document.addObject("Sketcher::SketchObject", "Ghost")
            raise RuntimeError("planted rollback-boundary failure")

        real_run = transaction.run_mutation
        real_equal = transaction.fingerprints_equal
        calls = []

        def once_unequal(left, right):
            calls.append(1)
            return False if len(calls) == 1 else real_equal(left, right)

        def restore_then_break_the_caller(*args, **kwargs):
            """Drive the real restore, then return a tuple the caller's 2-way unpack rejects."""
            document, envelope = real_run(*args, **kwargs)
            return (document, envelope, "surplus")

        transaction.run_mutation = restore_then_break_the_caller
        transaction.fingerprints_equal = once_unequal
        try:
            with self.assertRaises(ValueError):
                sketches._sketch_mutation(
                    self.registry, self.handle, "Keep", "forced", "test", {}, failing_op
                )
        finally:
            transaction.run_mutation = real_run
            transaction.fingerprints_equal = real_equal

        rebound = self.document()
        self.assertIsNot(rebound, original)
        self.assertIn(rebound, App.listDocuments().values())
        self.assertIsNotNone(rebound.getObject("Keep"))
        self.assertIsNone(rebound.getObject("Ghost"))


class SketchStateTest(_SketchFixture):
    """``sketch_state`` is a block on every envelope, never a null a consumer would dereference."""

    def test_a_successful_call_reports_a_readable_state(self):
        envelope = self.create("Base", plane="XY")

        state = self.state(envelope)
        self.assertTrue(state["readable"])
        self.assertEqual(state["sketch"], "Base")
        self.assertEqual(state["geometry_count"], 0)

    def test_a_sketch_rolled_back_out_of_existence_still_reports_a_state(self):
        # The forced snapshot restore undoes the sketch's creation, so verify_sketch cannot grade
        # it. The block names the sketch it could not read rather than returning null.
        def op(document):
            document.addObject("Sketcher::SketchObject", "Ghost")
            raise RuntimeError("planted rollback-boundary failure")

        real_equal = transaction.fingerprints_equal
        calls = []

        def once_unequal(left, right):
            calls.append(1)
            return False if len(calls) == 1 else real_equal(left, right)

        transaction.fingerprints_equal = once_unequal
        try:
            envelope = sketches._sketch_mutation(
                self.registry, self.handle, "Ghost", "forced restore", "test", {}, op
            )
        finally:
            transaction.fingerprints_equal = real_equal

        self.assertTrue(envelope["structured_content"]["mutation"]["rolled_back"])
        state = self.state(envelope)
        self.assertIsNotNone(state)
        self.assertEqual(state["schema"], "fcb.sketch-state/1")
        self.assertEqual(state["sketch"], "Ghost")
        self.assertFalse(state["readable"])
        self.assertIsNone(self.document().getObject("Ghost"))


class EnvelopeShapeTest(_SketchFixture):
    def test_every_successful_call_carries_a_mutation_and_an_agreeing_sketch_state(self):
        self.create("Rect", plane="XY")
        envelope = self.add("Rect", RECTANGLE_GEOMETRY, RECTANGLE_CONSTRAINTS)

        content = envelope["structured_content"]
        self.assertIn("mutation", content)
        self.assertIn("sketch_state", content)
        self.assertEqual(
            content["sketch_state"]["fully_constrained"],
            content["mutation"]["post_verify"]["fully_constrained"],
        )
        self.assertEqual(content["sketch_state"]["sketch"], "Rect")

    def test_the_audit_params_carry_the_confirm_passthrough(self):
        recorded = {}

        class _Sink:
            def before(self, event, tool, handle, params, **kwargs):
                recorded["params"] = params

            def after(self, *args, **kwargs):
                pass

        sketches.sketch_create(
            self.registry,
            doc=self.handle,
            name="Confirmed",
            plane="XY",
            confirm={"preview_id": "p-1", "elicitation_action": "accept"},
            audit_sink=_Sink(),
        )

        self.assertEqual(recorded["params"]["confirm"]["preview_id"], "p-1")


class ReviewPatchTest(_SketchFixture):
    """Rejections and reports that a review pass found missing from the pre-bracket guards."""

    def geometry_count(self):
        sketch = self.document().getObject("Rect")
        return None if sketch is None else int(sketch.GeometryCount)

    def test_a_tangent_with_only_one_pos_is_rejected_rather_than_silently_reshaped(self):
        # first_pos alone used to be dropped, turning an endpoint tangency into an edge-to-edge
        # one — a different constraint with different DoF, applied without an error.
        self.create("Rect", plane="XY")
        self.add("Rect", RECTANGLE_GEOMETRY, RECTANGLE_CONSTRAINTS)

        for spec in (
            {"type": "Tangent", "first": 0, "first_pos": 2, "second": 1},
            {"type": "Perpendicular", "first": 0, "second": 1, "second_pos": 1},
        ):
            with self.subTest(spec=spec):
                self.assert_rejected_pre_bracket(
                    self.geometry_count,
                    sketches.sketch_add_constraint,
                    self.registry,
                    doc=self.handle,
                    sketch="Rect",
                    constraints=[spec],
                )

    def test_a_non_positive_datum_is_rejected_before_the_bracket(self):
        # setDatum refuses a non-positive Radius/Diameter/Weight
        # (SketchObjectConstraints.cpp:200-204), so the sign is caller input and must not cost a
        # snapshot and a rollback.
        self.create("Rect", plane="XY")
        self.assert_fully_constrained(self.add("Rect", [CIRCLE_AT_ORIGIN], CIRCLE_CONSTRAINTS))

        for value in (-5.0, 0.0):
            with self.subTest(value=value):
                self.assert_rejected_pre_bracket(
                    self.geometry_count,
                    sketches.sketch_add_constraint,
                    self.registry,
                    doc=self.handle,
                    sketch="Rect",
                    constraints=[circle_radius(0, value)],
                )
                self.assert_rejected_pre_bracket(
                    self.geometry_count,
                    sketches.sketch_set_datum,
                    self.registry,
                    doc=self.handle,
                    sketch="Rect",
                    constraint=1,
                    value={"value": value, "unit": "mm"},
                )

    def test_a_signed_axis_offset_still_accepts_a_negative_datum(self):
        # DistanceX/DistanceY are signed, so the positivity rule must not reach them.
        self.create("Rect", plane="XY")
        envelope = self.add(
            "Rect",
            [line([0, 0], [-16, 0])],
            [
                coincident(0, 1, ORIGIN_GEO, ORIGIN_POS),
                {"type": "Horizontal", "first": 0},
                distance_x(0, 1, 0, 2, -16.0),
            ],
        )
        self.assert_fully_constrained(envelope)

    def test_a_radius_on_a_sketch_axis_is_rejected(self):
        self.create("Rect", plane="XY")
        self.add("Rect", [CIRCLE_AT_ORIGIN], [circle_radius(0, 5.0)])

        self.assert_rejected_pre_bracket(
            self.geometry_count,
            sketches.sketch_add_constraint,
            self.registry,
            doc=self.handle,
            sketch="Rect",
            constraints=[circle_radius(-1, 5.0)],
        )

    def test_a_full_turn_arc_is_rejected_like_a_zero_span_one(self):
        self.create("Rect", plane="XY")

        self.assert_rejected_pre_bracket(
            self.geometry_count,
            sketches.sketch_add_geometry,
            self.registry,
            doc=self.handle,
            sketch="Rect",
            geometry=[
                {
                    "kind": "arc_of_circle",
                    "center": [0, 0],
                    "radius": {"value": 5.0, "unit": "mm"},
                    "start_angle": {"value": 0.0, "unit": "deg"},
                    "end_angle": {"value": 360.0, "unit": "deg"},
                }
            ],
        )

    def test_an_empty_constraint_name_is_rejected_rather_than_matching_an_unnamed_one(self):
        self.create("Rect", plane="XY")
        self.add("Rect", RECTANGLE_GEOMETRY, RECTANGLE_CONSTRAINTS)

        self.assert_rejected_pre_bracket(
            self.geometry_count,
            sketches.sketch_remove_constraint,
            self.registry,
            doc=self.handle,
            sketch="Rect",
            constraints=[""],
        )

    def test_a_name_already_on_the_sketch_is_rejected_before_the_bracket_opens(self):
        # SketchObjectPyImp.cpp:538-545 raises ValueError("Duplicate constraint not allowed") from
        # renameConstraint, which runs inside the transaction — so without a pre-bracket check the
        # caller pays a snapshot and a rollback for input the I/O matrix rejects as INVALID_INPUT.
        self.create("Rect", plane="XY")
        self.add("Rect", RECTANGLE_GEOMETRY, RECTANGLE_CONSTRAINTS)
        named = sketches.sketch_add_constraint(
            self.registry,
            doc=self.handle,
            sketch="Rect",
            constraints=[{"type": "Distance", "first": 0, "name": "width", "value": mm(16.0)}],
        )
        self.assertEqual(named["status"], "OK", named.get("detail"))

        self.assert_rejected_pre_bracket(
            self.geometry_count,
            sketches.sketch_add_constraint,
            self.registry,
            doc=self.handle,
            sketch="Rect",
            constraints=[{"type": "Distance", "first": 1, "name": "width", "value": mm(8.0)}],
        )

    def test_a_third_on_a_type_that_cannot_consume_it_is_rejected_rather_than_dropped(self):
        # Only Symmetric and the Angle/Tangent/Perpendicular via-point forms take a third
        # geometry. For the rest it was range-checked and then discarded, so the tool accepted a
        # request describing a constraint it did not build.
        self.create("Rect", plane="XY")
        self.add("Rect", RECTANGLE_GEOMETRY, RECTANGLE_CONSTRAINTS)

        for spec in (
            {"type": "Parallel", "first": 0, "second": 2, "third": 1},
            {"type": "Equal", "first": 0, "second": 2, "third": 1},
            {"type": "Radius", "first": 0, "value": mm(5.0), "third": 1},
            {"type": "Horizontal", "first": 0, "third": 1},
            {"type": "PointOnObject", "first": 0, "first_pos": 1, "second": 2, "third": 1},
        ):
            with self.subTest(constraint=spec["type"]):
                self.assert_rejected_pre_bracket(
                    self.geometry_count,
                    sketches.sketch_add_constraint,
                    self.registry,
                    doc=self.handle,
                    sketch="Rect",
                    constraints=[spec],
                )

    def test_a_second_pos_on_point_on_object_is_rejected_rather_than_dropped(self):
        # PointOnObject binds a point to a whole edge; its constructor takes no second position,
        # so a supplied one was validated and then dropped.
        self.create("Rect", plane="XY")
        self.add("Rect", RECTANGLE_GEOMETRY, RECTANGLE_CONSTRAINTS)

        self.assert_rejected_pre_bracket(
            self.geometry_count,
            sketches.sketch_add_constraint,
            self.registry,
            doc=self.handle,
            sketch="Rect",
            constraints=[
                {"type": "PointOnObject", "first": 0, "first_pos": 1, "second": 2, "second_pos": 2}
            ],
        )

    def test_a_name_repeated_within_one_request_is_rejected_before_the_bracket_opens(self):
        # The collision is between two specs in the same list, so neither is on the sketch when
        # the request is validated; only comparing the request against itself catches it.
        self.create("Rect", plane="XY")
        self.add("Rect", RECTANGLE_GEOMETRY, RECTANGLE_CONSTRAINTS)

        self.assert_rejected_pre_bracket(
            self.geometry_count,
            sketches.sketch_add_constraint,
            self.registry,
            doc=self.handle,
            sketch="Rect",
            constraints=[
                {"type": "Distance", "first": 0, "name": "span", "value": mm(16.0)},
                {"type": "Distance", "first": 1, "name": "span", "value": mm(8.0)},
            ],
        )

    def test_a_rolled_back_constraint_add_reports_no_constraint_ids(self):
        # A rollback removes the constraints, so reporting the ids held mid-transaction would name
        # constraints the caller cannot address.
        self.create("Rect", plane="XY")
        self.add("Rect", RECTANGLE_GEOMETRY, RECTANGLE_CONSTRAINTS)

        envelope = sketches.sketch_add_constraint(
            self.registry,
            doc=self.handle,
            sketch="Rect",
            constraints=[distance_x(0, 1, 0, 2, 99.0)],
        )

        self.assertNotEqual(envelope["status"], "OK")
        self.assertTrue(envelope["structured_content"]["mutation"]["rolled_back"])
        self.assertEqual(envelope["structured_content"]["constraint_ids"], [])

    def test_an_untouched_redundant_sketch_still_blocks_a_commit(self):
        # A redundant sketch is shapeless (SketchObject.cpp returns before buildShape on solve
        # code -2). The warn-only deferral is therefore scoped to sketches the op touched, which
        # post_verify step 3 grades; nothing grades an untouched one, so exempting it there would
        # let a shapeless object commit unnoticed.
        import Sketcher

        self.create("Rect", plane="XY")
        self.add("Rect", RECTANGLE_GEOMETRY, RECTANGLE_CONSTRAINTS)
        self.create("Other", plane="XY")
        self.add("Other", RECTANGLE_GEOMETRY, RECTANGLE_CONSTRAINTS)

        document = self.document()
        other = document.getObject("Other")
        other.addConstraint(Sketcher.Constraint("Horizontal", 0))
        document.recompute()
        self.assertTrue(other.RedundantConstraints)
        self.assertFalse(other.isValid())

        envelope = sketches.sketch_set_datum(
            self.registry,
            doc=self.handle,
            sketch="Rect",
            constraint=10,
            value={"value": 20.0, "unit": "mm"},
        )

        self.assertNotEqual(envelope["status"], "OK")
        explanation = envelope["structured_content"]["mutation"]["post_verify"]["explanation"]
        self.assertIn("Other", explanation)


class DatumSignRuleTest(_SketchFixture):
    """The datum sign guard must reject exactly what FreeCAD rejects, and nothing more."""

    def geometry_count(self):
        sketch = self.document().getObject("Rect")
        return None if sketch is None else int(sketch.GeometryCount)

    def test_an_angle_datum_accepts_a_negative_value(self):
        # SketchObjectConstraints.cpp:200-204 constrains the sign of Radius/Diameter/Weight and
        # the zero of Distance only; Angle carries no sign rule, and -30 deg is the reversed
        # measurement of the same angle.
        self.create("Wedge", plane="XY")
        envelope = self.add(
            "Wedge",
            [line([0, 0], [10, 0]), line([0, 0], [8, 5])],
            [
                coincident(0, 1, ORIGIN_GEO, ORIGIN_POS),
                coincident(1, 1, 0, 1),
                {"type": "Horizontal", "first": 0},
                distance_x(0, 1, 0, 2, 10.0),
                {"type": "Distance", "first": 1, "value": mm(8.0)},
                {"type": "Angle", "first": 0, "second": 1, "value": deg(-30.0)},
            ],
        )

        self.assert_fully_constrained(envelope)

    def test_a_distance_datum_accepts_a_negative_value_and_rejects_zero(self):
        # Distance is refused only at exactly zero (SketchObjectConstraints.cpp:203-204).
        self.create("Rect", plane="XY")
        self.add("Rect", RECTANGLE_GEOMETRY, RECTANGLE_CONSTRAINTS)

        self.assert_rejected_pre_bracket(
            self.geometry_count,
            sketches.sketch_add_constraint,
            self.registry,
            doc=self.handle,
            sketch="Rect",
            constraints=[{"type": "Distance", "first": 0, "value": mm(0.0)}],
        )

        # A negative Distance reaches the solver rather than being refused as caller input.
        envelope = sketches.sketch_add_constraint(
            self.registry,
            doc=self.handle,
            sketch="Rect",
            constraints=[{"type": "Distance", "first": 0, "value": mm(-4.0)}],
        )
        self.assertNotIn("must be positive", str(envelope.get("detail") or ""))


class AngleEndpointFormTest(_SketchFixture):
    """A half-given Angle position must be an error, never a silently different constraint."""

    def geometry_count(self):
        sketch = self.document().getObject("Wedge")
        return None if sketch is None else int(sketch.GeometryCount)

    def test_an_angle_with_only_one_position_is_rejected_before_the_bracket(self):
        # Angle has both an edge-to-edge and a 5-arg endpoint form
        # (ConstraintPyImp.cpp:685-693). Dropping a lone first_pos would build the edge-to-edge
        # constraint instead of the endpoint one, which has different DoF.
        self.create("Wedge", plane="XY")
        self.add(
            "Wedge",
            [line([0, 0], [10, 0]), line([0, 0], [8, 5])],
            [
                coincident(0, 1, ORIGIN_GEO, ORIGIN_POS),
                coincident(1, 1, 0, 1),
                {"type": "Horizontal", "first": 0},
                distance_x(0, 1, 0, 2, 10.0),
                {"type": "Distance", "first": 1, "value": mm(8.0)},
                {"type": "Angle", "first": 0, "second": 1, "value": deg(30.0)},
            ],
        )

        self.assert_rejected_pre_bracket(
            self.geometry_count,
            sketches.sketch_add_constraint,
            self.registry,
            doc=self.handle,
            sketch="Wedge",
            constraints=[
                {
                    "type": "Angle",
                    "first": 0,
                    "first_pos": 1,
                    "second": 1,
                    "value": deg(30.0),
                }
            ],
        )


if __name__ == "__main__":
    unittest.main()
