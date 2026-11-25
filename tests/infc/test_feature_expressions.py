"""In-FreeCAD tests for ``feature_set_expression`` (stdlib unittest).

Run via ``FreeCADCmd tests/run_tests.py``. Expected values are the ones the caller wrote, read
back from the live document, never read from the tool under test.
"""

import unittest
from unittest import mock

import FreeCAD as App
import Part
import Sketcher

from freecad_buddy.adapters.rpc_dispatch import MethodRegistry, RpcMethod
from freecad_buddy.hosts.tool_catalog import preview_op_table
from freecad_buddy.usecases import features, preview, shim, sketches, transaction
from freecad_buddy.usecases import fingerprint as fingerprint_module
from infc.test_feature_tools import _FeatureFixture, _snapshot_leftovers

WIDTH = 12.0


def bind(obj, path, expression):
    return {"object": obj, "path": path, "expression": expression}


class _ExpressionFixture(_FeatureFixture):
    """A VarSet ``Params`` (width 12 mm, tilt 30 deg), two boxes and a constrained sketch."""

    def setUp(self):
        super().setUp()
        document = self.document()
        varset = document.addObject("App::VarSet", "Params")
        varset.addProperty("App::PropertyLength", "width", "Parameters", "")
        varset.width = WIDTH
        varset.addProperty("App::PropertyAngle", "tilt", "Parameters", "")
        varset.tilt = 30.0
        varset.addProperty("App::PropertyInteger", "count", "Parameters", "")
        varset.count = 4
        varset.addProperty("App::PropertyFloat", "ratio", "Parameters", "")
        varset.ratio = 0.5
        self.box = document.addObject("Part::Box", "Box")
        self.other = document.addObject("Part::Box", "Other")
        self.sketch = document.addObject("Sketcher::SketchObject", "Sketch")
        self.sketch.addGeometry(Part.LineSegment(App.Vector(0, 0, 0), App.Vector(10, 0, 0)))
        self.sketch.addConstraint(Sketcher.Constraint("Coincident", 0, 1, -1, 1))
        self.sketch.addConstraint(Sketcher.Constraint("Horizontal", 0))
        index = self.sketch.addConstraint(Sketcher.Constraint("DistanceX", 0, 1, 0, 2, 10.0))
        self.sketch.renameConstraint(index, "span")
        self.support = document.addObject("Part::Box", "Support")
        document.recompute()
        self.sketch.MapMode = "FlatFace"
        self.sketch.AttachmentSupport = [(self.support, ["Face6"])]
        self.loose = document.addObject("Sketcher::SketchObject", "Loose")
        document.recompute()

    def set_expressions(self, *items, **extra):
        return features.feature_set_expression(
            self.registry, doc=self.handle, expressions=list(items), **extra
        )

    def dispatch(self, *items):
        """Call the tool through the dispatcher, as a client does, and return its envelope."""
        methods = MethodRegistry()
        methods.register(
            RpcMethod(
                name="feature_set_expression",
                handler=lambda **p: features.feature_set_expression(self.registry, **p),
                mutating=True,
            )
        )
        return methods.dispatch(
            "feature_set_expression", {"doc": self.handle, "expressions": list(items)}
        )

    def bindings(self):
        return {
            obj.Name: sorted(obj.ExpressionEngine)
            for obj in self.document().Objects
            if obj.ExpressionEngine
        }

    def live(self, name):
        return self.document().getObject(name)

    def snapshots_minted_by(self, call):
        """Return ``(result, number of snapshot paths the mutation bracket asked for)``."""
        real = transaction.temp_snapshot_path
        minted = []

        def counting(doc):
            minted.append(doc)
            return real(doc)

        transaction.temp_snapshot_path = counting
        try:
            result = call()
        finally:
            transaction.temp_snapshot_path = real
        return result, len(minted)


