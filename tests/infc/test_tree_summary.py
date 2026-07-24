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
        self.assertIn("pcb", link_names)         # App::Link -> links
        self.assertIn("Plate", child_names)      # Part::Feature -> children
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
        return sum(1 + self._count(n.get("children", [])) + self._count(n.get("links", []))
                   for n in nodes)

    def test_link_target_still_a_root(self):
        # A standalone Body that an App::Link also targets must remain a top-level root
        # (an App::Link's OutList contains its LinkedObject; that must not prune the target).
        link = self.doc.addObject("App::Link", "BodyLink")
        link.LinkedObject = self.body
        self.doc.recompute()
        sc = self._tree(depth=1)
        names = [n["name"] for n in sc["tree"]]
        self.assertIn("Body", names)   # standalone Body still a root
        self.assertIn("BodyLink", names)  # the link is also a root

    def test_text_is_summary_not_json_dump(self):
        env = queries.query_tree_summary(self.registry, doc=self.handle, depth=1)
        self.assertNotIn("{", env["text"])  # no JSON braces — it's prose
        self.assertIn("objects", env["text"])


if __name__ == "__main__":
    unittest.main()
