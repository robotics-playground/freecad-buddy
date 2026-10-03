"""In-FreeCAD tests for the ten ``feature_*`` tools (stdlib unittest).

Run via ``FreeCADCmd tests/run_tests.py``. Covers a pad, pocket, revolve, hole, fillet, chamfer,
pattern, mirror, datum and parameter edit each reaching a valid solid, the ``Midplane`` symmetric
path, the dynamically re-populated hole enumerations, the dress-up silent-drop rejection, every
pre-bracket validation, and a forced snapshot restore proving the registry was rebound.

Expected values are analytic — hand-computed prism, cylinder and Pappus volumes — never captured
from ``verify_shape`` or any tool under test.
"""

import glob
import math
import os
import unittest

import FreeCAD as App
import Part
import Sketcher

from freecad_buddy.usecases import confirm, features, fingerprint, shim, transaction
from freecad_buddy.usecases.documents import DocumentRegistry, ValidationError, temp_dir

# Snapshots live in the session workdir, not the OS temp directory (AD-25). Globbing the OS temp
# directory here would now match nothing and this leak check would pass without measuring.
_SNAPSHOT_GLOB = os.path.join(temp_dir(), "FCB_TMP_snap_*")

# Fixture solids, all axis-aligned with their minimum corner at the origin so a sketch placed at
# a known Z lands on a known face.
PLATE_L = 40.0
PLATE_W = 40.0
PLATE_H = 10.0
PLATE_VOLUME = PLATE_L * PLATE_W * PLATE_H

BLOCK_L = 10.0
BLOCK_W = 20.0
BLOCK_H = 30.0
BLOCK_VOLUME = BLOCK_L * BLOCK_W * BLOCK_H

CYL_R = 5.0
CYL_H = 20.0
CYL_VOLUME = math.pi * CYL_R**2 * CYL_H

# A PartDesign Hole drills an angled point by default, so a blind hole removes its cylindrical
# depth plus the cone the drill tip leaves beyond it. The cone's height follows from the
# included point angle: a d=2r bore at an included angle A tapers over r / tan(A/2).
DRILL_POINT_ANGLE = 118.0


def blind_hole_volume(radius, depth):
    """The material a blind hole of this radius and dimensioned depth removes.

    The dimensioned depth measures the full-diameter bore; the angled drill point adds a cone
    of height ``radius / tan(angle / 2)`` below it.
    """
    cone_height = radius / math.tan(math.radians(DRILL_POINT_ANGLE / 2.0))
    return math.pi * radius**2 * depth + math.pi * radius**2 * cone_height / 3.0


def _snapshot_leftovers():
    """Every reserved-prefix snapshot directory currently on disk."""
    return sorted(glob.glob(_SNAPSHOT_GLOB))


def mm(value):
    return {"value": value, "unit": "mm"}


def deg(value):
    return {"value": value, "unit": "deg"}


def sub(obj, mapped):
    """A ``mapped_name`` selector naming one subelement of an object."""
    return {"kind": "mapped_name", "object": obj, "mapped_name": mapped}


def whole(obj):
    """A ``mapped_name`` selector naming a whole object, as datum links are spelled."""
    return {"kind": "mapped_name", "object": obj}


class _FeatureFixture(unittest.TestCase):
    """A registry holding one document, with helpers for building PartDesign fixtures."""

    def setUp(self):
        for path in _snapshot_leftovers():
            for name in os.listdir(path):
                os.remove(os.path.join(path, name))
            os.rmdir(path)
        # These tests call the use cases directly, with no host to read the operator flag, so the
        # posture is set here. The gate itself is covered in test_confirm_gate.py.
        self._posture = confirm.set_auto_approve(True)
        self.registry = DocumentRegistry()
        created = self.registry.document_create("feature_tools")
        self.handle = created["structured_content"]["doc"]

    def tearDown(self):
        confirm.set_auto_approve(self._posture)
        for name in list(App.listDocuments().keys()):
            App.closeDocument(name)

    def document(self):
        return self.registry.with_document(self.handle, lambda h, d: d)

    def empty_body(self, name="Body"):
        """Add an empty Body; its Tip stays unset until a solid feature is added."""
        document = self.document()
        body = document.addObject("PartDesign::Body", name)
        document.recompute()
        return body

    def body_over(self, solid, name="Body"):
        """Add a Body wrapping an existing solid, returning ``(body, in_body_base_name)``.

        ``Body.BaseFeature`` reports the external object, while the object the Body actually owns
        and dresses up is the ``PartDesign::FeatureBase`` wrapper its Tip names.
        """
        document = self.document()
        body = document.addObject("PartDesign::Body", name)
        body.BaseFeature = solid
        document.recompute()
        return body, body.Tip.Name

    def block(self):
        """A 10x20x30 block wrapped in a Body."""
        document = self.document()
        box = document.addObject("Part::Box", "Box")
        box.Length, box.Width, box.Height = BLOCK_L, BLOCK_W, BLOCK_H
        document.recompute()
        return self.body_over(box)

    def plate(self):
        """A 40x40x10 plate wrapped in a Body."""
        document = self.document()
        box = document.addObject("Part::Box", "Plate")
        box.Length, box.Width, box.Height = PLATE_L, PLATE_W, PLATE_H
        document.recompute()
        return self.body_over(box)

    def cylinder(self):
        """An r=5 h=20 cylinder wrapped in a Body."""
        document = self.document()
        cyl = document.addObject("Part::Cylinder", "Cyl")
        cyl.Radius, cyl.Height = CYL_R, CYL_H
        document.recompute()
        return self.body_over(cyl)

    def _sketch(self, body, name, z, rotation=None):
        """Add a fully constrained-ready sketch to ``body`` at height ``z``."""
        document = self.document()
        sketch = document.addObject("Sketcher::SketchObject", name)
        body.addObject(sketch)
        sketch.Placement = App.Placement(
            App.Vector(0, 0, z), rotation if rotation is not None else App.Rotation()
        )
        return sketch

    def circle_sketch(self, body, name, centre, radius, z=0.0, rotation=None):
        """A sketch holding one fully constrained circle."""
        sketch = self._sketch(body, name, z, rotation)
        sketch.addGeometry(
            Part.Circle(App.Vector(centre[0], centre[1], 0), App.Vector(0, 0, 1), radius), False
        )
        sketch.addConstraint(Sketcher.Constraint("Radius", 0, radius))
        sketch.addConstraint(Sketcher.Constraint("DistanceX", -1, 1, 0, 3, centre[0]))
        sketch.addConstraint(Sketcher.Constraint("DistanceY", -1, 1, 0, 3, centre[1]))
        self.document().recompute()
        self.assertTrue(sketch.FullyConstrained, f"{name} is not fully constrained")
        return sketch

    def rect_sketch(self, body, name, x0, y0, width, height, z=0.0, rotation=None):
        """A sketch holding one fully constrained axis-aligned rectangle."""
        sketch = self._sketch(body, name, z, rotation)
        corners = [
            (x0, y0),
            (x0 + width, y0),
            (x0 + width, y0 + height),
            (x0, y0 + height),
        ]
        for index in range(4):
            start = corners[index]
            end = corners[(index + 1) % 4]
            sketch.addGeometry(Part.LineSegment(App.Vector(*start, 0), App.Vector(*end, 0)), False)
        for index in range(4):
            sketch.addConstraint(Sketcher.Constraint("Coincident", index, 2, (index + 1) % 4, 1))
        for index in (0, 2):
            sketch.addConstraint(Sketcher.Constraint("Horizontal", index))
        for index in (1, 3):
            sketch.addConstraint(Sketcher.Constraint("Vertical", index))
        sketch.addConstraint(Sketcher.Constraint("DistanceX", -1, 1, 0, 1, x0))
        sketch.addConstraint(Sketcher.Constraint("DistanceY", -1, 1, 0, 1, y0))
        sketch.addConstraint(Sketcher.Constraint("DistanceX", 0, 1, 0, 2, width))
        sketch.addConstraint(Sketcher.Constraint("DistanceY", 1, 1, 1, 2, height))
        self.document().recompute()
        self.assertTrue(sketch.FullyConstrained, f"{name} is not fully constrained")
        return sketch

    def assert_ok(self, envelope):
        """Assert the envelope committed, returning its ``shape_summary``."""
        self.assertEqual(envelope["status"], "OK", envelope.get("detail"))
        block = envelope["structured_content"]["mutation"]
        self.assertFalse(block["rolled_back"])
        self.assertTrue(block["post_verify"]["passed"])
        state = envelope["structured_content"]["feature_state"]
        self.assertTrue(state["readable"], state)
        self.assertTrue(state["shape_summary"]["is_valid"])
        return state

    def assert_volume(self, envelope, expected, places=4):
        """Assert the created feature's solid has the hand-derived volume."""
        state = self.assert_ok(envelope)
        self.assertAlmostEqual(state["shape_summary"]["volume"], expected, places=places)
        return state

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

    def object_count(self):
        return len(self.document().Objects)