class BindTest(_ExpressionFixture):
    def test_Should_bind_a_feature_length_and_report_the_value_When_an_expression_is_given(
        self,
    ):
        # Arrange
        item = bind("Box", "Length", "Params.width * 2")

        # Act
        envelope = self.set_expressions(item)

        # Assert
        content = envelope["structured_content"]
        self.assertEqual(envelope["status"], "OK", envelope.get("detail"))
        self.assertEqual(
            content["bound"],
            [{"object": "Box", "path": "Length", "value": {"value": 2 * WIDTH, "unit": "mm"}}],
        )
        self.assertEqual((content["cleared"], content["unchanged"]), ([], []))
        self.assertEqual(content["undo_steps"], 1)
        self.assertEqual(self.live("Box").Length.getValueAs("mm"), 2 * WIDTH)
        self.assertEqual(self.bindings()["Box"], [("Length", "Params.width * 2")])

    def test_Should_drive_the_constraint_When_a_sketch_constraint_is_bound_by_name(self):
        # Arrange
        item = bind("Sketch", ".Constraints.span", "Params.width")

        # Act
        envelope = self.set_expressions(item)
        self.document().recompute()

        # Assert
        self.assertEqual(envelope["status"], "OK", envelope.get("detail"))
        self.assertEqual(self.live("Sketch").getDatum("span").getValueAs("mm"), WIDTH)
        row = envelope["structured_content"]["bound"][0]
        self.assertEqual(row["value"], {"value": WIDTH, "unit": "mm"})

    def test_Should_move_the_attachment_offset_When_a_numeric_leaf_of_a_placement_is_bound(self):
        # Arrange
        item = bind("Sketch", ".AttachmentOffset.Base.z", "Params.width")

        # Act
        envelope = self.set_expressions(item)

        # Assert
        self.assertEqual(envelope["status"], "OK", envelope.get("detail"))
        self.assertEqual(self.live("Sketch").AttachmentOffset.Base.z, WIDTH)

    def test_Should_bind_a_placement_leaf_and_an_angle_When_the_path_has_no_leading_dot(self):
        # Arrange
        items = [
            bind("Box", "Placement.Base.y", "Params.width"),
            bind("Box", "Placement.Rotation.Angle", "Params.tilt"),
        ]

        # Act
        envelope = self.set_expressions(*items)

        # Assert
        self.assertEqual(envelope["status"], "OK", envelope.get("detail"))
        self.assertEqual(self.live("Box").Placement.Base.y, WIDTH)
        angle = envelope["structured_content"]["bound"][1]["value"]
        self.assertEqual(angle["unit"], "deg")

    def test_Should_replace_the_text_When_a_bound_path_is_rebound(self):
        # Arrange
        self.set_expressions(bind("Box", "Length", "Params.width"))

        # Act
        envelope = self.set_expressions(bind("Box", "Length", "Params.width + 3 mm"))

        # Assert
        self.assertEqual(envelope["status"], "OK", envelope.get("detail"))
        self.assertEqual(len(envelope["structured_content"]["bound"]), 1)
        self.assertEqual(self.live("Box").Length.getValueAs("mm"), WIDTH + 3.0)
        self.assertEqual(self.bindings()["Box"], [("Length", "Params.width + 3 mm")])

    def test_Should_clear_the_binding_and_keep_the_value_When_the_expression_is_null(self):
        # Arrange
        self.set_expressions(bind("Box", "Length", "Params.width"))

        # Act
        envelope = self.set_expressions(bind("Box", "Length", None))

        # Assert
        content = envelope["structured_content"]
        self.assertEqual(envelope["status"], "OK", envelope.get("detail"))
        self.assertEqual(content["cleared"][0]["value"], {"value": WIDTH, "unit": "mm"})
        self.assertEqual(content["bound"], [])
        self.assertNotIn("Box", self.bindings())
        self.assertEqual(self.live("Box").Length.getValueAs("mm"), WIDTH)
        self.assertEqual(envelope["structured_content"]["mutation"]["post_verify"]["passed"], True)

    def test_Should_bind_every_item_in_one_undo_step_When_several_are_given(self):
        # Arrange
        items = [
            bind("Box", "Length", "Params.width"),
            bind("Other", "Height", "Params.width * 3"),
            bind("Sketch", ".Constraints.span", "Params.width"),
        ]

        # Act
        envelope = self.set_expressions(*items)

        # Assert
        self.assertEqual(envelope["structured_content"]["undo_steps"], 1)
        self.assertEqual(sorted(self.bindings()), ["Box", "Other", "Sketch"])
        self.registry.document_undo(doc=self.handle)
        self.assertEqual(self.bindings(), {})

    def test_Should_not_flag_the_audit_When_a_binding_is_added_replaced_and_cleared(self):
        # Arrange
        steps = [
            [bind("Box", "Length", "Params.width")],
            [bind("Box", "Length", "Params.width * 2")],
            [bind("Box", "Length", None)],
        ]

        # Act
        envelopes = [self.set_expressions(*step) for step in steps]

        # Assert
        for envelope in envelopes:
            audit = envelope["structured_content"]["mutation"]["post_verify"]["tnp_audit"]
            self.assertEqual(envelope["status"], "OK", envelope.get("detail"))
            self.assertEqual(audit["status"], "CLEAN", audit["findings"])


class UndoTest(_ExpressionFixture):
    def test_Should_restore_the_binding_and_the_value_When_a_bind_is_undone(self):
        # Arrange
        original = self.live("Box").Length.getValueAs("mm")
        self.set_expressions(bind("Box", "Length", "Params.width * 2"))

        # Act
        undone = self.registry.document_undo(doc=self.handle)

        # Assert
        self.assertEqual(undone["status"], "OK", undone.get("detail"))
        self.assertEqual(self.bindings(), {})
        self.assertEqual(self.live("Box").Length.getValueAs("mm"), original)

    def test_Should_restore_the_binding_When_a_clear_is_undone(self):
        # Arrange
        self.set_expressions(bind("Box", "Length", "Params.width"))
        self.set_expressions(bind("Box", "Length", None))

        # Act
        self.registry.document_undo(doc=self.handle)

        # Assert
        self.assertEqual(self.bindings()["Box"], [("Length", "Params.width")])


