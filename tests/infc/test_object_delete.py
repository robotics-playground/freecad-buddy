"""In-FreeCAD tests for ``document_object_delete`` (stdlib unittest).

Run via ``FreeCADCmd tests/run_tests.py``. Expected states are the ones the fixture built (object
names, Body ``Tip``, a pad length that follows a VarSet), read back from the live document and
never from the tool under test.
"""

from unittest import mock

import FreeCAD as App

from freecad_buddy.adapters.rpc_dispatch import MethodRegistry, RpcMethod
from freecad_buddy.hosts.tool_catalog import preview_op_table
from freecad_buddy.usecases import features, preview, shim, tnp_guard, transaction
from freecad_buddy.usecases.documents import ValidationError
from freecad_buddy.usecases.fingerprint import fingerprint
from infc.test_feature_tools import _FeatureFixture, _snapshot_leftovers

HAS_DEPENDENTS = "delete.has_dependents"
ORIGIN_OBJECT = "delete.origin_object"


class _DeleteFixture(_FeatureFixture):
    """A Body of Sketch1, Pad1 (Length = VS.L), Sketch2, Pad2, beside a VarSet ``VS``."""

    def setUp(self):
        super().setUp()
        document = self.document()
        self.body = self.empty_body()
        sketch1 = self.rect_sketch(self.body, "Sketch1", 0, 0, 20, 20)
        pad1 = self.body.newObject("PartDesign::Pad", "Pad1")
        pad1.Profile = sketch1
        pad1.Length = 10
        document.recompute()
        sketch2 = self.rect_sketch(self.body, "Sketch2", 5, 5, 5, 5, z=10)
        pad2 = self.body.newObject("PartDesign::Pad", "Pad2")
        pad2.Profile = sketch2
        pad2.Length = 5
        varset = document.addObject("App::VarSet", "VS")
        varset.addProperty("App::PropertyLength", "L", "Parameters")
        varset.L = 10
        pad1.setExpression("Length", "VS.L")
        document.recompute()

    def delete(self, objects, **extra):
        target = features.document_object_delete
        return target(self.registry, doc=self.handle, objects=objects, **extra)

    def names(self):
        return [obj.Name for obj in self.document().Objects]

    def obj(self, name):
        return self.document().getObject(name)

    def set_source_and_read_pad_length(self, value):
        self.obj("VS").L = value
        self.document().recompute()
        return self.obj("Pad1").Length.getValueAs("mm")


