"""In-FreeCAD depth/filter tree tests (stdlib unittest, discovered by tests/run_tests.py)."""

import unittest

import FreeCAD as App

from freecad_buddy.usecases import queries
from freecad_buddy.usecases.documents import DocumentRegistry


class TreeSummaryTest(unittest.TestCase):
    def setUp(self):
        self.registry = DocumentRegistry()
        self.handle = self.registry.document_create("tree")["structured_content"]["doc"]
        _, self.doc = self.registry.with_document(self.handle, lambda h, d: (h, d))
        # A standalone Body (pcb) + a linked instance inside a group, plus a datum-heavy Body.
        self.body = self.doc.addObject("PartDesign::Body", "Body")
        self.body.Label = "pcb"
        self.link = self.doc.addObject("App::Link", "pcb")
        self.link.Label = "pcb001"
        self.link.LinkedObject = self.body
        self.feature = self.doc.addObject("Part::Feature", "Plate")
        import Part

        self.feature.Shape = Part.makeBox(10, 10, 1)
        self.doc.recompute()

    def tearDown(self):
        for name in list(App.listDocuments().keys()):
            App.closeDocument(name)

    def _tree(self, **kw):
        envelope = queries.query_tree_summary(self.registry, doc=self.handle, **kw)
        return envelope["structured_content"]

    def test_depth_one_returns_roots_with_counts_no_expansion(self):
        sc = self._tree(depth=1, filters={"types": ["App::Link"]})
        names = [n["name"] for n in sc["tree"]]
        self.assertIn("pcb", names)
        link_node = next(n for n in sc["tree"] if n["name"] == "pcb")
        self.assertNotIn("links", link_node)  # not expanded at depth 1
        self.assertNotIn("children", link_node)

    def test_links_partitioned_from_children(self):
        # A group holding both a link and a plain feature separates them.
        grp = self.doc.addObject("App::DocumentObjectGroup", "Grp")
        grp.addObject(self.link)
        grp.addObject(self.feature)
        self.doc.recompute()
        sc = self._tree(depth=2, root="Grp")
        grp_node = sc["tree"][0]
        link_names = [n["name"] for n in grp_node.get("links", [])]
        child_names = [n["name"] for n in grp_node.get("children", [])]
        self.assertIn("pcb", link_names)  # App::Link -> links
        self.assertIn("Plate", child_names)  # Part::Feature -> children
        self.assertNotIn("pcb", child_names)

    def test_visible_only_filter_drops_hidden(self):
        self.feature.Visibility = False
        self.doc.recompute()
        sc = self._tree(depth=1, filters={"visible_only": True})
        self.assertNotIn("Plate", [n["name"] for n in sc["tree"]])

    def test_visibility_present_on_every_node(self):
        sc = self._tree(depth=1)
        for n in sc["tree"]:
            self.assertIn("visibility", n)

    def test_default_exclude_types_drops_datums(self):
        sc = self._tree(depth=3)  # deep enough to reach Body's origin datums
        types = self._all_types(sc["tree"])
        self.assertNotIn("App::Plane", types)
        self.assertNotIn("App::Origin", types)

    def test_root_scopes_to_subtree(self):
        sc = self._tree(depth=2, root="Body")
        self.assertEqual(sc["tree"][0]["name"], "Body")

    def test_total_and_returned_reported(self):
        sc = self._tree(depth=1)
        self.assertGreater(sc["total_objects"], 0)
        self.assertEqual(sc["returned_nodes"], self._count(sc["tree"]))

    def _all_types(self, nodes):
        out = []
        for n in nodes:
            out.append(n["type"])
            out += self._all_types(n.get("children", []))
            out += self._all_types(n.get("links", []))
        return out

    def _count(self, nodes):
        return sum(
            1 + self._count(n.get("children", [])) + self._count(n.get("links", [])) for n in nodes
        )

    def test_link_target_still_a_root(self):
        # A standalone Body that an App::Link also targets must remain a top-level root
        # (an App::Link's OutList contains its LinkedObject; that must not prune the target).
        link = self.doc.addObject("App::Link", "BodyLink")
        link.LinkedObject = self.body
        self.doc.recompute()
        sc = self._tree(depth=1)
        names = [n["name"] for n in sc["tree"]]
        self.assertIn("Body", names)  # standalone Body still a root
        self.assertIn("BodyLink", names)  # the link is also a root

    def test_a_child_linked_from_two_properties_appears_once(self):
        # getOutList walks every link property and appends each target, so an object reachable
        # through two of them comes back twice (DocumentObject.cpp getOutListProp). A real
        # PartDesign::Pad does exactly this: Profile and ReferenceAxis both point at its sketch.
        pad = self.doc.addObject("PartDesign::Pad", "Pad")
        sketch = self.doc.addObject("Sketcher::SketchObject", "PadProfile")
        pad.Profile = sketch
        pad.ReferenceAxis = (sketch, ["N_Axis"])
        self.doc.recompute()

        raw = [o.Name for o in pad.OutList]
        self.assertEqual(raw.count("PadProfile"), 2, "fixture must reproduce the duplicate")

        deps = queries.query_dependencies(self.registry, doc=self.handle, object="Pad")
        out = deps["structured_content"]["out_list"]
        self.assertEqual(out.count("PadProfile"), 1, f"duplicate survived: {out}")

    def test_text_is_summary_not_json_dump(self):
        env = queries.query_tree_summary(self.registry, doc=self.handle, depth=1)
        self.assertNotIn("{", env["text"])  # no JSON braces — it's prose
        self.assertIn("objects", env["text"])


