"""In-FreeCAD tests for ``feature_set_parameters`` writing placements and strings.

Run via ``FreeCADCmd tests/run_tests.py``. Expected values are the ones the caller wrote and
analytic coordinates, read back from the live objects, never from the tool under test.
"""

import math
from unittest import mock

import FreeCAD as App

from freecad_buddy.adapters.rpc_dispatch import MethodRegistry, RpcMethod
from freecad_buddy.usecases import features, shim
from freecad_buddy.usecases.documents import ValidationError
from infc.test_feature_tools import _FeatureFixture, _snapshot_leftovers, deg, mm


def base(**axes):
    return {"base": {key: mm(value) for key, value in axes.items()}}


def rotation(axis, angle):
    return {"rotation": {"axis": list(axis), "angle": deg(angle)}}


def placement(x=0.0, y=0.0, z=0.0, axis=(0, 0, 1), angle=0.0):
    return App.Placement(App.Vector(x, y, z), App.Rotation(App.Vector(*axis), angle))


class PlacementParserTest(_FeatureFixture):
    def parse(self, raw, current=None):
        return features._placement_value(raw, "Obj.Placement", current)

    def test_Should_default_to_the_origin_and_no_rotation_When_there_is_no_current_placement(self):
        # Arrange
        raw = base(x=5.0)

        # Act
        target = self.parse(raw)

        # Assert
        self.assertEqual(tuple(target.Base), (5.0, 0.0, 0.0))
        self.assertAlmostEqual(target.Rotation.Angle, 0.0)

    def test_Should_keep_the_omitted_components_When_a_current_placement_is_given(self):
        # Arrange
        current = placement(1.0, 2.0, 3.0, axis=(0, 1, 0), angle=40.0)

        # Act
        target = self.parse(base(y=9.0), current)

        # Assert
        self.assertEqual(tuple(target.Base), (1.0, 9.0, 3.0))
        self.assertAlmostEqual(math.degrees(target.Rotation.Angle), 40.0)
        self.assertAlmostEqual(target.Rotation.Axis.y, 1.0)

    def test_Should_store_the_rotation_exactly_When_the_axis_is_not_a_unit_vector(self):
        # Arrange
        raw = {"rotation": {"axis": [1, 2, 3], "angle": deg(37.5)}}
        target = self.parse(raw)
        holder = self.document().addObject("Part::Feature", "Holder")

        # Act
        holder.Placement = target

        # Assert
        self.assertTrue(holder.Placement.isSame(target, 0.0))

    def test_Should_keep_the_axis_When_only_the_angle_is_given(self):
        # Arrange
        current = placement(axis=(0, 1, 0), angle=40.0)

        # Act
        target = self.parse({"rotation": {"angle": deg(90.0)}}, current)

        # Assert
        self.assertAlmostEqual(math.degrees(target.Rotation.Angle), 90.0)
        self.assertAlmostEqual(target.Rotation.Axis.y, 1.0)

    def test_Should_keep_the_angle_When_only_the_axis_is_given(self):
        # Arrange
        current = placement(axis=(0, 1, 0), angle=40.0)

        # Act
        target = self.parse({"rotation": {"axis": [1, 0, 0]}}, current)

        # Assert
        self.assertAlmostEqual(math.degrees(target.Rotation.Angle), 40.0)
        self.assertAlmostEqual(target.Rotation.Axis.x, 1.0)

    def test_Should_refuse_the_value_When_it_is_malformed(self):
        # Arrange
        cases = {
            "unknown key": {"position": {}},
            "unknown base key": {"base": {"w": mm(1.0)}},
            "axis too long for FreeCAD": rotation((1e200, 0, 0), 10.0),
            "axis too short for FreeCAD": rotation((1e-200, 0, 0), 10.0),
            "axis beyond the float range": rotation((10**400, 0, 0), 10.0),
            "length beyond the float range": {"base": {"x": {"value": 10**400, "unit": "mm"}}},
            "angle beyond the float range": {
                "rotation": {"angle": {"value": 10**400, "unit": "deg"}}
            },
            "axis without angle from no rotation": {"rotation": {"axis": [1, 0, 0]}},
            "unknown rotation key": {"rotation": {"quaternion": [0, 0, 0, 1]}},
            "zero axis": rotation((0, 0, 0), 10.0),
            "short axis": rotation((1, 0), 10.0),
            "boolean axis component": rotation((True, 0, 0), 10.0),
            "infinite axis": rotation((math.inf, 0, 0), 10.0),
            "infinite length": {"base": {"x": {"value": math.inf, "unit": "mm"}}},
            "nan angle": {"rotation": {"angle": {"value": math.nan, "unit": "deg"}}},
            "length in degrees": {"base": {"x": deg(1.0)}},
            "angle in mm": {"rotation": {"angle": mm(1.0)}},
            "bare number length": {"base": {"x": 1.0}},
            "base not an object": {"base": [1, 2, 3]},
            "not an object": [1, 2, 3],
        }
        for label, raw in cases.items():
            with self.subTest(label):
                # Act
                def act(raw=raw):
                    return self.parse(raw)

                # Assert
                with self.assertRaises(ValidationError):
                    act()