class DeleteTest(_DeleteFixture):
    def test_Should_remove_the_tip_and_move_the_tip_back_When_the_last_feature_is_deleted(self):
        # Arrange
        expected_tip = "Pad1"

        # Act
        envelope = self.delete(["Pad2"])

        # Assert
        self.assertEqual(envelope["status"], "OK", envelope.get("detail"))
        content = envelope["structured_content"]
        self.assertEqual((content["deleted"], content["dependents"]), (["Pad2"], []))
        self.assertIsNone(self.obj("Pad2"))
        self.assertEqual(self.body.Tip.Name, expected_tip)
        self.assertNotIn("Pad2", [member.Name for member in self.body.Group])
        self.assertTrue(envelope["structured_content"]["mutation"]["post_verify"]["passed"])

    def test_Should_refuse_naming_the_dependent_When_a_profile_sketch_is_deleted_alone(self):
        # Arrange
        before = self.names()

        # Act
        message = self.assert_rejected_pre_bracket(self.names, self.delete, ["Sketch1"])

        # Assert
        self.assertIn("Pad1", message)
        self.assertEqual(self.names(), before)

    def test_Should_carry_the_dependents_code_When_the_dispatcher_maps_the_refusal(self):
        # Arrange
        methods = MethodRegistry()
        methods.register(
            RpcMethod(
                name="document_object_delete",
                handler=lambda **p: features.document_object_delete(self.registry, **p),
                mutating=True,
            )
        )

        # Act
        envelope = methods.dispatch(
            "document_object_delete", {"doc": self.handle, "objects": ["Sketch1"]}
        )

        # Assert
        self.assertEqual(envelope["status"], "INVALID_INPUT")
        self.assertEqual(envelope["detail"]["code"], HAS_DEPENDENTS)

    def test_Should_delete_the_closure_and_list_it_When_dependents_are_allowed(self):
        # Arrange
        expected_dependents = ["Pad1", "Pad2"]

        # Act
        envelope = self.delete(["Sketch1"], with_dependents=True)

        # Assert
        self.assertEqual(envelope["status"], "OK", envelope.get("detail"))
        content = envelope["structured_content"]
        self.assertEqual(content["deleted"], ["Sketch1", "Pad1", "Pad2"])
        self.assertEqual(content["dependents"], expected_dependents)
        self.assertEqual(
            [name for name in self.names() if name.startswith(("Sketch", "Pad"))], ["Sketch2"]
        )
        self.assertIsNone(self.body.Tip)

    def test_Should_remove_the_body_its_members_and_its_origin_When_the_body_is_deleted(self):
        # Arrange
        origin_names = [feature.Name for feature in self.body.Origin.OriginFeatures]

        # Act
        envelope = self.delete(["Body"])

        # Assert
        self.assertEqual(envelope["status"], "OK", envelope.get("detail"))
        self.assertEqual(self.names(), ["VS"])
        deleted = envelope["structured_content"]["deleted"]
        for name in ["Body", "Origin", "Sketch1", "Pad1", "Sketch2", "Pad2", *origin_names]:
            self.assertIn(name, deleted)

    def test_Should_refuse_the_origin_code_When_an_origin_plane_is_named_without_its_body(self):
        # Arrange
        plane = next(f for f in self.body.Origin.OriginFeatures if f.Role == "XY_Plane").Name

        # Act
        with self.assertRaises(ValidationError) as caught:
            self.delete([plane])

        # Assert
        self.assertEqual(caught.exception.code, ORIGIN_OBJECT)
        self.assertIsNotNone(self.obj(plane))

    def test_Should_refuse_the_origin_code_When_the_origin_object_is_named_without_its_body(self):
        # Arrange
        origin = self.body.Origin.Name

        # Act
        with self.assertRaises(ValidationError) as caught:
            self.delete([origin])

        # Assert
        self.assertEqual(caught.exception.code, ORIGIN_OBJECT)
        self.assertIsNotNone(self.obj(origin))

    def test_Should_refuse_naming_the_next_feature_When_a_middle_feature_is_deleted_alone(self):
        # Arrange
        before = self.names()

        # Act
        with self.assertRaises(ValidationError) as caught:
            self.delete(["Pad1"])

        # Assert
        self.assertEqual(caught.exception.code, HAS_DEPENDENTS)
        self.assertIn("Pad2", str(caught.exception))
        self.assertEqual(self.names(), before)

    def test_Should_keep_the_children_and_remove_the_origin_When_a_part_is_deleted(self):
        # Arrange
        document = self.document()
        part = document.addObject("App::Part", "Assembly")
        part.addObject(self.body)
        origin_names = [part.Origin.Name, *[f.Name for f in part.Origin.OriginFeatures]]

        # Act
        envelope = self.delete(["Assembly"])

        # Assert
        self.assertEqual(envelope["status"], "OK", envelope.get("detail"))
        self.assertIsNone(self.obj("Assembly"))
        for name in origin_names:
            self.assertIsNone(self.obj(name))
        self.assertIsNotNone(self.obj("Body"))
        self.assertIsNotNone(self.obj("Pad2"))

    def test_Should_delete_the_copy_When_a_body_follows_its_origin_in_document_order(self):
        # Arrange
        document = self.document()
        copies = document.copyObject(self.body, True)
        copy = copies[0] if isinstance(copies, (list, tuple)) else copies
        copy_name = copy.Name
        order = self.names()
        self.assertGreater(order.index(copy_name), order.index(copy.Origin.Name))

        # Act
        envelope = self.delete([copy_name])

        # Assert
        self.assertEqual(envelope["status"], "OK", envelope.get("detail"))
        self.assertIsNone(self.obj(copy_name))
        self.assertIsNotNone(self.obj("Body"))

    def test_Should_not_read_a_vector_origin_as_an_origin_object_When_a_function_has_one(self):
        # Arrange
        class FunctionLike:
            Name = "Plane"
            TypeId = "Fem::FemPostPlaneFunction"
            Origin = App.Vector(0, 0, 0)

        # Act
        owned = features._origin_objects(FunctionLike())

        # Assert
        self.assertEqual(owned, [])

    def test_Should_refuse_naming_the_bound_pad_When_a_bound_varset_is_deleted(self):
        # Arrange
        expected_code = HAS_DEPENDENTS

        # Act
        with self.assertRaises(ValidationError) as caught:
            self.delete(["VS"])

        # Assert
        self.assertEqual(caught.exception.code, expected_code)
        self.assertIn("Pad1", str(caught.exception))
        self.assertIsNotNone(self.obj("VS"))

    def test_Should_refuse_before_the_bracket_When_the_object_is_unknown(self):
        # Arrange
        objects = ["Nope"]

        # Act
        message = self.assert_rejected_pre_bracket(self.names, self.delete, objects)

        # Assert
        self.assertIn("Nope", message)

    def test_Should_refuse_before_the_bracket_When_the_object_list_is_empty(self):
        # Arrange
        objects = []

        # Act
        message = self.assert_rejected_pre_bracket(self.names, self.delete, objects)

        # Assert
        self.assertIn("non-empty", message)

    def test_Should_report_the_pad_as_deleted_in_the_diff_When_a_feature_is_deleted(self):
        # Arrange
        expected_name = "Pad2"

        # Act
        envelope = self.delete([expected_name])

        # Assert
        changed = envelope["structured_content"]["mutation"]["changed"]
        self.assertIn(expected_name, [entry["name"] for entry in changed])


