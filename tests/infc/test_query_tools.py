"""In-FreeCAD read-only query-tool tests (stdlib unittest).

Run via ``FreeCADCmd tests/run_tests.py``. Builds a real box + a constrained sketch, then
exercises every ``query_*`` tool for shape, the mass-properties golden (analytic box volume),
the tree-summary cap path, the ``INVALID_INPUT`` cases through dispatch, and the read-only
guarantee (document state unchanged across a full query sweep).
"""

import math
import time
import unittest
from unittest import mock

import FreeCAD as App
import Part
import Sketcher

from freecad_buddy.adapters.rpc_dispatch import MethodRegistry, RpcMethod
from freecad_buddy.usecases import queries, shim
from freecad_buddy.usecases.documents import DocumentRegistry, ValidationError
from freecad_buddy.usecases.fingerprint import fingerprint

BOX_L = 10.0
BOX_W = 20.0
BOX_H = 30.0
ANALYTIC_VOLUME = BOX_L * BOX_W * BOX_H  # 6000 mm^3


class QueryToolsTest(unittest.TestCase):
    def setUp(self):
        self.registry = DocumentRegistry()
        self.handle = self.registry.document_create("query_tools")["structured_content"]["doc"]
        _, self.document = self.registry.with_document(self.handle, lambda h, d: (h, d))

        self.box = self.document.addObject("Part::Box", "Box")
        self.box.Length = BOX_L
        self.box.Width = BOX_W
        self.box.Height = BOX_H

        self.sketch = self.document.addObject("Sketcher::SketchObject", "Sketch")
        self.sketch.addGeometry(Part.LineSegment(App.Vector(0, 0, 0), App.Vector(40, 0, 0)), False)
        self.sketch.addGeometry(
            Part.LineSegment(App.Vector(40, 0, 0), App.Vector(40, 25, 0)), False
        )
        self.sketch.addConstraint(Sketcher.Constraint("DistanceX", 0, 40.0))
        self.sketch.addConstraint(Sketcher.Constraint("Angle", 0, 1, math.radians(90.0)))

        self.document.recompute()

    def _close_all(self):
        for name in list(App.listDocuments().keys()):
            App.closeDocument(name)

    def tearDown(self):
        self._close_all()

    def _dispatch(self) -> MethodRegistry:
        methods = MethodRegistry()
        for name, fn in (
            ("query_object", queries.query_object),
            ("query_mass_properties", queries.query_mass_properties),
            ("query_sketch_info", queries.query_sketch_info),
        ):
            methods.register(
                RpcMethod(
                    name=name,
                    handler=(lambda _fn: lambda **p: _fn(self.registry, **p))(fn),
                    mutating=False,
                )
            )
        return methods

    def test_tree_summary_returns_ok_with_tree_text_and_totals(self):
        envelope = queries.query_tree_summary(self.registry, doc=self.handle, depth=1)
        content = envelope["structured_content"]
        self.assertEqual(envelope["status"], "OK")
        self.assertEqual(content["total_objects"], 2)
        self.assertEqual(content["shown"], 2)
        self.assertEqual(envelope["text_blocks"], ["v [BOX] Box\nv [SKETCH] Sketch"])

    def test_tree_summary_focus_scopes_result(self):
        envelope = queries.query_tree_summary(self.registry, doc=self.handle, focus="Box")
        self.assertEqual(envelope["text_blocks"], ["path: Box\nv [BOX] Box"])

    def test_query_object_reports_type_and_null_error(self):
        envelope = queries.query_object(self.registry, doc=self.handle, object="Box")
        content = envelope["structured_content"]
        self.assertEqual(content["name"], "Box")
        self.assertEqual(content["type"], "Part::Box")
        self.assertIsNone(content["error"])
        self.assertIn("Length", content["properties"])

    def test_query_mass_properties_matches_analytic_volume(self):
        envelope = queries.query_mass_properties(self.registry, doc=self.handle, object="Box")
        content = envelope["structured_content"]
        volume = content["volume"]
        self.assertEqual(volume["unit"], "mm^3")
        self.assertLessEqual(abs(volume["value"] - ANALYTIC_VOLUME) / ANALYTIC_VOLUME, 0.001)
        self.assertEqual(content["area"]["unit"], "mm^2")
        self.assertEqual(content["com"]["x"]["unit"], "mm")
        self.assertEqual(content["counts"]["faces"], 6)
        self.assertEqual(content["counts"]["edges"], 12)
        self.assertEqual(content["counts"]["solids"], 1)

    def _add_shell(self, name="Shell"):
        shell = self.document.addObject("Part::Feature", name)
        shell.Shape = Part.makeBox(1, 1, 1).Shells[0]
        self.document.recompute()

    def test_Should_add_is_valid_to_the_record_When_one_object_is_queried(self):
        # Arrange
        target = queries.query_mass_properties

        # Act
        record = target(self.registry, doc=self.handle, object="Box")["structured_content"]

        # Assert
        self.assertIs(record["is_valid"], True)
        self.assertNotIn("objects", record)
        self.assertNotIn("shape", record)

    def test_Should_return_records_in_input_order_When_several_objects_are_queried(self):
        # Arrange
        self._add_shell()
        self.document.addObject("App::DocumentObjectGroup", "Group")
        target = queries.query_mass_properties
        names = ["Shell", "Box", "Group", "Box"]

        # Act
        envelope = target(self.registry, doc=self.handle, objects=names)

        # Assert
        records = envelope["structured_content"]["objects"]
        self.assertEqual(envelope["status"], "OK")
        self.assertEqual([record["name"] for record in records], names)
        self.assertIsNone(records[0]["volume"])
        self.assertIsNone(records[0]["com"])
        self.assertFalse(records[0]["solid"])
        self.assertLessEqual(abs(records[1]["volume"]["value"] - ANALYTIC_VOLUME), 1e-6)
        self.assertIs(records[1]["is_valid"], True)
        self.assertEqual(records[1]["counts"]["solids"], 1)
        self.assertNotIn("solids", records[1])
        self.assertEqual(records[2], {"name": "Group", "shape": None})
        self.assertEqual(records[3], records[1])

    def test_Should_return_a_null_shape_record_When_an_object_has_a_null_shape(self):
        # Arrange
        self.document.addObject("Part::Feature", "Empty")
        self.document.recompute()
        target = queries.query_mass_properties

        # Act
        envelope = target(self.registry, doc=self.handle, objects=["Empty"])

        # Assert
        self.assertEqual(
            envelope["structured_content"], {"objects": [{"name": "Empty", "shape": None}]}
        )

    def test_Should_return_a_null_shape_record_When_a_listed_object_is_an_empty_compound(self):
        # Arrange
        empty = self.document.addObject("Part::Feature", "EmptyCompound")
        empty.Shape = Part.makeCompound([])
        self.document.recompute()
        target = queries.query_mass_properties

        # Act
        envelope = target(self.registry, doc=self.handle, objects=["EmptyCompound", "Box"])

        # Assert
        records = envelope["structured_content"]["objects"]
        self.assertEqual(records[0], {"name": "EmptyCompound", "shape": None})
        self.assertEqual(records[1]["name"], "Box")

    def test_Should_reject_an_empty_name_When_it_is_listed_with_valid_names(self):
        # Arrange
        target = queries.query_mass_properties

        # Act
        def act():
            return target(self.registry, doc=self.handle, objects=["Box", ""])

        # Assert
        with self.assertRaisesRegex(ValidationError, "non-empty"):
            act()

    def test_Should_return_fifty_records_in_order_When_fifty_objects_are_dispatched(self):
        # Arrange
        self._add_shell()
        target = self._dispatch()
        names = ["Box", "Shell"] * 25

        # Act
        envelope = target.dispatch("query_mass_properties", {"doc": self.handle, "objects": names})

        # Assert
        records = envelope["structured_content"]["objects"]
        self.assertEqual(envelope["status"], "OK")
        self.assertEqual([record["name"] for record in records], names)

    def test_Should_equal_the_object_record_and_a_direct_shape_read_When_objects_is_used(self):
        # Arrange
        target = queries.query_mass_properties
        shape = self.box.Shape

        # Act
        single = target(self.registry, doc=self.handle, object="Box")["structured_content"]
        listed = target(self.registry, doc=self.handle, objects=["Box"])["structured_content"]

        # Assert
        record = listed["objects"][0]
        self.assertEqual(record, single)
        self.assertAlmostEqual(record["bbox"]["xmax"]["value"], shape.BoundBox.XMax, places=6)
        self.assertAlmostEqual(record["bbox"]["zmax"]["value"], shape.BoundBox.ZMax, places=6)
        self.assertAlmostEqual(record["volume"]["value"], shape.Volume, places=6)
        self.assertEqual(record["is_valid"], bool(shape.isValid()))

    def test_Should_report_is_valid_false_and_flag_the_summary_When_the_shape_is_invalid(self):
        # Arrange
        bowtie = Part.makePolygon(
            [
                App.Vector(*point)
                for point in [(0, 0, 0), (1, 1, 0), (1, 0, 0), (0, 1, 0), (0, 0, 0)]
            ]
        )
        invalid = self.document.addObject("Part::Feature", "Bowtie")
        invalid.Shape = Part.Face(bowtie)
        self.document.recompute()
        target = queries.query_mass_properties

        # Act
        single = target(self.registry, doc=self.handle, object="Bowtie")
        listed = target(self.registry, doc=self.handle, objects=["Bowtie", "Box"])

        # Assert
        self.assertIs(single["structured_content"]["is_valid"], False)
        self.assertIn("INVALID shape", single["text"])
        self.assertEqual(
            [record["is_valid"] for record in listed["structured_content"]["objects"]],
            [False, True],
        )

    def test_Should_raise_validation_error_When_the_input_form_or_list_is_wrong(self):
        # Arrange
        target = queries.query_mass_properties
        bad_inputs = [
            {"object": "Box", "objects": ["Box"]},
            {},
            {"objects": []},
            {"objects": ["Box"] * 51},
            {"objects": ["Box", 3]},
            {"objects": "Box"},
        ]

        for bad in bad_inputs:
            with self.subTest(bad=bad):
                # Act
                def act(bad=bad):
                    return target(self.registry, doc=self.handle, **bad)

                # Assert
                with self.assertRaises(ValidationError):
                    act()

    def test_Should_raise_validation_error_naming_the_object_When_a_listed_name_is_unknown(self):
        # Arrange
        target = queries.query_mass_properties

        # Act
        def act():
            return target(self.registry, doc=self.handle, objects=["Box", "Nope"])

        # Assert
        with self.assertRaisesRegex(ValidationError, "Nope"):
            act()

    def test_Should_map_both_or_neither_to_invalid_input_When_dispatched(self):
        # Arrange
        target = self._dispatch()
        calls = [
            {"doc": self.handle},
            {"doc": self.handle, "object": "Box", "objects": ["Box"]},
            {"doc": self.handle, "objects": []},
            {"doc": self.handle, "objects": ["Box"] * 51},
            {"doc": self.handle, "objects": ["Box", ""]},
            {"doc": self.handle, "objects": ["Box", "Nope"]},
        ]

        for arguments in calls:
            with self.subTest(arguments=arguments):
                # Act
                envelope = target.dispatch("query_mass_properties", arguments)

                # Assert
                self.assertEqual(envelope["status"], "INVALID_INPUT")

    def test_query_dependencies_object_and_whole_doc(self):
        group = self.document.addObject("App::DocumentObjectGroup", "Group")
        group.addObject(self.box)
        group.addObject(self.sketch)
        self.document.recompute()

        scoped = queries.query_dependencies(self.registry, doc=self.handle, object="Box")[
            "structured_content"
        ]
        self.assertEqual(scoped["object"], "Box")
        self.assertIsInstance(scoped["in_list"], list)
        self.assertIsInstance(scoped["out_list"], list)

        whole = queries.query_dependencies(self.registry, doc=self.handle)["structured_content"]
        self.assertIn("edges", whole)
        for edge in whole["edges"]:
            self.assertIn("from", edge)
            self.assertIn("to", edge)
        self.assertGreater(whole["total_edges"], 1)
        self.assertFalse(whole["truncated"])
        self.assertEqual(whole["total_edges"], whole["returned_edges"])
        self.assertEqual(whole["returned_edges"], len(whole["edges"]))

        capped = queries.query_dependencies(self.registry, doc=self.handle, max_edges=1)[
            "structured_content"
        ]
        self.assertTrue(capped["truncated"])
        self.assertEqual(capped["returned_edges"], 1)
        self.assertEqual(len(capped["edges"]), 1)
        self.assertEqual(capped["total_edges"], whole["total_edges"])
        self.assertEqual(capped["edges"], whole["edges"][:1])

        two = queries.query_dependencies(self.registry, doc=self.handle, max_edges=2)[
            "structured_content"
        ]
        self.assertEqual(two["edges"], whole["edges"][:2])

        with self.assertRaises(ValidationError):
            queries.query_dependencies(self.registry, doc=self.handle, max_edges=0)
        with self.assertRaises(ValidationError):
            queries.query_dependencies(self.registry, doc=self.handle, max_edges=1.5)
        with self.assertRaises(ValidationError):
            queries.query_dependencies(self.registry, doc=self.handle, max_edges=True)

    def test_query_sketch_info_lists_geometry_and_constraints(self):
        content = queries.query_sketch_info(self.registry, doc=self.handle, sketch="Sketch")[
            "structured_content"
        ]
        self.assertEqual(content["sketch"], "Sketch")
        self.assertEqual(len(content["geometry"]), 2)
        self.assertGreaterEqual(len(content["constraints"]), 2)

        by_type = {c["type"]: c for c in content["constraints"]}
        length = by_type["DistanceX"]
        self.assertEqual(length["id"], 1)
        self.assertIn("driving", length)
        self.assertEqual(length["value"]["unit"], "mm")
        self.assertAlmostEqual(length["value"]["value"], 40.0, places=3)

        angle = by_type["Angle"]
        self.assertEqual(angle["value"]["unit"], "deg")
        self.assertAlmostEqual(angle["value"]["value"], 90.0, places=3)

    def test_query_placement_local_and_global(self):
        content = queries.query_placement(self.registry, doc=self.handle, object="Box")[
            "structured_content"
        ]
        self.assertEqual(content["object"], "Box")
        for scope in ("local", "global"):
            self.assertEqual(content[scope]["angle"]["unit"], "deg")
            self.assertIn("position", content[scope])
            self.assertIn("axis", content[scope])

    def test_unknown_object_maps_to_invalid_input(self):
        envelope = self._dispatch().dispatch("query_object", {"doc": self.handle, "object": "Nope"})
        self.assertEqual(envelope["status"], "INVALID_INPUT")

    def test_non_sketch_maps_to_invalid_input(self):
        envelope = self._dispatch().dispatch(
            "query_sketch_info", {"doc": self.handle, "sketch": "Box"}
        )
        self.assertEqual(envelope["status"], "INVALID_INPUT")

    def test_object_without_shape_maps_to_invalid_input(self):
        self.document.addObject("App::DocumentObjectGroup", "Group")
        envelope = self._dispatch().dispatch(
            "query_mass_properties", {"doc": self.handle, "object": "Group"}
        )
        self.assertEqual(envelope["status"], "INVALID_INPUT")

    def test_null_shape_maps_to_invalid_input(self):
        # A Part::Feature with no assigned Shape has a present-but-null Shape property.
        self.document.addObject("Part::Feature", "Empty")
        self.document.recompute()
        envelope = self._dispatch().dispatch(
            "query_mass_properties", {"doc": self.handle, "object": "Empty"}
        )
        self.assertEqual(envelope["status"], "INVALID_INPUT")

    def test_query_sweep_is_read_only(self):
        def signature():
            return {
                obj.Name: (
                    round(obj.Shape.Volume, 6) if hasattr(obj, "Shape") else None,
                    tuple(round(v, 6) for v in tuple(obj.Placement.Base)),
                    tuple(obj.State),
                )
                for obj in self.document.Objects
            }

        before_count = len(self.document.Objects)
        before_sig = signature()

        queries.query_tree_summary(self.registry, doc=self.handle)
        queries.query_object(self.registry, doc=self.handle, object="Box")
        queries.query_mass_properties(self.registry, doc=self.handle, object="Box")
        queries.query_dependencies(self.registry, doc=self.handle)
        queries.query_sketch_info(self.registry, doc=self.handle, sketch="Sketch")
        queries.query_placement(self.registry, doc=self.handle, object="Box")

        self.assertEqual(before_count, len(self.document.Objects))
        self.assertEqual(before_sig, signature())