class _PlacementFixture(_FeatureFixture):
    def set_parameters(self, feature, parameters):
        return features.feature_set_parameters(
            self.registry, doc=self.handle, feature=feature, parameters=parameters
        )

    def dispatch(self, feature, parameters):
        methods = MethodRegistry()
        methods.register(
            RpcMethod(
                name="feature_set_parameters",
                handler=lambda **p: features.feature_set_parameters(self.registry, **p),
                mutating=True,
            )
        )
        return methods.dispatch(
            "feature_set_parameters",
            {"doc": self.handle, "feature": feature, "parameters": parameters},
        )

    def padded_body(self):
        """A Body holding an attached sketch and an 8x16x5 Pad."""
        document = self.document()
        body = self.empty_body()
        sketch = self.rect_sketch(body, "Profile", 0.0, 0.0, 8.0, 16.0)
        plane = next(f for f in body.Origin.OriginFeatures if f.Role == "XY_Plane")
        sketch.AttachmentSupport = [(plane, "")]
        sketch.MapMode = "FlatFace"
        document.recompute()
        envelope = features.feature_pad(
            self.registry,
            doc=self.handle,
            body="Body",
            profile="Profile",
            name="Block",
            length=mm(5.0),
        )
        self.assertEqual(envelope["status"], "OK", envelope.get("detail"))
        return body

    def undo(self):
        return self.registry.document_undo(self.handle)