class PadTest(_FeatureFixture):
    def test_a_pad_adds_its_prism_and_advances_the_body_tip(self):
        # An 8x16 profile padded 5 mm adds 8*16*5 = 640 mm^3 to an empty Body.
        body = self.empty_body()
        self.rect_sketch(body, "Profile", 0.0, 0.0, 8.0, 16.0)

        envelope = features.feature_pad(
            self.registry,
            doc=self.handle,
            body="Body",
            profile="Profile",
            name="TopPad",
            length=mm(5.0),
        )

        state = self.assert_volume(envelope, 8.0 * 16.0 * 5.0)
        self.assertEqual(state["feature"], "TopPad")
        self.assertTrue(state["is_tip"])
        self.assertEqual(self.document().getObject("Body").Tip.Name, "TopPad")

    def test_a_symmetric_pad_straddles_the_profile_plane_without_changing_its_volume(self):
        # Midplane moves material, not volume: 8*16*12 either way, spanning -6..+6 in Z.
        body = self.empty_body()
        self.rect_sketch(body, "Profile", 0.0, 0.0, 8.0, 16.0)

        envelope = features.feature_pad(
            self.registry,
            doc=self.handle,
            body="Body",
            profile="Profile",
            name="MidPad",
            length=mm(12.0),
            midplane=True,
        )

        self.assert_volume(envelope, 8.0 * 16.0 * 12.0)
        shape = self.document().getObject("MidPad").Shape
        self.assertAlmostEqual(shape.BoundBox.ZMin, -6.0, places=6)
        self.assertAlmostEqual(shape.BoundBox.ZMax, 6.0, places=6)

    def test_a_one_sided_pad_starts_at_the_profile_plane(self):
        body = self.empty_body()
        self.rect_sketch(body, "Profile", 0.0, 0.0, 8.0, 16.0)

        envelope = features.feature_pad(
            self.registry,
            doc=self.handle,
            body="Body",
            profile="Profile",
            name="OneSide",
            length=mm(12.0),
        )

        self.assert_volume(envelope, 8.0 * 16.0 * 12.0)
        shape = self.document().getObject("OneSide").Shape
        self.assertAlmostEqual(shape.BoundBox.ZMin, 0.0, places=6)
        self.assertAlmostEqual(shape.BoundBox.ZMax, 12.0, places=6)

    def test_a_length_driven_pad_without_a_length_is_rejected_before_the_bracket(self):
        body = self.empty_body()
        self.rect_sketch(body, "Profile", 0.0, 0.0, 8.0, 16.0)

        self.assert_rejected_pre_bracket(
            self.object_count,
            features.feature_pad,
            self.registry,
            doc=self.handle,
            body="Body",
            profile="Profile",
            name="NoLength",
            up_to="Length",
        )

    def test_a_pad_with_no_length_field_at_all_is_rejected_before_the_bracket(self):
        # up_to defaults to Length, so an omitted up_to is still length-driven.
        body = self.empty_body()
        self.rect_sketch(body, "Profile", 0.0, 0.0, 8.0, 16.0)

        self.assert_rejected_pre_bracket(
            self.object_count,
            features.feature_pad,
            self.registry,
            doc=self.handle,
            body="Body",
            profile="Profile",
            name="NoLength",
        )

    def test_a_pocket_only_extrude_type_is_rejected_for_a_pad(self):
        # ThroughAll is a Pocket value; the Pad enumeration carries UpToLast at that position,
        # which is why the value is checked against the live enum rather than an index.
        body = self.empty_body()
        self.rect_sketch(body, "Profile", 0.0, 0.0, 8.0, 16.0)

        self.assert_rejected_pre_bracket(
            self.object_count,
            features.feature_pad,
            self.registry,
            doc=self.handle,
            body="Body",
            profile="Profile",
            name="Through",
            up_to="ThroughAll",
        )

    def test_an_unknown_body_is_rejected_before_the_bracket(self):
        body = self.empty_body()
        self.rect_sketch(body, "Profile", 0.0, 0.0, 8.0, 16.0)

        self.assert_rejected_pre_bracket(
            self.object_count,
            features.feature_pad,
            self.registry,
            doc=self.handle,
            body="NoSuchBody",
            profile="Profile",
            name="Pad",
            length=mm(5.0),
        )

    def test_a_body_name_that_is_not_a_body_is_rejected_before_the_bracket(self):
        body = self.empty_body()
        self.rect_sketch(body, "Profile", 0.0, 0.0, 8.0, 16.0)

        self.assert_rejected_pre_bracket(
            self.object_count,
            features.feature_pad,
            self.registry,
            doc=self.handle,
            body="Profile",
            profile="Profile",
            name="Pad",
            length=mm(5.0),
        )

    def test_a_name_already_in_use_is_rejected_before_the_bracket(self):
        body = self.empty_body()
        self.rect_sketch(body, "Profile", 0.0, 0.0, 8.0, 16.0)

        self.assert_rejected_pre_bracket(
            self.object_count,
            features.feature_pad,
            self.registry,
            doc=self.handle,
            body="Body",
            profile="Profile",
            name="Profile",
            length=mm(5.0),
        )

    def test_a_length_in_degrees_is_rejected_before_the_bracket(self):
        body = self.empty_body()
        self.rect_sketch(body, "Profile", 0.0, 0.0, 8.0, 16.0)

        self.assert_rejected_pre_bracket(
            self.object_count,
            features.feature_pad,
            self.registry,
            doc=self.handle,
            body="Body",
            profile="Profile",
            name="Pad",
            length=deg(5.0),
        )


class PocketTest(_FeatureFixture):
    def test_a_pocket_removes_its_prism_from_the_body(self):
        # A 6x12 profile pocketed 5 mm into the top face removes 6*12*5 = 360 mm^3.
        body, _ = self.block()
        self.rect_sketch(body, "Cut", 2.0, 4.0, 6.0, 12.0, z=BLOCK_H)

        envelope = features.feature_pocket(
            self.registry,
            doc=self.handle,
            body="Body",
            profile="Cut",
            name="Recess",
            length=mm(5.0),
        )

        self.assert_volume(envelope, BLOCK_VOLUME - 6.0 * 12.0 * 5.0)

    def test_a_through_all_pocket_cuts_the_whole_body(self):
        # A d=6 circular profile cut through the 30 mm Z extent removes pi*3^2*30.
        body, _ = self.block()
        self.circle_sketch(body, "Bore", (5.0, 10.0), 3.0, z=BLOCK_H)

        envelope = features.feature_pocket(
            self.registry,
            doc=self.handle,
            body="Body",
            profile="Bore",
            name="ThroughCut",
            up_to="ThroughAll",
        )

        state = self.assert_volume(envelope, BLOCK_VOLUME - math.pi * 9.0 * BLOCK_H)
        self.assertEqual(state["shape_summary"]["solid_count"], 1)

    def test_a_pad_only_extrude_type_is_rejected_for_a_pocket(self):
        body, _ = self.block()
        self.circle_sketch(body, "Bore", (5.0, 10.0), 3.0, z=BLOCK_H)

        self.assert_rejected_pre_bracket(
            self.object_count,
            features.feature_pocket,
            self.registry,
            doc=self.handle,
            body="Body",
            profile="Bore",
            name="Bad",
            up_to="UpToLast",
        )