class OperandAndBindingTest(_DeleteFixture):
    def _boolean_over_second_body(self):
        """A PartDesign::Boolean in Body that fuses a second Body (a 10x10x10 block at x=30)."""
        document = self.document()
        second = document.addObject("PartDesign::Body", "Body2")
        sketch = self.rect_sketch(second, "SketchB", 30, 0, 10, 10)
        pad = second.newObject("PartDesign::Pad", "PadB")
        pad.Profile = sketch
        pad.Length = 10
        boolean = self.body.newObject("PartDesign::Boolean", "Bool")
        boolean.addObjects([second])
        document.recompute()
        return boolean

    def test_Should_refuse_naming_the_boolean_When_an_operand_body_is_deleted(self):
        # Arrange
        self._boolean_over_second_body()
        before = self.names()

        # Act
        with self.assertRaises(ValidationError) as caught:
            self.delete(["Body2"])

        # Assert
        self.assertEqual(caught.exception.code, HAS_DEPENDENTS)
        self.assertIn("Bool", str(caught.exception))
        self.assertEqual(self.names(), before)

    def test_Should_drop_the_operand_volume_When_the_boolean_is_deleted_with_its_operand(self):
        # Arrange
        self._boolean_over_second_body()
        alone = self.obj("Pad2").Shape.Volume
        fused = self.body.Shape.Volume
        self.assertAlmostEqual(fused, alone + 1000.0, places=3)

        # Act
        envelope = self.delete(["Body2"], with_dependents=True)

        # Assert
        self.assertEqual(envelope["status"], "OK", envelope.get("detail"))
        self.assertIn("Bool", envelope["structured_content"]["dependents"])
        self.document().recompute()
        self.assertAlmostEqual(self.body.Shape.Volume, alone, places=3)

    def test_Should_refuse_naming_the_body_When_an_expression_on_it_names_a_member(self):
        # Arrange
        self.body.setExpression("Placement.Base.z", "Pad2.Length")
        self.document().recompute()
        before = self.names()

        # Act
        with self.assertRaises(ValidationError) as caught:
            self.delete(["Pad2"])

        # Assert
        self.assertEqual(caught.exception.code, HAS_DEPENDENTS)
        self.assertIn("Body", str(caught.exception))
        self.assertEqual(self.names(), before)

    def test_Should_delete_the_body_and_succeed_When_dependents_are_allowed_for_a_bound_member(
        self,
    ):
        # Arrange
        self.body.setExpression("Placement.Base.z", "Pad2.Length")
        self.document().recompute()

        # Act
        envelope = self.delete(["Pad2"], with_dependents=True)

        # Assert
        self.assertEqual(envelope["status"], "OK", envelope.get("detail"))
        self.assertIn("Body", envelope["structured_content"]["deleted"])
        self.assertIsNone(self.obj("Body"))