class NestedFilterTest(unittest.TestCase):
    """A filter must reach a match nested in a container that fails it (Body -> Sketch -> Pad)."""

    def setUp(self):
        import Part
        import Sketcher

        self.registry = DocumentRegistry()
        self.handle = self.registry.document_create("nested")["structured_content"]["doc"]
        doc = self.registry.with_document(self.handle, lambda h, d: d)
        body = doc.addObject("PartDesign::Body", "Body")
        sketch = body.newObject("Sketcher::SketchObject", "Sketch")
        sketch.AttachmentSupport = (body.Origin.OriginFeatures[3], [""])  # XY_Plane
        sketch.MapMode = "FlatFace"
        sketch.addGeometry(Part.Circle(App.Vector(0, 0, 0), App.Vector(0, 0, 1), 5.0), False)
        sketch.addConstraint(Sketcher.Constraint("Radius", 0, 5.0))
        pad = body.newObject("PartDesign::Pad", "Pad")
        pad.Profile = sketch
        pad.Length = 10.0
        doc.recompute()
        self.assertFalse(pad.Shape.isNull(), "fixture must build a real Pad")

    def tearDown(self):
        for name in list(App.listDocuments().keys()):
            App.closeDocument(name)

    def _names(self, filters, depth=1, root=None):
        sc = queries.query_tree_summary(
            self.registry, doc=self.handle, depth=depth, root=root, filters=filters
        )["structured_content"]
        names = []

        def walk(nodes):
            for node in nodes:
                names.append(node["name"])
                walk(node.get("children", []))
                walk(node.get("links", []))

        walk(sc["tree"])
        self.assertEqual(sc["returned_nodes"], len(names))
        return names

    def test_a_type_filter_returns_the_pad_nested_in_a_body(self):
        names = self._names({"types": ["PartDesign::Pad"]})

        self.assertEqual(names, ["Pad"])

    def test_a_name_pattern_returns_the_pad_nested_in_a_body(self):
        names = self._names({"name_pattern": "^Pad"})

        self.assertEqual(names, ["Pad"])

    def test_renderable_only_returns_the_pad_and_drops_its_containers(self):
        names = self._names({"renderable_only": True})

        self.assertEqual(names, ["Pad"])

    def test_the_search_ignores_depth_and_returns_each_name_once(self):
        names = self._names({"types": ["PartDesign::Pad", "Sketcher::SketchObject"]}, depth=1)

        self.assertEqual(sorted(names), ["Pad", "Sketch"])

    def test_a_hidden_body_under_visible_only_hides_its_whole_subtree(self):
        doc = self.registry.with_document(self.handle, lambda h, d: d)
        doc.getObject("Body").Visibility = False
        self.assertTrue(doc.getObject("Pad").Visibility, "fixture must keep the Pad visible")

        names = self._names({"visible_only": True})

        self.assertEqual(names, [])

    def test_an_excluded_body_drops_its_whole_subtree(self):
        names = self._names({"exclude_types": ["PartDesign::Body"]})

        self.assertEqual(names, [])

    def test_a_failing_link_does_not_hoist_its_target(self):
        doc = self.registry.with_document(self.handle, lambda h, d: d)
        link = doc.addObject("App::Link", "BodyLink")
        link.LinkedObject = doc.getObject("Body")
        doc.recompute()

        names = self._names({"types": ["PartDesign::Pad"]}, depth=3, root="BodyLink")

        self.assertEqual(names, [])


if __name__ == "__main__":
    unittest.main()