class RevolveTest(_FeatureFixture):
    def test_a_full_revolve_about_a_sketch_axis_sweeps_the_pappus_volume(self):
        # Pappus: a circle of radius 6 whose centre is 20 from the axis sweeps
        # 2*pi*20 * pi*6^2 = 14212.2303 mm^3 in a full turn.
        body = self.empty_body()
        self.circle_sketch(
            body,
            "Ring",
            (20.0, 0.0),
            6.0,
            rotation=App.Rotation(App.Vector(1, 0, 0), 90),
        )

        envelope = features.feature_revolve(
            self.registry,
            doc=self.handle,
            body="Body",
            profile="Ring",
            name="Torus",
            axis=sub("Ring", "V_Axis"),
            angle=deg(360.0),
        )

        self.assert_volume(envelope, 2 * math.pi * 20.0 * math.pi * 36.0, places=3)

    def test_a_half_revolve_sweeps_half_the_full_turn_volume(self):
        # The angle is applied in degrees: App::PropertyAngle reads degrees, unlike the
        # Sketcher datum API which reads radians.
        body = self.empty_body()
        self.circle_sketch(
            body,
            "Ring",
            (20.0, 0.0),
            6.0,
            rotation=App.Rotation(App.Vector(1, 0, 0), 90),
        )

        envelope = features.feature_revolve(
            self.registry,
            doc=self.handle,
            body="Body",
            profile="Ring",
            name="HalfTorus",
            axis=sub("Ring", "V_Axis"),
            angle=deg(180.0),
        )

        self.assert_volume(envelope, math.pi * 20.0 * math.pi * 36.0, places=3)

    def test_the_revolution_axis_is_driven_only_by_reference_axis(self):
        # Base and Axis are read-only and computed during execute; only ReferenceAxis is set.
        body = self.empty_body()
        self.circle_sketch(
            body,
            "Ring",
            (20.0, 0.0),
            6.0,
            rotation=App.Rotation(App.Vector(1, 0, 0), 90),
        )

        features.feature_revolve(
            self.registry,
            doc=self.handle,
            body="Body",
            profile="Ring",
            name="Torus",
            axis=sub("Ring", "V_Axis"),
            angle=deg(360.0),
        )

        feature = self.document().getObject("Torus")
        target, subelements = feature.ReferenceAxis
        self.assertEqual(target.Name, "Ring")
        self.assertEqual(list(subelements), ["V_Axis"])

    def test_an_axis_subelement_outside_the_sketch_axes_is_rejected_before_the_bracket(self):
        body = self.empty_body()
        self.circle_sketch(
            body,
            "Ring",
            (20.0, 0.0),
            6.0,
            rotation=App.Rotation(App.Vector(1, 0, 0), 90),
        )

        self.assert_rejected_pre_bracket(
            self.object_count,
            features.feature_revolve,
            self.registry,
            doc=self.handle,
            body="Body",
            profile="Ring",
            name="Bad",
            axis=sub("Ring", "Z_Axis"),
            angle=deg(90.0),
        )

    def test_an_angle_in_millimetres_is_rejected_before_the_bracket(self):
        body = self.empty_body()
        self.circle_sketch(
            body,
            "Ring",
            (20.0, 0.0),
            6.0,
            rotation=App.Rotation(App.Vector(1, 0, 0), 90),
        )

        self.assert_rejected_pre_bracket(
            self.object_count,
            features.feature_revolve,
            self.registry,
            doc=self.handle,
            body="Body",
            profile="Ring",
            name="Bad",
            axis=sub("Ring", "V_Axis"),
            angle=mm(90.0),
        )


class HoleTest(_FeatureFixture):
    def test_a_through_hole_removes_its_bore_from_the_body(self):
        # A d=6 hole through the 30 mm Z extent removes pi*3^2*30 = 848.2300 mm^3.
        body, _ = self.block()
        self.circle_sketch(body, "Centre", (5.0, 10.0), 3.0, z=BLOCK_H)

        envelope = features.feature_hole(
            self.registry,
            doc=self.handle,
            body="Body",
            profile="Centre",
            name="Bore",
            diameter=mm(6.0),
            depth_type="ThroughAll",
        )

        state = self.assert_volume(envelope, BLOCK_VOLUME - math.pi * 9.0 * BLOCK_H)
        self.assertEqual(state["shape_summary"]["solid_count"], 1)

    def test_a_blind_hole_stops_at_its_dimensioned_depth_plus_the_drill_point(self):
        # A d=4 hole 8 mm deep removes the 8 mm bore plus the 118-degree drill-point cone,
        # and leaves the far end of the cylinder intact.
        body, _ = self.cylinder()
        self.circle_sketch(body, "Centre", (0.0, 0.0), 2.0, z=CYL_H)

        envelope = features.feature_hole(
            self.registry,
            doc=self.handle,
            body="Body",
            profile="Centre",
            name="Blind",
            diameter=mm(4.0),
            depth=mm(8.0),
        )

        state = self.assert_volume(envelope, CYL_VOLUME - blind_hole_volume(2.0, 8.0), places=3)
        self.assertEqual(state["shape_summary"]["solid_count"], 1)
        # Blind means the bore does not reach the far face: the solid keeps its full extent.
        self.assertAlmostEqual(state["shape_summary"]["bbox"][2], CYL_H, places=6)

    def test_depth_type_up_to_first_is_rejected_because_the_source_comments_it_out(self):
        # DepthTypeEnums is {"Dimension", "ThroughAll"}; UpToFirst is commented out in the
        # source, so it must never reach the property.
        body, _ = self.block()
        self.circle_sketch(body, "Centre", (5.0, 10.0), 3.0, z=BLOCK_H)

        self.assert_rejected_pre_bracket(
            self.object_count,
            features.feature_hole,
            self.registry,
            doc=self.handle,
            body="Body",
            profile="Centre",
            name="Bad",
            diameter=mm(6.0),
            depth=mm(5.0),
            depth_type="UpToFirst",
        )

    def test_a_dimensioned_hole_without_a_depth_is_rejected_before_the_bracket(self):
        body, _ = self.block()
        self.circle_sketch(body, "Centre", (5.0, 10.0), 3.0, z=BLOCK_H)

        self.assert_rejected_pre_bracket(
            self.object_count,
            features.feature_hole,
            self.registry,
            doc=self.handle,
            body="Body",
            profile="Centre",
            name="Bad",
            diameter=mm(6.0),
        )

    def test_a_cut_type_outside_the_unthreaded_enum_is_rejected_before_the_bracket(self):
        # With no thread type the cut-type enumeration is the four-member "None" profile, so a
        # metric-screw cut type is not reachable.
        body, _ = self.block()
        self.circle_sketch(body, "Centre", (5.0, 10.0), 3.0, z=BLOCK_H)

        self.assert_rejected_pre_bracket(
            self.object_count,
            features.feature_hole,
            self.registry,
            doc=self.handle,
            body="Body",
            profile="Centre",
            name="Bad",
            diameter=mm(6.0),
            depth=mm(5.0),
            cut_type="ISO 4762",
        )

    def test_the_same_cut_type_becomes_legal_once_its_thread_type_is_set(self):
        # FeatureHole::onChanged re-populates HoleCutType on every ThreadType write, so the
        # tool sets the thread type first and reads the enumeration back before assigning.
        body, _ = self.block()
        self.circle_sketch(body, "Centre", (5.0, 10.0), 3.0, z=BLOCK_H)

        envelope = features.feature_hole(
            self.registry,
            doc=self.handle,
            body="Body",
            profile="Centre",
            name="Threaded",
            depth=mm(20.0),
            thread_type="ISOMetricProfile",
            cut_type="ISO 4762",
        )

        self.assert_ok(envelope)
        feature = self.document().getObject("Threaded")
        self.assertEqual(feature.ThreadType, "ISOMetricProfile")
        self.assertEqual(feature.HoleCutType, "ISO 4762")

    def test_diameter_is_rejected_for_a_threaded_hole(self):
        # A threaded hole is sized from its ThreadSize table entry: assigning Diameter succeeds
        # and the value persists, but the geometry ignores it (measured on FreeCAD 1.1.1 —
        # ThreadType=ISOMetricProfile with Diameter=6.0 still bores ThreadSize M1x0.25). Silently
        # accepting the diameter would report a hole the model does not have.
        body, _ = self.block()
        self.circle_sketch(body, "Centre", (5.0, 10.0), 3.0, z=BLOCK_H)

        with self.assertRaises(ValidationError) as caught:
            features.feature_hole(
                self.registry,
                doc=self.handle,
                body="Body",
                profile="Centre",
                name="Threaded",
                diameter=mm(6.0),
                depth=mm(20.0),
                thread_type="ISOMetricProfile",
            )
        self.assertIn("ThreadSize", str(caught.exception))
        self.assertIsNone(self.document().getObject("Threaded"), "rejected before the bracket")

    def test_a_thread_type_outside_the_build_enum_is_rejected_before_the_bracket(self):
        body, _ = self.block()
        self.circle_sketch(body, "Centre", (5.0, 10.0), 3.0, z=BLOCK_H)

        self.assert_rejected_pre_bracket(
            self.object_count,
            features.feature_hole,
            self.registry,
            doc=self.handle,
            body="Body",
            profile="Centre",
            name="Bad",
            diameter=mm(6.0),
            depth=mm(5.0),
            thread_type="NotAThreadStandard",
        )


