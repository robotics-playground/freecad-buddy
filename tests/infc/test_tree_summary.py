"""In-FreeCAD tests for the plain-text document tree (stdlib unittest, run by tests/run_tests.py).

Fixture: a ``base`` Body (pad), a ``piece`` Body built on it (base feature, datum plane, pad,
pocket), an ``App::Link`` to a ``Part::Box``, and an ``App::Part``.
"""

import unittest

import FreeCAD as App
import Part
import Sketcher

from freecad_buddy.usecases import queries
from freecad_buddy.usecases.documents import DocumentRegistry, ValidationError


def _circle_sketch(body, name, radius):
    sketch = body.newObject("Sketcher::SketchObject", name)
    sketch.AttachmentSupport = (body.Origin.OriginFeatures[3], [""])  # XY_Plane
    sketch.MapMode = "FlatFace"
    sketch.addGeometry(Part.Circle(App.Vector(0, 0, 0), App.Vector(0, 0, 1), radius), False)
    sketch.addConstraint(Sketcher.Constraint("Radius", 0, radius))
    return sketch


class TreeSummaryTest(unittest.TestCase):
    def setUp(self):
        self.registry = DocumentRegistry()
        self.handle = self.registry.document_create("tree")["structured_content"]["doc"]
        self.doc = self.registry.with_document(self.handle, lambda h, d: d)

        base = self.doc.addObject("PartDesign::Body", "base")
        base_pad = base.newObject("PartDesign::Pad", "base_pad")
        base_pad.Profile = _circle_sketch(base, "base_sketch", 20.0)
        base_pad.Length = 5.0

        piece = self.doc.addObject("PartDesign::Body", "piece")
        piece.BaseFeature = base
        datum = piece.newObject("PartDesign::Plane", "piece_plane")
        datum.AttachmentSupport = [(piece.Origin.OriginFeatures[3], "")]
        datum.MapMode = "FlatFace"
        boss = piece.newObject("PartDesign::Pad", "boss")
        boss.Profile = _circle_sketch(piece, "boss_sketch", 5.0)
        boss.Length = 10.0
        hole = piece.newObject("PartDesign::Pocket", "hole")
        hole.Profile = _circle_sketch(piece, "hole_sketch", 2.0)
        hole.Type = "ThroughAll"

        box = self.doc.addObject("Part::Box", "Box")
        link = self.doc.addObject("App::Link", "L")
        link.LinkedObject = box
        self.doc.addObject("App::Part", "Assembly")
        self.doc.recompute()
        self.assertFalse(hole.Shape.isNull(), "fixture must build a real pocket")

    def tearDown(self):
        for name in list(App.listDocuments().keys()):
            App.closeDocument(name)

    def _call(self, **kw):
        return queries.query_tree_summary(self.registry, doc=self.handle, **kw)

    def _lines(self, **kw):
        return self._call(**kw)["text_blocks"][0].splitlines()

    def test_should_list_each_top_level_object_collapsed_when_called_without_parameters(self):
        # Arrange
        expected = [
            "v [BODY] base (+2)",
            "v [BODY] piece (+5)",
            "v [BOX] Box",
            "v [LINK] L -> Box",
            "v [PART] Assembly (+1)",
        ]

        # Act
        lines = self._lines()

        # Assert
        self.assertEqual(lines, expected)

    def test_should_show_the_path_and_the_body_children_when_focused_on_a_body(self):
        # Arrange
        focus = "piece"

        # Act
        lines = self._lines(focus=focus)

        # Assert
        self.assertEqual(lines[:2], ["path: piece", "v [BODY] piece"])
        self.assertRegex(lines[2], r"^\|-- . \[ORIGIN\] Origin\d+( \"[^\"]+\")? \(\+7\)$")
        self.assertEqual(
            lines[3:],
            [
                "|-- - [BASE] BaseFeature",
                "|-- v [DPLANE] piece_plane",
                "|-- - [PAD] boss (+1)",
                "`-- v [POCKET] hole (+1) *tip",
            ],
        )

    def test_should_open_only_the_path_when_expanding_a_deep_node(self):
        # Arrange
        expand = ["boss"]

        # Act
        lines = self._lines(expand=expand)

        # Assert
        self.assertEqual(
            lines[:4],
            [
                "v [BODY] base (+2)",
                "v [BODY] piece (+4 more)",
                "`-- - [PAD] boss",
                "    `-- v [SKETCH] boss_sketch",
            ],
        )

    def test_should_name_no_object_of_the_base_body_when_focus_walks_the_piece_deeply(self):
        # Arrange
        base_names = {"base", "base_pad", "base_sketch"}

        # Act
        lines = self._lines(focus="piece", depth=3)

        # Assert
        names = {line.split("] ")[1].split(" ")[0] for line in lines[1:]}
        self.assertFalse(names & base_names, f"lines crossed into the base body: {lines}")
        self.assertIn("XY_Plane001", names)
        self.assertIn("hole_sketch", names)

    def test_should_cut_at_the_cap_and_steer_when_the_tree_is_too_long(self):
        # Arrange
        group = self.doc.addObject("App::DocumentObjectGroup", "Many")
        for index in range(210):
            group.addObject(self.doc.addObject("App::FeaturePython", f"item{index}"))

        # Act
        envelope = self._call(expand=["Many"])

        # Assert
        lines = envelope["text_blocks"][0].splitlines()
        self.assertEqual(len(lines), 201)
        self.assertEqual(lines[-1], "... 16 more lines; narrow with focus or a smaller depth")
        self.assertTrue(envelope["structured_content"]["truncated"])
        self.assertEqual(envelope["structured_content"]["shown"], 200)
        self.assertTrue(envelope["text"].endswith("truncated."))

    def test_should_open_match_paths_and_count_matches_when_revealing_by_name(self):
        # Arrange
        filters = {"name_pattern": "_sketch$"}

        # Act
        envelope = self._call(filters=filters)

        # Assert
        self.assertEqual(
            envelope["text_blocks"][0].splitlines(),
            [
                "v [BODY] base (+1 more)",
                "`-- v [PAD] base_pad *tip",
                "    `-- v [SKETCH] base_sketch",
                "v [BODY] piece (+3 more)",
                "|-- - [PAD] boss",
                "|   `-- v [SKETCH] boss_sketch",
                "`-- v [POCKET] hole *tip",
                "    `-- v [SKETCH] hole_sketch",
                "v [BOX] Box",
                "v [LINK] L -> Box",
                "v [PART] Assembly (+1)",
            ],
        )
        self.assertEqual(envelope["structured_content"]["matches"], 3)

    def test_should_show_only_matching_datums_when_revealing_by_code_inside_a_focus(self):
        # Arrange
        filters = {"types": ["DPLANE"]}

        # Act
        envelope = self._call(focus="piece", filters=filters)

        # Assert
        self.assertEqual(
            envelope["text_blocks"][0].splitlines(),
            ["path: piece", "v [BODY] piece (+4 more)", "`-- v [DPLANE] piece_plane"],
        )
        self.assertEqual(envelope["structured_content"]["matches"], 1)

    def test_should_show_the_start_level_only_when_nothing_matches(self):
        # Arrange
        filters = {"name_pattern": "zzz"}

        # Act
        envelope = self._call(filters=filters, depth=3)

        # Assert
        self.assertEqual(envelope["text_blocks"][0].splitlines(), self._lines())
        self.assertEqual(envelope["structured_content"]["matches"], 0)

    def test_should_keep_the_tree_out_of_structured_content_when_returning(self):
        # Arrange
        expected_keys = {"doc", "total_objects", "shown", "truncated"}

        # Act
        envelope = self._call()

        # Assert
        self.assertEqual(set(envelope["structured_content"]), expected_keys)
        self.assertEqual(envelope["text"], f"{len(self.doc.Objects)} objects, 5 shown.")
        self.assertEqual(len(envelope["text_blocks"]), 1)

    def test_should_refuse_an_unknown_name_when_given_as_focus(self):
        # Arrange
        focus = "nope"

        # Act
        act = lambda: self._call(focus=focus)  # noqa: E731

        # Assert
        self.assertRaisesRegex(ValidationError, "unknown object: nope", act)

    def test_should_refuse_an_unknown_name_when_given_in_expand(self):
        # Arrange
        expand = ["boss", "nope"]

        # Act
        act = lambda: self._call(expand=expand)  # noqa: E731

        # Assert
        self.assertRaisesRegex(ValidationError, "unknown object: nope", act)

    def test_should_refuse_a_depth_below_one(self):
        # Arrange
        depth = 0

        # Act
        act = lambda: self._call(depth=depth)  # noqa: E731

        # Assert
        self.assertRaises(ValidationError, act)

    def test_should_list_a_part_origin_under_the_part_when_the_part_has_one(self):
        # Arrange
        origin = self.doc.getObject("Assembly").Origin.Name

        # Act
        lines = self._lines(focus="Assembly")

        # Assert
        self.assertRegex(lines[2], rf"^`-- . \[ORIGIN\] {origin}\b")

    def test_should_return_a_child_once_when_two_properties_link_it(self):
        # getOutList walks every link property and appends each target, so an object reachable
        # through two of them comes back twice (DocumentObject.cpp getOutListProp).
        # Arrange
        pad = self.doc.addObject("PartDesign::Pad", "Pad")
        sketch = self.doc.addObject("Sketcher::SketchObject", "PadProfile")
        pad.Profile = sketch
        pad.ReferenceAxis = (sketch, ["N_Axis"])
        self.doc.recompute()
        self.assertEqual([o.Name for o in pad.OutList].count("PadProfile"), 2)

        # Act
        deps = queries.query_dependencies(self.registry, doc=self.handle, object="Pad")

        # Assert
        self.assertEqual(deps["structured_content"]["out_list"].count("PadProfile"), 1)

    def test_should_end_the_broken_line_with_its_status_and_name_it_in_text_when_a_pad_fails(self):
        # Arrange
        body = self.doc.addObject("PartDesign::Body", "broken_body")
        sketch = body.newObject("Sketcher::SketchObject", "open_sketch")
        sketch.addGeometry(Part.LineSegment(App.Vector(0, 0, 0), App.Vector(10, 0, 0)), False)
        pad = body.newObject("PartDesign::Pad", "bad_pad")
        pad.Profile = sketch
        self.doc.recompute()
        status = pad.getStatusString()
        self.assertNotIn(status, ("", "Valid", "Touched"), "fixture must break the pad")

        # Act
        envelope = self._call(focus="broken_body")

        # Assert
        lines = envelope["text_blocks"][0].splitlines()
        bad = [line for line in lines if "bad_pad" in line]
        self.assertEqual(len(bad), 1)
        self.assertTrue(bad[0].endswith(f"!{status}"), bad[0])
        clean = [line for line in lines[1:] if "bad_pad" not in line and "broken_body" not in line]
        self.assertFalse([line for line in clean if " !" in line], clean)
        self.assertIn(f"bad_pad: {status}", envelope["text"])
        self.assertIn(" Errors: ", envelope["text"])

    def test_should_nest_the_operands_when_a_part_cut_holds_them(self):
        # Arrange
        cut = self.doc.addObject("Part::Cut", "Cut")
        cut.Base = self.doc.addObject("Part::Box", "Stock")
        cut.Tool = self.doc.addObject("Part::Cylinder", "Drill")
        self.doc.recompute()

        # Act
        lines = self._lines(expand=["Cut"])

        # Assert
        index = lines.index("v [CUT] Cut")
        self.assertRegex(lines[index + 1], r"^\|-- . \[BOX\] Stock$")
        self.assertRegex(lines[index + 2], r"^`-- . \[CYLINDER\] Drill$")
        self.assertFalse([line for line in lines if line[:1] in "v-" and "Stock" in line])

    def test_should_nest_the_profile_and_section_when_a_loft_claims_them(self):
        # Arrange
        body = self.doc.getObject("piece")
        loft = body.newObject("PartDesign::AdditiveLoft", "loft")
        loft.Profile = body.newObject("Sketcher::SketchObject", "loft_profile")
        loft.Sections = [body.newObject("Sketcher::SketchObject", "loft_section")]

        # Act
        lines = self._lines(focus="piece", expand=["loft"])

        # Assert
        names = [line.split("] ")[1].split(" ")[0] for line in lines[1:]]
        index = names.index("loft")
        self.assertEqual(names[index + 1 : index + 3], ["loft_profile", "loft_section"])
        self.assertTrue(lines[index + 2].startswith("    |-- "), lines)
        self.assertEqual(names.count("loft_profile"), 1)

    def test_should_list_the_elements_when_a_link_group_holds_them(self):
        # Arrange
        group = self.doc.addObject("App::LinkGroup", "LG")
        group.ElementList = [self.doc.getObject("Box")]

        # Act
        lines = self._lines(expand=["LG"])

        # Assert
        index = lines.index("v [LINKGROUP] LG")
        self.assertEqual(lines[index + 1], "`-- v [BOX] Box")
        self.assertNotIn("v [BOX] Box", lines)

    def test_should_refuse_a_name_pattern_that_is_not_a_regex(self):
        # Arrange
        filters = {"name_pattern": "("}

        # Act
        act = lambda: self._call(filters=filters)  # noqa: E731

        # Assert
        self.assertRaisesRegex(ValidationError, "invalid name_pattern", act)

    def test_should_show_the_full_path_when_focused_on_a_feature_inside_a_body(self):
        # Arrange
        focus = "boss"

        # Act
        lines = self._lines(focus=focus)

        # Assert
        self.assertEqual(
            lines, ["path: piece > boss", "- [PAD] boss", "`-- v [SKETCH] boss_sketch"]
        )

    def test_should_match_the_same_lines_when_types_names_the_type_id_or_a_lowercase_code(self):
        # Arrange
        by_code = self._lines(focus="piece", filters={"types": ["DPLANE"]})

        # Act
        by_type_id = self._lines(focus="piece", filters={"types": ["PartDesign::Plane"]})
        by_lowercase = self._lines(focus="piece", filters={"types": ["dplane"]})

        # Assert
        self.assertEqual(by_type_id, by_code)
        self.assertEqual(by_lowercase, by_code)

    def test_should_open_the_named_child_when_focus_and_expand_are_given_together(self):
        # Arrange
        expand = ["boss"]

        # Act
        lines = self._lines(focus="piece", expand=expand)

        # Assert
        index = lines.index("|-- - [PAD] boss")
        self.assertEqual(lines[index + 1], "|   `-- v [SKETCH] boss_sketch")
        self.assertEqual(lines[-1], "`-- v [POCKET] hole (+1) *tip")

    def test_should_refuse_an_expand_name_outside_the_focus_subtree(self):
        # Arrange
        expand = ["base_pad"]

        # Act
        act = lambda: self._call(focus="piece", expand=expand)  # noqa: E731

        # Assert
        self.assertRaisesRegex(ValidationError, "base_pad is outside focus piece", act)

    def test_should_stay_under_2000_chars_when_called_in_the_call_128_shape(self):
        # Arrange
        request = {"focus": "piece", "depth": 3}

        # Act
        text = self._call(**request)["text_blocks"][0]

        # Assert
        self.assertLess(len(text), 2000)
        self.assertIn("hole_sketch", text)


if __name__ == "__main__":
    unittest.main()
