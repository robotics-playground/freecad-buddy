"""In-FreeCAD tests for ``feature_part_primitive`` and ``feature_part_boolean``.

Run via ``FreeCADCmd tests/run_tests.py``. Expected values are analytic (hand-computed volumes and
coordinates), never read from the tool under test. Every fixture is a real FreeCAD object: the
untrusted inputs are real reversed, self-intersecting and non-solid shapes.
"""

import math
import time

import FreeCAD as App
import Part

from freecad_buddy.contracts.fingerprint import massprops_equal
from freecad_buddy.usecases import confirm, features, fingerprint, shape_trust, transaction
from freecad_buddy.usecases.documents import ValidationError
from infc.test_feature_tools import _FeatureFixture, _snapshot_leftovers, mm


class _PartFixture(_FeatureFixture):
    def add_shape(self, name, shape):
        obj = self.document().addObject("Part::Feature", name)
        obj.Shape = shape
        self.document().recompute()
        return obj

    def add_box(self, name, x=0.0, y=0.0, z=0.0, size=10.0):
        return self.add_shape(name, Part.makeBox(size, size, size, App.Vector(x, y, z)))

    def crossing_family(self, axis, count, pitch):
        """``count`` parallel cylinders of radius 1, ``pitch`` apart, long enough to span the span.

        The "x" family runs along y at x offsets and the "y" family along x at y offsets; each
        cylinder is ``pitch * count + 2`` long, so every solid of one family crosses every solid
        of the other.
        """
        length = pitch * count + 2.0
        solids = []
        for index in range(count):
            offset = pitch * index
            if axis == "x":
                solids.append(
                    Part.makeCylinder(1.0, length, App.Vector(offset, 0, 0), App.Vector(0, 1, 0))
                )
            else:
                solids.append(
                    Part.makeCylinder(1.0, length, App.Vector(0, offset, 0), App.Vector(1, 0, 0))
                )
        return Part.Compound(solids)

    def two_cubes(self):
        """A 10 mm cube and the same cube shifted 5 mm along x: the overlap is 5 x 10 x 10."""
        self.add_box("A")
        self.add_box("B", x=5.0)

    def boolean(self, **overrides):
        args = {
            "doc": self.handle,
            "operation": "cut",
            "base": "A",
            "tools": ["B"],
            "name": "Result",
        }
        args.update(overrides)
        return features.feature_part_boolean(self.registry, **args)

    def primitive(self, **overrides):
        args = {"doc": self.handle, "kind": "box", "name": "Part1"}
        if "kind" not in overrides or overrides["kind"] == "box":
            args.update({"length": mm(10.0), "width": mm(20.0), "height": mm(30.0)})
        args.update(overrides)
        return features.feature_part_primitive(self.registry, **args)

    def preview(self, operation):
        from freecad_buddy.hosts.tool_catalog import preview_op_table
        from freecad_buddy.usecases import preview

        return preview.preview_dry_run(
            self.registry, preview_op_table(), None, doc=self.handle, operation=operation
        )

    def volume(self, name):
        return self.document().getObject(name).Shape.Volume

    def fingerprint(self):
        return fingerprint.fingerprint(self.document(), fresh=True)

    def visibility(self, *names):
        return [self.document().getObject(name).Visibility for name in names]

    def assert_refusal(self, envelope_or_call, code, status="INVALID_INPUT"):
        """Assert a refusal with ``code``, with the document untouched and no snapshot written."""
        before = self.fingerprint()
        count = self.object_count()
        with self.assertRaises(features.PartToolRefusal) as caught:
            envelope_or_call()
        self.assertEqual(caught.exception.code, code)
        self.assertEqual(self.fingerprint(), before)
        self.assertEqual(self.object_count(), count)
        self.assertEqual(_snapshot_leftovers(), [])
        return str(caught.exception)

    def assert_rolled_back(self, envelope, code, before_record, before_count):
        self.assertEqual(envelope["status"], "RECOMPUTE_ERROR", envelope.get("detail"))
        self.assertEqual(envelope["detail"]["code"], code)
        block = envelope["structured_content"]["mutation"]
        self.assertTrue(block["rolled_back"])
        self.assertIsNotNone(block["rollback_proven"])
        # The bracket proves a rollback by digest, or by mass properties when the recompute after
        # the abort rewrote B-rep bytes of an unchanged shape (transaction._prove_rollback).
        self.assertTrue(massprops_equal(self.fingerprint(), before_record))
        self.assertEqual(self.object_count(), before_count)