class DressUpDropTest(_FeatureFixture):
    """The silent edge-drop is the sharpest trap in the dress-up path.

    ``DressUp::getContinuousEdges`` erases any requested edge without exactly two adjacent faces
    and any whose faces meet above C0. It returns nothing, logs a warning, and the feature still
    reports ``Up-to-date`` with a valid shape — so a committed dress-up would silently ignore
    part of the user's selection.
    """

    def _cylinder_body(self):
        body, base = self.cylinder()
        shape = self.document().getObject(base).Shape
        # The cylinder's seam edge is the one with a single adjacent face; the two circular
        # edges each have two. Located by measurement rather than by assuming an index.
        seam = [
            f"Edge{i}"
            for i, edge in enumerate(shape.Edges, 1)
            if len(shape.ancestorsOfType(edge, Part.Face)) != 2
        ]
        keepers = [
            f"Edge{i}"
            for i, edge in enumerate(shape.Edges, 1)
            if len(shape.ancestorsOfType(edge, Part.Face)) == 2
        ]
        self.assertEqual(len(seam), 1, "the cylinder fixture must have exactly one seam edge")
        self.assertEqual(len(keepers), 2, "the cylinder fixture must have two circular edges")
        return body, base, seam[0], keepers

    def test_a_chamfer_naming_a_droppable_edge_is_rejected_before_the_bracket(self):
        body, base, seam, keepers = self._cylinder_body()

        self.assert_rejected_pre_bracket(
            self.object_count,
            features.feature_chamfer,
            self.registry,
            doc=self.handle,
            body="Body",
            base=base,
            name="Bad",
            edges=[sub(base, seam), sub(base, keepers[0])],
            size=mm(0.5),
        )

    def test_the_rejection_names_the_dropped_edge(self):
        body, base, seam, keepers = self._cylinder_body()

        with self.assertRaises(ValidationError) as caught:
            features.feature_chamfer(
                self.registry,
                doc=self.handle,
                body="Body",
                base=base,
                name="Bad",
                edges=[sub(base, seam), sub(base, keepers[0])],
                size=mm(0.5),
            )

        message = str(caught.exception)
        self.assertIn(seam, message)
        self.assertNotIn(keepers[0], message)

    def test_a_request_whose_every_edge_would_be_dropped_is_rejected_before_the_bracket(self):
        body, base, seam, _ = self._cylinder_body()

        self.assert_rejected_pre_bracket(
            self.object_count,
            features.feature_chamfer,
            self.registry,
            doc=self.handle,
            body="Body",
            base=base,
            name="Bad",
            edges=[sub(base, seam)],
            size=mm(0.5),
        )

    def test_the_dropped_edge_would_otherwise_commit_a_silently_smaller_chamfer(self):
        """Without the guard the two-edge request builds the same solid as a one-edge request.

        This is what makes the drop invisible: FreeCAD reports the feature valid and up to date,
        and only comparing the produced volume against a request the caller did not make reveals
        that one of the two named edges was never chamfered.
        """
        body, base, seam, keepers = self._cylinder_body()
        document = self.document()

        def build(name, subelements):
            feature = document.addObject("PartDesign::Chamfer", name)
            body.addObject(feature)
            feature.Base = (document.getObject(base), subelements)
            feature.Size = 0.5
            document.recompute()
            return feature

        one = build("OnlyKeeper", [keepers[0]])
        self.assertTrue(one.isValid())
        one_volume = one.Shape.Volume
        document.removeObject("OnlyKeeper")
        document.recompute()

        both = build("SeamPlusKeeper", [seam, keepers[0]])
        self.assertTrue(both.isValid(), "the drop is silent: FreeCAD still reports a valid shape")
        self.assertEqual(list(both.State), ["Up-to-date"])
        self.assertAlmostEqual(both.Shape.Volume, one_volume, places=9)

    def test_the_in_bracket_face_count_catches_a_drop_the_pre_bracket_guard_missed(self):
        """The pre-bracket guard predicts the drop; this one counts what FreeCAD actually did.

        The prediction reimplements ``getContinuousEdges``, whose continuity leg reads a stored
        OCC flag Python cannot see, so it can only approximate that condition with a normal
        comparison. The face count needs no prediction: a dressed edge always adds exactly one
        face, so a shortfall is the drop itself. Driven here with the prediction disabled, which
        is the only way to show the second guard carries the case on its own.
        """
        body, base, seam, keepers = self._cylinder_body()
        real_predictor = features._dropped_dressup_edges
        features._dropped_dressup_edges = lambda shape, subelements: []
        try:
            envelope = features.feature_chamfer(
                self.registry,
                doc=self.handle,
                body="Body",
                base=base,
                name="Backstop",
                edges=[sub(base, seam), sub(base, keepers[0])],
                size=mm(0.5),
            )
        finally:
            features._dropped_dressup_edges = real_predictor

        self.assertNotEqual(envelope["status"], "OK")
        self.assertIn("dressed 1 of the 2", envelope["detail"]["message"])
        mutation = envelope["structured_content"]["mutation"]
        self.assertTrue(mutation["rolled_back"])
        self.assertEqual(mutation["rollback_proven"], "rolled_back_verified")
        self.assertIsNone(self.document().getObject("Backstop"))


class DressUpTest(_FeatureFixture):
    def test_a_fillet_on_the_vertical_block_edges_removes_the_corner_material(self):
        # Each 2 mm corner fillet removes (r^2 - pi*r^2/4) * height along a vertical edge:
        # (4 - pi) * 30 per edge, over the four vertical edges.
        body, base = self.block()
        shape = self.document().getObject(base).Shape
        vertical = [
            f"Edge{i}"
            for i, edge in enumerate(shape.Edges, 1)
            if abs(edge.Vertexes[0].Point.z - edge.Vertexes[-1].Point.z) > 1e-9
        ]
        self.assertEqual(len(vertical), 4)

        envelope = features.feature_fillet(
            self.registry,
            doc=self.handle,
            body="Body",
            base=base,
            name="Corners",
            edges=[sub(base, name) for name in vertical],
            radius=mm(2.0),
        )

        removed = 4.0 * (4.0 - math.pi) * BLOCK_H
        self.assert_volume(envelope, BLOCK_VOLUME - removed, places=3)

    def test_a_chamfer_on_both_cylinder_rims_removes_two_frustum_rings(self):
        # A 45-degree chamfer of size s on a circular rim of radius r removes the difference
        # between the cylinder slice and the frustum: pi*s*(r^2 - (r*(r-s) + (r-s)^2/3 ... )).
        # Measured directly as the volume of a cylinder slice minus a truncated cone:
        #   pi*r^2*s - (pi*s/3)*(r^2 + r*(r-s) + (r-s)^2), per rim.
        body, base = self.cylinder()
        shape = self.document().getObject(base).Shape
        rims = [
            f"Edge{i}"
            for i, edge in enumerate(shape.Edges, 1)
            if len(shape.ancestorsOfType(edge, Part.Face)) == 2
        ]
        self.assertEqual(len(rims), 2)

        size = 0.5
        envelope = features.feature_chamfer(
            self.registry,
            doc=self.handle,
            body="Body",
            base=base,
            name="Rims",
            edges=[sub(base, name) for name in rims],
            size=mm(size),
        )

        inner = CYL_R - size
        slice_volume = math.pi * CYL_R**2 * size
        frustum = (math.pi * size / 3.0) * (CYL_R**2 + CYL_R * inner + inner**2)
        self.assert_volume(envelope, CYL_VOLUME - 2.0 * (slice_volume - frustum), places=3)

    def test_the_chamfer_type_is_the_verbatim_enum_member(self):
        body, base = self.cylinder()
        shape = self.document().getObject(base).Shape
        rim = next(
            f"Edge{i}"
            for i, edge in enumerate(shape.Edges, 1)
            if len(shape.ancestorsOfType(edge, Part.Face)) == 2
        )

        features.feature_chamfer(
            self.registry,
            doc=self.handle,
            body="Body",
            base=base,
            name="Rim",
            edges=[sub(base, rim)],
            size=mm(0.5),
            chamfer_type="Equal distance",
        )

        self.assertEqual(self.document().getObject("Rim").ChamferType, "Equal distance")

    def test_an_unknown_chamfer_type_is_rejected_before_the_bracket(self):
        body, base = self.cylinder()
        shape = self.document().getObject(base).Shape
        rim = next(
            f"Edge{i}"
            for i, edge in enumerate(shape.Edges, 1)
            if len(shape.ancestorsOfType(edge, Part.Face)) == 2
        )

        self.assert_rejected_pre_bracket(
            self.object_count,
            features.feature_chamfer,
            self.registry,
            doc=self.handle,
            body="Body",
            base=base,
            name="Bad",
            edges=[sub(base, rim)],
            size=mm(0.5),
            chamfer_type="Equal Distance",
        )

    def test_a_dress_up_base_outside_the_body_is_rejected_before_the_bracket(self):
        # FreeCAD only warns when a dress-up links out of its Body's scope, leaving a feature
        # whose reference the tree does not own.
        body, base = self.block()
        external = self.document().getObject("Box")
        self.assertNotEqual(external.Name, base)

        self.assert_rejected_pre_bracket(
            self.object_count,
            features.feature_fillet,
            self.registry,
            doc=self.handle,
            body="Body",
            base=external.Name,
            name="Bad",
            edges=[sub(external.Name, "Edge1")],
            radius=mm(1.0),
        )

    def test_a_selector_naming_a_face_rather_than_an_edge_is_rejected(self):
        body, base = self.block()

        self.assert_rejected_pre_bracket(
            self.object_count,
            features.feature_fillet,
            self.registry,
            doc=self.handle,
            body="Body",
            base=base,
            name="Bad",
            edges=[sub(base, "Face1")],
            radius=mm(1.0),
        )

    def test_an_unresolvable_edge_selector_is_rejected(self):
        body, base = self.block()

        self.assert_rejected_pre_bracket(
            self.object_count,
            features.feature_fillet,
            self.registry,
            doc=self.handle,
            body="Body",
            base=base,
            name="Bad",
            edges=[sub(base, "Edge9999")],
            radius=mm(1.0),
        )

    def test_a_repeated_edge_is_rejected(self):
        body, base = self.block()

        self.assert_rejected_pre_bracket(
            self.object_count,
            features.feature_fillet,
            self.registry,
            doc=self.handle,
            body="Body",
            base=base,
            name="Bad",
            edges=[sub(base, "Edge1"), sub(base, "Edge1")],
            radius=mm(1.0),
        )

    def test_an_edge_selector_naming_another_object_is_rejected(self):
        body, base = self.block()

        self.assert_rejected_pre_bracket(
            self.object_count,
            features.feature_fillet,
            self.registry,
            doc=self.handle,
            body="Body",
            base=base,
            name="Bad",
            edges=[sub("Box", "Edge1")],
            radius=mm(1.0),
        )


