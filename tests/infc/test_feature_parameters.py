"""In-FreeCAD tests for ``feature_parameters_define`` (stdlib unittest).

Run via ``FreeCADCmd tests/run_tests.py``. Expected values are the ones the caller wrote, read
back from the live VarSet, and analytic prism volumes; never read from the tool under test.
"""

import os
import tempfile
from unittest import mock

import FreeCAD as App

from freecad_buddy.adapters.rpc_dispatch import MethodRegistry, RpcMethod
from freecad_buddy.hosts.tool_catalog import preview_op_table
from freecad_buddy.usecases import features, preview, shim, transaction
from freecad_buddy.usecases import fingerprint as fingerprint_module
from infc.test_feature_tools import _FeatureFixture, _snapshot_leftovers, deg, mm

UNIT_SYMBOL_CODE = "parameters.unit_symbol_name"


def length(name, value, **extra):
    return {"name": name, "type": "length", "value": mm(value), **extra}


class _ParametersFixture(_FeatureFixture):
    def define(self, parameters, varset="Params", **extra):
        return features.feature_parameters_define(
            self.registry, doc=self.handle, varset=varset, parameters=parameters, **extra
        )

    def dispatch(self, parameters, varset="Params"):
        """Call the tool through the dispatcher, as a client does, and return its envelope."""
        methods = MethodRegistry()
        methods.register(
            RpcMethod(
                name="feature_parameters_define",
                handler=lambda **p: features.feature_parameters_define(self.registry, **p),
                mutating=True,
            )
        )
        return methods.dispatch(
            "feature_parameters_define",
            {"doc": self.handle, "varset": varset, "parameters": parameters},
        )

    def varset(self, name="Params"):
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