class PartPrimitiveTest(_PartFixture):
    def test_Should_make_a_document_level_box_When_all_three_sizes_are_given(self):
        # Arrange
        expected_volume = 10.0 * 20.0 * 30.0

        # Act
        envelope = self.primitive()

        # Assert
        state = self.assert_volume(envelope, expected_volume)
        obj = self.document().getObject("Part1")
        self.assertEqual(obj.TypeId, "Part::Box")
        self.assertEqual((obj.Name, obj.Label), ("Part1", "Part1"))
        self.assertIsNone(obj.getParentGeoFeatureGroup())
        self.assertEqual(state["body"], "")
        self.assertFalse(state["is_tip"])
        self.assertEqual(state["shape_summary"]["solid_count"], 1)

    def test_Should_make_the_analytic_volume_When_each_kind_is_built(self):
        # Arrange
        cases = {
            "cylinder": ({"radius": mm(5.0), "height": mm(10.0)}, math.pi * 25.0 * 10.0),
            "cone": (
                {"radius1": mm(5.0), "radius2": mm(0.0), "height": mm(10.0)},
                math.pi * 25.0 * 10.0 / 3.0,
            ),
            "cone with a flat top": (
                {"radius1": mm(5.0), "radius2": mm(2.0), "height": mm(10.0)},
                math.pi * 10.0 / 3.0 * (25.0 + 10.0 + 4.0),
            ),
            "sphere": ({"radius": mm(5.0)}, 4.0 / 3.0 * math.pi * 125.0),
            "torus": ({"radius1": mm(10.0), "radius2": mm(2.0)}, 2.0 * math.pi**2 * 10.0 * 4.0),
        }
        for label, (dimensions, expected) in cases.items():
            with self.subTest(kind=label):
                kind = label.split(" ")[0]
                name = label.replace(" ", "_")

                # Act
                envelope = self.primitive(kind=kind, name=name, **dimensions)

                # Assert
                self.assert_volume(envelope, expected, places=3)

    def test_Should_move_the_box_When_a_placement_with_a_rotation_is_given(self):
        # Arrange
        placement = {
            "base": {"x": mm(1.0), "y": mm(2.0), "z": mm(3.0)},
            "rotation": {"axis": [0, 0, 1], "angle": {"value": 90.0, "unit": "deg"}},
        }

        # Act
        envelope = self.primitive(placement=placement)

        # Assert
        self.assert_ok(envelope)
        box = self.document().getObject("Part1").Shape.BoundBox
        low = (box.XMin, box.YMin, box.ZMin)
        high = (box.XMax, box.YMax, box.ZMax)
        for got, want in zip(low + high, (-19.0, 2.0, 3.0, 1.0, 12.0, 33.0), strict=True):
            self.assertAlmostEqual(got, want, places=6)

    def test_Should_use_the_shared_placement_parser_When_a_placement_is_given(self):
        # Arrange
        calls = []
        original = features._placement_value

        def spy(raw, what, current=None):
            calls.append(what)
            return original(raw, what, current)

        features._placement_value = spy
        try:
            # Act
            self.primitive(placement={"base": {"x": mm(4.0)}})
        finally:
            features._placement_value = original

        # Assert
        self.assertIn("placement", calls)
        self.assertEqual(tuple(self.document().getObject("Part1").Placement.Base), (4.0, 0, 0))

    def test_Should_refuse_before_the_bracket_When_a_dimension_cannot_be_built(self):
        # Arrange
        cases = {
            "box length 0": ({"length": mm(0.0)}, "part_primitive.dimension"),
            "box negative width": ({"width": mm(-1.0)}, "part_primitive.dimension"),
            "cylinder radius 0": (
                {"kind": "cylinder", "radius": mm(0.0), "height": mm(5.0)},
                "part_primitive.dimension",
            ),
            "cone both radii 0": (
                {"kind": "cone", "radius1": mm(0.0), "radius2": mm(0.0), "height": mm(5.0)},
                "part_primitive.dimension",
            ),
            "cone negative radius": (
                {"kind": "cone", "radius1": mm(-1.0), "radius2": mm(2.0), "height": mm(5.0)},
                "part_primitive.dimension",
            ),
            "cone height 0": (
                {"kind": "cone", "radius1": mm(3.0), "radius2": mm(2.0), "height": mm(0.0)},
                "part_primitive.dimension",
            ),
            "sphere radius 0": (
                {"kind": "sphere", "radius": mm(0.0)},
                "part_primitive.dimension",
            ),
            "torus radius2 above radius1": (
                {"kind": "torus", "radius1": mm(2.0), "radius2": mm(3.0)},
                "part_primitive.dimension",
            ),
            "torus radius2 equal to radius1": (
                {"kind": "torus", "radius1": mm(2.0), "radius2": mm(2.0)},
                "part_primitive.dimension",
            ),
            "box with a radius": ({"radius": mm(3.0)}, "part_primitive.fields"),
            "box missing the height": ({"height": None}, "part_primitive.fields"),
            "sphere with a height": (
                {"kind": "sphere", "radius": mm(2.0), "height": mm(2.0)},
                "part_primitive.fields",
            ),
        }
        for label, (overrides, code) in cases.items():
            with self.subTest(case=label):
                # Act and Assert
                self.assert_refusal(lambda o=overrides: self.primitive(**o), code)

    def test_Should_refuse_with_a_plain_error_When_a_value_is_malformed(self):
        # Arrange
        cases = {
            "unit other than mm": {"length": {"value": 1.0, "unit": "cm"}},
            "non-finite value": {"length": mm(float("inf"))},
            "nan value": {"length": mm(float("nan"))},
            "bare number": {"length": 5.0},
            "unknown kind": {"kind": "pyramid"},
            "bad name": {"name": "1bad name"},
            "bad placement unit": {"placement": {"base": {"x": {"value": 1, "unit": "deg"}}}},
            "unknown placement key": {"placement": {"scale": 2}},
            "zero axis": {
                "placement": {"rotation": {"axis": [0, 0, 0], "angle": {"value": 1, "unit": "deg"}}}
            },
        }
        for label, overrides in cases.items():
            with self.subTest(case=label):
                before = self.fingerprint()

                # Act
                with self.assertRaises(ValidationError):
                    self.primitive(**overrides)

                # Assert
                self.assertEqual(self.fingerprint(), before)
                self.assertEqual(_snapshot_leftovers(), [])

    def test_Should_refuse_When_the_name_is_taken(self):
        # Arrange
        self.assert_ok(self.primitive())

        # Act
        with self.assertRaises(ValidationError) as caught:
            self.primitive()

        # Assert
        self.assertIn("already exists", str(caught.exception))

    def test_Should_not_need_partdesign_When_a_primitive_is_made(self):
        # Arrange
        original = features._require_partdesign
        calls = []
        features._require_partdesign = lambda: calls.append(1)
        try:
            # Act
            envelope = self.primitive()
        finally:
            features._require_partdesign = original

        # Assert
        self.assert_ok(envelope)
        self.assertEqual(calls, [])

    def test_Should_remove_the_box_When_the_primitive_is_undone(self):
        # Arrange
        pre_op = self.fingerprint()
        self.assert_ok(self.primitive())

        # Act
        undone = self.registry.document_undo(doc=self.handle, expect_fingerprint=pre_op["digest"])

        # Assert
        self.assertEqual(undone["status"], "OK", undone.get("detail"))
        self.assertIsNone(self.document().getObject("Part1"))

    def test_Should_change_the_fingerprint_When_a_primitive_is_made(self):
        # Arrange
        before = self.fingerprint()

        # Act
        self.assert_ok(self.primitive())

        # Assert
        self.assertNotEqual(self.fingerprint(), before)

    def test_Should_demand_a_confirm_When_the_operator_posture_is_off(self):
        # Arrange
        confirm.set_auto_approve(False)
        before = self.fingerprint()

        # Act
        with self.assertRaises(ValidationError) as caught:
            self.primitive()

        # Assert
        self.assertIn("requires a confirm", str(caught.exception))
        self.assertEqual(self.fingerprint(), before)
        self.assertIsNone(self.document().getObject("Part1"))

    def test_Should_report_a_valid_preview_When_dry_run_is_asked_for_a_primitive(self):
        # Arrange
        operation = {
            "tool": "feature_part_primitive",
            "args": {
                "kind": "box",
                "name": "Part1",
                "length": mm(1.0),
                "width": mm(2.0),
                "height": mm(3.0),
            },
        }
        before = self.fingerprint()

        # Act
        envelope = self.preview(operation)

        # Assert
        self.assertEqual(envelope["status"], "OK", envelope.get("detail"))
        self.assertIsNone(self.document().getObject("Part1"))
        self.assertEqual(self.fingerprint(), before)