class PatternTest(_FeatureFixture):
    def _plate_with_hole(self):
        """A 40x40x10 plate carrying one d=4 through hole 8 mm in from the X edge."""
        body, base = self.plate()
        self.circle_sketch(body, "Centre", (8.0, 20.0), 2.0, z=PLATE_H)
        envelope = features.feature_hole(
            self.registry,
            doc=self.handle,
            body="Body",
            profile="Centre",
            name="Bore",
            diameter=mm(4.0),
            depth_type="ThroughAll",
        )
        self.assert_volume(envelope, PLATE_VOLUME - math.pi * 4.0 * PLATE_H)
        return body, base

    def test_a_linear_pattern_repeats_the_hole_including_the_original(self):
        # Occurrences counts the original, so three occurrences remove three bores.
        self._plate_with_hole()

        envelope = features.feature_pattern(
            self.registry,
            doc=self.handle,
            body="Body",
            name="Row",
            kind="linear",
            originals=["Bore"],
            direction=whole("X_Axis"),
            length=mm(20.0),
            occurrences=3,
        )

        self.assert_volume(envelope, PLATE_VOLUME - 3.0 * math.pi * 4.0 * PLATE_H)

    def test_a_linear_pattern_spaces_its_occurrences_over_the_whole_length(self):
        # Extent mode spreads occurrences across Length, so three over 20 mm land 10 mm apart.
        self._plate_with_hole()

        features.feature_pattern(
            self.registry,
            doc=self.handle,
            body="Body",
            name="Row",
            kind="linear",
            originals=["Bore"],
            direction=whole("X_Axis"),
            length=mm(20.0),
            occurrences=3,
            mode="Extent",
        )

        shape = self.document().getObject("Row").Shape
        centres = sorted(
            round(face.Surface.Center.x, 6)
            for face in shape.Faces
            if type(face.Surface).__name__ == "Cylinder"
        )
        self.assertEqual(len(centres), 3)
        self.assertAlmostEqual(centres[1] - centres[0], 10.0, places=6)
        self.assertAlmostEqual(centres[2] - centres[1], 10.0, places=6)

    def test_a_polar_pattern_over_a_full_turn_steps_by_angle_over_occurrences(self):
        # A full turn divides by Occurrences, not Occurrences-1: six copies land 60 deg apart,
        # and the sixth does not coincide with the first.
        body, _ = self.cylinder()
        self.circle_sketch(body, "Recess", (3.0, 0.0), 1.0, z=CYL_H)
        features.feature_hole(
            self.registry,
            doc=self.handle,
            body="Body",
            profile="Recess",
            name="Dimple",
            diameter=mm(2.0),
            depth=mm(2.0),
        )

        envelope = features.feature_pattern(
            self.registry,
            doc=self.handle,
            body="Body",
            name="Ring",
            kind="polar",
            originals=["Dimple"],
            axis=whole("Z_Axis"),
            angle=deg(360.0),
            occurrences=6,
        )

        self.assert_volume(envelope, CYL_VOLUME - 6.0 * blind_hole_volume(1.0, 2.0), places=3)

    def test_fewer_than_two_occurrences_is_rejected_before_the_bracket(self):
        self._plate_with_hole()

        self.assert_rejected_pre_bracket(
            self.object_count,
            features.feature_pattern,
            self.registry,
            doc=self.handle,
            body="Body",
            name="Bad",
            kind="linear",
            originals=["Bore"],
            direction=whole("X_Axis"),
            length=mm(10.0),
            occurrences=1,
        )

    def test_an_unknown_pattern_kind_is_rejected_before_the_bracket(self):
        self._plate_with_hole()

        self.assert_rejected_pre_bracket(
            self.object_count,
            features.feature_pattern,
            self.registry,
            doc=self.handle,
            body="Body",
            name="Bad",
            kind="spiral",
            originals=["Bore"],
            direction=whole("X_Axis"),
            length=mm(10.0),
            occurrences=3,
        )

    def test_an_unknown_original_is_rejected_before_the_bracket(self):
        self._plate_with_hole()

        self.assert_rejected_pre_bracket(
            self.object_count,
            features.feature_pattern,
            self.registry,
            doc=self.handle,
            body="Body",
            name="Bad",
            kind="linear",
            originals=["NoSuchFeature"],
            direction=whole("X_Axis"),
            length=mm(10.0),
            occurrences=3,
        )

    def test_a_mode_outside_the_build_enum_is_rejected_before_the_bracket(self):
        # The value is checked against the live enumeration rather than a hardcoded list.
        self._plate_with_hole()

        self.assert_rejected_pre_bracket(
            self.object_count,
            features.feature_pattern,
            self.registry,
            doc=self.handle,
            body="Body",
            name="Bad",
            kind="linear",
            originals=["Bore"],
            direction=whole("X_Axis"),
            length=mm(10.0),
            occurrences=3,
            mode="NotAPatternMode",
        )

    def test_should_refuse_the_retired_length_spelling_when_mode_is_given(self):
        # Arrange
        self._plate_with_hole()
        legal = shim.probe_object(
            "PartDesign::LinearPattern", lambda probe: shim.enum_values(probe, "Mode")
        )

        # Act
        with self.assertRaises(ValidationError) as caught:
            features.feature_pattern(
                self.registry,
                doc=self.handle,
                body="Body",
                name="Bad",
                kind="linear",
                originals=["Bore"],
                direction=whole("X_Axis"),
                length=mm(10.0),
                occurrences=3,
                mode="length",
            )

        # Assert
        self.assertEqual(str(caught.exception), f"mode 'length' is not one of {legal}")

    def test_should_step_occurrences_by_the_offset_when_a_linear_pattern_uses_spacing(self):
        # Arrange
        self._plate_with_hole()

        # Act
        envelope = features.feature_pattern(
            self.registry,
            doc=self.handle,
            body="Body",
            name="Row",
            kind="linear",
            originals=["Bore"],
            direction=whole("X_Axis"),
            offset=mm(10.0),
            occurrences=3,
            mode="Spacing",
        )

        # Assert
        self.assertEqual(envelope["status"], "OK", envelope.get("detail"))
        row = self.document().getObject("Row")
        self.assertEqual(row.Mode, "Spacing")
        self.assertAlmostEqual(row.Offset.Value, 10.0, places=6)
        centres = sorted(
            round(face.Surface.Center.x, 6)
            for face in row.Shape.Faces
            if type(face.Surface).__name__ == "Cylinder"
        )
        self.assertEqual(len(centres), 3)
        self.assertAlmostEqual(centres[1] - centres[0], 10.0, places=6)
        self.assertAlmostEqual(centres[2] - centres[1], 10.0, places=6)

    def test_should_step_occurrences_by_the_offset_when_a_polar_pattern_uses_spacing(self):
        # Arrange
        body, _ = self.cylinder()
        self.circle_sketch(body, "Recess", (3.0, 0.0), 1.0, z=CYL_H)
        features.feature_hole(
            self.registry,
            doc=self.handle,
            body="Body",
            profile="Recess",
            name="Dimple",
            diameter=mm(2.0),
            depth=mm(2.0),
        )

        # Act
        envelope = features.feature_pattern(
            self.registry,
            doc=self.handle,
            body="Body",
            name="Ring",
            kind="polar",
            originals=["Dimple"],
            axis=whole("Z_Axis"),
            offset=deg(60.0),
            occurrences=3,
            mode="Spacing",
        )

        # Assert
        self.assertEqual(envelope["status"], "OK", envelope.get("detail"))
        ring = self.document().getObject("Ring")
        self.assertEqual(ring.Mode, "Spacing")
        self.assertAlmostEqual(ring.Offset.Value, 60.0, places=6)
        angles = sorted(
            round(math.degrees(math.atan2(face.Surface.Center.y, face.Surface.Center.x)), 6)
            for face in ring.Shape.Faces
            if type(face.Surface).__name__ == "Cylinder" and abs(face.Surface.Radius - 1.0) < 1e-6
        )
        self.assertEqual(len(angles), 3)
        self.assertAlmostEqual(angles[1] - angles[0], 60.0, places=6)
        self.assertAlmostEqual(angles[2] - angles[1], 60.0, places=6)