class DefineTest(_ParametersFixture):
    def test_Should_create_the_varset_and_every_typed_property_When_the_varset_is_missing(self):
        # Arrange
        parameters = [
            length("width", 12.5, group="Size", description="overall width"),
            {"name": "tilt", "type": "angle", "value": deg(30.0)},
            {"name": "ratio", "type": "float", "value": 0.25},
            {"name": "count", "type": "integer", "value": 4},
            {"name": "hollow", "type": "bool", "value": True},
            {"name": "note", "type": "string", "value": "rev A"},
        ]

        # Act
        envelope = self.define(parameters)

        # Assert
        self.assertEqual(envelope["status"], "OK", envelope.get("detail"))
        content = envelope["structured_content"]
        self.assertEqual(content["varset"], "Params")
        self.assertEqual(content["added"], [p["name"] for p in parameters])
        self.assertEqual(content["updated"], [])
        varset = self.varset()
        self.assertEqual(varset.TypeId, "App::VarSet")
        self.assertEqual(varset.Label, "Params")
        self.assertEqual(varset.getTypeIdOfProperty("width"), "App::PropertyLength")
        self.assertEqual(varset.width.getValueAs("mm"), 12.5)
        self.assertEqual(varset.getGroupOfProperty("width"), "Size")
        self.assertEqual(varset.getDocumentationOfProperty("width"), "overall width")
        self.assertEqual(varset.getTypeIdOfProperty("tilt"), "App::PropertyAngle")
        self.assertEqual(varset.tilt.getValueAs("deg"), 30.0)
        self.assertEqual(varset.getGroupOfProperty("tilt"), "Parameters")
        self.assertEqual(varset.ratio, 0.25)
        self.assertEqual(varset.count, 4)
        self.assertIs(varset.hollow, True)
        self.assertEqual(varset.note, "rev A")

    def test_Should_update_the_value_and_keep_the_group_When_the_parameter_exists(self):
        # Arrange
        self.define([length("width", 12.0, group="Size")])

        # Act
        envelope = self.define([length("width", 20.0)])

        # Assert
        self.assertEqual(envelope["status"], "OK", envelope.get("detail"))
        content = envelope["structured_content"]
        self.assertEqual((content["added"], content["updated"]), ([], ["width"]))
        self.assertEqual(self.varset().width.getValueAs("mm"), 20.0)
        self.assertEqual(self.varset().getGroupOfProperty("width"), "Size")

    def test_Should_report_added_and_updated_in_request_order_When_the_request_mixes_both(self):
        # Arrange
        self.define([length("width", 12.0)])

        # Act
        envelope = self.define([length("depth", 3.0), length("width", 14.0), length("a_b", 1.0)])

        # Assert
        content = envelope["structured_content"]
        self.assertEqual(content["added"], ["depth", "a_b"])
        self.assertEqual(content["updated"], ["width"])

    def test_Should_accept_names_that_only_start_with_a_unit_symbol_When_defining(self):
        # Arrange
        names = ["W2", "min2", "mm_value", "Pa1", "A1", "None1"]

        # Act
        envelope = self.define([{"name": n, "type": "float", "value": 1.0} for n in names])

        # Assert
        self.assertEqual(envelope["status"], "OK", envelope.get("detail"))
        self.assertEqual(envelope["structured_content"]["added"], names)

    def test_Should_let_an_expression_read_the_parameter_When_it_is_a_new_name(self):
        # Arrange
        self.define([length("width", 12.0)])
        box = self.document().addObject("Part::Box", "Box")

        # Act
        box.setExpression("Length", "Params.width")
        self.document().recompute()

        # Assert
        self.assertEqual(box.Length.getValueAs("mm"), 12.0)

    def test_Should_refuse_with_the_unit_symbol_code_When_a_name_is_a_lexer_unit_or_constant(self):
        # Arrange
        symbols = ["W", "T", "A", "V", "N", "C", "K", "J", "H", "F", "S", "m", "g", "s"]
        symbols += ["mm", "deg", "in", "e", "pi", "True", "cm", "rad"]

        for symbol in symbols:
            with self.subTest(symbol=symbol):
                # Act
                envelope, minted = self.snapshots_minted_by(
                    lambda: self.dispatch([{"name": symbol, "type": "float", "value": 1.0}])
                )

                # Assert
                self.assertEqual(envelope["status"], "INVALID_INPUT")
                self.assertEqual(envelope["detail"]["code"], UNIT_SYMBOL_CODE)
                self.assertIn(symbol, envelope["detail"]["message"])
                self.assertEqual(minted, 0)
                self.assertIsNone(self.varset())

    def test_Should_fail_to_parse_an_expression_When_a_listed_name_is_added_as_a_property(self):
        # Arrange
        # The list is checked against the real parser here, so a stale entry fails on a runner
        # that has no copy of the lexer source.
        document = self.document()
        holder = document.addObject("App::VarSet", "Holder")
        box = document.addObject("Part::Box", "Box")

        for name in sorted(features._EXPRESSION_RESERVED_NAMES):
            with self.subTest(name=name):
                holder.addProperty("App::PropertyFloat", name, "Parameters")

                # Act
                def act():
                    box.setExpression("Length", f"Holder.{name}")

                # Assert
                with self.assertRaises(Exception):
                    act()
                box.setExpression("Length", None)

    def test_Should_refuse_with_the_reserved_code_When_a_varset_or_expression_uses_the_name(
        self,
    ):
        # Arrange
        self.define([length("width", 1.0)])
        names = ["Label", "Label2", "Visibility", "ExpressionEngine"]
        names += ["_pla", "_self", "_shape", "__matrix", "TypeId", "Name", "getTypeIdOfProperty"]

        for name in names:
            with self.subTest(name=name):
                # Act
                envelope = self.dispatch([{"name": name, "type": "string", "value": "x"}])

                # Assert
                self.assertEqual(envelope["detail"]["code"], "parameters.reserved_name")
        self.assertEqual(self.varset().Label, "Params")

    def test_Should_refuse_with_the_type_conflict_code_When_an_existing_property_has_another_type(
        self,
    ):
        # Arrange
        self.define([{"name": "n", "type": "float", "value": 2.5}])

        # Act
        envelope, minted = self.snapshots_minted_by(
            lambda: self.dispatch(
                [length("fresh", 1.0), {"name": "n", "type": "integer", "value": 3}]
            )
        )

        # Assert
        self.assertEqual(envelope["status"], "INVALID_INPUT")
        self.assertEqual(envelope["detail"]["code"], "parameters.type_conflict")
        self.assertEqual(minted, 0)
        self.assertEqual(self.varset().n, 2.5)
        self.assertNotIn("fresh", self.varset().PropertiesList)

    def test_Should_refuse_with_the_not_a_varset_code_When_the_name_holds_another_object(self):
        # Arrange
        self.document().addObject("Part::Box", "Box")

        # Act
        envelope = self.dispatch([length("width", 1.0)], varset="Box")

        # Assert
        self.assertEqual(envelope["detail"]["code"], "parameters.not_a_varset")
        self.assertNotIn("width", self.document().getObject("Box").PropertiesList)

    def test_Should_refuse_with_the_duplicate_code_When_a_name_appears_twice(self):
        # Act
        envelope = self.dispatch([length("width", 1.0), length("width", 2.0)])

        # Assert
        self.assertEqual(envelope["detail"]["code"], "parameters.duplicate_name")
        self.assertIsNone(self.varset())

    def test_Should_refuse_with_the_bound_code_When_an_update_targets_a_bound_property(self):
        # Arrange
        self.define([length("width", 10.0), length("depth", 4.0)])
        self.varset().setExpression("width", "Params.depth * 2")
        self.document().recompute()

        # Act
        envelope, minted = self.snapshots_minted_by(lambda: self.dispatch([length("width", 99.0)]))

        # Assert
        self.assertEqual(envelope["detail"]["code"], "parameters.bound_by_expression")
        self.assertEqual(minted, 0)
        self.assertEqual(self.varset().width.getValueAs("mm"), 8.0)

    def test_Should_refuse_naming_the_property_When_an_update_targets_a_read_only_property(self):
        # Arrange
        self.define([length("width", 10.0)])
        self.varset().setPropertyStatus("width", "ReadOnly")

        # Act
        envelope = self.dispatch([length("width", 11.0)])

        # Assert
        self.assertEqual(envelope["status"], "INVALID_INPUT")
        self.assertIn("Params.width is read-only", envelope["detail"]["message"])

    def test_Should_refuse_naming_the_parameter_When_a_field_is_malformed(self):
        # Arrange
        cases = {
            "integer above the C long": {"name": "n", "type": "integer", "value": 2**31},
            "bool as integer": {"name": "n", "type": "integer", "value": True},
            "float as integer": {"name": "n", "type": "integer", "value": 2.0},
            "nan": {"name": "x", "type": "float", "value": float("nan")},
            "integer beyond double range": {"name": "x", "type": "float", "value": 10**400},
            "negative length": {"name": "x", "type": "length", "value": mm(-5.0)},
            "angle above 360": {"name": "x", "type": "angle", "value": deg(400.0)},
            "angle below -360": {"name": "x", "type": "angle", "value": deg(-360.5)},
            "length in cm": {"name": "x", "type": "length", "value": {"value": 1, "unit": "cm"}},
            "bare length": {"name": "x", "type": "length", "value": 1.0},
            "angle in mm": {"name": "x", "type": "angle", "value": mm(1.0)},
            "string as bool": {"name": "x", "type": "bool", "value": "true"},
            "number as string": {"name": "x", "type": "string", "value": 3},
            "leading digit": {"name": "1x", "type": "float", "value": 1.0},
            "trailing newline": {"name": "W\n", "type": "float", "value": 1.0},
            "unknown type": {"name": "x", "type": "vector", "value": 1.0},
            "empty group": {"name": "x", "type": "float", "value": 1.0, "group": ""},
        }

        for label, parameter in cases.items():
            with self.subTest(label):
                # Act
                envelope, minted = self.snapshots_minted_by(lambda: self.dispatch([parameter]))

                # Assert
                self.assertEqual(envelope["status"], "INVALID_INPUT")
                self.assertIn("parameters[0]", envelope["detail"]["message"])
                self.assertEqual(minted, 0)
                self.assertIsNone(self.varset())

    def test_Should_accept_the_limits_When_a_length_is_zero_and_an_angle_is_plus_or_minus_360(self):
        # Arrange
        parameters = [
            length("zero", 0.0),
            {"name": "full", "type": "angle", "value": deg(360.0)},
            {"name": "back", "type": "angle", "value": deg(-360.0)},
        ]

        # Act
        envelope = self.define(parameters)

        # Assert
        self.assertEqual(envelope["status"], "OK", envelope.get("detail"))
        self.assertEqual(self.varset().full.getValueAs("deg"), 360.0)
        self.assertEqual(self.varset().back.getValueAs("deg"), -360.0)

    def test_Should_refuse_When_the_list_is_empty_too_long_or_not_a_list(self):
        for parameters in ([], [length(f"p{i}", 1.0) for i in range(101)], "width"):
            with self.subTest(type(parameters).__name__, size=len(parameters)):
                # Act
                envelope = self.dispatch(parameters)

                # Assert
                self.assertEqual(envelope["status"], "INVALID_INPUT")
                self.assertIsNone(self.varset())

    def test_Should_refuse_When_the_build_has_no_varset(self):
        # Arrange
        parameters = [length("width", 1.0)]

        # Act
        with mock.patch.object(shim, "varset_available", return_value=False):
            envelope = self.dispatch(parameters)

        # Assert
        self.assertEqual(envelope["status"], "INVALID_INPUT")
        self.assertIn("App::VarSet", envelope["detail"]["message"])

    def test_Should_refuse_When_the_builtin_property_probe_read_nothing(self):
        # Arrange
        parameters = [length("width", 1.0)]

        # Act
        with mock.patch.object(shim, "varset_builtin_properties", return_value=frozenset()):
            envelope = self.dispatch(parameters)

        # Assert
        self.assertEqual(envelope["status"], "INVALID_INPUT")
        self.assertIsNone(self.varset())