class PartBooleanTest(_PartFixture):
    def test_Should_leave_the_analytic_volume_When_each_operation_runs_on_two_overlapping_cubes(
        self,
    ):
        # Arrange
        expected = {"cut": 500.0, "common": 500.0, "fuse": 1500.0}
        for operation, volume in expected.items():
            with self.subTest(operation=operation):
                self.two_cubes()

                # Act
                envelope = self.boolean(operation=operation, name=f"R_{operation}")

                # Assert
                state = self.assert_volume(envelope, volume, places=6)
                self.assertEqual(state["shape_summary"]["solid_count"], 1)
                self.document().removeObject(f"R_{operation}")
                self.document().removeObject("A")
                self.document().removeObject("B")

    def test_Should_build_the_two_input_types_When_one_tool_is_given(self):
        # Arrange
        self.two_cubes()
        types = {"cut": "Part::Cut", "fuse": "Part::Fuse", "common": "Part::Common"}

        for operation, type_id in types.items():
            with self.subTest(operation=operation):
                # Act
                self.assert_ok(self.boolean(operation=operation, name=f"R_{operation}"))

                # Assert
                result = self.document().getObject(f"R_{operation}")
                self.assertEqual(result.TypeId, type_id)
                self.assertEqual((result.Base.Name, result.Tool.Name), ("A", "B"))

    def test_Should_cut_the_fuse_of_the_tools_When_several_tools_are_given(self):
        # Arrange
        self.add_shape("Plate", Part.makeBox(20.0, 10.0, 10.0))
        self.add_shape("Bar1", Part.makeBox(2.0, 10.0, 10.0, App.Vector(2.0, 0, 0)))
        self.add_shape("Bar2", Part.makeBox(4.0, 10.0, 10.0, App.Vector(10.0, 0, 0)))
        expected = 20.0 * 10.0 * 10.0 - 2.0 * 100.0 - 4.0 * 100.0

        # Act
        envelope = self.boolean(base="Plate", tools=["Bar1", "Bar2"])

        # Assert
        self.assert_volume(envelope, expected, places=6)
        document = self.document()
        fused = document.getObject("Result_tools")
        self.assertEqual(fused.TypeId, "Part::MultiFuse")
        self.assertEqual([obj.Name for obj in fused.Shapes], ["Bar1", "Bar2"])
        cut = document.getObject("Result")
        self.assertEqual(cut.TypeId, "Part::Cut")
        self.assertEqual((cut.Base.Name, cut.Tool.Name), ("Plate", "Result_tools"))
        self.assertEqual(self.visibility("Plate", "Bar1", "Bar2", "Result_tools"), [False] * 4)
        self.assertTrue(cut.Visibility)

    def test_Should_fuse_every_input_When_several_tools_are_fused(self):
        # Arrange
        self.add_box("A")
        self.add_box("B", x=20.0)
        self.add_box("C", x=40.0)

        # Act
        envelope = self.boolean(operation="fuse", tools=["B", "C"])

        # Assert
        state = self.assert_volume(envelope, 3000.0, places=6)
        self.assertEqual(state["shape_summary"]["solid_count"], 3)
        self.assertEqual(self.document().getObject("Result").TypeId, "Part::MultiFuse")

    def test_Should_intersect_the_base_with_every_tool_When_several_tools_are_common(self):
        # Arrange
        self.add_box("A")
        self.add_box("B", x=5.0)
        self.add_box("C", x=7.0)
        expected = 3.0 * 10.0 * 10.0

        # Act
        envelope = self.boolean(operation="common", tools=["B", "C"])

        # Assert
        self.assert_volume(envelope, expected, places=6)
        self.assertEqual(self.document().getObject("Result").TypeId, "Part::MultiCommon")

    def test_Should_refuse_the_common_When_one_of_several_tools_misses_the_others(self):
        # Arrange
        self.add_box("A")
        self.add_box("B", x=5.0)
        self.add_box("Far", x=100.0)
        before, count = self.fingerprint(), self.object_count()

        # Act
        envelope = self.boolean(operation="common", tools=["B", "Far"])

        # Assert
        self.assert_rolled_back(envelope, "part_boolean.empty_result", before, count)

    def test_Should_hide_the_inputs_and_keep_the_result_visible_When_a_boolean_runs(self):
        # Arrange
        self.two_cubes()

        # Act
        self.assert_ok(self.boolean())

        # Assert
        self.assertEqual(self.visibility("A", "B", "Result"), [False, False, True])

    def test_Should_set_refine_on_every_object_made_When_refine_is_false(self):
        # Arrange
        self.add_shape("Plate", Part.makeBox(20.0, 10.0, 10.0))
        self.add_shape("Bar1", Part.makeBox(2.0, 10.0, 10.0, App.Vector(2.0, 0, 0)))
        self.add_shape("Bar2", Part.makeBox(4.0, 10.0, 10.0, App.Vector(10.0, 0, 0)))

        # Act
        self.assert_ok(self.boolean(base="Plate", tools=["Bar1", "Bar2"], refine=False))

        # Assert
        document = self.document()
        self.assertFalse(document.getObject("Result").Refine)
        self.assertFalse(document.getObject("Result_tools").Refine)

    def test_Should_set_refine_true_When_refine_is_left_out(self):
        # Arrange
        self.two_cubes()

        # Act
        self.assert_ok(self.boolean())

        # Assert
        self.assertTrue(self.document().getObject("Result").Refine)

    def test_Should_roll_back_with_the_empty_code_When_a_common_has_disjoint_inputs(self):
        # Arrange
        self.add_box("A")
        self.add_box("B", x=100.0)
        before, count = self.fingerprint(), self.object_count()
        visibility = self.visibility("A", "B")

        # Act
        envelope = self.boolean(operation="common")

        # Assert
        self.assert_rolled_back(envelope, "part_boolean.empty_result", before, count)
        self.assertIsNone(self.document().getObject("Result"))
        self.assertEqual(self.visibility("A", "B"), visibility)

    def test_Should_roll_back_with_the_empty_code_When_the_tool_removes_the_whole_base(self):
        # Arrange
        self.add_box("A")
        self.add_box("B", x=-5.0, y=-5.0, z=-5.0, size=30.0)
        before, count = self.fingerprint(), self.object_count()

        # Act
        envelope = self.boolean(operation="cut")

        # Assert
        self.assert_rolled_back(envelope, "part_boolean.empty_result", before, count)

    def test_Should_roll_back_with_the_empty_code_When_the_common_inputs_only_touch(self):
        # Arrange
        self.add_box("A")
        self.add_box("B", x=10.0)
        before, count = self.fingerprint(), self.object_count()

        # Act
        envelope = self.boolean(operation="common")

        # Assert
        self.assert_rolled_back(envelope, "part_boolean.empty_result", before, count)

    def test_Should_restore_the_visibility_of_the_inputs_When_an_empty_result_rolls_back(self):
        # Arrange
        self.add_box("A")
        self.add_box("B", x=100.0)
        self.document().getObject("A").Visibility = True

        # Act
        self.boolean(operation="common")

        # Assert
        self.assertEqual(self.visibility("A", "B"), [True, True])

    def test_Should_hand_the_bracket_a_state_probe_that_reads_visibility_When_a_boolean_runs(self):
        # Arrange
        # The fingerprint sees shapes only, so only a probe makes the rollback proof cover the
        # Visibility the op changes.
        self.two_cubes()
        seen = []
        original = transaction.run_mutation

        def spy(*args, **kwargs):
            seen.append(kwargs.get("state_probe"))
            return original(*args, **kwargs)

        transaction.run_mutation = spy
        try:
            # Act
            self.assert_ok(self.boolean())
        finally:
            transaction.run_mutation = original

        # Assert
        probe = seen[0]
        self.assertIsNotNone(probe)
        before = probe(self.document())
        self.document().getObject("A").Visibility = True
        self.assertNotEqual(probe(self.document()), before)

    def test_Should_keep_undo_usable_When_a_result_was_refused_and_rolled_back(self):
        # Arrange
        self.add_box("A")
        self.add_box("B", x=100.0)
        self.boolean(operation="common")

        # Act
        self.assert_ok(self.primitive())
        undone = self.registry.document_undo(doc=self.handle)

        # Assert
        self.assertEqual(undone["status"], "OK", undone.get("detail"))
        self.assertIsNone(self.document().getObject("Part1"))
        self.assertIsNotNone(self.document().getObject("A"))

    def test_Should_restore_result_intermediate_and_visibility_When_a_boolean_is_undone(self):
        # Arrange
        self.add_shape("Plate", Part.makeBox(20.0, 10.0, 10.0))
        self.add_shape("Bar1", Part.makeBox(2.0, 10.0, 10.0, App.Vector(2.0, 0, 0)))
        self.add_shape("Bar2", Part.makeBox(4.0, 10.0, 10.0, App.Vector(10.0, 0, 0)))
        pre_op = self.fingerprint()
        self.assert_ok(self.boolean(base="Plate", tools=["Bar1", "Bar2"]))
        self.assertEqual(self.visibility("Plate", "Bar1", "Bar2"), [False] * 3)

        # Act
        undone = self.registry.document_undo(doc=self.handle, expect_fingerprint=pre_op["digest"])

        # Assert
        self.assertEqual(undone["status"], "OK", undone.get("detail"))
        document = self.document()
        self.assertIsNone(document.getObject("Result"))
        self.assertIsNone(document.getObject("Result_tools"))
        self.assertEqual(self.visibility("Plate", "Bar1", "Bar2"), [True] * 3)

    def test_Should_refuse_an_invalid_result_When_the_result_shape_is_a_bowtie_solid(self):
        # Arrange
        corners = [(0, 0), (10, 10), (10, 0), (0, 10), (0, 0)]
        wire = Part.makePolygon([App.Vector(x, y, 0) for x, y in corners])
        bowtie = self.add_shape("Result", Part.Face(wire).extrude(App.Vector(0, 0, 10)))
        check = features._part_boolean_result_check("Result", "cut", ["A", "B"])

        # Act
        def act():
            check(self.document())

        # Assert
        self.assertFalse(bowtie.Shape.isValid(), "the fixture must be an invalid solid")
        with self.assertRaises(transaction.RecomputeFailure) as caught:
            act()
        self.assertEqual(caught.exception.code, "part_boolean.invalid_result")

    def test_Should_refuse_a_result_with_a_reversed_solid_When_checked(self):
        # Arrange
        reversed_box = Part.makeBox(10, 10, 10).reversed()
        self.add_shape("Result", reversed_box)
        check = features._part_boolean_result_check("Result", "fuse", ["A", "B"])

        # Act
        def act():
            check(self.document())

        # Assert
        self.assertLess(reversed_box.Volume, 0.0, "the fixture must have a negative volume")
        with self.assertRaises(transaction.RecomputeFailure) as caught:
            act()
        self.assertEqual(caught.exception.code, "part_boolean.empty_result")

    def test_Should_report_the_invalid_code_When_an_input_fails_to_recompute(self):
        # Arrange
        # A box of length 0 fails its own recompute ("Length of box too small"), and the cut
        # that uses it is left Touched with no solid, not Invalid.
        self.add_box("A")
        document = self.document()
        broken = document.addObject("Part::Box", "B")
        broken.Length = 0.0
        cut = document.addObject("Part::Cut", "Result")
        cut.Base, cut.Tool = document.getObject("A"), broken
        document.recompute()
        check = features._part_boolean_result_check("Result", "cut", ["A", "B"])

        # Act
        def act():
            check(document)

        # Assert
        self.assertNotEqual(set(cut.State) & {"Invalid", "Error", "Touched"}, set())
        with self.assertRaises(transaction.RecomputeFailure) as caught:
            act()
        self.assertEqual(caught.exception.code, "part_boolean.invalid_result")

    def test_Should_name_the_inputs_When_the_result_is_empty(self):
        # Arrange
        self.add_box("A")
        self.add_box("B", x=100.0)

        # Act
        envelope = self.boolean(operation="common")

        # Assert
        message = envelope["detail"]["message"]
        for expected in ("common", "Result", "A", "B"):
            self.assertIn(expected, message)

    def test_Should_report_the_kernel_message_with_the_invalid_code_When_the_boolean_fails(self):
        # Arrange
        # FreeCAD's own model check (Mod/Part/Boolean/CheckModel) fails a boolean whose input is
        # a self-intersecting solid and leaves the object in an error state with no shape.
        corners = [(0, 0), (10, 10), (10, 0), (0, 10), (0, 0)]
        wire = Part.makePolygon([App.Vector(x, y, 0) for x, y in corners])
        self.add_shape("Bowtie", Part.Face(wire).extrude(App.Vector(0, 0, 10)))
        self.add_box("B", x=5.0)
        document = self.document()
        cut = document.addObject("Part::Cut", "Result")
        cut.Base, cut.Tool = document.getObject("Bowtie"), document.getObject("B")
        document.recompute()
        check = features._part_boolean_result_check("Result", "cut", ["Bowtie", "B"])

        # Act
        def act():
            check(document)

        # Assert
        self.assertIn("Invalid", cut.State, "the fixture must be a failed real boolean")
        with self.assertRaises(transaction.RecomputeFailure) as caught:
            act()
        self.assertEqual(caught.exception.code, "part_boolean.invalid_result")
        self.assertIn("Bowtie", str(caught.exception))
        self.assertTrue(cut.getStatusString())
        self.assertIn(cut.getStatusString(), str(caught.exception))

    def test_Should_roll_back_and_leave_no_intermediate_When_a_several_tool_cut_removes_the_base(
        self,
    ):
        # Arrange
        self.add_box("Plate", size=10.0)
        self.add_box("Left", x=-1.0, y=-1.0, z=-1.0, size=7.0)
        self.add_box("Right", x=4.0, y=-1.0, z=-1.0, size=7.0)
        self.add_box("Top", x=-1.0, y=-1.0, z=-1.0, size=12.0)
        visibility = self.visibility("Plate", "Left", "Right", "Top")
        before, count = self.fingerprint(), self.object_count()

        # Act
        envelope = self.boolean(base="Plate", tools=["Left", "Right", "Top"])

        # Assert
        self.assert_rolled_back(envelope, "part_boolean.empty_result", before, count)
        self.assertIsNone(self.document().getObject("Result_tools"))
        self.assertEqual(self.visibility("Plate", "Left", "Right", "Top"), visibility)

    def test_Should_accept_a_result_with_two_solids_When_disjoint_solids_are_fused(self):
        # Arrange
        self.add_box("A")
        self.add_box("B", x=50.0)

        # Act
        envelope = self.boolean(operation="fuse")

        # Assert
        state = self.assert_volume(envelope, 2000.0, places=6)
        self.assertEqual(state["shape_summary"]["solid_count"], 2)