class FreeCADDefaultTest(_FeatureFixture):
    """A field FreeCAD fills in is optional here: omitting it takes the application's default.

    Each case also sends an explicit value, so an implementation that ignored the argument
    entirely would fail rather than pass the omission cases by accident.
    """

    def test_a_fillet_with_no_radius_takes_freecads_own(self):
        body, base = self.block()
        shape = self.document().getObject(base).Shape
        edge = next(
            f"Edge{i}"
            for i, e in enumerate(shape.Edges, 1)
            if abs(e.Vertexes[0].Point.z - e.Vertexes[-1].Point.z) > 1e-9
        )

        envelope = features.feature_fillet(
            self.registry,
            doc=self.handle,
            body="Body",
            base=base,
            name="Soft",
            edges=[sub(base, edge)],
        )

        self.assertEqual(envelope["status"], "OK", envelope.get("detail"))
        self.assertAlmostEqual(self.document().getObject("Soft").Radius.Value, 1.0, places=6)

    def test_a_fillet_still_honours_an_explicit_radius(self):
        body, base = self.block()
        shape = self.document().getObject(base).Shape
        edge = next(
            f"Edge{i}"
            for i, e in enumerate(shape.Edges, 1)
            if abs(e.Vertexes[0].Point.z - e.Vertexes[-1].Point.z) > 1e-9
        )

        features.feature_fillet(
            self.registry,
            doc=self.handle,
            body="Body",
            base=base,
            name="Soft",
            edges=[sub(base, edge)],
            radius=mm(2.0),
        )

        self.assertAlmostEqual(self.document().getObject("Soft").Radius.Value, 2.0, places=6)

    def test_a_chamfer_with_no_size_takes_freecads_own(self):
        body, base = self.block()
        shape = self.document().getObject(base).Shape
        edge = next(
            f"Edge{i}"
            for i, e in enumerate(shape.Edges, 1)
            if abs(e.Vertexes[0].Point.z - e.Vertexes[-1].Point.z) > 1e-9
        )

        envelope = features.feature_chamfer(
            self.registry,
            doc=self.handle,
            body="Body",
            base=base,
            name="Bevel",
            edges=[sub(base, edge)],
        )

        self.assertEqual(envelope["status"], "OK", envelope.get("detail"))
        self.assertAlmostEqual(self.document().getObject("Bevel").Size.Value, 1.0, places=6)

    def test_a_linear_pattern_with_no_occurrences_takes_freecads_two(self):
        body, base = self.plate()
        self.circle_sketch(body, "Centre", (8.0, 20.0), 2.0, z=PLATE_H)
        features.feature_hole(
            self.registry,
            doc=self.handle,
            body="Body",
            profile="Centre",
            name="Bore",
            diameter=mm(4.0),
            depth_type="ThroughAll",
        )

        envelope = features.feature_pattern(
            self.registry,
            doc=self.handle,
            body="Body",
            name="Row",
            kind="linear",
            originals=["Bore"],
            direction=sub(base, "Edge1"),
            length=mm(24.0),
        )

        self.assertEqual(envelope["status"], "OK", envelope.get("detail"))
        self.assertEqual(self.document().getObject("Row").Occurrences, 2)

    def test_a_polar_pattern_with_no_occurrences_takes_freecads_three(self):
        """FreeCAD defaults polar patterns to 3, not to the linear default of 2."""
        body, base = self.plate()
        self.circle_sketch(body, "Centre", (8.0, 20.0), 2.0, z=PLATE_H)
        features.feature_hole(
            self.registry,
            doc=self.handle,
            body="Body",
            profile="Centre",
            name="Bore",
            diameter=mm(4.0),
            depth_type="ThroughAll",
        )

        envelope = features.feature_pattern(
            self.registry,
            doc=self.handle,
            body="Body",
            name="Ring",
            kind="polar",
            originals=["Bore"],
            axis=sub("Centre", "N_Axis"),
        )

        self.assertEqual(envelope["status"], "OK", envelope.get("detail"))
        self.assertEqual(self.document().getObject("Ring").Occurrences, 3)


class MirrorTest(_FeatureFixture):
    def test_a_mirror_across_a_bisecting_plane_doubles_the_hole(self):
        # The plate spans 0..40 in X, so the plane through x=20 bisects it; a bore 8 mm from one
        # edge mirrors to 8 mm from the other, removing a second pi*2^2*10.
        body, base = self.plate()
        self.circle_sketch(body, "Centre", (8.0, 20.0), 2.0, z=PLATE_H)
        features.feature_hole(
            self.registry,
            doc=self.handle,
            body="Body",
            profile="Centre",
            name="Bore",
            diameter=mm(4.0),
            depth_type="ThroughAll",
        )
        document = self.document()
        plane = document.addObject("PartDesign::Plane", "MidPlane")
        body.addObject(plane)
        plane.AttachmentSupport = [(document.getObject("YZ_Plane"), [""])]
        plane.MapMode = "ObjectXY"
        plane.AttachmentOffset = App.Placement(App.Vector(0, 0, 20.0), App.Rotation())
        document.recompute()

        envelope = features.feature_mirror(
            self.registry,
            doc=self.handle,
            body="Body",
            name="Pair",
            mirror_plane=whole("MidPlane"),
            originals=["Bore"],
        )

        state = self.assert_volume(envelope, PLATE_VOLUME - 2.0 * math.pi * 4.0 * PLATE_H)
        self.assertEqual(state["shape_summary"]["solid_count"], 1)

    def test_an_unresolvable_mirror_plane_is_rejected_before_the_bracket(self):
        body, _ = self.plate()
        self.circle_sketch(body, "Centre", (8.0, 20.0), 2.0, z=PLATE_H)
        features.feature_hole(
            self.registry,
            doc=self.handle,
            body="Body",
            profile="Centre",
            name="Bore",
            diameter=mm(4.0),
            depth_type="ThroughAll",
        )

        self.assert_rejected_pre_bracket(
            self.object_count,
            features.feature_mirror,
            self.registry,
            doc=self.handle,
            body="Body",
            name="Bad",
            mirror_plane=whole("NoSuchPlane"),
            originals=["Bore"],
        )


class DatumTest(_FeatureFixture):
    def test_a_datum_plane_is_attached_and_offset_along_its_local_z(self):
        body, _ = self.block()

        envelope = features.feature_datum(
            self.registry,
            doc=self.handle,
            body="Body",
            name="Raised",
            kind="plane",
            attachment=whole("XY_Plane"),
            map_mode="ObjectXY",
            offset=mm(5.0),
        )

        self.assertEqual(envelope["status"], "OK", envelope.get("detail"))
        datum = self.document().getObject("Raised")
        self.assertEqual(datum.MapMode, "ObjectXY")
        self.assertAlmostEqual(datum.Placement.Base.z, 5.0, places=6)

    def test_each_datum_kind_creates_its_own_partdesign_type(self):
        # The MapMode enumeration is the union across attach engines, so a mode it advertises is
        # not necessarily one a given datum kind's engine implements — an axis rejects the
        # Translate a plane accepts. Each kind is therefore driven with a mode its own engine
        # implements, against a subelement of the right shape type.
        body, base = self.block()
        cases = {
            "plane": ("PartDesign::Plane", "Vertex1", "Translate"),
            "axis": ("PartDesign::Line", "Edge1", "Tangent"),
            "point": ("PartDesign::Point", "Vertex1", "Vertex"),
            "cs": ("PartDesign::CoordinateSystem", "Vertex1", "Translate"),
        }

        for kind, (type_id, subelement, map_mode) in cases.items():
            envelope = features.feature_datum(
                self.registry,
                doc=self.handle,
                body="Body",
                name=f"Datum{kind}",
                kind=kind,
                attachment=sub(base, subelement),
                map_mode=map_mode,
            )
            self.assertEqual(envelope["status"], "OK", envelope.get("detail"))
            self.assertEqual(self.document().getObject(f"Datum{kind}").TypeId, type_id)

    def test_an_unknown_datum_kind_is_rejected_before_the_bracket(self):
        self.block()

        self.assert_rejected_pre_bracket(
            self.object_count,
            features.feature_datum,
            self.registry,
            doc=self.handle,
            body="Body",
            name="Bad",
            kind="helix",
            attachment=whole("XY_Plane"),
        )

    def test_an_unknown_attachment_target_is_rejected_before_the_bracket(self):
        self.block()

        self.assert_rejected_pre_bracket(
            self.object_count,
            features.feature_datum,
            self.registry,
            doc=self.handle,
            body="Body",
            name="Bad",
            kind="plane",
            attachment=whole("NoSuchObject"),
        )

    def test_a_mode_the_kinds_engine_does_not_implement_is_rejected_before_the_bracket(self):
        # Measured on FreeCAD 1.1.1: every kind advertises all 55 MapMode values, but the axis
        # engine implements 19 and rejects FlatFace at recompute — inside the bracket — so the
        # caller paid a snapshot and a rollback for input the I/O matrix rejects as INVALID_INPUT.
        _, base = self.block()

        self.assert_rejected_pre_bracket(
            self.object_count,
            features.feature_datum,
            self.registry,
            doc=self.handle,
            body="Body",
            name="Bad",
            kind="axis",
            attachment=sub(base, "Face1"),
            map_mode="FlatFace",
        )

    def test_a_mode_rejected_only_by_its_references_still_reaches_the_bracket(self):
        # The guard excludes by kind alone. Translate is implemented for a plane and fails on a
        # face reference because it needs a vertex, which is a reference fault the precheck
        # cannot see — it must surface as a rolled-back RECOMPUTE_ERROR, not a pre-bracket
        # rejection, or the guard would be rejecting valid kind/mode pairs.
        _, base = self.block()

        envelope = features.feature_datum(
            self.registry,
            doc=self.handle,
            body="Body",
            name="RefFault",
            kind="plane",
            attachment=sub(base, "Face1"),
            map_mode="Translate",
        )

        self.assertNotEqual(envelope["status"], "OK")
        self.assertTrue(envelope["structured_content"]["mutation"]["rolled_back"])