class QueryObjectDisplayTest(unittest.TestCase):
    """``query_object`` prints a Quantity or Vector property at the display precision."""

    def setUp(self):
        self.registry = DocumentRegistry()
        self.handle = self.registry.document_create("query_display")["structured_content"]["doc"]
        _, self.document = self.registry.with_document(self.handle, lambda h, d: (h, d))
        patcher = mock.patch.object(shim, "display_decimals", return_value=2)
        patcher.start()
        self.addCleanup(patcher.stop)

    def tearDown(self):
        for name in list(App.listDocuments().keys()):
            App.closeDocument(name)

    def test_should_read_the_displayed_length_when_a_pad_is_queried(self):
        # Arrange
        body = self.document.addObject("PartDesign::Body", "Body")
        sketch = body.newObject("Sketcher::SketchObject", "Sketch")
        corners = [
            App.Vector(0, 0, 0),
            App.Vector(10, 0, 0),
            App.Vector(10, 5, 0),
            App.Vector(0, 5, 0),
        ]
        for start, end in zip(corners, corners[1:] + corners[:1]):
            sketch.addGeometry(Part.LineSegment(start, end), False)
        pad = body.newObject("PartDesign::Pad", "Pad")
        pad.Profile = sketch
        pad.Length = 3.33333
        self.document.recompute()

        # Act
        envelope = queries.query_object(self.registry, doc=self.handle, object="Pad")

        # Assert
        self.assertEqual(envelope["structured_content"]["properties"]["Length"], "3.33 mm")

    def test_should_render_rounded_components_when_a_vector_is_made_json_safe(self):
        # Arrange
        vector = App.Vector(5.999999998, -4.281973375071899e-16, 1234.5678)

        # Act
        out = queries._json_safe(vector)

        # Assert
        self.assertEqual(out, "Vector (6.0, 0.0, 1234.57)")


class _FakeSolid:
    """A stand-in solid the interference trust check accepts; tests override the booleans."""

    ShapeType = "Solid"
    Volume = 1.0

    @staticmethod
    def isValid():
        return True