class NoChangeTest(_ExpressionFixture):
    def test_Should_open_no_transaction_and_report_zero_undo_steps_When_the_stored_text_is_given(
        self,
    ):
        # Arrange
        self.set_expressions(bind("Box", "Length", "Params.width"))
        undo_before = self.document().UndoCount

        # Act
        envelope, minted = self.snapshots_minted_by(
            lambda: self.set_expressions(bind("Box", "Length", "Params.width"))
        )

        # Assert
        content = envelope["structured_content"]
        self.assertEqual(envelope["status"], "OK")
        self.assertEqual(content["unchanged"][0]["value"], {"value": WIDTH, "unit": "mm"})
        self.assertEqual((content["bound"], content["cleared"]), ([], []))
        self.assertEqual(content["undo_steps"], 0)
        self.assertNotIn("mutation", content)
        self.assertEqual(minted, 0)
        self.assertEqual(self.document().UndoCount, undo_before)

    def test_Should_open_no_transaction_When_an_unbound_path_is_cleared(self):
        # Arrange
        self.set_expressions(bind("Other", "Height", "Params.width"))

        # Act
        envelope, minted = self.snapshots_minted_by(
            lambda: self.set_expressions(bind("Box", "Length", None))
        )

        # Assert
        self.assertEqual(envelope["structured_content"]["undo_steps"], 0)
        self.assertEqual(envelope["structured_content"]["unchanged"][0]["object"], "Box")
        self.assertEqual(minted, 0)

    def test_Should_revert_the_earlier_step_When_undo_follows_a_call_that_changed_nothing(self):
        # Arrange
        self.set_expressions(bind("Box", "Length", "Params.width"))
        noop = self.set_expressions(bind("Box", "Length", "Params.width"))

        # Act
        self.registry.document_undo(doc=self.handle)

        # Assert
        self.assertEqual(noop["structured_content"]["undo_steps"], 0)
        self.assertEqual(self.bindings(), {})

    def test_Should_report_the_measured_step_count_When_only_some_items_change(self):
        # Arrange
        self.set_expressions(bind("Box", "Length", "Params.width"))
        items = [bind("Box", "Length", "Params.width"), bind("Other", "Height", "Params.width")]

        # Act
        envelope = self.set_expressions(*items)

        # Assert
        content = envelope["structured_content"]
        self.assertEqual([row["object"] for row in content["unchanged"]], ["Box"])
        self.assertEqual([row["object"] for row in content["bound"]], ["Other"])
        self.assertEqual(content["undo_steps"], 1)

    def test_Should_list_the_item_unchanged_and_keep_the_earlier_step_When_the_text_is_equivalent(
        self,
    ):
        # Arrange
        self.set_expressions(bind("Box", "Length", "Params.width * 2"))
        self.set_expressions(bind("Other", "Height", "Params.width"))

        # Act
        envelope = self.set_expressions(bind("Box", "Length", "Params.width*2"))

        # Assert
        content = envelope["structured_content"]
        self.assertEqual(envelope["status"], "OK", envelope.get("detail"))
        self.assertEqual([row["object"] for row in content["unchanged"]], ["Box"])
        self.assertEqual(content["bound"], [])
        self.assertEqual(content["undo_steps"], 0)
        self.registry.document_undo(doc=self.handle)
        self.assertEqual(sorted(self.bindings()), ["Box"])

    def test_Should_report_one_step_When_the_undo_stack_is_already_full(self):
        # Arrange
        for turn in range(24):
            self.set_expressions(bind("Box", "Length", f"Params.width + {turn + 1} mm"))

        # Act
        envelope = self.set_expressions(bind("Box", "Length", "Params.width + 99 mm"))

        # Assert
        self.assertEqual(envelope["structured_content"]["undo_steps"], 1)
        self.registry.document_undo(doc=self.handle)
        self.assertEqual(self.live("Box").Length.getValueAs("mm"), WIDTH + 24)