class PartBooleanRefusalTest(_PartFixture):
    def test_Should_refuse_a_reversed_input_with_the_untrusted_code_When_any_operation_runs(self):
        # Arrange
        reversed_box = Part.makeBox(10, 10, 10).reversed()
        self.add_shape("Rev", reversed_box)
        self.add_box("B", x=5.0)
        for operation in ("cut", "fuse", "common"):
            with self.subTest(operation=operation):
                # Act and Assert
                message = self.assert_refusal(
                    lambda op=operation: self.boolean(operation=op, base="Rev"),
                    "part_boolean.untrusted_shape",
                )
                self.assertIn("Rev", message)
                self.assertIn("reversed", message)

    def test_Should_refuse_a_self_intersecting_input_When_a_common_runs(self):
        # Arrange
        corners = [(0, 0), (10, 10), (10, 0), (0, 10), (0, 0)]
        wire = Part.makePolygon([App.Vector(x, y, 0) for x, y in corners])
        bowtie = self.add_shape("Bowtie", Part.Face(wire).extrude(App.Vector(0, 0, 10)))
        self.add_box("B", x=5.0)

        # Act
        message = self.assert_refusal(
            lambda: self.boolean(operation="common", base="Bowtie"),
            "part_boolean.untrusted_shape",
        )

        # Assert
        self.assertFalse(bowtie.Shape.isValid())
        self.assertIn("Bowtie", message)

    def test_Should_refuse_a_tool_input_that_is_untrusted_When_the_base_is_fine(self):
        # Arrange
        self.add_box("A")
        self.add_shape("Rev", Part.makeBox(10, 10, 10).reversed())

        # Act and Assert
        message = self.assert_refusal(
            lambda: self.boolean(tools=["Rev"]), "part_boolean.untrusted_shape"
        )
        self.assertIn("Rev", message)

    def test_Should_refuse_non_solid_inputs_When_a_sketch_a_wire_a_face_or_a_shell_is_named(self):
        # Arrange
        self.add_box("A")
        box = Part.makeBox(10, 10, 10)
        shapes = {
            "Wire": Part.makePolygon([App.Vector(0, 0, 0), App.Vector(10, 0, 0)]),
            "Face": box.Faces[0],
            "Shell": Part.Shell(box.Faces),
        }
        for name, shape in shapes.items():
            self.add_shape(name, shape)
        sketch = self.document().addObject("Sketcher::SketchObject", "Sketch")
        sketch.addGeometry(Part.LineSegment(App.Vector(0, 0, 0), App.Vector(5, 0, 0)))
        self.document().recompute()

        for name in [*shapes, "Sketch"]:
            with self.subTest(name=name):
                # Act and Assert
                message = self.assert_refusal(
                    lambda n=name: self.boolean(tools=[n]), "part_boolean.untrusted_shape"
                )
                self.assertIn(name, message)

    def test_Should_refuse_an_object_without_a_shape_When_it_is_named_as_an_input(self):
        # Arrange
        self.add_box("A")
        self.document().addObject("App::FeaturePython", "Plain")

        # Act and Assert
        self.assert_refusal(lambda: self.boolean(tools=["Plain"]), "part_boolean.untrusted_shape")

    def test_Should_refuse_a_body_feature_and_its_sketch_When_they_are_named_as_inputs(self):
        # Arrange
        self.add_box("B", x=5.0)
        body = self.empty_body()
        self.rect_sketch(body, "Profile", 0.0, 0.0, 8.0, 16.0)
        pad = features.feature_pad(
            self.registry,
            doc=self.handle,
            body="Body",
            profile="Profile",
            name="Block",
            length=mm(5.0),
        )
        self.assert_ok(pad)

        for name in ("Block", "Profile"):
            with self.subTest(name=name):
                # Act and Assert
                message = self.assert_refusal(
                    lambda n=name: self.boolean(base=n, tools=["B"]),
                    "part_boolean.not_top_level",
                )
                self.assertIn(name, message)
                self.assertIn("Body", message)

    def test_Should_refuse_an_app_part_member_When_it_is_named_as_an_input(self):
        # Arrange
        self.add_box("A")
        member = self.add_box("Member", x=5.0)
        container = self.document().addObject("App::Part", "Assembly")
        container.addObject(member)
        self.document().recompute()

        # Act and Assert
        message = self.assert_refusal(
            lambda: self.boolean(tools=["Member"]), "part_boolean.not_top_level"
        )
        self.assertIn("Assembly", message)

    def test_Should_accept_a_body_as_the_base_When_the_body_is_top_level(self):
        # Arrange
        body = self.empty_body()
        self.rect_sketch(body, "Profile", 0.0, 0.0, 10.0, 10.0)
        pad = features.feature_pad(
            self.registry,
            doc=self.handle,
            body="Body",
            profile="Profile",
            name="Block",
            length=mm(10.0),
        )
        self.assert_ok(pad)
        self.add_box("Cutter", x=5.0)

        # Act
        envelope = self.boolean(base="Body", tools=["Cutter"])

        # Assert
        self.assert_volume(envelope, 500.0, places=6)
        self.assertEqual(self.visibility("Body", "Cutter"), [False, False])

    def test_Should_refuse_before_the_bracket_When_the_inputs_are_not_acceptable(self):
        # Arrange
        self.two_cubes()
        cases = {
            "base repeated in tools": {"tools": ["A"]},
            "tool repeated": {"tools": ["B", "B"]},
            "empty tools": {"tools": []},
            "tools not a list": {"tools": "B"},
            "tools is an int": {"tools": 5},
            "tools is a bool": {"tools": True},
            "tools is null": {"tools": None},
            "twenty-one tools": {"tools": [f"T{index}" for index in range(21)]},
        }
        for label, overrides in cases.items():
            with self.subTest(case=label):
                # Act and Assert
                self.assert_refusal(
                    lambda o=overrides: self.boolean(**o), "part_boolean.invalid_input"
                )

    def test_Should_refuse_with_a_plain_error_When_a_name_or_argument_is_unknown(self):
        # Arrange
        self.two_cubes()
        self.add_box("Taken", x=50.0)
        cases = {
            "unknown base": {"base": "Nope"},
            "unknown tool": {"tools": ["Nope"]},
            "base missing": {"base": None},
            "unknown operation": {"operation": "slice"},
            "operation missing": {"operation": None},
            "name taken": {"name": "Taken"},
            "bad name": {"name": "a b"},
            "name missing": {"name": None},
            "refine not a bool": {"refine": "yes"},
        }
        for label, overrides in cases.items():
            with self.subTest(case=label):
                before = self.fingerprint()

                # Act
                with self.assertRaises(ValidationError):
                    self.boolean(**overrides)

                # Assert
                self.assertEqual(self.fingerprint(), before)
                self.assertEqual(_snapshot_leftovers(), [])

    def test_Should_refuse_a_taken_intermediate_name_When_a_cut_uses_several_tools(self):
        # Arrange
        self.two_cubes()
        self.add_box("C", x=-5.0)
        self.add_box("Result_tools", x=60.0)

        # Act
        with self.assertRaises(ValidationError) as caught:
            self.boolean(tools=["B", "C"])

        # Assert
        self.assertIn("Result_tools", str(caught.exception))
        self.assertIsNone(self.document().getObject("Result"))

    def test_Should_keep_the_documented_limits_When_the_constants_are_read(self):
        # Arrange and Act
        limits = (
            features._PART_BOOLEAN_MAX_FACES,
            features._PART_BOOLEAN_MAX_SOLID_PAIRS,
            features._PART_BOOLEAN_MAX_TOOLS,
        )

        # Assert
        self.assertEqual(limits, (3000, 1000, 20))

    def test_Should_refuse_at_the_shipped_face_limit_When_the_inputs_hold_3012_faces(self):
        # Arrange
        self.add_box("A")
        many = Part.Compound(
            [Part.makeBox(1, 1, 1, App.Vector(20 + 2 * i, 0, 0)) for i in range(501)]
        )
        self.add_shape("Many", many)

        # Act and Assert
        message = self.assert_refusal(
            lambda: self.boolean(tools=["Many"]), "part_boolean.too_complex"
        )
        self.assertIn("3012 faces", message)

    def test_Should_refuse_at_the_shipped_pair_limit_When_the_inputs_hold_1100_pairs(self):
        # Arrange
        base = Part.Compound([Part.makeBox(1, 1, 1, App.Vector(2 * i, 0, 0)) for i in range(100)])
        tool = Part.Compound([Part.makeBox(1, 1, 1, App.Vector(2 * i, 5, 0)) for i in range(11)])
        self.add_shape("Many", base)
        self.add_shape("Few", tool)

        # Act and Assert
        message = self.assert_refusal(
            lambda: self.boolean(base="Many", tools=["Few"]), "part_boolean.too_complex"
        )
        self.assertIn("1100 solid pairs", message)

    def test_Should_count_the_size_before_checking_the_shape_When_an_input_is_too_complex(self):
        # Arrange
        # A reversed compound of 501 boxes is both too complex and untrusted; the cheap size
        # check must answer first so isValid() never runs on an input the tool refuses anyway.
        self.add_box("A")
        boxes = [Part.makeBox(1, 1, 1, App.Vector(20 + 2 * i, 0, 0)) for i in range(501)]
        many = self.add_shape("Many", Part.Compound(boxes).reversed())

        # Act and Assert
        self.assertFalse(
            shape_trust.is_measurable_solid(many.Shape), "the fixture must be an untrusted shape"
        )
        self.assert_refusal(lambda: self.boolean(tools=["Many"]), "part_boolean.too_complex")

    def test_Should_refuse_crossing_tools_When_their_pairs_with_each_other_pass_the_limit(self):
        # Arrange
        # 606 faces and only 200 base-by-tool pairs, but the two families cross each other:
        # 10,200 pairs in all. Raw recompute took 68.9 s in the probe.
        self.add_shape("Plate", Part.makeBox(400.0, 400.0, 10.0))
        self.add_shape("FamilyX", self.crossing_family("x", 100, 3.0))
        self.add_shape("FamilyY", self.crossing_family("y", 100, 3.0))

        # Act and Assert
        message = self.assert_refusal(
            lambda: self.boolean(base="Plate", tools=["FamilyX", "FamilyY"]),
            "part_boolean.too_complex",
        )
        self.assertIn("606 faces", message)
        self.assertIn("10200 solid pairs", message)
        self.assertIn("0 overlapping inside one input", message)

    def test_Should_refuse_an_input_that_is_not_recomputed_When_its_shape_may_be_out_of_date(
        self,
    ):
        # Arrange
        self.add_box("A")
        document = self.document()
        stale = document.addObject("Part::Box", "B")
        stale.Length = 20.0
        before = self.fingerprint()

        # Act
        def act():
            return self.boolean()

        # Assert
        self.assertIn("Touched", stale.State, "the fixture must be a touched object")
        with self.assertRaises(features.PartToolRefusal) as caught:
            act()
        self.assertEqual(caught.exception.code, "part_boolean.untrusted_shape")
        self.assertIn("recompute", str(caught.exception))
        self.assertEqual(self.fingerprint(), before)

    def test_Should_refuse_the_intermediate_name_When_it_is_another_objects_label(self):
        # Arrange
        self.add_box("A")
        self.add_box("B", x=5.0)
        self.add_box("C", x=-5.0)
        self.add_box("D", x=50.0).Label = "Result_tools"

        # Act
        def act():
            return self.boolean(tools=["B", "C"])

        # Assert
        with self.assertRaises(ValidationError) as caught:
            act()
        self.assertIn("Label of D", str(caught.exception))

    def test_Should_refuse_one_compound_of_crossing_solids_When_it_is_the_only_tool(self):
        # Arrange
        # One tool compound of two fully crossing families of 100 cylinders: 606 faces and 200
        # base-by-tool pairs, but 10,000 solid pairs inside the tool. Part::Cut fuses the
        # tool solids pairwise and ran longer than 600 s in the probe.
        self.add_shape("Plate", Part.makeBox(400.0, 400.0, 10.0))
        both = [
            *self.crossing_family("x", 100, 3.0).Solids,
            *self.crossing_family("y", 100, 3.0).Solids,
        ]
        self.add_shape("Crossing", Part.Compound(both))

        # Act and Assert
        message = self.assert_refusal(
            lambda: self.boolean(base="Plate", tools=["Crossing"]), "part_boolean.too_complex"
        )
        self.assertIn("606 faces", message)
        self.assertIn("at least 1201 solid pairs", message)
        self.assertIn("200 across the inputs", message)
        self.assertIn("at least 1001 overlapping inside one input", message)

    def test_Should_count_only_solids_whose_boxes_overlap_When_pairs_inside_an_input_are_counted(
        self,
    ):
        # Arrange
        apart = Part.Compound([Part.makeBox(1, 1, 1, App.Vector(3 * i, 0, 0)) for i in range(5)])
        touching_boxes = Part.Compound(
            [Part.makeBox(2, 2, 2, App.Vector(1 * i, 0, 0)) for i in range(4)]
        )
        offset_in_y = Part.Compound(
            [
                Part.makeBox(2, 2, 2, App.Vector(0, 0, 0)),
                Part.makeBox(2, 2, 2, App.Vector(1, 5, 0)),
            ]
        )

        # Act
        counts = [
            features._overlapping_solid_pairs(shape, 1000)
            for shape in (apart, touching_boxes, offset_in_y)
        ]
        capped = features._overlapping_solid_pairs(touching_boxes, 2)

        # Assert
        self.assertEqual(counts, [0, 5, 0])
        self.assertGreater(capped, 2)

    def test_Should_accept_exactly_twenty_tools_When_they_are_disjoint_boxes(self):
        # Arrange
        self.add_box("Plate", size=100.0)
        names = [f"T{index}" for index in range(20)]
        for index, name in enumerate(names):
            self.add_box(name, x=5.0 * index, y=1.0, z=1.0, size=1.0)

        # Act
        envelope = self.boolean(base="Plate", tools=names)

        # Assert
        self.assert_volume(envelope, 100.0**3 - 20.0, places=4)

    def test_Should_refuse_with_a_plain_error_When_the_kind_is_not_a_string(self):
        # Arrange
        before = self.fingerprint()

        # Act
        def act():
            return features.feature_part_primitive(
                self.registry, doc=self.handle, kind=["box"], name="Part1"
            )

        # Assert
        with self.assertRaises(ValidationError):
            act()
        self.assertEqual(self.fingerprint(), before)

    def test_Should_refuse_a_size_FreeCAD_would_clamp_When_a_radius_is_above_the_stored_range(
        self,
    ):
        # Arrange
        before = self.fingerprint()

        # Act
        def act():
            return features.feature_part_primitive(
                self.registry, doc=self.handle, kind="sphere", name="Ball", radius=mm(1e39)
            )

        # Assert
        with self.assertRaises(features.PartToolRefusal) as caught:
            act()
        self.assertEqual(caught.exception.code, "part_primitive.dimension")
        self.assertEqual(self.fingerprint(), before)

    def test_Should_refuse_a_name_that_is_another_objects_label_When_a_tool_creates_a_part(self):
        # Arrange
        holder = self.add_box("A")
        holder.Label = "Taken"
        self.add_box("B", x=5.0)

        # Act
        def act_primitive():
            return self.primitive(name="Taken")

        def act_boolean():
            return self.boolean(name="Taken")

        # Assert
        for act in (act_primitive, act_boolean):
            with self.subTest(act=act.__name__):
                with self.assertRaises(ValidationError) as caught:
                    act()
                self.assertIn("Label of A", str(caught.exception))
        self.assertIsNone(self.document().getObject("Taken"))

    def test_Should_say_why_the_input_is_untrusted_When_it_is_not_a_solid(self):
        # Arrange
        self.add_box("A")
        box = Part.makeBox(10, 10, 10)
        self.add_shape("Wire", Part.makePolygon([App.Vector(0, 0, 0), App.Vector(10, 0, 0)]))
        self.add_shape("Face", box.Faces[0])
        expected = {
            "Wire": "not made only of solids",
            "Face": "not made only of solids",
        }
        for name, reason in expected.items():
            with self.subTest(name=name):
                # Act
                def act(n=name):
                    return self.boolean(tools=[n])

                # Assert
                with self.assertRaises(features.PartToolRefusal) as caught:
                    act()
                self.assertEqual(caught.exception.code, "part_boolean.untrusted_shape")
                self.assertIn(reason, str(caught.exception))

    def test_Should_refuse_before_any_write_When_the_faces_are_above_the_limit(self):
        # Arrange
        self.two_cubes()
        limit = features._PART_BOOLEAN_MAX_FACES
        features._PART_BOOLEAN_MAX_FACES = 11  # two cubes hold 12 faces
        try:
            # Act and Assert
            message = self.assert_refusal(self.boolean, "part_boolean.too_complex")
        finally:
            features._PART_BOOLEAN_MAX_FACES = limit
        self.assertIn("12 faces", message)
        self.assertIn("limit 11", message)

    def test_Should_run_When_the_faces_are_exactly_at_the_limit(self):
        # Arrange
        self.two_cubes()
        limit = features._PART_BOOLEAN_MAX_FACES
        features._PART_BOOLEAN_MAX_FACES = 12
        try:
            # Act
            envelope = self.boolean()
        finally:
            features._PART_BOOLEAN_MAX_FACES = limit

        # Assert
        self.assert_ok(envelope)

    def test_Should_refuse_before_any_write_When_the_solid_pairs_are_above_the_limit(self):
        # Arrange
        self.add_box("A")
        self.add_shape(
            "Many",
            Part.Compound(
                [Part.makeBox(1, 1, 1, App.Vector(20 + 2 * index, 0, 0)) for index in range(3)]
            ),
        )
        self.add_shape("Other", Part.Compound([Part.makeBox(1, 1, 1, App.Vector(5, 5, 5))]))
        base = Part.Compound(
            [Part.makeBox(1, 1, 1, App.Vector(100 + 2 * i, 0, 0)) for i in range(2)]
        )
        self.add_shape("Pair", base)
        limit = features._PART_BOOLEAN_MAX_SOLID_PAIRS
        features._PART_BOOLEAN_MAX_SOLID_PAIRS = 5  # 2 base solids x 4 tool solids = 8
        try:
            # Act and Assert
            message = self.assert_refusal(
                lambda: self.boolean(base="Pair", tools=["Many", "Other"]),
                "part_boolean.too_complex",
            )
        finally:
            features._PART_BOOLEAN_MAX_SOLID_PAIRS = limit
        self.assertIn("11 solid pairs", message)

    def test_Should_run_When_the_solid_pairs_are_exactly_at_the_limit(self):
        # Arrange
        self.add_box("A")
        self.add_box("B", x=5.0)
        limit = features._PART_BOOLEAN_MAX_SOLID_PAIRS
        features._PART_BOOLEAN_MAX_SOLID_PAIRS = 1
        try:
            # Act
            envelope = self.boolean()
        finally:
            features._PART_BOOLEAN_MAX_SOLID_PAIRS = limit

        # Assert
        self.assert_ok(envelope)

    def test_Should_never_call_partdesign_When_a_boolean_runs(self):
        # Arrange
        self.two_cubes()
        original = features._require_partdesign
        calls = []
        features._require_partdesign = lambda: calls.append(1)
        try:
            # Act
            envelope = self.boolean()
        finally:
            features._require_partdesign = original

        # Assert
        self.assert_ok(envelope)
        self.assertEqual(calls, [])

    def test_Should_demand_a_confirm_When_the_operator_posture_is_off(self):
        # Arrange
        self.two_cubes()
        confirm.set_auto_approve(False)
        before = self.fingerprint()

        # Act
        with self.assertRaises(ValidationError) as caught:
            self.boolean()

        # Assert
        self.assertIn("requires a confirm", str(caught.exception))
        self.assertEqual(self.fingerprint(), before)

    def test_Should_report_the_geometry_and_leave_the_document_alone_When_dry_run_is_asked(self):
        # Arrange
        self.two_cubes()
        before = self.fingerprint()
        operation = {
            "tool": "feature_part_boolean",
            "args": {"operation": "cut", "base": "A", "tools": ["B"], "name": "Result"},
        }

        # Act
        envelope = self.preview(operation)

        # Assert
        self.assertEqual(envelope["status"], "OK", envelope.get("detail"))
        self.assertIsNone(self.document().getObject("Result"))
        self.assertEqual(self.fingerprint(), before)
        self.assertEqual(self.visibility("A", "B"), [True, True])