class QueryInterferenceTest(unittest.TestCase):
    def setUp(self):
        self.registry = DocumentRegistry()
        self.handle = self.registry.document_create("interference")["structured_content"]["doc"]
        _, self.document = self.registry.with_document(self.handle, lambda h, d: (h, d))

    def tearDown(self):
        for name in list(App.listDocuments().keys()):
            App.closeDocument(name)

    def _add_shape(self, name, shape):
        obj = self.document.addObject("Part::Feature", name)
        obj.Shape = shape
        return obj

    def _add_box(self, name, x=0.0, y=0.0, z=0.0, size=10.0):
        return self._add_shape(name, Part.makeBox(size, size, size, App.Vector(x, y, z)))

    def _add_bowtie(self, name):
        corners = [(0, 0), (10, 10), (10, 0), (0, 10), (0, 0)]
        wire = Part.makePolygon([App.Vector(x, y, 0) for x, y in corners])
        return self._add_shape(name, Part.Face(wire).extrude(App.Vector(0, 0, 10)))

    def _dispatch(self) -> MethodRegistry:
        methods = MethodRegistry()
        methods.register(
            RpcMethod(
                name="query_interference",
                handler=lambda **p: queries.query_interference(self.registry, **p),
                mutating=False,
            )
        )
        return methods

    def _measure(self, **arguments):
        return queries.query_interference(self.registry, doc=self.handle, **arguments)

    def test_Should_report_common_volume_and_zero_distance_When_two_boxes_overlap(self):
        # Arrange
        self._add_box("A")
        self._add_box("B", 5, 5, 5)

        # Act
        envelope = self._measure(objects=["A", "B"])

        # Assert
        record = envelope["structured_content"]["pairs"][0]
        self.assertEqual(envelope["status"], "OK")
        self.assertEqual((record["a"], record["b"]), ("A", "B"))
        self.assertAlmostEqual(record["common_volume"]["value"], 125.0, places=6)
        self.assertEqual(record["common_volume"]["unit"], "mm^3")
        self.assertEqual(record["min_distance"]["value"], 0.0)
        self.assertFalse(record["boolean_failed"])
        self.assertIn("A/B: common volume 125", envelope["text"])

    def test_Should_report_zero_volume_and_the_gap_When_two_boxes_are_disjoint(self):
        # Arrange
        self._add_box("A")
        self._add_box("B", 20, 0, 0)

        # Act
        envelope = self._measure(objects=["A", "B"])

        # Assert
        record = envelope["structured_content"]["pairs"][0]
        self.assertEqual(record["common_volume"]["value"], 0.0)
        self.assertAlmostEqual(record["min_distance"]["value"], 10.0, places=6)
        self.assertFalse(record["boolean_failed"])
        self.assertEqual(envelope["text"], "1 pair(s), 0 overlapping, 0 boolean failed.")

    def test_Should_flag_a_failed_boolean_When_one_shape_is_an_invalid_solid_at_distance_zero(self):
        # Arrange
        self._add_box("Box")
        bowtie = self._add_bowtie("Bowtie")

        # Act
        envelope = self._measure(pairs=[["Box", "Bowtie"]])

        # Assert
        record = envelope["structured_content"]["pairs"][0]
        self.assertFalse(bowtie.Shape.isValid())
        self.assertTrue(record["boolean_failed"])
        self.assertIsNone(record["common_volume"])
        self.assertIsNone(record["min_distance"])
        self.assertIn("BOOLEAN FAILED", envelope["text"])

    def test_Should_flag_a_failed_boolean_When_common_raises_and_the_distance_is_zero(self):
        # Arrange
        class RaisingShape(_FakeSolid):
            def common(self, other):
                raise RuntimeError("boolean failed")

            def distToShape(self, other):
                return (0.0, [], [])

        # Act
        volume, distance, failed = queries._measure_interference(RaisingShape(), RaisingShape())

        # Assert
        self.assertIsNone(volume)
        self.assertEqual(distance, 0.0)
        self.assertTrue(failed)

    def test_Should_flag_a_failed_boolean_When_common_raises_and_the_distance_is_unknown(self):
        # Arrange
        class BrokenShape(_FakeSolid):
            def common(self, other):
                raise RuntimeError("boolean failed")

            def distToShape(self, other):
                raise RuntimeError("distance failed")

        # Act
        volume, distance, failed = queries._measure_interference(BrokenShape(), BrokenShape())

        # Assert
        self.assertIsNone(volume)
        self.assertIsNone(distance)
        self.assertTrue(failed)

    def test_Should_report_zero_overlap_When_two_solids_only_touch(self):
        # Arrange
        touching_offsets = {
            "face": (10, 0, 0),
            "edge": (10, 10, 0),
            "vertex": (10, 10, 10),
        }
        self._add_box("A")
        for kind, offset in touching_offsets.items():
            self._add_box(f"B_{kind}", *offset)

        for kind in touching_offsets:
            with self.subTest(contact=kind):
                # Act
                envelope = self._measure(pairs=[["A", f"B_{kind}"]])

                # Assert
                record = envelope["structured_content"]["pairs"][0]
                self.assertEqual(envelope["status"], "OK")
                self.assertFalse(record["boolean_failed"])
                self.assertEqual(record["common_volume"]["value"], 0.0)
                self.assertEqual(record["min_distance"]["value"], 0.0)
                self.assertIn("0 overlapping, 0 boolean failed", envelope["text"])

    def test_Should_report_zero_overlap_When_a_pin_touches_the_wall_of_its_hole(self):
        # Arrange
        plate = Part.makeBox(40, 40, 10, App.Vector(-20, -20, 0)).cut(Part.makeCylinder(5, 10))
        self._add_shape("Plate", plate)
        self._add_shape("Pin", Part.makeCylinder(5, 10))

        # Act
        envelope = self._measure(objects=["Plate", "Pin"])

        # Assert
        record = envelope["structured_content"]["pairs"][0]
        self.assertFalse(record["boolean_failed"])
        self.assertEqual(record["common_volume"]["value"], 0.0)

    def test_Should_flag_a_failed_boolean_When_boxes_overlap_by_a_depth_that_leaves_common_empty(
        self,
    ):
        # Arrange
        depth = 1e-7
        self._add_box("A", size=100.0)
        self._add_box("B", 100.0 - depth, 0, 0, size=100.0)
        shape_a = self.document.A.Shape.copy()
        shape_b = self.document.B.Shape.copy()

        # Act
        envelope = self._measure(objects=["A", "B"])

        # Assert
        record = envelope["structured_content"]["pairs"][0]
        self.assertTrue(shape_a.common(shape_b).isNull() or not shape_a.common(shape_b).Volume)
        self.assertTrue(record["boolean_failed"])
        self.assertIsNone(record["common_volume"])

    def test_Should_flag_a_failed_boolean_When_the_fuse_loses_the_volume_of_a_solid_inside_another(
        self,
    ):
        # Arrange
        class Inner(_FakeSolid):
            Volume = 8.0

            def common(self, other):
                raise RuntimeError("boolean failed")

            def distToShape(self, other):
                return (0.0, [], [])

            def fuse(self, other):
                return Fused(valid=True, volume=27.0)

        class Fused:
            def __init__(self, valid, volume):
                self.valid = valid
                self.Volume = volume

            def isValid(self):
                return self.valid

        class Outer(Inner):
            Volume = 27.0

        # Act
        volume, distance, failed = queries._measure_interference(Inner(), Outer())

        # Assert
        self.assertEqual((volume, distance, failed), (None, 0.0, True))

    def test_Should_flag_a_failed_boolean_When_the_fuse_is_not_a_valid_shape(self):
        # Arrange
        class Fused:
            Volume = 2.0

            @staticmethod
            def isValid():
                return False

        class Shape(_FakeSolid):
            def common(self, other):
                raise RuntimeError("boolean failed")

            def distToShape(self, other):
                return (0.0, [], [])

            def fuse(self, other):
                return Fused()

        # Act
        volume, distance, failed = queries._measure_interference(Shape(), Shape())

        # Assert
        self.assertEqual((volume, distance, failed), (None, 0.0, True))

    def test_Should_flag_a_failed_boolean_When_the_fuse_raises_or_has_no_finite_volume(self):
        # Arrange
        class RaisingFuse(_FakeSolid):
            def common(self, other):
                raise RuntimeError("boolean failed")

            def distToShape(self, other):
                return (0.0, [], [])

            def fuse(self, other):
                raise RuntimeError("fuse failed")

        class NanFused:
            Volume = float("nan")

            @staticmethod
            def isValid():
                return True

        class NanFuse(RaisingFuse):
            def fuse(self, other):
                return NanFused()

        for shape_type in (RaisingFuse, NanFuse):
            with self.subTest(shape=shape_type.__name__):
                # Act
                result = queries._measure_interference(shape_type(), shape_type())

                # Assert
                self.assertEqual(result, (None, 0.0, True))

    def test_Should_not_run_the_fuse_When_the_distance_is_unknown(self):
        # Arrange
        class Shape(_FakeSolid):
            def common(self, other):
                raise RuntimeError("boolean failed")

            def distToShape(self, other):
                raise RuntimeError("distance failed")

            def fuse(self, other):
                raise AssertionError("the fuse must not run without a distance")

        # Act
        result = queries._measure_interference(Shape(), Shape())

        # Assert
        self.assertEqual(result, (None, None, True))

    def test_Should_report_zero_overlap_When_common_raises_and_a_valid_fuse_has_the_summed_volume(
        self,
    ):
        # Arrange
        class Fused:
            Volume = 2.0

            @staticmethod
            def isValid():
                return True

        class Shape(_FakeSolid):
            def common(self, other):
                raise RuntimeError("boolean failed")

            def distToShape(self, other):
                return (0.0, [], [])

            def fuse(self, other):
                return Fused()

        # Act
        result = queries._measure_interference(Shape(), Shape())

        # Assert
        self.assertEqual(result, (0.0, 0.0, False))

    def test_Should_accept_a_fuse_gap_inside_the_tolerance_and_refuse_one_above_it(self):
        # Arrange
        class Fused:
            def __init__(self, volume):
                self.Volume = volume

            @staticmethod
            def isValid():
                return True

        def shapes_fusing_to(volume):
            class Shape(_FakeSolid):
                def common(self, other):
                    raise RuntimeError("boolean failed")

                def distToShape(self, other):
                    return (0.0, [], [])

                def fuse(self, other):
                    return Fused(volume)

            return Shape(), Shape()

        tolerance = queries._TOUCH_VOLUME_REL_TOL
        inside_tolerance = 2.0 * (1.0 - tolerance * 0.5)
        above_tolerance = 2.0 * (1.0 - tolerance * 2.0)

        # Act
        at = queries._measure_interference(*shapes_fusing_to(inside_tolerance))
        above = queries._measure_interference(*shapes_fusing_to(above_tolerance))

        # Assert
        self.assertFalse(at[2])
        self.assertTrue(above[2])

    def test_Should_leave_a_fresh_fingerprint_digest_equal_When_touching_pairs_are_measured(self):
        # Arrange
        self._add_box("A")
        self._add_box("B", 10, 0, 0)
        self._add_box("C", 10, 10, 10)
        self.document.recompute()
        before = fingerprint(self.document, fresh=True)["digest"]

        # Act
        envelope = self._measure(objects=["A", "B", "C"])

        # Assert
        self.assertEqual(envelope["status"], "OK")
        self.assertEqual(fingerprint(self.document, fresh=True)["digest"], before)

    def test_Should_flag_a_failed_boolean_When_both_shapes_are_faces(
        self,
    ):
        # Arrange
        self._add_shape("PlaneA", Part.makePlane(10, 10, App.Vector(0, 0, 0)))
        self._add_shape("PlaneB", Part.makePlane(10, 10, App.Vector(5, 5, 0)))

        # Act
        envelope = self._measure(objects=["PlaneA", "PlaneB"])

        # Assert
        record = envelope["structured_content"]["pairs"][0]
        self.assertIsNone(record["common_volume"])
        self.assertTrue(record["boolean_failed"])

    def test_Should_measure_every_pair_in_order_When_objects_lists_three_names(self):
        # Arrange
        for index, name in enumerate(("A", "B", "C")):
            self._add_box(name, index * 30)

        # Act
        envelope = self._measure(objects=["A", "B", "C"])

        # Assert
        pairs = [(r["a"], r["b"]) for r in envelope["structured_content"]["pairs"]]
        self.assertEqual(pairs, [("A", "B"), ("A", "C"), ("B", "C")])

    def test_Should_measure_the_given_pairs_in_input_order_When_pairs_is_used(self):
        # Arrange
        for index, name in enumerate(("A", "B", "C")):
            self._add_box(name, index * 30)

        # Act
        envelope = self._measure(pairs=[["C", "A"], ["B", "C"]])

        # Assert
        pairs = [(r["a"], r["b"]) for r in envelope["structured_content"]["pairs"]]
        self.assertEqual(pairs, [("C", "A"), ("B", "C")])

    def test_Should_map_bad_input_to_invalid_input_When_dispatched(self):
        # Arrange
        self._add_box("A")
        self._add_box("B", 30)
        self.document.addObject("App::DocumentObjectGroup", "Group")
        for index in range(21):
            self._add_box(f"A{index}", index * 30, 100)
        target = self._dispatch()
        calls = [
            {"doc": self.handle},
            {"doc": self.handle, "objects": ["A", "B"], "pairs": [["A", "B"]]},
            {"doc": self.handle, "objects": ["A"]},
            {"doc": self.handle, "objects": ["A", "B", "A"]},
            {"doc": self.handle, "objects": ["A", ""]},
            {"doc": self.handle, "objects": [f"A{i}" for i in range(21)]},
            {"doc": self.handle, "pairs": []},
            {"doc": self.handle, "pairs": [["A"]]},
            {"doc": self.handle, "pairs": [["A", "A"]]},
            {"doc": self.handle, "pairs": [["A", "B"]] * 101},
            {"doc": self.handle, "objects": ["A", "Nope"]},
            {"doc": self.handle, "objects": ["A", "Group"]},
        ]

        for arguments in calls:
            with self.subTest(arguments=arguments):
                # Act
                envelope = target.dispatch("query_interference", arguments)

                # Assert
                self.assertEqual(envelope["status"], "INVALID_INPUT")

    def test_Should_name_the_object_When_a_listed_name_is_unknown_or_has_no_shape(self):
        # Arrange
        self._add_box("A")
        self.document.addObject("App::DocumentObjectGroup", "Group")

        # Act
        act_unknown = lambda: self._measure(objects=["A", "Nope"])  # noqa: E731
        act_no_shape = lambda: self._measure(objects=["A", "Group"])  # noqa: E731

        # Assert
        with self.assertRaisesRegex(ValidationError, "unknown object: Nope"):
            act_unknown()
        with self.assertRaisesRegex(ValidationError, "no queryable shape: Group"):
            act_no_shape()

    def test_Should_leave_the_document_unchanged_When_pairs_are_measured(self):
        # Arrange
        self._add_box("A")
        self._add_box("B", 5, 5, 5)
        self.document.recompute()
        names_before = [obj.Name for obj in self.document.Objects]
        volume_before = self.document.A.Shape.Volume

        # Act
        self._measure(objects=["A", "B"])

        # Assert
        self.assertEqual([obj.Name for obj in self.document.Objects], names_before)
        self.assertEqual(self.document.A.Shape.Volume, volume_before)

    def test_Should_flag_a_failed_boolean_When_common_has_a_negative_volume(self):
        # Arrange
        class ReversedCommon:
            Volume = -5.0

            def isNull(self):
                return False

            class BoundBox:
                @staticmethod
                def isValid():
                    return True

        class Shape(_FakeSolid):
            def common(self, other):
                return ReversedCommon()

        # Act
        volume, distance, failed = queries._measure_interference(Shape(), Shape())

        # Assert
        self.assertEqual((volume, distance, failed), (None, None, True))

    def test_Should_flag_a_failed_boolean_When_common_volume_is_not_a_number(self):
        # Arrange
        class NanCommon:
            Volume = float("nan")

            def isNull(self):
                return False

            class BoundBox:
                @staticmethod
                def isValid():
                    return True

        class Shape(_FakeSolid):
            def common(self, other):
                return NanCommon()

        # Act
        volume, distance, failed = queries._measure_interference(Shape(), Shape())

        # Assert
        self.assertEqual((volume, distance, failed), (None, None, True))

    def test_Should_report_no_overlap_When_common_raises_but_the_distance_is_positive(self):
        # Arrange
        class Shape(_FakeSolid):
            def common(self, other):
                raise RuntimeError("boolean failed")

            def distToShape(self, other):
                return (3.5, [], [])

        # Act
        volume, distance, failed = queries._measure_interference(Shape(), Shape())

        # Assert
        self.assertEqual((volume, distance, failed), (0.0, 3.5, False))

    def test_Should_refuse_an_object_with_a_null_or_empty_shape_When_it_is_listed(self):
        # Arrange
        self._add_box("A")
        self.document.addObject("Part::Feature", "NullShape")
        self._add_shape("EmptyCompound", Part.Compound([]))

        for name in ("NullShape", "EmptyCompound"):
            with self.subTest(name=name):
                # Act
                act = lambda: self._measure(objects=["A", name])  # noqa: E731

                # Assert
                with self.assertRaisesRegex(ValidationError, f"no queryable shape: {name}"):
                    act()

    def test_Should_name_the_object_When_a_pair_repeats_one_name(self):
        # Arrange
        self._add_box("A")

        # Act
        act = lambda: self._measure(pairs=[["A", "A"]])  # noqa: E731

        # Assert
        with self.assertRaisesRegex(ValidationError, "two different objects: A"):
            act()

    def test_Should_not_change_placement_or_state_When_pairs_are_measured(self):
        # Arrange
        self._add_box("A")
        self._add_box("B", 5, 5, 5)
        self.document.recompute()

        def signature():
            return {
                obj.Name: (tuple(obj.Placement.Base), tuple(obj.State), obj.Shape.Volume)
                for obj in self.document.Objects
            }

        before = signature()
        undo_before = self.document.UndoCount

        # Act
        self._measure(objects=["A", "B"])

        # Assert
        self.assertEqual(signature(), before)
        self.assertEqual(self.document.UndoCount, undo_before)

    def _add_bowtie_100(self, name):
        corners = [(0, 0), (100, 100), (100, 0), (0, 100), (0, 0)]
        wire = Part.makePolygon([App.Vector(x, y, 0) for x, y in corners])
        return self._add_shape(name, Part.Face(wire).extrude(App.Vector(0, 0, 100)))

    def test_Should_flag_a_failed_boolean_When_an_invalid_solid_contains_the_other_shape(self):
        # Arrange
        bowtie = self._add_bowtie_100("Bowtie")
        self._add_box("InLobe", 70, 40, 40)
        direct_distance = bowtie.Shape.distToShape(self.document.InLobe.Shape)[0]

        # Act
        envelope = self._measure(pairs=[["Bowtie", "InLobe"]])

        # Assert
        record = envelope["structured_content"]["pairs"][0]
        self.assertFalse(bowtie.Shape.isValid())
        self.assertGreater(direct_distance, 0.0)
        self.assertTrue(record["boolean_failed"])
        self.assertIsNone(record["common_volume"])
        self.assertIsNone(record["min_distance"])

    def test_Should_flag_a_failed_boolean_When_a_reversed_solid_contains_the_other_shape(self):
        # Arrange
        self._add_shape("Rev", Part.makeBox(100, 100, 100).reversed())
        self._add_box("Small", 40, 40, 40)
        self._add_box("Big", 0, 0, 0, size=100)

        # Act
        reversed_pair = self._measure(pairs=[["Rev", "Small"]])["structured_content"]["pairs"][0]
        plain_pair = self._measure(pairs=[["Big", "Small"]])["structured_content"]["pairs"][0]

        # Assert
        self.assertTrue(self.document.Rev.Shape.isValid())
        self.assertLess(self.document.Rev.Shape.Volume, 0.0)
        self.assertTrue(reversed_pair["boolean_failed"])
        self.assertIsNone(reversed_pair["common_volume"])
        self.assertAlmostEqual(plain_pair["common_volume"]["value"], 1000.0, places=6)

    def test_Should_flag_a_failed_boolean_When_a_reversed_solid_overlaps_a_box(self):
        # Arrange
        self._add_shape("Rev", Part.makeBox(100, 100, 100).reversed())
        self._add_box("Corner", 95, 95, 95)

        # Act
        envelope = self._measure(pairs=[["Rev", "Corner"]])

        # Assert
        record = envelope["structured_content"]["pairs"][0]
        self.assertTrue(record["boolean_failed"])
        self.assertIsNone(record["common_volume"])

    def test_Should_flag_a_failed_boolean_When_a_closed_shell_contains_a_solid(self):
        # Arrange
        self._add_shape("Shell", Part.Shell(Part.makeBox(100, 100, 100).Faces))
        self._add_box("Inside", 40, 40, 40)

        # Act
        envelope = self._measure(pairs=[["Shell", "Inside"]])

        # Assert
        record = envelope["structured_content"]["pairs"][0]
        self.assertEqual(self.document.Shell.Shape.ShapeType, "Shell")
        self.assertTrue(record["boolean_failed"])
        self.assertIsNone(record["common_volume"])
        self.assertIsNone(record["min_distance"])

    def test_Should_flag_a_failed_boolean_When_a_compound_holds_a_face_beside_a_solid(self):
        # Arrange
        mixed = Part.Compound(
            [Part.makeBox(10, 10, 10), Part.makePlane(5, 5, App.Vector(50, 0, 0))]
        )
        self._add_shape("Mixed", mixed)
        self._add_box("Other", 5, 5, 5)

        # Act
        envelope = self._measure(pairs=[["Mixed", "Other"]])

        # Assert
        self.assertTrue(envelope["structured_content"]["pairs"][0]["boolean_failed"])

    def test_Should_measure_the_pair_When_both_shapes_are_compounds_of_valid_solids(self):
        # Arrange
        self._add_shape(
            "Group",
            Part.Compound(
                [Part.makeBox(10, 10, 10), Part.makeBox(10, 10, 10, App.Vector(50, 0, 0))]
            ),
        )
        self._add_box("Other", 5, 5, 5)

        # Act
        envelope = self._measure(pairs=[["Group", "Other"]])

        # Assert
        record = envelope["structured_content"]["pairs"][0]
        self.assertFalse(record["boolean_failed"])
        self.assertAlmostEqual(record["common_volume"]["value"], 125.0, places=6)

    def test_Should_not_count_a_pair_as_overlapping_When_its_volume_rounds_to_zero(self):
        # Arrange
        sc = {
            "pairs": [
                {
                    "a": "A",
                    "b": "B",
                    "common_volume": {"value": 1.25e-10, "unit": "mm^3"},
                    "min_distance": {"value": 0.0, "unit": "mm"},
                    "boolean_failed": False,
                }
            ]
        }

        # Act
        text = queries.summarize_interference(sc)

        # Assert
        self.assertEqual(text, "1 pair(s), 0 overlapping, 0 boolean failed.")

    def test_Should_report_zero_volume_When_common_is_a_non_empty_zero_volume_shape(self):
        # Arrange
        class ZeroVolumeCommon:
            Volume = 0.0

            def isNull(self):
                return False

            class BoundBox:
                @staticmethod
                def isValid():
                    return True

        class Shape(_FakeSolid):
            def common(self, other):
                return ZeroVolumeCommon()

            def distToShape(self, other):
                return (0.0, [], [])

        # Act
        volume, distance, failed = queries._measure_interference(Shape(), Shape())

        # Assert
        self.assertEqual((volume, distance, failed), (0.0, 0.0, False))

    def test_Should_flag_a_failed_boolean_When_a_zero_volume_common_has_no_distance(self):
        # Arrange
        class ZeroVolumeCommon:
            Volume = 0.0

            def isNull(self):
                return False

            class BoundBox:
                @staticmethod
                def isValid():
                    return True

        class Shape(_FakeSolid):
            def common(self, other):
                return ZeroVolumeCommon()

            def distToShape(self, other):
                raise RuntimeError("distance failed")

        # Act
        volume, distance, failed = queries._measure_interference(Shape(), Shape())

        # Assert
        self.assertEqual((volume, distance, failed), (None, None, True))

    def test_Should_fail_only_the_pairs_with_the_untrusted_object_When_objects_mixes_shapes(self):
        # Arrange
        self._add_shape("Shell", Part.Shell(Part.makeBox(10, 10, 10).Faces))
        self._add_box("A", 5, 5, 5)
        self._add_box("B", 100, 0, 0)

        # Act
        envelope = self._measure(objects=["Shell", "A", "B"])

        # Assert
        records = envelope["structured_content"]["pairs"]
        self.assertEqual(
            [(r["a"], r["b"]) for r in records], [("Shell", "A"), ("Shell", "B"), ("A", "B")]
        )
        self.assertEqual([r["boolean_failed"] for r in records], [True, True, False])
        self.assertAlmostEqual(records[2]["min_distance"]["value"], 85.0, places=6)

    def test_Should_refuse_the_call_with_a_code_When_a_pair_is_above_the_face_limit(self):
        # Arrange
        three_boxes = Part.Compound(
            [Part.makeBox(1, 1, 1, App.Vector(i * 5, 0, 0)) for i in range(3)]
        )
        self._add_shape("Big1", three_boxes)
        self._add_shape("Big2", three_boxes.translated(App.Vector(0, 50, 0)))
        target = self._dispatch()

        # Act
        with mock.patch.object(queries, "_MAX_PAIR_FACE_PRODUCT", 300):
            envelope = target.dispatch(
                "query_interference", {"doc": self.handle, "pairs": [["Big1", "Big2"]]}
            )

        # Assert
        self.assertEqual(envelope["status"], "INVALID_INPUT")
        self.assertEqual(envelope["detail"]["code"], "interference.too_complex")
        self.assertIn("Big1/Big2", envelope["detail"]["message"])

    def test_Should_measure_the_pair_When_it_is_at_the_face_limit(self):
        # Arrange
        three_boxes = Part.Compound(
            [Part.makeBox(1, 1, 1, App.Vector(i * 5, 0, 0)) for i in range(3)]
        )
        self._add_shape("Big1", three_boxes)
        self._add_shape("Big2", three_boxes.translated(App.Vector(0, 50, 0)))

        # Act
        with mock.patch.object(queries, "_MAX_PAIR_FACE_PRODUCT", 18 * 18):
            envelope = self._measure(pairs=[["Big1", "Big2"]])

        # Assert
        self.assertEqual(envelope["status"], "OK")
        self.assertFalse(envelope["structured_content"]["pairs"][0]["boolean_failed"])

    def test_Should_stop_with_a_code_and_the_count_When_the_deadline_passes_between_pairs(self):
        # Arrange
        for index in range(4):
            self._add_box(f"Box{index}", index * 30)
        names = [f"Box{index}" for index in range(4)]
        ticks = iter([0.0, 0.0, 10.0, 41.0, 41.0])

        # Act
        envelope = queries.query_interference(
            self.registry, doc=self.handle, objects=names, clock=lambda: next(ticks)
        )

        # Assert
        self.assertEqual(envelope["status"], "INVALID_INPUT")
        self.assertEqual(envelope["detail"]["code"], "interference.too_complex")
        self.assertEqual(
            envelope["detail"]["message"],
            "stopped after 2 of 6 pairs; measure fewer pairs per call",
        )

    def test_Should_measure_every_pair_When_the_clock_stays_inside_the_deadline(self):
        # Arrange
        for index in range(4):
            self._add_box(f"Box{index}", index * 30)
        names = [f"Box{index}" for index in range(4)]

        # Act
        envelope = queries.query_interference(
            self.registry, doc=self.handle, objects=names, clock=lambda: 40.0
        )

        # Assert
        self.assertEqual(envelope["status"], "OK")
        self.assertEqual(len(envelope["structured_content"]["pairs"]), 6)

    def test_Should_leave_a_fresh_fingerprint_digest_equal_When_pairs_are_measured(self):
        # Arrange
        from freecad_buddy.usecases.fingerprint import fingerprint

        for index, name in enumerate(("A", "B", "C")):
            box = self.document.addObject("Part::Box", name)
            box.Placement.Base = App.Vector(index * 30, 0, 0)
        self.document.recompute()
        before = fingerprint(self.document, fresh=True)["digest"]

        # Act
        self._measure(objects=["A", "B", "C"])

        # Assert
        self.assertEqual(fingerprint(self.document, fresh=True)["digest"], before)

    def test_Should_finish_inside_the_query_budget_When_twenty_realistic_objects_are_measured(self):
        # Arrange
        budget_seconds = 60.0
        for index in range(20):
            drilled = Part.makeBox(20, 20, 20, App.Vector(index * 9, 0, 0)).cut(
                Part.makeCylinder(4, 20, App.Vector(index * 9 + 10, 10, 0))
            )
            self._add_shape(f"Part{index}", drilled)
        names = [f"Part{index}" for index in range(20)]
        started = time.monotonic()

        # Act
        envelope = self._measure(objects=names)

        # Assert
        elapsed = time.monotonic() - started
        self.assertEqual(len(envelope["structured_content"]["pairs"]), 190)
        self.assertLess(elapsed, budget_seconds)