class PlacementWriteTest(_PlacementFixture):
    def test_Should_move_only_x_and_undo_it_When_a_body_placement_names_base_x(self):
        # Arrange
        body = self.padded_body()
        body.Placement = placement(1.0, 2.0, 3.0, axis=(0, 0, 1), angle=90.0)
        self.document().recompute()

        # Act
        envelope = self.set_parameters("Body", {"Placement": base(x=10.0)})

        # Assert
        self.assertEqual(envelope["status"], "OK", envelope.get("detail"))
        self.assertEqual(envelope["structured_content"]["undo_steps"], 1)
        stored = self.document().getObject("Body").Placement
        self.assertEqual(tuple(stored.Base), (10.0, 2.0, 3.0))
        self.assertAlmostEqual(math.degrees(stored.Rotation.Angle), 90.0)
        self.assertEqual(self.undo()["status"], "OK")
        restored = self.document().getObject("Body").Placement
        self.assertEqual(tuple(restored.Base), (1.0, 2.0, 3.0))

    def test_Should_rotate_and_keep_the_base_When_a_rotation_is_written(self):
        # Arrange
        self.padded_body()
        self.document().getObject("Body").Placement = placement(100.0, 0.0, 0.0)

        # Act
        envelope = self.set_parameters("Body", {"Placement": rotation((0, 0, 1), 90.0)})

        # Assert
        self.assertEqual(envelope["status"], "OK", envelope.get("detail"))
        stored = self.document().getObject("Body").Placement
        self.assertEqual(tuple(stored.Base), (100.0, 0.0, 0.0))
        self.assertAlmostEqual(math.degrees(stored.Rotation.Angle), 90.0)

    def test_Should_report_unchanged_without_a_transaction_When_the_placement_is_equal(self):
        # Arrange
        self.padded_body()
        self.document().getObject("Body").Placement = placement(4.0, 5.0, 6.0)
        undo_before = self.document().UndoCount

        # Act
        envelope = self.set_parameters("Body", {"Placement": base(x=4.0, y=5.0, z=6.0)})

        # Assert
        self.assertEqual(envelope["status"], "OK", envelope.get("detail"))
        content = envelope["structured_content"]
        self.assertEqual(content["unchanged"], ["Placement"])
        self.assertEqual(content["undo_steps"], 0)
        self.assertNotIn("mutation", content)
        self.assertEqual(self.document().UndoCount, undo_before)

    def test_Should_report_unchanged_When_the_placement_object_is_empty(self):
        # Arrange
        self.padded_body()

        # Act
        envelope = self.set_parameters("Body", {"Placement": {"base": {}}})

        # Assert
        self.assertEqual(envelope["structured_content"]["unchanged"], ["Placement"])

    def test_Should_report_unchanged_When_the_label_is_already_held(self):
        # Arrange
        self.padded_body()

        # Act
        envelope = self.set_parameters("Block", {"Label": "Block"})

        # Assert
        content = envelope["structured_content"]
        self.assertEqual(content["unchanged"], ["Label"])
        self.assertEqual(content["undo_steps"], 0)

    def test_Should_open_the_bracket_When_an_equal_label_is_mixed_with_a_numeric(self):
        # Arrange
        self.padded_body()

        # Act
        envelope = self.set_parameters("Block", {"Length": mm(5.0), "Label": "Block"})

        # Assert
        self.assertIn("mutation", envelope["structured_content"])
        self.assertEqual(envelope["structured_content"]["undo_steps"], 1)

    def test_Should_refuse_before_the_bracket_When_the_placement_is_malformed(self):
        # Arrange
        self.padded_body()

        # Act
        message = self.assert_rejected_pre_bracket(
            lambda: tuple(self.document().getObject("Body").Placement.Base),
            features.feature_set_parameters,
            self.registry,
            doc=self.handle,
            feature="Body",
            parameters={"Placement": rotation((0, 0, 0), 30.0)},
        )

        # Assert
        self.assertIn("Body.Placement", message)

    def test_Should_refuse_before_the_bracket_When_a_string_value_is_not_a_string(self):
        # Arrange
        self.padded_body()

        # Act
        message = self.assert_rejected_pre_bracket(
            lambda: self.document().getObject("Block").Label,
            features.feature_set_parameters,
            self.registry,
            doc=self.handle,
            feature="Block",
            parameters={"Label": 5},
        )

        # Assert
        self.assertIn("Block.Label", message)


class _ResetsPlacement:
    """A Python feature whose recompute puts its placement back at the origin."""

    def __init__(self, obj):
        obj.Proxy = self

    reset_note = False

    def execute(self, obj):
        obj.Placement = App.Placement()
        if self.reset_note:
            obj.Note = ""


class _ResetsTiny:
    """A Python feature whose recompute puts a ``Tiny`` above 0.1 back at zero."""

    def execute(self, obj):
        if obj.Tiny > 0.1:
            obj.Tiny = 0.0


