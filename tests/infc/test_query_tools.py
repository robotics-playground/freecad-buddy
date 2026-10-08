"""In-FreeCAD read-only query-tool tests (stdlib unittest).

Run via ``FreeCADCmd tests/run_tests.py``. Builds a real box + a constrained sketch, then
exercises every ``query_*`` tool for shape, the mass-properties golden (analytic box volume),
the tree-summary cap path, the ``INVALID_INPUT`` cases through dispatch, and the read-only
guarantee (document state unchanged across a full query sweep).
"""

import math
import unittest

import FreeCAD as App
import Part
import Sketcher

from freecad_buddy.adapters.rpc_dispatch import MethodRegistry, RpcMethod
from freecad_buddy.usecases import queries
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


if __name__ == "__main__":
    unittest.main()