class RollbackTest(_ParametersFixture):
    def _failing_after_first_write(self):
        real = features._write_parameter
        writes = []

        def write_then_fail(target, spec):
            writes.append(spec["name"])
            result = real(target, spec)
            if len(writes) == 2:
                raise RuntimeError("planted failure after a write")
            return result

        return mock.patch.object(features, "_write_parameter", write_then_fail)

    def test_Should_remove_the_new_varset_and_prove_it_When_a_write_fails_after_the_first(self):
        # Arrange
        parameters = [length("width", 1.0), length("depth", 2.0)]

        # Act
        with self._failing_after_first_write():
            envelope = self.define(parameters)

        # Assert
        self.assertNotEqual(envelope["status"], "OK")
        block = envelope["structured_content"]["mutation"]
        self.assertTrue(block["rolled_back"])
        self.assertEqual(block["rollback_proven"], "rolled_back_verified")
        self.assertNotIn("added", envelope["structured_content"])
        self.assertIsNone(self.varset())
        self.assertEqual(_snapshot_leftovers(), [])

    def test_Should_restore_the_old_values_When_an_update_fails_after_the_first_write(self):
        # Arrange
        self.define([length("width", 10.0), length("depth", 4.0)])

        # Act
        with self._failing_after_first_write():
            envelope = self.define([length("width", 99.0), length("depth", 98.0)])

        # Assert
        self.assertNotEqual(envelope["status"], "OK")
        self.assertTrue(envelope["structured_content"]["mutation"]["rolled_back"])
        self.assertEqual(self.varset().width.getValueAs("mm"), 10.0)
        self.assertEqual(self.varset().depth.getValueAs("mm"), 4.0)

    def test_Should_restore_from_the_snapshot_When_the_abort_leaves_the_varset_changed(self):
        # Arrange
        # With undo off the abort restores nothing. The shape fingerprint holds no shape here, so
        # it still compares equal; only the property read-back sees the leftover write.
        self.define([length("width", 10.0)])
        original = self.document()
        original.UndoMode = 0

        # Act
        with mock.patch.object(shim, "enable_undo", return_value=False):
            with self._failing_after_first_write():
                envelope = self.define([length("width", 99.0), length("depth", 98.0)])

        # Assert
        block = envelope["structured_content"]["mutation"]
        self.assertTrue(block["rolled_back"])
        self.assertEqual(block["rollback_proven"], "rolled_back_via_snapshot")
        restored = self.document()
        self.assertIsNot(restored, original)
        self.assertEqual(restored.getObject("Params").width.getValueAs("mm"), 10.0)
        self.assertNotIn("depth", restored.getObject("Params").PropertiesList)

    def test_Should_not_prove_the_rollback_When_the_snapshot_restore_leaves_the_varset_changed(
        self,
    ):
        # Arrange
        self.define([length("width", 10.0)])
        self.document().UndoMode = 0

        def restore_nothing(document, _snapshot_path):
            return document

        # Act
        with mock.patch.object(shim, "enable_undo", return_value=False):
            with mock.patch.object(transaction, "_restore_from_snapshot", restore_nothing):
                with self._failing_after_first_write():
                    envelope = self.define([length("width", 99.0), length("depth", 98.0)])

        # Assert
        self.assertEqual(envelope["status"], "SPEC_FAILED")
        self.assertFalse(envelope["structured_content"]["mutation"]["rolled_back"])