class BodyCreateTest(_FeatureFixture):
    """The Body creator: every feature_* tool needs a Body no other tool could make.

    _FeatureFixture.empty_body builds one with document.addObject directly, which is why the
    gap never surfaced in these tests — nothing here went through the tool surface.
    """

    def test_a_created_body_is_an_empty_partdesign_body(self):
        envelope = features.feature_body_create(
            self.registry, doc=self.handle, name="Bracket"
        )

        self.assertEqual(envelope["status"], "OK", envelope.get("detail"))
        body = self.document().getObject("Bracket")
        self.assertIsNotNone(body)
        self.assertEqual(body.TypeId, "PartDesign::Body")
        self.assertEqual(body.Label, "Bracket")
        self.assertIsNone(body.Tip)
        self.assertEqual(list(body.Group), [])

    def test_a_pad_succeeds_against_a_body_this_tool_created(self):
        # The end-to-end proof that the gap is closed: before this tool existed, no MCP caller
        # could reach feature_pad at all, because nothing could produce its 'body' argument.
        created = features.feature_body_create(
            self.registry, doc=self.handle, name="Bracket"
        )
        self.assertEqual(created["status"], "OK", created.get("detail"))
        body = self.document().getObject("Bracket")
        self.rect_sketch(body, "Profile", 0.0, 0.0, 8.0, 16.0)

        envelope = features.feature_pad(
            self.registry,
            doc=self.handle,
            body="Bracket",
            profile="Profile",
            name="Block",
            length=mm(5.0),
        )

        self.assertEqual(envelope["status"], "OK", envelope.get("detail"))
        pad = self.document().getObject("Block")
        self.assertTrue(pad.isValid())
        self.assertAlmostEqual(pad.Shape.Volume, 8.0 * 16.0 * 5.0, places=6)

    def test_a_name_already_in_use_is_rejected_before_the_bracket(self):
        # FreeCAD uniquifies a duplicate to "Bracket001" rather than raising, so an unchecked
        # collision would hand back an object under a name the caller never asked for.
        first = features.feature_body_create(self.registry, doc=self.handle, name="Bracket")
        self.assertEqual(first["status"], "OK", first.get("detail"))

        self.assert_rejected_pre_bracket(
            self.object_count,
            features.feature_body_create,
            self.registry,
            doc=self.handle,
            name="Bracket",
        )

    def test_a_name_freecad_would_rewrite_is_rejected_before_the_bracket(self):
        self.assert_rejected_pre_bracket(
            self.object_count,
            features.feature_body_create,
            self.registry,
            doc=self.handle,
            name="1Bracket",
        )

    def test_the_bodys_origin_children_stay_out_of_the_fingerprint(self):
        # A Body brings App::Origin plus its Plane/Line/Point children. They are datum features,
        # which fingerprint() already skips; asserted here so a later change cannot let the
        # infinite-extent planes back into the digest.
        features.feature_body_create(self.registry, doc=self.handle, name="Bracket")
        document = self.document()

        origin_types = {o.TypeId for o in document.Objects if o.TypeId.startswith("App::")}
        self.assertTrue(origin_types, "a Body must bring its Origin children")
        record = fingerprint.fingerprint(document)

        self.assertEqual([entry["name"] for entry in record["objects"]], [])

    def test_a_body_adopts_an_existing_solid_as_its_base_feature(self):
        document = self.document()
        document.addObject("Part::Box", "Box")
        document.recompute()

        envelope = features.feature_body_create(
            self.registry, doc=self.handle, name="Bracket", base_feature="Box"
        )

        self.assertEqual(envelope["status"], "OK", envelope.get("detail"))
        body = document.getObject("Bracket")
        self.assertIsNotNone(body.Tip)
        self.assertAlmostEqual(body.Shape.Volume, 10.0 * 10.0 * 10.0, places=6)

    def test_a_pad_on_an_adopted_body_adds_to_the_adopted_solid(self):
        # A feature on an adopted Body adds to the adopted solid, so the resulting volume is
        # the solid plus the feature, never the feature alone.
        document = self.document()
        document.addObject("Part::Box", "Box")
        document.recompute()
        created = features.feature_body_create(
            self.registry, doc=self.handle, name="Bracket", base_feature="Box"
        )
        self.assertEqual(created["status"], "OK", created.get("detail"))
        body = document.getObject("Bracket")
        self.rect_sketch(body, "Profile", 2.0, 2.0, 4.0, 4.0, z=10.0)

        envelope = features.feature_pad(
            self.registry,
            doc=self.handle,
            body="Bracket",
            profile="Profile",
            name="Block",
            length=mm(5.0),
        )

        self.assertEqual(envelope["status"], "OK", envelope.get("detail"))
        pad = document.getObject("Block")
        self.assertAlmostEqual(pad.Shape.Volume, 1000.0 + 4.0 * 4.0 * 5.0, places=6)

    def test_omitting_base_feature_still_creates_an_empty_body(self):
        envelope = features.feature_body_create(
            self.registry, doc=self.handle, name="Bracket"
        )

        self.assertEqual(envelope["status"], "OK", envelope.get("detail"))
        body = self.document().getObject("Bracket")
        self.assertIsNone(body.Tip)
        self.assertTrue(body.Shape.isNull())

    def test_a_sketch_as_base_feature_is_rejected_before_the_bracket(self):
        # FreeCAD accepts this silently and leaves the Body with a null shape and status
        # 'Touched', so nothing downstream would report it.
        document = self.document()
        document.addObject("Sketcher::SketchObject", "Sketchy")
        document.recompute()

        self.assert_rejected_pre_bracket(
            self.object_count,
            features.feature_body_create,
            self.registry,
            doc=self.handle,
            name="Bracket",
            base_feature="Sketchy",
        )

    def test_a_shapeless_object_as_base_feature_is_rejected_before_the_bracket(self):
        document = self.document()
        document.addObject("App::FeaturePython", "NoShape")
        document.recompute()

        self.assert_rejected_pre_bracket(
            self.object_count,
            features.feature_body_create,
            self.registry,
            doc=self.handle,
            name="Bracket",
            base_feature="NoShape",
        )

    def test_a_solid_another_body_already_adopted_is_rejected(self):
        # Measured: FreeCAD permits this and leaves BOTH Bodies reporting the same volume,
        # which no later check in this bridge would catch.
        document = self.document()
        document.addObject("Part::Box", "Box")
        document.recompute()
        first = features.feature_body_create(
            self.registry, doc=self.handle, name="First", base_feature="Box"
        )
        self.assertEqual(first["status"], "OK", first.get("detail"))

        self.assert_rejected_pre_bracket(
            self.object_count,
            features.feature_body_create,
            self.registry,
            doc=self.handle,
            name="Second",
            base_feature="Box",
        )

    def test_an_unknown_base_feature_is_rejected_before_the_bracket(self):
        self.assert_rejected_pre_bracket(
            self.object_count,
            features.feature_body_create,
            self.registry,
            doc=self.handle,
            name="Bracket",
            base_feature="NoSuchObject",
        )