class RollbackTest(_ExpressionFixture):
    def test_Should_roll_back_every_item_and_prove_it_When_a_later_item_closes_a_cycle(self):
        # Arrange
        items = [
            bind("Other", "Height", "Params.width"),
            bind("Box", "Width", "Other.Width"),
            bind("Other", "Width", "Box.Width"),
        ]
        before = self.bindings()
        fingerprint_before = fingerprint_module.fingerprint(self.document())["digest"]

        # Act
        envelope = self.set_expressions(*items)

        # Assert
        block = envelope["structured_content"]["mutation"]
        self.assertEqual(envelope["status"], "RECOMPUTE_ERROR")
        self.assertEqual(envelope["detail"]["code"], "expression.cycle")
        self.assertTrue(block["rolled_back"])
        self.assertEqual(block["rollback_proven"], "rolled_back_verified")
        self.assertEqual(self.bindings(), before)
        self.assertEqual(block["fingerprint_after"]["digest"], fingerprint_before)
        self.assertIn("cyclic", block["post_verify"]["explanation"])
        self.assertNotIn("bound", envelope["structured_content"])
        self.assertEqual(_snapshot_leftovers(), [])

    def test_Should_roll_back_a_self_reference_When_an_item_binds_a_property_to_itself(self):
        # Arrange
        item = bind("Box", "Height", "Box.Height + 1 mm")

        # Act
        envelope = self.set_expressions(item)

        # Assert
        block = envelope["structured_content"]["mutation"]
        self.assertNotEqual(envelope["status"], "OK")
        self.assertTrue(block["rolled_back"])
        self.assertEqual(block["rollback_proven"], "rolled_back_verified")
        self.assertEqual(self.bindings(), {})
        self.assertEqual(_snapshot_leftovers(), [])

    def test_Should_roll_back_and_prove_it_When_the_recompute_fails_after_the_bind(self):
        # Arrange
        self.set_expressions(bind("Other", "Height", "Params.width"))
        before = self.bindings()
        item = bind("Box", "Length", "Params.width - 12 mm")

        # Act
        envelope = self.set_expressions(item)

        # Assert
        block = envelope["structured_content"]["mutation"]
        self.assertNotEqual(envelope["status"], "OK")
        self.assertTrue(block["rolled_back"])
        self.assertEqual(block["rollback_proven"], "rolled_back_verified")
        self.assertEqual(self.bindings(), before)
        self.assertEqual(self.live("Box").Length.getValueAs("mm"), 10.0)
        self.assertEqual(self.live("Box").State, ["Up-to-date"])

    def test_Should_restore_from_the_snapshot_When_the_abort_leaves_the_binding_in_place(self):
        # Arrange
        # With undo off the abort restores nothing, and the shape fingerprint still compares
        # equal because a binding that changes no value leaves every shape alone; only the
        # binding read-back sees the leftover.
        self.set_expressions(bind("Other", "Height", "Params.width"))
        self.document().UndoMode = 0
        before = self.bindings()
        items = [bind("Other", "Height", None), bind("Box", "Height", "Box.Height + 1 mm")]

        # Act
        with mock.patch.object(shim, "enable_undo", return_value=False):
            envelope = self.set_expressions(*items)

        # Assert
        block = envelope["structured_content"]["mutation"]
        self.assertTrue(block["rolled_back"])
        self.assertEqual(block["rollback_proven"], "rolled_back_via_snapshot")
        self.assertEqual(self.bindings(), before)

    def test_Should_see_an_expression_only_change_When_the_shape_fingerprint_does_not(self):
        # Arrange
        self.set_expressions(bind("Box", "Length", "Params.width"))
        self.document().recompute()
        state_before = features._expression_state(self.document())
        fingerprint_before = fingerprint_module.fingerprint(self.document())["digest"]

        # Act
        self.live("Box").setExpression("Length", None)
        self.document().recompute()

        # Assert
        fingerprint_after = fingerprint_module.fingerprint(self.document())["digest"]
        self.assertEqual(fingerprint_after, fingerprint_before)
        self.assertNotEqual(features._expression_state(self.document()), state_before)