class UndoAndPreviewTest(_ParametersFixture):
    def test_Should_remove_the_varset_When_the_creating_call_is_undone(self):
        # Arrange
        self.define([length("width", 12.0)])

        # Act
        undone = self.registry.document_undo(doc=self.handle)

        # Assert
        self.assertEqual(undone["status"], "OK", undone.get("detail"))
        self.assertIsNone(self.varset())

    def test_Should_restore_the_old_value_When_an_update_is_undone(self):
        # Arrange
        self.define([length("width", 12.0)])
        self.define([length("width", 20.0)])

        # Act
        self.registry.document_undo(doc=self.handle)

        # Assert
        self.assertEqual(self.varset().width.getValueAs("mm"), 12.0)

    def test_Should_be_reachable_through_the_preview_op_table_When_previewing(self):
        # Arrange
        table = preview_op_table()
        operation = {
            "tool": "feature_parameters_define",
            "args": {"varset": "Params", "parameters": [length("width", 3.0)]},
        }

        # Act
        envelope = preview.preview_dry_run(
            self.registry, table, None, doc=self.handle, operation=operation, render="off"
        )

        # Assert
        self.assertIn("feature_parameters_define", table)
        self.assertEqual(envelope["status"], "OK", envelope.get("detail"))
        self.assertIsNone(self.varset())