class PlacementBoundTest(_PlacementFixture):
    def test_Should_store_the_base_When_a_component_is_at_the_bound(self):
        # Arrange
        self.padded_body()

        # Act
        envelope = self.dispatch("Body", {"Placement": base(x=1e9)})

        # Assert
        self.assertEqual(envelope["status"], "OK", envelope.get("detail"))
        self.assertEqual(self.document().getObject("Body").Placement.Base.x, 1e9)

    def test_Should_refuse_before_the_bracket_When_a_component_is_above_the_bound(self):
        # Arrange
        self.padded_body()

        # Act
        envelope = self.dispatch("Body", {"Placement": base(x=1e9 + 1.0)})

        # Assert
        self.assertEqual(envelope["status"], "INVALID_INPUT", envelope.get("detail"))
        self.assertEqual(envelope["detail"]["code"], "parameters.out_of_range")
        self.assertIn("Body.Placement.base.x", envelope["detail"]["message"])
        self.assertEqual(self.document().getObject("Body").Placement.Base.x, 0.0)
        self.assertEqual(_snapshot_leftovers(), [])

    def test_Should_report_the_stored_placement_When_a_placement_is_written(self):
        # Arrange
        self.padded_body()

        # Act
        envelope = self.dispatch("Body", {"Placement": base(x=3.0)})

        # Assert
        self.assertEqual(envelope["status"], "OK", envelope.get("detail"))
        reported = envelope["structured_content"]["placements"]["Placement"]
        self.assertEqual(reported["requested"], base(x=3.0))
        self.assertEqual(reported["stored"]["base"]["x"], {"value": 3.0, "unit": "mm"})
        self.assertEqual(reported["stored"]["base"]["y"], {"value": 0.0, "unit": "mm"})
        self.assertAlmostEqual(reported["stored"]["rotation"]["angle"]["value"], 0.0)