class VisibleTipAndLinkArrayTest(_DeleteFixture):
    def test_Should_show_the_new_tip_and_undo_the_visibility_When_a_visible_tip_is_deleted(self):
        # Arrange
        self.obj("Pad1").Visibility = False
        self.obj("Pad2").Visibility = True

        # Act
        envelope = self.delete(["Pad2"])

        # Assert
        self.assertEqual(envelope["status"], "OK", envelope.get("detail"))
        self.assertIs(self.obj("Pad1").Visibility, True)
        self.registry.document_undo(doc=self.handle)
        self.assertIs(self.obj("Pad1").Visibility, False)
        self.assertIs(self.obj("Pad2").Visibility, True)

    def test_Should_leave_the_visible_feature_alone_When_a_hidden_tip_is_deleted(self):
        # Arrange
        self.obj("Pad1").Visibility = False
        self.obj("Pad2").Visibility = False

        # Act
        self.delete(["Pad2"])

        # Assert
        self.assertIs(self.obj("Pad1").Visibility, False)

    def test_Should_delete_the_elements_with_the_array_and_restore_them_When_undone(self):
        # Arrange
        document = self.document()
        box = document.addObject("Part::Box", "Box")
        array = document.addObject("App::Link", "Arr")
        array.setLink(box)
        array.ShowElement = True
        array.ElementCount = 3
        document.recompute()
        elements = [element.Name for element in array.ElementList]
        self.assertEqual(len(elements), 3)

        # Act
        envelope = self.delete(["Arr"])

        # Assert
        self.assertEqual(envelope["status"], "OK", envelope.get("detail"))
        self.assertEqual(envelope["structured_content"]["deleted"], ["Arr", *elements])
        for name in elements:
            self.assertIsNone(self.obj(name))
        self.registry.document_undo(doc=self.handle)
        self.assertEqual([e.Name for e in self.obj("Arr").ElementList], elements)


class TnpExemptionTest(_DeleteFixture):
    def _audit(self, vanished, deleted):
        document = self.document()
        snapshot = tnp_guard.snapshot_references(document)
        for name in vanished:
            document.removeObject(name)
        document.recompute()
        return tnp_guard.audit_references(document, snapshot, None, frozenset(deleted))

    def _broken_owners(self, audit):
        return sorted(f["owner"] for f in audit["findings"] if f["verdict"] == "BROKEN")

    def test_Should_stay_clean_When_a_deleted_owner_of_a_reference_is_in_the_delete_set(self):
        # Arrange
        vanished = ["Pad2"]

        # Act
        audit = self._audit(vanished, deleted={"Pad2"})

        # Assert
        self.assertEqual(self._broken_owners(audit), [])

    def test_Should_grade_broken_When_an_owner_vanished_outside_the_delete_set(self):
        # Arrange
        vanished = ["Pad2"]

        # Act
        audit = self._audit(vanished, deleted=set())

        # Assert
        self.assertIn("Pad2", self._broken_owners(audit))
        self.assertEqual(audit["status"], "FLAGGED")

    def test_Should_grade_broken_When_a_second_owner_vanished_that_the_set_does_not_name(self):
        # Arrange
        vanished = ["Pad2", "Pad1"]

        # Act
        audit = self._audit(vanished, deleted={"Pad2"})

        # Assert
        broken = self._broken_owners(audit)
        self.assertIn("Pad1", broken)
        self.assertNotIn("Pad2", broken)

    def test_Should_pass_post_verify_with_a_clean_audit_When_an_owner_of_a_profile_is_deleted(
        self,
    ):
        # Arrange
        objects = ["Pad1", "Pad2"]

        # Act
        envelope = self.delete(objects)

        # Assert
        self.assertEqual(envelope["status"], "OK", envelope.get("detail"))
        audit = envelope["structured_content"]["mutation"]["post_verify"]["tnp_audit"]
        self.assertEqual(audit["status"], "CLEAN", audit)