class RefusalTest(_ExpressionFixture):
    def assert_refused(self, item, code):
        before = self.bindings()
        envelope, minted = self.snapshots_minted_by(lambda: self.dispatch(item))
        self.assertEqual(envelope["status"], "INVALID_INPUT", envelope.get("detail"))
        self.assertEqual(envelope["detail"]["code"], code, envelope["detail"])
        self.assertEqual(minted, 0)
        self.assertEqual(self.bindings(), before)
        return envelope

    def test_Should_refuse_with_the_invalid_expression_code_When_a_reference_is_unknown(self):
        envelope = self.assert_refused(
            bind("Box", "Height", "Nope.x"), "expression.invalid_expression"
        )
        self.assertIn("Nope", envelope["detail"]["message"])

    def test_Should_refuse_with_the_invalid_expression_code_When_the_text_does_not_parse(self):
        self.assert_refused(
            bind("Box", "Height", "Params.width +"), "expression.invalid_expression"
        )

    def test_Should_refuse_with_the_invalid_expression_code_When_the_text_is_not_a_number(self):
        self.assert_refused(bind("Box", "Height", "Params.Label"), "expression.invalid_expression")

    def test_Should_refuse_with_the_unit_mismatch_code_When_an_angle_is_bound_to_a_length(self):
        self.assert_refused(bind("Box", "Length", "5 deg"), "expression.unit_mismatch")

    def test_Should_refuse_with_the_unit_mismatch_code_When_a_length_is_bound_to_an_angle(self):
        self.assert_refused(
            bind("Box", "Placement.Rotation.Angle", "Params.width"), "expression.unit_mismatch"
        )

    def test_Should_accept_a_plain_number_When_it_takes_the_property_unit(self):
        # Arrange
        item = bind("Box", "Length", "3")

        # Act
        envelope = self.set_expressions(item)

        # Assert
        self.assertEqual(envelope["status"], "OK", envelope.get("detail"))
        self.assertEqual(self.live("Box").Length.getValueAs("mm"), 3.0)

    def test_Should_accept_a_dimensionless_quantity_When_it_takes_the_property_unit(self):
        # Arrange
        item = bind("Box", "Length", "Params.width / 1 mm")

        # Act
        envelope = self.set_expressions(item)

        # Assert
        self.assertEqual(envelope["status"], "OK", envelope.get("detail"))
        self.assertEqual(self.live("Box").Length.getValueAs("mm"), WIDTH)

    def test_Should_refuse_with_the_not_finite_code_When_the_expression_divides_by_zero(self):
        self.assert_refused(bind("Box", "Height", "1 mm / 0"), "expression.not_finite")

    def test_Should_refuse_with_the_invalid_path_code_When_the_path_resolves_to_nothing(self):
        for path in ("Length.x", "Nonexistent", "Placement.Base.q", ".Constraints.nope"):
            with self.subTest(path=path):
                target = "Sketch" if "Constraints" in path else "Box"
                self.assert_refused(bind(target, path, "1 mm"), "expression.invalid_path")

    def test_Should_refuse_with_the_invalid_path_code_When_the_path_is_not_a_property_path(self):
        for path in ("", "Length ", "Length..x", "1Length", "Length.", "Length[x]", "a b"):
            with self.subTest(path=path):
                self.assert_refused(bind("Box", path, "1 mm"), "expression.invalid_path")

    def test_Should_refuse_with_the_unsupported_code_When_the_property_holds_no_number(self):
        for target, path in (
            ("Box", "Placement"),
            ("Box", "Shape"),
            ("Box", "Label"),
            ("Sketch", ".AttachmentOffset"),
            ("Sketch", ".Constraints"),
            ("Box", "ExpressionEngine"),
        ):
            with self.subTest(path=path):
                self.assert_refused(bind(target, path, "1 mm"), "expression.unsupported_property")

    def test_Should_refuse_with_the_invalid_text_code_When_the_text_cannot_be_stored(self):
        too_long = "+".join(["1"] * 200) + "+1"
        for text in ("", "   ", "1 mm\x00", "1 mm\x07", too_long):
            with self.subTest(length=len(text)):
                self.assert_refused(bind("Box", "Height", text), "expression.invalid_text")

    def test_Should_refuse_before_FreeCAD_parses_When_a_long_chained_expression_is_given(self):
        # Arrange
        # FreeCAD 1.1.4 ends its process on the first and the third of these.
        for operator, terms in (("*", 700), ("&&", 600), ("+", 1000)):
            with self.subTest(operator=operator):
                text = operator.join(["1"] * terms)

                # Act, Assert
                self.assert_refused(bind("Box", "Height", text), "expression.invalid_text")

    def test_Should_accept_an_expression_at_the_length_limit_When_it_parses(self):
        # Arrange
        text = "*".join(["1"] * 199) + " mm"
        self.assertLessEqual(len(text), features._MAX_EXPRESSION_LENGTH)

        # Act
        envelope = self.set_expressions(bind("Box", "Height", text))

        # Assert
        self.assertEqual(envelope["status"], "OK", envelope.get("detail"))
        self.assertEqual(self.live("Box").Height.getValueAs("mm"), 1.0)

    def test_Should_refuse_with_the_duplicate_code_When_a_path_appears_twice(self):
        # Arrange
        items = [bind("Box", "Placement.Base.x", "1 mm"), bind("Box", ".Placement.Base.x", "2 mm")]

        # Act
        envelope = self.dispatch(*items)

        # Assert
        self.assertEqual(envelope["detail"]["code"], "expression.duplicate_path")
        self.assertEqual(self.bindings(), {})

    def test_Should_refuse_without_a_code_When_the_object_is_unknown(self):
        # Arrange
        item = bind("Missing", "Length", "1 mm")

        # Act
        envelope = self.dispatch(item)

        # Assert
        self.assertEqual(envelope["status"], "INVALID_INPUT")
        self.assertEqual(envelope["detail"]["code"], "INVALID_INPUT")
        self.assertIn("Missing", envelope["detail"]["message"])

    def test_Should_refuse_When_the_list_or_an_item_is_malformed(self):
        for items in ([], [{"object": "Box", "path": "Length"}], [1], [bind("Box", "Length", 5)]):
            with self.subTest(items=items):
                envelope = self.dispatch(*items)
                self.assertEqual(envelope["status"], "INVALID_INPUT")
        too_many = [bind("Box", "Placement.Base.x", "1 mm")] * 101
        self.assertEqual(self.dispatch(*too_many)["status"], "INVALID_INPUT")

    def test_Should_refuse_an_item_after_a_valid_one_and_bind_none_When_the_batch_is_checked(self):
        # Arrange
        items = [bind("Box", "Length", "Params.width"), bind("Box", "Height", "Nope.x")]

        # Act
        envelope = self.dispatch(*items)

        # Assert
        self.assertEqual(envelope["detail"]["code"], "expression.invalid_expression")
        self.assertEqual(self.bindings(), {})