class DrivenGeometryTest(_ParametersFixture):
    def test_Should_report_the_pad_as_changed_When_a_bound_parameter_changes_its_length(self):
        # Arrange
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
        self.assertEqual(pad["status"], "OK", pad.get("detail"))
        self.define([length("height", 5.0)])
        self.document().getObject("Block").setExpression("Length", "Params.height")
        self.document().recompute()

        # Act
        envelope = self.define([length("height", 9.0)])

        # Assert
        self.assertEqual(envelope["status"], "OK", envelope.get("detail"))
        changed = [entry["name"] for entry in envelope["structured_content"]["mutation"]["changed"]]
        self.assertIn("Block", changed)
        self.assertAlmostEqual(self.document().getObject("Block").Shape.Volume, 8.0 * 16.0 * 9.0)

    def test_Should_restore_the_pad_When_a_bound_parameter_makes_it_fail(self):
        # Arrange
        body = self.empty_body()
        self.rect_sketch(body, "Profile", 0.0, 0.0, 8.0, 16.0)
        features.feature_pad(
            self.registry,
            doc=self.handle,
            body="Body",
            profile="Profile",
            name="Block",
            length=mm(5.0),
        )
        self.define([length("height", 5.0)])
        self.document().getObject("Block").setExpression("Length", "Params.height")
        self.document().recompute()

        # Act
        envelope = self.define([length("height", 0.0)])

        # Assert
        self.assertNotEqual(envelope["status"], "OK")
        self.assertTrue(envelope["structured_content"]["mutation"]["rolled_back"])
        self.assertEqual(self.varset().height.getValueAs("mm"), 5.0)
        self.assertAlmostEqual(self.document().getObject("Block").Shape.Volume, 8.0 * 16.0 * 5.0)
        self.assertEqual(App.listDocuments()[self.document().Name], self.document())


class Blob:
    """A picklable object a PropertyPythonObject can hold; its repr carries an address."""

    def __init__(self):
        self.value = 1