def _coil_spring(turns):
    helix = Part.makeHelix(6, 6 * turns, 20)
    circle = Part.Wire(Part.makeCircle(1, App.Vector(20, 0, 0), App.Vector(0, 1, 0)))
    return Part.Wire(helix).makePipeShell([circle], True, True)


def _prism(sides):
    corners = [
        App.Vector(
            50 * math.cos(2 * math.pi * i / sides), 50 * math.sin(2 * math.pi * i / sides), 0
        )
        for i in range(sides)
    ]
    outline = Part.makePolygon(corners + [corners[0]])
    return Part.Face(outline).extrude(App.Vector(0, 0, 10))


def _hex_hole_plate(holes):
    columns = 40
    plate = Part.makeBox(columns * 6 + 6, (holes // columns + 1) * 6 + 6, 10)
    prisms = []
    for index in range(holes):
        center = App.Vector(7 + 6 * (index % columns), 7 + 6 * (index // columns), 0)
        corners = [
            center + App.Vector(2 * math.cos(math.pi / 3 * k), 2 * math.sin(math.pi / 3 * k), 0)
            for k in range(6)
        ]
        prisms.append(
            Part.Face(Part.makePolygon(corners + [corners[0]])).extrude(App.Vector(0, 0, 10))
        )
    return plate.cut(Part.makeCompound(prisms))


class QuerySectionTest(unittest.TestCase):
    def setUp(self):
        self.registry = DocumentRegistry()
        self.handle = self.registry.document_create("section")["structured_content"]["doc"]
        _, self.document = self.registry.with_document(self.handle, lambda h, d: (h, d))

    def tearDown(self):
        for name in list(App.listDocuments().keys()):
            App.closeDocument(name)

    def _add_shape(self, name, shape):
        obj = self.document.addObject("Part::Feature", name)
        obj.Shape = shape
        return obj

    def _box(self, name="Box"):
        return self._add_shape(name, Part.makeBox(BOX_L, BOX_W, BOX_H))

    def _section(self, name="Box", normal="z", offset=15.0, **extra):
        plane = {"normal": normal, "offset": {"value": offset, "unit": "mm"}}
        return queries.query_section(
            self.registry, doc=self.handle, object=name, plane=plane, **extra
        )

    def _points(self, deflection=0.1, **extra):
        return {"points": {"deflection": {"value": deflection, "unit": "mm"}, **extra}}

    def _dispatch(self) -> MethodRegistry:
        methods = MethodRegistry()
        methods.register(
            RpcMethod(
                name="query_section",
                handler=lambda **p: queries.query_section(self.registry, **p),
                mutating=False,
            )
        )
        return methods

    def test_Should_report_one_closed_wire_with_analytic_values_When_a_box_is_cut_mid_height(self):
        # Arrange
        self._box()

        # Act
        envelope = self._section(offset=15.0)

        # Assert
        result = envelope["structured_content"]
        self.assertEqual(envelope["status"], "OK")
        self.assertEqual((result["wires"], result["closed_wires"]), (1, 1))
        self.assertAlmostEqual(result["area"]["value"], BOX_L * BOX_W, places=6)
        self.assertEqual(result["area"]["unit"], "mm^2")
        self.assertAlmostEqual(result["length"]["value"], 2 * (BOX_L + BOX_W), places=6)
        self.assertAlmostEqual(result["bbox"]["zmin"]["value"], 15.0, places=6)
        self.assertAlmostEqual(result["bbox"]["xmax"]["value"], BOX_L, places=6)
        self.assertNotIn("polylines", result)

    def test_Should_not_read_a_miss_When_the_plane_is_within_1e5_mm_of_a_face(self):
        # Arrange
        self._box()
        offsets = [1e-6, 1e-5, 1e-4, BOX_H - 1e-5, BOX_H - 1e-6]

        for offset in offsets:
            with self.subTest(offset=offset):
                # Act
                result = self._section(offset=offset)["structured_content"]

                # Assert
                self.assertEqual((result["wires"], result["closed_wires"]), (1, 1))
                self.assertAlmostEqual(result["area"]["value"], BOX_L * BOX_W, places=6)

    def test_Should_report_zero_values_and_a_null_box_When_the_plane_misses_the_shape(self):
        # Arrange
        self._box()

        # Act
        envelope = self._section(offset=BOX_H + 10)

        # Assert
        result = envelope["structured_content"]
        self.assertEqual(envelope["status"], "OK")
        self.assertEqual((result["wires"], result["closed_wires"]), (0, 0))
        self.assertEqual(result["area"]["value"], 0.0)
        self.assertEqual(result["length"]["value"], 0.0)
        self.assertIsNone(result["bbox"])

    def test_Should_subtract_the_hole_from_the_area_When_a_plate_with_a_hole_is_cut(self):
        # Arrange
        plate = Part.makeBox(100, 100, 10).cut(Part.makeCylinder(10, 10, App.Vector(50, 50, 0)))
        self._add_shape("Plate", plate)

        # Act
        result = self._section("Plate", offset=5.0)["structured_content"]

        # Assert
        self.assertEqual((result["wires"], result["closed_wires"]), (2, 2))
        self.assertAlmostEqual(result["area"]["value"], 10000 - math.pi * 100, places=4)
        self.assertAlmostEqual(result["length"]["value"], 400 + 2 * math.pi * 10, places=4)

    def test_Should_add_the_island_area_When_a_solid_sits_inside_a_hole_of_another(self):
        # Arrange
        frame = Part.makeBox(100, 100, 10).cut(Part.makeBox(60, 60, 10, App.Vector(20, 20, 0)))
        island = Part.makeBox(20, 20, 10, App.Vector(40, 40, 0))
        self._add_shape("Nest", Part.makeCompound([frame, island]))

        # Act
        result = self._section("Nest", offset=5.0)["structured_content"]

        # Assert
        self.assertEqual(result["wires"], 3)
        self.assertAlmostEqual(result["area"]["value"], 10000 - 3600 + 400, places=4)

    def test_Should_match_the_analytic_hexagon_When_the_plane_is_oblique_through_a_cube(self):
        # Arrange
        self._add_shape("Cube", Part.makeBox(10, 10, 10))
        hexagon_area = 3 * math.sqrt(3) / 4 * 100
        offset = 15 / math.sqrt(3)

        # Act
        result = self._section("Cube", normal=[1, 1, 1], offset=offset)["structured_content"]

        # Assert
        self.assertEqual((result["wires"], result["closed_wires"]), (1, 1))
        self.assertAlmostEqual(result["area"]["value"], hexagon_area, places=4)

    def test_Should_cut_the_same_plane_When_the_normal_is_an_axis_name_or_a_scaled_vector(self):
        # Arrange
        self._box()

        # Act
        named = self._section(normal="z", offset=15.0)["structured_content"]
        scaled = self._section(normal=[0, 0, 5], offset=15.0)["structured_content"]

        # Assert
        self.assertEqual(named, scaled)

    def test_Should_return_wires_and_length_with_a_null_area_When_a_valid_shell_is_cut(self):
        # Arrange
        shell = Part.Shell(Part.makeBox(BOX_L, BOX_W, BOX_H).Faces)
        self._add_shape("Shell", shell)

        # Act
        envelope = self._section("Shell", offset=15.0)

        # Assert
        result = envelope["structured_content"]
        self.assertEqual(envelope["status"], "OK")
        self.assertEqual((result["wires"], result["closed_wires"]), (1, 1))
        self.assertAlmostEqual(result["length"]["value"], 2 * (BOX_L + BOX_W), places=6)
        self.assertIsNone(result["area"])
        self.assertIn("area unmeasured", envelope["text"])

    def test_Should_return_a_null_area_not_zero_When_the_boolean_gives_no_area(self):
        # Arrange
        self._box()

        # Act
        with mock.patch.object(queries, "_section_area", return_value=None):
            envelope = self._section(offset=15.0)

        # Assert
        result = envelope["structured_content"]
        self.assertEqual(result["wires"], 1)
        self.assertIsNone(result["area"])

    def test_Should_return_none_When_the_boolean_raises_or_returns_an_empty_shape(self):
        # Arrange
        class RaisingShape:
            @staticmethod
            def common(_other):
                raise RuntimeError("boolean failed")

        class EmptyShape:
            @staticmethod
            def common(_other):
                return Part.Shape()

        # Act
        raised = queries._section_area(RaisingShape(), object())
        empty = queries._section_area(EmptyShape(), object())

        # Assert
        self.assertIsNone(raised)
        self.assertIsNone(empty)

    def test_Should_refuse_with_a_code_When_the_shape_is_invalid_reversed_or_has_no_face(self):
        # Arrange
        corners = [(0, 0), (10, 10), (10, 0), (0, 10), (0, 0)]
        bowtie = Part.Face(Part.makePolygon([App.Vector(x, y, 0) for x, y in corners]))
        reversed_box = Part.makeBox(10, 10, 10)
        reversed_box.reverse()
        shapes = {
            "Bowtie": bowtie.extrude(App.Vector(0, 0, 10)),
            "Reversed": reversed_box,
            "Wire": Part.makePolygon([App.Vector(0, 0, 0), App.Vector(10, 0, 0)]),
        }
        for name, shape in shapes.items():
            self._add_shape(name, shape)

        for name in shapes:
            with self.subTest(name=name):
                # Act
                envelope = self._section(name, offset=5.0)

                # Assert
                self.assertEqual(envelope["status"], "INVALID_INPUT")
                self.assertEqual(envelope["detail"]["code"], "section.untrusted_shape")
                self.assertIn(name, envelope["detail"]["message"])

    def test_Should_refuse_before_cutting_When_the_face_count_is_above_the_limit(self):
        # Arrange
        self._box()

        # Act
        with mock.patch.object(queries, "_MAX_SECTION_FACES", 5):
            envelope = self._section()

        # Assert
        self.assertEqual(envelope["status"], "INVALID_INPUT")
        self.assertEqual(envelope["detail"]["code"], "section.too_complex")
        self.assertIn("6 faces", envelope["detail"]["message"])

    def test_Should_cut_the_shape_When_the_face_count_is_at_the_limit(self):
        # Arrange
        self._box()

        # Act
        with mock.patch.object(queries, "_MAX_SECTION_FACES", 6):
            envelope = self._section()

        # Assert
        self.assertEqual(envelope["status"], "OK")

    def test_Should_return_polylines_on_the_circle_When_points_are_requested(self):
        # Arrange
        radius = 50.0
        self._add_shape("Ball", Part.makeSphere(radius))

        # Act
        result = self._section("Ball", normal="x", offset=0.0, **self._points(0.1))[
            "structured_content"
        ]

        # Assert
        self.assertAlmostEqual(result["length"]["value"], 2 * math.pi * radius, places=4)
        self.assertAlmostEqual(result["area"]["value"], math.pi * radius**2, places=3)
        self.assertFalse(result["truncated"])
        (polyline,) = result["polylines"]
        self.assertGreater(len(polyline), 10)
        for x, y, z in polyline:
            self.assertAlmostEqual(x, 0.0, places=6)
            self.assertAlmostEqual(math.hypot(y, z), radius, delta=0.1)

    def test_Should_stop_at_max_points_and_flag_truncation_When_the_polyline_is_longer(self):
        # Arrange
        self._add_shape("Ball", Part.makeSphere(50))

        # Act
        envelope = self._section("Ball", normal="x", offset=0.0, **self._points(0.1, max_points=5))

        # Assert
        result = envelope["structured_content"]
        self.assertEqual(sum(len(line) for line in result["polylines"]), 5)
        self.assertTrue(result["truncated"])
        self.assertIn("truncated", envelope["text"])

    def test_Should_keep_whole_wires_within_the_total_cap_When_there_are_several_wires(self):
        # Arrange
        plate = Part.makeBox(100, 100, 10).cut(Part.makeCylinder(10, 10, App.Vector(50, 50, 0)))
        self._add_shape("Plate", plate)
        cap = 5000

        # Act
        result = self._section("Plate", offset=5.0, **self._points(0.5, max_points=cap))[
            "structured_content"
        ]

        # Assert
        self.assertEqual(len(result["polylines"]), 2)
        self.assertLessEqual(sum(len(line) for line in result["polylines"]), cap)
        self.assertFalse(result["truncated"])

    def test_Should_drop_whole_wires_and_flag_truncation_When_the_cap_leaves_no_room(self):
        # Arrange
        plate = Part.makeBox(100, 100, 10).cut(Part.makeCylinder(10, 10, App.Vector(50, 50, 0)))
        self._add_shape("Plate", plate)

        # Act
        result = self._section("Plate", offset=5.0, **self._points(0.5, max_points=4))[
            "structured_content"
        ]

        # Assert
        self.assertEqual(sum(len(line) for line in result["polylines"]), 4)
        self.assertEqual(len(result["polylines"]), 1)
        self.assertTrue(result["truncated"])

    def test_Should_raise_When_the_plane_or_points_are_malformed(self):
        # Arrange
        self._box()
        good = {"value": 1.0, "unit": "mm"}
        planes = [
            None,
            {"normal": "z"},
            {"normal": "w", "offset": good},
            {"normal": [0, 0, 0], "offset": good},
            {"normal": [1, 0], "offset": good},
            {"normal": [1, 0, float("nan")], "offset": good},
            {"normal": [True, 0, 0], "offset": good},
            {"normal": "z", "offset": {"value": float("nan"), "unit": "mm"}},
            {"normal": "z", "offset": {"value": 1.0, "unit": "deg"}},
            {"normal": "z", "offset": 1.0},
            {"normal": "z", "offset": good, "extra": 1},
        ]
        plane_good = {"normal": "z", "offset": good}
        diagonal = Part.makeBox(BOX_L, BOX_W, BOX_H).BoundBox.DiagonalLength
        below_floor = {"value": diagonal * 1e-7, "unit": "mm"}
        points_list = [
            {},
            {"deflection": {"value": 0.0, "unit": "mm"}},
            {"deflection": {"value": -1.0, "unit": "mm"}},
            {"deflection": below_floor},
            {"deflection": good, "max_points": 0},
            {"deflection": good, "max_points": 1},
            {"deflection": good, "max_points": 5001},
            {"deflection": good, "max_points": True},
            {"deflection": good, "max_points": 2.5},
            {"deflection": good, "extra": 1},
        ]

        # Act
        acts = [
            lambda plane=plane: queries.query_section(
                self.registry, doc=self.handle, object="Box", plane=plane
            )
            for plane in planes
        ] + [
            lambda points=points: queries.query_section(
                self.registry, doc=self.handle, object="Box", plane=plane_good, points=points
            )
            for points in points_list
        ]

        # Assert
        for index, act in enumerate(acts):
            with self.subTest(index=index), self.assertRaises(ValidationError):
                act()

    def test_Should_accept_max_points_at_the_bounds_When_the_request_is_valid(self):
        # Arrange
        self._add_shape("Ball", Part.makeSphere(50))

        for limit in (2, 5000):
            with self.subTest(limit=limit):
                # Act
                envelope = self._section("Ball", normal="x", **self._points(0.5, max_points=limit))

                # Assert
                self.assertEqual(envelope["status"], "OK")

    def test_Should_name_the_object_When_it_is_unknown_has_no_shape_or_an_empty_shape(self):
        # Arrange
        self.document.addObject("App::DocumentObjectGroup", "Group")
        self._add_shape("Empty", Part.Compound([]))

        # Act
        act_unknown = lambda: self._section("Nope")  # noqa: E731
        act_no_shape = lambda: self._section("Group")  # noqa: E731
        act_empty = lambda: self._section("Empty")  # noqa: E731

        # Assert
        with self.assertRaisesRegex(ValidationError, "unknown object: Nope"):
            act_unknown()
        with self.assertRaisesRegex(ValidationError, "no queryable shape: Group"):
            act_no_shape()
        with self.assertRaisesRegex(ValidationError, "no queryable shape: Empty"):
            act_empty()

    def test_Should_answer_invalid_input_When_the_call_goes_through_dispatch(self):
        # Arrange
        self._box()
        target = self._dispatch()
        plane = {"normal": "z", "offset": {"value": 15, "unit": "mm"}}
        calls = [
            {"doc": self.handle, "object": "Nope", "plane": plane},
            {"doc": self.handle, "object": "Box"},
            {
                "doc": self.handle,
                "object": "Box",
                "plane": {"normal": [0, 0, 0], "offset": {"value": 1, "unit": "mm"}},
            },
        ]

        for arguments in calls:
            with self.subTest(arguments=arguments):
                # Act
                envelope = target.dispatch("query_section", arguments)

                # Assert
                self.assertEqual(envelope["status"], "INVALID_INPUT")

    def test_Should_leave_a_fresh_fingerprint_digest_equal_When_a_section_is_measured(self):
        # Arrange
        self._box()
        self._add_shape("Ball", Part.makeSphere(50))
        self.document.recompute()
        before = fingerprint(self.document, fresh=True)["digest"]

        # Act
        self._section("Box", offset=15.0, **self._points(0.1))
        self._section("Ball", normal="x", offset=0.0, **self._points(0.1))

        # Assert
        self.assertEqual(fingerprint(self.document, fresh=True)["digest"], before)

    def test_Should_refuse_the_plane_When_it_lies_on_a_planar_face(self):
        # Arrange
        self._box()
        self._add_shape("Cylinder", Part.makeCylinder(10, 30))
        void_box = Part.makeBox(20, 20, 20).cut(Part.makeBox(10, 10, 10, App.Vector(5, 5, 5)))
        self._add_shape("Hollow", void_box)
        placed = self._box("Placed")
        placed.Placement = App.Placement(App.Vector(0, 0, 100), App.Rotation())
        nurbs_box = Part.makeBox(BOX_L, BOX_W, BOX_H).toNurbs()
        self._add_shape("NurbsBox", nurbs_box)
        loose_box = Part.makeBox(BOX_L, BOX_W, BOX_H)
        loose_box.fixTolerance(1e-5)
        self._add_shape("LooseBox", loose_box)
        cases = [
            ("Box", "z", 0.0),
            ("Box", "z", 1e-9),
            ("Box", "z", 1e-7),
            ("Box", "z", BOX_H),
            ("Box", "x", BOX_L),
            ("Box", [1e-10, 0, 1], 0.0),
            ("Cylinder", "z", 30.0),
            ("Hollow", "z", 5.0),
            ("Hollow", [0, 0, 1e-3], 15.0),
            ("Placed", "z", 130.0),
            ("NurbsBox", "z", 0.0),
            ("NurbsBox", "z", BOX_H),
            ("LooseBox", "z", 1e-6),
        ]

        for name, normal, offset in cases:
            with self.subTest(name=name, normal=normal, offset=offset):
                # Act
                envelope = self._section(name, normal=normal, offset=offset)

                # Assert
                self.assertEqual(envelope["status"], "INVALID_INPUT")
                self.assertEqual(envelope["detail"]["code"], "section.plane_on_face")
                self.assertIn(
                    f"the plane lies on a face of {name}; offset it by a small amount",
                    envelope["detail"]["message"],
                )

    def test_Should_cut_the_plane_When_it_is_tilted_or_just_off_a_planar_face(self):
        # Arrange
        self._box()
        void_box = Part.makeBox(20, 20, 20).cut(Part.makeBox(10, 10, 10, App.Vector(5, 5, 5)))
        self._add_shape("Hollow", void_box)

        # Act
        tilted = self._section("Box", normal=[1e-3, 0, 1], offset=15.0)["structured_content"]
        void_floor = self._section("Hollow", offset=5.000001)["structured_content"]

        # Assert
        self.assertEqual((tilted["wires"], tilted["closed_wires"]), (1, 1))
        self.assertAlmostEqual(tilted["area"]["value"], BOX_L * BOX_W, delta=1e-3)
        self.assertEqual((void_floor["wires"], void_floor["closed_wires"]), (2, 2))
        self.assertAlmostEqual(void_floor["area"]["value"], 400 - 100, places=6)
        self.assertAlmostEqual(void_floor["length"]["value"], 80 + 40, places=6)

    def test_Should_refuse_as_untrusted_When_the_shape_is_invalid_and_the_plane_is_on_a_face(self):
        # Arrange
        corners = [(0, 0), (10, 10), (10, 0), (0, 10), (0, 0)]
        bowtie = Part.Face(Part.makePolygon([App.Vector(x, y, 0) for x, y in corners]))
        self._add_shape("Bowtie", bowtie.extrude(App.Vector(0, 0, 10)))

        # Act
        envelope = self._section("Bowtie", offset=0.0)

        # Assert
        self.assertEqual(envelope["detail"]["code"], "section.untrusted_shape")

    def test_Should_refuse_as_untrusted_When_a_face_surface_cannot_be_read(self):
        # Arrange
        self._box()

        # Act
        with mock.patch.object(queries, "_bspline_pole_load", side_effect=TypeError("surface")):
            first = self._section(offset=15.0)
        with mock.patch.object(queries, "_plane_on_face", side_effect=TypeError("surface")):
            second = self._section(offset=15.0)

        # Assert
        self.assertEqual(first["detail"]["code"], "section.untrusted_shape")
        self.assertEqual(second["detail"]["code"], "section.untrusted_shape")

    def test_Should_cut_to_a_measured_area_When_the_section_edge_is_a_bspline(self):
        # Arrange
        radius = 10.0
        self._add_shape("Nurbs", Part.makeCylinder(radius, 30).toNurbs())

        # Act
        result = self._section("Nurbs", offset=15.0)["structured_content"]

        # Assert
        self.assertAlmostEqual(result["area"]["value"], math.pi * radius**2, delta=0.5)

    def test_Should_refuse_the_shape_When_the_pole_load_is_above_the_limit_by_one(self):
        # Arrange
        spring = _coil_spring(5)
        self._add_shape("Spring", spring)
        load = queries._bspline_pole_load(spring)

        # Act
        with mock.patch.object(queries, "_MAX_BSPLINE_POLE_LOAD", load):
            at_limit = self._section("Spring", normal="y", offset=0.5)
        with mock.patch.object(queries, "_MAX_BSPLINE_POLE_LOAD", load - 1):
            above = self._section("Spring", normal="y", offset=0.5)

        # Assert
        self.assertEqual(at_limit["status"], "OK")
        self.assertEqual(above["detail"]["code"], "section.too_complex")
        self.assertIn(f"pole load of {load}", above["detail"]["message"])

    def test_Should_sum_the_squares_of_the_poles_over_the_faces_When_the_load_is_read(self):
        # Arrange
        one = Part.makeBox(1, 1, 1).toNurbs()
        two = Part.makeCompound([one, one.translated(App.Vector(5, 0, 0))])

        # Act
        single_load = queries._bspline_pole_load(one)
        pair_load = queries._bspline_pole_load(two)

        # Assert
        self.assertGreater(single_load, 0)
        self.assertEqual(pair_load, 2 * single_load)

    def test_Should_return_null_area_When_the_wires_and_the_boolean_disagree(self):
        # Arrange
        self._box()

        # Act
        with mock.patch.object(queries, "_wire_face_area", return_value=123.0):
            disagree = self._section(offset=15.0)["structured_content"]
        with mock.patch.object(queries, "_wire_face_area", return_value=None):
            unbuilt = self._section(offset=15.0)["structured_content"]

        # Assert
        self.assertEqual(disagree["wires"], 1)
        self.assertIsNone(disagree["area"])
        self.assertIsNone(unbuilt["area"])

    def test_Should_return_null_area_When_a_wire_is_open(self):
        # Arrange
        side_by_side = Part.makeCompound(
            [Part.makeBox(10, 10, 10), Part.makeBox(10, 10, 10, App.Vector(10, 0, 0))]
        )
        self._add_shape("Touching", side_by_side)

        # Act
        result = self._section("Touching", offset=5.0)["structured_content"]

        # Assert
        self.assertGreater(result["wires"], result["closed_wires"])
        self.assertIsNone(result["area"])

    def test_Should_report_an_exact_bbox_When_the_section_edge_is_a_bspline(self):
        # Arrange
        radius = 10.0
        self._add_shape("Nurbs", Part.makeCylinder(radius, 30).toNurbs())

        # Act
        result = self._section("Nurbs", offset=15.0)["structured_content"]

        # Assert
        box = result["bbox"]
        for key, expected in (
            ("xmin", -radius),
            ("xmax", radius),
            ("ymin", -radius),
            ("ymax", radius),
        ):
            self.assertAlmostEqual(box[key]["value"], expected, delta=1e-3)

    def test_Should_refuse_a_coil_spring_When_its_bspline_face_has_too_many_poles(self):
        # Arrange
        self._add_shape("Long", _coil_spring(30))
        self._add_shape("Short", _coil_spring(5))
        started = time.monotonic()

        # Act
        refused = self._section("Long", normal="y", offset=0.5)
        cut = self._section("Short", normal="y", offset=0.5)

        # Assert
        self.assertEqual(refused["status"], "INVALID_INPUT")
        self.assertEqual(refused["detail"]["code"], "section.too_complex")
        self.assertIn("poles", refused["detail"]["message"])
        self.assertEqual(cut["status"], "OK")
        self.assertEqual(cut["structured_content"]["wires"], 10)
        self.assertLess(time.monotonic() - started, 30.0)

    def test_Should_refuse_a_prism_When_it_has_one_face_above_the_limit(self):
        # Arrange
        self._add_shape("Prism", _prism(queries._MAX_SECTION_FACES - 1))

        # Act
        envelope = self._section("Prism", offset=5.0)

        # Assert
        self.assertEqual(envelope["status"], "INVALID_INPUT")
        self.assertEqual(envelope["detail"]["code"], "section.too_complex")
        self.assertIn(f"{queries._MAX_SECTION_FACES + 1} faces", envelope["detail"]["message"])

    def test_Should_finish_well_inside_the_query_budget_When_shapes_are_at_the_limits(self):
        # Arrange
        measured_seconds_with_margin = 30.0
        self._add_shape("Prism", _prism(queries._MAX_SECTION_FACES - 2))
        self._add_shape("Plate", _hex_hole_plate(495))
        self._add_shape("AreaPlate", _hex_hole_plate(290))
        combined = Part.makeCompound(
            [_hex_hole_plate(290), _coil_spring(5).translated(App.Vector(-100, 0, 0))]
        )
        self._add_shape("Combined", combined)
        cases = (("Prism", 5.0), ("Plate", 5.0), ("AreaPlate", 5.0), ("Combined", 5.0))

        for name, offset in cases:
            with self.subTest(name=name):
                started = time.monotonic()

                # Act
                envelope = self._section(name, offset=offset)

                # Assert
                elapsed = time.monotonic() - started
                self.assertEqual(envelope["status"], "OK")
                self.assertLess(elapsed, measured_seconds_with_margin)
                if name == "AreaPlate":
                    self.assertIsNotNone(envelope["structured_content"]["area"])
                if name == "Plate":
                    self.assertIsNone(envelope["structured_content"]["area"])

    def test_Should_return_null_area_and_open_wires_When_a_face_or_an_open_shell_is_cut(self):
        # Arrange
        box = Part.makeBox(BOX_L, BOX_W, BOX_H)
        self._add_shape("Face", box.Faces[4])
        self._add_shape("OpenShell", Part.Shell(box.Faces[:5]))

        for name in ("Face", "OpenShell"):
            with self.subTest(name=name):
                # Act
                result = self._section(name, normal="x", offset=5.0)["structured_content"]

                # Assert
                self.assertGreaterEqual(result["wires"], 1)
                self.assertEqual(result["closed_wires"], 0)
                self.assertIsNone(result["area"])

    def test_Should_return_null_area_not_zero_When_the_wire_count_is_above_the_area_limit(self):
        # Arrange
        boxes = [Part.makeBox(2, 2, 2, App.Vector(3 * index, 0, 0)) for index in range(4)]
        self._add_shape("Row", Part.makeCompound(boxes))

        # Act
        with mock.patch.object(queries, "_MAX_AREA_WIRES", 3):
            above = self._section("Row", offset=1.0)["structured_content"]
        with mock.patch.object(queries, "_MAX_AREA_WIRES", 4):
            at_limit = self._section("Row", offset=1.0)["structured_content"]

        # Assert
        self.assertEqual(above["wires"], 4)
        self.assertIsNone(above["area"])
        self.assertAlmostEqual(at_limit["area"]["value"], 16.0, places=6)

    def test_Should_cut_in_the_container_frame_When_the_object_has_a_placement(self):
        # Arrange
        placed = self._box()
        placed.Placement = App.Placement(App.Vector(0, 0, 100), App.Rotation())

        # Act
        hit = self._section(offset=115.0)["structured_content"]
        miss = self._section(offset=15.0)["structured_content"]

        # Assert
        self.assertEqual(hit["wires"], 1)
        self.assertAlmostEqual(hit["bbox"]["zmin"]["value"], 115.0, places=6)
        self.assertEqual(miss["wires"], 0)

    def test_Should_drop_the_next_wire_When_the_cap_leaves_fewer_than_two_points(self):
        # Arrange
        plate = Part.makeBox(100, 100, 10).cut(Part.makeCylinder(10, 10, App.Vector(50, 50, 0)))
        self._add_shape("Plate", plate)
        full = self._section("Plate", offset=5.0, **self._points(0.5))["structured_content"]
        first_wire_points = len(full["polylines"][0])

        for cap in (first_wire_points, first_wire_points + 1):
            with self.subTest(cap=cap):
                # Act
                result = self._section("Plate", offset=5.0, **self._points(0.5, max_points=cap))[
                    "structured_content"
                ]

                # Assert
                self.assertEqual(len(result["polylines"]), 1)
                self.assertEqual(len(result["polylines"][0]), first_wire_points)
                self.assertTrue(result["truncated"])
        self.assertFalse(full["truncated"])

    def test_Should_raise_When_a_number_is_beyond_the_float_range(self):
        # Arrange
        self._box()
        huge_int = 10**400
        planes = [
            {"normal": [huge_int, 0, 0], "offset": {"value": 1.0, "unit": "mm"}},
            {"normal": "z", "offset": {"value": huge_int, "unit": "mm"}},
        ]

        for plane in planes:
            with self.subTest(plane=plane):
                # Act
                act = lambda plane=plane: queries.query_section(  # noqa: E731
                    self.registry, doc=self.handle, object="Box", plane=plane
                )

                # Assert
                with self.assertRaises(ValidationError):
                    act()

    def test_Should_cut_the_same_plane_When_the_normal_is_near_the_float_limits(self):
        # Arrange
        self._box()
        expected = self._section(normal="z", offset=15.0)["structured_content"]

        for scale in (1.5e308, 5e-324):
            with self.subTest(scale=scale):
                # Act
                result = self._section(normal=[0, 0, scale], offset=15.0)["structured_content"]

                # Assert
                self.assertEqual(result, expected)

    def test_Should_report_the_counts_in_the_text_When_a_section_is_measured(self):
        # Arrange
        self._box()

        # Act
        text = self._section(offset=15.0)["text"]

        # Assert
        self.assertEqual(text, "1 wire(s), 1 closed, length 60.0 mm, area 200.0 mm^2.")


class QueryParametersTest(unittest.TestCase):
    def setUp(self):
        self.registry = DocumentRegistry()
        self.handle = self.registry.document_create("query_parameters")["structured_content"]["doc"]
        _, self.document = self.registry.with_document(self.handle, lambda h, d: (h, d))

    def tearDown(self):
        for name in list(App.listDocuments().keys()):
            App.closeDocument(name)

    def _varset(self):
        varset = self.document.addObject("App::VarSet", "Params")
        varset.addProperty("App::PropertyLength", "width", "Size", "overall width")
        varset.width = App.Units.Quantity("12.5 mm")
        varset.addProperty("App::PropertyAngle", "tilt", "Parameters")
        varset.tilt = App.Units.Quantity("30 deg")
        varset.addProperty("App::PropertyInteger", "count", "Parameters")
        varset.count = 4
        varset.addProperty("App::PropertyBool", "hollow", "Parameters")
        varset.hollow = True
        varset.addProperty("App::PropertyString", "note", "Parameters")
        varset.note = "rev A"
        return varset

    def _sheet(self):
        sheet = self.document.addObject("Spreadsheet::Sheet", "Sheet")
        sheet.set("A1", "10 mm")
        sheet.setAlias("A1", "plate")
        sheet.set("A2", "=plate * 2")
        sheet.set("B1", "3")
        sheet.setAlias("B1", "holes")
        sheet.set("C1", "hello")
        sheet.setAlias("C1", "label")
        sheet.set("D1", "=1/0")
        sheet.setAlias("D1", "broken")
        self.document.recompute()
        return sheet

    def _query(self):
        return queries.query_parameters(self.registry, doc=self.handle)

    def test_Should_list_every_varset_property_with_value_unit_group_and_description_When_read(
        self,
    ):
        # Arrange
        self._varset()

        # Act
        envelope = self._query()

        # Assert
        self.assertEqual(envelope["status"], "OK")
        rows = {
            row["name"]: row for row in envelope["structured_content"]["varsets"][0]["parameters"]
        }
        self.assertEqual(sorted(rows), ["count", "hollow", "note", "tilt", "width"])
        self.assertEqual(
            rows["width"],
            {
                "name": "width",
                "type": "length",
                "value": 12.5,
                "unit": "mm",
                "group": "Size",
                "description": "overall width",
            },
        )
        self.assertEqual((rows["tilt"]["value"], rows["tilt"]["unit"]), (30.0, "deg"))
        self.assertEqual((rows["count"]["type"], rows["count"]["value"]), ("integer", 4))
        self.assertEqual((rows["hollow"]["type"], rows["hollow"]["value"]), ("bool", True))
        self.assertEqual((rows["note"]["type"], rows["note"]["value"]), ("string", "rev A"))
        self.assertEqual(envelope["structured_content"]["varsets"][0]["object"], "Params")

    def test_Should_list_only_aliased_cells_with_their_contents_When_a_sheet_exists(self):
        # Arrange
        self._sheet()

        # Act
        envelope = self._query()

        # Assert
        rows = {
            row["name"]: row
            for row in envelope["structured_content"]["spreadsheets"][0]["parameters"]
        }
        self.assertEqual(sorted(rows), ["broken", "holes", "label", "plate"])
        self.assertEqual(
            rows["plate"],
            {"name": "plate", "cell": "A1", "contents": "=10 mm", "value": 10.0, "unit": "mm"},
        )
        self.assertEqual((rows["holes"]["value"], rows["holes"]["unit"]), (3, None))
        self.assertEqual(rows["label"]["value"], "hello")

    def test_Should_report_null_with_a_reason_When_a_cell_is_in_error(self):
        # Arrange
        self._sheet()

        # Act
        envelope = self._query()

        # Assert
        rows = {
            row["name"]: row
            for row in envelope["structured_content"]["spreadsheets"][0]["parameters"]
        }
        self.assertIsNone(rows["broken"]["value"])
        self.assertTrue(rows["broken"]["reason"])
        self.assertNotIn("reason", rows["plate"])

    def test_Should_keep_a_text_cell_that_starts_with_err_When_it_is_not_a_formula(self):
        # Arrange
        sheet = self.document.addObject("Spreadsheet::Sheet", "Sheet")
        sheet.set("A1", "'ERR: a label")
        sheet.setAlias("A1", "label")
        self.document.recompute()

        # Act
        row = self._query()["structured_content"]["spreadsheets"][0]["parameters"][0]

        # Assert
        self.assertEqual(row["value"], "ERR: a label")
        self.assertNotIn("reason", row)

    def test_Should_list_every_expression_binding_When_objects_are_bound(self):
        # Arrange
        self._varset()
        self._sheet()
        box = self.document.addObject("Part::Box", "Box")
        box.setExpression("Length", "Params.width")
        box.setExpression("Width", "Sheet.plate")
        self.document.recompute()

        # Act
        envelope = self._query()

        # Assert
        self.assertEqual(
            envelope["structured_content"]["bindings"],
            [
                {"object": "Box", "path": "Length", "expression": "Params.width"},
                {"object": "Box", "path": "Width", "expression": "Sheet.plate"},
            ],
        )

    def test_Should_report_null_with_a_reason_When_a_property_is_not_a_scalar(self):
        # Arrange
        varset = self.document.addObject("App::VarSet", "Params")
        varset.addProperty("App::PropertyVector", "offset", "Parameters")
        varset.addProperty("App::PropertyFloat", "huge", "Parameters")
        varset.huge = float("inf")

        # Act
        envelope = self._query()

        # Assert
        rows = {
            row["name"]: row for row in envelope["structured_content"]["varsets"][0]["parameters"]
        }
        self.assertIsNone(rows["offset"]["value"])
        self.assertIn("Vector", rows["offset"]["reason"])
        self.assertIsNone(rows["huge"]["value"])
        self.assertIn("finite", rows["huge"]["reason"])

    def test_Should_return_empty_lists_When_the_document_holds_no_parameters(self):
        # Arrange
        self.document.addObject("Part::Box", "Box")

        # Act
        envelope = self._query()

        # Assert
        content = envelope["structured_content"]
        self.assertEqual(
            (content["varsets"], content["spreadsheets"], content["bindings"]), ([], [], [])
        )
        self.assertFalse(content["truncated"])

    def test_Should_cut_a_list_at_500_rows_and_say_so_When_a_varset_holds_more(self):
        # Arrange
        varset = self.document.addObject("App::VarSet", "Params")
        for index in range(501):
            varset.addProperty("App::PropertyInteger", f"p{index}", "Parameters")

        # Act
        envelope = self._query()

        # Assert
        content = envelope["structured_content"]
        self.assertEqual(len(content["varsets"][0]["parameters"]), 500)
        self.assertEqual(content["totals"]["varset_parameters"], 501)
        self.assertTrue(content["truncated"])
        self.assertIn("truncated", envelope["text"])

    def test_Should_cut_the_spreadsheet_and_binding_lists_at_500_rows_When_a_document_holds_more(
        self,
    ):
        # Arrange
        sheet = self.document.addObject("Spreadsheet::Sheet", "Sheet")
        holder = self.document.addObject("App::VarSet", "Holder")
        for index in range(501):
            sheet.set(f"A{index + 1}", str(index))
            sheet.setAlias(f"A{index + 1}", f"cell{index}")
            holder.addProperty("App::PropertyInteger", f"p{index}", "Parameters")
            holder.setExpression(f"p{index}", str(index))

        # Act
        content = self._query()["structured_content"]

        # Assert
        self.assertEqual(len(content["spreadsheets"][0]["parameters"]), 500)
        self.assertEqual(content["totals"]["spreadsheet_parameters"], 501)
        self.assertEqual(len(content["bindings"]), 500)
        self.assertEqual(content["totals"]["bindings"], 501)
        self.assertTrue(content["truncated"])

    def test_Should_list_a_sketch_constraint_binding_When_a_named_constraint_is_bound(self):
        # Arrange
        self._varset()
        sketch = self.document.addObject("Sketcher::SketchObject", "Sketch")
        sketch.addGeometry(Part.LineSegment(App.Vector(0, 0, 0), App.Vector(5, 0, 0)), False)
        index = sketch.addConstraint(Sketcher.Constraint("DistanceX", 0, 1, 0, 2, 5.0))
        sketch.renameConstraint(index, "span")
        sketch.setExpression(".Constraints.span", "Params.width")
        self.document.recompute()

        # Act
        envelope = self._query()

        # Assert
        self.assertEqual(
            envelope["structured_content"]["bindings"],
            [{"object": "Sketch", "path": ".Constraints.span", "expression": "Params.width"}],
        )

    def test_Should_read_a_dimensionless_quantity_as_its_number_When_the_unit_is_empty(self):
        # Arrange
        varset = self.document.addObject("App::VarSet", "Params")
        varset.addProperty("App::PropertyQuantity", "ratio", "Parameters")
        varset.ratio = 2.5

        # Act
        row = self._query()["structured_content"]["varsets"][0]["parameters"][0]

        # Assert
        self.assertEqual((row["value"], row["unit"]), (2.5, None))

    def test_Should_leave_the_document_untouched_When_read(self):
        # Arrange
        self._varset()
        self._sheet()
        box = self.document.addObject("Part::Box", "Box")
        box.setExpression("Length", "Params.width")
        self.document.recompute()
        box.Width = 3.0
        states_before = {obj.Name: list(obj.State) for obj in self.document.Objects}
        digest_before = fingerprint(self.document, fresh=True)["digest"]
        undo_before = self.document.UndoCount

        # Act
        self._query()

        # Assert
        self.assertIn("Touched", states_before["Box"])
        self.assertEqual(
            {obj.Name: list(obj.State) for obj in self.document.Objects}, states_before
        )
        self.assertEqual(fingerprint(self.document, fresh=True)["digest"], digest_before)
        self.assertEqual(self.document.UndoCount, undo_before)
        self.assertEqual(box.Width.getValueAs("mm"), 3.0)

    def test_Should_read_a_value_just_written_When_called_after_feature_parameters_define(self):
        # Arrange
        from freecad_buddy.usecases import confirm, features

        posture = confirm.set_auto_approve(True)
        self.addCleanup(confirm.set_auto_approve, posture)
        features.feature_parameters_define(
            self.registry,
            doc=self.handle,
            varset="Params",
            parameters=[{"name": "width", "type": "length", "value": {"value": 7, "unit": "mm"}}],
        )

        # Act
        envelope = self._query()

        # Assert
        row = envelope["structured_content"]["varsets"][0]["parameters"][0]
        self.assertEqual(
            (row["name"], row["type"], row["value"], row["unit"]), ("width", "length", 7.0, "mm")
        )

    def test_Should_raise_a_validation_error_When_the_document_is_unknown(self):
        # Act
        act = lambda: queries.query_parameters(self.registry, doc="nope")  # noqa: E731

        # Assert
        with self.assertRaises(ValidationError):
            act()

    def test_Should_summarize_the_totals_When_read(self):
        # Arrange
        self._varset()

        # Act
        text = self._query()["text"]

        # Assert
        self.assertEqual(
            text, "5 VarSet parameter(s) in 1 VarSet(s), 0 spreadsheet parameter(s), 0 binding(s)."
        )


if __name__ == "__main__":
    unittest.main()