class OverwrittenValueTest(_PlacementFixture):
    def assert_overwritten(self, envelope, feature):
        self.assertEqual(envelope["status"], "RECOMPUTE_ERROR", envelope.get("detail"))
        self.assertEqual(envelope["detail"]["code"], "parameters.value_overwritten")
        self.assertIn(f"{feature}.Placement", envelope["detail"]["message"])
        block = envelope["structured_content"]["mutation"]
        self.assertTrue(block["rolled_back"])
        self.assertEqual(_snapshot_leftovers(), [])

    def test_Should_refuse_before_the_bracket_and_name_the_offset_When_an_attached_sketch_is_placed(
        self,
    ):
        # Arrange
        self.padded_body()

        # Act
        message = self.assert_rejected_pre_bracket(
            lambda: tuple(self.document().getObject("Profile").Placement.Base),
            features.feature_set_parameters,
            self.registry,
            doc=self.handle,
            feature="Profile",
            parameters={"Placement": base(x=5.0)},
        )

        # Assert
        self.assertIn("Profile.Placement is read-only", message)
        self.assertIn("AttachmentOffset", message)

    def test_Should_refuse_before_the_bracket_When_a_feature_inside_a_body_is_placed(self):
        # Arrange
        self.padded_body()

        # Act
        message = self.assert_rejected_pre_bracket(
            lambda: tuple(self.document().getObject("Block").Placement.Base),
            features.feature_set_parameters,
            self.registry,
            doc=self.handle,
            feature="Block",
            parameters={"Placement": base(x=7.0)},
        )

        # Assert
        self.assertIn("Block.Placement is read-only", message)
        self.assertIn("move the Body", message)

    def test_Should_roll_back_When_a_python_feature_resets_the_placement(self):
        # Arrange
        feature = self.document().addObject("Part::FeaturePython", "Py")
        _ResetsPlacement(feature)
        self.document().recompute()

        # Act
        envelope = self.dispatch("Py", {"Placement": base(x=7.0)})

        # Assert
        self.assert_overwritten(envelope, "Py")
        self.assertEqual(tuple(self.document().getObject("Py").Placement.Base), (0, 0, 0))

    def test_Should_roll_back_When_a_python_feature_resets_a_string_property(self):
        # Arrange
        feature = self.document().addObject("Part::FeaturePython", "Py")
        feature.addProperty("App::PropertyString", "Note", "Meta")
        _ResetsPlacement(feature)
        feature.Proxy.reset_note = True
        self.document().recompute()

        # Act
        envelope = self.dispatch("Py", {"Note": "rev B"})

        # Assert
        self.assertEqual(envelope["status"], "RECOMPUTE_ERROR", envelope.get("detail"))
        self.assertEqual(envelope["detail"]["code"], "parameters.value_overwritten")
        self.assertIn("Py.Note", envelope["detail"]["message"])
        self.assertEqual(self.document().getObject("Py").Note, "")

    def test_Should_name_the_feature_and_its_state_When_the_call_rolls_back(self):
        # Arrange
        feature = self.document().addObject("Part::FeaturePython", "Py")
        _ResetsPlacement(feature)
        self.document().recompute()

        # Act
        envelope = self.dispatch("Py", {"Placement": base(x=7.0)})

        # Assert
        content = envelope["structured_content"]
        self.assertEqual(content["feature"], "Py")
        self.assertIn("feature_state", content)

    def test_Should_roll_back_When_an_expression_drives_a_numeric_property(self):
        # Arrange
        self.padded_body()
        self.document().getObject("Block").setExpression("Length", "3 mm")
        self.document().recompute()

        # Act
        envelope = self.dispatch("Block", {"Length": mm(7.0)})

        # Assert
        self.assertEqual(envelope["status"], "RECOMPUTE_ERROR", envelope.get("detail"))
        self.assertEqual(envelope["detail"]["code"], "parameters.value_overwritten")
        self.assertIn("Block.Length", envelope["detail"]["message"])
        self.assertTrue(envelope["structured_content"]["mutation"]["rolled_back"])
        self.assertAlmostEqual(self.document().getObject("Block").Length.Value, 3.0)

    def test_Should_roll_back_When_an_expression_drives_the_placement(self):
        # Arrange
        body = self.padded_body()
        body.setExpression(".Placement.Base.x", "3 mm")
        self.document().recompute()

        # Act
        envelope = self.dispatch("Body", {"Placement": base(x=9.0)})

        # Assert
        self.assert_overwritten(envelope, "Body")
        self.assertAlmostEqual(self.document().getObject("Body").Placement.Base.x, 3.0)

    def test_Should_move_the_attached_sketch_When_the_attachment_offset_is_written(self):
        # Arrange
        self.padded_body()

        # Act
        envelope = self.dispatch("Profile", {"AttachmentOffset": base(z=4.0)})

        # Assert
        self.assertEqual(envelope["status"], "OK", envelope.get("detail"))
        profile = self.document().getObject("Profile")
        self.assertAlmostEqual(profile.Placement.Base.z, 4.0)
        self.assertAlmostEqual(profile.AttachmentOffset.Base.z, 4.0)

    def test_Should_refuse_with_a_code_When_an_unattached_object_gets_an_attachment_offset(self):
        # Arrange
        body = self.empty_body()
        loose = self.rect_sketch(body, "Loose", 0.0, 0.0, 4.0, 4.0)
        self.assertEqual(loose.MapMode, "Deactivated")

        # Act
        envelope = self.dispatch("Loose", {"AttachmentOffset": base(z=1.0)})

        # Assert
        self.assertEqual(envelope["status"], "INVALID_INPUT", envelope.get("detail"))
        self.assertEqual(envelope["detail"]["code"], "parameters.not_attached")
        self.assertAlmostEqual(self.document().getObject("Loose").AttachmentOffset.Base.z, 0.0)


