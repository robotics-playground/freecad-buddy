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

    def test_Should_flag_a_failed_boolean_When_two_solids_only_touch_at_a_face(self):
        # Arrange
        self._add_box("A")
        self._add_box("B", 10, 0, 0)

        # Act
        envelope = self._measure(objects=["A", "B"])

        # Assert
        record = envelope["structured_content"]["pairs"][0]
        self.assertTrue(record["boolean_failed"])
        self.assertIsNone(record["common_volume"])

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


if __name__ == "__main__":
    unittest.main()