class UndoRecordTest(_ParametersFixture):
    def _user_box(self):
        document = self.document()
        document.openTransaction("user box")
        document.addObject("Part::Box", "UserBox")
        document.commitTransaction()

    def _note(self):
        return {"name": "note", "type": "string", "value": "rev A"}

    def test_Should_open_no_transaction_and_report_zero_undo_steps_When_every_value_is_current(
        self,
    ):
        # Arrange
        self.define([self._note()])
        self._user_box()
        undo_before = self.document().UndoCount

        # Act
        envelope, minted = self.snapshots_minted_by(lambda: self.define([self._note()]))

        # Assert
        content = envelope["structured_content"]
        self.assertEqual(envelope["status"], "OK")
        self.assertEqual(content["unchanged"], ["note"])
        self.assertEqual((content["added"], content["updated"]), ([], []))
        self.assertEqual(content["undo_steps"], 0)
        self.assertNotIn("mutation", content)
        self.assertEqual(minted, 0)
        self.assertEqual(self.document().UndoCount, undo_before)

    def test_Should_revert_the_earlier_step_When_undo_follows_a_call_that_changed_nothing(self):
        # Arrange
        self.define([self._note()])
        self._user_box()
        noop = self.define([self._note()])

        # Act
        undone = self.registry.document_undo(doc=self.handle)

        # Assert
        # undo_steps 0 is the signal: the undo reverts the step before the call, the user's box.
        self.assertEqual(noop["structured_content"]["undo_steps"], 0)
        self.assertEqual(undone["status"], "OK", undone.get("detail"))
        self.assertIsNone(self.document().getObject("UserBox"))

    def test_Should_record_one_step_and_list_the_unchanged_When_the_call_changes_only_some(self):
        # Arrange
        self.define([self._note()])
        self._user_box()

        # Act
        envelope = self.define([self._note(), length("w", 3.0)])
        undone = self.registry.document_undo(doc=self.handle)

        # Assert
        content = envelope["structured_content"]
        self.assertEqual((content["unchanged"], content["added"]), (["note"], ["w"]))
        self.assertEqual(content["undo_steps"], 1)
        self.assertEqual(undone["status"], "OK", undone.get("detail"))
        self.assertIsNotNone(self.document().getObject("UserBox"))
        self.assertNotIn("w", self.varset().PropertiesList)

    def test_Should_report_the_step_it_recorded_When_a_value_changes(self):
        # Arrange
        self.define([length("w", 3.0)])

        # Act
        envelope = self.define([length("w", 4.0)])

        # Assert
        content = envelope["structured_content"]
        self.assertEqual(content["updated"], ["w"])
        self.assertEqual((content["unchanged"], content["undo_steps"]), ([], 1))


class MetadataTest(_ParametersFixture):
    def test_Should_restore_everything_When_the_creating_call_is_undone(self):
        # Arrange
        self.define([length("w", 3.0, group="Size", description="width")])

        # Act
        self.registry.document_undo(doc=self.handle)

        # Assert
        self.assertIsNone(self.varset())

    def test_Should_refuse_with_the_metadata_code_When_a_group_or_description_would_change(self):
        # Arrange
        self.define([length("w", 3.0, group="Size", description="width")])
        cases = {"group": {"group": "Other"}, "description": {"description": "other"}}

        for label, extra in cases.items():
            with self.subTest(label):
                # Act
                envelope, minted = self.snapshots_minted_by(
                    lambda: self.dispatch([length("w", 4.0, **extra)])
                )

                # Assert
                self.assertEqual(envelope["detail"]["code"], "parameters.metadata_immutable")
                self.assertEqual(minted, 0)
                self.assertEqual(self.varset().w.getValueAs("mm"), 3.0)

    def test_Should_accept_the_same_metadata_When_it_repeats_the_current_values(self):
        # Arrange
        self.define([length("w", 3.0, group="Size", description="width")])

        # Act
        envelope = self.define([length("w", 4.0, group="Size", description="width")])

        # Assert
        self.assertEqual(envelope["structured_content"]["updated"], ["w"])
        self.assertEqual(self.varset().getGroupOfProperty("w"), "Size")