class UndoTest(_DeleteFixture):
    def test_Should_restore_everything_with_one_undo_When_a_dependents_delete_is_undone(self):
        # Arrange
        document = self.document()
        before_digest = fingerprint(document)["digest"]
        before_names = self.names()
        before_tip = self.body.Tip.Name
        before_group = [member.Name for member in self.body.Group]
        self.delete(["Sketch1"], with_dependents=True)

        # Act
        undone = self.registry.document_undo(doc=self.handle, expect_fingerprint=before_digest)

        # Assert
        self.assertEqual(undone["status"], "OK", undone.get("detail"))
        self.assertTrue(undone["structured_content"]["matches_pre_op"])
        self.assertEqual(sorted(self.names()), sorted(before_names))
        self.assertEqual(self.body.Tip.Name, before_tip)
        self.assertEqual([member.Name for member in self.body.Group], before_group)
        self.assertEqual(self.obj("Pad2").BaseFeature.Name, "Pad1")
        self.assertEqual(self.obj("Pad1").Profile[0].Name, "Sketch1")

    def test_Should_restore_the_tip_and_the_visibility_When_a_tip_delete_is_undone(self):
        # Arrange
        self.obj("Pad2").Visibility = False
        self.delete(["Pad2"])

        # Act
        undone = self.registry.document_undo(doc=self.handle)

        # Assert
        self.assertEqual(undone["status"], "OK", undone.get("detail"))
        self.assertEqual(self.body.Tip.Name, "Pad2")
        self.assertIs(self.obj("Pad2").Visibility, False)
        self.assertEqual(self.obj("Pad2").Label, "Pad2")

    def test_Should_restore_the_body_and_its_origin_When_a_body_delete_is_undone(self):
        # Arrange
        before = sorted(self.names())
        origin_names = [f.Name for f in self.body.Origin.OriginFeatures]
        self.delete(["Body"])

        # Act
        undone = self.registry.document_undo(doc=self.handle)

        # Assert
        self.assertEqual(undone["status"], "OK", undone.get("detail"))
        self.assertEqual(sorted(self.names()), before)
        body = self.obj("Body")
        self.assertEqual([f.Name for f in body.Origin.OriginFeatures], origin_names)
        self.assertEqual(body.Tip.Name, "Pad2")
        self.assertEqual(self.obj("Sketch1").Placement.Base.z, 0)

    def test_Should_restore_source_and_bound_pad_When_the_varset_delete_takes_its_dependents(self):
        # Arrange
        envelope = self.delete(["VS"], with_dependents=True)
        self.assertEqual(envelope["structured_content"]["dependents"][0], "Pad1")

        # Act
        self.registry.document_undo(doc=self.handle)
        length = self.set_source_and_read_pad_length(9.0)

        # Assert
        self.assertEqual(length, 9.0)
        self.assertEqual(self.obj("Pad1").ExpressionEngine, [("Length", "VS.L")])

    def test_Should_keep_following_the_varset_When_a_bound_pad_is_deleted_and_undone(self):
        # Arrange
        self.delete(["Pad1", "Pad2"])
        self.registry.document_undo(doc=self.handle)
        expected_length = 7.0

        # Act
        length = self.set_source_and_read_pad_length(expected_length)

        # Assert
        self.assertEqual(length, expected_length)
        self.assertIn("VS", [dependency.Name for dependency in self.obj("Pad1").OutList])

    def test_Should_keep_redo_and_add_no_undo_step_When_the_expression_is_relinked(self):
        # Arrange
        self.delete(["Pad1", "Pad2"])
        document = self.document()

        # Act
        self.registry.document_undo(doc=self.handle)

        # Assert
        self.assertEqual((document.UndoCount, document.RedoCount), (0, 1))
        document.redo()
        self.assertIsNone(self.obj("Pad1"))

    def test_Should_report_the_binding_in_errors_When_an_expression_cannot_be_set_again(self):
        # Arrange
        self.delete(["Pad1", "Pad2"])
        real = shim.relink_expressions

        def failing(document, names):
            real(document, names)
            return [("Pad1", "Length", "VS.L")]

        # Act
        with mock.patch.object(shim, "relink_expressions", failing):
            undone = self.registry.document_undo(doc=self.handle)

        # Assert
        self.assertEqual(undone["status"], "RECOMPUTE_ERROR")
        errors = undone["structured_content"]["errors"]
        self.assertEqual(errors[0]["name"], "Pad1")
        self.assertIn("Length", errors[0]["error"])
        self.assertIn("VS.L", errors[0]["error"])