class StringWriteTest(_PlacementFixture):
    def test_Should_report_the_stored_label_When_freecad_makes_it_unique(self):
        # Arrange
        self.padded_body()

        # Act
        envelope = self.set_parameters("Block", {"Label": "Profile"})

        # Assert
        self.assertEqual(envelope["status"], "OK", envelope.get("detail"))
        self.assertEqual(
            envelope["structured_content"]["label"],
            {"requested": "Profile", "stored": "Profile001"},
        )
        self.assertEqual(self.document().getObject("Block").Label, "Profile001")

    def test_Should_store_the_label_and_undo_it_When_it_is_unique(self):
        # Arrange
        self.padded_body()

        # Act
        envelope = self.set_parameters("Block", {"Label": "Main block"})

        # Assert
        self.assertEqual(envelope["structured_content"]["label"]["stored"], "Main block")
        self.assertEqual(envelope["structured_content"]["undo_steps"], 1)
        self.assertEqual(self.undo()["status"], "OK")
        self.assertEqual(self.document().getObject("Block").Label, "Block")

    def test_Should_refuse_with_a_code_When_the_string_holds_a_character_freecad_cuts(self):
        # Arrange
        self.padded_body()

        # Act
        envelope = self.dispatch("Block", {"Label": "a\x00b"})

        # Assert
        self.assertEqual(envelope["status"], "INVALID_INPUT", envelope.get("detail"))
        self.assertEqual(envelope["detail"]["code"], "parameters.invalid_string")
        self.assertEqual(self.document().getObject("Block").Label, "Block")

    def test_Should_write_a_string_property_When_it_is_not_a_label(self):
        # Arrange
        self.padded_body()
        block = self.document().getObject("Block")
        block.addProperty("App::PropertyString", "Note", "Meta")

        # Act
        envelope = self.set_parameters("Block", {"Note": "rev B"})

        # Assert
        self.assertEqual(envelope["status"], "OK", envelope.get("detail"))
        self.assertEqual(block.Note, "rev B")
        self.assertNotIn("label", envelope["structured_content"])


class _Stub:
    def __init__(self, **attributes):
        self.Name = "Stub"
        self.__dict__.update(attributes)

    def getPropertyStatus(self, _prop):
        return ["Hidden"]


class ReadBackRuleTest(_FeatureFixture):
    def test_Should_accept_the_offset_When_an_attached_object_has_a_hidden_offset_status(self):
        # Arrange
        # A stub, not the real state: FreeCAD hides the offset of an object attached before its
        # support had a shape, which a document built in a test cannot reproduce cheaply.
        attached = _Stub(MapMode="FlatFace")

        # Act
        features._require_attached_offset(attached, "AttachmentOffset")

        # Assert
        self.assertEqual(attached.MapMode, "FlatFace")

    def test_Should_refuse_the_offset_When_the_map_mode_is_deactivated(self):
        # Arrange
        loose = _Stub(MapMode="Deactivated")

        # Act
        def act():
            features._require_attached_offset(loose, "AttachmentOffset")

        # Assert
        with self.assertRaises(features.ParameterRefusal):
            act()

    def test_Should_tell_two_small_readings_apart_When_they_differ_by_one_part_in_a_thousand(self):
        # Arrange
        before, after = 1e-7, 1.001e-7

        # Act
        same = features._comparable(before) == features._comparable(after)

        # Assert
        self.assertFalse(same)

    def test_Should_read_a_stored_float_as_equal_When_it_differs_by_the_storage_error(self):
        # Arrange
        # 5.6e-17 is the largest error measured between a live value and the same value reopened
        # from a saved file; a larger magnitude scales it.
        cases = {
            "small": (1.0 / 3000.0, 1.0 / 3000.0 + 6e-17),
            "unit": (0.5, 0.5 + 5e-17),
            "large": (1e8 / 3, 1e8 / 3 + 1e-8),
        }
        for label, (before, after) in cases.items():
            with self.subTest(label):
                # Act
                same = features._comparable(before) == features._comparable(after)

                # Assert
                self.assertTrue(same)

    def test_Should_read_nan_as_equal_to_itself_When_the_probe_compares_two_readings(self):
        # Arrange
        nan = float("nan")

        # Act
        first, second = features._comparable(nan), features._comparable(nan)

        # Assert
        self.assertEqual(first, second)