class PartBooleanCostTest(_PartFixture):
    def test_Should_finish_inside_the_budget_When_the_inputs_sit_just_under_both_limits(self):
        # Arrange
        # A 200 x 200 x 10 plate cut by one compound of 990 cylinders: 2,976 faces (limit 3,000)
        # and 990 solid pairs (limit 1,000). Measured at 8.9 s for 3,006 faces in the spec probe.
        radius, pitch, columns, rows = 1.5, 6.0, 33, 30
        cylinders = [
            Part.makeCylinder(
                radius, 14.0, App.Vector(3.0 + pitch * column, 3.0 + pitch * row, -2.0)
            )
            for column in range(columns)
            for row in range(rows)
        ]
        self.add_shape("Plate", Part.makeBox(200.0, 200.0, 10.0))
        self.add_shape("Holes", Part.Compound(cylinders))
        expected = 200.0 * 200.0 * 10.0 - columns * rows * math.pi * radius**2 * 10.0
        started = time.monotonic()

        # Act
        envelope = self.boolean(base="Plate", tools=["Holes"], operation="cut")
        elapsed = time.monotonic() - started

        # Assert
        self.assertEqual(self.document().getObject("Holes").Shape.Faces.__len__(), 2970)
        self.assert_volume(envelope, expected, places=3)
        self.assertLess(elapsed, 60.0)

    def test_Should_finish_inside_the_budget_When_two_crossing_families_sit_at_900_pairs(self):
        # Arrange
        # Two families of 30 cylinders that cross each other: 180 faces, 900 solid pairs, both
        # under the limits. Measured at 13.4 s for a common in the spec probe.
        self.add_shape("FamilyX", self.crossing_family("x", 30, 3.0))
        self.add_shape("FamilyY", self.crossing_family("y", 30, 3.0))
        started = time.monotonic()

        # Act
        envelope = self.boolean(base="FamilyX", tools=["FamilyY"], operation="common")
        elapsed = time.monotonic() - started

        # Assert
        self.assert_ok(envelope)
        self.assertLess(elapsed, 60.0)

    def test_Should_finish_inside_the_budget_When_a_several_tool_cut_sits_at_960_pairs(self):
        # Arrange
        # A plate and two crossing families of 30 cylinders: 30 + 30 + 900 = 960 pairs, just
        # under the limit of 1,000.
        self.add_shape("Plate", Part.makeBox(120.0, 120.0, 10.0))
        self.add_shape("FamilyX", self.crossing_family("x", 30, 3.0))
        self.add_shape("FamilyY", self.crossing_family("y", 30, 3.0))
        started = time.monotonic()

        # Act
        envelope = self.boolean(base="Plate", tools=["FamilyX", "FamilyY"])
        elapsed = time.monotonic() - started

        # Assert
        self.assert_ok(envelope)
        self.assertLess(elapsed, 60.0)

    def test_Should_finish_inside_the_budget_When_one_compound_holds_900_crossing_pairs(self):
        # Arrange
        # One tool compound of two crossing families of 30 cylinders: 900 solid pairs inside the
        # input, 60 pairs across the inputs, 960 in all, just under the limit of 1,000.
        self.add_shape("Plate", Part.makeBox(120.0, 120.0, 10.0))
        both = [
            *self.crossing_family("x", 30, 3.0).Solids,
            *self.crossing_family("y", 30, 3.0).Solids,
        ]
        self.add_shape("Crossing", Part.Compound(both))
        started = time.monotonic()

        # Act
        envelope = self.boolean(base="Plate", tools=["Crossing"])
        elapsed = time.monotonic() - started

        # Assert
        self.assert_ok(envelope)
        self.assertLess(elapsed, 60.0)