class IntegrityTest(_ExpressionFixture):
    def assert_refused(self, item, code):
        before = self.bindings()
        envelope = self.dispatch(item)
        self.assertEqual(envelope["detail"]["code"], code, envelope["detail"])
        self.assertEqual(self.bindings(), before)

    def test_Should_refuse_with_the_invalid_path_code_When_the_path_ends_in_value(self):
        self.assert_refused(bind("Box", ".Length.Value", "5 deg"), "expression.invalid_path")

    def test_Should_refuse_with_the_not_integer_code_When_a_fraction_is_bound_to_an_integer(self):
        self.assert_refused(
            bind("Params", "count", "Params.width / 5 mm"), "expression.not_integer"
        )

    def test_Should_bind_an_integer_When_the_expression_evaluates_to_a_whole_number(self):
        # Arrange
        item = bind("Params", "count", "Params.width / 6 mm")

        # Act
        envelope = self.set_expressions(item)

        # Assert
        self.assertEqual(envelope["status"], "OK", envelope.get("detail"))
        self.assertEqual(envelope["structured_content"]["bound"][0]["value"], 2)
        self.assertEqual(self.live("Params").count, 2)

    def test_Should_refuse_with_the_unit_mismatch_code_When_a_length_is_bound_to_a_float(self):
        self.assert_refused(bind("Params", "ratio", "Params.width"), "expression.unit_mismatch")

    def test_Should_refuse_with_the_unsupported_code_When_the_property_is_read_only(self):
        # Arrange
        self.live("Box").setPropertyStatus("Length", "ReadOnly")

        # Act, Assert
        self.assert_refused(
            bind("Box", "Length", "Params.width"), "expression.unsupported_property"
        )

    def test_Should_clear_the_binding_When_it_sits_on_a_path_that_resolves_to_nothing(self):
        # Arrange
        self.live("Box").setExpression("Length.x", "1")
        self.assertEqual(self.bindings()["Box"], [(".Length.x", "1")])

        # Act
        envelope = self.set_expressions(bind("Box", "Length.x", None))

        # Assert
        self.assertEqual(envelope["status"], "OK", envelope.get("detail"))
        self.assertEqual(len(envelope["structured_content"]["cleared"]), 1)
        self.assertEqual(self.bindings(), {})

    def test_Should_clear_the_binding_When_the_path_names_the_constraint_by_index(self):
        # Arrange
        self.set_expressions(bind("Sketch", ".Constraints.span", "Params.width"))

        # Act
        envelope = self.set_expressions(bind("Sketch", ".Constraints[2]", None))

        # Assert
        content = envelope["structured_content"]
        self.assertEqual(envelope["status"], "OK", envelope.get("detail"))
        self.assertEqual(len(content["cleared"]), 1, content)
        self.assertEqual(self.bindings(), {})

    def test_Should_roll_back_When_two_items_address_one_stored_binding(self):
        # Arrange
        items = [
            bind("Sketch", ".Constraints.span", "Params.width"),
            bind("Sketch", ".Constraints[2]", "Params.width * 2"),
        ]

        # Act
        envelope = self.set_expressions(*items)

        # Assert
        block = envelope["structured_content"]["mutation"]
        self.assertNotEqual(envelope["status"], "OK")
        self.assertTrue(block["rolled_back"])
        self.assertIn("same binding", block["post_verify"]["explanation"])
        self.assertEqual(self.bindings(), {})

    def test_Should_refuse_with_the_unit_mismatch_code_When_a_length_is_bound_to_a_plain_constraint(
        self,
    ):
        self.assert_refused(
            bind("Sketch", ".Constraints[0]", "Params.width"), "expression.unit_mismatch"
        )

    def test_Should_roll_back_with_the_not_finite_code_When_a_sibling_item_makes_a_value_infinite(
        self,
    ):
        # Arrange
        # The second expression is finite against the document as it is before the call, so only
        # the recomputed state shows the infinite height.
        items = [
            bind("Other", "Height", "5 mm"),
            bind("Box", "Height", "1 mm / (Other.Height - 5 mm)"),
        ]

        # Act
        envelope = self.set_expressions(*items)

        # Assert
        self.assertEqual(envelope["status"], "RECOMPUTE_ERROR")
        self.assertEqual(envelope["detail"]["code"], "expression.not_finite")
        self.assertTrue(envelope["structured_content"]["mutation"]["rolled_back"])
        self.assertEqual(self.bindings(), {})
        self.assertEqual(self.live("Box").Height.getValueAs("mm"), 10.0)

    def test_Should_roll_back_with_the_range_code_When_a_new_binding_drives_another_out_of_range(
        self,
    ):
        # Arrange
        self.set_expressions(bind("Params", "count", "Params.ratio * 8"))

        # Act
        envelope = self.set_expressions(bind("Params", "ratio", "0.3"))

        # Assert
        self.assertEqual(envelope["status"], "RECOMPUTE_ERROR")
        self.assertEqual(envelope["detail"]["code"], "expression.value_out_of_range")
        self.assertEqual(self.live("Params").ratio, 0.5)
        self.assertEqual(self.live("Params").count, 4)

    def test_Should_show_the_geometry_change_in_the_mutation_diff_When_a_bound_length_moves(self):
        # Arrange
        item = bind("Box", "Length", "Params.width * 2")

        # Act
        envelope = self.set_expressions(item)

        # Assert
        block = envelope["structured_content"]["mutation"]
        self.assertIn("Box", block["touched"])
        self.assertNotEqual(
            block["fingerprint_before"]["digest"], block["fingerprint_after"]["digest"]
        )