class _DropsOne:
    """A Python feature whose recompute lowers a ``Count`` above 1000 by one."""

    def execute(self, obj):
        if obj.Count > 1000:
            obj.Count -= 1


class IntegerWriteTest(_PlacementFixture):
    def integer_feature(self):
        feature = self.document().addObject("Part::FeaturePython", "Py")
        feature.addProperty("App::PropertyInteger", "Count", "Meta")
        feature.Proxy = _DropsOne()
        self.document().recompute()
        return feature

    def test_Should_refuse_before_the_bracket_When_an_integer_exceeds_the_int32_range(self):
        # Arrange
        feature = self.integer_feature()

        # Act
        envelope = self.dispatch("Py", {"Count": 2**31})

        # Assert
        self.assertEqual(envelope["status"], "INVALID_INPUT", envelope.get("detail"))
        self.assertEqual(envelope["detail"]["code"], "parameters.out_of_range")
        self.assertEqual(feature.Count, 0)
        self.assertEqual(_snapshot_leftovers(), [])

    def test_Should_report_the_difference_When_a_recompute_lowers_a_large_integer_by_one(self):
        # Arrange
        self.integer_feature()

        # Act
        envelope = self.dispatch("Py", {"Count": 2**31 - 1})

        # Assert
        self.assertEqual(envelope["status"], "RECOMPUTE_ERROR", envelope.get("detail"))
        self.assertEqual(envelope["detail"]["code"], "parameters.value_overwritten")
        self.assertEqual(self.document().getObject("Py").Count, 0)


class NumericWriteTest(_PlacementFixture):
    def test_Should_roll_back_When_a_property_clamps_the_written_angle(self):
        # Arrange
        cylinder = self.document().addObject("Part::Cylinder", "Cyl")
        self.document().recompute()

        # Act
        envelope = self.dispatch("Cyl", {"Angle": deg(400.0)})

        # Assert
        self.assertEqual(envelope["status"], "RECOMPUTE_ERROR", envelope.get("detail"))
        self.assertEqual(envelope["detail"]["code"], "parameters.value_overwritten")
        self.assertAlmostEqual(cylinder.Angle.Value, 360.0)

    def test_Should_store_the_angle_When_a_cylinder_angle_is_written(self):
        # Arrange
        cylinder = self.document().addObject("Part::Cylinder", "Cyl")
        self.document().recompute()

        # Act
        envelope = self.dispatch("Cyl", {"Angle": deg(90.0)})

        # Assert
        self.assertEqual(envelope["status"], "OK", envelope.get("detail"))
        self.assertAlmostEqual(cylinder.Angle.Value, 90.0)

    def test_Should_refuse_the_number_When_it_is_beyond_the_float_range(self):
        # Arrange
        self.padded_body()

        # Act
        envelope = self.dispatch("Block", {"FuzzyTolerance": 10**400})

        # Assert
        self.assertEqual(envelope["status"], "INVALID_INPUT", envelope.get("detail"))
        self.assertIn("FuzzyTolerance", envelope["detail"]["message"])

    def test_Should_store_the_float_When_a_unitless_float_is_written(self):
        # Arrange
        self.padded_body()

        # Act
        envelope = self.dispatch("Block", {"FuzzyTolerance": 0.25})

        # Assert
        self.assertEqual(envelope["status"], "OK", envelope.get("detail"))
        self.assertAlmostEqual(self.document().getObject("Block").FuzzyTolerance, 0.25)