class RelinkTest(_DeleteFixture):
    def test_Should_return_the_binding_that_fails_When_set_expression_raises(self):
        # Arrange
        class Unbindable:
            Name = "Stub"
            ExpressionEngine = [("Length", "VS.L")]

            def setExpression(self, path, expression):
                raise RuntimeError("cannot bind")

        class Holder:
            def getObject(self, name):
                return Unbindable() if name == "Stub" else None

        # Act
        failed = shim.relink_expressions(Holder(), ["Stub", "Missing"])

        # Assert
        self.assertEqual(failed, [("Stub", "Length", "VS.L")])


class RollbackTest(_DeleteFixture):
    def _fail_on_second_removal(self):
        real = features._owning_body
        calls = []

        def counting(document, target):
            calls.append(target.Name)
            if len(calls) == 2:
                raise RuntimeError("planted failure after a removal")
            return real(document, target)

        return mock.patch.object(features, "_owning_body", counting)

    def test_Should_restore_the_object_set_and_prove_it_When_a_delete_fails_after_a_removal(self):
        # Arrange
        before = self.names()

        # Act
        with self._fail_on_second_removal():
            envelope = self.delete(["Pad1", "Pad2"])

        # Assert
        self.assertNotEqual(envelope["status"], "OK")
        block = envelope["structured_content"]["mutation"]
        self.assertTrue(block["rolled_back"])
        self.assertIn(
            block["rollback_proven"], ("rolled_back_verified", "rolled_back_via_snapshot")
        )
        self.assertEqual(sorted(self.names()), sorted(before))
        self.assertEqual(self.body.Tip.Name, "Pad2")
        self.assertEqual(_snapshot_leftovers(), [])

    def test_Should_keep_following_the_varset_When_an_aborted_delete_restored_the_bound_pad(self):
        # Arrange
        expected_length = 6.0

        # Act
        failure = RuntimeError("planted failure after every removal")
        with mock.patch.object(transaction, "post_verify", side_effect=failure):
            envelope = self.delete(["Pad1", "Pad2"])
        length = self.set_source_and_read_pad_length(expected_length)

        # Assert
        block = envelope["structured_content"]["mutation"]
        self.assertTrue(block["rolled_back"])
        self.assertEqual(block["rollback_proven"], "rolled_back_verified")
        self.assertEqual(length, expected_length)

    def test_Should_restore_from_the_snapshot_When_an_aborted_shapeless_delete_leaves_shapes_equal(
        self,
    ):
        # Arrange
        # A VarSet has no shape, and with undo off the abort restores nothing: the shape
        # fingerprint still compares equal, so only the object-set read-back sees the leftover.
        document = self.document()
        document.addObject("App::VarSet", "Lone")
        document.addObject("App::VarSet", "Lone2")
        document.recompute()
        document.UndoMode = 0

        # Act
        with mock.patch.object(shim, "enable_undo", return_value=False):
            with self._fail_on_second_removal():
                envelope = self.delete(["Lone", "Lone2"])

        # Assert
        block = envelope["structured_content"]["mutation"]
        self.assertTrue(block["rolled_back"])
        self.assertEqual(block["rollback_proven"], "rolled_back_via_snapshot")
        self.assertIsNotNone(self.document().getObject("Lone"))
        self.assertIsNotNone(self.document().getObject("Lone2"))


class PreviewTest(_DeleteFixture):
    def test_Should_preview_the_delete_and_leave_the_document_unchanged_When_previewing(self):
        # Arrange
        table = preview_op_table()
        before = self.names()
        operation = {"tool": "document_object_delete", "args": {"objects": ["Pad2"]}}

        # Act
        envelope = preview.preview_dry_run(
            self.registry, table, None, doc=self.handle, operation=operation, render="off"
        )

        # Assert
        self.assertIn("document_object_delete", table)
        self.assertEqual(envelope["status"], "OK", envelope.get("detail"))
        self.assertEqual(self.names(), before)
        self.assertEqual(self.body.Tip.Name, "Pad2")