class StringAndNameTest(_ParametersFixture):
    def test_Should_refuse_with_the_string_code_When_a_text_holds_an_unstorable_character(self):
        # Arrange
        characters = ["\x00", "\x01", "\x08", "\x0b", "\x1f", "\x7f", "￾", "￿", "\ud800"]

        for character in characters:
            for field in ("value", "group", "description"):
                with self.subTest(character=repr(character), field=field):
                    parameter = {"name": "note", "type": "string", "value": "ok"}
                    parameter[field] = "rev A" + character + "tail"

                    # Act
                    envelope = self.dispatch([parameter])

                    # Assert
                    self.assertEqual(envelope["detail"]["code"], "parameters.invalid_string")
                    self.assertIsNone(self.varset())

    def test_Should_keep_a_text_unchanged_When_it_is_saved_and_reopened(self):
        # Arrange
        text = 'a\tb\nc\ré Ø 12 µm 漢 \U0001f600 "q" <&>'
        self.define([{"name": "note", "type": "string", "value": text}])
        path = os.path.join(tempfile.mkdtemp(prefix="fcb_str_"), "round.FCStd")
        self.document().saveCopy(path)

        # Act
        reopened = App.openDocument(path)

        # Assert
        self.assertEqual(reopened.getObject("Params").note, text)

    def test_Should_refuse_with_the_unit_symbol_code_When_the_varset_is_named_like_a_unit(self):
        for name in ("W", "mm", "e", "pi", "deg"):
            with self.subTest(name=name):
                # Act
                envelope = self.dispatch([length("width", 1.0)], varset=name)

                # Assert
                self.assertEqual(envelope["detail"]["code"], "parameters.unit_symbol_name")
                self.assertIn(name, envelope["detail"]["message"])
                self.assertIsNone(self.document().getObject(name))

    def test_Should_create_a_varset_whose_name_only_starts_with_a_unit_symbol_When_defining(self):
        # Act
        envelope = self.define([length("width", 1.0)], varset="W2")

        # Assert
        self.assertEqual(envelope["status"], "OK", envelope.get("detail"))

    def test_Should_refuse_with_the_reserved_code_When_a_name_is_read_from_every_object(self):
        for name in ("Shape", "ElementMapVersion"):
            with self.subTest(name=name):
                # Act
                envelope = self.dispatch([{"name": name, "type": "string", "value": "x"}])

                # Assert
                self.assertEqual(envelope["detail"]["code"], "parameters.reserved_name")
        self.assertIsNone(self.varset())


class StateProbeScopeTest(_ParametersFixture):
    def test_Should_prove_a_snapshot_restore_When_the_varset_holds_a_python_object(self):
        # Arrange
        self.define([length("width", 10.0)])
        varset = self.varset()
        varset.addProperty("App::PropertyPythonObject", "blob", "Parameters")
        varset.blob = Blob()
        self.document().UndoMode = 0
        real = features._write_parameter
        writes = []

        def write_then_fail(target, spec):
            writes.append(spec["name"])
            result = real(target, spec)
            if len(writes) == 2:
                raise RuntimeError("planted failure after a write")
            return result

        # Act
        with mock.patch.object(shim, "enable_undo", return_value=False):
            with mock.patch.object(features, "_write_parameter", write_then_fail):
                envelope = self.dispatch([length("width", 99.0), length("depth", 98.0)])

        # Assert
        block = envelope["structured_content"]["mutation"]
        self.assertEqual(block["rollback_proven"], "rolled_back_via_snapshot")
        self.assertEqual(self.varset().width.getValueAs("mm"), 10.0)

    def _unproven_message(self, probe):
        record = fingerprint_module.fingerprint(self.document())
        path = transaction.temp_snapshot_path(self.document())
        self.document().saveCopy(path)

        def act():
            with mock.patch.object(transaction, "massprops_equal", return_value=False):
                with mock.patch.object(transaction, "fingerprints_equal", return_value=False):
                    transaction._prove_rollback(self.document(), record, path, False, probe, None)

        with self.assertRaises(transaction.RollbackNotProven) as caught:
            act()
        return str(caught.exception)

    def test_Should_name_the_property_state_When_the_tool_has_a_state_probe(self):
        # Act
        message = self._unproven_message(lambda document: None)

        # Assert
        self.assertIn("pre-mutation property state", message)

    def test_Should_not_name_a_property_state_When_the_tool_has_no_state_probe(self):
        # Act
        message = self._unproven_message(None)

        # Assert
        self.assertNotIn("property state", message)