class ClosureTest(_ExpressionFixture):
    """The application's active transaction is closed after every exit path of the tool."""

    def test_Should_leave_no_transaction_open_and_keep_undo_working_When_a_cycle_is_refused(self):
        # Arrange
        self.set_expressions(bind("Box", "Length", "Params.width"))

        # Act
        cycle = self.set_expressions(bind("Box", "Length", "Box.Length + 1 mm"))
        self.set_expressions(bind("Other", "Height", "Params.width"))
        undone = self.registry.document_undo(doc=self.handle)

        # Assert
        self.assertEqual(cycle["status"], "RECOMPUTE_ERROR")
        self.assertIsNone(App.getActiveTransaction())
        self.assertEqual(undone["status"], "OK", undone.get("detail"))
        self.assertEqual(sorted(self.bindings()), ["Box"])

    def test_Should_leave_no_transaction_open_When_every_item_is_equivalent_text(self):
        # Arrange
        self.set_expressions(bind("Box", "Length", "Params.width * 2"))

        # Act
        envelope = self.set_expressions(bind("Box", "Length", "Params.width*2"))

        # Assert
        self.assertEqual(envelope["status"], "OK", envelope.get("detail"))
        self.assertIsNone(App.getActiveTransaction())

    def test_Should_leave_no_transaction_open_When_the_recompute_fails(self):
        # Arrange
        item = bind("Box", "Length", "Params.width - 12 mm")

        # Act
        envelope = self.set_expressions(item)

        # Assert
        self.assertNotEqual(envelope["status"], "OK")
        self.assertIsNone(App.getActiveTransaction())

    def test_Should_report_the_recorded_step_When_a_no_change_call_runs_on_touched_objects(self):
        # Arrange
        # A property edit that is not recomputed leaves the object touched; the bracket's
        # recompute then writes inside the transaction and FreeCAD commits it as a step.
        self.set_expressions(bind("Box", "Length", "Params.width * 2"))
        document = self.document()
        document.openTransaction("user edit")
        self.live("Params").tilt = 45.0
        document.commitTransaction()

        # Act
        envelope = self.set_expressions(bind("Box", "Length", "Params.width*2"))

        # Assert
        recorded = list(document.UndoNames)[0].startswith("buddy: set expressions")
        self.assertEqual(envelope["structured_content"]["undo_steps"], 1 if recorded else 0)
        self.assertTrue(recorded, "FreeCAD should have committed a step on the touched document")