class RollbackProofTest(_PlacementFixture):
    def test_Should_prove_the_snapshot_restore_When_a_float_and_a_length_hold_17_digits(self):
        # Arrange
        # The saved file keeps 16 digits, so a probe that compares the raw floats would call the
        # restored 0.1 + 0.2 a mismatch and report the rollback as unproven.
        feature = self.document().addObject("Part::FeaturePython", "Py")
        feature.addProperty("App::PropertyFloat", "Ratio", "Meta")
        feature.addProperty("App::PropertyLength", "Size", "Meta")
        feature.addProperty("App::PropertyFloat", "Big", "Meta")
        feature.Big = 123456789.12345679
        _ResetsPlacement(feature)
        feature.Ratio = 0.1 + 0.2
        feature.Size = 0.1 + 0.2
        self.document().recompute()
        self.document().UndoMode = 0

        # Act
        with mock.patch.object(shim, "enable_undo", return_value=False):
            envelope = self.dispatch(
                "Py", {"Ratio": 0.5, "Size": mm(0.5), "Big": 1.5, "Placement": base(x=7.0)}
            )

        # Assert
        self.assertEqual(envelope["status"], "RECOMPUTE_ERROR", envelope)
        block = envelope["structured_content"]["mutation"]
        self.assertEqual(block["rollback_proven"], "rolled_back_via_snapshot")
        self.assertAlmostEqual(self.document().getObject("Py").Ratio, 0.3)
        self.assertAlmostEqual(self.document().getObject("Py").Size.Value, 0.3)
        self.assertAlmostEqual(self.document().getObject("Py").Big, 123456789.12345679, places=6)

    def test_Should_prove_the_snapshot_restore_When_the_stored_values_are_small(self):
        # Arrange
        # FreeCAD stores 16 decimals, so a value near 3e-4 reopens with a relative error near
        # 2e-13: a probe that reads 15 significant digits calls the restored document different.
        feature = self.document().addObject("Part::FeaturePython", "Py")
        feature.addProperty("App::PropertyFloat", "Ratio", "Meta")
        feature.addProperty("App::PropertyLength", "Size", "Meta")
        feature.addProperty("App::PropertyFloat", "Tiny", "Meta")
        feature.Proxy = _ResetsTiny()
        small = 1.0 / 3000.0
        feature.Ratio = small
        feature.Size = small
        feature.Tiny = small
        feature.Placement = placement(small, 0.0, 0.0, angle=0.5)
        self.document().recompute()
        self.document().UndoMode = 0

        # Act
        with mock.patch.object(shim, "enable_undo", return_value=False):
            envelope = self.dispatch("Py", {"Tiny": 0.5, "Placement": base(x=7.0)})

        # Assert
        self.assertEqual(envelope["status"], "RECOMPUTE_ERROR", envelope)
        block = envelope["structured_content"]["mutation"]
        self.assertEqual(block["rollback_proven"], "rolled_back_via_snapshot")
        restored = self.document().getObject("Py")
        self.assertAlmostEqual(restored.Tiny, small, places=15)
        self.assertAlmostEqual(restored.Placement.Base.x, small, places=15)

    def test_Should_restore_the_label_through_the_snapshot_When_abort_restores_nothing(self):
        # Arrange
        # A label change leaves the shape fingerprint equal, so with the undo stack off only the
        # property read-back can tell that the abort restored nothing.
        feature = self.document().addObject("Part::FeaturePython", "Py")
        _ResetsPlacement(feature)
        self.document().recompute()
        self.document().UndoMode = 0

        # Act
        with mock.patch.object(shim, "enable_undo", return_value=False):
            envelope = self.dispatch("Py", {"Label": "Renamed", "Placement": base(x=7.0)})

        # Assert
        self.assertEqual(envelope["status"], "RECOMPUTE_ERROR", envelope)
        block = envelope["structured_content"]["mutation"]
        self.assertEqual(block["rollback_proven"], "rolled_back_via_snapshot")
        self.assertEqual(self.document().getObject("Py").Label, "Py")