class SetParametersTest(_FeatureFixture):
    def _padded_body(self):
        body = self.empty_body()
        self.rect_sketch(body, "Profile", 0.0, 0.0, 8.0, 16.0)
        envelope = features.feature_pad(
            self.registry,
            doc=self.handle,
            body="Body",
            profile="Profile",
            name="Block",
            length=mm(5.0),
        )
        self.assert_volume(envelope, 8.0 * 16.0 * 5.0)
        return body

    def test_editing_a_driving_length_rebuilds_the_solid_inside_the_bracket(self):
        self._padded_body()

        envelope = features.feature_set_parameters(
            self.registry,
            doc=self.handle,
            feature="Block",
            parameters={"Length": mm(8.0)},
        )

        self.assert_volume(envelope, 8.0 * 16.0 * 8.0)

    def test_editing_an_enumerated_property_checks_the_live_enum(self):
        self._padded_body()

        envelope = features.feature_set_parameters(
            self.registry,
            doc=self.handle,
            feature="Block",
            parameters={"Type": "Length"},
        )

        self.assertEqual(envelope["status"], "OK", envelope.get("detail"))
        self.assertEqual(self.document().getObject("Block").Type, "Length")

    def test_an_unknown_property_is_rejected_before_the_bracket(self):
        self._padded_body()

        self.assert_rejected_pre_bracket(
            lambda: self.document().getObject("Block").Length.Value,
            features.feature_set_parameters,
            self.registry,
            doc=self.handle,
            feature="Block",
            parameters={"NoSuchProperty": mm(1.0)},
        )

    def test_a_length_given_in_degrees_is_rejected_before_the_bracket(self):
        self._padded_body()

        self.assert_rejected_pre_bracket(
            lambda: self.document().getObject("Block").Length.Value,
            features.feature_set_parameters,
            self.registry,
            doc=self.handle,
            feature="Block",
            parameters={"Length": deg(8.0)},
        )

    def test_an_enum_member_outside_the_live_enum_is_rejected_before_the_bracket(self):
        self._padded_body()

        self.assert_rejected_pre_bracket(
            lambda: self.document().getObject("Block").Type,
            features.feature_set_parameters,
            self.registry,
            doc=self.handle,
            feature="Block",
            parameters={"Type": "NotAnExtrudeType"},
        )

    def test_an_unknown_feature_is_rejected_before_the_bracket(self):
        self._padded_body()

        self.assert_rejected_pre_bracket(
            self.object_count,
            features.feature_set_parameters,
            self.registry,
            doc=self.handle,
            feature="NoSuchFeature",
            parameters={"Length": mm(8.0)},
        )

    def test_an_empty_parameter_map_is_rejected_before_the_bracket(self):
        self._padded_body()

        self.assert_rejected_pre_bracket(
            self.object_count,
            features.feature_set_parameters,
            self.registry,
            doc=self.handle,
            feature="Block",
            parameters={},
        )


class RollbackTest(_FeatureFixture):
    def test_a_feature_leaving_an_invalid_solid_rolls_back_with_the_document_restored(self):
        # A pad whose profile lies outside any material still builds, so the failure is planted
        # by naming a length the extrude cannot realise: a zero-length extrude has no solid.
        body = self.empty_body()
        self.rect_sketch(body, "Profile", 0.0, 0.0, 8.0, 16.0)
        before = len(self.document().Objects)

        def failing_op(document):
            pad = document.addObject("PartDesign::Pad", "Broken")
            body_obj = document.getObject("Body")
            body_obj.addObject(pad)
            pad.Profile = document.getObject("Profile")
            pad.Length = 0.0
            return ["Broken", "Body"]

        envelope = features._feature_mutation(
            self.registry,
            self.handle,
            "Broken",
            "planted invalid extrude",
            "test",
            {},
            failing_op,
        )

        self.assertNotEqual(envelope["status"], "OK")
        block = envelope["structured_content"]["mutation"]
        self.assertTrue(block["rolled_back"])
        self.assertIsNotNone(block["rollback_proven"])
        self.assertFalse(envelope["structured_content"]["feature_state"]["readable"])
        self.assertIsNone(self.document().getObject("Broken"))
        self.assertEqual(len(self.document().Objects), before)
        self.assertEqual(_snapshot_leftovers(), [])


class RegistryRebindTest(_FeatureFixture):
    """The snapshot-restore rebind, proven on a document whose fingerprint round-trips.

    The pre-mutation document holds a plain solid rather than a Body: a Body's ``App::Plane``
    origin planes are infinite (a face spanning +/-1e100), and the floating-point noise in a
    quantity of that magnitude changes their serialized B-rep across a save and reload, so no
    rollback on such a document can be hash-proven. That is recorded as deferred work; here the
    fixture avoids it so the rebind itself is what the test measures. The Body the later
    assertions need is created after the restore, through the tool.
    """

    def keep_solid(self):
        """A plain solid whose fingerprint survives ``saveCopy`` and reopen unchanged."""
        document = self.document()
        box = document.addObject("Part::Box", "Keep")
        box.Length, box.Width, box.Height = BLOCK_L, BLOCK_W, BLOCK_H
        document.recompute()
        return box

    def _force_snapshot_restore(self):
        """Drive a failing feature op down the snapshot-restore path and return its envelope.

        Abort restores this pattern cleanly on FreeCAD 1.1.x, so the escalation is forced by
        making the post-abort re-hash disagree once — the same state ``run_mutation`` reaches
        when undo fails to restore the pre-transaction boundary (FreeCAD #6031).
        """

        def op(document):
            ghost = document.addObject("Part::Box", "Ghost")
            ghost.Length, ghost.Width, ghost.Height = 1.0, 2.0, 3.0
            raise RuntimeError("planted rollback-boundary failure")

        real_equal = transaction.fingerprints_equal
        calls = []

        def once_unequal(left, right):
            calls.append(1)
            return False if len(calls) == 1 else real_equal(left, right)

        transaction.fingerprints_equal = once_unequal
        try:
            return features._feature_mutation(
                self.registry, self.handle, "Keep", "forced restore", "test", {}, op
            )
        finally:
            transaction.fingerprints_equal = real_equal

    def test_a_forced_snapshot_restore_rebinds_the_registry_to_the_live_document(self):
        self.keep_solid()
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

    def test_the_next_feature_call_on_the_rebound_handle_succeeds(self):
        self.keep_solid()
        self._force_snapshot_restore()

        document = self.document()
        body = document.addObject("PartDesign::Body", "Body")
        document.recompute()
        self.rect_sketch(body, "Profile", 0.0, 0.0, 8.0, 16.0)
        envelope = features.feature_pad(
            self.registry,
            doc=self.handle,
            body="Body",
            profile="Profile",
            name="AfterRestore",
            length=mm(5.0),
        )

        self.assert_volume(envelope, 8.0 * 16.0 * 5.0)

    def test_a_raise_after_the_snapshot_restore_still_rebinds_the_handle(self):
        """The rebind runs in a ``finally``, so it survives a raise on the way out of the bracket.

        The snapshot restore has already closed the caller's document by the time
        ``run_mutation`` returns, so a rebind skipped on the exception path would leave the handle
        holding a deleted object and every later call would fail on it.
        """
        self.keep_solid()
        original = self.document()

        def failing_op(document):
            ghost = document.addObject("Part::Box", "Ghost")
            ghost.Length, ghost.Width, ghost.Height = 1.0, 2.0, 3.0
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

        transaction.fingerprints_equal = once_unequal
        transaction.run_mutation = restore_then_break_the_caller
        try:
            with self.assertRaises(ValueError):
                features._feature_mutation(
                    self.registry, self.handle, "Keep", "raising exit", "test", {}, failing_op
                )
        finally:
            transaction.run_mutation = real_run
            transaction.fingerprints_equal = real_equal

        rebound = self.document()
        self.assertIsNot(rebound, original)
        self.assertIn(rebound, App.listDocuments().values())
        self.assertIsNotNone(rebound.getObject("Keep"))
        self.assertIsNone(rebound.getObject("Ghost"))


class CapabilityTest(_FeatureFixture):
    def test_every_feature_tool_refuses_when_partdesign_is_unavailable(self):
        from freecad_buddy.usecases import shim

        real_probe = shim.partdesign_available
        shim.partdesign_available = lambda: False
        try:
            for call, kwargs in (
                (features.feature_pad, {"body": "B", "profile": "P", "name": "N"}),
                (features.feature_pocket, {"body": "B", "profile": "P", "name": "N"}),
                (features.feature_revolve, {"body": "B", "profile": "P", "name": "N"}),
                (features.feature_hole, {"body": "B", "profile": "P", "name": "N"}),
                (features.feature_fillet, {"body": "B", "base": "P", "name": "N"}),
                (features.feature_chamfer, {"body": "B", "base": "P", "name": "N"}),
                (features.feature_pattern, {"body": "B", "name": "N", "kind": "linear"}),
                (features.feature_mirror, {"body": "B", "name": "N"}),
                (features.feature_datum, {"body": "B", "name": "N", "kind": "plane"}),
                (features.feature_set_parameters, {"feature": "F", "parameters": {"A": 1}}),
            ):
                with self.assertRaises(ValidationError):
                    call(self.registry, doc=self.handle, **kwargs)
        finally:
            shim.partdesign_available = real_probe

    def test_the_capability_banner_reports_partdesign_on_this_build(self):
        from freecad_buddy.usecases import shim

        banner = shim.capability_banner()
        self.assertIn("partdesign_available", banner)
        self.assertTrue(banner["partdesign_available"])


if __name__ == "__main__":
    unittest.main()