class ShapeTrustTest(_PartFixture):
    def test_Should_trust_only_valid_all_solid_positive_volume_shapes_When_checked(self):
        # Arrange
        box = Part.makeBox(10, 10, 10)
        corners = [(0, 0), (10, 10), (10, 0), (0, 10), (0, 0)]
        bowtie = Part.Face(Part.makePolygon([App.Vector(x, y, 0) for x, y in corners])).extrude(
            App.Vector(0, 0, 10)
        )
        cases = {
            "box": (box, True),
            "compound of two boxes": (
                Part.Compound([box, box.translated(App.Vector(20, 0, 0))]),
                True,
            ),
            "reversed box": (box.reversed(), False),
            "bowtie solid": (bowtie, False),
            "shell": (Part.Shell(box.Faces), False),
            "face": (box.Faces[0], False),
            "empty compound": (Part.Compound([]), False),
        }
        for label, (shape, expected) in cases.items():
            with self.subTest(shape=label):
                # Act
                trusted = shape_trust.is_measurable_solid(shape)

                # Assert
                self.assertEqual(trusted, expected)

    def test_Should_yield_none_for_non_solid_content_When_volumes_are_listed(self):
        # Arrange
        box = Part.makeBox(10, 10, 10)
        mixed = Part.Compound([box, box.Faces[0]])

        # Act
        volumes = list(shape_trust.solid_volumes(mixed))

        # Assert
        self.assertEqual(len(volumes), 2)
        self.assertAlmostEqual(volumes[0], 1000.0)
        self.assertIsNone(volumes[1])