class RoundTwoRefusalTest(_ExpressionFixture):
    def assert_refused(self, item, code):
        before = self.bindings()
        envelope, minted = self.snapshots_minted_by(lambda: self.dispatch(item))
        self.assertEqual(envelope["status"], "INVALID_INPUT", envelope.get("detail"))
        self.assertEqual(envelope["detail"]["code"], code, envelope["detail"])
        self.assertEqual(minted, 0)
        self.assertEqual(self.bindings(), before)

    def sheet(self):
        sheet = self.document().addObject("Spreadsheet::Sheet", "Sheet")
        sheet.set("A1", "1")
        sheet.set("B1", "2")
        self.document().recompute()
        return sheet

    def test_Should_refuse_with_the_unsupported_code_When_the_target_is_a_spreadsheet_cell(self):
        # Arrange
        self.sheet()

        # Act, Assert
        self.assert_refused(bind("Sheet", "A1", "7"), "expression.unsupported_property")

    def test_Should_clear_the_binding_When_a_spreadsheet_cell_already_holds_one(self):
        # Arrange
        sheet = self.sheet()
        sheet.setExpression("A1", "7")

        # Act
        envelope = self.set_expressions(bind("Sheet", "A1", None))

        # Assert
        self.assertEqual(envelope["status"], "OK", envelope.get("detail"))
        self.assertEqual(self.bindings(), {})

    def test_Should_refuse_with_the_range_code_When_the_text_holds_a_cell_range(self):
        for text in (
            "sum(A1:B2)",
            "sum(Sheet.A1:Sheet.B2)",
            "sum($A$1:$B$2)",
            "sum( C1 : ZZ16384 ) + 1",
            "sum(<<My Sheet>>.A1:<<My Sheet>>.B2)",
            "sum(Doc#Sheet.A1:Doc#Sheet.B2)",
        ):
            with self.subTest(text=text):
                self.assert_refused(bind("Box", "Height", text), "expression.range_unsupported")

    def test_Should_accept_a_ternary_and_a_single_cell_reference_When_no_range_is_present(self):
        # Arrange
        self.sheet()
        items = [bind("Box", "Height", "Sheet.A1 * 1 mm"), bind("Other", "Height", "1 ? 2 : 3")]

        # Act
        envelope = self.set_expressions(*items)

        # Assert
        self.assertEqual(envelope["status"], "OK", envelope.get("detail"))

    def test_Should_refuse_with_the_unsupported_code_When_the_object_is_not_attached(self):
        # Arrange
        item = bind("Loose", ".AttachmentOffset.Base.z", "Params.width")

        # Act, Assert
        self.assert_refused(item, "expression.unsupported_property")

    def test_Should_refuse_with_the_range_code_When_a_revolution_angle_exceeds_a_full_turn(self):
        # Arrange
        self.document().addObject("Part::Revolution", "Rev")

        # Act, Assert
        self.assert_refused(bind("Rev", "Angle", "400"), "expression.value_out_of_range")

    def test_Should_refuse_with_the_range_code_When_a_pad_length_is_negative(self):
        # Arrange
        self.document().addObject("PartDesign::Pad", "Pad")

        # Act, Assert
        self.assert_refused(bind("Pad", "Length", "-5 mm"), "expression.value_out_of_range")

    def test_Should_bind_a_revolution_angle_When_it_is_within_a_full_turn(self):
        # Arrange
        self.document().addObject("Part::Cylinder", "Cyl")

        # Act
        envelope = self.set_expressions(bind("Cyl", "Angle", "Params.tilt * 2"))

        # Assert
        self.assertEqual(envelope["status"], "OK", envelope.get("detail"))
        self.assertEqual(self.live("Cyl").Angle.getValueAs("deg"), 60.0)

    def test_Should_refuse_with_the_range_code_When_an_integer_leaves_the_int32_range(self):
        for text in ("3000000000", "-3000000000"):
            with self.subTest(text=text):
                # Arrange
                item = bind("Params", "count", text)

                # Act, Assert
                self.assert_refused(item, "expression.value_out_of_range")

    def test_Should_refuse_with_the_range_code_When_a_percent_parameter_exceeds_100(self):
        # Arrange
        self.live("Params").addProperty("App::PropertyPercent", "share", "Parameters", "")
        item = bind("Params", "share", "150")

        # Act, Assert
        self.assert_refused(item, "expression.value_out_of_range")

    def test_Should_refuse_with_the_unsupported_code_When_the_path_reads_into_a_shape(self):
        # Arrange
        item = bind("Box", ".Shape.Volume", "5")

        # Act, Assert
        self.assert_refused(item, "expression.unsupported_property")


class _StubObject:
    """An object holding one binding, recording every expression it is asked to evaluate."""

    def __init__(self, name, bindings):
        self.Name = name
        self.ExpressionEngine = bindings
        self.evaluated = []

    def evalExpression(self, text):
        self.evaluated.append(text)
        return 1.0


class _StubDocument:
    def __init__(self, objects):
        self.Objects = objects


class BindingSweepTest(unittest.TestCase):
    def test_Should_not_evaluate_a_binding_that_holds_a_cell_range_When_sweeping_the_document(self):
        # Arrange
        costly = _StubObject("Sheet", [(".A1", "sum(C1:ZZ16384)")])
        cheap = _StubObject("Box", [("Length", "1")])
        document = _StubDocument([costly, cheap])

        # Act
        features._binding_problems(document)

        # Assert
        self.assertEqual(costly.evaluated, [])
        self.assertIn("1", cheap.evaluated)


class OtherToolTest(_ExpressionFixture):
    def test_Should_still_grade_the_binding_broken_When_another_tool_removes_its_constraint(self):
        # Arrange
        self.set_expressions(bind("Sketch", ".Constraints.span", "Params.width"))

        # Act
        envelope = sketches.sketch_remove_geometry(
            self.registry, doc=self.handle, sketch="Sketch", geo_ids=[0]
        )

        # Assert
        self.assertEqual(envelope["status"], "SPEC_FAILED")
        explanation = envelope["structured_content"]["mutation"]["post_verify"]["explanation"]
        self.assertIn("BROKEN", explanation)
        self.assertTrue(envelope["structured_content"]["mutation"]["rolled_back"])


class DispatchTest(_ExpressionFixture):
    def test_Should_be_reachable_through_the_preview_op_table_When_previewing(self):
        # Arrange
        table = preview_op_table()
        operation = {
            "tool": "feature_set_expression",
            "args": {"expressions": [bind("Box", "Length", "Params.width")]},
        }

        # Act
        envelope = preview.preview_dry_run(
            self.registry, table, None, doc=self.handle, operation=operation, render="off"
        )

        # Assert
        self.assertIn("feature_set_expression", table)
        self.assertEqual(envelope["status"], "OK", envelope.get("detail"))
        self.assertEqual(self.bindings(), {})
